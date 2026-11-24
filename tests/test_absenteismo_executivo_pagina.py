"""Integração do painel executivo de presença com a planilha mensal."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

from services.absenteismo import CHAVE_SESSAO_REGISTROS, normalizar_registros
from services.lista_presenca import normalizar_planilha_lista_presenca
from services.presenca_grade import CHAVE_SNAPSHOT

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


def _rodar(monkeypatch, snapshot=None) -> AppTest:
    import services.lista_presenca as lista_presenca

    dados = _dados_planilha()
    monkeypatch.setattr(
        lista_presenca,
        "carregar_planilha_lista_presenca",
        lambda **kwargs: dados.copy(),
    )
    if snapshot is None:
        snapshot = {
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
    app = AppTest.from_file(str(PAGINA), default_timeout=60)
    app.session_state[CHAVE_SNAPSHOT] = snapshot
    app.session_state[CHAVE_SESSAO_REGISTROS] = snapshot["registros"].copy()
    app.session_state["presenca_data_2026_11"] = date(2026, 11, 1)
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


def test_pagina_separa_painel_executivo_e_chamada_diaria(monkeypatch):
    app = _rodar(monkeypatch)

    assert not app.exception
    rotulos_abas = {aba.label for aba in app.tabs}
    assert "Painel executivo" in rotulos_abas
    assert "Preencher presença do dia" in rotulos_abas
    app.session_state["absenteismo_aba_principal"] = "Preencher presença do dia"
    app.run()

    assert not app.exception
    assert any(item.label == "Data da chamada" for item in app.selectbox)
    assert any(item.label == "U.N. cadastral" for item in app.multiselect)
    assert any(item.label == "Monitor" for item in app.multiselect)
    assert any(editor.key.startswith("absenteismo_planilha_editor_") for editor in app.data_editor)


def test_chamada_grava_status_na_planilha_externa(monkeypatch):
    import services.presenca_planilha as presenca_planilha

    dados = _dados_planilha()
    valores = [list(dados.columns), *dados.astype(str).values.tolist()]
    atualizacoes = []
    aba = SimpleNamespace(id=9, get_all_values=lambda: [linha.copy() for linha in valores])
    planilha = SimpleNamespace(sheet1=aba, batch_update=atualizacoes.append)
    cliente = SimpleNamespace(
        open_by_key=lambda sheet_id: planilha,
        set_timeout=lambda timeout: None,
    )
    monkeypatch.setattr(presenca_planilha, "_cliente_gspread", lambda: cliente)

    app = _rodar(monkeypatch)
    app.session_state["absenteismo_aba_principal"] = "Preencher presença do dia"
    app.run()
    assert not app.exception
    editor = next(
        editor for editor in app.data_editor
        if editor.key.startswith("absenteismo_planilha_editor_")
    )
    assert editor.value.columns.tolist() == ["RE", "Login", "Técnico", "Monitor", "Status"]
    assert editor.value["Status"].tolist() == ["ATIVO", "FALTA", ""]

    app.session_state[editor.key] = {
        "edited_rows": {2: {"Status": "ATESTADO"}},
        "added_rows": [],
        "deleted_rows": [],
    }
    app.run()

    assert not app.exception
    assert len(atualizacoes) == 1
    pedido = atualizacoes[0]["requests"][0]["updateCells"]
    assert pedido["range"] == {
        "sheetId": 9,
        "startRowIndex": 3,
        "endRowIndex": 4,
        "startColumnIndex": 6,
        "endColumnIndex": 7,
    }
    assert pedido["rows"][0]["values"][0]["userEnteredValue"] == {"stringValue": "ATESTADO"}
