"""
components/dashboards.py
========================
Esqueleto padrão dos dashboards do portal — camada de composição.

Versão: 1.0.0
Autor: TOTALE Tecnologia

:mod:`components.layout_pagina` entrega as **peças** da hierarquia de leitura
(cabeçalho, sumário, filtros, seções, ações, rodapé). Este módulo entrega a
**montagem**: as três chamadas que toda página faz, no mesmo formato, para que
os onze dashboards do portal abram e fechem do mesmo jeito.

Estrutura canônica de um dashboard::

    from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao

    df = exigir_base(pagina="Produção Mensal")
    abrir_dashboard(
        "Produção Mensal",
        subtitulo="Execução e produtividade por técnico",
        secoes=["KPIs", "Tendência", "Ranking", "Exportação"],
        resumo=resumir_carga(dados_prod),
    )
    with secao("KPIs", icone="monitoring"):
        render_kpi_row(specs)
    ...
    secao_exportacao(df, nome_arquivo="producao_mensal", chave="pontos")
    fechar_dashboard()

Componentes:

• ``abrir_dashboard``: hero do Design System + faixa de contexto (chips com
  atualização, registros e abas) + sumário com âncoras para as seções.
• ``chips_de_contexto``: monta os chips padrão a partir de um
  :class:`services.dados_sessao.ResumoCarga`.
• ``secao_exportacao``: bloco ``Exportação`` com CSV + Excel corporativos
  (delega a :func:`components.dashboard_kit.render_barra_exportacao`).
• ``fechar_dashboard``: rodapé corporativo único, com versão e ambiente lidos
  de :mod:`config.settings` (nenhuma página hardcoda a versão do portal).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from components.layout_pagina import (
    render_chips,
    render_rodape_pagina,
    render_sumario,
)

logger = logging.getLogger(__name__)

VERSAO_DASHBOARDS = "1.0.0"

#: Rótulo dos chips de contexto (ordem de exibição).
CHIPS_PADRAO: tuple[str, ...] = ("Atualizado em", "Registros", "Abas", "Origem")

__all__ = [
    "CHIPS_PADRAO",
    "VERSAO_DASHBOARDS",
    "abrir_dashboard",
    "chips_de_contexto",
    "fechar_dashboard",
    "secao_exportacao",
    "versao_do_portal",
]


# ====================================================
# 🏷️ BLOCO 1: CONTEXTO (CHIPS) E VERSÃO DO PORTAL
# ====================================================
def versao_do_portal() -> tuple[str, str]:
    """Versão e ambiente oficiais do portal, sem hardcode nas páginas.

    Fonte única: :data:`config.settings.VERSAO_PORTAL` /
    :data:`~config.settings.AMBIENTE_PORTAL`, que priorizam ``TOTALE_VERSAO`` e
    ``TOTALE_AMBIENTE`` em ``st.secrets``/variáveis de ambiente. O entrypoint lê
    os mesmos valores, então rodapé e ``Sobre`` nunca divergem.
    """
    try:
        from config.settings import (
            AMBIENTE_PORTAL_PADRAO,
            VERSAO_PORTAL_PADRAO,
            obter_ambiente_portal,
            obter_versao_portal,
        )

        return (
            obter_versao_portal() or VERSAO_PORTAL_PADRAO,
            obter_ambiente_portal() or AMBIENTE_PORTAL_PADRAO,
        )
    except Exception:  # pragma: no cover - config indisponível
        logger.debug("config.settings indisponível; usando fallback fixo.", exc_info=True)
        return ("3.7.0", "Produção")


def _texto_horario(valor: Any) -> str:
    """Carimbo curto em pt-BR para o chip de atualização."""
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%d/%m/%Y %H:%M")
    return str(valor)


def chips_de_contexto(
    *,
    resumo: Any = None,
    registros: int | None = None,
    atualizado_em: Any = None,
    origem: str = "",
    periodo: str = "",
    extras: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    """Chips padrão do topo de todo dashboard.

    Aceita o :class:`~services.dados_sessao.ResumoCarga` da sessão (o caso
    comum) ou valores avulsos, e sempre devolve um ``dict`` ordenado —
    ``render_chips`` ignora os campos vazios.
    """
    if atualizado_em is None and resumo is not None:
        atualizado_em = getattr(resumo, "atualizado_em", None)
    if registros is None and resumo is not None:
        registros = getattr(resumo, "registros", None)
    abas = getattr(resumo, "tabelas", 0) if resumo is not None else 0

    chips: dict[str, Any] = {}
    if periodo:
        chips["Período"] = periodo
    if atualizado_em:
        chips["Atualizado em"] = _texto_horario(atualizado_em)
    if registros:
        chips["Registros"] = int(registros)
    if abas:
        chips["Abas"] = int(abas)
    if origem:
        chips["Origem"] = origem
    if extras:
        pares = list(extras.items()) if isinstance(extras, Mapping) else list(extras)
        for rotulo, valor in pares:
            if valor not in (None, ""):
                chips[str(rotulo)] = valor
    return chips


# ====================================================
# 🧭 BLOCO 2: ABERTURA PADRÃO DO DASHBOARD
# ====================================================
def abrir_dashboard(
    titulo: str,
    *,
    subtitulo: str = "",
    badge: str = "",
    icone: str = "⚡",
    secoes: Sequence[str] | Sequence[tuple[str, str]] = (),
    chips: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
    resumo: Any = None,
    registros: int | None = None,
    atualizado_em: Any = None,
    origem: str = "",
    periodo: str = "",
    hero: Callable[..., Any] | None = None,
    hero_kwargs: Mapping[str, Any] | None = None,
    titulo_sumario: str = "Nesta página",
    mostrar_sumario: bool = True,
) -> dict[str, Any]:
    """Abre um dashboard no padrão do portal: hero → contexto → sumário.

    * ``hero`` permite manter o herói que a página já usa
      (``render_hero_totale_2`` com destaque numérico, por exemplo); sem ele, o
      cabeçalho padrão do Design System é usado.
    * ``secoes`` alimenta o sumário de âncoras — os nomes precisam ser os mesmos
      passados a :func:`components.layout_pagina.secao` para os links funcionarem.
    * devolve os chips efetivamente exibidos (útil em testes e diagnósticos).
    """
    if hero is not None:
        hero(**dict(hero_kwargs or {}))
    else:
        from components.layout_pagina import render_cabecalho_pagina

        render_cabecalho_pagina(
            titulo,
            subtitulo=subtitulo,
            badge=badge or "PAINEL TOTALE",
            icone=icone,
        )

    chips_contexto = chips_de_contexto(
        resumo=resumo,
        registros=registros,
        atualizado_em=atualizado_em,
        origem=origem,
        periodo=periodo,
        extras=chips,
    )
    if chips_contexto:
        render_chips(chips_contexto)

    if mostrar_sumario and secoes:
        rotulos = [s[0] if isinstance(s, (tuple, list)) else s for s in secoes]
        render_sumario(rotulos, titulo=titulo_sumario)

    return chips_contexto


# ====================================================
# 📤 BLOCO 3: EXPORTAÇÃO PADRÃO
# ====================================================
def secao_exportacao(
    df: pd.DataFrame | None,
    *,
    nome_arquivo: str,
    chave: str,
    titulo: str = "Exportação",
    icone: str = "download",
    subtitulo: str = "CSV em utf-8-sig e Excel com cabeçalho corporativo.",
    incluir_excel: bool = True,
    abas: bool = True,
    rotulo_secao: str = "Exportar dados",
) -> Any:
    """Bloco final de exportação, sempre no mesmo lugar e no mesmo formato.

    Com ``abas=True`` (padrão) o bloco entra em uma :func:`~components.layout_pagina.secao`
    ancorada — o sumário consegue apontar para ela.
    """
    from components.dashboard_kit import render_barra_exportacao
    from components.layout_pagina import secao as _secao

    def _corpo() -> None:
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            st.caption("Nada para exportar no recorte atual.")
            return
        render_barra_exportacao(
            df,
            nome_arquivo=nome_arquivo,
            chave=chave,
            incluir_excel=incluir_excel,
            rotulo_secao=rotulo_secao,
        )

    if not abas:
        _corpo()
        return None
    with _secao(titulo, icone=icone, subtitulo=subtitulo):
        _corpo()
    return None


# ====================================================
# 🏁 BLOCO 4: FECHAMENTO PADRÃO
# ====================================================
def fechar_dashboard(
    *,
    texto: str = "Portal TOTALE Analytics",
    versao: str = "",
    ambiente: str = "",
    horario: datetime | None = None,
) -> None:
    """Rodapé corporativo único (marca, ambiente, horário e versão do portal)."""
    versao_portal, ambiente_portal = versao_do_portal()
    render_rodape_pagina(
        texto=texto,
        versao=versao or versao_portal,
        ambiente=ambiente or ambiente_portal,
        horario=horario,
    )
