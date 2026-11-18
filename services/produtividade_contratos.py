"""Indicadores agregados de produção e contratos atendidos na carga Prod."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from services.produtividade import ALIASES_PRODUCAO, NAO_INFORMADO, normalizar_producao
from services.texto import buscar_coluna, normalizar_chave, normalizar_texto

# Somente nomes explícitos de identificador: não confundir tipo de contrato,
# projeto, pedido ou O.S. com o número de contrato do cliente.
ALIASES_CONTRATO = {
    "CONTRATO", "NCONTRATO", "NUMEROCONTRATO", "NUMERODOCONTRATO",
    "IDCONTRATO", "CODIGOCONTRATO", "CODCONTRATO", "CONTRATOCLIENTE",
}
INVALIDOS = {"", "NAN", "NONE", "NULL", "N/A", "NA", "-", "0", "0.0", "<NA>"}


def _contrato(valor: Any) -> str | None:
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if not math.isfinite(valor):
            return None
        texto = str(int(valor)) if float(valor).is_integer() else str(valor)
    else:
        texto = normalizar_texto(valor)
    return None if texto in INVALIDOS else texto


def preparar_producao(origem: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """Normaliza produção e preserva somente uma coluna explícita de contrato."""
    dados = normalizar_producao(origem)
    coluna = next((c for c in origem.columns if normalizar_chave(c) in ALIASES_CONTRATO), None)
    dados["Data"] = dados["Data"].dt.normalize()
    if buscar_coluna(origem, ALIASES_PRODUCAO["Pontos"]) is None:
        dados["Pontos"] = float("nan")
    dados["Contrato"] = origem[coluna].map(_contrato).reset_index(drop=True) if coluna is not None else None
    return dados, coluna


def resumir(dados: pd.DataFrame) -> dict[str, Any]:
    """Uma linha da carga equivale a uma O.S.; equipe-dia é produção observada."""
    validos = dados["Contrato"].dropna()
    equipe = dados.loc[dados["Equipe"].ne(NAO_INFORMADO) & dados["Data"].notna()]
    pares = equipe.drop_duplicates(["Base", "Supervisor", "Equipe", "Data"])
    return {
        "os": len(dados),
        "contratos": int(validos.nunique()) if not validos.empty else None,
        "os_com_contrato": int(validos.size),
        "pontos": dados["Pontos"].sum(min_count=1),
        "equipes_dia": len(pares),
        "os_equipe_dia": len(equipe) / len(pares) if len(pares) else None,
        "os_com_equipe_data": len(equipe),
    }


def agrupar(dados: pd.DataFrame, dimensoes: list[str]) -> pd.DataFrame:
    """Contratos distintos são calculados dentro de cada grupo, não somáveis."""
    colunas = [*dimensoes, "O.S.", "Contratos", "O.S. com contrato", "Pontos"]
    if dados.empty:
        return pd.DataFrame(columns=colunas)
    resultado = dados.groupby(dimensoes, dropna=False).agg(
        **{"O.S.": ("O.S.", "size"), "Contratos": ("Contrato", "nunique"),
           "O.S. com contrato": ("Contrato", "count"), "Pontos": ("Pontos", lambda valores: valores.sum(min_count=1))}
    ).reset_index()
    resultado.loc[resultado["O.S. com contrato"].eq(0), "Contratos"] = pd.NA
    return resultado.sort_values("O.S.", ascending=False).reset_index(drop=True)[colunas]
