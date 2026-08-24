import sqlite3
import hashlib
import streamlit as st


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


def criptografar_senha(senha):
    """Garante segurança transformando a senha em um hash SHA-256."""
    return hashlib.sha256(senha.encode()).hexdigest()


def cadastrar_usuario_padrao():
    """Insere um usuário de teste inicial se o banco estiver vazio."""
    conn, cursor = conectar_banco()
    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        senha_hash = criptografar_senha("admin123")
        cursor.execute(
            "INSERT INTO usuarios (username, password) VALUES (?, ?)",
            ("admin", senha_hash),
        )
        conn.commit()
    conn.close()


def verificar_login(usuario, senha):
    """Valida se o usuário e senha existem no banco de dados."""
    conn, cursor = conectar_banco()
    senha_hash = criptografar_senha(senha)
    cursor.execute(
        "SELECT * FROM usuarios WHERE username = ? AND password = ?",
        (usuario, senha_hash),
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None


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

# Garante que o banco e o usuário inicial existam
cadastrar_usuario_padrao()


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

    st.metric(label="Vendas Mensais", value="R$ 45.200", delta="+12%")

    if st.button("Sair / Logout"):
        st.session_state.logado = False
        st.session_state.usuario = None
        st.rerun()


# --- FLUXO DE NAVEGAÇÃO ---
if not st.session_state.logado:
    area_autenticacao()
else:
    pagina_principal()
