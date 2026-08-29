"""
componentes.py
==============
Módulo central de estilos, fontes e componentes reutilizáveis
para todo o projeto Streamlit.

Uso em qualquer página:
    from componentes import (
        aplicar_estilo,
        render_kpi,
        render_kpi_sm,
        render_insight,
        render_section_header,
        render_sidebar_brand
    )
    aplicar_estilo()

Características unificadas:
- Fonte corporativa global (Plus Jakarta Sans + IBM Plex Sans)
- Restauração estrita dos ícones do Streamlit (impede vazamento de 'keyboard_double')
- Tema Plotly global corporativo
- Sidebar TOTALE: Topo Laranja Solar Corporativo + Deep Midnight Navy
- Heros TOTALE, Tabelas HTML Nativas e Cards KPI (Standard e Compacto/SM)
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
TemaKPI = Literal["azul", "verde", "vermelho", "laranja", "cinza"]
TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]

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

COR_PRIMARIA = "#012869"
COR_SECUNDARIA = "#F37C04"
COR_SUCESSO = "#059669"
COR_ALERTA = "#DC2626"
COR_NEUTRO = "#64748B"
COR_TEXTO = "#1F2937"
COR_TEXTO_2 = "#374151"
COR_TEXTO_3 = "#6B7280"
COR_BORDA = "#E2E8F0"
COR_FUNDO = "#F8FAFC"

_TEMA_CORES: dict[str, str] = {
    "azul": COR_PRIMARIA,
    "verde": COR_SUCESSO,
    "vermelho": COR_ALERTA,
    "laranja": COR_SECUNDARIA,
    "cinza": COR_NEUTRO,
}

_INSIGHT_CONFIG: dict[str, tuple[str, str, str, str]] = {
    "ok": ("#D1FAE5", "#065F46", "#059669", "✅"),
    "info": ("#DBEAFE", "#1E40AF", "#3B82F6", "ℹ️"),
    "alerta": ("#FEF3C7", "#92400E", "#F59E0B", "⚠️"),
    "critico": ("#FEE2E2", "#991B1B", "#DC2626", "🚨"),
    "acao": ("#EDE9FE", "#5B21B6", "#8B5CF6", "🎯"),
}

_PLOTLY_COLORWAY = [
    COR_PRIMARIA,
    COR_SECUNDARIA,
    COR_SUCESSO,
    COR_ALERTA,
    "#8B5CF6",
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
    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONTE_TEXTO, size=13, color=COR_TEXTO),
            title=dict(
                font=dict(family=FONTE_TITULO, size=20, color=COR_TEXTO),
                x=0.02,
                xanchor="left",
            ),
            legend=dict(font=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2)),
            xaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
                gridcolor="#F1F5F9",
                zerolinecolor="#CBD5E1",
            ),
            yaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
                gridcolor="#F1F5F9",
                zerolinecolor="#CBD5E1",
            ),
            hoverlabel=dict(
                font=dict(family=FONTE_TEXTO, size=13),
                bgcolor="white",
                bordercolor=COR_BORDA,
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
            colorway=_PLOTLY_COLORWAY,
        )
    )
    pio.templates["corporativo"] = template
    pio.templates.default = "plotly_white+corporativo"


# ====================================================
# INJEÇÃO DE DEPENDÊNCIAS (CSS & FONTES)
# ====================================================
def _injetar_fontes_no_head_pai() -> None:
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
    links_html = "\n".join(
        f'<link rel="stylesheet" href="{url}">' for url in _GOOGLE_FONTS_URLS
    )

    return f"""{links_html}
    <style>
    /* ═══ VARIÁVEIS ═══ */
    :root {{
        --font-titulo: {FONTE_TITULO};
        --font-texto: {FONTE_TEXTO};
        --font-codigo: {FONTE_CODIGO};
        --cor-primaria: {COR_PRIMARIA};
        --cor-secundaria: {COR_SECUNDARIA};
        --cor-borda: {COR_BORDA};
    }}

    /* ═══ BASE & TYPOGRAPHY (EXCETO ÍCONES) ═══ */
    html, body, p, label, li, a, button, input, select, textarea {{
        font-family: var(--font-texto);
    }}
    h1, h2, h3, h4, h5, h6, .hero-title, .section-title, .kpi-value, [data-testid="stMetricValue"] {{
        font-family: var(--font-titulo) !important;
        font-weight: 700;
        letter-spacing: -0.3px;
    }}
    code, pre, kbd, samp {{
        font-family: var(--font-codigo) !important;
    }}

    /* ═══ CORREÇÃO CRÍTICA DE ÍCONES (IMPEDE VAZAMENTO DE TEXTO 'keyboard_double') ═══ */
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

    /* Topo do Sidebar (Logo TOTALE e Cabeçalho) */
    section[data-testid="stSidebar"] > div:first-child {{
        background: transparent !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
        background: transparent !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
        padding: 8px 12px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
    }}

    /* Botão de recolher no topo */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {{
        background: transparent !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {{
        color: #FFFFFF !important;
        background: rgba(0, 0, 0, 0.2) !important;
        border-radius: 6px !important;
        border: none !important;
        width: 32px !important;
        height: 32px !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {{
        background: rgba(0, 0, 0, 0.4) !important;
        color: #FFFFFF !important;
    }}

    /* ELIMINAÇÃO DE FUNDO BRANCO EM TÍTULOS E SUBTÍTULOS DO SIDEBAR */
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] .sidebar-menu-header {{
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
    }}

    /* Títulos de Seção ("MENU PRINCIPAL", "CENTRAL DE PERFORMANCE") */
    section[data-testid="stSidebar"] [data-testid="stSidebarNavHeader"],
    section[data-testid="stSidebar"] .sidebar-menu-header,
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
        text-shadow: 0 1px 2px rgba(0,0,0,0.4) !important;
    }}

    /* Textos normais no menu */
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] label {{
        color: #E2E8F0 !important;
        font-weight: 500 !important;
    }}

    /* Divisor */
    section[data-testid="stSidebar"] hr {{
        background: linear-gradient(90deg, transparent 0%, rgba(243, 124, 4, 0.5) 50%, transparent 100%) !important;
        height: 1px !important;
        border: none !important;
        margin: 16px 0 !important;
    }}

    /* Items de Navegação */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
        background: rgba(0, 17, 53, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-left: 3px solid transparent !important;
        border-radius: 6px !important;
        margin: 4px 8px !important;
        padding: 8px 12px !important;
        transition: all 0.2s ease !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
        background: rgba(243, 124, 4, 0.15) !important;
        border-color: rgba(243, 124, 4, 0.3) !important;
        border-left-color: #F37C04 !important;
        transform: translateX(3px);
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span {{
        color: #F1F5F9 !important;
        font-weight: 600 !important;
    }}

    /* Item Ativo no Menu */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {{
        background: linear-gradient(90deg, rgba(243, 124, 4, 0.25) 0%, rgba(243, 124, 4, 0.08) 100%) !important;
        border: 1px solid rgba(243, 124, 4, 0.4) !important;
        border-left: 4px solid #F37C04 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] span {{
        color: #FFFFFF !important;
        font-weight: 800 !important;
    }}

    /* Botões do Sidebar */
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

    /* Inputs no Sidebar */
    section[data-testid="stSidebar"] input, 
    section[data-testid="stSidebar"] select,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div {{
        background: #06152F !important;
        color: #F1F5F9 !important;
        border: 1px solid rgba(243, 124, 4, 0.3) !important;
        border-radius: 6px !important;
    }}

    /* ═══════════════════════════════════════════════════
       COMPONENTES: HEROS E KPIS
       ═══════════════════════════════════════════════════ */
    .hero-totale-1 {{
        background: linear-gradient(to right, rgb(1,40,105) 0%, rgb(243,124,4) 100%);
        padding: 3rem 2.5rem;
        border-radius: 8px;
        color: #FFFFFF;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
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
        border-radius: 8px;
        color: #FFFFFF;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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

    /* KPI Standard */
    .kpi-card {{
        background: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%);
        border-radius: 8px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border-top: 1px solid #F3F4F6;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .kpi-card:hover {{ transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.08); }}
    .kpi-card .kpi-label {{ font-size: 12px; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; }}
    .kpi-card .kpi-value {{ font-size: 1.85rem; font-weight: 700; margin: 4px 0; }}
    .kpi-card .kpi-sub {{ font-size: 12px; color: #94A3B8; }}

    /* KPI Small / Compacto */
    .kpi-card-sm {{
        background: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%);
        border-radius: 6px;
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
        font-size: 10.5px;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        margin-bottom: 2px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .kpi-card-sm .kpi-value {{
        font-family: var(--font-titulo) !important;
        font-size: 1.25rem;
        font-weight: 700;
        line-height: 1.2;
        letter-spacing: -0.2px;
    }}
    .kpi-card-sm .kpi-sub {{
        font-size: 10.5px;
        color: #94A3B8;
        margin-top: 2px;
        font-weight: 500;
    }}
    
    /* ═══════════════════════════════════════════════════════
       TABELAS CORPORATIVAS
       ═══════════════════════════════════════════════════════ */
    .corp-table-wrap {{
        width: 100%; overflow: auto; border: 1px solid var(--cor-borda);
        border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); background: #FFFFFF;
    }}
    table.corp-table {{ width: 100%; border-collapse: separate; border-spacing: 0; }}
    .corp-table thead th {{
        font-family: var(--font-titulo) !important; font-weight: 700; font-size: 11px;
        text-transform: uppercase; color: #1F2937; background: #F8FAFC; padding: 10px 14px;
        border-bottom: 2px solid var(--cor-borda); text-align: left;
        position: sticky; top: 0; z-index: 2; white-space: nowrap;
    }}
    .corp-table tbody td {{
        font-weight: 500; font-size: 11px; color: #374151; padding: 8px 14px;
        border-bottom: 1px solid #F3F4F6; white-space: nowrap;
    }}
    .corp-table tbody tr:hover td {{ background: #F8FAFC !important; }}
    .corp-table td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    </style>
    """


def _injetar_css_global() -> None:
    st.markdown(_get_global_css(), unsafe_allow_html=True)


# ====================================================
# API PÚBLICA DE INICIALIZAÇÃO
# ====================================================
def aplicar_estilo() -> None:
    """Aplica configuração Plotly, injeta fontes e CSS Global. Deve ser chamado no início da página."""
    _configurar_plotly_global()

    if not st.session_state.get("_fontes_ok"):
        _injetar_fontes_no_head_pai()
        st.session_state["_fontes_ok"] = True

    _injetar_css_global()


# ====================================================
# HELPERS
# ====================================================
def _resolver_cor_tema(tema: str) -> str:
    return _TEMA_CORES.get(tema, COR_PRIMARIA)


def _markdown_inline_para_html(texto: str) -> str:
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    return texto


def _detectar_colunas_numericas(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=["number"]).columns.tolist()


# ====================================================
# COMPONENTES VISUAIS (HEROS & KPIS)
# ====================================================
def render_hero_totale_1(
    titulo: str = "Portal TOTALE",
    subtitulo: str = "Painéis de Produção e Gestão Estratégica",
) -> None:
    """Hero Principal: Gradiente Azul para Laranja."""
    if not titulo:
        return
    st.markdown(
        f"""<div class="hero-totale-1"><div class="hero-t1-content">
            <h1 class="hero-t1-title">{titulo}</h1><p class="hero-t1-sub">{subtitulo}</p>
        </div></div>""",
        unsafe_allow_html=True,
    )


def render_hero_totale_2(
    titulo: str, subtitulo: str = "", badge_texto: str = "", badge_tipo: str = "laranja"
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
    st.markdown(
        f"""<div class="hero-totale-2"><div class="hero-t2-container">
            <h1 class="hero-t2-title">{titulo}</h1><p class="hero-t2-sub">{subtitulo}</p>{html_badge}
        </div></div>""",
        unsafe_allow_html=True,
    )


def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    """Função legada que aponta para hero_totale_1."""
    extra = f" · {badge}" if badge else ""
    render_hero_totale_1(titulo, f"{subtitulo}{extra}".strip(" ·"))


def render_kpi(
    col: Any, label: str, valor: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    """Renderiza um cartão KPI em formato padrão (destaque visual amplo)."""
    cor = _resolver_cor_tema(tema)
    renderer = col.markdown if hasattr(col, "markdown") else st.markdown
    renderer(
        f"""<div class="kpi-card" style="border-left: 4px solid {cor};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{cor};">{valor}</div>
            <div class="kpi-sub">{sub}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_kpi_sm(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
    icone: str = "",
) -> None:
    """
    Renderiza um cartão KPI compacto (Small), ideal para grids com 4+ colunas,
    sidebars ou métricas secundárias com alta densidade de informação.
    """
    cor = _resolver_cor_tema(tema)
    renderer = col.markdown if hasattr(col, "markdown") else st.markdown
    html_icone = (
        f'<span style="font-size:13px; margin-left:4px;">{icone}</span>'
        if icone
        else ""
    )
    html_sub = f'<div class="kpi-sub">{sub}</div>' if sub else ""

    renderer(
        f"""<div class="kpi-card-sm" style="border-left: 3px solid {cor};">
            <div class="kpi-label">
                <span>{label}</span>
                {html_icone}
            </div>
            <div class="kpi-value" style="color:{cor};">{valor}</div>
            {html_sub}
        </div>""",
        unsafe_allow_html=True,
    )


def render_insight(msg: str, tipo: TipoInsight = "info") -> None:
    if not msg:
        return
    bg, texto, borda, icone = _INSIGHT_CONFIG.get(tipo, _INSIGHT_CONFIG["info"])
    msg_html = _markdown_inline_para_html(msg)
    st.markdown(
        f"""<div style="background:{bg};color:{texto};border-left:4px solid {borda};
             padding:12px 16px;border-radius:6px;margin:10px 0;font-size:14px;line-height:1.6;">
            <span style="margin-right:8px;">{icone}</span>{msg_html}
        </div>""",
        unsafe_allow_html=True,
    )


# ====================================================
# HEADERS & BRANDING CORPORATIVO
# ====================================================
def render_section_header(
    titulo: str,
    subtitulo: str = "",
    icone: str = "",
    cor_accent: str = COR_SECUNDARIA,
) -> None:
    """Renderiza um cabeçalho de seção estruturado com linha de acento corporativa."""
    if not titulo:
        return

    html_icone = (
        f'<span style="margin-right: 10px; font-size: 1.25em;">{icone}</span>'
        if icone
        else ""
    )
    html_sub = (
        f'<div style="font-family: {FONTE_TEXTO}; font-size: 14px; color: {COR_TEXTO_3}; margin-top: 4px; font-weight: 400;">{subtitulo}</div>'
        if subtitulo
        else ""
    )

    st.markdown(
        f"""
        <div style="margin-top: 2rem; margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center;">
                <h2 style="font-family: {FONTE_TITULO}; font-size: 22px; font-weight: 800; color: {COR_PRIMARIA}; margin: 0; padding: 0; line-height: 1.2;">
                    {html_icone}{titulo}
                </h2>
            </div>
            {html_sub}
            <div style="height: 3px; width: 45px; background: {cor_accent}; border-radius: 2px; margin-top: 10px; margin-bottom: 5px;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand(
    empresa: str = "TOTALE",
    segmento: str = "Sistemas & Energia",
    logo_svg: str | None = None,
) -> None:
    """Renderiza a marca/logo corporativa com acabamento visual integrado ao gradiente da Sidebar."""
    if not logo_svg:
        logo_svg = """
        <svg width="34" height="34" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.15));">
            <circle cx="50" cy="50" r="44" stroke="rgba(255, 255, 255, 0.15)" stroke-width="6"/>
            <path d="M50 12 A 38 38 0 0 1 88 50" stroke="#F37C04" stroke-width="10" stroke-linecap="round"/>
            <path d="M50 88 A 38 38 0 0 1 12 50" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>
            <circle cx="50" cy="50" r="10" fill="#F37C04"/>
        </svg>
        """

    st.sidebar.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 12px; padding: 8px 4px 16px 4px; margin-bottom: 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.15);">
            <div style="flex-shrink: 0; display: flex; align-items: center; justify-content: center;">
                {logo_svg}
            </div>
            <div style="display: flex; flex-direction: column; justify-content: center;">
                <span style="font-family: {FONTE_TITULO}; font-size: 20px; font-weight: 800; color: #FFFFFF; letter-spacing: 0.8px; line-height: 1;">
                    {empresa}
                </span>
                <span style="font-family: {FONTE_TEXTO}; font-size: 10px; font-weight: 600; color: #FFB86B; letter-spacing: 0.8px; text-transform: uppercase; margin-top: 3px; opacity: 0.95;">
                    {segmento}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# TABELAS HTML NATIVAS CORPORATIVAS
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
) -> None:
    """Renderiza um DataFrame como uma tabela HTML pura, respeitando fontes e regras de cor."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("Nenhum dado disponível.")
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
        rows_html.append(f"<tr>{''.join(tds)}</tr>")

    st.markdown(
        f'<div class="corp-table-wrap" style="max-height:{int(height)}px;"><table class="corp-table">'
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>",
        unsafe_allow_html=True,
    )

    if len(df) > max_rows or len(df.columns) > max_cols:
        st.caption(
            f"Exibindo limite de visualização: {min(len(df), max_rows)} linhas x {min(len(df.columns), max_cols)} colunas."
        )