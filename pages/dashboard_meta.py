"""
dashboard_meta.py
=================
Dashboard de Metas Operacionais - TOTALE
Integração Completa: Produção + Consultivo (CSV via gdown) + Hierarquia
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote as url_quote
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection

try:
    import gdown
except ImportError:
    gdown = None

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Dashboard de Metas | TOTALE",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════
# CORES E DESIGN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

FONTE_TITULO = "'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif"
FONTE_TEXTO = "'IBM Plex Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

COR_PRIMARIA = "#012869"
COR_SECUNDARIA = "#F37C04"
COR_SUCESSO = "#059669"
COR_ALERTA = "#DC2626"
COR_ATENCAO = "#F59E0B"
COR_NEUTRO = "#64748B"
COR_FUNDO_CARD = "#FFFFFF"
COR_BORDA = "#E2E8F0"
COR_TEXTO = "#1F2937"
COR_TEXTO_3 = "#6B7280"

SB_FUNDO = "#F8FAFC"
SB_BORDA_SUTIL = "#E2E8F0"

_TEMA_CORES: Dict[str, str] = {
    "azul": COR_PRIMARIA,
    "verde": COR_SUCESSO,
    "vermelho": COR_ALERTA,
    "laranja": COR_SECUNDARIA,
    "cinza": COR_NEUTRO,
}

CACHE_TTL_PRODUCAO = 300
CACHE_TTL_CONSULTIVO = 600
CACHE_TTL_METAS = 3600

# Fallback se o módulo de componentes existir
try:
    from components.componentes import COR_TEXTO as _CT, COR_TEXTO_3 as _CT3

    COR_TEXTO = _CT
    COR_TEXTO_3 = _CT3
except Exception:
    pass

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES E METAS
# ═══════════════════════════════════════════════════════════════════════════


class Configuracoes:
    # Planilha lista_ativos (Hierarquia)
    URL_ATIVOS = (
        "https://docs.google.com/spreadsheets/d/"
        "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    )
    SHEET_ID_ATIVOS = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    SHEET_ABA_ATIVOS = "lista_ativos"  # nome da aba

    SHEET_ID_PROD = "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
    SHEET_ABA_PROD = "Prod"
    DRIVE_ID_CONS = "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"

    TIMEOUT = 30
    TZ = ZoneInfo("America/Sao_Paulo")


class ObjetivosOperacao:
    PRODUCAO_OS_PROJETO = {"minima": 7_000, "meta_base": 10_000, "alta_perf": 11_000}
    CONSULTIVO_PROJETO = {"minima": 367, "meta_base": 525, "alta_perf": 580}
    PRODUCAO_OS_GERAL = {"minima": 21_000, "meta_base": 30_000, "alta_perf": 33_000}
    CONSULTIVO_GERAL = {"minima": 1_102, "meta_base": 1_575, "alta_perf": 1_732}


# ═══════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS DE COLUNAS (corrige duplicate keys / .str em DataFrame)
# ═══════════════════════════════════════════════════════════════════════════


def normalizar_texto(texto: Any) -> str:
    if pd.isna(texto):
        return ""
    txt = str(texto).strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    ).upper()


def _primeira_serie(df: pd.DataFrame, col: str) -> Optional[pd.Series]:
    """Se houver colunas duplicadas com o mesmo nome, devolve só a primeira Series."""
    if col not in df.columns:
        return None
    obj = df[col]
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def deduplicar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Remove colunas com nome repetido (mantém a primeira)."""
    if df.columns.is_unique:
        return df
    return df.loc[:, ~df.columns.duplicated(keep="first")].copy()


def mapear_colunas(df: pd.DataFrame, regras: Dict[str, List[str]]) -> pd.DataFrame:
    """
    Renomeia colunas de forma 1:1 (sem gerar nomes duplicados).

    regras = {
        "DATA": ["DATA", "DT_CRIACAO", "DT", "EXECUCAO", "CRIACAO"],
        "LOGIN": ["LOGIN", "USUARIO", "USER", "MATRICULA"],
        ...
    }
    Prioridade: ordem da lista de aliases (primeiro match ganha).
    Cada destino só é atribuído uma vez.
    """
    if df.empty:
        return df

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # destino -> coluna original
    destino_para_origem: Dict[str, str] = {}
    origem_usada: set[str] = set()

    colunas_norm = {c: normalizar_texto(c) for c in df.columns}

    for destino, aliases in regras.items():
        if destino in destino_para_origem:
            continue
        aliases_norm = [normalizar_texto(a) for a in aliases]

        # 1) match exato pelo alias
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

        # 2) match por "contém", do alias mais específico (mais longo) ao menor
        if destino not in destino_para_origem:
            for alias in sorted(aliases_norm, key=len, reverse=True):
                if len(alias) < 2:
                    continue
                for orig, cn in colunas_norm.items():
                    if orig in origem_usada:
                        continue
                    # evita match fraco demais (ex.: "OS" dentro de "POSICAO")
                    if alias == "OS":
                        if (
                            cn == "OS"
                            or cn.startswith("OS_")
                            or cn.endswith("_OS")
                            or "NUMERO_OS" in cn
                            or "NUM_OS" in cn
                            or "N_OS" in cn
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

    return deduplicar_colunas(df)


def garantir_datetime(df: pd.DataFrame, col: str = "DATA") -> pd.DataFrame:
    if col not in df.columns:
        return df
    s = _primeira_serie(df, col)
    if s is None:
        return df
    df = deduplicar_colunas(df)
    df[col] = pd.to_datetime(s, errors="coerce", dayfirst=True)
    return df


def garantir_login(df: pd.DataFrame, col: str = "LOGIN") -> pd.DataFrame:
    if col not in df.columns:
        return df
    s = _primeira_serie(df, col)
    if s is None:
        return df
    df = deduplicar_colunas(df)
    df[col] = (
        s.astype(str)
        .str.strip()
        .str.upper()
        .replace({"NAN": pd.NA, "NONE": pd.NA, "": pd.NA})
    )
    return df


# ═══════════════════════════════════════════════════════════════════════════
# CÁLCULOS E REGRAS DE NEGÓCIO
# ═══════════════════════════════════════════════════════════════════════════


class Calculos:
    @staticmethod
    def variacao(valor: float, meta: float) -> str:
        if meta == 0 or pd.isna(meta):
            return "N/A"
        pct = ((valor - meta) / meta) * 100
        return f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"

    @staticmethod
    def share(valor: float, geral: float) -> str:
        if geral == 0 or pd.isna(geral) or abs(valor - geral) < 0.0001:
            return "100.0%"
        return f"{(valor / geral) * 100:.1f}%"

    @staticmethod
    def fator_projecao(
        df: pd.DataFrame, coluna_data: str = "DATA"
    ) -> Tuple[float, int, int]:
        if df.empty or coluna_data not in df.columns:
            return 1.0, 0, 0

        s = _primeira_serie(df, coluna_data)
        if s is None:
            return 1.0, 0, 0

        datas = pd.to_datetime(s, errors="coerce").dropna()
        if datas.empty:
            return 1.0, 0, 0

        data_max = datas.max().normalize()
        inicio_mes = data_max.replace(day=1)
        prox_mes = (inicio_mes + pd.Timedelta(days=32)).replace(day=1)
        fim_mes = prox_mes - pd.Timedelta(days=1)

        dias_uteis_total = len(
            [d for d in pd.date_range(inicio_mes, fim_mes) if d.dayofweek < 6]
        )
        dias_decorridos = len(
            [d for d in pd.date_range(inicio_mes, data_max) if d.dayofweek < 6]
        )
        faltantes = max(0, dias_uteis_total - dias_decorridos)
        fator = (dias_uteis_total / dias_decorridos) if dias_decorridos > 0 else 1.0
        return fator, faltantes, dias_uteis_total


def get_status_geral(valor: int | float, tipo: str = "os") -> Tuple[str, str, str]:
    m = (
        ObjetivosOperacao.PRODUCAO_OS_GERAL
        if tipo == "os"
        else ObjetivosOperacao.CONSULTIVO_GERAL
    )
    if valor >= m["alta_perf"]:
        return "🔥 Alta Performance", COR_SUCESSO, "#D1FAE5"
    elif valor >= m["meta_base"]:
        return "✅ Meta Atingida", COR_SUCESSO, "#D1FAE5"
    elif valor >= m["minima"]:
        return "⚠️ Atenção / Mínimo", COR_ATENCAO, "#FEF3C7"
    else:
        return "🚨 Crítico / Abaixo", COR_ALERTA, "#FEE2E2"


def get_status_projeto(
    valor: int | float, metas: Dict[str, int]
) -> Tuple[str, str, str]:
    if valor >= metas["alta_perf"]:
        return "🔥 Alta Performance", COR_SUCESSO, "#D1FAE5"
    if valor >= metas["meta_base"]:
        return "✅ Meta Atingida", COR_SUCESSO, "#D1FAE5"
    if valor >= metas["minima"]:
        return "⚠️ Atenção / Mínimo", COR_ATENCAO, "#FEF3C7"
    return "🚨 Crítico / Abaixo", COR_ALERTA, "#FEE2E2"


# ═══════════════════════════════════════════════════════════════════════════
# ESTILOS CSS
# ═══════════════════════════════════════════════════════════════════════════


def aplicar_estilo():
    st.markdown(
        f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

    html, body, p, label, li, a, button, input, select, textarea {{
        font-family: {FONTE_TEXTO} !important;
    }}
    h1, h2, h3, h4 {{
        font-family: {FONTE_TITULO} !important;
        font-weight: 700;
        color: {COR_PRIMARIA};
    }}
    .main .block-container {{
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}
    section[data-testid="stSidebar"] {{
        background-color: {SB_FUNDO} !important;
        border-right: 1px solid {SB_BORDA_SUTIL} !important;
    }}
    .hero-totale {{
        background: linear-gradient(135deg, {COR_PRIMARIA} 0%, #02419c 60%, {COR_SECUNDARIA} 100%);
        padding: 1.8rem 2.2rem;
        border-radius: 12px;
        color: #FFFFFF;
        box-shadow: 0 4px 14px rgba(1, 40, 105, 0.15);
        margin-bottom: 1.5rem;
    }}
    .hero-totale h1 {{ color: #FFFFFF !important; margin: 0 0 0.4rem 0; font-size: 1.9rem; }}
    .hero-totale p {{ color: #E2E8F0 !important; margin: 0; font-size: 0.95rem; }}

    .card-kpi {{
        background: {COR_FUNDO_CARD};
        border-radius: 10px;
        padding: 1.2rem 1.4rem;
        border: 1px solid {COR_BORDA};
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
    }}
    .card-kpi-titulo {{ font-size: 0.85rem; font-weight: 600; color: {COR_NEUTRO}; text-transform: uppercase; margin-bottom: 0.3rem; }}
    .card-kpi-valor {{ font-size: 1.8rem; font-weight: 700; color: {COR_TEXTO}; margin-bottom: 0.4rem; }}
    .card-kpi-sub {{ font-size: 0.8rem; color: {COR_TEXTO_3}; }}
    .card-projeto {{
        background: {COR_FUNDO_CARD};
        border: 1px solid {COR_BORDA};
        border-top: 4px solid {COR_SECUNDARIA};
        border-radius: 10px;
        padding: 1rem 1.1rem;
        min-height: 150px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }}
    .card-projeto-titulo {{ font-size: 1rem; font-weight: 700; color: {COR_PRIMARIA}; margin-bottom: 0.6rem; }}
    .card-projeto-valor {{ font-size: 1.7rem; font-weight: 700; color: {COR_TEXTO}; }}
    .card-projeto-sub {{ font-size: 0.78rem; color: {COR_TEXTO_3}; margin-top: 0.25rem; }}
    .badge {{
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


aplicar_estilo()

# ═══════════════════════════════════════════════════════════════════════════
# CARREGAMENTO DE DADOS
# ═══════════════════════════════════════════════════════════════════════════


def _ler_csv_bytes(conteudo: bytes) -> pd.DataFrame:
    """Tenta vários encodings/separadores até obter um DataFrame válido."""
    if not conteudo or len(conteudo) < 10:
        raise ValueError("Arquivo CSV vazio ou muito pequeno.")

    melhor: Optional[pd.DataFrame] = None
    melhor_cols = 0

    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        for sep in (",", ";", "\t", "|"):
            try:
                tmp = pd.read_csv(
                    io.BytesIO(conteudo),
                    sep=sep,
                    encoding=enc,
                    low_memory=False,
                    dtype=str,  # evita inferência ambígua; convertemos depois
                )
                if tmp is not None and len(tmp.columns) > melhor_cols and len(tmp) > 0:
                    melhor = tmp
                    melhor_cols = len(tmp.columns)
                    # bom o bastante
                    if melhor_cols >= 3:
                        return melhor
            except Exception:
                continue

    if melhor is not None:
        return melhor

    return pd.read_csv(
        io.BytesIO(conteudo), encoding="latin-1", low_memory=False, dtype=str
    )


def _baixar_drive_csv(file_id: str) -> bytes:
    """
    Baixa arquivo do Google Drive.
    1) tenta gdown em arquivo temporário
    2) fallback via requests (export direto)
    """
    urls = [
        f"https://drive.google.com/uc?id={file_id}&export=download",
        f"https://drive.google.com/uc?export=download&id={file_id}",
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
    ]

    # --- gdown (arquivo temp; BytesIO costuma falhar em algumas versões) ---
    if gdown is not None:
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".csv")
            os.close(fd)
            out = gdown.download(
                url=f"https://drive.google.com/uc?id={file_id}",
                output=tmp_path,
                quiet=True,
                fuzzy=True,
            )
            if out and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 10:
                with open(tmp_path, "rb") as f:
                    return f.read()
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # --- requests ---
    last_err = None
    session = requests.Session()
    for url in urls:
        try:
            resp = session.get(url, timeout=Configuracoes.TIMEOUT, allow_redirects=True)
            # confirmação de download grande do Drive
            if (
                "confirm=" in resp.text[:2000]
                and "download_warning" in resp.text[:5000]
            ):
                m = re.search(r"confirm=([0-9A-Za-z_]+)", resp.text)
                if m:
                    resp = session.get(
                        f"https://drive.google.com/uc?export=download&confirm={m.group(1)}&id={file_id}",
                        timeout=Configuracoes.TIMEOUT,
                    )
            if resp.status_code == 200 and len(resp.content) > 10:
                ctype = resp.headers.get("Content-Type", "")
                # evita página HTML de login/permissão
                if (
                    "text/html" in ctype
                    and b"," not in resp.content[:500]
                    and b";" not in resp.content[:500]
                ):
                    last_err = "Drive retornou HTML (arquivo sem permissão pública?)"
                    continue
                return resp.content
            last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            last_err = str(e)

    raise RuntimeError(last_err or "Falha ao baixar CSV do Drive")


@st.cache_data(ttl=CACHE_TTL_METAS, show_spinner="Carregando hierarquia...")
def carregar_hierarquia() -> pd.DataFrame:
    """
    Carrega lista_ativos.
    Tenta streamlit_gsheets; fallback CSV público da planilha.
    """
    df = pd.DataFrame()

    # 1) GSheetsConnection
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            df = conn.read(
                spreadsheet=Configuracoes.URL_ATIVOS,
                worksheet=Configuracoes.SHEET_ABA_ATIVOS,
                ttl=0,
            )
        except Exception:
            df = conn.read(spreadsheet=Configuracoes.URL_ATIVOS, ttl=0)
    except Exception:
        df = pd.DataFrame()

    # 2) Fallback: export CSV público
    if df is None or df.empty:
        try:
            csv_url = (
                f"https://docs.google.com/spreadsheets/d/{Configuracoes.SHEET_ID_ATIVOS}"
                f"/gviz/tq?tqx=out:csv&sheet={url_quote(Configuracoes.SHEET_ABA_ATIVOS)}"
            )
            resp = requests.get(csv_url, timeout=Configuracoes.TIMEOUT)
            if resp.status_code == 200 and len(resp.text) > 10:
                df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        except Exception:
            df = pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame(columns=["LOGIN", "TECNICO", "MONITOR", "BASE"])

    df.columns = [str(c).strip() for c in df.columns]
    df = mapear_colunas(
        df,
        {
            "LOGIN": ["LOGIN", "USER", "USUARIO", "MATRICULA", "ID"],
            "TECNICO": ["TECNICO", "NOME", "COLABORADOR", "NOME_TECNICO"],
            "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR", "LIDER"],
            "BASE": ["BASE", "FILIAL", "REGIONAL", "CIDADE", "LOCALIDADE"],
        },
    )

    for col in ["LOGIN", "TECNICO", "MONITOR", "BASE"]:
        if col not in df.columns:
            df[col] = "Não Informado"

    df = garantir_login(df, "LOGIN")
    df = deduplicar_colunas(df)
    return (
        df[["LOGIN", "TECNICO", "MONITOR", "BASE"]]
        .dropna(subset=["LOGIN"])
        .drop_duplicates(subset=["LOGIN"])
        .reset_index(drop=True)
    )


@st.cache_data(ttl=CACHE_TTL_CONSULTIVO, show_spinner="Baixando Consultivos (Drive)...")
def carregar_consultivos() -> Tuple[pd.DataFrame, Optional[str]]:
    try:
        conteudo = _baixar_drive_csv(Configuracoes.DRIVE_ID_CONS)
        df = _ler_csv_bytes(conteudo)
        df.columns = [str(c).strip() for c in df.columns]

        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_CRIACAO",
                    "DATA_CRIACAO",
                    "DT",
                    "CRIACAO",
                    "DATAS",
                ],
                "LOGIN": ["LOGIN", "USUARIO", "USER", "MATRICULA"],
                "PROJETO": ["PROJETO", "PROJECT", "CONTRATO", "CLIENTE_PROJETO"],
                "BASE": ["BASE", "FILIAL", "REGIONAL"],
                "TECNICO": ["TECNICO", "NOME", "COLABORADOR"],
                "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR"],
            },
        )
        df = garantir_datetime(df, "DATA")
        df = garantir_login(df, "LOGIN")
        df = deduplicar_colunas(df)
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Erro ao processar CSV: {str(e)[:160]}"


@st.cache_data(ttl=CACHE_TTL_PRODUCAO, show_spinner="Carregando Produção...")
def carregar_producao() -> Tuple[pd.DataFrame, Optional[str]]:
    try:
        url = (
            f"https://docs.google.com/spreadsheets/d/{Configuracoes.SHEET_ID_PROD}"
            f"/gviz/tq?tqx=out:csv&sheet={url_quote(Configuracoes.SHEET_ABA_PROD)}"
        )
        resp = requests.get(url, timeout=Configuracoes.TIMEOUT)
        if resp.status_code != 200:
            return pd.DataFrame(), f"Erro HTTP {resp.status_code}"

        # gviz às vezes devolve HTML de login
        text = resp.text
        if text.lstrip().lower().startswith(
            "<!doctype"
        ) or text.lstrip().lower().startswith("<html"):
            return (
                pd.DataFrame(),
                "Planilha de Produção inacessível (permissão/público).",
            )

        df = pd.read_csv(io.StringIO(text), dtype=str)
        df.columns = [str(c).strip() for c in df.columns]

        # remove colunas totalmente vazias / Unnamed
        df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]]

        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_EXECUCAO",
                    "DATA_EXECUCAO",
                    "DT",
                    "EXECUCAO",
                    "DATA_OS",
                ],
                "LOGIN": ["LOGIN", "MATRICULA", "USUARIO", "USER", "LOGIN_TECNICO"],
                "PROJETO": ["PROJETO", "PROJECT", "CONTRATO"],
                "NUM_OS": ["NUM_OS", "NUMERO_OS", "N_OS", "OS", "ORDEM", "NUMERO"],
                "BASE": ["BASE", "FILIAL", "REGIONAL"],
                "TECNICO": ["TECNICO", "NOME", "COLABORADOR"],
                "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR"],
            },
        )
        df = garantir_datetime(df, "DATA")
        df = garantir_login(df, "LOGIN")
        df = deduplicar_colunas(df)
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {str(e)[:140]}"


# Carregamento
df_hierarquia = carregar_hierarquia()
df_cons_raw, erro_cons = carregar_consultivos()
df_prod_raw, erro_prod = carregar_producao()


def enriquecer_dados(df: pd.DataFrame, hierarquia: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = deduplicar_colunas(df.copy())

    if hierarquia.empty or "LOGIN" not in df.columns:
        for col in ["TECNICO", "MONITOR", "BASE"]:
            if col not in df.columns:
                df[col] = "Não Informado"
        return df

    hier = deduplicar_colunas(hierarquia.copy())
    df_merged = pd.merge(df, hier, on="LOGIN", how="left", suffixes=("", "_hier"))

    for col in ["TECNICO", "MONITOR", "BASE"]:
        c_hier = f"{col}_hier"
        if col in df_merged.columns and c_hier in df_merged.columns:
            df_merged[col] = df_merged[col].fillna(df_merged[c_hier])
            df_merged.drop(columns=[c_hier], inplace=True)
        elif c_hier in df_merged.columns:
            df_merged.rename(columns={c_hier: col}, inplace=True)
        elif col not in df_merged.columns:
            df_merged[col] = "Não Informado"

        df_merged[col] = df_merged[col].fillna("Não Informado")

    return deduplicar_colunas(df_merged)


df_prod = enriquecer_dados(df_prod_raw, df_hierarquia)
df_cons = enriquecer_dados(df_cons_raw, df_hierarquia)

# ═══════════════════════════════════════════════════════════════════════════
# BARRA LATERAL (FILTROS)
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 🎛️ Filtros Globais")

    def _opts(*series_list):
        vals = set()
        for s in series_list:
            if s is None:
                continue
            vals.update(
                [
                    v
                    for v in s.dropna().astype(str).unique().tolist()
                    if v and v != "nan"
                ]
            )
        return sorted(vals)

    bases = _opts(
        df_prod["BASE"] if "BASE" in df_prod.columns else None,
        df_cons["BASE"] if "BASE" in df_cons.columns else None,
    )
    monitores = _opts(
        df_prod["MONITOR"] if "MONITOR" in df_prod.columns else None,
        df_cons["MONITOR"] if "MONITOR" in df_cons.columns else None,
    )

    filtro_base = st.multiselect(
        "📍 Base / Regional", options=bases, placeholder="Todas as Bases"
    )
    filtro_monitor = st.multiselect(
        "👤 Monitor / Supervisor", options=monitores, placeholder="Todos os Monitores"
    )

    todas_datas: List[pd.Timestamp] = []
    for dframe in (df_prod, df_cons):
        if "DATA" in dframe.columns:
            s = pd.to_datetime(
                _primeira_serie(dframe, "DATA"), errors="coerce"
            ).dropna()
            todas_datas.extend(s.tolist())

    if todas_datas:
        min_dt = min(todas_datas).date()
        max_dt = max(todas_datas).date()
        filtro_datas = st.date_input(
            "📅 Período de Atendimento",
            value=(min_dt, max_dt),
            min_value=min_dt,
            max_value=max_dt,
        )
    else:
        filtro_datas = None

    st.divider()
    st.caption(f"Hierarquia: **{len(df_hierarquia)}** logins")
    st.caption(f"Produção (raw): **{len(df_prod_raw)}** linhas")
    st.caption(f"Consultivo (raw): **{len(df_cons_raw)}** linhas")

    if st.button("🔄 Atualizar Cache de Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption(
        f"🕐 Última consulta: {datetime.now(Configuracoes.TZ).strftime('%d/%m/%Y %H:%M:%S')}"
    )


def filtrar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    dff = deduplicar_colunas(df.copy())

    if filtro_base and "BASE" in dff.columns:
        dff = dff[dff["BASE"].astype(str).isin(filtro_base)]
    if filtro_monitor and "MONITOR" in dff.columns:
        dff = dff[dff["MONITOR"].astype(str).isin(filtro_monitor)]
    if (
        filtro_datas
        and isinstance(filtro_datas, (tuple, list))
        and len(filtro_datas) == 2
        and "DATA" in dff.columns
    ):
        d1, d2 = filtro_datas
        datas = pd.to_datetime(_primeira_serie(dff, "DATA"), errors="coerce")
        dff = dff[(datas.dt.date >= d1) & (datas.dt.date <= d2)]
    return dff


df_prod_f = filtrar_dataframe(df_prod)
df_cons_f = filtrar_dataframe(df_cons)

# ═══════════════════════════════════════════════════════════════════════════
# CABEÇALHO
# ═══════════════════════════════════════════════════════════════════════════

st.markdown(
    """
<div class="hero-totale">
    <h1>🎯 Dashboard de Metas Operacionais</h1>
    <p>Gestão Integrada de Produção (O.S.), Consultivos e Hierarquia Operacional</p>
</div>
""",
    unsafe_allow_html=True,
)

if erro_cons:
    st.warning(f"⚠️ Status Consultivo: {erro_cons}")
if erro_prod:
    st.warning(f"⚠️ Status Produção: {erro_prod}")
if df_hierarquia.empty:
    st.info(
        "ℹ️ Hierarquia vazia. Confira se a planilha "
        f"`{Configuracoes.SHEET_ABA_ATIVOS}` está pública ou se o secrets do GSheets está ok."
    )

# ═══════════════════════════════════════════════════════════════════════════
# COMPONENTES VISUAIS
# ═══════════════════════════════════════════════════════════════════════════


def render_gauge(
    valor_real: int, meta_min: int, meta_base: int, meta_alta: int, titulo: str
):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=valor_real,
            domain={"x": [0, 1], "y": [0, 1]},
            title={
                "text": titulo,
                "font": {"size": 18, "family": FONTE_TITULO, "color": COR_PRIMARIA},
            },
            delta={
                "reference": meta_base,
                "increasing": {"color": COR_SUCESSO},
                "decreasing": {"color": COR_ALERTA},
            },
            gauge={
                "axis": {
                    "range": [0, max(meta_alta * 1.15, valor_real * 1.15, 1)],
                    "tickwidth": 1,
                },
                "bar": {"color": COR_PRIMARIA},
                "bgcolor": "#FFFFFF",
                "borderwidth": 1,
                "bordercolor": "#E2E8F0",
                "steps": [
                    {"range": [0, meta_min], "color": "#FEE2E2"},
                    {"range": [meta_min, meta_base], "color": "#FEF3C7"},
                    {
                        "range": [meta_base, max(meta_alta * 1.15, 1)],
                        "color": "#D1FAE5",
                    },
                ],
                "threshold": {
                    "line": {"color": COR_SECUNDARIA, "width": 4},
                    "thickness": 0.8,
                    "value": meta_base,
                },
            },
        )
    )
    fig.update_layout(
        height=280, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="transparent"
    )
    return fig


def render_cards_por_projeto(
    df: pd.DataFrame, tipo: str, titulo: str, unidade: str
) -> None:
    if df.empty or "PROJETO" not in df.columns:
        st.info(f"Dados de projeto não disponíveis para {titulo.lower()}.")
        return

    metas = (
        ObjetivosOperacao.PRODUCAO_OS_PROJETO
        if tipo == "os"
        else ObjetivosOperacao.CONSULTIVO_PROJETO
    )
    projetos = df["PROJETO"].fillna("Não informado").astype(str).str.strip()
    projetos = projetos.replace({"": "Não informado", "nan": "Não informado"})
    volumes = projetos.value_counts().sort_values(ascending=False)

    st.markdown(f"#### {titulo}")
    items = list(volumes.items())
    for inicio in range(0, len(items), 4):
        cards = st.columns(min(len(items) - inicio, 4))
        for card, (projeto, volume) in zip(cards, items[inicio : inicio + 4]):
            atingimento = (
                (volume / metas["meta_base"] * 100) if metas["meta_base"] else 0
            )
            status, cor, _ = get_status_projeto(volume, metas)
            with card:
                st.markdown(
                    f"""
                    <div class="card-projeto">
                        <div class="card-projeto-titulo">{projeto}</div>
                        <div class="card-projeto-valor" style="color: {cor};">{volume:,}</div>
                        <div class="card-projeto-sub">{unidade} | Atingimento: <b>{atingimento:.1f}%</b></div>
                        <div class="card-projeto-sub" style="color: {cor};"><b>{status}</b></div>
                        <div class="card-projeto-sub">Meta base: {metas["meta_base"]:,}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ═══════════════════════════════════════════════════════════════════════════
# ABAS
# ═══════════════════════════════════════════════════════════════════════════

aba_prod, aba_cons, aba_hierarquia, aba_simulador = st.tabs(
    [
        "📊 Produção (O.S.)",
        "💼 Consultivos",
        "👥 Visão por Equipe & Base",
        "📈 Projeções & Simulador",
    ]
)

# ── ABA 1: PRODUÇÃO ────────────────────────────────────────────────────────
with aba_prod:
    total_os = len(df_prod_f)
    meta_min_os = ObjetivosOperacao.PRODUCAO_OS_GERAL["minima"]
    meta_base_os = ObjetivosOperacao.PRODUCAO_OS_GERAL["meta_base"]
    meta_alta_os = ObjetivosOperacao.PRODUCAO_OS_GERAL["alta_perf"]

    fator_proj_os, dias_rest_os, dias_tot_os = Calculos.fator_projecao(
        df_prod_f, "DATA"
    )
    projecao_os = int(total_os * fator_proj_os)
    atingimento_os = (total_os / meta_base_os * 100) if meta_base_os > 0 else 0
    status_os_txt, status_os_cor, _ = get_status_geral(total_os, "os")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">O.S. Realizadas</div>
            <div class="card-kpi-valor" style="color: {COR_PRIMARIA};">{total_os:,}</div>
            <div class="card-kpi-sub">Atingimento: <b>{atingimento_os:.1f}%</b> da meta base</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">Meta Consolidada (Base)</div>
            <div class="card-kpi-valor">{meta_base_os:,}</div>
            <div class="card-kpi-sub">Mín: {meta_min_os:,} | Alta Perf: {meta_alta_os:,}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">Projeção Fechamento (Run-Rate)</div>
            <div class="card-kpi-valor" style="color: {COR_SECUNDARIA};">{projecao_os:,}</div>
            <div class="card-kpi-sub">{dias_rest_os} dias úteis restantes</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">Status Operacional</div>
            <div class="card-kpi-valor" style="font-size: 1.35rem; color: {status_os_cor};">{status_os_txt}</div>
            <div class="card-kpi-sub">Diferença: <b>{total_os - meta_base_os:+,} O.S.</b></div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    render_cards_por_projeto(df_prod_f, "os", "Produção por Projeto", "O.S. realizadas")
    st.markdown("<br>", unsafe_allow_html=True)

    g1, g2 = st.columns([1, 2])
    with g1:
        st.plotly_chart(
            render_gauge(
                total_os,
                meta_min_os,
                meta_base_os,
                meta_alta_os,
                "Termômetro de Produção (O.S.)",
            ),
            use_container_width=True,
        )
    with g2:
        if (
            "DATA" in df_prod_f.columns
            and pd.to_datetime(_primeira_serie(df_prod_f, "DATA"), errors="coerce")
            .notna()
            .any()
        ):
            s_data = pd.to_datetime(_primeira_serie(df_prod_f, "DATA"), errors="coerce")
            df_tempo = (
                s_data.dt.date.value_counts()
                .rename_axis("DATA")
                .reset_index(name="Volume")
                .sort_values("DATA")
            )
            df_tempo["Acumulado"] = df_tempo["Volume"].cumsum()
            fig_tempo = px.area(
                df_tempo,
                x="DATA",
                y="Acumulado",
                title="Evolução Acumulada da Produção no Período",
                color_discrete_sequence=[COR_PRIMARIA],
            )
            fig_tempo.add_hline(
                y=meta_base_os,
                line_dash="dash",
                line_color=COR_SECUNDARIA,
                annotation_text="Meta Base",
            )
            fig_tempo.update_layout(
                height=280,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="transparent",
            )
            st.plotly_chart(fig_tempo, use_container_width=True)
        else:
            st.info("Distribuição temporal não disponível com os dados atuais.")

    with st.expander("📋 Ver Tabela de Dados da Produção", expanded=False):
        st.dataframe(df_prod_f, use_container_width=True, hide_index=True)

# ── ABA 2: CONSULTIVOS ─────────────────────────────────────────────────────
with aba_cons:
    total_cons = len(df_cons_f)
    meta_min_cons = ObjetivosOperacao.CONSULTIVO_GERAL["minima"]
    meta_base_cons = ObjetivosOperacao.CONSULTIVO_GERAL["meta_base"]
    meta_alta_cons = ObjetivosOperacao.CONSULTIVO_GERAL["alta_perf"]

    fator_proj_cons, dias_rest_c, _ = Calculos.fator_projecao(df_cons_f, "DATA")
    projecao_cons = int(total_cons * fator_proj_cons)
    atingimento_cons = (total_cons / meta_base_cons * 100) if meta_base_cons > 0 else 0
    status_c_txt, status_c_cor, _ = get_status_geral(total_cons, "cons")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">Consultivos Realizados</div>
            <div class="card-kpi-valor" style="color: {COR_PRIMARIA};">{total_cons:,}</div>
            <div class="card-kpi-sub">Atingimento: <b>{atingimento_cons:.1f}%</b> da meta</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">Meta Consultivo (Base)</div>
            <div class="card-kpi-valor">{meta_base_cons:,}</div>
            <div class="card-kpi-sub">Mín: {meta_min_cons:,} | Alta Perf: {meta_alta_cons:,}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">Projeção Fechamento</div>
            <div class="card-kpi-valor" style="color: {COR_SECUNDARIA};">{projecao_cons:,}</div>
            <div class="card-kpi-sub">{dias_rest_c} dias úteis restantes</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"""
        <div class="card-kpi">
            <div class="card-kpi-titulo">Status Consultivo</div>
            <div class="card-kpi-valor" style="font-size: 1.35rem; color: {status_c_cor};">{status_c_txt}</div>
            <div class="card-kpi-sub">Diferença: <b>{total_cons - meta_base_cons:+,}</b></div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    render_cards_por_projeto(
        df_cons_f, "cons", "Consultivos por Projeto", "Consultivos realizados"
    )
    st.markdown("<br>", unsafe_allow_html=True)

    cg1, cg2 = st.columns([1, 2])
    with cg1:
        st.plotly_chart(
            render_gauge(
                total_cons,
                meta_min_cons,
                meta_base_cons,
                meta_alta_cons,
                "Termômetro Consultivo",
            ),
            use_container_width=True,
        )
    with cg2:
        if (
            "DATA" in df_cons_f.columns
            and pd.to_datetime(_primeira_serie(df_cons_f, "DATA"), errors="coerce")
            .notna()
            .any()
        ):
            s_data = pd.to_datetime(_primeira_serie(df_cons_f, "DATA"), errors="coerce")
            df_tempo_c = (
                s_data.dt.date.value_counts()
                .rename_axis("DATA")
                .reset_index(name="Volume")
                .sort_values("DATA")
            )
            df_tempo_c["Acumulado"] = df_tempo_c["Volume"].cumsum()
            fig_tempo_c = px.line(
                df_tempo_c,
                x="DATA",
                y="Acumulado",
                title="Curva de Realização de Consultivos",
                markers=True,
                color_discrete_sequence=[COR_SECUNDARIA],
            )
            fig_tempo_c.add_hline(
                y=meta_base_cons,
                line_dash="dash",
                line_color=COR_PRIMARIA,
                annotation_text="Meta Base",
            )
            fig_tempo_c.update_layout(
                height=280,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="transparent",
            )
            st.plotly_chart(fig_tempo_c, use_container_width=True)
        else:
            st.info("Distribuição temporal de consultivo não disponível.")

    with st.expander("📋 Ver Tabela de Dados Consultivos", expanded=False):
        st.dataframe(df_cons_f, use_container_width=True, hide_index=True)

# ── ABA 3: EQUIPE & BASE ───────────────────────────────────────────────────
with aba_hierarquia:
    st.subheader("Desempenho por Base e Liderança")
    col_h1, col_h2 = st.columns(2)

    with col_h1:
        if "BASE" in df_prod_f.columns and not df_prod_f.empty:
            df_base = (
                df_prod_f.groupby("BASE", dropna=False)
                .size()
                .reset_index(name="Volume O.S.")
                .sort_values(by="Volume O.S.", ascending=False)
            )
            fig_base = px.bar(
                df_base,
                x="BASE",
                y="Volume O.S.",
                title="Produção de O.S. por Base",
                text_auto=True,
                color="Volume O.S.",
                color_continuous_scale=["#DBEAFE", COR_PRIMARIA],
            )
            fig_base.update_layout(height=340, coloraxis_showscale=False)
            st.plotly_chart(fig_base, use_container_width=True)
        else:
            st.info("Dados de Base não encontrados na Produção.")

    with col_h2:
        if "MONITOR" in df_prod_f.columns and not df_prod_f.empty:
            df_mon = (
                df_prod_f.groupby("MONITOR", dropna=False)
                .size()
                .reset_index(name="Volume O.S.")
                .sort_values(by="Volume O.S.", ascending=False)
            )
            fig_mon = px.bar(
                df_mon,
                x="MONITOR",
                y="Volume O.S.",
                title="Produção de O.S. por Monitor",
                text_auto=True,
                color="Volume O.S.",
                color_continuous_scale=["#FED7AA", COR_SECUNDARIA],
            )
            fig_mon.update_layout(height=340, coloraxis_showscale=False)
            st.plotly_chart(fig_mon, use_container_width=True)
        else:
            st.info("Dados de Monitor não encontrados na Produção.")

    st.divider()
    st.subheader("🏆 Ranking de Produtividade por Técnico")

    col_rk = (
        "TECNICO"
        if "TECNICO" in df_prod_f.columns
        else "LOGIN" if "LOGIN" in df_prod_f.columns else None
    )
    if col_rk and not df_prod_f.empty:
        grp_cols = [col_rk, "BASE"] if "BASE" in df_prod_f.columns else [col_rk]
        df_tec = (
            df_prod_f.groupby(grp_cols, dropna=False)
            .size()
            .reset_index(name="Total O.S.")
            .sort_values(by="Total O.S.", ascending=False)
        )
        st.dataframe(
            df_tec.head(25).style.background_gradient(
                subset=["Total O.S."], cmap="Blues"
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "Identificadores de técnicos/logins insuficientes para montar o ranking."
        )

# ── ABA 4: SIMULADOR ───────────────────────────────────────────────────────
with aba_simulador:
    st.subheader("🎯 Simulador de Fechamento de Metas")
    st.markdown(
        "Ajuste o ritmo diário esperado e os dias úteis restantes para calcular cenários de entrega."
    )

    # defaults seguros caso produção esteja vazia
    _dias_decorridos = max(1, (dias_tot_os - dias_rest_os) if dias_tot_os else 1)
    _default_ritmo_os = int(total_os / _dias_decorridos) if total_os else 1000
    _default_ritmo_cons = int(total_cons / _dias_decorridos) if total_cons else 50

    sim_col1, sim_col2, sim_col3 = st.columns(3)
    with sim_col1:
        dias_sim = st.number_input(
            "Dias Úteis Restantes no Mês",
            min_value=0,
            max_value=31,
            value=int(max(dias_rest_os, 0)),
        )
    with sim_col2:
        ritmo_prod_diario = st.number_input(
            "Média Diária Esperada de O.S. (Geral)",
            min_value=0,
            value=max(_default_ritmo_os, 0),
        )
    with sim_col3:
        ritmo_cons_diario = st.number_input(
            "Média Diária Esperada de Consultivos",
            min_value=0,
            value=max(_default_ritmo_cons, 0),
        )

    os_simulado = total_os + (ritmo_prod_diario * dias_sim)
    cons_simulado = total_cons + (ritmo_cons_diario * dias_sim)

    st.markdown("#### Resultado da Simulação")
    rs1, rs2 = st.columns(2)
    with rs1:
        st.metric(
            label="Projeção Simulada de Produção (O.S.)",
            value=f"{os_simulado:,} O.S.",
            delta=f"{os_simulado - meta_base_os:+,} vs Meta Base ({meta_base_os:,})",
        )
    with rs2:
        st.metric(
            label="Projeção Simulada de Consultivos",
            value=f"{cons_simulado:,} Consultivos",
            delta=f"{cons_simulado - meta_base_cons:+,} vs Meta Base ({meta_base_cons:,})",
        )