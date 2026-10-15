"""
services/planilhas.py
=====================
Leitura de uploads e exportação de planilhas — fonte única do portal.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
Cada dashboard tinha a sua ``ler_arquivo`` e a sua ``gerar_excel``: cinco
leitores de upload com encodings e separadores diferentes (um lia ``.xls``,
outro só ``.xlsx``, um devolvia ``DataFrame`` vazio em vez de erro) e cinco
geradores de Excel com cabeçalhos formatados à mão. O resultado prático era o
mesmo arquivo comportando-se de jeito diferente em cada página.

Aqui o contrato é um só:

* :func:`ler_upload` lê ``.csv``/``.xlsx``/``.xlsm``/``.xls`` com detecção de
  encoding, separador e aba — e **levanta** ``ValueError``/``OSError`` em vez de
  engolir o erro (a página decide como avisar o usuário);
* :func:`gerar_excel` devolve o XLSX corporativo (cabeçalho azul TOTALE,
  larguras automáticas, linha congelada) usando ``xlsxwriter`` ou ``openpyxl``;
* :func:`gerar_csv` devolve CSV em ``utf-8-sig`` com decimal ``,`` e separador
  ``;`` — o que abre certo no Excel pt-BR;
* :func:`botao_download_planilha` / :func:`botao_download_csv` padronizam os
  botões com carimbo de data/hora no nome do arquivo.

:mod:`components.dashboard_kit` reexporta a mesma matemática de exportação — a
fonte única é este módulo.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

VERSAO_PLANILHAS = "1.0.0"

#: Encodings tentados, em ordem, para CSV sem declaração de charset.
ENCODINGS_CSV: tuple[str, ...] = ("utf-8-sig", "utf-8", "latin-1", "cp1252")

#: Separadores candidatos quando o CSV não declara o delimitador.
SEPARADORES_CSV: tuple[str, ...] = (";", ",", "\t", "|")

#: Extensões aceitas por :func:`ler_upload`.
EXTENSOES_ACEITAS: frozenset[str] = frozenset({".csv", ".txt", ".xlsx", ".xlsm", ".xls"})

#: Cor do cabeçalho das planilhas exportadas (azul oficial TOTALE).
COR_CABECALHO: str = "#012869"

MIME_XLSX = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
MIME_CSV = "text/csv"

__all__ = [
    "COR_CABECALHO",
    "ENCODINGS_CSV",
    "EXTENSOES_ACEITAS",
    "MIME_CSV",
    "MIME_XLSX",
    "SEPARADORES_CSV",
    "VERSAO_PLANILHAS",
    "botao_download_csv",
    "botao_download_planilha",
    "gerar_csv",
    "gerar_excel",
    "gerar_excel_multiabas",
    "larguras_colunas",
    "ler_bytes",
    "ler_upload",
    "nome_com_carimbo",
]


# ====================================================
# 📥 BLOCO 1: LEITURA DE ARQUIVOS ENVIADOS
# ====================================================
def _decodificar_csv(conteudo: bytes) -> str:
    """Decodifica bytes de CSV tentando a lista oficial de encodings."""
    for encoding in ENCODINGS_CSV:
        try:
            return conteudo.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(
        "Não foi possível identificar o encoding do CSV "
        f"(tentados: {', '.join(ENCODINGS_CSV)})."
    )


def _detectar_separador(amostra: str) -> str:
    """Separador mais provável do CSV (``csv.Sniffer`` com contagem de reserva)."""
    try:
        return csv.Sniffer().sniff(amostra, delimiters="".join(SEPARADORES_CSV)).delimiter
    except csv.Error:
        return max(SEPARADORES_CSV, key=amostra.count)


def _ler_csv_bytes(
    conteudo: bytes,
    *,
    separador: str | None = None,
    dtype: Any = None,
    manter_na: bool = True,
    **kwargs: Any,
) -> pd.DataFrame:
    texto = _decodificar_csv(conteudo)
    delimitador = separador or _detectar_separador(texto[:10_000])
    padrao: dict[str, Any] = {
        "sep": delimitador,
        "engine": "python",
        "on_bad_lines": "skip",
        "dtype": dtype,
    }
    if not manter_na:
        padrao["keep_default_na"] = False
        padrao["na_values"] = [""]
    padrao.update(kwargs)
    return pd.read_csv(io.StringIO(texto), **padrao)


def ler_bytes(
    conteudo: bytes,
    filename: str,
    *,
    separador: str | None = None,
    dtype: Any = None,
    manter_na: bool = True,
    aba: str | int | None = 0,
    **kwargs: Any,
) -> pd.DataFrame:
    """Lê o conteúdo bruto de um arquivo (mesma semântica de :func:`ler_upload`).

    Útil quando os bytes já estão em memória — robô, cache ou download.
    """
    if not conteudo:
        raise ValueError("O arquivo enviado está vazio.")
    extensao = Path(str(filename or "")).suffix.lower()
    if extensao in {".csv", ".txt"}:
        return _ler_csv_bytes(
            conteudo, separador=separador, dtype=dtype, manter_na=manter_na, **kwargs
        )
    if extensao in {".xlsx", ".xlsm", ".xls"}:
        padrao: dict[str, Any] = {"sheet_name": aba, "dtype": dtype}
        if extensao != ".xls":
            padrao["engine"] = "openpyxl"
        padrao.update(kwargs)
        return pd.read_excel(io.BytesIO(conteudo), **padrao)
    raise ValueError(
        f"Formato '{extensao or filename}' não suportado. "
        f"Use {', '.join(sorted(EXTENSOES_ACEITAS))}."
    )


def ler_upload(
    arquivo: Any,
    *,
    separador: str | None = None,
    dtype: Any = None,
    manter_na: bool = True,
    aba: str | int | None = 0,
    **kwargs: Any,
) -> pd.DataFrame:
    """Lê um ``UploadedFile`` do Streamlit (ou bytes/tupla ``(nome, bytes)``).

    Nunca devolve ``DataFrame`` vazio para disfarçar erro: arquivo vazio,
    extensão desconhecida ou CSV ilegível levantam ``ValueError`` — a página
    trata e mostra a mensagem no padrão do portal.
    """
    if arquivo is None:
        raise ValueError("Nenhum arquivo selecionado.")
    if isinstance(arquivo, (bytes, bytearray)):
        raise ValueError("Use ler_bytes() quando já tiver os bytes do arquivo.")
    nome = str(getattr(arquivo, "name", "") or "")
    conteudo = arquivo.getvalue()
    return ler_bytes(
        conteudo,
        nome,
        separador=separador,
        dtype=dtype,
        manter_na=manter_na,
        aba=aba,
        **kwargs,
    )


# ====================================================
# 📤 BLOCO 2: EXPORTAÇÃO CORPORATIVA
# ====================================================
def nome_com_carimbo(nome_base: str, extensao: str = "xlsx", *, quando: datetime | None = None) -> str:
    """``producao`` → ``producao_20261014_1830.xlsx`` (sem espaços/acentos)."""
    instante = quando or datetime.now()
    limpo = (
        str(nome_base or "dados")
        .strip()
        .replace(" ", "_")
        .replace("/", "-")
    )
    sufixo = str(extensao or "xlsx").lstrip(".")
    return f"{limpo}_{instante:%Y%m%d_%H%M}.{sufixo}"


def larguras_colunas(df: pd.DataFrame, *, maxima: int = 60) -> list[int]:
    """Largura sugerida por coluna: cabeçalho + amostra de até 200 linhas.

    Coluna inteiramente vazia (``NaN``) não pode derrubar a exportação: o
    comprimento máximo cai no piso de 10 caracteres.
    """
    larguras: list[int] = []
    for coluna in df.columns:
        comprimentos = (
            df[coluna].head(200).fillna("").astype(str).str.len().dropna()
        )
        maior = comprimentos.max() if not comprimentos.empty else 10
        try:
            maior_int = int(maior)
        except (TypeError, ValueError):
            maior_int = 10
        larguras.append(min(max(len(str(coluna)), maior_int) + 2, maxima))
    return larguras


def _nomes_sanitizados(aba: str) -> str:
    """Nome de aba válido no Excel (sem ``[]:*?/\`` e com 31 caracteres)."""
    import re

    limpo = re.sub(r"[\[\]:*?/\\]", "_", str(aba or "")).strip()
    return limpo[:31] or "Dados"


def _nome_aba_unico(nome: Any, usados: set[str]) -> str:
    """Nome de aba sanitizado e único (``Equipe A`` repetida → ``Equipe A_1``)."""
    import re

    base = re.sub(r"[\\/*?:\[\]]", "-", str(nome)).strip().strip("'")
    base = re.sub(r"\s+", " ", base) or "Sem_Nome"
    base = base[:31]
    candidato = base
    sufixo = 1
    while candidato.lower() in usados:
        extra = f"_{sufixo}"
        candidato = f"{base[: 31 - len(extra)]}{extra}"
        sufixo += 1
    usados.add(candidato.lower())
    return candidato


def _colunas_percentuais(df: pd.DataFrame, termos: Sequence[str]) -> set[int]:
    """Índices (1-based) das colunas cujo cabeçalho indica percentual."""
    achadas: set[int] = set()
    for indice, coluna in enumerate(df.columns, start=1):
        nome = str(coluna).upper()
        if any(termo.upper() in nome for termo in termos):
            achadas.add(indice)
    return achadas


def _excel_xlsxwriter(
    df: pd.DataFrame,
    aba: str,
    *,
    autofiltro: bool = False,
    colunas_pct: Sequence[str] = (),
) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as escritor:
        df.to_excel(escritor, sheet_name=aba, index=False)
        planilha = escritor.sheets[aba]
        formato = escritor.book.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": COR_CABECALHO,
                "border": 0,
                "text_wrap": False,
                "valign": "vcenter",
                "align": "center",
            }
        )
        for indice, (coluna, largura) in enumerate(zip(df.columns, larguras_colunas(df))):
            planilha.write(0, indice, str(coluna), formato)
            planilha.set_column(indice, indice, largura)
        planilha.freeze_panes(1, 0)
        if autofiltro:
            planilha.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))
        if colunas_pct:
            formato_pct = escritor.book.add_format({"num_format": "0.00%"})
            for indice in sorted(_colunas_percentuais(df, colunas_pct)):
                planilha.set_column(indice - 1, indice - 1, None, formato_pct)
    return buffer.getvalue()


def _excel_openpyxl(
    df: pd.DataFrame,
    aba: str,
    *,
    autofiltro: bool = False,
    colunas_pct: Sequence[str] = (),
) -> bytes:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as escritor:
        df.to_excel(escritor, sheet_name=aba, index=False)
        planilha = escritor.sheets[aba]
        preenchimento = PatternFill("solid", fgColor=COR_CABECALHO.lstrip("#"))
        for indice, largura in enumerate(larguras_colunas(df), start=1):
            celula = planilha.cell(row=1, column=indice)
            celula.font = Font(bold=True, color="FFFFFF")
            celula.fill = preenchimento
            celula.alignment = Alignment(horizontal="center", vertical="center")
            planilha.column_dimensions[get_column_letter(indice)].width = largura
        planilha.freeze_panes = "A2"
        if autofiltro:
            planilha.auto_filter.ref = planilha.dimensions
        if colunas_pct:
            for indice in sorted(_colunas_percentuais(df, colunas_pct)):
                for linha in range(2, planilha.max_row + 1):
                    planilha.cell(linha, indice).number_format = "0.00%"
    return buffer.getvalue()


def gerar_excel(
    df: pd.DataFrame,
    aba: str = "Dados",
    *,
    autofiltro: bool = False,
    colunas_pct: Sequence[str] = (),
) -> bytes:
    """XLSX corporativo em memória: cabeçalho TOTALE, larguras e linha congelada.

    Prefere ``xlsxwriter``; sem ele no ambiente usa ``openpyxl`` — ambos são
    dependências do projeto, então a exportação nunca fica indisponível.

    ``autofiltro`` liga o filtro automático do Excel na primeira linha e
    ``colunas_pct`` formata como percentual as colunas cujo cabeçalho contém
    algum dos termos (ex.: ``("TAXA", "%")``).
    """
    if df is None:
        raise ValueError("Não há DataFrame para exportar.")
    nome_aba = _nomes_sanitizados(aba)
    try:
        import xlsxwriter  # noqa: F401
    except ImportError:
        return _excel_openpyxl(df, nome_aba, autofiltro=autofiltro, colunas_pct=colunas_pct)
    return _excel_xlsxwriter(df, nome_aba, autofiltro=autofiltro, colunas_pct=colunas_pct)


def gerar_csv(
    df: pd.DataFrame,
    *,
    separador: str = ";",
    decimal: str = ",",
    colunas: Sequence[str] | None = None,
) -> bytes:
    """CSV ``utf-8-sig`` pronto para o Excel pt-BR (``;`` e vírgula decimal)."""
    if df is None:
        raise ValueError("Não há DataFrame para exportar.")
    recorte = df[list(colunas)] if colunas else df
    return recorte.to_csv(
        index=False, sep=separador, decimal=decimal, encoding="utf-8-sig"
    ).encode("utf-8-sig")


# ====================================================
# 🔘 BLOCO 3: BOTÕES DE DOWNLOAD PADRONIZADOS
# ====================================================
def botao_download_planilha(
    df: pd.DataFrame,
    *,
    nome_arquivo: str,
    chave: str,
    rotulo: str = "⬇️ Excel",
    aba: str = "Dados",
    container: Any = None,
    **kwargs: Any,
) -> Any:
    """Botão de download do XLSX corporativo (gerado sob demanda)."""
    import streamlit as st

    alvo = container if container is not None else st
    return alvo.download_button(
        rotulo,
        data=gerar_excel(df, aba=aba),
        file_name=nome_com_carimbo(nome_arquivo, "xlsx"),
        mime=MIME_XLSX,
        key=chave,
        width="stretch",
        **kwargs,
    )


def botao_download_csv(
    df: pd.DataFrame,
    *,
    nome_arquivo: str,
    chave: str,
    rotulo: str = "⬇️ CSV",
    colunas: Sequence[str] | None = None,
    container: Any = None,
    **kwargs: Any,
) -> Any:
    """Botão de download do CSV em utf-8-sig (abre certo no Excel pt-BR)."""
    import streamlit as st

    alvo = container if container is not None else st
    return alvo.download_button(
        rotulo,
        data=gerar_csv(df, colunas=colunas),
        file_name=nome_com_carimbo(nome_arquivo, "csv"),
        mime=MIME_CSV,
        key=chave,
        width="stretch",
        **kwargs,
    )


def gerar_excel_multiabas(
    df: pd.DataFrame,
    *,
    coluna_grupo: str,
    aba_geral: str = "Consolidado_Geral",
    max_abas: int = 150,
) -> bytes:
    """XLSX com uma aba consolidada + uma aba por grupo de ``coluna_grupo``.

    Regras herdadas das páginas que reimplementavam este formato:

    * nome de aba válido (≤31 caracteres, sem ``\\/*?:[]``) e **único** — grupos
      com o mesmo nome ganham sufixo ``_1``, ``_2``…;
    * acima de ``max_abas`` grupos as abas extras são omitidas (o Excel não
      aceita volume ilimitado e o arquivo ficaria pesado);
    * cabeçalho corporativo, largura fixa, linha congelada e autofiltro em todas
      as abas (com ``xlsxwriter``; sem ele, o ``openpyxl`` faz o equivalente).
    """
    if df is None:
        raise ValueError("Não há DataFrame para exportar.")

    try:
        import xlsxwriter  # noqa: F401

        engine = "xlsxwriter"
    except ImportError:
        engine = "openpyxl"

    grupos: list[tuple[Any, pd.DataFrame]] = []
    if coluna_grupo in df.columns and not df.empty:
        grupos = list(df.groupby(coluna_grupo, dropna=False))
        if len(grupos) > max_abas:
            logger.warning(
                "Grupos (%s) acima do limite de abas (%s); abas extras omitidas.",
                len(grupos),
                max_abas,
            )
            grupos = grupos[:max_abas]

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine=engine) as escritor:
        nomes_usados: set[str] = set()
        df.to_excel(escritor, sheet_name=_nome_aba_unico(aba_geral, nomes_usados), index=False)
        for nome_grupo, df_grupo in grupos:
            df_grupo.to_excel(
                escritor,
                sheet_name=_nome_aba_unico(nome_grupo, nomes_usados),
                index=False,
            )

        if engine == "xlsxwriter":
            livro: Any = escritor.book
            formato = livro.add_format(
                {
                    "bold": True,
                    "bg_color": COR_CABECALHO,
                    "font_color": "white",
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                    "text_wrap": True,
                }
            )
            colunas = list(df.columns)
            ultima_coluna = max(len(colunas) - 1, 0)
            for planilha in escritor.sheets.values():
                alvo: Any = planilha
                alvo.set_column(0, ultima_coluna, 22)
                alvo.freeze_panes(1, 0)
                for indice, nome_coluna in enumerate(colunas):
                    alvo.write(0, indice, str(nome_coluna), formato)
                if ultima_coluna:
                    alvo.autofilter(0, 0, 0, ultima_coluna)

    return buffer.getvalue()
