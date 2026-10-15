"""
streamlit_app.py
================
Portal TOTALE — Aplicação Principal

Versão: 3.7.0 (navegação declarativa, dashboards padronizados na hierarquia de
leitura e camada de serviços compartilhada entre as páginas)
Autor: TOTALE Tecnologia

• Seletor da sidebar com temas Claro, Azul e Laranja.
• Tema selecionado persistido entre reruns e sincronizado com components.sidebar.
• Marca, status do sistema e informações do ambiente na sidebar.
• CSS do app limitado ao corpo da página; components.sidebar controla a sidebar.
• CSS v2 dos dashboards injetado globalmente: hover nos KPIs, moldura em
  gráficos Plotly, abas pill, expansores e tabelas com acabamento corporativo.
• **v3.6.0** — o CSS dos componentes nativos (botões, entradas, seleção,
  tabelas, abas, alertas, acessibilidade e impressão) saiu deste arquivo e foi
  consolidado em ``components/css_global.py``: uma única injeção por sessão,
  ~40 KB a menos trafegados por rerun e nenhum estilo duplicado. As classes
  utilitárias legadas (``.card``, ``.status-ok``, ``.status-warning``) foram
  preservadas lá.
• **v3.7.0** — o mapa do portal saiu do entrypoint: ``config/navegacao.py``
  declara páginas, grupos, ícones e descrições, e ``st.navigation`` apenas
  consome esse dado. A página ``Visão Geral`` (índice navegável dos painéis) e
  os testes de cobertura do menu lêem a mesma fonte. A versão e o ambiente
  publicados vieram para ``config.settings`` (``VERSAO_PORTAL`` /
  ``AMBIENTE_PORTAL``), então rodapé das páginas e o ``Sobre`` não divergem.
• **v3.7.0** — as onze páginas principais passaram a abrir e fechar no mesmo
  padrão (``components.dashboards``: hero → chips de contexto → sumário → seções
  → exportação → rodapé) e a compartilhar a camada de serviços
  (``services.dados_sessao``, ``services.hierarquia``, ``services.planilhas`` e
  ``services.texto``) em vez de reimplementar leitura de base, lista de ativos,
  exportação e normalização de colunas.
• Novos módulos disponíveis para as páginas: ``components.kpi_cards``
  (substituto do ``st.metric``), ``components.graficos`` (fábrica de 24 tipos
  de gráficos nas cores oficiais), ``components.layout_pagina`` (hierarquia de
  leitura das páginas) e ``services.cache_dados`` (HTTP reutilizável, cache
  condicional 304, Parquet em disco e carga paralela).
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
from components.css_global import injetar_css_global as injetar_css_componentes
from components.dashboard_kit import injetar_css_dashboards
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
from config.settings import AMBIENTE_PORTAL, ICON_PATH_PORTAL, VERSAO_PORTAL

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
    """Configurações globais do sistema (valores vindos de ``config.settings``)."""

    VERSAO: str = VERSAO_PORTAL
    AMBIENTE: str = AMBIENTE_PORTAL
    FUSO_HORARIO: str = "America/Sao_Paulo"
    ICON_PATH: str = ICON_PATH_PORTAL


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
            logger.exception("Erro em %s [ref=%s]: %s", func.__name__, error_id, exc)
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
    """Fachada dos estilos do corpo da página.

    Desde a v3.6.0 o CSS dos componentes nativos vive em
    :mod:`components.css_global` (injeção única por sessão, no ``<head>``, com
    fallback em fluxo). Esta classe mantém o nome e o contrato usados pelo
    entrypoint e pelas páginas, apenas delegando a injeção.

    A sidebar continua sob controle exclusivo de :mod:`components.sidebar`.
    """

    @classmethod
    def css_global(cls) -> str:
        """Conteúdo completo do CSS global v3.6 (diagnóstico e testes)."""
        from components.css_global import css_global_completo

        return css_global_completo()

    @classmethod
    def injetar_css_global(cls) -> None:
        """Injeta o CSS global do corpo da página (idempotente por sessão)."""
        injetar_css_componentes()


# ====================================================
# 🚀 BLOCO 4: GERENCIADOR DE NAVEGAÇÃO
# ====================================================
class GerenciadorNavegacao:
    """Gerencia navegação e conteúdo corporativo da sidebar."""

    @staticmethod
    def _definir_paginas() -> dict[str, list[st.Page]]:
        """Monta o menu a partir de :mod:`config.navegacao` (fonte única)."""
        from config.navegacao import mapa_de_navegacao

        return mapa_de_navegacao()

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
    # Camadas de estilo: Design System (aplicar_estilo) → CSS v2 dos dashboards
    # → CSS global v3.6 dos componentes nativos. Cada camada é injetada uma
    # única vez por sessão (a v3.6 fica no <head>, sobrevive aos reruns) e os
    # poucos seletores em comum usam a mesma paleta oficial — a ordem apenas
    # desempata detalhes cosméticos. A chamada final garante cobertura mesmo
    # quando a página ativa não executa aplicar_estilo().
    _aplicar_estilo_seguro(tema_ativo)
    injetar_css_dashboards()
    GerenciadorEstilos.injetar_css_global()
    GerenciadorNavegacao.renderizar_sidebar_corporativa()

    st.session_state["_totale_root_navigation_shell"] = True
    pg.run()
    logger.info("Aplicação iniciada com sucesso")


if __name__ == "__main__":
    main()
