"""components/dashboard_kit.py
=============================
Kit de Dashboards Aprimorados — Design System TOTALE (camada v2).

Versão: 1.0.0
Autor: TOTALE Tecnologia

Camada complementar ao ``components/componentes.py`` pensada para elevar o
padrão de todos os dashboards do portal sem duplicar código nas páginas:

• ``css_dashboards`` / ``injetar_css_dashboards``: microinterações de hover
  nos cards de KPI, moldura elegante nos gráficos Plotly, abas, expansores,
  tabelas e barras de rolagem refinadas — aplicado globalmente pelo
  entrypoint, valendo para todas as páginas de uma vez só.
• ``calcular_variacao_pct`` / ``rotulo_tendencia``: deltas percentuais no
  padrão pt-BR já com a direção (up/down/neutral) usada pelos KPIs.
• ``render_kpi_grid``: fileira declarativa de KPIs (menos código repetido).
• ``aplicar_tema_figura`` + fábricas de gráficos Plotly com identidade
  TOTALE: ranking em barras, linha de tendência com média móvel, donut e
  gauge de atingimento de meta.
• ``render_filtros_dashboard``: barra de filtros dinâmicos persistentes com
  botão de limpeza e contagem de registros exibidos.
• ``render_barra_exportacao``: exportação CSV + Excel (xlsxwriter) com
  cabeçalho corporativo, congelamento de linha e larguras automáticas.
• ``render_insights_automaticos``: insights textuais derivados da série
  (variação D-1, melhor/pior dia, média móvel e concentração).
• ``render_toggle_autorefresh``: autoatualização opcional do painel usando
  streamlit-autorefresh com degradação graciosa quando indisponível.
"""

from __future__ import annotations

import logging
from collections.abc import Hashable, Mapping, Sequence
from datetime import date, datetime
from typing import Literal, NotRequired, TypedDict, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.componentes import (
    ConfigCores,
    Cores,
    Fontes,
    TemaKPIType,
    TipoTrendType,
    formatar_numero_br,
    injetar_css,
    render_insight,
    render_kpi,
)
from components.kpi_cards import (
    SpecKPIAvancado,
    calcular_variacao_pct,
    render_kpi_row,
    rotulo_tendencia,
)

logger = logging.getLogger(__name__)

VERSAO_KIT = "1.0.0"

_CHAVE_PREFIXO = "totale_dashkit"

# ====================================================
# 🎨 BLOCO 1: CSS GLOBAL DOS DASHBOARDS (APLICADO PELO ENTRYPOINT)
# ====================================================


def css_dashboards() -> str:
    """CSS v2 dos dashboards: microinterações e acabamento de alto padrão.

    Todas as regras são escopadas em ``[data-testid="stMain"]`` para nunca
    interferir na sidebar, cujo tema é controlado por ``components.sidebar``.
    O CSS é centralizado aqui — páginas não devem repetir esses seletores.
    """
    return f"""
    /* ============================================================
       DASHBOARD KIT v{VERSAO_KIT} — acabamento global dos dashboards
       ============================================================ */

    /* Cards de KPI: elevação suave no hover */
    [data-testid="stMain"] .card-premium {{
        will-change: transform, box-shadow;
        transition: transform .22s ease, box-shadow .22s ease;
    }}
    [data-testid="stMain"] .card-premium:hover {{
        transform: translateY(-3px);
        box-shadow: 0 16px 34px rgba(1, 40, 105, 0.16);
    }}
    [data-testid="stMain"] .card-premium .kpi-icon-wrapper {{
        transition: transform .22s ease;
    }}
    [data-testid="stMain"] .card-premium:hover .kpi-icon-wrapper {{
        transform: scale(1.08) rotate(-3deg);
    }}

    /* Gráficos Plotly: moldura de cartão com respiro */
    [data-testid="stMain"] [data-testid="stPlotlyChart"] {{
        background: #FFFFFF;
        border: 1px solid {Cores.BORDA};
        border-radius: 16px;
        padding: 10px 12px 6px;
        box-shadow: 0 3px 12px rgba(15, 23, 42, 0.05);
        transition: box-shadow .22s ease;
    }}
    [data-testid="stMain"] [data-testid="stPlotlyChart"]:hover {{
        box-shadow: 0 10px 26px rgba(1, 40, 105, 0.10);
    }}

    /* st.metric: visual de cartão consistente com os KPIs */
    [data-testid="stMain"] [data-testid="stMetric"] {{
        background: #FFFFFF;
        border: 1px solid {Cores.BORDA};
        border-top: 3px solid {Cores.PRIMARIA};
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 3px 12px rgba(15, 23, 42, 0.05);
    }}
    [data-testid="stMain"] [data-testid="stMetric"]:hover {{
        box-shadow: 0 8px 22px rgba(1, 40, 105, 0.10);
    }}

    /* Abas: estilo pill com estado ativo destacado na cor de ação */
    [data-testid="stMain"] [data-testid="stTabs"] [data-baseweb="tab-list"] {{
        gap: 6px;
        border-bottom: 2px solid {Cores.BORDA};
    }}
    [data-testid="stMain"] [data-testid="stTabs"] [data-baseweb="tab"] {{
        border-radius: 10px 10px 0 0;
        padding: 8px 18px;
        font-weight: 600;
        color: {Cores.TEXTO_3};
        transition: background-color .18s ease, color .18s ease;
    }}
    [data-testid="stMain"] [data-testid="stTabs"] [data-baseweb="tab"]:hover {{
        background: {Cores.AZUL_SUAVE};
        color: {Cores.PRIMARIA};
    }}
    [data-testid="stMain"] [data-testid="stTabs"] [aria-selected="true"] {{
        color: {Cores.PRIMARIA};
        font-weight: 800;
    }}

    /* Expansores: cartão arredondado com sombra leve */
    [data-testid="stMain"] [data-testid="stExpander"] {{
        border: 1px solid {Cores.BORDA};
        border-radius: 14px;
        background: #FFFFFF;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
        overflow: hidden;
    }}
    [data-testid="stMain"] [data-testid="stExpander"] summary {{
        font-weight: 700;
        color: {Cores.PRIMARIA};
        padding: 12px 16px;
    }}
    [data-testid="stMain"] [data-testid="stExpander"] summary:hover {{
        background: {Cores.FUNDO};
    }}

    /* Tabelas e dataframes: cantos arredondados e moldura fina */
    [data-testid="stMain"] [data-testid="stDataFrame"],
    [data-testid="stMain"] [data-testid="stTable"] {{
        border: 1px solid {Cores.BORDA};
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
    }}

    /* Tags dos multiselects na identidade da marca */
    [data-testid="stMain"] span[data-baseweb="tag"] {{
        background-color: {Cores.PRIMARIA} !important;
        border-radius: 6px !important;
    }}
    [data-testid="stMain"] span[data-baseweb="tag"] span {{
        color: #FFFFFF !important;
    }}

    /* Barra de rolagem global fina e discreta */
    [data-testid="stMain"] ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    [data-testid="stMain"] ::-webkit-scrollbar-track {{
        background: {Cores.FUNDO};
        border-radius: 8px;
    }}
    [data-testid="stMain"] ::-webkit-scrollbar-thumb {{
        background: #CBD5E1;
        border-radius: 8px;
    }}
    [data-testid="stMain"] ::-webkit-scrollbar-thumb:hover {{
        background: {Cores.PRIMARIA_LIGHT};
    }}

    /* Acessibilidade: foco visível consistente em toda a página */
    [data-testid="stMain"] :focus-visible {{
        outline: 3px solid rgba(243, 124, 4, 0.45) !important;
        outline-offset: 2px !important;
        border-radius: 6px;
    }}

    /* Insights e estados vazios: entrada suave */
    [data-testid="stMain"] .totale-insight {{
        transition: transform .18s ease;
    }}
    [data-testid="stMain"] .totale-insight:hover {{
        transform: translateX(2px);
    }}
    """


def injetar_css_dashboards(*, container: object | None = None) -> None:
    """Injeta o CSS v2 dos dashboards (idempotente por execução)."""
    injetar_css(css_dashboards(), container)


# ====================================================
# 📐 BLOCO 2: HELPERS DE MÉTRICAS E FORMATAÇÃO
# ====================================================


# A matemática de variação/tendência vive em :mod:`components.kpi_cards`
# (fonte única do portal). Os nomes continuam reexportados daqui para as
# páginas que já importam deste kit: aliases diretos, sem lógica duplicada.


def resumo_periodo(serie: pd.Series) -> dict[str, float | Hashable | None]:
    """Estatísticas de uma série diária: total, média, melhor e pior dia."""
    if serie is None or serie.empty:
        return {"total": None, "media": None, "melhor": None, "pior": None}
    serie_num = pd.to_numeric(serie, errors="coerce").dropna()
    if serie_num.empty:
        return {"total": None, "media": None, "melhor": None, "pior": None}
    return {
        "total": float(serie_num.sum()),
        "media": float(serie_num.mean()),
        "melhor": float(serie_num.max()),
        "dia_melhor": serie_num.idxmax(),
        "pior": float(serie_num.min()),
        "dia_pior": serie_num.idxmin(),
    }


# ====================================================
# 🧱 BLOCO 3: GRID DECLARATIVO DE KPIs
# ====================================================


class SpecKPI(TypedDict):
    """Especificação declarativa de um cartão de KPI (ver ``render_kpi``)."""

    label: str
    valor: str
    sub: NotRequired[str]
    tema: NotRequired[TemaKPIType]
    icone: NotRequired[str]
    delta: NotRequired[str]
    delta_tipo: NotRequired[TipoTrendType]
    colorida: NotRequired[bool]


_CHAVES_AVANCADAS: frozenset[str] = frozenset(
    {"sparkline", "progresso", "meta_rotulo", "ajuda", "tamanho", "rodape", "delta_color"}
)


def render_kpi_grid(
    specs: Sequence[SpecKPI | SpecKPIAvancado],
    *,
    colunas: int | None = None,
    gap: Literal["xxsmall", "xsmall", "small", "medium", "large"] = "small",
) -> None:
    """Renderiza uma fileira de KPIs a partir de especificações declarativas.

    Reduz o boilerplate de ``st.columns`` + ``render_kpi`` repetidos nas
    páginas e garante espaçamento consistente entre os painéis.

    Quando qualquer especificação traz recursos dos cartões avançados
    (``sparkline``, ``progresso``, ``ajuda``, ``rodape``, ``meta_rotulo``,
    ``tamanho`` ou ``delta_color``) a fileira inteira é desenhada por
    :func:`components.kpi_cards.render_kpi_row`; caso contrário o visual
    clássico do Design System é preservado.
    """
    if not specs:
        return
    if any(_CHAVES_AVANCADAS & set(spec) for spec in specs):
        render_kpi_row(cast(Sequence[SpecKPIAvancado], specs), colunas=colunas, gap=gap)
        return
    quantidade = colunas or len(specs)
    grade = st.columns(quantidade, gap=gap)
    for indice, spec in enumerate(specs):
        coluna = grade[indice % quantidade]
        render_kpi(
            coluna,
            label=spec["label"],
            valor=spec["valor"],
            sub=spec.get("sub", ""),
            tema=spec.get("tema", "azul"),
            icone=spec.get("icone", ""),
            delta=spec.get("delta", ""),
            delta_tipo=spec.get("delta_tipo", "none"),
            colorida=spec.get("colorida", True),
        )


# ====================================================
# 📊 BLOCO 4: GRÁFICOS PLOTLY COM IDENTIDADE TOTALE
# ====================================================


def aplicar_tema_figura(
    fig: go.Figure,
    *,
    titulo: str | None = None,
    altura: int | None = None,
    hover_unificado: bool = True,
    legenda_horizontal: bool = True,
) -> go.Figure:
    """Aplica o acabamento TOTALE a qualquer figura Plotly existente.

    Respeita cores e dados já definidos pela página; ajusta apenas tipografia,
    fundo, grade, modo de hover, margens e legenda.
    """
    layout: dict[str, object] = {
        "font": {"family": Fontes.TEXTO, "size": 13, "color": Cores.TEXTO},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "margin": {"t": 52 if titulo else 32, "b": 44, "l": 52, "r": 24},
        "colorway": ConfigCores.PLOTLY_COLORWAY,
        "hoverlabel": {
            "bgcolor": "#FFFFFF",
            "bordercolor": Cores.BORDA,
            "font": {"family": Fontes.TEXTO, "size": 12, "color": Cores.TEXTO},
        },
    }
    if titulo:
        layout["title"] = {
            "text": titulo,
            "font": {"family": Fontes.TITULO, "size": 17, "color": Cores.TEXTO},
            "x": 0.0,
            "xanchor": "left",
        }
    if altura:
        layout["height"] = altura
    if hover_unificado:
        layout["hovermode"] = "x unified"
    if legenda_horizontal:
        layout["legend"] = {
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.22,
            "xanchor": "left",
            "x": 0,
            "bgcolor": "rgba(255,255,255,0.85)",
        }
    fig.update_layout(layout)
    fig.update_xaxes(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0")
    fig.update_yaxes(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0")
    return fig


def grafico_barras_ranking(
    df: pd.DataFrame,
    col_categoria: str,
    col_valor: str,
    *,
    titulo: str = "",
    top: int = 10,
    cor: str = Cores.PRIMARIA,
    altura: int | None = None,
    ascendente: bool = False,
) -> go.Figure:
    """Ranking horizontal de categorias por valor (Top N), pronto para exibir."""
    dados = df[[col_categoria, col_valor]].copy()
    dados[col_valor] = pd.to_numeric(dados[col_valor], errors="coerce").fillna(0.0)
    dados = (
        dados.groupby(col_categoria, as_index=False)
        .agg({col_valor: "sum"})
        .sort_values(by=col_valor, ascending=ascendente)
        .head(top)
        .sort_values(by=col_valor, ascending=True)
    )
    textos = [
        formatar_numero_br(v) if v >= 10 else f"{v:,.1f}".replace(".", ",")
        for v in dados[col_valor]
    ]
    fig = go.Figure(
        go.Bar(
            x=dados[col_valor],
            y=dados[col_categoria].astype(str),
            orientation="h",
            marker={"color": cor, "cornerradius": 6},
            text=textos,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{text}<extra></extra>",
        )
    )
    aplicar_tema_figura(fig, titulo=titulo or None, altura=altura, legenda_horizontal=False)
    fig.update_layout(bargap=0.32)
    fig.update_yaxes(tickfont={"size": 12, "color": Cores.TEXTO_2})
    return fig


def grafico_linha_tendencia(
    serie: pd.Series,
    *,
    titulo: str = "",
    cor: str = Cores.PRIMARIA,
    media_movel: int = 7,
    altura: int | None = None,
    rotulo_serie: str = "Realizado",
) -> go.Figure:
    """Linha de evolução com área suave, média móvel e destaque no último ponto."""
    serie_num = pd.to_numeric(serie, errors="coerce").dropna()
    fig = go.Figure()
    if serie_num.empty:
        aplicar_tema_figura(fig, titulo=titulo or None, altura=altura)
        return fig
    fig.add_trace(
        go.Scatter(
            x=serie_num.index,
            y=serie_num.values,
            name=rotulo_serie,
            mode="lines",
            line={"color": cor, "width": 2.4, "shape": "spline", "smoothing": 0.6},
            fill="tozeroy",
            fillcolor=f"{cor}1A",
            hovertemplate="%{x|%d/%m/%Y}: %{y:,.0f}<extra></extra>",
        )
    )
    if media_movel and len(serie_num) >= media_movel:
        media = serie_num.rolling(media_movel, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=media.index,
                y=media.values,
                name=f"Média móvel ({media_movel}d)",
                mode="lines",
                line={"color": Cores.SECUNDARIA, "width": 2, "dash": "dash"},
                hovertemplate="Média: %{y:,.1f}<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[serie_num.index[-1]],
            y=[serie_num.iloc[-1]],
            name="Último dia",
            mode="markers",
            marker={"size": 11, "color": cor, "line": {"color": "#FFFFFF", "width": 2}},
            showlegend=False,
            hovertemplate="Último: %{y:,.0f}<extra></extra>",
        )
    )
    aplicar_tema_figura(fig, titulo=titulo or None, altura=altura)
    return fig


def grafico_donut(
    rotulos: Sequence[str],
    valores: Sequence[float],
    *,
    titulo: str = "",
    altura: int | None = None,
    exibir_total: bool = True,
) -> go.Figure:
    """Donut com a paleta TOTALE, porcentagens internas e total no centro."""
    total = float(sum(v for v in valores if pd.notna(v)))
    fig = go.Figure(
        go.Pie(
            labels=[str(r) for r in rotulos],
            values=list(valores),
            hole=0.56,
            marker={
                "colors": ConfigCores.PLOTLY_COLORWAY,
                "line": {"color": "#FFFFFF", "width": 2},
            },
            textinfo="label+percent",
            insidetextorientation="radial",
            hovertemplate="%{label}: %{value:,.0f} (%{percent})<extra></extra>",
            sort=False,
        )
    )
    aplicar_tema_figura(fig, titulo=titulo or None, altura=altura, hover_unificado=False)
    if exibir_total and total > 0:
        fig.update_layout(
            annotations=[
                {
                    "text": f"<b>{formatar_numero_br(total)}</b>",
                    "x": 0.5,
                    "y": 0.5,
                    "font": {"family": Fontes.TITULO, "size": 20, "color": Cores.TEXTO},
                    "showarrow": False,
                }
            ]
        )
    return fig


def grafico_gauge_meta(
    valor_pct: float,
    *,
    titulo: str = "",
    meta_pct: float = 100.0,
    faixas: tuple[float, float] = (60.0, 85.0),
    altura: int | None = None,
    valor_rotulo: str | None = None,
) -> go.Figure:
    """Gauge semicircular de atingimento de meta (0–120%+), semáforo por faixas."""
    try:
        pct = max(0.0, float(valor_pct))
    except (TypeError, ValueError, OverflowError):
        pct = 0.0
    faixa1, faixa2 = faixas
    if pct >= meta_pct:
        cor_barra = Cores.SUCESSO
    elif pct >= faixa2:
        cor_barra = Cores.PRIMARIA
    elif pct >= faixa1:
        cor_barra = Cores.SECUNDARIA
    else:
        cor_barra = Cores.ALERTA
    teto = max(120.0, pct * 1.15)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            number={
                "suffix": "%",
                "font": {"family": Fontes.TITULO, "size": 30, "color": Cores.TEXTO},
            },
            title={
                "text": valor_rotulo or titulo,
                "font": {"family": Fontes.TEXTO, "size": 13, "color": Cores.TEXTO_3},
            },
            gauge={
                "axis": {"range": [0, teto], "tickwidth": 1, "tickcolor": Cores.BORDA},
                "bar": {"color": cor_barra, "thickness": 0.28},
                "bgcolor": "#FFFFFF",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, faixa1], "color": "#FEF2F2"},
                    {"range": [faixa1, faixa2], "color": "#FFF7ED"},
                    {"range": [faixa2, meta_pct], "color": "#EFF6FF"},
                    {"range": [meta_pct, teto], "color": "#ECFDF5"},
                ],
                "threshold": {
                    "line": {"color": Cores.SECUNDARIA_DARK, "width": 3},
                    "thickness": 0.75,
                    "value": meta_pct,
                },
            },
        )
    )
    fig.update_layout(
        font={"family": Fontes.TEXTO, "size": 12, "color": Cores.TEXTO_2},
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"t": 44, "b": 8, "l": 24, "r": 24},
        height=altura or 230,
    )
    return fig


# ====================================================
# 🔎 BLOCO 5: FILTROS DINÂMICOS PADRONIZADOS
# ====================================================


def _opcoes_unicas(serie: pd.Series, limite: int = 500) -> list[str]:
    """Valores únicos como texto, ordenados e limitados (proteção de UI)."""
    valores = serie.dropna().astype(str)
    valores = valores[valores.str.strip() != ""]
    unicos = sorted(valores.unique().tolist())
    if len(unicos) > limite:
        logger.warning("Filtro truncado em %d opções (coluna com %d).", limite, len(unicos))
        return unicos[:limite]
    return unicos


def render_filtros_dashboard(
    df: pd.DataFrame,
    colunas: Mapping[str, str],
    *,
    chave: str,
    coluna_data: str | None = None,
    max_por_linha: int = 4,
    mostrar_contagem: bool = True,
) -> pd.DataFrame:
    """Barra de filtros persistentes (multiselect + período) sobre um DataFrame.

    ``colunas`` mapeia ``NOME_COLUNA -> rótulo amigável``. As escolhas ficam
    em ``st.session_state`` sob o prefixo da ``chave`` da página, com botão
    "Limpar filtros". Retorna o DataFrame já filtrado.
    """
    if df is None or df.empty or not colunas and coluna_data is None:
        return df

    chave_base = f"{_CHAVE_PREFIXO}::{chave}"
    colunas_validas = {col: rotulo for col, rotulo in colunas.items() if col in df.columns}
    if not colunas_validas and coluna_data not in (None, *df.columns):
        return df

    total_original = len(df)
    filtrado = df

    itens = list(colunas_validas.items())
    linhas_filtro = [itens[i : i + max_por_linha] for i in range(0, len(itens), max_por_linha)]
    min_data = None
    max_data = None
    if coluna_data is not None and coluna_data in df.columns:
        datas = pd.to_datetime(df[coluna_data], errors="coerce", dayfirst=True)
        if datas.notna().any():
            min_data, max_data = datas.min().date(), datas.max().date()
            if not linhas_filtro or len(linhas_filtro[-1]) >= max_por_linha:
                linhas_filtro.append([])
            linhas_filtro[-1].append(("__periodo__", "Período"))
    else:
        datas = None

    for linha in linhas_filtro:
        controles = st.columns(max_por_linha, gap="small")
        for posicao, (coluna, rotulo) in enumerate(linha):
            with controles[posicao]:
                if coluna == "__periodo__":
                    selecao_data = st.date_input(
                        rotulo,
                        value=(min_data, max_data),  # type: ignore[arg-type]
                        min_value=min_data,  # type: ignore[arg-type]
                        max_value=max_data,  # type: ignore[arg-type]
                        format="DD/MM/YYYY",
                        key=f"{chave_base}::periodo",
                    )
                    if (
                        datas is not None
                        and isinstance(selecao_data, tuple)
                        and len(selecao_data) == 2
                        and all(isinstance(d, date) for d in selecao_data)
                    ):
                        inicio, fim = selecao_data
                        mascara = datas.dt.date.between(inicio, fim)
                        filtrado = filtrado[mascara.fillna(False)]
                else:
                    selecionados = st.multiselect(
                        rotulo,
                        options=_opcoes_unicas(df[coluna]),
                        default=[],
                        placeholder="Todos",
                        key=f"{chave_base}::col::{coluna}",
                    )
                    if selecionados:
                        filtrado = filtrado[filtrado[coluna].astype(str).isin(selecionados)]

    _, coluna_acao = st.columns([5, 1], gap="small")
    with coluna_acao:
        if st.button(
            "🧹 Limpar filtros",
            key=f"{chave_base}::limpar",
            width="stretch",
        ):
            for estado in list(st.session_state):
                if str(estado).startswith(f"{chave_base}::"):
                    del st.session_state[estado]
            st.rerun()

    if mostrar_contagem:
        exibidos = len(filtrado)
        if exibidos != total_original:
            st.caption(
                f"🔎 Exibindo **{formatar_numero_br(exibidos)}** de "
                f"**{formatar_numero_br(total_original)}** registros após os filtros."
            )
    return filtrado


# ====================================================
# 📤 BLOCO 6: EXPORTAÇÃO PADRONIZADA (CSV + EXCEL)
# ====================================================


def gerar_excel_exportacao(df: pd.DataFrame, aba: str = "Dados") -> bytes:
    """XLSX corporativo (delega a :func:`services.planilhas.gerar_excel`).

    Mantido aqui como nome histórico do kit; a implementação única vive em
    :mod:`services.planilhas`, que as páginas também usam diretamente.
    """
    from services.planilhas import gerar_excel

    return gerar_excel(df, aba=aba)


def render_barra_exportacao(
    df: pd.DataFrame,
    *,
    nome_arquivo: str,
    chave: str,
    incluir_excel: bool = True,
    rotulo_secao: str = "Exportar dados",
) -> None:
    """Botões de download CSV (UTF-8-SIG) e Excel formatado para um recorte."""
    if df is None or df.empty:
        st.caption("Nada para exportar no recorte atual.")
        return
    carimbo = datetime.now().strftime("%Y%m%d_%H%M")
    col_txt, col_csv, col_xlsx = st.columns([3, 1, 1], gap="small")
    with col_txt:
        st.caption(
            f"📤 **{rotulo_secao}** — {formatar_numero_br(len(df))} registro(s) no recorte atual."
        )
    with col_csv:
        st.download_button(
            "⬇️ CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{nome_arquivo}_{carimbo}.csv",
            mime="text/csv",
            key=f"{_CHAVE_PREFIXO}::{chave}::csv",
            width="stretch",
        )
    with col_xlsx:
        if incluir_excel:
            try:
                dados_xlsx = gerar_excel_exportacao(df)
            except Exception:  # pragma: no cover - proteção de runtime
                logger.exception("Falha ao gerar Excel para '%s'.", nome_arquivo)
                st.warning("Não foi possível gerar o Excel agora; use o CSV.")
            else:
                st.download_button(
                    "⬇️ Excel",
                    data=dados_xlsx,
                    file_name=f"{nome_arquivo}_{carimbo}.xlsx",
                    mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    key=f"{_CHAVE_PREFIXO}::{chave}::xlsx",
                    width="stretch",
                )


# ====================================================
# 💡 BLOCO 7: INSIGHTS AUTOMÁTICOS SOBRE UMA SÉRIE
# ====================================================


def gerar_insights(
    df: pd.DataFrame,
    *,
    col_data: str | None = None,
    col_valor: str | None = None,
    col_categoria: str | None = None,
    rotulo_unidade: str = "registros",
) -> list[tuple[str, str]]:
    """Gera insights textuais (mensagem, tipo) prontos para ``render_insight``.

    Regras aplicadas: variação contra D-1, posição contra a média móvel de
    7 dias, melhor e pior dia do recorte e concentração da principal
    categoria (Pareto simples) quando ``col_categoria`` é informada.
    """
    from components.metricas_executivas import comparar_periodos, serie_diaria

    insights: list[tuple[str, str]] = []
    serie = serie_diaria(df, data_col=col_data, valor_col=col_valor)
    if serie.empty:
        return insights

    comparacao = comparar_periodos(serie)
    atual, d1 = comparacao.get("atual"), comparacao.get("d1")
    variacao = calcular_variacao_pct(atual, d1)
    if variacao is not None and atual is not None:
        seta = "📈" if variacao >= 0 else "📉"
        rotulo_var = f"{variacao:+.1f}%".replace(".", ",").replace("-", "−")
        tipo = "ok" if variacao >= 0 else "alerta"
        insights.append(
            (
                f"{seta} Último dia fechou com **{formatar_numero_br(atual)} {rotulo_unidade}**, "
                f"variação de **{rotulo_var}** contra o dia anterior "
                f"({formatar_numero_br(d1)}).",
                tipo,
            )
        )

    if len(serie) >= 7:
        media7 = serie.tail(7).mean()
        if media7 > 0 and serie.iloc[-1] < media7 * 0.85:
            insights.append(
                (
                    "⚠️ O dia mais recente ficou **abaixo da média dos últimos 7 dias** "
                    f"({formatar_numero_br(media7, 1)} {rotulo_unidade}). "
                    "Vale investigar capacidade, feriados ou problemas sistêmicos.",
                    "alerta",
                )
            )

    melhor_dia = serie.idxmax()
    insights.append(
        (
            "🏆 Melhor dia do recorte: "
            f"**{pd.Timestamp(str(melhor_dia)).strftime('%d/%m/%Y')}** com "
            f"**{formatar_numero_br(serie.max())} {rotulo_unidade}**; "
            f"pior dia: **{pd.Timestamp(str(serie.idxmin())).strftime('%d/%m/%Y')}** "
            f"({formatar_numero_br(serie.min())}).",
            "info",
        )
    )

    if col_categoria and col_categoria in df.columns:
        contagem = df[col_categoria].astype(str).value_counts()
        if not contagem.empty and contagem.sum() > 0:
            lider = contagem.index[0]
            participacao = contagem.iloc[0] / contagem.sum() * 100.0
            if participacao >= 50.0:
                insights.append(
                    (
                        f"🎯 Concentração: **{lider}** responde por "
                        f"**{participacao:.1f}%** dos {rotulo_unidade}. "
                        "Atenção redobrada a desvios nessa categoria.".replace(".", ","),
                        "alerta",
                    )
                )
    return insights


def render_insights_automaticos(
    df: pd.DataFrame,
    *,
    col_data: str | None = None,
    col_valor: str | None = None,
    col_categoria: str | None = None,
    rotulo_unidade: str = "registros",
    titulo: str = "Leitura automática dos dados",
    max_insights: int = 3,
) -> None:
    """Renderiza um painel de insights automáticos sobre o recorte atual."""
    insights = gerar_insights(
        df,
        col_data=col_data,
        col_valor=col_valor,
        col_categoria=col_categoria,
        rotulo_unidade=rotulo_unidade,
    )
    if not insights:
        return
    with st.container(border=True):
        st.markdown(f"**💡 {titulo}**")
        for mensagem, tipo in insights[:max_insights]:
            render_insight(msg=mensagem, tipo=tipo)  # type: ignore[arg-type]


# ====================================================
# 🔄 BLOCO 8: AUTOATUALIZAÇÃO DO PAINEL
# ====================================================


def render_toggle_autorefresh(
    *,
    chave: str,
    intervalos_min: Sequence[int] = (2, 5, 10, 15),
    padrao_min: int = 5,
    rotulo: str = "Atualização automática",
) -> bool:
    """Toggle de autoatualização do painel usando streamlit-autorefresh.

    Retorna ``True`` quando a atualização está ativa. Se a biblioteca não
    estiver disponível no ambiente, apenas o controle é exibido (sem rerun
    programado) e o módulo registra o motivo — nenhum erro sobe para a tela.
    """
    chave_base = f"{_CHAVE_PREFIXO}::{chave}"
    col_toggle, col_intervalo = st.columns([3, 2], gap="small")
    with col_toggle:
        ativo = st.toggle(rotulo, key=f"{chave_base}::ativo", value=False)
    with col_intervalo:
        indice_padrao = intervalos_min.index(padrao_min) if padrao_min in intervalos_min else 0
        intervalo = st.selectbox(
            "Intervalo",
            options=list(intervalos_min),
            index=indice_padrao,
            format_func=lambda m: f"a cada {m} min",
            key=f"{chave_base}::intervalo",
            disabled=not ativo,
            label_visibility="collapsed",
        )
    if not ativo:
        return False
    try:
        from streamlit_autorefresh import st_autorefresh

        st_autorefresh(interval=int(intervalo) * 60 * 1000, key=f"{chave_base}::tick")
        st.caption(f"🔄 Painel atualizando automaticamente a cada {intervalo} min.")
        return True
    except Exception:  # pragma: no cover - depende de runtime/componente
        logger.info("streamlit-autorefresh indisponível; toggle sem efeito.", exc_info=True)
        st.caption("🔄 Atualização automática indisponível neste ambiente.")
        return False


# API pública do kit (mantém os re-exports de :mod:`components.kpi_cards`).
__all__ = [
    "SpecKPI",
    "SpecKPIAvancado",
    "VERSAO_KIT",
    "aplicar_tema_figura",
    "calcular_variacao_pct",
    "css_dashboards",
    "gerar_insights",
    "grafico_barras_ranking",
    "grafico_donut",
    "grafico_gauge_meta",
    "grafico_linha_tendencia",
    "injetar_css_dashboards",
    "render_barra_exportacao",
    "render_filtros_dashboard",
    "render_insights_automaticos",
    "render_kpi_grid",
    "render_kpi_row",
    "render_toggle_autorefresh",
    "resumo_periodo",
    "rotulo_tendencia",
]
