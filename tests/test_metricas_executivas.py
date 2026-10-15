from __future__ import annotations

from datetime import datetime

import pandas as pd

from components.metricas_executivas import (
    comparar_periodos,
    resumo_frequencia,
    serie_atingimento_meta,
    serie_diaria,
    serie_quebra_diaria,
)
from components.saude_dados import avaliar_consistencia, avaliar_frescor


def test_comparar_periodos_nao_inventa_datas_ausentes() -> None:
    serie = pd.Series(
        [10.0, 20.0],
        index=pd.to_datetime(["2026-10-01", "2026-10-08"]),
    )

    comparacao = comparar_periodos(serie)

    assert comparacao["data"].isoformat() == "2026-10-08"
    assert comparacao["atual"] == 20.0
    assert comparacao["d1"] is None
    assert comparacao["w1"] == 10.0


def test_serie_diaria_soma_quantidade_e_ignora_data_invalida() -> None:
    df = pd.DataFrame(
        {
            "Data Agendamento": ["01/10/2026", "01/10/2026", "inválida"],
            "TOTAL DE TAREFAS": [2, 3, 5],
        }
    )

    serie = serie_diaria(df, valor_col="TOTAL DE TAREFAS")

    assert len(serie) == 1
    assert serie.iloc[0] == 5.0


def test_serie_atingimento_meta_acumula_no_mes_por_equipe() -> None:
    df = pd.DataFrame(
        {
            "Data": ["01/10/2026", "02/10/2026", "02/10/2026"],
            "Nome Equipe": ["A", "A", "B"],
            "Pontos": [200, 100, 250],
        }
    )

    serie = serie_atingimento_meta(df)

    assert serie.iloc[0] == 0.0
    assert serie.iloc[1] == 50.0


def test_serie_quebra_considera_somente_ordens_concluidas() -> None:
    df = pd.DataFrame(
        {
            "Data": ["01/10/2026", "01/10/2026", "01/10/2026"],
            "Status Contrato": ["Executada", "Não Executada", "Pendente"],
        }
    )

    serie = serie_quebra_diaria(df)

    assert serie.iloc[0] == 50.0


def test_frequencia_conta_dias_observados_sem_inferir_faltas() -> None:
    df = pd.DataFrame(
        {
            "Data": ["01/10/2026", "01/10/2026", "03/10/2026"],
            "Nome Equipe": ["A", "A", "A"],
            "Supervisor": ["Sup 1", pd.NA, "Sup 1"],
            "Projeto": ["Fibra", "Fibra", pd.NA],
        }
    )

    resumo = resumo_frequencia(df)

    assert list(resumo.columns) == [
        "Equipe",
        "Supervisor",
        "Projeto",
        "Dias com produção",
        "Registros",
        "Última atividade",
    ]
    assert resumo.loc[0, "Supervisor"] == "Sup 1"
    assert resumo.loc[0, "Projeto"] == "Fibra"
    assert resumo.loc[0, "Dias com produção"] == 2
    assert resumo.loc[0, "Registros"] == 3


def test_saude_de_dados_classifica_frescor_e_duplicatas() -> None:
    agora = datetime.fromisoformat("2026-10-05T12:00:00-03:00")
    estado, _ = avaliar_frescor(agora, True, agora=agora)
    consistencia, _ = avaliar_consistencia(pd.DataFrame({"id": [1, 1], "vazio": [None, None]}))

    assert estado == "ok"
    assert consistencia == "alerta"
