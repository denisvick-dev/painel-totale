"""Lista de presença explícita: vazio nunca confirma presença."""

import io
import re
from collections.abc import Sequence
from datetime import date
from typing import Any

import pandas as pd

from services.absenteismo import (
    ABREVIACOES_AUSENCIA,
    STATUS_CANCELADO,
    montar_matriz_ausencias,
)
from services.absenteismo_grade import registros_do_preenchimento
from services.texto import normalizar_chave, normalizar_login

OPCOES_PRESENCA = (
    "Não preenchido",
    "Presente",
    "Falta",
    "Folga",
    "Férias",
    "Atestado",
    "Afastamento",
    "Licença",
    "Treinamento",
)

# Rótulos mostrados na chamada diária (compatíveis com a planilha operacional).
OPCOES_STATUS_DIA = (
    "",
    "ATIVO",
    "ATESTADO",
    "FALTA",
    "FOLGA",
    "LICENÇA",
    "TREINAMENTO",
    "SUSPENSÃO",
    "BAIXA DE KIT",
    "FÉRIAS",
    "AFASTADO",
)
_STATUS_DIA_PARA_TIPO = {
    normalizar_chave("ATIVO"): "Presente",
    normalizar_chave("ATESTADO"): "Atestado",
    normalizar_chave("FALTA"): "Falta",
    normalizar_chave("FOLGA"): "Folga",
    normalizar_chave("LICENÇA"): "Licença",
    normalizar_chave("TREINAMENTO"): "Treinamento",
    normalizar_chave("SUSPENSÃO"): "Suspensão",
    normalizar_chave("BAIXA DE KIT"): "Baixa De Kit",
    normalizar_chave("FÉRIAS"): "Férias",
    normalizar_chave("AFASTADO"): "Afastamento",
}
_TIPO_PARA_STATUS_DIA = {
    normalizar_chave(_STATUS_DIA_PARA_TIPO[normalizar_chave(status)]): status
    for status in OPCOES_STATUS_DIA
    if status
}


def status_tela_para_tipo(valor: Any) -> str:
    """Converte o rótulo da chamada para o tipo persistido na grade mensal."""
    chave = normalizar_chave(valor)
    if not chave or chave == normalizar_chave("Não preenchido"):
        return "Não preenchido"
    return _STATUS_DIA_PARA_TIPO.get(chave, str(valor).strip())


def tipo_para_status_tela(valor: Any) -> str:
    """Apresenta os tipos já registrados no padrão de status da planilha."""
    chave = normalizar_chave(valor)
    if not chave or chave == normalizar_chave("Não preenchido"):
        return ""
    return _TIPO_PARA_STATUS_DIA.get(chave, str(valor).strip().upper())


CODIGOS = {codigo: tipo for tipo, codigo in ABREVIACOES_AUSENCIA.items()}
CODIGOS["P"] = "Presente"
CODIGOS["BAIXA DE KIT"] = "Baixa De Kit"

COLUNAS_CHAMADA_DIARIA = (
    "Cód.Equipe",
    "Cód.Aux.Equipe",
    "Matrícula",
    "Nome Equipe",
    "Supervisor",
    "Status Dia",
)


def montar_tabela_chamada_diaria(matriz: pd.DataFrame, dia: date) -> pd.DataFrame:
    """Monta a tabela diária no leiaute operacional, sem expor o login interno."""
    if not isinstance(matriz, pd.DataFrame) or dia not in matriz.columns:
        raise ValueError("A data escolhida não existe na lista de presença.")

    def coluna_texto(origem: str) -> pd.Series:
        if origem in matriz.columns:
            return matriz[origem].fillna("").astype(str).str.strip()
        return pd.Series("", index=matriz.index, dtype="object")

    tabela = pd.DataFrame(index=matriz.index)
    tabela["Cód.Equipe"] = coluna_texto("Cód.Equipe")
    tabela["Cód.Aux.Equipe"] = coluna_texto("Cód.Aux.Equipe")
    tabela["Matrícula"] = coluna_texto("RE") if "RE" in matriz.columns else coluna_texto("Login")
    tabela["Nome Equipe"] = coluna_texto("Técnico")
    tabela["Supervisor"] = coluna_texto("Monitor")
    tabela["Status Dia"] = matriz[dia].map(tipo_para_status_tela)
    return tabela[list(COLUNAS_CHAMADA_DIARIA)]


def registros_da_chamada_diaria(
    original: pd.DataFrame, editada: pd.DataFrame, dia: date
) -> list[dict]:
    """Valida a tabela diária e converte suas seleções ao fluxo da grade mensal."""
    esperada = montar_tabela_chamada_diaria(original, dia)
    if not editada.index.equals(esperada.index) or list(editada.columns) != list(esperada.columns):
        raise ValueError("A estrutura da tabela foi alterada. Reabra o preenchimento.")

    colunas_protegidas = [coluna for coluna in COLUNAS_CHAMADA_DIARIA if coluna != "Status Dia"]
    for coluna in colunas_protegidas:
        antes = esperada[coluna].fillna("").astype(str).str.strip()
        depois = editada[coluna].fillna("").astype(str).str.strip()
        if not antes.equals(depois):
            raise ValueError("Os dados cadastrais não podem ser alterados nesta tabela.")

    opcoes_oficiais = {normalizar_chave(valor) for valor in OPCOES_STATUS_DIA if valor}
    statuses = editada["Status Dia"].fillna("").astype(str).str.strip()
    atuais = esperada["Status Dia"].fillna("").astype(str).str.strip()
    for indice, valor in statuses.items():
        if valor and normalizar_chave(valor) not in opcoes_oficiais and valor != atuais.at[indice]:
            raise ValueError("Selecione uma das situações disponíveis para o dia.")

    matriz_editada = original.copy()
    matriz_editada[dia] = statuses.map(status_tela_para_tipo)
    return registros_da_presenca(original, matriz_editada)


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
        no_dia = operacionais.loc[
            (operacionais["_inicio"].dt.date <= dia) & (operacionais["_fim"].dt.date >= dia)
        ]
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
    "RE",
    "Login",
    "Técnico",
    "Monitor",
    "U.N.",
    "Base",
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
        copia = copia.loc[
            copia["Login"].ne("") | copia.get("Técnico", pd.Series("", index=copia.index)).ne("")
        ]
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


_MESES_COLUNA_DIA = {
    "JAN": "Janeiro",
    "JANEIRO": "Janeiro",
    "FEV": "Fevereiro",
    "FEVEREIRO": "Fevereiro",
    "MAR": "Março",
    "MARCO": "Março",
    "ABR": "Abril",
    "ABRIL": "Abril",
    "MAI": "Maio",
    "MAIO": "Maio",
    "JUN": "Junho",
    "JUNHO": "Junho",
    "JUL": "Julho",
    "JULHO": "Julho",
    "AGO": "Agosto",
    "AGOSTO": "Agosto",
    "SET": "Setembro",
    "SETEMBRO": "Setembro",
    "OUT": "Outubro",
    "OUTUBRO": "Outubro",
    "NOV": "Novembro",
    "NOVEMBRO": "Novembro",
    "DEZ": "Dezembro",
    "DEZEMBRO": "Dezembro",
}

_COLUNAS_METRICAS_PRESENCA = (
    "ATIVO",
    "FALTA",
    "ATESTADO",
    "Não preenchido",
    "Outros",
    "Dias preenchidos",
    "Total de marcações",
    "FALTA + ATESTADO",
    "% Presença",
    "% Preenchimento",
)
_COLUNAS_SOMA_PRESENCA = (
    "ATIVO",
    "FALTA",
    "ATESTADO",
    "Não preenchido",
    "Outros",
    "Dias preenchidos",
    "Total de marcações",
)


def agrupar_colunas_dias_por_mes(colunas_dias: Sequence[str]) -> dict[str, list[str]]:
    """Agrupa cabeçalhos ``1/nov.`` pelo mês para análises mensais."""
    grupos: dict[str, list[str]] = {}
    for coluna in colunas_dias:
        correspondencia = re.match(r"^\s*\d{1,2}\s*/\s*([A-Za-zÀ-ÿ]{3,})\.?\s*$", str(coluna))
        mes = normalizar_chave(correspondencia.group(1)) if correspondencia else ""
        rotulo = _MESES_COLUNA_DIA.get(mes, "Mês não identificado")
        grupos.setdefault(rotulo, []).append(str(coluna))
    return grupos


def _normalizar_status_analise(valor: Any) -> str:
    """Converte valores equivalentes do Sheets para os quatro status da análise."""
    chave = normalizar_chave(valor)
    if chave in {
        "",
        "NA",
        "NAN",
        "NAT",
        "NONE",
        "NULL",
        "VAZIO",
        "NAOPREENCHIDO",
        "NENHUM",
        "NENHUMA",
    }:
        return "Não preenchido"
    return {
        "ATIVO": "ATIVO",
        "FALTA": "FALTA",
        "ATESTADO": "ATESTADO",
    }.get(chave, "Outros")


def _matriz_status_presenca(df: pd.DataFrame, colunas_dias: Sequence[str]) -> pd.DataFrame:
    """Cópia normalizada das células diárias; nunca converte vazio em presença."""
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    colunas = [coluna for coluna in colunas_dias if coluna in df.columns]
    if not colunas:
        return pd.DataFrame(index=df.index)
    return pd.DataFrame(
        {coluna: df[coluna].map(_normalizar_status_analise) for coluna in colunas},
        index=df.index,
    )


def _metricas_por_linha(df: pd.DataFrame, colunas_dias: Sequence[str]) -> pd.DataFrame:
    """Contagens de status por técnico, preservando o índice da planilha."""
    status = _matriz_status_presenca(df, colunas_dias)
    total = len(status.columns)
    saida = pd.DataFrame(index=status.index)
    for rotulo in ("ATIVO", "FALTA", "ATESTADO", "Não preenchido"):
        saida[rotulo] = status.eq(rotulo).sum(axis=1).astype(int)
    saida["Outros"] = (
        (total - saida[["ATIVO", "FALTA", "ATESTADO", "Não preenchido"]].sum(axis=1))
        .clip(lower=0)
        .astype(int)
    )
    saida["Dias preenchidos"] = total - saida["Não preenchido"]
    saida["Total de marcações"] = total
    saida["FALTA + ATESTADO"] = saida["FALTA"] + saida["ATESTADO"]
    preenchidos = saida["Dias preenchidos"].replace(0, float("nan"))
    saida["% Presença"] = saida["ATIVO"] / preenchidos * 100.0
    saida["% Preenchimento"] = saida["Dias preenchidos"] / total * 100.0 if total else 0.0
    return saida


def _identificador_tecnico(df: pd.DataFrame) -> pd.Series:
    """Login canônico, com nome como fallback para cadastros sem login."""
    identificadores = []
    for indice, linha in df.iterrows():
        login = normalizar_login(linha.get("Login", ""))
        nome = normalizar_chave(linha.get("Técnico", ""))
        identificadores.append(login or nome or f"LINHA{indice}")
    return pd.Series(identificadores, index=df.index, dtype="object")


def resumir_marcacoes_presenca(
    df: pd.DataFrame,
    colunas_dias: Sequence[str] | None = None,
) -> dict[str, int | float]:
    """Resumo executivo das marcações no recorte, incluindo pendências."""
    dados = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    dias = list(
        identificar_colunas_dias_planilha(dados)
        if colunas_dias is None
        else colunas_dias
    )
    por_linha = _metricas_por_linha(dados, dias)
    somas = por_linha[list(_COLUNAS_SOMA_PRESENCA)].sum()
    total = int(somas["Total de marcações"])
    preenchidos = int(somas["Dias preenchidos"])
    ativos = int(somas["ATIVO"])
    nao_preenchidos = int(somas["Não preenchido"])
    identificadores = _identificador_tecnico(dados) if not dados.empty else pd.Series(dtype=object)
    return {
        "tecnicos": int(identificadores.nunique()) if len(identificadores) else 0,
        "dias_total": len(dias),
        "total_marcacoes": total,
        "dias_preenchidos": preenchidos,
        "ativo": ativos,
        "falta": int(somas["FALTA"]),
        "atestado": int(somas["ATESTADO"]),
        "nao_preenchido": nao_preenchidos,
        "outros": int(somas["Outros"]),
        "faltas_atestados": int(somas["FALTA"] + somas["ATESTADO"]),
        "percentual_presenca": (ativos / preenchidos * 100.0) if preenchidos else float("nan"),
        "percentual_preenchimento": (preenchidos / total * 100.0) if total else 0.0,
    }


def _rotulo_categoria_presenca(valor: Any) -> str:
    if pd.isna(valor):
        return "Não informado"
    texto = str(valor).strip()
    if normalizar_chave(texto) in {"", "NA", "NAN", "NONE", "NULL", "NENHUM", "NENHUMA"}:
        return "Não informado"
    return texto


def agrupar_marcacoes_presenca(
    df: pd.DataFrame,
    colunas_dias: Sequence[str],
    por: str | Sequence[str],
) -> pd.DataFrame:
    """Agrega status por dimensão(ões), com percentual e total de faltas/atestados."""
    dados = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    dimensoes_pedidas = [por] if isinstance(por, str) else list(por)
    dimensoes = [coluna for coluna in dimensoes_pedidas if coluna in dados.columns]
    colunas_saida = [*dimensoes, "Técnicos", *_COLUNAS_METRICAS_PRESENCA]
    if dados.empty:
        return pd.DataFrame(columns=colunas_saida)

    metricas = _metricas_por_linha(dados, colunas_dias)
    trabalho = pd.DataFrame(index=dados.index)
    for coluna in dimensoes:
        trabalho[coluna] = dados[coluna].map(_rotulo_categoria_presenca)
    for coluna in _COLUNAS_SOMA_PRESENCA:
        trabalho[coluna] = metricas[coluna]
    trabalho["_id_tecnico"] = _identificador_tecnico(dados)

    if not dimensoes:
        linha = {coluna: int(trabalho[coluna].sum()) for coluna in _COLUNAS_SOMA_PRESENCA}
        linha["Técnicos"] = int(trabalho["_id_tecnico"].nunique())
        linha["FALTA + ATESTADO"] = linha["FALTA"] + linha["ATESTADO"]
        linha["% Presença"] = (
            linha["ATIVO"] / linha["Dias preenchidos"] * 100.0
            if linha["Dias preenchidos"]
            else float("nan")
        )
        linha["% Preenchimento"] = (
            linha["Dias preenchidos"] / linha["Total de marcações"] * 100.0
            if linha["Total de marcações"]
            else 0.0
        )
        return pd.DataFrame([linha], columns=colunas_saida)

    agrupado = trabalho.groupby(dimensoes, sort=False, dropna=False)
    totais = agrupado[list(_COLUNAS_SOMA_PRESENCA)].sum().reset_index()
    quantidade = agrupado["_id_tecnico"].nunique().reset_index(name="Técnicos")
    resultado = totais.merge(quantidade, on=dimensoes, how="left")
    resultado["FALTA + ATESTADO"] = resultado["FALTA"] + resultado["ATESTADO"]
    resultado["% Presença"] = (
        resultado["ATIVO"] / resultado["Dias preenchidos"].replace(0, float("nan")) * 100.0
    )
    resultado["% Preenchimento"] = (
        resultado["Dias preenchidos"] / resultado["Total de marcações"].replace(0, pd.NA) * 100.0
    ).fillna(0.0)
    return resultado[colunas_saida].reset_index(drop=True)


def gerar_excel_executivo_presenca(
    recorte: pd.DataFrame,
    resumo_por_monitor_base: pd.DataFrame,
) -> bytes:
    """Gera o Excel executivo: detalhe filtrado + resumo por Monitor/Base."""
    from openpyxl.styles import Alignment, Font, PatternFill

    dados = recorte if isinstance(recorte, pd.DataFrame) else pd.DataFrame()
    resumo = (
        resumo_por_monitor_base
        if isinstance(resumo_por_monitor_base, pd.DataFrame)
        else pd.DataFrame()
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        dados.to_excel(writer, index=False, sheet_name="Recorte filtrado")
        resumo.to_excel(writer, index=False, sheet_name="Resumo Monitor Base")
        for planilha in writer.book.worksheets:
            planilha.freeze_panes = "A2"
            planilha.sheet_view.showGridLines = False
            if planilha.max_row and planilha.max_column:
                planilha.auto_filter.ref = planilha.dimensions
            for celula in planilha[1]:
                celula.fill = PatternFill("solid", fgColor="012869")
                celula.font = Font(color="FFFFFF", bold=True)
                celula.alignment = Alignment(vertical="center", wrap_text=True)
            planilha.row_dimensions[1].height = 28
            for indice, coluna in enumerate(planilha.iter_cols(), start=1):
                cabecalho = str(planilha.cell(1, indice).value or "")
                tamanho = max(
                    (len(str(celula.value)) for celula in coluna if celula.value is not None),
                    default=len(cabecalho),
                )
                planilha.column_dimensions[planilha.cell(1, indice).column_letter].width = min(
                    max(tamanho + 2, 12), 40
                )
                if cabecalho == "% Presença":
                    for linha in range(2, planilha.max_row + 1):
                        planilha.cell(linha, indice).number_format = '0.0"%"'
    return buffer.getvalue()
