"""
pages/visao_geral.py
====================
Visão Geral — índice navegável de todos os dashboards do portal.

Versão: 1.0.0
Autor: TOTALE Tecnologia

O menu lateral cresceu para dezesseis itens e a pergunta "onde está o painel de
X?" passou a custar cliques. Esta página é o **mapa do portal**: lista as
seções de ``config.navegacao`` com uma descrição de uma linha por painel, um
buscador por título/descrição e o estado da carga de dados no topo.

Como o conteúdo vem de :mod:`config.navegacao`, criar/reorganizar um painel
atualiza automaticamente o menu, esta página e os testes de cobertura — nenhum
índice é mantido à mão.

Segue a hierarquia de leitura padrão (``components.layout_pagina.ORDEM_PADRAO``):
cabeçalho → contexto → sumário → filtros → detalhamento → rodapé.
"""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from components.componentes import aplicar_estilo, render_insight
from components.dashboards import abrir_dashboard, fechar_dashboard
from components.layout_pagina import barra_filtros, secao
from components.sidebar import render_page_sidebar_theme_selector
from config.navegacao import (
    DESCRICAO_GRUPOS,
    PaginaPortal,
    grupos_ordenados,
    paginas_do_grupo,
)
from services.dados_sessao import obter_base, resumir_carga, ultima_atualizacao

logger = logging.getLogger(__name__)

# ====================================================
# ⚙️ BLOCO 1: CONFIGURAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(
    page_title="Visão Geral | TOTALE",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

TITULO_PAGINA = "Visão Geral dos Dashboards"
SUBTITULO_PAGINA = (
    "Mapa do portal: o que cada painel responde, em qual área ele vive e como "
    "chegar nele em um clique."
)
COLUNAS_POR_LINHA = 3


# ====================================================
# 🧩 BLOCO 2: COMPONENTES DA PÁGINA
# ====================================================
def _resumo_da_carga() -> dict[str, Any]:
    """Estado da base compartilhada (para os chips de contexto do cabeçalho)."""
    base = obter_base(copiar=False)
    resumo = resumir_carga(
        base if base is not None else st.session_state.get("dados_prod"),
        atualizado_em=ultima_atualizacao(),
    )
    return {
        "resumo": resumo,
        "origem": str(st.session_state.get("origem_dados") or ""),
        "carregado": resumo.carregado,
    }


def _cartao(pagina: PaginaPortal) -> None:
    """Cartão de um painel: link nativo (título + ícone) e a descrição."""
    try:
        st.page_link(pagina.caminho, label=f"{pagina.icone} {pagina.titulo}")
    except Exception:  # pragma: no cover - página fora do shell de navegação
        logger.debug("st.page_link indisponível para %s.", pagina.arquivo, exc_info=True)
        st.markdown(f"**{pagina.icone} {pagina.titulo}**")
    if pagina.descricao:
        st.caption(pagina.descricao)


def render_grupo(grupo: str, paginas: list[PaginaPortal]) -> None:
    """Seção de uma área do portal com os painéis em grade."""
    icone = paginas[0].icone if paginas else "dashboard"
    with secao(
        grupo,
        icone=icone,
        subtitulo=DESCRICAO_GRUPOS.get(grupo, ""),
        badge=f"{len(paginas)} painel(is)",
    ):
        linhas = [
            paginas[posicao : posicao + COLUNAS_POR_LINHA]
            for posicao in range(0, len(paginas), COLUNAS_POR_LINHA)
        ]
        for linha in linhas:
            colunas = st.columns(COLUNAS_POR_LINHA, gap="small")
            for indice, pagina in enumerate(linha):
                with colunas[indice].container(border=True):
                    _cartao(pagina)


def render_busca(termo: str) -> list[PaginaPortal]:
    """Resultados da busca por título/descrição (vazio = índice completo)."""
    from config.navegacao import PAGINAS

    alvo = str(termo or "").strip().lower()
    if not alvo:
        return []
    return [
        pagina
        for pagina in PAGINAS
        if alvo in pagina.titulo.lower()
        or alvo in pagina.descricao.lower()
        or alvo in pagina.grupo.lower()
    ]


# ====================================================
# 🚀 BLOCO 3: FUNÇÃO PRINCIPAL DA PÁGINA
# ====================================================
def main() -> None:
    """Monta a página no padrão do portal (abre → filtra → lista → fecha)."""
    aplicar_estilo()
    render_page_sidebar_theme_selector()

    grupos = grupos_ordenados()
    total_paineis = sum(len(paginas_do_grupo(grupo)) for grupo in grupos)
    carga = _resumo_da_carga()

    # 1) Cabeçalho e contexto -------------------------------------------------
    abrir_dashboard(
        TITULO_PAGINA,
        subtitulo=SUBTITULO_PAGINA,
        badge="MAPA DO PORTAL",
        icone="🧭",
        secoes=[grupo for grupo in grupos],
        resumo=carga["resumo"],
        origem=carga["origem"],
        chips={
            "Painéis": total_paineis,
            "Seções": len(grupos),
        },
    )
    if not carga["carregado"]:
        render_insight(
            "Nenhuma base carregada nesta sessão — os painéis abrem, mas pedem a "
            "sincronização em **Atualização de Dados** antes de mostrar números.",
            tipo="alerta",
        )

    # 2) Filtros --------------------------------------------------------------
    with barra_filtros("visao_geral", titulo="Localizar painel", icone="search", colunas=1) as cols:
        termo = cols[0].text_input(
            "Buscar por nome, área ou assunto",
            key="visao_geral_busca",
            placeholder="Ex.: quebra, rota, meta, SLA…",
            label_visibility="collapsed",
        )

    # 3) Detalhamento ---------------------------------------------------------
    resultados = render_busca(termo)
    if resultados:
        with secao(
            f"Resultados para “{termo.strip()}”",
            icone="search",
            subtitulo=f"{len(resultados)} painel(is) encontrado(s).",
            ancora=False,
        ):
            colunas = st.columns(COLUNAS_POR_LINHA, gap="small")
            for indice, pagina in enumerate(resultados):
                with colunas[indice % COLUNAS_POR_LINHA].container(border=True):
                    _cartao(pagina)
                    st.caption(pagina.grupo)
    else:
        for grupo in grupos:
            render_grupo(grupo, paginas_do_grupo(grupo))

    # 4) Rodapé ---------------------------------------------------------------
    fechar_dashboard()


if __name__ == "__main__":
    main()
