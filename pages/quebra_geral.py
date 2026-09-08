"""
quebra.py
=========
Super Relatório Corporativo Unificado | Quebra Operacional TOTALE
Versão Final: ETL Robusto + Integração de Robô via Callback Reativo
"""

from __future__ import annotations

import csv
import os
import re
import sys
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, cast, TypedDict, Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ─ Path bootstrap ──────────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_ROOT = _DIR.parent
for _p in (_DIR, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── Componentes visuais globais ─────────────────────────────────────
from components.componentes import (
    FONTE_TEXTO,
    FONTE_TITULO,
    aplicar_estilo,
    render_section_header,
    render_sidebar_brand,
    render_sidebar_status,
    render_table_html,
)
from components.componentes import render_insight as _render_insight_global
from components.componentes import render_kpi as _render_kpi_global
from components.componentes import render_kpi_sm as _render_kpi_sm_global

# ── Robô de Sincronismo Local ───────────────────────────────────────
import importlib
import traceback

ROBO_DISPONIVEL: bool = False
_impl_robo: Optional[Callable[..., None]] = None
_ROBO_IMPORT_ERRO: str = ""


def _tentar_import_robo() -> Any:
    """Importa renderizar_robo_local do pacote robo."""
    _here = Path(__file__).resolve().parent
    for extra in (_here, _here.parent):
        s = str(extra)
        if s not in sys.path:
            sys.path.insert(0, s)

    # 1) Pacote oficial
    try:
        from robo.robo_local import renderizar_robo_local as fn  # type: ignore
        import robo.robo_local as mod  # type: ignore

        return fn, f"OK via robo.robo_local ({getattr(mod, '__file__', '?')})"
    except Exception as e1:
        err1 = f"robo.robo_local: {type(e1).__name__}: {e1}"

    # 2) Fallback: função com outro nome no mesmo módulo
    try:
        import robo.robo_local as mod  # type: ignore

        for nome in (
            "renderizar_robo_local",
            "renderizar_sidebar_robo",
            "render_robo_local",
        ):
            fn = getattr(mod, nome, None)
            if callable(fn):
                return fn, f"OK via robo.robo_local.{nome} ({mod.__file__})"
        return None, f"{err1} | módulo carregou mas sem função de render"
    except Exception as e2:
        return None, f"{err1} | retry: {type(e2).__name__}: {e2}"

_impl_robo, _ROBO_IMPORT_ERRO = _tentar_import_robo()
ROBO_DISPONIVEL = _impl_robo is not None


def renderizar_robo_local(*args: Any, **kwargs: Any) -> None:
    if _impl_robo is not None:
        _impl_robo(*args, **kwargs)
        return
    st.sidebar.error("❌ Robô não importou")
    st.sidebar.code(_ROBO_IMPORT_ERRO)


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DO ROBÔ (Integrado)
# ═══════════════════════════════════════════════════════════════════════
class PaginaConfig(TypedDict, total=False):
    titulo: str
    subtitulo: str
    pasta: Optional[str]
    etl_fn: Optional[Callable[..., Any]]
    colunas: Optional[List[str]]
    ativo_padrao: bool
    sheet_name: int | str


class ConfigRobo:
    """Configurações centralizadas do robô auto-sincronizador."""

    PASTA_PADRAO: Optional[str] = None
    TEMPO_VERIFICACAO_SEGUNDOS: int = 1   # Sincronização imediata (1 segundo)
    CICLOS_ESTABILIDADE: int = 1          # Estabilidade imediata (1 ciclo)

    COLUNAS_ROTA: List[str] = [
        "CONTRATO",
        "STATUS DA O.S 1",
        "TÉCNICO",
        "TOTAL DE TAREFAS",
    ]


# ── Critérios centralizados ───────────────────────────────────────
try:
    from components.criterios import (
        VAZIOS_CONTRATO,
        classificar_tipo_servico,
        detectar_col_contrato,
        detectar_col_status_atividade,
        render_debug_criterios,
        render_painel_criterios,
    )
except ImportError:
    VAZIOS_CONTRATO = {"", "NAN", "NONE", "N/A", "NA", "-", "0", "NULL"}

    def classificar_tipo_servico(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        df = df.copy()
        df["TIPO_SERVICO"] = "Outros"
        return df, df["TIPO_SERVICO"]

    def detectar_col_contrato(df: pd.DataFrame) -> Optional[str]:
        return str("CONTRATO") if "CONTRATO" in df.columns else None

    def detectar_col_status_atividade(df: pd.DataFrame) -> Optional[str]:
        return (
            str("STATUS DA ATIVIDADE") if "STATUS DA ATIVIDADE" in df.columns else None
        )

    def render_debug_criterios(df_full: pd.DataFrame, expanded: bool = False) -> None:
        st.info("Debug de critérios indisponível.")

    def render_painel_criterios(df: pd.DataFrame) -> None:
        st.info("Painel de critérios indisponível.")


TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]
TemaKPI = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo", "amarelo", "escuro"
]

# ═════════════════════════════════════════════════════════════════════
# MAPEAMENTO DE DEPARA (CÓD DE BAIXA 1)
# ══════════════════════════════════════════════════════════════════════
MAPA_CODIGO_NUMERICO: Dict[int, str] = {
    100: "Não Executada",
    101: "Não Executada",
    103: "Não Executada",
    104: "Não Executada",
    105: "Não Executada",
    106: "Não Executada",
    107: "Não Executada",
    108: "Não Executada",
    110: "Não Executada",
    112: "Não Executada",
    113: "Não Executada",
    114: "Não Executada",
    125: "Não Executada",
    203: "Não Executada",
    204: "Não Executada",
    205: "Não Executada",
    206: "Não Executada",
    301: "Não Executada",
    302: "Não Executada",
    303: "Não Executada",
    305: "Não Executada",
    306: "Não Executada",
    307: "Não Executada",
    308: "Não Executada",
    312: "Não Executada",
    316: "Não Executada",
    400: "Não Executada",
    402: "Não Executada",
    128: "Executada",
    328: "Executada",
    408: "Executada",
    409: "Executada",
    425: "Executada",
    430: "Executada",
    440: "Executada",
    467: "Executada",
    470: "Executada",
    474: "Executada",
    475: "Executada",
    477: "Executada",
    500: "Executada",
    501: "Executada",
    502: "Executada",
    505: "Executada",
    506: "Executada",
    507: "Executada",
    509: "Executada",
    510: "Executada",
    514: "Executada",
    515: "Executada",
    516: "Executada",
    517: "Executada",
    518: "Executada",
    519: "Executada",
    520: "Executada",
    521: "Executada",
    522: "Executada",
    523: "Executada",
    524: "Executada",
    525: "Executada",
    526: "Executada",
    527: "Executada",
    530: "Executada",
    533: "Executada",
    534: "Executada",
    535: "Executada",
    536: "Executada",
    537: "Executada",
    538: "Executada",
    539: "Executada",
    540: "Executada",
    541: "Executada",
    542: "Executada",
    544: "Executada",
    545: "Executada",
    546: "Executada",
    547: "Executada",
    549: "Executada",
    551: "Executada",
    552: "Executada",
    553: "Executada",
    554: "Executada",
    555: "Executada",
    556: "Executada",
    557: "Executada",
    558: "Executada",
    560: "Executada",
    562: "Executada",
    563: "Executada",
    564: "Executada",
    565: "Executada",
    566: "Executada",
    567: "Executada",
    568: "Executada",
    569: "Executada",
    570: "Executada",
    574: "Executada",
    575: "Executada",
    580: "Executada",
    582: "Executada",
    584: "Executada",
    590: "Executada",
}

MAPA_COD_BAIXA_TEXTO: Dict[str, str] = {
    "EM ROTA": "Pendente",
    "INICIADO": "Pendente",
    "PENDENTE": "Pendente",
}


# ══════════════════════════════════════════════════════════════════════
# CONSTANTES DE DOMÍNIO
# ═══════════════════════════════════════════════════════════════════════
class Config:
    SLA_QUEBRA_MAXIMA = 0.20
    URL_LISTA_ATIVOS = (
        "https://docs.google.com/spreadsheets/d/"
        "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    )
    SHEET_ID_ATIVOS = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    WORKSHEET_ATIVOS = "lista_ativos"
    CONTRATO_VALORES_VAZIOS = VAZIOS_CONTRATO
    STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]
    CORES_STATUS = {
        "Executada": "#10B981",
        "Não Executada": "#EF4444",
        "Pendente": "#94A3B8",
    }
    COL_REGIAO = "REGIÃO"
    CORES_TIPO = {
        "Novos Domicílios": "#1E40AF",
        "PME": "#7C3AED",
        "Migração": "#0369A1",
        "Quebra Geral": "#78350F",
        "Outros": "#64748B",
    }
    ORDEM_TIPOS = ["Novos Domicílios", "PME", "Migração", "Outros"]


CORES_REGIAO: Dict[str, Dict[str, str]] = {
    "LESTE": {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU": {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM": {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

TEMAS_CARD_EXTRA: Dict[str, Dict[str, str]] = {
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

_MAPA_TEMA_GLOBAL: Any[str, str] = {
    "azul": "azul",
    "verde": "verde",
    "vermelho": "vermelho",
    "laranja": "laranja",
    "cinza": "cinza",
    "roxo": "roxo",
    "amarelo": "amarelo",
    "escuro": "escuro",
}


# ═══════════════════════════════════════════════════════════════════════
# WRAPPERS DE INTERFACE (UI)
# ═══════════════════════════════════════════════════════════════════════
def render_kpi(
    col: Any, label: str, value: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    if tema in TEMAS_CARD_EXTRA:
        t = TEMAS_CARD_EXTRA[tema]
        col.markdown(
            f'<div style="background:{t["fundo"]};border-left:4px solid {t["borda"]};'
            f'border-radius:10px;padding:20px 24px;box-shadow:0 4px 12px rgba(0,0,0,0.08);">'
            f'<div style="font-family:{FONTE_TEXTO};font-size:11px;font-weight:700;'
            f'color:{t["titulo"]};text-transform:uppercase;letter-spacing:1.2px;'
            f'margin-bottom:6px;">{label}</div>'
            f'<div style="font-family:{FONTE_TITULO};font-size:28px;font-weight:800;'
            f'color:{t["texto"]};line-height:1;font-variant-numeric:tabular-nums;">{value}</div>'
            f'<div style="font-family:{FONTE_TEXTO};font-size:12px;color:{t["titulo"]};'
            f'margin-top:6px;font-weight:500;">{sub}</div></div>',
            unsafe_allow_html=True,
        )
    else:
        _render_kpi_global(col, label, value, sub, _MAPA_TEMA_GLOBAL.get(tema, "azul"))


def render_kpi_sm(
    col: Any, label: str, value: str, sub: str = "", tema: TemaKPI = "azul"
) -> None:
    if tema in TEMAS_CARD_EXTRA:
        t = TEMAS_CARD_EXTRA[tema]
        col.markdown(
            f'<div style="background:{t["fundo"]};border-left:3px solid {t["borda"]};'
            f"border-radius:6px;padding:12px 16px;margin-bottom:8px;"
            f'box-shadow:0 1px 4px rgba(0,0,0,0.06);">'
            f'<div style="font-family:{FONTE_TEXTO};font-size:10px;color:{t["titulo"]};'
            f'text-transform:uppercase;letter-spacing:1px;font-weight:700;">{label}</div>'
            f'<div style="font-family:{FONTE_TITULO};font-size:20px;color:{t["texto"]};'
            f"font-weight:800;line-height:1.2;margin-top:4px;"
            f'font-variant-numeric:tabular-nums;">{value}</div>'
            f'<div style="font-family:{FONTE_TEXTO};font-size:11px;color:{t["titulo"]};'
            f'margin-top:2px;">{sub}</div></div>',
            unsafe_allow_html=True,
        )
    else:
        _render_kpi_sm_global(
            col, label, value, sub, _MAPA_TEMA_GLOBAL.get(tema, "azul")
        )


def render_insight(texto: str, tipo: TipoInsight = "info") -> None:
    _render_insight_global(texto, tipo)


def render_section(titulo: str) -> None:
    partes = titulo.strip().split(" ", 1)
    primeiro_char = partes[0][0] if partes[0] else ""
    if len(partes) == 2 and not primeiro_char.isascii():
        icon, title = partes[0], partes[1]
    else:
        icon, title = "", titulo
    render_section_header(icon, title)


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
# ══════════════════════════════════════════════════════════════════════
class Utils:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras: list) -> Optional[str]:
        if df is None or df.empty:
            return None

        def normalizar(s: str) -> str:
            s = str(s).upper().strip()
            s = re.sub(r"[ÁÀÂÃÄ]", "A", s)
            s = re.sub(r"[ÉÈÊË]", "E", s)
            s = re.sub(r"[ÍÌÎÏ]", "I", s)
            s = re.sub(r"[ÓÒÔÕÖ]", "O", s)
            s = re.sub(r"[ÚÙÜ]", "U", s)
            s = re.sub(r"[Ç]", "C", s)
            s = re.sub(r"[^A-Z0-9]", "", s)
            return s

        cols_norm = {normalizar(c): c for c in df.columns}
        for p in palavras:
            pn = normalizar(p)
            if pn in cols_norm:
                return cols_norm[pn]
            for cn, co in cols_norm.items():
                if pn in cn or cn in pn:
                    return co
        return None

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
                "INICIO DA ATIVIDADE",
            ],
        )
        col_fechamento_ext = Utils.buscar_coluna(
            df,
            [
                "MOTIVO DE FECHAMENTO EXTERNO",
                "MOTIVO FECHAMENTO EXTERNO",
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
                "STATUS ATIVIDADE 1",
            ],
        )
        col_cod_baixa = Utils.buscar_coluna(
            df,
            [
                "CÓD DE BAIXA 1",
                "COD DE BAIXA 1",
                "CÓD. DE BAIXA 1",
                "CÓD.BAIXA",
                "COD.BAIXA",
                "COD BAIXA",
                "MOTIVO DE BAIXA",
            ],
        )
        col_status_os = Utils.buscar_coluna(
            df, ["STATUS DA O.S 1", "STATUS OS 1", "STATUS CONTRATO", "STATUS DA OS"]
        )

        s_inicio = (
            df[col_inicio].fillna("").astype(str).str.strip()
            if col_inicio
            else pd.Series("", index=df.index)
        )
        s_fechamento = (
            df[col_fechamento_ext].fillna("").astype(str).str.strip().str.upper()
            if col_fechamento_ext
            else pd.Series("", index=df.index)
        )
        s_status_atv = (
            df[col_status_atv].fillna("").astype(str).str.strip().str.lower()
            if col_status_atv
            else pd.Series("", index=df.index)
        )
        s_cod_baixa = (
            df[col_cod_baixa].fillna("").astype(str).str.strip()
            if col_cod_baixa
            else pd.Series("", index=df.index)
        )

        fechamento_alvo = ["LIBERADO NO SISTEMA NETSMS", "CANCELADO NO SISTEMA NETSMS"]
        cond_f2 = s_fechamento.isin(fechamento_alvo)
        inicio_vazio = s_inicio.isin(["", "NAN", "NONE", "NULL", "NAT", "NA"])

        cond1 = inicio_vazio & cond_f2
        cond2 = (~inicio_vazio) & cond_f2
        cond3 = s_status_atv.eq("cancelado")
        cond4 = s_status_atv.isin(["suspenso", "suspensa"])
        cond5 = s_status_atv.isin(
            ["não concluído", "nao concluido", "não concluida", "nao concluida"]
        )

        def traduzir_cod_baixa(val: str) -> str:
            if not val or str(val).strip().upper() in ["NAN", "NONE", "NULL", ""]:
                return "Pendente"
            val_upper = str(val).strip().upper()
            if val_upper in MAPA_COD_BAIXA_TEXTO:
                return MAPA_COD_BAIXA_TEXTO[val_upper]
            match = re.match(r"^(\d+)", val_upper)
            if match:
                cod_num = int(match.group(1))
                if cod_num in MAPA_CODIGO_NUMERICO:
                    return MAPA_CODIGO_NUMERICO[cod_num]
            return "Pendente"

        status_procv = s_cod_baixa.apply(traduzir_cod_baixa)
        condicoes = [cond1, cond2, cond3, cond4, cond5]
        resultados = [
            "Cancelado",
            "Não Executada",
            "Cancelado",
            "Suspenso",
            "Não Executada",
        ]

        if (
            not any([col_inicio, col_fechamento_ext, col_status_atv, col_cod_baixa])
            and col_status_os
        ):
            s = df[col_status_os].fillna("").astype(str).str.strip().str.upper()
            exe = s.eq("EXECUTADA")
            nex = s.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])
            return pd.Series(
                np.select(
                    [exe, nex], ["Executada", "Não Executada"], default="Pendente"
                ),
                index=df.index,
            )

        return pd.Series(
            np.select(condicoes, resultados, default=status_procv), index=df.index
        )

    @staticmethod
    def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=aba[:31])
            ws = w.sheets[aba[:31]]
            ws.views.sheetView[0].showGridLines = True
            header_fill = PatternFill("solid", fgColor="0F172A")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            border_thin = Side(border_style="thin", color="CBD5E1")
            cell_border = Border(
                left=border_thin, right=border_thin, top=border_thin, bottom=border_thin
            )
            align_center = Alignment(horizontal="center", vertical="center")
            align_left = Alignment(horizontal="left", vertical="center")

            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = align_center

            for row in range(2, ws.max_row + 1):
                for col in range(1, ws.max_column + 1):
                    cell = ws.cell(row=row, column=col)
                    cell.border = cell_border
                    val = cell.value
                    col_name = str(ws.cell(1, col).value).upper()
                    try:
                        if val is not None and str(val).strip() != "":
                            if (
                                "%" in col_name
                                or "QUEBRA" in col_name
                                or "TAXA" in col_name
                            ):
                                cell.value = (
                                    float(
                                        str(val)
                                        .replace("%", "")
                                        .replace(",", ".")
                                        .strip()
                                    )
                                    / 100.0
                                )
                                cell.number_format = "0.0%"
                            elif col_name in [
                                "VOLUME",
                                "ALOCADO",
                                "EXECUTADA",
                                "NÃO EXECUTADA",
                                "PENDENTE",
                                "TOTAL DE TAREFAS",
                                "TOTAL TAREFAS",
                            ]:
                                cell.value = int(
                                    float(
                                        str(val)
                                        .replace(".", "")
                                        .replace(",", ".")
                                        .strip()
                                    )
                                )
                                cell.number_format = "#,##0"
                    except Exception:
                        pass
                    if isinstance(cell.value, (int, float)):
                        cell.alignment = align_center
                    else:
                        cell.alignment = align_left

            for i, col in enumerate(df.columns, 1):
                try:
                    serie_str = df[col].fillna("").astype(str)
                    tamanhos = serie_str.str.len()
                    max_len_dados = int(tamanhos.max()) if len(tamanhos) > 0 else 0
                    max_len = max(max_len_dados, len(str(col)))
                    ws.column_dimensions[get_column_letter(i)].width = min(
                        max(max_len + 3, 12), 40
                    )
                except Exception:
                    ws.column_dimensions[get_column_letter(i)].width = 20
        return out.getvalue()


# ═══════════════════════════════════════════════════════════════════════
# CARREGAMENTO E SANEAMENTO DE DADOS (ETL)
# ═══════════════════════════════════════════════════════════════════════
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
                try:
                    sep = csv.Sniffer().sniff(amostra).delimiter if amostra else ";"
                except Exception:
                    sep = ";"
                return pd.read_csv(
                    bio, sep=sep, encoding="utf-8", dtype=str, engine="python"
                )
            return pd.read_excel(bio, engine="openpyxl", dtype=str)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(
        ttl=600, show_spinner=" Conectando com Google Sheets (lista_ativos)..."
    )
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
        for url in (
            f"https://docs.google.com/spreadsheets/d/{Config.SHEET_ID_ATIVOS}/gviz/tq?tqx=out:csv&sheet={Config.WORKSHEET_ATIVOS}",
            f"https://docs.google.com/spreadsheets/d/{Config.SHEET_ID_ATIVOS}/export?format=csv&gid=0",
        ):
            try:
                raw = pd.read_csv(url)
                if raw is not None and not raw.empty:
                    return DataLoader._processar_lista_ativos(raw)
            except Exception:
                continue
        return pd.DataFrame()

    @staticmethod
    def _processar_lista_ativos(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        raw.columns = raw.columns.astype(str).str.strip()
        rename_map = {}
        for col in raw.columns:
            col_upper = col.upper().strip()
            if col_upper in ("LOGIN", "MATRÍCULA", "MATRICULA", "ID"):
                rename_map[col] = "Login"
            elif col_upper in ("TÉCNICO", "TECNICO", "NOME", "NOME TÉCNICO"):
                rename_map[col] = "Técnico"
            elif col_upper in ("MONITOR", "GESTOR", "SUPERVISOR"):
                rename_map[col] = "Monitor"
            elif col_upper in ("BASE", "REGIÃO", "REGIAO"):
                rename_map[col] = "Base"
        raw = raw.rename(columns=rename_map)
        cols_uteis = [
            c for c in ["Login", "Técnico", "Monitor", "Base"] if c in raw.columns
        ]
        if "Login" not in cols_uteis:
            return pd.DataFrame()
        raw = raw[cols_uteis].copy()
        raw["Login"] = (
            raw["Login"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
            .str.upper()
        )
        raw = raw[raw["Login"].str.strip() != ""]
        raw = raw[~raw["Login"].isin(["NAN", "NONE", "NULL", "N/A"])]
        return raw.drop_duplicates(subset=["Login"], keep="last").reset_index(drop=True)

    @staticmethod
    def preparar_base(
        df: pd.DataFrame, df_gs: pd.DataFrame, filename: str = ""
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        # 1. Normalizar TODAS as colunas para UPPERCASE
        df.columns = df.columns.astype(str).str.strip().str.upper()
        df.attrs["total_importado"] = len(df)

        # 2. Status Contrato
        df["STATUS CONTRATO"] = Utils.classificar_status_excel(df)

        # 3. Remoção de Cancelados e Suspensos
        col_atv = detectar_col_status_atividade(df)
        n_susp = int(df["STATUS CONTRATO"].isin(["SUSPENSO", "CANCELADO"]).sum())
        df = df[~df["STATUS CONTRATO"].isin(["SUSPENSO", "CANCELADO"])].copy()
        df = df.reset_index(drop=True)
        df.attrs["col_status_atividade"] = col_atv
        df.attrs["removidos_suspensos"] = n_susp

        # 4. Eliminar Contratos Inválidos
        col_con = detectar_col_contrato(df)
        n_invalidos = 0
        if col_con:
            serie_con = (
                df[col_con]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
                .str.replace(r"\.0$", "", regex=True)
            )
            mask_invalido = serie_con.isin(VAZIOS_CONTRATO)
            n_invalidos = int(mask_invalido.sum())
            df = df[~mask_invalido].copy()
        df.attrs["col_contrato"] = col_con
        df.attrs["removidos_contrato"] = n_invalidos

        if df.empty:
            return pd.DataFrame()

        # 5. Total de Tarefas
        col_tot = Utils.buscar_coluna(
            df, ["TOTAL DE TAREFAS", "QTD TAREFAS", "QUANTIDADE", "VOLUME"]
        )
        if col_tot:
            s_num = (
                pd.to_numeric(
                    df[col_tot].astype(str).str.replace(",", "."), errors="coerce"
                )
                .fillna(1)
                .round()
            )
            df["TOTAL DE TAREFAS"] = s_num.astype("int64")
        else:
            df["TOTAL DE TAREFAS"] = pd.Series(1, index=df.index, dtype="int64")

        # 6. Técnicos e Monitores
        col_login = Utils.buscar_coluna(
            df,
            ["LOGIN DO TÉCNICO", "LOGIN DO TECNICO", "LOGIN", "USUÁRIO", "MATRÍCULA"],
        )
        col_tec_orig = Utils.buscar_coluna(
            df, ["TECNICO", "NOME TECNICO", "NOME DO TECNICO", "TÉCNICO"]
        )
        col_mon_orig = Utils.buscar_coluna(
            df, ["MONITOR", "GESTOR", "SUPERVISOR", "NOME MONITOR"]
        )

        s_tec_backup = (
            df[col_tec_orig].fillna("NÃO MAPEADO")
            if col_tec_orig and col_tec_orig in df.columns
            else pd.Series("NÃO MAPEADO", index=df.index)
        )
        s_mon_backup = (
            df[col_mon_orig].fillna("SEM MONITOR")
            if col_mon_orig and col_mon_orig in df.columns
            else pd.Series("SEM MONITOR", index=df.index)
        )

        df.attrs["merge_aplicado"] = False
        
        # Garante que as colunas do GSheets fiquem em UPPERCASE
        if df_gs is not None and not df_gs.empty:
            df_gs = df_gs.copy()
            df_gs.columns = df_gs.columns.astype(str).str.strip().str.upper()

        if (
            col_login
            and col_login in df.columns
            and df_gs is not None
            and not df_gs.empty
            and "LOGIN" in df_gs.columns
        ):
            df[col_login] = (
                df[col_login]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
                .str.upper()
            )
            df_gs_unico = df_gs.drop_duplicates(subset=["LOGIN"], keep="last").copy()
            
            if "TÉCNICO" in df_gs_unico.columns:
                df_gs_unico = df_gs_unico.rename(columns={"TÉCNICO": "TÉCNICO_GS"})
            if "MONITOR" in df_gs_unico.columns:
                df_gs_unico = df_gs_unico.rename(columns={"MONITOR": "MONITOR_GS"})

            df = df.merge(df_gs_unico, left_on=col_login, right_on="LOGIN", how="left")
            df.attrs["merge_aplicado"] = True

        # Prioriza colunas vindas do GSheets, caindo de volta para a base ou backup
        if "TÉCNICO_GS" in df.columns:
            df["TÉCNICO"] = df["TÉCNICO_GS"].fillna(s_tec_backup)
        elif "TÉCNICO" in df.columns:
            df["TÉCNICO"] = df["TÉCNICO"].fillna(s_tec_backup)
        elif col_tec_orig and col_tec_orig in df.columns:
            df["TÉCNICO"] = df[col_tec_orig].fillna("NÃO MAPEADO")
        else:
            df["TÉCNICO"] = "NÃO MAPEADO"

        if "MONITOR_GS" in df.columns:
            df["MONITOR"] = df["MONITOR_GS"].fillna(s_mon_backup)
        elif "MONITOR" in df.columns:
            df["MONITOR"] = df["MONITOR"].fillna(s_mon_backup)
        elif col_mon_orig and col_mon_orig in df.columns:
            df["MONITOR"] = df[col_mon_orig].fillna("SEM MONITOR")
        else:
            df["MONITOR"] = "SEM MONITOR"

        # Padronização e sanitização final de strings
        df["TÉCNICO"] = df["TÉCNICO"].astype(str).str.strip().str.upper()
        df["MONITOR"] = df["MONITOR"].astype(str).str.strip().str.upper()

        df.loc[df["TÉCNICO"].isin(["", "NAN", "NONE", "NULL"]), "TÉCNICO"] = "NÃO MAPEADO"
        df.loc[df["MONITOR"].isin(["", "NAN", "NONE", "NULL"]), "MONITOR"] = "SEM MONITOR"

        # Limpeza de colunas auxiliares do merge
        df = df.drop(columns=["TÉCNICO_GS", "MONITOR_GS", "BASE_GS"], errors="ignore")

        # 7. Regiões (TUDO EM UPPERCASE)
        col_cid = Utils.buscar_coluna(df, ["CIDADE", "LOCALIDADE", "MUNICÍPIO", "CITY"])
        col_reg_existente = Utils.buscar_coluna(
            df, ["REGIÃO", "REGIAO", "BASE", "FILIAL"]
        )

        regiao_detectada = None
        if filename:
            fname = filename.upper()
            if "ABCDM" in fname or "SBC" in fname:
                regiao_detectada = "ABCDM"
            elif "GRU" in fname or "GUARULHOS" in fname:
                regiao_detectada = "GRU"
            elif "LESTE" in fname or "SP" in fname:
                regiao_detectada = "LESTE"

        if col_cid and col_cid in df.columns:
            cidade = df[col_cid].fillna("").astype(str).str.strip().str.upper()
            df["REGIÃO"] = np.select(
                [
                    cidade.isin(["SAO PAULO", "SÃO PAULO"]),
                    cidade.isin(
                        [
                            "GUARULHOS",
                            "ARUJA",
                            "MOGI DAS CRUZES",
                            "SUZANO",
                            "ITAQUAQUECETUBA",
                            "FERRAZ DE VASCONCELOS",
                            "POA",
                        ]
                    ),
                    cidade.isin(
                        [
                            "SANTO ANDRE",
                            "SAO BERNARDO DO CAMPO",
                            "SAO CAETANO DO SUL",
                            "DIADEMA",
                            "MAUA",
                            "RIBEIRAO PIRES",
                            "RIO GRANDE DA SERRA",
                        ]
                    ),
                ],
                ["LESTE", "GRU", "ABCDM"],
                default="OUTRAS",
            )
        elif col_reg_existente and col_reg_existente in df.columns:
            reg_crua = (
                df[col_reg_existente].fillna("").astype(str).str.strip().str.upper()
            )
            df["REGIÃO"] = np.select(
                [
                    reg_crua.str.contains("LESTE|SP|SAO PAULO|SÃO PAULO"),
                    reg_crua.str.contains("GRU|GUARULHOS"),
                    reg_crua.str.contains("ABCD|SBC|SANTO ANDRE|SÃO BERNARDO"),
                ],
                ["LESTE", "GRU", "ABCDM"],
                default="OUTRAS",
            )
        elif regiao_detectada:
            df["REGIÃO"] = regiao_detectada
        else:
            df["REGIÃO"] = "OUTRAS"

        # 8. Tipo de Serviço
        try:
            res = classificar_tipo_servico(df)
            if isinstance(res, tuple) and len(res) == 2:
                df, _ = res
        except Exception:
            pass

        if "TIPO_SERVICO" not in df.columns:
            df["TIPO_SERVICO"] = "Outros"
        df["TIPO_SERVICO"] = df["TIPO_SERVICO"].fillna("Outros").astype(str).str.strip()

        # 9. Código de Baixa
        col_cod = Utils.buscar_coluna(
            df, ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "MOTIVO DE BAIXA", "COD_BAIXA"]
        )
        nome_col_baixa = "_COL_BAIXA"
        df[nome_col_baixa] = df[col_cod].astype(str).str.strip() if col_cod and col_cod in df.columns else ""
        df.attrs["_COL_BAIXA"] = nome_col_baixa

        # 10. GARANTIA DE COLUNAS
        colunas_obrigatorias = {
            "STATUS CONTRATO": "Pendente",
            "REGIÃO": "OUTRAS",
            "TIPO_SERVICO": "Outros",
            "TOTAL DE TAREFAS": 1,
            "MONITOR": "SEM MONITOR",
            "TÉCNICO": "NÃO MAPEADO",
        }
        for col, default in colunas_obrigatorias.items():
            if col not in df.columns:
                df[col] = default

        df["Status Contrato"] = df["STATUS CONTRATO"]

        return df

    @staticmethod
    def callback_robo_etl(df_raw: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        caminho_completo = st.session_state.get("robo_candidato_path", "")
        nome_arquivo = Path(caminho_completo).name if caminho_completo else "Arquivo_Robo"

        df_processado = DataLoader.preparar_base(df_raw, df_gs, filename=nome_arquivo)

        st.session_state["df_memoria"] = df_processado
        st.session_state["origem_dados"] = f"Robô Local ({nome_arquivo})"
        st.session_state["robo_hora_sucesso"] = datetime.now()
        return df_processado


# ═══════════════════════════════════════════════════════════════════════
# MOTOR ANALÍTICO
# ═══════════════════════════════════════════════════════════════════════
class Motor:
    @staticmethod
    def _soma_status(df: pd.DataFrame, status: str) -> float:
        if "Status Contrato" not in df.columns or "TOTAL DE TAREFAS" not in df.columns:
            return 0.0
        return float(df.loc[df["Status Contrato"] == status, "TOTAL DE TAREFAS"].sum())

    @staticmethod
    def quebra_atual(df: pd.DataFrame) -> Tuple[float, float]:
        if df.empty:
            return 0.0, 0.0
        exe = Motor._soma_status(df, "Executada")
        nex = Motor._soma_status(df, "Não Executada")
        cons = exe + nex
        return cons, (nex / cons) if cons > 0 else 0.0

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
        if "TIPO_SERVICO" not in df.columns:
            df_seg = df.copy()
        else:
            df_seg = (
                df[df["TIPO_SERVICO"] == segmento].copy()
                if segmento and segmento != "TODOS"
                else df.copy()
            )
        if df_seg.empty:
            return pd.DataFrame()
        tab = Motor.tabela_cenarios(df_seg, "TÉCNICO", p_ot, p_base, p_pess, min_aloc)
        return tab.head(top_n) if not tab.empty else pd.DataFrame()

    @staticmethod
    def _normalizar_baixa(df_nex: pd.DataFrame, col_baixa: str) -> pd.DataFrame:
        df_nex = df_nex.copy()
        df_nex["_baixa_norm"] = (
            df_nex[col_baixa]
            .fillna("Sem Registro")
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"NAN": "Sem Registro", "": "Sem Registro"})
        )
        return df_nex

    @staticmethod
    def causa_raiz(df: pd.DataFrame, col_baixa: str, top_n: int = 8) -> pd.DataFrame:
        if "Status Contrato" not in df.columns:
            return pd.DataFrame()
        df_nex = df[df["Status Contrato"] == "Não Executada"].copy()
        if df_nex.empty or col_baixa not in df_nex.columns:
            return pd.DataFrame()
        df_nex = Motor._normalizar_baixa(df_nex, col_baixa)
        res = (
            df_nex.groupby("_baixa_norm")["TOTAL DE TAREFAS"]
            .sum()
            .nlargest(top_n)
            .reset_index()
        )
        res.columns = ["Motivo de Baixa", "Volume"]
        total = res["Volume"].sum()
        res["% do Total"] = res["Volume"] / total if total > 0 else 0
        res["Acumulado"] = res["% do Total"].cumsum()
        return res

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

        # 1. Renomeamos as colunas do dataframe pivot PRIMEIRO
        rename_map = {"MONITOR": "Monitor", "TÉCNICO": "Técnico"}
        if "TIPO_SERVICO" in pivot.columns:
            rename_map["TIPO_SERVICO"] = "Segmento"
            
        pivot = pivot.rename(columns=rename_map)

        # 2. Agora montamos as colunas finais com os nomes já devidamente traduzidos
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
            pivot.sort_values("Prioridade", ascending=False)
            .reset_index(drop=True)[cols_final]
        )

    @staticmethod
    def matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        if "TIPO_SERVICO" not in df.columns:
            df = df.copy()
            df["TIPO_SERVICO"] = "Outros"
        if "Status Contrato" not in df.columns:
            return pd.DataFrame()

        df_valid = df[df["TIPO_SERVICO"].isin(Config.ORDEM_TIPOS)].copy()
        if df_valid.empty:
            return pd.DataFrame()
        df_valid["_executadas"] = np.where(
            df_valid["Status Contrato"] == "Executada", df_valid["TOTAL DE TAREFAS"], 0
        )
        df_valid["_nao_executadas"] = np.where(
            df_valid["Status Contrato"] == "Não Executada",
            df_valid["TOTAL DE TAREFAS"],
            0,
        )
        grp = (
            df_valid.groupby(["MONITOR", "TIPO_SERVICO"])
            .agg(
                executados=("_executadas", "sum"),
                nao_executados=("_nao_executadas", "sum"),
                total_tarefas=("TOTAL DE TAREFAS", "sum"),
            )
            .reset_index()
        )
        grp["denominador"] = grp["executados"] + grp["nao_executados"]
        grp["pct"] = np.where(
            grp["denominador"] > 0, grp["nao_executados"] / grp["denominador"], 0.0
        )
        pivot = grp.pivot_table(
            index="MONITOR", columns="TIPO_SERVICO", values="pct", fill_value=0.0
        )
        for t in Config.ORDEM_TIPOS:
            if t not in pivot.columns:
                pivot[t] = 0.0
        pivot = pivot[Config.ORDEM_TIPOS]
        exec_tot = df_valid.groupby("MONITOR")["_executadas"].sum()
        ne_tot = df_valid.groupby("MONITOR")["_nao_executadas"].sum()
        tar_tot = df_valid.groupby("MONITOR")["TOTAL DE TAREFAS"].sum()
        df_tot = pd.DataFrame({"exec": exec_tot, "ne": ne_tot, "tar": tar_tot}).fillna(
            0
        )
        pivot["Quebra Geral"] = np.where(
            (df_tot["exec"] + df_tot["ne"]) > 0,
            df_tot["ne"] / (df_tot["exec"] + df_tot["ne"]),
            0.0,
        )
        pivot["Total Tarefas"] = df_tot["tar"].astype(int)
        pivot = pivot.reset_index().rename(columns={"MONITOR": "Monitor"})
        total_row: Dict[str, Any] = {"Monitor": "TOTAL GERAL"}
        for tipo in Config.ORDEM_TIPOS:
            sub = df_valid[df_valid["TIPO_SERVICO"] == tipo]
            ex, ne = sub["_executadas"].sum(), sub["_nao_executadas"].sum()
            total_row[tipo] = (ne / (ex + ne)) if (ex + ne) > 0 else 0.0
        ex_g, ne_g = df_valid["_executadas"].sum(), df_valid["_nao_executadas"].sum()
        total_row["Quebra Geral"] = (ne_g / (ex_g + ne_g)) if (ex_g + ne_g) > 0 else 0.0
        total_row["Total Tarefas"] = int(df_valid["TOTAL DE TAREFAS"].sum())
        return pd.concat([pivot, pd.DataFrame([total_row])], ignore_index=True)

    @staticmethod
    def projetar(df: pd.DataFrame, p: float) -> Dict[str, float]:
        if df.empty:
            return dict(
                alocado=0,
                exec=0,
                naoexec=0,
                pend=0,
                quebra_atual=0,
                fechamento_proj=0,
                naoexec_proj=0,
            )
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = float(
            df.loc[df["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum()
        )
        nex = float(
            df.loc[df["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum()
        )
        pen = max(0.0, aloc - exe - nex)
        _, qa = Motor.quebra_atual(df)
        nex_proj = nex + (pen * p)
        return dict(
            alocado=aloc,
            exec=exe,
            naoexec=nex,
            pend=pen,
            quebra_atual=qa,
            fechamento_proj=(nex_proj / aloc) if aloc > 0 else 0,
            naoexec_proj=nex_proj,
        )

    @staticmethod
    def folga_sla(df: pd.DataFrame, sla: float) -> Dict[str, Any]:
        if df.empty:
            return dict(
                alocado=0,
                exec=0,
                naoexec=0,
                pend=0,
                limite_ne_total=0,
                folga_ne_pendente=0,
                folga_pct_pendente=0,
                precisa_executar_pendente=0,
                estourado=False,
            )
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = float(
            df.loc[df["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum()
        )
        nex = float(
            df.loc[df["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum()
        )
        pen = max(0.0, aloc - exe - nex)
        limite = sla * aloc
        folga_tot = limite - nex
        folga_pen = max(0.0, min(pen, folga_tot))
        return dict(
            alocado=aloc,
            exec=exe,
            naoexec=nex,
            pend=pen,
            limite_ne_total=limite,
            folga_ne_pendente=folga_pen,
            folga_pct_pendente=(folga_pen / pen) if pen > 0 else 0,
            precisa_executar_pendente=max(0.0, pen - folga_pen),
            estourado=folga_tot < 0,
        )


# ═══════════════════════════════════════════════════════════════════════
# COMPONENTES VISUAIS
# ═══════════════════════════════════════════════════════════════════════
def estilizar_matriz(df: pd.DataFrame, meta_padrao: float = 0.20):
    cols_pct = [c for c in df.columns if c not in ("Monitor", "Total Tarefas")]
    fmt: Dict[str, Any] = {c: _fmt_pct_br for c in cols_pct}
    if "Total Tarefas" in df.columns:
        fmt["Total Tarefas"] = _fmt_int_br
    METAS_COLUNAS: Dict[str, float] = {
        "NOVOS DOMICÍLIOS": 0.20,
        "Novos Domicílios": 0.20,
        "PME": 0.20,
        "MIGRAÇÃO": 0.25,
        "Migração": 0.25,
        "QUEBRA GERAL": 0.20,
        "Quebra Geral": 0.20,
        "OUTROS": 0.20,
        "Outros": 0.20,
    }
    condicoes: Dict[str, Dict[str, Any]] = {}
    for col in cols_pct:
        meta_col = METAS_COLUNAS.get(col, meta_padrao)
        condicoes[col] = {
            "meta": meta_col,
            "acima_meta": {"bg": "#FEE2E2", "text": "#991B1B", "bold": True},
            "abaixo_meta": {"bg": "#D1FAE5", "text": "#065F46", "bold": True},
        }
    return df, fmt, condicoes


def render_dataframe_profundo(
    df: pd.DataFrame,
    titulo: str,
    icone: str,
    color_col: Optional[str] = None,
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
    df_disp = df.copy()
    _COLS_INT = [
        "Executada",
        "Não Executada",
        "Pendente",
        "Alocado",
        "Considerado",
        "Volume",
        "Total Fila",
        "Prioridade",
        "TOTAL DE TAREFAS",
        "Total Tarefas",
    ]
    for col in _COLS_INT:
        if col in df_disp.columns:
            df_disp[col] = (
                pd.to_numeric(df_disp[col], errors="coerce").fillna(0).astype(int)
            )
    fmt_cols = [
        "Quebra Atual",
        "Fechamento Otimista",
        "Fechamento Base",
        "Fechamento Pessimista",
        "% do Total",
        "Acumulado",
    ]
    fmt_dict: dict[str, Any] = {c: "{:.2%}" for c in fmt_cols if c in df_disp.columns}
    for col in _COLS_INT:
        if col in df_disp.columns:
            fmt_dict[col] = "{:,.0f}"
    condicao_cores = None
    if color_col and color_col in df_disp.columns:
        condicao_cores = {
            "coluna": color_col,
            "meta": meta,
            "acima_meta": {"bg": "#FEE2E2", "text": "#991B1B", "bold": True},
            "perto_meta": {"bg": "#FEF9C3", "text": "#854D0E", "bold": True},
            "abaixo_meta": {"bg": "#DCFCE7", "text": "#166534", "bold": True},
        }
    render_table_html(
        df_disp,
        fmt=fmt_dict,
        color_rules=condicao_cores,
        num_cols=list(df_disp.columns),
        height=height,
    )


# ═══════════════════════════════════════════════════════════════════════
# HEROS
# ═══════════════════════════════════════════════════════════════════════
def html_resultado_base(regioes: List[str], total: int, origem: str = "") -> str:
    badges = "".join(
        [
            f'<span style="padding:0.3rem 0.9rem;border-radius:999px;font-size:0.82rem;'
            f'font-weight:700;border:2px solid;background:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["bg"]};'
            f'color:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["text"]};'
            f'border-color:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["border"]};">{r}</span>'
            for r in sorted(regioes)
        ]
    )
    total_fmt = f"{total:,}".replace(",", ".")
    tag_origem = (
        f'<span style="color:#6EE7B7;font-size:0.78rem;font-weight:600;margin-left:8px;">• {escape(origem)}</span>'
        if origem
        else ""
    )
    return (
        f'<div style="background:linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);'
        f"padding:1rem 1.5rem;border-radius:0.75rem;margin-bottom:1.5rem;display:flex;"
        f'align-items:center;flex-wrap:wrap;gap:0.6rem;box-shadow:0 4px 12px rgba(0,0,0,0.15);">'
        f'<span style="color:#94A3B8;font-size:0.8rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.08em;">📋 Base Ativa:</span>{badges}{tag_origem}'
        f'<span style="color:#FFFFFF;font-size:0.78rem;margin-left:auto;font-weight:700;">{total_fmt} registros</span></div>'
    )


def render_hero_topo_fixo(
    titulo: str,
    subtitulo: str,
    regioes: List[str],
    total: int,
    badge: str = "",
    origem: str = "",
) -> None:
    badge_html = (
        f'<span style="display:inline-block;background:rgba(255,255,255,0.20);padding:5px 16px;'
        f"border-radius:20px;font-size:12px;font-weight:700;margin-top:10px;letter-spacing:0.6px;"
        f'text-transform:uppercase;color:white;border:1px solid rgba(255,255,255,0.30);">{badge}</span>'
        if badge
        else ""
    )
    resultado_html = html_resultado_base(regioes, total, origem) if total > 0 else ""
    st.markdown(
        f'<div style="background:rgba(248,250,252,0.95);padding:0.5rem 0;border-radius:14px;">'
        f'<div style="background:linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);'
        f"padding:28px 40px;border-radius:14px;color:white;box-shadow:0 10px 40px rgba(1,40,105,0.20);"
        f'margin-bottom:12px;position:relative;overflow:hidden;border:1px solid rgba(255,255,255,0.10);">'
        f'<div style="position:relative;z-index:2;"><h1 style="margin:0;font-size:30px;font-weight:800;'
        f'color:white!important;letter-spacing:-0.5px;text-shadow:0 2px 4px rgba(0,0,0,0.45);">{titulo}</h1>'
        f'<p style="margin:6px 0 0 0;font-size:14px;opacity:0.95;color:#F8FAFC;'
        f'text-shadow:0 1px 3px rgba(0,0,0,0.40);">{subtitulo}</p>{badge_html}</div></div>{resultado_html}</div>',
        unsafe_allow_html=True,
    )


def render_hero_upload() -> None:
    st.markdown(
        '<div style="background:linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);'
        "padding:32px 44px;border-radius:14px;color:white;box-shadow:0 10px 40px rgba(1,40,105,0.25);"
        'margin-bottom:24px;position:relative;overflow:hidden;border:1px solid rgba(255,255,255,0.10);">'
        '<div style="position:relative;z-index:2;"><h1 style="margin:0;font-size:34px;font-weight:800;'
        'color:white!important;letter-spacing:-0.8px;text-shadow:0 2px 4px rgba(0,0,0,0.45);"> '
        'Gestão de Quebra de Agenda</h1><p style="margin:8px 0 0 0;font-size:15px;opacity:0.95;'
        'color:#F8FAFC;text-shadow:0 1px 3px rgba(0,0,0,0.40);">🤖 O <b>Robô Auto-Sincronizador</b> está ativo. '
        "Coloque o arquivo <code>Atividades-*.csv</code> ou <code>.xlsx</code> na pasta monitorada "
        "— o arquivo será capturado e processado automaticamente em segundo plano.</p>"
        '<span style="display:inline-block;background:rgba(255,255,255,0.20);padding:5px 16px;'
        "border-radius:20px;font-size:12px;font-weight:700;margin-top:12px;letter-spacing:0.6px;"
        'text-transform:uppercase;color:white;border:1px solid rgba(255,255,255,0.30);">'
        "SISTEMA TOTALE</span></div></div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════
# VISUALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════
def view_resumo_executivo(df: pd.DataFrame, meta_sla: float) -> None:
    render_section("📊 Matriz de Quebra por Monitor e Segmento")
    df_matriz = Motor.matriz_resumo(df)
    if df_matriz.empty:
        st.warning("⚠️ Dados insuficientes para montar a Matriz Executiva.")
        return
    df_proc, fmt, condicoes = estilizar_matriz(df_matriz, meta_sla)
    render_table_html(
        df_proc,
        fmt=fmt,
        condicoes_colunas=condicoes,
        linha_destaque={"coluna": "Monitor", "valor": "TOTAL GERAL"},
        height=460,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    c1, _ = st.columns([1, 1])
    with c1:
        st.download_button(
            "📥 Baixar Matriz (Excel)",
            data=Utils.gerar_excel(df_matriz, "Matriz_Resumo"),
            file_name="Matriz_Resumo_Quebra.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Projeções", "🏆 Rankings", "🔍 Causas Raiz", "🛠️ Backoffice"]
    )
    with tab1:
        render_section("📈 Cenários de Projeção de Fechamento")
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
        render_section(" Técnicos Mais Críticos")
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
    with tab3:
        render_section(" Análise de Causa Raiz (Motivos de Baixa)")
        col_baixa = cast(str, df.attrs.get("_COL_BAIXA", "_COL_BAIXA"))
        df_causa = Motor.causa_raiz(df, col_baixa, top_n=10)
        render_dataframe_profundo(df_causa, "Pareto de Motivos", "🎯")
    with tab4:
        render_section("🛠️ Gestão de Fila e Reincidência (Backoffice)")
        df_fila = Motor.backoffice_fila(df)
        render_dataframe_profundo(df_fila, "Fila Priorizada", "📋")


# ══════════════════════════════════════════════════════════════════════
# FLUXO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
def main() -> None:
    # ── Injeção de JS/CSS para Ocultar Legendas Indesejadas Instantaneamente ──
    st.markdown(
        """
        <style>
        /* Oculta mensagens de caption padrão na sidebar */
        div[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] {
            display: none !important;
        }
        </style>
        <script>
        const observer = new MutationObserver((mutations) => {
            document.querySelectorAll('span, p, div, caption, code').forEach(el => {
                if (
                    el.textContent.includes('Robô importou') || 
                    el.textContent.includes('🔌 Robô:') ||
                    el.textContent.includes('só que mantendo que importe')
                ) {
                    el.style.display = 'none';
                    el.style.height = '0px';
                    el.style.padding = '0px';
                    el.style.margin = '0px';
                }
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
        </script>
        """,
        unsafe_allow_html=True
    )

    # ─ 1. Sidebar: Marca ──────────────────────────────────────────────
    render_sidebar_brand(
        titulo="TOTALE",
        subtitulo="Quebra Operacional",
        logo="monitoring",
        ambiente="produção",
        versao="v3.4.0",
        mostrar_data=True,
    )

    # ─ 2. Configurações de Sistema (Botões) ──────────────────────
    with st.sidebar.expander("⚙️ Configurações do Sistema", expanded=False):
        st.markdown("**Gerenciamento de Sessão**")

        if st.button(
            "🔄 Reiniciar Aplicação", use_container_width=True, type="secondary"
        ):
            st.rerun()

        if st.button(
            "🗑️ Limpar Cache e Reiniciar", use_container_width=True, type="secondary"
        ):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("Cache limpo! Recarregando...")
            st.rerun()

    # ─ 3. Robô Auto-Sincronizador ────────────────────────────────────
    def _pasta_padrao_segura() -> str:
        candidatos = [
            Path.home() / "Downloads",
            Path.home() / "robo",
            _DIR / "dados",
            _DIR,
        ]
        for p in candidatos:
            if p.exists() and p.is_dir():
                return str(p.resolve())
        return str(Path.home() / "Downloads")

    if "robo_pasta_alvo" not in st.session_state or not st.session_state.get(
        "robo_pasta_alvo"
    ):
        st.session_state["robo_pasta_alvo"] = _pasta_padrao_segura()

    st.sidebar.markdown("---")

    # [Legenda da sidebar removida como requisitado]

    if ROBO_DISPONIVEL and _impl_robo is not None:
        # ── Modo NATIVO: usa o robo_local.py com ciclos rápidos de sincronismo (1s) ─────
        try:
            _impl_robo(
                etl_fn=DataLoader.callback_robo_etl,
                gsheets_fn=DataLoader.buscar_gsheets,
                pasta_padrao=st.session_state["robo_pasta_alvo"],
                ciclos_estabilidade=1, # Sincronização imediata
                mostrar_toggle=True,
                mostrar_config=True,
            )
        except Exception as e:
            st.sidebar.error(f"Robô quebrou ao renderizar: {e}")
            st.sidebar.exception(e)
    else:
        # ── Modo FALLBACK: import falhou, oferece botão manual ────────
        st.sidebar.error("Robô pacote offline — modo fallback")
        st.sidebar.code(_ROBO_IMPORT_ERRO or "sem detalhes")

        pasta_fb = st.sidebar.text_input(
            "Pasta monitorada (fallback)",
            value=st.session_state.get(
                "robo_pasta_alvo", str(Path.home() / "Downloads")
            ),
            key="robo_pasta_fallback",
        )
        st.session_state["robo_pasta_alvo"] = pasta_fb
        ativo_fb = st.sidebar.toggle(
            "⚡ Auto-Sincronizar fallback", value=True, key="fb_toggle"
        )

        if ativo_fb and pasta_fb and os.path.isdir(pasta_fb):
            candidatos: List[Path] = []
            p_dir = Path(pasta_fb)
            for pat in ("Atividades-*.csv", "Atividades-*.xlsx", "Atividades-*.xls"):
                candidatos.extend(p_dir.glob(pat))
            candidatos = [
                c for c in candidatos if c.is_file() and not c.name.startswith("~$")
            ]
            if candidatos:
                arq = max(candidatos, key=lambda x: x.stat().st_mtime)
                st.sidebar.caption(f"📄 {arq.name}")
                sig = f"{arq}|{arq.stat().st_mtime}|{arq.stat().st_size}"
                if st.sidebar.button("🚀 Importar agora", type="primary", key="fb_btn"):
                    try:
                        with st.spinner(f"Processando {arq.name}..."):
                            if arq.suffix.lower() in (".xlsx", ".xls"):
                                raw = pd.read_excel(arq, dtype=str)
                            else:
                                raw = pd.read_csv(
                                    arq,
                                    sep=None,
                                    engine="python",
                                    dtype=str,
                                    encoding="utf-8-sig",
                                    on_bad_lines="skip",
                                )
                            gs = DataLoader.buscar_gsheets()
                            st.session_state["df_memoria"] = DataLoader.preparar_base(
                                raw, gs, filename=arq.name
                            )
                            st.session_state["origem_dados"] = f"Fallback ({arq.name})"
                            st.session_state["_fb_sig"] = sig
                        st.rerun()
                    except Exception as e:
                        st.sidebar.exception(e)
            else:
                st.sidebar.warning(f"Nenhum `Atividades-*.csv/xlsx` em `{pasta_fb}`")

    # [Sessão "🐞 Debugger de Estado do Robô" totalmente removida]

    # ─ 4. Área Central: Upload Manual de Contingência ────────────────
    hero_area = st.container()
    df_atual: Optional[pd.DataFrame] = st.session_state.get("df_memoria")
    origem_atual = str(st.session_state.get("origem_dados", ""))
    robo_carregou = (
        df_atual is not None
        and not df_atual.empty
        and not origem_atual.startswith("Upload")
    )

    uploaded_file = None
    if not robo_carregou:
        with hero_area:
            render_hero_upload()
        uploaded_file = st.file_uploader(
            "⬇️ Ou carregue a base manualmente (CSV/XLSX)",
            type=["csv", "xlsx"],
            help="O Robô monitora a pasta local. Use o upload apenas em contingência.",
        )
    else:
        with st.sidebar.expander("📂 Substituir base manualmente", expanded=False):
            uploaded_file = st.file_uploader(
                "Base (CSV/XLSX)",
                type=["csv", "xlsx"],
                key="upload_contingencia",
                label_visibility="collapsed",
            )

    # ─ 5. Processamento de Upload Manual ─────────────────────────────
    if uploaded_file is not None:
        file_id = (uploaded_file.name, uploaded_file.size)
        if st.session_state.get("arquivo_processado") != file_id:
            with st.spinner("️ Processando upload manual..."):
                try:
                    file_bytes = uploaded_file.getvalue()
                    raw_df = DataLoader.ler_arquivo(file_bytes, uploaded_file.name)
                    df_gs = DataLoader.buscar_gsheets()
                    st.session_state["df_memoria"] = DataLoader.preparar_base(
                        raw_df, df_gs, filename=uploaded_file.name
                    )
                    st.session_state["arquivo_processado"] = file_id
                    st.session_state["origem_dados"] = f"Upload ({uploaded_file.name})"
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao processar o arquivo: {e}")
                    return

    df: Optional[pd.DataFrame] = st.session_state.get("df_memoria")

    # ─ 6. Estado Vazio ───────────────────────────────────────────────
    if df is None or df.empty:
        return

    # ─ 7. Sidebar: Filtros ──────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<div style='font-size:12px; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:0.8px;'>🎯 Filtros Operacionais</div>",
        unsafe_allow_html=True,
    )

    regioes_sel = []
    df_filtrado = df.copy()
    if "REGIÃO" in df.columns:
        regioes_disponiveis = sorted(df["REGIÃO"].unique().tolist())
        regioes_sel = st.sidebar.multiselect(
            "Região", regioes_disponiveis, default=regioes_disponiveis
        )
        if regioes_sel:
            df_filtrado = df[df["REGIÃO"].isin(regioes_sel)].copy()
    else:
        st.sidebar.info("ℹ️ Coluna 'REGIÃO' não identificada. Exibindo todos os dados.")

    p_ot = st.sidebar.slider("Probabilidade Otimista (%)", 0, 100, 15, step=5) / 100.0
    p_base = st.sidebar.slider("Probabilidade Base (%)", 0, 100, 30, step=5) / 100.0
    p_pess = (
        st.sidebar.slider("Probabilidade Pessimista (%)", 0, 100, 50, step=5) / 100.0
    )
    min_aloc = float(
        st.sidebar.number_input("Mínimo de Alocações", value=5, min_value=1)
    )

    # ─ 8. Hero Principal ─────────────────────────────────────────────
    origem_base = st.session_state.get("origem_dados", "Base Carregada")
    render_hero_topo_fixo(
        "Super Relatório Corporativo",
        "Análise unificada de desempenho operacional e quebra de agenda",
        regioes_sel if regioes_sel else ["OUTRAS"],
        len(df_filtrado),
        badge="TOTALE OPERACIONAL",
        origem=origem_base,
    )

    # ─ 9. Navegação por Abas ─────────────────────────────────────────
    aba = st.radio(
        "Navegação",
        ["Resumo Executivo", "Análise Detalhada", "Auditoria"],
        horizontal=True,
    )

    if aba == "Resumo Executivo":
        view_resumo_executivo(df_filtrado, Config.SLA_QUEBRA_MAXIMA)
    elif aba == "Análise Detalhada":
        view_analise_detalhada(
            df_filtrado, p_ot, p_base, p_pess, min_aloc, Config.SLA_QUEBRA_MAXIMA
        )
    elif aba == "Auditoria":
        render_painel_criterios(df_filtrado)
        render_debug_criterios(df_filtrado)


if __name__ == "__main__":
    main()