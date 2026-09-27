"""
components/componentes.py
=========================
Design System Streamlit — TOTALE

Versão: 5.0.0 (Refinamento Visual Enterprise)
Autor: TOTALE Tecnologia

Evoluções desta versão (100% retrocompatível — mesmas funções e assinaturas):
• Novo sistema de tokens (escala de cinzas "ink", bordas, sombras em camadas, raios).
• Heros mais sóbrios: gradientes profundos, malha sutil e brilho de canto (sem
  animação de cor), pills translúcidas e cartões de estatística em vidro.
• KPIs redesenhados: variante sólida (colorida=True) com brilho e anel
  decorativo; variante clara (colorida=False) com faixa de acento e ícone tintado.
• Section header com ícone em "chip", linha fina e acento laranja curto.
• Insights/notificações, empty state, progresso e cards com visual unificado.
• Tabela premium com cabeçalho fixo (sticky), badges com indicador e números
  tabulares (sem fonte monoespaçada).
• Polimento de widgets nativos do Streamlit (abas, botões, expanders, métricas,
  inputs, dataframes e gráficos Plotly).
• Remoção do override automático de modo escuro que deixava textos claros
  sobre cartões brancos.

Histórico 4.7.1:
• Correção de layout quebrado quando textos longos eram passados no tile de ícone.
• Lógica inteligente reforçada para inverter posições de Título e Ícone se passados na ordem errada.
• CSS do glyph atualizado para suportar Material Symbols nativamente sem imprimir o texto.
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
        "azul": ("#011E52", "#0A48AA"),
        "laranja": ("#C2410C", "#F37C04"),
        "verde": ("#064E3B", "#059669"),
        "vermelho": ("#7F1D1D", "#DC2626"),
        "roxo": ("#4C1D95", "#7C3AED"),
        "cinza": ("#334155", "#64748B"),
        "gradiente": ("#012869", "#D96500"),
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
        "sucesso": ("#F0FDF7", "#065F46", "#059669", "✅"),
        "info": ("#F2F7FF", "#1E40AF", "#3B82F6", "ℹ️"),
        "alerta": ("#FFFAEB", "#92400E", "#F59E0B", "⚠️"),
        "erro": ("#FEF4F4", "#991B1B", "#DC2626", "❌"),
    }

    TIMELINE: dict[str, tuple[str, str, str]] = {
        "concluido": (Cores.SUCESSO, "#D1FAE5", "✓"),
        "em_andamento": (Cores.SECUNDARIA, "#FEF3C7", "⏳"),
        "pendente": (Cores.NEUTRO, "#F3F4F6", "○"),
        "cancelado": (Cores.ALERTA, "#FEE2E2", "✕"),
    }

    INSIGHT: dict[str, tuple[str, str, str, str]] = {
        "ok": ("#F0FDF7", "#065F46", "#059669", "✅"),
        "info": ("#F2F7FF", "#1E40AF", "#3B82F6", "ℹ️"),
        "alerta": ("#FFFAEB", "#92400E", "#F59E0B", "⚠️"),
        "critico": ("#FEF4F4", "#991B1B", "#DC2626", "🚨"),
        "acao": ("#F7F5FF", "#5B21B6", "#8B5CF6", "💡"),
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


def _hex_to_rgba(cor: str, alpha: float) -> str:
    """
    Converte '#RRGGBB' (ou '#RGB') em 'rgba(r,g,b,a)'.
    Valores fora do padrão hexadecimal são devolvidos sem alteração.
    """
    txt = str(cor or "").strip()
    if not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", txt):
        return txt
    h = txt[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    a = max(0.0, min(1.0, float(alpha)))
    return f"rgba({r},{g},{b},{a:g})"


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
    _PANDAS_SUPORTA_MIXED = tuple(int(p) for p in pd.__version__.split(".")[:2]) >= (
        2,
        0,
    )
except ValueError:
    _PANDAS_SUPORTA_MIXED = False


def converter_data_br(serie: pd.Series) -> pd.Series:
    """
    Converte uma coluna para datetime lendo sempre DIA/MÊS/ANO.
    """
    if serie is None or len(serie) == 0:
        return pd.Series(dtype="datetime64[ns]")

    if pd.api.types.is_datetime64_any_dtype(serie):
        return pd.to_datetime(serie, errors="coerce")

    resultado = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")

    try:
        numericos = pd.to_numeric(serie, errors="coerce")
    except (TypeError, ValueError):
        numericos = pd.Series(np.nan, index=serie.index)
    mask_serial = numericos.between(20_000, 80_000)  # ~1954 a ~2119
    if mask_serial.any():
        resultado.loc[mask_serial] = pd.to_datetime(
            numericos[mask_serial], unit="D", origin="1899-12-30", errors="coerce"
        )

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
    Constrói um tile de ícone corporativo com trava de segurança para textos longos.
    """
    texto = str(icone or "").strip()
    if not texto:
        return ""

    # Trava de segurança: impede vazamento visual se passarem texto para o parâmetro do ícone
    if len(texto) > 15 and " " in texto:
        texto = texto[0]

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
# Todas as regras abaixo são escopadas por classes do Design System para não
# conflitar com o CSS nativo do Streamlit. Títulos (h1/h2/h3) recebem resets
# explícitos porque o Streamlit aplica estilos próprios aos headings do
# markdown (padding, font-size e ícone de âncora).
# -----------------------------------------------------------------------------
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

    --ink-900: #0B1324;
    --ink-800: #111C33;
    --ink-700: #1E293B;
    --ink-600: #334155;
    --ink-500: #475569;
    --ink-400: #64748B;
    --ink-300: #94A3B8;
    --line: #E5E9F0;
    --line-soft: #EEF1F6;
    --line-strong: #D3DAE5;
    --surface: #FFFFFF;
    --surface-2: #F8FAFC;
    --app-bg: #F4F6FA;

    --radius-xs: 6px; --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px; --radius-xl: 20px;
    --shadow-xs: 0 1px 2px rgba(16,24,40,0.05);
    --shadow-sm: 0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06);
    --shadow-md: 0 2px 4px -2px rgba(16,24,40,0.06), 0 6px 12px -4px rgba(16,24,40,0.08);
    --shadow-lg: 0 4px 6px -4px rgba(16,24,40,0.05), 0 18px 32px -12px rgba(16,24,40,0.16);
    --ring-focus: 0 0 0 3px rgba(10,72,170,0.16);
    --ease: cubic-bezier(0.4, 0, 0.2, 1);
}}
"""

_CSS_RESET_GLOBAL = """
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stSidebar"], p, label, div, li, a, button, input, select, textarea { font-family: var(--font-texto) !important; }
html, body, .stApp { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: optimizeLegibility; }
h1, h2, h3, h4, h5, h6, .hero-title, .section-title, .kpi-value, .metric-value, [data-testid="stMetricValue"] { font-family: var(--font-titulo) !important; font-weight: 700; letter-spacing: -0.02em; }
h1, .hero-title { font-weight: 800; letter-spacing: -0.025em; }
.main .block-container { padding-top: 1rem; max-width: 1400px; }
::selection { background: rgba(243,124,4,0.22); }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 999px; border: 3px solid transparent; background-clip: content-box; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; border: 3px solid transparent; background-clip: content-box; }
*:focus-visible { outline: 2px solid #0A48AA; outline-offset: 2px; border-radius: 4px; }

/* Remove âncoras/padding que o Streamlit injeta nos headings dos componentes */
.section-header [data-testid="stHeaderActionElements"],
.hero-corp [data-testid="stHeaderActionElements"],
.totale-hero-1 [data-testid="stHeaderActionElements"],
.totale-hero-2 [data-testid="stHeaderActionElements"],
.hero-migracao [data-testid="stHeaderActionElements"],
.hero-pme [data-testid="stHeaderActionElements"],
.hero-domicilios [data-testid="stHeaderActionElements"],
.empty-state [data-testid="stHeaderActionElements"],
.sidebar-brand [data-testid="stHeaderActionElements"] { display: none !important; }
.section-header h2, .hero-corp h1, .totale-hero-1 h1, .totale-hero-2 h1,
.hero-migracao h1, .hero-pme h1, .hero-domicilios h1, .empty-state h3, .sidebar-brand h2 { padding: 0 !important; }

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important; }
}
"""

_CSS_STREAMLIT_NATIVO = """
/* ====================== WIDGETS NATIVOS DO STREAMLIT ====================== */
/* Abas */
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 2px; }
[data-testid="stTabs"] [data-baseweb="tab"] { height: 44px; padding: 0 16px; border-radius: 10px 10px 0 0; background: transparent; color: var(--ink-500); transition: color .18s var(--ease), background .18s var(--ease); }
[data-testid="stTabs"] [data-baseweb="tab"] p { font-size: 14px; font-weight: 600; }
[data-testid="stTabs"] [data-baseweb="tab"]:hover { color: var(--cor-primaria); background: rgba(1,40,105,0.045); }
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] { color: var(--cor-primaria); }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--cor-secundaria) !important; height: 3px !important; border-radius: 3px 3px 0 0; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { background: var(--line) !important; }

/* Botões */
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"],
.stButton > button, [data-testid="stDownloadButton"] > button, [data-testid="stFormSubmitButton"] > button {
    border-radius: 10px !important; font-weight: 600 !important; min-height: 40px;
    transition: transform .18s var(--ease), box-shadow .18s var(--ease), border-color .18s var(--ease), color .18s var(--ease), filter .18s var(--ease) !important;
}
[data-testid="stBaseButton-secondary"] { background: #FFFFFF !important; border: 1px solid var(--line-strong) !important; color: var(--ink-700) !important; box-shadow: var(--shadow-xs); }
[data-testid="stBaseButton-secondary"]:hover { border-color: var(--cor-primaria-light) !important; color: var(--cor-primaria) !important; transform: translateY(-1px); box-shadow: var(--shadow-md); }
[data-testid="stBaseButton-primary"] { background: linear-gradient(135deg, #012869 0%, #0A48AA 100%) !important; border: 1px solid transparent !important; color: #FFFFFF !important; box-shadow: 0 6px 14px -6px rgba(1,40,105,0.55); }
[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.1); transform: translateY(-1px); box-shadow: 0 10px 20px -8px rgba(1,40,105,0.6); }
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primary"] span { color: #FFFFFF !important; }

/* Expanders */
[data-testid="stExpander"] details { background: #FFFFFF; border: 1px solid var(--line) !important; border-radius: 12px !important; box-shadow: var(--shadow-xs); overflow: hidden; }
[data-testid="stExpander"] summary { padding-top: 12px; padding-bottom: 12px; transition: background .18s var(--ease), color .18s var(--ease); }
[data-testid="stExpander"] summary:hover { background: var(--surface-2); color: var(--cor-primaria); }
[data-testid="stExpander"] summary p { font-weight: 600; }

/* st.metric */
[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; box-shadow: var(--shadow-sm); }
[data-testid="stMetricLabel"] p { font-size: 12px !important; font-weight: 700 !important; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-400) !important; }
[data-testid="stMetricValue"] { color: var(--ink-900); font-weight: 800; font-variant-numeric: tabular-nums; }

/* Dataframes, gráficos e alertas */
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-xs); background: #FFFFFF; }
[data-testid="stPlotlyChart"] { background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px; box-shadow: var(--shadow-sm); overflow: hidden; }
[data-testid="stAlert"], [data-testid="stAlertContainer"] { border-radius: 12px !important; }

/* Inputs */
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] { border-radius: 10px !important; transition: border-color .18s var(--ease), box-shadow .18s var(--ease); }
[data-baseweb="select"] > div:focus-within, [data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within { border-color: var(--cor-primaria-light) !important; box-shadow: var(--ring-focus) !important; }
[data-baseweb="tag"] { border-radius: 6px !important; }
[data-testid="stWidgetLabel"] p { font-weight: 600; color: var(--ink-600); }
hr { border-color: var(--line) !important; }
"""

_CSS_HEROS = """
/* ====================== HEROS ====================== */
@keyframes hero-gradient-shift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
@keyframes hero-fade-up { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.hero-corp, .totale-hero-1, .totale-hero-2, .hero-migracao, .hero-pme, .hero-domicilios {
    position: relative; overflow: hidden; isolation: isolate;
    color: #FFFFFF; border-radius: var(--radius-xl); padding: 32px 38px; margin-bottom: 26px;
    border: 1px solid rgba(255,255,255,0.10);
    box-shadow: 0 1px 2px rgba(16,24,40,0.06), 0 24px 48px -24px rgba(1,30,82,0.55);
    animation: hero-fade-up .45s var(--ease) backwards;
}
/* Malha sutil (grid) */
.hero-corp::before, .totale-hero-1::before, .totale-hero-2::before, .hero-migracao::before, .hero-pme::before, .hero-domicilios::before {
    content: ''; position: absolute; inset: 0; z-index: 0; pointer-events: none;
    background-image: linear-gradient(rgba(255,255,255,0.055) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.055) 1px, transparent 1px);
    background-size: 32px 32px;
    -webkit-mask-image: radial-gradient(ellipse 70% 90% at 85% 10%, #000 0%, transparent 70%);
    mask-image: radial-gradient(ellipse 70% 90% at 85% 10%, #000 0%, transparent 70%);
}
/* Brilho de canto */
.hero-corp::after, .totale-hero-1::after, .totale-hero-2::after, .hero-migracao::after, .hero-pme::after, .hero-domicilios::after {
    content: ''; position: absolute; z-index: 0; pointer-events: none;
    width: 460px; height: 460px; right: -140px; top: -220px; border-radius: 50%;
    background: radial-gradient(circle, var(--hero-glow, rgba(243,124,4,0.38)) 0%, transparent 65%);
}
.hero-corp > *, .totale-hero-1 > *, .totale-hero-2 > *, .hero-migracao > *, .hero-pme > *, .hero-domicilios > * { position: relative; z-index: 2; }

.hero-corp { background: linear-gradient(125deg, #011A47 0%, #012869 42%, #0A3F97 100%); }
.totale-hero-1 { background: linear-gradient(125deg, #011A47 0%, #012869 45%, #0B439E 100%); }
.totale-hero-1::after { top: auto; bottom: -260px; right: -120px; }
.totale-hero-2 { background: linear-gradient(120deg, #011A47 0%, #012869 50%, #0A3F97 100%); border-left: 5px solid #F37C04; display: grid; grid-template-columns: 1fr auto; gap: 28px; align-items: center; --hero-glow: rgba(243,124,4,0.26); }
@media (max-width: 768px) { .totale-hero-2 { grid-template-columns: 1fr; } .hero-corp, .totale-hero-1, .totale-hero-2, .hero-migracao, .hero-pme, .hero-domicilios { padding: 24px 22px; } }
.hero-migracao { background: linear-gradient(125deg, #1E0B4B 0%, #3B1790 45%, #6D28D9 100%); --hero-glow: rgba(196,181,253,0.40); box-shadow: 0 1px 2px rgba(16,24,40,0.06), 0 24px 48px -24px rgba(76,29,149,0.6); }
.hero-pme { background: linear-gradient(125deg, #033D2E 0%, #046C4E 45%, #0E6C8C 100%); --hero-glow: rgba(96,165,250,0.40); box-shadow: 0 1px 2px rgba(16,24,40,0.06), 0 24px 48px -24px rgba(4,108,78,0.55); }
.hero-domicilios { background: linear-gradient(125deg, #011A47 0%, #0A3A63 45%, #0F766E 100%); --hero-glow: rgba(45,212,191,0.34); }

.hero-corp .hero-title { font-size: clamp(24px, 3vw, 36px); font-weight: 800; color: #FFFFFF; margin: 0 0 8px 0; line-height: 1.12; position: relative; z-index: 2; }
.hero-corp .hero-subtitle { font-size: clamp(14px, 1.4vw, 16px); color: rgba(255,255,255,0.80); margin: 0; line-height: 1.55; max-width: 780px; position: relative; z-index: 2; }
.hero-corp .hero-badge, .totale-hero-pill {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(255,255,255,0.10); -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.20); color: #FFFFFF;
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em;
    padding: 6px 14px 6px 12px; border-radius: 999px; margin-bottom: 14px; position: relative; z-index: 2;
}
.hero-corp .hero-badge::before, .totale-hero-pill-dot { content: ''; width: 6px; height: 6px; border-radius: 50%; background: #F37C04; box-shadow: 0 0 0 3px rgba(243,124,4,0.25); flex-shrink: 0; }
.totale-hero-pill .totale-hero-pill-icon { font-size: 13px; line-height: 1; }

.th-title-lg, .totale-hero-1 .th-title-lg { font-size: clamp(24px, 2.6vw, 34px) !important; font-weight: 800; color: #FFFFFF !important; margin: 4px 0 8px !important; line-height: 1.12 !important; letter-spacing: -0.025em; }
.th-title, .totale-hero-2 .th-title { font-size: clamp(22px, 2.2vw, 30px) !important; font-weight: 800; color: #FFFFFF !important; margin: 10px 0 8px !important; line-height: 1.15 !important; letter-spacing: -0.02em; }
.totale-hero-h1, .hero-migracao .totale-hero-h1, .hero-pme .totale-hero-h1, .hero-domicilios .totale-hero-h1 { font-size: clamp(24px, 2.6vw, 34px) !important; font-weight: 800; color: #FFFFFF !important; margin: 4px 0 8px !important; line-height: 1.12 !important; letter-spacing: -0.025em; }
.th-sub, .th-sub-muted, .totale-hero-sub { font-size: 15px !important; color: rgba(255,255,255,0.78) !important; margin: 0 !important; line-height: 1.55; max-width: 820px; }
.th-meta, .totale-hero-meta { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: rgba(255,255,255,0.62); margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.12); font-weight: 500; }
.th-badge { display: inline-flex; align-items: center; background: #F37C04; color: #FFFFFF; font-size: 10.5px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; padding: 5px 12px; border-radius: 6px; margin-bottom: 4px; box-shadow: 0 6px 14px -6px rgba(243,124,4,0.7); }
.th-tag { display: inline-block; font-size: 12px; color: rgba(255,255,255,0.72); margin-left: 10px; font-weight: 500; }
.totale-hero-2-card {
    background: linear-gradient(160deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.05) 100%);
    -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.18); border-radius: 14px; padding: 18px 26px; min-width: 190px; text-align: center; position: relative; z-index: 2;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.12);
}
.th-card-label { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: rgba(255,255,255,0.70); margin-bottom: 6px; }
.th-card-value { font-family: var(--font-titulo) !important; font-size: 30px; font-weight: 800; color: #FF9D45; line-height: 1; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }

.totale-hero-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin-top: 20px; }
.totale-hero-stat {
    background: linear-gradient(160deg, rgba(255,255,255,0.13) 0%, rgba(255,255,255,0.05) 100%);
    -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.16); border-radius: 12px; padding: 14px 16px; text-align: left;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.10);
}
.totale-hero-stat-value { display: block; font-family: var(--font-titulo) !important; font-size: 22px; font-weight: 800; color: var(--hero-stat-cor, #FF9D45); line-height: 1.05; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
.totale-hero-stat-label { display: block; margin-top: 6px; font-size: 10.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(255,255,255,0.72); }
.totale-hero-features { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.totale-hero-feature { display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.18); border-radius: 999px; padding: 6px 14px 6px 10px; font-size: 12px; font-weight: 600; color: #FFFFFF; }
.totale-hero-feature-check { display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 50%; background: rgba(255,255,255,0.22); font-size: 10px; font-weight: 800; }

.totale-badge-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 999px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; border: 1px solid transparent; line-height: 1.4; white-space: nowrap; }
"""

_CSS_CARDS = """
/* ====================== CARDS / KPIs ====================== */
@keyframes card-color-shift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
@keyframes card-enter { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
.card-premium {
    position: relative; overflow: hidden; isolation: isolate;
    display: flex; flex-direction: column; justify-content: space-between; gap: 14px;
    background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
    padding: 20px 22px; margin-bottom: 14px; box-shadow: var(--shadow-sm);
    transition: transform .25s var(--ease), box-shadow .25s var(--ease), border-color .25s var(--ease);
}
.card-premium:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); border-color: var(--line-strong); }
.card-premium-colorida { background: linear-gradient(135deg, #012869 0%, #0A48AA 100%); border: 1px solid rgba(255,255,255,0.14); color: #FFFFFF; }
.card-premium-colorida .kpi-label-premium { color: rgba(255,255,255,0.78); }
.card-premium-colorida .kpi-value-premium { color: #FFFFFF; }
.card-premium-colorida .kpi-sub-premium { color: rgba(255,255,255,0.82); }
.card-premium-colorida .kpi-icon-wrapper { background: rgba(255,255,255,0.14) !important; color: #FFFFFF !important; }
.card-accent-top { position: absolute; top: 0; left: 0; right: 0; height: 3px; z-index: 3; }
.card-header-flex { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; position: relative; z-index: 2; }
.kpi-label-premium { font-size: 11.5px; font-weight: 700; color: var(--ink-400); text-transform: uppercase; letter-spacing: 0.06em; line-height: 1.4; padding-top: 2px; overflow-wrap: anywhere; }
.kpi-icon-wrapper { display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 11px; flex-shrink: 0; font-size: 19px; line-height: 1; }
.kpi-body { position: relative; z-index: 2; }
.kpi-value-premium { font-size: 30px; font-weight: 800; color: var(--ink-900); line-height: 1.05; font-variant-numeric: tabular-nums; font-family: var(--font-titulo) !important; letter-spacing: -0.03em; position: relative; z-index: 2; overflow-wrap: anywhere; }
.kpi-sub-premium { font-size: 12.5px; color: var(--ink-400); margin-top: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; position: relative; z-index: 2; line-height: 1.45; }
.trend-pill { display: inline-flex; align-items: center; gap: 3px; padding: 3px 8px; border-radius: 999px; font-size: 11.5px; font-weight: 700; line-height: 1.2; font-variant-numeric: tabular-nums; }
.trend-up { background: #ECFDF5; color: #047857; box-shadow: inset 0 0 0 1px rgba(5,150,105,0.18); }
.trend-down { background: #FEF2F2; color: #B91C1C; box-shadow: inset 0 0 0 1px rgba(220,38,38,0.18); }
.trend-neutral, .trend-pill:not(.trend-up):not(.trend-down) { background: #F1F5F9; color: #475569; box-shadow: inset 0 0 0 1px rgba(100,116,139,0.18); }

/* Variante sólida (colorida=True) */
.kpi-card--solid {
    background: radial-gradient(130% 120% at 100% 0%, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0) 52%), linear-gradient(135deg, var(--kpi-c1) 0%, var(--kpi-c2) 100%);
    border-color: rgba(255,255,255,0.12); color: #FFFFFF;
    box-shadow: 0 1px 2px rgba(16,24,40,0.06), 0 12px 24px -14px var(--kpi-shadow);
}
.kpi-card--solid::after { content: ''; position: absolute; right: -46px; bottom: -70px; width: 170px; height: 170px; border-radius: 50%; border: 26px solid rgba(255,255,255,0.06); z-index: 0; pointer-events: none; }
.kpi-card--solid:hover { border-color: rgba(255,255,255,0.22); box-shadow: 0 2px 4px rgba(16,24,40,0.06), 0 22px 36px -16px var(--kpi-shadow); }
.kpi-card--solid .kpi-label-premium { color: rgba(255,255,255,0.80); }
.kpi-card--solid .kpi-value-premium { color: #FFFFFF; }
.kpi-card--solid .kpi-sub-premium { color: rgba(255,255,255,0.82); }
.kpi-card--solid .kpi-icon-wrapper { background: rgba(255,255,255,0.14); color: #FFFFFF; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.20); -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px); }
.kpi-card--solid .trend-up { background: rgba(16,185,129,0.22); color: #D1FAE5; box-shadow: inset 0 0 0 1px rgba(167,243,208,0.30); }
.kpi-card--solid .trend-down { background: rgba(239,68,68,0.24); color: #FEE2E2; box-shadow: inset 0 0 0 1px rgba(254,202,202,0.30); }
.kpi-card--solid .trend-neutral, .kpi-card--solid .trend-pill:not(.trend-up):not(.trend-down) { background: rgba(255,255,255,0.14); color: #FFFFFF; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.22); }

/* Variante clara (colorida=False) */
.kpi-card--soft .card-accent-top { background: linear-gradient(90deg, var(--kpi-c1), var(--kpi-c2)); }
.kpi-card--soft .kpi-icon-wrapper { background: var(--kpi-soft); color: var(--kpi-c1); box-shadow: inset 0 0 0 1px var(--kpi-ring); }
.kpi-card--soft .kpi-value-premium { color: var(--ink-900); }

.kpi-card--compact { gap: 10px; border-radius: 12px; }
.kpi-card--compact .kpi-icon-wrapper { width: 32px; height: 32px; border-radius: 9px; font-size: 16px; }
.kpi-card--compact .kpi-label-premium { font-size: 10.5px; }
.kpi-card--compact .kpi-sub-premium { margin-top: 6px; font-size: 11.5px; }
.kpi-card--compact::after { width: 120px; height: 120px; right: -36px; bottom: -56px; border-width: 18px; }

/* Card informativo (render_card) */
.totale-info-card { flex-direction: row; justify-content: flex-start; align-items: flex-start; gap: 14px; border-left: 4px solid var(--card-accent); }
.totale-info-card-icon { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 11px; flex-shrink: 0; background: var(--card-soft); color: var(--card-fg); font-size: 19px; line-height: 1; box-shadow: inset 0 0 0 1px var(--card-ring); }
.totale-info-card-title { font-family: var(--font-titulo) !important; font-size: 15px; font-weight: 800; color: var(--ink-900); margin-bottom: 4px; letter-spacing: -0.01em; line-height: 1.3; }
.totale-info-card-body { font-size: 13px; color: var(--ink-500); line-height: 1.6; }
.totale-info-card-body strong { color: var(--ink-700); }
"""

_CSS_TABELAS = """
/* ====================== TABELA PREMIUM ENTERPRISE ====================== */
.table-premium-title { display: flex; align-items: center; gap: 10px; font-family: var(--font-titulo) !important; font-weight: 800; font-size: 15.5px; color: var(--ink-900); margin-bottom: 12px; letter-spacing: -0.01em; }
.table-premium-title::before { content: ''; width: 4px; height: 18px; border-radius: 3px; background: linear-gradient(180deg, #F37C04 0%, #FDBA74 100%); flex-shrink: 0; }
.table-premium-meta { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 10px; font-size: 11.5px; color: #94A3B8; font-weight: 500; }
.table-premium-meta-right { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; }
.table-premium-meta-right::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: #10B981; box-shadow: 0 0 0 3px rgba(16,185,129,0.18); }

.table-premium-wrapper {
    color-scheme: light !important;
    background: #FFFFFF !important;
    border-radius: 14px !important;
    border: 1px solid var(--line) !important;
    box-shadow: var(--shadow-sm) !important;
    overflow: hidden !important;
    margin: 0 !important;
}
.table-premium-scroll {
    width: 100% !important;
    overflow: auto !important;
    scrollbar-width: thin !important;
    scrollbar-color: #CBD5E1 transparent !important;
    background: #FFFFFF !important;
}
.totale-table-pro {
    width: 100% !important;
    border-collapse: separate !important;
    border-spacing: 0 !important;
    text-align: left !important;
    font-family: var(--font-texto) !important;
    background: #FFFFFF !important;
    margin: 0 !important;
}
.totale-table-pro thead, .totale-table-pro thead tr, .totale-table-pro th { background: #F8FAFC !important; }
.totale-table-pro th {
    position: sticky !important; top: 0 !important; z-index: 2 !important;
    color: #475569 !important;
    font-family: var(--font-titulo) !important;
    font-size: 11px !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    padding: 13px 16px !important;
    border: none !important;
    border-bottom: 1px solid var(--line) !important;
    box-shadow: inset 0 -1px 0 var(--line) !important;
    white-space: nowrap !important;
}
.totale-table-pro tbody, .totale-table-pro tbody tr, .totale-table-pro tbody tr td { background: #FFFFFF !important; }
.totale-table-pro td {
    padding: 11px 16px !important;
    border: none !important;
    border-bottom: 1px solid var(--line-soft) !important;
    color: #1E293B !important;
    font-size: 13px !important;
    line-height: 1.45 !important;
    vertical-align: middle !important;
    transition: background-color .15s ease !important;
    white-space: normal !important;
}
.totale-table-pro td.td-num { font-variant-numeric: tabular-nums !important; font-feature-settings: "tnum" 1 !important; font-weight: 500 !important; color: #0F172A !important; }
.totale-table-pro tbody tr:last-child td { border-bottom: none !important; }
.totale-table-pro tbody tr.striped, .totale-table-pro tbody tr.striped td { background-color: #FAFBFD !important; }
.totale-table-pro tbody tr:hover, .totale-table-pro tbody tr:hover td { background-color: #F1F5FB !important; color: #0F172A !important; }
.totale-table-pro tbody tr.linha-destaque, .totale-table-pro tbody tr.linha-destaque td {
    background: #FFF7ED !important;
    border-top: 1px solid #FED7AA !important;
    border-bottom: 1px solid #FED7AA !important;
    color: #7C2D12 !important;
    font-weight: 700 !important;
}
.totale-table-pro tbody tr.linha-destaque td:first-child { box-shadow: inset 3px 0 0 #F37C04 !important; }

.td-badge-ok, .td-badge-alerta, .td-badge-neutro {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    padding: 3px 10px 3px 8px !important;
    border-radius: 999px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.03em !important;
    line-height: 1.4 !important;
    white-space: nowrap !important;
}
.td-badge-ok::before, .td-badge-alerta::before, .td-badge-neutro::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: 0.85; flex-shrink: 0; }
.td-badge-ok { background-color: #ECFDF5 !important; color: #047857 !important; box-shadow: inset 0 0 0 1px rgba(5,150,105,0.22) !important; }
.td-badge-alerta { background-color: #FEF2F2 !important; color: #B91C1C !important; box-shadow: inset 0 0 0 1px rgba(220,38,38,0.20) !important; }
.td-badge-neutro { background-color: #F1F5F9 !important; color: #334155 !important; box-shadow: inset 0 0 0 1px rgba(100,116,139,0.22) !important; }
"""

_CSS_EXTRAS = """
/* ====================== PROGRESSO / SKELETON ====================== */
@keyframes pb-shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
.totale-progress { margin: 14px 0; }
.totale-progress-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 8px; }
.totale-progress-label { font-size: 13px; font-weight: 600; color: var(--ink-600); }
.totale-progress-value { font-family: var(--font-titulo) !important; font-size: 14px; font-weight: 800; color: var(--cor-primaria); font-variant-numeric: tabular-nums; }
.totale-progress-track { width: 100%; background: #E9EEF5; border-radius: 999px; overflow: hidden; box-shadow: inset 0 1px 2px rgba(16,24,40,0.06); }
.totale-pb-fill { position: relative; overflow: hidden; height: 100%; border-radius: 999px; transition: width .6s var(--ease); }
.totale-pb-fill.animado::after { content: ''; position: absolute; inset: 0; background: linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.38) 50%, transparent 70%); background-size: 200% 100%; animation: pb-shimmer 2.2s linear infinite; }
.totale-skeleton { background: linear-gradient(90deg, #EEF2F7 25%, #E2E8F0 50%, #EEF2F7 75%); background-size: 200% 100%; animation: pb-shimmer 1.4s linear infinite; border-radius: 8px; }

/* ====================== EMPTY STATE ====================== */
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 44px 32px; margin: 20px 0; background: #FFFFFF; border: 1.5px dashed var(--line-strong); border-radius: 16px; transition: border-color .25s ease; }
.empty-state:hover { border-color: #B8C3D3; }
.empty-state-icon { display: inline-flex; align-items: center; justify-content: center; width: 64px; height: 64px; border-radius: 18px; background: #FFFFFF; box-shadow: var(--shadow-md), inset 0 0 0 1px var(--line); font-size: 30px; line-height: 1; margin-bottom: 16px; }
.empty-state-title, .empty-state .empty-state-title { font-family: var(--font-titulo) !important; font-size: 17px !important; font-weight: 800; color: #334155; margin: 0 0 6px !important; line-height: 1.3 !important; letter-spacing: -0.01em; }
.empty-state-desc { font-size: 13.5px; color: #64748B; margin: 0 !important; max-width: 440px; line-height: 1.6; }
.empty-state-action { display: inline-flex; align-items: center; gap: 6px; margin-top: 16px !important; padding: 6px 14px; border-radius: 999px; background: #FFF7ED; color: #C2410C; border: 1px solid #FED7AA; font-size: 12.5px; font-weight: 700; }

/* ====================== INSIGHT / NOTIFICAÇÃO ====================== */
.totale-insight, .totale-notification {
    display: flex; align-items: flex-start; gap: 12px;
    border-radius: 12px; padding: 14px 16px; margin: 12px 0;
    font-size: 14px; line-height: 1.6;
    background: var(--ins-bg, #EFF6FF); color: var(--ins-fg, #1E40AF);
    border: 1px solid var(--ins-ring, rgba(59,130,246,0.22)); border-left: 4px solid var(--ins-bd, #3B82F6);
    box-shadow: var(--shadow-xs);
}
.totale-insight-icon { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 9px; background: #FFFFFF; box-shadow: inset 0 0 0 1px var(--ins-ring, rgba(59,130,246,0.22)); font-size: 15px; line-height: 1; flex-shrink: 0; }
.totale-insight-body { flex: 1; min-width: 0; padding-top: 3px; }
.totale-insight-title { display: block; font-family: var(--font-titulo) !important; font-weight: 800; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 2px; }
.totale-insight-msg { color: var(--ink-700); }
.totale-insight-msg strong { color: var(--ins-fg, inherit); font-weight: 700; }
.totale-insight-msg code, .totale-info-card-body code { font-family: var(--font-codigo) !important; font-size: 12px; background: rgba(255,255,255,0.7); padding: 1px 6px; border-radius: 5px; box-shadow: inset 0 0 0 1px rgba(15,23,42,0.08); }
.totale-notification { font-size: 13px; line-height: 1.55; }

/* ====================== SECTION HEADER ====================== */
.section-header { display: flex; align-items: center; gap: 14px; margin: 34px 0 18px 0; padding-bottom: 14px; border-bottom: 1px solid var(--line); position: relative; }
.section-header::after { content: ''; position: absolute; left: 0; bottom: -1px; width: 64px; height: 3px; border-radius: 3px; background: linear-gradient(90deg, #F37C04 0%, #FDBA74 100%); }
.section-title, .section-header .section-title { font-size: clamp(18px, 1.7vw, 22px) !important; font-weight: 800; color: var(--ink-900) !important; margin: 0 !important; line-height: 1.25 !important; letter-spacing: -0.02em; min-width: 0; overflow-wrap: anywhere; }
.section-subtitle, .section-header .section-subtitle { margin: 4px 0 0 !important; font-size: 13.5px; color: var(--ink-400); line-height: 1.5; }
.section-header-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0; }
.user-info-card { background: linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%); border: 1px solid var(--line); border-radius: 12px; padding: 16px; margin: 12px 0; }

/* ====================== ÍCONES CORPORATIVOS ====================== */
.totale-icon-tile {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
    overflow: hidden !important;
    line-height: 1 !important;
    padding: 0 !important;
}
.totale-icon-tile--section {
    width: 44px !important; height: 44px !important; border-radius: 12px !important;
    background: linear-gradient(145deg, #FFFFFF 0%, #EEF3FB 100%) !important;
    border: 1px solid #DCE4F1 !important;
    box-shadow: 0 1px 2px rgba(16,24,40,0.05), inset 0 1px 0 #FFFFFF !important;
}
.totale-icon-tile--brand {
    width: 40px !important; height: 40px !important; border-radius: 11px !important;
    background: linear-gradient(145deg, #012869 0%, #0A48AA 100%) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    box-shadow: 0 6px 14px -6px rgba(1,40,105,0.55), inset 0 1px 0 rgba(255,255,255,0.18) !important;
}
.totale-icon-glyph {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: none !important;
    -webkit-background-clip: border-box !important;
    background-clip: border-box !important;
    color: var(--cor-primaria) !important;
    -webkit-text-fill-color: currentColor !important;
    font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji",
                 "Material Symbols Rounded", "Material Symbols Outlined",
                 "Material Icons", sans-serif !important;
    font-feature-settings: "liga" 1 !important;
    font-style: normal !important;
    font-weight: 400 !important;
    line-height: 1 !important;
    white-space: nowrap !important;
}
.totale-icon-tile--brand .totale-icon-glyph { font-size: 20px !important; color: #FFFFFF !important; }
.totale-icon-tile--section .totale-icon-glyph { font-size: 21px !important; }
.section-header-copy { flex: 1 !important; min-width: 0 !important; }
.totale-icon-tile:empty, .totale-icon-glyph:empty { display: none !important; }
"""

_CSS_SIDEBAR = """
/* ====================== CONTAINER ====================== */
[data-testid="stSidebar"] {
    position: relative;
    background: linear-gradient(180deg, #FFFFFF 0%, #F6F8FC 100%);
    border-right: 1px solid var(--line);
    box-shadow: 1px 0 0 rgba(16,24,40,0.02);
}
[data-testid="stSidebar"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #012869 0%, #0A48AA 55%, #F37C04 100%);
    z-index: 100;
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 10px; }
[data-testid="stSidebar"] ::-webkit-scrollbar { width: 6px; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; border: none; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover { background: #F37C04; }

[data-testid="stSidebarCollapseButton"] button:hover {
    background: rgba(243,124,4,0.10) !important;
    color: #F37C04 !important;
}

/* ====================== CABEÇALHO DE SEÇÃO ====================== */
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {
    font-family: var(--font-titulo) !important;
    font-size: 10px !important;
    font-weight: 800 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    color: #7A8699 !important;
    padding: 6px 12px 6px 14px !important;
    margin: 18px 0 4px !important;
    position: relative;
}
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"]:first-child { margin-top: 4px !important; }
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"]::before {
    content: "";
    position: absolute;
    left: 4px; top: 50%;
    width: 4px; height: 4px; margin-top: -2px;
    border-radius: 50%;
    background: #F37C04;
    box-shadow: 0 0 0 3px rgba(243,124,4,0.18);
}

/* ====================== LISTA ====================== */
[data-testid="stSidebarNav"] ul { padding: 0 8px !important; margin: 0 !important; list-style: none !important; }
[data-testid="stSidebarNav"] li { margin: 2px 0 !important; }

/* ====================== LINK ====================== */
[data-testid="stSidebarNav"] a {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 8px 12px !important;
    border-radius: 9px !important;
    border: 1px solid transparent !important;
    color: #334155 !important;
    font-family: var(--font-texto) !important;
    font-size: 13.5px !important;
    font-weight: 600 !important;
    line-height: 1.25 !important;
    text-decoration: none !important;
    position: relative;
    overflow: hidden;
    transition: background .18s ease, color .18s ease, border-color .18s ease, transform .18s ease, box-shadow .18s ease;
}
[data-testid="stSidebarNav"] a span { color: inherit !important; }
[data-testid="stSidebarNav"] a > span:first-child,
[data-testid="stSidebarNav"] a [data-testid="stIconMaterial"] {
    flex-shrink: 0 !important;
    width: 20px !important;
    font-size: 18px !important;
    text-align: center !important;
    line-height: 1 !important;
    opacity: 0.9;
}
[data-testid="stSidebarNav"] a:hover {
    background: rgba(1,40,105,0.055) !important;
    border-color: rgba(1,40,105,0.08) !important;
    color: #012869 !important;
    transform: translateX(2px);
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: linear-gradient(90deg, #012869 0%, #0A48AA 100%) !important;
    border-color: transparent !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    box-shadow: 0 8px 16px -8px rgba(1,40,105,0.55);
    transform: none;
}
[data-testid="stSidebarNav"] a[aria-current="page"]::before {
    content: "";
    position: absolute;
    left: 0; top: 22%; bottom: 22%;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: #F37C04;
}
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: #FFFFFF !important; }
[data-testid="stSidebarNav"] a:focus-visible { outline: 2px solid #F37C04; outline-offset: 1px; }

[data-testid="stSidebarNavSeparator"] {
    margin: 14px 12px !important;
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(1,40,105,0.16), transparent) !important;
}

/* ====================== COMPONENTES CUSTOM ====================== */
.sidebar-brand {
    padding: 8px 4px 16px;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--line);
    position: relative;
}
.sidebar-brand::after { content: ''; position: absolute; left: 4px; bottom: -1px; width: 44px; height: 2px; border-radius: 2px; background: linear-gradient(90deg, #F37C04, #FDBA74); }
.sidebar-brand-row { display: flex; align-items: center; gap: 12px; }
.sidebar-brand-name {
    font-family: var(--font-titulo) !important;
    font-size: 18px !important; font-weight: 800 !important; line-height: 1.15 !important; letter-spacing: -0.02em;
    margin: 0 !important;
    background: linear-gradient(135deg, #012869 0%, #0A48AA 55%, #F37C04 130%);
    -webkit-background-clip: text; background-clip: text; color: transparent; -webkit-text-fill-color: transparent;
}
.sidebar-brand-sub { font-size: 11.5px; color: var(--ink-400); margin-top: 3px; font-weight: 500; line-height: 1.35; }
.sidebar-brand-version { display: inline-flex; align-items: center; margin-top: 10px; background: #EEF3FF; color: #012869; font-weight: 700; font-size: 10px; letter-spacing: 0.06em; padding: 2px 9px; border-radius: 999px; border: 1px solid #D6E0F5; text-transform: uppercase; }
.sidebar-section-header {
    margin: 18px 0 6px;
    padding: 6px 0 6px 14px;
    position: relative;
}
.sidebar-section-header::before {
    content: "";
    position: absolute;
    left: 4px; top: 50%;
    width: 4px; height: 4px; margin-top: -2px;
    border-radius: 50%;
    background: #F37C04;
    box-shadow: 0 0 0 3px rgba(243,124,4,0.18);
}
.sidebar-footer {
    margin-top: 24px;
    padding: 14px 12px 10px;
    border: 1px solid var(--line);
    background: #FFFFFF;
    border-radius: 12px;
    box-shadow: var(--shadow-xs);
    position: relative;
    overflow: hidden;
}
.sidebar-footer::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, #012869 0%, #F37C04 100%); }
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
    border-color: #FED7AA !important;
    color: #7C2D12 !important;
    font-weight: 800 !important;
    box-shadow: 0 2px 8px rgba(243,124,4,0.16);
}
[data-testid="stSidebarNav"] a[aria-current="page"]::before {
    content: "";
    position: absolute;
    left: 0; top: 22%; bottom: 22%;
    width: 3px;
    border-radius: 0 3px 3px 0;
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
        eixo = {
            "gridcolor": "#EEF2F7",
            "zerolinecolor": "#D3DAE5",
            "linecolor": "#E5E9F0",
            "tickfont": {"family": Fontes.TEXTO, "size": 12, "color": "#64748B"},
            "title": {
                "font": {
                    "family": Fontes.TITULO,
                    "size": 12.5,
                    "color": Cores.TEXTO_2,
                }
            },
        }
        template = go.layout.Template(
            layout=go.Layout(
                font={"family": Fontes.TEXTO, "size": 13, "color": "#334155"},
                title={
                    "font": {"family": Fontes.TITULO, "size": 17, "color": "#0B1324"},
                    "x": 0.02,
                    "xanchor": "left",
                },
                legend={
                    "font": {
                        "family": Fontes.TEXTO,
                        "size": 12,
                        "color": Cores.TEXTO_2,
                    },
                    "bgcolor": "rgba(255,255,255,0)",
                    "bordercolor": "rgba(0,0,0,0)",
                    "borderwidth": 0,
                },
                xaxis=eixo,
                yaxis=eixo,
                paper_bgcolor="white",
                plot_bgcolor="white",
                colorway=ConfigCores.PLOTLY_COLORWAY,
                hoverlabel={
                    "bgcolor": "#FFFFFF",
                    "bordercolor": "#D3DAE5",
                    "font": {"family": Fontes.TEXTO, "size": 12, "color": "#0B1324"},
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
            f"{_CSS_STREAMLIT_NATIVO}\n"
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

        badge_html = (
            '<span class="sidebar-brand-version">'
            f"{Validadores.html_escape(versao_final)}</span>"
            if versao_final
            else ""
        )

        icone_html = ""
        if not logo_valida:
            icone_html = _icone_tile(icone_final, "brand")

        nome_html = (
            '<div class="sidebar-brand-name">'
            f"{Validadores.html_escape(nome_final)}</div>"
            if nome_final
            else ""
        )

        subtitulo_html = (
            '<div class="sidebar-brand-sub">'
            f"{Validadores.html_escape(subtitulo_final)}</div>"
            if subtitulo_final
            else ""
        )

        markup = (
            '<div class="sidebar-brand">'
            '<div class="sidebar-brand-row">'
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
    detalhes_html = "".join(
        f"""
        <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;">
            <span style="font-size:10.5px;color:{Cores.TEXTO_3};font-weight:500;">{Validadores.html_escape(k)}</span>
            <span style="font-size:10.5px;color:{Cores.PRIMARIA};font-weight:700;font-variant-numeric:tabular-nums;">{Validadores.html_escape(v)}</span>
        </div>
        """
        for k, v in detalhes_dict.items()
    )

    ultima_atualizacao_fmt = (
        formatar_datetime_exibicao(ultima_atualizacao) if ultima_atualizacao else ""
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
def _hero_pill(icone: str, texto: str) -> str:
    """Pill translúcida usada no topo dos heros (ícone + rótulo)."""
    if not texto:
        return ""
    icone_html = (
        f'<span class="totale-hero-pill-icon">{Validadores.html_escape(icone)}</span>'
        if icone
        else '<span class="totale-hero-pill-dot"></span>'
    )
    return (
        f'<div class="totale-hero-pill">{icone_html}'
        f"<span>{Validadores.html_escape(texto)}</span></div>"
    )


def _hero_stats(
    stats: Sequence[dict[str, str]] | None, cor_valor: str = "#FF9D45"
) -> str:
    """Grade de estatísticas em cartões de vidro (até 4 itens)."""
    if not stats:
        return ""
    cards: list[str] = []
    for item in list(stats)[:4]:
        valor_txt = Validadores.html_escape(item.get("valor", ""))
        label_txt = Validadores.html_escape(item.get("label", ""))
        cards.append(
            '<div class="totale-hero-stat">'
            f'<strong class="totale-hero-stat-value">{valor_txt}</strong>'
            f'<span class="totale-hero-stat-label">{label_txt}</span>'
            "</div>"
        )
    return (
        f'<div class="totale-hero-stats" style="--hero-stat-cor:{cor_valor};">'
        f"{''.join(cards)}</div>"
    )


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
    b = _hero_pill(icone, badge)
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
        "<div>"
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
        f'<div style="min-width:0;">{b}{tag}<h1 class="th-title">{t}</h1>{s}</div>{card}'
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
    badge_html = _hero_pill(icone, badge)
    sub_html = (
        f'<p class="totale-hero-sub">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    stats_html = _hero_stats(stats, "#FDBA74")

    markup = (
        '<div class="hero-migracao"><div>'
        f"{badge_html}"
        f'<h1 class="totale-hero-h1">{t}</h1>'
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
    badge_html = _hero_pill(icone, badge)
    sub_html = (
        f'<p class="totale-hero-sub">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )

    feat_html = ""
    if features:
        pills = [
            '<span class="totale-hero-feature">'
            '<span class="totale-hero-feature-check">✓</span>'
            f"{Validadores.html_escape(feature)}"
            "</span>"
            for feature in list(features)[:5]
        ]
        feat_html = f'<div class="totale-hero-features">{"".join(pills)}</div>'

    markup = (
        '<div class="hero-pme"><div>'
        f"{badge_html}"
        f'<h1 class="totale-hero-h1">{t}</h1>'
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
    if not titulo:
        raise ValueError("render_hero_novos_domicilios: 'titulo' não pode ser vazio.")

    t = Validadores.html_escape(titulo)
    badge_html = _hero_pill(icone, badge)
    sub_html = (
        f'<p class="totale-hero-sub">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    stats_html = _hero_stats(stats, "#5EEAD4")
    meta_html = (
        f'<div class="totale-hero-meta">{Validadores.html_escape(meta_info)}</div>'
        if meta_info
        else ""
    )

    markup = (
        '<div class="hero-domicilios"><div>'
        f"{badge_html}"
        f'<h1 class="totale-hero-h1">{t}</h1>'
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
    titulo_final = str(titulo or title or "").strip()
    icone_final = str(icone or icon or "").strip()
    badge_final = str(badge or "").strip()
    subtitulo_final = str(subtitulo or "").strip()

    # ---------------------------------------------------------
    # Compatibilidade com chamadas antigas: (icone, titulo).
    # Identificação inteligente para evitar layouts quebrados.
    # ---------------------------------------------------------
    def _parece_icone(val: str) -> bool:
        v = val.strip()
        if not v:
            return False
        if len(v) <= 4:
            return True
        # Verifica se pode ser nome de um Material Icon (sem espaço, alphanum e underscore)
        if " " not in v and all(c.isalnum() or c == "_" for c in v):
            return True
        return False

    def _parece_titulo(val: str) -> bool:
        v = val.strip()
        if not v:
            return False
        if len(v) > 10:
            return True
        if " " in v:
            return True
        if any(c.isupper() for c in v):
            return True
        return False

    # Se o argumento passado como título for claramente um ícone, e o de ícone for um título, inverta.
    if _parece_icone(titulo_final) and _parece_titulo(icone_final):
        titulo_final, icone_final = icone_final, titulo_final
        logger.warning(
            "render_section_header recebeu ícone e título invertidos. "
            "Os argumentos foram corrigidos automaticamente para evitar layout quebrado."
        )

    if not any((titulo_final, icone_final, badge_final, subtitulo_final)):
        return

    tipo_norm = normalizar_tipo_badge(badge_tipo)
    bg_badge, cor_badge, borda_badge = ConfigCores.BADGE[tipo_norm]

    # O tile já possui a trava de segurança para textos longos.
    icone_html = _icone_tile(icone_final, "section") if icone_final else ""

    titulo_html = (
        f'<h2 class="section-title">{Validadores.html_escape(titulo_final)}</h2>'
        if titulo_final
        else ""
    )

    badge_html = (
        '<span class="totale-badge-pill" '
        f'style="background:{bg_badge};color:{cor_badge};'
        f'border-color:{_hex_to_rgba(borda_badge, 0.45)};">'
        f"{Validadores.html_escape(badge_final)}</span>"
        if badge_final
        else ""
    )

    subtitulo_html = (
        f'<p class="section-subtitle">{Validadores.html_escape(subtitulo_final)}</p>'
        if subtitulo_final
        else ""
    )

    linha_html = (
        f'<div class="section-header-row">{titulo_html}{badge_html}</div>'
        if (titulo_html or badge_html)
        else ""
    )

    markup = (
        '<div class="section-header">'
        f"{icone_html}"
        f'<div class="section-header-copy">{linha_html}{subtitulo_html}</div>'
        "</div>"
    )

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

    # Cores do tema expostas como variáveis CSS — o visual fica todo no CSS.
    cor_base = ConfigCores.TEMA.get(tema_norm, cor_inicio)
    fundo_suave = ConfigCores.FUNDOS_SUAVES.get(
        tema_norm, ConfigCores.FUNDOS_SUAVES["azul"]
    )
    variaveis = (
        f"--kpi-c1:{cor_inicio};"
        f"--kpi-c2:{cor_fim};"
        f"--kpi-shadow:{_hex_to_rgba(cor_inicio, 0.55)};"
        f"--kpi-soft:{fundo_suave};"
        f"--kpi-ring:{_hex_to_rgba(cor_base, 0.18)};"
    )

    classes = ["card-premium", "kpi-card--solid" if usar_cor else "kpi-card--soft"]
    if compacto:
        classes.append("kpi-card--compact")

    label_esc = Validadores.html_escape(label)
    valor_esc = Validadores.html_escape(valor)
    sub_esc = Validadores.html_escape(sub)

    padding = "14px 16px" if compacto else "20px 22px"
    altura_minima = "104px" if compacto else "148px"
    tamanho_valor = "22px" if compacto else "30px"

    estilo_card = f"{variaveis}padding:{padding};min-height:{altura_minima};"

    icone_html = ""
    if icone:
        # Prevenção extra para textos longos explodirem o tile do wrapper
        icone_seguro = icone.strip()
        if len(icone_seguro) > 15 and " " in icone_seguro:
            icone_seguro = icone_seguro[0]

        icone_html = (
            '<div class="kpi-icon-wrapper">'
            '<span aria-hidden="true" style="line-height:1;">'
            f"{Validadores.html_escape(icone_seguro)}"
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
        sub_html = (
            f'<div class="kpi-sub-premium">{delta_html}'
            f"{f'<span>{sub_esc}</span>' if sub_esc else ''}</div>"
        )

    accent_html = "" if usar_cor else '<div class="card-accent-top"></div>'

    markup = (
        f'<div class="{" ".join(classes)}" style="{estilo_card}" '
        f'role="region" aria-label="{label_esc}: {valor_esc}">'
        f"{accent_html}"
        '<div class="card-header-flex">'
        f'<div class="kpi-label-premium">{label_esc}</div>'
        f"{icone_html}"
        "</div>"
        '<div class="kpi-body">'
        f'<div class="kpi-value-premium" style="font-size:{tamanho_valor};">'
        f"{valor_esc}</div>"
        f"{sub_html}"
        "</div>"
        "</div>"
    )

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


def _estilo_alerta(bg: str, texto: str, borda: str) -> str:
    """Variáveis CSS compartilhadas por insight e notificação."""
    return (
        f"--ins-bg:{bg};--ins-fg:{texto};--ins-bd:{borda};"
        f"--ins-ring:{_hex_to_rgba(borda, 0.24)};"
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
        f'<div class="totale-insight totale-insight--{tipo_norm}" '
        f'style="{_estilo_alerta(bg, texto, borda)}">'
        f'<span class="totale-insight-icon" aria-hidden="true">{icone}</span>'
        '<div class="totale-insight-body">'
        f'{titulo_html}<div class="totale-insight-msg">{msg_html}</div>'
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
        f'<span class="totale-insight-title">{Validadores.html_escape(titulo)}</span>'
        if titulo
        else ""
    )

    markup = (
        f'<div role="status" class="totale-notification totale-notification--{tipo_norm}" '
        f'style="{_estilo_alerta(bg, fg, borda)}">'
        f'<span class="totale-insight-icon" aria-hidden="true">{icone}</span>'
        '<div class="totale-insight-body">'
        f'{titulo_html}<div class="totale-insight-msg">'
        f"{Formatadores.markdown_para_html(mensagem)}</div>"
        "</div></div>"
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
        f'<p class="empty-state-action">→ {Validadores.html_escape(acao)}</p>'
        if acao
        else ""
    )

    markup = (
        f'<div class="empty-state" style="background:linear-gradient(180deg,'
        f'{bg_estado} 0%,#FFFFFF 100%);border-color:{_hex_to_rgba(cor_estado, 0.28)};">'
        f'<span class="empty-state-icon" aria-hidden="true">'
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
    elif tema_norm == "verde":
        bg_style = f"linear-gradient(90deg, #047857, {Cores.VERDE_PME})"
    elif tema_norm == "vermelho":
        bg_style = "linear-gradient(90deg, #B91C1C, #EF4444)"
    elif tema_norm == "roxo":
        bg_style = f"linear-gradient(90deg, #5B21B6, {Cores.ROXO_CLARO})"

    header_html = ""
    if label or mostrar_valor:
        lbl = (
            f'<span class="totale-progress-label">{Validadores.html_escape(label)}</span>'
            if label
            else "<span></span>"
        )
        val = (
            f'<span class="totale-progress-value">{porcentagem:.1f}{unidade}</span>'
            if mostrar_valor
            else ""
        )
        header_html = f'<div class="totale-progress-head">{lbl}{val}</div>'

    classe_anim = "totale-pb-fill animado" if animado else "totale-pb-fill"

    markup = (
        '<div class="totale-progress" role="progressbar" aria-valuemin="0" '
        f'aria-valuemax="100" aria-valuenow="{porcentagem:.1f}">'
        f"{header_html}"
        f'<div class="totale-progress-track" style="height:{altura_px};">'
        f'<div class="{classe_anim}" style="width:{porcentagem:.4f}%;'
        f'background:{bg_style};"></div>'
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

            # Números/datas: algarismos tabulares (alinhados) na fonte do texto.
            eh_numerico = align == "right" or any(
                char.isdigit() for char in val_str if char not in ".,-"
            )
            classe_td = ' class="td-num"' if eh_numerico else ""
            td_parts.append(
                f'<td{classe_td} style="text-align:{align};">{val_str}</td>'
            )

        classe_linha: list[str] = []
        if eh_destaque:
            classe_linha.append("linha-destaque")
        elif striped and i % 2 == 1:
            classe_linha.append("striped")

        classe_attr = f' class="{" ".join(classe_linha)}"' if classe_linha else ""
        tr_parts.append(f"<tr{classe_attr}>{''.join(td_parts)}</tr>")

    titulo_html = (
        f'<div class="table-premium-title">{Validadores.html_escape(titulo)}</div>'
        if titulo
        else ""
    )
    caption_html = f"<span>{Validadores.html_escape(caption)}</span>" if caption else ""
    data_html = (
        '<span class="table-premium-meta-right">Atualizado em: '
        f"{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')}</span>"
        if mostrar_data
        else ""
    )
    meta_html = (
        f'<div class="table-premium-meta">{caption_html}{data_html}</div>'
        if (caption_html or data_html)
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
        f"{meta_html}</div>"
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
                        f"{nome_arquivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
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

    icone_html = (
        '<span class="totale-info-card-icon" aria-hidden="true">'
        f"{Validadores.html_escape(icone)}</span>"
        if icone
        else ""
    )
    corpo_bloco = (
        f'<div class="totale-info-card-body">{corpo_html}</div>' if corpo_html else ""
    )

    estilo = (
        f"--card-accent:{borda};--card-soft:{bg};--card-fg:{fg};"
        f"--card-ring:{_hex_to_rgba(borda, 0.22)};"
    )

    markup = (
        f'<div class="card-premium totale-info-card" role="region" '
        f'aria-label="{titulo_esc}" style="{estilo}">'
        f"{icone_html}"
        '<div style="flex:1;min-width:0;">'
        f'<div class="totale-info-card-title">{titulo_esc}</div>'
        f"{corpo_bloco}"
        "</div></div>"
    )

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
        else f'<span style="width:6px;height:6px;border-radius:50%;background:{borda};"></span>'
    )

    markup = (
        f'<span class="totale-badge-pill" style="background:{bg};color:{fg};'
        f'border-color:{_hex_to_rgba(borda, 0.45)};">{icone_html}'
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
    "CSSInjector",
    "ConfigCores",
    "Cores",
    "FontInjector",
    "Fontes",
    "Formatadores",
    "PlotlyConfig",
    "TemaKPI",
    "TemaKPIType",
    "TipoBadge",
    "TipoBadgeType",
    "TipoEmptyState",
    "TipoEmptyStateType",
    "TipoHero",
    "TipoHeroType",
    "TipoInsight",
    "TipoInsightType",
    "TipoNotification",
    "TipoNotificationType",
    "TipoProgressBar",
    "TipoProgressBarType",
    "TipoStatus",
    "TipoStatusType",
    "TipoTimelineItem",
    "TipoTimelineItemType",
    "TipoTrend",
    "TipoTrendType",
    "Validadores",
    "aplicar_estilo",
    "aplicar_estilo_corp",
    "aplicar_sidebar_corp",
    "formatar_datetime_exibicao",
    "formatar_numero_br",
    "normalizar_texto_badge",
    "normalizar_tipo",
    "render_badge",
    "render_card",
    "render_empty_state",
    "render_hero",
    "render_hero_migracao",
    "render_hero_novos_domicilios",
    "render_hero_pme",
    "render_hero_totale_1",
    "render_hero_totale_2",
    "render_insight",
    "render_kpi",
    "render_kpi_sm",
    "render_metric_card",
    "render_notification",
    "render_progress_bar",
    "render_section_header",
    "render_sidebar_brand",
    "render_sidebar_divider",
    "render_sidebar_footer_info",
    "render_sidebar_info",
    "render_sidebar_section",
    "render_sidebar_spacer",
    "render_sidebar_status",
    "render_skeleton",
    "render_spacer",
    "render_table_html",
]
