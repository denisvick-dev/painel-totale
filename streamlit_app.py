import streamlit as st
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from components.componentes import aplicar_estilo
from components.sidebar import aplicar_sidebar_corp

# ====================================================
# 🔧 BLOCO 1: CONFIGURAÇÃO INICIAL
# ====================================================
st.set_page_config(
    page_title="Painel TOTALE",
    page_icon="assets/images/icons/totale.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ====================================================
# ⚙️ BLOCO 2: CONSTANTES GLOBAIS
# ====================================================
class Configuracoes:
    VERSAO_SISTEMA = "3.1.0"
    AMBIENTE = "Produção"
    FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
    INTERVALO_REFRESH = 60  # segundos


# ====================================================
# 🎨 BLOCO 3: CSS GLOBAL
# ====================================================
class Visual:
    @staticmethod
    def injetar_css_global():
        st.html("""
        <style>
        /* INPUTS */
        [data-testid="stSelectbox"] label p { color: #012869 !important; font-weight: bold !important; }
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            border: 2px solid #E2E8F0 !important; border-radius: 8px !important; background-color: white !important;
        }
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover { border-color: #F37C04 !important; }

        [data-testid="stDateInput"] label p { color: #012869 !important; font-weight: bold !important; }
        [data-testid="stDateInput"] div[data-baseweb="input"] > div {
            background-color: white !important; border: 2px solid #E2E8F0 !important; border-radius: 8px !important;
        }
        [data-testid="stDateInput"] div[data-baseweb="input"] > div:hover { border-color: #F37C04 !important; }
        [data-testid="stDateInput"] svg { fill: #F37C04 !important; color: #F37C04 !important; }

        /* CARDS */
        .card {
            background-color: #FFFFFF; padding: 24px; border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            border: 1px solid #F1F5F9; transition: all 0.2s ease-in-out;
        }
        .card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); }
        .status-ok { background-color: #F0FDF4; border-left: 5px solid #22C55E; }
        .status-warning { background-color: #FFF7ED; border-left: 5px solid #F37C04; }

        .hero-banner {
            background: linear-gradient(135deg, #012869 0%, #1E40AF 60%, #F37C04 100%);
            padding: 32px 40px; border-radius: 16px; color: white;
            box-shadow: 0 10px 25px rgba(1, 40, 105, 0.15); margin-bottom: 24px;
        }

        .footer {
            position: fixed; left: 0; bottom: 0; width: 100%;
            background-color: #012869; color: white; padding: 12px 20px;
            font-size: 13px; text-align: center; z-index: 999;
        }
        .block-container { padding-bottom: 5rem; }
        </style>
        """)


# ====================================================
# 🏠 BLOCO 4: PÁGINA HOME
# ====================================================
def pagina_home():
    st.markdown(
        """
        <div class="hero-banner">
            <h1 style="font-size:32px; font-weight:800; margin:0; color:#FFFFFF !important;">📊 Portal TOTALE</h1>
            <p style="font-size:14px; opacity:0.9; margin:4px 0 0 0; color:#FFFFFF !important;">
                Painéis de Produção, Indicadores e Gestão Estratégica
            </p>
        </div>
        <div class="card">
            <p style="margin:0; font-size:14px; color:#334155; line-height:1.6;">
                <b>Bem-vindo ao ambiente centralizado de dados da TOTALE.</b><br>
                Este portal fornece uma visão clara e estratégica dos processos produtivos
                e indicadores de performance, apoiando decisões com base em dados confiáveis.
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
                <p style="margin:8px 0 0 0; font-size:13px; color:#7C2D12;">
                    1️⃣ Acesse <b>🔁 Atualização de Dados</b> no menu lateral<br>
                    2️⃣ Clique em <b>Sincronizar Agora</b> para puxar as bases operacionais.
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
                <p style="margin:0; font-size:13px; color:#64748B;">
                    Monitore a eficiência e o volume produzido por técnicos e equipes em tempo real.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div class="card">
                <h4 style="margin:0 0 8px 0; color:#012869;">📈 Indicadores de Performance</h4>
                <p style="margin:0; font-size:13px; color:#64748B;">
                    Acompanhe a evolução de metas operacionais e KPIs estratégicos.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    agora = datetime.now(Configuracoes.FUSO_HORARIO)
    st.markdown(
        f"""
        <div class="footer">
            🏢 <b>Painel TOTALE</b> <span>|</span>
            🌐 {Configuracoes.AMBIENTE} <span>|</span>
            🕒 {agora.strftime("%d/%m/%Y")} • {agora.strftime("%H:%M")} BRT <span>|</span>
            🔖 v{Configuracoes.VERSAO_SISTEMA}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "_last_refresh_time" not in st.session_state:
        st.session_state["_last_refresh_time"] = time.time()
    if time.time() - st.session_state["_last_refresh_time"] > Configuracoes.INTERVALO_REFRESH:
        st.session_state["_last_refresh_time"] = time.time()
        st.rerun()


# ====================================================
# 🚀 BLOCO 5: NAVEGAÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    aplicar_estilo()
    aplicar_sidebar_corp()
    Visual.injetar_css_global()
    st.logo("assets/images/novo-logo-totale.png", size="medium")

    home_page = st.Page(pagina_home, title="Home", icon="🏠", default=True)
    envio_excel = st.Page("pages/envio_excel.py", title="Atualização de Dados", icon="🔁")

    ranking_pontos = st.Page("pages/pontos.py", title="Ranking de Pontos", icon="📈")
    qtde_os = st.Page("pages/qtde_os.py", title="Quantidade de O.S.", icon="⚡")
    consultivo = st.Page("pages/consultivo.py", title="Consultivos", icon="📋")
    gestao_ativos = st.Page("pages/gestao_ativos.py", title="Gestão de Ativos", icon="👷")
    rota_inicial = st.Page("pages/rota_inicial.py", title="Rota Inicial", icon="🗺️")
    rota_geral = st.Page("pages/rota_geral.py", title="Rota Geral", icon="🗺️")
    volumetria = st.Page("pages/volumetria.py", title="Volumetria", icon="📊")
    quebra_unif = st.Page("pages/quebra_unificada.py", title="Visão PME & Migração", icon="📉")
    assinatura = st.Page("pages/assinatura.py", title="Assinatura", icon="✉️")
    retorno = st.Page("pages/retorno.py", title="Retornos", icon="🔍")
    p_atendimento = st.Page("pages/p_atendimento.py", title="1º Atendimento", icon="🚙")
    quebra_geral = st.Page("pages/quebra_geral.py", title="Geral", icon="📉")

    paginas_agrupadas = {
        "MENU PRINCIPAL": [home_page, envio_excel],
        "CENTRAL DE PERFORMANCE": [ranking_pontos, qtde_os, consultivo],
        "COMPILADO": [gestao_ativos],
        "DISPAROS DIÁRIOS": [rota_inicial, rota_geral, volumetria, retorno, p_atendimento],
        "QUEBRA": [quebra_geral, quebra_unif],
        "UTILITÁRIOS": [assinatura],
    }

    pg = st.navigation(paginas_agrupadas)
    if pg is not None:
        pg.run()


if __name__ == "__main__":
    main()