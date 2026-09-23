"""
app.py
======
Portal TOTALE — Aplicação Principal

Versão: 3.2.0 (Integração Design System v4.9.2 - Sidebar Enterprise)
Autor: TOTALE Tecnologia

Evoluções desta versão:
• Sidebar 100% integrada ao Design System: Brand Card, Seções, Status e Footer
  corporativos (Azul #012869 + Laranja #F37C04).
• Remoção de CSS duplicado da sidebar (agora responsabilidade de componentes.py).
• CSS global injetado via st.markdown (compatível com todas as versões do Streamlit).
• Footer reformulado: sem position:fixed (não cobre mais a sidebar).
• Menu nativo (st.navigation) com headers de seção estilizados.
• Eliminação de injeção dupla de estilo (aplicar_sidebar_corp removido do fluxo).
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_sidebar_brand,
    render_sidebar_divider,
    render_sidebar_footer_info,
    render_sidebar_section,
    render_sidebar_spacer,
    render_sidebar_status,
)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ====================================================
# 🎨 BLOCO 1: CONSTANTES E CONFIGURAÇÕES CENTRALIZADAS
# ====================================================
@dataclass(frozen=True)
class Cores:
    """Paleta de cores centralizada para todo o sistema."""

    PRIMARIA: str = "#012869"
    PRIMARIA_LIGHT: str = "#0A48AA"
    SECUNDARIA: str = "#F37C04"
    SECUNDARIA_LIGHT: str = "#FF9D45"
    SUCESSO: str = "#22C55E"
    ALERTA: str = "#F37C04"
    ERRO: str = "#DC2626"
    TEXTO_PRIMARIO: str = "#334155"
    TEXTO_SECUNDARIO: str = "#64748B"
    FUNDO_CARD: str = "#FFFFFF"
    BORDA_CARD: str = "#F1F5F9"
    BORDA_INPUT: str = "#E2E8F0"


@dataclass(frozen=True)
class ConfiguracoesSistema:
    """Configurações globais do sistema."""

    VERSAO: str = "3.2.0"
    AMBIENTE: str = "Produção"
    FUSO_HORARIO: str = "America/Sao_Paulo"
    INTERVALO_REFRESH: int = 60
    LOGO_PATH: str = "assets/images/novo-logo-totale.png"
    ICON_PATH: str = "assets/images/icons/totale.ico"

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.FUSO_HORARIO)


# Instâncias globais
CORES = Cores()
CONFIG = ConfiguracoesSistema()


# ====================================================
# 🔧 BLOCO 2: DECORATORS E UTILITÁRIOS
# ====================================================
def handle_exceptions(func):
    """Decorator para tratamento centralizado de exceções."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error("Erro em %s: %s", func.__name__, e, exc_info=True)
            st.error(f"Ocorreu um erro: {e!s}")
            return None

    return wrapper


def get_current_time() -> datetime:
    """Retorna o horário atual no fuso configurado."""
    return datetime.now(CONFIG.timezone)


def format_datetime(
    dt: datetime | None, format_str: str = "%d/%m/%Y às %H:%M:%S"
) -> str:
    """Formata datetime de forma segura."""
    if dt is None:
        return "Não disponível"
    return dt.strftime(format_str)


# ====================================================
# 🎨 BLOCO 3: GERENCIADOR DE ESTILOS (somente corpo da página)
# ====================================================
class GerenciadorEstilos:
    """
    Gerencia estilos do CORPO da página.

    ⚠️ A sidebar é 100% estilizada por components/componentes.py (v4.9.2).
    Não duplicar regras de [data-testid="stSidebar"] aqui.
    """

    @staticmethod
    def _get_input_styles() -> str:
        return f"""
        /* INPUTS DO CORPO DA PÁGINA */
        [data-testid="stSelectbox"] label p,
        [data-testid="stMultiSelect"] label p,
        [data-testid="stTextInput"] label p {{
            color: {CORES.PRIMARIA} !important;
            font-weight: 700 !important;
            font-size: 13px !important;
        }}
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stDateInput"] div[data-baseweb="input"] > div {{
            border: 2px solid {CORES.BORDA_INPUT} !important;
            border-radius: 10px !important;
            background-color: #FFFFFF !important;
            transition: border-color .18s ease, box-shadow .18s ease;
        }}
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
        [data-testid="stDateInput"] div[data-baseweb="input"] > div:hover {{
            border-color: {CORES.SECUNDARIA} !important;
            box-shadow: 0 0 0 3px rgba(243, 124, 4, 0.12);
        }}
        [data-testid="stDateInput"] svg {{
            fill: {CORES.SECUNDARIA} !important;
            color: {CORES.SECUNDARIA} !important;
        }}
        """

    @staticmethod
    def _get_card_styles() -> str:
        return f"""
        /* CARDS DO CORPO DA PÁGINA */
        .card {{
            background-color: {CORES.FUNDO_CARD};
            padding: 22px 24px;
            border-radius: 14px;
            box-shadow: 0 4px 14px rgba(1, 40, 105, 0.06);
            border: 1px solid {CORES.BORDA_CARD};
            border-top: 3px solid {CORES.PRIMARIA};
            transition: transform .2s ease, box-shadow .2s ease;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 24px rgba(1, 40, 105, 0.10);
        }}
        .status-ok {{
            background-color: #F0FDF4;
            border-top: none;
            border-left: 5px solid {CORES.SUCESSO};
        }}
        .status-warning {{
            background-color: #FFF7ED;
            border-top: none;
            border-left: 5px solid {CORES.ALERTA};
        }}
        """

    @staticmethod
    def _get_layout_styles() -> str:
        return f"""
        /* HERO BANNER */
        .hero-banner {{
            background:
                radial-gradient(circle at 88% 20%, rgba(255, 157, 69, 0.35) 0, transparent 30%),
                linear-gradient(135deg, #011E52 0%, {CORES.PRIMARIA} 45%, {CORES.PRIMARIA_LIGHT} 100%);
            padding: 34px 40px;
            border-radius: 18px;
            color: white;
            box-shadow: 0 14px 32px rgba(1, 40, 105, 0.24);
            margin-bottom: 24px;
            border: 1px solid rgba(255, 157, 69, 0.30);
            position: relative;
            overflow: hidden;
        }}
        .hero-banner::before {{
            content: "";
            position: absolute;
            left: 0; top: 0;
            width: 5px; height: 100%;
            background: linear-gradient(180deg, {CORES.SECUNDARIA_LIGHT}, {CORES.SECUNDARIA});
        }}

        /* FOOTER (em fluxo, não fixo — não cobre a sidebar) */
        .footer {{
            margin-top: 2.5rem;
            background: linear-gradient(90deg, #011E52 0%, {CORES.PRIMARIA} 55%, {CORES.PRIMARIA_LIGHT} 100%);
            color: #FFFFFF;
            padding: 14px 24px;
            border-radius: 14px;
            font-size: 12.5px;
            font-weight: 600;
            text-align: center;
            letter-spacing: .2px;
            box-shadow: 0 10px 24px rgba(1, 40, 105, 0.20);
            border-top: 3px solid {CORES.SECUNDARIA};
        }}
        .footer span.sep {{
            color: {CORES.SECUNDARIA_LIGHT};
            margin: 0 8px;
            font-weight: 900;
        }}
        .block-container {{
            padding-bottom: 3rem;
        }}

        /* HEADERS DAS SEÇÕES DO MENU NATIVO (st.navigation) */
        [data-testid="stSidebarNav"] p {{
            font-size: 10px !important;
            font-weight: 900 !important;
            letter-spacing: .9px !important;
            color: #64748B !important;
            text-transform: uppercase;
            margin: 20px 0 6px 6px !important;
        }}
        [data-testid="stSidebarNav"] p:first-child {{
            margin-top: 4px !important;
        }}
        """

    @classmethod
    def injetar_css_global(cls) -> None:
        """Injeta CSS global via markdown (garante aplicação em todo o DOM)."""
        css_completo = f"""
        <style>
        {cls._get_input_styles()}
        {cls._get_card_styles()}
        {cls._get_layout_styles()}
        </style>
        """
        st.markdown(css_completo, unsafe_allow_html=True)


# ====================================================
# 🏠 BLOCO 4: COMPONENTES DA PÁGINA HOME
# ====================================================
class ComponentesHome:
    """Componentes reutilizáveis da página home."""

    @staticmethod
    def render_hero_banner() -> None:
        st.markdown(
            """
            <div class="hero-banner">
                <h1 style="font-size:32px; font-weight:900; margin:0; color:#FFFFFF !important; letter-spacing:.2px;">
                    📊 Portal TOTALE
                </h1>
                <p style="font-size:14px; opacity:.92; margin:6px 0 0 0; color:#FFFFFF !important; font-weight:500;">
                    Painéis de Produção, Indicadores e Gestão Estratégica
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def render_card_boas_vindas() -> None:
        st.markdown(
            f"""
            <div class="card">
                <p style="margin:0; font-size:14px; color:{CORES.TEXTO_PRIMARIO}; line-height:1.65;">
                    <b style="color:{CORES.PRIMARIA};">Bem-vindo ao ambiente centralizado de dados da TOTALE.</b><br>
                    Este portal fornece uma visão clara e estratégica dos processos produtivos
                    e indicadores de performance, apoiando decisões com base em dados confiáveis.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def render_status_sistema() -> None:
        dados_prod = st.session_state.get("dados_prod")

        if dados_prod is None:
            st.markdown(
                """
                <div class="card status-warning">
                    <b style="color:#C2410C;">⚠️ Sistema aguardando atualização de dados</b><br>
                    <p style="margin:8px 0 0 0; font-size:13px; color:#7C2D12; line-height:1.6;">
                        1️⃣ Acesse <b>🔁 Atualização de Dados</b> no menu lateral<br>
                        2️⃣ Clique em <b>Sincronizar Agora</b> para puxar as bases operacionais.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            ultima = st.session_state.get("ultima_atualizacao")
            hora = format_datetime(ultima)
            st.markdown(
                f"""
                <div class="card status-ok">
                    <b style="color:#15803D;">✅ Sistema operacional e atualizado</b><br>
                    <span style="font-size:13px; color:#166534;">
                        Última sincronização validada em {hora}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    @staticmethod
    def render_cards_modulos() -> None:
        col1, col2 = st.columns(2, gap="medium")

        with col1:
            st.markdown(
                f"""
                <div class="card">
                    <h4 style="margin:0 0 8px 0; color:{CORES.PRIMARIA}; font-weight:800;">
                        ⚙️ Produção Operacional
                    </h4>
                    <p style="margin:0; font-size:13px; color:{CORES.TEXTO_SECUNDARIO}; line-height:1.55;">
                        Monitore a eficiência e o volume produzido por técnicos e equipes em tempo real.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                f"""
                <div class="card">
                    <h4 style="margin:0 0 8px 0; color:{CORES.PRIMARIA}; font-weight:800;">
                        📈 Indicadores de Performance
                    </h4>
                    <p style="margin:0; font-size:13px; color:{CORES.TEXTO_SECUNDARIO}; line-height:1.55;">
                        Acompanhe a evolução de metas operacionais e KPIs estratégicos.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    @staticmethod
    def render_footer() -> None:
        agora = get_current_time()
        st.markdown(
            f"""
            <div class="footer">
                🏢 <b>Painel TOTALE</b>
                <span class="sep">|</span> 🌐 {CONFIG.AMBIENTE}
                <span class="sep">|</span> 🕒 {agora.strftime("%d/%m/%Y")} • {agora.strftime("%H:%M")} BRT
                <span class="sep">|</span> 🔖 v{CONFIG.VERSAO}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ====================================================
# 🏠 BLOCO 5: PÁGINA HOME PRINCIPAL
# ====================================================
@handle_exceptions
def pagina_home() -> None:
    """Página principal do sistema."""
    ComponentesHome.render_hero_banner()
    ComponentesHome.render_card_boas_vindas()
    ComponentesHome.render_status_sistema()

    st.markdown("<br>", unsafe_allow_html=True)
    ComponentesHome.render_cards_modulos()

    ComponentesHome.render_footer()

    _gerenciar_refresh_automatico()


def _gerenciar_refresh_automatico() -> None:
    """Gerencia o refresh automático da página."""
    if "_last_refresh_time" not in st.session_state:
        st.session_state["_last_refresh_time"] = time.time()

    tempo_decorrido = time.time() - st.session_state["_last_refresh_time"]

    if tempo_decorrido > CONFIG.INTERVALO_REFRESH:
        logger.info("Executando refresh automático da página")
        st.session_state["_last_refresh_time"] = time.time()
        st.rerun()


# ====================================================
# 🚀 BLOCO 6: GERENCIADOR DE NAVEGAÇÃO
# ====================================================
class GerenciadorNavegacao:
    """Gerencia a navegação e estrutura de páginas."""

    @staticmethod
    def _definir_paginas() -> dict[str, list]:
        """Define todas as páginas do sistema."""
        return {
            "Menu Principal": [
                st.Page(pagina_home, title="Home", icon="🏠", default=True),
                st.Page(
                    "pages/envio_excel.py", title="Atualização de Dados", icon="🔁"
                ),
            ],
            "Central de Performance": [
                st.Page("pages/pontos.py", title="Produção Mensal", icon="📈"),
                st.Page("pages/qtde_os.py", title="Quantidade de O.S.", icon="⚡"),
                st.Page("pages/consultivo.py", title="Consultivos", icon="📋"),
                st.Page(
                    "pages/dashboard_meta.py", title="Metas Operacionais", icon="🎯"
                ),
            ],
            "Compilado": [
                st.Page("pages/gestao_ativos.py", title="Gestão de Ativos", icon="👷"),
            ],
            "Disparos Diários": [
                st.Page("pages/rota_inicial.py", title="Rota Inicial", icon="🗺️"),
                st.Page("pages/rota_geral.py", title="Rota Geral", icon="🗺️"),
                st.Page("pages/volumetria.py", title="Volumetria", icon="📊"),
                st.Page("pages/retorno.py", title="Retornos", icon="🔍"),
                st.Page("pages/p_atendimento.py", title="1º Atendimento", icon="🚙"),
            ],
            "Quebra": [
                st.Page("pages/quebra_geral.py", title="Geral", icon="📉"),
                st.Page(
                    "pages/quebra_unificada.py", title="Visão Segmentos", icon="📉"
                ),
            ],
            "Utilitários": [
                st.Page("pages/assinatura.py", title="Assinatura", icon="✉️"),
            ],
        }

    @staticmethod
    def renderizar_sidebar_corporativa() -> None:
        """
        Renderiza o cabeçalho corporativo da sidebar (acima do menu nativo).
        O menu de navegação em si é desenhado pelo st.navigation.
        """
        render_sidebar_brand(
            nome="TOTALE",
            subtitulo="Portal de Produção & Performance",
            versao=f"v{CONFIG.VERSAO}",
            icone="📊",
        )

        render_sidebar_section("Status Operacional", icone="🛰️")

        dados_prod = st.session_state.get("dados_prod")
        if dados_prod is not None:
            render_sidebar_status(
                label="Dados Sincronizados",
                status="Atualizado",
                tipo="ok",
                icone="🗄️",
                # Passa o objeto cru — o Design System formata sozinho
                ultima_atualizacao=st.session_state.get("ultima_atualizacao"),
            )
        else:
            render_sidebar_status(
                label="Aguardando Sincronismo",
                status="Pendente",
                tipo="alerta",
                icone="⏳",
            )

        render_sidebar_divider(estilo="gradiente")


# ====================================================
# 🚀 BLOCO 7: APLICAÇÃO PRINCIPAL
# ====================================================
@handle_exceptions
def main() -> None:
    """Função principal da aplicação."""
    logger.info("Iniciando aplicação TOTALE")

    # 1. Configuração inicial da página
    st.set_page_config(
        page_title="Painel TOTALE",
        page_icon=CONFIG.ICON_PATH,
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": None,
            "Report a bug": None,
            "About": f"# Portal TOTALE v{CONFIG.VERSAO}\nTecnologia, Dados e Performance.",
        },
    )

    # 2. Injeção de estilos (uma única vez — Design System + estilos do app)
    aplicar_estilo()
    GerenciadorEstilos.injetar_css_global()

    # 3. Cabeçalho corporativo da sidebar (marca + status, acima do menu)
    GerenciadorNavegacao.renderizar_sidebar_corporativa()

    # 4. Navegação nativa (seções + páginas)
    paginas = GerenciadorNavegacao._definir_paginas()
    pg = st.navigation(paginas)
    pg.run()

    # 5. Rodapé corporativo da sidebar (abaixo do menu)
    render_sidebar_spacer(altura=12)
    render_sidebar_footer_info(
        empresa="TOTALE Tecnologia",
        versao=f"v{CONFIG.VERSAO}",
        ambiente=CONFIG.AMBIENTE,
    )

    logger.info("Aplicação iniciada com sucesso")


if __name__ == "__main__":
    main()
