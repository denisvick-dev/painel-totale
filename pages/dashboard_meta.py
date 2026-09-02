"""
dashboard_meta.py
=================
Dashboard de Metas Operacionais - TOTALE
Integração Completa: Produção + Consultivo (CSV via gdown) + Hierarquia
"""

from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote as url_quote
from zoneinfo import ZoneInfo

from gdown.download import download as gdown_download
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection

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

COR_PRIMARIA = "#012869"  # Azul Totale
COR_SECUNDARIA = "#F37C04"  # Laranja Totale
COR_SUCESSO = "#059669"  # Verde
COR_ALERTA = "#DC2626"  # Vermelho
COR_ATENCAO = "#F59E0B"  # Âmbar
COR_NEUTRO = "#64748B"  # Slate Gray
COR_FUNDO_CARD = "#FFFFFF"
COR_BORDA = "#E2E8F0"

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

from components.componentes import (
    COR_TEXTO,
    COR_TEXTO_3,
)

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES E METAS (3 PROJETOS ATIVOS)
# ═══════════════════════════════════════════════════════════════════════════


class Configuracoes:
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"  # Substitua pela URL da planilha de Hierarquia
    SHEET_ID_PROD = "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
    SHEET_ABA_PROD = "Prod"
    DRIVE_ID_CONS = "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"

    TIMEOUT = 30
    TZ = ZoneInfo("America/Sao_Paulo")


class ObjetivosOperacao:
    # Metas por projeto individual
    PRODUCAO_OS_PROJETO = {"minima": 7_000, "meta_base": 10_000, "alta_perf": 11_000}
    CONSULTIVO_PROJETO = {"minima": 367, "meta_base": 525, "alta_perf": 580}

    # Metas Consolidadas Gerais (3 Projetos)
    PRODUCAO_OS_GERAL = {"minima": 21_000, "meta_base": 30_000, "alta_perf": 33_000}
    CONSULTIVO_GERAL = {"minima": 1_102, "meta_base": 1_575, "alta_perf": 1_732}


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
        """
        Retorna (fator_multiplicador, dias_restantes, dias_uteis_total)
        Considera Segunda a Sábado como dias operacionais úteis.
        """
        if df.empty or coluna_data not in df.columns or df[coluna_data].isna().all():
            return 1.0, 0, 0

        datas = pd.to_datetime(df[coluna_data], errors="coerce").dropna()
        if datas.empty:
            return 1.0, 0, 0

        hoje = pd.Timestamp.now(Configuracoes.TZ).tz_localize(None).normalize()
        data_max = datas.max().normalize()

        # Mês de referência baseado nos dados
        inicio_mes = data_max.replace(day=1)
        prox_mes = (inicio_mes + pd.Timedelta(days=32)).replace(day=1)
        fim_mes = prox_mes - pd.Timedelta(days=1)

        dias_uteis_total = len(
            [d for d in pd.date_range(inicio_mes, fim_mes) if d.dayofweek < 6]
        )

        # Considera dias decorridos até a data máxima observada nos dados
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


def normalizar_texto(texto: Any) -> str:
    if pd.isna(texto):
        return ""
    txt = str(texto).strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    ).upper()


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
# CARREGAMENTO E TRATAMENTO DE DADOS
# ═══════════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=CACHE_TTL_METAS, show_spinner="Carregando hierarquia...")
def carregar_hierarquia() -> pd.DataFrame:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=Configuracoes.URL_ATIVOS, ttl=0)
        df.columns = [c.strip() for c in df.columns]

        # Mapeamento dinâmico de colunas essenciais
        col_map = {}
        for c in df.columns:
            c_norm = normalizar_texto(c)
            if "LOGIN" in c_norm or "USER" in c_norm or "MATRICULA" in c_norm:
                col_map[c] = "LOGIN"
            elif "TECNICO" in c_norm or "NOME" in c_norm or "COLABORADOR" in c_norm:
                col_map[c] = "TECNICO"
            elif "MONITOR" in c_norm or "SUPERVISOR" in c_norm or "GESTOR" in c_norm:
                col_map[c] = "MONITOR"
            elif "BASE" in c_norm or "FILIAL" in c_norm or "REGIONAL" in c_norm:
                col_map[c] = "BASE"

        df = df.rename(columns=col_map)
        for col in ["LOGIN", "TECNICO", "MONITOR", "BASE"]:
            if col not in df.columns:
                df[col] = "Não Informado"

        df["LOGIN"] = df["LOGIN"].astype(str).str.strip().str.upper()
        return df[["LOGIN", "TECNICO", "MONITOR", "BASE"]].drop_duplicates(
            subset=["LOGIN"]
        )
    except Exception:
        # Fallback estrutural seguro caso não haja conexão de planilhas ativa
        return pd.DataFrame(columns=["LOGIN", "TECNICO", "MONITOR", "BASE"])


@st.cache_data(ttl=CACHE_TTL_CONSULTIVO, show_spinner="Baixando Consultivos (Drive)...")
def carregar_consultivos() -> Tuple[pd.DataFrame, Optional[str]]:
    try:
        url = f"https://drive.google.com/uc?id={Configuracoes.DRIVE_ID_CONS}"
        output = io.BytesIO()
        gdown_download(url, output, quiet=True)
        output.seek(0)
        conteudo_bytes = output.read()

        if len(conteudo_bytes) < 10:
            return pd.DataFrame(), "Arquivo CSV vazio ou sem permissão pública."

        df = None
        for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            for sep in [",", ";", "\t"]:
                try:
                    df_temp = pd.read_csv(
                        io.BytesIO(conteudo_bytes),
                        sep=sep,
                        encoding=enc,
                        low_memory=False,
                    )
                    if (
                        df_temp is not None
                        and len(df_temp.columns) > 1
                        and len(df_temp) > 0
                    ):
                        df = df_temp
                        break
                except Exception:
                    continue
            if df is not None:
                break

        if df is None:
            df = pd.read_csv(
                io.BytesIO(conteudo_bytes), encoding="latin-1", low_memory=False
            )

        df.columns = [c.strip() for c in df.columns]

        # Mapeamento e padronização de colunas
        for c in df.columns:
            cn = normalizar_texto(c)
            if "DATA" in cn or "DT" in cn or "CRIACAO" in cn:
                df = df.rename(columns={c: "DATA"})
            elif "LOGIN" in cn or "USUARIO" in cn:
                df = df.rename(columns={c: "LOGIN"})
            elif "PROJETO" in cn:
                df = df.rename(columns={c: "PROJETO"})
            elif "BASE" in cn:
                df = df.rename(columns={c: "BASE"})

        if "DATA" in df.columns:
            df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce")

        if "LOGIN" in df.columns:
            df["LOGIN"] = df["LOGIN"].astype(str).str.strip().str.upper()

        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Erro ao processar CSV: {str(e)[:100]}"


@st.cache_data(ttl=CACHE_TTL_PRODUCAO, show_spinner="Carregando Produção...")
def carregar_producao() -> Tuple[pd.DataFrame, Optional[str]]:
    try:
        url = f"https://docs.google.com/spreadsheets/d/{Configuracoes.SHEET_ID_PROD}/gviz/tq?tqx=out:csv&sheet={url_quote(Configuracoes.SHEET_ABA_PROD)}"
        resp = requests.get(url, timeout=Configuracoes.TIMEOUT)
        if resp.status_code != 200:
            return pd.DataFrame(), f"Erro HTTP {resp.status_code}"
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.strip() for c in df.columns]

        # Normalização de Nomes de Coluna
        for c in df.columns:
            cn = normalizar_texto(c)
            if "DATA" in cn or "DT" in cn or "EXECUCAO" in cn:
                df = df.rename(columns={c: "DATA"})
            elif "LOGIN" in cn or "MATRICULA" in cn:
                df = df.rename(columns={c: "LOGIN"})
            elif "PROJETO" in cn:
                df = df.rename(columns={c: "PROJETO"})
            elif "OS" in cn or "ORDEM" in cn or "NUMERO" in cn:
                df = df.rename(columns={c: "NUM_OS"})

        if "DATA" in df.columns:
            df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce")

        if "LOGIN" in df.columns:
            df["LOGIN"] = df["LOGIN"].astype(str).str.strip().str.upper()

        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)[:100]


# Carregamento
df_hierarquia = carregar_hierarquia()
df_cons_raw, erro_cons = carregar_consultivos()
df_prod_raw, erro_prod = carregar_producao()


# Enriquecimento com Hierarquia
def enriquecer_dados(df: pd.DataFrame, hierarquia: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if not hierarquia.empty and "LOGIN" in df.columns:
        df_merged = pd.merge(
            df, hierarquia, on="LOGIN", how="left", suffixes=("", "_hier")
        )
        # Preencher colunas se ausentes no dataset original
        for col in ["TECNICO", "MONITOR", "BASE"]:
            if col in df_merged.columns and f"{col}_hier" in df_merged.columns:
                df_merged[col] = df_merged[col].fillna(df_merged[f"{col}_hier"])
                df_merged.drop(columns=[f"{col}_hier"], inplace=True)
            elif f"{col}_hier" in df_merged.columns:
                df_merged[col] = df_merged[f"{col}_hier"]
                df_merged.drop(columns=[f"{col}_hier"], inplace=True)
        return df_merged
    return df


df_prod = enriquecer_dados(df_prod_raw.copy(), df_hierarquia)
df_cons = enriquecer_dados(df_cons_raw.copy(), df_hierarquia)

# ═══════════════════════════════════════════════════════════════════════════
# BARRA LATERAL (FILTROS)
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 🎛️ Filtros Globais")

    # Obter listas únicas para filtros
    bases = sorted(
        list(
            set(
                df_prod["BASE"].dropna().unique().tolist()
                if "BASE" in df_prod.columns
                else []
            )
            | set(
                df_cons["BASE"].dropna().unique().tolist()
                if "BASE" in df_cons.columns
                else []
            )
        )
    )

    monitores = sorted(
        list(
            set(
                df_prod["MONITOR"].dropna().unique().tolist()
                if "MONITOR" in df_prod.columns
                else []
            )
            | set(
                df_cons["MONITOR"].dropna().unique().tolist()
                if "MONITOR" in df_cons.columns
                else []
            )
        )
    )

    filtro_base = st.multiselect(
        "📍 Base / Regional", options=bases, placeholder="Todas as Bases"
    )
    filtro_monitor = st.multiselect(
        "👤 Monitor / Supervisor", options=monitores, placeholder="Todos os Monitores"
    )

    # Filtro de Data caso haja colunas temporais
    todas_datas = []
    if "DATA" in df_prod.columns and not df_prod["DATA"].isna().all():
        todas_datas.extend(df_prod["DATA"].dropna().tolist())
    if "DATA" in df_cons.columns and not df_cons["DATA"].isna().all():
        todas_datas.extend(df_cons["DATA"].dropna().tolist())

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
    if st.button("🔄 Atualizar Cache de Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption(
        f"🕐 Última consulta: {datetime.now(Configuracoes.TZ).strftime('%d/%m/%Y %H:%M:%S')}"
    )


# Aplicação dos Filtros
def filtrar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    dff = df.copy()
    if filtro_base and "BASE" in dff.columns:
        dff = dff[dff["BASE"].isin(filtro_base)]
    if filtro_monitor and "MONITOR" in dff.columns:
        dff = dff[dff["MONITOR"].isin(filtro_monitor)]
    if (
        filtro_datas
        and isinstance(filtro_datas, (tuple, list))
        and len(filtro_datas) == 2
        and "DATA" in dff.columns
    ):
        d1, d2 = filtro_datas
        dff = dff[(dff["DATA"].dt.date >= d1) & (dff["DATA"].dt.date <= d2)]
    return dff


df_prod_f = filtrar_dataframe(df_prod)
df_cons_f = filtrar_dataframe(df_cons)

# ═══════════════════════════════════════════════════════════════════════════
# CABEÇALHO HERO
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
    st.info(f"ℹ️ Status Consultivo: {erro_cons}")
if erro_prod:
    st.info(f"ℹ️ Status Produção: {erro_prod}")

# ═══════════════════════════════════════════════════════════════════════════
# COMPONENTES VISUAIS AUXILIARES
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
                    "range": [None, max(meta_alta * 1.15, valor_real * 1.15)],
                    "tickwidth": 1,
                },
                "bar": {"color": COR_PRIMARIA},
                "bgcolor": "#FFFFFF",
                "borderwidth": 1,
                "bordercolor": "#E2E8F0",
                "steps": [
                    {"range": [0, meta_min], "color": "#FEE2E2"},
                    {"range": [meta_min, meta_base], "color": "#FEF3C7"},
                    {"range": [meta_base, meta_alta * 1.15], "color": "#D1FAE5"},
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


def get_status_projeto(valor: int | float, metas: Dict[str, int]) -> Tuple[str, str, str]:
    if valor >= metas["alta_perf"]:
        return "🔥 Alta Performance", COR_SUCESSO, "#D1FAE5"
    if valor >= metas["meta_base"]:
        return "✅ Meta Atingida", COR_SUCESSO, "#D1FAE5"
    if valor >= metas["minima"]:
        return "⚠️ Atenção / Mínimo", COR_ATENCAO, "#FEF3C7"
    return "🚨 Crítico / Abaixo", COR_ALERTA, "#FEE2E2"


def render_cards_por_projeto(
    df: pd.DataFrame, tipo: str, titulo: str, unidade: str
) -> None:
    """Exibe o desempenho individual de cada projeto do dataset."""
    if df.empty or "PROJETO" not in df.columns:
        st.info(f"Dados de projeto não disponíveis para {titulo.lower()}.")
        return

    metas = (
        ObjetivosOperacao.PRODUCAO_OS_PROJETO
        if tipo == "os"
        else ObjetivosOperacao.CONSULTIVO_PROJETO
    )
    projetos = df["PROJETO"].fillna("Não informado").astype(str).str.strip()
    projetos = projetos.replace("", "Não informado")
    volumes = projetos.value_counts().sort_values(ascending=False)

    st.markdown(f"#### {titulo}")
    projetos_items = list(volumes.items())
    for inicio in range(0, len(projetos_items), 4):
        cards = st.columns(min(len(projetos_items) - inicio, 4))
        for card, (projeto, volume) in zip(cards, projetos_items[inicio : inicio + 4]):
            atingimento = (volume / metas["meta_base"] * 100) if metas["meta_base"] else 0
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
# ABAS DA APLICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════

aba_prod, aba_cons, aba_hierarquia, aba_simulador = st.tabs(
    [
        "📊 Produção (O.S.)",
        "💼 Consultivos",
        "👥 Visão por Equipe & Base",
        "📈 Projeções & Simulador",
    ]
)

# ───────────────────────────────────────────────────────────────────────────
# ABA 1: PRODUÇÃO (O.S.)
# ───────────────────────────────────────────────────────────────────────────
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
    status_os_txt, status_os_cor, status_os_bg = get_status_geral(total_os, "os")

    # Linha de Métricas
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

    render_cards_por_projeto(
        df_prod_f, "os", "Produção por Projeto", "O.S. realizadas"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Gráficos
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
        if "DATA" in df_prod_f.columns and not df_prod_f["DATA"].isna().all():
            df_tempo = (
                df_prod_f.groupby(df_prod_f["DATA"].dt.date)
                .size()
                .reset_index(name="Volume")
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

    # Tabela detalhada
    with st.expander("📋 Ver Tabela de Dados da Produção", expanded=False):
        st.dataframe(df_prod_f, use_container_width=True, hide_index=True)


# ───────────────────────────────────────────────────────────────────────────
# ABA 2: CONSULTIVOS
# ───────────────────────────────────────────────────────────────────────────
with aba_cons:
    total_cons = len(df_cons_f)
    meta_min_cons = ObjetivosOperacao.CONSULTIVO_GERAL["minima"]
    meta_base_cons = ObjetivosOperacao.CONSULTIVO_GERAL["meta_base"]
    meta_alta_cons = ObjetivosOperacao.CONSULTIVO_GERAL["alta_perf"]

    fator_proj_cons, dias_rest_c, _ = Calculos.fator_projecao(df_cons_f, "DATA")
    projecao_cons = int(total_cons * fator_proj_cons)
    atingimento_cons = (total_cons / meta_base_cons * 100) if meta_base_cons > 0 else 0
    status_c_txt, status_c_cor, status_c_bg = get_status_geral(total_cons, "cons")

    # Linha de Métricas
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

    # Gráficos Consultivo
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
        if "DATA" in df_cons_f.columns and not df_cons_f["DATA"].isna().all():
            df_tempo_c = (
                df_cons_f.groupby(df_cons_f["DATA"].dt.date)
                .size()
                .reset_index(name="Volume")
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

    # Tabela detalhada
    with st.expander("📋 Ver Tabela de Dados Consultivos", expanded=False):
        st.dataframe(df_cons_f, use_container_width=True, hide_index=True)


# ───────────────────────────────────────────────────────────────────────────
# ABA 3: VISÃO POR EQUIPE & BASE
# ───────────────────────────────────────────────────────────────────────────
with aba_hierarquia:
    st.subheader("Desempenho por Base e Liderança")

    col_h1, col_h2 = st.columns(2)

    with col_h1:
        if "BASE" in df_prod_f.columns and not df_prod_f.empty:
            df_base = (
                df_prod_f.groupby("BASE")
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
                df_prod_f.groupby("MONITOR")
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
        df_tec = (
            df_prod_f.groupby(
                [col_rk, "BASE"] if "BASE" in df_prod_f.columns else [col_rk]
            )
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


# ───────────────────────────────────────────────────────────────────────────
# ABA 4: PROJEÇÕES & SIMULADOR
# ───────────────────────────────────────────────────────────────────────────
with aba_simulador:
    st.subheader("🎯 Simulador de Fechamento de Metas")
    st.markdown(
        "Ajuste o ritmo diário esperado e os dias úteis restantes para calcular cenários de entrega."
    )

    sim_col1, sim_col2, sim_col3 = st.columns(3)
    with sim_col1:
        dias_sim = st.number_input(
            "Dias Úteis Restantes no Mês",
            min_value=0,
            max_value=31,
            value=max(dias_rest_os, 5),
        )
    with sim_col2:
        ritmo_prod_diario = st.number_input(
            "Média Diária Esperada de O.S. (Geral)",
            min_value=0,
            value=(
                int(total_os / max(1, (dias_tot_os - dias_rest_os)))
                if dias_tot_os > dias_rest_os
                else 1000
            ),
        )
    with sim_col3:
        ritmo_cons_diario = st.number_input(
            "Média Diária Esperada de Consultivos",
            min_value=0,
            value=(
                int(total_cons / max(1, (dias_tot_os - dias_rest_os)))
                if dias_tot_os > dias_rest_os
                else 50
            ),
        )

    os_simulado = total_os + (ritmo_prod_diario * dias_sim)
    cons_simulado = total_cons + (ritmo_cons_diario * dias_sim)

    st.markdown("#### Resultado da Simulação")
    rs1, rs2 = st.columns(2)
    with rs1:
        diff_sim_os = os_simulado - meta_base_os
        st.metric(
            label="Projeção Simulada de Produção (O.S.)",
            value=f"{os_simulado:,} O.S.",
            delta=f"{diff_sim_os:+,} vs Meta Base ({meta_base_os:,})",
        )
    with rs2:
        diff_sim_cons = cons_simulado - meta_base_cons
        st.metric(
            label="Projeção Simulada de Consultivos",
            value=f"{cons_simulado:,} Consultivos",
            delta=f"{diff_sim_cons:+,} vs Meta Base ({meta_base_cons:,})",
        )
