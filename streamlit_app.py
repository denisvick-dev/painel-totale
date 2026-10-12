"""
streamlit_app.py
================
Portal TOTALE — Aplicação Principal

Versão: 3.4.0 (seletor de tema do sidebar integrado ao módulo components.sidebar)
Autor: TOTALE Tecnologia

• Seletor da sidebar com temas Claro, Azul e Laranja.
• Tema selecionado persistido entre reruns e sincronizado com components.sidebar.
• Marca, status do sistema e informações do ambiente na sidebar.
• CSS do app limitado ao corpo da página; components.sidebar controla a sidebar.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import streamlit as st

try:
    from streamlit.runtime.scriptrunner_utils.exceptions import (
        RerunException,
        StopException,
    )
except ImportError:  # pragma: no cover - fallback para variações internas do Streamlit
    RerunException = StopException = ()  # type: ignore[misc, assignment]

from components.componentes import aplicar_estilo
from components.sidebar import (
    TemaSidebarType,
    definir_tema_sidebar,
    render_sidebar_brand,
    render_sidebar_divider,
    render_sidebar_footer_info,
    render_sidebar_section,
    render_sidebar_spacer,
    render_sidebar_status,
    render_sidebar_theme_selector,
)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


# ====================================================
# 🎨 BLOCO 1: CONSTANTES E CONFIGURAÇÕES CENTRALIZADAS
# ====================================================
@dataclass(frozen=True)
class Cores:
    """Paleta de cores para o corpo do sistema."""

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

    VERSAO: str = "3.4.0"
    AMBIENTE: str = "Produção"
    FUSO_HORARIO: str = "America/Sao_Paulo"
    ICON_PATH: str = "assets/icons/totale.ico"


CORES = Cores()
CONFIG = ConfiguracoesSistema()


# ====================================================
# 🔧 BLOCO 2: DECORATORS E UTILITÁRIOS
# ====================================================
def handle_exceptions(func: Callable[P, R]) -> Callable[P, R | None]:
    """Decorador que registra exceções e mostra um erro amigável com ID de correlação."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
        try:
            return func(*args, **kwargs)
        except (RerunException, StopException):
            raise
        except Exception as exc:
            error_id = uuid.uuid4().hex[:8].upper()
            logger.exception(
                "Erro em %s [ref=%s]: %s", func.__name__, error_id, exc
            )
            st.error(
                f"Ocorreu um erro inesperado ao carregar a página "
                f"(código de referência #{error_id})."
            )
            return None

    return wrapper


def format_datetime(
    dt: datetime | str | None,
    format_str: str = "%d/%m/%Y às %H:%M:%S",
) -> str:
    """Formata datetime com retorno garantido em string."""
    if dt is None:
        return "Não disponível"
    if isinstance(dt, str):
        return dt
    try:
        return dt.strftime(format_str)
    except (ValueError, TypeError, AttributeError, OverflowError):
        logger.debug("strftime falhou para valor; usando str().", exc_info=True)
        return str(dt)


def _aplicar_estilo_seguro(tema: Any = "claro") -> None:
    """Persiste o tema da sidebar e aplica o estilo global da página."""
    tema_texto = str(tema or "claro").strip().lower()
    if tema_texto == "azul":
        tema_norm: TemaSidebarType = "azul"
    elif tema_texto == "laranja":
        tema_norm = "laranja"
    else:
        # Inclui "claro", "padrao" e valores desconhecidos.
        tema_norm = "claro"

    st.session_state["tema_sidebar"] = tema_norm
    definir_tema_sidebar(tema_norm)
    aplicar_estilo()


# ====================================================
# 🎨 BLOCO 3: GERENCIADOR DE ESTILOS DO CORPO DA PÁGINA
# ====================================================
class GerenciadorEstilos:
    """Gerencia os estilos do corpo; a sidebar é controlada por components.sidebar."""

    @staticmethod
    def _get_input_styles() -> str:
        return f"""
        /* INPUTS DO CORPO DA PÁGINA — sidebar controlada pelo módulo próprio */
        [data-testid="stMain"] [data-testid="stSelectbox"] label p,
        [data-testid="stMain"] [data-testid="stMultiSelect"] label p,
        [data-testid="stMain"] [data-testid="stTextInput"] label p {{
            color: {CORES.PRIMARIA} !important;
            font-weight: 700 !important;
            font-size: 13px !important;
        }}
        [data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stMain"] [data-testid="stDateInput"] div[data-baseweb="input"] > div {{
            border: 2px solid {CORES.BORDA_INPUT} !important;
            border-radius: 10px !important;
            background-color: #FFFFFF !important;
            transition: border-color .18s ease, box-shadow .18s ease;
        }}
        [data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
        [data-testid="stMain"] [data-testid="stDateInput"] div[data-baseweb="input"] > div:hover {{
            border-color: {CORES.SECUNDARIA} !important;
            box-shadow: 0 0 0 3px rgba(243, 124, 4, 0.12);
        }}
        [data-testid="stMain"] [data-testid="stDateInput"] svg {{
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

        /* FOOTER DA PÁGINA */
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
        """

    @classmethod
    def injetar_css_global(cls) -> None:
        """Injeta CSS do corpo da página sem sobrescrever o tema da sidebar."""
        css_completo = f"""
        <style>
        {cls._get_input_styles()}
        {cls._get_card_styles()}
        {cls._get_layout_styles()}
        </style>
        """
        st.markdown(css_completo, unsafe_allow_html=True)


# ====================================================
# 🚀 BLOCO 4: GERENCIADOR DE NAVEGAÇÃO
# ====================================================
class GerenciadorNavegacao:
    """Gerencia navegação e conteúdo corporativo da sidebar."""

    @staticmethod
    def _definir_paginas() -> dict[str, list[st.Page]]:
        """Define as páginas do sistema."""
        return {
            "Menu Principal": [
                st.Page("pages/home.py", title="Home", icon="🏠", default=True),
                st.Page("pages/alertas.py", title="Alertas automáticos", icon="⚠️"),
                st.Page(
                    "pages/envio_excel.py", title="Atualização de Dados", icon="🔁"
                ),
                st.Page("robo/main.py", title="Robô local", icon="🤖"),
            ],
            "Central de Performance": [
                st.Page("pages/pontos.py", title="Produção Mensal", icon="📈"),
                st.Page("pages/qtde_os.py", title="Quantidade de O.S.", icon="⚡"),
                st.Page("pages/consultivo.py", title="Consultivos", icon="📋"),
                st.Page(
                    "pages/dashboard_meta.py", title="Metas Operacionais", icon="🎯"
                ),
                st.Page("pages/indicadores.py", title="Indicadores", icon="⚡"),
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
        """Renderiza marca, seletor de tema, status e informações do portal."""
        tema_atual = st.session_state.get(
            "_totale_sidebar_theme",
            st.session_state.get("tema_sidebar", "laranja"),
        )

        render_sidebar_brand(
            nome="TOTALE",
            subtitulo="Portal de Produção & Performance",
            versao=f"v{CONFIG.VERSAO}",
            icone="⚡",
            tema=tema_atual,
        )
        render_sidebar_section("Aparência", icone="🎨", tema=tema_atual)
        tema_escolhido = render_sidebar_theme_selector(
            label="Tema visual",
            help="Escolha as cores do menu lateral.",
            key="_totale_sidebar_theme_select",
            mostrar_icone=True,
            aplicar_automaticamente=True,
        )
        st.session_state["tema_sidebar"] = tema_escolhido

        render_sidebar_divider(
            estilo="gradiente",
            espacamento="pequeno",
            tema=tema_escolhido,
        )

        dados = st.session_state.get("dados_prod")
        ultima = st.session_state.get("ultima_atualizacao")
        ultima_formatada = format_datetime(ultima) if ultima is not None else ""
        try:
            total_registros = len(dados) if dados is not None else None
        except (TypeError, ValueError):
            total_registros = None

        tem_dados = dados is not None
        render_sidebar_status(
            status="Dados disponíveis" if tem_dados else "Aguardando dados",
            label="STATUS DO SISTEMA",
            ultima_atualizacao=ultima_formatada,
            total_registros=total_registros,
            tipo="ok" if tem_dados else "info",
            tema=tema_escolhido,
        )
        render_sidebar_spacer("pequeno")
        render_sidebar_footer_info(
            itens={"Fuso horário": CONFIG.FUSO_HORARIO},
            empresa="TOTALE",
            ambiente=CONFIG.AMBIENTE,
            unidade="Portal de Produção & Performance",
            tema=tema_escolhido,
        )


# ====================================================
# 🚀 BLOCO 5: APLICAÇÃO PRINCIPAL
# ====================================================
@handle_exceptions
def main() -> None:
    """Função principal da aplicação."""
    logger.info("Iniciando aplicação TOTALE")

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

    if "dados_prod" not in st.session_state:
        st.session_state["dados_prod"] = None
    if "ultima_atualizacao" not in st.session_state:
        st.session_state["ultima_atualizacao"] = None
    if "tema_sidebar" not in st.session_state:
        st.session_state["tema_sidebar"] = "laranja"

    paginas = GerenciadorNavegacao._definir_paginas()
    pg = st.navigation(paginas)

    # A chave do widget tem precedência para não reverter a escolha no rerun.
    tema_ativo = (
        st.session_state.get("_totale_sidebar_theme_select")
        or st.session_state.get("seletor_cor_sidebar")  # estado legado
        or st.session_state.get("_totale_sidebar_theme")
        or st.session_state.get("tema_sidebar", "laranja")
    )
    _aplicar_estilo_seguro(tema_ativo)
    GerenciadorEstilos.injetar_css_global()
    GerenciadorNavegacao.renderizar_sidebar_corporativa()

    st.session_state["_totale_root_navigation_shell"] = True
    pg.run()
    logger.info("Aplicação iniciada com sucesso")


if __name__ == "__main__":
    main()
