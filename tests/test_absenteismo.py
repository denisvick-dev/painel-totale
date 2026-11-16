"""Testes do controle de absenteísmo (``services.absenteismo``).

Cobre a regra pura do controle de faltas/folgas/férias:

* contagem de dias corridos × úteis (seg–sex) e interseção com o período;
* normalização da aba ``controle_absenteismo`` (aliases, datas BR/ISO,
  dias recalculados, cancelados preservados);
* resumo, agrupamentos e série diária usados pelo painel.

    pytest tests/test_absenteismo.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from services.absenteismo import (
    COLUNAS_REGISTROS,
    agrupar_registros,
    calcular_dias,
    dias_no_periodo,
    fase_do_registro,
    filtrar_registros_periodo,
    normalizar_registros,
    registros_vazios,
    resumir_controle,
    serie_diaria_ausencias,
)

NOVEMBRO = (date(2026, 11, 1), date(2026, 11, 30))


def _bruto() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ID": "1",
                "Login": "101.0",
                "Técnico": "ana souza",
                "Monitor": "Mon A",
                "Base": "SPO",
                "Tipo": "FÉRIAS",
                "Data Início": "01/11/2026",
                "Data Fim": "20/11/2026",
                "Status": "Ativo",
            },
            {
                "ID": "2",
                "Login": "102",
                "Técnico": "José Lima",
                "Monitor": "Mon A",
                "Base": "SPO",
                "Tipo": "Falta",
                "Data Início": "2026-11-16",
                "Data Fim": "",
                "Justificativa": "Não justificada",
            },
            {
                "ID": "3",
                "Login": "103",
                "Técnico": "Carlos",
                "Monitor": "Mon B",
                "Base": "Campinas",
                "Tipo": "Atestado",
                "Data Início": "2026-10-28",
                "Data Fim": "2026-11-03",
                "Status": "Cancelado",
            },
        ]
    )


def test_calcular_dias_corridos_e_uteis() -> None:
    # Seg 02/11 a sex 06/11/2026: 5 corridos, 5 úteis.
    assert calcular_dias(date(2026, 11, 2), date(2026, 11, 6)) == (5, 5)
    # Sex a seg: 4 corridos, 2 úteis (sáb/dom fora).
    assert calcular_dias(date(2026, 11, 6), date(2026, 11, 9)) == (4, 2)
    assert calcular_dias(date(2026, 11, 9), date(2026, 11, 6)) == (0, 0)
    assert calcular_dias("lixo", None) == (0, 0)


def test_dias_no_periodo_conta_so_a_intersecao() -> None:
    # Férias 28/10–03/11 dentro de novembro: só 01–03/11 (3 corridos, 2 úteis:
    # 02/11 é segunda, 01/11 domingo, 03/11 terça).
    corridos, uteis = dias_no_periodo(date(2026, 10, 28), date(2026, 11, 3), *NOVEMBRO)
    assert corridos == 3
    assert uteis == 2
    assert dias_no_periodo(date(2026, 9, 1), date(2026, 9, 10), *NOVEMBRO) == (0, 0)


def test_normalizar_registros_recalcula_dias_e_preserva_cancelado() -> None:
    df = normalizar_registros(_bruto())

    assert list(df.columns)[: len(COLUNAS_REGISTROS)] == list(COLUNAS_REGISTROS)
    assert df["Login"].tolist() == ["101", "102", "103"]  # '101.0' normalizado
    ferias = df.loc[df["ID"] == "1"].iloc[0]
    assert (ferias["Dias Corridos"], ferias["Dias Úteis"]) == (20, 15)
    falta = df.loc[df["ID"] == "2"].iloc[0]
    assert (falta["Dias Corridos"], falta["Dias Úteis"]) == (1, 1)  # sem fim = dia único
    assert df.loc[df["ID"] == "3", "Status"].item() == "Cancelado"

    assert normalizar_registros(pd.DataFrame({"X": [1]})).empty
    assert list(registros_vazios().columns)[:2] == ["ID", "Login"]


def test_resumo_e_agrupamentos_ignoram_cancelados() -> None:
    df = normalizar_registros(_bruto())
    resumo = resumir_controle(df, periodo_inicio=NOVEMBRO[0], periodo_fim=NOVEMBRO[1], hoje=date(2026, 11, 16))

    assert resumo["registros_periodo"] == 2  # férias + falta; atestado cancelado fora
    assert resumo["cancelados"] == 1
    assert resumo["tecnicos_periodo"] == 2
    assert resumo["ausentes_hoje"] == 2  # férias (01–20/11) + falta (16/11)
    assert resumo["dias_uteis_periodo"] == 16  # 15 das férias + 1 da falta

    por_tipo = agrupar_registros(df, "Tipo", periodo_inicio=NOVEMBRO[0], periodo_fim=NOVEMBRO[1])
    assert por_tipo.iloc[0]["Tipo"] == "Férias"
    assert por_tipo.iloc[0]["Dias Úteis"] == 15

    serie = serie_diaria_ausencias(df, periodo_inicio=date(2026, 11, 15), periodo_fim=date(2026, 11, 17))
    assert serie.loc[serie["Data"] == pd.Timestamp("2026-11-16"), "Técnicos"].item() == 2


def test_fase_e_filtro_de_periodo() -> None:
    df = normalizar_registros(_bruto())
    hoje = date(2026, 11, 16)
    assert fase_do_registro(df.loc[df["ID"] == "1"].iloc[0].to_dict(), hoje) == "Em andamento"
    assert fase_do_registro(df.loc[df["ID"] == "3"].iloc[0].to_dict(), hoje) == "Cancelado"

    em_outubro = filtrar_registros_periodo(df, date(2026, 10, 1), date(2026, 10, 31))
    assert em_outubro.empty  # férias começam em 01/11; atestado de outubro está cancelado
    em_novembro = filtrar_registros_periodo(df, *NOVEMBRO)
    assert em_novembro["ID"].tolist() == ["1", "2"]
