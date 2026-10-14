from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import pages.quebra_geral as quebra_geral
from pages.quebra_geral import DataLoader, Utils


def test_normalizar_login_remove_decimal_de_identificador_numerico() -> None:
    assert Utils.normalizar_login("123.0") == "123"
    assert Utils.normalizar_login("00123.00") == "123"
    assert Utils.normalizar_login("123") == "123"


def test_preparar_base_correlaciona_login_decimal_com_lista_de_ativos() -> None:
    ativos = DataLoader._processar_lista_ativos(
        pd.DataFrame(
            {
                "Login": [123],
                "Técnico": ["Técnico Exemplo"],
                "Monitor": ["Monitor Exemplo"],
                "Base": ["São Paulo"],
            }
        )
    )
    ordens = pd.DataFrame(
        {
            "Contrato": ["OS-1"],
            "Login do Técnico": ["123.0"],
            "Status da O.S 1": ["EXECUTADA"],
        }
    )

    base = DataLoader.preparar_base(ordens, ativos)

    assert base.loc[0, "TÉCNICO"] == "TÉCNICO EXEMPLO"
    assert base.loc[0, "MONITOR"] == "MONITOR EXEMPLO"
    assert base.attrs["logins_encontrados"] == 1


def test_match_nao_depende_do_preenchimento_do_nome_do_tecnico() -> None:
    ativos = DataLoader._processar_lista_ativos(
        pd.DataFrame(
            {
                "Login": ["123"],
                "Técnico": [""],
                "Monitor": ["Monitor Exemplo"],
            }
        )
    )
    colunas_originais = list(ativos.columns)
    ordens = pd.DataFrame(
        {
            "Contrato": ["OS-1"],
            "Login do Técnico": ["123"],
            "Status da O.S 1": ["EXECUTADA"],
        }
    )

    base = DataLoader.preparar_base(ordens, ativos)

    assert base.loc[0, "TÉCNICO"] == "NÃO MAPEADO"
    assert base.loc[0, "MONITOR"] == "MONITOR EXEMPLO"
    assert base.attrs["logins_encontrados"] == 1
    assert list(ativos.columns) == colunas_originais


def test_etl_da_pagina_usa_saida_bruta_do_robo_global_uma_vez(monkeypatch) -> None:
    bruto = pd.DataFrame({"Login do Técnico": [123]})
    processado = pd.DataFrame({"TÉCNICO": ["EXEMPLO"]})
    estado: dict[str, object] = {
        "origem_dados": "Robô Local (1 arquivo)",
        "df_memoria_raw": bruto,
        "robo_processado_sig": (("Atividades-SPO.csv", 1.0, 10),),
    }
    chamadas: list[tuple[pd.DataFrame, pd.DataFrame]] = []

    def aplicar_etl(df_raw: pd.DataFrame, df_ativos: pd.DataFrame) -> pd.DataFrame:
        chamadas.append((df_raw, df_ativos))
        estado["df_memoria"] = processado
        estado["origem_dados"] = "Robô (Atividades-SPO.csv)"
        return processado

    monkeypatch.setattr(quebra_geral, "st", SimpleNamespace(session_state=estado))
    monkeypatch.setattr(DataLoader, "callback_robo_etl", staticmethod(aplicar_etl))
    ativos = pd.DataFrame({"LOGIN": [123]})

    quebra_geral._aplicar_etl_robo_global(ativos)
    quebra_geral._aplicar_etl_robo_global(ativos)

    assert len(chamadas) == 1
    assert chamadas[0][0] is bruto
    assert chamadas[0][1] is ativos
    assert estado["df_memoria_raw"] is bruto
    assert estado["df_memoria"] is processado
