"""Chamada diária gravada diretamente na planilha ``lista_de_presenca``.

A planilha externa é a origem da equipe e das situações do dia. A gravação é
localizada: conferimos a célula remota antes de alterar somente as posições
escolhidas pelo usuário. Nenhuma linha, coluna ou formatação é recriada.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

from config.settings import obter_sheet_id_presenca
from services.absenteismo import MESES_ABREVIADOS, _cliente_gspread
from services.lista_presenca import (
    OPCOES_STATUS_DIA,
    normalizar_planilha_lista_presenca,
)
from services.texto import normalizar_chave

#: Identidade protectada contra edição na tabela da chamada.
COLUNAS_IDENTIDADE = ("RE", "Login", "Técnico", "Monitor")

_MESES = {normalizar_chave(mes): indice + 1 for indice, mes in enumerate(MESES_ABREVIADOS)}
_PADRAO_DIA = re.compile(r"^\s*(\d{1,2})\s*/\s*([A-Za-zÀ-ÿ]{3,})\.?\s*$")
_VAZIOS = {"", "NÃO PREENCHIDO", "NAN", "NONE", "NULL", "N/A"}


def coluna_dia(dia: date) -> str:
    """Rótulo da coluna diária no padrão da planilha (``1/nov.``)."""
    return f"{dia.day}/{MESES_ABREVIADOS[dia.month - 1]}"


def status_cellula(valor: Any) -> str:
    """Texto da situação como aparece na planilha; vazio é pendência."""
    texto = str(valor or "").strip().upper()
    return "" if texto in _VAZIOS else texto


def datas_da_planilha(df: pd.DataFrame, referencia: date | None = None) -> list[date]:
    """Converte as colunas ``dd/mês.`` da planilha em datas utilizáveis na chamada."""
    if df is None or len(df.columns) == 0:
        return []
    referencia = referencia or date.today()
    encontradas: set[date] = set()
    for coluna in df.columns:
        correspondencia = _PADRAO_DIA.match(str(coluna).strip())
        if not correspondencia:
            continue
        dia = int(correspondencia.group(1))
        mes = _MESES.get(normalizar_chave(correspondencia.group(2)))
        if not mes:
            continue
        ano = referencia.year
        # Planilhas que atravessam virada de ano mantêm as colunas em ordem.
        if mes < referencia.month - 6:
            ano += 1
        elif mes > referencia.month + 6:
            ano -= 1
        try:
            encontradas.add(date(ano, mes, dia))
        except ValueError:
            continue
    return sorted(encontradas)


def filtrar_equipe(
    df: pd.DataFrame,
    *,
    unidades: tuple[str, ...] | list[str] = (),
    monitores: tuple[str, ...] | list[str] = (),
    busca: str = "",
) -> pd.DataFrame:
    """Aplica os filtros da chamada sobre o cadastro da planilha externa."""
    if df is None or df.empty:
        return pd.DataFrame()
    filtrado = df.copy()
    if unidades and "U.N." in filtrado.columns:
        filtrado = filtrado.loc[filtrado["U.N."].isin(unidades)]
    if monitores and "Monitor" in filtrado.columns:
        filtrado = filtrado.loc[filtrado["Monitor"].isin(monitores)]
    if busca.strip():
        termo = busca.strip().casefold()
        nome = filtrado.get("Técnico", pd.Series("", index=filtrado.index)).fillna("").astype(str)
        login = filtrado.get("Login", pd.Series("", index=filtrado.index)).fillna("").astype(str)
        filtrado = filtrado.loc[(nome + " " + login).str.casefold().str.contains(termo, regex=False)]
    return filtrado.reset_index(drop=True)


def montar_tabela(df: pd.DataFrame, dias: list[date]) -> pd.DataFrame:
    """Monta a tabela editável: ``Status`` para um dia ou uma coluna por dia."""
    tabela = pd.DataFrame(index=df.index if df is not None else [])
    for coluna in COLUNAS_IDENTIDADE:
        tabela[coluna] = (
            df[coluna].fillna("").astype(str).str.strip()
            if df is not None and coluna in df.columns
            else ""
        )
    for dia in dias:
        rotulo = coluna_dia(dia)
        valores = (
            df[rotulo].map(status_cellula)
            if df is not None and rotulo in df.columns
            else ""
        )
        tabela["Status" if len(dias) == 1 else dia.isoformat()] = valores
    return tabela[list(tabela.columns)]


def opcoes_status(tabela: pd.DataFrame, coluna: str) -> list[str]:
    """Opções oficiais mais valores históricos já presentes na coluna."""
    opcoes = list(OPCOES_STATUS_DIA)
    if coluna not in tabela.columns:
        return opcoes
    existentes = {
        str(valor).strip()
        for valor in tabela[coluna]
        if str(valor).strip()
    }
    return [*opcoes, *sorted(existentes - set(opcoes))]


def _serie_logins(df: pd.DataFrame) -> pd.Series:
    if "Login" not in df.columns:
        raise ValueError("A planilha de presença não tem a coluna Login.")
    logins = df["Login"].fillna("").astype(str).str.strip()
    repetidos = logins[logins.duplicated() & logins.ne("")]
    if not repetidos.empty:
        raise ValueError("Há logins repetidos na planilha de presença. Corrija a origem antes de preencher.")
    return logins


def _login_por_indice(df: pd.DataFrame) -> dict[Any, str]:
    return _serie_logins(df).to_dict()


def _indice_por_login(df: pd.DataFrame) -> dict[str, Any]:
    return {login: indice for indice, login in _serie_logins(df).items() if login}


def planejar_alteracoes(
    original: pd.DataFrame,
    editada: pd.DataFrame,
    dias: list[date],
    remoto: pd.DataFrame | None = None,
) -> list[dict]:
    """Valida a edição e devolve só as células que precisam ser gravadas."""
    colunas_status = ["Status"] if len(dias) == 1 else [dia.isoformat() for dia in dias]
    esperadas = [*COLUNAS_IDENTIDADE, *colunas_status]
    if not isinstance(editada, pd.DataFrame) or list(editada.columns) != esperadas:
        raise ValueError("A estrutura da tabela foi alterada. Reabra o preenchimento.")
    if not original.index.equals(editada.index):
        raise ValueError("A equipe da chamada mudou. Reabra o preenchimento.")

    for coluna in COLUNAS_IDENTIDADE:
        antes = original[coluna].fillna("").astype(str).str.strip()
        depois = editada[coluna].fillna("").astype(str).str.strip()
        if not antes.equals(depois):
            raise ValueError("Os dados cadastrais não podem ser alterados nesta tabela.")

    login_por_indice = _login_por_indice(original)
    indice_por_login = _indice_por_login(remoto) if remoto is not None else None
    opcoes = {normalizar_chave(valor) for valor in OPCOES_STATUS_DIA if valor}
    alteracoes: list[dict] = []
    for dia, coluna_status in zip(dias, colunas_status):
        rotulo = coluna_dia(dia)
        if rotulo not in original.columns:
            raise ValueError(f"A coluna {rotulo} não existe na planilha de presença.")
        atuais = original[rotulo].map(status_cellula)
        novos = editada[coluna_status].map(status_cellula)
        if remoto is not None and rotulo not in remoto.columns:
            raise ValueError(f"A coluna {rotulo} não existe mais na planilha remota.")
        for indice, valor in novos.items():
            antes = atuais.at[indice]
            if valor == antes:
                continue
            if valor and normalizar_chave(valor) not in opcoes and valor != antes:
                raise ValueError("Selecione uma das situações disponíveis para o dia.")
            login = login_por_indice.get(indice, "")
            if not login:
                raise ValueError("Sem login não é possível gravar a situação na planilha.")
            if indice_por_login is not None:
                if login not in indice_por_login:
                    raise ValueError(f"O login {login} não existe mais na planilha remota.")
                valor_remoto = status_cellula(remoto.at[indice_por_login[login], rotulo])
                if valor_remoto != antes:
                    raise ValueError(
                        f"Conflito: {login} em {rotulo} foi alterado na planilha. Atualize a chamada antes de continuar."
                    )
            alteracoes.append({
                "login": login,
                "dia": dia,
                "coluna": rotulo,
                "antes": antes,
                "depois": valor,
            })
    return alteracoes


def salvar(
    original: pd.DataFrame,
    editada: pd.DataFrame,
    dias: list[date],
    *,
    sheet_id: str | None = None,
    cliente: Any | None = None,
) -> tuple[bool, str, pd.DataFrame, int]:
    """Salva as células alteradas na planilha ``lista_de_presenca``."""
    sid = str(sheet_id or obter_sheet_id_presenca() or "").strip()
    if not sid:
        raise ValueError("ID da planilha lista_de_presenca não configurado.")
    cliente = cliente or _cliente_gspread()
    if hasattr(cliente, "set_timeout"):
        cliente.set_timeout((5, 20))
    planilha = cliente.open_by_key(sid)
    aba = planilha.sheet1
    valores = aba.get_all_values()
    if not valores:
        raise ValueError("A planilha de presença está vazia.")
    cabecalho = [str(coluna).strip() for coluna in valores[0]]
    remoto = normalizar_planilha_lista_presenca(
        pd.DataFrame(valores[1:], columns=cabecalho)
    )
    alteracoes = planejar_alteracoes(original, editada, dias, remoto)
    if not alteracoes:
        return True, "", remoto, 0
    if "Login" not in cabecalho:
        raise ValueError("A planilha remota não tem a coluna Login.")
    coluna_login = cabecalho.index("Login")
    linhas_por_login: dict[str, int] = {}
    for indice, linha in enumerate(valores[1:], start=1):
        login = str(linha[coluna_login]).strip() if coluna_login < len(linha) else ""
        if not login:
            continue
        if login in linhas_por_login:
            raise ValueError("Há logins repetidos na planilha remota. Corrija a origem antes de preencher.")
        linhas_por_login[login] = indice

    pedidos = []
    mapa_remoto = _indice_por_login(remoto)
    for item in alteracoes:
        if item["coluna"] not in cabecalho:
            raise ValueError(f"A coluna {item['coluna']} não existe mais na planilha remota.")
        linha = linhas_por_login.get(item["login"])
        if linha is None:
            raise ValueError(f"O login {item['login']} não existe mais na planilha remota.")
        pedidos.append({
            "updateCells": {
                "range": {
                    "sheetId": aba.id,
                    "startRowIndex": linha,
                    "endRowIndex": linha + 1,
                    "startColumnIndex": cabecalho.index(item["coluna"]),
                    "endColumnIndex": cabecalho.index(item["coluna"]) + 1,
                },
                "rows": [{"values": [{"userEnteredValue": {"stringValue": item["depois"]}}]}],
                "fields": "userEnteredValue",
            }
        })
    planilha.batch_update({"requests": pedidos})
    for item in alteracoes:
        indice = mapa_remoto[item["login"]]
        remoto.at[indice, item["coluna"]] = item["depois"] or "Não preenchido"
    return True, "", remoto, len(alteracoes)
