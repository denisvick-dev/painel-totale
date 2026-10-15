"""Testes do Kit de Dashboards Aprimorados (`components/dashboard_kit.py`).

Cobertura:

1. Cálculos puros: variação percentual, rótulo de tendência e resumo de série
   (regras que alimentam os KPIs de todos os painéis);
2. Fábricas de gráficos Plotly: ranking, tendência, donut e gauge saem com os
   dados e o acabamento corporativo corretos;
3. CSS v2: seletores globais essenciais presentes e chaves balanceadas;
4. Integração: o entrypoint injeta o CSS v2 e os componentes de UI montam sem
   exceção via AppTest (grid de KPIs, filtros, exportação e insights).

Execução:

    python tests/test_dashboard_kit.py     # execução direta (stdlib + pytest)
    pytest tests/test_dashboard_kit.py     # via pytest
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from components import dashboard_kit as kit  # noqa: E402

# ---------------------------------------------------------------------------
# 1. Cálculos puros
# ---------------------------------------------------------------------------


def test_calcular_variacao_pct_basico_e_sinal() -> None:
    assert kit.calcular_variacao_pct(110, 100) == pytest.approx(10.0)
    assert kit.calcular_variacao_pct(90, 100) == pytest.approx(-10.0)
    # denominador negativo usa módulo, preservando o sinal da variação
    assert kit.calcular_variacao_pct(-80, -100) == pytest.approx(20.0)


def test_calcular_variacao_pct_casos_limite() -> None:
    assert kit.calcular_variacao_pct(None, 100) is None
    assert kit.calcular_variacao_pct(100, None) is None
    assert kit.calcular_variacao_pct(100, 0) is None
    assert kit.calcular_variacao_pct(float("nan"), 100) is None
    assert kit.calcular_variacao_pct("abc", 100) is None


def test_rotulo_tendencia_direcoes_e_formato_pt_br() -> None:
    rotulo, direcao = kit.rotulo_tendencia(125, 100)
    assert rotulo == "+25,0%"
    assert direcao == "up"

    rotulo, direcao = kit.rotulo_tendencia(80, 100)
    assert rotulo == "−20,0%"
    assert direcao == "down"

    # dentro da tolerância: neutro
    _, direcao = kit.rotulo_tendencia(100.01, 100)
    assert direcao == "neutral"

    # sem base de cálculo: sem rótulo
    assert kit.rotulo_tendencia(None, 100) == ("", "none")


def test_rotulo_tendencia_inverso_para_metricas_menor_melhor() -> None:
    _, direcao = kit.rotulo_tendencia(80, 100, inverso=True)
    assert direcao == "up"
    _, direcao = kit.rotulo_tendencia(120, 100, inverso=True)
    assert direcao == "down"


def test_resumo_periodo_total_media_e_dias_extremos() -> None:
    serie = pd.Series(
        [10.0, 20.0, 30.0],
        index=pd.to_datetime(["2026-10-05", "2026-10-06", "2026-10-07"]),
    )
    resumo = kit.resumo_periodo(serie)
    assert resumo["total"] == pytest.approx(60.0)
    assert resumo["media"] == pytest.approx(20.0)
    assert resumo["melhor"] == pytest.approx(30.0)
    assert pd.Timestamp(resumo["dia_melhor"]) == pd.Timestamp("2026-10-07")
    assert resumo["pior"] == pytest.approx(10.0)


def test_resumo_periodo_serie_vazia_e_nao_numerica() -> None:
    vazio = kit.resumo_periodo(pd.Series(dtype="float64"))
    assert vazio["total"] is None
    texto = kit.resumo_periodo(pd.Series(["a", "b"]))
    assert texto["total"] is None


# ---------------------------------------------------------------------------
# 2. Fábricas de gráficos
# ---------------------------------------------------------------------------


def test_grafico_barras_ranking_respeita_top_e_ordem() -> None:
    df = pd.DataFrame(
        {
            "BASE": [f"B{i}" for i in range(15)],
            "OS": list(range(15)),
        }
    )
    fig = kit.grafico_barras_ranking(df, "BASE", "OS", top=10)
    assert len(fig.data) == 1
    assert len(fig.data[0].y) == 10
    # barras horizontais em ordem crescente (maior no topo)
    valores = list(fig.data[0].x)
    assert valores == sorted(valores)
    assert max(valores) == 14
    assert fig.data[0].marker.cornerradius == 6


def test_grafico_linha_tendencia_tem_serie_media_movel_e_ultimo_ponto() -> None:
    serie = pd.Series(
        range(10, 30),
        index=pd.date_range("2026-10-01", periods=20, freq="D"),
        dtype="float64",
    )
    fig = kit.grafico_linha_tendencia(serie, titulo="Volumetria", media_movel=7)
    assert len(fig.data) == 3  # série + média móvel + último ponto
    assert fig.data[0].fill == "tozeroy"
    assert fig.layout.title.text == "Volumetria"
    assert fig.layout.hovermode == "x unified"


def test_grafico_linha_tendencia_serie_curta_sem_media_movel() -> None:
    serie = pd.Series([5.0, 8.0], index=pd.date_range("2026-10-01", periods=2))
    fig = kit.grafico_linha_tendencia(serie, media_movel=7)
    assert len(fig.data) == 2  # série + último ponto, sem média móvel


def test_grafico_donut_preserva_valores_e_total_no_centro() -> None:
    fig = kit.grafico_donut(["A", "B", "C"], [30, 20, 10], titulo="Mix")
    pizza = fig.data[0]
    assert list(pizza.values) == [30, 20, 10]
    assert pizza.hole == pytest.approx(0.56)
    anotacoes = fig.layout.annotations or ()
    assert any("60" in a.text for a in anotacoes)


def test_grafico_gauge_meta_threshold_na_meta_e_semaforo() -> None:
    fig = kit.grafico_gauge_meta(92.5, meta_pct=100.0)
    indicador = fig.data[0]
    assert indicador.value == pytest.approx(92.5)
    assert indicador.gauge.threshold.value == pytest.approx(100.0)

    # semáforo: verde em meta batida, vermelho abaixo da primeira faixa
    cor_ok = kit.grafico_gauge_meta(105).data[0].gauge.bar.color
    cor_ruim = kit.grafico_gauge_meta(30).data[0].gauge.bar.color
    assert cor_ok != cor_ruim

    # valor inválido não quebra: cai para 0%
    fig_invalido = kit.grafico_gauge_meta("abc")
    assert fig_invalido.data[0].value == pytest.approx(0.0)


def test_aplicar_tema_figura_define_acabamento_sem_tocar_nos_dados() -> None:
    import plotly.graph_objects as go

    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    kit.aplicar_tema_figura(fig, titulo="Teste", altura=320)
    assert fig.layout.height == 320
    assert fig.layout.hovermode == "x unified"
    assert fig.layout.legend.orientation == "h"
    assert list(fig.data[0].y) == [3, 4]


# ---------------------------------------------------------------------------
# 3. CSS v2 global
# ---------------------------------------------------------------------------


def test_css_dashboards_contem_seletores_globais_e_chaves_balanceadas() -> None:
    css = kit.css_dashboards()
    for trecho in (
        ".card-premium:hover",
        'data-testid="stPlotlyChart"',
        'data-testid="stMetric"',
        'data-testid="stTabs"',
        'data-testid="stExpander"',
        ":focus-visible",
        "::-webkit-scrollbar-thumb",
        'span[data-baseweb="tag"]',
    ):
        assert trecho in css, f"Trecho ausente no CSS v2: {trecho!r}"
    assert css.count("{") == css.count("}"), "Chaves desbalanceadas no CSS v2"
    # o CSS é global mas nunca pode tocar a sidebar (tema próprio)
    assert '[data-testid="stSidebar"]' not in css


def test_entrypoint_injeta_css_dos_dashboards() -> None:
    """O acabamento v2 vale para todas as páginas: nasce no entrypoint."""
    codigo = (RAIZ / "streamlit_app.py").read_text(encoding="utf-8")
    assert "from components.dashboard_kit import injetar_css_dashboards" in codigo
    assert "injetar_css_dashboards()" in codigo


# ---------------------------------------------------------------------------
# 4. Integração com AppTest (componentes de UI montam sem exceção)
# ---------------------------------------------------------------------------

_SCRIPT_UI = """
import pandas as pd
import streamlit as st

from components.dashboard_kit import (
    injetar_css_dashboards,
    render_barra_exportacao,
    render_filtros_dashboard,
    render_insights_automaticos,
    render_kpi_grid,
    render_toggle_autorefresh,
)

st.set_page_config(layout="wide")
injetar_css_dashboards()

render_kpi_grid(
    [
        {"label": "O.S.", "valor": "1.250", "sub": "no mês", "tema": "azul",
         "delta": "+12,5%", "delta_tipo": "up"},
        {"label": "Quebra", "valor": "3,2%", "tema": "verde", "delta": "−0,4%",
         "delta_tipo": "down"},
    ]
)

df = pd.DataFrame(
    {
        "BASE": ["LESTE", "OESTE", "LESTE"],
        "DATA": ["01/10/2026", "02/10/2026", "03/10/2026"],
        "OS": [10, 8, 12],
    }
)
filtrado = render_filtros_dashboard(
    df, {"BASE": "Base"}, chave="teste", coluna_data="DATA"
)
assert len(filtrado) == 3

render_barra_exportacao(filtrado, nome_arquivo="recorte", chave="teste")
render_insights_automaticos(
    filtrado, col_data="DATA", col_valor="OS", col_categoria="BASE"
)
render_toggle_autorefresh(chave="teste")
"""


def test_componentes_de_ui_montam_sem_excecao() -> None:
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_string(_SCRIPT_UI, default_timeout=60).run()
    assert not list(app.exception), f"Falhas: {list(app.exception)}"
    # filtros renderizam: 1 multiselect + 1 date_input + botão limpar
    assert len(app.multiselect) == 1
    assert len(app.date_input) == 1
    # exportação: dois downloads (CSV + Excel)
    assert len(app.get("download_button")) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
