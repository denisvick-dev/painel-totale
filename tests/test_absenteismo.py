"""Testes do controle de absenteísmo (``services.absenteismo``).

Cobre a regra pura do controle de faltas/folgas/férias:

* contagem de dias corridos × úteis (seg–sex) e interseção com o período;
* normalização da aba ``controle_absenteismo`` (aliases, datas BR/ISO,
  dias recalculados, cancelados preservados);
* resumo, agrupamentos e série diária usados pelo painel;
* grade mensal (técnico × dia): códigos, leitura da planilha e matriz.

    pytest tests/test_absenteismo.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from services.absenteismo import (
    ABREVIACOES_AUSENCIA,
    COLUNAS_IDENTIDADE_GRADE,
    COLUNAS_REGISTROS,
    TIPOS_AUSENCIA,
    abreviar_ausencia,
    agrupar_registros,
    calcular_dias,
    carregar_registros_com_origem,
    codigo_para_tipo,
    detectar_colunas_dias,
    dias_no_periodo,
    fase_do_registro,
    filtrar_registros_periodo,
    montar_matriz_ausencias,
    normalizar_matriz_ausencias,
    normalizar_quadro_identidade,
    normalizar_registros,
    registros_vazios,
    resumir_controle,
    serie_diaria_ausencias,
    tipos_do_codigo,
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


def test_alias_afastado_normaliza_para_o_tipo_canonico() -> None:
    bruto = pd.DataFrame([{"Login": "Z1", "Tipo": "AFASTADO", "Data Início": "2026-11-17"}])
    assert normalizar_registros(bruto).loc[0, "Tipo"] == "Afastamento"


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


# ====================================================
# Grade mensal (técnico × dia)
# ====================================================
def _quadro() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "RE": ["1001", "1002", "1003"],
            "Login": ["101", "102", "999"],
            "Técnico": ["Ana Souza", "José Lima", "Sem Ausência"],
            "Monitor": ["Mon A", "Mon A", "Mon B"],
            "Base": ["SPO", "SPO", "Campinas"],
            "U.N.": ["NET-ABCDM", "NET-ABCDM", "NET-LESTE"],
        }
    )


def _grade() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "RE": [8368, 8496],
            "Login": ["Z641759", "Z663524"],
            "Técnico": ["ALEX BERNARDES DA SILVA", "ALEX DE JESUS FREIRE"],
            "Monitor": ["EDSON MARCO PINHEIRO", "EDSON MARCO PINHEIRO"],
            "U.N.": ["NET-ABCDM", "NET-ABCDM"],
            "Base": ["ABCDM-TOTALE", "ABCDM-TOTALE"],
            "1/nov.": ["", ""],
            "2/nov.": ["FE", ""],
            "3/nov.": ["FE", ""],
            "4/nov.": ["FE", ""],
            "5/nov.": ["AT", "P"],
            "6/nov.": ["", ""],
        }
    )


def test_codigos_da_grade_mapeiam_tipos_e_presenca() -> None:
    assert codigo_para_tipo("F") == "Falta"
    assert codigo_para_tipo("FE") == "Férias"
    assert codigo_para_tipo("férias") == "Férias"
    assert codigo_para_tipo("AT") == "Atestado"
    assert codigo_para_tipo("AF") == "Afastamento"
    assert codigo_para_tipo("Licença médica") == "Licença"
    assert codigo_para_tipo("Suspensão") == "Suspensão"
    assert codigo_para_tipo("Treinamento") == "Treinamento"
    assert codigo_para_tipo("Sinistro") == "Outros"

    for presente in ("", "   ", "P", "OK", "PRESENTE", "1", "0", "-"):
        assert codigo_para_tipo(presente) == ""

    assert tipos_do_codigo("FE/AT") == ["Férias", "Atestado"]
    assert tipos_do_codigo("P") == []
    assert abreviar_ausencia("Férias") == "FE"
    assert abreviar_ausencia("Outros") == "OUT"
    assert abreviar_ausencia("Sinistro") == "SIN"
    assert set(ABREVIACOES_AUSENCIA) <= set(TIPOS_AUSENCIA)


def test_detectar_colunas_dias_aceita_formatos_da_planilha() -> None:
    grade = pd.DataFrame(columns=["RE", "Login", "1/nov.", "2/nov.", "3/nov.", "4/nov.", "Total"])
    colunas = detectar_colunas_dias(grade, referencia=date(2026, 11, 10))
    assert list(colunas) == ["1/nov.", "2/nov.", "3/nov.", "4/nov."]
    assert colunas["1/nov."] == date(2026, 11, 1)

    # Cabeçalho sem ano em dezembro, lido em janeiro: pertence ao ano anterior.
    dezembro = detectar_colunas_dias(
        pd.DataFrame(columns=["1/dez.", "2/dez."]), referencia=date(2027, 1, 10)
    )
    assert dezembro["1/dez."] == date(2026, 12, 1)

    misto = detectar_colunas_dias(
        pd.DataFrame(columns=["2026-11-20", "21/11/2026", "22"]),
        referencia=date(2026, 11, 10),
    )
    assert list(misto.values()) == [date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 22)]

    # Uma coluna só não caracteriza grade; "Data Início" não é dia.
    assert detectar_colunas_dias(pd.DataFrame(columns=["1/nov."]), referencia=date(2026, 11, 10)) == {}
    assert detectar_colunas_dias(pd.DataFrame(columns=["Data Início", "Data Fim"])) == {}


def test_normalizar_quadro_identidade_mapeia_re_login_e_unidade() -> None:
    identidade = normalizar_quadro_identidade(_quadro())

    assert list(identidade.columns) == list(COLUNAS_IDENTIDADE_GRADE)
    assert identidade["RE"].tolist() == ["1001", "1002", "1003"]
    assert identidade["Login"].tolist() == ["101", "102", "999"]

    # Número do Sheets (8368.0) vira texto sem o ".0".
    bruto = pd.DataFrame(
        {
            "RE": [8368.0, 7777.0],
            "Login": ["Z1", "Z2"],
            "Técnico": ["Antigo", "Atual"],
            "Base": ["ABCDM", "ABCDM"],
        }
    )
    assert normalizar_quadro_identidade(bruto)["RE"].tolist() == ["8368", "7777"]

    # Duplicidade: vale a última ocorrência.
    duplicado = normalizar_quadro_identidade(
        pd.DataFrame(
            {
                "RE": [8368, 7777],
                "Login": ["Z1", "Z1"],
                "Técnico": ["Antigo", "Atual"],
                "Base": ["ABCDM", "ABCDM"],
            }
        )
    )
    assert len(duplicado) == 1
    assert duplicado.iloc[0]["RE"] == "7777"
    assert duplicado.iloc[0]["Técnico"] == "Atual"

    # Sem login, o RE assume a identidade.
    sem_login = normalizar_quadro_identidade(pd.DataFrame({"RE": [123], "Técnico": ["Ana"]}))
    assert sem_login.iloc[0]["Login"] == "123"
    assert normalizar_quadro_identidade(None).empty


def test_montar_matriz_ausencias_usa_quadro_e_marca_os_dias() -> None:
    matriz = montar_matriz_ausencias(
        normalizar_registros(_bruto()), _quadro(), inicio=date(2026, 11, 1), fim=date(2026, 11, 20)
    )

    assert list(matriz.columns[: len(COLUNAS_IDENTIDADE_GRADE)]) == list(COLUNAS_IDENTIDADE_GRADE)
    assert matriz["Login"].tolist() == ["999", "101", "102"]
    assert matriz.at[1, date(2026, 11, 20)] == "FE"
    assert matriz.at[1, date(2026, 11, 16)] == "FE"
    assert matriz.at[2, date(2026, 11, 16)] == "F"
    assert matriz.at[0, date(2026, 11, 16)] == ""
    assert matriz.at[1, "Total"] == 20  # férias de 01 a 20/11, fins de semana inclusive
    assert matriz.at[2, "Total"] == 1
    assert matriz.at[0, "Total"] == 0
    assert matriz.at[1, "Técnico"] == "Ana Souza"

    # Cancelado não marca e técnico que só existe nos registros entra no fim.
    extra = normalizar_registros(
        pd.DataFrame(
            [
                {
                    "ID": "x",
                    "Login": "777",
                    "Técnico": "Fora Do Quadro",
                    "Monitor": "Mon C",
                    "Base": "Leste",
                    "Tipo": "Folga",
                    "Data Início": "10/11/2026",
                    "Data Fim": "10/11/2026",
                }
            ]
        )
    )
    com_extra = montar_matriz_ausencias(
        extra, _quadro(), inicio=date(2026, 11, 10), fim=date(2026, 11, 10)
    )
    assert com_extra["Login"].tolist() == ["999", "777", "101", "102"]
    assert com_extra.loc[com_extra["Login"] == "777", date(2026, 11, 10)].item() == "FO"
    assert "103" not in montar_matriz_ausencias(
        normalizar_registros(_bruto()), _quadro(), inicio=date(2026, 11, 1), fim=date(2026, 11, 30)
    )["Login"].tolist()

    # Sem quadro, as linhas vêm dos registros ativos.
    sem_quadro = montar_matriz_ausencias(
        normalizar_registros(_bruto()), None, inicio=date(2026, 11, 16), fim=date(2026, 11, 16)
    )
    assert sem_quadro["Login"].tolist() == ["101", "102"]
    assert sem_quadro.at[0, date(2026, 11, 16)] == "FE"
    assert sem_quadro.at[1, date(2026, 11, 16)] == "F"


def test_normalizar_matriz_ausencias_importa_a_grade_mensal() -> None:
    registros = normalizar_matriz_ausencias(_grade(), referencia=date(2026, 11, 10))

    assert len(registros) == 2
    ferias = registros.loc[registros["Tipo"] == "Férias"].iloc[0]
    assert (ferias["Data Início"], ferias["Data Fim"]) == ("2026-11-02", "2026-11-04")
    assert (ferias["Dias Corridos"], ferias["Dias Úteis"]) == (3, 3)
    assert ferias["ID"] == "mapa-Z641759-2026-11-02-FE"
    assert ferias["Motivo"] == "Importado da grade mensal"
    assert ferias["Justificativa"] == "Não se aplica"
    assert ferias["Status"] == "Ativo"
    assert ferias["Técnico"] == "Alex Bernardes Da Silva"

    atestado = registros.loc[registros["Tipo"] == "Atestado"].iloc[0]
    assert (atestado["Data Início"], atestado["Data Fim"]) == ("2026-11-05", "2026-11-05")
    # A linha com "P" não gerou registro.
    assert set(registros["Login"]) == {"Z641759"}

    # Combinação de códigos no mesmo dia vira um registro por tipo.
    combinada = _grade()
    combinada.loc[1, "5/nov."] = "FE/AT"
    registros_combinados = normalizar_matriz_ausencias(combinada, referencia=date(2026, 11, 10))
    do_segundo = registros_combinados.loc[registros_combinados["Login"] == "Z663524"]
    assert set(do_segundo["Tipo"]) == {"Férias", "Atestado"}
    assert len(do_segundo) == 2

    # Aba de registros (sem colunas de dia) não é confundida com grade.
    assert normalizar_matriz_ausencias(_bruto(), referencia=date(2026, 11, 10)).empty


def test_carregar_registros_com_origem_detecta_grade(monkeypatch) -> None:
    import services.google_drive_client as cliente

    monkeypatch.setattr(
        cliente, "carregar_planilha_gsheets_csv", lambda *args, **kwargs: _grade()
    )
    registros, origem = carregar_registros_com_origem("planilha", "controle_absenteismo")
    assert origem is True
    assert len(registros) == 2

    # Grade recém-criada, ainda toda em branco: continua sendo grade (somente leitura).
    vazia = _grade().copy()
    for coluna in ("2/nov.", "3/nov.", "4/nov.", "5/nov."):
        vazia[coluna] = ""
    monkeypatch.setattr(cliente, "carregar_planilha_gsheets_csv", lambda *args, **kwargs: vazia)
    registros, origem = carregar_registros_com_origem("planilha", "controle_absenteismo")
    assert origem is True
    assert registros.empty

    monkeypatch.setattr(
        cliente, "carregar_planilha_gsheets_csv", lambda *args, **kwargs: _bruto()
    )
    registros, origem = carregar_registros_com_origem("planilha", "controle_absenteismo")
    assert origem is False
    assert len(registros) == 3
