"""Utilitários de persistência sem dependência da interface Streamlit."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def substituir_celulas_atomico(planilha: Any, aba: Any, dados: list[list[str]]) -> None:
    """Substitui valores e remove sobras na mesma requisição Google Sheets.

    updateCells com range explícito limpa os valores não cobertos pelas linhas
    enviadas. Apenas userEnteredValue é alterado: formatação fica preservada.
    """
    linhas = max(aba.row_count, len(dados))
    colunas = max(aba.col_count, max((len(linha) for linha in dados), default=1))
    pedidos = []
    if linhas > aba.row_count or colunas > aba.col_count:
        pedidos.append({"updateSheetProperties": {
            "properties": {"sheetId": aba.id, "gridProperties": {
                "rowCount": linhas, "columnCount": colunas,
            }}, "fields": "gridProperties.rowCount,gridProperties.columnCount",
        }})
    pedidos.append({"updateCells": {
        "range": {"sheetId": aba.id, "startRowIndex": 0, "endRowIndex": linhas,
                  "startColumnIndex": 0, "endColumnIndex": colunas},
        "rows": [{"values": [{"userEnteredValue": {"stringValue": str(v)}} for v in linha]}
                 for linha in dados],
        "fields": "userEnteredValue",
    }})
    planilha.batch_update({"requests": pedidos})


def sincronizar_abas(alteracoes: dict, gravar: Callable, invalidar: Callable) -> dict:
    """Relata sucesso parcial e sempre invalida abas já escritas.

    Não promete transação entre abas; a primeira falha interrompe o envio.
    """
    resultado = {"ok": True, "gravadas": [], "pendentes": list(alteracoes), "mensagem": ""}
    for aba, dados in alteracoes.items():
        try:
            gravar(aba, dados)
        except Exception as exc:
            resultado.update(ok=False, mensagem=f"{aba}: {exc}")
            break
        resultado["gravadas"].append(aba)
        resultado["pendentes"].remove(aba)
        invalidar(aba)
    return resultado
