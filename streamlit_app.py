import streamlit as st
import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any
from dataclasses import dataclass
from functools import wraps

from components.componentes import (
    aplicar_sidebar_corp,
    aplicar_estilo,
    render_sidebar_status,
)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ====================================================
# 🎨 BLOCO 1: CONSTANTES E CONFIGURAÇÕES CENTRALIZADAS
# ====================================================
@dataclass(frozen=True)
class Cores:
    """Paleta de cores centralizada para todo o sistema."""

    PRIMARIA: str = "#012869"
    SECUNDARIA: str = "#F37C04"
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

    VERSAO: str = "3.1.0"
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
            logger.error(f"Erro em {func.__name__}: {str(e)}", exc_info=True)
            st.error(f"Ocorreu um erro: {str(e)}")
            return None

    return wrapper


def get_current_time() -> datetime:
    """Retorna o horário atual no fuso configurado."""
    return datetime.now(CONFIG.timezone)


def format_datetime(
    dt: Optional[datetime], format_str: str = "%d/%m/%Y às %H:%M:%S"
) -> str:
    """Formata datetime de forma segura."""
    if dt is None:
        return "Não disponível"
    return dt.strftime(format_str)


# ====================================================
# 🎨 BLOCO 3: GERENCIADOR DE ESTILOS
# ====================================================
class GerenciadorEstilos:
    """Gerencia todos os estilos CSS do sistema."""

    @staticmethod
    def _get_input_styles() -> str:
        return f"""
        /* INPUTS DO CORPO DA PÁGINA */
        [data-testid="stSelectbox"] label p {{ 
            color: {CORES.PRIMARIA} !important; 
            font-weight: bold !important; 
        }}
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
            border: 2px solid {CORES.BORDA_INPUT} !important; 
            border-radius: 8px !important; 
            background-color: white !important;
        }}
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {{ 
            border-color: {CORES.SECUNDARIA} !important; 
        }}

        [data-testid="stDateInput"] label p {{ 
            color: {CORES.PRIMARIA} !important; 
            font-weight: bold !important; 
        }}
        [data-testid="stDateInput"] div[data-baseweb="input"] > div {{
            background-color: white !important; 
            border: 2px solid {CORES.BORDA_INPUT} !important; 
            border-radius: 8px !important;
        }}
        [data-testid="stDateInput"] div[data-baseweb="input"] > div:hover {{ 
            border-color: {CORES.SECUNDARIA} !important; 
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
            padding: 24px; 
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            border: 1px solid {CORES.BORDA_CARD}; 
            transition: all 0.2s ease-in-out;
        }}
        .card:hover {{ 
            transform: translateY(-2px); 
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); 
        }}
        .status-ok {{ 
            background-color: #F0FDF4; 
            border-left: 5px solid {CORES.SUCESSO}; 
        }}
        .status-warning {{ 
            background-color: #FFF7ED; 
            border-left: 5px solid {CORES.ALERTA}; 
        }}
        """

    @staticmethod
    def _debug_sidebar_css() -> str:
        """CSS temporário para debug - remova após testes."""
        return """
        [data-testid="stSidebar"] * {
            outline: 1px solid red !important;
        }
        """

    @staticmethod
    def _get_layout_styles() -> str:
        return f"""
        .hero-banner {{
            background: linear-gradient(135deg, {CORES.PRIMARIA} 0%, #1E40AF 60%, {CORES.SECUNDARIA} 100%);
            padding: 32px 40px; 
            border-radius: 16px; 
            color: white;
            box-shadow: 0 10px 25px rgba(1, 40, 105, 0.15); 
            margin-bottom: 24px;
        }}

        .footer {{
            position: fixed; 
            left: 0; 
            bottom: 0; 
            width: 100%;
            background-color: {CORES.PRIMARIA}; 
            color: white; 
            padding: 12px 20px;
            font-size: 16px; 
            text-align: center; 
            z-index: 999;
        }}
        .block-container {{ 
            padding-bottom: 5rem; 
        }}

        /* NAVIGATION SIDEBAR - ÍCONE E TEXTO COLADOS (HORIZONTAL) */
        [data-testid="stSidebar"] {{
            position: relative !important;

            &::after {{
                content: "";
                position: absolute;
                top: 0;
                right: 0;
                width: 4px;
                height: 100%;
                background: linear-gradient(180deg, {CORES.PRIMARIA} 0%, {CORES.PRIMARIA} 58%, {CORES.SECUNDARIA} 58%, {CORES.SECUNDARIA} 100%);
                pointer-events: none;
                z-index: 100;
            }}

            a[href] {{
                display: flex !important;
                flex-direction: row !important;
                align-items: center !important;
                justify-content: flex-start !important;
                text-align: left !important;
                padding: 6px 12px !important;
                margin: 2px 8px !important;
                border-radius: 6px !important;
                gap: 6px !important;
                min-height: 32px !important;
            }}

            a[href]:hover {{
                background-color: rgba(255,255,255,0.08) !important;
            }}

            a[href] svg {{
                width: 16px !important;
                height: 16px !important;
                margin: 0px !important;
                flex-shrink: 0 !important;
            }}

            a[href] p,
            a[href] span {{
                color: {CORES.PRIMARIA} !important;
                font-size: 12px !important;
                font-weight: 600 !important;
                text-align: left !important;
                line-height: 1.1 !important;
                margin: 0px !important;
                white-space: nowrap !important;
            }}

            a[href][aria-current="page"] {{
                background-color: #FFF7ED !important;
                border: 1px solid {CORES.SECUNDARIA} !important;
                border-left: 3px solid {CORES.SECUNDARIA} !important;
            }}

            a[href][aria-current="page"] p,
            a[href][aria-current="page"] span {{
                color: {CORES.PRIMARIA} !important;
                font-weight: 700 !important;
            }}

            a[href][aria-current="page"] svg {{
                fill: {CORES.SECUNDARIA} !important;
                color: {CORES.SECUNDARIA} !important;
            }}
        }}
        """

    @classmethod
    def injetar_css_global(cls) -> None:
        """Injeta todo o CSS global no Streamlit."""
        css_completo = f"""
        <style>
        {cls._get_input_styles()}
        {cls._get_card_styles()}
        {cls._get_layout_styles()}
        </style>
        """
        st.html(css_completo)


# ====================================================
# 🏠 BLOCO 4: COMPONENTES DA PÁGINA HOME
# ====================================================
class ComponentesHome:
    """Componentes reutilizáveis da página home."""

    @staticmethod
    def render_hero_banner() -> None:
        st.markdown(
            f"""
            <div class="hero-banner">
                <h1 style="font-size:32px; font-weight:800; margin:0; color:#FFFFFF !important;">
                    📊 Portal TOTALE
                </h1>
                <p style="font-size:14px; opacity:0.9; margin:4px 0 0 0; color:#FFFFFF !important;">
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
                <p style="margin:0; font-size:14px; color:{CORES.TEXTO_PRIMARIO}; line-height:1.6;">
                    <b>Bem-vindo ao ambiente centralizado de dados da TOTALE.</b><br>
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
                f"""
                <div class="card status-warning">
                    <b style="color:#C2410C;">⚠️ Sistema aguardando atualização de dados</b><br>
                    <p style="margin:8px 0 0 0; font-size:13px; color:#7C2D12;">
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
                    <h4 style="margin:0 0 8px 0; color:{CORES.PRIMARIA};">⚙️ Produção Operacional</h4>
                    <p style="margin:0; font-size:13px; color:{CORES.TEXTO_SECUNDARIO};">
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
                    <h4 style="margin:0 0 8px 0; color:{CORES.PRIMARIA};">📈 Indicadores de Performance</h4>
                    <p style="margin:0; font-size:13px; color:{CORES.TEXTO_SECUNDARIO};">
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
                🏢 <b>Painel TOTALE</b> <span>|</span>
                🌐 {CONFIG.AMBIENTE} <span>|</span>
                🕒 {agora.strftime("%d/%m/%Y")} • {agora.strftime("%H:%M")} BRT <span>|</span>
                🔖 v{CONFIG.VERSAO}
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

    st.divider()
    ComponentesHome.render_footer()

    # Auto-refresh controlado
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
    def _definir_paginas() -> Dict[str, list]:
        """Define todas as páginas do sistema."""
        return {
            "MENU PRINCIPAL": [
                st.Page(pagina_home, title="Home", icon="🏠", default=True),
                st.Page(
                    "pages/envio_excel.py", title="Atualização de Dados", icon="🔁"
                ),
            ],
            "CENTRAL DE PERFORMANCE": [
                st.Page("pages/pontos.py", title="Produção Mensal", icon="📈"),
                st.Page("pages/qtde_os.py", title="Quantidade de O.S.", icon="⚡"),
                st.Page("pages/consultivo.py", title="Consultivos", icon="📋"),
                st.Page("pages/dashboard_meta.py", title="Metas Operacionais", icon="🎯"),
            ],
            "COMPILADO": [
                st.Page("pages/gestao_ativos.py", title="Gestão de Ativos", icon="👷"),
            ],
            "DISPAROS DIÁRIOS": [
                st.Page("pages/rota_inicial.py", title="Rota Inicial", icon="🗺️"),
                st.Page("pages/rota_geral.py", title="Rota Geral", icon="🗺️"),
                st.Page("pages/volumetria.py", title="Volumetria", icon="📊"),
                st.Page("pages/retorno.py", title="Retornos", icon="🔍"),
                st.Page("pages/p_atendimento.py", title="1º Atendimento", icon="🚙"),
            ],
            "QUEBRA": [
                st.Page("pages/quebra_geral.py", title="Geral", icon="📉"),
                st.Page(
                    "pages/quebra_unificada.py", title="Visão PME & Migração", icon="📉"
                ),
            ],
            "UTILITÁRIOS": [
                st.Page("pages/assinatura.py", title="Assinatura", icon="✉️"),
            ],
        }

    @staticmethod
    def renderizar_sidebar(paginas: Dict[str, list]) -> None:
        """Mantém o ponto de extensão sem duplicar a navegação nativa."""
        return None


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
    )

    # 2. Injeção de estilos
    aplicar_estilo()
    aplicar_sidebar_corp()
    GerenciadorEstilos.injetar_css_global()

    # 3. Status operacional
    dados_prod = st.session_state.get("dados_prod")
    if dados_prod is not None:
        render_sidebar_status(label="Bases Atualizadas", tipo="success")
    else:
        render_sidebar_status(label="Aguardando Sincronismo", tipo="warning")

    # 4. Navegação nativa
    paginas = GerenciadorNavegacao._definir_paginas()

    pg = st.navigation(paginas)
    pg.run()

    logger.info("Aplicação iniciada com sucesso")


if __name__ == "__main__":
    main()
