import streamlit as st
import json
import toml
from pathlib import Path

# ============ CONFIGURAÇÕES ============

COR_AZUL = "#012869"
COR_LARANJA = "#F37C04"

# Diretório raiz do projeto
ARQUIVO_ATUAL = Path(__file__).resolve()
if ARQUIVO_ATUAL.parent.name == "pages":
    BASE_DIR = ARQUIVO_ATUAL.parent.parent
else:
    BASE_DIR = ARQUIVO_ATUAL.parent

STREAMLIT_DIR = BASE_DIR / ".streamlit"
SECRETS_PATH = STREAMLIT_DIR / "secrets.toml"

st.set_page_config(
    page_title="Conversor de Credenciais | Totale",
    page_icon="🔐",
    layout="centered"
)

st.markdown(f"""
    <style>
    .main-title {{
        color: {COR_AZUL};
        text-align: center;
        font-weight: 700;
    }}
    .subtitle {{
        color: {COR_LARANJA};
        text-align: center;
        margin-bottom: 2rem;
    }}
    .stButton > button {{
        background: linear-gradient(135deg, {COR_LARANJA}, #e56d00) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">🔐 Conversor de Credenciais Google</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">JSON → secrets.toml</p>', unsafe_allow_html=True)

st.info("Faça upload do arquivo JSON da Service Account do Google Cloud para gerar o `secrets.toml` no formato correto.")


# ============ FUNÇÕES ============

def validar_credenciais(creds):
    """Valida os campos obrigatórios do JSON"""
    campos_obrigatorios = [
        "type", "project_id", "private_key_id", "private_key",
        "client_email", "client_id", "token_uri"
    ]
    
    ausentes = [c for c in campos_obrigatorios if c not in creds or not creds[c]]
    erros = []
    
    if ausentes:
        erros.append(f"Campos ausentes: {', '.join(ausentes)}")
    
    if "private_key" in creds:
        pk = creds["private_key"]
        if not pk.startswith("-----BEGIN PRIVATE KEY-----"):
            erros.append("private_key não inicia com '-----BEGIN PRIVATE KEY-----'")
        if not pk.strip().endswith("-----END PRIVATE KEY-----"):
            erros.append("private_key não termina com '-----END PRIVATE KEY-----'")
    
    if "type" in creds and creds["type"] != "service_account":
        erros.append(f"Tipo inválido: {creds['type']} (esperado: service_account)")
    
    return erros


def gerar_toml(creds):
    """Gera o conteúdo TOML com private_key corretamente escapada"""
    linhas = ["[gcp_service_account]"]
    
    for key, value in creds.items():
        if key == "private_key":
            # Escapar quebras de linha como \n literais
            value_escaped = value.replace("\n", "\\n")
            linhas.append(f'{key} = "{value_escaped}"')
        else:
            linhas.append(f'{key} = "{value}"')
    
    return "\n".join(linhas) + "\n"


# ============ UPLOAD DO ARQUIVO ============

arquivo = st.file_uploader(
    "📤 Selecione o arquivo JSON da Service Account",
    type=["json"],
    help="Arquivo baixado do Google Cloud Console → IAM & Admin → Service Accounts → Keys"
)

if arquivo:
    try:
        conteudo = arquivo.read().decode("utf-8")
        creds = json.loads(conteudo)
        
        st.success(f"✅ Arquivo **{arquivo.name}** carregado com sucesso!")
        
        # ============ VALIDAÇÃO ============
        st.markdown("### 🔍 Validação do Arquivo")
        
        erros = validar_credenciais(creds)
        
        if erros:
            for erro in erros:
                st.error(f"❌ {erro}")
        else:
            st.success("✅ Todos os campos obrigatórios estão presentes e válidos")
        
        # Resumo das credenciais (sem expor a chave)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**📧 Client Email:**")
            st.code(creds.get("client_email", "N/A"), language=None)
        with col2:
            st.markdown(f"**🆔 Project ID:**")
            st.code(creds.get("project_id", "N/A"), language=None)
        
        # ============ GERAR TOML ============
        st.markdown("### 📄 Resultado (secrets.toml)")
        
        toml_gerado = gerar_toml(creds)
        
        st.code(toml_gerado, language="toml")
        
        # ============ AÇÕES ============
        st.markdown("### 💾 Salvar Arquivo")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.download_button(
                label="⬇️ Baixar secrets.toml",
                data=toml_gerado,
                file_name="secrets.toml",
                mime="text/plain",
                use_container_width=True
            )
        
        with col_b:
            if st.button("💾 Salvar direto em .streamlit/", use_container_width=True):
                try:
                    STREAMLIT_DIR.mkdir(exist_ok=True)
                    
                    # Backup se já existir
                    if SECRETS_PATH.exists():
                        backup = SECRETS_PATH.with_suffix(".toml.bak")
                        backup.write_bytes(SECRETS_PATH.read_bytes())
                        st.warning(f"⚠️ Backup criado: `{backup.name}`")
                    
                    SECRETS_PATH.write_text(toml_gerado, encoding="utf-8")
                    st.success(f"✅ Salvo em: `{SECRETS_PATH}`")
                    st.info("🔄 Recarregue o app para aplicar as novas credenciais")
                    
                except Exception as e:
                    st.error(f"❌ Erro ao salvar: {e}")
        
        # ============ TESTE DE CONEXÃO ============
        st.markdown("---")
        
        if st.button("🔌 Testar Conexão com Google Sheets"):
            with st.spinner("Autenticando..."):
                try:
                    from google.oauth2.service_account import Credentials
                    
                    scopes = [
                        "https://www.googleapis.com/auth/spreadsheets",
                        "https://www.googleapis.com/auth/drive"
                    ]
                    
                    credentials = Credentials.from_service_account_info(creds, scopes=scopes)
                    
                    # Forçar geração de token (valida a assinatura JWT)
                    import google.auth.transport.requests
                    request = google.auth.transport.requests.Request()
                    credentials.refresh(request)
                    
                    st.success("✅ **Autenticação bem-sucedida!** A chave JWT é válida.")
                    st.balloons()
                    
                except ImportError:
                    st.error("❌ Biblioteca não instalada. Execute: `pip install google-auth`")
                except Exception as e:
                    st.error(f"❌ Falha na autenticação: {e}")
    
    except json.JSONDecodeError as e:
        st.error(f"❌ Arquivo JSON inválido: {e}")
    except UnicodeDecodeError:
        st.error("❌ Erro de codificação. Verifique se o arquivo é um JSON válido.")
    except Exception as e:
        st.error(f"❌ Erro ao processar arquivo: {e}")

else:
    st.markdown("""
    ### 📋 Como obter o arquivo JSON
    
    1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
    2. Vá em **IAM & Admin → Service Accounts**
    3. Selecione a service account do projeto
    4. Aba **Keys → Add Key → Create new key**
    5. Escolha **JSON** e faça o download
    6. Faça upload do arquivo aqui
    """)