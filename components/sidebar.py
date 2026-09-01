"""
sidebar.py
==========
Módulo centralizado de styling e componentes do Sidebar corporativo TOTALE.

Design System:
    - Fundo escuro sólido (Deep Navy)
    - Acento laranja apenas em elementos ativos/hover
    - Tipografia hierárquica e legível
    - Componentes limpos sem "cards blocados"

Uso:
    from components.sidebar import (
        aplicar_sidebar_corp,
        render_sidebar_info,
        render_sidebar_filtro,
        render_sidebar_status,
        render_sidebar_section,
        render_sidebar_divider,
        render_sidebar_spacer,
        render_sidebar_footer_info,
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

# Novas cores do design escuro moderno
COR_FUNDO_SIDEBAR = "#0B1120"  # Azul quase preto (fundo principal)
COR_FUNDO_HOVER = "#1E293B"  # Fundo em hover suave
COR_BORDA_SUTIL = "#1E293B"  # Bordas internas discretas
COR_TEXTO_CLARO = "#F1F5F9"
COR_TEXTO_MEDIO = "#CBD5E1"
COR_TEXTO_SUAVE = "#64748B"  # Para categorias e labels discretas
COR_FUNDO_DARK = "#0F172A"

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
    Aplica o CSS corporativo moderno ao sidebar.
    Deve ser chamado uma única vez, logo após o st.set_page_config.
    """
    st.markdown(_get_sidebar_css(), unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def _get_sidebar_css() -> str:
    """Retorna o CSS do sidebar corporativo com design moderno escuro."""

    rgb_laranja = hex_to_rgb(TOTALE_LARANJA)
    rgb_azul = hex_to_rgb(TOTALE_AZUL)

    return f"""
    <style>
    /* ═════════════════════════════════════════════════════════════
       SIDEBAR CORPORATIVO TOTALE — DESIGN MODERNO ESCURO
       ═════════════════════════════════════════════════════════════ */

    /* Fundo sólido elegante (sem gradiente laranja agressivo) */
    section[data-testid="stSidebar"] {{
        background: {COR_FUNDO_SIDEBAR} !important;
        border-right: 1px solid {COR_BORDA_SUTIL} !important;
    }}

    /* Esconder o footer nativo do Streamlit */
    footer {{visibility: hidden !important; display: none !important;}}
    .stApp > header {{background-color: transparent !important;}}

    /* Scrollbar discreta */
    section[data-testid="stSidebar"] ::-webkit-scrollbar {{
        width: 4px !important;
        background: transparent !important;
    }}
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{
        background: {COR_BORDA_SUTIL} !important;
        border-radius: 10px !important;
    }}
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {{
        background: {COR_TEXTO_SUAVE} !important;
    }}

    /* ═════ CABEÇALHO (LOGO E BRANDING) ═════ */
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
        background: transparent !important;
        padding: 12px 12px 8px 12px !important;
        border-radius: 0 !important;
    }}

    /* ═════ BOTÃO COLLAPSE (Discreto) ═════ */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {{
        background: transparent !important;
        border: none !important;
        color: {COR_TEXTO_SUAVE} !important;
        transition: all 0.2s ease !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {{
        background: rgba(255, 255, 255, 0.05) !important;
        color: {COR_TEXTO_CLARO} !important;
    }}

    /* ═════ TÍTULOS E CATEGORIAS (Discretos e Alinhados à Esquerda) ═════ */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {{
        color: {COR_TEXTO_SUAVE} !important;
        font-weight: 700 !important;
        font-size: 11px !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        border-bottom: none !important;
        padding: 0 0 0 20px !important;
        margin: 24px 0 4px 0 !important;
        text-align: left !important;
    }}

    /* ═════ MENU NATIVO DE PÁGINAS ═════ */
    section[data-testid="stSidebarNav"] {{
        padding-top: 0 !important;
    }}
    
    section[data-testid="stSidebarNav"] li:first-child {{
        display: none !important;
    }}

    /* Itens de menu limpos, sem cards blocados */
    section[data-testid="stSidebarNav"] a {{
        background-color: transparent !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        border-radius: 0 6px 6px 0 !important;
        margin: 2px 12px 2px 0 !important;
        padding: 8px 12px 8px 17px !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        box-shadow: none !important;
    }}
    section[data-testid="stSidebarNav"] a:hover {{
        background-color: rgba(255, 255, 255, 0.05) !important;
        transform: none !important;
    }}
    section[data-testid="stSidebarNav"] a span,
    section[data-testid="stSidebarNav"] a svg {{
        color: {COR_TEXTO_MEDIO} !important;
        fill: {COR_TEXTO_MEDIO} !important;
        font-weight: 500 !important;
        font-size: 14px !important;
    }}

    /* PÁGINA ATIVA (Destaque laranja elegante) */
    section[data-testid="stSidebarNav"] a[aria-current="page"] {{
        background-color: rgba({rgb_laranja}, 0.1) !important;
        border-left: 3px solid {TOTALE_LARANJA} !important;
        box-shadow: none !important;
    }}
    section[data-testid="stSidebarNav"] a[aria-current="page"] span,
    section[data-testid="stSidebarNav"] a[aria-current="page"] svg {{
        color: {TOTALE_LARANJA} !important;
        fill: {TOTALE_LARANJA} !important;
        font-weight: 700 !important;
    }}

    /* ═════ LABELS DE WIDGETS ═════ */
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
        color: {COR_TEXTO_MEDIO} !important;
        font-weight: 600 !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.4px !important;
    }}

    /* ═════ INPUTS / SELECTS ═════ */
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="input"],
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] select {{
        background-color: {COR_FUNDO_DARK} !important;
        border: 1px solid {COR_BORDA_SUTIL} !important;
        border-radius: 6px !important;
        color: {COR_TEXTO_CLARO} !important;
    }}
    section[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
    section[data-testid="stSidebar"] [data-baseweb="input"]:focus-within,
    section[data-testid="stSidebar"] input:focus {{
        border-color: {TOTALE_LARANJA} !important;
        background-color: {COR_FUNDO_HOVER} !important;
    }}

    /* ═════ BOTÕES ═════ */
    section[data-testid="stSidebar"] .stButton button {{
        background: linear-gradient(135deg, {TOTALE_LARANJA} 0%, #D86A02 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 6px rgba({rgb_laranja}, 0.25) !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        filter: brightness(1.1) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba({rgb_laranja}, 0.4) !important;
    }}

    /* ═════ DIVIDERS ═════ */
    section[data-testid="stSidebar"] hr {{
        background: {COR_BORDA_SUTIL} !important;
        border: none !important;
        height: 1px !important;
        margin: 16px 20px !important;
    }}

    /* ═════ EXPANDERS ═════ */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {{
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid {COR_BORDA_SUTIL} !important;
        border-radius: 8px !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {{
        color: {COR_TEXTO_CLARO} !important;
        font-weight: 600 !important;
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
    """
    Renderiza bloco de informações do usuário com Avatar inteligente.
    Design escuro moderno alinhado ao novo layout.
    """
    # Tratamento de avatar (Imagem via URL/Base64 ou Emoji)
    if avatar and (avatar.startswith("http") or avatar.startswith("data:image")):
        avatar_html = (
            f'<img src="{avatar}" style="width:44px; height:44px; border-radius:50%; '
            f'object-fit:cover; border: 2px solid {TOTALE_LARANJA}; flex-shrink: 0;">'
        )
    else:
        avatar_text = avatar or "👤"
        avatar_html = (
            f'<div style="width:44px; height:44px; border-radius:50%; '
            f"background: linear-gradient(135deg, {TOTALE_LARANJA} 0%, #D86A02 100%); "
            f"display:flex; align-items:center; justify-content:center; "
            f'font-size: 20px; flex-shrink: 0;">{avatar_text}</div>'
        )

    role_html = ""
    if role:
        role_html = (
            f'<p style="color: {TOTALE_LARANJA}; font-size: 10px; font-weight:700; '
            f'margin: 2px 0 0 0; text-transform: uppercase; letter-spacing: 0.5px;">{role}</p>'
        )

    email_html = ""
    if email:
        email_html = (
            f'<p style="color: {COR_TEXTO_SUAVE}; font-size: 11px; margin: 2px 0 0 0; '
            f'word-break: break-word; font-weight: 400;">{email}</p>'
        )

    st.markdown(
        f"""
        <div style="
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid {COR_BORDA_SUTIL};
            border-radius: 8px;
            padding: 12px;
            margin: 8px 12px 16px 12px;
        ">
            {avatar_html}
            <div style="flex: 1; min-width: 0; text-align: left;">
                <p style="color: {COR_TEXTO_CLARO}; font-weight: 700; font-size: 13px; 
                          margin: 0; line-height: 1.2; overflow: hidden; text-overflow: ellipsis;">
                    {user_name}
                </p>
                {role_html}
                {email_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_status(
    status: Literal["ok", "alerta", "erro"] = "ok",
    mensagem: str = "Sistema operacional",
    ultima_atualizacao: Optional[datetime] = None,
) -> None:
    """
    Renderiza indicador de status com 3 níveis (ok, alerta, erro).
    Design discreto com pill de status.
    """
    configs = {
        "ok": {
            "bg": "rgba(16, 185, 129, 0.1)",
            "border": "rgba(16, 185, 129, 0.3)",
            "dot": "#10B981",
            "color": "#34D399",
        },
        "alerta": {
            "bg": "rgba(245, 158, 11, 0.1)",
            "border": "rgba(245, 158, 11, 0.3)",
            "dot": "#F59E0B",
            "color": "#FCD34D",
        },
        "erro": {
            "bg": "rgba(239, 68, 68, 0.1)",
            "border": "rgba(239, 68, 68, 0.3)",
            "dot": "#EF4444",
            "color": "#FCA5A5",
        },
    }

    cfg = configs.get(status, configs["ok"])

    tempo_html = ""
    if ultima_atualizacao:
        tempo = ultima_atualizacao.strftime("%d/%m/%Y %H:%M")
        tempo_html = (
            f"<p style='font-size: 10px; margin: 6px 0 0 0; color: {COR_TEXTO_SUAVE};'>"
            f"🕒 Atualizado às {tempo}</p>"
        )

    st.markdown(
        f"""
        <div style="
            background: {cfg['bg']};
            border: 1px solid {cfg['border']};
            border-radius: 6px;
            padding: 10px 12px;
            margin: 12px 12px;
        ">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; 
                             background: {cfg['dot']}; box-shadow: 0 0 8px {cfg['dot']};
                             flex-shrink: 0;"></span>
                <p style="font-size: 12px; font-weight: 600; margin: 0; 
                          color: {cfg['color']}; flex: 1;">
                    {mensagem}
                </p>
            </div>
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
    """Renderiza filtro customizado no sidebar (Selectbox ou Multiselect)."""
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
    """Renderiza um título de seção customizado (categoria de menu)."""
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
    """Renderiza o rodapé de versão/ambiente com design discreto."""
    info_items = [f"v{versao}", ambiente]

    if mostrar_timestamp:
        agora = datetime.now(FUSO_HORARIO)
        info_items.append(agora.strftime("%d/%m/%Y %H:%M"))

    info_text = " • ".join(info_items)

    st.markdown(
        f"""
        <div style="
            border-top: 1px solid {COR_BORDA_SUTIL};
            padding: 12px 16px;
            margin: 20px 12px 8px 12px;
            text-align: center;
            font-size: 10px;
            color: {COR_TEXTO_SUAVE};
            font-weight: 500;
        ">
            {info_text}<br>
            <span style="color: {TOTALE_LARANJA}; font-weight: 700; 
                         letter-spacing: 0.5px; font-size: 11px;">
                SISTEMA TOTALE
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )