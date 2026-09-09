"""
Módulo central de estilos, fontes e componentes reutilizáveis
para todo o projeto Streamlit TOTALE.

Version: 4.1.2
Author: TOTALE Tecnologia
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, TypeAlias
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

# =============================================================================
# CONFIGURAÇÃO DE LOGGING
# =============================================================================
logger = logging.getLogger(__name__)


# =============================================================================
# TIPOS E ENUMERAÇÕES
# =============================================================================
class TemaKPI(str, Enum):
    AZUL = "azul"
    VERDE = "verde"
    VERMELHO = "vermelho"
    LARANJA = "laranja"
    CINZA = "cinza"
    ROXO = "roxo"


class TipoInsight(str, Enum):
    OK = "ok"
    INFO = "info"
    ALERTA = "alerta"
    CRITICO = "critico"
    ACAO = "acao"


class TipoStatus(str, Enum):
    OK = "ok"
    INFO = "info"
    ALERTA = "alerta"
    CRITICO = "critico"
    NEUTRO = "neutro"


class TipoEmptyState(str, Enum):
    DADOS = "dados"
    FILTRO = "filtro"
    ERRO = "erro"
    CARREGANDO = "carregando"
    PADRAO = "padrao"


class TipoBadge(str, Enum):
    DEFAULT = "default"
    SUCESSO = "sucesso"
    ALERTA = "alerta"
    ERRO = "erro"
    INFO = "info"
    ROXO = "roxo"


class TipoProgressBar(str, Enum):
    AZUL = "azul"
    LARANJA = "laranja"
    VERDE = "verde"
    VERMELHO = "vermelho"
    ROXO = "roxo"
    GRADIENTE = "gradiente"


class TipoTrend(str, Enum):
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"
    NONE = "none"


class TipoNotification(str, Enum):
    SUCESSO = "sucesso"
    INFO = "info"
    ALERTA = "alerta"
    ERRO = "erro"


class TipoTimelineItem(str, Enum):
    CONCLUIDO = "concluido"
    EM_ANDAMENTO = "em_andamento"
    PENDENTE = "pendente"
    CANCELADO = "cancelado"


class TipoHero(str, Enum):
    PADRAO = "padrao"
    MIGRACAO = "migracao"
    PME = "pme"
    TOTALE_1 = "totale_1"
    TOTALE_2 = "totale_2"


# Type aliases
TemaKPIType: TypeAlias = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo"
]
TipoInsightType: TypeAlias = Literal["ok", "info", "alerta", "critico", "acao"]
TipoStatusType: TypeAlias = Literal["ok", "info", "alerta", "critico", "neutro"]
TipoEmptyStateType: TypeAlias = Literal[
    "dados", "filtro", "erro", "carregando", "padrao"
]
TipoBadgeType: TypeAlias = Literal[
    "default", "sucesso", "alerta", "erro", "info", "roxo"
]
TipoProgressBarType: TypeAlias = Literal[
    "azul", "laranja", "verde", "vermelho", "roxo", "gradiente"
]
TipoTrendType: TypeAlias = Literal["up", "down", "neutral", "none"]
TipoNotificationType: TypeAlias = Literal["sucesso", "info", "alerta", "erro"]
TipoTimelineItemType: TypeAlias = Literal[
    "concluido", "em_andamento", "pendente", "cancelado"
]
TipoHeroType: TypeAlias = Literal["padrao", "migracao", "pme", "totale_1", "totale_2"]

BaseFormatter: TypeAlias = str | Callable[[object], str]
FmtDict: TypeAlias = dict[str, BaseFormatter | None]
ColorMapDict: TypeAlias = dict[str, str]


# =============================================================================
# CONFIGURAÇÕES DE TIPOGRAFIA E CORES
# =============================================================================
class Fontes:
    TITULO = "'Manrope', 'Segoe UI', Arial, sans-serif"
    TEXTO = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    CODIGO = "'JetBrains Mono', Consolas, 'Courier New', monospace"


class GoogleFonts:
    URLS: tuple[str, ...] = (
        "https://fonts.googleapis.com/icon?family=Material+Icons",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded"
        ":opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined"
        ":opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
        "&family=Manrope:wght@400;500;600;700;800;900"
        "&family=JetBrains+Mono:wght@400;500&display=swap",
    )


class Cores:
    PRIMARIA = "#012869"
    PRIMARIA_LIGHT = "#0A48AA"
    SECUNDARIA = "#F37C04"
    SECUNDARIA_DARK = "#D96500"

    SUCESSO = "#059669"
    ALERTA = "#DC2626"
    ATENCAO = "#F59E0B"
    NEUTRO = "#64748B"

    TEXTO = "#1F2937"
    TEXTO_2 = "#374151"
    TEXTO_3 = "#6B7280"

    BORDA = "#E2E8F0"
    FUNDO = "#F8FAFC"
    LARANJA_SUAVE = "#FDE68A"
    AZUL_SUAVE = "#DBEAFE"
    ROXO = "#7C3AED"
    ROXO_CLARO = "#A78BFA"
    VERDE_PME = "#10B981"
    AZUL_PME = "#3B82F6"


class ConfigCores:
    TEMA: dict[str, str] = {
        "azul": Cores.PRIMARIA,
        "verde": Cores.SUCESSO,
        "vermelho": Cores.ALERTA,
        "laranja": Cores.SECUNDARIA,
        "cinza": Cores.NEUTRO,
        "roxo": Cores.ROXO,
    }

    BADGE: dict[str, tuple[str, str, str]] = {
        "default": ("#F3F4F6", "#374151", "#D1D5DB"),
        "sucesso": ("#D1FAE5", "#065F46", "#059669"),
        "alerta": ("#FEF3C7", "#92400E", "#F59E0B"),
        "erro": ("#FEE2E2", "#991B1B", "#DC2626"),
        "info": ("#DBEAFE", "#1E40AF", "#3B82F6"),
        "roxo": ("#EDE9FE", "#5B21B6", "#8B5CF6"),
    }

    PROGRESS_BAR: dict[str, str] = {
        "azul": Cores.PRIMARIA,
        "laranja": Cores.SECUNDARIA,
        "verde": Cores.SUCESSO,
        "vermelho": Cores.ALERTA,
        "roxo": Cores.ROXO,
        "gradiente": f"linear-gradient(90deg, {Cores.PRIMARIA}, {Cores.SECUNDARIA})",
    }

    TREND: dict[str, str] = {
        "up": Cores.SUCESSO,
        "down": Cores.ALERTA,
        "neutral": Cores.NEUTRO,
        "none": Cores.NEUTRO,
    }

    TREND_ICONS: dict[str, str] = {
        "up": "↑",
        "down": "↓",
        "neutral": "→",
        "none": "",
    }

    NOTIFICATION: dict[str, tuple[str, str, str, str]] = {
        "sucesso": ("#D1FAE5", "#065F46", "#059669", "✅"),
        "info": ("#DBEAFE", "#1E40AF", "#3B82F6", "ℹ️"),
        "alerta": ("#FEF3C7", "#92400E", "#F59E0B", "⚠️"),
        "erro": ("#FEE2E2", "#991B1B", "#DC2626", "❌"),
    }

    TIMELINE: dict[str, tuple[str, str, str]] = {
        "concluido": (Cores.SUCESSO, "#D1FAE5", "✓"),
        "em_andamento": (Cores.SECUNDARIA, "#FEF3C7", "⏳"),
        "pendente": (Cores.NEUTRO, "#F3F4F6", "○"),
        "cancelado": (Cores.ALERTA, "#FEE2E2", "✕"),
    }

    INSIGHT: dict[str, tuple[str, str, str, str]] = {
        "ok": ("#D1FAE5", "#065F46", "#059669", "✅"),
        "info": ("#DBEAFE", "#1E40AF", "#3B82F6", "ℹ️"),
        "alerta": ("#FEF3C7", "#92400E", "#F59E0B", "⚠️"),
        "critico": ("#FEE2E2", "#991B1B", "#DC2626", "🚨"),
        "acao": ("#EDE9FE", "#5B21B6", "#8B5CF6", "💡"),
    }

    EMPTY_STATE: dict[str, tuple[str, str, str, str]] = {
        "dados": ("#F8FAFC", "#64748B", "📊", "Nenhum dado disponível"),
        "filtro": ("#F0F9FF", "#0369A1", "🔍", "Nenhum resultado encontrado"),
        "erro": ("#FEF2F2", "#DC2626", "⚠️", "Ocorreu um erro"),
        "carregando": ("#F5F3FF", "#7C3AED", "⏳", "Carregando dados..."),
        "padrao": ("#F8FAFC", "#64748B", "📭", "Conteúdo não disponível"),
    }

    PLOTLY_COLORWAY: list[str] = [
        Cores.PRIMARIA,
        Cores.SECUNDARIA,
        Cores.SUCESSO,
        Cores.ALERTA,
        "#8B5CF6",
        "#EC4899",
        "#14B8A6",
        "#F59E0B",
        "#6366F1",
        Cores.NEUTRO,
    ]


# ====================================================
# HELPERS
# ====================================================
def _resolver_cor_tema(tema: str) -> str:
    cor = ConfigCores.TEMA.get(tema)
    if cor is None:
        logger.warning("Tema desconhecido: '%s'. Usando 'azul'.", tema)
        return Cores.PRIMARIA
    return cor


def _markdown_inline_para_html(texto: str) -> str:
    """Converte marcadores markdown inline básicos para HTML."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    return texto


# =============================================================================
# UTILITÁRIOS E FORMATAÇÃO
# =============================================================================
class Validadores:
    @staticmethod
    def url(url: str | None) -> bool:
        if not url:
            return False
        try:
            result = urlparse(url)
            return bool(result.scheme and result.netloc)
        except Exception:
            return False

    @staticmethod
    def html_escape(texto: Any) -> str:
        if texto is None:
            return ""
        return html_lib.escape(str(texto))

    @staticmethod
    def resolver_cor_tema(tema: str) -> str:
        cor = ConfigCores.TEMA.get(tema)
        if cor is None:
            return Cores.PRIMARIA
        return cor


class Formatadores:
    @staticmethod
    def markdown_para_html(texto: str) -> str:
        if not texto:
            return texto
        texto = html_lib.escape(texto)
        texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
        texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", texto)
        texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
        return texto


# =============================================================================
# RENDER HTML À PROVA DE MARKDOWN DO STREAMLIT
# =============================================================================
def _safe_render_html(html_str: str, container: Any = st) -> None:
    """Renderiza HTML no Streamlit sem ser corrompido pelo parser Markdown."""
    if not html_str:
        return
    clean = html_str.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    clean = re.sub(r">\s+<", "><", clean)
    clean = re.sub(r" {2,}", " ", clean)
    clean = clean.strip()
    container.markdown(clean, unsafe_allow_html=True)


# =============================================================================
# CONFIGURAÇÃO GLOBAL DO PLOTLY E CSS
# =============================================================================
class PlotlyConfig:
    @staticmethod
    def configurar() -> None:
        template = go.layout.Template(
            layout=go.Layout(
                font={"family": Fontes.TEXTO, "size": 13, "color": Cores.TEXTO},
                title={
                    "font": {"family": Fontes.TITULO, "size": 20, "color": Cores.TEXTO},
                    "x": 0.02,
                    "xanchor": "left",
                },
                legend={
                    "font": {"family": Fontes.TEXTO, "size": 12, "color": Cores.TEXTO_2}
                },
                xaxis={"gridcolor": "#F1F5F9", "zerolinecolor": "#CBD5E1"},
                yaxis={"gridcolor": "#F1F5F9", "zerolinecolor": "#CBD5E1"},
                paper_bgcolor="white",
                plot_bgcolor="white",
                colorway=ConfigCores.PLOTLY_COLORWAY,
            )
        )
        pio.templates["corporativo"] = template
        pio.templates.default = "plotly_white+corporativo"


class FontInjector:
    @staticmethod
    def _build_links_html() -> str:
        tags = "\n".join(
            f'<link rel="stylesheet" href="{url}">' for url in GoogleFonts.URLS
        )
        return (
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            + tags
        )

    @staticmethod
    def injetar_no_head_pai() -> None:
        urls_js = ", ".join(f'"{u}"' for u in GoogleFonts.URLS)
        components.html(
            f"""
            <script>
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
                const existentes = Array.from(head.querySelectorAll('link[rel="stylesheet"]')).map(function (l) {{ return l.href; }});
                urls.forEach(function (href) {{
                    if (existentes.includes(href)) return;
                    const link = parentDoc.createElement('link');
                    link.rel = 'stylesheet'; link.href = href;
                    head.appendChild(link);
                }});
            }})();
            </script>
            """,
            height=0,
        )


class CSSInjector:
    @staticmethod
    def _build_css_2() -> str:
        return f"""
        <style>
        :root {{
            --totale-font-title: {Fontes.TITULO};
            --totale-font-text: {Fontes.TEXTO};
            --totale-font-code: {Fontes.CODIGO};

            --totale-primary: {Cores.PRIMARIA};
            --totale-primary-light: {Cores.PRIMARIA_LIGHT};
            --totale-secondary: {Cores.SECUNDARIA};

            --totale-text: {Cores.TEXTO};
            --totale-text-2: {Cores.TEXTO_2};
            --totale-text-3: {Cores.TEXTO_3};

            --totale-border: {Cores.BORDA};
            --totale-background: {Cores.FUNDO};

            --totale-radius-sm: 6px;
            --totale-radius-md: 10px;
            --totale-radius-lg: 14px;

            --totale-shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06);
            --totale-shadow-md: 0 8px 20px rgba(15, 23, 42, 0.08);
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #FFFFFF 0%, #FBFCFE 55%, #F8FAFC 100%);
            border-right: 1px solid var(--totale-border);
        }}

        [data-testid="stSidebar"] > div:first-child {{
            background: transparent;
        }}

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
            padding-top: 0.5rem;
        }}

        [data-testid="stSidebar"] *,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] button,
        [data-testid="stSidebar"] input {{
            font-family: var(--totale-font-text) !important;
        }}

        [data-testid="stSidebar"] .stSelectbox label,
        [data-testid="stSidebar"] .stMultiSelect label,
        [data-testid="stSidebar"] .stDateInput label,
        [data-testid="stSidebar"] .stTextInput label,
        [data-testid="stSidebar"] .stNumberInput label,
        [data-testid="stSidebar"] .stSlider label,
        [data-testid="stSidebar"] .stCheckbox label {{
            color: var(--totale-text-2) !important;
            font-size: 11px !important;
            font-weight: 700 !important;
            letter-spacing: 0.25px;
        }}

        [data-testid="stSidebar"] div[data-baseweb="select"] > div {{
            background: #FFFFFF !important;
            border-color: var(--totale-border) !important;
            border-radius: 9px !important;
            min-height: 40px;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }}

        [data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within {{
            border-color: var(--totale-primary-light) !important;
            box-shadow: 0 0 0 3px rgba(10, 72, 170, 0.10) !important;
        }}

        [data-testid="stSidebar"] div[data-baseweb="input"] {{
            background: #FFFFFF !important;
            border-color: var(--totale-border) !important;
            border-radius: 9px !important;
        }}

        [data-testid="stSidebar"] .stButton > button {{
            width: 100%;
            min-height: 40px;
            border-radius: 9px;
            border: 1px solid var(--totale-border);
            background: #FFFFFF;
            color: var(--totale-text-2);
            font-size: 12px;
            font-weight: 700;
            transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
        }}

        [data-testid="stSidebar"] .stButton > button:hover {{
            color: var(--totale-primary);
            border-color: #BFDBFE;
            box-shadow: var(--totale-shadow-sm);
            transform: translateY(-1px);
        }}

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
            color: #FFFFFF;
            background: linear-gradient(135deg, var(--totale-primary), var(--totale-primary-light));
            border-color: var(--totale-primary);
        }}

        [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
            border-color: var(--totale-border) !important;
            border-radius: 12px !important;
            background: linear-gradient(160deg, #FFFFFF 0%, #F8FAFC 100%);
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.035);
        }}

        [data-testid="stSidebar"] .totale-sidebar-menu-marker + div div[role="radiogroup"] {{
            gap: 5px;
        }}

        [data-testid="stSidebar"] .totale-sidebar-menu-marker + div div[role="radiogroup"] > label {{
            width: 100%;
            min-height: 42px;
            display: flex;
            align-items: center;
            padding: 8px 11px;
            margin: 0;
            border: 1px solid transparent;
            border-radius: 9px;
            color: var(--totale-text-2);
            background: transparent;
            transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
        }}

        [data-testid="stSidebar"] .totale-sidebar-menu-marker + div div[role="radiogroup"] > label:hover {{
            color: var(--totale-primary);
            background: #F1F5F9;
            border-color: #E2E8F0;
            transform: translateX(2px);
        }}

        [data-testid="stSidebar"] .totale-sidebar-menu-marker + div div[role="radiogroup"] > label:has(input:checked) {{
            color: var(--totale-primary);
            background: linear-gradient(90deg, #EFF6FF 0%, #F8FAFC 100%);
            border-color: #BFDBFE;
            box-shadow: inset 3px 0 0 var(--totale-primary);
            font-weight: 700 !important;
        }}

        [data-testid="stSidebar"] .totale-sidebar-menu-marker + div div[role="radiogroup"] > label > div:first-child {{
            display: none;
        }}

        [data-testid="stSidebar"] .totale-sidebar-menu-marker + div div[role="radiogroup"] > label p {{
            font-size: 12.5px !important;
            line-height: 1.25;
        }}

        [data-testid="stSidebar"] details[data-testid="stExpander"] {{
            border: 1px solid var(--totale-border);
            border-radius: 10px;
            background: #FFFFFF;
        }}

        [data-testid="stSidebar"] details[data-testid="stExpander"] summary {{
            color: var(--totale-text-2);
            font-size: 11px;
            font-weight: 700;
        }}

        [data-testid="stSidebar"] ::-webkit-scrollbar {{ width: 7px; }}
        [data-testid="stSidebar"] ::-webkit-scrollbar-track {{ background: transparent; }}
        [data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 999px; }}
        [data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}

        @media (max-width: 768px) {{
            [data-testid="stSidebar"] {{ box-shadow: 8px 0 30px rgba(15, 23, 42, 0.16); }}
        }}
        </style>
        """

    @staticmethod
    def _build_css() -> str:
        return f"""{FontInjector._build_links_html()}
        <style>
        @font-face {{ font-family: 'Material Icons'; font-style: normal; font-weight: 400; src: url(https://fonts.gstatic.com/s/materialicons/v143/flUhRq6tzZclQEJ-Vdg-IuiaDsNc.woff2) format('woff2'); }}
        @font-face {{ font-family: 'Material Symbols Rounded'; font-style: normal; font-weight: 400; src: url(https://fonts.gstatic.com/s/materialsymbolsrounded/v206/syl0-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190Fjzag.woff2) format('woff2'); }}
        
        :root {{
            --font-titulo: {Fontes.TITULO}; --font-texto: {Fontes.TEXTO}; --font-codigo: {Fontes.CODIGO};
            --cor-primaria: {Cores.PRIMARIA}; --cor-secundaria: {Cores.SECUNDARIA};
            --cor-sucesso: {Cores.SUCESSO}; --cor-alerta: {Cores.ALERTA}; --cor-neutro: {Cores.NEUTRO};
            --cor-texto: {Cores.TEXTO}; --cor-texto-2: {Cores.TEXTO_2}; --cor-texto-3: {Cores.TEXTO_3};
            --cor-borda: {Cores.BORDA}; --cor-fundo: {Cores.FUNDO};
            --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.06); --shadow-md: 0 4px 12px rgba(0,0,0,0.08); --shadow-lg: 0 10px 28px rgba(0,0,0,0.12);
        }}

        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stSidebar"], p, label, div, li, a, button, input, select, textarea {{ font-family: var(--font-texto) !important; }}
        h1, h2, h3, h4, h5, h6, .hero-title, .section-title, .kpi-value, .metric-value, [data-testid="stMetricValue"] {{ font-family: var(--font-titulo) !important; font-weight: 700; letter-spacing: -0.3px; }}
        h1, .hero-title {{ font-weight: 800; letter-spacing: -0.6px; }}
        
        .main .block-container {{ padding-top: 1rem; max-width: 1400px; }}
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }} ::-webkit-scrollbar-track {{ background: #F1F5F9; }} ::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 4px; }}
        
        .hero-corp {{ background: linear-gradient(120deg, #012869 0%, #023A9E 35%, #1E5FCC 55%, #E85D04 82%, #F37C04 100%); padding: 34px 44px; border-radius: var(--radius-lg); color: #FFFFFF; box-shadow: 0 10px 40px rgba(1, 40, 105, 0.30); margin-bottom: 24px; position: relative; overflow: hidden; }}
        .totale-hero-1 {{ background: linear-gradient(135deg, #011E52 0%, #012869 45%, #0A48AA 80%, #F37C04 130%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(243, 124, 4, 0.25); box-shadow: 0 12px 32px rgba(1, 40, 105, 0.28); margin-bottom: 24px; position: relative; overflow: hidden; }}
        .totale-hero-2 {{ background: linear-gradient(120deg, #012869 0%, #033486 50%, #0747B3 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border-left: 6px solid #F37C04; box-shadow: 0 10px 28px rgba(1, 40, 105, 0.22); margin-bottom: 24px; display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: center; }}
        @media (max-width: 768px) {{ .totale-hero-2 {{ grid-template-columns: 1fr; }} }}
        .totale-hero-2-card {{ background: rgba(255, 255, 255, 0.08); -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 12px; padding: 16px 24px; min-width: 180px; text-align: center; }}
        
        .hero-migracao {{ background: linear-gradient(135deg, #4C1D95 0%, #6D28D9 35%, #7C3AED 60%, #A78BFA 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(167, 139, 250, 0.30); box-shadow: 0 12px 32px rgba(124, 58, 237, 0.35); margin-bottom: 24px; position: relative; overflow: hidden; }}
        .hero-pme {{ background: linear-gradient(135deg, #059669 0%, #10B981 35%, #3B82F6 70%, #60A5FA 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(255, 255, 255, 0.25); box-shadow: 0 12px 32px rgba(16, 185, 129, 0.30); margin-bottom: 24px; position: relative; overflow: hidden; }}
        
        .card-premium {{
            background: #FFFFFF;
            border-radius: 12px;
            padding: 20px 24px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            margin-bottom: 12px;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .card-premium:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 20px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -5px rgba(0, 0, 0, 0.04);
            border-color: #CBD5E1;
        }}
        .card-accent-top {{
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
        }}
        .card-header-flex {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }}
        .kpi-label-premium {{
            font-size: 12px;
            font-weight: 600;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            line-height: 1.4;
        }}
        .kpi-icon-wrapper {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 36px;
            height: 36px;
            border-radius: 10px;
            flex-shrink: 0;
        }}
        .kpi-value-premium {{
            font-size: 32px;
            font-weight: 800;
            color: #0F172A;
            line-height: 1;
            font-variant-numeric: tabular-nums;
            font-family: var(--font-titulo) !important;
            letter-spacing: -0.5px;
        }}
        .kpi-sub-premium {{
            font-size: 13px;
            color: #64748B;
            margin-top: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .trend-pill {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            line-height: 1;
        }}
        .trend-up {{ background: #ECFDF5; color: #059669; }}
        .trend-down {{ background: #FEF2F2; color: #DC2626; }}
        .trend-neutral {{ background: #F8FAFC; color: #64748B; }}
        
        .table-premium-wrapper {{
            background: #FFFFFF;
            border-radius: 12px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
            overflow: hidden;
            margin: 16px 0;
            position: relative;
        }}
        .table-premium-scroll {{
            width: 100%;
            overflow-x: auto;
            scrollbar-width: thin;
            scrollbar-color: #CBD5E1 transparent;
        }}
        .table-premium-scroll::-webkit-scrollbar {{ height: 6px; width: 6px; }}
        .table-premium-scroll::-webkit-scrollbar-thumb {{ background-color: #CBD5E1; border-radius: 3px; }}
        
        .totale-table-pro {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            text-align: left;
        }}
        .totale-table-pro th {{
            background: #F8FAFC;
            color: #475569;
            font-family: var(--font-texto) !important;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 14px 16px;
            position: sticky;
            top: 0;
            z-index: 10;
            border-bottom: 1px solid #E2E8F0;
            white-space: nowrap;
        }}
        .totale-table-pro th::after {{
            content: ''; position: absolute; left: 0; right: 0; bottom: -5px; height: 5px;
            background: linear-gradient(to bottom, rgba(0,0,0,0.02) 0%, rgba(0,0,0,0) 100%);
            pointer-events: none;
        }}
        .totale-table-pro td {{
            padding: 14px 16px;
            border-bottom: 1px solid #F1F5F9;
            color: #334155;
            font-size: 13px;
            font-family: var(--font-texto) !important;
            vertical-align: middle;
            transition: background 0.2s ease;
        }}
        .totale-table-pro tbody tr:last-child td {{ border-bottom: none; }}
        .totale-table-pro tbody tr:hover td {{ background-color: #F8FAFC; color: #0F172A; }}
        .totale-table-pro tbody tr.striped td {{ background-color: #FAFCFE; }}
        .totale-table-pro tbody tr.striped:hover td {{ background-color: #F8FAFC; }}
        
        .td-badge {{
            display: inline-block; padding: 4px 10px; border-radius: 12px;
            font-size: 11px; font-weight: 600; text-transform: uppercase;
        }}
        
        .section-header {{ display: flex; align-items: center; gap: 12px; margin: 32px 0 16px 0; padding-bottom: 12px; border-bottom: 2px solid var(--cor-borda); }}
        .user-info-card {{ background: linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%); border: 1px solid var(--cor-borda); border-radius: 12px; padding: 16px; margin: 12px 0; }}
        .user-avatar {{ width: 42px; height: 42px; border-radius: 50%; background: linear-gradient(135deg, {Cores.PRIMARIA}, {Cores.SECUNDARIA}); display: flex; align-items: center; justify-content: center; font-size: 18px; color: #FFFFFF; font-weight: 700; flex-shrink: 0; object-fit: cover; }}
        .filter-group {{ background: #FFFFFF; border: 1px solid var(--cor-borda); border-radius: 8px; margin: 8px 0; overflow: hidden; }}
        
        .totale-table-container {{ width: 100%; overflow-x: auto; border-radius: 8px; border: 1px solid var(--cor-borda); margin: 16px 0; background: #FFFFFF; box-shadow: var(--shadow-sm); }}
        .totale-table {{ width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }}
        .totale-table th {{ background-color: #F8FAFC; color: var(--cor-primaria); font-weight: 700; padding: 12px 16px; border-bottom: 2px solid var(--cor-borda); text-transform: uppercase; font-size: 11px; white-space: nowrap; }}
        .totale-table td {{ padding: 10px 16px; border-bottom: 1px solid var(--cor-borda); color: var(--cor-texto-2); }}
        .totale-table tbody tr.striped {{ background-color: #FAFCFE; }}
        .totale-table tbody tr:hover {{ background-color: #F1F5F9; }}
        
        .th-title {{
            margin: 0;
            font-size: 30px;
            font-weight: 800;
            color: #FFFFFF;
            font-family: var(--font-titulo) !important;
            line-height: 1.2;
            letter-spacing: -0.5px;
        }}
        .th-title-lg {{
            margin: 0;
            font-size: 32px;
            font-weight: 800;
            color: #FFFFFF;
            font-family: var(--font-titulo) !important;
            line-height: 1.2;
            letter-spacing: -0.6px;
        }}
        .th-sub {{
            margin: 6px 0 0 0;
            font-size: 13px;
            color: #E0E7FF;
            font-family: var(--font-texto) !important;
            line-height: 1.5;
        }}
        .th-sub-muted {{
            margin: 8px 0 0 0;
            font-size: 14px;
            color: #E2E8F0;
            font-family: var(--font-texto) !important;
        }}
        .th-badge {{
            background: rgba(255,255,255,0.15);
            border: 1px solid rgba(255,255,255,0.25);
            color: #FFFFFF;
            padding: 3px 10px;
            border-radius: 14px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            display: inline-block;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }}
        .th-tag {{
            font-size: 11px;
            color: #CBD5E1;
            margin-left: 8px;
        }}
        .th-card-label {{
            font-size: 10px;
            font-weight: 700;
            color: #CBD5E1;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .th-card-value {{
            font-size: 26px;
            font-weight: 800;
            color: #F37C04;
            font-family: var(--font-titulo) !important;
            margin-top: 4px;
            line-height: 1;
        }}
        .th-meta {{
            margin-top: 14px;
            font-size: 11px;
            color: #94A3B8;
            display: inline-block;
            background: rgba(0,0,0,0.25);
            padding: 4px 10px;
            border-radius: 6px;
        }}
        
        .material-icons, .material-symbols-outlined, .material-symbols-rounded {{ font-family: "Material Symbols Rounded", "Material Icons" !important; font-weight: normal !important; -webkit-font-smoothing: antialiased !important; }}
        </style>
        """

    @staticmethod
    def injetar() -> None:
        _safe_render_html(CSSInjector._build_css())


# =============================================================================
# API PÚBLICA PRINCIPAL
# =============================================================================
def aplicar_estilo() -> None:
    PlotlyConfig.configurar()
    FontInjector.injetar_no_head_pai()
    CSSInjector.injetar()


def aplicar_estilo_corp() -> None:
    aplicar_estilo()


def aplicar_sidebar_corp() -> None:
    aplicar_estilo()


# =============================================================================
# COMPONENTES DE SIDEBAR
# =============================================================================
def render_sidebar_brand(
    nome: str = "TOTALE",
    subtitulo: str = "Analytics & Intelligence",
    versao: str = "",
    logo_url: str | None = None,
    icone: str = "⚡",
    titulo: str = "",
    logo: str | None = None,
    **kwargs: Any,
) -> None:
    nome_final = titulo or nome
    subtitulo_final = kwargs.get("segmento", subtitulo)
    logo_final = logo or logo_url

    with st.sidebar:
        if logo_final and Validadores.url(logo_final):
            st.image(logo_final, use_container_width=True)

        badge_html = (
            f'<span style="display:inline-block;background-color:{Cores.AZUL_SUAVE};color:{Cores.PRIMARIA};font-weight:700;font-size:10px;padding:2px 8px;border-radius:12px;border:1px solid #BFDBFE;margin-top:6px;text-transform:uppercase;">{Validadores.html_escape(versao)}</span>'
            if versao
            else ""
        )
        icone_html = (
            f'<span style="font-size:22px;color:{Cores.SECUNDARIA};line-height:1;">{Validadores.html_escape(icone)}</span>'
            if not logo_final
            else ""
        )

        markup = f"""
        <div style="padding:10px 0 16px 0;border-bottom:1px solid {Cores.BORDA};margin-bottom:16px;">
            <div style="display:flex;align-items:center;gap:10px;">
                {icone_html}
                <div>
                    <h2 style="font-family:{Fontes.TITULO};font-size:18px;font-weight:800;color:{Cores.PRIMARIA};margin:0;line-height:1.2;">{Validadores.html_escape(nome_final)}</h2>
                    <div style="font-family:{Fontes.TEXTO};font-size:11px;color:{Cores.TEXTO_3};margin-top:2px;">{Validadores.html_escape(subtitulo_final)}</div>
                </div>
            </div>
            {badge_html}
        </div>
        """
        _safe_render_html(markup)


def render_sidebar_section(
    titulo: str, icone: str = "", collapsible: bool = False
) -> None:
    if collapsible:
        with st.sidebar.expander(f"{icone} {titulo}".strip(), expanded=True):
            pass
    else:
        icone_html = (
            f'<span style="font-size:14px;line-height:1;">{Validadores.html_escape(icone)}</span>'
            if icone
            else ""
        )
        markup = f'<div style="margin:16px 0;padding:12px 0;border-top:1px solid {Cores.BORDA};"><div style="font-size:11px;font-weight:700;color:{Cores.TEXTO_3};text-transform:uppercase;display:flex;align-items:center;gap:6px;">{icone_html}<span>{Validadores.html_escape(titulo)}</span></div></div>'
        with st.sidebar:
            _safe_render_html(markup)


def render_sidebar_divider(
    estilo: Literal["linha", "gradiente", "pontilhado", "espaco"] = "gradiente",
    espacamento: Literal["pequeno", "medio", "grande"] = "medio",
    cor: str = "",
    label: str = "",
) -> None:
    margens = {
        "pequeno": "6px 0",
        "medio": "14px 0",
        "grande": "24px 0",
    }
    margem = margens.get(espacamento, margens["medio"])
    cor_final = cor or Cores.BORDA

    if estilo == "espaco":
        alturas = {"pequeno": "8px", "medio": "16px", "grande": "28px"}
        markup = f'<div style="height:{alturas.get(espacamento, "16px")};"></div>'
        with st.sidebar:
            _safe_render_html(markup)
        return

    if label:
        label_esc = Validadores.html_escape(label)
        if estilo == "pontilhado":
            line_style = f"border:none;border-top:1.5px dashed {cor_final};"
        elif estilo == "gradiente":
            line_style = (
                f"border:none;height:1px;"
                f"background:linear-gradient(90deg,transparent 0%,{cor_final} 40%,{cor_final} 60%,transparent 100%);"
            )
        else:
            line_style = f"border:none;border-top:1px solid {cor_final};"

        markup = (
            f'<div style="display:flex;align-items:center;gap:10px;margin:{margem};">'
            f'<div style="flex:1;{line_style}"></div>'
            f'<span style="font-size:9px;font-weight:700;color:{Cores.TEXTO_3};'
            f'text-transform:uppercase;letter-spacing:1.2px;white-space:nowrap;">'
            f"{label_esc}</span>"
            f'<div style="flex:1;{line_style}"></div>'
            f"</div>"
        )
        with st.sidebar:
            _safe_render_html(markup)
        return

    if estilo == "pontilhado":
        markup = f'<div style="margin:{margem};border:none;border-top:1.5px dashed {cor_final};"></div>'
    elif estilo == "gradiente":
        markup = (
            f'<div style="margin:{margem};height:1px;border:none;'
            f'background:linear-gradient(90deg,transparent 0%,{cor_final} 50%,transparent 100%);"></div>'
        )
    else:
        markup = f'<div style="margin:{margem};border:none;border-top:1px solid {cor_final};"></div>'

    with st.sidebar:
        _safe_render_html(markup)


def render_sidebar_footer_info(
    itens: dict[str, Any] | list[tuple[str, Any]] | None = None,
    copyright: str = "",
    empresa: str = "TOTALE",
    ano: int | None = None,
    versao: str = "",
    ambiente: str = "",
    unidade: str = "",
    mostrar_relógio: bool = False,
    **kwargs: Any,
) -> None:
    mostrar_rel = mostrar_relógio or kwargs.get("mostrar_relogio", False)

    itens_dict: dict[str, Any] = {}
    if isinstance(itens, list):
        itens_dict = dict(itens)
    elif isinstance(itens, dict):
        itens_dict = itens

    if ano is None:
        ano = datetime.now(timezone.utc).year

    _AMB_CFG: dict[str, tuple[str, str, str]] = {
        "produção": ("#D1FAE5", "#065F46", "#059669"),
        "producao": ("#D1FAE5", "#065F46", "#059669"),
        "prod": ("#D1FAE5", "#065F46", "#059669"),
        "homologação": ("#FEF3C7", "#92400E", "#D97706"),
        "homologacao": ("#FEF3C7", "#92400E", "#D97706"),
        "hml": ("#FEF3C7", "#92400E", "#D97706"),
        "desenvolvimento": ("#DBEAFE", "#1E40AF", "#3B82F6"),
        "dev": ("#DBEAFE", "#1E40AF", "#3B82F6"),
        "local": ("#F3F4F6", "#374151", "#9CA3AF"),
    }

    versao_html = ""
    if versao:
        v_txt = versao if str(versao).startswith("v") else f"v{versao}"
        versao_html = (
            f'<span style="display:inline-block;background:#F0F4FF;'
            f"color:{Cores.PRIMARIA};font-size:9px;font-weight:700;"
            f"padding:2px 8px;border-radius:10px;border:1px solid #C7D2FE;"
            f'letter-spacing:0.4px;text-transform:uppercase;">'
            f"{Validadores.html_escape(v_txt)}</span>"
        )

    amb_html = ""
    if ambiente:
        bg_a, fg_a, dot_a = _AMB_CFG.get(
            ambiente.lower().strip(),
            ("#F3F4F6", "#374151", "#9CA3AF"),
        )
        amb_html = (
            f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f"background:{bg_a};color:{fg_a};font-size:9px;font-weight:700;"
            f"padding:2px 8px;border-radius:10px;letter-spacing:0.4px;"
            f'text-transform:uppercase;">'
            f'<span style="width:6px;height:6px;border-radius:50%;'
            f'background:{dot_a};display:inline-block;flex-shrink:0;"></span>'
            f"{Validadores.html_escape(ambiente)}</span>"
        )

    badges_row = ""
    if versao_html or amb_html:
        badges_row = (
            f'<div style="display:flex;align-items:center;gap:6px;'
            f'flex-wrap:wrap;margin-bottom:10px;">'
            f"{versao_html}{amb_html}</div>"
        )

    unidade_html = ""
    if unidade:
        unidade_html = (
            f'<div style="font-size:10px;font-weight:600;color:{Cores.TEXTO_2};'
            f'margin-bottom:8px;letter-spacing:0.2px;">'
            f"{Validadores.html_escape(unidade)}</div>"
        )

    itens_html = ""
    if itens_dict:
        rows = "".join(
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;padding:3px 0;gap:8px;">'
            f'<span style="font-size:10px;color:{Cores.TEXTO_3};'
            f'font-weight:500;">{Validadores.html_escape(k)}</span>'
            f'<span style="font-size:10px;color:{Cores.TEXTO_2};'
            f"font-weight:700;font-variant-numeric:tabular-nums;"
            f'text-align:right;">{Validadores.html_escape(v)}</span>'
            f"</div>"
            for k, v in itens_dict.items()
        )
        itens_html = (
            f'<div style="border-top:1px solid {Cores.BORDA};'
            f'padding-top:8px;margin-top:4px;">{rows}</div>'
        )

    relogio_html = ""
    if mostrar_rel:
        agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        relogio_html = (
            f'<div style="font-size:9px;color:{Cores.TEXTO_3};'
            f'text-align:center;margin-top:6px;letter-spacing:0.3px;">'
            f"🕒 {agora}</div>"
        )

    copy_final = copyright or f"© {ano} {empresa}"
    copy_html = (
        f'<div style="margin-top:10px;padding-top:8px;'
        f"border-top:1px solid {Cores.BORDA};"
        f"font-size:9px;color:{Cores.TEXTO_3};text-align:center;"
        f'line-height:1.5;letter-spacing:0.2px;">'
        f"{Validadores.html_escape(copy_final)}</div>"
    )

    markup = (
        f'<div style="margin-top:28px;padding:14px 12px 10px;'
        f"border-top:1px solid {Cores.BORDA};"
        f"background:linear-gradient(180deg,#FFFFFF 0%,#F8FAFC 100%);"
        f'border-radius:0 0 10px 10px;">'
        f"{badges_row}"
        f"{unidade_html}"
        f"{itens_html}"
        f"{relogio_html}"
        f"{copy_html}"
        f"</div>"
    )

    with st.sidebar:
        _safe_render_html(markup)


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
) -> None:
    itens_dict: dict[str, Any] = {}
    if isinstance(itens, list):
        itens_dict = dict(itens)
    elif isinstance(itens, dict):
        itens_dict = itens

    _STATUS_CFG: dict[str, tuple[str, str]] = {
        "online": ("#059669", "Online"),
        "offline": ("#94A3B8", "Offline"),
        "ausente": ("#D97706", "Ausente"),
        "ocupado": ("#DC2626", "Ocupado"),
    }

    if avatar and Validadores.url(avatar):
        avatar_html = (
            f'<img src="{Validadores.html_escape(avatar)}" '
            f'alt="Avatar" style="width:42px;height:42px;border-radius:50%;'
            f'object-fit:cover;flex-shrink:0;border:2px solid #E2E8F0;" />'
        )
    else:
        if avatar:
            mono = Validadores.html_escape(avatar[:2])
            mono_size = "18px" if len(avatar) <= 2 else "14px"
        elif user_name:
            partes = user_name.strip().split()
            if len(partes) >= 2:
                mono = Validadores.html_escape((partes[0][0] + partes[-1][0]).upper())
            else:
                mono = Validadores.html_escape(user_name[:1].upper())
            mono_size = "16px"
        else:
            mono = "U"
            mono_size = "16px"

        avatar_html = (
            f'<div style="width:42px;height:42px;border-radius:50%;'
            f"background:linear-gradient(135deg,{Cores.PRIMARIA},{Cores.SECUNDARIA});"
            f"display:flex;align-items:center;justify-content:center;"
            f"font-size:{mono_size};color:#FFFFFF;font-weight:800;"
            f"flex-shrink:0;letter-spacing:0.5px;border:2px solid rgba(255,255,255,0.3);"
            f'box-shadow:0 2px 8px rgba(1,40,105,0.25);">{mono}</div>'
        )

    status_dot = ""
    status_label_html = ""
    if status and status in _STATUS_CFG:
        cor_s, label_s = _STATUS_CFG[status]
        status_dot = (
            f'<span style="position:absolute;bottom:1px;right:1px;'
            f"width:11px;height:11px;border-radius:50%;background:{cor_s};"
            f'border:2px solid #FFFFFF;box-shadow:0 0 0 1px {cor_s}40;"></span>'
        )
        status_label_html = (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f"font-size:9px;font-weight:700;color:{cor_s};"
            f'text-transform:uppercase;letter-spacing:0.5px;margin-top:2px;">'
            f'<span style="width:5px;height:5px;border-radius:50%;'
            f'background:{cor_s};display:inline-block;"></span>'
            f"{label_s}</span>"
        )

    user_section = ""
    if user_name or role or email or avatar:
        name_html = (
            f'<p style="margin:0;font-size:13px;font-weight:700;'
            f'color:{Cores.TEXTO};line-height:1.25;font-family:var(--font-titulo) !important;">'
            f"{Validadores.html_escape(user_name)}</p>"
            if user_name
            else ""
        )
        role_html = (
            f'<p style="margin:2px 0 0;font-size:10px;color:{Cores.TEXTO_3};'
            f'line-height:1.3;font-weight:500;">'
            f"{Validadores.html_escape(role)}</p>"
            if role
            else ""
        )
        email_html = (
            f'<p style="margin:2px 0 0;font-size:10px;color:{Cores.PRIMARIA};'
            f'line-height:1.3;font-weight:500;opacity:0.85;">'
            f"{Validadores.html_escape(email)}</p>"
            if email
            else ""
        )

        user_section = (
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">'
            f'<div style="position:relative;flex-shrink:0;">{avatar_html}{status_dot}</div>'
            f'<div style="min-width:0;flex:1;">'
            f"{name_html}{role_html}{email_html}{status_label_html}"
            f"</div></div>"
        )

    itens_html = ""
    if itens_dict:
        sep = (
            f'<div style="height:1px;background:{Cores.BORDA};'
            f'margin:10px 0 6px;"></div>'
            if user_section
            else ""
        )
        rows = "".join(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'padding:5px 0;">'
            f'<span style="font-size:12px;line-height:1;flex-shrink:0;'
            f'width:18px;text-align:center;opacity:0.7;">'
            f"{Validadores.html_escape(icone)}</span>"
            f'<span style="font-size:11px;color:{Cores.TEXTO_3};'
            f'font-weight:500;flex-shrink:0;">'
            f"{Validadores.html_escape(k)}</span>"
            f'<span style="font-size:11px;color:{Cores.TEXTO};'
            f"font-weight:700;margin-left:auto;text-align:right;"
            f'font-variant-numeric:tabular-nums;">'
            f"{Validadores.html_escape(v)}</span>"
            f"</div>"
            for k, v in itens_dict.items()
        )
        itens_html = f"{sep}<div>{rows}</div>"

    rodape_html = ""
    if rodape:
        rodape_html = (
            f'<div style="margin-top:8px;padding-top:8px;'
            f"border-top:1px dashed {Cores.BORDA};"
            f"font-size:9px;color:{Cores.TEXTO_3};line-height:1.4;"
            f'letter-spacing:0.2px;">'
            f"{Validadores.html_escape(rodape)}</div>"
        )

    titulo_html = ""
    if titulo:
        titulo_html = (
            f'<div style="font-size:10px;font-weight:700;color:{Cores.TEXTO_3};'
            f"text-transform:uppercase;letter-spacing:0.8px;"
            f'margin:0 0 6px 2px;">{Validadores.html_escape(titulo)}</div>'
        )

    if not user_section and not itens_html and not rodape_html:
        return

    markup = (
        f"{titulo_html}"
        f'<div style="background:linear-gradient(160deg,#FFFFFF 0%,#F8FAFC 100%);'
        f"border:1px solid {Cores.BORDA};border-radius:12px;"
        f"padding:14px;margin:8px 0 12px;"
        f'box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
        f"{user_section}"
        f"{itens_html}"
        f"{rodape_html}"
        f"</div>"
    )

    with st.sidebar:
        _safe_render_html(markup)


def render_sidebar_spacer(
    altura: Literal["pequeno", "medio", "grande", "xgrande"] | int | str = "medio",
) -> None:
    PRESETS: dict[str, str] = {
        "pequeno": "8px",
        "medio": "16px",
        "grande": "28px",
        "xgrande": "48px",
    }

    if isinstance(altura, int):
        altura_css = f"{altura}px"
    elif isinstance(altura, str):
        altura_lower = altura.lower().strip()
        if altura_lower in PRESETS:
            altura_css = PRESETS[altura_lower]
        elif any(
            altura_lower.endswith(unit) for unit in ("px", "rem", "em", "%", "vh", "vw")
        ):
            altura_css = altura_lower
        else:
            altura_css = f"{altura_lower}px"
    else:
        altura_css = "16px"

    markup = f'<div style="height:{altura_css};width:100%;display:block;" aria-hidden="true"></div>'

    with st.sidebar:
        _safe_render_html(markup)


# =============================================================================
# COMPONENTES HERO
# =============================================================================
def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    if not titulo:
        raise ValueError("render_hero: 'titulo' não pode ser vazio.")
    t = Validadores.html_escape(titulo)
    s = (
        f'<p class="hero-subtitle">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    b = (
        f'<span class="hero-badge">{Validadores.html_escape(badge)}</span>'
        if badge
        else ""
    )
    _safe_render_html(
        f'<div class="hero-corp"><div class="hero-content">'
        f'<h1 class="hero-title">{t}</h1>{s}{b}'
        f"</div></div>"
    )


def render_hero_totale_1(
    titulo: str,
    subtitulo: str = "",
    badge: str = "TOTALE ANALYTICS",
    icone: str = "⚡",
    meta_info: str = "",
) -> None:
    if not titulo:
        raise ValueError("render_hero_totale_1: 'titulo' não pode ser vazio.")
    t = Validadores.html_escape(titulo)
    b = (
        f'<div class="totale-badge-pill"><span>{Validadores.html_escape(icone)}</span>'
        f" {Validadores.html_escape(badge)}</div>"
        if badge
        else ""
    )
    s = (
        f'<p class="th-sub-muted">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    m = (
        f'<div class="th-meta">{Validadores.html_escape(meta_info)}</div>'
        if meta_info
        else ""
    )
    _safe_render_html(
        f'<div class="totale-hero-1"><div style="position:relative;z-index:2;">'
        f'{b}<h1 class="th-title-lg">{t}</h1>{s}{m}'
        f"</div></div>"
    )


def render_hero_totale_2(
    titulo: str,
    subtitulo: str = "",
    valor_destaque: str = "",
    label_destaque: str = "",
    badge: str = "PAINEL GERENCIAL",
    tag_info: str = "",
    **kwargs: Any,
) -> None:
    if not titulo:
        raise ValueError("render_hero_totale_2: 'titulo' não pode ser vazio.")

    badge_texto = kwargs.get("badge_texto", badge)
    t = Validadores.html_escape(titulo)

    b = (
        f'<span class="th-badge">{Validadores.html_escape(badge_texto)}</span>'
        if badge_texto
        else ""
    )
    tag = (
        f'<span class="th-tag">• {Validadores.html_escape(tag_info)}</span>'
        if tag_info
        else ""
    )
    s = (
        f'<p class="th-sub">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    card = ""
    if valor_destaque:
        card = (
            f'<div class="totale-hero-2-card">'
            f'<div class="th-card-label">{Validadores.html_escape(label_destaque)}</div>'
            f'<div class="th-card-value">{Validadores.html_escape(valor_destaque)}</div>'
            f"</div>"
        )

    _safe_render_html(
        f'<div class="totale-hero-2">'
        f'<div>{b}{tag}<h1 class="th-title">{t}</h1>{s}</div>'
        f"{card}"
        f"</div>"
    )


def render_hero_migracao(
    titulo: str,
    subtitulo: str = "",
    badge: str = "MIGRAÇÃO DE DADOS",
    icone: str = "🔄",
    stats: Sequence[dict[str, str]] | None = None,
) -> None:
    if not titulo:
        raise ValueError("render_hero_migracao: 'titulo' não pode ser vazio.")
    t = Validadores.html_escape(titulo)
    b = (
        f'<div class="hero-migracao-badge"><span>{Validadores.html_escape(icone)}</span>'
        f" {Validadores.html_escape(badge)}</div>"
        if badge
        else ""
    )
    s = (
        f'<p class="hero-migracao-subtitle">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    stats_html = ""
    if stats:
        items = "".join(
            f'<div class="hero-migracao-stat">'
            f"<strong>{Validadores.html_escape(st_item.get('valor', ''))}</strong>"
            f" {Validadores.html_escape(st_item.get('label', ''))}</div>"
            for st_item in stats[:4]
        )
        stats_html = f'<div class="hero-migracao-stats">{items}</div>'

    _safe_render_html(
        f'<div class="hero-migracao"><div style="position:relative;z-index:2;">'
        f'{b}<h1 class="hero-migracao-title">{t}</h1>{s}{stats_html}'
        f"</div></div>"
    )


def render_hero_pme(
    titulo: str,
    subtitulo: str = "",
    badge: str = "PME CONNECT",
    icone: str = "🚀",
    features: Sequence[str] | None = None,
) -> None:
    if not titulo:
        raise ValueError("render_hero_pme: 'titulo' não pode ser vazio.")
    t = Validadores.html_escape(titulo)
    b = (
        f'<div class="hero-pme-badge"><span>{Validadores.html_escape(icone)}</span>'
        f" {Validadores.html_escape(badge)}</div>"
        if badge
        else ""
    )
    s = (
        f'<p class="hero-pme-subtitle">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    feat_html = ""
    if features:
        items = "".join(
            f'<span class="hero-pme-feature">✓ {Validadores.html_escape(f)}</span>'
            for f in features[:5]
        )
        feat_html = f'<div class="hero-pme-features">{items}</div>'

    _safe_render_html(
        f'<div class="hero-pme"><div style="position:relative;z-index:2;">'
        f'{b}<h1 class="hero-pme-title">{t}</h1>{s}{feat_html}'
        f"</div></div>"
    )


# =============================================================================
# OUTROS COMPONENTES
# =============================================================================


def render_sidebar_status(
    status: str = "Online",
    ultima_atualizacao: str = "",
    total_registros: int | str | None = None,
    detalhes: dict[str, Any] | None = None,
    tipo: Literal["ok", "info", "alerta", "critico"] = "ok",
    **kwargs: Any,
) -> None:
    detalhes_dict = detalhes or {}

    detalhes_html = "".join(
        f"""
        <div class="sidebar-footer-item">
            <span class="sidebar-footer-label">{Validadores.html_escape(k)}</span>
            <span class="sidebar-footer-value">{Validadores.html_escape(v)}</span>
        </div>
        """
        for k, v in detalhes_dict.items()
    )

    mapa_status_cor = {
        "ok": Cores.SUCESSO,
        "info": Cores.PRIMARIA,
        "alerta": Cores.ATENCAO,
        "critico": Cores.ALERTA,
    }
    cor_status = mapa_status_cor.get(tipo, Cores.NEUTRO)

    markup = f"""
    <div class="user-info-card" style="border-left:3px solid {cor_status};">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span style="width:10px;height:10px;border-radius:50%;background:{cor_status};display:inline-block;flex-shrink:0;"></span>
            <strong style="color:{Cores.TEXTO};font-size:13px;">{Validadores.html_escape(status)}</strong>
        </div>
        {f'<div style="font-size:11px;color:{Cores.TEXTO_3};line-height:1.4;">Atualizado em: {Validadores.html_escape(ultima_atualizacao)}</div>' if ultima_atualizacao else ""}
        {f'<div style="font-size:11px;color:{Cores.TEXTO_3};margin-top:4px;line-height:1.4;">Total: <strong>{Validadores.html_escape(total_registros)}</strong></div>' if total_registros is not None else ""}
        {detalhes_html}
    </div>
    """

    with st.sidebar:
        st.markdown(markup, unsafe_allow_html=True)


def render_section_header(
    title: str = "",
    icon: str = "",
    badge: str = "",
    titulo: str = "",
    subtitulo: str = "",
    icone: str = "",
    badge_tipo: TipoBadgeType = "default",
) -> None:
    titulo_final = titulo or title
    icon_final = icone or icon
    bg_badge, cor_badge, borda_badge = ConfigCores.BADGE.get(
        badge_tipo, ConfigCores.BADGE["default"]
    )

    badge_html = (
        f'<span style="background:{bg_badge};color:{cor_badge};border:1px solid {borda_badge};padding:4px 12px;border-radius:4px;font-size:11px;font-weight:600;text-transform:uppercase;">{Validadores.html_escape(badge)}</span>'
        if badge
        else ""
    )
    icone_html = (
        f'<span style="font-size:24px;line-height:1;">{Validadores.html_escape(icon_final)}</span>'
        if icon_final
        else ""
    )
    sub_html = (
        f'<p class="section-subtitle">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )

    markup = f"""
    <div class="section-header">
        <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                {icone_html}
                <h2 class="section-title">{Validadores.html_escape(titulo_final)}</h2>
                {badge_html}
            </div>
            {sub_html}
        </div>
    </div>
    """
    _safe_render_html(markup)


# =============================================================================
# COMPONENTES KPI E MÉTRICAS PREMIUM
# =============================================================================
def render_kpi(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPIType = "azul",
    icone: str = "",
) -> None:
    cor_hex = Validadores.resolver_cor_tema(tema)

    icone_html = ""
    if icone:
        icone_html = (
            f'<div class="kpi-icon-wrapper" style="background-color:{cor_hex}15; color:{cor_hex};">'
            f'<span style="font-size:20px; line-height:1;">{Validadores.html_escape(icone)}</span>'
            f"</div>"
        )

    sub_html = (
        f'<div class="kpi-sub-premium">{Validadores.html_escape(sub)}</div>'
        if sub
        else ""
    )

    markup = f"""
    <div class="card-premium">
        <div class="card-accent-top" style="background-color:{cor_hex};"></div>
        <div class="card-header-flex">
            <div class="kpi-label-premium">{Validadores.html_escape(label)}</div>
            {icone_html}
        </div>
        <div>
            <div class="kpi-value-premium">{Validadores.html_escape(valor)}</div>
            {sub_html}
        </div>
    </div>
    """
    _safe_render_html(markup, col)


def render_metric_card(
    col: Any,
    label: str,
    valor: str,
    trend: TipoTrendType = "none",
    trend_valor: str = "",
    sub: str = "",
) -> None:
    trend_icone = ConfigCores.TREND_ICONS.get(trend, "")
    trend_classe = f"trend-{trend}" if trend in ("up", "down", "neutral") else ""

    trend_html = ""
    if trend != "none" and trend_valor:
        trend_html = (
            f'<span class="trend-pill {trend_classe}">'
            f"<span>{trend_icone}</span> {Validadores.html_escape(trend_valor)}"
            f"</span>"
        )

    sub_html = ""
    if sub or trend_html:
        sub_text = (
            f'<span style="margin-left:6px;">{Validadores.html_escape(sub)}</span>'
            if sub
            else ""
        )
        sub_html = f'<div class="kpi-sub-premium">{trend_html}{sub_text}</div>'

    markup = f"""
    <div class="card-premium">
        <div class="kpi-label-premium" style="margin-bottom:12px;">{Validadores.html_escape(label)}</div>
        <div>
            <div class="kpi-value-premium">{Validadores.html_escape(valor)}</div>
            {sub_html}
        </div>
    </div>
    """
    _safe_render_html(markup, col)


def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPIType = "azul",
    icone: str = "",
) -> None:
    cor = _resolver_cor_tema(tema)
    container.markdown(
        f"""
        <div style="background:white;border-radius:6px;padding:12px 16px;
             border-left:3px solid {cor};margin-bottom:8px;
             box-shadow:0 1px 4px rgba(0,0,0,0.06);">
            <div style="font-family:{Cores.TEXTO};font-size:10px;
                 color:{Cores.TEXTO_3};text-transform:uppercase;
                 letter-spacing:1px;font-weight:700;">{label}</div>
            <div style="font-family:{Fontes.TITULO};font-size:20px;
                 color:{cor};font-weight:800;line-height:1.2;
                 margin-top:4px;font-variant-numeric:tabular-nums;">{valor}</div>
            <div style="font-family:{Fontes.TEXTO};font-size:11px;
                 color:{Cores.TEXTO_3};margin-top:2px;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insight(msg: str, tipo: TipoInsightType = "info") -> None:
    if not msg:
        return
    bg, texto, borda, icone = ConfigCores.INSIGHT.get(tipo, ConfigCores.INSIGHT["info"])
    msg_html = Formatadores.markdown_para_html(msg)
    markup = f'<div style="background:{bg};color:{texto};border-left:4px solid {borda};padding:12px 16px;border-radius:6px;margin:10px 0;font-size:14px;line-height:1.6;"><span style="margin-right:8px;">{icone}</span>{msg_html}</div>'
    _safe_render_html(markup)


def render_empty_state(
    tipo: TipoEmptyStateType = "padrao",
    titulo: str = "",
    descricao: str = "",
    acao: str = "",
    icone: str = "",
) -> None:
    _, _, icone_default, titulo_default = ConfigCores.EMPTY_STATE.get(
        tipo, ConfigCores.EMPTY_STATE["padrao"]
    )
    desc_html = (
        f'<p class="empty-state-desc">{Validadores.html_escape(descricao)}</p>'
        if descricao
        else ""
    )
    acao_html = (
        f'<p style="margin:12px 0 0 0;font-size:13px;color:{Cores.SECUNDARIA};font-weight:600;">{Validadores.html_escape(acao)}</p>'
        if acao
        else ""
    )

    markup = f"""
    <div class="empty-state">
        <span class="empty-state-icon">{Validadores.html_escape(icone or icone_default)}</span>
        <h3 class="empty-state-title">{Validadores.html_escape(titulo or titulo_default)}</h3>
        {desc_html}
        {acao_html}
    </div>
    """
    _safe_render_html(markup)


def render_progress_bar(
    valor: float,
    maximo: float = 100.0,
    label: str = "",
    mostrar_valor: bool = True,
    tema: TipoProgressBarType = "azul",
    altura: str = "medio",
    unidade: str = "%",
) -> None:
    altura_px = {"pequeno": "6px", "medio": "10px", "grande": "14px"}.get(
        altura, "10px"
    )
    porcentagem = min(100.0, max(0.0, (valor / maximo) * 100)) if maximo > 0 else 0.0
    bg_style = (
        f"linear-gradient(90deg, {Cores.PRIMARIA}, {Cores.SECUNDARIA})"
        if tema == "gradiente"
        else ConfigCores.PROGRESS_BAR.get(tema, Cores.PRIMARIA)
    )

    label_html = (
        f'<div class="progress-bar-label"><span>{Validadores.html_escape(label)}</span>{f"<span style=font-weight:700;color:{Cores.TEXTO};>{porcentagem:.1f}{unidade}</span>" if mostrar_valor else ""}</div>'
        if label or mostrar_valor
        else ""
    )
    markup = f'{label_html}<div class="progress-bar-container" style="height:{altura_px};"><div class="progress-bar-fill" style="width:{porcentagem}%;height:{altura_px};background:{bg_style};"></div></div>'
    _safe_render_html(markup)


# =============================================================================
# TABELA HTML PREMIUM (RESISTENTE A DUPLICADAS E AMBIGUIDADE)
# =============================================================================
def render_table_html(
    df: pd.DataFrame,
    titulo: str = "",
    colunas: Sequence[str] | None = None,
    alinhamentos: dict[str, Literal["left", "center", "right"]] | None = None,
    striped: bool = True,
    max_rows: int = 100,
    fmt: FmtDict | None = None,
    color_rules: dict[str, Any] | None = None,
    colunas_num: Sequence[str] | None = None,
    height: int | None = 400,
    mostrar_data: bool = True,
) -> None:
    """Renderiza uma tabela premium (SaaS UI) com Sticky Headers protegida contra ambiguidade booleana."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        render_empty_state(tipo="dados", descricao="Nenhum dado disponível na tabela.")
        return

    # Deduplicação defensiva de colunas para prevenir a.any() / a.all()
    df_clean = df.loc[:, ~df.columns.duplicated()].copy()

    if colunas:
        cols_validas = [c for c in colunas if c in df_clean.columns]
        df_display = df_clean[cols_validas].copy() if cols_validas else df_clean.copy()
    else:
        df_display = df_clean.copy()

    if len(df_display) > max_rows:
        df_display = df_display.head(max_rows)

    alinhamentos = dict(alinhamentos or {})
    if colunas_num:
        for c in colunas_num:
            if c in df_display.columns:
                alinhamentos[c] = "right"

    th_parts: list[str] = []
    for col in df_display.columns:
        align = alinhamentos.get(col, "left")
        th_parts.append(
            f'<th style="text-align:{align};">{Validadores.html_escape(str(col))}</th>'
        )
    th_html = "".join(th_parts)

    tr_parts: list[str] = []
    for i, (_, row) in enumerate(df_display.iterrows()):
        td_parts: list[str] = []
        for col in df_display.columns:
            val = row[col]
            if isinstance(val, (pd.Series, np.ndarray)):
                val = val.iloc[0] if isinstance(val, pd.Series) else val[0]

            align = alinhamentos.get(col, "left")

            is_na = pd.isna(val)
            if isinstance(is_na, (pd.Series, np.ndarray)):
                is_na = bool(is_na.any())

            if is_na:
                val_str = "—"
            else:
                if fmt and col in fmt and fmt[col] is not None:
                    formatter = fmt[col]
                    if isinstance(formatter, str):
                        try:
                            val = formatter.format(val)
                        except Exception:
                            pass
                    elif callable(formatter):
                        try:
                            val = formatter(val)
                        except Exception:
                            pass
                val_str = Validadores.html_escape(str(val))

            if color_rules and col in color_rules:
                regras = color_rules[col]
                if isinstance(regras, dict):
                    raw_val = row[col]
                    if isinstance(raw_val, (pd.Series, np.ndarray)):
                        raw_val = (
                            raw_val.iloc[0]
                            if isinstance(raw_val, pd.Series)
                            else raw_val[0]
                        )
                    classe_cor = regras.get(str(raw_val), "")
                    if classe_cor in ("positive", "sucesso"):
                        val_str = f'<span class="td-badge" style="background:#ECFDF5;color:#059669;">{val_str}</span>'
                    elif classe_cor in ("negative", "alerta"):
                        val_str = f'<span class="td-badge" style="background:#FEF2F2;color:#DC2626;">{val_str}</span>'
                    elif classe_cor in ("neutral", "info"):
                        val_str = f'<span class="td-badge" style="background:#F0F9FF;color:#0284C7;">{val_str}</span>'

            font_style = (
                "font-variant-numeric: tabular-nums; font-family: var(--font-codigo) !important; font-size: 12px;"
                if align == "right"
                else ""
            )

            td_parts.append(
                f'<td style="text-align:{align}; {font_style}">{val_str}</td>'
            )

        classe_linha = ' class="striped"' if striped and i % 2 == 1 else ""
        tr_parts.append(f"<tr{classe_linha}>{''.join(td_parts)}</tr>")

    titulo_html = (
        f'<div style="font-weight:800;font-size:16px;color:#0F172A;margin-bottom:12px;font-family:var(--font-titulo) !important;">{Validadores.html_escape(titulo)}</div>'
        if titulo
        else ""
    )
    data_html = (
        f'<div style="font-size:11px;color:#94A3B8;margin-top:8px;text-align:right;font-weight:500;">Atualizado em: {datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")}</div>'
        if mostrar_data
        else ""
    )

    height_style = f"max-height:{height}px;" if height else ""

    markup = f"""
    <div style="margin: 24px 0;">
        {titulo_html}
        <div class="table-premium-wrapper">
            <div class="table-premium-scroll" style="{height_style}">
                <table class="totale-table-pro">
                    <thead><tr>{th_html}</tr></thead>
                    <tbody>{"".join(tr_parts)}</tbody>
                </table>
            </div>
        </div>
        {data_html}
    </div>
    """
    _safe_render_html(markup)
