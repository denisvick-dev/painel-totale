from datetime import date

import pandas as pd

from services.absenteismo import normalizar_registros
from services.forca_trabalho import calcular_forca_trabalho


def test_quadro_deduplicado_sobreposicoes_cancelamento_e_externos():
    quadro = pd.DataFrame({"LOGIN": ["Z1", "Z1", "Z2"], "TÉCNICO": ["A", "A", "B"],
                           "BASE": ["ABC"] * 3, "MONITOR": ["M"] * 3})
    registros = normalizar_registros(pd.DataFrame([
        {"ID": str(i), "Login": login, "Tipo": tipo, "Status": status,
         "Data Início": "2026-11-17", "Data Fim": "2026-11-17"}
        for i, (login, tipo, status) in enumerate([
            ("Z1", "Falta", "Ativo"), ("Z1", "Atestado", "Ativo"),
            ("Z2", "Férias", "Cancelado"), ("Z9", "Falta", "Ativo"),
        ])
    ]))
    resumo, detalhes = calcular_forca_trabalho(quadro, registros, date(2026, 11, 17))
    assert resumo.iloc[0]["Quadro"] == 2
    assert resumo.iloc[0]["Ausentes"] == 1
    assert resumo.iloc[0]["Disponíveis estimados"] == 1
    assert resumo.iloc[0]["Disponibilidade (%)"] == 50
    assert len(detalhes) == 2


def test_sem_quadro_nao_inventa_disponibilidade():
    resumo, detalhes = calcular_forca_trabalho(pd.DataFrame(), normalizar_registros(None), date(2026, 11, 17))
    assert resumo.empty
    assert detalhes.empty


def test_fora_da_data_e_dados_de_grupo_ausentes():
    quadro = pd.DataFrame({"LOGIN": ["Z1"], "TÉCNICO": ["A"]})
    resumo, detalhes = calcular_forca_trabalho(quadro, normalizar_registros(None), date(2026, 11, 18))
    assert resumo.iloc[0]["Base"] == "Não informado"
    assert resumo.iloc[0]["Disponíveis estimados"] == 1
    assert detalhes.iloc[0]["Situação no dia"] == "Disponível estimado"
