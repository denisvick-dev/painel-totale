import streamlit as st
import pandas as pd
from components.componentes import aplicar_estilo

# ✅ SEMPRE O PRIMEIRO COMANDO STREAMLIT
st.set_page_config(
    page_title="Painéis de Produção TOTALE",
    page_icon="assets/images/icons/totale.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ✅ DEPOIS do set_page_config
aplicar_estilo()

# ✅ DEPOIS do set_page_config
st.html("""
    <style>
    /* CRIAÇÃO DE ESTILOS PARA A SIDEBAR */
    
    .stSidebar h2 {
        color: #012869 !important;
        font-size: 26px !important;
        font-weight: 700 !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }

    .stSidebar [data-testid="stWidgetLabel"] p {
        color: #000047 !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }

    .stSidebar [data-baseweb="tag"] {
        background-color: #012869 !important;
        color: #FFFFFF !important;
        border-radius: 4px !important;
    }

    .stSidebar [data-baseweb="tag"] svg {
        fill: #FFFFFF !important;
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgb(255, 190, 100) 0%, rgb(243, 124, 4) 100%) !important;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] a {
        color: white !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
    }
    
    [data-testid="stSidebar"] .stButton button {
        background-color: #012869 !important;
        color: white !important;
        border-radius: 4px !important;
        border: none !important;    
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        background-color: #FFC48A !important;
        border-color: #FFC48A !important;
    }
    
    /* CRIAÇÃO DE ESTILOS PARA O SELECTBOX */
    
    [data-testid="stSelectbox"] label p {
        color: #012869 !important;
        font-weight: bold !important;
    }

    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border: 2px solid #012869 !important;
        border-radius: 6px !important;
        background-color: white !important;
    }

    [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
        border-color: #F37C04 !important;
        box-shadow: 0 0 0 1px #F37C04 !important;
    }

    [data-testid="stSelectbox"] div[data-baseweb="select"] div {
        color: #012869 !important;
        font-weight: 500 !important;
    }

    [data-testid="stSelectbox"] div[data-baseweb="select"] svg {
        fill: #F37C04 !important;
    }

    ul[role="listbox"] {
        background-color: white !important;
        border: 2px solid #012869 !important;
        border-radius: 6px !important;
    }

    ul[role="listbox"] li {
        color: #012869 !important;
    }

    ul[role="listbox"] li:hover, 
    ul[role="listbox"] li[aria-selected="true"] {
        background-color: #F37C04 !important;
        color: white !important;
        font-weight: bold !important;
    }
    
    /* CRIAÇÃO DE ESTILOS PARA O DATE INPUT */
    
    [data-testid="stDateInput"] label p {
        color: #012869 !important;
        font-weight: bold !important;
    }

    [data-testid="stDateInput"] div[data-baseweb="input"] > div {
        background-color: white !important;
        border: 2px solid #012869 !important;
        border-radius: 6px !important;
    }

    [data-testid="stDateInput"] div[data-baseweb="input"] > div:hover,
    [data-testid="stDateInput"] div[data-baseweb="input"] > div:focus-within {
        border-color: #F37C04 !important;
        box-shadow: 0 0 0 1px #F37C04 !important;
    }

    [data-testid="stDateInput"] input {
        color: #012869 !important;
        font-weight: 500 !important;
    }
    
    [data-testid="stDateInput"] svg {
        fill: #F37C04 !important;
        color: #F37C04 !important;
    }
    </style>
    """)


def main():
    # Logotipo
    st.logo("assets/images/novo-logo-totale.png", size="medium")

    # Definição das páginas
    home_page = st.Page("pages/home.py", title="Home", icon="🏠", default=True)
    envio_excel = st.Page("pages/envio_excel.py", title="Atualização de Dados", icon="🔁")
    ranking_pontos = st.Page("pages/pontos.py", title="Ranking de Pontos", icon="📈")
    qtde_os = st.Page("pages/qtde_os.py", title="Quantidade de O.S.", icon="📊")
    consultivo = st.Page("pages/consultivo.py", title="Consultivos", icon="📋")
    gestao_ativos = st.Page("pages/gestao_ativos.py", title="Gestão de Ativos", icon="👷")
    visao_tec_prod = st.Page("pages/visao_tecnico_prod.py", title="Produção", icon="🛠️")
    visao_tec_cons = st.Page("pages/visao_tecnico_cons.py", title="Consultivo", icon="🗣️")
    rota_inicial = st.Page("pages/rota_inicial.py", title="Rota Inicial", icon="🗺️")
    rota_geral = st.Page("pages/rota_geral.py", title="Rota Geral", icon="🗺️")
    volumetria = st.Page("pages/volumetria.py", title="Volumetria", icon="📊")
    quebra_unif = st.Page("pages/quebra_unificada.py", title="Visão PME & Migração", icon="📉")
    assinatura = st.Page("pages/assinatura.py", title="Assinatura", icon="✉️")
    retorno = st.Page("pages/retorno.py", title="Retornos", icon="📜")
    p_atendimento = st.Page("pages/p_atendimento.py", title="1º Atendimento", icon="🚙")
    quebra_geral = st.Page("pages/quebra_geral.py", title="Geral", icon="📉")
    
    # ═══════════════════════════════════════════════════════
    # PÁGINAS ANTIGAS
    # ═══════════════════════════════════════════════════════
    quebra = st.Page("old/quebra.py", title="Geral", icon="📉")
    quebra_pme = st.Page("old/quebra_pme.py", title="Visão PME", icon="📉")
    quebra_mig = st.Page("old/quebra_migracao.py", title="Visão Migração", icon="📉")
    quebra_resumo = st.Page("old/quebra_resumo.py", title="Resumo", icon="📉")
    teste = st.Page("old/diagnostico_abas.py", title="Teste")
    toml = st.Page("old/convert_toml.py", title="TOML")

    # Agrupamento das seções
    paginas_agrupadas = {
        "MENU PRINCIPAL": [home_page, envio_excel],
        "CENTRAL DE PERFORMANCE": [ranking_pontos, qtde_os, consultivo],
        "VISÃO POR TÉCNICO": [visao_tec_prod, visao_tec_cons],
        "COMPILADO": [gestao_ativos],
        "DISPAROS DIÁRIOS": [rota_inicial, rota_geral, volumetria, retorno, p_atendimento],
        "QUEBRA": [quebra_geral, quebra_unif],
        "UTILITÁRIOS": [assinatura],
    }

    pg = st.navigation(paginas_agrupadas)
    pg.run()


if __name__ == "__main__":
    main()
