"""Acesso direto à grade absenteismo: escrita localizada, sem substituir a aba."""
from __future__ import annotations

import hashlib
import threading
from datetime import date, datetime

import pandas as pd

from services.absenteismo import (
    CODIGOS_AUSENCIA,
    MARCAS_PRESENCA,
    STATUS_CANCELADO,
    TIPOS_AUSENCIA,
    _cliente_gspread,
    detectar_colunas_dias,
    normalizar_registros,
)
from services.texto import buscar_coluna, normalizar_chave, normalizar_login

CHAVE_SNAPSHOT = "presenca_grade_snapshot"
ABA_GRADE = "absenteismo"
ABA_AUDITORIA = "auditoria_presenca"
_LOCK = threading.RLock()


def interpretar_valores(valores: list[list], referencia: date | None = None, formulas=None) -> dict:
    if not valores:
        raise ValueError("A aba absenteismo está vazia. Cadastre os técnicos e as datas na planilha.")
    cabecalho = []
    for valor in valores[0]:
        if isinstance(valor, (int, float)) and 20000 < valor < 100000:
            valor = (pd.Timestamp("1899-12-30") + pd.Timedelta(days=valor)).date().isoformat()
        cabecalho.append(str(valor).strip())
    indices = [i for i, nome in enumerate(cabecalho) if nome]
    nomes = [cabecalho[i] for i in indices]
    if len(nomes) != len(set(nomes)):
        raise ValueError("A grade contém cabeçalhos duplicados. Revise a origem.")
    bruto = pd.DataFrame([
        [linha[i] if i < len(linha) else "" for i in indices] for linha in valores[1:]
    ], columns=nomes)
    dias = detectar_colunas_dias(bruto, referencia)
    if not dias:
        raise ValueError("Não foi possível identificar as datas da grade absenteismo.")
    login_col = buscar_coluna(bruto, ("Login", "LOGIN DO TÉCNICO"))
    if not login_col:
        raise ValueError("A grade precisa de uma coluna Login.")
    linhas, pessoas, celulas, registros = {}, [], {}, []
    aliases = {
        "RE": ("RE", "MATRÍCULA", "MATRICULA"),
        "Técnico": ("Técnico", "TECNICO", "Nome Equipe", "Equipe"),
        "Monitor": ("Monitor", "Supervisor"),
        "Base": ("Base",),
        "U.N.": ("U.N.", "UN"),
        "Cód.Equipe": ("Cód.Equipe", "Cód Equipe", "CodEquipe", "Código Equipe", "Cod Equipe"),
        "Cód.Aux.Equipe": (
            "Cód.Aux.Equipe", "Cód Aux Equipe", "CódAuxEquipe", "CodAuxEquipe", "Cod Aux Equipe",
        ),
    }
    colunas = {nome: buscar_coluna(bruto, opcoes) for nome, opcoes in aliases.items()}
    tipos = {normalizar_chave(t): t for t in TIPOS_AUSENCIA}
    tipos.update(CODIGOS_AUSENCIA)
    for indice, linha in bruto.iterrows():
        login = normalizar_login(linha[login_col])
        if not login:
            if any(str(linha[c]).strip() for c in dias):
                raise ValueError(f"Linha {indice + 2} tem marcações sem login. Corrija a origem antes de continuar.")
            continue
        if login in linhas:
            raise ValueError(f"Login repetido nas linhas {linhas[login][0] + 1} e {indice + 2}. Revise a grade.")
        pessoa = {nome: str(linha[col]).strip() if col else "" for nome, col in colunas.items()}
        pessoa["Login"] = login
        pessoas.append(pessoa)
        linhas[login] = (indice + 1, pessoa)
        for coluna, dia in dias.items():
            valor = linha[coluna]
            texto = str(valor).strip() if pd.notna(valor) else ""
            posicao = (indice + 1, indices[nomes.index(coluna)])
            formula = ""
            if formulas and indice + 1 < len(formulas) and posicao[1] < len(formulas[indice + 1]):
                formula = str(formulas[indice + 1][posicao[1]])
            celulas[(login, dia)] = {"posicao": posicao, "valor": valor, "texto": texto,
                                    "formula": formula if formula.startswith("=") else ""}
            if not texto:
                continue
            chave = normalizar_chave(texto)
            tipo = "Presente" if chave in {*MARCAS_PRESENCA, "ATIVO"} else tipos.get(chave, texto)
            id_ = "grade-" + hashlib.sha256(f"{login}|{dia.isoformat()}".encode()).hexdigest()[:24]
            registros.append({"ID": id_, **{c: pessoa[c] for c in ("Login", "Técnico", "Monitor", "Base")},
                              "Tipo": tipo, "Data Início": dia.isoformat(), "Data Fim": dia.isoformat(),
                              "Status": "Ativo", "Motivo": f"Grade absenteismo · linha {indice + 2}", "Registrado em": ""})
    return {"registros": normalizar_registros(pd.DataFrame(registros)), "celulas": celulas,
            "pessoas": pd.DataFrame(
                pessoas,
                columns=[
                    "RE", "Login", "Técnico", "Monitor", "Base", "U.N.",
                    "Cód.Equipe", "Cód.Aux.Equipe",
                ],
            ),
            "dias": list(dias.values())}


def _abrir():
    from config.settings import obter_sheet_id_ativos
    cliente = _cliente_gspread()
    # Evita espera de rede sem limite durante leitura e salvamento da chamada.
    cliente.set_timeout((5, 20))
    return cliente.open_by_key(obter_sheet_id_ativos())


def ler_snapshot(planilha=None):
    planilha = planilha or _abrir()
    aba = planilha.worksheet(ABA_GRADE)
    # Datas reais são lidas como seriais para não inferir o ano pelo rótulo 1/nov.
    valores = aba.get_all_values(value_render_option="UNFORMATTED_VALUE")
    formulas = aba.get_all_values(value_render_option="FORMULA")
    return interpretar_valores(valores, formulas=formulas)


def carregar_grade_sessao(forcar=False):
    import streamlit as st

    from services.absenteismo import CHAVE_SESSAO_REGISTROS
    if forcar or CHAVE_SNAPSHOT not in st.session_state:
        snapshot = ler_snapshot()
        st.session_state[CHAVE_SNAPSHOT] = snapshot
        st.session_state[CHAVE_SESSAO_REGISTROS] = snapshot["registros"]
    return st.session_state[CHAVE_SNAPSHOT]["registros"].copy()


def _marcas(df):
    marcas = {}
    for linha in df.loc[df["Status"].ne(STATUS_CANCELADO)].to_dict("records"):
        for data in pd.date_range(linha["_inicio"], linha["_fim"]):
            par = (linha["Login"], data.date())
            if par in marcas and marcas[par] != linha["Tipo"]:
                raise ValueError("Há situações sobrepostas para o mesmo técnico e dia. Use a correção da marcação.")
            marcas[par] = linha["Tipo"]
    return marcas


def planejar_alteracoes(snapshot, base, local, remoto):
    antigas, novas = _marcas(base), _marcas(local)
    alteracoes = []
    for par in antigas.keys() | novas.keys():
        if antigas.get(par) == novas.get(par):
            continue
        if par not in snapshot["celulas"] or par not in remoto["celulas"]:
            raise ValueError("Técnico ou dia não existe na grade. Cadastre a linha/data na planilha antes de preencher.")
        esperado, atual = snapshot["celulas"][par], remoto["celulas"][par]
        if atual.get("formula") or esperado.get("formula"):
            raise ValueError("A célula contém fórmula e não será substituída pelo painel.")
        if esperado["texto"] != atual["texto"]:
            raise ValueError("Conflito: a célula foi alterada no Drive. Atualize a lista antes de tentar novamente.")
        tipo = novas.get(par, "")
        texto = {"Presente": "ATIVO", "Afastamento": "AFASTADO"}.get(tipo, tipo.upper())
        alteracoes.append({"par": par, "posicao": atual["posicao"], "antes": atual["texto"], "depois": texto})
    return alteracoes


def salvar_grade(snapshot, base, local):
    """Atualiza somente células alteradas e anexa auditoria no mesmo batchUpdate."""
    try:
        with _LOCK:
            planilha = _abrir()
            aba = planilha.worksheet(ABA_GRADE)
            remoto = ler_snapshot(planilha)
            alteracoes = planejar_alteracoes(snapshot, base, local, remoto)
            pedidos, historico = [], []
            agora = datetime.now().isoformat(timespec="seconds")
            for item in alteracoes:
                linha, coluna = item["posicao"]
                pedidos.append({"updateCells": {"range": {"sheetId": aba.id, "startRowIndex": linha,
                    "endRowIndex": linha + 1, "startColumnIndex": coluna, "endColumnIndex": coluna + 1},
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": item["depois"]}}]}],
                    "fields": "userEnteredValue"}})
                login, dia = item["par"]
                motivos = local.loc[local["Login"].eq(login) & local["_inicio"].le(pd.Timestamp(dia))
                    & local["_fim"].ge(pd.Timestamp(dia)), "Motivo"].tolist()
                historico.append([agora, login, dia.isoformat(), item["antes"], item["depois"], " | ".join(motivos)])
            if pedidos:
                from gspread.exceptions import WorksheetNotFound
                try:
                    audit = planilha.worksheet(ABA_AUDITORIA)
                    existentes_auditoria = audit.get_all_values()
                    cabecalho = not existentes_auditoria
                    esperado_auditoria = ["Horário", "Login", "Data", "Antes", "Depois", "Motivo / responsável"]
                    if existentes_auditoria and existentes_auditoria[0] != esperado_auditoria:
                        raise ValueError("O cabeçalho de auditoria_presenca é incompatível. Nenhuma célula foi alterada.")
                except WorksheetNotFound:
                    audit = planilha.add_worksheet(title=ABA_AUDITORIA, rows=1000, cols=6)
                    cabecalho = True
                linhas = ([["Horário", "Login", "Data", "Antes", "Depois", "Motivo / responsável"]] if cabecalho else []) + historico
                pedidos.append({"appendCells": {"sheetId": audit.id,
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": str(v)}} for v in linha]} for linha in linhas],
                    "fields": "userEnteredValue"}})
                planilha.batch_update({"requests": pedidos})
            # Aplica o resultado confirmado ao snapshot remoto, sem uma segunda leitura falhável.
            for item in alteracoes:
                remoto["celulas"][item["par"]]["texto"] = item["depois"]
            confirmados = remoto["registros"]
            pares = {item["par"] for item in alteracoes}
            manter = [not any((r["Login"], d.date()) in pares for d in pd.date_range(r["_inicio"], r["_fim"]))
                      for r in confirmados.to_dict("records")]
            novos = local.loc[local["Status"].ne(STATUS_CANCELADO)].copy()
            afetados = [any((r["Login"], d.date()) in pares for d in pd.date_range(r["_inicio"], r["_fim"]))
                        for r in novos.to_dict("records")]
            confirmados = normalizar_registros(pd.concat([confirmados.loc[manter], novos.loc[afetados]]).drop(columns=["_inicio", "_fim"], errors="ignore"))
            remoto["registros"] = confirmados
            return True, "", remoto
    except Exception as exc:
        return False, str(exc), snapshot


def consultar_auditoria_grade(dia, logins):
    from gspread.exceptions import WorksheetNotFound
    try:
        valores = _abrir().worksheet(ABA_AUDITORIA).get_all_values()
    except WorksheetNotFound:
        return pd.DataFrame()
    if len(valores) < 2:
        return pd.DataFrame()
    historico = pd.DataFrame(valores[1:], columns=valores[0])
    return historico.loc[historico["Data"].eq(dia.isoformat()) & historico["Login"].isin(logins)]
