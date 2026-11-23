"""Lista de presença explícita: vazio nunca confirma presença."""
from datetime import date
import re
from typing import Any

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


COLUNAS_FIXAS_PLANILHA_PRESENCA: tuple[str, ...] = (
    "RE", "Login", "Técnico", "Monitor", "U.N.", "Base",
)
_PADRAO_COLUNA_DIA = re.compile(r"^\d{1,2}/[a-zA-ZçÇ]{3,}\.?$")


def identificar_colunas_dias_planilha(df: pd.DataFrame) -> list[str]:
    """Retorna as colunas diárias (ex.: ``1/nov.``) na ordem da planilha."""
    return [str(col) for col in df.columns if _PADRAO_COLUNA_DIA.match(str(col).strip())]


def normalizar_planilha_lista_presenca(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa cabeçalhos e padroniza células vazias/valores da planilha externa."""
    if df is None or df.empty:
        return pd.DataFrame()
    copia = df.copy()
    copia.columns = [str(c).strip() for c in copia.columns]
    for col in COLUNAS_FIXAS_PLANILHA_PRESENCA:
        if col in copia.columns:
            copia[col] = copia[col].fillna("").astype(str).str.strip()
    colunas_dias = identificar_colunas_dias_planilha(copia)
    for col in colunas_dias:
        copia[col] = (
            copia[col]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"": "Não preenchido", "NAN": "Não preenchido", "NONE": "Não preenchido"})
        )
    if "Login" in copia.columns:
        copia = copia.loc[copia["Login"].ne("") | copia.get("Técnico", pd.Series("", index=copia.index)).ne("")]
    return copia.reset_index(drop=True)


def carregar_planilha_lista_presenca(
    sheet_id: str | None = None,
    ttl: int = 300,
) -> pd.DataFrame:
    """Carrega a planilha externa ``lista_de_presenca`` do Google Sheets."""
    from config.settings import obter_sheet_id_presenca
    from services.google_drive_client import carregar_planilha_gsheets_csv

    sid = str(sheet_id or obter_sheet_id_presenca() or "").strip()
    if not sid:
        return pd.DataFrame()
    bruto = carregar_planilha_gsheets_csv(sheet_id=sid, ttl=ttl)
    return normalizar_planilha_lista_presenca(bruto)


def resumir_planilha_lista_presenca(df: pd.DataFrame) -> dict[str, Any]:
    """Calcula indicadores agregados da planilha ``lista_de_presenca``."""
    if df is None or df.empty:
        return {
            "tecnicos": 0,
            "dias_total": 0,
            "dias_preenchidos": 0,
            "ativo": 0,
            "falta": 0,
            "atestado": 0,
            "outros": 0,
        }
    colunas_dias = identificar_colunas_dias_planilha(df)
    if not colunas_dias:
        return {
            "tecnicos": int(len(df)),
            "dias_total": 0,
            "dias_preenchidos": 0,
            "ativo": 0,
            "falta": 0,
            "atestado": 0,
            "outros": 0,
        }
    valores = df[colunas_dias].stack().astype(str).str.strip().str.upper()
    preenchidos = valores[valores.ne("NÃO PREENCHIDO") & valores.ne("")]
    dias_com_dados = sum(
        bool(df[col].astype(str).str.strip().str.upper().ne("NÃO PREENCHIDO").any())
        for col in colunas_dias
    )
    ativo = int(preenchidos.eq("ATIVO").sum())
    falta = int(preenchidos.eq("FALTA").sum())
    atestado = int(preenchidos.eq("ATESTADO").sum())
    outros = int(len(preenchidos) - ativo - falta - atestado)
    return {
        "tecnicos": int(len(df)),
        "dias_total": int(len(colunas_dias)),
        "dias_preenchidos": int(dias_com_dados),
        "ativo": ativo,
        "falta": falta,
        "atestado": atestado,
        "outros": outros,
    }
