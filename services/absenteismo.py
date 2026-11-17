"""
services/absenteismo.py
=======================
Controle de ausências (faltas, folgas, férias, atestados...) do portal.

Versão: 1.1.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
A ``lista_ativos`` diz **quem** é o quadro (Login → Técnico → Monitor → Base,
via :mod:`services.hierarquia`), mas não registra **quando** cada técnico se
ausenta. Este serviço é a fonte única desse controle:

* os registros moram na aba ``controle_absenteismo`` da **mesma planilha** da
  ``lista_ativos`` (:data:`config.settings.SHEET_ABA_ABSENTEISMO`) — a aba é
  criada com o cabeçalho oficial na primeira gravação;
* a leitura usa o caminho compartilhado
  (:func:`services.google_drive_client.carregar_planilha_gsheets_csv`) e a
  gravação usa ``gspread`` com a conta de serviço de ``st.secrets``
  (``gcp_service_account``), o mesmo padrão de ``pages/gestao_ativos.py`` —
  por isso ``gspread`` é importado de forma tardia, dentro das funções de
  escrita: ler e testar o módulo não exigem as credenciais;
* o cálculo de dias é único: **dias corridos** (início–fim, inclusive) e
  **dias úteis** (seg–sex, sem calendário de feriados), sempre recalculados
  a partir das datas — os valores gravados na planilha são conferência, não
  fonte;
* cancelar não apaga: o registro vira ``Cancelado`` e continua auditável.

Grade mensal (técnico × dia)
----------------------------
A página mostra o controle **no formato da planilha operacional**: ``RE,
Login, Técnico, Monitor, Base, U.N.`` + uma coluna por dia (``1/nov.``...).
A grade é derivada dos registros por :func:`montar_matriz_ausencias`; a
leitura da aba também aceita esse formato, convertendo as marcas em registros
por :func:`normalizar_matriz_ausencias` (nesse caso a aba é somente leitura,
para a gravação não apagar as colunas de dias). Os códigos de célula
(``F``/``FE``/``AT``...) e as marcas de presença estão em
:data:`CODIGOS_AUSENCIA` / :data:`MARCAS_PRESENCA`.

Regras de contagem
------------------
* registro **ativo** = ``Status`` diferente de ``Cancelado``;
* registro cobre um período quando ``[Início, Fim] ∩ período ≠ ∅``; os dias
  "no período" são contados só na interseção (férias que começam no mês
  anterior não inflam o mês atual);
* "ausente hoje" = técnico único com registro ativo cobrindo a data.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from services.datas import converter_serie_datas
from services.texto import buscar_coluna, normalizar_chave, normalizar_login

logger = logging.getLogger(__name__)

VERSAO_ABSENTEISMO = "1.1.0"

#: Chave dos registros do controle em ``st.session_state``.
CHAVE_SESSAO_REGISTROS = "totale_controle_absenteismo"
#: ``True`` quando a aba veio no formato de grade (técnico × dia), não em registros.
CHAVE_SESSAO_ORIGEM_GRADE = "totale_absenteismo_origem_grade"

#: Colunas oficiais da aba ``controle_absenteismo`` (ordem de gravação).
COLUNAS_REGISTROS: tuple[str, ...] = (
    "ID",
    "Login",
    "Técnico",
    "Monitor",
    "Base",
    "Tipo",
    "Data Início",
    "Data Fim",
    "Dias Corridos",
    "Dias Úteis",
    "Justificativa",
    "Motivo",
    "Status",
    "Registrado em",
)

#: Tipo usado para marcas da grade que não casam com um tipo conhecido.
TIPO_OUTROS = "Outros"

#: Tipos de ausência aceitos no controle.
TIPOS_AUSENCIA: tuple[str, ...] = (
    "Falta",
    "Folga",
    "Férias",
    "Atestado",
    "Afastamento",
    "Licença",
    "Suspensão",
    "Treinamento",
    TIPO_OUTROS,
)

#: Tipos que costumam ser programados (agenda) — os demais são imprevistos.
TIPOS_PROGRAMADOS: tuple[str, ...] = ("Folga", "Férias", "Treinamento")

#: Identidade da grade mensal (mesma ordem da planilha de controle).
COLUNAS_IDENTIDADE_GRADE: tuple[str, ...] = (
    "RE",
    "Login",
    "Técnico",
    "Monitor",
    "Base",
    "U.N.",
)

#: Meses curtos usados no cabeçalho da grade (``1/nov.``).
MESES_ABREVIADOS: tuple[str, ...] = (
    "jan.",
    "fev.",
    "mar.",
    "abr.",
    "mai.",
    "jun.",
    "jul.",
    "ago.",
    "set.",
    "out.",
    "nov.",
    "dez.",
)

#: Dias da semana curtos (segunda = 0), exibidos sob o dia no cabeçalho.
DIAS_SEMANA_ABREVIADOS: tuple[str, ...] = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")

#: Abreviação de cada tipo dentro da célula da grade (como na planilha).
ABREVIACOES_AUSENCIA: dict[str, str] = {
    "Falta": "F",
    "Folga": "FO",
    "Férias": "FE",
    "Atestado": "AT",
    "Afastamento": "AF",
    "Licença": "LI",
    "Suspensão": "SU",
    "Treinamento": "TR",
    TIPO_OUTROS: "OUT",
}

#: Códigos aceitos na grade → tipo canônico (comparação sem acento/pontuação).
CODIGOS_AUSENCIA: dict[str, str] = {
    "F": "Falta",
    "FA": "Falta",
    "FAL": "Falta",
    "FALTA": "Falta",
    "FJ": "Falta",
    "FI": "Falta",
    "FE": "Férias",
    "FER": "Férias",
    "FERIAS": "Férias",
    "FO": "Folga",
    "FOL": "Folga",
    "FOLGA": "Folga",
    "DSR": "Folga",
    "A": "Atestado",
    "AT": "Atestado",
    "ATE": "Atestado",
    "ATESTADO": "Atestado",
    "AM": "Atestado",
    "AF": "Afastamento",
    "AFA": "Afastamento",
    "AFAST": "Afastamento",
    "AFASTAMENTO": "Afastamento",
    "L": "Licença",
    "LIC": "Licença",
    "LICENCA": "Licença",
    "LM": "Licença",
    "LP": "Licença",
    "S": "Suspensão",
    "SU": "Suspensão",
    "SUS": "Suspensão",
    "SUSP": "Suspensão",
    "SUSPENSAO": "Suspensão",
    "T": "Treinamento",
    "TR": "Treinamento",
    "TRE": "Treinamento",
    "TREIN": "Treinamento",
    "TREINAMENTO": "Treinamento",
    "O": TIPO_OUTROS,
    "OUT": TIPO_OUTROS,
    "OUTROS": TIPO_OUTROS,
}

#: Marcas que significam presença (não viram ausência na grade).
MARCAS_PRESENCA: frozenset[str] = frozenset(
    {"OK", "P", "PRES", "PRESENTE", "DISPONIVEL"}
)

#: Palavras que identificam o tipo quando a célula traz o nome por extenso.
_PALAVRAS_TIPO: tuple[tuple[str, str], ...] = (
    ("FERIAS", "Férias"),
    ("FALTA", "Falta"),
    ("FOLGA", "Folga"),
    ("ATESTADO", "Atestado"),
    ("AFAST", "Afastamento"),
    ("LICENC", "Licença"),
    ("SUSPENS", "Suspensão"),
    ("TREIN", "Treinamento"),
)

#: Mínimo de colunas de dia para reconhecer uma aba no formato de grade.
MIN_COLUNAS_DIA = 2

_RE_DIA_MES_ANO = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?$")
_RE_DIA_MES_NOME = re.compile(
    r"^(\d{1,2})\s*[/.\-]?\s*([A-Za-zÀ-ÿ]{3,})\.?\s*(?:[/.\-]?\s*(\d{2,4}))?$"
)
_RE_DIA_SOZINHO = re.compile(r"^\d{1,2}$")
_RE_ISO_DIA = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")
_RE_SEPARADOR_CODIGOS = re.compile(r"\s*[/+,;]\s*|\s+e\s+", re.IGNORECASE)

_MESES_POR_NOME: dict[str, int] = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}

JUSTIFICATIVAS: tuple[str, ...] = ("Justificada", "Não justificada", "Não se aplica")

STATUS_ATIVO = "Ativo"
STATUS_CANCELADO = "Cancelado"

_RE_ESPACOS = re.compile(r"\s+")


def _texto(valor: Any) -> str:
    """Texto de exibição sem valores fantasmas (``nan``/``None`` viram ``""``)."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    texto = _RE_ESPACOS.sub(" ", str(valor).strip())
    return "" if texto.upper() in {"NAN", "NONE", "NAT", "NULL", "N/A", "NA", "<NA>"} else texto


def _tipo_canonico(valor: Any) -> str:
    """Tipo no rótulo oficial (``'FERIAS'`` → ``'Férias'``); desconhecido vira Title Case."""
    texto = _texto(valor)
    for tipo in TIPOS_AUSENCIA:
        if texto.casefold() == tipo.casefold():
            return tipo
    return texto.title()


__all__ = [
    "ABREVIACOES_AUSENCIA",
    "CHAVE_SESSAO_ORIGEM_GRADE",
    "CHAVE_SESSAO_REGISTROS",
    "CODIGOS_AUSENCIA",
    "COLUNAS_IDENTIDADE_GRADE",
    "COLUNAS_REGISTROS",
    "DIAS_SEMANA_ABREVIADOS",
    "JUSTIFICATIVAS",
    "MARCAS_PRESENCA",
    "MESES_ABREVIADOS",
    "MIN_COLUNAS_DIA",
    "STATUS_ATIVO",
    "STATUS_CANCELADO",
    "TIPO_OUTROS",
    "TIPOS_AUSENCIA",
    "TIPOS_PROGRAMADOS",
    "VERSAO_ABSENTEISMO",
    "abreviar_ausencia",
    "agrupar_registros",
    "calcular_dias",
    "carregar_registros",
    "carregar_registros_com_origem",
    "codigo_para_tipo",
    "detectar_colunas_dias",
    "dias_no_periodo",
    "fase_do_registro",
    "filtrar_registros_periodo",
    "gravar_registros",
    "montar_matriz_ausencias",
    "normalizar_matriz_ausencias",
    "normalizar_quadro_identidade",
    "normalizar_registros",
    "origem_grade_da_sessao",
    "registrar_ausencia",
    "registros_da_sessao",
    "registros_vazios",
    "resumir_controle",
    "serie_diaria_ausencias",
    "tipos_do_codigo",
]


# ============================================================
# 📅 BLOCO 1: CÁLCULO DE DIAS (PURO)
# ============================================================
def calcular_dias(inicio: Any, fim: Any) -> tuple[int, int]:
    """``(dias corridos, dias úteis)`` de ``inicio`` a ``fim``, inclusive.

    Dias úteis = segunda a sexta (sem calendário de feriados). Intervalo
    vazio/invertido devolve ``(0, 0)``.
    """
    try:
        ini = pd.Timestamp(inicio).normalize()
        limite = pd.Timestamp(fim).normalize()
    except (TypeError, ValueError):
        return (0, 0)
    if pd.isna(ini) or pd.isna(limite) or limite < ini:
        return (0, 0)
    corridos = int((limite - ini).days) + 1
    uteis = int(np.busday_count(ini.date(), (limite + timedelta(days=1)).date()))
    return (corridos, uteis)


def dias_no_periodo(
    inicio: Any, fim: Any, periodo_inicio: Any, periodo_fim: Any
) -> tuple[int, int]:
    """Dias da ausência **dentro** do período (interseção dos intervalos)."""
    try:
        ini = max(pd.Timestamp(inicio).normalize(), pd.Timestamp(periodo_inicio).normalize())
        limite = min(pd.Timestamp(fim).normalize(), pd.Timestamp(periodo_fim).normalize())
    except (TypeError, ValueError):
        return (0, 0)
    if pd.isna(ini) or pd.isna(limite):
        return (0, 0)
    return calcular_dias(ini, limite)


def fase_do_registro(registro: Any, hoje: date | None = None) -> str:
    """Fase temporal de um registro: ``Programada``/``Em andamento``/``Concluída``/``Cancelada``."""
    referencia = hoje or date.today()
    if isinstance(registro, dict):
        status = _texto(registro.get("Status"))
        ini, fim = registro.get("_inicio"), registro.get("_fim")
    else:
        status = _texto(getattr(registro, "Status", ""))
        ini, fim = getattr(registro, "_inicio", None), getattr(registro, "_fim", None)
    if status.casefold() == STATUS_CANCELADO.casefold():
        return STATUS_CANCELADO
    try:
        ini_ts, fim_ts = pd.Timestamp(ini), pd.Timestamp(fim)
    except (TypeError, ValueError):
        return STATUS_ATIVO
    if pd.isna(ini_ts) or pd.isna(fim_ts):
        return STATUS_ATIVO
    if fim_ts.date() < referencia:
        return "Concluída"
    if ini_ts.date() > referencia:
        return "Programada"
    return "Em andamento"


# ============================================================
# 🧹 BLOCO 2: NORMALIZAÇÃO DOS REGISTROS
# ============================================================
def registros_vazios() -> pd.DataFrame:
    """DataFrame sem linhas, mas com as colunas oficiais + auxiliares de cálculo."""
    df = pd.DataFrame({coluna: pd.Series(dtype="object") for coluna in COLUNAS_REGISTROS})
    df["_inicio"] = pd.Series(dtype="datetime64[ns]")
    df["_fim"] = pd.Series(dtype="datetime64[ns]")
    return df


def normalizar_registros(bruto: pd.DataFrame | None) -> pd.DataFrame:
    """Normaliza a aba ``controle_absenteismo`` para o formato do painel.

    * aceita os cabeçalhos oficiais e variações (``Inicio``, ``Data_Inicio``...);
    * datas via :func:`services.datas.converter_serie_datas` (ISO ou BR);
    * ``Dias Corridos``/``Dias Úteis`` **recalculados** das datas;
    * colunas auxiliares ``_inicio``/``_fim`` (datetime) para filtro e fase;
    * linhas sem login ou sem início válido são descartadas (lixo de planilha).
    """
    if bruto is None or not isinstance(bruto, pd.DataFrame) or bruto.empty:
        return registros_vazios()

    base = bruto.copy()
    base.columns = base.columns.astype(str).str.strip()

    aliases: dict[str, tuple[str, ...]] = {
        "ID": ("ID", "CODIGO", "CÓDIGO"),
        "Login": ("LOGIN", "LOGIN DO TÉCNICO", "MATRICULA", "MATRÍCULA", "RE"),
        "Técnico": ("TÉCNICO", "TECNICO", "NOME", "COLABORADOR"),
        "Monitor": ("MONITOR", "GESTOR", "SUPERVISOR"),
        "Base": ("BASE", "REGIÃO", "REGIAO", "FILIAL"),
        "Tipo": ("TIPO", "TIPO DE AUSÊNCIA", "TIPO DE AUSENCIA", "AUSÊNCIA", "AUSENCIA"),
        "Data Início": ("DATA INÍCIO", "DATA INICIO", "INÍCIO", "INICIO", "DATA_INICIO", "DT INICIO"),
        "Data Fim": ("DATA FIM", "FIM", "DATA_FIM", "DT FIM", "DATA TÉRMINO", "DATA TERMINO"),
        "Justificativa": ("JUSTIFICATIVA", "JUSTIFICADA"),
        "Motivo": ("MOTIVO", "OBSERVAÇÃO", "OBSERVACAO", "OBS", "DESCRIÇÃO", "DESCRICAO"),
        "Status": ("STATUS", "SITUAÇÃO", "SITUACAO"),
        "Registrado em": ("REGISTRADO EM", "REGISTRADO_EM", "CRIADO EM", "DATA REGISTRO"),
    }
    renomear: dict[str, str] = {}
    for destino, nomes in aliases.items():
        coluna = buscar_coluna(base, nomes)
        if coluna is not None and coluna not in renomear:
            renomear[coluna] = destino
    if "Login" not in renomear.values() or "Data Início" not in renomear.values():
        logger.debug("Controle de absenteísmo sem Login/Data Início; colunas: %s", list(base.columns))
        return registros_vazios()

    resultado = base.rename(columns=renomear)
    for coluna in COLUNAS_REGISTROS:
        if coluna not in resultado.columns:
            resultado[coluna] = ""
    resultado = resultado[list(COLUNAS_REGISTROS)].copy()

    resultado["Login"] = resultado["Login"].map(normalizar_login)
    resultado["_inicio"] = converter_serie_datas(resultado["Data Início"])
    resultado["_fim"] = converter_serie_datas(resultado["Data Fim"])
    # Registro de um dia só pode vir sem fim na planilha: fim = início.
    resultado["_fim"] = resultado["_fim"].fillna(resultado["_inicio"])
    resultado = resultado.loc[resultado["Login"].ne("") & resultado["_inicio"].notna()].copy()
    # Fim antes do início (digitação invertida): trata como dia único.
    invertido = resultado["_fim"] < resultado["_inicio"]
    resultado.loc[invertido, "_fim"] = resultado.loc[invertido, "_inicio"]

    for coluna in ("Técnico", "Monitor", "Base"):
        resultado[coluna] = resultado[coluna].map(_texto).str.title()
    resultado["Tipo"] = resultado["Tipo"].map(_tipo_canonico)
    resultado["Justificativa"] = resultado["Justificativa"].map(
        lambda v: next(
            (j for j in JUSTIFICATIVAS if _texto(v).casefold() == j.casefold()),
            _texto(v).title() or "Não se aplica",
        )
    )
    resultado["Status"] = resultado["Status"].map(
        lambda v: STATUS_CANCELADO
        if _texto(v).casefold() == STATUS_CANCELADO.casefold()
        else STATUS_ATIVO
    )
    resultado["Motivo"] = resultado["Motivo"].map(_texto)
    resultado["Registrado em"] = resultado["Registrado em"].map(_texto)
    resultado["ID"] = resultado["ID"].map(_texto)
    sem_id = resultado["ID"].eq("")
    if sem_id.any():
        # ID estável para registros antigos sem código: posição na planilha.
        resultado.loc[sem_id, "ID"] = [
            f"legado-{i}" for i in resultado.index[sem_id]
        ]

    dias = [calcular_dias(ini, fim) for ini, fim in zip(resultado["_inicio"], resultado["_fim"])]
    resultado["Dias Corridos"] = [d[0] for d in dias]
    resultado["Dias Úteis"] = [d[1] for d in dias]
    return resultado.reset_index(drop=True)


# ============================================================
# 📊 BLOCO 3: RECORTES, RESUMO E AGRUPAMENTOS (PURO)
# ============================================================
def _ativos(df: pd.DataFrame | None) -> pd.DataFrame:
    """Somente registros não cancelados, com as colunas auxiliares garantidas."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return registros_vazios()
    if "Status" not in df.columns or "_inicio" not in df.columns:
        return registros_vazios()
    return df.loc[df["Status"].ne(STATUS_CANCELADO) & df["Tipo"].ne("Presente")].copy()


def filtrar_registros_periodo(
    df: pd.DataFrame | None, periodo_inicio: Any, periodo_fim: Any
) -> pd.DataFrame:
    """Registros ativos que **cobrem** ao menos um dia do período."""
    ativos = _ativos(df)
    if ativos.empty:
        return ativos
    try:
        ini = pd.Timestamp(periodo_inicio).normalize()
        fim = pd.Timestamp(periodo_fim).normalize()
    except (TypeError, ValueError):
        return ativos
    if pd.isna(ini) or pd.isna(fim):
        return ativos
    mascara = (ativos["_inicio"] <= fim) & (ativos["_fim"] >= ini)
    return ativos.loc[mascara].copy()


def _dias_periodo(df: pd.DataFrame, periodo_inicio: Any, periodo_fim: Any) -> pd.DataFrame:
    """Anexa ``_dias_corridos_periodo``/``_dias_uteis_periodo`` (interseção)."""
    dados = df.copy()
    if dados.empty:
        dados["_dias_corridos_periodo"] = pd.Series(dtype="int64")
        dados["_dias_uteis_periodo"] = pd.Series(dtype="int64")
        return dados
    pares = [
        dias_no_periodo(ini, fim, periodo_inicio, periodo_fim)
        for ini, fim in zip(dados["_inicio"], dados["_fim"])
    ]
    dados["_dias_corridos_periodo"] = [p[0] for p in pares]
    dados["_dias_uteis_periodo"] = [p[1] for p in pares]
    return dados


def resumir_controle(
    df: pd.DataFrame | None,
    *,
    periodo_inicio: Any,
    periodo_fim: Any,
    hoje: date | None = None,
) -> dict[str, Any]:
    """KPIs do controle no período + retrato de hoje (sobre todos os ativos)."""
    referencia = hoje or date.today()
    ativos = _ativos(df)
    no_periodo = _dias_periodo(
        filtrar_registros_periodo(ativos, periodo_inicio, periodo_fim),
        periodo_inicio,
        periodo_fim,
    )
    cobrindo_hoje = ativos.loc[
        (ativos["_inicio"].dt.date <= referencia) & (ativos["_fim"].dt.date >= referencia)
    ] if not ativos.empty else ativos
    futuras = (
        ativos.loc[ativos["_inicio"].dt.date > referencia] if not ativos.empty else ativos
    )
    return {
        "registros_periodo": int(len(no_periodo)),
        "registros_total": int(len(ativos)),
        "cancelados": int(len(df) - len(ativos)) if isinstance(df, pd.DataFrame) else 0,
        "tecnicos_periodo": int(no_periodo["Login"].nunique()) if not no_periodo.empty else 0,
        "dias_corridos_periodo": int(no_periodo["_dias_corridos_periodo"].sum())
        if not no_periodo.empty
        else 0,
        "dias_uteis_periodo": int(no_periodo["_dias_uteis_periodo"].sum())
        if not no_periodo.empty
        else 0,
        "ausentes_hoje": int(cobrindo_hoje["Login"].nunique()) if not cobrindo_hoje.empty else 0,
        "registros_hoje": int(len(cobrindo_hoje)),
        "programadas": int(len(futuras)),
        "faltas_periodo": int((no_periodo["Tipo"] == "Falta").sum()) if not no_periodo.empty else 0,
        "ferias_periodo": int((no_periodo["Tipo"] == "Férias").sum())
        if not no_periodo.empty
        else 0,
    }


def agrupar_registros(
    df: pd.DataFrame | None,
    coluna: str,
    *,
    periodo_inicio: Any,
    periodo_fim: Any,
) -> pd.DataFrame:
    """Registros/técnicos/dias por ``Tipo``, ``Base`` ou ``Monitor`` no período."""
    colunas = [coluna, "Registros", "Técnicos", "Dias Corridos", "Dias Úteis"]
    no_periodo = _dias_periodo(
        filtrar_registros_periodo(df, periodo_inicio, periodo_fim), periodo_inicio, periodo_fim
    )
    if no_periodo.empty or coluna not in no_periodo.columns:
        return pd.DataFrame(columns=colunas)
    dados = no_periodo.copy()
    dados[coluna] = dados[coluna].map(_texto).replace("", "Não informado")
    agrupado = (
        dados.groupby(coluna, as_index=False)
        .agg(
            Registros=("ID", "count"),
            Técnicos=("Login", "nunique"),
            **{
                "Dias Corridos": ("_dias_corridos_periodo", "sum"),
                "Dias Úteis": ("_dias_uteis_periodo", "sum"),
            },
        )
        .sort_values(["Dias Úteis", "Registros"], ascending=False)
        .reset_index(drop=True)
    )
    return agrupado[colunas]


def serie_diaria_ausencias(
    df: pd.DataFrame | None, *, periodo_inicio: Any, periodo_fim: Any
) -> pd.DataFrame:
    """Série diária ``Data`` × ``Ausências`` × ``Técnicos`` (para o calendário)."""
    colunas = ["Data", "Ausências", "Técnicos"]
    no_periodo = filtrar_registros_periodo(df, periodo_inicio, periodo_fim)
    if no_periodo.empty:
        return pd.DataFrame(columns=colunas)
    try:
        ini = pd.Timestamp(periodo_inicio).normalize()
        fim = pd.Timestamp(periodo_fim).normalize()
    except (TypeError, ValueError):
        return pd.DataFrame(columns=colunas)
    linhas: list[dict[str, Any]] = []
    for dia in pd.date_range(ini, fim, freq="D"):
        cobrindo = no_periodo.loc[
            (no_periodo["_inicio"] <= dia) & (no_periodo["_fim"] >= dia)
        ]
        if not cobrindo.empty:
            linhas.append(
                {
                    "Data": dia,
                    "Ausências": int(len(cobrindo)),
                    "Técnicos": int(cobrindo["Login"].nunique()),
                }
            )
    return pd.DataFrame(linhas, columns=colunas)


# ============================================================
# 🗓️ BLOCO 3B: GRADE MENSAL (TÉCNICO × DIA)
# ============================================================
def abreviar_ausencia(tipo: Any) -> str:
    """Código curto da ausência na célula da grade (``Férias`` → ``FE``).

    Tipos fora do dicionário oficial usam as três primeiras letras
    (``Sinistro`` → ``SIN``); ``Outros`` vira ``OUT``.
    """
    canonico = _tipo_canonico(tipo)
    if not _texto(canonico):
        return ""
    if canonico in ABREVIACOES_AUSENCIA:
        return ABREVIACOES_AUSENCIA[canonico]
    chave = normalizar_chave(canonico)
    return chave[:3] or "?"


def codigo_para_tipo(valor: Any) -> str:
    """Tipo de ausência de uma célula da grade (``"FE"`` → ``"Férias"``).

    Devolve ``""`` para célula vazia, marca de presença (``P``/``OK``/
    ``PRESENTE``) ou número (contagens/horas não são ausência). Códigos
    desconhecidos com texto viram :data:`TIPO_OUTROS` — nada é descartado em
    silêncio.
    """
    texto = _texto(valor)
    if not texto:
        return ""
    chave = normalizar_chave(texto)
    if not chave or chave in MARCAS_PRESENCA or chave.isdigit():
        return ""
    if chave in CODIGOS_AUSENCIA:
        return CODIGOS_AUSENCIA[chave]
    for palavra, tipo in _PALAVRAS_TIPO:
        if palavra in chave:
            return tipo
    return TIPO_OUTROS


def tipos_do_codigo(valor: Any) -> list[str]:
    """Tipos de uma célula, aceitando combinações (``"FE/AT"`` → 2 tipos)."""
    texto = _texto(valor)
    if not texto:
        return []
    tipos: list[str] = []
    for parte in _RE_SEPARADOR_CODIGOS.split(texto):
        tipo = codigo_para_tipo(parte)
        if tipo and tipo not in tipos:
            tipos.append(tipo)
    return tipos


def _dia_do_cabecalho(valor: Any, referencia: date) -> date | None:
    """Data de um cabeçalho de dia (``1/nov.``, ``01/11``, ``2026-11-01``, ``1``).

    Sem ano explícito, usa o ano da referência — e o ano anterior quando o mês
    do cabeçalho é posterior ao da referência (planilha de dezembro aberta em
    janeiro). Cabeçalho que não é dia devolve ``None``.
    """
    if isinstance(valor, (pd.Timestamp, datetime, date)):
        try:
            return pd.Timestamp(valor).date()
        except (TypeError, ValueError):
            return None

    texto = _texto(valor)
    if not texto:
        return None

    match_iso = _RE_ISO_DIA.match(texto)
    if match_iso:
        try:
            return date(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
        except ValueError:
            return None

    match_numerico = _RE_DIA_MES_ANO.fullmatch(texto)
    match_nome = _RE_DIA_MES_NOME.fullmatch(texto)
    if match_numerico:
        dia, mes = int(match_numerico.group(1)), int(match_numerico.group(2))
        ano_txt = match_numerico.group(3)
    elif match_nome:
        dia = int(match_nome.group(1))
        mes = _MESES_POR_NOME.get(normalizar_chave(match_nome.group(2)).lower()[:3], 0)
        ano_txt = match_nome.group(3)
        if not mes:
            return None
    elif _RE_DIA_SOZINHO.fullmatch(texto):
        dia = int(texto)
        mes = referencia.month
        ano_txt = None
    else:
        return None

    ano = (
        int(ano_txt)
        if ano_txt
        else (referencia.year - 1 if mes > referencia.month else referencia.year)
    )
    if ano < 100:
        ano += 2000
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def detectar_colunas_dias(
    df: pd.DataFrame | None, referencia: Any = None
) -> dict[str, date]:
    """Colunas de dia de uma grade, na ordem cronológica (``{coluna: data}``).

    Exige :data:`MIN_COLUNAS_DIA` cabeçalhos válidos — uma aba de registros
    (com ``Data Início``) não é confundida com uma grade. A referência define
    mês/ano dos cabeçalhos sem ano; por padrão, hoje.
    """
    if df is None or not isinstance(df, pd.DataFrame) or not len(df.columns):
        return {}
    try:
        ref = pd.Timestamp(referencia).date() if referencia is not None else date.today()
    except (TypeError, ValueError):
        ref = date.today()

    encontrados: dict[str, date] = {}
    usados: set[date] = set()
    for coluna in df.columns:
        dia = _dia_do_cabecalho(coluna, ref)
        if dia is None or dia in usados:
            continue
        encontrados[coluna] = dia
        usados.add(dia)
    if len(encontrados) < MIN_COLUNAS_DIA:
        return {}
    return dict(sorted(encontrados.items(), key=lambda par: par[1]))


def normalizar_quadro_identidade(quadro: pd.DataFrame | None) -> pd.DataFrame:
    """Quadro no formato da grade: ``RE, Login, Técnico, Monitor, Base, U.N.``.

    Aceita a ``lista_ativos`` já normalizada (``LOGIN``/``TÉCNICO``...) ou a
    planilha crua com variações de caixa/acento. O ``Login`` é a identidade
    (normalizado por :func:`services.texto.normalizar_login`); sem coluna de
    login, o ``RE`` assume esse papel. Duplicidades ficam com a última linha.
    """
    colunas = list(COLUNAS_IDENTIDADE_GRADE)
    if quadro is None or not isinstance(quadro, pd.DataFrame) or quadro.empty:
        return pd.DataFrame({coluna: pd.Series(dtype="object") for coluna in colunas})

    base = quadro.copy()
    base.columns = base.columns.astype(str).str.strip()

    aliases: dict[str, tuple[str, ...]] = {
        "RE": ("RE", "MATRÍCULA", "MATRICULA"),
        "Login": ("LOGIN", "LOGIN DO TÉCNICO", "LOGIN DO TECNICO", "USUÁRIO", "USUARIO"),
        "Técnico": ("TÉCNICO", "TECNICO", "NOME", "COLABORADOR"),
        "Monitor": ("MONITOR", "GESTOR", "SUPERVISOR"),
        "Base": ("BASE", "REGIÃO", "REGIAO", "FILIAL"),
        "U.N.": (
            "U.N.",
            "UN",
            "UNIDADE",
            "UNIDADE DE NEGÓCIO",
            "UNIDADE DE NEGOCIO",
            "UNIDADE_NEGOCIO",
        ),
    }
    colunas_origem = {destino: buscar_coluna(base, nomes) for destino, nomes in aliases.items()}

    resultado = pd.DataFrame(index=base.index)
    if colunas_origem["RE"] is not None:
        resultado["RE"] = base[colunas_origem["RE"]].map(_identificador_grade)
    else:
        resultado["RE"] = ""

    if colunas_origem["Login"] is not None:
        resultado["Login"] = base[colunas_origem["Login"]].map(normalizar_login)
        if colunas_origem["RE"] is not None:
            # Linha sem login ainda tem identidade pelo RE.
            resultado["Login"] = resultado["Login"].where(
                resultado["Login"].ne(""), resultado["RE"].map(normalizar_login)
            )
    else:
        resultado["Login"] = resultado["RE"].map(normalizar_login)

    for coluna in ("Técnico", "Monitor", "Base", "U.N."):
        origem = colunas_origem[coluna]
        resultado[coluna] = base[origem].map(_texto) if origem is not None else ""

    resultado = resultado.loc[resultado["Login"].ne("")]
    return resultado.drop_duplicates(subset=["Login"], keep="last")


def _identificador_grade(valor: Any) -> str:
    """RE em texto, sem o ``.0`` que o Sheets acrescenta a números."""
    texto = _texto(valor)
    return texto[:-2] if re.fullmatch(r"\d+\.0", texto) else texto


def montar_matriz_ausencias(
    registros: pd.DataFrame | None,
    quadro: pd.DataFrame | None = None,
    *,
    inicio: Any = None,
    fim: Any = None,
    referencia: Any = None,
) -> pd.DataFrame:
    """Grade ``técnico × dia`` do período (``RE … U.N.``, dias e ``Total``).

    * as linhas vêm do quadro (quem não tem ausência também aparece, com a
      linha em branco); técnicos que só existem nos registros entram no fim;
    * cada célula recebe o código do tipo no dia (``F``, ``FE``, ``AT``…);
      mais de um tipo no mesmo dia vira ``AT/FE``;
    * registros cancelados não marcam nada;
    * ``Total`` = quantidade de dias com pelo menos uma marca.

    Sem ``inicio``/``fim``, usa o mês de ``referencia`` (hoje por padrão).
    As colunas de dia são objetos :class:`datetime.date`, não texto.
    """
    try:
        ref = pd.Timestamp(referencia).date() if referencia is not None else date.today()
    except (TypeError, ValueError):
        ref = date.today()
    try:
        dia_inicio = pd.Timestamp(inicio).date() if inicio is not None else ref.replace(day=1)
        dia_fim = pd.Timestamp(fim).date() if fim is not None else _ultimo_dia_do_mes(dia_inicio)
    except (TypeError, ValueError):
        dia_inicio, dia_fim = ref.replace(day=1), _ultimo_dia_do_mes(ref)
    if dia_fim < dia_inicio:
        dia_inicio, dia_fim = dia_fim, dia_inicio
    dias = [dia.date() for dia in pd.date_range(dia_inicio, dia_fim, freq="D")]

    identidade = normalizar_quadro_identidade(quadro)
    ativos = _ativos(registros)
    if not ativos.empty:
        for coluna in ("Técnico", "Monitor", "Base", "Tipo"):
            if coluna not in ativos.columns:
                ativos[coluna] = ""
        ativos = ativos.loc[
            (ativos["_inicio"].dt.date <= dia_fim) & (ativos["_fim"].dt.date >= dia_inicio)
        ].copy()
    if not ativos.empty:
        extras = ativos.sort_values("_inicio").drop_duplicates(subset=["Login"], keep="last")
        if not identidade.empty:
            extras = extras.loc[~extras["Login"].isin(identidade["Login"])]
        if not extras.empty:
            bloco = pd.DataFrame(
                {
                    "RE": "",
                    "Login": extras["Login"].to_numpy(),
                    "Técnico": extras["Técnico"].to_numpy(),
                    "Monitor": extras["Monitor"].to_numpy(),
                    "Base": extras["Base"].to_numpy(),
                    "U.N.": "",
                }
            )
            identidade = pd.concat([identidade, bloco], ignore_index=True)

    if identidade.empty:
        return pd.DataFrame(
            columns=[*COLUNAS_IDENTIDADE_GRADE, *dias, "Total"]
        )

    identidade = identidade.copy()
    identidade["_ordem_base"] = identidade["Base"].astype(str).str.upper()
    identidade["_ordem_monitor"] = identidade["Monitor"].astype(str).str.upper()
    identidade["_ordem_tecnico"] = identidade["Técnico"].astype(str).str.upper()
    identidade = identidade.sort_values(
        ["_ordem_base", "_ordem_monitor", "_ordem_tecnico", "Login"], kind="stable"
    ).drop(columns=["_ordem_base", "_ordem_monitor", "_ordem_tecnico"])

    marcas: dict[tuple[str, date], set[str]] = {}
    if not ativos.empty:
        for login, data_ini, data_fim, tipo in ativos[
            ["Login", "_inicio", "_fim", "Tipo"]
        ].itertuples(index=False, name=None):
            inicio_reg = max(pd.Timestamp(data_ini).date(), dia_inicio)
            fim_reg = min(pd.Timestamp(data_fim).date(), dia_fim)
            if fim_reg < inicio_reg:
                continue
            codigo = abreviar_ausencia(tipo)
            dia = inicio_reg
            while dia <= fim_reg:
                marcas.setdefault((str(login), dia), set()).add(codigo)
                dia += timedelta(days=1)

    linhas: list[dict[str, Any]] = []
    for _, pessoa in identidade.iterrows():
        login = str(pessoa["Login"])
        linha: dict[str, Any] = {coluna: pessoa[coluna] for coluna in COLUNAS_IDENTIDADE_GRADE}
        total = 0
        for dia in dias:
            codigos = sorted(marcas.get((login, dia), ()))
            linha[dia] = "/".join(codigos)
            total += 1 if codigos else 0
        linha["Total"] = total
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=[*COLUNAS_IDENTIDADE_GRADE, *dias, "Total"])


def normalizar_matriz_ausencias(
    bruto: pd.DataFrame | None, referencia: Any = None
) -> pd.DataFrame:
    """Converte uma aba em grade (técnico × dia) em registros de ausência.

    Cada sequência de dias consecutivos com o **mesmo** tipo vira um registro
    (``Data Início``/``Data Fim``); combinações como ``FE/AT`` geram um
    registro por tipo. Os registros recebem ``ID`` determinístico (``mapa-…``),
    ``Motivo = Importado da grade mensal`` e ficam ativos. Sem colunas de dia
    suficientes devolve :func:`registros_vazios` — a leitura de registros
    continua valendo.
    """
    if bruto is None or not isinstance(bruto, pd.DataFrame) or bruto.empty:
        return registros_vazios()

    base = bruto.copy()
    base.columns = base.columns.astype(str).str.strip()
    base = base.reset_index(drop=True)
    colunas_dias = detectar_colunas_dias(base, referencia)
    if not colunas_dias:
        return registros_vazios()

    identidade = normalizar_quadro_identidade(base)
    if identidade.empty:
        return registros_vazios()
    por_login = identidade.set_index("Login", drop=False)

    marcas: dict[tuple[str, str], list[date]] = {}
    for indice, pessoa in identidade.iterrows():
        login = str(pessoa["Login"])
        for coluna, dia in colunas_dias.items():
            for tipo in tipos_do_codigo(base.at[indice, coluna]):
                marcas.setdefault((login, tipo), []).append(dia)

    linhas: list[dict[str, Any]] = []
    for (login, tipo), datas in marcas.items():
        datas = sorted(set(datas))
        blocos: list[tuple[date, date]] = []
        inicio_bloco = fim_bloco = datas[0]
        for dia in datas[1:]:
            if (dia - fim_bloco).days == 1:
                fim_bloco = dia
            else:
                blocos.append((inicio_bloco, fim_bloco))
                inicio_bloco = fim_bloco = dia
        blocos.append((inicio_bloco, fim_bloco))
        pessoa = por_login.loc[login]
        for inicio_bloco, fim_bloco in blocos:
            linhas.append(
                {
                    "ID": (
                        f"mapa-{normalizar_chave(login)}-{inicio_bloco.isoformat()}-"
                        f"{abreviar_ausencia(tipo)}"
                    ),
                    "Login": login,
                    "Técnico": pessoa["Técnico"],
                    "Monitor": pessoa["Monitor"],
                    "Base": pessoa["Base"],
                    "Tipo": tipo,
                    "Data Início": inicio_bloco.isoformat(),
                    "Data Fim": fim_bloco.isoformat(),
                    "Justificativa": "Não se aplica",
                    "Motivo": "Importado da grade mensal",
                    "Status": STATUS_ATIVO,
                    "Registrado em": "",
                }
            )
    if not linhas:
        return registros_vazios()
    return normalizar_registros(pd.DataFrame(linhas))


def _ultimo_dia_do_mes(dia: date) -> date:
    """Último dia do mês de ``dia``."""
    return (dia.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)


# ============================================================
# 💾 BLOCO 4: LEITURA E GRAVAÇÃO NA PLANILHA
# ============================================================
def carregar_registros_com_origem(
    sheet_id: str | None = None,
    aba: str | None = None,
    *,
    ttl: int = 300,
) -> tuple[pd.DataFrame, bool]:
    """Lê o controle e informa se ele veio no formato de grade mensal.

    Devolve ``(registros, origem_grade)``. A aba pode estar em dois formatos:

    * **registros** (oficial) — ``Login``/``Data Início``/``Data Fim``...;
    * **grade** — ``RE, Login, Técnico, Monitor, Base, U.N.`` + uma coluna por
      dia (``1/nov.``, ``2/nov.``...). Nesse caso os registros são derivados
      por :func:`normalizar_matriz_ausencias` e ``origem_grade`` fica ``True``
      — quem for gravar precisa saber que a aba não pode ser substituída pelo
      formato longo sem apagar as colunas de dias.
    """
    from config.settings import SHEET_ABA_ABSENTEISMO, obter_sheet_id_ativos
    from services.google_drive_client import carregar_planilha_gsheets_csv

    sid = str(sheet_id or obter_sheet_id_ativos() or "").strip()
    if not sid:
        logger.warning("Sheet de ativos não configurado; controle de absenteísmo vazio.")
        return registros_vazios(), False
    try:
        bruto = carregar_planilha_gsheets_csv(
            sid,
            aba or SHEET_ABA_ABSENTEISMO,
            usar_cache=True,
            ttl=ttl,
            usar_conexao_streamlit=False,
        )
    except Exception:
        logger.warning("Falha ao ler o controle de absenteísmo (%s).", sid, exc_info=True)
        bruto = pd.DataFrame()

    registros = normalizar_registros(bruto)
    if registros.empty and isinstance(bruto, pd.DataFrame) and not bruto.empty:
        if detectar_colunas_dias(bruto):
            # Grade recém-criada pode estar toda em branco: a origem ainda é
            # grade (a gravação no formato longo apagaria as colunas de dias).
            derivados = normalizar_matriz_ausencias(bruto)
            logger.info(
                "controle_absenteismo no formato de grade: %d registro(s) derivados.",
                len(derivados),
            )
            return derivados, True
    return registros, False


def carregar_registros(
    sheet_id: str | None = None,
    aba: str | None = None,
    *,
    ttl: int = 300,
) -> pd.DataFrame:
    """Lê a aba ``controle_absenteismo`` (mesma planilha da ``lista_ativos``).

    Aceita registros ou grade mensal (ver :func:`carregar_registros_com_origem`).
    Aba inexistente/sem acesso devolve :func:`registros_vazios` — o painel
    abre vazio e a primeira gravação cria a aba com o cabeçalho oficial.
    """
    return carregar_registros_com_origem(sheet_id, aba, ttl=ttl)[0]


def _cliente_gspread() -> Any:
    """Cliente ``gspread`` pela conta de serviço dos secrets (import tardio)."""
    import streamlit as st

    secret_map = getattr(st, "secrets", {}).get("gcp_service_account", {})
    info = dict(secret_map) if isinstance(secret_map, dict) else dict(secret_map or {})
    if not info:
        raise RuntimeError(
            "Credenciais de escrita não configuradas: defina [gcp_service_account] "
            "nos secrets (mesma conta usada pela Gestão de Ativos)."
        )
    if "private_key" in info:
        info["private_key"] = str(info["private_key"]).replace("\\n", "\n")
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:  # pragma: no cover - ambiente sem gspread
        raise RuntimeError(f"gspread/google-auth não instalado: {exc}") from exc
    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


def _sanitizar_celula(valor: Any) -> str:
    """Neutraliza CSV injection (``=``, ``+``, ``-``, ``@``) ao gravar na planilha."""
    texto = _texto(valor)
    if texto[:1] in ("=", "+", "-", "@"):
        return "'" + texto
    return texto


def _df_para_planilha(df: pd.DataFrame) -> list[list[str]]:
    """Matriz de texto (cabeçalho + linhas) no formato de gravação da aba."""
    saida = df.copy()
    for coluna in COLUNAS_REGISTROS:
        if coluna not in saida.columns:
            saida[coluna] = ""
    saida = saida[list(COLUNAS_REGISTROS)]
    saida["Data Início"] = pd.to_datetime(df["_inicio"], errors="coerce").dt.strftime("%Y-%m-%d")
    saida["Data Fim"] = pd.to_datetime(df["_fim"], errors="coerce").dt.strftime("%Y-%m-%d")
    saida = saida.fillna("")
    linhas = [[_sanitizar_celula(c) for c in saida.columns]]
    linhas.extend([_sanitizar_celula(v) for v in linha] for linha in saida.itertuples(index=False))
    return linhas


def gravar_registros(df: pd.DataFrame, sheet_id: str | None = None) -> tuple[bool, str]:
    """Regrava a aba inteira (cria a aba com cabeçalho se ainda não existir).

    Devolve ``(True, "")`` em sucesso ou ``(False, motivo)`` — quem chama
    decide o fallback (ex.: manter o registro só na sessão e avisar).
    """
    from config.settings import SHEET_ABA_ABSENTEISMO, obter_sheet_id_ativos

    sid = str(sheet_id or obter_sheet_id_ativos() or "").strip()
    if not sid:
        return (False, "Planilha de ativos não configurada (SHEET_ID_ATIVOS).")
    try:
        cliente = _cliente_gspread()
        planilha = cliente.open_by_key(sid)
        try:
            aba_ws = planilha.worksheet(SHEET_ABA_ABSENTEISMO)
        except Exception as exc:
            import gspread

            if not isinstance(exc, gspread.WorksheetNotFound):
                raise
            aba_ws = planilha.add_worksheet(
                title=SHEET_ABA_ABSENTEISMO, rows=1000, cols=len(COLUNAS_REGISTROS)
            )
        dados = _df_para_planilha(df)
        from services.sincronizacao import substituir_celulas_atomico

        substituir_celulas_atomico(planilha, aba_ws, dados)
        return (True, "")
    except Exception as exc:  # noqa: BLE001 - motivo vai para a UI
        logger.warning("Falha ao gravar controle de absenteísmo: %s", exc)
        return (False, str(exc))


def registrar_ausencia(
    df_atual: pd.DataFrame, registro: dict[str, Any], sheet_id: str | None = None
) -> tuple[pd.DataFrame, bool, str]:
    """Anexa um registro e tenta persistir; devolve ``(novo_df, persistiu, motivo)``."""
    base = (
        df_atual.drop(columns=["_inicio", "_fim"], errors="ignore")
        if isinstance(df_atual, pd.DataFrame)
        else pd.DataFrame()
    )
    combinado = pd.concat([base, pd.DataFrame([registro])], ignore_index=True)
    novo = normalizar_registros(combinado)
    persistiu, motivo = gravar_registros(novo, sheet_id)
    return (novo, persistiu, motivo)


def registros_da_sessao(
    sheet_id: str | None = None,
    aba: str | None = None,
    *,
    ttl: int = 300,
    forcar: bool = False,
) -> pd.DataFrame:
    """Registros do controle compartilhados via ``st.session_state``."""
    import streamlit as st

    atual = st.session_state.get(CHAVE_SESSAO_REGISTROS)
    if forcar or not isinstance(atual, pd.DataFrame):
        atual, origem_grade = carregar_registros_com_origem(sheet_id, aba, ttl=ttl)
        st.session_state[CHAVE_SESSAO_REGISTROS] = atual
        st.session_state[CHAVE_SESSAO_ORIGEM_GRADE] = origem_grade
    return atual


def origem_grade_da_sessao() -> bool:
    """``True`` quando o controle lido está no formato de grade mensal.

    A aba em grade é somente leitura no painel: regravá-la no formato de
    registros apagaria as colunas de dias. A página usa esta flag para avisar
    e não oferecer o formulário/gravação.
    """
    import streamlit as st

    return bool(st.session_state.get(CHAVE_SESSAO_ORIGEM_GRADE, False))
