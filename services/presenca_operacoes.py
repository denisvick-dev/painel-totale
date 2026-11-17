"""Operações auditáveis da chamada e conferência otimista de alterações."""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import date, datetime, timedelta

import pandas as pd

from services.absenteismo import (
    COLUNAS_REGISTROS,
    STATUS_CANCELADO,
    _cliente_gspread,
    _df_para_planilha,
    normalizar_registros,
    registros_vazios,
)
from services.lista_presenca import OPCOES_PRESENCA, registros_da_presenca

_LOCK = threading.RLock()


def assinatura(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()


def preparar_lote(matriz, dia, logins, situacao):
    if situacao not in OPCOES_PRESENCA[1:] or not logins:
        raise ValueError("Selecione técnicos e uma situação válida.")
    selecionados = matriz["Login"].isin(logins)
    if set(logins) - set(matriz["Login"]):
        raise ValueError("A seleção de técnicos mudou. Selecione novamente.")
    if matriz.loc[selecionados, dia].ne("Não preenchido").any():
        raise ValueError("O lote contém marcações existentes. Selecione apenas pendentes.")
    editada = matriz.copy()
    editada.loc[selecionados, dia] = situacao
    return registros_da_presenca(matriz, editada)


def corrigir_dia(registros, login, dia: date, situacao, motivo, responsavel):
    if not motivo.strip() or not responsavel.strip():
        raise ValueError("Informe o responsável e o motivo da correção.")
    if situacao not in OPCOES_PRESENCA[1:]:
        raise ValueError("Situação inválida.")
    atuais = registros.loc[
        registros["Login"].eq(login) & registros["Status"].ne(STATUS_CANCELADO)
        & registros["_inicio"].le(pd.Timestamp(dia)) & registros["_fim"].ge(pd.Timestamp(dia))
    ]
    if atuais.empty:
        raise ValueError("Nenhuma marcação existente para corrigir nessa data.")
    novos = []
    agora = datetime.now().isoformat(timespec="seconds")
    for _, linha in atuais.iterrows():
        # Cancela o original e preserva o restante de um lançamento por período.
        for inicio, fim in ((linha["_inicio"].date(), dia - timedelta(days=1)),
                            (dia + timedelta(days=1), linha["_fim"].date())):
            if inicio <= fim:
                parte = linha.to_dict()
                parte.update(ID=uuid.uuid4().hex, **{"Data Início": inicio.isoformat(),
                    "Data Fim": fim.isoformat(), "Registrado em": agora,
                    "Motivo": f"Preservado de {linha['ID']} na correção por {responsavel}"})
                novos.append(parte)
    novo = atuais.iloc[0].to_dict()
    novo.update(ID=uuid.uuid4().hex, Tipo=situacao, **{
        "Data Início": dia.isoformat(), "Data Fim": dia.isoformat(), "Registrado em": agora,
        "Motivo": f"Correção por {responsavel}: {motivo.strip()} | Substitui: {','.join(atuais['ID'])}",
    })
    novos.append(novo)
    saida = registros.copy()
    saida.loc[saida["ID"].isin(atuais["ID"]), "Status"] = STATUS_CANCELADO
    return normalizar_registros(pd.concat([
        saida.drop(columns=["_inicio", "_fim"], errors="ignore"),
        pd.DataFrame(novos).drop(columns=["_inicio", "_fim"], errors="ignore"),
    ], ignore_index=True))


def mesclar_conferindo(base, local, remoto):
    """Merge por ID; bloqueia alterações divergentes e novas marcações sobrepostas."""
    def mapa(df):
        if df["ID"].duplicated().any():
            raise ValueError("IDs duplicados no controle. Corrija a origem antes de gravar.")
        linhas = _df_para_planilha(df)[1:]
        return {str(id_): tuple(linha) for id_, linha in zip(df["ID"], linhas)}
    base_mapa, local_mapa, remoto_mapa = mapa(base), mapa(local), mapa(remoto)
    alterados = {id_ for id_ in local_mapa if local_mapa[id_] != base_mapa.get(id_)}
    ja_aplicado = all(remoto_mapa.get(id_) == local_mapa[id_] for id_ in alterados)
    for id_ in alterados & base_mapa.keys():
        if remoto_mapa.get(id_) != base_mapa[id_] and not ja_aplicado:
            raise ValueError("Conflito: outro usuário alterou um registro. Atualize os dados antes de tentar novamente.")
    cancelados_localmente = local.loc[
        local["ID"].isin(alterados) & local["Status"].eq(STATUS_CANCELADO), "ID"
    ]
    novos_remotos = remoto.loc[~remoto["ID"].isin(cancelados_localmente)]
    for linha in local.loc[local["ID"].isin(alterados) & local["Status"].ne(STATUS_CANCELADO)].to_dict("records"):
        choque = novos_remotos.loc[
            novos_remotos["Login"].eq(linha["Login"])
            & novos_remotos["Status"].ne(STATUS_CANCELADO)
            & novos_remotos["_inicio"].le(linha["_fim"])
            & novos_remotos["_fim"].ge(linha["_inicio"])
            & novos_remotos["ID"].ne(linha["ID"])
        ]
        if not choque.empty:
            raise ValueError("Conflito: o técnico já foi preenchido por outra sessão. Atualize a lista.")
    combinado = pd.concat([remoto.loc[~remoto["ID"].isin(alterados)], local.loc[local["ID"].isin(alterados)]])
    return normalizar_registros(combinado.drop(columns=["_inicio", "_fim"], errors="ignore"))


def _abrir():
    from config.settings import obter_sheet_id_ativos
    return _cliente_gspread().open_by_key(obter_sheet_id_ativos())


def _ler_controle(planilha):
    from gspread.exceptions import WorksheetNotFound

    from config.settings import SHEET_ABA_ABSENTEISMO
    try:
        aba = planilha.worksheet(SHEET_ABA_ABSENTEISMO)
    except WorksheetNotFound:
        return None, registros_vazios()
    valores = aba.get_all_values()
    if not valores:
        return aba, registros_vazios()
    if "ID" not in valores[0] or "Data Início" not in valores[0]:
        raise ValueError("Formato remoto incompatível. A gravação foi bloqueada para preservar a planilha.")
    return aba, normalizar_registros(pd.DataFrame(valores[1:], columns=valores[0]))


def salvar_conferindo(base, local):
    """Conferência remota imediatamente antes da escrita; lock só neste processo."""
    from config.settings import SHEET_ABA_ABSENTEISMO
    from services.sincronizacao import substituir_celulas_atomico
    try:
        with _LOCK:
            planilha = _abrir()
            aba, remoto = _ler_controle(planilha)
            combinado = mesclar_conferindo(base, local, remoto)
            if aba is None:
                aba = planilha.add_worksheet(title=SHEET_ABA_ABSENTEISMO, rows=1000, cols=len(COLUNAS_REGISTROS))
            substituir_celulas_atomico(planilha, aba, _df_para_planilha(combinado))
            return True, "", combinado
    except Exception as exc:
        return False, str(exc), local


def fechar_chamada(detalhes, dia, responsavel, confirmar_pendencias):
    from gspread.exceptions import WorksheetNotFound
    if not responsavel.strip():
        raise ValueError("Informe o responsável pelo fechamento.")
    pendentes = int(detalhes[dia].eq("Não preenchido").sum())
    if pendentes and not confirmar_pendencias:
        raise ValueError("Confirme o fechamento com pendências.")
    with _LOCK:
        planilha = _abrir()
        _, remoto = _ler_controle(planilha)
        from services.lista_presenca import montar_lista_presenca
        atual = montar_lista_presenca(remoto, detalhes, dia, dia).set_index("Login")
        for _, pessoa in detalhes.iterrows():
            if pessoa[dia] != atual.at[pessoa["Login"], dia]:
                raise ValueError("A lista remota mudou ou tem marcações não sincronizadas. Atualize antes de fechar.")
        evento = {"ID": uuid.uuid4().hex, "Data": dia.isoformat(), "Responsável": responsavel.strip(),
                  "Horário": datetime.now().isoformat(timespec="seconds"),
                  "Técnicos": len(detalhes), "Pendentes": pendentes,
                  "Presentes": int(detalhes[dia].eq("Presente").sum()),
                  "Ausentes": int((~detalhes[dia].isin(["Presente", "Não preenchido"])).sum()),
                  "Recorte": json.dumps(detalhes[["Login", "U.N.", "Monitor"]].to_dict("records"), ensure_ascii=False),
                  "Assinatura": assinatura(detalhes[["Login", dia]])}
        try:
            aba = planilha.worksheet("fechamentos_presenca")
        except WorksheetNotFound:
            aba = planilha.add_worksheet(title="fechamentos_presenca", rows=1000, cols=len(evento))
        if not aba.get_all_values():
            aba.append_row(list(evento), value_input_option="RAW")
        aba.append_row([str(v) for v in evento.values()], value_input_option="RAW")
        return evento


def consultar_fechamentos(dia):
    """Consulta explícita do histórico persistido, inclusive após nova sessão."""
    from gspread.exceptions import WorksheetNotFound
    try:
        aba = _abrir().worksheet("fechamentos_presenca")
    except WorksheetNotFound:
        return pd.DataFrame()
    valores = aba.get_all_values()
    if len(valores) < 2:
        return pd.DataFrame()
    dados = pd.DataFrame(valores[1:], columns=valores[0])
    return dados.loc[dados["Data"].eq(dia.isoformat())].drop(columns="Recorte", errors="ignore")
