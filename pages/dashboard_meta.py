"""
dashboard_meta.py
=================
Dashboard de Metas Operacionais - TOTALE (Versão Production-Ready v2.6)
- Datas 100% padrão pt-BR (DD/MM/YYYY)
- Parsing robusto multi-formato
- Dias úteis Seg–Sáb (exclui domingos e feriados)
- Projeções automáticas + simulador de esforço por base
- Agrupamento oficial PROJETO/BASE (inclui sufixos VT)
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from html import escape
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)
from urllib.parse import quote as url_quote
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from pandas.io.formats.style import Styler
from streamlit.delta_generator import DeltaGenerator

# =============================================================================
# Imports opcionais
# =============================================================================

try:
    from streamlit_gsheets import GSheetsConnection  # type: ignore
except ImportError:
    GSheetsConnection = None  # type: ignore

try:
    import gdown  # type: ignore
except ImportError:
    gdown = None  # type: ignore

try:
    from components.componentes import (  # type: ignore
        aplicar_estilo as aplicar_estilo_corporativo,
        render_empty_state as render_empty_state_corporativo,
        render_insight as render_insight_corporativo,
        render_kpi as render_kpi_corporativo,
        render_progress_bar as render_progress_bar_corporativo,
        render_section_header as render_section_header_corporativo,
        render_status_pill as render_status_pill_corporativo,
        render_table_html as render_table_html_corporativo,
        render_hero_totale_2 as render_hero_totale_2
    )

    COMPONENTES_CORPORATIVOS = True
except (ImportError, ModuleNotFoundError):
    COMPONENTES_CORPORATIVOS = False
    aplicar_estilo_corporativo = None
    render_empty_state_corporativo = None
    render_insight_corporativo = None
    render_kpi_corporativo = None
    render_progress_bar_corporativo = None
    render_section_header_corporativo = None
    render_status_pill_corporativo = None
    render_table_html_corporativo = None


# =============================================================================
# Logging + Page config
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("dashboard_meta")

st.set_page_config(
    page_title="Dashboard de Metas | TOTALE",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Dashboard de Metas Operacionais - TOTALE v2.6"},
)


# =============================================================================
# Tipos / Constantes
# =============================================================================

Number = Union[int, float, np.integer, np.floating]
CorTema = Literal["laranja", "azul", "verde", "vermelho", "cinza", "roxo"]
DataFrameOrNumber = Union[float, int, pd.Series]

BASES_PRIORITARIAS: Tuple[str, ...] = ("NET-ABCDM", "NET-LESTE", "NET-GUARULHOS")
PROJETOS_NET: Tuple[str, ...] = (
    "NET-ABCDM",
    "NET-LESTE",
    "NET-LESTE VT",
    "NET-GUARULHOS",
    "NET-GRU VT",
)

# Formatos de data pt-BR (ordem de prioridade)
FORMATOS_DATA_BR: Tuple[str, ...] = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%y %H:%M:%S",
    "%d/%m/%y",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
)


def get_secret(key: str, default: str) -> str:
    try:
        return str(st.secrets.get(key, default))
    except (AttributeError, FileNotFoundError, KeyError):
        return default


@dataclass
class Configuracoes:
    URL_ATIVOS: str = field(
        default_factory=lambda: get_secret(
            "GSHEETS_URL_ATIVOS",
            "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg",
        )
    )
    SHEET_ID_ATIVOS: str = field(
        default_factory=lambda: get_secret(
            "GSHEETS_ID_ATIVOS", "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
        )
    )
    SHEET_ABA_ATIVOS: str = "lista_ativos"

    SHEET_ID_PROD: str = field(
        default_factory=lambda: get_secret(
            "GSHEETS_ID_PROD", "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
        )
    )
    SHEET_ABA_PROD: str = "Prod"

    DRIVE_ID_CONS: str = field(
        default_factory=lambda: get_secret(
            "DRIVE_ID_CONS", "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"
        )
    )

    TIMEOUT: int = 30
    TZ: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/Sao_Paulo"))

    CACHE_TTL_HIERARQUIA: int = 3600
    CACHE_TTL_CONSULTIVO: int = 600
    CACHE_TTL_PRODUCAO: int = 300


class Cores:
    PRIMARIA = "#012869"
    SECUNDARIA = "#F37C04"
    SUCESSO = "#059669"
    ALERTA = "#DC2626"
    ATENCAO = "#F59E0B"
    NEUTRO = "#64748B"
    FUNDO_CARD = "#FFFFFF"
    BORDA = "#E2E8F0"
    TEXTO = "#1F2937"
    TEXTO_3 = "#6B7280"

    MAPA_CORES: Dict[CorTema, str] = {
        "azul": PRIMARIA,
        "verde": SUCESSO,
        "vermelho": ALERTA,
        "laranja": SECUNDARIA,
        "cinza": NEUTRO,
        "roxo": "#7C3AED",
    }


class Metas:
    PRODUCAO_OS_BASE: Dict[str, int] = {
        "minima": 10_000,
        "meta_base": 11_000,
        "alta_perf": 12_000,
    }
    CONSULTIVO_BASE: Dict[str, int] = {
        "minima": 400,
        "meta_base": 525,
        "alta_perf": 600,
    }
    PRODUCAO_OS_GERAL: Dict[str, int] = {
        "minima": 30_000,
        "meta_base": 33_000,
        "alta_perf": 36_000,
    }
    CONSULTIVO_GERAL: Dict[str, int] = {
        "minima": 1_200,
        "meta_base": 1_575,
        "alta_perf": 1_800,
    }


CFG = Configuracoes()


# =============================================================================
# HTTP session
# =============================================================================


@st.cache_resource
def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "totale-dashboard/2.6"})
    return s


# =============================================================================
# Utils de dados
# =============================================================================


def normalizar_texto(texto: Any) -> str:
    if texto is None:
        return ""
    try:
        if pd.isna(texto):
            return ""
    except (TypeError, ValueError):
        pass
    txt = str(texto).strip()
    txt = "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    )
    return txt.upper()


def _to_float_safe(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def formatar_data_br(valor: Any, com_hora: bool = False) -> str:
    """Formata qualquer data/timestamp para padrão pt-BR."""
    if valor is None:
        return "-"
    try:
        if pd.isna(valor):
            return "-"
    except (TypeError, ValueError):
        return "-"

    if not isinstance(valor, (datetime, pd.Timestamp, date, np.datetime64)):
        return str(valor)

    try:
        ts = pd.Timestamp(valor)
        if pd.isna(ts):
            return "-"
        if com_hora:
            return ts.strftime("%d/%m/%Y %H:%M")
        return ts.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def mapear_colunas(df: pd.DataFrame, regras: Dict[str, List[str]]) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df.columns = pd.Index([str(c).strip() for c in df.columns])

    destino_para_origem: Dict[str, str] = {}
    origem_usada: Set[str] = set()
    colunas_norm: Dict[str, str] = {str(c): normalizar_texto(c) for c in df.columns}

    for destino, aliases in regras.items():
        if destino in destino_para_origem:
            continue

        aliases_norm = [normalizar_texto(a) for a in aliases]

        for alias in aliases_norm:
            for orig, cn in colunas_norm.items():
                if orig in origem_usada:
                    continue
                if cn == alias:
                    destino_para_origem[destino] = orig
                    origem_usada.add(orig)
                    break
            if destino in destino_para_origem:
                break

        if destino not in destino_para_origem:
            for alias in sorted(aliases_norm, key=len, reverse=True):
                if len(alias) < 2:
                    continue
                for orig, cn in colunas_norm.items():
                    if orig in origem_usada:
                        continue

                    if alias == "OS":
                        if cn == "OS" or any(
                            x in cn for x in ("NUMERO_OS", "NUM_OS", "N_OS")
                        ):
                            destino_para_origem[destino] = orig
                            origem_usada.add(orig)
                            break
                    elif alias in cn:
                        destino_para_origem[destino] = orig
                        origem_usada.add(orig)
                        break
                if destino in destino_para_origem:
                    break

    if destino_para_origem:
        df = df.rename(
            columns={orig: dest for dest, orig in destino_para_origem.items()}
        )

    return df.loc[:, ~df.columns.duplicated(keep="first")].copy()


def garantir_datetime(
    df: pd.DataFrame,
    col: str = "DATA",
    dayfirst: bool = True,
    origem: str = "br",
) -> pd.DataFrame:
    """
    Converte coluna de data.
    - origem='br'  → DD/MM/AAAA (consultivos)
    - origem='us'  → MM/DD/AAAA (produção)
    """
    if col not in df.columns or df.empty:
        return df

    df = df.copy()
    serie = df[col]

    if pd.api.types.is_datetime64_any_dtype(serie):
        df[col] = pd.to_datetime(serie, errors="coerce")
        return df

    s = serie.astype(str).str.strip()
    s = s.replace(
        ["", "nan", "None", "NaT", "NaN", "-", "NULL", "none"],
        pd.NA,
    )

    # Formatos por origem
    if origem == "us":
        # Produção: MM/DD/YYYY
        formatos: Tuple[str, ...] = (
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
            "%m-%d-%Y %H:%M:%S",
            "%m-%d-%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%m/%d/%y %H:%M:%S",
            "%m/%d/%y",
        )
        dayfirst_fallback = False
    else:
        # Consultivo / padrão BR: DD/MM/YYYY
        formatos = (
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%y %H:%M:%S",
            "%d/%m/%y",
        )
        dayfirst_fallback = True

    resultado = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    restantes = s.notna()

    for fmt in formatos:
        if not restantes.any():
            break
        try:
            parsed = pd.to_datetime(s[restantes], format=fmt, errors="coerce")
            ok = parsed.notna()
            if ok.any():
                idx_ok = parsed.index[ok]
                resultado.loc[idx_ok] = parsed.loc[idx_ok]
                restantes.loc[idx_ok] = False
        except Exception:
            continue

    # Fallback
    if restantes.any():
        try:
            parsed = pd.to_datetime(
                s[restantes], dayfirst=dayfirst_fallback, errors="coerce"
            )
            ok = parsed.notna()
            if ok.any():
                idx_ok = parsed.index[ok]
                resultado.loc[idx_ok] = parsed.loc[idx_ok]
        except Exception as e:
            logger.warning(f"Falha no fallback datetime ({origem}) col={col}: {e}")

    df[col] = resultado

    # Log de sanidade (opcional)
    validas = int(resultado.notna().sum())
    if validas > 0:
        dmin = resultado.min()
        dmax = resultado.max()
        logger.info(
            f"[DATA {origem.upper()}] {validas} datas OK | "
            f"min={formatar_data_br(dmin)} max={formatar_data_br(dmax)}"
        )
    else:
        logger.warning(f"[DATA {origem.upper()}] Nenhuma data válida em '{col}'")

    return df


def garantir_login(df: pd.DataFrame, col: str = "LOGIN") -> pd.DataFrame:
    if col not in df.columns:
        return df
    df = df.copy()
    s = df[col].astype(str).str.strip().str.upper()
    invalidos = ["NAN", "NONE", "N/A", "<NA>", "", "NA"]
    s = s.replace(invalidos, np.nan)
    df[col] = s
    return df


def add_norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Pré-computa colunas normalizadas usadas em filtros/joins."""
    if df.empty:
        return df
    df = df.copy()
    for src, dst in [
        ("BASE", "_BASE_NORM"),
        ("LOGIN", "_LOGIN_NORM"),
        ("TECNICO", "_TECNICO_NORM"),
        ("PROJETO", "_PROJETO_NORM"),
    ]:
        if src in df.columns:
            df[dst] = df[src].map(normalizar_texto)
        else:
            df[dst] = ""

    # Se BASE vazia, herda do PROJETO
    if "_PROJETO_NORM" in df.columns and "_BASE_NORM" in df.columns:
        mask_base_vazia = df["_BASE_NORM"].isin(["", "NAO INFORMADO", "NAN", "NONE"])
        df.loc[mask_base_vazia, "_BASE_NORM"] = df.loc[mask_base_vazia, "_PROJETO_NORM"]
        if "BASE" in df.columns and "PROJETO" in df.columns:
            df.loc[mask_base_vazia, "BASE"] = df.loc[mask_base_vazia, "PROJETO"]

    return df


# =============================================================================
# Métricas / Projeção
# =============================================================================


class CalculosOperacionais:
    @staticmethod
    @lru_cache(maxsize=16)
    def feriados_brasil(ano: int) -> Tuple[date, ...]:
        """Feriados nacionais fixos + móveis (Carnaval, Sexta Santa, Corpus Christi)."""
        a = ano % 19
        b = ano // 100
        c = ano % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        L = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * L) // 451
        mes = (h + L - 7 * m + 114) // 31
        dia = ((h + L - 7 * m + 114) % 31) + 1
        pascoa = date(ano, mes, dia)

        feriados = {
            date(ano, 1, 1),
            date(ano, 4, 21),
            date(ano, 5, 1),
            date(ano, 9, 7),
            date(ano, 10, 12),
            date(ano, 11, 2),
            date(ano, 11, 15),
            date(ano, 11, 20),
            date(ano, 12, 25),
            pascoa - timedelta(days=48),  # Carnaval (seg)
            pascoa - timedelta(days=47),  # Carnaval (ter)
            pascoa - timedelta(days=2),  # Sexta Santa
            pascoa + timedelta(days=60),  # Corpus Christi
        }
        return tuple(sorted(feriados))

    @staticmethod
    def _busday_count(
        inicio: date, fim_inclusivo: date, feriados: Tuple[date, ...]
    ) -> int:
        """Dias úteis Seg–Sáb, excluindo domingos e feriados."""
        if fim_inclusivo < inicio:
            return 0
        hol = np.array([np.datetime64(d) for d in feriados], dtype="datetime64[D]")
        return int(
            np.busday_count(
                np.datetime64(inicio),
                np.datetime64(fim_inclusivo + timedelta(days=1)),
                weekmask="Mon Tue Wed Thu Fri Sat",
                holidays=hol,
            )
        )

    @staticmethod
    @lru_cache(maxsize=256)
    def fator_por_data_max(data_max: date) -> Tuple[float, int, int, int]:
        """
        Retorna: (fator, dias_faltantes, dias_totais, dias_trabalhados)
        Baseado no mês vigente da última data da base.
        """
        inicio_mes = data_max.replace(day=1)
        prox_mes = (inicio_mes.replace(day=28) + timedelta(days=4)).replace(day=1)
        fim_mes = prox_mes - timedelta(days=1)

        feriados = CalculosOperacionais.feriados_brasil(data_max.year)
        total = CalculosOperacionais._busday_count(inicio_mes, fim_mes, feriados)
        decorridos = CalculosOperacionais._busday_count(inicio_mes, data_max, feriados)

        faltantes = max(0, total - decorridos)
        fator = (total / decorridos) if decorridos > 0 else 1.0
        return float(fator), int(faltantes), int(total), int(decorridos)

    @staticmethod
    def fator_projecao(
        df: pd.DataFrame, coluna_data: str = "DATA"
    ) -> Tuple[float, int, int, int]:
        if df.empty or coluna_data not in df.columns:
            return 1.0, 0, 0, 0
        datas = pd.to_datetime(df[coluna_data], errors="coerce").dropna()
        if datas.empty:
            return 1.0, 0, 0, 0
        dmax_ts = datas.max()
        if pd.isna(dmax_ts):
            return 1.0, 0, 0, 0
        dmax = dmax_ts.normalize().date()
        return CalculosOperacionais.fator_por_data_max(dmax)

    @staticmethod
    def calcular_atingimento(
        valor: DataFrameOrNumber, meta: float
    ) -> DataFrameOrNumber:
        if meta <= 0:
            if isinstance(valor, pd.Series):
                return valor * 0.0
            return 0.0
        if isinstance(valor, pd.Series):
            return (valor / meta) * 100
        return (float(valor) / meta) * 100.0


def get_status_geral(
    valor: Any, tipo: Literal["os", "cons"] = "os"
) -> Tuple[str, str, str]:
    valor_f = _to_float_safe(valor)
    metas = Metas.PRODUCAO_OS_GERAL if tipo == "os" else Metas.CONSULTIVO_GERAL
    if valor_f >= metas["alta_perf"]:
        return "Alta Performance", Cores.SUCESSO, "#D1FAE5"
    if valor_f >= metas["meta_base"]:
        return "Meta Atingida", Cores.SUCESSO, "#D1FAE5"
    if valor_f >= metas["minima"]:
        return "Atenção / Mínimo", Cores.ATENCAO, "#FEF3C7"
    return "Crítico / Abaixo", Cores.ALERTA, "#FEE2E2"


def get_status_base(valor: Any, metas: Dict[str, int]) -> Tuple[str, str, str]:
    valor_f = _to_float_safe(valor)
    if valor_f >= float(metas["alta_perf"]):
        return "Alta Performance", Cores.SUCESSO, "#D1FAE5"
    if valor_f >= float(metas["meta_base"]):
        return "Meta Atingida", Cores.SUCESSO, "#D1FAE5"
    if valor_f >= float(metas["minima"]):
        return "Atenção / Mínimo", Cores.ATENCAO, "#FEF3C7"
    return "Crítico / Abaixo", Cores.ALERTA, "#FEE2E2"


# =============================================================================
# CSS
# =============================================================================


def aplicar_estilo_local() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');
        html, body, [class*="css"] {{
            font-family: 'IBM Plex Sans', sans-serif !important;
        }}
        h1, h2, h3 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            color: {Cores.PRIMARIA};
        }}
        .main .block-container {{
            padding-top: 1.2rem;
            max-width: 1440px;
        }}
        .hero-totale {{
            background: linear-gradient(135deg, {Cores.PRIMARIA} 0%, #02419c 60%, {Cores.SECUNDARIA} 100%);
            padding: 1.8rem 2rem;
            border-radius: 12px;
            color: #FFFFFF;
            box-shadow: 0 4px 14px rgba(1, 40, 105, 0.15);
            margin-bottom: 1.5rem;
        }}
        .hero-totale h1 {{ color: #FFFFFF !important; margin: 0; font-size: 1.85rem; }}
        .hero-totale p {{ color: #E2E8F0 !important; margin: 0.45rem 0 0 0; }}
        .card-kpi {{
            background: {Cores.FUNDO_CARD};
            border-radius: 10px;
            padding: 1.1rem 1.2rem;
            border: 1px solid {Cores.BORDA};
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            height: 100%;
        }}
        .card-kpi-titulo {{
            font-size: 0.80rem;
            font-weight: 700;
            color: {Cores.NEUTRO};
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }}
        .card-kpi-valor {{
            font-size: 1.9rem;
            font-weight: 800;
            color: {Cores.TEXTO};
            margin: 0.35rem 0 0.2rem 0;
        }}
        .card-kpi-sub {{ font-size: 0.8rem; color: {Cores.TEXTO_3}; }}
        .base-card {{
            background: #FFFFFF;
            border: 1px solid {Cores.BORDA};
            border-top: 4px solid {Cores.SECUNDARIA};
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            height: 100%;
        }}
        .base-title {{
            color: {Cores.PRIMARIA};
            font-weight: 800;
            margin-bottom: 0.7rem;
        }}
        .pill {{
            display: inline-block;
            padding: 0.22rem 0.55rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 800;
            border: 1px solid {Cores.BORDA};
            background: #F8FAFC;
            color: {Cores.TEXTO};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


if COMPONENTES_CORPORATIVOS and aplicar_estilo_corporativo is not None:
    try:
        aplicar_estilo_corporativo()
    except Exception as e:
        logger.warning(f"Falha ao aplicar estilo corporativo: {e}")

aplicar_estilo_local()


# =============================================================================
# Render wrappers
# =============================================================================


def render_section_header_seguro(
    titulo: str,
    subtitulo: str = "",
    icone: str = "",
    badge: str = "",
    badge_tipo: CorTema = "laranja",
) -> None:
    if COMPONENTES_CORPORATIVOS and render_section_header_corporativo is not None:
        try:
            render_section_header_corporativo(
                titulo,
                subtitulo=subtitulo,
                icone=icone,
                badge=badge,
                badge_tipo=badge_tipo,
            )
            return
        except Exception as e:
            logger.warning(f"Falha render_section_header_corporativo: {e}")

    st.subheader(f"{icone} {titulo}".strip())
    if subtitulo:
        st.caption(subtitulo)


def render_kpi_fallback(
    container: DeltaGenerator, titulo: str, valor: str, subtexto: str, cor_tema: CorTema
) -> None:
    cor_hex = Cores.MAPA_CORES.get(cor_tema, Cores.PRIMARIA)
    container.markdown(
        f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">{escape(titulo)}</div>
            <div class="card-kpi-valor" style="color:{cor_hex};">{escape(valor)}</div>
            <div class="card-kpi-sub">{escape(subtexto)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_seguro(
    container: DeltaGenerator, titulo: str, valor: str, subtexto: str, cor_tema: CorTema
) -> None:
    if COMPONENTES_CORPORATIVOS and render_kpi_corporativo is not None:
        try:
            render_kpi_corporativo(container, titulo, valor, subtexto, cor_tema)
            return
        except Exception as e:
            logger.warning(f"Falha render_kpi_corporativo: {e}")
    render_kpi_fallback(container, titulo, valor, subtexto, cor_tema)


def render_empty_state_seguro(titulo: str, mensagem: str) -> None:
    if COMPONENTES_CORPORATIVOS and render_empty_state_corporativo is not None:
        try:
            render_empty_state_corporativo(titulo, mensagem)
            return
        except Exception as e:
            logger.warning(f"Falha render_empty_state_corporativo: {e}")
    st.info(f"{titulo}: {mensagem}")


def render_insight_seguro(
    mensagem: str, tipo: Literal["info", "alerta", "critico"] = "info"
) -> None:
    if COMPONENTES_CORPORATIVOS and render_insight_corporativo is not None:
        try:
            render_insight_corporativo(mensagem, tipo=tipo)
            return
        except Exception as e:
            logger.warning(f"Falha render_insight_corporativo: {e}")

    if tipo in ("alerta", "critico"):
        st.warning(mensagem)
    else:
        st.info(mensagem)


def render_progress_bar_seguro(
    label: str, valor: float, meta: float, unidade: str = ""
) -> None:
    if COMPONENTES_CORPORATIVOS and render_progress_bar_corporativo is not None:
        try:
            render_progress_bar_corporativo(label, valor, meta, unidade)
            return
        except Exception as e:
            logger.warning(f"Falha render_progress_bar_corporativo: {e}")

    valor_num = _to_float_safe(valor)
    meta_num = _to_float_safe(meta)
    pct_raw = CalculosOperacionais.calcular_atingimento(valor_num, meta_num)
    pct = _to_float_safe(pct_raw)
    st.progress(
        min(pct / 100.0, 1.0),
        text=f"{label}: {pct:.1f}% ({valor_num}{unidade} / {meta_num}{unidade})",
    )


def render_status_pill_seguro(texto: str, status: str) -> str:
    if COMPONENTES_CORPORATIVOS and render_status_pill_corporativo is not None:
        try:
            status_tipo = (
                "sucesso"
                if "Meta" in status or "Performance" in status
                else "pendente" if "Atenção" in status else "erro"
            )
            return render_status_pill_corporativo(texto, status_tipo)
        except Exception as e:
            logger.warning(f"Falha render_status_pill_corporativo: {e}")
    return f"<span class='pill'>{escape(texto)}</span>"


def _styler_apply_color_rules(
    df: pd.DataFrame,
    color_rules: Dict[str, List[Tuple[Callable[[Any], bool], str]]],
) -> Styler:
    styler = df.style

    def style_cell(val: Any, rules: List[Tuple[Callable[[Any], bool], str]]) -> str:
        for pred, color in rules:
            try:
                if pred(val):
                    return f"color: {color}; font-weight: 700;"
            except Exception as e:
                logger.debug(f"Falha na regra de estilo para valor '{val}': {e}")
                continue
        return ""

    for col, rules in color_rules.items():
        if col in df.columns:
            try:
                styler = styler.map(  # type: ignore[attr-defined]
                    lambda v, rr=rules: style_cell(v, rr), subset=[col]
                )
            except AttributeError:
                styler = styler.applymap(  # type: ignore[attr-defined]
                    lambda v, rr=rules: style_cell(v, rr), subset=[col]
                )
    return styler


def render_table_seguro(
    df: pd.DataFrame,
    titulo: str = "",
    fmt: Optional[Any] = None,
    num_cols: Optional[List[str]] = None,
    color_rules: Optional[Dict[str, List[Tuple[Callable[[Any], bool], str]]]] = None,
) -> None:
    if COMPONENTES_CORPORATIVOS and render_table_html_corporativo is not None:
        try:
            render_table_html_corporativo(
                df,
                titulo=titulo,
                fmt=fmt or {},
                color_rules=color_rules or {},
                num_cols=num_cols or [],
            )
            return
        except Exception as e:
            logger.warning(
                f"Falha render_table_html corporativo; fallback st.dataframe: {e}"
            )

    if titulo:
        st.markdown(f"**{titulo}**")

    _df = df.copy()
    if fmt:
        styler = _df.style.format(fmt)
    else:
        styler = _df.style

    if color_rules:
        styler = _styler_apply_color_rules(_df, color_rules)

    st.dataframe(styler, use_container_width=True, hide_index=True)


# =============================================================================
# Charts
# =============================================================================


def render_gauge(
    valor: int, min_val: int, base: int, alta: int, titulo: str
) -> go.Figure:
    max_range = max(int(alta * 1.2), int(valor * 1.2), 1)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=valor,
            title={"text": titulo, "font": {"size": 16, "color": Cores.PRIMARIA}},
            delta={
                "reference": base,
                "increasing": {"color": Cores.SUCESSO},
                "decreasing": {"color": Cores.ALERTA},
            },
            gauge={
                "axis": {"range": [0, max_range]},
                "bar": {"color": Cores.PRIMARIA},
                "steps": [
                    {"range": [0, min_val], "color": "#FEE2E2"},
                    {"range": [min_val, base], "color": "#FEF3C7"},
                    {"range": [base, max_range], "color": "#D1FAE5"},
                ],
                "threshold": {
                    "line": {"color": Cores.SECUNDARIA, "width": 4},
                    "thickness": 0.75,
                    "value": base,
                },
            },
        )
    )
    fig.update_layout(
        height=250, margin=dict(l=10, r=10, t=35, b=10), paper_bgcolor="rgba(0,0,0,0)"
    )
    return fig


# =============================================================================
# ETL
# =============================================================================


def _ler_csv_bytes(conteudo: bytes) -> pd.DataFrame:
    if not conteudo or len(conteudo) < 10:
        raise ValueError("CSV vazio ou corrompido.")

    head = conteudo[:4096]
    seps = [b";", b",", b"\t", b"|"]
    sep_counts = [(s, head.count(s)) for s in seps]
    sep_best = max(sep_counts, key=lambda x: x[1])
    sep_char = sep_best[0].decode("utf-8", errors="ignore") if sep_best[1] > 0 else ";"

    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(
                io.BytesIO(conteudo),
                sep=sep_char,
                encoding=enc,
                dtype=str,
                low_memory=False,
                on_bad_lines="skip",
            )
            if not df.empty and len(df.columns) > 1:
                return df
        except Exception:
            continue
    raise ValueError("Não foi possível decodificar o CSV.")


def _baixar_drive_csv(file_id: str) -> bytes:
    sess = http_session()
    url = f"https://drive.google.com/uc?id={file_id}&export=download"

    if gdown is not None:
        download_fn = getattr(gdown, "download", None)
        if callable(download_fn):
            tmp_path: Optional[str] = None
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=".csv")
                os.close(fd)
                download_fn(
                    f"https://drive.google.com/uc?id={file_id}", tmp_path, quiet=True
                )
                with open(tmp_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"gdown falhou, fallback para requests: {e}")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError as e:
                        logger.error(f"Não removeu tmp {tmp_path}: {e}")

    resp = sess.get(url, stream=True, timeout=CFG.TIMEOUT)
    resp.raise_for_status()

    for key, value in resp.cookies.items():
        if key.startswith("download_warning"):
            url += f"&confirm={value}"
            resp = sess.get(url, stream=True, timeout=CFG.TIMEOUT)
            resp.raise_for_status()
            break

    return resp.content


@st.cache_data(ttl=CFG.CACHE_TTL_HIERARQUIA, show_spinner="Carregando hierarquia...")
def carregar_hierarquia() -> pd.DataFrame:
    df = pd.DataFrame()
    if GSheetsConnection is not None:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            resultado = conn.read(  # type: ignore[attr-defined]
                spreadsheet=CFG.URL_ATIVOS, worksheet=CFG.SHEET_ABA_ATIVOS, ttl=0
            )
            if isinstance(resultado, pd.DataFrame):
                df = resultado
        except Exception as e:
            logger.warning(f"Hierarquia via GSheetsConnection falhou: {e}")

    if df.empty:
        try:
            sess = http_session()
            csv_url = (
                f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_ATIVOS}"
                f"/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_ATIVOS)}"
            )
            resp = sess.get(csv_url, timeout=CFG.TIMEOUT)
            resp.raise_for_status()
            if len(resp.content) > 10:
                df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        except Exception as e:
            logger.warning(f"Hierarquia via gviz falhou: {e}")

    if df.empty:
        st.warning("Não foi possível carregar os dados da hierarquia.")
        return pd.DataFrame()

    df = mapear_colunas(
        df,
        {
            "LOGIN": ["LOGIN", "USER", "USUARIO", "MATRICULA"],
            "TECNICO": ["TECNICO", "NOME", "COLABORADOR"],
            "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR"],
            "BASE": ["BASE", "FILIAL", "REGIONAL"],
        },
    )
    for col in ("LOGIN", "TECNICO", "MONITOR", "BASE"):
        if col not in df.columns:
            df[col] = "Não Informado"

    df = garantir_login(df, "LOGIN")
    df = (
        df.dropna(subset=["LOGIN"])
        .drop_duplicates(subset=["LOGIN"])
        .reset_index(drop=True)
    )
    return add_norm_cols(df)


@st.cache_data(
    ttl=CFG.CACHE_TTL_CONSULTIVO, show_spinner="Carregando consultivos (Drive)..."
)
def carregar_consultivos() -> Tuple[pd.DataFrame, Optional[str]]:
    try:
        content = _baixar_drive_csv(CFG.DRIVE_ID_CONS)
        df = _ler_csv_bytes(content)
        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_CRIACAO",
                    "CRIACAO",
                    "DATA_FINALIZACAO",
                    "DT_FINALIZACAO",
                    "DATA FINALIZACAO",
                ],
                "LOGIN": ["LOGIN NETSALES", "LOGIN", "USUARIO", "MATRICULA"],
                "PROJETO": ["PROJETO", "CONTRATO"],
                "BASE": ["BASE", "FILIAL"],
                "TECNICO": ["TECNICO", "NOME"],
                "MONITOR": ["MONITOR", "SUPERVISOR"],
            },
        )
        # Consultivo = DD/MM/AAAA (pt-BR)
        return garantir_datetime(df, col="DATA", origem="br"), None
    except Exception as e:
        logger.exception("Erro ao carregar consultivos")
        return pd.DataFrame(), f"Consultivo: {type(e).__name__}: {str(e)[:180]}"


@st.cache_data(
    ttl=CFG.CACHE_TTL_PRODUCAO, show_spinner="Carregando produção (GSheets)..."
)
def carregar_producao() -> Tuple[pd.DataFrame, Optional[str]]:
    try:
        sess = http_session()
        url = (
            f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_PROD}"
            f"/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_PROD)}"
        )
        resp = sess.get(url, timeout=CFG.TIMEOUT)
        resp.raise_for_status()

        if "<!doctype html" in resp.text.lower()[:1000]:
            return pd.DataFrame(), "Produção: planilha privada/indisponível."

        df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
        df = mapear_colunas(
            df,
            {
                "DATA": ["DATA", "DT_EXECUCAO", "EXECUCAO", "DT_FINALIZACAO"],
                "LOGIN": [
                    "LOGIN",
                    "MATRICULA",
                    "USER",
                    "CÓD.EQUIPE",
                    "CODEQUIPE",
                    "CódEquipe",
                ],
                "NUM_OS": ["NUM_OS", "NUMERO_OS", "OS", "NUM OS"],
                "PROJETO": [
                    "PROJETO",
                    "CAMPANHA",
                    "OPERACAO",
                    "OPERAÇÃO",
                    "CONTRATO_PROJETO",
                ],
                "BASE": ["BASE", "FILIAL"],
                "TECNICO": [
                    "NOME EQUIPE",
                    "TECNICO",
                    "NOME",
                    "CÓDAUXEQUIPE",
                    "CódAuxEquipe",
                ],
                "MONITOR": ["MONITOR", "SUPERVISOR"],
            },
        )
        # Produção = MM/DD/AAAA (US)
        return garantir_datetime(df, col="DATA", origem="us"), None
    except Exception as e:
        logger.exception("Erro ao carregar produção")
        return pd.DataFrame(), f"Produção: {type(e).__name__}: {str(e)[:180]}"


# =============================================================================
# Enriquecimento
# =============================================================================


def _is_value_empty(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.Series(dtype=bool)
    norm_text = series.map(normalizar_texto)
    return series.isna() | norm_text.isin({"", "NAN", "NONE", "NAO INFORMADO"})


def _enriquecer_dados_impl(df: pd.DataFrame, hierarquia: pd.DataFrame) -> pd.DataFrame:
    if df.empty or hierarquia.empty:
        return df

    dfm = add_norm_cols(df)

    lk_login = (
        hierarquia.dropna(subset=["_LOGIN_NORM"])
        .drop_duplicates("_LOGIN_NORM")[["_LOGIN_NORM", "TECNICO", "MONITOR", "BASE"]]
        .rename(columns={c: f"{c}_H" for c in ("TECNICO", "MONITOR", "BASE")})
    )

    dfm = dfm.merge(lk_login, on="_LOGIN_NORM", how="left")

    for c in ("TECNICO", "MONITOR", "BASE"):
        if c not in dfm.columns:
            dfm[c] = pd.NA
        vazio = _is_value_empty(dfm[c])
        dfm.loc[vazio, c] = dfm.loc[vazio, f"{c}_H"]
        dfm = dfm.drop(columns=f"{c}_H")

    lk_tec = (
        hierarquia.dropna(subset=["_TECNICO_NORM"])
        .drop_duplicates("_TECNICO_NORM")[["_TECNICO_NORM", "MONITOR", "BASE"]]
        .rename(columns={"MONITOR": "MONITOR_H2", "BASE": "BASE_H2"})
    )

    dfm = dfm.merge(lk_tec, on="_TECNICO_NORM", how="left")

    for c, ch in (("MONITOR", "MONITOR_H2"), ("BASE", "BASE_H2")):
        if c not in dfm.columns:
            dfm[c] = pd.NA
        vazio = _is_value_empty(dfm[c])
        dfm.loc[vazio, c] = dfm.loc[vazio, ch]
        dfm = dfm.drop(columns=ch)

    dfm = dfm.fillna("Não Informado")
    return add_norm_cols(dfm)


@st.cache_data(show_spinner="Processando e enriquecendo dados...")
def get_enriched_data(
    df_prod_raw: pd.DataFrame, df_cons_raw: pd.DataFrame, df_hierarquia: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df_prod = _enriquecer_dados_impl(df_prod_raw, df_hierarquia)
    df_cons = _enriquecer_dados_impl(df_cons_raw, df_hierarquia)
    return df_prod.copy(), df_cons.copy()


# =============================================================================
# Carregamento
# =============================================================================

df_hierarquia_raw = carregar_hierarquia()
df_cons_raw, erro_cons = carregar_consultivos()
df_prod_raw, erro_prod = carregar_producao()

df_prod, df_cons = get_enriched_data(df_prod_raw, df_cons_raw, df_hierarquia_raw)


# =============================================================================
# Sidebar / Filtros
# =============================================================================


def _unique_sorted(series: Optional[pd.Series]) -> List[str]:
    if series is None or series.empty:
        return []
    vals = series.dropna().astype(str).str.strip()
    return sorted(vals[vals != ""].unique().tolist())


def _get_col_safe(df: pd.DataFrame, col: str) -> Optional[pd.Series]:
    if col in df.columns:
        return df[col]
    return None


with st.sidebar:
    st.markdown("### Filtros Globais")

    all_bases: Set[str] = set(_unique_sorted(_get_col_safe(df_prod, "BASE"))) | set(
        _unique_sorted(_get_col_safe(df_cons, "BASE"))
    )
    all_monitores: Set[str] = set(
        _unique_sorted(_get_col_safe(df_prod, "MONITOR"))
    ) | set(_unique_sorted(_get_col_safe(df_cons, "MONITOR")))
    all_projetos: Set[str] = set(
        _unique_sorted(_get_col_safe(df_prod, "PROJETO"))
    ) | set(_unique_sorted(_get_col_safe(df_cons, "PROJETO")))

    bases_opts = sorted(all_bases)
    monitores_opts = sorted(all_monitores)
    projetos_opts = sorted(all_projetos)

    st.divider()
    st.markdown("### Filtro Rápido")
    filtro_net = st.checkbox(
        "Filtrar apenas NET (ABCDM/LESTE/GUARULHOS)", value=False, key="filtro_net"
    )

    default_projetos = (
        [p for p in PROJETOS_NET if p in projetos_opts] if filtro_net else []
    )

    filtro_projeto: List[str] = st.multiselect(
        "Projeto",
        options=projetos_opts,
        default=default_projetos,
        placeholder="Todos",
        key="select_projetos",
    )
    filtro_base: List[str] = st.multiselect(
        "Base / Regional", options=bases_opts, placeholder="Todas", key="select_bases"
    )
    filtro_monitor: List[str] = st.multiselect(
        "Monitor", options=monitores_opts, placeholder="Todos", key="select_monitores"
    )

    series_datas_list: List[pd.Series] = []
    for _df in (df_prod, df_cons):
        col_d = _get_col_safe(_df, "DATA")
        if col_d is not None:
            series_datas_list.append(col_d)

    todas_datas = (
        pd.concat(series_datas_list, ignore_index=True).dropna()
        if series_datas_list
        else pd.Series(dtype="datetime64[ns]")
    )

    filtro_datas: Optional[Tuple[date, date]] = None
    if not todas_datas.empty:
        min_ts = pd.to_datetime(todas_datas.min())
        max_ts = pd.to_datetime(todas_datas.max())
        if pd.notna(min_ts) and pd.notna(max_ts):
            min_dt: date = min_ts.date()
            max_dt: date = max_ts.date()
            resultado_data = st.date_input(
                "Período",
                value=(min_dt, max_dt),
                min_value=min_dt,
                max_value=max_dt,
                format="DD/MM/YYYY",  # padrão pt-BR no seletor
                key="date_range",
            )
            if isinstance(resultado_data, tuple) and len(resultado_data) == 2:
                filtro_datas = (resultado_data[0], resultado_data[1])
            elif isinstance(resultado_data, date):
                filtro_datas = (resultado_data, resultado_data)

    st.divider()
    if st.button(
        "Limpar Cache e Recarregar", use_container_width=True, key="btn_refresh"
    ):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    st.caption(f"Atualizado: {datetime.now(CFG.TZ).strftime('%d/%m/%Y %H:%M')}")
    st.caption(f"Hierarquia: {len(df_hierarquia_raw):,}")
    st.caption(f"Produção: {len(df_prod):,} | Consultivo: {len(df_cons):,}")


def aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)
    if filtro_base and "BASE" in df.columns:
        mask &= df["BASE"].isin(filtro_base)
    if filtro_monitor and "MONITOR" in df.columns:
        mask &= df["MONITOR"].isin(filtro_monitor)
    if filtro_projeto and "PROJETO" in df.columns:
        mask &= df["PROJETO"].isin(filtro_projeto)

    if filtro_datas is not None and "DATA" in df.columns:
        start_date, end_date = filtro_datas
        sdt = pd.to_datetime(df["DATA"], errors="coerce").dt.normalize()
        mask &= (sdt >= pd.Timestamp(start_date)) & (sdt <= pd.Timestamp(end_date))

    return df.loc[mask]


df_prod_f = aplicar_filtros(df_prod)
df_cons_f = aplicar_filtros(df_cons)


# =============================================================================
# UI
# =============================================================================

render_hero_totale_2(
    titulo="🎯 Dashboard de Metas Operacionais",
    subtitulo="Gestão Integrada: Produção (O.S.) + Consultivos + Hierarquia + Bases",
    badge_texto="Atualizado junto a produção e consultivos",
    badge_tipo="info",
)

for err in [erro_prod, erro_cons]:
    if err:
        st.warning(f"Aviso de carregamento: {err}")

if df_hierarquia_raw.empty:
    render_insight_seguro(
        "Hierarquia vazia ou não pôde ser carregada.",
        tipo="critico",
    )

tab_prod, tab_cons, tab_bases, tab_abcdm, tab_leste, tab_guarulhos = st.tabs(
    [
        "📊 Produção",
        "💼 Consultivos",
        "🗂️ Bases",
        "📈 ABCDM",
        "📈 LESTE",
        "📈 GUARULHOS",
    ]
)


def render_aba_metricas(
    tab: DeltaGenerator,
    titulo_total: str,
    total: int,
    metas: Dict[str, int],
    df: pd.DataFrame,
    tipo: Literal["os", "cons"],
) -> Tuple[int, int]:
    with tab:
        render_section_header_seguro(
            titulo_total,
            "Acompanhamento operacional e projeção mensal",
            icone="📊" if tipo == "os" else "💼",
            badge="Produção" if tipo == "os" else "Consultivos",
            badge_tipo="azul" if tipo == "os" else "laranja",
        )

        fator, dias_rest, dias_totais, dias_trabalhados = (
            CalculosOperacionais.fator_projecao(df, "DATA")
        )
        projecao = int(total * fator)

        status_txt, status_cor, _ = get_status_geral(total, tipo)
        cor_status: CorTema = "verde" if status_cor == Cores.SUCESSO else "vermelho"

        ating_raw = CalculosOperacionais.calcular_atingimento(
            float(total), float(metas["meta_base"])
        )
        ating = _to_float_safe(ating_raw)

        c1, c2, c3, c4 = st.columns(4)
        render_kpi_seguro(
            c1,
            titulo_total,
            f"{total:,}".replace(",", "."),
            f"{ating:.1f}% da meta base",
            "azul",
        )
        render_kpi_seguro(
            c2,
            "Meta base",
            f"{metas['meta_base']:,}".replace(",", "."),
            f"Variação: {total - metas['meta_base']:+,}".replace(",", "."),
            "laranja",
        )
        render_kpi_seguro(
            c3,
            "Projeção mês",
            f"{projecao:,}".replace(",", "."),
            f"{dias_trabalhados} trabalhados | {dias_rest} faltantes",
            "verde",
        )
        render_kpi_seguro(c4, "Status", status_txt, "Avaliação no período", cor_status)

        st.plotly_chart(
            render_gauge(
                total,
                metas["minima"],
                metas["meta_base"],
                metas["alta_perf"],
                f"Termômetro {titulo_total}",
            ),
            use_container_width=True,
        )

        if "DATA" in df.columns and pd.api.types.is_datetime64_any_dtype(df["DATA"]):
            daily = (
                df.dropna(subset=["DATA"])
                .set_index("DATA")
                .resample("D")
                .size()
                .reset_index(name="Volume")
            )
            daily["Acumulado"] = daily["Volume"].cumsum()
            fig = px.area(
                daily, x="DATA", y="Acumulado", title="Evolução acumulada no período"
            )
            fig.add_hline(
                y=metas["meta_base"], line_dash="dash", line_color=Cores.SECUNDARIA
            )
            fig.update_layout(
                height=260,
                margin=dict(l=10, r=10, t=45, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis_tickformat="%d/%m/%Y",  # eixo X em pt-BR
            )
            st.plotly_chart(fig, use_container_width=True)

        return dias_rest, projecao


dias_rest_prod, proj_prod = render_aba_metricas(
    tab_prod,
    "O.S. realizadas",
    len(df_prod_f),
    Metas.PRODUCAO_OS_GERAL,
    df_prod_f,
    "os",
)
dias_rest_cons, proj_cons = render_aba_metricas(
    tab_cons,
    "Consultivos",
    len(df_cons_f),
    Metas.CONSULTIVO_GERAL,
    df_cons_f,
    "cons",
)


def _resumo_por_base(df: pd.DataFrame, nome_coluna: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["_BASE_NORM", "Base", nome_coluna, "MAX_DATA"])

    col_group = "_PROJETO_NORM" if "_PROJETO_NORM" in df.columns else "_BASE_NORM"
    col_display = "PROJETO" if "PROJETO" in df.columns else "BASE"

    g = (
        df.dropna(subset=["DATA"], how="all")
        .groupby(col_group, dropna=False)
        .agg(
            Base=(col_display, lambda s: s.iloc[0] if len(s) > 0 else "Não Informado"),
            **{nome_coluna: ("DATA", "size")},
            MAX_DATA=("DATA", "max"),
        )
        .reset_index()
        .rename(columns={col_group: "_BASE_NORM"})
    )
    g[nome_coluna] = g[nome_coluna].fillna(0).astype(int)
    return g


def _projecao_por_base(prod: pd.DataFrame, cons: pd.DataFrame) -> pd.DataFrame:
    a = _resumo_por_base(prod, "O.S.")
    b = _resumo_por_base(cons, "Consultivos")
    dfm = a.merge(b, on="_BASE_NORM", how="outer", suffixes=("", "_CONS"))

    if "Base_CONS" in dfm.columns:
        dfm["Base"] = dfm["Base"].fillna(dfm["Base_CONS"])
        dfm.drop(columns=["Base_CONS"], inplace=True)
    dfm["Base"] = dfm["Base"].fillna("Não Informado")

    dfm["O.S."] = (
        pd.to_numeric(dfm.get("O.S.", pd.Series(0, index=dfm.index)), errors="coerce")
        .fillna(0)
        .astype(int)
    )
    dfm["Consultivos"] = (
        pd.to_numeric(
            dfm.get("Consultivos", pd.Series(0, index=dfm.index)), errors="coerce"
        )
        .fillna(0)
        .astype(int)
    )

    def fatores_por_data(coluna_data: str) -> List[Tuple[float, int, int, int]]:
        datas = (
            pd.to_datetime(dfm[coluna_data], errors="coerce")
            if coluna_data in dfm.columns
            else pd.Series([pd.NaT] * len(dfm), index=dfm.index)
        )
        fatores: List[Tuple[float, int, int, int]] = []
        for data_max in datas:
            if pd.notna(data_max):
                fatores.append(
                    CalculosOperacionais.fator_por_data_max(data_max.normalize().date())
                )
            else:
                fatores.append((1.0, 0, 0, 0))
        return fatores

    proj_prod = fatores_por_data("MAX_DATA")
    proj_cons = fatores_por_data("MAX_DATA_CONS")

    dfm["Fator O.S."] = [p[0] for p in proj_prod]
    dfm["Dias trabalhados O.S."] = [p[3] for p in proj_prod]
    dfm["Dias faltantes O.S."] = [p[1] for p in proj_prod]
    dfm["Dias totais O.S."] = [p[2] for p in proj_prod]

    dfm["Fator Consultivos"] = [p[0] for p in proj_cons]
    dfm["Dias trabalhados Consultivos"] = [p[3] for p in proj_cons]
    dfm["Dias faltantes Consultivos"] = [p[1] for p in proj_cons]
    dfm["Dias totais Consultivos"] = [p[2] for p in proj_cons]

    # Exibição pt-BR
    dfm["Última data O.S."] = dfm["MAX_DATA"].apply(lambda x: formatar_data_br(x))
    dfm["Última data Consultivos"] = dfm.get(
        "MAX_DATA_CONS", pd.Series([pd.NaT] * len(dfm))
    ).apply(lambda x: formatar_data_br(x))

    dfm["O.S. projetadas"] = (dfm["O.S."] * dfm["Fator O.S."]).astype(int)
    dfm["Consultivos projetados"] = (
        dfm["Consultivos"] * dfm["Fator Consultivos"]
    ).astype(int)

    ating_os = CalculosOperacionais.calcular_atingimento(
        dfm["O.S. projetadas"], float(Metas.PRODUCAO_OS_BASE["meta_base"])
    )
    ating_cons = CalculosOperacionais.calcular_atingimento(
        dfm["Consultivos projetados"], float(Metas.CONSULTIVO_BASE["meta_base"])
    )

    dfm["% Meta O.S. (proj)"] = np.round(cast(pd.Series, ating_os).astype(float), 1)
    dfm["% Meta Cons. (proj)"] = np.round(cast(pd.Series, ating_cons).astype(float), 1)

    dfm["A fazer após projeção O.S."] = np.maximum(
        Metas.PRODUCAO_OS_BASE["meta_base"] - dfm["O.S. projetadas"], 0
    ).astype(int)
    dfm["A fazer após projeção consultivos"] = np.maximum(
        Metas.CONSULTIVO_BASE["meta_base"] - dfm["Consultivos projetados"], 0
    ).astype(int)

    return dfm.sort_values("Base").reset_index(drop=True)


df_proj_base = _projecao_por_base(df_prod_f, df_cons_f)


def _obter_contagem_projeto_base(
    df: pd.DataFrame, chave: str
) -> Tuple[int, Optional[pd.Timestamp]]:
    """Contagem por PROJETO ou BASE (inclui sufixos VT, GRU etc.)."""
    if df.empty:
        return 0, None
    chave_norm = normalizar_texto(chave)

    mask = pd.Series(False, index=df.index)
    if "_PROJETO_NORM" in df.columns:
        mask |= df["_PROJETO_NORM"].str.contains(chave_norm, na=False)
    if "_BASE_NORM" in df.columns:
        mask |= df["_BASE_NORM"].str.contains(chave_norm, na=False)

    df_sub = df.loc[mask]
    total = len(df_sub)
    data_max = (
        pd.to_datetime(df_sub["DATA"], errors="coerce").max()
        if "DATA" in df_sub.columns and not df_sub.empty
        else None
    )
    return total, data_max if data_max is not None and pd.notna(data_max) else None


def render_aba_projecao_base(
    tab: DeltaGenerator, base_nome: str, df_projecoes: pd.DataFrame
) -> None:
    with tab:
        render_section_header_seguro(
            f"Projeção {base_nome}",
            "Fechamento projetado da base no período selecionado",
            icone="📈",
            badge="PROJEÇÃO POR BASE",
            badge_tipo="azul",
        )

        base_norm = normalizar_texto(base_nome)

        # Contagem oficial e datas máximas
        os_atual, max_dt_os = _obter_contagem_projeto_base(df_prod_f, base_nome)
        cons_atual, max_dt_cons = _obter_contagem_projeto_base(df_cons_f, base_nome)

        # Dias úteis (Seg-Sáb, sem domingos/feriados)
        dmax_os = (
            max_dt_os.normalize().date() if max_dt_os is not None else date.today()
        )
        fator_os, dias_faltantes_os, dias_totais_os, dias_trabalhados_os = (
            CalculosOperacionais.fator_por_data_max(dmax_os)
        )

        dmax_cons = (
            max_dt_cons.normalize().date() if max_dt_cons is not None else date.today()
        )
        fator_cons, dias_faltantes_cons, dias_totais_cons, dias_trabalhados_cons = (
            CalculosOperacionais.fator_por_data_max(dmax_cons)
        )

        # Projeção automática (ritmo atual x fator dias úteis)
        os_projetadas = int(os_atual * fator_os)
        cons_projetados = int(cons_atual * fator_cons)

        # Metas e atingimentos
        meta_os = Metas.PRODUCAO_OS_BASE["meta_base"]
        meta_cons = Metas.CONSULTIVO_BASE["meta_base"]

        pct_meta_os = _to_float_safe(
            CalculosOperacionais.calcular_atingimento(os_projetadas, meta_os)
        )
        pct_meta_cons = _to_float_safe(
            CalculosOperacionais.calcular_atingimento(cons_projetados, meta_cons)
        )

        status_os, _, _ = get_status_base(os_projetadas, Metas.PRODUCAO_OS_BASE)
        status_cons, _, _ = get_status_base(cons_projetados, Metas.CONSULTIVO_BASE)

        # ==================== KPIs PRINCIPAIS ====================
         # ==================== KPIs PRINCIPAIS - LINHA 1 (Projeções) ====================
        c1, c2 = st.columns(2)

        render_kpi_seguro(
            c1,
            "O.S. PROJETADAS",
            f"{os_projetadas:,}".replace(",", "."),
            f"Atual: {os_atual:,} | {pct_meta_os:.1f}% da meta | {status_os}".replace(",", "."),
            "azul",
        )
        render_kpi_seguro(
            c2,
            "CONSULTIVOS PROJETADOS",
            f"{cons_projetados:,}".replace(",", "."),
            f"Atual: {cons_atual:,} | {pct_meta_cons:.1f}% da meta | {status_cons}".replace(",", "."),
            "laranja",
        )

        # ==================== KPIs PRINCIPAIS - LINHA 2 (Dias Úteis Detalhados) ====================
        st.write("")
        d1, d2, d3, d4 = st.columns(4)

        # % de progresso do mês (útil como referência visual)
        pct_dias_os_top = (
            (dias_trabalhados_os / (dias_trabalhados_os + dias_faltantes_os) * 100)
            if (dias_trabalhados_os + dias_faltantes_os) > 0
            else 0.0
        )
        pct_dias_cons_top = (
            (dias_trabalhados_cons / (dias_trabalhados_cons + dias_faltantes_cons) * 100)
            if (dias_trabalhados_cons + dias_faltantes_cons) > 0
            else 0.0
        )

        render_kpi_seguro(
            d1,
            "DIAS TRAB. (O.S.)",
            f"{dias_trabalhados_os}",
            f"{pct_dias_os_top:.1f}% do mês concluído",
            "verde",
        )
        render_kpi_seguro(
            d2,
            "DIAS FALTANTES (O.S.)",
            f"{dias_faltantes_os}",
            f"Dias úteis restantes no mês (seg–sáb)",
            "cinza",
        )
        render_kpi_seguro(
            d3,
            "DIAS TRAB. (CONSULTIVOS)",
            f"{dias_trabalhados_cons}",
            f"{pct_dias_cons_top:.1f}% do mês concluído",
            "verde",
        )
        render_kpi_seguro(
            d4,
            "DIAS FALTANTES (CONSULTIVOS)",
            f"{dias_faltantes_cons}",
            f"Dias úteis restantes no mês (seg–sáb)",
            "cinza",
        )

        # ==================== DASHBOARD DE PROJEÇÕES ====================
        st.write("")
        st.markdown(
            f"""
            <div style="background-color: #F8FAFC; padding: 1.25rem; border-radius: 8px;
                        border-left: 5px solid {Cores.PRIMARIA}; margin-bottom: 1.5rem;">
                <h4 style="margin: 0 0 0.5rem 0; color: {Cores.PRIMARIA};
                           font-size: 1.1rem; font-weight: 700;">
                    📊 Dashboard de Projeções Automáticas — {base_nome}
                </h4>
                <p style="margin: 0; font-size: 0.85rem; color: {Cores.TEXTO_3};">
                    Análise baseada em dias trabalhados e faltantes (Seg–Sáb, sem domingos/feriados).
                    Ritmo atual projetado até o fechamento do mês.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---------- Métricas de Ritmo ----------
        ritmo_atual_os = (
            os_atual / dias_trabalhados_os if dias_trabalhados_os > 0 else 0.0
        )
        ritmo_atual_cons = (
            cons_atual / dias_trabalhados_cons if dias_trabalhados_cons > 0 else 0.0
        )

        falta_os = max(0, meta_os - os_atual)
        falta_cons = max(0, meta_cons - cons_atual)

        ritmo_necessario_os = (
            falta_os / dias_faltantes_os if dias_faltantes_os > 0 else 0.0
        )
        ritmo_necessario_cons = (
            falta_cons / dias_faltantes_cons if dias_faltantes_cons > 0 else 0.0
        )

        gap_ritmo_os = ritmo_necessario_os - ritmo_atual_os
        gap_ritmo_cons = ritmo_necessario_cons - ritmo_atual_cons

        st.markdown("##### ⚡ Ritmo Diário (Atual vs. Necessário para Meta)")
        r1, r2, r3, r4 = st.columns(4)

        render_kpi_seguro(
            r1,
            "Ritmo Atual O.S./dia",
            f"{ritmo_atual_os:.1f}".replace(".", ","),
            f"Base: {os_atual:,} O.S. em {dias_trabalhados_os} dias".replace(",", "."),
            "azul",
        )
        cor_gap_os: CorTema = (
            "verde"
            if gap_ritmo_os <= 0
            else "vermelho" if gap_ritmo_os > ritmo_atual_os * 0.3 else "laranja"
        )
        render_kpi_seguro(
            r2,
            "Ritmo Necessário O.S./dia",
            f"{ritmo_necessario_os:.1f}".replace(".", ","),
            (
                f"Meta batida no ritmo atual! (+{abs(gap_ritmo_os):.1f}/dia sobra)"
                if gap_ritmo_os <= 0
                else f"Precisa acelerar +{gap_ritmo_os:.1f} O.S./dia"
            ).replace(".", ","),
            cor_gap_os,
        )
        render_kpi_seguro(
            r3,
            "Ritmo Atual Cons./dia",
            f"{ritmo_atual_cons:.1f}".replace(".", ","),
            f"Base: {cons_atual:,} cons. em {dias_trabalhados_cons} dias".replace(
                ",", "."
            ),
            "azul",
        )
        cor_gap_cons: CorTema = (
            "verde"
            if gap_ritmo_cons <= 0
            else "vermelho" if gap_ritmo_cons > ritmo_atual_cons * 0.3 else "laranja"
        )
        render_kpi_seguro(
            r4,
            "Ritmo Necessário Cons./dia",
            f"{ritmo_necessario_cons:.1f}".replace(".", ","),
            (
                f"Meta batida no ritmo atual! (+{abs(gap_ritmo_cons):.1f}/dia sobra)"
                if gap_ritmo_cons <= 0
                else f"Precisa acelerar +{gap_ritmo_cons:.1f} cons./dia"
            ).replace(".", ","),
            cor_gap_cons,
        )

        # ---------- Gráficos de Projeção ----------
        st.write("")
        st.markdown("##### 📈 Projeção de Fechamento vs. Meta")

        g1, g2 = st.columns(2)

        # Gráfico O.S.
        with g1:
            fig_os = go.Figure()
            fig_os.add_trace(
                go.Bar(
                    x=["Realizado", "Projetado", "Meta"],
                    y=[os_atual, os_projetadas, meta_os],
                    marker_color=[Cores.PRIMARIA, Cores.SECUNDARIA, Cores.SUCESSO],
                    text=[
                        f"{os_atual:,}".replace(",", "."),
                        f"{os_projetadas:,}".replace(",", "."),
                        f"{meta_os:,}".replace(",", "."),
                    ],
                    textposition="outside",
                    textfont=dict(size=14, color=Cores.TEXTO, family="IBM Plex Sans"),
                )
            )
            fig_os.add_hline(
                y=meta_os,
                line_dash="dash",
                line_color=Cores.ALERTA,
                annotation_text=f"Meta: {meta_os:,}".replace(",", "."),
                annotation_position="top right",
            )
            fig_os.update_layout(
                title=dict(
                    text=f"Produção O.S. | Atingimento projetado: {pct_meta_os:.1f}%",
                    font=dict(size=14, color=Cores.PRIMARIA),
                ),
                height=340,
                margin=dict(l=10, r=10, t=60, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                yaxis=dict(gridcolor="#E5E7EB"),
            )
            st.plotly_chart(fig_os, use_container_width=True)

        # Gráfico Consultivos
        with g2:
            fig_cons = go.Figure()
            fig_cons.add_trace(
                go.Bar(
                    x=["Realizado", "Projetado", "Meta"],
                    y=[cons_atual, cons_projetados, meta_cons],
                    marker_color=[Cores.PRIMARIA, Cores.SECUNDARIA, Cores.SUCESSO],
                    text=[
                        f"{cons_atual:,}".replace(",", "."),
                        f"{cons_projetados:,}".replace(",", "."),
                        f"{meta_cons:,}".replace(",", "."),
                    ],
                    textposition="outside",
                    textfont=dict(size=14, color=Cores.TEXTO, family="IBM Plex Sans"),
                )
            )
            fig_cons.add_hline(
                y=meta_cons,
                line_dash="dash",
                line_color=Cores.ALERTA,
                annotation_text=f"Meta: {meta_cons:,}".replace(",", "."),
                annotation_position="top right",
            )
            fig_cons.update_layout(
                title=dict(
                    text=f"Consultivos | Atingimento projetado: {pct_meta_cons:.1f}%",
                    font=dict(size=14, color=Cores.PRIMARIA),
                ),
                height=340,
                margin=dict(l=10, r=10, t=60, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                yaxis=dict(gridcolor="#E5E7EB"),
            )
            st.plotly_chart(fig_cons, use_container_width=True)

        # ---------- Gap e Volume Restante ----------
        st.write("")
        st.markdown("##### 🎯 Volume Restante para Atingir a Meta")

        gap_os_projetado = max(0, meta_os - os_projetadas)
        gap_cons_projetado = max(0, meta_cons - cons_projetados)
        superavit_os = max(0, os_projetadas - meta_os)
        superavit_cons = max(0, cons_projetados - meta_cons)

        v1, v2, v3, v4 = st.columns(4)

        render_kpi_seguro(
            v1,
            "Falta hoje (O.S.)",
            f"{falta_os:,}".replace(",", "."),
            f"Diferença atual até {meta_os:,} O.S.".replace(",", "."),
            "azul",
        )
        render_kpi_seguro(
            v2,
            "Falta projetada (O.S.)",
            f"{gap_os_projetado:,}".replace(",", "."),
            (
                f"Superávit de +{superavit_os:,} projetado!"
                if superavit_os > 0
                else f"Gap de {gap_os_projetado:,} ao fim do mês"
            ).replace(",", "."),
            "verde" if superavit_os > 0 else "vermelho",
        )
        render_kpi_seguro(
            v3,
            "Falta hoje (Cons.)",
            f"{falta_cons:,}".replace(",", "."),
            f"Diferença atual até {meta_cons:,} consultivos".replace(",", "."),
            "azul",
        )
        render_kpi_seguro(
            v4,
            "Falta projetada (Cons.)",
            f"{gap_cons_projetado:,}".replace(",", "."),
            (
                f"Superávit de +{superavit_cons:,} projetado!"
                if superavit_cons > 0
                else f"Gap de {gap_cons_projetado:,} ao fim do mês"
            ).replace(",", "."),
            "verde" if superavit_cons > 0 else "vermelho",
        )

        # ---------- Tabela consolidada ----------
        st.write("")
        st.markdown("##### 📋 Resumo Consolidado da Base")

        pct_dias_os = (
            (dias_trabalhados_os / dias_totais_os * 100) if dias_totais_os > 0 else 0
        )
        pct_dias_cons = (
            (dias_trabalhados_cons / dias_totais_cons * 100)
            if dias_totais_cons > 0
            else 0
        )

        df_resumo = pd.DataFrame(
            {
                "Indicador": [
                    "Realizado atual",
                    "Meta do mês",
                    "Projeção fim do mês",
                    "% da meta (projetado)",
                    "Falta para meta (hoje)",
                    "Falta para meta (projetado)",
                    "Dias trabalhados",
                    "Dias faltantes",
                    "Dias totais (mês)",
                    "% do mês percorrido",
                    "Ritmo atual (por dia útil)",
                    "Ritmo necessário (por dia útil)",
                    "Última data registrada",
                ],
                "Produção (O.S.)": [
                    f"{os_atual:,}".replace(",", "."),
                    f"{meta_os:,}".replace(",", "."),
                    f"{os_projetadas:,}".replace(",", "."),
                    f"{pct_meta_os:.1f}%",
                    f"{falta_os:,}".replace(",", "."),
                    f"{gap_os_projetado:,}".replace(",", "."),
                    f"{dias_trabalhados_os}",
                    f"{dias_faltantes_os}",
                    f"{dias_totais_os}",
                    f"{pct_dias_os:.1f}%",
                    f"{ritmo_atual_os:.1f}".replace(".", ","),
                    f"{ritmo_necessario_os:.1f}".replace(".", ","),
                    formatar_data_br(max_dt_os),
                ],
                "Consultivos": [
                    f"{cons_atual:,}".replace(",", "."),
                    f"{meta_cons:,}".replace(",", "."),
                    f"{cons_projetados:,}".replace(",", "."),
                    f"{pct_meta_cons:.1f}%",
                    f"{falta_cons:,}".replace(",", "."),
                    f"{gap_cons_projetado:,}".replace(",", "."),
                    f"{dias_trabalhados_cons}",
                    f"{dias_faltantes_cons}",
                    f"{dias_totais_cons}",
                    f"{pct_dias_cons:.1f}%",
                    f"{ritmo_atual_cons:.1f}".replace(".", ","),
                    f"{ritmo_necessario_cons:.1f}".replace(".", ","),
                    formatar_data_br(max_dt_cons),
                ],
            }
        )

        render_table_seguro(
            df_resumo,
            titulo=f"Consolidado completo — {base_nome}",
        )

        # ---------- Insight automático ----------
        st.write("")
        if os_projetadas >= meta_os and cons_projetados >= meta_cons:
            render_insight_seguro(
                f"🎉 **{base_nome}** está no ritmo certo! Ambas as metas serão atingidas mantendo o ritmo atual.",
                tipo="info",
            )
        elif os_projetadas < meta_os and cons_projetados < meta_cons:
            render_insight_seguro(
                f"⚠️ **{base_nome}** precisa acelerar em AMBAS as frentes. "
                f"Faltam **{gap_os_projetado:,} O.S.** e **{gap_cons_projetado:,} consultivos** ao fim do mês. "
                f"Aumentar ritmo em +{gap_ritmo_os:.1f} O.S./dia e +{gap_ritmo_cons:.1f} cons./dia.".replace(
                    ",", "."
                ),
                tipo="critico",
            )
        elif os_projetadas < meta_os:
            render_insight_seguro(
                f"⚠️ **{base_nome}** — Produção está abaixo do necessário. "
                f"Falta projetada: **{gap_os_projetado:,} O.S.** (acelerar +{gap_ritmo_os:.1f}/dia). "
                f"Consultivos OK.".replace(",", "."),
                tipo="alerta",
            )
        else:
            render_insight_seguro(
                f"⚠️ **{base_nome}** — Consultivos abaixo do necessário. "
                f"Falta projetada: **{gap_cons_projetado:,} cons.** (acelerar +{gap_ritmo_cons:.1f}/dia). "
                f"Produção OK.".replace(",", "."),
                tipo="alerta",
            )

        st.divider()
        st.caption(
            f"📅 Última produção em {base_nome}: {formatar_data_br(max_dt_os)} | "
            f"Último consultivo: {formatar_data_br(max_dt_cons)} | "
            f"Dias úteis: seg–sáb (sem domingos/feriados) · Datas em DD/MM/AAAA"
        )

with tab_bases:
    render_section_header_seguro(
        "Visão por Base",
        "Comparativo de Produção e Consultivos por unidade",
        icone="🗂️",
    )
    if df_prod_f.empty and df_cons_f.empty:
        render_empty_state_seguro(
            "Sem dados", "Ajuste filtros para visualizar as bases."
        )
    else:
        k1, k2, k3, k4 = st.columns(4)
        render_kpi_seguro(
            k1,
            "Bases com dados",
            f"{len(df_proj_base):,}".replace(",", "."),
            "Bases únicas no período",
            "azul",
        )
        render_kpi_seguro(
            k2,
            "O.S. (atual)",
            f"{int(df_proj_base['O.S.'].sum()):,}".replace(",", "."),
            "Soma produção filtrada",
            "verde",
        )
        render_kpi_seguro(
            k3,
            "Consultivos (atual)",
            f"{int(df_proj_base['Consultivos'].sum()):,}".replace(",", "."),
            "Soma consultivo filtrado",
            "laranja",
        )
        bases_prio_count = int(
            df_proj_base["Base"].astype(str).str.upper().isin(BASES_PRIORITARIAS).sum()
        )
        render_kpi_seguro(
            k4,
            "Bases prioritárias",
            f"{bases_prio_count:,}".replace(",", "."),
            "ABCDM/LESTE/GUARULHOS",
            "roxo",
        )

        st.divider()
        st.markdown("#### Bases prioritárias (Visão por Projeto Oficial)")
        cards = st.columns(len(BASES_PRIORITARIAS))
        for col, base_nome in zip(cards, BASES_PRIORITARIAS):
            os_atual, _ = _obter_contagem_projeto_base(df_prod_f, base_nome)
            cons_atual, _ = _obter_contagem_projeto_base(df_cons_f, base_nome)

            ating_os_v = _to_float_safe(
                CalculosOperacionais.calcular_atingimento(
                    float(os_atual), float(Metas.PRODUCAO_OS_BASE["meta_base"])
                )
            )
            ating_cons_v = _to_float_safe(
                CalculosOperacionais.calcular_atingimento(
                    float(cons_atual), float(Metas.CONSULTIVO_BASE["meta_base"])
                )
            )
            status_os, _, _ = get_status_base(os_atual, Metas.PRODUCAO_OS_BASE)
            status_cons, _, _ = get_status_base(cons_atual, Metas.CONSULTIVO_BASE)

            with col:
                st.markdown(
                    f"""
                <div class="base-card">
                    <div class="base-title">{escape(base_nome)}</div>
                    <div style="margin-bottom:.45rem;">
                        <div><strong>Produção:</strong> {os_atual:,} O.S. ({ating_os_v:.1f}%)</div>
                        <div>{render_status_pill_seguro(status_os, status_os)}</div>
                    </div>
                    <div>
                        <div><strong>Consultivos:</strong> {cons_atual:,} ({ating_cons_v:.1f}%)</div>
                        <div>{render_status_pill_seguro(status_cons, status_cons)}</div>
                    </div>
                </div>
                """.replace(",", "."),
                    unsafe_allow_html=True,
                )

        st.divider()


# Abas individuais
render_aba_projecao_base(tab_abcdm, "NET-ABCDM", df_proj_base)
render_aba_projecao_base(tab_leste, "NET-LESTE", df_proj_base)
render_aba_projecao_base(tab_guarulhos, "NET-GUARULHOS", df_proj_base)
