"""Validação dos lançamentos em lote da grade mensal."""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pandas as pd

from services.absenteismo import ABREVIACOES_AUSENCIA, STATUS_ATIVO


def registros_do_preenchimento(original: pd.DataFrame, editada: pd.DataFrame) -> list[dict]:
    """Converte apenas células vazias preenchidas; nunca sobrescreve ausências."""
    tipos = {codigo: tipo for tipo, codigo in ABREVIACOES_AUSENCIA.items()}
    tipos["P"] = "Presente"
    # Situação operacional exibida no fluxo diário, sem ser classificada como falta.
    tipos["BAIXA DE KIT"] = "BAIXA DE KIT"
    if not original.index.equals(editada.index) or list(original.columns) != list(editada.columns):
        raise ValueError("A estrutura da tabela foi alterada. Reabra o preenchimento.")
    novos = []
    for indice, pessoa in original.iterrows():
        for coluna in original.columns:
            antes = str(pessoa[coluna]) if pd.notna(pessoa[coluna]) else ""
            valor = editada.at[indice, coluna]
            depois = str(valor) if pd.notna(valor) else ""
            if antes == depois:
                continue
            if not isinstance(coluna, date):
                raise ValueError("Os dados do técnico e os totais não podem ser alterados.")
            if antes:
                raise ValueError("Há uma ausência existente alterada. Cancele o registro antes de corrigir o dia.")
            if not depois:
                continue
            if depois not in tipos:
                raise ValueError("Selecione um código de ausência válido.")
            if not str(pessoa["Login"]).strip() or not str(pessoa["Técnico"]).strip():
                raise ValueError("O técnico precisa ter login e nome para receber um lançamento.")
            novos.append({
                "ID": uuid.uuid4().hex[:12],
                **{campo: pessoa[campo] for campo in ("Login", "Técnico", "Monitor", "Base")},
                "Tipo": tipos[depois],
                "Data Início": coluna.isoformat(),
                "Data Fim": coluna.isoformat(),
                "Status": STATUS_ATIVO,
                "Motivo": "Preenchimento pela grade mensal",
                "Registrado em": datetime.now().strftime("%d/%m/%Y %H:%M"),
            })
    return novos


def recortar_grade(original: pd.DataFrame, dias: list[date]) -> pd.DataFrame:
    """Seleciona dias sem perder a identidade e recalcula o total visível."""
    selecionados = [c for c in original.columns if isinstance(c, date) and c in dias]
    identidade = [c for c in original.columns if not isinstance(c, date) and c != "Total"]
    recorte = original[[*identidade, *selecionados]].copy()
    recorte["Total"] = recorte[selecionados].fillna("").astype(str).apply(
        lambda coluna: coluna.str.strip().ne("")
    ).sum(axis=1).astype(int)
    return recorte


def resumir_grade(matriz: pd.DataFrame) -> dict[str, int]:
    """Indicadores do mapa: dias marcados, não quantidade de códigos."""
    dias = [c for c in matriz.columns if isinstance(c, date)]
    marcas = matriz[dias].fillna("").astype(str).apply(lambda coluna: coluna.str.strip().ne(""))
    return {
        "tecnicos": len(matriz),
        "com_ausencia": int(marcas.any(axis=1).sum()),
        "dias_marcados": int(marcas.sum().sum()),
    }


def filtrar_grade_preenchimento(
    matriz: pd.DataFrame,
    dias: list[date],
    unidades: list[str] | None = None,
    monitores: list[str] | None = None,
) -> pd.DataFrame:
    """Recorte exclusivo do editor, preservando índices para validar os lançamentos."""
    recorte = matriz.copy()
    for coluna, valores in (("U.N.", unidades), ("Monitor", monitores)):
        if valores:
            rotulos = recorte[coluna].fillna("").astype(str).str.strip().replace("", "Não informado")
            recorte = recorte.loc[rotulos.isin(valores)]
    return recortar_grade(recorte, dias)
