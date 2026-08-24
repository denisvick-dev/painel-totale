"""
componentes.py
==============
Módulo central de estilos, fontes e componentes reutilizáveis
para todo o projeto Streamlit.

Uso em qualquer página:
    from componentes import aplicar_estilo, render_kpi, render_insight
    aplicar_estilo()

Características:
- Fonte corporativa global (Inter + Manrope)
- Preservação de ícones Material Icons do Streamlit
- Tema Plotly global corporativo
- Componentes reutilizáveis (KPIs, insights, seções, hero, dataframes)
- Hero com identidade AZUL + LARANJA corporativos
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

BaseFormatter = Union[str, Callable[[object], str]]
FmtDict = dict[str, BaseFormatter | None]


# ====================================================
# TIPOGRAFIA
# ====================================================
FONTE_TITULO = "'Manrope', 'Segoe UI', Arial, sans-serif"
FONTE_TEXTO = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONTE_CODIGO = "'JetBrains Mono', Consolas, 'Courier New', monospace"

_GOOGLE_FONTS_URLS = (
    "https://fonts.googleapis.com/icon?family=Material+Icons",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded"
    ":opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined"
    ":opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
    "&family=Manrope:wght@400;500;600;700;800;900"
    "&family=JetBrains+Mono:wght@400;500&display=swap",
)

# ====================================================
# PALETA CORPORATIVA
# ====================================================
COR_PRIMARIA = "#012869"  # Azul institucional
COR_SECUNDARIA = "#F37C04"  # Laranja corporativo
COR_SUCESSO = "#059669"
COR_ALERTA = "#DC2626"
COR_NEUTRO = "#64748B"
COR_TEXTO = "#1F2937"
COR_TEXTO_2 = "#374151"
COR_TEXTO_3 = "#6B7280"
COR_BORDA = "#E2E8F0"
COR_FUNDO = "#F8FAFC"
COR_LARANJA_SUAVE = "#FDE68A" # Laranja suave para destaques
COR_AZUL_SUAVE = "#DBEAFE" # Azul suave para destaques

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
        f"""
        <script>
        (function () {{
            const urls = [{urls_js}];
            const preconnects = [
                'https://fonts.googleapis.com',
                'https://fonts.gstatic.com'
            ];
            let parentDoc;
            try {{ parentDoc = window.parent.document; }}
            catch (e) {{ return; }}
            const head = parentDoc.head;
            preconnects.forEach(function (href) {{
                if (head.querySelector('link[href="' + href + '"]')) return;
                const link = parentDoc.createElement('link');
                link.rel = 'preconnect';
                link.href = href;
                if (href.includes('gstatic')) link.crossOrigin = 'anonymous';
                head.appendChild(link);
            }});
            const existentes = Array.from(
                head.querySelectorAll('link[rel="stylesheet"]')
            ).map(function (l) {{ return l.href; }});
            urls.forEach(function (href) {{
                if (existentes.includes(href)) return;
                const link = parentDoc.createElement('link');
                link.rel  = 'stylesheet';
                link.href = href;
                head.appendChild(link);
            }});
        }})();
        </script>
        """,
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

    css = f"""{links_html}
        <style>
        /* ═════════ FONT-FACE FALLBACK ═════════ */
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

        /* ═════════ VARIÁVEIS ═════════ */
        :root {{
            --font-titulo:    {FONTE_TITULO};
            --font-texto:     {FONTE_TEXTO};
            --font-codigo:    {FONTE_CODIGO};
            --cor-primaria:   {COR_PRIMARIA};
            --cor-secundaria: {COR_SECUNDARIA};
            --cor-sucesso:    {COR_SUCESSO};
            --cor-alerta:     {COR_ALERTA};
            --cor-neutro:     {COR_NEUTRO};
            --cor-texto:      {COR_TEXTO};
            --cor-texto-2:    {COR_TEXTO_2};
            --cor-texto-3:    {COR_TEXTO_3};
            --cor-borda:      {COR_BORDA};
            --cor-fundo:      {COR_FUNDO};
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 14px;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
            --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
            --shadow-lg: 0 10px 28px rgba(0,0,0,0.12);
        }}

        /* ═════════ BASE — FONTE ═════════ */
        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stHeader"],
        [data-testid="stSidebar"],
        [data-testid="stToolbar"],
        section[data-testid="stSidebar"] {{
            font-family: var(--font-texto) !important;
        }}
        p, label, div, li, a, button, input, select, textarea {{
            font-family: var(--font-texto) !important;
        }}
        span:not([class*="material"]):not([class*="Icon"]):not([class*="icon"])
            :not([data-testid*="Icon"]):not([data-testid*="icon"]) {{
            font-family: var(--font-texto) !important;
        }}

        /* ═════════ TÍTULOS ═════════ */
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

        /* ═════════ WIDGETS STREAMLIT ═════════ */
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

        /* ═════════ BOTÕES ═════════ */
        .stButton button, .stDownloadButton button,
        .stFormSubmitButton button, button[kind] {{
            font-family: var(--font-texto) !important;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}

        /* ═════════ TABELAS ═════════ */
        .stDataFrame, .stTable,
        table, thead, tbody, tr, th, td {{
            font-family: var(--font-texto) !important;
        }}
        th {{ font-weight: 700; letter-spacing: 0.4px; }}
        td {{ font-variant-numeric: tabular-nums; }}

        /* ═════════ CÓDIGO ═════════ */
        code, pre, kbd, samp {{
            font-family: var(--font-codigo) !important;
        }}

        /* ═════════ LAYOUT ═════════ */
        .main .block-container {{
            padding-top: 1rem;
            max-width: 1400px;
        }}

        /* ═════════ SCROLLBAR ═════════ */
        ::-webkit-scrollbar       {{ width: 10px; height: 10px; }}
        ::-webkit-scrollbar-track {{ background: #F1F5F9; }}
        ::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 5px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}

        /* ═════════════════════════════════════════════════
        🎨 HERO CORPORATIVO — AZUL + LARANJA
        ═════════════════════════════════════════════════ */
        .hero-corp {{
            background: linear-gradient(
                120deg,
                #012869 0%,
                #023A9E 35%,
                #1E5FCC 55%,
                #E85D04 82%,
                #F37C04 100%
            );
            padding: 34px 44px;
            border-radius: var(--radius-lg);
            color: white;
            box-shadow:
                0 10px 40px rgba(1, 40, 105, 0.30),
                inset 0 1px 0 rgba(255,255,255,0.15);
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.10);
            min-height: 120px;
        }}
        .hero-corp::before {{
            content: '';
            position: absolute;
            top: 50%; right: -100px;
            transform: translateY(-50%);
            width: 420px; height: 420px;
            background: radial-gradient(
                circle at center,
                rgba(255,180,90,0.35) 0%,
                rgba(243,124,4,0.20) 35%,
                rgba(232,93,4,0.08) 60%,
                transparent 78%
            );
            border-radius: 50%;
            pointer-events: none;
            filter: blur(2px);
        }}
        .hero-corp::after {{
            content: '';
            position: absolute;
            top: 0; left: 30%;
            width: 35%; height: 100%;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255,255,255,0.06) 40%,
                rgba(255,255,255,0.14) 50%,
                rgba(255,255,255,0.06) 60%,
                transparent 100%
            );
            transform: skewX(-18deg);
            pointer-events: none;
        }}
        .hero-content {{ position: relative; z-index: 2; }}
        .hero-title {{
            font-size: 36px;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.8px;
            font-family: var(--font-titulo) !important;
            color: #FFFFFF;
            text-shadow:
                0 2px 4px rgba(0,0,0,0.45),
                0 1px 2px rgba(0,0,0,0.30),
                0 0 24px rgba(255,255,255,0.15);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .hero-subtitle {{
            font-size: 14px;
            opacity: 0.95;
            margin: 8px 0 0 0;
            font-weight: 400;
            color: #F8FAFC;
            text-shadow: 0 1px 3px rgba(0,0,0,0.40);
            letter-spacing: 0.3px;
        }}
        .hero-badge {{
            display: inline-block;
            background: linear-gradient(
                135deg,
                rgba(255,255,255,0.25) 0%,
                rgba(255,255,255,0.10) 100%
            );
            padding: 5px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            margin-top: 12px;
            letter-spacing: 0.6px;
            text-transform: uppercase;
            color: #FFFFFF;
            border: 1px solid rgba(255,255,255,0.30);
            backdrop-filter: blur(10px);
            box-shadow:
                0 2px 8px rgba(0,0,0,0.20),
                inset 0 1px 0 rgba(255,255,255,0.25);
        }}

        /* ═════════ KPI CARDS ═════════ */
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

        /* ═════════ SEÇÕES ═════════ */
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

        /* ═════════ MATERIAL ICONS OVERRIDE ═════════ */
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
            font-size: 16px !important;
            width: 16px !important;
            height: 16px !important;
        }}
        </style>
        """

    st.markdown(css, unsafe_allow_html=True)


# ====================================================
# API PÚBLICA
# ====================================================
def aplicar_estilo() -> None:
    """
    Aplica fonte corporativa, tema Plotly e CSS global.

    Reinjeta a cada rerun/página — não usa cache de sessão porque
    o Streamlit descarta CSS entre navegações de páginas.
    """
    _configurar_plotly_global()
    _injetar_fontes_no_head_pai()
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
    """
    Converte marcadores markdown inline básicos para HTML.
    Suporta **negrito**, *itálico*, `código`.
    """
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    return texto


# ====================================================
# COMPONENTES
# ====================================================
def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    """Hero corporativo com gradiente azul → laranja."""
    if not titulo:
        raise ValueError("render_hero: 'titulo' não pode ser vazio.")

    subtitulo_html = f'<p class="hero-subtitle">{subtitulo}</p>' if subtitulo else ""
    badge_html = f'<span class="hero-badge">{badge}</span>' if badge else ""

    html = (
        f'<div class="hero-corp">'
        f'<div class="hero-content">'
        f'<h1 class="hero-title">{titulo}</h1>'
        f'{subtitulo_html}'
        f'{badge_html}'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_section(titulo: str, divider: str = "gray") -> None:
    st.subheader(titulo, divider=divider)  # type: ignore[arg-type]


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
    """
    Caixa de insight/alerta. Aceita markdown inline: **negrito**, *itálico*, `código`.
    """
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


def render_dataframe(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    height: int = 400,
    fmt: FmtDict | None = None,
    **kwargs: Any,
) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Esperado pd.DataFrame, recebido {type(df).__name__}.")

    if df.empty:
        st.info("Nenhum dado disponível para exibição.")
        return

    if titulo:
        st.markdown(f"**{icone} {titulo}**")

    if fmt:
        fmt_valido: FmtDict = {c: f for c, f in fmt.items() if c in df.columns}
        if fmt_valido:
            try:
                st.dataframe(
                    df.style.format(fmt_valido),  # type: ignore[arg-type]
                    height=height,
                    use_container_width=True,
                    hide_index=True,
                    **kwargs,
                )
                return
            except Exception:
                logger.exception("Falha ao formatar. Exibindo sem formatação.")

    st.dataframe(df, height=height, use_container_width=True, hide_index=True, **kwargs)
