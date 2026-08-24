# =====================================
# 📄 ARQUIVO: pages/home.py
# 📌 PÁGINA: Home - Portal TOTALE
# 🔄 ÚLTIMA ATUALIZAÇÃO: 2025
# =====================================

import streamlit as st
import time
from zoneinfo import ZoneInfo
from datetime import datetime

# =====================================
# 🔧 BLOCO 1: CONFIGURAÇÕES GERAIS
# =====================================

VERSAO_SISTEMA = "2.1.0"
AMBIENTE = "Produção"
FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
INTERVALO_REFRESH = 60  # segundos (60s é mais leve que 1s)


# =====================================
# 🎨 BLOCO 2: FUNÇÕES DE ESTILO
# =====================================


def get_css_global():
    """Retorna o CSS global do portal."""
    return """
    <style>
        /* Fundo geral */
        .main { background-color: #F3F2F1; }
        
    /* CRIAÇÃO DE ESTILOS PARA A HERO (barra de títulos) */
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
            top: -50%; right: -10%;
            width: 400px; height: 400px;
            background: rgba(255,255,255,0.05);
            border-radius: 50%;
        }
        .hero-title {
            font-size: 34px;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.5px;
            font-family: 'Segoe UI', -apple-system, sans-serif;
        }
        .hero-subtitle {
            font-size: 15px;
            opacity: 0.92;
            margin: 6px 0 0 0;
            font-weight: 400;
        }
        .hero-badge {
            display: inline-block;
            background: rgba(255,255,255,0.18);
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 12px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        /* Remove padding exagerado */
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

        /* Barra superior */
        .top-bar {
            background-color: #012869;
            padding: 18px 30px;
            border-radius: 8px;
            color: white;
            margin-bottom: 25px;
        }

        /* Cards padrão */
        .card {
            background-color: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid #E0E0E0;
        }

        /* Status OK */
        .status-ok {
            background-color: #E6F4EA;
            border-left: 6px solid #2E7D32;
        }

        /* Status Warning */
        .status-warning {
            background-color: #FFF4E5;
            border-left: 6px solid #F37C04;
        }

        /* Títulos */
        h1, h2, h3 { font-weight: 600; }

        /* Rodapé fixo */
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
    """


def get_css_carousel():
    """Retorna CSS do carrossel."""
    return """
    <style>
        .carousel-card {
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid #E0E0E0;
        }
    </style>
    """


# =====================================
# 🧩 BLOCO 3: FUNÇÕES DE COMPONENTES
# =====================================


def render_header():
    """Renderiza o cabeçalho do portal."""
    st.markdown(
        f"""
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
    """Renderiza a introdução do portal."""
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
    """Renderiza o card de status do sistema."""
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
            3️⃣ Aguarde a conclusão
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        ultima = st.session_state.get("ultima_atualizacao")
        hora = ultima.strftime("%d/%m/%Y às %H:%M:%S") if ultima else "Recente"

        st.markdown(
            f"""
        <div class="card status-ok">
            ✅ <b>Sistema atualizado e pronto para uso</b><br>
            Última sincronização: {hora}
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.write("")


def render_cards_navegacao():
    """Renderiza os cards de navegação."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
        <div class="card">
            <h4>⚙️ Produção</h4>
            Monitore eficiência operacional, volume produzido e desempenho por setor.
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
        <div class="card">
            <h4>📈 Indicadores Estratégicos</h4>
            Acompanhe metas, resultados financeiros e KPIs críticos do negócio.
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.divider()


# =====================================
# 🖼️ BLOCO 4: CARROSSEL DE IMAGENS
# =====================================

IMGS_CARROSSEL = [
    "assets/images/informe_vagas.jpeg",
    "assets/images/consultivo_copa.jpg",
    "assets/images/indicacao_totale.png",
]


def render_carrossel():
    """Renderiza o carrossel de comunicados internos."""
    st.subheader("📢 Comunicados Internos")

    # Inicializa índice do slide
    if "slide_index" not in st.session_state:
        st.session_state.slide_index = 0

    if not IMGS_CARROSSEL:
        st.info("Nenhum comunicado disponível no momento.")
        return

    total = len(IMGS_CARROSSEL)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        # Imagem atual
        slide_atual = IMGS_CARROSSEL[st.session_state.slide_index]
        st.image(slide_atual, use_container_width=True)

        # Indicador de posição
        st.markdown(
            f"<div style='text-align:center; font-size:14px; color:#666;'>"
            f"Slide {st.session_state.slide_index + 1} de {total}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Botões de navegação
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("⬅ Anterior", use_container_width=True):
                st.session_state.slide_index = (
                    st.session_state.slide_index - 1
                ) % total

        with col_btn2:
            if st.button("Próximo ➡", use_container_width=True):
                st.session_state.slide_index = (
                    st.session_state.slide_index + 1
                ) % total

        st.markdown("</div>", unsafe_allow_html=True)


# =====================================
# ⏰ BLOCO 5: AUTO REFRESH INTELIGENTE
# =====================================


def auto_refresh(intervalo_segundos=60):
    """
    Auto-refresh usando session_state.
    Evita loop infinito e é mais leve que st_autorefresh.
    """
    key = "_last_refresh_time"

    if key not in st.session_state:
        st.session_state[key] = time.time()

    tempo_decorrido = time.time() - st.session_state[key]

    if tempo_decorrido > intervalo_segundos:
        st.session_state[key] = time.time()
        st.rerun()


# =====================================
# 🕒 BLOCO 6: HORÁRIO DE BRASÍLIA
# =====================================


def get_hora_brasilia():
    """Retorna datetime atual no fuso de Brasília."""
    return datetime.now(FUSO_HORARIO)


def render_footer():
    """Renderiza o rodapé fixo do portal."""
    agora = get_hora_brasilia()
    data_str = agora.strftime("%d/%m/%Y")
    hora_str = agora.strftime("%H:%M")

    st.markdown(
        f"""
    <div class="footer">
        🏢 <b>Portal TOTALE</b>
        <span>|</span>
        🌐 {AMBIENTE}
        <span>|</span>
        🕒 {data_str} • {hora_str} BRT
        <span>|</span>
        🔖 v{VERSAO_SISTEMA}
    </div>
    <style>.block-container {{ padding-bottom: 4.5rem; }}</style>
    """,
        unsafe_allow_html=True,
    )


# =====================================
# 🚀 BLOCO 7: EXECUÇÃO PRINCIPAL
# =====================================


def main():
    """Função principal que orquestra toda a página."""

    # Configuração da página
    st.set_page_config(
        page_title="Portal TOTALE",
        page_icon="📊",
        layout="wide",
    )

    # Aplica estilos globais
    st.markdown(get_css_global(), unsafe_allow_html=True)
    st.markdown(get_css_carousel(), unsafe_allow_html=True)

    # Renderiza componentes na ordem
    render_header()
    render_intro()
    render_status_sistema()
    render_cards_navegacao()
    render_carrossel()

    # Auto-refresh e rodapé
    auto_refresh(intervalo_segundos=INTERVALO_REFRESH)
    render_footer()


# =====================================
# ▶️ PONTO DE ENTRADA
# =====================================

if __name__ == "__main__":
    main()
