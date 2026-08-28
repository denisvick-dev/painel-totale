"""
componentes.py
==============
Módulo central de estilos, fontes e componentes reutilizáveis
para todo o projeto Streamlit.

Uso em qualquer página:
    from componentes import aplicar_estilo, render_kpi, render_insight
    aplicar_estilo()

Características unificadas:
- Fonte corporativa global (Plus Jakarta Sans + IBM Plex Sans)
- Tema Plotly global corporativo
- Sidebar TOTALE: Laranja metálico limpo + borda no sombreamento
- Selecionador creme/pêssego com borda laranja (estilo pill)
- Heros TOTALE (Gradiente Imagem + Azul com faixa laranja)
- Componentes: KPIs, Insights, Dataframes, Tabelas HTML, Nav Headers

IMPORTANTE:
- st.dataframe usa Canvas (Glide Data Grid) e NÃO aceita font-family via CSS.
- Para fonte corporativa garantida em tabelas, use render_table_html().
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
# TIPOS LITERAIS
# ====================================================
TemaKPI = Literal["azul", "verde", "vermelho", "laranja", "cinza"]
TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]

CellFormatter = Union[str, Callable[[Any], str]]
FmtDict = dict[str, CellFormatter | None]

ColorRule = tuple[Callable[[Any], bool], str]
ColorMapDict = dict[str, list[ColorRule]]


# ====================================================
# TIPOGRAFIA CORPORATIVA TOTALE
# ====================================================
FONTE_TITULO = "'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif"
FONTE_TEXTO = "'IBM Plex Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONTE_CODIGO = "'IBM Plex Mono', Consolas, 'Courier New', monospace"

_GOOGLE_FONTS_URLS = (
    "https://fonts.googleapis.com/icon?family=Material+Icons",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded"
    ":opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined"
    ":opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap",
    "https://fonts.googleapis.com/css2?"
    "family=Plus+Jakarta+Sans:wght@400;500;600;700;800&"
    "family=IBM+Plex+Sans:wght@400;500;600;700&"
    "family=IBM+Plex+Mono:wght@400;500&"
    "display=swap",
)


# ====================================================
# PALETA CORPORATIVA TOTALE
# ====================================================
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
COR_LARANJA_SUAVE = "#FDE6CB"

COR_LARANJA_METAL_1 = "#7A2E00"
COR_LARANJA_METAL_2 = "#C24A00"
COR_LARANJA_METAL_3 = "#E85D04"
COR_LARANJA_METAL_4 = "#F37C04"
COR_LARANJA_METAL_5 = "#FF9838"
COR_LARANJA_METAL_6 = "#FFB86B"

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
# PLOTLY
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
                title_font=dict(family=FONTE_TEXTO, size=13, color=COR_TEXTO_2),
                gridcolor="#F1F5F9",
                zerolinecolor="#CBD5E1",
            ),
            yaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
                title_font=dict(family=FONTE_TEXTO, size=13, color=COR_TEXTO_2),
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
# FONTES
# ====================================================
def _injetar_fontes_no_head_pai() -> None:
    urls_js = ", ".join(f'"{u}"' for u in _GOOGLE_FONTS_URLS)
    components.html(
        f"""<script>
        (function () {{
            const urls = [{urls_js}];
            const preconnects = ['https://fonts.googleapis.com', 'https://fonts.gstatic.com'];
            let parentDoc;
            try {{ parentDoc = window.parent.document; }} catch (e) {{ return; }}
            const head = parentDoc.head;
            preconnects.forEach(function (href) {{
                if (head.querySelector('link[href="' + href + '"]')) return;
                const link = parentDoc.createElement('link');
                link.rel = 'preconnect'; link.href = href;
                if (href.includes('gstatic')) link.crossOrigin = 'anonymous';
                head.appendChild(link);
            }});
            const existentes = Array.from(head.querySelectorAll('link[rel="stylesheet"]'))
                .map(function (l) {{ return l.href; }});
            urls.forEach(function (href) {{
                if (existentes.includes(href)) return;
                const link = parentDoc.createElement('link');
                link.rel = 'stylesheet'; link.href = href;
                head.appendChild(link);
            }});
        }})();
        </script>""",
        height=0,
    )


def _build_links_html() -> str:
    tags = "\n".join(
        f'<link rel="stylesheet" href="{url}">' for url in _GOOGLE_FONTS_URLS
    )
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n' + tags
    )


# ====================================================
# CSS GLOBAL
# ====================================================
def _injetar_css_global() -> None:
    links_html = _build_links_html()

    css = (
        f"""{links_html}
        <style>
        /* ═══ FONT-FACE FALLBACK ═══ */
        @font-face {{
            font-family: 'Material Icons';
            font-style: normal; font-weight: 400; font-display: block;
            src: url(https://fonts.gstatic.com/s/materialicons/v143/flUhRq6tzZclQEJ-Vdg-IuiaDsNc.woff2) format('woff2');
        }}
        @font-face {{
            font-family: 'Material Symbols Rounded';
            font-style: normal; font-weight: 400; font-display: block;
            src: url(https://fonts.gstatic.com/s/materialsymbolsrounded/v206/syl0-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190Fjzag.woff2) format('woff2');
        }}
        @font-face {{
            font-family: 'Material Symbols Outlined';
            font-style: normal; font-weight: 400; font-display: block;
            src: url(https://fonts.gstatic.com/s/materialsymbolsoutlined/v206/kJEhBvYX7BgnkSrUwT8OhrdQw4oELdPIeeII9v6oDMzByHX9rA6RzaxHMPdY43zj-jCxv3fzvRNU22ZXGJpEpjC_1v-p_4MrImHCIJIZrDCvHOej.woff2) format('woff2');
        }}

        /* ═══ VARIÁVEIS ═══ */
        :root {{
            --font-titulo: {FONTE_TITULO};
            --font-texto: {FONTE_TEXTO};
            --font-codigo: {FONTE_CODIGO};
            --cor-primaria: {COR_PRIMARIA};
            --cor-secundaria: {COR_SECUNDARIA};
            --cor-sucesso: {COR_SUCESSO};
            --cor-alerta: {COR_ALERTA};
            --cor-neutro: {COR_NEUTRO};
            --cor-texto: {COR_TEXTO};
            --cor-texto-2: {COR_TEXTO_2};
            --cor-texto-3: {COR_TEXTO_3};
            --cor-borda: {COR_BORDA};
            --cor-fundo: {COR_FUNDO};
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 14px;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
            --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
            --shadow-lg: 0 10px 28px rgba(0,0,0,0.12);
        }}

        /* ═══ BASE — FONTE ═══ */
        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stHeader"],
        [data-testid="stSidebar"],
        [data-testid="stToolbar"],
        section[data-testid="stSidebar"] {{
            font-family: var(--font-texto) !important;
        }}
        p, label, li, a, button, input, select, textarea {{
            font-family: var(--font-texto) !important;
        }}

        /* ═══ TÍTULOS ═══ */
        h1, h2, h3, h4, h5, h6,
        .hero-title, .section-title, .kpi-value {{
            font-family: var(--font-titulo) !important;
            font-weight: 700;
            letter-spacing: -0.3px;
        }}
        h1, .hero-title {{
            font-weight: 800;
            letter-spacing: -0.6px;
        }}

        /* ═══ WIDGETS STREAMLIT ═══ */
        [data-testid="stWidgetLabel"],
        [data-testid="stMarkdownContainer"],
        [data-testid="stMetric"],
        [data-testid="stMetricLabel"],
        [data-baseweb="select"],
        [data-baseweb="input"],
        [data-baseweb="tab"] {{
            font-family: var(--font-texto) !important;
        }}
        [data-testid="stMetricValue"] {{
            font-family: var(--font-titulo) !important;
            font-weight: 700;
            font-variant-numeric: tabular-nums;
        }}
        .stButton button, .stDownloadButton button,
        .stFormSubmitButton button, button[kind] {{
            font-family: var(--font-texto) !important;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}

        /* ═══════════════════════════════════════════════════════
           TABELA HTML CORPORATIVA (fontes 100% garantidas via DOM)
           Use render_table_html() para tabelas críticas.
           ═══════════════════════════════════════════════════════ */

        .corp-table-wrap {{
            width: 100%;
            overflow: auto;
            border: 1px solid var(--cor-borda);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            background: #FFFFFF;
            margin-bottom: 12px;
        }}
        table.corp-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-family: var(--font-texto) !important;
        }}
        .corp-table thead th {{
            font-family: var(--font-titulo) !important;
            font-weight: 700 !important;
            font-size: 11px !important;
            letter-spacing: 0.4px !important;
            text-transform: uppercase !important;
            color: var(--cor-texto) !important;
            background: #F8FAFC !important;
            padding: 10px 14px !important;
            border-bottom: 2px solid var(--cor-borda) !important;
            text-align: left !important;
            position: sticky;
            top: 0;
            z-index: 2;
            white-space: nowrap;
        }}
        .corp-table tbody td {{
            font-family: var(--font-texto) !important;
            font-weight: 500 !important;
            font-size: 10.5px !important;
            font-variant-numeric: tabular-nums !important;
            color: var(--cor-texto-2) !important;
            padding: 8px 14px !important;
            border-bottom: 1px solid #F3F4F6 !important;
            white-space: nowrap;
        }}
        .corp-table tbody tr:hover td {{
            background: #F8FAFC !important;
        }}
        .corp-table td.num {{
            text-align: right !important;
            font-variant-numeric: tabular-nums !important;
        }}
        .corp-table td.neg {{
            color: var(--cor-alerta) !important;
            font-weight: 700 !important;
        }}
        .corp-table td.pos {{
            color: var(--cor-sucesso) !important;
            font-weight: 700 !important;
        }}

        /* ═══ st.dataframe / st.table — melhor esforço (Canvas ignora) ═══ */
        [data-testid="stDataFrame"], .stDataFrame {{
            font-family: var(--font-texto) !important;
        }}
        [data-testid="stTable"], [data-testid="stTable"] * {{
            font-family: var(--font-texto) !important;
        }}
        [data-testid="stTable"] thead th {{
            font-family: var(--font-titulo) !important;
            font-weight: 700 !important;
            letter-spacing: 0.3px !important;
            font-size: 12px !important;
            color: var(--cor-texto) !important;
            background: #F8FAFC !important;
            border-bottom: 2px solid var(--cor-borda) !important;
        }}
        [data-testid="stTable"] tbody td {{
            font-family: var(--font-texto) !important;
            font-weight: 500 !important;
            font-size: 13px !important;
            font-variant-numeric: tabular-nums !important;
            color: var(--cor-texto-2) !important;
            padding: 8px 12px !important;
            border-bottom: 1px solid #F3F4F6 !important;
        }}
        [data-testid="stTable"] tbody tr:hover {{
            background-color: #F8FAFC !important;
        }}
        
        .corp-table td.meta-alta {{
            background: #1E3A8A !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            text-align: center !important;
            border-left: 3px solid #0F172A !important;
        }}
        .corp-table td.meta-ok {{
            background: #DCFCE7 !important;
            color: #166534 !important;
            font-weight: 700 !important;
            text-align: center !important;
            border-left: 3px solid #22C55E !important;
        }}
        .corp-table td.meta-prox {{
            background: #FEF9C3 !important;
            color: #854D0E !important;
            font-weight: 700 !important;
            text-align: center !important;
            border-left: 3px solid #EAB308 !important;
        }}
        .corp-table td.meta-baixa {{
            font-weight: 700 !important;
            text-align: center !important;
            border-left: 3px solid #EF4444 !important;
        }}
        .corp-table td.proj {{
            background: #0F172A !important;
            color: #FFFFFF !important;
            font-weight: 800 !important;
            text-align: center !important;
            border-left: 3px solid #64748B !important;
        }}
        .corp-table thead th.th-corp {{
            background: linear-gradient(180deg, #012869 0%, #1E3A8A 100%) !important;
            color: #FFFFFF !important;
            text-transform: uppercase !important;
        }}

        /* ═══ CÓDIGO ═══ */
        code, pre, kbd, samp {{
            font-family: var(--font-codigo) !important;
        }}

        /* ═══ LAYOUT ═══ */
        .main .block-container {{
            padding-top: 1rem;
            max-width: 1400px;
        }}

        /* ═══ SCROLLBAR ═══ */
        ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
        ::-webkit-scrollbar-track {{ background: #F1F5F9; }}
        ::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 5px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}

        """
        + """

        /* ═══════════════════════════════════════════════════
           SIDEBAR — LARANJA METÁLICO + TEXTO ESCURO
           ═══════════════════════════════════════════════════ */

        section[data-testid="stSidebar"] {
            background: linear-gradient(
                180deg,
                #F6A158 0%,
                #F37C04 20%,
                #E86B03 48%,
                #D85B00 76%,
                #B94700 100%
            ) !important;
            border-right: 2px solid #943800 !important;
            box-shadow:
                inset 1px 0 0 rgba(255, 235, 210, 0.52),
                inset -1px 0 0 rgba(105, 37, 0, 0.35),
                2px 0 0 rgba(114, 43, 0, 0.52),
                6px 0 18px rgba(87, 31, 0, 0.22),
                12px 0 32px rgba(87, 31, 0, 0.12) !important;
        }
        section[data-testid="stSidebar"]::before,
        section[data-testid="stSidebar"]::after {
            content: none !important;
            display: none !important;
        }

        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
        section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] span {
            color: #3C1A08 !important;
            font-weight: 600;
            text-shadow: 0 1px 0 rgba(255, 235, 210, 0.20);
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] h4 {
            color: #2A1004 !important;
            font-family: var(--font-titulo) !important;
            font-weight: 800 !important;
            letter-spacing: -0.3px;
            border-bottom: 2px solid rgba(126, 47, 0, 0.65) !important;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }

        section[data-testid="stSidebar"] hr {
            border: none !important;
            height: 1px !important;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(109, 40, 0, 0.42) 20%,
                rgba(255, 238, 215, 0.55) 50%,
                rgba(109, 40, 0, 0.42) 80%,
                transparent 100%
            ) !important;
            margin: 12px 0 !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
            background: transparent !important;
            padding: 6px 0 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {
            padding: 0 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li {
            margin: 3px 12px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a,
        section[data-testid="stSidebar"] li a {
            background: transparent !important;
            border: 1px solid transparent !important;
            border-left: 3px solid transparent !important;
            border-radius: 8px !important;
            padding: 9px 12px !important;
            transition: all 0.18s ease !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span,
        section[data-testid="stSidebar"] li a span,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a p,
        section[data-testid="stSidebar"] li a p {
            color: #3C1A08 !important;
            font-weight: 700 !important;
            text-shadow: 0 1px 0 rgba(255, 235, 210, 0.22);
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover,
        section[data-testid="stSidebar"] li a:hover {
            background: rgba(255, 247, 237, 0.30) !important;
            border-color: rgba(124, 48, 0, 0.18) !important;
            border-left-color: #8E3500 !important;
            transform: translateX(2px);
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover span,
        section[data-testid="stSidebar"] li a:hover span {
            color: #261003 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
        section[data-testid="stSidebar"] li a[aria-current="page"] {
            background: linear-gradient(
                90deg,
                #FFF8F0 0%,
                #FFE9D0 55%,
                #FADBB9 100%
            ) !important;
            border: 1px solid rgba(153, 57, 0, 0.20) !important;
            border-left: 4px solid #E85D04 !important;
            border-radius: 8px !important;
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.85),
                0 2px 6px rgba(88, 31, 0, 0.20) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] span,
        section[data-testid="stSidebar"] li a[aria-current="page"] span,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] p,
        section[data-testid="stSidebar"] li a[aria-current="page"] p {
            color: #722B00 !important;
            font-weight: 800 !important;
            text-shadow: none !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a [data-testid*="Icon"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a [class*="material"] {
            color: #4A1D08 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] [data-testid*="Icon"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] [class*="material"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] svg {
            color: #E85D04 !important;
            fill: #E85D04 !important;
        }

        section[data-testid="stSidebar"] .stButton button,
        section[data-testid="stSidebar"] .stDownloadButton button,
        section[data-testid="stSidebar"] .stFormSubmitButton button {
            background: linear-gradient(
                180deg,
                #FFF8F0 0%,
                #FDE6CB 100%
            ) !important;
            color: #4A1D08 !important;
            border: 1px solid rgba(125, 47, 0, 0.38) !important;
            border-radius: 8px !important;
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.90),
                0 2px 4px rgba(82, 29, 0, 0.16) !important;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] .stButton button:hover,
        section[data-testid="stSidebar"] .stDownloadButton button:hover,
        section[data-testid="stSidebar"] .stFormSubmitButton button:hover {
            background: linear-gradient(
                180deg,
                #F58B24 0%,
                #D95A00 100%
            ) !important;
            color: #FFFFFF !important;
            border-color: #923700 !important;
            box-shadow:
                inset 0 1px 0 rgba(255, 220, 180, 0.35),
                0 3px 8px rgba(81, 29, 0, 0.25) !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] [data-baseweb="input"],
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea {
            background: #FFF9F3 !important;
            color: #3C1A08 !important;
            border: 1px solid rgba(125, 47, 0, 0.36) !important;
            border-radius: 8px !important;
            box-shadow:
                inset 0 1px 2px rgba(92, 32, 0, 0.10),
                0 1px 2px rgba(255, 235, 210, 0.20) !important;
        }
        section[data-testid="stSidebar"] [data-baseweb="select"] * {
            color: #3C1A08 !important;
            text-shadow: none !important;
        }
        section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within,
        section[data-testid="stSidebar"] [data-baseweb="input"]:focus-within {
            border-color: #FFF0DD !important;
            box-shadow:
                0 0 0 3px rgba(255, 237, 214, 0.35),
                0 0 0 5px rgba(139, 53, 0, 0.22) !important;
        }

        """
        + f"""

        /* ═══════════════════════════════════════════════════
           🎨 HERO 1 — Gradiente Imagem TOTALE (azul → laranja)
           ═══════════════════════════════════════════════════ */
        .hero-totale-1 {{
            background: linear-gradient(90deg,
                #012869 0%,
                #1e40a6 35%,
                #4c4c8a 55%,
                #b86a2e 85%,
                #d3751f 100%
            );
            border-radius: var(--radius-lg);
            padding: 24px 32px;
            position: relative;
            overflow: hidden;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            gap: 16px;
            min-height: 100px;
        }}
        .hero-totale-1::after {{
            content: '';
            position: absolute;
            top: -50%; bottom: -50%;
            left: 45%; width: 60px;
            background: linear-gradient(
                90deg,
                transparent,
                rgba(255, 255, 255, 0.15),
                transparent
            );
            transform: rotate(25deg);
            pointer-events: none;
        }}
        .hero-t1-icon-box {{
            background: white;
            padding: 6px 8px;
            border-radius: 6px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            box-shadow: 1px 2px 6px rgba(0, 0, 0, 0.35);
            font-size: 28px;
            line-height: 1;
            position: relative;
            z-index: 2;
            color: #333333;
        }}
        .hero-t1-content {{
            position: relative;
            z-index: 2;
            color: white;
        }}
        .hero-t1-title {{
            font-family: var(--font-titulo) !important;
            font-size: 32px;
            font-weight: 800;
            margin: 0;
            text-shadow: 1px 2px 4px rgba(0, 0, 0, 0.40);
            line-height: 1.1;
            color: #FFFFFF;
        }}
        .hero-t1-sub {{
            font-family: var(--font-texto) !important;
            font-size: 14px;
            margin: 6px 0 0 0;
            opacity: 0.95;
            font-weight: 500;
            color: #F8FAFC;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.30);
        }}

        /* ═══════════════════════════════════════════════════
           🎨 HERO 2 — Azul Totale + faixa laranja
           ═══════════════════════════════════════════════════ */
        .hero-totale-2 {{
            background: var(--cor-primaria);
            border-radius: var(--radius-lg);
            padding: 28px 32px;
            margin-bottom: 24px;
            position: relative;
            box-shadow: var(--shadow-md);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 100px;
        }}
        .hero-totale-2::after {{
            content: '';
            position: absolute;
            bottom: 0; left: 0; right: 0;
            height: 4px;
            background: var(--cor-secundaria);
        }}
        .hero-totale-2::before {{
            content: '';
            position: absolute;
            top: -20px; right: -20px;
            width: 150px; height: 150px;
            border-radius: 50%;
            background: radial-gradient(
                circle,
                rgba(243, 124, 4, 0.18) 0%,
                transparent 70%
            );
        }}
        .hero-t2-title {{
            font-family: var(--font-titulo) !important;
            color: #FFFFFF;
            font-size: 28px;
            font-weight: 800;
            margin: 0 0 8px 0;
            letter-spacing: -0.5px;
            position: relative;
            z-index: 2;
        }}
        .hero-t2-sub {{
            font-family: var(--font-texto) !important;
            color: #CBD5E1;
            font-size: 15px;
            margin: 0;
            position: relative;
            z-index: 2;
        }}

        /* ═══ KPI CARDS ═══ */
        .kpi-card {{
            background: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%);
            border-radius: var(--radius-md);
            padding: 20px 24px;
            box-shadow: var(--shadow-md);
            border-left: 4px solid var(--cor-primaria);
            border-top: 1px solid #F3F4F6;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}
        .kpi-label {{
            font-family: var(--font-texto) !important;
            font-size: 11px;
            font-weight: 700;
            color: var(--cor-texto-3);
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-family: var(--font-titulo) !important;
            font-size: 28px;
            font-weight: 800;
            color: var(--cor-texto);
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }}
        .kpi-sub {{
            font-family: var(--font-texto) !important;
            font-size: 12px;
            color: var(--cor-texto-3);
            margin-top: 6px;
            font-weight: 500;
        }}

        /* ═══ SEÇÕES ═══ */
        .section-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 32px 0 16px 0;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--cor-borda);
        }}
        .section-title {{
            font-family: var(--font-titulo) !important;
            font-size: 20px;
            font-weight: 700;
            color: var(--cor-primaria);
            margin: 0;
        }}
        .section-badge {{
            background: linear-gradient(135deg, #F3F4F6 0%, #E5E7EB 100%);
            color: var(--cor-texto-2);
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border: 1px solid #D1D5DB;
        }}

        /* ═══ MATERIAL ICONS ═══ */
        .material-icons, .material-icons-outlined, .material-icons-round,
        .material-symbols-outlined, .material-symbols-rounded,
        [data-testid="stIconMaterial"],
        [data-testid*="Icon"], [data-testid*="icon"],
        span[class*="material"], i[class*="material"] {{
            font-family:
                "Material Symbols Rounded",
                "Material Symbols Outlined",
                "Material Icons" !important;
            font-weight: normal !important;
            font-style: normal !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            white-space: nowrap !important;
            direction: ltr !important;
            font-feature-settings: "liga" !important;
            -webkit-font-smoothing: antialiased !important;
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24 !important;
        }}
        svg, svg * {{ font-family: inherit !important; }}
        section[data-testid="stSidebar"] [data-testid*="Icon"],
        section[data-testid="stSidebar"] [class*="material"] {{
            font-size: 18px !important;
            width: 18px !important;
            height: 18px !important;
        }}
        </style>
        """
    )

    st.markdown(css, unsafe_allow_html=True)


# ====================================================
# API PÚBLICA
# ====================================================
def aplicar_estilo() -> None:
    _configurar_plotly_global()
    # Fontes: só 1x por sessão
    if not st.session_state.get("_fontes_ok"):
        _injetar_fontes_no_head_pai()
        st.session_state["_fontes_ok"] = True
    # CSS: barato e garante persistência entre pages
    _injetar_css_global()


# ====================================================
# HELPERS
# ====================================================
def _resolver_cor_tema(tema: str) -> str:
    cor = _TEMA_CORES.get(tema)
    if cor is None:
        logger.warning("Tema desconhecido: '%s'. Usando 'azul'.", tema)
        return COR_PRIMARIA
    return cor


def _markdown_inline_para_html(texto: str) -> str:
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    return texto


def _resolver_fmt_para_style(
    fmt: FmtDict, df: pd.DataFrame
) -> dict[str, str | Callable | None]:
    resultado: dict[str, str | Callable | None] = {}
    for col, formatter in fmt.items():
        if col not in df.columns:
            continue
        if formatter is None:
            resultado[col] = None
        elif isinstance(formatter, str) or callable(formatter):
            resultado[col] = formatter
        else:
            logger.warning(
                "Formatador inválido para coluna '%s': %s. Ignorado.",
                col,
                type(formatter).__name__,
            )
    return resultado


def _detectar_colunas_numericas(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=["number"]).columns.tolist()


def _aplicar_coloracao_condicional(
    styled: pd.io.formats.style.Styler,
    df: pd.DataFrame,
    rules: ColorMapDict,
) -> pd.io.formats.style.Styler:
    for col, regras in rules.items():
        if col not in df.columns:
            continue

        def _make_color_func(col_rules: list[ColorRule]):
            def _colorir(val: Any) -> str:
                for pred, cor in col_rules:
                    try:
                        if pred(val):
                            return f"color: {cor}; font-weight: 700;"
                    except (TypeError, ValueError):
                        continue
                return ""

            return _colorir

        func = _make_color_func(regras)
        try:
            styled = styled.map(func, subset=[col])  # Pandas >=2.1
        except AttributeError:
            styled = styled.map(func, subset=[col])  # Pandas <2.1
    return styled


# ====================================================
# HEROS
# ====================================================
def render_hero_totale_1(
    titulo: str = "Portal TOTALE",
    subtitulo: str = "Painéis de Produção, Indicadores e Gestão Estratégica",
) -> None:
    """Hero estilo imagem: gradiente azul → laranja com feixe de luz animado sem ícone."""
    if not titulo:
        raise ValueError("render_hero_totale_1: 'titulo' não pode ser vazio.")
        
    st.markdown(
        f"""
        <style>
            .hero-totale-1 {{
                /* Gradiente horizontal com as cores exatas: Azul rgb(1,40,105) para Laranja rgb(243,124,4) */
                background: linear-gradient(to right, rgb(1,40,105) 0%, rgb(243,124,4) 100%);
                padding: 3rem 2.5rem;
                border-radius: 8px;
                color: #FFFFFF;
                font-family: sans-serif;
                position: relative;
                overflow: hidden; /* Garante que o feixe de luz não escape do container */
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
            }}
            
            /* Efeito de Feixe de Luz Diagonal */
            .hero-totale-1::after {{
                content: '';
                position: absolute;
                top: -50%;
                left: -60%;
                width: 30%;
                height: 200%;
                background: linear-gradient(
                    to right, 
                    rgba(255,255,255,0) 0%, 
                    rgba(255,255,255,0.25) 50%, 
                    rgba(255,255,255,0) 100%
                );
                transform: rotate(25deg);
                animation: feixeLuz 6s infinite ease-in-out;
            }}
            
            @keyframes feixeLuz {{
                0% {{ left: -60%; }}
                30% {{ left: 130%; }}
                100% {{ left: 130%; }}
            }}
            
            .hero-t1-content {{
                position: relative;
                z-index: 1; /* Mantém o texto acima do efeito de luz */
            }}
            
            .hero-t1-title {{
                margin: 0;
                font-size: 2.8rem;
                font-weight: 700;
                letter-spacing: -0.5px;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }}
            
            .hero-t1-sub {{
                margin: 0.75rem 0 0 0;
                font-size: 1.25rem;
                opacity: 0.95;
                font-weight: 400;
                text-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
            }}
        </style>

        <div class="hero-totale-1">
            <div class="hero-t1-content">
                <h1 class="hero-t1-title">{titulo}</h1>
                <p class="hero-t1-sub">{subtitulo}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero_totale_2(
    titulo: str, 
    subtitulo: str = "", 
    badge_texto: str = "", 
    badge_tipo: str = "laranja",
    FONTE_TEXTO: str = "sans-serif"
) -> None:
    """Hero Totale com fundo em gradiente horizontal e feixe de luz sutil e mais leve."""
    if not titulo:
        raise ValueError("render_hero_totale_2: 'titulo' não pode ser vazio.")
        
    # Valida e define a classe de cor do badge
    classe_cor_badge = "badge-laranja" if badge_tipo.lower() == "laranja" else "badge-azul"
        
    badge_html = f'<span class="hero-t2-badge {classe_cor_badge}">{badge_texto}</span>' if badge_texto else ""
    sub_html = f'<p class="hero-t2-sub">{subtitulo}</p>' if subtitulo else ""
    
    st.markdown(
        f"""
        <style>
            .hero-totale-2 {{
                background: linear-gradient(to right, rgb(243,124,4) 0%, rgb(1,40,105) 100%);
                padding: 2.5rem 2rem;
                border-radius: 8px;
                color: #FFFFFF;
                font-family: sans-serif;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                position: relative;
                overflow: hidden;
            }}
            
            /* Efeito de Feixe de Luz Suavizado (Mais Leve) */
            .hero-totale-2::after {{
                content: '';
                position: absolute;
                top: -50%;
                left: -60%;
                width: 25%;
                height: 200%;
                background: linear-gradient(
                    to right, 
                    rgba(255,255,255,0) 0%, 
                    rgba(255,255,255,0.08) 50%, /* Opacidade reduzida para um efeito discreto */
                    rgba(255,255,255,0) 100%
                );
                transform: rotate(25deg);
                animation: feixeLuzT2Leve 8s infinite ease-in-out; /* Tempo aumentado para movimento suave */
            }}
            
            @keyframes feixeLuzT2Leve {{
                0% {{ left: -60%; }}
                25% {{ left: 130%; }}
                100% {{ left: 130%; }}
            }}
            
            .hero-t2-container {{
                position: relative;
                z-index: 1;
            }}
            
            .hero-t2-title {{
                margin: 0;
                font-size: 2.5rem;
                font-weight: 700;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
            }}
            .hero-t2-sub {{
                margin: 0.5rem 0 0 0;
                font-size: 1.2rem;
                opacity: 0.95;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
            }}
            .hero-t2-badge {{
                display: inline-block;
                padding: 5px 14px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
                margin-top: 16px;
                letter-spacing: 0.8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                font-family: {FONTE_CODIGO};
            }}
            .badge-laranja {{
                background-color: #FFFFFF;
                color: rgb(243,124,4);
            }}
            .badge-azul {{
                background-color: rgb(1,40,105);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
        </style>

        <div class="hero-totale-2">
            <div class="hero-t2-container">
                <h1 class="hero-t2-title">{titulo}</h1>
                {sub_html}
                {badge_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    """Alias legado → redireciona para hero_totale_1."""
    extra = f" · {badge}" if badge else ""
    render_hero_totale_1(titulo=titulo, subtitulo=f"{subtitulo}{extra}".strip(" ·"))


# ====================================================
# SIDEBAR
# ====================================================
def render_sidebar_nav_header(titulo: str) -> None:
    """Título divisor do menu (ex: MENU PRINCIPAL, CENTRAL DE PERFORMANCE)."""
    if not titulo:
        return
    st.sidebar.markdown(
        f'<div class="sidebar-menu-header">{titulo}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar_brand(
    titulo: str,
    subtitulo: str = "",
    icone: str = "🏢",
) -> None:
    """Cabeçalho de marca no topo do sidebar."""
    if not titulo:
        raise ValueError("render_sidebar_brand: 'titulo' não pode ser vazio.")
    sub_html = f'<p class="sidebar-brand-subtitle">{subtitulo}</p>' if subtitulo else ""
    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand">
            <h1 class="sidebar-brand-title">{icone} {titulo}</h1>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_section(label: str) -> None:
    """Label de seção para agrupar filtros no sidebar."""
    if not label:
        return
    st.sidebar.markdown(
        f'<div class="sidebar-section-label">{label}</div>',
        unsafe_allow_html=True,
    )


# ====================================================
# COMPONENTES DE CONTEÚDO
# ====================================================
def render_section(titulo: str, divider: str = "gray") -> None:
    st.subheader(titulo, divider=divider)


def render_section_header(icon: str, title: str, badge: str = "") -> None:
    if not title:
        raise ValueError("render_section_header: 'title' vazio.")
    badge_html = f'<span class="section-badge">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="section-header">
            <span style="font-size:24px;line-height:1;">{icon}</span>
            <h2 class="section-title">{title}</h2>
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
) -> None:
    cor = _resolver_cor_tema(tema)
    col.markdown(
        f"""
        <div class="kpi-card" style="border-left-color:{cor};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{cor};">{valor}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
) -> None:
    cor = _resolver_cor_tema(tema)
    container.markdown(
        f"""
        <div style="background:white;border-radius:6px;padding:12px 16px;
             border-left:3px solid {cor};margin-bottom:8px;
             box-shadow:0 1px 4px rgba(0,0,0,0.06);">
            <div style="font-family:{FONTE_TEXTO};font-size:10px;
                 color:{COR_TEXTO_3};text-transform:uppercase;
                 letter-spacing:1px;font-weight:700;">{label}</div>
            <div style="font-family:{FONTE_TITULO};font-size:20px;
                 color:{cor};font-weight:800;line-height:1.2;
                 margin-top:4px;font-variant-numeric:tabular-nums;">{valor}</div>
            <div style="font-family:{FONTE_TEXTO};font-size:11px;
                 color:{COR_TEXTO_3};margin-top:2px;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insight(msg: str, tipo: TipoInsight = "info") -> None:
    if not msg:
        return
    config = _INSIGHT_CONFIG.get(tipo)
    if config is None:
        logger.warning("Tipo desconhecido: '%s'. Usando 'info'.", tipo)
        config = _INSIGHT_CONFIG["info"]
    bg, texto, borda, icone = config
    msg_html = _markdown_inline_para_html(msg)
    st.markdown(
        f"""
        <div style="background:{bg};color:{texto};
             border-left:4px solid {borda};
             padding:12px 16px;border-radius:6px;margin:10px 0;
             font-family:{FONTE_TEXTO};font-size:14px;line-height:1.6;">
            <span style="margin-right:8px;">{icone}</span>{msg_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# DATAFRAMES / TABELAS
# ====================================================
def render_dataframe(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    height: int = 400,
    fmt: FmtDict | None = None,
    color_rules: ColorMapDict | None = None,
    highlight_index: bool = False,
    **kwargs: Any,
) -> None:
    """
    Renderiza st.dataframe (Canvas/Glide Data Grid).

    ⚠️ ATENÇÃO: st.dataframe pinta o texto em Canvas e IGNORA font-family
    do CSS. Para tabelas com fonte corporativa garantida, use
    render_table_html() em vez desta função.

    Use render_dataframe quando precisar de:
    - Sorting/filtering interativo
    - Grandes volumes de dados (>200 linhas)
    - Column config avançado
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Esperado pd.DataFrame, recebido {type(df).__name__}.")
    if df.empty:
        st.info("Nenhum dado disponível para exibição.")
        return

    if titulo:
        st.markdown(
            f'<div style="font-family:{FONTE_TITULO};font-weight:700;'
            f'font-size:16px;color:{COR_PRIMARIA};margin-bottom:8px;">'
            f"{icone} {titulo}</div>",
            unsafe_allow_html=True,
        )

    styled = df.style
    if fmt:
        fmt_resolvido = _resolver_fmt_para_style(fmt, df)
        if fmt_resolvido:
            try:
                styled = styled.format(fmt_resolvido)
            except Exception:
                logger.exception("Falha ao aplicar formatação. Exibindo sem fmt.")

    if color_rules:
        styled = _aplicar_coloracao_condicional(styled, df, color_rules)

    # Mescla kwargs evitando duplicatas
    kwargs.setdefault("use_container_width", True)
    kwargs.setdefault("hide_index", not highlight_index)
    kwargs.setdefault("height", height)

    try:
        st.dataframe(styled, **kwargs)
    except Exception:
        logger.exception("Falha ao renderizar Styler. Fallback para df cru.")
        kwargs["hide_index"] = True
        st.dataframe(df, **kwargs)


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
    """
    Tabela HTML corporativa — versão performática.
    - Sem iterrows()
    - Limita colunas no preview
    - HTML montado de forma vetorizada
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Esperado pd.DataFrame, recebido {type(df).__name__}.")
    if df.empty:
        st.info("Nenhum dado disponível.")
        return

    # Limita colunas no preview (evita DOM monstro)
    cols = list(df.columns[:max_cols])
    df_show = df.loc[:, cols].head(max_rows).copy()

    if titulo:
        st.markdown(
            f'<div style="font-family:{FONTE_TITULO};font-weight:700;'
            f'font-size:16px;color:{COR_PRIMARIA};margin-bottom:8px;">'
            f"{icone} {titulo}</div>",
            unsafe_allow_html=True,
        )

    if num_cols is None:
        num_cols = [c for c in _detectar_colunas_numericas(df_show) if c in cols]
    num_set = set(num_cols)

    # Preenche NaN uma vez
    df_show = df_show.fillna("—")

    # Aplica formatação vetorizada por coluna (sem iterrows)
    display = pd.DataFrame(index=df_show.index)
    for c in cols:
        s = df_show[c]
        if fmt and c in fmt and fmt[c] is not None:
            f = fmt[c]
            try:
                if callable(f):
                    display[c] = s.map(lambda v, _f=f: _f(v) if v != "—" else "—")
                elif isinstance(f, str):
                    display[c] = s.map(
                        lambda v, _f=f: _f.format(v) if v != "—" else "—"
                    )
                else:
                    display[c] = s.astype(str)
            except Exception:
                display[c] = s.astype(str)
        else:
            display[c] = s.astype(str)

    # Color rules (opcional, só se passado)
    style_maps: dict[str, pd.Series] = {}
    if color_rules:
        for c, regras in color_rules.items():
            if c not in df_show.columns:
                continue
            styles = pd.Series("", index=df_show.index, dtype=str)
            raw = df.loc[df_show.index, c] if c in df.columns else df_show[c]
            for pred, cor in regras:
                try:
                    mask = raw.map(
                        lambda v, _p=pred: bool(_p(v)) if v != "—" else False
                    )
                    styles = styles.where(~mask, f"color:{cor};font-weight:700;")
                except Exception:
                    continue
            style_maps[c] = styles

    # Monta HTML em chunks (muito mais rápido que concatenar célula a célula em loop Python puro com f-string aninhada por linha)
    header = "".join(f"<th>{c}</th>" for c in cols)
    rows_html: list[str] = []
    values = display.to_numpy()
    n_rows, n_cols = values.shape

    for i in range(n_rows):
        tds: list[str] = []
        for j, c in enumerate(cols):
            cls = ' class="num"' if c in num_set else ""
            style = ""
            if c in style_maps:
                stl = style_maps[c].iloc[i]
                if stl:
                    style = f' style="{stl}"'
            # Escape mínimo
            val = (
                str(values[i, j])
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            tds.append(f"<td{cls}{style}>{val}</td>")
        rows_html.append(f"<tr>{''.join(tds)}</tr>")

    html = (
        f'<div class="corp-table-wrap" style="max-height:{int(height)}px;">'
        f'<table class="corp-table">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        f"</table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)

    extras = []
    if len(df) > max_rows:
        extras.append(f"{max_rows} de {len(df):,} linhas".replace(",", "."))
    if len(df.columns) > max_cols:
        extras.append(f"{max_cols} de {len(df.columns)} colunas")
    if extras:
        st.caption("Exibindo " + " · ".join(extras))
