"""Testes da regra de Produtividade × Disponibilidade (D3).

A página é só apresentação; aqui travamos as premissas que mudam o número:

* dias úteis de segunda a sexta, sem feriados;
* um dia de ausência por login/dia, com o tipo de maior prioridade;
* quadro como retrato atual da ``lista_ativos`` (sem desligados);
* técnico-dia = quadro × dias úteis − ausência;
* ausência fora do quadro não entra no denominador;
* filtro de base/supervisor não transforma o restante do quadro em "fora";
* sem data na produção, o período não filtra as O.S. (e isso é avisado).

    pytest tests/test_produtividade_disponibilidade.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from services.absenteismo import normalizar_registros
from services.produtividade import (
    consolidar,
    dias_uteis,
    gerar_insights,
    normalizar_producao,
    pares_de_ausencia,
    quadro_de_referencia,
)


def _lista_ativos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "LOGIN": ["001", "002", "003", "004"],
            "TÉCNICO": ["Ana", "Bia", "Caio", "Dora"],
            "MONITOR": ["SUP1", "SUP1", "SUP2", "SUP3"],
            "BASE": ["BASE1", "BASE1", "BASE2", "BASE1"],
            "SITUAÇÃO": ["ATIVO", "ATIVO", "FÉRIAS", "DESLIGADO"],
        }
    )


def _registros() -> pd.DataFrame:
    return normalizar_registros(
        pd.DataFrame(
            {
                "LOGIN": ["001", "002", "003", "001", "004"],
                "TIPO": ["Folga", "Atestado", "Férias", "Falta", "Falta"],
                "DATA INICIO": [
                    "03/11/2026",
                    "04/11/2026",
                    "02/11/2026",
                    "03/11/2026",
                    "03/11/2026",
                ],
                "DATA FIM": [
                    "03/11/2026",
                    "05/11/2026",
                    "06/11/2026",
                    "03/11/2026",
                    "03/11/2026",
                ],
                "STATUS": ["Ativo"] * 5,
            }
        )
    )


def _producao() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SUPERVISOR": ["SUP1"] * 20 + ["SUP2"] * 5,
            "BASE": ["BASE1"] * 20 + ["BASE2"] * 5,
            "PONTOS": [10] * 25,
            "DATA": (["02/11/2026", "03/11/2026", "04/11/2026", "05/11/2026"] * 6) + ["06/11/2026"],
        }
    )


def test_periodo_conta_apenas_dias_uteis() -> None:
    assert dias_uteis(date(2026, 11, 2), date(2026, 11, 6)) == 5
    # Sábado e domingo não entram: 06/11 (sex) → 09/11 (seg) = 2 dias úteis.
    assert dias_uteis(date(2026, 11, 6), date(2026, 11, 9)) == 2


def test_producao_normalizada_aceita_aliases_e_numero_pt_br() -> None:
    base = pd.DataFrame(
        {
            "MONITOR": ["sup1", ""],
            "PONTOS": ["1.234,5", "3,5"],
            "DATA": ["2026-11-10", "10/11/2026"],
        }
    )
    normalizada = normalizar_producao(base)

    assert normalizada["Supervisor"].tolist() == ["SUP1", "NÃO INFORMADO"]
    assert normalizada["Pontos"].tolist() == [1234.5, 3.5]
    assert normalizada["O.S."].tolist() == [1, 1]
    assert normalizada["Data"].notna().all()


def test_quadro_ignora_desligados_e_deduplica_login() -> None:
    lista = _lista_ativos()
    lista = pd.concat([lista, lista.iloc[[0]].assign(MONITOR="SUP NOVO")], ignore_index=True)

    quadro = quadro_de_referencia(lista)

    assert set(quadro["Login"]) == {"1", "2", "3"}
    assert "4" not in set(quadro["Login"])  # DESLIGADO fora do quadro
    assert quadro.loc[quadro["Login"].eq("1"), "Supervisor"].iat[0] == "SUP NOVO"


def test_pares_de_ausencia_deduplicam_dia_e_clipam_fim_de_semana() -> None:
    registros = _registros()
    quadro = quadro_de_referencia(_lista_ativos())

    detalhe = pares_de_ausencia(registros, quadro, inicio=date(2026, 11, 2), fim=date(2026, 11, 13))

    # 001: folga e falta no dia 03 → um par, com tipo FALTA.
    dia_03 = detalhe.loc[detalhe["Login"].eq("1") & detalhe["Data"].eq("2026-11-03")]
    assert len(dia_03) == 1
    assert dia_03["Tipo"].iat[0] == "FALTA"
    # 003: férias de 02 a 06 = 5 dias úteis (fim de semana não existe no par).
    assert detalhe.loc[detalhe["Login"].eq("3")].shape[0] == 5
    # 004 está desligado: entra como fora do quadro, não como ausência do time.
    assert not detalhe.loc[detalhe["Login"].eq("4"), "NoQuadro"].any()

    # Texto em dia/mês/ano brasileiro vale o mesmo que ``date``.
    com_texto = pares_de_ausencia(registros, quadro, inicio="02/11/2026", fim="13/11/2026")
    assert len(com_texto) == len(detalhe)


def test_pares_de_ausencia_filtram_por_tipo() -> None:
    detalhe = pares_de_ausencia(
        _registros(),
        quadro_de_referencia(_lista_ativos()),
        inicio=date(2026, 11, 2),
        fim=date(2026, 11, 13),
        tipos=["Férias"],
    )

    assert detalhe["Tipo"].unique().tolist() == ["FERIAS"]
    assert detalhe["Login"].unique().tolist() == ["3"]


def test_consolidado_fecha_a_conta_do_recorte() -> None:
    resultado = consolidar(
        _producao(),
        _registros(),
        _lista_ativos(),
        inicio=date(2026, 11, 2),
        fim=date(2026, 11, 13),
    )

    assert resultado.dias_uteis == 10
    assert resultado.headcount == 3  # desligado não conta
    assert resultado.dias_ausencia == 8  # 1 (falta) + 2 (atestado) + 5 (férias)
    assert resultado.dias_disponiveis == 22.0
    assert resultado.os == 25
    assert resultado.os_por_tecnico_dia == round(25 / 22, 2)
    assert resultado.taxa_absenteismo == round(8 / 30 * 100, 2)
    assert resultado.os_estimadas_perdidas is not None

    sup1 = resultado.por_supervisor.set_index("Supervisor").loc["SUP1"]
    assert sup1["Quadro"] == 2
    assert sup1["Dias Ausência"] == 3
    assert sup1["Técnico-dia Disponível"] == 17
    assert sup1["O.S."] == 20
    assert sup1["Leitura"] in {"Acima", "Abaixo", "Na mediana"}


def test_consolidado_separa_programada_de_nao_programada() -> None:
    resultado = consolidar(
        _producao(),
        _registros(),
        _lista_ativos(),
        inicio=date(2026, 11, 2),
        fim=date(2026, 11, 13),
    )

    naturezas = dict(zip(resultado.por_tipo["Tipo"], resultado.por_tipo["Natureza"]))
    assert naturezas["FERIAS"] == "Programada"
    assert naturezas["ATESTADO"] == "Não programada"
    assert naturezas["FALTA"] == "Não programada"
    assert resultado.por_tipo["Dias"].sum() == resultado.dias_ausencia


def test_filtro_de_base_nao_marca_o_resto_do_quadro_como_fora() -> None:
    resultado = consolidar(
        _producao(),
        _registros(),
        _lista_ativos(),
        inicio=date(2026, 11, 2),
        fim=date(2026, 11, 13),
        bases=["BASE1"],
    )

    assert resultado.headcount == 2
    assert resultado.dias_ausencia == 3  # só a falta do login 001
    # A férias do login 003 (BASE2) sai do recorte sem virar "fora do quadro":
    # o único aviso é o dia do login 004, que está desligado de fato.
    avisos_fora = [aviso for aviso in resultado.avisos if "fora do quadro" in aviso]
    assert len(avisos_fora) == 1
    assert "1 dia" in avisos_fora[0]


def test_sem_data_na_producao_o_periodo_nao_filtra_os() -> None:
    producao = _producao().drop(columns="DATA")

    resultado = consolidar(
        producao,
        _registros(),
        _lista_ativos(),
        inicio=date(2026, 11, 2),
        fim=date(2026, 11, 13),
    )

    assert resultado.os == 25
    assert resultado.serie_semanal.empty
    assert any("não trouxe uma coluna de data" in aviso for aviso in resultado.avisos)


def test_sem_fontes_de_presenca_o_painel_nao_quebra() -> None:
    resultado = consolidar(
        _producao(),
        None,
        None,
        inicio=date(2026, 11, 2),
        fim=date(2026, 11, 13),
    )

    assert resultado.os == 25
    assert resultado.headcount == 0
    assert resultado.dias_ausencia == 0
    assert resultado.os_por_tecnico_dia is None
    assert any("Sem lista de ativos" in aviso for aviso in resultado.avisos)


def test_insights_avisam_quando_falta_quadro() -> None:
    resultado = consolidar(
        _producao(), None, None, inicio=date(2026, 11, 2), fim=date(2026, 11, 13)
    )
    insights = gerar_insights(resultado)

    assert insights
    assert any("quadro de referência" in mensagem for mensagem, _ in insights)


def test_calendario_operacional_afeta_denominador_ausencia_e_semanas():
    registros = normalizar_registros(pd.DataFrame({
        "LOGIN": ["001"], "TIPO": ["Falta"],
        "DATA INICIO": ["02/11/2026"], "DATA FIM": ["07/11/2026"],
    }))
    producao = pd.DataFrame({"Supervisor": ["SUP1"], "Base": ["BASE1"],
                             "Data": ["04/11/2026"], "O.S.": [1]})
    resultado = consolidar(
        producao, registros, _lista_ativos(), inicio=date(2026, 11, 2),
        fim=date(2026, 11, 7), dias_semana=(0, 1, 2, 3, 4, 5),
        feriados=(date(2026, 11, 2),),
    )
    assert resultado.dias_uteis == 5
    assert resultado.dias_ausencia == 5
    assert resultado.dias_disponiveis == 10
    assert resultado.serie_semanal.iloc[0]["Dias Úteis"] == 5
    assert resultado.serie_semanal.iloc[0]["Dias Ausência"] == 5
