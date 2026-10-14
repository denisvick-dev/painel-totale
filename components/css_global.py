"""components/css_global.py
===========================
Injeção de CSS global para os componentes nativos do Streamlit.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Problema resolvido: cada página repetia blocos de ``st.markdown("<style>…")``
para "consertar" o visual dos componentes nativos (botões, inputs, abas,
expansores, tabelas, métricas…). Isso gerava dezenas de nós ``<style>`` no DOM,
reprocessados a cada rerun, e aparências divergentes entre painéis.

Este módulo centraliza tudo em **um único nó ``<style>`` no ``<head>``**,
gravado uma vez por sessão (idempotente por versão), com:

• ``css_variaveis_marca``: tokens de design da TOTALE (azul ``#012869``,
  laranja ``#F37C04``, raios, sombras e espaçamentos) como CSS custom
  properties — qualquer HTML de página usa ``var(--totale-azul)``.
• ``css_botoes``: botões primário/secundário, download, submit, page_link,
  link_button e controle segmentado (``st.segmented_control``).
• ``css_entradas``: text/number/date/time/textarea, selectbox, multiselect,
  file uploader e color picker com foco e hover na cor de ação.
• ``css_selecao``: radio, checkbox, toggle e slider.
• ``css_containers``: densidade do ``block-container``, colunas, container com
  borda, abas, expansores, popover, dialog, divider, captions, headings, code,
  alertas, progresso, status, spinner/skeleton, toast, imagens, tabelas,
  dataframes, chat e tooltips.
• ``css_acessibilidade``: foco visível, seleção de texto, barras de rolagem,
  impressão e respeito a ``prefers-reduced-motion``.
• ``injetar_css_global``: agregador idempotente (também inclui o CSS dos
  cartões de KPI avançados e das primitivas de layout de página).

Regra de escopo: tudo que é corpo de página fica sob ``[data-testid="stMain"]``.
A sidebar continua exclusiva de ``components.sidebar`` — nada aqui a toca.
"""

from __future__ import annotations

import json
import logging

import streamlit as st

from components.componentes import Cores, _injetar_js, _safe_render_html
from components.graficos import (
    AZUL_CLARO,
    AZUL_ESCURO,
    AZUL_TOTALE,
    LARANJA_CLARO,
    LARANJA_ESCURO,
    LARANJA_TOTALE,
)
from components.kpi_cards import css_kpi_avancado

logger = logging.getLogger(__name__)

VERSAO_CSS_GLOBAL = "1.0.0"
ID_NO_HEAD = "totale-css-global-v1"
_CHAVE_SESSAO = "_totale_css_global_versao"

# Prefixo curto usado pelos seletores (mantém o CSS legível e menor).
_MAIN = '[data-testid="stMain"]'


# ====================================================
# 🎨 BLOCO 1: TOKENS DE DESIGN (CSS CUSTOM PROPERTIES)
# ====================================================
def css_variaveis_marca() -> str:
    """Tokens da marca disponíveis como ``var(--totale-*)`` em qualquer página."""
    return f"""
    :root {{
        --totale-azul: {AZUL_TOTALE};
        --totale-azul-claro: {AZUL_CLARO};
        --totale-azul-escuro: {AZUL_ESCURO};
        --totale-laranja: {LARANJA_TOTALE};
        --totale-laranja-claro: {LARANJA_CLARO};
        --totale-laranja-escuro: {LARANJA_ESCURO};
        --totale-azul-suave: #E8EEF8;
        --totale-laranja-suave: #FFF3E6;
        --totale-texto: {Cores.TEXTO};
        --totale-texto-2: {Cores.TEXTO_2};
        --totale-texto-3: {Cores.TEXTO_3};
        --totale-borda: {Cores.BORDA};
        --totale-fundo: {Cores.FUNDO};
        --totale-card: #FFFFFF;
        --totale-sucesso: {Cores.SUCESSO};
        --totale-alerta: {Cores.ALERTA};
        --totale-verde: #22C55E;
        --totale-verde-escuro: {Cores.SUCESSO};
        --totale-vermelho: #DC2626;
        --totale-ambar: #F59E0B;
        --totale-raio-sm: 8px;
        --totale-raio-md: 12px;
        --totale-raio-lg: 16px;
        --totale-sombra-sm: 0 1px 2px rgba(15, 23, 42, 0.05);
        --totale-sombra-md: 0 8px 22px rgba(15, 23, 42, 0.06);
        --totale-sombra-lg: 0 16px 36px rgba(1, 40, 105, 0.14);
        --totale-espaco-secao: 26px;
        --totale-transicao: 0.18s ease;
    }}
    """


# ====================================================
# 🔘 BLOCO 2: BOTÕES E AÇÕES
# ====================================================
def css_botoes() -> str:
    """Botões, downloads, page_link e controle segmentado na identidade TOTALE."""
    return f"""
    {_MAIN} [data-testid="stButton"] > button,
    {_MAIN} [data-testid="stDownloadButton"] > button,
    {_MAIN} [data-testid="stFormSubmitButton"] > button,
    {_MAIN} [data-testid="stLinkButton"] > a,
    {_MAIN} [data-testid="stPageLink"] > a {{
        border-radius: var(--totale-raio-sm) !important;
        border: 1px solid var(--totale-borda) !important;
        font-weight: 650 !important;
        letter-spacing: -0.01em;
        transition: transform var(--totale-transicao), box-shadow var(--totale-transicao),
            border-color var(--totale-transicao), background var(--totale-transicao);
    }}
    {_MAIN} [data-testid="stButton"] > button:hover,
    {_MAIN} [data-testid="stDownloadButton"] > button:hover,
    {_MAIN} [data-testid="stFormSubmitButton"] > button:hover {{
        transform: translateY(-1px);
        border-color: var(--totale-azul) !important;
        box-shadow: 0 6px 16px rgba(1, 40, 105, 0.14);
    }}
    {_MAIN} [data-testid="stButton"] > button:active,
    {_MAIN} [data-testid="stDownloadButton"] > button:active {{
        transform: translateY(0);
        box-shadow: var(--totale-sombra-sm);
    }}
    {_MAIN} button[kind="primary"],
    {_MAIN} [data-testid="stBaseButton-primary"] {{
        background: linear-gradient(135deg, var(--totale-azul) 0%, var(--totale-azul-claro) 100%) !important;
        border-color: var(--totale-azul) !important;
        color: #FFFFFF !important;
        box-shadow: 0 2px 8px rgba(1, 40, 105, 0.22) !important;
    }}
    {_MAIN} button[kind="primary"]:hover,
    {_MAIN} [data-testid="stBaseButton-primary"]:hover {{
        background: linear-gradient(135deg, var(--totale-azul-escuro) 0%, var(--totale-azul) 100%) !important;
        border-color: var(--totale-laranja) !important;
        box-shadow: 0 8px 20px rgba(1, 40, 105, 0.28) !important;
    }}
    {_MAIN} button[kind="primary"]:disabled,
    {_MAIN} [data-testid="stBaseButton-primary"]:disabled {{
        background: #E2E8F0 !important;
        border-color: #E2E8F0 !important;
        color: #94A3B8 !important;
        box-shadow: none !important;
    }}
    {_MAIN} [data-testid="stPageLink"] > a:hover {{
        border-color: var(--totale-laranja) !important;
        background: var(--totale-laranja-suave);
    }}
    /* Controle segmentado / pill group (st.segmented_control, st.pills) */
    {_MAIN} [data-testid="stButtonGroup"] button {{
        border-radius: 0 !important;
        border: 1px solid var(--totale-borda) !important;
        font-weight: 600 !important;
        color: var(--totale-texto-2) !important;
    }}
    {_MAIN} [data-testid="stButtonGroup"] button:first-of-type {{
        border-radius: var(--totale-raio-sm) 0 0 var(--totale-raio-sm) !important;
    }}
    {_MAIN} [data-testid="stButtonGroup"] button:last-of-type {{
        border-radius: 0 var(--totale-raio-sm) var(--totale-raio-sm) 0 !important;
    }}
    {_MAIN} [data-testid="stButtonGroup"] button[aria-pressed="true"],
    {_MAIN} [data-testid="stButtonGroup"] button:has(input:checked) {{
        background: var(--totale-azul) !important;
        color: #FFFFFF !important;
        border-color: var(--totale-azul) !important;
    }}
    """


# ====================================================
# 📝 BLOCO 3: ENTRADAS DE DADOS (INPUTS)
# ====================================================
def css_entradas() -> str:
    """Campos de texto, seleção, data, número e upload com foco na cor de ação."""
    return f"""
    {_MAIN} [data-testid="stTextInput"] input,
    {_MAIN} [data-testid="stNumberInput"] input,
    {_MAIN} [data-testid="stTextArea"] textarea,
    {_MAIN} [data-testid="stDateInput"] input,
    {_MAIN} [data-testid="stTimeInput"] input {{
        border-radius: var(--totale-raio-sm) !important;
        border: 1.5px solid var(--totale-borda) !important;
        background: #FFFFFF !important;
        transition: border-color var(--totale-transicao), box-shadow var(--totale-transicao);
    }}
    {_MAIN} [data-testid="stTextInput"] input:focus,
    {_MAIN} [data-testid="stNumberInput"] input:focus,
    {_MAIN} [data-testid="stTextArea"] textarea:focus,
    {_MAIN} [data-testid="stDateInput"] input:focus {{
        border-color: var(--totale-laranja) !important;
        box-shadow: 0 0 0 3px rgba(243, 124, 4, 0.16) !important;
    }}
    {_MAIN} [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    {_MAIN} [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
        border-radius: var(--totale-raio-sm) !important;
        border: 1.5px solid var(--totale-borda) !important;
        background: #FFFFFF !important;
        transition: border-color var(--totale-transicao), box-shadow var(--totale-transicao);
    }}
    {_MAIN} [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
    {_MAIN} [data-testid="stMultiSelect"] div[data-baseweb="select"] > div:hover {{
        border-color: var(--totale-azul-claro) !important;
    }}
    {_MAIN} [data-testid="stSelectbox"] div[data-baseweb="select"][aria-expanded="true"] > div,
    {_MAIN} [data-testid="stMultiSelect"] div[data-baseweb="select"][aria-expanded="true"] > div {{
        border-color: var(--totale-laranja) !important;
        box-shadow: 0 0 0 3px rgba(243, 124, 4, 0.14) !important;
    }}
    {_MAIN} label p,
    {_MAIN} [data-testid="stWidgetLabel"] p {{
        color: var(--totale-azul) !important;
        font-weight: 700 !important;
        font-size: 12.5px !important;
        letter-spacing: 0.01em;
    }}
    {_MAIN} span[data-baseweb="tag"] {{
        background-color: var(--totale-azul) !important;
        border-radius: 6px !important;
    }}
    {_MAIN} span[data-baseweb="tag"] span {{
        color: #FFFFFF !important;
    }}
    {_MAIN} [data-testid="stFileUploader"] section {{
        border-radius: var(--totale-raio-md);
    }}
    {_MAIN} [data-testid="stFileUploaderDropzone"] {{
        border: 1.5px dashed var(--totale-borda) !important;
        border-radius: var(--totale-raio-md) !important;
        background: #FBFCFE !important;
        transition: border-color var(--totale-transicao), background var(--totale-transicao);
    }}
    {_MAIN} [data-testid="stFileUploaderDropzone"]:hover {{
        border-color: var(--totale-laranja) !important;
        background: var(--totale-laranja-suave) !important;
    }}
    {_MAIN} [data-testid="stFileUploaderDropzone"] button {{
        border-color: var(--totale-azul) !important;
        color: var(--totale-azul) !important;
    }}
    {_MAIN} [data-baseweb="popover"] {{
        border-radius: var(--totale-raio-md) !important;
        box-shadow: var(--totale-sombra-lg) !important;
    }}
    {_MAIN} [data-baseweb="menu"] li:hover {{
        background: var(--totale-azul-suave) !important;
    }}
    """


# ====================================================
# ✅ BLOCO 4: SELEÇÃO (RADIO, CHECKBOX, TOGGLE, SLIDER)
# ====================================================
def css_selecao() -> str:
    """Marcação e slider com as cores oficiais."""
    return f"""
    {_MAIN} [data-testid="stRadio"] label:hover,
    {_MAIN} [data-testid="stCheckbox"] label:hover {{
        color: var(--totale-azul);
    }}
    {_MAIN} [data-testid="stCheckbox"] input:checked ~ span[data-baseweb="checkbox"],
    {_MAIN} [data-testid="stRadio"] span[data-baseweb="radio"] span:has(input:checked) {{
        border-color: var(--totale-azul) !important;
        background-color: var(--totale-azul) !important;
    }}
    {_MAIN} [data-testid="stRadio"] span[data-baseweb="radio"] {{
        color: var(--totale-azul) !important;
    }}
    /* st.toggle/st.checkbox: o trilho ligado usa o laranja da marca. Não há
       data-testid próprio para o toggle no Streamlit 1.65 — o seletor por
       data-baseweb cobre os dois widgets. */
    {_MAIN} [data-baseweb="checkbox"] div[aria-checked="true"] {{
        background-color: var(--totale-laranja) !important;
        border-color: var(--totale-laranja) !important;
    }}
    {_MAIN} [data-testid="stSlider"] div[data-baseweb="slider"] [role="slider"] {{
        background-color: var(--totale-azul) !important;
        border-color: var(--totale-azul) !important;
        box-shadow: 0 1px 4px rgba(1, 40, 105, 0.3);
    }}
    {_MAIN} [data-testid="stSlider"] div[data-baseweb="slider"] div[style*="width"] {{
        background-color: var(--totale-laranja) !important;
    }}
    {_MAIN} [data-testid="stProgress"] div[role="progressbar"] > div {{
        background: linear-gradient(90deg, var(--totale-azul) 0%, var(--totale-laranja) 100%) !important;
    }}
    """


# ====================================================
# 🧱 BLOCO 5: CONTAINERS, NAVEGAÇÃO E CONTEÚDO
# ====================================================
def css_containers() -> str:
    """Densidade, abas, expansores, tabelas, alertas e demais blocos nativos."""
    return f"""
    {_MAIN} .block-container {{
        padding-top: 1.1rem;
        padding-bottom: 3rem;
    }}
    {_MAIN} [data-testid="stHorizontalBlock"] {{
        gap: 0.55rem;
    }}
    {_MAIN} [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] {{
        margin-bottom: 0.15rem;
    }}
    /* Contêineres com borda (st.container(border=True)) recebem a classe
       st-key-<key>; o raio vem do próprio Streamlit e dos blocos .totale-*. */
    {_MAIN} hr {{
        margin: 18px 0;
        border-color: var(--totale-borda);
        opacity: 0.9;
    }}
    /* Títulos e texto */
    {_MAIN} h1:not(.hero-title):not(.th-title):not(.th-title-lg):not(.hero-comparativo__title),
    {_MAIN} h2:not(.hero-title):not(.th-title):not(.th-title-lg):not(.hero-comparativo__title),
    {_MAIN} h3:not(.hero-title):not(.th-title):not(.th-title-lg):not(.hero-comparativo__title) {{
        color: var(--totale-azul);
        letter-spacing: -0.03em;
    }}
    {_MAIN} .hero-corp h1,
    {_MAIN} .totale-hero-1 h1,
    {_MAIN} .totale-hero-2 h1,
    {_MAIN} .hero-migracao h1,
    {_MAIN} .hero-pme h1,
    {_MAIN} .hero-domicilios h1,
    {_MAIN} .hero-card h1,
    {_MAIN} .hero-comparativo h1,
    {_MAIN} .hero-title,
    {_MAIN} .th-title,
    {_MAIN} .th-title-lg,
    {_MAIN} .hero-comparativo__title {{
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-family: var(--font-titulo, 'Oscine', 'Manrope', 'Segoe UI', Arial, sans-serif) !important;
        letter-spacing: -0.03em;
    }}
    {_MAIN} .hero-subtitle,
    {_MAIN} .th-sub,
    {_MAIN} .th-sub-muted,
    {_MAIN} .hero-sub,
    {_MAIN} .hero-comparativo__sub {{
        color: rgba(255, 255, 255, 0.88) !important;
        -webkit-text-fill-color: rgba(255, 255, 255, 0.88) !important;
        font-family: var(--font-texto, 'Inter', 'Segoe UI', sans-serif) !important;
    }}
    {_MAIN} .th-card-value,
    {_MAIN} .th-stat-value,
    {_MAIN} .hero-side-metric strong,
    {_MAIN} .hero-comparativo__metric-value {{
        font-family: var(--font-titulo, 'Oscine', 'Manrope', 'Segoe UI', Arial, sans-serif) !important;
    }}
    {_MAIN} [data-testid="stCaptionContainer"],
    {_MAIN} [data-testid="stCaption"] {{
        color: var(--totale-texto-3);
        font-size: 12px;
        line-height: 1.5;
    }}
    {_MAIN} [data-testid="stMarkdownContainer"] a {{
        color: var(--totale-laranja-escuro);
        font-weight: 600;
        text-decoration: none;
        border-bottom: 1px solid rgba(194, 65, 12, 0.35);
    }}
    {_MAIN} [data-testid="stMarkdownContainer"] a:hover {{
        color: var(--totale-azul);
        border-bottom-color: var(--totale-azul);
    }}
    {_MAIN} [data-testid="stCode"],
    {_MAIN} code {{
        border-radius: var(--totale-raio-sm);
        background: #F6F8FB;
    }}
    /* Abas: trilho discreto e aba ativa em azul com acento laranja */
    {_MAIN} [data-testid="stTabs"] [data-baseweb="tab-list"] {{
        gap: 4px;
        border-bottom: 1px solid var(--totale-borda);
        background: transparent;
    }}
    {_MAIN} [data-testid="stTabs"] button[data-baseweb="tab"] {{
        border-radius: 10px 10px 0 0;
        padding: 8px 16px;
        font-weight: 650;
        color: var(--totale-texto-3) !important;
        background: transparent !important;
        transition: background var(--totale-transicao), color var(--totale-transicao);
    }}
    {_MAIN} [data-testid="stTabs"] button[data-baseweb="tab"]:hover {{
        background: var(--totale-azul-suave) !important;
        color: var(--totale-azul) !important;
    }}
    {_MAIN} [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {{
        color: var(--totale-azul) !important;
        font-weight: 800;
        background: #FFFFFF !important;
        box-shadow: inset 0 2px 0 var(--totale-laranja);
    }}
    {_MAIN} [data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
        background-color: var(--totale-laranja) !important;
        height: 2px !important;
    }}
    {_MAIN} [data-testid="stTabs"] [data-baseweb="tab-panel"] {{
        padding-top: 12px;
    }}
    /* Expansores */
    {_MAIN} [data-testid="stExpander"] details {{
        border: 1px solid var(--totale-borda) !important;
        border-radius: var(--totale-raio-md) !important;
        background: #FFFFFF !important;
        overflow: hidden;
        box-shadow: var(--totale-sombra-sm);
    }}
    {_MAIN} [data-testid="stExpander"] summary {{
        font-weight: 700;
        color: var(--totale-azul);
        padding: 12px 16px;
    }}
    {_MAIN} [data-testid="stExpander"] summary:hover {{
        background: var(--totale-azul-suave);
    }}
    {_MAIN} [data-testid="stExpander"] [data-testid="stMarkdownContainer"] {{
        padding: 4px 16px 12px;
    }}
    /* Popover e dialog */
    {_MAIN} [data-testid="stPopover"] button {{
        border-radius: var(--totale-raio-sm) !important;
    }}
    [data-testid="stDialog"] > div {{
        border-radius: var(--totale-raio-lg) !important;
        box-shadow: var(--totale-sombra-lg) !important;
    }}
    /* Alertas nativos */
    {_MAIN} [data-testid="stAlert"] {{
        border-radius: var(--totale-raio-md) !important;
        border-width: 1px !important;
        box-shadow: var(--totale-sombra-sm);
    }}
    {_MAIN} [data-testid="stAlertContainer"] {{
        font-size: 13px;
        line-height: 1.55;
    }}
    {_MAIN} [data-baseweb="notification"][kind="positive"] {{
        border-left: 4px solid var(--totale-sucesso) !important;
    }}
    {_MAIN} [data-baseweb="notification"][kind="negative"] {{
        border-left: 4px solid var(--totale-alerta) !important;
    }}
    {_MAIN} [data-baseweb="notification"][kind="warning"] {{
        border-left: 4px solid var(--totale-laranja) !important;
    }}
    {_MAIN} [data-baseweb="notification"][kind="info"] {{
        border-left: 4px solid var(--totale-azul) !important;
    }}
    /* Métrica nativa (quando ainda usada em alguma página) */
    {_MAIN} [data-testid="stMetric"] {{
        background: #FFFFFF;
        border: 1px solid var(--totale-borda);
        border-top: 3px solid var(--totale-azul);
        border-radius: var(--totale-raio-md);
        padding: 14px 16px;
        box-shadow: var(--totale-sombra-sm);
        transition: box-shadow var(--totale-transicao), transform var(--totale-transicao);
    }}
    {_MAIN} [data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: var(--totale-sombra-md);
    }}
    {_MAIN} [data-testid="stMetricLabel"] p {{
        color: var(--totale-texto-3) !important;
        font-size: 10.5px !important;
        letter-spacing: 0.07em !important;
        text-transform: uppercase !important;
    }}
    {_MAIN} [data-testid="stMetricValue"] {{
        color: var(--totale-azul) !important;
        letter-spacing: -0.03em !important;
        font-variant-numeric: tabular-nums;
    }}
    {_MAIN} [data-testid="stMetricDelta"] {{
        font-size: 12px !important;
        font-weight: 700 !important;
    }}
    /* Tabelas e dataframes */
    {_MAIN} [data-testid="stDataFrame"],
    {_MAIN} [data-testid="stTable"] {{
        border: 1px solid var(--totale-borda);
        border-radius: var(--totale-raio-md);
        overflow: hidden;
        box-shadow: var(--totale-sombra-sm);
    }}
    {_MAIN} [data-testid="stTable"] table {{
        font-size: 12.5px;
    }}
    {_MAIN} [data-testid="stTable"] thead th {{
        background: var(--totale-azul-suave) !important;
        color: var(--totale-azul) !important;
        font-weight: 750;
        text-transform: uppercase;
        font-size: 10.5px;
        letter-spacing: 0.06em;
    }}
    {_MAIN} [data-testid="stDataFrameResizable"] {{
        border-radius: var(--totale-raio-md);
    }}
    /* Gráficos Plotly: moldura de cartão */
    {_MAIN} [data-testid="stPlotlyChart"] {{
        background: #FFFFFF;
        border: 1px solid var(--totale-borda);
        border-radius: var(--totale-raio-lg);
        padding: 10px 12px 6px;
        box-shadow: var(--totale-sombra-sm);
        transition: box-shadow var(--totale-transicao);
    }}
    {_MAIN} [data-testid="stPlotlyChart"]:hover {{
        box-shadow: var(--totale-sombra-md);
    }}
    {_MAIN} .js-plotly-plot .modebar {{
        opacity: 0.25;
        transition: opacity var(--totale-transicao);
    }}
    {_MAIN} .js-plotly-plot:hover .modebar {{
        opacity: 1;
    }}
    /* Imagens, chat, spinner, skeleton, toast e status */
    {_MAIN} [data-testid="stImage"] img {{
        border-radius: var(--totale-raio-md);
    }}
    {_MAIN} [data-testid="stChatMessage"] {{
        border-radius: var(--totale-raio-md);
        border: 1px solid var(--totale-borda);
        background: #FFFFFF;
    }}
    {_MAIN} [data-testid="stSpinner"] > div > div {{
        border-color: var(--totale-laranja) transparent var(--totale-laranja) transparent !important;
    }}
    {_MAIN} [data-testid="stSkeleton"] {{
        background: linear-gradient(90deg, #F1F5F9 25%, #E6EDF5 50%, #F1F5F9 75%);
        background-size: 200% 100%;
        border-radius: var(--totale-raio-sm);
    }}
    [data-testid="stToast"] {{
        border-radius: var(--totale-raio-md) !important;
        box-shadow: var(--totale-sombra-lg) !important;
    }}
    {_MAIN} [data-testid="stStatusWidget"] {{
        border-radius: var(--totale-raio-md) !important;
    }}
    {_MAIN} [data-testid="stTooltipContent"] {{
        border-radius: var(--totale-raio-sm);
        box-shadow: var(--totale-sombra-md);
    }}
    """


# ====================================================
# ♿ BLOCO 6: ACESSIBILIDADE, DENSIDADE E IMPRESSÃO
# ====================================================
def css_acessibilidade() -> str:
    """Foco visível, seleção de texto, rolagem, impressão e movimento reduzido."""
    return f"""
    {_MAIN} :focus-visible {{
        outline: 3px solid rgba(243, 124, 4, 0.45) !important;
        outline-offset: 2px !important;
        border-radius: 6px;
    }}
    {_MAIN} ::selection {{
        background: rgba(243, 124, 4, 0.22);
        color: var(--totale-azul-escuro);
    }}
    {_MAIN} ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    {_MAIN} ::-webkit-scrollbar-track {{
        background: transparent;
    }}
    {_MAIN} ::-webkit-scrollbar-thumb {{
        background: #CBD5E1;
        border-radius: 99px;
    }}
    {_MAIN} ::-webkit-scrollbar-thumb:hover {{
        background: var(--totale-azul-claro);
    }}
    {_MAIN} [data-testid="stElementContainer"] {{
        scroll-margin-top: 84px;
    }}
    @media (prefers-reduced-motion: reduce) {{
        {_MAIN} * {{
            animation-duration: 0.001ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.001ms !important;
        }}
    }}
    @media (max-width: 900px) {{
        {_MAIN} .block-container {{
            padding-left: 14px;
            padding-right: 14px;
        }}
        {_MAIN} [data-testid="stHorizontalBlock"] {{
            flex-wrap: wrap;
        }}
    }}
    @media print {{
        {_MAIN} [data-testid="stPlotlyChart"],
        {_MAIN} [data-testid="stDataFrame"],
        {_MAIN} [data-testid="stTable"],
        {_MAIN} [data-testid="stExpander"] {{
            break-inside: avoid;
            box-shadow: none !important;
        }}
        {_MAIN} [data-testid="stButton"],
        {_MAIN} [data-testid="stDownloadButton"],
        {_MAIN} [data-testid="stTabs"] [data-baseweb="tab-list"] {{
            display: none !important;
        }}
    }}
    """


def css_utilitarios_estado() -> str:
    """Classes utilitárias de estado usadas por páginas legadas (``.card`` etc.).

    Consolidam o CSS que antes vivia duplicado no ``streamlit_app.py``: qualquer
    página pode marcar um bloco com ``class="card status-ok"`` e herdar o
    acabamento corporativo sem reescrever estilos.
    """
    return f"""
    {_MAIN} .card {{
        background-color: #FFFFFF;
        padding: 22px 24px;
        border-radius: var(--totale-raio-md);
        box-shadow: var(--totale-sombra-sm);
        border: 1px solid var(--totale-borda);
        border-top: 3px solid var(--totale-azul);
        transition: transform var(--totale-transicao), box-shadow var(--totale-transicao);
    }}
    {_MAIN} .card:hover {{
        transform: translateY(-2px);
        box-shadow: var(--totale-sombra-md);
    }}
    {_MAIN} .status-ok {{
        background-color: #F0FDF4;
        border-top: none;
        border-left: 5px solid var(--totale-verde);
    }}
    {_MAIN} .status-warning {{
        background-color: #FFF7ED;
        border-top: none;
        border-left: 5px solid var(--totale-ambar);
    }}
    {_MAIN} .status-error {{
        background-color: #FEF2F2;
        border-top: none;
        border-left: 5px solid var(--totale-vermelho);
    }}
    """


def css_componentes_nativos() -> str:
    """CSS completo dos componentes nativos (variáveis + blocos por família)."""
    return "\n".join(
        (
            css_variaveis_marca(),
            css_botoes(),
            css_entradas(),
            css_selecao(),
            css_containers(),
            css_utilitarios_estado(),
            css_acessibilidade(),
        )
    )


def css_global_completo(*, incluir_kpi: bool = True) -> str:
    """Todo o CSS global do portal em um único texto (nativos + KPIs + layout)."""
    blocos = [css_componentes_nativos()]
    if incluir_kpi:
        blocos.append(css_kpi_avancado())
    try:
        # Import tardio: layout_pagina agrega o próprio CSS ao global.
        from components.layout_pagina import css_layout_pagina

        blocos.append(css_layout_pagina())
    except ImportError:  # pragma: no cover - módulo opcional
        logger.debug("css_layout_pagina indisponível; seguindo sem ele.", exc_info=True)
    return "\n".join(blocos)


# ====================================================
# 💉 BLOCO 7: INJEÇÃO IDEMPOTENTE (UMA VEZ POR SESSÃO)
# ====================================================
def _injetar_no_head(css: str, *, id_no: str = ID_NO_HEAD) -> None:
    """Grava/atualiza um único nó ``<style>`` no ``<head>`` do documento.

    O nó vive fora do fluxo de elementos do Streamlit, portanto **sobrevive aos
    reruns**: nas execuções seguintes não enviamos o payload de CSS de novo
    (menos bytes por rerun e menos trabalho de layout no navegador).
    """
    payload = json.dumps(css).replace("<", "\\u003c")
    _injetar_js(
        f"""
        <script>
        (function () {{
            let doc;
            try {{ doc = __DOC__; }} catch (e) {{ return; }}
            if (!doc || !doc.head) return;
            const id = "{id_no}";
            let no = doc.getElementById(id);
            if (!no) {{
                no = doc.createElement("style");
                no.id = id;
                doc.head.appendChild(no);
            }}
            no.textContent = {payload};
        }})();
        </script>
        """
    )


def injetar_css_global(*, forcar: bool = False, incluir_kpi: bool = True) -> str | None:
    """Injeta o CSS global uma única vez por sessão (idempotente por versão).

    Retorna o CSS injetado na primeira chamada e ``None`` nas seguintes — útil
    para testes e para diagnóstico de tamanho do payload.

    Args:
        forcar: reinjeta mesmo que a versão já esteja aplicada na sessão.
        incluir_kpi: inclui os estilos dos cartões de KPI avançados.
    """
    if st.session_state.get(_CHAVE_SESSAO) == VERSAO_CSS_GLOBAL and not forcar:
        return None
    css = css_global_completo(incluir_kpi=incluir_kpi)
    # 1) nó persistente no head (sobrevive aos reruns);
    _injetar_no_head(css)
    # 2) fallback em fluxo: garante o estilo mesmo se o JS não executar.
    _safe_render_html(f"<style>{css}</style>")
    st.session_state[_CHAVE_SESSAO] = VERSAO_CSS_GLOBAL
    st.session_state["_totale_css_global_bytes"] = len(css)
    logger.debug("CSS global v%s injetado (%d bytes).", VERSAO_CSS_GLOBAL, len(css))
    return css


def tamanho_css_global() -> int:
    """Tamanho (em bytes) do CSS global — usado no diagnóstico de performance."""
    return len(css_global_completo())


__all__ = [
    "ID_NO_HEAD",
    "VERSAO_CSS_GLOBAL",
    "css_acessibilidade",
    "css_botoes",
    "css_componentes_nativos",
    "css_containers",
    "css_entradas",
    "css_global_completo",
    "css_selecao",
    "css_utilitarios_estado",
    "css_variaveis_marca",
    "injetar_css_global",
    "tamanho_css_global",
]
