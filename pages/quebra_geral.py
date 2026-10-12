"""
quebra.py
=========
Super Relatório Corporativo Unificado | Quebra Operacional TOTALE

Versão: 5.4.0 (Busca Avançada no Google Sheets + Conversão Login -> Nome do Técnico/Monitor)
Author: TOTALE Tecnologia
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import logging
import re
import sys
import unicodedata
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Final, Literal, cast

import numpy as np
import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Bootstrap de caminhos antes dos imports locais.
_DIR: Final[Path] = Path(__file__).resolve().parent
_ROOT: Final[Path] = _DIR.parent
for _path in (_DIR, _ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

logger = logging.getLogger(__name__)

TemaKPI = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo", "amarelo", "escuro"
]
TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]


@dataclass
class ModuloCriterios:
    """Encapsula o módulo opcional de critérios."""

    disponivel: bool = False
    termos_nd: tuple[str, ...] = ("ADESAO", "ADESÃO")
    termo_gpon: str = "PON"
    termo_migracao: str = "MUDANCA DE PACOTE"
    termo_pme: str = "PME"
    vazios_gerais: set[str] = field(default_factory=set)
    classificar: Callable[..., Any] | None = None
    criar_flag_gpon: Callable[..., Any] | None = None
    detect_tipo_os: Callable[..., Any] | None = None
    detect_habilidade: Callable[..., Any] | None = None
    detect_flag_gpon: Callable[..., Any] | None = None
    render_painel: Callable[..., Any] | None = None


def _carregar_criterios() -> ModuloCriterios:
    try:
        from components import criterios as c  # type: ignore

        return ModuloCriterios(
            disponivel=True,
            termos_nd=c.TERMOS_ND,
            termo_gpon=c.TERMO_GPON_HABILIDADE,
            termo_migracao=c.TERMO_MIGRACAO_OS,
            termo_pme=c.TERMO_PME_HABILIDADE,
            vazios_gerais=c.VAZIOS_GERAIS,
            classificar=c.classificar_tipo_servico,
            criar_flag_gpon=c.criar_flag_gpon,
            detect_tipo_os=c.detectar_col_tipo_os_1,
            detect_habilidade=c.detectar_col_habilidade,
            detect_flag_gpon=c.detectar_col_flag_gpon,
            render_painel=c.render_painel_criterios,
        )
    except ImportError as erro:
        logger.warning("Módulo critérios não disponível: %s", erro)
        return ModuloCriterios()


CRITERIOS: Final[ModuloCriterios] = _carregar_criterios()


@dataclass
class ComponentesVisuais:
    """Componentes de UI opcionais."""

    disponivel: bool = False
    section_header: Callable[..., Any] | None = None
    sidebar_brand: Callable[..., Any] | None = None
    table_html: Callable[..., Any] | None = None
    insight: Callable[..., Any] | None = None
    kpi: Callable[..., Any] | None = None
    kpi_sm: Callable[..., Any] | None = None
    theme_selector: Callable[..., Any] | None = None


def _carregar_componentes() -> ComponentesVisuais:
    try:
        from components import componentes as m  # type: ignore

        return ComponentesVisuais(
            disponivel=True,
            section_header=getattr(m, "render_section_header", None),
            sidebar_brand=getattr(m, "render_sidebar_brand", None),
            table_html=getattr(m, "render_table_html", None),
            insight=getattr(m, "render_insight", None),
            kpi=getattr(m, "render_kpi", None),
            kpi_sm=getattr(m, "render_kpi_sm", None),
            theme_selector=getattr(m, "render_page_sidebar_theme_selector", None),
        )
    except ImportError as erro:
        logger.warning("Módulo componentes não disponível: %s", erro)
        return ComponentesVisuais()


COMPONENTES: Final[ComponentesVisuais] = _carregar_componentes()


def _carregar_robo() -> tuple[Callable[..., Any] | None, str]:
    try:
        module = importlib.import_module("robo.robo_local")
        funcao = getattr(module, "renderizar_robo_local", None) or getattr(
            module, "render_robo_local", None
        )
        if callable(funcao):
            return funcao, f"OK ({getattr(module, '__file__', '?')})"
        return None, "Função de renderização não encontrada."
    except Exception as erro:
        logger.debug("Robô local não pôde ser importado.", exc_info=True)
        return None, f"{type(erro).__name__}: {erro}"


_ROBO_FN, _ROBO_ERRO = _carregar_robo()
ROBO_DISPONIVEL: bool = _ROBO_FN is not None


from config.settings import (
    SHEET_ABA_ATIVOS as _DEFAULT_WORKSHEET_ATIVOS,
)
from config.settings import (
    SHEET_ID_ATIVOS as _DEFAULT_SHEET_ID_ATIVOS,
)
from config.settings import (
    URL_ATIVOS_EDIT as _DEFAULT_URL_LISTA_ATIVOS,
)
from config.settings import (
    url_gsheets_export,
    url_gsheets_gviz_csv,
)


class Config:
    """Constantes de negócio e visuais."""

    SLA_QUEBRA_MAXIMA: Final[float] = 0.20
    SLA_MIGRACAO_MAXIMA: Final[float] = 0.25
    URL_LISTA_ATIVOS: Final[str] = _DEFAULT_URL_LISTA_ATIVOS
    SHEET_ID_ATIVOS: Final[str] = _DEFAULT_SHEET_ID_ATIVOS
    WORKSHEET_ATIVOS: Final[str] = _DEFAULT_WORKSHEET_ATIVOS
    STATUS_ORDEM: Final[tuple[str, ...]] = ("Executada", "Não Executada", "Pendente")
    ORDEM_TIPOS: Final[tuple[str, ...]] = (
        "Novos Domicílios",
        "PME",
        "Migração",
        "Outros",
    )
    COLUNAS_TIPO_SERVICO: Final[tuple[str, ...]] = (
        "TIPO_SERVICO",
        "TIPO SERVICO",
        "TIPO O.S 1",
        "TIPO OS 1",
        "TIPO O.S. 1",
    )
    CORES_STATUS: Final[dict[str, str]] = {
        "Executada": "#10B981",
        "Não Executada": "#EF4444",
        "Pendente": "#94A3B8",
    }
    CORES_TIPO: Final[dict[str, str]] = {
        "Novos Domicílios": "#1E40AF",
        "PME": "#7C3AED",
        "Migração": "#0369A1",
        "Quebra Geral": "#78350F",
        "Outros": "#64748B",
    }


class Fontes:
    TITULO: Final[str] = (
        "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    )
    TEXTO: Final[str] = (
        "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    )


_CODIGOS_NAO_EXECUTADA: Final[tuple[int, ...]] = (
    100,
    101,
    103,
    104,
    105,
    106,
    107,
    108,
    110,
    112,
    113,
    114,
    125,
    203,
    204,
    205,
    206,
    301,
    302,
    303,
    305,
    306,
    307,
    308,
    312,
    316,
    400,
    402,
)
_CODIGOS_EXECUTADA: Final[tuple[int, ...]] = (
    128,
    328,
    408,
    409,
    425,
    430,
    440,
    467,
    470,
    474,
    475,
    477,
    *range(500, 591),
)
MAPA_CODIGO_NUMERICO: Final[dict[int, str]] = {
    **{c: "Não Executada" for c in _CODIGOS_NAO_EXECUTADA},
    **{c: "Executada" for c in _CODIGOS_EXECUTADA},
}
CORES_REGIAO: Final[dict[str, dict[str, str]]] = {
    "LESTE": {"bg": "#EFF6FF", "text": "#1E40AF", "border": "#BFDBFE"},
    "GRU": {"bg": "#ECFDF5", "text": "#047857", "border": "#A7F3D0"},
    "ABCDM": {"bg": "#F5F3FF", "text": "#6D28D9", "border": "#DDD6FE"},
    "OUTRAS": {"bg": "#F8FAFC", "text": "#475569", "border": "#CBD5E1"},
}
CIDADES_LESTE: Final[frozenset[str]] = frozenset({"SAO PAULO"})
CIDADES_GRU: Final[frozenset[str]] = frozenset(
    {
        "GUARULHOS",
        "ARUJA",
        "MOGI DAS CRUZES",
        "SUZANO",
        "ITAQUAQUECETUBA",
        "FERRAZ DE VASCONCELOS",
        "POA",
    }
)
CIDADES_ABCDM: Final[frozenset[str]] = frozenset(
    {
        "SANTO ANDRE",
        "SAO BERNARDO DO CAMPO",
        "SAO CAETANO DO SUL",
        "DIADEMA",
        "MAUA",
        "RIBEIRAO PIRES",
        "RIO GRANDE DA SERRA",
    }
)
VALORES_AUSENTES: Final[frozenset[str]] = frozenset(
    {"", "NAN", "NONE", "NULL", "NAT", "NA", "N/A", "-", "None"}
)
RE_ESPACOS: Final[re.Pattern[str]] = re.compile(r"\s+")
RE_ALFANUMERICO: Final[re.Pattern[str]] = re.compile(r"[^A-Z0-9]")
RE_NUMERO_INICIAL: Final[re.Pattern[str]] = re.compile(r"^(\d+)")
RE_LOGIN_DECIMAL: Final[re.Pattern[str]] = re.compile(r"^(\d+)\.0+$")


def html_safe(valor: Any) -> str:
    return escape(str(valor), quote=True)


def fmt_pct_br(valor: Any) -> str:
    try:
        n = float(valor)
        if not np.isfinite(n):
            return "—"
        return f"{n * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def fmt_int_br(valor: Any) -> str:
    try:
        n = float(valor)
        if not np.isfinite(n):
            return "—"
        return f"{int(round(n)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def is_missing(valor: Any) -> bool:
    try:
        r = pd.isna(valor)
        return bool(r) if isinstance(r, (bool, np.bool_)) else False
    except (TypeError, ValueError):
        return False


def div_segura(num: pd.Series, den: pd.Series, padrao: float = 0.0) -> pd.Series:
    n = pd.to_numeric(num, errors="coerce").fillna(0).to_numpy(dtype=float)
    d = pd.to_numeric(den, errors="coerce").fillna(0).to_numpy(dtype=float)
    out = np.full_like(n, padrao, dtype=float)
    np.divide(n, d, out=out, where=d > 0)
    return pd.Series(out, index=num.index)


def hash_upload(nome: str, conteudo: bytes) -> str:
    return f"{nome}|{len(conteudo)}|{hashlib.sha256(conteudo).hexdigest()}"


def df_sessao(chave: str) -> pd.DataFrame | None:
    v = st.session_state.get(chave)
    return v if isinstance(v, pd.DataFrame) else None


def normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    try:
        if isinstance(pd.isna(valor), (bool, np.bool_)) and bool(pd.isna(valor)):
            return ""
    except (TypeError, ValueError):
        pass
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return RE_ESPACOS.sub(" ", texto.upper().strip())


def normalizar_coluna(valor: Any) -> str:
    return RE_ALFANUMERICO.sub("", normalizar_texto(valor))


def normalizar_login(valor: Any) -> str:
    if valor is None:
        return ""
    texto = normalizar_texto(valor).replace(" ", "")
    m = RE_LOGIN_DECIMAL.match(texto)
    base = m.group(1) if m else texto
    if base.isdigit():
        return base.lstrip("0") or "0"
    return base


def padronizar_tipo_servico(tipo: Any) -> str:
    if tipo is None or (isinstance(tipo, float) and np.isnan(tipo)):
        return "Outros"
    t = normalizar_texto(tipo)
    if not t:
        return "Outros"
    if any(k in t for k in ("PME", "PJ", "JURIDICO", "CORPORATIVO", "EMPRESA")):
        return "PME"
    if any(k in t for k in ("MIGRA", "MUDANCA DE PACOTE", "UPGRADE", "TROCA", "SWAP")):
        return "Migração"
    if (
        any(
            k in t
            for k in (
                "NOVOS DOMICILIOS",
                "NOVO DOMICILIO",
                "DOMICIL",
                "ADESAO",
                "INSTALACAO",
                "INSTAL",
                "RESIDENCIAL",
                "FIBRA NOVA",
            )
        )
        or t == "ND"
    ):
        return "Novos Domicílios"
    return "Outros"


class DF:
    @staticmethod
    def obter_serie(
        df: pd.DataFrame | None,
        coluna: str | None,
        padrao: Any = "",
        *,
        copiar: bool = False,
    ) -> pd.Series:
        if df is None:
            return pd.Series(dtype="object", name=coluna)
        if coluna is None or coluna not in df.columns:
            return pd.Series(padrao, index=df.index, dtype="object", name=coluna)
        obtido = df[coluna]
        if isinstance(obtido, pd.DataFrame):
            obtido = cast(pd.DataFrame, obtido).T.bfill().iloc[0]
        serie = cast(pd.Series, obtido)
        if not serie.index.equals(df.index):
            serie = serie.reindex(df.index)
        serie.name = coluna
        return serie.copy() if copiar else serie

    @staticmethod
    def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        resultado = df.copy()
        nomes, usados = [], {}
        for col in resultado.columns:
            base = normalizar_texto(col) or "COLUNA"
            usados[base] = usados.get(base, 0) + 1
            nomes.append(base if usados[base] == 1 else f"{base}__{usados[base]}")
        resultado.columns = nomes
        return resultado

    @staticmethod
    def buscar_coluna(
        df: pd.DataFrame | None, palavras: tuple[str, ...] | list[str]
    ) -> str | None:
        if df is None:
            return None
        mapa = {normalizar_coluna(c): str(c) for c in df.columns}
        for p in palavras:
            alvo = normalizar_coluna(p)
            if alvo and alvo in mapa:
                return mapa[alvo]
        for p in palavras:
            alvo = normalizar_coluna(p)
            if len(alvo) < 3:
                continue
            for norm, orig in mapa.items():
                if alvo == "CONTRATO" and "STATUS" in norm:
                    continue
                if "TECNICO" in alvo and "LOGIN" not in alvo and "LOGIN" in norm:
                    continue
                if alvo in norm or norm in alvo:
                    return orig
        return None

    @staticmethod
    def remover_duplicatas_coluna(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        vistos: set[str] = set()
        remover = []
        for col in df.columns:
            norm = normalizar_texto(col)
            if norm in vistos:
                remover.append(col)
            else:
                vistos.add(norm)
        return df.drop(columns=remover) if remover else df

    @staticmethod
    def corrigir_colunas_vazias(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["DATA AGENDA MDU", "ID SGD", "DATA_AGENDA_MDU", "ID_SGD"]:
            if col in df.columns and (
                df[col].isna().all() or (df[col].astype(str) == "None").all()
            ):
                for alt in df.columns:
                    if alt != col and (
                        ("AGENDA" in alt.upper() and col in alt.upper())
                        or ("ID" in alt.upper() and "SGD" in alt.upper())
                    ):
                        df[col] = df[alt]
                        break
        return df

    @staticmethod
    def limpar_texto(serie: pd.Series, padrao: str) -> pd.Series:
        r = serie.fillna("").astype(str).str.strip().str.upper()
        return r.mask(r.isin(VALORES_AUSENTES), padrao)


def converter_numero(valor: Any) -> float:
    if valor is None:
        return np.nan
    if isinstance(valor, (int, float, np.number)):
        n = float(valor)
        return n if np.isfinite(n) else np.nan
    texto = re.sub(r"[^\d,.\-]", "", str(valor).strip())
    if not texto or texto in {"-", ".", ","}:
        return np.nan
    try:
        if "," in texto and "." in texto:
            texto = (
                texto.replace(".", "").replace(",", ".")
                if texto.rfind(",") > texto.rfind(".")
                else texto.replace(",", "")
            )
        elif "," in texto:
            texto = (
                texto.replace(",", "")
                if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+", texto)
                else texto.replace(",", ".")
            )
        elif "." in texto and re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", texto):
            texto = texto.replace(".", "")
        n = float(texto)
        return n if np.isfinite(n) else np.nan
    except (TypeError, ValueError):
        return np.nan


class ClassificadorStatus:
    @staticmethod
    def status_texto(valor: Any) -> str | None:
        texto = normalizar_texto(valor)
        if texto in VALORES_AUSENTES:
            return None
        if "SUSPENS" in texto:
            return "Suspenso"
        if "CANCEL" in texto:
            return "Cancelado"
        if "NAO EXECUT" in texto or "NAO CONCLU" in texto:
            return "Não Executada"
        if "EXECUT" in texto or "CONCLUID" in texto:
            return "Executada"
        if any(
            t in texto for t in ("PEND", "EM ROTA", "INICIADO", "AGENDADO", "ABERTO")
        ):
            return "Pendente"
        return None

    @staticmethod
    def codigo_baixa(valor: Any) -> str | None:
        texto = normalizar_texto(valor)
        if texto in VALORES_AUSENTES:
            return None
        if texto in {"EM ROTA", "INICIADO", "PENDENTE"}:
            return "Pendente"
        m = RE_NUMERO_INICIAL.match(texto)
        return MAPA_CODIGO_NUMERICO.get(int(m.group(1))) if m else None

    @classmethod
    def classificar(cls, df: pd.DataFrame) -> pd.Series:
        col_inicio = DF.buscar_coluna(
            df, ("INÍCIO", "INICIO", "DATA INÍCIO", "DT INICIO", "HORA INICIO")
        )
        col_fechamento = DF.buscar_coluna(
            df,
            (
                "MOTIVO DE FECHAMENTO EXTERNO",
                "FECHAMENTO EXTERNO",
                "MOTIVO DE FECHAMENTO",
            ),
        )
        col_atividade = DF.buscar_coluna(
            df, ("STATUS DA ATIVIDADE", "STATUS ATIVIDADE", "STATUS_ATIVIDADE")
        )
        col_cod_baixa = DF.buscar_coluna(
            df, ("CÓD DE BAIXA 1", "COD DE BAIXA 1", "MOTIVO DE BAIXA", "COD_BAIXA")
        )
        col_status_os = DF.buscar_coluna(
            df,
            (
                "STATUS DA O.S 1",
                "STATUS OS 1",
                "STATUS CONTRATO",
                "STATUS O.S.",
                "STATUS OS",
            ),
        )
        inicio = DF.obter_serie(df, col_inicio).map(normalizar_texto)
        fechamento = DF.obter_serie(df, col_fechamento).map(normalizar_texto)
        atividade = DF.obter_serie(df, col_atividade).map(normalizar_texto)
        cod_baixa = DF.obter_serie(df, col_cod_baixa)
        status_os = DF.obter_serie(df, col_status_os).map(cls.status_texto)
        s_atividade, s_codigo = atividade.map(cls.status_texto), cod_baixa.map(
            cls.codigo_baixa
        )
        resultado = s_codigo.where(s_codigo.notna(), status_os)
        resultado = resultado.where(resultado.notna(), s_atividade).fillna("Pendente")
        fech_alvo = {"LIBERADO NO SISTEMA NETSMS", "CANCELADO NO SISTEMA NETSMS"}
        inicio_vazio = inicio.isin(VALORES_AUSENTES)
        c_fech = fechamento.isin(fech_alvo)
        resultado = resultado.mask(
            atividade.str.contains("NAO CONCLU", regex=False, na=False), "Não Executada"
        )
        resultado = resultado.mask(
            atividade.str.contains("SUSPENS", regex=False, na=False), "Suspenso"
        )
        resultado = resultado.mask(
            atividade.str.contains("CANCEL", regex=False, na=False), "Cancelado"
        )
        resultado = resultado.mask(~inicio_vazio & c_fech, "Não Executada")
        resultado = resultado.mask(inicio_vazio & c_fech, "Cancelado")
        return resultado.astype("object")


_PALAVRAS_PCT_EXCEL: Final[tuple[str, ...]] = (
    "QUEBRA",
    "FECHAMENTO",
    "CONVERSÃO",
    "CONVERSAO",
    "PROJEÇÃO",
    "PROJECAO",
    "%",
    "PME",
    "MIGRAÇÃO",
    "MIGRACAO",
    "DOMICÍLIOS",
    "DOMICILIOS",
    "GPON",
)


def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
    nome_aba = re.sub(r"[\[\]:*?/\\]", "_", aba).strip()[:31] or "Dados"
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba)
        ws = writer.sheets[nome_aba]
        header_fill = PatternFill("solid", fgColor="0F172A")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_border = Border(bottom=Side(style="thin", color="CBD5E1"))
        for cell in ws[1]:
            cell.fill, cell.font = header_fill, header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = header_border
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, col in enumerate(df.columns, start=1):
            upper = str(col).upper()
            amostra = df[col].head(2000).fillna("").astype(str).tolist()
            ws.column_dimensions[get_column_letter(i)].width = min(
                max(
                    max([len(str(col)), *(len(v) for v in amostra)], default=12) + 2, 12
                ),
                40,
            )
            if any(t in upper for t in _PALAVRAS_PCT_EXCEL):
                for linha in range(2, ws.max_row + 1):
                    ws.cell(linha, i).number_format = "0.00%"
    return buffer.getvalue()


class Utils:
    normalizar_login = staticmethod(normalizar_login)

    @staticmethod
    def classificar_status_excel(df: pd.DataFrame) -> pd.Series:
        return ClassificadorStatus.classificar(df)

    @staticmethod
    def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
        return gerar_excel(df, aba)


class DataLoader:
    _ENCODINGS_CSV: Final[tuple[str, ...]] = ("utf-8-sig", "utf-8", "latin-1", "cp1252")

    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        if not file_bytes:
            raise ValueError("O arquivo está vazio.")
        ext = Path(filename).suffix.lower()
        if ext == ".csv":
            return DataLoader._ler_csv(file_bytes)
        if ext in {".xlsx", ".xlsm"}:
            return pd.read_excel(BytesIO(file_bytes), engine="openpyxl", dtype=str)
        raise ValueError("Formato inválido. Utilize CSV, XLSX ou XLSM.")

    @staticmethod
    def _ler_csv(file_bytes: bytes) -> pd.DataFrame:
        texto = None
        for enc in DataLoader._ENCODINGS_CSV:
            try:
                texto = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if texto is None:
            raise ValueError("Encoding do CSV não identificado.")
        amostra = texto[:10000]
        try:
            delim = csv.Sniffer().sniff(amostra, delimiters=";,\t|").delimiter
        except csv.Error:
            delim = max((";", ",", "\t", "|"), key=amostra.count)
        return pd.read_csv(
            StringIO(texto),
            sep=delim,
            dtype=str,
            engine="python",
            on_bad_lines="skip",
            keep_default_na=False,
        )

    @staticmethod
    @st.cache_data(ttl=300, show_spinner="Sincronizando Lista de Ativos...")
    def buscar_gsheets() -> pd.DataFrame:
        urls = (
            url_gsheets_export(
                Config.SHEET_ID_ATIVOS, fmt="csv", sheet=Config.WORKSHEET_ATIVOS
            ),
            url_gsheets_gviz_csv(
                Config.SHEET_ID_ATIVOS, sheet=Config.WORKSHEET_ATIVOS
            ),
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        for i, url in enumerate(urls, start=1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = resp.read()
                raw = pd.read_csv(BytesIO(data), dtype=str)
                if not raw.empty:
                    out = DataLoader.processar_lista_ativos(raw)
                    if not out.empty:
                        return out
            except Exception as e:
                logger.debug("Falha método Google Sheets %s: %s", i, e)
        try:
            m = importlib.import_module("streamlit_gsheets")
            conn = st.connection("gsheets", type=m.GSheetsConnection)
            raw = conn.read(
                spreadsheet=Config.URL_LISTA_ATIVOS, worksheet=Config.WORKSHEET_ATIVOS
            )
            if isinstance(raw, pd.DataFrame) and not raw.empty:
                return DataLoader.processar_lista_ativos(raw)
        except Exception as e:
            logger.debug("Falha Streamlit Connection: %s", e)
        return pd.DataFrame()

    @staticmethod
    def processar_lista_ativos(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        base = raw.copy()
        base.columns = base.columns.astype(str).str.strip()
        aliases = {
            "LOGIN": (
                "LOGIN",
                "LOGIN DO TÉCNICO",
                "LOGIN DO TECNICO",
                "LOGIN_TECNICO",
                "MATRÍCULA",
                "MATRICULA",
                "ID",
                "USUARIO",
                "USUÁRIO",
                "RE",
                "COD_TECNICO",
            ),
            "TÉCNICO": (
                "TÉCNICO",
                "TECNICO",
                "NOME",
                "COLABORADOR",
                "NOME TÉCNICO",
                "NOME TECNICO",
                "NOME COMPLETO",
                "NOME DO TÉCNICO",
                "NOME DO TECNICO",
            ),
            "MONITOR": (
                "MONITOR",
                "GESTOR",
                "SUPERVISOR",
                "COORDENADOR",
                "LIDER",
                "LÍDER",
                "NOME MONITOR",
                "NOME SUPERVISOR",
                "NOME GESTOR",
            ),
            "BASE": ("BASE", "REGIÃO", "REGIAO", "FILIAL", "LOCALIDADE"),
        }
        resultado = pd.DataFrame(index=base.index)
        for destino, nomes in aliases.items():
            col = DF.buscar_coluna(base, nomes)
            if col:
                resultado[destino] = DF.obter_serie(base, col)
        if "LOGIN" not in resultado.columns:
            return pd.DataFrame()
        resultado["LOGIN"] = resultado["LOGIN"].map(normalizar_login)
        resultado = resultado.loc[~resultado["LOGIN"].isin(VALORES_AUSENTES)].copy()
        for col in ("TÉCNICO", "MONITOR"):
            if col in resultado.columns:
                resultado[col] = (
                    resultado[col].fillna("").astype(str).str.strip().str.upper()
                )
        return resultado.drop_duplicates(subset=["LOGIN"], keep="last").reset_index(
            drop=True
        )

    _processar_lista_ativos = processar_lista_ativos

    @staticmethod
    def classificar_regiao(valor: Any) -> str:
        cidade = normalizar_texto(valor)
        if cidade in CIDADES_LESTE:
            return "LESTE"
        if cidade in CIDADES_GRU:
            return "GRU"
        if cidade in CIDADES_ABCDM:
            return "ABCDM"
        return cidade if cidade in CORES_REGIAO else "OUTRAS"

    @staticmethod
    def gerar_tipo_servico(df: pd.DataFrame) -> pd.Series:
        if df.empty:
            return pd.Series(dtype="object")
        if CRITERIOS.disponivel and CRITERIOS.classificar:
            try:
                _, serie = CRITERIOS.classificar(df.copy())
                return serie.map(padronizar_tipo_servico)
            except Exception as erro:
                st.warning(f"Erro ao usar critérios; fallback aplicado: {erro}")
        col = DF.buscar_coluna(df, Config.COLUNAS_TIPO_SERVICO)
        return (
            pd.Series("Outros", index=df.index, dtype="object")
            if col is None
            else DF.obter_serie(df, col).map(padronizar_tipo_servico)
        )

    @staticmethod
    def criar_flag_gpon(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            df["FLAG_GPON"] = "Não"
            return df
        if CRITERIOS.disponivel and CRITERIOS.criar_flag_gpon:
            try:
                result, _, _ = CRITERIOS.criar_flag_gpon(df)
                return result
            except Exception as erro:
                st.warning(f"Erro ao criar FLAG_GPON; fallback aplicado: {erro}")
        col = DF.buscar_coluna(
            df,
            ("HABILIDADE DE TRABALHO", "HABILIDADE", "HABILIDADES", "SKILL", "SKILLS"),
        )
        df["FLAG_GPON"] = (
            np.where(
                df[col]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.contains("PON", na=False),
                "Sim",
                "Não",
            )
            if col
            else "Não"
        )
        return df

    @staticmethod
    def _mesclar_ativos(
        base: pd.DataFrame, ativos: pd.DataFrame, col_login: str | None
    ) -> pd.DataFrame:
        col_mon_os = DF.buscar_coluna(
            base, ("MONITOR", "GESTOR", "SUPERVISOR", "COORDENADOR")
        )
        col_tec_os = DF.buscar_coluna(
            base, ("TÉCNICO", "TECNICO", "NOME TÉCNICO", "NOME TECNICO", "COLABORADOR")
        )
        mon_os = (
            DF.obter_serie(base, col_mon_os).map(normalizar_texto)
            if col_mon_os
            else pd.Series("", index=base.index)
        )
        tec_os = (
            DF.obter_serie(base, col_tec_os).map(normalizar_texto)
            if col_tec_os
            else pd.Series("", index=base.index)
        )
        if ativos is None or ativos.empty or "LOGIN" not in ativos.columns:
            base["TÉCNICO"] = tec_os.mask(
                tec_os.isin(VALORES_AUSENTES) | (tec_os == ""), "NÃO MAPEADO"
            )
            base["MONITOR"] = mon_os.mask(
                mon_os.isin(VALORES_AUSENTES) | (mon_os == ""), "SEM MONITOR"
            )
            return base
        at = ativos.copy()
        at["_JOIN_KEY"] = at["LOGIN"].map(normalizar_login)
        at["_JOIN_CLEAN"] = at["_JOIN_KEY"].str.lstrip("0")
        for col in ("TÉCNICO", "MONITOR", "BASE"):
            if col not in at.columns:
                at[col] = ""
        at_key = at.drop_duplicates(subset=["_JOIN_KEY"], keep="last")
        at_clean = at.loc[at["_JOIN_CLEAN"] != ""].drop_duplicates(
            subset=["_JOIN_CLEAN"], keep="last"
        )
        os_login = (
            DF.obter_serie(base, col_login)
            if col_login
            else pd.Series("", index=base.index)
        )
        work = base.copy()
        work["_JOIN_KEY"] = os_login.map(normalizar_login)
        work["_JOIN_CLEAN"] = work["_JOIN_KEY"].str.lstrip("0")
        work["_MON_OS"], work["_TEC_OS"] = mon_os, tec_os
        rename = {"TÉCNICO": "_TEC_AT", "MONITOR": "_MON_AT", "BASE": "_BASE_AT"}
        m1 = work.merge(
            at_key[["_JOIN_KEY", "TÉCNICO", "MONITOR", "BASE"]].rename(columns=rename),
            on="_JOIN_KEY",
            how="left",
        )
        m2 = work.merge(
            at_clean[["_JOIN_CLEAN", "TÉCNICO", "MONITOR", "BASE"]].rename(
                columns=rename
            ),
            on="_JOIN_CLEAN",
            how="left",
        )

        def resolve(col: str, fallback: str, default: str) -> pd.Series:
            a = m1[col].fillna("").astype(str).str.strip()
            b = m2[col].fillna("").astype(str).str.strip()
            c = m1[fallback].fillna("").astype(str).str.strip()
            result = np.where(a != "", a, np.where(b != "", b, c))
            return DF.limpar_texto(pd.Series(result, index=base.index), default)

        result = base.copy()
        result["TÉCNICO"] = resolve("_TEC_AT", "_TEC_OS", "NÃO MAPEADO")
        result["MONITOR"] = resolve("_MON_AT", "_MON_OS", "SEM MONITOR")
        b1 = m1["_BASE_AT"].fillna("").astype(str).str.strip()
        b2 = m2["_BASE_AT"].fillna("").astype(str).str.strip()
        b_final = np.where(b1 != "", b1, b2)
        if any(b_final != ""):
            result["_B"] = pd.Series(b_final, index=result.index)
        match_mask = (
            m1["_JOIN_KEY"].isin(set(at_key["_JOIN_KEY"]))
            | m2["_JOIN_CLEAN"].isin(set(at_clean["_JOIN_CLEAN"]))
        ) & (work["_JOIN_KEY"] != "")
        result.attrs["logins_encontrados"] = int(match_mask.sum())
        return result

    @staticmethod
    def _definir_regiao(base: pd.DataFrame) -> pd.Series:
        col = DF.buscar_coluna(base, ("CIDADE", "LOCALIDADE", "MUNICÍPIO", "MUNICIPIO"))
        if col:
            return DF.obter_serie(base, col).map(DataLoader.classificar_regiao)
        if "_B" in base.columns:
            return base["_B"].map(DataLoader.classificar_regiao)
        if "BASE" in base.columns:
            return base["BASE"].map(DataLoader.classificar_regiao)
        return pd.Series("OUTRAS", index=base.index)

    @staticmethod
    def preparar_base(
        df: pd.DataFrame, df_gs: pd.DataFrame | None, filename: str = ""
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        base = DF.corrigir_colunas_vazias(
            DF.remover_duplicatas_coluna(DF.padronizar_colunas(df))
        )
        total_importado = len(base)
        base = DataLoader.criar_flag_gpon(base)
        flag_gpon_sim = int((base["FLAG_GPON"] == "Sim").sum())
        col_tipo = DF.buscar_coluna(base, Config.COLUNAS_TIPO_SERVICO)
        valores_tipo = {}
        if col_tipo:
            serie = DF.obter_serie(base, col_tipo).fillna("").astype(str).str.strip()
            valores_tipo = {
                str(k): int(v) for k, v in serie.value_counts().head(20).items()
            }
        base["STATUS CONTRATO"] = ClassificadorStatus.classificar(base)
        status = base["STATUS CONTRATO"].fillna("").astype(str).str.upper().str.strip()
        removidos_status = int(status.isin({"CANCELADO", "SUSPENSO"}).sum())
        base = base.loc[~status.isin({"CANCELADO", "SUSPENSO"})].copy()
        if base.empty:
            return pd.DataFrame()
        col_contrato = DF.buscar_coluna(
            base,
            (
                "CONTRATO",
                "NR CONTRATO",
                "NÚMERO CONTRATO",
                "NUMERO CONTRATO",
                "CONTRATO_ID",
            ),
        )
        removidos_contrato = 0
        if col_contrato:
            contratos = DF.obter_serie(base, col_contrato).map(normalizar_texto)
            invalidos = contratos.isin(
                {"", "NAN", "NONE", "NULL", "N/A", "NA", "-", "0"}
            )
            removidos_contrato = int(invalidos.sum())
            base = base.loc[~invalidos].copy()
        if base.empty:
            return pd.DataFrame()
        col_total = DF.buscar_coluna(
            base, ("TOTAL DE TAREFAS", "QTD TAREFAS", "QUANTIDADE", "VOLUME")
        )
        base["TOTAL DE TAREFAS"] = (
            pd.to_numeric(
                DF.obter_serie(base, col_total).map(converter_numero), errors="coerce"
            )
            .fillna(1)
            .clip(lower=0)
            .round()
            .astype(int)
            if col_total
            else 1
        )
        col_login = DF.buscar_coluna(
            base,
            (
                "LOGIN DO TÉCNICO",
                "LOGIN DO TECNICO",
                "LOGIN_DO_TECNICO",
                "LOGIN TÉCNICO",
                "LOGIN TECNICO",
                "LOGIN_TECNICO",
                "LOGIN",
                "MATRÍCULA",
                "MATRICULA",
                "RE",
                "ID TÉCNICO",
                "ID TECNICO",
                "ID_TECNICO",
                "COD_TECNICO",
            ),
        )
        ativos = (
            DataLoader.processar_lista_ativos(df_gs)
            if isinstance(df_gs, pd.DataFrame)
            else pd.DataFrame()
        )
        base = DataLoader._mesclar_ativos(base, ativos, col_login)
        base["REGIÃO"] = DataLoader._definir_regiao(base)
        base["TIPO_SERVICO"] = DataLoader.gerar_tipo_servico(base).map(
            padronizar_tipo_servico
        )
        base["Status Contrato"] = base["STATUS CONTRATO"]
        aux = [
            c
            for c in base.columns
            if c.startswith("_LOGIN_")
            or c.startswith("_ATIVO")
            or c in ("_T", "_M", "_B")
        ]
        logins_encontrados = int(base.attrs.get("logins_encontrados", 0))
        base = base.drop(columns=aux, errors="ignore").reset_index(drop=True)
        base.attrs.update(
            {
                "arquivo_origem": filename,
                "total_importado": total_importado,
                "removidos_suspensos_cancelados": removidos_status,
                "removidos_contrato": removidos_contrato,
                "tipo_servico_coluna": col_tipo or "",
                "valores_tipo_servico_originais": valores_tipo,
                "total_processado": len(base),
                "flag_gpon_sim_count": flag_gpon_sim,
                "logins_encontrados": logins_encontrados,
            }
        )
        return base

    @staticmethod
    def callback_robo_etl(df_raw: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        caminho = st.session_state.get("robo_candidato_path", "")
        nome = Path(str(caminho)).name if caminho else "Arquivo_Robo"
        df_proc = DataLoader.preparar_base(df_raw, df_gs, filename=nome)
        st.session_state.update(
            {
                "_robo_df_pronto": df_proc,
                "_robo_nome_arquivo": nome,
                "_robo_dados_disponiveis": not df_proc.empty,
                "df_memoria_raw": df_raw,
                "df_memoria": df_proc,
                "origem_dados": f"Robô ({nome})",
                "robo_hora_sucesso": datetime.now(),
            }
        )
        return df_proc


class Motor:
    @staticmethod
    def _matriz_logic(df: pd.DataFrame) -> pd.DataFrame:
        obrig = {"MONITOR", "TIPO_SERVICO", "Status Contrato", "TOTAL DE TAREFAS"}
        if df is None or df.empty or not obrig.issubset(df.columns):
            return pd.DataFrame()
        t = df.copy()
        t["MONITOR"] = (
            t["MONITOR"].fillna("SEM MONITOR").astype(str).str.strip().str.upper()
        )
        t["TIPO_SERVICO"] = t["TIPO_SERVICO"].apply(padronizar_tipo_servico)
        t["Status Contrato"] = t["Status Contrato"].fillna("").astype(str).str.strip()
        t["TOTAL DE TAREFAS"] = (
            pd.to_numeric(t["TOTAL DE TAREFAS"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
        )
        validos = t.loc[t["Status Contrato"].isin(Config.STATUS_ORDEM)].copy()
        if validos.empty:
            return pd.DataFrame()
        validos["_EXEC"] = np.where(
            validos["Status Contrato"].eq("Executada"), validos["TOTAL DE TAREFAS"], 0
        )
        validos["_NEX"] = np.where(
            validos["Status Contrato"].eq("Não Executada"),
            validos["TOTAL DE TAREFAS"],
            0,
        )
        ag = (
            validos.groupby(["MONITOR", "TIPO_SERVICO"], dropna=False)
            .agg(executados=("_EXEC", "sum"), nao_executados=("_NEX", "sum"))
            .reset_index()
        )
        ag["DENOMINADOR"] = ag["executados"] + ag["nao_executados"]
        ag["PERCENTUAL"] = div_segura(
            ag["nao_executados"], ag["DENOMINADOR"], padrao=np.nan
        )
        monitores = pd.Index(
            sorted(validos["MONITOR"].dropna().unique()), name="MONITOR"
        )
        pivot = ag.pivot(
            index="MONITOR", columns="TIPO_SERVICO", values="PERCENTUAL"
        ).reindex(monitores)
        for tipo in Config.ORDEM_TIPOS:
            if tipo not in pivot.columns:
                pivot[tipo] = np.nan
        pivot = pivot.loc[:, list(Config.ORDEM_TIPOS)]
        totais = (
            validos.groupby("MONITOR")[["_EXEC", "_NEX"]]
            .sum()
            .reindex(monitores)
            .fillna(0)
        )
        denom = totais["_EXEC"] + totais["_NEX"]
        pivot["Quebra Geral"] = div_segura(totais["_NEX"], denom, padrao=np.nan)
        pivot["Total Tasks"] = (
            validos.groupby("MONITOR")["TOTAL DE TAREFAS"]
            .sum()
            .reindex(monitores)
            .fillna(0)
            .round()
            .astype(int)
        )
        pivot = pivot.reset_index().rename(columns={"MONITOR": "Monitor"})
        exec_g, nex_g = float(validos["_EXEC"].sum()), float(validos["_NEX"].sum())
        total_row: dict[str, Any] = {
            "Monitor": "TOTAL GERAL",
            "Quebra Geral": nex_g / (exec_g + nex_g) if exec_g + nex_g > 0 else np.nan,
            "Total Tasks": int(validos["TOTAL DE TAREFAS"].sum()),
        }
        for tipo in Config.ORDEM_TIPOS:
            r = validos.loc[validos["TIPO_SERVICO"].eq(tipo)]
            e, n = float(r["_EXEC"].sum()), float(r["_NEX"].sum())
            total_row[tipo] = n / (e + n) if e + n > 0 else np.nan
        return pd.concat(
            [pivot, pd.DataFrame([total_row], columns=pivot.columns)], ignore_index=True
        )

    @staticmethod
    def matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame() if df is None or df.empty else _cache_matriz(df.copy())

    @staticmethod
    def _pivot_status(df: pd.DataFrame, grupo: str) -> pd.DataFrame:
        t = df.copy()
        t["TOTAL DE TAREFAS"] = (
            pd.to_numeric(t["TOTAL DE TAREFAS"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
        )
        pivot = pd.pivot_table(
            t,
            index=grupo,
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        )
        for s in Config.STATUS_ORDEM:
            if s not in pivot.columns:
                pivot[s] = 0.0
        return pivot.reset_index()

    @staticmethod
    def tabela_cenarios(
        df: pd.DataFrame,
        grupo: str,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 5,
    ) -> pd.DataFrame:
        obrig = {grupo, "Status Contrato", "TOTAL DE TAREFAS"}
        if df.empty or not obrig.issubset(df.columns):
            return pd.DataFrame()
        p_ot, p_base, p_pess = (float(np.clip(x, 0, 1)) for x in (p_ot, p_base, p_pess))
        r = Motor._pivot_status(df, grupo)
        r["Considerado"] = r["Executada"] + r["Não Executada"]
        r["Alocado"] = r["Considerado"] + r["Pendente"]
        r["Quebra Atual"] = div_segura(r["Não Executada"], r["Considerado"])
        for nome, prob in (
            ("Otimista", p_ot),
            ("Base", p_base),
            ("Pessimista", p_pess),
        ):
            r[f"Fechamento {nome}"] = div_segura(
                r["Não Executada"] + r["Pendente"] * prob, r["Alocado"]
            )
        return (
            r.loc[r["Alocado"] >= min_aloc]
            .sort_values("Fechamento Base", ascending=False)
            .reset_index(drop=True)
        )

    @staticmethod
    def tecnicos_criticos(
        df: pd.DataFrame,
        segmento: str,
        p_base: float,
        min_aloc: float,
        top_n: int,
        p_ot: float = 0.15,
        p_pess: float = 0.50,
    ) -> pd.DataFrame:
        recorte = (
            df.loc[df["TIPO_SERVICO"].eq(segmento)].copy()
            if segmento and segmento != "TODOS" and "TIPO_SERVICO" in df.columns
            else df.copy()
        )
        return (
            pd.DataFrame()
            if recorte.empty
            else Motor.tabela_cenarios(
                recorte, "TÉCNICO", p_ot, p_base, p_pess, min_aloc
            ).head(top_n)
        )

    @staticmethod
    def causa_raiz(df: pd.DataFrame, coluna_baixa: str, top_n: int = 8) -> pd.DataFrame:
        if not {"Status Contrato", "TOTAL DE TAREFAS", coluna_baixa}.issubset(
            df.columns
        ):
            return pd.DataFrame()
        r = df.loc[df["Status Contrato"].eq("Não Executada")].copy()
        if r.empty:
            return pd.DataFrame()
        r["_B"] = (
            r[coluna_baixa]
            .fillna("SEM REGISTRO")
            .astype(str)
            .map(normalizar_texto)
            .replace("", "SEM REGISTRO")
        )
        r["TOTAL DE TAREFAS"] = (
            pd.to_numeric(r["TOTAL DE TAREFAS"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
        )
        total = float(r["TOTAL DE TAREFAS"].sum())
        res = r.groupby("_B")["TOTAL DE TAREFAS"].sum().nlargest(top_n).reset_index()
        res.columns = ["Motivo de Baixa", "Volume"]
        res["% do Total"] = div_segura(res["Volume"], pd.Series(total, index=res.index))
        res["Acumulado"] = res["% do Total"].cumsum()
        return res

    @staticmethod
    def backoffice_fila(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or "Status Contrato" not in df.columns:
            return pd.DataFrame()
        t = df.copy()
        for col, pad in (
            ("MONITOR", "SEM MONITOR"),
            ("TÉCNICO", "NÃO MAPEADO"),
            ("TIPO_SERVICO", "Outros"),
        ):
            if col not in t.columns:
                t[col] = pad
        if "TOTAL DE TAREFAS" in t.columns:
            t["TOTAL DE TAREFAS"] = (
                pd.to_numeric(t["TOTAL DE TAREFAS"], errors="coerce")
                .fillna(0)
                .clip(lower=0)
            )
        else:
            t["TOTAL DE TAREFAS"] = 0
        fila = t.loc[t["Status Contrato"].isin(["Não Executada", "Pendente"])].copy()
        if fila.empty:
            return pd.DataFrame()
        ag = (
            fila.groupby(
                ["MONITOR", "TÉCNICO", "TIPO_SERVICO", "Status Contrato"], dropna=False
            )["TOTAL DE TAREFAS"]
            .sum()
            .reset_index()
        )
        pivot = pd.pivot_table(
            ag,
            index=["MONITOR", "TÉCNICO", "TIPO_SERVICO"],
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        for c in ("Não Executada", "Pendente"):
            if c not in pivot.columns:
                pivot[c] = 0
        pivot["Total Fila"] = pivot["Não Executada"] + pivot["Pendente"]
        pivot["Prioridade"] = pivot["Não Executada"] * 2 + pivot["Pendente"]
        pivot["Classificação"] = np.select(
            [
                pivot["Prioridade"].ge(20),
                pivot["Prioridade"].ge(10),
                pivot["Prioridade"].ge(5),
            ],
            ["🔴 CRÍTICO", "🟠 ALTA", "🟡 MÉDIA"],
            default="⚪ BAIXA",
        )
        pivot = pivot.rename(
            columns={
                "MONITOR": "Monitor",
                "TÉCNICO": "Técnico",
                "TIPO_SERVICO": "Segmento",
            }
        )
        return pivot.sort_values("Prioridade", ascending=False).reset_index(drop=True)[
            [
                "Classificação",
                "Monitor",
                "Técnico",
                "Segmento",
                "Não Executada",
                "Pendente",
                "Total Fila",
                "Prioridade",
            ]
        ]

    @staticmethod
    def projetar(
        df: pd.DataFrame,
        probabilidade: float = 0.30,
        grupo: str = "MONITOR",
        incluir_meta: bool = True,
        meta_sla: float = Config.SLA_QUEBRA_MAXIMA,
    ) -> pd.DataFrame:
        obrig = {grupo, "Status Contrato", "TOTAL DE TAREFAS"}
        if not obrig.issubset(df.columns):
            return pd.DataFrame()
        probabilidade, meta_sla = float(np.clip(probabilidade, 0, 1)), float(
            np.clip(meta_sla, 0, 1)
        )
        r = Motor._pivot_status(df, grupo)
        r["Considerado"] = r["Executada"] + r["Não Executada"]
        r["Alocado"] = r["Considerado"] + r["Pendente"]
        r["Quebra Atual"] = div_segura(r["Não Executada"], r["Considerado"])
        r["Projeção Fechamento"] = div_segura(
            r["Não Executada"] + r["Pendente"] * (1 - probabilidade), r["Alocado"]
        )
        r["Executadas Projetadas"] = r["Executada"] + r["Pendente"] * probabilidade
        conv = div_segura(
            r["Alocado"] * (1 - meta_sla) - r["Executada"], r["Pendente"]
        ).clip(0, 1)
        r["Conversão Necessária"] = np.where(r["Pendente"].gt(0), conv, 0.0)
        if incluir_meta:
            p = r["Projeção Fechamento"]
            r["Status Meta"] = np.select(
                [p.le(meta_sla), p.le(meta_sla * 1.25), p.le(meta_sla * 1.50)],
                ["✅ Dentro da Meta", "⚠️ Atenção", "🔶 Crítico"],
                default="🚨 Muito Crítico",
            )
        for c in ("Executada", "Não Executada", "Pendente", "Considerado", "Alocado"):
            r[c] = r[c].fillna(0).round().astype(int)
        return r.sort_values("Projeção Fechamento", ascending=False).reset_index(
            drop=True
        )

    @staticmethod
    def resumo_gpon(df: pd.DataFrame) -> dict[str, Any]:
        if df is None or df.empty or "FLAG_GPON" not in df.columns:
            return {"total": 0, "sim": 0, "nao": 0, "percentual": 0.0}
        total, sim = len(df), int((df["FLAG_GPON"] == "Sim").sum())
        return {
            "total": total,
            "sim": sim,
            "nao": total - sim,
            "percentual": sim / total * 100 if total > 0 else 0.0,
        }


@st.cache_data(ttl=3600, show_spinner=False)
def _cache_matriz(df: pd.DataFrame) -> pd.DataFrame:
    return Motor._matriz_logic(df)


_TEMAS_KPI: Final[dict[str, dict[str, str]]] = {
    "amarelo": {
        "fundo": "#FFFBEB",
        "texto": "#92400E",
        "borda": "#F59E0B",
        "titulo": "#B45309",
    },
    "roxo": {
        "fundo": "#FAF5FF",
        "texto": "#6B21A8",
        "borda": "#A855F7",
        "titulo": "#7E22CE",
    },
    "escuro": {
        "fundo": "#1E293B",
        "texto": "#FFFFFF",
        "borda": "#475569",
        "titulo": "#E2E8F0",
    },
}


def render_section_header(icone: str, titulo: str) -> None:
    if COMPONENTES.section_header:
        COMPONENTES.section_header(icone, titulo)
    else:
        st.subheader(f"{icone} {titulo}" if icone else titulo)


def render_sidebar_brand(**kw: Any) -> None:
    if COMPONENTES.sidebar_brand:
        COMPONENTES.sidebar_brand(**kw)


def render_table_html(df: pd.DataFrame, **kw: Any) -> None:
    if COMPONENTES.table_html:
        COMPONENTES.table_html(df, **kw)
    else:
        st.dataframe(df, width="stretch", hide_index=True)


def render_insight(texto: str, tipo: TipoInsight = "info") -> None:
    if COMPONENTES.insight:
        COMPONENTES.insight(texto, tipo)
    elif tipo == "ok":
        st.success(texto)
    elif tipo in {"critico", "alerta"}:
        st.warning(texto)
    elif tipo == "acao":
        st.error(texto)
    else:
        st.info(texto)


def render_kpi_sm(
    col: Any, label: str, value: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    if tema not in _TEMAS_KPI:
        if COMPONENTES.kpi_sm:
            COMPONENTES.kpi_sm(col, label, value, sub, tema)
        else:
            col.metric(label, value, sub)
        return
    e = _TEMAS_KPI[tema]
    col.markdown(
        f"""<div class="kpi-mini" style="--kpi-bg:{e["fundo"]};--kpi-text:{e["texto"]};--kpi-border:{e["borda"]};--kpi-label:{e["titulo"]}"><div class="kpi-mini__label">{html_safe(label)}</div><div class="kpi-mini__value">{html_safe(value)}</div><div class="kpi-mini__sub">{html_safe(sub)}</div></div>""",
        unsafe_allow_html=True,
    )


def renderizar_robo_local(*args: Any, **kw: Any) -> None:
    if _ROBO_FN is None:
        st.sidebar.warning("Robô offline. Utilize upload manual.")
        return
    try:
        _ROBO_FN(*args, **kw)
    except Exception as erro:
        st.sidebar.error(f"Erro no robô: {erro}")


_CSS_GLOBAL: Final[str] = """
<style>
:root{--page:#F4F7FB;--surface:#FFFFFF;--surface-soft:#F8FAFC;--ink:#0F172A;--muted:#64748B;--line:#E2E8F0;--navy:#123B5D;--teal:#0F766E;--radius:14px}
html,body,[data-testid="stAppViewContainer"]{font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink)}
[data-testid="stAppViewContainer"]{background:var(--page)}[data-testid="stMainBlockContainer"]{max-width:1480px;padding-top:1.4rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line)}[data-testid="stSidebar"]>div{padding-top:1.2rem}
h1,h2,h3{color:var(--ink);letter-spacing:-.025em}
.import-header-title{font-size:1.65rem;font-weight:750;color:var(--ink);letter-spacing:-.035em}.import-header-badge{display:inline-flex;margin-left:.7rem;padding:.25rem .65rem;border:1px solid #BFDBFE;border-radius:999px;background:#EFF6FF;color:#1D4ED8;font-size:.68rem;font-weight:700}.import-header-sub{margin:.4rem 0 1rem;color:var(--muted);font-size:.9rem}.import-header-line{height:2px;margin-bottom:1.25rem;border-radius:2px;background:linear-gradient(90deg,var(--navy),var(--teal) 65%,#E2E8F0)}
.import-alert-green{display:flex;align-items:center;gap:.6rem;margin-bottom:1rem;padding:.85rem 1rem;border:1px solid #A7F3D0;border-radius:10px;background:#ECFDF5;color:#065F46;font-size:.85rem;font-weight:650}
.hero-container{margin:0 0 1rem;padding:0;background:transparent}.hero-card{padding:1.7rem 1.9rem;border:1px solid rgba(255,255,255,.12);border-radius:18px;background:linear-gradient(115deg,#0F172A,#123B5D 68%,#0F766E);box-shadow:0 10px 28px rgba(15,23,42,.12);color:#fff}.hero-card__layout{display:flex;align-items:center;justify-content:space-between;gap:1.5rem}.hero-eyebrow{margin:0 0 .45rem;color:#BAE6FD;font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.hero-title{margin:0;color:#fff!important;font-size:clamp(1.45rem,2.6vw,2rem);font-weight:750;line-height:1.15}.hero-sub{margin:.55rem 0 0;color:#CBD5E1;font-size:.9rem}.hero-badge{display:inline-block;margin-top:.85rem;padding:.3rem .65rem;border:1px solid rgba(255,255,255,.25);border-radius:999px;background:rgba(255,255,255,.08);color:#fff;font-size:.68rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase}.hero-side-metric{min-width:155px;padding:.9rem 1rem;border:1px solid rgba(255,255,255,.18);border-radius:12px;background:rgba(255,255,255,.08);text-align:right}.hero-side-metric span{display:block;color:#CBD5E1;font-size:.68rem;font-weight:600;text-transform:uppercase}.hero-side-metric strong{display:block;margin-top:.25rem;color:#fff;font-size:1.55rem;font-weight:750}
.base-info{display:flex;align-items:center;flex-wrap:wrap;gap:.55rem;margin-top:.75rem;padding:.85rem 1rem;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 2px 8px rgba(15,23,42,.035)}.base-info-label{margin-right:.2rem;color:var(--muted);font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}.base-info-source{color:var(--muted);font-size:.75rem}.base-info-total{margin-left:auto;color:var(--ink);font-size:.8rem;font-weight:700}.badge-regiao{display:inline-flex;padding:.28rem .65rem;border:1px solid;border-radius:999px;font-size:.72rem;font-weight:700}
.matriz-table-container{width:100%;overflow-x:auto;margin-bottom:1rem;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 3px 12px rgba(15,23,42,.04)}.matriz-table{width:100%;border-collapse:collapse;font-size:.82rem}.matriz-table th{padding:.85rem 1rem;border-bottom:1px solid var(--line);background:#F8FAFC;color:#475569;font-size:.68rem;font-weight:700;letter-spacing:.06em;text-align:center;text-transform:uppercase}.matriz-table th:first-child,.matriz-table td:first-child{text-align:left}.matriz-table td{padding:.7rem 1rem;border-bottom:1px solid #F1F5F9;color:#334155;text-align:center}.matriz-table td:first-child{color:var(--ink);font-weight:650}.matriz-table tr:hover{background:#F8FAFC}.matriz-table tr.total-row{border-top:2px solid #CBD5E1;background:#F1F5F9;font-weight:750}
.badge-meta-ok,.badge-meta-nok{display:inline-block;min-width:68px;padding:.28rem .55rem;border:1px solid;border-radius:7px;font-size:.74rem;font-weight:700}.badge-meta-ok{border-color:#A7F3D0;background:#ECFDF5;color:#047857}.badge-meta-nok{border-color:#FECACA;background:#FEF2F2;color:#B91C1C}
div[data-testid="stMetric"]{padding:.85rem;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 2px 8px rgba(15,23,42,.035)}.kpi-mini{padding:12px 16px;margin-bottom:8px;border:1px solid var(--line);border-left:3px solid var(--kpi-border);border-radius:10px;background:var(--kpi-bg);box-shadow:0 2px 8px rgba(15,23,42,.035)}.kpi-mini__label{color:var(--kpi-label);font-size:.68rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase}.kpi-mini__value{margin-top:4px;color:var(--kpi-text);font-size:1.25rem;font-weight:750;line-height:1.2}.kpi-mini__sub{margin-top:3px;color:var(--kpi-label);font-size:.72rem}
.matriz-table-container{font-family:inherit}.stButton>button,.stDownloadButton>button{min-height:2.55rem;border-radius:9px;font-weight:650}div[data-testid="stExpander"]{overflow:hidden;border:1px solid var(--line);border-radius:11px;background:#fff}div[data-testid="stFileUploader"] section{border:1px dashed #94A3B8;border-radius:12px;background:#F8FAFC}[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input{border-radius:9px}
@media(max-width:760px){.hero-card__layout{align-items:flex-start;flex-direction:column}.hero-side-metric{width:100%;text-align:left}.base-info-total{margin-left:0}}
</style>
"""


def injetar_css() -> None:
    st.markdown(_CSS_GLOBAL, unsafe_allow_html=True)


_METAS_COLUNA_MATRIZ: Final[dict[str, str]] = {
    "NOVOS DOMICÍLIOS": "geral",
    "NOVOS DOMICILIOS": "geral",
    "PME": "geral",
    "MIGRAÇÃO": "migracao",
    "MIGRACAO": "migracao",
    "OUTROS": "geral",
    "QUEBRA GERAL": "geral",
}


def render_matriz_executiva(
    df: pd.DataFrame, meta_geral: float = Config.SLA_QUEBRA_MAXIMA
) -> None:
    if df.empty:
        st.info("Sem dados na Matriz Executiva.")
        return
    metas = {
        k: meta_geral if v == "geral" else Config.SLA_MIGRACAO_MAXIMA
        for k, v in _METAS_COLUNA_MATRIZ.items()
    }
    linhas = [
        '<div class="matriz-table-container"><table class="matriz-table"><thead><tr>'
    ]
    linhas.extend(f"<th>{html_safe(c)}</th>" for c in df.columns)
    linhas.append("</tr></thead><tbody>")
    for _, linha in df.iterrows():
        is_total = str(linha.iloc[0]).strip().upper() == "TOTAL GERAL"
        linhas.append("<tr class='total-row'>" if is_total else "<tr>")
        for i, col in enumerate(df.columns):
            v, cu = linha.iloc[i], str(col).strip().upper()
            if cu in metas:
                try:
                    n = float(v)
                    if not np.isfinite(n):
                        linhas.append(
                            "<td><span style='color:#94A3B8;font-weight:700;'>—</span></td>"
                        )
                    else:
                        cls = "badge-meta-ok" if n <= metas[cu] else "badge-meta-nok"
                        linhas.append(
                            f"<td><span class='{cls}'>{fmt_pct_br(n)}</span></td>"
                        )
                except (TypeError, ValueError):
                    linhas.append(f"<td>{html_safe(v)}</td>")
            elif cu in {"TOTAL TASKS", "TOTAL_TASKS"}:
                linhas.append(f"<td><strong>{fmt_int_br(v)}</strong></td>")
            else:
                conteudo = (
                    html_safe(v)
                    if not is_missing(v)
                    else "<span style='color:#94A3B8;'>—</span>"
                )
                linhas.append(f"<td>{conteudo}</td>")
        linhas.append("</tr>")
    linhas.append("</tbody></table></div>")
    st.markdown("".join(linhas), unsafe_allow_html=True)


def render_bloco_importacao(dados_prontos: bool = False) -> bool:
    st.markdown(
        """<div style="margin-top:6px;margin-bottom:4px"><span class="import-header-title">Importação de Dados</span><span class="import-header-badge">EXCEL, CSV OU AUTO</span></div><div class="import-header-sub">Envie a base consolidada de O.S. ou aguarde o robô detectar o arquivo automaticamente.</div><div class="import-header-line"></div>""",
        unsafe_allow_html=True,
    )
    if not dados_prontos:
        return False
    st.markdown(
        '<div class="import-alert-green"><span>Dados carregados e processados. O relatório está pronto.</span></div>',
        unsafe_allow_html=True,
    )
    return st.button(
        "Atualizar relatório",
        type="primary",
        width="stretch",
        key="btn_atualizar_relatorio",
    )


def _html_base_ativa(regioes: list[str], total: int, origem: str) -> str:
    badges = []
    for regiao in sorted({str(r).upper().strip() for r in regioes}):
        cor = CORES_REGIAO.get(regiao, CORES_REGIAO["OUTRAS"])
        badges.append(
            f'<span class="badge-regiao" style="background:{cor["bg"]};color:{cor["text"]};border-color:{cor["border"]};">{html_safe(regiao)}</span>'
        )
    origem_html = (
        f'<span class="base-info-source">Fonte: {html_safe(origem)}</span>'
        if origem
        else ""
    )
    return (
        '<div class="base-info"><span class="base-info-label">Bases analisadas</span>'
        + "".join(badges)
        + origem_html
        + f'<span class="base-info-total">{fmt_int_br(total)} registros</span></div>'
    )


def render_hero(
    titulo: str,
    subtitulo: str,
    regioes: list[str],
    total: int,
    badge: str = "",
    origem: str = "",
) -> None:
    badge_html = f'<span class="hero-badge">{html_safe(badge)}</span>' if badge else ""
    base_html = _html_base_ativa(regioes, total, origem) if total > 0 else ""
    st.markdown(
        f"""<div class="hero-container"><div class="hero-card"><div class="hero-card__layout"><div><p class="hero-eyebrow">TOTALE · RELATÓRIO OPERACIONAL</p><h1 class="hero-title">{html_safe(titulo)}</h1><p class="hero-sub">{html_safe(subtitulo)}</p>{badge_html}</div><div class="hero-side-metric"><span>Registros analisados</span><strong>{fmt_int_br(total)}</strong></div></div></div>{base_html}</div>""",
        unsafe_allow_html=True,
    )


_PALAVRAS_PCT_TABELA: Final[tuple[str, ...]] = (
    "QUEBRA",
    "FECHAMENTO",
    "%",
    "PROJEÇÃO",
    "PROJECAO",
    "CONVERSÃO",
    "CONVERSAO",
    "ACUMULADO",
)
_PALAVRAS_INT_TABELA: Final[tuple[str, ...]] = (
    "TOTAL",
    "VOLUME",
    "TAREFAS",
    "PRIORIDADE",
    "EXECUTADA",
    "TASKS",
    "ALOCADO",
    "CONSIDERADO",
)


def render_tabela(
    df: pd.DataFrame,
    titulo: str,
    icone: str,
    color_col: str | None = None,
    meta: float = Config.SLA_QUEBRA_MAXIMA,
    height: int = 400,
) -> None:
    st.markdown(
        f"""<div style="background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:.9rem 1rem;margin-bottom:.5rem"><div style="font-size:.95rem;font-weight:700;color:#0F172A;display:flex;align-items:center;gap:.5rem"><span>{html_safe(icone)}</span><span>{html_safe(titulo)}</span><span style="font-size:.68rem;background:#EFF6FF;color:#1D4ED8;padding:.18rem .55rem;border-radius:999px">{len(df)} registros</span></div></div>""",
        unsafe_allow_html=True,
    )
    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return
    formatos = {}
    for col in df.columns:
        cu = str(col).upper()
        if any(k in cu for k in _PALAVRAS_PCT_TABELA):
            formatos[str(col)] = "{:.2%}"
        elif any(k in cu for k in _PALAVRAS_INT_TABELA):
            formatos[str(col)] = "{:,.0f}"
    regras = (
        {
            "coluna": color_col,
            "meta": meta,
            "acima_meta": {"bg": "#FEF2F2", "text": "#991B1B", "bold": True},
            "abaixo_meta": {"bg": "#ECFDF5", "text": "#166534", "bold": True},
        }
        if color_col and color_col in df.columns
        else None
    )
    render_table_html(
        df,
        fmt=formatos,
        color_rules=regras,
        colunas_num=df.select_dtypes(include=np.number).columns.astype(str).tolist(),
        height=height,
    )


def render_card_gpon(df: pd.DataFrame) -> None:
    r = Motor.resumo_gpon(df)
    st.markdown(
        f"""<div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;margin-bottom:1rem;padding:1rem 1.2rem;border:1px solid #BFDBFE;border-radius:12px;background:#EFF6FF"><div><div style="color:#475569;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase">Indicador GPON</div><div style="margin-top:.25rem;color:#1E3A8A;font-size:1.45rem;font-weight:750">{fmt_int_br(r["sim"])}</div><div style="color:#475569;font-size:.78rem">{r["percentual"]:.1f}% com GPON habilitado</div></div><div style="text-align:right"><div style="color:#64748B;font-size:.7rem">Total analisado</div><div style="color:#0F172A;font-size:1.1rem;font-weight:700">{fmt_int_br(r["total"])}</div></div></div>""",
        unsafe_allow_html=True,
    )


def view_resumo_executivo(df: pd.DataFrame, meta_sla: float) -> None:
    col_tipo = str(df.attrs.get("tipo_servico_coluna", ""))
    tipos_proc = set(
        df.get("TIPO_SERVICO", pd.Series(dtype="object")).dropna().astype(str).unique()
    )
    if not col_tipo:
        st.warning(
            "A base não possui coluna identificável de tipo de serviço. Os registros foram classificados como 'Outros'."
        )
    if tipos_proc and tipos_proc <= {"Outros"}:
        originais = df.attrs.get("valores_tipo_servico_originais", {})
        st.warning(
            "A coluna de segmento foi encontrada, mas nenhum valor foi reconhecido como Novos Domicílios, PME ou Migração."
        )
        if isinstance(originais, dict) and originais:
            st.caption(
                "Valores originais encontrados: "
                + ", ".join(list(originais.keys())[:10])
            )
    if "FLAG_GPON" in df.columns:
        render_card_gpon(df)
    matriz = Motor.matriz_resumo(df)
    if matriz.empty:
        st.warning("Dados insuficientes para montar a Matriz Executiva.")
        return
    if "Monitor" in matriz.columns:
        mask = matriz["Monitor"].astype(str).str.strip().str.upper().eq("TOTAL GERAL")
        matriz = pd.concat([matriz.loc[~mask], matriz.loc[mask]], ignore_index=True)
    render_matriz_executiva(matriz, meta_geral=meta_sla)
    st.download_button(
        "Baixar matriz (Excel)",
        data=gerar_excel(matriz, "Matriz_Resumo"),
        file_name="Matriz_Resumo_Quebra.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )


def view_analise_detalhada(
    df: pd.DataFrame,
    p_ot: float,
    p_base: float,
    p_pess: float,
    min_aloc: float,
    meta_sla: float,
) -> None:
    if CRITERIOS.disponivel and CRITERIOS.render_painel:
        with st.expander("Critérios de classificação", expanded=False):
            CRITERIOS.render_painel(df)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Projeções", "Projeção personalizada", "Rankings", "Causas raiz", "Backoffice"]
    )
    with tab1:
        render_section_header("", "Cenários de Projeção de Fechamento")
        render_tabela(
            Motor.tabela_cenarios(df, "MONITOR", p_ot, p_base, p_pess, min_aloc),
            "Projeção por Monitor",
            "",
            color_col="Fechamento Base",
            meta=meta_sla,
        )
    with tab2:
        render_section_header("", "Projeção Personalizada")
        c1, c2 = st.columns(2)
        with c1:
            prob = st.slider("Probabilidade de Conversão (%)", 0, 100, 30, step=5) / 100
        with c2:
            grupo = st.selectbox("Agrupar por", ["MONITOR", "TÉCNICO", "REGIÃO"])
        proj = Motor.projetar(df, probabilidade=prob, grupo=grupo, meta_sla=meta_sla)
        render_tabela(
            proj,
            f"Projeção por {grupo}",
            "",
            color_col="Projeção Fechamento",
            meta=meta_sla,
        )
        if not proj.empty:
            k1, k2, k3, k4 = st.columns(4)
            total = len(proj)
            dentro = int(proj["Projeção Fechamento"].le(meta_sla).sum())
            atencao = int(
                (
                    proj["Projeção Fechamento"].gt(meta_sla)
                    & proj["Projeção Fechamento"].le(meta_sla * 1.25)
                ).sum()
            )
            critico = int(proj["Projeção Fechamento"].gt(meta_sla * 1.25).sum())
            conv_med = float(proj["Conversão Necessária"].mean())

            def pct(x: int) -> str:
                return f"{x / total:.0%}" if total else "0%"

            render_kpi_sm(k1, "Dentro da Meta", str(dentro), pct(dentro), "verde")
            render_kpi_sm(k2, "Atenção", str(atencao), pct(atencao), "amarelo")
            render_kpi_sm(k3, "Crítico", str(critico), pct(critico), "vermelho")
            render_kpi_sm(
                k4, "Conversão Média", f"{conv_med:.1%}", "Para atingir meta", "azul"
            )
    with tab3:
        render_section_header("", "Técnicos Mais Críticos")
        render_tabela(
            Motor.tecnicos_criticos(df, "TODOS", p_base, min_aloc, 20, p_ot, p_pess),
            "Top 20 Técnicos com Maior Risco",
            "",
            color_col="Fechamento Base",
            meta=meta_sla,
        )
    with tab4:
        render_section_header("", "Análise de Causa Raiz")
        col = DF.buscar_coluna(
            df, ("CÓD DE BAIXA 1", "COD DE BAIXA 1", "MOTIVO DE BAIXA", "COD_BAIXA")
        )
        if col:
            render_tabela(Motor.causa_raiz(df, col, 10), "Pareto de Motivos", "")
        else:
            st.warning("Coluna de Código/Motivo de Baixa não encontrada.")
    with tab5:
        render_section_header("", "Gestão de Fila (Backoffice)")
        render_tabela(Motor.backoffice_fila(df), "Fila Priorizada", "")


def view_auditoria(df: pd.DataFrame) -> None:
    render_section_header("", "Auditoria de Processamento")
    total = len(df)
    importado = int(df.attrs.get("total_importado", total))
    rem_status = int(df.attrs.get("removidos_suspensos_cancelados", 0))
    rem_contrato = int(df.attrs.get("removidos_contrato", 0))
    gpon_sim = int(df.attrs.get("flag_gpon_sim_count", 0))
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Importados", fmt_int_br(importado))
    k2.metric("Processados", fmt_int_br(total))
    k3.metric("Removidos por status", fmt_int_br(rem_status))
    k4.metric("Contratos inválidos", fmt_int_br(rem_contrato))
    st.caption(
        f"Arquivo de origem: {df.attrs.get('arquivo_origem', 'Não identificado')}"
    )
    st.caption(
        f"Coluna de tipo de serviço: {df.attrs.get('tipo_servico_coluna', 'Não identificada')}"
    )
    if "FLAG_GPON" in df.columns:
        st.markdown("#### Indicador GPON")
        g1, g2 = st.columns(2)
        pct_sim = gpon_sim / total * 100 if total > 0 else 0.0
        pct_nao = (total - gpon_sim) / total * 100 if total > 0 else 0.0
        g1.metric("FLAG_GPON = Sim", f"{gpon_sim:,}", f"{pct_sim:.1f}%")
        g2.metric("FLAG_GPON = Não", f"{total - gpon_sim:,}", f"{pct_nao:.1f}%")
    if "TIPO_SERVICO" in df.columns:
        st.markdown("### Distribuição de tipo de serviço")
        dist = df["TIPO_SERVICO"].value_counts().reset_index()
        dist.columns = ["Segmento", "Registros"]
        dist["%"] = (dist["Registros"] / total * 100).round(1).astype(str) + "%"
        st.dataframe(dist, hide_index=True, width="stretch")
        nd = int(dist.loc[dist["Segmento"] == "Novos Domicílios", "Registros"].sum())
        pme = int(dist.loc[dist["Segmento"] == "PME", "Registros"].sum())
        if nd == 0 and pme == 0:
            st.error(
                "Novos Domicílios e PME estão zerados. Verifique a coluna de tipo de serviço e os critérios de classificação."
            )
    if (
        CRITERIOS.disponivel
        and CRITERIOS.detect_tipo_os
        and CRITERIOS.detect_habilidade
        and CRITERIOS.detect_flag_gpon
    ):
        with st.expander("Diagnóstico de critérios", expanded=False):
            col_tipo, col_hab, col_gpon = (
                CRITERIOS.detect_tipo_os(df),
                CRITERIOS.detect_habilidade(df),
                CRITERIOS.detect_flag_gpon(df),
            )
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "TIPO O.S 1",
                "Encontrada" if col_tipo else "Não encontrada",
                col_tipo or "—",
            )
            c2.metric(
                "HABILIDADE",
                "Encontrada" if col_hab else "Não encontrada",
                col_hab or "—",
            )
            c3.metric(
                "FLAG_GPON",
                "Encontrada" if col_gpon else "Não encontrada",
                col_gpon or "—",
            )
            if col_tipo:
                st.markdown("Amostras de tipo de O.S.")
                st.code(df[col_tipo].dropna().astype(str).unique()[:15].tolist())
            if col_hab:
                st.markdown("Amostras de habilidade")
                st.code(df[col_hab].dropna().astype(str).unique()[:15].tolist())
    with st.expander("Visualizar amostra da base processada", expanded=False):
        st.dataframe(df.head(200), width="stretch", hide_index=True)


_CHAVES_SESSAO: Final[tuple[str, ...]] = (
    "df_memoria",
    "df_memoria_raw",
    "arquivo_processado",
    "origem_dados",
    "_robo_df_pronto",
    "_robo_nome_arquivo",
    "_robo_dados_disponiveis",
    "robo_hora_sucesso",
)
_CHAVES_ATIVOS: Final[tuple[str, ...]] = ("df_gs_manual", "arquivo_ativos_processado")


def limpar_sessao(incluir_ativos: bool = True) -> None:
    for k in list(_CHAVES_SESSAO) + (list(_CHAVES_ATIVOS) if incluir_ativos else []):
        st.session_state.pop(k, None)
    st.session_state["upload_nonce"] = int(st.session_state.get("upload_nonce", 0)) + 1


def _sidebar_ativos(nonce: int) -> None:
    with st.sidebar.expander("Configurações e Lista de Ativos", expanded=False):
        st.markdown("### Lista de Ativos")
        upload = st.file_uploader(
            "Upload de contingência de ativos",
            type=["csv", "xlsx", "xlsm"],
            key=f"uploaded_ativos_manual_{nonce}",
        )
        if upload:
            try:
                b = upload.getvalue()
                hid = hash_upload(upload.name, b)
                if st.session_state.get("arquivo_ativos_processado") != hid:
                    proc = DataLoader.processar_lista_ativos(
                        DataLoader.ler_arquivo(b, upload.name)
                    )
                    if proc.empty:
                        raise ValueError(
                            "A base de ativos não possui coluna LOGIN válida."
                        )
                    (
                        st.session_state["df_gs_manual"],
                        st.session_state["arquivo_ativos_processado"],
                    ) = (proc, hid)
                    st.toast(f"{len(proc)} ativos carregados.")
            except Exception as erro:
                st.error(f"Erro ao processar base de ativos: {erro}")
        if st.button("Reiniciar aplicação", width="stretch", type="secondary"):
            limpar_sessao(True)
            DataLoader.ler_arquivo.clear()
            DataLoader.buscar_gsheets.clear()
            _cache_matriz.clear()
            st.rerun()
        if st.button("Limpar cache", width="stretch", type="secondary"):
            limpar_sessao(True)
            DataLoader.ler_arquivo.clear()
            DataLoader.buscar_gsheets.clear()
            _cache_matriz.clear()
            st.rerun()


def _sidebar_filtros() -> tuple[float, float, float, float]:
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Filtros de projeção")
    p_ot = st.sidebar.slider("Probabilidade otimista (%)", 0, 100, 15, step=5) / 100
    p_base = st.sidebar.slider("Probabilidade base (%)", 0, 100, 30, step=5) / 100
    p_pess = st.sidebar.slider("Probabilidade pessimista (%)", 0, 100, 50, step=5) / 100
    min_aloc = float(
        st.sidebar.number_input("Mínimo de alocações", min_value=1, value=5)
    )
    if not (p_ot <= p_base <= p_pess):
        st.sidebar.warning("O esperado é: otimista ≤ base ≤ pessimista.")
    return p_ot, p_base, p_pess, min_aloc


def _sidebar_robo(df_ativos: pd.DataFrame) -> None:
    st.sidebar.markdown("---")
    if not (ROBO_DISPONIVEL and _ROBO_FN):
        st.sidebar.info("Robô offline. Utilize o upload manual.")
        return
    try:
        _ROBO_FN(
            etl_fn=lambda df_raw, df_gs_arg=None, **_: DataLoader.callback_robo_etl(
                df_raw, df_gs_arg if df_gs_arg is not None else df_ativos
            ),
            gsheets_fn=lambda: df_ativos,
            pasta_padrao=st.session_state.get(
                "robo_pasta_alvo", str(Path.home() / "Downloads")
            ),
            ciclos_estabilidade=1,
            mostrar_toggle=True,
            mostrar_config=True,
        )
    except Exception as erro:
        st.sidebar.error(f"Erro ao inicializar robô: {erro}")


def _processar_upload(upload: Any, df_ativos: pd.DataFrame) -> None:
    if not upload:
        return
    try:
        b = upload.getvalue()
        hid = hash_upload(upload.name, b)
        if st.session_state.get("arquivo_processado") == hid:
            return
        with st.spinner(f"Processando {upload.name}..."):
            raw = DataLoader.ler_arquivo(b, upload.name)
            base = DataLoader.preparar_base(raw, df_ativos, filename=upload.name)
            if base.empty:
                raise ValueError("Nenhuma O.S. válida permaneceu após o tratamento.")
            st.session_state.update(
                {
                    "df_memoria_raw": raw,
                    "df_memoria": base,
                    "arquivo_processado": hid,
                    "origem_dados": f"Upload ({upload.name})",
                    "_robo_dados_disponiveis": True,
                    "mensagem_flash": "Base processada com sucesso.",
                }
            )
            st.rerun()
    except Exception as erro:
        st.error(f"Erro no processamento do arquivo: {erro}")


def _render_upload_os(dados_prontos: bool, nonce: int) -> Any:
    if not dados_prontos:
        return st.file_uploader(
            "Carregar base de O.S. manualmente",
            type=["csv", "xlsx", "xlsm"],
            key=f"upload_os_principal_{nonce}",
        )
    with st.expander("Substituir base de O.S. manualmente", expanded=False):
        return st.file_uploader(
            "Upload manual O.S.",
            type=["csv", "xlsx", "xlsm"],
            key=f"upload_os_substituir_{nonce}",
        )


def main() -> None:
    injetar_css()
    msg = st.session_state.pop("mensagem_flash", "")
    if msg:
        st.success(str(msg))
    render_sidebar_brand(
        titulo="TOTALE",
        subtitulo="Quebra Operacional",
        logo="monitoring",
        ambiente="produção",
        versao="v5.4.0",
        mostrar_data=True,
    )
    st.session_state.setdefault("upload_nonce", 0)
    nonce = int(st.session_state["upload_nonce"])
    _sidebar_ativos(nonce)
    ativos_sessao = df_sessao("df_gs_manual")
    df_ativos = (
        ativos_sessao
        if ativos_sessao is not None and not ativos_sessao.empty
        else DataLoader.buscar_gsheets()
    )
    if df_ativos is None:
        df_ativos = pd.DataFrame()
    if not df_ativos.empty:
        st.sidebar.caption(f"Lista de ativos: {len(df_ativos)} registros")
    else:
        st.sidebar.warning(
            "Lista de ativos indisponível. Utilize o upload manual nas configurações."
        )
    _sidebar_robo(df_ativos)
    df_atual = df_sessao("df_memoria")
    dados_prontos = df_atual is not None and not df_atual.empty
    if render_bloco_importacao(dados_prontos):
        st.session_state["mensagem_flash"] = "Relatório atualizado com sucesso."
        st.rerun()
    upload = _render_upload_os(dados_prontos, nonce)
    _processar_upload(upload, df_ativos)
    df = df_sessao("df_memoria")
    if df is None or df.empty:
        st.info("Carregue uma base de O.S. para iniciar a análise.")
        return
    p_ot, p_base, p_pess, min_aloc = _sidebar_filtros()
    regioes = (
        sorted(df["REGIÃO"].dropna().astype(str).unique().tolist())
        if "REGIÃO" in df.columns
        else ["TODAS"]
    )
    render_hero(
        "Super Relatório Corporativo",
        "Análise unificada de desempenho operacional",
        regioes,
        len(df),
        badge="TOTALE OPERACIONAL",
        origem=str(st.session_state.get("origem_dados", "Base carregada")),
    )
    if "TÉCNICO" in df.columns:
        nao_mapeados = int(df["TÉCNICO"].eq("NÃO MAPEADO").sum())
        if nao_mapeados > 0:
            pct = nao_mapeados / len(df) * 100
            st.warning(
                f"Aviso de integração: {nao_mapeados} O.S. ({pct:.1f}% do volume ativo) sem correspondência na Lista de Ativos."
            )
        else:
            st.success("Todos os logins estão mapeados na Lista de Ativos.")
    aba = st.radio(
        "Navegação",
        ["Resumo executivo", "Análise detalhada", "Auditoria"],
        horizontal=True,
    )
    rotas: dict[str, Callable[[], None]] = {
        "Resumo executivo": lambda: view_resumo_executivo(df, Config.SLA_QUEBRA_MAXIMA),
        "Análise detalhada": lambda: view_analise_detalhada(
            df, p_ot, p_base, p_pess, min_aloc, Config.SLA_QUEBRA_MAXIMA
        ),
        "Auditoria": lambda: view_auditoria(df),
    }
    rotas[aba]()
    st.divider()


if __name__ == "__main__":
    main()
