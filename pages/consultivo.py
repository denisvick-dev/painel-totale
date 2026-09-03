import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import BytesIO
from typing import Any, Optional
from streamlit_gsheets import GSheetsConnection

from components.componentes import (
    aplicar_estilo,
    render_hero_totale_2,
    render_kpi,
    render_insight,
    render_section_header,
    FONTE_TEXTO,
    FONTE_TITULO,
    COR_PRIMARIA,
    COR_TEXTO_3,
)

# ====================================================
# BLOCO 1: CONFIGURAÇÕES E INICIALIZAÇÃO
# ====================================================
try:
    st.set_page_config(page_title="Total de Consultivos", page_icon="📋", layout="wide")
except Exception:
    pass

aplicar_estilo()

# ── CSS LOCAL DA PÁGINA (Cores da tabela e colunas específicas) ──
st.markdown(
    f"""
    <style>
    /* Estilo do SideBar Filtros Específicos */
    [data-testid="stSidebar"] [data-testid="stDateInput"] input {{
        border-radius: 8px !important;
        border: 1.5px solid #CBD5E1 !important;
        font-weight: 600 !important;
        color: #012869 !important;
        font-size: 13px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stDateInput"] input:focus {{
        border-color: #F37C04 !important;
        box-shadow: 0 0 0 3px rgba(243, 124, 4, 0.15) !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {{
        font-size: 13px !important;
        padding: 4px 0 !important;
    }}

    /* Estilo Tabela HTML DOM */
    .corp-table thead th {{
        background: linear-gradient(180deg, #012869 0%, #1E40AF 100%) !important;
        color: #FFFFFF !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        font-size: 11px !important;
        border-right: 1px solid rgba(255,255,255,0.12) !important;
    }}
    .corp-table td.col-real {{
        background: #F8FAFC !important;
        font-weight: 700 !important;
    }}
    .corp-table td.col-proj {{
        background: #FEF9C3 !important;
        color: #854D0E !important;
        font-weight: 700 !important;
    }}
    .corp-table td.meta-batida {{
        background: #DCFCE7 !important;
        color: #166534 !important;
        font-weight: 700 !important;
    }}
    .corp-table td.falta-meta {{
        background: #FEE2E2 !important;
        color: #991B1B !important;
        font-weight: 700 !important;
    }}
    .corp-table td.num {{
        text-align: right !important;
        font-variant-numeric: tabular-nums !important;
    }}
    .corp-table-wrap.centralizada {{
        width: min(100%, 1100px) !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }}
    .corp-table-wrap.centralizada .corp-table th,
    .corp-table-wrap.centralizada .corp-table td {{
        text-align: center !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


class Configuracoes:
    url_ativos = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    meta_diaria_consultivos = 7


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
    def fator_projecao(df: pd.DataFrame) -> tuple[float, int]:
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

        fator = (
            dias_uteis_total / dias_decorridos
            if dias_decorridos > 0 and faltantes > 0
            else 1.0
        )
        return fator, faltantes


# ====================================================
# BLOCO 2: PREPARAÇÃO DE DADOS
# ====================================================
@st.cache_data(ttl=300)
def carregar_hierarquia() -> pd.DataFrame:
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

    # Ordena
    col_sort = (
        "Total Consultivos" if "Total Consultivos" in res.columns else "Total Produtos"
    )
    if col_sort in res.columns:
        res = res.sort_values(col_sort, ascending=False)
    res.insert(0, "Posição", range(1, len(res) + 1))

    # Lógica de Ordenação das Colunas: 1º Reais, 2º Projeções, 3º Demais
    nova_ordem = ["Posição"] + colunas_grupo

    if "Total Consultivos" in res.columns:
        nova_ordem.append("Total Consultivos")
    if "Total Produtos" in res.columns:
        nova_ordem.append("Total Produtos")

    if "Total Consultivos" in res.columns and fator_proj > 1.0:
        res["Proj. Consultivos"] = (res["Total Consultivos"] * fator_proj).astype(int)
        nova_ordem.append("Proj. Consultivos")

    if "Total Produtos" in res.columns and fator_proj > 1.0:
        res["Proj. Produtos"] = (res["Total Produtos"] * fator_proj).astype(int)
        nova_ordem.append("Proj. Produtos")

    for col in ["Mesh", "TV Box", "Virtua"]:
        if col in res.columns:
            nova_ordem.append(col)

    metricas = [c for c in nova_ordem if c not in ["Posição"] + colunas_grupo]
    res[metricas] = res[metricas].astype(int)
    return res[nova_ordem]


def preparar_resumo_diario_monitor(
    df: pd.DataFrame, data_referencia: pd.Timestamp
) -> pd.DataFrame:
    """Agrega os consultivos do dia e preserva monitores sem movimentação."""
    monitores = pd.DataFrame(
        df[["Base", "Monitor"]]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .sort_values(["Base", "Monitor"])
    )
    mascara_dia = (
        df["DATA"].notna()
        & df["DATA"].dt.normalize().eq(data_referencia.normalize())
    )
    resumo = (
        df.loc[mascara_dia]
        .groupby(["Base", "Monitor"], dropna=False)["Qtde. Cons."]
        .sum()
        .rename("Total Consultivos")
        .reset_index()
    )
    resumo = monitores.merge(resumo, on=["Base", "Monitor"], how="left")
    resumo["Total Consultivos"] = resumo["Total Consultivos"].fillna(0).astype(int)
    return resumo.sort_values("Total Consultivos", ascending=False).reset_index(drop=True)


def calcular_meta_acumulada_monitor(
    df: pd.DataFrame, data_referencia: pd.Timestamp
) -> pd.DataFrame:
    """Calcula a meta de hoje compensando apenas o déficit de ontem."""
    ontem = data_referencia.normalize() - pd.Timedelta(days=1)
    mascara_anterior = (
        df["DATA"].notna()
        & df["DATA"].dt.normalize().eq(ontem)
    )
    realizado_anterior = (
        df.loc[mascara_anterior]
        .groupby(["Base", "Monitor"], dropna=False)["Qtde. Cons."]
        .sum()
        .rename("Realizado Anterior")
        .reset_index()
    )
    monitores = df[["Base", "Monitor"]].dropna().astype(str).drop_duplicates()
    resumo = monitores.merge(
        realizado_anterior, on=["Base", "Monitor"], how="left"
    )
    resumo["Realizado Anterior"] = resumo["Realizado Anterior"].fillna(0).astype(int)
    resumo["Saldo Anterior"] = (
        Configuracoes.meta_diaria_consultivos
        - resumo["Realizado Anterior"]
    ).clip(lower=0)
    resumo["Meta Ajustada"] = (
        Configuracoes.meta_diaria_consultivos + resumo["Saldo Anterior"]
    ).astype(int)
    return resumo[["Base", "Monitor", "Saldo Anterior", "Meta Ajustada"]]


def render_tabela_cons(
    df: pd.DataFrame,
    height: int = 450,
    max_rows: int = 300,
    limite_destaque: float = 350,
    colunas_destaque: list[str] | None = None,
    centralizar: bool = False,
) -> None:
    """Tabela HTML corporativa customizada para os Consultivos."""
    if df.empty:
        render_insight("Nenhum dado disponível.", "info")
        return

    df_show = df.head(max_rows).copy()
    cols = list(df_show.columns)

    if colunas_destaque is None:
        colunas_destaque = ["Total Produtos"]

    def _fmt(val: Any, col: str) -> str:
        if pd.isna(val):
            return "—"
        if (
            "Total" in col
            or "Proj" in col
            or col in ("Mesh", "TV Box", "Virtua", "Posição", "Meta Diária", "Falta para Meta")
        ):
            try:
                return f"{float(val):,.0f}".replace(",", ".")
            except (ValueError, TypeError):
                return str(val)
        return str(val)

    def _cls(val: Any, col: str) -> str:
        classes: list[str] = []

        if (
            "Total" in col
            or "Proj" in col
            or col in ("Mesh", "TV Box", "Virtua", "Posição", "Meta Diária", "Falta para Meta")
        ):
            classes.append("num")

        if col in ("Total Consultivos", "Total Produtos"):
            classes.append("col-real")

        if "Proj." in col:
            classes.append("col-proj")

        if col in colunas_destaque:
            try:
                if float(val) >= limite_destaque:
                    classes.append("meta-batida")
            except (ValueError, TypeError):
                pass

        if col == "Status" and val == "Meta atingida":
            classes.append("meta-batida")

        if col == "Falta para Meta":
            try:
                classes.append("meta-batida" if float(val) == 0 else "falta-meta")
            except (ValueError, TypeError):
                pass

        return " ".join(classes)

    # ── Montagem do HTML (estava faltando) ──
    header = "".join(f"<th>{c}</th>" for c in cols)
    body_rows: list[str] = []

    for _, row in df_show.iterrows():
        tds: list[str] = []
        for c in cols:
            v = row[c]
            display = (
                _fmt(v, c)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            cls = _cls(v, c)
            attr = f' class="{cls}"' if cls else ""
            tds.append(f"<td{attr}>{display}</td>")
        body_rows.append(f"<tr>{''.join(tds)}</tr>")

    html = f"""
    <div class="corp-table-wrap{' centralizada' if centralizar else ''}" style="max-height:{int(height)}px;">
      <table class="corp-table">
        <thead><tr>{header}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    if len(df) > max_rows:
        st.caption(f"Exibindo {max_rows} de {len(df)} registros.")


# ====================================================
# BLOCO 3: CARREGAMENTO PRINCIPAL E TRATAMENTO
# ====================================================
render_hero_totale_2(
    titulo="📋 Painel de Consultivos e Produtos",
    subtitulo="Análise de mix de produtos, consultivos realizados e oportunidades comerciais",
    badge_texto="Atualização em tempo real",
    badge_tipo="info",
)

st.divider()

if (
    "dados_cons" not in st.session_state
    or "Consultivo" not in st.session_state["dados_cons"]
):
    render_insight("Carregue os dados na aba principal primeiro.", "alerta")
    st.stop()

df = st.session_state["dados_cons"]["Consultivo"].copy()

# Tratamento Numérico
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
    # Outer merge
    df = pd.merge(
        df, df_ativos, left_on="LOGIN NETSALES", right_on="Login", how="outer"
    )
except Exception as e:
    st.error(f"Erro ao carregar hierarquia: {e}")

df["LOGIN NETSALES"] = df["LOGIN NETSALES"].fillna(df["Login"]).fillna("SEM LOGIN")

if "VENDEDOR" not in df.columns:
    df["VENDEDOR"] = np.nan
df["VENDEDOR"] = (
    df["VENDEDOR"]
    .fillna(df["Técnico"])
    .fillna(df["LOGIN NETSALES"])
    .fillna("Nome Não Cadastrado")
)
df["Monitor"] = df["Monitor"].fillna("Não Identificado")
df["Base"] = df["Base"].fillna("Não Identificada")

for col in ["Qtde. Cons.", "Qtde. Prod.", "Qtde. Mesh", "Qtde. TV", "Qtde. Virtua"]:
    if col in df.columns:
        df[col] = df[col].fillna(0).astype(int)

df_base = df.copy()


# ====================================================
# BLOCO 4: FILTROS E CÁLCULOS GLOBAIS
# ====================================================
t_cons, t_prod = df["Qtde. Cons."].sum(), df["Qtde. Prod."].sum()

st.sidebar.header("🎯 Filtros Avançados")

# ── FILTRO DE CALENDÁRIO ──
st.sidebar.markdown("### 📅 Período")
if "DATA" in df.columns and df["DATA"].notna().any():
    df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce", dayfirst=True)
    datas_validas = df["DATA"].dropna()
    data_min = datas_validas.min().date()
    hoje = pd.Timestamp.today().normalize().date()
    data_max = max(datas_validas.max().date(), hoje)

    data_referencia = min(hoje, data_max)

    def limitar_data(data):
        return max(data_min, min(data, data_max))

    def obter_periodo(nome_preset: str):
        if nome_preset == "Mês atual":
            inicio = data_referencia.replace(day=1)
            fim = data_referencia
        elif nome_preset == "Última semana":
            inicio = (pd.Timestamp(data_referencia) - pd.Timedelta(days=6)).date()
            fim = data_referencia
        elif nome_preset == "Últimos 15 dias":
            inicio = (pd.Timestamp(data_referencia) - pd.Timedelta(days=14)).date()
            fim = data_referencia
        elif nome_preset == "Todo período":
            inicio = data_min
            fim = data_max
        else:
            periodo_atual = st.session_state.get("filtro_periodo", (data_min, data_max))
            if isinstance(periodo_atual, (tuple, list)) and len(periodo_atual) == 2:
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

    assinatura_datas = (data_min.isoformat(), data_max.isoformat(), hoje.isoformat())
    assinatura_anterior = st.session_state.get("_assinatura_datas_calendario")
    preset_anterior = st.session_state.get("_preset_calendario_aplicado")

    dados_mudaram = assinatura_anterior != assinatura_datas
    preset_mudou = preset_anterior != preset

    if "filtro_periodo" not in st.session_state or preset_mudou or dados_mudaram:
        st.session_state["filtro_periodo"] = obter_periodo(preset)

    st.session_state["_assinatura_datas_calendario"] = assinatura_datas
    st.session_state["_preset_calendario_aplicado"] = preset

    def aplicar_dia_vigente() -> None:
        st.session_state["calendario_preset"] = "Personalizado"
        st.session_state["filtro_periodo"] = (hoje, hoje)

    st.sidebar.button(
        "📅 Dia vigente",
        key="botao_dia_vigente",
        use_container_width=True,
        on_click=aplicar_dia_vigente,
    )

    def marcar_como_personalizado():
        if st.session_state.get("calendario_preset") != "Personalizado":
            st.session_state["calendario_preset"] = "Personalizado"

    periodo = st.sidebar.date_input(
        "Selecione o intervalo:",
        min_value=data_min,
        max_value=data_max,
        format="DD/MM/YYYY",
        key="filtro_periodo",
        on_change=marcar_como_personalizado,
    )

    manter_sem_data = st.sidebar.checkbox(
        "Manter técnicos sem movimentação",
        value=True,
        help="Mantém no ranking os técnicos da hierarquia que não possuem registros no período selecionado.",
        key="manter_tecnicos_sem_data",
    )

    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        data_ini = pd.Timestamp(periodo[0]).date()
        data_fim = pd.Timestamp(periodo[1]).date()
        if data_ini > data_fim:
            data_ini, data_fim = data_fim, data_ini

        inicio_timestamp = pd.Timestamp(data_ini)
        fim_exclusivo = pd.Timestamp(data_fim) + pd.Timedelta(days=1)

        mascara_periodo = df["DATA"].ge(inicio_timestamp) & df["DATA"].lt(fim_exclusivo)
        if manter_sem_data:
            mascara_periodo = mascara_periodo | df["DATA"].isna()

        df = df.loc[mascara_periodo].copy()

        st.sidebar.caption(
            f"📆 {data_ini.strftime('%d/%m/%Y')} → {data_fim.strftime('%d/%m/%Y')}"
        )
        st.sidebar.caption(f"📊 {len(df):,.0f} registros".replace(",", "."))

        if preset == "Mês atual" and (data_referencia.year, data_referencia.month) != (
            hoje.year,
            hoje.month,
        ):
            st.sidebar.info(
                "Não há dados no mês corrente. Exibindo último mês disponível."
            )
    else:
        st.sidebar.warning("⚠️ Selecione a data inicial e a data final.")
else:
    st.sidebar.info("ℹ️ Não existem datas válidas para aplicar o filtro.")

st.sidebar.divider()

# ── FILTROS DE HIERARQUIA ──
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


# ====================================================
# BLOCO 5: UI - CARDS E PROJEÇÕES
# ====================================================
# Calculando Variaveis
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

# Linha 1 de KPIs
c1, c2, c3, c4 = st.columns(4)
render_kpi(c1, "Total Equipes", f"{eq_total:,.0f}".replace(",", "."), tema="azul")
render_kpi(
    c2, "Equipes Produtivas", f"{eq_produtivas:,.0f}".replace(",", "."), tema="verde"
)
render_kpi(
    c3,
    "Técnicos Zerados",
    f"{eq_total - eq_produtivas:,.0f}".replace(",", "."),
    tema="vermelho",
)
render_kpi(c4, "Eficiência (Conversão)", f"{eficiencia:.2%}", tema="cinza")

st.divider()

st.markdown("#### 📊 Resultado Realizado (Até o momento)")
c5, c6, c7, c8, c9 = st.columns(5)
render_kpi(
    c5,
    "Tot. Consultivos",
    f"{f_cons:,.0f}".replace(",", "."),
    sub=Calculos.share(f_cons, t_cons),
    tema="azul",
)
render_kpi(
    c6,
    "Tot. Produtos",
    f"{f_prod:,.0f}".replace(",", "."),
    sub=Calculos.share(f_prod, t_prod),
    tema="cinza",
)
render_kpi(c7, "Total Mesh", f"{f_mesh:,.0f}".replace(",", "."), tema="cinza")
render_kpi(c8, "Total TV Box", f"{f_tv:,.0f}".replace(",", "."), tema="cinza")
render_kpi(c9, "Total Virtua", f"{f_vir:,.0f}".replace(",", "."), tema="cinza")

st.divider()

if falt_dias > 0:
    st.markdown(
        f"#### 🔮 Projeção Fim do Mês <span style='font-size:14px; color:#64748B;'> (Faltam {falt_dias} dias úteis)</span>",
        unsafe_allow_html=True,
    )
    p1, p2, _ = st.columns([1, 1, 3])
    render_kpi(
        p1,
        "Proj. Consultivos",
        f"{int(f_cons * fator_proj):,.0f}".replace(",", "."),
        sub=f"+ {int((f_cons * fator_proj) - f_cons)} est.",
        tema="laranja",
    )
    render_kpi(
        p2,
        "Proj. Produtos",
        f"{int(f_prod * fator_proj):,.0f}".replace(",", "."),
        sub=f"+ {int((f_prod * fator_proj) - f_prod)} est.",
        tema="laranja",
    )

st.divider()

# ====================================================
# BLOCO 6: TABELAS E GRÁFICOS
# ====================================================
col_tit, col_tog, _ = st.columns([3, 1, 1])
with col_tit:
    render_section_header("👷", "Visão Consolidada")
with col_tog:
    st.write("")
    detalhar_tec = st.toggle("Detalhar por Técnico")

grupo = (
    ["LOGIN NETSALES", "VENDEDOR", "Monitor", "Base"] if detalhar_tec else ["Monitor"]
)
df_exibir = preparar_ranking(df, grupo, fator_proj)

# Destaque: técnico → 30 produtos | monitor → 350
if detalhar_tec:
    limite = 30
    cols_destaque = ["Total Produtos"]  # só produtos
    legenda_destaque = "🌟 Destaque Produtos (> 30)"
else:
    limite = 350
    cols_destaque = ["Total Consultivos", "Total Produtos"]
    legenda_destaque = "🌟 Destaque (> 350)"

render_tabela_cons(
    df_exibir,
    height=450,
    max_rows=300,
    limite_destaque=limite,
    colunas_destaque=cols_destaque,
)

st.markdown(
    f"""
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:-8px;margin-bottom:16px;
         padding:12px 16px;background:#F8FAFC;border-radius:8px;
         border:1px solid #E2E8F0;font-size:0.78rem;
         font-family:{FONTE_TEXTO};">
        <span style="font-weight:700;color:#6B7280;text-transform:uppercase;
             letter-spacing:0.05em;">🎨 Legenda:</span>
        <span style="background:#F8FAFC;color:#0F172A;padding:3px 10px;
             border-radius:6px;font-weight:700;border:1px solid #CBD5E1;">✅ Realizado</span>
        <span style="background:#DCFCE7;color:#166534;padding:3px 10px;
             border-radius:6px;font-weight:700;">{legenda_destaque}</span>
        <span style="background:#FEF9C3;color:#854D0E;padding:3px 10px;
             border-radius:6px;font-weight:700;">🎯 Projeção Calculada</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── ABAS INFERIORES ──
aba1, aba2 = st.tabs(
    ["📈 Desempenho e Matriz", "🚫 Equipes sem Consultivos"]
)

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
                    color_discrete_sequence=["#0EA5E9"],
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
                    color_discrete_sequence=px.colors.qualitative.Prism,
                ),
                use_container_width=True,
            )

with aba2:
    render_section_header("🚫", "Equipes que ainda não fizeram Consultivos")
    df_zerados = df_exibir[df_exibir["Total Consultivos"] == 0]

    if not df_zerados.empty:
        render_tabela_cons(df_zerados, height=350)
    else:
        render_insight(
            "Excelente! 100% da operação possui pelo menos um consultivo registrado.",
            "ok",
        )

# ── EXPORTAÇÃO ──
st.divider()
st.subheader("📥 Exportar Dados (Inclui Projeções)")
c_exp1, c_exp2 = st.columns([1, 4])
tipo_exp = c_exp1.selectbox("Formato:", ["Excel", "CSV"], label_visibility="collapsed")

if tipo_exp == "CSV":
    c_exp2.download_button(
        "Baixar Arquivo CSV",
        df_exibir.to_csv(index=False, encoding="utf-8-sig", decimal=","),
        "relatorio_consultivos.csv",
        "text/csv",
        use_container_width=True,
    )
else:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_exibir.to_excel(w, index=False)
    c_exp2.download_button(
        "Baixar Planilha Excel",
        out.getvalue(),
        "relatorio_consultivos.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
