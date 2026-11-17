"""Conversão assistida da grade legada, sem modificar a aba de origem."""
from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd

from services.absenteismo import (
    CODIGOS_AUSENCIA,
    MARCAS_PRESENCA,
    TIPOS_AUSENCIA,
    detectar_colunas_dias,
    normalizar_quadro_identidade,
    normalizar_registros,
)
from services.texto import buscar_coluna, normalizar_chave, normalizar_login

MANTER_PENDENTE = "Manter pendente (não importar)"


def ler_grade_legada() -> pd.DataFrame:
    from config.settings import obter_sheet_id_ativos
    from services.absenteismo import _cliente_gspread

    planilha = _cliente_gspread().open_by_key(obter_sheet_id_ativos())
    valores = planilha.worksheet("absenteismo").get_all_values()
    if not valores:
        raise ValueError("A aba absenteismo está vazia.")
    indices = [i for i, c in enumerate(valores[0]) if str(c).strip()]
    cabecalho = [str(valores[0][i]).strip() for i in indices]
    if len(cabecalho) != len(set(cabecalho)):
        raise ValueError("Há cabeçalhos repetidos na grade. Revise a origem antes de importar.")
    return pd.DataFrame([
        [linha[i] if i < len(linha) else "" for i in indices] for linha in valores[1:]
    ], columns=cabecalho)


def converter_grade(bruto: pd.DataFrame, referencia: date, mapeamento: dict[str, str] | None = None):
    """Uma marca por login/dia; códigos não reconhecidos bloqueiam a confirmação."""
    base = bruto.copy().reset_index(drop=True)
    base.columns = base.columns.astype(str).str.strip()
    dias = detectar_colunas_dias(base, referencia)
    if not dias:
        raise ValueError("Não foram identificadas colunas de dias suficientes na grade.")
    col_login = buscar_coluna(base, ("Login", "LOGIN", "Login do Técnico"))
    if not col_login:
        raise ValueError("A grade precisa ter a coluna Login; RE não substitui o login nesta importação.")
    mapa = {normalizar_chave(k): v for k, v in (mapeamento or {}).items()}
    oficiais = {normalizar_chave(tipo): tipo for tipo in TIPOS_AUSENCIA}
    oficiais.update(CODIGOS_AUSENCIA)
    presencas = {*MARCAS_PRESENCA, "ATIVO"}
    registros, pendencias, pulados = [], [], 0
    vistos = {}
    for indice, linha in base.iterrows():
        identidade = normalizar_quadro_identidade(pd.DataFrame([linha]))
        login = normalizar_login(linha[col_login])
        for coluna, dia in dias.items():
            valor = str(linha[coluna]).strip() if pd.notna(linha[coluna]) else ""
            if not valor:
                continue
            chave = normalizar_chave(valor)
            tipo = mapa.get(chave)
            if tipo is None:
                tipo = "Presente" if chave in presencas else oficiais.get(chave)
            if not login or identidade.empty:
                pendencias.append({"Linha": indice + 2, "Dia": dia.isoformat(), "Valor": valor, "Motivo": "Login ausente"})
                continue
            if tipo == MANTER_PENDENTE:
                pulados += 1
                continue
            if tipo not in ["Presente", *TIPOS_AUSENCIA]:
                pendencias.append({"Linha": indice + 2, "Dia": dia.isoformat(), "Valor": valor, "Motivo": "Defina o tratamento"})
                continue
            par = (login, dia)
            if par in vistos:
                pendencias.append({"Linha": indice + 2, "Dia": dia.isoformat(), "Valor": valor, "Motivo": "Login/dia repetido na grade"})
                continue
            vistos[par] = tipo
            pessoa = identidade.iloc[0]
            id_ = "legado-" + hashlib.sha256(f"absenteismo|{login}|{dia.isoformat()}".encode()).hexdigest()[:24]
            registros.append({
                "ID": id_, **{c: pessoa[c] for c in ("Login", "Técnico", "Monitor", "Base")},
                "Tipo": tipo, "Data Início": dia.isoformat(), "Data Fim": dia.isoformat(),
                "Status": "Ativo", "Motivo": f"Importado da aba absenteismo; linha {indice + 2}; valor original: {valor}",
            })
    return normalizar_registros(pd.DataFrame(registros)), pd.DataFrame(pendencias), pulados


def preparar_importacao(atuais: pd.DataFrame, importados: pd.DataFrame, responsavel: str):
    if not responsavel.strip():
        raise ValueError("Informe o responsável pela importação.")
    existentes = atuais.set_index("ID")
    for linha in importados.to_dict("records"):
        if linha["ID"] in existentes.index:
            antigo = existentes.loc[linha["ID"]]
            if antigo["Tipo"] != linha["Tipo"]:
                raise ValueError("Um registro legado já importado mudou de situação. Use a correção com histórico, não reimporte.")
    novos = importados.loc[~importados["ID"].isin(atuais["ID"])].copy()
    novos["Motivo"] = novos["Motivo"] + f" | Responsável pela importação: {responsavel.strip()}"
    novos["Registrado em"] = pd.Timestamp.now().isoformat(timespec="seconds")
    resultado = normalizar_registros(pd.concat([
        atuais.drop(columns=["_inicio", "_fim"], errors="ignore"),
        novos.drop(columns=["_inicio", "_fim"], errors="ignore"),
    ], ignore_index=True))
    return resultado, len(novos)
