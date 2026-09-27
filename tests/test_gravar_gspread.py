"""
Testes da gravação segura no Google Sheets — pages/gestao_ativos.py

Regressão do bug crítico: ``_gravar_gspread`` chamava ``ws.clear()`` ANTES do
``ws.update()``. Se o update falhasse (rede/rate-limit), a aba ficava vazia.
Os testes abaixo garantem que:

* ``clear()`` **nunca** é chamado;
* nada é removido antes de a gravação dar certo;
* falha na gravação preserva os dados originais;
* sobras (linhas/colunas de uma versão maior) são limpas só depois do sucesso.

Executar: pytest tests/test_gravar_gspread.py -v
"""

from __future__ import annotations

import pandas as pd
import pytest

from pages import gestao_ativos as ga


class FakeWorksheet:
    """Worksheet fake que registra a ordem das operações na planilha."""

    def __init__(self, valores: list[list[str]] | None = None, falhar_update: bool = False):
        self.valores = valores or []
        self.falhar_update = falhar_update
        self.operacoes: list[tuple[str, object]] = []

    # leitura
    def get_all_values(self) -> list[list[str]]:
        self.operacoes.append(("get_all_values", None))
        return [list(linha) for linha in self.valores]

    # escrita
    def update(self, *args, **kwargs):
        intervalo = kwargs.get("range_name") or (args[0] if args else None)
        self.operacoes.append(("update", intervalo))
        if self.falhar_update:
            raise RuntimeError("429 Too Many Requests (simulado)")
        dados = kwargs.get("values")
        if dados is None and len(args) >= 2:
            dados = args[1]
        self.valores = [list(linha) for linha in (dados or [])]
        return {}

    def batch_clear(self, faixas):
        self.operacoes.append(("batch_clear", tuple(faixas)))
        return {}

    def clear(self):  # pragma: no cover - deve nunca ser chamado
        self.operacoes.append(("clear", None))
        self.valores = []
        raise AssertionError("ws.clear() é destrutivo e não deve ser usado")


@pytest.fixture
def patch_ws(monkeypatch):
    def _aplicar(ws: FakeWorksheet):
        monkeypatch.setattr(ga, "_gspread_sheet", lambda _nome: ws)
        return ws
    return _aplicar


def _df(linhas: int, colunas: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        [[f"v{i}{j}" for j in range(colunas)] for i in range(linhas)],
        columns=[f"c{j}" for j in range(colunas)],
    )


def test_clear_nunca_e_chamado(patch_ws):
    ws = patch_ws(FakeWorksheet([["cab1", "cab2"], ["a", "b"]]))
    assert ga._gravar_gspread("ativos", _df(2, 2)) is True
    assert all(op != "clear" for op, _ in ws.operacoes)


def test_leitura_antes_da_escrita(patch_ws):
    ws = patch_ws(FakeWorksheet([["x"]]))
    ga._gravar_gspread("ativos", _df(2))
    nomes = [op for op, _ in ws.operacoes]
    assert nomes.index("get_all_values") < nomes.index("update")


def test_falha_no_update_preserva_dados_e_nao_limpa(patch_ws):
    """O cenário que antes destruía a aba inteira."""
    original = [["cab1", "cab2"], ["a", "b"], ["c", "d"]]
    ws = patch_ws(FakeWorksheet(original, falhar_update=True))

    resultado = ga._gravar_gspread("ativos", _df(5, 2))

    assert resultado is False                       # falhou
    assert ws.valores == original                   # dados intactos
    assert all(op != "batch_clear" for op, _ in ws.operacoes)
    assert all(op != "clear" for op, _ in ws.operacoes)


def test_limpa_sobras_de_linhas_depois_do_sucesso(patch_ws):
    ws = patch_ws(FakeWorksheet([["h1", "h2"]] + [[f"l{i}", "x"] for i in range(9)]))  # 10 linhas
    assert ga._gravar_gspread("ativos", _df(3, 2)) is True

    nomes = [op for op, _ in ws.operacoes]
    assert nomes.index("update") < nomes.index("batch_clear")
    faixa = dict(ws.operacoes)["batch_clear"][0]
    # 3 linhas de dados + cabeçalho = 4 linhas gravadas (A1:B4)
    # -> sobras são as linhas 5 a 10 da versão antiga
    assert faixa == "A5:B10"
    assert len(ws.valores) == 4                      # cabeçalho + 3 linhas


def test_limpa_sobras_de_colunas_depois_do_sucesso(patch_ws):
    ws = patch_ws(FakeWorksheet([["h1", "h2", "h3", "h4"], ["a", "b", "c", "d"]]))
    assert ga._gravar_gspread("ativos", _df(2, 2)) is True
    faixa = dict(ws.operacoes)["batch_clear"][0]
    assert faixa == "C1:D2"


def test_sem_sobras_nao_chama_batch_clear(patch_ws):
    ws = patch_ws(FakeWorksheet([["h1", "h2"], ["a", "b"]]))
    assert ga._gravar_gspread("ativos", _df(2, 2)) is True
    assert all(op != "batch_clear" for op, _ in ws.operacoes)


def test_dataframe_vazio_nao_grava(patch_ws):
    ws = patch_ws(FakeWorksheet([["h1"]]))
    assert ga._gravar_gspread("ativos", pd.DataFrame()) is False
    assert ws.operacoes == []


def test_intervalo_de_gravacao(patch_ws):
    ws = patch_ws(FakeWorksheet([["h1"]]))
    ga._gravar_gspread("ativos", _df(4, 3))
    intervalo = dict(ws.operacoes)["update"]
    assert intervalo == "A1:C5"                      # cabeçalho + 4 linhas


@pytest.mark.parametrize(
    ("indice", "esperado"),
    [(1, "A"), (26, "Z"), (27, "AA"), (52, "AZ"), (53, "BA"), (703, "AAA")],
)
def test_col_letra(indice, esperado):
    assert ga._col_letra(indice) == esperado
