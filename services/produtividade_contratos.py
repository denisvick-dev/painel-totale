"""Indicadores agregados de produção e contratos atendidos na carga Prod."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from services.produtividade import ALIASES_PRODUCAO, NAO_INFORMADO, normalizar_producao
from services.texto import buscar_coluna, normalizar_chave, normalizar_texto

# Somente nomes explícitos de identificador: não confundir tipo de contrato,
# projeto, pedido ou O.S. com o número de contrato do cliente.
ALIASES_CONTRATO = {
    "CONTRATO", "NCONTRATO", "NUMEROCONTRATO", "NUMERODOCONTRATO",
    "IDCONTRATO", "CODIGOCONTRATO", "CODCONTRATO", "CONTRATOCLIENTE", "NUMCONTRATO", "NROCONTRATO",
}
INVALIDOS = {"", "NAN", "NONE", "NULL", "N/A", "NA", "-", "0", "0.0", "<NA>", "#N/A", "NAO INFORMADO", "SEM CONTRATO"}


def _contrato(valor: Any) -> str | None:
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if not math.isfinite(valor):
            return None
        texto = str(int(valor)) if float(valor).is_integer() else str(valor)
    else:
        texto = normalizar_texto(valor)
    return None if texto in INVALIDOS else texto


def preparar_producao(origem: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """Normaliza produção e preserva somente uma coluna explícita de contrato."""
    dados = normalizar_producao(origem)
    coluna = next((c for c in origem.columns if normalizar_chave(c) in ALIASES_CONTRATO), None)
    dados["Data"] = dados["Data"].dt.normalize()
    if buscar_coluna(origem, ALIASES_PRODUCAO["Pontos"]) is None:
        dados["Pontos"] = float("nan")
    dados["Contrato"] = origem[coluna].map(_contrato).reset_index(drop=True) if coluna is not None else None
    return dados, coluna


def resumir(dados: pd.DataFrame) -> dict[str, Any]:
    """Uma linha da carga equivale a uma O.S.; equipe-dia é produção observada."""
    validos = dados["Contrato"].dropna()
    equipe = dados.loc[dados["Equipe"].ne(NAO_INFORMADO) & dados["Data"].notna()]
    pares = equipe.drop_duplicates(["Base", "Supervisor", "Equipe", "Data"])
    return {
        "os": len(dados),
        "contratos": int(validos.nunique()) if not validos.empty else None,
        "os_com_contrato": int(validos.size),
        "pontos": dados["Pontos"].sum(min_count=1),
        "equipes_dia": len(pares),
        "os_equipe_dia": len(equipe) / len(pares) if len(pares) else None,
        "os_com_equipe_data": len(equipe),
    }


def agrupar(dados: pd.DataFrame, dimensoes: list[str]) -> pd.DataFrame:
    """Contratos distintos são calculados dentro de cada grupo, não somáveis."""
    colunas = [*dimensoes, "O.S.", "Contratos", "O.S. com contrato", "Pontos"]
    if dados.empty:
        return pd.DataFrame(columns=colunas)
    resultado = dados.groupby(dimensoes, dropna=False).agg(
        **{"O.S.": ("O.S.", "size"), "Contratos": ("Contrato", "nunique"),
           "O.S. com contrato": ("Contrato", "count"), "Pontos": ("Pontos", lambda valores: valores.sum(min_count=1))}
    ).reset_index()
    resultado.loc[resultado["O.S. com contrato"].eq(0), "Contratos"] = pd.NA
    return resultado.sort_values("O.S.", ascending=False).reset_index(drop=True)[colunas]


def encontrar_coluna(origem: pd.DataFrame, aliases: set[str]) -> str | None:
    """Aceita somente nomes exatos normalizados; evita pegar campos parecidos."""
    return next((c for c in origem.columns if normalizar_chave(c) in aliases), None)


ALIASES_OS = {"OS", "NUMEROOS", "NUMERODAOS", "NOS", "IDORDEMSERVICO",
              "NUMERODAOS1", "NUMEROOS1", "IDOS"}


def diagnostico_os(origem: pd.DataFrame) -> tuple[str | None, int | None, int]:
    """Repetições de identificadores, sem supor que toda repetição é erro."""
    coluna = encontrar_coluna(origem, ALIASES_OS)
    if coluna is None:
        return None, None, 0
    ids = origem[coluna].map(_contrato).dropna()
    return coluna, int(ids.duplicated().sum()), len(ids)


def resumo_equipes(dados: pd.DataFrame) -> pd.DataFrame:
    """Totais e produtividade observada; linhas sem data/equipe não entram na taxa."""
    dimensoes = ["Base", "Supervisor", "Equipe"]
    colunas = [*dimensoes, "O.S.", "Contratos", "Equipe-dias", "O.S. com data", "O.S./equipe-dia"]
    if dados.empty:
        return pd.DataFrame(columns=colunas)
    total = agrupar(dados, dimensoes)
    observados = dados.loc[dados["Equipe"].ne(NAO_INFORMADO) & dados["Data"].notna()]
    por_dia = observados.groupby(dimensoes).agg(
        **{"Equipe-dias": ("Data", "nunique"), "O.S. com data": ("O.S.", "size")}
    ).reset_index()
    tabela = total.merge(por_dia, on=dimensoes, how="left")
    tabela["O.S./equipe-dia"] = tabela["O.S. com data"] / tabela["Equipe-dias"]
    return tabela[colunas]


def distribuicao_contratos(dados: pd.DataFrame) -> pd.DataFrame:
    """Quantidade de contratos distintos por número de linhas atendidas."""
    valores = dados["Contrato"].dropna().value_counts()
    return (valores.value_counts().sort_index().rename_axis("O.S. por contrato")
            .reset_index(name="Contratos"))


def preparar_retornos(origem: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normaliza arquivo TOA; exige contrato, data, atividade e status explícitos."""
    aliases = {
        "Contrato": ALIASES_CONTRATO | {"NUMCONTRATO", "NROCONTRATO"},
        "Data": {"DATA", "DATAATIVIDADE", "DATAEXECUCAO", "DATACONCLUSAO", "DATAAGENDAMENTO"},
        "Tipo": {"TIPODEATIVIDADE1", "TIPODEATIVIDADE", "TIPOATIVIDADE"},
        "Status": {"STATUSDAATIVIDADE", "STATUS", "SITUACAO"},
        "Motivo": {"MOTIVO", "MOTIVORETORNO", "MOTIVODORETORNO"},
    }
    colunas = {nome: encontrar_coluna(origem, opcoes) for nome, opcoes in aliases.items()}
    # A fonte TOA usa a coluna .1 para a classificação de retorno quando ambas existem.
    colunas["Tipo"] = (encontrar_coluna(origem, {"TIPODEATIVIDADE1"}) or colunas["Tipo"])
    faltantes = [nome for nome in ("Contrato", "Data", "Tipo", "Status") if colunas[nome] is None]
    if faltantes:
        raise ValueError("Colunas obrigatórias não reconhecidas: " + ", ".join(faltantes))
    from services.datas import converter_serie_datas

    tipo = origem[colunas["Tipo"]].map(normalizar_texto)
    status = origem[colunas["Status"]].map(normalizar_texto)
    selecionados = tipo.str.contains("RETORNO", regex=False) & tipo.str.contains("CREDENCIAD", regex=False)
    selecionados &= ~status.str.contains("SUSPEN", regex=False)
    bruto = origem.loc[selecionados]
    resultado = pd.DataFrame({
        "Contrato": bruto[colunas["Contrato"]].map(_contrato),
        "Data": converter_serie_datas(bruto[colunas["Data"]]).dt.normalize(),
        "Motivo": bruto[colunas["Motivo"]].map(normalizar_texto) if colunas["Motivo"] else "",
    })
    invalidos = int((resultado["Contrato"].isna() | resultado["Data"].isna()).sum())
    resultado = resultado.dropna(subset=["Contrato", "Data"]).copy()
    return resultado.reset_index(drop=True), {
        "origem": len(origem), "selecionados": len(bruto), "invalidos": invalidos,
        "sem_status": int((selecionados & status.eq("")).sum()),
        "tem_motivo": bool(colunas["Motivo"]),
    }


def analisar_retornos(
    producao: pd.DataFrame, retornos: pd.DataFrame, inicio_cobertura: Any, fim_cobertura: Any, janela: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coorte de contratos: último atendimento do recorte e primeiro retorno posterior.

    Só entram no denominador contratos com janela inteira dentro da cobertura
    declarada. O vínculo por contrato não prova causalidade.
    """
    if janela not in (7, 30):
        raise ValueError("Janela inválida")
    inicio, fim = pd.Timestamp(inicio_cobertura), pd.Timestamp(fim_cobertura)
    base = producao.dropna(subset=["Contrato", "Data"]).sort_values("Data", kind="stable")
    ultima_data = base.groupby("Contrato")["Data"].transform("max")
    ultimos = base.loc[base["Data"].eq(ultima_data)]
    atribuicoes = ultimos.drop_duplicates(["Contrato", "Base", "Supervisor"])
    ambiguos = atribuicoes.groupby("Contrato").size()
    ambiguos = set(ambiguos[ambiguos > 1].index)
    base = base.loc[~base["Contrato"].isin(ambiguos)].drop_duplicates("Contrato", keep="last").copy()
    base = base.loc[(base["Data"] >= inicio) & (base["Data"] + pd.Timedelta(days=janela) <= fim)].copy()
    base = base.rename(columns={"Data": "Atendimento"})
    eventos = retornos.loc[retornos["Data"].between(inicio, fim)].merge(
        base[["Contrato", "Atendimento"]], on="Contrato", how="inner"
    )
    dias = (eventos["Data"] - eventos["Atendimento"]).dt.days
    eventos = eventos.loc[dias.between(1, janela)].sort_values("Data", kind="stable")
    primeiros = eventos.drop_duplicates("Contrato", keep="first")
    base["Com retorno"] = base["Contrato"].isin(primeiros["Contrato"])
    return base, primeiros
