"""Cálculos sem estado da interface para tendências executivas."""

from __future__ import annotations

import unicodedata
from datetime import timedelta
from typing import Any

import pandas as pd

COLUNAS_DATA = (
    "DATA",
    "DATA AGENDAMENTO",
    "DATA CONCLUSÃO",
    "DATA CONCLUSAO",
    "DATA EXECUÇÃO",
    "DATA EXECUCAO",
    "DATA OS",
    "DATA BAIXA",
    "DATE",
)


def _chave_coluna(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", str(valor))
    sem_acentos = "".join(c for c in texto if not unicodedata.combining(c))
    return "".join(c for c in sem_acentos.upper() if c.isalnum())


def encontrar_coluna(df: pd.DataFrame, candidatas: tuple[str, ...]) -> str | None:
    colunas = {_chave_coluna(coluna): str(coluna) for coluna in df.columns}
    for candidata in candidatas:
        encontrada = colunas.get(_chave_coluna(candidata))
        if encontrada is not None:
            return encontrada
    return None


def serie_diaria(
    df: pd.DataFrame,
    *,
    data_col: str | None = None,
    valor_col: str | None = None,
) -> pd.Series:
    """Soma a métrica por data; sem coluna de valor, conta registros."""
    if df.empty:
        return pd.Series(dtype="float64")
    coluna_data = data_col or encontrar_coluna(df, COLUNAS_DATA)
    if coluna_data is None or coluna_data not in df.columns:
        return pd.Series(dtype="float64")

    datas = pd.to_datetime(df[coluna_data], errors="coerce", dayfirst=True).dt.normalize()
    validas = datas.notna()
    if not validas.any():
        return pd.Series(dtype="float64")

    if valor_col and valor_col in df.columns:
        valores = pd.to_numeric(df[valor_col], errors="coerce").fillna(0.0)
    else:
        valores = pd.Series(1.0, index=df.index)

    serie = pd.Series(valores.loc[validas].to_numpy(), index=datas.loc[validas])
    resultado = serie.groupby(level=0).sum().sort_index()
    resultado.index.name = "Data"
    return resultado


def comparar_periodos(serie: pd.Series) -> dict[str, Any]:
    """Compara a última data disponível com D-1 e com o mesmo dia em W-1."""
    if serie.empty:
        return {"data": None, "atual": None, "d1": None, "w1": None}

    normalizada = serie.copy()
    normalizada.index = pd.to_datetime(normalizada.index, errors="coerce").normalize()
    normalizada = normalizada.loc[normalizada.index.notna()].groupby(level=0).sum()
    if normalizada.empty:
        return {"data": None, "atual": None, "d1": None, "w1": None}

    data_atual = normalizada.index.max()
    valor = normalizada.get(data_atual)
    d1 = normalizada.get(data_atual - timedelta(days=1))
    w1 = normalizada.get(data_atual - timedelta(days=7))
    return {
        "data": data_atual.date(),
        "atual": float(valor) if valor is not None else None,
        "d1": float(d1) if d1 is not None else None,
        "w1": float(w1) if w1 is not None else None,
    }


def serie_atingimento_meta(
    df: pd.DataFrame,
    *,
    meta_pontos: float = 300.0,
) -> pd.Series:
    """Percentual acumulado no mês de equipes que alcançaram a meta de pontos."""
    if df.empty:
        return pd.Series(dtype="float64")
    coluna_data = encontrar_coluna(df, COLUNAS_DATA)
    coluna_equipe = encontrar_coluna(df, ("Nome Equipe", "Equipe", "Técnico", "Tecnico"))
    coluna_pontos = encontrar_coluna(df, ("Pontos", "Pontuação", "Pontuacao"))
    if not coluna_data or not coluna_equipe or not coluna_pontos:
        return pd.Series(dtype="float64")

    trabalho = pd.DataFrame(
        {
            "data": pd.to_datetime(df[coluna_data], errors="coerce", dayfirst=True).dt.normalize(),
            "equipe": df[coluna_equipe].astype("string").str.strip(),
            "pontos": pd.to_numeric(df[coluna_pontos], errors="coerce"),
        }
    ).dropna(subset=["data", "equipe", "pontos"])
    trabalho = trabalho.loc[trabalho["equipe"].ne("")]
    if trabalho.empty:
        return pd.Series(dtype="float64")

    datas = sorted(pd.Timestamp(valor) for valor in trabalho["data"].unique())
    atingimento: dict[pd.Timestamp, float] = {}
    for dia in datas:
        inicio_mes = dia.replace(day=1)
        acumulado = (
            trabalho.loc[trabalho["data"].between(inicio_mes, dia)]
            .groupby("equipe")["pontos"]
            .sum()
        )
        if not acumulado.empty:
            atingimento[dia] = float(acumulado.ge(meta_pontos).mean() * 100.0)

    resultado = pd.Series(atingimento, dtype="float64").sort_index()
    resultado.index.name = "Data"
    return resultado


def serie_quebra_diaria(df: pd.DataFrame) -> pd.Series:
    """Calcula a taxa diária de não execução entre OS concluídas."""
    if df.empty:
        return pd.Series(dtype="float64")
    coluna_data = encontrar_coluna(df, COLUNAS_DATA)
    coluna_status = encontrar_coluna(df, ("Status Contrato", "Status", "Situação", "Situacao"))
    if not coluna_data or not coluna_status:
        return pd.Series(dtype="float64")

    datas = pd.to_datetime(df[coluna_data], errors="coerce", dayfirst=True).dt.normalize()
    status = df[coluna_status].astype("string").fillna("").map(_chave_coluna)
    executadas = status.isin({"EXECUTADA", "EXECUTADO", "CONCLUIDA", "CONCLUIDO"})
    nao_executadas = status.isin({"NAOEXECUTADA", "NAOEXECUTADO", "NAOEXEC", "QUEBRA"})
    validas = datas.notna() & (executadas | nao_executadas)
    if not validas.any():
        return pd.Series(dtype="float64")

    tarefas_col = encontrar_coluna(df, ("TOTAL DE TAREFAS", "QUANTIDADE", "QTD OS"))
    if tarefas_col:
        peso = pd.to_numeric(df[tarefas_col], errors="coerce").fillna(1.0)
    else:
        peso = pd.Series(1.0, index=df.index)

    dados = pd.DataFrame(
        {
            "data": datas.loc[validas],
            "nao_executada": (peso.loc[validas] * nao_executadas.loc[validas].astype(float)),
            "total": peso.loc[validas],
        }
    )
    diario = dados.groupby("data")[["nao_executada", "total"]].sum()
    considerado = diario["total"].where(diario["total"] > 0)
    resultado = diario["nao_executada"].div(considerado).mul(100.0).dropna()
    resultado.index.name = "Data"
    return resultado.sort_index()


def _limpar_texto_dimensao(serie: pd.Series) -> pd.Series:
    """Normaliza coluna textual, convertendo vazios e placeholders em NA."""
    texto = serie.astype("string").str.strip()
    invalido = texto.isna() | texto.str.lower().isin(
        {"", "nan", "none", "null", "<na>", "nat", "n/a", "na"}
    )
    return texto.mask(invalido, pd.NA)


def resumo_frequencia(
    df: pd.DataFrame,
    *,
    data_col: str | None = None,
    equipe_col: str | None = None,
    supervisor_col: str | None = None,
    projeto_col: str | None = None,
) -> pd.DataFrame:
    """Resume somente dias com produção observada por Equipe, Supervisor e Projeto."""
    colunas_saida = [
        "Equipe",
        "Supervisor",
        "Projeto",
        "Dias com produção",
        "Registros",
        "Última atividade",
    ]
    if df.empty:
        return pd.DataFrame(columns=colunas_saida)
    coluna_data = data_col or encontrar_coluna(df, COLUNAS_DATA)
    coluna_equipe = equipe_col or encontrar_coluna(
        df, ("Nome Equipe", "Equipe", "Técnico", "Tecnico")
    )
    if not coluna_data or not coluna_equipe:
        return pd.DataFrame(columns=colunas_saida)

    coluna_supervisor = supervisor_col or encontrar_coluna(
        df, ("Supervisor", "Monitor", "Gestor", "Lider", "Líder")
    )
    coluna_projeto = projeto_col or encontrar_coluna(
        df, ("Projeto", "Contrato", "Campanha", "Operacao", "Operação", "Segmento")
    )

    supervisor_serie = (
        _limpar_texto_dimensao(df[coluna_supervisor])
        if coluna_supervisor and coluna_supervisor in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="string")
    )
    projeto_serie = (
        _limpar_texto_dimensao(df[coluna_projeto])
        if coluna_projeto and coluna_projeto in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="string")
    )

    dados = pd.DataFrame(
        {
            "Equipe": _limpar_texto_dimensao(df[coluna_equipe]),
            "Supervisor": supervisor_serie,
            "Projeto": projeto_serie,
            "Data": pd.to_datetime(df[coluna_data], errors="coerce", dayfirst=True).dt.normalize(),
        }
    ).dropna(subset=["Equipe", "Data"])
    if dados.empty:
        return pd.DataFrame(columns=colunas_saida)

    if dados["Supervisor"].notna().any():
        mapa_sup = dados.dropna(subset=["Supervisor"]).groupby("Equipe")["Supervisor"].first()
        dados["Supervisor"] = dados["Supervisor"].fillna(dados["Equipe"].map(mapa_sup))
    dados["Supervisor"] = dados["Supervisor"].fillna("Não informado")

    if dados["Projeto"].notna().any():
        mapa_proj = dados.dropna(subset=["Projeto"]).groupby("Equipe")["Projeto"].first()
        dados["Projeto"] = dados["Projeto"].fillna(dados["Equipe"].map(mapa_proj))
    dados["Projeto"] = dados["Projeto"].fillna("Não informado")

    resumo = (
        dados.groupby(["Equipe", "Supervisor", "Projeto"], as_index=False, dropna=False)
        .agg(
            **{
                "Dias com produção": ("Data", "nunique"),
                "Registros": ("Data", "size"),
                "Última atividade": ("Data", "max"),
            }
        )
        .sort_values(
            ["Dias com produção", "Registros", "Equipe", "Supervisor", "Projeto"],
            ascending=[False, False, True, True, True],
        )
        .reset_index(drop=True)
    )
    resumo["Última atividade"] = pd.to_datetime(resumo["Última atividade"]).dt.date
    return resumo[colunas_saida]
