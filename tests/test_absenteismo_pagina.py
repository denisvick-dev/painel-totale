"""Testes isolados da aba de preenchimento diário de presença."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

from services.absenteismo import (
    CHAVE_SESSAO_REGISTROS,
    normalizar_quadro_identidade,
    normalizar_registros,
)
from services.lista_presenca import normalizar_planilha_lista_presenca
from services.presenca_grade import CHAVE_SNAPSHOT, interpretar_valores

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = RAIZ / "pages" / "absenteismo.py"


def _quadro() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "LOGIN": ["Z641759", "Z663524", "Z657046"],
            "TÉCNICO": ["Alex Bernardes Da Silva", "Alex De Jesus Freire", "Abner Makalas"],
            "MONITOR": ["Edson Marco Pinheiro", "Edson Marco Pinheiro", "Alan De Andrade Dias"],
            "BASE": ["Abcdm-Totale", "Abcdm-Totale", "Spo-Totalleste"],
            "SITUAÇÃO": ["ATIVO", "ATIVO", "FÉRIAS"],
            "RE": ["8368", "8496", "8554"],
            "U.N.": ["NET-ABCDM", "NET-ABCDM", "NET-LESTE"],
        }
    )


def _registros() -> pd.DataFrame:
    return normalizar_registros(
        pd.DataFrame(
            [
                {
                    "ID": "1",
                    "Login": "Z641759",
                    "Técnico": "Alex Bernardes Da Silva",
                    "Monitor": "Edson Marco Pinheiro",
                    "Base": "Abcdm-Totale",
                    "Tipo": "Férias",
                    "Data Início": "03/11/2026",
                    "Data Fim": "05/11/2026",
                    "Status": "Ativo",
                },
                {
                    "ID": "2",
                    "Login": "Z641759",
                    "Técnico": "Alex Bernardes Da Silva",
                    "Monitor": "Edson Marco Pinheiro",
                    "Base": "Abcdm-Totale",
                    "Tipo": "Atestado",
                    "Data Início": "04/11/2026",
                    "Data Fim": "04/11/2026",
                    "Status": "Ativo",
                },
            ]
        )
    )


def _snapshot() -> dict:
    dias = list(pd.date_range("2026-11-01", "2026-11-30").date)
    pessoas = normalizar_quadro_identidade(_quadro())
    valores = [list(pessoas.columns) + [dia.isoformat() for dia in dias]]
    valores.extend(
        [list(linha) + [""] * len(dias) for linha in pessoas.itertuples(index=False, name=None)]
    )
    snapshot = interpretar_valores(valores)
    snapshot["registros"] = _registros()
    return snapshot


def _planilha_presenca() -> pd.DataFrame:
    colunas_dias = {f"{dia.day}/nov.": ["", "", ""] for dia in pd.date_range("2026-11-01", "2026-11-30")}
    return normalizar_planilha_lista_presenca(
        pd.DataFrame(
            {
                "RE": ["8368", "8496", "8554"],
                "Login": ["Z641759", "Z663524", "Z657046"],
                "Técnico": [
                    "Alex Bernardes Da Silva",
                    "Alex De Jesus Freire",
                    "Abner Makalas",
                ],
                "Monitor": [
                    "Edson Marco Pinheiro",
                    "Edson Marco Pinheiro",
                    "Alan De Andrade Dias",
                ],
                "U.N.": ["ABCDM-TOTALE", "ABCDM-TOTALE", "SPO-TOTALLESTE"],
                "Base": ["NET-ABCDM", "NET-ABCDM", "NET-LESTE"],
                **colunas_dias,
            }
        )
    )


def _rodar(monkeypatch) -> AppTest:
    import services.lista_presenca as lista_presenca

    dados = _planilha_presenca()
    monkeypatch.setattr(
        lista_presenca,
        "carregar_planilha_lista_presenca",
        lambda **kwargs: dados.copy(),
    )
    snapshot = _snapshot()
    app = AppTest.from_file(str(PAGINA), default_timeout=60)
    app.session_state[CHAVE_SNAPSHOT] = snapshot
    app.session_state[CHAVE_SESSAO_REGISTROS] = snapshot["registros"].copy()
    app.session_state["absenteismo_aba_principal"] = "Preencher presença do dia"
    app.session_state["absenteismo_periodo_inicio"] = date(2026, 11, 1)
    app.session_state["absenteismo_periodo_fim"] = date(2026, 11, 30)
    app.session_state["presenca_data_2026_11"] = date(2026, 11, 1)
    return app.run()


def test_aba_diaria_exibe_data_equipe_e_grade_editavel(monkeypatch) -> None:
    app = _rodar(monkeypatch)

    assert not app.exception
    assert any(aba.label == "Painel executivo" for aba in app.tabs)
    assert any(aba.label == "Preencher presença do dia" for aba in app.tabs)
    data = next(widget for widget in app.selectbox if widget.label == "Data da chamada")
    assert data.value == date(2026, 11, 1)
    assert len(data.options) == 30
    unidade = next(widget for widget in app.multiselect if widget.label == "U.N. cadastral")
    monitor = next(widget for widget in app.multiselect if widget.label == "Monitor")
    assert unidade.options == ["ABCDM-TOTALE", "SPO-TOTALLESTE"]
    assert "Edson Marco Pinheiro" in monitor.options
    assert any(widget.label == "Localizar técnico" for widget in app.text_input)

    editor = next(iter(app.data_editor))
    assert editor.value.columns.tolist() == ["RE", "Login", "Técnico", "Monitor", "Status"]
    assert editor.value["RE"].tolist() == ["8368", "8496", "8554"]
    assert editor.value["Técnico"].tolist() == [
        "Alex Bernardes Da Silva", "Alex De Jesus Freire", "Abner Makalas",
    ]


def test_preenchimento_por_periodo_e_opcional(monkeypatch) -> None:
    app = _rodar(monkeypatch)
    visualizacao = next(widget for widget in app.selectbox if widget.label == "Visualização")

    assert visualizacao.value == "Chamada do dia"
    visualizacao.set_value("Preenchimento por período").run()

    assert not app.exception
    periodo = next(widget for widget in app.multiselect if widget.label == "Dias do período")
    assert len(periodo.options) == 30


def test_busca_sem_resultado_mostra_orientacao(monkeypatch) -> None:
    app = _rodar(monkeypatch)
    busca = next(widget for widget in app.text_input if widget.label == "Localizar técnico")
    busca.set_value("tecnico-inexistente-xyz").run()

    assert not app.exception
    assert any("Nenhum técnico encontrado" in aviso.value for aviso in app.info)


def test_filtro_de_unidade_limita_a_equipe_exibida(monkeypatch) -> None:
    app = _rodar(monkeypatch)
    unidade = next(widget for widget in app.multiselect if widget.label == "U.N. cadastral")
    unidade.set_value(["SPO-TOTALLESTE"]).run()

    assert not app.exception
    assert app.data_editor[0].value["RE"].tolist() == ["8554"]


def test_chamada_grava_status_na_planilha_externa(monkeypatch) -> None:
    import services.presenca_planilha as presenca_planilha

    dados = _planilha_presenca()
    valores = [list(dados.columns), *dados.astype(str).values.tolist()]
    atualizacoes = []
    aba = SimpleNamespace(id=7, get_all_values=lambda: [linha.copy() for linha in valores])
    planilha = SimpleNamespace(sheet1=aba, batch_update=atualizacoes.append)
    cliente = SimpleNamespace(
        open_by_key=lambda sheet_id: planilha,
        set_timeout=lambda timeout: None,
    )
    monkeypatch.setattr(presenca_planilha, "_cliente_gspread", lambda: cliente)

    app = _rodar(monkeypatch)
    editor = next(iter(app.data_editor))
    app.session_state[editor.key] = {
        "edited_rows": {0: {"Status": "ATIVO"}},
        "added_rows": [],
        "deleted_rows": [],
    }
    app.run()

    assert not app.exception
    assert len(atualizacoes) == 1
    pedido = atualizacoes[0]["requests"][0]["updateCells"]
    assert pedido["range"]["sheetId"] == 7
    assert pedido["rows"][0]["values"][0]["userEnteredValue"] == {"stringValue": "ATIVO"}
