# =====================================
# 📄 ARQUIVO: pages/home.py
# 📌 PÁGINA: Home - Portal TOTALE
# =====================================

import streamlit as st
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# =====================================
# 🔧 BLOCO 1: CONFIGURAÇÕES LOCAIS
# =====================================

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
INTERVALO_REFRESH = 60  # segundos


# =====================================
# 🎨 BLOCO 2: CSS
# =====================================


def injetar_css():
    """Injeta CSS específico da Home."""
    st.markdown(
        """
        <style>
            .hero-corp {
                background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
                padding: 32px 40px;
                border-radius: 16px;
                color: white;
                box-shadow: 0 10px 40px rgba(1, 40, 105, 0.25);
                margin-bottom: 24px;
                position: relative;
                overflow: hidden;
            }
            .hero-corp::before {
                content: '';
                position: absolute;
                top: -50%;
                right: -10%;
                width: 400px;
                height: 400px;
                background: rgba(255,255,255,0.05);
                border-radius: 50%;
            }
            .hero-title {
                font-size: 34px;
                font-weight: 800;
                margin: 0;
                letter-spacing: -0.5px;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                color: white !important;
            }
            .hero-subtitle {
                font-size: 15px;
                opacity: 0.92;
                margin: 6px 0 0 0;
                font-weight: 400;
                color: white !important;
            }

            .block-container { padding-top: 1.5rem; padding-bottom: 4.5rem; }

            .card {
                background-color: white;
                padding: 25px;
                border-radius: 10px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                border: 1px solid #E2E8F0;
                transition: transform 0.2s ease-in-out;
                height: 100%;
            }
            .card:hover {
                transform: translateY(-2px);
            }

            .status-ok {
                background-color: #E6F4EA;
                border-left: 6px solid #2E7D32;
            }

            .status-warning {
                background-color: #FFF4E5;
                border-left: 6px solid #F37C04;
            }

            .footer {
                position: fixed;
                left: 0;
                bottom: 0;
                width: 100%;
                background-color: #012869;
                color: white;
                padding: 12px 20px;
                font-size: 14px;
                text-align: center;
                z-index: 999;
                box-shadow: 0 -2px 10px rgba(0,0,0,0.2);
                font-weight: 500;
            }
            .footer span { margin: 0 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =====================================
# 🧩 BLOCO 3: COMPONENTES
# =====================================


def render_header():
    st.markdown(
        """
        <div class="hero-corp">
            <div style="position:relative;z-index:2;">
                <h1 class="hero-title">📊 Portal TOTALE</h1>
                <p class="hero-subtitle">
                    Painéis de Produção, Indicadores e Gestão Estratégica
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_intro():
    st.markdown(
        """
        <div class="card">
            <b>Bem-vindo ao ambiente centralizado de dados da TOTALE.</b><br><br>
            Este portal fornece uma visão clara e estratégica dos processos produtivos e
            indicadores de performance, apoiando decisões com base em dados confiáveis.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")


def render_status_sistema():
    dados_carregados = (
        "dados_prod" in st.session_state and st.session_state["dados_prod"] is not None
    )

    if not dados_carregados:
        st.markdown(
            """
            <div class="card status-warning">
                <b>⚠️ Sistema aguardando atualização de dados</b><br><br>
                1️⃣ Acesse <b>🔁 Atualização de Dados</b> no menu lateral<br>
                2️⃣ Clique em <b>Atualizar Agora</b><br>
                3️⃣ Aguarde a conclusão da sincronização
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        ultima = st.session_state.get("ultima_atualizacao")
        if ultima:
            hora_str = ultima.strftime("%d/%m/%Y às %H:%M:%S")
        else:
            hora_str = "Recente"

        st.markdown(
            f"""
            <div class="card status-ok">
                ✅ <b>Sistema atualizado e pronto para uso</b><br>
                Última sincronização: {hora_str}
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.write("")


def render_cards_navegacao():
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            """
            <div class="card">
                <h4 style="margin-top:0;">⚙️ Produção</h4>
                Monitore eficiência operacional, volume produzido e desempenho por setor.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="card">
                <h4 style="margin-top:0;">📈 Indicadores Estratégicos</h4>
                Acompanhe metas, resultados consolidados e principais KPIs do negócio.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.divider()


def render_footer():
    versao = st.session_state.get("versao_sistema", "3.1.0")
    ambiente = st.session_state.get("ambiente_sistema", "Produção")

    agora = datetime.now(FUSO_HORARIO)
    data_str = agora.strftime("%d/%m/%Y")
    hora_str = agora.strftime("%H:%M")

    st.markdown(
        f"""
        <div class="footer">
            🏢 <b>Painel TOTALE</b>
            <span>|</span>
            🌐 {ambiente}
            <span>|</span>
            🕒 {data_str} • {hora_str} BRT
            <span>|</span>
            🔖 v{versao}
        </div>
        """,
        unsafe_allow_html=True,
    )


def auto_refresh():
    key = "_last_refresh_home"
    if key not in st.session_state:
        st.session_state[key] = time.time()

    if (time.time() - st.session_state[key]) > INTERVALO_REFRESH:
        st.session_state[key] = time.time()
        st.rerun()


# =====================================
# 🚀 BLOCO 4: MAIN
# =====================================


def main():
    injetar_css()
    render_header()
    render_intro()
    render_status_sistema()
    render_cards_navegacao()
    render_footer()
    auto_refresh()


if __name__ == "__main__":
    main()