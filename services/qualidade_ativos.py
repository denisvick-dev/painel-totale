"""Diagnóstico cadastral antes de descartar ou deduplicar linhas da origem."""
from __future__ import annotations

import pandas as pd

from services.texto import buscar_coluna, normalizar_login


def diagnosticar_ativos(bruto: pd.DataFrame) -> dict:
    from services.hierarquia import (
        ALIASES,
        ALIASES_LISTA_EXTRAS,
        ALIASES_SITUACAO,
        SITUACOES_QUADRO,
        SITUACOES_SAIDA,
        normalizar_situacao,
    )

    df = bruto.copy()
    df.columns = df.columns.astype(str).str.strip()
    ocorrencias = []

    def registrar(mascara, problema, orientacao):
        for posicao, marcado in enumerate(mascara):
            if marcado:
                ocorrencias.append({"Linha na origem": posicao + 2,
                                    "Verificação": problema, "Orientação": orientacao})

    login_col = buscar_coluna(df, ALIASES["LOGIN"])
    login = df[login_col].map(normalizar_login) if login_col else pd.Series("", index=df.index)
    sem_login = login.eq("")
    duplicados = login.ne("") & login.duplicated(keep=False)
    registrar(sem_login, "Login ausente", "Informe o login correto; a linha não entra na lista normalizada.")
    registrar(duplicados, "Login duplicado", "Confira os cadastros; o painel mantém a última ocorrência.")
    re_col = buscar_coluna(df, ALIASES_LISTA_EXTRAS["RE"])
    re = df[re_col].fillna("").astype(str).str.strip() if re_col else pd.Series("", index=df.index)
    re = re.str.replace(r"\.0$", "", regex=True)
    re_duplicados = re.ne("") & re.duplicated(keep=False)
    registrar(re_duplicados, "RE repetido", "Valide a matrícula na origem; não mescle pessoas só pelo RE.")
    for campo, aliases in (("Técnico", ALIASES["TÉCNICO"]), ("Monitor", ALIASES["MONITOR"]),
                           ("Base", ALIASES["BASE"]), ("U.N.", ALIASES_LISTA_EXTRAS["U.N."])):
        coluna = buscar_coluna(df, aliases)
        vazio = df[coluna].fillna("").astype(str).str.strip().eq("") if coluna else pd.Series(True, index=df.index)
        registrar(vazio, f"{campo} ausente", "Complete o cadastro para filtros e relatórios confiáveis.")
    situacao_col = buscar_coluna(df, ALIASES_SITUACAO)
    situacoes = df[situacao_col].map(normalizar_situacao) if situacao_col else pd.Series("NÃO INFORMADO", index=df.index)
    registrar(~situacoes.isin([*SITUACOES_QUADRO, *SITUACOES_SAIDA]), "Situação não reconhecida",
              "Confira a situação; valores não mapeados não entram no quadro da chamada.")
    data_col = buscar_coluna(df, ("Ultima_Modificacao", "Última Modificação", "ULTIMA MODIFICACAO"))
    ultima = None
    if data_col:
        from services.datas import converter_serie_datas
        datas = converter_serie_datas(df[data_col])
        registrar(datas.isna(), "Data de modificação inválida", "Use uma data válida; não preencher automaticamente com hoje.")
        if datas.notna().any():
            ultima = datas.max().strftime("%d/%m/%Y")
    return {
        "linhas_origem": len(df), "logins_validos": int(login.loc[~sem_login].nunique()),
        "sem_login": int(sem_login.sum()), "linhas_login_duplicado": int(duplicados.sum()),
        "res_repetidos": int(re.loc[re_duplicados].nunique()),
        "situacoes": {str(k): int(v) for k, v in situacoes.value_counts().items()},
        "ultima_modificacao_cadastral": ultima, "ocorrencias": ocorrencias,
    }
