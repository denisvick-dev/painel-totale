"""components/frescor_fontes.py
==============================
Faixa global de frescor: a idade do dado e o SLO, em qualquer dashboard.

Versão: 1.0.0
Autor: TOTALE Tecnologia

A regra (idade, estado e SLO) vive em :mod:`services.frescor`; aqui só há a
apresentação. A faixa é intencionalmente discreta — uma linha de 11 px entre os
chips de contexto e o sumário — para não competir com o conteúdo:

    🟢 Dados atualizados · Produção há 4 min · Consultivo há 1 h · Ativos há 2 h

O detalhe completo (SLO combinado, linhas e erro) vai no ``title``/``aria-label``
da linha, sem popover e sem custo de mais um widget. Quando a sessão não tem
``status_fontes``, a faixa usa a carga manual (``ultima_atualizacao``) como
fonte "Sessão"; sem nenhuma das duas, nada é renderizado.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from html import escape
from typing import Any

import streamlit as st

from components.componentes import _safe_render_html
from services.frescor import (
    ROTULOS_ESTADO,
    LeituraFrescor,
    estado_geral,
    leitura_de_sessao,
    resumir_frescor,
    resumo_curto,
)

VERSAO_FAIXA_FRESCOR = "1.0.0"

#: Cor da borda/dot, fundo e texto por estado.
_PALETA: dict[str, tuple[str, str, str]] = {
    "ok": ("#047857", "#ECFDF5", "#065F46"),
    "alerta": ("#D97706", "#FFFBEB", "#92400E"),
    "critico": ("#DC2626", "#FEF2F2", "#991B1B"),
    "desconhecido": ("#64748B", "#F8FAFC", "#334155"),
}

__all__ = [
    "VERSAO_FAIXA_FRESCOR",
    "html_faixa_frescor",
    "render_faixa_frescor",
]


def html_faixa_frescor(leituras: Sequence[LeituraFrescor]) -> str:
    """HTML da faixa (string vazia quando não há leitura)."""
    if not leituras:
        return ""
    geral = estado_geral(leituras)
    cor, fundo, texto = _PALETA.get(geral, _PALETA["desconhecido"])
    rotulo = ROTULOS_ESTADO.get(geral, ROTULOS_ESTADO["desconhecido"])
    resumo = resumo_curto(leituras)
    detalhe = " | ".join(leitura.detalhe for leitura in leituras)
    return (
        f'<div role="status" aria-live="polite" '
        f'aria-label="{escape(f"{rotulo}. {detalhe}")}" '
        f'title="{escape(detalhe)}" '
        'style="display:flex;align-items:center;flex-wrap:wrap;gap:7px;'
        f"background:{fundo};border:1px solid {cor}33;border-left:3px solid {cor};"
        "border-radius:9px;padding:6px 11px;margin:2px 0 10px;"
        'font-size:11px;line-height:1.45;color:#334155;">'
        f'<span aria-hidden="true" style="width:7px;height:7px;border-radius:50%;'
        f'background:{cor};flex:0 0 auto;"></span>'
        f'<strong style="color:{texto};font-size:11px;font-weight:800;">{escape(rotulo)}</strong>'
        f'<span style="color:#64748B;">·</span>'
        f'<span style="color:#334155;">{escape(resumo)}</span>'
        "</div>"
    )


def render_faixa_frescor(
    container: Any = None,
    *,
    agora: datetime | None = None,
    leituras: Sequence[LeituraFrescor] | None = None,
) -> None:
    """Renderiza a faixa no topo do dashboard, se houver estado para mostrar.

    ``leituras`` existe para testes e para telas que já calcularam o frescor;
    sem ele, lê ``status_fontes`` e, como fallback, ``ultima_atualizacao``.
    """
    if leituras is None:
        leituras = resumir_frescor(st.session_state.get("status_fontes"), agora=agora)
    if not leituras:
        leituras = leitura_de_sessao(
            st.session_state.get("ultima_atualizacao"),
            agora=agora,
        )
    markup = html_faixa_frescor(leituras)
    if markup:
        _safe_render_html(markup, container)
