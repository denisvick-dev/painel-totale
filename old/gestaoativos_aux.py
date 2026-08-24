import pandas as pd
import streamlit as st
import time
from datetime import datetime
import plotly.express as px
from io import BytesIO
from streamlit_gsheets import GSheetsConnection

# ===========================================
# BLOCO 1: CONFIGURAÇÃO E ESTILOS VISUAIS
# ===========================================
st.set_page_config(
    page_title="Gestão de Ativos TOTALE",
    page_icon="👷",
    layout="wide",
    initial_sidebar_state="expanded",
)

TEMAS_CARD = {
    "azul":     {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
    "verde":    {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
    "amarelo":  {"fundo": "#FEF9C3", "texto": "#854D0E", "borda": "#EAB308", "titulo": "#A16207"},
    "cinza":    {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
    "vermelho": {"fundo": "#FEF2F2", "texto": "#991B1B", "borda": "#EF4444", "titulo": "#7F1D1D"},
    "roxo":     {"fundo": "#FAF5FF", "texto": "#6B21A8", "borda": "#A855F7", "titulo": "#581C87"},
}


def criar_card_metrica(titulo: str, valor, tema: str = "azul") -> str:
    """Gera HTML para cards de métricas estilizados."""
    cores = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    return f"""
    <div style="background-color:{cores['fundo']};padding:20px;border-radius:10px;
         border-left:6px solid {cores['borda']};box-shadow:0 4px 6px rgba(0,0,0,0.1);
         margin-bottom:15px;">
        <p style="margin:0;font-size:14px;color:{cores['titulo']};"><b>{titulo}</b></p>
        <h2 style="margin:0;padding-top:5px;color:{cores['texto']};font-weight:900;">{valor}</h2>
    </div>
    """


# ===========================================
# BLOCO 2: FUNÇÕES DE DADOS (sem classe estática com cache)
# CORREÇÃO: cache_data não funciona bem em métodos estáticos.
# Extraímos as funções para o nível do módulo.
# ===========================================

URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"

COLUNAS_PADRAO = [
    "RE", "Login", "Técnico", "Base", "Monitor", "Situação",
    "Data_Admissao", "Tipo_Contrato", "Valor_Hora", "Custo_Mensal",
    "Ultima_Manutencao", "Proxima_Manutencao", "Observacoes", "Ultima_Modificacao",
]

LISTA_SITUACOES = ["ATIVO", "FÉRIAS", "INOPERANTE", "ETN", "DESLIGADO", "AFASTADO", "INATIVO"]
LISTA_CONTRATOS = ["CLT", "PJ", "ESTÁGIO", "TERCEIRIZADO"]


# CORREÇÃO 1: @st.cache_data no nível do módulo, não dentro de classe
@st.cache_data(ttl=300)
def _carregar_ativos_cached(url: str) -> pd.DataFrame:
    """Carrega e normaliza os dados do Google Sheets."""
    try:
        conexao = st.connection("gsheets", type=GSheetsConnection)
        df = conexao.read(spreadsheet=url, ttl=0)

        if df is None or df.empty:
            return pd.DataFrame(columns=COLUNAS_PADRAO)

        # Padroniza nomes de colunas
        df.columns = df.columns.str.strip()

        # Garante todas as colunas padrão
        for col in COLUNAS_PADRAO:
            if col not in df.columns:
                df[col] = 0.0 if col in ("Valor_Hora", "Custo_Mensal") else ""

        # CORREÇÃO 2: Converte colunas numéricas com segurança
        for col_num in ("Valor_Hora", "Custo_Mensal"):
            df[col_num] = pd.to_numeric(df[col_num], errors="coerce").fillna(0.0)

        # CORREÇÃO 3: Padroniza coluna de datas de manutenção para datetime
        for col_dt in ("Proxima_Manutencao", "Ultima_Manutencao"):
            df[col_dt] = pd.to_datetime(df[col_dt], dayfirst=True, errors="coerce")

        return df

    except Exception as e:
        st.error(f"Erro ao conectar com a nuvem: {e}")
        return pd.DataFrame(columns=COLUNAS_PADRAO)


def limpar_cache_ativos() -> None:
    """Limpa o cache da função de carregamento."""
    _carregar_ativos_cached.clear()


def gerar_log_auditoria(usuario: str, acao: str) -> str:
    """Gera string de auditoria com timestamp."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"{agora} | {acao} por {usuario.upper()}"


def salvar_no_sheets(df_novo: pd.DataFrame, mensagem: str) -> None:
    """Envia dados ao Sheets, limpa cache e força rerun."""
    try:
        # CORREÇÃO 4: Converte datas de volta para string antes de salvar
        df_salvar = df_novo.copy()
        for col_dt in ("Proxima_Manutencao", "Ultima_Manutencao"):
            if col_dt in df_salvar.columns:
                df_salvar[col_dt] = df_salvar[col_dt].apply(
                    lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) and hasattr(x, "strftime") else ""
                )

        conexao = st.connection("gsheets", type=GSheetsConnection)
        conexao.update(spreadsheet=URL_ATIVOS, data=df_salvar)
        limpar_cache_ativos()
        st.toast(mensagem, icon="✅")
        time.sleep(0.5)
        st.rerun()
    except Exception as erro:
        st.error(f"❌ Erro na gravação: {erro}")


def formatar_moeda(valor) -> str:
    """Formata numérico para Real Brasileiro."""
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


# ===========================================
# BLOCO 3: SEGURANÇA E LOGIN
# ===========================================
if "logado" not in st.session_state:
    st.session_state.logado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = ""

try:
    USER_CORRETO = st.secrets["credenciais"]["usuario"]
    PWD_CORRETA  = st.secrets["credenciais"]["senha"]
except Exception:
    USER_CORRETO = "denis"
    PWD_CORRETA  = "admin"

if not st.session_state.logado:
    st.markdown(
        """<style>[data-testid="collapsedControl"]{display:none}</style>""",
        unsafe_allow_html=True,
    )
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;'>🔐 Acesso TOTALE</h2>", unsafe_allow_html=True)
        with st.form("form_login"):
            usuario = st.text_input("👤 Usuário:")
            senha   = st.text_input("🔑 Senha:", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                if usuario == USER_CORRETO and senha == PWD_CORRETA:
                    st.session_state.logado = True
                    st.session_state.usuario_logado = usuario
                    st.rerun()
                else:
                    st.error("❌ Credenciais inválidas!")
    st.stop()

# ===========================================
# BLOCO 4: INTERFACE PRINCIPAL
# ===========================================
usuario_atual: str = st.session_state.usuario_logado

with st.sidebar:
    st.markdown(f"👤 **Logado:** `{usuario_atual.upper()}`")
    st.divider()
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        limpar_cache_ativos()
        st.rerun()
    if st.button("🚪 Sair do Sistema", use_container_width=True, type="secondary"):
        st.session_state.logado = False
        st.rerun()
    st.divider()
    st.info("💡 Use a aba 'Relatórios' para exportar a base completa com custos.")

st.title("📊 Gestão de Ativos e Patrimônio TOTALE")

with st.spinner("Sincronizando base de dados..."):
    df_bruto = _carregar_ativos_cached(URL_ATIVOS)

if not df_bruto.empty:

    # CORREÇÃO 5: dropna + astype + unique pode ter NaN — filtra antes
    lista_bases    = ["Nova Base..."] + sorted(
        df_bruto["Base"].dropna().astype(str).str.strip()
        .replace("", pd.NA).dropna().unique().tolist()
    )
    lista_monitores = ["Novo Monitor..."] + sorted(
        df_bruto["Monitor"].dropna().astype(str).str.strip()
        .replace("", pd.NA).dropna().unique().tolist()
    )

    aba_dash, aba_cad, aba_edit, aba_rel = st.tabs([
        "📈 Dashboard Operacional",
        "➕ Cadastro de Ativos",
        "✏️ Manutenção de Registro",
        "📑 Relatórios Gerenciais",
    ])

    # ═══════════════════════════════════════════
    # ABA 1: DASHBOARD OPERACIONAL
    # ═══════════════════════════════════════════
    with aba_dash:
        df_view = df_bruto[df_bruto["Situação"] != "INATIVO"].copy()

        c_f1, c_f2, c_f3 = st.columns(3)

        # CORREÇÃO 6: sorted() precisa de lista de strings, não de mixed types
        with c_f1:
            bases_disponiveis = sorted(df_view["Base"].dropna().astype(str).unique().tolist())
            filtro_base = st.selectbox("Filtrar por Base", ["Todas"] + bases_disponiveis)
            if filtro_base != "Todas":
                df_view = df_view[df_view["Base"] == filtro_base]

        with c_f2:
            sits_disponiveis = sorted(df_view["Situação"].dropna().astype(str).unique().tolist())
            filtro_sit = st.selectbox("Filtrar por Situação", ["Todas"] + sits_disponiveis)
            if filtro_sit != "Todas":
                df_view = df_view[df_view["Situação"] == filtro_sit]

        with c_f3:
            conts_disponiveis = sorted(
                df_view["Tipo_Contrato"].dropna().astype(str).unique().tolist()
            )
            filtro_cont = st.selectbox("Tipo de Contrato", ["Todos"] + conts_disponiveis)
            if filtro_cont != "Todos":
                df_view = df_view[df_view["Tipo_Contrato"] == filtro_cont]

        # KPIs
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

        total_ativos    = len(df_view)
        ativos_operando = len(df_view[df_view["Situação"] == "ATIVO"])
        custo_mensal    = df_view["Custo_Mensal"].sum() if "Custo_Mensal" in df_view.columns else 0

        # CORREÇÃO 7: comparação de datas correta (coluna já é datetime)
        hoje = pd.Timestamp(datetime.now().date())
        if "Proxima_Manutencao" in df_view.columns:
            manutencao_pendente = int(
                (df_view["Proxima_Manutencao"].notna() & (df_view["Proxima_Manutencao"] < hoje)).sum()
            )
        else:
            manutencao_pendente = 0

        with kpi1:
            st.markdown(criar_card_metrica("Total Ativos",        total_ativos,                    "cinza"),   unsafe_allow_html=True)
        with kpi2:
            st.markdown(criar_card_metrica("Em Operação",         ativos_operando,                 "verde"),   unsafe_allow_html=True)
        with kpi3:
            st.markdown(criar_card_metrica("Custo Mensal",        formatar_moeda(custo_mensal),     "vermelho"),unsafe_allow_html=True)
        with kpi4:
            st.markdown(criar_card_metrica("Manutenção Atrasada", manutencao_pendente,              "amarelo"), unsafe_allow_html=True)
        with kpi5:
            st.markdown(criar_card_metrica("Bases Ativas",        df_view["Base"].nunique(),        "azul"),    unsafe_allow_html=True)

        # Gráficos
        g1, g2 = st.columns([2, 1])
        with g1:
            df_graf_base = (
                df_view.groupby("Base").size().reset_index(name="Qtd")
                .sort_values("Qtd", ascending=False)
            )
            fig_base = px.bar(
                df_graf_base, x="Base", y="Qtd",
                title="Distribuição por Base",
                color="Qtd", color_continuous_scale="Blues",
            )
            st.plotly_chart(fig_base, use_container_width=True)

        with g2:
            df_graf_sit = df_view.groupby("Situação").size().reset_index(name="Qtd")
            fig_sit = px.pie(
                df_graf_sit, values="Qtd", names="Situação", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            st.plotly_chart(fig_sit, use_container_width=True)

        # CORREÇÃO 8: Exibe datas formatadas no dataframe (converte de volta p/ string)
        df_exibir = df_view.copy()
        for col_dt in ("Proxima_Manutencao", "Ultima_Manutencao"):
            if col_dt in df_exibir.columns:
                df_exibir[col_dt] = df_exibir[col_dt].apply(
                    lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else ""
                )
        st.dataframe(df_exibir, use_container_width=True, hide_index=True, height=400)

    # ═══════════════════════════════════════════
    # ABA 2: CADASTRO
    # ═══════════════════════════════════════════
    with aba_cad:
        st.subheader("📝 Novo Registro de Ativo/Técnico")

        with st.form("form_novo_ativo", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)

            with c1:
                novo_re    = st.text_input("RE *")
                novo_login = st.text_input("Login NETSALES *")
                novo_nome  = st.text_input("Nome do Técnico *")

            with c2:
                sel_base = st.selectbox("Base *", lista_bases)
                # CORREÇÃO 9: disabled funciona com expressão booleana
                nova_base_input = st.text_input(
                    "Ou Nova Base:",
                    disabled=(sel_base != "Nova Base..."),
                )
                sel_monitor = st.selectbox("Monitor *", lista_monitores)
                novo_monitor_input = st.text_input(
                    "Ou Novo Monitor:",
                    disabled=(sel_monitor != "Novo Monitor..."),
                )

            with c3:
                nova_situacao  = st.selectbox(
                    "Situação *",
                    [s for s in LISTA_SITUACOES if s != "INATIVO"],
                )
                novo_contrato  = st.selectbox("Tipo Contrato *", LISTA_CONTRATOS)
                novo_valor_hora = st.number_input("Valor Hora (R$)", min_value=0.0, step=0.50)
                novo_custo     = st.number_input("Custo Mensal Estimado (R$)", min_value=0.0, step=50.0)
                data_admissao  = st.date_input("Data Admissão", value=datetime.now())

            if st.form_submit_button("💾 Salvar Registro", type="primary"):
                b_final = (
                    nova_base_input.strip().upper()
                    if sel_base == "Nova Base..." and nova_base_input.strip()
                    else sel_base
                )
                m_final = (
                    novo_monitor_input.strip().upper()
                    if sel_monitor == "Novo Monitor..." and novo_monitor_input.strip()
                    else sel_monitor
                )

                erros = []
                if not novo_re.strip():
                    erros.append("RE")
                if not novo_login.strip():
                    erros.append("Login")
                if not novo_nome.strip():
                    erros.append("Nome")

                if erros:
                    st.error(f"⚠️ Preencha os campos obrigatórios: {', '.join(erros)}")
                else:
                    novo_registro = {
                        "RE":                 novo_re.strip(),
                        "Login":              novo_login.strip(),
                        "Técnico":            novo_nome.strip().upper(),
                        "Monitor":            m_final,
                        "Base":               b_final,
                        "Situação":           nova_situacao,
                        "Tipo_Contrato":      novo_contrato,
                        "Valor_Hora":         novo_valor_hora,
                        "Custo_Mensal":       novo_custo,
                        "Data_Admissao":      data_admissao.strftime("%d/%m/%Y"),
                        "Ultima_Manutencao":  "",
                        "Proxima_Manutencao": "",
                        "Observacoes":        "",
                        "Ultima_Modificacao": gerar_log_auditoria(usuario_atual, "CRIADO"),
                    }
                    df_atualizado = pd.concat(
                        [df_bruto, pd.DataFrame([novo_registro])],
                        ignore_index=True,
                    )
                    salvar_no_sheets(df_atualizado, "Registro criado com sucesso!")

    # ═══════════════════════════════════════════
    # ABA 3: EDIÇÃO E MANUTENÇÃO
    # ═══════════════════════════════════════════
    with aba_edit:
        st.subheader("🔍 Buscar e Editar Registro")

        df_busca = df_bruto[df_bruto["Situação"] != "INATIVO"].copy()
        df_busca["Identificador"] = (
            df_busca["Técnico"].fillna("") + " | RE: " + df_busca["RE"].astype(str)
        )

        tecnico_sel = st.selectbox(
            "Selecione o Técnico:",
            [""] + df_busca["Identificador"].tolist(),
        )

        if tecnico_sel != "":
            # CORREÇÃO 10: usa .iloc[0] para pegar o índice original com segurança
            idx_busca = df_busca[df_busca["Identificador"] == tecnico_sel].index
            if len(idx_busca) == 0:
                st.warning("Registro não encontrado.")
                st.stop()

            idx   = idx_busca[0]
            dados = df_bruto.loc[idx]

            col_ed, col_ex = st.columns([2, 1])

            with col_ed:
                with st.form("form_editar"):
                    st.markdown("#### ✏️ Dados Cadastrais")
                    ec1, ec2 = st.columns(2)

                    with ec1:
                        st.text_input("RE",    value=str(dados.get("RE",    "")), disabled=True)
                        st.text_input("Login", value=str(dados.get("Login", "")), disabled=True)
                        edit_nome = st.text_input("Técnico", value=str(dados.get("Técnico", "")))
                        edit_base = st.text_input("Base",    value=str(dados.get("Base",    "")))

                    with ec2:
                        edit_monitor = st.text_input("Monitor", value=str(dados.get("Monitor", "")))

                        sit_atual = str(dados.get("Situação", "ATIVO"))
                        sit_idx   = LISTA_SITUACOES.index(sit_atual) if sit_atual in LISTA_SITUACOES else 0
                        edit_situacao = st.selectbox("Situação", LISTA_SITUACOES, index=sit_idx)

                        cont_atual = str(dados.get("Tipo_Contrato", "CLT"))
                        cont_idx   = LISTA_CONTRATOS.index(cont_atual) if cont_atual in LISTA_CONTRATOS else 0
                        edit_contrato = st.selectbox("Contrato", LISTA_CONTRATOS, index=cont_idx)

                        # CORREÇÃO 11: garante que custo seja float
                        custo_atual = 0.0
                        try:
                            custo_atual = float(dados.get("Custo_Mensal", 0.0) or 0.0)
                        except (ValueError, TypeError):
                            custo_atual = 0.0
                        edit_custo = st.number_input("Custo Mensal", value=custo_atual, min_value=0.0)

                    st.markdown("#### 🛠️ Controle de Manutenção")
                    em1, em2 = st.columns(2)

                    # CORREÇÃO 12: extrai valor de data com segurança (coluna já é datetime)
                    with em1:
                        val_ult = dados.get("Ultima_Manutencao")
                        val_ult = val_ult.date() if pd.notna(val_ult) and hasattr(val_ult, "date") else None
                        edit_ult_man = st.date_input("Última Manutenção", value=val_ult)

                    with em2:
                        val_prox = dados.get("Proxima_Manutencao")
                        val_prox = val_prox.date() if pd.notna(val_prox) and hasattr(val_prox, "date") else None
                        edit_prox_man = st.date_input("Próxima Manutenção", value=val_prox)

                    if st.form_submit_button("💾 Atualizar Registro", type="primary"):
                        df_atualizado = df_bruto.copy()
                        df_atualizado.at[idx, "Técnico"]           = edit_nome.strip().upper()
                        df_atualizado.at[idx, "Base"]              = edit_base.strip().upper()
                        df_atualizado.at[idx, "Monitor"]           = edit_monitor.strip().upper()
                        df_atualizado.at[idx, "Situação"]          = edit_situacao
                        df_atualizado.at[idx, "Tipo_Contrato"]     = edit_contrato
                        df_atualizado.at[idx, "Custo_Mensal"]      = edit_custo

                        # Salva como datetime (salvar_no_sheets converte para string)
                        df_atualizado.at[idx, "Ultima_Manutencao"]  = (
                            pd.Timestamp(edit_ult_man)  if edit_ult_man  else pd.NaT
                        )
                        df_atualizado.at[idx, "Proxima_Manutencao"] = (
                            pd.Timestamp(edit_prox_man) if edit_prox_man else pd.NaT
                        )
                        df_atualizado.at[idx, "Ultima_Modificacao"] = gerar_log_auditoria(
                            usuario_atual, "EDIÇÃO"
                        )
                        salvar_no_sheets(df_atualizado, "Registro atualizado!")

            with col_ex:
                st.markdown("#### 🗑️ Zona de Perigo")
                st.warning("Inativar remove o técnico das listas operacionais, mas mantém o histórico.")

                re_alvo = dados.get("RE", "")
                if st.checkbox(f"Confirmar inativação do RE {re_alvo}"):
                    if st.button("🚨 INATIVAR", type="primary", use_container_width=True):
                        df_atualizado = df_bruto.copy()
                        df_atualizado.at[idx, "Situação"]          = "INATIVO"
                        df_atualizado.at[idx, "Ultima_Modificacao"] = gerar_log_auditoria(
                            usuario_atual, "INATIVADO"
                        )
                        salvar_no_sheets(df_atualizado, "Técnico inativado.")

    # ═══════════════════════════════════════════
    # ABA 4: RELATÓRIOS
    # ═══════════════════════════════════════════
    with aba_rel:
        st.subheader("📑 Exportação e Análise de Custos")

        rel_tipo = st.selectbox(
            "Tipo de Relatório",
            ["Completo", "Apenas Ativos", "Apenas Inativos", "Manutenção Pendente"],
        )

        df_rel = df_bruto.copy()

        if rel_tipo == "Apenas Ativos":
            df_rel = df_rel[df_rel["Situação"] == "ATIVO"]
        elif rel_tipo == "Apenas Inativos":
            df_rel = df_rel[df_rel["Situação"] == "INATIVO"]
        elif rel_tipo == "Manutenção Pendente":
            # CORREÇÃO 13: comparação correta com timestamp
            hoje_ts = pd.Timestamp(datetime.now().date())
            df_rel = df_rel[
                df_rel["Proxima_Manutencao"].notna() &
                (df_rel["Proxima_Manutencao"] < hoje_ts)
            ]

        # Exibe com datas formatadas
        df_rel_exib = df_rel.copy()
        for col_dt in ("Proxima_Manutencao", "Ultima_Manutencao"):
            if col_dt in df_rel_exib.columns:
                df_rel_exib[col_dt] = df_rel_exib[col_dt].apply(
                    lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else ""
                )

        st.dataframe(df_rel_exib, use_container_width=True, height=400)

        # Exportação Excel
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df_rel_exib.to_excel(writer, index=False, sheet_name="Relatorio")

        st.download_button(
            label="📥 Baixar Relatório (Excel)",
            data=out.getvalue(),
            file_name=f"relatorio_{rel_tipo.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

else:
    st.warning("⚠️ Planilha vazia ou erro de conexão.")