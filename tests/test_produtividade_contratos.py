from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from services.produtividade_contratos import agrupar, preparar_producao, resumir

CAMINHO_PAGINA = Path(__file__).resolve().parents[1] / "pages" / "visao_operacional.py"


def _dados():
    return pd.DataFrame({
        "Contrato": ["001", "001", "002", "", None],
        "Projeto": ["A", "A", "B", "A", "A"], "Base": ["X", "Y", "X", "X", "X"],
        "Supervisor": ["S1", "S1", "S2", "S1", "S1"],
        "Nome Equipe": ["E1", "E1", "E1", "E1", ""],
        "Data": ["01/11/2026 08:00", "01/11/2026 09:00", "01/11/2026", "02/11/2026", "02/11/2026"],
        "Pontos": [1, 1, 2, 1, 1],
    })


def _tabela_consolidada(app: AppTest) -> pd.DataFrame:
    """Localiza a tabela da visão por base/supervisor pela assinatura de colunas."""
    candidatos = [
        elemento.value
        for elemento in app.dataframe
        if {"Base", "Supervisor", "O.S."}.issubset(set(elemento.value.columns))
    ]
    assert candidatos, "tabela consolidada por base/supervisor não encontrada"
    return candidatos[0]


# ====================================================
# Regra pura de produção × contratos (inalterada)
# ====================================================
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


def test_retornos_ambiguos_por_projeto_nao_por_base():
    from services.produtividade_contratos import analisar_retornos

    dados, _ = preparar_producao(pd.DataFrame({
        "Contrato": ["123", "123"], "Projeto": ["P1", "P2"], "Base": ["X", "X"],
        "Supervisor": ["S", "S"], "Data": ["01/11/2026", "01/11/2026"],
    }))
    retornos = pd.DataFrame({"Contrato": ["123"], "Data": pd.to_datetime(["2026-11-05"]), "Motivo": [""]})
    coorte, eventos = analisar_retornos(dados, retornos, date(2026, 11, 1), date(2026, 11, 30), 7)
    assert coorte.empty and eventos.empty


# ====================================================
# Página unificada (O.S. · Contratos · Consultivos)
# ====================================================
def test_pagina_unificada_carrega_e_consolida_por_base_supervisor():
    app = AppTest.from_file(str(CAMINHO_PAGINA), default_timeout=60)
    app.session_state["dados_prod"] = _dados()
    app.run()
    assert not app.exception

    # Filtros transversais herdam as dimensões da produção normalizada.
    assert set(app.multiselect(key="unificada_projetos").options) == {"A", "B"}
    assert set(app.multiselect(key="unificada_bases").options) == {"X", "Y"}
    assert set(app.multiselect(key="unificada_supervisores").options) == {"S1", "S2"}

    tabela = _tabela_consolidada(app)
    assert {"Base", "Supervisor", "O.S.", "Contratos"}.issubset(tabela.columns)
    # Recorte padrão cobre todo o período → cinco O.S. da carga inteira.
    assert tabela["O.S."].sum() == 5


def test_pagina_unificada_filtra_periodo():
    app = AppTest.from_file(str(CAMINHO_PAGINA), default_timeout=60)
    app.session_state["dados_prod"] = _dados()
    app.run()
    assert not app.exception

    app.date_input(key="unificada_inicio").set_value(date(2026, 11, 2)).run()
    assert not app.exception
    assert _tabela_consolidada(app)["O.S."].sum() == 2


def test_pagina_unificada_recorte_vazio_avisa():
    app = AppTest.from_file(str(CAMINHO_PAGINA), default_timeout=60)
    app.session_state["dados_prod"] = _dados()
    app.run()
    # Projeto B só tem produção em 01/11: restringindo a 02/11 o recorte esvazia.
    app.date_input(key="unificada_inicio").set_value(date(2026, 11, 2)).run()
    app.multiselect(key="unificada_projetos").set_value(["B"]).run()
    assert not app.exception
    assert any("Nenhum registro" in item.value for item in app.info)


def test_pagina_sem_identificador_ou_data_avisos():
    app = AppTest.from_file(str(CAMINHO_PAGINA), default_timeout=60)
    app.session_state["dados_prod"] = pd.DataFrame({"Base": ["A"], "Nome Equipe": ["E1"]})
    app.run()
    assert not app.exception
    assert any("Nenhuma coluna de contrato" in w.value for w in app.warning)
    assert any("Sem data reconhecida" in w.value for w in app.warning)


def test_pagina_projeto_ausente_vira_nao_informado():
    app = AppTest.from_file(str(CAMINHO_PAGINA), default_timeout=60)
    app.session_state["dados_prod"] = pd.DataFrame({"Contrato": ["001"], "Base": ["ABC"]})
    app.run()
    assert not app.exception
    assert app.multiselect(key="unificada_projetos").options == ["NÃO INFORMADO"]


def test_pagina_unificada_cruza_consultivos_quando_carregados():
    app = AppTest.from_file(str(CAMINHO_PAGINA), default_timeout=60)
    app.session_state["dados_prod"] = _dados()
    app.session_state["dados_cons"] = pd.DataFrame({
        "DATA": ["01/11/2026", "02/11/2026"],
        "QTDE_CONSULTIVO": [3, 5],
        "QTDE_PRODUTOS": [1, 2],
        "QTDE_MESH": [1, 0], "QTDE_TV": [0, 1], "QTDE_VIRTUA": [0, 1],
        "LOGIN NETSALES": ["L1", "L2"],
        "MONITOR": ["S1", "S1"], "BASE": ["X", "X"],
    })
    app.run()
    assert not app.exception
    tabela = _tabela_consolidada(app)
    assert "Consultivos" in tabela.columns
    assert tabela["Consultivos"].sum() == 8
