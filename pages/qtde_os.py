"""
Central de Performance | Qtde. de O.S.
Arquivo: pages/producao.py
"""

from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_hero_totale_2,
    render_kpi,
    render_insight,
    render_section_header,
    render_table_html,
    FONTE_TEXTO,
    FONTE_TITULO,
    COR_PRIMARIA,
    COR_TEXTO_3,
)

# ====================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ====================================================
try:
    st.set_page_config(
        page_title="Central de Performance | O.S.",
        page_icon="⚡",
        layout="wide",
    )
except Exception:
    pass

aplicar_estilo()

# CSS local: cores de O.S., projeção e faixas (sobre a corp-table)
st.markdown(
    f"""
    <style>
    .corp-table thead th {{
        background: linear-gradient(180deg, #012869 0%, #1E40AF 100%) !important;
        color: #FFFFFF !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        font-size: 11px !important;
    }}
    .corp-table td.col-os {{
        background: #F8FAFC !important;
        color: #334155 !important;
        font-weight: 700 !important;
        text-align: right !important;
    }}
    .corp-table td.col-proj {{
        background: #334155 !important;
        color: #FFFFFF !important;
        font-weight: 800 !important;
        text-align: right !important;
    }}
    .corp-table td.faixa-f3 {{
        background: #DCFCE7 !important;
        color: #166534 !important;
        font-weight: 700 !important;
        text-align: center !important;
        border-radius: 6px;
    }}
    .corp-table td.faixa-f2 {{
        background: #DBEAFE !important;
        color: #1E40AF !important;
        font-weight: 700 !important;
        text-align: center !important;
        border-radius: 6px;
    }}
    .corp-table td.faixa-f1 {{
        background: #FEF3C7 !important;
        color: #B45309 !important;
        font-weight: 700 !important;
        text-align: center !important;
        border-radius: 6px;
    }}
    .corp-table td.faixa-baixa {{
        background: #FEE2E2 !important;
        color: #991B1B !important;
        font-weight: 700 !important;
        text-align: center !important;
        border-radius: 6px;
    }}
    .corp-table td.num {{
        text-align: right !important;
        font-variant-numeric: tabular-nums !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ====================================================
# 2. HELPERS DE FAIXA + TABELA COLORIDA
# ====================================================
def _safe_float(v: Any) -> float:
    try:
        if pd.isna(v):
            return float("-inf")
        return float(v)
    except (ValueError, TypeError):
        return float("-inf")


def definir_faixa_supervisor(qtd: Any) -> str:
    """Classifica OS do supervisor: F3≥3500, F2≥3000, F1≥2500."""
    try:
        q = float(qtd)
    except (ValueError, TypeError):
        return "—"
    if q >= 3500:
        return "F3 🌟"
    if q >= 3000:
        return "F2 ✅"
    if q >= 2500:
        return "F1 ⚠️"
    return "< 2500 ❌"


def definir_faixa_projeto(qtd: Any) -> str:
    """Classifica OS do projeto: F3≥11000, F2≥10000, F1≥9000."""
    try:
        q = float(qtd)
    except (ValueError, TypeError):
        return "—"
    if q >= 11000:
        return "F3 🌟"
    if q >= 10000:
        return "F2 ✅"
    if q >= 9000:
        return "F1 ⚠️"
    return "< 9000 ❌"


def _classe_faixa(valor: Any) -> str:
    s = str(valor)
    if "F3" in s:
        return "faixa-f3"
    if "F2" in s:
        return "faixa-f2"
    if "F1" in s:
        return "faixa-f1"
    if s not in ("—", "", "nan"):
        return "faixa-baixa"
    return ""


def render_tabela_os(
    df: pd.DataFrame,
    *,
    height: int = 360,
    max_rows: int = 200,
    col_os: str = "Qtde. de O.S.",
    col_proj: str = "Projeção",
    col_faixa: str = "Faixa",
) -> None:
    """
    Tabela HTML corporativa com:
    - fontes Plus Jakarta / IBM Plex
    - O.S. cinza destacado
    - Projeção fundo escuro
    - Faixa colorida (F1/F2/F3)
    """
    if df is None or df.empty:
        render_insight("Nenhum dado disponível.", "info")
        return

    df_show = df.head(max_rows).copy()
    cols = list(df_show.columns)

    # Formatação numérica
    def _fmt(val: Any, col: str) -> str:
        if pd.isna(val):
            return "—"
        if col in (col_os, col_proj) or col.startswith("Meta"):
            try:
                return f"{float(val):,.0f}".replace(",", ".")
            except (ValueError, TypeError):
                return str(val)
        return str(val)

    def _cls(val: Any, col: str) -> str:
        classes: list[str] = []
        if col == col_os:
            classes.append("col-os")
            classes.append("num")
        elif col == col_proj:
            classes.append("col-proj")
            classes.append("num")
        elif col == col_faixa:
            classes.append(_classe_faixa(val))
        elif col.startswith("Meta"):
            classes.append("num")
        return " ".join(c for c in classes if c)

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
    <div class="corp-table-wrap" style="max-height:{int(height)}px;">
      <table class="corp-table">
        <thead><tr>{header}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    if len(df) > max_rows:
        st.caption(f"Exibindo {max_rows} de {len(df)} linhas.")


# ====================================================
# 3. CÁLCULO DE CALENDÁRIO
# ====================================================
@dataclass
class InfoCalendario:
    """Informações de dias úteis (Seg–Sáb) do mês de referência."""

    ano: int
    mes: int
    data_ref: datetime.date
    total_dias_uteis: int
    dias_passados: int
    dias_faltantes: int

    @classmethod
    def calcular(
        cls, data_referencia: Optional[datetime.date] = None
    ) -> "InfoCalendario":
        data_ref = data_referencia or datetime.date.today()
        ano, mes = data_ref.year, data_ref.month
        _, ultimo_dia_num = calendar.monthrange(ano, mes)

        primeiro = np.datetime64(datetime.date(ano, mes, 1))
        ultimo = np.datetime64(datetime.date(ano, mes, ultimo_dia_num))
        ref = np.datetime64(data_ref)

        mask = "1111110"  # Seg a Sáb
        total = int(
            np.busday_count(primeiro, ultimo + np.timedelta64(1, "D"), weekmask=mask)
        )
        passados = int(
            np.busday_count(primeiro, ref + np.timedelta64(1, "D"), weekmask=mask)
        )
        faltantes = max(0, total - passados)

        return cls(
            ano=ano,
            mes=mes,
            data_ref=data_ref,
            total_dias_uteis=total,
            dias_passados=passados,
            dias_faltantes=faltantes,
        )


# ====================================================
# 4. PROCESSAMENTO DE DADOS
# ====================================================
class ProcessadorDados:
    """Carrega, valida e processa o DataFrame de produção."""

    COL_DATA = "Data Agendamento"
    COL_OS = "OS"
    COL_SUPERVISOR = "Supervisor"
    COL_PROJETO = "Projeto"
    COL_TECNICO = "Nome Equipe"
    COL_COD_TEC = "CódAuxEquipe"

    def __init__(self, df: pd.DataFrame):
        self.df_original = df.copy()
        self.df = df.copy()
        self._preparar()

    def _preparar(self) -> None:
        if self.COL_DATA in self.df.columns:
            self.df[self.COL_DATA] = pd.to_datetime(
                self.df[self.COL_DATA], errors="coerce"
            )

    @property
    def total_geral(self) -> int:
        return len(self.df_original)

    @property
    def total_filtrado(self) -> int:
        return len(self.df)

    @property
    def qtd_projetos(self) -> int:
        if self.COL_PROJETO not in self.df.columns:
            return 0
        return int(self.df[self.COL_PROJETO].nunique())

    @property
    def qtd_supervisores(self) -> int:
        if self.COL_SUPERVISOR not in self.df.columns:
            return 0
        return int(self.df[self.COL_SUPERVISOR].nunique())

    @property
    def ultima_atualizacao(self) -> Optional[pd.Timestamp]:
        if self.COL_DATA in self.df.columns and not self.df.empty:
            return self.df[self.COL_DATA].max()
        return None

    def filtrar(self, coluna: str, valor: Optional[str]) -> None:
        if valor != "Todos" and coluna in self.df.columns:
            self.df = self.df[self.df[coluna] == valor]

    def opcoes_filtro(self, coluna: str) -> list:
        if coluna not in self.df.columns:
            return ["Todos"]
        return ["Todos"] + sorted(self.df[coluna].dropna().astype(str).unique())

    def media_diaria(self, grupo: str) -> pd.Series:
        if (
            self.COL_DATA not in self.df.columns
            or grupo not in self.df.columns
            or self.df.empty
        ):
            return pd.Series(dtype=float)

        return (
            self.df.groupby([grupo, self.COL_DATA])[self.COL_OS]
            .count()
            .groupby(grupo)
            .mean()
        )

    def tabela_supervisor(self, dias_faltantes: int) -> pd.DataFrame:
        if self.COL_SUPERVISOR not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        qtde = (
            self.df.groupby(self.COL_SUPERVISOR)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
        )

        media = (
            qtde[self.COL_SUPERVISOR]
            .map(self.media_diaria(self.COL_SUPERVISOR))
            .fillna(0.0)
            .astype(float)
        )
        qtde["Qtde. de O.S."] = pd.to_numeric(
            qtde["Qtde. de O.S."], errors="coerce"
        ).fillna(0.0)

        qtde["Faixa"] = qtde["Qtde. de O.S."].map(definir_faixa_supervisor)
        qtde["Meta | 2500"] = qtde["Qtde. de O.S."] - 2500
        qtde["Meta | 3000"] = qtde["Qtde. de O.S."] - 3000
        qtde["Meta | 3500"] = qtde["Qtde. de O.S."] - 3500
        # .div evita TypeError Series[Any] / int
        qtde["Projeção"] = (
            (qtde["Qtde. de O.S."] + media.mul(float(dias_faltantes)))
            .round(0)
            .astype(int)
        )

        # Ordem amigável
        cols = [
            self.COL_SUPERVISOR,
            "Qtde. de O.S.",
            "Faixa",
            "Meta | 2500",
            "Meta | 3000",
            "Meta | 3500",
            "Projeção",
        ]
        return qtde[cols].sort_values("Qtde. de O.S.", ascending=False)

    def tabela_projeto(self, dias_faltantes: int) -> pd.DataFrame:
        if self.COL_PROJETO not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        qtde = (
            self.df.groupby(self.COL_PROJETO)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
        )

        media = (
            qtde[self.COL_PROJETO]
            .map(self.media_diaria(self.COL_PROJETO))
            .fillna(0.0)
            .astype(float)
        )
        qtde["Qtde. de O.S."] = pd.to_numeric(
            qtde["Qtde. de O.S."], errors="coerce"
        ).fillna(0.0)

        qtde["Faixa"] = qtde["Qtde. de O.S."].map(definir_faixa_projeto)
        qtde["Meta | 9000"] = qtde["Qtde. de O.S."] - 9000
        qtde["Meta | 10000"] = qtde["Qtde. de O.S."] - 10000
        qtde["Meta | 11000"] = qtde["Qtde. de O.S."] - 11000
        qtde["Projeção"] = (
            (qtde["Qtde. de O.S."] + media.mul(float(dias_faltantes)))
            .round(0)
            .astype(int)
        )

        cols = [
            self.COL_PROJETO,
            "Qtde. de O.S.",
            "Faixa",
            "Meta | 9000",
            "Meta | 10000",
            "Meta | 11000",
            "Projeção",
        ]
        return qtde[cols].sort_values("Qtde. de O.S.", ascending=False)

    def tabela_tecnico(self) -> pd.DataFrame:
        cols_necessarias = [
            self.COL_COD_TEC,
            self.COL_TECNICO,
            self.COL_SUPERVISOR,
            self.COL_PROJETO,
        ]
        if not all(c in self.df.columns for c in cols_necessarias) or self.df.empty:
            return pd.DataFrame()

        return (
            self.df.groupby(cols_necessarias)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
            .sort_values("Qtde. de O.S.", ascending=False)
        )

    def tendencia_diaria(self) -> pd.DataFrame:
        if self.COL_DATA not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        return (
            self.df.groupby(self.df[self.COL_DATA].dt.date)[self.COL_OS]
            .count()
            .reset_index()
            .rename(columns={self.COL_DATA: "Data", self.COL_OS: "Quantidade"})
        )


# ====================================================
# 5. COMPONENTES VISUAIS
# ====================================================
class Componentes:
    """Renderiza seções visuais do dashboard."""

    @staticmethod
    def kpis(proc: ProcessadorDados) -> None:
        c1, c2, c3, c4 = st.columns(4)
        render_kpi(
            c1,
            "Total O.S. (Geral)",
            f"{proc.total_geral:,}".replace(",", "."),
            tema="cinza",
        )
        render_kpi(
            c2,
            "Total O.S. (Filtrado)",
            f"{proc.total_filtrado:,}".replace(",", "."),
            tema="azul",
        )
        render_kpi(c3, "Projetos Ativos", str(proc.qtd_projetos), tema="laranja")
        render_kpi(c4, "Supervisores Ativos", str(proc.qtd_supervisores), tema="verde")

    @staticmethod
    def grafico_tendencia(df_tend: pd.DataFrame) -> None:
        render_section_header("📈", "Evolução Diária de O.S.")

        if df_tend.empty:
            render_insight("Sem dados de **Data Agendamento** para tendência.", "info")
            return

        fig = px.area(
            df_tend,
            x="Data",
            y="Quantidade",
            markers=True,
            color_discrete_sequence=["#F97316"],
        )
        fig.update_layout(
            xaxis_title="",
            yaxis_title="",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            font=dict(family=FONTE_TEXTO),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    @staticmethod
    def visao_supervisor(df_sup: pd.DataFrame) -> None:
        render_section_header("👨‍💼", "Visão por Supervisor")

        if df_sup.empty:
            render_insight("Sem dados de Supervisor.", "info")
            return

        render_tabela_os(df_sup, height=380)

        # Legenda de faixas
        st.markdown(
            f"""
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;
                 font-family:{FONTE_TEXTO};font-size:0.75rem;">
              <span style="background:#DCFCE7;color:#166534;padding:3px 10px;
                   border-radius:6px;font-weight:700;">F3 ≥ 3500</span>
              <span style="background:#DBEAFE;color:#1E40AF;padding:3px 10px;
                   border-radius:6px;font-weight:700;">F2 ≥ 3000</span>
              <span style="background:#FEF3C7;color:#B45309;padding:3px 10px;
                   border-radius:6px;font-weight:700;">F1 ≥ 2500</span>
              <span style="background:#FEE2E2;color:#991B1B;padding:3px 10px;
                   border-radius:6px;font-weight:700;">&lt; 2500</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def visao_projeto(df_proj: pd.DataFrame) -> None:
        render_section_header("💼", "Visão por Projeto")

        if df_proj.empty:
            render_insight("Sem dados de Projeto.", "info")
            return

        tab_tabela, tab_grafico = st.tabs(["📋 Tabela", "🍩 Gráfico de Share"])

        with tab_tabela:
            render_tabela_os(df_proj, height=380)
            st.markdown(
                f"""
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;
                     font-family:{FONTE_TEXTO};font-size:0.75rem;">
                  <span style="background:#DCFCE7;color:#166534;padding:3px 10px;
                       border-radius:6px;font-weight:700;">F3 ≥ 11000</span>
                  <span style="background:#DBEAFE;color:#1E40AF;padding:3px 10px;
                       border-radius:6px;font-weight:700;">F2 ≥ 10000</span>
                  <span style="background:#FEF3C7;color:#B45309;padding:3px 10px;
                       border-radius:6px;font-weight:700;">F1 ≥ 9000</span>
                  <span style="background:#FEE2E2;color:#991B1B;padding:3px 10px;
                       border-radius:6px;font-weight:700;">&lt; 9000</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with tab_grafico:
            fig = px.pie(
                df_proj,
                values="Qtde. de O.S.",
                names="Projeto",
                hole=0.6,
                color_discrete_sequence=px.colors.sequential.Tealgrn_r,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(
                showlegend=False,
                margin=dict(t=0, b=0, l=0, r=0),
                height=350,
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family=FONTE_TEXTO),
            )
            st.plotly_chart(
                fig, use_container_width=True, config={"displayModeBar": False}
            )

    @staticmethod
    def performance_tecnicos(df_tec: pd.DataFrame) -> None:
        render_section_header("👷", "Performance de Técnicos")

        if df_tec.empty:
            render_insight("Sem dados de Técnicos para exibir.", "info")
            return

        col_tab, col_chart = st.columns([1.5, 1])

        with col_tab:
            st.markdown(
                f'<div style="font-family:{FONTE_TITULO};font-weight:700;'
                f'font-size:14px;color:{COR_PRIMARIA};margin-bottom:8px;">'
                f"📋 Tabela Geral de Técnicos</div>",
                unsafe_allow_html=True,
            )
            # Técnicos: só coluna O.S. colorida (sem faixa/projeção)
            render_tabela_os(df_tec, height=450, max_rows=150)

        with col_chart:
            st.markdown(
                f'<div style="font-family:{FONTE_TITULO};font-weight:700;'
                f'font-size:14px;color:{COR_PRIMARIA};margin-bottom:8px;">'
                f"🏆 Top 10 Técnicos</div>",
                unsafe_allow_html=True,
            )
            top10 = df_tec.head(10).sort_values("Qtde. de O.S.", ascending=True)

            fig = px.bar(
                top10,
                x="Qtde. de O.S.",
                y="Nome Equipe",
                orientation="h",
                text="Qtde. de O.S.",
                color="Qtde. de O.S.",
                color_continuous_scale="Oranges",
                range_color=[
                    top10["Qtde. de O.S."].min(),
                    top10["Qtde. de O.S."].max(),
                ],
            )
            fig.update_layout(
                xaxis_title="",
                yaxis_title="",
                coloraxis_showscale=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=0, b=0),
                height=450,
                font=dict(family=FONTE_TEXTO),
            )
            st.plotly_chart(
                fig, use_container_width=True, config={"displayModeBar": False}
            )

    @staticmethod
    def rodape(ultima_atualizacao: Optional[pd.Timestamp]) -> None:
        st.divider()
        if ultima_atualizacao is not None and pd.notna(ultima_atualizacao):
            st.sidebar.divider()
            st.sidebar.caption(
                f"🕒 **Última Atualização:**\n"
                f"{pd.to_datetime(ultima_atualizacao).strftime('%d/%m/%Y')}"
            )


# ====================================================
# 6. APLICAÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    render_hero_totale_2(
        titulo="⚡ Central de Performance | Qtde. de O.S.",
        subtitulo=(
            "Volumetria operacional, projeções de fechamento "
            "e metas por supervisor e projeto"
        ),
        badge_texto="Acompanhamento em tempo real da quantidade de O.S. executadas por supervisores e projetos",
        badge_tipo="info"
    )

    if "dados_prod" not in st.session_state:
        render_insight("Carregue os dados na página principal primeiro.", "alerta")
        st.stop()

    dados_prod = st.session_state.get("dados_prod", {})
    if not isinstance(dados_prod, dict) or "Prod" not in dados_prod:
        render_insight("Aba **Prod** não encontrada na base de dados.", "critico")
        st.stop()

    df_raw = dados_prod["Prod"].copy()
    if not isinstance(df_raw, pd.DataFrame) or df_raw.empty:
        render_insight("Base de Produção vazia.", "alerta")
        st.stop()

    proc = ProcessadorDados(df_raw)

    # ── Filtros ──
    st.sidebar.header("🎯 Filtros Avançados")

    proj_sel = st.sidebar.selectbox(
        "Filtrar por Projeto:",
        proc.opcoes_filtro(ProcessadorDados.COL_PROJETO),
    )
    proc.filtrar(ProcessadorDados.COL_PROJETO, proj_sel)

    # Opções de supervisor recalculadas após filtro de projeto
    sup_sel = st.sidebar.selectbox(
        "Filtrar por Supervisor:",
        proc.opcoes_filtro(ProcessadorDados.COL_SUPERVISOR),
    )
    proc.filtrar(ProcessadorDados.COL_SUPERVISOR, sup_sel)

    if st.sidebar.button("🔄 Limpar Filtros"):
        st.rerun()

    # ── Calendário ──
    data_ref = (
        proc.ultima_atualizacao.date()
        if proc.ultima_atualizacao is not None and pd.notna(proc.ultima_atualizacao)
        else None
    )
    cal = InfoCalendario.calcular(data_ref)

    render_insight(
        f"Período: **{cal.data_ref.strftime('%m/%Y')}** · "
        f"Dias úteis: **{cal.dias_passados}/{cal.total_dias_uteis}** · "
        f"Restam **{cal.dias_faltantes}** dia(s) útil(is).",
        "info",
    )

    # ── KPIs ──
    Componentes.kpis(proc)
    st.divider()

    # ── Tendência ──
    Componentes.grafico_tendencia(proc.tendencia_diaria())
    st.divider()

    # ── Supervisor × Projeto ──
    col_esq, col_dir = st.columns(2)
    with col_esq:
        Componentes.visao_supervisor(proc.tabela_supervisor(cal.dias_faltantes))
    with col_dir:
        Componentes.visao_projeto(proc.tabela_projeto(cal.dias_faltantes))

    st.divider()

    # ── Técnicos ──
    Componentes.performance_tecnicos(proc.tabela_tecnico())

    # ── Rodapé ──
    Componentes.rodape(proc.ultima_atualizacao)


if __name__ == "__main__":
    main()
