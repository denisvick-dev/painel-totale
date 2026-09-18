"""
quebra.py
=========
Super Relatório Corporativo Unificado | Quebra Operacional TOTALE
ETL robusto + cache inteligente + matriz executiva com metas.

Version: 4.3.0
Author: TOTALE Tecnologia
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections.abc import Callable, Iterable
from datetime import datetime
from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, ClassVar, Literal, cast

import numpy as np
import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

__version__ = "4.3.0"

# ── Path bootstrap ──────────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_ROOT = _DIR.parent
for _p in (_DIR, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ── Definição Global de Fontes ──────────────────────────────────────
class Fontes:
    TITULO: str = "'Manrope', sans-serif"
    TEXTO: str = "'Inter', sans-serif"


TemaKPI = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo", "amarelo", "escuro"
]
TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]


# ── Componentes visuais globais ─────────────────────────────────────
try:
    from components.componentes import render_insight as _render_insight_global
    from components.componentes import render_kpi as _render_kpi_global
    from components.componentes import render_kpi_sm as _render_kpi_sm_global
    from components.componentes import (
        render_section_header,
        render_sidebar_brand,
        render_table_html,
    )

    COMPONENTES_DISPONIVEIS = True
except ImportError:
    COMPONENTES_DISPONIVEIS = False

    def render_section_header(
        titulo: str = "", icone: str = "", **_kwargs: Any
    ) -> None:
        st.subheader(f"{icone} {titulo}".strip())

    def render_sidebar_brand(**_kwargs: Any) -> None:
        return None

    def render_table_html(df: pd.DataFrame, **_kwargs: Any) -> None:
        st.dataframe(df, use_container_width=True)

    def _render_insight_global(texto: str, tipo: str = "info") -> None:
        if tipo in ("critico", "alerta"):
            st.warning(texto)
        elif tipo == "ok":
            st.success(texto)
        else:
            st.info(texto)

    def _render_kpi_global(
        col: Any, label: str, value: str, sub: str = "", tema: str = "azul"
    ) -> None:
        col.metric(label, value, sub)

    def _render_kpi_sm_global(
        col: Any, label: str, value: str, sub: str = "", tema: str = "azul"
    ) -> None:
        col.metric(label, value, sub)


# ── Importação do Robô (Lazy Load) ─────────────────────────────────
def _tentar_import_robo() -> tuple[Callable[..., Any] | None, str]:
    for extra in (_DIR, _ROOT):
        s = str(extra)
        if s not in sys.path:
            sys.path.insert(0, s)
    try:
        from robo.robo_local import renderizar_robo_local as fn
    except Exception as e:  # noqa: BLE001 - import opcional
        return None, f"{type(e).__name__}: {e}"
    return fn, "OK"


_impl_robo, _ROBO_IMPORT_ERRO = _tentar_import_robo()
ROBO_DISPONIVEL: bool = _impl_robo is not None


def renderizar_robo_local(*args: Any, **kwargs: Any) -> None:
    if _impl_robo is None:
        st.sidebar.warning("🤖 Robô offline (Modo Manual)")
        return
    try:
        _impl_robo(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 - robô não pode derrubar o app
        st.sidebar.error(f"Erro no Robô: {e}")


# ══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES E CONSTANTES
# ══════════════════════════════════════════════════════════════════════
class Config:
    """Fonte única de verdade para parâmetros do relatório."""

    SLA_QUEBRA_MAXIMA: float = 0.20
    SLA_MIGRACAO_MAXIMA: float = 0.25

    SHEET_ID_ATIVOS: str = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    WORKSHEET_ATIVOS: str = "lista_ativos"
    URL_LISTA_ATIVOS: str = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID_ATIVOS}/edit"
    )

    STATUS_ORDEM: ClassVar[list[str]] = ["Executada", "Não Executada", "Pendente"]
    CORES_STATUS: ClassVar[dict[str, str]] = {
        "Executada": "#10B981",
        "Não Executada": "#EF4444",
        "Pendente": "#94A3B8",
    }

    ORDEM_TIPOS: ClassVar[list[str]] = ["Novos Domicílios", "PME", "Migração", "Outros"]
    CORES_TIPO: ClassVar[dict[str, str]] = {
        "Novos Domicílios": "#1E40AF",
        "PME": "#7C3AED",
        "Migração": "#0369A1",
        "Quebra Geral": "#78350F",
        "Outros": "#64748B",
    }

    COLUNAS_TIPO_SERVICO: ClassVar[list[str]] = [
        "TIPO_SERVICO",
        "TIPO SERVICO",
        "TIPO DE SERVICO",
        "SEGMENTO",
    ]
    COLUNAS_CONTRATO: ClassVar[list[str]] = ["CONTRATO", "NR CONTRATO", "CONTRATO_ID"]
    COLUNAS_TOTAL_TAREFAS: ClassVar[list[str]] = [
        "TOTAL DE TAREFAS",
        "QTD TAREFAS",
        "QUANTIDADE",
        "VOLUME",
    ]
    COLUNAS_LOGIN: ClassVar[list[str]] = [
        "LOGIN DO TÉCNICO",
        "LOGIN DO TECNICO",
        "LOGIN",
        "USUÁRIO",
        "USUARIO",
        "MATRÍCULA",
        "MATRICULA",
    ]
    COLUNAS_CIDADE: ClassVar[list[str]] = [
        "CIDADE",
        "LOCALIDADE",
        "MUNICÍPIO",
        "MUNICIPIO",
    ]
    COLUNAS_COD_BAIXA: ClassVar[list[str]] = [
        "CÓD DE BAIXA 1",
        "COD DE BAIXA 1",
        "MOTIVO DE BAIXA",
        "COD_BAIXA",
    ]

    REGIOES: ClassVar[dict[str, set[str]]] = {
        "LESTE": {"SAO PAULO"},
        "GRU": {
            "GUARULHOS",
            "ARUJA",
            "MOGI DAS CRUZES",
            "SUZANO",
            "ITAQUAQUECETUBA",
            "FERRAZ DE VASCONCELOS",
            "POA",
        },
        "ABCDM": {
            "SANTO ANDRE",
            "SAO BERNARDO DO CAMPO",
            "SAO CAETANO DO SUL",
            "DIADEMA",
            "MAUA",
            "RIBEIRAO PIRES",
            "RIO GRANDE DA SERRA",
        },
    }


# Aliases mantidos por compatibilidade com módulos que importam de quebra.py.
SLA_QUEBRA_MAXIMA = Config.SLA_QUEBRA_MAXIMA
SLA_MIGRACAO_MAXIMA = Config.SLA_MIGRACAO_MAXIMA
URL_LISTA_ATIVOS = Config.URL_LISTA_ATIVOS
SHEET_ID_ATIVOS = Config.SHEET_ID_ATIVOS
WORKSHEET_ATIVOS = Config.WORKSHEET_ATIVOS
STATUS_ORDEM = Config.STATUS_ORDEM
CORES_STATUS = Config.CORES_STATUS
ORDEM_TIPOS = Config.ORDEM_TIPOS
CORES_TIPO = Config.CORES_TIPO
COLUNAS_TIPO_SERVICO = Config.COLUNAS_TIPO_SERVICO

MAPA_CODIGO_NUMERICO: dict[int, str] = {
    **{
        k: "Não Executada"
        for k in (
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
        k: "Executada"
        for k in (
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

CORES_REGIAO: dict[str, dict[str, str]] = {
    "LESTE": {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU": {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM": {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

# Textos que representam ausência de valor após normalização.
VAZIOS = frozenset({"", "NAN", "NONE", "NULL", "NAT", "NA", "N/A", "-"})

COL_STATUS = "Status Contrato"
COL_TIPO = "TIPO_SERVICO"
COL_TOTAL = "TOTAL DE TAREFAS"


# ══════════════════════════════════════════════════════════════════════
# CSS GLOBAL
# ══════════════════════════════════════════════════════════════════════
_CSS_GLOBAL = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

.import-header-title { font-family: 'Manrope', sans-serif; font-size: 32px; font-weight: 800; color: #1E293B; letter-spacing: -0.5px; margin: 0; display: inline-block; }
.import-header-badge { display: inline-flex; align-items: center; background: #EEF2FF; color: #3B82F6; border: 1.5px solid #93C5FD; font-size: 11px; font-weight: 800; padding: 3px 12px; border-radius: 9999px; letter-spacing: 0.6px; text-transform: uppercase; margin-left: 14px; vertical-align: middle; }
.import-header-sub { font-size: 14px; color: #64748B; margin-top: 6px; margin-bottom: 14px; font-weight: 400; font-family: 'Inter', sans-serif; }
.import-header-line { height: 3px; background: linear-gradient(90deg, #012869 0%, #1E40AF 30%, #F59E0B 65%, #EF4444 100%); border-radius: 2px; margin-bottom: 18px; }
.import-alert-green { background-color: #E8F8F0; border: 1px solid #C2F0D9; border-radius: 8px; padding: 14px 20px; color: #107C41; font-size: 14.5px; font-weight: 700; display: flex; align-items: center; gap: 10px; margin-bottom: 16px; font-family: 'Inter', sans-serif; }

div[data-testid="stButton"] > button[kind="primary"] { background: #FF3838 !important; color: #FFFFFF !important; border: none !important; border-radius: 8px !important; padding: 12px 24px !important; font-size: 14.5px !important; font-weight: 700 !important; box-shadow: 0 4px 14px rgba(255, 56, 56, 0.25) !important; transition: all 0.2s ease-in-out !important; font-family: 'Manrope', sans-serif; }
div[data-testid="stButton"] > button[kind="primary"]:hover { background: #E02828 !important; box-shadow: 0 6px 18px rgba(224, 40, 40, 0.35) !important; transform: translateY(-1px); }

.hero-container { background: rgba(248,250,252,0.95); padding: 0.5rem 0; border-radius: 14px; margin-bottom: 20px; }
.hero-card { background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%); padding: 28px 40px; border-radius: 14px; color: white; box-shadow: 0 10px 40px rgba(1,40,105,0.20); position: relative; overflow: hidden; border: 1px solid rgba(255,255,255,0.10); }
.hero-title { margin: 0; font-size: 30px; font-weight: 800; color: white !important; letter-spacing: -0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.45); font-family: 'Manrope', sans-serif; }
.hero-sub { margin: 6px 0 0 0; font-size: 14px; opacity: 0.95; color: #F8FAFC; text-shadow: 0 1px 3px rgba(0,0,0,0.40); font-family: 'Inter', sans-serif; }

.base-info { background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%); padding: 1rem 1.5rem; border-radius: 0.75rem; margin-bottom: 1.5rem; display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-family: 'Inter', sans-serif; }
.badge-regiao { padding: 0.3rem 0.9rem; border-radius: 999px; font-size: 0.82rem; font-weight: 700; border: 2px solid; }

.matriz-table-container { width: 100%; overflow-x: auto; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); border: 1px solid #E2E8F0; background: #FFFFFF; margin-bottom: 16px; font-family: 'Inter', sans-serif; }
.matriz-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.matriz-table th { background: #F8FAFC; color: #475569; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 14px 16px; border-bottom: 2px solid #E2E8F0; text-align: center; }
.matriz-table th:first-child { text-align: left; }
.matriz-table td { padding: 10px 16px; border-bottom: 1px solid #F1F5F9; text-align: center; color: #1E293B; }
.matriz-table td:first-child { text-align: left; font-weight: 600; }
.matriz-table tr:hover { background-color: #F8FAFC; }
.matriz-table tr.total-row { background-color: #F1F5F9; font-weight: 800; border-top: 2px solid #CBD5E1; }
.badge-meta-ok { background-color: #DCFCE7; color: #15803D; font-weight: 700; padding: 5px 12px; border-radius: 6px; display: inline-block; min-width: 70px; border: 1px solid #86EFAC; }
.badge-meta-nok { background-color: #FEE2E2; color: #B91C1C; font-weight: 700; padding: 5px 12px; border-radius: 6px; display: inline-block; min-width: 70px; border: 1px solid #FCA5A5; }
.matriz-vazio { color: #94A3B8; font-weight: 700; }
</style>
"""


def _injetar_css_global() -> None:
    st.markdown(_CSS_GLOBAL, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# WRAPPERS DE INTERFACE (UI)
# ══════════════════════════════════════════════════════════════════════
_TEMAS_EXTRA: dict[str, dict[str, str]] = {
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

_TEMAS_PADRAO = frozenset(
    {"azul", "verde", "vermelho", "laranja", "cinza", "roxo", "amarelo", "escuro"}
)


def _kpi_html(
    label: str, value: str, sub: str, tema: dict[str, str], *, compacto: bool
) -> str:
    if compacto:
        return (
            f'<div style="background:{tema["fundo"]};border-left:3px solid {tema["borda"]};'
            f"border-radius:6px;padding:12px 16px;margin-bottom:8px;"
            f'box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
            f'<div style="font-family:{Fontes.TEXTO};font-size:10px;color:{tema["titulo"]};'
            f'text-transform:uppercase;letter-spacing:1px;font-weight:700;">{escape(label)}</div>'
            f'<div style="font-family:{Fontes.TITULO};font-size:20px;color:{tema["texto"]};'
            f"font-weight:800;line-height:1.2;margin-top:4px;"
            f'font-variant-numeric:tabular-nums;">{escape(value)}</div>'
            f'<div style="font-family:{Fontes.TEXTO};font-size:11px;color:{tema["titulo"]};'
            f'margin-top:2px;">{escape(sub)}</div></div>'
        )
    return (
        f'<div style="background:{tema["fundo"]};border-left:4px solid {tema["borda"]};'
        f'border-radius:10px;padding:20px 24px;box-shadow:0 4px 12px rgba(0,0,0,0.08);">'
        f'<div style="font-family:{Fontes.TEXTO};font-size:11px;font-weight:700;'
        f"color:{tema['titulo']};text-transform:uppercase;letter-spacing:1.2px;"
        f'margin-bottom:6px;">{escape(label)}</div>'
        f'<div style="font-family:{Fontes.TITULO};font-size:28px;font-weight:800;'
        f'color:{tema["texto"]};line-height:1;font-variant-numeric:tabular-nums;">'
        f"{escape(value)}</div>"
        f'<div style="font-family:{Fontes.TEXTO};font-size:12px;color:{tema["titulo"]};'
        f'margin-top:6px;font-weight:500;">{escape(sub)}</div></div>'
    )


def _render_kpi_base(
    col: Any,
    label: str,
    value: str,
    sub: str,
    tema: TemaKPI,
    *,
    compacto: bool,
) -> None:
    if not COMPONENTES_DISPONIVEIS:
        col.metric(label, value, sub)
        return

    if tema in _TEMAS_EXTRA:
        col.markdown(
            _kpi_html(label, value, sub, _TEMAS_EXTRA[tema], compacto=compacto),
            unsafe_allow_html=True,
        )
        return

    tema_str = tema if tema in _TEMAS_PADRAO else "azul"
    render = _render_kpi_sm_global if compacto else _render_kpi_global
    render(col, label, value, sub, cast(Any, tema_str))


def render_kpi(
    col: Any, label: str, value: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    _render_kpi_base(col, label, value, sub, tema, compacto=False)


def render_kpi_sm(
    col: Any, label: str, value: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    _render_kpi_base(col, label, value, sub, tema, compacto=True)


def render_insight(texto: str, tipo: TipoInsight = "info") -> None:
    _render_insight_global(texto, tipo)


def _fmt_pct_br(v: Any) -> str:
    try:
        val = float(v) * 100
    except (ValueError, TypeError):
        return "0,00%"
    if not np.isfinite(val):
        return "—"
    return f"{val:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_int_br(v: Any) -> str:
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "0"
    if not np.isfinite(val):
        return "0"
    return f"{int(val):,}".replace(",", ".")


# ══════════════════════════════════════════════════════════════════════
# UTILITÁRIOS OPERACIONAIS
# ══════════════════════════════════════════════════════════════════════
@lru_cache(maxsize=4096)
def _normalizar_texto_cached(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.upper().strip())


@lru_cache(maxsize=2048)
def _classificar_tipo_cached(texto: str) -> str:
    if not texto:
        return "Outros"
    if re.search(r"\bMIGR", texto):
        return "Migração"
    if re.search(
        r"\bPME\b|\bP\s*M\s*E\b|\bPJ\b|PEQUENA\s+EMPRESA|MEDIA\s+EMPRESA"
        r"|EMPRESAR|CORPORAT",
        texto,
    ):
        return "PME"
    if re.search(r"\bND\b|NOV.*DOMICIL|DOMICIL|RESIDENCIAL|NOV.*INSTAL", texto):
        return "Novos Domicílios"
    return "Outros"


@lru_cache(maxsize=2048)
def _traduzir_codigo_baixa(valor: str) -> str:
    valor_upper = valor.strip().upper()
    if valor_upper in VAZIOS or valor_upper in {"EM ROTA", "INICIADO", "PENDENTE"}:
        return "Pendente"
    match = re.match(r"^(\d+)", valor_upper)
    if match:
        return MAPA_CODIGO_NUMERICO.get(int(match.group(1)), "Pendente")
    return "Pendente"


class Utils:
    @staticmethod
    def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
        nome_aba = (aba or "Dados")[:31]
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=nome_aba)
            ws = w.sheets[nome_aba]
            header_fill = PatternFill("solid", fgColor="0F172A")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

            for i, col in enumerate(df.columns, 1):
                largura = 20
                if not df.empty:
                    max_len = df[col].astype(str).str.len().max()
                    if pd.notna(max_len):
                        largura = min(max(int(max_len) + 2, 12), 40)
                largura = max(largura, len(str(col)) + 2)
                ws.column_dimensions[get_column_letter(i)].width = largura
        return out.getvalue()

    @staticmethod
    def normalizar_texto(valor: Any) -> str:
        """Remove acentos e espaços duplicados e converte para maiúsculas."""
        if valor is None:
            return ""
        try:
            if pd.isna(valor):
                return ""
        except (TypeError, ValueError):
            pass
        return _normalizar_texto_cached(str(valor))

    @staticmethod
    def normalizar_coluna(valor: Any) -> str:
        """Normaliza nomes de colunas para comparação."""
        return re.sub(r"[^A-Z0-9]", "", Utils.normalizar_texto(valor))

    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras: Iterable[str]) -> str | None:
        """Procura coluna por nome exato e depois parcial, ignorando acentos."""
        if df is None or df.columns.empty:
            return None

        colunas_normalizadas: dict[str, str] = {}
        for coluna in df.columns:
            colunas_normalizadas.setdefault(Utils.normalizar_coluna(coluna), coluna)

        palavras_norm = [Utils.normalizar_coluna(p) for p in palavras]
        palavras_norm = [p for p in palavras_norm if p]

        for palavra in palavras_norm:
            if palavra in colunas_normalizadas:
                return colunas_normalizadas[palavra]

        for palavra in palavras_norm:
            for coluna_norm, coluna_original in colunas_normalizadas.items():
                if palavra in coluna_norm or coluna_norm in palavra:
                    return coluna_original

        return None

    @staticmethod
    def serie_texto(
        df: pd.DataFrame, coluna: str | None, *, upper: bool = True
    ) -> pd.Series:
        """Série de texto limpa (sempre string, sem NaN) para a coluna indicada."""
        if not coluna or coluna not in df.columns:
            return pd.Series("", index=df.index, dtype="object")
        serie = df[coluna].astype("object").where(df[coluna].notna(), "")
        serie = serie.astype(str).str.strip()
        return serie.str.upper() if upper else serie

    @staticmethod
    def classificar_tipo_servico(valor: Any) -> str:
        """Converte o texto original do serviço em uma categoria oficial."""
        return _classificar_tipo_cached(Utils.normalizar_texto(valor))

    @staticmethod
    def _mapear_rapido(serie: pd.Series, func: Callable[[Any], str]) -> pd.Series:
        """Aplica ``func`` apenas nos valores distintos (ganho em bases grandes)."""
        if serie.empty:
            return pd.Series(dtype="object", index=serie.index)
        mapa = {valor: func(valor) for valor in serie.unique()}
        return serie.map(mapa).astype("object")

    @staticmethod
    def gerar_tipo_servico(
        df: pd.DataFrame, coluna_origem: str | None = None
    ) -> pd.Series:
        """Cria a coluna padronizada TIPO_SERVICO."""
        if df is None or df.empty:
            return pd.Series(dtype="object")

        if coluna_origem is None:
            coluna_origem = Utils.buscar_coluna(df, Config.COLUNAS_TIPO_SERVICO)

        if not coluna_origem or coluna_origem not in df.columns:
            return pd.Series("Outros", index=df.index, dtype="object")

        return Utils._mapear_rapido(
            Utils.serie_texto(df, coluna_origem), Utils.classificar_tipo_servico
        )

    @staticmethod
    def classificar_status_excel(df: pd.DataFrame) -> pd.Series:
        col_inicio = Utils.buscar_coluna(
            df, ["INÍCIO", "INICIO", "DATA INÍCIO", "DT INICIO", "HORA INICIO"]
        )
        col_fechamento = Utils.buscar_coluna(
            df,
            [
                "MOTIVO DE FECHAMENTO EXTERNO",
                "FECHAMENTO EXTERNO",
                "MOTIVO DE FECHAMENTO",
            ],
        )
        col_status_atv = Utils.buscar_coluna(
            df, ["STATUS DA ATIVIDADE", "STATUS ATIVIDADE", "STATUS_ATIVIDADE"]
        )
        col_cod_baixa = Utils.buscar_coluna(df, Config.COLUNAS_COD_BAIXA)
        col_status_os = Utils.buscar_coluna(
            df, ["STATUS DA O.S 1", "STATUS OS 1", "STATUS CONTRATO"]
        )

        # Fallback para bases que só possuem STATUS DA O.S.
        if (
            not any([col_inicio, col_fechamento, col_status_atv, col_cod_baixa])
            and col_status_os
        ):
            status_os = Utils.serie_texto(df, col_status_os)
            return pd.Series(
                np.select(
                    [
                        status_os.eq("EXECUTADA"),
                        status_os.isin(["NÃO EXECUTADA", "NAO EXECUTADA"]),
                    ],
                    ["Executada", "Não Executada"],
                    default="Pendente",
                ),
                index=df.index,
                dtype="object",
            )

        s_inicio = Utils.serie_texto(df, col_inicio)
        s_fechamento = Utils.serie_texto(df, col_fechamento)
        s_status_atv = Utils.serie_texto(df, col_status_atv).str.lower()
        s_cod_baixa = Utils.serie_texto(df, col_cod_baixa, upper=False)

        cond_fechamento = s_fechamento.isin(
            {"LIBERADO NO SISTEMA NETSMS", "CANCELADO NO SISTEMA NETSMS"}
        )
        inicio_vazio = s_inicio.isin(VAZIOS)

        condicoes = [
            inicio_vazio & cond_fechamento,
            (~inicio_vazio) & cond_fechamento,
            s_status_atv.eq("cancelado"),
            s_status_atv.isin(["suspenso", "suspensa"]),
            s_status_atv.isin(
                ["não concluído", "nao concluido", "não concluida", "nao concluida"]
            ),
        ]
        resultados = [
            "Cancelado",
            "Não Executada",
            "Cancelado",
            "Suspenso",
            "Não Executada",
        ]

        status_processado = Utils._mapear_rapido(s_cod_baixa, _traduzir_codigo_baixa)

        return pd.Series(
            np.select(condicoes, resultados, default=status_processado.to_numpy()),
            index=df.index,
            dtype="object",
        )


# ══════════════════════════════════════════════════════════════════════
# CARREGAMENTO E SANEAMENTO DE DADOS (ETL ENGINE)
# ══════════════════════════════════════════════════════════════════════
class DataLoader:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        bio = BytesIO(file_bytes)
        try:
            if filename.lower().endswith(".csv"):
                amostra = bio.read(5000).decode("utf-8", errors="ignore")
                bio.seek(0)
                sep = ";"
                if amostra:
                    try:
                        sep = csv.Sniffer().sniff(amostra, delimiters=";,\t|").delimiter
                    except csv.Error:
                        sep = ";" if amostra.count(";") >= amostra.count(",") else ","
                return pd.read_csv(
                    bio,
                    sep=sep,
                    encoding="utf-8",
                    dtype=str,
                    engine="python",
                    on_bad_lines="skip",
                )
            return pd.read_excel(bio, engine="openpyxl", dtype=str)
        except Exception as e:  # noqa: BLE001 - arquivo vem do usuário
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner="Sincronizando com Google Sheets...")
    def buscar_gsheets() -> pd.DataFrame:
        erros: list[str] = []
        try:
            from streamlit_gsheets import GSheetsConnection

            conn = st.connection("gsheets", type=GSheetsConnection)
            raw = conn.read(
                spreadsheet=Config.URL_LISTA_ATIVOS,
                worksheet=Config.WORKSHEET_ATIVOS,
            )
            if raw is not None and not raw.empty:
                return DataLoader._processar_lista_ativos(raw)
        except Exception as e:  # noqa: BLE001 - conector opcional
            erros.append(f"conexão gsheets: {type(e).__name__}: {e}")

        try:
            url = (
                f"https://docs.google.com/spreadsheets/d/{Config.SHEET_ID_ATIVOS}"
                f"/gviz/tq?tqx=out:csv&sheet={Config.WORKSHEET_ATIVOS}"
            )
            raw = pd.read_csv(url)
            if raw is not None and not raw.empty:
                return DataLoader._processar_lista_ativos(raw)
        except Exception as e:  # noqa: BLE001 - rede pode estar indisponível
            erros.append(f"csv público: {type(e).__name__}: {e}")

        if erros:
            st.session_state["_gsheets_erros"] = erros
        return pd.DataFrame()

    @staticmethod
    def _processar_lista_ativos(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()

        raw = raw.copy()
        raw.columns = raw.columns.astype(str).str.strip()

        equivalencias = {
            "LOGIN": {"LOGIN", "MATRÍCULA", "MATRICULA", "ID"},
            "TÉCNICO": {"TÉCNICO", "TECNICO", "NOME"},
            "MONITOR": {"MONITOR", "GESTOR"},
            "BASE": {"BASE", "REGIÃO", "REGIAO"},
        }
        rename_map = {
            col: destino
            for col in raw.columns
            for destino, aliases in equivalencias.items()
            if col.upper().strip() in aliases
        }
        raw = raw.rename(columns=rename_map)
        raw = raw.loc[:, ~raw.columns.duplicated()]

        cols_uteis = [c for c in equivalencias if c in raw.columns]
        if "LOGIN" not in cols_uteis:
            return pd.DataFrame()

        raw = raw[cols_uteis].copy()
        raw["LOGIN"] = (
            raw["LOGIN"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
            .str.upper()
        )
        raw = raw[~raw["LOGIN"].isin(VAZIOS)].drop_duplicates(
            subset=["LOGIN"], keep="last"
        )
        return raw.reset_index(drop=True)

    @staticmethod
    def preparar_base(
        df: pd.DataFrame, df_gs: pd.DataFrame, filename: str = ""
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.upper()
        df = df.loc[:, ~df.columns.duplicated()]

        # Metadados acumulados e aplicados no final (merge/concat descartam .attrs).
        meta: dict[str, Any] = {
            "arquivo": filename,
            "total_importado": len(df),
            "removidos_suspensos": 0,
            "removidos_contrato": 0,
        }

        coluna_tipo_origem = Utils.buscar_coluna(df, Config.COLUNAS_TIPO_SERVICO)
        valores_tipo_origem: dict[str, int] = {}
        if coluna_tipo_origem:
            valores_tipo_origem = {
                str(chave): int(qtd)
                for chave, qtd in Utils.serie_texto(df, coluna_tipo_origem, upper=False)
                .value_counts()
                .head(20)
                .items()
            }

        # Status operacional
        df["STATUS CONTRATO"] = Utils.classificar_status_excel(df)
        status_upper = df["STATUS CONTRATO"].astype(str).str.strip().str.upper()
        mask_remover = status_upper.isin(
            {"SUSPENSO", "SUSPENSA", "CANCELADO", "CANCELADA"}
        )
        meta["removidos_suspensos"] = int(mask_remover.sum())
        df = df.loc[~mask_remover].reset_index(drop=True)
        if df.empty:
            return pd.DataFrame()

        # Contratos inválidos
        col_contrato = Utils.buscar_coluna(df, Config.COLUNAS_CONTRATO)
        if col_contrato:
            serie_contrato = Utils.serie_texto(df, col_contrato)
            mask_invalido = serie_contrato.isin(VAZIOS) | serie_contrato.eq("0")
            meta["removidos_contrato"] = int(mask_invalido.sum())
            df = df.loc[~mask_invalido].reset_index(drop=True)
            if df.empty:
                return pd.DataFrame()

        # Volume de tarefas
        col_total = Utils.buscar_coluna(df, Config.COLUNAS_TOTAL_TAREFAS)
        if col_total:
            total_tarefas = pd.to_numeric(
                df[col_total].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            df[COL_TOTAL] = total_tarefas.fillna(1).clip(lower=0).astype(int)
        else:
            df[COL_TOTAL] = 1

        # Merge com a lista de ativos
        col_login = Utils.buscar_coluna(df, Config.COLUNAS_LOGIN)
        meta["logins_mapeados"] = False
        if (
            col_login
            and isinstance(df_gs, pd.DataFrame)
            and not df_gs.empty
            and "LOGIN" in df_gs.columns
        ):
            df[col_login] = (
                Utils.serie_texto(df, col_login)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
            )

            ativos = df_gs.copy()
            ativos["LOGIN"] = (
                Utils.serie_texto(ativos, "LOGIN")
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
            )
            ativos = ativos.drop_duplicates(subset=["LOGIN"], keep="last")

            df = df.merge(
                ativos,
                left_on=col_login,
                right_on="LOGIN",
                how="left",
                suffixes=("", "_gs"),
            )
            meta["logins_mapeados"] = True

            for coluna in ("TÉCNICO", "MONITOR", "BASE"):
                origem = f"{coluna}_gs"
                if origem in df.columns:
                    valores = Utils.serie_texto(df, origem)
                    df[coluna] = valores.where(~valores.isin(VAZIOS), pd.NA)
                    df = df.drop(columns=[origem])

            df = df.loc[:, ~df.columns.duplicated()]

        def limpar_texto_coluna(nome_coluna: str, valor_padrao: str) -> pd.Series:
            if nome_coluna not in df.columns:
                return pd.Series(valor_padrao, index=df.index, dtype="object")
            serie = Utils.serie_texto(df, nome_coluna)
            return serie.where(~serie.isin(VAZIOS), valor_padrao)

        df["TÉCNICO"] = limpar_texto_coluna("TÉCNICO", "NÃO MAPEADO")
        df["MONITOR"] = limpar_texto_coluna("MONITOR", "SEM MONITOR")

        # Região
        col_cidade = Utils.buscar_coluna(df, Config.COLUNAS_CIDADE)
        if col_cidade:
            cidade = Utils._mapear_rapido(
                Utils.serie_texto(df, col_cidade), Utils.normalizar_texto
            )
            df["REGIÃO"] = np.select(
                [cidade.isin(cidades) for cidades in Config.REGIOES.values()],
                list(Config.REGIOES.keys()),
                default="OUTRAS",
            )
        else:
            df["REGIÃO"] = "OUTRAS"

        df[COL_TIPO] = Utils.gerar_tipo_servico(df, coluna_origem=coluna_tipo_origem)
        df[COL_STATUS] = df["STATUS CONTRATO"]

        df = df.reset_index(drop=True)
        meta["tipo_servico_coluna"] = coluna_tipo_origem or ""
        meta["valores_tipo_servico_originais"] = valores_tipo_origem
        meta["total_processado"] = len(df)
        df.attrs.update(meta)
        return df

    @staticmethod
    def callback_robo_etl(df_raw: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        caminho = st.session_state.get("robo_candidato_path", "")
        nome = Path(caminho).name if caminho else "Arquivo_Robo"
        df_proc = DataLoader.preparar_base(df_raw, df_gs, filename=nome)

        st.session_state["_robo_df_pronto"] = df_proc
        st.session_state["_robo_nome_arquivo"] = nome
        st.session_state["_robo_dados_disponiveis"] = True
        st.session_state["df_memoria_raw"] = df_raw
        st.session_state["df_memoria"] = df_proc
        st.session_state["origem_dados"] = f"Robô ({nome})"
        st.session_state["robo_hora_sucesso"] = datetime.now().astimezone()
        return df_proc


# ══════════════════════════════════════════════════════════════════════
# MOTOR ANALÍTICO (COMPUTATIONAL ENGINE)
# ══════════════════════════════════════════════════════════════════════
def _razao_segura(numerador: Any, denominador: Any, default: float = 0.0) -> Any:
    """Divisão elemento a elemento sem warnings nem divisão por zero."""
    num = np.asarray(numerador, dtype="float64")
    den = np.asarray(denominador, dtype="float64")
    return np.divide(num, den, out=np.full(num.shape, default), where=den > 0)


class Motor:
    @staticmethod
    @st.cache_data(ttl=3600, show_spinner=False)
    def _cache_wrapper_matriz(df: pd.DataFrame) -> pd.DataFrame:
        return Motor.matriz_resumo_logic(df)

    @staticmethod
    def matriz_resumo_logic(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        obrigatorias = {"MONITOR", COL_TIPO, COL_STATUS, COL_TOTAL}
        if not obrigatorias.issubset(df.columns):
            return pd.DataFrame()

        trabalho = df.loc[:, ["MONITOR", COL_TIPO, COL_STATUS, COL_TOTAL]].copy()
        monitores_txt = Utils.serie_texto(trabalho, "MONITOR")
        trabalho["MONITOR"] = monitores_txt.where(
            ~monitores_txt.isin(VAZIOS), "SEM MONITOR"
        ).astype(str)
        trabalho[COL_TIPO] = Utils._mapear_rapido(
            trabalho[COL_TIPO], Utils.classificar_tipo_servico
        )
        trabalho[COL_STATUS] = Utils.serie_texto(trabalho, COL_STATUS, upper=False)
        trabalho[COL_TOTAL] = pd.to_numeric(
            trabalho[COL_TOTAL], errors="coerce"
        ).fillna(0)

        df_valid = trabalho[trabalho[COL_STATUS].isin(Config.STATUS_ORDEM)].copy()
        if df_valid.empty:
            return pd.DataFrame()

        df_valid["_exec"] = df_valid[COL_TOTAL].where(
            df_valid[COL_STATUS].eq("Executada"), 0
        )
        df_valid["_nex"] = df_valid[COL_TOTAL].where(
            df_valid[COL_STATUS].eq("Não Executada"), 0
        )

        agrupado = (
            df_valid.groupby(["MONITOR", COL_TIPO], dropna=False)
            .agg(executados=("_exec", "sum"), nao_executados=("_nex", "sum"))
            .reset_index()
        )
        agrupado["denominador"] = agrupado["executados"] + agrupado["nao_executados"]
        # Sem volume executado/não executado não há percentual: mantém vazio
        # em vez de exibir 0,00% como se fosse meta atingida.
        agrupado["pct"] = np.where(
            agrupado["denominador"] > 0,
            _razao_segura(agrupado["nao_executados"], agrupado["denominador"]),
            np.nan,
        )

        monitores = pd.Index(sorted(df_valid["MONITOR"].unique()), name="MONITOR")
        pivot = agrupado.pivot(index="MONITOR", columns=COL_TIPO, values="pct").reindex(
            monitores
        )

        for tipo in Config.ORDEM_TIPOS:
            if tipo not in pivot.columns:
                pivot[tipo] = np.nan
        pivot = pivot[Config.ORDEM_TIPOS]

        totais_monitor = (
            df_valid.groupby("MONITOR")[["_exec", "_nex", COL_TOTAL]]
            .sum()
            .reindex(monitores)
            .fillna(0)
        )
        denominador_geral = totais_monitor["_exec"] + totais_monitor["_nex"]
        pivot["Quebra Geral"] = pd.Series(
            _razao_segura(totais_monitor["_nex"], denominador_geral, np.nan),
            index=monitores,
        )
        pivot["Total Tasks"] = totais_monitor[COL_TOTAL].astype(int)

        pivot = pivot.reset_index().rename(columns={"MONITOR": "Monitor"})

        # Linha de total geral
        exec_geral = float(df_valid["_exec"].sum())
        nex_geral = float(df_valid["_nex"].sum())
        den_geral = exec_geral + nex_geral

        total_row: dict[str, Any] = {
            "Monitor": "TOTAL GERAL",
            "Quebra Geral": (nex_geral / den_geral) if den_geral > 0 else np.nan,
            "Total Tasks": int(df_valid[COL_TOTAL].sum()),
        }

        por_tipo = df_valid.groupby(COL_TIPO)[["_exec", "_nex"]].sum()
        for tipo in Config.ORDEM_TIPOS:
            if tipo in por_tipo.index:
                exec_t = float(por_tipo.loc[tipo, "_exec"])
                nex_t = float(por_tipo.loc[tipo, "_nex"])
                den_t = exec_t + nex_t
                total_row[tipo] = (nex_t / den_t) if den_t > 0 else np.nan
            else:
                total_row[tipo] = np.nan

        return pd.concat(
            [pivot, pd.DataFrame([total_row], columns=pivot.columns)],
            ignore_index=True,
        )

    @staticmethod
    def matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        return Motor._cache_wrapper_matriz(df)

    @staticmethod
    def _pivot_status(df: pd.DataFrame, grupo: str) -> pd.DataFrame:
        pv = pd.pivot_table(
            df,
            index=grupo,
            columns=COL_STATUS,
            values=COL_TOTAL,
            aggfunc="sum",
            fill_value=0,
        )
        for c in Config.STATUS_ORDEM:
            if c not in pv.columns:
                pv[c] = 0.0
        out = pv.reset_index()
        out["Considerado"] = out["Executada"] + out["Não Executada"]
        out["Alocado"] = out["Considerado"] + out["Pendente"]
        out["Quebra Atual"] = _razao_segura(out["Não Executada"], out["Considerado"])
        return out

    @staticmethod
    def tabela_cenarios(
        df: pd.DataFrame,
        grupo: str,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 5,
    ) -> pd.DataFrame:
        if df is None or df.empty or grupo not in df.columns:
            return pd.DataFrame()
        if COL_STATUS not in df.columns or COL_TOTAL not in df.columns:
            return pd.DataFrame()

        out = Motor._pivot_status(df, grupo)
        if out.empty:
            return pd.DataFrame()

        # Aqui ``p`` é a probabilidade de o pendente virar NÃO executado
        # (por isso Otimista < Base < Pessimista). Em ``projetar`` o parâmetro
        # tem o sentido inverso: probabilidade de conversão em executado.
        for nome, p in (("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)):
            out[f"Fechamento {nome}"] = _razao_segura(
                out["Não Executada"] + out["Pendente"] * p, out["Alocado"]
            )

        return (
            out[out["Alocado"] >= min_aloc]
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
        if df is None or df.empty or "TÉCNICO" not in df.columns:
            return pd.DataFrame()

        df_seg = (
            df[df[COL_TIPO] == segmento]
            if segmento and segmento != "TODOS" and COL_TIPO in df.columns
            else df
        )
        if df_seg.empty:
            return pd.DataFrame()

        tab = Motor.tabela_cenarios(df_seg, "TÉCNICO", p_ot, p_base, p_pess, min_aloc)
        return tab.head(top_n) if not tab.empty else pd.DataFrame()

    @staticmethod
    def causa_raiz(df: pd.DataFrame, col_baixa: str, top_n: int = 8) -> pd.DataFrame:
        if df is None or COL_STATUS not in df.columns or col_baixa not in df.columns:
            return pd.DataFrame()

        df_nex = df[df[COL_STATUS] == "Não Executada"]
        if df_nex.empty:
            return pd.DataFrame()

        baixa_norm = Utils.serie_texto(df_nex, col_baixa)
        baixa_norm = baixa_norm.where(~baixa_norm.isin(VAZIOS), "SEM REGISTRO")

        volumes = (
            pd.to_numeric(df_nex[COL_TOTAL], errors="coerce")
            .fillna(0)
            .groupby(baixa_norm)
            .sum()
        )
        total_geral = float(volumes.sum())

        res_top = volumes.nlargest(top_n).reset_index()
        res_top.columns = ["Motivo de Baixa", "Volume"]
        # Percentual sobre o total de não executadas (não sobre o top N).
        res_top["% do Total"] = (
            res_top["Volume"] / total_geral if total_geral > 0 else 0.0
        )
        res_top["Acumulado"] = res_top["% do Total"].cumsum()
        return res_top

    @staticmethod
    def backoffice_fila(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or COL_STATUS not in df.columns:
            return pd.DataFrame()
        if not {"MONITOR", "TÉCNICO", COL_TOTAL}.issubset(df.columns):
            return pd.DataFrame()

        df_fila = df[df[COL_STATUS].isin(["Não Executada", "Pendente"])]
        if df_fila.empty:
            return pd.DataFrame()

        index_cols = ["MONITOR", "TÉCNICO"]
        if COL_TIPO in df_fila.columns:
            index_cols.append(COL_TIPO)

        pivot = pd.pivot_table(
            df_fila,
            index=index_cols,
            columns=COL_STATUS,
            values=COL_TOTAL,
            aggfunc="sum",
            fill_value=0,
        ).reset_index()

        for col in ("Não Executada", "Pendente"):
            if col not in pivot.columns:
                pivot[col] = 0

        pivot["Total Fila"] = pivot["Não Executada"] + pivot["Pendente"]
        pivot["Prioridade"] = pivot["Não Executada"] * 2 + pivot["Pendente"]
        pivot["Classificação"] = np.select(
            [
                pivot["Prioridade"] >= 20,
                pivot["Prioridade"] >= 10,
                pivot["Prioridade"] >= 5,
            ],
            ["🔴 CRÍTICO", "🟠 ALTA", "🟡 MÉDIA"],
            default="⚪ BAIXA",
        )

        pivot = pivot.rename(
            columns={"MONITOR": "Monitor", "TÉCNICO": "Técnico", COL_TIPO: "Segmento"}
        )
        cols_final = [
            "Classificação",
            "Monitor",
            "Técnico",
            "Não Executada",
            "Pendente",
            "Total Fila",
            "Prioridade",
        ]
        if "Segmento" in pivot.columns:
            cols_final.insert(3, "Segmento")

        return (
            pivot.sort_values("Prioridade", ascending=False).reset_index(drop=True)
        )[cols_final]

    @staticmethod
    def projetar(
        df: pd.DataFrame,
        probabilidade: float = 0.30,
        grupo: str = "MONITOR",
        incluir_meta: bool = True,
        meta_sla: float = Config.SLA_QUEBRA_MAXIMA,
    ) -> pd.DataFrame:
        if df is None or df.empty or grupo not in df.columns:
            return pd.DataFrame()
        if COL_STATUS not in df.columns or COL_TOTAL not in df.columns:
            return pd.DataFrame()

        out = Motor._pivot_status(df, grupo)
        if out.empty:
            return pd.DataFrame()

        out["Projeção Fechamento"] = _razao_segura(
            out["Não Executada"] + out["Pendente"] * (1 - probabilidade),
            out["Alocado"],
        )
        out["Executadas Projetadas"] = out["Executada"] + out["Pendente"] * (
            probabilidade
        )

        # Fração dos pendentes que precisa ser executada para atingir a meta.
        conversao = _razao_segura(
            out["Alocado"] * (1 - meta_sla) - out["Executada"], out["Pendente"]
        )
        out["Conversão Necessária"] = np.clip(conversao, 0.0, 1.0)

        if incluir_meta:
            out["Status Meta"] = np.select(
                [
                    out["Projeção Fechamento"] <= meta_sla,
                    out["Projeção Fechamento"] <= meta_sla * 1.25,
                    out["Projeção Fechamento"] <= meta_sla * 1.50,
                ],
                ["✅ Dentro da Meta", "⚠️ Atenção", "🔴 Crítico"],
                default="🚨 Muito Crítico",
            )

        out = out.sort_values("Projeção Fechamento", ascending=False)

        for coluna in (
            "Executada",
            "Não Executada",
            "Pendente",
            "Considerado",
            "Alocado",
            "Executadas Projetadas",
        ):
            if coluna in out.columns:
                out[coluna] = (
                    pd.to_numeric(out[coluna], errors="coerce").fillna(0).astype(int)
                )

        return out.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════
# MATRIZ EXECUTIVA EM HTML (COM METAS E FORMATAÇÃO)
# ══════════════════════════════════════════════════════════════════════
_METAS_COLUNA: dict[str, float] = {
    "NOVOS DOMICÍLIOS": Config.SLA_QUEBRA_MAXIMA,
    "NOVOS DOMICILIOS": Config.SLA_QUEBRA_MAXIMA,
    "PME": Config.SLA_QUEBRA_MAXIMA,
    "MIGRAÇÃO": Config.SLA_MIGRACAO_MAXIMA,
    "MIGRACAO": Config.SLA_MIGRACAO_MAXIMA,
    "OUTROS": Config.SLA_QUEBRA_MAXIMA,
    "QUEBRA GERAL": Config.SLA_QUEBRA_MAXIMA,
}

_CELULA_VAZIA = "<td><span class='matriz-vazio'>—</span></td>"


def _celula_percentual(valor: Any, limite_meta: float) -> str:
    try:
        numero = float(valor)
    except (ValueError, TypeError):
        return f"<td>{escape(str(valor))}</td>"
    if not np.isfinite(numero):
        return _CELULA_VAZIA
    classe = "badge-meta-ok" if numero <= limite_meta else "badge-meta-nok"
    return f"<td><span class='{classe}'>{numero:.2%}</span></td>"


def _celula_inteiro(valor: Any) -> str:
    try:
        numero = float(valor)
    except (ValueError, TypeError):
        return f"<td>{escape(str(valor))}</td>"
    if not np.isfinite(numero):
        return _CELULA_VAZIA
    return f"<td><strong>{_fmt_int_br(numero)}</strong></td>"


def _celula_texto(valor: Any) -> str:
    try:
        if pd.isna(valor):
            return _CELULA_VAZIA
    except (TypeError, ValueError):
        pass
    return f"<td>{escape(str(valor))}</td>"


def render_matriz_executiva_html(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        st.info("Sem dados na Matriz Executiva.")
        return

    partes: list[str] = [
        '<div class="matriz-table-container"><table class="matriz-table"><thead><tr>'
    ]
    partes += [f"<th>{escape(str(coluna))}</th>" for coluna in df.columns]
    partes.append("</tr></thead><tbody>")

    colunas_upper = {coluna: str(coluna).strip().upper() for coluna in df.columns}

    for row in df.itertuples(index=False):
        valores = dict(zip(df.columns, row, strict=True))
        primeiro = str(row[0]).strip().upper() if len(row) else ""
        partes.append("<tr class='total-row'>" if primeiro == "TOTAL GERAL" else "<tr>")

        for coluna, valor in valores.items():
            coluna_upper = colunas_upper[coluna]
            if coluna_upper in _METAS_COLUNA:
                partes.append(_celula_percentual(valor, _METAS_COLUNA[coluna_upper]))
            elif coluna_upper in {"TOTAL TASKS", "TOTAL_TASKS"}:
                partes.append(_celula_inteiro(valor))
            else:
                partes.append(_celula_texto(valor))

        partes.append("</tr>")

    partes.append("</tbody></table></div>")
    st.markdown("".join(partes), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# BLOCOS DE INTERFACE
# ══════════════════════════════════════════════════════════════════════
def render_bloco_importacao_robo(dados_prontos: bool = False) -> bool:
    st.markdown(
        """
        <div style="margin-top: 6px; margin-bottom: 4px;">
            <span class="import-header-title">Importação de Dados</span>
            <span class="import-header-badge">EXCEL, CSV OU AUTO</span>
        </div>
        <div class="import-header-sub">Envie a base consolidada de O.S. do dia ou aguarde o robô detectar automaticamente.</div>
        <div class="import-header-line"></div>
        """,
        unsafe_allow_html=True,
    )

    if not dados_prontos:
        return False

    st.markdown(
        '<div class="import-alert-green"><span style="font-size: 16px;">✅</span>'
        "<span>Dados carregados automaticamente! Pronto para processamento.</span></div>",
        unsafe_allow_html=True,
    )
    return st.button(
        "🚀 Processar Dados Carregados",
        type="primary",
        use_container_width=True,
        key="btn_processar_robo_central",
    )


def html_resultado_base(regioes: list[str], total: int, origem: str = "") -> str:
    badges = "".join(
        f'<span class="badge-regiao" style="background:{cor["bg"]};color:{cor["text"]};'
        f'border-color:{cor["border"]};">{escape(str(r))}</span>'
        for r, cor in (
            (r, CORES_REGIAO.get(str(r), CORES_REGIAO["OUTRAS"]))
            for r in sorted(regioes)
        )
    )
    tag_origem = (
        f'<span style="color:#6EE7B7;font-size:0.78rem;font-weight:600;'
        f'margin-left:8px;">• {escape(origem)}</span>'
        if origem
        else ""
    )
    return (
        '<div class="base-info"><span style="color:#94A3B8;font-size:0.8rem;'
        'font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">'
        f"📋 Base Ativa:</span>{badges}{tag_origem}"
        '<span style="color:#FFFFFF;font-size:0.78rem;margin-left:auto;'
        f'font-weight:700;">{_fmt_int_br(total)} registros</span></div>'
    )


def render_hero_topo_fixo(
    titulo: str,
    subtitulo: str,
    regioes: list[str],
    total: int,
    badge: str = "",
    origem: str = "",
) -> None:
    badge_html = (
        '<span style="display:inline-block;background:rgba(255,255,255,0.20);'
        "padding:5px 16px;border-radius:20px;font-size:12px;font-weight:700;"
        "margin-top:10px;letter-spacing:0.6px;text-transform:uppercase;color:white;"
        f'border:1px solid rgba(255,255,255,0.30);">{escape(badge)}</span>'
        if badge
        else ""
    )
    resultado_html = html_resultado_base(regioes, total, origem) if total > 0 else ""
    st.markdown(
        '<div class="hero-container"><div class="hero-card">'
        '<div style="position:relative;z-index:2;">'
        f'<h1 class="hero-title">{escape(titulo)}</h1>'
        f'<p class="hero-sub">{escape(subtitulo)}</p>{badge_html}</div></div>'
        f"{resultado_html}</div>",
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
        f'<div style="background:#FFFFFF;border-radius:0.75rem;padding:1rem 1.2rem;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:0.5rem;">'
        f'<div style="font-size:1rem;font-weight:700;color:#0F172A;display:flex;'
        f'align-items:center;gap:0.5rem;"><span>{icone}</span>'
        f"<span>{escape(titulo)}</span>"
        f'<span style="font-size:0.68rem;background:#E0F2FE;color:#0369A1;'
        f'padding:0.15rem 0.5rem;border-radius:999px;">'
        f"{total_registros} registros</span></div></div>",
        unsafe_allow_html=True,
    )

    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return

    fmt_dict: dict[str, Any] = {}
    for col in df.columns:
        col_u = str(col).upper()
        if any(x in col_u for x in _COLUNAS_PERCENTUAIS):
            fmt_dict[col] = "{:.2%}"
        elif any(x in col_u for x in _COLUNAS_INTEIRAS):
            fmt_dict[col] = "{:,.0f}"

    condicao_cores: dict[str, Any] | None = None
    if color_col and color_col in df.columns:
        condicao_cores = {
            "coluna": color_col,
            "meta": meta,
            "acima_meta": {"bg": "#FEE2E2", "text": "#991B1B", "bold": True},
            "abaixo_meta": {"bg": "#DCFCE7", "text": "#166534", "bold": True},
        }

    render_table_html(
        df,
        fmt=fmt_dict,
        color_rules=condicao_cores,
        colunas_num=list(df.columns),
        height=height,
    )


# ══════════════════════════════════════════════════════════════════════
# DASHBOARD VIEWS AND LAYOUTS
# ══════════════════════════════════════════════════════════════════════
def _avisar_tipo_servico(df: pd.DataFrame) -> None:
    coluna_tipo = df.attrs.get("tipo_servico_coluna", "")
    tipos_processados: set[str] = set()
    if COL_TIPO in df.columns:
        tipos_processados = set(df[COL_TIPO].dropna().astype(str).unique())

    if not coluna_tipo:
        st.warning(
            "⚠️ A base não possui uma coluna identificável de tipo de serviço. "
            "Os registros foram classificados como 'Outros'. Inclua o nome da "
            "coluna em Config.COLUNAS_TIPO_SERVICO."
        )
        return

    if tipos_processados and tipos_processados <= {"Outros"}:
        st.warning(
            f"⚠️ A coluna de segmento ('{coluna_tipo}') foi encontrada, mas nenhum "
            "valor foi reconhecido para Novos Domicílios, PME ou Migração. "
            "Todos os registros ficaram em 'Outros'."
        )
        valores_originais = df.attrs.get("valores_tipo_servico_originais", {})
        if valores_originais:
            st.caption(
                "Valores originais encontrados: "
                + ", ".join(list(valores_originais)[:10])
            )


def view_resumo_executivo(df: pd.DataFrame, meta_sla: float) -> None:
    _avisar_tipo_servico(df)

    render_section_header(
        titulo="Matriz de Quebra por Monitor e Segmento", icone="📊"
    )

    df_matriz = Motor.matriz_resumo(df)
    if df_matriz.empty:
        st.warning("⚠️ Dados insuficientes para montar a Matriz Executiva.")
        return

    if "Monitor" in df_matriz.columns:
        mask_total = (
            df_matriz["Monitor"].astype(str).str.strip().str.upper().eq("TOTAL GERAL")
        )
        if mask_total.any():
            df_matriz = pd.concat(
                [df_matriz.loc[~mask_total], df_matriz.loc[mask_total]],
                ignore_index=True,
            )

    render_matriz_executiva_html(df_matriz)

    quebra_geral = df_matriz["Quebra Geral"].iloc[-1] if len(df_matriz) else np.nan
    if pd.notna(quebra_geral):
        tipo: TipoInsight = "ok" if float(quebra_geral) <= meta_sla else "critico"
        render_insight(
            f"Quebra geral consolidada: {_fmt_pct_br(quebra_geral)} "
            f"(meta {_fmt_pct_br(meta_sla)}).",
            tipo,
        )

    st.download_button(
        "📥 Baixar Matriz (Excel)",
        data=Utils.gerar_excel(df_matriz, "Matriz_Resumo"),
        file_name="Matriz_Resumo_Quebra.xlsx",
        mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
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
            titulo="Cenários de Projeção de Fechamento", icone="📈"
        )
        tab_monitores = Motor.tabela_cenarios(
            df, "MONITOR", p_ot, p_base, p_pess, min_aloc
        )
        render_dataframe_profundo(
            tab_monitores,
            "Projeção por Monitor",
            "👨‍💼",
            color_col="Fechamento Base",
            meta=meta_sla,
        )

    with tab2:
        render_section_header(titulo="Projeção Customizada", icone="🎯")
        col1, col2 = st.columns(2)
        with col1:
            prob_custom = (
                st.slider("Probabilidade de Conversão (%)", 0, 100, 30, step=5) / 100.0
            )
        with col2:
            opcoes_grupo = [
                c for c in ("MONITOR", "TÉCNICO", "REGIÃO") if c in df.columns
            ]
            grupo_proj = st.selectbox("Agrupar por", opcoes_grupo or ["MONITOR"])

        df_proj = Motor.projetar(
            df, probabilidade=prob_custom, grupo=grupo_proj, meta_sla=meta_sla
        )
        render_dataframe_profundo(
            df_proj,
            f"Projeção por {grupo_proj}",
            "🎯",
            color_col="Projeção Fechamento",
            meta=meta_sla,
        )

        if not df_proj.empty:
            k1, k2, k3, k4 = st.columns(4)
            projecao = df_proj["Projeção Fechamento"]
            total = len(df_proj)
            dentro_meta = int((projecao <= meta_sla).sum())
            atencao = int(((projecao > meta_sla) & (projecao <= meta_sla * 1.25)).sum())
            critico = int((projecao > meta_sla * 1.25).sum())
            conversao_media = float(df_proj["Conversão Necessária"].mean())

            render_kpi_sm(
                k1,
                "Dentro da Meta",
                f"{dentro_meta}",
                f"{dentro_meta / total * 100:.0f}%",
                "verde",
            )
            render_kpi_sm(
                k2, "Atenção", f"{atencao}", f"{atencao / total * 100:.0f}%", "amarelo"
            )
            render_kpi_sm(
                k3, "Crítico", f"{critico}", f"{critico / total * 100:.0f}%", "vermelho"
            )
            render_kpi_sm(
                k4,
                "Conversão Média",
                f"{conversao_media:.1%}",
                "Para atingir meta",
                "azul",
            )

    with tab3:
        render_section_header(titulo="Técnicos Mais Críticos", icone="🏆")
        df_tec = Motor.tecnicos_criticos(
            df, "TODOS", p_base, min_aloc, top_n=20, p_ot=p_ot, p_pess=p_pess
        )
        render_dataframe_profundo(
            df_tec,
            "Top 20 Técnicos com Maior Risco",
            "👤",
            color_col="Fechamento Base",
            meta=meta_sla,
        )

    with tab4:
        render_section_header(titulo="Análise de Causa Raiz", icone="🔍")
        col_baixa = Utils.buscar_coluna(df, Config.COLUNAS_COD_BAIXA)
        if col_baixa:
            df_causa = Motor.causa_raiz(df, col_baixa, top_n=10)
            render_dataframe_profundo(df_causa, "Pareto de Motivos", "🎯")
        else:
            st.warning(
                "⚠️ Coluna de 'Código de Baixa' não encontrada para mapear Pareto."
            )

    with tab5:
        render_section_header(titulo="Gestão de Fila (Backoffice)", icone="🛠️")
        df_fila = Motor.backoffice_fila(df)
        render_dataframe_profundo(df_fila, "Fila Priorizada", "📋")


def view_auditoria(df: pd.DataFrame) -> None:
    render_section_header(titulo="Auditoria do Processamento", icone="🧾")

    c1, c2, c3, c4 = st.columns(4)
    render_kpi_sm(c1, "Importados", _fmt_int_br(df.attrs.get("total_importado", 0)))
    render_kpi_sm(c2, "Processados", _fmt_int_br(len(df)), "", "verde")
    render_kpi_sm(
        c3,
        "Susp./Cancel. removidos",
        _fmt_int_br(df.attrs.get("removidos_suspensos", 0)),
        "",
        "amarelo",
    )
    render_kpi_sm(
        c4,
        "Contratos inválidos",
        _fmt_int_br(df.attrs.get("removidos_contrato", 0)),
        "",
        "vermelho",
    )

    coluna_tipo = df.attrs.get("tipo_servico_coluna", "") or "não identificada"
    st.caption(f"Coluna de segmento utilizada: **{coluna_tipo}**")

    valores = df.attrs.get("valores_tipo_servico_originais", {})
    if valores:
        st.dataframe(
            pd.DataFrame(
                sorted(valores.items(), key=lambda kv: kv[1], reverse=True),
                columns=["Valor original", "Ocorrências"],
            ),
            use_container_width=True,
            hide_index=True,
        )

    erros = st.session_state.get("_gsheets_erros")
    if erros:
        with st.expander("Falhas de sincronização com Google Sheets"):
            for erro in erros:
                st.caption(f"• {erro}")

    if not ROBO_DISPONIVEL and _ROBO_IMPORT_ERRO:
        st.caption(f"Robô indisponível — {_ROBO_IMPORT_ERRO}")


# ══════════════════════════════════════════════════════════════════════
# FLUXO PRINCIPAL DE INICIALIZAÇÃO E EVENTOS
# ══════════════════════════════════════════════════════════════════════
def _sidebar_ativos() -> tuple[pd.DataFrame, str]:
    with st.sidebar.expander("⚙️ Configurações & Lista de Ativos", expanded=False):
        st.markdown("### Lista de Ativos (Merge)")

        uploaded_ativos = st.file_uploader(
            "Upload Contingência de Ativos",
            type=["csv", "xlsx"],
            key="uploaded_ativos_manual",
            help="Substitua ou adicione técnicos se o Sheets estiver indisponível.",
        )

        if uploaded_ativos is not None:
            try:
                raw_ativos_manual = DataLoader.ler_arquivo(
                    uploaded_ativos.getvalue(), uploaded_ativos.name
                )
                df_ativos_proc = DataLoader._processar_lista_ativos(raw_ativos_manual)
                if df_ativos_proc.empty:
                    st.error("Arquivo de ativos inválido ou vazio.")
                else:
                    st.session_state["df_gs_manual"] = df_ativos_proc
                    st.toast(
                        f"✅ {len(df_ativos_proc)} ativos carregados manualmente!",
                        icon="👥",
                    )
                    if "df_memoria_raw" in st.session_state:
                        st.session_state["df_memoria"] = DataLoader.preparar_base(
                            st.session_state["df_memoria_raw"], df_ativos_proc
                        )
            except Exception as e:  # noqa: BLE001 - upload do usuário
                st.error(f"Erro no processamento manual: {e}")

        if st.button(
            "🔄 Reiniciar Aplicação", use_container_width=True, type="secondary"
        ):
            st.rerun()

        if st.button("🗑️ Limpar Cache", use_container_width=True, type="secondary"):
            st.cache_data.clear()
            st.session_state.pop("df_gs_manual", None)
            st.success("Cache limpo com sucesso!")
            st.rerun()

    if "df_gs_manual" in st.session_state:
        return st.session_state["df_gs_manual"], "Carregado Manualmente (Backup)"
    return DataLoader.buscar_gsheets(), "Google Sheets (Sincronizado)"


def _sidebar_robo(df_ativos_atv: pd.DataFrame) -> None:
    if "robo_pasta_alvo" not in st.session_state:
        st.session_state["robo_pasta_alvo"] = str(Path.home() / "Downloads")

    st.sidebar.markdown("---")

    if _impl_robo is None:
        st.sidebar.info("🤖 Robô offline. Use upload manual.")
        st.session_state["robo_pasta_alvo"] = st.sidebar.text_input(
            "Pasta monitorada",
            value=st.session_state["robo_pasta_alvo"],
            key="robo_pasta_fallback",
        )
        return

    def callback_robo_com_ativos(
        df_raw: pd.DataFrame,
        df_gs_arg: pd.DataFrame | None = None,
        *_args: Any,
        **_kwargs: Any,
    ) -> pd.DataFrame:
        df_gs_final = (
            df_gs_arg
            if isinstance(df_gs_arg, pd.DataFrame) and not df_gs_arg.empty
            else df_ativos_atv
        )
        return DataLoader.callback_robo_etl(df_raw, df_gs_final)

    try:
        _impl_robo(
            etl_fn=callback_robo_com_ativos,
            gsheets_fn=lambda: df_ativos_atv,
            pasta_padrao=st.session_state["robo_pasta_alvo"],
            ciclos_estabilidade=1,
            mostrar_toggle=True,
            mostrar_config=True,
        )
    except Exception as e:  # noqa: BLE001 - robô não pode derrubar o app
        st.sidebar.error(f"Erro Robô: {e}")


def _carregar_upload_os(df_ativos_atv: pd.DataFrame, robo_tem_dados: bool) -> None:
    if robo_tem_dados:
        with st.expander("📂 Substituir base de O.S. manualmente", expanded=False):
            uploaded_file = st.file_uploader(
                "Upload Manual O.S.",
                type=["csv", "xlsx"],
                key="upload_contingencia_manual",
            )
    else:
        uploaded_file = st.file_uploader(
            "⬇️ Carregar base de O.S. manualmente (CSV/XLSX)",
            type=["csv", "xlsx"],
            help="O Robô monitora a pasta local. Use aqui se estiver offline.",
        )

    if uploaded_file is None:
        return

    file_id = (uploaded_file.name, uploaded_file.size)
    if st.session_state.get("arquivo_processado") == file_id:
        return

    with st.spinner(f"Processando {uploaded_file.name}..."):
        try:
            raw_df = DataLoader.ler_arquivo(
                uploaded_file.getvalue(), uploaded_file.name
            )
            if raw_df.empty:
                st.error("❌ Arquivo vazio ou ilegível.")
                return
            st.session_state["df_memoria_raw"] = raw_df
            st.session_state["df_memoria"] = DataLoader.preparar_base(
                raw_df, df_ativos_atv, filename=uploaded_file.name
            )
            st.session_state["arquivo_processado"] = file_id
            st.session_state["origem_dados"] = f"Upload ({uploaded_file.name})"
            st.session_state["_robo_dados_disponiveis"] = True
        except Exception as e:  # noqa: BLE001 - upload do usuário
            st.error(f"❌ Erro: {e}")
            return

    st.rerun()


def main() -> None:
    _injetar_css_global()

    render_sidebar_brand(
        titulo="TOTALE",
        subtitulo="Quebra Operacional",
        logo="monitoring",
        ambiente="produção",
        versao=f"v{__version__}",
        mostrar_data=True,
    )

    df_ativos_atv, origem_ativos = _sidebar_ativos()

    if df_ativos_atv.empty:
        st.sidebar.error("🚨 Nenhuma base de ativos de técnicos conectada!")
    else:
        st.sidebar.caption(
            f"👥 **Base de Ativos Ativa:** {len(df_ativos_atv)} registros"
        )
        st.sidebar.caption(f"📍 *Origem: {origem_ativos}*")

    _sidebar_robo(df_ativos_atv)

    df_atual: pd.DataFrame | None = st.session_state.get("df_memoria")
    robo_tem_dados = bool(
        st.session_state.get("_robo_dados_disponiveis", False)
        or (df_atual is not None and not df_atual.empty)
    )

    if render_bloco_importacao_robo(dados_prontos=robo_tem_dados):
        raw = st.session_state.get("df_memoria_raw")
        if raw is not None and not raw.empty:
            with st.spinner("Processando base detectada..."):
                st.session_state["df_memoria"] = DataLoader.preparar_base(
                    raw,
                    df_ativos_atv,
                    filename=st.session_state.get("_robo_nome_arquivo", ""),
                )
            st.success("✅ Base processada com sucesso!", icon="🚀")
            st.rerun()
        else:
            st.warning("Nenhuma base bruta disponível para reprocessar.")

    _carregar_upload_os(df_ativos_atv, robo_tem_dados)

    df: pd.DataFrame | None = st.session_state.get("df_memoria")
    if df is None or df.empty:
        st.info("Carregue uma base de O.S. para iniciar a análise.")
        return

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<div style='font-size:12px; font-weight:700; color:#64748B; "
        "text-transform:uppercase;'>🎯 Filtros de Projeção</div>",
        unsafe_allow_html=True,
    )
    p_ot = st.sidebar.slider("Prob. Otimista (%)", 0, 100, 15, step=5) / 100.0
    p_base = st.sidebar.slider("Prob. Base (%)", 0, 100, 30, step=5) / 100.0
    p_pess = st.sidebar.slider("Prob. Pessimista (%)", 0, 100, 50, step=5) / 100.0
    min_aloc = float(st.sidebar.number_input("Mínimo Alocações", value=5, min_value=1))

    regioes_sel = (
        sorted(df["REGIÃO"].dropna().astype(str).unique().tolist())
        if "REGIÃO" in df.columns
        else []
    )

    render_hero_topo_fixo(
        "Super Relatório Corporativo",
        "Análise unificada de desempenho operacional",
        regioes_sel or ["TODAS"],
        len(df),
        badge="TOTALE OPERACIONAL",
        origem=st.session_state.get("origem_dados", "Base Carregada"),
    )

    total_os = len(df)
    nao_mapeados = (
        int((df["TÉCNICO"] == "NÃO MAPEADO").sum()) if "TÉCNICO" in df.columns else 0
    )
    pct_nao_mapeado = (nao_mapeados / total_os) if total_os > 0 else 0.0

    if nao_mapeados > 0:
        st.warning(
            f"⚠️ **Aviso de Integração:** {nao_mapeados} O.S. "
            f"({pct_nao_mapeado:.1%} do volume ativo) não encontraram "
            "correspondência na Lista de Ativos e estão como 'NÃO MAPEADO'."
        )
    else:
        st.success(
            "🎉 **Perfeito!** Todos os logins estão mapeados na Lista de Ativos."
        )

    aba = st.radio(
        "Navegação Principal",
        ["Resumo Executivo", "Análise Detalhada", "Auditoria"],
        horizontal=True,
    )

    if aba == "Resumo Executivo":
        view_resumo_executivo(df, Config.SLA_QUEBRA_MAXIMA)
    elif aba == "Análise Detalhada":
        view_analise_detalhada(
            df, p_ot, p_base, p_pess, min_aloc, Config.SLA_QUEBRA_MAXIMA
        )
    else:
        view_auditoria(df)

    st.divider()


if __name__ == "__main__":
    main()
