# debug_400.py — v2 com leitura robusta do secrets.toml
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import traceback

st.title("🔬 Debug 400 — v2")

SHEET_ID = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
ABA      = "lista_ativos"

# ── Mostra TODAS as chaves disponíveis no secrets ─────────────────────────────
st.subheader("🔑 Chaves encontradas no secrets.toml")
try:
    s = st.secrets["connections"]["gsheets"]
    chaves = list(s.keys())
    st.code("\n".join(chaves))

    # Verifica campos obrigatórios
    obrigatorios = ["project_id","private_key_id","private_key",
                    "client_id","token_uri"]
    opcionais    = ["client_email","client_x509_cert_url",
                    "auth_uri","auth_provider_x509_cert_url"]

    faltando = [c for c in obrigatorios if c not in chaves]
    if faltando:
        st.error(f"❌ Campos obrigatórios FALTANDO: {faltando}")
        st.stop()
    else:
        st.success("✅ Todos os campos obrigatórios presentes.")

    for op in opcionais:
        if op not in chaves:
            st.warning(f"⚠️ Campo opcional ausente (será inferido): {op}")

except Exception:
    st.error("❌ Erro ao ler secrets:")
    st.code(traceback.format_exc())
    st.stop()

# ── Monta client_email de forma robusta ───────────────────────────────────────
def extrair_client_email(s: dict) -> str:
    """
    Tenta obter client_email de múltiplas formas:
    1. Campo direto 'client_email'
    2. Derivado de 'client_x509_cert_url'
    3. Derivado de 'spreadsheet' (não se aplica)
    """
    # Forma 1: campo direto
    if "client_email" in s:
        return s["client_email"]

    # Forma 2: extrai da URL do certificado
    # URL formato: .../x509/EMAIL_ENCODED
    if "client_x509_cert_url" in s:
        import urllib.parse
        url   = s["client_x509_cert_url"]
        parte = url.split("/x509/")[-1]
        email = urllib.parse.unquote(parte)
        if "@" in email:
            st.info(f"ℹ️ client_email inferido da URL: `{email}`")
            return email

    st.error("❌ Não foi possível determinar o client_email.")
    st.stop()


def get_client():
    s = st.secrets["connections"]["gsheets"]

    client_email = extrair_client_email(dict(s))

    info = {
        "type":                        "service_account",
        "project_id":                  s["project_id"],
        "private_key_id":              s["private_key_id"],
        "private_key":                 s["private_key"],
        "client_email":                client_email,
        "client_id":                   s["client_id"],
        "auth_uri":                    s.get("auth_uri","https://accounts.google.com/o/oauth2/auth"),
        "token_uri":                   s.get("token_uri","https://oauth2.googleapis.com/token"),
        "auth_provider_x509_cert_url": s.get("auth_provider_x509_cert_url","https://www.googleapis.com/oauth2/v1/certs"),
        "client_x509_cert_url":        s.get("client_x509_cert_url",""),
    }

    st.expander("📋 Info de autenticação (sem private_key)").json(
        {k:v for k,v in info.items() if k != "private_key"}
    )

    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


# ── Passo 1: Autenticação ─────────────────────────────────────────────────────
st.subheader("Passo 1 — Autenticação")
try:
    gc = get_client()
    st.success("✅ Autenticação OK")
except Exception:
    st.error("❌ Falha na autenticação:")
    st.code(traceback.format_exc())
    st.stop()

# ── Passo 2: Abre a planilha ──────────────────────────────────────────────────
st.subheader("Passo 2 — Abre planilha e lista abas")
try:
    sh   = gc.open_by_key(SHEET_ID)
    abas = [ws.title for ws in sh.worksheets()]
    st.success(f"✅ Planilha aberta. Abas encontradas: {abas}")
except Exception:
    st.error("❌ Não conseguiu abrir a planilha:")
    st.code(traceback.format_exc())
    st.stop()

# ── Passo 3: Lê a aba ────────────────────────────────────────────────────────
st.subheader(f"Passo 3 — Lê aba '{ABA}'")
try:
    if ABA not in abas:
        st.error(f"❌ Aba '{ABA}' não existe. Abas disponíveis: {abas}")
        ABA_REAL = st.selectbox("Escolha a aba correta:", abas)
        ws = sh.worksheet(ABA_REAL)
    else:
        ws = sh.worksheet(ABA)

    dados = ws.get_all_values()
    if not dados:
        st.warning("Aba vazia — sem dados para testar escrita.")
        st.stop()

    cabecalho = dados[0]
    linhas    = dados[1:]
    df = pd.DataFrame(linhas, columns=cabecalho)

    st.success(f"✅ Leitura OK — {len(df)} linhas, colunas: {cabecalho}")
    st.dataframe(df.head(5), use_container_width=True)

except Exception:
    st.error("❌ Erro na leitura:")
    st.code(traceback.format_exc())
    st.stop()

# ── Passo 4: Testa escrita ────────────────────────────────────────────────────
st.subheader("Passo 4 — Testa ws.update() com dados reais")

# Garante que TUDO é str pura
payload = [[str(v) if v is not None else "" for v in row] for row in dados]
st.caption(f"Payload: {len(payload)} linhas × {len(payload[0])} colunas")

# Verifica tipos
tipos_errados = {}
for i, row in enumerate(payload[:10]):
    for j, val in enumerate(row):
        if not isinstance(val, str):
            tipos_errados[f"[{i}][{j}]"] = f"{type(val).__name__} = {val!r}"

if tipos_errados:
    st.error(f"❌ Ainda há valores não-string: {tipos_errados}")
else:
    st.success("✅ Payload 100% str — pronto para enviar.")

if st.button("🚀 Executar ws.clear() + ws.update()"):
    try:
        ws.clear()
        st.info("ws.clear() OK")
        ws.update(payload)
        st.success("✅ ws.update() OK — erro 400 resolvido!")
    except gspread.exceptions.APIError as exc:
        st.error(f"❌ APIError: {exc}")
        # Mostra o corpo completo da resposta
        try:
            st.json(exc.response.json())
        except Exception:
            st.code(str(exc))
        st.code(traceback.format_exc())
    except Exception:
        st.error("❌ Erro inesperado:")
        st.code(traceback.format_exc())

# ── Passo 5: Teste mínimo (1 linha) ──────────────────────────────────────────
st.subheader("Passo 5 — Teste mínimo (só cabeçalho + 1 linha)")
st.caption("Se este funcionar mas o Passo 4 falhar, o problema é volume de dados.")

if st.button("🧪 Escrever só cabeçalho + 1 linha"):
    try:
        payload_mini = [cabecalho, [""]*len(cabecalho)]
        ws.clear()
        ws.update(payload_mini)
        st.success("✅ Escrita mínima OK!")
    except gspread.exceptions.APIError as exc:
        st.error(f"❌ APIError no teste mínimo: {exc}")
        try:
            st.json(exc.response.json())
        except Exception:
            st.code(str(exc))
        st.code(traceback.format_exc())
    except Exception:
        st.error("❌ Erro inesperado:")
        st.code(traceback.format_exc())