from datetime import date

import pandas as pd
import pytest

from services.absenteismo_grade import registros_do_preenchimento


def _grade():
    return pd.DataFrame([{
        "Login": "Z123", "Técnico": "Alex", "Monitor": "Edson", "Base": "ABCDM",
        date(2026, 11, 1): "", date(2026, 11, 2): "FE", "Total": 1,
    }])


def test_converte_somente_dia_preenchido():
    original = _grade()
    editada = original.copy()
    editada.at[0, date(2026, 11, 1)] = "AT"
    novos = registros_do_preenchimento(original, editada)
    assert len(novos) == 1
    assert novos[0]["Tipo"] == "Atestado"
    assert novos[0]["Data Início"] == novos[0]["Data Fim"] == "2026-11-01"
    assert novos[0]["Login"] == "Z123"


def test_sem_alteracoes():
    assert registros_do_preenchimento(_grade(), _grade()) == []


@pytest.mark.parametrize("coluna, valor", [
    (date(2026, 11, 2), ""),
    (date(2026, 11, 2), "F"),
    (date(2026, 11, 1), "INVALIDO"),
    ("Login", "OUTRO"),
    ("Total", 5),
])
def test_rejeita_sobrescrita_e_dados_invalidos(coluna, valor):
    original = _grade()
    editada = original.copy()
    editada.at[0, coluna] = valor
    with pytest.raises(ValueError):
        registros_do_preenchimento(original, editada)


def test_recorte_recalcula_total_e_nao_altera_original():
    from services.absenteismo_grade import recortar_grade, resumir_grade
    original = _grade()
    recorte = recortar_grade(original, [date(2026, 11, 1)])
    assert recorte.iloc[0]["Total"] == 0
    assert original.iloc[0]["Total"] == 1
    assert resumir_grade(original) == {"tecnicos": 1, "com_ausencia": 1, "dias_marcados": 1}


def test_filtros_editor_combinam_dia_unidade_monitor_sem_alterar_origem():
    from services.absenteismo_grade import filtrar_grade_preenchimento
    original = pd.concat([_grade(), _grade()], ignore_index=True)
    original["U.N."] = ["ABC", "LESTE"]
    original["Monitor"] = ["Edson", "Alan"]
    recorte = filtrar_grade_preenchimento(original, [date(2026, 11, 2)], ["LESTE"], ["Alan"])
    assert recorte.index.tolist() == [1]
    assert recorte.iloc[0]["Total"] == 1
    assert date(2026, 11, 1) not in recorte.columns
    assert len(original) == 2
    assert date(2026, 11, 1) in original.columns


def test_filtros_editor_aceitam_nao_informado_e_recorte_vazio():
    from services.absenteismo_grade import filtrar_grade_preenchimento
    original = _grade()
    original["U.N."] = None
    original["Monitor"] = " "
    assert len(filtrar_grade_preenchimento(original, [date(2026, 11, 1)], ["Não informado"], ["Não informado"])) == 1
    assert filtrar_grade_preenchimento(original, [], ["OUTRA"]).empty
