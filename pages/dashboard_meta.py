"""
dashboard_meta.py
=================
Dashboard de Metas Operacionais - TOTALE (v4.6.2)

Leitura do painel:
1. Faixa executiva: realizado, projeção e se o fechamento cabe na meta.
2. Abas operacionais: produção, consultivos, agrupamento, monitores e projeção por base.
3. Central de alertas calculada de verdade — não é mais um texto estático.

Regras preservadas:
- Faltantes = Meta - Realizado (não é a projeção).
- Produção agrupada por PROJETO; consultivo agrupado por BASE.
- Dias úteis de segunda a sábado, sem domingo e sem feriado nacional.
- Número de técnicos editável manualmente em cada base.
"""

from __future__ import annotations

import io
import logging
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote as url_quote
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator
else:
    try:
        from streamlit.delta_generator import DeltaGenerator
    except ImportError:
        DeltaGenerator = Any

TipoInsightType = Literal["ok", "info", "alerta", "critico", "acao"]
TemaKPIType = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"
]
TipoProgressBarType = Literal[
    "azul", "laranja", "verde", "vermelho", "roxo", "gradiente"
]

try:
    from components.componentes import (
        aplicar_estilo,
        aplicar_sidebar_corp,
        render_empty_state,
        render_hero_totale_2,
        render_insight,
        render_kpi,
        render_metric_card,
        render_progress_bar,
        render_section_header,
        render_sidebar_brand,
        render_sidebar_divider,
        render_sidebar_footer_info,
        render_sidebar_info,
        render_sidebar_section,
        render_sidebar_spacer,
        render_sidebar_status,
        render_table_html,
    )
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
        valor: float,
        maximo: float = 100.0,
        label: str = "",
        **kwargs: Any,
    ) -> None:
        if label:
            st.caption(label)
        st.progress(min(valor / maximo, 1.0) if maximo else 0.0)

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

    aplicar_estilo = _noop
    aplicar_sidebar_corp = _noop
    render_empty_state = lambda **k: st.info(
        k.get("titulo") or k.get("descricao") or "Sem dados"
    )
    render_hero_totale_2 = lambda **k: st.title(k.get("titulo", "Dashboard"))
    render_insight = _fallback_insight
    render_kpi = _fallback_kpi
    render_metric_card = _fallback_metric_card
    render_progress_bar = _fallback_progress
    render_section_header = _fallback_section_header
    render_sidebar_brand = _noop
    render_sidebar_divider = _noop
    render_sidebar_footer_info = _noop
    render_sidebar_info = _noop
    render_sidebar_section = lambda *a, **k: st.sidebar.header(a[0] if a else "")
    render_sidebar_spacer = _noop
    render_sidebar_status = lambda **k: st.sidebar.success(k.get("status", "OK"))
    render_table_html = lambda df, **k: st.dataframe(df, use_container_width=True)

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


VERSAO = "4.6.2"
ROTULOS_VAZIOS = {"", "NAN", "NONE", "NA", "N/A", "NAO INFORMADO", "NULL"}


@dataclass
class Configuracoes:
    URL_ATIVOS: str = field(
        default_factory=lambda: st.secrets.get(
            "URL_ATIVOS",
            "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg",
        )
    )
    SHEET_ID_ATIVOS: str = field(
        default_factory=lambda: st.secrets.get(
            "SHEET_ID_ATIVOS", "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
        )
    )
    SHEET_ABA_ATIVOS: str = "lista_ativos"
    SHEET_ID_PROD: str = field(
        default_factory=lambda: st.secrets.get(
            "SHEET_ID_PROD", "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
        )
    )
    SHEET_ABA_PROD: str = "Prod"
    DRIVE_ID_CONS: str = field(
        default_factory=lambda: st.secrets.get(
            "DRIVE_ID_CONS", "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"
        )
    )
    TIMEOUT: int = 60
    TZ: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/Sao_Paulo"))
    CACHE_TTL_HIERARQUIA: int = 3600
    CACHE_TTL_CONSULTIVO: int = 600
    CACHE_TTL_PRODUCAO: int = 300


CFG = Configuracoes()
BASES_PRIORITARIAS: tuple[str, ...] = ("NET-ABCDM", "NET-LESTE", "NET-GUARULHOS")
PROJETOS_NET: tuple[str, ...] = (
    "NET-ABCDM",
    "NET-LESTE",
    "NET-LESTE VT",
    "NET-GUARULHOS",
    "NET-GRU VT",
)
METAS_PRODUCAO_OS_BASE: dict[str, int] = {
    "minima": 10_000,
    "meta_base": 11_000,
    "alta_perf": 12_000,
}
METAS_CONSULTIVO_BASE: dict[str, int] = {
    "minima": 400,
    "meta_base": 525,
    "alta_perf": 600,
}
METAS_PRODUCAO_OS_GERAL: dict[str, int] = {
    "minima": 30_000,
    "meta_base": 33_000,
    "alta_perf": 36_000,
}
METAS_CONSULTIVO_GERAL: dict[str, int] = {
    "minima": 1_200,
    "meta_base": 1_575,
    "alta_perf": 1_800,
}


@st.cache_resource
def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": f"totale-dashboard/{VERSAO}"})
    return s


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
        file_name=f"{nome_arquivo}_{hoje_tz.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
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
    except Exception:
        return False


def normalizar_texto(texto: Any) -> str:
    if _is_na_scalar(texto):
        return ""
    txt = str(texto).strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    ).upper()


def _to_float_safe(value: Any, default: float = 0.0) -> float:
    if _is_na_scalar(value):
        return default
    if isinstance(value, (int, float, np.integer, np.floating)):
        val_float = float(value)
        return default if np.isnan(val_float) else val_float
    try:
        val_float = float(value)
        return default if np.isnan(val_float) else val_float
    except (TypeError, ValueError):
        return default


def formatar_data_br(valor: Any, com_hora: bool = False) -> str:
    if _is_na_scalar(valor):
        return "-"
    try:
        ts = pd.Timestamp(valor)
        if pd.isna(ts):
            return "-"
        return ts.strftime("%d/%m/%Y %H:%M" if com_hora else "%d/%m/%Y")
    except Exception:
        return str(valor)


def _fmt_int(valor: Any) -> str:
    return f"{int(round(_to_float_safe(valor))):,}".replace(",", ".")


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
        aliases_norm = [normalizar_texto(a) for a in aliases]
        for alias in aliases_norm:
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


def garantir_datetime(
    df: pd.DataFrame, col: str = "DATA", origem: str = ""
) -> pd.DataFrame:
    if col not in df.columns or df.empty:
        return df.copy()
    df_copia = df.copy()
    if pd.api.types.is_datetime64_any_dtype(df_copia[col]):
        df_copia[col] = pd.to_datetime(df_copia[col], errors="coerce")
        return df_copia
    texto = df_copia[col].astype(str).str.strip()
    invalidos = {"", "nan", "None", "NaT", "NaN", "-", "NULL", "<NA>"}
    s = texto.mask(texto.isin(invalidos))
    formatos = (
        ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d")
        if origem == "us"
        else ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d")
    )
    resultado = pd.Series(pd.NaT, index=df_copia.index, dtype="datetime64[ns]")
    restantes = s.notna()
    for fmt in formatos:
        if not restantes.any():
            break
        try:
            parsed = pd.to_datetime(s[restantes], format=fmt, errors="coerce")
            ok = parsed.notna()
            if ok.any():
                idx_ok = parsed.index[ok]
                resultado.loc[idx_ok] = parsed.loc[idx_ok]
                restantes.loc[idx_ok] = False
        except Exception as e:
            logger.debug("Formato %s falhou: %s", fmt, e)
            continue
    if restantes.any():
        try:
            parsed = pd.to_datetime(
                s[restantes], dayfirst=(origem == "br"), errors="coerce"
            )
            ok = parsed.notna()
            if ok.any():
                resultado.loc[parsed.index[ok]] = parsed.loc[ok]
        except Exception as e:
            logger.debug("Parse final falhou: %s", e)
    df_copia[col] = resultado
    return df_copia


def garantir_datetime_auto(
    df: pd.DataFrame, col: str = "DATA", nome_fonte: str = ""
) -> pd.DataFrame:
    """Detecta a orientação da coluna inteira e normaliza para datetime.

    A orientação é inferida pelos registros não ambíguos do próprio arquivo:
    13/09 indica DD/MM, enquanto 09/26 indica MM/DD. Datas ambíguas seguem a
    orientação predominante da coluna; empate usa MM/DD como padrão legado.
    """
    if col not in df.columns or df.empty:
        return df.copy()
    if pd.api.types.is_datetime64_any_dtype(df[col]):
        df_out = df.copy()
        df_out[col] = pd.to_datetime(df_out[col], errors="coerce")
        return df_out

    padrao_data = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?:\s|$)")
    votos_br = 0
    votos_us = 0
    for valor in df[col].dropna().astype(str):
        achado = padrao_data.match(valor.strip())
        if not achado:
            continue
        primeiro, segundo = int(achado.group(1)), int(achado.group(2))
        if primeiro > 12 and segundo <= 12:
            votos_br += 1
        elif segundo > 12 and primeiro <= 12:
            votos_us += 1
    dayfirst_padrao = votos_br > votos_us

    def _parse_valor(valor: Any) -> Any:
        if _is_na_scalar(valor):
            return pd.NaT
        texto = str(valor).strip()
        if not texto or texto.upper() in {"NAT", "NULL", "<NA>", "-"}:
            return pd.NaT

        match = padrao_data.match(texto)
        if match:
            primeiro, segundo = int(match.group(1)), int(match.group(2))
            if primeiro > 12 and segundo <= 12:
                dayfirst = True
            elif segundo > 12 and primeiro <= 12:
                dayfirst = False
            else:
                dayfirst = dayfirst_padrao
            try:
                parsed = pd.to_datetime(texto, dayfirst=dayfirst, errors="coerce")
                return parsed if not pd.isna(parsed) else pd.NaT
            except Exception:
                return pd.NaT

        try:
            # ISO (YYYY-MM-DD) e timestamps sem ambiguidade.
            parsed = pd.to_datetime(texto, yearfirst=True, errors="coerce")
            return parsed if not pd.isna(parsed) else pd.NaT
        except Exception:
            return pd.NaT

    df_out = df.copy()
    parsed = df_out[col].map(_parse_valor)
    df_out[col] = pd.to_datetime(parsed, errors="coerce")
    orientacao = "DD/MM/AAAA" if dayfirst_padrao else "MM/DD/AAAA"
    logger.info(
        "Coluna de data '%s' normalizada em %s (%s; votos BR=%d, US=%d).",
        col,
        nome_fonte or "fonte",
        orientacao,
        votos_br,
        votos_us,
    )
    return df_out


def garantir_login(df: pd.DataFrame, col: str = "LOGIN") -> pd.DataFrame:
    if col not in df.columns:
        return df.copy()
    df_copia = df.copy()
    texto = df_copia[col].astype(str).str.strip().str.upper()
    df_copia[col] = texto.mask(texto.isin({"NAN", "NONE", "N/A", "<NA>", "", "NA"}))
    return df_copia


def detectar_coluna_data(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    possiveis_nomes = [
        "DATA",
        "DATE",
        "DT",
        "DATA_OS",
        "DATA_EXECUCAO",
        "DT_EXECUCAO",
        "DATA_FINALIZACAO",
        "DT_FINALIZACAO",
        "DATA_CONSULTIVO",
        "DT_CRIACAO",
        "DATA_CRIACAO",
        "TIMESTAMP",
        "CREATED_AT",
        "UPDATED_AT",
        "PERIODO",
    ]
    colunas_norm = {str(c).upper().strip(): str(c) for c in df.columns}
    for nome in possiveis_nomes:
        if nome in colunas_norm:
            return colunas_norm[nome]
    for col in df.columns:
        col_upper = str(col).upper()
        if "DATA" in col_upper or "DT" in col_upper or "DATE" in col_upper:
            return str(col)
    for col in df.columns:
        try:
            if pd.to_datetime(df[col].head(10), errors="coerce").notna().sum() > 5:
                return str(col)
        except Exception:
            continue
    return None


@lru_cache(maxsize=16)
def _feriados_brasil(ano: int) -> tuple[date, ...]:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    ele = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ele) // 451
    mes, dia = (h + ele - 7 * m + 114) // 31, ((h + ele - 7 * m + 114) % 31) + 1
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


@lru_cache(maxsize=256)
def resumo_dias_uteis_mes(data_referencia: date) -> dict[str, Any]:
    """Dias úteis de segunda a sábado, excluindo domingo e feriado nacional."""
    inicio_mes = data_referencia.replace(day=1)
    prox_mes = (data_referencia.replace(day=28) + timedelta(4)).replace(day=1)
    fim_mes = prox_mes - timedelta(1)
    feriados_ano = _feriados_brasil(data_referencia.year)
    feriados_mes = tuple(f for f in feriados_ano if f.month == data_referencia.month)
    total = _busday_count(inicio_mes, fim_mes, feriados_ano)
    decorridos = _busday_count(inicio_mes, data_referencia, feriados_ano)
    restantes = max(0, total - decorridos)
    fator = float(total / decorridos) if decorridos > 0 else 1.0
    return {
        "inicio_mes": inicio_mes,
        "fim_mes": fim_mes,
        "total_uteis": total,
        "uteis_decorridos": decorridos,
        "uteis_restantes": restantes,
        "fator": fator,
        "feriados_do_mes": feriados_mes,
    }


@lru_cache(maxsize=256)
def _fator_por_data_max(data_max: date) -> tuple[float, int, int, int]:
    r = resumo_dias_uteis_mes(data_max)
    return r["fator"], r["uteis_restantes"], r["total_uteis"], r["uteis_decorridos"]


def data_ancora_projecao(df: pd.DataFrame, coluna_data: str = "DATA") -> date | None:
    if df.empty or coluna_data not in df.columns:
        return None
    datas = pd.to_datetime(df[coluna_data], errors="coerce").dropna()
    if datas.empty:
        return None
    return datas.max().normalize().date()


def fator_projecao(
    df: pd.DataFrame, coluna_data: str = "DATA"
) -> tuple[float, int, int, int]:
    ancora = data_ancora_projecao(df, coluna_data)
    if ancora is None:
        return 1.0, 0, 0, 0
    return _fator_por_data_max(ancora)


def calcular_atingimento_float(valor: Any, meta: float) -> float:
    v, m = _to_float_safe(valor), _to_float_safe(meta)
    return ((v / m) * 100.0) if m > 0 else 0.0


def calcular_atingimento_series(valor: pd.Series, meta: float) -> pd.Series:
    m = _to_float_safe(meta)
    if m <= 0.0:
        return pd.Series(0.0, index=valor.index, dtype=float)
    return (pd.to_numeric(valor, errors="coerce").fillna(0.0) / m) * 100.0


def classificar_semaforo(valor_projetado: Any, metas: dict[str, int]) -> str:
    """Classifica a projeção em três faixas visuais de atingimento."""
    valor = _to_float_safe(valor_projetado)
    if valor < metas["minima"]:
        return "🔴 Abaixo do mínimo"
    if valor < metas["meta_base"]:
        return "🟠 Entre mínimo e meta"
    return "🟢 Meta atingida"


def calcular_cenarios(
    realizado: Any,
    fator: float,
    variacao: float = 0.15,
) -> dict[str, int]:
    """Varia em ±15% o volume projetado ainda não realizado."""
    real = max(0, int(round(_to_float_safe(realizado))))
    fator_seguro = max(_to_float_safe(fator), 0.0)
    atual = max(real, int(real * fator_seguro))
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
    """Acrescenta cenários conservador e otimista a cada linha agrupada."""
    restante_projetado = (df[coluna_projetada] - df[coluna_real]).clip(lower=0)
    df[f"{prefixo} Conservadora"] = (
        (df[coluna_real] + restante_projetado * (1 - variacao)).round().astype(int)
    )
    df[f"{prefixo} Otimista"] = (
        (df[coluna_real] + restante_projetado * (1 + variacao)).round().astype(int)
    )
    return df


def resolver_status_atingimento(valor: Any, metas: dict[str, int]) -> tuple[str, str]:
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
        except Exception as e:
            logger.debug("Encoding %s falhou: %s", enc, e)
            continue
    raise ValueError("Falha ao decodificar.")


def _baixar_drive_csv(file_id: str) -> bytes:
    sess = http_session()
    url = "https://docs.google.com/uc?export=download"
    params: dict[str, str] = {"id": file_id}
    try:
        resp = sess.get(url, params=params, stream=True, timeout=CFG.TIMEOUT)
        resp.raise_for_status()
        token = None
        for key, value in resp.cookies.items():
            if key.startswith("download_warning"):
                token = value
                break
        if token:
            params["confirm"] = token
            resp = sess.get(url, params=params, stream=True, timeout=CFG.TIMEOUT)
            resp.raise_for_status()
        elif "text/html" in resp.headers.get("Content-Type", ""):
            text_content = resp.text
            if "<!doctype html" in text_content.lower()[:500]:
                match = re.search(r"confirm=([A-Za-z0-9_]+)", text_content)
                if match:
                    params["confirm"] = match.group(1)
                    resp = sess.get(
                        url, params=params, stream=True, timeout=CFG.TIMEOUT
                    )
                    resp.raise_for_status()
                else:
                    raise requests.exceptions.RequestException(
                        "ID inválido, arquivo privado ou limite atingido."
                    )
        return resp.content
    except Exception as e:
        logger.warning("Abordagem nativa falhou (%s). Tentando gdown...", e)
        tmp_path = ""
        try:
            from gdown.download import download as gdown_download

            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_file:
                tmp_path = tmp_file.name
            gdown_download(id=file_id, output=tmp_path, quiet=True, resume=True)
            with open(tmp_path, "rb") as handle:
                return handle.read()
        except Exception as e2:
            logger.error("gdown fallback também falhou: %s", e2)
            raise e
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    logger.debug(
                        "Não foi possível remover o arquivo temporário %s", tmp_path
                    )


@st.cache_data(ttl=CFG.CACHE_TTL_HIERARQUIA, show_spinner="Carregando Hierarquia...")
def carregar_hierarquia() -> pd.DataFrame:
    df = pd.DataFrame()
    try:
        from streamlit_gsheets import GSheetsConnection

        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(
            spreadsheet=CFG.URL_ATIVOS, worksheet=CFG.SHEET_ABA_ATIVOS, ttl=0
        )
    except (ImportError, Exception) as e:
        logger.debug("GSheetsConnection falhou: %s", e)
    if df.empty:
        try:
            resp = http_session().get(
                f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_ATIVOS}/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_ATIVOS)}",
                timeout=CFG.TIMEOUT,
            )
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        except Exception as e:
            logger.debug("HTTP fallback falhou: %s", e)
    if df.empty:
        return pd.DataFrame()
    df = mapear_colunas(
        df,
        {
            "LOGIN": ["LOGIN", "USER", "USUARIO", "MATRICULA", "ID"],
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
    df = garantir_login(df, "LOGIN").dropna(subset=["LOGIN"])
    df = df[df["LOGIN"].astype(str).str.strip() != ""]
    df = add_norm_cols(df)
    if "_LOGIN_NORM" in df.columns:
        df = df[df["_LOGIN_NORM"].str.strip() != ""].copy()
        return df.drop_duplicates(subset=["_LOGIN_NORM"], keep="first").reset_index(
            drop=True
        )
    return df.drop_duplicates(subset=["LOGIN"], keep="first").reset_index(drop=True)


@st.cache_data(ttl=CFG.CACHE_TTL_CONSULTIVO, show_spinner="Baixando Consultivos...")
def carregar_consultivos(
    cache_version: str = VERSAO,
) -> tuple[pd.DataFrame, str | None]:
    # cache_version entra na chave do cache para invalidar dados antigos quando a regra de data muda.
    logger.debug("Cache de consultivos: versão %s", cache_version)
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
                    "Date",
                ],
                "LOGIN": ["LOGIN NETSALES", "LOGIN", "USUARIO", "MATRICULA", "User"],
                "PROJETO": ["PROJETO", "CONTRATO", "Project"],
                "BASE": ["BASE", "FILIAL", "REGIONAL", "Region", "CIDADE"],
                "TECNICO": ["TECNICO", "NOME", "Technician"],
                "MONITOR": ["MONITOR", "SUPERVISOR", "Manager"],
            },
        )
        col_data_detectada = detectar_coluna_data(df)
        if col_data_detectada is None:
            return pd.DataFrame(), "Coluna DATA não encontrada em Consultivos."
        if col_data_detectada != "DATA":
            df = df.rename(columns={col_data_detectada: "DATA"})
        # A origem pode variar entre MM/DD, DD/MM e ISO; normalizar automaticamente.
        df = garantir_datetime_auto(df, col="DATA", nome_fonte="Consultivos")
        if df["DATA"].isna().all():
            return pd.DataFrame(), "Todas as datas são inválidas em Consultivos."
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Consultivos: {type(e).__name__} - {e!s}"


@st.cache_data(ttl=CFG.CACHE_TTL_PRODUCAO, show_spinner="Lendo Produção...")
def carregar_producao(cache_version: str = VERSAO) -> tuple[pd.DataFrame, str | None]:
    logger.debug("Cache de produção: versão %s", cache_version)
    try:
        resp = http_session().get(
            f"https://docs.google.com/spreadsheets/d/{CFG.SHEET_ID_PROD}/gviz/tq?tqx=out:csv&sheet={url_quote(CFG.SHEET_ABA_PROD)}",
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
        df = garantir_datetime_auto(df, col="DATA", nome_fonte="Produção")
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


def enriquecer_dados_completos(
    df: pd.DataFrame, hierarquia: pd.DataFrame
) -> pd.DataFrame:
    if df.empty or hierarquia.empty:
        return add_norm_cols(df)
    colunas_originais_antes = list(df.columns)
    df_resultado = add_norm_cols(df)
    hierarquia_copia = add_norm_cols(hierarquia.copy())
    if "_LOGIN_NORM" not in df_resultado.columns:
        df_resultado["_LOGIN_NORM"] = ""
    if "_LOGIN_NORM" not in hierarquia_copia.columns:
        hierarquia_copia["_LOGIN_NORM"] = ""
    mask_hierarquia_valida = hierarquia_copia["_LOGIN_NORM"].notna() & (
        hierarquia_copia["_LOGIN_NORM"] != ""
    )
    hierarquia_valida = hierarquia_copia.loc[mask_hierarquia_valida].drop_duplicates(
        subset=["_LOGIN_NORM"], keep="first"
    )
    if hierarquia_valida.empty:
        return df_resultado
    cols_para_merge = ["_LOGIN_NORM"] + [
        c
        for c in ["BASE", "PROJETO", "MONITOR", "TECNICO"]
        if c in hierarquia_valida.columns
    ]
    lk_lookup = hierarquia_valida[cols_para_merge].rename(
        columns={c: f"{c}_SRC" for c in cols_para_merge if c != "_LOGIN_NORM"}
    )
    df_resultado = pd.merge(df_resultado, lk_lookup, on="_LOGIN_NORM", how="left")
    for col_origem in ["BASE", "PROJETO", "MONITOR", "TECNICO"]:
        col_src = f"{col_origem}_SRC"
        if col_src in df_resultado.columns:
            if col_origem not in df_resultado.columns:
                df_resultado[col_origem] = None
            df_resultado[col_origem] = df_resultado[col_src].combine_first(
                df_resultado[col_origem]
            )
            df_resultado = df_resultado.drop(columns=[col_src])
    for col_base in ["BASE", "PROJETO", "MONITOR", "TECNICO"]:
        if col_base in df_resultado.columns:
            df_resultado[f"_{col_base}_NORM"] = (
                df_resultado[col_base].astype(str).map(normalizar_texto)
            )
    if (
        "_PROJETO_NORM" in df_resultado.columns
        and "BASE" in df_resultado.columns
        and hierarquia_valida["_PROJETO_NORM"].notna().any()
    ):
        map_projeto_base = (
            hierarquia_valida.dropna(subset=["_PROJETO_NORM", "BASE"])
            .drop_duplicates("_PROJETO_NORM")
            .set_index("_PROJETO_NORM")["BASE"]
            .to_dict()
        )
        mask_base_vazia = df_resultado["BASE"].isna() | (df_resultado["BASE"] == "")
        if mask_base_vazia.any() and map_projeto_base:
            df_resultado.loc[mask_base_vazia, "BASE"] = df_resultado.loc[
                mask_base_vazia, "_PROJETO_NORM"
            ].map(map_projeto_base)
    for c in ["BASE", "PROJETO", "TECNICO", "MONITOR"]:
        if c in df_resultado.columns:
            df_resultado[c] = df_resultado[c].fillna("Não Informado")
    colunas_perdidas = set(colunas_originais_antes) - set(df_resultado.columns)
    if colunas_perdidas:
        logger.error("COLUNAS PERDIDAS NO ENRIQUECIMENTO: %s", colunas_perdidas)
    return df_resultado


def contar_tecnicos_validos(serie: pd.Series) -> int:
    """Não conta 'Não Informado' como técnico ativo."""
    norm = serie.astype(str).map(normalizar_texto)
    validos = norm[~norm.isin(ROTULOS_VAZIOS)]
    return int(validos.nunique())


def percentual_sem_vinculo(df: pd.DataFrame, coluna: str) -> tuple[int, float]:
    if df.empty or coluna not in df.columns:
        return 0, 0.0
    norm = df[coluna].astype(str).map(normalizar_texto)
    sem = int(norm.isin(ROTULOS_VAZIOS).sum())
    return sem, (sem / len(df) * 100.0) if len(df) else 0.0


def duplicatas_os(df: pd.DataFrame) -> int:
    if df.empty or "NUM_OS" not in df.columns:
        return 0
    serie = df["NUM_OS"].astype(str).str.strip()
    serie = serie[~serie.map(normalizar_texto).isin(ROTULOS_VAZIOS)]
    if serie.empty:
        return 0
    return int(serie.duplicated().sum())


def render_tabela_segura(df: pd.DataFrame, **kwargs: Any) -> None:
    """Exibe colunas de data como DD/MM/AAAA sem alterar os dados de cálculo.

    A coluna DATA pode chegar como datetime ou como texto MM/DD/AAAA. O parser
    da cópia de apresentação interpreta texto de origem em padrão US e converte
    só essa cópia para texto brasileiro.
    """
    df_display = df.copy()
    for col in df_display.columns:
        nome_coluna = normalizar_texto(col)
        eh_coluna_data = (
            nome_coluna in {"DATA", "DATE", "DATA/HORA", "DATA HORA"}
            or nome_coluna.startswith("DATA_")
            or nome_coluna.startswith("DATA ")
            or nome_coluna.endswith("_DATA")
        )
        if not eh_coluna_data:
            continue

        if pd.api.types.is_datetime64_any_dtype(df_display[col]):
            serie = pd.to_datetime(df_display[col], errors="coerce")
        else:
            serie = garantir_datetime(
                df_display[[col]].rename(columns={col: "DATA"}),
                col="DATA",
                origem="us",
            )["DATA"]

        tem_hora = (
            bool(
                (
                    serie.dropna().dt.hour.ne(0)
                    | serie.dropna().dt.minute.ne(0)
                    | serie.dropna().dt.second.ne(0)
                ).any()
            )
            if serie.notna().any()
            else False
        )
        formato = "%d/%m/%Y %H:%M" if tem_hora else "%d/%m/%Y"
        df_display[col] = serie.dt.strftime(formato).fillna("-")

    try:
        render_table_html(df_display, **kwargs)
    except TypeError:
        kwargs.pop("color_rules", None)
        kwargs.pop("colunas_num", None)
        kwargs.pop("alinhamentos", None)
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
    """
    Realizado é fato. A cor de status fica na projeção, para o início do mês
    não parecer crítico só porque a meta mensal ainda não foi acumulada.
    Faltantes = Meta - Realizado. Se já passou da meta, mostra o excedente.
    """
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
    status_nome = (
        resolver_status_atingimento(projetado, metas)[0]
        if metas
        else ("Meta Atingida" if projetado >= meta else "Abaixo da meta")
    )

    c1, c2, c3 = st.columns(3, gap="large")
    render_kpi(
        c1,
        label=label_realizado,
        valor=_fmt_int(realizado),
        sub=f"{pct_real:.1f}% da meta mensal",
        tema="azul",
        icone="✅",
    )
    render_kpi(
        c2,
        label=label_projetado,
        valor=_fmt_int(projetado),
        sub=f"{status_nome} • {pct_proj:.1f}% da meta",
        tema=tema_proj,
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
        label=f"Progresso {titulo}",
        mostrar_valor=True,
        tema=tema_progresso,
        altura="medio",
    )

    gap = _to_float_safe(faltantes)
    if dias_restantes <= 0:
        render_insight(
            f"Período de dias úteis encerrado para {titulo.lower()}.",
            tipo="info",
        )
        return

    n_cols = 3 if tecnico_dia is not None else 2
    cols = st.columns(n_cols, gap="large")
    if gap <= 0:
        render_kpi(
            cols[0],
            label="EXCEDENTE",
            valor=_fmt_int(abs(gap)),
            sub="Realizado já cobre a meta",
            tema="verde",
            icone="✅",
        )
    else:
        render_kpi(
            cols[0],
            label=label_faltantes,
            valor=_fmt_int(gap),
            sub="Meta − Realizado",
            tema="vermelho",
            icone="⚠️",
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


def coletar_alertas(
    df_prod: pd.DataFrame,
    df_cons: pd.DataFrame,
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

    ancoras = [
        d
        for d in (
            data_ancora_projecao(df_prod, "DATA"),
            data_ancora_projecao(df_cons, "DATA"),
        )
        if d is not None
    ]
    if ancoras:
        mais_atrasada = min(ancoras)
        atraso = (hoje - mais_atrasada).days
        if atraso >= 2:
            alertas.append(
                (
                    f"Fonte desatualizada: a última data da fonte mais atrasada é {formatar_data_br(mais_atrasada)} ({atraso} dias atrás).",
                    "alerta",
                )
            )
    elif df_prod.empty and df_cons.empty:
        alertas.append(
            ("Nenhuma linha de produção ou consultivo no recorte atual.", "critico")
        )

    for nome, df in (("produção", df_prod), ("consultivos", df_cons)):
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

    dups = duplicatas_os(df_prod)
    if dups > 0:
        alertas.append(
            (
                f"{_fmt_int(dups)} linhas de produção repetem NUM_OS. O volume continua contando linhas, não O.S. distintas.",
                "info",
            )
        )

    if not resumo.empty and "Agrupamento" in resumo.columns:
        nomes_acompanhados = {
            normalizar_texto(x) for x in (*BASES_PRIORITARIAS, *PROJETOS_NET)
        }
        for _, row in resumo.iterrows():
            nome = str(row.get("Agrupamento", "—"))
            if normalizar_texto(nome) not in nomes_acompanhados:
                continue
            os_proj = _to_float_safe(row.get("O.S. Projetadas"))
            os_real = _to_float_safe(row.get("OS_Volume"))
            cons_proj = _to_float_safe(row.get("Consultivos Projetados"))
            cons_real = _to_float_safe(row.get("Cons_Volume"))
            if os_real > 0 and os_proj < METAS_PRODUCAO_OS_BASE["minima"]:
                alertas.append(
                    (
                        f"{nome}: projeção de O.S. em {_fmt_int(os_proj)}, abaixo do mínimo de {_fmt_int(METAS_PRODUCAO_OS_BASE['minima'])}.",
                        "critico",
                    )
                )
            elif os_real > 0 and os_proj < METAS_PRODUCAO_OS_BASE["meta_base"]:
                alertas.append(
                    (
                        f"{nome}: projeção de O.S. em {_fmt_int(os_proj)}, ainda abaixo da meta de {_fmt_int(METAS_PRODUCAO_OS_BASE['meta_base'])}.",
                        "alerta",
                    )
                )
            if cons_real > 0 and cons_proj < METAS_CONSULTIVO_BASE["minima"]:
                alertas.append(
                    (
                        f"{nome}: projeção de consultivos em {_fmt_int(cons_proj)}, abaixo do mínimo de {_fmt_int(METAS_CONSULTIVO_BASE['minima'])}.",
                        "critico",
                    )
                )
            elif cons_real > 0 and cons_proj < METAS_CONSULTIVO_BASE["meta_base"]:
                alertas.append(
                    (
                        f"{nome}: projeção de consultivos em {_fmt_int(cons_proj)}, abaixo da meta de {_fmt_int(METAS_CONSULTIVO_BASE['meta_base'])}.",
                        "alerta",
                    )
                )
        presentes = {normalizar_texto(x) for x in resumo["Agrupamento"].astype(str)}
        for base in BASES_PRIORITARIAS:
            if normalizar_texto(base) not in presentes:
                alertas.append(
                    (f"{base} não aparece no agrupamento deste recorte.", "alerta")
                )

    return alertas


df_hierarquia_raw = carregar_hierarquia()
df_cons_raw, erro_cons = carregar_consultivos(VERSAO)
df_prod_raw, erro_prod = carregar_producao(VERSAO)
df_prod = enriquecer_dados_completos(df_prod_raw, df_hierarquia_raw)
df_cons = enriquecer_dados_completos(df_cons_raw, df_hierarquia_raw)

if not df_prod.empty and any(
    c not in df_prod.columns for c in ["DATA", "LOGIN", "BASE", "PROJETO"]
):
    st.error(
        "Colunas críticas perdidas em Produção: "
        + ", ".join(
            c for c in ["DATA", "LOGIN", "BASE", "PROJETO"] if c not in df_prod.columns
        )
    )
    st.stop()


def obter_param_url(chave: str) -> list[str]:
    try:
        return list(st.query_params.get_all(chave))
    except AttributeError:
        return []


def atualizar_param_url(chave: str, key_widget: str) -> None:
    try:
        st.query_params[chave] = st.session_state.get(key_widget, [])
    except AttributeError:
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
st.sidebar.caption(f"Produção: {_fmt_int(len(df_prod))} linhas")
st.sidebar.caption(f"Consultivos: {_fmt_int(len(df_cons))} linhas")
st.sidebar.caption(f"Hierarquia: {_fmt_int(len(df_hierarquia_raw))} logins")
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
    obter_param_url("projeto") or default_proj,
    key="ui_proj",
    on_change=atualizar_param_url,
    args=("projeto", "ui_proj"),
)
filtro_base = st.sidebar.multiselect(
    "Filial / Regional",
    all_bases,
    obter_param_url("base"),
    key="ui_base",
    on_change=atualizar_param_url,
    args=("base", "ui_base"),
)
filtro_monitor = st.sidebar.multiselect(
    "Supervisor / Monitor",
    all_monitores,
    obter_param_url("monitor"),
    key="ui_monitor",
    on_change=atualizar_param_url,
    args=("monitor", "ui_monitor"),
)
todas_datas = (
    pd.concat([df_prod["DATA"], df_cons["DATA"]]).dropna()
    if "DATA" in df_prod.columns and "DATA" in df_cons.columns
    else pd.Series(dtype="datetime64[ns]")
)
hoje_tz = datetime.now(CFG.TZ).date()
data_min_disponivel, data_max = (hoje_tz - timedelta(30), hoje_tz)
if not todas_datas.empty:
    data_min_disponivel = pd.to_datetime(todas_datas.min()).date()
    data_max = pd.to_datetime(todas_datas.max()).date()

# Metas são mensais: por padrão, inicia no primeiro dia do mês mais recente
# disponível, em vez de acumular todo o histórico contra uma meta de um mês.
data_min = max(data_max.replace(day=1), data_min_disponivel)
raw_filtro_datas = st.sidebar.date_input(
    "Janela Temporal",
    (data_min, data_max),
    data_min_disponivel,
    data_max,
    format="DD/MM/YYYY",
    key="janela_temporal_v450",
)
_filtro_datas_safe: tuple[date, date] | None = None
if isinstance(raw_filtro_datas, (tuple, list)):
    if len(raw_filtro_datas) >= 2:
        _filtro_datas_safe = (raw_filtro_datas[0], raw_filtro_datas[1])
    elif len(raw_filtro_datas) == 1:
        _filtro_datas_safe = (raw_filtro_datas[0], raw_filtro_datas[0])
elif isinstance(raw_filtro_datas, date):
    _filtro_datas_safe = (raw_filtro_datas, raw_filtro_datas)
render_sidebar_divider(espacamento="medio")
if st.sidebar.button("Atualizar bases", use_container_width=True):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()
render_sidebar_footer_info(versao=f"v{VERSAO}")


def filtrar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df = df.copy()
    mask = pd.Series(True, index=df.index)
    if "DATA" not in df.columns:
        col_data_alt = detectar_coluna_data(df)
        if col_data_alt:
            df = df.rename(columns={col_data_alt: "DATA"})
    if filtro_base and "BASE" in df.columns:
        mask &= df["BASE"].isin(filtro_base)
    if filtro_monitor and "MONITOR" in df.columns:
        mask &= df["MONITOR"].isin(filtro_monitor)
    if filtro_projeto and "PROJETO" in df.columns:
        mask &= df["PROJETO"].isin(filtro_projeto)
    if _filtro_datas_safe and "DATA" in df.columns:
        inicio, fim = _filtro_datas_safe
        sdt = pd.to_datetime(df["DATA"], errors="coerce").dt.normalize()
        mask &= (sdt >= pd.Timestamp(inicio)) & (sdt <= pd.Timestamp(fim))
    return df.loc[mask].copy()


df_prod_f = filtrar_dataframe(df_prod)
df_cons_f = filtrar_dataframe(df_cons)
fator_global_os, dias_rest_os, dias_tot_os, dias_trab_os = (
    fator_projecao(df_prod_f, "DATA") if "DATA" in df_prod_f.columns else (1.0, 0, 0, 0)
)
fator_global_cons, dias_rest_c, dias_tot_c, dias_trab_c = (
    fator_projecao(df_cons_f, "DATA") if "DATA" in df_cons_f.columns else (1.0, 0, 0, 0)
)
ancora_os = data_ancora_projecao(df_prod_f, "DATA")
ancora_cons = data_ancora_projecao(df_cons_f, "DATA")
_data_inicio_str = formatar_data_br(
    _filtro_datas_safe[0] if _filtro_datas_safe else data_min
)
_data_fim_str = formatar_data_br(
    _filtro_datas_safe[1] if _filtro_datas_safe else data_max
)
_periodo_multimes = bool(
    _filtro_datas_safe
    and (
        _filtro_datas_safe[0].year != _filtro_datas_safe[1].year
        or _filtro_datas_safe[0].month != _filtro_datas_safe[1].month
    )
)

render_hero_totale_2(
    titulo="Painel Consolidado de Metas",
    subtitulo="O que já foi feito, o que a projeção fecha e onde a meta não cabe",
    badge_texto=f"Período: {_data_inicio_str} até {_data_fim_str}",
)
st.caption(
    "Dias úteis: segunda a sábado, sem domingo e sem feriado nacional. "
    f"Projeção de O.S. ancorada em {formatar_data_br(ancora_os)} "
    f"({dias_trab_os} decorridos / {dias_tot_os} no mês, {dias_rest_os} restantes). "
    "Faltantes = Meta − Realizado."
)
for err in (erro_prod, erro_cons):
    if err:
        render_insight(f"Atenção na carga de dados: {err}", tipo="alerta")
if _periodo_multimes:
    render_insight(
        "O período selecionado inclui mais de um mês, mas as metas configuradas são mensais. "
        "Para uma projeção comparável à meta, selecione um único mês.",
        tipo="alerta",
    )

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

k_os, k_cons, k_ritmo = st.columns(3, gap="large")
render_kpi(
    k_os,
    label="O.S. NO RECORTE",
    valor=_fmt_int(real_prod),
    sub=f"Projeção {_fmt_int(proj_prod)} • meta {_fmt_int(meta_prod)}",
    tema=tema_kpi_de_valor(proj_prod, METAS_PRODUCAO_OS_GERAL),
    icone="📊",
)
render_kpi(
    k_cons,
    label="CONSULTIVOS NO RECORTE",
    valor=_fmt_int(real_cons),
    sub=f"Projeção {_fmt_int(proj_cons)} • meta {_fmt_int(meta_cons)}",
    tema=tema_kpi_de_valor(proj_cons, METAS_CONSULTIVO_GERAL),
    icone="💼",
)
render_kpi(
    k_ritmo,
    label="RITMO PARA FECHAR A META",
    valor=_fmt_dec(os_media_diaria_geral),
    sub=f"O.S./dia útil • consultivos {_fmt_dec(cons_media_diaria_geral)}/dia",
    tema="roxo",
    icone="📅",
)


cenarios_os = calcular_cenarios(real_prod, fator_global_os)
cenarios_cons = calcular_cenarios(real_cons, fator_global_cons)

render_section_header(
    titulo="Cenários de fechamento",
    icone="🔮",
    subtitulo="Compare o fechamento estimado com a meta mensal em três ritmos de produção.",
)
st.caption(
    "Conservador e otimista variam em 15% o volume projetado ainda não realizado. "
    "O cenário atual mantém a projeção linear."
)


def _status_cenario(valor: int, metas: dict[str, int]) -> str:
    nome, _ = resolver_status_atingimento(valor, metas)
    if nome == "Alta Performance":
        return "🟢 Alta performance"
    if nome == "Meta Atingida":
        return "🟢 Meta projetada"
    if nome == "Atenção / Mínimo":
        return "🟠 No mínimo"
    return "🔴 Abaixo do mínimo"


df_cenarios = pd.DataFrame(
    [
        {
            "Indicador": "📊 O.S.",
            "Meta mensal": meta_prod,
            "Conservador": cenarios_os["Conservador"],
            "Atual": cenarios_os["Atual"],
            "Otimista": cenarios_os["Otimista"],
            "% da meta (atual)": calcular_atingimento_float(
                cenarios_os["Atual"], meta_prod
            ),
            "Status atual": _status_cenario(
                cenarios_os["Atual"], METAS_PRODUCAO_OS_GERAL
            ),
        },
        {
            "Indicador": "💼 Consultivos",
            "Meta mensal": meta_cons,
            "Conservador": cenarios_cons["Conservador"],
            "Atual": cenarios_cons["Atual"],
            "Otimista": cenarios_cons["Otimista"],
            "% da meta (atual)": calcular_atingimento_float(
                cenarios_cons["Atual"], meta_cons
            ),
            "Status atual": _status_cenario(
                cenarios_cons["Atual"], METAS_CONSULTIVO_GERAL
            ),
        },
    ]
)

# Formatação localizada e destaque visual por cenário.
_cenario_styler = (
    df_cenarios.style.format(
        {
            "Meta mensal": lambda valor: _fmt_int(valor),
            "Conservador": lambda valor: _fmt_int(valor),
            "Atual": lambda valor: _fmt_int(valor),
            "Otimista": lambda valor: _fmt_int(valor),
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
st.dataframe(
    _cenario_styler,
    hide_index=True,
    use_container_width=True,
    height=185,
)


def processar_resumo_agrupado(
    prod: pd.DataFrame, cons: pd.DataFrame, ft_os: float, ft_cons: float
) -> pd.DataFrame:
    if not prod.empty and all(
        c in prod.columns for c in ["CHAVE_AGRUPAMENTO", "DATA", "TECNICO"]
    ):
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
    if "Agrupamento_C" in m.columns:
        m["Agrupamento"] = m["Agrupamento"].fillna(m["Agrupamento_C"])
        m = m.drop(columns=["Agrupamento_C"])
    m["Agrupamento"] = m["Agrupamento"].fillna("Não Informado")
    if "CHAVE_AGRUPAMENTO" in m.columns:
        m = m.drop(columns=["CHAVE_AGRUPAMENTO"])
    for col in ["OS_Volume", "Cons_Volume", "Tecnicos_Ativos"]:
        if col in m.columns:
            m[col] = m[col].fillna(0).astype(int)
        else:
            m[col] = 0
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
    m["% Meta O.S. (Proj)"] = np.round(
        calcular_atingimento_series(
            m["O.S. Projetadas"], float(METAS_PRODUCAO_OS_BASE["meta_base"])
        ),
        1,
    )
    m["% Meta Cons. (Proj)"] = np.round(
        calcular_atingimento_series(
            m["Consultivos Projetados"], float(METAS_CONSULTIVO_BASE["meta_base"])
        ),
        1,
    )
    m["Status O.S."] = m["O.S. Projetadas"].apply(
        lambda valor: classificar_semaforo(valor, METAS_PRODUCAO_OS_BASE)
    )
    m["Status Consultivos"] = m["Consultivos Projetados"].apply(
        lambda valor: classificar_semaforo(valor, METAS_CONSULTIVO_BASE)
    )
    m = adicionar_cenarios_agrupados(m, "OS_Volume", "O.S. Projetadas", "O.S.")
    m = adicionar_cenarios_agrupados(
        m, "Cons_Volume", "Consultivos Projetados", "Consultivos"
    )
    m["_ordem"] = np.where(m["OS_Volume"] > 0, m["% Meta O.S. (Proj)"], 999.0)
    m = m.sort_values(["_ordem", "Agrupamento"], ascending=[True, True]).drop(
        columns=["_ordem"]
    )
    return m.reset_index(drop=True)


df_prod_para_resumo = df_prod_f.copy()
df_cons_para_resumo = df_cons_f.copy()
if not df_prod_para_resumo.empty and "PROJETO" in df_prod_para_resumo.columns:
    df_prod_para_resumo["CHAVE_AGRUPAMENTO"] = df_prod_para_resumo["PROJETO"]
if not df_cons_para_resumo.empty and "BASE" in df_cons_para_resumo.columns:
    df_cons_para_resumo["CHAVE_AGRUPAMENTO"] = df_cons_para_resumo["BASE"]
df_resumo_agrupado = processar_resumo_agrupado(
    df_prod_para_resumo, df_cons_para_resumo, fator_global_os, fator_global_cons
)

tabs = st.tabs(
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
(
    tab_prod,
    tab_cons,
    tab_bases,
    tab_monitores,
    tab_alertas,
    tab_abcdm,
    tab_leste,
    tab_guarulhos,
) = tabs

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

with tab_bases:
    render_section_header(
        titulo="Visão Agrupada",
        icone="🗂️",
        subtitulo="Produção por projeto e consultivos por base, do pior fechamento projetado para o melhor",
    )
    st.caption(
        f"Meta de O.S. por agrupamento: {_fmt_int(METAS_PRODUCAO_OS_BASE['meta_base'])}. "
        f"Meta de consultivos: {_fmt_int(METAS_CONSULTIVO_BASE['meta_base'])}. "
        "Faltantes = Meta − Realizado, nunca a projeção."
    )
    if not df_resumo_agrupado.empty:
        df_display = df_resumo_agrupado[
            [
                "Agrupamento",
                "OS_Volume",
                "O.S. Projetadas",
                "O.S. Conservadora",
                "O.S. Otimista",
                "O.S. Faltantes",
                "% Meta O.S. (Proj)",
                "Status O.S.",
                "Cons_Volume",
                "Consultivos Projetados",
                "Consultivos Conservadora",
                "Consultivos Otimista",
                "Cons. Faltantes",
                "% Meta Cons. (Proj)",
                "Status Consultivos",
                "Tecnicos_Ativos",
            ]
        ].rename(columns={"OS_Volume": "O.S. Real", "Cons_Volume": "Cons. Real"})
        regras_os: dict[str, str] = {}
        regras_cons: dict[str, str] = {}
        for valor in df_display["% Meta O.S. (Proj)"].dropna().unique():
            regras_os[str(valor)] = "sucesso" if float(valor) >= 100 else "alerta"
        for valor in df_display["% Meta Cons. (Proj)"].dropna().unique():
            regras_cons[str(valor)] = "sucesso" if float(valor) >= 100 else "alerta"
        render_tabela_segura(
            df_display,
            fmt={
                "O.S. Real": "{:,.0f}",
                "O.S. Projetadas": "{:,.0f}",
                "O.S. Conservadora": "{:,.0f}",
                "O.S. Otimista": "{:,.0f}",
                "O.S. Faltantes": "{:,.0f}",
                "% Meta O.S. (Proj)": "{:.1f}%",
                "Cons. Real": "{:,.0f}",
                "Consultivos Projetados": "{:,.0f}",
                "Consultivos Conservadora": "{:,.0f}",
                "Consultivos Otimista": "{:,.0f}",
                "Cons. Faltantes": "{:,.0f}",
                "% Meta Cons. (Proj)": "{:.1f}%",
                "Tecnicos_Ativos": "{:,.0f}",
            },
            colunas_num=[
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
            ],
            color_rules={
                "% Meta O.S. (Proj)": regras_os,
                "% Meta Cons. (Proj)": regras_cons,
            },
        )
        render_botao_exportacao(df_resumo_agrupado, "Resumo_Agrupado")
    else:
        render_empty_state(tipo="dados", titulo="Sem dados para a visão agrupada.")


def render_aba_projecao_base(tab: DeltaGenerator, base_nome: str) -> None:
    with tab:
        render_section_header(
            titulo=f"Projeção de Desempenho — {base_nome}",
            icone="📈",
            subtitulo="Ritmo necessário para a meta. Faltantes = Meta − Realizado.",
        )
        if df_resumo_agrupado.empty:
            render_empty_state(
                tipo="dados",
                titulo="Sem dados para projeção",
                descricao="Não existem dados disponíveis para o período selecionado.",
            )
            return

        b_data = df_resumo_agrupado[
            df_resumo_agrupado["Agrupamento"].astype(str).str.strip().str.upper()
            == base_nome.strip().upper()
        ]
        if b_data.empty:
            disponiveis = ", ".join(
                df_resumo_agrupado["Agrupamento"].astype(str).head(8).tolist()
            )
            render_empty_state(
                tipo="filtro",
                titulo="Agrupamento sem dados",
                descricao=(
                    f"'{base_nome}' não está neste recorte. "
                    f"Agrupamentos disponíveis: {disponiveis or 'nenhum'}."
                ),
            )
            return

        try:
            os_real = _to_float_safe(b_data["OS_Volume"].iloc[0])
            os_projetado = _to_float_safe(b_data["O.S. Projetadas"].iloc[0])
            cons_real = _to_float_safe(b_data["Cons_Volume"].iloc[0])
            cons_projetado = _to_float_safe(b_data["Consultivos Projetados"].iloc[0])
            tecnicos_base = max(
                1, int(_to_float_safe(b_data["Tecnicos_Ativos"].iloc[0], default=1))
            )
        except (IndexError, KeyError, ValueError, TypeError) as exc:
            render_insight(
                f"Erro ao processar os dados de {base_nome}: {exc}", tipo="critico"
            )
            return

        meta_os = float(METAS_PRODUCAO_OS_BASE["meta_base"])
        meta_cons_base = float(METAS_CONSULTIVO_BASE["meta_base"])

        render_section_header(
            titulo="Parâmetros da Operação",
            icone="⚙️",
            subtitulo="Ajuste manual da força de trabalho. 'Não Informado' não entra na contagem detectada.",
        )
        c_cfg1, c_cfg2 = st.columns([1, 2], gap="large")
        with c_cfg1:
            tecnicos_ativos = st.number_input(
                "Número de técnicos ativos",
                min_value=1,
                max_value=1000,
                value=tecnicos_base,
                step=1,
                key=f"tecnicos_manuais_{base_nome}",
                help="Altere para recalcular a média por técnico/dia.",
            )
        with c_cfg2:
            render_insight(
                f"{base_nome}: {tecnicos_base} técnicos válidos na hierarquia. "
                f"Dias úteis restantes — O.S.: {dias_rest_os}; consultivos: {dias_rest_c}. "
                f"Projeção ancorada em {formatar_data_br(ancora_os)}.",
                tipo="info",
            )
        st.divider()

        os_faltantes = meta_os - os_real
        os_media_diaria = max(os_faltantes, 0) / dias_rest_os if dias_rest_os > 0 else 0
        os_por_tecnico = os_media_diaria / tecnicos_ativos if tecnicos_ativos > 0 else 0
        render_resumo_cards(
            titulo="Produção (O.S.)",
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
            tecnico_dia=os_por_tecnico,
            ancora=ancora_os,
        )
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

        cons_faltantes = meta_cons_base - cons_real
        cons_media_diaria = (
            max(cons_faltantes, 0) / dias_rest_c if dias_rest_c > 0 else 0
        )
        render_resumo_cards(
            titulo="Consultivos",
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
            ancora=ancora_cons,
        )


render_aba_projecao_base(tab_abcdm, "NET-ABCDM")
render_aba_projecao_base(tab_leste, "NET-LESTE")
render_aba_projecao_base(tab_guarulhos, "NET-GUARULHOS")

with tab_monitores:
    render_section_header(
        titulo="Desempenho por Supervisor",
        icone="👔",
        subtitulo="Volume de O.S. e consultivos no mesmo recorte",
    )
    if df_prod_f.empty and df_cons_f.empty:
        render_empty_state(
            tipo="dados",
            titulo="Sem dados de supervisores",
            descricao="Nenhum registro disponível no período.",
        )
    else:
        partes: list[pd.DataFrame] = []
        if not df_prod_f.empty and "MONITOR" in df_prod_f.columns:
            partes.append(
                df_prod_f.groupby("MONITOR").size().rename("OS_Equipe").reset_index()
            )
        if not df_cons_f.empty and "MONITOR" in df_cons_f.columns:
            partes.append(
                df_cons_f.groupby("MONITOR").size().rename("Consultivos").reset_index()
            )
        if not partes:
            render_empty_state(
                tipo="dados",
                titulo="Sem coluna de monitor",
                descricao="A hierarquia não trouxe supervisor para este recorte.",
            )
        else:
            df_mon = partes[0]
            for parte in partes[1:]:
                df_mon = pd.merge(df_mon, parte, on="MONITOR", how="outer")
            for col in ("OS_Equipe", "Consultivos"):
                if col not in df_mon.columns:
                    df_mon[col] = 0
                df_mon[col] = df_mon[col].fillna(0).astype(int)
            total_os = int(df_mon["OS_Equipe"].sum())
            if total_os:
                participacao = (df_mon["OS_Equipe"] / total_os * 100.0).round(1)
            else:
                participacao = 0.0
            df_mon["Participação O.S. (%)"] = participacao
            df_mon = df_mon.sort_values(["OS_Equipe", "Consultivos"], ascending=False)
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
        titulo="Central de Alertas",
        icone="🚨",
        subtitulo="O que impede o fechamento da meta neste recorte",
        badge="Monitoramento",
        badge_tipo="erro",
    )
    alertas = coletar_alertas(
        df_prod_f, df_cons_f, df_resumo_agrupado, erro_prod, erro_cons, hoje_tz
    )
    if not alertas:
        render_insight(
            "Nenhum desvio relevante: cargas ok, vínculo aceitável e projeções dentro da meta.",
            tipo="ok",
        )
    else:
        criticos = sum(1 for _, tipo in alertas if tipo == "critico")
        render_insight(
            f"{len(alertas)} pontos de atenção, {criticos} críticos. Priorize os críticos.",
            tipo="critico" if criticos else "alerta",
        )
        for mensagem, tipo in alertas[:12]:
            render_insight(mensagem, tipo=tipo)
        if len(alertas) > 12:
            st.caption(
                f"Mais {len(alertas) - 12} alertas omitidos para não poluir a leitura."
            )
            