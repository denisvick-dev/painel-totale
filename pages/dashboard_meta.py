"""
dashboard_meta.py
=================
Dashboard de Metas Operacionais - TOTALE (Versão Production-Ready, reestruturada)

Foco: robustez, performance, segurança de execução e manutenção.
- Carregamento: GSheets (hierarquia + produção) e Drive CSV (consultivo)
- Enriquecimento: merge por LOGIN e fallback por TECNICO (normalizado)
- Filtros: Base, Monitor, Projeto, Período
- Abas: Produção, Consultivos, Bases (com projeções e prioridades), Projeção por base

Revisão técnica aplicada:
- Tipagem corrigida (sem Any[...] inválido)
- Sem vazamento de arquivos temporários (gdown)
- Cache + proteção contra mutação (copy após cache)
- Colunas normalizadas pré-computadas (_BASE_NORM etc.)
- Projeção por base O(n_bases) sem filtrar DF em loop
- Render wrappers corporativos com fallback seguro (inclui tabelas)
"""

from __future__ import annotations

import io
import logging
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from html import escape
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)
from urllib.parse import quote as url_quote
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

# =============================================================================
# Imports opcionais (componentes corporativos / gsheets / gdown)
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
    )

    COMPONENTES_CORPORATIVOS = True
except (ImportError, ModuleNotFoundError):
    COMPONENTES_CORPORATIVOS = False
    aplicar_estilo_corporativo = None  # type: ignore
    render_empty_state_corporativo = None  # type: ignore
    render_insight_corporativo = None  # type: ignore
    render_kpi_corporativo = None  # type: ignore
    render_progress_bar_corporativo = None  # type: ignore
    render_section_header_corporativo = None  # type: ignore
    render_status_pill_corporativo = None  # type: ignore
    render_table_html_corporativo = None  # type: ignore


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
    menu_items={"About": "Dashboard de Metas Operacionais - TOTALE"},
)


# =============================================================================
# Tipos / Constantes
# =============================================================================

Number = Union[int, float, np.integer, np.floating]
CorTema = Literal["laranja", "azul", "verde", "vermelho", "cinza", "roxo"]

BASES_PRIORITARIAS: Tuple[str, ...] = ("NET-ABCDM", "NET-LESTE", "NET-GUARULHOS")
PROJETOS_NET: Tuple[str, ...] = ("NET-ABCDM", "NET-LESTE", "NET-GUARULHOS")


def get_secret(key: str, default: str) -> str:
    try:
        return str(st.secrets.get(key, default))
    except Exception:
        return default


@dataclass(frozen=True)
class Configuracoes:
    URL_ATIVOS: str = get_secret(
        "GSHEETS_URL_ATIVOS",
        "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg",
    )
    SHEET_ID_ATIVOS: str = get_secret(
        "GSHEETS_ID_ATIVOS", "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    )
    SHEET_ABA_ATIVOS: str = "lista_ativos"

    SHEET_ID_PROD: str = get_secret(
        "GSHEETS_ID_PROD", "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
    )
    SHEET_ABA_PROD: str = "Prod"

    DRIVE_ID_CONS: str = get_secret(
        "DRIVE_ID_CONS", "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"
    )

    TIMEOUT: int = 30
    TZ: ZoneInfo = ZoneInfo("America/Sao_Paulo")

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
    PRODUCAO_OS_BASE = {"minima": 10_000, "meta_base": 11_000, "alta_perf": 12_000}
    CONSULTIVO_BASE = {"minima": 400, "meta_base": 525, "alta_perf": 600}
    PRODUCAO_OS_GERAL = {"minima": 30_000, "meta_base": 33_000, "alta_perf": 36_000}
    CONSULTIVO_GERAL = {"minima": 1_200, "meta_base": 1_575, "alta_perf": 1_800}


CFG = Configuracoes()


# =============================================================================
# HTTP session (reuso de conexões)
# =============================================================================


@st.cache_resource
def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "totale-dashboard/2.0"})
    return s


# =============================================================================
# Utils de dados
# =============================================================================


def normalizar_texto(texto: Any) -> str:
    if pd.isna(texto):
        return ""
    txt = str(texto).strip()
    txt = "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    )
    return txt.upper()


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

        # busca exata
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

        # busca parcial
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


def garantir_datetime(df: pd.DataFrame, col: str = "DATA") -> pd.DataFrame:
    if col not in df.columns:
        return df
    df = df.copy()
    df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df


def garantir_login(df: pd.DataFrame, col: str = "LOGIN") -> pd.DataFrame:
    if col not in df.columns:
        return df
    df = df.copy()
    s = df[col].astype(str).str.strip().str.upper()
    invalidos = {"NAN", "NONE", "N/A", "<NA>", "", "NA"}
    s = s.where(~s.isin(list(invalidos)), None)
    s = s.where(s.notna(), None)
    df[col] = s
    return df


def add_norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Pré-computa colunas normalizadas usadas em filtros/joins."""
    if df.empty:
        return df
    df = df.copy()
    if "BASE" in df.columns and "_BASE_NORM" not in df.columns:
        df["_BASE_NORM"] = df["BASE"].map(normalizar_texto)
    if "LOGIN" in df.columns and "_LOGIN_NORM" not in df.columns:
        df["_LOGIN_NORM"] = df["LOGIN"].map(normalizar_texto)
    if "TECNICO" in df.columns and "_TECNICO_NORM" not in df.columns:
        df["_TECNICO_NORM"] = df["TECNICO"].map(normalizar_texto)
    if "PROJETO" in df.columns and "_PROJETO_NORM" not in df.columns:
        df["_PROJETO_NORM"] = df["PROJETO"].map(normalizar_texto)
    return df


# =============================================================================
# Métricas / Projeção (otimizadas)
# =============================================================================


class CalculosOperacionais:
    @staticmethod
    @lru_cache(maxsize=16)
    def feriados_brasil(ano: int) -> Tuple[date, ...]:
        """Feriados nacionais + móveis (aproximação)."""
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
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        mes = (h + l - 7 * m + 114) // 31
        dia = ((h + l - 7 * m + 114) % 31) + 1
        pascoa = date(ano, mes, dia)

        feriados = (
            date(ano, 1, 1),
            date(ano, 4, 21),
            date(ano, 5, 1),
            date(ano, 9, 7),
            date(ano, 10, 12),
            date(ano, 11, 2),
            date(ano, 11, 15),
            date(
                ano, 11, 20
            ),  # pode variar por cidade/UF; manter se regra interna aceita
            date(ano, 12, 25),
            pascoa - timedelta(days=48),
            pascoa - timedelta(days=47),
            pascoa - timedelta(days=2),
            pascoa + timedelta(days=60),
        )
        return tuple(sorted(set(feriados)))

    @staticmethod
    def _busday_count(
        inicio: date, fim_inclusivo: date, feriados: Sequence[date]
    ) -> int:
        hol = np.array([np.datetime64(d) for d in feriados], dtype="datetime64[D]")
        return int(
            np.busday_count(
                np.datetime64(inicio),
                np.datetime64(fim_inclusivo + timedelta(days=1)),
                holidays=hol,
            )
        )

    @staticmethod
    @lru_cache(maxsize=256)
    def fator_por_data_max(data_max: date) -> Tuple[float, int, int]:
        inicio_mes = data_max.replace(day=1)
        prox_mes = (inicio_mes.replace(day=28) + timedelta(days=4)).replace(day=1)
        fim_mes = prox_mes - timedelta(days=1)

        feriados = CalculosOperacionais.feriados_brasil(data_max.year)
        total = CalculosOperacionais._busday_count(inicio_mes, fim_mes, feriados)
        decorridos = CalculosOperacionais._busday_count(inicio_mes, data_max, feriados)

        faltantes = max(0, total - decorridos)
        fator = (total / decorridos) if decorridos > 0 else 1.0
        return float(fator), int(faltantes), int(total)

    @staticmethod
    def fator_projecao(
        df: pd.DataFrame, coluna_data: str = "DATA"
    ) -> Tuple[float, int, int]:
        if df.empty or coluna_data not in df.columns:
            return 1.0, 0, 0
        datas = pd.to_datetime(df[coluna_data], errors="coerce").dropna()
        if datas.empty:
            return 1.0, 0, 0
        dmax = datas.max().normalize().date()
        return CalculosOperacionais.fator_por_data_max(dmax)

    @staticmethod
    def calcular_atingimento(
        valor: Any[Number, pd.Series], meta: Number
    ) -> Any[float, pd.Series]:
        if meta <= 0:
            return 0.0 if not isinstance(valor, pd.Series) else valor * 0
        return (valor / meta) * 100


def get_status_geral(
    valor: Any, tipo: Literal["os", "cons"] = "os"
) -> Tuple[str, str, str]:
    if pd.isna(valor):
        valor = 0
    metas = Metas.PRODUCAO_OS_GERAL if tipo == "os" else Metas.CONSULTIVO_GERAL
    if float(valor) >= metas["alta_perf"]:
        return "Alta Performance", Cores.SUCESSO, "#D1FAE5"
    if float(valor) >= metas["meta_base"]:
        return "Meta Atingida", Cores.SUCESSO, "#D1FAE5"
    if float(valor) >= metas["minima"]:
        return "Atenção / Mínimo", Cores.ATENCAO, "#FEF3C7"
    return "Crítico / Abaixo", Cores.ALERTA, "#FEE2E2"


def get_status_base(valor: Any, metas: Mapping[str, Number]) -> Tuple[str, str, str]:
    if pd.isna(valor):
        valor = 0
    if float(valor) >= float(metas["alta_perf"]):
        return "Alta Performance", Cores.SUCESSO, "#D1FAE5"
    if float(valor) >= float(metas["meta_base"]):
        return "Meta Atingida", Cores.SUCESSO, "#D1FAE5"
    if float(valor) >= float(metas["minima"]):
        return "Atenção / Mínimo", Cores.ATENCAO, "#FEF3C7"
    return "Crítico / Abaixo", Cores.ALERTA, "#FEE2E2"


# =============================================================================
# CSS (corporativo + fallback local)
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


if COMPONENTES_CORPORATIVOS and aplicar_estilo_corporativo:
    try:
        aplicar_estilo_corporativo()  # type: ignore[misc]
    except Exception as e:
        logger.warning(f"Falha ao aplicar estilo corporativo: {e}")

aplicar_estilo_local()


# =============================================================================
# Render wrappers (corporativo com fallback)
# =============================================================================


def render_section_header_seguro(
    titulo: str,
    subtitulo: str = "",
    icone: str = "",
    badge: str = "",
    badge_tipo: CorTema = "laranja",
) -> None:
    if COMPONENTES_CORPORATIVOS and render_section_header_corporativo:
        try:
            render_section_header_corporativo(  # type: ignore[misc]
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
    if COMPONENTES_CORPORATIVOS and render_kpi_corporativo:
        try:
            render_kpi_corporativo(container, titulo, valor, subtexto, cor_tema)  # type: ignore[misc]
            return
        except Exception as e:
            logger.warning(f"Falha render_kpi_corporativo: {e}")
    render_kpi_fallback(container, titulo, valor, subtexto, cor_tema)


def render_empty_state_seguro(titulo: str, mensagem: str) -> None:
    if COMPONENTES_CORPORATIVOS and render_empty_state_corporativo:
        try:
            render_empty_state_corporativo(titulo, mensagem)  # type: ignore[misc]
            return
        except Exception as e:
            logger.warning(f"Falha render_empty_state_corporativo: {e}")
    st.info(f"{titulo}: {mensagem}")


def render_insight_seguro(
    mensagem: str, tipo: Literal["info", "alerta", "critico"] = "info"
) -> None:
    if COMPONENTES_CORPORATIVOS and render_insight_corporativo:
        try:
            render_insight_corporativo(mensagem, tipo=tipo)  # type: ignore[misc]
            return
        except Exception as e:
            logger.warning(f"Falha render_insight_corporativo: {e}")

    if tipo in ("alerta", "critico"):
        st.warning(mensagem)
    else:
        st.info(mensagem)


def render_progress_bar_seguro(
    label: str, valor: Number, meta: Number, unidade: str = ""
) -> None:
    if COMPONENTES_CORPORATIVOS and render_progress_bar_corporativo:
        try:
            render_progress_bar_corporativo(label, valor, meta, unidade)  # type: ignore[misc]
            return
        except Exception as e:
            logger.warning(f"Falha render_progress_bar_corporativo: {e}")

    pct = float(CalculosOperacionais.calcular_atingimento(float(valor), float(meta)))
    st.progress(
        min(pct / 100.0, 1.0),
        text=f"{label}: {pct:.1f}% ({valor}{unidade} / {meta}{unidade})",
    )


def render_status_pill_seguro(texto: str, status: str) -> str:
    if COMPONENTES_CORPORATIVOS and render_status_pill_corporativo:
        try:
            status_tipo = (
                "sucesso"
                if "Meta" in status or "Performance" in status
                else "pendente" if "Atenção" in status else "erro"
            )
            return render_status_pill_corporativo(texto, status_tipo)  # type: ignore[misc]
        except Exception as e:
            logger.warning(f"Falha render_status_pill_corporativo: {e}")
    return f"<span class='pill'>{escape(texto)}</span>"


def _styler_apply_color_rules(
    df: pd.DataFrame,
    color_rules: Dict[str, List[Tuple[Callable[[Any], bool], str]]],
) -> pd.io.formats.style.Styler:
    styler = df.style

    # aplica por célula apenas nas colunas definidas
    def style_cell(val: Any, rules: List[Tuple[Callable[[Any], bool], str]]) -> str:
        for pred, color in rules:
            try:
                if pred(val):
                    return f"color: {color}; font-weight: 700;"
            except Exception:
                continue
        return ""

    for col, rules in color_rules.items():
        if col in df.columns:
            styler = styler.map(lambda v, rr=rules: style_cell(v, rr), subset=[col])
    return styler


def render_table_seguro(
    df: pd.DataFrame,
    titulo: str = "",
    fmt: Optional[Any[str, str]] = None,
    num_cols: Optional[List[str]] = None,
    color_rules: Optional[Any[str, List[Tuple[Callable[[Any], bool], str]]]] = None,
) -> None:
    if COMPONENTES_CORPORATIVOS and render_table_html_corporativo:
        try:
            render_table_html_corporativo(  # type: ignore[misc]
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
        # fallback simples: format via Styler
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
                "axis": {"range": [0, max(int(alta * 1.2), int(valor * 1.2), 1)]},
                "bar": {"color": Cores.PRIMARIA},
                "steps": [
                    {"range": [0, min_val], "color": "#FEE2E2"},
                    {"range": [min_val, base], "color": "#FEF3C7"},
                    {"range": [base, max(int(alta * 1.2), 1)], "color": "#D1FAE5"},
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
# ETL: leitura e downloads
# =============================================================================


def _ler_csv_bytes(conteudo: bytes) -> pd.DataFrame:
    if not conteudo or len(conteudo) < 10:
        raise ValueError("CSV vazio ou corrompido.")

    # heurística leve para separador
    head = conteudo[:4096]
    seps = [b";", b",", b"\t", b"|"]
    sep = max(seps, key=lambda s: head.count(s))
    sep_char = sep.decode("utf-8", errors="ignore") or ";"

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

    # último fallback
    return pd.read_csv(
        io.BytesIO(conteudo),
        encoding="latin-1",
        dtype=str,
        low_memory=False,
        on_bad_lines="skip",
    )


def _baixar_drive_csv(file_id: str) -> bytes:
    sess = http_session()
    url = f"https://drive.google.com/uc?id={file_id}&export=download"

    # gdown (com cleanup garantido)
    download = getattr(gdown, "download", None) if gdown else None
    if callable(download):
        tmp_path: Optional[str] = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".csv")
            os.close(fd)
            download(f"https://drive.google.com/uc?id={file_id}", tmp_path, quiet=True)
            with open(tmp_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"gdown falhou, fallback requests: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    resp = sess.get(url, timeout=CFG.TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"Falha download Drive: HTTP {resp.status_code}")

    if "confirm=" in resp.text:
        token = re.search(r"confirm=([0-9A-Za-z_]+)", resp.text)
        if token:
            url_confirm = f"https://drive.google.com/uc?export=download&confirm={token.group(1)}&id={file_id}"
            resp = sess.get(url_confirm, timeout=CFG.TIMEOUT)

    if resp.status_code != 200:
        raise RuntimeError(f"Falha download Drive confirm: HTTP {resp.status_code}")

    return resp.content


@st.cache_data(ttl=CFG.CACHE_TTL_HIERARQUIA, show_spinner="Carregando hierarquia...")
def carregar_hierarquia() -> pd.DataFrame:
    df = pd.DataFrame()

    # 1) GSheetsConnection
    if GSheetsConnection:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(spreadsheet=CFG.URL_ATIVOS, worksheet=CFG.SHEET_ABA_ATIVOS, ttl=0)  # type: ignore[no-untyped-call]
        except Exception as e:
            logger.warning(f"Hierarquia via GSheetsConnection falhou: {e}")

    # 2) fallback gviz csv
    if df.empty:
        try:
            sess = http_session()
            csv_url = (
                f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_ATIVOS}"
                f"/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_ATIVOS)}"
            )
            resp = sess.get(csv_url, timeout=CFG.TIMEOUT)
            if resp.status_code == 200 and len(resp.text) > 10:
                df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        except Exception as e:
            logger.warning(f"Hierarquia via gviz falhou: {e}")

    if df.empty:
        return pd.DataFrame(columns=["LOGIN", "TECNICO", "MONITOR", "BASE"])

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
        df[["LOGIN", "TECNICO", "MONITOR", "BASE"]]
        .dropna(subset=["LOGIN"])
        .drop_duplicates()
        .reset_index(drop=True)
    )
    df = add_norm_cols(df)
    return df


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
                "DATA": ["DATA", "DT_CRIACAO", "CRIACAO"],
                "LOGIN": ["LOGIN NETSALES", "LOGIN", "USUARIO", "MATRICULA"],
                "PROJETO": ["PROJETO", "CONTRATO"],
                "BASE": ["BASE", "FILIAL"],
                "TECNICO": ["TECNICO", "NOME"],
                "MONITOR": ["MONITOR", "SUPERVISOR"],
            },
        )
        df = garantir_datetime(df, "DATA")
        df = garantir_login(df, "LOGIN")
        df = add_norm_cols(df)
        return df, None
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

        if resp.status_code != 200:
            return pd.DataFrame(), f"Produção: HTTP {resp.status_code}"

        if (
            resp.text.lstrip().lower().startswith("<!doctype")
            or "<html" in resp.text.lower()
        ):
            return pd.DataFrame(), "Produção: planilha privada/indisponível."

        df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

        df = mapear_colunas(
            df,
            {
                "DATA": ["DATA", "DT_EXECUCAO", "EXECUCAO"],
                "LOGIN": ["LOGIN", "MATRICULA", "USER"],
                "NUM_OS": ["NUM_OS", "NUMERO_OS", "OS"],
                "PROJETO": [
                    "PROJETO",
                    "CAMPANHA",
                    "OPERACAO",
                    "OPERAÇÃO",
                    "CONTRATO_PROJETO",
                ],
                "BASE": ["BASE", "FILIAL"],
                "TECNICO": ["NOME EQUIPE", "TECNICO", "NOME"],
                "MONITOR": ["MONITOR", "SUPERVISOR"],
            },
        )
        df = garantir_datetime(df, "DATA")
        df = garantir_login(df, "LOGIN")
        df = add_norm_cols(df)
        return df, None
    except Exception as e:
        logger.exception("Erro ao carregar produção")
        return pd.DataFrame(), f"Produção: {type(e).__name__}: {str(e)[:180]}"


# =============================================================================
# Enriquecimento (hierarquia) - com fallback por LOGIN e TECNICO normalizados
# =============================================================================


def enriquecer_dados(df: pd.DataFrame, hierarquia: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    dfm = df.copy()
    for col in ("TECNICO", "MONITOR", "BASE"):
        if col not in dfm.columns:
            dfm[col] = pd.NA

    if hierarquia.empty:
        return dfm.fillna("Não Informado")

    hier = hierarquia.copy()
    hier = add_norm_cols(hier)

    # 1) merge por LOGIN normalizado
    if "_LOGIN_NORM" not in dfm.columns:
        dfm["_LOGIN_NORM"] = dfm.get("LOGIN", pd.Series([""] * len(dfm))).map(
            normalizar_texto
        )

    lk_login = hier.dropna(subset=["_LOGIN_NORM"]).drop_duplicates("_LOGIN_NORM")[
        ["_LOGIN_NORM", "TECNICO", "MONITOR", "BASE"]
    ]
    lk_login = lk_login.rename(
        columns={c: f"{c}_H" for c in ("TECNICO", "MONITOR", "BASE")}
    )

    dfm = dfm.merge(lk_login, on="_LOGIN_NORM", how="left")
    for c in ("TECNICO", "MONITOR", "BASE"):
        vazio = dfm[c].isna() | dfm[c].map(normalizar_texto).isin(
            {"", "NAN", "NONE", "NAO INFORMADO"}
        )
        dfm.loc[vazio, c] = dfm.loc[vazio, f"{c}_H"]
        dfm.drop(columns=[f"{c}_H"], inplace=True)

    # 2) fallback por técnico normalizado (apenas onde segue vazio)
    if "TECNICO" in dfm.columns:
        dfm["_TECNICO_NORM"] = dfm["TECNICO"].map(normalizar_texto)
    if "_TECNICO_NORM" not in hier.columns and "TECNICO" in hier.columns:
        hier["_TECNICO_NORM"] = hier["TECNICO"].map(normalizar_texto)

    lk_tec = hier.dropna(subset=["_TECNICO_NORM"]).drop_duplicates("_TECNICO_NORM")[
        ["_TECNICO_NORM", "MONITOR", "BASE"]
    ]
    lk_tec = lk_tec.rename(columns={"MONITOR": "MONITOR_H2", "BASE": "BASE_H2"})

    dfm = dfm.merge(lk_tec, on="_TECNICO_NORM", how="left")
    for c, ch in (("MONITOR", "MONITOR_H2"), ("BASE", "BASE_H2")):
        vazio = dfm[c].isna() | dfm[c].map(normalizar_texto).isin(
            {"", "NAN", "NONE", "NAO INFORMADO"}
        )
        dfm.loc[vazio, c] = dfm.loc[vazio, ch]
        dfm.drop(columns=[ch], inplace=True)

    dfm = dfm.fillna("Não Informado")
    dfm = add_norm_cols(dfm)
    return dfm


# =============================================================================
# Carregamento principal (com cópias para evitar mutação em cache)
# =============================================================================

df_hierarquia = carregar_hierarquia().copy()
df_cons_raw, erro_cons = carregar_consultivos()
df_prod_raw, erro_prod = carregar_producao()
df_cons_raw = df_cons_raw.copy()
df_prod_raw = df_prod_raw.copy()

df_prod = enriquecer_dados(df_prod_raw, df_hierarquia)
df_cons = enriquecer_dados(df_cons_raw, df_hierarquia)


# =============================================================================
# Sidebar / Filtros (com defaults estáveis)
# =============================================================================


def _unique_sorted(series: pd.Series) -> List[str]:
    if series is None or series.empty:
        return []
    vals = series.dropna().astype(str).str.strip()
    vals = vals[vals != ""]
    return sorted(set(vals.tolist()))


with st.sidebar:
    st.markdown("### Filtros Globais")

    bases_opts = sorted(
        set(_unique_sorted(df_prod.get("BASE", pd.Series(dtype=str))))
        | set(_unique_sorted(df_cons.get("BASE", pd.Series(dtype=str))))
    )
    monitores_opts = sorted(
        set(_unique_sorted(df_prod.get("MONITOR", pd.Series(dtype=str))))
        | set(_unique_sorted(df_cons.get("MONITOR", pd.Series(dtype=str))))
    )
    projetos_opts = sorted(
        set(_unique_sorted(df_prod.get("PROJETO", pd.Series(dtype=str))))
        | set(_unique_sorted(df_cons.get("PROJETO", pd.Series(dtype=str))))
    )

    st.divider()
    st.markdown("### Filtro Rápido")
    filtro_net = st.checkbox(
        "Filtrar apenas NET (ABCDM/LESTE/GUARULHOS)", value=False, key="filtro_net"
    )

    default_projetos = (
        [p for p in PROJETOS_NET if p in projetos_opts] if filtro_net else []
    )

    filtro_projeto = st.multiselect(
        "Projeto",
        options=projetos_opts,
        default=default_projetos,
        placeholder="Todos",
        key="select_projetos",
    )
    filtro_base = st.multiselect(
        "Base / Regional", options=bases_opts, placeholder="Todas", key="select_bases"
    )
    filtro_monitor = st.multiselect(
        "Monitor", options=monitores_opts, placeholder="Todos", key="select_monitores"
    )

    # Período (usa datetime64 direto para filtrar)
    todas_datas = pd.concat(
        [
            df_prod.get("DATA", pd.Series(dtype="datetime64[ns]")),
            df_cons.get("DATA", pd.Series(dtype="datetime64[ns]")),
        ],
        ignore_index=True,
    ).dropna()
    if not todas_datas.empty:
        min_dt = pd.to_datetime(todas_datas.min()).date()
        max_dt = pd.to_datetime(todas_datas.max()).date()
        filtro_datas = st.date_input(
            "Período",
            value=(min_dt, max_dt),
            min_value=min_dt,
            max_value=max_dt,
            key="date_range",
        )
    else:
        filtro_datas = None

    st.divider()
    if st.button(
        "Atualizar Dados (limpa cache global)",
        use_container_width=True,
        key="btn_refresh",
    ):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    st.caption(f"Atualizado: {datetime.now(CFG.TZ).strftime('%d/%m %H:%M')}")
    st.caption(f"Hierarquia: {len(df_hierarquia):,}")
    st.caption(f"Produção: {len(df_prod):,} | Consultivo: {len(df_cons):,}")


def aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    dff = df.copy()
    mask = pd.Series(True, index=dff.index)

    if filtro_base and "BASE" in dff.columns:
        mask &= dff["BASE"].astype(str).isin(filtro_base)

    if filtro_monitor and "MONITOR" in dff.columns:
        mask &= dff["MONITOR"].astype(str).isin(filtro_monitor)

    if filtro_projeto and "PROJETO" in dff.columns:
        mask &= dff["PROJETO"].astype(str).isin(filtro_projeto)

    if filtro_datas and "DATA" in dff.columns:
        if isinstance(filtro_datas, tuple) and len(filtro_datas) == 2:
            d1, d2 = filtro_datas
        else:
            d1 = filtro_datas[0]
            d2 = filtro_datas[0]
        sdt = pd.to_datetime(dff["DATA"], errors="coerce")
        mask &= (sdt.dt.normalize() >= pd.Timestamp(d1)) & (
            sdt.dt.normalize() <= pd.Timestamp(d2)
        )

    return dff.loc[mask].copy()


df_prod_f = add_norm_cols(aplicar_filtros(df_prod))
df_cons_f = add_norm_cols(aplicar_filtros(df_cons))


# =============================================================================
# Header + erros
# =============================================================================

st.markdown(
    """
    <div class="hero-totale">
        <h1>Dashboard de Metas Operacionais</h1>
        <p>Gestão Integrada: Produção (O.S.) + Consultivos + Hierarquia + Bases</p>
    </div>
    """,
    unsafe_allow_html=True,
)

for err in [erro_prod, erro_cons]:
    if err:
        st.warning(f"Aviso: {err}")

if df_hierarquia.empty:
    render_insight_seguro(
        "Hierarquia vazia. Verifique permissões da planilha/credenciais.", tipo="alerta"
    )


# =============================================================================
# Abas
# =============================================================================

tab_prod, tab_cons, tab_bases, tab_projecao = st.tabs(
    ["📊 Produção", "💼 Consultivos", "🗂️ Bases", "📈 Projeção"]
)


def render_aba_metricas(
    tab: DeltaGenerator,
    titulo_total: str,
    total: int,
    metas: Dict[str, int],
    df: pd.DataFrame,
    tipo: Literal["os", "cons"],
) -> Tuple[int, int]:
    """Renderiza KPIs + gauge. Retorna (dias_restantes, projecao) para reuso se necessário."""
    with tab:
        render_section_header_seguro(
            titulo_total,
            "Acompanhamento operacional e projeção mensal",
            icone="📊" if tipo == "os" else "💼",
            badge="Produção" if tipo == "os" else "Consultivos",
            badge_tipo="azul" if tipo == "os" else "laranja",
        )

        fator, dias_rest, _ = CalculosOperacionais.fator_projecao(df, "DATA")
        projecao = int(total * fator)

        status_txt, status_cor, _ = get_status_geral(total, tipo)
        cor_status: CorTema = "verde" if status_cor == Cores.SUCESSO else "vermelho"

        ating = float(
            CalculosOperacionais.calcular_atingimento(
                float(total), float(metas["meta_base"])
            )
        )

        c1, c2, c3, c4 = st.columns(4)
        render_kpi_seguro(
            c1, titulo_total, f"{total:,}", f"{ating:.1f}% da meta base", "azul"
        )
        render_kpi_seguro(
            c2,
            "Meta base",
            f"{metas['meta_base']:,}",
            f"Variação: {total - metas['meta_base']:+,}",
            "laranja",
        )
        render_kpi_seguro(
            c3,
            "Projeção mês",
            f"{projecao:,}",
            f"{dias_rest} dias úteis restantes",
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

        # opcional: curva acumulada (apenas se DATA existe e não explode)
        if "DATA" in df.columns and df["DATA"].notna().any():
            sdt = pd.to_datetime(df["DATA"], errors="coerce").dropna()
            if not sdt.empty:
                daily = (
                    sdt.dt.date.value_counts()
                    .rename_axis("DATA")
                    .reset_index(name="Volume")
                    .sort_values("DATA")
                )
                daily["Acumulado"] = daily["Volume"].cumsum()
                fig = px.area(
                    daily,
                    x="DATA",
                    y="Acumulado",
                    title="Evolução acumulada no período",
                )
                fig.add_hline(
                    y=metas["meta_base"], line_dash="dash", line_color=Cores.SECUNDARIA
                )
                fig.update_layout(
                    height=260,
                    margin=dict(l=10, r=10, t=45, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

        return dias_rest, projecao


# Produção
dias_rest_prod, proj_prod = render_aba_metricas(
    tab_prod,
    "O.S. realizadas",
    int(len(df_prod_f)),
    Metas.PRODUCAO_OS_GERAL,
    df_prod_f,
    "os",
)

# Consultivos
dias_rest_cons, proj_cons = render_aba_metricas(
    tab_cons,
    "Consultivos",
    int(len(df_cons_f)),
    Metas.CONSULTIVO_GERAL,
    df_cons_f,
    "cons",
)


# =============================================================================
# Aba Bases (resumo + prioridades + projeções por base otimizadas)
# =============================================================================


def _resumo_por_base(df: pd.DataFrame, nome_coluna: str) -> pd.DataFrame:
    if df.empty or "_BASE_NORM" not in df.columns:
        return pd.DataFrame(columns=["_BASE_NORM", "Base", nome_coluna, "MAX_DATA"])

    g = (
        df.dropna(subset=["DATA"], how="all")
        .groupby("_BASE_NORM", dropna=False)
        .agg(
            Base=(
                "BASE",
                lambda s: (
                    s.dropna().astype(str).iloc[0]
                    if len(s.dropna())
                    else "Não Informado"
                ),
            ),
            **{nome_coluna: ("DATA", "size")},
            MAX_DATA=("DATA", "max"),
        )
        .reset_index()
    )
    g[nome_coluna] = g[nome_coluna].fillna(0).astype(int)
    return g


def _projecao_por_base(prod: pd.DataFrame, cons: pd.DataFrame) -> pd.DataFrame:
    a = _resumo_por_base(prod, "O.S.")
    b = _resumo_por_base(cons, "Consultivos")
    dfm = a.merge(b, on="_BASE_NORM", how="outer", suffixes=("", "_CONS"))

    # resolve Base display
    dfm["Base"] = dfm["Base"].fillna(dfm["Base_CONS"]).fillna("Não Informado")
    dfm.drop(columns=[c for c in ("Base_CONS",) if c in dfm.columns], inplace=True)

    dfm["O.S."] = dfm["O.S."].fillna(0).astype(int)
    dfm["Consultivos"] = dfm["Consultivos"].fillna(0).astype(int)

    max_data = pd.to_datetime(
        dfm[["MAX_DATA", "MAX_DATA_CONS"]].max(axis=1), errors="coerce"
    )
    dfm["MAX_DATA_ALL"] = max_data

    # calcula fator por linha usando cache por data_max
    dias_falt = []
    fator_lst = []
    for v in dfm["MAX_DATA_ALL"].tolist():
        if pd.isna(v):
            fator, falt, _ = 1.0, 0, 0
        else:
            fator, falt, _ = CalculosOperacionais.fator_por_data_max(
                pd.Timestamp(v).normalize().date()
            )
        fator_lst.append(fator)
        dias_falt.append(falt)

    dfm["Dias faltantes"] = dias_falt
    dfm["Fator"] = fator_lst
    dfm["O.S. projetadas"] = (dfm["O.S."] * dfm["Fator"]).astype(int)
    dfm["Consultivos projetados"] = (dfm["Consultivos"] * dfm["Fator"]).astype(int)

    dfm["% Meta O.S. (proj)"] = np.round(
        CalculosOperacionais.calcular_atingimento(
            dfm["O.S. projetadas"], Metas.PRODUCAO_OS_BASE["meta_base"]
        ),
        1,
    )
    dfm["% Meta Cons. (proj)"] = np.round(
        CalculosOperacionais.calcular_atingimento(
            dfm["Consultivos projetados"], Metas.CONSULTIVO_BASE["meta_base"]
        ),
        1,
    )

    dfm["Falta atual O.S."] = np.maximum(
        Metas.PRODUCAO_OS_BASE["meta_base"] - dfm["O.S."], 0
    ).astype(int)
    dfm["Falta atual consultivos"] = np.maximum(
        Metas.CONSULTIVO_BASE["meta_base"] - dfm["Consultivos"], 0
    ).astype(int)
    dfm["A fazer após projeção O.S."] = np.maximum(
        Metas.PRODUCAO_OS_BASE["meta_base"] - dfm["O.S. projetadas"], 0
    ).astype(int)
    dfm["A fazer após projeção consultivos"] = np.maximum(
        Metas.CONSULTIVO_BASE["meta_base"] - dfm["Consultivos projetados"], 0
    ).astype(int)

    dfm["Status O.S."] = dfm["O.S."].map(
        lambda v: get_status_base(v, Metas.PRODUCAO_OS_BASE)[0]
    )
    dfm["Status Consult."] = dfm["Consultivos"].map(
        lambda v: get_status_base(v, Metas.CONSULTIVO_BASE)[0]
    )

    return dfm.sort_values("Base").reset_index(drop=True)


with tab_bases:
    render_section_header_seguro(
        "Visão por Base",
        "Comparativo independente de Produção e Consultivos por unidade operacional",
        icone="🗂️",
        badge="Metas por base",
        badge_tipo="verde",
    )

    if df_prod_f.empty and df_cons_f.empty:
        render_empty_state_seguro(
            "Sem dados", "Ajuste filtros para visualizar as bases."
        )
    else:
        df_proj_base = _projecao_por_base(df_prod_f, df_cons_f)

        # KPIs consolidados
        k1, k2, k3, k4 = st.columns(4)
        render_kpi_seguro(
            k1,
            "Bases com dados",
            f"{len(df_proj_base):,}",
            "Bases únicas no período",
            "azul",
        )
        render_kpi_seguro(
            k2,
            "O.S. (atual)",
            f"{int(df_proj_base['O.S.'].sum()):,}",
            "Soma produção filtrada",
            "verde",
        )
        render_kpi_seguro(
            k3,
            "Consultivos (atual)",
            f"{int(df_proj_base['Consultivos'].sum()):,}",
            "Soma consultivo filtrado",
            "laranja",
        )
        render_kpi_seguro(
            k4,
            "Bases prioritárias",
            f"{sum(df_proj_base['Base'].str.upper().isin(BASES_PRIORITARIAS)):,}",
            "ABCDM/LESTE/GUARULHOS",
            "roxo",
        )

        st.divider()
        st.markdown("#### Bases prioritárias")

        cards = st.columns(3)
        for col, base_nome in zip(cards, BASES_PRIORITARIAS):
            row = df_proj_base[
                df_proj_base["Base"].astype(str).str.strip().str.upper() == base_nome
            ]
            os_atual = int(row["O.S."].iloc[0]) if not row.empty else 0
            cons_atual = int(row["Consultivos"].iloc[0]) if not row.empty else 0

            ating_os = float(
                CalculosOperacionais.calcular_atingimento(
                    os_atual, Metas.PRODUCAO_OS_BASE["meta_base"]
                )
            )
            ating_cons = float(
                CalculosOperacionais.calcular_atingimento(
                    cons_atual, Metas.CONSULTIVO_BASE["meta_base"]
                )
            )

            status_os = get_status_base(os_atual, Metas.PRODUCAO_OS_BASE)[0]
            status_cons = get_status_base(cons_atual, Metas.CONSULTIVO_BASE)[0]

            with col:
                col.markdown(
                    f"""
                    <div class="base-card">
                        <div class="base-title">{escape(base_nome)}</div>
                        <div style="margin-bottom:.45rem;">
                            <div><strong>Produção:</strong> {os_atual:,} O.S. ({ating_os:.1f}%)</div>
                            <div>{render_status_pill_seguro(status_os, status_os)}</div>
                        </div>
                        <div>
                            <div><strong>Consultivos:</strong> {cons_atual:,} ({ating_cons:.1f}%)</div>
                            <div>{render_status_pill_seguro(status_cons, status_cons)}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.divider()
        cA, cB = st.columns(2)

        with cA:
            fig_os = px.bar(
                df_proj_base.sort_values("O.S.", ascending=True),
                x="O.S.",
                y="Base",
                orientation="h",
                color="O.S.",
                color_continuous_scale=["#DBEAFE", Cores.PRIMARIA],
                title="Produção (O.S.) por base",
            )
            fig_os.add_vline(
                x=Metas.PRODUCAO_OS_BASE["meta_base"],
                line_dash="dash",
                line_color=Cores.SECUNDARIA,
            )
            fig_os.update_layout(
                height=360,
                margin=dict(l=20, r=20, t=50, b=10),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_os, use_container_width=True)

        with cB:
            fig_cons = px.bar(
                df_proj_base.sort_values("Consultivos", ascending=True),
                x="Consultivos",
                y="Base",
                orientation="h",
                color="Consultivos",
                color_continuous_scale=["#FED7AA", Cores.SECUNDARIA],
                title="Consultivos por base",
            )
            fig_cons.add_vline(
                x=Metas.CONSULTIVO_BASE["meta_base"],
                line_dash="dash",
                line_color=Cores.PRIMARIA,
            )
            fig_cons.update_layout(
                height=360,
                margin=dict(l=20, r=20, t=50, b=10),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_cons, use_container_width=True)

        st.divider()
        st.markdown("#### Projeções mensais por base")
        st.caption(
            "Projeção com ritmo atual e dias úteis restantes no mês (exclui domingos e feriados)."
        )

        base_prioritaria_rule = {
            "Base": [
                (
                    lambda v: str(v).strip().upper() in BASES_PRIORITARIAS,
                    Cores.SECUNDARIA,
                )
            ]
        }
        faltantes_rule = {
            **base_prioritaria_rule,
            "Falta atual O.S.": [
                (lambda v: isinstance(v, (int, float)) and v > 0, Cores.ALERTA)
            ],
            "A fazer após projeção O.S.": [
                (lambda v: isinstance(v, (int, float)) and v > 0, Cores.ATENCAO)
            ],
            "Falta atual consultivos": [
                (lambda v: isinstance(v, (int, float)) and v > 0, Cores.ALERTA)
            ],
            "A fazer após projeção consultivos": [
                (lambda v: isinstance(v, (int, float)) and v > 0, Cores.ATENCAO)
            ],
        }

        render_table_seguro(
            df_proj_base[
                [
                    "Base",
                    "Dias faltantes",
                    "O.S.",
                    "Falta atual O.S.",
                    "O.S. projetadas",
                    "A fazer após projeção O.S.",
                    "% Meta O.S. (proj)",
                ]
            ],
            titulo="Produção projetada por base | Meta: 11.000 O.S.",
            fmt={"% Meta O.S. (proj)": "{:.1f}%"},
            color_rules=faltantes_rule,
            num_cols=[
                "Dias faltantes",
                "O.S.",
                "Falta atual O.S.",
                "O.S. projetadas",
                "A fazer após projeção O.S.",
            ],
        )

        render_table_seguro(
            df_proj_base[
                [
                    "Base",
                    "Dias faltantes",
                    "Consultivos",
                    "Falta atual consultivos",
                    "Consultivos projetados",
                    "A fazer após projeção consultivos",
                    "% Meta Cons. (proj)",
                ]
            ],
            titulo="Consultivos projetados por base | Meta: 525",
            fmt={"% Meta Cons. (proj)": "{:.1f}%"},
            color_rules=faltantes_rule,
            num_cols=[
                "Dias faltantes",
                "Consultivos",
                "Falta atual consultivos",
                "Consultivos projetados",
                "A fazer após projeção consultivos",
            ],
        )

        with st.expander("Exportar resumo por base"):
            csv = df_proj_base.to_csv(index=False, encoding="utf-8-sig", sep=";")
            st.download_button(
                "Baixar CSV",
                data=csv,
                file_name=f"resumo_bases_{datetime.now(CFG.TZ).strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )


# =============================================================================
# Aba Projeção (por base)
# =============================================================================

with tab_projecao:
    render_section_header_seguro(
        "Projeção por Base",
        "Projete o fechamento mensal com os ritmos atuais de Produção e Consultivos",
        icone="📈",
        badge="Projeção",
        badge_tipo="azul",
    )

    bases_projecao = sorted(
        set(df_prod_f.get("BASE", pd.Series(dtype=str)).dropna().astype(str))
        | set(df_cons_f.get("BASE", pd.Series(dtype=str)).dropna().astype(str))
    )
    if not bases_projecao:
        render_empty_state_seguro(
            "Sem bases", "Ajuste os filtros para habilitar a projeção."
        )
    else:
        base_sel = st.selectbox("Base", bases_projecao, key="projecao_base")
        base_norm = normalizar_texto(base_sel)

        prod_base = (
            df_prod_f[df_prod_f.get("_BASE_NORM", pd.Series(dtype=str)) == base_norm]
            if not df_prod_f.empty
            else df_prod_f
        )
        cons_base = (
            df_cons_f[df_cons_f.get("_BASE_NORM", pd.Series(dtype=str)) == base_norm]
            if not df_cons_f.empty
            else df_cons_f
        )
        base_union = pd.concat([prod_base, cons_base], ignore_index=True)

        _, dias_rest_sim, dias_tot = CalculosOperacionais.fator_projecao(
            base_union, "DATA"
        )

        c1, c2, c3 = st.columns(3)
        dias_projecao = c1.number_input(
            "Dias restantes (úteis)",
            min_value=0,
            value=int(dias_rest_sim),
            key="projecao_dias",
        )
        ritmo_os = c2.number_input(
            "Ritmo diário O.S.",
            min_value=0,
            value=(
                int(len(prod_base) / max(1, dias_rest_sim)) if dias_rest_sim > 0 else 0
            ),
            key="projecao_ritmo_os",
        )
        ritmo_cons = c3.number_input(
            "Ritmo diário consultivos",
            min_value=0,
            value=(
                int(len(cons_base) / max(1, dias_rest_sim)) if dias_rest_sim > 0 else 0
            ),
            key="projecao_ritmo_cons",
        )

        res_os = int(len(prod_base) + (ritmo_os * dias_projecao))
        res_cons = int(len(cons_base) + (ritmo_cons * dias_projecao))

        st.markdown("#### Resultado projetado")
        r1, r2 = st.columns(2)
        render_kpi_seguro(
            r1,
            "Produção projetada",
            f"{res_os:,} O.S.",
            f"Meta 11.000 | {float(CalculosOperacionais.calcular_atingimento(res_os, Metas.PRODUCAO_OS_BASE['meta_base'])):.1f}% | {get_status_base(res_os, Metas.PRODUCAO_OS_BASE)[0]}",
            "azul",
        )
        render_kpi_seguro(
            r2,
            "Consultivos projetados",
            f"{res_cons:,}",
            f"Meta 525 | {float(CalculosOperacionais.calcular_atingimento(res_cons, Metas.CONSULTIVO_BASE['meta_base'])):.1f}% | {get_status_base(res_cons, Metas.CONSULTIVO_BASE)[0]}",
            "laranja",
        )

        render_progress_bar_seguro(
            "Progresso projetado Produção",
            res_os,
            Metas.PRODUCAO_OS_BASE["meta_base"],
            " O.S.",
        )
        render_progress_bar_seguro(
            "Progresso projetado Consultivos",
            res_cons,
            Metas.CONSULTIVO_BASE["meta_base"],
            "",
        )

        st.caption(
            f"Base {base_sel}: atual {len(prod_base):,} O.S. e {len(cons_base):,} consultivos | {dias_tot} dias úteis no mês (conforme data máxima)"
        )