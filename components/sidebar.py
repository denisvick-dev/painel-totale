"""
sidebar.py
==========
Módulo centralizado de styling e componentes do Sidebar corporativo TOTALE.

Uso:
    from components.sidebar import (
        aplicar_sidebar_corp,
        render_sidebar_info,
        render_sidebar_filtro,
        render_sidebar_status
    )
    aplicar_sidebar_corp()
    render_sidebar_info(user_name="João", email="joao@totale.com")
"""

import streamlit as st
from datetime import datetime
from typing import Optional, Any, Literal
from zoneinfo import ZoneInfo

# ====================================================
# 🎨 PALETA CORPORATIVA
# ====================================================
TOTALE_AZUL = "#012869"
TOTALE_LARANJA = "#F37C04"
TOTALE_LARANJA_CLARO = "#FFBE64"
TOTALE_ROXO = "#8B5CF6"

COR_TEXTO_CLARO = "#F1F5F9"
COR_TEXTO_MEDIO = "#E2E8F0"
COR_FUNDO_DARK = "#0B1E3D"

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


# ====================================================
# 🔧 HELPERS INTERNOS
# ====================================================
def hex_to_rgb(hex_color: str) -> str:
    """Converte cor HEX (#RRGGBB) para string RGB (RRR, GGG, BBB) para uso em rgba()."""
    hex_color = hex_color.lstrip("#")
    return f"{int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}"


# ====================================================
# 🎨 STYLING (CSS)
# ====================================================
def aplicar_sidebar_corp() -> None:
    """
    Aplica o CSS corporativo completo ao sidebar.
    Deve ser chamado uma única vez, logo após o st.set_page_config.
    """
    st.markdown(_get_sidebar_css(), unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def _get_sidebar_css() -> str:
    """Retorna o CSS do sidebar corporativo."""

    # Cores convertidas para RGB para suportar transparência corretamente
    rgb_laranja = hex_to_rgb(TOTALE_LARANJA)
    rgb_azul = hex_to_rgb(TOTALE_AZUL)

    return f"""
    <style>
    /* ═════════════════════════════════════════════════════════════
       SIDEBAR CORPORATIVO TOTALE — TOPO LARANJA + DEEP NAVY
       ═════════════════════════════════════════════════════════════ */
    
    section[data-testid="stSidebar"] {{
        background: linear-gradient(
            180deg,
            {TOTALE_LARANJA_CLARO} 0%,
            {TOTALE_LARANJA} 8%,
            #E86B03 12%,
            #0B1E3D 20%,
            {TOTALE_AZUL} 50%,
            #001135 100%
        ) !important;
        border-right: 2px solid rgba({rgb_laranja}, 0.4) !important;
        box-shadow: 4px 0 20px rgba(0, 0, 0, 0.25) !important;
    }}

    /* Esconder o footer nativo do Streamlit ("Made with Streamlit") */
    footer {{visibility: hidden !important; display: none !important;}}
    .stApp > header {{background-color: transparent !important;}}

    /* ═════ CABEÇALHO (LOGO E BRANDING) ═════ */
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
        background: linear-gradient(
            180deg,
            rgba(255, 255, 255, 0.1) 0%,
            rgba(255, 255, 255, 0.0) 100%
        ) !important;
        padding: 16px 12px 8px 12px !important;
        border-radius: 0 !important;
    }}

    /* ═════ BOTÃO COLLAPSE ═════ */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {{
        background: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 6px !important;
        color: {COR_TEXTO_CLARO} !important;
        transition: all 0.2s ease !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {{
        background: rgba(255, 255, 255, 0.2) !important;
        border-color: rgba({rgb_laranja}, 0.6) !important;
    }}

    /* ═════ TÍTULOS E SEÇÕES ═════ */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {{
        color: {TOTALE_LARANJA_CLARO} !important;
        font-weight: 800 !important;
        font-size: 11px !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        border-bottom: 1px solid rgba({rgb_laranja}, 0.3) !important;
        padding-bottom: 6px !important;
        margin: 20px 0 12px 0 !important;
    }}

    /* ═════ MENU NATIVO DE PÁGINAS ═════ */
    section[data-testid="stSidebarNav"] li:first-child {{
        display: none !important; /* Esconde item padrão */
    }}

    section[data-testid="stSidebarNav"] a {{
        background-color: rgba(6, 21, 47, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 8px !important;
        margin: 6px 12px !important;
        padding: 8px 14px !important;
        transition: all 0.2s ease !important;
    }}
    section[data-testid="stSidebarNav"] a:hover {{
        background-color: rgba(10, 34, 74, 0.8) !important;
        border-color: rgba({rgb_laranja}, 0.5) !important;
        transform: translateX(4px);
    }}
    section[data-testid="stSidebarNav"] a span {{
        color: {COR_TEXTO_CLARO} !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }}

    /* PÁGINA ATIVA */
    section[data-testid="stSidebarNav"] a[aria-current="page"] {{
        background: linear-gradient(135deg, rgba({rgb_laranja}, 0.2) 0%, rgba({rgb_azul}, 0.5) 100%) !important;
        border: 1px solid {TOTALE_LARANJA} !important;
        box-shadow: 0 4px 10px rgba({rgb_laranja}, 0.2) !important;
    }}
    section[data-testid="stSidebarNav"] a[aria-current="page"] span {{
        color: {TOTALE_LARANJA_CLARO} !important;
        font-weight: 700 !important;
    }}

    /* ═════ INPUTS E LABELS ═════ */
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
        color: {TOTALE_LARANJA_CLARO} !important;
        font-weight: 600 !important;
        font-size: 12px !important;
    }}

    section[data-testid="stSidebar"] [data-baseweb="select"],
    section[data-testid="stSidebar"] [data-baseweb="input"] {{
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba({rgb_laranja}, 0.3) !important;
        border-radius: 6px !important;
        color: white !important;
    }}
    section[data-testid="stSidebar"] [data-baseweb="select"]:hover,
    section[data-testid="stSidebar"] [data-baseweb="input"]:focus {{
        border-color: {TOTALE_LARANJA} !important;
        background-color: rgba(255, 255, 255, 0.1) !important;
    }}

    /* ═════ BOTÕES ═════ */
    section[data-testid="stSidebar"] .stButton button {{
        background: linear-gradient(135deg, {TOTALE_LARANJA} 0%, #D86A02 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 10px rgba({rgb_laranja}, 0.3) !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        filter: brightness(1.1) !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba({rgb_laranja}, 0.5) !important;
    }}

    /* ═════ DIVIDERS ═════ */
    section[data-testid="stSidebar"] hr {{
        border-color: rgba({rgb_laranja}, 0.2) !important;
        margin: 16px 0 !important;
    }}

    /* ═════ SCROLLBAR ═════ */
    section[data-testid="stSidebar"] ::-webkit-scrollbar {{
        width: 6px !important;
    }}
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{
        background: rgba({rgb_laranja}, 0.4) !important;
        border-radius: 10px !important;
    }}
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {{
        background: rgba({rgb_laranja}, 0.8) !important;
    }}
    </style>
    """


# ====================================================
# 🧩 COMPONENTES DO SIDEBAR
# ====================================================


def render_sidebar_info(
    user_name: str = "Usuário",
    email: Optional[str] = None,
    role: Optional[str] = None,
    avatar: Optional[str] = None,
) -> None:
    """Renderiza bloco de informações do usuário (Avatar inteligente)."""

    # Tratamento de avatar (Imagem via URL/Base64 ou Emoji)
    if avatar and (avatar.startswith("http") or avatar.startswith("data:image")):
        avatar_html = f'<img src="{avatar}" style="width:50px; height:50px; border-radius:50%; object-fit:cover; border: 2px solid {TOTALE_LARANJA_CLARO}; margin-bottom: 8px;">'
    else:
        avatar_text = avatar or "👤"
        avatar_html = (
            f'<div style="font-size: 32px; margin-bottom: 4px;">{avatar_text}</div>'
        )

    role_text = f" • {role}" if role else ""

    rgb_laranja = hex_to_rgb(TOTALE_LARANJA)
    st.markdown(
        f"""
        <div style="
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba({rgb_laranja}, 0.2);
            border-radius: 8px;
            padding: 16px 12px;
            margin-bottom: 16px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">
            {avatar_html}
            <p style="color: {COR_TEXTO_CLARO}; font-weight: 700; font-size: 14px; margin: 0 0 2px 0;">
                {user_name}
            </p>
            {f'<p style="color: {TOTALE_LARANJA_CLARO}; font-size: 11px; font-weight:600; margin: 0;">{role_text.strip(" • ")}</p>' if role else ''}
            {f'<p style="color: {COR_TEXTO_MEDIO}; font-size: 11px; margin: 4px 0 0 0; word-break: break-word; opacity: 0.8;">{email}</p>' if email else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_status(
    status: Literal["ok", "alerta", "erro"] = "ok",
    mensagem: str = "Sistema operacional",
    ultima_atualizacao: Optional[datetime] = None,
) -> None:
    """Renderiza indicador de status com 3 níveis (ok, alerta, erro)."""

    configs = {
        "ok": {
            "bg": "rgba(16, 185, 129, 0.15)",
            "border": "#10B981",
            "icon": "✅",
            "color": "#34D399",
        },
        "alerta": {
            "bg": "rgba(245, 158, 11, 0.15)",
            "border": "#F59E0B",
            "icon": "⚠️",
            "color": "#FCD34D",
        },
        "erro": {
            "bg": "rgba(239, 68, 68, 0.15)",
            "border": "#EF4444",
            "icon": "❌",
            "color": "#FCA5A5",
        },
    }

    cfg = configs.get(status, configs["ok"])

    tempo_html = ""
    if ultima_atualizacao:
        tempo = ultima_atualizacao.strftime("%d/%m/%Y %H:%M")
        tempo_html = f"<p style='font-size: 10px; margin: 4px 0 0 0; color: rgba(255,255,255,0.6);'>🕒 Atualizado às {tempo}</p>"

    st.markdown(
        f"""
        <div style="
            background: {cfg['bg']};
            border: 1px solid {cfg['border']};
            border-radius: 6px;
            padding: 10px;
            margin: 12px 0;
            text-align: center;
        ">
            <p style="font-size: 13px; font-weight: 600; margin: 0; color: {cfg['color']};">
                {cfg['icon']} {mensagem}
            </p>
            {tempo_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_filtro(
    label: str,
    options: list,
    default: Optional[str] = None,
    key: Optional[str] = None,
    help_text: Optional[str] = None,
    multi: bool = False,
) -> Any:
    """Renderiza filtro customizado no sidebar."""
    if multi:
        return st.multiselect(
            label, options=options, default=default, key=key, help=help_text
        )
    else:
        index = options.index(default) if default and default in options else 0
        return st.selectbox(
            label, options=options, index=index, key=key, help=help_text
        )


def render_sidebar_section(title: str) -> None:
    """Renderiza um título de seção customizado."""
    st.markdown(f"#### {title}", unsafe_allow_html=False)


def render_sidebar_divider() -> None:
    """Renderiza divisor sutil."""
    st.divider()


def render_sidebar_spacer(height: int = 150) -> None:
    """Cria um espaço vertical invisível (útil para empurrar o footer para baixo)."""
    st.markdown(f'<div style="height: {height}px;"></div>', unsafe_allow_html=True)


def render_sidebar_footer_info(
    versao: str = "1.0.0",
    ambiente: str = "Produção",
    mostrar_timestamp: bool = True,
) -> None:
    """Renderiza o rodapé de versão/ambiente."""
    info_items = [f"v{versao}", ambiente]

    if mostrar_timestamp:
        agora = datetime.now(FUSO_HORARIO)
        info_items.append(agora.strftime("%d/%m/%Y %H:%M"))

    info_text = " • ".join(info_items)
    rgb_laranja = hex_to_rgb(TOTALE_LARANJA)

    st.markdown(
        f"""
        <div style="
            background: rgba(0, 0, 0, 0.25);
            border-top: 1px solid rgba({rgb_laranja}, 0.2);
            padding: 12px;
            margin-top: 20px;
            text-align: center;
            font-size: 10px;
            color: rgba(255,255,255,0.5);
            font-weight: 500;
            border-radius: 6px;
        ">
            {info_text}<br>
            <span style="color: {TOTALE_LARANJA_CLARO}; font-weight: 700;">SISTEMA TOTALE</span>
        </div>
        """,
        unsafe_allow_html=True,
    )