"""
dashboard_meta.py
=================
Dashboard de Metas Operacionais - TOTALE (v4.7.0)

Leitura do painel:
1. Faixa executiva: realizado, projeção e se o fechamento cabe na meta.
2. Abas operacionais: produção, consultivos, agrupamento, monitores e projeção por base.
3. Central de alertas calculada a partir dos dados.

Mudanças v4.7.0:
- Gauge semicircular "Projeção × Meta" ao lado da barra de progresso
  (Dashboard Kit), com semáforo por faixas de atingimento.
- Donut de participação por supervisor na aba Monitores (Top 8 com O.S.).
- Acabamento visual v2 aplicado globalmente pelo entrypoint (CSS Dashboard
  Kit: molduras em gráficos, abas pill, hover nos cards de KPI).

Mudanças v4.6.17:
- Motor de datas centralizado em services/datas.py: ISO e BR sem inversão.
- Janela temporal funciona mesmo quando uma fonte está vazia ou sem DATA.
- Seleção incompleta não é interpretada como um recorte de um dia.
- Filtros, diagnóstico, âncoras e exibição usam o mesmo parser.
- Regras comerciais de agrupamento, metas e projeção preservadas.
- Consultivos: agrupamento e projeções passam a seguir _PROJETO_NORM (projeto normalizado).
- Testes de tipagem e execução com dados simulados; validação de estado de widgets.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal, TypedDict
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

from services.datas import (
    converter_serie_datas,
    converter_serie_datas_mdy,
    data_ancora_projecao,
    detectar_coluna_data,
    garantir_datetime,
    garantir_datetime_auto,
    limites_datas_disponiveis,
    mascara_periodo,
    normalizar_janela_datas,
    validar_estado_janela,
)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator
else:
    try:
        from streamlit.delta_generator import DeltaGenerator
    except ImportError:
        DeltaGenerator = Any

#: Seções ancoradas do sumário (títulos usados em ``secao()``).
SECOES_PAGINA: tuple[str, ...] = (
    "Resumo Executivo",
    "Cenários de Fechamento",
    "Análise Detalhada por Frente",
)

TipoInsightType = Literal["ok", "info", "alerta", "critico", "acao"]
TemaKPIType = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"
]
TipoProgressBarType = Literal[
    "azul", "laranja", "verde", "vermelho", "roxo", "gradiente"
]

try:
    from components.componentes import (  # pyright: ignore[reportMissingImports]
        aplicar_estilo,
        render_empty_state,
        render_hero_totale_2,
        render_insight,
        render_kpi,
        render_metric_card,
        render_progress_bar,
        render_section_header,
        render_table_html,
    )
    from components.dashboard_kit import (  # pyright: ignore[reportMissingImports]
        grafico_donut,
        grafico_gauge_meta,
    )
    from components.dashboards import (  # pyright: ignore[reportMissingImports]
        abrir_dashboard,
        fechar_dashboard,
    )
    from components.layout_pagina import render_chips, render_sumario, secao
    from components.sidebar import (
        aplicar_sidebar_corp,
        render_page_sidebar_theme_selector,
        render_sidebar_brand,
        render_sidebar_divider,
        render_sidebar_footer_info,
        render_sidebar_info,
        render_sidebar_section,
        render_sidebar_spacer,
        render_sidebar_status,
    )
    from services.google_drive_client import carregar_planilha_gsheets_csv
    from services.texto import formatar_inteiro
    from services.texto import normalizar_texto as normalizar_texto_servico
except ImportError:

    def _noop(*args: Any, **kwargs: Any) -> None:
        pass

    def _fallback_kpi(
        container: Any,
        label: str,
        valor: str,
        sub: str = "",
        tema: str = "azul",
        icone: str = "",
        **kwargs: Any,
    ) -> None:
        container.metric(label, valor, help=sub or None)

    def _fallback_metric_card(
        container: Any,
        label: str,
        valor: str,
        trend: str = "none",
        trend_valor: str = "",
        sub: str = "",
        **kwargs: Any,
    ) -> None:
        container.metric(label, valor, delta=trend_valor or None, help=sub or None)

    def _fallback_section_header(*args: Any, **kwargs: Any) -> None:
        titulo = (
            kwargs.get("titulo")
            or kwargs.get("title")
            or (args[0] if args else "Seção")
        )
        st.subheader(str(titulo))

    def _fallback_progress(
        valor: float, maximo: float = 100.0, label: str = "", **kwargs: Any
    ) -> None:
        if label:
            st.caption(label)
        st.progress(max(0.0, min(valor / maximo, 1.0)) if maximo else 0.0)

    def _fallback_insight(
        msg: str = "", tipo: str = "info", titulo: str = "", **kwargs: Any
    ) -> None:
        texto = f"{titulo} — {msg}" if titulo else msg
        if tipo in ("alerta", "critico"):
            st.warning(texto)
        elif tipo == "ok":
            st.success(texto)
        else:
            st.info(texto)

    def _fallback_empty_state(**kwargs: Any) -> None:
        st.info(kwargs.get("titulo") or kwargs.get("descricao") or "Sem dados")

    def _fallback_hero(**kwargs: Any) -> None:
        st.title(kwargs.get("titulo", "Dashboard"))

    def _fallback_sidebar_section(*args: Any, **kwargs: Any) -> None:
        st.sidebar.header(args[0] if args else "")

    def _fallback_sidebar_status(**kwargs: Any) -> None:
        st.sidebar.success(kwargs.get("status", "OK"))

    def _fallback_table(df: pd.DataFrame, **kwargs: Any) -> None:
        st.dataframe(df, width="stretch")

    def _abrir_dashboard_fallback(
        titulo: str,
        *,
        secoes: Any = (),
        hero: Any = None,
        hero_kwargs: Any = None,
        chips: Any = None,
        **kwargs: Any,
    ) -> None:
        """Sem components.dashboards: herói + chips + sumário na ordem padrão."""
        if hero is not None:
            hero(**dict(hero_kwargs or {}))
        else:
            st.title(titulo)
        if chips:
            render_chips(chips)
        if secoes:
            render_sumario(list(secoes), titulo="Nesta página")

    def _grafico_indisponivel(*args: Any, **kwargs: Any) -> None:
        """Dashboard Kit ausente: a página segue sem os gráficos extras."""
        return None

    aplicar_estilo = _noop
    aplicar_sidebar_corp = _noop
    grafico_donut = _grafico_indisponivel
    grafico_gauge_meta = _grafico_indisponivel
    render_empty_state = _fallback_empty_state
    render_hero_totale_2 = _fallback_hero
    render_insight = _fallback_insight
    render_kpi = _fallback_kpi
    render_metric_card = _fallback_metric_card
    render_page_sidebar_theme_selector = _noop
    render_progress_bar = _fallback_progress
    render_section_header = _fallback_section_header
    render_sidebar_brand = _noop
    render_sidebar_divider = _noop
    render_sidebar_footer_info = _noop
    render_sidebar_info = _noop
    render_sidebar_section = _fallback_sidebar_section
    render_sidebar_spacer = _noop
    render_sidebar_status = _fallback_sidebar_status
    render_table_html = _fallback_table

    # Sem a camada compartilhada (services/) a página mantém o comportamento
    # antigo: normalização/formatação locais e leitura de planilha indisponível.
    import unicodedata as _unicodedata_fallback

    def _normalizar_texto_local(texto: Any) -> str:
        if _is_na_scalar(texto):
            return ""
        txt = str(texto).strip()
        return "".join(
            c
            for c in _unicodedata_fallback.normalize("NFD", txt)
            if _unicodedata_fallback.category(c) != "Mn"
        ).upper()

    def _formatar_inteiro_local(valor: Any) -> str:
        return f"{int(round(_to_float_safe(valor))):,}".replace(",", ".")

    def _planilha_indisponivel(*args: Any, **kwargs: Any) -> pd.DataFrame:
        return pd.DataFrame()

    abrir_dashboard = _abrir_dashboard_fallback
    carregar_planilha_gsheets_csv = _planilha_indisponivel
    fechar_dashboard = _noop
    formatar_inteiro = _formatar_inteiro_local
    normalizar_texto_servico = _normalizar_texto_local

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dashboard_meta")
st.set_page_config(
    page_title="Metas | TOTALE",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)
try:
    aplicar_estilo()
    aplicar_sidebar_corp()
except Exception as e:
    logger.warning("Estilização customizada falhou: %s", e)
render_page_sidebar_theme_selector()

VERSAO = "4.7.0"
ROTULOS_VAZIOS = {
    "",
    "NAN",
    "NAT",
    "NONE",
    "NA",
    "N/A",
    "NAO INFORMADO",
    "NULL",
    "<NA>",
}
MAPA_ALIAS_PROJETO: dict[str, str] = {
    "SAO PAULO": "NET-LESTE",
    "SÃO PAULO": "NET-LESTE",
    "SP": "NET-LESTE",
    "GUARULHOS": "NET-GUARULHOS",
    "GRU": "NET-GUARULHOS",
    "ABCDM": "NET-ABCDM",
    "ABC": "NET-ABCDM",
}


from config.settings import (
    FUSO_BR,
    URL_ATIVOS_BASE,
    obter_drive_id_cons,
    obter_sheet_id_ativos,
    obter_sheet_id_prod,
    url_gsheets_gviz_csv,
)
from config.settings import (
    SHEET_ABA_ATIVOS as _DEFAULT_ABA_ATIVOS,
)
from config.settings import (
    SHEET_ABA_PROD as _DEFAULT_ABA_PROD,
)
from config.settings import (
    obter_secret as _obter_secret,
)
from services.google_drive_client import baixar_arquivo_drive, criar_sessao_http


@dataclass
class Configuracoes:
    URL_ATIVOS: str = field(
        default_factory=lambda: _obter_secret("URL_ATIVOS", URL_ATIVOS_BASE)
    )
    SHEET_ID_ATIVOS: str = field(default_factory=obter_sheet_id_ativos)
    SHEET_ABA_ATIVOS: str = _DEFAULT_ABA_ATIVOS
    SHEET_ID_PROD: str = field(default_factory=obter_sheet_id_prod)
    SHEET_ABA_PROD: str = _DEFAULT_ABA_PROD
    DRIVE_ID_CONS: str = field(default_factory=obter_drive_id_cons)
    TIMEOUT: int = 60
    TZ: ZoneInfo = field(default_factory=lambda: FUSO_BR)
    CACHE_TTL_HIERARQUIA: int = 3600
    CACHE_TTL_CONSULTIVO: int = 600
    CACHE_TTL_PRODUCAO: int = 300


CFG = Configuracoes()
BASES_PRIORITARIAS = ("NET-ABCDM", "NET-LESTE", "NET-GUARULHOS")
PROJETOS_NET = ("NET-ABCDM", "NET-LESTE", "NET-LESTE VT", "NET-GUARULHOS", "NET-GRU VT")
METAS_PRODUCAO_OS_BASE = {"minima": 10_000, "meta_base": 11_000, "alta_perf": 12_000}
METAS_CONSULTIVO_BASE = {"minima": 400, "meta_base": 525, "alta_perf": 600}
METAS_PRODUCAO_OS_GERAL = {"minima": 30_000, "meta_base": 33_000, "alta_perf": 36_000}
METAS_CONSULTIVO_GERAL = {"minima": 1_200, "meta_base": 1_575, "alta_perf": 1_800}


@st.cache_resource
def http_session() -> requests.Session:
    return criar_sessao_http(user_agent=f"totale-dashboard/{VERSAO}")


@st.cache_data(show_spinner=False)
def converter_para_excel(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Relatorio")
    return output.getvalue()


def render_botao_exportacao(df: pd.DataFrame, nome_arquivo: str) -> None:
    if df.empty:
        st.warning("Sem dados para exportar.")
        return
    hoje_tz = datetime.now(CFG.TZ).date()
    st.download_button(
        label="📥 Exportar Excel",
        data=converter_para_excel(df),
        file_name=f"{nome_arquivo}_{hoje_tz.strftime('%d-%m-%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
        key=f"export_{nome_arquivo}",
    )


def _is_na_scalar(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, (float, int, np.number)):
        try:
            return bool(np.isnan(val))
        except TypeError:
            return False
    try:
        if isinstance(val, (str, bytes)):
            return val in ("", " ", "None", "NaN", "NA", "null", "NULL")
        return bool(pd.isna(val))
    except (TypeError, ValueError):
        return False


#: Normalização de texto delegada a :func:`services.texto.normalizar_texto`
#: (maiúscula, sem acentos e sem espaços sobrando — fonte única do portal).
normalizar_texto = normalizar_texto_servico


def _to_float_safe(value: Any, default: float = 0.0) -> float:
    if _is_na_scalar(value):
        return default
    try:
        val_float = float(value)
        return default if not np.isfinite(val_float) else val_float
    except (TypeError, ValueError):
        return default


def formatar_data_br(valor: Any, com_hora: bool = False) -> str:
    if _is_na_scalar(valor):
        return "-"
    ts = converter_serie_datas(pd.Series([valor], dtype=object)).iloc[0]
    if pd.isna(ts):
        return "-"
    return ts.strftime("%d-%m-%Y %H:%M" if com_hora else "%d-%m-%Y")


#: Inteiros em pt-BR delegados a :func:`services.texto.formatar_inteiro`.
_fmt_int = formatar_inteiro


def _fmt_dec(valor: Any, casas: int = 1) -> str:
    txt = f"{_to_float_safe(valor):,.{casas}f}"
    return txt.replace(",", "§").replace(".", ",").replace("§", ".")


def mapear_colunas(df: pd.DataFrame, regras: dict[str, list[str]]) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df_copia = df.copy()
    df_copia.columns = pd.Index([str(c).strip() for c in df_copia.columns])
    destino_para_origem: dict[str, str] = {}
    origem_usada: set[str] = set()
    colunas_norm = {str(c): normalizar_texto(c) for c in df_copia.columns}
    for destino, aliases in regras.items():
        for alias in [normalizar_texto(a) for a in aliases]:
            for orig, cn in colunas_norm.items():
                if orig not in origem_usada and cn == alias:
                    destino_para_origem[destino] = orig
                    origem_usada.add(orig)
                    break
            if destino in destino_para_origem:
                break
    if destino_para_origem:
        df_copia = df_copia.rename(
            columns={o: d for d, o in destino_para_origem.items()}
        )
    return df_copia.loc[:, ~df_copia.columns.duplicated(keep="first")].copy()


def garantir_login(df: pd.DataFrame, col: str = "LOGIN") -> pd.DataFrame:
    if col not in df.columns:
        return df.copy()
    df_copia = df.copy()
    texto = df_copia[col].astype(str).str.strip().str.upper()
    df_copia[col] = texto.mask(texto.isin({"NAN", "NONE", "N/A", "<NA>", "", "NA"}))
    return df_copia


@lru_cache(maxsize=16)
def _feriados_brasil(ano: int) -> tuple[date, ...]:
    # Calendário operacional original preservado, inclusive datas móveis.
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    ele = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ele) // 451
    mes = (h + ele - 7 * m + 114) // 31
    dia = ((h + ele - 7 * m + 114) % 31) + 1
    pascoa = date(ano, mes, dia)
    return tuple(
        sorted(
            {
                date(ano, 1, 1),
                date(ano, 4, 21),
                date(ano, 5, 1),
                date(ano, 9, 7),
                date(ano, 10, 12),
                date(ano, 11, 2),
                date(ano, 11, 15),
                date(ano, 11, 20),
                date(ano, 12, 25),
                pascoa - timedelta(48),
                pascoa - timedelta(47),
                pascoa - timedelta(2),
                pascoa + timedelta(60),
            }
        )
    )


def _busday_count(inicio: date, fim_inclusivo: date, feriados: tuple[date, ...]) -> int:
    if fim_inclusivo < inicio:
        return 0
    hol = np.array(
        [np.datetime64(str(d), "D") for d in feriados], dtype="datetime64[D]"
    )
    return int(
        np.busday_count(
            np.datetime64(str(inicio), "D"),
            np.datetime64(str(fim_inclusivo + timedelta(1)), "D"),
            weekmask="Mon Tue Wed Thu Fri Sat",
            holidays=hol,
        )
    )


class ResumoDiasUteis(TypedDict):
    inicio_mes: date
    fim_mes: date
    total_uteis: int
    uteis_decorridos: int
    uteis_restantes: int
    fator: float
    feriados_do_mes: tuple[date, ...]


@lru_cache(maxsize=256)
def resumo_dias_uteis_mes(data_referencia: date) -> ResumoDiasUteis:
    inicio_mes = data_referencia.replace(day=1)
    prox_mes = (data_referencia.replace(day=28) + timedelta(4)).replace(day=1)
    fim_mes = prox_mes - timedelta(1)
    feriados_ano = _feriados_brasil(data_referencia.year)
    feriados_mes = tuple(f for f in feriados_ano if f.month == data_referencia.month)
    total = _busday_count(inicio_mes, fim_mes, feriados_ano)
    decorridos = _busday_count(inicio_mes, data_referencia, feriados_ano)
    return {
        "inicio_mes": inicio_mes,
        "fim_mes": fim_mes,
        "total_uteis": total,
        "uteis_decorridos": decorridos,
        "uteis_restantes": max(0, total - decorridos),
        "fator": float(total / decorridos) if decorridos > 0 else 1.0,
        "feriados_do_mes": feriados_mes,
    }


@lru_cache(maxsize=256)
def _fator_por_data_max(data_max: date) -> tuple[float, int, int, int]:
    r = resumo_dias_uteis_mes(data_max)
    return r["fator"], r["uteis_restantes"], r["total_uteis"], r["uteis_decorridos"]


def fator_projecao(
    df: pd.DataFrame, coluna_data: str = "DATA"
) -> tuple[float, int, int, int]:
    ancora = data_ancora_projecao(df, coluna_data)
    return (1.0, 0, 0, 0) if ancora is None else _fator_por_data_max(ancora)


def calcular_atingimento_float(valor: Any, meta: float) -> float:
    v, m = _to_float_safe(valor), _to_float_safe(meta)
    return ((v / m) * 100.0) if m > 0 else 0.0


def calcular_atingimento_series(valor: pd.Series, meta: float) -> pd.Series:
    m = _to_float_safe(meta)
    if m <= 0.0:
        return pd.Series(0.0, index=valor.index, dtype=float)
    return (pd.to_numeric(valor, errors="coerce").fillna(0.0) / m) * 100.0


def classificar_semaforo(valor_projetado: Any, metas: dict[str, int]) -> str:
    valor = _to_float_safe(valor_projetado)
    if valor < metas["minima"]:
        return "🔴 Abaixo do mínimo"
    if valor < metas["meta_base"]:
        return "🟠 Entre mínimo e meta"
    return "🟢 Meta atingida"


def calcular_cenarios(
    realizado: Any, fator: float, variacao: float = 0.15
) -> dict[str, int]:
    real = max(0, int(round(_to_float_safe(realizado))))
    atual = max(real, int(real * max(_to_float_safe(fator), 0.0)))
    restante_projetado = max(atual - real, 0)
    return {
        "Conservador": int(round(real + restante_projetado * (1 - variacao))),
        "Atual": atual,
        "Otimista": int(round(real + restante_projetado * (1 + variacao))),
    }


def adicionar_cenarios_agrupados(
    df: pd.DataFrame,
    coluna_real: str,
    coluna_projetada: str,
    prefixo: str,
    variacao: float = 0.15,
) -> pd.DataFrame:
    restante_projetado = (df[coluna_projetada] - df[coluna_real]).clip(lower=0)
    df[f"{prefixo} Conservadora"] = (
        (df[coluna_real] + restante_projetado * (1 - variacao)).round().astype(int)
    )
    df[f"{prefixo} Otimista"] = (
        (df[coluna_real] + restante_projetado * (1 + variacao)).round().astype(int)
    )
    return df


def resolver_status_atingimento(
    valor: Any, metas: dict[str, int]
) -> tuple[str, TemaKPIType]:
    v = _to_float_safe(valor)
    if v >= metas["alta_perf"]:
        return "Alta Performance", "verde"
    if v >= metas["meta_base"]:
        return "Meta Atingida", "verde"
    if v >= metas["minima"]:
        return "Atenção / Mínimo", "laranja"
    return "Crítico / Abaixo", "vermelho"


def tema_kpi_de_valor(valor: Any, metas: dict[str, int]) -> TemaKPIType:
    _, tema = resolver_status_atingimento(valor, metas)
    if tema == "laranja":
        return "laranja"
    if tema == "vermelho":
        return "vermelho"
    return "verde"


def _ler_csv_bytes(conteudo: bytes) -> pd.DataFrame:
    if not conteudo or len(conteudo) < 10:
        raise ValueError("CSV vazio.")
    sep_char = max([b";", b",", b"\t", b"|"], key=conteudo[:4096].count).decode("utf-8")
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(
                io.BytesIO(conteudo),
                sep=sep_char,
                encoding=enc,
                dtype=str,
                low_memory=False,
                on_bad_lines="skip",
            )
            if not df.empty and len(df.columns) > 1:
                return df
        except Exception:
            continue
    raise ValueError("Falha ao decodificar.")


def _baixar_drive_csv(file_id: str) -> bytes:
    return baixar_arquivo_drive(file_id, sess=http_session(), timeout=CFG.TIMEOUT)


@st.cache_data(ttl=CFG.CACHE_TTL_HIERARQUIA, show_spinner="Carregando Hierarquia...")
def _carregar_hierarquia_com_projeto() -> pd.DataFrame:
    """Lista de ativos com a coluna extra ``PROJETO`` que este painel agrupa.

    O download passa pela camada compartilhada
    (:func:`services.google_drive_client.carregar_planilha_gsheets_csv`, com
    cache em disco e fallbacks de URL); o ``GSheetsConnection`` fica só como
    último recurso. O mapeamento continua local porque esta página precisa de
    ``PROJETO``, coluna que a hierarquia canônica do portal não carrega.
    """
    df = pd.DataFrame()
    try:
        bruto = carregar_planilha_gsheets_csv(
            CFG.SHEET_ID_ATIVOS,
            CFG.SHEET_ABA_ATIVOS,
            usar_cache=True,
            ttl=CFG.CACHE_TTL_HIERARQUIA,
        )
        if isinstance(bruto, pd.DataFrame) and not bruto.empty:
            df = bruto
    except Exception:
        logger.warning("Leitura compartilhada da hierarquia falhou.", exc_info=True)
    if df.empty:
        try:
            from streamlit_gsheets import GSheetsConnection

            conn = st.connection("gsheets", type=GSheetsConnection)
            df_temp = conn.read(
                spreadsheet=CFG.URL_ATIVOS, worksheet=CFG.SHEET_ABA_ATIVOS, ttl=0
            )
            if isinstance(df_temp, pd.DataFrame) and not df_temp.empty:
                df = df_temp
        except Exception:
            logger.warning("Hierarquia indisponível também via conexão Streamlit.")
    if df.empty:
        return pd.DataFrame()
    df = mapear_colunas(
        df,
        {
            "LOGIN": ["LOGIN", "USER", "USUARIO", "MATRICULA", "ID", "RE"],
            "TECNICO": [
                "TECNICO",
                "NOME",
                "COLABORADOR",
                "NOME TÉCNICO",
                "FUNCIONARIO",
            ],
            "MONITOR": ["MONITOR", "SUPERVISOR", "GESTOR", "LIDER", "COORDENADOR"],
            "BASE": ["BASE", "FILIAL", "REGIONAL", "REGIÃO", "CIDADE", "LOCAL"],
            "PROJETO": ["PROJETO", "CONTRATO", "CAMPANHA", "OPERACAO", "CLIENTE"],
        },
    )
    for col in ["LOGIN", "TECNICO", "MONITOR", "BASE", "PROJETO"]:
        if col not in df.columns:
            df[col] = "Não Informado"
    df = garantir_login(df).dropna(subset=["LOGIN"])
    df = df[df["LOGIN"].astype(str).str.strip() != ""]
    df = add_norm_cols(df)
    if "_LOGIN_NORM" in df.columns:
        df = df[df["_LOGIN_NORM"].str.strip() != ""].copy()
        return df.drop_duplicates(subset=["_LOGIN_NORM"], keep="last").reset_index(
            drop=True
        )
    return df.drop_duplicates(subset=["LOGIN"], keep="last").reset_index(drop=True)


@st.cache_data(ttl=CFG.CACHE_TTL_CONSULTIVO, show_spinner="Baixando Consultivos...")
def carregar_consultivos(
    cache_version: str = VERSAO,
) -> tuple[pd.DataFrame, str | None]:
    try:
        df = _ler_csv_bytes(_baixar_drive_csv(CFG.DRIVE_ID_CONS))
        if df.empty:
            return pd.DataFrame(), "Arquivo de Consultivos vazio."
        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_CRIACAO",
                    "DATA_FINALIZACAO",
                    "DT_FINALIZACAO",
                    "DATA_CONSULTIVO",
                    "DATE",
                    "DATA_ATENDIMENTO",
                    "DATA_SOLICITACAO",
                    "DATA_ABERTURA",
                    "DATA HORA",
                    "DATA/HORA",
                    "CREATED_AT",
                    "TIMESTAMP",
                ],
                "LOGIN": [
                    "LOGIN NETSALES",
                    "LOGIN",
                    "USUARIO",
                    "MATRICULA",
                    "USER",
                    "ID_TECNICO",
                ],
                "PROJETO": [
                    "PROJETO",
                    "CONTRATO",
                    "PROJECT",
                    "CANAL",
                    "OPERACAO",
                    "CAMPANHA",
                ],
                "BASE": [
                    "BASE",
                    "FILIAL",
                    "REGIONAL",
                    "REGION",
                    "CIDADE",
                    "LOCALIDADE",
                ],
                "TECNICO": ["TECNICO", "NOME", "TECHNICIAN", "NOME_TECNICO"],
                "MONITOR": ["MONITOR", "SUPERVISOR", "MANAGER", "LIDER", "COORDENADOR"],
            },
        )
        col_data_detectada = detectar_coluna_data(df)
        if col_data_detectada is None:
            return pd.DataFrame(), "Coluna DATA não encontrada em Consultivos."
        if col_data_detectada != "DATA":
            df = df.rename(columns={col_data_detectada: "DATA"})
        df = garantir_datetime_auto(df, col="DATA", nome_fonte="Consultivos")
        if df["DATA"].isna().all():
            return pd.DataFrame(), "Todas as datas são inválidas em Consultivos."
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Consultivos: {type(e).__name__} - {e!s}"


@st.cache_data(ttl=CFG.CACHE_TTL_PRODUCAO, show_spinner="Lendo Produção...")
def carregar_producao(cache_version: str = VERSAO) -> tuple[pd.DataFrame, str | None]:
    try:
        resp = http_session().get(
            url_gsheets_gviz_csv(CFG.SHEET_ID_PROD, sheet=CFG.SHEET_ABA_PROD),
            timeout=CFG.TIMEOUT,
        )
        resp.raise_for_status()
        if "<!doctype html" in resp.text.lower()[:1000]:
            return pd.DataFrame(), "Acesso negado à planilha de produção."
        df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
        if df.empty:
            return pd.DataFrame(), "Planilha de Produção está vazia."
        df = mapear_colunas(
            df,
            {
                "DATA": [
                    "DATA",
                    "DT_EXECUCAO",
                    "DATA_EXECUCAO",
                    "DATA_FINALIZACAO",
                    "DATA CONCLUSAO",
                    "Date",
                    "DATA_OS",
                ],
                "LOGIN": [
                    "LOGIN",
                    "MATRICULA",
                    "CÓD.EQUIPE",
                    "COD_EQUIPE",
                    "User",
                    "ID_TECNICO",
                ],
                "NUM_OS": ["NUM_OS", "NUMERO_OS", "OS", "ORDEM_SERVICO", "ID"],
                "PROJETO": [
                    "PROJETO",
                    "CAMPANHA",
                    "OPERACAO",
                    "Project",
                    "CONTRATO",
                    "CLIENTE",
                    "COD_PROJETO",
                ],
                "BASE": ["BASE", "FILIAL", "Region", "CIDADE", "LOCAL", "REGIÃO"],
                "TECNICO": [
                    "NOME EQUIPE",
                    "TECNICO",
                    "NOME",
                    "Technician",
                    "COLABORADOR",
                ],
                "MONITOR": ["MONITOR", "SUPERVISOR", "Manager", "GESTOR", "LIDER"],
            },
        )
        col_data_detectada = detectar_coluna_data(df)
        if col_data_detectada is None:
            return pd.DataFrame(), "Coluna DATA não encontrada na planilha de produção."
        if col_data_detectada != "DATA":
            df = df.rename(columns={col_data_detectada: "DATA"})
        # CSV de Produção confirmado como MM/DD/AAAA; converter antes do parser BR.
        df["DATA"] = converter_serie_datas_mdy(df["DATA"])
        if df["DATA"].isna().all():
            return pd.DataFrame(), "Datas inválidas na planilha de produção."
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Produção: {type(e).__name__} - {e!s}"


def add_norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df_copia = df.copy()
    for src, dst in (
        ("BASE", "_BASE_NORM"),
        ("LOGIN", "_LOGIN_NORM"),
        ("TECNICO", "_TECNICO_NORM"),
        ("PROJETO", "_PROJETO_NORM"),
        ("MONITOR", "_MONITOR_NORM"),
    ):
        if src in df_copia.columns:
            df_copia[dst] = (
                df_copia[src]
                .astype(str)
                .map(normalizar_texto)
                .replace(
                    ["", "NAN", "NONE", "NA", "NÃO INFORMADO", "NAO INFORMADO"], ""
                )
            )
        else:
            df_copia[dst] = ""
    return df_copia


def garantir_projeto_de_base(df: pd.DataFrame) -> pd.DataFrame:
    """Preenche projeto vazio a partir da base e mantém o mapeamento original."""
    if df.empty or "BASE" not in df.columns:
        return df.copy()
    df_out = df.copy()
    if "PROJETO" not in df_out.columns:
        df_out["PROJETO"] = df_out["BASE"]
    else:
        mask_vazio = (
            df_out["PROJETO"]
            .astype(str)
            .map(normalizar_texto)
            .isin(ROTULOS_VAZIOS | {"NAO INFORMADO", "NÃO INFORMADO"})
        )
        df_out.loc[mask_vazio, "PROJETO"] = df_out.loc[mask_vazio, "BASE"]
    for alias, proj_oficial in MAPA_ALIAS_PROJETO.items():
        m_alias = (df_out["PROJETO"].astype(str).map(normalizar_texto) == alias) | (
            df_out["BASE"].astype(str).map(normalizar_texto) == alias
        )
        df_out.loc[m_alias, "PROJETO"] = proj_oficial
    projeto_norm = df_out["PROJETO"].astype(str).map(normalizar_texto)
    if "_PROJETO_NORM_ATIVOS" in df_out.columns:
        projeto_norm_ativos = df_out["_PROJETO_NORM_ATIVOS"].astype(str).map(
            normalizar_texto
        )
        projeto_ativos_valido = ~projeto_norm_ativos.isin(
            ROTULOS_VAZIOS | {"NAO INFORMADO", "NÃO INFORMADO"}
        )
        projeto_norm = projeto_norm_ativos.where(
            projeto_ativos_valido, projeto_norm
        )
        df_out = df_out.drop(columns=["_PROJETO_NORM_ATIVOS"])
    df_out["_PROJETO_NORM"] = projeto_norm
    if "_BASE_NORM" not in df_out.columns:
        df_out["_BASE_NORM"] = df_out["BASE"].astype(str).map(normalizar_texto)
    return df_out


def _isin_norm(serie: pd.Series, valores: list[str]) -> pd.Series:
    alvos = {normalizar_texto(v) for v in valores if v is not None}
    return serie.astype(str).map(normalizar_texto).isin(alvos)


def _match_base_ou_projeto(df: pd.DataFrame, valores: list[str]) -> pd.Series:
    alvos = [
        normalizar_texto(v) for v in valores if v is not None and not _is_na_scalar(v)
    ]
    alvos_set = set(alvos)
    masks = []
    for coluna in ("BASE", "PROJETO"):
        if coluna not in df.columns:
            continue
        s_norm = df[coluna].map(
            lambda v: normalizar_texto(v) if not _is_na_scalar(v) else ""
        )
        exato = s_norm.isin(alvos_set)
        fuzzy = s_norm.map(
            lambda v: (
                isinstance(v, str)
                and bool(v)
                and v not in ROTULOS_VAZIOS
                and any(
                    isinstance(t, str)
                    and bool(t)
                    and t not in ROTULOS_VAZIOS
                    and (t == v or t in v or v in t)
                    for t in alvos
                )
            )
        )
        masks.append(exato | fuzzy)
    if not masks:
        return pd.Series(True, index=df.index)
    out = masks[0]
    for m in masks[1:]:
        out = out | m
    return out


def enriquecer_dados_completos(
    df: pd.DataFrame, hierarquia: pd.DataFrame
) -> pd.DataFrame:
    """A hierarquia preenche apenas os campos originalmente vazios."""
    if df.empty:
        return add_norm_cols(df)
    if hierarquia.empty:
        resultado = df.copy()
        for coluna in ("BASE", "PROJETO", "MONITOR", "TECNICO"):
            if coluna not in resultado.columns:
                resultado[coluna] = "Não Informado"
        return add_norm_cols(resultado)
    df_resultado = add_norm_cols(df)
    hierarquia_copia = garantir_projeto_de_base(add_norm_cols(hierarquia.copy()))
    mask_valida = hierarquia_copia["_LOGIN_NORM"].notna() & (
        hierarquia_copia["_LOGIN_NORM"] != ""
    )
    hierarquia_valida = hierarquia_copia.loc[mask_valida].drop_duplicates(
        subset=["_LOGIN_NORM"], keep="first"
    )
    if hierarquia_valida.empty:
        return df_resultado
    cols = ["_LOGIN_NORM"] + [
        c
        for c in ["BASE", "PROJETO", "MONITOR", "TECNICO", "_PROJETO_NORM"]
        if c in hierarquia_valida.columns
    ]
    lookup = hierarquia_valida[cols].rename(
        columns={
            c: ("_PROJETO_NORM_ATIVOS" if c == "_PROJETO_NORM" else f"{c}_SRC")
            for c in cols
            if c != "_LOGIN_NORM"
        }
    )
    df_resultado = pd.merge(df_resultado, lookup, on="_LOGIN_NORM", how="left")
    for col in ["BASE", "PROJETO", "MONITOR", "TECNICO"]:
        src = f"{col}_SRC"
        if src in df_resultado.columns:
            if col not in df_resultado.columns:
                df_resultado[col] = None
            vazio = df_resultado[col].isna() | df_resultado[col].astype(str).map(
                normalizar_texto
            ).isin(ROTULOS_VAZIOS | {"NAO INFORMADO", "NÃO INFORMADO"})
            df_resultado.loc[vazio, col] = df_resultado.loc[vazio, src]
            df_resultado = df_resultado.drop(columns=[src])
    if "_PROJETO_NORM_ATIVOS" in df_resultado.columns:
        projeto_norm_ativos = df_resultado["_PROJETO_NORM_ATIVOS"].astype(str).map(
            normalizar_texto
        )
        projeto_ativos_valido = ~projeto_norm_ativos.isin(
            ROTULOS_VAZIOS | {"NAO INFORMADO", "NÃO INFORMADO"}
        )
        projeto_norm = df_resultado["PROJETO"].astype(str).map(normalizar_texto)
        df_resultado["_PROJETO_NORM"] = projeto_norm_ativos.where(
            projeto_ativos_valido, projeto_norm
        )
    for col in ["BASE", "PROJETO", "MONITOR", "TECNICO"]:
        if col in df_resultado.columns:
            df_resultado[f"_{col}_NORM"] = (
                df_resultado[col].astype(str).map(normalizar_texto)
            )
            df_resultado[col] = df_resultado[col].fillna("Não Informado")
    return df_resultado


def contar_tecnicos_validos(serie: pd.Series) -> int:
    norm = serie.astype(str).map(normalizar_texto)
    return int(norm[~norm.isin(ROTULOS_VAZIOS)].nunique())


def percentual_sem_vinculo(df: pd.DataFrame, coluna: str) -> tuple[int, float]:
    if df.empty or coluna not in df.columns:
        return 0, 0.0
    norm = df[coluna].astype(str).map(normalizar_texto)
    sem = int(norm.isin(ROTULOS_VAZIOS).sum())
    return sem, sem / len(df) * 100.0


def duplicatas_os(df: pd.DataFrame) -> int:
    if df.empty or "NUM_OS" not in df.columns:
        return 0
    serie = df["NUM_OS"].astype(str).str.strip()
    serie = serie[~serie.map(normalizar_texto).isin(ROTULOS_VAZIOS)]
    return int(serie.duplicated().sum())


def diagnosticar_perda_filtros(df: pd.DataFrame, label: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            {
                "Etapa": ["vazio"],
                "Linhas que restam": [0],
                "Eliminadas nesta etapa": [0],
            }
        )
    rows = [("1. Entrada (após enriquecimento)", len(df), 0)]
    mask = pd.Series(True, index=df.index)
    # Mesma lógica OR entre base e projeto usada em filtrar_dataframe.
    if filtro_base or filtro_projeto:
        m = _mascara_filtros_operacionais(
            df, eh_consultivo=normalizar_texto(label) == "CONSULTIVOS"
        )
        perda = int((mask & ~m).sum())
        mask &= m
        rows.append(
            (
                "2–4. Após BASE/PROJETO/MONITOR (mesma regra do filtro)",
                int(mask.sum()),
                perda,
            )
        )
    elif filtro_monitor and "MONITOR" in df.columns:
        m = _isin_norm(df["MONITOR"], filtro_monitor)
        perda = int((mask & ~m).sum())
        mask &= m
        rows.append(("3. Após filtro MONITOR", int(mask.sum()), perda))
    if _filtro_datas_safe and "DATA" in df.columns:
        inicio, fim = _filtro_datas_safe
        sdt = converter_serie_datas(df["DATA"])
        m = mascara_periodo(df["DATA"], inicio, fim)
        perda = int((mask & ~m).sum())
        mask &= m
        rows.append(("5. Após filtro DATA", int(mask.sum()), perda))
        validas = sdt.dropna()
        if not validas.empty:
            rows.append(
                (
                    f"   ↳ datas na fonte: {formatar_data_br(validas.min())} → {formatar_data_br(validas.max())}",
                    len(validas),
                    0,
                )
            )
            rows.append(
                (
                    f"   ↳ janela do filtro: {formatar_data_br(inicio)} → {formatar_data_br(fim)}",
                    0,
                    0,
                )
            )
        rows.append(("   ↳ datas inválidas/vazias na fonte", int(sdt.isna().sum()), 0))
    return pd.DataFrame(
        rows, columns=["Etapa", "Linhas que restam", "Eliminadas nesta etapa"]
    )


def render_tabela_segura(df: pd.DataFrame, **kwargs: Any) -> None:
    df_display = df.copy()
    if df_display.empty:
        render_table_html(df_display, **kwargs)
        return
    for col in df_display.columns:
        nome = normalizar_texto(col)
        eh_data = (
            nome in {"DATA", "DATE", "DATA/HORA", "DATA HORA"}
            or nome.startswith(("DATA_", "DATA "))
            or nome.endswith("_DATA")
        )
        if not eh_data:
            continue
        serie = garantir_datetime(df_display[[col]], col=col, origem="Tabela")[col]
        validas = serie.dropna()
        tem_hora = (
            bool(
                (
                    validas.dt.hour.ne(0)
                    | validas.dt.minute.ne(0)
                    | validas.dt.second.ne(0)
                ).any()
            )
            if not validas.empty
            else False
        )
        df_display[col] = serie.dt.strftime(
            "%d-%m-%Y %H:%M" if tem_hora else "%d-%m-%Y"
        ).fillna("-")
    try:
        render_table_html(df_display, **kwargs)
    except TypeError:
        for chave in ("color_rules", "colunas_num", "alinhamentos"):
            kwargs.pop(chave, None)
        render_table_html(df_display, **kwargs)


def render_resumo_cards(
    *,
    titulo: str,
    icone: str,
    realizado: float,
    projetado: float,
    meta: float,
    faltantes: float,
    media_diaria: float,
    dias_restantes: int,
    tema_progresso: TipoProgressBarType,
    label_realizado: str,
    label_projetado: str,
    label_meta: str,
    label_faltantes: str,
    metas: dict[str, int] | None = None,
    tecnico_dia: float | None = None,
    ancora: date | None = None,
) -> None:
    subtitulo = (
        "Realizado, projeção de fechamento e ritmo necessário (Meta − Realizado)"
    )
    if ancora is not None:
        subtitulo += f" • projeção ancorada em {formatar_data_br(ancora)}"
    render_section_header(titulo=titulo, icone=icone, subtitulo=subtitulo)
    pct_real = calcular_atingimento_float(realizado, meta)
    pct_proj = calcular_atingimento_float(projetado, meta)
    tema_proj: TemaKPIType = (
        tema_kpi_de_valor(projetado, metas)
        if metas
        else ("verde" if projetado >= meta else "vermelho")
    )
    status = (
        resolver_status_atingimento(projetado, metas)[0]
        if metas
        else ("Meta Atingida" if projetado >= meta else "Abaixo da meta")
    )
    col_kpis, col_gauge = st.columns([5, 2], gap="large")
    with col_kpis:
        c1, c2, c3 = st.columns(3, gap="medium")
        render_kpi(
            c1,
            label=label_realizado,
            valor=_fmt_int(realizado),
            sub=(
                f"{pct_real:.1f}% da meta mensal"
                if ancora is not None
                else "Sem dados no recorte"
            ),
            tema="azul",
            icone="✅",
        )
        render_kpi(
            c2,
            label=label_projetado,
            valor=_fmt_int(projetado) if ancora is not None else "—",
            sub=(
                f"{status} • {pct_proj:.1f}% da meta"
                if ancora is not None
                else "Projeção indisponível: sem dados"
            ),
            tema=tema_proj if ancora is not None else "cinza",
            icone="📈",
        )
        render_kpi(
            c3,
            label=label_meta,
            valor=_fmt_int(meta),
            sub="Meta mensal estabelecida",
            tema="laranja",
            icone="🎯",
        )
        render_progress_bar(
            valor=float(realizado),
            maximo=float(meta) if meta > 0 else 1.0,
            label=f"Progresso Realizado × Meta ({titulo})",
            mostrar_valor=True,
            tema=tema_progresso,
            altura="medio",
        )
        if ancora is not None and dias_restantes > 0:
            cols = st.columns(3 if tecnico_dia is not None else 2, gap="medium")
            gap = _to_float_safe(faltantes)
            render_kpi(
                cols[0],
                label="EXCEDENTE" if gap <= 0 else label_faltantes,
                valor=_fmt_int(abs(gap)),
                sub="Realizado já cobre a meta" if gap <= 0 else "Meta − Realizado",
                tema="verde" if gap <= 0 else "vermelho",
                icone="✅" if gap <= 0 else "⚠️",
            )
            render_kpi(
                cols[1],
                label="MÉDIA DIÁRIA NECESSÁRIA",
                valor=_fmt_dec(max(media_diaria, 0.0)),
                sub=f"{dias_restantes} dias úteis restantes (seg–sáb)",
                tema="roxo",
                icone="📅",
            )
            if tecnico_dia is not None:
                render_kpi(
                    cols[2],
                    label="MÉDIA POR TÉCNICO / DIA",
                    valor=_fmt_dec(max(tecnico_dia, 0.0)),
                    sub="Distribuição pelo número informado",
                    tema="cinza",
                    icone="👨‍🔧",
                )
    with col_gauge:
        if ancora is not None:
            fig_gauge = grafico_gauge_meta(
                pct_proj,
                valor_rotulo=f"Projeção × Meta — {titulo}",
                altura=250,
            )
            if fig_gauge is not None:
                st.plotly_chart(fig_gauge, width="stretch")
        else:
            st.caption("Gauge de projeção indisponível sem datas no recorte.")
    if ancora is None:
        render_insight(
            f"Sem datas válidas no recorte de {titulo.lower()} para calcular a projeção.",
            tipo="info",
        )
        return
    if dias_restantes <= 0:
        render_insight(
            f"Período de dias úteis encerrado para {titulo.lower()}.", tipo="info"
        )
        return


def coletar_alertas(
    df_prod_raw: pd.DataFrame,
    df_cons_raw: pd.DataFrame,
    df_cons_filtrado: pd.DataFrame,
    resumo: pd.DataFrame,
    erro_prod: str | None,
    erro_cons: str | None,
    hoje: date,
) -> list[tuple[str, TipoInsightType]]:
    alertas: list[tuple[str, TipoInsightType]] = []
    if erro_prod:
        alertas.append((f"Carga de produção falhou: {erro_prod}", "critico"))
    if erro_cons:
        alertas.append((f"Carga de consultivos falhou: {erro_cons}", "critico"))
    if df_cons_raw.empty and not erro_cons:
        alertas.append(
            ("Consultivos: arquivo carregado mas sem linhas úteis.", "critico")
        )
    elif not df_cons_raw.empty and df_cons_filtrado.empty:
        alertas.append(
            (
                f"Consultivos: {_fmt_int(len(df_cons_raw))} linhas carregadas, mas o filtro atual eliminou todas.",
                "alerta",
            )
        )
    ancoras = [
        d
        for d in (data_ancora_projecao(df_prod_raw), data_ancora_projecao(df_cons_raw))
        if d is not None
    ]
    if ancoras:
        mais_atrasada = min(ancoras)
        atraso = (hoje - mais_atrasada).days
        if atraso >= 2:
            alertas.append(
                (
                    f"Fonte desatualizada: a última data é {formatar_data_br(mais_atrasada)} ({atraso} dias atrás).",
                    "alerta",
                )
            )
    elif df_prod_raw.empty and df_cons_raw.empty:
        alertas.append(
            ("Nenhuma linha de produção ou consultivo recebida das fontes.", "critico")
        )
    for nome, df in (("produção", df_prod_raw), ("consultivos", df_cons_raw)):
        sem_tec, pct_tec = percentual_sem_vinculo(df, "TECNICO")
        sem_base, pct_base = percentual_sem_vinculo(df, "BASE")
        if pct_tec >= 2:
            alertas.append(
                (
                    f"{_fmt_int(sem_tec)} registros de {nome} ({pct_tec:.1f}%) sem técnico na hierarquia.",
                    "alerta",
                )
            )
        if pct_base >= 2:
            alertas.append(
                (
                    f"{_fmt_int(sem_base)} registros de {nome} ({pct_base:.1f}%) sem base vinculada.",
                    "alerta",
                )
            )
        if "DATA" in df.columns and not df.empty:
            invalidas = int(converter_serie_datas(df["DATA"]).isna().sum())
            if invalidas:
                alertas.append(
                    (
                        f"{_fmt_int(invalidas)} registros de {nome} com DATA inválida/vazia; excluídos do filtro temporal.",
                        "alerta",
                    )
                )
            ancora = data_ancora_projecao(df)
            if ancora is not None and ancora > hoje:
                alertas.append(
                    (
                        f"{nome.capitalize()}: há datas futuras até {formatar_data_br(ancora)}. Confira a fonte.",
                        "alerta",
                    )
                )
    dups = duplicatas_os(df_prod_raw)
    if dups > 0:
        alertas.append(
            (
                f"{_fmt_int(dups)} linhas de produção repetem NUM_OS. Contagem de linhas preservada.",
                "info",
            )
        )
    if not resumo.empty and "Agrupamento" in resumo.columns:
        acompanhados = {
            normalizar_texto(x) for x in (*BASES_PRIORITARIAS, *PROJETOS_NET)
        }
        for _, row in resumo.iterrows():
            nome = str(row.get("Agrupamento", "—"))
            if normalizar_texto(nome) not in acompanhados:
                continue
            for real_col, proj_col, metas, indicador in (
                ("OS_Volume", "O.S. Projetadas", METAS_PRODUCAO_OS_BASE, "O.S."),
                (
                    "Cons_Volume",
                    "Consultivos Projetados",
                    METAS_CONSULTIVO_BASE,
                    "consultivos",
                ),
            ):
                if _to_float_safe(row.get(real_col)) > 0:
                    proj = _to_float_safe(row.get(proj_col))
                    if proj < metas["minima"]:
                        alertas.append(
                            (
                                f"{nome}: projeção de {indicador} abaixo do mínimo.",
                                "critico",
                            )
                        )
                    elif proj < metas["meta_base"]:
                        alertas.append(
                            (
                                f"{nome}: projeção de {indicador} abaixo da meta.",
                                "alerta",
                            )
                        )
        presentes = {normalizar_texto(x) for x in resumo["Agrupamento"].astype(str)}
        for base in BASES_PRIORITARIAS:
            if normalizar_texto(base) not in presentes:
                alertas.append(
                    (f"{base} não aparece no agrupamento deste recorte.", "info")
                )
    return alertas


df_hierarquia_raw = _carregar_hierarquia_com_projeto()
df_cons_raw, erro_cons = carregar_consultivos(VERSAO)
df_prod_raw, erro_prod = carregar_producao(VERSAO)
if df_hierarquia_raw.empty:
    render_insight("Atenção: Lista de Ativos falhou ao carregar.", tipo="alerta")
df_prod = garantir_projeto_de_base(
    enriquecer_dados_completos(df_prod_raw, df_hierarquia_raw)
)
df_cons = garantir_projeto_de_base(
    enriquecer_dados_completos(df_cons_raw, df_hierarquia_raw)
)
if not df_prod.empty and any(
    c not in df_prod.columns for c in ["DATA", "LOGIN", "BASE", "PROJETO"]
):
    st.error("Colunas críticas perdidas em Produção.")
    st.stop()


def obter_param_url(chave: str) -> list[str]:
    try:
        return list(st.query_params.get_all(chave))
    except AttributeError:
        return []


def atualizar_param_url(chave: str, key_widget: str) -> None:
    try:
        st.query_params[chave] = st.session_state.get(key_widget, [])
    except Exception:
        pass


def obter_valores_unicos_seguro(df: pd.DataFrame, coluna: str) -> list[str]:
    if df.empty or coluna not in df.columns:
        return []
    return sorted(str(v) for v in df[coluna].dropna().unique().tolist())


render_sidebar_brand(empresa="TOTALE", segmento="Metas Operacionais")
render_sidebar_info(
    user_name="Administrador",
    email="analise.metas@totale.com.br",
    role="Gestão Operacional",
    avatar="🎯",
)
render_sidebar_section("Status de Conexão")
render_sidebar_status(
    status="Online" if not erro_prod and not erro_cons else "Com Erros",
    tipo="ok" if not erro_prod and not erro_cons else "critico",
)
render_sidebar_spacer(altura="medio")
render_sidebar_section("Filtros Consolidados")
all_bases = sorted(
    set(obter_valores_unicos_seguro(df_prod, "BASE"))
    | set(obter_valores_unicos_seguro(df_cons, "BASE"))
)
all_monitores = sorted(
    set(obter_valores_unicos_seguro(df_prod, "MONITOR"))
    | set(obter_valores_unicos_seguro(df_cons, "MONITOR"))
)
all_projetos = sorted(
    set(obter_valores_unicos_seguro(df_prod, "PROJETO"))
    | set(obter_valores_unicos_seguro(df_cons, "PROJETO"))
)
if not all_bases and not all_monitores and not all_projetos:
    st.sidebar.warning("Nenhuma coluna de filtro encontrada.")


def _aplicar_canais_net() -> None:
    if st.session_state.get("ui_net"):
        st.session_state["ui_proj"] = [p for p in PROJETOS_NET if p in all_projetos]


for chave, opcoes in (
    ("ui_proj", all_projetos),
    ("ui_base", all_bases),
    ("ui_monitor", all_monitores),
):
    if chave in st.session_state:
        anterior = st.session_state[chave]
        if isinstance(anterior, (tuple, list)):
            st.session_state[chave] = [v for v in anterior if v in opcoes]
        else:
            del st.session_state[chave]


filtro_net_opcao = st.sidebar.checkbox(
    "Filtrar canais oficiais NET",
    value=False,
    key="ui_net",
    on_change=_aplicar_canais_net,
    help="Ao marcar, seleciona NET-ABCDM, NET-LESTE, NET-LESTE VT, NET-GUARULHOS e NET-GRU VT.",
)
default_proj = (
    [p for p in PROJETOS_NET if p in all_projetos] if filtro_net_opcao else []
)
filtro_projeto = st.sidebar.multiselect(
    "Projeto / Contrato",
    all_projetos,
    [p for p in (obter_param_url("projeto") or default_proj) if p in all_projetos],
    key="ui_proj",
    on_change=atualizar_param_url,
    args=("projeto", "ui_proj"),
)
filtro_base = st.sidebar.multiselect(
    "Filial / Regional",
    all_bases,
    [b for b in obter_param_url("base") if b in all_bases],
    key="ui_base",
    on_change=atualizar_param_url,
    args=("base", "ui_base"),
)
filtro_monitor = st.sidebar.multiselect(
    "Supervisor / Monitor",
    all_monitores,
    [m for m in obter_param_url("monitor") if m in all_monitores],
    key="ui_monitor",
    on_change=atualizar_param_url,
    args=("monitor", "ui_monitor"),
)

hoje_tz = datetime.now(CFG.TZ).date()
data_min_disponivel, data_max, data_min = limites_datas_disponiveis(
    [df_prod, df_cons], hoje_tz
)
# Permite MTD mesmo quando o primeiro registro do mês é do dia 2 ou 3.
# Isso não certifica que a fonte contenha todas as transações do mês.
limite_min_widget = data_min_disponivel.replace(day=1)
chave_janela = "janela_temporal_v4616"
if chave_janela in st.session_state and not validar_estado_janela(
    st.session_state[chave_janela], limite_min_widget, data_max
):
    del st.session_state[chave_janela]
raw_filtro_datas = st.sidebar.date_input(
    "Janela Temporal",
    value=(data_min, data_max),
    min_value=limite_min_widget,
    max_value=data_max,
    format="DD/MM/YYYY",
    key=chave_janela,
)
_filtro_datas_safe = normalizar_janela_datas(raw_filtro_datas)
render_sidebar_divider(espacamento="medio")
if st.sidebar.button("Atualizar bases", width="stretch"):
    _carregar_hierarquia_com_projeto.clear()
    carregar_consultivos.clear()
    carregar_producao.clear()
    converter_para_excel.clear()
    http_session.clear()
    st.rerun()
if _filtro_datas_safe is None:
    st.sidebar.info("Selecione a data inicial e a data final do período.")
    st.stop()


def _mascara_filtros_operacionais(
    df: pd.DataFrame, eh_consultivo: bool = False
) -> pd.Series:
    """Regra original: BASE OR PROJETO; MONITOR restringe o resultado."""
    mask = pd.Series(True, index=df.index)
    base_match = _match_base_ou_projeto(df, filtro_base) if filtro_base else mask.copy()
    projeto_match = mask.copy()
    if filtro_projeto:
        if "PROJETO" in df.columns:
            projeto_match = _isin_norm(
                df["PROJETO"], filtro_projeto
            ) | _match_base_ou_projeto(df, filtro_projeto)
            if not projeto_match.any() and eh_consultivo and "BASE" in df.columns:
                projeto_match = _isin_norm(df["BASE"], filtro_projeto)
        elif "BASE" in df.columns:
            projeto_match = _isin_norm(df["BASE"], filtro_projeto)
    if filtro_base and filtro_projeto:
        mask &= base_match | projeto_match
    elif filtro_base:
        mask &= base_match
    elif filtro_projeto:
        mask &= projeto_match
    if filtro_monitor and "MONITOR" in df.columns:
        mask &= _isin_norm(df["MONITOR"], filtro_monitor)
    return mask


def filtrar_dataframe(df: pd.DataFrame, eh_consultivo: bool = False) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df = df.copy()
    if "DATA" not in df.columns:
        col_data_alt = detectar_coluna_data(df)
        if col_data_alt is not None:
            df = df.rename(columns={col_data_alt: "DATA"})
    if "DATA" in df.columns:
        df = garantir_datetime_auto(df, nome_fonte="Filtro")
    mask = _mascara_filtros_operacionais(df, eh_consultivo)
    if _filtro_datas_safe:
        if "DATA" not in df.columns:
            logger.warning("Fonte sem DATA: excluída do recorte temporal.")
            return df.iloc[0:0].copy()
        inicio, fim = _filtro_datas_safe
        mask &= mascara_periodo(df["DATA"], inicio, fim)
    return df.loc[mask].copy()


df_prod_f = filtrar_dataframe(df_prod)
df_cons_f = filtrar_dataframe(df_cons, eh_consultivo=True)
st.sidebar.caption(
    f"📊 Produção: {_fmt_int(len(df_prod))} bruto → {_fmt_int(len(df_prod_f))} filtrado"
)
st.sidebar.caption(
    f"💼 Consultivos: {_fmt_int(len(df_cons))} bruto → {_fmt_int(len(df_cons_f))} filtrado"
)
st.sidebar.caption(f"👥 Hierarquia: {_fmt_int(len(df_hierarquia_raw))} logins")
render_sidebar_footer_info(versao=f"v{VERSAO}")
fator_global_os, dias_rest_os, dias_tot_os, dias_trab_os = fator_projecao(df_prod_f)
fator_global_cons, dias_rest_c, dias_tot_c, dias_trab_c = fator_projecao(df_cons_f)
ancora_os = data_ancora_projecao(df_prod_f)
ancora_cons = data_ancora_projecao(df_cons_f)
_data_inicio_str = formatar_data_br(_filtro_datas_safe[0])
_data_fim_str = formatar_data_br(_filtro_datas_safe[1])
_periodo_multimes = (_filtro_datas_safe[0].year, _filtro_datas_safe[0].month) != (
    _filtro_datas_safe[1].year,
    _filtro_datas_safe[1].month,
)

abrir_dashboard(
    "Painel Consolidado de Metas",
    secoes=SECOES_PAGINA,
    hero=render_hero_totale_2,
    hero_kwargs={
        "titulo": "Painel Consolidado de Metas",
        "subtitulo": (
            "O que já foi feito, o que a projeção fecha e onde a meta exige ação imediata"
        ),
        "badge_texto": f"Período: {_data_inicio_str} até {_data_fim_str}",
    },
    chips=[
        ("Período", f"{_data_inicio_str} a {_data_fim_str}"),
        (
            "Âncora O.S.",
            f"{formatar_data_br(ancora_os)} · {dias_trab_os}/{dias_tot_os} d.u. ({dias_rest_os} rest.)",
        ),
        (
            "Âncora Consultivos",
            f"{formatar_data_br(ancora_cons)} · {dias_trab_c}/{dias_tot_c} d.u. ({dias_rest_c} rest.)",
        ),
        ("Regra", "Seg–Sáb · Faltantes = Meta − Realizado"),
    ],
)

_avisos_operacionais: list[tuple[str, TipoInsightType]] = []
for err in (erro_prod, erro_cons):
    if err:
        _avisos_operacionais.append((f"Atenção na carga de dados: {err}", "alerta"))
if len(df_cons) > 0 and len(df_cons_f) == 0:
    _avisos_operacionais.append(
        (
            f"⚠️ Consultivos: {_fmt_int(len(df_cons))} linhas carregadas, mas os filtros atuais eliminaram todas.",
            "alerta",
        )
    )
elif len(df_cons) == 0 and not erro_cons:
    _avisos_operacionais.append(
        (
            "⚠️ Consultivos: nenhuma linha carregada. Verifique o Google Drive.",
            "critico",
        )
    )
# Não altera a regra comercial sem autorização; sinaliza a limitação do fator mensal.
if _periodo_multimes:
    _avisos_operacionais.append(
        (
            "O período inclui mais de um mês. As metas e o fator de projeção são mensais; a projeção deste recorte não representa um fechamento mensal válido.",
            "alerta",
        )
    )
elif _filtro_datas_safe[0].day != 1:
    _avisos_operacionais.append(
        (
            "O recorte não começa no dia 1. O fator de projeção original usa dias decorridos desde o início do mês; interprete a projeção com cautela.",
            "alerta",
        )
    )
if ancora_os and ancora_cons and ancora_os != ancora_cons:
    _avisos_operacionais.append(
        (
            f"Fontes com datas de atualização diferentes: O.S. {formatar_data_br(ancora_os)}; consultivos {formatar_data_br(ancora_cons)}. Cada projeção mantém sua própria âncora.",
            "info",
        )
    )
if _avisos_operacionais:
    _tem_critico = any(t == "critico" for _, t in _avisos_operacionais)
    with st.expander(
        f"📌 Avisos operacionais do recorte ({len(_avisos_operacionais)})",
        expanded=_tem_critico,
    ):
        for _msg_aviso, _tipo_aviso in _avisos_operacionais:
            render_insight(_msg_aviso, tipo=_tipo_aviso)

real_prod = len(df_prod_f)
proj_prod = int(real_prod * fator_global_os)
meta_prod = METAS_PRODUCAO_OS_GERAL["meta_base"]
os_faltantes_geral = meta_prod - real_prod
os_media_diaria_geral = (
    max(os_faltantes_geral, 0) / dias_rest_os if dias_rest_os > 0 else 0
)
real_cons = len(df_cons_f)
proj_cons = int(real_cons * fator_global_cons)
meta_cons = METAS_CONSULTIVO_GERAL["meta_base"]
cons_faltantes_geral = meta_cons - real_cons
cons_media_diaria_geral = (
    max(cons_faltantes_geral, 0) / dias_rest_c if dias_rest_c > 0 else 0
)
pct_real_os_geral = calcular_atingimento_float(real_prod, meta_prod)
pct_proj_os_geral = calcular_atingimento_float(proj_prod, meta_prod)
pct_real_cons_geral = calcular_atingimento_float(real_cons, meta_cons)
pct_proj_cons_geral = calcular_atingimento_float(proj_cons, meta_cons)

with secao(
    "Resumo Executivo",
    icone="insights",
    subtitulo="Consolidado geral de O.S. e Consultivos frente à meta mensal e ritmo diário necessário.",
):
    k_os_real, k_os_proj, k_cons_real, k_cons_proj = st.columns(4, gap="medium")
    render_kpi(
        k_os_real,
        label="O.S. REALIZADAS",
        valor=_fmt_int(real_prod),
        sub=f"{pct_real_os_geral:.1f}% da meta ({_fmt_int(meta_prod)})",
        tema="azul",
        icone="📊",
    )
    render_kpi(
        k_os_proj,
        label="O.S. PROJETADAS",
        valor=_fmt_int(proj_prod) if ancora_os else "—",
        sub=(
            f"{pct_proj_os_geral:.1f}% da meta • Ritmo: {_fmt_dec(os_media_diaria_geral)}/d.u."
            if ancora_os
            else "Sem dados para projetar"
        ),
        tema=(
            tema_kpi_de_valor(proj_prod, METAS_PRODUCAO_OS_GERAL)
            if ancora_os
            else "cinza"
        ),
        icone="📈",
    )
    render_kpi(
        k_cons_real,
        label="CONSULTIVOS REALIZADOS",
        valor=_fmt_int(real_cons),
        sub=f"{pct_real_cons_geral:.1f}% da meta ({_fmt_int(meta_cons)})",
        tema="laranja",
        icone="💼",
    )
    render_kpi(
        k_cons_proj,
        label="CONSULTIVOS PROJETADOS",
        valor=_fmt_int(proj_cons) if ancora_cons else "—",
        sub=(
            f"{pct_proj_cons_geral:.1f}% da meta • Ritmo: {_fmt_dec(cons_media_diaria_geral)}/d.u."
            if ancora_cons
            else "Sem dados para projetar"
        ),
        tema=(
            tema_kpi_de_valor(proj_cons, METAS_CONSULTIVO_GERAL)
            if ancora_cons
            else "cinza"
        ),
        icone="🎯",
    )

cenarios_os = calcular_cenarios(real_prod, fator_global_os)
cenarios_cons = calcular_cenarios(real_cons, fator_global_cons)


def _status_cenario(valor: int, metas: dict[str, int]) -> str:
    nome, _ = resolver_status_atingimento(valor, metas)
    return {
        "Alta Performance": "🟢 Alta performance",
        "Meta Atingida": "🟢 Meta projetada",
        "Atenção / Mínimo": "🟠 No mínimo",
    }.get(nome, "🔴 Abaixo do mínimo")


df_cenarios = pd.DataFrame(
    [
        {
            "Indicador": indicador,
            "Meta mensal": meta,
            "Conservador": cenarios["Conservador"],
            "Atual": cenarios["Atual"],
            "Otimista": cenarios["Otimista"],
            "% da meta (atual)": calcular_atingimento_float(cenarios["Atual"], meta),
            "Status atual": _status_cenario(cenarios["Atual"], metas),
        }
        for indicador, meta, cenarios, metas in (
            ("📊 O.S.", meta_prod, cenarios_os, METAS_PRODUCAO_OS_GERAL),
            ("💼 Consultivos", meta_cons, cenarios_cons, METAS_CONSULTIVO_GERAL),
        )
        if (ancora_os if indicador == "📊 O.S." else ancora_cons) is not None
    ],
    columns=[
        "Indicador",
        "Meta mensal",
        "Conservador",
        "Atual",
        "Otimista",
        "% da meta (atual)",
        "Status atual",
    ],
)
_cenario_styler = (
    df_cenarios.style.format(
        {
            "Meta mensal": _fmt_int,
            "Conservador": _fmt_int,
            "Atual": _fmt_int,
            "Otimista": _fmt_int,
            "% da meta (atual)": lambda valor: f"{valor:.1f}%",
        }
    )
    .set_properties(
        subset=["Conservador"],
        **{"background-color": "#fff7ed", "color": "#9a3412", "font-weight": "600"},
    )
    .set_properties(
        subset=["Atual"],
        **{"background-color": "#eff6ff", "color": "#1d4ed8", "font-weight": "700"},
    )
    .set_properties(
        subset=["Otimista"],
        **{"background-color": "#ecfdf5", "color": "#047857", "font-weight": "600"},
    )
    .set_properties(
        subset=["Indicador", "Status atual"],
        **{"font-weight": "600", "text-align": "left"},
    )
    .set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background-color", "#f1f5f9"),
                    ("color", "#334155"),
                    ("font-weight", "700"),
                    ("padding", "10px 12px"),
                    ("text-align", "center"),
                    ("border-bottom", "2px solid #cbd5e1"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("padding", "12px"),
                    ("text-align", "center"),
                    ("border-bottom", "1px solid #e2e8f0"),
                ],
            },
            {
                "selector": "table",
                "props": [
                    ("border-collapse", "separate"),
                    ("border-spacing", "0"),
                    ("border-radius", "10px"),
                    ("overflow", "hidden"),
                ],
            },
        ]
    )
)
with secao(
    "Cenários de Fechamento",
    icone="analytics",
    subtitulo="Simulação de fechamento em três ritmos de produção (±15% sobre o saldo projetado ainda não realizado).",
):
    st.dataframe(_cenario_styler, hide_index=True, width="stretch", height=160)


def processar_resumo_agrupado(
    prod: pd.DataFrame, cons: pd.DataFrame, ft_os: float, ft_cons: float
) -> pd.DataFrame:
    if not prod.empty and all(c in prod.columns for c in ["CHAVE_AGRUPAMENTO", "DATA"]):
        prod = prod.copy()
        if "TECNICO" not in prod.columns:
            prod["TECNICO"] = "Não Informado"
        a = (
            prod.groupby("CHAVE_AGRUPAMENTO")
            .agg(
                Agrupamento=("CHAVE_AGRUPAMENTO", "first"),
                OS_Volume=("DATA", "size"),
                Tecnicos_Ativos=("TECNICO", contar_tecnicos_validos),
            )
            .reset_index()
        )
    else:
        a = pd.DataFrame(
            columns=["CHAVE_AGRUPAMENTO", "Agrupamento", "OS_Volume", "Tecnicos_Ativos"]
        )
    if not cons.empty and all(c in cons.columns for c in ["CHAVE_AGRUPAMENTO", "DATA"]):
        b = (
            cons.groupby("CHAVE_AGRUPAMENTO")
            .agg(
                Agrupamento_C=("CHAVE_AGRUPAMENTO", "first"),
                Cons_Volume=("DATA", "size"),
            )
            .reset_index()
        )
    else:
        b = pd.DataFrame(columns=["CHAVE_AGRUPAMENTO", "Agrupamento_C", "Cons_Volume"])
    if a.empty and b.empty:
        return pd.DataFrame()
    m = pd.merge(a, b, on="CHAVE_AGRUPAMENTO", how="outer")
    m["Agrupamento"] = (
        m["Agrupamento"].fillna(m["Agrupamento_C"]).fillna("Não Informado")
    )
    m = m.drop(columns=["Agrupamento_C", "CHAVE_AGRUPAMENTO"])
    for col in ["OS_Volume", "Cons_Volume", "Tecnicos_Ativos"]:
        m[col] = (
            pd.to_numeric(m[col], errors="coerce").fillna(0).astype(int)
            if col in m.columns
            else 0
        )
    m["O.S. Projetadas"] = (m["OS_Volume"] * ft_os).astype(int)
    m["Consultivos Projetados"] = (m["Cons_Volume"] * ft_cons).astype(int)
    m["O.S. Faltantes"] = np.where(
        m["OS_Volume"] > 0,
        (METAS_PRODUCAO_OS_BASE["meta_base"] - m["OS_Volume"]).clip(lower=0),
        0,
    ).astype(int)
    m["Cons. Faltantes"] = np.where(
        m["Cons_Volume"] > 0,
        (METAS_CONSULTIVO_BASE["meta_base"] - m["Cons_Volume"]).clip(lower=0),
        0,
    ).astype(int)
    m["% Meta O.S. (Proj)"] = calcular_atingimento_series(
        m["O.S. Projetadas"], float(METAS_PRODUCAO_OS_BASE["meta_base"])
    ).round(1)
    m["% Meta Cons. (Proj)"] = calcular_atingimento_series(
        m["Consultivos Projetados"], float(METAS_CONSULTIVO_BASE["meta_base"])
    ).round(1)
    m["Status O.S."] = m["O.S. Projetadas"].apply(
        lambda v: classificar_semaforo(v, METAS_PRODUCAO_OS_BASE)
    )
    m["Status Consultivos"] = m["Consultivos Projetados"].apply(
        lambda v: classificar_semaforo(v, METAS_CONSULTIVO_BASE)
    )
    m = adicionar_cenarios_agrupados(m, "OS_Volume", "O.S. Projetadas", "O.S.")
    m = adicionar_cenarios_agrupados(
        m, "Cons_Volume", "Consultivos Projetados", "Consultivos"
    )
    m["_ordem"] = np.where(m["OS_Volume"] > 0, m["% Meta O.S. (Proj)"], 999.0)
    return (
        m.sort_values(["_ordem", "Agrupamento"])
        .drop(columns=["_ordem"])
        .reset_index(drop=True)
    )


df_prod_para_resumo = df_prod_f.copy()
df_cons_para_resumo = df_cons_f.copy()
if not df_prod_para_resumo.empty and "PROJETO" in df_prod_para_resumo.columns:
    df_prod_para_resumo["CHAVE_AGRUPAMENTO"] = df_prod_para_resumo["PROJETO"]
# Consultivos: projeções passam a seguir o projeto normalizado (_PROJETO_NORM),
# alinhando os consultivos às abas de projeção (NET-ABCDM / NET-LESTE / NET-GUARULHOS).
if not df_cons_para_resumo.empty:
    if "_PROJETO_NORM" in df_cons_para_resumo.columns:
        chave_cons = df_cons_para_resumo["_PROJETO_NORM"].astype(str).str.strip()
    elif "PROJETO" in df_cons_para_resumo.columns:
        chave_cons = df_cons_para_resumo["PROJETO"].astype(str).map(normalizar_texto)
    elif "BASE" in df_cons_para_resumo.columns:
        chave_cons = df_cons_para_resumo["BASE"].astype(str).map(normalizar_texto)
    else:
        chave_cons = pd.Series("", index=df_cons_para_resumo.index)
    df_cons_para_resumo["CHAVE_AGRUPAMENTO"] = chave_cons.where(
        chave_cons != "", "Não Informado"
    )
df_resumo_agrupado = processar_resumo_agrupado(
    df_prod_para_resumo, df_cons_para_resumo, fator_global_os, fator_global_cons
)
with secao(
    "Análise Detalhada por Frente",
    icone="hub",
    subtitulo="Navegue pelas abas para detalhar Produção, Consultivos, Visão por Projeto, Supervisores, Projeções por Base e Alertas.",
):
    (
        tab_prod,
        tab_cons,
        tab_bases,
        tab_monitores,
        tab_alertas,
        tab_abcdm,
        tab_leste,
        tab_guarulhos,
    ) = st.tabs(
        [
            "📊 Produção",
            "💼 Consultivos",
            "🗂️ Visão Agrupada",
            "👔 Monitores",
            "🚨 Alertas",
            "📈 Projeção ABCDM",
            "📈 Projeção LESTE",
            "📈 Projeção GUARULHOS",
        ]
    )


def render_diagnostico_zerado(
    df: pd.DataFrame, df_raw: pd.DataFrame, erro: str | None, nome: str
) -> None:
    with st.expander(f"🔍 Diagnóstico: Por que {nome} está zerado?", expanded=True):
        if erro:
            st.error(f"❌ Erro de carga: {erro}")
        elif df_raw.empty:
            st.warning("⚠️ Fonte veio vazia.")
        else:
            st.success(f"✅ Fonte OK: {_fmt_int(len(df_raw))} linhas brutas.")
        st.dataframe(
            diagnosticar_perda_filtros(df, nome), hide_index=True, width="stretch"
        )
        if not df.empty and "DATA" in df.columns:
            st.markdown("### Amostra de Datas Corrigidas (DD-MM-AAAA)")
            cols = [
                c
                for c in ["DATA", "LOGIN", "BASE", "PROJETO", "MONITOR", "TECNICO"]
                if c in df.columns
            ]
            amostra = df[cols].head(15).copy()
            amostra["DATA"] = (
                converter_serie_datas(amostra["DATA"])
                .dt.strftime("%d-%m-%Y %H:%M")
                .fillna("-")
            )
            st.dataframe(amostra, hide_index=True, width="stretch")
        st.markdown("### Ações")
        st.markdown(
            "1. Confira os filtros BASE/PROJETO/MONITOR e clique em **Atualizar bases**.\n"
            "2. Se a etapa **DATA** eliminar os registros, confira a faixa da fonte e amplie a janela temporal.\n"
            "3. Desmarque **Filtrar canais oficiais NET** e limpe Base/Projeto/Monitor para validar."
        )


with tab_prod:
    render_resumo_cards(
        titulo="Produção Geral",
        icone="📊",
        realizado=float(real_prod),
        projetado=float(proj_prod),
        meta=float(meta_prod),
        faltantes=float(os_faltantes_geral),
        media_diaria=os_media_diaria_geral,
        dias_restantes=dias_rest_os,
        tema_progresso="azul",
        label_realizado="O.S. REALIZADAS",
        label_projetado="O.S. PROJETADAS",
        label_meta="META MENSAL DE O.S.",
        label_faltantes="O.S. FALTANTES",
        metas=METAS_PRODUCAO_OS_GERAL,
        ancora=ancora_os,
    )
    if real_prod == 0:
        render_diagnostico_zerado(df_prod, df_prod_raw, erro_prod, "Produção")
with tab_cons:
    render_resumo_cards(
        titulo="Consultivos",
        icone="💼",
        realizado=float(real_cons),
        projetado=float(proj_cons),
        meta=float(meta_cons),
        faltantes=float(cons_faltantes_geral),
        media_diaria=cons_media_diaria_geral,
        dias_restantes=dias_rest_c,
        tema_progresso="laranja",
        label_realizado="CONSULTIVOS REALIZADOS",
        label_projetado="CONSULTIVOS PROJETADOS",
        label_meta="META MENSAL DE CONSULTIVOS",
        label_faltantes="CONSULTIVOS FALTANTES",
        metas=METAS_CONSULTIVO_GERAL,
        ancora=ancora_cons,
    )
    if real_cons == 0:
        render_diagnostico_zerado(df_cons, df_cons_raw, erro_cons, "Consultivos")
with tab_bases:
    render_section_header(
        titulo="Visão Agrupada por Projeto",
        icone="🗂️",
        subtitulo="Produção por projeto e consultivos por projeto (_PROJETO_NORM), ordenados do maior risco para o melhor fechamento",
    )
    render_chips(
        [
            (
                "Meta O.S. / Base",
                _fmt_int(METAS_PRODUCAO_OS_BASE["meta_base"]),
            ),
            (
                "Meta Consultivos / Base",
                _fmt_int(METAS_CONSULTIVO_BASE["meta_base"]),
            ),
            ("Fórmula Faltantes", "Meta − Realizado"),
        ]
    )
    if not df_resumo_agrupado.empty:
        visao_tabela = st.radio(
            "Modo de visualização da tabela agrupada",
            options=[
                "📋 Resumo Executivo (O.S. + Consultivos)",
                "📊 Foco em Produção (O.S. & Cenários)",
                "💼 Foco em Consultivos (Volume & Cenários)",
                "🔎 Tabela Completa (16 colunas)",
            ],
            horizontal=True,
            key="radio_visao_agrupada_meta",
        )
        df_base_renomeada = df_resumo_agrupado.rename(
            columns={"OS_Volume": "O.S. Real", "Cons_Volume": "Cons. Real"}
        )
        if visao_tabela.startswith("📋"):
            cols_visao = [
                "Agrupamento",
                "Tecnicos_Ativos",
                "O.S. Real",
                "O.S. Projetadas",
                "O.S. Faltantes",
                "% Meta O.S. (Proj)",
                "Status O.S.",
                "Cons. Real",
                "Consultivos Projetados",
                "Cons. Faltantes",
                "% Meta Cons. (Proj)",
                "Status Consultivos",
            ]
        elif visao_tabela.startswith("📊"):
            cols_visao = [
                "Agrupamento",
                "Tecnicos_Ativos",
                "O.S. Real",
                "O.S. Projetadas",
                "O.S. Conservadora",
                "O.S. Otimista",
                "O.S. Faltantes",
                "% Meta O.S. (Proj)",
                "Status O.S.",
            ]
        elif visao_tabela.startswith("💼"):
            cols_visao = [
                "Agrupamento",
                "Tecnicos_Ativos",
                "Cons. Real",
                "Consultivos Projetados",
                "Consultivos Conservadora",
                "Consultivos Otimista",
                "Cons. Faltantes",
                "% Meta Cons. (Proj)",
                "Status Consultivos",
            ]
        else:
            cols_visao = [
                "Agrupamento",
                "O.S. Real",
                "O.S. Projetadas",
                "O.S. Conservadora",
                "O.S. Otimista",
                "O.S. Faltantes",
                "% Meta O.S. (Proj)",
                "Status O.S.",
                "Cons. Real",
                "Consultivos Projetados",
                "Consultivos Conservadora",
                "Consultivos Otimista",
                "Cons. Faltantes",
                "% Meta Cons. (Proj)",
                "Status Consultivos",
                "Tecnicos_Ativos",
            ]
        cols_visao = [c for c in cols_visao if c in df_base_renomeada.columns]
        df_display = df_base_renomeada[cols_visao]
        todas_num = [
            "O.S. Real",
            "O.S. Projetadas",
            "O.S. Conservadora",
            "O.S. Otimista",
            "O.S. Faltantes",
            "Cons. Real",
            "Consultivos Projetados",
            "Consultivos Conservadora",
            "Consultivos Otimista",
            "Cons. Faltantes",
            "Tecnicos_Ativos",
        ]
        colunas_num = [c for c in todas_num if c in df_display.columns]
        fmt = {c: "{:,.0f}" for c in colunas_num}
        for pct_col in ("% Meta O.S. (Proj)", "% Meta Cons. (Proj)"):
            if pct_col in df_display.columns:
                fmt[pct_col] = "{:.1f}%"
        color_rules = {
            c: {
                str(v): "sucesso" if float(v) >= 100 else "alerta"
                for v in df_display[c].dropna().unique()
            }
            for c in ("% Meta O.S. (Proj)", "% Meta Cons. (Proj)")
            if c in df_display.columns
        }
        render_tabela_segura(
            df_display, fmt=fmt, colunas_num=colunas_num, color_rules=color_rules
        )
        render_botao_exportacao(df_resumo_agrupado, "Resumo_Agrupado")
    else:
        render_empty_state(tipo="dados", titulo="Sem dados para a visão agrupada.")


def render_aba_projecao_base(tab: DeltaGenerator, base_nome: str) -> None:
    with tab:
        render_section_header(
            titulo=f"Projeção de Desempenho — {base_nome}",
            icone="📈",
            subtitulo="Simule a força de trabalho ativa e acompanhe o ritmo necessário para fechar O.S. e Consultivos.",
        )
        if df_resumo_agrupado.empty:
            render_empty_state(tipo="dados", titulo="Sem dados para projeção")
            return
        b_data = df_resumo_agrupado[
            df_resumo_agrupado["Agrupamento"].astype(str).str.strip().str.upper()
            == base_nome.strip().upper()
        ]
        if b_data.empty:
            render_empty_state(tipo="filtro", titulo="Agrupamento sem dados")
            return
        try:
            row = b_data.iloc[0]
            os_real = _to_float_safe(row["OS_Volume"])
            os_projetado = _to_float_safe(row["O.S. Projetadas"])
            cons_real = _to_float_safe(row["Cons_Volume"])
            cons_projetado = _to_float_safe(row["Consultivos Projetados"])
            tecnicos_base = max(
                1, int(_to_float_safe(row["Tecnicos_Ativos"], default=1))
            )
        except (IndexError, KeyError, ValueError, TypeError) as exc:
            render_insight(f"Erro: {exc}", tipo="critico")
            return
        meta_os = float(METAS_PRODUCAO_OS_BASE["meta_base"])
        meta_cons_base = float(METAS_CONSULTIVO_BASE["meta_base"])
        c1, c2 = st.columns([1, 2], gap="large")
        with c1:
            tecnicos_ativos = st.number_input(
                "Técnicos ativos para simulação de ritmo",
                min_value=1,
                max_value=1000,
                value=min(tecnicos_base, 1000),
                step=1,
                key=f"tecnicos_{base_nome}",
            )
        with c2:
            render_chips(
                [
                    ("Base", base_nome),
                    ("Técnicos Identificados", f"{tecnicos_base} ativos"),
                    ("Âncora O.S.", formatar_data_br(ancora_os)),
                    ("Âncora Consultivos", formatar_data_br(ancora_cons)),
                ]
            )
        os_faltantes = meta_os - os_real
        os_media_diaria = max(os_faltantes, 0) / dias_rest_os if dias_rest_os > 0 else 0
        cons_faltantes = meta_cons_base - cons_real
        cons_media_diaria = (
            max(cons_faltantes, 0) / dias_rest_c if dias_rest_c > 0 else 0
        )
        sub_os, sub_cons = st.tabs(
            [
                f"📊 Produção O.S. ({_fmt_int(os_real)} / {_fmt_int(meta_os)})",
                f"💼 Consultivos ({_fmt_int(cons_real)} / {_fmt_int(meta_cons_base)})",
            ]
        )
        with sub_os:
            render_resumo_cards(
                titulo=f"Produção (O.S.) — {base_nome}",
                icone="📊",
                realizado=os_real,
                projetado=os_projetado,
                meta=meta_os,
                faltantes=os_faltantes,
                media_diaria=os_media_diaria,
                dias_restantes=dias_rest_os,
                tema_progresso="azul",
                label_realizado="O.S. REALIZADAS",
                label_projetado="O.S. PROJETADAS",
                label_meta="META DE O.S.",
                label_faltantes="O.S. FALTANTES",
                metas=METAS_PRODUCAO_OS_BASE,
                tecnico_dia=(
                    os_media_diaria / tecnicos_ativos if tecnicos_ativos > 0 else 0
                ),
                ancora=ancora_os if os_real > 0 else None,
            )
        with sub_cons:
            render_resumo_cards(
                titulo=f"Consultivos — {base_nome}",
                icone="💼",
                realizado=cons_real,
                projetado=cons_projetado,
                meta=meta_cons_base,
                faltantes=cons_faltantes,
                media_diaria=cons_media_diaria,
                dias_restantes=dias_rest_c,
                tema_progresso="laranja",
                label_realizado="CONSULTIVOS REALIZADOS",
                label_projetado="CONSULTIVOS PROJETADOS",
                label_meta="META DE CONSULTIVOS",
                label_faltantes="CONSULTIVOS FALTANTES",
                metas=METAS_CONSULTIVO_BASE,
                ancora=ancora_cons if cons_real > 0 else None,
            )


render_aba_projecao_base(tab_abcdm, "NET-ABCDM")
render_aba_projecao_base(tab_leste, "NET-LESTE")
render_aba_projecao_base(tab_guarulhos, "NET-GUARULHOS")
with tab_monitores:
    render_section_header(
        titulo="Desempenho por Supervisor",
        icone="👔",
        subtitulo="Participação no volume de O.S. e consultivos no mesmo recorte filtrado",
    )
    if df_prod_f.empty and df_cons_f.empty:
        render_empty_state(tipo="dados", titulo="Sem dados de supervisores")
    else:
        partes = []
        if not df_prod_f.empty and "MONITOR" in df_prod_f.columns:
            partes.append(
                df_prod_f.groupby("MONITOR").size().rename("OS_Equipe").reset_index()
            )
        if not df_cons_f.empty and "MONITOR" in df_cons_f.columns:
            partes.append(
                df_cons_f.groupby("MONITOR").size().rename("Consultivos").reset_index()
            )
        if not partes:
            render_empty_state(tipo="dados", titulo="Sem monitor na hierarquia")
        else:
            df_mon = partes[0]
            for p in partes[1:]:
                df_mon = pd.merge(df_mon, p, on="MONITOR", how="outer")
            for col in ("OS_Equipe", "Consultivos"):
                if col not in df_mon.columns:
                    df_mon[col] = 0
                df_mon[col] = df_mon[col].fillna(0).astype(int)
            total_os = int(df_mon["OS_Equipe"].sum())
            df_mon["Participação O.S. (%)"] = (
                (df_mon["OS_Equipe"] / total_os * 100).round(1) if total_os else 0.0
            )
            df_mon = df_mon.sort_values(["OS_Equipe", "Consultivos"], ascending=False)
            supervisores = df_mon[df_mon["OS_Equipe"] > 0].head(8)
            col_grafico_mon, col_tabela_mon = st.columns([2, 3], gap="large")
            with col_grafico_mon:
                if not supervisores.empty:
                    fig_donut = grafico_donut(
                        supervisores["MONITOR"].tolist(),
                        supervisores["OS_Equipe"].tolist(),
                        titulo="Top Supervisores (O.S. da equipe)",
                        altura=340,
                    )
                    if fig_donut is not None:
                        st.plotly_chart(fig_donut, width="stretch")
                else:
                    render_empty_state(
                        tipo="dados", titulo="Sem volume de O.S. por supervisor"
                    )
            with col_tabela_mon:
                render_tabela_segura(
                    df_mon,
                    fmt={
                        "OS_Equipe": "{:,.0f}",
                        "Consultivos": "{:,.0f}",
                        "Participação O.S. (%)": "{:.1f}%",
                    },
                )
                render_botao_exportacao(df_mon, "Resumo_Supervisores")
with tab_alertas:
    render_section_header(
        titulo="Central de Alertas da Meta",
        icone="🚨",
        subtitulo="Desvios críticos e pontos de atenção que impactam o fechamento da meta neste recorte",
        badge="Monitoramento",
        badge_tipo="erro",
    )
    alertas = coletar_alertas(
        df_prod_raw,
        df_cons_raw,
        df_cons_f,
        df_resumo_agrupado,
        erro_prod,
        erro_cons,
        hoje_tz,
    )
    if not alertas:
        render_insight("Nenhum desvio relevante identificado no recorte.", tipo="ok")
    else:
        alertas_criticos = [msg for msg, t in alertas if t == "critico"]
        alertas_atencao = [(msg, t) for msg, t in alertas if t != "critico"]
        render_chips(
            [
                ("Total de Alertas", str(len(alertas))),
                ("Críticos", str(len(alertas_criticos))),
                ("Avisos / Atenção", str(len(alertas_atencao))),
            ]
        )
        col_crit, col_aviso = st.columns(2, gap="large")
        with col_crit:
            st.markdown("#### 🔴 Desvios Críticos")
            if alertas_criticos:
                for mensagem in alertas_criticos[:8]:
                    render_insight(mensagem, tipo="critico")
            else:
                render_insight("Nenhum alerta crítico no momento.", tipo="ok")
        with col_aviso:
            st.markdown("#### 🟠 Pontos de Atenção")
            if alertas_atencao:
                for mensagem, tipo in alertas_atencao[:8]:
                    render_insight(mensagem, tipo=tipo)
            else:
                render_insight("Nenhum aviso adicional.", tipo="ok")
        if len(alertas) > 16:
            st.caption(
                f"Mais {len(alertas) - 16} alertas omitidos para preservar a legibilidade."
            )

fechar_dashboard(versao=VERSAO)