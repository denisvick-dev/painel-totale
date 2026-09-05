# gerador_assinatura.py
import io
import traceback
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ==========================================================
# IMPORTAÇÃO DE COMPONENTES CORPORATIVOS
# ==========================================================
from components.componentes import (
    COR_PRIMARIA,
    COR_SECUNDARIA,
    COR_TEXTO,
    COR_TEXTO_3,
    FONTE_TEXTO,
    FONTE_TITULO,
    aplicar_estilo as aplicar_estilo_corp,
    render_hero_totale_2,
    render_insight,
    render_kpi_sm,
    render_section_header,
    render_sidebar_brand,
)

# ============ CONFIGURAÇÕES DE IMAGEM ============

# Cores específicas para a assinatura gerada (preservando o manual da marca no PNG)
COR_ASSINATURA_AZUL = "#012869"
COR_ASSINATURA_LARANJA = "#FF4B00"

# Dimensão ÚNICA (template = saída)
IMG_WIDTH = 600
IMG_HEIGHT = 123

# Diretórios
ARQUIVO_ATUAL = Path(__file__).resolve()
if ARQUIVO_ATUAL.parent.name == "pages":
    BASE_DIR = ARQUIVO_ATUAL.parent.parent
else:
    BASE_DIR = ARQUIVO_ATUAL.parent

FONTS_DIR = BASE_DIR / "fonts"
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
IMAGES_DIR = ASSETS_DIR / "images"

# Arquivos
FONTE_REGULAR = FONTS_DIR / "Oscine-Regular.ttf"
FONTE_BOLD = FONTS_DIR / "Oscine-Bold.ttf"
ICONE_INSTAGRAM = ICONS_DIR / "instagram.png"
ICONE_LINKEDIN = ICONS_DIR / "linkedin.png"
TEMPLATE_BASE = IMAGES_DIR / "ass_email_totale.png"

# ============ STREAMLIT CONFIG ============

st.set_page_config(
    page_title="Gerador de Assinatura | TOTALE",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============ CSS ESPECÍFICO ============


def aplicar_estilo_pagina():
    css = (
        f"<style>"
        f".preview-container {{"
        f"    background: #F8FAFC;"
        f"    border: 2px dashed {COR_TEXTO_3};"
        f"    border-radius: 12px;"
        f"    padding: 1.5rem;"
        f"    text-align: center;"
        f"}}"
        f".status-item {{"
        f"    display: flex; align-items: center;"
        f"    padding: 0.5rem 0.75rem; margin: 0.25rem 0;"
        f"    background: white; border-radius: 6px;"
        f"    border-left: 3px solid; font-size: 0.875rem;"
        f"    color: {COR_TEXTO}; font-family: {FONTE_TEXTO};"
        f"    box-shadow: 0 1px 3px rgba(0,0,0,0.05);"
        f"}}"
        f".status-ok {{ border-left-color: #10B981; }}"
        f".status-error {{ border-left-color: #EF4444; }}"
        f".corporate-footer {{"
        f"    margin-top: 3rem; padding: 1.5rem;"
        f"    background: #F8FAFC; border-radius: 8px;"
        f"    text-align: center; border-top: 3px solid {COR_SECUNDARIA};"
        f"    font-family: {FONTE_TEXTO};"
        f"}}"
        f"</style>"
    )
    st.markdown(css, unsafe_allow_html=True)


# ============ FUNÇÕES DE GERAÇÃO ============


def hex_to_rgb(hex_color: str) -> tuple:
    """Converte cor hexadecimal para tupla RGB."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def carregar_fonte(tamanho: int, negrito: bool = False):
    """Carrega fonte com diagnóstico."""
    caminho = FONTE_BOLD if negrito else FONTE_REGULAR
    tipo = "Bold" if negrito else "Regular"

    if caminho.exists():
        try:
            fonte = ImageFont.truetype(str(caminho), tamanho)
            return fonte, f"Oscine {tipo} ({caminho.name})"
        except (OSError, IOError) as e:
            st.warning(f"⚠️ Erro ao carregar {caminho.name}: {e}")

    fallbacks = [
        (
            "Arial Bold" if negrito else "Arial",
            "arialbd.ttf" if negrito else "arial.ttf",
        ),
        (
            "Arial (Win)",
            "C:/Windows/Fonts/arialbd.ttf" if negrito else "C:/Windows/Fonts/arial.ttf",
        ),
        (
            "DejaVu Sans",
            (
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if negrito
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ),
        ),
        (
            "Liberation Sans",
            (
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
                if negrito
                else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            ),
        ),
        (
            "FreeSans",
            (
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
                if negrito
                else "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
            ),
        ),
        ("Helvetica", "/System/Library/Fonts/Helvetica.ttc"),
    ]

    for nome_fonte, caminho_fonte in fallbacks:
        try:
            fonte = ImageFont.truetype(caminho_fonte, tamanho)
            return fonte, f"{nome_fonte} (fallback)"
        except (OSError, IOError):
            continue

    return ImageFont.load_default(), "DEFAULT (bitmap)"


def verificar_recursos() -> dict:
    """Verifica arquivos essenciais."""
    return {
        "Fonte Regular": FONTE_REGULAR.exists(),
        "Fonte Bold": FONTE_BOLD.exists(),
        "Template Base": TEMPLATE_BASE.exists(),
    }


def formatar_telefone(tel: str) -> str:
    """Formata telefone automaticamente."""
    digitos = "".join(filter(str.isdigit, tel))
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return tel


def gerar_assinatura(
    nome: str,
    cargo: str,
    telefone1: str,
    telefone2: str,
    config: dict,
    debug: bool = False,
) -> tuple:
    """Renderiza a assinatura e retorna a imagem em PIL."""
    log = []

    img = Image.open(TEMPLATE_BASE).convert("RGBA")
    w, h = img.size
    log.append(f"✅ Template aberto: {w}×{h} px")

    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    laranja_rgb = hex_to_rgb(COR_ASSINATURA_LARANJA)
    azul_rgb = hex_to_rgb(COR_ASSINATURA_AZUL)

    fonte_nome, info_fn = carregar_fonte(config["tamanho_nome"], negrito=True)
    fonte_cargo, info_fc = carregar_fonte(config["tamanho_cargo"], negrito=False)
    fonte_telefone, info_ft = carregar_fonte(config["tamanho_telefone"], negrito=True)

    log.append(f"🔤 Nome: {info_fn}")
    log.append(f"🔤 Cargo: {info_fc}")
    log.append(f"🔤 Tel: {info_ft}")

    # Nome
    if nome.strip():
        pos = (config["x_nome"], config["y_nome"])
        txt = nome.strip()
        bbox = draw.textbbox(pos, txt, font=fonte_nome)
        draw.text(pos, txt, fill=laranja_rgb + (255,), font=fonte_nome)
        if debug:
            draw.rectangle(bbox, outline=(255, 0, 0, 180), width=2)

    # Cargo
    if cargo.strip():
        pos = (config["x_cargo"], config["y_cargo"])
        txt = cargo.strip()
        bbox = draw.textbbox(pos, txt, font=fonte_cargo)
        draw.text(pos, txt, fill=azul_rgb + (255,), font=fonte_cargo)
        if debug:
            draw.rectangle(bbox, outline=(0, 0, 255, 180), width=2)

    # Telefones
    tel1, tel2 = telefone1.strip(), telefone2.strip()
    telefones = f"{tel1}  •  {tel2}" if (tel1 and tel2) else tel1 or tel2

    if telefones:
        pos = (config["x_telefone"], config["y_telefone"])
        bbox = draw.textbbox(pos, telefones, font=fonte_telefone)
        draw.text(pos, telefones, fill=azul_rgb + (255,), font=fonte_telefone)
        if debug:
            draw.rectangle(bbox, outline=(0, 128, 0, 180), width=2)

    resultado = Image.alpha_composite(img, txt_layer).convert("RGB")
    return resultado, log


def imagem_para_buffer(
    img: Image.Image, formato: str, qualidade: int = 90
) -> io.BytesIO:
    buf = io.BytesIO()
    if formato == "PNG":
        img.save(buf, format="PNG", optimize=True)
    else:
        img.save(buf, format="JPEG", quality=qualidade, optimize=True)
    buf.seek(0)
    return buf


# ============ INIT E VERIFICAÇÕES ============

aplicar_estilo_corp()
aplicar_estilo_pagina()

if not TEMPLATE_BASE.exists():
    render_hero_totale_2(
        "Erro Crítico", "Template da assinatura não encontrado", "FALHA", "vermelho"
    )
    render_insight(
        f"O arquivo base não foi localizado em: `{TEMPLATE_BASE}`", "critico"
    )
    st.stop()

# ============ HEADER ============

render_hero_totale_2(
    titulo="✉️ Gerador de Assinatura",
    subtitulo="Crie e padronize sua assinatura profissional de e-mail corporativo.",
    badge_texto="Ferramenta Interna",
    badge_tipo="laranja",
)

# ============ SIDEBAR ============

with st.sidebar:
    render_sidebar_brand()

    st.markdown(
        f"<h3 style='font-family:{FONTE_TITULO}; font-size:16px; margin-top:20px;'>📦 Status do Sistema</h3>",
        unsafe_allow_html=True,
    )

    status = verificar_recursos()
    todos_ok = all(status.values())

    for recurso, ok in status.items():
        classe = "status-ok" if ok else "status-error"
        icone = "✓" if ok else "✗"
        st.markdown(
            f'<div class="status-item {classe}"><strong>{icone}</strong>&nbsp;&nbsp;{recurso}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown(
        f"<h3 style='font-family:{FONTE_TITULO}; font-size:16px;'>🎯 Posições e Tamanhos</h3>",
        unsafe_allow_html=True,
    )

    with st.expander("👤 Nome", expanded=False):
        x_nome = st.slider("X (horizontal)", 0, IMG_WIDTH, 55, key="xn")
        y_nome = st.slider("Y (vertical)", 0, IMG_HEIGHT, 63, key="yn")
        tamanho_nome = st.slider("Tamanho da fonte", 6, 40, 19, key="tn")

    with st.expander("💼 Cargo", expanded=False):
        x_cargo = st.slider("X (horizontal)", 0, IMG_WIDTH, 56, key="xc")
        y_cargo = st.slider("Y (vertical)", 0, IMG_HEIGHT, 87, key="yc")
        tamanho_cargo = st.slider("Tamanho da fonte", 6, 30, 14, key="tc")

    with st.expander("📱 Telefones", expanded=False):
        x_telefone = st.slider("X (horizontal)", 0, IMG_WIDTH, 292, key="xt")
        y_telefone = st.slider("Y (vertical)", 0, IMG_HEIGHT, 82, key="yt")
        tamanho_telefone = st.slider("Tamanho da fonte", 6, 30, 15, key="tt")

    st.divider()
    modo_debug = st.checkbox("🔍 Ativar modo debug", value=False)


# ============ LAYOUT PRINCIPAL ============

col1, col2 = st.columns([1, 2], gap="large")

with col1:
    render_section_header(
        titulo="Dados Pessoais",
        subtitulo="Preencha as informações que constarão na assinatura.",
        icone="📝",
        badge="Entrada",
        badge_tipo="azul",
    )

    nome = st.text_input(
        "Nome Completo *", value="Denis Vick", placeholder="Ex: Denis Vick"
    )
    cargo = st.text_input(
        "Cargo / Função *",
        value="Analista de COP | Leste & ABCDM",
        placeholder="Ex: Analista de COP",
    )

    st.markdown(
        f"<div style='font-family:{FONTE_TITULO}; font-size:14px; margin: 15px 0 5px;'>📞 Contatos Telefônicos</div>",
        unsafe_allow_html=True,
    )

    col_tel1, col_tel2 = st.columns(2)
    with col_tel1:
        telefone1_raw = st.text_input(
            "Principal", value="11993045101", placeholder="Apenas números", max_chars=11
        )
    with col_tel2:
        telefone2_raw = st.text_input(
            "Secundário (Opcional)", value="", placeholder="Opcional", max_chars=11
        )

    telefone1 = formatar_telefone(telefone1_raw)
    telefone2 = formatar_telefone(telefone2_raw)

    campos_ok = bool(nome.strip() and cargo.strip())

    if not campos_ok:
        render_insight("Preencha o Nome e o Cargo para liberar o download.", "alerta")

    # Substitui a caixa de dicas manual pelo componente Insight
    render_insight(
        "**Dicas:** O telefone formata sozinho. Use o painel lateral para ajustar pixels se o texto ficar desalinhado.",
        "info",
    )


with col2:
    render_section_header(
        titulo="Pré-visualização",
        subtitulo="A imagem gerada em tempo real e em seu tamanho final exato.",
        icone="👁️",
        badge="Preview",
        badge_tipo="laranja",
    )

    try:
        config_pos = {
            "x_nome": x_nome,
            "y_nome": y_nome,
            "tamanho_nome": tamanho_nome,
            "x_cargo": x_cargo,
            "y_cargo": y_cargo,
            "tamanho_cargo": tamanho_cargo,
            "x_telefone": x_telefone,
            "y_telefone": y_telefone,
            "tamanho_telefone": tamanho_telefone,
        }

        img_final, debug_log = gerar_assinatura(
            nome, cargo, telefone1, telefone2, config_pos, debug=modo_debug
        )

        st.markdown('<div class="preview-container">', unsafe_allow_html=True)
        st.image(img_final, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if modo_debug:
            st.markdown("### 🔍 Log")
            for linha in debug_log:
                st.code(linha, language="text")

        # ── Exportar e Download ──
        render_section_header(
            titulo="Exportação",
            subtitulo="Analise o tamanho do arquivo e baixe sua assinatura.",
            icone="📥",
            badge="Download",
            badge_tipo="verde",
        )

        formato_opcao = st.selectbox(
            "Formato do Arquivo",
            options=["PNG (alta qualidade)", "JPG (arquivo menor)"],
        )
        formato = "PNG" if formato_opcao.startswith("PNG") else "JPG"
        extensao = formato.lower()

        buffer = imagem_para_buffer(img_final, formato)
        tamanho_kb = len(buffer.getvalue()) / 1024

        # Substitui os blocos HTML antigos pelos novos KPIs compactos
        k1, k2, k3 = st.columns(3)
        render_kpi_sm(
            k1,
            "Dimensões",
            f"{img_final.width}×{img_final.height}",
            "pixels",
            "azul",
            "📐",
        )
        render_kpi_sm(
            k2, "Tamanho", f"{tamanho_kb:.1f} KB", "peso do arquivo", "cinza", "💾"
        )
        render_kpi_sm(
            k3, "Formato", extensao.upper(), "extensão final", "laranja", "🖼️"
        )

        st.markdown("<br>", unsafe_allow_html=True)

        nome_slug = nome.strip().replace(" ", "_").lower() if nome.strip() else "padrao"

        st.download_button(
            label=f"⬇️ Baixar Assinatura ({extensao.upper()})",
            data=buffer,
            file_name=f"assinatura_totale_{nome_slug}.{extensao}",
            mime=f"image/{extensao}",
            use_container_width=True,
            type="primary",
            disabled=not campos_ok,
        )

    except Exception as e:
        render_insight(f"Erro inesperado: {e}", "critico")
        st.code(traceback.format_exc(), language="python")

# ============ GUIA DE INSTALAÇÃO ============

st.markdown("<br>", unsafe_allow_html=True)
render_section_header(
    "Guia de Instalação",
    "Como aplicar a imagem nos principais clientes de e-mail.",
    "📚",
    badge="Dúvidas",
    badge_tipo="cinza",
)

tab1, tab2, tab3 = st.tabs(["📧 Gmail", "🖥️ Outlook Desktop", "🌐 Outlook Web"])

with tab1:
    st.markdown("""
    1. Abra o **Gmail** → ⚙️ Engrenagem → **Ver todas as configurações**
    2. Aba **Geral** → role até a seção **Assinatura**
    3. Clique em **Criar nova** e dê um nome (ex: Totale)
    4. No editor de texto, clique no ícone de imagem 🖼️ e faça o upload do arquivo baixado
    5. Defina a assinatura como padrão para *novas mensagens* e *respostas*
    6. Vá até o final da página e clique em **Salvar alterações**
    """)

with tab2:
    st.markdown("""
    1. No Outlook, clique em **Arquivo** → **Opções** → **E-mail**
    2. Clique no botão **Assinaturas...**
    3. Clique em **Novo** e digite um nome
    4. Na caixa de edição, clique no ícone de imagem 🖼️ e selecione o arquivo
    5. Escolha a assinatura nas caixas *Novas mensagens* e *Respostas* no canto superior direito
    6. Clique em **OK**
    """)

with tab3:
    st.markdown("""
    1. Clique na ⚙️ Engrenagem → **Ver todas as configurações do Outlook**
    2. Acesse **E-mail** → **Compor e responder**
    3. Clique em **Nova assinatura** e dê um nome
    4. Cole a imagem ou use o ícone de inserir imagem 🖼️
    5. Marque as opções para incluir a assinatura automaticamente
    6. Clique em **Salvar**
    """)

# ============ FOOTER ============

st.markdown(
    f'<div class="corporate-footer">'
    f'<p><strong style="color:{COR_PRIMARIA};">Totale Tecnologia</strong> · Conexão em Movimento</p>'
    f'<p style="font-size:0.75rem;margin-top:0.5rem;color:{COR_TEXTO_3};">Ferramenta de uso interno · Versão 2.1 · © 2026</p>'
    f"</div>",
    unsafe_allow_html=True,
)