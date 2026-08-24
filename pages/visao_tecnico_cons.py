import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, List

# ────────────────────────────────────────────────────────
# IMPORTAÇÃO DO DESIGN SYSTEM CORPORATIVO
# ────────────────────────────────────────────────────────
try:
    from components.componentes import (
        aplicar_estilo,
        render_hero,
        render_kpi,
        render_insight,
    )
except ImportError:
    st.error("⚠️ Módulo 'componentes.py' não encontrado.")
    st.stop()
    
# ────────────────────────────────────────────────────────
# FORÇAR LOCALE PARA PORTUGUÊS (BRASIL)
# ────────────────────────────────────────────────────────
import locale

def configurar_locale():
    try:
        locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")  # Linux / Streamlit Cloud
    except:
        try:
            locale.setlocale(locale.LC_TIME, "Portuguese_Brazil.1252")  # Windows
        except:
            pass  # Continua mesmo se não conseguir

configurar_locale()

# ====================================================
# CSS LOCAL — HERO PRETO/CINZA/PRATA (só nesta página)
# ====================================================
def _override_hero_dark() -> None:
    """Sobrescreve o hero do componentes.py com gradiente Preto/Cinza/Prata."""
    st.markdown(
        """
        <style>
        .hero-corp {
            background: linear-gradient(
                135deg,
                #0A0A0A   0%,
                #1C1C1E  18%,
                #2C2C2E  32%,
                #3A3A3C  45%,
                #636366  58%,
                #8E8E93  72%,
                #AEAEB2  84%,
                #C7C7CC  92%,
                #D1D1D6 100%
            ) !important;
            box-shadow:
                0 8px 32px rgba(0, 0, 0, 0.45),
                inset 0 1px 0 rgba(255, 255, 255, 0.12) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
        }

        .hero-corp::before {
            background: radial-gradient(
                circle at center,
                rgba(255, 255, 255, 0.10) 0%,
                rgba(199, 199, 204, 0.08) 30%,
                rgba(142, 142, 147, 0.04) 55%,
                transparent 75%
            ) !important;
        }

        .hero-corp::after {
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.04) 40%,
                rgba(255, 255, 255, 0.08) 50%,
                rgba(255, 255, 255, 0.04) 60%,
                transparent 100%
            ) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# BLOCO 1: FUNÇÕES UTILITÁRIAS
# ====================================================
class Utilitarios:
    @staticmethod
    def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df.columns = df.columns.str.upper().str.strip()
        mapa = {
            "QTDE_CONSULTIVO": "CONSULTIVOS",
            "QTDE. CONS.": "CONSULTIVOS",
            "QTDE_CONS": "CONSULTIVOS",
            "QTDE_PRODUTOS": "VENDAS",
            "QTDE. PROD.": "VENDAS",
            "PRODUTOS": "VENDAS",
            "QTDE_MESH": "MESH",
            "QTDE. MESH": "MESH",
            "QTDE_TV": "TV",
            "QTDE. TV": "TV",
            "QTDE_VIRTUA": "VIRTUA",
            "QTDE. VIRTUA": "VIRTUA",
        }
        for col_origem, col_destino in mapa.items():
            if col_origem in df.columns:
                df[col_destino] = pd.to_numeric(df[col_origem], errors="coerce").fillna(0).astype(int)
        return df

    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: List[str]) -> Optional[str]:
        cols_upper = {c.upper(): c for c in df.columns}
        for palavra in palavras_chave:
            if palavra in cols_upper:
                return cols_upper[palavra]
        return None


# ====================================================
# BLOCO 2: GRÁFICOS
# ====================================================
class Graficos:
    @staticmethod
    def grafico_linhas_vendas(df: pd.DataFrame, x_col: str, y_cons: str, y_prod: str) -> go.Figure:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_cons],
            name="Consultivos",
            mode="lines+markers",
            line=dict(color="#94A3B8", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_prod],
            name="Vendas",
            mode="lines+markers",
            line=dict(color="#F37C04", width=3),
            marker=dict(size=8),
        ))
        fig.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
        )
        return fig

    @staticmethod
    def grafico_rosca_mix(df_mix: pd.DataFrame) -> go.Figure:
        fig = px.pie(
            df_mix, names="Produto", values="Quantidade",
            hole=0.6,
            color_discrete_sequence=["#012869", "#F37C04", "#059669"],
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(
            margin=dict(t=10, b=10, l=0, r=0),
            showlegend=False,
        )
        return fig


# ====================================================
# BLOCO 3: MOCK DE DADOS
# ====================================================
@st.cache_data(show_spinner=False)
def gerar_dados_teste():
    import numpy as np
    datas = pd.date_range(start="2023-10-01", periods=15, freq="D").tolist() * 3
    tecnicos = ["JOAO SILVA", "MARIA SOUZA", "CARLOS ALBERTO"] * 15
    return pd.DataFrame({
        "DATA": datas,
        "VENDEDOR": tecnicos,
        "MONITOR": ["SUP A", "SUP B", "SUP A"] * 15,
        "BASE": ["SP", "SP", "CAMPINAS"] * 15,
        "QTDE_CONSULTIVO": np.random.randint(3, 12, size=45),
        "QTDE_PRODUTOS": np.random.randint(0, 5, size=45),
        "QTDE_MESH": np.random.randint(0, 3, size=45),
        "QTDE_TV": np.random.randint(0, 2, size=45),
        "QTDE_VIRTUA": np.random.randint(0, 2, size=45),
    })


# ====================================================
# BLOCO 4: INICIALIZAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(page_title="Visão Consultivo", page_icon="🗣️", layout="wide")

# 1. Aplica o design system global
aplicar_estilo()

# 2. Sobrescreve o hero APENAS nesta página
_override_hero_dark()

# 3. Renderiza o hero (agora com o gradiente preto/prata)
render_hero(
    titulo="🗣️ Raio-X: Módulo Consultivo",
    subtitulo="Auditoria de performance comercial, taxa de conversão e mix de produtos",
    badge="Vendas & Oportunidades",
)

# ====================================================
# BLOCO 5: CARREGAMENTO DA BASE
# ====================================================
df_cons = None
if "df_consultivo" in st.session_state:
    df_cons = st.session_state["df_consultivo"]
elif "dados_cons" in st.session_state:
    df_cons = st.session_state["dados_cons"].get("Consultivo", pd.DataFrame())

if df_cons is None or df_cons.empty:
    render_insight("Base não encontrada na sessão. Carregando dados de demonstração.", "alerta")
    df_cons = gerar_dados_teste()

df_cons = Utilitarios.padronizar_colunas(df_cons)

col_tec  = Utilitarios.buscar_coluna(df_cons, ["VENDEDOR", "TÉCNICO", "TECNICO", "NOME EQUIPE", "LOGIN"])
col_sup  = Utilitarios.buscar_coluna(df_cons, ["SUPERVISOR", "MONITOR", "GESTOR", "COORDENADOR", "LÍDER"])
col_base = Utilitarios.buscar_coluna(df_cons, ["BASE", "PROJETO", "CIDADE", "FILIAL", "LOCALIDADE"])
col_data = Utilitarios.buscar_coluna(df_cons, ["DATA", "DATA AGENDAMENTO", "DATE"])

if not col_tec:
    render_insight("Coluna de Vendedor/Técnico não encontrada na base.", "critico")
    st.stop()

df_cons[col_tec] = df_cons[col_tec].astype(str).str.strip().str.upper()

# ====================================================
# BLOCO 6: MOTOR DE BUSCA EM CASCATA
# ====================================================
with st.container(border=True):
    st.markdown("#### 🎯 Localizar Técnico")

    f_base, f_sup = st.columns(2)
    mask = pd.Series(True, index=df_cons.index)

    with f_base:
        if col_base:
            bases = ["Todas"] + sorted(
                [str(b) for b in df_cons[col_base].dropna().unique() if str(b).strip() != ""]
            )
            base_sel = st.selectbox("📍 Filtrar por Base:", bases)
            if base_sel != "Todas":
                mask &= df_cons[col_base] == base_sel

    with f_sup:
        if col_sup:
            monitores = ["Todos"] + sorted(
                [str(m) for m in df_cons.loc[mask, col_sup].dropna().unique() if str(m).strip() != ""]
            )
            sup_sel = st.selectbox("👤 Filtrar por Gestor:", monitores)
            if sup_sel != "Todos":
                mask &= df_cons[col_sup] == sup_sel

    st.divider()

    col_busca, col_info = st.columns([1, 2], gap="large")
    tecnicos_filtrados = sorted([t for t in df_cons.loc[mask, col_tec].unique() if t and t != "NAN"])

    with col_busca:
        tec_selecionado = st.selectbox("🔎 Selecione o Técnico:", options=[""] + tecnicos_filtrados)

    df_tec = pd.DataFrame()
    if tec_selecionado:
        df_tec = df_cons[df_cons[col_tec] == tec_selecionado].copy()

        sup_tec  = df_tec[col_sup].mode()[0]  if col_sup  and not df_tec[col_sup].empty  else "Não Atribuído"
        base_tec = df_tec[col_base].mode()[0] if col_base and not df_tec[col_base].empty else "Não Atribuída"

        with col_info:
            st.markdown("<br>", unsafe_allow_html=True)
            render_insight(f"<b>Gestor Comercial:</b> {sup_tec} &nbsp;|&nbsp; <b>Base:</b> {base_tec}", "info")

# ====================================================
# BLOCO 7: DASHBOARD
# ====================================================
if tec_selecionado and not df_tec.empty:
    st.divider()

    if "CONSULTIVOS" not in df_tec.columns or "VENDAS" not in df_tec.columns:
        render_insight("Colunas métricas (CONSULTIVOS/VENDAS) ausentes.", "critico")
        st.stop()

    t_cons = int(df_tec["CONSULTIVOS"].sum())
    t_prod = int(df_tec["VENDAS"].sum())
    taxa_conversao = (t_prod / t_cons) if t_cons > 0 else 0

    st.markdown(f"### 🎯 Funil de Abordagem de **{tec_selecionado}**")

    vc1, vc2, vc3 = st.columns(3)
    render_kpi(vc1, "Consultivos", str(t_cons), "🗣️ Tentativas realizadas", "azul")
    render_kpi(vc2, "Vendas Fechadas", str(t_prod), "🚀 Produtos convertidos", "laranja")

    cor_win = "verde" if taxa_conversao >= 0.1 else "laranja"
    render_kpi(vc3, "Win Rate", f"{taxa_conversao:.1%}", "📈 Taxa de Conversão", cor_win)

    st.write("---")

    g_linha, g_pizza = st.columns([2, 1])

    with g_linha:
        st.markdown("#### 📉 Ritmo de Ofertas Diárias")
        if col_data:
            df_tec[col_data] = pd.to_datetime(
                df_tec[col_data],
                errors="coerce",
                dayfirst=True  # ✅ garante padrão brasileiro
            )
            df_tec_grafico = df_tec.dropna(subset=[col_data]).copy()
            df_tec_grafico[col_data] = df_tec_grafico[col_data].dt.date

            if not df_tec_grafico.empty:
                df_tempo = df_tec_grafico.groupby(col_data)[["CONSULTIVOS", "VENDAS"]].sum().reset_index()
                st.plotly_chart(
                    Graficos.grafico_linhas_vendas(df_tempo, col_data, "CONSULTIVOS", "VENDAS"),
                    use_container_width=True,
                )
            else:
                render_insight("Nenhuma data válida encontrada para este técnico.", "alerta")
        else:
            render_insight("Coluna de data não encontrada na base.", "alerta")

    with g_pizza:
        st.markdown("#### 📦 Mix de Produtos")
        mix_data = {
            "Mesh":   int(df_tec["MESH"].sum())   if "MESH"   in df_tec.columns else 0,
            "TV":     int(df_tec["TV"].sum())     if "TV"     in df_tec.columns else 0,
            "Virtua": int(df_tec["VIRTUA"].sum()) if "VIRTUA" in df_tec.columns else 0,
        }
        df_mix = pd.DataFrame(list(mix_data.items()), columns=["Produto", "Quantidade"])
        df_mix = df_mix[df_mix["Quantidade"] > 0]

        if not df_mix.empty:
            st.plotly_chart(Graficos.grafico_rosca_mix(df_mix), use_container_width=True)
        else:
            render_insight("Nenhum produto (Mesh/TV/Virtua) vendido no período.", "ok")

    st.write("---")

    # ── Tabela detalhada ──
    st.markdown("#### 🧾 Extrato Comercial Detalhado")

    colunas_exibir = [
        c for c in [col_data, col_tec, "CONSULTIVOS", "VENDAS", "MESH", "TV", "VIRTUA"]
        if c is not None and c in df_tec.columns
    ]
    if col_data and col_data in df_tec.columns:
        df_tec[col_data] = pd.to_datetime(
        df_tec[col_data],
        errors="coerce",
        dayfirst=True
    )
    df_exibir = df_tec[colunas_exibir].copy()

    if col_data:
        df_exibir = df_exibir.sort_values(by=col_data, ascending=False)

    max_vendas = int(df_exibir["VENDAS"].max()) if not df_exibir.empty else 10

    configs_tabela = {
        "CONSULTIVOS": st.column_config.NumberColumn("🗣️ Consultivos", help="Total de abordagens"),
        "VENDAS": st.column_config.ProgressColumn("💰 Vendas", format="%d", min_value=0, max_value=max_vendas),
        "MESH": st.column_config.NumberColumn("📶 Mesh"),
        "TV": st.column_config.NumberColumn("📺 TV"),
        "VIRTUA": st.column_config.NumberColumn("🌐 Virtua"),
    }
    if col_data is not None:
        configs_tabela[col_data] = st.column_config.DateColumn("📅 Data", format="DD/MM/YYYY")
    if col_tec is not None:
        configs_tabela[col_tec] = st.column_config.TextColumn("Técnico")

    st.dataframe(
        df_exibir,
        use_container_width=True,
        hide_index=True,
        column_config=configs_tabela,
    )