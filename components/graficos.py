"""components/graficos.py
=========================
Fábrica minimalista de gráficos Plotly Express com a identidade TOTALE.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Um único ponto de entrada para todos os gráficos do portal: as fábricas daqui
recebem o DataFrame e devolvem uma figura já tematizada (tipografia, margens,
grade, hover e legenda no padrão minimalista), nas cores oficiais da marca —
**Azul ``#012869``** e **Laranja ``#F37C04``**.

Como usar::

    from components.graficos import criar_grafico, render_grafico

    fig = criar_grafico("ranking", df, col_categoria="BASE", col_valor="OS", top=8)
    render_grafico(fig, chave="ranking_base")

    # ou a fábrica específica, com os mesmos parâmetros nomeados
    from components.graficos import grafico_linha
    render_grafico(grafico_linha(df, "DATA", "OS", cor="BASE", area=True))

Fábricas disponíveis (``TIPOS_GRAFICO`` lista todas as chaves aceitas por
``criar_grafico``):

=========================  =====================================================
Chave                      O que desenha
=========================  =====================================================
``linha``                  Evolução temporal (opcionalmente área e spline)
``area``                   Área empilhada por categoria
``barras``                 Colunas/barras agrupadas, empilhadas ou 100%
``ranking``                Top N horizontal com destaque no líder
``pizza`` / ``donut``      Participação com agregação automática de "Outros"
``dispersao``              Dispersão com bolhas e reta de tendência própria
``histograma``             Distribuição de uma variável
``caixa`` / ``violino``    Distribuição comparada por categoria
``calor``                  Matriz (heatmap) com escala azul→laranja
``calendario``             Heatmap calendário (dia da semana × semana)
``treemap`` / ``sunburst`` Hierarquia navegável
``funil``                  Etapas de conversão
``radar``                  Perfil multivariado (1 ou 2 séries comparadas)
``cascata``                Ponte de valores (waterfall) com total
``bullet`` / ``gauge``     Atingimento de meta compacto
``polar``                  Rosa dos ventos (barras polares)
``densidade``              Densidade 2D (heatmap ou contorno)
``combinado``              Barras + linha em eixo secundário
``progresso``              Barras horizontais de atingimento por item
``comparativo``            Dois períodos lado a lado (atual × anterior)
=========================  =====================================================
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

logger = logging.getLogger(__name__)

VERSAO_GRAFICOS = "1.0.0"

# ====================================================
# 🎨 BLOCO 1: IDENTIDADE VISUAL TOTALE
# ====================================================
AZUL_TOTALE = "#012869"
AZUL_CLARO = "#0A48AA"
AZUL_ESCURO = "#011838"
LARANJA_TOTALE = "#F37C04"
LARANJA_CLARO = "#FF9D45"
LARANJA_ESCURO = "#C2410C"

TEXTO_PRIMARIO = "#122033"
TEXTO_SECUNDARIO = "#64748B"
GRADE = "#EEF2F7"
BORDA = "#E6EDF5"

FONTE_TEXTO = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONTE_TITULO = "'Manrope', 'Segoe UI', Arial, sans-serif"

#: Paleta categórica oficial — abre no azul da marca, alterna com o laranja de
#: ação e só então completa com tons de apoio (nunca cores fora da identidade).
PALETA_TOTALE: list[str] = [
    AZUL_TOTALE,
    LARANJA_TOTALE,
    AZUL_CLARO,
    LARANJA_CLARO,
    AZUL_ESCURO,
    LARANJA_ESCURO,
    "#4E7FC4",
    "#FFB870",
    "#334155",
    "#9DB9E4",
]

#: Escala sequencial (mínimo → máximo) em degradê azul→laranja.
ESCALA_TOTALE: list[list[Any]] = [
    [0.0, "#F4F7FC"],
    [0.25, "#C7D6EE"],
    [0.5, "#5C8ACF"],
    [0.75, AZUL_TOTALE],
    [1.0, LARANJA_TOTALE],
]

#: Escala divergente (negativo → neutro → positivo) para desvios e variações.
ESCALA_DIVERGENTE_TOTALE: list[list[Any]] = [
    [0.0, LARANJA_ESCURO],
    [0.35, "#FDBA74"],
    [0.5, "#F8FAFC"],
    [0.65, "#9DB9E4"],
    [1.0, AZUL_TOTALE],
]

NOME_TEMA = "totale_min"

_DIAS_SEMANA = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")

TIPOS_GRAFICO: tuple[str, ...] = (
    "linha",
    "area",
    "barras",
    "ranking",
    "pizza",
    "donut",
    "dispersao",
    "histograma",
    "caixa",
    "violino",
    "calor",
    "calendario",
    "treemap",
    "sunburst",
    "funil",
    "radar",
    "cascata",
    "bullet",
    "gauge",
    "polar",
    "densidade",
    "combinado",
    "progresso",
    "comparativo",
)


def paleta_totale(quantidade: int = 10) -> list[str]:
    """Devolve ``quantidade`` cores da paleta oficial (repetindo se necessário)."""
    try:
        n = max(1, int(quantidade))
    except (TypeError, ValueError):
        n = 1
    return [PALETA_TOTALE[i % len(PALETA_TOTALE)] for i in range(n)]


def interpolar_cor(posicao: float, inicio: str = AZUL_TOTALE, fim: str = LARANJA_TOTALE) -> str:
    """Interpola linearmente entre duas cores hexadecimais (0 → 1)."""

    def _rgb(hexa: str) -> tuple[int, int, int]:
        limpo = hexa.lstrip("#")
        if len(limpo) == 3:
            limpo = "".join(c * 2 for c in limpo)
        try:
            return int(limpo[0:2], 16), int(limpo[2:4], 16), int(limpo[4:6], 16)
        except ValueError:
            return 1, 40, 105

    try:
        t = min(1.0, max(0.0, float(posicao)))
    except (TypeError, ValueError):
        t = 0.0
    r1, g1, b1 = _rgb(inicio)
    r2, g2, b2 = _rgb(fim)
    return "#{:02X}{:02X}{:02X}".format(
        round(r1 + (r2 - r1) * t),
        round(g1 + (g2 - g1) * t),
        round(b1 + (b2 - b1) * t),
    )


def cores_por_categoria(categorias: Sequence[Any], destaque: Any | None = None) -> dict[str, str]:
    """Mapa categoria → cor da marca, reservando o laranja para o ``destaque``."""
    unicas = [str(c) for c in pd.unique(pd.Series(list(categorias)).astype(str))]
    if destaque is not None and str(destaque) in unicas:
        outras = [c for c in unicas if c != str(destaque)]
        mapa = {c: paleta_totale(len(outras))[i] for i, c in enumerate(outras)}
        mapa[str(destaque)] = LARANJA_TOTALE
        return mapa
    return {c: paleta_totale(len(unicas))[i] for i, c in enumerate(unicas)}


# ====================================================
# 🧪 BLOCO 2: TEMA MINIMALISTA PLOTLY
# ====================================================
def registrar_tema_totale() -> None:
    """Registra (uma vez) o template ``totale_min`` no Plotly.

    Minimalista de propósito: sem fundo colorido, sem caixa de legenda, grade
    apenas no eixo Y, tipografia da marca e margens enxutas.
    """
    if NOME_TEMA in pio.templates:
        return
    template = go.layout.Template(
        layout=go.Layout(
            font={"family": FONTE_TEXTO, "size": 12.5, "color": TEXTO_SECUNDARIO},
            title={
                "font": {"family": FONTE_TITULO, "size": 16, "color": TEXTO_PRIMARIO},
                "x": 0.0,
                "xanchor": "left",
                "xref": "container",
                "pad": {"t": 6, "b": 8, "l": 0, "r": 0},
            },
            colorway=PALETA_TOTALE,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin={"t": 54, "b": 46, "l": 54, "r": 18},
            hoverlabel={
                "bgcolor": "#FFFFFF",
                "bordercolor": BORDA,
                "font": {"family": FONTE_TEXTO, "size": 12, "color": TEXTO_PRIMARIO},
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": -0.24,
                "xanchor": "left",
                "x": 0,
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "font": {"family": FONTE_TEXTO, "size": 11.5, "color": TEXTO_SECUNDARIO},
            },
            xaxis={
                "gridcolor": "rgba(0,0,0,0)",
                "zerolinecolor": BORDA,
                "linecolor": BORDA,
                "showline": True,
                "ticks": "",
                "title": {"font": {"size": 11.5, "color": TEXTO_SECUNDARIO}},
            },
            yaxis={
                "gridcolor": GRADE,
                "zerolinecolor": BORDA,
                "linecolor": "rgba(0,0,0,0)",
                "showline": False,
                "ticks": "",
                "title": {"font": {"size": 11.5, "color": TEXTO_SECUNDARIO}},
            },
        )
    )
    pio.templates[NOME_TEMA] = template


def _tema_registrado() -> None:
    registrar_tema_totale()


def aplicar_tema(
    fig: go.Figure,
    *,
    titulo: str | None = None,
    altura: int | None = None,
    hover_unificado: bool = True,
    legenda: bool = True,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Aplica o acabamento minimalista TOTALE a qualquer figura Plotly."""
    _tema_registrado()
    fig.update_layout(
        template=NOME_TEMA,
        height=altura,
        title=({"text": titulo} if titulo else None),
        hovermode=("x unified" if hover_unificado else "closest"),
        showlegend=legenda,
        bargap=0.34,
        bargroupgap=0.06,
    )
    if rotulos:
        atualizacoes: dict[str, Any] = {}
        if rotulos.get("x"):
            atualizacoes["xaxis_title"] = rotulos["x"]
        if rotulos.get("y"):
            atualizacoes["yaxis_title"] = rotulos["y"]
        if rotulos.get("color"):
            atualizacoes["legend_title_text"] = rotulos["color"]
        if atualizacoes:
            fig.update_layout(**atualizacoes)
    return fig


def config_minimalista(*, download: bool = True, zoom: bool = True) -> dict[str, Any]:
    """Configuração enxuta do ``st.plotly_chart`` (barra de ferramentas mínima).

    Mantém apenas hover, zoom/pan e exportação de imagem; remove seleção,
    laço e picos. Sem logo do Plotly — o gráfico é da TOTALE.
    """
    remover = ["select2d", "lasso2d", "toggleSpikelines", "hoverCompareCartesian"]
    if not zoom:
        remover += ["zoom2d", "pan2d", "resetScale2d", "autoScale2d"]
    if not download:
        remover.append("toImage")
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": remover,
        "responsive": True,
        "scrollZoom": bool(zoom),
        "doubleClick": "reset" if zoom else "reset+autosize",
    }


#: ``"noop"`` existia em versões antigas do Streamlit; hoje o equivalente é
#: ``"ignore"``. Normalizamos aqui para as páginas poderem usar qualquer um.
_MODO_SELECAO: dict[str, str] = {"noop": "ignore", "ignore": "ignore", "rerun": "rerun"}


def render_grafico(
    fig: go.Figure,
    *,
    chave: str | None = None,
    altura: int | None = None,
    config: dict[str, Any] | None = None,
    ao_selecionar: Literal["noop", "ignore", "rerun"] = "noop",
) -> Any:
    """Exibe a figura com o padrão do portal (largura total, toolbar mínima)."""
    import streamlit as st

    if fig is None:
        return None
    if altura:
        fig.update_layout(height=altura)
    kwargs: dict[str, Any] = {
        "width": "stretch",
        "config": config or config_minimalista(),
    }
    if chave:
        kwargs["key"] = f"totale_grafico::{chave}"
        kwargs["on_select"] = _MODO_SELECAO.get(str(ao_selecionar), "ignore")
    try:
        return st.plotly_chart(fig, **kwargs)
    except TypeError:
        # Streamlit antigo sem on_select/key: exibe sem seleção interativa.
        kwargs.pop("on_select", None)
        kwargs.pop("key", None)
        return st.plotly_chart(fig, **kwargs)
    except Exception:
        # Só engolimos o erro quando ele pode vir de key/on_select; caso
        # contrário, propagamos para não mascarar falha real da figura.
        if "on_select" not in kwargs:
            raise
        kwargs.pop("on_select", None)
        kwargs.pop("key", None)
        return st.plotly_chart(fig, **kwargs)


def render_graficos_em_abas(
    figuras: Mapping[str, go.Figure],
    *,
    chave: str,
    altura: int | None = None,
) -> None:
    """Coloca várias figuras em abas nomeadas (organização da informação)."""
    import streamlit as st

    itens = [(rotulo, fig) for rotulo, fig in figuras.items() if fig is not None]
    if not itens:
        st.caption("Sem gráficos para exibir no recorte atual.")
        return
    abas = st.tabs([rotulo for rotulo, _ in itens])
    for aba, (rotulo, fig) in zip(abas, itens):
        with aba:
            render_grafico(fig, chave=f"{chave}::{rotulo}", altura=altura)


def figura_vazia(titulo: str = "", mensagem: str = "Sem dados no recorte atual.") -> go.Figure:
    """Figura neutra com aviso central (nunca devolvemos ``None`` às páginas)."""
    _tema_registrado()
    fig = go.Figure()
    fig.update_layout(
        template=NOME_TEMA,
        height=240,
        title=({"text": titulo} if titulo else None),
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": mensagem,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"family": FONTE_TEXTO, "size": 13.5, "color": TEXTO_SECUNDARIO},
            }
        ],
    )
    return fig


def _esta_vazio(df: pd.DataFrame | None) -> bool:
    return df is None or not isinstance(df, pd.DataFrame) or df.empty


def _coluna_existe(df: pd.DataFrame, coluna: str | None) -> bool:
    return bool(coluna) and coluna in df.columns


def _rotulos(rotulos: Mapping[str, str] | None, padrao: Mapping[str, str]) -> dict[str, str]:
    base = dict(padrao)
    if rotulos:
        base.update({k: v for k, v in rotulos.items() if v})
    return base


def _numerica(df: pd.DataFrame, coluna: str) -> pd.Series:
    return pd.to_numeric(df[coluna], errors="coerce").fillna(0.0)


def _numero_br(valor: Any, casas: int = 0) -> str:
    """Formata número no padrão pt-BR (ponto de milhar, vírgula decimal).

    Usado nos textos desenhados pelo Python (rótulos de barra, anotações e
    totais). Nos ``hovertemplate`` o Plotly formata com d3 (sem agrupamento),
    evitando o conflito entre o separador de milhar americano e o brasileiro.
    """
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if not np.isfinite(numero):
        return "—"
    if casas <= 0:
        return f"{int(round(numero)):,}".replace(",", ".")
    texto = f"{numero:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


# ====================================================
# 📈 BLOCO 3: FÁBRICAS DE SÉRIE E COMPARAÇÃO
# ====================================================
def _textos_matriz(fig: go.Figure, matriz: pd.DataFrame, mostrar: bool) -> None:
    """Escreve os valores do heatmap em pt-BR (o ``text_auto`` do d3 não localiza)."""
    if not mostrar or matriz is None or matriz.empty:
        return
    textos = [[_numero_br(v) for v in linha] for linha in np.asarray(matriz, dtype="object")]
    fig.update_traces(text=textos, texttemplate="%{text}", textfont={"size": 10})


def _aplicar_cor_unica(fig: go.Figure, cor: str | None) -> None:
    """Pinta a série única com uma cor da marca (quando não há agrupamento).

    Usado pelos gráficos de linha, área e barras: sem ``col_grupo`` o traço
    assume a cor informada (padrão da paleta TOTALE); com agrupamento, a paleta
    categórica continua valendo.
    """
    if not cor:
        return
    for trace in fig.data:
        tipo = getattr(trace, "type", "")
        try:
            if tipo == "bar":
                trace.marker.color = cor
            elif tipo in ("scatter", "scattergl", "scatterpolar"):
                trace.line.color = cor
                trace.marker.color = cor
            elif tipo == "histogram":
                trace.marker.color = cor
            else:
                trace.marker.color = cor
        except Exception:  # pragma: no cover - tipo de traço sem marker/line
            logger.debug("Não foi possível aplicar a cor %r ao traço %r.", cor, tipo, exc_info=True)


def grafico_linha(
    df: pd.DataFrame,
    col_x: str,
    col_y: str,
    *,
    col_grupo: str | None = None,
    cor: str | None = None,
    titulo: str = "",
    altura: int = 360,
    rotulos: Mapping[str, str] | None = None,
    suave: bool = True,
    marcadores: bool = True,
    area: bool = False,
    ordem: Sequence[str] | None = None,
    empilhar: bool = False,
) -> go.Figure:
    """Evolução temporal minimalista (linha, spline, marcadores e/ou área).

    Args:
        col_grupo: coluna que separa a série em vários traços (ex.: equipe,
            base, segmento). Com ela, vale a paleta categórica TOTALE.
        cor: cor única (hex) quando não há ``col_grupo`` — padrão azul oficial.
    """
    if _esta_vazio(df) or not _coluna_existe(df, col_x) or not _coluna_existe(df, col_y):
        return figura_vazia(titulo, "Sem dados suficientes para a série temporal.")
    dados = df[[col_x, col_y] + ([col_grupo] if _coluna_existe(df, col_grupo) else [])].copy()
    dados[col_y] = pd.to_numeric(dados[col_y], errors="coerce")
    dados = dados.dropna(subset=[col_y])
    if dados.empty:
        return figura_vazia(titulo)
    if _coluna_existe(dados, col_grupo):
        dados[col_grupo] = dados[col_grupo].astype(str)
    kwargs: dict[str, Any] = {
        "markers": marcadores,
        "line_shape": "spline" if suave else "linear",
    }
    if area:
        kwargs["line_group"] = col_grupo if _coluna_existe(dados, col_grupo) else None
    fabrica = px.area if area else px.line
    fig = fabrica(
        dados,
        x=col_x,
        y=col_y,
        color=col_grupo if _coluna_existe(dados, col_grupo) else None,
        color_discrete_sequence=PALETA_TOTALE,
        category_orders={col_grupo: list(ordem)} if ordem and _coluna_existe(dados, col_grupo) else None,
        labels=_rotulos(rotulos, {"x": "", "y": "", "color": col_grupo or ""}),
        **kwargs,
    )
    if not _coluna_existe(dados, col_grupo):
        _aplicar_cor_unica(fig, cor or AZUL_TOTALE)
    if area:
        for indice, trace in enumerate(fig.data):
            cor_trace = trace.line.color if trace.line and trace.line.color else None
            cor_area = cor_trace or PALETA_TOTALE[indice % len(PALETA_TOTALE)]
            trace.fillcolor = f"{cor_area}22"
    return aplicar_tema(
        fig,
        titulo=titulo or None,
        altura=altura,
        legenda=col_grupo is not None and _coluna_existe(dados, col_grupo),
    )


def grafico_area(
    df: pd.DataFrame,
    col_x: str,
    col_y: str,
    *,
    col_grupo: str | None = None,
    cor: str | None = None,
    titulo: str = "",
    altura: int = 360,
    rotulos: Mapping[str, str] | None = None,
    ordem: Sequence[str] | None = None,
) -> go.Figure:
    """Área empilhada translúcida por categoria (demanda ao longo do tempo)."""
    return grafico_linha(
        df,
        col_x,
        col_y,
        col_grupo=col_grupo,
        cor=cor,
        titulo=titulo,
        altura=altura,
        rotulos=rotulos,
        area=True,
        empilhar=True,
        ordem=ordem,
        marcadores=False,
    )


def grafico_barras(
    df: pd.DataFrame,
    col_x: str,
    col_y: str,
    *,
    col_grupo: str | None = None,
    cor: str | None = None,
    titulo: str = "",
    altura: int = 360,
    rotulos: Mapping[str, str] | None = None,
    orientacao: Literal["v", "h"] = "v",
    modo: Literal["agrupado", "empilhado", "relativo"] = "agrupado",
    mostrar_valores: bool = False,
    ordem: Sequence[str] | None = None,
    agregacao: Literal["soma", "media", "contagem"] | None = "soma",
) -> go.Figure:
    """Barras/colunas agrupadas, empilhadas ou em participação relativa (100%).

    Args:
        col_grupo: coluna que divide cada categoria em barras por série.
        cor: cor única (hex) sem ``col_grupo`` — padrão azul oficial.
        modo: ``agrupado``, ``empilhado`` ou ``relativo`` (participação 100%).
        agregacao: ``soma`` (padrão), ``media`` ou ``contagem`` de linhas.
    """
    if _esta_vazio(df) or not _coluna_existe(df, col_x) or not _coluna_existe(df, col_y):
        return figura_vazia(titulo, "Sem dados suficientes para as barras.")
    dados = df.copy()
    dados[col_x] = dados[col_x].astype(str)
    dados[col_y] = pd.to_numeric(dados[col_y], errors="coerce").fillna(0.0)
    tem_grupo = _coluna_existe(dados, col_grupo)
    if tem_grupo:
        dados[col_grupo] = dados[col_grupo].astype(str)
    if agregacao == "contagem":
        agrupar = [col_x] + ([col_grupo] if tem_grupo else [])
        dados = dados.groupby(agrupar, as_index=False).size().rename(columns={"size": "__contagem__"})
        col_valor = "__contagem__"
    else:
        col_valor = col_y
        agrupar = [col_x] + ([col_grupo] if tem_grupo else [])
        dados = dados.groupby(agrupar, as_index=False)[col_valor].agg(
            "sum" if agregacao != "media" else "mean"
        )
    tem_grupo = bool(tem_grupo and col_grupo in dados.columns)

    if modo == "relativo":
        # Participação relativa (100%): normaliza dentro de cada categoria base.
        totais = dados.groupby(col_x)[col_valor].transform("sum").replace(0, np.nan)
        dados = dados.assign(**{col_valor: (dados[col_valor] / totais).fillna(0.0)})

    kwargs: dict[str, Any] = {}
    if orientacao == "h":
        kwargs["orientation"] = "h"
    if ordem:
        kwargs["category_orders"] = {col_x: list(ordem)}
    # Rótulos desenhados pelo Python em pt-BR (o d3 usaria "1.25k", ambíguo).
    textos: list[str] | None = None
    if mostrar_valores:
        if modo == "relativo":
            textos = [f"{_numero_br(v * 100.0, 1)}%" for v in dados[col_valor]]
        elif agregacao == "media":
            textos = [_numero_br(v, 2) for v in dados[col_valor]]
        else:
            textos = [_numero_br(v) for v in dados[col_valor]]

    fig = px.bar(
        dados,
        x=col_valor if orientacao == "h" else col_x,
        y=col_x if orientacao == "h" else col_valor,
        color=col_grupo if tem_grupo else None,
        barmode="stack" if modo in ("empilhado", "relativo") else "group",
        color_discrete_sequence=PALETA_TOTALE,
        text=textos,
        labels=_rotulos(rotulos, {"x": col_x, "y": col_y, "color": col_grupo or ""}),
        **kwargs,
    )
    fig.update_traces(marker_line_width=0, marker_cornerradius=4)
    if textos:
        fig.update_traces(texttemplate="%{text}")
    if not tem_grupo:
        _aplicar_cor_unica(fig, cor or AZUL_TOTALE)
    if modo == "relativo":
        eixo_valor = "xaxis" if orientacao == "h" else "yaxis"
        fig.update_layout(**{f"{eixo_valor}_tickformat": ".0%"})
    if orientacao == "h":
        fig.update_yaxes(autorange="reversed")
    return aplicar_tema(
        fig,
        titulo=titulo or None,
        altura=altura,
        hover_unificado=(orientacao == "v"),
        legenda=tem_grupo,
    )


def grafico_ranking(
    df: pd.DataFrame,
    col_categoria: str,
    col_valor: str,
    *,
    titulo: str = "",
    altura: int | None = None,
    top: int = 10,
    cor: str = AZUL_TOTALE,
    cor_destaque: str = LARANJA_TOTALE,
    destacar_lider: bool = True,
    mostrar_valores: bool = True,
    ascendente: bool = False,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Ranking horizontal (Top N) com o líder destacado no laranja da marca."""
    if _esta_vazio(df) or not _coluna_existe(df, col_categoria) or not _coluna_existe(df, col_valor):
        return figura_vazia(titulo, "Sem categorias para ranquear.")
    dados = (
        df.assign(**{col_categoria: df[col_categoria].astype(str)})
        .groupby(col_categoria, as_index=False)
        .agg({col_valor: lambda s: pd.to_numeric(s, errors="coerce").fillna(0.0).sum()})
        .sort_values(col_valor, ascending=ascendente)
        .head(max(1, int(top)))
        .sort_values(col_valor, ascending=True)
        .reset_index(drop=True)
    )
    if dados.empty:
        return figura_vazia(titulo)
    cores = [cor] * len(dados)
    if destacar_lider and len(dados) > 1:
        cores[-1] = cor_destaque
    fig = px.bar(
        dados,
        x=col_valor,
        y=col_categoria,
        orientation="h",
        text=([_numero_br(v) for v in dados[col_valor]] if mostrar_valores else None),
        labels=_rotulos(rotulos, {"x": col_valor, "y": ""}),
    )
    fig.update_traces(
        marker_color=cores,
        marker_line_width=0,
        marker_cornerradius=5,
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}: %{x:.0f}<extra></extra>",
    )
    if mostrar_valores:
        fig.update_traces(texttemplate="%{text}")
    fig.update_layout(bargap=0.34)
    fig.update_yaxes(tickfont={"size": 12, "color": TEXTO_PRIMARIO})
    fig.update_xaxes(showgrid=True, gridcolor=GRADE)
    return aplicar_tema(
        fig,
        titulo=titulo or None,
        altura=altura or max(220, 34 * len(dados) + 90),
        hover_unificado=False,
        legenda=False,
    )


def grafico_comparativo(
    categorias: Sequence[Any],
    atual: Sequence[float],
    anterior: Sequence[float],
    *,
    titulo: str = "",
    altura: int = 340,
    rotulo_atual: str = "Período atual",
    rotulo_anterior: str = "Período anterior",
    mostrar_valores: bool = False,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Comparação lado a lado de dois períodos por categoria (atual × anterior)."""
    nomes = [str(c) for c in categorias]
    valores_atual = pd.to_numeric(pd.Series(list(atual)), errors="coerce").tolist()
    valores_anterior = pd.to_numeric(pd.Series(list(anterior)), errors="coerce").tolist()
    if len(nomes) != len(valores_atual) or len(nomes) != len(valores_anterior):
        return figura_vazia(
            titulo, "Categorias, valores atuais e anteriores precisam ter o mesmo tamanho."
        )
    dados = pd.DataFrame(
        {
            "Categoria": [*nomes, *nomes],
            "Valor": [*valores_atual, *valores_anterior],
            "Período": [rotulo_atual] * len(nomes) + [rotulo_anterior] * len(nomes),
        }
    )
    dados = dados.dropna(subset=["Valor"])
    if dados.empty:
        return figura_vazia(titulo)
    fig = px.bar(
        dados,
        x="Categoria",
        y="Valor",
        color="Período",
        barmode="group",
        color_discrete_map={rotulo_atual: AZUL_TOTALE, rotulo_anterior: LARANJA_CLARO},
        text=([_numero_br(v) for v in dados["Valor"]] if mostrar_valores else None),
        labels=_rotulos(rotulos, {"x": "", "y": "", "color": ""}),
    )
    fig.update_traces(marker_line_width=0, marker_cornerradius=4)
    if mostrar_valores:
        fig.update_traces(texttemplate="%{text}")
    return aplicar_tema(fig, titulo=titulo or None, altura=altura, legenda=True)


def grafico_combinado(
    df: pd.DataFrame,
    col_x: str,
    col_barras: str,
    col_linha: str,
    *,
    titulo: str = "",
    altura: int = 380,
    cor_barra: str = AZUL_TOTALE,
    cor_linha: str = LARANJA_TOTALE,
    rotulo_barra: str = "",
    rotulo_linha: str = "",
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Barras (volume) + linha em eixo secundário (taxa/percentual)."""
    if (
        _esta_vazio(df)
        or not _coluna_existe(df, col_x)
        or not _coluna_existe(df, col_barras)
        or not _coluna_existe(df, col_linha)
    ):
        return figura_vazia(titulo, "Sem dados para o gráfico combinado.")
    dados = df[[col_x, col_barras, col_linha]].copy()
    dados[col_barras] = pd.to_numeric(dados[col_barras], errors="coerce").fillna(0.0)
    dados[col_linha] = pd.to_numeric(dados[col_linha], errors="coerce")
    dados[col_x] = dados[col_x].astype(str)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=dados[col_x],
            y=dados[col_barras],
            name=rotulo_barra or col_barras,
            marker_color=cor_barra,
            marker_cornerradius=4,
            marker_line_width=0,
            hovertemplate=f"%{{x}}<br>{rotulo_barra or col_barras}: %{{y:.0f}}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dados[col_x],
            y=dados[col_linha],
            name=rotulo_linha or col_linha,
            mode="lines+markers",
            yaxis="y2",
            line_color=cor_linha,
            line_width=2.4,
            marker_size=7,
            hovertemplate=f"%{{x}}<br>{rotulo_linha or col_linha}: %{{y:.1f}}<extra></extra>",
        )
    )
    aplicar_tema(
        fig,
        titulo=titulo or None,
        altura=altura,
        rotulos=_rotulos(rotulos, {"x": ""}),
    )
    fig.update_layout(
        yaxis={"title": rotulo_barra or col_barras, "gridcolor": GRADE},
        yaxis2={
            "title": rotulo_linha or col_linha,
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
            "ticksuffix": "%",
        },
        legend={"orientation": "h", "y": -0.24, "x": 0},
    )
    return fig


# ====================================================
# 🥧 BLOCO 4: PARTICIPAÇÃO, DISTRIBUIÇÃO E HIERARQUIA
# ====================================================
def _agregar_outros(
    rotulos: list[str],
    valores: list[float],
    top: int | None,
    rotulo_outros: str = "Outros",
) -> tuple[list[str], list[float]]:
    """Mantém os ``top`` maiores e agrupa o restante em "Outros"."""
    pares = sorted(zip(rotulos, valores), key=lambda item: item[1], reverse=True)
    if top is None or len(pares) <= top:
        return [p[0] for p in pares], [p[1] for p in pares]
    principais = pares[:top]
    resto = sum(p[1] for p in pares[top:])
    rotulos_saida = [p[0] for p in principais]
    valores_saida = [p[1] for p in principais]
    if resto > 0:
        rotulos_saida.append(rotulo_outros)
        valores_saida.append(resto)
    return rotulos_saida, valores_saida


def grafico_pizza(
    df: pd.DataFrame | None = None,
    col_nome: str | None = None,
    col_valor: str | None = None,
    *,
    rotulos: Sequence[Any] | None = None,
    valores: Sequence[float] | None = None,
    titulo: str = "",
    altura: int = 340,
    donut: bool = True,
    top: int | None = 7,
    rotulo_outros: str = "Outros",
    mostrar_total: bool = True,
) -> go.Figure:
    """Participação em pizza/donut com agregação automática de "Outros"."""
    if df is not None and col_nome and col_valor and _coluna_existe(df, col_nome):
        if not _coluna_existe(df, col_valor):
            return figura_vazia(titulo)
        agrupado = (
            df.assign(**{col_nome: df[col_nome].astype(str)})
            .groupby(col_nome, as_index=False)[col_valor]
            .sum()
        )
        nomes = [str(n) for n in agrupado[col_nome]]
        pesos = [float(v) for v in pd.to_numeric(agrupado[col_valor], errors="coerce").fillna(0.0)]
    elif rotulos is not None and valores is not None:
        nomes = [str(r) for r in rotulos]
        pesos = [float(v) for v in pd.to_numeric(pd.Series(list(valores)), errors="coerce").fillna(0.0)]
    else:
        return figura_vazia(titulo, "Informe DataFrame + colunas ou rotulos + valores.")

    nomes, pesos = _agregar_outros(nomes, pesos, top, rotulo_outros)
    total = float(sum(pesos))
    if total <= 0:
        return figura_vazia(titulo)

    cores = paleta_totale(len(nomes))
    if len(cores) > 1:
        cores[-1] = "#CBD5E1" if nomes[-1] == rotulo_outros else cores[-1]
    fig = px.pie(
        pd.DataFrame({"nome": nomes, "valor": pesos}),
        names="nome",
        values="valor",
        hole=0.58 if donut else 0.0,
        color_discrete_sequence=cores,
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label" if len(nomes) <= 6 else "percent",
        marker_line_color="#FFFFFF",
        marker_line_width=2,
        hovertemplate="%{label}<br>%{value:.0f} (%{percent})<extra></extra>",
        sort=False,
    )
    aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=True)
    if donut and mostrar_total:
        fig.update_layout(
            annotations=[
                {
                    "text": (
                        f"<b>{_numero_br(total)}</b>"
                        + "<br><span style='font-size:11px;color:#64748B;'>TOTAL</span>"
                    ),
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"family": FONTE_TITULO, "size": 20, "color": TEXTO_PRIMARIO},
                }
            ]
        )
    return fig


def grafico_donut(
    df: pd.DataFrame | None = None,
    col_nome: str | None = None,
    col_valor: str | None = None,
    **kwargs: Any,
) -> go.Figure:
    """Atalho semântico para ``grafico_pizza(..., donut=True)``."""
    kwargs.setdefault("donut", True)
    return grafico_pizza(df, col_nome, col_valor, **kwargs)


def grafico_treemap(
    df: pd.DataFrame,
    caminho: Sequence[str],
    col_valor: str,
    *,
    titulo: str = "",
    altura: int = 420,
    col_grupo: str | None = None,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Hierarquia navegável (ex.: Base → Monitor → Técnico) em treemap."""
    if _esta_vazio(df) or col_valor not in df.columns:
        return figura_vazia(titulo, "Sem dados para o treemap.")
    trilhas = [c for c in caminho if c in df.columns]
    if not trilhas:
        return figura_vazia(titulo, "Colunas da hierarquia não encontradas.")
    dados = df[trilhas + [col_valor]].copy()
    for coluna in trilhas:
        dados[coluna] = dados[coluna].astype(str).replace("", "Não informado")
    dados[col_valor] = pd.to_numeric(dados[col_valor], errors="coerce").fillna(0.0)
    fig = px.treemap(
        dados,
        path=trilhas,
        values=col_valor,
        color=col_grupo if _coluna_existe(dados, col_grupo) else col_valor,
        color_continuous_scale=ESCALA_TOTALE if not _coluna_existe(dados, col_grupo) else None,
        color_discrete_sequence=PALETA_TOTALE if _coluna_existe(dados, col_grupo) else None,
        labels=dict(_rotulos(rotulos, {})),
    )
    fig.update_traces(
        marker_line_color="#FFFFFF",
        marker_line_width=1.4,
        textinfo="label+value",
        hovertemplate="%{label}<br>%{value:.0f}<extra></extra>",
    )
    return aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=False)


def grafico_sunburst(
    df: pd.DataFrame,
    caminho: Sequence[str],
    col_valor: str,
    *,
    titulo: str = "",
    altura: int = 440,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Hierarquia radial (sunburst) com a escala sequencial da marca."""
    if _esta_vazio(df) or col_valor not in df.columns:
        return figura_vazia(titulo, "Sem dados para o sunburst.")
    trilhas = [c for c in caminho if c in df.columns]
    if not trilhas:
        return figura_vazia(titulo, "Colunas da hierarquia não encontradas.")
    dados = df[trilhas + [col_valor]].copy()
    for coluna in trilhas:
        dados[coluna] = dados[coluna].astype(str).replace("", "Não informado")
    dados[col_valor] = pd.to_numeric(dados[col_valor], errors="coerce").fillna(0.0)
    fig = px.sunburst(
        dados,
        path=trilhas,
        values=col_valor,
        color=col_valor,
        color_continuous_scale=ESCALA_TOTALE,
        labels=dict(_rotulos(rotulos, {})),
    )
    fig.update_traces(hovertemplate="%{label}<br>%{value:.0f}<extra></extra>")
    return aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=False)


def grafico_funil(
    df: pd.DataFrame,
    col_etapa: str,
    col_valor: str,
    *,
    titulo: str = "",
    altura: int = 380,
    cor: str = AZUL_TOTALE,
    ordem: Sequence[str] | None = None,
    mostrar_conversao: bool = True,
) -> go.Figure:
    """Funil de etapas com percentual de conversão em relação à primeira etapa."""
    if _esta_vazio(df) or not _coluna_existe(df, col_etapa) or not _coluna_existe(df, col_valor):
        return figura_vazia(titulo, "Sem etapas para o funil.")
    dados = df[[col_etapa, col_valor]].copy()
    dados[col_etapa] = dados[col_etapa].astype(str)
    dados[col_valor] = pd.to_numeric(dados[col_valor], errors="coerce").fillna(0.0)
    dados = dados.groupby(col_etapa, as_index=False)[col_valor].sum()
    if ordem:
        dados[col_etapa] = pd.Categorical(dados[col_etapa], categories=list(ordem), ordered=True)
        dados = dados.sort_values(col_etapa)
    else:
        dados = dados.sort_values(col_valor, ascending=False)
    dados = dados.reset_index(drop=True)
    if dados.empty:
        return figura_vazia(titulo)

    texto = None
    if mostrar_conversao:
        base = float(dados[col_valor].iloc[0]) or 1.0
        texto = [
            f"{_numero_br(valor)}  ({_numero_br(valor / base * 100, 1)}%)"
            for valor in dados[col_valor]
        ]
    fig = px.funnel(
        dados,
        x=col_valor,
        y=col_etapa,
        color_discrete_sequence=[cor],
        text=texto,
    )
    fig.update_traces(
        marker_line_color="#FFFFFF",
        marker_line_width=1.5,
        textposition="inside",
        hovertemplate="%{y}<br>%{x:.0f}<extra></extra>",
    )
    return aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=False)


def grafico_histograma(
    df: pd.DataFrame,
    col_x: str,
    *,
    col_grupo: str | None = None,
    titulo: str = "",
    altura: int = 340,
    nbins: int = 30,
    cumulativo: bool = False,
    mostrar_media: bool = True,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Distribuição de uma variável com linha de média opcional."""
    if _esta_vazio(df) or not _coluna_existe(df, col_x):
        return figura_vazia(titulo, "Sem valores para o histograma.")
    dados = df[[col_x] + ([col_grupo] if _coluna_existe(df, col_grupo) else [])].copy()
    dados[col_x] = pd.to_numeric(dados[col_x], errors="coerce")
    dados = dados.dropna(subset=[col_x])
    if dados.empty:
        return figura_vazia(titulo)
    if _coluna_existe(dados, col_grupo):
        dados[col_grupo] = dados[col_grupo].astype(str)
    fig = px.histogram(
        dados,
        x=col_x,
        color=col_grupo if _coluna_existe(dados, col_grupo) else None,
        nbins=max(2, int(nbins)),
        color_discrete_sequence=PALETA_TOTALE,
        cumulative=cumulativo,
        labels=_rotulos(rotulos, {"x": col_x, "y": "Frequência", "color": col_grupo or ""}),
    )
    fig.update_traces(marker_line_color="#FFFFFF", marker_line_width=0.8)
    aplicar_tema(fig, titulo=titulo or None, altura=altura, legenda=_coluna_existe(dados, col_grupo))
    if mostrar_media:
        media = float(dados[col_x].mean())
        fig.add_vline(
            x=media,
            line_color=LARANJA_TOTALE,
            line_width=1.8,
            line_dash="dash",
            annotation_text=f"Média {_numero_br(media, 1)}",
            annotation_position="top right",
            annotation_font_color=LARANJA_ESCURO,
        )
    return fig


def grafico_distribuicao(
    df: pd.DataFrame,
    col_y: str,
    col_x: str | None = None,
    *,
    tipo: Literal["caixa", "violino", "pontos"] = "caixa",
    col_grupo: str | None = None,
    titulo: str = "",
    altura: int = 360,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Distribuição comparada por categoria (box, violino ou strip)."""
    if _esta_vazio(df) or not _coluna_existe(df, col_y):
        return figura_vazia(titulo, "Sem valores para a distribuição.")
    dados = df.copy()
    dados[col_y] = pd.to_numeric(dados[col_y], errors="coerce")
    dados = dados.dropna(subset=[col_y])
    if dados.empty:
        return figura_vazia(titulo)
    tem_x = _coluna_existe(dados, col_x)
    if tem_x:
        dados[col_x] = dados[col_x].astype(str)
    if _coluna_existe(dados, col_grupo):
        dados[col_grupo] = dados[col_grupo].astype(str)
    fabricas = {"caixa": px.box, "violino": px.violin, "pontos": px.strip}
    fabrica = fabricas.get(tipo, px.box)
    kwargs: dict[str, Any] = {"color_discrete_sequence": PALETA_TOTALE}
    if tipo == "violino":
        kwargs["box"] = True
        kwargs["points"] = False
    if tipo == "caixa":
        kwargs["notched"] = False
        kwargs["points"] = "outliers"
    fig = fabrica(
        dados,
        x=col_x if tem_x else None,
        y=col_y,
        color=col_grupo if _coluna_existe(dados, col_grupo) else None,
        labels=_rotulos(rotulos, {"x": col_x or "", "y": col_y, "color": col_grupo or ""}),
        **kwargs,
    )
    return aplicar_tema(
        fig,
        titulo=titulo or None,
        altura=altura,
        hover_unificado=False,
        legenda=_coluna_existe(dados, col_grupo),
    )


def grafico_caixa(df: pd.DataFrame, col_y: str, col_x: str | None = None, **kwargs: Any) -> go.Figure:
    """Atalho para ``grafico_distribuicao(..., tipo="caixa")``."""
    return grafico_distribuicao(df, col_y, col_x, tipo="caixa", **kwargs)


def grafico_violino(
    df: pd.DataFrame, col_y: str, col_x: str | None = None, **kwargs: Any
) -> go.Figure:
    """Atalho para ``grafico_distribuicao(..., tipo="violino")``."""
    return grafico_distribuicao(df, col_y, col_x, tipo="violino", **kwargs)


def grafico_dispersao(
    df: pd.DataFrame,
    col_x: str,
    col_y: str,
    *,
    col_grupo: str | None = None,
    tamanho: str | None = None,
    titulo: str = "",
    altura: int = 380,
    tendencia: Literal[None, "linear"] = "linear",
    rotulo_tendencia: str = "Tendência",
    rotulos: Mapping[str, str] | None = None,
    opacidade: float = 0.78,
) -> go.Figure:
    """Dispersão (bolhas) com reta de tendência calculada no próprio módulo.

    A tendência usa mínimos quadrados via NumPy — não depende de ``statsmodels``
    (que o ``px.trendline`` exigiria e não está nas dependências do portal).
    """
    if _esta_vazio(df) or not _coluna_existe(df, col_x) or not _coluna_existe(df, col_y):
        return figura_vazia(titulo, "Sem dados para a dispersão.")
    colunas = [col_x, col_y]
    colunas += [c for c in (col_grupo, tamanho) if _coluna_existe(df, c) and c not in colunas]
    dados = df[colunas].copy()
    dados[col_x] = pd.to_numeric(dados[col_x], errors="coerce")
    dados[col_y] = pd.to_numeric(dados[col_y], errors="coerce")
    dados = dados.dropna(subset=[col_x, col_y])
    if len(dados) < 2:
        return figura_vazia(titulo)
    if _coluna_existe(dados, col_grupo):
        dados[col_grupo] = dados[col_grupo].astype(str)
    fig = px.scatter(
        dados,
        x=col_x,
        y=col_y,
        color=col_grupo if _coluna_existe(dados, col_grupo) else None,
        size=tamanho if _coluna_existe(dados, tamanho) else None,
        color_discrete_sequence=PALETA_TOTALE,
        opacity=opacidade,
        labels=_rotulos(rotulos, {"x": col_x, "y": col_y, "color": col_grupo or ""}),
    )
    fig.update_traces(marker_line_color="#FFFFFF", marker_line_width=0.8)
    if tendencia == "linear":
        try:
            coeficientes = np.polyfit(dados[col_x].to_numpy(), dados[col_y].to_numpy(), 1)
            reta_x = np.array([float(dados[col_x].min()), float(dados[col_x].max())])
            reta_y = np.polyval(coeficientes, reta_x)
            fig.add_trace(
                go.Scatter(
                    x=reta_x,
                    y=reta_y,
                    mode="lines",
                    name=rotulo_tendencia,
                    line_color=LARANJA_TOTALE,
                    line_width=2.2,
                    line_dash="dash",
                    hovertemplate=f"{rotulo_tendencia}: %{{y:.1f}}<extra></extra>",
                )
            )
        except (ValueError, TypeError, np.linalg.LinAlgError):
            logger.debug("Reta de tendência não calculável.", exc_info=True)
    return aplicar_tema(
        fig,
        titulo=titulo or None,
        altura=altura,
        hover_unificado=False,
        legenda=_coluna_existe(dados, col_grupo) or tendencia == "linear",
    )


# ====================================================
# 🔥 BLOCO 5: MAPAS DE CALOR, CALENDÁRIO E DENSIDADE
# ====================================================
def grafico_mapa_calor(
    df: pd.DataFrame,
    col_x: str | None = None,
    col_y: str | None = None,
    col_valor: str | None = None,
    *,
    matriz: pd.DataFrame | None = None,
    titulo: str = "",
    altura: int = 400,
    escala: Literal["totale", "divergente", "azul", "laranja"] = "totale",
    rotulos: Mapping[str, str] | None = None,
    mostrar_valores: bool = False,
) -> go.Figure:
    """Heatmap a partir de uma matriz pronta ou de colunas longas (x, y, valor)."""
    escalas = {
        "totale": ESCALA_TOTALE,
        "divergente": ESCALA_DIVERGENTE_TOTALE,
        "azul": [[0.0, "#F4F7FC"], [1.0, AZUL_TOTALE]],
        "laranja": [[0.0, "#FFF7ED"], [1.0, LARANJA_ESCURO]],
    }
    if matriz is not None and isinstance(matriz, pd.DataFrame) and not matriz.empty:
        dados_matriz = matriz.apply(pd.to_numeric, errors="coerce")
        fig = px.imshow(
            dados_matriz,
            color_continuous_scale=escalas.get(escala, ESCALA_TOTALE),
            aspect="auto",
            labels=_rotulos(rotulos, {"color": ""}),
        )
        _textos_matriz(fig, dados_matriz, mostrar_valores)
        return aplicar_tema(
            fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=False
        )

    if (
        _esta_vazio(df)
        or not _coluna_existe(df, col_x)
        or not _coluna_existe(df, col_y)
        or not _coluna_existe(df, col_valor)
    ):
        return figura_vazia(titulo, "Informe matriz ou as colunas x, y e valor.")
    largo = df.pivot_table(
        index=col_y, columns=col_x, values=col_valor, aggfunc="sum", fill_value=0.0
    )
    if largo.empty:
        return figura_vazia(titulo)
    fig = px.imshow(
        largo,
        color_continuous_scale=escalas.get(escala, ESCALA_TOTALE),
        aspect="auto",
        labels=_rotulos(
            rotulos, {"x": str(col_x), "y": str(col_y), "color": str(col_valor)}
        ),
    )
    _textos_matriz(fig, largo, mostrar_valores)
    return aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=False)


def grafico_calendario(
    serie: pd.Series | pd.DataFrame,
    *,
    col_data: str | None = None,
    col_valor: str | None = None,
    titulo: str = "Calendário de produção",
    altura: int = 300,
    escala: Literal["totale", "azul", "laranja"] = "totale",
    mostrar_valores: bool = False,
) -> go.Figure:
    """Heatmap calendário: dia da semana × semana, ideal para sazonalidade."""
    escalas = {
        "totale": ESCALA_TOTALE,
        "azul": [[0.0, "#F4F7FC"], [1.0, AZUL_TOTALE]],
        "laranja": [[0.0, "#FFF7ED"], [1.0, LARANJA_ESCURO]],
    }
    if isinstance(serie, pd.DataFrame):
        if not col_data or col_data not in serie.columns:
            return figura_vazia(titulo, "Informe a coluna de data do DataFrame.")
        dados = pd.DataFrame(
            {
                "data": pd.to_datetime(serie[col_data], errors="coerce", dayfirst=True),
                "valor": (
                    pd.to_numeric(serie[col_valor], errors="coerce")
                    if col_valor and col_valor in serie.columns
                    else 1.0
                ),
            }
        ).dropna(subset=["data"])
    else:
        if serie is None or serie.empty:
            return figura_vazia(titulo)
        indices = pd.to_datetime(pd.Series(np.asarray(serie.index)), errors="coerce").to_numpy()
        valores = pd.to_numeric(serie, errors="coerce").to_numpy()
        dados = pd.DataFrame({"data": indices, "valor": valores}).dropna()
    if dados.empty:
        return figura_vazia(titulo)

    dados["data"] = dados["data"].dt.normalize()
    dados["dia_semana"] = dados["data"].dt.weekday
    # Início da semana (segunda-feira) calculado de forma vetorial — sem .apply.
    dados["semana"] = dados["data"] - pd.to_timedelta(dados["data"].dt.weekday, unit="D")
    matriz = dados.pivot_table(index="dia_semana", columns="semana", values="valor", aggfunc="sum")
    if matriz.empty:
        return figura_vazia(titulo)
    matriz.index = [_DIAS_SEMANA[i] if i < 7 else str(i) for i in matriz.index]
    fig = px.imshow(
        matriz,
        color_continuous_scale=escalas.get(escala, ESCALA_TOTALE),
        aspect="auto",
        labels={"x": "Semana", "y": "", "color": ""},
    )
    _textos_matriz(fig, matriz, mostrar_valores)
    fig.update_xaxes(
        tickformat="%d/%m",
        tickangle=-45,
        tickfont={"size": 10},
        dtick=max(1, len(matriz.columns) // 12),
    )
    return aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=False)


def grafico_densidade(
    df: pd.DataFrame,
    col_x: str,
    col_y: str,
    *,
    tipo: Literal["heatmap", "contorno"] = "heatmap",
    titulo: str = "",
    altura: int = 380,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Densidade 2D (heatmap ou contorno) com a escala sequencial da marca."""
    if _esta_vazio(df) or not _coluna_existe(df, col_x) or not _coluna_existe(df, col_y):
        return figura_vazia(titulo, "Sem dados para a densidade.")
    dados = df[[col_x, col_y]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(dados) < 4:
        return figura_vazia(titulo, "Amostra pequena demais para estimar densidade.")
    rotulos_eixo = _rotulos(rotulos, {"x": col_x, "y": col_y, "color": ""})
    if tipo == "contorno":
        fig = px.density_contour(dados, x=col_x, y=col_y, labels=rotulos_eixo)
        fig.update_traces(line_color=AZUL_TOTALE, showscale=False)
    else:
        fig = px.density_heatmap(
            dados,
            x=col_x,
            y=col_y,
            color_continuous_scale=ESCALA_TOTALE,
            labels=rotulos_eixo,
        )
    return aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=False)


# ====================================================
# 🎯 BLOCO 6: METAS — RADAR, CASCATA, BULLET E GAUGE
# ====================================================
def grafico_radar(
    categorias: Sequence[Any],
    valores: Sequence[float],
    *,
    comparativo: Sequence[float] | None = None,
    rotulo_serie: str = "Atual",
    rotulo_comparativo: str = "Referência",
    titulo: str = "",
    altura: int = 380,
    cor: str = AZUL_TOTALE,
    cor_comparativo: str = LARANJA_TOTALE,
    preencher: bool = True,
) -> go.Figure:
    """Perfil multivariado (radar) — útil para indicadores por dimensão."""
    eixos = [str(c) for c in categorias]
    if not eixos:
        return figura_vazia(titulo, "Sem dimensões para o radar.")
    serie = [float(v) for v in pd.to_numeric(pd.Series(list(valores)), errors="coerce").fillna(0.0)]
    if not serie:
        return figura_vazia(titulo)
    fechamento = eixos + [eixos[0]]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=serie + [serie[0]],
            theta=fechamento,
            name=rotulo_serie,
            mode="lines+markers",
            line_color=cor,
            line_width=2.2,
            marker_size=6,
            fill="toself" if preencher else "none",
            fillcolor=f"{cor}22" if preencher else None,
            hovertemplate=f"{rotulo_serie}: %{{r:.1f}}<extra>%{{theta}}</extra>",
        )
    )
    if comparativo is not None:
        base = [float(v) for v in pd.to_numeric(pd.Series(list(comparativo)), errors="coerce").fillna(0.0)]
        if base:
            fig.add_trace(
                go.Scatterpolar(
                    r=base + [base[0]],
                    theta=fechamento,
                    name=rotulo_comparativo,
                    mode="lines+markers",
                    line_color=cor_comparativo,
                    line_width=2,
                    line_dash="dash",
                    marker_size=5,
                    fill="none",
                    hovertemplate=f"{rotulo_comparativo}: %{{r:.1f}}<extra>%{{theta}}</extra>",
                )
            )
    aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=True)
    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "gridcolor": GRADE,
                "linecolor": BORDA,
                "tickfont": {"size": 10, "color": TEXTO_SECUNDARIO},
                "range": [0, max(serie + ([max(base)] if comparativo is not None and base else [])) * 1.15],
            },
            "angularaxis": {
                "gridcolor": GRADE,
                "linecolor": BORDA,
                "tickfont": {"size": 11.5, "color": TEXTO_PRIMARIO},
            },
            "bgcolor": "rgba(0,0,0,0)",
        },
        margin={"t": 54, "b": 30, "l": 40, "r": 40},
    )
    return fig


def grafico_cascata(
    df: pd.DataFrame,
    col_categoria: str,
    col_valor: str,
    *,
    titulo: str = "",
    altura: int = 380,
    incluir_total: bool = True,
    rotulo_total: str = "Total",
    cor_positivo: str = AZUL_TOTALE,
    cor_negativo: str = LARANJA_TOTALE,
    cor_total: str = AZUL_ESCURO,
) -> go.Figure:
    """Ponte (waterfall) de contribuições positivas e negativas até o total."""
    if _esta_vazio(df) or not _coluna_existe(df, col_categoria) or not _coluna_existe(df, col_valor):
        return figura_vazia(titulo, "Sem dados para a cascata.")
    dados = df[[col_categoria, col_valor]].copy()
    dados[col_categoria] = dados[col_categoria].astype(str)
    dados[col_valor] = pd.to_numeric(dados[col_valor], errors="coerce").fillna(0.0)
    dados = dados.groupby(col_categoria, as_index=False)[col_valor].sum()
    if dados.empty:
        return figura_vazia(titulo)
    categorias = list(dados[col_categoria])
    valores = [float(v) for v in dados[col_valor]]
    medidas: list[str] = ["relative"] * len(valores)
    if incluir_total:
        categorias = [*categorias, rotulo_total]
        valores = [*valores, float(sum(valores))]
        medidas = [*medidas, "total"]
    fig = go.Figure(
        go.Waterfall(
            x=categorias,
            y=valores,
            measure=medidas,
            orientation="v",
            increasing={"marker": {"color": cor_positivo}},
            decreasing={"marker": {"color": cor_negativo}},
            totals={"marker": {"color": cor_total}},
            connector={"line": {"color": BORDA, "width": 1}},
            text=[_numero_br(v) for v in valores],
            textposition="outside",
            hovertemplate="%{x}: %{y:.0f}<extra></extra>",
        )
    )
    return aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False, legenda=False)


def grafico_bullet(
    valor: float,
    *,
    meta: float = 100.0,
    titulo: str = "",
    rotulo: str = "",
    altura: int = 150,
    faixas: Sequence[float] | None = None,
) -> go.Figure:
    """Bullet chart compacto de atingimento (ocupa pouco espaço vertical)."""
    try:
        valor_f = float(valor)
    except (TypeError, ValueError):
        valor_f = 0.0
    try:
        meta_f = float(meta)
    except (TypeError, ValueError):
        meta_f = 100.0
    passos = list(faixas) if faixas else [50.0, 85.0, 100.0]
    teto = max([valor_f, meta_f, *passos] + [1.0]) * 1.12
    cores_faixa = ["#F1F5F9", "#E8EEF8", "#DCE6F5", "#CFDCF0"]
    steps = []
    anterior = 0.0
    for indice, limite in enumerate([*passos, teto]):
        steps.append(
            {"range": [anterior, limite], "color": cores_faixa[indice % len(cores_faixa)]}
        )
        anterior = limite
    fig = go.Figure(
        go.Indicator(
            mode="number+gauge",
            value=valor_f,
            number={
                "font": {"family": FONTE_TITULO, "size": 24, "color": TEXTO_PRIMARIO},
                "suffix": "%" if meta_f == 100.0 else "",
            },
            title={"text": rotulo or titulo, "font": {"size": 12, "color": TEXTO_SECUNDARIO}},
            gauge={
                "shape": "bullet",
                "bar": {"color": AZUL_TOTALE if valor_f >= meta_f else LARANJA_TOTALE, "thickness": 0.55},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": steps,
                "threshold": {
                    "line": {"color": LARANJA_ESCURO, "width": 3},
                    "thickness": 0.95,
                    "value": meta_f,
                },
                "axis": {
                    "range": [0, teto],
                    "tickfont": {"size": 10, "color": TEXTO_SECUNDARIO},
                    "ticks": "",
                },
            },
        )
    )
    _tema_registrado()
    fig.update_layout(
        template=NOME_TEMA,
        height=altura,
        margin={"t": 30 if rotulo or titulo else 10, "b": 8, "l": 20, "r": 20},
    )
    return fig


def grafico_gauge(
    valor_pct: float,
    *,
    titulo: str = "",
    meta_pct: float = 100.0,
    faixas: tuple[float, float] = (60.0, 85.0),
    altura: int = 240,
    rotulo: str = "",
) -> go.Figure:
    """Gauge semicircular de atingimento com semáforo nas cores da marca."""
    try:
        pct = max(0.0, float(valor_pct))
    except (TypeError, ValueError):
        pct = 0.0
    faixa1, faixa2 = faixas
    if pct >= meta_pct:
        cor_barra = AZUL_TOTALE
    elif pct >= faixa2:
        cor_barra = AZUL_CLARO
    elif pct >= faixa1:
        cor_barra = LARANJA_TOTALE
    else:
        cor_barra = LARANJA_ESCURO
    teto = max(120.0, pct * 1.15)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            number={"suffix": "%", "font": {"family": FONTE_TITULO, "size": 28, "color": TEXTO_PRIMARIO}},
            title={"text": rotulo or titulo, "font": {"size": 12.5, "color": TEXTO_SECUNDARIO}},
            gauge={
                "axis": {"range": [0, teto], "tickwidth": 1, "tickcolor": BORDA},
                "bar": {"color": cor_barra, "thickness": 0.28},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, faixa1], "color": "#FFF7ED"},
                    {"range": [faixa1, faixa2], "color": "#FFEDD5"},
                    {"range": [faixa2, meta_pct], "color": "#E8EEF8"},
                    {"range": [meta_pct, teto], "color": "#DCE6F5"},
                ],
                "threshold": {
                    "line": {"color": LARANJA_ESCURO, "width": 3},
                    "thickness": 0.75,
                    "value": meta_pct,
                },
            },
        )
    )
    _tema_registrado()
    fig.update_layout(
        template=NOME_TEMA,
        height=altura,
        margin={"t": 44, "b": 8, "l": 24, "r": 24},
    )
    return fig


def grafico_progresso(
    valores: Mapping[str, float] | pd.Series,
    *,
    meta: float = 100.0,
    titulo: str = "",
    altura: int | None = None,
    cor_atingido: str = AZUL_TOTALE,
    cor_pendente: str = LARANJA_TOTALE,
    unidade: str = "%",
    top: int | None = None,
) -> go.Figure:
    """Barras horizontais de atingimento por item (progresso visual compacto)."""
    if isinstance(valores, pd.Series):
        serie = pd.to_numeric(valores, errors="coerce").dropna()
        itens = {str(k): float(v) for k, v in serie.items()}
    elif isinstance(valores, Mapping):
        itens = {}
        for chave, bruto in valores.items():
            try:
                itens[str(chave)] = float(bruto)
            except (TypeError, ValueError):
                continue
    else:
        itens = {}
    if not itens:
        return figura_vazia(titulo, "Sem valores de progresso.")
    ordenado = sorted(itens.items(), key=lambda par: par[1], reverse=True)
    if top:
        ordenado = ordenado[: max(1, int(top))]
    ordenado = ordenado[::-1]
    nomes = [item[0] for item in ordenado]
    numeros = [item[1] for item in ordenado]
    cores = [cor_atingido if v >= meta else cor_pendente for v in numeros]
    fig = go.Figure(
        go.Bar(
            x=numeros,
            y=nomes,
            orientation="h",
            marker_color=cores,
            marker_cornerradius=5,
            marker_line_width=0,
            text=[f"{_numero_br(v, 1)}{unidade}" for v in numeros],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x:.1f}<extra></extra>",
        )
    )
    if meta and meta > 0:
        fig.add_vline(
            x=meta,
            line_color=AZUL_ESCURO,
            line_width=1.6,
            line_dash="dot",
            annotation_text=f"Meta {_numero_br(meta)}{unidade}",
            annotation_position="top",
            annotation_font_size=10,
        )
    aplicar_tema(fig, titulo=titulo or None, altura=altura or max(200, 32 * len(nomes) + 80), legenda=False)
    fig.update_layout(bargap=0.36, xaxis_range=[0, max([*numeros, meta or 0]) * 1.18])
    return fig


def grafico_barras_polar(
    df: pd.DataFrame,
    col_theta: str,
    col_r: str,
    *,
    col_grupo: str | None = None,
    titulo: str = "",
    altura: int = 420,
    rotulos: Mapping[str, str] | None = None,
) -> go.Figure:
    """Rosa dos ventos (barras polares) — distribuição cíclica (hora, dia, setor)."""
    if _esta_vazio(df) or not _coluna_existe(df, col_theta) or not _coluna_existe(df, col_r):
        return figura_vazia(titulo, "Sem dados para o gráfico polar.")
    dados = df[[col_theta, col_r] + ([col_grupo] if _coluna_existe(df, col_grupo) else [])].copy()
    dados[col_theta] = dados[col_theta].astype(str)
    dados[col_r] = pd.to_numeric(dados[col_r], errors="coerce").fillna(0.0)
    if _coluna_existe(dados, col_grupo):
        dados[col_grupo] = dados[col_grupo].astype(str)
    fig = px.bar_polar(
        dados,
        r=col_r,
        theta=col_theta,
        color=col_grupo if _coluna_existe(dados, col_grupo) else None,
        color_discrete_sequence=PALETA_TOTALE,
        labels=_rotulos(rotulos, {"r": col_r, "theta": col_theta, "color": col_grupo or ""}),
    )
    aplicar_tema(fig, titulo=titulo or None, altura=altura, hover_unificado=False)
    fig.update_layout(
        polar={
            "bgcolor": "rgba(0,0,0,0)",
            "radialaxis": {"gridcolor": GRADE, "linecolor": BORDA, "ticksuffix": ""},
            "angularaxis": {"gridcolor": GRADE, "linecolor": BORDA},
        },
        bargap=0.18,
    )
    return fig


# ====================================================
# 🏭 BLOCO 7: FÁBRICA ÚNICA (DISPATCH POR TIPO)
# ====================================================
def criar_grafico(tipo: str, *args: Any, **kwargs: Any) -> go.Figure:
    """Fábrica única: escolhe o gráfico por ``tipo`` e repassa os argumentos.

    Exemplo::

        fig = criar_grafico("barras", df, "BASE", "OS", cor="STATUS", modo="empilhado")
        fig = criar_grafico("radar", ["SLA", "Retorno", "Meta"], [92, 8, 95])

    Tipos aceitos: ``TIPOS_GRAFICO``. Tipo desconhecido devolve uma figura com
    aviso (nunca levanta exceção no meio de um dashboard).
    """
    mapa = {
        "linha": grafico_linha,
        "area": grafico_area,
        "barras": grafico_barras,
        "ranking": grafico_ranking,
        "pizza": grafico_pizza,
        "donut": grafico_donut,
        "dispersao": grafico_dispersao,
        "histograma": grafico_histograma,
        "caixa": grafico_caixa,
        "violino": grafico_violino,
        "calor": grafico_mapa_calor,
        "calendario": grafico_calendario,
        "treemap": grafico_treemap,
        "sunburst": grafico_sunburst,
        "funil": grafico_funil,
        "radar": grafico_radar,
        "cascata": grafico_cascata,
        "bullet": grafico_bullet,
        "gauge": grafico_gauge,
        "polar": grafico_barras_polar,
        "densidade": grafico_densidade,
        "combinado": grafico_combinado,
        "progresso": grafico_progresso,
        "comparativo": grafico_comparativo,
    }
    chave = str(tipo or "").strip().lower().replace("ç", "c").replace("ã", "a").replace("é", "e")
    sinonimos = {
        "barra": "barras",
        "colunas": "barras",
        "barrash": "barras",
        "pie": "pizza",
        "donut_chart": "donut",
        "rosquinha": "donut",
        "heatmap": "calor",
        "mapacalor": "calor",
        "calendarioheatmap": "calendario",
        "box": "caixa",
        "boxplot": "caixa",
        "violin": "violino",
        "scatter": "dispersao",
        "dispersao_bolhas": "dispersao",
        "waterfall": "cascata",
        "ponte": "cascata",
        "funnel": "funil",
        "rose": "polar",
        "rosadosventos": "polar",
        "progress": "progresso",
        "comparacao": "comparativo",
        "combo": "combinado",
        "barraselinha": "combinado",
    }
    chave = sinonimos.get(chave, chave)
    fabrica = mapa.get(chave)
    if fabrica is None:
        logger.warning("Tipo de gráfico desconhecido: %r", tipo)
        return figura_vazia(
            str(kwargs.get("titulo", "")),
            f"Tipo de gráfico '{tipo}' não disponível. Use um de: {', '.join(TIPOS_GRAFICO)}.",
        )
    try:
        return fabrica(*args, **kwargs)
    except Exception:  # pragma: no cover - proteção de runtime em painel
        logger.exception("Falha ao montar o gráfico '%s'.", chave)
        return figura_vazia(str(kwargs.get("titulo", "")), "Não foi possível montar este gráfico.")


__all__ = [
    "AZUL_CLARO",
    "AZUL_ESCURO",
    "AZUL_TOTALE",
    "ESCALA_DIVERGENTE_TOTALE",
    "ESCALA_TOTALE",
    "FONTE_TEXTO",
    "FONTE_TITULO",
    "LARANJA_CLARO",
    "LARANJA_ESCURO",
    "LARANJA_TOTALE",
    "NOME_TEMA",
    "PALETA_TOTALE",
    "TIPOS_GRAFICO",
    "VERSAO_GRAFICOS",
    "aplicar_tema",
    "config_minimalista",
    "cores_por_categoria",
    "criar_grafico",
    "figura_vazia",
    "grafico_area",
    "grafico_barras",
    "grafico_barras_polar",
    "grafico_bullet",
    "grafico_calendario",
    "grafico_cascata",
    "grafico_caixa",
    "grafico_combinado",
    "grafico_comparativo",
    "grafico_densidade",
    "grafico_dispersao",
    "grafico_distribuicao",
    "grafico_donut",
    "grafico_funil",
    "grafico_gauge",
    "grafico_histograma",
    "grafico_linha",
    "grafico_mapa_calor",
    "grafico_pizza",
    "grafico_progresso",
    "grafico_radar",
    "grafico_ranking",
    "grafico_sunburst",
    "grafico_treemap",
    "grafico_violino",
    "interpolar_cor",
    "paleta_totale",
    "registrar_tema_totale",
    "render_grafico",
    "render_graficos_em_abas",
]
