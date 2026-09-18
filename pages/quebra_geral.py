"""
quebra.py
=========
Super Relatório Corporativo Unificado | Quebra Operacional TOTALE

Versão: 4.3.0 (Integração com Critérios)
Author: TOTALE Tecnologia
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import re
import sys
import unicodedata
from collections.abc import Callable, Iterable
from datetime import datetime
from functools import lru_cache
from html import escape
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Final, Literal, cast
from urllib.parse import quote

import numpy as np
import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# ─────────────────────────────────────────────────────────────────────
# IMPORTAÇÃO DO MÓDULO CRITÉRIOS
# ─────────────────────────────────────────────────────────────────────
CRITERIOS_DISPONIVEL = False
try:
    from components.criterios import (
        classificar_tipo_servico as _classificar_tipo_servico_criterios,
        detectar_col_tipo_os_1,
        detectar_col_habilidade,
        detectar_col_flag_gpon,
        render_painel_criterios,
        TERMOS_ND,
        TERMO_MIGRACAO_OS,
        TERMO_GPON_HABILIDADE,
        TERMO_PME_HABILIDADE,
        VAZIOS_GERAIS,
    )
    CRITERIOS_DISPONIVEL = True
except ImportError as erro:
    CRITERIOS_DISPONIVEL = False
    st.warning(f"⚠️ Módulo critérios não disponível: {erro}")

# ─────────────────────────────────────────────────────────────────────
# PATH BOOTSTRAP
# ─────────────────────────────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_ROOT = _DIR.parent

for _path in (_DIR, _ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


# ────────────────────────────────────────────────────────────────────
# FONTES
# ─────────────────────────────────────────────────────────────────────
class Fontes:
    TITULO: Final[str] = "'Manrope', sans-serif"
    TEXTO: Final[str] = "'Inter', sans-serif"


# ─────────────────────────────────────────────────────────────────────
# TIPAGENS
# ─────────────────────────────────────────────────────────────────────
TemaKPI = Literal[
    "azul",
    "verde",
    "vermelho",
    "laranja",
    "cinza",
    "roxo",
    "amarelo",
    "escuro",
]


# ─────────────────────────────────────────────────────────────────────
# COMPONENTES VISUAIS OPCIONAIS
# ─────────────────────────────────────────────────────────────────────
_component_section_header: Callable[..., Any] | None = None
_component_sidebar_brand: Callable[..., Any] | None = None
_component_table_html: Callable[..., Any] | None = None
_component_insight: Callable[..., Any] | None = None
_component_kpi: Callable[..., Any] | None = None
_component_kpi_sm: Callable[..., Any] | None = None

try:
    from components.componentes import render_insight as _component_insight
    from components.componentes import render_kpi as _component_kpi
    from components.componentes import render_kpi_sm as _component_kpi_sm
    from components.componentes import (
        render_section_header as _component_section_header,
    )
    from components.componentes import render_sidebar_brand as _component_sidebar_brand
    from components.componentes import render_table_html as _component_table_html

    COMPONENTES_DISPONIVEIS = True

except ImportError:
    COMPONENTES_DISPONIVEIS = False


def render_section_header(icone: str, titulo: str) -> None:
    if _component_section_header is not None:
        _component_section_header(icone, titulo)
        return

    st.subheader(f"{icone} {titulo}" if icone else titulo)


def render_sidebar_brand(**kwargs: Any) -> None:
    if _component_sidebar_brand is not None:
        _component_sidebar_brand(**kwargs)


def render_table_html(df: pd.DataFrame, **kwargs: Any) -> None:
    if _component_table_html is not None:
        _component_table_html(df, **kwargs)
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def render_insight(
    texto: str,
    tipo: Literal["ok", "info", "alerta", "critico", "acao"] = "info",
) -> None:
    if _component_insight is not None:
        _component_insight(texto, tipo)
        return

    if tipo == "ok":
        st.success(texto)
    elif tipo in {"critico", "alerta"}:
        st.warning(texto)
    elif tipo == "acao":
        st.error(texto)
    else:
        st.info(texto)


# ────────────────────────────────────────────────────────────────────
# ROBÔ OPCIONAL
# ─────────────────────────────────────────────────────────────────────
RoboCallable = Callable[..., Any]

ROBO_DISPONIVEL: bool = False
_impl_robo: RoboCallable | None = None
_ROBO_IMPORT_ERRO: str = ""


def _tentar_import_robo() -> tuple[RoboCallable | None, str]:
    try:
        module = importlib.import_module("robo.robo_local")

        funcao = getattr(module, "renderizar_robo_local", None)
        if not callable(funcao):
            funcao = getattr(module, "render_robo_local", None)

        if callable(funcao):
            arquivo_modulo = getattr(module, "__file__", "módulo sem caminho")
            return funcao, f"OK ({arquivo_modulo})"

        return None, "Módulo encontrado, mas sem função de renderização compatível."

    except Exception as erro:
        return None, f"{type(erro).__name__}: {erro}"


_impl_robo, _ROBO_IMPORT_ERRO = _tentar_import_robo()
ROBO_DISPONIVEL: bool = _impl_robo is not None


def renderizar_robo_local(*args: Any, **kwargs: Any) -> None:
    if _impl_robo is None:
        st.sidebar.warning("🤖 Robô offline. Utilize upload manual.")
        return

    try:
        _impl_robo(*args, **kwargs)
    except Exception as erro:
        st.sidebar.error(f"Erro no Robô: {erro}")


# ─────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ────────────────────────────────────────────────────────────────────
class Config:
    SLA_QUEBRA_MAXIMA: Final[float] = 0.20
    SLA_MIGRACAO_MAXIMA: Final[float] = 0.25

    URL_LISTA_ATIVOS: Final[str] = (
        "https://docs.google.com/spreadsheets/d/"
        "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    )

    SHEET_ID_ATIVOS: Final[str] = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"

    WORKSHEET_ATIVOS: Final[str] = "lista_ativos"

    STATUS_ORDEM: Final[tuple[str, ...]] = (
        "Executada",
        "Não Executada",
        "Pendente",
    )

    ORDEM_TIPOS: Final[tuple[str, ...]] = (
        "Novos Domicílios",
        "PME",
        "Migração",
        "Outros",
    )

    # EXPANDIDO: Mais variações de nomes de colunas
    COLUNAS_TIPO_SERVICO: Final[tuple[str, ...]] = (
        "TIPO_SERVICO",
        "TIPO SERVICO",
        "TIPO DE SERVICO",
        "TIPO DE SERVIÇO",
        "SERVICO",
        "SERVIÇO",
        "SEGMENTO",
        "PRODUTO",
        "TIPO DE ORDEM",
        "TIPO_ORDEM",
        "CATEGORIA",
        "CLASSIFICACAO",
        "CLASSIFICAÇÃO",
        "NATUREZA",
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


MAPA_CODIGO_NUMERICO: Final[dict[int, str]] = {
    **{
        codigo: "Não Executada"
        for codigo in [
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
    },
    **{
        codigo: "Executada"
        for codigo in [
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
    },
}

CORES_REGIAO: Final[dict[str, dict[str, str]]] = {
    "LESTE": {
        "bg": "#DBEAFE",
        "text": "#1E40AF",
        "border": "#3B82F6",
    },
    "GRU": {
        "bg": "#D1FAE5",
        "text": "#065F46",
        "border": "#10B981",
    },
    "ABCDM": {
        "bg": "#EDE9FE",
        "text": "#5B21B6",
        "border": "#8B5CF6",
    },
    "OUTRAS": {
        "bg": "#F1F5F9",
        "text": "#475569",
        "border": "#94A3B8",
    },
}

CIDADES_LESTE: Final[frozenset[str]] = frozenset(
    {
        "SAO PAULO",
    }
)

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
    {
        "",
        "NAN",
        "NONE",
        "NULL",
        "NAT",
        "NA",
        "N/A",
        "-",
    }
)

RE_ESPACOS: Final[re.Pattern[str]] = re.compile(r"\s+")
RE_ALFANUMERICO: Final[re.Pattern[str]] = re.compile(r"[^A-Z0-9]")
RE_NUMERO_INICIAL: Final[re.Pattern[str]] = re.compile(r"^(\d+)")
RE_LOGIN_DECIMAL: Final[re.Pattern[str]] = re.compile(r"^(\d+)\.0+$")

RE_MIGRACAO: Final[re.Pattern[str]] = re.compile(
    r"\bMIGR\b"
    r"|\bUPGRADE\b"
    r"|\bTROCA\b"
    r"|\bMELHORIA\b"
    r"|\bSWAP\b",
    re.IGNORECASE
)

RE_PME: Final[re.Pattern[str]] = re.compile(
    r"\bPME\b"
    r"|\bP\s*M\s*E\b"
    r"|\bPJ\b"
    r"|\bJURIDICO\b"
    r"|\bJURÍDICO\b"
    r"|\bEMPRESA\b"
    r"|\bCORPORATIVO\b"
    r"|\bCOMERCIAL\b",
    re.IGNORECASE,
)

RE_NOVOS_DOMICILIOS: Final[re.Pattern[str]] = re.compile(
    r"\bND\b"
    r"|\bINSTALACAO\b"
    r"|\bINSTALAÇÃO\b"
    r"|\bNOV.*DOMICIL"
    r"|\bDOMICIL"
    r"|\bRESIDENCIAL\b"
    r"|\bNOV.*INSTAL"
    r"|\bPRIMEIRA\b"
    r"|\bFIBRA\s*NOVA\b",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────
def _html(valor: Any) -> str:
    return escape(str(valor), quote=True)


def _fmt_pct_br(valor: Any) -> str:
    try:
        numero = float(valor)

        if not np.isfinite(numero):
            return "—"

        texto = f"{numero * 100:,.2f}%"
        return texto.replace(",", "X").replace(".", ",").replace("X", ".")

    except (TypeError, ValueError):
        return "—"


def _fmt_int_br(valor: Any) -> str:
    try:
        numero = float(valor)

        if not np.isfinite(numero):
            return "—"

        return f"{int(round(numero)):,}".replace(",", ".")

    except (TypeError, ValueError):
        return "—"


def _is_missing_scalar(valor: Any) -> bool:
    try:
        resultado = pd.isna(valor)

        if isinstance(resultado, (bool, np.bool_)):
            return bool(resultado)

        return False

    except (TypeError, ValueError):
        return False


def _divisao_segura(
    numerador: pd.Series,
    denominador: pd.Series,
    padrao: float = 0.0,
) -> pd.Series:
    num = pd.to_numeric(numerador, errors="coerce").fillna(0).to_numpy(dtype=float)
    den = pd.to_numeric(denominador, errors="coerce").fillna(0).to_numpy(dtype=float)

    resultado = np.full_like(num, padrao, dtype=float)

    np.divide(
        num,
        den,
        out=resultado,
        where=den > 0,
    )

    return pd.Series(resultado, index=numerador.index)


def _identificador_upload(nome: str, conteudo: bytes) -> str:
    hash_arquivo = hashlib.sha256(conteudo).hexdigest()
    return f"{nome}|{len(conteudo)}|{hash_arquivo}"


def _obter_dataframe_sessao(chave: str) -> pd.DataFrame | None:
    valor = st.session_state.get(chave)

    if isinstance(valor, pd.DataFrame):
        return valor

    return None


# ─────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────
def _injetar_css_global() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@400;600;700;800&display=swap');

        .import-header-title {
            font-family: 'Manrope', sans-serif;
            font-size: 32px;
            font-weight: 800;
            color: #1E293B;
            letter-spacing: -0.5px;
            margin: 0;
            display: inline-block;
        }

        .import-header-badge {
            display: inline-flex;
            align-items: center;
            background: #EEF2FF;
            color: #3B82F6;
            border: 1.5px solid #93C5FD;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 12px;
            border-radius: 9999px;
            letter-spacing: 0.6px;
            text-transform: uppercase;
            margin-left: 14px;
            vertical-align: middle;
        }

        .import-header-sub {
            font-size: 14px;
            color: #64748B;
            margin-top: 6px;
            margin-bottom: 14px;
            font-family: 'Inter', sans-serif;
        }

        .import-header-line {
            height: 3px;
            background: linear-gradient(90deg, #012869 0%, #1E40AF 30%, #F59E0B 65%, #EF4444 100%);
            border-radius: 2px;
            margin-bottom: 18px;
        }

        .import-alert-green {
            background-color: #E8F8F0;
            border: 1px solid #C2F0D9;
            border-radius: 8px;
            padding: 14px 20px;
            color: #107C41;
            font-size: 14px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 16px;
            font-family: 'Inter', sans-serif;
        }

        .hero-container {
            background: rgba(248,250,252,0.95);
            padding: 0.5rem 0;
            border-radius: 14px;
            margin-bottom: 20px;
        }

        .hero-card {
            background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
            padding: 28px 40px;
            border-radius: 14px;
            color: white;
            box-shadow: 0 10px 40px rgba(1,40,105,0.20);
        }

        .hero-title {
            margin: 0;
            font-size: 30px;
            font-weight: 800;
            color: white !important;
            font-family: 'Manrope', sans-serif;
        }

        .hero-sub {
            margin: 6px 0 0 0;
            font-size: 14px;
            color: #F8FAFC;
            font-family: 'Inter', sans-serif;
        }

        .base-info {
            background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
            padding: 1rem 1.5rem;
            border-radius: 0.75rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.6rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .badge-regiao {
            padding: 0.3rem 0.9rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
            border: 2px solid;
        }

        .matriz-table-container {
            width: 100%;
            overflow-x: auto;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.06);
            border: 1px solid #E2E8F0;
            background: #FFFFFF;
            margin-bottom: 16px;
            font-family: 'Inter', sans-serif;
        }

        .matriz-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        .matriz-table th {
            background: #F8FAFC;
            color: #475569;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 14px 16px;
            border-bottom: 2px solid #E2E8F0;
            text-align: center;
        }

        .matriz-table th:first-child {
            text-align: left;
        }

        .matriz-table td {
            padding: 10px 16px;
            border-bottom: 1px solid #F1F5F9;
            text-align: center;
            color: #1E293B;
        }

        .matriz-table td:first-child {
            text-align: left;
            font-weight: 600;
        }

        .matriz-table tr:hover {
            background-color: #F8FAFC;
        }

        .matriz-table tr.total-row {
            background-color: #F1F5F9;
            font-weight: 800;
            border-top: 2px solid #CBD5E1;
        }

        .badge-meta-ok {
            background-color: #DCFCE7;
            color: #15803D;
            font-weight: 700;
            padding: 5px 12px;
            border-radius: 6px;
            display: inline-block;
            min-width: 70px;
            border: 1px solid #86EFAC;
        }

        .badge-meta-nok {
            background-color: #FEE2E2;
            color: #B91C1C;
            font-weight: 700;
            padding: 5px 12px;
            border-radius: 6px;
            display: inline-block;
            min-width: 70px;
            border: 1px solid #FCA5A5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# KPI
# ─────────────────────────────────────────────────────────────────────
TEMAS_ESPECIAIS: Final[dict[str, dict[str, str]]] = {
    "amarelo": {
        "fundo": "#FEF9C3",
        "texto": "#854D0E",
        "borda": "#EAB308",
        "titulo": "#A16207",
    },
    "roxo": {
        "fundo": "#FAF5FF",
        "texto": "#7E22CE",
        "borda": "#A855F7",
        "titulo": "#6B21A8",
    },
    "escuro": {
        "fundo": "#1E293B",
        "texto": "#FFFFFF",
        "borda": "#475569",
        "titulo": "#E2E8F0",
    },
}


def render_kpi_sm(
    col: Any,
    label: str,
    value: str,
    sub: str = "",
    tema: TemaKPI = "azul",
) -> None:
    if tema not in TEMAS_ESPECIAIS:
        if _component_kpi_sm is not None:
            _component_kpi_sm(col, label, value, sub, tema)
        else:
            col.metric(label, value, sub)
        return

    estilo = TEMAS_ESPECIAIS[tema]

    col.markdown(
        f"""
        <div style="
            background:{estilo["fundo"]};
            border-left:3px solid {estilo["borda"]};
            border-radius:6px;
            padding:12px 16px;
            margin-bottom:8px;
            box-shadow:0 1px 4px rgba(0,0,0,0.06);
        ">
            <div style="
                font-family:{Fontes.TEXTO};
                font-size:10px;
                color:{estilo["titulo"]};
                text-transform:uppercase;
                letter-spacing:1px;
                font-weight:700;
            ">
                {_html(label)}
            </div>
            <div style="
                font-family:{Fontes.TITULO};
                font-size:20px;
                color:{estilo["texto"]};
                font-weight:800;
                line-height:1.2;
                margin-top:4px;
            ">
                {_html(value)}
            </div>
            <div style="
                font-family:{Fontes.TEXTO};
                font-size:11px;
                color:{estilo["titulo"]};
                margin-top:2px;
            ">
                {_html(sub)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────
class Utils:
    @staticmethod
    def normalizar_texto(valor: Any) -> str:
        if valor is None:
            return ""
        try:
            ausente = pd.isna(valor)

            if isinstance(ausente, (bool, np.bool_)) and bool(ausente):
                return ""

        except (TypeError, ValueError):
            pass

        texto = unicodedata.normalize("NFKD", str(valor))
        texto = "".join(
            caractere for caractere in texto if not unicodedata.combining(caractere)
        )

        texto = texto.upper().strip()
        return RE_ESPACOS.sub(" ", texto)

    @staticmethod
    def normalizar_coluna(valor: Any) -> str:
        return RE_ALFANUMERICO.sub("", Utils.normalizar_texto(valor))

    @staticmethod
    def normalizar_login(valor: Any) -> str:
        texto = Utils.normalizar_texto(valor).replace(" ", "")

        match = RE_LOGIN_DECIMAL.match(texto)
        if match:
            return match.group(1)

        return texto

    @staticmethod
    def obter_serie(
        df: pd.DataFrame | None,
        coluna: str | None,
        padrao: Any = "",
        *,
        copiar: bool = False,
        consolidar_duplicadas: bool = True,
    ) -> pd.Series:
        """
        Retorna sempre uma ``pd.Series`` alinhada ao índice do DataFrame.
        """
        if df is None:
            return pd.Series(dtype="object", name=coluna)

        if coluna is None or coluna not in df.columns:
            return pd.Series(
                padrao,
                index=df.index,
                dtype="object",
                name=coluna,
            )

        obtido: Any = df[coluna]

        if isinstance(obtido, pd.DataFrame):
            if consolidar_duplicadas and obtido.shape[1] > 1:
                obtido = obtido.bfill(axis=1).iloc[:, 0]
            else:
                obtido = obtido.iloc[:, 0]

        serie = cast(pd.Series, obtido)

        if not serie.index.equals(df.index):
            serie = serie.reindex(df.index)

        serie.name = coluna

        return serie.copy() if copiar else serie

    @staticmethod
    def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        resultado = df.copy()

        nomes: list[str] = []
        usados: dict[str, int] = {}

        for coluna in resultado.columns:
            base = Utils.normalizar_texto(coluna) or "COLUNA"

            if base not in usados:
                usados[base] = 1
                nomes.append(base)
                continue

            usados[base] += 1
            nomes.append(f"{base}__{usados[base]}")

        resultado.columns = nomes
        return resultado

    @staticmethod
    def buscar_coluna(
        df: pd.DataFrame | None,
        palavras: tuple[str, ...] | list[str],
    ) -> str | None:
        if df is None:
            return None

        mapa_colunas = {
            Utils.normalizar_coluna(coluna): str(coluna) for coluna in df.columns
        }

        for palavra in palavras:
            alvo = Utils.normalizar_coluna(palavra)

            if alvo and alvo in mapa_colunas:
                return mapa_colunas[alvo]

        for palavra in palavras:
            alvo = Utils.normalizar_coluna(palavra)

            if len(alvo) < 4:
                continue

            for coluna_normalizada, coluna_original in mapa_colunas.items():
                if alvo == "CONTRATO" and "STATUS" in coluna_normalizada:
                    continue

                if alvo in coluna_normalizada or coluna_normalizada in alvo:
                    return coluna_original

        return None

    @staticmethod
    def converter_numero(valor: Any) -> float:
        if valor is None:
            return np.nan

        try:
            if isinstance(valor, (int, float, np.number)):
                numero = float(valor)
                return numero if np.isfinite(numero) else np.nan
        except (TypeError, ValueError):
            pass

        texto = str(valor).strip()

        if not texto:
            return np.nan

        texto = re.sub(r"[^\d,.\-]", "", texto)

        if not texto or texto in {"-", ".", ","}:
            return np.nan

        try:
            if "," in texto and "." in texto:
                if texto.rfind(",") > texto.rfind("."):
                    texto = texto.replace(".", "").replace(",", ".")
                else:
                    texto = texto.replace(",", "")

            elif "," in texto:
                if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+", texto):
                    texto = texto.replace(",", "")
                else:
                    texto = texto.replace(",", ".")

            elif "." in texto:
                if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", texto):
                    texto = texto.replace(".", "")

            numero = float(texto)
            return numero if np.isfinite(numero) else np.nan

        except (TypeError, ValueError):
            return np.nan

    @staticmethod
    def classificar_tipo_servico(valor: Any) -> str:
        """
        Fallback: Converte o texto original do serviço para uma das categorias oficiais.
        Usado apenas quando o módulo criterios.py não está disponível.
        """
        texto = Utils.normalizar_texto(valor)

        if not texto:
            return "Outros"

        # Migração deve ser avaliada antes das demais categorias
        if RE_MIGRACAO.search(texto):
            return "Migração"

        # Novos domicílios / residencial / nova instalação
        if RE_NOVOS_DOMICILIOS.search(texto):
            return "Novos Domicílios"

        # PME / empresarial
        if RE_PME.search(texto):
            return "PME"

        if texto in {"OUTRO", "OUTROS", "OUTRA", "OUTRAS"}:
            return "Outros"

        return "Outros"

    @staticmethod
    def gerar_tipo_servico_com_criterios(
        df: pd.DataFrame,
        usar_criterios: bool = True,
    ) -> pd.Series:
        """
        Gera TIPO_SERVICO usando o módulo criterios.py se disponível.
        Fallback para classificação por regex tradicional.
        """
        if df.empty:
            return pd.Series(dtype="object")

        if usar_criterios and CRITERIOS_DISPONIVEL:
            try:
                df_copy = df.copy()
                _, serie_tipo = _classificar_tipo_servico_criterios(df_copy)
                return serie_tipo
            except Exception as erro:
                st.warning(f"️ Erro ao usar critérios: {erro}. Usando fallback.")

        # Fallback: usa a classificação por regex tradicional
        coluna_origem = Utils.buscar_coluna(
            df,
            Config.COLUNAS_TIPO_SERVICO,
        )

        if coluna_origem is None:
            return pd.Series("Outros", index=df.index, dtype="object")

        return Utils.obter_serie(df, coluna_origem).map(Utils.classificar_tipo_servico)

    @staticmethod
    def traduzir_status_texto(valor: Any) -> str | None:
        texto = Utils.normalizar_texto(valor)

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
            termo in texto
            for termo in (
                "PEND",
                "EM ROTA",
                "INICIADO",
                "AGENDADO",
                "ABERTO",
            )
        ):
            return "Pendente"

        return None

    @staticmethod
    def traduzir_codigo_baixa(valor: Any) -> str | None:
        texto = Utils.normalizar_texto(valor)

        if texto in VALORES_AUSENTES:
            return None

        if texto in {"EM ROTA", "INICIADO", "PENDENTE"}:
            return "Pendente"

        match = RE_NUMERO_INICIAL.match(texto)

        if match is None:
            return None

        codigo = int(match.group(1))
        return MAPA_CODIGO_NUMERICO.get(codigo)

    @staticmethod
    def classificar_status_excel(df: pd.DataFrame) -> pd.Series:
        col_inicio = Utils.buscar_coluna(
            df,
            (
                "INÍCIO",
                "INICIO",
                "DATA INÍCIO",
                "DT INICIO",
                "HORA INICIO",
            ),
        )
        col_fechamento = Utils.buscar_coluna(
            df,
            (
                "MOTIVO DE FECHAMENTO EXTERNO",
                "FECHAMENTO EXTERNO",
                "MOTIVO DE FECHAMENTO",
            ),
        )

        col_status_atividade = Utils.buscar_coluna(
            df,
            (
                "STATUS DA ATIVIDADE",
                "STATUS ATIVIDADE",
                "STATUS_ATIVIDADE",
            ),
        )

        col_codigo_baixa = Utils.buscar_coluna(
            df,
            (
                "CÓD DE BAIXA 1",
                "COD DE BAIXA 1",
                "MOTIVO DE BAIXA",
                "COD_BAIXA",
            ),
        )

        col_status_os = Utils.buscar_coluna(
            df,
            (
                "STATUS DA O.S 1",
                "STATUS OS 1",
                "STATUS CONTRATO",
                "STATUS O.S.",
                "STATUS OS",
            ),
        )

        inicio = Utils.obter_serie(df, col_inicio).map(Utils.normalizar_texto)
        fechamento = Utils.obter_serie(df, col_fechamento).map(Utils.normalizar_texto)
        atividade = Utils.obter_serie(df, col_status_atividade).map(
            Utils.normalizar_texto
        )
        codigo_baixa = Utils.obter_serie(df, col_codigo_baixa)
        status_os = Utils.obter_serie(df, col_status_os).map(
            Utils.traduzir_status_texto
        )

        status_atividade = atividade.map(Utils.traduzir_status_texto)
        status_codigo = codigo_baixa.map(Utils.traduzir_codigo_baixa)

        resultado = status_codigo.where(
            status_codigo.notna(),
            status_os,
        )

        resultado = resultado.where(
            resultado.notna(),
            status_atividade,
        )

        resultado = resultado.fillna("Pendente")

        fechamento_alvo = {
            "LIBERADO NO SISTEMA NETSMS",
            "CANCELADO NO SISTEMA NETSMS",
        }

        inicio_vazio = inicio.isin(VALORES_AUSENTES)
        cond_fechamento = fechamento.isin(fechamento_alvo)

        cond_cancelado = atividade.str.contains(
            "CANCEL",
            regex=False,
            na=False,
        )

        cond_suspenso = atividade.str.contains(
            "SUSPENS",
            regex=False,
            na=False,
        )

        cond_nao_concluido = atividade.str.contains(
            "NAO CONCLU",
            regex=False,
            na=False,
        )

        resultado = resultado.mask(cond_nao_concluido, "Não Executada")
        resultado = resultado.mask(cond_suspenso, "Suspenso")
        resultado = resultado.mask(cond_cancelado, "Cancelado")
        resultado = resultado.mask((~inicio_vazio) & cond_fechamento, "Não Executada")
        resultado = resultado.mask(inicio_vazio & cond_fechamento, "Cancelado")

        return resultado.astype("object")

    @staticmethod
    def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
        nome_aba = re.sub(r"[\[\]:*?/\\]", "_", aba).strip()[:31] or "Dados"

        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=nome_aba)

            ws = writer.sheets[nome_aba]

            header_fill = PatternFill("solid", fgColor="0F172A")
            header_font = Font(
                name="Calibri",
                size=11,
                bold=True,
                color="FFFFFF",
            )

            borda_header = Border(
                bottom=Side(style="thin", color="CBD5E1"),
            )

            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                )
                cell.border = borda_header

            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions

            for indice, coluna in enumerate(df.columns, start=1):
                nome_coluna = str(coluna).upper()

                valores = [
                    len(str(coluna)),
                    *[
                        len(str(valor))
                        for valor in df[coluna]
                        .head(2000)
                        .fillna("")
                        .astype(str)
                        .tolist()
                    ],
                ]

                largura = min(max(max(valores, default=12) + 2, 12), 40)
                ws.column_dimensions[get_column_letter(indice)].width = largura

                if any(
                    token in nome_coluna
                    for token in (
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
                    )
                ):
                    for linha in range(2, ws.max_row + 1):
                        ws.cell(linha, indice).number_format = "0.00%"

        return output.getvalue()


# ─────────────────────────────────────────────────────────────────────
# LOADER / ETL
# ─────────────────────────────────────────────────────────────────────
class DataLoader:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        if not file_bytes:
            raise ValueError("O arquivo está vazio.")

        extensao = Path(filename).suffix.lower()

        if extensao == ".csv":
            return DataLoader._ler_csv(file_bytes)

        if extensao in {".xlsx", ".xlsm"}:
            return pd.read_excel(
                BytesIO(file_bytes),
                engine="openpyxl",
                dtype=str,
            )

        raise ValueError("Formato inválido. Utilize arquivos CSV, XLSX ou XLSM.")

    @staticmethod
    def _ler_csv(file_bytes: bytes) -> pd.DataFrame:
        encodings = ("utf-8-sig", "utf-8", "latin-1", "cp1252")

        texto_csv: str | None = None

        for encoding in encodings:
            try:
                texto_csv = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if texto_csv is None:
            raise ValueError("Não foi possível identificar o encoding do arquivo CSV.")

        amostra = texto_csv[:10000]

        try:
            delimitador = (
                csv.Sniffer()
                .sniff(
                    amostra,
                    delimiters=";,\t|",
                )
                .delimiter
            )
        except csv.Error:
            candidatos = (";", ",", "\t", "|")
            delimitador = max(
                candidatos,
                key=lambda item: amostra.count(item),
            )

        return pd.read_csv(
            StringIO(texto_csv),
            sep=delimitador,
            dtype=str,
            engine="python",
            on_bad_lines="skip",
            keep_default_na=False,
        )

    @staticmethod
    @st.cache_data(
        ttl=600,
        show_spinner="Sincronizando Lista de Ativos...",
    )
    def buscar_gsheets() -> pd.DataFrame:
        erros: list[str] = []
        try:
            modulo = importlib.import_module("streamlit_gsheets")
            connection_type = getattr(modulo, "GSheetsConnection")

            conn = st.connection(
                "gsheets",
                type=connection_type,
            )

            raw = getattr(conn, "read")(
                spreadsheet=Config.URL_LISTA_ATIVOS,
                worksheet=Config.WORKSHEET_ATIVOS,
            )

            if isinstance(raw, pd.DataFrame) and not raw.empty:
                return DataLoader._processar_lista_ativos(raw)

        except Exception:
            pass

        try:
            aba = quote(Config.WORKSHEET_ATIVOS)

            url = (
                f"https://docs.google.com/spreadsheets/d/"
                f"{Config.SHEET_ID_ATIVOS}/gviz/tq"
                f"?tqx=out:csv&sheet={aba}"
            )

            raw_csv = pd.read_csv(
                url,
                dtype=str,
            )

            if not raw_csv.empty:
                return DataLoader._processar_lista_ativos(raw_csv)

        except Exception:
            pass

        return pd.DataFrame()

    @staticmethod
    def _processar_lista_ativos(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()

        base = raw.copy()
        base.columns = base.columns.astype(str).str.strip()

        aliases: Final[dict[str, tuple[str, ...]]] = {
            "LOGIN": (
                "LOGIN",
                "MATRÍCULA",
                "MATRICULA",
                "ID",
                "USUARIO",
                "USUÁRIO",
            ),
            "TÉCNICO": (
                "TÉCNICO",
                "TECNICO",
                "NOME",
                "COLABORADOR",
            ),
            "MONITOR": (
                "MONITOR",
                "GESTOR",
                "SUPERVISOR",
            ),
            "BASE": (
                "BASE",
                "REGIÃO",
                "REGIAO",
            ),
        }

        resultado = pd.DataFrame(index=base.index)

        for destino, nomes in aliases.items():
            coluna = Utils.buscar_coluna(base, nomes)

            if coluna is not None:
                resultado[destino] = Utils.obter_serie(base, coluna)

        if "LOGIN" not in resultado.columns:
            return pd.DataFrame()

        resultado["LOGIN"] = resultado["LOGIN"].map(Utils.normalizar_login)

        resultado = resultado.loc[~resultado["LOGIN"].isin(VALORES_AUSENTES)].copy()

        resultado = resultado.drop_duplicates(
            subset=["LOGIN"],
            keep="last",
        )

        return resultado.reset_index(drop=True)

    @staticmethod
    def _limpar_serie_texto(
        serie: pd.Series,
        padrao: str,
    ) -> pd.Series:
        resultado = serie.fillna("").astype(str).str.strip().str.upper()

        return resultado.mask(
            resultado.isin(VALORES_AUSENTES),
            padrao,
        )

    @staticmethod
    def _classificar_regiao(valor: Any) -> str:
        cidade = Utils.normalizar_texto(valor)

        if cidade in CIDADES_LESTE:
            return "LESTE"

        if cidade in CIDADES_GRU:
            return "GRU"

        if cidade in CIDADES_ABCDM:
            return "ABCDM"

        if cidade in CORES_REGIAO:
            return cidade

        return "OUTRAS"

    @staticmethod
    def preparar_base(
        df: pd.DataFrame,
        df_gs: pd.DataFrame | None,
        filename: str = "",
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        base = Utils.padronizar_colunas(df)
        total_importado = len(base)

        coluna_tipo_origem = Utils.buscar_coluna(
            base,
            Config.COLUNAS_TIPO_SERVICO,
        )

        valores_tipo_origem: dict[str, int] = {}

        if coluna_tipo_origem is not None:
            valores_tipo = Utils.obter_serie(
                base,
                coluna_tipo_origem,
            )

            valores_tipo_origem = {
                str(chave): int(valor)
                for chave, valor in (
                    valores_tipo.fillna("")
                    .astype(str)
                    .str.strip()
                    .value_counts()
                    .head(20)
                    .items()
                )
            }

        base["STATUS CONTRATO"] = Utils.classificar_status_excel(base)

        status_upper = (
            base["STATUS CONTRATO"].fillna("").astype(str).str.upper().str.strip()
        )

        mask_remover_status = status_upper.isin(
            {
                "CANCELADO",
                "SUSPENSO",
            }
        )

        removidos_status = int(mask_remover_status.sum())

        base = base.loc[~mask_remover_status].copy()

        if base.empty:
            return pd.DataFrame()

        coluna_contrato = Utils.buscar_coluna(
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

        if coluna_contrato is not None:
            contratos = Utils.obter_serie(
                base,
                coluna_contrato,
            ).map(Utils.normalizar_texto)

            mask_contrato_invalido = contratos.isin(
                {
                    "",
                    "NAN",
                    "NONE",
                    "NULL",
                    "N/A",
                    "NA",
                    "-",
                    "0",
                }
            )

            removidos_contrato = int(mask_contrato_invalido.sum())

            base = base.loc[~mask_contrato_invalido].copy()

        if base.empty:
            return pd.DataFrame()

        coluna_total = Utils.buscar_coluna(
            base,
            (
                "TOTAL DE TAREFAS",
                "QTD TAREFAS",
                "QUANTIDADE",
                "VOLUME",
            ),
        )

        if coluna_total is not None:
            tarefas = Utils.obter_serie(
                base,
                coluna_total,
            ).map(Utils.converter_numero)

            base["TOTAL DE TAREFAS"] = (
                pd.to_numeric(
                    tarefas,
                    errors="coerce",
                )
                .fillna(1)
                .clip(lower=0)
                .round()
                .astype(int)
            )
        else:
            base["TOTAL DE TAREFAS"] = 1

        coluna_login = Utils.buscar_coluna(
            base,
            (
                "LOGIN DO TÉCNICO",
                "LOGIN DO TECNICO",
                "LOGIN",
                "USUÁRIO",
                "USUARIO",
                "MATRÍCULA",
                "MATRICULA",
            ),
        )

        ativos = (
            DataLoader._processar_lista_ativos(df_gs)
            if isinstance(df_gs, pd.DataFrame)
            else pd.DataFrame()
        )

        if coluna_login is not None and not ativos.empty:
            base["_LOGIN_CHAVE"] = Utils.obter_serie(
                base,
                coluna_login,
            ).map(Utils.normalizar_login)

            merge_ativos = pd.DataFrame(
                {
                    "_LOGIN_CHAVE": ativos["LOGIN"],
                    "_ATIVO_ENCONTRADO": True,
                }
            )

            if "TÉCNICO" in ativos.columns:
                merge_ativos["_ATIVO_TECNICO"] = ativos["TÉCNICO"]

            if "MONITOR" in ativos.columns:
                merge_ativos["_ATIVO_MONITOR"] = ativos["MONITOR"]

            if "BASE" in ativos.columns:
                merge_ativos["_ATIVO_BASE"] = ativos["BASE"]

            merge_ativos = merge_ativos.drop_duplicates(
                subset=["_LOGIN_CHAVE"],
                keep="last",
            )

            base = base.merge(
                merge_ativos,
                on="_LOGIN_CHAVE",
                how="left",
                validate="m:1",
            )

            encontrado = base["_ATIVO_ENCONTRADO"].fillna(False).astype(bool)

            if "_ATIVO_TECNICO" in base.columns:
                tecnico_ativo = DataLoader._limpar_serie_texto(
                    base["_ATIVO_TECNICO"],
                    "NÃO MAPEADO",
                )

                base["TÉCNICO"] = tecnico_ativo.where(
                    encontrado,
                    "NÃO MAPEADO",
                )
            else:
                base["TÉCNICO"] = "NÃO MAPEADO"

            if "_ATIVO_MONITOR" in base.columns:
                monitor_ativo = DataLoader._limpar_serie_texto(
                    base["_ATIVO_MONITOR"],
                    "SEM MONITOR",
                )

                base["MONITOR"] = monitor_ativo.where(
                    encontrado,
                    "SEM MONITOR",
                )
            else:
                base["MONITOR"] = "SEM MONITOR"

        else:
            if "TÉCNICO" not in base.columns:
                base["TÉCNICO"] = "NÃO MAPEADO"

            if "MONITOR" not in base.columns:
                base["MONITOR"] = "SEM MONITOR"

        base["TÉCNICO"] = DataLoader._limpar_serie_texto(
            base["TÉCNICO"],
            "NÃO MAPEADO",
        )

        base["MONITOR"] = DataLoader._limpar_serie_texto(
            base["MONITOR"],
            "SEM MONITOR",
        )

        coluna_cidade = Utils.buscar_coluna(
            base,
            (
                "CIDADE",
                "LOCALIDADE",
                "MUNICÍPIO",
                "MUNICIPIO",
            ),
        )

        if coluna_cidade is not None:
            base["REGIÃO"] = Utils.obter_serie(
                base,
                coluna_cidade,
            ).map(DataLoader._classificar_regiao)

        elif "_ATIVO_BASE" in base.columns:
            base["REGIÃO"] = base["_ATIVO_BASE"].map(DataLoader._classificar_regiao)

        elif "BASE" in base.columns:
            base["REGIÃO"] = base["BASE"].map(DataLoader._classificar_regiao)

        else:
            base["REGIÃO"] = "OUTRAS"

        # INTEGRAÇÃO COM CRITÉRIOS: Gera TIPO_SERVICO usando módulo criterios.py
        base["TIPO_SERVICO"] = Utils.gerar_tipo_servico_com_criterios(
            base,
            usar_criterios=True,
        )

        base["Status Contrato"] = base["STATUS CONTRATO"]

        colunas_auxiliares = [
            coluna
            for coluna in base.columns
            if coluna.startswith("_LOGIN_") or coluna.startswith("_ATIVO_")
        ]

        base = base.drop(
            columns=colunas_auxiliares,
            errors="ignore",
        )

        base = base.reset_index(drop=True)

        base.attrs["arquivo_origem"] = filename
        base.attrs["total_importado"] = total_importado
        base.attrs["removidos_suspensos_cancelados"] = removidos_status
        base.attrs["removidos_contrato"] = removidos_contrato
        base.attrs["tipo_servico_coluna"] = coluna_tipo_origem or ""
        base.attrs["valores_tipo_servico_originais"] = valores_tipo_origem
        base.attrs["total_processado"] = len(base)

        return base

    @staticmethod
    def callback_robo_etl(
        df_raw: pd.DataFrame,
        df_gs: pd.DataFrame,
    ) -> pd.DataFrame:
        caminho = st.session_state.get(
            "robo_candidato_path",
            "",
        )

        nome = Path(str(caminho)).name if caminho else "Arquivo_Robo"

        df_processado = DataLoader.preparar_base(
            df_raw,
            df_gs,
            filename=nome,
        )

        st.session_state["_robo_df_pronto"] = df_processado
        st.session_state["_robo_nome_arquivo"] = nome
        st.session_state["_robo_dados_disponiveis"] = not df_processado.empty
        st.session_state["df_memoria_raw"] = df_raw
        st.session_state["df_memoria"] = df_processado
        st.session_state["origem_dados"] = f"Robô ({nome})"
        st.session_state["robo_hora_sucesso"] = datetime.now()

        return df_processado


# ─────────────────────────────────────────────────────────────────────
# MOTOR ANALÍTICO
# ─────────────────────────────────────────────────────────────────────
class Motor:
    @staticmethod
    def matriz_resumo_logic(df: pd.DataFrame) -> pd.DataFrame:
        colunas_obrigatorias = {
            "MONITOR",
            "TIPO_SERVICO",
            "Status Contrato",
            "TOTAL DE TAREFAS",
        }

        if df is None or df.empty:
            return pd.DataFrame()

        if not colunas_obrigatorias.issubset(df.columns):
            return pd.DataFrame()

        trabalho = df.copy()

        trabalho["MONITOR"] = (
            trabalho["MONITOR"]
            .fillna("SEM MONITOR")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # GARANTIA DE INTEGRIDADE: Normaliza TIPO_SERVICO para valores válidos
        tipos_validos = set(Config.ORDEM_TIPOS)
        trabalho["TIPO_SERVICO"] = trabalho["TIPO_SERVICO"].apply(
            lambda x: x if x in tipos_validos else "Outros"
        )

        trabalho["Status Contrato"] = (
            trabalho["Status Contrato"].fillna("").astype(str).str.strip()
        )

        trabalho["TOTAL DE TAREFAS"] = (
            pd.to_numeric(
                trabalho["TOTAL DE TAREFAS"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        validos = trabalho.loc[
            trabalho["Status Contrato"].isin(Config.STATUS_ORDEM)
        ].copy()

        if validos.empty:
            return pd.DataFrame()

        validos["_EXEC"] = np.where(
            validos["Status Contrato"].eq("Executada"),
            validos["TOTAL DE TAREFAS"],
            0,
        )

        validos["_NEX"] = np.where(
            validos["Status Contrato"].eq("Não Executada"),
            validos["TOTAL DE TAREFAS"],
            0,
        )

        agrupado = (
            validos.groupby(
                ["MONITOR", "TIPO_SERVICO"],
                dropna=False,
            )
            .agg(
                executados=("_EXEC", "sum"),
                nao_executados=("_NEX", "sum"),
            )
            .reset_index()
        )

        agrupado["DENOMINADOR"] = agrupado["executados"] + agrupado["nao_executados"]

        agrupado["PERCENTUAL"] = _divisao_segura(
            agrupado["nao_executados"],
            agrupado["DENOMINADOR"],
            padrao=np.nan,
        )

        monitores = pd.Index(
            sorted(validos["MONITOR"].dropna().unique()),
            name="MONITOR",
        )

        pivot = agrupado.pivot(
            index="MONITOR",
            columns="TIPO_SERVICO",
            values="PERCENTUAL",
        ).reindex(monitores)

        for tipo in Config.ORDEM_TIPOS:
            if tipo not in pivot.columns:
                pivot[tipo] = np.nan

        pivot = pivot.loc[:, list(Config.ORDEM_TIPOS)]

        totais_monitor = (
            validos.groupby("MONITOR")[["_EXEC", "_NEX"]]
            .sum()
            .reindex(monitores)
            .fillna(0)
        )

        denominador_geral = totais_monitor["_EXEC"] + totais_monitor["_NEX"]

        pivot["Quebra Geral"] = _divisao_segura(
            totais_monitor["_NEX"],
            denominador_geral,
            padrao=np.nan,
        )

        pivot["Total Tasks"] = (
            validos.groupby("MONITOR")["TOTAL DE TAREFAS"]
            .sum()
            .reindex(monitores)
            .fillna(0)
            .round()
            .astype(int)
        )

        pivot = pivot.reset_index().rename(columns={"MONITOR": "Monitor"})

        total_row: dict[str, Any] = {
            "Monitor": "TOTAL GERAL",
        }

        executados_geral = float(validos["_EXEC"].sum())
        nao_executados_geral = float(validos["_NEX"].sum())

        denominador_total = executados_geral + nao_executados_geral

        total_row["Quebra Geral"] = (
            nao_executados_geral / denominador_total
            if denominador_total > 0
            else np.nan
        )

        total_row["Total Tasks"] = int(validos["TOTAL DE TAREFAS"].sum())

        for tipo in Config.ORDEM_TIPOS:
            recorte = validos.loc[validos["TIPO_SERVICO"].eq(tipo)]

            executados_tipo = float(recorte["_EXEC"].sum())
            nao_executados_tipo = float(recorte["_NEX"].sum())

            denominador_tipo = executados_tipo + nao_executados_tipo

            total_row[tipo] = (
                nao_executados_tipo / denominador_tipo
                if denominador_tipo > 0
                else np.nan
            )

        return pd.concat(
            [pivot, pd.DataFrame([total_row], columns=pivot.columns)],
            ignore_index=True,
        )

    @staticmethod
    def matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
    def matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        return _cache_matriz_resumo(df.copy())

    @staticmethod
    def tabela_cenarios(
        df: pd.DataFrame,
        grupo: str,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 5,
    ) -> pd.DataFrame:
        colunas_obrigatorias = {
            grupo,
            "Status Contrato",
            "TOTAL DE TAREFAS",
        }

        if df.empty or not colunas_obrigatorias.issubset(df.columns):
            return pd.DataFrame()

        p_ot = float(np.clip(p_ot, 0, 1))
        p_base = float(np.clip(p_base, 0, 1))
        p_pess = float(np.clip(p_pess, 0, 1))

        trabalho = df.copy()

        trabalho["TOTAL DE TAREFAS"] = (
            pd.to_numeric(
                trabalho["TOTAL DE TAREFAS"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        pivot = pd.pivot_table(
            trabalho,
            index=grupo,
            columns=COL_STATUS,
            values=COL_TOTAL,
            aggfunc="sum",
            fill_value=0,
        )

        for status in Config.STATUS_ORDEM:
            if status not in pivot.columns:
                pivot[status] = 0.0

        resultado = pivot.reset_index()

        resultado["Considerado"] = resultado["Executada"] + resultado["Não Executada"]

        resultado["Alocado"] = resultado["Considerado"] + resultado["Pendente"]

        resultado["Quebra Atual"] = _divisao_segura(
            resultado["Não Executada"],
            resultado["Considerado"],
        )

        cenarios = (
            ("Otimista", p_ot),
            ("Base", p_base),
            ("Pessimista", p_pess),
        )

        for nome, probabilidade_quebra in cenarios:
            resultado[f"Fechamento {nome}"] = _divisao_segura(
                resultado["Não Executada"]
                + resultado["Pendente"] * probabilidade_quebra,
                resultado["Alocado"],
            )

        return (
            resultado.loc[resultado["Alocado"] >= min_aloc]
            .sort_values(
                "Fechamento Base",
                ascending=False,
            )
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
        if segmento and segmento != "TODOS" and "TIPO_SERVICO" in df.columns:
            recorte = df.loc[df["TIPO_SERVICO"].eq(segmento)].copy()
        else:
            recorte = df.copy()

        if recorte.empty:
            return pd.DataFrame()

        resultado = Motor.tabela_cenarios(
            recorte,
            "TÉCNICO",
            p_ot,
            p_base,
            p_pess,
            min_aloc,
        )

        return resultado.head(top_n)

    @staticmethod
    def causa_raiz(
        df: pd.DataFrame,
        coluna_baixa: str,
        top_n: int = 8,
    ) -> pd.DataFrame:
        colunas_obrigatorias = {
            "Status Contrato",
            "TOTAL DE TAREFAS",
            coluna_baixa,
        }

        if not colunas_obrigatorias.issubset(df.columns):
            return pd.DataFrame()

        recorte = df.loc[df["Status Contrato"].eq("Não Executada")].copy()

        if recorte.empty:
            return pd.DataFrame()

        recorte["_BAIXA_NORM"] = (
            recorte[coluna_baixa]
            .fillna("SEM REGISTRO")
            .astype(str)
            .map(Utils.normalizar_texto)
            .replace("", "SEM REGISTRO")
        )

        recorte["TOTAL DE TAREFAS"] = (
            pd.to_numeric(
                recorte["TOTAL DE TAREFAS"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        total_geral = float(recorte["TOTAL DE TAREFAS"].sum())

        resultado = (
            recorte.groupby("_BAIXA_NORM")["TOTAL DE TAREFAS"]
            .sum()
            .nlargest(top_n)
            .reset_index()
        )

        resultado.columns = [
            "Motivo de Baixa",
            "Volume",
        ]

        resultado["% do Total"] = _divisao_segura(
            resultado["Volume"],
            pd.Series(
                total_geral,
                index=resultado.index,
            ),
        )

        resultado["Acumulado"] = resultado["% do Total"].cumsum()

        return resultado

    @staticmethod
    def backoffice_fila(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or COL_STATUS not in df.columns:
            return pd.DataFrame()

        trabalho = df.copy()

        if "MONITOR" not in trabalho.columns:
            trabalho["MONITOR"] = "SEM MONITOR"

        if "TÉCNICO" not in trabalho.columns:
            trabalho["TÉCNICO"] = "NÃO MAPEADO"

        if "TIPO_SERVICO" not in trabalho.columns:
            trabalho["TIPO_SERVICO"] = "Outros"

        if "TOTAL DE TAREFAS" not in trabalho.columns:
            trabalho["TOTAL DE TAREFAS"] = 1

        trabalho["TOTAL DE TAREFAS"] = (
            pd.to_numeric(
                trabalho["TOTAL DE TAREFAS"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        fila = trabalho.loc[
            trabalho["Status Contrato"].isin(
                [
                    "Não Executada",
                    "Pendente",
                ]
            )
        ].copy()

        if fila.empty:
            return pd.DataFrame()

        agrupamento = (
            fila.groupby(
                [
                    "MONITOR",
                    "TÉCNICO",
                    "TIPO_SERVICO",
                    "Status Contrato",
                ],
                dropna=False,
            )["TOTAL DE TAREFAS"]
            .sum()
            .reset_index()
        )

        pivot = pd.pivot_table(
            agrupamento,
            index=[
                "MONITOR",
                "TÉCNICO",
                "TIPO_SERVICO",
            ],
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()

        for coluna in ("Não Executada", "Pendente"):
            if coluna not in pivot.columns:
                pivot[coluna] = 0

        pivot["Total Fila"] = pivot["Não Executada"] + pivot["Pendente"]

        pivot["Prioridade"] = pivot["Não Executada"] * 2 + pivot["Pendente"]

        pivot["Classificação"] = np.select(
            [
                pivot["Prioridade"].ge(20).to_numpy(dtype=bool),
                pivot["Prioridade"].ge(10).to_numpy(dtype=bool),
                pivot["Prioridade"].ge(5).to_numpy(dtype=bool),
            ],
            [
                "🔴 CRÍTICO",
                "🟠 ALTA",
                "🟡 MÉDIA",
            ],
            default="⚪ BAIXA",
        )

        pivot = pivot.rename(
            columns={
                "MONITOR": "Monitor",
                "TÉCNICO": "Técnico",
                "TIPO_SERVICO": "Segmento",
            }
        )

        colunas_finais = [
            "Classificação",
            "Monitor",
            "Técnico",
            "Segmento",
            "Não Executada",
            "Pendente",
            "Total Fila",
            "Prioridade",
        ]

        return (
            pivot.sort_values(
                "Prioridade",
                ascending=False,
            )
            .reset_index(drop=True)
            .loc[:, colunas_finais]
        )

    @staticmethod
    def projetar(
        df: pd.DataFrame,
        probabilidade: float = 0.30,
        grupo: str = "MONITOR",
        incluir_meta: bool = True,
        meta_sla: float = Config.SLA_QUEBRA_MAXIMA,
    ) -> pd.DataFrame:
        colunas_obrigatorias = {
            grupo,
            "Status Contrato",
            "TOTAL DE TAREFAS",
        }

        if df.empty or not colunas_obrigatorias.issubset(df.columns):
            return pd.DataFrame()

        probabilidade = float(np.clip(probabilidade, 0, 1))

        meta_sla = float(np.clip(meta_sla, 0, 1))

        trabalho = df.copy()

        trabalho["TOTAL DE TAREFAS"] = (
            pd.to_numeric(
                trabalho["TOTAL DE TAREFAS"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
        )

        pivot = pd.pivot_table(
            trabalho,
            index=grupo,
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        )

        for status in Config.STATUS_ORDEM:
            if status not in pivot.columns:
                pivot[status] = 0.0

        resultado = pivot.reset_index()

        resultado["Considerado"] = resultado["Executada"] + resultado["Não Executada"]

        resultado["Alocado"] = resultado["Considerado"] + resultado["Pendente"]

        resultado["Quebra Atual"] = _divisao_segura(
            resultado["Não Executada"],
            resultado["Considerado"],
        )

        resultado["Projeção Fechamento"] = _divisao_segura(
            resultado["Não Executada"] + resultado["Pendente"] * (1 - probabilidade),
            resultado["Alocado"],
        )

        resultado["Executadas Projetadas"] = (
            resultado["Executada"] + resultado["Pendente"] * probabilidade
        )

        numerador = resultado["Alocado"] * (1 - meta_sla) - resultado["Executada"]

        conversao = _divisao_segura(
            numerador,
            resultado["Pendente"],
        ).clip(0, 1)

        resultado["Conversão Necessária"] = np.where(
            resultado["Pendente"].gt(0),
            conversao,
            0.0,
        )

        if incluir_meta:
            projecao = resultado["Projeção Fechamento"]

            resultado["Status Meta"] = np.select(
                [
                    projecao.le(meta_sla).to_numpy(dtype=bool),
                    projecao.le(meta_sla * 1.25).to_numpy(dtype=bool),
                    projecao.le(meta_sla * 1.50).to_numpy(dtype=bool),
                ],
                [
                    "✅ Dentro da Meta",
                    "️ Atenção",
                    "🔴 Crítico",
                ],
                default="🚨 Muito Crítico",
            )

        colunas_inteiras = (
            "Executada",
            "Não Executada",
            "Pendente",
            "Considerado",
            "Alocado",
        )

        for coluna in colunas_inteiras:
            resultado[coluna] = resultado[coluna].fillna(0).round().astype(int)

        return resultado.sort_values(
            "Projeção Fechamento",
            ascending=False,
        ).reset_index(drop=True)


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def _cache_matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
    return Motor.matriz_resumo_logic(df)


# ─────────────────────────────────────────────────────────────────────
# HTML MATRIZ EXECUTIVA
# ─────────────────────────────────────────────────────────────────────
def render_matriz_executiva_html(
    df: pd.DataFrame,
    meta_geral: float = Config.SLA_QUEBRA_MAXIMA,
) -> None:
    if df.empty:
        st.info("Sem dados na Matriz Executiva.")
        return

    metas_coluna: dict[str, float] = {
        "NOVOS DOMICÍLIOS": meta_geral,
        "NOVOS DOMICILIOS": meta_geral,
        "PME": meta_geral,
        "MIGRAÇÃO": Config.SLA_MIGRACAO_MAXIMA,
        "MIGRACAO": Config.SLA_MIGRACAO_MAXIMA,
        "OUTROS": meta_geral,
        "QUEBRA GERAL": meta_geral,
    }

    html = """
    <div class="matriz-table-container">
        <table class="matriz-table">
            <thead>
                <tr>
    """

    for coluna in df.columns:
        html += f"<th>{_html(coluna)}</th>"

    html += """
                </tr>
            </thead>
            <tbody>
    """

    for _, linha in df.iterrows():
        primeiro_valor = linha.iloc[0]
        is_total = str(primeiro_valor).strip().upper() == "TOTAL GERAL"

        classe_linha = "class='total-row'" if is_total else ""
        html += f"<tr {classe_linha}>"

        for posicao, coluna in enumerate(df.columns):
            valor = linha.iloc[posicao]
            coluna_upper = str(coluna).strip().upper()

            if coluna_upper in metas_coluna:
                try:
                    numero = float(valor)

                    if not np.isfinite(numero):
                        html += (
                            "<td><span style='color:#94A3B8;"
                            "font-weight:700;'>—</span></td>"
                        )
                        continue

                    classe_badge = (
                        "badge-meta-ok"
                        if numero <= metas_coluna[coluna_upper]
                        else "badge-meta-nok"
                    )

                    html += (
                        f"<td><span class='{classe_badge}'>"
                        f"{_fmt_pct_br(numero)}"
                        f"</span></td>"
                    )

                except (TypeError, ValueError):
                    html += f"<td>{_html(valor)}</td>"

            elif coluna_upper in {"TOTAL TASKS", "TOTAL_TASKS"}:
                html += f"<td><strong>{_fmt_int_br(valor)}</strong></td>"

            else:
                if _is_missing_scalar(valor):
                    html += "<td><span style='color:#94A3B8;'>—</span></td>"
                else:
                    html += f"<td>{_html(valor)}</td>"

        html += "</tr>"

    html += """
            </tbody>
        </table>
    </div>
    """

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# COMPONENTES DE TELA
# ─────────────────────────────────────────────────────────────────────
def render_bloco_importacao_robo(
    dados_prontos: bool = False,
) -> bool:
    st.markdown(
        """
        <div style="margin-top:6px;margin-bottom:4px;">
            <span class="import-header-title">Importação de Dados</span>
            <span class="import-header-badge">EXCEL, CSV OU AUTO</span>
        </div>

        <div class="import-header-sub">
            Envie a base consolidada de O.S. do dia ou aguarde o robô detectar automaticamente.
        </div>

        <div class="import-header-line"></div>
        """,
        """,
        unsafe_allow_html=True,
    )

    if not dados_prontos:
        return False

    st.markdown(
        """
        <div class="import-alert-green">
            <span style="font-size:16px;">✅</span>
            <span>Dados carregados e processados. O relatório está pronto.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return st.button(
        "🔄 Atualizar Relatório",
        type="primary",
        use_container_width=True,
        key="btn_atualizar_relatorio",
    )


def html_resultado_base(
    regioes: list[str],
    total: int,
    origem: str = "",
) -> str:
    badges: list[str] = []

    for regiao in sorted(set(regioes)):
        regiao_norm = str(regiao).upper().strip()
        cores = CORES_REGIAO.get(
            regiao_norm,
            CORES_REGIAO["OUTRAS"],
        )

        badges.append(f"""
            <span class="badge-regiao"
                style="
                    background:{cores["bg"]};
                    color:{cores["text"]};
                    border-color:{cores["border"]};
                ">
                {_html(regiao_norm)}
            </span>
            """)

    total_fmt = _fmt_int_br(total)

    tag_origem = (
        f"""
        <span style="
            color:#6EE7B7;
            font-size:0.78rem;
            font-weight:600;
            margin-left:8px;
        ">
            • {_html(origem)}
        </span>
        """
        if origem
        else ""
    )

    return f"""
    <div class="base-info">
        <span style="
            color:#94A3B8;
            font-size:0.8rem;
            font-weight:700;
            text-transform:uppercase;
            letter-spacing:0.08em;
        ">
            📋 Base Ativa:
        </span>

        {''.join(badges)}

        {tag_origem}

        <span style="
            color:#FFFFFF;
            font-size:0.78rem;
            margin-left:auto;
            font-weight:700;
        ">
            {total_fmt} registros
        </span>
    </div>
    """


def render_hero_topo_fixo(
    titulo: str,
    subtitulo: str,
    regioes: list[str],
    total: int,
    badge: str = "",
    origem: str = "",
) -> None:
    badge_html = ""

    if badge:
        badge_html = f"""
        <span style="
            display:inline-block;
            background:rgba(255,255,255,0.20);
            padding:5px 16px;
            border-radius:20px;
            font-size:12px;
            font-weight:700;
            margin-top:10px;
            letter-spacing:0.6px;
            text-transform:uppercase;
            color:white;
            border:1px solid rgba(255,255,255,0.30);
        ">
            {_html(badge)}
        </span>
        """

    info_base = html_resultado_base(regioes, total, origem) if total > 0 else ""

    st.markdown(
        f"""
        <div class="hero-container">
            <div class="hero-card">
                <h1 class="hero-title">{_html(titulo)}</h1>
                <p class="hero-sub">{_html(subtitulo)}</p>
                {badge_html}
            </div>
            {info_base}
        </div>
        """,
        unsafe_allow_html=True,
    )


_COLUNAS_PERCENTUAIS = (
    "QUEBRA",
    "FECHAMENTO",
    "%",
    "PROJEÇÃO",
    "CONVERSÃO",
    "DOMICÍLIOS",
    "DOMICILIOS",
    "PME",
    "MIGRAÇÃO",
    "MIGRACAO",
    "OUTROS",
)
_COLUNAS_INTEIRAS = (
    "TOTAL",
    "VOLUME",
    "TAREFAS",
    "PRIORIDADE",
    "EXECUTADAS",
    "TASKS",
)


def render_dataframe_profundo(
    df: pd.DataFrame,
    titulo: str,
    icone: str,
    color_col: str | None = None,
    meta: float = Config.SLA_QUEBRA_MAXIMA,
    height: int = 400,
) -> None:
    total_registros = 0 if df is None else len(df)
    st.markdown(
        f"""
        <div style="
            background:#FFFFFF;
            border-radius:0.75rem;
            padding:1rem 1.2rem;
            box-shadow:0 2px 8px rgba(0,0,0,0.05);
            margin-bottom:0.5rem;
        ">
            <div style="
                font-size:1rem;
                font-weight:700;
                color:#0F172A;
                display:flex;
                align-items:center;
                gap:0.5rem;
            ">
                <span>{_html(icone)}</span>
                <span>{_html(titulo)}</span>
                <span style="
                    font-size:0.68rem;
                    background:#E0F2FE;
                    color:#0369A1;
                    padding:0.15rem 0.5rem;
                    border-radius:999px;
                ">
                    {len(df)} registros
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return

    formatos: dict[str, str] = {}

    for coluna in df.columns:
        coluna_upper = str(coluna).upper()

        if any(
            item in coluna_upper
            for item in (
                "QUEBRA",
                "FECHAMENTO",
                "%",
                "PROJEÇÃO",
                "PROJECAO",
                "CONVERSÃO",
                "CONVERSAO",
                "ACUMULADO",
            )
        ):
            formatos[str(coluna)] = "{:.2%}"

        elif any(
            item in coluna_upper
            for item in (
                "TOTAL",
                "VOLUME",
                "TAREFAS",
                "PRIORIDADE",
                "EXECUTADA",
                "TASKS",
                "ALOCADO",
                "CONSIDERADO",
            )
        ):
            formatos[str(coluna)] = "{:,.0f}"

    regras_cor: dict[str, Any] | None = None

    if color_col is not None and color_col in df.columns:
        regras_cor = {
            "coluna": color_col,
            "meta": meta,
            "acima_meta": {
                "bg": "#FEE2E2",
                "text": "#991B1B",
                "bold": True,
            },
            "abaixo_meta": {
                "bg": "#DCFCE7",
                "text": "#166534",
                "bold": True,
            },
        }

    colunas_numericas = df.select_dtypes(include=np.number).columns.astype(str).tolist()

    render_table_html(
        df,
        fmt=formatos,
        color_rules=regras_cor,
        colunas_num=colunas_numericas,
        height=height,
    )


# ─────────────────────────────────────────────────────────────────────
# VIEWS
# ────────────────────────────────────────────────────────────────────
def view_resumo_executivo(
    df: pd.DataFrame,
    meta_sla: float,
) -> None:
    coluna_tipo = str(
        df.attrs.get(
            "tipo_servico_coluna",
            "",
        )
    )

    tipos_processados: set[str] = set()

    if "TIPO_SERVICO" in df.columns:
        tipos_processados = set(
            df["TIPO_SERVICO"].dropna().astype(str).unique().tolist()
        )

    if not coluna_tipo:
        st.warning(
            "️ A base não possui uma coluna identificável de tipo de serviço. "
            "Todos os registros foram classificados como 'Outros'."
        )
        return

    if tipos_processados and tipos_processados <= {"Outros"}:
        st.warning(
            "⚠️ A coluna de segmento foi encontrada, mas nenhum valor foi "
            "reconhecido como Novos Domicílios, PME ou Migração."
        )

        if isinstance(valores_originais, dict) and valores_originais:
            st.caption(
                "Valores originais encontrados: "
                + ", ".join(list(valores_originais.keys())[:10])
            )


    matriz = Motor.matriz_resumo(df)

    if matriz.empty:
        st.warning("⚠️ Dados insuficientes para montar a Matriz Executiva.")
        return

    if "Monitor" in matriz.columns:
        mask_total = (
            matriz["Monitor"].astype(str).str.strip().str.upper().eq("TOTAL GERAL")
        )

        matriz = pd.concat(
            [
                matriz.loc[~mask_total],
                matriz.loc[mask_total],
            ],
            ignore_index=True,
        )

    render_matriz_executiva_html(
        matriz,
        meta_geral=meta_sla,
    )

    st.download_button(
        "📥 Baixar Matriz (Excel)",
        data=Utils.gerar_excel(
            matriz,
            "Matriz_Resumo",
        ),
        file_name="Matriz_Resumo_Quebra.xlsx",
        mime=("application/vnd.openxmlformats-officedocument." "spreadsheetml.sheet"),
        use_container_width=True,
    )



def view_analise_detalhada(
    df: pd.DataFrame,
    p_ot: float,
    p_base: float,
    p_pess: float,
    min_aloc: float,
    meta_sla: float,
) -> None:
    # PAINEL DE CRITÉRIOS (NOVO)
    if CRITERIOS_DISPONIVEL:
        with st.expander("📊 Painel de Critérios de Classificação", expanded=False):
            render_painel_criterios(df)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📉 Projeções",
            "🎯 Projeção Customizada",
            "🏆 Rankings",
            "🔍 Causas Raiz",
            "📋 Backoffice",
        ]
    )

    with tab1:
        render_section_header(
            "📈",
            "Cenários de Projeção de Fechamento",
        )

        monitores = Motor.tabela_cenarios(
            df,
            "MONITOR",
            p_ot,
            p_base,
            p_pess,
            min_aloc,
        )

        render_dataframe_profundo(
            monitores,
            "Projeção por Monitor",
            "👨‍💼",
            color_col="Fechamento Base",
            meta=meta_sla,
        )

    with tab2:
        render_section_header(
            "",
            "Projeção Customizada",
        )

        col1, col2 = st.columns(2)

        with col1:
            prob_custom = (
                st.slider(
                    "Probabilidade de Conversão (%)",
                    0,
                    100,
                    30,
                    step=5,
                )
                / 100
            )

        with col2:
            grupo_proj = st.selectbox(
                "Agrupar por",
                [
                    "MONITOR",
                    "TÉCNICO",
                    "REGIÃO",
                ],
            )

        projecao = Motor.projetar(
            df,
            probabilidade=prob_custom,
            grupo=grupo_proj,
            meta_sla=meta_sla,
        )

        render_dataframe_profundo(
            projecao,
            f"Projeção por {grupo_proj}",
            "",
            color_col="Projeção Fechamento",
            meta=meta_sla,
        )

        if not projecao.empty:
            k1, k2, k3, k4 = st.columns(4)

            dentro_meta = int(projecao["Projeção Fechamento"].le(meta_sla).sum())

            atencao = int(
                (
                    projecao["Projeção Fechamento"].gt(meta_sla)
                    & projecao["Projeção Fechamento"].le(meta_sla * 1.25)
                ).sum()
            )

            critico = int(projecao["Projeção Fechamento"].gt(meta_sla * 1.25).sum())

            conversao_media = float(projecao["Conversão Necessária"].mean())

            render_kpi_sm(
                k1,
                "Dentro da Meta",
                str(dentro_meta),
                f"{dentro_meta / len(projecao):.0%}",
                "verde",
            )

            render_kpi_sm(
                k2,
                "Atenção",
                str(atencao),
                f"{atencao / len(projecao):.0%}",
                "amarelo",
            )

            render_kpi_sm(
                k3,
                "Crítico",
                str(critico),
                f"{critico / len(projecao):.0%}",
                "vermelho",
            )

            render_kpi_sm(
                k4,
                "Conversão Média",
                f"{conversao_media:.1%}",
                "Para atingir meta",
                "azul",
            )

    with tab3:
        render_section_header(
            "",
            "Técnicos Mais Críticos",
        )

        tecnicos = Motor.tecnicos_criticos(
            df,
            "TODOS",
            p_base,
            min_aloc,
            top_n=20,
            p_ot=p_ot,
            p_pess=p_pess,
        )

        render_dataframe_profundo(
            tecnicos,
            "Top 20 Técnicos com Maior Risco",
            "👤",
            color_col="Fechamento Base",
            meta=meta_sla,
        )

    with tab4:
        render_section_header(
            "🔍",
            "Análise de Causa Raiz",
        )

        coluna_baixa = Utils.buscar_coluna(
            df,
            (
                "CÓD DE BAIXA 1",
                "COD DE BAIXA 1",
                "MOTIVO DE BAIXA",
                "COD_BAIXA",
            ),
        )

        if coluna_baixa is None:
            st.warning("⚠️ Coluna de Código/Motivo de Baixa não encontrada.")
        else:
            causas = Motor.causa_raiz(
                df,
                coluna_baixa,
                top_n=10,
            )

            render_dataframe_profundo(
                causas,
                "Pareto de Motivos",
                "",
            )

    with tab5:
        render_section_header(
            "🛠️",
            "Gestão de Fila (Backoffice)",
        )

        fila = Motor.backoffice_fila(df)

        render_dataframe_profundo(
            fila,
            "Fila Priorizada",
            "📋",
        )


def view_auditoria(df: pd.DataFrame) -> None:
    render_section_header(
        "🔎",
        "Auditoria de Processamento",
    )

    total_importado = int(
        df.attrs.get(
            "total_importado",
            len(df),
        )
    )

    removidos_status = int(
        df.attrs.get(
            "removidos_suspensos_cancelados",
            0,
        )
    )

    removidos_contrato = int(
        df.attrs.get(
            "removidos_contrato",
            0,
        )
    )

    k1, k2, k3, k4 = st.columns(4)

    k1.metric("Importados", _fmt_int_br(total_importado))
    k2.metric("Processados", _fmt_int_br(len(df)))
    k3.metric("Removidos por Status", _fmt_int_br(removidos_status))
    k4.metric("Contratos Inválidos", _fmt_int_br(removidos_contrato))

    arquivo_origem = str(
        df.attrs.get(
            "arquivo_origem",
            "Não identificado",
        )
    )

    coluna_tipo = str(
        df.attrs.get(
            "tipo_servico_coluna",
            "Não identificada",
        )
    )

    st.caption(f"Arquivo de origem: {arquivo_origem}")
    st.caption(f"Coluna de tipo de serviço: {coluna_tipo}")

    # DIAGNÓSTICO DE CRITÉRIOS (NOVO)
    if CRITERIOS_DISPONIVEL:
        with st.expander("🔍 Diagnóstico de Critérios", expanded=False):
            col_tipo = detectar_col_tipo_os_1(df)
            col_hab = detectar_col_habilidade(df)
            col_gpon = detectar_col_flag_gpon(df)

            c1, c2, c3 = st.columns(3)
            c1.metric(
                "TIPO O.S 1",
                "✅ Encontrada" if col_tipo else "❌ Não encontrada",
                col_tipo or "—",
            )
            c2.metric(
                "HABILIDADE",
                "✅ Encontrada" if col_hab else "❌ Não encontrada",
                col_hab or "—",
            )
            c3.metric(
                "FLAG_GPON",
                "✅ Encontrada" if col_gpon else "❌ Não encontrada",
                col_gpon or "—",
            )

            if "TIPO_SERVICO" in df.columns:
                st.markdown("#### Distribuição por Segmento")
                dist = df["TIPO_SERVICO"].value_counts().reset_index()
                dist.columns = ["Segmento", "Registros"]
                st.dataframe(dist, hide_index=True, use_container_width=True)

    with st.expander(
        "Visualizar amostra da base processada",
        expanded=False,
    ):
        st.dataframe(
            df.head(200),
            use_container_width=True,
            hide_index=True,
        )


# ─────────────────────────────────────────────────────────────────────
# SESSÃO
# ─────────────────────────────────────────────────────────────────────
def _limpar_estado_aplicacao(
    limpar_ativos: bool = True,
) -> None:
    chaves = [
        "df_memoria",
        "df_memoria_raw",
        "arquivo_processado",
        "origem_dados",
        "_robo_df_pronto",
        "_robo_nome_arquivo",
        "_robo_dados_disponiveis",
        "robo_hora_sucesso",
    ]

    if limpar_ativos:
        chaves.extend(
            [
                "df_gs_manual",
                "arquivo_ativos_processado",
            ]
        )

    for chave in chaves:
        st.session_state.pop(chave, None)

    nonce_atual = int(
        st.session_state.get(
            "upload_nonce",
            0,
        )
    )

    st.session_state["upload_nonce"] = nonce_atual + 1


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
def main() -> None:
    _injetar_css_global()

    mensagem_flash = st.session_state.pop(
        "mensagem_flash",
        "",
    )

    if mensagem_flash:
        st.success(str(mensagem_flash))

    render_sidebar_brand(
        titulo="TOTALE",
        subtitulo="Quebra Operacional",
        logo="monitoring",
        ambiente="produção",
        versao="v4.3.0",
        mostrar_data=True,
    )

    if "upload_nonce" not in st.session_state:
        st.session_state["upload_nonce"] = 0

    nonce = int(st.session_state["upload_nonce"])

    with st.sidebar.expander(
        "⚙️ Configurações & Lista de Ativos",
        expanded=False,
    ):
        st.markdown("### Lista de Ativos (Merge)")

        upload_ativos = st.file_uploader(
            "Upload de Contingência de Ativos",
            type=["csv", "xlsx", "xlsm"],
            key=f"uploaded_ativos_manual_{nonce}",
            help=(
                "Utilize esta opção caso o Google Sheets esteja "
                "indisponível ou para atualizar a lista de ativos."
            ),
        )

        if upload_ativos is not None:
            try:
                bytes_ativos = upload_ativos.getvalue()

                id_ativos = _identificador_upload(
                    upload_ativos.name,
                    bytes_ativos,
                )

                if st.session_state.get("arquivo_ativos_processado") != id_ativos:
                    raw_ativos = DataLoader.ler_arquivo(
                        bytes_ativos,
                        upload_ativos.name,
                    )

                    ativos_processados = DataLoader._processar_lista_ativos(raw_ativos)

                    if ativos_processados.empty:
                        raise ValueError(
                            "A base de ativos não possui uma coluna LOGIN válida."
                        )

                    st.session_state["df_gs_manual"] = ativos_processados

                    st.session_state["arquivo_ativos_processado"] = id_ativos

                    raw_memoria = _obter_dataframe_sessao("df_memoria_raw")

                    if raw_memoria is not None:
                        st.session_state["df_memoria"] = DataLoader.preparar_base(
                            raw_memoria,
                            ativos_processados,
                        )

                    st.toast(
                        f"✅ {len(ativos_processados)} ativos carregados.",
                        icon="",
                    )

            except Exception as erro:
                st.error(f"Erro ao processar base de ativos: {erro}")

        if st.button(
            "🔄 Reiniciar Aplicação",
            use_container_width=True,
            type="secondary",
        ):
            _limpar_estado_aplicacao(
                limpar_ativos=True,
            )
            st.cache_data.clear()
            st.rerun()

        if st.button(
            "️ Limpar Cache",
            use_container_width=True,
            type="secondary",
        ):
            _limpar_estado_aplicacao(
                limpar_ativos=True,
            )
            st.cache_data.clear()
            st.rerun()

    if "df_gs_manual" in st.session_state:
        df_ativos_atual = _obter_dataframe_sessao("df_gs_manual") or pd.DataFrame()

        origem_ativos = "Upload Manual"

    else:
        df_ativos_atual = DataLoader.buscar_gsheets()
        origem_ativos = "Google Sheets"

    if not df_ativos_atual.empty:
        st.sidebar.caption(f"👥 Base de Ativos: {len(df_ativos_atual)} registros")
        st.sidebar.caption(f"📍 Origem: {origem_ativos}")
    else:
        st.sidebar.warning("⚠️ Nenhuma base de ativos conectada.")

    if "robo_pasta_alvo" not in st.session_state:
        st.session_state["robo_pasta_alvo"] = str(Path.home() / "Downloads")

    pasta_robo = st.session_state.get(
        "robo_pasta_alvo",
        str(Path.home() / "Downloads"),
    )

    if not isinstance(pasta_robo, str):
        pasta_robo = str(Path.home() / "Downloads")

    st.sidebar.markdown("---")

    if ROBO_DISPONIVEL and _impl_robo is not None:
        try:

            def callback_robo_com_ativos(
                df_raw: pd.DataFrame,
                df_gs_arg: pd.DataFrame | None = None,
                *_args: Any,
                **_kwargs: Any,
            ) -> pd.DataFrame:
                ativos_finais = (
                    df_gs_arg
                    if isinstance(df_gs_arg, pd.DataFrame) and not df_gs_arg.empty
                    else df_ativos_atual
                )

                return DataLoader.callback_robo_etl(
                    df_raw,
                    ativos_finais,
                )

            _impl_robo(
                etl_fn=callback_robo_com_ativos,
                gsheets_fn=lambda: df_ativos_atual,
                pasta_padrao=pasta_robo,
                ciclos_estabilidade=1,
                mostrar_toggle=True,
                mostrar_config=True,
            )

        except Exception as erro:
            st.sidebar.error(f"Erro ao inicializar Robô: {erro}")

    else:
        st.sidebar.info("🤖 Robô offline. Utilize upload manual.")

        pasta_manual = st.sidebar.text_input(
            "Pasta monitorada",
            value=pasta_robo,
            key="robo_pasta_fallback",
        )

        st.session_state["robo_pasta_alvo"] = pasta_manual

    df_atual = _obter_dataframe_sessao("df_memoria")

    dados_prontos = df_atual is not None and not df_atual.empty

    clicou_atualizar = render_bloco_importacao_robo(
        dados_prontos=dados_prontos,
    )

    if clicou_atualizar:
        st.session_state["mensagem_flash"] = "✅ Relatório atualizado com sucesso."
        st.rerun()

    if not dados_prontos:
        upload_os = st.file_uploader(
            "⬇️ Carregar base de O.S. manualmente",
            type=["csv", "xlsx", "xlsm"],
            key=f"upload_os_principal_{nonce}",
        )
    else:
        with st.expander(
            " Substituir base de O.S. manualmente",
            expanded=False,
        ):
            upload_os = st.file_uploader(
                "Upload Manual O.S.",
                type=["csv", "xlsx", "xlsm"],
                key=f"upload_os_substituir_{nonce}",
            )

    if upload_os is not None:
        try:
            bytes_os = upload_os.getvalue()

            id_arquivo = _identificador_upload(
                upload_os.name,
                bytes_os,
            )

            if st.session_state.get("arquivo_processado") != id_arquivo:
                with st.spinner(f"Processando {upload_os.name}..."):
                    raw_os = DataLoader.ler_arquivo(
                        bytes_os,
                        upload_os.name,
                    )

                    if raw_os.empty:
                        raise ValueError("A base de O.S. não possui registros.")

                    base_processada = DataLoader.preparar_base(
                        raw_os,
                        df_ativos_atual,
                        filename=upload_os.name,
                    )

                    if base_processada.empty:
                        raise ValueError(
                            "Nenhuma O.S. válida permaneceu após o tratamento."
                        )

                    st.session_state["df_memoria_raw"] = raw_os
                    st.session_state["df_memoria"] = base_processada
                    st.session_state["arquivo_processado"] = id_arquivo
                    st.session_state["origem_dados"] = f"Upload ({upload_os.name})"

                    st.session_state["_robo_dados_disponiveis"] = True

                    st.session_state["mensagem_flash"] = (
                        "✅ Base processada com sucesso."
                    )

                    st.rerun()

        except Exception as erro:
            st.error(f"❌ Erro no processamento do arquivo: {erro}")

    df = _obter_dataframe_sessao("df_memoria")

    if df is None or df.empty:
        st.info("Carregue uma base de O.S. para iniciar a análise.")
        return

    # DEBUG DE COLUNAS (OPCIONAL - REMOVER EM PRODUÇÃO)
    # with st.sidebar.expander(" Debug Colunas"):
    #     st.write("**Colunas disponíveis:**")
    #     st.write(list(df.columns))
    #     if CRITERIOS_DISPONIVEL:
    #         col_tipo = detectar_col_tipo_os_1(df)
    #         col_hab = detectar_col_habilidade(df)
    #         if col_tipo:
    #             st.write(f"**{col_tipo}** (amostra):")
    #             st.write(df[col_tipo].dropna().head(20).unique().tolist()[:10])
    #         if col_hab:
    #             st.write(f"**{col_hab}** (amostra):")
    #             st.write(df[col_hab].dropna().head(20).unique().tolist()[:10])

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="
            font-size:12px;
            font-weight:700;
            color:#64748B;
            text-transform:uppercase;
        ">
            🎯 Filtros de Projeção
        </div>
        """,
        unsafe_allow_html=True,
    )

    p_ot = (
        st.sidebar.slider(
            "Prob. Otimista de Quebra (%)",
            0,
            100,
            15,
            step=5,
        )
        / 100
    )

    p_base = (
        st.sidebar.slider(
            "Prob. Base de Quebra (%)",
            0,
            100,
            30,
            step=5,
        )
        / 100
    )

    p_pess = (
        st.sidebar.slider(
            "Prob. Pessimista de Quebra (%)",
            0,
            100,
            50,
            step=5,
        )
        / 100
    )

    min_aloc = float(
        st.sidebar.number_input(
            "Mínimo de Alocações",
            min_value=1,
            value=5,
        )
    )

    if not (p_ot <= p_base <= p_pess):
        st.sidebar.warning(
            "Atenção: o cenário Otimista deveria ser menor ou igual "
            "ao Base, que deveria ser menor ou igual ao Pessimista."
        )

    regioes = (
        sorted(df["REGIÃO"].dropna().astype(str).unique().tolist())
        if "REGIÃO" in df.columns
        else ["TODAS"]
    )

    origem_base = str(
        st.session_state.get(
            "origem_dados",
            "Base Carregada",
        )
    )

    render_hero_topo_fixo(
        "Super Relatório Corporativo",
        "Análise unificada de desempenho operacional",
        regioes if regioes else ["TODAS"],
        len(df),
        badge="TOTALE OPERACIONAL",
        origem=st.session_state.get("origem_dados", "Base Carregada"),
    )

    if "TÉCNICO" in df.columns:
        nao_mapeados = int(df["TÉCNICO"].eq("NÃO MAPEADO").sum())
    else:
        nao_mapeados = len(df)

    total_os = len(df)
    pct_nao_mapeado = nao_mapeados / total_os if total_os > 0 else 0.0

    if nao_mapeados > 0:
        st.warning(
            f"⚠️ **Aviso de Integração:** {nao_mapeados} O.S. "
            f"({pct_nao_mapeado:.1%} do volume ativo) não possuem "
            "correspondência válida na Lista de Ativos."
        )
    else:
        st.success("🎉 Todos os logins estão mapeados na Lista de Ativos.")

    aba = st.radio(
        "Navegação Principal",
        [
            "Resumo Executivo",
            "Análise Detalhada",
            "Auditoria",
        ],
        horizontal=True,
    )


    if aba == "Resumo Executivo":
        view_resumo_executivo(
            df,
            Config.SLA_QUEBRA_MAXIMA,
        )

    elif aba == "Análise Detalhada":
        view_analise_detalhada(
            df,
            p_ot,
            p_base,
            p_pess,
            min_aloc,
            Config.SLA_QUEBRA_MAXIMA,
        )

    else:
        view_auditoria(df)

    st.divider()


if __name__ == "__main__":
    main()