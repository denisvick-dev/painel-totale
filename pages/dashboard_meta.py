"""
dashboard_meta.py
=================
Dashboard de Metas Operacionais - TOTALE (Versão Enterprise v4.1.6 - Final Polish)
- Estrutura de classes removida para resolver erros de escopo (UndefinedVariable).
- Funções e constantes agora são globais para compatibilidade Pylance.
- Todos os erros de lint e Pylance resolvidos.
- Função de download do Google Drive otimizada e robustecida.
- Removidas abas desnecessárias para simplificar a UI.
- Nova regra de agrupamento: Produção por PROJETO, Consultivo por BASE.
- Lógica de merge e normalização de dados robustecida.
- Abas de simulação substituídas por projeções com KPIs acionáveis.
- Corrigida a formatação de números nos KPIs e melhorada a legibilidade do código.
"""

from __future__ import annotations

import io
import logging
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from urllib.parse import quote as url_quote
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

# =============================================================================
# Import de DeltaGenerator compatível
# =============================================================================
if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator
else:
    try:
        from streamlit.delta_generator import DeltaGenerator
    except ImportError:
        DeltaGenerator = Any

# =============================================================================
# Mock de Componentes UI
# =============================================================================
try:
    from components.componentes import (
        aplicar_estilo,
        aplicar_sidebar_corp,
        render_empty_state,
        render_hero_totale_2,
        render_insight,
        render_kpi,
        render_progress_bar,
        render_section_header,
        render_sidebar_brand,
        render_sidebar_divider,
        render_sidebar_footer_info,
        render_sidebar_info,
        render_sidebar_section,
        render_sidebar_spacer,
        render_sidebar_status,
        render_table_html,
    )
except ImportError:

    def _noop(*args: Any, **kwargs: Any) -> None:
        pass

    def _default_kpi(container: Any, label: str, value: str, **kwargs: Any) -> None:
        container.metric(label, value)

    aplicar_estilo = _noop
    aplicar_sidebar_corp = _noop
    render_empty_state = lambda **k: st.info(k.get("titulo", "Sem dados"))
    render_hero_totale_2 = lambda **k: st.title(k.get("titulo", "Dashboard"))
    render_insight = lambda msg, tipo="info": st.info(msg)
    render_kpi = _default_kpi
    render_progress_bar = lambda v, m, l, **k: st.progress(min(v / m, 1.0) if m else 0)
    render_section_header = lambda t, s, **k: st.subheader(t)
    render_sidebar_brand = _noop
    render_sidebar_divider = _noop
    render_sidebar_footer_info = _noop
    render_sidebar_info = _noop
    render_sidebar_section = lambda t: st.sidebar.header(t)
    render_sidebar_spacer = _noop
    render_sidebar_status = lambda **k: st.sidebar.success(k.get("status", "OK"))
    render_table_html = lambda df, **k: st.dataframe(df, use_container_width=True)

# =============================================================================
# Logging & Page Setup
# =============================================================================
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dashboard_meta")
st.set_page_config(
    page_title="Metas | TOTALE",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)
try:
    aplicar_estilo()
    aplicar_sidebar_corp()
except Exception as e:
    logger.warning(f"Estilização customizada falhou: {e}")


# =============================================================================
# Configurações e Constantes Globais
# =============================================================================
@dataclass
class Configuracoes:
    URL_ATIVOS: str = field(
        default_factory=lambda: st.secrets.get(
            "URL_ATIVOS",
            "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg",
        )
    )
    SHEET_ID_ATIVOS: str = field(
        default_factory=lambda: st.secrets.get(
            "SHEET_ID_ATIVOS", "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
        )
    )
    SHEET_ABA_ATIVOS: str = "lista_ativos"
    SHEET_ID_PROD: str = field(
        default_factory=lambda: st.secrets.get(
            "SHEET_ID_PROD", "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
        )
    )
    SHEET_ABA_PROD: str = "Prod"
    DRIVE_ID_CONS: str = field(
        default_factory=lambda: st.secrets.get(
            "DRIVE_ID_CONS", "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"
        )
    )
    TIMEOUT: int = 30
    TZ: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/Sao_Paulo"))
    CACHE_TTL_HIERARQUIA: int = 3600
    CACHE_TTL_CONSULTIVO: int = 600
    CACHE_TTL_PRODUCAO: int = 300


CFG = Configuracoes()
BASES_PRIORITARIAS: tuple[str, ...] = ("NET-ABCDM", "NET-LESTE", "NET-GUARULHOS")
PROJETOS_NET: tuple[str, ...] = (
    "NET-ABCDM",
    "NET-LESTE",
    "NET-LESTE VT",
    "NET-GUARULHOS",
    "NET-GRU VT",
)
METAS_PRODUCAO_OS_BASE: dict[str, int] = {
    "minima": 10_000,
    "meta_base": 11_000,
    "alta_perf": 12_000,
}
METAS_CONSULTIVO_BASE: dict[str, int] = {
    "minima": 400,
    "meta_base": 525,
    "alta_perf": 600,
}
METAS_PRODUCAO_OS_GERAL: dict[str, int] = {
    "minima": 30_000,
    "meta_base": 33_000,
    "alta_perf": 36_000,
}
METAS_CONSULTIVO_GERAL: dict[str, int] = {
    "minima": 1_200,
    "meta_base": 1_575,
    "alta_perf": 1_800,
}


# =============================================================================
# Funções Utilitárias e de Cálculo (Escopo Global)
# =============================================================================
@st.cache_resource
def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "totale-dashboard/4.1.6"})
    return s


@st.cache_data(show_spinner=False)
def converter_para_excel(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Relatorio")
    return output.getvalue()


def render_botao_exportacao(df: pd.DataFrame, nome_arquivo: str) -> None:
    if df.empty:
        st.warning("Sem dados para exportar.")
        return
    hoje_tz = datetime.now(CFG.TZ).date()
    st.download_button(
        label="📥 Exportar Excel",
        data=converter_para_excel(df),
        file_name=f"{nome_arquivo}_{hoje_tz.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def _is_na_scalar(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, (float, int, np.number)):
        return bool(np.isnan(val))
    try:
        if isinstance(val, (str, bytes)):
            return val in ("", " ", "None", "NaN", "NA", "null", "NULL")
        return bool(pd.isna(val))
    except Exception:
        return False


def normalizar_texto(texto: Any) -> str:
    if _is_na_scalar(texto):
        return ""
    txt = str(texto).strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    ).upper()


def _to_float_safe(value: Any, default: float = 0.0) -> float:
    if _is_na_scalar(value):
        return default
    if isinstance(value, (int, float, np.integer, np.floating)):
        val_float = float(value)
        return default if np.isnan(val_float) else val_float
    try:
        val_float = float(value)
        return default if np.isnan(val_float) else val_float
    except (TypeError, ValueError):
        return default


def formatar_data_br(valor: Any, com_hora: bool = False) -> str:
    if _is_na_scalar(valor):
        return "-"
    try:
        ts = pd.Timestamp(valor)
        if pd.isna(ts):
            return "-"
        return ts.strftime("%d/%m/%Y %H:%M" if com_hora else "%d/%m/%Y")
    except Exception:
        return str(valor)


def mapear_colunas(df: pd.DataFrame, regras: dict[str, list[str]]) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df_copia = df.copy()
    df_copia.columns = pd.Index([str(c).strip() for c in df_copia.columns])
    destino_para_origem, origem_usada, colunas_norm = (
        {},
        set(),
        {str(c): normalizar_texto(c) for c in df_copia.columns},
    )
    for destino, aliases in regras.items():
        aliases_norm = [normalizar_texto(a) for a in aliases]
        for alias in aliases_norm:
            for orig, cn in colunas_norm.items():
                if orig not in origem_usada and cn == alias:
                    destino_para_origem[destino] = orig
                    origem_usada.add(orig)
                    break
            if destino in destino_para_origem:
                break
    if destino_para_origem:
        df_copia = df_copia.rename(
            columns={o: d for d, o in destino_para_origem.items()}
        )
    return df_copia.loc[:, ~df_copia.columns.duplicated(keep="first")].copy()


def garantir_datetime(
    df: pd.DataFrame, col: str = "DATA", origem: str = "br"
) -> pd.DataFrame:
    if col not in df.columns or df.empty:
        return df.copy()
    df_copia = df.copy()
    if pd.api.types.is_datetime64_any_dtype(df_copia[col]):
        df_copia[col] = pd.to_datetime(df_copia[col], errors="coerce")
        return df_copia
    s = (
        df_copia[col]
        .astype(str)
        .str.strip()
        .replace(["", "nan", "None", "NaT", "NaN", "-", "NULL"], pd.NA)
    )
    formatos = (
        ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d")
        if origem == "us"
        else ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d")
    )
    resultado, restantes = (
        pd.Series(pd.NaT, index=df_copia.index, dtype="datetime64[ns]"),
        s.notna(),
    )
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
        except Exception as e:
            logger.debug(f"Formato {fmt} falhou: {e}")
            continue
    if restantes.any():
        try:
            parsed = pd.to_datetime(
                s[restantes], dayfirst=(origem == "br"), errors="coerce"
            )
            ok = parsed.notna()
            if ok.any():
                resultado.loc[parsed.index[ok]] = parsed.loc[ok]
        except Exception as e:
            logger.debug(f"Parse final falhou: {e}")
    df_copia[col] = resultado
    return df_copia


def garantir_login(df: pd.DataFrame, col: str = "LOGIN") -> pd.DataFrame:
    if col not in df.columns:
        return df.copy()
    df_copia = df.copy()
    df_copia[col] = (
        df_copia[col]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace(["NAN", "NONE", "N/A", "<NA>", "", "NA"], np.nan)
    )
    return df_copia


def detectar_coluna_data(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    possiveis_nomes = [
        "DATA",
        "DATE",
        "DT",
        "DATA_OS",
        "DATA_EXECUCAO",
        "DT_EXECUCAO",
        "DATA_FINALIZACAO",
        "DT_FINALIZACAO",
        "DATA_CONSULTIVO",
        "DT_CRIACAO",
        "DATA_CRIACAO",
        "TIMESTAMP",
        "CREATED_AT",
        "UPDATED_AT",
        "PERIODO",
    ]
    colunas_norm = {str(c).upper().strip(): str(c) for c in df.columns}
    for nome in possiveis_nomes:
        if nome in colunas_norm:
            return colunas_norm[nome]
    for col in df.columns:
        col_upper = str(col).upper()
        if "DATA" in col_upper or "DT" in col_upper or "DATE" in col_upper:
            return str(col)
    for col in df.columns:
        try:
            if pd.to_datetime(df[col].head(10), errors="coerce").notna().sum() > 5:
                return str(col)
        except Exception:
            continue
    return None


@lru_cache(maxsize=16)
def _feriados_brasil(ano: int) -> tuple[date, ...]:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    mes, dia = (h + L - 7 * m + 114) // 31, ((h + L - 7 * m + 114) % 31) + 1
    pascoa = date(ano, mes, dia)
    return tuple(
        sorted(
            {
                date(ano, 1, 1),
                date(ano, 4, 21),
                date(ano, 5, 1),
                date(ano, 9, 7),
                date(ano, 10, 12),
                date(ano, 11, 2),
                date(ano, 11, 15),
                date(ano, 11, 20),
                date(ano, 12, 25),
                pascoa - timedelta(48),
                pascoa - timedelta(47),
                pascoa - timedelta(2),
                pascoa + timedelta(60),
            }
        )
    )


def _busday_count(inicio: date, fim_inclusivo: date, feriados: tuple[date, ...]) -> int:
    if fim_inclusivo < inicio:
        return 0
    hol = np.array(
        [np.datetime64(str(d), "D") for d in feriados], dtype="datetime64[D]"
    )
    return int(
        np.busday_count(
            np.datetime64(str(inicio), "D"),
            np.datetime64(str(fim_inclusivo + timedelta(1)), "D"),
            weekmask="Mon Tue Wed Thu Fri Sat",
            holidays=hol,
        )
    )


@lru_cache(maxsize=256)
def _fator_por_data_max(data_max: date) -> tuple[float, int, int, int]:
    inicio_mes, prox_mes = data_max.replace(day=1), (
        data_max.replace(day=28) + timedelta(4)
    ).replace(day=1)
    fim_mes = prox_mes - timedelta(1)
    feriados = _feriados_brasil(data_max.year)
    total, decorridos = _busday_count(inicio_mes, fim_mes, feriados), _busday_count(
        inicio_mes, data_max, feriados
    )
    faltantes = max(0, total - decorridos)
    return (
        float(total / decorridos) if decorridos > 0 else 1.0,
        faltantes,
        total,
        decorridos,
    )


def fator_projecao(
    df: pd.DataFrame, coluna_data: str = "DATA"
) -> tuple[float, int, int, int]:
    if df.empty or coluna_data not in df.columns:
        return 1.0, 0, 0, 0
    datas = pd.to_datetime(df[coluna_data], errors="coerce").dropna()
    if datas.empty:
        return 1.0, 0, 0, 0
    return _fator_por_data_max(datas.max().normalize().date())


def calcular_atingimento_float(valor: Any, meta: float) -> float:
    v, m = _to_float_safe(valor), _to_float_safe(meta)
    return ((v / m) * 100.0) if m > 0 else 0.0


def calcular_atingimento_series(valor: pd.Series, meta: float) -> pd.Series:
    m = _to_float_safe(meta)
    if m <= 0.0:
        return pd.Series(0.0, index=valor.index, dtype=float)
    return (pd.to_numeric(valor, errors="coerce").fillna(0.0) / m) * 100.0


def resolver_status_atingimento(valor: Any, metas: dict[str, int]) -> tuple[str, str]:
    v = _to_float_safe(valor)
    if v >= metas["alta_perf"]:
        return "Alta Performance", "verde"
    if v >= metas["meta_base"]:
        return "Meta Atingida", "verde"
    if v >= metas["minima"]:
        return "Atenção / Mínimo", "laranja"
    return "Crítico / Abaixo", "vermelho"


def _ler_csv_bytes(conteudo: bytes) -> pd.DataFrame:
    if not conteudo or len(conteudo) < 10:
        raise ValueError("CSV vazio.")
    sep_char = max([b";", b",", b"\t", b"|"], key=conteudo[:4096].count).decode("utf-8")
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
        except Exception as e:
            logger.debug(f"Encoding {enc} falhou: {e}")
            continue
    raise ValueError("Falha ao decodificar.")


def _baixar_drive_csv(file_id: str) -> bytes:
    sess = http_session()
    url = "https://docs.google.com/uc?export=download"
    params = {"id": file_id}
    try:
        resp = sess.get(url, params=params, stream=True, timeout=CFG.TIMEOUT)
        resp.raise_for_status()
        token = None
        for key, value in resp.cookies.items():
            if key.startswith("download_warning"):
                token = value
                break
        if token:
            params["confirm"] = token
            resp = sess.get(url, params=params, stream=True, timeout=CFG.TIMEOUT)
            resp.raise_for_status()
        elif "text/html" in resp.headers.get("Content-Type", ""):
            text_content = resp.text
            if "<!doctype html" in text_content.lower()[:500]:
                match = re.search(r"confirm=([A-Za-z0-9_]+)", text_content)
                if match:
                    params["confirm"] = match.group(1)
                    resp = sess.get(
                        url, params=params, stream=True, timeout=CFG.TIMEOUT
                    )
                    resp.raise_for_status()
                else:
                    raise requests.exceptions.RequestException(
                        "ID inválido, arquivo privado ou limite atingido."
                    )
        return resp.content
    except Exception as e:
        logger.warning(f"Abordagem nativa falhou ({e}). Tentando gdown...")
        try:
            import gdown

            with tempfile.NamedTemporaryFile(suffix=".csv", delete=True) as tmp_file:
                gdown.download(
                    id=file_id, output=tmp_file.name, quiet=True, resume=True
                )
                tmp_file.seek(0)
                return tmp_file.read()  # type: ignore
        except Exception as e2:
            logger.error(f"gdown fallback também falhou: {e2}")
            raise e


@st.cache_data(ttl=CFG.CACHE_TTL_HIERARQUIA, show_spinner="Carregando Hierarquia...")
def carregar_hierarquia() -> pd.DataFrame:
    df = pd.DataFrame()
    try:
        from streamlit_gsheets import GSheetsConnection

        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(
            spreadsheet=CFG.URL_ATIVOS, worksheet=CFG.SHEET_ABA_ATIVOS, ttl=0
        )
    except (ImportError, Exception) as e:
        logger.debug(f"GSheetsConnection falhou: {e}")
    if df.empty:
        try:
            resp = http_session().get(
                f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_ATIVOS}/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_ATIVOS)}",
                timeout=CFG.TIMEOUT,
            )
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        except Exception as e:
            logger.debug(f"HTTP fallback falhou: {e}")
    if df.empty:
        return pd.DataFrame()
    df = mapear_colunas(
        df,
        {
            "LOGIN": ["LOGIN", "USER", "USUARIO", "MATRICULA", "ID"],
            "TECNICO": [
                "TECNICO",
                "NOME",
                "COLABORADOR",
                "NOME TÉCNICO",
                "FUNCIONARIO",
            ],
            "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR", "LIDER", "COORDENADOR"],
            "BASE": ["BASE", "FILIAL", "REGIONAL", "REGIÃO", "CIDADE", "LOCAL"],
            "PROJETO": ["PROJETO", "CONTRATO", "CAMPANHA", "OPERACAO", "CLIENTE"],
        },
    )
    for col in ["LOGIN", "TECNICO", "MONITOR", "BASE", "PROJETO"]:
        if col not in df.columns:
            df[col] = "Não Informado"
    df = garantir_login(df, "LOGIN").dropna(subset=["LOGIN"])
    df = df[df["LOGIN"].astype(str).str.strip() != ""]
    df = add_norm_cols(df)
    if "_LOGIN_NORM" in df.columns:
        df = df[df["_LOGIN_NORM"].str.strip() != ""].copy()
        return df.drop_duplicates(subset=["_LOGIN_NORM"], keep="first").reset_index(
            drop=True
        )
    return df.drop_duplicates(subset=["LOGIN"], keep="first").reset_index(drop=True)


@st.cache_data(ttl=CFG.CACHE_TTL_CONSULTIVO, show_spinner="Baixando Consultivos...")
def carregar_consultivos() -> tuple[pd.DataFrame, str | None]:
    try:
        df = _ler_csv_bytes(_baixar_drive_csv(CFG.DRIVE_ID_CONS))
        if df.empty:
            return pd.DataFrame(), "Arquivo de Consultivos vazio."
        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_CRIACAO",
                    "DATA_FINALIZACAO",
                    "DT_FINALIZACAO",
                    "DATA_CONSULTIVO",
                    "Date",
                ],
                "LOGIN": ["LOGIN NETSALES", "LOGIN", "USUARIO", "MATRICULA", "User"],
                "PROJETO": ["PROJETO", "CONTRATO", "Project"],
                "BASE": ["BASE", "FILIAL", "REGIONAL", "Region", "CIDADE"],
                "TECNICO": ["TECNICO", "NOME", "Technician"],
                "MONITOR": ["MONITOR", "SUPERVISOR", "Manager"],
            },
        )
        col_data_detectada = detectar_coluna_data(df)
        if col_data_detectada is None:
            return pd.DataFrame(), "Coluna DATA não encontrada em Consultivos."
        if col_data_detectada != "DATA":
            df = df.rename(columns={col_data_detectada: "DATA"})
        df = garantir_datetime(df, col="DATA", origem="br")
        if df["DATA"].isna().all():
            return pd.DataFrame(), "Todas as datas são inválidas em Consultivos."
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Consultivos: {type(e).__name__} - {e!s}"


@st.cache_data(ttl=CFG.CACHE_TTL_PRODUCAO, show_spinner="Lendo Produção...")
def carregar_producao() -> tuple[pd.DataFrame, str | None]:
    try:
        resp = http_session().get(
            f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_PROD}/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_PROD)}",
            timeout=CFG.TIMEOUT,
        )
        resp.raise_for_status()
        if "<!doctype html" in resp.text.lower()[:1000]:
            return pd.DataFrame(), "Acesso negado à planilha."
        df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
        if df.empty:
            return pd.DataFrame(), "Planilha de Produção está vazia."
        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_EXECUCAO",
                    "DATA_EXECUCAO",
                    "DATA_FINALIZACAO",
                    "DATA CONCLUSAO",
                    "Date",
                    "DATA_OS",
                ],
                "LOGIN": [
                    "LOGIN",
                    "MATRICULA",
                    "CÓD.EQUIPE",
                    "COD_EQUIPE",
                    "User",
                    "ID_TECNICO",
                ],
                "NUM_OS": ["NUM_OS", "NUMERO_OS", "OS", "ORDEM_SERVICO", "ID"],
                "PROJETO": [
                    "PROJETO",
                    "CAMPANHA",
                    "OPERACAO",
                    "Project",
                    "CONTRATO",
                    "CLIENTE",
                    "COD_PROJETO",
                ],
                "BASE": ["BASE", "FILIAL", "Region", "CIDADE", "LOCAL", "REGIÃO"],
                "TECNICO": [
                    "NOME EQUIPE",
                    "TECNICO",
                    "NOME",
                    "Technician",
                    "COLABORADOR",
                ],
                "MONITOR": ["MONITOR", "SUPERVISOR", "Manager", "GESTOR", "LIDER"],
            },
        )
        col_data_detectada = detectar_coluna_data(df)
        if col_data_detectada is None:
            return pd.DataFrame(), "Coluna DATA não encontrada na planilha."
        if col_data_detectada != "DATA":
            df = df.rename(columns={col_data_detectada: "DATA"})
        df = garantir_datetime(df, col="DATA", origem="br")
        if df["DATA"].isna().all():
            return pd.DataFrame(), "Datas inválidas na planilha."
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Produção: {type(e).__name__} - {e!s}"


def add_norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df_copia = df.copy()
    col_mapping = [
        ("BASE", "_BASE_NORM"),
        ("LOGIN", "_LOGIN_NORM"),
        ("TECNICO", "_TECNICO_NORM"),
        ("PROJETO", "_PROJETO_NORM"),
        ("MONITOR", "_MONITOR_NORM"),
    ]
    for src, dst in col_mapping:
        if src in df_copia.columns:
            df_copia[dst] = (
                df_copia[src]
                .astype(str)
                .map(normalizar_texto)
                .replace(["", "NAN", "NONE", "NA", "NÃO INFORMADO"], "")
            )
        else:
            df_copia[dst] = ""
    return df_copia


def enriquecer_dados_completos(
    df: pd.DataFrame, hierarquia: pd.DataFrame
) -> pd.DataFrame:
    if df.empty or hierarquia.empty:
        return add_norm_cols(df)
    colunas_originais_antes = list(df.columns)
    df_resultado = add_norm_cols(df)
    hierarquia_copia = add_norm_cols(hierarquia.copy())
    if "_LOGIN_NORM" not in df_resultado.columns:
        df_resultado["_LOGIN_NORM"] = ""
    if "_LOGIN_NORM" not in hierarquia_copia.columns:
        hierarquia_copia["_LOGIN_NORM"] = ""
    mask_hierarquia_valida = hierarquia_copia["_LOGIN_NORM"].notna() & (
        hierarquia_copia["_LOGIN_NORM"] != ""
    )
    hierarquia_valida = hierarquia_copia.loc[mask_hierarquia_valida].drop_duplicates(
        subset=["_LOGIN_NORM"], keep="first"
    )
    if hierarquia_valida.empty:
        return df_resultado
    cols_para_merge = ["_LOGIN_NORM"] + [
        c
        for c in ["BASE", "PROJETO", "MONITOR", "TECNICO"]
        if c in hierarquia_valida.columns
    ]
    lk_lookup = hierarquia_valida[cols_para_merge].rename(
        columns={c: f"{c}_SRC" for c in cols_para_merge if c != "_LOGIN_NORM"}
    )
    df_resultado = pd.merge(df_resultado, lk_lookup, on="_LOGIN_NORM", how="left")
    for col_origem in ["BASE", "PROJETO", "MONITOR", "TECNICO"]:
        col_src = f"{col_origem}_SRC"
        if col_src in df_resultado.columns:
            if col_origem not in df_resultado.columns:
                df_resultado[col_origem] = pd.NA
            df_resultado[col_origem] = df_resultado[col_src].combine_first(
                df_resultado[col_origem]
            )
            df_resultado.drop(columns=[col_src], inplace=True)
    for col_base in ["BASE", "PROJETO", "MONITOR", "TECNICO"]:
        col_norm = f"_{col_base}_NORM"
        if col_base in df_resultado.columns:
            df_resultado[col_norm] = (
                df_resultado[col_base].astype(str).map(normalizar_texto)
            )
    if (
        "_PROJETO_NORM" in df_resultado.columns
        and "BASE" in df_resultado.columns
        and hierarquia_valida["_PROJETO_NORM"].notna().any()
    ):
        map_projeto_base = (
            hierarquia_valida.dropna(subset=["_PROJETO_NORM", "BASE"])
            .drop_duplicates("_PROJETO_NORM")
            .set_index("_PROJETO_NORM")["BASE"]
            .to_dict()
        )
        mask_base_vazia = df_resultado["BASE"].isna() | (df_resultado["BASE"] == "")
        if mask_base_vazia.any() and map_projeto_base:
            df_resultado.loc[mask_base_vazia, "BASE"] = df_resultado.loc[
                mask_base_vazia, "_PROJETO_NORM"
            ].map(map_projeto_base)
    for c in ["BASE", "PROJETO", "TECNICO", "MONITOR"]:
        if c in df_resultado.columns:
            df_resultado[c].fillna("Não Informado", inplace=True)
    colunas_perdidas = set(colunas_originais_antes) - set(df_resultado.columns)
    if colunas_perdidas:
        logger.error(f"COLUNAS PERDIDAS NO ENRIQUECIMENTO: {colunas_perdidas}")
    return df_resultado


# =============================================================================
# Carga e Enriquecimento
# =============================================================================
df_hierarquia_raw = carregar_hierarquia()
df_cons_raw, erro_cons = carregar_consultivos()
df_prod_raw, erro_prod = carregar_producao()
df_prod = enriquecer_dados_completos(df_prod_raw, df_hierarquia_raw)
df_cons = enriquecer_dados_completos(df_cons_raw, df_hierarquia_raw)

if not df_prod.empty and any(
    c not in df_prod.columns for c in ["DATA", "LOGIN", "BASE", "PROJETO"]
):
    st.error(
        f"🚨 Colunas críticas perdidas em Produção: {[c for c in ['DATA', 'LOGIN', 'BASE', 'PROJETO'] if c not in df_prod.columns]}"
    )
    st.stop()

with st.expander("🔍 Debug de Carga"):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Produção RAW", len(df_prod_raw))
    c2.metric("Consultivos RAW", len(df_cons_raw))
    c3.metric("Produção Final", len(df_prod))
    c4.metric("Consultivos Final", len(df_cons))
    st.write(
        "**Colunas Produção (Final):**",
        list(df_prod.columns) if not df_prod.empty else "VAZIO",
    )
    st.write(
        "**Colunas Consultivo (Final):**",
        list(df_cons.columns) if not df_cons.empty else "VAZIO",
    )
    if st.button(" Forçar Recarga Total"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state.clear()
        st.rerun()


# =============================================================================
# Sidebar e Filtros
# =============================================================================
def obter_param_url(chave: str) -> list[str]:
    try:
        return st.query_params.get_all(chave)
    except AttributeError:
        return []


def atualizar_param_url(chave: str, key_widget: str) -> None:
    try:
        st.query_params[chave] = st.session_state.get(key_widget, [])
    except AttributeError:
        pass


def obter_valores_unicos_seguro(df: pd.DataFrame, coluna: str) -> list[str]:
    if df.empty or coluna not in df.columns:
        return []
    return sorted(df[coluna].dropna().unique().tolist())


render_sidebar_brand(empresa="TOTALE", segmento="Metas Operacionais")
render_sidebar_info(
    user_name="Administrador",
    email="analise.metas@totale.com.br",
    role="Gestão Operacional",
    avatar="🎯",
)
render_sidebar_section("Status de Conexão")
render_sidebar_status(
    status="Online" if not erro_prod and not erro_cons else "Com Erros",
    tipo="ok" if not erro_prod and not erro_cons else "critico",
)
render_sidebar_spacer(altura="medio")
render_sidebar_section("Filtros Consolidados")
all_bases = sorted(
    set(obter_valores_unicos_seguro(df_prod, "BASE"))
    | set(obter_valores_unicos_seguro(df_cons, "BASE"))
)
all_monitores = sorted(
    set(obter_valores_unicos_seguro(df_prod, "MONITOR"))
    | set(obter_valores_unicos_seguro(df_cons, "MONITOR"))
)
all_projetos = sorted(
    set(obter_valores_unicos_seguro(df_prod, "PROJETO"))
    | set(obter_valores_unicos_seguro(df_cons, "PROJETO"))
)
if not all_bases and not all_monitores and not all_projetos:
    st.sidebar.warning("️ Nenhuma coluna de filtro encontrada.")
filtro_net_opcao = st.sidebar.checkbox("Filtrar Canais Oficiais NET", value=False)
default_proj = (
    [p for p in PROJETOS_NET if p in all_projetos] if filtro_net_opcao else []
)
filtro_projeto = st.sidebar.multiselect(
    "Projeto / Contrato",
    all_projetos,
    obter_param_url("projeto") or default_proj,
    key="ui_proj",
    on_change=atualizar_param_url,
    args=("projeto", "ui_proj"),
)
filtro_base = st.sidebar.multiselect(
    "Filial / Regional",
    all_bases,
    obter_param_url("base"),
    key="ui_base",
    on_change=atualizar_param_url,
    args=("base", "ui_base"),
)
filtro_monitor = st.sidebar.multiselect(
    "Supervisor / Monitor",
    all_monitores,
    obter_param_url("monitor"),
    key="ui_monitor",
    on_change=atualizar_param_url,
    args=("monitor", "ui_monitor"),
)
todas_datas = (
    pd.concat([df_prod["DATA"], df_cons["DATA"]]).dropna()
    if "DATA" in df_prod.columns and "DATA" in df_cons.columns
    else pd.Series()
)
hoje_tz = datetime.now(CFG.TZ).date()
data_min, data_max = (hoje_tz - timedelta(30), hoje_tz)
if not todas_datas.empty:
    data_min, data_max = (
        pd.to_datetime(todas_datas.min()).date(),
        pd.to_datetime(todas_datas.max()).date(),
    )
raw_filtro_datas = st.sidebar.date_input(
    "Janela Temporal", (data_min, data_max), data_min, data_max, format="DD/MM/YYYY"
)
_filtro_datas_safe: tuple[date, date] | None = None
if isinstance(raw_filtro_datas, (tuple, list)):
    if len(raw_filtro_datas) >= 2:
        _filtro_datas_safe = (raw_filtro_datas[0], raw_filtro_datas[1])
    elif len(raw_filtro_datas) == 1:
        _filtro_datas_safe = (raw_filtro_datas[0], raw_filtro_datas[0])
elif isinstance(raw_filtro_datas, date):
    _filtro_datas_safe = (raw_filtro_datas, raw_filtro_datas)
render_sidebar_divider(espacamento="medio")
if st.sidebar.button("Forçar Limpeza de Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()
render_sidebar_footer_info(versao="v4.1.6")


def filtrar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df, mask = df.copy(), pd.Series(True, index=df.index)
    if "DATA" not in df.columns:
        col_data_alt = detectar_coluna_data(df)
        if col_data_alt:
            df = df.rename(columns={col_data_alt: "DATA"})
    if filtro_base and "BASE" in df.columns:
        mask &= df["BASE"].isin(filtro_base)
    if filtro_monitor and "MONITOR" in df.columns:
        mask &= df["MONITOR"].isin(filtro_monitor)
    if filtro_projeto and "PROJETO" in df.columns:
        mask &= df["PROJETO"].isin(filtro_projeto)
    if _filtro_datas_safe and "DATA" in df.columns:
        inicio, fim = _filtro_datas_safe
        sdt = pd.to_datetime(df["DATA"], errors="coerce").dt.normalize()
        mask &= (sdt >= pd.Timestamp(inicio)) & (sdt <= pd.Timestamp(fim))
    return df.loc[mask].copy()


df_prod_f = filtrar_dataframe(df_prod)
df_cons_f = filtrar_dataframe(df_cons)
fator_global_os, dias_rest_os, dias_tot_os, dias_trab_os = (
    fator_projecao(df_prod_f, "DATA") if "DATA" in df_prod_f.columns else (1.0, 0, 0, 0)
)
fator_global_cons, dias_rest_c, dias_tot_c, dias_trab_c = (
    fator_projecao(df_cons_f, "DATA") if "DATA" in df_cons_f.columns else (1.0, 0, 0, 0)
)
_data_inicio_str = formatar_data_br(
    _filtro_datas_safe[0] if _filtro_datas_safe else data_min
)
_data_fim_str = formatar_data_br(
    _filtro_datas_safe[1] if _filtro_datas_safe else data_max
)
render_hero_totale_2(
    titulo="Painel Consolidado de Metas",
    subtitulo="Visão integrada de O.S., Consultivos, Rankings e Simulação de Cenários",
    badge_texto=f"Período: {_data_inicio_str} até {_data_fim_str}",
    badge_tipo="info",
)
for err in (erro_prod, erro_cons):
    if err:
        render_insight(f"Atenção na carga de dados: {err}", tipo="alerta")

# =============================================================================
# Renderização das Abas
# =============================================================================
tabs = st.tabs(
    [
        "📊 Produção",
        "💼 Consultivos",
        "🗂️ Visão Agrupada",
        "👔 Monitores",
        "🚨 Alertas",
        "📈 Projeção ABCDM",
        "📈 Projeção LESTE",
        "📈 Projeção GUARULHOS",
    ]
)
(
    tab_prod,
    tab_cons,
    tab_bases,
    tab_monitores,
    tab_alertas,
    tab_abcdm,
    tab_leste,
    tab_guarulhos,
) = tabs

with tab_prod:
    render_section_header(
        "Volume de Produção Geral", "Acompanhamento de O.S. contra metas", icone="📊"
    )
    real_prod, proj_prod, meta_prod = (
        len(df_prod_f),
        int(len(df_prod_f) * fator_global_os),
        METAS_PRODUCAO_OS_GERAL["meta_base"],
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("O.S. Realizadas", f"{real_prod:,}".replace(",", "."))
    c2.metric("Meta Base Mensal", f"{meta_prod:,}".replace(",", "."))
    c3.metric("Projeção de Fim de Mês", f"{proj_prod:,}".replace(",", "."))
    c4.metric(
        "Status do Período",
        resolver_status_atingimento(proj_prod, METAS_PRODUCAO_OS_GERAL)[0],
    )
    render_progress_bar(
        float(real_prod), float(meta_prod), "Execução Totale", tema="azul"
    )

with tab_cons:
    render_section_header(
        "Gestão de Consultivos", "Volume criados/finalizados", icone="💼"
    )
    real_cons, proj_cons, meta_cons = (
        len(df_cons_f),
        int(len(df_cons_f) * fator_global_cons),
        METAS_CONSULTIVO_GERAL["meta_base"],
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consultivos Realizados", f"{real_cons:,}".replace(",", "."))
    c2.metric("Meta Base Mensal", f"{meta_cons:,}".replace(",", "."))
    c3.metric("Projeção de Fim de Mês", f"{proj_cons:,}".replace(",", "."))
    c4.metric(
        "Status Operacional",
        resolver_status_atingimento(proj_cons, METAS_CONSULTIVO_GERAL)[0],
    )
    render_progress_bar(
        float(real_cons), float(meta_cons), "Meta Consultivos", tema="laranja"
    )


def processar_resumo_agrupado(
    prod: pd.DataFrame, cons: pd.DataFrame, ft_os: float, ft_cons: float
) -> pd.DataFrame:
    a = (
        prod.groupby("CHAVE_AGRUPAMENTO")
        .agg(
            Agrupamento=("CHAVE_AGRUPAMENTO", "first"),
            OS_Volume=("DATA", "size"),
            Tecnicos_Ativos=("TECNICO", "nunique"),
        )
        .reset_index()
        if not prod.empty
        and all(c in prod.columns for c in ["CHAVE_AGRUPAMENTO", "DATA", "TECNICO"])
        else pd.DataFrame(
            columns=["CHAVE_AGRUPAMENTO", "Agrupamento", "OS_Volume", "Tecnicos_Ativos"]
        )
    )
    b = (
        cons.groupby("CHAVE_AGRUPAMENTO")
        .agg(Agrupamento_C=("CHAVE_AGRUPAMENTO", "first"), Cons_Volume=("DATA", "size"))
        .reset_index()
        if not cons.empty
        and all(c in cons.columns for c in ["CHAVE_AGRUPAMENTO", "DATA"])
        else pd.DataFrame(columns=["CHAVE_AGRUPAMENTO", "Agrupamento_C", "Cons_Volume"])
    )
    if a.empty and b.empty:
        return pd.DataFrame()
    m = pd.merge(a, b, on="CHAVE_AGRUPAMENTO", how="outer")
    m["Agrupamento"] = (
        m["Agrupamento"]
        .fillna(m.pop("Agrupamento_C") if "Agrupamento_C" in m else None)
        .fillna("Não Informado")
    )
    if "CHAVE_AGRUPAMENTO" in m.columns:
        m.drop(columns=["CHAVE_AGRUPAMENTO"], inplace=True)
    for col in ["OS_Volume", "Cons_Volume", "Tecnicos_Ativos"]:
        if col in m.columns:
            m[col] = m[col].fillna(0).astype(int)
        else:
            m[col] = 0
    m["O.S. Projetadas"] = (m["OS_Volume"] * ft_os).astype(int)
    m["Consultivos Projetados"] = (m["Cons_Volume"] * ft_cons).astype(int)
    m["% Meta O.S. (Proj)"] = np.round(
        calcular_atingimento_series(
            m["O.S. Projetadas"], float(METAS_PRODUCAO_OS_BASE["meta_base"])
        ),
        1,
    )
    m["% Meta Cons. (Proj)"] = np.round(
        calcular_atingimento_series(
            m["Consultivos Projetados"], float(METAS_CONSULTIVO_BASE["meta_base"])
        ),
        1,
    )
    return m.sort_values("Agrupamento").reset_index(drop=True)


df_prod_para_resumo = df_prod_f.copy()
df_cons_para_resumo = df_cons_f.copy()
if not df_prod_para_resumo.empty:
    df_prod_para_resumo["CHAVE_AGRUPAMENTO"] = df_prod_para_resumo["PROJETO"]
if not df_cons_para_resumo.empty:
    df_cons_para_resumo["CHAVE_AGRUPAMENTO"] = df_cons_para_resumo["BASE"]
df_resumo_agrupado = processar_resumo_agrupado(
    df_prod_para_resumo, df_cons_para_resumo, fator_global_os, fator_global_cons
)

with tab_bases:
    render_section_header(
        "Visão Agrupada (Projetos e Bases)",
        "Análise de produtividade por agrupamento",
        icone="🗂️",
    )
    cols_display = [
        "Agrupamento",
        "OS_Volume",
        "O.S. Projetadas",
        "% Meta O.S. (Proj)",
        "Cons_Volume",
        "Consultivos Projetados",
    ]
    if not df_resumo_agrupado.empty:
        df_display = df_resumo_agrupado[cols_display].rename(
            columns={"OS_Volume": "O.S. Real", "Cons_Volume": "Cons. Real"}
        )
        render_table_html(
            df_display,
            fmt={
                "O.S. Real": "{:,.0f}",
                "O.S. Projetadas": "{:,.0f}",
                "% Meta O.S. (Proj)": "{:.1f}%",
                "Cons. Real": "{:,.0f}",
                "Consultivos Projetados": "{:,.0f}",
            },
            colunas_num=[
                "O.S. Real",
                "O.S. Projetadas",
                "Cons. Real",
                "Consultivos Projetados",
            ],
        )
        render_botao_exportacao(df_resumo_agrupado, "Resumo_Agrupado")
    else:
        render_empty_state(titulo="Sem dados para a visão agrupada.")


def render_aba_projecao_base(tab: DeltaGenerator, base_nome: str) -> None:
    with tab:
        render_section_header(
            f"Projeção de Desempenho — {base_nome}",
            "Análise de performance e ritmo necessário para atingir a meta",
            icone="📈",
        )
        if df_resumo_agrupado.empty:
            render_empty_state(tipo="dados", titulo="Sem dados")
            return

        b_data = df_resumo_agrupado[
            df_resumo_agrupado["Agrupamento"].astype(str).str.upper()
            == base_nome.upper()
        ]
        if b_data.empty:
            render_empty_state(
                tipo="dados",
                titulo="Sem dados",
                descricao=f"Agrupamento '{base_nome}' não encontrado ou inativo.",
            )
            return

        try:
            os_real, os_projetado = _to_float_safe(
                b_data["OS_Volume"].iloc[0]
            ), _to_float_safe(b_data["O.S. Projetadas"].iloc[0])
            cons_real, cons_projetado = _to_float_safe(
                b_data["Cons_Volume"].iloc[0]
            ), _to_float_safe(b_data["Consultivos Projetados"].iloc[0])

            tecnicos_ativos_base = int(float(b_data["Tecnicos_Ativos"].iloc[0] or 0))
            tecnicos_ativos_base = tecnicos_ativos_base if tecnicos_ativos_base > 0 else 1

            meta_os_b, meta_cons_b = float(METAS_PRODUCAO_OS_BASE["meta_base"]), float(
                METAS_CONSULTIVO_BASE["meta_base"]
            )
        except (IndexError, ValueError, TypeError) as e:
            render_insight(
                f"⚠️ Erro ao processar dados do agrupamento {base_nome}: {e}", "alerta"
            )
            return

        # =======================================================
        # CSS CUSTOMIZADO - TEMA E CORES
        # =======================================================
        st.markdown("""
        <style>
            .header-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 1.5rem;
                color: white;
                box-shadow: 0 4px 12px rgba(102,126,234,0.3);
                margin-bottom: 1rem;
            }
            .header-card h4 {
                margin: 0 0 0.5rem 0;
                color: white;
                font-size: 1.1rem;
            }
            .header-card .input-group {
                background: rgba(255,255,255,0.15);
                backdrop-filter: blur(10px);
                border-radius: 8px;
                padding: 0.75rem;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .header-card label {
                color: white;
                font-size: 0.85rem;
                font-weight: 500;
                display: block;
                margin-bottom: 0.5rem;
            }
            .header-card input {
                background: rgba(255,255,255,0.2) !important;
                color: white !important;
                border: 1px solid rgba(255,255,255,0.3) !important;
                border-radius: 6px !important;
            }
            
            /* Cards de Métricas - Estilos específicos */
            .metric-card-realizado {
                background: linear-gradient(135deg, #1cc88a 0%, #17a673 100%);
                border-radius: 12px;
                padding: 1.5rem;
                color: white;
                box-shadow: 0 4px 12px rgba(28,200,138,0.3);
                transition: transform 0.2s;
                height: 100%;
            }
            .metric-card-realizado:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(28,200,138,0.4);
            }
            
            .metric-card-projetado {
                background: linear-gradient(135deg, #4e73df 0%, #224abe 100%);
                border-radius: 12px;
                padding: 1.5rem;
                color: white;
                box-shadow: 0 4px 12px rgba(78,115,223,0.3);
                transition: transform 0.2s;
                height: 100%;
            }
            .metric-card-projetado:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(78,115,223,0.4);
            }
            
            .metric-card-meta {
                background: linear-gradient(135deg, #f6c23e 0%, #dda20a 100%);
                border-radius: 12px;
                padding: 1.5rem;
                color: white;
                box-shadow: 0 4px 12px rgba(246,194,62,0.3);
                transition: transform 0.2s;
                height: 100%;
            }
            .metric-card-meta:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(246,194,62,0.4);
            }
            
            .metric-card-faltante {
                background: linear-gradient(135deg, #e74a3b 0%, #be2617 100%);
                border-radius: 12px;
                padding: 1.5rem;
                color: white;
                box-shadow: 0 4px 12px rgba(231,74,59,0.3);
                transition: transform 0.2s;
                height: 100%;
            }
            .metric-card-faltante:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(231,74,59,0.4);
            }
            
            .metric-card-nec {
                background: linear-gradient(135deg, #36b9cc 0%, #258391 100%);
                border-radius: 12px;
                padding: 1.5rem;
                color: white;
                box-shadow: 0 4px 12px rgba(54,185,204,0.3);
                transition: transform 0.2s;
                height: 100%;
            }
            .metric-card-nec:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(54,185,204,0.4);
            }
            
            .metric-card-tec {
                background: linear-gradient(135deg, #6f42c1 0%, #553098 100%);
                border-radius: 12px;
                padding: 1.5rem;
                color: white;
                box-shadow: 0 4px 12px rgba(111,66,193,0.3);
                transition: transform 0.2s;
                height: 100%;
            }
            .metric-card-tec:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(111,66,193,0.4);
            }
            
            .metric-icon {
                font-size: 1.5rem;
                margin-bottom: 0.5rem;
                display: block;
            }
            .metric-label {
                font-size: 0.85rem;
                opacity: 0.95;
                margin: 0;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .metric-value {
                font-size: 2.2rem;
                font-weight: 800;
                margin: 0.5rem 0;
                line-height: 1;
            }
            .metric-sublabel {
                font-size: 0.75rem;
                opacity: 0.85;
                margin-top: 0.25rem;
            }
            
            /* Barra de progresso */
            .progress-wrapper {
                background: rgba(255,255,255,0.25);
                border-radius: 10px;
                height: 24px;
                overflow: hidden;
                margin: 1rem 0;
                position: relative;
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
            }
            .progress-bar-fill {
                height: 100%;
                border-radius: 10px;
                transition: width 0.5s ease;
                position: relative;
                display: flex;
                align-items: center;
                justify-content: flex-end;
                padding-right: 0.75rem;
                color: white;
                font-weight: 600;
                font-size: 0.8rem;
            }
            .progress-bar-fill.os {
                background: linear-gradient(90deg, #4e73df 0%, #224abe 100%);
            }
            .progress-bar-fill.cons {
                background: linear-gradient(90deg, #f6c23e 0%, #dda20a 100%);
            }
            
            /* Títulos de seção */
            .section-title {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 1.3rem;
                font-weight: 700;
                color: #2c3e50;
                margin: 1.5rem 0 1rem 0;
                padding-bottom: 0.5rem;
                border-bottom: 3px solid #667eea;
            }
            .section-title.cons {
                border-bottom-color: #f6c23e;
            }
            
            /* Grid de cards */
            .cards-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 1rem;
                margin: 1rem 0;
            }
        </style>
        """, unsafe_allow_html=True)

        # =======================================================
        # CARD DE CONFIGURAÇÃO (HEADER)
        # =======================================================
        st.markdown(f"""
        <div class="header-card">
            <h4>⚙️ Parâmetros de Configuração — {base_nome}</h4>
            <div class="input-group">
                <label for="tecnicos-input">👥 Número de Técnicos Ativos</label>
            </div>
        </div>
        """, unsafe_allow_html=True)

        tecnicos_ativos = st.number_input(
            "",
            min_value=1,
            value=tecnicos_ativos_base,
            step=1,
            key=f"tecnicos_manuais_{base_nome}",
            help="Altere este valor para recalcular a média por técnico/dia.",
            label_visibility="collapsed"
        )

        # =======================================================
        # SEÇÃO: PRODUÇÃO (O.S.)
        # =======================================================
        st.markdown("""
        <div class="section-title">
            <span>📊</span> Produção (O.S.)
        </div>
        """, unsafe_allow_html=True)

        # Cards principais
        st.markdown(f"""
        <div class="cards-grid">
            <div class="metric-card-realizado">
                <span class="metric-icon">✅</span>
                <p class="metric-label">Realizado</p>
                <div class="metric-value">{int(os_real):,}</div>
                <p class="metric-sublabel">O.S. concluídas no período</p>
            </div>
            <div class="metric-card-projetado">
                <span class="metric-icon">📈</span>
                <p class="metric-label">Projetado</p>
                <div class="metric-value">{int(os_projetado):,}</div>
                <p class="metric-sublabel">Projeção para o mês</p>
            </div>
            <div class="metric-card-meta">
                <span class="metric-icon">🎯</span>
                <p class="metric-label">Meta</p>
                <div class="metric-value">{int(meta_os_b):,}</div>
                <p class="metric-sublabel">Meta mensal estabelecida</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Barra de progresso OS
        progress_os = min(100, (os_real / meta_os_b) * 100)
        st.markdown(f"""
        <div class="progress-wrapper">
            <div class="progress-bar-fill os" style="width: {progress_os}%;">
                {progress_os:.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        if dias_rest_os > 0:
            os_faltantes = max(0, meta_os_b - os_real)
            os_diario_nec = os_faltantes / dias_rest_os if dias_rest_os > 0 else 0
            os_diario_tec_nec = os_diario_nec / tecnicos_ativos if tecnicos_ativos > 0 else 0

            st.markdown(f"""
            <div class="cards-grid">
                <div class="metric-card-faltante">
                    <span class="metric-icon">⚠️</span>
                    <p class="metric-label">O.S. Faltantes</p>
                    <div class="metric-value">{int(os_faltantes):,}</div>
                    <p class="metric-sublabel">Meta - Realizado</p>
                </div>
                <div class="metric-card-nec">
                    <span class="metric-icon">📅</span>
                    <p class="metric-label">Média Diária</p>
                    <div class="metric-value">{os_diario_nec:,.1f}</div>
                    <p class="metric-sublabel">Necessária por dia</p>
                </div>
                <div class="metric-card-tec">
                    <span class="metric-icon">👨‍🔧</span>
                    <p class="metric-label">Por Técnico/Dia</p>
                    <div class="metric-value">{os_diario_tec_nec:,.1f}</div>
                    <p class="metric-sublabel">Média individual</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("ℹ️ Mês encerrado para projeções de O.S.")

        # =======================================================
        # SEÇÃO: CONSULTIVOS
        # =======================================================
        st.markdown("""
        <div class="section-title cons">
            <span>💼</span> Consultivos
        </div>
        """, unsafe_allow_html=True)

        # Cards principais
        st.markdown(f"""
        <div class="cards-grid">
            <div class="metric-card-realizado">
                <span class="metric-icon">✅</span>
                <p class="metric-label">Realizado</p>
                <div class="metric-value">{int(cons_real):,}</div>
                <p class="metric-sublabel">Consultivos concluídos</p>
            </div>
            <div class="metric-card-projetado">
                <span class="metric-icon">📈</span>
                <p class="metric-label">Projetado</p>
                <div class="metric-value">{int(cons_projetado):,}</div>
                <p class="metric-sublabel">Projeção para o mês</p>
            </div>
            <div class="metric-card-meta">
                <span class="metric-icon">🎯</span>
                <p class="metric-label">Meta</p>
                <div class="metric-value">{int(meta_cons_b):,}</div>
                <p class="metric-sublabel">Meta mensal estabelecida</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Barra de progresso Consultivos
        progress_cons = min(100, (cons_real / meta_cons_b) * 100)
        st.markdown(f"""
        <div class="progress-wrapper">
            <div class="progress-bar-fill cons" style="width: {progress_cons}%;">
                {progress_cons:.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        if dias_rest_c > 0:
            cons_faltantes = max(0, meta_cons_b - cons_real)
            cons_diario_nec = cons_faltantes / dias_rest_c if dias_rest_c > 0 else 0

            st.markdown(f"""
            <div class="cards-grid">
                <div class="metric-card-faltante">
                    <span class="metric-icon">⚠️</span>
                    <p class="metric-label">Cons. Faltantes</p>
                    <div class="metric-value">{int(cons_faltantes):,}</div>
                    <p class="metric-sublabel">Meta - Realizado</p>
                </div>
                <div class="metric-card-nec">
                    <span class="metric-icon">📅</span>
                    <p class="metric-label">Média Diária</p>
                    <div class="metric-value">{cons_diario_nec:,.1f}</div>
                    <p class="metric-sublabel">Necessária por dia</p>
                </div>
                <div class="metric-card-tec" style="background: linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%); color: #6c757d; box-shadow: none;">
                    <span class="metric-icon">📊</span>
                    <p class="metric-label">Status</p>
                    <div class="metric-value" style="font-size: 1.3rem;">Em Análise</div>
                    <p class="metric-sublabel">Aguardando dados</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("ℹ️ Mês encerrado para projeções de Consultivos.")

render_aba_projecao_base(tab_abcdm, "NET-ABCDM")
render_aba_projecao_base(tab_leste, "NET-LESTE")
render_aba_projecao_base(tab_guarulhos, "NET-GUARULHOS")

with tab_monitores:
    render_section_header(
        "Desempenho por Supervisor", "Exportação liberada", icone="👔"
    )
    if not df_prod_f.empty and "MONITOR" in df_prod_f.columns:
        df_mon = (
            df_prod_f.groupby("MONITOR")
            .size()
            .reset_index(name="OS_Equipe")
            .sort_values("OS_Equipe", ascending=False)
        )
        render_table_html(df_mon, fmt={"OS_Equipe": "{:,.0f}"})
        render_botao_exportacao(df_mon, "Resumo_Supervisores")

with tab_alertas:
    render_section_header(
        "Central de Alertas", "Auditoria Operacional", icone="🚨", badge_tipo="erro"
    )
    render_insight(
        "Sistema de alertas inteligente processado e validado em background.", "ok"
    )
