import streamlit as st
import pandas as pd
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
        render_section_header,
    )
except ImportError:
    st.error("⚠️ Módulo 'componentes.py' não encontrado.")
    st.stop()


# ====================================================
# BLOCO 1: FUNÇÕES UTILITÁRIAS
# ====================================================
class Utilitarios:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: List[str]) -> Optional[str]:
        cols_upper = {c.upper(): c for c in df.columns}
        for palavra in palavras_chave:
            if palavra in cols_upper:
                return cols_upper[palavra]
        return None

    @staticmethod
    def formatar_numero(valor: float, casas_decimais: int = 2) -> str:
        if pd.isna(valor):
            return "0," + "0" * casas_decimais
        return (
            f"{valor:,.{casas_decimais}f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    @staticmethod
    def formatar_dataframe_para_download(df: pd.DataFrame) -> bytes:
        df_export = df.copy()
        for col in df_export.select_dtypes(
            include=["float", "float64", "float32"]
        ).columns:
            df_export[col] = df_export[col].apply(
                lambda x: Utilitarios.formatar_numero(x) if pd.notna(x) else "0,00"
            )
        return df_export.to_csv(index=False, sep=";", encoding="utf-8-sig").encode(
            "utf-8-sig"
        )


# ====================================================
# BLOCO 2: CSS EXCLUSIVO — TOOLTIP PREMIUM
# (apenas o que o componentes.py não cobre)
# ====================================================
def _injetar_css_tooltip() -> None:
    """
    Injeta apenas o CSS do tooltip premium.
    O restante (fontes, hero, KPIs) vem do componentes.py via aplicar_estilo().
    """
    st.markdown(
        """
        <style>
        .card-premium          { position: relative; cursor: help; }

        .tooltip-premium {
            visibility: hidden;
            background-color: #1E293B;
            color: #F8FAFC;
            text-align: center;
            border-radius: 8px;
            padding: 8px 12px;
            position: absolute;
            z-index: 999;
            bottom: 115%;
            left: 50%;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.3s ease, bottom 0.3s ease;
            font-size: 10px;
            font-weight: 500;
            min-width: 180px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            pointer-events: none;
        }
        .tooltip-premium::after {
            content: "";
            position: absolute;
            top: 100%; left: 50%;
            margin-left: -6px;
            border-width: 6px;
            border-style: solid;
            border-color: #1E293B transparent transparent transparent;
        }
        .card-premium:hover .tooltip-premium {
            visibility: visible;
            opacity: 1;
            bottom: 105%;
        }
        /* ─── HERO CORPORATIVO — GRADIENTE PRETO/CINZA/PRATA ─── */
        .hero-corp {
            background: linear-gradient(
                135deg,
                #0A0A0A   0%,    /* Preto profundo        */
                #1C1C1E  18%,    /* Carvão                */
                #2C2C2E  32%,    /* Grafite               */
                #3A3A3C  45%,    /* Cinza escuro           */
                #636366  58%,    /* Cinza médio            */
                #8E8E93  72%,    /* Cinza claro            */
                #AEAEB2  84%,    /* Prata                  */
                #C7C7CC  92%,    /* Prata claro            */
                #D1D1D6 100%     /* Prata luminoso         */
            );
            padding: 32px 48px;
            border-radius: 12px;
            color: white;
            box-shadow:
                0 8px 32px rgba(0, 0, 0, 0.45),
                inset 0 1px 0 rgba(255, 255, 255, 0.12);
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.08);
            min-height: 110px;
        }

        .hero-corp::before {
            content: '';
            position: absolute;
            top: 50%;
            right: -80px;
            transform: translateY(-50%);
            width: 380px;
            height: 380px;
            background: radial-gradient(
                circle at center,
                rgba(255, 255, 255, 0.10) 0%,
                rgba(199, 199, 204, 0.08) 30%,
                rgba(142, 142, 147, 0.04) 55%,
                transparent 75%
            );
            border-radius: 50%;
            pointer-events: none;
            filter: blur(2px);
        }

        .hero-corp::after {
            content: '';
            position: absolute;
            top: 0;
            left: 35%;
            width: 30%;
            height: 100%;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.04) 40%,
                rgba(255, 255, 255, 0.08) 50%,
                rgba(255, 255, 255, 0.04) 60%,
                transparent 100%
            );
            transform: skewX(-15deg);
            pointer-events: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ====================================================
# BLOCO 3: CARD COM TOOLTIP
# (componentes.py não tem tooltip — mantemos local)
# ====================================================
# Paleta local — espelha as variáveis CSS do componentes.py
_TEMAS_CARD = {
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
    "laranja": {
        "fundo": "#FFF7ED",
        "texto": "#C2410C",
        "borda": "#F97316",
        "titulo": "#9A3412",
    },
    "cinza": {
        "fundo": "#F8FAFC",
        "texto": "#334155",
        "borda": "#94A3B8",
        "titulo": "#64748B",
    },
    "roxo": {
        "fundo": "#FAF5FF",
        "texto": "#7E22CE",
        "borda": "#A855F7",
        "titulo": "#581C87",
    },
}


def _criar_card_tooltip(
    titulo: str,
    valor: str,
    tema: str = "azul",
    subtitulo: str = "",
    icone: str = "",
    tooltip: str = "",
) -> str:
    """
    Card KPI com tooltip hover.
    Utiliza a mesma paleta visual do componentes.py.
    """
    cores = _TEMAS_CARD.get(tema, _TEMAS_CARD["azul"])
    titulo_fmt = f"{icone} {titulo}" if icone else titulo
    html_tooltip = f'<div class="tooltip-premium">{tooltip}</div>' if tooltip else ""

    return f"""
    <div class="card-premium"
         style="background:{cores['fundo']};padding:20px;border-radius:10px;
                border-left:6px solid {cores['borda']};
                box-shadow:0 4px 6px rgba(0,0,0,0.05);
                height:100%;display:flex;flex-direction:column;
                justify-content:center;transition:transform 0.2s;"
         onmouseover="this.style.transform='scale(1.02)'"
         onmouseout="this.style.transform='scale(1)'">
        <p style="margin:0;font-size:14px;color:{cores['titulo']};font-weight:bold;">{titulo_fmt}</p>
        <h2 style="margin:5px 0 0;color:{cores['texto']};font-weight:900;font-size:32px;">{valor}</h2>
        <p style="margin:5px 0 0;font-size:13px;color:#64748B;font-weight:500;">{subtitulo}</p>
        {html_tooltip}
    </div>
    """


# ====================================================
# BLOCO 4: GRÁFICOS
# ====================================================
class Graficos:
    @staticmethod
    def grafico_combo_raiox(
        df: pd.DataFrame, x_col: str, y_bar: str, y_line: str
    ) -> go.Figure:
        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df[x_col],
                y=df[y_bar],
                name="Volume O.S.",
                marker_color="#CBD5E1",
                opacity=0.8,
                hovertemplate="<b>%{x}</b><br>O.S.: %{y}<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df[x_col],
                y=df[y_line],
                name="Pontos",
                mode="lines+markers",
                line=dict(color="#012869", width=3),  # cor-primaria do design system
                marker=dict(size=8, color="#F37C04"),  # cor-secundaria como destaque
                yaxis="y2",
                hovertemplate="<b>%{x}</b><br>Pontos: %{y:.2f}<extra></extra>",
            )
        )

        fig.update_layout(
            margin=dict(l=0, r=50, t=30, b=0),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            hovermode="x unified",
            yaxis=dict(
                title="Quantidade O.S.", showgrid=True, gridcolor="rgba(0,0,0,0.05)"
            ),
            yaxis2=dict(
                title="Pontos",
                overlaying="y",
                side="right",
                showgrid=False,
                tickformat=".1f",
            ),
            xaxis=dict(showgrid=False),
        )
        return fig


# ====================================================
# BLOCO 5: MOCK DE DADOS
# ====================================================
@st.cache_data(show_spinner=False)
def gerar_dados_teste() -> pd.DataFrame:
    import numpy as np

    datas = pd.date_range(start="2023-10-01", periods=15, freq="D").tolist() * 3
    tecnicos = ["JOAO SILVA", "MARIA SOUZA", "CARLOS ALBERTO"] * 15
    return pd.DataFrame(
        {
            "Data": datas,
            "Técnico": tecnicos,
            "Supervisor": ["SUP A", "SUP B", "SUP A"] * 15,
            "Base": ["SÃO PAULO", "SÃO PAULO", "CAMPINAS"] * 15,
            "Pontos": np.random.uniform(10.5, 50.8, size=45),
            "Status": ["CONCLUÍDO"] * 45,
        }
    )


@st.cache_data(show_spinner=False)
def preparar_base_cache(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Pontos" in df.columns:
        df["Pontos"] = pd.to_numeric(df["Pontos"], errors="coerce").fillna(0.0)
    return df


# ====================================================
# BLOCO 6: INICIALIZAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(page_title="Raio-X do Técnico", page_icon="🔍", layout="wide")

# ── Design system global (fontes, Plotly, CSS corporativo) ──
aplicar_estilo()

# ── CSS exclusivo desta página (apenas tooltip) ──
_injetar_css_tooltip()

# ── Hero corporativo via componentes.py ──
render_hero(
    titulo="🔍 Raio-X: Desempenho Operacional",
    subtitulo="Auditoria detalhada de Execução Física (O.S. e Pontuação) por técnico/equipe",
    badge="Produção de Campo",
)

# ====================================================
# BLOCO 7: CARREGAMENTO DA BASE
# ====================================================
df_prod = pd.DataFrame()

if "dados_prod" in st.session_state:
    try:
        p1 = st.session_state["dados_prod"].get("Prod", pd.DataFrame())
        p2 = st.session_state["dados_prod"].get("Gpon", pd.DataFrame())
        if not p1.empty and not p2.empty:
            df_prod = pd.concat([p1, p2], ignore_index=True)
        elif not p1.empty:
            df_prod = p1.copy()
        elif not p2.empty:
            df_prod = p2.copy()
    except Exception:
        pass

if df_prod.empty:
    render_insight(
        "Base de Produção não encontrada. Carregando dados de demonstração.", "alerta"
    )
    df_prod = gerar_dados_teste()

df_prod = preparar_base_cache(df_prod)

# Identificação de colunas
col_tec = Utilitarios.buscar_coluna(
    df_prod, ["TÉCNICO", "TECNICO", "VENDEDOR", "NOME EQUIPE", "NOME", "LOGIN"]
)
col_sup = Utilitarios.buscar_coluna(
    df_prod, ["SUPERVISOR", "MONITOR", "GESTOR", "COORDENADOR", "LÍDER", "LIDER"]
)
col_base = Utilitarios.buscar_coluna(
    df_prod, ["BASE", "PROJETO", "CIDADE", "FILIAL", "LOCALIDADE"]
)
col_data = Utilitarios.buscar_coluna(
    df_prod, ["DATA", "DATA AGENDAMENTO", "DATA CONCLUSÃO", "DATA_EXECUCAO", "DATE"]
)

if not col_tec:
    render_insight(
        "Não foi possível encontrar a coluna de Técnico/Equipe na base de dados.",
        "critico",
    )
    st.stop()

df_prod[col_tec] = df_prod[col_tec].astype(str).str.strip().str.upper()

if col_data:
    df_prod[col_data] = pd.to_datetime(df_prod[col_data], errors="coerce").dt.date

# ====================================================
# BLOCO 8: MOTOR DE BUSCA EM CASCATA
# ====================================================
with st.container(border=True):
    render_section_header("🎯", "Localizar Técnico / Equipe")

    f_data, f_base, f_sup = st.columns([1.5, 1, 1])
    mask = pd.Series(True, index=df_prod.index)

    # ── Filtro de período ──
    with f_data:
        if col_data and not df_prod[col_data].dropna().empty:
            min_date = df_prod[col_data].min()
            max_date = df_prod[col_data].max()

            datas_sel = st.date_input(
                "📅 Período:",
                [min_date, max_date],
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY",
            )
            if len(datas_sel) == 2:
                mask &= (df_prod[col_data] >= datas_sel[0]) & (
                    df_prod[col_data] <= datas_sel[1]
                )
        else:
            render_insight("Sem coluna de data detectada na base.", "info")

    # ── Filtro de base ──
    with f_base:
        base_sel = "Todas"
        if col_base:
            bases = ["Todas"] + sorted(
                str(b)
                for b in df_prod.loc[mask, col_base].dropna().unique()
                if str(b).strip()
            )
            base_sel = st.selectbox("📍 Base:", bases)
            if base_sel != "Todas":
                mask &= df_prod[col_base] == base_sel

    # ── Filtro de supervisor ──
    with f_sup:
        sup_sel = "Todos"
        if col_sup:
            supervisores = ["Todos"] + sorted(
                str(s)
                for s in df_prod.loc[mask, col_sup].dropna().unique()
                if str(s).strip()
            )
            sup_sel = st.selectbox("👤 Supervisor:", supervisores)
            if sup_sel != "Todos":
                mask &= df_prod[col_sup] == sup_sel

    st.divider()

    tecnicos_filtrados = sorted(
        t for t in df_prod.loc[mask, col_tec].unique() if t and t != "NAN"
    )

    if not tecnicos_filtrados:
        render_insight(
            "Nenhum técnico encontrado para o período/base/supervisor selecionados.",
            "alerta",
        )
        st.stop()

    col_busca, col_info = st.columns([1, 2], gap="large")

    with col_busca:
        tec_selecionado = st.selectbox(
            "🔎 Selecione a Equipe/Técnico:", options=[""] + tecnicos_filtrados
        )

    df_tec_prod = pd.DataFrame()

    if tec_selecionado:
        df_tec_prod = df_prod[(df_prod[col_tec] == tec_selecionado) & mask].copy()

        sup_tec = (
            df_tec_prod[col_sup].mode()[0]
            if col_sup and not df_tec_prod[col_sup].empty
            else "Não Atribuído"
        )
        base_tec = (
            df_tec_prod[col_base].mode()[0]
            if col_base and not df_tec_prod[col_base].empty
            else "Não Atribuída"
        )

        with col_info:
            st.markdown("<br>", unsafe_allow_html=True)
            render_insight(
                f"<b>Supervisor:</b> {sup_tec} &nbsp;|&nbsp; <b>Base/Projeto:</b> {base_tec}",
                "info",
            )


# ====================================================
# BLOCO 9: DASHBOARD OPERACIONAL
# ====================================================
if tec_selecionado and not df_tec_prod.empty:
    st.divider()

    if "Pontos" not in df_tec_prod.columns:
        render_insight("Coluna 'Pontos' não encontrada na base de dados.", "critico")
        st.stop()

    t_pontos = df_tec_prod["Pontos"].sum()
    t_os = len(df_tec_prod)
    pontos_por_os = t_pontos / t_os if t_os > 0 else 0.0
    media_pontos = df_tec_prod["Pontos"].mean()

    # ── KPIs com tooltip ──
    render_section_header("⚙️", f"Execução Física — {tec_selecionado}")

    kr1, kr2, kr3, kr4 = st.columns(4)

    with kr1:
        st.markdown(
            _criar_card_tooltip(
                "O.S. Realizadas",
                str(t_os),
                "cinza",
                "Total de visitas executadas",
                "📋",
                tooltip="Quantidade total de O.S. executadas no período selecionado",
            ),
            unsafe_allow_html=True,
        )
    with kr2:
        st.markdown(
            _criar_card_tooltip(
                "Pontuação Total",
                Utilitarios.formatar_numero(t_pontos),
                "azul",
                "Soma dos pontos",
                "🎯",
                tooltip="Soma de toda a pontuação acumulada no período",
            ),
            unsafe_allow_html=True,
        )
    with kr3:
        st.markdown(
            _criar_card_tooltip(
                "Ticket Médio",
                Utilitarios.formatar_numero(pontos_por_os),
                "roxo",
                "Pts médio por O.S.",
                "🔌",
                tooltip="Média de pontos por cada O.S. executada",
            ),
            unsafe_allow_html=True,
        )
    with kr4:
        st.markdown(
            _criar_card_tooltip(
                "Média por O.S.",
                Utilitarios.formatar_numero(media_pontos),
                "verde",
                "Pontos por visita",
                "📊",
                tooltip="Média aritmética de pontos por visita",
            ),
            unsafe_allow_html=True,
        )

    st.write("---")

    # ── Gráfico de evolução diária ──
    if col_data:
        render_section_header("📊", "Evolução Diária — Volume vs Qualidade")
        df_grafico = df_tec_prod.dropna(subset=[col_data]).copy()

        if not df_grafico.empty:
            df_tempo = (
                df_grafico.groupby(col_data)
                .agg(Pontos=("Pontos", "sum"), Qtd_OS=("Pontos", "count"))
                .reset_index()
            )
            st.plotly_chart(
                Graficos.grafico_combo_raiox(df_tempo, col_data, "Qtd_OS", "Pontos"),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        else:
            render_insight(
                "Nenhuma data válida encontrada para exibir o gráfico.", "alerta"
            )
    else:
        render_insight("Coluna de data não disponível para plotar o gráfico.", "alerta")

    st.write("---")

    # ── Tabela de extrato ──
    render_section_header("🧾", "Extrato Operacional Detalhado")

    col_ignorar = {
        "lat",
        "lon",
        "latitude",
        "longitude",
        "Posição",
        "Cidade",
        "Unnamed: 0",
    }
    colunas_exib = [c for c in df_tec_prod.columns if c not in col_ignorar]
    df_exibir = df_tec_prod[colunas_exib].copy()

    if col_data:
        df_exibir = df_exibir.sort_values(by=col_data, ascending=False)

    config_cols = {}

    if "Pontos" in df_exibir.columns:
        config_cols["Pontos"] = st.column_config.NumberColumn(
            "🎯 Pontos", format="%.2f", help="Pontuação obtida nesta O.S."
        )
    if col_data and col_data in df_exibir.columns:
        config_cols[col_data] = st.column_config.DateColumn(
            "📅 Data", format="DD/MM/YYYY", help="Data de execução da O.S."
        )
    if col_tec and col_tec in df_exibir.columns:
        config_cols[col_tec] = st.column_config.TextColumn("👤 Técnico")
    if col_sup and col_sup in df_exibir.columns:
        config_cols[col_sup] = st.column_config.TextColumn("👔 Supervisor")
    if col_base and col_base in df_exibir.columns:
        config_cols[col_base] = st.column_config.TextColumn("📍 Base/Projeto")

    st.dataframe(
        df_exibir,
        use_container_width=True,
        hide_index=True,
        column_config=config_cols,
    )

    # ── Download + métricas de resumo ──
    if not df_exibir.empty:
        st.download_button(
            label="📥 Baixar Extrato Operacional",
            data=Utilitarios.formatar_dataframe_para_download(df_exibir),
            file_name=f"extrato_operacional_{tec_selecionado.replace(' ', '_')}.csv",
            mime="text/csv",
            type="primary",
        )

        st.write("")
        col_met1, col_met2, col_met3 = st.columns(3)

        with col_met1:
            st.metric(
                "📅 Período",
                (
                    f"{df_exibir[col_data].min()} → {df_exibir[col_data].max()}"
                    if col_data
                    else "N/A"
                ),
            )
        if col_data and "Pontos" in df_exibir.columns:

            df_exec = df_exibir.copy()

            # Garante datetime robusto
            df_exec[col_data] = pd.to_datetime(
                df_exec[col_data],
                errors="coerce"
            )

            # Remove datas inválidas
            df_exec = df_exec.dropna(subset=[col_data])

            if not df_exec.empty:

                # ── Consolidação diária ──
                df_resumo_dia = (
                    df_exec
                    .groupby(col_data)["Pontos"]
                    .sum()
                    .reset_index()
                    .sort_values(col_data)
                )

                # Melhor e pior dia
                max_val = df_resumo_dia["Pontos"].max()
                min_val = df_resumo_dia["Pontos"].min()

                melhores_dias = df_resumo_dia[df_resumo_dia["Pontos"] == max_val]
                piores_dias = df_resumo_dia[df_resumo_dia["Pontos"] == min_val]

                # Seleciona o primeiro em caso de empate
                dia_max = pd.to_datetime(melhores_dias.iloc[0][col_data])
                dia_min = pd.to_datetime(piores_dias.iloc[0][col_data])

                # Indicadores estratégicos
                gap_absoluto = max_val - min_val
                variacao_percentual = ((max_val - min_val) / min_val * 100) if min_val > 0 else 0

                # ── MÉTRICAS EXECUTIVAS ──
                with col_met2:
                    st.metric(
                        "📈 Pico de Performance",
                        dia_max.strftime("%d/%m/%Y"),
                        f"{Utilitarios.formatar_numero(max_val)} pts",
                    )

                with col_met3:
                    st.metric(
                        "📉 Vale Operacional",
                        dia_min.strftime("%d/%m/%Y"),
                        f"{Utilitarios.formatar_numero(min_val)} pts",
                    )

                # ── Linha estratégica adicional ──
                st.write("")
                col_gap1, col_gap2 = st.columns(2)

                with col_gap1:
                    st.metric(
                        "📊 Gap de Produtividade",
                        Utilitarios.formatar_numero(gap_absoluto),
                        "Diferença entre melhor e pior dia",
                    )

                with col_gap2:
                    delta_cor = "normal"
                    st.metric(
                        "🚀 Variação Percentual",
                        f"{Utilitarios.formatar_numero(variacao_percentual)}%",
                        "Oscilação entre extremos do período",
                        delta_color=delta_cor,
                    )

            else:
                render_insight("Sem dados válidos para análise executiva diária.", "alerta")