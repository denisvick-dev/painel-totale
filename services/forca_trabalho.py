"""Disponibilidade estimada do quadro por dia, sem dependência do Streamlit."""
from datetime import date

import pandas as pd

from services.absenteismo import montar_matriz_ausencias, normalizar_quadro_identidade


def calcular_forca_trabalho(
    quadro: pd.DataFrame, registros: pd.DataFrame, dia: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Uma pessoa por login; ausências sobrepostas contam apenas uma vez.

    Somente integrantes do quadro entram no denominador. Um registro antigo
    de pessoa fora do quadro não cria capacidade operacional adicional.
    Sem ausência registrada significa disponibilidade estimada, não presença.
    """
    identidade = normalizar_quadro_identidade(quadro)
    matriz = montar_matriz_ausencias(registros, quadro, inicio=dia, fim=dia)
    detalhes = matriz.loc[matriz["Login"].isin(identidade["Login"])].copy()
    detalhes = detalhes.rename(columns={dia: "Códigos"}).drop(columns="Total")
    detalhes["Com ausência"] = detalhes["Códigos"].fillna("").astype(str).str.strip().ne("")
    detalhes["Situação no dia"] = detalhes["Com ausência"].map(
        {True: "Ausência registrada", False: "Disponível estimado"}
    )
    for coluna in ("Base", "Monitor"):
        detalhes[coluna] = detalhes[coluna].fillna("").replace("", "Não informado")
    resumo = detalhes.groupby(["Base", "Monitor"], as_index=False).agg(
        Quadro=("Login", "size"), Ausentes=("Com ausência", "sum"),
    )
    resumo["Ausentes"] = resumo["Ausentes"].astype(int)
    resumo["Disponíveis estimados"] = resumo["Quadro"] - resumo["Ausentes"]
    resumo["Disponibilidade (%)"] = (
        resumo["Disponíveis estimados"] / resumo["Quadro"] * 100
    ).round(1)
    return resumo, detalhes.drop(columns="Com ausência").reset_index(drop=True)
