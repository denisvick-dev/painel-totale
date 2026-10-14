import hashlib
import hmac
import secrets
import sqlite3

import streamlit as st

from components.componentes import aplicar_estilo
from components.kpi_cards import render_metric
from components.sidebar import render_page_sidebar_theme_selector

aplicar_estilo()
render_page_sidebar_theme_selector()

# --- IDENTIDADE VISUAL DA TELA DE ACESSO ---
_CSS_LOGIN: str = """
<style>
[data-testid="stMain"] .totale-login-hero {
    position: relative; overflow: hidden; isolation: isolate;
    background: linear-gradient(125deg, #011838 0%, #012869 46%, #0A3F96 100%);
    border: 1px solid rgba(243, 124, 4, 0.28);
    border-radius: 18px; padding: 34px 32px; min-height: 320px;
    color: #FFFFFF !important;
    box-shadow: 0 16px 36px rgba(1, 24, 56, 0.18);
}
[data-testid="stMain"] .totale-login-hero::before {
    content: ""; position: absolute; inset: 0; pointer-events: none; z-index: 0;
    background-image:
        linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
    background-size: 28px 28px;
    mask-image: linear-gradient(90deg, transparent 10%, #000 78%);
}
[data-testid="stMain"] .totale-login-hero::after {
    content: ""; position: absolute; right: -80px; top: -90px; width: 280px; height: 280px;
    border-radius: 50%; pointer-events: none; z-index: 0;
    background: radial-gradient(circle, rgba(243,124,4,0.38), transparent 68%);
}
[data-testid="stMain"] .totale-login-hero > div { position: relative; z-index: 2; }
[data-testid="stMain"] .totale-login-hero h1 {
    font-family: var(--font-titulo, 'Oscine', 'Manrope', 'Segoe UI', Arial, sans-serif) !important;
    font-size: clamp(26px, 3vw, 34px) !important; font-weight: 800 !important;
    letter-spacing: -0.03em !important; line-height: 1.08 !important;
    color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important;
    margin: 14px 0 10px !important;
}
[data-testid="stMain"] .totale-login-hero p {
    font-family: var(--font-texto, 'Inter', 'Segoe UI', sans-serif) !important;
    font-size: 14.5px !important; line-height: 1.6 !important;
    color: rgba(255,255,255,0.88) !important; -webkit-text-fill-color: rgba(255,255,255,0.88) !important;
    margin: 0 !important;
}
[data-testid="stMain"] .totale-login-recursos {
    list-style: none; padding: 0; margin: 22px 0 0; display: grid; gap: 11px;
}
[data-testid="stMain"] .totale-login-recursos li {
    display: flex; align-items: flex-start; gap: 10px;
    font-family: var(--font-texto, 'Inter', 'Segoe UI', sans-serif) !important;
    font-size: 13px !important; line-height: 1.45;
    color: rgba(255,255,255,0.92) !important; -webkit-text-fill-color: rgba(255,255,255,0.92) !important;
}
[data-testid="stMain"] .totale-login-recursos .check {
    display: inline-flex; align-items: center; justify-content: center;
    width: 20px; height: 20px; flex-shrink: 0; margin-top: 1px;
    border-radius: 999px; background: rgba(243, 124, 4, 0.22);
    border: 1px solid rgba(243, 124, 4, 0.55);
    color: #FFB870 !important; -webkit-text-fill-color: #FFB870 !important;
    font-size: 11px; font-weight: 900;
}
[data-testid="stMain"] .totale-login-card__topo {
    height: 5px; margin: -6px -8px 16px; border-radius: 999px;
    background: linear-gradient(90deg, #012869 0%, #F37C04 100%);
}
[data-testid="stMain"] .totale-login-card__eyebrow {
    margin: 0 0 6px; font-size: 10px; font-weight: 800; letter-spacing: 0.12em;
    text-transform: uppercase; color: #64748B !important;
}
[data-testid="stMain"] .totale-login-card__titulo {
    font-family: var(--font-titulo, 'Oscine', 'Manrope', 'Segoe UI', Arial, sans-serif) !important;
    font-size: 22px !important; font-weight: 800 !important; letter-spacing: -0.02em !important;
    color: #012869 !important; -webkit-text-fill-color: #012869 !important; margin: 0 0 4px !important;
}
[data-testid="stMain"] .totale-login-card__sub {
    font-family: var(--font-texto, 'Inter', 'Segoe UI', sans-serif) !important;
    font-size: 12.5px !important; color: #64748B !important; margin: 0 0 14px !important;
}
[data-testid="stMain"] .totale-login-rodape {
    margin: 16px 0 0; padding-top: 12px; border-top: 1px solid #E6EDF5;
    font-size: 11px; color: #94A3B8 !important; text-align: center;
}
@media (max-width: 800px) {
    [data-testid="stMain"] .totale-login-hero { padding: 26px 22px; min-height: 0; }
}
</style>
"""

_PBKDF2_ITERATIONS = 600_000


# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
def conectar_banco():
    """Cria a conexão e a tabela de usuários caso ela não exista."""
    conn = sqlite3.connect("usuarios.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn, cursor


def criptografar_senha(senha: str, salt: str | None = None) -> str:
    """Gera hash seguro PBKDF2-HMAC-SHA256 com salt aleatório."""
    salt_efetivo = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode("utf-8"),
        salt_efetivo.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt_efetivo}${dk.hex()}"


def verificar_hash_senha(senha_digitada: str, hash_armazenado: str) -> bool:
    """Valida senha contra PBKDF2-HMAC-SHA256 (com fallback legado constante)."""
    if not senha_digitada or not hash_armazenado:
        return False
    if hash_armazenado.startswith("pbkdf2_sha256$"):
        try:
            _, iter_str, salt, digest_hex = hash_armazenado.split("$", 3)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                senha_digitada.encode("utf-8"),
                salt.encode("utf-8"),
                int(iter_str),
            )
            return hmac.compare_digest(dk.hex(), digest_hex)
        except (ValueError, TypeError):
            return False
    # Compatibilidade para hashes legados de 64 chars hex
    legado = hashlib.pbkdf2_hmac(
        "sha256", senha_digitada.encode("utf-8"), b"totale-legacy", 1
    ).hex()
    return hmac.compare_digest(legado, hash_armazenado)


def verificar_login(usuario, senha):
    """Valida se o usuário e senha existem no banco de dados."""
    conn, cursor = conectar_banco()
    try:
        cursor.execute(
            "SELECT password FROM usuarios WHERE username = ?",
            (usuario,),
        )
        resultado = cursor.fetchone()
    finally:
        conn.close()
    if not resultado:
        return False
    return verificar_hash_senha(senha, str(resultado[0]))


def cadastrar_novo_usuario(usuario, senha):
    """Insere um novo usuário no banco de dados utilizando INSERT INTO."""
    conn, cursor = conectar_banco()
    senha_hash = criptografar_senha(senha)
    try:
        cursor.execute(
            "INSERT INTO usuarios (username, password) VALUES (?, ?)",
            (usuario, senha_hash),
        )
        conn.commit()
        sucesso = True
    except sqlite3.IntegrityError:
        # Erro disparado caso o username já exista (PRIMARY KEY)
        sucesso = False
    finally:
        conn.close()
    return sucesso


# --- CONTROLE DE SESSÃO DO STREAMLIT ---
if "logado" not in st.session_state:
    st.session_state.logado = False
if "usuario" not in st.session_state:
    st.session_state.usuario = None


# A tabela é criada sob demanda na primeira tentativa de login/cadastro.
# --- INTERFACE GRÁFICA ---
def area_autenticacao():
    """Renderiza o hero da marca e as abas de Login e Cadastro de Usuários."""
    st.markdown(_CSS_LOGIN, unsafe_allow_html=True)

    col_hero, col_form = st.columns([1.05, 1], gap="large")

    with col_hero:
        st.markdown(
            """
            <div class="totale-login-hero"><div>
                <div class="hero-badge">⚡ TOTALE TECNOLOGIA</div>
                <h1>Painel TOTALE</h1>
                <p>Plataforma Corporativa de Gestão de Ativos e Indicadores.
                Produção, metas e indicadores operacionais da Totale em um só lugar.</p>
                <ul class="totale-login-recursos">
                    <li><span class="check">✓</span><span>KPIs e dashboards operacionais em tempo real</span></li>
                    <li><span class="check">✓</span><span>Controle de acesso por usuário e perfil</span></li>
                    <li><span class="check">✓</span><span>Dados integrados às planilhas corporativas</span></li>
                </ul>
            </div></div>
            """,
            unsafe_allow_html=True,
        )

    with col_form:
        with st.container(border=True):
            st.markdown(
                """
                <div class="totale-login-card__topo"></div>
                <p class="totale-login-card__eyebrow">Acesso restrito</p>
                <p class="totale-login-card__titulo">Sistema de Acesso</p>
                <p class="totale-login-card__sub">Entre com suas credenciais ou crie uma nova conta.</p>
                """,
                unsafe_allow_html=True,
            )

            # Criação das abas na interface
            aba_login, aba_cadastro = st.tabs(["Acessar Conta", "Criar Nova Conta"])

            # --- ABA DE LOGIN ---
            with aba_login:
                st.subheader("🔑 Login")
                with st.form("formulario_login"):
                    usuario_input = st.text_input(
                        "Usuário", placeholder="Digite seu usuário", key="login_user"
                    )
                    senha_input = st.text_input(
                        "Senha",
                        type="password",
                        placeholder="Digite sua senha",
                        key="login_pass",
                    )
                    botao_entrar = st.form_submit_button("Entrar")

                    if botao_entrar:
                        if not usuario_input or not senha_input:
                            st.warning("Por favor, preencha todos os campos.")
                        elif verificar_login(usuario_input, senha_input):
                            st.session_state.logado = True
                            st.session_state.usuario = usuario_input
                            st.success("Login realizado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos.")

            # --- ABA DE CADASTRO ---
            with aba_cadastro:
                st.subheader("📝 Registrar Novo Usuário")
                with st.form("formulario_cadastro"):
                    novo_usuario = st.text_input(
                        "Escolha um Usuário", placeholder="Ex: joao_silva", key="cad_user"
                    )
                    nova_senha = st.text_input(
                        "Escolha uma Senha",
                        type="password",
                        placeholder="Mínimo 6 caracteres",
                        key="cad_pass",
                    )
                    confirmar_senha = st.text_input(
                        "Confirme a Senha",
                        type="password",
                        placeholder="Repita a senha",
                        key="cad_pass_conf",
                    )
                    botao_cadastrar = st.form_submit_button("Cadastrar")

                    if botao_cadastrar:
                        # Validações básicas de segurança antes de inserir no banco
                        if not novo_usuario or not nova_senha:
                            st.warning("Preencha todos os campos para efetuar o cadastro.")
                        elif len(nova_senha) < 6:
                            st.error("A senha deve ter pelo menos 6 caracteres.")
                        elif nova_senha != confirmar_senha:
                            st.error("As senhas digitadas não coincidem.")
                        else:
                            # Executa a query INSERT INTO através da função
                            if cadastrar_novo_usuario(novo_usuario.strip(), nova_senha):
                                st.success(
                                    f"Usuário '{novo_usuario}' cadastrado com sucesso! Agora você pode mudar para a aba 'Acessar Conta'."
                                )
                            else:
                                st.error(
                                    f"O nome de usuário '{novo_usuario}' já está em uso. Escolha outro."
                                )

            st.markdown(
                '<p class="totale-login-rodape">TOTALE Tecnologia · Ambiente corporativo · '
                "Credenciais protegidas com hash PBKDF2-SHA256</p>",
                unsafe_allow_html=True,
            )


def pagina_principal():
    """Renderiza o conteúdo protegido do seu sistema."""
    st.title(f"📊 Dashboard de {st.session_state.usuario.capitalize()}")
    st.write("Você está autenticado de forma segura!")

    render_metric(
        "Vendas Mensais",
        "R$ 45.200",
        delta="+12%",
        icone="payments",
        ajuda="Faturamento do mês corrente (demonstração).",
    )

    if st.button("Sair / Logout"):
        st.session_state.logado = False
        st.session_state.usuario = None
        st.rerun()


# --- FLUXO DE NAVEGAÇÃO ---
if not st.session_state.logado:
    area_autenticacao()
else:
    pagina_principal()
