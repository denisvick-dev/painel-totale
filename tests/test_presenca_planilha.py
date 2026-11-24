"""Testes da chamada gravada na planilha externa lista_de_presenca."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from services.lista_presenca import normalizar_planilha_lista_presenca
from services.presenca_planilha import (
    coluna_dia,
    datas_da_planilha,
    filtrar_equipe,
    montar_tabela,
    planejar_alteracoes,
    salvar,
)

DIA = date(2026, 11, 17)
OUTRO_DIA = date(2026, 11, 18)


def _planilha() -> pd.DataFrame:
    return normalizar_planilha_lista_presenca(
        pd.DataFrame(
            {
                "RE": ["8368", "8496", "8554"],
                "Login": ["Z641759", "Z663524", "Z657046"],
                "Técnico": ["Ana", "Bia", "Caio"],
                "Monitor": ["Edson", "Edson", "Alan"],
                "U.N.": ["ABCDM-TOTALE", "ABCDM-TOTALE", "SPO-TOTALLESTE"],
                "Base": ["NET-ABCDM", "NET-ABCDM", "NET-LESTE"],
                "17/nov.": ["", "FALTA", "ATIVO"],
                "18/nov.": ["", "", "FOLGA"],
            }
        )
    )


def _cliente(dados: pd.DataFrame, atualizacoes: list):
    valores = [list(dados.columns), *dados.astype(str).values.tolist()]
    aba = SimpleNamespace(id=5, get_all_values=lambda: [linha.copy() for linha in valores])
    planilha = SimpleNamespace(sheet1=aba, batch_update=atualizacoes.append)
    return SimpleNamespace(
        open_by_key=lambda sheet_id: planilha,
        set_timeout=lambda timeout: None,
    )


def test_colunas_e_datas_da_planilha() -> None:
    dados = pd.DataFrame(columns=["1/nov.", "15/nov.", "2/dez.", "Técnico"])
    assert coluna_dia(DIA) == "17/nov."
    assert datas_da_planilha(dados, date(2026, 11, 24)) == [
        date(2026, 11, 1),
        date(2026, 11, 15),
        date(2026, 12, 2),
    ]


def test_filtros_e_tabela_compacta() -> None:
    dados = _planilha()
    filtrado = filtrar_equipe(dados, unidades=["ABCDM-TOTALE"], monitores=["Edson"])
    assert filtrado["Login"].tolist() == ["Z641759", "Z663524"]

    tabela = montar_tabela(filtrado, [DIA])
    assert tabela.columns.tolist() == ["RE", "Login", "Técnico", "Monitor", "Status"]
    assert tabela["Status"].tolist() == ["", "FALTA"]

    por_busca = filtrar_equipe(dados, busca="z657046")
    assert por_busca["Login"].tolist() == ["Z657046"]


def test_planejamento_valida_cadastro_status_e_conflito() -> None:
    dados = _planilha()
    editada = montar_tabela(dados, [DIA])

    editada.loc[0, "RE"] = "0000"
    with pytest.raises(ValueError, match="cadastrais"):
        planejar_alteracoes(dados, editada, [DIA])

    editada = montar_tabela(dados, [DIA])
    editada.loc[0, "Status"] = "NÃO É UMA SITUAÇÃO"
    with pytest.raises(ValueError, match="situações disponíveis"):
        planejar_alteracoes(dados, editada, [DIA])

    editada = montar_tabela(dados, [DIA])
    editada.loc[0, "Status"] = "ATIVO"
    remoto = dados.copy()
    remoto.loc[0, "17/nov."] = "FALTA"
    with pytest.raises(ValueError, match="Conflito"):
        planejar_alteracoes(dados, editada, [DIA], remoto)


def test_salvar_atualiza_varios_dias_em_uma_requisicao() -> None:
    dados = _planilha()
    atualizacoes = []
    cliente = _cliente(dados, atualizacoes)
    editada = montar_tabela(dados, [DIA, OUTRO_DIA])
    assert editada.columns.tolist() == [
        "RE", "Login", "Técnico", "Monitor",
        DIA.isoformat(), OUTRO_DIA.isoformat(),
    ]
    editada.loc[0, DIA.isoformat()] = "ATIVO"
    editada.loc[0, OUTRO_DIA.isoformat()] = "ATESTADO"

    ok, motivo, _, quantidade = salvar(
        dados, editada, [DIA, OUTRO_DIA], sheet_id="planilha-teste", cliente=cliente
    )

    assert ok and not motivo
    assert quantidade == 2
    assert len(atualizacoes) == 1
    pedidos = atualizacoes[0]["requests"]
    assert len(pedidos) == 2
    valores = [
        pedido["updateCells"]["rows"][0]["values"][0]["userEnteredValue"]["stringValue"]
        for pedido in pedidos
    ]
    assert sorted(valores) == ["ATESTADO", "ATIVO"]
