"""
sidebar.py
==========
Módulo de Design System e Componentes Visuais Premium para o Sidebar TOTALE.

Padrões Aplicados:
    - Base Cromática: Azul Corporativo Real (RGB 1, 40, 105) adaptado para Dark Mode.
    - Elementos de Destaque: Laranja Corporativo Ativo (RGB 243, 124, 4).
    - Tipografia: Hierarquia corporativa clean com espaçamento de caracteres otimizado.
"""

import streamlit as st
from datetime import datetime
from typing import Optional, Any, Literal
from zoneinfo import ZoneInfo

# ====================================================
# 🎨 PALETA CORPORATIVA OFICIAL (HEXADECIMAL PURIFICADO)
# ====================================================
TOTALE_AZUL_OFICIAL = "#012869"  # RGB(1, 40, 105)
TOTALE_LARANJA_OFICIAL = "#F37C04"  # RGB(243, 124, 4)
TOTALE_LARANJA_HOVER = "#D46B02"

# Tons de suporte derivados da marca para o Dark Mode Premium
COR_FUNDO_SIDEBAR = "#010D20"  # Azul profundo corporativo (fundo principal)
COR_FUNDO_DARK = "#010814"  # Base sólida para inputs e caixas de seleção
COR_FUNDO_HOVER = "#02173A"  # Destaque de linha em hover
COR_BORDA_SUTIL = "#032054"  # Linhas divisórias internas discretas

# Paleta de textos e legibilidade
COR_TEXTO_TITULO = "#F8FAFC"
COR_TEXTO_MEDIO = "#E2E8F0"
COR_TEXTO_MUTED = "#94A3B8"  # Cinza azulado para labels e descrições secundárias

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


# ====================================================
# 🔧 HELPERS INTERNOS
# ====================================================
def hex_to_rgb(hex_color: str) -> str:
    """Converte cor HEX para string RGB (RRR, GGG, BBB) para injeções via RGBA."""
    hex_color = hex_color.lstrip("#")
    return f"{int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}"


# ====================================================
# 🎨 APLICAÇÃO DE ESTILO (CSS)
# ====================================================
def aplicar_sidebar_corp() -> None:
    """
    Injeta a folha de estilo corporativa premium customizada para a TOTALE.
    Deve ser invocado no início do script logo após a configuração de página.
    """
    st.markdown(_get_sidebar_css(), unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def _get_sidebar_css() -> str:
    """Gera a engine CSS do ecossistema visual do sidebar."""
    rgb_laranja = hex_to_rgb(TOTALE_LARANJA_OFICIAL)

    return f"""
    <style>
    /* ═════════════════════════════════════════════════════════════
       ESTRUTURA PRINCIPAL DO SIDEBAR
       ═════════════════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {{
        background-color: {COR_FUNDO_SIDEBAR} !important;
        border-right: 1px solid {COR_BORDA_SUTIL} !important;
    }}

    /* Reset global de cabeçalhos e rodapés nativos */
    footer {{visibility: hidden !important; display: none !important;}}
    .stApp > header {{background-color: transparent !important;}}

    /* Scrollbar minimalista corporativa */
    section[data-testid="stSidebar"] ::-webkit-scrollbar {{
        width: 5px !important;
        background: transparent !important;
    }}
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{
        background: {COR_BORDA_SUTIL} !important;
        border-radius: 20px !important;
    }}
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {{
        background: {COR_TEXTO_MUTED} !important;
    }}

    /* ═════════════════════════════════════════════════════════════
       NAVEGAÇÃO NATIVA (LINKS E PÁGINAS)
       ═════════════════════════════════════════════════════════════ */
    section[data-testid="stSidebarNav"] {{
        padding-top: 8px !important;
    }}
    section[data-testid="stSidebarNav"] a {{
        background-color: transparent !important;
        border-left: 3px solid transparent !important;
        border-radius: 0 4px 4px 0 !important;
        margin: 1px 12px 1px 0 !important;
        padding: 9px 12px 9px 18px !important;
        transition: all 0.15s ease-in-out !important;
        display: flex !important;
        align-items: center !important;
    }}
    section[data-testid="stSidebarNav"] a:hover {{
        background-color: {COR_FUNDO_HOVER} !important;
    }}
    section[data-testid="stSidebarNav"] a span,
    section[data-testid="stSidebarNav"] a svg {{
        color: {COR_TEXTO_MEDIO} !important;
        fill: {COR_TEXTO_MEDIO} !important;
        font-weight: 500 !important;
        font-size: 13.5px !important;
        letter-spacing: 0.2px !important;
    }}

    /* Estado Ativo do Menu (Identidade TOTALE) */
    section[data-testid="stSidebarNav"] a[aria-current="page"] {{
        background-color: rgba({rgb_laranja}, 0.08) !important;
        border-left: 3px solid {TOTALE_LARANJA_OFICIAL} !important;
    }}
    section[data-testid="stSidebarNav"] a[aria-current="page"] span,
    section[data-testid="stSidebarNav"] a[aria-current="page"] svg {{
        color: {TOTALE_LARANJA_OFICIAL} !important;
        fill: {TOTALE_LARANJA_OFICIAL} !important;
        font-weight: 600 !important;
    }}

    /* ═════════════════════════════════════════════════════════════
       COMPONENTES DE FORMULÁRIO E INPUTS NATIVOS
       ═════════════════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
        color: {COR_TEXTO_MUTED} !important;
        font-weight: 600 !important;
        font-size: 11px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.8px !important;
        margin-bottom: 4px !important;
    }}
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="input"],
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] select {{
        background-color: {COR_FUNDO_DARK} !important;
        border: 1px solid {COR_BORDA_SUTIL} !important;
        border-radius: 6px !important;
        color: {COR_TEXTO_TITULO} !important;
        font-size: 13px !important;
    }}
    section[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
    section[data-testid="stSidebar"] [data-baseweb="input"]:focus-within {{
        border-color: {TOTALE_LARANJA_OFICIAL} !important;
        background-color: {COR_FUNDO_HOVER} !important;
        box-shadow: 0 0 0 1px rgba({rgb_laranja}, 0.2) !important;
    }}

    /* Botão de Ação de Alto Impacto */
    section[data-testid="stSidebar"] .stButton button {{
        background: {TOTALE_LARANJA_OFICIAL} !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 5px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        letter-spacing: 0.3px !important;
        width: 100% !important;
        padding: 6px 12px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        background: {TOTALE_LARANJA_HOVER} !important;
        box-shadow: 0 4px 10px rgba({rgb_laranja}, 0.3) !important;
        transform: translateY(-0.5px);
    }}

    /* ═════════════════════════════════════════════════════════════
       COMPONENTES CUSTOMIZADOS (TOTALE UI)
       ═════════════════════════════════════════════════════════════ */
    .sidebar-section-title {{
        color: {COR_TEXTO_MUTED} !important;
        font-weight: 700 !important;
        font-size: 10px !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        padding: 22px 0 6px 6px !important;
        margin: 0 !important;
    }}
    .user-profile-box {{
        padding: 12px 14px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid {COR_BORDA_SUTIL};
        margin: 4px 0 16px 0;
    }}
    .user-profile-name {{ color: {COR_TEXTO_TITULO}; font-size: 13.5px; font-weight: 600; }}
    .user-profile-email {{ color: {COR_TEXTO_MUTED}; font-size: 11px; margin-top: 1px; }}

    .status-container {{
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 12.5px;
        color: {COR_TEXTO_MEDIO};
        padding: 6px 4px;
    }}
    .status-pill {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        box-shadow: 0 0 6px currentColor;
    }}
    </style>
    """


# ====================================================
# 🧱 COMPONENTES DE INTERFACE REUTILIZÁVEIS
# ====================================================
def render_sidebar_info(user_name: str, email: str) -> None:
    """Gera o bloco identificador de perfil do usuário logado na plataforma."""
    with st.sidebar:
        st.markdown(
            f"""
            <div class="user-profile-box">
                <div class="user-profile-name">👤 {user_name}</div>
                <div class="user-profile-email">{email}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar_section(title: str) -> None:
    """Cria um título de agrupamento/categoria corporativa textual no menu."""
    with st.sidebar:
        st.markdown(
            f'<p class="sidebar-section-title">{title}</p>', unsafe_allow_html=True
        )


def render_sidebar_status(
    label: str, tipo: Literal["success", "warning", "danger", "info"] = "success"
) -> None:
    """Exibe indicadores de status da aplicação em formato micro-pill brilhante."""
    cores_status = {
        "success": "#10B981",  # Verde esmeralda operacional
        "warning": "#F59E0B",  # Ambar corporativo
        "danger": "#EF4444",  # Vermelho crítico
        "info": "#3B82F6",  # Azul informativo
    }
    cor = cores_status.get(tipo, cores_status["success"])
    with st.sidebar:
        st.markdown(
            f"""
            <div class="status-container">
                <div class="status-pill" style="background-color: {cor}; color: {cor};"></div>
                <span>{label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar_divider() -> None:
    """Gera uma linha horizontal divisória fina ultra sutil alinhada ao tema."""
    with st.sidebar:
        st.markdown(
            f'<hr style="margin: 16px 0; border: 0; border-top: 1px solid {COR_BORDA_SUTIL};">',
            unsafe_allow_html=True,
        )


def render_sidebar_spacer(height: int = 15) -> None:
    """Cria um bloco espaçador vertical transparente milimétrico."""
    with st.sidebar:
        st.markdown(f'<div style="height: {height}px;"></div>', unsafe_allow_html=True)


def render_sidebar_footer_info(versao: str = "v2.5.0") -> None:
    """Renderiza as informações consolidadas de compliance no rodapé operacional."""
    agora = datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y %H:%M")
    with st.sidebar:
        render_sidebar_divider()
        st.markdown(
            f"""
            <div style="font-size: 11px; color: {COR_TEXTO_MUTED}; line-height: 1.6; padding-left: 6px;">
                <div>🕒 {agora} BRT</div>
                <div>🚀 Versão {versao}</div>
                <div style="margin-top: 6px; font-weight: 600; color: {COR_TEXTO_MEDIO}; font-size: 10px; letter-spacing: 0.3px;">© TOTALE TECNOLOGIA</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar_filtro(
    label: str, options: list, key: str, default: Any = None
) -> Any:
    """Abstração otimizada do st.selectbox respeitando a estilização unificada corporativa."""
    with st.sidebar:
        index = 0
        if default in options:
            index = options.index(default)
        return st.selectbox(label, options=options, index=index, key=key)
