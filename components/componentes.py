"""
componentes.py
==============
Módulo central unificado de estilos, fontes, componentes reutilizáveis,
visualizações gráficas padronizadas e Design System do Sidebar TOTALE.

Uso em qualquer página:
    from componentes import (
        aplicar_estilo,
        # Sidebar
        aplicar_sidebar_corp,
        render_sidebar_info, render_sidebar_section,
        render_sidebar_status, render_sidebar_footer_info,
        render_sidebar_divider, render_sidebar_spacer,
        # UI
        render_kpi, render_kpi_sm, render_metric_delta,
        render_insight, render_status_pill, render_empty_state,
        render_section_header, render_divider, render_progress_bar,
        render_sidebar_brand, render_table_html,
        # Gráficos e Heros
        render_grafico_linhas, render_grafico_barras,
        render_grafico_rosca, render_grafico_gauge, render_grafico_funnel,
        render_hero_totale_1, render_hero_totale_2,
        render_hero_migracao, render_hero_pme
    )
    aplicar_estilo()
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

logger = logging.getLogger(__name__)

# ====================================================
# TIPOS LITERAIS E ALIASES
# ====================================================
TemaKPI = Literal["azul", "verde", "vermelho", "laranja", "cinza", "roxo"]
TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]
TipoBadge = Literal["laranja", "azul", "verde", "vermelho", "cinza", "roxo"]
TipoStatus = Literal["ativo", "inativo", "pendente", "sucesso", "erro"]
TendenciaDelta = Literal["up", "down", "flat"]

CellFormatter = Union[str, Callable[[Any], str]]
FmtDict = Dict[str, Union[CellFormatter, None]]

ColorRule = Tuple[Callable[[Any], bool], str]
ColorMapDict = Dict[str, List[ColorRule]]

# Configuração de cores condicionais para tabelas
CondicaoCoresConfig = Dict[str, Any]
LinhaDestaqueConfig = Dict[str, Any]


# ====================================================
# TIPOGRAFIA & CORES CORPORATIVAS UNIFICADAS
# ====================================================
FONTE_TITULO = "'Plus Jakarta Sans', 'Inter', 'Segoe UI', Arial, sans-serif"
FONTE_TEXTO = "'IBM Plex Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONTE_CODIGO = "'IBM Plex Mono', Consolas, 'Courier New', monospace"

_GOOGLE_FONTS_URLS = (
    "https://fonts.googleapis.com/icon?family=Material+Icons",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap",
    "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800;900&display=swap",
)

# Paleta Corporativa Totale
COR_PRIMARIA = "#012869"  # Deep Midnight Navy
COR_SECUNDARIA = "#F37C04"  # Solar Orange
COR_SECUNDARIA_HOVER = "#D46B02"
COR_SUCESSO = "#059669"  # Emerald Green
COR_ALERTA = "#DC2626"  # Crimson Red
COR_ATENCAO = "#F59E0B"  # Amber Warning
COR_NEUTRO = "#64748B"  # Slate Grey
COR_ROXO = "#8B5CF6"  # Violet Accent

# Textos
COR_TEXTO = "#1F2937"
COR_TEXTO_2 = "#374151"
COR_TEXTO_3 = "#6B7280"

# Estruturais
COR_BORDA = "#E2E8F0"
COR_FUNDO = "#F8FAFC"
COR_FUNDO_2 = "#F1F5F9"

# ─ Sidebar (tema claro, conforme imagem de referência) ──────────────────
SB_FUNDO = "#EEF2F7"  # Fundo geral da sidebar (cinza-azulado claro)
SB_FUNDO_LINK = "#FFFFFF"  # Fundo dos botões de navegação
SB_FUNDO_LINK_HOVER = "#F8FAFC"
SB_FUNDO_ATIVO = "#FFF7ED"  # Bege/laranja bem claro para item ativo
SB_BORDA_ATIVA = "#F37C04"  # Borda laranja à esquerda do ativo
SB_TITULO_SECAO = "#012869"  # Azul corporativo para títulos de seção
SB_TEXTO_LINK = "#1F2937"  # Texto escuro dos links
SB_TEXTO_MUTED = "#64748B"  # Cinza para labels secundários
SB_BORDA_SUTIL = "#D9E0E9"  # Linhas divisórias discretas

_TEMA_CORES: Dict[str, str] = {
    "azul": COR_PRIMARIA,
    "verde": COR_SUCESSO,
    "vermelho": COR_ALERTA,
    "laranja": COR_SECUNDARIA,
    "cinza": COR_NEUTRO,
    "roxo": COR_ROXO,
}

_INSIGHT_CONFIG: Dict[str, Tuple[str, str, str, str]] = {
    "ok": ("#D1FAE5", "#065F46", "#059669", "✅"),
    "info": ("#DBEAFE", "#1E40AF", "#3B82F6", "ℹ️"),
    "alerta": ("#FEF3C7", "#92400E", "#F59E0B", "⚠️"),
    "critico": ("#FEE2E2", "#991B1B", "#DC2626", "🚨"),
    "acao": ("#EDE9FE", "#5B21B6", "#8B5CF6", ""),
}

_STATUS_CONFIG: Dict[str, Tuple[str, str, str]] = {
    "ativo": ("#D1FAE5", "#065F46", "#10B981"),
    "inativo": ("#F1F5F9", "#475569", "#94A3B8"),
    "pendente": ("#FEF3C7", "#92400E", "#F59E0B"),
    "sucesso": ("#D1FAE5", "#065F46", "#059669"),
    "erro": ("#FEE2E2", "#991B1B", "#DC2626"),
}

_PLOTLY_COLORWAY = [
    COR_PRIMARIA,
    COR_SECUNDARIA,
    COR_SUCESSO,
    COR_ALERTA,
    COR_ROXO,
    "#EC4899",
    "#14B8A6",
    "#F59E0B",
    "#6366F1",
    COR_NEUTRO,
]


# ====================================================
# PLOTLY GLOBAL SETUP
# ====================================================
def _configurar_plotly_global() -> None:
    """Configura o tema global do Plotly com identidade corporativa."""
    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
            title=dict(
                font=dict(family=FONTE_TITULO, size=16, color=COR_TEXTO, weight="bold"),
                x=0.01,
                xanchor="left",
                y=0.95,
            ),
            legend=dict(
                font=dict(family=FONTE_TEXTO, size=11, color=COR_TEXTO_2),
                orientation="h",
                yanchor="bottom",
                y=-0.22,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0)",
                bordercolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=11, color=COR_TEXTO_3),
                gridcolor="#F1F5F9",
                zerolinecolor="#E2E8F0",
                showgrid=True,
                linecolor="#E2E8F0",
            ),
            yaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=11, color=COR_TEXTO_3),
                gridcolor="#F1F5F9",
                zerolinecolor="#E2E8F0",
                showgrid=True,
                linecolor="#E2E8F0",
            ),
            hoverlabel=dict(
                font=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO),
                bgcolor="white",
                bordercolor=COR_BORDA,
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
            colorway=_PLOTLY_COLORWAY,
            margin=dict(l=40, r=20, t=50, b=40),
        )
    )
    pio.templates["corporativo"] = template
    pio.templates.default = "plotly_white+corporativo"


# ====================================================
# INJEÇÃO DE DEPENDÊNCIAS (CSS & FONTES)
# ====================================================
def _injetar_fontes_no_head_pai() -> None:
    """Injeta as fontes Google no <head> pai com preconnect e retry."""
    urls_js = ", ".join(f'"{u}"' for u in _GOOGLE_FONTS_URLS)
    components.html(
        f"""<script>
        (function () {{
            let d;
            try {{ d = window.parent.document; }} catch (e) {{ return; }}
            const head = d.head;
            const add = (rel, href, cross) => {{
                if (head.querySelector('link[href="' + href + '"]')) return;
                const l = d.createElement('link');
                l.rel = rel; l.href = href;
                if (cross) l.crossOrigin = 'anonymous';
                head.appendChild(l);
            }};
            add('preconnect', 'https://fonts.googleapis.com', false);
            add('preconnect', 'https://fonts.gstatic.com', true);
            [{urls_js}].forEach(u => add('stylesheet', u, false));
        }})();
        </script>""",
        height=0,
    )


@st.cache_data
def _get_global_css() -> str:
    """Retorna o CSS Global Corporativo (cacheado para performance)."""
    links_html = "\n".join(
        f'<link rel="stylesheet" href="{url}">' for url in _GOOGLE_FONTS_URLS
    )

    return f"""{links_html}
    <style>
    /* ═══ DUPLA GARANTIA DE FONTES E MATERIAL ICONS ══ */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800;900&display=swap');
    @import url('https://fonts.googleapis.com/icon?family=Material+Icons');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

    /* ═══ VARIÁVEIS CSS ═══ */
    :root {{
        --font-titulo: {FONTE_TITULO};
        --font-texto: {FONTE_TEXTO};
        --font-codigo: {FONTE_CODIGO};
        --cor-primaria: {COR_PRIMARIA};
        --cor-secundaria: {COR_SECUNDARIA};
        --cor-sucesso: {COR_SUCESSO};
        --cor-alerta: {COR_ALERTA};
        --cor-borda: {COR_BORDA};
        --cor-fundo: {COR_FUNDO};
        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
        --shadow-lg: 0 8px 24px rgba(0,0,0,0.12);
    }}

    /* ═══ TIPOGRAFIA BASE ═══ */
    html, body, p, label, li, a, button, input, select, textarea, [class*="st-"] {{
        font-family: var(--font-texto) !important;
    }}
    h1, h2, h3, h4, h5, h6, .hero-title, .section-title, .kpi-value, [data-testid="stMetricValue"] {{
        font-family: var(--font-titulo) !important;
        font-weight: 700;
        letter-spacing: -0.3px;
    }}
    code, pre, kbd, samp {{
        font-family: var(--font-codigo) !important;
    }}

    /* ═══ ÍCONES MATERIAL ══ */
    [data-testid="stIconMaterial"],
    .material-icons,
    .material-symbols-rounded,
    .material-symbols-outlined {{
        font-family: "Material Symbols Rounded", "Material Icons" !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 20px !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        white-space: nowrap !important;
        font-feature-settings: "liga" 1 !important;
        font-variant-ligatures: normal !important;
        -webkit-font-smoothing: antialiased !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        overflow: hidden !important;
    }}

    /* ═══ LAYOUT CORE ═══ */
    .main .block-container {{
        padding-top: 1rem;
        max-width: 1400px;
    }}

    /* ═══════════════════════════════════════════════════
       SIDEBAR — TEMA CLARO CORPORATIVO (TOTALE)
       ═══════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {{
        background-color: {SB_FUNDO} !important;
        border-right: 1px solid {SB_BORDA_SUTIL} !important;
        box-shadow: 2px 0 12px rgba(1, 40, 105, 0.06) !important;
    }}

    section[data-testid="stSidebar"] > div:first-child,
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
        background: transparent !important;
    }}

    /* Scrollbar minimalista */
    section[data-testid="stSidebar"] ::-webkit-scrollbar {{
        width: 5px !important;
        background: transparent !important;
    }}
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{
        background: {SB_BORDA_SUTIL} !important;
        border-radius: 20px !important;
    }}
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {{
        background: {SB_TEXTO_MUTED} !important;
    }}

    /* Títulos de seção (categorias) */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4,
    section[data-testid="stSidebar"] .sidebar-section-title {{
        color: {SB_TITULO_SECAO} !important;
        font-family: var(--font-titulo) !important;
        font-weight: 800 !important;
        font-size: 11px !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        border-bottom: none !important;
        padding: 18px 14px 6px 14px !important;
        margin: 0 !important;
        background: transparent !important;
        text-align: left !important;
    }}

    /* Cabeçalhos NATIVOS de agrupamento no Menu */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] span[data-testid="stSidebarNavSeparator"] ~ span,
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li div {{
        color: {SB_TITULO_SECAO} !important;
        font-family: var(--font-titulo) !important;
        font-weight: 800 !important;
        font-size: 11px !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        background: transparent !important;
        border: none !important;
        margin-top: 14px !important;
        padding: 0 14px 4px 14px !important;
        text-align: left !important;
        display: block !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
        padding-top: 4px !important;
    }}

    /* Botões de páginas — ícone acima do texto */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a {{
        background-color: {SB_FUNDO_LINK} !important;
        border: 1px solid {SB_BORDA_SUTIL} !important;
        border-left: 3px solid transparent !important;
        border-radius: 6px !important;
        margin: 3px 10px !important;
        padding: 8px 12px !important;
        box-shadow: 0 1px 2px rgba(1, 40, 105, 0.04) !important;
        transition: all 0.18s ease !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 2px !important;
        min-height: 58px !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a svg,
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a span:first-child {{
        width: 16px !important;
        height: 16px !important;
        margin: 0 !important;
        flex-shrink: 0 !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a:hover {{
        background-color: {SB_FUNDO_LINK_HOVER} !important;
        border-color: {COR_BORDA} !important;
        transform: translateX(2px);
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a span {{
        color: {SB_TEXTO_LINK} !important;
        font-family: var(--font-texto) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        background: transparent !important;
        text-align: left !important;
        line-height: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
        white-space: nowrap !important;
        display: inline-block !important;
        vertical-align: middle !important;
    }}

    /* Página Ativa — destaque laranja */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a[aria-current="page"] {{
        background-color: {SB_FUNDO_ATIVO} !important;
        border-left: 3px solid {SB_BORDA_ATIVA} !important;
        border-color: {SB_BORDA_SUTIL} !important;
        border-left-color: {SB_BORDA_ATIVA} !important;
        box-shadow: 0 2px 6px rgba(243, 124, 4, 0.12) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a[aria-current="page"] span {{
        color: {COR_PRIMARIA} !important;
        font-weight: 700 !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a[aria-current="page"] svg {{
        fill: {COR_SECUNDARIA} !important;
        color: {COR_SECUNDARIA} !important;
    }}

    /* Esconde linha separadora nativa */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] div[data-testid="stSidebarNavSeparator"] {{
        display: none !important;
    }}

    /* Textos genéricos e labels */
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    section[data-testid="stSidebar"] span {{
        color: {SB_TEXTO_LINK} !important;
        font-weight: 500 !important;
        background: transparent !important;
    }}

    /* ═══════════════════════════════════════════════════
       EXPANDERS NO SIDEBAR — CORREÇÃO DO CARACTERE "a"
       ═══════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {{
        background-color: {SB_FUNDO_LINK} !important;
        border: 1px solid {SB_BORDA_SUTIL} !important;
        border-radius: 8px !important;
        margin: 8px 10px !important;
        overflow: hidden !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        background-color: {SB_FUNDO_LINK_HOVER} !important;
        position: relative !important;
        padding: 10px 14px 10px 36px !important;
        transition: background-color 0.2s ease;
        list-style: none !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary::before {{
        content: "▸" !important;
        display: block !important;
        position: absolute !important;
        left: 14px !important;
        top: 50% !important;
        color: {COR_PRIMARIA} !important;
        font-family: Arial, sans-serif !important;
        font-size: 18px !important;
        line-height: 1 !important;
        transform: translateY(-50%) !important;
        visibility: visible !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"][open] > summary::before,
    section[data-testid="stSidebar"] [data-testid="stExpander"] details[open] > summary::before {{
        content: "▾" !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary::-webkit-details-marker {{
        display: none !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary .material-icons,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary .material-symbols-rounded,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{
        display: none !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
        background-color: {COR_FUNDO_2} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {{
        color: {COR_PRIMARIA} !important;
        fill: {COR_PRIMARIA} !important;
        font-weight: 700 !important;
        font-family: var(--font-titulo) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpanderDetails"] {{
        padding: 14px !important;
        background: transparent !important;
    }}
    /* Desativa ligaturas de fonte que podem causar caracteres fantasmas */
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary * {{
        font-feature-settings: "liga" 0 !important;
        font-variant-ligatures: none !important;
    }}

    /* Sliders */
    section[data-testid="stSidebar"] [data-testid="stSlider"] {{
        padding-top: 8px !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSlider"] [data-testid="stThumbValue"],
    section[data-testid="stSidebar"] [data-testid="stSlider"] [data-testid="stTickBar"] {{
        color: {COR_PRIMARIA} !important;
        font-family: var(--font-codigo) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }}

    /* Checkboxes */
    section[data-testid="stSidebar"] [data-testid="stCheckbox"] label span {{
        color: {SB_TEXTO_LINK} !important;
        font-weight: 600 !important;
    }}

    /* Divisores */
    section[data-testid="stSidebar"] hr {{
        background: linear-gradient(90deg, transparent 0%, {SB_BORDA_SUTIL} 50%, transparent 100%) !important;
        height: 1px !important;
        border: none !important;
        margin: 14px 10px !important;
    }}

    /* Botões primários no sidebar */
    section[data-testid="stSidebar"] .stButton button {{
        background: {COR_SECUNDARIA} !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-family: var(--font-titulo) !important;
        font-size: 13px !important;
        letter-spacing: 0.3px !important;
        width: 100% !important;
        padding: 8px 14px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 4px rgba(243, 124, 4, 0.25) !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        background: {COR_SECUNDARIA_HOVER} !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(243, 124, 4, 0.35) !important;
    }}

    /* Inputs e Selects */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] select,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="base-input"] {{
        background-color: {SB_FUNDO_LINK} !important;
        color: {SB_TEXTO_LINK} !important;
        border: 1px solid {SB_BORDA_SUTIL} !important;
        border-radius: 6px !important;
        font-family: var(--font-texto) !important;
    }}
    section[data-testid="stSidebar"] input:focus,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within {{
        border-color: {COR_SECUNDARIA} !important;
        box-shadow: 0 0 0 2px rgba(243, 124, 4, 0.15) !important;
    }}

    /* ═══════════════════════════════════════════════════
       HEROS CORPORATIVOS
       ═══════════════════════════════════════════════════ */
    .hero-totale-1 {{
        background: linear-gradient(to right, rgb(1,40,105) 0%, rgb(243,124,4) 100%);
        padding: 3rem 2.5rem;
        border-radius: var(--radius-md);
        color: #FFFFFF;
        position: relative;
        overflow: hidden;
        box-shadow: var(--shadow-md);
    }}
    .hero-totale-1::after {{
        content: ''; position: absolute; top: -50%; left: -60%; width: 30%; height: 200%;
        background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.25) 50%, rgba(255,255,255,0) 100%);
        transform: rotate(25deg);
        animation: feixeLuz 6s infinite ease-in-out;
    }}
    @keyframes feixeLuz {{ 0% {{ left: -60%; }} 30%, 100% {{ left: 130%; }} }}
    .hero-t1-content {{ position: relative; z-index: 1; }}

    .hero-totale-2 {{
        background: linear-gradient(to right, rgb(243,124,4) 0%, rgb(1,40,105) 100%);
        padding: 2.5rem 2rem;
        border-radius: var(--radius-md);
        color: #FFFFFF;
        position: relative;
        overflow: hidden;
        box-shadow: var(--shadow-md);
    }}
    .hero-totale-2::after {{
        content: ''; position: absolute; top: -50%; left: -60%; width: 25%; height: 200%;
        background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0) 100%);
        transform: rotate(25deg);
        animation: feixeLuzLeve 8s infinite ease-in-out;
    }}
    @keyframes feixeLuzLeve {{ 0% {{ left: -60%; }} 25%, 100% {{ left: 130%; }} }}
    .hero-t2-badge {{
        display: inline-block; padding: 5px 14px; border-radius: 12px;
        font-size: 11px; font-weight: bold; text-transform: uppercase; margin-top: 16px;
        font-family: var(--font-codigo);
    }}
    .badge-laranja {{ background-color: #FFFFFF; color: rgb(243,124,4); }}
    .badge-azul {{ background-color: rgb(1,40,105); color: #FFFFFF; border: 1px solid rgba(255, 255, 255, 0.4); }}

    /* ═══════════════════════════════════════════════════
       HEROS ESPECÍFICOS (MIGRAÇÃO E PME) — RÉPLICA DA IMAGEM
       ═══════════════════════════════════════════════════ */
    .hero-migracao {{
        background: linear-gradient(135deg, #024B7A 0%, #027BBF 100%);
        padding: 2.2rem 2.5rem;
        border-radius: 16px;
        color: #FFFFFF;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(2, 75, 122, 0.2);
    }}
    .hero-migracao::after {{
        content: ''; position: absolute; top: -50%; left: -60%; width: 30%; height: 200%;
        background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.15) 50%, rgba(255,255,255,0) 100%);
        transform: rotate(25deg);
        animation: feixeLuz 7s infinite ease-in-out;
    }}

    .hero-pme {{
        background: linear-gradient(135deg, #4A1D96 0%, #8B42F6 100%);
        padding: 2.2rem 2.5rem;
        border-radius: 16px;
        color: #FFFFFF;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(74, 29, 150, 0.2);
    }}
    .hero-pme::after {{
        content: ''; position: absolute; top: -50%; left: -60%; width: 30%; height: 200%;
        background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.15) 50%, rgba(255,255,255,0) 100%);
        transform: rotate(25deg);
        animation: feixeLuz 7s infinite ease-in-out;
    }}

    /* ═══════════════════════════════════════════════════
       TIPOGRAFIA DOS HEROS
       ═══════════════════════════════════════════════════ */
    .hero-totale-1 .hero-t1-title,
    .hero-totale-2 .hero-t2-title {{
        font-family: var(--font-titulo) !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
        margin: 0;
        color: #FFFFFF !important;
        line-height: 1.15;
    }}

    .hero-migracao .hero-alt-title,
    .hero-pme .hero-alt-title,
    .hero-alt-title {{
        font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif !important;
        font-weight: 800 !important;
        font-size: 2.1rem !important;
        letter-spacing: -0.6px !important;
        margin: 0 !important;
        color: #FFFFFF !important;
        display: flex !important;
        align-items: center !important;
        gap: 14px !important;
        line-height: 1.2 !important;
    }}

    /* Container do ícone quadrado escuro igual ao da imagem */
    .hero-alt-title .hero-icon-box {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.28);
        border: 1.5px solid rgba(255, 255, 255, 0.35);
        border-radius: 6px;
        width: 38px;
        height: 38px;
        font-size: 20px;
        flex-shrink: 0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    }}

    .hero-totale-1 .hero-t1-title {{ font-size: 2.8rem; }}
    .hero-totale-2 .hero-t2-title {{ font-size: 2.4rem; }}

    .hero-totale-1 .hero-t1-sub,
    .hero-totale-2 .hero-t2-sub {{
        font-family: var(--font-texto) !important;
        font-weight: 500 !important;
        letter-spacing: 0;
        margin: 0.75rem 0 0 0;
        color: rgba(255, 255, 255, 0.95) !important;
        line-height: 1.45;
        opacity: 0.95;
    }}

    .hero-migracao .hero-alt-sub,
    .hero-pme .hero-alt-sub,
    .hero-alt-sub {{
        font-family: 'IBM Plex Sans', 'Inter', sans-serif !important;
        font-weight: 400 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0px !important;
        margin: 1rem 0 0 0 !important;
        color: rgba(255, 255, 255, 0.88) !important;
        line-height: 1.4 !important;
    }}

    .hero-totale-1 .hero-t1-sub {{ font-size: 1.25rem; }}
    .hero-totale-2 .hero-t2-sub {{ font-size: 1.1rem; }}

    /* ═══════════════════════════════════════════════════
       KPIs CORPORATIVOS
       ═══════════════════════════════════════════════════ */
    .kpi-card {{
        background: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%);
        border-radius: var(--radius-md);
        padding: 20px 24px;
        box-shadow: var(--shadow-sm);
        border-top: 1px solid #F3F4F6;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }}
    .kpi-card .kpi-label {{
        font-size: 12px; font-weight: 600; color: #64748B;
        text-transform: uppercase; letter-spacing: 0.5px;
    }}
    .kpi-card .kpi-value {{
        font-size: 1.85rem; font-weight: 700; margin: 4px 0;
    }}
    .kpi-card .kpi-sub {{ font-size: 12px; color: #94A3B8; }}

    .kpi-card-delta {{
        background: #FFFFFF;
        border-radius: var(--radius-md);
        padding: 18px 22px;
        box-shadow: var(--shadow-sm);
        border-top: 3px solid;
        transition: all 0.2s ease;
    }}
    .kpi-card-delta:hover {{
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }}
    .kpi-card-delta .kpi-delta-header {{
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 8px;
    }}
    .kpi-card-delta .kpi-delta-label {{
        font-size: 11px; font-weight: 700; color: #64748B;
        text-transform: uppercase; letter-spacing: 0.6px;
    }}
    .kpi-card-delta .kpi-delta-value {{
        font-family: var(--font-titulo);
        font-size: 1.9rem; font-weight: 800;
        line-height: 1.15; margin-bottom: 6px;
        letter-spacing: -0.5px;
    }}
    .kpi-card-delta .kpi-delta-indicator {{
        display: inline-flex; align-items: center; gap: 4px;
        font-size: 12px; font-weight: 700;
        padding: 3px 8px; border-radius: 12px;
    }}
    .kpi-delta-up   {{ background: #D1FAE5; color: #065F46; }}
    .kpi-delta-down {{ background: #FEE2E2; color: #991B1B; }}
    .kpi-delta-flat {{ background: #F1F5F9; color: #475569; }}

    .kpi-card-sm {{
        background: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%);
        border-radius: var(--radius-sm);
        padding: 10px 14px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
        border: 1px solid var(--cor-borda);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .kpi-card-sm:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.07);
    }}
    .kpi-card-sm .kpi-label {{
        font-size: 10.5px; font-weight: 600; color: #64748B;
        text-transform: uppercase; letter-spacing: 0.4px;
        margin-bottom: 2px;
        display: flex; align-items: center; justify-content: space-between;
    }}
    .kpi-card-sm .kpi-value {{
        font-family: var(--font-titulo) !important;
        font-size: 1.25rem; font-weight: 700;
        line-height: 1.2; letter-spacing: -0.2px;
    }}
    .kpi-card-sm .kpi-sub {{
        font-size: 10.5px; color: #94A3B8;
        margin-top: 2px; font-weight: 500;
    }}

    /* ═══════════════════════════════════════════════════
       STATUS PILLS
       ══════════════════════════════════════════════════ */
    .status-pill {{
        display: inline-flex; align-items: center; gap: 5px;
        padding: 3px 10px; border-radius: 12px;
        font-size: 11px; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.5px;
        border: 1px solid;
    }}
    .status-pill::before {{
        content: ''; width: 6px; height: 6px; border-radius: 50%;
        background: currentColor;
    }}

    /* ═══════════════════════════════════════════════════
       PROGRESS BAR CORPORATIVA
       ═══════════════════════════════════════════════════ */
    .progress-container {{
        background: #FFFFFF;
        border-radius: var(--radius-md);
        padding: 14px 18px;
        border: 1px solid var(--cor-borda);
        box-shadow: var(--shadow-sm);
    }}
    .progress-header {{
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 8px;
    }}
    .progress-label {{
        font-size: 12px; font-weight: 700; color: #374151;
        text-transform: uppercase; letter-spacing: 0.4px;
    }}
    .progress-value {{
        font-family: var(--font-titulo);
        font-size: 14px; font-weight: 800; color: #0F172A;
        font-variant-numeric: tabular-nums;
    }}
    .progress-track {{
        background: #F1F5F9;
        border-radius: 999px;
        height: 10px; overflow: hidden;
    }}
    .progress-fill {{
        height: 100%; border-radius: 999px;
        transition: width 0.5s ease;
        position: relative;
    }}
    .progress-fill::after {{
        content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%);
        animation: progressShine 2s infinite;
    }}
    @keyframes progressShine {{
        0% {{ transform: translateX(-100%); }}
        100% {{ transform: translateX(100%); }}
    }}
    .progress-footer {{
        margin-top: 6px;
        font-size: 11px; color: #6B7280; font-weight: 500;
    }}

    /* ═══════════════════════════════════════════════════
       EMPTY STATE
       ═══════════════════════════════════════════════════ */
    .empty-state {{
        text-align: center;
        padding: 48px 24px;
        background: #FAFBFC;
        border: 2px dashed var(--cor-borda);
        border-radius: var(--radius-lg);
        color: #64748B;
    }}
    .empty-state-icon {{ font-size: 48px; margin-bottom: 12px; opacity: 0.6; }}
    .empty-state-title {{
        font-family: var(--font-titulo);
        font-size: 16px; font-weight: 700;
        color: #374151; margin-bottom: 6px;
    }}
    .empty-state-msg {{
        font-size: 13px; color: #6B7280; line-height: 1.5;
        max-width: 400px; margin: 0 auto;
    }}

    /* ═══════════════════════════════════════════════════
       DIVIDER CORPORATIVO
       ═══════════════════════════════════════════════════ */
    .corp-divider {{
        display: flex; align-items: center; gap: 12px;
        margin: 24px 0 16px 0;
    }}
    .corp-divider-line {{
        flex: 1; height: 1px;
        background: linear-gradient(90deg, transparent, var(--cor-borda), transparent);
    }}
    .corp-divider-text {{
        font-family: var(--font-titulo);
        font-size: 11px; font-weight: 800;
        color: #94A3B8; text-transform: uppercase;
        letter-spacing: 1.2px;
    }}

    /* ══════════════════════════════════════════════════
       TABELAS CORPORATIVAS
       ═══════════════════════════════════════════════════ */
    .corp-table-wrap {{
        width: 100%; overflow: auto;
        border: 1px solid var(--cor-borda);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-sm);
        background: #FFFFFF;
    }}
    table.corp-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
    }}
    .corp-table thead th {{
        font-family: var(--font-titulo) !important;
        font-weight: 700; font-size: 11px;
        text-transform: uppercase; color: #1F2937;
        background: #F8FAFC; padding: 10px 14px;
        border-bottom: 2px solid var(--cor-borda);
        text-align: left;
        position: sticky; top: 0; z-index: 2;
        white-space: nowrap;
    }}
    .corp-table tbody td {{
        font-weight: 500; font-size: 11px; color: #374151;
        padding: 8px 14px;
        border-bottom: 1px solid #F3F4F6;
        white-space: nowrap;
    }}
    .corp-table tbody tr:hover td {{ background: #F8FAFC !important; }}
    .corp-table td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .corp-table tr.total-row td {{
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%) !important;
        color: #FFFFFF !important;
        font-weight: 800 !important;
        border-top: 2px solid var(--cor-secundaria) !important;
    }}

    /* ═══════════════════════════════════════════════════
       COMPONENTES CUSTOMIZADOS SIDEBAR (TOTALE UI)
       ═══════════════════════════════════════════════════ */
    .sidebar-section-title {{
        color: {SB_TITULO_SECAO} !important;
        font-weight: 800 !important;
        font-size: 11px !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        padding: 18px 14px 6px 14px !important;
        margin: 0 !important;
        font-family: var(--font-titulo) !important;
    }}
    .user-profile-box {{
        padding: 12px 14px;
        border-radius: 8px;
        background: {SB_FUNDO_LINK};
        border: 1px solid {SB_BORDA_SUTIL};
        margin: 8px 10px 16px 10px;
        box-shadow: 0 1px 3px rgba(1, 40, 105, 0.05);
    }}
    .user-profile-name {{
        color: {COR_PRIMARIA};
        font-size: 13.5px;
        font-weight: 700;
        font-family: var(--font-titulo) !important;
    }}
    .user-profile-email {{
        color: {SB_TEXTO_MUTED};
        font-size: 11px;
        margin-top: 2px;
    }}

    .status-container {{
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 12.5px;
        color: {SB_TEXTO_LINK};
        padding: 6px 14px;
        font-weight: 600;
    }}
    .status-pill-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        box-shadow: 0 0 6px currentColor;
    }}

    /* ═══════════════════════════════════════════════════
       CORREÇÃO FINAL - REMOVE CARACTERES FANTASMAS GLOBAIS
       ═══════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] details summary {{
        list-style-type: none !important;
        list-style-position: outside !important;
    }}
    section[data-testid="stSidebar"] details summary::-webkit-details-marker {{
        display: inline-block !important;
    }}
    </style>
    """


def _injetar_css_global() -> None:
    """Injeta o CSS Global no <head> da página."""
    st.markdown(_get_global_css(), unsafe_allow_html=True)


# ====================================================
# API PÚBLICA DE INICIALIZAÇÃO
# ====================================================
def aplicar_estilo() -> None:
    """Aplica configuração Plotly, injeta fontes e CSS Global."""
    _configurar_plotly_global()
    _injetar_fontes_no_head_pai()
    _injetar_css_global()


# ====================================================
# HELPERS INTERNOS
# ====================================================
def _resolver_cor_tema(tema: str) -> str:
    return _TEMA_CORES.get(tema, COR_PRIMARIA)


def _markdown_inline_para_html(texto: str) -> str:
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    return texto


def _detectar_colunas_numericas(df: pd.DataFrame) -> List[str]:
    return df.select_dtypes(include=["number"]).columns.tolist()


def _fmt_br(valor: float, casas: int = 1) -> str:
    """Formata número no padrão brasileiro (1.234,56)."""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ====================================================
# HEROS CORPORATIVOS
# ====================================================
def render_hero_totale_1(
    titulo: str = "Portal TOTALE",
    subtitulo: str = "Painéis de Produção e Gestão Estratégica",
) -> None:
    """Hero Principal: Gradiente Azul para Laranja."""
    if not titulo:
        return
    html = (
        f'<div class="hero-totale-1"><div class="hero-t1-content">'
        f'<h1 class="hero-t1-title">{titulo}</h1>'
        f'<p class="hero-t1-sub">{subtitulo}</p>'
        f"</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_hero_totale_2(
    titulo: str,
    subtitulo: str = "",
    badge_texto: str = "",
    badge_tipo: str = "laranja",
) -> None:
    """Hero Secundário: Gradiente Laranja para Azul com Badge."""
    if not titulo:
        return
    cls_badge = "badge-laranja" if badge_tipo.lower() == "laranja" else "badge-azul"
    html_badge = (
        f'<span class="hero-t2-badge {cls_badge}">{badge_texto}</span>'
        if badge_texto
        else ""
    )
    html = (
        f'<div class="hero-totale-2"><div class="hero-t2-container">'
        f'<h1 class="hero-t2-title">{titulo}</h1>'
        f'<p class="hero-t2-sub">{subtitulo}</p>{html_badge}'
        f"</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_hero_migracao(
    titulo: str = "🔄 Migração — Quebra de Agenda",
    subtitulo: str = "Análise estratégica dedicada às mudanças de pacotes com tecnologia GPON",
) -> None:
    """Hero Específico: Gradiente Azul para painéis de Migração."""
    if not titulo:
        return
    html = (
        f'<div class="hero-migracao"><div class="hero-t1-content">'
        f'<h1 class="hero-alt-title"><span>{titulo}</span></h1>'
        f'<p class="hero-alt-sub">{subtitulo}</p>'
        f"</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_hero_pme(
    titulo: str = "🏢 PME — Quebra de Agenda",
    subtitulo: str = "Análise estratégica dedicada às Pequenas e Médias Empresas",
) -> None:
    """Hero Específico: Gradiente Roxo para painéis PME."""
    if not titulo:
        return
    html = (
        f'<div class="hero-pme"><div class="hero-t1-content">'
        f'<h1 class="hero-alt-title"><span>{titulo}</span></h1>'
        f'<p class="hero-alt-sub">{subtitulo}</p>'
        f"</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    """Função legada — aponta para hero_totale_1."""
    extra = f" · {badge}" if badge else ""
    render_hero_totale_1(titulo, f"{subtitulo}{extra}".strip(" ·"))


# ====================================================
# KPIs
# ====================================================
def render_kpi(
    col: Any, label: str, valor: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    """Renderiza um cartão KPI padrão."""
    cor = _resolver_cor_tema(tema)
    renderer = col.markdown if hasattr(col, "markdown") else st.markdown
    html = (
        f'<div class="kpi-card" style="border-left: 4px solid {cor};">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value" style="color:{cor};">{valor}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f"</div>"
    )
    renderer(html, unsafe_allow_html=True)


def render_kpi_sm(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
    icone: str = "",
) -> None:
    """Renderiza um cartão KPI compacto."""
    cor = _resolver_cor_tema(tema)
    renderer = col.markdown if hasattr(col, "markdown") else st.markdown
    html_icone = (
        f'<span style="font-size:13px; margin-left:4px;">{icone}</span>'
        if icone
        else ""
    )
    html_sub = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    html = (
        f'<div class="kpi-card-sm" style="border-left: 3px solid {cor};">'
        f'<div class="kpi-label"><span>{label}</span>{html_icone}</div>'
        f'<div class="kpi-value" style="color:{cor};">{valor}</div>'
        f"{html_sub}"
        f"</div>"
    )
    renderer(html, unsafe_allow_html=True)


def render_metric_delta(
    col: Any,
    label: str,
    valor: str,
    delta: float,
    delta_sufixo: str = "%",
    tendencia: TendenciaDelta | None = None,
    tema: TemaKPI = "azul",
    inverter_cor: bool = False,
) -> None:
    """Renderiza um KPI com indicador de variação (Delta)."""
    cor = _resolver_cor_tema(tema)
    renderer = col.markdown if hasattr(col, "markdown") else st.markdown

    if tendencia is None:
        if delta > 0.01:
            tendencia = "up"
        elif delta < -0.01:
            tendencia = "down"
        else:
            tendencia = "flat"

    icones = {"up": "▲", "down": "▼", "flat": "▬"}
    classes = {"up": "kpi-delta-up", "down": "kpi-delta-down", "flat": "kpi-delta-flat"}

    if inverter_cor:
        if tendencia == "up":
            classe = "kpi-delta-down"
        elif tendencia == "down":
            classe = "kpi-delta-up"
        else:
            classe = "kpi-delta-flat"
    else:
        classe = classes[tendencia]

    delta_txt = f"{'+' if delta > 0 else ''}{_fmt_br(delta)}{delta_sufixo}"

    html = (
        f'<div class="kpi-card-delta" style="border-top-color:{cor};">'
        f'<div class="kpi-delta-header">'
        f'<span class="kpi-delta-label">{label}</span>'
        f'<span class="kpi-delta-indicator {classe}">{icones[tendencia]} {delta_txt}</span>'
        f"</div>"
        f'<div class="kpi-delta-value" style="color:{cor};">{valor}</div>'
        f"</div>"
    )
    renderer(html, unsafe_allow_html=True)


# ====================================================
# INSIGHTS & ALERTAS
# ====================================================
def render_insight(msg: str, tipo: TipoInsight = "info") -> None:
    """Renderiza uma caixa de alerta/insight com ícone e cor semântica."""
    if not msg:
        return
    bg, texto, borda, icone = _INSIGHT_CONFIG.get(tipo, _INSIGHT_CONFIG["info"])
    msg_html = _markdown_inline_para_html(msg)
    html = (
        f'<div style="background:{bg};color:{texto};border-left:4px solid {borda};'
        f'padding:12px 16px;border-radius:6px;margin:10px 0;font-size:14px;line-height:1.6;">'
        f'<span style="margin-right:8px;">{icone}</span>{msg_html}'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_status_pill(texto: str, tipo: TipoStatus = "ativo") -> str:
    """Retorna HTML de uma pílula de status (para uso inline ou em tabelas)."""
    bg, cor_texto, borda = _STATUS_CONFIG.get(tipo, _STATUS_CONFIG["ativo"])
    return (
        f'<span class="status-pill" style="background:{bg};color:{cor_texto};border-color:{borda};">'
        f"{texto}</span>"
    )


def render_empty_state(
    titulo: str = "Nenhum dado disponível",
    mensagem: str = "Não há registros para exibir com os filtros atuais.",
    icone: str = "📭",
) -> None:
    """Renderiza um placeholder elegante para telas sem dados."""
    html = (
        f'<div class="empty-state">'
        f'<div class="empty-state-icon">{icone}</div>'
        f'<div class="empty-state-title">{titulo}</div>'
        f'<div class="empty-state-msg">{mensagem}</div>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_divider(titulo: str = "") -> None:
    """Divisor corporativo elegante, com texto opcional no centro."""
    if titulo:
        html = (
            f'<div class="corp-divider">'
            f'<div class="corp-divider-line"></div>'
            f'<span class="corp-divider-text">{titulo}</span>'
            f'<div class="corp-divider-line"></div>'
            f"</div>"
        )
    else:
        html = (
            f'<div class="corp-divider">'
            f'<div class="corp-divider-line"></div>'
            f"</div>"
        )
    st.markdown(html, unsafe_allow_html=True)


def render_progress_bar(
    label: str,
    valor: float,
    meta: float,
    unidade: str = "",
    mostrar_meta: bool = True,
) -> None:
    """Renderiza uma barra de progresso corporativa contra uma meta."""
    percentual = (valor / meta * 100) if meta > 0 else 0
    percentual_bar = min(percentual, 100)

    if percentual >= 100:
        cor = COR_SUCESSO
        gradiente = "linear-gradient(90deg, #059669 0%, #10B981 100%)"
    elif percentual >= 70:
        cor = COR_ATENCAO
        gradiente = "linear-gradient(90deg, #F59E0B 0%, #FBBF24 100%)"
    else:
        cor = COR_ALERTA
        gradiente = "linear-gradient(90deg, #DC2626 0%, #EF4444 100%)"

    footer_txt = ""
    if mostrar_meta:
        footer_txt = (
            f'<div class="progress-footer">'
            f"{_fmt_br(valor)}{unidade} de {_fmt_br(meta)}{unidade} · "
            f'<strong style="color:{cor}">{_fmt_br(percentual, 1)}%</strong> da meta'
            f"</div>"
        )

    html = (
        f'<div class="progress-container">'
        f'<div class="progress-header">'
        f'<span class="progress-label">{label}</span>'
        f'<span class="progress-value" style="color:{cor};">{_fmt_br(percentual, 1)}%</span>'
        f"</div>"
        f'<div class="progress-track">'
        f'<div class="progress-fill" style="width:{percentual_bar}%;background:{gradiente};"></div>'
        f"</div>"
        f"{footer_txt}"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# ====================================================
# HEADERS & BRANDING
# ====================================================
def render_section_header(
    titulo: str,
    subtitulo: str = "",
    icone: str = "",
    badge: str = "",
    badge_tipo: TipoBadge = "laranja",
    cor_accent: str = COR_SECUNDARIA,
) -> None:
    """Renderiza um cabeçalho de seção com título, subtítulo, ícone e badge."""
    if not titulo:
        return

    html_icone = (
        f'<span style="margin-right: 10px; font-size: 1.2em; display: inline-flex; align-items: center;">{icone}</span>'
        if icone
        else ""
    )

    html_badge = ""
    if badge:
        _cores_badge = {
            "laranja": ("#FFF7ED", "#C2410C", "#FDBA74"),
            "azul": ("#EFF6FF", "#1D4ED8", "#93C5FD"),
            "verde": ("#ECFDF5", "#047857", "#6EE7B7"),
            "vermelho": ("#FEF2F2", "#B91C1C", "#FCA5A5"),
            "cinza": ("#F8FAFC", "#475569", "#CBD5E1"),
            "roxo": ("#F5F3FF", "#6D28D9", "#C4B5FD"),
        }
        bg, texto, borda = _cores_badge.get(badge_tipo, _cores_badge["laranja"])
        html_badge = (
            f'<span style="background-color: {bg}; color: {texto}; border: 1px solid {borda}; '
            f"padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; "
            f"font-family: {FONTE_TEXTO}; text-transform: uppercase; letter-spacing: 0.5px; "
            f"margin-left: 10px; display: inline-flex; align-items: center; align-self: center; "
            f'line-height: 1.2;">{badge}</span>'
        )

    html_sub = (
        f'<div style="font-family: {FONTE_TITULO}; font-size: 18px; color: {COR_PRIMARIA}; margin-top: 5px; font-weight: bold;">{subtitulo}</div>'
        if subtitulo
        else ""
    )

    html = (
        f'<div style="margin-top: 2.2rem; margin-bottom: 1.6rem; width: 100%;">'
        f'<div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px 0;">'
        f'<h2 style="font-family: {FONTE_TITULO}; font-size: 22px; font-weight: 800; color: {COR_PRIMARIA}; margin: 0; padding: 0; line-height: 1.25; display: flex; align-items: center;">'
        f"{html_icone}{titulo}"
        f"</h2>"
        f"{html_badge}"
        f"</div>"
        f"{html_sub}"
        f'<div style="height: 3px; width: 45px; background: {cor_accent}; border-radius: 2px; margin-top: 10px; margin-bottom: 5px;"></div>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_sidebar_brand(
    empresa: str = "TOTALE",
    segmento: str = "Sistemas & Energia",
    logo_svg: str | None = None,
) -> None:
    """Renderiza logo + nome + segmento da empresa na sidebar."""
    if not logo_svg:
        logo_svg = (
            '<svg width="34" height="34" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.15));">'
            '<circle cx="50" cy="50" r="44" stroke="rgba(1, 40, 105, 0.15)" stroke-width="6"/>'
            '<path d="M50 12 A 38 38 0 0 1 88 50" stroke="#F37C04" stroke-width="10" stroke-linecap="round"/>'
            '<path d="M50 88 A 38 38 0 0 1 12 50" stroke="#012869" stroke-width="8" stroke-linecap="round"/>'
            '<circle cx="50" cy="50" r="10" fill="#F37C04"/>'
            "</svg>"
        )

    html = (
        f'<div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; margin: 8px 10px 12px 10px; border-bottom: 1px solid {SB_BORDA_SUTIL};">'
        f'<div style="flex-shrink: 0; display: flex; align-items: center; justify-content: center;">{logo_svg}</div>'
        f'<div style="display: flex; flex-direction: column; justify-content: center;">'
        f'<span style="font-family: {FONTE_TITULO}; font-size: 20px; font-weight: 800; color: {COR_PRIMARIA}; letter-spacing: 0.8px; line-height: 1;">{empresa}</span>'
        f'<span style="font-family: {FONTE_TEXTO}; font-size: 10px; font-weight: 600; color: {COR_SECUNDARIA}; letter-spacing: 0.8px; text-transform: uppercase; margin-top: 3px; opacity: 0.95;">{segmento}</span>'
        f"</div></div>"
    )
    st.sidebar.markdown(html, unsafe_allow_html=True)


# ====================================================
# COMPONENTES DE INTERFACE DO SIDEBAR (TOTALE UI)
# ====================================================
def aplicar_sidebar_corp() -> None:
    """Injeta a folha de estilo do sidebar após a configuração da página."""
    st.markdown(_get_sidebar_css(), unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def _get_sidebar_css() -> str:
    """Retorna os ajustes específicos do sidebar corporativo claro."""
    return f"""
    <style>
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #F4F6F9 0%, {SB_FUNDO} 100%) !important;
        border-right: 1px solid {SB_BORDA_SUTIL} !important;
        box-shadow: 2px 0 12px rgba(1, 40, 105, 0.06) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
        background: {SB_FUNDO_LINK} !important;
        border: 1px solid {SB_BORDA_SUTIL} !important;
        border-left: 3px solid transparent !important;
        border-radius: 6px !important;
        margin: 3px 10px !important;
        min-height: 36px !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
        background: {SB_FUNDO_LINK_HOVER} !important;
        border-color: #B8C4D3 !important;
        transform: translateX(2px);
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {{
        background: {SB_FUNDO_ATIVO} !important;
        border-left-color: {SB_BORDA_ATIVA} !important;
    }}
    section[data-testid="stSidebar"] .stButton > button {{
        background: {COR_PRIMARIA} !important;
        color: #FFFFFF !important;
        border: 0 !important;
    }}
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background: {COR_SECUNDARIA} !important;
    }}
    /* CORREÇÃO EXPANDER - Remove caracteres fantasmas */
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary::before,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary::after {{
        content: "" !important;
        display: none !important;
    }}
    </style>
    """


def render_sidebar_info(
    user_name: str,
    email: str = "",
    role: str = "",
    avatar: str = "",
) -> None:
    """Gera o bloco identificador de perfil do usuário logado na plataforma."""
    with st.sidebar:
        st.markdown(
            f"""
            <div class="user-profile-box">
                <div class="user-profile-name">{avatar} {user_name}</div>
                {f'<div class="user-profile-email">{role}</div>' if role else ''}
                <div class="user-profile-email">{email}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar_section(title: str) -> None:
    """Cria um título de agrupamento/categoria corporativa textual no menu."""
    with st.sidebar:
        st.markdown(
            f'<p class="sidebar-section-title">{title}</p>',
            unsafe_allow_html=True,
        )


def render_sidebar_status(
    label: str = "Sistema operacional",
    tipo: Literal["success", "warning", "danger", "info"] = "success",
    sistema_ok: Optional[bool] = None,
    mensagem: Optional[str] = None,
    ultima_atualizacao: Optional[datetime] = None,
) -> None:
    """Exibe indicadores de status da aplicação em formato micro-pill brilhante."""
    cores_status = {
        "success": "#10B981",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "info": "#3B82F6",
    }
    if sistema_ok is not None:
        tipo = "success" if sistema_ok else "danger"
    label = mensagem or label
    cor = cores_status.get(tipo, cores_status["success"])
    with st.sidebar:
        st.markdown(
            f"""
            <div class="status-container">
                <div class="status-pill-dot" style="background-color: {cor}; color: {cor};"></div>
                <span>{label}</span>
                {f'<small>{ultima_atualizacao.strftime("%H:%M")}</small>' if ultima_atualizacao else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar_divider() -> None:
    """Gera uma linha horizontal divisória fina ultra sutil alinhada ao tema."""
    with st.sidebar:
        st.markdown(
            f'<hr style="margin: 14px 10px; border: 0; border-top: 1px solid {SB_BORDA_SUTIL};">',
            unsafe_allow_html=True,
        )


def render_sidebar_spacer(height: int = 15) -> None:
    """Cria um bloco espaçador vertical transparente milimétrico."""
    with st.sidebar:
        st.markdown(f'<div style="height: {height}px;"></div>', unsafe_allow_html=True)


def render_sidebar_footer_info(versao: str = "v3.1.0") -> None:
    """Renderiza as informações consolidadas de compliance no rodapé operacional."""
    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
    with st.sidebar:
        render_sidebar_divider()
        st.markdown(
            f"""
            <div style="font-size: 11px; color: {SB_TEXTO_MUTED}; line-height: 1.6; padding: 4px 14px 12px 14px;">
                <div>🕒 {agora} BRT</div>
                <div>🚀 Versão {versao}</div>
                <div style="margin-top: 6px; font-weight: 700; color: {COR_PRIMARIA}; font-size: 10px; letter-spacing: 0.5px; font-family: {FONTE_TITULO};">© TOTALE TECNOLOGIA</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_hora_atual_brt() -> str:
    """Retorna a hora atual no fuso de Sao Paulo."""
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%H:%M:%S")


def get_data_atual_br() -> str:
    """Retorna a data atual no formato brasileiro."""
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y")


def render_sidebar_filtro(
    label: str,
    options: list,
    key: str,
    default: Any = None,
    multi: bool = False,
) -> Any:
    """Abstração otimizada do st.selectbox respeitando a estilização unificada corporativa."""
    with st.sidebar:
        if multi:
            defaults = default if isinstance(default, list) else []
            return st.multiselect(label, options=options, default=defaults, key=key)
        index = options.index(default) if default in options else 0
        return st.selectbox(label, options=options, index=index, key=key)


# ====================================================
# TABELAS HTML CORPORATIVAS (ATUALIZADO)
# ====================================================
def render_table_html(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    max_rows: int = 100,
    height: int = 420,
    fmt: FmtDict | None = None,
    color_rules: ColorMapDict | None = None,
    num_cols: List[str] | None = None,
    max_cols: int = 20,
    linha_total: bool = False,
    # Novos parâmetros para compatibilidade com quebra.py
    condicao_cores: CondicaoCoresConfig | None = None,
    destaque_col: Dict[str, Any] | None = None,
    condicoes_colunas: Dict[str, Any] | None = None,
    linha_destaque: Dict[str, Any] | None = None,
    hide_index: bool = True,
) -> None:
    """
    Renderiza uma tabela HTML corporativa com formatação e cores condicionais.

    Parâmetros:
    - df: DataFrame pandas
    - titulo: Título opcional da tabela
    - icone: Ícone para o título
    - max_rows: Máximo de linhas a exibir
    - height: Altura máxima do container com scroll
    - fmt: Dicionário de formatação por coluna
    - color_rules: Regras de cores antigas (legado)
    - num_cols: Colunas numéricas para totais
    - max_cols: Máximo de colunas
    - linha_total: Se True, adiciona linha de total
    - condicao_cores: Config para cores condicionais por meta (acima/perto/abaixo)
    - destaque_col: Config para destacar coluna específica (ex: Quebra Atual)
    - condicoes_colunas: Config de cores por coluna (para matriz)
    - linha_destaque: Config para destacar linha específica (ex: TOTAL GERAL)
    - hide_index: Se True, esconde o índice
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        render_empty_state(
            "Sem dados na tabela", "Ajuste os filtros para visualizar registros."
        )
        return

    cols = list(df.columns[:max_cols])
    df_show = df.loc[:, cols].head(max_rows).copy()

    if titulo:
        st.markdown(
            f'<div style="font-weight:700;font-size:16px;color:{COR_PRIMARIA};margin-bottom:8px;">{icone} {titulo}</div>',
            unsafe_allow_html=True,
        )

    num_set = set(
        num_cols or [c for c in _detectar_colunas_numericas(df_show) if c in cols]
    )
    df_show = df_show.fillna("—")

    # Aplicar formatação
    display = pd.DataFrame(index=df_show.index)
    for c in cols:
        s = df_show[c]
        if fmt and c in fmt and fmt[c] is not None:
            f = fmt[c]
            if callable(f):
                display[c] = s.map(lambda v, _f=f: _f(v) if v != "—" else "—")
            elif isinstance(f, str):
                display[c] = s.map(lambda v, _f=f: _f.format(v) if v != "—" else "—")
        else:
            display[c] = s

    # Gerar linhas HTML com estilos condicionais
    html_rows = []
    for idx, row in display.iterrows():
        cells = []
        is_linha_destaque = False

        # Verificar se é linha de destaque (ex: TOTAL GERAL)
        if linha_destaque:
            col_check = linha_destaque.get("coluna")
            val_check = linha_destaque.get("valor")
            if (
                col_check
                and val_check
                and str(row.get(col_check, "")).upper() == str(val_check).upper()
            ):
                is_linha_destaque = True

        for c in cols:
            val = row[c]
            style_parts = []

            # Estilo para linha de destaque (TOTAL GERAL)
            if is_linha_destaque:
                if c == col_check:
                    style_parts.append(
                        "background:linear-gradient(90deg,#012869 0%,#1E40AF 100%);color:white;font-weight:800;text-align:left;padding-left:16px;"
                    )
                else:
                    style_parts.append(
                        "background-color:#F8FAFC;font-weight:700;text-align:left;padding-left:16px;border-right:2px solid #E2E8F0;"
                    )
            # Destaque de coluna específica (ex: Quebra Atual)
            elif destaque_col and c == destaque_col.get("coluna"):
                if val != "—":
                    try:
                        float(val)
                        style_parts.append(
                            f"background-color:{destaque_col.get('bg', '#1E293B')};color:{destaque_col.get('text', '#FFFFFF')};font-weight:{'800' if destaque_col.get('bold', True) else '500'};"
                        )
                    except (ValueError, TypeError):
                        pass

            # Cores condicionais por meta (condicao_cores)
            elif condicao_cores and c == condicao_cores.get("coluna"):
                try:
                    v = float(val) if val != "—" else 0
                    meta = condicao_cores.get("meta", 0.20)
                    if v > meta:
                        cfg = condicao_cores.get("acima_meta", {})
                        style_parts.append(
                            f"background-color:{cfg.get('bg', '#FEE2E2')};color:{cfg.get('text', '#991B1B')};font-weight:{'800' if cfg.get('bold', True) else '500'};"
                        )
                    elif v > meta * 0.85:
                        cfg = condicao_cores.get("perto_meta", {})
                        style_parts.append(
                            f"background-color:{cfg.get('bg', '#FEF9C3')};color:{cfg.get('text', '#854D0E')};font-weight:{'800' if cfg.get('bold', True) else '500'};"
                        )
                    else:
                        cfg = condicao_cores.get("abaixo_meta", {})
                        style_parts.append(
                            f"background-color:{cfg.get('bg', '#DCFCE7')};color:{cfg.get('text', '#166534')};font-weight:{'800' if cfg.get('bold', True) else '500'};"
                        )
                except (ValueError, TypeError):
                    pass

            # Cores condicionais por coluna (condicoes_colunas - para matriz)
            elif condicoes_colunas and c in condicoes_colunas:
                try:
                    v = float(val) if val != "—" else 0
                    cfg = condicoes_colunas[c]
                    meta = cfg.get("meta", 0.20)
                    if v > meta:
                        acima = cfg.get("acima_meta", {})
                        style_parts.append(
                            f"background-color:{acima.get('bg', '#FEE2E2')};color:{acima.get('text', '#991B1B')};font-weight:{'800' if acima.get('bold', True) else '500'};text-align:center;"
                        )
                    else:
                        abaixo = cfg.get("abaixo_meta", {})
                        style_parts.append(
                            f"background-color:{abaixo.get('bg', '#D1FAE5')};color:{abaixo.get('text', '#065F46')};font-weight:{'800' if abaixo.get('bold', True) else '500'};text-align:center;"
                        )
                except (ValueError, TypeError):
                    pass

            # Regras de cores legadas (color_rules)
            elif color_rules and c in color_rules:
                for rule, color in color_rules[c]:
                    if rule(val):
                        style_parts.append(f"color:{color};font-weight:600;")
                        break

            # Alinhamento para colunas numéricas
            if c in num_set and val != "—":
                style_parts.append(
                    "text-align:right;font-variant-numeric:tabular-nums;"
                )

            style = "".join(style_parts)
            cells.append(f'<td style="{style}">{val}</td>')

        html_rows.append(f'<tr>{"".join(cells)}</tr>')

    # Linha de total
    if linha_total and not df_show.empty:
        total_cells = []
        for c in cols:
            if c in num_set:
                total = df_show[c].sum()
                total_cells.append(f'<td class="num">{_fmt_br(total)}</td>')
            else:
                total_cells.append("<td><strong>TOTAL</strong></td>")
        html_rows.append(f'<tr class="total-row">{"".join(total_cells)}</tr>')

    headers_html = "".join(f"<th>{c}</th>" for c in cols)
    html = (
        f'<div class="corp-table-wrap" style="max-height:{height}px;overflow-y:auto;">'
        f'<table class="corp-table">'
        f"<thead><tr>{headers_html}</tr></thead>"
        f'<tbody>{"".join(html_rows)}</tbody>'
        f"</table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)