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

#: Colunas canônicas devolvidas por :func:`normalizar_hierarquia`.
COLUNAS_CANONICAS: tuple[str, ...] = ("LOGIN", "TÉCNICO", "MONITOR", "BASE")

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


__all__ = [
    "ALIASES",
    "CHAVE_SESSAO_HIERARQUIA",
    "COLUNAS_CANONICAS",
    "VERSAO_HIERARQUIA",
    "carregar_hierarquia",
    "hierarquia_da_sessao",
    "hierarquia_vazia",
    "normalizar_hierarquia",
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
    from config.settings import obter_sheet_id_ativos
    from services.google_drive_client import carregar_planilha_gsheets_csv

    sid = str(sheet_id or obter_sheet_id_ativos() or "").strip()
    if not sid:
        logger.warning("Sheet de ativos não configurado; hierarquia vazia.")
        return hierarquia_vazia()
    try:
        bruto = carregar_planilha_gsheets_csv(
            sid, aba, usar_cache=usar_cache, ttl=ttl, usar_conexao_streamlit=False
        )
    except Exception:
        logger.warning("Falha ao baixar a lista de ativos (%s).", sid, exc_info=True)
        bruto = pd.DataFrame()
    if bruto is None or bruto.empty:
        bruto = _ler_via_conexao_streamlit(sid, aba)
    hierarquia = normalizar_hierarquia(bruto)
    if hierarquia.empty:
        logger.warning("Hierarquia de ativos vazia após normalização (sheet %s).", sid)
    return hierarquia


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
