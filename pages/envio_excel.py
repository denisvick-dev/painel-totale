import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from io import BytesIO, StringIO
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
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
    VERSAO_SISTEMA = "3.0.0"
    AMBIENTE = "Produção"
    FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
    INTERVALO_REFRESH = 60  # segundos

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

    VAZIOS = {"-", "nan", "None", "", "NaN"}

    IMGS_CARROSSEL = [
        "assets/images/informe_vagas.jpeg",
        "assets/images/consultivo_copa.jpg",
        "assets/images/indicacao_totale.png",
    ]


# ====================================================
# 🧠 BLOCO 3: PROCESSAMENTO DE DADOS (ENVIO EXCEL)
# ====================================================
class ProcessadorDeDados:
    @staticmethod
    def _normalizar_serie(serie: pd.Series) -> pd.Series:
        return (
            serie.astype(str)
            .str.strip()
            .replace(list(Configuracoes.VAZIOS), "")
            .fillna("")
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
    def baixar_e_processar():
        try:
            prod_raw = pd.read_excel(
                Configuracoes.URL_PROD, sheet_name=None, engine="openpyxl"
            )
        except Exception as e:
            st.error(f"Erro ao baixar Produção: {e}")
            prod_raw = {}

        cons_raw = {}
        try:
            resposta = requests.get(Configuracoes.URL_CONS)
            resposta.raise_for_status()
            if "text/html" in resposta.headers.get("Content-Type", ""):
                st.error("❌ O Google Drive bloqueou o download automático do CSV.")
            else:
                try:
                    df_csv = pd.read_csv(StringIO(resposta.text), sep=",")
                except Exception:
                    df_csv = pd.read_csv(
                        BytesIO(resposta.content),
                        sep=";",
                        encoding="utf-8",
                        engine="python",
                    )
                cons_raw = {"Aba_Dinamica": df_csv}
        except Exception as e:
            st.error(f"❌ Erro ao baixar ou ler o arquivo CSV: {e}")

        try:
            ativos = pd.read_csv(Configuracoes.URL_ATIVOS)
            ativos.columns = ativos.columns.str.strip()
        except Exception as e:
            st.error(f"Erro ao baixar ATIVOS: {e}")
            ativos = pd.DataFrame()

        if cons_raw and isinstance(cons_raw, dict):
            cons = cons_raw[list(cons_raw.keys())[0]]
        else:
            cons = pd.DataFrame()

        if cons.empty:
            return prod_raw, {"Consultivo": pd.DataFrame()}, ativos

        cons.columns = cons.columns.str.strip()

        if "OBSERVACAO" in cons.columns:
            cons["LISTA_PRODUTOS"] = (
                cons["OBSERVACAO"].fillna("").astype(str).str.findall(r"\b\d{9,12}\b")
            )
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

        if (
            not ativos.empty
            and "Login" in ativos.columns
            and "LOGIN NETSALES" in cons.columns
        ):
            ativos_limpo = ativos[["Login", "Monitor", "U.N.", "Base"]].drop_duplicates(
                subset=["Login"]
            )
            cons = pd.merge(
                cons,
                ativos_limpo,
                left_on="LOGIN NETSALES",
                right_on="Login",
                how="left",
            ).drop(columns=["Login"])
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
        /* CSS DA SIDEBAR E INPUTS */
        .stSidebar h2 { color: #012869 !important; font-size: 26px !important; font-weight: 700 !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }
        .stSidebar [data-testid="stWidgetLabel"] p { color: #000047 !important; font-size: 16px !important; font-weight: 600 !important; }
        .stSidebar [data-baseweb="tag"] { background-color: #012869 !important; color: #FFFFFF !important; border-radius: 4px !important; }
        .stSidebar [data-baseweb="tag"] svg { fill: #FFFFFF !important; }
        [data-testid="stSidebar"] { background: linear-gradient(180deg, rgb(255, 190, 100) 0%, rgb(243, 124, 4) 100%) !important; }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] a {
            color: white !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        }
        [data-testid="stSidebar"] .stButton button { background-color: #012869 !important; color: white !important; border-radius: 4px !important; border: none !important; }
        [data-testid="stSidebar"] .stButton button:hover { background-color: #FFC48A !important; border-color: #FFC48A !important; }
        
        [data-testid="stSelectbox"] label p { color: #012869 !important; font-weight: bold !important; }
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div { border: 2px solid #012869 !important; border-radius: 6px !important; background-color: white !important; }
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover, [data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within { border-color: #F37C04 !important; box-shadow: 0 0 0 1px #F37C04 !important; }
        [data-testid="stSelectbox"] div[data-baseweb="select"] div { color: #012869 !important; font-weight: 500 !important; }
        [data-testid="stSelectbox"] div[data-baseweb="select"] svg { fill: #F37C04 !important; }
        ul[role="listbox"] { background-color: white !important; border: 2px solid #012869 !important; border-radius: 6px !important; }
        ul[role="listbox"] li { color: #012869 !important; }
        ul[role="listbox"] li:hover, ul[role="listbox"] li[aria-selected="true"] { background-color: #F37C04 !important; color: white !important; font-weight: bold !important; }
        
        [data-testid="stDateInput"] label p { color: #012869 !important; font-weight: bold !important; }
        [data-testid="stDateInput"] div[data-baseweb="input"] > div { background-color: white !important; border: 2px solid #012869 !important; border-radius: 6px !important; }
        [data-testid="stDateInput"] div[data-baseweb="input"] > div:hover, [data-testid="stDateInput"] div[data-baseweb="input"] > div:focus-within { border-color: #F37C04 !important; box-shadow: 0 0 0 1px #F37C04 !important; }
        [data-testid="stDateInput"] input { color: #012869 !important; font-weight: 500 !important; }
        [data-testid="stDateInput"] svg { fill: #F37C04 !important; color: #F37C04 !important; }

        /* UTILITARIOS GERAIS */
        .card { background-color: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border: 1px solid #E0E0E0; }
        .status-ok { background-color: #E6F4EA; border-left: 6px solid #2E7D32; }
        .status-warning { background-color: #FFF4E5; border-left: 6px solid #F37C04; }
        </style>
        """)

    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul") -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px; font-family: 'Segoe UI', Arial, sans-serif;">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']};"><b>{titulo}</b></p>
            <h2 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900;">{valor}</h2>
        </div>
        """


# ====================================================
# 🏠 BLOCO 5: PÁGINA HOME
# ====================================================
def pagina_home():
    st.markdown(
        """
        <style>
        .hero-home {
            background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
            padding: 32px 40px; border-radius: 16px; color: white; box-shadow: 0 10px 40px rgba(1, 40, 105, 0.25);
            margin-bottom: 24px; position: relative; overflow: hidden;
        }
        .hero-home::before {
            content: ''; position: absolute; top: -50%; right: -10%; width: 400px; height: 400px; background: rgba(255,255,255,0.05); border-radius: 50%;
        }
        .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #012869; color: white; padding: 12px 20px; font-size: 14px; text-align: center; z-index: 999; box-shadow: 0 -2px 10px rgba(0,0,0,0.2); }
        .block-container { padding-bottom: 4.5rem; }
        </style>
        <div class="hero-home">
            <div style="position:relative;z-index:2;">
                <h1 style="font-size:34px; font-weight:800; margin:0;">📊 Portal TOTALE</h1>
                <p style="font-size:15px; opacity:0.92; margin:6px 0 0 0;">Painéis de Produção, Indicadores e Gestão Estratégica</p>
            </div>
        </div>
        <div class="card">
            <b>Bem-vindo ao ambiente centralizado de dados da TOTALE.</b><br><br>
            Este portal fornece uma visão clara e estratégica dos processos produtivos e indicadores de performance, apoiando decisões com base em dados confiáveis.
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
            <b>⚠️ Sistema aguardando atualização de dados</b><br><br>
            1️⃣ Acesse <b>🔁 Atualização de Dados</b> no menu lateral<br>
            2️⃣ Clique em <b>Atualizar Agora</b>
        </div><br>
        """,
            unsafe_allow_html=True,
        )
    else:
        ultima = st.session_state.get("ultima_atualizacao")
        hora = ultima.strftime("%d/%m/%Y às %H:%M:%S") if ultima else "Recente"
        st.markdown(
            f"""
        <div class="card status-ok">
            ✅ <b>Sistema atualizado e pronto para uso</b><br>Última sincronização: {hora}
        </div><br>
        """,
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            '<div class="card"><h4>⚙️ Produção</h4>Monitore eficiência operacional, volume produzido e desempenho.</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            '<div class="card"><h4>📈 Indicadores Estratégicos</h4>Acompanhe metas, resultados financeiros e KPIs.</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Carrossel
    st.subheader("📢 Comunicados Internos")
    if "slide_index" not in st.session_state:
        st.session_state.slide_index = 0
    total = len(Configuracoes.IMGS_CARROSSEL)

    col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
    with col_c2:
        st.markdown('<div class="card" style="padding:10px;">', unsafe_allow_html=True)
        st.image(
            Configuracoes.IMGS_CARROSSEL[st.session_state.slide_index],
            use_container_width=True,
        )
        st.markdown(
            f"<div style='text-align:center; font-size:14px; color:#666;'>Slide {st.session_state.slide_index + 1} de {total}</div>",
            unsafe_allow_html=True,
        )

        btn1, btn2 = st.columns(2)
        if btn1.button("⬅ Anterior", use_container_width=True):
            st.session_state.slide_index = (st.session_state.slide_index - 1) % total
        if btn2.button("Próximo ➡", use_container_width=True):
            st.session_state.slide_index = (st.session_state.slide_index + 1) % total
        st.markdown("</div>", unsafe_allow_html=True)

    # Footer
    agora = datetime.now(Configuracoes.FUSO_HORARIO)
    st.markdown(
        f"""
        <div class="footer">
            🏢 <b>Painel TOTALE</b> <span>|</span> 🌐 {Configuracoes.AMBIENTE} <span>|</span> 🕒 {agora.strftime("%d/%m/%Y")} • {agora.strftime("%H:%M")} BRT <span>|</span> 🔖 v{Configuracoes.VERSAO_SISTEMA}
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Auto Refresh
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
        <style>
        .hero-excel {
            background: linear-gradient(90deg, #1E293B 0%, #334155 25%, #64748B 55%, #94A3B8 75%, #CBD5E1 92%, #94A3B8 100%);
            padding: 32px 48px; border-radius: 12px; color: white; margin-bottom: 24px; position: relative; overflow: hidden;
        }
        </style>
        <div class="hero-excel">
            <h1 style="font-size:36px; font-weight:800; margin:0;">🔁 Central de Atualização de Dados</h1>
            <p style="font-size:14px; margin:8px 0 0 0; opacity:0.9;">Sincronização e gestão de bases operacionais</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    def executar_atualizacao():
        status = st.empty()
        barra = st.progress(0)
        try:
            status.info("⏳ Fazendo download e processando dados em nuvem. Aguarde...")
            barra.progress(20)
            ProcessadorDeDados.baixar_e_processar.clear()
            p_raw, c_raw, a_raw = ProcessadorDeDados.baixar_e_processar()
            barra.progress(90)

            st.session_state["dados_prod"] = p_raw
            st.session_state["dados_cons"] = c_raw
            st.session_state["dados_ativos"] = a_raw
            st.session_state["ultima_atualizacao"] = datetime.now(
                Configuracoes.FUSO_HORARIO
            )

            barra.progress(100)
            time.sleep(0.5)
            status.empty()
            barra.empty()
            return True
        except Exception as e:
            status.empty()
            barra.empty()
            st.error(f"❌ Erro na atualização: {e}")
            return False

    if "dados_cons" not in st.session_state:
        executar_atualizacao()

    col_btn, _ = st.columns([1, 4])
    if col_btn.button("🔄 Atualizar Agora", use_container_width=True, type="primary"):
        if executar_atualizacao():
            st.success("✅ Dados atualizados com sucesso!")

    st.divider()

    df_prod = st.session_state.get("dados_prod", {}).get("Prod", pd.DataFrame())
    df_cons = st.session_state.get("dados_cons", {}).get("Consultivo", pd.DataFrame())
    ultima_data = st.session_state.get("ultima_atualizacao")
    hora_str = (
        ultima_data.strftime("%d/%m/%Y às %H:%M:%S")
        if ultima_data
        else "Nunca atualizado"
    )

    aba1, aba2 = st.tabs(
        ["📊 Pré-visualização: Produção", "📋 Pré-visualização: Consultivos"]
    )

    with aba1:
        c1, c2, c3 = st.columns(3)
        c1.markdown(
            Visual.criar_card(
                "Total Registros", f"{len(df_prod):,}".replace(",", "."), "azul"
            ),
            unsafe_allow_html=True,
        )
        c2.markdown(
            Visual.criar_card("Total Colunas", str(len(df_prod.columns)), "cinza"),
            unsafe_allow_html=True,
        )
        c3.markdown(
            Visual.criar_card("Última Sincronização", hora_str, "verde"),
            unsafe_allow_html=True,
        )
        if not df_prod.empty:
            st.dataframe(
                df_prod.head(100), use_container_width=True, height=400, hide_index=True
            )
        else:
            st.warning("⚠️ Nenhuma aba chamada 'Prod' encontrada.")

    with aba2:
        c4, c5, c6 = st.columns(3)
        c4.markdown(
            Visual.criar_card(
                "Total Registros", f"{len(df_cons):,}".replace(",", "."), "azul"
            ),
            unsafe_allow_html=True,
        )
        c5.markdown(
            Visual.criar_card("Total Colunas", str(len(df_cons.columns)), "cinza"),
            unsafe_allow_html=True,
        )
        c6.markdown(
            Visual.criar_card("Última Sincronização", hora_str, "verde"),
            unsafe_allow_html=True,
        )
        if not df_cons.empty:
            st.dataframe(
                df_cons.head(100), use_container_width=True, height=400, hide_index=True
            )
        else:
            st.warning("⚠️ Nenhuma aba encontrada ou o arquivo CSV está vazio.")


# ====================================================
# 🚀 BLOCO 7: ARQUITETURA PRINCIPAL DE NAVEGAÇÃO
# ====================================================
def main():
    aplicar_estilo()
    Visual.injetar_css_global()
    st.logo("assets/images/novo-logo-totale.png", size="medium")

    # Mapeamento Híbrido (Funções unificadas + Arquivos)
    home_page = st.Page(pagina_home, title="Home", icon="🏠", default=True)
    envio_excel = st.Page(pagina_envio_excel, title="Atualização de Dados", icon="🔁")

    # Outras Páginas Físicas (Essas podem continuar como arquivos)
    ranking_pontos = st.Page("pages/pontos.py", title="Ranking de Pontos", icon="📈")
    qtde_os = st.Page("pages/qtde_os.py", title="Quantidade de O.S.", icon="📊")
    consultivo = st.Page("pages/consultivo.py", title="Consultivos", icon="📋")
    gestao_ativos = st.Page(
        "pages/gestao_ativos.py", title="Gestão de Ativos", icon="👷"
    )
    visao_tec_prod = st.Page("pages/visao_tecnico_prod.py", title="Produção", icon="🛠️")
    visao_tec_cons = st.Page(
        "pages/visao_tecnico_cons.py", title="Consultivo", icon="🗣️"
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
        "VISÃO POR TÉCNICO": [visao_tec_prod, visao_tec_cons],
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
    pg.run()


if __name__ == "__main__":
    main()
