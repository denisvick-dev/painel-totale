"""
dashboard_meta.py
=================
Dashboard de Metas Operacionais - TOTALE (Versão Production-Ready v3.0.4)
- Integração profunda com o Design System corporativo (componentes.py)
- Datas 100% padrão pt-BR (DD/MM/YYYY)
- Projeções automáticas baseadas em Dias Úteis Seg–Sáb (exclui domingos e feriados)
- 100% Type-Safe: Zero erros no Pylance / MyPy
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import (
    Any,
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
from streamlit.delta_generator import DeltaGenerator

# Importação dos componentes do design system TOTALE
try:
    from components.componentes import (
        Cores,
        Fontes,
        aplicar_estilo,
        aplicar_sidebar_corp,
        render_empty_state,
        render_hero_totale_2,
        render_insight,
        render_kpi,
        render_kpi_sm,
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

    COMPONENTES_DISPONIVEIS = True
except ImportError as e:
    st.error(
        f"Erro ao importar componentes.py: {e}. Certifique-se de que o arquivo está no mesmo diretório."
    )
    raise e

try:
    from streamlit_gsheets import GSheetsConnection  # type: ignore
except ImportError:
    GSheetsConnection = None  # type: ignore

try:
    import gdown  # type: ignore
except ImportError:
    gdown = None  # type: ignore


# =============================================================================
# Logging & Page Setup
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dashboard_meta")

st.set_page_config(
    page_title="Dashboard de Metas | TOTALE",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Aplicar o design system corporativo imediatamente
aplicar_estilo()
aplicar_sidebar_corp()


# =============================================================================
# Configurações & Parâmetros Corporativos
# =============================================================================
BASES_PRIORITARIAS: tuple[str, ...] = ("NET-ABCDM", "NET-LESTE", "NET-GUARULHOS")
PROJETOS_NET: tuple[str, ...] = (
    "NET-ABCDM",
    "NET-LESTE",
    "NET-LESTE VT",
    "NET-GUARULHOS",
    "NET-GRU VT",
)


@dataclass
class Configuracoes:
    URL_ATIVOS: str = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    SHEET_ID_ATIVOS: str = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    SHEET_ABA_ATIVOS: str = "lista_ativos"
    SHEET_ID_PROD: str = "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
    SHEET_ABA_PROD: str = "Prod"
    DRIVE_ID_CONS: str = "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"
    TIMEOUT: int = 30
    TZ: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/Sao_Paulo"))
    CACHE_TTL_HIERARQUIA: int = 3600
    CACHE_TTL_CONSULTIVO: int = 600
    CACHE_TTL_PRODUCAO: int = 300


CFG = Configuracoes()


class Metas:
    PRODUCAO_OS_BASE: dict[str, int] = {
        "minima": 10_000,
        "meta_base": 11_000,
        "alta_perf": 12_000,
    }
    CONSULTIVO_BASE: dict[str, int] = {
        "minima": 400,
        "meta_base": 525,
        "alta_perf": 600,
    }
    PRODUCAO_OS_GERAL: dict[str, int] = {
        "minima": 30_000,
        "meta_base": 33_000,
        "alta_perf": 36_000,
    }
    CONSULTIVO_GERAL: dict[str, int] = {
        "minima": 1_200,
        "meta_base": 1_575,
        "alta_perf": 1_800,
    }


# =============================================================================
# Conexão HTTP Cacheada
# =============================================================================
@st.cache_resource
def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "totale-dashboard/3.0"})
    return s


# =============================================================================
# Utilitários Type-Safe de Formatação & Tratamento de Dados
# =============================================================================
def _is_na_scalar(val: Any) -> bool:
    """Verifica se um valor escalar é nulo sem disparar erros do Pylance."""
    if val is None:
        return True
    if isinstance(val, (float, int, np.number)):
        return bool(np.isnan(val))
    try:
        return bool(pd.isna(val))
    except Exception:
        return False


def normalizar_texto(texto: Any) -> str:
    """Normaliza texto removendo acentos e convertendo para maiúsculo."""
    if _is_na_scalar(texto):
        return ""
    txt = str(texto).strip()
    txt = "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    )
    return txt.upper()


def _to_float_safe(value: Any, default: float = 0.0) -> float:
    """Converte valor para float com tratamento seguro de erros."""
    if value is None:
        return default
    if isinstance(value, (int, float, np.integer, np.floating)):
        f_val = float(value)
        return default if np.isnan(f_val) else f_val
    try:
        if _is_na_scalar(value):
            return default
        f_val = float(value)
        return default if np.isnan(f_val) else f_val
    except (TypeError, ValueError):
        return default


def formatar_data_br(valor: Any, com_hora: bool = False) -> str:
    """Formata data no padrão brasileiro DD/MM/YYYY."""
    if _is_na_scalar(valor):
        return "-"
    try:
        ts = pd.Timestamp(valor)
        if pd.isna(ts):
            return "-"
        return ts.strftime("%d/%m/%Y %H:%M") if com_hora else ts.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def formatar_df_para_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    """Formata colunas do tipo datetime do DataFrame para string DD/MM/AAAA antes da exibição."""
    if df.empty:
        return df

    df_display = df.copy()

    for col in df_display.columns:
        if pd.api.types.is_datetime64_any_dtype(df_display[col]):
            # Se todas as horas forem zeradas (00:00:00), formatar apenas como data DD/MM/AAAA
            tem_hora = (
                df_display[col].dropna().dt.strftime("%H:%M:%S") != "00:00:00"
            ).any()
            fmt = "%d/%m/%Y %H:%M" if tem_hora else "%d/%m/%Y"
            df_display[col] = df_display[col].dt.strftime(fmt).fillna("-")

    return df_display


def mapear_colunas(df: pd.DataFrame, regras: dict[str, list[str]]) -> pd.DataFrame:
    """Mapeia colunas com validação robusta."""
    if df.empty:
        return df

    df = df.copy()
    df.columns = pd.Index([str(c).strip() for c in df.columns])

    destino_para_origem: dict[str, str] = {}
    origem_usada: set[str] = set()
    colunas_norm = {str(c): normalizar_texto(c) for c in df.columns}

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
        df = df.rename(
            columns={orig: dest for dest, orig in destino_para_origem.items()}
        )

    # Remove colunas duplicadas
    df = df.loc[:, ~df.columns.duplicated(keep="first")].copy()

    return df


def garantir_datetime(
    df: pd.DataFrame,
    col: str = "DATA",
    origem: str = "br",
) -> pd.DataFrame:
    """Garante que a coluna seja datetime com fallback para múltiplos formatos."""
    if col not in df.columns or df.empty:
        return df

    df = df.copy()
    serie = df[col]

    if pd.api.types.is_datetime64_any_dtype(serie):
        df[col] = pd.to_datetime(serie, errors="coerce")
        return df

    s = (
        serie.astype(str)
        .str.strip()
        .replace(["", "nan", "None", "NaT", "NaN", "-", "NULL", "none"], pd.NA)
    )

    formatos = (
        ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d")
        if origem == "us"
        else ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d")
    )

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

    if restantes.any():
        try:
            parsed = pd.to_datetime(
                s[restantes], dayfirst=(origem == "br"), errors="coerce"
            )
            ok = parsed.notna()
            if ok.any():
                resultado.loc[parsed.index[ok]] = parsed.loc[ok]
        except Exception as e:
            logger.warning(f"Erro no fallback datetime ({origem}): {e}")

    df[col] = resultado
    return df


def garantir_login(df: pd.DataFrame, col: str = "LOGIN") -> pd.DataFrame:
    """Garante que a coluna LOGIN esteja normalizada."""
    if col not in df.columns:
        return df
    df = df.copy()
    s = df[col].astype(str).str.strip().str.upper()
    df[col] = s.replace(["NAN", "NONE", "N/A", "<NA>", "", "NA"], np.nan)
    return df


def add_norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona colunas normalizadas com validação robusta."""
    if df.empty:
        return df

    df = df.copy()

    # Mapeamento de colunas origem → destino
    colunas_norm_map = [
        ("BASE", "_BASE_NORM"),
        ("LOGIN", "_LOGIN_NORM"),
        ("TECNICO", "_TECNICO_NORM"),
        ("PROJETO", "_PROJETO_NORM"),
        ("MONITOR", "_MONITOR_NORM"),
    ]

    for src, dst in colunas_norm_map:
        if src in df.columns:
            # Converte para string, normaliza e trata nulos
            df[dst] = df[src].astype(str).map(normalizar_texto)
            # Substitui valores vazios/nulos por string vazia
            df[dst] = df[dst].replace(["", "NAN", "NONE", "NA"], "")
        else:
            # Cria coluna vazia se não existir
            df[dst] = ""

    # Preenche BASE com PROJETO se BASE estiver vazio
    if "_PROJETO_NORM" in df.columns and "_BASE_NORM" in df.columns:
        mask_vazia = (
            df["_BASE_NORM"].isin(["", "NAO INFORMADO", "NAN", "NONE", "NA"])
            | df["_BASE_NORM"].isna()
        )
        if "PROJETO" in df.columns:
            df.loc[mask_vazia, "_BASE_NORM"] = df.loc[mask_vazia, "_PROJETO_NORM"]
        if "BASE" in df.columns and "PROJETO" in df.columns:
            df.loc[mask_vazia, "BASE"] = df.loc[mask_vazia, "PROJETO"]

    return df


# =============================================================================
# Regras de Negócio e Cálculos de Projeção (Type-Safe)
# =============================================================================
class CalculosOperacionais:
    """Classe com cálculos operacionais e projeções."""

    @staticmethod
    @lru_cache(maxsize=16)
    def feriados_brasil(ano: int) -> tuple[date, ...]:
        """Calcula feriados nacionais e móveis do Brasil."""
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
            pascoa - timedelta(days=48),
            pascoa - timedelta(days=47),
            pascoa - timedelta(days=2),
            pascoa + timedelta(days=60),
        }
        return tuple(sorted(feriados))

    @staticmethod
    def _busday_count(
        inicio: date, fim_inclusivo: date, feriados: tuple[date, ...]
    ) -> int:
        """Conta dias úteis (Seg-Sáb) excluindo feriados."""
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
    def fator_por_data_max(data_max: date) -> tuple[float, int, int, int]:
        """Calcula fator de projeção baseado na data máxima."""
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
    ) -> tuple[float, int, int, int]:
        """Calcula fator de projeção para um DataFrame."""
        if df.empty or coluna_data not in df.columns:
            return 1.0, 0, 0, 0
        datas = pd.to_datetime(df[coluna_data], errors="coerce").dropna()
        if datas.empty:
            return 1.0, 0, 0, 0
        dmax = datas.max().normalize().date()
        return CalculosOperacionais.fator_por_data_max(dmax)

    @staticmethod
    def calcular_atingimento_float(valor: Any, meta: float) -> float:
        """Cálculo estritamente escalar de percentual de atingimento."""
        meta_f = _to_float_safe(meta)
        if meta_f <= 0.0:
            return 0.0
        val_f = _to_float_safe(valor)
        return (val_f / meta_f) * 100.0

    @staticmethod
    def calcular_atingimento_series(valor: pd.Series, meta: float) -> pd.Series:
        """Cálculo estritamente vetorizado para Series de Pandas."""
        meta_f = _to_float_safe(meta)
        if meta_f <= 0.0:
            return pd.Series(0.0, index=valor.index)
        s_num = pd.to_numeric(valor, errors="coerce").fillna(0.0)
        return (s_num / meta_f) * 100.0

    @staticmethod
    def calcular_atingimento(valor: Any, meta: float) -> Any:
        """Wrapper flexível mantendo compatibilidade."""
        if isinstance(valor, pd.Series):
            return CalculosOperacionais.calcular_atingimento_series(valor, meta)
        return CalculosOperacionais.calcular_atingimento_float(valor, meta)


def resolver_status_atingimento(valor: Any, metas: dict[str, int]) -> tuple[str, str]:
    """Resolve status e cor baseado no atingimento da meta."""
    v = _to_float_safe(valor)
    if v >= float(metas["alta_perf"]):
        return "Alta Performance", "verde"
    if v >= float(metas["meta_base"]):
        return "Meta Atingida", "verde"
    if v >= float(metas["minima"]):
        return "Atenção / Mínimo", "laranja"
    return "Crítico / Abaixo", "vermelho"


# =============================================================================
# Pipeline ETL de Dados
# =============================================================================
def _ler_csv_bytes(conteudo: bytes) -> pd.DataFrame:
    """Lê CSV de bytes com detecção automática de separador e encoding."""
    if not conteudo or len(conteudo) < 10:
        raise ValueError("CSV vazio ou de tamanho insuficiente.")
    head = conteudo[:4096]
    seps = [b";", b",", b"\t", b"|"]
    sep_char = max(seps, key=head.count).decode("utf-8")
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
    raise ValueError("Falha ao decodificar arquivo CSV com codificações comuns.")


def _baixar_drive_csv(file_id: str) -> bytes:
    """Baixa arquivo do Google Drive com fallback múltiplo."""
    sess = http_session()

    # Método 1: URL direta de download
    url = f"https://drive.google.com/uc?id={file_id}&export=download"

    try:
        resp = sess.get(url, stream=True, timeout=CFG.TIMEOUT)
        resp.raise_for_status()

        # Verifica se é HTML de erro (acesso negado)
        if "<!doctype html" in resp.text.lower()[:1000]:
            # Método 2: Tenta URL alternativa
            url_alt = f"https://drive.google.com/uc?export=download&id={file_id}"
            resp = sess.get(url_alt, stream=True, timeout=CFG.TIMEOUT)
            resp.raise_for_status()

        # Verifica cookie de confirmação (arquivos grandes)
        for k, v in resp.cookies.items():
            if k.startswith("download_warning"):
                url_confirm = f"{url}&confirm={v}"
                resp = sess.get(url_confirm, stream=True, timeout=CFG.TIMEOUT)
                resp.raise_for_status()
                break

        return resp.content

    except Exception as e:
        logger.warning(f"Fallback para gdown devido a: {e}")

        # Método 3: Tenta gdown se disponível
        if gdown is not None:
            try:
                tmp_path: str | None = None
                fd, tmp_path = tempfile.mkstemp(suffix=".csv")
                os.close(fd)
                gdown.download(  # type: ignore
                    f"https://drive.google.com/uc?id={file_id}", tmp_path, quiet=True
                )
                with open(tmp_path, "rb") as f:
                    return f.read()
            except Exception as gdown_err:
                logger.warning(f"gdown também falhou: {gdown_err}")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

        # Se tudo falhar, levanta o erro original
        raise


@st.cache_data(
    ttl=CFG.CACHE_TTL_HIERARQUIA, show_spinner="Carregando Hierarquia Operacional..."
)
def carregar_hierarquia() -> pd.DataFrame:
    """Carrega hierarquia de técnicos da planilha Google Sheets."""
    df = pd.DataFrame()

    if GSheetsConnection is not None:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            resultado = conn.read(
                spreadsheet=CFG.URL_ATIVOS, worksheet=CFG.SHEET_ABA_ATIVOS, ttl=0
            )
            if isinstance(resultado, pd.DataFrame) and not resultado.empty:
                df = resultado
        except Exception as e:
            logger.warning(f"Falha na conexão nativa GSheets para hierarquia: {e}")

    if df.empty:
        try:
            sess = http_session()
            csv_url = f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_ATIVOS}/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_ATIVOS)}"
            resp = sess.get(csv_url, timeout=CFG.TIMEOUT)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        except Exception as e:
            logger.error(f"Erro ao obter hierarquia via requisição direta: {e}")

    if df.empty:
        logger.warning("Hierarquia vazia - retornando DataFrame vazio")
        return pd.DataFrame()

    # Mapeia colunas
    df = mapear_colunas(
        df,
        {
            "LOGIN": ["LOGIN", "USER", "USUARIO", "MATRICULA", "MATRÍCULA"],
            "TECNICO": ["TECNICO", "NOME", "COLABORADOR", "NOME TÉCNICO"],
            "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR", "SUPERVISOR TÉCNICO"],
            "BASE": ["BASE", "FILIAL", "REGIONAL", "REGIÃO"],
        },
    )

    # Garante que todas as colunas essenciais existem
    for col in ["LOGIN", "TECNICO", "MONITOR", "BASE"]:
        if col not in df.columns:
            df[col] = "Não Informado"
            logger.warning(
                f"Coluna {col} não encontrada na hierarquia, criada com valor padrão"
            )

    # Normaliza LOGIN
    df = garantir_login(df, "LOGIN")

    # Remove linhas sem LOGIN válido
    df = df.dropna(subset=["LOGIN"])
    df = df[df["LOGIN"].astype(str).str.strip() != ""]
    df = df[df["LOGIN"].astype(str).str.upper().notna()]

    # Remove duplicatas
    df = df.drop_duplicates(subset=["LOGIN"], keep="first").reset_index(drop=True)

    logger.info(f"Hierarquia carregada: {len(df)} registros únicos")
    return df


@st.cache_data(
    ttl=CFG.CACHE_TTL_CONSULTIVO, show_spinner="Baixando Volume de Consultivos..."
)
def carregar_consultivos() -> tuple[pd.DataFrame, str | None]:
    """Carrega dados de consultivos do Google Drive."""
    try:
        content = _baixar_drive_csv(CFG.DRIVE_ID_CONS)
        df = _ler_csv_bytes(content)

        logger.info(f"Colunas originais Consultivos: {list(df.columns)}")

        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_CRIACAO",
                    "CRIACAO",
                    "DATA_FINALIZACAO",
                    "DT_FINALIZACAO",
                    "DATA_CRIACAO",
                    "DT",
                    "DATE",
                    "DATA_CONSULTIVO",
                    "DATA_ATENDIMENTO",
                ],
                "LOGIN": ["LOGIN NETSALES", "LOGIN", "USUARIO", "MATRICULA", "USER"],
                "PROJETO": ["PROJETO", "CONTRATO", "CONTRATO_PROJETO"],
                "BASE": ["BASE", "FILIAL", "REGIONAL"],
                "TECNICO": ["TECNICO", "NOME", "NOME_TECNICO"],
                "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR"],
            },
        )

        # Verifica se DATA foi mapeada
        if "DATA" not in df.columns:
            logger.warning(
                f"Coluna DATA não encontrada! Colunas disponíveis: {list(df.columns)}"
            )
            for col in df.columns:
                col_upper = str(col).upper()
                if "DATA" in col_upper or "DT" in col_upper or "DATE" in col_upper:
                    df = df.rename(columns={col: "DATA"})
                    logger.info(f"Coluna '{col}' renomeada para 'DATA'")
                    break

        if "DATA" not in df.columns:
            logger.error("Não foi possível identificar coluna de DATA")
            df["DATA"] = pd.NaT

        return garantir_datetime(df, col="DATA", origem="br"), None

    except Exception as e:
        logger.exception("Inconsistência crítica de consultivos")
        return pd.DataFrame(), f"Consultivos: {type(e).__name__} (verificar conexões)"


@st.cache_data(
    ttl=CFG.CACHE_TTL_PRODUCAO, show_spinner="Lendo registros de Produção..."
)
def carregar_producao() -> tuple[pd.DataFrame, str | None]:
    """Carrega dados de produção do Google Sheets."""
    try:
        sess = http_session()
        url = f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_PROD}/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_PROD)}"
        resp = sess.get(url, timeout=CFG.TIMEOUT)
        resp.raise_for_status()

        if "<!doctype html" in resp.text.lower()[:1000]:
            return pd.DataFrame(), "Acesso negado à planilha corporativa privada."

        df = pd.read_csv(io.StringIO(resp.text), dtype=str)

        # Remove colunas Unnamed
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

        logger.info(f"Colunas originais Produção: {list(df.columns)}")

        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_EXECUCAO",
                    "EXECUCAO",
                    "DT_FINALIZACAO",
                    "DATA_EXECUCAO",
                    "DATA_FINALIZACAO",
                    "DT",
                    "DATE",
                    "DATA_OS",
                    "DATA CONCLUSAO",
                    "CONCLUSAO",
                ],
                "LOGIN": [
                    "LOGIN",
                    "MATRICULA",
                    "USER",
                    "CÓD.EQUIPE",
                    "CODEQUIPE",
                    "CódEquipe",
                    "COD_EQUIPE",
                    "ID_TECNICO",
                ],
                "NUM_OS": ["NUM_OS", "NUMERO_OS", "OS", "NUM OS", "ORDEM_SERVICO"],
                "PROJETO": ["PROJETO", "CAMPANHA", "OPERACAO", "CONTRATO_PROJETO"],
                "BASE": ["BASE", "FILIAL", "REGIONAL"],
                "TECNICO": [
                    "NOME EQUIPE",
                    "TECNICO",
                    "NOME",
                    "CódAuxEquipe",
                    "NOME_TECNICO",
                ],
                "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR"],
            },
        )

        # Verifica se DATA foi mapeada
        if "DATA" not in df.columns:
            logger.warning(
                f"Coluna DATA não encontrada! Colunas disponíveis: {list(df.columns)}"
            )
            # Tenta encontrar qualquer coluna que pareça data
            for col in df.columns:
                col_upper = str(col).upper()
                if "DATA" in col_upper or "DT" in col_upper or "DATE" in col_upper:
                    df = df.rename(columns={col: "DATA"})
                    logger.info(f"Coluna '{col}' renomeada para 'DATA'")
                    break

        # Garante que DATA existe
        if "DATA" not in df.columns:
            logger.error("Não foi possível identificar coluna de DATA")
            df["DATA"] = pd.NaT

        return garantir_datetime(df, col="DATA", origem="us"), None

    except Exception as e:
        logger.exception("Falha no download dos registros de Produção")
        return pd.DataFrame(), f"Produção: {type(e).__name__}"


def enriquecer_dados_completos(
    df: pd.DataFrame, hierarquia: pd.DataFrame
) -> pd.DataFrame:
    """Enriquece dados com hierarquia, com validações robustas."""
    # Se df estiver vazio, retorna com colunas normalizadas
    if df.empty:
        return add_norm_cols(df)

    # Se hierarquia estiver vazia, apenas adiciona colunas normais
    if hierarquia.empty:
        logger.warning("Hierarquia vazia, retornando dados sem enriquecimento")
        return add_norm_cols(df)

    df = df.copy()
    hierarquia = hierarquia.copy()

    # Salva colunas originais para preservar
    cols_originais = list(df.columns)
    logger.info(f"Colunas originais antes do enriquecimento: {cols_originais}")

    # Garante que as colunas normalizadas existem
    df = add_norm_cols(df)
    hierarquia = add_norm_cols(hierarquia)

    # Valida se _LOGIN_NORM existe em ambos
    if "_LOGIN_NORM" not in df.columns:
        logger.warning("Coluna _LOGIN_NORM não encontrada no DataFrame principal")
        df["_LOGIN_NORM"] = ""

    if "_LOGIN_NORM" not in hierarquia.columns:
        logger.warning("Coluna _LOGIN_NORM não encontrada na hierarquia")
        hierarquia["_LOGIN_NORM"] = ""

    # Remove linhas com LOGIN vazio da hierarquia
    hierarquia_valida = hierarquia[
        hierarquia["_LOGIN_NORM"].notna()
        & (hierarquia["_LOGIN_NORM"] != "")
        & (hierarquia["_LOGIN_NORM"].str.upper().notna())
        & (~hierarquia["_LOGIN_NORM"].str.upper().isin(["NAN", "NONE", "NA"]))
    ].copy()

    if hierarquia_valida.empty:
        logger.warning("Hierarquia vazia após filtragem de LOGINS válidos")
        return add_norm_cols(df)

    # Remove duplicatas mantendo o primeiro
    hierarquia_valida = hierarquia_valida.drop_duplicates(
        subset=["_LOGIN_NORM"], keep="first"
    )

    # Seleciona apenas colunas necessárias da hierarquia
    cols_hierarchy = ["_LOGIN_NORM"]
    for col in ["TECNICO", "MONITOR", "BASE"]:
        if col in hierarquia_valida.columns:
            cols_hierarchy.append(col)

    lk_login = hierarquia_valida[cols_hierarchy].rename(
        columns={
            c: f"{c}_H" for c in ["TECNICO", "MONITOR", "BASE"] if c in cols_hierarchy
        }
    )

    # Merge com validação - how='left' para preservar todas as linhas do df original
    try:
        dfm = df.merge(lk_login, on="_LOGIN_NORM", how="left")
    except Exception as e:
        logger.error(f"Erro no merge de LOGIN: {e}")
        return add_norm_cols(df)

    # Preenche colunas faltantes com dados da hierarquia
    for c in ["TECNICO", "MONITOR", "BASE"]:
        col_h = f"{c}_H"

        # Garante que a coluna existe
        if c not in dfm.columns:
            dfm[c] = "Não Informado"

        # Identifica valores vazios
        if col_h in dfm.columns:
            vazio = dfm[c].isna() | dfm[c].astype(str).str.strip().isin(
                ["", "nan", "NaN", "None", "NA", "NAN"]
            )
            dfm.loc[vazio, c] = dfm.loc[vazio, col_h]
            dfm = dfm.drop(columns=[col_h])

    # Segundo pass: busca por TÉCNICO se LOGIN não encontrou
    if "_TECNICO_NORM" in df.columns:
        tec_valida = hierarquia_valida[
            hierarquia_valida["_TECNICO_NORM"].notna()
            & (hierarquia_valida["_TECNICO_NORM"] != "")
        ].drop_duplicates(subset=["_TECNICO_NORM"], keep="first")

        if not tec_valida.empty:
            cols_tec = ["_TECNICO_NORM"]
            for col in ["MONITOR", "BASE"]:
                if col in tec_valida.columns:
                    cols_tec.append(col)

            lk_tec = tec_valida[cols_tec].rename(
                columns={c: f"{c}_H2" for c in ["MONITOR", "BASE"] if c in cols_tec}
            )

            try:
                dfm = dfm.merge(lk_tec, on="_TECNICO_NORM", how="left")
            except Exception as e:
                logger.warning(f"Erro no merge de TÉCNICO: {e}")
                return add_norm_cols(dfm.fillna("Não Informado"))

            for c, ch in [("MONITOR", "MONITOR_H2"), ("BASE", "BASE_H2")]:
                if ch in dfm.columns:
                    vazio = dfm[c].isna() | dfm[c].astype(str).str.strip().isin(
                        ["", "nan", "NaN", "None", "NA", "NAN"]
                    )
                    dfm.loc[vazio, c] = dfm.loc[vazio, ch]
                    dfm = dfm.drop(columns=[ch])

    # Preenche todos os nulos restantes
    dfm = dfm.fillna("Não Informado")

    # Verifica se DATA foi preservada
    if "DATA" not in dfm.columns:
        logger.error("Coluna DATA foi perdida no enriquecimento!")
        # Tenta recuperar das colunas originais
        for col in cols_originais:
            if "DATA" in str(col).upper() or "DT" in str(col).upper():
                dfm["DATA"] = df[col]
                logger.info(f"Coluna DATA recuperada de '{col}'")
                break

    # Re-adiciona colunas normalizadas após enriquecimento
    dfm = add_norm_cols(dfm)

    logger.info(f"Colunas após enriquecimento: {list(dfm.columns)}")
    return dfm


# =============================================================================
# Execução das Cargas dos Dados
# =============================================================================
logger.info("Iniciando carga de dados...")

df_hierarquia_raw = carregar_hierarquia()
logger.info(
    f"Hierarquia: {len(df_hierarquia_raw)} registros | Colunas: {list(df_hierarquia_raw.columns)}"
)

df_cons_raw, erro_cons = carregar_consultivos()
logger.info(f"Consultivos: {len(df_cons_raw)} registros | Erro: {erro_cons}")
if not df_cons_raw.empty:
    logger.info(f"Colunas Consultivos: {list(df_cons_raw.columns)}")

df_prod_raw, erro_prod = carregar_producao()
logger.info(f"Produção: {len(df_prod_raw)} registros | Erro: {erro_prod}")
if not df_prod_raw.empty:
    logger.info(f"Colunas Produção: {list(df_prod_raw.columns)}")

if df_hierarquia_raw.empty:
    logger.warning("⚠️ Hierarquia vazia! Verifique a planilha de ativos.")

df_prod = enriquecer_dados_completos(df_prod_raw, df_hierarquia_raw)
df_cons = enriquecer_dados_completos(df_cons_raw, df_hierarquia_raw)

logger.info(f"Produção enriquecida: {len(df_prod)} registros")
logger.info(f"Consultivos enriquecidos: {len(df_cons)} registros")

# Validação crítica de DATA
if not df_prod.empty and "DATA" not in df_prod.columns:
    logger.error(
        "❌ ERRO CRÍTICO: Coluna DATA não encontrada em df_prod após enriquecimento!"
    )

if not df_cons.empty and "DATA" not in df_cons.columns:
    logger.error(
        "❌ ERRO CRÍTICO: Coluna DATA não encontrada em df_cons após enriquecimento!"
    )


# =============================================================================
# Estruturação e Montagem do Sidebar Design System
# =============================================================================
render_sidebar_brand(empresa="TOTALE", segmento="Metas Operacionais")

render_sidebar_info(
    user_name="Administrador",
    email="analise.metas@totale.com.br",
    role="Gestão Operacional",
    avatar="🎯",
)

render_sidebar_section("Status de Conexão")
is_system_ok = (not df_prod.empty) and (not df_cons.empty)
render_sidebar_status(
    status="Online" if is_system_ok else "Offline",
    tipo="ok" if is_system_ok else "critico",
    detalhes={
        "Status": "Online & Integrado" if is_system_ok else "Falha na sincronização"
    },
)

render_sidebar_spacer(altura="medio")
render_sidebar_section("Filtros Consolidados")

all_bases = sorted(
    list(
        set(df_prod["BASE"].dropna().unique()) | set(df_cons["BASE"].dropna().unique())
    )
)
all_monitores = sorted(
    list(
        set(df_prod["MONITOR"].dropna().unique())
        | set(df_cons["MONITOR"].dropna().unique())
    )
)
all_projetos = sorted(
    list(
        set(df_prod["PROJETO"].dropna().unique())
        | set(df_cons["PROJETO"].dropna().unique())
    )
)

filtro_net_opcao = st.sidebar.checkbox(
    "Filtrar Canais Oficiais NET",
    value=False,
    help="Restringe a seleção apenas para NET-ABCDM, NET-LESTE e NET-GUARULHOS",
)

default_proj = (
    [p for p in PROJETOS_NET if p in all_projetos] if filtro_net_opcao else []
)

filtro_projeto = st.sidebar.multiselect(
    "Projeto / Contrato", options=all_projetos, default=default_proj
)
filtro_base = st.sidebar.multiselect("Filial / Regional", options=all_bases)
filtro_monitor = st.sidebar.multiselect("Supervisor / Monitor", options=all_monitores)

# Date Range Picker adaptado para pt-BR
todas_datas = pd.concat([df_prod["DATA"], df_cons["DATA"]]).dropna()
data_min: date = date.today() - timedelta(days=30)
data_max: date = date.today()

if not todas_datas.empty:
    data_min = pd.to_datetime(todas_datas.min()).date()
    data_max = pd.to_datetime(todas_datas.max()).date()

raw_filtro_datas = st.sidebar.date_input(
    "Janela Temporal",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
    format="DD/MM/YYYY",
)

# Unpacking totalmente protegido contra tuplas incompletas
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

render_sidebar_footer_info(versao="v3.0.4")


# =============================================================================
# Lógica de Aplicação de Filtros
# =============================================================================
def filtrar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica filtros ao DataFrame com validação de colunas."""
    if df.empty:
        return df

    # Valida se DATA existe
    if "DATA" not in df.columns:
        logger.warning(
            "Coluna DATA não encontrada, retornando DataFrame sem filtro de data"
        )
        return df

    mask = pd.Series(True, index=df.index)

    if filtro_base:
        mask &= df["BASE"].isin(filtro_base)
    if filtro_monitor:
        mask &= df["MONITOR"].isin(filtro_monitor)
    if filtro_projeto:
        mask &= df["PROJETO"].isin(filtro_projeto)

    if _filtro_datas_safe is not None:
        inicio, fim = _filtro_datas_safe
        sdt = pd.to_datetime(df["DATA"], errors="coerce").dt.normalize()
        mask &= (sdt >= pd.Timestamp(inicio)) & (sdt <= pd.Timestamp(fim))

    return df.loc[mask]


df_prod_f = filtrar_dataframe(df_prod)
df_cons_f = filtrar_dataframe(df_cons)


# =============================================================================
# Visão Geral - Hero e Informações Rápidas
# =============================================================================
_data_inicio_str = (
    formatar_data_br(_filtro_datas_safe[0])
    if _filtro_datas_safe
    else formatar_data_br(data_min)
)
_data_fim_str = (
    formatar_data_br(_filtro_datas_safe[1])
    if _filtro_datas_safe
    else formatar_data_br(data_max)
)

render_hero_totale_2(
    titulo="Painel Consolidado de Metas",
    subtitulo="Visão integrada de O.S. executadas, Consultivos gerados e desempenho individual/coletivo",
    badge_texto=f"Período: {_data_inicio_str} até {_data_fim_str}",
    badge_tipo="info",
)

for err in (erro_prod, erro_cons):
    if err:
        render_insight(f"Atenção na carga de dados: {err}", tipo="alerta")


# =============================================================================
# Criação das Abas Operacionais e Táticas
# =============================================================================
(
    tab_prod,
    tab_cons,
    tab_bases,
    tab_tecnicos,
    tab_monitores,
    tab_heatmap,
    tab_comp,
    tab_alertas,
    tab_abcdm,
    tab_leste,
    tab_guarulhos,
) = st.tabs(
    [
        " Produção",
        "💼 Consultivos",
        "🗂️ Visão Bases",
        "👥 Técnicos",
        "👔 Monitores",
        "️ Heatmap",
        "⚖️ Comparativo",
        "🚨 Alertas",
        "📈 Projeção ABCDM",
        "📈 Projeção LESTE",
        "📈 Projeção GUARULHOS",
    ]
)


# =============================================================================
# Renderização da Aba de Produção O.S.
# =============================================================================
with tab_prod:
    render_section_header(
        titulo="Volume de Produção Geral",
        subtitulo="Acompanhamento de ordens de serviço executadas contra metas globais",
        icone="📊",
    )

    fator, dias_rest, dias_totais, dias_trab = CalculosOperacionais.fator_projecao(
        df_prod_f
    )
    realizado_prod = len(df_prod_f)
    projetado_prod = int(realizado_prod * fator)
    meta_prod_geral = Metas.PRODUCAO_OS_GERAL["meta_base"]

    atingimento_prod = CalculosOperacionais.calcular_atingimento_float(
        realizado_prod, float(meta_prod_geral)
    )
    status_txt, status_cor = resolver_status_atingimento(
        realizado_prod, Metas.PRODUCAO_OS_GERAL
    )

    c1, c2, c3, c4 = st.columns(4)
    render_kpi(
        c1,
        "O.S. Realizadas",
        f"{realizado_prod:,}".replace(",", "."),
        sub=f"Atingimento: {atingimento_prod:.1f}%",
        tema="azul",
    )
    render_kpi(
        c2,
        "Meta Base Mensal",
        f"{meta_prod_geral:,}".replace(",", "."),
        sub=f"Gap atual: {realizado_prod - meta_prod_geral:+,}".replace(",", "."),
        tema="laranja",
    )
    render_kpi(
        c3,
        "Projeção de Fim de Mês",
        f"{projetado_prod:,}".replace(",", "."),
        sub=f"Dias trabalhados: {dias_trab} de {dias_totais}",
        tema="verde",
    )
    render_kpi(
        c4,
        "Status do Período",
        status_txt,
        sub="Análise baseada no ritmo",
        tema="azul" if status_cor == "verde" else "vermelho",
    )

    st.markdown("#### Progresso em relação à Meta Global")
    render_progress_bar(
        valor=float(realizado_prod),
        maximo=float(meta_prod_geral),
        label="Execução de O.S. Totale",
        tema="azul",
    )

    if not df_prod_f.empty and "DATA" in df_prod_f.columns:
        df_evolucao = (
            df_prod_f.dropna(subset=["DATA"])
            .set_index("DATA")
            .resample("D")
            .size()
            .reset_index(name="Volume")
        )
        df_evolucao["Acumulado"] = df_evolucao["Volume"].cumsum()

        fig = px.area(
            df_evolucao,
            x="DATA",
            y="Acumulado",
            title="Histórico Cumulativo de Ordens de Serviço (O.S.)",
        )
        fig.add_hline(
            y=meta_prod_geral,
            line_dash="dash",
            line_color=Cores.SECUNDARIA,
            annotation_text="Meta Nominal",
        )
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Renderização da Aba de Consultivos
# =============================================================================
with tab_cons:
    render_section_header(
        titulo="Gestão de Consultivos",
        subtitulo="Acompanhamento do volume de consultivos criados e finalizados",
        icone="💼",
    )

    fator_c, dias_rest_c, dias_totais_c, dias_trab_c = (
        CalculosOperacionais.fator_projecao(df_cons_f)
    )
    realizado_cons = len(df_cons_f)
    projetado_cons = int(realizado_cons * fator_c)
    meta_cons_geral = Metas.CONSULTIVO_GERAL["meta_base"]

    atingimento_cons = CalculosOperacionais.calcular_atingimento_float(
        realizado_cons, float(meta_cons_geral)
    )
    status_txt_c, status_cor_c = resolver_status_atingimento(
        realizado_cons, Metas.CONSULTIVO_GERAL
    )

    c1, c2, c3, c4 = st.columns(4)
    render_kpi(
        c1,
        "Consultivos Realizados",
        f"{realizado_cons:,}".replace(",", "."),
        sub=f"Atingimento: {atingimento_cons:.1f}%",
        tema="laranja",
    )
    render_kpi(
        c2,
        "Meta Base Mensal",
        f"{meta_cons_geral:,}".replace(",", "."),
        sub=f"Gap atual: {realizado_cons - meta_cons_geral:+,}".replace(",", "."),
        tema="azul",
    )
    render_kpi(
        c3,
        "Projeção para o Período",
        f"{projetado_cons:,}".replace(",", "."),
        sub=f"Dias restantes: {dias_rest_c} úteis",
        tema="verde",
    )
    render_kpi(
        c4,
        "Status Operacional",
        status_txt_c,
        sub="Valoração nominal",
        tema="azul" if status_cor_c == "verde" else "vermelho",
    )

    st.markdown("#### Progresso de Consultivos")
    render_progress_bar(
        valor=float(realizado_cons),
        maximo=float(meta_cons_geral),
        label="Meta de Consultivos",
        tema="laranja",
    )


# =============================================================================
# Processamento de Dados Consolidados por Base (Type-Safe)
# =============================================================================
def processar_resumo_bases(prod: pd.DataFrame, cons: pd.DataFrame) -> pd.DataFrame:
    """Processa resumo consolidado por base/filial."""
    if not prod.empty:
        a = (
            prod.groupby("_BASE_NORM", dropna=False)
            .agg(
                Base=("BASE", "first"),
                OS_Volume=("DATA", "size"),
                Max_Data_OS=("DATA", "max"),
            )
            .reset_index()
        )
    else:
        a = pd.DataFrame(columns=["_BASE_NORM", "Base", "OS_Volume", "Max_Data_OS"])

    if not cons.empty:
        b = (
            cons.groupby("_BASE_NORM", dropna=False)
            .agg(
                Base_C=("BASE", "first"),
                Cons_Volume=("DATA", "size"),
                Max_Data_Cons=("DATA", "max"),
            )
            .reset_index()
        )
    else:
        b = pd.DataFrame(
            columns=["_BASE_NORM", "Base_C", "Cons_Volume", "Max_Data_Cons"]
        )

    m = pd.merge(a, b, on="_BASE_NORM", how="outer")

    fallback_base = m["Base_C"] if "Base_C" in m.columns else pd.Series(dtype=str)
    m["Base"] = m["Base"].fillna(fallback_base).fillna("Não Informado")
    if "Base_C" in m.columns:
        m = m.drop(columns=["Base_C"])

    m["OS_Volume"] = m["OS_Volume"].fillna(0).astype(int)
    m["Cons_Volume"] = m["Cons_Volume"].fillna(0).astype(int)

    proj_os: list[int] = []
    proj_cons: list[int] = []
    max_data_os_br: list[str] = []
    max_data_cons_br: list[str] = []

    for _, row in m.iterrows():
        dt_os = row.get("Max_Data_OS")
        if pd.notna(dt_os):
            f_os, _, _, _ = CalculosOperacionais.fator_por_data_max(
                cast(pd.Timestamp, dt_os).date()
            )
            max_data_os_br.append(formatar_data_br(dt_os))
        else:
            f_os = 1.0
            max_data_os_br.append("-")

        dt_cons = row.get("Max_Data_Cons")
        if pd.notna(dt_cons):
            f_cons, _, _, _ = CalculosOperacionais.fator_por_data_max(
                cast(pd.Timestamp, dt_cons).date()
            )
            max_data_cons_br.append(formatar_data_br(dt_cons))
        else:
            f_cons = 1.0
            max_data_cons_br.append("-")

        proj_os.append(int(_to_float_safe(row.get("OS_Volume")) * f_os))
        proj_cons.append(int(_to_float_safe(row.get("Cons_Volume")) * f_cons))

    m["O.S. Projetadas"] = pd.Series(proj_os, dtype=int)
    m["Consultivos Projetados"] = pd.Series(proj_cons, dtype=int)
    m["Última O.S."] = max_data_os_br
    m["Último Consultivo"] = max_data_cons_br

    m["% Meta O.S. (Proj)"] = np.round(
        CalculosOperacionais.calcular_atingimento_series(
            m["O.S. Projetadas"], float(Metas.PRODUCAO_OS_BASE["meta_base"])
        ),
        1,
    )
    m["% Meta Cons. (Proj)"] = np.round(
        CalculosOperacionais.calcular_atingimento_series(
            m["Consultivos Projetados"], float(Metas.CONSULTIVO_BASE["meta_base"])
        ),
        1,
    )

    return m.sort_values("Base").reset_index(drop=True)


df_resumo_base = processar_resumo_bases(df_prod_f, df_cons_f)


# =============================================================================
# Renderização da Aba de Visão Geral por Base
# =============================================================================
with tab_bases:
    render_section_header(
        titulo="Comparativo por Filiais",
        subtitulo="Informações consolidadas e integridade física de produção e metas por regional",
        icone="🗂️",
    )

    k1, k2, k3, k4 = st.columns(4)
    render_kpi_sm(
        k1,
        "Regionais Operantes",
        str(len(df_resumo_base)),
        "Ativas no ciclo atual",
        "azul",
        icone="🏢",
    )
    render_kpi_sm(
        k2,
        "Volume Acumulado O.S.",
        f"{df_resumo_base['OS_Volume'].sum():,}".replace(",", "."),
        "Soma de filiais",
        "verde",
        icone="📈",
    )
    render_kpi_sm(
        k3,
        "Volume Acumulado Cons.",
        f"{df_resumo_base['Cons_Volume'].sum():,}".replace(",", "."),
        "Soma de filiais",
        "laranja",
        icone="💼",
    )
    render_kpi_sm(
        k4,
        "Regionais Prioritárias",
        str(len(BASES_PRIORITARIAS)),
        "NET ABCDM/LESTE/GRU",
        "roxo",
        icone="⭐",
    )

    st.markdown("#### Canais Prioritários de Metas da Operação")
    cards = st.columns(len(BASES_PRIORITARIAS))

    for col, b_nome in zip(cards, BASES_PRIORITARIAS):
        with col:
            b_data = df_resumo_base[
                df_resumo_base["Base"].astype(str).str.upper() == b_nome.upper()
            ]
            if not b_data.empty:
                os_v = (
                    f"{int(_to_float_safe(b_data['OS_Volume'].values[0])):,}".replace(
                        ",", "."
                    )
                )
                cons_v = (
                    f"{int(_to_float_safe(b_data['Cons_Volume'].values[0])):,}".replace(
                        ",", "."
                    )
                )
                os_proj_v = f"{int(_to_float_safe(b_data['O.S. Projetadas'].values[0])):,}".replace(
                    ",", "."
                )
                cons_proj_v = f"{int(_to_float_safe(b_data['Consultivos Projetados'].values[0])):,}".replace(
                    ",", "."
                )

                st.markdown(
                    f"""
                    <div style="background-color: white; border: 1px solid #E2E8F0; border-top: 4px solid {Cores.SECUNDARIA}; border-radius: 8px; padding: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                        <h4 style="color: {Cores.PRIMARIA}; margin-top: 0; margin-bottom: 12px; font-weight: 800;">{b_nome}</h4>
                        <div style="font-size: 13px; line-height: 1.6; color: #374151;">
                            <div><strong>Produção Real:</strong> {os_v} O.S.</div>
                            <div style="margin-bottom: 8px;"><strong>Projeção:</strong> {os_proj_v} O.S.</div>
                            <div><strong>Consultivos Real:</strong> {cons_v}</div>
                            <div><strong>Projeção:</strong> {cons_proj_v}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"**{b_nome}** sem dados no período")

    st.markdown("#### Consolidação Geral das Regionais")
    df_tabela_bases = df_resumo_base[
        [
            "Base",
            "OS_Volume",
            "O.S. Projetadas",
            "% Meta O.S. (Proj)",
            "Última O.S.",
            "Cons_Volume",
            "Consultivos Projetados",
            "% Meta Cons. (Proj)",
            "Último Consultivo",
        ]
    ].rename(
        columns={
            "Base": "Filial",
            "OS_Volume": "O.S. Real",
            "Cons_Volume": "Cons. Real",
        }
    )

    render_table_html(
        df_tabela_bases,
        fmt={
            "O.S. Real": "{:,.0f}",
            "O.S. Projetadas": "{:,.0f}",
            "% Meta O.S. (Proj)": "{:.1f}%",
            "Cons. Real": "{:,.0f}",
            "Consultivos Projetados": "{:,.0f}",
            "% Meta Cons. (Proj)": "{:.1f}%",
        },
        colunas_num=[
            "O.S. Real",
            "O.S. Projetadas",
            "Cons. Real",
            "Consultivos Projetados",
        ],
    )


# =============================================================================
# Dashboard de Técnicos
# =============================================================================
with tab_tecnicos:
    render_section_header(
        titulo="Desempenho Individual dos Técnicos",
        subtitulo="Análise de produção e ranking de performance operacional",
        icone="👥",
        badge="Métrica Individual",
        badge_tipo="info",
    )

    if df_prod_f.empty and df_cons_f.empty:
        render_empty_state(
            tipo="dados",
            titulo="Sem dados de técnicos",
            descricao="Ajuste os filtros de data e filial.",
        )
    else:
        df_prod_tec = (
            df_prod_f.groupby(["TECNICO", "BASE", "MONITOR"], dropna=False)
            .size()
            .reset_index(name="OS")
        )
        df_cons_tec = (
            df_cons_f.groupby(["TECNICO", "BASE", "MONITOR"], dropna=False)
            .size()
            .reset_index(name="Consultivos")
        )

        df_tec_perf = pd.merge(
            df_prod_tec, df_cons_tec, on=["TECNICO", "BASE", "MONITOR"], how="outer"
        ).fillna(0)
        df_tec_perf["OS"] = df_tec_perf["OS"].astype(int)
        df_tec_perf["Consultivos"] = df_tec_perf["Consultivos"].astype(int)
        df_tec_perf["Score Produtividade"] = df_tec_perf["OS"] + (
            df_tec_perf["Consultivos"] * 15
        )
        df_tec_perf = df_tec_perf.sort_values(
            by="Score Produtividade", ascending=False
        ).reset_index(drop=True)
        df_tec_perf["Posição"] = df_tec_perf.index + 1

        tk1, tk2, tk3, tk4 = st.columns(4)
        render_kpi_sm(
            tk1,
            "Total de Técnicos Ativos",
            str(len(df_tec_perf)),
            "No período filtrado",
            "azul",
            icone="👷",
        )
        render_kpi_sm(
            tk2,
            "Média de O.S. por Técnico",
            f"{_to_float_safe(df_tec_perf['OS'].mean()):.1f}",
            "Média aritmética",
            "verde",
            icone="📊",
        )
        render_kpi_sm(
            tk3,
            "Média de Consultivos",
            f"{_to_float_safe(df_tec_perf['Consultivos'].mean()):.1f}",
            "Média aritmética",
            "laranja",
            icone="💼",
        )
        melhor_tecnico = (
            df_tec_perf.iloc[0]["TECNICO"] if not df_tec_perf.empty else "N/A"
        )
        render_kpi_sm(
            tk4,
            "Destaque do Mês",
            str(melhor_tecnico)[:18],
            "Maior Score do período",
            "roxo",
            icone="🏆",
        )

        st.divider()

        col_top, col_bot = st.columns(2)
        with col_top:
            st.markdown("##### 🏆 Top 10 Técnicos (Maior Produção)")
            df_top10 = df_tec_perf.head(10)
            fig_top = px.bar(
                df_top10,
                x="Score Produtividade",
                y="TECNICO",
                orientation="h",
                text="Score Produtividade",
                color="Score Produtividade",
                color_continuous_scale=["#FDBA74", "#012869"],
            )
            fig_top.update_layout(
                yaxis={"categoryorder": "total ascending"}, height=360, showlegend=False
            )
            st.plotly_chart(fig_top, use_container_width=True)

        with col_bot:
            st.markdown("##### ⚠️ Alerta de Baixa Produtividade (Bottom 10)")
            df_bot10 = df_tec_perf.tail(10).sort_values(
                by="Score Produtividade", ascending=True
            )
            fig_bot = px.bar(
                df_bot10,
                x="Score Produtividade",
                y="TECNICO",
                orientation="h",
                text="Score Produtividade",
                color="Score Produtividade",
                color_continuous_scale=["#FCA5A5", "#DC2626"],
            )
            fig_bot.update_layout(height=360, showlegend=False)
            st.plotly_chart(fig_bot, use_container_width=True)

        st.markdown("#### Busca Ativa de Colaboradores")
        busca_nome = st.text_input(
            "Filtrar por nome do Colaborador:", key="busca_tec_completa"
        )

        df_display_tec = df_tec_perf.copy()
        if busca_nome:
            df_display_tec = df_display_tec[
                df_display_tec["TECNICO"]
                .astype(str)
                .str.contains(busca_nome, case=False, na=False)
            ]

        if not df_display_tec.empty:
            q25 = float(df_tec_perf["Score Produtividade"].quantile(0.25))
            q75 = float(df_tec_perf["Score Produtividade"].quantile(0.75))

            def classificar_desempenho(score: Any) -> str:
                s_f = _to_float_safe(score)
                if s_f >= q75:
                    return "🟢 Alta Performance"
                if s_f >= q25:
                    return "🟡 Produtividade Média"
                return "🔴 Necessita Atenção"

            df_display_tec["Classificação"] = df_display_tec[
                "Score Produtividade"
            ].apply(classificar_desempenho)
            render_table_html(
                df_display_tec[
                    [
                        "Posição",
                        "TECNICO",
                        "BASE",
                        "MONITOR",
                        "OS",
                        "Consultivos",
                        "Score Produtividade",
                        "Classificação",
                    ]
                ].rename(
                    columns={
                        "TECNICO": "Técnico",
                        "BASE": "Filial",
                        "MONITOR": "Supervisor",
                        "OS": "O.S. Realizadas",
                    }
                ),
                fmt={
                    "O.S. Realizadas": "{:,.0f}",
                    "Consultivos": "{:,.0f}",
                    "Score Produtividade": "{:,.0f}",
                },
                colunas_num=["O.S. Realizadas", "Consultivos", "Score Produtividade"],
            )


# =============================================================================
# Dashboard de Monitores/Supervisores
# =============================================================================
with tab_monitores:
    render_section_header(
        titulo="Desempenho por Supervisor",
        subtitulo="Visão consolidada das equipes sob a gestão de cada monitor",
        icone="👔",
    )

    if df_prod_f.empty and df_cons_f.empty:
        render_empty_state(
            tipo="dados",
            titulo="Sem dados de supervisão",
            descricao="Ajuste os filtros globais.",
        )
    else:
        df_mon_prod = (
            df_prod_f.groupby("MONITOR", dropna=False)
            .agg(OS_Equipe=("DATA", "size"), Tecnicos_Ativos=("TECNICO", "nunique"))
            .reset_index()
        )
        df_mon_cons = (
            df_cons_f.groupby("MONITOR", dropna=False)
            .size()
            .reset_index(name="Cons_Equipe")
        )

        df_mon_perf = pd.merge(
            df_mon_prod, df_mon_cons, on="MONITOR", how="outer"
        ).fillna(0)
        df_mon_perf["OS_Equipe"] = df_mon_perf["OS_Equipe"].astype(int)
        df_mon_perf["Cons_Equipe"] = df_mon_perf["Cons_Equipe"].astype(int)
        df_mon_perf["Tecnicos_Ativos"] = df_mon_perf["Tecnicos_Ativos"].astype(int)
        df_mon_perf["Média O.S. por Técnico"] = np.round(
            np.where(
                df_mon_perf["Tecnicos_Ativos"] > 0,
                df_mon_perf["OS_Equipe"] / df_mon_perf["Tecnicos_Ativos"],
                0.0,
            ),
            1,
        )
        df_mon_perf = df_mon_perf.sort_values(
            by="OS_Equipe", ascending=False
        ).reset_index(drop=True)

        mk1, mk2, mk3, mk4 = st.columns(4)
        render_kpi_sm(
            mk1,
            "Monitores Operando",
            str(len(df_mon_perf)),
            "Com dados no período",
            "azul",
            icone="👔",
        )
        render_kpi_sm(
            mk2,
            "O.S. sob Gestão",
            f"{df_mon_perf['OS_Equipe'].sum():,}".replace(",", "."),
            "Total realizado",
            "verde",
            icone="",
        )
        render_kpi_sm(
            mk3,
            "Consultivos sob Gestão",
            f"{df_mon_perf['Cons_Equipe'].sum():,}".replace(",", "."),
            "Total realizado",
            "laranja",
            icone="💼",
        )
        melhor_mon = df_mon_perf.iloc[0]["MONITOR"] if not df_mon_perf.empty else "N/A"
        render_kpi_sm(
            mk4,
            "Equipe com maior volume",
            str(melhor_mon)[:18],
            "Maior volume total de O.S.",
            "roxo",
            icone="🌟",
        )

        st.markdown("#### Produção por Supervisor")
        fig_mon = px.bar(
            df_mon_perf,
            x="MONITOR",
            y="OS_Equipe",
            text="OS_Equipe",
            title="Distribuição Absoluta de O.S. por Equipe",
            color="Média O.S. por Técnico",
            color_continuous_scale="Viridis",
            labels={
                "OS_Equipe": "Total de O.S.",
                "Média O.S. por Técnico": "Média per Capita",
            },
        )
        fig_mon.update_layout(height=350, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_mon, use_container_width=True)

        st.markdown("#### Matriz Consolidada de Supervisão")
        render_table_html(
            df_mon_perf.rename(
                columns={
                    "MONITOR": "Supervisor",
                    "OS_Equipe": "O.S. Totais",
                    "Tecnicos_Ativos": "Qtd Técnicos Ativos",
                    "Cons_Equipe": "Consultivos Totais",
                }
            ),
            fmt={
                "O.S. Totais": "{:,.0f}",
                "Qtd Técnicos Ativos": "{:,.0f}",
                "Consultivos Totais": "{:,.0f}",
                "Média O.S. por Técnico": "{:.1f}",
            },
            colunas_num=[
                "O.S. Totais",
                "Qtd Técnicos Ativos",
                "Consultivos Totais",
                "Média O.S. por Técnico",
            ],
        )


# =============================================================================
# Dashboard de Heatmap Temporal
# =============================================================================
with tab_heatmap:
    render_section_header(
        titulo="Sazonalidade e Comportamento Temporal",
        subtitulo="Análise de calor de produção cruzando semanas e dias da semana úteis",
        icone="🗓️",
    )

    if df_prod_f.empty:
        render_empty_state(
            tipo="dados",
            titulo="Dados temporais indisponíveis",
            descricao="Ajuste os filtros de data.",
        )
    else:
        df_heat = df_prod_f.dropna(subset=["DATA"]).copy()

        dias_semana_mapeados = {
            0: "1-Segunda",
            1: "2-Terça",
            2: "3-Quarta",
            3: "4-Quinta",
            4: "5-Sexta",
            5: "6-Sábado",
            6: "7-Domingo",
        }
        df_heat["Dia_Semana"] = df_heat["DATA"].dt.dayofweek.map(dias_semana_mapeados)
        df_heat["Semana_Ano"] = df_heat["DATA"].dt.isocalendar().week.astype(str)

        pivot_heat = (
            df_heat.groupby(["Semana_Ano", "Dia_Semana"])
            .size()
            .reset_index(name="Volume_OS")
        )
        pivot_heat_matrix = pivot_heat.pivot(
            index="Semana_Ano", columns="Dia_Semana", values="Volume_OS"
        ).fillna(0)

        st.markdown(
            "##### 🌋 Mapa de Calor de Produção (Semanas do Ano × Dias da Semana)"
        )
        fig_heat = px.imshow(
            pivot_heat_matrix,
            labels=dict(x="Dia da Semana", y="Semana do Ano", color="O.S. Realizadas"),
            x=pivot_heat_matrix.columns,
            y=pivot_heat_matrix.index,
            color_continuous_scale="Plasma",
            text_auto=True,
        )
        fig_heat.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)

        st.markdown("##### 📊 Distribuição Consolidada de Volume por Dia Útil")
        df_dia_util_agg = (
            df_heat.groupby("Dia_Semana").size().reset_index(name="Volume_OS")
        )
        fig_dia_util = px.bar(
            df_dia_util_agg,
            x="Dia_Semana",
            y="Volume_OS",
            text="Volume_OS",
            color="Volume_OS",
            color_continuous_scale="Blues",
        )
        fig_dia_util.update_layout(
            height=300, margin=dict(l=10, r=10, t=40, b=10), showlegend=False
        )
        st.plotly_chart(fig_dia_util, use_container_width=True)


# =============================================================================
# Dashboard Comparativo Lado a Lado
# =============================================================================
with tab_comp:
    render_section_header(
        titulo="Comparativo entre Regionais",
        subtitulo="Cruzamento estatístico e proporcional de filiais",
        icone="⚖️",
    )

    if len(df_resumo_base) < 2:
        render_empty_state(
            tipo="dados",
            titulo="Poucos dados para comparação",
            descricao="Mantenha mais de uma filial ativa nos filtros globais.",
        )
    else:
        st.markdown("#####  Eficiência Radar das Regionais (Normalizado)")
        fig_radar = go.Figure()
        top_bases_radar = df_resumo_base.nlargest(5, "OS_Volume")

        for _, row in top_bases_radar.iterrows():
            ating_os_norm = min(_to_float_safe(row.get("% Meta O.S. (Proj)")), 150.0)
            ating_cons_norm = min(_to_float_safe(row.get("% Meta Cons. (Proj)")), 150.0)
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=[ating_os_norm, ating_cons_norm, ating_os_norm],
                    theta=["Meta O.S.", "Meta Consultivo", "Meta O.S."],
                    fill="toself",
                    name=str(row.get("Base", "")),
                )
            )

        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 150])),
            showlegend=True,
            height=380,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        st.markdown(
            "##### 📈 Correlação: Volume de O.S. × Volume de Consultivos por Regional"
        )
        fig_scatter = px.scatter(
            df_resumo_base,
            x="OS_Volume",
            y="Cons_Volume",
            size="O.S. Projetadas",
            color="Base",
            hover_name="Base",
            text="Base",
            labels={
                "OS_Volume": "Volume Real de O.S.",
                "Cons_Volume": "Volume Real de Consultivos",
            },
        )
        fig_scatter.update_traces(textposition="top center")
        fig_scatter.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_scatter, use_container_width=True)


# =============================================================================
# Dashboard de Alertas Inteligentes
# =============================================================================
with tab_alertas:
    render_section_header(
        titulo="Central de Alertas e Anomalias",
        subtitulo="Auditoria de integridade física de metas e produtividade individual",
        icone="🚨",
        badge="Auditoria Inteligente",
        badge_tipo="erro",
    )

    alertas_criticos: list[str] = []
    alertas_atencao: list[str] = []

    for _, row in df_resumo_base.iterrows():
        b_nome = str(row.get("Base", ""))
        os_proj = _to_float_safe(row.get("O.S. Projetadas"))
        meta_min = float(Metas.PRODUCAO_OS_BASE["minima"])
        if os_proj < meta_min:
            os_proj_str = f"{os_proj:,.0f}".replace(",", ".")
            meta_min_str = f"{meta_min:,.0f}".replace(",", ".")
            alertas_criticos.append(
                f"**{b_nome}** possui projeção mensal de **{os_proj_str} O.S.**, valor abaixo da meta mínima aceitável de **{meta_min_str} O.S.**"
            )
        elif os_proj < float(Metas.PRODUCAO_OS_BASE["meta_base"]):
            os_proj_str = f"{os_proj:,.0f}".replace(",", ".")
            alertas_atencao.append(
                f"**{b_nome}** está projetando **{os_proj_str} O.S.**, risco moderado de não atingir a meta base."
            )

    if not df_prod_f.empty and "DATA" in df_prod_f.columns:
        data_corte = pd.Timestamp(date.today() - timedelta(days=4))
        tecnicos_produzindo = set(
            df_prod_f[df_prod_f["DATA"] >= data_corte]["TECNICO"].dropna().unique()
        )
        tecnicos_totais = set(df_prod_f["TECNICO"].dropna().unique())
        tecnicos_ausentes = tecnicos_totais - tecnicos_produzindo
        tecnicos_ausentes = {
            t for t in tecnicos_ausentes if str(t).upper() != "NÃO INFORMADO"
        }

        if len(tecnicos_ausentes) > 0:
            alertas_atencao.append(
                f"Detectamos **{len(tecnicos_ausentes)} técnico(s) ativo(s)** sem qualquer registro de O.S. nos últimos 4 dias úteis."
            )

    if not df_prod_f.empty and "DATA" in df_prod_f.columns:
        df_diario = (
            df_prod_f.dropna(subset=["DATA"]).groupby(df_prod_f["DATA"].dt.date).size()
        )
        if len(df_diario) >= 10:
            media_recente = float(df_diario.tail(3).mean())
            media_anterior = float(df_diario.iloc[-10:-3].mean())
            if media_anterior > 0 and media_recente < media_anterior * 0.75:
                queda_pct = (1.0 - (media_recente / media_anterior)) * 100.0
                alertas_criticos.append(
                    f"**Alerta de Ritmo:** Queda abrupta de **{queda_pct:.1f}%** na média diária de produção de O.S. nos últimos 3 dias."
                )

    ak1, ak2 = st.columns(2)
    render_kpi_sm(
        ak1,
        "Alertas Críticos (Ação Imediata)",
        str(len(alertas_criticos)),
        "Risco alto de perda de metas",
        "vermelho",
        icone="🔴",
    )
    render_kpi_sm(
        ak2,
        "Alertas de Atenção",
        str(len(alertas_atencao)),
        "Desvios operacionais leves",
        "laranja",
        icone="🟡",
    )

    st.markdown("#### Detalhamento de Ocorrências")
    if alertas_criticos:
        st.markdown("##### 🔴 Ocorrências Críticas")
        for alerta in alertas_criticos:
            render_insight(alerta, tipo="critico")

    if alertas_atencao:
        st.markdown("##### 🟡 Ocorrências de Monitoramento")
        for alerta in alertas_atencao:
            render_insight(alerta, tipo="alerta")

    if not alertas_criticos and not alertas_atencao:
        render_empty_state(
            tipo="padrao",
            titulo="Operação Saudável",
            descricao="Nenhum desvio ou anomalia operacional detectada nas bases ativas.",
            icone="🟢",
        )


# =============================================================================
# Renderização das Abas Individuais com Projeções e Simuladores
# =============================================================================
def render_aba_individual_base(tab: DeltaGenerator, base_nome: str) -> None:
    """Renderiza aba individual de projeção por base."""
    with tab:
        render_section_header(
            titulo=f"Projeções — {base_nome}",
            subtitulo="Lógica de projeção matemática baseada no calendário Seg-Sáb",
            icone="📈",
        )

        b_data = df_resumo_base[
            df_resumo_base["Base"].astype(str).str.upper() == base_nome.upper()
        ]

        if b_data.empty:
            render_empty_state(
                tipo="dados",
                titulo="Sem dados para esta regional",
                descricao="Verifique se a filial está ativa nos filtros da barra lateral.",
            )
            return

        os_real = _to_float_safe(b_data["OS_Volume"].values[0])
        cons_real = _to_float_safe(b_data["Cons_Volume"].values[0])
        os_proj = _to_float_safe(b_data["O.S. Projetadas"].values[0])
        cons_proj = _to_float_safe(b_data["Consultivos Projetados"].values[0])

        meta_os_b = float(Metas.PRODUCAO_OS_BASE["meta_base"])
        meta_cons_b = float(Metas.CONSULTIVO_BASE["meta_base"])

        ating_os = CalculosOperacionais.calcular_atingimento_float(os_proj, meta_os_b)
        ating_cons = CalculosOperacionais.calcular_atingimento_float(
            cons_proj, meta_cons_b
        )

        c1, c2, c3, c4 = st.columns(4)
        render_kpi(
            c1,
            "Projeção O.S. Mensal",
            f"{os_proj:,.0f}".replace(",", "."),
            sub=f"Atingimento: {ating_os:.1f}%",
            tema="azul",
        )
        render_kpi(
            c2,
            "Projeção Consultivos",
            f"{cons_proj:,.0f}".replace(",", "."),
            sub=f"Atingimento: {ating_cons:.1f}%",
            tema="laranja",
        )
        render_kpi(
            c3,
            "Falta para Meta (O.S.)",
            f"{max(0.0, meta_os_b - os_proj):,.0f}".replace(",", "."),
            sub=f"Meta nominal: {meta_os_b:,.0f}".replace(",", "."),
            tema="verde" if os_proj >= meta_os_b else "vermelho",
        )
        render_kpi(
            c4,
            "Falta para Meta (Cons.)",
            f"{max(0.0, meta_cons_b - cons_proj):,.0f}".replace(",", "."),
            sub=f"Meta nominal: {meta_cons_b:,.0f}".replace(",", "."),
            tema="verde" if cons_proj >= meta_cons_b else "vermelho",
        )

        st.markdown("#### 🛠️ Simulador de Ritmo Operacional")
        _, dias_faltantes, dias_totais, _ = CalculosOperacionais.fator_projecao(
            df_prod_f
        )

        if dias_faltantes > 0:
            gap_os = max(0.0, meta_os_b - os_real)
            dias_decorridos = float(dias_totais - dias_faltantes)
            ritmo_atual = os_real / dias_decorridos if dias_decorridos > 0 else 0.0
            ritmo_necessario = gap_os / float(dias_faltantes)

            st.write(
                f"Dias úteis restantes no mês (Seg–Sáb): **{dias_faltantes} dias**"
            )
            st.write(f"Ritmo atual da equipe: **{ritmo_atual:.1f} O.S./dia**")

            if ritmo_necessario > ritmo_atual:
                render_insight(
                    f"A equipe precisa acelerar a produção de **{ritmo_atual:.1f} O.S./dia** para **{ritmo_necessario:.1f} O.S./dia** para bater a meta do mês.",
                    tipo="alerta",
                )
            else:
                render_insight(
                    "Mantendo o ritmo atual, a meta mensal de produção de O.S. será atingida com sucesso!",
                    tipo="ok",
                )
        else:
            render_insight(
                "Ciclo mensal encerrado. Aguardando abertura do próximo período operacional.",
                tipo="info",
            )


render_aba_individual_base(tab_abcdm, "NET-ABCDM")
render_aba_individual_base(tab_leste, "NET-LESTE")
render_aba_individual_base(tab_guarulhos, "NET-GUARULHOS")

# Exibição dos DataFrames finais formatando datas no padrão pt-BR (DD/MM/AAAA)
st.dataframe(
    formatar_df_para_exibicao(df_cons_f), use_container_width=True, hide_index=True
)
st.dataframe(
    formatar_df_para_exibicao(df_prod_f), use_container_width=True, hide_index=True
)
