"""
componentes.py
==============
Módulo central unificado de estilos, fontes, componentes reutilizáveis,
visualizações gráficas padronizadas e Design System do Sidebar TOTALE.

Uso em qualquer página:
    from componentes import (
        aplicar_estilo, aplicar_sidebar_corp, render_kpi, render_table_html, ...
    )
    aplicar_estilo()
"""

from __future__ import annotations

import logging
import re
import textwrap
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
from zoneinfo import ZoneInfo
from html import escape

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
TipoTemaBrand = Literal["gradiente", "clean", "minimalista"]
TipoAmbiente = Literal[
    "produção",
    "homologação",
    "desenvolvimento",
    "producao",
    "homologacao",
    "prod",
    "homo",
    "dev",
]

CellFormatter = Union[str, Callable[[Any], str]]
FmtDict = Dict[str, Union[CellFormatter, None]]

ColorRule = Tuple[Callable[[Any], bool], str]
ColorMapDict = Dict[str, List[ColorRule]]

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

# ─ Sidebar
SB_FUNDO = "#EEF2F7"
SB_FUNDO_LINK = "#FFFFFF"
SB_FUNDO_LINK_HOVER = "#F8FAFC"
SB_FUNDO_ATIVO = "#FFF7ED"
SB_BORDA_ATIVA = "#F37C04"
SB_TITULO_SECAO = "#012869"
SB_TEXTO_LINK = "#1F2937"
SB_TEXTO_MUTED = "#64748B"
SB_BORDA_SUTIL = "#D9E0E9"

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
    js = textwrap.dedent(f"""
        <script>
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
        </script>
    """)
    components.html(js, height=0)


@st.cache_data
def _get_global_css() -> str:
    """Retorna o CSS Global Corporativo (cacheado para performance)."""
    links_html = "\n".join(
        f'<link rel="stylesheet" href="{url}">' for url in _GOOGLE_FONTS_URLS
    )

    css = textwrap.dedent(f"""
        {links_html}
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700;800;900&display=swap');
        @import url('https://fonts.googleapis.com/icon?family=Material+Icons');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

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

        html, body, p, label, li, a, button, input, select, textarea, [class*="st-"] {{ font-family: var(--font-texto) !important; }}
        h1, h2, h3, h4, h5, h6, .hero-title, .section-title, .kpi-value, [data-testid="stMetricValue"] {{ font-family: var(--font-titulo) !important; font-weight: 700; letter-spacing: -0.3px; }}
        code, pre, kbd, samp {{ font-family: var(--font-codigo) !important; }}

        /* Icones */
        [data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded, .material-symbols-outlined {{
            font-family: "Material Symbols Rounded", "Material Icons" !important;
            font-weight: normal !important; font-style: normal !important; font-size: 20px !important;
            line-height: 1 !important; text-transform: none !important; white-space: nowrap !important;
            font-feature-settings: "liga" 1 !important; -webkit-font-smoothing: antialiased !important;
            display: inline-flex !important; align-items: center !important; justify-content: center !important;
        }}

        .main .block-container {{ padding-top: 1rem; max-width: 1400px; }}

        /* Sidebar Base */
        section[data-testid="stSidebar"] {{
            background-color: {SB_FUNDO} !important; border-right: 1px solid {SB_BORDA_SUTIL} !important;
            box-shadow: 2px 0 12px rgba(1, 40, 105, 0.06) !important;
        }}
        section[data-testid="stSidebar"] > div:first-child, section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{ background: transparent !important; }}
        
        /* Scrollbar */
        section[data-testid="stSidebar"] ::-webkit-scrollbar {{ width: 5px !important; background: transparent !important; }}
        section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{ background: {SB_BORDA_SUTIL} !important; border-radius: 20px !important; }}
        section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {{ background: {SB_TEXTO_MUTED} !important; }}

        /* Menu */
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a {{
            background-color: {SB_FUNDO_LINK} !important; border: 1px solid {SB_BORDA_SUTIL} !important;
            border-left: 3px solid transparent !important; border-radius: 6px !important; margin: 3px 10px !important;
            padding: 8px 12px !important; box-shadow: 0 1px 2px rgba(1, 40, 105, 0.04) !important;
            transition: all 0.18s ease !important; display: flex !important; flex-direction: column !important;
            align-items: center !important; justify-content: center !important; gap: 2px !important; min-height: 58px !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a:hover {{ background-color: {SB_FUNDO_LINK_HOVER} !important; border-color: {COR_BORDA} !important; transform: translateX(2px); }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li a[aria-current="page"] {{ background-color: {SB_FUNDO_ATIVO} !important; border-left: 3px solid {SB_BORDA_ATIVA} !important; border-color: {SB_BORDA_SUTIL} !important; box-shadow: 0 2px 6px rgba(243, 124, 4, 0.12) !important; }}
        
        /* Heros e Visuals Gerais continuam idênticos ao original */
        .hero-totale-1 {{ background: linear-gradient(to right, rgb(1,40,105) 0%, rgb(243,124,4) 100%); padding: 3rem 2.5rem; border-radius: var(--radius-md); color: #FFFFFF; position: relative; overflow: hidden; box-shadow: var(--shadow-md); }}
        .hero-totale-1::after {{ content: ''; position: absolute; top: -50%; left: -60%; width: 30%; height: 200%; background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.25) 50%, rgba(255,255,255,0) 100%); transform: rotate(25deg); animation: feixeLuz 6s infinite ease-in-out; }}
        @keyframes feixeLuz {{ 0% {{ left: -60%; }} 30%, 100% {{ left: 130%; }} }}
        
        .kpi-card {{ background: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%); border-radius: var(--radius-md); padding: 20px 24px; box-shadow: var(--shadow-sm); border-top: 1px solid #F3F4F6; transition: transform 0.2s ease, box-shadow 0.2s ease; }}
        .kpi-card:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-md); }}
        .kpi-card .kpi-label {{ font-size: 12px; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; }}
        .kpi-card .kpi-value {{ font-size: 1.85rem; font-weight: 700; margin: 4px 0; }}
        .kpi-card .kpi-sub {{ font-size: 12px; color: #94A3B8; }}

        /* Tabelas */
        .corp-table-wrap {{ width: 100%; overflow: auto; border: 1px solid var(--cor-borda); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); background: #FFFFFF; }}
        table.corp-table {{ width: 100%; border-collapse: separate; border-spacing: 0; }}
        .corp-table thead th {{ font-family: var(--font-titulo) !important; font-weight: 700; font-size: 11px; text-transform: uppercase; color: #1F2937; background: #F8FAFC; padding: 10px 14px; border-bottom: 2px solid var(--cor-borda); text-align: left; position: sticky; top: 0; z-index: 2; white-space: nowrap; }}
        .corp-table tbody td {{ font-weight: 500; font-size: 11px; color: #374151; padding: 8px 14px; border-bottom: 1px solid #F3F4F6; white-space: nowrap; }}
        .corp-table tbody tr:hover td {{ background: #F8FAFC !important; }}
        .corp-table td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .corp-table tr.total-row td {{ background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%) !important; color: #FFFFFF !important; font-weight: 800 !important; border-top: 2px solid var(--cor-secundaria) !important; }}
        </style>
    """)
    return css


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


def _safe_float(val: Any) -> float:
    """Extrai e converte segurança strings numéricas e porcentagens para float."""
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s_val = str(val).strip()
        if s_val == "—" or not s_val:
            return 0.0
        if s_val.endswith("%"):
            return (
                float(s_val.removesuffix("%").replace(".", "").replace(",", ".")) / 100
            )
        return float(s_val.replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


# ====================================================
# HEROS CORPORATIVOS
# ====================================================
def render_hero_totale_1(
    titulo: str = "Portal TOTALE", subtitulo: str = "Painéis de Produção"
) -> None:
    if not titulo:
        return
    html = textwrap.dedent(f"""
        <div class="hero-totale-1"><div class="hero-t1-content">
        <h1 class="hero-t1-title">{escape(titulo)}</h1>
        <p class="hero-t1-sub">{escape(subtitulo)}</p>
        </div></div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_hero_totale_2(
    titulo: str, subtitulo: str = "", badge_texto: str = "", badge_tipo: str = "laranja"
) -> None:
    if not titulo:
        return
    cls_badge = "badge-laranja" if badge_tipo.lower() == "laranja" else "badge-azul"
    html_badge = (
        f'<span class="hero-t2-badge {cls_badge}">{escape(badge_texto)}</span>'
        if badge_texto
        else ""
    )
    html = textwrap.dedent(f"""
        <div class="hero-totale-2"><div class="hero-t2-container">
        <h1 class="hero-t2-title">{escape(titulo)}</h1>
        <p class="hero-t2-sub">{escape(subtitulo)}</p>{html_badge}
        </div></div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_hero_migracao(
    titulo: str = "🔄 Migração", subtitulo: str = "Análise estratégica"
) -> None:
    if not titulo:
        return
    html = textwrap.dedent(f"""
        <div class="hero-migracao" style="background: linear-gradient(135deg, #024B7A 0%, #027BBF 100%); padding: 2.2rem 2.5rem; border-radius: 16px; color: white;">
        <div class="hero-t1-content">
        <h1 class="hero-alt-title" style="font-family: var(--font-titulo); font-size: 2.1rem; margin:0;">{titulo}</h1>
        <p class="hero-alt-sub" style="margin-top: 1rem; opacity: 0.88;">{subtitulo}</p>
        </div></div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_hero_pme(
    titulo: str = "🏢 PME", subtitulo: str = "Pequenas e Médias Empresas"
) -> None:
    if not titulo:
        return
    html = textwrap.dedent(f"""
        <div class="hero-pme" style="background: linear-gradient(135deg, #4A1D96 0%, #8B42F6 100%); padding: 2.2rem 2.5rem; border-radius: 16px; color: white;">
        <div class="hero-t1-content">
        <h1 class="hero-alt-title" style="font-family: var(--font-titulo); font-size: 2.1rem; margin:0;">{titulo}</h1>
        <p class="hero-alt-sub" style="margin-top: 1rem; opacity: 0.88;">{subtitulo}</p>
        </div></div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    """Função legada."""
    extra = f" · {badge}" if badge else ""
    render_hero_totale_1(titulo, f"{subtitulo}{extra}".strip(" ·"))


# ====================================================
# KPIs
# ====================================================
def render_kpi(
    col: Any, label: str, valor: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    cor = _resolver_cor_tema(tema)
    html = textwrap.dedent(f"""
        <div class="kpi-card" style="border-left: 4px solid {cor};">
        <div class="kpi-label">{escape(label)}</div>
        <div class="kpi-value" style="color:{cor};">{escape(str(valor))}</div>
        <div class="kpi-sub">{escape(sub)}</div>
        </div>
    """)
    (col.markdown if hasattr(col, "markdown") else st.markdown)(
        html, unsafe_allow_html=True
    )


def render_kpi_sm(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
    icone: str = "",
) -> None:
    cor = _resolver_cor_tema(tema)
    html_icone = (
        f'<span style="font-size:13px; margin-left:4px;">{icone}</span>'
        if icone
        else ""
    )
    html = textwrap.dedent(f"""
        <div class="kpi-card-sm" style="border-left: 3px solid {cor};">
        <div class="kpi-label"><span>{escape(label)}</span>{html_icone}</div>
        <div class="kpi-value" style="color:{cor};">{escape(str(valor))}</div>
        {f'<div class="kpi-sub">{escape(sub)}</div>' if sub else ''}
        </div>
    """)
    (col.markdown if hasattr(col, "markdown") else st.markdown)(
        html, unsafe_allow_html=True
    )


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
    cor = _resolver_cor_tema(tema)
    if tendencia is None:
        tendencia = "up" if delta > 0.01 else "down" if delta < -0.01 else "flat"

    icones = {"up": "▲", "down": "▼", "flat": "▬"}
    classes = {"up": "kpi-delta-up", "down": "kpi-delta-down", "flat": "kpi-delta-flat"}

    classe = classes[tendencia]
    if inverter_cor:
        classe = (
            "kpi-delta-down"
            if tendencia == "up"
            else "kpi-delta-up" if tendencia == "down" else "kpi-delta-flat"
        )

    delta_txt = f"{'+' if delta > 0 else ''}{_fmt_br(delta)}{delta_sufixo}"

    html = textwrap.dedent(f"""
        <div class="kpi-card-delta" style="border-top-color:{cor};">
        <div class="kpi-delta-header">
        <span class="kpi-delta-label">{escape(label)}</span>
        <span class="kpi-delta-indicator {classe}">{icones[tendencia]} {delta_txt}</span>
        </div>
        <div class="kpi-delta-value" style="color:{cor};">{escape(str(valor))}</div>
        </div>
    """)
    (col.markdown if hasattr(col, "markdown") else st.markdown)(
        html, unsafe_allow_html=True
    )


# ====================================================
# INSIGHTS & UTILS
# ====================================================
def render_insight(msg: str, tipo: TipoInsight = "info") -> None:
    if not msg:
        return
    bg, texto, borda, icone = _INSIGHT_CONFIG.get(tipo, _INSIGHT_CONFIG["info"])
    msg_html = _markdown_inline_para_html(escape(msg))
    html = textwrap.dedent(f"""
        <div style="background:{bg};color:{texto};border-left:4px solid {borda};padding:12px 16px;border-radius:6px;margin:10px 0;font-size:14px;line-height:1.6;">
        <span style="margin-right:8px;">{icone}</span>{msg_html}
        </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_empty_state(
    titulo: str = "Sem dados", mensagem: str = "", icone: str = "📭"
) -> None:
    html = textwrap.dedent(f"""
        <div class="empty-state" style="text-align:center;padding:48px 24px;background:#FAFBFC;border:2px dashed var(--cor-borda);border-radius:12px;">
        <div class="empty-state-icon" style="font-size:48px;opacity:0.6;">{icone}</div>
        <div class="empty-state-title" style="font-weight:700;color:#374151;margin-top:12px;">{escape(titulo)}</div>
        <div class="empty-state-msg" style="color:#6B7280;font-size:13px;">{escape(mensagem)}</div>
        </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_section_header(
    titulo: str,
    subtitulo: str = "",
    icone: str = "",
    badge: str = "",
    badge_tipo: TipoBadge = "laranja",
    cor_accent: str = COR_SECUNDARIA,
) -> None:
    if not titulo:
        return
    html = textwrap.dedent(f"""
        <div style="margin-top:2.2rem; margin-bottom:1.6rem;">
        <div style="display:flex;align-items:center;flex-wrap:wrap;">
        <h2 style="font-family:var(--font-titulo);font-size:22px;font-weight:800;color:{COR_PRIMARIA};margin:0;display:flex;align-items:center;">
        {f'<span style="margin-right:10px;">{icone}</span>' if icone else ''}{escape(titulo)}
        </h2>
        {f'<span style="margin-left:10px;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:700;background:#FFF7ED;color:#C2410C;border:1px solid #FDBA74;">{escape(badge)}</span>' if badge else ''}
        </div>
        {f'<div style="font-family:var(--font-titulo);font-size:18px;color:{COR_PRIMARIA};font-weight:bold;">{escape(subtitulo)}</div>' if subtitulo else ''}
        <div style="height:3px;width:45px;background:{cor_accent};border-radius:2px;margin-top:10px;"></div>
        </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


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
    num_cols: List[str] | None = None,
    max_cols: int = 20,
    linha_total: bool = False,
    condicao_cores: CondicaoCoresConfig | None = None,
    destaque_col: Dict[str, Any] | None = None,
    condicoes_colunas: Dict[str, Any] | None = None,
    linha_destaque: Dict[str, Any] | None = None,
    hide_index: bool = True,
    **kwargs: Any,
) -> None:
    """Renderiza uma tabela HTML corporativa e responsiva."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        render_empty_state("Sem dados na tabela", "Ajuste os filtros.")
        return

    cols = list(df.columns[:max_cols])
    df_show = df.loc[:, cols].head(max_rows).copy()

    if titulo:
        st.markdown(
            f'<div style="font-weight:700;font-size:16px;color:{COR_PRIMARIA};margin-bottom:8px;">{icone} {escape(titulo)}</div>',
            unsafe_allow_html=True,
        )

    num_set = set(
        num_cols or [c for c in _detectar_colunas_numericas(df_show) if c in cols]
    )
    df_show = df_show.fillna("—")

    # Applica formatação de forma vetorizada onde possível
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

    # Renderiza Linhas HTML
    html_rows = []

    # Pre-computa linha destaque config
    destaque_coluna_alvo = linha_destaque.get("coluna") if linha_destaque else None
    destaque_valor_alvo = (
        str(linha_destaque.get("valor")).upper() if linha_destaque else None
    )

    for _, row in display.iterrows():
        cells = []
        is_linha_destaque = (
            destaque_coluna_alvo
            and str(row.get(destaque_coluna_alvo, "")).upper() == destaque_valor_alvo
        )

        for c in cols:
            val_raw = row[c]
            val = escape(str(val_raw)) if val_raw != "—" else "—"
            style_parts = []

            # Lógica de destaque da linha inteira (ex: TOTAL GERAL)
            if is_linha_destaque:
                if c == destaque_coluna_alvo:
                    style_parts.append(
                        "background:linear-gradient(90deg,#012869 0%,#1E40AF 100%);color:white;font-weight:800;text-align:left;padding-left:16px;"
                    )
                else:
                    style_parts.append(
                        "background-color:#F8FAFC;font-weight:700;text-align:left;padding-left:16px;border-right:2px solid #E2E8F0;"
                    )

            # Lógica de destaque de Coluna Específica (fundo colorido)
            elif destaque_col and c == destaque_col.get("coluna"):
                if val_raw != "—":
                    bg_col = destaque_col.get("bg", "#1E293B")
                    txt_col = destaque_col.get("text", "#FFFFFF")
                    b_weight = "800" if destaque_col.get("bold", True) else "500"
                    style_parts.append(
                        f"background-color:{bg_col};color:{txt_col};font-weight:{b_weight};"
                    )

            # Lógica de Heatmap condicional (abaixo/acima de meta - Condição Cores)
            elif condicao_cores and c == condicao_cores.get("coluna"):
                v = _safe_float(val_raw)
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

            # Condições Colunas (usado em matriz)
            elif condicoes_colunas and c in condicoes_colunas:
                v = _safe_float(val_raw)
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

            # Legado Color Rules
            elif color_rules and c in color_rules:
                for rule, color in color_rules[c]:
                    if rule(val_raw):
                        style_parts.append(f"color:{color};font-weight:600;")
                        break

            # Alinhamento Numérico
            if c in num_set and val_raw != "—" and not is_linha_destaque:
                style_parts.append(
                    "text-align:right;font-variant-numeric:tabular-nums;"
                )

            style = "".join(style_parts)
            cells.append(f'<td style="{style}">{val}</td>')

        html_rows.append(f"<tr>{''.join(cells)}</tr>")

    # Linha Total
    if linha_total and not df_show.empty:
        total_cells = []
        for c in cols:
            if c in num_set:
                try:
                    total = pd.to_numeric(
                        df_show[c].replace(r"[^\d.-]", "", regex=True), errors="coerce"
                    ).sum()
                    total_cells.append(f'<td class="num">{_fmt_br(total)}</td>')
                except:
                    total_cells.append("<td>—</td>")
            else:
                total_cells.append("<td><strong>TOTAL</strong></td>")
        html_rows.append(f'<tr class="total-row">{"".join(total_cells)}</tr>')

    headers_html = "".join(f"<th>{escape(c)}</th>" for c in cols)

    html = textwrap.dedent(f"""
        <div class="corp-table-wrap" style="max-height:{height}px;overflow-y:auto;">
        <table class="corp-table">
        <thead><tr>{headers_html}</tr></thead>
        <tbody>{"".join(html_rows)}</tbody>
        </table></div>
    """)
    st.markdown(html, unsafe_allow_html=True)


# ====================================================
# SIDEBAR CORPORATIVA
# ====================================================
def aplicar_sidebar_corp(
    logo_url: str = "",
    nome_empresa: str = "TOTALE",
    subtitulo: str = "Inteligência Corporativa",
    versao: str = "",
    ambiente: Literal["produção", "homologação", "desenvolvimento"] = "produção",
    mostrar_data: bool = True,
    divider: bool = True,
) -> None:
    """
    Configura e renderiza o cabeçalho corporativo completo da sidebar.

    Parameters
    ----------
    logo_url : str
        URL da imagem do logotipo. Se vazio, usa ícone Material Symbols.
    nome_empresa : str
        Nome exibido no topo da sidebar.
    subtitulo : str
        Linha secundária abaixo do nome.
    versao : str
        Tag de versão (ex: ``"v2.4.1"``). Se vazio, omite o badge.
    ambiente : str
        ``"produção"`` | ``"homologação"`` | ``"desenvolvimento"``.
        Controla a cor do badge de ambiente.
    mostrar_data : bool
        Exibe a data/hora atual (fuso de São Paulo) no rodapé do header.
    divider : bool
        Insere um separador horizontal após o header.

    Exemplo
    -------
    >>> aplicar_sidebar_corp(
    ...     nome_empresa="TOTALE",
    ...     subtitulo="Painel de Produção",
    ...     versao="v3.1.0",
    ...     ambiente="produção",
    ... )
    """

    # ── CSS adicional específico da sidebar ──────────────────
    css_sidebar = textwrap.dedent(f"""
        <style>
        /* ── Header Corporativo da Sidebar ── */
        .sb-corp-header {{
            padding: 20px 16px 14px;
            margin: -10px -16px 0;
            background: linear-gradient(160deg, {COR_PRIMARIA} 0%, #0A3A8A 60%, #124DB5 100%);
            border-radius: 0 0 14px 14px;
            position: relative;
            overflow: hidden;
        }}
        .sb-corp-header::before {{
            content: '';
            position: absolute;
            top: -40%;
            right: -25%;
            width: 120px;
            height: 120px;
            background: radial-gradient(circle, rgba(243,124,4,0.18) 0%, transparent 70%);
            border-radius: 50%;
        }}
        .sb-corp-header::after {{
            content: '';
            position: absolute;
            bottom: -30%;
            left: -15%;
            width: 90px;
            height: 90px;
            background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
            border-radius: 50%;
        }}
        .sb-corp-logo-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            position: relative;
            z-index: 1;
        }}
        .sb-corp-logo-img {{
            width: 36px;
            height: 36px;
            object-fit: contain;
            border-radius: 8px;
            background: rgba(255,255,255,0.12);
            padding: 4px;
        }}
        .sb-corp-logo-icon {{
            width: 36px;
            height: 36px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.12);
            border-radius: 8px;
            font-size: 22px;
            color: {COR_SECUNDARIA};
        }}
        .sb-corp-nome {{
            font-family: {FONTE_TITULO} !important;
            font-size: 18px;
            font-weight: 800;
            color: #FFFFFF;
            letter-spacing: -0.3px;
            line-height: 1.15;
        }}
        .sb-corp-sub {{
            font-family: {FONTE_TEXTO} !important;
            font-size: 11px;
            font-weight: 500;
            color: rgba(255,255,255,0.65);
            margin-top: 2px;
            letter-spacing: 0.3px;
        }}
        .sb-corp-badges {{
            display: flex;
            align-items: center;
            gap: 6px;
            margin-top: 10px;
            position: relative;
            z-index: 1;
        }}
        .sb-badge {{
            font-family: {FONTE_TEXTO} !important;
            font-size: 9.5px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 10px;
            letter-spacing: 0.4px;
            text-transform: uppercase;
            line-height: 1.5;
        }}
        .sb-badge-versao {{
            background: rgba(255,255,255,0.14);
            color: rgba(255,255,255,0.85);
            border: 1px solid rgba(255,255,255,0.15);
        }}
        .sb-badge-prod {{
            background: rgba(5,150,105,0.2);
            color: #6EE7B7;
            border: 1px solid rgba(5,150,105,0.3);
        }}
        .sb-badge-homo {{
            background: rgba(245,158,11,0.2);
            color: #FCD34D;
            border: 1px solid rgba(245,158,11,0.3);
        }}
        .sb-badge-dev {{
            background: rgba(139,92,246,0.2);
            color: #C4B5FD;
            border: 1px solid rgba(139,92,246,0.3);
        }}
        .sb-corp-data {{
            font-family: {FONTE_TEXTO} !important;
            font-size: 10px;
            color: rgba(255,255,255,0.45);
            margin-top: 8px;
            position: relative;
            z-index: 1;
        }}
        .sb-corp-divider {{
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, {SB_BORDA_SUTIL} 30%, {SB_BORDA_SUTIL} 70%, transparent 100%);
            margin: 14px 10px 10px;
        }}

        /* ── Status Card da Sidebar ── */
        .sb-status-card {{
            background: #FFFFFF;
            border: 1px solid {SB_BORDA_SUTIL};
            border-radius: 10px;
            padding: 12px 14px;
            margin: 6px 10px;
            box-shadow: 0 1px 4px rgba(1,40,105,0.04);
        }}
        .sb-status-card-compacto {{
            padding: 8px 12px;
            margin: 4px 10px;
        }}
        .sb-status-row {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .sb-status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
            position: relative;
        }}
        .sb-status-dot::after {{
            content: '';
            position: absolute;
            inset: -3px;
            border-radius: 50%;
            opacity: 0.25;
        }}
        .sb-status-dot-ativo {{ background: {COR_SUCESSO}; }}
        .sb-status-dot-ativo::after {{ background: {COR_SUCESSO}; }}
        .sb-status-dot-inativo {{ background: {COR_NEUTRO}; }}
        .sb-status-dot-inativo::after {{ background: {COR_NEUTRO}; }}
        .sb-status-dot-pendente {{ background: {COR_ATENCAO}; }}
        .sb-status-dot-pendente::after {{ background: {COR_ATENCAO}; animation: sbPulse 2s infinite; }}
        .sb-status-dot-sucesso {{ background: {COR_SUCESSO}; }}
        .sb-status-dot-sucesso::after {{ background: {COR_SUCESSO}; }}
        .sb-status-dot-erro {{ background: {COR_ALERTA}; }}
        .sb-status-dot-erro::after {{ background: {COR_ALERTA}; animation: sbPulse 1.2s infinite; }}
        @keyframes sbPulse {{
            0%, 100% {{ transform: scale(1); opacity: 0.25; }}
            50% {{ transform: scale(1.6); opacity: 0; }}
        }}
        .sb-status-label {{
            font-family: {FONTE_TEXTO} !important;
            font-size: 12px;
            font-weight: 600;
            color: {COR_TEXTO};
            flex: 1;
        }}
        .sb-status-tag {{
            font-family: {FONTE_TEXTO} !important;
            font-size: 10px;
            font-weight: 700;
            padding: 1px 7px;
            border-radius: 8px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .sb-status-desc {{
            font-family: {FONTE_TEXTO} !important;
            font-size: 10.5px;
            color: {COR_TEXTO_3};
            margin-top: 6px;
            line-height: 1.45;
        }}
        .sb-status-meta {{
            display: flex;
            flex-direction: column;
            gap: 3px;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #F1F5F9;
        }}
        .sb-status-meta-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .sb-status-meta-key {{
            font-family: {FONTE_TEXTO} !important;
            font-size: 10px;
            color: {COR_TEXTO_3};
            font-weight: 500;
        }}
        .sb-status-meta-val {{
            font-family: {FONTE_CODIGO} !important;
            font-size: 10px;
            color: {COR_TEXTO_2};
            font-weight: 500;
        }}
        .sb-status-atualizacao {{
            font-family: {FONTE_TEXTO} !important;
            font-size: 9.5px;
            color: {SB_TEXTO_MUTED};
            margin-top: 6px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        </style>
    """)
    st.sidebar.markdown(css_sidebar, unsafe_allow_html=True)

    # ── Badge de ambiente ────────────────────────────────────
    amb_map = {
        "produção": ("sb-badge-prod", "PROD"),
        "homologação": ("sb-badge-homo", "HOMO"),
        "desenvolvimento": ("sb-badge-dev", "DEV"),
    }
    amb_cls, amb_txt = amb_map.get(ambiente, amb_map["produção"])

    badges_html = f'<span class="sb-badge {amb_cls}">{amb_txt}</span>'
    if versao:
        badges_html += f'<span class="sb-badge sb-badge-versao">{escape(versao)}</span>'

    # ── Logo ─────────────────────────────────────────────────
    if logo_url:
        logo_html = (
            f'<img class="sb-corp-logo-img" src="{escape(logo_url)}" alt="logo">'
        )
    else:
        logo_html = (
            '<span class="sb-corp-logo-icon">'
            '<span class="material-symbols-rounded">dashboard</span>'
            "</span>"
        )

    # ── Data/hora ────────────────────────────────────────────
    data_html = ""
    if mostrar_data:
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        data_html = (
            f'<div class="sb-corp-data">'
            f'<span class="material-symbols-rounded" '
            f'style="font-size:12px;vertical-align:middle;margin-right:2px;">schedule</span>'
            f'{agora.strftime("%d/%m/%Y · %H:%M")}'
            f"</div>"
        )

    # ── Divider ──────────────────────────────────────────────
    divider_html = '<hr class="sb-corp-divider">' if divider else ""

    # ── Renderização ─────────────────────────────────────────
    html = textwrap.dedent(f"""
        <div class="sb-corp-header">
            <div class="sb-corp-logo-row">
                {logo_html}
                <div>
                    <div class="sb-corp-nome">{escape(nome_empresa)}</div>
                    <div class="sb-corp-sub">{escape(subtitulo)}</div>
                </div>
            </div>
            <div class="sb-corp-badges">{badges_html}</div>
            {data_html}
        </div>
        {divider_html}
    """)
    st.sidebar.markdown(html, unsafe_allow_html=True)


from datetime import datetime
from html import escape
import textwrap
from typing import Dict, Literal, Tuple, Union
from zoneinfo import ZoneInfo
import streamlit as st


def render_sidebar_status(
    status: TipoStatus = "ativo",
    label: str = "Sistema",
    descricao: str = "",
    tag_customizada: str = "",
    ultima_atualizacao: str | datetime | None = None,
    dados: Dict[str, str] | None = None,
    compacto: bool = False,
) -> None:
    """Renderiza um cartão de status na sidebar com indicador visual pulsante

    e suporte a tags customizadas.

    Parameters
    ----------
    status : TipoStatus
        ``"ativo"`` | ``"inativo"`` | ``"pendente"`` | ``"sucesso"`` | ``"erro"``.
        Controla a cor e a animação do indicador visual.
    label : str
        Texto principal do status (ex: ``"Base de Dados"``, ``"Robô Local"``).
    descricao : str
        Linha explicativa opcional exibida abaixo do label.
    tag_customizada : str
        Texto personalizado para a etiqueta no canto superior direito
        (ex: ``"EM DIA"``, ``"SINC"``, ``"98% SLA"``). Se vazio, utiliza
        o rótulo padrão do status (``"Online"``, ``"Pendente"``, etc.).
    ultima_atualizacao : str | datetime | None
        Timestamp da última atualização. Se ``datetime``, formata
        automaticamente no fuso de São Paulo. Se ``None``, omite.
    dados : dict | None
        Pares chave-valor adicionais exibidos como metadados
        (ex: ``{"Linhas": "12.450", "Tamanho": "1.2 MB"}``).
    compacto : bool
        Se ``True``, reduz o padding e omite a descrição/metadados.

    Exemplo
    -------
    >>> render_sidebar_status(
    ...     status="ativo",
    ...     label="Sincronismo ETL",
    ...     tag_customizada="EM DIA",
    ...     descricao="Base carregada via Robô Local",
    ...     dados={"Arquivo": "Atividades-2024.csv", "Linhas": "45.100"},
    ...     ultima_atualizacao=datetime.now(),
    ... )
    """

    # ── Cores e texto padrão do tag de status ────────────────
    tag_cfg: Dict[str, Tuple[str, str, str]] = {
        "ativo": ("#D1FAE5", "#065F46", "Online"),
        "inativo": ("#F1F5F9", "#475569", "Offline"),
        "pendente": ("#FEF3C7", "#92400E", "Pendente"),
        "sucesso": ("#D1FAE5", "#065F46", "OK"),
        "erro": ("#FEE2E2", "#991B1B", "Erro"),
    }
    tag_bg, tag_fg, tag_txt_padrao = tag_cfg.get(status, tag_cfg["inativo"])

    # Define o texto final da tag (customizado ou padrão)
    tag_txt = (
        escape(tag_customizada.strip()) if tag_customizada.strip() else tag_txt_padrao
    )

    # ── Timestamp ────────────────────────────────────────────
    atualizacao_html = ""
    if ultima_atualizacao is not None:
        if isinstance(ultima_atualizacao, datetime):
            ts = (
                ultima_atualizacao
                if ultima_atualizacao.tzinfo
                else ultima_atualizacao.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
            )
            ts_str = ts.strftime("%d/%m %H:%M:%S")
        else:
            ts_str = str(ultima_atualizacao)
        atualizacao_html = (
            f'<div class="sb-status-atualizacao">'
            f'<span class="material-symbols-rounded" style="font-size:11px;">update</span>'
            f"Atualizado em {escape(ts_str)}"
            f"</div>"
        )

    # ── Descrição ────────────────────────────────────────────
    desc_html = ""
    if descricao and not compacto:
        desc_html = f'<div class="sb-status-desc">{escape(descricao)}</div>'

    # ── Metadados ────────────────────────────────────────────
    meta_html = ""
    if dados and not compacto:
        rows = "".join(
            f'<div class="sb-status-meta-row">'
            f'<span class="sb-status-meta-key">{escape(k)}</span>'
            f'<span class="sb-status-meta-val">{escape(str(v))}</span>'
            f"</div>"
            for k, v in dados.items()
        )
        meta_html = f'<div class="sb-status-meta">{rows}</div>'

    # ── Classe compacto ──────────────────────────────────────
    cls_extra = " sb-status-card-compacto" if compacto else ""

    # ── Renderização HTML ────────────────────────────────────
    html = textwrap.dedent(f"""
        <div class="sb-status-card{cls_extra}">
            <div class="sb-status-row">
                <span class="sb-status-dot sb-status-dot-{status}"></span>
                <span class="sb-status-label">{escape(label)}</span>
                <span class="sb-status-tag" style="background:{tag_bg};color:{tag_fg};">
                    {tag_txt}
                </span>
            </div>
            {desc_html}
            {meta_html}
            {atualizacao_html}
        </div>
    """)
    st.sidebar.markdown(html, unsafe_allow_html=True)


# ====================================================
# BRAND / LOGO SIDEBAR
# ====================================================
def render_sidebar_brand(
    titulo: str = "TOTALE",
    subtitulo: str = "Inteligência Corporativa",
    logo: str = "",
    tema: TipoTemaBrand = "gradiente",
    ambiente: TipoAmbiente | None = "produção",
    versao: str = "",
    badge_custom: str = "",
    link_url: str = "",
    mostrar_data: bool = False,
    divider: bool = True,
    compacto: bool = False,
) -> None:
    """Renderiza a marca/cabeçalho corporativo na sidebar com suporte a logos,

    badges e temas visuais.

    Parameters
    ----------
    titulo : str
        Nome principal da aplicação ou empresa (ex: ``"TOTALE"``, ``"TOTALE BI"``).
    subtitulo : str
        Slogan, departamento ou módulo (ex: ``"Mesa de Operações"``, ``"Portal Saúde"``).
    logo : str
        - URL web (``"https://..."``) ou caminho de imagem.
        - Nome de ícone Material Symbols (ex: ``"insights"``, ``"account_balance"``, ``"token"``).
        - Se vazio, renderiza um ícone corporativo padrão.
    tema : TipoTemaBrand
        - ``"gradiente"``: Fundo midnight navy corporativo com brilho de luz e alto contraste.
        - ``"clean"``: Card branco refinado com borda e sombra sutil.
        - ``"minimalista"``: Layout plano sem caixa de fundo, perfeito para sidebars enxutas.
    ambiente : TipoAmbiente | None
        Exibe badge de ambiente (``"produção"`` / ``"homologação"`` / ``"desenvolvimento"``).
        Se ``None``, não renderiza badge de ambiente.
    versao : str
        Tag de versão do sistema (ex: ``"v3.2.0"``).
    badge_custom : str
        Texto de um badge extra personalizado (ex: ``"BETA"``, ``"PREMIUM"``, ``"PME"``).
    link_url : str
        URL opcional para transformar a marca em um link clicável (ex: ``"/"`` ou portal corporativo).
    mostrar_data : bool
        Exibe timestamp no fuso de São Paulo.
    divider : bool
        Renderiza uma linha divisória elegante abaixo do bloco da marca.
    compacto : bool
        Reduz espaçamentos e fontes para otimizar espaço vertical na sidebar.

    Exemplo
    -------
    >>> render_sidebar_brand(
    ...     titulo="TOTALE SAÚDE",
    ...     subtitulo="Auditoria & Faturamento",
    ...     logo="medical_services",
    ...     ambiente="produção",
    ...     versao="v2.5.1",
    ... )
    """
    # ── 1. Mapeamento de Ambientes ───────────────────────────
    amb_map: Dict[str, Tuple[str, str, str]] = {
        "produção": ("#059669", "rgba(5,150,105,0.18)", "PROD"),
        "producao": ("#059669", "rgba(5,150,105,0.18)", "PROD"),
        "prod": ("#059669", "rgba(5,150,105,0.18)", "PROD"),
        "homologação": ("#D97706", "rgba(245,158,11,0.18)", "HOMO"),
        "homologacao": ("#D97706", "rgba(245,158,11,0.18)", "HOMO"),
        "homo": ("#D97706", "rgba(245,158,11,0.18)", "HOMO"),
        "desenvolvimento": ("#7C3AED", "rgba(139,92,246,0.18)", "DEV"),
        "dev": ("#7C3AED", "rgba(139,92,246,0.18)", "DEV"),
    }

    # ── 2. Renderização do Logo ──────────────────────────────
    logo_is_url = bool(
        re.match(r"^(https?://|data:image/|/|\./)", logo.strip().lower())
    )

    if logo and logo_is_url:
        logo_html = f'<img src="{escape(logo)}" class="sb-brand-logo-img" alt="logo" />'
    else:
        icone_nome = logo if logo else "token"
        logo_html = f"""
            <div class="sb-brand-logo-icon">
                <span class="material-symbols-rounded">{escape(icone_nome)}</span>
            </div>
        """

    # ── 3. Badges ────────────────────────────────────────────
    badges_parts: List[str] = []

    if ambiente:
        amb_key = str(ambiente).strip().lower()
        cor_txt, cor_bg, label_amb = amb_map.get(
            amb_key, ("#059669", "rgba(5,150,105,0.18)", "PROD")
        )
        badges_parts.append(
            f'<span class="sb-brand-badge" style="background:{cor_bg};color:{cor_txt};border-color:{cor_txt}40;">{label_amb}</span>'
        )

    if versao:
        badges_parts.append(
            f'<span class="sb-brand-badge sb-brand-badge-version">{escape(versao)}</span>'
        )

    if badge_custom:
        badges_parts.append(
            f'<span class="sb-brand-badge sb-brand-badge-custom">{escape(badge_custom)}</span>'
        )

    badges_html = (
        f'<div class="sb-brand-badges-row">{"".join(badges_parts)}</div>'
        if badges_parts
        else ""
    )

    # ── 4. Data / Horário ────────────────────────────────────
    data_html = ""
    if mostrar_data:
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        data_html = f"""
            <div class="sb-brand-date">
                <span class="material-symbols-rounded">schedule</span>
                {agora.strftime("%d/%m/%Y · %H:%M")}
            </div>
        """

    # ── 5. Divider ───────────────────────────────────────────
    divider_html = '<div class="sb-brand-divider"></div>' if divider else ""

    # ── 6. CSS Inline do Brand Component ─────────────────────
    css = textwrap.dedent(f"""
        <style>
        .sb-brand-wrapper {{
            margin: {("-4px -8px 8px -8px" if compacto else "0 0 12px 0")};
            font-family: {FONTE_TEXTO};
        }}
        .sb-brand-link {{
            text-decoration: none !important;
            color: inherit !important;
            display: block;
        }}
        
        /* TEMAS */
        .sb-brand-card-gradiente {{
            background: linear-gradient(145deg, {COR_PRIMARIA} 0%, #0A3A8A 65%, #0F52BA 100%);
            border-radius: {("10px" if compacto else "14px")};
            padding: {("12px 14px" if compacto else "16px 16px 14px")};
            color: #FFFFFF;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 14px rgba(1, 40, 105, 0.16);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .sb-brand-card-gradiente::before {{
            content: ''; position: absolute; top: -30px; right: -30px; width: 90px; height: 90px;
            background: radial-gradient(circle, rgba(243,124,4,0.3) 0%, transparent 70%); border-radius: 50%;
        }}
        
        .sb-brand-card-clean {{
            background: #FFFFFF;
            border-radius: {("10px" if compacto else "14px")};
            padding: {("12px 14px" if compacto else "14px 16px")};
            color: {COR_TEXTO};
            box-shadow: 0 2px 8px rgba(1, 40, 105, 0.05);
            border: 1px solid {SB_BORDA_SUTIL};
        }}

        .sb-brand-card-minimalista {{
            background: transparent;
            padding: {("4px 4px" if compacto else "8px 6px")};
            color: {COR_TEXTO};
        }}

        /* HEADER ROW */
        .sb-brand-header {{
            display: flex;
            align-items: center;
            gap: {("10px" if compacto else "12px")};
            position: relative;
            z-index: 1;
        }}

        /* LOGO */
        .sb-brand-logo-img {{
            width: {("32px" if compacto else "40px")};
            height: {("32px" if compacto else "40px")};
            object-fit: contain;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.12);
            padding: 2px;
            flex-shrink: 0;
        }}
        .sb-brand-logo-icon {{
            width: {("32px" if compacto else "40px")};
            height: {("32px" if compacto else "40px")};
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            background: rgba(243, 124, 4, 0.15);
            color: {COR_SECUNDARIA};
            border: 1px solid rgba(243, 124, 4, 0.3);
        }}
        .sb-brand-card-gradiente .sb-brand-logo-icon {{
            background: rgba(255, 255, 255, 0.14);
            color: #FFFFFF;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        .sb-brand-logo-icon span {{
            font-size: {("20px" if compacto else "24px")} !important;
        }}

        /* TEXTOS */
        .sb-brand-title {{
            font-family: {FONTE_TITULO} !important;
            font-size: {("15px" if compacto else "17px")};
            font-weight: 800;
            line-height: 1.15;
            letter-spacing: -0.3px;
        }}
        .sb-brand-card-gradiente .sb-brand-title {{ color: #FFFFFF; }}
        .sb-brand-card-clean .sb-brand-title,
        .sb-brand-card-minimalista .sb-brand-title {{ color: {COR_PRIMARIA}; }}

        .sb-brand-sub {{
            font-size: {("10.5px" if compacto else "11.5px")};
            font-weight: 500;
            margin-top: 2px;
            letter-spacing: 0.2px;
            opacity: 0.75;
        }}

        /* BADGES */
        .sb-brand-badges-row {{
            display: flex;
            align-items: center;
            gap: 5px;
            margin-top: {("8px" if compacto else "10px")};
            position: relative;
            z-index: 1;
            flex-wrap: wrap;
        }}
        .sb-brand-badge {{
            font-size: 9.5px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 6px;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            border: 1px solid transparent;
            line-height: 1.3;
        }}
        .sb-brand-badge-version {{
            background: rgba(100, 116, 139, 0.12);
            color: #64748B;
            border-color: rgba(100, 116, 139, 0.2);
        }}
        .sb-brand-card-gradiente .sb-brand-badge-version {{
            background: rgba(255, 255, 255, 0.15);
            color: rgba(255, 255, 255, 0.9);
            border-color: rgba(255, 255, 255, 0.2);
        }}
        .sb-brand-badge-custom {{
            background: rgba(243, 124, 4, 0.15);
            color: {COR_SECUNDARIA};
            border-color: rgba(243, 124, 4, 0.3);
        }}
        .sb-brand-card-gradiente .sb-brand-badge-custom {{
            background: {COR_SECUNDARIA};
            color: #FFFFFF;
            border-color: transparent;
        }}

        /* DATA */
        .sb-brand-date {{
            font-size: 9.5px;
            margin-top: 6px;
            display: flex;
            align-items: center;
            gap: 4px;
            opacity: 0.6;
            font-family: {FONTE_CODIGO};
        }}
        .sb-brand-date span {{ font-size: 11px !important; }}

        /* DIVIDER */
        .sb-brand-divider {{
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, {SB_BORDA_SUTIL} 30%, {SB_BORDA_SUTIL} 70%, transparent 100%);
            margin: {("10px 0 6px" if compacto else "14px 0 10px")};
        }}
        </style>
    """)

    card_class = f"sb-brand-card-{tema}"
    sub_html = (
        f'<div class="sb-brand-sub">{escape(subtitulo)}</div>' if subtitulo else ""
    )

    corpo_card = f"""
        <div class="sb-brand-header">
            {logo_html}
            <div>
                <div class="sb-brand-title">{escape(titulo)}</div>
                {sub_html}
            </div>
        </div>
        {badges_html}
        {data_html}
    """

    if link_url:
        corpo_card = (
            f'<a href="{escape(link_url)}" class="sb-brand-link">{corpo_card}</a>'
        )

    html = textwrap.dedent(f"""
        {css}
        <div class="sb-brand-wrapper">
            <div class="{card_class}">
                {corpo_card}
            </div>
            {divider_html}
        </div>
    """)
    st.sidebar.markdown(html, unsafe_allow_html=True)
