"""
components/componentes.py
=========================
Design System Streamlit — TOTALE

Versão: 5.1.0
Autor: TOTALE Tecnologia

5.1.0 — Refino visual da navegação nos 3 temas de sidebar (baseado em feedback
das telas reais do portal):
• Item ativo (Azul): preenchimento marrom (laranja alpha sobre navy) substituído
  por gradiente em azul de marca rgba(10,72,170,0.45→0.10); hairline laranja
  sutil (0.16) no lugar do contorno fechado; barra de acento laranja 3px.
• Item ativo (Laranja): contorno fechado substituído por hairline âmbar 0.18 +
  barra de acento #FFB067 (clara, destaca-se do próprio fill) e fill levemente
  mais quente à esquerda (0.36→0.10).
• Item ativo (Claro): ganha barra de acento laranja 3px (consistência de marca
  entre os 3 skins).
• Alinhamento sem "pulo" de 2px: todos os links da navegação passam a ter
  border-left transparente de 3px (antes só o item ativo tinha 3px).
• Hierarquia de rótulos (Azul): itens passivos de #94A3B8 → #CBD5E1 (10.27:1),
  deixando os títulos de seção (#94A3B8) mais escuros que os itens.
• Hover (Azul) levemente mais visível (0.05 → 0.07 de branco translúcido).

5.0.0 — Verificação e melhoria dos temas de sidebar (Claro, Azul e Laranja):
• Paleta centralizada em ConfigCores.SIDEBAR com tokens semânticos verificados:
  fundo, borda, texto (primário/secundário), ícones, cards, nav ativo/passaivo,
  botões, inputs, foco e acentos — cada tema com contraste WCAG AA validado.
• Ferramenta de verificação de contraste embutida:
  `python components/componentes.py` (ou `verificar_contrastes_sidebar()`)
  calcula luminância relativa e razão de contraste (WCAG 2.1) e sinaliza
  pares abaixo do mínimo (4.5:1 texto / 3:1 texto grande e componentes de UI).
• Correções de contraste aplicadas na navegação passiva (azul #334155 sobre
  #F1F5F9 hover no tema claro; #94A3B8/#FED7AA com !important nos temas
  escuros — regras genéricas do Streamlit venciam por ordem de cascade).
• Inputs com contraparte escura: `input-surface`, `input-text`, `input-border`
  em todos os temas; checkbox/radio com borda de contraste (mínimo 3:1).
• Estados de foco visíveis em todos os temas; scrollbars tematizadas;
  botões desabilitados estilizados; variante de botão secundário laranja
  nos temas escuros.
• Componentes de sidebar com `nav_contrast` parametrizável (padrão branco
  no item ativo); default do seletor de tema corrigido para o tema da sessão
  (antes sempre reiniciava em "claro"); marca alinhada em todos os temas;
  checkboxes/radios nativos pintados por tema.
• Preservado da 4.9.0: os 3 skins de sidebar (Claro, Azul, Laranja),
  heróis e cartões estáticos, cabeçalho sticky em tabelas, trava de tile
  longo, inversão de segurança título/ícone e Material Symbols com ligadura.
"""

from __future__ import annotations

import html as html_lib
import io
import json
import logging
import re
import unicodedata
from collections.abc import Callable, Sequence
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Protocol, TypeAlias, runtime_checkable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

logger = logging.getLogger(__name__)

_FUSO_BR = ZoneInfo("America/Sao_Paulo")


def _agora_br() -> datetime:
    return datetime.now(_FUSO_BR)


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
TemaSidebarType: TypeAlias = Literal["claro", "azul", "laranja", "padrao"]

BaseFormatter: TypeAlias = str | Callable[[object], str]
FmtDict: TypeAlias = dict[str, BaseFormatter | None]
ColorMapDict: TypeAlias = dict[str, str]


class TemaKPI(str, Enum):
    AZUL = "azul"
    VERDE = "verde"
    VERMELHO = "vermelho"
    LARANJA = "laranja"
    CINZA = "cinza"
    ROXO = "roxo"
    GRADIENTE = "gradiente"


class TemaSidebar(str, Enum):
    CLARO = "claro"
    AZUL = "azul"
    LARANJA = "laranja"
    PADRAO = "claro"


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


class Fontes:
    TITULO = "'Manrope', 'Segoe UI', Arial, sans-serif"
    TEXTO = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    CODIGO = "'JetBrains Mono', Consolas, 'Courier New', monospace"


class GoogleFonts:
    URLS: tuple[str, ...] = (
        "https://fonts.googleapis.com/icon?family=Material+Icons",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap",
    )


class Cores:
    PRIMARIA = "#012869"
    PRIMARIA_LIGHT = "#0A48AA"
    PRIMARIA_DARK = "#011838"
    SECUNDARIA = "#F37C04"
    SECUNDARIA_DARK = "#C2410C"
    SECUNDARIA_LIGHT = "#FDBA74"
    SUCESSO = "#047857"
    ALERTA = "#B91C1C"
    ATENCAO = "#B45309"
    NEUTRO = "#64748B"
    TEXTO = "#122033"
    TEXTO_2 = "#334155"
    TEXTO_3 = "#64748B"
    BORDA = "#E6EDF5"
    FUNDO = "#F3F6FB"
    LARANJA_SUAVE = "#FFEDD5"
    AZUL_SUAVE = "#E8EEF8"
    ROXO = "#6D28D9"
    ROXO_CLARO = "#A78BFA"
    VERDE_PME = "#0F766E"
    AZUL_PME = "#1D4ED8"


class ConfigCores:
    TEMA: dict[str, str] = {
        "azul": Cores.PRIMARIA,
        "verde": Cores.SUCESSO,
        "vermelho": Cores.ALERTA,
        "laranja": Cores.SECUNDARIA,
        "cinza": Cores.NEUTRO,
        "roxo": Cores.ROXO,
        "gradiente": Cores.PRIMARIA,
    }

    GRADIENTES: dict[str, tuple[str, str]] = {
        "azul": ("#011838", "#0A48AA"),
        "laranja": ("#9A3412", "#C2410C"),
        "verde": ("#064E3B", "#0F766E"),
        "vermelho": ("#7F1D1D", "#B91C1C"),
        "roxo": ("#4C1D95", "#6D28D9"),
        "cinza": ("#1E293B", "#334155"),
        "gradiente": ("#011838", "#9A3412"),
    }

    FUNDOS_SUAVES: dict[str, str] = {
        "azul": "#F4F7FC",
        "verde": "#F0FDF8",
        "vermelho": "#FEF2F2",
        "laranja": "#FFF7ED",
        "cinza": "#F8FAFC",
        "roxo": "#F5F3FF",
    }

    BADGE: dict[str, tuple[str, str, str]] = {
        "default": ("#F8FAFC", "#334155", "#E2E8F0"),
        "sucesso": ("#ECFDF5", "#065F46", "#A7F3D0"),
        "alerta": ("#FFFBEB", "#92400E", "#FDE68A"),
        "erro": ("#FEF2F2", "#991B1B", "#FECACA"),
        "info": ("#EFF6FF", "#1E3A8A", "#BFDBFE"),
        "roxo": ("#F5F3FF", "#5B21B6", "#DDD6FE"),
        "laranja": ("#FFF7ED", "#9A3412", "#FED7AA"),
    }

    PROGRESS_BAR: dict[str, str] = {
        "azul": Cores.PRIMARIA,
        "laranja": Cores.SECUNDARIA,
        "verde": Cores.SUCESSO,
        "vermelho": Cores.ALERTA,
        "roxo": Cores.ROXO,
        "gradiente": f"linear-gradient(90deg, {Cores.PRIMARIA} 0%, {Cores.SECUNDARIA} 100%)",
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
        "sucesso": ("#ECFDF5", "#065F46", "#059669", "✅"),
        "info": ("#EFF6FF", "#1E3A8A", "#2563EB", "ℹ️"),
        "alerta": ("#FFFBEB", "#92400E", "#D97706", "⚠️"),
        "erro": ("#FEF2F2", "#991B1B", "#DC2626", "❌"),
    }

    TIMELINE: dict[str, tuple[str, str, str]] = {
        "concluido": (Cores.SUCESSO, "#D1FAE5", "✓"),
        "em_andamento": (Cores.SECUNDARIA, "#FEF3C7", "⏳"),
        "pendente": (Cores.NEUTRO, "#F3F4F6", "○"),
        "cancelado": (Cores.ALERTA, "#FEE2E2", "✕"),
    }

    INSIGHT: dict[str, tuple[str, str, str, str]] = {
        "ok": ("#F0FDF8", "#065F46", "#059669", "✅"),
        "info": ("#F4F7FC", "#1E3A8A", "#2563EB", "ℹ️"),
        "alerta": ("#FFFBEB", "#92400E", "#D97706", "⚠️"),
        "critico": ("#FEF2F2", "#991B1B", "#DC2626", "🚨"),
        "acao": ("#F5F3FF", "#5B21B6", "#7C3AED", "💡"),
    }

    EMPTY_STATE: dict[str, tuple[str, str, str, str]] = {
        "dados": ("#F8FAFC", "#64748B", "📊", "Nenhum dado disponível"),
        "filtro": ("#F4F7FC", "#1E3A8A", "🔍", "Nenhum resultado encontrado"),
        "erro": ("#FEF2F2", "#B91C1C", "⚠️", "Ocorreu um erro"),
        "carregando": ("#F5F3FF", "#6D28D9", "⏳", "Carregando dados..."),
        "padrao": ("#F8FAFC", "#64748B", "📭", "Conteúdo não disponível"),
    }

    # Paleta centralizada e verificada dos 3 temas de sidebar (v5.0.0).
    # Cada cor abaixo passa pela verificação de contraste WCAG embutida
    # (ver: verificar_contrastes_sidebar / CLI `python components/componentes.py`).
    SIDEBAR: dict[str, dict[str, str]] = {
        "claro": {
            "fundo": "linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 50%, #F1F5F9 100%)",
            # base inferior do gradiente: #F1F5F9 (usado nos testes de contraste)
            "fundo_base": "#F1F5F9",
            "borda": "#E2E8F0",
            "texto_primario": "#011E52",
            "texto_secundario": "#475569",
            "icone": "#475569",
            "card_fundo": "#FFFFFF",
            "card_borda": "#E2E8F0",
            "nav_ativo_fundo": "#012869",
            "nav_ativo_texto": "#FFFFFF",
            "nav_passivo_texto": "#334155",
            "nav_passivo_hover_texto": "#011E52",
            "botao_fundo": "#F8FAFC",
            "botao_texto": "#011E52",
            "botao_hover_fundo": "#011E52",
            "botao_hover_texto": "#FFFFFF",
            "input_fundo": "#FFFFFF",
            "input_texto": "#0F172A",
            "input_borda": "#78879E",
            "input_focus": "#C2410C",
            "foco": "#C2410C",
            "accent_topo": "linear-gradient(90deg, #012869 0%, #0A48AA 65%, #F37C04 100%)",
        },
        "azul": {
            "fundo": "linear-gradient(180deg, #020C1B 0%, #061730 45%, #0B254A 100%)",
            "fundo_base": "#0B254A",
            "borda": "rgba(255, 255, 255, 0.10)",
            "texto_primario": "#FFFFFF",
            "texto_secundario": "#CBD5E1",
            "icone": "#94A3B8",
            "card_fundo": "rgba(255, 255, 255, 0.035)",
            "card_borda": "rgba(255, 255, 255, 0.10)",
            "nav_ativo_fundo": "linear-gradient(90deg, rgba(10, 72, 170, 0.45) 0%, rgba(10, 72, 170, 0.10) 100%)",
            "nav_ativo_texto": "#FFFFFF",
            "nav_passivo_texto": "#CBD5E1",
            "nav_passivo_hover_texto": "#FFFFFF",
            "botao_fundo": "rgba(255, 255, 255, 0.07)",
            "botao_texto": "#FFFFFF",
            "botao_hover_fundo": "#C2410C",
            "botao_hover_texto": "#FFFFFF",
            "input_fundo": "rgba(255, 255, 255, 0.05)",
            "input_texto": "#FFFFFF",
            "input_borda": "rgba(255, 255, 255, 0.42)",
            "input_focus": "#F37C04",
            "foco": "#F37C04",
            "accent_topo": "linear-gradient(90deg, #F37C04 0%, #FB923C 100%)",
        },
        "laranja": {
            "fundo": "linear-gradient(180deg, #160702 0%, #2A0F04 40%, #3E1606 75%, #541E09 100%)",
            "fundo_base": "#541E09",
            "borda": "rgba(243, 124, 4, 0.22)",
            "texto_primario": "#FFFFFF",
            "texto_secundario": "#FFEDD5",
            "icone": "#FED7AA",
            "card_fundo": "rgba(0, 0, 0, 0.22)",
            "card_borda": "rgba(255, 255, 255, 0.12)",
            "nav_ativo_fundo": "linear-gradient(90deg, rgba(243, 124, 4, 0.36) 0%, rgba(243, 124, 4, 0.10) 100%)",
            "nav_ativo_texto": "#FFFFFF",
            "nav_passivo_texto": "#FED7AA",
            "nav_passivo_hover_texto": "#FFFFFF",
            "botao_fundo": "rgba(255, 255, 255, 0.10)",
            "botao_texto": "#FFFFFF",
            "botao_hover_fundo": "#011838",
            "botao_hover_texto": "#FFFFFF",
            "input_fundo": "rgba(0, 0, 0, 0.24)",
            "input_texto": "#FFFFFF",
            "input_borda": "rgba(255, 255, 255, 0.42)",
            "input_focus": "#F37C04",
            "foco": "#F37C04",
            "accent_topo": "linear-gradient(90deg, #F37C04 0%, #FFB067 60%, #FFFFFF 100%)",
        },
    }

    PLOTLY_COLORWAY: list[str] = [
        Cores.PRIMARIA,
        Cores.SECUNDARIA,
        Cores.SUCESSO,
        Cores.ALERTA,
        "#6D28D9",
        "#0F766E",
        "#1D4ED8",
        "#B45309",
        "#334155",
        "#9A3412",
    ]


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


def normalizar_tema_sidebar(tema: Any) -> TemaSidebarType:
    s = normalizar_tipo(
        tema,
        {"claro", "azul", "laranja", "padrao"},
        "claro",
    )
    if s == "padrao":
        return "claro"
    return s  # type: ignore[return-value]


def definir_tema_sidebar(tema: TemaSidebarType | str) -> None:
    """Define o tema ativo da sidebar ('claro', 'azul' ou 'laranja') na sessão Streamlit.

    v5.0.0: sincroniza também o widget do `render_sidebar_theme_selector` (quando
    já existir) para que trocas programáticas de tema (botões, callbacks, URL)
    não sejam revertidas na execução seguinte pelo estado do selectbox.
    """
    tema_norm = normalizar_tema_sidebar(tema)
    st.session_state["_totale_sidebar_theme"] = tema_norm
    if st.session_state.get("_totale_sidebar_theme_select") != tema_norm:
        try:
            st.session_state["_totale_sidebar_theme_select"] = tema_norm
        except Exception:
            # Widget já instanciado nesta execução — a sincronização ocorre
            # naturalmente na próxima execução do script.
            logger.debug(
                "Seletor de tema não sincronizado em tempo real (tema=%s).", tema_norm
            )


def _obter_tema_sidebar(tema_param: Any = None) -> TemaSidebarType:
    """Obtém o tema da sidebar a partir do parâmetro explícito ou do session_state."""
    if tema_param is not None:
        return normalizar_tema_sidebar(tema_param)
    return normalizar_tema_sidebar(
        st.session_state.get("_totale_sidebar_theme", "claro")
    )


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
    """Remove tags HTML, normaliza acentuação e retorna a string em caixa alta."""
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
    """Converte uma coluna para datetime lendo sempre DIA/MÊS/ANO."""
    if serie is None or len(serie) == 0:
        return pd.Series(dtype="datetime64[ns]")

    if pd.api.types.is_datetime64_any_dtype(serie):
        return pd.to_datetime(serie, errors="coerce")

    resultado = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")

    try:
        numericos = pd.to_numeric(serie, errors="coerce")
    except (TypeError, ValueError):
        numericos = pd.Series(np.nan, index=serie.index)
    mask_serial = numericos.between(20_000, 80_000)
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
# VERIFICAÇÃO DE CORES DA SIDEBAR (WCAG 2.1) — NOVO NA 5.0.0
# =============================================================================
def _hex_para_rgb(cor: str) -> tuple[int, int, int] | None:
    """Converte '#RGB', '#RRGGBB' ou 'rgb(r,g,b)' para tupla (r, g, b)."""
    s = str(cor).strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", s)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    m = re.fullmatch(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})[^)]*\)", s)
    if m:
        r, g, b = (min(255, int(x)) for x in m.groups())
        return (r, g, b)
    return None


def _extrair_alpha(cor: str) -> float:
    """Retorna o alfa de 'rgba(...)' (1.0 para cores opacas)."""
    m = re.search(r"rgba\s*\([^)]*,\s*([0-9]*\.?[0-9]+)\s*\)", str(cor).strip())
    if m:
        return min(1.0, max(0.0, float(m.group(1))))
    return 1.0


def _compor_cor(cor: str, base: str) -> str | None:
    """Compõe uma cor (hex/rgb(a)) sobre uma base sólida e devolve '#RRGGBB'.

    Permite avaliar cores translúcidas (ex.: rgba(255,255,255,0.42)) contra o
    fundo em que realmente aparecem — essencial para os skins escuros.
    """
    rgb = _hex_para_rgb(cor)
    base_rgb = _hex_para_rgb(base)
    if rgb is None or base_rgb is None:
        return None
    a = _extrair_alpha(cor)
    if a >= 1.0:
        return "#%02X%02X%02X" % rgb
    comp = tuple(round(a * v + (1 - a) * b) for v, b in zip(rgb, base_rgb))
    return "#%02X%02X%02X" % comp


def _para_solidas(cor: str, base: str) -> list[str]:
    """Resolve uma cor em sólidos sobre `base`.

    - hex/rgb(a)  → 1 cor composta sobre a base;
    - gradiente   → cada stop composto sobre a base (avaliação do pior caso).
    """
    s = str(cor).strip()
    if "gradient(" in s:
        tokens = re.findall(r"#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)", s)
        solidas = []
        for tok in tokens:
            comp = _compor_cor(tok, base)
            if comp:
                solidas.append(comp)
        return solidas
    comp = _compor_cor(s, base)
    return [comp] if comp else []


def _luminancia(cor: str) -> float | None:
    """Luminância relativa (WCAG 2.1). None quando a cor não é sólida/parseável."""
    rgb = _hex_para_rgb(cor)
    if rgb is None:
        return None
    canais = []
    for v in rgb:
        c = v / 255.0
        canais.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canais
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(cor1: str, cor2: str) -> float | None:
    """Razão de contraste entre duas cores sólidas (1.0 a 21.0); None se indefinível."""
    l1 = _luminancia(cor1)
    l2 = _luminancia(cor2)
    if l1 is None or l2 is None:
        return None
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _contraste_par(fg: str, bg: str, base: str) -> float | None:
    """Contraste do pior caso de um par (foreground, background).

    Ambos são resolvidos para cores sólidas compostas sobre `base`; o fg
    translúcido é composto sobre cada variação do bg. Gradientes são
    avaliados stop a stop (pior caso).
    """
    fundos = _para_solidas(bg, base)
    if not fundos:
        return None
    razoes: list[float] = []
    for b in fundos:
        fgs = _para_solidas(fg, b)
        if not fgs:
            return None
        for f in fgs:
            r = _contraste(f, b)
            if r is None:
                return None
            razoes.append(r)
    return min(razoes) if razoes else None


def verificar_contrastes_sidebar(
    detalhar: bool = False,
    minimo: float = 4.5,
    minimo_ui: float = 3.0,
) -> list[dict[str, Any]]:
    """Verifica as cores dos 3 temas de sidebar contra os critérios WCAG AA.

    Cada par é avaliado com composição alpha sobre a base do tema e, quando
    aplicável, stop a stop em gradientes (pior caso). Cada item do relatório
    contém: tema, par, contraste, mínimo exigido, status
    ('ok', 'baixo', 'decorativo' ou 'nao_verificavel') e `aprovado`.

    Pares 'decorativos' (ex.: divisor estrutural da sidebar) são informativos
    e não reprova o tema — bordas de controles (inputs) seguem 3:1 (WCAG 1.4.11).

    Uso:
        >>> relatorio = verificar_contrastes_sidebar()
        >>> falhas = [r for r in relatorio if not r["aprovado"]]
    """
    pares: list[dict[str, Any]] = []
    for tema, pal in ConfigCores.SIDEBAR.items():
        fundo = pal.get("fundo_base", "")
        cfg: list[tuple[str, str, str, float, bool]] = [
            (
                "texto primário vs fundo",
                pal.get("texto_primario", ""),
                fundo,
                minimo,
                False,
            ),
            (
                "texto secundário vs fundo",
                pal.get("texto_secundario", ""),
                fundo,
                minimo,
                False,
            ),
            ("ícone vs fundo", pal.get("icone", ""), fundo, minimo, False),
            (
                "nav passivo vs fundo",
                pal.get("nav_passivo_texto", ""),
                fundo,
                minimo,
                False,
            ),
            (
                "nav passivo hover vs fundo",
                pal.get("nav_passivo_hover_texto", ""),
                fundo,
                minimo,
                False,
            ),
            (
                "nav ativo vs fundo",
                pal.get("nav_ativo_texto", ""),
                pal.get("nav_ativo_fundo", ""),
                minimo,
                False,
            ),
            (
                "botão vs fundo",
                pal.get("botao_texto", ""),
                pal.get("botao_fundo", ""),
                minimo,
                False,
            ),
            (
                "botão hover vs fundo",
                pal.get("botao_hover_texto", ""),
                pal.get("botao_hover_fundo", ""),
                minimo,
                False,
            ),
            (
                "input texto vs input fundo",
                pal.get("input_texto", ""),
                pal.get("input_fundo", ""),
                minimo,
                False,
            ),
            (
                "input borda vs fundo (UI)",
                pal.get("input_borda", ""),
                fundo,
                minimo_ui,
                False,
            ),
            (
                "input borda vs input fundo (UI)",
                pal.get("input_borda", ""),
                pal.get("input_fundo", ""),
                minimo_ui,
                False,
            ),
            ("foco vs fundo (UI)", pal.get("foco", ""), fundo, minimo_ui, False),
            ("borda da sidebar vs fundo", pal.get("borda", ""), fundo, 0.0, True),
        ]
        for rotulo, fg, bg, min_req, decorativo in cfg:
            ratio = _contraste_par(fg, bg, fundo)
            if decorativo:
                status = "decorativo"
                aprovado = True
            elif ratio is None:
                status = "nao_verificavel"
                aprovado = True
            else:
                aprovado = ratio >= min_req
                status = "ok" if aprovado else "baixo"
            pares.append(
                {
                    "tema": tema,
                    "par": rotulo,
                    "fg": fg,
                    "bg": bg,
                    "contraste": ratio,
                    "minimo": min_req,
                    "status": status,
                    "aprovado": aprovado,
                }
            )

    falhas = [p for p in pares if not p["aprovado"]]
    if detalhar or falhas:
        largura = max((len(p["par"]) for p in pares), default=40)
        print("Verificação de contraste da sidebar — Design System TOTALE (WCAG AA)")
        print("(cores alpha/gradiente compostas sobre a base do tema; pior caso)")
        print("-" * (largura + 52))
        atual = None
        for p in pares:
            if p["tema"] != atual:
                atual = p["tema"]
                print(f"\n[{atual.upper()}]")
            ratio = p["contraste"]
            ratio_txt = f"{ratio:.2f}:1" if ratio is not None else "   n/d  "
            flag = {
                "ok": "OK ",
                "baixo": "BAIXO",
                "nao_verificavel": "n/d",
                "decorativo": "INFO",
            }[p["status"]]
            min_txt = (
                "decor." if p["status"] == "decorativo" else f"mín {p['minimo']:.1f}:1"
            )
            print(
                f"  {flag:<7} {p['par']:<{largura}}  {ratio_txt}"
                f"  ({min_txt})  {p['fg']} / {p['bg']}"
            )
        print("-" * (largura + 52))
        total = len(pares)
        ok = sum(1 for p in pares if p["status"] == "ok")
        dec = sum(1 for p in pares if p["status"] == "decorativo")
        nver = sum(1 for p in pares if p["status"] == "nao_verificavel")
        print(
            f"Resumo: {total} verificações | {ok} OK | {len(falhas)} abaixo do mínimo"
            f" | {dec} decorativas | {nver} não verificável(is)\n"
        )
        if falhas:
            print("!! Ajustar cores com contraste abaixo do mínimo WCAG AA.")
        else:
            print("Todos os pares obrigatórios atendem ao mínimo WCAG AA.")
    return pares


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
    clean = html_str.strip()

    # st.html (Streamlit 1.64+): injeção pura no DOM da página, sem iframe,
    # sanitizada com DOMPurify — preserva <style> e atributos style/data-*.
    if hasattr(c, "html"):
        try:
            c.html(clean)
            return
        except Exception:
            pass

    clean_md = clean.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    clean_md = re.sub(r">\s+<", "><", clean_md)
    clean_md = re.sub(r" {2,}", " ", clean_md).strip()
    try:
        c.markdown(clean_md, unsafe_allow_html=True)
    except Exception as exc:
        logger.error("Falha ao renderizar HTML customizado: %s", exc)
        try:
            st.markdown(clean_md, unsafe_allow_html=True)
        except Exception:
            pass


def _texto_icone_seguro(icone: str) -> str:
    """Trava da 4.7.1: texto longo com espaço não estoura o tile."""
    texto = str(icone or "").strip()
    if len(texto) > 15 and " " in texto:
        return texto[0]
    return texto


def _injetar_js(html: str) -> None:
    """Executa um snippet `<script>` no documento da aplicação.

    v5.0.0: prefere `st.html(unsafe_allow_javascript=True)` (Streamlit ≥ 1.64,
    substituto de `components.html`, deprecado após 2026-06-01): o script roda
    direto no documento real da app, sem iframe. Fallback automático para
    `components.html` (iframe de mesma origem) em versões anteriores.

    Os templates JS usam os placeholders `__DOC__`/`__WIN__` para se ajustar
    ao modo de injeção:
      - st.html         → `document` / `window`
      - components.html → `window.parent.document` / `window.parent`
    """
    fn = getattr(st, "html", None)
    if fn is not None:
        try:
            fn(
                html.replace("__DOC__", "document").replace("__WIN__", "window"),
                unsafe_allow_javascript=True,
            )
            return
        except Exception:
            logger.debug(
                "st.html com JS indisponível/falhou; usando components.html.",
                exc_info=True,
            )
    components.html(
        html.replace("__DOC__", "window.parent.document").replace(
            "__WIN__", "window.parent"
        ),
        height=0,
    )


def _icone_tile(icone: str, variante: str = "section") -> str:
    texto = _texto_icone_seguro(icone)
    if not texto:
        return ""
    variante_norm = variante if variante in {"section", "brand"} else "section"
    return (
        f'<span class="totale-icon-tile totale-icon-tile--{variante_norm}" '
        'aria-hidden="true">'
        '<span class="totale-icon-glyph">'
        f"{Validadores.html_escape(texto)}"
        "</span></span>"
    )


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
    --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px;
    --shadow-sm: 0 1px 2px rgba(15,23,42,0.04);
    --shadow-md: 0 8px 24px rgba(15,23,42,0.06);
    --shadow-lg: 0 18px 40px rgba(1,24,56,0.16);
}}
"""

_CSS_RESET_GLOBAL = """
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stSidebar"], p, label, div, li, a, button, input, select, textarea {
    font-family: var(--font-texto) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
h1, h2, h3, h4, h5, h6, .hero-title, .section-title, .kpi-value, .metric-value,
[data-testid="stMetricValue"] {
    font-family: var(--font-titulo) !important;
    font-weight: 750;
    letter-spacing: -0.03em;
}
::selection { background: rgba(243,124,4,0.22); color: #011838; }
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(900px 380px at 100% -8%, rgba(243,124,4,0.07), transparent 55%),
        radial-gradient(760px 360px at -8% -4%, rgba(1,40,105,0.06), transparent 50%),
        #F3F6FB !important;
}
[data-testid="stHeader"] {
    background: rgba(243,246,251,0.86) !important;
    backdrop-filter: blur(10px);
}
[data-testid="stDecoration"] { display: none !important; }
footer[data-testid="stFooter"] { display: none !important; }
.main .block-container { padding-top: 1.15rem; padding-bottom: 3.2rem; max-width: 1240px; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #D5DEEA; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
*:focus-visible { outline: 2px solid #C2410C; outline-offset: 2px; border-radius: 6px; }
"""

_CSS_HEROS = """
.hero-corp, .totale-hero-1, .totale-hero-2, .hero-migracao, .hero-pme, .hero-domicilios {
    position: relative; overflow: hidden; isolation: isolate; color: #fff;
    border-radius: 18px; margin-bottom: 22px;
    box-shadow: 0 16px 36px rgba(1,24,56,0.18);
}
.hero-corp::before, .totale-hero-1::before, .hero-migracao::before,
.hero-pme::before, .hero-domicilios::before, .totale-hero-2::before {
    content: ""; position: absolute; inset: 0; pointer-events: none; z-index: 0;
    background-image:
        linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
    background-size: 28px 28px;
    mask-image: linear-gradient(90deg, transparent 10%, #000 78%);
}
.hero-corp::after, .totale-hero-1::after, .hero-migracao::after,
.hero-pme::after, .hero-domicilios::after {
    content: ""; position: absolute; right: -80px; top: -90px; width: 280px; height: 280px;
    border-radius: 50%; pointer-events: none; z-index: 0;
    background: radial-gradient(circle, rgba(243,124,4,0.38), transparent 68%);
}
.hero-corp {
    background: linear-gradient(125deg, #011838 0%, #012869 46%, #0A3F96 100%);
    padding: 32px 40px; border: 1px solid rgba(255,255,255,0.08);
}
.hero-title { font-size: clamp(26px, 3vw, 36px); font-weight: 800; color: #fff; margin: 0 0 8px; line-height: 1.08; position: relative; z-index: 2; }
.hero-subtitle { font-size: 15px; color: rgba(255,255,255,0.78); margin: 0; line-height: 1.55; position: relative; z-index: 2; max-width: 68ch; }
.hero-badge, .th-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.18);
    color: #fff; font-size: 10px; font-weight: 750; letter-spacing: 0.12em;
    text-transform: uppercase; padding: 5px 11px; border-radius: 999px; position: relative; z-index: 2;
}
.hero-content, .totale-hero-1 > div, .hero-migracao > div, .hero-pme > div, .hero-domicilios > div { position: relative; z-index: 2; }
.totale-hero-1 {
    background: linear-gradient(128deg, #011838 0%, #012869 52%, #123E86 100%);
    padding: 30px 36px; border: 1px solid rgba(243,124,4,0.28);
}
.totale-hero-2 {
    background: linear-gradient(120deg, #012869 0%, #03306F 100%);
    padding: 28px 32px; border-left: 4px solid #F37C04;
    display: grid; grid-template-columns: 1fr auto; gap: 22px; align-items: center;
}
@media (max-width: 768px) { .totale-hero-2 { grid-template-columns: 1fr; } .hero-corp, .totale-hero-1 { padding: 24px 20px; } }
.totale-hero-2-card {
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.14);
    border-radius: 14px; padding: 14px 20px; min-width: 168px; text-align: center; position: relative; z-index: 2;
}
.hero-migracao { background: linear-gradient(128deg, #3B0764 0%, #5B21B6 58%, #6D28D9 100%); padding: 30px 36px; }
.hero-pme { background: linear-gradient(128deg, #064E3B 0%, #0F766E 52%, #1D4ED8 140%); padding: 30px 36px; }
.hero-domicilios { background: linear-gradient(128deg, #011838 0%, #0F3D5E 48%, #0F766E 120%); padding: 30px 36px; }
.th-title-lg, .th-title { color: #fff; margin: 12px 0 8px; line-height: 1.08; letter-spacing: -0.03em; position: relative; z-index: 2; }
.th-title-lg { font-size: clamp(24px, 2.6vw, 34px); font-weight: 800; }
.th-title { font-size: clamp(22px, 2.2vw, 30px); font-weight: 800; }
.th-sub, .th-sub-muted { font-size: 14.5px; color: rgba(255,255,255,0.78); margin: 0; line-height: 1.55; position: relative; z-index: 2; }
.th-meta, .th-tag { font-size: 12px; color: rgba(255,255,255,0.62); position: relative; z-index: 2; }
.th-tag { margin-left: 8px; }
.th-card-label { font-size: 10px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(255,255,255,0.68); margin-bottom: 4px; }
.th-card-value { font-size: 28px; font-weight: 800; color: #FDBA74; line-height: 1; letter-spacing: -0.03em; }
.totale-badge-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
"""

_CSS_CARDS = """
.card-premium {
    background: #fff; border-radius: 14px; padding: 18px 20px; border: 1px solid #E6EDF5;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04), 0 10px 24px rgba(15,23,42,0.04);
    margin-bottom: 12px; position: relative; overflow: hidden;
    display: flex; flex-direction: column; justify-content: space-between; min-height: 132px;
    transition: transform .2s ease, box-shadow .2s ease;
}
.card-premium:hover { transform: translateY(-2px); box-shadow: 0 12px 28px rgba(15,23,42,0.08); }
.card-premium-colorida { border-color: rgba(255,255,255,0.14); }
.card-premium-colorida::after {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: linear-gradient(180deg, rgba(255,255,255,0.16), transparent 36%);
}
.card-accent-top { position: absolute; top: 0; left: 0; right: 0; height: 3px; z-index: 2; }
.card-header-flex { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 14px; position: relative; z-index: 2; }
.kpi-label-premium { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; line-height: 1.35; }
.kpi-icon-wrapper { display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0; }
.kpi-value-premium { font-size: 30px; font-weight: 800; line-height: 1; letter-spacing: -0.04em; font-variant-numeric: tabular-nums; font-family: var(--font-titulo) !important; position: relative; z-index: 2; }
.kpi-sub-premium { font-size: 12.5px; margin-top: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; position: relative; z-index: 2; opacity: 0.9; }
.trend-pill { display: inline-flex; align-items: center; gap: 3px; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 750; line-height: 1; background: rgba(255,255,255,0.16); }
.trend-up { background: #ECFDF5; color: #047857; }
.trend-down { background: #FEF2F2; color: #B91C1C; }
.trend-neutral { background: #F8FAFC; color: #64748B; }
"""

_CSS_TABELAS = """
.table-premium-wrapper {
    color-scheme: light !important; background: #fff !important; border-radius: 14px !important;
    border: 1px solid #E6EDF5 !important; box-shadow: 0 8px 24px rgba(15,23,42,0.04) !important;
    overflow: hidden !important; margin: 8px 0 18px !important;
}
.table-premium-scroll { width: 100% !important; overflow: auto !important; background: #fff !important; scrollbar-width: thin; }
.totale-table-pro { width: 100% !important; border-collapse: separate !important; border-spacing: 0 !important; text-align: left !important; background: #fff !important; }
.totale-table-pro thead th {
    position: sticky; top: 0; z-index: 2;
    background: #F8FAFC !important; color: #012869 !important;
    font-family: var(--font-titulo) !important; font-size: 10.5px !important; font-weight: 800 !important;
    letter-spacing: 0.08em !important; text-transform: uppercase !important;
    padding: 12px 14px !important; border-bottom: 1px solid #E6EDF5 !important; white-space: nowrap !important;
}
.totale-table-pro thead th:first-child { box-shadow: inset 3px 0 0 #F37C04; }
.totale-table-pro td {
    padding: 11px 14px !important; border-bottom: 1px solid #F1F5F9 !important;
    color: #1E293B !important; font-size: 12.5px !important; line-height: 1.45 !important;
    vertical-align: middle !important; background: #fff !important;
    overflow-wrap: anywhere;
}
.totale-table-pro tbody tr.striped td { background: #F8FAFC !important; }
.totale-table-pro tbody tr:hover td { background: #F4F7FC !important; }
.totale-table-pro tbody tr.linha-destaque td {
    background: #FFF7ED !important; color: #7C2D12 !important; font-weight: 700 !important;
    box-shadow: inset 3px 0 0 #F37C04;
}
.td-badge-ok, .td-badge-alerta, .td-badge-neutro {
    display: inline-flex !important; align-items: center !important;
    padding: 2px 8px !important; border-radius: 999px !important;
    font-size: 10.5px !important; font-weight: 750 !important; letter-spacing: 0.04em !important;
}
.td-badge-ok { background: #ECFDF5 !important; color: #065F46 !important; }
.td-badge-alerta { background: #FEF2F2 !important; color: #991B1B !important; }
.td-badge-neutro { background: #F1F5F9 !important; color: #334155 !important; }
"""

_CSS_EXTRAS = """
@keyframes pb-shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
.totale-pb-fill { position: relative; overflow: hidden; }
.totale-pb-fill.animado::after {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.35) 50%, transparent 70%);
    background-size: 200% 100%; animation: pb-shimmer 2.4s linear infinite;
}
.totale-skeleton { background: linear-gradient(90deg, #F1F5F9 25%, #E2E8F0 50%, #F1F5F9 75%); background-size: 200% 100%; animation: pb-shimmer 1.4s linear infinite; border-radius: 8px; }
.empty-state {
    display: flex; flex-direction: column; align-items: center; text-align: center;
    padding: 42px 28px; margin: 18px 0; background: #fff; border: 1px dashed #D5DEEA; border-radius: 16px;
}
.empty-state-icon { font-size: 32px; line-height: 1; margin-bottom: 10px; }
.empty-state-title { font-family: var(--font-titulo) !important; font-size: 16px; font-weight: 800; color: #122033; margin: 0 0 6px; }
.empty-state-desc { font-size: 13px; color: #64748B; margin: 0; max-width: 440px; line-height: 1.55; }
.totale-insight {
    display: flex; align-items: flex-start; gap: 12px;
    border-radius: 12px; padding: 12px 14px; margin: 10px 0;
    border: 1px solid transparent; box-shadow: none;
}
.totale-insight-icon {
    width: 28px; height: 28px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center;
    background: rgba(255,255,255,0.72); flex-shrink: 0; font-size: 14px; line-height: 1;
}
.totale-insight-title { display: block; font-weight: 800; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 2px; }
.section-header { display: flex; align-items: flex-start; gap: 10px; margin: 26px 0 12px; padding-bottom: 10px; border-bottom: 1px solid #E6EDF5; }
.section-title { font-size: clamp(18px, 2vw, 22px); font-weight: 800; color: #012869; margin: 0; line-height: 1.15; letter-spacing: -0.03em; }
.section-subtitle { margin: 4px 0 0; font-size: 13px; color: #64748B; }
.section-header-copy { flex: 1; min-width: 0; }
.totale-icon-tile {
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    flex-shrink: 0 !important; background: none !important; border: none !important;
    box-shadow: none !important; padding: 0 !important; line-height: 1 !important; overflow: visible !important;
}
.totale-icon-tile--brand, .totale-icon-tile--section { width: auto !important; height: auto !important; min-width: 24px !important; }
.totale-icon-glyph {
    display: inline-flex !important; align-items: center !important; justify-content: center !important;
    background: none !important; color: initial !important; -webkit-text-fill-color: initial !important;
    font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons",
                 "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif !important;
    font-style: normal !important; font-weight: 400 !important; line-height: 1 !important;
    font-feature-settings: "liga" 1 !important; font-variant-ligatures: common-ligatures !important;
    letter-spacing: normal !important; white-space: nowrap !important; text-transform: none !important;
}
.totale-icon-tile--brand .totale-icon-glyph { font-size: 22px !important; }
.totale-icon-tile--section .totale-icon-glyph { font-size: 22px !important; }
.totale-icon-tile:empty, .totale-icon-glyph:empty { display: none !important; }
.sidebar-brand { padding: 2px 2px 14px; margin-bottom: 8px; }
.sidebar-brand-name {
    font-family: var(--font-titulo); font-size: 18px; font-weight: 800; letter-spacing: -0.03em;
    margin: 0; line-height: 1.1;
    color: #011E52;
    background: linear-gradient(100deg, #012869 10%, #0A48AA 62%, #F37C04 140%);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.sidebar-brand-sub { font-size: 11px; color: #475569; margin-top: 3px; letter-spacing: 0.01em; }
.sidebar-section-header { margin: 16px 0 6px; padding: 4px 0 8px 12px; position: relative; }
.sidebar-section-header::before {
    content: ""; position: absolute; left: 0; top: 6px; width: 3px; height: 12px; border-radius: 99px; background: #F37C04;
}
.sidebar-footer { margin-top: 22px; padding: 12px 4px 6px; border-top: 1px solid #E6EDF5; }
"""

_CSS_STREAMLIT_CHROME = """
div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button,
div[data-testid="stFormSubmitButton"] > button,
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-secondary"] {
    border-radius: 10px !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
    border: 1px solid #E6EDF5 !important;
    transition: background .16s ease, box-shadow .16s ease, transform .16s ease !important;
}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background: #012869 !important; color: #fff !important; border-color: #012869 !important;
    box-shadow: 0 1px 2px rgba(1,40,105,0.18) !important;
}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
    background: #011838 !important; border-color: #F37C04 !important;
    box-shadow: 0 6px 16px rgba(1,40,105,0.22) !important;
}
button[kind="primary"]:disabled, button[data-testid="stBaseButton-primary"]:disabled {
    background: #94A3B8 !important; border-color: #94A3B8 !important;
    color: #F8FAFC !important; box-shadow: none !important; cursor: not-allowed !important;
}
button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover,
div[data-testid="stDownloadButton"] > button:hover {
    border-color: #012869 !important; color: #012869 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 4px; border-bottom: 1px solid #E6EDF5;
}
[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-weight: 650 !important; color: #64748B !important; background: transparent !important;
}
[data-testid="stTabs"] button[aria-selected="true"] { color: #012869 !important; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: #F37C04 !important; height: 2px !important; }
[data-testid="stMetric"] {
    background: #fff; border: 1px solid #E6EDF5; border-radius: 14px;
    padding: 14px 16px 12px; box-shadow: 0 8px 20px rgba(15,23,42,0.04);
}
[data-testid="stMetricLabel"] {
    color: #64748B !important; font-size: 11px !important; font-weight: 700 !important;
    letter-spacing: 0.06em !important; text-transform: uppercase !important;
}
[data-testid="stMetricValue"] { color: #012869 !important; letter-spacing: -0.03em !important; }
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
    border-radius: 10px !important; border-color: #E6EDF5 !important; background: #fff !important;
}
[data-testid="stExpander"] details {
    border: 1px solid #E6EDF5 !important; border-radius: 12px !important; background: #fff !important;
}
[data-testid="stStatusWidget"] { border-radius: 12px !important; }
[data-testid="stAlert"] { border-radius: 12px !important; }
"""

# =============================================================================
# CSS ESPECÍFICO DOS 3 TIPOS DE SIDEBAR (CLARO, AZUL E LARANJA)
# v5.0.0: contraste verificado (WCAG AA), inputs com borda de contraste,
# checkbox/radio pintados, foco visível, scrollbars e botões desabilitados.
# =============================================================================
_CSS_SIDEBAR_CLARO = """
[data-testid="stSidebar"] {
    position: relative;
    background: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 50%, #F1F5F9 100%) !important;
    border-right: 1px solid #E2E8F0 !important;
}
[data-testid="stSidebar"]::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2.5px; z-index: 100;
    background: linear-gradient(90deg, #012869 0%, #0A48AA 65%, #F37C04 100%);
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 12px; }
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {
    font-size: 10px !important; font-weight: 800 !important; letter-spacing: 0.1em !important;
    text-transform: uppercase !important; color: #475569 !important; padding: 10px 12px 6px 14px !important;
}
[data-testid="stSidebarNav"] a {
    border-radius: 8px !important; color: #334155 !important; font-weight: 550 !important;
    font-size: 13px !important; border: 1px solid transparent !important;
    border-left: 3px solid transparent !important;
    transition: background 0.15s ease, color 0.15s ease !important;
}
[data-testid="stSidebarNav"] a:hover {
    background: #F1F5F9 !important; color: #011E52 !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: #012869 !important; color: #FFFFFF !important; font-weight: 700 !important;
    border: 1px solid #011E52 !important;
    border-left: 3px solid #F37C04 !important;
    box-shadow: 0 2px 8px rgba(1, 40, 105, 0.16) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: #FFFFFF !important; }
/* Widgets nativos na sidebar clara — borda com contraste mínimo 3:1 (WCAG 1.4.11) */
[data-testid="stSidebar"] div[data-baseweb="select"] > div,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    background: #FFFFFF !important;
    border: 1px solid #78879E !important;
    color: #0F172A !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover,
[data-testid="stSidebar"] input:hover {
    border-color: #012869 !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within,
[data-testid="stSidebar"] input:focus,
[data-testid="stSidebar"] textarea:focus {
    border-color: #C2410C !important;
    box-shadow: 0 0 0 2px rgba(194, 65, 12, 0.28) !important;
    outline: none !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] span { color: #0F172A !important; }
[data-testid="stSidebar"] div[data-baseweb="select"] svg { fill: #475569 !important; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"] span,
[data-testid="stSidebar"] label[data-baseweb="radio"] span { color: #334155 !important; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"] [data-baseweb="checkbox--checkmark"],
[data-testid="stSidebar"] label[data-baseweb="radio"] [data-baseweb="radio--circle"] {
    border-color: #475569 !important;
}
[data-testid="stSidebar"] label[data-baseweb="checkbox"] input:checked + div,
[data-testid="stSidebar"] label[data-baseweb="checkbox"] [data-baseweb="checkbox--checkmark"] {
    border-color: #012869 !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    color: #011E52 !important;
    border-radius: 8px !important;
    font-weight: 650 !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background: #011E52 !important;
    border-color: #011E52 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(1, 40, 105, 0.18) !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled {
    background: #F1F5F9 !important;
    border-color: #E2E8F0 !important;
    color: #94A3B8 !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary { color: #011E52 !important; font-weight: 700 !important; }
[data-testid="stSidebar"] hr { border-color: #E2E8F0 !important; }
[data-testid="stSidebar"] *::-webkit-scrollbar { width: 8px; height: 8px; }
[data-testid="stSidebar"] *::-webkit-scrollbar-track { background: transparent; }
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 99px; }
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
[data-testid="stSidebar"] .sidebar-brand-name {
    color: #011E52 !important;
    background: linear-gradient(100deg, #012869 10%, #0A48AA 62%, #F37C04 140%) !important;
    -webkit-background-clip: text !important; background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
}
[data-testid="stSidebar"] .sidebar-brand-sub { color: #475569 !important; }
[data-testid="stSidebar"] .sidebar-section-header::before { background: #F37C04 !important; }
[data-testid="stSidebar"] .sidebar-footer { border-top: 1px solid #E2E8F0 !important; }
[data-testid="stSidebar"]:focus-within *:focus-visible { outline-color: #C2410C !important; }
"""

_CSS_SIDEBAR_AZUL = """
[data-testid="stSidebar"] {
    position: relative;
    background: linear-gradient(180deg, #020C1B 0%, #061730 45%, #0B254A 100%) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.10) !important;
    color: #CBD5E1 !important;
}
[data-testid="stSidebar"]::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2.5px; z-index: 100;
    background: linear-gradient(90deg, #F37C04 0%, #FB923C 100%);
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 12px; }
/* Cor de texto de base do tema (regras de widgets abaixo sobrescrevem com !important) */
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] li, [data-testid="stSidebar"] .stMarkdown {
    color: #CBD5E1 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4, [data-testid="stSidebar"] strong {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {
    color: #94A3B8 !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {
    background: rgba(255, 255, 255, 0.08) !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {
    font-size: 10px !important; font-weight: 800 !important; letter-spacing: 0.12em !important;
    text-transform: uppercase !important; color: #94A3B8 !important; padding: 10px 12px 6px 14px !important;
}
[data-testid="stSidebarNav"] a {
    border-radius: 8px !important; color: #CBD5E1 !important; font-weight: 550 !important;
    font-size: 13px !important; border: 1px solid transparent !important;
    border-left: 3px solid transparent !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebarNav"] a:hover {
    background: rgba(255, 255, 255, 0.07) !important; color: #FFFFFF !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    /* Preenchimento em azul de marca (antes: laranja sobre navy = marrom sujo) */
    background: linear-gradient(90deg, rgba(10, 72, 170, 0.45) 0%, rgba(10, 72, 170, 0.10) 100%) !important;
    border: 1px solid rgba(243, 124, 4, 0.16) !important;
    border-left: 3px solid #F37C04 !important;
    color: #FFFFFF !important; font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: #FFFFFF !important; }
/* Widgets Streamlit nativos na Sidebar Azul */
[data-testid="stSidebar"] div[data-baseweb="select"] > div,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.42) !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover,
[data-testid="stSidebar"] input:hover {
    border-color: #F37C04 !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within,
[data-testid="stSidebar"] input:focus,
[data-testid="stSidebar"] textarea:focus {
    border-color: #F37C04 !important;
    box-shadow: 0 0 0 2px rgba(243, 124, 4, 0.30) !important;
    outline: none !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] span { color: #FFFFFF !important; }
[data-testid="stSidebar"] div[data-baseweb="select"] svg { fill: #94A3B8 !important; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"] span,
[data-testid="stSidebar"] label[data-baseweb="radio"] span { color: #CBD5E1 !important; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"] [data-baseweb="checkbox--checkmark"],
[data-testid="stSidebar"] label[data-baseweb="radio"] [data-baseweb="radio--circle"] {
    border-color: rgba(255, 255, 255, 0.55) !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background: rgba(255, 255, 255, 0.07) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255, 255, 255, 0.18) !important;
    border-radius: 8px !important;
    font-weight: 650 !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background: #C2410C !important;
    border-color: #C2410C !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(194, 65, 12, 0.35) !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled {
    background: rgba(255, 255, 255, 0.05) !important;
    border-color: rgba(255, 255, 255, 0.10) !important;
    color: #94A3B8 !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
    background: rgba(255, 255, 255, 0.035) !important;
    border: 1px solid rgba(255, 255, 255, 0.10) !important;
    border-radius: 10px !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary { color: #FFFFFF !important; font-weight: 700 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255, 255, 255, 0.12) !important; }
[data-testid="stSidebar"] *::-webkit-scrollbar { width: 8px; height: 8px; }
[data-testid="stSidebar"] *::-webkit-scrollbar-track { background: transparent; }
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.22); border-radius: 99px; }
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb:hover { background: rgba(243, 124, 4, 0.65); }
[data-testid="stSidebar"] .sidebar-brand-name {
    color: #FFFFFF !important;
    background: linear-gradient(100deg, #FFFFFF 20%, #FDBA74 100%) !important;
    -webkit-background-clip: text !important; background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
}
[data-testid="stSidebar"] .sidebar-brand-sub { color: #CBD5E1 !important; }
[data-testid="stSidebar"] .sidebar-section-header::before { background: #F37C04 !important; }
[data-testid="stSidebar"] .sidebar-footer { border-top: 1px solid rgba(255, 255, 255, 0.10) !important; }
[data-testid="stSidebar"]:focus-within *:focus-visible { outline-color: #F37C04 !important; }
"""

_CSS_SIDEBAR_LARANJA = """
[data-testid="stSidebar"] {
    position: relative;
    background: linear-gradient(180deg, #160702 0%, #2A0F04 40%, #3E1606 75%, #541E09 100%) !important;
    border-right: 1px solid rgba(243, 124, 4, 0.22) !important;
    color: #FFEDD5 !important;
}
[data-testid="stSidebar"]::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2.5px; z-index: 100;
    background: linear-gradient(90deg, #F37C04 0%, #FFB067 60%, #FFFFFF 100%);
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 12px; }
/* Cor de texto de base do tema (regras de widgets abaixo sobrescrevem com !important) */
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] li, [data-testid="stSidebar"] .stMarkdown {
    color: #FFEDD5 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4, [data-testid="stSidebar"] strong {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {
    color: #FED7AA !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {
    background: rgba(255, 255, 255, 0.10) !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] {
    font-size: 10px !important; font-weight: 800 !important; letter-spacing: 0.12em !important;
    text-transform: uppercase !important; color: #FDBA74 !important; padding: 10px 12px 6px 14px !important;
    opacity: 0.95;
}
[data-testid="stSidebarNav"] a {
    border-radius: 8px !important; color: #FED7AA !important; font-weight: 550 !important;
    font-size: 13px !important; border: 1px solid transparent !important;
    border-left: 3px solid transparent !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebarNav"] a:hover {
    background: rgba(255, 255, 255, 0.08) !important; color: #FFFFFF !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    /* Fill âmbar mais legível + barra âmbar clara (antes: contorno laranja fechado em volta toda) */
    background: linear-gradient(90deg, rgba(243, 124, 4, 0.36) 0%, rgba(243, 124, 4, 0.10) 100%) !important;
    border: 1px solid rgba(255, 176, 103, 0.18) !important;
    border-left: 3px solid #FFB067 !important;
    color: #FFFFFF !important; font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.40) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: #FFFFFF !important; }
/* Widgets Streamlit nativos na Sidebar Laranja Terracotta */
[data-testid="stSidebar"] div[data-baseweb="select"] > div,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    background: rgba(0, 0, 0, 0.24) !important;
    border: 1px solid rgba(255, 255, 255, 0.42) !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover,
[data-testid="stSidebar"] input:hover {
    border-color: #F37C04 !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within,
[data-testid="stSidebar"] input:focus,
[data-testid="stSidebar"] textarea:focus {
    border-color: #F37C04 !important;
    box-shadow: 0 0 0 2px rgba(243, 124, 4, 0.32) !important;
    outline: none !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] span { color: #FFFFFF !important; }
[data-testid="stSidebar"] div[data-baseweb="select"] svg { fill: #FED7AA !important; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"] span,
[data-testid="stSidebar"] label[data-baseweb="radio"] span { color: #FFEDD5 !important; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"] [data-baseweb="checkbox--checkmark"],
[data-testid="stSidebar"] label[data-baseweb="radio"] [data-baseweb="radio--circle"] {
    border-color: rgba(255, 255, 255, 0.60) !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background: rgba(255, 255, 255, 0.10) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255, 255, 255, 0.20) !important;
    border-radius: 8px !important;
    font-weight: 650 !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background: #011838 !important;
    border-color: #F37C04 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35) !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled {
    background: rgba(255, 255, 255, 0.06) !important;
    border-color: rgba(255, 255, 255, 0.12) !important;
    color: rgba(255, 255, 255, 0.55) !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
    background: rgba(0, 0, 0, 0.20) !important;
    border: 1px solid rgba(255, 255, 255, 0.14) !important;
    border-radius: 10px !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary { color: #FFFFFF !important; font-weight: 700 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255, 255, 255, 0.16) !important; }
[data-testid="stSidebar"] *::-webkit-scrollbar { width: 8px; height: 8px; }
[data-testid="stSidebar"] *::-webkit-scrollbar-track { background: transparent; }
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.24); border-radius: 99px; }
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb:hover { background: rgba(243, 124, 4, 0.75); }
[data-testid="stSidebar"] .sidebar-brand-name {
    color: #FFFFFF !important;
    background: none !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
[data-testid="stSidebar"] .sidebar-brand-sub { color: #FED7AA !important; }
[data-testid="stSidebar"] .sidebar-section-header::before { background: #F37C04 !important; }
[data-testid="stSidebar"] .sidebar-footer { border-top: 1px solid rgba(255, 255, 255, 0.16) !important; }
[data-testid="stSidebar"]:focus-within *:focus-visible { outline-color: #FDBA74 !important; }
"""

_CSS_SIDEBAR_NAV_ATIVO = """
html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] [aria-current="page"],
html body [data-testid="stSidebar"] [data-testid="stSidebarNav"] [aria-current="page"] * {
    color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important;
}
[data-testid="stElementContainer"]:has(iframe[height="0"]) { display: none !important; }
"""

_CSS_SIDEBAR_TEMAS: dict[str, str] = {
    "claro": _CSS_SIDEBAR_CLARO,
    "azul": _CSS_SIDEBAR_AZUL,
    "laranja": _CSS_SIDEBAR_LARANJA,
}


def _gerar_css_sidebar(tema: str) -> str:
    tema_norm = normalizar_tema_sidebar(tema)
    return _CSS_SIDEBAR_TEMAS.get(tema_norm, _CSS_SIDEBAR_CLARO)


class PlotlyConfig:
    @staticmethod
    def configurar() -> None:
        template = go.layout.Template(
            layout=go.Layout(
                font={"family": Fontes.TEXTO, "size": 13, "color": Cores.TEXTO},
                title={
                    "font": {"family": Fontes.TITULO, "size": 18, "color": Cores.TEXTO},
                    "x": 0.0,
                    "xanchor": "left",
                },
                legend={
                    "font": {
                        "family": Fontes.TEXTO,
                        "size": 12,
                        "color": Cores.TEXTO_2,
                    },
                    "bgcolor": "rgba(255,255,255,0.9)",
                    "bordercolor": Cores.BORDA,
                    "borderwidth": 1,
                },
                xaxis={
                    "gridcolor": "#F1F5F9",
                    "zerolinecolor": "#E2E8F0",
                    "title": {
                        "font": {
                            "family": Fontes.TITULO,
                            "size": 12,
                            "color": Cores.TEXTO_2,
                        }
                    },
                },
                yaxis={
                    "gridcolor": "#F1F5F9",
                    "zerolinecolor": "#E2E8F0",
                    "title": {
                        "font": {
                            "family": Fontes.TITULO,
                            "size": 12,
                            "color": Cores.TEXTO_2,
                        }
                    },
                },
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                colorway=ConfigCores.PLOTLY_COLORWAY,
                hoverlabel={
                    "bgcolor": "#FFFFFF",
                    "bordercolor": Cores.BORDA,
                    "font": {"family": Fontes.TEXTO, "size": 12, "color": Cores.TEXTO},
                },
                margin={"t": 48, "b": 40, "l": 48, "r": 16},
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
        _injetar_js(
            f"""
            <script>
            (function () {{
                const urls = [{urls_js}];
                const preconnects = ['https://fonts.googleapis.com', 'https://fonts.gstatic.com'];
                let parentDoc;
                try {{ parentDoc = __DOC__; }} catch (e) {{ return; }}
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
        )
        st.session_state["_totale_fonts_head_injected"] = True


class NavContrastFix:
    """Garante contraste do item ativo da navegação da sidebar.

    v5.0.0: a cor do texto é resolvida por tema (branco nos 3 skins) e o
    mecanismo passou a ser reutilizável via `injetar(cor=..., ativo=...)`.
    """

    _COR_PADRAO = "#FFFFFF"
    _JS = """
<script>
(function () {
    var doc;
    try { doc = __DOC__; } catch (e) { return; }
    if (!doc || !doc.body) return;
    var COR = "__COR__";
    var MODO = "__MODO__";
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
            if (a.getAttribute("aria-current") === "page" && MODO === "ativo") return;
            if (a.getAttribute("aria-current") !== "page" && MODO === "passivo") return;
            limpa(a); a.querySelectorAll("*").forEach(limpa); a.removeAttribute("data-totale-ativo");
        });
        var alvo = MODO === "passivo"
            ? '[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:not([aria-current="page"])'
            : SEL_ATIVO;
        doc.querySelectorAll(alvo).forEach(function (a) {
            pinta(a); a.querySelectorAll("*").forEach(pinta); a.setAttribute("data-totale-ativo", "1");
        });
    }
    var agendado = false;
    function agendar() {
        if (agendado) return;
        agendado = true;
        __WIN__.setTimeout(function () { agendado = false; aplicar(); }, 0);
    }
    if (__WIN__.__totaleNavObs) { try { __WIN__.__totaleNavObs.disconnect(); } catch (e) {} }
    var obs = new MutationObserver(agendar);
    obs.observe(doc.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["aria-current"] });
    __WIN__.__totaleNavObs = obs;
    aplicar();
})();
</script>
"""

    @staticmethod
    def injetar(cor: str | None = None, ativo: bool = True) -> None:
        cor_final = cor or NavContrastFix._COR_PADRAO
        modo = "ativo" if ativo else "passivo"
        js = NavContrastFix._JS.replace("__COR__", cor_final).replace("__MODO__", modo)
        _injetar_js(js)


class CSSInjector:
    @staticmethod
    @lru_cache(maxsize=8)
    def _build_css(tema_sidebar: str = "claro") -> str:
        css_sidebar = _gerar_css_sidebar(tema_sidebar)
        return (
            f"{FontInjector._build_links_html()}\n<style>\n"
            f"{_CSS_VARS_ROOT}\n{_CSS_RESET_GLOBAL}\n{_CSS_HEROS}\n{_CSS_CARDS}\n"
            f"{_CSS_TABELAS}\n{_CSS_EXTRAS}\n{_CSS_STREAMLIT_CHROME}\n{css_sidebar}\n"
            f"{_CSS_SIDEBAR_NAV_ATIVO}\n</style>"
        )

    @staticmethod
    def injetar(tema_sidebar: str = "claro") -> None:
        tema_norm = normalizar_tema_sidebar(tema_sidebar)
        css_html = CSSInjector._build_css(tema_norm)
        _safe_render_html(css_html)

        inicio = css_html.find("<style>")
        fim = css_html.rfind("</style>")
        regras = (
            css_html[inicio + len("<style>") : fim]
            if inicio >= 0 and fim > inicio
            else css_html
        )
        payload = json.dumps(regras).replace("</", "<\\/")
        _injetar_js(
            f"""
            <script>
            (function () {{
                let parentDoc;
                try {{ parentDoc = __DOC__; }} catch (e) {{ return; }}
                if (!parentDoc) return;
                const id = "totale-ds-50";
                let style = parentDoc.getElementById(id);
                if (!style) {{
                    style = parentDoc.createElement("style");
                    style.id = id;
                    parentDoc.head.appendChild(style);
                }}
                style.textContent = {payload};
            }})();
            </script>
            """,
        )
        st.session_state["_totale_css_head_injected"] = True
        st.session_state["_totale_css_head_tema"] = tema_norm


def aplicar_estilo(tema_sidebar: TemaSidebarType = "claro") -> None:
    """Aplica o Design System TOTALE com suporte a 3 temas de sidebar ('claro', 'azul', 'laranja')."""
    tema_norm = normalizar_tema_sidebar(tema_sidebar)
    st.session_state["_totale_sidebar_theme"] = tema_norm
    PlotlyConfig.configurar()
    FontInjector.injetar_no_head_pai()
    CSSInjector.injetar(tema_sidebar=tema_norm)
    NavContrastFix.injetar(cor="#FFFFFF", ativo=True)


def aplicar_estilo_corp(tema_sidebar: TemaSidebarType = "claro") -> None:
    """Alias corporativo de aplicar_estilo()."""
    aplicar_estilo(tema_sidebar=tema_sidebar)


def aplicar_sidebar_corp(tema: TemaSidebarType = "claro") -> None:
    """Aplica tema de sidebar TOTALE ('claro', 'azul' ou 'laranja')."""
    aplicar_estilo(tema_sidebar=tema)


def carregar_layout_corporativo(
    tema_sidebar: TemaSidebarType | None = None,
    renderizar_sidebar: bool = False,
    nome: str = "TOTALE",
    subtitulo: str = "Portal de Produção & Performance",
    versao: str = "",
) -> None:
    """Garante a aplicação do Design System TOTALE em qualquer página.

    Pode ser chamada no início de qualquer página individual em pages/*.
    """
    tema_ativo = _obter_tema_sidebar(tema_sidebar)
    aplicar_estilo(tema_sidebar=tema_ativo)
    if renderizar_sidebar:
        with st.sidebar:
            render_sidebar_brand(nome=nome, subtitulo=subtitulo, versao=versao)
            render_sidebar_theme_selector()


def render_sidebar_theme_selector(
    label: str = "TEMA DA SIDEBAR",
    help: str = "",
    container: Any = None,
    key: str = "_totale_sidebar_theme_select",
    mostrar_icone: bool = True,
    aplicar_automaticamente: bool = True,
) -> TemaSidebarType:
    """Renderiza um st.selectbox nativo para escolher a cor da sidebar ('claro', 'azul', 'laranja').

    Aplica automaticamente o estilo e atualiza o estado da sessão quando
    aplicar_automaticamente=True.

    v5.0.0: o índice inicial reflete o tema ativo da sessão (antes o widget
    sempre reabria em "claro" mesmo com outro tema aplicado).
    """
    alvo = container if container is not None else st.sidebar

    opcoes: list[TemaSidebarType] = ["claro", "azul", "laranja"]
    labels = {
        "claro": "☀️ Claro Corporativo" if mostrar_icone else "Claro Corporativo",
        "azul": "🔷 Deep Executive Navy" if mostrar_icone else "Deep Executive Navy",
        "laranja": "🔶 Terracotta & Amber" if mostrar_icone else "Terracotta & Amber",
    }

    tema_atual = _obter_tema_sidebar()
    idx_atual = opcoes.index(tema_atual) if tema_atual in opcoes else 0

    # Evita o aviso "created with default value but also had its value set via
    # the Session State API": só informa index quando o widget ainda não tem
    # estado persistido (nesse caso o index reflete o tema da sessão).
    kwargs_select: dict[str, Any] = {}
    if key not in st.session_state:
        kwargs_select["index"] = idx_atual

    escolha = alvo.selectbox(
        label,
        options=opcoes,
        format_func=lambda x: labels.get(x, str(x).title()),
        key=key,
        **kwargs_select,
    )

    tema_escolhido = normalizar_tema_sidebar(escolha)

    if aplicar_automaticamente:
        definir_tema_sidebar(tema_escolhido)
        aplicar_estilo(tema_sidebar=tema_escolhido)

    return tema_escolhido


def render_sidebar_brand(
    nome: str = "TOTALE",
    subtitulo: str = "Analytics & Intelligence",
    versao: str = "",
    logo_url: str | None = None,
    icone: str = "⚡",
    titulo: str = "",
    logo: str | None = None,
    tema: TemaSidebarType | None = None,
    **kwargs: Any,
) -> None:
    nome_final = str(titulo or nome or "").strip()
    subtitulo_final = str(kwargs.get("segmento", subtitulo) or "").strip()
    versao_final = str(versao or "").strip()
    icone_final = str(icone or "").strip()
    logo_final = logo or logo_url
    if not nome_final and not subtitulo_final and not logo_final:
        return

    tema_ativo = _obter_tema_sidebar(tema)

    with st.sidebar:
        logo_valida = bool(logo_final and Validadores.url(str(logo_final)))
        if logo_valida:
            st.image(str(logo_final), use_container_width=True)

        badge_html = ""
        if versao_final:
            if tema_ativo == "azul":
                b_bg, b_fg, b_bd = (
                    "rgba(255,255,255,0.12)",
                    Cores.SECUNDARIA_LIGHT,
                    "rgba(255,255,255,0.20)",
                )
            elif tema_ativo == "laranja":
                b_bg, b_fg, b_bd = (
                    "rgba(255,255,255,0.20)",
                    "#FFFFFF",
                    "rgba(255,255,255,0.30)",
                )
            else:
                b_bg, b_fg, b_bd = Cores.AZUL_SUAVE, "#011E52", "#D6E0F0"

            badge_html = (
                f'<span class="totale-badge-pill" style="margin-top:8px;'
                f'background:{b_bg};color:{b_fg};border-color:{b_bd};">'
                f"{Validadores.html_escape(versao_final)}</span>"
            )

        icone_html = "" if logo_valida else _icone_tile(icone_final, "brand")

        # v5.0.0: estilos explícitos alinham a marca em todos os temas.
        if tema_ativo == "azul":
            nome_style = (
                "font-family: var(--font-titulo); font-size: 18px; font-weight: 800; "
                "letter-spacing: -0.03em; margin: 0; line-height: 1.1; "
                "background: linear-gradient(100deg, #FFFFFF 20%, #FDBA74 100%); "
                "-webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;"
            )
            sub_style = "font-size: 11px; color: #CBD5E1; margin-top: 3px; letter-spacing: 0.01em;"
        elif tema_ativo == "laranja":
            nome_style = (
                "font-family: var(--font-titulo); font-size: 18px; font-weight: 800; "
                "letter-spacing: -0.03em; margin: 0; line-height: 1.1; color: #FFFFFF;"
            )
            sub_style = "font-size: 11px; color: #FFEDD5; margin-top: 3px; letter-spacing: 0.01em;"
        else:
            nome_style = (
                "font-family: var(--font-titulo); font-size: 18px; font-weight: 800; "
                "letter-spacing: -0.03em; margin: 0; line-height: 1.1; "
                "background: linear-gradient(100deg, #012869 10%, #0A48AA 62%, #F37C04 140%); "
                "-webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;"
            )
            sub_style = "font-size: 11px; color: #475569; margin-top: 3px; letter-spacing: 0.01em;"

        nome_html = (
            f'<h2 class="sidebar-brand-name" style="{nome_style}">{Validadores.html_escape(nome_final)}</h2>'
            if nome_final
            else ""
        )
        subtitulo_html = (
            f'<div class="sidebar-brand-sub" style="{sub_style}">{Validadores.html_escape(subtitulo_final)}</div>'
            if subtitulo_final
            else ""
        )

        markup = (
            '<div class="sidebar-brand">'
            '<div style="display:flex;align-items:center;gap:10px;">'
            f'{icone_html}<div style="min-width:0;">{nome_html}{subtitulo_html}</div></div>'
            f"{badge_html}</div>"
        )
        _safe_render_html(markup)


def render_sidebar_section(
    titulo: str,
    icone: str = "",
    collapsible: bool = False,
    tema: TemaSidebarType | None = None,
) -> None:
    if collapsible:
        with st.sidebar.expander(f"{icone} {titulo}".strip(), expanded=True):
            pass
        return

    tema_ativo = _obter_tema_sidebar(tema)

    if tema_ativo == "azul":
        bar_color = Cores.SECUNDARIA
        titulo_color = "#FFFFFF"
        icone_color = Cores.SECUNDARIA_LIGHT
    elif tema_ativo == "laranja":
        bar_color = "#011838"
        titulo_color = "#FFFFFF"
        icone_color = "#FFF7ED"
    else:
        bar_color = Cores.SECUNDARIA
        titulo_color = "#011E52"
        icone_color = Cores.SECUNDARIA

    icone_html = (
        f'<span style="font-size:14px;line-height:1;color:{icone_color};">'
        f"{Validadores.html_escape(icone)}</span>"
        if icone
        else ""
    )
    markup = (
        f'<div class="sidebar-section-header" style="position:relative;margin:16px 0 6px;padding:4px 0 8px 12px;">'
        f'<span style="position:absolute;left:0;top:6px;width:3px;height:12px;border-radius:99px;background:{bar_color};"></span>'
        f'<div style="font-size:11px;font-weight:750;color:{titulo_color};'
        'text-transform:uppercase;letter-spacing:0.08em;display:flex;align-items:center;gap:6px;">'
        f"{icone_html}<span>{Validadores.html_escape(titulo)}</span></div></div>"
    )
    with st.sidebar:
        _safe_render_html(markup)


def render_sidebar_divider(
    estilo: Literal["linha", "gradiente", "pontilhado", "espaco"] = "gradiente",
    espacamento: Literal["pequeno", "medio", "grande"] = "medio",
    cor: str = "",
    label: str = "",
    tema: TemaSidebarType | None = None,
) -> None:
    margens = {"pequeno": "6px 0", "medio": "14px 0", "grande": "24px 0"}
    margem = margens.get(espacamento, margens["medio"])

    tema_ativo = _obter_tema_sidebar(tema)

    if tema_ativo == "azul":
        cor_default = "rgba(255,255,255,0.14)"
        gradiente_padrao = (
            "border:none;height:1px;background:linear-gradient(90deg,transparent 0%,"
            "rgba(255,255,255,0.3) 50%,transparent 100%);"
        )
        label_color = Cores.SECUNDARIA_LIGHT
    elif tema_ativo == "laranja":
        cor_default = "rgba(255,255,255,0.22)"
        gradiente_padrao = (
            "border:none;height:1px;background:linear-gradient(90deg,transparent 0%,"
            "rgba(255,255,255,0.4) 50%,transparent 100%);"
        )
        label_color = "#FFFFFF"
    else:
        cor_default = "#CBD5E1"
        gradiente_padrao = (
            "border:none;height:1px;background:linear-gradient(90deg,transparent 0%,"
            f"{Cores.PRIMARIA}55 40%,{Cores.SECUNDARIA} 70%,transparent 100%);"
        )
        label_color = "#011E52"

    cor_final = cor or cor_default

    if estilo == "espaco":
        alturas = {"pequeno": "8px", "medio": "16px", "grande": "28px"}
        _safe_render_html(
            f'<div style="height:{alturas.get(espacamento, "16px")};"></div>',
            st.sidebar,
        )
        return
    if estilo == "pontilhado":
        style_line = f"border:none;border-top:1.5px dashed {cor_final};"
    elif estilo == "gradiente":
        style_line = gradiente_padrao
    else:
        style_line = f"border:none;border-top:1px solid {cor_final};"

    if label:
        label_esc = Validadores.html_escape(label)
        markup = (
            f'<div style="display:flex;align-items:center;gap:10px;margin:{margem};">'
            f'<div style="flex:1;{style_line}"></div>'
            f'<span style="font-size:9px;font-weight:750;color:{label_color};'
            f'text-transform:uppercase;letter-spacing:0.12em;">{label_esc}</span>'
            f'<div style="flex:1;{style_line}"></div></div>'
        )
    else:
        markup = f'<div style="margin:{margem};{style_line}"></div>'
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
    tema: TemaSidebarType | None = None,
    **kwargs: Any,
) -> None:
    mostrar_rel = mostrar_relógio or kwargs.get("mostrar_relogio", False)
    itens_dict: dict[str, Any] = (
        dict(itens) if isinstance(itens, dict) else dict(itens or [])
    )
    agora = _agora_br()
    if ano is None:
        ano = agora.year

    tema_ativo = _obter_tema_sidebar(tema)

    if tema_ativo == "azul":
        border_col = "rgba(255,255,255,0.10)"
        lbl_col = "#94A3B8"
        val_col = "#FFFFFF"
        sub_col = "#CBD5E1"
        bar_col = Cores.SECUNDARIA
        v_bg, v_fg = "rgba(243,124,4,0.12)", Cores.SECUNDARIA_LIGHT
    elif tema_ativo == "laranja":
        border_col = "rgba(255,255,255,0.16)"
        lbl_col = "#FED7AA"
        val_col = "#FFFFFF"
        sub_col = "#FFEDD5"
        bar_col = Cores.SECUNDARIA
        v_bg, v_fg = "rgba(255,255,255,0.12)", "#FFF7ED"
    else:
        border_col = "#E2E8F0"
        lbl_col = "#475569"
        val_col = "#011E52"
        sub_col = "#334155"
        bar_col = Cores.SECUNDARIA
        v_bg, v_fg = Cores.AZUL_SUAVE, "#011E52"

    amb_cfg = {
        "produção": ("#ECFDF5", "#065F46", "#059669"),
        "producao": ("#ECFDF5", "#065F46", "#059669"),
        "prod": ("#ECFDF5", "#065F46", "#059669"),
        "homologação": ("#FFFBEB", "#92400E", "#D97706"),
        "homologacao": ("#FFFBEB", "#92400E", "#D97706"),
        "hml": ("#FFFBEB", "#92400E", "#D97706"),
        "desenvolvimento": ("#EFF6FF", "#1E40AF", "#3B82F6"),
        "dev": ("#EFF6FF", "#1E40AF", "#3B82F6"),
        "local": ("#F3F4F6", "#374151", "#9CA3AF"),
    }
    versao_html = (
        f'<span class="totale-badge-pill" style="background:{v_bg};color:{v_fg};">'
        f"{Validadores.html_escape(versao if str(versao).startswith('v') else f'v{versao}')}</span>"
        if versao
        else ""
    )
    amb_html = ""
    if ambiente:
        bg_a, fg_a, dot_a = amb_cfg.get(
            ambiente.lower().strip(), ("#F3F4F6", "#374151", "#9CA3AF")
        )
        amb_html = (
            f'<span class="totale-badge-pill" style="background:{bg_a};color:{fg_a};">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{dot_a};"></span>'
            f"{Validadores.html_escape(ambiente)}</span>"
        )
    badges_row = (
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;">{versao_html}{amb_html}</div>'
        if (versao_html or amb_html)
        else ""
    )
    unidade_html = (
        f'<div style="font-size:11px;font-weight:650;color:{sub_col};margin-bottom:8px;'
        f'border-left:3px solid {bar_col};padding-left:8px;">'
        f"{Validadores.html_escape(unidade)}</div>"
        if unidade
        else ""
    )
    itens_html = ""
    if itens_dict:
        rows = "".join(
            '<div style="display:flex;justify-content:space-between;gap:8px;padding:3px 0;">'
            f'<span style="font-size:11px;color:{lbl_col};">{Validadores.html_escape(k)}</span>'
            f'<span style="font-size:11px;color:{val_col};font-weight:750;">{Validadores.html_escape(v)}</span></div>'
            for k, v in itens_dict.items()
        )
        itens_html = f'<div style="border-top:1px solid {border_col};padding-top:8px;">{rows}</div>'
    relogio_html = (
        f'<div style="font-size:10px;color:{lbl_col};text-align:center;margin-top:8px;">'
        f"{agora.strftime('%d/%m/%Y %H:%M')}</div>"
        if mostrar_rel
        else ""
    )
    copy_final = copyright or f"© {ano} {empresa}"
    copy_html = (
        f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid {border_col};'
        f'font-size:10px;color:{lbl_col};text-align:center;">'
        f"{Validadores.html_escape(copy_final)}</div>"
    )
    with st.sidebar:
        _safe_render_html(
            f'<div class="sidebar-footer">{badges_row}{unidade_html}{itens_html}{relogio_html}{copy_html}</div>'
        )


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
    tema: TemaSidebarType | None = None,
) -> None:
    itens_dict: dict[str, Any] = (
        dict(itens) if isinstance(itens, dict) else dict(itens or [])
    )
    tema_ativo = _obter_tema_sidebar(tema)

    if tema_ativo == "azul":
        card_bg = "rgba(255, 255, 255, 0.035)"
        card_bd = "rgba(255, 255, 255, 0.10)"
        avatar_bg = Cores.PRIMARIA_LIGHT
        nome_col = "#FFFFFF"
        role_col = "#FDBA74"
        email_col = "#94A3B8"
        item_lbl_col = "#94A3B8"
        item_val_col = "#FFFFFF"
        rodape_col = "#94A3B8"
        titulo_col = "#FFFFFF"
    elif tema_ativo == "laranja":
        card_bg = "rgba(0, 0, 0, 0.22)"
        card_bd = "rgba(255, 255, 255, 0.12)"
        avatar_bg = Cores.PRIMARIA_DARK
        nome_col = "#FFFFFF"
        role_col = "#FDBA74"
        email_col = "rgba(255, 255, 255, 0.88)"
        item_lbl_col = "#FED7AA"
        item_val_col = "#FFFFFF"
        rodape_col = "rgba(255, 255, 255, 0.82)"
        titulo_col = "#FFFFFF"
    else:
        card_bg = "#FFFFFF"
        card_bd = "#E2E8F0"
        avatar_bg = "#011E52"
        nome_col = "#011E52"
        role_col = "#9A3412"
        email_col = "#475569"
        item_lbl_col = "#475569"
        item_val_col = "#011E52"
        rodape_col = "#475569"
        titulo_col = "#011E52"

    status_cfg = {
        "online": ("#059669", "Online"),
        "offline": ("#94A3B8", "Offline"),
        "ausente": ("#D97706", "Ausente"),
        "ocupado": ("#DC2626", "Ocupado"),
    }
    if avatar and Validadores.url(avatar):
        avatar_html = (
            f'<img src="{Validadores.html_escape(avatar)}" alt="" '
            'style="width:40px;height:40px;border-radius:12px;object-fit:cover;" />'
        )
    else:
        if avatar:
            mono = Validadores.html_escape(avatar[:2])
        elif user_name:
            partes = user_name.strip().split()
            mono = Validadores.html_escape(
                (partes[0][0] + partes[-1][0]).upper()
                if len(partes) >= 2
                else user_name[:1].upper()
            )
        else:
            mono = "U"
        avatar_html = (
            '<div style="width:40px;height:40px;border-radius:12px;display:flex;align-items:center;'
            f'justify-content:center;background:{avatar_bg};color:#fff;font-weight:800;">{mono}</div>'
        )
    status_label_html = ""
    if status and status in status_cfg:
        cor_s, label_s = status_cfg[status]
        status_label_html = (
            f'<span style="font-size:10px;font-weight:750;color:{cor_s};letter-spacing:0.04em;">'
            f"{label_s}</span>"
        )
    user_section = ""
    if user_name or role or email or avatar:
        name_html = (
            f'<p style="margin:0;font-size:13px;font-weight:750;color:{nome_col};">'
            f"{Validadores.html_escape(user_name)}</p>"
            if user_name
            else ""
        )
        role_html = (
            f'<p style="margin:2px 0 0;font-size:11px;color:{role_col};font-weight:650;">'
            f"{Validadores.html_escape(role)}</p>"
            if role
            else ""
        )
        email_html = (
            f'<p style="margin:2px 0 0;font-size:11px;color:{email_col};">'
            f"{Validadores.html_escape(email)}</p>"
            if email
            else ""
        )
        user_section = (
            '<div style="display:flex;align-items:center;gap:12px;">'
            f"{avatar_html}<div>{name_html}{role_html}{email_html}{status_label_html}</div></div>"
        )
    itens_html = ""
    if itens_dict:
        rows = "".join(
            '<div style="display:flex;justify-content:space-between;gap:8px;padding:4px 0;">'
            f'<span style="font-size:11px;color:{item_lbl_col};">{Validadores.html_escape(k)}</span>'
            f'<span style="font-size:11px;color:{item_val_col};font-weight:750;">{Validadores.html_escape(v)}</span></div>'
            for k, v in itens_dict.items()
        )
        itens_html = f'<div style="margin-top:8px;">{rows}</div>'
    rodape_html = (
        f'<div style="margin-top:8px;font-size:10px;color:{rodape_col};">{Validadores.html_escape(rodape)}</div>'
        if rodape
        else ""
    )
    titulo_html = (
        f'<div class="sidebar-section-header"><span style="font-size:11px;font-weight:750;color:{titulo_col};'
        f'text-transform:uppercase;letter-spacing:0.08em;">{Validadores.html_escape(titulo)}</span></div>'
        if titulo
        else ""
    )
    if not user_section and not itens_html and not rodape_html:
        return
    markup = (
        f"{titulo_html}"
        f'<div style="background:{card_bg};border:1px solid {card_bd};border-radius:14px;padding:14px;margin:8px 0 12px;">'
        f"{user_section}{itens_html}{rodape_html}</div>"
    )
    with st.sidebar:
        _safe_render_html(markup)


def render_sidebar_spacer(
    altura: Literal["pequeno", "medio", "grande", "xgrande"] | int | str = "medio",
) -> None:
    presets = {"pequeno": "8px", "medio": "16px", "grande": "28px", "xgrande": "48px"}
    if isinstance(altura, int):
        altura_css = f"{altura}px"
    else:
        bruto = str(altura).lower().strip()
        if any(bruto.endswith(u) for u in ("px", "rem", "em", "%", "vh", "vw")):
            altura_css = str(altura)
        else:
            altura_css = presets.get(bruto, "16px")
    with st.sidebar:
        _safe_render_html(
            f'<div style="height:{altura_css};" aria-hidden="true"></div>'
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
    tema: TemaSidebarType | None = None,
    nav_contrast: str | None = None,
    **kwargs: Any,
) -> None:
    """Card de status da sidebar.

    v5.0.0: `nav_contrast=None` (padrão) não injeta JS; `nav_contrast="#FFFFFF"`
    reforça o contraste do item ativo da navegação; use `nav_contrast=""` para
    desligar explicitamente. Também aceita `kwargs['cor_nav_contrast']`.
    """
    tema_ativo = _obter_tema_sidebar(tema)

    if nav_contrast is None and "cor_nav_contrast" in kwargs:
        nav_contrast = kwargs.get("cor_nav_contrast")
    if nav_contrast:
        NavContrastFix.injetar(cor=str(nav_contrast), ativo=True)

    cfg_status = {
        "ok": ("#047857", "#ECFDF5", "#A7F3D0", "#065F46"),
        "info": ("#1D4ED8", "#EFF6FF", "#BFDBFE", "#1E3A8A"),
        "alerta": ("#D97706", "#FFFBEB", "#FDE68A", "#92400E"),
        "critico": ("#DC2626", "#FEF2F2", "#FECACA", "#991B1B"),
    }
    cor, bg, borda, texto = cfg_status.get(tipo, cfg_status["ok"])
    status_esc = Validadores.html_escape(str(status).strip())
    label_esc = Validadores.html_escape(label.strip().upper())
    pill = (
        f'<span class="totale-badge-pill" style="background:{bg};color:{texto};border:1px solid {borda};">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{cor};"></span>{status_esc}</span>'
    )
    if compacto or kwargs.get("badge_only", False):
        target = container if container is not None else st.sidebar
        _safe_render_html(f'<div style="margin:6px 0;">{pill}</div>', target)
        return

    if tema_ativo == "azul":
        card_bg = "rgba(255, 255, 255, 0.035)"
        card_bd = "rgba(255, 255, 255, 0.10)"
        lbl_col = "#94A3B8"
        total_sub_col = "#CBD5E1"
        total_val_col = "#FFFFFF"
        detail_k_col = "#94A3B8"
        detail_v_col = "#FFFFFF"
        date_col = "#94A3B8"
    elif tema_ativo == "laranja":
        card_bg = "rgba(0, 0, 0, 0.22)"
        card_bd = "rgba(255, 255, 255, 0.12)"
        lbl_col = "#FED7AA"
        total_sub_col = "#FFEDD5"
        total_val_col = "#FFFFFF"
        detail_k_col = "#FED7AA"
        detail_v_col = "#FFFFFF"
        date_col = "#FDBA74"
    else:
        card_bg = "#FFFFFF"
        card_bd = "#E2E8F0"
        lbl_col = "#475569"
        total_sub_col = "#334155"
        total_val_col = "#011E52"
        detail_k_col = "#475569"
        detail_v_col = "#011E52"
        date_col = "#475569"

    detalhes_dict = detalhes or {}
    detalhes_html = "".join(
        '<div style="display:flex;justify-content:space-between;padding:3px 0;">'
        f'<span style="font-size:11px;color:{detail_k_col};">{Validadores.html_escape(k)}</span>'
        f'<span style="font-size:11px;color:{detail_v_col};font-weight:750;">{Validadores.html_escape(v)}</span></div>'
        for k, v in detalhes_dict.items()
    )
    ultima_fmt = (
        formatar_datetime_exibicao(ultima_atualizacao) if ultima_atualizacao else ""
    )
    data_html = (
        f'<div style="font-size:11px;color:{date_col};margin-top:6px;">Atualizado {Validadores.html_escape(ultima_fmt)}</div>'
        if ultima_fmt
        else ""
    )
    total_html = (
        f'<div style="font-size:12px;color:{total_sub_col};margin-top:4px;">Total <strong style="color:{total_val_col};">{Validadores.html_escape(total_registros)}</strong></div>'
        if total_registros is not None
        else ""
    )
    markup = (
        f'<div style="background:{card_bg};border:1px solid {card_bd};border-radius:14px;padding:12px 14px;margin:10px 0 14px;'
        f'box-shadow:inset 3px 0 0 {cor};">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
        f'<span style="font-size:10px;font-weight:800;letter-spacing:0.08em;color:{lbl_col};">{label_esc}</span>'
        f"{pill}</div>{total_html}{detalhes_html}{data_html}</div>"
    )
    target = container if container is not None else st.sidebar
    _safe_render_html(markup, target)


def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    if not titulo:
        raise ValueError("render_hero: 'titulo' não pode ser vazio.")
    badge_html = (
        f'<span class="hero-badge">{Validadores.html_escape(badge)}</span>'
        if badge
        else ""
    )
    sub_html = (
        f'<p class="hero-subtitle">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    _safe_render_html(
        '<div class="hero-corp"><div class="hero-content">'
        f'{badge_html}<h1 class="hero-title">{Validadores.html_escape(titulo)}</h1>{sub_html}'
        "</div></div>"
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
    b = (
        '<div class="totale-badge-pill" style="background:rgba(255,255,255,0.12);color:#fff;border:1px solid rgba(255,255,255,0.18);">'
        f"<span>{Validadores.html_escape(icone)}</span> {Validadores.html_escape(badge)}</div>"
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
        '<div class="totale-hero-1"><div>'
        f'{b}<h1 class="th-title-lg">{Validadores.html_escape(titulo)}</h1>{s}{m}</div></div>'
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
    b = (
        f'<span class="th-badge">{Validadores.html_escape(badge_texto)}</span>'
        if badge_texto
        else ""
    )
    tag = (
        f'<span class="th-tag">{Validadores.html_escape(tag_info)}</span>'
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
        f'<div class="th-card-value">{Validadores.html_escape(valor_destaque)}</div></div>'
        if valor_destaque
        else ""
    )
    _safe_render_html(
        '<div class="totale-hero-2"><div>'
        f'{b}{tag}<h1 class="th-title">{Validadores.html_escape(titulo)}</h1>{s}</div>{card}</div>'
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
    badge_html = (
        '<div class="hero-badge">'
        f"<span>{Validadores.html_escape(icone)}</span> {Validadores.html_escape(badge)}</div>"
        if badge
        else ""
    )
    sub_html = (
        f'<p class="th-sub">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    stats_html = _hero_stats(stats, "#FDBA74")
    _safe_render_html(
        '<div class="hero-migracao"><div>'
        f'{badge_html}<h1 class="th-title-lg">{Validadores.html_escape(titulo)}</h1>'
        f"{sub_html}{stats_html}</div></div>"
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
    badge_html = (
        '<div class="hero-badge">'
        f"<span>{Validadores.html_escape(icone)}</span> {Validadores.html_escape(badge)}</div>"
        if badge
        else ""
    )
    sub_html = (
        f'<p class="th-sub">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    feat_html = ""
    if features:
        pills = "".join(
            '<span class="totale-badge-pill" style="background:rgba(255,255,255,0.12);color:#fff;border:1px solid rgba(255,255,255,0.18);">'
            f"{Validadores.html_escape(feature)}</span>"
            for feature in list(features)[:5]
        )
        feat_html = f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;">{pills}</div>'
    _safe_render_html(
        '<div class="hero-pme"><div>'
        f'{badge_html}<h1 class="th-title-lg">{Validadores.html_escape(titulo)}</h1>'
        f"{sub_html}{feat_html}</div></div>"
    )


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
    badge_html = (
        '<div class="hero-badge">'
        f"<span>{Validadores.html_escape(icone)}</span> {Validadores.html_escape(badge)}</div>"
        if badge
        else ""
    )
    sub_html = (
        f'<p class="th-sub">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    meta_html = (
        f'<div class="th-meta">{Validadores.html_escape(meta_info)}</div>'
        if meta_info
        else ""
    )
    _safe_render_html(
        '<div class="hero-domicilios"><div>'
        f'{badge_html}<h1 class="th-title-lg">{Validadores.html_escape(titulo)}</h1>'
        f"{sub_html}{_hero_stats(stats, '#86EFAC')}{meta_html}</div></div>"
    )


def _hero_stats(stats: Sequence[dict[str, str]] | None, cor_valor: str) -> str:
    if not stats:
        return ""
    cards = []
    for item in list(stats)[:4]:
        cards.append(
            '<div style="background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.16);'
            'border-radius:12px;padding:12px 14px;text-align:left;">'
            f'<strong style="font-size:18px;font-weight:800;color:{cor_valor};display:block;letter-spacing:-0.03em;">'
            f"{Validadores.html_escape(item.get('valor', ''))}</strong>"
            f'<span style="font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:rgba(255,255,255,0.72);">'
            f"{Validadores.html_escape(item.get('label', ''))}</span></div>"
        )
    return (
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-top:16px;">'
        + "".join(cards)
        + "</div>"
    )


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

    def _parece_icone(val: str) -> bool:
        v = val.strip()
        if not v:
            return False
        if len(v) <= 4:
            return True
        if " " not in v and all(c.isalnum() or c == "_" for c in v):
            return True
        return False

    def _parece_titulo(val: str) -> bool:
        v = val.strip()
        if not v:
            return False
        if len(v) > 10 or " " in v or any(c.isupper() for c in v):
            return True
        return False

    # 4.7.1: chamada antiga (icone, titulo, subtitulo) não pode quebrar o layout.
    if _parece_icone(titulo_final) and _parece_titulo(icone_final):
        titulo_final, icone_final = icone_final, titulo_final
        if (
            badge_final
            and not subtitulo_final
            and (" " in badge_final or len(badge_final) > 18)
        ):
            subtitulo_final = badge_final
            badge_final = ""
        logger.warning(
            "render_section_header recebeu ícone e título invertidos. Argumentos corrigidos."
        )
    if not any((titulo_final, icone_final, badge_final, subtitulo_final)):
        return

    tipo_norm = normalizar_tipo_badge(badge_tipo)
    bg_badge, cor_badge, borda_badge = ConfigCores.BADGE[tipo_norm]
    icone_html = _icone_tile(icone_final, "section") if icone_final else ""
    titulo_html = (
        f'<h2 class="section-title">{Validadores.html_escape(titulo_final)}</h2>'
        if titulo_final
        else ""
    )
    badge_html = (
        f'<span class="totale-badge-pill" style="background:{bg_badge};color:{cor_badge};border:1px solid {borda_badge};">'
        f"{Validadores.html_escape(badge_final)}</span>"
        if badge_final
        else ""
    )
    subtitulo_html = (
        f'<p class="section-subtitle">{Validadores.html_escape(subtitulo_final)}</p>'
        if subtitulo_final
        else ""
    )
    markup = (
        '<div class="section-header">'
        f'{icone_html}<div class="section-header-copy">'
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-width:0;">'
        f"{titulo_html}{badge_html}</div>{subtitulo_html}</div></div>"
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
    if usar_cor:
        fundo = f"linear-gradient(155deg, {cor_inicio} 0%, {cor_inicio} 58%, {cor_fim} 140%)"
        cor_texto = "#FFFFFF"
        cor_borda = "rgba(255,255,255,0.16)"
        fundo_icone = "rgba(255,255,255,0.16)"
        classe = "card-premium card-premium-colorida"
    else:
        fundo = "#FFFFFF"
        cor_texto = Cores.TEXTO
        cor_borda = Cores.BORDA
        fundo_icone = f"{cor_inicio}14"
        classe = "card-premium"
    label_esc = Validadores.html_escape(label)
    valor_esc = Validadores.html_escape(valor)
    sub_esc = Validadores.html_escape(sub)
    padding = "14px 16px" if compacto else "18px 18px 16px"
    tamanho_valor = "22px" if compacto else "30px"
    icone_html = ""
    if icone:
        icone_seguro = _texto_icone_seguro(icone)
        icone_html = (
            f'<div class="kpi-icon-wrapper" style="background:{fundo_icone};color:{cor_texto};">'
            f'<span class="totale-icon-glyph" aria-hidden="true">{Validadores.html_escape(icone_seguro)}</span></div>'
        )
    delta_html = ""
    if delta:
        trend_norm = normalizar_tipo_trend(delta_tipo)
        seta = ConfigCores.TREND_ICONS.get(trend_norm, "")
        classe_delta = "trend-pill" + (
            f" trend-{trend_norm}" if trend_norm != "none" else ""
        )
        delta_html = (
            f'<span class="{classe_delta}"><span aria-hidden="true">{seta}</span>'
            f"{Validadores.html_escape(delta)}</span>"
        )
    sub_html = (
        f'<div class="kpi-sub-premium" style="color:{cor_texto};">{delta_html}{sub_esc}</div>'
        if (sub or delta)
        else ""
    )
    markup = (
        f'<div class="{classe}" style="background:{fundo};color:{cor_texto};border-color:{cor_borda};padding:{padding};" '
        f'role="region" aria-label="{label_esc}: {valor_esc}">'
        f'<div class="card-accent-top" style="background:{cor_fim if usar_cor else cor_inicio};"></div>'
        '<div class="card-header-flex">'
        f'<div class="kpi-label-premium" style="color:{cor_texto};">{label_esc}</div>{icone_html}</div>'
        f'<div><div class="kpi-value-premium" style="font-size:{tamanho_valor};color:{cor_texto};">{valor_esc}</div>'
        f"{sub_html}</div></div>"
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
    _card_premium(col, label, valor, sub, tema, icone, delta, delta_tipo, colorida)


def render_metric_card(
    col: Any,
    label: str,
    valor: str,
    trend: TipoTrendType = "none",
    trend_valor: str = "",
    sub: str = "",
    colorida: bool = True,
) -> None:
    _card_premium(col, label, valor, sub, "azul", "", trend_valor, trend, colorida)


def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPIType = "azul",
    icone: str = "",
) -> None:
    _card_premium(
        container, label, valor, sub, tema, icone, colorida=True, compacto=True
    )


def render_insight(msg: str, tipo: TipoInsightType = "info", titulo: str = "") -> None:
    if not msg:
        return
    tipo_norm = normalizar_tipo_insight(tipo)
    bg, texto, borda, icone = ConfigCores.INSIGHT.get(
        tipo_norm, ConfigCores.INSIGHT["info"]
    )
    titulo_html = (
        f'<span class="totale-insight-title">{Validadores.html_escape(titulo)}</span>'
        if titulo
        else ""
    )
    markup = (
        f'<div class="totale-insight" style="background:{bg};color:{texto};border-color:{borda}33;box-shadow:inset 3px 0 0 {borda};">'
        f'<span class="totale-insight-icon">{icone}</span>'
        f'<div style="flex:1;min-width:0;">{titulo_html}<div>{Formatadores.markdown_para_html(msg)}</div></div></div>'
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
        f'<strong style="display:block;margin-bottom:2px;font-size:13px;">{Validadores.html_escape(titulo)}</strong>'
        if titulo
        else ""
    )
    markup = (
        f'<div class="totale-insight" role="status" style="background:{bg};color:{fg};border-color:{borda}33;box-shadow:inset 3px 0 0 {borda};">'
        f'<span class="totale-insight-icon">{icone}</span>'
        f'<div style="font-size:13px;line-height:1.5;">{titulo_html}{Formatadores.markdown_para_html(mensagem)}</div></div>'
    )
    _safe_render_html(markup, container)


def render_empty_state(
    tipo: TipoEmptyStateType = "padrao",
    titulo: str = "",
    descricao: str = "",
    acao: str = "",
    icone: str = "",
) -> None:
    _bg, cor_estado, icone_default, titulo_default = ConfigCores.EMPTY_STATE.get(
        tipo, ConfigCores.EMPTY_STATE["padrao"]
    )
    desc_html = (
        f'<p class="empty-state-desc">{Validadores.html_escape(descricao)}</p>'
        if descricao
        else ""
    )
    acao_html = (
        f'<p style="margin:12px 0 0;font-size:13px;color:{Cores.SECUNDARIA};font-weight:700;">'
        f"{Validadores.html_escape(acao)}</p>"
        if acao
        else ""
    )
    _safe_render_html(
        '<div class="empty-state">'
        f'<span class="empty-state-icon">{Validadores.html_escape(icone or icone_default)}</span>'
        f'<h3 class="empty-state-title" style="color:{cor_estado};">{Validadores.html_escape(titulo or titulo_default)}</h3>'
        f"{desc_html}{acao_html}</div>"
    )


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
    altura_px = {"pequeno": "6px", "medio": "8px", "grande": "10px"}.get(
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
            f'<span style="font-size:12px;font-weight:700;color:{Cores.TEXTO_2};">{Validadores.html_escape(label)}</span>'
            if label
            else "<span></span>"
        )
        val = (
            f'<span style="font-size:13px;font-weight:800;color:{Cores.PRIMARIA};font-variant-numeric:tabular-nums;">'
            f"{porcentagem:.1f}{unidade}</span>"
            if mostrar_valor
            else ""
        )
        header_html = f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">{lbl}{val}</div>'
    classe_anim = "totale-pb-fill animado" if animado else "totale-pb-fill"
    _safe_render_html(
        f'<div style="margin:12px 0;" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{porcentagem:.1f}">'
        f'{header_html}<div style="width:100%;background:#E8EEF5;border-radius:999px;height:{altura_px};">'
        f'<div class="{classe_anim}" style="width:{porcentagem:.4f}%;height:100%;background:{bg_style};border-radius:999px;"></div>'
        "</div></div>"
    )


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

    th_html = "".join(
        f'<th style="text-align:{alinhamentos.get(col, "left")};">{Validadores.html_escape(str(col))}</th>'
        for col in df_display.columns
    )
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
                    try:
                        if isinstance(formatter, str):
                            val_str = formatter.format(val)
                        elif callable(formatter):
                            val_str = str(formatter(val))
                    except Exception:
                        pass
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
            if (
                color_rules
                and col in color_rules
                and isinstance(color_rules[col], dict)
            ):
                classe_cor = color_rules[col].get(str(val), "")
                if classe_cor in ("positive", "sucesso"):
                    val_str = f'<span class="td-badge-ok">{val_str}</span>'
                elif classe_cor in ("negative", "alerta"):
                    val_str = f'<span class="td-badge-alerta">{val_str}</span>'
            font_style = (
                "font-variant-numeric:tabular-nums;font-family:var(--font-codigo);font-size:11.5px;"
                if align == "right"
                else ""
            )
            td_parts.append(
                f'<td style="text-align:{align};{font_style}">{val_str}</td>'
            )
        classe_linha: list[str] = []
        if eh_destaque:
            classe_linha.append("linha-destaque")
        elif striped and i % 2 == 1:
            classe_linha.append("striped")
        classe_attr = f' class="{" ".join(classe_linha)}"' if classe_linha else ""
        tr_parts.append(f"<tr{classe_attr}>{''.join(td_parts)}</tr>")

    titulo_html = (
        f'<div class="section-title" style="margin-bottom:10px;">{Validadores.html_escape(titulo)}</div>'
        if titulo
        else ""
    )
    caption_html = (
        f'<div style="font-size:11px;color:#94A3B8;margin-top:8px;">{Validadores.html_escape(caption)}</div>'
        if caption
        else ""
    )
    data_html = (
        '<div style="font-size:11px;color:#94A3B8;margin-top:6px;text-align:right;">Atualizado em '
        f"{_agora_br().strftime('%d/%m/%Y %H:%M')}</div>"
        if mostrar_data
        else ""
    )
    height_style = f"max-height:{height}px;" if height else ""
    _safe_render_html(
        f'<div style="margin:8px 0 18px;">{titulo_html}'
        '<div class="table-premium-wrapper">'
        f'<div class="table-premium-scroll" style="{height_style}">'
        '<table class="totale-table-pro"><thead><tr>'
        f"{th_html}</tr></thead><tbody>{''.join(tr_parts)}</tbody></table></div></div>"
        f"{caption_html}{data_html}</div>"
    )
    if exportar_excel and not df_display.empty:
        buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_display.to_excel(writer, index=False, sheet_name="Dados")
            _, c2 = st.columns([4, 1])
            with c2:
                st.download_button(
                    label="Baixar Excel",
                    data=buffer.getvalue(),
                    file_name=f"{nome_arquivo}_{_agora_br().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    help="Exportar relatório atual",
                )
        except Exception as exc:
            logger.error("Falha na exportação de planilha: %s", exc)


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
    icone_html = _icone_tile(icone, "section") if icone else ""
    markup = (
        f'<div class="card-premium" role="region" aria-label="{Validadores.html_escape(titulo)}" '
        f'style="background:{bg};color:{fg};border-color:{borda};min-height:0;">'
        f'<div class="card-accent-top" style="background:{borda};"></div>'
        '<div style="display:flex;align-items:flex-start;gap:12px;position:relative;z-index:2;">'
        f'{icone_html}<div style="flex:1;min-width:0;">'
        f'<div style="font-family:var(--font-titulo);font-size:15px;font-weight:800;margin-bottom:4px;">'
        f"{Validadores.html_escape(titulo)}</div>"
        f'<div style="font-size:13px;line-height:1.55;">{Formatadores.markdown_para_html(corpo)}</div>'
        "</div></div></div>"
    )
    _safe_render_html(markup, container)


def render_spacer(altura: int | str = 16) -> None:
    css = f"{altura}px" if isinstance(altura, int) else str(altura)
    _safe_render_html(f'<div style="height:{css};" aria-hidden="true"></div>')


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
    icone_html = f"<span>{Validadores.html_escape(icone)}</span>" if icone else ""
    _safe_render_html(
        f'<span class="totale-badge-pill" style="background:{bg};color:{fg};border:1px solid {borda};">'
        f"{icone_html}{Validadores.html_escape(texto)}</span>",
        container,
    )


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
    "TemaSidebar",
    "TemaSidebarType",
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
    "carregar_layout_corporativo",
    "definir_tema_sidebar",
    "formatar_datetime_exibicao",
    "formatar_numero_br",
    "normalizar_texto_badge",
    "normalizar_tema_sidebar",
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
    "render_sidebar_theme_selector",
    "render_skeleton",
    "render_spacer",
    "render_table_html",
    "verificar_contrastes_sidebar",
]


if __name__ == "__main__":
    # Verificação de cores da sidebar:
    #   python components/componentes.py            -> relatório resumido
    #   python components/componentes.py --detalhe  -> relatório completo
    import sys

    verificar_contrastes_sidebar(detalhar="--detalhe" in sys.argv[1:])
