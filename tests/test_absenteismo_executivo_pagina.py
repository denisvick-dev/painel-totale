"""Integração do painel executivo de presença com a planilha mensal."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from services.absenteismo import normalizar_registros
from services.lista_presenca import normalizar_planilha_lista_presenca

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = RAIZ / "pages" / "absenteismo.py"


def _dados_planilha() -> pd.DataFrame:
    return normalizar_planilha_lista_presenca(
        pd.DataFrame(
            {
                "RE": ["1", "2", "3"],
                "Login": ["Z1", "Z2", "Z3"],
                "Técnico": ["Ana", "Bia", "Caio"],
                "Monitor": ["Monitor A", "Monitor A", "Monitor B"],
                "Base": ["NET-ABCDM", "NET-ABCDM", "NET-LESTE"],
                "U.N.": ["ABCDM-TOTALE", "ABCDM-TOTALE", "LESTE"],
                "1/nov.": ["ATIVO", "FALTA", ""],
                "2/nov.": ["FALTA", "ATESTADO", "FALTA"],
                "3/nov.": ["", "ATIVO", "FOLGA"],
                "1/dez.": ["ATESTADO", "", "ATIVO"],
            }
        )
    )


def _rodar(monkeypatch) -> AppTest:
    import services.lista_presenca as lista_presenca

    dados = _dados_planilha()
    monkeypatch.setattr(
        lista_presenca,
        "carregar_planilha_lista_presenca",
        lambda **kwargs: dados.copy(),
    )
    app = AppTest.from_file(str(PAGINA), default_timeout=60)
    app.session_state["presenca_grade_snapshot"] = {
        "registros": normalizar_registros(None),
        "dias": [date(2026, 11, 1)],
        "pessoas": pd.DataFrame(
            [
                {
                    "RE": login,
                    "Login": login,
                    "Técnico": tecnico,
                    "Monitor": monitor,
                    "Base": "ABCDM-TOTALE",
                    "U.N.": unidade,
                }
                for login, tecnico, monitor, unidade in (
                    ("Z1", "Ana", "Monitor A", "ABCDM-TOTALE"),
                    ("Z2", "Bia", "Monitor A", "ABCDM-TOTALE"),
                    ("Z3", "Caio", "Monitor B", "LESTE"),
                )
            ]
        ),
    }
    return app.run()


def _valor_metrica(app: AppTest, rotulo: str) -> str:
    return next(metrica.value for metrica in app.metric if metrica.label == rotulo)


def test_painel_executivo_aplica_mes_filtros_ranking_donut_e_exportacao(monkeypatch):
    app = _rodar(monkeypatch)

    assert not app.exception
    assert _valor_metrica(app, "Técnicos") == "3"
    assert _valor_metrica(app, "FALTA + ATESTADO") == "4"
    assert len(app.get("plotly_chart")) == 5  # donut + 2 métricas × Monitor/Base
    assert any(
        botao.key == "presenca_exportar_executivo"
        for botao in app.get("download_button")
    )
    assert any("Alerta · técnicos com mais faltas e atestados" in item.value for item in app.subheader)

    app.selectbox(key="presenca_ext_monitor").set_value("Monitor A").run()
    assert not app.exception
    assert _valor_metrica(app, "Técnicos") == "2"
    assert _valor_metrica(app, "FALTA + ATESTADO") == "3"

    app.selectbox(key="presenca_ext_base").set_value("NET-LESTE").run()
    assert not app.exception
    assert _valor_metrica(app, "Técnicos") == "0"
    assert _valor_metrica(app, "% Presença") == "—"
    app.selectbox(key="presenca_ext_base").set_value("Todas").run()
    app.selectbox(key="presenca_ext_monitor").set_value("Todos").run()
    app.selectbox(key="presenca_ext_base").set_value("NET-LESTE").run()
    assert not app.exception
    assert _valor_metrica(app, "Técnicos") == "1"
    assert _valor_metrica(app, "FALTA + ATESTADO") == "1"

    app.selectbox(key="presenca_ext_base").set_value("Todas").run()
    app.selectbox(key="presenca_ext_mes").set_value("Dezembro").run()
    assert not app.exception
    assert _valor_metrica(app, "ATIVO") == "1"
    assert _valor_metrica(app, "ATESTADO") == "1"
    assert _valor_metrica(app, "Não preenchido") == "1"
    tabela = next(
        elemento.value
        for elemento in app.dataframe
        if "1/dez." in elemento.value.columns
    )
    assert "1/nov." not in tabela.columns
