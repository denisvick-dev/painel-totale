from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from services.produtividade_contratos import agrupar, preparar_producao, resumir


def _dados():
    return pd.DataFrame({
        "Contrato": ["001", "001", "002", "", None],
        "Projeto": ["A", "A", "B", "A", "A"], "Base": ["X", "Y", "X", "X", "X"],
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
    assert agrupar(dados, ["Projeto"]).set_index("Projeto").loc["A", "Contratos"] == 1


def test_nao_confunde_projeto_tipo_contrato_ou_os_com_identificador():
    dados, coluna = preparar_producao(pd.DataFrame({"Projeto": ["P1"], "Tipo Contrato": ["X"], "O.S.": ["1"]}))
    assert coluna is None
    assert resumir(dados)["contratos"] is None
    assert pd.isna(agrupar(dados, ["Projeto"]).iloc[0]["Contratos"])


def test_pagina_filtra_periodo_e_nao_requer_presenca():
    caminho = Path(__file__).resolve().parents[1] / "pages" / "produtividade_disponibilidade.py"
    app = AppTest.from_file(str(caminho), default_timeout=60)
    app.session_state["dados_prod"] = _dados()
    app.run()
    assert not app.exception
    app.date_input(key="contratos_inicio").set_value(date(2026, 11, 2)).run()
    assert not app.exception
    assert app.dataframe[0].value["O.S."].sum() == 2
    app.multiselect(key="contratos_projetos").set_value(["B"]).run()
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


def test_equipes_e_distribuicao_nao_contam_dias_sem_data():
    from services.produtividade_contratos import distribuicao_contratos, resumo_equipes

    dados, _ = preparar_producao(_dados())
    equipes = resumo_equipes(dados).set_index(["Projeto", "Supervisor", "Equipe"])
    assert equipes.loc[("A", "S1", "E1"), "Equipe-dias"] == 2
    assert equipes.loc[("A", "S1", "E1"), "O.S./equipe-dia"] == 1.5
    distribuicao = distribuicao_contratos(dados).set_index("O.S. por contrato")
    assert distribuicao.loc[1, "Contratos"] == 1
    assert distribuicao.loc[2, "Contratos"] == 1


def test_diagnostico_repeticoes_nao_remove_linhas():
    from services.produtividade_contratos import diagnostico_os

    dados = pd.DataFrame({"Número da O.S 1": ["123", "123", "456", ""]})
    assert diagnostico_os(dados) == ("Número da O.S 1", 1, 3)
    assert diagnostico_os(pd.DataFrame({"Contrato": ["123"]})) == (None, None, 0)


def test_retornos_janela_filtra_status_e_descarta_coorte_incompleta():
    from services.produtividade_contratos import analisar_retornos, preparar_retornos

    prod, _ = preparar_producao(pd.DataFrame({
        "Contrato": ["1", "2", "3"], "Data": ["01/11/2026", "10/11/2026", "28/11/2026"],
        "Projeto": ["A", "A", "A"], "Supervisor": ["S", "S", "S"],
    }))
    retornos, qualidade = preparar_retornos(pd.DataFrame({
        "Contrato": ["1", "1", "2", "3"],
        "Data": ["05/11/2026", "01/11/2026", "13/11/2026", "30/11/2026"],
        "Tipo de Atividade": ["Outra", "Outra", "Outra", "Outra"],
        "Tipo de Atividade.1": ["Retorno Credenciada"] * 4,
        "Status da Atividade": ["Concluída", "Concluída", "Suspensa", "Concluída"],
        "Motivo": ["Falha", "Falha", "Falha", "Falha"],
    }))
    assert qualidade["selecionados"] == 3
    coorte, eventos = analisar_retornos(prod, retornos, date(2026, 11, 1), date(2026, 11, 30), 7)
    assert len(coorte) == 2
    assert int(coorte["Com retorno"].sum()) == 1
    assert len(eventos) == 1
    assert eventos.iloc[0]["Contrato"] == "1"
    assert eventos.iloc[0]["Data"] == pd.Timestamp("2026-11-05")
    coorte30, _ = analisar_retornos(prod, retornos, date(2026, 11, 1), date(2026, 11, 30), 30)
    assert coorte30.empty


def test_retornos_exclui_atribuicao_ambigua_e_exige_colunas():
    import pytest

    from services.produtividade_contratos import analisar_retornos, preparar_retornos

    with pytest.raises(ValueError, match="Status"):
        preparar_retornos(pd.DataFrame({"Contrato": ["1"], "Data": ["01/11/2026"], "Tipo": ["Retorno"]}))
    prod, _ = preparar_producao(pd.DataFrame({
        "Contrato": ["1", "1"], "Data": ["01/11/2026", "01/11/2026"],
        "Projeto": ["A", "B"], "Supervisor": ["S1", "S2"],
    }))
    retornos, _ = preparar_retornos(pd.DataFrame({
        "Contrato": ["1"], "Data": ["05/11/2026"],
        "Tipo de Atividade": ["Retorno Credenciada"], "Status": ["Concluído"],
    }))
    coorte, eventos = analisar_retornos(prod, retornos, date(2026, 11, 1), date(2026, 11, 30), 7)
    assert coorte.empty and eventos.empty


def test_pagina_retorno_exige_confirmacao_e_calcula_com_cobertura(monkeypatch):
    import streamlit as st

    class Arquivo:
        name = "retornos.csv"

        def getvalue(self):
            return (
                "Contrato;Data;Tipo de Atividade;Status;Motivo\n"
                "001;05/11/2026;Retorno Credenciada;Concluída;Falha\n"
            ).encode("utf-8")

    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: Arquivo())
    caminho = Path(__file__).resolve().parents[1] / "pages" / "produtividade_disponibilidade.py"
    app = AppTest.from_file(str(caminho), default_timeout=60)
    app.session_state["dados_prod"] = _dados()
    app.run()
    assert not app.exception
    assert any("Confirme a cobertura" in i.value for i in app.info)
    app.date_input(key="retornos_cobertura_fim").set_value(date(2026, 12, 5))
    app.checkbox(key="retornos_confirmar_cobertura").check().run()
    assert not app.exception
    assert app.radio(key="retornos_janela").value == 7
    assert any("Taxa (%)" in t.value.columns for t in app.dataframe)


def test_projeto_ausente_nao_usa_contrato_nem_base():
    dados, _ = preparar_producao(pd.DataFrame({"Contrato": ["001"], "Base": ["ABC"]}))
    assert dados.loc[0, "Projeto"] == "NÃO INFORMADO"
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages" / "produtividade_disponibilidade.py"))
    app.session_state["dados_prod"] = pd.DataFrame({"Contrato": ["001"], "Base": ["ABC"]})
    app.run()
    assert not app.exception
    assert any("sem projeto reconhecido" in warning.value for warning in app.warning)
    assert app.multiselect(key="contratos_projetos").options == ["NÃO INFORMADO"]


def test_painel_filtra_agrupa_e_exporta_por_projeto_nao_base():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages" / "produtividade_disponibilidade.py"))
    app.session_state["dados_prod"] = _dados()
    app.run()
    assert not app.exception
    assert set(app.multiselect(key="contratos_projetos").options) == {"A", "B"}
    app.multiselect(key="contratos_projetos").set_value(["A"]).run()
    assert not app.exception
    detalhe = app.dataframe[0].value
    assert "Projeto" in detalhe.columns and "Base" not in detalhe.columns
    assert detalhe["O.S."].sum() == 4
    equipes = app.dataframe[1].value
    assert set(equipes["Projeto"]) == {"A"}


def test_retornos_ambiguos_por_projeto_nao_por_base():
    from services.produtividade_contratos import analisar_retornos

    dados, _ = preparar_producao(pd.DataFrame({
        "Contrato": ["123", "123"], "Projeto": ["P1", "P2"], "Base": ["X", "X"],
        "Supervisor": ["S", "S"], "Data": ["01/11/2026", "01/11/2026"],
    }))
    retornos = pd.DataFrame({"Contrato": ["123"], "Data": pd.to_datetime(["2026-11-05"]), "Motivo": [""]})
    coorte, eventos = analisar_retornos(dados, retornos, date(2026, 11, 1), date(2026, 11, 30), 7)
    assert coorte.empty and eventos.empty
