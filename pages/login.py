import hashlib
import hmac
import secrets
import sqlite3

import streamlit as st

from components.kpi_cards import render_metric
from components.sidebar import render_page_sidebar_theme_selector

render_page_sidebar_theme_selector()

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
    """Renderiza as abas de Login e Cadastro de Usuários."""
    st.title("🔐 Sistema de Acesso")

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
