"""
components/componentes.py
=========================
Design System Streamlit — TOTALE

Versão: 4.9.2 (Enterprise Sidebar Layout & Overflow Fix)
Autor: TOTALE Tecnologia

Evoluções desta versão:
• Sidebar ampliada (310px) e reprojetada: sem corte de textos, navegação
  compacta, item ativo destacado em laranja e scrollbar discreta.
• Estilização nativa de `st.page_link` / `stSidebarNav` (ícone + label).
• Card de marca premium (gradiente azul + acento laranja) com truncamento
  seguro para nomes longos.
• Conteúdo principal sem overflow horizontal: `block-container` fluido com
  padding responsivo (`clamp`) e `max-width: 1440px`.
• Hero `totale_2` responsivo (flex-wrap) — não estoura mais em telas menores.
• Correção de imports faltantes: `Protocol`, `runtime_checkable`, `Union`.
• `_safe_render_html` com checagem defensiva de container.
"""

from __future__ import annotations

import functools
import html as html_lib
import inspect
import io
import logging
import re
import unicodedata
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Literal,
    Protocol,
    TypeAlias,
    TypeVar,
    Union,
    cast,
    runtime_checkable,
)
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TypeVar para preservar assinaturas no decorator de compatibilidade
# ---------------------------------------------------------------------------
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# PROTOCOLOS E TIPOS ESTRITOS
# =============================================================================
@runtime_checkable
class StreamlitContainer(Protocol):
    def markdown(
        self, body: str, unsafe_allow_html: bool = False, **kwargs: Any
    ) -> Any: ...


TemaKPIType: TypeAlias = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"
]
TipoInsightType: TypeAlias = Literal["ok", "info", "alerta", "critico", "acao"]
TipoStatusType: TypeAlias = Literal["ok", "info", "alerta", "critico", "neutro"]
TipoEmptyStateType: TypeAlias = Literal[
    "dados", "filtro", "erro", "carregando", "padrao"
]
TipoBadgeType: TypeAlias = Literal[
    "default", "sucesso", "alerta", "erro", "info", "roxo", "laranja"
]
TipoProgressBarType: TypeAlias = Literal[
    "azul", "laranja", "verde", "vermelho", "roxo", "gradiente"
]
TipoTrendType: TypeAlias = Literal["up", "down", "neutral", "none"]
TipoNotificationType: TypeAlias = Literal["sucesso", "info", "alerta", "erro"]
TipoTimelineItemType: TypeAlias = Literal[
    "concluido", "em_andamento", "pendente", "cancelado"
]
TipoHeroType: TypeAlias = Literal[
    "padrao", "migracao", "pme", "totale_1", "totale_2", "novos_domicilios"
]

BaseFormatter: TypeAlias = Union[str, Callable[[object], str]]
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
    GRADIENTE = "gradiente"


class TipoInsight(str, Enum):
    OK = "ok"
    INFO = "info"
    ALERTA = "alerta"
    CRITICO = "critico"
    ACAO = "acao"


class TipoBadge(str, Enum):
    DEFAULT = "default"
    SUCESSO = "sucesso"
    ALERTA = "alerta"
    ERRO = "erro"
    INFO = "info"
    ROXO = "roxo"
    LARANJA = "laranja"


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
    PRIMARIA_DARK = "#011E52"
    SECUNDARIA = "#F37C04"
    SECUNDARIA_DARK = "#D96500"
    SECUNDARIA_LIGHT = "#FF9D45"
    SUCESSO = "#059669"
    ALERTA = "#DC2626"
    ATENCAO = "#F59E0B"
    NEUTRO = "#64748B"
    TEXTO = "#1F2937"
    TEXTO_2 = "#374151"
    TEXTO_3 = "#6B7280"
    BORDA = "#E2E8F0"
    FUNDO = "#F8FAFC"
    LARANJA_SUAVE = "#FFF4E5"
    AZUL_SUAVE = "#E6EEF8"
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
    GRADIENTES: dict[str, tuple[str, str]] = {
        "azul": ("#012869", "#0A48AA"),
        "laranja": ("#F37C04", "#FF9D45"),
        "verde": ("#065F46", "#047857"),
        "vermelho": ("#991B1B", "#DC2626"),
        "roxo": ("#5B21B6", "#7C3AED"),
        "cinza": ("#475569", "#64748B"),
        "gradiente": ("#012869", "#F37C04"),
    }
    BADGE: dict[str, tuple[str, str, str]] = {
        "default": ("#F3F4F6", "#374151", "#D1D5DB"),
        "sucesso": ("#D1FAE5", "#065F46", "#059669"),
        "alerta": ("#FEF3C7", "#92400E", "#F59E0B"),
        "erro": ("#FEE2E2", "#991B1B", "#DC2626"),
        "info": ("#DBEAFE", "#1E40AF", "#3B82F6"),
        "roxo": ("#EDE9FE", "#5B21B6", "#8B5CF6"),
        "laranja": ("#FFEDD5", "#9A3412", "#F97316"),
    }
    PROGRESS_BAR: dict[str, str] = {
        "azul": Cores.PRIMARIA,
        "laranja": Cores.SECUNDARIA,
        "verde": Cores.SUCESSO,
        "vermelho": Cores.ALERTA,
        "roxo": Cores.ROXO,
        "gradiente": f"linear-gradient(90deg, {Cores.PRIMARIA}, {Cores.SECUNDARIA})",
    }
    TREND_ICONS: dict[str, str] = {"up": "↑", "down": "↓", "neutral": "→", "none": ""}
    NOTIFICATION: dict[str, tuple[str, str, str, str]] = {
        "sucesso": ("#D1FAE5", "#065F46", "#059669", "✅"),
        "info": ("#DBEAFE", "#1E40AF", "#3B82F6", "ℹ️"),
        "alerta": ("#FEF3C7", "#92400E", "#F59E0B", "⚠️"),
        "erro": ("#FEE2E2", "#991B1B", "#DC2626", "❌"),
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


# =============================================================================
# HELPERS
# =============================================================================
def formatar_numero_br(valor: Any, casas: int = 0) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if casas <= 0:
        return f"{int(round(v)):,}".replace(",", ".")
    return f"{v:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def normalizar_tipo(valor: Any, permitido: set[str], padrao: str) -> str:
    s = str(valor.value if isinstance(valor, Enum) else (valor or "")).strip().lower()
    return s if s in permitido else padrao


def normalizar_tema_kpi(tema: Any) -> TemaKPIType:
    return cast(
        TemaKPIType,
        normalizar_tipo(
            tema,
            {"azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"},
            "azul",
        ),
    )


def normalizar_tipo_badge(tipo: Any) -> TipoBadgeType:
    return cast(
        TipoBadgeType,
        normalizar_tipo(
            tipo,
            {"default", "sucesso", "alerta", "erro", "info", "roxo", "laranja"},
            "default",
        ),
    )


def normalizar_tipo_progress(tema: Any) -> TipoProgressBarType:
    return cast(
        TipoProgressBarType,
        normalizar_tipo(
            tema, {"azul", "laranja", "verde", "vermelho", "roxo", "gradiente"}, "azul"
        ),
    )


def normalizar_tipo_trend(trend: Any) -> TipoTrendType:
    return cast(
        TipoTrendType, normalizar_tipo(trend, {"up", "down", "neutral", "none"}, "none")
    )


def normalizar_tipo_insight(tipo: Any) -> TipoInsightType:
    return cast(
        TipoInsightType,
        normalizar_tipo(tipo, {"ok", "info", "alerta", "critico", "acao"}, "info"),
    )


def normalizar_tipo_status(tipo: Any) -> TipoStatusType:
    return cast(
        TipoStatusType,
        normalizar_tipo(tipo, {"ok", "info", "alerta", "critico", "neutro"}, "ok"),
    )


def normalizar_texto_badge(txt: str) -> str:
    txt_clean = re.sub(r"<[^>]+>", "", str(txt))
    normalized = unicodedata.normalize("NFKD", txt_clean)
    return (
        "".join(c for c in normalized if not unicodedata.combining(c)).strip().upper()
    )


def formatar_datetime_exibicao(valor: Any, com_segundos: bool = False) -> str:
    if valor is None:
        return ""
    try:
        ts = pd.Timestamp(valor)
        if pd.isna(ts):
            return str(valor)
        return ts.strftime("%d/%m/%Y %H:%M:%S" if com_segundos else "%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(valor)


class Validadores:
    @staticmethod
    def url(url: str | None) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def html_escape(texto: Any) -> str:
        return html_lib.escape(str(texto)) if texto is not None else ""


class Formatadores:
    @staticmethod
    def markdown_para_html(texto: str) -> str:
        if not texto:
            return texto
        t = html_lib.escape(texto)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        return t


def _safe_render_html(
    html_str: str, container: StreamlitContainer | None = None
) -> None:
    if not html_str:
        return
    alvo: Any = (
        container if (container is not None and hasattr(container, "markdown")) else st
    )
    clean = html_str.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    clean = re.sub(r">\s+<", "><", clean)
    clean = re.sub(r" {2,}", " ", clean)
    alvo.markdown(clean.strip(), unsafe_allow_html=True)


def _icone_tile(icone: str, variante: str = "section") -> str:
    t = str(icone or "").strip()
    if not t:
        return ""
    v = variante if variante in {"section", "brand"} else "section"
    return (
        f'<span class="totale-icon-tile totale-icon-tile--{v}" aria-hidden="true">'
        f'<span class="totale-icon-glyph">{Validadores.html_escape(t)}</span></span>'
    )


# =============================================================================
# BLINDAGEM DE COMPATIBILIDADE (kwargs legados)
# =============================================================================
def tolerante_kwargs(func: F) -> F:
    """
    Decorador de compatibilidade para componentes públicos.

    Descarta (com log) argumentos nomeados que não fazem parte da assinatura,
    evitando TypeError em chamadas legadas. Preserva a assinatura original
    para ferramentas de tipo (Pylance / Pyright).
    """
    sig = inspect.signature(func)
    aceita_var_kw = any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not aceita_var_kw:
            validos = set(sig.parameters)
            extras = [k for k in kwargs if k not in validos]
            if extras:
                logger.warning(
                    "%s: argumento(s) ignorado(s) por incompatibilidade -> %s",
                    func.__name__,
                    extras,
                )
                kwargs = {k: v for k, v in kwargs.items() if k in validos}
        return func(*args, **kwargs)

    return cast(F, wrapper)


# =============================================================================
# CSS — VARIÁVEIS
# =============================================================================
_CSS_VARS_ROOT = (
    ":root {"
    f"--font-titulo: {Fontes.TITULO}; "
    f"--font-texto: {Fontes.TEXTO}; "
    f"--font-codigo: {Fontes.CODIGO}; "
    f"--cor-primaria: {Cores.PRIMARIA}; "
    f"--cor-primaria-dark: {Cores.PRIMARIA_DARK}; "
    f"--cor-primaria-light: {Cores.PRIMARIA_LIGHT}; "
    f"--cor-secundaria: {Cores.SECUNDARIA}; "
    f"--cor-secundaria-light: {Cores.SECUNDARIA_LIGHT}; "
    f"--cor-borda: {Cores.BORDA}; "
    "--cor-card-bg: #FFFFFF; "
    "--sidebar-w: 310px; "
    "--radius-md: 10px; "
    "--shadow-md: 0 4px 12px rgba(1,40,105,0.07);"
    "}"
)


# =============================================================================
# CSS — GLOBAL / LAYOUT (anti-overflow + responsivo)
# =============================================================================
_CSS_GLOBAL = """
html, body, .stApp {
    overflow-x: hidden !important;
    font-family: var(--font-texto) !important;
}

.main { overflow-x: hidden !important; }

.main .block-container {
    width: 100% !important;
    max-width: 1440px !important;
    padding-top: 2rem !important;
    padding-right: clamp(1rem, 3vw, 3rem) !important;
    padding-bottom: 3rem !important;
    padding-left: clamp(1rem, 3vw, 3rem) !important;
}

.main .block-container > div,
.main .block-container [data-testid="stVerticalBlock"] {
    max-width: 100% !important;
}

.main .block-container h1,
.main .block-container h2,
.main .block-container h3 { overflow-wrap: anywhere; }

.card-premium,
.sidebar-brand-card,
.sidebar-status-card {
    max-width: 100%;
    box-sizing: border-box;
}

@media (max-width: 900px) {
    [data-testid="stSidebar"] {
        min-width: 280px !important;
        max-width: 280px !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-left: 12px !important;
        padding-right: 12px !important;
    }
}

@media (max-width: 640px) {
    .main .block-container { padding: 1rem !important; }
}
"""


# =============================================================================
# CSS — CARDS / KPIS
# =============================================================================
_CSS_CARDS = """
.card-premium {
    position: relative;
    overflow: hidden;
    padding: 20px;
    border: 1px solid var(--cor-borda);
    border-radius: 12px;
    background: var(--cor-card-bg);
    box-shadow: var(--shadow-md);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card-premium:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 22px rgba(1,40,105,0.11);
}
.card-accent-top { position: absolute; top: 0; left: 0; right: 0; height: 3px; }
.kpi-label-premium {
    font-size: 12px; font-weight: 600; color: #6B7280; text-transform: uppercase;
    letter-spacing: 0.4px;
}
.kpi-value-premium {
    font-size: 32px; font-weight: 800; color: #1F2937; margin-top: 4px;
    font-family: var(--font-titulo);
}
.trend-pill { padding: 4px 8px; border-radius: 20px; font-size: 11px; font-weight: 700; }
"""


# =============================================================================
# CSS — SIDEBAR (Azul & Laranja Enterprise)
# =============================================================================
_CSS_SIDEBAR = """
[data-testid="stSidebar"] {
    min-width: var(--sidebar-w) !important;
    max-width: var(--sidebar-w) !important;
    border-right: 1px solid #D8E2EF !important;
    background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 55%, #EEF4FB 100%) !important;
    box-shadow: 5px 0 24px rgba(1, 40, 105, 0.08) !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding: 18px 16px 24px 16px !important;
}

[data-testid="stSidebar"] .block-container {
    padding: 0 !important;
    max-width: none !important;
}

[data-testid="stSidebar"] button[kind="headerNoPadding"] {
    color: #012869 !important;
    background: transparent !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] button[kind="headerNoPadding"]:hover {
    color: #F37C04 !important;
    background: #FFF4E5 !important;
}

/* ---------- Card da marca ---------- */
.sidebar-brand-card {
    position: relative;
    overflow: hidden;
    margin-bottom: 22px;
    padding: 17px 16px;
    border: 1px solid rgba(243, 124, 4, 0.38);
    border-radius: 16px;
    color: #FFFFFF;
    background:
        radial-gradient(circle at 100% 0%, rgba(243,124,4,0.38), transparent 35%),
        linear-gradient(135deg, #011E52 0%, #012869 55%, #0A48AA 100%);
    box-shadow: 0 8px 24px rgba(1,40,105,0.24), inset 0 1px 0 rgba(255,255,255,0.12);
}
.sidebar-brand-card::before {
    content: "";
    position: absolute; left: 0; bottom: 0;
    width: 100%; height: 3px;
    background: linear-gradient(90deg, #F37C04, #FF9D45, #F37C04);
}
.sidebar-brand-card::after {
    content: "";
    position: absolute; right: -35px; top: -35px;
    width: 100px; height: 100px;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 50%;
}
.sidebar-brand-card .totale-icon-tile {
    width: 42px !important; height: 42px !important;
    border: 1px solid rgba(255,255,255,0.22);
    background: linear-gradient(135deg, #F37C04, #FF9D45) !important;
    box-shadow: 0 4px 12px rgba(243,124,4,0.35);
}

/* ---------- Títulos de seção ---------- */
.sidebar-section-pill {
    display: flex;
    align-items: center;
    min-height: 28px;
    margin: 20px 0 7px;
    padding: 5px 10px;
    border-left: 3px solid #F37C04;
    border-radius: 0 8px 8px 0;
    background: linear-gradient(90deg, rgba(1,40,105,0.09), rgba(243,124,4,0.025));
}
.sidebar-section-pill > div {
    display: flex; align-items: center; gap: 6px;
    color: #012869 !important;
    font-size: 10px !important;
    font-weight: 900 !important;
    letter-spacing: 0.65px;
    text-transform: uppercase;
}

/* ---------- Navegação (page_link / botões) ---------- */
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"],
[data-testid="stSidebar"] .stButton > button {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    min-height: 34px !important;
    margin: 2px 0 !important;
    padding: 7px 10px !important;
    border: 1px solid transparent !important;
    border-radius: 8px !important;
    color: #123E78 !important;
    background: transparent !important;
    font-size: 12px !important;
    font-weight: 650 !important;
    text-align: left !important;
    transition: background .18s ease, border .18s ease, color .18s ease, transform .18s ease;
}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] span {
    font-size: 12px !important;
    font-weight: 650 !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover,
[data-testid="stSidebar"] .stButton > button:hover {
    color: #012869 !important;
    border-color: rgba(243,124,4,0.55) !important;
    background: linear-gradient(90deg, #FFF4E5, #FFFFFF) !important;
    transform: translateX(2px);
}

.sidebar-item-active,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"],
[data-testid="stSidebar"] .stButton > button[aria-pressed="true"] {
    color: #012869 !important;
    border-color: #F37C04 !important;
    background: linear-gradient(90deg, #FFF4E5 0%, #FFFFFF 100%) !important;
    box-shadow: 0 3px 9px rgba(243,124,4,0.14);
}

/* Expander nativo "View more / View less" */
[data-testid="stSidebarNav"] ul { padding-top: 2px !important; }
[data-testid="stSidebarNav"] + div button {
    color: #64748B !important;
    font-size: 11px !important;
    font-weight: 700 !important;
}

/* ---------- Card de status ---------- */
.sidebar-status-card {
    margin: 12px 0;
    padding: 12px 14px;
    border: 1px solid #DCE5EF;
    border-left: 4px solid #059669;
    border-radius: 11px;
    background: #FFFFFF;
    box-shadow: 0 3px 9px rgba(1,40,105,0.045);
    transition: box-shadow .2s ease, transform .2s ease;
}
.sidebar-status-card:hover {
    box-shadow: 0 6px 16px rgba(1,40,105,0.11);
    transform: translateY(-1px);
}

/* ---------- Rodapé ---------- */
.sidebar-footer {
    margin-top: 24px;
    padding: 15px 4px 4px;
    border-top: 1px dashed #CBD5E1;
}

/* ---------- Scrollbar ---------- */
[data-testid="stSidebar"] ::-webkit-scrollbar { width: 7px; }
[data-testid="stSidebar"] ::-webkit-scrollbar-track { background: transparent; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb { border-radius: 10px; background: #CBD5E1; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover { background: #F37C04; }
"""


# =============================================================================
# CSS — TILES DE ÍCONE
# =============================================================================
_CSS_TILES = """
.totale-icon-tile {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border-radius: 10px;
    color: #FFFFFF;
    background: linear-gradient(135deg, #012869, #F37C04);
    box-shadow: 0 2px 6px rgba(243,124,4,0.25);
}
.totale-icon-tile--brand { width: 42px; height: 42px; }
.totale-icon-tile--section { width: 38px; height: 38px; }
.totale-icon-glyph {
    font-size: 20px;
    font-family: 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif;
}
"""


class CSSInjector:
    @staticmethod
    def injetar() -> None:
        style = (
            "<style>"
            f"{_CSS_VARS_ROOT}"
            f"{_CSS_GLOBAL}"
            f"{_CSS_CARDS}"
            f"{_CSS_SIDEBAR}"
            f"{_CSS_TILES}"
            "</style>"
        )
        _safe_render_html(style)


class FontInjector:
    @staticmethod
    def injetar() -> None:
        links = "\n".join(
            f'<link rel="stylesheet" href="{u}">' for u in GoogleFonts.URLS
        )
        _safe_render_html(links)


def aplicar_estilo() -> None:
    FontInjector.injetar()
    CSSInjector.injetar()


def aplicar_estilo_corp() -> None:
    """Alias de compatibilidade corporativa."""
    aplicar_estilo()


def aplicar_sidebar_corp() -> None:
    """Alias de compatibilidade corporativa."""
    aplicar_estilo()


# =============================================================================
# COMPONENTES SIDEBAR
# =============================================================================
def render_sidebar_brand(
    nome: str = "TOTALE",
    subtitulo: str = "Analytics",
    versao: str = "",
    icone: str = "⚡",
    titulo: str = "",
    **kwargs: Any,
) -> None:
    nome_f = titulo or nome
    sub_f = kwargs.get("segmento", subtitulo)
    ic_html = _icone_tile(icone, "brand")

    versao_html = (
        '<div style="position:relative;z-index:1;margin-top:10px;">'
        '<span style="background:rgba(243,124,4,0.18);color:#FFB870;font-size:9px;'
        "font-weight:800;padding:3px 10px;border-radius:12px;letter-spacing:0.6px;"
        'border:1px solid rgba(243,124,4,0.45);">'
        f"{Validadores.html_escape(versao)}</span></div>"
        if versao
        else ""
    )

    markup = f"""
    <div class="sidebar-brand-card">
        <div style="position:relative;z-index:1;display:flex;align-items:center;gap:12px;min-width:0;">
            {ic_html}
            <div style="min-width:0;flex:1;">
                <h2 style="margin:0;overflow:hidden;color:#FFFFFF;font-family:var(--font-titulo);
                           font-size:17px;font-weight:900;letter-spacing:0.2px;line-height:1.2;
                           text-overflow:ellipsis;white-space:nowrap;">
                    {Validadores.html_escape(nome_f)}
                </h2>
                <div style="margin-top:3px;overflow:hidden;color:#DBEAFE;font-size:10px;
                            font-weight:500;text-overflow:ellipsis;white-space:nowrap;">
                    {Validadores.html_escape(sub_f)}
                </div>
            </div>
        </div>
        {versao_html}
    </div>
    """
    with st.sidebar:
        _safe_render_html(markup)


@tolerante_kwargs
def render_sidebar_section(titulo: str, icone: str = "") -> None:
    icone_html = (
        f'<span style="font-size:13px;">{Validadores.html_escape(icone)}</span>'
        if icone
        else ""
    )
    markup = f"""
    <div class="sidebar-section-pill">
        <div>{icone_html}<span>{Validadores.html_escape(titulo)}</span></div>
    </div>
    """
    with st.sidebar:
        _safe_render_html(markup)


@tolerante_kwargs
def render_sidebar_divider(estilo: str = "gradiente", label: str = "") -> None:
    line = (
        "height:1px;background:linear-gradient(90deg,transparent,#012869,#F37C04,transparent);"
        if estilo == "gradiente"
        else "border-top:1px solid #CBD5E1;"
    )
    if label:
        markup = (
            "<div style='display:flex;align-items:center;gap:10px;margin:18px 0;'>"
            f"<div style='flex:1;{line}'></div>"
            "<span style='font-size:9px;font-weight:800;color:#64748B;letter-spacing:0.6px;'>"
            f"{Validadores.html_escape(label)}</span>"
            f"<div style='flex:1;{line}'></div></div>"
        )
    else:
        markup = f"<div style='margin:18px 0;{line}'></div>"
    with st.sidebar:
        _safe_render_html(markup)


@tolerante_kwargs
def render_sidebar_spacer(altura: int = 16) -> None:
    with st.sidebar:
        _safe_render_html(f"<div style='height:{altura}px;'></div>")


@tolerante_kwargs
def render_sidebar_info(
    user_name: str = "", role: str = "", status: str = "online"
) -> None:
    cor = "#059669" if status == "online" else "#94A3B8"
    inicial = Validadores.html_escape(user_name[0].upper() if user_name else "U")
    markup = f"""
    <div style="margin:12px 0;padding:12px 14px;border:1px solid #DCE5EF;border-radius:12px;
                background:#FFFFFF;box-shadow:0 3px 9px rgba(1,40,105,0.04);">
        <div style="display:flex;align-items:center;gap:12px;min-width:0;">
            <div style="width:38px;height:38px;flex-shrink:0;border-radius:50%;
                        background:linear-gradient(135deg,var(--cor-primaria),var(--cor-secundaria));
                        color:#FFFFFF;display:flex;align-items:center;justify-content:center;
                        font-weight:900;font-size:15px;box-shadow:0 3px 8px rgba(1,40,105,0.22);">
                {inicial}
            </div>
            <div style="min-width:0;flex:1;">
                <div style="font-size:13px;font-weight:800;color:var(--cor-primaria);
                            overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                    {Validadores.html_escape(user_name)}
                </div>
                <div style="font-size:10px;color:#64748B;font-weight:600;text-transform:uppercase;
                            letter-spacing:0.4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                    {Validadores.html_escape(role)}
                </div>
                <div style="display:flex;align-items:center;gap:5px;margin-top:3px;">
                    <span style="width:7px;height:7px;border-radius:50%;background:{cor};
                                 box-shadow:0 0 0 2px {cor}30;"></span>
                    <span style="font-size:9px;color:{cor};font-weight:800;text-transform:uppercase;
                                 letter-spacing:0.5px;">{Validadores.html_escape(status)}</span>
                </div>
            </div>
        </div>
    </div>
    """
    with st.sidebar:
        _safe_render_html(markup)


def render_sidebar_status(
    status: str = "Ativo",
    label: str = "SISTEMA",
    tipo: str = "ok",
    ultima_atualizacao: Any = None,
    icone: str = "",
    **kwargs: Any,
) -> None:
    """
    Card de status na sidebar.

    Kwargs legados aceitos:
      • atualizado_em / updated_at / data_atualizacao -> alias de ultima_atualizacao
      • titulo -> alias de label
      • texto / valor -> alias de status
      • com_segundos (bool) -> formata o timestamp com segundos
    """
    ultima_atualizacao = (
        ultima_atualizacao
        or kwargs.pop("atualizado_em", None)
        or kwargs.pop("updated_at", None)
        or kwargs.pop("data_atualizacao", None)
    )
    label = kwargs.pop("titulo", None) or label
    status = kwargs.pop("texto", None) or kwargs.pop("valor", None) or status
    com_segundos = bool(kwargs.pop("com_segundos", False))

    if kwargs:
        logger.debug("render_sidebar_status: kwargs ignorados -> %s", list(kwargs))

    cor = {
        "ok": "#059669",
        "info": "#3B82F6",
        "alerta": "#D97706",
        "critico": "#DC2626",
    }.get(normalizar_tipo(tipo, {"ok", "info", "alerta", "critico"}, "ok"), "#059669")

    ts_txt = formatar_datetime_exibicao(ultima_atualizacao, com_segundos=com_segundos)
    ts_html = (
        '<div style="margin-top:9px;padding-top:7px;border-top:1px dashed #E2E8F0;'
        'font-size:9px;color:#64748B;font-weight:600;display:flex;align-items:center;gap:4px;">'
        f"<span>🕒</span> Atualizado: {Validadores.html_escape(ts_txt)}</div>"
        if ts_txt
        else ""
    )

    ic_html = (
        f'<span style="font-size:13px;">{Validadores.html_escape(icone)}</span>'
        if icone
        else ""
    )

    markup = f"""
    <div class="sidebar-status-card" style="border-left-color:{cor};">
        <div style="font-size:9px;font-weight:900;color:#64748B;letter-spacing:0.8px;text-transform:uppercase;">
            {Validadores.html_escape(label)}
        </div>
        <div style="display:flex;align-items:center;gap:7px;margin-top:5px;min-width:0;">
            {ic_html}
            <span style="width:8px;height:8px;flex-shrink:0;border-radius:50%;background:{cor};
                         box-shadow:0 0 0 3px {cor}20;"></span>
            <span style="font-size:12px;font-weight:800;color:var(--cor-primaria);
                         overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                {Validadores.html_escape(status)}
            </span>
        </div>
        {ts_html}
    </div>
    """
    with st.sidebar:
        _safe_render_html(markup)


@tolerante_kwargs
def render_sidebar_footer_info(
    empresa: str = "TOTALE", versao: str = "", ambiente: str = ""
) -> None:
    ano = datetime.now().year
    ambiente_html = (
        '<span style="font-size:9px;background:#FFF4E5;border:1px solid rgba(243,124,4,0.30);'
        'padding:2px 8px;border-radius:6px;color:#D96500;font-weight:800;">'
        f"{Validadores.html_escape(ambiente)}</span>"
        if ambiente
        else ""
    )
    versao_html = (
        '<span style="font-size:9px;background:#E6EEF8;border:1px solid rgba(1,40,105,0.20);'
        'padding:2px 8px;border-radius:6px;color:#012869;font-weight:800;">'
        f"{Validadores.html_escape(versao)}</span>"
        if versao
        else ""
    )
    markup = f"""
    <div class="sidebar-footer">
        <div style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;">
            {ambiente_html}{versao_html}
        </div>
        <div style="font-size:10px;color:#64748B;font-weight:500;line-height:1.5;">
            © {ano} <b style="color:var(--cor-primaria);">{Validadores.html_escape(empresa)}</b><br>
            Todos os direitos reservados.
        </div>
    </div>
    """
    with st.sidebar:
        _safe_render_html(markup)


# =============================================================================
# COMPONENTES HERO
# =============================================================================
@tolerante_kwargs
def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    badge_html = (
        '<div style="background:rgba(255,255,255,0.15);display:inline-block;padding:4px 12px;'
        'border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase;margin-bottom:12px;">'
        f"{Validadores.html_escape(badge)}</div>"
        if badge
        else ""
    )
    markup = f"""
    <div style="width:100%;box-sizing:border-box;overflow:hidden;padding:30px;margin-bottom:24px;
                color:#FFFFFF;border-radius:14px;
                background:linear-gradient(135deg,#012869,#0A48AA);
                box-shadow:0 8px 24px rgba(1,40,105,0.18);">
        {badge_html}
        <h1 style="margin:0;font-size:32px;font-weight:800;overflow-wrap:anywhere;">
            {Validadores.html_escape(titulo)}
        </h1>
        <p style="margin-top:8px;font-size:16px;opacity:0.85;overflow-wrap:anywhere;">
            {Validadores.html_escape(subtitulo)}
        </p>
    </div>
    """
    _safe_render_html(markup)


@tolerante_kwargs
def render_hero_totale_1(
    titulo: str, subtitulo: str = "", badge: str = "TOTALE", icone: str = "⚡"
) -> None:
    markup = f"""
    <div style="width:100%;box-sizing:border-box;overflow:hidden;padding:35px;margin-bottom:24px;
                color:#FFFFFF;border-radius:16px;border:1px solid rgba(255,255,255,0.10);
                background:linear-gradient(135deg,#011E52,#0A48AA);
                box-shadow:0 8px 26px rgba(1,40,105,0.20);">
        <div style="display:flex;align-items:center;gap:8px;width:fit-content;padding:5px 15px;
                    border-radius:30px;font-size:11px;font-weight:700;
                    background:rgba(243,124,4,0.18);border:1px solid rgba(243,124,4,0.40);">
            <span>{Validadores.html_escape(icone)}</span>{Validadores.html_escape(badge)}
        </div>
        <h1 style="margin:15px 0 10px;font-size:36px;font-weight:900;overflow-wrap:anywhere;">
            {Validadores.html_escape(titulo)}
        </h1>
        <p style="font-size:15px;opacity:0.75;overflow-wrap:anywhere;">
            {Validadores.html_escape(subtitulo)}
        </p>
    </div>
    """
    _safe_render_html(markup)


@tolerante_kwargs
def render_hero_totale_2(
    titulo: str, subtitulo: str = "", valor: str = "", label: str = ""
) -> None:
    valor_html = (
        '<div style="flex:0 0 auto;padding:15px 25px;border-radius:12px;text-align:center;'
        'background:rgba(255,255,255,0.08);border:1px solid rgba(243,124,4,0.28);">'
        '<div style="font-size:10px;text-transform:uppercase;opacity:0.75;letter-spacing:0.6px;">'
        f"{Validadores.html_escape(label)}</div>"
        '<div style="font-size:28px;font-weight:900;color:#FF9D45;">'
        f"{Validadores.html_escape(valor)}</div></div>"
        if valor
        else ""
    )
    markup = f"""
    <div style="width:100%;box-sizing:border-box;overflow:hidden;display:flex;flex-wrap:wrap;gap:20px;
                align-items:center;justify-content:space-between;padding:30px;margin-bottom:24px;
                color:#FFFFFF;border-radius:16px;
                background:linear-gradient(120deg,#012869,#033486);
                box-shadow:0 8px 24px rgba(1,40,105,0.18);">
        <div style="min-width:0;flex:1 1 320px;">
            <h1 style="margin:0;font-size:28px;font-weight:800;overflow-wrap:anywhere;">
                {Validadores.html_escape(titulo)}
            </h1>
            <p style="margin-top:5px;font-size:14px;opacity:0.85;overflow-wrap:anywhere;">
                {Validadores.html_escape(subtitulo)}
            </p>
        </div>
        {valor_html}
    </div>
    """
    _safe_render_html(markup)


@tolerante_kwargs
def render_hero_migracao(
    titulo: str, subtitulo: str = "", stats: list[dict[str, Any]] | None = None
) -> None:
    cards = "".join(
        '<div style="padding:10px;border-radius:8px;text-align:center;background:rgba(255,255,255,0.10);">'
        f'<div style="font-size:18px;font-weight:900;color:#FF9D45;">{Validadores.html_escape(s.get("valor", "-"))}</div>'
        f'<div style="font-size:9px;text-transform:uppercase;opacity:0.85;">{Validadores.html_escape(s.get("label", ""))}</div></div>'
        for s in (stats or [])
    )
    markup = f"""
    <div style="width:100%;box-sizing:border-box;overflow:hidden;padding:30px;margin-bottom:24px;
                color:#FFFFFF;border-radius:16px;background:linear-gradient(135deg,#4C1D95,#7C3AED);">
        <h1 style="margin:0;font-size:28px;font-weight:900;overflow-wrap:anywhere;">
            {Validadores.html_escape(titulo)}
        </h1>
        <p style="margin:5px 0 20px;font-size:14px;opacity:0.85;overflow-wrap:anywhere;">
            {Validadores.html_escape(subtitulo)}
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:12px;">
            {cards}
        </div>
    </div>
    """
    _safe_render_html(markup)


@tolerante_kwargs
def render_hero_pme(
    titulo: str, subtitulo: str = "", features: list[str] | None = None
) -> None:
    pills = "".join(
        '<span style="padding:4px 12px;border-radius:20px;font-size:11px;'
        f'background:rgba(255,255,255,0.16);">✓ {Validadores.html_escape(f)}</span>'
        for f in (features or [])
    )
    markup = f"""
    <div style="width:100%;box-sizing:border-box;overflow:hidden;padding:30px;margin-bottom:24px;
                color:#FFFFFF;border-radius:16px;background:linear-gradient(135deg,#059669,#10B981);">
        <h1 style="margin:0;font-size:28px;font-weight:900;overflow-wrap:anywhere;">
            {Validadores.html_escape(titulo)}
        </h1>
        <p style="margin:5px 0 15px;font-size:14px;opacity:0.85;overflow-wrap:anywhere;">
            {Validadores.html_escape(subtitulo)}
        </p>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">{pills}</div>
    </div>
    """
    _safe_render_html(markup)


@tolerante_kwargs
def render_hero_novos_domicilios(
    titulo: str, subtitulo: str = "", stats: list[dict[str, Any]] | None = None
) -> None:
    cards = "".join(
        '<div style="padding:12px;border-radius:10px;text-align:center;background:rgba(255,255,255,0.12);">'
        f'<div style="font-size:20px;font-weight:900;color:#4ADE80;">{Validadores.html_escape(s.get("valor", "-"))}</div>'
        f'<div style="font-size:10px;text-transform:uppercase;opacity:0.85;">{Validadores.html_escape(s.get("label", ""))}</div></div>'
        for s in (stats or [])
    )
    markup = f"""
    <div style="width:100%;box-sizing:border-box;overflow:hidden;padding:30px;margin-bottom:24px;
                color:#FFFFFF;border-radius:16px;background:linear-gradient(135deg,#012869,#14B8A6);">
        <h1 style="margin:0;font-size:28px;font-weight:900;overflow-wrap:anywhere;">
            {Validadores.html_escape(titulo)}
        </h1>
        <p style="margin:5px 0 20px;font-size:14px;opacity:0.85;overflow-wrap:anywhere;">
            {Validadores.html_escape(subtitulo)}
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:12px;">
            {cards}
        </div>
    </div>
    """
    _safe_render_html(markup)


# =============================================================================
# COMPONENTES VISUAIS E KPIS
# =============================================================================
def render_section_header(
    titulo: str = "",
    icone: str = "",
    badge: str = "",
    subtitulo: str = "",
    **kwargs: Any,
) -> None:
    ic_html = _icone_tile(icone, "section") if icone else ""
    badge_html = (
        '<span style="background:#FFF4E5;color:#9A3412;border:1px solid rgba(243,124,4,0.35);'
        'padding:3px 10px;border-radius:20px;font-size:10px;font-weight:800;text-transform:uppercase;">'
        f"{Validadores.html_escape(badge)}</span>"
        if badge
        else ""
    )
    subtitulo_html = (
        '<p style="margin:4px 0 0;font-size:13px;color:#6B7280;overflow-wrap:anywhere;">'
        f"{Validadores.html_escape(subtitulo)}</p>"
        if subtitulo
        else ""
    )
    markup = f"""
    <div style="display:flex;align-items:center;gap:12px;margin:30px 0 15px;padding-bottom:12px;
                border-bottom:3px solid var(--cor-primaria);
                border-image:linear-gradient(90deg,var(--cor-primaria),var(--cor-secundaria)) 1;">
        {ic_html}
        <div style="flex:1;min-width:0;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <h2 style="margin:0;font-size:22px;font-weight:800;color:var(--cor-primaria);
                           overflow-wrap:anywhere;">
                    {Validadores.html_escape(titulo)}
                </h2>
                {badge_html}
            </div>
            {subtitulo_html}
        </div>
    </div>
    """
    _safe_render_html(markup)


def _card_premium(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: str = "azul",
    icone: str = "",
    compacto: bool = False,
    sub_is_html: bool = False,
) -> None:
    cor = ConfigCores.TEMA.get(tema, Cores.PRIMARIA)
    padding = "14px" if compacto else "20px"
    valor_tamanho = "24px" if compacto else "32px"
    sub_render = sub if sub_is_html else Validadores.html_escape(sub)
    sub_html = (
        f'<div style="font-size:11px;color:#94A3B8;margin-top:8px;">{sub_render}</div>'
        if sub
        else ""
    )
    markup = f"""
    <div class="card-premium" style="padding:{padding};">
        <div class="card-accent-top" style="background:{cor};"></div>
        <div style="display:flex;justify-content:space-between;gap:8px;">
            <div class="kpi-label-premium">{Validadores.html_escape(label)}</div>
            <div style="font-size:20px;opacity:0.5;">{Validadores.html_escape(icone)}</div>
        </div>
        <div class="kpi-value-premium" style="font-size:{valor_tamanho};overflow-wrap:anywhere;">
            {Validadores.html_escape(valor)}
        </div>
        {sub_html}
    </div>
    """
    _safe_render_html(markup, container)


@tolerante_kwargs
def render_kpi(
    col: Any, label: str, valor: str, sub: str = "", tema: str = "azul", icone: str = ""
) -> None:
    _card_premium(col, label, valor, sub, tema, icone, compacto=False)


@tolerante_kwargs
def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: str = "azul",
    icone: str = "",
) -> None:
    _card_premium(container, label, valor, sub, tema, icone, compacto=True)


@tolerante_kwargs
def render_metric_card(
    col: Any,
    label: str,
    valor: str,
    trend: str = "none",
    trend_valor: str = "",
    sub: str = "",
) -> None:
    delta_html = ""
    if trend != "none":
        c_t = Cores.SUCESSO if trend == "up" else Cores.ALERTA
        delta_html = (
            f'<span style="background:{c_t}15;color:{c_t};padding:2px 6px;border-radius:4px;'
            'font-size:10px;font-weight:800;">'
            f"{ConfigCores.TREND_ICONS.get(trend, '')} {Validadores.html_escape(trend_valor)}</span>"
        )
    sub_completo = f"{delta_html} {Validadores.html_escape(sub)}".strip()
    _card_premium(
        col, label, valor, sub_completo, "azul", compacto=False, sub_is_html=True
    )


@tolerante_kwargs
def render_insight(msg: str, tipo: str = "info", titulo: str = "") -> None:
    bg, tx, br, ic = ConfigCores.INSIGHT.get(tipo, ConfigCores.INSIGHT["info"])
    titulo_html = (
        '<div style="font-weight:800;font-size:12px;text-transform:uppercase;margin-bottom:4px;">'
        f"{Validadores.html_escape(titulo)}</div>"
        if titulo
        else ""
    )
    markup = f"""
    <div style="background:{bg};color:{tx};border-left:4px solid {br};padding:15px;
                border-radius:8px;margin:15px 0;box-sizing:border-box;">
        <div style="display:flex;gap:10px;">
            <span style="font-size:20px;flex-shrink:0;">{ic}</span>
            <div style="min-width:0;">
                {titulo_html}
                <div style="font-size:14px;line-height:1.5;overflow-wrap:anywhere;">
                    {Formatadores.markdown_para_html(msg)}
                </div>
            </div>
        </div>
    </div>
    """
    _safe_render_html(markup)


@tolerante_kwargs
def render_notification(
    mensagem: str, tipo: str = "info", titulo: str = "", container: Any = None
) -> None:
    bg, fg, br, ic = ConfigCores.NOTIFICATION.get(
        tipo, ConfigCores.NOTIFICATION["info"]
    )
    titulo_html = f"<b>{Validadores.html_escape(titulo)}</b><br>" if titulo else ""
    markup = f"""
    <div style="background:{bg};color:{fg};border:1px solid {br};border-radius:10px;
                padding:12px 16px;margin:10px 0;display:flex;gap:10px;box-sizing:border-box;
                box-shadow:0 1px 3px rgba(0,0,0,0.05);">
        <span style="flex-shrink:0;">{ic}</span>
        <div style="font-size:13px;min-width:0;overflow-wrap:anywhere;">
            {titulo_html}{Formatadores.markdown_para_html(mensagem)}
        </div>
    </div>
    """
    _safe_render_html(markup, container)


@tolerante_kwargs
def render_empty_state(
    tipo: str = "padrao", titulo: str = "", descricao: str = ""
) -> None:
    bg, cor, ic, tit_def = ConfigCores.EMPTY_STATE.get(
        tipo, ConfigCores.EMPTY_STATE["padrao"]
    )
    markup = f"""
    <div style="background:{bg};border:2px dashed {cor}40;border-radius:12px;padding:40px;
                text-align:center;margin:20px 0;box-sizing:border-box;">
        <div style="font-size:40px;margin-bottom:10px;">{ic}</div>
        <h3 style="margin:0;color:{cor};font-size:18px;">
            {Validadores.html_escape(titulo or tit_def)}
        </h3>
        <p style="margin-top:5px;color:#6B7280;font-size:13px;">
            {Validadores.html_escape(descricao)}
        </p>
    </div>
    """
    _safe_render_html(markup)


@tolerante_kwargs
def render_progress_bar(
    valor: float, maximo: float = 100.0, label: str = "", tema: str = "azul"
) -> None:
    p = min(100.0, max(0.0, (valor / maximo) * 100)) if maximo > 0 else 0.0
    cor = ConfigCores.PROGRESS_BAR.get(tema, Cores.PRIMARIA)
    cor_texto = Cores.PRIMARIA if tema == "gradiente" else cor
    markup = f"""
    <div style="margin:15px 0;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;
                    font-size:12px;font-weight:700;gap:8px;">
            <span style="color:#374151;overflow-wrap:anywhere;">{Validadores.html_escape(label)}</span>
            <span style="color:{cor_texto};flex-shrink:0;">{p:.1f}%</span>
        </div>
        <div style="width:100%;height:8px;border-radius:10px;background:#E2E8F0;overflow:hidden;">
            <div style="width:{p}%;height:100%;background:{cor};transition:width .5s ease;"></div>
        </div>
    </div>
    """
    _safe_render_html(markup)


def render_table_html(
    df: pd.DataFrame,
    titulo: str = "",
    height: int = 400,
    exportar_excel: bool = False,
    **kwargs: Any,
) -> None:
    if df is None or df.empty:
        render_empty_state("dados", "Tabela vazia")
        return

    th = "".join(
        "<th style='padding:12px;background:#F8FAFC;border-bottom:2px solid #E2E8F0;"
        "font-size:11px;text-transform:uppercase;color:#64748B;white-space:nowrap;'>"
        f"{Validadores.html_escape(c)}</th>"
        for c in df.columns
    )

    rows = ""
    for i, (_, row) in enumerate(df.iterrows()):
        tds = ""
        for val in row:
            v_str = str(val)
            estilo_badge = ""
            v_up = normalizar_texto_badge(v_str)
            if v_up in ("SIM", "ATIVO", "CONCLUIDO"):
                estilo_badge = (
                    "background:#D1FAE5;color:#065F46;padding:2px 8px;border-radius:10px;"
                    "font-size:10px;font-weight:700;"
                )
            elif v_up in ("NAO", "INATIVO", "CANCELADO"):
                estilo_badge = (
                    "background:#FEE2E2;color:#991B1B;padding:2px 8px;border-radius:10px;"
                    "font-size:10px;font-weight:700;"
                )
            tds += (
                "<td style='padding:10px 12px;border-bottom:1px solid #F1F5F9;font-size:12px;'>"
                f"<span style='{estilo_badge}'>{Validadores.html_escape(v_str)}</span></td>"
            )
        fundo = "#FFFFFF" if i % 2 == 0 else "#FBFBFC"
        rows += f"<tr style='background:{fundo};'>{tds}</tr>"

    titulo_html = (
        '<div style="font-weight:800;font-size:16px;color:var(--cor-primaria);margin-bottom:10px;'
        'border-left:4px solid var(--cor-secundaria);padding-left:10px;">'
        f"{Validadores.html_escape(titulo)}</div>"
        if titulo
        else ""
    )
    markup = f"""
    <div style="margin:20px 0;width:100%;box-sizing:border-box;">
        {titulo_html}
        <div style="border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(1,40,105,0.05);">
            <div style="max-height:{height}px;overflow:auto;">
                <table style="width:100%;border-collapse:collapse;text-align:left;">
                    <thead><tr>{th}</tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </div>
    </div>
    """
    _safe_render_html(markup)

    if exportar_excel:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        st.download_button(
            "📥 Baixar Excel",
            output.getvalue(),
            "relatorio.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


@tolerante_kwargs
def render_skeleton(linhas: int = 3) -> None:
    rows = "".join(
        "<div style='height:16px;background:#F1F5F9;border-radius:4px;margin-bottom:10px;"
        f"width:{'100%' if i < linhas - 1 else '60%'};animation:pulse 1.5s infinite;'></div>"
        for i in range(linhas)
    )
    markup = (
        "<style>@keyframes pulse{0%{opacity:.6}50%{opacity:1}100%{opacity:.6}}</style>"
        f"<div style='margin:15px 0;'>{rows}</div>"
    )
    _safe_render_html(markup)


@tolerante_kwargs
def render_spacer(altura: int = 16) -> None:
    _safe_render_html(f"<div style='height:{altura}px;'></div>")


@tolerante_kwargs
def render_badge(texto: str, tipo: str = "default") -> None:
    bg, fg, br = ConfigCores.BADGE.get(tipo, ConfigCores.BADGE["default"])
    markup = (
        f"<span style='background:{bg};color:{fg};border:1px solid {br};padding:3px 12px;"
        "border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;'>"
        f"{Validadores.html_escape(texto)}</span>"
    )
    _safe_render_html(markup)


# =============================================================================
# EXPORTAÇÃO
# =============================================================================
__all__ = [
    # Estilo
    "aplicar_estilo",
    "aplicar_estilo_corp",
    "aplicar_sidebar_corp",
    # Sidebar
    "render_sidebar_brand",
    "render_sidebar_section",
    "render_sidebar_divider",
    "render_sidebar_footer_info",
    "render_sidebar_info",
    "render_sidebar_spacer",
    "render_sidebar_status",
    # Hero
    "render_hero",
    "render_hero_totale_1",
    "render_hero_totale_2",
    "render_hero_migracao",
    "render_hero_pme",
    "render_hero_novos_domicilios",
    # Conteúdo
    "render_section_header",
    "render_kpi",
    "render_kpi_sm",
    "render_metric_card",
    "render_insight",
    "render_notification",
    "render_empty_state",
    "render_progress_bar",
    "render_table_html",
    "render_spacer",
    "render_badge",
    "render_skeleton",
    # Utilitários
    "formatar_numero_br",
    "formatar_datetime_exibicao",
    "tolerante_kwargs",
    # Configuração
    "Validadores",
    "Formatadores",
    "ConfigCores",
    "Cores",
    "Fontes",
    "GoogleFonts",
    "StreamlitContainer",
]