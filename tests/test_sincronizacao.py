from types import SimpleNamespace

import pytest

from services.sincronizacao import sincronizar_abas, substituir_celulas_atomico


def test_substituicao_atomica_preserva_formato_e_limpa_sobras():
    chamadas = []
    planilha = SimpleNamespace(batch_update=chamadas.append)
    aba = SimpleNamespace(id=12, row_count=100, col_count=20)
    substituir_celulas_atomico(planilha, aba, [["ID"], ["123"]])
    assert len(chamadas) == 1
    pedido = chamadas[0]["requests"][0]["updateCells"]
    assert pedido["range"]["endRowIndex"] == 100
    assert pedido["fields"] == "userEnteredValue"
    assert pedido["rows"][1]["values"][0]["userEnteredValue"] == {"stringValue": "123"}


def test_expansao_na_mesma_requisicao():
    chamadas = []
    substituir_celulas_atomico(SimpleNamespace(batch_update=chamadas.append),
                              SimpleNamespace(id=1, row_count=1, col_count=1),
                              [["a", "b"], ["c", "d"]])
    assert len(chamadas[0]["requests"]) == 2


def test_falha_nao_e_sucesso():
    def falhar(_):
        raise RuntimeError("Sem permissão")
    with pytest.raises(RuntimeError):
        substituir_celulas_atomico(SimpleNamespace(batch_update=falhar),
                                  SimpleNamespace(id=1, row_count=10, col_count=3), [["a"]])


def test_sincronizacao_parcial_invalida_cache_das_abas_gravadas():
    gravadas, invalidadas = [], []
    def gravar(aba, dados):
        if aba == "B":
            raise RuntimeError("offline")
        gravadas.append(aba)
    resultado = sincronizar_abas({"A": [], "B": [], "C": []}, gravar, invalidadas.append)
    assert not resultado["ok"]
    assert resultado["gravadas"] == gravadas == invalidadas == ["A"]
    assert resultado["pendentes"] == ["B", "C"]
    assert "offline" in resultado["mensagem"]


def test_sincronizacao_completa():
    resultado = sincronizar_abas({"A": []}, lambda *_: None, lambda _: None)
    assert resultado["ok"]
    assert resultado["pendentes"] == []
