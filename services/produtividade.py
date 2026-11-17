"""services/produtividade.py
===========================
Produtividade × Disponibilidade — regra de negócio pura do painel.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
Produção e presença vivem em páginas e planilhas diferentes. Para responder
"quanta produção a equipe entrega por técnico-dia disponível?" era necessário
juntar `Prod`, `controle_absenteismo` e `lista_ativos` à mão, sem uma definição
única de denominador. Este módulo fixa as regras em uma camada pura, testável
sem Streamlit:

* :func:`normalizar_producao` — colunas canônicas da produção (supervisor,
  equipe, projeto, base, pontos, data e uma linha = uma O.S.);
* :func:`quadro_de_referencia` — headcount por supervisor a partir da
  ``lista_ativos`` (situações do quadro), com o login como identidade;
* :func:`pares_de_ausencia` — expande cada ausência em pares
  ``(login, dia)``, deduplicados e restritos a dias úteis (segunda a sexta);
* :func:`consolidar` — devolve KPIs, tabela por supervisor, quebra por tipo,
  séries semanal/diária e avisos de qualidade do recorte.

Premissas explícitas (aparecem na página, em "Como calculamos")
---------------------------------------------------------------
* **Técnico-dia disponível** = ``quadro × dias úteis − dias de ausência``.
  O quadro é o **retrato atual** da ``lista_ativos``: o portal não guarda a
  vigência histórica de base/monitor, então recortes antigos usam o quadro de
  hoje. Essa limitação é avisada, não escondida.
* **Dias úteis** são segunda a sexta, sem calendário de feriados — a mesma
  definição de :func:`services.absenteismo.calcular_dias`.
* **Ausência** é dia de afastamento do técnico, não "registro": duas faltas
  sobrepostas para o mesmo login no mesmo dia contam **um** dia, com o tipo de
  maior prioridade (falta > atestado > afastamento > licença > suspensão >
  férias > folga > treinamento > outros).
* **O.S. estimadas não realizadas** = ``dias de ausência × produtividade média
  do recorte``. É uma estimativa de ordem de grandeza, não uma medição de
  demanda perdida.
* Ausências de logins fora do quadro são contadas à parte e não entram no
  denominador; produção de supervisor sem quadro aparece com "sem base" e é
  reportada na cobertura.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Sequence

import pandas as pd

from services.absenteismo import (
    TIPOS_PROGRAMADOS,
    calcular_dias,
    filtrar_registros_periodo,
    normalizar_registros,
    registros_vazios,
)
from services.datas import converter_serie_datas
from services.hierarquia import (
    SITUACOES_QUADRO,
    normalizar_lista_ativos,
    normalizar_situacao,
)
from services.texto import (
    buscar_coluna,
    normalizar_login,
    normalizar_texto,
)

VERSAO_PRODUTIVIDADE = "1.0.0"

#: Rótulo de quem não trouxe supervisor/base na origem.
NAO_INFORMADO = "NÃO INFORMADO"

#: Colunas canônicas da produção normalizada.
COLUNAS_PRODUCAO: tuple[str, ...] = (
    "Supervisor",
    "Equipe",
    "Projeto",
    "Base",
    "Pontos",
    "O.S.",
    "Data",
)

#: Colunas de :func:`quadro_de_referencia`.
COLUNAS_QUADRO: tuple[str, ...] = ("Login", "Supervisor", "Base")

#: Colunas do detalhe de ausências (um par login × dia).
COLUNAS_AUSENCIA: tuple[str, ...] = (
    "Login",
    "Supervisor",
    "Base",
    "Tipo",
    "Data",
    "NoQuadro",
)

#: Colunas da tabela por supervisor.
COLUNAS_SUPERVISOR: tuple[str, ...] = (
    "Supervisor",
    "Base",
    "Quadro",
    "Dias Ausência",
    "Ausentes",
    "Absenteísmo (%)",
    "Técnico-dia Disponível",
    "O.S.",
    "Pontos",
    "O.S./téc-dia",
    "Pontos/téc-dia",
    "O.S. Estimadas Perdidas",
    "Leitura",
)

#: Colunas da série semanal.
COLUNAS_SEMANA: tuple[str, ...] = (
    "Semana",
    "Rótulo",
    "Dias Úteis",
    "Dias Ausência",
    "Técnico-dia Disponível",
    "O.S.",
    "Pontos",
    "O.S./téc-dia",
    "Absenteísmo (%)",
)

#: Ordem de gravidade dos tipos quando duas ausências cobrem o mesmo dia.
PRIORIDADE_TIPOS: dict[str, int] = {
    "FALTA": 1,
    "ATESTADO": 2,
    "AFASTAMENTO": 3,
    "LICENCA": 4,
    "SUSPENSAO": 5,
    "FERIAS": 6,
    "FOLGA": 7,
    "TREINAMENTO": 8,
}

#: Aliases aceitos na base de produção (a primeira coluna encontrada vence).
ALIASES_PRODUCAO: dict[str, tuple[str, ...]] = {
    "Supervisor": (
        "Supervisor",
        "Monitor",
        "Gestor",
        "SUPERVISOR",
        "MONITOR",
        "GESTOR",
        "NOME SUPERVISOR",
    ),
    "Equipe": (
        "Nome Equipe",
        "Equipe",
        "Cod Aux Equipe",
        "CódAuxEquipe",
        "COD AUX EQUIPE",
        "NOME EQUIPE",
    ),
    "Projeto": ("Projeto", "PROJETO", "Contrato", "CONTRATO"),
    "Base": ("Base", "BASE", "Região", "Regiao", "REGIÃO", "REGIAO", "Filial", "FILIAL"),
    "Pontos": ("Pontos", "PONTOS", "Pontuação", "Pontuacao", "PONTUAÇÃO"),
    "Data": (
        "Data",
        "DATA",
        "Date",
        "DATE",
        "Data Agendamento",
        "Data Conclusão",
        "Data Execução",
        "Data Execucao",
    ),
}

__all__ = [
    "ALIASES_PRODUCAO",
    "COLUNAS_AUSENCIA",
    "COLUNAS_PRODUCAO",
    "COLUNAS_QUADRO",
    "COLUNAS_SEMANA",
    "COLUNAS_SUPERVISOR",
    "Consolidado",
    "NAO_INFORMADO",
    "PRIORIDADE_TIPOS",
    "VERSAO_PRODUTIVIDADE",
    "consolidar",
    "dias_uteis",
    "gerar_insights",
    "normalizar_producao",
    "pares_de_ausencia",
    "quadro_de_referencia",
    "rotulo_dimensao",
]


# ====================================================
# 🧱 BLOCO 1: RESULTADO E AUXILIARES
# ====================================================
@dataclass(frozen=True)
class Consolidado:
    """Fotografia do recorte: KPIs, tabelas, séries e avisos de qualidade."""

    inicio: date
    fim: date
    dias_uteis: int
    headcount: int
    headcount_origem: str
    dias_ausencia: int
    tecnicos_ausentes: int
    dias_disponiveis: float
    os: int
    pontos: float
    os_por_tecnico_dia: float | None
    pontos_por_tecnico_dia: float | None
    taxa_absenteismo: float | None
    os_estimadas_perdidas: float | None
    cobertura_os: float | None
    por_supervisor: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=COLUNAS_SUPERVISOR)
    )
    por_tipo: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=("Tipo", "Natureza", "Dias", "Técnicos", "% do Total")
        )
    )
    ausencias_por_supervisor_tipo: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=("Supervisor", "Tipo", "Dias"))
    )
    serie_semanal: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=COLUNAS_SEMANA)
    )
    serie_diaria: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=("Data", "Técnicos"))
    )
    avisos: tuple[str, ...] = ()

    @property
    def vazio(self) -> bool:
        """``True`` quando não há produção nem ausência no recorte."""
        return self.os == 0 and self.dias_ausencia == 0


def _numero(valor: Any) -> float:
    """Número tolerante a texto pt-BR (``"3,5"``/``"1.234,5"``) e vazio."""
    if valor is None or valor is pd.NA or valor is pd.NaT:
        return 0.0
    if isinstance(valor, (int, float)):
        return 0.0 if pd.isna(valor) else float(valor)
    texto = str(valor).strip().replace(" ", "")
    if not texto:
        return 0.0
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def rotulo_dimensao(valor: Any) -> str:
    """Rótulo canônico de supervisor/base (caixa alta, sem acento, sem vazio)."""
    texto = normalizar_texto(valor)
    return texto or NAO_INFORMADO


def _quadro_vazio() -> pd.DataFrame:
    return pd.DataFrame({coluna: pd.Series(dtype="object") for coluna in COLUNAS_QUADRO})


def _ausencias_vazias() -> pd.DataFrame:
    dados = pd.DataFrame({coluna: pd.Series(dtype="object") for coluna in COLUNAS_AUSENCIA})
    dados["Data"] = pd.Series(dtype="datetime64[ns]")
    dados["NoQuadro"] = pd.Series(dtype="bool")
    return dados


def _como_data(valor: Any) -> date:
    """Converte date/datetime/texto em ``date`` respeitando dia/mês brasileiro."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    convertido = converter_serie_datas(pd.Series([valor])).iloc[0]
    if pd.isna(convertido):
        raise ValueError(f"Data inválida para o painel de produtividade: {valor!r}")
    return convertido.date()


def dias_uteis(inicio: Any, fim: Any) -> int:
    """Dias úteis (segunda a sexta, sem feriados) do intervalo inclusivo."""
    return int(calcular_dias(inicio, fim)[1])


# ====================================================
# 🏭 BLOCO 2: PRODUÇÃO
# ====================================================
def normalizar_producao(producao: pd.DataFrame | None) -> pd.DataFrame:
    """Colunas canônicas da produção, com uma linha = uma O.S.

    A base ``Prod`` chega com nomes diferentes conforme a origem (Sheets,
    upload, aba GPON). A página nunca procura coluna: chama este normalizador e
    usa apenas :data:`COLUNAS_PRODUCAO`. Sem supervisor, as linhas ficam em
    ``NÃO INFORMADO`` (e a página avisa); sem ``Data``, o recorte de período
    deixa de filtrar a produção — também avisado.
    """
    if producao is None or not isinstance(producao, pd.DataFrame) or producao.empty:
        vazio = pd.DataFrame({coluna: pd.Series(dtype="object") for coluna in COLUNAS_PRODUCAO})
        vazio["Pontos"] = pd.Series(dtype="float64")
        vazio["O.S."] = pd.Series(dtype="int64")
        vazio["Data"] = pd.Series(dtype="datetime64[ns]")
        return vazio

    origem = producao.copy()
    origem.columns = origem.columns.astype(str).str.strip()

    def coluna(chave: str) -> str | None:
        return buscar_coluna(origem, ALIASES_PRODUCAO[chave])

    normalizada = pd.DataFrame(index=origem.index)
    coluna_supervisor = coluna("Supervisor")
    normalizada["Supervisor"] = (
        origem[coluna_supervisor].map(rotulo_dimensao) if coluna_supervisor else NAO_INFORMADO
    )

    coluna_equipe = coluna("Equipe")
    normalizada["Equipe"] = (
        origem[coluna_equipe].map(rotulo_dimensao) if coluna_equipe else NAO_INFORMADO
    )

    coluna_projeto = coluna("Projeto")
    normalizada["Projeto"] = (
        origem[coluna_projeto].map(rotulo_dimensao) if coluna_projeto else NAO_INFORMADO
    )

    coluna_base = coluna("Base")
    normalizada["Base"] = origem[coluna_base].map(rotulo_dimensao) if coluna_base else NAO_INFORMADO

    coluna_pontos = coluna("Pontos")
    normalizada["Pontos"] = origem[coluna_pontos].map(_numero) if coluna_pontos else 0.0

    normalizada["O.S."] = 1

    coluna_data = coluna("Data")
    if coluna_data:
        normalizada["Data"] = converter_serie_datas(origem[coluna_data])
    else:
        normalizada["Data"] = pd.NaT

    return normalizada.reset_index(drop=True)[list(COLUNAS_PRODUCAO)]


# ====================================================
# 👥 BLOCO 3: QUADRO DE REFERÊNCIA
# ====================================================
def quadro_de_referencia(lista_ativos: pd.DataFrame | None) -> pd.DataFrame:
    """Headcount por supervisor a partir da ``lista_ativos``.

    Conta apenas situações do quadro (``SITUACOES_QUADRO``: ativo, férias,
    inoperante, ETN e afastado) e usa o login normalizado como identidade.
    A ``lista_ativos`` é um retrato atual: não há vigência histórica.
    """
    if lista_ativos is None or not isinstance(lista_ativos, pd.DataFrame) or lista_ativos.empty:
        return _quadro_vazio()

    dados = lista_ativos
    if not {"LOGIN", "MONITOR", "BASE", "SITUAÇÃO"}.issubset(dados.columns):
        dados = normalizar_lista_ativos(dados)
    if dados.empty or not {"LOGIN", "MONITOR", "BASE", "SITUAÇÃO"}.issubset(dados.columns):
        return _quadro_vazio()

    quadro = dados.copy()
    quadro["_situacao"] = quadro["SITUAÇÃO"].map(normalizar_situacao)
    quadro = quadro.loc[quadro["_situacao"].isin(SITUACOES_QUADRO)].copy()
    if quadro.empty:
        return _quadro_vazio()

    quadro["Login"] = quadro["LOGIN"].map(normalizar_login)
    quadro = quadro.loc[quadro["Login"].ne("")].drop_duplicates("Login", keep="last")
    quadro["Supervisor"] = quadro["MONITOR"].map(rotulo_dimensao)
    quadro["Base"] = quadro["BASE"].map(rotulo_dimensao)
    return quadro[list(COLUNAS_QUADRO)].reset_index(drop=True)


def _quadro_das_presencas(registros: pd.DataFrame | None) -> pd.DataFrame:
    """Quadro mínimo inferido dos registros de presença (fallback sem lista)."""
    if (
        registros is None
        or not isinstance(registros, pd.DataFrame)
        or registros.empty
        or "Login" not in registros.columns
    ):
        return _quadro_vazio()

    dados = registros.copy()
    dados["Login"] = dados["Login"].map(normalizar_login)
    dados = dados.loc[dados["Login"].ne("")]
    if dados.empty:
        return _quadro_vazio()
    dados["Supervisor"] = (
        dados["Monitor"].map(rotulo_dimensao) if "Monitor" in dados.columns else NAO_INFORMADO
    )
    dados["Base"] = dados["Base"].map(rotulo_dimensao) if "Base" in dados.columns else NAO_INFORMADO
    return (
        dados.sort_values(["Supervisor", "Base"])
        .drop_duplicates("Login", keep="last")[list(COLUNAS_QUADRO)]
        .reset_index(drop=True)
    )


def _mapa_do_quadro(quadro: pd.DataFrame) -> dict[str, tuple[str, str]]:
    return {
        str(linha["Login"]): (str(linha["Supervisor"]), str(linha["Base"]))
        for linha in quadro.to_dict("records")
    }


# ====================================================
# 🗓️ BLOCO 4: AUSÊNCIAS EM PARES (LOGIN × DIA)
# ====================================================
def _pares_do_registro(
    inicio: pd.Timestamp,
    fim: pd.Timestamp,
    referencia_inicio: pd.Timestamp,
    referencia_fim: pd.Timestamp,
) -> pd.DatetimeIndex:
    """Dias úteis da interseção entre a ausência e o recorte."""
    ini = max(inicio.normalize(), referencia_inicio)
    limite = min(fim.normalize(), referencia_fim)
    if pd.isna(ini) or pd.isna(limite) or limite < ini:
        return pd.DatetimeIndex([])
    return pd.bdate_range(ini, limite)


def pares_de_ausencia(
    registros: pd.DataFrame | None,
    quadro: pd.DataFrame | None,
    *,
    inicio: Any,
    fim: Any,
    tipos: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Expande cada ausência ativa em pares ``(login, dia)`` úteis.

    * canceladas e tipos que não são ausência (presente/duplado/baixa de kit)
      ficam de fora pelo próprio :func:`filtrar_registros_periodo`;
    * o mesmo login no mesmo dia conta **uma** vez, preservando o tipo de maior
      prioridade (:data:`PRIORIDADE_TIPOS`);
    * ``NoQuadro`` distingue ausências de quem está no quadro atual de quem não
      está (ex.: desligado que ainda aparece no controle). Só as primeiras
      entram no denominador dos KPIs.
    """
    if registros is None or not isinstance(registros, pd.DataFrame) or registros.empty:
        return _ausencias_vazias()
    if "_inicio" not in registros.columns or "_fim" not in registros.columns:
        registros = normalizar_registros(registros)

    try:
        inicio_data = _como_data(inicio)
        fim_data = _como_data(fim)
    except (TypeError, ValueError):
        return _ausencias_vazias()

    ativos = filtrar_registros_periodo(registros, inicio_data, fim_data)
    if ativos.empty:
        return _ausencias_vazias()

    if tipos:
        desejados = {normalizar_texto(tipo) for tipo in tipos}
        ativos = ativos.loc[ativos["Tipo"].map(normalizar_texto).isin(desejados)]
    if ativos.empty:
        return _ausencias_vazias()

    referencia_inicio = pd.Timestamp(inicio_data)
    referencia_fim = pd.Timestamp(fim_data)

    mapa = _mapa_do_quadro(quadro) if quadro is not None and not quadro.empty else {}
    linhas: list[dict[str, Any]] = []
    for registro in ativos.to_dict("records"):
        login = normalizar_login(registro.get("Login"))
        if not login:
            continue
        try:
            inicio_ausencia = pd.Timestamp(registro.get("_inicio"))
            fim_ausencia = pd.Timestamp(registro.get("_fim"))
        except (TypeError, ValueError):
            continue
        if pd.isna(inicio_ausencia) or pd.isna(fim_ausencia):
            continue

        no_quadro = not mapa or login in mapa
        if login in mapa:
            supervisor, base = mapa[login]
        else:
            supervisor = rotulo_dimensao(registro.get("Monitor"))
            base = rotulo_dimensao(registro.get("Base"))
        tipo = rotulo_dimensao(registro.get("Tipo"))

        for dia in _pares_do_registro(
            inicio_ausencia, fim_ausencia, referencia_inicio, referencia_fim
        ):
            linhas.append(
                {
                    "Login": login,
                    "Supervisor": supervisor,
                    "Base": base,
                    "Tipo": tipo,
                    "Data": dia,
                    "NoQuadro": no_quadro,
                }
            )

    if not linhas:
        return _ausencias_vazias()

    detalhe = pd.DataFrame(linhas)
    detalhe["_prioridade"] = detalhe["Tipo"].map(
        lambda tipo: PRIORIDADE_TIPOS.get(normalizar_texto(tipo), 99)
    )
    detalhe = (
        detalhe.sort_values(["_prioridade", "Tipo"])
        .drop_duplicates(["Login", "Data"], keep="first")
        .drop(columns="_prioridade")
        .sort_values(["Data", "Supervisor", "Login"])
        .reset_index(drop=True)
    )
    return detalhe[list(COLUNAS_AUSENCIA)]


# ====================================================
# 📊 BLOCO 5: AGREGAÇÕES
# ====================================================
def _agregar_ausencias(detalhe: pd.DataFrame) -> pd.DataFrame:
    colunas = ["Supervisor", "Dias Ausência", "Ausentes"]
    if detalhe.empty:
        return pd.DataFrame(columns=colunas)
    return (
        detalhe.groupby("Supervisor", as_index=False)
        .agg(**{"Dias Ausência": ("Data", "count"), "Ausentes": ("Login", "nunique")})
        .sort_values("Dias Ausência", ascending=False)
        .reset_index(drop=True)
    )


def _agregar_producao(producao: pd.DataFrame) -> pd.DataFrame:
    colunas = ["Supervisor", "O.S.", "Pontos", "Base Produção"]
    if producao.empty:
        return pd.DataFrame(columns=colunas)
    agrupado = producao.groupby("Supervisor", as_index=False).agg(
        **{"O.S.": ("O.S.", "sum"), "Pontos": ("Pontos", "sum")}
    )
    bases = (
        producao.loc[producao["Base"].astype(str).str.strip().ne("")]
        .groupby("Supervisor")["Base"]
        .agg(lambda serie: serie.mode().iat[0] if not serie.mode().empty else "")
    )
    agrupado["Base Produção"] = agrupado["Supervisor"].map(bases).fillna("")
    return agrupado[colunas]


def _por_tipo(detalhe: pd.DataFrame) -> pd.DataFrame:
    colunas = ["Tipo", "Natureza", "Dias", "Técnicos", "% do Total"]
    if detalhe.empty:
        return pd.DataFrame(columns=colunas)
    total = int(len(detalhe))
    agrupado = (
        detalhe.groupby("Tipo", as_index=False)
        .agg(Dias=("Data", "count"), Técnicos=("Login", "nunique"))
        .sort_values("Dias", ascending=False)
        .reset_index(drop=True)
    )
    programados = {normalizar_texto(tipo) for tipo in TIPOS_PROGRAMADOS}
    agrupado["Natureza"] = agrupado["Tipo"].map(
        lambda tipo: "Programada" if normalizar_texto(tipo) in programados else "Não programada"
    )
    agrupado["% do Total"] = (agrupado["Dias"] / total * 100.0).round(1) if total else 0.0
    return agrupado[colunas]


def _por_supervisor_tipo(detalhe: pd.DataFrame) -> pd.DataFrame:
    colunas = ["Supervisor", "Tipo", "Dias"]
    if detalhe.empty:
        return pd.DataFrame(columns=colunas)
    return (
        detalhe.groupby(["Supervisor", "Tipo"], as_index=False)
        .agg(Dias=("Data", "count"))
        .sort_values("Dias", ascending=False)
        .reset_index(drop=True)
    )


def _serie_diaria(detalhe: pd.DataFrame) -> pd.DataFrame:
    colunas = ["Data", "Técnicos"]
    if detalhe.empty:
        return pd.DataFrame(columns=colunas)
    return (
        detalhe.groupby("Data", as_index=False)
        .agg(Técnicos=("Login", "nunique"))
        .sort_values("Data")
        .reset_index(drop=True)
    )


def _semanas_do_periodo(inicio: date, fim: date) -> list[tuple[date, date]]:
    """Semanas de segunda a domingo, recortadas nas bordas do período."""
    cursor = inicio - timedelta(days=inicio.weekday())
    semanas: list[tuple[date, date]] = []
    while cursor <= fim:
        inicio_semana = max(cursor, inicio)
        fim_semana = min(cursor + timedelta(days=6), fim)
        if inicio_semana <= fim_semana:
            semanas.append((inicio_semana, fim_semana))
        cursor += timedelta(days=7)
    return semanas


def _serie_semanal(
    producao: pd.DataFrame,
    detalhe: pd.DataFrame,
    *,
    headcount: int,
    inicio: date,
    fim: date,
) -> pd.DataFrame:
    if "Data" not in producao.columns or producao["Data"].isna().all():
        return pd.DataFrame(columns=COLUNAS_SEMANA)

    linhas: list[dict[str, Any]] = []
    for inicio_semana, fim_semana in _semanas_do_periodo(inicio, fim):
        dias = dias_uteis(inicio_semana, fim_semana)
        mascara_producao = (
            producao["Data"].dt.date.between(inicio_semana, fim_semana)
            if not producao.empty
            else pd.Series(dtype="bool")
        )
        recorte = producao.loc[mascara_producao] if len(producao) else producao
        mascara_ausencia = (
            detalhe["Data"].dt.date.between(inicio_semana, fim_semana)
            if not detalhe.empty
            else pd.Series(dtype="bool")
        )
        ausencia = detalhe.loc[mascara_ausencia] if len(detalhe) else detalhe
        ausencias = int(len(ausencia))
        nominal = headcount * dias
        disponivel = max(0.0, float(nominal - ausencias))
        os_semana = int(recorte["O.S."].sum()) if len(recorte) else 0
        pontos = float(recorte["Pontos"].sum()) if len(recorte) else 0.0
        linhas.append(
            {
                "Semana": inicio_semana,
                "Rótulo": f"{inicio_semana:%d/%m}",
                "Dias Úteis": dias,
                "Dias Ausência": ausencias,
                "Técnico-dia Disponível": round(disponivel, 2),
                "O.S.": os_semana,
                "Pontos": round(pontos, 2),
                "O.S./téc-dia": round(os_semana / disponivel, 2) if disponivel > 0 else None,
                "Absenteísmo (%)": round(ausencias / nominal * 100.0, 2) if nominal > 0 else None,
            }
        )
    return pd.DataFrame(linhas, columns=COLUNAS_SEMANA)


# ====================================================
# 🧮 BLOCO 6: CONSOLIDAÇÃO
# ====================================================
def _leitura_do_supervisor(valor: float | None, mediana: float | None, quantidade: int) -> str:
    if valor is None or pd.isna(valor):
        return "Sem base"
    if mediana is None or quantidade < 2:
        return "Sem comparação"
    if valor >= mediana * 1.05:
        return "Acima"
    if valor <= mediana * 0.95:
        return "Abaixo"
    return "Na mediana"


def _filtrar_por_dimensoes(
    producao: pd.DataFrame,
    quadro: pd.DataFrame,
    *,
    bases: Sequence[str] | None,
    supervisores: Sequence[str] | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bases_norm = {normalizar_texto(base) for base in (bases or []) if str(base).strip()}
    supers_norm = {
        normalizar_texto(supervisor)
        for supervisor in (supervisores or [])
        if str(supervisor).strip()
    }

    quadro_filtrado = quadro
    if bases_norm:
        quadro_filtrado = quadro_filtrado.loc[quadro_filtrado["Base"].isin(bases_norm)]
    if supers_norm:
        quadro_filtrado = quadro_filtrado.loc[quadro_filtrado["Supervisor"].isin(supers_norm)]

    producao_filtrada = producao
    if supers_norm:
        producao_filtrada = producao_filtrada.loc[producao_filtrada["Supervisor"].isin(supers_norm)]
    if bases_norm:
        supervisores_das_bases = set(quadro_filtrado["Supervisor"])
        base_producao = producao_filtrada["Base"].astype(str).str.strip()
        producao_filtrada = producao_filtrada.loc[
            producao_filtrada["Supervisor"].isin(supervisores_das_bases)
            | base_producao.isin(bases_norm)
        ]
    return producao_filtrada, quadro_filtrado


def consolidar(
    producao: pd.DataFrame | None,
    registros: pd.DataFrame | None,
    lista_ativos: pd.DataFrame | None,
    *,
    inicio: Any,
    fim: Any,
    tipos: Sequence[str] | None = None,
    bases: Sequence[str] | None = None,
    supervisores: Sequence[str] | None = None,
) -> Consolidado:
    """Cruza produção, presença e quadro em um recorte de datas.

    Tolerante a fonte ausente: sem presença, a disponibilidade é o quadro cheio
    (e o painel avisa); sem quadro, o headcount é inferido dos próprios
    registros de presença; sem data na produção, o período vale só para as
    ausências. Nunca levanta exceção por dado faltante — devolve avisos.
    """
    inicio_data = _como_data(inicio)
    fim_data = _como_data(fim)
    if fim_data < inicio_data:
        inicio_data, fim_data = fim_data, inicio_data

    producao_norm = normalizar_producao(producao)
    registros_norm = (
        registros
        if isinstance(registros, pd.DataFrame) and not registros.empty
        else registros_vazios()
    )
    avisos: list[str] = []

    # Quadro e headcount -----------------------------------------------------
    quadro = quadro_de_referencia(lista_ativos)
    origem_quadro = "lista_ativos"
    if quadro.empty:
        quadro = _quadro_das_presencas(registros_norm)
        origem_quadro = "presença" if not quadro.empty else "indisponível"
        if origem_quadro == "presença":
            avisos.append(
                "Lista de ativos indisponível: o quadro foi inferido dos registros de "
                "presença, então técnicos sem nenhuma ausência no período podem faltar."
            )
        else:
            avisos.append(
                "Sem lista de ativos nem registros de presença: não há denominador de "
                "técnico-dia disponível. Os volumes de produção continuam válidos."
            )

    quadro_completo = quadro.copy()
    producao_norm, quadro = _filtrar_por_dimensoes(
        producao_norm, quadro, bases=bases, supervisores=supervisores
    )

    # Recorte de datas da produção -----------------------------------------
    linhas_sem_data = 0
    tem_data = "Data" in producao_norm.columns and producao_norm["Data"].notna().any()
    if tem_data:
        linhas_sem_data = int(producao_norm["Data"].isna().sum())
        mascara = producao_norm["Data"].dt.date.between(inicio_data, fim_data)
        producao_recorte = producao_norm.loc[mascara].copy()
    else:
        producao_recorte = producao_norm.copy()
        if not producao_recorte.empty:
            avisos.append(
                "A base de produção não trouxe uma coluna de data reconhecida: o período "
                "filtra as ausências, mas não as O.S. O total exibido é o da carga inteira."
            )

    # Ausências -------------------------------------------------------------
    detalhe = pares_de_ausencia(
        registros_norm,
        quadro_completo,
        inicio=inicio_data,
        fim=fim_data,
        tipos=tipos,
    )
    if not detalhe.empty and not quadro.empty:
        # Recorte de base/supervisor: a ausência de quem ficou fora do recorte
        # não entra no denominador, mas também não é "fora do quadro".
        logins_recorte = set(quadro["Login"])
        detalhe = detalhe.loc[detalhe["Login"].isin(logins_recorte) | ~detalhe["NoQuadro"]]
    fora_do_quadro = detalhe.loc[~detalhe["NoQuadro"]] if not detalhe.empty else detalhe
    detalhe_quadro = detalhe.loc[detalhe["NoQuadro"]] if not detalhe.empty else detalhe
    if not fora_do_quadro.empty:
        avisos.append(
            f"{len(fora_do_quadro):,} dia(s) de ausência de login fora do quadro atual "
            "foram ignorados nos KPIs (aparecem apenas na conferência).".replace(",", ".")
        )
    if not tem_data and producao_recorte.empty:
        avisos.append("Não há O.S. no recorte atual.")

    # Headcount e volumes ---------------------------------------------------
    headcount = int(quadro["Login"].nunique()) if not quadro.empty else 0
    total_dias = dias_uteis(inicio_data, fim_data)
    nominal = headcount * total_dias
    dias_ausencia = int(len(detalhe_quadro))
    tecnicos_ausentes = int(detalhe_quadro["Login"].nunique()) if not detalhe_quadro.empty else 0
    disponiveis = max(0.0, float(nominal - dias_ausencia))
    os_total = int(producao_recorte["O.S."].sum()) if not producao_recorte.empty else 0
    pontos_total = float(producao_recorte["Pontos"].sum()) if not producao_recorte.empty else 0.0
    os_por_tecnico = os_total / disponiveis if disponiveis > 0 else None
    pontos_por_tecnico = pontos_total / disponiveis if disponiveis > 0 else None
    taxa = (dias_ausencia / nominal * 100.0) if nominal > 0 else None

    # Tabela por supervisor -------------------------------------------------
    quadro_agregado = pd.DataFrame(columns=["Supervisor", "Base", "Quadro"])
    if not quadro.empty:
        quadro_agregado = (
            quadro.groupby("Supervisor", as_index=False)
            .agg(
                Quadro=("Login", "nunique"),
                Base=(
                    "Base",
                    lambda serie: serie.mode().iat[0] if not serie.mode().empty else NAO_INFORMADO,
                ),
            )
            .reset_index(drop=True)
        )

    ausencias_agregadas = _agregar_ausencias(detalhe_quadro)
    producao_agregada = _agregar_producao(producao_recorte)

    tabela = quadro_agregado.merge(ausencias_agregadas, on="Supervisor", how="outer")
    tabela = tabela.merge(producao_agregada, on="Supervisor", how="outer")
    if tabela.empty:
        tabela = pd.DataFrame(columns=COLUNAS_SUPERVISOR)
    else:
        for coluna in ("Quadro", "Dias Ausência", "Ausentes", "O.S.", "Pontos"):
            if coluna not in tabela.columns:
                tabela[coluna] = 0
            tabela[coluna] = pd.to_numeric(tabela[coluna], errors="coerce").fillna(0)
        tabela["Supervisor"] = tabela["Supervisor"].map(rotulo_dimensao)
        tabela["Base"] = tabela["Base"].fillna("").astype(str).str.strip().replace("", pd.NA)
        tabela["Base"] = tabela["Base"].fillna(
            tabela["Base Produção"].fillna("").replace("", NAO_INFORMADO)
        )
        tabela["Dias Úteis"] = total_dias
        tabela["Nominal"] = tabela["Quadro"] * total_dias
        tabela["Técnico-dia Disponível"] = (tabela["Nominal"] - tabela["Dias Ausência"]).clip(
            lower=0
        )
        tabela["Absenteísmo (%)"] = (tabela["Dias Ausência"] / tabela["Nominal"] * 100.0).where(
            tabela["Nominal"] > 0
        )
        tabela["O.S./téc-dia"] = (tabela["O.S."] / tabela["Técnico-dia Disponível"]).where(
            tabela["Técnico-dia Disponível"] > 0
        )
        tabela["Pontos/téc-dia"] = (tabela["Pontos"] / tabela["Técnico-dia Disponível"]).where(
            tabela["Técnico-dia Disponível"] > 0
        )
        tabela["O.S. Estimadas Perdidas"] = tabela["Dias Ausência"] * (os_por_tecnico or 0.0)

        validos = tabela["O.S./téc-dia"].dropna()
        mediana = float(validos.median()) if len(validos) else None
        tabela["Leitura"] = [
            _leitura_do_supervisor(valor, mediana, len(validos)) for valor in tabela["O.S./téc-dia"]
        ]
        tabela = tabela.sort_values(["O.S.", "Dias Ausência"], ascending=False).reset_index(
            drop=True
        )
        tabela = tabela[list(COLUNAS_SUPERVISOR)]

    # Cobertura e estimativa ------------------------------------------------
    os_com_quadro = 0
    if not tabela.empty:
        os_com_quadro = int(tabela.loc[tabela["Quadro"] > 0, "O.S."].sum())
    cobertura = (os_com_quadro / os_total) if os_total else None
    estimadas = (
        dias_ausencia * os_por_tecnico if os_por_tecnico is not None and dias_ausencia else None
    )

    if cobertura is not None and cobertura < 0.9:
        avisos.append(
            f"{1 - cobertura:.0%} das O.S. estão em supervisores sem quadro na lista de "
            "ativos: a produtividade geral fica levemente otimista."
        )
    if linhas_sem_data:
        avisos.append(
            f"{linhas_sem_data:,} linha(s) de produção sem data ficaram fora do recorte.".replace(
                ",", "."
            )
        )

    return Consolidado(
        inicio=inicio_data,
        fim=fim_data,
        dias_uteis=total_dias,
        headcount=headcount,
        headcount_origem=origem_quadro,
        dias_ausencia=dias_ausencia,
        tecnicos_ausentes=tecnicos_ausentes,
        dias_disponiveis=round(disponiveis, 2),
        os=os_total,
        pontos=round(pontos_total, 2),
        os_por_tecnico_dia=round(os_por_tecnico, 2) if os_por_tecnico is not None else None,
        pontos_por_tecnico_dia=(
            round(pontos_por_tecnico, 2) if pontos_por_tecnico is not None else None
        ),
        taxa_absenteismo=round(taxa, 2) if taxa is not None else None,
        os_estimadas_perdidas=round(estimadas, 1) if estimadas is not None else None,
        cobertura_os=round(cobertura, 4) if cobertura is not None else None,
        por_supervisor=tabela,
        por_tipo=_por_tipo(detalhe_quadro),
        ausencias_por_supervisor_tipo=_por_supervisor_tipo(detalhe_quadro),
        serie_semanal=_serie_semanal(
            producao_recorte,
            detalhe_quadro,
            headcount=headcount,
            inicio=inicio_data,
            fim=fim_data,
        ),
        serie_diaria=_serie_diaria(detalhe_quadro),
        avisos=tuple(avisos),
    )


# ====================================================
# 💡 BLOCO 7: INSIGHTS AUTOMÁTICOS
# ====================================================
def gerar_insights(consolidado: Consolidado) -> list[tuple[str, str]]:
    """Até três leituras sobre o recorte (texto, tipo para ``render_insight``)."""
    insights: list[tuple[str, str]] = []
    tabela = consolidado.por_supervisor

    if consolidado.headcount == 0:
        insights.append(
            (
                "Sem quadro de referência não é possível calcular técnico-dia disponível "
                "nem produtividade real. Carregue a lista de ativos.",
                "alerta",
            )
        )
    elif consolidado.dias_ausencia == 0:
        insights.append(
            (
                f"Nenhuma ausência registrada no período para {consolidado.headcount} "
                "técnico(s) do quadro: a disponibilidade considerada é integral.",
                "info",
            )
        )

    if not tabela.empty and consolidado.dias_ausencia > 0:
        candidatos = tabela.loc[tabela["Dias Ausência"] > 0]
        if not candidatos.empty:
            lider = candidatos.sort_values("Dias Ausência", ascending=False).iloc[0]
            participacao = (
                float(lider["Dias Ausência"]) / consolidado.dias_ausencia * 100.0
                if consolidado.dias_ausencia
                else 0.0
            )
            insights.append(
                (
                    f"**{lider['Supervisor']}** concentra {participacao:.0f}% dos dias de "
                    f"ausência do recorte ({int(lider['Dias Ausência'])} dia(s) e "
                    f"{int(lider['Ausentes'])} técnico(s)).",
                    "info",
                )
            )

    if consolidado.os_estimadas_perdidas and consolidado.os_estimadas_perdidas >= 1:
        insights.append(
            (
                f"O tempo indisponível equivale a aproximadamente "
                f"**{consolidado.os_estimadas_perdidas:.0f} O.S.** na produtividade média "
                "do recorte — uma estimativa, não uma demanda perdida medida.",
                "alerta",
            )
        )

    if consolidado.cobertura_os is not None and consolidado.cobertura_os < 0.9:
        insights.append(
            (
                f"Cobertura de quadro: {consolidado.cobertura_os:.0%} das O.S. estão em "
                "supervisores com headcount conhecido. As demais aparecem como "
                "“Sem base” na tabela.",
                "alerta",
            )
        )

    return insights[:3]
