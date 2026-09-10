"""
components/componentes.py
=========================
Design System Streamlit — TOTALE

Versão: 4.4.0 (Enterprise Polish & Full Architecture)
Autor: TOTALE Tecnologia

Principais evoluções concretizadas:
• API pública 100% retrocompatível (nenhuma função removida).
• Componentes seguros (escapamento HTML, validação de container).
• Tipagem forte (Literal, TypeAlias) para Pylance/Pyright.
• Factory de cards (_card_premium) — evita repetição de HTML.
• Tabela premium completa: linha_destaque, condicoes_colunas, caption, export_excel.
• Progress bar com shimmer; KPI com delta/trend; Insight com título.
• Normalizadores de tema/badge/progress/trend/insight (tolerância a erros).
• CSS modular (variáveis, heróis, cards, tabelas, extras) + dark mode.
• Injeção de fontes protegida por session_state (não redundante).
• Componentes novos: render_card, render_badge, render_notification,
  render_spacer, render_skeleton, formatar_numero_br.
• Acessibilidade: aria-label, role="region", focus-visible.
"""

from __future__ import annotations

import html as html_lib
import io
import logging
import re
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Protocol, TypeAlias, runtime_checkable
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLOS E TIPOS ESTRITOS
# =============================================================================
@runtime_checkable
class StreamlitContainer(Protocol):
    def markdown(
        self, body: str, unsafe_allow_html: bool = False, **kwargs: Any
    ) -> Any: ...


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
# ENUMS
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


# =============================================================================
# CONFIGURAÇÃO DE TIPOGRAFIA E CORES
# =============================================================================
class Fontes:
    TITULO = "'Manrope', 'Segoe UI', Arial, sans-serif"
    TEXTO = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    CODIGO = "'JetBrains Mono', Consolas, 'Courier New', monospace"


class GoogleFonts:
    URLS: tuple[str, ...] = (
        "https://fonts.googleapis.com/icon?family=Material+Icons",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap",
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


# =============================================================================
# HELPERS
# =============================================================================
def _resolver_cor_tema(tema: str) -> str:
    cor = ConfigCores.TEMA.get(tema)
    if cor is None:
        logger.warning("Tema desconhecido: '%s'. Usando 'azul'.", tema)
        return Cores.PRIMARIA
    return cor


def _markdown_inline_para_html(texto: str) -> str:
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    return texto


def formatar_numero_br(valor: Any, casas: int = 0) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if casas <= 0:
        return f"{int(round(v)):,}".replace(",", ".")
    txt = f"{v:,.{casas}f}"
    return txt.replace(",", "§").replace(".", ",").replace("§", ".")


def normalizar_tipo(valor: Any, permitido: set[str], padrao: str) -> str:
    if isinstance(valor, Enum):
        s = str(valor.value).strip().lower()
    else:
        s = str(valor or "").strip().lower()
    return s if s in permitido else padrao


def normalizar_tema_kpi(tema: Any) -> TemaKPIType:
    return normalizar_tipo(
        tema, {"azul", "verde", "vermelho", "laranja", "cinza", "roxo"}, "azul"
    )  # type: ignore[return-value]


def normalizar_tipo_badge(tipo: Any) -> TipoBadgeType:
    return normalizar_tipo(
        tipo, {"default", "sucesso", "alerta", "erro", "info", "roxo"}, "default"
    )  # type: ignore[return-value]


def normalizar_tipo_progress(tema: Any) -> TipoProgressBarType:
    return normalizar_tipo(
        tema, {"azul", "laranja", "verde", "vermelho", "roxo", "gradiente"}, "azul"
    )  # type: ignore[return-value]


def normalizar_tipo_trend(trend: Any) -> TipoTrendType:
    return normalizar_tipo(trend, {"up", "down", "neutral", "none"}, "none")  # type: ignore[return-value]


def normalizar_tipo_insight(tipo: Any) -> TipoInsightType:
    return normalizar_tipo(tipo, {"ok", "info", "alerta", "critico", "acao"}, "info")  # type: ignore[return-value]


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
# GARANTIA DE CONTAINER
# =============================================================================
def _garantir_container(container: Any = None) -> Any:
    if container is None:
        return st
    if hasattr(container, "markdown"):
        return container
    logger.warning(
        "Container inválido recebido: %s. Usando st.", type(container).__name__
    )
    return st


def _safe_render_html(html_str: str, container: Any = None) -> None:
    if not html_str:
        return
    c = _garantir_container(container)
    clean = html_str.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    clean = re.sub(r">\s+<", "><", clean)
    clean = re.sub(r" {2,}", " ", clean)
    clean = clean.strip()
    try:
        c.markdown(clean, unsafe_allow_html=True)
    except Exception as exc:
        logger.error("Falha ao renderizar HTML customizado: %s", exc)
        st.markdown(clean, unsafe_allow_html=True)


# =============================================================================
# BLOCO CSS MODULAR (COM CACHE)
# =============================================================================
_CSS_VARS_ROOT = f"""
:root {{
    --font-titulo: {Fontes.TITULO};
    --font-texto: {Fontes.TEXTO};
    --font-codigo: {Fontes.CODIGO};
    --cor-primaria: {Cores.PRIMARIA};
    --cor-primaria-light: {Cores.PRIMARIA_LIGHT};
    --cor-secundaria: {Cores.SECUNDARIA};
    --cor-sucesso: {Cores.SUCESSO};
    --cor-alerta: {Cores.ALERTA};
    --cor-texto: {Cores.TEXTO};
    --cor-texto-2: {Cores.TEXTO_2};
    --cor-texto-3: {Cores.TEXTO_3};
    --cor-borda: {Cores.BORDA};
    --cor-fundo: {Cores.FUNDO};
    --cor-card-bg: #FFFFFF;
    --cor-card-hover: #F8FAFC;
    --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
    --shadow-lg: 0 10px 28px rgba(0,0,0,0.12);
}}
@media (prefers-color-scheme: dark) {{
    :root {{
        --cor-texto: #F9FAFB; --cor-texto-2: #E5E7EB; --cor-texto-3: #9CA3AF;
        --cor-borda: #334155; --cor-fundo: #0B0F19; --cor-card-bg: #111827; --cor-card-hover: #1E293B;
    }}
}}
"""

_CSS_RESET_GLOBAL = """
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stSidebar"], p, label, div, li, a, button, input, select, textarea { font-family: var(--font-texto) !important; }
h1, h2, h3, h4, h5, h6, .hero-title, .section-title, .kpi-value, .metric-value, [data-testid="stMetricValue"] { font-family: var(--font-titulo) !important; font-weight: 700; letter-spacing: -0.3px; }
h1, .hero-title { font-weight: 800; letter-spacing: -0.6px; }
.main .block-container { padding-top: 1rem; max-width: 1400px; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #F1F5F9; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
*:focus-visible { outline: 2px solid #0A48AA; outline-offset: 2px; border-radius: 4px; }
"""

_CSS_HEROS = """
@keyframes hero-gradient-shift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
.hero-corp { background: linear-gradient(120deg, #012869 0%, #023A9E 35%, #1E5FCC 55%, #E85D04 82%, #F37C04 100%); background-size: 180% 180%; animation: hero-gradient-shift 14s ease infinite; padding: 34px 44px; border-radius: var(--radius-lg); color: #FFFFFF; box-shadow: 0 10px 40px rgba(1,40,105,0.30); margin-bottom: 24px; position: relative; overflow: hidden; }
.hero-corp::before { content: ''; position: absolute; top: -50%; right: -20%; width: 420px; height: 420px; background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 65%); pointer-events: none; }
.totale-hero-1 { background: linear-gradient(135deg, #011E52 0%, #012869 45%, #0A48AA 80%, #F37C04 130%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(243,124,4,0.25); box-shadow: 0 12px 32px rgba(1,40,105,0.28); margin-bottom: 24px; position: relative; overflow: hidden; }
.totale-hero-2 { background: linear-gradient(120deg, #012869 0%, #033486 50%, #0747B3 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border-left: 6px solid #F37C04; box-shadow: 0 10px 28px rgba(1,40,105,0.22); margin-bottom: 24px; display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: center; position: relative; overflow: hidden; }
@media (max-width: 768px) { .totale-hero-2 { grid-template-columns: 1fr; } }
.totale-hero-2-card { background: rgba(255,255,255,0.08); -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.18); border-radius: 12px; padding: 16px 24px; min-width: 180px; text-align: center; position: relative; z-index: 2; }
.hero-migracao { background: linear-gradient(135deg, #4C1D95 0%, #6D28D9 35%, #7C3AED 60%, #A78BFA 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(167,139,250,0.30); box-shadow: 0 12px 32px rgba(124,58,237,0.35); margin-bottom: 24px; position: relative; overflow: hidden; }
.hero-pme { background: linear-gradient(135deg, #059669 0%, #10B981 35%, #3B82F6 70%, #60A5FA 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(255,255,255,0.25); box-shadow: 0 12px 32px rgba(16,185,129,0.30); margin-bottom: 24px; position: relative; overflow: hidden; }
"""

_CSS_CARDS = """
.card-premium { background: var(--cor-card-bg); border-radius: 12px; padding: 20px 24px; border: 1px solid var(--cor-borda); box-shadow: 0 1px 2px rgba(15,23,42,0.03), 0 4px 6px -1px rgba(0,0,0,0.02); transition: transform 0.28s cubic-bezier(0.4,0,0.2,1), box-shadow 0.28s ease, border-color 0.28s ease; margin-bottom: 12px; position: relative; overflow: hidden; display: flex; flex-direction: column; justify-content: space-between; }
.card-premium:hover { transform: translateY(-4px); box-shadow: 0 4px 8px -2px rgba(15,23,42,0.05), 0 12px 24px -6px rgba(15,23,42,0.10); border-color: #CBD5E1; }
.card-accent-top { position: absolute; top: 0; left: 0; right: 0; height: 3px; }
.card-header-flex { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.kpi-label-premium { font-size: 12px; font-weight: 600; color: var(--cor-texto-3); text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.4; }
.kpi-icon-wrapper { display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0; }
.kpi-value-premium { font-size: 32px; font-weight: 800; color: var(--cor-texto); line-height: 1; font-variant-numeric: tabular-nums; font-family: var(--font-titulo) !important; letter-spacing: -0.5px; }
.kpi-sub-premium { font-size: 13px; color: var(--cor-texto-3); margin-top: 8px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.trend-pill { display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 20px; font-size: 12px; font-weight: 700; line-height: 1; }
.trend-up { background: #ECFDF5; color: #059669; }
.trend-down { background: #FEF2F2; color: #DC2626; }
.trend-neutral { background: #F8FAFC; color: #64748B; }
.totale-badge-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border: 1px solid transparent; }
"""

_CSS_TABELAS = """
.table-premium-wrapper { background: var(--cor-card-bg); border-radius: 12px; border: 1px solid var(--cor-borda); box-shadow: 0 1px 3px rgba(0,0,0,0.03); overflow: hidden; margin: 16px 0; position: relative; }
.table-premium-scroll { width: 100%; overflow-x: auto; scrollbar-width: thin; scrollbar-color: #CBD5E1 transparent; }
.table-premium-scroll::-webkit-scrollbar { height: 6px; width: 6px; }
.table-premium-scroll::-webkit-scrollbar-thumb { background-color: #CBD5E1; border-radius: 3px; }
.totale-table-pro { width: 100%; border-collapse: separate; border-spacing: 0; text-align: left; }
.totale-table-pro th { background: #F8FAFC; color: #475569; font-family: var(--font-texto) !important; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 14px 16px; position: sticky; top: 0; z-index: 10; border-bottom: 1px solid var(--cor-borda); white-space: nowrap; }
.totale-table-pro th::after { content: ''; position: absolute; left: 0; right: 0; bottom: -5px; height: 5px; background: linear-gradient(to bottom, rgba(0,0,0,0.02) 0%, rgba(0,0,0,0) 100%); pointer-events: none; }
.totale-table-pro td { padding: 13px 16px; border-bottom: 1px solid #F1F5F9; color: var(--cor-texto-2); font-size: 13px; font-family: var(--font-texto) !important; vertical-align: middle; transition: background 0.2s ease; }
.totale-table-pro tbody tr:last-child td { border-bottom: none; }
.totale-table-pro tbody tr:hover td { background-color: var(--cor-card-hover); color: var(--cor-texto); }
.totale-table-pro tbody tr.striped td { background-color: #FAFCFE; }
.totale-table-pro tbody tr.striped:hover td { background-color: var(--cor-card-hover); }
.totale-table-pro tbody tr.linha-destaque td { background: linear-gradient(90deg, #FFF7ED 0%, #FFFBEB 100%) !important; border-top: 2px solid #F37C04; color: #7C2D12 !important; font-weight: 800; font-family: var(--font-titulo) !important; }
.totale-table-pro tbody tr.linha-destaque:hover td { background: linear-gradient(90deg, #FFEDD5 0%, #FEF3C7 100%) !important; }
.td-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
"""

_CSS_EXTRAS = """
@keyframes pb-shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
.totale-pb-fill { position: relative; overflow: hidden; }
.totale-pb-fill.animado::after { content: ''; position: absolute; inset: 0; background: linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.38) 50%, transparent 70%); background-size: 200% 100%; animation: pb-shimmer 2.2s linear infinite; }
.totale-skeleton { background: linear-gradient(90deg, #F1F5F9 25%, #E2E8F0 50%, #F1F5F9 75%); background-size: 200% 100%; animation: pb-shimmer 1.4s linear infinite; border-radius: 8px; }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 48px 32px; margin: 24px 0; background: #FAFBFD; border: 2px dashed #E2E8F0; border-radius: 14px; transition: border-color 0.25s ease; }
.empty-state:hover { border-color: #CBD5E1; }
.empty-state-icon { font-size: 44px; line-height: 1; margin-bottom: 14px; }
.empty-state-title { font-family: var(--font-titulo) !important; font-size: 17px; font-weight: 800; color: #334155; margin: 0 0 6px; }
.empty-state-desc { font-size: 13px; color: #64748B; margin: 0; max-width: 420px; line-height: 1.55; }
.totale-insight { border-radius: 10px; padding: 13px 16px; margin: 12px 0; font-size: 14px; line-height: 1.6; box-shadow: 0 1px 3px rgba(15,23,42,0.04); }
.totale-insight-title { display: block; font-weight: 900; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px; }
.section-header { display: flex; align-items: center; gap: 12px; margin: 32px 0 16px 0; padding-bottom: 12px; border-bottom: 2px solid var(--cor-borda); }
.section-subtitle { margin: 6px 0 0; font-size: 13px; color: var(--cor-texto-3); }
.user-info-card { background: linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%); border: 1px solid var(--cor-borda); border-radius: 12px; padding: 16px; margin: 12px 0; }
"""


# =============================================================================
# PLOTLY + FONT INJECTOR
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
        if st.session_state.get("_totale_fonts_head_injected", False):
            return
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
                const existentes = Array.from(
                    head.querySelectorAll('link[rel="stylesheet"]')
                ).map(function (l) {{ return l.href; }});
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
        st.session_state["_totale_fonts_head_injected"] = True


class CSSInjector:
    @staticmethod
    @lru_cache(maxsize=1)
    def _build_css() -> str:
        return (
            f"{FontInjector._build_links_html()}\n"
            "<style>\n"
            f"{_CSS_VARS_ROOT}\n"
            f"{_CSS_RESET_GLOBAL}\n"
            f"{_CSS_HEROS}\n"
            f"{_CSS_CARDS}\n"
            f"{_CSS_TABELAS}\n"
            f"{_CSS_EXTRAS}\n"
            "</style>"
        )

    @staticmethod
    def injetar() -> None:
        _safe_render_html(CSSInjector._build_css())


# =============================================================================
# API PÚBLICA
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
# SIDEBAR
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
            f'<span style="display:inline-block;background-color:{Cores.AZUL_SUAVE};'
            f"color:{Cores.PRIMARIA};font-weight:700;font-size:10px;padding:2px 8px;"
            f"border-radius:12px;border:1px solid #BFDBFE;margin-top:6px;"
            f'text-transform:uppercase;">{Validadores.html_escape(versao)}</span>'
            if versao
            else ""
        )
        icone_html = (
            f'<span style="font-size:22px;color:{Cores.SECUNDARIA};line-height:1;">'
            f"{Validadores.html_escape(icone)}</span>"
            if not logo_final
            else ""
        )
        markup = f"""
        <div style="padding:10px 0 16px 0;border-bottom:1px solid {Cores.BORDA};margin-bottom:16px;">
            <div style="display:flex;align-items:center;gap:10px;">
                {icone_html}
                <div>
                    <h2 style="font-family:{Fontes.TITULO};font-size:18px;font-weight:800;
                    color:{Cores.PRIMARIA};margin:0;line-height:1.2;">{Validadores.html_escape(nome_final)}</h2>
                    <div style="font-family:{Fontes.TEXTO};font-size:11px;color:{Cores.TEXTO_3};margin-top:2px;">
                        {Validadores.html_escape(subtitulo_final)}
                    </div>
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
    margens = {"pequeno": "6px 0", "medio": "14px 0", "grande": "24px 0"}
    margem = margens.get(espacamento, margens["medio"])
    cor_final = cor or Cores.BORDA
    if estilo == "espaco":
        alturas = {"pequeno": "8px", "medio": "16px", "grande": "28px"}
        _safe_render_html(
            f'<div style="height:{alturas.get(espacamento, "16px")};"></div>',
            st.sidebar,
        )
        return
    if label:
        label_esc = Validadores.html_escape(label)
        style_line = (
            "border:none;border-top:1.5px dashed " + cor_final + ";"
            if estilo == "pontilhado"
            else (
                "border:none;height:1px;background:linear-gradient(90deg,transparent 0%,"
                + cor_final
                + " 40%,"
                + cor_final
                + " 60%,transparent 100%);"
                if estilo == "gradiente"
                else "border:none;border-top:1px solid " + cor_final + ";"
            )
        )
        markup = f'<div style="display:flex;align-items:center;gap:10px;margin:{margem};"><div style="flex:1;{style_line}"></div><span style="font-size:9px;font-weight:700;color:{Cores.TEXTO_3};text-transform:uppercase;letter-spacing:1.2px;white-space:nowrap;">{label_esc}</span><div style="flex:1;{style_line}"></div></div>'
        with st.sidebar:
            _safe_render_html(markup)
        return
    style_line = (
        "border:none;border-top:1.5px dashed " + cor_final + ";"
        if estilo == "pontilhado"
        else (
            "border:none;height:1px;background:linear-gradient(90deg,transparent 0%,"
            + cor_final
            + " 50%,transparent 100%);"
            if estilo == "gradiente"
            else "border:none;border-top:1px solid " + cor_final + ";"
        )
    )
    with st.sidebar:
        _safe_render_html(f'<div style="margin:{margem};{style_line}"></div>')


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
    itens_dict: dict[str, Any] = (
        dict(itens) if isinstance(itens, dict) else dict(itens or [])
    )
    if ano is None:
        ano = datetime.now(timezone.utc).year
    _AMB_CFG = {
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
    versao_html = (
        f'<span style="display:inline-block;background:#F0F4FF;color:{Cores.PRIMARIA};font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;border:1px solid #C7D2FE;letter-spacing:0.4px;text-transform:uppercase;">{Validadores.html_escape(versao if str(versao).startswith("v") else f"v{versao}")}</span>'
        if versao
        else ""
    )
    amb_html = ""
    if ambiente:
        bg_a, fg_a, dot_a = _AMB_CFG.get(
            ambiente.lower().strip(), ("#F3F4F6", "#374151", "#9CA3AF")
        )
        amb_html = f'<span style="display:inline-flex;align-items:center;gap:5px;background:{bg_a};color:{fg_a};font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;letter-spacing:0.4px;text-transform:uppercase;"><span style="width:6px;height:6px;border-radius:50%;background:{dot_a};display:inline-block;flex-shrink:0;"></span>{Validadores.html_escape(ambiente)}</span>'
    badges_row = (
        f'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:10px;">{versao_html}{amb_html}</div>'
        if (versao_html or amb_html)
        else ""
    )
    unidade_html = (
        f'<div style="font-size:10px;font-weight:600;color:{Cores.TEXTO_2};margin-bottom:8px;letter-spacing:0.2px;">{Validadores.html_escape(unidade)}</div>'
        if unidade
        else ""
    )
    itens_html = ""
    if itens_dict:
        rows = "".join(
            f'<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;gap:8px;"><span style="font-size:10px;color:{Cores.TEXTO_3};font-weight:500;">{Validadores.html_escape(k)}</span><span style="font-size:10px;color:{Cores.TEXTO_2};font-weight:700;font-variant-numeric:tabular-nums;text-align:right;">{Validadores.html_escape(v)}</span></div>'
            for k, v in itens_dict.items()
        )
        itens_html = f'<div style="border-top:1px solid {Cores.BORDA};padding-top:8px;margin-top:4px;">{rows}</div>'
    relogio_html = (
        f'<div style="font-size:9px;color:{Cores.TEXTO_3};text-align:center;margin-top:6px;letter-spacing:0.3px;">🕒 {datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")}</div>'
        if mostrar_rel
        else ""
    )
    copy_final = copyright or f"© {ano} {empresa}"
    copy_html = f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid {Cores.BORDA};font-size:9px;color:{Cores.TEXTO_3};text-align:center;line-height:1.5;letter-spacing:0.2px;">{Validadores.html_escape(copy_final)}</div>'
    markup = f'<div style="margin-top:28px;padding:14px 12px 10px;border-top:1px solid {Cores.BORDA};background:linear-gradient(180deg,#FFFFFF 0%,#F8FAFC 100%);border-radius:0 0 10px 10px;">{badges_row}{unidade_html}{itens_html}{relogio_html}{copy_html}</div>'
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
    itens_dict: dict[str, Any] = (
        dict(itens) if isinstance(itens, dict) else dict(itens or [])
    )
    _STATUS_CFG = {
        "online": ("#059669", "Online"),
        "offline": ("#94A3B8", "Offline"),
        "ausente": ("#D97706", "Ausente"),
        "ocupado": ("#DC2626", "Ocupado"),
    }
    if avatar and Validadores.url(avatar):
        avatar_html = f'<img src="{Validadores.html_escape(avatar)}" alt="Avatar" style="width:42px;height:42px;border-radius:50%;object-fit:cover;flex-shrink:0;border:2px solid #E2E8F0;" />'
    else:
        if avatar:
            mono, mono_size = (
                Validadores.html_escape(avatar[:2]),
                ("18px" if len(avatar) <= 2 else "14px"),
            )
        elif user_name:
            partes = user_name.strip().split()
            mono = Validadores.html_escape(
                (partes[0][0] + partes[-1][0]).upper()
                if len(partes) >= 2
                else user_name[:1].upper()
            )
            mono_size = "16px"
        else:
            mono, mono_size = "U", "16px"
        avatar_html = f'<div style="width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,{Cores.PRIMARIA},{Cores.SECUNDARIA});display:flex;align-items:center;justify-content:center;font-size:{mono_size};color:#FFFFFF;font-weight:800;flex-shrink:0;letter-spacing:0.5px;border:2px solid rgba(255,255,255,0.3);box-shadow:0 2px 8px rgba(1,40,105,0.25);">{mono}</div>'
    status_dot = ""
    status_label_html = ""
    if status and status in _STATUS_CFG:
        cor_s, label_s = _STATUS_CFG[status]
        status_dot = f'<span style="position:absolute;bottom:1px;right:1px;width:11px;height:11px;border-radius:50%;background:{cor_s};border:2px solid #FFFFFF;box-shadow:0 0 0 1px {cor_s}40;"></span>'
        status_label_html = f'<span style="display:inline-flex;align-items:center;gap:4px;font-size:9px;font-weight:700;color:{cor_s};text-transform:uppercase;letter-spacing:0.5px;margin-top:2px;"><span style="width:5px;height:5px;border-radius:50%;background:{cor_s};display:inline-block;"></span>{label_s}</span>'
    user_section = ""
    if user_name or role or email or avatar:
        name_html = (
            f'<p style="margin:0;font-size:13px;font-weight:700;color:{Cores.TEXTO};line-height:1.25;font-family:var(--font-titulo) !important;">{Validadores.html_escape(user_name)}</p>'
            if user_name
            else ""
        )
        role_html = (
            f'<p style="margin:2px 0 0;font-size:10px;color:{Cores.TEXTO_3};line-height:1.3;font-weight:500;">{Validadores.html_escape(role)}</p>'
            if role
            else ""
        )
        email_html = (
            f'<p style="margin:2px 0 0;font-size:10px;color:{Cores.PRIMARIA};line-height:1.3;font-weight:500;opacity:0.85;">{Validadores.html_escape(email)}</p>'
            if email
            else ""
        )
        user_section = f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;"><div style="position:relative;flex-shrink:0;">{avatar_html}{status_dot}</div><div style="min-width:0;flex:1;">{name_html}{role_html}{email_html}{status_label_html}</div></div>'
    itens_html = ""
    if itens_dict:
        sep = (
            f'<div style="height:1px;background:{Cores.BORDA};margin:10px 0 6px;"></div>'
            if user_section
            else ""
        )
        rows = "".join(
            f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;"><span style="font-size:12px;line-height:1;flex-shrink:0;width:18px;text-align:center;opacity:0.7;">{Validadores.html_escape(icone)}</span><span style="font-size:11px;color:{Cores.TEXTO_3};font-weight:500;flex-shrink:0;">{Validadores.html_escape(k)}</span><span style="font-size:11px;color:{Cores.TEXTO};font-weight:700;margin-left:auto;text-align:right;font-variant-numeric:tabular-nums;">{Validadores.html_escape(v)}</span></div>'
            for k, v in itens_dict.items()
        )
        itens_html = f"{sep}<div>{rows}</div>"
    rodape_html = (
        f'<div style="margin-top:8px;padding-top:8px;border-top:1px dashed {Cores.BORDA};font-size:9px;color:{Cores.TEXTO_3};line-height:1.4;letter-spacing:0.2px;">{Validadores.html_escape(rodape)}</div>'
        if rodape
        else ""
    )
    titulo_html = (
        f'<div style="font-size:10px;font-weight:700;color:{Cores.TEXTO_3};text-transform:uppercase;letter-spacing:0.8px;margin:0 0 6px 2px;">{Validadores.html_escape(titulo)}</div>'
        if titulo
        else ""
    )
    if not user_section and not itens_html and not rodape_html:
        return
    markup = f'{titulo_html}<div style="background:linear-gradient(160deg,#FFFFFF 0%,#F8FAFC 100%);border:1px solid {Cores.BORDA};border-radius:12px;padding:14px;margin:8px 0 12px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">{user_section}{itens_html}{rodape_html}</div>'
    with st.sidebar:
        _safe_render_html(markup)


def render_sidebar_spacer(
    altura: Literal["pequeno", "medio", "grande", "xgrande"] | int | str = "medio",
) -> None:
    PRESETS = {"pequeno": "8px", "medio": "16px", "grande": "28px", "xgrande": "48px"}
    altura_css = (
        f"{altura}px"
        if isinstance(altura, int)
        else (
            PRESETS.get(str(altura).lower().strip(), f"{altura}px")
            if not any(
                str(altura).lower().endswith(u)
                for u in ("px", "rem", "em", "%", "vh", "vw")
            )
            else str(altura)
        )
    )
    with st.sidebar:
        _safe_render_html(
            f'<div style="height:{altura_css};width:100%;display:block;" aria-hidden="true"></div>'
        )


# =============================================================================
# COMPONENTES HERO
# =============================================================================
def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    if not titulo:
        raise ValueError("render_hero: 'titulo' não pode ser vazio.")
    _safe_render_html(
        f'<div class="hero-corp"><div class="hero-content"><h1 class="hero-title">{Validadores.html_escape(titulo)}</h1>'
        f"{f'<p class="hero-subtitle">{Validadores.html_escape(subtitulo)}</p>' if subtitulo else ''}"
        f"{f'<span class="hero-badge">{Validadores.html_escape(badge)}</span>' if badge else ''}"
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
        f'<div class="totale-badge-pill"><span>{Validadores.html_escape(icone)}</span> {Validadores.html_escape(badge)}</div>'
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
        f'<div class="totale-hero-1"><div style="position:relative;z-index:2;">{b}<h1 class="th-title-lg">{t}</h1>{s}{m}</div></div>'
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
    card = (
        f'<div class="totale-hero-2-card"><div class="th-card-label">{Validadores.html_escape(label_destaque)}</div><div class="th-card-value">{Validadores.html_escape(valor_destaque)}</div></div>'
        if valor_destaque
        else ""
    )
    _safe_render_html(
        f'<div class="totale-hero-2"><div>{b}{tag}<h1 class="th-title">{t}</h1>{s}</div>{card}</div>'
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
        f'<div class="hero-migracao-badge"><span>{Validadores.html_escape(icone)}</span> {Validadores.html_escape(badge)}</div>'
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
            f'<div class="hero-migracao-stat"><strong>{Validadores.html_escape(st.get("valor", ""))}</strong> {Validadores.html_escape(st.get("label", ""))}</div>'
            for st in stats[:4]
        )
        stats_html = f'<div class="hero-migracao-stats">{items}</div>'
    _safe_render_html(
        f'<div class="hero-migracao"><div style="position:relative;z-index:2;">{b}<h1 class="hero-migracao-title">{t}</h1>{s}{stats_html}</div></div>'
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
        f'<div class="hero-pme-badge"><span>{Validadores.html_escape(icone)}</span> {Validadores.html_escape(badge)}</div>'
        if badge
        else ""
    )
    s = (
        f'<p class="hero-pme-subtitle">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    feat_html = (
        f'<div class="hero-pme-features">{"".join(f'<span class="hero-pme-feature">✓ {Validadores.html_escape(f)}</span>' for f in features[:5])}</div>'
        if features
        else ""
    )
    _safe_render_html(
        f'<div class="hero-pme"><div style="position:relative;z-index:2;">{b}<h1 class="hero-pme-title">{t}</h1>{s}{feat_html}</div></div>'
    )


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
        f'<div class="sidebar-footer-item"><span class="sidebar-footer-label">{Validadores.html_escape(k)}</span><span class="sidebar-footer-value">{Validadores.html_escape(v)}</span></div>'
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


# =============================================================================
# COMPONENTES PRINCIPAIS (API PÚBLICA — RETROCOMPATÍVEL)
# =============================================================================


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

    markup = f'<div class="section-header"><div style="flex:1;"><div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">{icone_html}<h2 class="section-title">{Validadores.html_escape(titulo_final)}</h2>{badge_html}</div>{sub_html}</div></div>'
    _safe_render_html(markup)


def _card_premium(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPIType = "azul",
    icone: str = "",
    delta: str = "",
    delta_tipo: TipoTrendType = "none",
) -> None:
    tema_norm = normalizar_tema_kpi(tema)
    cor_hex = Validadores.resolver_cor_tema(tema_norm)

    label_esc = Validadores.html_escape(label)
    valor_esc = Validadores.html_escape(valor)

    icone_html = ""
    if icone:
        icone_html = (
            f'<div class="kpi-icon-wrapper" style="background-color:{cor_hex}15;color:{cor_hex};">'
            f'<span style="font-size:20px;line-height:1;">{Validadores.html_escape(icone)}</span>'
            f"</div>"
        )

    delta_html = ""
    if delta:
        trend_norm = normalizar_tipo_trend(delta_tipo)
        if trend_norm == "none":
            delta_html = f'<span style="font-weight:700;color:{cor_hex};margin-right:6px;">{Validadores.html_escape(delta)}</span>'
        else:
            trend_icone = ConfigCores.TREND_ICONS.get(trend_norm, "")
            classe = f"trend-{trend_norm}"
            delta_html = f'<span class="trend-pill {classe}" style="margin-right:6px;"><span>{trend_icone}</span>{Validadores.html_escape(delta)}</span>'

    sub_html = ""
    if sub or delta_html:
        sub_html = f'<div class="kpi-sub-premium">{delta_html}{Validadores.html_escape(sub) if sub else ""}</div>'

    markup = f"""
    <div class="card-premium" role="region" aria-label="{label_esc}: {valor_esc}">
        <div class="card-accent-top" style="background-color:{cor_hex};"></div>
        <div class="card-header-flex">
            <div class="kpi-label-premium">{label_esc}</div>
            {icone_html}
        </div>
        <div>
            <div class="kpi-value-premium">{valor_esc}</div>
            {sub_html}
        </div>
    </div>
    """
    _safe_render_html(markup, container)


def render_kpi(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPIType = "azul",
    icone: str = "",
    delta: str = "",
    delta_tipo: TipoTrendType = "none",
) -> None:
    _card_premium(
        container=col,
        label=label,
        valor=valor,
        sub=sub,
        tema=tema,
        icone=icone,
        delta=delta,
        delta_tipo=delta_tipo,
    )


def render_metric_card(
    col: Any,
    label: str,
    valor: str,
    trend: TipoTrendType = "none",
    trend_valor: str = "",
    sub: str = "",
) -> None:
    _card_premium(
        container=col,
        label=label,
        valor=valor,
        sub=sub,
        tema="azul",
        icone="",
        delta=trend_valor,
        delta_tipo=trend,
    )


def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPIType = "azul",
    icone: str = "",
) -> None:
    cor = _resolver_cor_tema(tema)
    markup = f'<div style="background:white;border-radius:6px;padding:12px 16px;border-left:3px solid {cor};margin-bottom:8px;box-shadow:0 1px 4px rgba(0,0,0,0.06);" role="region" aria-label="{Validadores.html_escape(label)}"><div style="font-family:{Cores.TEXTO};font-size:10px;color:{Cores.TEXTO_3};text-transform:uppercase;letter-spacing:1px;font-weight:700;">{Validadores.html_escape(label)}</div><div style="font-family:{Fontes.TITULO};font-size:20px;color:{cor};font-weight:800;line-height:1.2;margin-top:4px;font-variant-numeric:tabular-nums;">{Validadores.html_escape(valor)}</div><div style="font-family:{Cores.TEXTO};font-size:11px;color:{Cores.TEXTO_3};margin-top:2px;">{Validadores.html_escape(sub)}</div></div>'
    _safe_render_html(markup, container)


def render_insight(msg: str, tipo: TipoInsightType = "info", titulo: str = "") -> None:
    if not msg:
        return
    tipo_norm = normalizar_tipo_insight(tipo)
    bg, texto, borda, icone = ConfigCores.INSIGHT.get(
        tipo_norm, ConfigCores.INSIGHT["info"]
    )
    msg_html = Formatadores.markdown_para_html(msg)
    titulo_html = (
        f'<span class="totale-insight-title">{Validadores.html_escape(titulo)}</span>'
        if titulo
        else ""
    )
    markup = f'<div class="totale-insight" style="background:{bg};color:{texto};border-left:4px solid {borda};"><div style="display:flex;align-items:flex-start;gap:10px;"><span style="font-size:18px;line-height:1.2;">{icone}</span><div style="flex:1;">{titulo_html}<div>{msg_html}</div></div></div></div>'
    _safe_render_html(markup)


def render_notification(
    mensagem: str,
    tipo: TipoNotificationType = "info",
    titulo: str = "",
    container: Any = None,
) -> None:
    if not mensagem:
        return
    tipo_norm = normalizar_tipo(mensagem, {"sucesso", "info", "alerta", "erro"}, "info")
    bg, fg, borda, icone = ConfigCores.NOTIFICATION.get(
        tipo_norm, ConfigCores.NOTIFICATION["info"]
    )
    titulo_html = (
        f'<strong style="display:block;margin-bottom:3px;font-size:13px;">{Validadores.html_escape(titulo)}</strong>'
        if titulo
        else ""
    )
    markup = f'<div role="status" style="background:{bg};color:{fg};border:1px solid {borda};border-radius:10px;padding:13px 16px;margin:12px 0;display:flex;align-items:flex-start;gap:10px;box-shadow:0 1px 3px rgba(15,23,42,0.05);"><span style="font-size:18px;line-height:1.2;">{icone}</span><div style="font-size:13px;line-height:1.5;">{titulo_html}{Formatadores.markdown_para_html(mensagem)}</div></div>'
    _safe_render_html(markup, container)


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
    markup = f'<div class="empty-state"><span class="empty-state-icon">{Validadores.html_escape(icone or icone_default)}</span><h3 class="empty-state-title">{Validadores.html_escape(titulo or titulo_default)}</h3>{desc_html}{acao_html}</div>'
    _safe_render_html(markup)


def render_progress_bar(
    valor: float,
    maximo: float = 100.0,
    label: str = "",
    mostrar_valor: bool = True,
    tema: TipoProgressBarType = "azul",
    altura: str = "medio",
    unidade: str = "%",
    animado: bool = True,
) -> None:
    tema_norm = normalizar_tipo_progress(tema)
    altura_px = {"pequeno": "6px", "medio": "8px", "grande": "12px"}.get(
        str(altura).lower(), "8px"
    )
    try:
        v, m = float(valor), float(maximo)
    except Exception:
        v, m = 0.0, 0.0
    porcentagem = min(100.0, max(0.0, (v / m) * 100)) if m > 0 else 0.0
    bg_style = ConfigCores.PROGRESS_BAR.get(tema_norm, Cores.PRIMARIA)
    header_html = ""
    if label or mostrar_valor:
        lbl = (
            f'<span style="font-size:13px;font-weight:600;color:{Cores.TEXTO_2};">{Validadores.html_escape(label)}</span>'
            if label
            else "<span></span>"
        )
        val = (
            f'<span style="font-size:14px;font-weight:800;color:{Cores.TEXTO};font-family:var(--font-titulo);font-variant-numeric:tabular-nums;">{porcentagem:.1f}{unidade}</span>'
            if mostrar_valor
            else ""
        )
        header_html = f'<div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:8px;">{lbl}{val}</div>'
    classe_anim = "totale-pb-fill animado" if animado else "totale-pb-fill"
    markup = f'<div style="margin:14px 0;" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{porcentagem:.1f}">{header_html}<div style="width:100%;background:#E2E8F0;border-radius:999px;overflow:hidden;height:{altura_px};"><div class="{classe_anim}" style="width:{porcentagem:.4f}%;height:100%;background:{bg_style};border-radius:999px;transition:width 0.6s ease-out;"></div></div></div>'
    _safe_render_html(markup)


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
    linha_destaque: dict[str, str] | None = None,
    condicoes_colunas: dict[str, Any] | None = None,
    caption: str = "",
    exportar_excel: bool = False,
    nome_arquivo: str = "relatorio_totale",
) -> None:
    if color_rules is None and condicoes_colunas is not None:
        color_rules = condicoes_colunas
    if not isinstance(df, pd.DataFrame) or df.empty:
        render_empty_state(tipo="dados", descricao="Nenhum dado disponível na tabela.")
        return
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

    ld_coluna = str(linha_destaque.get("coluna", "")) if linha_destaque else ""
    ld_valor = (
        str(linha_destaque.get("valor", "")).strip().upper() if linha_destaque else ""
    )

    th_parts = [
        f'<th style="text-align:{alinhamentos.get(col, "left")};">{Validadores.html_escape(str(col))}</th>'
        for col in df_display.columns
    ]
    th_html = "".join(th_parts)

    tr_parts = []
    for i, (_, row) in enumerate(df_display.iterrows()):
        td_parts = []
        eh_destaque = False
        if ld_coluna and ld_coluna in df_display.columns and ld_valor:
            raw_ld = row[ld_coluna]
            if isinstance(raw_ld, (pd.Series, np.ndarray)):
                raw_ld = raw_ld.iloc[0] if isinstance(raw_ld, pd.Series) else raw_ld[0]
            eh_destaque = ld_valor in str(raw_ld).strip().upper()
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
                        val_str = f'<span class="td-badge" style="background:#FEE2E2;color:#DC2626;">{val_str}</span>'
                    elif classe_cor in ("neutral", "info"):
                        val_str = f'<span class="td-badge" style="background:#DBEAFE;color:#3B82F6;">{val_str}</span>'
            font_style = (
                "font-variant-numeric: tabular-nums; font-family: var(--font-codigo) !important; font-size: 12px;"
                if align == "right"
                else ""
            )
            td_parts.append(
                f'<td style="text-align:{align}; {font_style}">{val_str}</td>'
            )
        classe_linha = (
            ' class="linha-destaque"'
            if eh_destaque
            else (' class="striped"' if striped and i % 2 == 1 else "")
        )
        tr_parts.append(f"<tr{classe_linha}>{''.join(td_parts)}</tr>")

    titulo_html = (
        f'<div style="font-weight:800;font-size:16px;color:#0F172A;margin-bottom:12px;font-family:var(--font-titulo) !important;">{Validadores.html_escape(titulo)}</div>'
        if titulo
        else ""
    )
    caption_html = (
        f'<div style="font-size:11px;color:#94A3B8;margin-top:8px;font-weight:500;">{Validadores.html_escape(caption)}</div>'
        if caption
        else ""
    )
    data_html = (
        f'<div style="font-size:11px;color:#94A3B8;margin-top:8px;text-align:right;font-weight:500;">Atualizado em: {datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")}</div>'
        if mostrar_data
        else ""
    )
    height_style = f"max-height:{height}px;" if height else ""

    markup = f'<div style="margin: 24px 0;">{titulo_html}<div class="table-premium-wrapper"><div class="table-premium-scroll" style="{height_style}"><table class="totale-table-pro"><thead><tr>{th_html}</tr></thead><tbody>{"".join(tr_parts)}</tbody></table></div></div>{caption_html}{data_html}</div>'
    _safe_render_html(markup)

    if exportar_excel and not df_display.empty:
        buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_display.to_excel(writer, index=False, sheet_name="Dados")
            c1, c2 = st.columns([4, 1])
            with c2:
                st.download_button(
                    label="📥 Exportar Excel",
                    data=buffer.getvalue(),
                    file_name=f"{nome_arquivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        except Exception:
            pass


# =============================================================================
# COMPONENTES VISUAIS ADICIONAIS
# =============================================================================
def render_card(
    titulo: str,
    corpo: str = "",
    icone: str = "",
    tipo: TipoBadgeType = "default",
    container: Any = None,
) -> None:
    if not titulo:
        return
    tipo_norm = normalizar_tipo_badge(tipo)
    bg, fg, borda = ConfigCores.BADGE.get(tipo_norm, ConfigCores.BADGE["default"])
    icone_html = (
        f'<span style="font-size:22px;line-height:1;">{Validadores.html_escape(icone)}</span>'
        if icone
        else ""
    )
    markup = f'<div class="card-premium" role="region" aria-label="{Validadores.html_escape(titulo)}"><div style="display:flex;align-items:flex-start;gap:12px;">{icone_html}<div style="flex:1;"><div style="font-family:var(--font-titulo) !important;font-size:15px;font-weight:800;color:var(--cor-texto);margin-bottom:4px;">{Validadores.html_escape(titulo)}</div><div style="font-size:13px;color:var(--cor-texto-3);line-height:1.55;">{Formatadores.markdown_para_html(corpo)}</div></div></div><div class="card-accent-top" style="background:{borda};"></div></div>'
    _safe_render_html(markup, container)


def render_spacer(altura: int | str = 16) -> None:
    css = f"{altura}px" if isinstance(altura, int) else str(altura)
    _safe_render_html(
        f'<div style="height:{css};width:100%;display:block;" aria-hidden="true"></div>'
    )


def render_badge(
    texto: str, tipo: TipoBadgeType = "default", icone: str = "", container: Any = None
) -> None:
    if not texto:
        return
    tipo_norm = normalizar_tipo_badge(tipo)
    bg, fg, borda = ConfigCores.BADGE.get(tipo_norm, ConfigCores.BADGE["default"])
    icone_html = (
        f'<span style="line-height:1;">{Validadores.html_escape(icone)}</span>'
        if icone
        else ""
    )
    markup = f'<span class="totale-badge-pill" style="background:{bg};color:{fg};border-color:{borda};">{icone_html}{Validadores.html_escape(texto)}</span>'
    _safe_render_html(markup, container)


def render_skeleton(
    linhas: int = 3, altura_linha: int = 16, largura_ultima: str = "60%"
) -> None:
    linhas = max(1, int(linhas))
    rows = []
    for i in range(linhas):
        largura = largura_ultima if i == linhas - 1 else "100%"
        rows.append(
            f'<div class="totale-skeleton" style="height:{altura_linha}px;width:{largura};margin-bottom:10px;"></div>'
        )
    _safe_render_html(f'<div style="margin:12px 0;">{"".join(rows)}</div>')


# =============================================================================
# EXPORTAÇÃO
# =============================================================================
__all__ = [
    "TemaKPI",
    "TipoInsight",
    "TipoStatus",
    "TipoEmptyState",
    "TipoBadge",
    "TipoProgressBar",
    "TipoTrend",
    "TipoNotification",
    "TipoTimelineItem",
    "TipoHero",
    "TemaKPIType",
    "TipoInsightType",
    "TipoStatusType",
    "TipoEmptyStateType",
    "TipoBadgeType",
    "TipoProgressBarType",
    "TipoTrendType",
    "TipoNotificationType",
    "TipoTimelineItemType",
    "TipoHeroType",
    "Fontes",
    "Cores",
    "ConfigCores",
    "Validadores",
    "Formatadores",
    "PlotlyConfig",
    "FontInjector",
    "CSSInjector",
    "aplicar_estilo",
    "aplicar_estilo_corp",
    "aplicar_sidebar_corp",
    "render_sidebar_brand",
    "render_sidebar_section",
    "render_sidebar_divider",
    "render_sidebar_footer_info",
    "render_sidebar_info",
    "render_sidebar_spacer",
    "render_sidebar_status",
    "render_hero",
    "render_hero_totale_1",
    "render_hero_totale_2",
    "render_hero_migracao",
    "render_hero_pme",
    "render_section_header",
    "render_kpi",
    "render_metric_card",
    "render_kpi_sm",
    "render_card",
    "render_insight",
    "render_notification",
    "render_empty_state",
    "render_progress_bar",
    "render_table_html",
    "render_spacer",
    "render_badge",
    "render_skeleton",
    "formatar_numero_br",
    "normalizar_tipo",
]
