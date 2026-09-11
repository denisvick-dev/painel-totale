"""
components/componentes.py
=========================
Design System Streamlit — TOTALE

Versão: 4.7.0 (Enterprise Polish & Icon Safety)
Autor: TOTALE Tecnologia

Evoluções desta versão:
• Sistema de ícones em tile, eliminando o quadrado de gradiente em emojis.
• Remoção do bloco CSS duplicado de .hero-domicilios.
• Tabela premium isolada de dark mode (color-scheme: light).
• render_notification normalizando o parâmetro correto.
• render_kpi_sm sem renderização duplicada.
• Exportação Excel única em render_table_html.
• Normalizador de acentuação para badges automáticos em tabelas.
"""

from __future__ import annotations

import html as html_lib
import io
import logging
import re
import unicodedata
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
    GRADIENTE = "gradiente"


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
    NOVOS_DOMICILIOS = "novos_domicilios"


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

    GRADIENTES: dict[str, tuple[str, str]] = {
        "azul": ("#012869", "#0A48AA"),
        "laranja": ("#F37C04", "#FDBA74"),
        "verde": ("#065F46", "#047857"),
        "vermelho": ("#991B1B", "#DC2626"),
        "roxo": ("#5B21B6", "#7C3AED"),
        "cinza": ("#475569", "#64748B"),
        "gradiente": ("#012869", "#B45309"),
    }

    FUNDOS_SUAVES: dict[str, str] = {
        "azul": "#EFF6FF",
        "verde": "#ECFDF5",
        "vermelho": "#FEF2F2",
        "laranja": "#FFF7ED",
        "cinza": "#F8FAFC",
        "roxo": "#F5F3FF",
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


def _resolver_gradiente(tema: str) -> tuple[str, str]:
    grad = ConfigCores.GRADIENTES.get(tema)
    if grad is None:
        return ConfigCores.GRADIENTES["azul"]
    return grad


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
        tema,
        {"azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"},
        "azul",
    )  # type: ignore[return-value]


def normalizar_tipo_badge(tipo: Any) -> TipoBadgeType:
    return normalizar_tipo(
        tipo,
        {"default", "sucesso", "alerta", "erro", "info", "roxo", "laranja"},
        "default",
    )  # type: ignore[return-value]


def normalizar_tipo_progress(tema: Any) -> TipoProgressBarType:
    return normalizar_tipo(
        tema,
        {"azul", "laranja", "verde", "vermelho", "roxo", "gradiente"},
        "azul",
    )  # type: ignore[return-value]


def normalizar_tipo_trend(trend: Any) -> TipoTrendType:
    return normalizar_tipo(trend, {"up", "down", "neutral", "none"}, "none")  # type: ignore[return-value]


def normalizar_tipo_insight(tipo: Any) -> TipoInsightType:
    return normalizar_tipo(tipo, {"ok", "info", "alerta", "critico", "acao"}, "info")  # type: ignore[return-value]


def normalizar_texto_badge(txt: str) -> str:
    """
    Remove tags HTML, normaliza acentuação e retorna a string em caixa alta.

    Exemplos:
        "Não"        -> "NAO"
        "Concluído"  -> "CONCLUIDO"
    """
    txt_clean = re.sub(r"<[^>]+>", "", str(txt))
    normalized = unicodedata.normalize("NFKD", txt_clean)
    without_accents = "".join(c for c in normalized if not unicodedata.combining(c))
    return without_accents.strip().upper()

_FORMATOS_DATA_BR: tuple[str, ...] = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)

try:
    _PANDAS_SUPORTA_MIXED = (
        tuple(int(p) for p in pd.__version__.split(".")[:2]) >= (2, 0)
    )
except ValueError:
    _PANDAS_SUPORTA_MIXED = False


def converter_data_br(serie: pd.Series) -> pd.Series:
    """
    Converte uma coluna para datetime lendo sempre DIA/MÊS/ANO.

    - datetime64: mantido;
    - serial do Excel (ex.: 46270): convertido pela origem 1899-12-30;
    - texto: formatos brasileiros/ISO e, por fim, parser com dayfirst=True.

    "05/09/2026" vira 2026-09-05 (5 de setembro), nunca 9 de maio.
    """
    if serie is None or len(serie) == 0:
        return pd.Series(dtype="datetime64[ns]")

    if pd.api.types.is_datetime64_any_dtype(serie):
        return pd.to_datetime(serie, errors="coerce")

    resultado = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")

    # 1) Seriais numéricos do Excel
    try:
        numericos = pd.to_numeric(serie, errors="coerce")
    except (TypeError, ValueError):
        numericos = pd.Series(np.nan, index=serie.index)
    mask_serial = numericos.between(20_000, 80_000)  # ~1954 a ~2119
    if mask_serial.any():
        resultado.loc[mask_serial] = pd.to_datetime(
            numericos[mask_serial], unit="D", origin="1899-12-30", errors="coerce"
        )

    # 2) Textos nos formatos conhecidos (dia primeiro)
    textos = serie.astype(str).str.strip()
    textos = textos.mask(textos.isin(["", "nan", "None", "NaT", "NaN", "-", "NULL"]))
    pendentes = resultado.isna() & textos.notna()

    for fmt in _FORMATOS_DATA_BR:
        if not pendentes.any():
            break
        parsed = pd.to_datetime(textos[pendentes], format=fmt, errors="coerce")
        ok = parsed.notna()
        if ok.any():
            idx = parsed.index[ok]
            resultado.loc[idx] = parsed.loc[idx]
            pendentes.loc[idx] = False

    # 3) Último recurso: parser flexível, ainda com dia primeiro
    if pendentes.any():
        kwargs: dict[str, Any] = {"dayfirst": True, "errors": "coerce"}
        if _PANDAS_SUPORTA_MIXED:
            kwargs["format"] = "mixed"
        parsed = pd.to_datetime(textos[pendentes], **kwargs)
        ok = parsed.notna()
        if ok.any():
            idx = parsed.index[ok]
            resultado.loc[idx] = parsed.loc[idx]

    return resultado

def formatar_datetime_exibicao(valor: Any, com_segundos: bool = False) -> str:
    """
    Formata datetime/string para exibição amigável.

    Exemplos:
        2026-09-11 16:43:52.825008-03:00 -> 11/09/2026 16:43
        2026-09-11T16:43:52-03:00       -> 11/09/2026 16:43
    """
    if valor is None:
        return ""

    try:
        ts = pd.Timestamp(valor)

        if pd.isna(ts):
            return str(valor)

        formato = "%d/%m/%Y %H:%M:%S" if com_segundos else "%d/%m/%Y %H:%M"
        return ts.strftime(formato)
    except Exception:
        return str(valor)


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


def _icone_tile(icone: str, variante: str = "section") -> str:
    """
    Constrói um tile de ícone corporativo.

    O emoji nunca recebe background-clip:text, evitando o quadrado
    de gradiente exibido por alguns navegadores.
    """
    texto = str(icone or "").strip()
    if not texto:
        return ""

    variante_norm = variante if variante in {"section", "brand"} else "section"

    return (
        f'<span class="totale-icon-tile totale-icon-tile--{variante_norm}" '
        'aria-hidden="true">'
        '<span class="totale-icon-glyph">'
        f"{Validadores.html_escape(texto)}"
        "</span>"
        "</span>"
    )


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
    --cor-primaria-dark: {Cores.PRIMARIA_DARK};
    --cor-secundaria: {Cores.SECUNDARIA};
    --cor-secundaria-dark: {Cores.SECUNDARIA_DARK};
    --cor-secundaria-light: {Cores.SECUNDARIA_LIGHT};
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
.hero-title { font-size: clamp(24px, 3vw, 36px); font-weight: 900; color: #FFFFFF; margin: 0 0 8px 0; line-height: 1.15; position: relative; z-index: 2; }
.hero-subtitle { font-size: clamp(14px, 1.5vw, 17px); color: rgba(255,255,255,0.85); margin: 0; line-height: 1.5; position: relative; z-index: 2; }
.hero-badge { display: inline-block; background: rgba(255,255,255,0.15); -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,0.25); color: #FFFFFF; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; padding: 6px 16px; border-radius: 20px; margin-bottom: 16px; position: relative; z-index: 2; }
.totale-hero-1 { background: linear-gradient(135deg, #011E52 0%, #012869 45%, #0A48AA 80%, #F37C04 130%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(243,124,4,0.25); box-shadow: 0 12px 32px rgba(1,40,105,0.28); margin-bottom: 24px; position: relative; overflow: hidden; }
.totale-hero-2 { background: linear-gradient(120deg, #012869 0%, #033486 50%, #0747B3 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border-left: 6px solid #F37C04; box-shadow: 0 10px 28px rgba(1,40,105,0.22); margin-bottom: 24px; display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: center; position: relative; overflow: hidden; }
@media (max-width: 768px) { .totale-hero-2 { grid-template-columns: 1fr; } }
.totale-hero-2-card { background: rgba(255,255,255,0.08); -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.18); border-radius: 12px; padding: 16px 24px; min-width: 180px; text-align: center; position: relative; z-index: 2; }
.hero-migracao { background: linear-gradient(135deg, #4C1D95 0%, #6D28D9 35%, #7C3AED 60%, #A78BFA 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(167,139,250,0.30); box-shadow: 0 12px 32px rgba(124,58,237,0.35); margin-bottom: 24px; position: relative; overflow: hidden; }
.hero-pme { background: linear-gradient(135deg, #059669 0%, #10B981 35%, #3B82F6 70%, #60A5FA 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(255,255,255,0.25); box-shadow: 0 12px 32px rgba(16,185,129,0.30); margin-bottom: 24px; position: relative; overflow: hidden; }
.hero-domicilios { background: linear-gradient(135deg, #012869 0%, #0A3D62 35%, #0D9488 70%, #14B8A6 100%); border-radius: 16px; padding: 28px 36px; color: #FFFFFF; border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 12px 32px rgba(1,40,105,0.28); margin-bottom: 24px; position: relative; overflow: hidden; }
.hero-domicilios::before { content: ''; position: absolute; top: -40%; right: -10%; width: 350px; height: 350px; background: radial-gradient(circle, rgba(255,255,255,0.10) 0%, transparent 65%); pointer-events: none; }
.th-title-lg { font-size: clamp(22px, 2.5vw, 32px); font-weight: 900; color: #FFFFFF; margin: 12px 0 8px; line-height: 1.15; letter-spacing: -0.5px; }
.th-title { font-size: clamp(20px, 2vw, 28px); font-weight: 800; color: #FFFFFF; margin: 12px 0 8px; line-height: 1.15; }
.th-sub { font-size: 14px; color: rgba(255,255,255,0.80); margin: 0; line-height: 1.5; }
.th-sub-muted { font-size: 14px; color: rgba(255,255,255,0.70); margin: 0 0 4px; line-height: 1.5; }
.th-meta { font-size: 12px; color: rgba(255,255,255,0.60); margin-top: 8px; }
.th-badge { display: inline-block; background: #F37C04; color: #FFFFFF; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; padding: 4px 12px; border-radius: 4px; margin-bottom: 8px; }
.th-tag { display: inline-block; font-size: 11px; color: rgba(255,255,255,0.70); margin-left: 8px; }
.th-card-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: rgba(255,255,255,0.70); margin-bottom: 4px; }
.th-card-value { font-size: 28px; font-weight: 900; color: #F37C04; line-height: 1; }
.totale-badge-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border: 1px solid transparent; }
"""

_CSS_CARDS = """
@keyframes card-color-shift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
.card-premium { background: var(--cor-card-bg); border-radius: 12px; padding: 20px 24px; border: 1px solid var(--cor-borda); box-shadow: 0 1px 2px rgba(15,23,42,0.03), 0 4px 6px -1px rgba(0,0,0,0.02); transition: transform 0.28s cubic-bezier(0.4,0,0.2,1), box-shadow 0.28s ease, border-color 0.28s ease; margin-bottom: 12px; position: relative; overflow: hidden; display: flex; flex-direction: column; justify-content: space-between; }
.card-premium:hover { transform: translateY(-4px); box-shadow: 0 4px 8px -2px rgba(15,23,42,0.05), 0 12px 24px -6px rgba(15,23,42,0.10); border-color: #CBD5E1; }
.card-premium-colorida { background: linear-gradient(135deg, #012869 0%, #F37C04 100%); background-size: 200% 200%; animation: card-color-shift 8s ease infinite; border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 8px 24px rgba(1,40,105,0.25); color: #FFFFFF; }
.card-premium-colorida .kpi-label-premium { color: rgba(255,255,255,0.85); }
.card-premium-colorida .kpi-value-premium { color: #FFFFFF; }
.card-premium-colorida .kpi-sub-premium { color: rgba(255,255,255,0.80); }
.card-premium-colorida .kpi-icon-wrapper { background: rgba(255,255,255,0.15) !important; color: #FFFFFF !important; -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); }
.card-premium-colorida:hover { box-shadow: 0 12px 32px rgba(1,40,105,0.35); border-color: rgba(243,124,4,0.40); }
.card-accent-top { position: absolute; top: 0; left: 0; right: 0; height: 3px; }
.card-header-flex { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; position: relative; z-index: 2; }
.kpi-label-premium { font-size: 12px; font-weight: 600; color: var(--cor-texto-3); text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.4; }
.kpi-icon-wrapper { display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0; }
.kpi-value-premium { font-size: 32px; font-weight: 800; color: var(--cor-texto); line-height: 1; font-variant-numeric: tabular-nums; font-family: var(--font-titulo) !important; letter-spacing: -0.5px; position: relative; z-index: 2; }
.kpi-sub-premium { font-size: 13px; color: var(--cor-texto-3); margin-top: 8px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; position: relative; z-index: 2; }
.trend-pill { display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 20px; font-size: 12px; font-weight: 700; line-height: 1; }
.trend-up { background: #ECFDF5; color: #059669; }
.trend-down { background: #FEF2F2; color: #DC2626; }
.trend-neutral { background: #F8FAFC; color: #64748B; }
"""

_CSS_TABELAS = """
/* ====================== TABELA PREMIUM ENTERPRISE ====================== */
.table-premium-wrapper {
    color-scheme: light !important;
    background: #FFFFFF !important;
    border-radius: 12px !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04) !important;
    overflow: hidden !important;
    margin: 20px 0 !important;
}

.table-premium-scroll {
    width: 100% !important;
    overflow-x: auto !important;
    scrollbar-width: thin !important;
    scrollbar-color: #CBD5E1 transparent !important;
    background: #FFFFFF !important;
}

.totale-table-pro {
    width: 100% !important;
    border-collapse: collapse !important;
    text-align: left !important;
    font-family: var(--font-texto) !important;
    background: #FFFFFF !important;
}

.totale-table-pro thead,
.totale-table-pro thead tr,
.totale-table-pro th {
    background: #F8FAFC !important;
}

.totale-table-pro th {
    color: #475569 !important;
    font-family: var(--font-titulo) !important;
    font-size: 11px !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
    padding: 14px 16px !important;
    border-bottom: 2px solid #E2E8F0 !important;
    white-space: nowrap !important;
}

.totale-table-pro tbody,
.totale-table-pro tbody tr,
.totale-table-pro tbody tr td {
    background: #FFFFFF !important;
}

.totale-table-pro td {
    padding: 12px 16px !important;
    border-bottom: 1px solid #F1F5F9 !important;
    color: #1E293B !important;
    font-size: 12.5px !important;
    line-height: 1.4 !important;
    vertical-align: middle !important;
    transition: background-color 0.15s ease !important;
    white-space: normal !important;
}

.totale-table-pro tbody tr.striped,
.totale-table-pro tbody tr.striped td {
    background-color: #F8FAFC !important;
}

.totale-table-pro tbody tr:hover,
.totale-table-pro tbody tr:hover td {
    background-color: #F1F5F9 !important;
    color: #0F172A !important;
}

.totale-table-pro tbody tr.linha-destaque,
.totale-table-pro tbody tr.linha-destaque td {
    background: linear-gradient(90deg, #FFF7ED 0%, #FFFBEB 100%) !important;
    border-top: 1.5px solid #F37C04 !important;
    border-bottom: 1.5px solid #F37C04 !important;
    color: #7C2D12 !important;
    font-weight: 700 !important;
}

.td-badge-ok {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    background-color: #D1FAE5 !important;
    color: #065F46 !important;
    padding: 3px 8px !important;
    border-radius: 12px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
}

.td-badge-alerta {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    background-color: #FEE2E2 !important;
    color: #991B1B !important;
    padding: 3px 8px !important;
    border-radius: 12px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
}

.td-badge-neutro {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    background-color: #E2E8F0 !important;
    color: #334155 !important;
    padding: 3px 8px !important;
    border-radius: 12px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
}
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
.section-title { font-size: clamp(18px, 2vw, 24px); font-weight: 800; color: var(--cor-primaria); margin: 0; line-height: 1.2; }
.section-subtitle { margin: 6px 0 0; font-size: 13px; color: var(--cor-texto-3); }
.user-info-card { background: linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%); border: 1px solid var(--cor-borda); border-radius: 12px; padding: 16px; margin: 12px 0; }

/* ====================== ÍCONES CORPORATIVOS ====================== */
/*
Não aplicar background-clip:text diretamente em emojis.
Alguns navegadores exibem apenas um quadrado com o gradiente.
*/
.totale-icon-tile {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
    background: linear-gradient(135deg, #012869 0%, #0A48AA 52%, #F37C04 100%) !important;
    background-clip: border-box !important;
    -webkit-background-clip: border-box !important;
    -webkit-text-fill-color: initial !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.24) !important;
    box-shadow: 0 4px 12px rgba(1,40,105,0.20) !important;
    overflow: hidden !important;
    line-height: 1 !important;
}

.totale-icon-tile--brand {
    width: 36px !important;
    height: 36px !important;
    min-width: 36px !important;
    border-radius: 10px !important;
}

.totale-icon-tile--section {
    width: 38px !important;
    height: 38px !important;
    min-width: 38px !important;
    border-radius: 10px !important;
}

.totale-icon-glyph {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: transparent !important;
    background-image: none !important;
    background-clip: border-box !important;
    -webkit-background-clip: border-box !important;
    color: initial !important;
    -webkit-text-fill-color: initial !important;
    font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif !important;
    font-style: normal !important;
    font-weight: 400 !important;
    font-size: 20px !important;
    line-height: 1 !important;
}

.totale-icon-tile--brand .totale-icon-glyph { font-size: 19px !important; }
.totale-icon-tile--section .totale-icon-glyph { font-size: 20px !important; }

.section-header-copy {
    flex: 1 !important;
    min-width: 0 !important;
}

.totale-icon-tile:empty,
.totale-icon-glyph:empty {
    display: none !important;
}
"""

_CSS_SIDEBAR = """
/* ====================== CONTAINER ====================== */
[data-testid="stSidebar"] {
    position: relative;
    background: linear-gradient(180deg, #FFFFFF 0%, #F4F7FB 100%);
    border-right: 1px solid #E2E8F0;
}
[data-testid="stSidebar"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, #012869 0%, #0A48AA 45%, #F37C04 100%);
    z-index: 100;
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    padding-top: 10px;
}
[data-testid="stSidebar"] ::-webkit-scrollbar { width: 6px; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
    background: #C7D2E4;
    border-radius: 3px;
}
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover { background: #F37C04; }

[data-testid="stSidebarCollapseButton"] button:hover {
    background: rgba(243,124,4,0.12) !important;
    color: #F37C04 !important;
}

/* ====================== CABEÇALHO DE SEÇÃO ====================== */
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {
    font-family: var(--font-titulo) !important;
    font-size: 10px !important;
    font-weight: 800 !important;
    letter-spacing: 1.4px !important;
    text-transform: uppercase !important;
    color: #012869 !important;
    padding: 6px 12px 8px 14px !important;
    margin: 20px 0 4px !important;
    position: relative;
}
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"]:first-child {
    margin-top: 4px !important;
}
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"]::before {
    content: "";
    position: absolute;
    left: 4px; top: 6px;
    width: 4px; height: 13px;
    border-radius: 2px;
    background: linear-gradient(180deg, #F37C04 0%, #FDBA74 100%);
}
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"]::after {
    content: "";
    position: absolute;
    left: 14px; right: 14px; bottom: 2px;
    height: 1px;
    background: linear-gradient(90deg, rgba(1,40,105,0.20) 0%, transparent 85%);
}

/* ====================== LISTA ====================== */
[data-testid="stSidebarNav"] ul {
    padding: 0 8px !important;
    margin: 0 !important;
    list-style: none !important;
}
[data-testid="stSidebarNav"] li { margin: 2px 0 !important; }

/* ====================== LINK ====================== */
[data-testid="stSidebarNav"] a {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 9px 12px !important;
    border-radius: 8px !important;
    border: 1px solid transparent !important;
    color: #334155 !important;
    font-family: var(--font-texto) !important;
    font-size: 13.5px !important;
    font-weight: 600 !important;
    line-height: 1.25 !important;
    text-decoration: none !important;
    position: relative;
    overflow: hidden;
    transition:
        background 0.18s ease,
        color 0.18s ease,
        border-color 0.18s ease,
        transform 0.18s ease;
}
[data-testid="stSidebarNav"] a span { color: inherit !important; }

[data-testid="stSidebarNav"] a > span:first-child,
[data-testid="stSidebarNav"] a [data-testid="stIconMaterial"] {
    flex-shrink: 0 !important;
    width: 20px !important;
    font-size: 17px !important;
    text-align: center !important;
    line-height: 1 !important;
}

[data-testid="stSidebarNav"] a:hover {
    background: linear-gradient(90deg,
        rgba(1,40,105,0.08) 0%,
        rgba(1,40,105,0.02) 100%) !important;
    border-color: rgba(1,40,105,0.12) !important;
    color: #012869 !important;
    transform: translateX(2px);
}
[data-testid="stSidebarNav"] a:hover::after {
    content: "";
    position: absolute;
    left: 0; top: 20%; bottom: 20%;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: #F37C04;
}

[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: linear-gradient(90deg, #012869 0%, #0A48AA 100%) !important;
    border-color: transparent !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 12px rgba(1,40,105,0.28);
    transform: none;
}
[data-testid="stSidebarNav"] a[aria-current="page"]::before {
    content: "";
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
    background: #F37C04;
}
[data-testid="stSidebarNav"] a[aria-current="page"]::after { display: none; }
[data-testid="stSidebarNav"] a[aria-current="page"] span {
    color: #FFFFFF !important;
}

[data-testid="stSidebarNav"] a:focus-visible {
    outline: 2px solid #F37C04;
    outline-offset: 1px;
}

[data-testid="stSidebarNavSeparator"] {
    margin: 14px 12px !important;
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg,
        transparent, rgba(1,40,105,0.18), transparent) !important;
}

/* ====================== COMPONENTES CUSTOM ====================== */
.sidebar-brand {
    padding: 6px 4px 14px;
    margin-bottom: 6px;
    border-bottom: 2px solid transparent;
    border-image: linear-gradient(90deg, #012869 0%, #F37C04 100%) 1;
}
.sidebar-section-header {
    margin: 18px 0 6px;
    padding: 6px 0 8px 14px;
    position: relative;
}
.sidebar-section-header::before {
    content: "";
    position: absolute;
    left: 4px; top: 6px;
    width: 4px; height: 13px;
    border-radius: 2px;
    background: linear-gradient(180deg, #F37C04 0%, #FDBA74 100%);
}
.sidebar-footer {
    margin-top: 24px;
    padding: 14px 12px 10px;
    border-top: 2px solid transparent;
    border-image: linear-gradient(90deg, #012869 0%, #F37C04 100%) 1;
    background: linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 100%);
    border-radius: 0 0 10px 10px;
}
"""

_CSS_SIDEBAR_NAV_ATIVO = """
/* ===== ITEM ATIVO DO st.navigation — texto branco, prioridade máxima ===== */
html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] [aria-current="page"] {
    background: linear-gradient(90deg, #012869 0%, #0A48AA 100%) !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    font-weight: 700 !important;
}
html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] [aria-current="page"] *,
html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] [aria-current="page"]:hover,
html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] [aria-current="page"]:hover * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    fill: #FFFFFF !important;
    text-shadow: none !important;
}
html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] [aria-current="page"]:hover {
    background: linear-gradient(90deg, #012869 0%, #0A48AA 100%) !important;
    transform: none !important;
}

html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] a p,
html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] a [data-testid="stMarkdownContainer"] {
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
}

[data-testid="stElementContainer"]:has(iframe[height="0"]) {
    display: none !important;
}
"""

_CSS_SIDEBAR_ATIVO_LARANJA = """
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: linear-gradient(90deg, #FFF7ED 0%, #FFFBEB 100%) !important;
    border-color: #F37C04 !important;
    color: #7C2D12 !important;
    font-weight: 800 !important;
    box-shadow: 0 2px 8px rgba(243,124,4,0.20);
}
[data-testid="stSidebarNav"] a[aria-current="page"]::before {
    content: "";
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
    background: #F37C04;
}
[data-testid="stSidebarNav"] a[aria-current="page"] span {
    color: #7C2D12 !important;
}
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
                    "font": {
                        "family": Fontes.TEXTO,
                        "size": 12,
                        "color": Cores.TEXTO_2,
                    },
                    "bgcolor": "rgba(255,255,255,0.8)",
                    "bordercolor": Cores.BORDA,
                    "borderwidth": 1,
                },
                xaxis={
                    "gridcolor": "#F1F5F9",
                    "zerolinecolor": "#CBD5E1",
                    "title": {
                        "font": {
                            "family": Fontes.TITULO,
                            "size": 13,
                            "color": Cores.TEXTO_2,
                        }
                    },
                },
                yaxis={
                    "gridcolor": "#F1F5F9",
                    "zerolinecolor": "#CBD5E1",
                    "title": {
                        "font": {
                            "family": Fontes.TITULO,
                            "size": 13,
                            "color": Cores.TEXTO_2,
                        }
                    },
                },
                paper_bgcolor="white",
                plot_bgcolor="white",
                colorway=ConfigCores.PLOTLY_COLORWAY,
                hoverlabel={
                    "bgcolor": "#FFFFFF",
                    "bordercolor": Cores.BORDA,
                    "font": {"family": Fontes.TEXTO, "size": 12, "color": Cores.TEXTO},
                },
                margin={"t": 50, "b": 40, "l": 50, "r": 20},
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


class NavContrastFix:
    """
    Força texto branco no item ativo do st.navigation via estilo inline.
    Inline com !important vence qualquer CSS legado do projeto.
    Reage a trocas de página com MutationObserver.
    """

    _COR = "#FFFFFF"

    _JS = """
<script>
(function () {
    var doc;
    try { doc = window.parent.document; } catch (e) { return; }
    if (!doc || !doc.body) return;

    var COR = "__COR__";
    var SEL_ATIVO = '[data-testid="stSidebar"] [aria-current="page"]';
    var SEL_MARCADO = '[data-testid="stSidebar"] [data-totale-ativo]';

    function pinta(el) {
        el.style.setProperty("color", COR, "important");
        el.style.setProperty("-webkit-text-fill-color", COR, "important");
    }
    function limpa(el) {
        el.style.removeProperty("color");
        el.style.removeProperty("-webkit-text-fill-color");
    }
    function aplicar() {
        doc.querySelectorAll(SEL_MARCADO).forEach(function (a) {
            if (a.getAttribute("aria-current") === "page") return;
            limpa(a);
            a.querySelectorAll("*").forEach(limpa);
            a.removeAttribute("data-totale-ativo");
        });
        doc.querySelectorAll(SEL_ATIVO).forEach(function (a) {
            pinta(a);
            a.querySelectorAll("*").forEach(pinta);
            a.setAttribute("data-totale-ativo", "1");
        });
    }

    var agendado = false;
    function agendar() {
        if (agendado) return;
        agendado = true;
        window.parent.setTimeout(function () { agendado = false; aplicar(); }, 0);
    }

    if (window.parent.__totaleNavObs) {
        try { window.parent.__totaleNavObs.disconnect(); } catch (e) {}
    }
    var obs = new MutationObserver(agendar);
    obs.observe(doc.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["aria-current"]
    });
    window.parent.__totaleNavObs = obs;
    aplicar();
})();
</script>
"""

    @staticmethod
    def injetar() -> None:
        components.html(
            NavContrastFix._JS.replace("__COR__", NavContrastFix._COR),
            height=0,
        )


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
            f"{_CSS_SIDEBAR}\n"
            f"{_CSS_SIDEBAR_NAV_ATIVO}\n"
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
    NavContrastFix.injetar()


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
    """
    Renderiza a marca no topo da sidebar.

    O emoji utiliza um tile próprio, evitando a exibição de um quadrado
    de gradiente causada por background-clip:text.
    """
    nome_final = str(titulo or nome or "").strip()
    subtitulo_final = str(kwargs.get("segmento", subtitulo) or "").strip()
    versao_final = str(versao or "").strip()
    icone_final = str(icone or "").strip()
    logo_final = logo or logo_url

    if not nome_final and not subtitulo_final and not logo_final:
        return

    with st.sidebar:
        logo_valida = bool(logo_final and Validadores.url(str(logo_final)))

        if logo_valida:
            st.image(str(logo_final), use_container_width=True)

        badge_html = ""
        if versao_final:
            badge_html = (
                "<span "
                'style="'
                "display:inline-block;"
                f"background-color:{Cores.AZUL_SUAVE};"
                f"color:{Cores.PRIMARIA};"
                "font-weight:700;"
                "font-size:10px;"
                "padding:2px 8px;"
                "border-radius:12px;"
                "border:1px solid #BFDBFE;"
                "margin-top:6px;"
                "text-transform:uppercase;"
                '">'
                f"{Validadores.html_escape(versao_final)}"
                "</span>"
            )

        icone_html = ""
        if not logo_valida:
            icone_html = _icone_tile(icone_final, "brand")

        nome_html = ""
        if nome_final:
            nome_html = (
                "<h2 "
                'style="'
                f"font-family:{Fontes.TITULO};"
                "font-size:18px;"
                "font-weight:800;"
                f"background:linear-gradient(135deg,{Cores.PRIMARIA} 0%,"
                f"{Cores.SECUNDARIA} 100%);"
                "-webkit-background-clip:text;"
                "background-clip:text;"
                "color:transparent;"
                "margin:0;"
                "line-height:1.2;"
                '">'
                f"{Validadores.html_escape(nome_final)}"
                "</h2>"
            )

        subtitulo_html = ""
        if subtitulo_final:
            subtitulo_html = (
                "<div "
                'style="'
                f"font-family:{Fontes.TEXTO};"
                "font-size:11px;"
                f"color:{Cores.TEXTO_3};"
                "margin-top:2px;"
                '">'
                f"{Validadores.html_escape(subtitulo_final)}"
                "</div>"
            )

        markup = (
            '<div class="sidebar-brand">'
            '<div style="display:flex;align-items:center;gap:10px;">'
            f"{icone_html}"
            '<div style="min-width:0;">'
            f"{nome_html}"
            f"{subtitulo_html}"
            "</div>"
            "</div>"
            f"{badge_html}"
            "</div>"
        )

        _safe_render_html(markup)


def render_sidebar_section(
    titulo: str, icone: str = "", collapsible: bool = False
) -> None:
    if collapsible:
        with st.sidebar.expander(f"{icone} {titulo}".strip(), expanded=True):
            pass
        return

    icone_html = (
        f'<span style="font-size:14px;line-height:1;color:{Cores.SECUNDARIA};">'
        f"{Validadores.html_escape(icone)}</span>"
        if icone
        else ""
    )
    markup = (
        '<div class="sidebar-section-header">'
        f'<div style="font-size:11px;font-weight:700;color:{Cores.PRIMARIA};'
        'text-transform:uppercase;display:flex;align-items:center;gap:6px;">'
        f"{icone_html}<span>{Validadores.html_escape(titulo)}</span>"
        "</div></div>"
    )
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
                + Cores.PRIMARIA
                + " 40%,"
                + Cores.SECUNDARIA
                + " 60%,transparent 100%);"
                if estilo == "gradiente"
                else "border:none;border-top:1px solid " + cor_final + ";"
            )
        )
        markup = (
            f'<div style="display:flex;align-items:center;gap:10px;margin:{margem};">'
            f'<div style="flex:1;{style_line}"></div>'
            f'<span style="font-size:9px;font-weight:700;color:{Cores.PRIMARIA};'
            'text-transform:uppercase;letter-spacing:1.2px;white-space:nowrap;">'
            f"{label_esc}</span>"
            f'<div style="flex:1;{style_line}"></div></div>'
        )
        with st.sidebar:
            _safe_render_html(markup)
        return

    style_line = (
        "border:none;border-top:1.5px dashed " + cor_final + ";"
        if estilo == "pontilhado"
        else (
            "border:none;height:1px;background:linear-gradient(90deg,transparent 0%,"
            + Cores.PRIMARIA
            + " 50%,"
            + Cores.SECUNDARIA
            + " 100%,transparent 100%);"
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
        f'<span style="display:inline-block;background:linear-gradient(135deg,'
        f"{Cores.PRIMARIA}15,{Cores.SECUNDARIA}15);color:{Cores.PRIMARIA};"
        f"font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;"
        f"border:1px solid {Cores.PRIMARIA}30;letter-spacing:0.4px;"
        f'text-transform:uppercase;">'
        f"{Validadores.html_escape(versao if str(versao).startswith('v') else f'v{versao}')}"
        "</span>"
        if versao
        else ""
    )

    amb_html = ""
    if ambiente:
        bg_a, fg_a, dot_a = _AMB_CFG.get(
            ambiente.lower().strip(), ("#F3F4F6", "#374151", "#9CA3AF")
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

    badges_row = (
        '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;'
        f'margin-bottom:10px;">{versao_html}{amb_html}</div>'
        if (versao_html or amb_html)
        else ""
    )

    unidade_html = (
        f'<div style="font-size:10px;font-weight:600;color:{Cores.TEXTO_2};'
        f"margin-bottom:8px;letter-spacing:0.2px;"
        f'border-left:3px solid {Cores.SECUNDARIA};padding-left:8px;">'
        f"{Validadores.html_escape(unidade)}</div>"
        if unidade
        else ""
    )

    itens_html = ""
    if itens_dict:
        rows = "".join(
            '<div style="display:flex;justify-content:space-between;'
            'align-items:center;padding:3px 0;gap:8px;">'
            f'<span style="font-size:10px;color:{Cores.TEXTO_3};font-weight:500;">'
            f"{Validadores.html_escape(k)}</span>"
            f'<span style="font-size:10px;color:{Cores.PRIMARIA};font-weight:700;'
            'font-variant-numeric:tabular-nums;text-align:right;">'
            f"{Validadores.html_escape(v)}</span></div>"
            for k, v in itens_dict.items()
        )
        itens_html = (
            f'<div style="border-top:1px solid {Cores.BORDA};padding-top:8px;'
            f'margin-top:4px;">{rows}</div>'
        )

    relogio_html = (
        f'<div style="font-size:9px;color:{Cores.TEXTO_3};text-align:center;'
        'margin-top:6px;letter-spacing:0.3px;">🕒 '
        f"{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}</div>"
        if mostrar_rel
        else ""
    )

    copy_final = copyright or f"© {ano} {empresa}"
    copy_html = (
        f'<div style="margin-top:10px;padding-top:8px;'
        f"border-top:1px solid {Cores.BORDA};font-size:9px;color:{Cores.TEXTO_3};"
        'text-align:center;line-height:1.5;letter-spacing:0.2px;">'
        f'<span style="color:{Cores.PRIMARIA};font-weight:600;">'
        f"{Validadores.html_escape(copy_final)}</span></div>"
    )

    markup = (
        '<div class="sidebar-footer">'
        f"{badges_row}{unidade_html}{itens_html}{relogio_html}{copy_html}"
        "</div>"
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
        avatar_html = (
            f'<img src="{Validadores.html_escape(avatar)}" alt="Avatar" '
            'style="width:42px;height:42px;border-radius:50%;object-fit:cover;'
            f'flex-shrink:0;border:2px solid {Cores.PRIMARIA}30;" />'
        )
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

        avatar_html = (
            '<div style="width:42px;height:42px;border-radius:50%;'
            f"background:linear-gradient(135deg,{Cores.PRIMARIA},{Cores.SECUNDARIA});"
            "display:flex;align-items:center;justify-content:center;"
            f"font-size:{mono_size};color:#FFFFFF;font-weight:800;flex-shrink:0;"
            "letter-spacing:0.5px;border:2px solid rgba(255,255,255,0.3);"
            'box-shadow:0 2px 8px rgba(1,40,105,0.25);">'
            f"{mono}</div>"
        )

    status_dot = ""
    status_label_html = ""
    if status and status in _STATUS_CFG:
        cor_s, label_s = _STATUS_CFG[status]
        status_dot = (
            f'<span style="position:absolute;bottom:1px;right:1px;width:11px;'
            f"height:11px;border-radius:50%;background:{cor_s};"
            f'border:2px solid #FFFFFF;box-shadow:0 0 0 1px {cor_s}40;"></span>'
        )
        status_label_html = (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f"font-size:9px;font-weight:700;color:{cor_s};text-transform:uppercase;"
            'letter-spacing:0.5px;margin-top:2px;">'
            f'<span style="width:5px;height:5px;border-radius:50%;'
            f'background:{cor_s};display:inline-block;"></span>{label_s}</span>'
        )

    user_section = ""
    if user_name or role or email or avatar:
        name_html = (
            f'<p style="margin:0;font-size:13px;font-weight:700;'
            f"color:{Cores.PRIMARIA};line-height:1.25;"
            'font-family:var(--font-titulo) !important;">'
            f"{Validadores.html_escape(user_name)}</p>"
            if user_name
            else ""
        )
        role_html = (
            f'<p style="margin:2px 0 0;font-size:10px;color:{Cores.SECUNDARIA};'
            "line-height:1.3;font-weight:600;text-transform:uppercase;"
            'letter-spacing:0.3px;">'
            f"{Validadores.html_escape(role)}</p>"
            if role
            else ""
        )
        email_html = (
            f'<p style="margin:2px 0 0;font-size:10px;color:{Cores.TEXTO_3};'
            'line-height:1.3;font-weight:500;">'
            f"{Validadores.html_escape(email)}</p>"
            if email
            else ""
        )
        user_section = (
            '<div style="display:flex;align-items:center;gap:12px;'
            'margin-bottom:4px;">'
            '<div style="position:relative;flex-shrink:0;">'
            f"{avatar_html}{status_dot}</div>"
            '<div style="min-width:0;flex:1;">'
            f"{name_html}{role_html}{email_html}{status_label_html}</div></div>"
        )

    itens_html = ""
    if itens_dict:
        sep = (
            '<div style="height:1px;background:linear-gradient(90deg,'
            f'{Cores.PRIMARIA}30,{Cores.SECUNDARIA}30);margin:10px 0 6px;"></div>'
            if user_section
            else ""
        )
        rows = "".join(
            '<div style="display:flex;align-items:center;gap:8px;padding:5px 0;">'
            '<span style="font-size:12px;line-height:1;flex-shrink:0;width:18px;'
            f'text-align:center;color:{Cores.SECUNDARIA};">'
            f"{Validadores.html_escape(icone)}</span>"
            f'<span style="font-size:11px;color:{Cores.TEXTO_3};font-weight:500;'
            'flex-shrink:0;">'
            f"{Validadores.html_escape(k)}</span>"
            f'<span style="font-size:11px;color:{Cores.PRIMARIA};font-weight:700;'
            'margin-left:auto;text-align:right;font-variant-numeric:tabular-nums;">'
            f"{Validadores.html_escape(v)}</span></div>"
            for k, v in itens_dict.items()
        )
        itens_html = f"{sep}<div>{rows}</div>"

    rodape_html = (
        f'<div style="margin-top:8px;padding-top:8px;'
        f"border-top:1px dashed {Cores.PRIMARIA}30;font-size:9px;"
        f'color:{Cores.TEXTO_3};line-height:1.4;letter-spacing:0.2px;">'
        f"{Validadores.html_escape(rodape)}</div>"
        if rodape
        else ""
    )

    titulo_html = (
        f'<div style="font-size:10px;font-weight:700;color:{Cores.PRIMARIA};'
        "text-transform:uppercase;letter-spacing:0.8px;margin:0 0 6px 2px;"
        f'border-left:3px solid {Cores.SECUNDARIA};padding-left:8px;">'
        f"{Validadores.html_escape(titulo)}</div>"
        if titulo
        else ""
    )

    if not user_section and not itens_html and not rodape_html:
        return

    markup = (
        f"{titulo_html}"
        '<div style="background:linear-gradient(160deg,#FFFFFF 0%,#F8FAFC 100%);'
        f"border:1px solid {Cores.BORDA};border-radius:12px;padding:14px;"
        "margin:8px 0 12px;box-shadow:0 1px 3px rgba(0,0,0,0.04);"
        f'border-left:3px solid {Cores.PRIMARIA};">'
        f"{user_section}{itens_html}{rodape_html}</div>"
    )
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
            f'<div style="height:{altura_css};width:100%;display:block;" '
            'aria-hidden="true"></div>'
        )


def render_sidebar_status(
    status: str = "Ativo",
    label: str = "STATUS DO SISTEMA",
    ultima_atualizacao: str = "",
    total_registros: int | str | None = None,
    detalhes: dict[str, Any] | None = None,
    tipo: Literal["ok", "info", "alerta", "critico"] = "ok",
    compacto: bool = False,
    container: Any = None,
    **kwargs: Any,
) -> None:
    """
    Renderiza um widget de status corporativo na sidebar.

    compacto=True  -> pílula inline.
    compacto=False -> card estruturado com indicador pulsante.
    """
    cfg_status = {
        "ok": {
            "cor": "#059669",
            "bg": "#ECFDF5",
            "borda": "#A7F3D0",
            "texto": "#065F46",
            "dot": "#10B981",
            "glow": "rgba(16, 185, 129, 0.4)",
        },
        "info": {
            "cor": "#0A48AA",
            "bg": "#EFF6FF",
            "borda": "#BFDBFE",
            "texto": "#1E40AF",
            "dot": "#3B82F6",
            "glow": "rgba(59, 130, 246, 0.4)",
        },
        "alerta": {
            "cor": "#D97706",
            "bg": "#FFFBEB",
            "borda": "#FDE68A",
            "texto": "#92400E",
            "dot": "#F59E0B",
            "glow": "rgba(245, 158, 11, 0.4)",
        },
        "critico": {
            "cor": "#DC2626",
            "bg": "#FEF2F2",
            "borda": "#FECACA",
            "texto": "#991B1B",
            "dot": "#EF4444",
            "glow": "rgba(239, 68, 68, 0.4)",
        },
    }

    c = cfg_status.get(tipo, cfg_status["ok"])
    status_esc = Validadores.html_escape(str(status).strip().title())
    label_esc = Validadores.html_escape(label.strip().upper())

    keyframes = f"""
    <style>
    @keyframes pulse-dot-{tipo} {{
        0% {{ box-shadow: 0 0 0 0 {c["glow"]}; transform: scale(1); }}
        70% {{ box-shadow: 0 0 0 6px rgba(0,0,0,0); transform: scale(1.08); }}
        100% {{ box-shadow: 0 0 0 0 rgba(0,0,0,0); transform: scale(1); }}
    }}
    </style>
    """

    if compacto or kwargs.get("badge_only", False):
        markup = f"""
        {keyframes}
        <div style="
            display: inline-flex;
            align-items: center;
            gap: 7px;
            background: {c["bg"]};
            border: 1px solid {c["borda"]};
            border-radius: 20px;
            padding: 4px 12px 4px 10px;
            font-family: var(--font-texto);
            font-size: 11px;
            font-weight: 700;
            color: {c["texto"]};
            letter-spacing: 0.4px;
            margin: 6px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        ">
            <span style="
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: {c["dot"]};
                display: inline-block;
                animation: pulse-dot-{tipo} 2s infinite ease-in-out;
            "></span>
            <span>{status_esc}</span>
        </div>
        """
        target = container if container is not None else st.sidebar
        _safe_render_html(markup, target)
        return

    detalhes_dict = detalhes or {}
    detalhes_html = "".join(f"""
        <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;">
            <span style="font-size:10.5px;color:{Cores.TEXTO_3};font-weight:500;">{Validadores.html_escape(k)}</span>
            <span style="font-size:10.5px;color:{Cores.PRIMARIA};font-weight:700;font-variant-numeric:tabular-nums;">{Validadores.html_escape(v)}</span>
        </div>
        """ for k, v in detalhes_dict.items())

    ultima_atualizacao_fmt = (
    formatar_datetime_exibicao(ultima_atualizacao)
    if ultima_atualizacao
    else ""
    )

    data_html = (
        f"""<div style="font-size:10px;color:{Cores.TEXTO_3};margin-top:6px;display:flex;align-items:center;gap:4px;">
            <span style="opacity:0.7;">🕒</span> Atualizado: {Validadores.html_escape(ultima_atualizacao_fmt)}
        </div>"""
        if ultima_atualizacao_fmt
        else ""
    )

    total_html = (
        f"""<div style="font-size:10.5px;color:{Cores.TEXTO_2};margin-top:4px;">
            Total monitorado: <strong style="color:{Cores.PRIMARIA};">{Validadores.html_escape(total_registros)}</strong>
        </div>"""
        if total_registros is not None
        else ""
    )

    divisor = (
        '<div style="height:1px;background:#E2E8F0;margin:8px 0 6px;"></div>'
        if (detalhes_html or data_html or total_html)
        else ""
    )

    markup = f"""
    {keyframes}
    <div style="
        background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
        border: 1px solid #E2E8F0;
        border-top: 3px solid {c["cor"]};
        border-radius: 10px;
        padding: 12px 14px;
        margin: 10px 0 14px 0;
        box-shadow: 0 2px 6px rgba(1, 40, 105, 0.05);
    ">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
            <span style="
                font-family: var(--font-titulo);
                font-size: 9.5px;
                font-weight: 800;
                color: {Cores.TEXTO_3};
                letter-spacing: 0.8px;
            ">{label_esc}</span>

            <div style="
                display: inline-flex;
                align-items: center;
                gap: 6px;
                background: {c["bg"]};
                border: 1px solid {c["borda"]};
                border-radius: 12px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
                color: {c["texto"]};
            ">
                <span style="
                    width: 7px;
                    height: 7px;
                    border-radius: 50%;
                    background: {c["dot"]};
                    display: inline-block;
                    animation: pulse-dot-{tipo} 2s infinite ease-in-out;
                "></span>
                {status_esc}
            </div>
        </div>

        {divisor}
        {total_html}
        {detalhes_html}
        {data_html}
    </div>
    """

    target = container if container is not None else st.sidebar
    _safe_render_html(markup, target)


# =============================================================================
# COMPONENTES HERO
# =============================================================================
def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    if not titulo:
        raise ValueError("render_hero: 'titulo' não pode ser vazio.")

    t = Validadores.html_escape(titulo)

    badge_html = ""
    if badge:
        badge_html = f'<span class="hero-badge">{Validadores.html_escape(badge)}</span>'

    sub_html = ""
    if subtitulo:
        sub_html = f'<p class="hero-subtitle">{Validadores.html_escape(subtitulo)}</p>'

    markup = (
        '<div class="hero-corp"><div class="hero-content">'
        f"{badge_html}"
        f'<h1 class="hero-title">{t}</h1>'
        f"{sub_html}"
        "</div></div>"
    )
    _safe_render_html(markup)


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
        '<div class="totale-badge-pill" '
        'style="background:rgba(255,255,255,0.15);color:#FFFFFF;'
        'border-color:rgba(255,255,255,0.25);">'
        f"<span>{Validadores.html_escape(icone)}</span> "
        f"{Validadores.html_escape(badge)}</div>"
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
        '<div class="totale-hero-1">'
        '<div style="position:relative;z-index:2;">'
        f'{b}<h1 class="th-title-lg">{t}</h1>{s}{m}'
        "</div></div>"
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
        '<div class="totale-hero-2-card">'
        f'<div class="th-card-label">{Validadores.html_escape(label_destaque)}</div>'
        f'<div class="th-card-value">{Validadores.html_escape(valor_destaque)}</div>'
        "</div>"
        if valor_destaque
        else ""
    )

    _safe_render_html(
        '<div class="totale-hero-2">'
        f'<div>{b}{tag}<h1 class="th-title">{t}</h1>{s}</div>{card}'
        "</div>"
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

    badge_html = ""
    if badge:
        ic = Validadores.html_escape(icone)
        bd = Validadores.html_escape(badge)
        badge_html = (
            '<div style="display:inline-flex;align-items:center;gap:6px;'
            "background:rgba(255,255,255,0.15);padding:4px 12px;border-radius:20px;"
            "font-size:11px;font-weight:700;text-transform:uppercase;"
            'letter-spacing:0.5px;color:#FFFFFF;">'
            f"<span>{ic}</span> {bd}"
            "</div>"
        )

    sub_html = ""
    if subtitulo:
        sub_html = (
            '<p style="font-size:14px;color:rgba(255,255,255,0.80);'
            'margin:0;line-height:1.5;">'
            f"{Validadores.html_escape(subtitulo)}"
            "</p>"
        )

    stats_html = ""
    if stats:
        cards: list[str] = []
        for item in list(stats)[:4]:
            valor_txt = Validadores.html_escape(item.get("valor", ""))
            label_txt = Validadores.html_escape(item.get("label", ""))
            cards.append(
                '<div style="background:rgba(255,255,255,0.12);'
                "-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);"
                "border:1px solid rgba(255,255,255,0.20);border-radius:10px;"
                'padding:12px 16px;text-align:center;">'
                '<strong style="font-size:20px;font-weight:900;color:#F37C04;'
                'display:block;line-height:1;">'
                f"{valor_txt}"
                "</strong>"
                '<span style="font-size:10px;font-weight:600;'
                "text-transform:uppercase;letter-spacing:0.5px;"
                'color:rgba(255,255,255,0.80);">'
                f"{label_txt}"
                "</span></div>"
            )
        stats_html = (
            '<div style="display:grid;'
            "grid-template-columns:repeat(auto-fit,minmax(100px,1fr));"
            'gap:12px;margin-top:16px;">'
            f"{''.join(cards)}"
            "</div>"
        )

    markup = (
        '<div class="hero-migracao"><div style="position:relative;z-index:2;">'
        f"{badge_html}"
        '<h1 style="font-size:clamp(22px,2.5vw,32px);font-weight:900;'
        'color:#FFFFFF;margin:12px 0 8px;line-height:1.15;">'
        f"{t}</h1>"
        f"{sub_html}{stats_html}"
        "</div></div>"
    )
    _safe_render_html(markup)


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

    badge_html = ""
    if badge:
        ic = Validadores.html_escape(icone)
        bd = Validadores.html_escape(badge)
        badge_html = (
            '<div style="display:inline-flex;align-items:center;gap:6px;'
            "background:rgba(255,255,255,0.15);padding:4px 12px;border-radius:20px;"
            "font-size:11px;font-weight:700;text-transform:uppercase;"
            'letter-spacing:0.5px;color:#FFFFFF;">'
            f"<span>{ic}</span> {bd}"
            "</div>"
        )

    sub_html = ""
    if subtitulo:
        sub_html = (
            '<p style="font-size:14px;color:rgba(255,255,255,0.80);'
            'margin:0;line-height:1.5;">'
            f"{Validadores.html_escape(subtitulo)}"
            "</p>"
        )

    feat_html = ""
    if features:
        pills: list[str] = []
        for feature in list(features)[:5]:
            pills.append(
                '<span style="background:rgba(255,255,255,0.10);'
                "-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);"
                "border:1px solid rgba(255,255,255,0.20);border-radius:20px;"
                'padding:6px 14px;font-size:11px;font-weight:600;color:#FFFFFF;">'
                f"✓ {Validadores.html_escape(feature)}"
                "</span>"
            )
        feat_html = (
            '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;">'
            f"{''.join(pills)}"
            "</div>"
        )

    markup = (
        '<div class="hero-pme"><div style="position:relative;z-index:2;">'
        f"{badge_html}"
        '<h1 style="font-size:clamp(22px,2.5vw,32px);font-weight:900;'
        'color:#FFFFFF;margin:12px 0 8px;line-height:1.15;">'
        f"{t}</h1>"
        f"{sub_html}{feat_html}"
        "</div></div>"
    )
    _safe_render_html(markup)


def render_hero_novos_domicilios(
    titulo: str,
    subtitulo: str = "",
    badge: str = "NOVOS DOMICÍLIOS",
    icone: str = "🏠",
    stats: Sequence[dict[str, str]] | None = None,
    meta_info: str = "",
) -> None:
    """
    Hero corporativo para análise de novos domicílios.

    Gradiente: azul institucional -> azul-petróleo -> teal.
    O badge recebe apenas texto curto; a frase longa vai no subtítulo.
    """
    if not titulo:
        raise ValueError("render_hero_novos_domicilios: 'titulo' não pode ser vazio.")

    t = Validadores.html_escape(titulo)

    badge_html = ""
    if badge:
        ic = Validadores.html_escape(icone)
        bd = Validadores.html_escape(badge)
        badge_html = (
            '<div style="display:inline-flex;align-items:center;gap:6px;'
            "background:rgba(255,255,255,0.15);-webkit-backdrop-filter:blur(8px);"
            "backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,0.22);"
            "border-radius:20px;padding:4px 14px;font-size:11px;font-weight:700;"
            "text-transform:uppercase;letter-spacing:0.5px;color:#FFFFFF;"
            'margin-bottom:8px;">'
            f"<span>{ic}</span> {bd}"
            "</div>"
        )

    sub_html = ""
    if subtitulo:
        sub_html = (
            '<p style="font-size:14px;color:rgba(255,255,255,0.85);'
            'margin:0;line-height:1.5;">'
            f"{Validadores.html_escape(subtitulo)}"
            "</p>"
        )

    stats_html = ""
    if stats:
        cards: list[str] = []
        for item in list(stats)[:4]:
            valor_txt = Validadores.html_escape(item.get("valor", ""))
            label_txt = Validadores.html_escape(item.get("label", ""))
            cards.append(
                '<div style="background:rgba(255,255,255,0.12);'
                "-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);"
                "border:1px solid rgba(255,255,255,0.20);border-radius:10px;"
                'padding:12px 16px;text-align:center;">'
                '<strong style="font-size:20px;font-weight:900;color:#4ADE80;'
                'display:block;line-height:1;">'
                f"{valor_txt}"
                "</strong>"
                '<span style="font-size:10px;font-weight:600;'
                "text-transform:uppercase;letter-spacing:0.5px;"
                'color:rgba(255,255,255,0.80);">'
                f"{label_txt}"
                "</span></div>"
            )
        stats_html = (
            '<div style="display:grid;'
            "grid-template-columns:repeat(auto-fit,minmax(110px,1fr));"
            'gap:12px;margin-top:16px;">'
            f"{''.join(cards)}"
            "</div>"
        )

    meta_html = ""
    if meta_info:
        meta_html = (
            '<div style="font-size:11px;color:rgba(255,255,255,0.60);'
            'margin-top:10px;font-weight:500;">'
            f"{Validadores.html_escape(meta_info)}"
            "</div>"
        )

    markup = (
        '<div class="hero-domicilios"><div style="position:relative;z-index:2;">'
        f"{badge_html}"
        '<h1 style="font-family:var(--font-titulo);'
        "font-size:clamp(22px,2.5vw,32px);font-weight:900;color:#FFFFFF;"
        'margin:4px 0 6px;line-height:1.15;letter-spacing:-0.5px;">'
        f"{t}</h1>"
        f"{sub_html}{stats_html}{meta_html}"
        "</div></div>"
    )
    _safe_render_html(markup)


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
    """
    Cabeçalho de seção.

    Uso recomendado:
        render_section_header(
            titulo="Base de dados",
            icone="📊",
            badge="PRIMEIROS 50 REGISTROS",
        )

    Compatibilidade:
        Reconhece a chamada antiga (emoji, titulo) quando
        o primeiro argumento contém somente emoji/símbolo
        e o segundo contém texto.
    """
    titulo_final = str(titulo or title or "").strip()
    icone_final = str(icone or icon or "").strip()
    badge_final = str(badge or "").strip()
    subtitulo_final = str(subtitulo or "").strip()

    # ---------------------------------------------------------
    # Compatibilidade com chamadas antigas: (icone, titulo).
    # Não troca argumentos quando o título já contém texto.
    # ---------------------------------------------------------
    titulo_eh_icone = (
        bool(titulo_final)
        and not any(caractere.isalnum() for caractere in titulo_final)
        and any(
            unicodedata.category(caractere).startswith("S")
            for caractere in titulo_final
        )
    )

    icone_contem_texto = any(
        caractere.isalpha() for caractere in icone_final
    )

    if titulo_eh_icone and icone_contem_texto:
        titulo_final, icone_final = icone_final, titulo_final

        logger.warning(
            "render_section_header recebeu ícone e título invertidos. "
            "Use titulo=... e icone=... nas chamadas."
        )

    if not any(
        (titulo_final, icone_final, badge_final, subtitulo_final)
    ):
        return

    tipo_norm = normalizar_tipo_badge(badge_tipo)
    bg_badge, cor_badge, borda_badge = ConfigCores.BADGE[tipo_norm]

    # Ícone: somente o ícone ocupa o tile.
    icone_html = ""
    if icone_final:
        icone_html = f"""
        <span
            class="totale-icon-tile totale-icon-tile--section"
            aria-hidden="true"
        >
            <span class="totale-icon-glyph">
                {Validadores.html_escape(icone_final)}
            </span>
        </span>
        """

    # Título: fica fora do tile, com largura disponível.
    titulo_html = ""
    if titulo_final:
        titulo_html = f"""
        <h2
            class="section-title"
            style="min-width:0;overflow-wrap:anywhere;"
        >
            {Validadores.html_escape(titulo_final)}
        </h2>
        """

    badge_html = ""
    if badge_final:
        badge_html = f"""
        <span style="
            display:inline-flex;
            align-items:center;
            background:{bg_badge};
            color:{cor_badge};
            border:1px solid {borda_badge};
            padding:4px 12px;
            border-radius:999px;
            font-size:10px;
            font-weight:700;
            text-transform:uppercase;
            letter-spacing:0.5px;
            max-width:100%;
            overflow-wrap:anywhere;
        ">
            {Validadores.html_escape(badge_final)}
        </span>
        """

    subtitulo_html = ""
    if subtitulo_final:
        subtitulo_html = f"""
        <p class="section-subtitle">
            {Validadores.html_escape(subtitulo_final)}
        </p>
        """

    markup = f"""
    <div
        class="section-header"
        style="
            border-bottom:3px solid {Cores.PRIMARIA};
            border-image:linear-gradient(
                90deg,
                {Cores.PRIMARIA},
                {Cores.SECUNDARIA}
            ) 1;
        "
    >
        {icone_html}

        <div class="section-header-copy">
            <div style="
                display:flex;
                align-items:center;
                gap:12px;
                flex-wrap:wrap;
                min-width:0;
            ">
                {titulo_html}
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
    tema: TemaKPIType = "azul",
    icone: str = "",
    delta: str = "",
    delta_tipo: TipoTrendType = "none",
    colorida: bool = True,
    compacto: bool = False,
) -> None:
    tema_norm = normalizar_tema_kpi(tema)
    cor_inicio, cor_fim = _resolver_gradiente(tema_norm)

    usar_cor = colorida or tema_norm == "gradiente"

    if usar_cor:
        fundo = f"linear-gradient(135deg, {cor_inicio} 0%, {cor_fim} 100%)"
        cor_texto = Cores.PRIMARIA if tema_norm == "laranja" else "#FFFFFF"
        cor_borda = "rgba(255,255,255,0.22)"
        fundo_icone = "rgba(255,255,255,0.20)"
    else:
        fundo = "#FFFFFF"
        cor_texto = Cores.TEXTO
        cor_borda = Cores.BORDA
        fundo_icone = f"{cor_inicio}15"

    label_esc = Validadores.html_escape(label)
    valor_esc = Validadores.html_escape(valor)
    sub_esc = Validadores.html_escape(sub)

    padding = "14px 16px" if compacto else "20px 24px"
    altura_minima = "100px" if compacto else "150px"
    tamanho_valor = "22px" if compacto else "32px"

    estilo_card = (
        f"background:{fundo};"
        f"color:{cor_texto} !important;"
        f"--cor-texto:{cor_texto};"
        f"--cor-texto-2:{cor_texto};"
        f"--cor-texto-3:{cor_texto};"
        f"border:1px solid {cor_borda};"
        f"padding:{padding};"
        f"min-height:{altura_minima};"
    )

    icone_html = ""
    if icone:
        icone_html = (
            '<div class="kpi-icon-wrapper" '
            f'style="background:{fundo_icone};color:{cor_texto};">'
            '<span aria-hidden="true" style="font-size:20px;line-height:1;">'
            f"{Validadores.html_escape(icone)}"
            "</span></div>"
        )

    delta_html = ""
    if delta:
        trend_norm = normalizar_tipo_trend(delta_tipo)
        seta = ConfigCores.TREND_ICONS.get(trend_norm, "")

        classe_delta = "trend-pill"
        if trend_norm != "none":
            classe_delta += f" trend-{trend_norm}"

        delta_html = (
            f'<span class="{classe_delta}">'
            f'<span aria-hidden="true">{seta}</span>'
            f"{Validadores.html_escape(delta)}"
            "</span>"
        )

    sub_html = ""
    if sub or delta:
        sub_html = f'<div class="kpi-sub-premium">{delta_html}{sub_esc}</div>'

    markup = f"""
    <div
        class="card-premium"
        style="{estilo_card}"
        role="region"
        aria-label="{label_esc}: {valor_esc}"
    >
        <div class="card-accent-top" style="background:{cor_inicio};"></div>

        <div class="card-header-flex">
            <div class="kpi-label-premium" style="color:{cor_texto} !important;">{label_esc}</div>
            {icone_html}
        </div>

        <div>
            <div
                class="kpi-value-premium"
                style="font-size:{tamanho_valor};color:{cor_texto} !important;"
            >{valor_esc}</div>
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
    colorida: bool = True,
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
        colorida=colorida,
    )


def render_metric_card(
    col: Any,
    label: str,
    valor: str,
    trend: TipoTrendType = "none",
    trend_valor: str = "",
    sub: str = "",
    colorida: bool = True,
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
        colorida=colorida,
    )


def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPIType = "azul",
    icone: str = "",
) -> None:
    """Card KPI compacto, usando o mesmo padrão visual do card premium."""
    _card_premium(
        container=container,
        label=label,
        valor=valor,
        sub=sub,
        tema=tema,
        icone=icone,
        colorida=True,
        compacto=True,
    )


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

    markup = (
        f'<div class="totale-insight" style="background:{bg};color:{texto};'
        f'border-left:4px solid {borda};">'
        '<div style="display:flex;align-items:flex-start;gap:10px;">'
        f'<span style="font-size:18px;line-height:1.2;">{icone}</span>'
        f'<div style="flex:1;">{titulo_html}<div>{msg_html}</div></div>'
        "</div></div>"
    )
    _safe_render_html(markup)


def render_notification(
    mensagem: str,
    tipo: TipoNotificationType = "info",
    titulo: str = "",
    container: Any = None,
) -> None:
    if not mensagem:
        return

    tipo_norm = normalizar_tipo(tipo, {"sucesso", "info", "alerta", "erro"}, "info")
    bg, fg, borda, icone = ConfigCores.NOTIFICATION.get(
        tipo_norm, ConfigCores.NOTIFICATION["info"]
    )
    titulo_html = (
        '<strong style="display:block;margin-bottom:3px;font-size:13px;">'
        f"{Validadores.html_escape(titulo)}</strong>"
        if titulo
        else ""
    )

    markup = (
        f'<div role="status" style="background:{bg};color:{fg};'
        f"border:1px solid {borda};border-radius:10px;padding:13px 16px;"
        "margin:12px 0;display:flex;align-items:flex-start;gap:10px;"
        'box-shadow:0 1px 3px rgba(15,23,42,0.05);">'
        f'<span style="font-size:18px;line-height:1.2;">{icone}</span>'
        f'<div style="font-size:13px;line-height:1.5;">'
        f"{titulo_html}{Formatadores.markdown_para_html(mensagem)}</div>"
        "</div>"
    )
    _safe_render_html(markup, container)


def render_empty_state(
    tipo: TipoEmptyStateType = "padrao",
    titulo: str = "",
    descricao: str = "",
    acao: str = "",
    icone: str = "",
) -> None:
    bg_estado, cor_estado, icone_default, titulo_default = ConfigCores.EMPTY_STATE.get(
        tipo, ConfigCores.EMPTY_STATE["padrao"]
    )
    desc_html = (
        f'<p class="empty-state-desc">{Validadores.html_escape(descricao)}</p>'
        if descricao
        else ""
    )
    acao_html = (
        f'<p style="margin:12px 0 0 0;font-size:13px;color:{Cores.SECUNDARIA};'
        f'font-weight:600;">{Validadores.html_escape(acao)}</p>'
        if acao
        else ""
    )

    markup = (
        f'<div class="empty-state" style="background:{bg_estado};'
        f'border-color:{cor_estado}30;">'
        f'<span class="empty-state-icon">'
        f"{Validadores.html_escape(icone or icone_default)}</span>"
        f'<h3 class="empty-state-title" style="color:{cor_estado};">'
        f"{Validadores.html_escape(titulo or titulo_default)}</h3>"
        f"{desc_html}{acao_html}</div>"
    )
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

    if tema_norm == "azul":
        bg_style = f"linear-gradient(90deg, {Cores.PRIMARIA}, {Cores.PRIMARIA_LIGHT})"
    elif tema_norm == "laranja":
        bg_style = (
            f"linear-gradient(90deg, {Cores.SECUNDARIA_DARK}, {Cores.SECUNDARIA})"
        )

    header_html = ""
    if label or mostrar_valor:
        lbl = (
            f'<span style="font-size:13px;font-weight:600;color:{Cores.TEXTO_2};">'
            f"{Validadores.html_escape(label)}</span>"
            if label
            else "<span></span>"
        )
        val = (
            f'<span style="font-size:14px;font-weight:800;color:{Cores.PRIMARIA};'
            'font-family:var(--font-titulo);font-variant-numeric:tabular-nums;">'
            f"{porcentagem:.1f}{unidade}</span>"
            if mostrar_valor
            else ""
        )
        header_html = (
            '<div style="display:flex;justify-content:space-between;'
            f'align-items:flex-end;margin-bottom:8px;">{lbl}{val}</div>'
        )

    classe_anim = "totale-pb-fill animado" if animado else "totale-pb-fill"

    markup = (
        f'<div style="margin:14px 0;" role="progressbar" aria-valuemin="0" '
        f'aria-valuemax="100" aria-valuenow="{porcentagem:.1f}">'
        f"{header_html}"
        '<div style="width:100%;background:#E2E8F0;border-radius:999px;'
        f'overflow:hidden;height:{altura_px};">'
        f'<div class="{classe_anim}" style="width:{porcentagem:.4f}%;height:100%;'
        f"background:{bg_style};border-radius:999px;"
        'transition:width 0.6s ease-out;"></div>'
        "</div></div>"
    )
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

    def formatar_data_limpa(valor_raw: Any) -> str:
        s = str(valor_raw).strip()
        match_datetime = re.match(
            r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})", s
        )
        match_date = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)

        if match_datetime:
            ano, mes, dia, h, m, _ = match_datetime.groups()
            if h == "00" and m == "00":
                return f"{dia}/{mes}/{ano}"
            return f"{dia}/{mes}/{ano} {h}:{m}"
        if match_date:
            ano, mes, dia = match_date.groups()
            return f"{dia}/{mes}/{ano}"
        return s

    th_parts = [
        f'<th style="text-align:{alinhamentos.get(col, "left")};">'
        f"{Validadores.html_escape(str(col))}</th>"
        for col in df_display.columns
    ]
    th_html = "".join(th_parts)

    tr_parts: list[str] = []
    for i, (_, row) in enumerate(df_display.iterrows()):
        td_parts: list[str] = []
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
                val_str = formatar_data_limpa(val)

                if fmt and col in fmt and fmt[col] is not None:
                    formatter = fmt[col]
                    if isinstance(formatter, str):
                        try:
                            val_str = formatter.format(val)
                        except Exception:
                            pass
                    elif callable(formatter):
                        try:
                            val_str = formatter(val)
                        except Exception:
                            pass
                    val_str = Validadores.html_escape(val_str)
                else:
                    val_str = Validadores.html_escape(val_str)

            val_clean_upper = normalizar_texto_badge(val_str)
            if val_clean_upper in (
                "NAO",
                "INATIVO",
                "CANCELADO",
                "REPROVADO",
                "DEVOLVIDO",
                "DEVOLVIDA",
            ):
                val_str = f'<span class="td-badge-alerta">{val_str}</span>'
            elif val_clean_upper in ("SIM", "ATIVO", "CONCLUIDO", "APROVADO"):
                val_str = f'<span class="td-badge-ok">{val_str}</span>'
            elif val_clean_upper in (
                "PROCESSO",
                "PENDENTE",
                "AGENDADO",
                "EM ANDAMENTO",
            ):
                val_str = f'<span class="td-badge-neutro">{val_str}</span>'

            if color_rules and col in color_rules:
                regras = color_rules[col]
                if isinstance(regras, dict):
                    classe_cor = regras.get(str(val), "")
                    if classe_cor in ("positive", "sucesso"):
                        val_str = f'<span class="td-badge-ok">{val_str}</span>'
                    elif classe_cor in ("negative", "alerta"):
                        val_str = f'<span class="td-badge-alerta">{val_str}</span>'

            font_style = (
                "font-variant-numeric: tabular-nums; "
                "font-family: var(--font-codigo) !important; font-size: 11.5px;"
                if align == "right"
                or any(char.isdigit() for char in val_str if char not in ".,-")
                else ""
            )
            td_parts.append(
                f'<td style="text-align:{align}; {font_style}">{val_str}</td>'
            )

        classe_linha: list[str] = []
        if eh_destaque:
            classe_linha.append("linha-destaque")
        elif striped and i % 2 == 1:
            classe_linha.append("striped")

        classe_attr = f' class="{" ".join(classe_linha)}"' if classe_linha else ""
        tr_parts.append(f"<tr{classe_attr}>{''.join(td_parts)}</tr>")

    titulo_html = (
        f'<div style="font-weight:800;font-size:16px;color:{Cores.PRIMARIA};'
        "margin-bottom:12px;font-family:var(--font-titulo) !important;"
        f'border-left:4px solid {Cores.SECUNDARIA};padding-left:12px;">'
        f"{Validadores.html_escape(titulo)}</div>"
        if titulo
        else ""
    )
    caption_html = (
        '<div style="font-size:11px;color:#94A3B8;margin-top:8px;'
        f'font-weight:500;">{Validadores.html_escape(caption)}</div>'
        if caption
        else ""
    )
    data_html = (
        '<div style="font-size:11px;color:#94A3B8;margin-top:8px;'
        'text-align:right;font-weight:500;">Atualizado em: '
        f"{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')}</div>"
        if mostrar_data
        else ""
    )
    height_style = f"max-height:{height}px;" if height else ""

    markup = (
        '<div style="margin: 24px 0;">'
        f"{titulo_html}"
        '<div class="table-premium-wrapper">'
        f'<div class="table-premium-scroll" style="{height_style}">'
        '<table class="totale-table-pro">'
        f"<thead><tr>{th_html}</tr></thead>"
        f"<tbody>{''.join(tr_parts)}</tbody>"
        "</table></div></div>"
        f"{caption_html}{data_html}</div>"
    )
    _safe_render_html(markup)

    if exportar_excel and not df_display.empty:
        buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_display.to_excel(writer, index=False, sheet_name="Dados")
            _, c2 = st.columns([4, 1])
            with c2:
                st.download_button(
                    label="📥 Baixar Excel",
                    data=buffer.getvalue(),
                    file_name=(
                        f"{nome_arquivo}_"
                        f"{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    use_container_width=True,
                    help="Exportar relatório atual",
                )
        except Exception as exc:
            logger.error("Falha na exportação de planilha: %s", exc)


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
    chave_cor = "info" if tipo_norm == "default" else tipo_norm
    bg, fg, borda = ConfigCores.BADGE[chave_cor]

    titulo_esc = Validadores.html_escape(titulo)
    corpo_html = Formatadores.markdown_para_html(corpo)

    icone_html = ""
    if icone:
        icone_html = (
            '<span aria-hidden="true" '
            'style="font-size:24px;line-height:1;flex-shrink:0;">'
            f"{Validadores.html_escape(icone)}"
            "</span>"
        )

    markup = f"""
    <div
        class="card-premium"
        role="region"
        aria-label="{titulo_esc}"
        style="background:{bg};color:{fg};border-color:{borda};"
    >
        <div class="card-accent-top" style="background:{borda};"></div>

        <div style="display:flex;align-items:flex-start;gap:12px;">
            {icone_html}
            <div style="flex:1;min-width:0;">
                <div style="
                    font-family:var(--font-titulo);
                    font-size:15px;
                    font-weight:800;
                    color:{fg};
                    margin-bottom:6px;
                ">{titulo_esc}</div>

                <div style="font-size:13px;color:{fg};line-height:1.6;">
                    {corpo_html}
                </div>
            </div>
        </div>
    </div>
    """

    _safe_render_html(markup, container)


def render_spacer(altura: int | str = 16) -> None:
    css = f"{altura}px" if isinstance(altura, int) else str(altura)
    _safe_render_html(
        f'<div style="height:{css};width:100%;display:block;" aria-hidden="true"></div>'
    )


def render_badge(
    texto: str,
    tipo: TipoBadgeType = "default",
    icone: str = "",
    container: Any = None,
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

    markup = (
        f'<span class="totale-badge-pill" style="background:{bg};color:{fg};'
        f'border-color:{borda};">{icone_html}'
        f"{Validadores.html_escape(texto)}</span>"
    )
    _safe_render_html(markup, container)


def render_skeleton(
    linhas: int = 3, altura_linha: int = 16, largura_ultima: str = "60%"
) -> None:
    linhas = max(1, int(linhas))
    rows: list[str] = []
    for i in range(linhas):
        largura = largura_ultima if i == linhas - 1 else "100%"
        rows.append(
            f'<div class="totale-skeleton" style="height:{altura_linha}px;'
            f'width:{largura};margin-bottom:10px;"></div>'
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
    "render_hero_novos_domicilios",
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
    "normalizar_texto_badge",
    "formatar_numero_br",
    "formatar_datetime_exibicao",
    "normalizar_tipo",
    "normalizar_texto_badge",
]
