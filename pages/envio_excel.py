import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from io import BytesIO, StringIO
from datetime import datetime
from components.componentes import (
    aplicar_estilo,
    render_hero_totale_1,
    render_kpi,
    render_section_header,
    render_insight,
    render_sidebar_brand,
    COR_PRIMARIA,
)

# ====================================================
# BLOCO 1: CONFIGURAÇÕES E ESTADO
# ====================================================

st.set_page_config(
    page_title="Atualização de Dados | TOTALE", page_icon="🔁", layout="wide"
)

# Aplica as fontes Inter/Manrope, tema Plotly e CSS do Sidebar Laranja
aplicar_estilo()


class Configuracoes:
    """Configurações técnicas de infraestrutura."""

    URL_PROD = "https://docs.google.com/spreadsheets/d/11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v/export?format=xlsx"
    URL_CONS = "https://drive.google.com/uc?id=1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs&export=download"
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/export?format=csv"
    VAZIOS = {"-", "nan", "None", "", "NaN"}
    FUSO = pd.Timestamp.now().tz_localize("UTC").tz_convert("America/Sao_Paulo").tzinfo


# ====================================================
# BLOCO 2: LOGICA DE PROCESSAMENTO (VETORIZADA)
# ====================================================


class ProcessadorDeDados:
    @staticmethod
    def _normalizar(serie: pd.Series) -> pd.Series:
        return (
            serie.astype(str)
            .str.strip()
            .replace(list(Configuracoes.VAZIOS), "")
            .fillna("")
        )

    @staticmethod
    def tratar_planos(df: pd.DataFrame) -> pd.DataFrame:
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df

        # Lógica de extração e limpeza
        internet_bruta = df["PLANO INTERNET"].astype(str).str.strip()
        partes = internet_bruta.str.split(".", n=1, expand=True)

        internet_limpa = ProcessadorDeDados._normalizar(partes[0]).astype(str)
        tv_embutida = (
            ProcessadorDeDados._normalizar(partes[1]).astype(str)
            if partes.shape[1] > 1
            else pd.Series("", index=df.index)
        )

        tv_original = ProcessadorDeDados._normalizar(df["PLANO TV"]).replace(
            "SERVIÇOS AVANÇADOS", "CLARO TV+ BOX"
        )
        tv_final = pd.Series(
            np.where(tv_original != "", tv_original, tv_embutida), index=df.index
        ).astype(str)

        # Flags e Tipos
        tem_tv = tv_final != ""
        tem_net = internet_limpa != ""

        df["QTDE_CONSULTIVO"] = tem_tv.astype(int) + tem_net.astype(int)

        cond = [tem_tv & tem_net, tem_tv & ~tem_net, ~tem_tv & tem_net]
        opts = [tv_final + " & " + internet_limpa, tv_final, internet_limpa]
        df["TIPO SERVIÇO"] = np.select(cond, opts, default="Sem Tipo")

        df["PLANO TV"] = tv_final
        df["PLANO INTERNET"] = internet_limpa
        return df

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)
    def sincronizar():
        """Executa o download e a engenharia de dados."""
        # 1. Produção
        prod_raw = pd.read_excel(Configuracoes.URL_PROD, sheet_name=None)

        # 2. Consultivo (CSV Google Drive)
        resp = requests.get(Configuracoes.URL_CONS)
        try:
            cons = pd.read_csv(StringIO(resp.text), sep=",")
        except:
            cons = pd.read_csv(BytesIO(resp.content), sep=";", encoding="utf-8")

        # 3. Ativos
        ativos = pd.read_csv(Configuracoes.URL_ATIVOS)
        ativos.columns = ativos.columns.str.strip()

        # Processamento Consultivo
        cons.columns = cons.columns.str.strip()
        cons = ProcessadorDeDados.tratar_planos(cons)

        if "OBSERVACAO" in cons.columns:
            cons["QTDE_PRODUTOS"] = (
                cons["OBSERVACAO"].fillna("").str.findall(r"\b\d{9,12}\b").apply(len)
            )

        return prod_raw, cons, ativos


# ====================================================
# BLOCO 3: INTERFACE DE USUÁRIO
# ====================================================

# --- SIDEBAR CORPORATIVO ---
with st.sidebar:
    render_sidebar_brand("TOTALE", "Data Management", icone="🏢")
    st.markdown("---")
    render_insight(
        "Certifique-se de estar conectado à VPN para acessar as bases de rede, se necessário.",
        "info",
    )

# --- HERO UNIT ---
render_hero_totale_1(
    titulo="Central de Atualização",
    subtitulo="Sincronização de bases de Produção, Consultivos e Lista de Ativos",
    icone="🔁",
)

# --- AÇÕES DE SINCRONIZAÇÃO ---
col_status, col_btn = st.columns([3, 1])

with col_status:
    ultima = st.session_state.get("ultima_atualizacao")
    if ultima:
        render_insight(
            f"Última sincronização realizada em: **{ultima.strftime('%d/%m/%Y às %H:%M:%S')}**",
            "ok",
        )
    else:
        render_insight("Os dados ainda não foram carregados nesta sessão.", "alerta")

with col_btn:
    if st.button("🔄 Sincronizar Agora", use_container_width=True, type="primary"):
        with st.status("Conectando aos servidores...", expanded=True) as status:
            st.write("Baixando planilhas mestras...")
            p, c, a = ProcessadorDeDados.sincronizar()

            st.write("Aplicando regras de negócio vetorizadas...")
            st.session_state["dados_prod"] = p
            st.session_state["dados_cons"] = c
            st.session_state["dados_ativos"] = a
            st.session_state["ultima_atualizacao"] = datetime.now()

            status.update(
                label="Sincronização Concluída!", state="complete", expanded=False
            )
            st.rerun()

st.divider()

# --- DASHBOARD DE PRÉ-VISUALIZAÇÃO ---
df_prod = st.session_state.get("dados_prod", {}).get("Prod", pd.DataFrame())
df_cons = st.session_state.get("dados_cons", pd.DataFrame())

if not df_cons.empty:
    # KPIs usando o componente oficial
    k1, k2, k3, k4 = st.columns(4)
    render_kpi(
        k1, "Registros Produção", f"{len(df_prod)}", "Total na aba 'Prod'", "azul"
    )
    render_kpi(
        k2, "Base Consultiva", f"{len(df_cons)}", "Registros processados", "laranja"
    )
    render_kpi(
        k3,
        "Total Equipamentos",
        f"{int(df_cons['QTDE_PRODUTOS'].sum())}",
        "Detectados em OBS",
        "verde",
    )
    render_kpi(
        k4,
        "Serviços/Venda",
        f"{df_cons['QTDE_CONSULTIVO'].mean():.2f}",
        "Média de penetração",
        "cinza",
    )

    # Abas de Dados
    tab_p, tab_c = st.tabs(["📊 Produção (Preview)", "📋 Consultivo Processado"])

    with tab_p:
        render_section_header("table_view", "Base de Produção", "Top 100")
        st.dataframe(df_prod.head(100), use_container_width=True, hide_index=True)

    with tab_c:
        render_section_header("analytics", "Base Consultiva Detalhada", "Processado")
        st.dataframe(df_cons.head(100), use_container_width=True, hide_index=True)

else:
    render_insight(
        "Clique no botão **Sincronizar Agora** para visualizar os dados das planilhas.",
        "acao",
    )
