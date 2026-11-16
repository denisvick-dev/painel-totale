"""
services/absenteismo.py
=======================
Controle de ausências (faltas, folgas, férias, atestados...) do portal.

Versão: 1.0.0
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
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from services.datas import converter_serie_datas
from services.texto import buscar_coluna, normalizar_login

logger = logging.getLogger(__name__)

VERSAO_ABSENTEISMO = "1.0.0"

#: Chave dos registros do controle em ``st.session_state``.
CHAVE_SESSAO_REGISTROS = "totale_controle_absenteismo"

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
)

#: Tipos que costumam ser programados (agenda) — os demais são imprevistos.
TIPOS_PROGRAMADOS: tuple[str, ...] = ("Folga", "Férias", "Treinamento")

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
    "CHAVE_SESSAO_REGISTROS",
    "COLUNAS_REGISTROS",
    "JUSTIFICATIVAS",
    "STATUS_ATIVO",
    "STATUS_CANCELADO",
    "TIPOS_AUSENCIA",
    "TIPOS_PROGRAMADOS",
    "VERSAO_ABSENTEISMO",
    "agrupar_registros",
    "calcular_dias",
    "carregar_registros",
    "dias_no_periodo",
    "fase_do_registro",
    "filtrar_registros_periodo",
    "gravar_registros",
    "normalizar_registros",
    "registrar_ausencia",
    "registros_da_sessao",
    "registros_vazios",
    "resumir_controle",
    "serie_diaria_ausencias",
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
    return df.loc[df["Status"].ne(STATUS_CANCELADO)].copy()


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
# 💾 BLOCO 4: LEITURA E GRAVAÇÃO NA PLANILHA
# ============================================================
def carregar_registros(
    sheet_id: str | None = None,
    aba: str | None = None,
    *,
    ttl: int = 300,
) -> pd.DataFrame:
    """Lê a aba ``controle_absenteismo`` (mesma planilha da ``lista_ativos``).

    Aba inexistente/sem acesso devolve :func:`registros_vazios` — o painel
    abre vazio e a primeira gravação cria a aba com o cabeçalho oficial.
    """
    from config.settings import SHEET_ABA_ABSENTEISMO, obter_sheet_id_ativos
    from services.google_drive_client import carregar_planilha_gsheets_csv

    sid = str(sheet_id or obter_sheet_id_ativos() or "").strip()
    if not sid:
        logger.warning("Sheet de ativos não configurado; controle de absenteísmo vazio.")
        return registros_vazios()
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
    return normalizar_registros(bruto)


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
    saida["Data Início"] = pd.to_datetime(saida["_inicio"], errors="coerce").dt.strftime("%Y-%m-%d")
    saida["Data Fim"] = pd.to_datetime(saida["_fim"], errors="coerce").dt.strftime("%Y-%m-%d")
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
        except Exception:
            aba_ws = planilha.add_worksheet(
                title=SHEET_ABA_ABSENTEISMO, rows=1000, cols=len(COLUNAS_REGISTROS)
            )
        dados = _df_para_planilha(df)
        aba_ws.clear()
        if dados:
            aba_ws.update(values=dados, value_input_option="RAW")
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
        atual = carregar_registros(sheet_id, aba, ttl=ttl)
        st.session_state[CHAVE_SESSAO_REGISTROS] = atual
    return atual
