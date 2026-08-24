# VERSÃO CLEAN: PROJEÇÕES ORDENADAS (REAIS PRIMEIRO, PROJEÇÕES DEPOIS)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from plotly.graph_objects import Figure
from io import BytesIO
from typing import Any, Optional, cast
from streamlit_gsheets import GSheetsConnection

# ====================================================
# BLOCO 1: CONFIGURAÇÕES E UTILITÁRIOS
# ====================================================
st.set_page_config(page_title="Total de Consultivos", page_icon="📋", layout="wide")

class Configuracoes:
    url_ativos = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    cores_grafico = ["#0EA5E9", "#22C55E", "#A855F7", "#F97316", "#EF4444", "#3B82F6"]
    temas_card = {
        "amarelo": {
            "fundo": "#FEF9C3",
            "texto": "#854D0E",
            "borda": "#EAB308",
            "titulo": "#A16207",
        },
        "azul": {
            "fundo": "#F0F9FF",
            "texto": "#0369A1",
            "borda": "#0EA5E9",
            "titulo": "#075985",
        },
        "verde": {
            "fundo": "#F0FDF4",
            "texto": "#15803D",
            "borda": "#22C55E",
            "titulo": "#166534",
        },
        "roxo": {
            "fundo": "#FAF5FF",
            "texto": "#7E22CE",
            "borda": "#A855F7",
            "titulo": "#6B21A8",
        },
        "cinza": {
            "fundo": "#F8FAFC",
            "texto": "#334155",
            "borda": "#94A3B8",
            "titulo": "#64748B",
        },
        "escuro": {
            "fundo": "#1E293B",
            "texto": "#FFFFFF",
            "borda": "#475569",
            "titulo": "#E2E8F0",
        },
        "vermelho": {
            "fundo": "#FEF2F2",
            "texto": "#B91C1C",
            "borda": "#EF4444",
            "titulo": "#991B1B",
        },
    }


class ComponenteVisual:
    @staticmethod
    def criar_card(
        titulo: str, valor: str, tema: str = "azul", delta: Optional[str] = None
    ) -> str:
        cores = Configuracoes.temas_card.get(tema, Configuracoes.temas_card["azul"])
        delta_html = ""
        if delta:
            cor_delta = (
                "#22c55e"
                if delta.startswith(("+", "▲"))
                else (
                    "#ef4444"
                    if delta.startswith(("-", "▼"))
                    else "#0ea5e9" if "Total" in delta else "#94a3b8"
                )
            )
            simbolo = (
                "▲"
                if delta.startswith("+")
                else "▼" if delta.startswith("-") else "◴" if "Total" in delta else "■"
            )
            delta_html = f'<span style="font-size:13px; color:{cor_delta}; margin-left:10px;">{simbolo} {delta}</span>'

        return f"""
        <div style="background-color:{cores['fundo']}; padding:20px; border-radius:10px; border-left:6px solid {cores['borda']}; box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:10px;">
            <p style="margin:0; font-size:13px; color:{cores['titulo']};"><b>{titulo}</b></p>
            <h2 style="margin:5px 0 0 0; color:{cores['texto']}; font-weight:900; font-size:28px;">{valor}{delta_html}</h2>
        </div>"""
        
    @staticmethod        
    def aplicar_capa():
        st.markdown(
            """
        <style>
    /* CRIAÇÃO DE ESTILOS PARA A HERO (barra de títulos) */
            .hero-corp {
            background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
            padding: 32px 40px;
            border-radius: 16px;
            color: white;
            box-shadow: 0 10px 40px rgba(1, 40, 105, 0.25);
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
        }
        .hero-corp::before {
            content: '';
            position: absolute;
            top: -50%; right: -10%;
            width: 400px; height: 400px;
            background: rgba(255,255,255,0.05);
            border-radius: 50%;
        }
        .hero-title {
            font-size: 34px;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.5px;
            font-family: 'Segoe UI', -apple-system, sans-serif;
        }
        .hero-subtitle {
            font-size: 15px;
            opacity: 0.92;
            margin: 6px 0 0 0;
            font-weight: 400;
        }
        .hero-badge {
            display: inline-block;
            background: rgba(255,255,255,0.18);
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 12px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        
            .kpi-card {
                padding: 1.4rem 1.6rem; border-radius: 1rem; border-left: 5px solid;
                box-shadow: 0 4px 12px rgba(0,0,0,0.06);
                min-height: 110px; display: flex; flex-direction: column; justify-content: center;
            }
            .kpi-val  { font-size: 1.85rem; font-weight: 800; line-height: 1.1; margin: 0.3rem 0; }
            .kpi-lab  { font-size: 0.72rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; }
            .kpi-sub  { font-size: 0.78rem; margin-top: 0.2rem; }
            .section-header {
                display: flex; align-items: center; gap: 0.6rem;
                margin: 1.5rem 0 0.8rem; padding-bottom: 0.4rem;
                border-bottom: 2px solid #E2E8F0;
            }
            .section-header h3 { margin: 0; font-size: 1.1rem; color: #0F172A; }
            
            /* ═══════════════════════════════════════════
            SIDEBAR — Estilo dos filtros
            ═══════════════════════════════════════════ */
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #F8FAFC 0%, #EFF6FF 100%);
            }
            [data-testid="stSidebar"] h3 {
                color: #012869;
                font-weight: 700;
                font-size: 14px;
                margin-top: 0.5rem;
            }
            [data-testid="stSidebar"] [data-testid="stDateInput"] input {
                border-radius: 8px !important;
                border: 1.5px solid #CBD5E1 !important;
                font-weight: 600 !important;
                color: #012869 !important;
                font-size: 13px !important;
            }
            [data-testid="stSidebar"] [data-testid="stDateInput"] input:focus {
                border-color: #F37C04 !important;
                box-shadow: 0 0 0 3px rgba(243, 124, 4, 0.15) !important;
            }
            [data-testid="stSidebar"] [data-testid="stRadio"] label {
                font-size: 13px !important;
                padding: 4px 0 !important;
            }
            [data-testid="stSidebar"] .stSelectbox label {
                color: #012869 !important;
                font-weight: 600 !important;
                font-size: 13px !important;
            }
        </style>
        """,
            unsafe_allow_html=True,
        )
        
    @staticmethod
    def colorir_metas(valor: Any) -> str:
        """Destaca valores numéricos maiores que 350."""
        try:
            numero = pd.to_numeric(valor, errors="coerce")

            if pd.notna(numero) and numero > 350:
                return (
                    "background-color: #BBF7D0; "
                    "color: #166534; "
                    "font-weight: bold;"
                )
        except (TypeError, ValueError):
            pass

        # Mantém a formatação original da coluna
        return ""

class Calculos:
    @staticmethod
    def variacao(valor: float, geral: float) -> str:
        if geral == 0 or pd.isna(geral) or abs(valor - geral) < 0.0001:
            return "Visão Geral"
        pct = ((valor - geral) / geral) * 100
        return f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"

    @staticmethod
    def share(valor: float, geral: float) -> str:
        if geral == 0 or pd.isna(geral) or abs(valor - geral) < 0.0001:
            return "Visão Geral"
        return f"{(valor / geral) * 100:.1f}% do Total"

    @staticmethod
    def fator_projecao(df: pd.DataFrame) -> tuple:
        if df.empty or "DATA" not in df.columns or df["DATA"].isna().all():
            return 1.0, 0
        hoje = pd.Timestamp.today().normalize()
        if df["DATA"].max().month != hoje.month or df["DATA"].max().year != hoje.year:
            return 1.0, 0

        inicio_mes = hoje.replace(day=1)
        prox_mes = inicio_mes.replace(day=28) + pd.Timedelta(days=4)
        fim_mes = prox_mes - pd.Timedelta(days=prox_mes.day)

        dias_uteis_total = len(
            [d for d in pd.date_range(inicio_mes, fim_mes) if d.dayofweek < 6]
        )
        dias_decorridos = len(
            [d for d in pd.date_range(inicio_mes, hoje) if d.dayofweek < 6]
        )
        faltantes = dias_uteis_total - dias_decorridos

        return (
            dias_uteis_total / dias_decorridos
            if dias_decorridos > 0 and faltantes > 0
            else 1.0
        ), faltantes


# ====================================================
# BLOCO 2: PREPARAÇÃO DE DADOS
# ====================================================
@st.cache_data(ttl=300)
def carregar_hierarquia():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=Configuracoes.url_ativos, ttl=0)
    df.columns = df.columns.str.strip()
    return df[["Login", "Técnico", "Monitor", "Base"]].drop_duplicates(subset=["Login"])


def preparar_ranking(
    df: pd.DataFrame, colunas_grupo: list, fator_proj: float = 1.0
) -> pd.DataFrame:
    colunas_soma = [
        "Qtde. Cons.",
        "Qtde. Prod.",
        "Qtde. Mesh",
        "Qtde. TV",
        "Qtde. Virtua",
    ]
    colunas_soma = [c for c in colunas_soma if c in df.columns]

    # Agrupa os dados e renomeia
    res = df.groupby(colunas_grupo, dropna=False)[colunas_soma].sum().reset_index()
    renomeios = {
        "Qtde. Cons.": "Total Consultivos",
        "Qtde. Prod.": "Total Produtos",
        "Qtde. Mesh": "Mesh",
        "Qtde. TV": "TV Box",
        "Qtde. Virtua": "Virtua",
    }
    res = res.rename(columns=renomeios).fillna(0)

    # Adiciona Posição
    res = res.sort_values(
        "Total Consultivos" if "Total Consultivos" in res.columns else "Total Produtos",
        ascending=False,
    )
    res.insert(0, "Posição", range(1, len(res) + 1))

    # Lógica de Ordenação: 1º Reais, 2º Projeções, 3º Demais Produtos
    nova_ordem = ["Posição"] + colunas_grupo

    # Adiciona os Reais
    if "Total Consultivos" in res.columns:
        nova_ordem.append("Total Consultivos")
    if "Total Produtos" in res.columns:
        nova_ordem.append("Total Produtos")

    # Adiciona as Projeções
    if "Total Consultivos" in res.columns and fator_proj > 1.0:
        res["Proj. Consultivos"] = (res["Total Consultivos"] * fator_proj).astype(int)
        nova_ordem.append("Proj. Consultivos")

    if "Total Produtos" in res.columns and fator_proj > 1.0:
        res["Proj. Produtos"] = (res["Total Produtos"] * fator_proj).astype(int)
        nova_ordem.append("Proj. Produtos")

    # Adiciona os demais produtos (Mesh, TV, Virtua)
    for col in ["Mesh", "TV Box", "Virtua"]:
        if col in res.columns:
            nova_ordem.append(col)

    # Converte métricas para int e aplica nova ordem
    metricas = [c for c in nova_ordem if c not in ["Posição"] + colunas_grupo]
    res[metricas] = res[metricas].astype(int)
    return res[nova_ordem]


# ====================================================
# BLOCO 3: CARREGAMENTO PRINCIPAL E TRATAMENTO
# ====================================================
ComponenteVisual.aplicar_capa()
st.markdown(
        f"""
        <div class="hero-corp">
            <div style="position:relative;z-index:2;">
                <h1 class="hero-title">📋 Central de Performance | Painel de Consultivos e Produtos</h1>
                <p class="hero-subtitle">
                    Análise de mix de produtos, consultivos realizados e oportunidades comerciais
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if (
    "dados_cons" not in st.session_state
    or "Consultivo" not in st.session_state["dados_cons"]
):
    st.warning("⚠️ Carregue os dados na aba principal primeiro.")
    st.stop()

df = st.session_state["dados_cons"]["Consultivo"].copy()

# Tratamento de Colunas Numéricas Iniciais
mapa = {
    "QTDE_CONSULTIVO": "Qtde. Cons.",
    "QTDE_PRODUTOS": "Qtde. Prod.",
    "QTDE_MESH": "Qtde. Mesh",
    "QTDE_TV": "Qtde. TV",
    "QTDE_VIRTUA": "Qtde. Virtua",
}
for k, v in mapa.items():
    df[v] = pd.to_numeric(df.get(k, 0), errors="coerce").fillna(0).astype(int)

if "DATA" in df.columns:
    df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce", dayfirst=True)

# Merge com GSheets (Hierarquia)
try:
    df_ativos = carregar_hierarquia()
    df["LOGIN NETSALES"] = df.get("LOGIN NETSALES", "").astype(str).str.strip()
    df = df.drop(columns=["Monitor", "Base"], errors="ignore")
    # Outer merge: traz todos da base + todos da planilha do google (mesmo zerados)
    df = pd.merge(
        df, df_ativos, left_on="LOGIN NETSALES", right_on="Login", how="outer"
    )
except Exception as e:
    st.error(f"Erro ao carregar hierarquia: {e}")

# 1. Arruma os Logins (Se não tem Netsales, pega o Login do GSheets)
df["LOGIN NETSALES"] = df["LOGIN NETSALES"].fillna(df["Login"]).fillna("SEM LOGIN")

# 2. Arruma os Nomes (Se não tem Vendedor na base, pega Técnico do GSheets, senão pega Login)
if "VENDEDOR" not in df.columns:
    df["VENDEDOR"] = np.nan

df["VENDEDOR"] = (
    df["VENDEDOR"]
    .fillna(df["Técnico"])
    .fillna(df["LOGIN NETSALES"])
    .fillna("Nome Não Cadastrado")
)

# 3. Arruma a Hierarquia
df["Monitor"] = df["Monitor"].fillna("Não Identificado")
df["Base"] = df["Base"].fillna("Não Identificada")

# 4. Preenche com ZERO as métricas dos técnicos zerados puxados do GSheets
colunas_metricas = [
    "Qtde. Cons.",
    "Qtde. Prod.",
    "Qtde. Mesh",
    "Qtde. TV",
    "Qtde. Virtua",
]
for col in colunas_metricas:
    if col in df.columns:
        df[col] = df[col].fillna(0).astype(int)

# ====================================================
# BLOCO 4: FILTROS E CÁLCULOS GLOBAIS
# ====================================================
# Memória dos Totais (Sem Filtro) para % de Share
t_cons, t_prod = df["Qtde. Cons."].sum(), df["Qtde. Prod."].sum()
t_mesh, t_tv, t_vir = (
    df["Qtde. Mesh"].sum(),
    df["Qtde. TV"].sum(),
    df["Qtde. Virtua"].sum(),
)

st.sidebar.header("🎯 Filtros Avançados")

# ═══════════════════════════════════════════════════
# 📅 FILTRO DE CALENDÁRIO INTELIGENTE
# ═══════════════════════════════════════════════════
st.sidebar.markdown("### 📅 Período")

if "DATA" in df.columns and df["DATA"].notna().any():

    # Garante que a coluna esteja em formato datetime
    df["DATA"] = pd.to_datetime(
        df["DATA"],
        errors="coerce",
        dayfirst=True,
    )

    datas_validas = df["DATA"].dropna()

    data_min = datas_validas.min().date()
    data_max = datas_validas.max().date()
    hoje = pd.Timestamp.today().normalize().date()

    # Não permite que a referência ultrapasse a última data disponível.
    data_referencia = min(hoje, data_max)

    def limitar_data(data):
        """Mantém a data dentro dos limites disponíveis."""
        return max(data_min, min(data, data_max))

    def obter_periodo(nome_preset: str):
        """
        Calcula automaticamente o intervalo conforme o atalho.

        Se não houver dados no mês atual, o preset 'Mês atual'
        utiliza o mês da última data disponível.
        """
        if nome_preset == "Mês atual":
            inicio = data_referencia.replace(day=1)
            fim = data_referencia

        elif nome_preset == "Última semana":
            # Intervalo móvel de 7 dias, incluindo a data de referência
            inicio = (
                pd.Timestamp(data_referencia) - pd.Timedelta(days=6)
            ).date()
            fim = data_referencia

        elif nome_preset == "Últimos 15 dias":
            # Intervalo móvel de 15 dias, incluindo a data de referência
            inicio = (
                pd.Timestamp(data_referencia) - pd.Timedelta(days=14)
            ).date()
            fim = data_referencia

        elif nome_preset == "Todo período":
            inicio = data_min
            fim = data_max

        else:
            # Personalizado: mantém o período selecionado pelo usuário
            periodo_atual = st.session_state.get(
                "filtro_periodo",
                (data_min, data_max),
            )

            if (
                isinstance(periodo_atual, (tuple, list))
                and len(periodo_atual) == 2
            ):
                inicio = pd.Timestamp(periodo_atual[0]).date()
                fim = pd.Timestamp(periodo_atual[1]).date()
            else:
                inicio = data_min
                fim = data_max

        inicio = limitar_data(inicio)
        fim = limitar_data(fim)

        if inicio > fim:
            inicio = fim

        return inicio, fim

    # ------------------------------------------------
    # Atalhos
    # ------------------------------------------------
    preset = st.sidebar.radio(
        "Atalho:",
        [
            "Mês atual",
            "Última semana",
            "Últimos 15 dias",
            "Todo período",
            "Personalizado",
        ],
        index=0,
        key="calendario_preset",
    )

    # Detecta mudança de dados, de dia ou de preset
    assinatura_datas = (
        data_min.isoformat(),
        data_max.isoformat(),
        hoje.isoformat(),
    )

    assinatura_anterior = st.session_state.get(
        "_assinatura_datas_calendario"
    )
    preset_anterior = st.session_state.get(
        "_preset_calendario_aplicado"
    )

    dados_mudaram = assinatura_anterior != assinatura_datas
    preset_mudou = preset_anterior != preset

    # Atualiza automaticamente o date_input quando:
    # 1. O usuário muda o atalho;
    # 2. As datas disponíveis mudam;
    # 3. O dia atual muda.
    if (
        "filtro_periodo" not in st.session_state
        or preset_mudou
        or dados_mudaram
    ):
        st.session_state["filtro_periodo"] = obter_periodo(preset)

    st.session_state["_assinatura_datas_calendario"] = assinatura_datas
    st.session_state["_preset_calendario_aplicado"] = preset

    def marcar_como_personalizado():
        """
        Quando o usuário altera manualmente o calendário,
        muda o atalho automaticamente para Personalizado.
        """
        if (
            st.session_state.get("calendario_preset")
            != "Personalizado"
        ):
            st.session_state["calendario_preset"] = "Personalizado"

    # ------------------------------------------------
    # Calendário
    # ------------------------------------------------
    periodo = st.sidebar.date_input(
        "Selecione o intervalo:",
        min_value=data_min,
        max_value=data_max,
        format="DD/MM/YYYY",
        key="filtro_periodo",
        on_change=marcar_como_personalizado,
    )

    # Preserva técnicos vindos da hierarquia que não possuem DATA.
    # Isso é importante porque seu merge é outer.
    manter_sem_data = st.sidebar.checkbox(
        "Manter técnicos sem movimentação",
        value=True,
        help=(
            "Mantém no ranking os técnicos da hierarquia que não possuem "
            "registros no período selecionado."
        ),
        key="manter_tecnicos_sem_data",
    )

    # ------------------------------------------------
    # Aplicação do filtro
    # ------------------------------------------------
    if (
        isinstance(periodo, (tuple, list))
        and len(periodo) == 2
    ):
        data_ini = pd.Timestamp(periodo[0]).date()
        data_fim = pd.Timestamp(periodo[1]).date()

        if data_ini > data_fim:
            data_ini, data_fim = data_fim, data_ini

        inicio_timestamp = pd.Timestamp(data_ini)

        # Limite exclusivo para incluir todo o último dia,
        # inclusive quando DATA possui horário.
        fim_exclusivo = (
            pd.Timestamp(data_fim) + pd.Timedelta(days=1)
        )

        mascara_periodo = (
            df["DATA"].ge(inicio_timestamp)
            & df["DATA"].lt(fim_exclusivo)
        )

        if manter_sem_data:
            mascara_periodo = (
                mascara_periodo | df["DATA"].isna()
            )

        df = df.loc[mascara_periodo].copy()

        st.sidebar.caption(
            f"📆 {data_ini.strftime('%d/%m/%Y')} "
            f"→ {data_fim.strftime('%d/%m/%Y')}"
        )

        st.sidebar.caption(
            f"📊 {len(df):,.0f} registros após o filtro".replace(",", ".")
        )

        # Informa quando o mês da última carga é diferente do mês atual
        mes_atual = (hoje.year, hoje.month)
        mes_referencia = (
            data_referencia.year,
            data_referencia.month,
        )

        if preset == "Mês atual" and mes_referencia != mes_atual:
            st.sidebar.info(
                "Não há dados no mês corrente. "
                "Exibindo automaticamente o último mês disponível."
            )

    else:
        st.sidebar.warning(
            "⚠️ Selecione a data inicial e a data final."
        )

else:
    st.sidebar.info(
        "ℹ️ Não existem datas válidas para aplicar o filtro."
    )

st.sidebar.divider()

# ═══════════════════════════════════════════════════
# 🏢 FILTROS DE HIERARQUIA
# ═══════════════════════════════════════════════════
base_sel = st.sidebar.selectbox(
    "Base:", ["Todas"] + sorted(df["Base"].dropna().unique().tolist())
)
monitor_opts = ["Todos"] + sorted(
    df[df["Base"] == base_sel]["Monitor"].dropna().unique().tolist()
    if base_sel != "Todas"
    else df["Monitor"].dropna().unique().tolist()
)
monitor_sel = st.sidebar.selectbox("Monitor:", monitor_opts)

if base_sel != "Todas":
    df = df[df["Base"] == base_sel]
if monitor_sel != "Todos":
    df = df[df["Monitor"] == monitor_sel]

# ═══════════════════════════════════════════════════
# 📊 RESUMO DOS FILTROS APLICADOS
# ═══════════════════════════════════════════════════
st.sidebar.divider()
with st.sidebar.expander("📋 Resumo dos filtros", expanded=False):
    st.markdown(f"**Base:** {base_sel}")
    st.markdown(f"**Monitor:** {monitor_sel}")
    st.markdown(f"**Registros filtrados:** {len(df):,}".replace(",", "."))

# Variáveis Filtradas
f_cons, f_prod = df["Qtde. Cons."].sum(), df["Qtde. Prod."].sum()
f_mesh, f_tv, f_vir = (
    df["Qtde. Mesh"].sum(),
    df["Qtde. TV"].sum(),
    df["Qtde. Virtua"].sum(),
)
eq_ativas = df.groupby("LOGIN NETSALES")["Qtde. Cons."].sum()
eq_total, eq_produtivas = len(eq_ativas), len(eq_ativas[eq_ativas > 0])
eficiencia = (eq_produtivas / eq_total) if eq_total > 0 else 0

fator_proj, falt_dias = Calculos.fator_projecao(df)

# ====================================================
# BLOCO 5: UI - CARDS E PROJEÇÕES
# ====================================================
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        ComponenteVisual.criar_card("Total Equipes", f"{eq_total:,.0f}", "azul"),
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        ComponenteVisual.criar_card(
            "Equipes Produtivas", f"{eq_produtivas:,.0f}", "verde"
        ),
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        ComponenteVisual.criar_card(
            "Técnicos Zerados", f"{eq_total - eq_produtivas:,.0f}", "vermelho"
        ),
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        ComponenteVisual.criar_card(
            "Eficiência (Conversão)", f"{eficiencia:.2%}", "roxo"
        ),
        unsafe_allow_html=True,
    )

st.markdown("#### 📊 Resultado Realizado (Até o momento)")
c5, c6, c7, c8, c9 = st.columns(5)
with c5:
    st.markdown(
        ComponenteVisual.criar_card(
            "Tot. Consultivos", f"{f_cons:,.0f}", "azul", Calculos.share(f_cons, t_cons)
        ),
        unsafe_allow_html=True,
    )
with c6:
    st.markdown(
        ComponenteVisual.criar_card(
            "Tot. Produtos", f"{f_prod:,.0f}", "cinza", Calculos.share(f_prod, t_prod)
        ),
        unsafe_allow_html=True,
    )
with c7:
    st.markdown(
        ComponenteVisual.criar_card("Total Mesh", f"{f_mesh:,.0f}", "escuro"),
        unsafe_allow_html=True,
    )
with c8:
    st.markdown(
        ComponenteVisual.criar_card("Total TV Box", f"{f_tv:,.0f}", "escuro"),
        unsafe_allow_html=True,
    )
with c9:
    st.markdown(
        ComponenteVisual.criar_card("Total Virtua", f"{f_vir:,.0f}", "escuro"),
        unsafe_allow_html=True,
    )

if falt_dias > 0:
    st.markdown(
        f"#### 🔮 Projeção Fim do Mês <span style='font-size:14px; color:#64748B;'> (Faltam {falt_dias} dias úteis)</span>",
        unsafe_allow_html=True,
    )
    p1, p2, _ = st.columns([1, 1, 3])
    with p1:
        st.markdown(
            ComponenteVisual.criar_card(
                "Proj. Consultivos",
                f"{int(f_cons * fator_proj):,}",
                "amarelo",
                f"+ {int((f_cons * fator_proj) - f_cons)} est.",
            ),
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            ComponenteVisual.criar_card(
                "Proj. Produtos",
                f"{int(f_prod * fator_proj):,}",
                "amarelo",
                f"+ {int((f_prod * fator_proj) - f_prod)} est.",
            ),
            unsafe_allow_html=True,
        )

st.divider()

# ====================================================
# BLOCO 6: TABELAS E GRÁFICOS
# ====================================================
col_tit, col_tog, _ = st.columns([3, 1, 1])
with col_tit:
    st.subheader("👷 Visão Consolidada")
with col_tog:
    detalhar_tec = st.toggle("Detalhar por Técnico")

grupo = (
    ["LOGIN NETSALES", "VENDEDOR", "Monitor", "Base"] if detalhar_tec else ["Monitor"]
)
df_exibir = preparar_ranking(df, grupo, fator_proj)

colunas_proj = [c for c in df_exibir.columns if "Proj." in str(c)]
colunas_reais = [
    c for c in ["Total Consultivos", "Total Produtos"] if c in df_exibir.columns
]
todas_num = [c for c in df_exibir.columns if c not in ["Posição"] + grupo]

style_df = df_exibir.style.format(
    formatter=cast(Any, {c: "{:,}" for c in todas_num})
)

# Formatação das colunas realizadas
if colunas_reais:
    style_df = style_df.set_properties(
        **{
            "background-color": "#F8FAFC",
            "font-weight": "bold",
        },
        subset=cast(Any, colunas_reais),
    )

# Formatação das colunas projetadas
if colunas_proj:
    style_df = style_df.set_properties(
        **{
            "background-color": "#FEF9C3",
            "color": "#854D0E",
            "font-weight": "bold",
        },
        subset=cast(Any, colunas_proj),
    )

# Colunas nas quais a meta de 350 será verificada
coluna_meta = colunas_reais

if coluna_meta:
    style_df = style_df.map(
        ComponenteVisual.colorir_metas,
        subset=cast(Any, coluna_meta),
    )

st.dataframe(
    style_df,
    use_container_width=True,
    height=450,
    hide_index=True,
)

# Abas de Gráficos Rápidos e Alertas
aba1, aba2 = st.tabs(["📈 Desempenho e Matriz", "🚫 Equipes sem Consultivos"])

with aba1:
    g1, g2 = st.columns(2)
    with g1:
        if not df_exibir.empty:
            st.plotly_chart(
                px.bar(
                    df_exibir.head(10),
                    x=grupo[1] if detalhar_tec else "Monitor",
                    y="Total Consultivos",
                    title="Top 10 Consultivos (Real)",
                ),
                use_container_width=True,
            )
    with g2:
        df_disp = df_exibir[df_exibir["Total Consultivos"] > 0]
        if not df_disp.empty:
            st.plotly_chart(
                px.scatter(
                    df_disp,
                    x="Total Consultivos",
                    y="Total Produtos",
                    color="Monitor",
                    title="Matriz: Consultivos x Produtos",
                ),
                use_container_width=True,
            )

with aba2:
    st.subheader("🚫 Equipes que ainda não fizeram Consultivos")
    # Filtra quem tem exatamente zero consultivos
    df_zerados = df_exibir[df_exibir["Total Consultivos"] == 0]

    if not df_zerados.empty:
        st.dataframe(df_zerados, use_container_width=True, hide_index=True)
    else:
        st.success(
            "✅ Excelente! 100% da operação possui pelo menos um consultivo registrado."
        )

# Exportação
st.divider()
st.subheader("📥 Exportar Dados (Inclui Projeções)")
c_exp1, c_exp2 = st.columns([1, 4])
tipo_exp = c_exp1.selectbox("Formato:", ["Excel", "CSV"], label_visibility="collapsed")
if tipo_exp == "CSV":
    c_exp2.download_button(
        "Baixar",
        df_exibir.to_csv(index=False, encoding="utf-8-sig"),
        "relatorio.csv",
        "text/csv",
    )
else:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_exibir.to_excel(w, index=False)
    c_exp2.download_button(
        "Baixar",
        out.getvalue(),
        "relatorio.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
