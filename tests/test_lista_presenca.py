from datetime import date

import pandas as pd

from services.absenteismo import normalizar_registros, resumir_controle
from services.lista_presenca import montar_lista_presenca, registros_da_presenca, resumo_presenca

DIA = date(2026, 11, 17)


def _quadro():
    return pd.DataFrame({"LOGIN": ["Z1", "Z2", "Z3"], "TÉCNICO": ["A", "B", "C"],
                         "MONITOR": ["M"] * 3, "BASE": ["ABC"] * 3})


def _registros():
    return normalizar_registros(pd.DataFrame([
        {"ID": "1", "Login": "Z1", "Tipo": "Presente", "Data Início": DIA.isoformat()},
        {"ID": "2", "Login": "Z2", "Tipo": "Falta", "Data Início": DIA.isoformat()},
    ]))


def test_presente_ausente_pendente_sao_distintos():
    matriz = montar_lista_presenca(_registros(), _quadro(), DIA, DIA)
    assert resumo_presenca(matriz, DIA) == {"Presentes": 1, "Ausentes": 1, "Pendentes": 1}


def test_presenca_nao_entra_em_ausencias():
    resumo = resumir_controle(_registros(), periodo_inicio=DIA, periodo_fim=DIA, hoje=DIA)
    assert resumo["tecnicos_periodo"] == 1


def test_preenchimento_presente_gera_registro_persistivel():
    original = montar_lista_presenca(normalizar_registros(None), _quadro(), DIA, DIA)
    editada = original.copy()
    editada.at[0, DIA] = "Presente"
    novos = registros_da_presenca(original, editada)
    assert len(novos) == 1
    assert novos[0]["Tipo"] == "Presente"
    relida = normalizar_registros(pd.DataFrame(novos))
    assert resumo_presenca(montar_lista_presenca(relida, _quadro(), DIA, DIA), DIA)["Presentes"] == 1


def test_cancelamento_remove_presenca_e_ausencia_tem_precedencia():
    registros = _registros()
    registros.loc[registros["ID"].eq("1"), "Status"] = "Cancelado"
    matriz = montar_lista_presenca(registros, _quadro(), DIA, DIA)
    assert resumo_presenca(matriz, DIA)["Pendentes"] == 2
