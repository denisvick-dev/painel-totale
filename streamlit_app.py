import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from io import BytesIO, StringIO
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Tuple, Dict, Any
from components.componentes import aplicar_estilo

# ====================================================
# 🔧 BLOCO 1: CONFIGURAÇÃO INICIAL DA PÁGINA
# ====================================================
st.set_page_config(
    page_title="Painel TOTALE",
    page_icon="assets/images/icons/totale.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ====================================================
# ⚙️ BLOCO 2: CONSTANTES E CONFIGURAÇÕES GLOBAIS
# ====================================================
class Configuracoes:
    VERSAO_SISTEMA = "3.1.0"
    AMBIENTE = "Produção"
    FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
    INTERVALO_REFRESH = 60  # segundos
    TIMEOUT_REQUISICAO = 15  # segundos

    TEMAS_CARD = {
        "azul": {
            "fundo": "#F0F9FF",
            "texto": "#0369A1",
            "borda": "#0EA5E9",
            "titulo": "#075985",
        },
        "verde": {
            "fundo": "#F0FDF4",
            "texto": "#15803D",
            "borda": "#22C55E",
            "titulo": "#166534",
        },
        "cinza": {
            "fundo": "#F8FAFC",
            "texto": "#334155",
            "borda": "#94A3B8",
            "titulo": "#64748B",
        },
    }

    URL_PROD = "https://docs.google.com/spreadsheets/d/11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v/export?format=xlsx"
    URL_CONS = "https://drive.google.com/uc?id=1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs&export=download"
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/export?format=csv"

    VAZIOS = {"-", "nan", "None", "", "NaN", "nat", "NAT", "<NA>"}


# ====================================================
# 🧠 BLOCO 3: PROCESSAMENTO DE DADOS (ENVIO EXCEL)
# ====================================================
class ProcessadorDeDados:
    @staticmethod
    def _normalizar_serie(serie: pd.Series) -> pd.Series:
        # Corrige o problema de converter nulos em string literal "nan"
        return (
            serie.fillna("")
            .astype(str)
            .str.strip()
            .replace(list(Configuracoes.VAZIOS), "")
        )

    @staticmethod
    def tratar_planos_vetorizado(df: pd.DataFrame) -> pd.DataFrame:
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df

        tv_bruta = (
            df["PLANO TV"]
            .astype(str)
            .str.strip()
            .replace("SERVIÇOS AVANÇADOS", "CLARO TV+ BOX")
        )
        internet_bruta = df["PLANO INTERNET"].astype(str).str.strip()
        partes = internet_bruta.str.split(".", n=1, expand=True)

        internet_limpa = ProcessadorDeDados._normalizar_serie(partes[0])
        tv_do_internet = (
            ProcessadorDeDados._normalizar_serie(partes[1])
            if partes.shape[1] > 1
            else pd.Series("", index=df.index, dtype=str)
        )
        tv_normalizada = ProcessadorDeDados._normalizar_serie(tv_bruta)

        tv_limpa = pd.Series(
            np.where(tv_normalizada != "", tv_normalizada, tv_do_internet),
            index=df.index,
            dtype=str,
        )

        tem_tv = tv_limpa != ""
        tem_internet = internet_limpa != ""

        df["QTDE_CONSULTIVO"] = tem_tv.astype(int) + tem_internet.astype(int)
        condicoes = [
            tem_tv & tem_internet,
            tem_tv & ~tem_internet,
            ~tem_tv & tem_internet,
        ]
        opcoes = [tv_limpa + " & " + internet_limpa, tv_limpa, internet_limpa]

        df["TIPO SERVIÇO"] = np.select(condicoes, opcoes, default="Sem Tipo")
        df["PLANO TV"] = tv_limpa
        df["PLANO INTERNET"] = internet_limpa

        return df

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)
    def baixar_e_processar() -> (
        Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame], pd.DataFrame]
    ):
        # Download Produção
        try:
            prod_raw = pd.read_excel(
                Configuracoes.URL_PROD, sheet_name=None, engine="openpyxl"
            )
        except Exception as e:
            st.error(f"Erro ao baixar planilha de Produção: {e}")
            prod_raw = {}

        # Download Consultivo
        cons_raw = {}
        try:
            resposta = requests.get(
                Configuracoes.URL_CONS, timeout=Configuracoes.TIMEOUT_REQUISICAO
            )
            resposta.raise_for_status()
            if "text/html" in resposta.headers.get("Content-Type", "").lower():
                st.error(
                    "❌ Download do Consultivo bloqueado pelas diretrizes do Google Drive."
                )
            else:
                try:
                    df_csv = pd.read_csv(StringIO(resposta.text), sep=",", dtype=str)
                except Exception:
                    df_csv = pd.read_csv(
                        BytesIO(resposta.content),
                        sep=";",
                        encoding="utf-8",
                        engine="python",
                        dtype=str,
                    )
                cons_raw = {"Aba_Dinamica": df_csv}
        except Exception as e:
            st.error(f"❌ Erro na integração da base de Consultivos: {e}")

        # Download Ativos
        try:
            ativos = pd.read_csv(Configuracoes.URL_ATIVOS, dtype=str)
            ativos.columns = ativos.columns.str.strip()
        except Exception as e:
            st.error(f"Erro ao baixar planilha de Ativos: {e}")
            ativos = pd.DataFrame()

        # Extração
        cons = (
            cons_raw.get("Aba_Dinamica", pd.DataFrame()) if cons_raw else pd.DataFrame()
        )
        if cons.empty:
            return prod_raw, {"Consultivo": pd.DataFrame()}, ativos

        cons.columns = cons.columns.str.strip()

        if "OBSERVACAO" in cons.columns:
            obs_limpo = cons["OBSERVACAO"].fillna("").astype(str)
            cons["LISTA_PRODUTOS"] = obs_limpo.str.findall(r"\b\d{9,12}\b")
            cons["QTDE_PRODUTOS"] = cons["LISTA_PRODUTOS"].apply(len)
        else:
            cons["LISTA_PRODUTOS"] = [[] for _ in range(len(cons))]
            cons["QTDE_PRODUTOS"] = 0

        cons = ProcessadorDeDados.tratar_planos_vetorizado(cons)

        tipo_servico = (
            cons.get("TIPO SERVIÇO", pd.Series("", index=cons.index))
            .fillna("")
            .astype(str)
        )
        qtde_prod = cons["QTDE_PRODUTOS"].fillna(0).astype(int)

        is_combinado = tipo_servico.str.contains("&", case=False, regex=False)
        tem_tv = tipo_servico.str.contains("TV", case=False, regex=False)
        tem_virtua = tipo_servico.str.contains(r"MEGA|GIGA", case=False, regex=True)

        cons["QTDE_TV"] = np.where(
            is_combinado, tem_tv.astype(int), tem_tv.astype(int) * qtde_prod
        )
        cons["QTDE_VIRTUA"] = np.where(
            is_combinado, tem_virtua.astype(int), tem_virtua.astype(int) * qtde_prod
        )
        cons["QTDE_MESH"] = (qtde_prod - cons["QTDE_TV"] - cons["QTDE_VIRTUA"]).clip(
            lower=0
        )

        # Merge de Ativos
        if (
            not ativos.empty
            and "Login" in ativos.columns
            and "LOGIN NETSALES" in cons.columns
        ):
            ativos_limpo = (
                ativos[["Login", "Monitor", "U.N.", "Base"]]
                .dropna(subset=["Login"])
                .drop_duplicates(subset=["Login"])
                .copy()
            )
            # Normaliza chaves de cruzamento
            ativos_limpo["Login_JOIN"] = (
                ativos_limpo["Login"].astype(str).str.strip().str.upper()
            )
            cons["Login_JOIN"] = (
                cons["LOGIN NETSALES"].astype(str).str.strip().str.upper()
            )

            cons = pd.merge(
                cons,
                ativos_limpo.drop(columns=["Login"]),
                on="Login_JOIN",
                how="left",
            ).drop(columns=["Login_JOIN"])
            cons["Monitor"] = cons["Monitor"].fillna("Não Identificado")

        return prod_raw, {"Consultivo": cons}, ativos


# ====================================================
# 🎨 BLOCO 4: COMPONENTES VISUAIS E CSS GLOBAL
# ====================================================
class Visual:
    @staticmethod
    def injetar_css_global():
        st.html("""
        <style>
        /* CONFIGURAÇÃO DA SIDEBAR */
        .stSidebar h2 { color: #012869 !important; font-size: 24px !important; font-weight: 700 !important; }
        .stSidebar [data-testid="stWidgetLabel"] p { color: #000047 !important; font-size: 15px !important; font-weight: 600 !important; }
        .stSidebar [data-baseweb="tag"] { background-color: #012869 !important; color: #FFFFFF !important; border-radius: 4px !important; }
        .stSidebar [data-baseweb="tag"] svg { fill: #FFFFFF !important; }
        [data-testid="stSidebar"] { background: linear-gradient(180deg, #FFBE64 0%, #F37C04 100%) !important; }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] a {
            color: white !important;
        }
        [data-testid="stSidebar"] .stButton button { background-color: #012869 !important; color: white !important; border-radius: 6px !important; border: none !important; }
        [data-testid="stSidebar"] .stButton button:hover { background-color: #FFC48A !important; color: #012869 !important; }
        
        /* SELECTBOXES E ENTRADAS */
        [data-testid="stSelectbox"] label p { color: #012869 !important; font-weight: bold !important; }
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div { border: 2px solid #E2E8F0 !important; border-radius: 8px !important; background-color: white !important; }
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover { border-color: #F37C04 !important; }
        
        /* CARDS E GRIDS */
        .card { background-color: #FFFFFF; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03); border: 1px solid #F1F5F9; transition: all 0.2s ease-in-out; }
        .card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); }
        .status-ok { background-color: #F0FDF4; border-left: 5px solid #22C55E; }
        .status-warning { background-color: #FFF7ED; border-left: 5px solid #F37C04; }
        
        /* LAYOUT ATUALIZAÇÕES (EXCEL) */
        .hero-banner {
            background: linear-gradient(135deg, #012869 0%, #1E40AF 60%, #F37C04 100%);
            padding: 32px 40px; border-radius: 16px; color: white; box-shadow: 0 10px 25px rgba(1, 40, 105, 0.15); margin-bottom: 24px;
        }
        .toolbar-container {
            background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 16px; display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px;
        }
        .status-pill {
            display: inline-flex; align-items: center; justify-content: center; border-radius: 9999px; padding: 6px 16px; font-size: 11px; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; border: 1px solid transparent; min-height: 38px; width: 100%;
        }
        .status-pill.ok { background-color: #DCFCE7; color: #15803D; border-color: #86EFAC; }
        .status-pill.warn { background-color: #FEF3C7; color: #D97706; border-color: #FCD34D; }
        .status-pill.alert { background-color: #FEE2E2; color: #B91C1C; border-color: #FCA5A5; }
        
        .upload-dashed {
            background-color: #F8FAFC; border: 2px dashed #CBD5E1; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 20px;
        }
        .kpi-metric-card {
            background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); height: 100%;
        }
        .kpi-metric-card .label { font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
        .kpi-metric-card .value { font-size: 24px; font-weight: 800; color: #0F172A; margin: 0; }
        .kpi-metric-card .meta { font-size: 12px; color: #94A3B8; margin-top: 4px; }
        
        /* RODAPÉ E GERAIS */
        .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #012869; color: white; padding: 12px 20px; font-size: 13px; text-align: center; z-index: 999; }
        .block-container { padding-bottom: 5rem; }
        </style>
        """)

    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul") -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 18px; border-radius: 10px; border-left: 5px solid {cores['borda']}; margin-bottom: 12px; font-family: sans-serif;">
            <p style="margin: 0; font-size: 13px; color: {cores['titulo']}; font-weight: 600;">{titulo}</p>
            <h3 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 800; font-size: 22px;">{valor}</h3>
        </div>
        """


# ====================================================
# 🏠 BLOCO 5: PÁGINA HOME
# ====================================================
def pagina_home():
    st.markdown(
        """
        <div class="hero-banner">
            <h1 style="font-size:32px; font-weight:800; margin:0; color: #FFFFFF !important;">📊 Portal TOTALE</h1>
            <p style="font-size:14px; opacity:0.9; margin:4px 0 0 0; color: #FFFFFF !important;">Painéis de Produção, Indicadores e Gestão Estratégica</p>
        </div>
        <div class="card">
            <p style="margin:0; font-size:14px; color:#334155; line-height:1.6;">
                <b>Bem-vindo ao ambiente centralizado de dados da TOTALE.</b><br>
                Este portal fornece uma visão clara e estratégica dos processos produtivos e indicadores de performance, apoiando decisões com base em dados confiáveis.
            </p>
        </div><br>
    """,
        unsafe_allow_html=True,
    )

    if not (
        "dados_prod" in st.session_state and st.session_state["dados_prod"] is not None
    ):
        st.markdown(
            """
        <div class="card status-warning">
            <b style="color:#C2410C;">⚠️ Sistema aguardando atualização de dados</b><br>
            <p style="margin: 8px 0 0 0; font-size:13px; color:#7C2D12;">
                1️⃣ Acesse <b>🔁 Atualização de Dados</b> no menu lateral<br>
                2️⃣ Clique em <b>Atualizar Agora</b> para puxar as bases operacionais.
            </p>
        </div><br>
        """,
            unsafe_allow_html=True,
        )
    else:
        ultima = st.session_state.get("ultima_atualizacao")
        hora = ultima.strftime("%d/%m/%Y às %H:%M:%S") if ultima else "Sincronizado"
        st.markdown(
            f"""
        <div class="card status-ok">
            <b style="color:#15803D;">✅ Sistema operacional e atualizado</b><br>
            <span style="font-size:13px; color:#166534;">Última sincronização validada em {hora}</span>
        </div><br>
        """,
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        st.markdown(
            """
            <div class="card">
                <h4 style="margin:0 0 8px 0; color:#012869;">⚙️ Produção Operacional</h4>
                <p style="margin:0; font-size:13px; color:#64748B;">Monitore a eficiência e volume produzido por técnicos e equipes em tempo real.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div class="card">
                <h4 style="margin:0 0 8px 0; color:#012869;">📈 Indicadores de Performance</h4>
                <p style="margin:0; font-size:13px; color:#64748B;">Acompanhe a evolução de metas operacionais e KPIs estratégicos.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # Rodapé fixo
    agora = datetime.now(Configuracoes.FUSO_HORARIO)
    st.markdown(
        f"""
        <div class="footer">
            🏢 <b>Painel TOTALE</b> <span>|</span> 🌐 {Configuracoes.AMBIENTE} <span>|</span> 🕒 {agora.strftime("%d/%m/%Y")} • {agora.strftime("%H:%M")} BRT <span>|</span> 🔖 v{Configuracoes.VERSAO_SISTEMA}
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Autorefresh Inteligente
    if "_last_refresh_time" not in st.session_state:
        st.session_state["_last_refresh_time"] = time.time()
    if (
        time.time() - st.session_state["_last_refresh_time"]
        > Configuracoes.INTERVALO_REFRESH
    ):
        st.session_state["_last_refresh_time"] = time.time()
        st.rerun()


# ====================================================
# 🔁 BLOCO 6: PÁGINA DE ATUALIZAÇÃO (EXCEL)
# ====================================================
def pagina_envio_excel():
    st.markdown(
        """
        <div class="hero-banner">
            <h1 style="font-size:32px; font-weight:800; margin:0; color: #FFFFFF !important;">🔁 Central de Atualização de Dados</h1>
            <p style="font-size:14px; opacity:0.9; margin:4px 0 0 0; color: #FFFFFF !important;">Controle central de sincronização de bases e uploads manuais</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    def executar_atualizacao() -> bool:
        status = st.empty()
        barra = st.progress(0)
        st.session_state["sync_status"] = {"label": "Sincronizando...", "tone": "warn"}
        try:
            status.info("⏳ Fazendo download e processando dados em nuvem. Aguarde...")
            barra.progress(20)
            ProcessadorDeDados.baixar_e_processar.clear()
            p_raw, c_raw, a_raw = ProcessadorDeDados.baixar_e_processar()
            barra.progress(85)

            st.session_state["dados_prod"] = p_raw
            st.session_state["dados_cons"] = c_raw
            st.session_state["dados_ativos"] = a_raw
            st.session_state["ultima_atualizacao"] = datetime.now(
                Configuracoes.FUSO_HORARIO
            )
            st.session_state["sync_status"] = {"label": "Sincronizado", "tone": "ok"}

            barra.progress(100)
            time.sleep(0.4)
            status.empty()
            barra.empty()
            return True
        except Exception as e:
            st.session_state["sync_status"] = {
                "label": "Falha na Rede",
                "tone": "alert",
            }
            status.empty()
            barra.empty()
            st.error(f"❌ Erro durante o processamento remoto: {e}")
            return False

    if "dados_cons" not in st.session_state:
        executar_atualizacao()

    # Barra de ferramentas limpa
    st.markdown('<div class="toolbar-container">', unsafe_allow_html=True)
    tb_col1, tb_col2 = st.columns([3, 1])
    with tb_col1:
        if st.button(
            "🔄 Executar Sincronização em Nuvem",
            use_container_width=True,
            type="primary",
        ):
            if executar_atualizacao():
                st.success("✅ Bases atualizadas!")
                st.rerun()
    with tb_col2:
        st_cfg = st.session_state.get("sync_status", {"label": "Pronto", "tone": "ok"})
        st.markdown(
            f'<div class="status-pill {st_cfg["tone"]}">{st_cfg["label"]}</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    # Upload manual de revisão rápida
    st.markdown('<div class="upload-dashed">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "📤 Arraste ou anexe um arquivo local para validação temporária",
        type=["xlsx", "csv"],
        label_visibility="collapsed",
    )
    if uploaded_file:
        try:
            df_upload = (
                pd.read_csv(uploaded_file)
                if uploaded_file.name.lower().endswith(".csv")
                else pd.read_excel(uploaded_file)
            )
            st.session_state["arquivo_upload"] = uploaded_file.name
            st.session_state["dados_upload"] = df_upload
            st.success(
                f"Arquivo local carregado: {uploaded_file.name} ({len(df_upload):,} registros)"
            )
        except Exception as e:
            st.error(f"Falha ao ler o arquivo importado: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

    # Métricas Operacionais
    df_prod = st.session_state.get("dados_prod", {}).get("Prod", pd.DataFrame())
    df_cons = st.session_state.get("dados_cons", {}).get("Consultivo", pd.DataFrame())
    ultima_data = st.session_state.get("ultima_atualizacao")
    hora_str = (
        ultima_data.strftime("%d/%m/%Y às %H:%M:%S") if ultima_data else "Pendente"
    )

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.markdown(
            f"""
            <div class="kpi-metric-card">
                <div class="label">Última Sincronização</div>
                <div class="value">{hora_str}</div>
                <div class="meta">Origem: Google Sheets & Drive</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi2:
        st.markdown(
            f"""
            <div class="kpi-metric-card">
                <div class="label">Volume Produção</div>
                <div class="value">{len(df_prod):,}</div>
                <div class="meta">Registros de Ordens Operacionais</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi3:
        st.markdown(
            f"""
            <div class="kpi-metric-card">
                <div class="label">Volume Consultivos</div>
                <div class="value">{len(df_cons):,}</div>
                <div class="meta">Registros de Vendas Processadas</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    aba1, aba2 = st.tabs(["📊 Base de Produção (Aba: Prod)", "📋 Base de Consultivos"])
    with aba1:
        if not df_prod.empty:
            st.dataframe(
                df_prod.head(100), use_container_width=True, height=350, hide_index=True
            )
        else:
            st.warning("⚠️ Nenhuma base operacional detectada na aba 'Prod'.")

    with aba2:
        if not df_cons.empty:
            st.dataframe(
                df_cons.head(100), use_container_width=True, height=350, hide_index=True
            )
        else:
            st.warning("⚠️ Sem registros ou arquivo CSV consultivo vazio.")


# ====================================================
# 🚀 BLOCO 7: ARQUITETURA PRINCIPAL DE NAVEGAÇÃO
# ====================================================
def main() -> None:
    aplicar_estilo()
    Visual.injetar_css_global()
    st.logo("assets/images/novo-logo-totale.png", size="medium")

    # Mapeamento Híbrido (Funções unificadas + Arquivos)
    home_page = st.Page(pagina_home, title="Home", icon="🏠", default=True)
    envio_excel = st.Page(pagina_envio_excel, title="Atualização de Dados", icon="🔁")

    # Demais Páginas Operacionais
    ranking_pontos = st.Page("pages/pontos.py", title="Ranking de Pontos", icon="📈")
    qtde_os = st.Page("pages/qtde_os.py", title="Quantidade de O.S.", icon="📊")
    consultivo = st.Page("pages/consultivo.py", title="Consultivos", icon="📋")
    gestao_ativos = st.Page(
        "pages/gestao_ativos.py", title="Gestão de Ativos", icon="👷"
    )
    rota_inicial = st.Page("pages/rota_inicial.py", title="Rota Inicial", icon="🗺️")
    rota_geral = st.Page("pages/rota_geral.py", title="Rota Geral", icon="🗺️")
    volumetria = st.Page("pages/volumetria.py", title="Volumetria", icon="📊")
    quebra_unif = st.Page(
        "pages/quebra_unificada.py", title="Visão PME & Migração", icon="📉"
    )
    assinatura = st.Page("pages/assinatura.py", title="Assinatura", icon="✉️")
    retorno = st.Page("pages/retorno.py", title="Retornos", icon="📜")
    p_atendimento = st.Page("pages/p_atendimento.py", title="1º Atendimento", icon="🚙")
    quebra_geral = st.Page("pages/quebra_geral.py", title="Geral", icon="📉")

    paginas_agrupadas = {
        "MENU PRINCIPAL": [home_page, envio_excel],
        "CENTRAL DE PERFORMANCE": [ranking_pontos, qtde_os, consultivo],
        "COMPILADO": [gestao_ativos],
        "DISPAROS DIÁRIOS": [
            rota_inicial,
            rota_geral,
            volumetria,
            retorno,
            p_atendimento,
        ],
        "QUEBRA": [quebra_geral, quebra_unif],
        "UTILITÁRIOS": [assinatura],
    }

    pg = st.navigation(paginas_agrupadas)
    if pg is not None:
        pg.run()


if __name__ == "__main__":
    main()