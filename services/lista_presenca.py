"""Lista de presença explícita: vazio nunca confirma presença."""
from datetime import date

import pandas as pd

from services.absenteismo import (
    ABREVIACOES_AUSENCIA,
    STATUS_CANCELADO,
    montar_matriz_ausencias,
)
from services.absenteismo_grade import registros_do_preenchimento

OPCOES_PRESENCA = (
    "Não preenchido", "Presente", "Falta", "Folga", "Férias", "Atestado",
    "Afastamento", "Licença", "Treinamento",
)
CODIGOS = {codigo: tipo for tipo, codigo in ABREVIACOES_AUSENCIA.items()}
CODIGOS["P"] = "Presente"


def montar_lista_presenca(registros, quadro, inicio: date, fim: date) -> pd.DataFrame:
    matriz = montar_matriz_ausencias(registros, quadro, inicio=inicio, fim=fim)
    presentes = registros.loc[
        registros["Tipo"].eq("Presente") & registros["Status"].ne(STATUS_CANCELADO)
    ]
    dias = [c for c in matriz.columns if isinstance(c, date)]
    for dia in dias:
        logins = presentes.loc[
            (presentes["_inicio"].dt.date <= dia) & (presentes["_fim"].dt.date >= dia), "Login"
        ]
        # Ausência sobreposta tem precedência; não ocultar conflito operacional.
        matriz.loc[matriz["Login"].isin(logins) & matriz[dia].eq(""), dia] = "P"
        matriz[dia] = matriz[dia].map(lambda v: CODIGOS.get(v, v) if v else "Não preenchido")
    # Situações operacionais da grade são exibidas por extenso e não viram
    # falta ou presença por inferência.
    operacionais = registros.loc[
        registros["Tipo"].str.upper().isin(["DUPLADO", "BAIXA DE KIT"])
        & registros["Status"].ne(STATUS_CANCELADO)
    ]
    for dia in dias:
        no_dia = operacionais.loc[(operacionais["_inicio"].dt.date <= dia) & (operacionais["_fim"].dt.date >= dia)]
        for _, linha in no_dia.iterrows():
            matriz.loc[matriz["Login"].eq(linha["Login"]), dia] = linha["Tipo"]
    matriz["Total"] = matriz[dias].ne("Não preenchido").sum(axis=1)
    return matriz


def registros_da_presenca(original, editada):
    def codificar(matriz):
        copia = matriz.copy()
        reverso = {tipo: codigo for codigo, tipo in CODIGOS.items()}
        for coluna in copia.columns:
            if isinstance(coluna, date):
                copia[coluna] = copia[coluna].map(
                    lambda v: "" if v == "Não preenchido" else reverso.get(v, v)
                )
        return copia
    return registros_do_preenchimento(codificar(original), codificar(editada))


def resumo_presenca(matriz, dia):
    valores = matriz[dia].fillna("Não preenchido")
    operacionais = valores.str.upper().isin(["DUPLADO", "BAIXA DE KIT"])
    resultado = {
        "Presentes": int(valores.eq("Presente").sum()),
        "Ausentes": int((~valores.isin(["Presente", "Não preenchido"]) & ~operacionais).sum()),
        "Pendentes": int(valores.eq("Não preenchido").sum()),
    }
    if operacionais.any():
        resultado["Situação operacional"] = int(operacionais.sum())
    return resultado
