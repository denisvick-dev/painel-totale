"""Testes dos cartões de KPI avançados (``components.kpi_cards``).

Cobrem a matemática de variação, a geração do sparkline SVG, o contrato de
renderização (``st.metric`` → cartão TOTALE) e a delegação do Dashboard Kit.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import components.dashboard_kit as kit  # noqa: E402
import components.kpi_cards as kpi  # noqa: E402
from components.componentes import Cores  # noqa: E402

AZUL_OFICIAL = "#012869"
LARANJA_OFICIAL = "#F37C04"


def _rodar(codigo: str) -> AppTest:
    app = AppTest.from_string(codigo, default_timeout=60).run()
    assert not list(app.exception), [str(e.value) for e in app.exception]
    return app


def _html(app: AppTest) -> str:
    return "\n".join(str(getattr(bloco, "value", "")) for bloco in app.get("html"))


# ====================================================
# MATEMÁTICA DE VARIAÇÃO
# ====================================================
def test_variacao_percentual_preserva_sinal_e_base_negativa() -> None:
    assert kpi.calcular_variacao_pct(110, 100) == pytest.approx(10.0)
    assert kpi.calcular_variacao_pct(90, 100) == pytest.approx(-10.0)
    assert kpi.calcular_variacao_pct(-80, -100) == pytest.approx(20.0)


def test_variacao_percentual_devolve_none_em_casos_invalidos() -> None:
    assert kpi.calcular_variacao_pct(None, 100) is None
    assert kpi.calcular_variacao_pct(100, None) is None
    assert kpi.calcular_variacao_pct(100, 0) is None
    assert kpi.calcular_variacao_pct(float("nan"), 100) is None
    assert kpi.calcular_variacao_pct("abc", 100) is None
    assert kpi.calcular_variacao_pct(float("inf"), 100) is None


def test_rotulo_tendencia_formato_pt_br_e_direcoes() -> None:
    rotulo, direcao = kpi.rotulo_tendencia(125, 100)
    assert rotulo == "+25,0%"
    assert direcao == "up"

    rotulo, direcao = kpi.rotulo_tendencia(80, 100)
    assert rotulo == "−20,0%"  # sinal tipográfico U+2212
    assert direcao == "down"

    _, direcao = kpi.rotulo_tendencia(100.01, 100)
    assert direcao == "neutral"

    assert kpi.rotulo_tendencia(None, 100) == ("", "none")


def test_rotulo_tendencia_inverso_para_metricas_menor_melhor() -> None:
    assert kpi.rotulo_tendencia(80, 100, inverso=True)[1] == "up"
    assert kpi.rotulo_tendencia(120, 100, inverso=True)[1] == "down"


def test_dashboard_kit_delega_para_kpi_cards() -> None:
    """Fonte única da matemática: o kit reexporta as funções dos cartões."""
    assert kit.calcular_variacao_pct is kpi.calcular_variacao_pct
    assert kit.rotulo_tendencia is kpi.rotulo_tendencia
    assert kit.render_kpi_row is kpi.render_kpi_row


def test_direcao_delta_entende_texto_livre_e_delta_color() -> None:
    assert kpi.direcao_delta("+12,5%") == "up"
    assert kpi.direcao_delta("−3,1%") == "down"
    assert kpi.direcao_delta("-3.1%", delta_color="inverse") == "up"
    assert kpi.direcao_delta("", delta_color="off") == "none"
    assert kpi.direcao_delta(None) == "none"
    assert kpi.direcao_delta("Sem OS") == "neutral"


def test_resumo_de_serie_traz_valor_atual_delta_e_sparkline() -> None:
    serie = pd.Series([10.0, 30.0, 20.0, 40.0])
    resumo = kpi.resumo_de_serie(serie)

    assert resumo["atual"] == pytest.approx(40.0)
    assert resumo["anterior"] == pytest.approx(20.0)
    assert resumo["delta"] == "+100,0%"
    assert resumo["delta_tipo"] == "up"
    assert resumo["pontos"] == 4
    assert list(resumo["sparkline"]) == [10.0, 30.0, 20.0, 40.0]


def test_resumo_de_serie_vazio_nao_quebra() -> None:
    resumo = kpi.resumo_de_serie(pd.Series(dtype="float64"))

    assert resumo["pontos"] == 0
    assert resumo["valor"] == "—"
    assert resumo["delta"] == ""
    assert resumo["delta_tipo"] == "none"
    assert resumo["sparkline"] == []


# ====================================================
# SPARKLINE SVG
# ====================================================
def test_sparkline_svg_tem_polyline_area_e_ponto_final() -> None:
    svg = kpi.sparkline_svg([1, 4, 2, 8, 6], cor=AZUL_OFICIAL)

    assert svg.startswith("<svg")
    assert "<polyline" in svg
    assert "<path" in svg  # área preenchida
    assert "<circle" in svg  # ponto final
    assert AZUL_OFICIAL in svg
    assert 'role="img"' in svg and "aria-label" in svg
    assert svg.count("<svg") == 1 and svg.count("</svg>") == 1


def test_sparkline_svg_casos_degenerados() -> None:
    assert kpi.sparkline_svg(None) == ""
    assert kpi.sparkline_svg([]) == ""
    constante = kpi.sparkline_svg([5, 5, 5])
    assert "<polyline" in constante  # linha reta, sem divisão por zero
    com_nan = kpi.sparkline_svg([1.0, float("nan"), 3.0])
    assert "<polyline" in com_nan


def test_sparkline_svg_normaliza_serie_pandas() -> None:
    serie = pd.Series([3.0, 1.0, 2.0])
    assert kpi.sparkline_svg(serie) == kpi.sparkline_svg([3.0, 1.0, 2.0])


# ====================================================
# RENDERIZAÇÃO (AppTest)
# ====================================================
def test_render_metric_e_substituto_direto_do_st_metric() -> None:
    app = _rodar(
        """
        from components.kpi_cards import render_metric
        render_metric("Municípios", 12, delta="+3", help="Cidades atendidas")
        """
    )
    corpo = _html(app)

    assert "kpi-avancado" in corpo
    assert "Municípios" in corpo
    assert "12" in corpo
    assert "+3" in corpo
    assert "Cidades atendidas" in corpo
    # Nenhum st.metric nativo foi usado.
    assert len(app.metric) == 0


def test_cartao_avancado_traz_sparkline_progresso_e_cores_da_marca() -> None:
    app = _rodar(
        """
        import pandas as pd
        from components.kpi_cards import render_kpi_card
        serie = pd.Series([4.0, 6.0, 5.0, 9.0, 12.0])
        render_kpi_card(
            label="OS executadas",
            valor="1.248",
            delta="+12,5%",
            sparkline=serie,
            progresso=(1248, 1500),
            meta_rotulo="meta 1.500",
            tema="laranja",
            rodape="Atualizado há 3 min",
            ajuda="Total de OS do mês",
        )
        """
    )
    corpo = _html(app)

    assert "kpi-avancado__spark-svg" in corpo
    assert "kpi-avancado__trilho" in corpo and "kpi-avancado__cheio" in corpo
    assert "meta 1.500" in corpo
    assert "Atualizado há 3 min" in corpo
    assert LARANJA_OFICIAL.lower() in corpo.lower()
    assert 'aria-label="OS executadas: 1.248"' in corpo


def test_render_kpi_row_quebra_em_multiplas_linhas() -> None:
    app = _rodar(
        """
        from components.kpi_cards import render_kpi_row
        specs = [
            {"label": f"KPI {i}", "valor": str(i * 10), "delta": f"+{i}%"}
            for i in range(1, 6)
        ]
        render_kpi_row(specs, colunas=2)
        """
    )
    corpo = _html(app)

    assert corpo.count("kpi-avancado__rotulo") == 5
    # 5 cartões em 2 colunas → 3 chamadas de st.columns (2 colunas cada) = 6.
    assert len(app.get("columns")) == 6


def test_render_kpi_de_serie_calcula_valor_e_tendencia() -> None:
    app = _rodar(
        """
        import pandas as pd
        from components.kpi_cards import render_kpi_de_serie
        serie = pd.Series([10.0, 20.0, 30.0], index=pd.date_range("2026-10-01", periods=3))
        render_kpi_de_serie(label="Volume", serie=serie, unidade=" OS", icone="trending_up")
        """
    )
    corpo = _html(app)

    assert "Volume" in corpo
    assert "30" in corpo  # último valor da série
    assert "+50,0%" in corpo  # variação contra o ponto anterior
    assert "kpi-avancado__spark-svg" in corpo


def test_cartoes_nao_usam_html_nao_escapado_do_usuario() -> None:
    app = _rodar(
        """
        from components.kpi_cards import render_kpi_card
        render_kpi_card(
            label="<script>alert(1)</script>",
            valor="<b>7</b>",
            ajuda='<img src=x onerror="alert(2)">',
        )
        """
    )
    corpo = _html(app)

    # Rótulo/valor escapados: nenhum tag ou handler cru sobrevive.
    assert "<script>" not in corpo
    assert "&lt;script&gt;" in corpo
    assert '<img src=x' not in corpo
    assert 'onerror="alert(2)"' not in corpo
    assert "&quot;" in corpo  # aspas escapadas dentro do atributo title


def test_css_dos_cartões_cobre_variantes_e_temas() -> None:
    css = kpi.css_kpi_avancado()

    for classe in (
        ".kpi-avancado",
        ".kpi-avancado__valor",
        ".kpi-avancado__rotulo",
        ".kpi-avancado__delta",
        ".kpi-avancado__spark",
        ".kpi-avancado__trilho",
        ".kpi-avancado__cheio",
        ".kpi-avancado--compacto",
        ".kpi-avancado--colorida",
        "@media print",
    ):
        assert classe in css, classe
    assert css.count("{") == css.count("}")
    # Acessibilidade de foco fica no CSS global (css_global.css_acessibilidade).
    # As cores da marca vêm inline por tema; o CSS fixa os estados semânticos.
    assert Cores.SUCESSO.lower() in css.lower()
    assert Cores.ALERTA.lower() in css.lower()
    assert "var(--cor-borda" in css
    # Escopo no corpo da página: nunca mexe na sidebar.
    assert 'data-testid="stSidebar"' not in css
    assert '[data-testid="stMain"]' in css


def test_cores_oficiais_sao_a_base_dos_temas() -> None:
    assert Cores.PRIMARIA == AZUL_OFICIAL
    assert Cores.SECUNDARIA == LARANJA_OFICIAL

    app = _rodar(
        """
        from components.kpi_cards import render_kpi_card
        render_kpi_card(label="Azul", valor="1", tema="azul")
        render_kpi_card(label="Laranja", valor="2", tema="laranja")
        """
    )
    corpo = _html(app).lower()

    assert AZUL_OFICIAL.lower() in corpo
    assert LARANJA_OFICIAL.lower() in corpo


def test_versao_do_modulo_e_exportada() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", kpi.VERSAO_KPI)
    assert set(kpi.__all__) <= set(dir(kpi))
    for nome in kpi.__all__:
        assert hasattr(kpi, nome), nome
