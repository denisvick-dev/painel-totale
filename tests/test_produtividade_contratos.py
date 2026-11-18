from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from services.produtividade_contratos import agrupar, preparar_producao, resumir


def _dados():
    return pd.DataFrame({
        "Contrato": ["001", "001", "002", "", None],
        "Base": ["A", "A", "B", "A", "A"],
        "Supervisor": ["S1", "S1", "S2", "S1", "S1"],
        "Nome Equipe": ["E1", "E1", "E1", "E1", ""],
        "Data": ["01/11/2026 08:00", "01/11/2026 09:00", "01/11/2026", "02/11/2026", "02/11/2026"],
        "Pontos": [1, 1, 2, 1, 1],
    })


def test_contratos_unicos_e_equipe_dia_observado():
    dados, coluna = preparar_producao(_dados())
    resultado = resumir(dados)
    assert coluna == "Contrato"
    assert resultado["contratos"] == 2
    assert resultado["os_com_contrato"] == 3
    assert resultado["equipes_dia"] == 3
    assert resultado["os_com_equipe_data"] == 4
    assert round(resultado["os_equipe_dia"], 2) == 1.33
    assert agrupar(dados, ["Base"]).set_index("Base").loc["A", "Contratos"] == 1


def test_nao_confunde_projeto_tipo_contrato_ou_os_com_identificador():
    dados, coluna = preparar_producao(pd.DataFrame({"Projeto": ["P1"], "Tipo Contrato": ["X"], "O.S.": ["1"]}))
    assert coluna is None
    assert resumir(dados)["contratos"] is None
    assert pd.isna(agrupar(dados, ["Base"]).iloc[0]["Contratos"])


def test_pagina_filtra_periodo_e_nao_requer_presenca():
    caminho = Path(__file__).resolve().parents[1] / "pages" / "produtividade_disponibilidade.py"
    app = AppTest.from_file(str(caminho), default_timeout=60)
    app.session_state["dados_prod"] = _dados()
    app.run()
    assert not app.exception
    app.date_input(key="contratos_inicio").set_value(date(2026, 11, 2)).run()
    assert not app.exception
    assert app.dataframe[0].value["O.S."].sum() == 2
    app.multiselect(key="contratos_bases").set_value(["B"]).run()
    assert not app.exception
    assert any("Nenhuma produção" in i.value for i in app.info)


def test_pagina_sem_identificador_ou_data_avisos():
    caminho = Path(__file__).resolve().parents[1] / "pages" / "produtividade_disponibilidade.py"
    app = AppTest.from_file(str(caminho), default_timeout=60)
    app.session_state["dados_prod"] = pd.DataFrame({"Base": ["A"], "Nome Equipe": ["E1"]})
    app.run()
    assert not app.exception
    assert any("Nenhuma coluna de identificador" in w.value for w in app.warning)
    assert any("Sem data reconhecida" in w.value for w in app.warning)
