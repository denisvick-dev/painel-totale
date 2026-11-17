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
