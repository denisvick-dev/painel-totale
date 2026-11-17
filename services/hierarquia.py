"""
services/hierarquia.py
======================
Lista de Ativos (Login → Técnico → Monitor → Base) como serviço único.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
Todo dashboard que cruza produção com gente precisa da mesma lista: ``consultivo``,
``volumetria``, ``rota_inicial``, ``quebra_geral`` e ``indicadores`` tinham cada
um a sua função ``buscar_hierarquia``/``carregar_hierarquia``, com TTLs
diferentes (300 s, 600 s), aliases diferentes para as colunas e um tratamento
de falha diferente. Na prática: o mesmo técnico aparecia com base diferente em
duas páginas, e quando o Sheets ficava indisponível metade do portal caía.

Este módulo entrega **uma** hierarquia para o portal inteiro:

* :func:`normalizar_hierarquia` aplica os aliases oficiais e devolve sempre as
  quatro colunas canônicas (``LOGIN``, ``TÉCNICO``, ``MONITOR``, ``BASE``) com
  o login normalizado por :func:`services.texto.normalizar_login` — a mesma
  identidade usada pelas bases de produção, então o *join* casa;
* :func:`carregar_hierarquia` tenta o caminho rápido (CSV de exportação do
  Sheets, com cache em disco e revalidação ``304``) e degrada para a
  ``GSheetsConnection``; sem rede devolve um DataFrame vazio **com as colunas
  certas** e registra o motivo, em vez de derrubar a página;
* :func:`hierarquia_da_sessao` guarda o resultado em ``st.session_state`` para
  todas as páginas do rerun compartilharem a mesma leitura.
* :func:`normalizar_lista_ativos` / :func:`lista_ativos_da_sessao` entregam a
  mesma lista **com a ``SITUAÇÃO``, o ``RE`` e a ``U.N.``** de cada técnico
  (colunas que a hierarquia de quatro colunas descarta) — é a fonte do painel
  de Absenteísmo e da grade mensal (técnico × dia);
* :func:`resumir_absenteismo` / :func:`agrupar_absenteismo` concentram a regra
  de negócio do absenteísmo derivado da ``lista_ativos`` (ver abaixo), para a
  página não reimplementar classificação de situação.

Regra do absenteísmo (retrato cadastral)
----------------------------------------
A ``lista_ativos`` é um **retrato atual** do quadro: não traz faltas, dias
ausentes nem histórico. O absenteísmo do portal é, portanto, derivado da
``Situação`` de cada registro, espelhando as listas oficiais de
``pages/gestao_ativos.py`` (``SITS_ATIVAS``/``SITS_SAIDA``):

* **quadro** — ``ATIVO``, ``FÉRIAS``, ``INOPERANTE``, ``ETN`` e ``AFASTADO``;
* **presentes** — ``ATIVO``;
* **ausentes** — ``FÉRIAS``, ``AFASTADO`` e ``INOPERANTE``;
* **fora do quadro** — ``DESLIGADO`` e ``INATIVO`` (não entram nas taxas);
* ``ETN`` conta no quadro, mas não é presente nem ausência (situação
  operacional distinta), por isso aparece separada nos agrupamentos.

Taxa de absenteísmo = ausentes ÷ quadro; disponibilidade = presentes ÷ quadro.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from services.texto import VALORES_AUSENTES, buscar_coluna, normalizar_login

logger = logging.getLogger(__name__)

VERSAO_HIERARQUIA = "1.0.0"

#: Chave da hierarquia compartilhada em ``st.session_state``.
CHAVE_SESSAO_HIERARQUIA = "totale_hierarquia"

#: Chave da lista de ativos completa (com ``SITUAÇÃO``) em ``st.session_state``.
CHAVE_SESSAO_LISTA_ATIVOS = "totale_lista_ativos"

#: Colunas canônicas devolvidas por :func:`normalizar_hierarquia`.
COLUNAS_CANONICAS: tuple[str, ...] = ("LOGIN", "TÉCNICO", "MONITOR", "BASE")

#: Colunas devolvidas por :func:`normalizar_lista_ativos` (hierarquia + cadastro).
COLUNAS_LISTA_ATIVOS: tuple[str, ...] = (*COLUNAS_CANONICAS, "SITUAÇÃO", "RE", "U.N.")

#: Aliases das colunas de cadastro que acompanham a hierarquia (RE e unidade).
ALIASES_LISTA_EXTRAS: dict[str, tuple[str, ...]] = {
    "RE": ("RE", "MATRÍCULA", "MATRICULA"),
    "U.N.": (
        "U.N.",
        "UN",
        "UNIDADE",
        "UNIDADE DE NEGÓCIO",
        "UNIDADE DE NEGOCIO",
        "UNIDADE_NEGOCIO",
    ),
}

#: Aliases da situação cadastral na ``lista_ativos``.
ALIASES_SITUACAO: tuple[str, ...] = (
    "SITUAÇÃO",
    "SITUACAO",
    "STATUS",
    "SITUAÇÃO ATUAL",
    "SITUACAO ATUAL",
)

#: Rótulo usado quando a ``lista_ativos`` não informa a situação do técnico.
SITUACAO_NAO_INFORMADA = "NÃO INFORMADO"

#: Situações de quem está no quadro ativo (espelha ``SITS_ATIVAS`` da Gestão de Ativos).
SITUACOES_QUADRO: tuple[str, ...] = ("ATIVO", "FÉRIAS", "INOPERANTE", "ETN", "AFASTADO")

#: Situação de quem está disponível para operar hoje.
SITUACOES_PRESENTES: tuple[str, ...] = ("ATIVO",)

#: Situações contadas como ausência no retrato cadastral.
SITUACOES_AUSENCIAS: tuple[str, ...] = ("FÉRIAS", "AFASTADO", "INOPERANTE")

#: Situações de saída: fora do quadro, fora das taxas (espelha ``SITS_SAIDA``).
SITUACOES_SAIDA: tuple[str, ...] = ("DESLIGADO", "INATIVO")

#: Aliases oficiais de cada campo nas planilhas do portal.
ALIASES: dict[str, tuple[str, ...]] = {
    "LOGIN": (
        "LOGIN",
        "LOGIN DO TÉCNICO",
        "LOGIN DO TECNICO",
        "LOGIN_TECNICO",
        "LOGIN NETSALES",
        "MATRÍCULA",
        "MATRICULA",
        "ID",
        "USUARIO",
        "USUÁRIO",
        "RE",
        "COD_TECNICO",
        "COD TECNICO",
        "CD TEC",
    ),
    "TÉCNICO": (
        "TÉCNICO",
        "TECNICO",
        "NOME",
        "NOME DO TÉCNICO",
        "NOME TECNICO",
        "NOME COMPLETO",
        "COLABORADOR",
    ),
    "MONITOR": (
        "MONITOR",
        "GESTOR",
        "SUPERVISOR",
        "COORDENADOR",
        "LIDER",
        "LÍDER",
        "NOME MONITOR",
        "NOME SUPERVISOR",
        "NOME GESTOR",
    ),
    "BASE": ("BASE", "REGIÃO", "REGIAO", "BASE / REGIÃO", "FILIAL", "LOCALIDADE"),
}

_RE_ESPACOS = re.compile(r"\s+")
_RE_DECIMAL_INTEIRO = re.compile(r"\d+\.0")


def _limpar_nome(valor: Any) -> str:
    """Nome para exibição: caixa/espaços normalizados **sem** perder o acento."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return _RE_ESPACOS.sub(" ", str(valor).strip())


def _identificador(valor: Any) -> str:
    """Código de cadastro (RE): texto sem o ``.0`` que o Sheets acrescenta."""
    texto = _limpar_nome(valor)
    return texto[:-2] if _RE_DECIMAL_INTEIRO.fullmatch(texto) else texto


__all__ = [
    "ALIASES",
    "ALIASES_LISTA_EXTRAS",
    "ALIASES_SITUACAO",
    "CHAVE_SESSAO_HIERARQUIA",
    "CHAVE_SESSAO_LISTA_ATIVOS",
    "COLUNAS_CANONICAS",
    "COLUNAS_LISTA_ATIVOS",
    "SITUACOES_AUSENCIAS",
    "SITUACOES_PRESENTES",
    "SITUACOES_QUADRO",
    "SITUACOES_SAIDA",
    "SITUACAO_NAO_INFORMADA",
    "VERSAO_HIERARQUIA",
    "agrupar_absenteismo",
    "carregar_hierarquia",
    "carregar_lista_ativos",
    "classificar_situacao",
    "hierarquia_da_sessao",
    "hierarquia_vazia",
    "lista_ativos_da_sessao",
    "lista_ativos_vazia",
    "normalizar_hierarquia",
    "normalizar_lista_ativos",
    "normalizar_situacao",
    "resumir_absenteismo",
]


def hierarquia_vazia() -> pd.DataFrame:
    """DataFrame sem linhas, mas com as colunas canônicas (consumidor não quebra)."""
    return pd.DataFrame({coluna: pd.Series(dtype="object") for coluna in COLUNAS_CANONICAS})


def normalizar_hierarquia(bruto: pd.DataFrame | None) -> pd.DataFrame:
    """Aplica os aliases oficiais e devolve a hierarquia no formato canônico.

    * colunas renomeadas para ``LOGIN``/``TÉCNICO``/``MONITOR``/``BASE``;
    * ``LOGIN`` normalizado (``'123.0'`` → ``'123'``) e sem linhas vazias;
    * nomes em ``Title Case`` sem espaços duplicados, preservando acentos
      (``normalizar_texto`` remove acento — serve para comparar, não exibir);
    * duplicidades resolvidas pela **última** ocorrência (a planilha costuma
      trazer a movimentação mais recente no fim).
    """
    if bruto is None or not isinstance(bruto, pd.DataFrame) or bruto.empty:
        return hierarquia_vazia()

    base = bruto.copy()
    base.columns = base.columns.astype(str).str.strip()

    renomear: dict[str, str] = {}
    for destino, alias in ((campo, nomes) for campo, nomes in ALIASES.items()):
        coluna = buscar_coluna(base, alias)
        if coluna is not None and coluna not in renomear:
            renomear[coluna] = destino
    if "LOGIN" not in renomear.values():
        logger.debug("Hierarquia sem coluna de login; colunas vistas: %s", list(base.columns))
        return hierarquia_vazia()

    resultado = base.rename(columns=renomear)
    resultado = resultado[[c for c in COLUNAS_CANONICAS if c in resultado.columns]].copy()
    for coluna in COLUNAS_CANONICAS:
        if coluna not in resultado.columns:
            resultado[coluna] = ""

    resultado["LOGIN"] = resultado["LOGIN"].map(normalizar_login)
    resultado = resultado.loc[~resultado["LOGIN"].isin(VALORES_AUSENTES)]
    for coluna in ("TÉCNICO", "MONITOR", "BASE"):
        resultado[coluna] = resultado[coluna].map(_limpar_nome).str.title()
    return resultado.drop_duplicates(subset=["LOGIN"], keep="last").reset_index(drop=True)


def normalizar_situacao(valor: Any) -> str:
    """Situação cadastral comparável: caixa alta, sem espaços duplicados.

    Valores vazios/ausentes viram :data:`SITUACAO_NAO_INFORMADA` — nunca
    ``""``/``"NAN"``, para o agrupamento não criar uma categoria fantasma.
    """
    texto = _RE_ESPACOS.sub(" ", str(valor or "").strip()).upper()
    return SITUACAO_NAO_INFORMADA if texto in VALORES_AUSENTES else texto


def classificar_situacao(situacao: Any) -> str:
    """Categoria de absenteísmo de uma situação da ``lista_ativos``.

    Devolve ``"Presente"``, ``"Ausente"``, ``"Fora do quadro"``,
    ``"No quadro (outra situação)"`` (ex.: ``ETN`` e situações novas ainda não
    mapeadas) ou ``"Não informado"``.
    """
    texto = normalizar_situacao(situacao)
    if texto == SITUACAO_NAO_INFORMADA:
        return "Não informado"
    if texto in SITUACOES_PRESENTES:
        return "Presente"
    if texto in SITUACOES_AUSENCIAS:
        return "Ausente"
    if texto in SITUACOES_SAIDA:
        return "Fora do quadro"
    return "No quadro (outra situação)"


def lista_ativos_vazia() -> pd.DataFrame:
    """DataFrame sem linhas, mas com as colunas da lista completa (com situação)."""
    return pd.DataFrame({coluna: pd.Series(dtype="object") for coluna in COLUNAS_LISTA_ATIVOS})


def normalizar_lista_ativos(bruto: pd.DataFrame | None) -> pd.DataFrame:
    """``lista_ativos`` completa: hierarquia canônica + cadastro (situação/RE/U.N.).

    Reaproveita :func:`normalizar_hierarquia` para as quatro colunas de
    identidade (mesmos aliases, mesmo login, mesma deduplicação pela última
    ocorrência) e anexa situação, RE e U.N. da **mesma** linha vencedora — por
    isso a deduplicação é refeita aqui sobre login + cadastro antes do recorte.
    Sem coluna de login devolve :func:`lista_ativos_vazia`; sem coluna de
    situação, todos ficam como :data:`SITUACAO_NAO_INFORMADA`; sem RE/U.N.,
    as colunas existem vazias (o consumidor não quebra).
    """
    if bruto is None or not isinstance(bruto, pd.DataFrame) or bruto.empty:
        return lista_ativos_vazia()

    base = bruto.copy()
    base.columns = base.columns.astype(str).str.strip()
    coluna_situacao = buscar_coluna(base, ALIASES_SITUACAO)

    hierarquia = normalizar_hierarquia(base)
    if hierarquia.empty:
        return lista_ativos_vazia()

    # Cadastro por login, resolvido pela última ocorrência (mesma regra da
    # hierarquia): alinhar pelo índice pós-dedup perderia a linha vencedora.
    coluna_login = buscar_coluna(base, ALIASES["LOGIN"])
    if coluna_login is None:  # normalizar_hierarquia já garantiu que existe
        hierarquia["SITUAÇÃO"] = SITUACAO_NAO_INFORMADA
        for coluna in ("RE", "U.N."):
            hierarquia[coluna] = ""
        return hierarquia[list(COLUNAS_LISTA_ATIVOS)]

    mapa_cadastro = pd.DataFrame({"LOGIN": base[coluna_login].map(normalizar_login)})
    mapa_cadastro["SITUAÇÃO"] = (
        base[coluna_situacao].map(normalizar_situacao)
        if coluna_situacao is not None
        else SITUACAO_NAO_INFORMADA
    )
    for destino, aliases in ALIASES_LISTA_EXTRAS.items():
        coluna = buscar_coluna(base, aliases)
        if coluna is None:
            mapa_cadastro[destino] = ""
            continue
        normalizador = _identificador if destino == "RE" else _limpar_nome
        mapa_cadastro[destino] = base[coluna].map(normalizador)

    mapa_cadastro = (
        mapa_cadastro.loc[~mapa_cadastro["LOGIN"].isin(VALORES_AUSENTES)]
        .drop_duplicates(subset=["LOGIN"], keep="last")
    )
    resultado = hierarquia.merge(mapa_cadastro, on="LOGIN", how="left")
    resultado["SITUAÇÃO"] = resultado["SITUAÇÃO"].fillna(SITUACAO_NAO_INFORMADA)
    for coluna in ("RE", "U.N."):
        resultado[coluna] = resultado[coluna].fillna("").astype(str)
    return resultado[list(COLUNAS_LISTA_ATIVOS)].reset_index(drop=True)


def _situacoes_de(df: pd.DataFrame | None) -> pd.Series:
    """Série de situações normalizadas (vazia quando a base não tem a coluna)."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or "SITUAÇÃO" not in df.columns:
        return pd.Series(dtype="object")
    return df["SITUAÇÃO"].map(normalizar_situacao)


def resumir_absenteismo(df: pd.DataFrame | None) -> dict[str, Any]:
    """Totais do retrato de absenteísmo de uma lista de ativos normalizada.

    Espera o formato de :func:`normalizar_lista_ativos`. As taxas são frações
    (``0.0``–``1.0``) sobre o **quadro**; fora do quadro e não informados ficam
    fora do denominador, mas são devolvidos para auditoria do recorte.
    """
    situacoes = _situacoes_de(df)
    total = int(len(situacoes))
    quadro = int(situacoes.isin(SITUACOES_QUADRO).sum())
    presentes = int(situacoes.isin(SITUACOES_PRESENTES).sum())
    ausentes = int(situacoes.isin(SITUACOES_AUSENCIAS).sum())
    fora_do_quadro = int(situacoes.isin(SITUACOES_SAIDA).sum())
    return {
        "total": total,
        "quadro": quadro,
        "presentes": presentes,
        "ausentes": ausentes,
        "ferias": int((situacoes == "FÉRIAS").sum()),
        "afastados": int((situacoes == "AFASTADO").sum()),
        "inoperantes": int((situacoes == "INOPERANTE").sum()),
        "outras_no_quadro": quadro - presentes - ausentes,
        "fora_do_quadro": fora_do_quadro,
        "nao_informados": total - quadro - fora_do_quadro,
        "taxa_absenteismo": (ausentes / quadro) if quadro else 0.0,
        "taxa_disponibilidade": (presentes / quadro) if quadro else 0.0,
    }


def agrupar_absenteismo(df: pd.DataFrame | None, coluna: str) -> pd.DataFrame:
    """Absenteísmo por ``BASE``/``MONITOR``/``SITUAÇÃO`` (uma linha por grupo).

    Devolve contagens por categoria e as taxas em percentual (``0``–``100``),
    ordenado pela taxa de absenteísmo (maior primeiro). Grupos vazios viram
    ``"Não informado"`` para não sumirem do ranking.
    """
    colunas = [
        coluna,
        "Quadro",
        "Presentes",
        "Ausentes",
        "Outras no quadro",
        "Fora do quadro",
        "Taxa de Absenteísmo (%)",
        "Disponibilidade (%)",
    ]
    if (
        df is None
        or not isinstance(df, pd.DataFrame)
        or df.empty
        or coluna not in df.columns
        or "SITUAÇÃO" not in df.columns
    ):
        return pd.DataFrame(columns=colunas)

    dados = df.copy()
    dados[coluna] = dados[coluna].map(_limpar_nome).replace("", "Não informado")
    dados["_situacao"] = dados["SITUAÇÃO"].map(normalizar_situacao)
    dados["_quadro"] = dados["_situacao"].isin(SITUACOES_QUADRO).astype(int)
    dados["_presentes"] = dados["_situacao"].isin(SITUACOES_PRESENTES).astype(int)
    dados["_ausentes"] = dados["_situacao"].isin(SITUACOES_AUSENCIAS).astype(int)
    dados["_fora"] = dados["_situacao"].isin(SITUACOES_SAIDA).astype(int)

    agrupado = (
        dados.groupby(coluna, as_index=False)
        .agg(
            Quadro=("_quadro", "sum"),
            Presentes=("_presentes", "sum"),
            Ausentes=("_ausentes", "sum"),
            **{"Fora do quadro": ("_fora", "sum")},
        )
        .assign(**{"Outras no quadro": lambda d: d["Quadro"] - d["Presentes"] - d["Ausentes"]})
    )
    denominador = agrupado["Quadro"].replace(0, pd.NA)
    agrupado["Taxa de Absenteísmo (%)"] = (agrupado["Ausentes"] / denominador * 100).fillna(0.0)
    agrupado["Disponibilidade (%)"] = (agrupado["Presentes"] / denominador * 100).fillna(0.0)
    return (
        agrupado[colunas]
        .sort_values(
            ["Taxa de Absenteísmo (%)", "Ausentes", "Quadro"],
            ascending=[False, False, False],
        )
        .reset_index(drop=True)
    )


def _ler_via_conexao_streamlit(sheet_id: str, aba: str | None) -> pd.DataFrame:
    """Caminho de contingência: ``st.connection('gsheets')`` (precisa de secrets)."""
    try:
        import streamlit as st
        from streamlit_gsheets import GSheetsConnection

        from config.settings import url_gsheets_edit

        conn = st.connection("gsheets", type=GSheetsConnection)
        kwargs: dict[str, Any] = {"spreadsheet": url_gsheets_edit(sheet_id), "ttl": 0}
        if aba:
            kwargs["worksheet"] = aba
        bruto = conn.read(**kwargs)
        if isinstance(bruto, pd.DataFrame) and not bruto.empty:
            bruto.columns = bruto.columns.astype(str).str.strip()
            return bruto
    except Exception:
        logger.debug("Hierarquia via GSheetsConnection indisponível.", exc_info=True)
    return pd.DataFrame()


def _carregar_bruto_ativos(
    sheet_id: str | None,
    aba: str | None,
    *,
    ttl: int,
    usar_cache: bool,
) -> pd.DataFrame:
    """Baixa a ``lista_ativos`` bruta (CSV do Sheets → ``GSheetsConnection``).

    Compartilhado por :func:`carregar_hierarquia` e
    :func:`carregar_lista_ativos`: a fonte e a degradação são as mesmas, só
    muda a normalização aplicada depois.
    """
    from config.settings import obter_sheet_id_ativos
    from services.google_drive_client import carregar_planilha_gsheets_csv

    sid = str(sheet_id or obter_sheet_id_ativos() or "").strip()
    if not sid:
        logger.warning("Sheet de ativos não configurado; lista de ativos vazia.")
        return pd.DataFrame()
    try:
        bruto = carregar_planilha_gsheets_csv(
            sid, aba, usar_cache=usar_cache, ttl=ttl, usar_conexao_streamlit=False
        )
    except Exception:
        logger.warning("Falha ao baixar a lista de ativos (%s).", sid, exc_info=True)
        bruto = pd.DataFrame()
    if bruto is None or bruto.empty:
        bruto = _ler_via_conexao_streamlit(sid, aba)
    return bruto if isinstance(bruto, pd.DataFrame) else pd.DataFrame()


def carregar_hierarquia(
    sheet_id: str | None = None,
    aba: str | None = None,
    *,
    ttl: int = 300,
    usar_cache: bool = True,
) -> pd.DataFrame:
    """Lista de Ativos normalizada, com degradação graciosa quando o Sheets falha.

    Ordem das tentativas: CSV de exportação (``export?format=csv`` → ``gviz``),
    com cache em disco e revalidação condicional quando ``usar_cache=True``;
    depois ``GSheetsConnection``. Sem nenhuma fonte disponível devolve
    :func:`hierarquia_vazia` — o dashboard continua funcionando, apenas sem o
    enriquecimento cadastral.
    """
    hierarquia = normalizar_hierarquia(
        _carregar_bruto_ativos(sheet_id, aba, ttl=ttl, usar_cache=usar_cache)
    )
    if hierarquia.empty:
        logger.warning("Hierarquia de ativos vazia após normalização.")
    return hierarquia


def carregar_lista_ativos(
    sheet_id: str | None = None,
    aba: str | None = None,
    *,
    ttl: int = 300,
    usar_cache: bool = True,
) -> pd.DataFrame:
    """``lista_ativos`` completa (hierarquia + ``SITUAÇÃO``), mesma fonte da hierarquia.

    Sem fonte disponível devolve :func:`lista_ativos_vazia` — quem consome
    (painel de Absenteísmo) mostra o estado vazio em vez de quebrar.
    """
    from services.qualidade_ativos import diagnosticar_ativos

    bruto = _carregar_bruto_ativos(sheet_id, aba, ttl=ttl, usar_cache=usar_cache)
    lista = normalizar_lista_ativos(bruto)
    lista.attrs["qualidade_origem"] = diagnosticar_ativos(bruto)
    if lista.empty:
        logger.warning("Lista de ativos vazia após normalização.")
    return lista


def hierarquia_da_sessao(
    sheet_id: str | None = None,
    aba: str | None = None,
    *,
    ttl: int = 300,
    forcar: bool = False,
) -> pd.DataFrame:
    """Hierarquia compartilhada entre as páginas via ``st.session_state``.

    Uma leitura por sessão (o TTL interno do serviço cuida da revalidação):
    navegar entre dashboards não repete o download da lista de ativos.
    """
    import streamlit as st

    atual = st.session_state.get(CHAVE_SESSAO_HIERARQUIA)
    if forcar or not isinstance(atual, pd.DataFrame) or atual.empty:
        atual = carregar_hierarquia(sheet_id, aba, ttl=ttl)
        st.session_state[CHAVE_SESSAO_HIERARQUIA] = atual
    return atual


def lista_ativos_da_sessao(
    sheet_id: str | None = None,
    aba: str | None = None,
    *,
    ttl: int = 300,
    forcar: bool = False,
) -> pd.DataFrame:
    """Lista de ativos completa compartilhada via ``st.session_state``.

    Chave própria (:data:`CHAVE_SESSAO_LISTA_ATIVOS`): a hierarquia de quatro
    colunas continua servindo os demais painéis sem carregar a situação.
    """
    import streamlit as st

    atual = st.session_state.get(CHAVE_SESSAO_LISTA_ATIVOS)
    if forcar or not isinstance(atual, pd.DataFrame) or atual.empty:
        atual = carregar_lista_ativos(sheet_id, aba, ttl=ttl)
        st.session_state[CHAVE_SESSAO_LISTA_ATIVOS] = atual
    return atual
