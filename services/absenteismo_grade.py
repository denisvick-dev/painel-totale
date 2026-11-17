"""Validação dos lançamentos em lote da grade mensal."""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pandas as pd

from services.absenteismo import ABREVIACOES_AUSENCIA, STATUS_ATIVO


def registros_do_preenchimento(original: pd.DataFrame, editada: pd.DataFrame) -> list[dict]:
    """Converte apenas células vazias preenchidas; nunca sobrescreve ausências."""
    tipos = {codigo: tipo for tipo, codigo in ABREVIACOES_AUSENCIA.items()}
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
