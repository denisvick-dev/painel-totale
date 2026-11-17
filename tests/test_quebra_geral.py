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


def test_matriz_executiva_calcula_e_exibe_percentuais_com_escala_consistente(monkeypatch) -> None:
    df = pd.DataFrame(
        [
            {
                "MONITOR": "MONITOR A",
                "TIPO_SERVICO": tipo,
                "Status Contrato": status,
                "TOTAL DE TAREFAS": quantidade,
            }
            for tipo, status, quantidade in (
                ("Novos Domicílios", "Executada", 131),
                ("Novos Domicílios", "Não Executada", 68),
                ("PME", "Executada", 124),
                ("PME", "Não Executada", 1),
                ("Migração", "Executada", 9),
                ("Migração", "Não Executada", 3),
                ("Outros", "Executada", 1),
            )
        ]
    )

    matriz = quebra_geral.Motor._matriz_logic(df)
    monitor = matriz.loc[matriz["Monitor"] == "MONITOR A"].iloc[0]
    assert monitor["Novos Domicílios"] == 68 / (131 + 68)
    assert monitor["PME"] == 1 / (124 + 1)

    saidas: list[str] = []
    monkeypatch.setattr(
        quebra_geral, "st", SimpleNamespace(markdown=lambda html, **_: saidas.append(html))
    )
    quebra_geral.render_matriz_executiva(matriz)

    html = "".join(saidas)
    assert "34,2%" in html
    assert "0,8%" in html
    assert "25,0%" in html
    assert "337" in html
