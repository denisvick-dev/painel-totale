"""
quebra.py
=========
Super Relatório Corporativo Unificado | Quebra Operacional TOTALE
Versão Final: ETL Robusto + Cache Inteligente + UX Refinado + Método Projetar + Merge Inteligente Ativos + Tabela Formatada c/ Metas

Version: 4.2.1
Author: TOTALE Tecnologia
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import sys
import unicodedata
from collections.abc import Callable
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

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


# ── Componentes visuais globais ─────────────────────────────────────
try:
    from components.componentes import (
        render_section_header,
        render_sidebar_brand,
        render_table_html,
    )
    from components.componentes import render_insight as _render_insight_global
    from components.componentes import render_kpi as _render_kpi_global
    from components.componentes import render_kpi_sm as _render_kpi_sm_global

    COMPONENTES_DISPONIVEIS = True
except ImportError:
    COMPONENTES_DISPONIVEIS = False

    render_section_header = lambda i, t: st.subheader(f"{i} {t}" if i else t)
    render_sidebar_brand = lambda **k: None
    render_table_html = lambda df, **k: st.dataframe(df, use_container_width=True)
    _render_insight_global = lambda t, tipo="info": (
        st.info(t) if tipo == "info" else st.warning(t)
    )
    _render_kpi_global = lambda col, label, value, sub="", tema="azul": col.metric(
        label, value, sub
    )
    _render_kpi_sm_global = lambda col, label, value, sub="", tema="azul": col.metric(
        label, value, sub
    )


# ── Importação do Robô (Lazy Load) ─────────────────────────────────
ROBO_DISPONIVEL: bool = False
_impl_robo: Callable[..., None] | None = None
_ROBO_IMPORT_ERRO: str = ""


def _tentar_import_robo() -> tuple[Callable[..., Any] | None, str]:
    _here = Path(__file__).resolve().parent
    for extra in (_here, _here.parent):
        s = str(extra)
        if s not in sys.path:
            sys.path.insert(0, s)
    try:
        import robo.robo_local as mod

        fn = getattr(mod, "renderizar_robo_local", None) or getattr(
            mod, "render_robo_local", None
        )
        if callable(fn):
            return fn, f"OK ({mod.__file__})"
        return None, "Módulo encontrado mas sem função de render"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


_impl_robo, _ROBO_IMPORT_ERRO = _tentar_import_robo()
ROBO_DISPONIVEL = _impl_robo is not None


def renderizar_robo_local(*args: Any, **kwargs: Any) -> None:
    if _impl_robo:
        try:
            _impl_robo(*args, **kwargs)
        except Exception as e:
            st.sidebar.error(f"Erro no Robô: {e}")
    else:
        st.sidebar.warning("🤖 Robô offline (Modo Manual)")


# ══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES E CONSTANTES
# ═══════════════════════════════════════════════════════════════════════
class Config:
    SLA_QUEBRA_MAXIMA = 0.20
    SLA_MIGRACAO_MAXIMA = 0.25
    URL_LISTA_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    SHEET_ID_ATIVOS = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    WORKSHEET_ATIVOS = "lista_ativos"
    STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]
    CORES_STATUS = {
        "Executada": "#10B981",
        "Não Executada": "#EF4444",
        "Pendente": "#94A3B8",
    }
    ORDEM_TIPOS = ["Novos Domicílios", "PME", "Migração", "Outros"]
    CORES_TIPO = {
        "Novos Domicílios": "#1E40AF",
        "PME": "#7C3AED",
        "Migração": "#0369A1",
        "Quebra Geral": "#78350F",
        "Outros": "#64748B",
    }


MAPA_CODIGO_NUMERICO = {
    **{
        k: "Não Executada"
        for k in [
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
        ]
    },
    **{
        k: "Executada"
        for k in [
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
        ]
    },
}

CORES_REGIAO = {
    "LESTE": {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU": {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM": {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

TemaKPI = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo", "amarelo", "escuro"
]

SLA_QUEBRA_MAXIMA = 0.20
SLA_MIGRACAO_MAXIMA = 0.25

URL_LISTA_ATIVOS = (
    "https://docs.google.com/spreadsheets/d/"
    "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
)

SHEET_ID_ATIVOS = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
WORKSHEET_ATIVOS = "lista_ativos"

STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]

CORES_STATUS = {
    "Executada": "#10B981",
    "Não Executada": "#EF4444",
    "Pendente": "#94A3B8",
}

ORDEM_TIPOS = [
    "Novos Domicílios",
    "PME",
    "Migração",
    "Outros",
]

CORES_TIPO = {
    "Novos Domicílios": "#1E40AF",
    "PME": "#7C3AED",
    "Migração": "#0369A1",
    "Quebra Geral": "#78350F",
    "Outros": "#64748B",
}

SLA_QUEBRA_MAXIMA = 0.20
SLA_MIGRACAO_MAXIMA = 0.25
URL_LISTA_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
SHEET_ID_ATIVOS = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
WORKSHEET_ATIVOS = "lista_ativos"

STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]

CORES_STATUS = {
    "Executada": "#10B981",
    "Não Executada": "#EF4444",
    "Pendente": "#94A3B8",
}

ORDEM_TIPOS = [
    "Novos Domicílios",
    "PME",
    "Migração",
    "Outros",
]

CORES_TIPO = {
    "Novos Domicílios": "#1E40AF",
    "PME": "#7C3AED",
    "Migração": "#0369A1",
    "Quebra Geral": "#78350F",
    "Outros": "#64748B",
}


# Constante global — fora da classe Config
COLUNAS_TIPO_SERVICO: list[str] = [
    "TIPO_SERVICO",
    "TIPO SERVICO",
]


# ═══════════════════════════════════════════════════════════════════════
# CSS GLOBAL
# ═══════════════════════════════════════════════════════════════════════
def _injetar_css_global() -> None:
    st.markdown(
        """
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

    /* Estilização da Tabela Matriz Executiva */
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


# ═══════════════════════════════════════════════════════════════════════
# WRAPPERS DE INTERFACE (UI)
# ═══════════════════════════════════════════════════════════════════════
_MAPA_TEMA_GLOBAL: dict[str, str] = {
    "azul": "azul",
    "verde": "verde",
    "vermelho": "vermelho",
    "laranja": "laranja",
    "cinza": "cinza",
    "roxo": "roxo",
    "amarelo": "amarelo",
    "escuro": "escuro",
}


def render_kpi(
    col: Any, label: str, value: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    if not COMPONENTES_DISPONIVEIS:
        col.metric(label, value, sub)
        return

    temas_extra: dict[str, dict[str, str]] = {
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

    if tema in temas_extra:
        t = temas_extra[tema]
        col.markdown(
            f'<div style="background:{t["fundo"]};border-left:4px solid {t["borda"]};'
            f'border-radius:10px;padding:20px 24px;box-shadow:0 4px 12px rgba(0,0,0,0.08);">'
            f'<div style="font-family:{Fontes.TEXTO};font-size:11px;font-weight:700;'
            f'color:{t["titulo"]};text-transform:uppercase;letter-spacing:1.2px;'
            f'margin-bottom:6px;">{label}</div>'
            f'<div style="font-family:{Fontes.TITULO};font-size:28px;font-weight:800;'
            f'color:{t["texto"]};line-height:1;font-variant-numeric:tabular-nums;">{value}</div>'
            f'<div style="font-family:{Fontes.TEXTO};font-size:12px;color:{t["titulo"]};'
            f'margin-top:6px;font-weight:500;">{sub}</div></div>',
            unsafe_allow_html=True,
        )
    else:
        tema_str = _MAPA_TEMA_GLOBAL.get(str(tema), "azul")
        _render_kpi_global(col, label, value, sub, cast(Any, tema_str))


def render_kpi_sm(
    col: Any, label: str, value: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    if not COMPONENTES_DISPONIVEIS:
        col.metric(label, value, sub)
        return

    temas_extra: dict[str, dict[str, str]] = {
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

    if tema in temas_extra:
        t = temas_extra[tema]
        col.markdown(
            f'<div style="background:{t["fundo"]};border-left:3px solid {t["borda"]};'
            f"border-radius:6px;padding:12px 16px;margin-bottom:8px;"
            f'box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
            f'<div style="font-family:{Fontes.TEXTO};font-size:10px;color:{t["titulo"]};'
            f'text-transform:uppercase;letter-spacing:1px;font-weight:700;">{label}</div>'
            f'<div style="font-family:{Fontes.TITULO};font-size:20px;color:{t["texto"]};'
            f"font-weight:800;line-height:1.2;margin-top:4px;"
            f'font-variant-numeric:tabular-nums;">{value}</div>'
            f'<div style="font-family:{Fontes.TEXTO};font-size:11px;color:{t["titulo"]};'
            f'margin-top:2px;">{sub}</div></div>',
            unsafe_allow_html=True,
        )
    else:
        tema_str = _MAPA_TEMA_GLOBAL.get(str(tema), "azul")
        _render_kpi_sm_global(col, label, value, sub, cast(Any, tema_str))


def render_insight(
    texto: str, tipo: Literal["ok", "info", "alerta", "critico", "acao"] = "info"
) -> None:
    _render_insight_global(texto, tipo)


def _fmt_pct_br(v: Any) -> str:
    try:
        val = float(v) * 100
        return f"{val:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00%"


def _fmt_int_br(v: Any) -> str:
    try:
        return f"{int(float(v)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


# ═══════════════════════════════════════════════════════════════════════
# UTILITÁRIOS OPERACIONAIS
# ═══════════════════════════════════════════════════════════════════════
class Utils:
    @staticmethod
    def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=aba[:31])
            ws = w.sheets[aba[:31]]
            header_fill = PatternFill("solid", fgColor="0F172A")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

            for i, col in enumerate(df.columns, 1):
                try:
                    max_len = df[col].astype(str).str.len().max()
                    ws.column_dimensions[get_column_letter(i)].width = min(
                        max(max_len + 2, 12), 40
                    )
                except Exception:
                    ws.column_dimensions[get_column_letter(i)].width = 20
        return out.getvalue()
    
    @staticmethod
    def normalizar_texto(valor: Any) -> str:
        """
        Remove acentos, espaços duplicados e converte para maiúsculas.
        """
        if valor is None:
            return ""

        try:
            if pd.isna(valor):
                return ""
        except (TypeError, ValueError):
            pass

        texto = str(valor)

        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(
            caractere
            for caractere in texto
            if not unicodedata.combining(caractere)
        )

        texto = texto.upper().strip()
        texto = re.sub(r"\s+", " ", texto)

        return texto

    @staticmethod
    def normalizar_coluna(valor: Any) -> str:
        """
        Normaliza nomes de colunas para comparação.
        """
        texto = Utils.normalizar_texto(valor)
        return re.sub(r"[^A-Z0-9]", "", texto)

    @staticmethod
    def buscar_coluna(
        df: pd.DataFrame,
        palavras: list[str],
    ) -> str | None:
        """
        Procura uma coluna por nome exato ou parcial,
        ignorando acentos, espaços e pontuação.
        """
        if df is None or df.empty:
            return None

        colunas_normalizadas = {
            Utils.normalizar_coluna(coluna): coluna
            for coluna in df.columns
        }

        for palavra in palavras:
            palavra_normalizada = Utils.normalizar_coluna(palavra)

            if not palavra_normalizada:
                continue

            # Primeiro tenta correspondência exata
            if palavra_normalizada in colunas_normalizadas:
                return colunas_normalizadas[palavra_normalizada]

            # Depois tenta correspondência parcial
            for coluna_normalizada, coluna_original in (
                colunas_normalizadas.items()
            ):
                if (
                    palavra_normalizada in coluna_normalizada
                    or coluna_normalizada in palavra_normalizada
                ):
                    return coluna_original

        return None

    @staticmethod
    def classificar_tipo_servico(valor: Any) -> str:
        """
        Converte o texto original do serviço para uma das categorias oficiais.
        """
        texto = Utils.normalizar_texto(valor)

        if not texto:
            return "Outros"

        # Migração deve ser avaliada antes das demais categorias
        if re.search(r"\bMIGR", texto):
            return "Migração"

        # PME / empresarial
        if re.search(
            r"\bPME\b"
            r"|\bP\s*M\s*E\b"
            r"|\bPJ\b"
            r"|PEQUENA\s+EMPRESA"
            r"|MEDIA\s+EMPRESA"
            r"|EMPRESAR"
            r"|CORPORAT",
            texto,
        ):
            return "PME"

        # Novos domicílios / residencial / nova instalação
        if re.search(
            r"\bND\b"
            r"|NOV.*DOMICIL"
            r"|DOMICIL"
            r"|RESIDENCIAL"
            r"|NOV.*INSTAL",
            texto,
        ):
            return "Novos Domicílios"

        if texto in {
            "OUTRO",
            "OUTROS",
            "OUTRA",
            "OUTRAS",
        }:
            return "Outros"

        return "Outros"

    @staticmethod
    def gerar_tipo_servico(
        df: pd.DataFrame,
        coluna_origem: str | None = None,
    ) -> pd.Series:
        """
        Cria a coluna padronizada TIPO_SERVICO.
        """
        if df is None or df.empty:
            return pd.Series(dtype="object")

        if coluna_origem is None:
            coluna_origem = Utils.buscar_coluna(
                df,
                COLUNAS_TIPO_SERVICO,
            )

        if not coluna_origem or coluna_origem not in df.columns:
            return pd.Series(
                "Outros",
                index=df.index,
                dtype="object",
            )

        return df[coluna_origem].map(
            Utils.classificar_tipo_servico
        ).astype("object")

    @staticmethod
    def classificar_status_excel(df: pd.DataFrame) -> pd.Series:
        col_inicio = Utils.buscar_coluna(
            df,
            [
                "INÍCIO",
                "INICIO",
                "DATA INÍCIO",
                "DT INICIO",
                "HORA INICIO",
            ],
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
            df,
            [
                "STATUS DA ATIVIDADE",
                "STATUS ATIVIDADE",
                "STATUS_ATIVIDADE",
            ],
        )

        col_cod_baixa = Utils.buscar_coluna(
            df,
            [
                "CÓD DE BAIXA 1",
                "COD DE BAIXA 1",
                "MOTIVO DE BAIXA",
                "COD_BAIXA",
            ],
        )

        col_status_os = Utils.buscar_coluna(
            df,
            [
                "STATUS DA O.S 1",
                "STATUS OS 1",
                "STATUS CONTRATO",
            ],
        )

        s_inicio = (
            df[col_inicio]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            if col_inicio
            else pd.Series("", index=df.index)
        )

        s_fechamento = (
            df[col_fechamento]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            if col_fechamento
            else pd.Series("", index=df.index)
        )

        s_status_atv = (
            df[col_status_atv]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            if col_status_atv
            else pd.Series("", index=df.index)
        )

        s_cod_baixa = (
            df[col_cod_baixa]
            .fillna("")
            .astype(str)
            .str.strip()
            if col_cod_baixa
            else pd.Series("", index=df.index)
        )

        fechamento_alvo = {
            "LIBERADO NO SISTEMA NETSMS",
            "CANCELADO NO SISTEMA NETSMS",
        }

        cond_fechamento = s_fechamento.isin(fechamento_alvo)

        inicio_vazio = s_inicio.isin(
            {
                "",
                "NAN",
                "NONE",
                "NULL",
                "NAT",
                "NA",
            }
        )

        condicoes = [
            inicio_vazio & cond_fechamento,
            (~inicio_vazio) & cond_fechamento,
            s_status_atv.eq("cancelado"),
            s_status_atv.isin(["suspenso", "suspensa"]),
            s_status_atv.isin(
                [
                    "não concluído",
                    "nao concluido",
                    "não concluida",
                    "nao concluida",
                ]
            ),
        ]

        resultados = [
            "Cancelado",
            "Não Executada",
            "Cancelado",
            "Suspenso",
            "Não Executada",
        ]

        def traduzir_codigo(valor: str) -> str:
            if not valor:
                return "Pendente"

            valor_upper = str(valor).strip().upper()

            if valor_upper in {
                "NAN",
                "NONE",
                "NULL",
                "",
                "EM ROTA",
                "INICIADO",
                "PENDENTE",
            }:
                return "Pendente"

            match = re.match(r"^(\d+)", valor_upper)

            if match:
                codigo = int(match.group(1))
                return MAPA_CODIGO_NUMERICO.get(
                    codigo,
                    "Pendente",
                )

            return "Pendente"

        status_processado = s_cod_baixa.map(traduzir_codigo)

        # Fallback para bases que possuem somente STATUS DA O.S.
        if (
            not any(
                [
                    col_inicio,
                    col_fechamento,
                    col_status_atv,
                    col_cod_baixa,
                ]
            )
            and col_status_os
        ):
            status_os = (
                df[col_status_os]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

            return pd.Series(
                np.select(
                    [
                        status_os.eq("EXECUTADA"),
                        status_os.isin(
                            [
                                "NÃO EXECUTADA",
                                "NAO EXECUTADA",
                            ]
                        ),
                    ],
                    [
                        "Executada",
                        "Não Executada",
                    ],
                    default="Pendente",
                ),
                index=df.index,
            )

        return pd.Series(
            np.select(
                condicoes,
                resultados,
                default=status_processado,
            ),
            index=df.index,
        )


# ═══════════════════════════════════════════════════════════════════════
# CARREGAMENTO E SANEAMENTO DE DADOS (ETL ENGINE)
# ══════════════════════════════════════════════════════════════════════
class DataLoader:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        bio = BytesIO(file_bytes)
        try:
            if filename.lower().endswith(".csv"):
                bio.seek(0)
                amostra = bio.read(5000).decode("utf-8", errors="ignore")
                bio.seek(0)
                sep = csv.Sniffer().sniff(amostra).delimiter if amostra else ";"
                return pd.read_csv(
                    bio,
                    sep=sep,
                    encoding="utf-8",
                    dtype=str,
                    engine="python",
                    on_bad_lines="skip",
                )
            return pd.read_excel(bio, engine="openpyxl", dtype=str)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner="Sincronizando com Google Sheets...")
    def buscar_gsheets() -> pd.DataFrame:
        try:
            from streamlit_gsheets import GSheetsConnection

            conn = st.connection("gsheets", type=GSheetsConnection)
            raw = conn.read(
                spreadsheet=Config.URL_LISTA_ATIVOS, worksheet=Config.WORKSHEET_ATIVOS
            )
            if raw is not None and not raw.empty:
                return DataLoader._processar_lista_ativos(raw)
        except Exception:
            pass
        try:
            url = f"https://docs.google.com/spreadsheets/d/{Config.SHEET_ID_ATIVOS}/gviz/tq?tqx=out:csv&sheet={Config.WORKSHEET_ATIVOS}"
            raw = pd.read_csv(url)
            if raw is not None and not raw.empty:
                return DataLoader._processar_lista_ativos(raw)
        except Exception:
            pass
        return pd.DataFrame()

    @staticmethod
    def _processar_lista_ativos(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        raw.columns = raw.columns.astype(str).str.strip()
        rename_map = {}
        for col in raw.columns:
            cu = col.upper().strip()
            if cu in ("LOGIN", "MATRÍCULA", "MATRICULA", "ID"):
                rename_map[col] = "LOGIN"
            elif cu in ("TÉCNICO", "TECNICO", "NOME"):
                rename_map[col] = "TÉCNICO"
            elif cu in ("MONITOR", "GESTOR"):
                rename_map[col] = "MONITOR"
            elif cu in ("BASE", "REGIÃO", "REGIAO"):
                rename_map[col] = "BASE"

        raw = raw.rename(columns=rename_map)
        cols_uteis = [
            c for c in ["LOGIN", "TÉCNICO", "MONITOR", "BASE"] if c in raw.columns
        ]
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
        raw = raw[raw["LOGIN"].str.strip() != ""].drop_duplicates(
            subset=["LOGIN"], keep="last"
        )
        return raw.reset_index(drop=True)

    @staticmethod
    def preparar_base(
        df: pd.DataFrame,
        df_gs: pd.DataFrame,
        filename: str = "",
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()

        # Padroniza nomes das colunas
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.upper()
        )

        total_importado = len(df)

        # Identifica a coluna de serviço antes de criar TIPO_SERVICO
        coluna_tipo_origem = Utils.buscar_coluna(
            df,
            COLUNAS_TIPO_SERVICO,
        )

        valores_tipo_origem: dict[str, int] = {}

        if coluna_tipo_origem and coluna_tipo_origem in df.columns:
            valores_tipo = (
                df[coluna_tipo_origem]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            valores_tipo_origem = {
                str(chave): int(valor)
                for chave, valor in valores_tipo
                .value_counts()
                .head(20)
                .items()
            }

        df.attrs["total_importado"] = total_importado

        # Classifica status operacional
        df["STATUS CONTRATO"] = Utils.classificar_status_excel(df)

        # Corrige o problema de maiúsculas/minúsculas
        status_upper = (
            df["STATUS CONTRATO"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        mask_remover = status_upper.isin(
            {
                "SUSPENSO",
                "SUSPENSA",
                "CANCELADO",
                "CANCELADA",
            }
        )

        removidos_status = int(mask_remover.sum())

        df = df.loc[~mask_remover].reset_index(drop=True)

        df.attrs["removidos_suspensos"] = removidos_status

        if df.empty:
            return pd.DataFrame()

        # Remove contratos inválidos
        col_contrato = Utils.buscar_coluna(
            df,
            [
                "CONTRATO",
                "NR CONTRATO",
                "CONTRATO_ID",
            ],
        )

        removidos_contrato = 0

        if col_contrato:
            serie_contrato = (
                df[col_contrato]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

            mask_contrato_invalido = serie_contrato.isin(
                {
                    "",
                    "NAN",
                    "NONE",
                    "N/A",
                    "NA",
                    "-",
                    "0",
                    "NULL",
                }
            )

            removidos_contrato = int(mask_contrato_invalido.sum())

            df = df.loc[~mask_contrato_invalido].copy()

        df.attrs["removidos_contrato"] = removidos_contrato

        if df.empty:
            return pd.DataFrame()

        # Total de tarefas
        col_total = Utils.buscar_coluna(
            df,
            [
                "TOTAL DE TAREFAS",
                "QTD TAREFAS",
                "QUANTIDADE",
                "VOLUME",
            ],
        )

        if col_total:
            total_tarefas = pd.to_numeric(
                df[col_total]
                .astype(str)
                .str.replace(",", ".", regex=False),
                errors="coerce",
            )

            df["TOTAL DE TAREFAS"] = (
                total_tarefas
                .fillna(1)
                .clip(lower=0)
                .astype(int)
            )
        else:
            df["TOTAL DE TAREFAS"] = 1

        # Localiza login do técnico
        col_login = Utils.buscar_coluna(
            df,
            [
                "LOGIN DO TÉCNICO",
                "LOGIN DO TECNICO",
                "LOGIN",
                "USUÁRIO",
                "USUARIO",
                "MATRÍCULA",
                "MATRICULA",
            ],
        )

        # Merge com lista de ativos
        if (
            col_login
            and isinstance(df_gs, pd.DataFrame)
            and not df_gs.empty
            and "LOGIN" in df_gs.columns
        ):
            df[col_login] = (
                df[col_login]
                .fillna("")
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
                .str.upper()
            )

            ativos = df_gs.copy()

            ativos["LOGIN"] = (
                ativos["LOGIN"]
                .fillna("")
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
                .str.upper()
            )

            ativos = ativos.drop_duplicates(
                subset=["LOGIN"],
                keep="last",
            )

            df = df.merge(
                ativos,
                left_on=col_login,
                right_on="LOGIN",
                how="left",
                suffixes=("", "_gs"),
            )

            if "TÉCNICO_gs" in df.columns:
                tecnico_gs = (
                    df["TÉCNICO_gs"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.upper()
                )

                df["TÉCNICO"] = tecnico_gs.mask(
                    tecnico_gs.isin(
                        {
                            "",
                            "NAN",
                            "NONE",
                            "NULL",
                        }
                    ),
                    "NÃO MAPEADO",
                )

            if "MONITOR_gs" in df.columns:
                monitor_gs = (
                    df["MONITOR_gs"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.upper()
                )

                df["MONITOR"] = monitor_gs.mask(
                    monitor_gs.isin(
                        {
                            "",
                            "NAN",
                            "NONE",
                            "NULL",
                        }
                    ),
                    "SEM MONITOR",
                )

            df = df.loc[
                :,
                ~df.columns.duplicated(),
            ]

        def limpar_texto_coluna(
            nome_coluna: str,
            valor_padrao: str,
        ) -> pd.Series:
            if nome_coluna not in df.columns:
                return pd.Series(
                    valor_padrao,
                    index=df.index,
                    dtype="string",
                )

            serie = (
                df[nome_coluna]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

            return serie.mask(
                serie.isin(
                    {
                        "",
                        "NAN",
                        "NONE",
                        "NULL",
                        "NAT",
                    }
                ),
                valor_padrao,
            )

        df["TÉCNICO"] = limpar_texto_coluna(
            "TÉCNICO",
            "NÃO MAPEADO",
        )

        df["MONITOR"] = limpar_texto_coluna(
            "MONITOR",
            "SEM MONITOR",
        )

        # Classificação da região
        col_cidade = Utils.buscar_coluna(
            df,
            [
                "CIDADE",
                "LOCALIDADE",
                "MUNICÍPIO",
                "MUNICIPIO",
            ],
        )

        if col_cidade:
            cidade = (
                df[col_cidade]
                .fillna("")
                .map(Utils.normalizar_texto)
            )

            df["REGIÃO"] = np.select(
                [
                    cidade.isin(
                        {
                            "SAO PAULO",
                        }
                    ),
                    cidade.isin(
                        {
                            "GUARULHOS",
                            "ARUJA",
                            "MOGI DAS CRUZES",
                            "SUZANO",
                            "ITAQUAQUECETUBA",
                            "FERRAZ DE VASCONCELOS",
                            "POA",
                        }
                    ),
                    cidade.isin(
                        {
                            "SANTO ANDRE",
                            "SAO BERNARDO DO CAMPO",
                            "SAO CAETANO DO SUL",
                            "DIADEMA",
                            "MAUA",
                            "RIBEIRAO PIRES",
                            "RIO GRANDE DA SERRA",
                        }
                    ),
                ],
                [
                    "LESTE",
                    "GRU",
                    "ABCDM",
                ],
                default="OUTRAS",
            )
        else:
            df["REGIÃO"] = "OUTRAS"

        # ==============================================================
        # CORREÇÃO PRINCIPAL:
        # Cria efetivamente a coluna usada pelo motor analítico
        # ==============================================================
        df["TIPO_SERVICO"] = Utils.gerar_tipo_servico(
            df,
            coluna_origem=coluna_tipo_origem,
        )

        df["Status Contrato"] = df["STATUS CONTRATO"]

        # Metadados para auditoria
        df.attrs["tipo_servico_coluna"] = coluna_tipo_origem or ""
        df.attrs["valores_tipo_servico_originais"] = valores_tipo_origem

        return df.reset_index(drop=True)

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
        st.session_state["robo_hora_sucesso"] = datetime.now()
        return df_proc


# ═══════════════════════════════════════════════════════════════════════
# MOTOR ANALÍTICO (COMPUTATIONAL ENGINE)
# ═══════════════════════════════════════════════════════════════════════
class Motor:
    @staticmethod
    def _get_df_hash(df: pd.DataFrame) -> str:
        return hashlib.md5(
            f"{df.shape}{df.select_dtypes(include=np.number).sum().sum()}".encode()
        ).hexdigest()

    @staticmethod
    @st.cache_data(
        ttl=3600,
        show_spinner=False,
    )
    def _cache_wrapper_matriz(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        return Motor.matriz_resumo_logic(df)

    @staticmethod
    def matriz_resumo_logic(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        colunas_obrigatorias = {
            "MONITOR",
            "TIPO_SERVICO",
            "Status Contrato",
            "TOTAL DE TAREFAS",
        }

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

        trabalho["TIPO_SERVICO"] = trabalho[
            "TIPO_SERVICO"
        ].map(
            Utils.classificar_tipo_servico
        )

        trabalho["Status Contrato"] = (
            trabalho["Status Contrato"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        trabalho["TOTAL DE TAREFAS"] = pd.to_numeric(
            trabalho["TOTAL DE TAREFAS"],
            errors="coerce",
        ).fillna(0)

        # Considera somente os status válidos do fluxo operacional
        df_valid = trabalho[
            trabalho["Status Contrato"].isin(
                Config.STATUS_ORDEM
            )
        ].copy()

        if df_valid.empty:
            return pd.DataFrame()

        df_valid["_exec"] = np.where(
            df_valid["Status Contrato"].eq("Executada"),
            df_valid["TOTAL DE TAREFAS"],
            0,
        )

        df_valid["_nex"] = np.where(
            df_valid["Status Contrato"].eq("Não Executada"),
            df_valid["TOTAL DE TAREFAS"],
            0,
        )

        agrupado = (
            df_valid
            .groupby(
                [
                    "MONITOR",
                    "TIPO_SERVICO",
                ],
                dropna=False,
            )
            .agg(
                executados=("_exec", "sum"),
                nao_executados=("_nex", "sum"),
                total=("TOTAL DE TAREFAS", "sum"),
            )
            .reset_index()
        )

        agrupado["denominador"] = (
            agrupado["executados"]
            + agrupado["nao_executados"]
        )

        # Sem volume executado ou não executado = sem percentual
        # Não deve aparecer como 0,00% verde
        agrupado["pct"] = np.where(
            agrupado["denominador"] > 0,
            agrupado["nao_executados"]
            / agrupado["denominador"],
            np.nan,
        )

        monitores = pd.Index(
            sorted(
                df_valid["MONITOR"]
                .dropna()
                .astype(str)
                .unique()
            ),
            name="MONITOR",
        )

        pivot = (
            agrupado
            .pivot(
                index="MONITOR",
                columns="TIPO_SERVICO",
                values="pct",
            )
            .reindex(monitores)
        )

        # Garante todas as colunas oficiais
        for tipo in Config.ORDEM_TIPOS:
            if tipo not in pivot.columns:
                pivot[tipo] = np.nan

        pivot = pivot[
            Config.ORDEM_TIPOS
        ]

        totais_monitor = (
            df_valid
            .groupby("MONITOR")[
                [
                    "_exec",
                    "_nex",
                ]
            ]
            .sum()
            .reindex(monitores)
            .fillna(0)
        )

        denominador_geral = (
            totais_monitor["_exec"]
            + totais_monitor["_nex"]
        )

        pivot["Quebra Geral"] = (
            totais_monitor["_nex"]
            / denominador_geral
        ).where(
            denominador_geral > 0,
            np.nan,
        )

        pivot["Total Tasks"] = (
            df_valid
            .groupby("MONITOR")[
                "TOTAL DE TAREFAS"
            ]
            .sum()
            .reindex(monitores)
            .fillna(0)
            .astype(int)
        )

        pivot = (
            pivot
            .reset_index()
            .rename(
                columns={
                    "MONITOR": "Monitor",
                }
            )
        )

        # Total geral
        total_row: dict[str, Any] = {
            "Monitor": "TOTAL GERAL",
        }

        executados_geral = float(
            df_valid["_exec"].sum()
        )

        nao_executados_geral = float(
            df_valid["_nex"].sum()
        )

        denominador_geral_total = (
            executados_geral
            + nao_executados_geral
        )

        total_row["Quebra Geral"] = (
            nao_executados_geral
            / denominador_geral_total
            if denominador_geral_total > 0
            else np.nan
        )

        total_row["Total Tasks"] = int(
            df_valid["TOTAL DE TAREFAS"].sum()
        )

        for tipo in Config.ORDEM_TIPOS:
            subtotal = df_valid[
                df_valid["TIPO_SERVICO"].eq(tipo)
            ]

            executados_tipo = float(
                subtotal["_exec"].sum()
            )

            nao_executados_tipo = float(
                subtotal["_nex"].sum()
            )

            denominador_tipo = (
                executados_tipo
                + nao_executados_tipo
            )

            total_row[tipo] = (
                nao_executados_tipo
                / denominador_tipo
                if denominador_tipo > 0
                else np.nan
            )

        return pd.concat(
            [
                pivot,
                pd.DataFrame([total_row]),
            ],
            ignore_index=True,
        )

    @staticmethod
    def matriz_resumo(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        return Motor._cache_wrapper_matriz(df.copy())

    @staticmethod
    def tabela_cenarios(
        df: pd.DataFrame,
        grupo: str,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 5,
    ) -> pd.DataFrame:
        if df.empty or grupo not in df.columns:
            return pd.DataFrame()
        pv = pd.pivot_table(
            df,
            index=grupo,
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        )
        for c in Config.STATUS_ORDEM:
            if c not in pv.columns:
                pv[c] = 0.0
        out = pv.reset_index()
        out["Considerado"] = out["Executada"] + out["Não Executada"]
        out["Alocado"] = out["Considerado"] + out["Pendente"]
        out["Quebra Atual"] = np.where(
            out["Considerado"] > 0, out["Não Executada"] / out["Considerado"], 0
        )

        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            out[f"Fechamento {nome}"] = np.where(
                out["Alocado"] > 0,
                (out["Não Executada"] + out["Pendente"] * p) / out["Alocado"],
                0,
            )
        return out[out["Alocado"] >= min_aloc].sort_values(
            "Fechamento Base", ascending=False
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
        df_seg = (
            df[df["TIPO_SERVICO"] == segmento].copy()
            if segmento and segmento != "TODOS" and "TIPO_SERVICO" in df.columns
            else df.copy()
        )
        if df_seg.empty:
            return pd.DataFrame()
        tab = Motor.tabela_cenarios(df_seg, "TÉCNICO", p_ot, p_base, p_pess, min_aloc)
        return tab.head(top_n) if not tab.empty else pd.DataFrame()

    @staticmethod
    def causa_raiz(df: pd.DataFrame, col_baixa: str, top_n: int = 8) -> pd.DataFrame:
        if "Status Contrato" not in df.columns:
            return pd.DataFrame()
        df_nex = df[df["Status Contrato"] == "Não Executada"].copy()
        if df_nex.empty or col_baixa not in df_nex.columns:
            return pd.DataFrame()

        df_nex["_baixa_norm"] = (
            df_nex[col_baixa]
            .fillna("Sem Registro")
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"NAN": "Sem Registro", "": "Sem Registro"})
        )
        
        # Agrupamento limpo: Series.groupby().sum().nlargest()
        s_top = df_nex.groupby("_baixa_norm")["TOTAL DE TAREFAS"].sum().nlargest(top_n)
        
        res_top = s_top.reset_index()
        res_top.columns = ["Motivo de Baixa", "Volume"]
        
        total = float(res_top["Volume"].sum())
        res_top["% do Total"] = res_top["Volume"] / total if total > 0 else 0.0
        res_top["Acumulado"] = res_top["% do Total"].cumsum()
        return res_top

    @staticmethod
    def backoffice_fila(df: pd.DataFrame) -> pd.DataFrame:
        if "Status Contrato" not in df.columns:
            return pd.DataFrame()
        df_fila = df[df["Status Contrato"].isin(["Não Executada", "Pendente"])]
        if df_fila.empty:
            return pd.DataFrame()

        cols_group = ["MONITOR", "TÉCNICO", "Status Contrato"]
        if "TIPO_SERVICO" in df_fila.columns:
            cols_group.insert(2, "TIPO_SERVICO")

        agg = df_fila.groupby(cols_group)["TOTAL DE TAREFAS"].sum().reset_index()
        pivot_cols = ["MONITOR", "TÉCNICO"]
        if "TIPO_SERVICO" in agg.columns:
            pivot_cols.append("TIPO_SERVICO")

        pivot = pd.pivot_table(
            agg,
            index=pivot_cols,
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        for col in ["Não Executada", "Pendente"]:
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

        rename_map = {"MONITOR": "Monitor", "TÉCNICO": "Técnico"}
        if "TIPO_SERVICO" in pivot.columns:
            rename_map["TIPO_SERVICO"] = "Segmento"
        pivot = pivot.rename(columns=rename_map)

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
        return pivot.sort_values("Prioridade", ascending=False).reset_index(drop=True)[
            cols_final
        ]

    @staticmethod
    def projetar(
        df: pd.DataFrame,
        probabilidade: float = 0.30,
        grupo: str = "MONITOR",
        incluir_meta: bool = True,
        meta_sla: float = 0.20,
    ) -> pd.DataFrame:
        if (
            df is None
            or df.empty
            or grupo not in df.columns
            or "Status Contrato" not in df.columns
        ):
            return pd.DataFrame()

        pv = pd.pivot_table(
            df,
            index=grupo,
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        )

        for coluna in Config.STATUS_ORDEM:
            if coluna not in pv.columns:
                pv[coluna] = 0.0

        out = pv.reset_index()

        out["Considerado"] = (
            out["Executada"]
            + out["Não Executada"]
        )

        out["Alocado"] = (
            out["Considerado"]
            + out["Pendente"]
        )

        out["Quebra Atual"] = np.where(
            out["Considerado"] > 0,
            out["Não Executada"]
            / out["Considerado"],
            0.0,
        )

        out["Projeção Fechamento"] = np.where(
            out["Alocado"] > 0,
            (
                out["Não Executada"]
                + out["Pendente"]
                * (1 - probabilidade)
            )
            / out["Alocado"],
            0.0,
        )

        out["Executadas Projetadas"] = (
            out["Executada"]
            + out["Pendente"] * probabilidade
        )

        pendentes = out["Pendente"]

        conversao_segura = np.where(
            pendentes > 0,
            np.clip(
                (
                    out["Alocado"] * (1 - meta_sla)
                    - out["Executada"]
                )
                / pendentes,
                0.0,
                1.0,
            ),
            0.0,
        )

        # Corrigido: mesmo sem Não Executada atual,
        # pode haver conversão necessária para tratar os pendentes
        out["Conversão Necessária"] = np.where(
            (out["Alocado"] > 0)
            & (out["Pendente"] > 0),
            conversao_segura,
            0.0,
        )

        if incluir_meta:
            out["Status Meta"] = np.select(
                [
                    out["Projeção Fechamento"] <= meta_sla,
                    out["Projeção Fechamento"]
                    <= meta_sla * 1.25,
                    out["Projeção Fechamento"]
                    <= meta_sla * 1.50,
                ],
                [
                    "✅ Dentro da Meta",
                    "⚠️ Atenção",
                    "🔴 Crítico",
                ],
                default="🚨 Muito Crítico",
            )

        out = out.sort_values(
            "Projeção Fechamento",
            ascending=False,
        )

        colunas_inteiras = [
            "Executada",
            "Não Executada",
            "Pendente",
            "Considerado",
            "Alocado",
            "Executadas Projetadas",
        ]

        for coluna in colunas_inteiras:
            if coluna in out.columns:
                out[coluna] = (
                    out[coluna]
                    .fillna(0)
                    .astype(int)
                )

        return out


# ═══════════════════════════════════════════════════════════════════════
# GERADOR DE TABELA MATRIZ EXECUTIVA HTML COM METAS E FORMATACÃO
# ═══════════════════════════════════════════════════════════════════════
def render_matriz_executiva_html(
    df: pd.DataFrame,
) -> None:
    if df is None or df.empty:
        st.info("Sem dados na Matriz Executiva.")
        return

    metas_coluna = {
        "NOVOS DOMICÍLIOS": Config.SLA_QUEBRA_MAXIMA,
        "NOVOS DOMICILIOS": Config.SLA_QUEBRA_MAXIMA,
        "PME": Config.SLA_QUEBRA_MAXIMA,
        "MIGRAÇÃO": Config.SLA_MIGRACAO_MAXIMA,
        "MIGRACAO": Config.SLA_MIGRACAO_MAXIMA,
        "OUTROS": Config.SLA_QUEBRA_MAXIMA,
        "QUEBRA GERAL": Config.SLA_QUEBRA_MAXIMA,
    }

    html = """
    <div class="matriz-table-container">
    <table class="matriz-table">
    <thead>
        <tr>
    """

    for coluna in df.columns:
        html += (
            f"<th>{escape(str(coluna))}</th>"
        )

    html += """
        </tr>
    </thead>
    <tbody>
    """

    for _, row in df.iterrows():
        is_total = (
            str(row.iloc[0])
            .strip()
            .upper()
            == "TOTAL GERAL"
        )

        classe_linha = (
            "class='total-row'"
            if is_total
            else ""
        )

        html += f"<tr {classe_linha}>"

        for coluna in df.columns:
            valor = row[coluna]
            coluna_upper = (
                str(coluna)
                .strip()
                .upper()
            )

            if coluna_upper in metas_coluna:
                limite_meta = metas_coluna[coluna_upper]

                try:
                    valor_numerico = float(valor)

                    if not np.isfinite(valor_numerico):
                        html += (
                            "<td>"
                            "<span style='color:#94A3B8;"
                            "font-weight:700;'>—</span>"
                            "</td>"
                        )
                        continue

                    classe_badge = (
                        "badge-meta-ok"
                        if valor_numerico <= limite_meta
                        else "badge-meta-nok"
                    )

                    html += (
                        "<td>"
                        f"<span class='{classe_badge}'>"
                        f"{valor_numerico:.2%}"
                        "</span>"
                        "</td>"
                    )

                except (
                    ValueError,
                    TypeError,
                ):
                    html += (
                        f"<td>{escape(str(valor))}</td>"
                    )

            elif coluna_upper in {
                "TOTAL TASKS",
                "TOTAL_TASKS",
            }:
                try:
                    valor_inteiro = int(
                        float(valor)
                    )

                    valor_formatado = (
                        f"{valor_inteiro:,}"
                        .replace(",", ".")
                    )

                    html += (
                        "<td>"
                        f"<strong>{valor_formatado}</strong>"
                        "</td>"
                    )

                except (
                    ValueError,
                    TypeError,
                ):
                    html += (
                        f"<td>{escape(str(valor))}</td>"
                    )

            else:
                try:
                    if pd.isna(valor):
                        html += (
                            "<td>"
                            "<span style='color:#94A3B8;'>—</span>"
                            "</td>"
                        )
                    else:
                        html += (
                            f"<td>{escape(str(valor))}</td>"
                        )
                except (TypeError, ValueError):
                    html += (
                        f"<td>{escape(str(valor))}</td>"
                    )

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

    clicou_processar = False
    if dados_prontos:
        st.markdown(
            '<div class="import-alert-green"><span style="font-size: 16px;">✅</span><span>Dados carregados automaticamente! Pronto para processamento.</span></div>',
            unsafe_allow_html=True,
        )
        clicou_processar = st.button(
            "🚀 Processar Dados Carregados",
            type="primary",
            use_container_width=True,
            key="btn_processar_robo_central",
        )
    return clicou_processar


def html_resultado_base(regioes: list[str], total: int, origem: str = "") -> str:
    badges = "".join(
        [
            f'<span class="badge-regiao" style="background:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["bg"]};color:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["text"]};border-color:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["border"]};">{r}</span>'
            for r in sorted(regioes)
        ]
    )
    total_fmt = f"{total:,}".replace(",", ".")
    tag_origem = (
        f'<span style="color:#6EE7B7;font-size:0.78rem;font-weight:600;margin-left:8px;">• {escape(origem)}</span>'
        if origem
        else ""
    )
    return f'<div class="base-info"><span style="color:#94A3B8;font-size:0.8rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">📋 Base Ativa:</span>{badges}{tag_origem}<span style="color:#FFFFFF;font-size:0.78rem;margin-left:auto;font-weight:700;">{total_fmt} registros</span></div>'


def render_hero_topo_fixo(
    titulo: str,
    subtitulo: str,
    regioes: list[str],
    total: int,
    badge: str = "",
    origem: str = "",
) -> None:
    badge_html = (
        f'<span style="display:inline-block;background:rgba(255,255,255,0.20);padding:5px 16px;border-radius:20px;font-size:12px;font-weight:700;margin-top:10px;letter-spacing:0.6px;text-transform:uppercase;color:white;border:1px solid rgba(255,255,255,0.30);">{badge}</span>'
        if badge
        else ""
    )
    resultado_html = html_resultado_base(regioes, total, origem) if total > 0 else ""
    st.markdown(
        f'<div class="hero-container"><div class="hero-card"><div style="position:relative;z-index:2;"><h1 class="hero-title">{titulo}</h1><p class="hero-sub">{subtitulo}</p>{badge_html}</div></div>{resultado_html}</div>',
        unsafe_allow_html=True,
    )


def render_dataframe_profundo(
    df: pd.DataFrame,
    titulo: str,
    icone: str,
    color_col: str | None = None,
    meta: float = 0.20,
    height: int = 400,
) -> None:
    st.markdown(
        f'<div style="background:#FFFFFF;border-radius:0.75rem;padding:1rem 1.2rem;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:0.5rem;">'
        f'<div style="font-size:1rem;font-weight:700;color:#0F172A;display:flex;'
        f'align-items:center;gap:0.5rem;"><span>{icone}</span><span>{titulo}</span>'
        f'<span style="font-size:0.68rem;background:#E0F2FE;color:#0369A1;'
        f'padding:0.15rem 0.5rem;border-radius:999px;">{len(df)} registros</span></div></div>',
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("Sem dados para exibir.")
        return

    fmt_dict: dict[str, Any] = {}

    for col in df.columns:
        col_u = str(col).upper()
        if any(
            x in col_u
            for x in [
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
            ]
        ):
            fmt_dict[col] = "{:.2%}"
        elif any(
            x in col_u
            for x in ["TOTAL", "VOLUME", "TAREFAS", "PRIORIDADE", "EXECUTADAS", "TASKS"]
        ):
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


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD VIEWS AND LAYOUTS
# ═══════════════════════════════════════════════════════════════════════
def view_resumo_executivo(
    df: pd.DataFrame,
    meta_sla: float,
) -> None:
    coluna_tipo = df.attrs.get(
        "tipo_servico_coluna",
        "",
    )
    
    # st.dataframe(df, use_container_width=True, hide_index=False)

    tipos_processados = set()

    if "TIPO_SERVICO" in df.columns:
        tipos_processados = set(
            df["TIPO_SERVICO"]
            .dropna()
            .astype(str)
            .unique()
        )

    if not coluna_tipo:
        st.warning(
            "⚠️ A base não possui uma coluna identificável "
            "de tipo de serviço. Os registros foram classificados "
            "como 'Outros'. Inclua o nome da coluna em "
            "Config.COLUNAS_TIPO_SERVICO."
        )

    elif tipos_processados == {"Outros"}:
        valores_originais = df.attrs.get(
            "valores_tipo_servico_originais",
            {},
        )

        st.warning(
            "⚠️ A coluna de segmento foi encontrada, "
            f"mas nenhum valor foi reconhecido para "
            "Novos Domicílios, PME ou Migração. "
            "Todos os registros ficaram em 'Outros'."
        )

        if valores_originais:
            st.caption(
                "Valores originais encontrados: "
                + ", ".join(
                    list(valores_originais.keys())[:10]
                )
            )

    render_section_header(
        "📊",
        "Matriz de Quebra por Monitor e Segmento",
    )

    df_matriz = Motor.matriz_resumo(df)

    if df_matriz.empty:
        st.warning(
            "⚠️ Dados insuficientes para montar "
            "a Matriz Executiva."
        )
        return

    if "Monitor" in df_matriz.columns:
        mask_total = (
            df_matriz["Monitor"]
            .astype(str)
            .str.strip()
            .str.upper()
            .eq("TOTAL GERAL")
        )

        if mask_total.any():
            df_total = df_matriz.loc[
                mask_total
            ].copy()

            df_resto = df_matriz.loc[
                ~mask_total
            ].copy()

            df_matriz = pd.concat(
                [
                    df_resto,
                    df_total,
                ],
                ignore_index=True,
            )

    render_matriz_executiva_html(df_matriz)

    st.download_button(
        "📥 Baixar Matriz (Excel)",
        data=Utils.gerar_excel(
            df_matriz,
            "Matriz_Resumo",
        ),
        file_name="Matriz_Resumo_Quebra.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
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
        render_section_header("📈", "Cenários de Projeção de Fechamento")
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
        render_section_header("🎯", "Projeção Customizada")
        col1, col2 = st.columns(2)
        with col1:
            prob_custom = (
                st.slider("Probabilidade de Conversão (%)", 0, 100, 30, step=5) / 100.0
            )
        with col2:
            grupo_proj = st.selectbox("Agrupar por", ["MONITOR", "TÉCNICO", "REGIÃO"])

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
            dentro_meta = int((df_proj["Projeção Fechamento"] <= meta_sla).sum())
            atencao = int(
                (
                    (df_proj["Projeção Fechamento"] > meta_sla)
                    & (df_proj["Projeção Fechamento"] <= meta_sla * 1.25)
                ).sum()
            )
            critico = int((df_proj["Projeção Fechamento"] > meta_sla * 1.25).sum())
            conversao_media = df_proj["Conversão Necessária"].mean()

            render_kpi_sm(
                k1,
                "Dentro da Meta",
                f"{dentro_meta}",
                f"{dentro_meta/len(df_proj)*100:.0f}%",
                "verde",
            )
            render_kpi_sm(
                k2,
                "Atenção",
                f"{atencao}",
                f"{atencao/len(df_proj)*100:.0f}%",
                "amarelo",
            )
            render_kpi_sm(
                k3,
                "Crítico",
                f"{critico}",
                f"{critico/len(df_proj)*100:.0f}%",
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
        render_section_header("🏆", "Técnicos Mais Críticos")
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
        render_section_header("🔍", "Análise de Causa Raiz")
        col_baixa = Utils.buscar_coluna(
            df, ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "MOTIVO DE BAIXA", "COD_BAIXA"]
        )
        if col_baixa:
            df_causa = Motor.causa_raiz(df, col_baixa, top_n=10)
            render_dataframe_profundo(df_causa, "Pareto de Motivos", "🎯")
        else:
            st.warning(
                "⚠️ Coluna de 'Código de Baixa' não encontrada para mapear Pareto."
            )

    with tab5:
        render_section_header("🛠️", "Gestão de Fila (Backoffice)")
        df_fila = Motor.backoffice_fila(df)
        render_dataframe_profundo(df_fila, "Fila Priorizada", "📋")


# ═══════════════════════════════════════════════════════════════════════
# FLUXO PRINCIPAL DE INICIALIZAÇÃO E EVENTOS
# ═══════════════════════════════════════════════════════════════════════
def main() -> None:
    _injetar_css_global()

    render_sidebar_brand(
        titulo="TOTALE",
        subtitulo="Quebra Operacional",
        logo="monitoring",
        ambiente="produção",
        versao="v4.2.1",
        mostrar_data=True,
    )

    df_ativos_atv = pd.DataFrame()

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
                if not df_ativos_proc.empty:
                    st.session_state["df_gs_manual"] = df_ativos_proc
                    st.toast(
                        f"✅ {len(df_ativos_proc)} ativos carregados manualmente!",
                        icon="👥",
                    )
                    if "df_memoria_raw" in st.session_state:
                        st.session_state["df_memoria"] = DataLoader.preparar_base(
                            st.session_state["df_memoria_raw"], df_ativos_proc
                        )
                else:
                    st.error("Arquivo de ativos inválido ou vazio.")
            except Exception as e:
                st.error(f"Erro no processamento manual: {e}")

        if st.button(
            "🔄 Reiniciar Aplicação", use_container_width=True, type="secondary"
        ):
            st.rerun()
        if st.button("🗑️ Limpar Cache", use_container_width=True, type="secondary"):
            st.cache_data.clear()
            if "df_gs_manual" in st.session_state:
                del st.session_state["df_gs_manual"]
            st.success("Cache limpo com sucesso!")
            st.rerun()

    if "df_gs_manual" in st.session_state:
        df_ativos_atv = st.session_state["df_gs_manual"]
        origem_ativos = "Carregado Manualmente (Backup)"
    else:
        df_ativos_atv = DataLoader.buscar_gsheets()
        origem_ativos = "Google Sheets (Sincronizado)"

    if not df_ativos_atv.empty:
        st.sidebar.caption(
            f"👥 **Base de Ativos Ativa:** {len(df_ativos_atv)} registros"
        )
        st.sidebar.caption(f"📍 *Origem: {origem_ativos}*")
    else:
        st.sidebar.error("🚨 Nenhuma base de ativos de técnicos conectada!")

    if "robo_pasta_alvo" not in st.session_state:
        st.session_state["robo_pasta_alvo"] = str(Path.home() / "Downloads")

    st.sidebar.markdown("---")
    if ROBO_DISPONIVEL and _impl_robo is not None:
        try:

            def callback_robo_com_ativos(
                df_raw: pd.DataFrame,
                df_gs_arg: pd.DataFrame | None = None,
                *args: Any,
                **kwargs: Any,
            ) -> pd.DataFrame:
                df_gs_final = (
                    df_gs_arg
                    if isinstance(df_gs_arg, pd.DataFrame) and not df_gs_arg.empty
                    else df_ativos_atv
                )
                return DataLoader.callback_robo_etl(df_raw, df_gs_final)

            _impl_robo(
                etl_fn=callback_robo_com_ativos,
                gsheets_fn=lambda: df_ativos_atv,
                pasta_padrao=st.session_state["robo_pasta_alvo"],
                ciclos_estabilidade=1,
                mostrar_toggle=True,
                mostrar_config=True,
            )
        except Exception as e:
            st.sidebar.error(f"Erro Robô: {e}")
    else:
        st.sidebar.info("🤖 Robô offline. Use upload manual.")
        pasta_fb = st.sidebar.text_input(
            "Pasta monitorada",
            value=st.session_state["robo_pasta_alvo"],
            key="robo_pasta_fallback",
        )
        st.session_state["robo_pasta_alvo"] = pasta_fb

    df_atual: pd.DataFrame | None = st.session_state.get("df_memoria")
    robo_tem_dados = bool(
        st.session_state.get("_robo_dados_disponiveis", False)
        or (df_atual is not None and not df_atual.empty)
    )

    clicou_processar = render_bloco_importacao_robo(dados_prontos=robo_tem_dados)

    if clicou_processar:
        with st.spinner("Processando base detectada..."):
            st.success("✅ Base processada com sucesso!", icon="🚀")
            st.rerun()

    uploaded_file = None
    if not robo_tem_dados:
        uploaded_file = st.file_uploader(
            "⬇️ Carregar base de O.S. manualmente (CSV/XLSX)",
            type=["csv", "xlsx"],
            help="O Robô monitora a pasta local. Use aqui se estiver offline.",
        )
    else:
        with st.expander("📂 Substituir base de O.S. manualmente", expanded=False):
            uploaded_file = st.file_uploader(
                "Upload Manual O.S.",
                type=["csv", "xlsx"],
                key="upload_contingencia_manual",
            )

    if uploaded_file is not None:
        file_id = (uploaded_file.name, uploaded_file.size)
        if st.session_state.get("arquivo_processado") != file_id:
            with st.spinner(f"Processando {uploaded_file.name}..."):
                try:
                    raw_df = DataLoader.ler_arquivo(
                        uploaded_file.getvalue(), uploaded_file.name
                    )
                    st.session_state["df_memoria_raw"] = raw_df
                    st.session_state["df_memoria"] = DataLoader.preparar_base(
                        raw_df, df_ativos_atv, filename=uploaded_file.name
                    )
                    st.session_state["arquivo_processado"] = file_id
                    st.session_state["origem_dados"] = f"Upload ({uploaded_file.name})"
                    st.session_state["_robo_dados_disponiveis"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro: {e}")
                    return

    df: pd.DataFrame | None = st.session_state.get("df_memoria")
    if df is None or df.empty:
        return

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<div style='font-size:12px; font-weight:700; color:#64748B; text-transform:uppercase;'>🎯 Filtros de Projeção</div>",
        unsafe_allow_html=True,
    )
    p_ot = st.sidebar.slider("Prob. Otimista (%)", 0, 100, 15, step=5) / 100.0
    p_base = st.sidebar.slider("Prob. Base (%)", 0, 100, 30, step=5) / 100.0
    p_pess = st.sidebar.slider("Prob. Pessimista (%)", 0, 100, 50, step=5) / 100.0
    min_aloc = float(st.sidebar.number_input("Mínimo Alocações", value=5, min_value=1))

    regioes_sel = (
        sorted(df["REGIÃO"].dropna().unique().tolist())
        if "REGIÃO" in df.columns
        else []
    )
    origem_base = st.session_state.get("origem_dados", "Base Carregada")

    render_hero_topo_fixo(
        "Super Relatório Corporativo",
        "Análise unificada de desempenho operacional",
        regioes_sel if regioes_sel else ["TODAS"],
        len(df),
        badge="TOTALE OPERACIONAL",
        origem=origem_base,
    )

    total_os = len(df)
    nao_mapeados = int((df["TÉCNICO"] == "NÃO MAPEADO").sum())
    pct_mapeado = ((total_os - nao_mapeados) / total_os) if total_os > 0 else 0.0

    if nao_mapeados > 0:
        st.warning(
            f"⚠️ **Aviso de Integração:** {nao_mapeados} O.S. ({1 - pct_mapeado:.1%} do volume ativo) não encontraram correspondência "
            "na Lista de Ativos instalada e estão listados como 'NÃO MAPEADO'."
        )
    else:
        st.success(
            "🎉 **Perfeito!** Todos os logins estão mapeados na Lista de Ativos com sucesso."
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
    elif aba == "Auditoria":
        st.info("Painel de auditoria e logs disponível em módulos avançados.")
        
st.divider()


if __name__ == "__main__":
    main()