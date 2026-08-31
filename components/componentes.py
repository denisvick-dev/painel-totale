"""
componentes.py
==============
Módulo central de estilos, fontes, componentes reutilizáveis e
visualizações gráficas padronizadas para todo o projeto Streamlit.

Uso em qualquer página:
    from componentes import (
        aplicar_estilo,
        render_kpi, render_kpi_sm, render_metric_delta,
        render_insight, render_status_pill, render_empty_state,
        render_section_header, render_divider, render_progress_bar,
        render_sidebar_brand, render_table_html,
        render_grafico_linhas, render_grafico_barras,
        render_grafico_rosca, render_grafico_gauge, render_grafico_funnel,
        render_hero_totale_1, render_hero_totale_2
    )
    aplicar_estilo()
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Literal, Union

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
FmtDict = dict[str, Union[CellFormatter, None]]

ColorRule = tuple[Callable[[Any], bool], str]
ColorMapDict = dict[str, list[ColorRule]]


# ====================================================
# TIPOGRAFIA & CORES CORPORATIVAS
# ====================================================
FONTE_TITULO = "'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif"
FONTE_TEXTO = "'IBM Plex Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONTE_CODIGO = "'IBM Plex Mono', Consolas, 'Courier New', monospace"

_GOOGLE_FONTS_URLS = (
    "https://fonts.googleapis.com/icon?family=Material+Icons",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap",
    "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap",
)

# Paleta Corporativa Totale
COR_PRIMARIA = "#012869"  # Deep Midnight Navy
COR_SECUNDARIA = "#F37C04"  # Solar Orange
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

_TEMA_CORES: dict[str, str] = {
    "azul": COR_PRIMARIA,
    "verde": COR_SUCESSO,
    "vermelho": COR_ALERTA,
    "laranja": COR_SECUNDARIA,
    "cinza": COR_NEUTRO,
    "roxo": COR_ROXO,
}

_INSIGHT_CONFIG: dict[str, tuple[str, str, str, str]] = {
    "ok": ("#D1FAE5", "#065F46", "#059669", "✅"),
    "info": ("#DBEAFE", "#1E40AF", "#3B82F6", "ℹ️"),
    "alerta": ("#FEF3C7", "#92400E", "#F59E0B", "⚠️"),
    "critico": ("#FEE2E2", "#991B1B", "#DC2626", "🚨"),
    "acao": ("#EDE9FE", "#5B21B6", "#8B5CF6", "🎯"),
}

_STATUS_CONFIG: dict[str, tuple[str, str, str]] = {
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
    "#EC4899",  # Rosa
    "#14B8A6",  # Teal
    "#F59E0B",  # Amarelo Âmbar
    "#6366F1",  # Índigo
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
    """Injeta as fontes Google no <head> pai do iframe do Streamlit."""
    urls_js = ", ".join(f'"{u}"' for u in _GOOGLE_FONTS_URLS)
    components.html(
        f"""<script>
        (function () {{
            const urls = [{urls_js}];
            let parentDoc;
            try {{ parentDoc = window.parent.document; }} catch (e) {{ return; }}
            const head = parentDoc.head;
            const existentes = Array.from(head.querySelectorAll('link[rel="stylesheet"]')).map(l => l.href);
            urls.forEach(href => {{
                if (existentes.includes(href)) return;
                const link = parentDoc.createElement('link');
                link.rel = 'stylesheet'; link.href = href;
                head.appendChild(link);
            }});
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
    /* ═══ DUPLA GARANTIA DE FONTES ═══ */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

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

    /* ═══ CORREÇÃO DE ÍCONES MATERIAL ═══ */
    [data-testid="stIconMaterial"],
    [data-testid="stSidebarCollapseButton"] *,
    [data-testid="stSidebarHeader"] *,
    .material-icons, 
    .material-symbols-rounded, 
    .material-symbols-outlined {{
        font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
        font-weight: normal !important;
        font-style: normal !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-smoothing: antialiased !important;
    }}

    /* ═══ LAYOUT CORE ═══ */
    .main .block-container {{
        padding-top: 1rem;
        max-width: 1400px;
    }}

    /* ═══════════════════════════════════════════════════
       SIDEBAR — TOPO LARANJA + DEEP NAVY CORPORATIVO
       ═══════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {{
        background: linear-gradient(
            180deg,
            #F37C04 0%,
            #E86B03 7%,
            #0B1E3D 15%,
            #012869 45%,
            #001135 100%
        ) !important;
        border-right: 1px solid rgba(243, 124, 4, 0.3) !important;
        box-shadow: 4px 0 20px rgba(0, 0, 0, 0.25) !important;
    }}

    section[data-testid="stSidebar"] > div:first-child,
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
        background: transparent !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
        border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
        padding: 8px 12px !important;
    }}

    /* Botão Collapse */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {{
        background: transparent !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {{
        color: #FFFFFF !important;
        background: rgba(0, 0, 0, 0.2) !important;
        border-radius: 6px !important;
        border: none !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {{
        background: rgba(0, 0, 0, 0.4) !important;
    }}

    /* Títulos H1-H4 personalizados no sidebar */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {{
        color: #FFB86B !important;
        font-family: var(--font-titulo) !important;
        font-weight: 800 !important;
        font-size: 11px !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        border-bottom: 1px solid rgba(243, 124, 4, 0.35) !important;
        padding-bottom: 6px !important;
        margin-top: 18px !important;
        margin-bottom: 10px !important;
        background: transparent !important;
    }}

    /* Cabeçalhos NATIVOS de agrupamento de páginas no Menu */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] span[data-testid="stSidebarNavSeparator"] ~ span,
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li div {{
        color: #E2E8F0 !important;
        font-family: var(--font-titulo) !important;
        font-weight: 800 !important;
        font-size: 12px !important;
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
        background: transparent !important;
        border: none !important;
        margin-top: 16px !important;
        padding-left: 14px !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
        padding-top: 0 !important;
    }}

    /* Botões de páginas (Cards flutuantes) */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a {{
        background-color: #06152F !important;
        border: 1px solid rgba(255, 255, 255, 0.03) !important;
        border-radius: 6px !important;
        margin: 4px 14px !important;
        padding: 10px 12px !important;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.15) !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a:hover {{
        background-color: #0A224A !important;
        border-color: rgba(243, 124, 4, 0.4) !important;
        transform: translateX(3px);
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a span {{
        color: #F8FAFC !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        background: transparent !important;
    }}

    /* Página Ativa - destaque laranja */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a[aria-current="page"] {{
        background-color: #0A224A !important;
        border-left: 4px solid #F37C04 !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a[aria-current="page"] span {{
        color: #FFFFFF !important;
        font-weight: 800 !important;
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
        color: #F1F5F9 !important;
        font-weight: 500 !important;
        background: transparent !important;
    }}

    /* Expanders */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {{
        background-color: rgba(0, 17, 53, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 8px !important;
        margin-bottom: 12px !important;
        overflow: hidden !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        background-color: rgba(255, 255, 255, 0.08) !important;
        padding: 10px 14px !important;
        transition: background-color 0.2s ease;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
        background-color: rgba(255, 255, 255, 0.15) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {{
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
        font-weight: 700 !important;
        font-family: var(--font-titulo) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpanderDetails"] {{
        padding: 16px 14px !important;
        background: transparent !important;
    }}

    /* Sliders */
    section[data-testid="stSidebar"] [data-testid="stSlider"] {{
        padding-top: 8px !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSlider"] [data-testid="stThumbValue"],
    section[data-testid="stSidebar"] [data-testid="stSlider"] [data-testid="stTickBar"] {{
        color: #FFFFFF !important;
        font-family: var(--font-codigo) !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }}

    /* Checkboxes */
    section[data-testid="stSidebar"] [data-testid="stCheckbox"] label span {{
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }}

    /* Divisores */
    section[data-testid="stSidebar"] hr {{
        background: linear-gradient(90deg, transparent 0%, rgba(243, 124, 4, 0.5) 50%, transparent 100%) !important;
        height: 1px !important;
        border: none !important;
        margin: 16px 0 !important;
    }}

    /* Botões primários no sidebar */
    section[data-testid="stSidebar"] .stButton button {{
        background: linear-gradient(180deg, #FF9029 0%, #F37C04 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.2) !important;
        font-weight: 700 !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.3) !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(243, 124, 4, 0.35) !important;
    }}

    /* Inputs e Selects */
    section[data-testid="stSidebar"] input, 
    section[data-testid="stSidebar"] select,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="base-input"] {{
        background-color: rgba(0, 0, 0, 0.25) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 6px !important;
    }}
    section[data-testid="stSidebar"] input:focus,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within {{
        border-color: #F37C04 !important;
        background-color: rgba(0, 0, 0, 0.4) !important;
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
    .hero-t1-title {{ margin: 0; font-size: 2.8rem; font-weight: 700; letter-spacing: -0.5px; }}
    .hero-t1-sub {{ margin: 0.75rem 0 0 0; font-size: 1.25rem; font-weight: 400; opacity: 0.95; }}

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

    /* KPI com Delta (Variação) */
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

    /* KPI Small */
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
       ═══════════════════════════════════════════════════ */
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

    /* ═══════════════════════════════════════════════════
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

    if not st.session_state.get("_fontes_ok"):
        _injetar_fontes_no_head_pai()
        st.session_state["_fontes_ok"] = True

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


def _detectar_colunas_numericas(df: pd.DataFrame) -> list[str]:
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
    """
    Renderiza um KPI com indicador de variação (Delta).

    Args:
        delta: Valor da variação. Positivo = alta, Negativo = queda.
        inverter_cor: Se True, delta positivo vira vermelho e negativo vira verde
                     (útil para métricas onde "menos é melhor", ex: reclamações).
    """
    cor = _resolver_cor_tema(tema)
    renderer = col.markdown if hasattr(col, "markdown") else st.markdown

    # Determina tendência automaticamente se não fornecida
    if tendencia is None:
        if delta > 0.01:
            tendencia = "up"
        elif delta < -0.01:
            tendencia = "down"
        else:
            tendencia = "flat"

    # Cores e ícones baseados em tendência
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
    """
    Retorna HTML de uma pílula de status (para uso inline ou em tabelas).
    Não renderiza diretamente — retorna string HTML.
    """
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
    """
    Renderiza uma barra de progresso corporativa contra uma meta.
    Cor dinâmica: verde (≥100%), amarelo (70-99%), vermelho (<70%).
    """
    percentual = (valor / meta * 100) if meta > 0 else 0
    percentual_bar = min(percentual, 100)

    if percentual >= 100:
        cor = COR_SUCESSO
        gradiente = f"linear-gradient(90deg, #059669 0%, #10B981 100%)"
    elif percentual >= 70:
        cor = COR_ATENCAO
        gradiente = f"linear-gradient(90deg, #F59E0B 0%, #FBBF24 100%)"
    else:
        cor = COR_ALERTA
        gradiente = f"linear-gradient(90deg, #DC2626 0%, #EF4444 100%)"

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
        f'<div style="font-family: {FONTE_TEXTO}; font-size: 14px; color: {COR_TEXTO_3}; margin-top: 5px; font-weight: 400;">{subtitulo}</div>'
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
            '<circle cx="50" cy="50" r="44" stroke="rgba(255, 255, 255, 0.15)" stroke-width="6"/>'
            '<path d="M50 12 A 38 38 0 0 1 88 50" stroke="#F37C04" stroke-width="10" stroke-linecap="round"/>'
            '<path d="M50 88 A 38 38 0 0 1 12 50" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>'
            '<circle cx="50" cy="50" r="10" fill="#F37C04"/>'
            "</svg>"
        )

    html = (
        f'<div style="display: flex; align-items: center; gap: 12px; padding: 8px 4px 16px 4px; margin-bottom: 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.15);">'
        f'<div style="flex-shrink: 0; display: flex; align-items: center; justify-content: center;">{logo_svg}</div>'
        f'<div style="display: flex; flex-direction: column; justify-content: center;">'
        f'<span style="font-family: {FONTE_TITULO}; font-size: 20px; font-weight: 800; color: #FFFFFF; letter-spacing: 0.8px; line-height: 1;">{empresa}</span>'
        f'<span style="font-family: {FONTE_TEXTO}; font-size: 10px; font-weight: 600; color: #FFB86B; letter-spacing: 0.8px; text-transform: uppercase; margin-top: 3px; opacity: 0.95;">{segmento}</span>'
        f"</div></div>"
    )
    st.sidebar.markdown(html, unsafe_allow_html=True)


# ====================================================
# TABELAS HTML CORPORATIVAS
# ====================================================
def render_table_html(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    max_rows: int = 100,
    height: int = 420,
    fmt: FmtDict | None = None,
    color_rules: ColorMapDict | None = None,
    num_cols: list[str] | None = None,
    max_cols: int = 20,
    linha_total: bool = False,
) -> None:
    """
    Renderiza uma tabela HTML corporativa com formatação, cores e destaque de totais.

    Args:
        linha_total: Se True, destaca a última linha como total.
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
            display[c] = s.astype(str)

    style_maps: dict[str, pd.Series] = {}
    if color_rules:
        for c, regras in color_rules.items():
            if c not in df_show.columns:
                continue
            styles = pd.Series("", index=df_show.index, dtype=str)
            raw = df.loc[df_show.index, c] if c in df.columns else df_show[c]
            for pred, css_str in regras:
                try:
                    mask = raw.map(
                        lambda v, _p=pred: bool(_p(v)) if v != "—" else False
                    )
                    styles = styles.where(~mask, css_str)
                except Exception:
                    continue
            style_maps[c] = styles

    header = "".join(f"<th>{c}</th>" for c in cols)
    rows_html: list[str] = []
    values = display.to_numpy()
    total_idx = len(values) - 1 if linha_total else -1

    for i in range(values.shape[0]):
        tds: list[str] = []
        for j, c in enumerate(cols):
            cls_str = ' class="num"' if c in num_set else ""
            stl_str = (
                f' style="{style_maps[c].iloc[i]}"'
                if c in style_maps and style_maps[c].iloc[i]
                else ""
            )
            val = (
                str(values[i, j])
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            tds.append(f"<td{cls_str}{stl_str}>{val}</td>")

        tr_class = ' class="total-row"' if i == total_idx else ""
        rows_html.append(f"<tr{tr_class}>{''.join(tds)}</tr>")

    html_tabela = (
        f'<div class="corp-table-wrap" style="max-height:{int(height)}px;">'
        f'<table class="corp-table">'
        f"<thead><tr>{header}</tr></thead>"
        f'<tbody>{"".join(rows_html)}</tbody>'
        f"</table></div>"
    )
    st.markdown(html_tabela, unsafe_allow_html=True)

    if len(df) > max_rows or len(df.columns) > max_cols:
        st.caption(
            f"Exibindo limite de visualização: {min(len(df), max_rows)} linhas x {min(len(df.columns), max_cols)} colunas."
        )


# ====================================================
# GRÁFICOS PLOTLY PADRONIZADOS
# ====================================================
def _obter_config_interacao() -> dict[str, Any]:
    """Retorna configuração limpa para gráficos Plotly."""
    return {
        "displayModeBar": "hover",
        "displaylogo": False,
        "modeBarButtonsToRemove": [
            "select2d",
            "lasso2d",
            "zoomIn2d",
            "zoomOut2d",
            "autoScale2d",
            "resetScale2d",
            "toggleSpikelines",
        ],
        "responsive": True,
    }


def _titulo_plotly(titulo: str, subtitulo: str = "") -> str:
    """Formata título com subtítulo para gráficos."""
    if subtitulo:
        return f"<b>{titulo}</b><br><span style='font-size:12px; font-weight:normal; color:{COR_TEXTO_3}'>{subtitulo}</span>"
    return f"<b>{titulo}</b>"


def render_grafico_linhas(
    df: pd.DataFrame,
    x: str,
    y: list[str] | str,
    titulo: str = "",
    subtitulo: str = "",
    altura: int = 350,
    area: bool = False,
    stacked: bool = False,
) -> None:
    """Renderiza gráfico de linhas ou áreas suavizadas (spline)."""
    if df is None or df.empty:
        render_empty_state(
            "Sem dados para o gráfico", "Ajuste os filtros para visualizar."
        )
        return

    colunas_y = [y] if isinstance(y, str) else y
    fig = go.Figure()

    for i, col in enumerate(colunas_y):
        cor_manual = _PLOTLY_COLORWAY[i % len(_PLOTLY_COLORWAY)]
        fill_mode = "tonexty" if area else None
        if area and i == 0 and not stacked:
            fill_mode = "tozeroy"

        fig.add_trace(
            go.Scatter(
                x=df[x],
                y=df[col],
                name=col,
                mode="lines+markers",
                line=dict(width=3, shape="spline", color=cor_manual),
                marker=dict(size=6),
                fill=fill_mode,
                stackgroup="one" if (area and stacked) else None,
                hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y}}<extra></extra>",
            )
        )

    layout_args = {"height": altura, "hovermode": "x unified"}
    if titulo:
        layout_args["title"] = _titulo_plotly(titulo, subtitulo)

    fig.update_layout(**layout_args)
    st.plotly_chart(fig, use_container_width=True, config=_obter_config_interacao())


def render_grafico_barras(
    df: pd.DataFrame,
    x: str,
    y: list[str] | str,
    titulo: str = "",
    subtitulo: str = "",
    horizontal: bool = False,
    empilhado: bool = False,
    altura: int = 350,
) -> None:
    """Renderiza gráfico de barras (vertical/horizontal, agrupado/empilhado)."""
    if df is None or df.empty:
        render_empty_state(
            "Sem dados para o gráfico", "Ajuste os filtros para visualizar."
        )
        return

    colunas_y = [y] if isinstance(y, str) else y
    fig = go.Figure()

    for i, col in enumerate(colunas_y):
        cor_manual = _PLOTLY_COLORWAY[i % len(_PLOTLY_COLORWAY)]
        if horizontal:
            fig.add_trace(
                go.Bar(
                    y=df[x],
                    x=df[col],
                    name=col,
                    orientation="h",
                    marker=dict(color=cor_manual, line=dict(color="white", width=1)),
                    hovertemplate=f"<b>%{{y}}</b><br>{col}: %{{x}}<extra></extra>",
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=df[x],
                    y=df[col],
                    name=col,
                    marker=dict(color=cor_manual, line=dict(color="white", width=1)),
                    hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y}}<extra></extra>",
                )
            )

    layout_args = {
        "height": altura,
        "barmode": "stack" if empilhado else "group",
        "bargap": 0.18,
        "bargroupgap": 0.04,
    }
    if titulo:
        layout_args["title"] = _titulo_plotly(titulo, subtitulo)

    fig.update_layout(**layout_args)
    if horizontal:
        fig.update_layout(
            xaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
            yaxis=dict(showgrid=False),
        )

    st.plotly_chart(fig, use_container_width=True, config=_obter_config_interacao())


def render_grafico_rosca(
    df: pd.DataFrame,
    valores: str,
    nomes: str,
    titulo: str = "",
    subtitulo: str = "",
    furo: float = 0.6,
    altura: int = 330,
) -> None:
    """Renderiza gráfico de rosca com totalizador no centro."""
    if df is None or df.empty:
        render_empty_state(
            "Sem dados para o gráfico", "Ajuste os filtros para visualizar."
        )
        return

    valor_total = df[valores].sum()
    if valor_total >= 1_000_000:
        texto_centro = f"Total<br><b>{valor_total/1_000_000:.1f}M</b>"
    elif valor_total >= 1_000:
        texto_centro = f"Total<br><b>{valor_total/1_000:.1f}k</b>"
    else:
        texto_centro = f"Total<br><b>{valor_total:,.0f}</b>"

    fig = go.Figure(
        data=[
            go.Pie(
                labels=df[nomes],
                values=df[valores],
                hole=furo,
                marker=dict(line=dict(color="white", width=2)),
                textinfo="percent",
                textposition="inside",
                direction="clockwise",
                sort=True,
                hovertemplate=f"<b>%{{label}}</b><br>{valores}: %{{value}}<br>Proporção: %{{percent}}<extra></extra>",
            )
        ]
    )

    layout_args = {
        "height": altura,
        "annotations": [
            dict(
                text=texto_centro,
                x=0.5,
                y=0.5,
                font=dict(family=FONTE_TITULO, size=15, color=COR_TEXTO),
                showarrow=False,
            )
        ],
        "legend": dict(
            orientation="v", yanchor="middle", y=0.5, xanchor="left", x=0.85
        ),
        "margin": dict(l=20, r=80, t=50, b=20),
    }
    if titulo:
        layout_args["title"] = _titulo_plotly(titulo, subtitulo)

    fig.update_layout(**layout_args)
    st.plotly_chart(fig, use_container_width=True, config=_obter_config_interacao())


def render_grafico_gauge(
    valor: float,
    meta: float,
    titulo: str = "",
    subtitulo: str = "",
    sufixo: str = "%",
    altura: int = 280,
) -> None:
    """Renderiza velocímetro (gauge) para acompanhamento de meta."""
    percentual = (valor / meta * 100) if meta > 0 else 0

    if percentual >= 100:
        cor = COR_SUCESSO
    elif percentual >= 70:
        cor = COR_ATENCAO
    else:
        cor = COR_ALERTA

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=valor,
            number={
                "suffix": sufixo,
                "font": {"family": FONTE_TITULO, "size": 32, "color": cor},
            },
            delta={
                "reference": meta,
                "increasing": {"color": COR_SUCESSO},
                "decreasing": {"color": COR_ALERTA},
            },
            gauge={
                "axis": {
                    "range": [0, meta * 1.3],
                    "tickfont": {"family": FONTE_TEXTO, "size": 11},
                },
                "bar": {"color": cor, "thickness": 0.7},
                "bgcolor": "#F8FAFC",
                "borderwidth": 1,
                "bordercolor": COR_BORDA,
                "steps": [
                    {"range": [0, meta * 0.7], "color": "#FEE2E2"},
                    {"range": [meta * 0.7, meta], "color": "#FEF3C7"},
                    {"range": [meta, meta * 1.3], "color": "#D1FAE5"},
                ],
                "threshold": {
                    "line": {"color": COR_PRIMARIA, "width": 3},
                    "thickness": 0.85,
                    "value": meta,
                },
            },
            domain={"x": [0, 1], "y": [0, 1]},
        )
    )

    layout_args = {"height": altura, "margin": dict(l=20, r=20, t=60, b=20)}
    if titulo:
        layout_args["title"] = _titulo_plotly(titulo, subtitulo)

    fig.update_layout(**layout_args)
    st.plotly_chart(fig, use_container_width=True, config=_obter_config_interacao())


def render_grafico_funnel(
    df: pd.DataFrame,
    valores: str,
    nomes: str,
    titulo: str = "",
    subtitulo: str = "",
    altura: int = 350,
) -> None:
    """Renderiza gráfico de funil (útil para análise de conversão)."""
    if df is None or df.empty:
        render_empty_state(
            "Sem dados para o gráfico", "Ajuste os filtros para visualizar."
        )
        return

    fig = go.Figure(
        go.Funnel(
            y=df[nomes],
            x=df[valores],
            textinfo="value+percent initial",
            textposition="inside",
            textfont=dict(family=FONTE_TEXTO, size=13, color="white"),
            marker=dict(
                color=_PLOTLY_COLORWAY[: len(df)],
                line=dict(width=2, color="white"),
            ),
            connector={"line": {"color": COR_BORDA, "width": 2, "dash": "dot"}},
            hovertemplate=f"<b>%{{y}}</b><br>{valores}: %{{x}}<extra></extra>",
        )
    )

    layout_args = {"height": altura, "margin": dict(l=40, r=40, t=60, b=20)}
    if titulo:
        layout_args["title"] = _titulo_plotly(titulo, subtitulo)

    fig.update_layout(**layout_args)
    st.plotly_chart(fig, use_container_width=True, config=_obter_config_interacao())