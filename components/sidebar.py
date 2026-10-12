"""
sidebar.py
==========
Sidebar independente do Design System TOTALE para aplicações Streamlit.

Inclui os três temas (claro, azul e laranja), persistência de tema entre páginas,
seletor compatível com os controles BaseWeb/React Aria do Streamlit, marca,
seções, divisores, cartões de usuário e de status.

Uso básico:
    import streamlit as st
    from sidebar import aplicar_sidebar_corp, render_sidebar_brand
    from sidebar import render_sidebar_theme_selector, render_sidebar_section

    aplicar_sidebar_corp()  # preserva o tema salvo na sessão
    render_sidebar_brand(nome="TOTALE", subtitulo="Portal de Operações")
    render_sidebar_theme_selector()
    render_sidebar_section("NAVEGAÇÃO")

Dependência: streamlit.
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import streamlit as st

logger = logging.getLogger(__name__)

TemaSidebarType = Literal["claro", "azul", "laranja", "padrao"]
_FUSO_BR = ZoneInfo("America/Sao_Paulo")
_TEMAS_VALIDOS: tuple[str, ...] = ("claro", "azul", "laranja")

# Tokens centralizados do sidebar. Os valores são deliberadamente opacos onde
# possível, para manter previsível a leitura dos controles e do menu.
_TEMAS: dict[str, dict[str, str]] = {
    "claro": {
        "fundo": "linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 52%, #F1F5F9 100%)",
        "fundo_base": "#F1F5F9",
        "borda": "#D8E1EC",
        "texto_primario": "#102A43",
        "texto_secundario": "#40536B",
        "texto_muted": "#52657D",
        "texto_acento": "#9A3412",
        "icone": "#52657D",
        "secao": "#52657D",
        "card_fundo": "#FFFFFF",
        "card_borda": "#D8E1EC",
        "nav_ativo_fundo": "#012869",
        "nav_ativo_texto": "#FFFFFF",
        "nav_ativo_borda": "#0B2440",
        "nav_ativo_acento": "#F37C04",
        "nav_passivo_texto": "#334155",
        "nav_hover_texto": "#0B2440",
        "nav_hover_fundo": "#E7EEF7",
        "botao_fundo": "#F8FAFC",
        "botao_texto": "#102A43",
        "botao_hover_fundo": "#0B2440",
        "botao_hover_texto": "#FFFFFF",
        "input_fundo": "#FFFFFF",
        "input_texto": "#102A43",
        "input_borda": "#718096",
        "input_focus": "#C2410C",
        "input_focus_ring": "rgba(194, 65, 12, 0.24)",
        "accent_topo": "linear-gradient(90deg, #012869 0%, #0A48AA 65%, #F37C04 100%)",
        "scrollbar": "#CBD5E1",
    },
    "azul": {
        "fundo": "linear-gradient(180deg, #061426 0%, #0B1E35 47%, #112B4A 100%)",
        "fundo_base": "#112B4A",
        "borda": "rgba(255, 255, 255, 0.13)",
        "texto_primario": "#F8FAFC",
        "texto_secundario": "#D4DFEB",
        "texto_muted": "#A9BDD3",
        "texto_acento": "#FDBA74",
        "icone": "#AFC5DC",
        "secao": "#9FB2C9",
        "card_fundo": "rgba(255, 255, 255, 0.055)",
        "card_borda": "rgba(255, 255, 255, 0.14)",
        "nav_ativo_fundo": "linear-gradient(90deg, rgba(10,72,170,0.50) 0%, rgba(10,72,170,0.16) 100%)",
        "nav_ativo_texto": "#FFFFFF",
        "nav_ativo_borda": "rgba(253, 186, 116, 0.24)",
        "nav_ativo_acento": "#FDBA74",
        "nav_passivo_texto": "#D7E2EF",
        "nav_hover_texto": "#FFFFFF",
        "nav_hover_fundo": "rgba(255, 255, 255, 0.085)",
        "botao_fundo": "rgba(255, 255, 255, 0.085)",
        "botao_texto": "#FFFFFF",
        "botao_hover_fundo": "#C2410C",
        "botao_hover_texto": "#FFFFFF",
        "input_fundo": "rgba(255, 255, 255, 0.06)",
        "input_texto": "#FFFFFF",
        "input_borda": "rgba(255, 255, 255, 0.48)",
        "input_focus": "#FDBA74",
        "input_focus_ring": "rgba(253, 186, 116, 0.28)",
        "accent_topo": "linear-gradient(90deg, #F37C04 0%, #FDBA74 100%)",
        "scrollbar": "rgba(255, 255, 255, 0.24)",
    },
    "laranja": {
        "fundo": "linear-gradient(180deg, #1B0A04 0%, #2E1207 40%, #451B0A 75%, #5A260F 100%)",
        "fundo_base": "#5A260F",
        "borda": "rgba(255, 196, 150, 0.26)",
        "texto_primario": "#FFF9F3",
        "texto_secundario": "#FFE6CC",
        "texto_muted": "#F1C79F",
        "texto_acento": "#FFD09A",
        "icone": "#FFD1A3",
        "secao": "#FFD3A6",
        "card_fundo": "rgba(0, 0, 0, 0.22)",
        "card_borda": "rgba(255, 255, 255, 0.16)",
        "nav_ativo_fundo": "linear-gradient(90deg, rgba(243,124,4,0.36) 0%, rgba(243,124,4,0.10) 100%)",
        "nav_ativo_texto": "#FFFFFF",
        "nav_ativo_borda": "rgba(255, 205, 157, 0.30)",
        "nav_ativo_acento": "#FFB067",
        "nav_passivo_texto": "#FFE4C7",
        "nav_hover_texto": "#FFFFFF",
        "nav_hover_fundo": "rgba(255, 255, 255, 0.09)",
        "botao_fundo": "rgba(255, 255, 255, 0.10)",
        "botao_texto": "#FFFFFF",
        "botao_hover_fundo": "#011838",
        "botao_hover_texto": "#FFFFFF",
        "input_fundo": "rgba(0, 0, 0, 0.22)",
        "input_texto": "#FFFFFF",
        "input_borda": "rgba(255, 255, 255, 0.52)",
        "input_focus": "#FFD09A",
        "input_focus_ring": "rgba(255, 208, 154, 0.28)",
        "accent_topo": "linear-gradient(90deg, #F37C04 0%, #FFD09A 60%, #FFF9F3 100%)",
        "scrollbar": "rgba(255, 255, 255, 0.24)",
    },
}

_CSS_SIDEBAR = r"""
<style>
[data-testid="stSidebar"] {
    --totale-sb-primary: @@TEXTO_PRIMARIO@@;
    --totale-sb-secondary: @@TEXTO_SECUNDARIO@@;
    --totale-sb-muted: @@TEXTO_MUTED@@;
    --totale-sb-accent-text: @@TEXTO_ACENTO@@;
    --totale-sb-icon: @@ICONE@@;
    --totale-sb-section: @@SECAO@@;
    --totale-sb-card: @@CARD_FUNDO@@;
    --totale-sb-card-border: @@CARD_BORDA@@;
    --totale-sb-nav-active-bg: @@NAV_ATIVO_FUNDO@@;
    --totale-sb-nav-active-text: @@NAV_ATIVO_TEXTO@@;
    --totale-sb-nav-active-border: @@NAV_ATIVO_BORDA@@;
    --totale-sb-nav-active-accent: @@NAV_ATIVO_ACENTO@@;
    --totale-sb-nav: @@NAV_PASSIVO_TEXTO@@;
    --totale-sb-nav-hover: @@NAV_HOVER_TEXTO@@;
    --totale-sb-nav-hover-bg: @@NAV_HOVER_FUNDO@@;
    --totale-sb-button-bg: @@BOTAO_FUNDO@@;
    --totale-sb-button-text: @@BOTAO_TEXTO@@;
    --totale-sb-button-hover-bg: @@BOTAO_HOVER_FUNDO@@;
    --totale-sb-button-hover-text: @@BOTAO_HOVER_TEXTO@@;
    --totale-sb-input-bg: @@INPUT_FUNDO@@;
    --totale-sb-input-text: @@INPUT_TEXTO@@;
    --totale-sb-input-border: @@INPUT_BORDA@@;
    --totale-sb-input-focus: @@INPUT_FOCUS@@;
    --totale-sb-input-focus-ring: @@INPUT_FOCUS_RING@@;
    position: relative;
    isolation: isolate;
    background: @@FUNDO@@ !important;
    border-right: 1px solid @@BORDA@@ !important;
    color: var(--totale-sb-secondary) !important;
    font-family: Inter, "Segoe UI", system-ui, -apple-system, sans-serif !important;
    box-shadow: 8px 0 28px rgba(15, 23, 42, .08);
}
[data-testid="stSidebar"]::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0;
    height: 3px; z-index: 100; background: @@ACCENT_TOPO@@;
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    padding-top: 16px;
    padding-bottom: 18px;
}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: var(--totale-sb-muted) !important;
    font-size: 10px !important;
    font-weight: 800 !important;
    letter-spacing: .09em !important;
    text-transform: uppercase !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] .stMarkdown { color: var(--totale-sb-secondary) !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 { color: var(--totale-sb-primary) !important; }
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {
    color: var(--totale-sb-muted) !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {
    background: var(--totale-sb-nav-hover-bg) !important;
    color: var(--totale-sb-primary) !important;
}

/* Navegação Streamlit: links passivos e item ativo, com acento estável de 3px. */
[data-testid="stSidebarNav"] { padding: 4px 2px 12px; }
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {
    color: var(--totale-sb-section) !important; font-size: 10px !important;
    font-weight: 800 !important; letter-spacing: .11em !important;
    text-transform: uppercase !important; padding: 10px 12px 6px 14px !important;
}
[data-testid="stSidebarNav"] a {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    min-height: 40px !important;
    padding: 9px 11px !important;
    margin: 3px 0 !important;
    box-sizing: border-box !important;
    color: var(--totale-sb-nav) !important;
    font-size: 12.5px !important;
    line-height: 1.35 !important;
    font-weight: 560 !important;
    border-radius: 10px !important;
    border: 1px solid transparent !important;
    border-left: 3px solid transparent !important;
    text-decoration: none !important;
    transition: background .18s ease, color .18s ease, transform .18s ease, box-shadow .18s ease !important;
}
[data-testid="stSidebarNav"] a:not([aria-current="page"]):hover {
    background: var(--totale-sb-nav-hover-bg) !important;
    color: var(--totale-sb-nav-hover) !important;
    transform: translateX(2px);
}
[data-testid="stSidebarNav"] a:not([aria-current="page"]) span {
    color: var(--totale-sb-nav) !important;
    -webkit-text-fill-color: var(--totale-sb-nav) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: var(--totale-sb-nav-active-bg) !important;
    color: var(--totale-sb-nav-active-text) !important; font-weight: 700 !important;
    border: 1px solid var(--totale-sb-nav-active-border) !important;
    border-left: 3px solid var(--totale-sb-nav-active-accent) !important;
    box-shadow: 0 5px 14px rgba(0, 0, 0, .16), inset 0 1px 0 rgba(255, 255, 255, .08) !important;
    transform: translateX(1px);
}
[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebarNav"] a[aria-current="page"] * {
    color: var(--totale-sb-nav-active-text) !important;
    -webkit-text-fill-color: var(--totale-sb-nav-active-text) !important;
}

/* Compatibilidade BaseWeb e React Aria nas versões recentes do Streamlit. */
[data-testid="stSidebar"] div[data-baseweb="select"] > div,
[data-testid="stSidebar"] input:not([type="checkbox"]):not([type="radio"]),
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"] {
    background: var(--totale-sb-input-bg) !important;
    border: 1px solid var(--totale-sb-input-border) !important;
    color: var(--totale-sb-input-text) !important; border-radius: 10px !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, .06) !important;
    transition: border-color .15s ease, box-shadow .15s ease, background .15s ease !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] span,
[data-testid="stSidebar"] [data-testid="stSelectbox"] input[role="combobox"] {
    color: var(--totale-sb-input-text) !important;
    -webkit-text-fill-color: var(--totale-sb-input-text) !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] svg,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"] svg {
    fill: var(--totale-sb-icon) !important; color: var(--totale-sb-icon) !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within,
[data-testid="stSidebar"] input:not([type="checkbox"]):not([type="radio"]):focus,
[data-testid="stSidebar"] textarea:focus,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"]:focus-within {
    border-color: var(--totale-sb-input-focus) !important;
    box-shadow: 0 0 0 2px var(--totale-sb-input-focus-ring) !important;
    outline: none !important;
}
[data-testid="stSidebar"] label[data-baseweb="checkbox"] span,
[data-testid="stSidebar"] label[data-baseweb="radio"] span { color: var(--totale-sb-secondary) !important; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"] [data-baseweb="checkbox--checkmark"],
[data-testid="stSidebar"] label[data-baseweb="radio"] [data-baseweb="radio--circle"] {
    border-color: var(--totale-sb-icon) !important;
}

[data-testid="stSidebar"] [data-testid="stButton"] > button,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] > button {
    background: var(--totale-sb-button-bg) !important;
    color: var(--totale-sb-button-text) !important;
    border: 1px solid var(--totale-sb-card-border) !important;
    border-radius: 10px !important; min-height: 2.35rem !important;
    font-weight: 650 !important; box-shadow: 0 1px 2px rgba(15, 23, 42, .05) !important;
    transition: background .15s ease, color .15s ease, border-color .15s ease, transform .15s ease !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] > button:hover {
    background: var(--totale-sb-button-hover-bg) !important;
    color: var(--totale-sb-button-hover-text) !important;
    border-color: var(--totale-sb-button-hover-bg) !important;
    transform: translateY(-1px);
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:disabled {
    opacity: .58 !important; cursor: not-allowed !important; box-shadow: none !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
    background: var(--totale-sb-card) !important;
    border: 1px solid var(--totale-sb-card-border) !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary { color: var(--totale-sb-primary) !important; }
[data-testid="stSidebar"] hr { border-color: var(--totale-sb-card-border) !important; }
[data-testid="stSidebar"] *::-webkit-scrollbar { width: 8px; height: 8px; }
[data-testid="stSidebar"] *::-webkit-scrollbar-track { background: transparent; }
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb {
    background: @@SCROLLBAR@@; border-radius: 99px;
}
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb:hover { background: var(--totale-sb-nav-active-accent); }
[data-testid="stSidebar"]:focus-within *:focus-visible {
    outline: 2px solid var(--totale-sb-input-focus) !important; outline-offset: 2px;
}
.sidebar-brand {
    position: relative; isolation: isolate; overflow: hidden;
    padding: 15px 13px 13px; margin: 5px 0 18px;
    border: 1px solid var(--totale-sb-card-border);
    border-radius: 15px; background: var(--totale-sb-card);
    box-shadow: 0 8px 22px rgba(15, 23, 42, .08);
}
.sidebar-brand::before {
    content: ""; position: absolute; inset: 0 0 auto; height: 3px;
    background: @@ACCENT_TOPO@@;
}
.sidebar-brand::after {
    content: ""; position: absolute; z-index: 0; width: 116px; height: 116px;
    right: -55px; top: -62px; border-radius: 50%;
    background: radial-gradient(circle, rgba(243, 124, 4, .15), transparent 68%);
}
.sidebar-brand > * { position: relative; z-index: 1; }
.sidebar-brand-row { display: flex; align-items: center; gap: 11px; min-width: 0; }
.sidebar-brand-copy { min-width: 0; }
.sidebar-brand-mark, .sidebar-brand-logo {
    display: inline-flex; align-items: center; justify-content: center;
    flex: 0 0 40px; width: 40px; height: 40px;
    border-radius: 12px; object-fit: cover;
}
.sidebar-brand-mark {
    color: #FFFFFF; font-size: 19px; line-height: 1;
    background: linear-gradient(145deg, #012869 5%, #0A48AA 72%, #C2410C 145%);
    border: 1px solid rgba(255, 255, 255, .22);
    box-shadow: 0 5px 12px rgba(1, 40, 105, .22);
}
.sidebar-brand-logo { border: 1px solid var(--totale-sb-card-border); }
.sidebar-brand-name {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: 17px; font-weight: 820; letter-spacing: -.035em;
    margin: 0; line-height: 1.12; color: var(--totale-sb-primary);
}
.sidebar-brand-sub {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    color: var(--totale-sb-secondary); font-size: 10.5px;
    line-height: 1.4; margin-top: 4px;
}
.sidebar-section-header {
    margin: 19px 0 7px; padding: 3px 0 7px 12px; position: relative;
}
.sidebar-section-header::before {
    content: ""; position: absolute; left: 0; top: 4px; width: 3px; height: 13px;
    border-radius: 99px; background: var(--totale-sb-nav-active-accent);
    box-shadow: 0 0 10px color-mix(in srgb, var(--totale-sb-nav-active-accent) 32%, transparent);
}
.sidebar-profile-card, .sidebar-status-card {
    position: relative; overflow: hidden;
    border: 1px solid var(--totale-sb-card-border);
    border-radius: 14px; background: var(--totale-sb-card);
    box-shadow: 0 6px 18px rgba(15, 23, 42, .07);
    transition: transform .18s ease, box-shadow .18s ease;
}
.sidebar-profile-card:hover, .sidebar-status-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 9px 22px rgba(15, 23, 42, .11);
}
.sidebar-footer {
    margin-top: 18px; padding: 13px 12px 10px;
    border: 1px solid var(--totale-sb-card-border);
    border-radius: 14px; background: var(--totale-sb-card);
    box-shadow: 0 5px 16px rgba(15, 23, 42, .05);
}
@media (prefers-reduced-motion: reduce) {
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] *::before,
    [data-testid="stSidebar"] *::after { transition: none !important; animation: none !important; }
}
</style>
"""

_CSS_PLACEHOLDERS: dict[str, str] = {
    "FUNDO": "fundo",
    "BORDA": "borda",
    "TEXTO_PRIMARIO": "texto_primario",
    "TEXTO_SECUNDARIO": "texto_secundario",
    "TEXTO_MUTED": "texto_muted",
    "TEXTO_ACENTO": "texto_acento",
    "ICONE": "icone",
    "SECAO": "secao",
    "CARD_FUNDO": "card_fundo",
    "CARD_BORDA": "card_borda",
    "NAV_ATIVO_FUNDO": "nav_ativo_fundo",
    "NAV_ATIVO_TEXTO": "nav_ativo_texto",
    "NAV_ATIVO_BORDA": "nav_ativo_borda",
    "NAV_ATIVO_ACENTO": "nav_ativo_acento",
    "NAV_PASSIVO_TEXTO": "nav_passivo_texto",
    "NAV_HOVER_TEXTO": "nav_hover_texto",
    "NAV_HOVER_FUNDO": "nav_hover_fundo",
    "BOTAO_FUNDO": "botao_fundo",
    "BOTAO_TEXTO": "botao_texto",
    "BOTAO_HOVER_FUNDO": "botao_hover_fundo",
    "BOTAO_HOVER_TEXTO": "botao_hover_texto",
    "INPUT_FUNDO": "input_fundo",
    "INPUT_TEXTO": "input_texto",
    "INPUT_BORDA": "input_borda",
    "INPUT_FOCUS": "input_focus",
    "INPUT_FOCUS_RING": "input_focus_ring",
    "ACCENT_TOPO": "accent_topo",
    "SCROLLBAR": "scrollbar",
}


def _escapar(valor: Any) -> str:
    """Escapa valores antes de inseri-los em HTML."""
    if valor is None:
        return ""
    return html_lib.escape(str(valor), quote=True)


def _agora_br() -> datetime:
    return datetime.now(_FUSO_BR)


def normalizar_tema_sidebar(tema: Any) -> TemaSidebarType:
    """Normaliza o nome do tema. O alias legado ``padrao`` equivale a ``claro``."""
    valor = str(getattr(tema, "value", tema) or "").strip().lower()
    if valor == "padrao":
        valor = "claro"
    return valor if valor in _TEMAS_VALIDOS else "claro"  # type: ignore[return-value]


def _obter_tema_sidebar(tema_param: Any = None) -> TemaSidebarType:
    if tema_param is not None:
        return normalizar_tema_sidebar(tema_param)
    # O estado canônico é escrito pelo callback do selectbox, evitando que a
    # chamada de estilo no começo de uma página reverta a escolha do usuário.
    for chave in (
        "_totale_sidebar_theme",
        "_totale_sidebar_theme_select",
        "seletor_cor_sidebar",
        "tema_sidebar",
    ):
        valor = st.session_state.get(chave)
        if valor:
            return normalizar_tema_sidebar(valor)
    return "claro"


def definir_tema_sidebar(tema: TemaSidebarType | str) -> None:
    """Persiste o tema ativo e tenta sincronizar a chave padrão do seletor."""
    tema_norm = normalizar_tema_sidebar(tema)
    st.session_state["_totale_sidebar_theme"] = tema_norm
    chave_widget = "_totale_sidebar_theme_select"
    if st.session_state.get(chave_widget) != tema_norm:
        try:
            st.session_state[chave_widget] = tema_norm
        except Exception:
            # O Streamlit proíbe alterar uma chave de widget depois que o widget
            # foi instanciado na execução atual; a próxima execução sincroniza.
            logger.debug("Seletor de tema sincronizado na próxima execução.")


def _render_html(markup: str, container: Any = None) -> None:
    """Renderiza HTML usando st.html quando disponível e markdown como fallback."""
    if not markup:
        return
    destino = container if container is not None else st
    limpo = markup.strip()
    html_fn = getattr(destino, "html", None)
    if callable(html_fn):
        try:
            html_fn(limpo)
            return
        except Exception:
            logger.debug(
                "st.html falhou; usando markdown com HTML permitido.", exc_info=True
            )
    try:
        destino.markdown(limpo, unsafe_allow_html=True)
    except Exception:
        logger.exception("Não foi possível renderizar o componente HTML da sidebar.")


def _css_tema(tema: TemaSidebarType | str) -> str:
    tokens = _TEMAS[normalizar_tema_sidebar(tema)]
    css = _CSS_SIDEBAR
    for placeholder, chave in _CSS_PLACEHOLDERS.items():
        css = css.replace(f"@@{placeholder}@@", tokens[chave])
    return css


def aplicar_estilo(tema_sidebar: TemaSidebarType | str | None = None) -> None:
    """Aplica apenas o CSS do sidebar, mantendo o tema da sessão se omitido."""
    tema = _obter_tema_sidebar(tema_sidebar)
    definir_tema_sidebar(tema)
    _render_html(_css_tema(tema), st)
    st.session_state["_totale_sidebar_css_tema"] = tema


def aplicar_estilo_corp(tema_sidebar: TemaSidebarType | str | None = None) -> None:
    """Alias compatível com o Design System corporativo."""
    aplicar_estilo(tema_sidebar=tema_sidebar)


def aplicar_sidebar_corp(tema: TemaSidebarType | str | None = None) -> None:
    """Aplica um tema explícito ou reaplica o tema atual da sessão."""
    aplicar_estilo(tema_sidebar=tema)


def _callback_tema_sidebar(chave: str) -> None:
    escolha = st.session_state.get(chave)
    if escolha:
        st.session_state["_totale_sidebar_theme"] = normalizar_tema_sidebar(escolha)


def render_sidebar_theme_selector(
    label: str = "TEMA DA SIDEBAR",
    help: str = "",
    container: Any = None,
    key: str = "_totale_sidebar_theme_select",
    mostrar_icone: bool = True,
    aplicar_automaticamente: bool = True,
) -> TemaSidebarType:
    """Renderiza o seletor de tema e persiste a escolha na sessão Streamlit."""
    alvo = container if container is not None else st.sidebar
    opcoes: list[TemaSidebarType] = ["claro", "azul", "laranja"]
    nomes = {
        "claro": "☀️ Claro Corporativo" if mostrar_icone else "Claro Corporativo",
        "azul": "🔷 Deep Executive Navy" if mostrar_icone else "Deep Executive Navy",
        "laranja": "🔶 Terracotta & Amber" if mostrar_icone else "Terracotta & Amber",
    }
    tema_atual = _obter_tema_sidebar()
    kwargs: dict[str, Any] = {
        "format_func": lambda valor: nomes.get(valor, str(valor).title()),
        "key": key,
        "on_change": _callback_tema_sidebar,
        "args": (key,),
    }
    if help:
        kwargs["help"] = help
    if key not in st.session_state:
        kwargs["index"] = opcoes.index(tema_atual)
    elif normalizar_tema_sidebar(st.session_state.get(key)) not in opcoes:
        # Corrige valores antigos/inválidos antes da criação do widget.
        st.session_state[key] = tema_atual

    escolha = alvo.selectbox(label, options=opcoes, **kwargs)
    tema_escolhido = normalizar_tema_sidebar(escolha)
    definir_tema_sidebar(tema_escolhido)
    if aplicar_automaticamente:
        aplicar_estilo(tema_sidebar=tema_escolhido)
    return tema_escolhido


def render_page_sidebar_theme_selector() -> TemaSidebarType:
    """Renderiza o seletor somente quando a página não usa o shell raiz."""
    if st.session_state.get("_totale_root_navigation_shell", False):
        return _obter_tema_sidebar()
    return render_sidebar_theme_selector()


def carregar_layout_corporativo(
    tema_sidebar: TemaSidebarType | str | None = None,
    renderizar_sidebar: bool = False,
    nome: str = "TOTALE",
    subtitulo: str = "Portal de Produção & Performance",
    versao: str = "",
) -> None:
    """Atalho para aplicar o tema e, opcionalmente, desenhar marca e seletor."""
    tema_ativo = _obter_tema_sidebar(tema_sidebar)
    aplicar_estilo(tema_sidebar=tema_ativo)
    if renderizar_sidebar:
        render_sidebar_brand(nome=nome, subtitulo=subtitulo, versao=versao)
        render_sidebar_theme_selector()


def _url_valida(url: str | None) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(str(url))
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except (TypeError, ValueError):
        return False


def render_sidebar_brand(
    nome: str = "TOTALE",
    subtitulo: str = "Analytics & Intelligence",
    versao: str = "",
    logo_url: str | None = None,
    icone: str = "⚡",
    titulo: str = "",
    logo: str | None = None,
    tema: TemaSidebarType | str | None = None,
    **kwargs: Any,
) -> None:
    """Mostra marca, subtítulo, ícone/logotipo e badge de versão no sidebar."""
    nome_final = str(titulo or nome or "").strip()
    subtitulo_final = str(kwargs.get("segmento", subtitulo) or "").strip()
    versao_final = str(versao or "").strip()
    logo_final = logo or logo_url
    tema_ativo = _obter_tema_sidebar(tema)
    if not nome_final and not subtitulo_final and not logo_final:
        return

    logo_valida = _url_valida(str(logo_final)) if logo_final else False

    if tema_ativo == "azul":
        cor_nome, fundo_badge, cor_badge, borda_badge = (
            "#FFFFFF",
            "rgba(255,255,255,.12)",
            "#FDBA74",
            "rgba(255,255,255,.20)",
        )
        estilo_nome = "background:linear-gradient(100deg,#FFFFFF 20%,#FDBA74 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;"
    elif tema_ativo == "laranja":
        cor_nome, fundo_badge, cor_badge, borda_badge = (
            "#FFFFFF",
            "rgba(255,255,255,.16)",
            "#FFFFFF",
            "rgba(255,255,255,.28)",
        )
        estilo_nome = ""
    else:
        cor_nome, fundo_badge, cor_badge, borda_badge = (
            "#011E52",
            "#E8EEF8",
            "#011E52",
            "#D6E0F0",
        )
        estilo_nome = "background:linear-gradient(100deg,#012869 10%,#0A48AA 62%,#F37C04 140%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;"

    badge = ""
    if versao_final:
        badge_txt = (
            versao_final if versao_final.lower().startswith("v") else f"v{versao_final}"
        )
        badge = (
            f'<span style="display:inline-flex;margin-top:8px;padding:4px 9px;border-radius:999px;'
            f"background:{fundo_badge};color:{cor_badge};border:1px solid {borda_badge};"
            f'font-size:10px;font-weight:750;letter-spacing:.04em;">{_escapar(badge_txt)}</span>'
        )

    if logo_valida:
        marca_visual = (
            f'<img class="sidebar-brand-logo" src="{_escapar(logo_final)}" '
            f'alt="{_escapar(nome_final or "Logotipo")}" loading="lazy">'
        )
    else:
        marca_visual = f'<span class="sidebar-brand-mark" aria-hidden="true">{_escapar(icone or "⚡")}</span>'
    nome_html = (
        f'<h2 class="sidebar-brand-name" style="color:{cor_nome};{estilo_nome}">'
        f"{_escapar(nome_final)}</h2>"
        if nome_final
        else ""
    )
    subtitulo_html = (
        f'<div class="sidebar-brand-sub">{_escapar(subtitulo_final)}</div>'
        if subtitulo_final
        else ""
    )
    markup = (
        '<div class="sidebar-brand"><div class="sidebar-brand-row">'
        f'{marca_visual}<div class="sidebar-brand-copy">{nome_html}{subtitulo_html}</div>'
        f"</div>{badge}</div>"
    )
    _render_html(markup, st.sidebar)


def render_sidebar_section(
    titulo: str,
    icone: str = "",
    collapsible: bool = False,
    tema: TemaSidebarType | str | None = None,
) -> None:
    """Renderiza o título de uma seção da sidebar."""
    if not str(titulo or "").strip():
        return
    if collapsible:
        with st.sidebar.expander(f"{icone} {titulo}".strip(), expanded=True):
            pass
        return

    tema_ativo = _obter_tema_sidebar(tema)
    tokens = _TEMAS[tema_ativo]
    icone_html = (
        f'<span aria-hidden="true" style="font-size:14px;color:{tokens["texto_acento"]};">'
        f"{_escapar(icone)}</span>"
        if icone
        else ""
    )
    markup = (
        '<div class="sidebar-section-header">'
        '<div style="display:flex;align-items:center;gap:7px;min-width:0;'
        f'font-size:11px;font-weight:750;color:{tokens["secao"]};'
        f'text-transform:uppercase;letter-spacing:.08em;">{icone_html}'
        f"<span>{_escapar(titulo)}</span></div></div>"
    )
    _render_html(markup, st.sidebar)


def _cor_css_segura(cor: str, padrao: str) -> str:
    valor = str(cor or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", valor):
        return valor
    if re.fullmatch(r"rgba?\([\d\s.,%+-]+\)", valor):
        return valor
    nomes = {"white", "black", "transparent", "currentColor"}
    if valor in nomes:
        return valor
    return padrao


def render_sidebar_divider(
    estilo: Literal["linha", "gradiente", "pontilhado", "espaco"] = "gradiente",
    espacamento: Literal["pequeno", "medio", "grande"] = "medio",
    cor: str = "",
    label: str = "",
    tema: TemaSidebarType | str | None = None,
) -> None:
    """Renderiza divisor, linha rotulada ou espaço vertical."""
    margens = {"pequeno": "6px 0", "medio": "14px 0", "grande": "24px 0"}
    margem = margens.get(espacamento, margens["medio"])
    tema_ativo = _obter_tema_sidebar(tema)
    tokens = _TEMAS[tema_ativo]
    if tema_ativo == "claro":
        cor_default = "#CBD5E1"
        gradiente = "border:none;height:1px;background:linear-gradient(90deg,transparent 0%,#01286955 40%,#F37C04 70%,transparent 100%);"
        label_color = "#011E52"
    elif tema_ativo == "azul":
        cor_default = "rgba(255,255,255,.16)"
        gradiente = "border:none;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.32),transparent);"
        label_color = "#FDBA74"
    else:
        cor_default = "rgba(255,255,255,.22)"
        gradiente = "border:none;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.42),transparent);"
        label_color = "#FFFFFF"
    cor_final = _cor_css_segura(cor, cor_default)

    if estilo == "espaco":
        alturas = {"pequeno": "8px", "medio": "16px", "grande": "28px"}
        _render_html(
            f'<div aria-hidden="true" style="height:{alturas.get(espacamento, "16px")};"></div>',
            st.sidebar,
        )
        return
    if estilo == "pontilhado":
        linha = f"border:none;border-top:1.5px dashed {cor_final};"
    elif estilo == "gradiente":
        linha = gradiente
    else:
        linha = f"border:none;border-top:1px solid {cor_final};"

    if label:
        markup = (
            f'<div style="display:flex;align-items:center;gap:10px;margin:{margem};">'
            f'<div style="flex:1;{linha}"></div>'
            f'<span style="font-size:9px;font-weight:750;color:{label_color};'
            f'text-transform:uppercase;letter-spacing:.12em;">{_escapar(label)}</span>'
            f'<div style="flex:1;{linha}"></div></div>'
        )
    else:
        markup = f'<div style="margin:{margem};{linha}"></div>'
    _render_html(markup, st.sidebar)


def render_sidebar_footer_info(
    itens: dict[str, Any] | list[tuple[str, Any]] | None = None,
    copyright: str = "",
    empresa: str = "TOTALE",
    ano: int | None = None,
    versao: str = "",
    ambiente: str = "",
    unidade: str = "",
    mostrar_relógio: bool = False,
    tema: TemaSidebarType | str | None = None,
    **kwargs: Any,
) -> None:
    """Renderiza versão, ambiente, metadados, relógio opcional e copyright."""
    mostrar_relogio = mostrar_relógio or bool(kwargs.get("mostrar_relogio", False))
    try:
        itens_dict = dict(itens) if itens is not None else {}
    except (TypeError, ValueError):
        itens_dict = {}
    agora = _agora_br()
    ano_final = ano if ano is not None else agora.year
    tema_ativo = _obter_tema_sidebar(tema)
    tokens = _TEMAS[tema_ativo]

    badges: list[str] = []
    if versao:
        versao_txt = str(versao)
        if not versao_txt.lower().startswith("v"):
            versao_txt = f"v{versao_txt}"
        badges.append(
            f'<span style="padding:3px 8px;border-radius:999px;background:{tokens["card_fundo"]};'
            f'color:{tokens["texto_acento"]};font-size:10px;font-weight:750;">{_escapar(versao_txt)}</span>'
        )
    if ambiente:
        amb_key = str(ambiente).strip().lower()
        amb_cfg = {
            "produção": ("#ECFDF5", "#065F46", "#059669"),
            "producao": ("#ECFDF5", "#065F46", "#059669"),
            "prod": ("#ECFDF5", "#065F46", "#059669"),
            "homologação": ("#FFFBEB", "#92400E", "#D97706"),
            "homologacao": ("#FFFBEB", "#92400E", "#D97706"),
            "hml": ("#FFFBEB", "#92400E", "#D97706"),
            "desenvolvimento": ("#EFF6FF", "#1E40AF", "#3B82F6"),
            "dev": ("#EFF6FF", "#1E40AF", "#3B82F6"),
            "local": ("#F3F4F6", "#374151", "#9CA3AF"),
        }
        bg, fg, dot = amb_cfg.get(
            amb_key, (tokens["card_fundo"], tokens["texto_secundario"], tokens["icone"])
        )
        badges.append(
            f'<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 8px;'
            f'border-radius:999px;background:{bg};color:{fg};font-size:10px;font-weight:750;">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{dot};"></span>'
            f"{_escapar(ambiente)}</span>"
        )

    badges_html = (
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;">{"".join(badges)}</div>'
        if badges
        else ""
    )
    unidade_html = (
        f'<div style="font-size:11px;font-weight:650;color:{tokens["texto_secundario"]};'
        f'margin-bottom:8px;border-left:3px solid #F37C04;padding-left:8px;">'
        f"{_escapar(unidade)}</div>"
        if unidade
        else ""
    )
    linhas = "".join(
        '<div style="display:flex;justify-content:space-between;gap:8px;padding:3px 0;">'
        f'<span style="font-size:11px;color:{tokens["texto_muted"]};">{_escapar(chave)}</span>'
        f'<span style="font-size:11px;color:{tokens["texto_primario"]};font-weight:750;">{_escapar(valor)}</span></div>'
        for chave, valor in itens_dict.items()
    )
    itens_html = (
        f'<div style="border-top:1px solid {tokens["card_borda"]};padding-top:8px;">{linhas}</div>'
        if linhas
        else ""
    )
    relogio_html = (
        f'<div style="font-size:10px;color:{tokens["texto_muted"]};text-align:center;margin-top:8px;">'
        f"{agora.strftime('%d/%m/%Y %H:%M')}</div>"
        if mostrar_relogio
        else ""
    )
    copy_final = copyright or f"© {ano_final} {empresa}"
    markup = (
        f'<div class="sidebar-footer">{badges_html}{unidade_html}{itens_html}{relogio_html}'
        f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid {tokens["card_borda"]};'
        f'font-size:10px;color:{tokens["texto_muted"]};text-align:center;">{_escapar(copy_final)}</div></div>'
    )
    _render_html(markup, st.sidebar)


def render_sidebar_info(
    user_name: str = "",
    role: str = "",
    email: str = "",
    avatar: str = "",
    itens: dict[str, Any] | list[tuple[str, Any]] | None = None,
    icone: str = "ℹ️",
    rodape: str = "",
    status: Literal["online", "offline", "ausente", "ocupado", ""] = "online",
    titulo: str = "",
    tema: TemaSidebarType | str | None = None,
) -> None:
    """Renderiza cartão opcional de usuário, dados complementares e presença."""
    try:
        itens_dict = dict(itens) if itens is not None else {}
    except (TypeError, ValueError):
        itens_dict = {}
    tema_ativo = _obter_tema_sidebar(tema)
    tokens = _TEMAS[tema_ativo]

    status_cfg = {
        "online": ("#059669", "Online"),
        "offline": ("#94A3B8", "Offline"),
        "ausente": ("#D97706", "Ausente"),
        "ocupado": ("#DC2626", "Ocupado"),
    }
    if avatar and _url_valida(avatar):
        avatar_html = (
            f'<img src="{_escapar(avatar)}" alt="" '
            'style="width:40px;height:40px;border-radius:12px;object-fit:cover;flex:none;">'
        )
    else:
        if avatar:
            iniciais = str(avatar).strip()[:2].upper()
        elif user_name.strip():
            partes = user_name.strip().split()
            iniciais = (
                (partes[0][0] + partes[-1][0]).upper()
                if len(partes) > 1
                else partes[0][0].upper()
            )
        else:
            iniciais = "U"
        avatar_html = (
            f'<div aria-hidden="true" style="width:40px;height:40px;border-radius:12px;display:flex;'
            f'align-items:center;justify-content:center;background:#012869;color:#fff;font-weight:800;flex:none;">'
            f"{_escapar(iniciais)}</div>"
        )

    status_html = ""
    if status and status in status_cfg:
        cor_status, label_status = status_cfg[status]
        status_html = (
            f'<span style="display:inline-flex;align-items:center;gap:5px;margin-top:3px;'
            f'font-size:10px;font-weight:750;color:{cor_status};">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{cor_status};"></span>'
            f"{label_status}</span>"
        )
    user_html = ""
    if user_name or role or email or avatar:
        user_html = (
            '<div style="display:flex;align-items:center;gap:12px;">'
            f'{avatar_html}<div style="min-width:0;">'
            f'<p class="sidebar-user-name" style="margin:0;font-size:13px;font-weight:750;color:{tokens["texto_primario"]};">{_escapar(user_name)}</p>'
            f'<p class="sidebar-user-role" style="margin:2px 0 0;font-size:11px;color:{tokens["texto_acento"]};font-weight:650;">{_escapar(role)}</p>'
            f'<p class="sidebar-user-email" style="margin:2px 0 0;font-size:11px;color:{tokens["texto_muted"]};overflow-wrap:anywhere;">{_escapar(email)}</p>'
            f"{status_html}</div></div>"
        )
    linhas = "".join(
        '<div style="display:flex;justify-content:space-between;gap:8px;padding:4px 0;">'
        f'<span style="font-size:11px;color:{tokens["texto_muted"]};">{_escapar(chave)}</span>'
        f'<span style="font-size:11px;color:{tokens["texto_primario"]};font-weight:750;">{_escapar(valor)}</span></div>'
        for chave, valor in itens_dict.items()
    )
    itens_html = f'<div style="margin-top:8px;">{linhas}</div>' if linhas else ""
    rodape_html = (
        f'<div style="margin-top:8px;font-size:10px;color:{tokens["texto_muted"]};">{_escapar(rodape)}</div>'
        if rodape
        else ""
    )
    titulo_html = (
        f'<div class="sidebar-section-header"><span style="font-size:11px;font-weight:750;'
        f'color:{tokens["secao"]};text-transform:uppercase;letter-spacing:.08em;">'
        f"{_escapar(titulo)}</span></div>"
        if titulo
        else ""
    )
    if not any((user_html, itens_html, rodape_html, titulo_html)):
        return
    markup = (
        f'{titulo_html}<div class="sidebar-profile-card" role="region" '
        f"aria-label=\"{_escapar(titulo or user_name or 'Informações do usuário')}\" "
        f"style=\"background:{tokens['card_fundo']};border:1px solid {tokens['card_borda']};"
        f'border-radius:14px;padding:14px;margin:8px 0 12px;">'
        f"{user_html}{itens_html}{rodape_html}</div>"
    )
    _render_html(markup, st.sidebar)


def formatar_datetime_exibicao(valor: Any, com_segundos: bool = False) -> str:
    """Formata datas para exibição, aceitando datetime, Timestamp e texto."""
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        formato = "%d/%m/%Y %H:%M:%S" if com_segundos else "%d/%m/%Y %H:%M"
        return valor.strftime(formato)
    try:
        import pandas as pd

        ts = pd.Timestamp(valor)
        if pd.isna(ts):
            return str(valor)
        formato = "%d/%m/%Y %H:%M:%S" if com_segundos else "%d/%m/%Y %H:%M"
        return ts.strftime(formato)
    except (TypeError, ValueError, OverflowError, ImportError):
        return str(valor)


def render_sidebar_status(
    status: str = "Ativo",
    label: str = "STATUS DO SISTEMA",
    ultima_atualizacao: Any = "",
    total_registros: int | str | None = None,
    detalhes: dict[str, Any] | None = None,
    tipo: Literal["ok", "info", "alerta", "critico"] = "ok",
    compacto: bool = False,
    container: Any = None,
    tema: TemaSidebarType | str | None = None,
    nav_contrast: str | None = None,
    **kwargs: Any,
) -> None:
    """Renderiza badge compacto ou cartão detalhado de status do sistema."""
    if nav_contrast is None and "cor_nav_contrast" in kwargs:
        nav_contrast = kwargs.get("cor_nav_contrast")
    if nav_contrast:
        cor_nav = _cor_css_segura(nav_contrast, "#FFFFFF")
        _render_html(
            '<style>[data-testid="stSidebarNav"] a[aria-current="page"],'
            '[data-testid="stSidebarNav"] a[aria-current="page"] * {'
            f"color:{cor_nav} !important;-webkit-text-fill-color:{cor_nav} !important;}}</style>",
            st,
        )

    tema_ativo = _obter_tema_sidebar(tema)
    tokens = _TEMAS[tema_ativo]
    cfg = {
        "ok": ("#047857", "#ECFDF5", "#A7F3D0", "#065F46"),
        "info": ("#1D4ED8", "#EFF6FF", "#BFDBFE", "#1E3A8A"),
        "alerta": ("#D97706", "#FFFBEB", "#FDE68A", "#92400E"),
        "critico": ("#DC2626", "#FEF2F2", "#FECACA", "#991B1B"),
    }
    cor, bg, borda, texto = cfg.get(tipo, cfg["ok"])
    pill = (
        f'<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 8px;'
        f"border-radius:999px;background:{bg};color:{texto};border:1px solid {borda};"
        f'font-size:10px;font-weight:750;white-space:nowrap;">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{cor};"></span>'
        f"{_escapar(status)}</span>"
    )
    destino = container if container is not None else st.sidebar
    if compacto or kwargs.get("badge_only", False):
        _render_html(f'<div style="margin:6px 0;">{pill}</div>', destino)
        return

    detalhes_html = "".join(
        '<div style="display:flex;justify-content:space-between;gap:8px;padding:3px 0;">'
        f'<span style="font-size:11px;color:{tokens["texto_muted"]};">{_escapar(chave)}</span>'
        f'<span style="font-size:11px;color:{tokens["texto_primario"]};font-weight:750;">{_escapar(valor)}</span></div>'
        for chave, valor in (detalhes or {}).items()
    )
    ultima_fmt = (
        formatar_datetime_exibicao(ultima_atualizacao) if ultima_atualizacao else ""
    )
    data_html = (
        f'<div style="font-size:10px;color:{tokens["texto_muted"]};margin-top:6px;">'
        f"Atualizado { _escapar(ultima_fmt) }</div>"
        if ultima_fmt
        else ""
    )
    total_html = (
        f'<div style="font-size:12px;color:{tokens["texto_secundario"]};margin-top:5px;">'
        f'Total <strong style="color:{tokens["texto_primario"]};">{_escapar(total_registros)}</strong></div>'
        if total_registros is not None
        else ""
    )
    markup = (
        f'<div class="sidebar-status-card" role="status" aria-label="{_escapar(label)}" '
        f'style="background:{tokens["card_fundo"]};border:1px solid {tokens["card_borda"]};'
        f'border-radius:14px;padding:13px 14px;margin:10px 0 14px;box-shadow:inset 3px 0 0 {cor};">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
        f'<span style="font-size:10px;font-weight:800;letter-spacing:.08em;color:{tokens["texto_muted"]};">'
        f"{_escapar(label.strip().upper())}</span>{pill}</div>{total_html}{detalhes_html}{data_html}</div>"
    )
    _render_html(markup, destino)


def render_sidebar_spacer(
    altura: Literal["pequeno", "medio", "grande", "xgrande"] | int | str = "medio",
) -> None:
    """Adiciona espaço vertical controlado na sidebar."""
    presets = {"pequeno": "8px", "medio": "16px", "grande": "28px", "xgrande": "48px"}
    if isinstance(altura, int):
        altura_css = f"{max(0, min(altura, 1200))}px"
    else:
        valor = str(altura).strip().lower()
        if re.fullmatch(r"\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%)", valor):
            altura_css = valor
        else:
            altura_css = presets.get(valor, "16px")
    _render_html(
        f'<div aria-hidden="true" style="height:{altura_css};"></div>', st.sidebar
    )


__all__ = [
    "TemaSidebarType",
    "aplicar_estilo",
    "aplicar_estilo_corp",
    "aplicar_sidebar_corp",
    "carregar_layout_corporativo",
    "definir_tema_sidebar",
    "formatar_datetime_exibicao",
    "normalizar_tema_sidebar",
    "render_page_sidebar_theme_selector",
    "render_sidebar_brand",
    "render_sidebar_divider",
    "render_sidebar_footer_info",
    "render_sidebar_info",
    "render_sidebar_section",
    "render_sidebar_spacer",
    "render_sidebar_status",
    "render_sidebar_theme_selector",
]
