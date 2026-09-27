"""
robo/robo_local.py
==================
Robô monitor de pasta local para arquivos TOTALE (CSV/Excel).

Detecção de BASE pelo nome do arquivo:
    • "ABCDM" → NET-ABCDM
    • "SPO"   → NET-LESTE
    • "GRS"   → NET-GUARULHOS

Por padrão entra no pipeline só o arquivo mais recente de cada base.
Exports TOTALE costumam ser snapshot; concatenar o histórico duplica O.S.
No expander da sidebar dá para voltar ao modo "todos os arquivos".

A leitura Excel não depende do registry io.excel.* do pandas. Copia os bytes
antes de parsear, para soltar o lock do OneDrive, e recusa arquivo que mudou
no meio da leitura.
"""

from __future__ import annotations

import fnmatch
import logging
import math
import os
import sys
import tempfile
import zipfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Literal, cast

import pandas as pd

try:
    from pandas.errors import OptionError as PandasOptionError
except ImportError:  # pandas < 1.0
    PandasOptionError = KeyError  # type: ignore[misc, assignment]

try:
    import streamlit as st
except ImportError:  # permite testar a leitura sem o app
    st = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ── Constantes ──────────────────────────────────────────────────────
PADROES_TOTALE: tuple[str, ...] = (
    "Atividades-*.csv",
    "Atividades-*.xlsx",
    "Atividades-*.xls",
)
EXTENSOES_VALIDAS: tuple[str, ...] = (".csv", ".xlsx", ".xls")
EXTENSOES_TEMP: tuple[str, ...] = (".tmp", ".crdownload", ".partial", ".download", ".part")

MAPA_BASES_ARQUIVO: dict[str, str] = {
    "ABCDM": "NET-ABCDM",
    "SPO": "NET-LESTE",
    "GRS": "NET-GUARULHOS",
}

_VALORES_AUSENTES: frozenset[str] = frozenset(
    {"", "nan", "none", "na", "n/a", "<na>", "nat", "null", "não informado", "nao informado", "-"}
)
_TAMANHO_MINIMO_XLSX: int = 2_000
_TAMANHO_MAXIMO_PADRAO: int = 80 * 1024 * 1024
_LOCK_STALE_SEGUNDOS: int = 180

ModoLeitura = Literal["ultimo_por_base", "todos"]
EtlFn = Callable[[pd.DataFrame, pd.DataFrame], "pd.DataFrame | None"]
FonteSheets = Callable[[], pd.DataFrame] | pd.DataFrame | None
Candidato = tuple[str, float, int]


class ArquivoBloqueadoError(Exception):
    """Arquivo em gravação ou sincronização. O próximo ciclo tenta de novo."""


class _BytesNomeados(BytesIO):
    """BytesIO com .name, para o pandas não inferir a extensão como zip."""

    def __init__(self, raw: bytes, nome: str) -> None:
        super().__init__(raw)
        self.name = nome


@dataclass(frozen=True)
class LeituraArquivo:
    df: pd.DataFrame | None
    erro: str | None
    motor: str | None


@dataclass(frozen=True)
class ResultadoCiclo:
    df: pd.DataFrame | None
    bases: tuple[str, ...]
    arquivos: tuple[str, ...]
    erros: tuple[str, ...]
    bloqueio: str | None
    motores: tuple[str, ...]
    duplicatas_removidas: int


# ── Texto e colunas ─────────────────────────────────────────────────
def _celula_para_texto(valor: object) -> str:
    if valor is None or valor is pd.NA:
        return ""
    if isinstance(valor, bool):
        return "True" if valor else "False"
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        if math.isnan(valor):
            return ""
        if valor.is_integer():
            return str(int(valor))
        return str(valor).strip()
    if isinstance(valor, str):
        texto = valor.strip()
    else:
        texto = str(valor).strip()
    if texto.lower() in {"nat", "<na>", "nan", "none"}:
        return ""
    corpo = texto[:-2] if texto.endswith(".0") else ""
    if corpo and corpo.replace("-", "", 1).isdigit():
        return corpo
    return texto


def _nomes_colunas_unicos(nomes: Iterable[object]) -> list[str]:
    vistos: dict[str, int] = {}
    saida: list[str] = []
    for i, bruto in enumerate(nomes):
        nome = str(bruto).replace("\ufeff", "").replace("\xa0", " ").strip()
        if not nome or nome.lower().startswith("unnamed"):
            nome = f"col_{i}"
        if nome in vistos:
            vistos[nome] += 1
            nome = f"{nome}.{vistos[nome]}"
        else:
            vistos[nome] = 0
        saida.append(nome)
    return saida


def _padronizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty and len(df.columns) == 0:
        return df.copy()
    saida = df.copy()
    saida.columns = _nomes_colunas_unicos(list(saida.columns))
    for col in saida.columns:
        texto = saida[col].map(_celula_para_texto)
        saida[col] = texto.mask(texto.str.strip().str.lower().isin(_VALORES_AUSENTES))
    return saida.dropna(how="all")


def _cabecalho_fraco(colunas: Sequence[object]) -> bool:
    nomes = [str(c).strip() for c in colunas]
    if not nomes:
        return True
    ruins = sum(
        1
        for n in nomes
        if not n or n.lower().startswith("unnamed") or n.lower().startswith("col_")
    )
    return ruins / len(nomes) >= 0.5


def _alinhar_colunas_esperadas(
    df: pd.DataFrame,
    esperadas: Sequence[str] | None,
) -> pd.DataFrame:
    if not esperadas:
        return df
    por_chave = {str(c).casefold(): str(c) for c in df.columns}
    renomear: dict[str, str] = {}
    for esperada in esperadas:
        if esperada in df.columns:
            continue
        atual = por_chave.get(esperada.casefold())
        if atual and atual not in renomear:
            renomear[atual] = esperada
    if not renomear:
        return df
    return df.rename(columns=renomear)


def _chaves_colunas(df: pd.DataFrame) -> set[str]:
    return {str(c).casefold() for c in df.columns}


def _contem_colunas(df: pd.DataFrame, esperadas: Sequence[str] | None) -> bool:
    if not esperadas:
        return True
    chaves = _chaves_colunas(df)
    return all(esperada.casefold() in chaves for esperada in esperadas)


def _faltam_colunas(df: pd.DataFrame, esperadas: Sequence[str] | None) -> list[str]:
    if not esperadas:
        return []
    chaves = _chaves_colunas(df)
    return [c for c in esperadas if c.casefold() not in chaves]


# ── Detecção de base ────────────────────────────────────────────────
def detectar_base_arquivo(caminho_ou_nome: str | None) -> str | None:
    marcador = detectar_marcador_arquivo(caminho_ou_nome)
    if marcador is None:
        return None
    return MAPA_BASES_ARQUIVO.get(marcador)


def detectar_marcador_arquivo(caminho_ou_nome: str | None) -> str | None:
    if not caminho_ou_nome:
        return None
    nome = Path(str(caminho_ou_nome)).name.upper()
    for marcador in sorted(MAPA_BASES_ARQUIVO, key=len, reverse=True):
        if marcador in nome:
            return marcador
    return None


def _canonizar_coluna_base(df: pd.DataFrame) -> pd.DataFrame:
    variantes = [col for col in df.columns if str(col).casefold() == "base" and col != "BASE"]
    if not variantes:
        return df
    saida = df.copy()
    if "BASE" not in saida.columns:
        saida = saida.rename(columns={variantes[0]: "BASE"})
        variantes = variantes[1:]
    for col in variantes:
        texto = saida["BASE"].map(_celula_para_texto).str.strip().str.lower()
        vazios = texto.isin(_VALORES_AUSENTES)
        saida.loc[vazios, "BASE"] = saida.loc[vazios, col]
        saida = saida.drop(columns=[col])
    return saida


def _aplicar_base_no_dataframe(df: pd.DataFrame, base: str) -> pd.DataFrame:
    saida = _canonizar_coluna_base(df)
    if "BASE" not in saida.columns:
        saida["BASE"] = base
        return saida
    texto = saida["BASE"].map(_celula_para_texto).str.strip().str.lower()
    vazios = texto.isin(_VALORES_AUSENTES)
    saida.loc[vazios, "BASE"] = base
    return saida


def _unificar_nomes_colunas(frames: list[pd.DataFrame]) -> list[pd.DataFrame]:
    """Uma grafia por coluna na junção. O primeiro arquivo define o nome."""
    canonico: dict[str, str] = {}
    unificados: list[pd.DataFrame] = []
    for df in frames:
        renomear: dict[str, str] = {}
        for col in df.columns:
            chave = str(col).casefold()
            nome = canonico.get(chave)
            if nome is None:
                canonico[chave] = str(col)
            elif nome != col:
                renomear[str(col)] = nome
        unificados.append(df.rename(columns=renomear) if renomear else df)
    return unificados


# ── Arquivos ────────────────────────────────────────────────────────
def obter_pasta_robo_padrao() -> str:
    base = Path(__file__).resolve().parent
    for cand in (base / "dados", Path.home() / "robo", Path.home() / "Downloads"):
        if cand.is_dir():
            return str(cand.resolve())
    return str(Path.home() / "Downloads")


def formatar_tamanho(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_ / (1024 * 1024):.2f} MB"


def obter_metadados_arquivo(caminho: str | None) -> dict[str, str]:
    vazio = {
        "nome": Path(caminho).name if caminho else "Desconhecido",
        "ext": Path(caminho).suffix.lower() if caminho else "",
        "tamanho": "—",
        "modificado": "—",
        "caminho_completo": caminho or "",
    }
    if not caminho or not os.path.exists(caminho):
        return vazio
    try:
        p = Path(caminho)
        stat = p.stat()
        return {
            "nome": p.name,
            "ext": p.suffix.lower(),
            "tamanho": formatar_tamanho(stat.st_size),
            "modificado": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
            "caminho_completo": str(p.resolve()),
        }
    except OSError:
        return vazio


def _stat_basico(caminho: str) -> tuple[float | None, int | None]:
    try:
        st_ = os.stat(caminho)
        return float(st_.st_mtime), int(st_.st_size)
    except OSError:
        return None, None


def _arquivo_ignorado(nome: str) -> bool:
    baixo = nome.lower()
    if baixo.startswith("~$") or baixo.startswith("."):
        return True
    return baixo.endswith(EXTENSOES_TEMP)


def _listar_arquivos(pasta: Path, recursivo: bool) -> list[Path]:
    try:
        if recursivo:
            return [p for p in pasta.rglob("*") if p.is_file()]
        return [p for p in pasta.iterdir() if p.is_file()]
    except OSError as e:
        logger.warning("Não foi possível listar %s: %s", pasta, e)
        return []


def _casa_padrao(nome: str, padroes: Sequence[str]) -> bool:
    baixo = nome.lower()
    return any(fnmatch.fnmatch(baixo, p.lower()) for p in padroes)


def _listar_candidatos_com_stat(
    pasta: str,
    padroes: tuple[str, ...] = PADROES_TOTALE,
    recursivo: bool = False,
) -> list[Candidato]:
    p = Path(pasta)
    if not p.is_dir():
        return []

    arquivos = [arq for arq in _listar_arquivos(p, recursivo) if not _arquivo_ignorado(arq.name)]
    encontrados = [arq for arq in arquivos if _casa_padrao(arq.name, padroes)]

    if not encontrados:
        encontrados = [
            arq
            for arq in arquivos
            if "atividades" in arq.name.lower() and arq.suffix.lower() in EXTENSOES_VALIDAS
        ]
    if not encontrados:
        marcadores = tuple(m.lower() for m in MAPA_BASES_ARQUIVO)
        encontrados = [
            arq
            for arq in arquivos
            if arq.suffix.lower() in EXTENSOES_VALIDAS
            and any(m in arq.name.lower() for m in marcadores)
        ]

    candidatos: list[Candidato] = []
    for arq in encontrados:
        mtime, size = _stat_basico(str(arq))
        if mtime is None or size is None or size <= 0:
            continue
        candidatos.append((str(arq), mtime, size))
    candidatos.sort(key=lambda item: item[1], reverse=True)
    return candidatos


def buscar_arquivo_mais_recente(
    pasta: str,
    padroes: tuple[str, ...] = PADROES_TOTALE,
) -> tuple[str | None, float | None, int | None]:
    candidatos = _listar_candidatos_com_stat(pasta, padroes)
    if not candidatos:
        return None, None, None
    caminho, mtime, size = candidatos[0]
    return caminho, mtime, size


def mapear_arquivos_por_base(pasta: str, recursivo: bool = False) -> dict[str, Candidato]:
    por_base: dict[str, Candidato] = {}
    for item in _listar_candidatos_com_stat(pasta, recursivo=recursivo):
        base = detectar_base_arquivo(item[0])
        if base and base not in por_base:
            por_base[base] = item
    return por_base


def selecionar_arquivos(
    candidatos: Sequence[Candidato],
    modo: ModoLeitura = "ultimo_por_base",
) -> list[Candidato]:
    """Escolhe o que entra no pipeline.

    ultimo_por_base: o mais novo de cada marcador. Arquivo sem SPO/GRS/ABCDM
    só entra se nenhum arquivo marcado foi encontrado.
    todos: a pasta inteira, do mais novo para o mais antigo.
    """
    if modo == "todos":
        return list(candidatos)

    por_base: dict[str, Candidato] = {}
    sem_marcador: Candidato | None = None
    for item in candidatos:
        base = detectar_base_arquivo(item[0])
        if base is None:
            if sem_marcador is None:
                sem_marcador = item
            continue
        if base not in por_base:
            por_base[base] = item
    if por_base:
        return sorted(por_base.values(), key=lambda item: detectar_base_arquivo(item[0]) or "")
    if sem_marcador is not None:
        return [sem_marcador]
    return []


def contar_arquivos_por_base(candidatos: Sequence[Candidato]) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for caminho, _, _ in candidatos:
        base = detectar_base_arquivo(caminho) or "SEM MARCADOR"
        contagem[base] = contagem.get(base, 0) + 1
    return contagem


# ── Leitura ─────────────────────────────────────────────────────────
def _ler_bytes_estavel(caminho: str, tamanho_maximo: int) -> bytes:
    try:
        tamanho = os.path.getsize(caminho)
    except OSError as e:
        raise ArquivoBloqueadoError(f"'{Path(caminho).name}' não pôde ser medido.") from e
    if tamanho > tamanho_maximo:
        raise ValueError(
            f"'{Path(caminho).name}' tem {formatar_tamanho(tamanho)}, acima do limite de {formatar_tamanho(tamanho_maximo)}."
        )
    if tamanho == 0:
        raise ValueError(f"'{Path(caminho).name}' está vazio.")
    try:
        with open(caminho, "rb") as fh:
            raw = fh.read()
        tamanho_depois = os.path.getsize(caminho)
    except PermissionError as e:
        raise ArquivoBloqueadoError(
            f"'{Path(caminho).name}' está bloqueado (OneDrive/Excel)."
        ) from e
    except OSError as e:
        raise ArquivoBloqueadoError(f"'{Path(caminho).name}' ficou inacessível.") from e
    if len(raw) != tamanho or tamanho_depois != tamanho:
        raise ArquivoBloqueadoError(
            f"'{Path(caminho).name}' mudou durante a leitura. Aguardando o próximo ciclo."
        )
    return raw


def _validar_xlsx(raw: bytes, nome: str) -> None:
    if len(raw) < _TAMANHO_MINIMO_XLSX:
        raise ValueError(f"'{nome}' tem {len(raw)} bytes — download incompleto.")
    bio = BytesIO(raw)
    if not zipfile.is_zipfile(bio):
        raise ValueError(f"'{nome}' não é um .xlsx válido (zip corrompido ou extensão errada).")
    bio.seek(0)
    with zipfile.ZipFile(bio) as zf:
        ruim = zf.testzip()
    if ruim is not None:
        raise ValueError(f"'{nome}' está corrompido no membro interno: {ruim}")


def _ler_excel_via_openpyxl_nativo(raw: bytes, sheet_name: str | int, header: int) -> pd.DataFrame:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(raw), read_only=True, data_only=True)
    try:
        ws = None
        if isinstance(sheet_name, int):
            if 0 <= sheet_name < len(wb.worksheets):
                ws = wb.worksheets[sheet_name]
        elif sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        if ws is None:
            ws = wb.active
        if ws is None and wb.worksheets:
            ws = wb.worksheets[0]
        if ws is None:
            return pd.DataFrame()

        linhas = list(ws.iter_rows(values_only=True))
        if header >= len(linhas):
            return pd.DataFrame()
        header_raw = linhas[header]
        if header_raw is None:
            return pd.DataFrame()

        colunas = _nomes_colunas_unicos(header_raw)
        n_cols = len(colunas)
        data: list[list[object]] = []
        for row in linhas[header + 1 :]:
            valores: list[object] = [celula for celula in row]
            if len(valores) < n_cols:
                valores.extend([None] * (n_cols - len(valores)))
            elif len(valores) > n_cols:
                valores = valores[:n_cols]
            data.append(valores)
        return pd.DataFrame(data, columns=pd.Index(colunas))
    finally:
        wb.close()


def _ler_excel_robusto(
    caminho: str,
    sheet_name: str | int | None = 0,
    header: int = 0,
    tamanho_maximo: int = _TAMANHO_MAXIMO_PADRAO,
) -> tuple[pd.DataFrame, str]:
    planilha: str | int = 0 if sheet_name is None else sheet_name
    ext = Path(caminho).suffix.lower()
    nome = Path(caminho).name
    raw = _ler_bytes_estavel(caminho, tamanho_maximo)
    if ext == ".xlsx":
        _validar_xlsx(raw, nome)

    erros: list[str] = []

    def _tentar(
        rotulo: str,
        fn: Callable[[], pd.DataFrame | dict[str, pd.DataFrame]],
    ) -> pd.DataFrame | None:
        try:
            bruto = fn()
            if isinstance(bruto, dict):
                df = next(iter(bruto.values())) if len(bruto) else pd.DataFrame()
            else:
                df = bruto
            if df.empty:
                erros.append(f"{rotulo}: planilha vazia")
                return None
            return df
        except PandasOptionError as e:
            erros.append(f"{rotulo}: OptionError {e}")
            return None
        except ImportError as e:
            erros.append(f"{rotulo}: engine ausente ({e})")
            return None
        except ArquivoBloqueadoError:
            raise
        except PermissionError as e:
            raise ArquivoBloqueadoError(str(e)) from e
        except Exception as e:
            erros.append(f"{rotulo}: {type(e).__name__}: {e}")
            logger.debug("Falha ao ler %s via %s", nome, rotulo, exc_info=True)
            return None

    def _via_temp(engine: str, sufixo: str) -> pd.DataFrame:
        fd, tmp = tempfile.mkstemp(suffix=sufixo)
        os.close(fd)
        try:
            with open(tmp, "wb") as out:
                out.write(raw)
            return pd.read_excel(
                tmp,
                sheet_name=planilha,
                header=header,
                dtype=str,
                engine=cast(Literal["openpyxl", "calamine", "xlrd"], engine),
            )
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _via_buffer(engine: str, nome_buffer: str) -> pd.DataFrame:
        bio = _BytesNomeados(raw, nome_buffer)
        return pd.read_excel(
            bio,
            sheet_name=planilha,
            header=header,
            dtype=str,
            engine=cast(Literal["openpyxl", "calamine", "xlrd"], engine),
        )

    tentativas: list[tuple[str, Callable[[], pd.DataFrame]]] = []
    if ext == ".xls":
        tentativas.append(("calamine/.xls", lambda: _via_temp("calamine", ".xls")))
        tentativas.append(("xlrd/.xls", lambda: _via_temp("xlrd", ".xls")))
    else:
        tentativas.extend(
            [
                ("openpyxl/temp.xlsx", lambda: _via_temp("openpyxl", ".xlsx")),
                ("openpyxl/BytesIO", lambda: _via_buffer("openpyxl", "arquivo.xlsx")),
                ("calamine", lambda: _via_buffer("calamine", "arquivo.xlsx")),
                (
                    "openpyxl nativo",
                    lambda: _ler_excel_via_openpyxl_nativo(raw, planilha, header),
                ),
            ]
        )

    for rotulo, fn in tentativas:
        df = _tentar(rotulo, fn)
        if df is not None:
            return df, rotulo

    dica = ""
    joined = " | ".join(erros)
    if "engine ausente" in joined.lower():
        dica = " → pip install openpyxl" if ext != ".xls" else " → pip install python-calamine"
    raise RuntimeError(f"{joined}{dica}" if erros else f"Falha desconhecida ao ler {nome}.")


def _ler_csv_de_bytes(raw: bytes, nome: str) -> tuple[pd.DataFrame | None, str | None]:
    ultimo: Exception | None = None
    for enc in ("utf-8-sig", "cp1252", "latin1", "iso-8859-1", "utf-8"):
        for sep in (";", ","):
            try:
                df = pd.read_csv(
                    BytesIO(raw),
                    sep=sep,
                    encoding=enc,
                    dtype=str,
                    low_memory=False,
                    on_bad_lines="skip",
                )
            except Exception as e:
                ultimo = e
                continue
            if df.shape[1] <= 1:
                continue
            return df, f"csv {enc} sep={sep!r}"
    detalhe = f" ({type(ultimo).__name__}: {ultimo})" if ultimo else ""
    return None, f"{nome}: falha ao decodificar CSV{detalhe}"


def ler_arquivo_detalhado(
    caminho_arquivo: str,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    tamanho_maximo: int = _TAMANHO_MAXIMO_PADRAO,
) -> LeituraArquivo:
    if not caminho_arquivo or not os.path.exists(caminho_arquivo):
        nome = Path(caminho_arquivo).name if caminho_arquivo else "—"
        return LeituraArquivo(None, f"Arquivo não encontrado: {nome}", None)

    nome = Path(caminho_arquivo).name
    ext = Path(caminho_arquivo).suffix.lower()
    if ext not in EXTENSOES_VALIDAS:
        return LeituraArquivo(None, f"{nome}: extensão {ext or '—'} não é CSV/Excel.", None)

    try:
        if ext in (".xlsx", ".xls"):
            df, motor = _ler_excel_robusto(
                caminho_arquivo,
                sheet_name=sheet_name,
                header=0,
                tamanho_maximo=tamanho_maximo,
            )
            df = _padronizar_dataframe(df)
            if _cabecalho_fraco(list(df.columns)) or not _contem_colunas(df, colunas_esperadas):
                try:
                    alternativo, motor_alt = _ler_excel_robusto(
                        caminho_arquivo,
                        sheet_name=sheet_name,
                        header=1,
                        tamanho_maximo=tamanho_maximo,
                    )
                except Exception as e:
                    logger.debug("Header alternativo falhou em %s: %s", nome, e)
                else:
                    alternativo = _padronizar_dataframe(alternativo)
                    alt_melhor = (
                        _contem_colunas(alternativo, colunas_esperadas)
                        and not _contem_colunas(df, colunas_esperadas)
                    ) or (
                        _cabecalho_fraco(list(df.columns))
                        and not _cabecalho_fraco(list(alternativo.columns))
                    )
                    if alt_melhor:
                        df, motor = alternativo, f"{motor_alt} header=1"
        else:
            raw = _ler_bytes_estavel(caminho_arquivo, tamanho_maximo)
            df_csv, motor_csv = _ler_csv_de_bytes(raw, nome)
            if df_csv is None:
                return LeituraArquivo(None, motor_csv, None)
            df, motor = _padronizar_dataframe(df_csv), motor_csv
    except ArquivoBloqueadoError:
        raise
    except Exception as e:
        return LeituraArquivo(None, f"{nome}: {type(e).__name__} — {e}", None)

    if df.empty:
        return LeituraArquivo(None, f"{nome}: arquivo lido, porém sem linhas de dados.", motor)

    df = _alinhar_colunas_esperadas(df, colunas_esperadas)
    faltando = _faltam_colunas(df, colunas_esperadas)
    if faltando:
        return LeituraArquivo(
            None,
            f"{nome}: colunas ausentes → {', '.join(faltando)}",
            motor,
        )
    return LeituraArquivo(df, None, motor)


def ler_arquivo_totale(
    caminho_arquivo: str,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    notificar: bool = True,
) -> pd.DataFrame | None:
    try:
        leitura = ler_arquivo_detalhado(caminho_arquivo, colunas_esperadas, sheet_name)
    except ArquivoBloqueadoError:
        raise
    if st is None or not notificar:
        return leitura.df
    nome = Path(caminho_arquivo).name if caminho_arquivo else "—"
    if leitura.erro:
        st.session_state["robo_erro"] = leitura.erro
        _toast_dedup(f"Falha ao ler: {nome}", icon="⚠️")
        return None
    _toast_dedup(f"Arquivo carregado: {nome}", icon="✅")
    return leitura.df


def processar_candidatos(
    candidatos: Sequence[Candidato],
    modo: ModoLeitura = "ultimo_por_base",
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    tamanho_maximo: int = _TAMANHO_MAXIMO_PADRAO,
) -> ResultadoCiclo:
    selecionados = selecionar_arquivos(candidatos, modo)
    if not selecionados:
        return ResultadoCiclo(None, (), (), (), None, (), 0)

    frames: list[pd.DataFrame] = []
    bases: list[str] = []
    arquivos: list[str] = []
    erros: list[str] = []
    motores: list[str] = []
    bloqueios: list[str] = []

    for caminho, _, _ in selecionados:
        try:
            leitura = ler_arquivo_detalhado(
                caminho,
                colunas_esperadas=colunas_esperadas,
                sheet_name=sheet_name,
                tamanho_maximo=tamanho_maximo,
            )
        except ArquivoBloqueadoError as e:
            bloqueios.append(str(e))
            continue
        if leitura.erro or leitura.df is None:
            erros.append(leitura.erro or f"{Path(caminho).name}: leitura vazia")
            continue
        df_parcial = leitura.df
        base = detectar_base_arquivo(caminho)
        if base:
            df_parcial = _aplicar_base_no_dataframe(df_parcial, base)
            if base not in bases:
                bases.append(base)
        frames.append(df_parcial)
        arquivos.append(caminho)
        if leitura.motor:
            motores.append(f"{Path(caminho).name}: {leitura.motor}")

    if not frames:
        return ResultadoCiclo(
            None,
            tuple(bases),
            (),
            tuple(erros),
            bloqueios[0] if bloqueios else None,
            tuple(motores),
            0,
        )

    df = pd.concat(_unificar_nomes_colunas(frames), ignore_index=True)
    removidas = 0
    if modo == "todos" and len(frames) > 1:
        antes = len(df)
        df = df.drop_duplicates()
        removidas = antes - len(df)
    return ResultadoCiclo(
        df,
        tuple(bases),
        tuple(arquivos),
        tuple(erros),
        bloqueios[0] if bloqueios else None,
        tuple(motores),
        removidas,
    )


# ── UI ──────────────────────────────────────────────────────────────
def _exigir_streamlit() -> object:
    if st is None:
        raise RuntimeError("Streamlit não está instalado. A sidebar do robô só roda no app.")
    return st


def _toast_dedup(mensagem: str, icon: str = "✅") -> None:
    if st is None:
        return
    assinatura = f"{icon}:{mensagem}"
    if st.session_state.get("_robo_ultimo_toast") != assinatura:
        st.session_state["_robo_ultimo_toast"] = assinatura
        st.toast(mensagem, icon=icon)


def _estado_str(chave: str, padrao: str) -> str:
    if st is None:
        return padrao
    valor = st.session_state.get(chave, padrao)
    return str(valor) if valor else padrao


def _estado_bool(chave: str, padrao: bool) -> bool:
    if st is None:
        return padrao
    valor = st.session_state.get(chave, padrao)
    return bool(valor)


def _modo_atual() -> ModoLeitura:
    valor = _estado_str("robo_modo_leitura", "ultimo_por_base")
    if valor == "todos":
        return "todos"
    return "ultimo_por_base"


def _lock_ativo() -> bool:
    if st is None or not st.session_state.get("robo_processando", False):
        return False
    inicio = st.session_state.get("robo_processando_desde")
    if not isinstance(inicio, datetime):
        return False
    if (datetime.now() - inicio).total_seconds() < _LOCK_STALE_SEGUNDOS:
        return True
    st.session_state["robo_processando"] = False
    logger.warning("Lock do robô expirou depois de %ss.", _LOCK_STALE_SEGUNDOS)
    return False


def _obter_gsheets(gsheets_fn: FonteSheets) -> pd.DataFrame:
    if callable(gsheets_fn):
        return gsheets_fn()
    if isinstance(gsheets_fn, pd.DataFrame):
        return gsheets_fn
    return pd.DataFrame()


def _rerun_aplicacao() -> None:
    if st is None:
        return
    rerun = getattr(st, "rerun")
    try:
        rerun(scope="app")
    except TypeError:
        rerun()


def _executar_verificacao_robo(
    pasta_monitorada: str,
    etl_fn: EtlFn | None = None,
    gsheets_fn: FonteSheets = None,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    ciclos_estabilidade: int = 2,
    modo: ModoLeitura = "ultimo_por_base",
    recursivo: bool = False,
) -> None:
    if st is None or not _estado_bool("robo_ativo", True) or _lock_ativo():
        return

    candidatos = _listar_candidatos_com_stat(pasta_monitorada, recursivo=recursivo)
    selecionados = selecionar_arquivos(candidatos, modo)
    if not selecionados:
        return

    assinatura = tuple(selecionados)
    if st.session_state.get("robo_candidato_sig") == assinatura:
        stable = int(st.session_state.get("robo_candidato_stable", 0) or 0) + 1
    else:
        stable = 1
    st.session_state["robo_candidato_sig"] = assinatura
    st.session_state["robo_candidato_stable"] = stable
    if stable < max(ciclos_estabilidade, 1):
        return
    if st.session_state.get("robo_processado_sig") == assinatura:
        return

    st.session_state["robo_processando"] = True
    st.session_state["robo_processando_desde"] = datetime.now()
    try:
        if tuple(selecionar_arquivos(_listar_candidatos_com_stat(pasta_monitorada, recursivo=recursivo), modo)) != assinatura:
            st.session_state["robo_candidato_stable"] = 0
            _toast_dedup("Arquivos mudaram durante a espera. Aguardando...", icon="⚠️")
            return

        resultado = processar_candidatos(
            candidatos,
            modo=modo,
            colunas_esperadas=colunas_esperadas,
            sheet_name=sheet_name,
        )
        if resultado.bloqueio and resultado.df is None:
            st.session_state["robo_candidato_stable"] = 0
            st.session_state["_robo_aguardando_lock"] = resultado.bloqueio
            return
        if resultado.df is None:
            if resultado.erros:
                st.session_state["robo_erro"] = " | ".join(resultado.erros)
            return

        if tuple(selecionar_arquivos(_listar_candidatos_com_stat(pasta_monitorada, recursivo=recursivo), modo)) != assinatura:
            st.session_state["robo_candidato_stable"] = 0
            _toast_dedup("Arquivos mudaram durante a leitura. Aguardando...", icon="⚠️")
            return

        caminho_recente = selecionados[0][0]
        st.session_state["robo_ultimo_processado_path"] = caminho_recente
        st.session_state["robo_ultimo_processado_mtime"] = selecionados[0][1]
        st.session_state["robo_processado_sig"] = assinatura
        st.session_state["robo_arquivos_processados"] = {caminho: mtime for caminho, mtime, _ in selecionados}
        st.session_state["robo_bases_carregadas"] = list(resultado.bases)
        st.session_state["robo_base_detectada"] = detectar_base_arquivo(caminho_recente)
        st.session_state["robo_hora_sucesso"] = datetime.now()
        st.session_state["robo_motores"] = list(resultado.motores)
        st.session_state["robo_duplicatas_removidas"] = resultado.duplicatas_removidas
        st.session_state.pop("_robo_aguardando_lock", None)

        sufixo = f" · {', '.join(resultado.bases)}" if resultado.bases else ""
        st.session_state["origem_dados"] = f"Robô Local ({len(resultado.arquivos)} arquivo(s){sufixo})"
        if resultado.erros:
            st.session_state["robo_erro"] = "Parcial: " + " | ".join(resultado.erros)
        else:
            st.session_state.pop("robo_erro", None)

        df_gs = _obter_gsheets(gsheets_fn)
        if callable(etl_fn):
            transformado = etl_fn(resultado.df, df_gs)
            if isinstance(transformado, pd.DataFrame):
                st.session_state["df_memoria"] = transformado
        else:
            st.session_state["df_memoria"] = resultado.df

        if resultado.bases:
            _toast_dedup(f"Bases: {', '.join(resultado.bases)} — pipeline concluído!", icon="🚀")
        else:
            _toast_dedup("Pipeline concluído!", icon="🚀")
        _rerun_aplicacao()
    except Exception as e:
        logger.exception("Falha no ciclo do robô")
        st.session_state["robo_erro"] = f"{type(e).__name__}: {e}"
        _toast_dedup(f"Erro no pipeline: {e}", icon="❌")
    finally:
        st.session_state["robo_processando"] = False


if st is not None and hasattr(st, "fragment"):
    _executar_verificacao_robo = st.fragment(run_every="5s")(_executar_verificacao_robo)


def renderizar_robo_local(
    etl_fn: EtlFn | None = None,
    gsheets_fn: FonteSheets = None,
    pasta_padrao: str | None = None,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    ciclos_estabilidade: int = 2,
    mostrar_toggle: bool = True,
    mostrar_config: bool = True,
) -> None:
    _exigir_streamlit()
    assert st is not None

    if "robo_ativo" not in st.session_state:
        st.session_state["robo_ativo"] = True
    if "robo_modo_leitura" not in st.session_state:
        st.session_state["robo_modo_leitura"] = "ultimo_por_base"
    if "robo_recursivo" not in st.session_state:
        st.session_state["robo_recursivo"] = False
    if not st.session_state.get("robo_pasta_alvo"):
        st.session_state["robo_pasta_alvo"] = pasta_padrao or obter_pasta_robo_padrao()
    if pasta_padrao and not st.session_state.get("_robo_pasta_user_set"):
        if st.session_state.get("robo_pasta_alvo") in (None, "", obter_pasta_robo_padrao()):
            st.session_state["robo_pasta_alvo"] = pasta_padrao

    pasta_alvo = str(st.session_state["robo_pasta_alvo"])
    st.sidebar.markdown(
        """
        <div style='font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;
        letter-spacing:0.8px;margin:14px 0 6px;padding-left:4px;'>
            Robô de Sincronismo
        </div>
        """,
        unsafe_allow_html=True,
    )

    if mostrar_toggle:
        ativo = st.sidebar.toggle(
            "⚡ Auto-Sincronizar",
            value=_estado_bool("robo_ativo", True),
            key="robo_toggle_ui",
            help=(
                "Monitora a pasta a cada 5s enquanto esta sessão estiver aberta. "
                "SPO→Leste, GRS→Guarulhos, ABCDM→ABCDM."
            ),
        )
        st.session_state["robo_ativo"] = bool(ativo)
    else:
        ativo = _estado_bool("robo_ativo", True)

    if mostrar_config:
        with st.sidebar.expander("⚙️ Configurar Pasta", expanded=False):
            pasta_input = st.text_input("Caminho do Disco:", value=pasta_alvo, key="input_pasta_robo")
            if pasta_input != pasta_alvo:
                st.session_state["_robo_pasta_user_set"] = True
            st.session_state["robo_pasta_alvo"] = pasta_input
            pasta_alvo = str(pasta_input)
            modo_label = st.radio(
                "Quais arquivos entram",
                ("Último de cada base", "Todos da pasta"),
                index=0 if _modo_atual() == "ultimo_por_base" else 1,
                key="robo_modo_ui",
                help=(
                    "Último de cada base evita contar o mesmo snapshot várias vezes. "
                    "Use todos só se cada arquivo for um lote novo, sem reexportar o anterior."
                ),
            )
            st.session_state["robo_modo_leitura"] = (
                "ultimo_por_base" if modo_label == "Último de cada base" else "todos"
            )
            st.session_state["robo_recursivo"] = bool(
                st.checkbox("Incluir subpastas", value=_estado_bool("robo_recursivo", False), key="robo_recursivo_ui")
            )
            if os.path.isdir(pasta_alvo):
                st.success("✅ Pasta válida")
            else:
                st.error("❌ Pasta não existe")

    modo = _modo_atual()
    recursivo = _estado_bool("robo_recursivo", False)
    candidatos_ui = _listar_candidatos_com_stat(pasta_alvo, recursivo=recursivo)
    selecionados_ui = selecionar_arquivos(candidatos_ui, modo)
    por_base = mapear_arquivos_por_base(pasta_alvo, recursivo=recursivo)

    if candidatos_ui:
        hora = st.session_state.get("robo_hora_sucesso")
        hs = hora.strftime("%H:%M:%S") if isinstance(hora, datetime) else "—"
        sig_ok = st.session_state.get("robo_processado_sig") == tuple(selecionados_ui)
        stable = int(st.session_state.get("robo_candidato_stable", 0) or 0)
        aguardando_lock = st.session_state.get("_robo_aguardando_lock")
        if sig_ok:
            st.sidebar.success(f"✅ Sincronizado às {hs}\n{len(selecionados_ui)} arquivo(s) no pipeline")
        elif isinstance(aguardando_lock, str) and aguardando_lock:
            st.sidebar.info(f"⏳ {aguardando_lock}")
        else:
            st.sidebar.warning(
                f"📥 {len(candidatos_ui)} na pasta, {len(selecionados_ui)} na fila\n"
                f"Estável {stable}/{ciclos_estabilidade}"
            )

        extras = len(candidatos_ui) - len(selecionados_ui)
        if modo == "ultimo_por_base" and extras > 0:
            st.sidebar.caption(f"{extras} arquivo(s) antigo(s) fora do pipeline.")
        if modo == "todos":
            repetidos = {base: n for base, n in contar_arquivos_por_base(candidatos_ui).items() if n > 1}
            if repetidos:
                resumo = ", ".join(f"{base} ×{n}" for base, n in repetidos.items())
                st.sidebar.caption(f"Vários arquivos da mesma base ({resumo}). Snapshots vão duplicar volume.")

        st.sidebar.markdown(
            """
            <div style='font-size:10px;font-weight:700;color:#64748B;text-transform:uppercase;
            letter-spacing:0.6px;margin:10px 0 4px;padding-left:4px;'>
                Bases Monitoradas
            </div>
            """,
            unsafe_allow_html=True,
        )
        processados_bruto = st.session_state.get("robo_arquivos_processados")
        processados_map: dict[object, object] = processados_bruto if isinstance(processados_bruto, dict) else {}
        for marcador, base in MAPA_BASES_ARQUIVO.items():
            info = por_base.get(base)
            if info is None:
                st.sidebar.caption(f"⬜ {base} — aguardando arquivo com '{marcador}'")
                continue
            caminho_b, mtime_b, _ = info
            meta = obter_metadados_arquivo(caminho_b)
            ok = processados_map.get(caminho_b) == mtime_b
            icone = "✅" if ok else "📥"
            st.sidebar.caption(f"{icone} {base} — {meta['nome'][:32]} ({meta['tamanho']})")

        sem_base = [c for c, _, _ in candidatos_ui if detectar_base_arquivo(c) is None]
        if sem_base:
            st.sidebar.caption(f"⚠️ {len(sem_base)} arquivo(s) sem SPO, GRS ou ABCDM no nome.")
        removidas = st.session_state.get("robo_duplicatas_removidas")
        if isinstance(removidas, int) and removidas > 0:
            st.sidebar.caption(f"{removidas} linha(s) idêntica(s) removida(s) na junção.")
    else:
        estado = "🟢 Monitorando" if ativo else "⏸ Pausado"
        st.sidebar.info(f"{estado}: `{Path(pasta_alvo).name}`")

    erro = st.session_state.get("robo_erro")
    if isinstance(erro, str) and erro:
        st.sidebar.error(f"❌ {erro}")
        c_a, c_b = st.sidebar.columns(2)
        with c_a:
            if st.button("🧹 Limpar", key="limpar_erro_robo", use_container_width=True):
                st.session_state.pop("robo_erro", None)
                _rerun_aplicacao()
        with c_b:
            if st.button("🔄 Retentar", key="retry_erro_robo", use_container_width=True):
                st.session_state.pop("robo_erro", None)
                st.session_state["robo_candidato_sig"] = None
                st.session_state["robo_processado_sig"] = None
                st.session_state["robo_candidato_stable"] = 0
                _rerun_aplicacao()

    _executar_verificacao_robo(
        pasta_monitorada=pasta_alvo,
        etl_fn=etl_fn,
        gsheets_fn=gsheets_fn,
        colunas_esperadas=colunas_esperadas,
        sheet_name=sheet_name,
        ciclos_estabilidade=ciclos_estabilidade,
        modo=modo,
        recursivo=recursivo,
    )


def executar_ciclo_headless(
    pasta: str,
    destino_csv: str | None = None,
    modo: ModoLeitura = "ultimo_por_base",
    colunas_esperadas: list[str] | None = None,
) -> ResultadoCiclo:
    """Um ciclo sem Streamlit. Útil para Agendador de Tarefas, com a sessão do browser fechada."""
    resultado = processar_candidatos(
        _listar_candidatos_com_stat(pasta),
        modo=modo,
        colunas_esperadas=colunas_esperadas,
    )
    if resultado.df is not None and destino_csv:
        Path(destino_csv).parent.mkdir(parents=True, exist_ok=True)
        resultado.df.to_csv(destino_csv, index=False, sep=";", encoding="utf-8-sig")
    return resultado


renderizar_sidebar_robo = renderizar_robo_local
_obter_pasta_robo_padrao = obter_pasta_robo_padrao
_obter_metadados_arquivo = obter_metadados_arquivo

__all__ = [
    "EXTENSOES_VALIDAS",
    "MAPA_BASES_ARQUIVO",
    "ArquivoBloqueadoError",
    "LeituraArquivo",
    "ResultadoCiclo",
    "buscar_arquivo_mais_recente",
    "detectar_base_arquivo",
    "detectar_marcador_arquivo",
    "executar_ciclo_headless",
    "ler_arquivo_totale",
    "mapear_arquivos_por_base",
    "obter_metadados_arquivo",
    "obter_pasta_robo_padrao",
    "processar_candidatos",
    "renderizar_robo_local",
    "renderizar_sidebar_robo",
    "selecionar_arquivos",
]


if __name__ == "__main__":
    pasta_cli = sys.argv[1] if len(sys.argv) > 1 else obter_pasta_robo_padrao()
    destino = sys.argv[2] if len(sys.argv) > 2 else str(Path(pasta_cli) / "_robo_cache.csv")
    ciclo = executar_ciclo_headless(pasta_cli, destino_csv=destino)
    if ciclo.df is None:
        print(ciclo.bloqueio or " | ".join(ciclo.erros) or "Nenhum arquivo processado.")
        raise SystemExit(1)
    print(f"{len(ciclo.df)} linhas, bases={', '.join(ciclo.bases) or '—'} → {destino}")
