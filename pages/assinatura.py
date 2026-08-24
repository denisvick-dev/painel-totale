import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import io
from pathlib import Path
import traceback

# ============ CONFIGURAÇÕES ============

# Cores da marca
COR_AZUL = "#012869"
COR_LARANJA = "#FF4B00"
COR_CINZA = "#555555"
COR_CINZA_CLARO = "#F5F7FA"
COR_CINZA_MEDIO = "#E1E5EB"
COR_BRANCA = "#FFFFFF"
COR_TEXTO = "#2C3E50"

# Dimensão ÚNICA (template = saída)
IMG_WIDTH = 600
IMG_HEIGHT = 123

# Diretório raiz do projeto
ARQUIVO_ATUAL = Path(__file__).resolve()
if ARQUIVO_ATUAL.parent.name == "pages":
    BASE_DIR = ARQUIVO_ATUAL.parent.parent
else:
    BASE_DIR = ARQUIVO_ATUAL.parent

# Diretórios
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
    page_title="Gerador de Assinatura | Totale Tecnologia",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ CSS CORPORATIVO ============

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}

    #MainMenu {{visibility: hidden;}}
    footer    {{visibility: hidden;}}

    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}

    .corporate-header {{
        background: linear-gradient(135deg, {COR_AZUL} 0%, #023a9c 100%);
        padding: 2rem 3rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(1,40,105,0.15);
        color: white;
    }}
    .corporate-header h1 {{
        color: white !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        letter-spacing: -0.5px;
    }}
    .corporate-header p {{
        color: rgba(255,255,255,0.85) !important;
        font-size: 1rem !important;
        margin: 0.5rem 0 0 0 !important;
    }}
    .header-badge {{
        display: inline-block;
        background: {COR_LARANJA};
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 8px;
    }}

    .section-title {{
        color: {COR_AZUL};
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .section-subtitle {{
        color: {COR_CINZA};
        font-size: 0.875rem;
        margin-bottom: 1.5rem;
    }}

    section.main .stTextInput > label {{
        color: {COR_TEXTO} !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
    }}
    section.main .stTextInput > div > div > input {{
        border-radius: 8px !important;
        border: 1.5px solid {COR_CINZA_MEDIO} !important;
        padding: 0.6rem 1rem !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
    }}
    section.main .stTextInput > div > div > input:focus {{
        border-color: {COR_LARANJA} !important;
        box-shadow: 0 0 0 3px rgba(255,75,0,0.1) !important;
    }}
    section.main .stSelectbox > label {{
        color: {COR_TEXTO} !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
    }}

    .stButton > button,
    .stDownloadButton > button {{
        background: linear-gradient(135deg, {COR_LARANJA} 0%, #e56d00 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.75rem 2rem !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.3px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(255,75,0,0.25) !important;
    }}
    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 16px rgba(255,75,0,0.35) !important;
    }}

    .status-item {{
        display: flex;
        align-items: center;
        padding: 0.5rem 0.75rem;
        margin: 0.25rem 0;
        background: white;
        border-radius: 6px;
        border-left: 3px solid;
        font-size: 0.875rem;
        color: {COR_TEXTO};
    }}
    .status-ok    {{ border-left-color: #10B981; }}
    .status-error {{ border-left-color: #EF4444; }}

    .file-metrics {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin: 1rem 0;
    }}
    .metric-box {{
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid {COR_CINZA_MEDIO};
        text-align: center;
    }}
    .metric-label {{
        font-size: 0.75rem;
        color: {COR_CINZA};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
        margin-bottom: 0.25rem;
    }}
    .metric-value {{
        font-size: 1.25rem;
        color: {COR_AZUL};
        font-weight: 700;
    }}

    .stAlert {{
        border-radius: 8px !important;
        border: none !important;
        padding: 1rem 1.25rem !important;
    }}

    .custom-divider {{
        height: 1px;
        background: linear-gradient(90deg, transparent, {COR_CINZA_MEDIO}, transparent);
        margin: 2rem 0;
        border: none;
    }}

    .preview-container {{
        background: {COR_CINZA_CLARO};
        border: 2px dashed {COR_CINZA_MEDIO};
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
    }}

    .info-card {{
        background: white;
        border: 1px solid {COR_CINZA_MEDIO};
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        border-left: 4px solid {COR_AZUL};
    }}
    .info-card-orange {{ border-left-color: {COR_LARANJA}; }}

    .corporate-footer {{
        margin-top: 3rem;
        padding: 1.5rem;
        background: {COR_CINZA_CLARO};
        border-radius: 8px;
        text-align: center;
        border-top: 3px solid {COR_LARANJA};
    }}
    .corporate-footer p {{
        margin: 0;
        color: {COR_CINZA};
        font-size: 0.875rem;
    }}
    .corporate-footer strong {{ color: {COR_AZUL}; }}

    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] a span {{
        color: white !important;
        font-weight: 500 !important;
    }}
    [data-testid="stSidebarNav"] a:hover {{
        background: rgba(255,255,255,0.15) !important;
    }}
    [data-testid="stSidebar"] .element-container h2,
    [data-testid="stSidebar"] .element-container h3,
    [data-testid="stSidebar"] .element-container p,
    [data-testid="stSidebar"] .element-container label {{
        color: white !important;
    }}
    [data-testid="stSidebar"] .streamlit-expanderHeader {{
        background: rgba(255,255,255,0.1) !important;
        color: white !important;
        border-radius: 6px !important;
    }}
    [data-testid="stSidebar"] .stSlider label {{
        color: white !important;
    }}
    </style>
""", unsafe_allow_html=True)

# ============ HEADER ============

st.markdown(f"""
    <div class="corporate-header">
        <div class="header-badge">Ferramenta Interna</div>
        <h1>✉️ Gerador de Assinatura de E-mail</h1>
        <p>Crie sua assinatura profissional padronizada · Totale Tecnologia</p>
    </div>
""", unsafe_allow_html=True)

# ============ FUNÇÕES ============

def hex_to_rgb(hex_color: str) -> tuple:
    """Converte cor hexadecimal para tupla RGB."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def carregar_fonte(tamanho: int, negrito: bool = False):
    """
    Carrega fonte com diagnóstico.
    Retorna (fonte, nome_info).
    """
    caminho = FONTE_BOLD if negrito else FONTE_REGULAR
    tipo = "Bold" if negrito else "Regular"

    if caminho.exists():
        try:
            fonte = ImageFont.truetype(str(caminho), tamanho)
            return fonte, f"Oscine {tipo} ({caminho.name})"
        except (OSError, IOError) as e:
            st.warning(f"⚠️ Erro ao carregar {caminho.name}: {e}")

    fallbacks = [
        ("Arial Bold" if negrito else "Arial",
         "arialbd.ttf" if negrito else "arial.ttf"),
        ("Arial (Win)",
         "C:/Windows/Fonts/arialbd.ttf" if negrito else "C:/Windows/Fonts/arial.ttf"),
        ("DejaVu Sans",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
         if negrito else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("Liberation Sans",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
         if negrito else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        ("FreeSans",
         "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
         if negrito else "/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
        ("Helvetica",
         "/System/Library/Fonts/Helvetica.ttc"),
    ]

    for nome_fonte, caminho_fonte in fallbacks:
        try:
            fonte = ImageFont.truetype(caminho_fonte, tamanho)
            return fonte, f"{nome_fonte} (fallback)"
        except (OSError, IOError):
            continue

    return ImageFont.load_default(), "DEFAULT (bitmap — texto pequeno!)"


def verificar_recursos() -> dict:
    """Status de cada recurso necessário."""
    return {
        "Fonte Regular":   FONTE_REGULAR.exists(),
        "Fonte Bold":      FONTE_BOLD.exists(),
        "Ícone Instagram": ICONE_INSTAGRAM.exists(),
        "Ícone LinkedIn":  ICONE_LINKEDIN.exists(),
        "Template Base":   TEMPLATE_BASE.exists(),
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
    debug: bool = False
) -> tuple:
    """
    Abre o template e desenha os textos.
    Retorna (imagem_rgb, log_debug).
    SEM redimensionamento — o template já é o tamanho final.
    """
    log = []

    # Abrir template
    img = Image.open(TEMPLATE_BASE).convert("RGBA")
    w, h = img.size
    log.append(f"✅ Template aberto: {w}×{h} px")

    # Verificar tamanho esperado
    if w != IMG_WIDTH or h != IMG_HEIGHT:
        log.append(f"⚠️ Tamanho diferente do esperado ({IMG_WIDTH}×{IMG_HEIGHT})")

    # Camada de texto transparente
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    laranja_rgb = hex_to_rgb(COR_LARANJA)
    azul_rgb = hex_to_rgb(COR_AZUL)

    # Carregar fontes
    fonte_nome, info_fn = carregar_fonte(config["tamanho_nome"], negrito=True)
    fonte_cargo, info_fc = carregar_fonte(config["tamanho_cargo"], negrito=False)
    fonte_telefone, info_ft = carregar_fonte(config["tamanho_telefone"], negrito=True)

    log.append(f"🔤 Nome: {info_fn} (tam={config['tamanho_nome']})")
    log.append(f"🔤 Cargo: {info_fc} (tam={config['tamanho_cargo']})")
    log.append(f"🔤 Tel: {info_ft} (tam={config['tamanho_telefone']})")

    # ── NOME ──
    if nome and nome.strip():
        pos = (config["x_nome"], config["y_nome"])
        txt = nome.strip()
        bbox = draw.textbbox(pos, txt, font=fonte_nome)
        log.append(f"📝 NOME: '{txt}' pos={pos} bbox={bbox}")
        draw.text(pos, txt, fill=laranja_rgb + (255,), font=fonte_nome)
        if debug:
            draw.rectangle(bbox, outline=(255, 0, 0, 180), width=2)
    else:
        log.append("⚠️ NOME: vazio")

    # ── CARGO ──
    if cargo and cargo.strip():
        pos = (config["x_cargo"], config["y_cargo"])
        txt = cargo.strip()
        bbox = draw.textbbox(pos, txt, font=fonte_cargo)
        log.append(f"📝 CARGO: '{txt}' pos={pos} bbox={bbox}")
        draw.text(pos, txt, fill=azul_rgb + (255,), font=fonte_cargo)
        if debug:
            draw.rectangle(bbox, outline=(0, 0, 255, 180), width=2)
    else:
        log.append("⚠️ CARGO: vazio")

    # ── TELEFONES ──
    tel1 = telefone1.strip() if telefone1 else ""
    tel2 = telefone2.strip() if telefone2 else ""
    if tel1 and tel2:
        telefones = f"{tel1}  •  {tel2}"
    elif tel1:
        telefones = tel1
    elif tel2:
        telefones = tel2
    else:
        telefones = ""

    if telefones:
        pos = (config["x_telefone"], config["y_telefone"])
        bbox = draw.textbbox(pos, telefones, font=fonte_telefone)
        log.append(f"📝 TEL: '{telefones}' pos={pos} bbox={bbox}")
        draw.text(pos, telefones, fill=azul_rgb + (255,), font=fonte_telefone)
        if debug:
            draw.rectangle(bbox, outline=(0, 128, 0, 180), width=2)
    else:
        log.append("⚠️ TEL: vazio")

    # Compor e converter para RGB
    resultado = Image.alpha_composite(img, txt_layer).convert("RGB")
    log.append(f"✅ Imagem final: {resultado.size[0]}×{resultado.size[1]} px")

    return resultado, log


def imagem_para_buffer(img: Image.Image, formato: str, qualidade: int = 90) -> io.BytesIO:
    """Salva imagem em buffer de memória."""
    buf = io.BytesIO()
    if formato == "PNG":
        img.save(buf, format="PNG", optimize=True)
    else:
        img.convert("RGB").save(buf, format="JPEG", quality=qualidade, optimize=True)
    buf.seek(0)
    return buf


# ============ SIDEBAR ============

with st.sidebar:
    st.markdown("## ⚙️ Painel de Controle")

    # Status
    st.markdown("### 📦 Status do Sistema")
    status = verificar_recursos()
    todos_ok = all(status.values())

    for recurso, ok in status.items():
        classe = "status-ok" if ok else "status-error"
        icone = "✓" if ok else "✗"
        st.markdown(
            f'<div class="status-item {classe}"><strong>{icone}</strong>&nbsp;&nbsp;{recurso}</div>',
            unsafe_allow_html=True
        )

    if todos_ok:
        st.success("Todos os recursos carregados!", icon="✅")
    else:
        st.warning("Alguns recursos estão faltando.", icon="⚠️")

    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    # Info do template
    st.markdown(f"""
        <div style="background:white;padding:1rem;border-radius:8px;border-left:3px solid {COR_AZUL};">
            <div style="font-size:0.7rem;color:{COR_CINZA};text-transform:uppercase;font-weight:600;">
                Tamanho da Assinatura
            </div>
            <div style="font-size:1.1rem;color:{COR_AZUL};font-weight:700;margin-top:4px;">
                {IMG_WIDTH} × {IMG_HEIGHT} px
            </div>
            <div style="font-size:0.7rem;color:{COR_CINZA};margin-top:4px;">
                Template = Saída final (sem redimensionamento)
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    # Posicionamento
    st.markdown("### 🎯 Ajustes de Posicionamento")
    st.caption(f"Coordenadas em pixels ({IMG_WIDTH}×{IMG_HEIGHT})")

    with st.expander("👤 Nome", expanded=False):
        x_nome = st.slider("X (horizontal)", 0, IMG_WIDTH, 55, key="xn")
        y_nome = st.slider("Y (vertical)", 0, IMG_HEIGHT, 70, key="yn")
        tamanho_nome = st.slider("Tamanho da fonte", 6, 40, 18, key="tn")

    with st.expander("💼 Cargo", expanded=False):
        x_cargo = st.slider("X (horizontal)", 0, IMG_WIDTH, 55, key="xc")
        y_cargo = st.slider("Y (vertical)", 0, IMG_HEIGHT, 91, key="yc")
        tamanho_cargo = st.slider("Tamanho da fonte", 6, 30, 13, key="tc")

    with st.expander("📱 Telefones", expanded=False):
        x_telefone = st.slider("X (horizontal)", 0, IMG_WIDTH, 270, key="xt")
        y_telefone = st.slider("Y (vertical)", 0, IMG_HEIGHT, 90, key="yt")
        tamanho_telefone = st.slider("Tamanho da fonte", 6, 30, 15, key="tt")

    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    # Modo debug
    st.markdown("### 🔍 Diagnóstico")
    modo_debug = st.checkbox(
        "Ativar modo debug",
        value=False,
        help="Mostra retângulos ao redor do texto e log detalhado"
    )

    with st.expander("🔧 Caminhos do Sistema"):
        st.code(f"Base    : {BASE_DIR}", language="text")
        st.code(f"Fontes  : {FONTS_DIR}", language="text")
        st.code(f"Assets  : {ASSETS_DIR}", language="text")
        st.code(f"Template: {TEMPLATE_BASE}", language="text")

        if FONTS_DIR.exists():
            fontes = list(FONTS_DIR.glob("*.*"))
            if fontes:
                st.caption("**Fontes encontradas:**")
                for f in fontes:
                    st.write(f"  • `{f.name}` ({f.stat().st_size/1024:.1f} KB)")
            else:
                st.warning("Pasta fonts/ vazia!")
        else:
            st.error("Pasta fonts/ não existe!")


# ============ VERIFICAÇÕES ============

if not TEMPLATE_BASE.exists():
    st.error("❌ **Template não encontrado!**")
    st.warning(f"Caminho esperado: `{TEMPLATE_BASE}`")

    if IMAGES_DIR.exists():
        arquivos = list(IMAGES_DIR.iterdir())
        if arquivos:
            st.info("📁 Arquivos em `images/`:")
            for arq in arquivos:
                st.write(f"  • `{arq.name}`")
        else:
            st.info("Pasta `images/` está vazia.")
    else:
        st.info("Pasta `assets/images/` não encontrada.")
    st.stop()

# Verificar dimensões reais do template
try:
    _test = Image.open(TEMPLATE_BASE)
    _tw, _th = _test.size
    if _tw != IMG_WIDTH or _th != IMG_HEIGHT:
        st.error(
            f"❌ **Template com tamanho errado!** "
            f"Encontrado: **{_tw}×{_th} px** — Esperado: **{IMG_WIDTH}×{IMG_HEIGHT} px**"
        )
        st.info(
            f"Redimensione o template para exatamente **{IMG_WIDTH}×{IMG_HEIGHT} px** "
            f"ou ajuste as constantes `IMG_WIDTH` e `IMG_HEIGHT` no código."
        )
        st.warning("As posições padrão dos textos foram calibradas para 600×123 px.")
except Exception as e:
    st.error(f"❌ Erro ao abrir template: {e}")
    st.stop()

if not FONTE_REGULAR.exists() or not FONTE_BOLD.exists():
    st.warning("⚠️ Fontes **Oscine** não encontradas. Será usada fonte alternativa.")


# ============ LAYOUT PRINCIPAL ============

col1, col2 = st.columns([1, 2], gap="large")

# ════════════════════════════════════════
# COLUNA ESQUERDA — Formulário
# ════════════════════════════════════════
with col1:
    st.markdown('<div class="section-title">📝 Dados Pessoais</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-subtitle">Preencha as informações da assinatura</p>',
        unsafe_allow_html=True
    )

    nome = st.text_input(
        "Nome Completo *",
        value="Denis Vick",
        placeholder="Digite seu nome completo",
        help="Exibido em laranja"
    )

    cargo = st.text_input(
        "Cargo / Função *",
        value="Analista de COP | Leste & ABCDM",
        placeholder="Ex: Analista, Gerente, Coordenador",
        help="Exibido em azul, abaixo do nome"
    )

    st.markdown("**📞 Contatos Telefônicos**")

    col_tel1, col_tel2 = st.columns(2)

    with col_tel1:
        telefone1_raw = st.text_input(
            "Telefone Principal",
            value="11993045101",
            placeholder="00900000000",
            help="Apenas números — formatação automática",
            max_chars=11
        )

    with col_tel2:
        telefone2_raw = st.text_input(
            "Telefone Secundário",
            value="",
            placeholder="Opcional",
            help="Deixe em branco se não quiser",
            max_chars=11
        )

    telefone1 = formatar_telefone(telefone1_raw)
    telefone2 = formatar_telefone(telefone2_raw)

    if telefone1_raw:
        st.caption(f"📱 Formatado: **{telefone1}**")
    if telefone2_raw:
        st.caption(f"📱 Formatado: **{telefone2}**")

    campos_ok = bool(nome.strip() and cargo.strip())
    if not campos_ok:
        st.warning("⚠️ Preencha Nome e Cargo para gerar a assinatura.")

    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

    st.markdown(f"""
        <div class="info-card info-card-orange">
            <strong style="color:{COR_LARANJA};">💡 Dicas</strong>
            <ul style="margin:0.5rem 0 0 0;padding-left:1.2rem;font-size:0.85rem;color:{COR_TEXTO};">
                <li>Digite apenas números no telefone</li>
                <li>Use os sliders na sidebar para ajustar posições</li>
                <li>Ative o <b>modo debug</b> se o texto não aparecer</li>
                <li>O template já está em {IMG_WIDTH}×{IMG_HEIGHT} px</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════
# COLUNA DIREITA — Preview + Download
# ════════════════════════════════════════
with col2:
    st.markdown('<div class="section-title">👁️ Pré-visualização</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-subtitle">Visualização em tempo real da assinatura</p>',
        unsafe_allow_html=True
    )

    try:
        config = {
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
            nome, cargo, telefone1, telefone2, config,
            debug=modo_debug
        )

        # Preview
        st.markdown('<div class="preview-container">', unsafe_allow_html=True)
        st.image(img_final, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.caption(f"📐 Tamanho: **{img_final.width} × {img_final.height} px** (pronto para uso)")

        # Log de debug
        if modo_debug:
            st.markdown("### 🔍 Log de Diagnóstico")
            for linha in debug_log:
                if linha.startswith("✅"):
                    st.success(linha, icon="✅")
                elif linha.startswith("⚠️"):
                    st.warning(linha, icon="⚠️")
                elif linha.startswith("❌"):
                    st.error(linha, icon="❌")
                else:
                    st.text(linha)

        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

        # ══════════════════════════════════
        # DOWNLOAD
        # ══════════════════════════════════
        st.markdown('<div class="section-title">📥 Exportar Assinatura</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-subtitle">Escolha o formato e faça o download</p>',
            unsafe_allow_html=True
        )

        formato_opcao = st.selectbox(
            "🎨 Formato do Arquivo",
            options=[
                "PNG (alta qualidade)",
                "JPG (arquivo menor)",
            ],
            index=0,
            help="PNG preserva nitidez. JPG gera arquivo menor."
        )

        formato = "PNG" if formato_opcao.startswith("PNG") else "JPG"
        extensao = formato.lower()
        mime_type = "image/png" if formato == "PNG" else "image/jpeg"

        # Buffer direto (sem redimensionamento)
        buffer = imagem_para_buffer(img_final, formato)
        tamanho_kb = len(buffer.getvalue()) / 1024

        # Métricas
        st.markdown(f"""
            <div class="file-metrics">
                <div class="metric-box">
                    <div class="metric-label">Dimensões</div>
                    <div class="metric-value">{img_final.width}×{img_final.height}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Tamanho</div>
                    <div class="metric-value">{tamanho_kb:.1f} KB</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Formato</div>
                    <div class="metric-value">{extensao.upper()}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Download
        nome_slug = nome.strip().replace(" ", "_").lower() if nome.strip() else "padrao"
        nome_arquivo = f"assinatura_totale_{nome_slug}.{extensao}"

        st.download_button(
            label=f"⬇️  Baixar Assinatura · {img_final.width}×{img_final.height} px · {extensao.upper()}",
            data=buffer,
            file_name=nome_arquivo,
            mime=mime_type,
            use_container_width=True,
            type="primary",
            disabled=not campos_ok
        )

        # Alerta de tamanho
        if tamanho_kb > 150:
            st.warning(f"⚠️ Arquivo grande ({tamanho_kb:.1f} KB). Recomendado: < 150 KB.")
        elif tamanho_kb > 100:
            st.info(f"ℹ️ {tamanho_kb:.1f} KB — considere JPG para reduzir.")
        else:
            st.success(f"✅ Tamanho otimizado ({tamanho_kb:.1f} KB) — perfeito para e-mail!")

        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)

        # ══════════════════════════════════
        # GUIA DE INSTALAÇÃO
        # ══════════════════════════════════
        st.markdown('<div class="section-title">📚 Guia de Instalação</div>', unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs([
            "📧 Gmail", "🖥️ Outlook Desktop", "🌐 Outlook Web", "📱 Mobile"
        ])

        with tab1:
            st.markdown("""
            #### Gmail — Passo a passo

            1. Abra o **Gmail** → ⚙️ → **"Ver todas as configurações"**
            2. Aba **"Geral"** → role até **"Assinatura"**
            3. **"Criar nova"** → nomeie (ex: *Totale*)
            4. No editor, ícone 🖼️ → upload da imagem
            5. Defina para **novas mensagens** e **respostas**
            6. **"Salvar alterações"** ✅
            """)

        with tab2:
            st.markdown("""
            #### Outlook Desktop — Passo a passo

            1. **Arquivo** → **Opções** → **E-mail**
            2. **"Assinaturas..."** → **"Novo"**
            3. No editor, ícone 🖼️ → selecione o arquivo
            4. Defina como padrão
            5. **OK** ✅
            """)

        with tab3:
            st.markdown("""
            #### Outlook Web (Office 365) — Passo a passo

            1. ⚙️ → **"Ver todas as configurações"**
            2. **E-mail → Compor e responder**
            3. **"Nova assinatura"** → insira imagem
            4. Marque inclusão automática
            5. **"Salvar"** ✅
            """)

        with tab4:
            st.markdown("""
            #### Mobile

            **Gmail:** ☰ → Configurações → conta → "Assinatura para dispositivo móvel"

            **Outlook:** ☰ → ⚙️ → conta → "Assinatura"

            > 💡 Para melhor compatibilidade, hospede a imagem e insira via URL.
            """)

    except FileNotFoundError as e:
        st.error(f"❌ Arquivo não encontrado: {e}")
    except Exception as e:
        st.error(f"❌ Erro inesperado: {e}")
        with st.expander("🔍 Detalhes do erro"):
            st.code(traceback.format_exc(), language="python")


# ============ FOOTER ============

st.markdown(f"""
    <div class="corporate-footer">
        <p><strong>Totale Tecnologia</strong> · Conexão em Movimento</p>
        <p style="font-size:0.75rem;margin-top:0.5rem;">
            Ferramenta de uso interno · Versão 2.1 · © 2026
        </p>
    </div>
""", unsafe_allow_html=True)