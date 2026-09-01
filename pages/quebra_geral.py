"""
quebra_totale.py
================
Super Relatório Corporativo Unificado | Quebra Operacional TOTALE

Módulos integrados:
  • Resumo Executivo (Matriz Monitor × Segmento)
  • Análise Detalhada (Projeções, Rankings, Causas, Backoffice, Base)
  • Análise por Segmento (Migração / PME) com exportação PDF Executivo
  • Auditoria de Critérios de Classificação

Critérios centralizados em: components.criterios
"""

from __future__ import annotations

import csv
import sys
import unicodedata
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import textwrap
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Path bootstrap ──────────────────────────────────────────────────
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
)
from components.componentes import render_insight as _render_insight_global
from components.componentes import render_kpi as _render_kpi_global
from components.componentes import render_kpi_sm as _render_kpi_sm_global

# ── Critérios centralizados ─────────────────────────────────────────
from components.criterios import (
    VAZIOS_CONTRATO,
    classificar_tipo_servico,
    detectar_col_contrato,
    detectar_col_status_atividade,
    render_card_destaque_migracao,
    render_debug_criterios,
    render_painel_criterios,
)

TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]
TemaKPI = Literal[
    "azul", "verde", "vermelho", "laranja", "cinza", "roxo", "amarelo", "escuro"
]


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Quebra Operacional | TOTALE",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)
aplicar_estilo()

if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None


# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES DE DOMÍNIO
# ═══════════════════════════════════════════════════════════════════════
class Config:
    """Configurações centralizadas de SLA, cores e domínio operacional."""

    SLA_QUEBRA_MAXIMA = 0.20
    SLA_PME = 0.20
    SLA_MIGRACAO = 0.25

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
        "Migração": "#0284C7",
        "PME": "#1E3A8A",
        "Quebra Geral": "#78350F",
        "Outros": "#64748B",
    }
    ORDEM_TIPOS = ["Novos Domicílios", "Migração", "PME"]


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

_MAPA_TEMA_GLOBAL: Dict[str, str] = {
    "azul": "azul",
    "verde": "verde",
    "vermelho": "vermelho",
    "laranja": "laranja",
    "cinza": "cinza",
    "roxo": "azul",
    "amarelo": "laranja",
    "escuro": "cinza",
}

FONTE_CARD_TITULO = '"Poppins", "Manrope", sans-serif'
FONTE_CARD_TEXTO = '"Inter", "Roboto", sans-serif'


# ═══════════════════════════════════════════════════════════════════════
# WRAPPERS DE INTERFACE (UI)
# ═══════════════════════════════════════════════════════════════════════
def render_kpi(col, label: str, value: str, sub: str = "", tema: str = "azul") -> None:
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
        _render_kpi_global(col, label, value, sub, _MAPA_TEMA_GLOBAL.get(tema, "azul"))  # type: ignore


def render_kpi_sm(
    col, label: str, value: str, sub: str = "", tema: str = "azul"
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
        _render_kpi_sm_global(col, label, value, sub, _MAPA_TEMA_GLOBAL.get(tema, "azul"))  # type: ignore


def render_insight(texto: str, tipo: TipoInsight = "info") -> None:
    _render_insight_global(texto, tipo)


def render_section(titulo: str) -> None:
    partes = titulo.strip().split(" ", 1)
    primeiro_char = partes[0][0] if partes[0] else ""
    if len(partes) == 2 and not primeiro_char.isascii():
        icon, title = partes[0], partes[1]
    else:
        icon, title = "📊", titulo
    render_section_header(icon, title)


# ═══════════════════════════════════════════════════════════════════════
# UTILITÁRIOS OPERACIONAIS
# ═══════════════════════════════════════════════════════════════════════
def _fmt_pct_br(v: Any) -> str:
    try:
        return (
            f"{float(v) * 100:,.2f}%".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    except (ValueError, TypeError):
        return "0,00%"


def _fmt_int_br(v: Any) -> str:
    try:
        return f"{int(float(v)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


class Utils:
    """Utilitários de manipulação, busca de colunas e exportação."""

    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras: list) -> Optional[str]:
        if df is None or df.empty:
            return None
        cols = {
            str(c)
            .strip()
            .upper()
            .replace(".", "")
            .replace("_", "")
            .replace("  ", " "): c
            for c in df.columns
        }
        for p in palavras:
            pn = (
                str(p)
                .strip()
                .upper()
                .replace(".", "")
                .replace("_", "")
                .replace("  ", " ")
            )
            for cn, co in cols.items():
                if pn in cn:
                    return co
        return None

    @staticmethod
    def classificar_status(serie: pd.Series) -> pd.Series:
        s = serie.fillna("").astype(str).str.strip().str.upper()
        exe = s == "EXECUTADA"
        nex = s.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])
        return pd.Series(
            np.select([exe, nex], ["Executada", "Não Executada"], default="Pendente"),
            index=serie.index,
        )

    @staticmethod
    def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=aba[:31])
            ws = w.sheets[aba[:31]]
            hf = PatternFill("solid", fgColor="0F172A")
            for cell in ws[1]:
                cell.fill = hf
                cell.font = Font(color="FFFFFF", bold=True)
            for i, col in enumerate(df.columns, 1):
                try:
                    serie_str = df[col].fillna("").astype(str)
                    tamanhos = serie_str.str.len()
                    max_len_dados = int(tamanhos.max()) if len(tamanhos) > 0 else 0
                    max_len = max(max_len_dados, len(str(col)))
                    ws.column_dimensions[get_column_letter(i)].width = min(
                        max(max_len + 2, 12), 40
                    )
                except Exception:
                    ws.column_dimensions[get_column_letter(i)].width = 20
        return out.getvalue()


# ═══════════════════════════════════════════════════════════════════════
# CARREGAMENTO E SANEAMENTO DE DADOS (ETL)
# ═══════════════════════════════════════════════════════════════════════
class DataLoader:
    """Pipeline de ingestão, limpeza e enriquecimento da base."""

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
        ttl=600, show_spinner="🔗 Conectando com Google Sheets (lista_ativos)..."
    )
    def buscar_gsheets() -> pd.DataFrame:
        try:
            from streamlit_gsheets import GSheetsConnection

            conn = st.connection("gsheets", type=GSheetsConnection)
            raw = conn.read(
                spreadsheet=Config.URL_LISTA_ATIVOS,
                worksheet=Config.WORKSHEET_ATIVOS,
            )
            if raw is not None and not raw.empty:
                return DataLoader._processar_lista_ativos(raw)
        except Exception:
            pass
        for url in (
            f"https://docs.google.com/spreadsheets/d/{Config.SHEET_ID_ATIVOS}"
            f"/gviz/tq?tqx=out:csv&sheet={Config.WORKSHEET_ATIVOS}",
            f"https://docs.google.com/spreadsheets/d/{Config.SHEET_ID_ATIVOS}"
            f"/export?format=csv&gid=0",
        ):
            try:
                raw = pd.read_csv(url)
                if raw is not None and not raw.empty:
                    return DataLoader._processar_lista_ativos(raw)
            except Exception as e:
                st.warning(f"⚠️ Falha ao carregar lista_ativos: {e}")
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
    @st.cache_data(show_spinner=False)
    def preparar_base(df: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.upper()
        df.attrs["total_importado"] = len(df)

        # 1. Remover Suspensos
        col_atv = detectar_col_status_atividade(df)
        n_susp = 0
        if col_atv:
            serie_atv = df[col_atv].fillna("").astype(str).str.strip().str.upper()
            mask_susp = (
                serie_atv.str.contains("SUSP", na=False)
                | serie_atv.eq("SUSPENSO")
                | serie_atv.eq("SUSPENSA")
            )
            n_susp = int(mask_susp.sum())
            df = df[~mask_susp].copy()
        df.attrs["col_status_atividade"] = col_atv
        df.attrs["removidos_suspensos"] = n_susp

        # 2. Remover Contratos Inválidos
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
            st.warning(
                "⚠️ Base ficou vazia após remoção de suspensos e contratos inválidos."
            )
            return pd.DataFrame()

        # 3. Total de Tarefas (Conversão segura para int64 sem conflito com dtype='str')
        col_tot = Utils.buscar_coluna(df, ["TOTAL DE TAREFAS", "QTD TAREFAS"])
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

        # 4. Merge com lista_ativos
        col_login = Utils.buscar_coluna(
            df,
            ["LOGIN DO TÉCNICO", "LOGIN DO TECNICO", "LOGIN", "USUÁRIO", "MATRÍCULA"],
        )
        df.attrs["merge_aplicado"] = False
        df.attrs["merge_matches"] = 0
        df.attrs["merge_total"] = len(df)

        if col_login and not df_gs.empty and "Login" in df_gs.columns:
            df[col_login] = (
                df[col_login]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip()
                .str.upper()
            )
            df = df.drop(
                columns=[c for c in ["TÉCNICO", "MONITOR", "Base"] if c in df.columns],
                errors="ignore",
            )
            df = df.merge(
                df_gs,
                left_on=col_login,
                right_on="Login",
                how="left",
                suffixes=("", "_gs"),
            )
            if "Login" in df.columns and col_login != "Login":
                df = df.drop(columns=["Login"], errors="ignore")
            if "Técnico" in df.columns:
                df.attrs["merge_matches"] = int(df["Técnico"].notna().sum())
                df.attrs["merge_aplicado"] = True

        if "Técnico" not in df.columns:
            col_tec_orig = Utils.buscar_coluna(
                df, ["TECNICO", "NOME TECNICO", "NOME DO TECNICO", "TÉCNICO"]
            )
            df["Técnico"] = (
                df[col_tec_orig]
                if col_tec_orig and col_tec_orig in df.columns
                else "NÃO MAPEADO"
            )
        if "Monitor" not in df.columns:
            col_mon_orig = Utils.buscar_coluna(
                df, ["MONITOR", "GESTOR", "SUPERVISOR", "NOME MONITOR"]
            )
            df["Monitor"] = (
                df[col_mon_orig]
                if col_mon_orig and col_mon_orig in df.columns
                else "SEM MONITOR"
            )

        df["TÉCNICO"] = (
            df["Técnico"].fillna("NÃO MAPEADO").astype(str).str.strip().str.upper()
        )
        df["MONITOR"] = (
            df["Monitor"].fillna("SEM MONITOR").astype(str).str.strip().str.upper()
        )
        df = df.drop(columns=["Técnico", "Monitor"], errors="ignore")
        df.loc[df["TÉCNICO"].isin(["", "NAN", "NONE", "NULL"]), "TÉCNICO"] = (
            "NÃO MAPEADO"
        )
        df.loc[df["MONITOR"].isin(["", "NAN", "NONE", "NULL"]), "MONITOR"] = (
            "SEM MONITOR"
        )

        # 5. Regiões
        col_cid = Utils.buscar_coluna(df, ["CIDADE", "LOCALIDADE"])
        cidade = (
            df[col_cid].fillna("").astype(str).str.strip().str.upper()
            if col_cid
            else pd.Series("", index=df.index)
        )
        df["REGIÃO"] = np.select(
            [
                cidade.isin(["SAO PAULO"]),
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

        # 6. Status Contrato
        col_status = Utils.buscar_coluna(
            df, ["STATUS DA O.S 1", "STATUS OS 1", "STATUS CONTRATO"]
        )
        df["Status Contrato"] = (
            Utils.classificar_status(df[col_status]) if col_status else "Pendente"
        )

        # 7. Classificação centralizada (Migração + FLAG_GPON auto)
        df, df["TIPO_SERVICO"] = classificar_tipo_servico(df)

        # 8. Motivo de Baixa
        col_cod = Utils.buscar_coluna(
            df, ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "MOTIVO DE BAIXA"]
        )
        df["_COL_BAIXA"] = df[col_cod].astype(str) if col_cod else ""

        # 9. Data Agenda
        col_data = Utils.buscar_coluna(df, ["DATA", "DT AGENDA", "DATA AGENDA"])
        df["_DATA_AGENDA"] = (
            pd.to_datetime(df[col_data], errors="coerce", dayfirst=True)
            if col_data
            else pd.NaT
        )
        return df


# ═══════════════════════════════════════════════════════════════════════
# MOTOR ANALÍTICO (BUSINESS LOGIC)
# ═══════════════════════════════════════════════════════════════════════
class Motor:
    """Cálculos vetorizados de projeções, SLA, causas e rankings."""

    @staticmethod
    def _soma_status(df: pd.DataFrame, status: str) -> float:
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
    def projetar(df: pd.DataFrame, p: float) -> Dict[str, float]:
        if df.empty:
            return dict(
                alocado=0.0,
                exec=0.0,
                naoexec=0.0,
                pend=0.0,
                quebra_atual=0.0,
                fechamento_proj=0.0,
                naoexec_proj=0.0,
            )
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = Motor._soma_status(df, "Executada")
        nex = Motor._soma_status(df, "Não Executada")
        pen = max(0.0, aloc - exe - nex)
        _, qa = Motor.quebra_atual(df)
        nex_proj = nex + (pen * p)
        return dict(
            alocado=aloc,
            exec=exe,
            naoexec=nex,
            pend=pen,
            quebra_atual=qa,
            fechamento_proj=(nex_proj / aloc) if aloc > 0 else 0.0,
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
        exe = Motor._soma_status(df, "Executada")
        nex = Motor._soma_status(df, "Não Executada")
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
            if "TIPO_SERVICO" in df.columns
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
        df_nex = df[df["Status Contrato"] == "Não Executada"]
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
    def causa_raiz_segmento(
        df: pd.DataFrame, segmento: str, col_baixa: str, top_n: int = 8
    ) -> pd.DataFrame:
        if "TIPO_SERVICO" not in df.columns:
            return pd.DataFrame()
        df_seg = df[df["TIPO_SERVICO"] == segmento]
        return Motor.causa_raiz(df_seg, col_baixa, top_n)

    @staticmethod
    def causa_por_segmento(
        df: pd.DataFrame, col_baixa: str, top_n: int = 5
    ) -> pd.DataFrame:
        df_nex = df[df["Status Contrato"] == "Não Executada"]
        if df_nex.empty or col_baixa not in df_nex.columns:
            return pd.DataFrame()
        df_nex = Motor._normalizar_baixa(df_nex, col_baixa)
        df_nex = df_nex[df_nex["TIPO_SERVICO"].isin(Config.ORDEM_TIPOS)]
        if df_nex.empty:
            return pd.DataFrame()

        resultados = []
        for seg in Config.ORDEM_TIPOS:
            df_s = df_nex[df_nex["TIPO_SERVICO"] == seg]
            if df_s.empty:
                continue
            top = (
                df_s.groupby("_baixa_norm")["TOTAL DE TAREFAS"]
                .sum()
                .nlargest(top_n)
                .reset_index()
            )
            top.columns = ["Motivo", "Volume"]
            total_seg = df_s["TOTAL DE TAREFAS"].sum()
            top["% no Segmento"] = top["Volume"] / total_seg if total_seg > 0 else 0
            top["Segmento"] = seg
            resultados.append(top)
        if not resultados:
            return pd.DataFrame()
        return pd.concat(resultados, ignore_index=True)[
            ["Segmento", "Motivo", "Volume", "% no Segmento"]
        ]

    @staticmethod
    def causa_por_monitor(
        df: pd.DataFrame, col_baixa: str, top_n_monitores: int = 10
    ) -> pd.DataFrame:
        df_nex = df[df["Status Contrato"] == "Não Executada"]
        if df_nex.empty or col_baixa not in df_nex.columns:
            return pd.DataFrame()
        df_nex = Motor._normalizar_baixa(df_nex, col_baixa)

        vol_por_mon = (
            df_nex.groupby("MONITOR")["TOTAL DE TAREFAS"]
            .sum()
            .nlargest(top_n_monitores)
            .reset_index()
        )
        vol_por_mon.columns = ["Monitor", "Total NE"]

        motivo_top = (
            df_nex.groupby(["MONITOR", "_baixa_norm"])["TOTAL DE TAREFAS"]
            .sum()
            .reset_index()
            .sort_values(["MONITOR", "TOTAL DE TAREFAS"], ascending=[True, False])
            .groupby("MONITOR")
            .first()
            .reset_index()
        )
        motivo_top.columns = ["Monitor", "Motivo Principal", "Vol. Motivo"]
        result = vol_por_mon.merge(motivo_top, on="Monitor", how="left")
        result["% do Motivo"] = np.where(
            result["Total NE"] > 0, result["Vol. Motivo"] / result["Total NE"], 0
        )
        return result

    @staticmethod
    def causa_por_regiao(df: pd.DataFrame, col_baixa: str) -> pd.DataFrame:
        df_nex = df[df["Status Contrato"] == "Não Executada"]
        if df_nex.empty or col_baixa not in df_nex.columns:
            return pd.DataFrame()
        df_nex = Motor._normalizar_baixa(df_nex, col_baixa)
        top_motivos = (
            df_nex.groupby("_baixa_norm")["TOTAL DE TAREFAS"]
            .sum()
            .nlargest(10)
            .index.tolist()
        )
        df_top = df_nex[df_nex["_baixa_norm"].isin(top_motivos)]
        if df_top.empty:
            return pd.DataFrame()
        pivot = (
            pd.pivot_table(
                df_top,
                index="_baixa_norm",
                columns="REGIÃO",
                values="TOTAL DE TAREFAS",
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
            .rename(columns={"_baixa_norm": "Motivo"})
        )
        pivot["Total"] = pivot.iloc[:, 1:].sum(axis=1)
        return pivot.sort_values("Total", ascending=False)

    @staticmethod
    def backoffice_fila(df: pd.DataFrame) -> pd.DataFrame:
        df_fila = df[df["Status Contrato"].isin(["Não Executada", "Pendente"])]
        if df_fila.empty:
            return pd.DataFrame()
        agg = (
            df_fila.groupby(["MONITOR", "TÉCNICO", "TIPO_SERVICO", "Status Contrato"])[
                "TOTAL DE TAREFAS"
            ]
            .sum()
            .reset_index()
        )
        pivot = pd.pivot_table(
            agg,
            index=["MONITOR", "TÉCNICO", "TIPO_SERVICO"],
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
            default="🟢 BAIXA",
        )
        pivot = pivot.sort_values("Prioridade", ascending=False).reset_index(drop=True)
        return pivot[
            [
                "Classificação",
                "MONITOR",
                "TÉCNICO",
                "TIPO_SERVICO",
                "Não Executada",
                "Pendente",
                "Total Fila",
                "Prioridade",
            ]
        ].rename(
            columns={
                "MONITOR": "Monitor",
                "TÉCNICO": "Técnico",
                "TIPO_SERVICO": "Segmento",
            }
        )

    @staticmethod
    def backoffice_reincidencia(
        df: pd.DataFrame, col_baixa: str, min_ocorrencias: int = 2
    ) -> pd.DataFrame:
        df_nex = df[df["Status Contrato"] == "Não Executada"]
        if df_nex.empty or col_baixa not in df_nex.columns:
            return pd.DataFrame()
        df_nex = Motor._normalizar_baixa(df_nex, col_baixa)
        df_nex = df_nex[df_nex["_baixa_norm"] != "SEM REGISTRO"]
        if df_nex.empty:
            return pd.DataFrame()
        agg = (
            df_nex.groupby(["TÉCNICO", "_baixa_norm", "MONITOR"])
            .agg(
                Ocorrencias=("TOTAL DE TAREFAS", "count"),
                Volume=("TOTAL DE TAREFAS", "sum"),
            )
            .reset_index()
        )
        reincidentes = agg[agg["Ocorrencias"] >= min_ocorrencias]
        if reincidentes.empty:
            return pd.DataFrame()
        return (
            reincidentes.sort_values(
                ["Ocorrencias", "Volume"], ascending=[False, False]
            )
            .reset_index(drop=True)
            .rename(
                columns={
                    "TÉCNICO": "Técnico",
                    "_baixa_norm": "Motivo",
                    "MONITOR": "Monitor",
                }
            )[["Técnico", "Motivo", "Ocorrencias", "Volume", "Monitor"]]
        )

    @staticmethod
    def backoffice_ranking_criticos(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
        df_fila = df[df["Status Contrato"].isin(["Não Executada", "Pendente"])]
        if df_fila.empty:
            return pd.DataFrame()
        return (
            df_fila.groupby(["TÉCNICO", "MONITOR"])
            .agg(
                Total_Fila=("TOTAL DE TAREFAS", "sum"),
                Qtd_OS=("TOTAL DE TAREFAS", "count"),
            )
            .reset_index()
            .sort_values("Total_Fila", ascending=False)
            .head(top_n)
            .rename(
                columns={
                    "TÉCNICO": "Técnico",
                    "MONITOR": "Monitor",
                    "Total_Fila": "Total na Fila",
                    "Qtd_OS": "Qtd OS",
                }
            )
        )

    @staticmethod
    def matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        df_valid = df[df["TIPO_SERVICO"] != "Outros"].copy()
        if df_valid.empty:
            return pd.DataFrame()

        # Vetorização inteligente (elimina warning do Pandas)
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

        total_row: Dict[str, Any] = {"Monitor": "Total Geral"}
        for tipo in Config.ORDEM_TIPOS:
            sub = df_valid[df_valid["TIPO_SERVICO"] == tipo]
            ex = sub["_executadas"].sum()
            ne = sub["_nao_executadas"].sum()
            total_row[tipo] = ne / (ex + ne) if (ex + ne) > 0 else 0.0

        ex_g = df_valid["_executadas"].sum()
        ne_g = df_valid["_nao_executadas"].sum()
        total_row["Quebra Geral"] = ne_g / (ex_g + ne_g) if (ex_g + ne_g) > 0 else 0.0
        total_row["Total Tarefas"] = int(df_valid["TOTAL DE TAREFAS"].sum())

        return pd.concat([pivot, pd.DataFrame([total_row])], ignore_index=True)


# ═══════════════════════════════════════════════════════════════════════
# PDFs EXECUTIVOS (SEGMENTOS) - SEM PYLANCE ERRORS
# ═══════════════════════════════════════════════════════════════════════
class _PDFExecutivoBase:
    """Classe base compartilhada para PDFs Executivos (Migração e PME)."""

    COR_PRIMARIA: str = "#0C4A6E"
    COR_SECUNDARIA: str = "#0369A1"
    COR_TEXTO: str = "#0F172A"
    COR_SUBTEXTO: str = "#6B7280"
    COR_OK: str = "#059669"
    COR_ALERTA: str = "#D97706"
    COR_CRITICO: str = "#DC2626"
    COR_LINHA: str = "#E5E7EB"
    COR_LINHA_ALT: str = "#F0F9FF"
    LARGURA_UTIL: float = 27.7
    MARGEM_H: float = 0.8
    MARGEM_TOP: float = 0.8
    MARGEM_BOT: float = 1.3
    NOME_SEGMENTO: str = ""

    @classmethod
    def _fmt(cls, v: Any, col: str = "") -> str:
        if pd.isna(v):
            return "—"
        col_u = str(col).upper()
        pct_keys = {"QUEBRA", "FECHAMENTO", "META", "PROBAB", "%", "ACUMULADO", "TOTAL"}
        if isinstance(v, (float, np.floating)):
            if any(k in col_u for k in pct_keys):
                return f"{v:.2%}"
            if float(v).is_integer():
                return f"{int(v):,}".replace(",", ".")
            return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if isinstance(v, (int, np.integer)):
            return f"{v:,}".replace(",", ".")
        return escape(str(v))

    @classmethod
    def _calcular_larguras(cls, df: pd.DataFrame) -> List[float]:
        if df.empty:
            return [cls.LARGURA_UTIL]
        pesos: List[float] = []
        for col in df.columns:
            max_len = len(str(col))
            for val in df[col].head(50):
                max_len = max(max_len, len(cls._fmt(val, col)))
            pesos.append(min(max(max_len, 5), 30))
        total = sum(pesos)
        return [(p / total) * cls.LARGURA_UTIL for p in pesos]

    @classmethod
    def _tab(
        cls,
        df: pd.DataFrame,
        limite: Optional[int] = None,
        larguras: Optional[List[float]] = None,
        cor_col_quebra: Optional[str] = None,
        sla_meta: float = 0.25,
    ) -> Table:
        def _interna() -> Table:
            if df is None or df.empty:
                t = Table(
                    [["Sem dados disponíveis"]], colWidths=[cls.LARGURA_UTIL * cm]
                )
                t.setStyle(
                    TableStyle(
                        [
                            (
                                "BACKGROUND",
                                (0, 0),
                                (-1, -1),
                                colors.HexColor(cls.COR_LINHA_ALT),
                            ),
                            (
                                "TEXTCOLOR",
                                (0, 0),
                                (-1, -1),
                                colors.HexColor(cls.COR_SUBTEXTO),
                            ),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            (
                                "BOX",
                                (0, 0),
                                (-1, -1),
                                0.5,
                                colors.HexColor(cls.COR_LINHA),
                            ),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                return t

            base = df.head(limite) if limite else df.copy()
            st_h = ParagraphStyle(
                "h",
                fontName="Helvetica-Bold",
                fontSize=6.5,
                leading=8,
                textColor=colors.white,
                alignment=TA_CENTER,
            )
            st_c = ParagraphStyle(
                "c",
                fontName="Helvetica",
                fontSize=6.5,
                leading=8.5,
                textColor=colors.HexColor(cls.COR_TEXTO),
                alignment=TA_CENTER,
            )
            st_cl = ParagraphStyle(
                "cl",
                fontName="Helvetica",
                fontSize=6.5,
                leading=8.5,
                textColor=colors.HexColor(cls.COR_TEXTO),
                alignment=TA_LEFT,
            )

            dados = [[Paragraph(str(c), st_h) for c in base.columns]]
            for _, row in base.iterrows():
                dados.append(
                    [
                        Paragraph(cls._fmt(row[c], c), st_cl if i == 0 else st_c)
                        for i, c in enumerate(base.columns)
                    ]
                )

            col_widths = (
                [w * cm for w in larguras]
                if larguras
                else [w * cm for w in cls._calcular_larguras(base)]
            )
            if sum(col_widths) > cls.LARGURA_UTIL * cm:
                fator = (cls.LARGURA_UTIL * cm) / sum(col_widths)
                col_widths = [w * fator for w in col_widths]

            tab = Table(dados, colWidths=col_widths, repeatRows=1)
            style = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(cls.COR_PRIMARIA)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 6.5),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, 0),
                    1.5,
                    colors.HexColor(cls.COR_SECUNDARIA),
                ),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 6.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 1), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(cls.COR_PRIMARIA)),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor(cls.COR_LINHA)),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
            for i in range(1, len(dados)):
                style.append(
                    (
                        "BACKGROUND",
                        (0, i),
                        (-1, i),
                        (
                            colors.white
                            if i % 2 == 1
                            else colors.HexColor(cls.COR_LINHA_ALT)
                        ),
                    )
                )

            if cor_col_quebra and cor_col_quebra in base.columns:
                col_idx = list(base.columns).index(cor_col_quebra)
                for row_i, (_, row) in enumerate(base.iterrows(), start=1):
                    try:
                        val = float(row[cor_col_quebra])
                        if val > sla_meta:
                            bg_c, tx_c = colors.HexColor("#FEE2E2"), colors.HexColor(
                                cls.COR_CRITICO
                            )
                        elif val > sla_meta * 0.85:
                            bg_c, tx_c = colors.HexColor("#FEF9C3"), colors.HexColor(
                                cls.COR_ALERTA
                            )
                        else:
                            bg_c, tx_c = colors.HexColor("#DCFCE7"), colors.HexColor(
                                cls.COR_OK
                            )
                        style += [
                            ("BACKGROUND", (col_idx, row_i), (col_idx, row_i), bg_c),
                            ("TEXTCOLOR", (col_idx, row_i), (col_idx, row_i), tx_c),
                            (
                                "FONTNAME",
                                (col_idx, row_i),
                                (col_idx, row_i),
                                "Helvetica-Bold",
                            ),
                        ]
                    except Exception:
                        pass
            tab.setStyle(TableStyle(style))
            return tab

        wrapper = Table(
            [[_interna()]], colWidths=[cls.LARGURA_UTIL * cm], hAlign="CENTER"
        )
        wrapper.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return wrapper

    @classmethod
    def _rodape(cls, canvas: Any, doc: Any) -> None:
        canvas.saveState()
        page_w, _ = landscape(A4)
        canvas.setStrokeColor(colors.HexColor(cls.COR_LINHA))
        canvas.setLineWidth(0.5)
        canvas.line(cls.MARGEM_H * cm, 1.05 * cm, page_w - cls.MARGEM_H * cm, 1.05 * cm)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor(cls.COR_SUBTEXTO))
        canvas.drawString(
            cls.MARGEM_H * cm,
            0.52 * cm,
            f"{cls.NOME_SEGMENTO} — Gestão de Quebra de Agenda  |  "
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Confidencial",
        )
        canvas.drawRightString(
            page_w - cls.MARGEM_H * cm, 0.52 * cm, f"Página {doc.page}"
        )
        canvas.restoreState()


class PDFExecutivoMigracao(_PDFExecutivoBase):
    COR_PRIMARIA = "#0C4A6E"
    COR_SECUNDARIA = "#0369A1"
    COR_TEXTO = "#0F172A"
    COR_LINHA_ALT = "#F0F9FF"
    NOME_SEGMENTO = "Migração"

    @classmethod
    def _estilos(cls) -> Any:
        s = getSampleStyleSheet()
        s.add(
            ParagraphStyle(
                name="MIG_Titulo",
                parent=s["Normal"],
                fontName="Helvetica-Bold",
                fontSize=22,
                leading=28,
                textColor=colors.white,
                alignment=TA_CENTER,
                spaceAfter=2,
            )
        )
        s.add(
            ParagraphStyle(
                name="MIG_Subtitulo",
                parent=s["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=colors.HexColor("#BAE6FD"),
                alignment=TA_CENTER,
                spaceAfter=0,
            )
        )
        s.add(
            ParagraphStyle(
                name="MIG_Secao",
                parent=s["Normal"],
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=15,
                textColor=colors.HexColor(cls.COR_PRIMARIA),
                spaceBefore=8,
                spaceAfter=4,
                alignment=TA_LEFT,
            )
        )
        return s

    @classmethod
    def gerar(
        cls,
        df: pd.DataFrame,
        sla_meta: float,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 1.0,
        top_n: int = 10,
    ) -> bytes:
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=cls.MARGEM_H * cm,
            leftMargin=cls.MARGEM_H * cm,
            topMargin=cls.MARGEM_TOP * cm,
            bottomMargin=cls.MARGEM_BOT * cm,
        )
        s, el = cls._estilos(), []
        el.append(Paragraph("RELATÓRIO EXECUTIVO — MIGRAÇÃO", s["MIG_Titulo"]))
        el.append(
            Paragraph(
                f"Mudança de Pacote + FLAG_GPON = Sim • Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
                s["MIG_Subtitulo"],
            )
        )
        el.append(Spacer(1, 1 * cm))

        el.append(Paragraph("1 ─ Cenários de Fechamento", s["MIG_Secao"]))
        cenarios = [
            {
                "Cenário": nome,
                "Probab. Pendente": p,
                "Fechamento Proj.": (proj := Motor.projetar(df, p))["fechamento_proj"],
                "Não Exec. Proj.": proj["naoexec_proj"],
                "vs Meta": proj["fechamento_proj"] - sla_meta,
            }
            for nome, p in [
                ("Otimista", p_ot),
                ("Base", p_base),
                ("Pessimista", p_pess),
            ]
        ]
        el.append(
            cls._tab(
                pd.DataFrame(cenarios),
                cor_col_quebra="Fechamento Proj.",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.5 * cm))

        el.append(Paragraph("2 ─ Técnicos Críticos", s["MIG_Secao"]))
        df_tec = Motor.tecnicos_criticos(
            df, "Migração", p_base, float(min_aloc), int(top_n)
        )
        cols_tec = [
            c
            for c in [
                "TÉCNICO",
                "Alocado",
                "Executada",
                "Não Executada",
                "Pendente",
                "Quebra Atual",
                "Fechamento Otimista",
                "Fechamento Base",
                "Fechamento Pessimista",
            ]
            if c in df_tec.columns
        ]
        el.append(
            cls._tab(
                df_tec[cols_tec] if not df_tec.empty else df_tec,
                limite=15,
                cor_col_quebra="Fechamento Base",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.5 * cm))

        el.append(Paragraph("3 ─ Principais Causas de Quebra", s["MIG_Secao"]))
        el.append(
            cls._tab(
                Motor.causa_raiz_segmento(df, "Migração", "_COL_BAIXA", top_n=8),
                limite=8,
            )
        )

        doc.build(el, onFirstPage=cls._rodape, onLaterPages=cls._rodape)
        buf.seek(0)
        return buf.getvalue()


class PDFExecutivoPME(_PDFExecutivoBase):
    COR_PRIMARIA = "#4C1D95"
    COR_SECUNDARIA = "#7C3AED"
    COR_TEXTO = "#1E1B4B"
    COR_LINHA_ALT = "#F9FAFB"
    NOME_SEGMENTO = "PME"

    @classmethod
    def _estilos(cls) -> Any:
        s = getSampleStyleSheet()
        s.add(
            ParagraphStyle(
                name="PME_Titulo",
                parent=s["Normal"],
                fontName="Helvetica-Bold",
                fontSize=24,
                leading=30,
                textColor=colors.white,
                alignment=TA_CENTER,
                spaceAfter=4,
            )
        )
        s.add(
            ParagraphStyle(
                name="PME_Subtitulo",
                parent=s["Normal"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#DDD6FE"),
                alignment=TA_CENTER,
                spaceAfter=0,
            )
        )
        s.add(
            ParagraphStyle(
                name="PME_Secao",
                parent=s["Normal"],
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=15,
                textColor=colors.HexColor(cls.COR_PRIMARIA),
                spaceBefore=10,
                spaceAfter=4,
                alignment=TA_LEFT,
            )
        )
        return s

    @classmethod
    def gerar(
        cls,
        df: pd.DataFrame,
        sla_meta: float,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 1,
        top_n: int = 10,
    ) -> bytes:
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=cls.MARGEM_H * cm,
            leftMargin=cls.MARGEM_H * cm,
            topMargin=cls.MARGEM_TOP * cm,
            bottomMargin=cls.MARGEM_BOT * cm,
        )
        s, el = cls._estilos(), []
        el.append(Paragraph("RELATÓRIO EXECUTIVO — PME", s["PME_Titulo"]))
        el.append(
            Paragraph(
                f"Pequenas e Médias Empresas • Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
                s["PME_Subtitulo"],
            )
        )
        el.append(Spacer(1, 1 * cm))

        el.append(Paragraph("1. Cenários de Fechamento", s["PME_Secao"]))
        cenarios = [
            {
                "Cenário": nome,
                "Probab. Pend.": p,
                "Fechamento": (proj := Motor.projetar(df, p))["fechamento_proj"],
                "Não Exec. Proj.": proj["naoexec_proj"],
                "vs Meta": proj["fechamento_proj"] - sla_meta,
            }
            for nome, p in [
                ("Otimista", p_ot),
                ("Base", p_base),
                ("Pessimista", p_pess),
            ]
        ]
        el.append(
            cls._tab(
                pd.DataFrame(cenarios),
                larguras=[4.5, 4.5, 5.5, 5.5, 5.0],
                cor_col_quebra="Fechamento",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.5 * cm))

        el.append(Paragraph("2. Técnicos Críticos", s["PME_Secao"]))
        df_tec = Motor.tecnicos_criticos(df, "PME", p_base, float(min_aloc), int(top_n))
        cols_tec = [
            c
            for c in [
                "TÉCNICO",
                "Alocado",
                "Executada",
                "Não Executada",
                "Pendente",
                "Quebra Atual",
                "Fechamento Otimista",
                "Fechamento Base",
                "Fechamento Pessimista",
            ]
            if c in df_tec.columns
        ]
        el.append(
            cls._tab(
                df_tec[cols_tec] if not df_tec.empty else df_tec,
                limite=10,
                cor_col_quebra="Fechamento Base",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.5 * cm))

        el.append(Paragraph("3. Principais Causas de Quebra (Pareto)", s["PME_Secao"]))
        el.append(
            cls._tab(
                Motor.causa_raiz_segmento(df, "PME", "_COL_BAIXA", top_n=8),
                limite=8,
                larguras=[9.0, 4.5, 4.5, 4.5],
            )
        )

        doc.build(el, onFirstPage=cls._rodape, onLaterPages=cls._rodape)
        buf.seek(0)
        return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES DE SEGMENTO (Migração / PME)
# ═══════════════════════════════════════════════════════════════════════
SEGMENTOS_CONFIG: Dict[str, Any] = {
    "Migração": {
        "icone": "🔄",
        "subtitulo": "Análise estratégica dedicada às mudanças de pacotes com tecnologia GPON",
        "cor_primaria": "#0369A1",
        "cor_secundaria": "#0C4A6E",
        "grad_hero": "linear-gradient(135deg, #0C4A6E 0%, #0369A1 55%, #0284C7 100%)",
        "sombra_hero": "rgba(12, 74, 110, 0.25)",
        "sla_default": Config.SLA_MIGRACAO,
        "pdf_class": PDFExecutivoMigracao,
        "acoes": [
            (
                "ALTA",
                "Verificar estoque de equipamentos nos almoxarifados das regiões com maior quebra.",
                "alerta",
            ),
            (
                "MÉDIA",
                "Confirmar certificação dos técnicos em instalação GPON.",
                "acao",
            ),
            ("MÉDIA", "Priorizar agendamentos de migração no início do turno.", "acao"),
            (
                "BAIXA",
                "Validar se ordens com status 'Pendente' possuem pré-vistoria aprovada.",
                "info",
            ),
        ],
    },
    "PME": {
        "icone": "🏢",
        "subtitulo": "Análise estratégica dedicada às Pequenas e Médias Empresas",
        "cor_primaria": "#7C3AED",
        "cor_secundaria": "#4C1D95",
        "grad_hero": "linear-gradient(135deg, #4C1D95 0%, #7C3AED 55%, #A855F7 100%)",
        "sombra_hero": "rgba(76, 29, 149, 0.25)",
        "sla_default": Config.SLA_PME,
        "pdf_class": PDFExecutivoPME,
        "acoes": [
            (
                "🟡 MÉDIA",
                "Verificar disponibilidade de técnicos habilitados em PME.",
                "acao",
            ),
            (
                "🟡 MÉDIA",
                "Acionar equipe comercial PME para comunicação proativa.",
                "acao",
            ),
            ("🟢 BAIXA", "Revisar janelas de atendimento PME.", "info"),
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════
# COMPONENTES VISUAIS AVANÇADOS
# ═══════════════════════════════════════════════════════════════════════
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
        f'<div style="font-size:1rem;font-weight:700;color:#0F172A;'
        f'display:flex;align-items:center;gap:0.5rem;">'
        f"<span>{icone}</span><span>{titulo}</span>"
        f'<span style="font-size:0.68rem;background:#E0F2FE;color:#0369A1;'
        f'padding:0.15rem 0.5rem;border-radius:999px;">{len(df)} registros</span>'
        f"</div></div>",
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
        "Qtd Não Executadas",
        "Volume",
        "Total NE",
        "Vol. Motivo",
        "Total Fila",
        "Prioridade",
        "Ocorrencias",
        "Total na Fila",
        "Qtd OS",
        "TOTAL DE TAREFAS",
        "Total Tarefas",
        "Qtde. O.S.",
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
        "% no Segmento",
        "% do Motivo",
    ]
    fmt_dict: dict[str, Any] = {c: "{:.2%}" for c in fmt_cols if c in df_disp.columns}
    for col in _COLS_INT:
        if col in df_disp.columns:
            fmt_dict[col] = "{:,.0f}"

    styler = df_disp.style.format(fmt_dict)

    if color_col and color_col in df_disp.columns:

        def _cor(val: Any) -> str:
            try:
                v = float(val)
            except (ValueError, TypeError):
                return ""
            if v > meta:
                return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"
            if v > meta * 0.85:
                return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
            return "background-color:#DCFCE7;color:#166534;font-weight:600;"

        styler = styler.map(_cor, subset=[color_col])

    if "Quebra Atual" in df_disp.columns:
        styler = styler.map(
            lambda v: (
                "background-color:#1E293B;color:#FFFFFF;font-weight:600;"
                if not pd.isna(v)
                else ""
            ),
            subset=["Quebra Atual"],
        )

    styler = styler.set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background-color", "#0F172A"),
                    ("color", "#FFFFFF"),
                    ("font-size", "0.78rem"),
                    ("font-weight", "700"),
                    ("text-transform", "uppercase"),
                    ("padding", "0.6rem 0.8rem"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("font-size", "0.82rem"),
                    ("padding", "0.5rem 0.8rem"),
                    ("border-bottom", "1px solid #F1F5F9"),
                ],
            },
        ]
    )
    st.dataframe(styler, use_container_width=True, hide_index=True, height=height)


def estilizar_matriz(df: pd.DataFrame, meta: float):
    cols_pct = [c for c in df.columns if c not in ("Monitor", "Total Tarefas")]

    def _cores(row):
        estilos = []
        is_total = str(row.get("Monitor", "")).upper() == "TOTAL GERAL"
        for col in df.columns:
            if col == "Monitor":
                estilos.append(
                    "background:linear-gradient(90deg,#012869 0%,#1E40AF 100%);"
                    "color:white;font-weight:800;text-align:left;padding-left:16px;"
                    if is_total
                    else "background-color:#F8FAFC;font-weight:700;text-align:left;"
                    "padding-left:16px;border-right:2px solid #E2E8F0;"
                )
            elif col == "Total Tarefas":
                estilos.append(
                    "background:#1E3A8A;color:white;font-weight:800;text-align:center;"
                    if is_total
                    else "background-color:#EFF6FF;color:#1E3A8A;font-weight:700;text-align:center;"
                )
            else:
                try:
                    val = float(row[col])
                except (ValueError, TypeError):
                    val = 0.0
                bg = "#FEE2E2" if val > meta else "#D1FAE5"
                tc = "#991B1B" if val > meta else "#065F46"
                if is_total:
                    bg = "#7F1D1D" if val > meta else "#064E3B"
                    tc = "white"
                estilos.append(
                    f"background-color:{bg};color:{tc};text-align:center;font-weight:800;"
                )
        return estilos

    styler = df.style.apply(_cores, axis=1)
    fmt: Dict[str, Any] = {c: _fmt_pct_br for c in cols_pct}
    if "Total Tarefas" in df.columns:
        fmt["Total Tarefas"] = _fmt_int_br
    return styler.format(fmt).set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background", "#012869"),
                    ("color", "white"),
                    ("text-align", "center"),
                    ("padding", "10px"),
                    ("font-family", FONTE_TITULO),
                    ("font-weight", "700"),
                    ("text-transform", "uppercase"),
                    ("letter-spacing", "0.05em"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("padding", "12px 10px"),
                    ("border-bottom", "1px solid #E2E8F0"),
                    ("font-variant-numeric", "tabular-nums"),
                ],
            },
        ]
    )


def render_dataframe(
    df: pd.DataFrame,
    titulo: str,
    icone: str,
    fmt: Optional[Dict[str, str]] = None,
    color_col: Optional[str] = None,
    color_meta: float = 0.20,
    color_invertido: bool = False,
    height: int = 400,
) -> None:
    """Wrapper de compatibilidade."""
    render_dataframe_profundo(df, titulo, icone, color_col, color_meta, height)


# ═══════════════════════════════════════════════════════════════════════
# HEROS E HEADERS DINÂMICOS
# ═══════════════════════════════════════════════════════════════════════
def html_resultado_base(regioes: List[str], total: int) -> str:
    badges = "".join(
        [
            f'<span style="padding:0.3rem 0.9rem;border-radius:999px;'
            f"font-size:0.82rem;font-weight:700;border:2px solid;"
            f'background:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["bg"]};'
            f'color:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["text"]};'
            f'border-color:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["border"]};">'
            f"{r}</span>"
            for r in sorted(regioes)
        ]
    )
    total_fmt = f"{total:,}".replace(",", ".")
    return (
        '<div style="background:linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);'
        "padding:1rem 1.5rem;border-radius:0.75rem;margin-bottom:1.5rem;"
        "display:flex;align-items:center;flex-wrap:wrap;gap:0.6rem;"
        'box-shadow:0 4px 12px rgba(0,0,0,0.15);">'
        '<span style="color:#94A3B8;font-size:0.8rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.08em;">📋 Resultado da Base:</span>'
        f"{badges}"
        '<span style="color:#FFFFFF;font-size:0.78rem;margin-left:auto;'
        f'font-weight:700;">{total_fmt} registros</span>'
        "</div>"
    )


def render_hero_topo_fixo(
    titulo: str,
    subtitulo: str,
    regioes: List[str],
    total: int,
    badge: str = "",
) -> None:
    badge_html = ""
    if badge:
        badge_html = (
            f'<span style="display:inline-block;background:rgba(255,255,255,0.20);'
            f"padding:5px 16px;border-radius:20px;font-size:12px;font-weight:700;"
            f"margin-top:10px;letter-spacing:0.6px;text-transform:uppercase;"
            f'color:white;border:1px solid rgba(255,255,255,0.30);">'
            f"{badge}</span>"
        )
    resultado_html = html_resultado_base(regioes, total) if total > 0 else ""
    st.markdown(
        f'<div style="position:sticky;top:0.75rem;z-index:1000;'
        f"background:rgba(248,250,252,0.92);backdrop-filter:blur(10px);"
        f'-webkit-backdrop-filter:blur(10px);padding:0.5rem 0;border-radius:14px;">'
        f'<div style="background:linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);'
        f"padding:28px 40px;border-radius:14px;color:white;"
        f"box-shadow:0 10px 40px rgba(1,40,105,0.30);margin-bottom:12px;"
        f'position:relative;overflow:hidden;border:1px solid rgba(255,255,255,0.10);">'
        f'<div style="position:absolute;top:50%;right:-100px;transform:translateY(-50%);'
        f"width:420px;height:420px;background:radial-gradient(circle at center,"
        f"rgba(255,180,90,0.35) 0%, rgba(243,124,4,0.20) 35%,"
        f"rgba(232,93,4,0.08) 60%, transparent 78%);"
        f'border-radius:50%;pointer-events:none;filter:blur(2px);"></div>'
        f'<div style="position:relative;z-index:2;">'
        f'<h1 style="margin:0;font-size:30px;font-weight:800;color:white!important;'
        f'letter-spacing:-0.5px;text-shadow:0 2px 4px rgba(0,0,0,0.45);">{titulo}</h1>'
        f'<p style="margin:6px 0 0 0;font-size:14px;opacity:0.95;'
        f'color:#F8FAFC;text-shadow:0 1px 3px rgba(0,0,0,0.40);">{subtitulo}</p>'
        f"{badge_html}</div></div>"
        f"{resultado_html}</div>",
        unsafe_allow_html=True,
    )


def render_hero_upload() -> None:
    st.markdown(
        '<div style="background:linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);'
        "padding:32px 44px;border-radius:14px;color:white;"
        "box-shadow:0 10px 40px rgba(1,40,105,0.30);margin-bottom:24px;"
        'position:relative;overflow:hidden;border:1px solid rgba(255,255,255,0.10);">'
        '<div style="position:absolute;top:50%;right:-100px;transform:translateY(-50%);'
        "width:420px;height:420px;background:radial-gradient(circle at center,"
        "rgba(255,180,90,0.35) 0%, rgba(243,124,4,0.20) 35%,"
        "rgba(232,93,4,0.08) 60%, transparent 78%);"
        'border-radius:50%;pointer-events:none;filter:blur(2px);"></div>'
        '<div style="position:relative;z-index:2;">'
        '<h1 style="margin:0;font-size:34px;font-weight:800;color:white!important;'
        'letter-spacing:-0.8px;text-shadow:0 2px 4px rgba(0,0,0,0.45);">'
        "📉 Gestão de Quebra de Agenda</h1>"
        '<p style="margin:8px 0 0 0;font-size:15px;opacity:0.95;'
        'color:#F8FAFC;text-shadow:0 1px 3px rgba(0,0,0,0.40);">'
        "Importe a base para gerar o Super Relatório Consolidado</p>"
        '<span style="display:inline-block;background:rgba(255,255,255,0.20);'
        "padding:5px 16px;border-radius:20px;font-size:12px;font-weight:700;"
        "margin-top:12px;letter-spacing:0.6px;text-transform:uppercase;"
        'color:white;border:1px solid rgba(255,255,255,0.30);">SISTEMA TOTALE</span>'
        "</div></div>",
        unsafe_allow_html=True,
    )


def _injetar_css_segmento(segmento: str) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    st.markdown(
        f"""
<style>
.hero-segmento {{
    background: {conf["grad_hero"]};
    padding: 32px 40px;
    border-radius: 16px;
    color: white;
    box-shadow: 0 10px 40px {conf["sombra_hero"]};
    margin-bottom: 12px;
    position: relative;
    overflow: hidden;
}}

.hero-segmento h1 {{
    position: relative;
    z-index: 2;
    color: white !important;
    font-family: {FONTE_CARD_TITULO} !important;
    font-size: 34px;
    font-weight: 900;
    margin: 0;
    letter-spacing: -0.04em;
    text-shadow: 0 2px 4px rgba(0,0,0,0.28);
}}

.hero-segmento p {{
    position: relative;
    z-index: 2;
    color: rgba(255,255,255,0.92) !important;
    font-family: {FONTE_CARD_TEXTO} !important;
    font-size: 15px;
    margin: 8px 0 0;
    font-weight: 500;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_hero_segmento(segmento: str, regioes: List[str], total: int) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    _injetar_css_segmento(segmento)
    st.markdown(
        f'<div class="hero-segmento">'
        f'<h1>{conf["icone"]} {segmento} — Quebra de Agenda</h1>'
        f'<p>{conf["subtitulo"]}</p></div>'
        f"{html_resultado_base(regioes, total)}",
        unsafe_allow_html=True,
    )


def _render_card_status(segmento: str, m_seg: Dict[str, Any], sla_meta: float) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    quebra_atual = float(m_seg["quebra_atual"])
    dentro_sla = quebra_atual <= sla_meta

    if dentro_sla:
        status_label = "DENTRO DO SLA"
        status_icone = "✓"
        cor_status = "#059669"
        cor_bg = "#D1FAE5"
        cor_txt = "#065F46"
        mensagem = (
            f"{segmento} com folga de "
            f"<strong>{sla_meta - quebra_atual:.2%}</strong> em relação à meta."
        )
        icone_mensagem = "✅"
    else:
        status_label = "FORA DO SLA"
        status_icone = "!"
        cor_status = "#DC2626"
        cor_bg = "#FEE2E2"
        cor_txt = "#991B1B"
        mensagem = (
            f"{segmento} acima da meta em "
            f"<strong>{quebra_atual - sla_meta:.2%}</strong>. "
            "Ação corretiva imediata necessária."
        )
        icone_mensagem = "🚨"

    pct_barra = min(
        100.0,
        (quebra_atual / (sla_meta * 2)) * 100 if sla_meta > 0 else 0,
    )

    # textwrap.dedent remove os espaços de recuo para o Streamlit não renderizar como bloco de código
    html = textwrap.dedent(f"""
        <div style="background:white;border:1px solid #E5E7EB;border-radius:14px;padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.04);margin:16px 0 24px 0;border-top:3px solid {conf['cor_primaria']};">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;">
                <div style="display:flex;align-items:center;gap:14px;">
                    <div style="width:44px;height:44px;background:{conf['grad_hero']};border-radius:10px;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px {conf['sombra_hero']};">
                        <span style="font-size:22px;">{conf['icone']}</span>
                    </div>
                    <div>
                        <div style="font-family:{FONTE_TITULO};font-size:20px;font-weight:800;color:#0F172A;letter-spacing:-0.03em;line-height:1.1;">
                            {segmento}
                        </div>
                        <div style="font-family:{FONTE_TEXTO};font-size:12px;color:#64748B;font-weight:500;margin-top:4px;letter-spacing:-0.01em;">
                            Análise de Quebra
                        </div>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    <div style="display:inline-flex;align-items:center;gap:6px;padding:6px 14px;background:{cor_bg};border-radius:999px;border:1px solid {cor_status};">
                        <span style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;background:{cor_status};color:white;border-radius:50%;font-family:{FONTE_TEXTO};font-size:11px;font-weight:800;">
                            {status_icone}
                        </span>
                        <span style="font-family:{FONTE_TEXTO};font-size:11px;font-weight:800;color:{cor_txt};text-transform:uppercase;letter-spacing:0.04em;">
                            {status_label}
                        </span>
                    </div>
                    <div style="display:inline-flex;flex-direction:column;padding:7px 15px;background:#F0F9FF;border-radius:8px;border:1px solid #BAE6FD;min-width:102px;">
                        <span style="font-family:{FONTE_TEXTO};font-size:9px;color:#64748B;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;">
                            Quebra Atual
                        </span>
                        <span style="font-family:{FONTE_TITULO};font-size:18px;color:{cor_status};font-weight:900;line-height:1.15;letter-spacing:-0.04em;font-variant-numeric:tabular-nums;">
                            {quebra_atual:.2%}
                        </span>
                    </div>
                    <div style="display:inline-flex;flex-direction:column;padding:7px 15px;background:#F0F9FF;border-radius:8px;border:1px solid #BAE6FD;min-width:92px;">
                        <span style="font-family:{FONTE_TEXTO};font-size:9px;color:#64748B;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;">
                            Meta SLA
                        </span>
                        <span style="font-family:{FONTE_TITULO};font-size:18px;color:{conf['cor_secundaria']};font-weight:900;line-height:1.15;letter-spacing:-0.04em;font-variant-numeric:tabular-nums;">
                            {sla_meta:.2%}
                        </span>
                    </div>
                </div>
            </div>
            <div style="margin:16px 0 12px 0;">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-family:{FONTE_TEXTO};font-size:11px;color:#64748B;font-weight:700;">
                    <span>0%</span>
                    <span>Meta {sla_meta:.2%}</span>
                    <span>{sla_meta * 2:.0%}</span>
                </div>
                <div style="position:relative;height:8px;background:#E5E7EB;border-radius:4px;overflow:hidden;">
                    <div style="position:absolute;left:50%;top:0;width:2px;height:100%;background:#374151;z-index:2;"></div>
                    <div style="width:{pct_barra:.2f}%;height:100%;background:linear-gradient(90deg,{cor_status} 0%, {cor_status}CC 100%);border-radius:4px;"></div>
                </div>
            </div>
            <div style="display:flex;align-items:flex-start;gap:10px;padding:12px 14px;background:{cor_bg};border-left:3px solid {cor_status};border-radius:6px;">
                <span style="font-size:16px;line-height:1;flex-shrink:0;">
                    {icone_mensagem}
                </span>
                <div style="font-family:{FONTE_TEXTO};font-size:13px;color:{cor_txt};line-height:1.55;font-weight:500;letter-spacing:-0.01em;">
                    {mensagem}
                </div>
            </div>
        </div>
    """).strip()

    st.markdown(html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# UTILITÁRIO — Contratos Pendentes por Segmento
# ═══════════════════════════════════════════════════════════════════════
def _build_df_pendentes(df_seg: pd.DataFrame) -> pd.DataFrame:
    MAPA = {
        "Contrato": [
            "CONTRATO",
            "Nº CONTRATO",
            "NUM_CONTRATO",
            "NUMERO CONTRATO",
            "NÚMERO CONTRATO",
            "CONTRATO_ID",
            "COD_CONTRATO",
            "CÓDIGO CONTRATO",
        ],
        "Login": [
            "LOGIN DO TÉCNICO",
            "LOGIN DO TECNICO",
            "LOGIN_DO_TECNICO",
            "LOGIN_TECNICO",
            "LOGIN TÉCNICO",
            "LOGIN TECNICO",
            "LOGIN",
            "USER",
            "USUÁRIO",
            "USUARIO",
            "USERNAME",
            "MATRÍCULA",
            "MATRICULA",
        ],
        "Técnico": [
            "TÉCNICO",
            "TECNICO",
            "NOME TÉCNICO",
            "NOME_TECNICO",
            "NOME DO TÉCNICO",
        ],
        "Monitor": ["MONITOR", "SUPERVISOR", "NOME MONITOR", "NOME_MONITOR"],
        "Qtde. O.S.": ["TOTAL DE TAREFAS"],
    }

    def _norm(s: str) -> str:
        return (
            unicodedata.normalize("NFKD", str(s))
            .encode("ascii", errors="ignore")
            .decode("ascii")
            .upper()
            .strip()
            .replace("_", " ")
            .replace(".", "")
        )

    def _achar(df: pd.DataFrame, cands: List[str]) -> Optional[str]:
        cols_norm = {_norm(c): c for c in df.columns}
        for cand in cands:
            cn = _norm(cand)
            if cn in cols_norm:
                return cols_norm[cn]
        for cand in cands:
            cn = _norm(cand)
            for col_norm, col_real in cols_norm.items():
                if cn in col_norm:
                    return col_real
        return None

    if "Status Contrato" in df_seg.columns:
        mask = (
            df_seg["Status Contrato"]
            .str.upper()
            .isin(["PENDENTE", "PENDING", "ABERTO", "EM ABERTO", "NÃO EXECUTADO"])
        )
    else:
        mask = pd.Series(True, index=df_seg.index)

    df_p = df_seg[mask].copy()
    if df_p.empty:
        return pd.DataFrame(
            columns=["Contrato", "Login", "Técnico", "Monitor", "Qtde. O.S."]
        )

    df_out = pd.DataFrame(index=df_p.index)
    for nome, cands in MAPA.items():
        col = _achar(df_p, cands)
        df_out[nome] = df_p[col].values if col else "N/D"

    if "Qtde. O.S." in df_out.columns:
        df_out["Qtde. O.S."] = (
            pd.to_numeric(df_out["Qtde. O.S."], errors="coerce").fillna(0).astype(int)
        )

    return (
        df_out.drop_duplicates()
        .sort_values("Técnico", na_position="last")
        .reset_index(drop=True)
        .pipe(lambda d: d.set_index(d.index + 1))
    )


# ═══════════════════════════════════════════════════════════════════════
# SUB-ABAS SEGMENTO
# ═══════════════════════════════════════════════════════════════════════
def _sub_visao_geral(
    segmento: str,
    df_seg: pd.DataFrame,
    m_seg: Dict[str, Any],
    p_ot: float,
    p_base: float,
    p_pess: float,
    sla_meta: float,
) -> None:
    render_section(f"📊 Resumo Operacional — {segmento}")
    tema_q: TemaKPI = "vermelho" if m_seg["quebra_atual"] > sla_meta else "verde"
    c1, c2, c3, c4, c5 = st.columns(5)
    render_kpi(
        c1, "Alocado", f"{int(m_seg['alocado']):,}".replace(",", "."), tema="azul"
    )
    render_kpi(
        c2, "Executadas", f"{int(m_seg['exec']):,}".replace(",", "."), tema="verde"
    )
    render_kpi(
        c3, "Não Exec.", f"{int(m_seg['naoexec']):,}".replace(",", "."), tema="laranja"
    )
    render_kpi(
        c4, "Pendentes", f"{int(m_seg['pend']):,}".replace(",", "."), tema="cinza"
    )
    render_kpi(
        c5,
        "Quebra Atual",
        f"{m_seg['quebra_atual']:.2%}",
        sub=f"Meta: {sla_meta:.0%}",
        tema=tema_q,
    )

    st.markdown("")
    render_section("🔮 Projeções de Fechamento")
    cen = {
        n: Motor.projetar(df_seg, p)
        for n, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]
    }
    c_cen, c_gauge = st.columns([2, 3])
    with c_cen:
        for nome, cd in cen.items():
            cor_p: TemaKPI = "vermelho" if cd["fechamento_proj"] > sla_meta else "verde"
            render_kpi_sm(
                st,
                nome,
                f"{cd['fechamento_proj']:.2%}",
                sub=f"Não Exec. proj.: {int(cd['naoexec_proj']):,}",
                tema=cor_p,
            )

    with c_gauge:
        cor_bar = "#EF4444" if m_seg["quebra_atual"] > sla_meta else "#10B981"
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number+delta",
                value=m_seg["quebra_atual"] * 100,
                delta={
                    "reference": sla_meta * 100,
                    "increasing": {"color": "#EF4444"},
                    "decreasing": {"color": "#10B981"},
                    "suffix": "%",
                },
                number={"suffix": "%", "font": {"size": 40}},
                gauge={
                    "axis": {"range": [0, 50], "ticksuffix": "%"},
                    "bar": {"color": cor_bar},
                    "steps": [
                        {"range": [0, sla_meta * 100], "color": "#DCFCE7"},
                        {"range": [sla_meta * 100, sla_meta * 120], "color": "#FEF9C3"},
                        {"range": [sla_meta * 120, 50], "color": "#FEE2E2"},
                    ],
                    "threshold": {
                        "line": {"color": "#DC2626", "width": 3},
                        "thickness": 0.85,
                        "value": sla_meta * 100,
                    },
                },
                title={"text": f"Quebra vs. Meta {sla_meta:.0%}", "font": {"size": 14}},
            )
        )
        fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("")
    render_section("🛡️ Folga de SLA")
    folga = Motor.folga_sla(df_seg, sla_meta)
    f1, f2, f3 = st.columns(3)
    cor_f: TemaKPI = (
        "vermelho"
        if folga["estourado"]
        else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
    )
    render_kpi(
        f1,
        "Folga (OS)",
        f"{int(np.floor(folga['folga_ne_pendente'])):,}",
        sub="Não Exec. ainda permitidas",
        tema=cor_f,
    )
    render_kpi(
        f2,
        "Execução Mínima",
        f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
        sub="Pendentes a executar para atingir meta",
        tema="azul",
    )
    render_kpi(
        f3,
        "Limite NE Total",
        f"{int(folga['limite_ne_total']):,}",
        sub=f"= {sla_meta:.0%} × {int(folga['alocado']):,}",
        tema="cinza",
    )


def _sub_causa_raiz_segmento(segmento: str, df_seg: pd.DataFrame) -> None:
    render_section(f"🔍 Causa Raiz — {segmento}")
    df_c = Motor.causa_raiz_segmento(df_seg, segmento, "_COL_BAIXA", top_n=8)
    if df_c.empty:
        render_insight(
            "Coluna de código/motivo de baixa não identificada.", tipo="alerta"
        )
        return

    c_tab, c_chart = st.columns([1.2, 2])
    with c_tab:
        render_dataframe_profundo(df_c, f"Top Motivos — {segmento}", "🔍", height=350)
    with c_chart:
        cor_bar = SEGMENTOS_CONFIG[segmento]["cor_primaria"]
        cor_linha = SEGMENTOS_CONFIG[segmento]["cor_secundaria"]
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_c["Motivo de Baixa"],
                y=df_c["Volume"],
                name="Volume",
                marker_color=cor_bar,
                text=df_c["Volume"],
                textposition="outside",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_c["Motivo de Baixa"],
                y=df_c["Acumulado"],
                name="Acumulado %",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color=cor_linha, width=2),
                marker=dict(size=7),
            )
        )
        fig.update_layout(
            title=f"Pareto de Motivos — {segmento}",
            yaxis=dict(title="Volume"),
            yaxis2=dict(
                title="Acumulado %",
                overlaying="y",
                side="right",
                tickformat=".0%",
                range=[0, 1.1],
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=380,
            xaxis=dict(tickangle=-30),
        )
        fig.add_hline(
            y=0.8,
            line_dash="dot",
            line_color="#F59E0B",
            yref="y2",
            annotation_text="80%",
            annotation_position="top right",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if len(df_c) >= 2:
        t1, t2 = df_c.iloc[0], df_c.iloc[1]
        render_insight(
            f"Os 2 principais motivos (**{t1['Motivo de Baixa']}** e **{t2['Motivo de Baixa']}**) "
            f"respondem por **{t2['Acumulado']:.1%}** das quebras.",
            tipo="acao",
        )


def _sub_tecnicos_segmento(
    segmento: str,
    df_seg: pd.DataFrame,
    p_base: float,
    min_aloc: float,
    top_n: int,
    sla_meta: float,
) -> None:
    render_section(f"👤 Técnicos com Maior Quebra — {segmento}")
    df_tec = Motor.tecnicos_criticos(df_seg, segmento, p_base, min_aloc, top_n)
    if df_tec.empty:
        render_insight("Não há técnicos com volume suficiente.", tipo="info")
        return

    render_dataframe_profundo(
        df_tec,
        f"Técnicos Críticos — {segmento}",
        "🚨",
        color_col="Fechamento Base",
        meta=sla_meta,
        height=450,
    )
    st.download_button(
        "📥 Exportar Técnicos",
        Utils.gerar_excel(df_tec, f"Tec_{segmento[:20]}"),
        f"tecnicos_{segmento.lower()}.xlsx",
        key=f"dl_tec_{segmento}",
    )

    df_plot = df_tec.head(10).sort_values("Fechamento Base")
    cores = [
        "#EF4444" if v > sla_meta else "#10B981" for v in df_plot["Fechamento Base"]
    ]
    fig = go.Figure(
        go.Bar(
            y=df_plot["TÉCNICO"],
            x=df_plot["Fechamento Base"],
            orientation="h",
            marker_color=cores,
            text=[f"{v:.1%}" for v in df_plot["Fechamento Base"]],
            textposition="outside",
        )
    )
    fig.add_vline(
        x=sla_meta,
        line_dash="dash",
        line_color="#DC2626",
        annotation_text=f"Meta {sla_meta:.0%}",
    )
    fig.update_layout(
        title="Quebra Projetada por Técnico",
        xaxis_tickformat=".1%",
        height=max(300, len(df_plot) * 36),
        margin=dict(t=40, b=20, l=10, r=60),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _sub_plano_acao(
    segmento: str,
    df_seg: pd.DataFrame,
    p_base: float,
    sla_meta: float,
) -> None:
    render_section(f"🎯 Plano de Ação — {segmento}")
    folga = Motor.folga_sla(df_seg, sla_meta)
    cen = Motor.projetar(df_seg, p_base)
    excesso = max(0.0, folga["naoexec"] - folga["limite_ne_total"])
    pend_exec = folga["precisa_executar_pendente"]

    col_d, col_a = st.columns([1, 1.5])
    with col_d:
        render_section("📋 Diagnóstico")
        render_kpi_sm(
            st,
            "Excesso de NE",
            f"{int(excesso):,}",
            sub="OS além do permitido",
            tema="vermelho" if excesso > 0 else "verde",
        )
        render_kpi_sm(
            st,
            "Pendentes a Executar",
            f"{int(np.ceil(pend_exec)):,}",
            sub=f"Mínimo para meta {sla_meta:.0%}",
            tema="azul",
        )
        render_kpi_sm(
            st,
            "Proj. Base",
            f"{cen['fechamento_proj']:.2%}",
            sub=f"c/ {p_base:.0%} de quebra nos pend.",
            tema="vermelho" if cen["fechamento_proj"] > sla_meta else "verde",
        )

    with col_a:
        render_section("✅ Ações Recomendadas")
        acoes: List[Tuple[str, str, str]] = []
        if folga["estourado"]:
            acoes.append(
                (
                    "🔴 IMEDIATA",
                    f"Acionar plantão para recuperar {int(excesso):,} OS não executadas.",
                    "critico",
                )
            )
        if pend_exec > 0:
            acoes.append(
                (
                    "🟠 ALTA",
                    f"Garantir execução de {int(np.ceil(pend_exec)):,} OS pendentes para atingir meta.",
                    "alerta",
                )
            )
        acoes.extend(SEGMENTOS_CONFIG[segmento]["acoes"])
        for pri, ac, tp in acoes:
            render_insight(f"**{pri}** — {ac}", tipo=cast(TipoInsight, tp))

    df_plano = pd.DataFrame(
        [{"Segmento": segmento, "Prioridade": p, "Ação": a} for p, a, _ in acoes]
    )
    if not df_plano.empty:
        st.download_button(
            "📥 Exportar Plano",
            Utils.gerar_excel(df_plano, f"Plano_{segmento[:20]}"),
            f"plano_{segmento.lower()}.xlsx",
            key=f"dl_plano_{segmento}",
        )


def _sub_pendentes(segmento: str, df_seg: pd.DataFrame) -> None:
    render_section(f"📋 Contratos Pendentes — {segmento}")
    df_pend = _build_df_pendentes(df_seg)
    total_pend = len(df_pend)

    m1, m2, m3 = st.columns(3)
    render_kpi(
        m1,
        "Total Pendentes",
        f"{total_pend:,}",
        sub="contratos sem execução",
        tema="laranja" if total_pend > 0 else "verde",
    )
    render_kpi(
        m2,
        "Técnicos Envolvidos",
        f"{df_pend['Técnico'].replace('N/D', pd.NA).dropna().nunique():,}",
        sub="com contrato pendente",
        tema="azul",
    )
    render_kpi(
        m3,
        "Monitores Envolvidos",
        f"{df_pend['Monitor'].replace('N/D', pd.NA).dropna().nunique():,}",
        sub="supervisionando pendências",
        tema="cinza",
    )

    st.markdown("")
    if df_pend.empty:
        render_insight("Nenhum contrato pendente encontrado.", tipo="ok")
        return

    with st.expander("🔎 Filtros rápidos", expanded=False):
        fc1, fc2 = st.columns(2)
        with fc1:
            f_tec = st.selectbox(
                "Técnico",
                ["Todos"]
                + sorted(
                    str(x)
                    for x in df_pend["Técnico"].dropna().unique()
                    if str(x) not in {"N/D", "nan"}
                ),
                key=f"pend_f_tec_{segmento}",
            )
        with fc2:
            f_mon = st.selectbox(
                "Monitor",
                ["Todos"]
                + sorted(
                    str(x)
                    for x in df_pend["Monitor"].dropna().unique()
                    if str(x) not in {"N/D", "nan"}
                ),
                key=f"pend_f_mon_{segmento}",
            )

    df_view = df_pend.copy()
    if f_tec != "Todos":
        df_view = df_view[df_view["Técnico"] == f_tec]
    if f_mon != "Todos":
        df_view = df_view[df_view["Monitor"] == f_mon]

    st.markdown(f"**Exibindo {len(df_view):,} de {total_pend:,} contratos pendentes**")
    render_dataframe_profundo(
        df_view.reset_index(drop=True), "Pendentes", "📋", height=480
    )

    st.markdown("")
    col_exp1, col_exp2, _ = st.columns([1, 1, 2])
    with col_exp1:
        st.download_button(
            "📥 Exportar Filtrado",
            Utils.gerar_excel(df_view, "Filtrado"),
            f"pendentes_{segmento.lower()}_filtrado.xlsx",
            key=f"dl_pend_f_{segmento}",
        )
    with col_exp2:
        st.download_button(
            "📥 Exportar Completo",
            Utils.gerar_excel(df_pend, "Completo"),
            f"pendentes_{segmento.lower()}_completo.xlsx",
            key=f"dl_pend_c_{segmento}",
        )


# ═══════════════════════════════════════════════════════════════════════
# VISÕES: Resumo Executivo, Análise Detalhada e Segmento
# ═══════════════════════════════════════════════════════════════════════
def render_visao_resumo(df: pd.DataFrame, meta_pct: float) -> None:
    if df.empty:
        render_insight("Sem dados para a Visão Resumo.", tipo="alerta")
        return

    with st.spinner("Gerando matriz corporativa..."):
        df_matriz = Motor.matriz_resumo(df)

    if df_matriz.empty:
        render_insight("Não foi possível gerar a matriz de resumo.", tipo="alerta")
        return

    total_row = df_matriz[df_matriz["Monitor"] == "Total Geral"].iloc[0]
    total_tar = int(total_row["Total Tarefas"])
    q_geral = float(total_row["Quebra Geral"])

    k1, k2, k3, k4 = st.columns(4)
    render_kpi(
        k1,
        "Total O.S.",
        f"{total_tar:,}".replace(",", "."),
        "Base válida analisada",
        "azul",
    )
    render_kpi(
        k2,
        "Quebra Consolidada",
        f"{q_geral:.2%}",
        "Todos os segmentos",
        "vermelho" if q_geral > meta_pct else "verde",
    )
    render_kpi(k3, "Meta Geral", f"{meta_pct:.0%}", "SLA Alvo", "cinza")

    pior_tipo = max(Config.ORDEM_TIPOS, key=lambda t: float(total_row.get(t, 0)))
    render_kpi(
        k4,
        "Segmento Crítico",
        pior_tipo,
        f"Quebra: {float(total_row[pior_tipo]):.2%}",
        "laranja",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    render_section("📋 Matriz de Desempenho (Monitor × Segmento)")
    st.markdown(
        '<div style="background:#F1F5F9;padding:12px;border-radius:6px;'
        'font-size:13px;color:#334155;margin-bottom:16px;">'
        "🧮 <b>Fórmula:</b> Não Executadas ÷ (Executadas + Não Executadas). "
        "Pendentes não entram no cálculo.</div>",
        unsafe_allow_html=True,
    )
    styler = estilizar_matriz(df_matriz, meta_pct)
    st.markdown(
        f'<div style="background:white;padding:5px;border-radius:12px;'
        f'box-shadow:0 4px 12px rgba(0,0,0,0.08);">'
        f'{styler.hide(axis="index").to_html()}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    c_dw1, _, _ = st.columns([1, 1, 3])
    with c_dw1:
        st.download_button(
            "📊 Baixar Matriz (Excel)",
            Utils.gerar_excel(df_matriz, "Matriz"),
            f"matriz_quebra_{datetime.now():%Y%m%d_%H%M}.xlsx",
            use_container_width=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    render_section("📊 Distribuição Visual")
    df_plot = df_matriz[df_matriz["Monitor"] != "Total Geral"].copy()
    fig = go.Figure()
    for tipo in Config.ORDEM_TIPOS:
        fig.add_trace(
            go.Bar(
                name=tipo,
                x=df_plot["Monitor"],
                y=df_plot[tipo],
                marker_color=Config.CORES_TIPO.get(tipo, "#64748B"),
                text=[_fmt_pct_br(v) for v in df_plot[tipo]],
                textposition="outside",
            )
        )
    fig.add_hline(
        y=meta_pct,
        line_dash="dash",
        line_color="#DC2626",
        annotation_text=f"META: {meta_pct:.0%}",
    )
    fig.update_layout(
        barmode="group",
        height=500,
        yaxis_tickformat=".0%",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_tab_causas(df: pd.DataFrame, meta: float) -> None:
    render_section("🔍 Análise Profunda de Causas Raiz")
    if df.empty:
        render_insight("Sem dados para análise de causas.", tipo="alerta")
        return

    df_ne = df[df["Status Contrato"] == "Não Executada"]
    total_ne = int(df_ne["TOTAL DE TAREFAS"].sum())
    motivos_unicos = (
        df_ne["_COL_BAIXA"].nunique() if "_COL_BAIXA" in df_ne.columns else 0
    )
    tec_afetados = df_ne["TÉCNICO"].nunique()

    kc1, kc2, kc3 = st.columns(3)
    render_kpi(kc1, "Total NE", _fmt_int_br(total_ne), "OSs não executadas", "vermelho")
    render_kpi(
        kc2, "Motivos Únicos", str(motivos_unicos), "Códigos de baixa distintos", "roxo"
    )
    render_kpi(
        kc3, "Técnicos Afetados", str(tec_afetados), "com pelo menos 1 NE", "laranja"
    )

    st.markdown("<br>", unsafe_allow_html=True)
    sub_geral, sub_seg, sub_mon, sub_reg = st.tabs(
        ["📊 Pareto Geral", "🏷️ Por Segmento", "👔 Por Monitor", "🗺️ Por Região"]
    )

    with sub_geral:
        df_causa = Motor.causa_raiz(df, "_COL_BAIXA", 10)
        if df_causa.empty:
            render_insight("Sem dados de motivos de baixa.", tipo="alerta")
        else:
            c1, c2 = st.columns([1.2, 2])
            with c1:
                render_dataframe_profundo(
                    df_causa, "Top 10 Motivos Gerais", "🔍", height=430
                )
            with c2:
                fig_p = go.Figure()
                fig_p.add_trace(
                    go.Bar(
                        x=df_causa["Motivo de Baixa"],
                        y=df_causa["Volume"],
                        name="Volume",
                        marker_color="#EF4444",
                        text=df_causa["Volume"],
                        textposition="outside",
                    )
                )
                fig_p.add_trace(
                    go.Scatter(
                        x=df_causa["Motivo de Baixa"],
                        y=df_causa["Acumulado"],
                        name="Acumulado %",
                        yaxis="y2",
                        mode="lines+markers",
                        line=dict(color="#0EA5E9", width=2),
                        marker=dict(size=8),
                    )
                )
                fig_p.add_hline(
                    y=0.8,
                    line_dash="dot",
                    line_color="#F59E0B",
                    yref="y2",
                    annotation_text="80%",
                    annotation_position="top right",
                )
                fig_p.update_layout(
                    title="Pareto de Motivos",
                    yaxis=dict(title="Volume"),
                    yaxis2=dict(
                        title="Acumulado %",
                        overlaying="y",
                        side="right",
                        tickformat=".0%",
                        range=[0, 1.1],
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    height=430,
                    xaxis=dict(tickangle=-30),
                    margin=dict(t=50, b=100),
                )
                st.plotly_chart(
                    fig_p, use_container_width=True, config={"displayModeBar": False}
                )

            if len(df_causa) >= 3:
                top3 = df_causa.iloc[2]
                render_insight(
                    f"💡 <b>Insight:</b> Os <b>3 principais motivos</b> "
                    f"(<b>{df_causa.iloc[0]['Motivo de Baixa']}</b>, "
                    f"<b>{df_causa.iloc[1]['Motivo de Baixa']}</b> e "
                    f"<b>{top3['Motivo de Baixa']}</b>) respondem por "
                    f"<b>{top3['Acumulado']:.1%}</b> de todas as quebras.",
                    tipo="info",
                )

    with sub_seg:
        df_seg = Motor.causa_por_segmento(df, "_COL_BAIXA", top_n=5)
        if df_seg.empty:
            render_insight("Sem dados de motivos por segmento.", tipo="alerta")
        else:
            segmentos_com_dados = df_seg["Segmento"].unique().tolist()
            for i in range(0, len(segmentos_com_dados), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    if i + j >= len(segmentos_com_dados):
                        break
                    seg = segmentos_com_dados[i + j]
                    df_s = df_seg[df_seg["Segmento"] == seg].copy()
                    cor = Config.CORES_TIPO.get(seg, "#64748B")
                    with col:
                        fig = go.Figure()
                        fig.add_trace(
                            go.Bar(
                                y=df_s["Motivo"],
                                x=df_s["Volume"],
                                orientation="h",
                                marker_color=cor,
                                text=[
                                    f"{int(v)} ({p:.1%})"
                                    for v, p in zip(
                                        df_s["Volume"], df_s["% no Segmento"]
                                    )
                                ],
                                textposition="outside",
                            )
                        )
                        fig.update_layout(
                            title=f"🏷️ {seg} — Top 5 Motivos",
                            height=280,
                            margin=dict(t=40, b=10, l=10, r=10),
                            yaxis=dict(autorange="reversed"),
                            xaxis=dict(title="Volume"),
                            showlegend=False,
                        )
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            config={"displayModeBar": False},
                        )
            st.markdown("<br>", unsafe_allow_html=True)
            render_dataframe_profundo(
                df_seg, "Todos os Motivos por Segmento", "📋", height=350
            )
            st.download_button(
                "📥 Baixar Motivos × Segmento",
                Utils.gerar_excel(df_seg, "Motivos_Segmento"),
                f"motivos_segmento_{datetime.now():%Y%m%d_%H%M}.xlsx",
                key="dl_causa_seg",
            )

    with sub_mon:
        df_mon = Motor.causa_por_monitor(df, "_COL_BAIXA", top_n_monitores=15)
        if df_mon.empty:
            render_insight("Sem dados de causas por monitor.", tipo="alerta")
        else:
            c1, c2 = st.columns([1.5, 1.5])
            with c1:
                render_dataframe_profundo(
                    df_mon, "Ranking Monitores + Motivo Principal", "👔", height=500
                )
            with c2:
                fig = px.bar(
                    df_mon.head(10),
                    x="Total NE",
                    y="Monitor",
                    orientation="h",
                    color="% do Motivo",
                    color_continuous_scale="Reds",
                    text=df_mon.head(10)["Total NE"].apply(_fmt_int_br),
                    title="Top 10 Monitores com Mais NE",
                    labels={
                        "Total NE": "Volume NE",
                        "% do Motivo": "% Motivo Principal",
                    },
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(
                    height=500,
                    yaxis=dict(autorange="reversed"),
                    margin=dict(t=50, b=10, l=10, r=10),
                )
                st.plotly_chart(
                    fig, use_container_width=True, config={"displayModeBar": False}
                )
            st.download_button(
                "📥 Baixar Causas por Monitor",
                Utils.gerar_excel(df_mon, "Motivos_Monitor"),
                f"motivos_monitor_{datetime.now():%Y%m%d_%H%M}.xlsx",
                key="dl_causa_mon",
            )

    with sub_reg:
        df_reg = Motor.causa_por_regiao(df, "_COL_BAIXA")
        if df_reg.empty:
            render_insight("Sem dados de causas por região.", tipo="alerta")
        else:
            df_hm = df_reg.set_index("Motivo").drop(columns=["Total"], errors="ignore")
            fig = px.imshow(
                df_hm,
                text_auto=True,
                aspect="auto",
                color_continuous_scale="Reds",
                labels=dict(x="Região", y="Motivo", color="Volume"),
            )
            fig.update_layout(
                title="🌡️ Mapa de Calor — Motivo × Região",
                height=500,
                margin=dict(t=50, b=10, l=10, r=10),
            )
            st.plotly_chart(
                fig, use_container_width=True, config={"displayModeBar": False}
            )
            st.markdown("<br>", unsafe_allow_html=True)
            render_dataframe_profundo(
                df_reg, "Matriz Motivo × Região", "🗺️", height=400
            )
            st.download_button(
                "📥 Baixar Motivos × Região",
                Utils.gerar_excel(df_reg, "Motivos_Regiao"),
                f"motivos_regiao_{datetime.now():%Y%m%d_%H%M}.xlsx",
                key="dl_causa_reg",
            )


def render_tab_backoffice(df: pd.DataFrame, meta: float) -> None:
    render_section("🚨 Central de Backoffice")
    if df.empty:
        render_insight("Sem dados para backoffice.", tipo="alerta")
        return

    df_ne = df[df["Status Contrato"] == "Não Executada"]
    df_pen = df[df["Status Contrato"] == "Pendente"]
    total_ne = int(df_ne["TOTAL DE TAREFAS"].sum())
    total_pen = int(df_pen["TOTAL DE TAREFAS"].sum())
    total_fila = total_ne + total_pen
    tec_fila = df[df["Status Contrato"].isin(["Não Executada", "Pendente"])][
        "TÉCNICO"
    ].nunique()

    kb1, kb2, kb3, kb4 = st.columns(4)
    render_kpi(
        kb1,
        "🚨 Total na Fila",
        _fmt_int_br(total_fila),
        "OSs para tratamento",
        "vermelho",
    )
    render_kpi(
        kb2, "❌ Não Executadas", _fmt_int_br(total_ne), "Prioridade alta", "laranja"
    )
    render_kpi(
        kb3, "⏳ Pendentes", _fmt_int_br(total_pen), "Aguardando execução", "cinza"
    )
    render_kpi(kb4, "👥 Técnicos na Fila", str(tec_fila), "com OSs para tratar", "azul")

    st.markdown("<br>", unsafe_allow_html=True)
    sub_fila, sub_rein, sub_crit = st.tabs(
        ["🚨 Fila Operacional", "🔄 Reincidência", "🏆 Ranking Críticos"]
    )

    with sub_fila:
        render_section("📋 Fila Priorizada por Score")
        st.markdown(
            '<div style="background:#F1F5F9;padding:12px;border-radius:6px;'
            'font-size:13px;color:#334155;margin-bottom:16px;">'
            "🎯 <b>Cálculo de Prioridade:</b> Score = (Não Exec. × 2) + Pendentes.<br>"
            "<b>Classificação:</b> 🔴 Crítico (≥20) · 🟠 Alta (≥10) · 🟡 Média (≥5) · 🟢 Baixa (<5)"
            "</div>",
            unsafe_allow_html=True,
        )
        df_fila = Motor.backoffice_fila(df)
        if df_fila.empty:
            render_insight("Sem OSs na fila de backoffice.", tipo="ok")
        else:
            classe_sel = st.multiselect(
                "🎯 Filtrar por Prioridade:",
                ["🔴 CRÍTICO", "🟠 ALTA", "🟡 MÉDIA", "🟢 BAIXA"],
                default=["🔴 CRÍTICO", "🟠 ALTA"],
            )
            df_fila_view = (
                df_fila[df_fila["Classificação"].isin(classe_sel)]
                if classe_sel
                else df_fila
            )
            k1, k2, k3, k4 = st.columns(4)
            for col, classe in zip(
                [k1, k2, k3, k4], ["🔴 CRÍTICO", "🟠 ALTA", "🟡 MÉDIA", "🟢 BAIXA"]
            ):
                qtd = int((df_fila["Classificação"] == classe).sum())
                cor = {
                    "🔴 CRÍTICO": "vermelho",
                    "🟠 ALTA": "laranja",
                    "🟡 MÉDIA": "amarelo",
                    "🟢 BAIXA": "verde",
                }[classe]
                render_kpi(col, classe, str(qtd), "registros", cor)
            st.markdown("<br>", unsafe_allow_html=True)
            render_dataframe_profundo(
                df_fila_view,
                f"Fila Priorizada — {len(df_fila_view)} registros",
                "🚨",
                height=500,
            )
            col_dl1, col_dl2, _ = st.columns([1, 1, 3])
            with col_dl1:
                st.download_button(
                    "📊 Baixar Fila (filtrada)",
                    Utils.gerar_excel(df_fila_view, "Fila_Backoffice"),
                    f"fila_backoffice_{datetime.now():%Y%m%d_%H%M}.xlsx",
                    use_container_width=True,
                    type="primary",
                    key="dl_fila_filt",
                )
            with col_dl2:
                st.download_button(
                    "📊 Baixar Fila (completa)",
                    Utils.gerar_excel(df_fila, "Fila_Backoffice_Completa"),
                    f"fila_backoffice_completa_{datetime.now():%Y%m%d_%H%M}.xlsx",
                    use_container_width=True,
                    key="dl_fila_full",
                )

    with sub_rein:
        render_section("🔄 Análise de Reincidência")
        st.markdown(
            '<div style="background:#F1F5F9;padding:12px;border-radius:6px;'
            'font-size:13px;color:#334155;margin-bottom:16px;">'
            "💡 <b>O que é reincidência:</b> Técnicos que apresentam o <b>mesmo motivo "
            "de quebra ≥ 2 vezes</b>.</div>",
            unsafe_allow_html=True,
        )
        col_conf1, _, _ = st.columns([1, 2, 2])
        with col_conf1:
            min_ocorr = st.number_input(
                "Mín. Ocorrências", min_value=2, max_value=20, value=2, step=1
            )
        df_rein = Motor.backoffice_reincidencia(df, "_COL_BAIXA", int(min_ocorr))
        if df_rein.empty:
            render_insight(
                f"✅ Nenhum caso de reincidência (≥{min_ocorr} ocorrências) encontrado.",
                tipo="ok",
            )
        else:
            kr1, kr2, kr3 = st.columns(3)
            render_kpi(
                kr1,
                "🔄 Casos Reincidentes",
                str(len(df_rein)),
                "combinações Técnico × Motivo",
                "vermelho",
            )
            render_kpi(
                kr2,
                "👥 Técnicos com Padrão",
                str(df_rein["Técnico"].nunique()),
                "reincidentes identificados",
                "laranja",
            )
            render_kpi(
                kr3,
                "📌 Motivos Repetidos",
                str(df_rein["Motivo"].nunique()),
                "diferentes causas",
                "roxo",
            )
            st.markdown("<br>", unsafe_allow_html=True)
            render_dataframe_profundo(
                df_rein, "Casos de Reincidência", "🔄", height=500
            )
            top = df_rein.iloc[0]
            render_insight(
                f"⚠️ <b>Caso mais crítico:</b> Técnico <b>{top['Técnico']}</b> "
                f"(Monitor: <b>{top['Monitor']}</b>) — motivo <b>'{top['Motivo']}'</b> "
                f"em <b>{int(top['Ocorrencias'])} ocorrências</b>.",
                tipo="critico",
            )
            st.download_button(
                "📥 Baixar Reincidências",
                Utils.gerar_excel(df_rein, "Reincidencia"),
                f"reincidencia_{datetime.now():%Y%m%d_%H%M}.xlsx",
                key="dl_rein",
            )

    with sub_crit:
        render_section("🏆 Top 15 Técnicos Críticos")
        df_crit = Motor.backoffice_ranking_criticos(df, top_n=15)
        if df_crit.empty:
            render_insight("Sem dados para ranking.", tipo="alerta")
        else:
            c1, c2 = st.columns([1.5, 1.5])
            with c1:
                render_dataframe_profundo(
                    df_crit, "Técnicos com Maior Fila", "🏆", height=500
                )
            with c2:
                fig = px.bar(
                    df_crit.head(10).sort_values("Total na Fila"),
                    x="Total na Fila",
                    y="Técnico",
                    orientation="h",
                    color="Total na Fila",
                    color_continuous_scale="Reds",
                    text=df_crit.head(10)
                    .sort_values("Total na Fila")["Total na Fila"]
                    .apply(_fmt_int_br),
                    title="Top 10 Técnicos com Maior Fila",
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(
                    height=500,
                    margin=dict(t=50, b=10, l=10, r=10),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(
                    fig, use_container_width=True, config={"displayModeBar": False}
                )
            st.download_button(
                "📥 Baixar Ranking Críticos",
                Utils.gerar_excel(df_crit, "Ranking_Criticos"),
                f"ranking_criticos_{datetime.now():%Y%m%d_%H%M}.xlsx",
                key="dl_crit",
            )


def render_tab_base_completa(df: pd.DataFrame) -> None:
    render_section("📋 Base Completa — Todos os Registros")
    if df.empty:
        render_insight("Sem dados para exibir.", tipo="alerta")
        return

    total = len(df)
    n_exec = int((df["Status Contrato"] == "Executada").sum())
    n_nex = int((df["Status Contrato"] == "Não Executada").sum())
    n_pend = int((df["Status Contrato"] == "Pendente").sum())
    n_tec = df["TÉCNICO"].nunique()
    n_mon = df["MONITOR"].nunique()

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    render_kpi(k1, "Total Registros", f"{total:,}".replace(",", "."), tema="azul")
    render_kpi(k2, "Executadas", f"{n_exec:,}".replace(",", "."), tema="verde")
    render_kpi(k3, "Não Executadas", f"{n_nex:,}".replace(",", "."), tema="vermelho")
    render_kpi(k4, "Pendentes", f"{n_pend:,}".replace(",", "."), tema="cinza")
    render_kpi(k5, "Técnicos", f"{n_tec:,}".replace(",", "."), tema="laranja")
    render_kpi(k6, "Monitores", f"{n_mon:,}".replace(",", "."), tema="amarelo")

    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("🔎 Filtros da Tabela", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            f_status = st.multiselect(
                "Status",
                ["Executada", "Não Executada", "Pendente"],
                default=["Executada", "Não Executada", "Pendente"],
                key="base_f_status",
            )
        with fc2:
            opcoes_seg = ["Todos"] + sorted(
                df["TIPO_SERVICO"].dropna().unique().tolist()
            )
            f_seg = st.selectbox("Segmento", opcoes_seg, key="base_f_seg")
        with fc3:
            opcoes_mon = ["Todos"] + sorted(
                str(x)
                for x in df["MONITOR"].dropna().unique()
                if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
            )
            f_mon = st.selectbox("Monitor", opcoes_mon, key="base_f_mon")
        with fc4:
            opcoes_tec = ["Todos"] + sorted(
                str(x)
                for x in df["TÉCNICO"].dropna().unique()
                if str(x) not in {"nan", "NÃO MAPEADO"}
            )
            f_tec = st.selectbox("Técnico", opcoes_tec, key="base_f_tec")

    df_view = df.copy()
    if f_status:
        df_view = df_view[df_view["Status Contrato"].isin(f_status)]
    if f_seg != "Todos":
        df_view = df_view[df_view["TIPO_SERVICO"] == f_seg]
    if f_mon != "Todos":
        df_view = df_view[df_view["MONITOR"] == f_mon]
    if f_tec != "Todos":
        df_view = df_view[df_view["TÉCNICO"] == f_tec]

    st.markdown(
        f"**Exibindo {len(df_view):,} de {total:,} registros**".replace(",", ".")
    )

    colunas_internas = [c for c in df_view.columns if str(c).startswith("_")]
    _PRIORITY_COLS = [
        "MONITOR",
        "TÉCNICO",
        "TIPO_SERVICO",
        "Status Contrato",
        "TOTAL DE TAREFAS",
        "REGIÃO",
        "FLAG_GPON",
    ]
    cols_priority = [c for c in _PRIORITY_COLS if c in df_view.columns]
    cols_resto = [
        c
        for c in df_view.columns
        if c not in cols_priority and c not in colunas_internas
    ]
    cols_exibir = cols_priority + cols_resto

    df_exibir = df_view[cols_exibir].copy().reset_index(drop=True)
    df_exibir.index = df_exibir.index + 1

    _COLS_INTEIRAS = ["TOTAL DE TAREFAS", "QTD TAREFAS", "QUANTIDADE", "QTDE"]
    for col in df_exibir.columns:
        col_upper = str(col).upper().strip()
        if any(k in col_upper for k in _COLS_INTEIRAS):
            df_exibir[col] = (
                pd.to_numeric(df_exibir[col], errors="coerce").fillna(0).astype(int)
            )

    def _colorir_status(val: Any) -> str:
        v = str(val).strip()
        if v == "Executada":
            return "background-color:#DCFCE7;color:#166534;font-weight:600;"
        if v == "Não Executada":
            return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"
        if v == "Pendente":
            return "background-color:#F1F5F9;color:#475569;font-weight:600;"
        return ""

    def _colorir_gpon(val: Any) -> str:
        v = str(val).strip().upper()
        if v == "SIM":
            return "background-color:#FEF3C7;color:#92400E;font-weight:700;"
        if v in {"NÃO", "NAO"}:
            return "background-color:#F1F5F9;color:#64748B;"
        return ""

    styler = df_exibir.style.set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background-color", "#0F172A"),
                    ("color", "#FFFFFF"),
                    ("font-size", "0.75rem"),
                    ("font-weight", "700"),
                    ("text-transform", "uppercase"),
                    ("padding", "0.5rem 0.8rem"),
                    ("white-space", "nowrap"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("font-size", "0.78rem"),
                    ("padding", "0.4rem 0.8rem"),
                    ("border-bottom", "1px solid #F1F5F9"),
                    ("white-space", "nowrap"),
                ],
            },
        ]
    )
    if "Status Contrato" in df_exibir.columns:
        styler = styler.map(_colorir_status, subset=["Status Contrato"])
    if "FLAG_GPON" in df_exibir.columns:
        styler = styler.map(_colorir_gpon, subset=["FLAG_GPON"])
    if "TIPO_SERVICO" in df_exibir.columns:
        _CORES_SEG = {
            "Migração": "background-color:#E0F2FE;color:#0369A1;font-weight:600;",
            "Novos Domicílios": "background-color:#DBEAFE;color:#1E40AF;font-weight:600;",
            "PME": "background-color:#EDE9FE;color:#6D28D9;font-weight:600;",
            "Outros": "background-color:#F1F5F9;color:#64748B;",
        }
        styler = styler.map(
            lambda v: _CORES_SEG.get(str(v), ""), subset=["TIPO_SERVICO"]
        )
    if "TOTAL DE TAREFAS" in df_exibir.columns:
        styler = styler.format({"TOTAL DE TAREFAS": "{:,.0f}"})

    st.dataframe(styler, use_container_width=True, hide_index=False, height=600)

    col_dl1, col_dl2, _ = st.columns([1, 1, 3])
    with col_dl1:
        st.download_button(
            "📥 Baixar Filtrado (Excel)",
            Utils.gerar_excel(
                df_view[cols_exibir].reset_index(drop=True), "Base_Filtrada"
            ),
            f"base_filtrada_{datetime.now():%Y%m%d_%H%M}.xlsx",
            use_container_width=True,
            type="primary",
            key="dl_base_filt",
        )
    with col_dl2:
        st.download_button(
            "📥 Baixar Completo (Excel)",
            Utils.gerar_excel(
                (
                    df[cols_exibir].reset_index(drop=True)
                    if cols_exibir
                    else df.reset_index(drop=True)
                ),
                "Base_Completa",
            ),
            f"base_completa_{datetime.now():%Y%m%d_%H%M}.xlsx",
            use_container_width=True,
            key="dl_base_full",
        )


def render_visao_detalhada(
    df: pd.DataFrame,
    p_ot: float,
    p_base: float,
    p_pess: float,
    meta: float,
) -> None:
    m = Motor.projetar(df, p_base)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    render_kpi(k1, "Alocado", f"{int(m['alocado']):,}".replace(",", "."), tema="azul")
    render_kpi(k2, "Executadas", f"{int(m['exec']):,}".replace(",", "."), tema="verde")
    render_kpi(
        k3, "Não Exec", f"{int(m['naoexec']):,}".replace(",", "."), tema="laranja"
    )
    render_kpi(k4, "Pendentes", f"{int(m['pend']):,}".replace(",", "."), tema="cinza")
    render_kpi(
        k5,
        "Quebra Atual",
        f"{m['quebra_atual']:.2%}",
        tema="vermelho" if m["quebra_atual"] > meta else "verde",
    )
    render_kpi(
        k6,
        "Proj. Base",
        f"{m['fechamento_proj']:.2%}",
        tema="vermelho" if m["fechamento_proj"] > meta else "roxo",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    t_proj, t_rank, t_causa, t_back, t_base = st.tabs(
        [
            "🔮 Projeções SLA",
            "🧭 Rankings",
            "🔍 Causas",
            "🚨 Backoffice",
            "📋 Base Completa",
        ]
    )

    with t_proj:
        render_section("🔮 Análise e Simulações de Fechamento")
        cen = {
            "Otimista": Motor.projetar(df, p_ot),
            "Base": m,
            "Pessimista": Motor.projetar(df, p_pess),
        }
        c1, c2 = st.columns([1, 1])
        with c1:
            for n, c in cen.items():
                render_kpi_sm(
                    st,
                    f"Cenário {n}",
                    f"{c['fechamento_proj']:.2%}",
                    sub=f"Não Exec. Projetadas: {int(c['naoexec_proj'])}",
                    tema="vermelho" if c["fechamento_proj"] > meta else "verde",
                )
        with c2:
            folga = Motor.folga_sla(df, meta)
            render_kpi_sm(
                st,
                "Garantia Mínima",
                f"{int(np.ceil(folga['precisa_executar_pendente']))} OS",
                sub="Pendentes a executar para atingir meta",
                tema="azul",
            )
            render_kpi_sm(
                st,
                "Folga no SLA",
                f"{int(np.floor(folga['folga_ne_pendente']))} OS",
                sub="OS permitidas como não executadas",
                tema="laranja",
            )

    with t_rank:
        t_mon, t_tec = st.tabs(["👔 Monitores", "👤 Técnicos"])
        with t_mon:
            df_rm = Motor.tabela_cenarios(df, "MONITOR", p_ot, p_base, p_pess, 1)
            render_dataframe_profundo(
                df_rm,
                "Ranking Monitores",
                "👔",
                color_col="Fechamento Base",
                meta=meta,
                height=500,
            )
            if not df_rm.empty:
                st.download_button(
                    "📥 Baixar Monitores",
                    Utils.gerar_excel(df_rm, "Monitores"),
                    f"rank_monitores_{datetime.now():%Y%m%d_%H%M}.xlsx",
                    key="dl_rm",
                )
        with t_tec:
            df_rt = Motor.tabela_cenarios(df, "TÉCNICO", p_ot, p_base, p_pess, 1)
            render_dataframe_profundo(
                df_rt,
                "Ranking Técnicos",
                "👤",
                color_col="Fechamento Base",
                meta=meta,
                height=500,
            )
            if not df_rt.empty:
                st.download_button(
                    "📥 Baixar Técnicos",
                    Utils.gerar_excel(df_rt, "Técnicos"),
                    f"rank_tecnicos_{datetime.now():%Y%m%d_%H%M}.xlsx",
                    key="dl_rt",
                )

    with t_causa:
        render_tab_causas(df, meta)
    with t_back:
        render_tab_backoffice(df, meta)
    with t_base:
        render_tab_base_completa(df)


def render_visao_segmento(
    df_full: pd.DataFrame,
    segmento: str,
    p_ot: float,
    p_base: float,
    p_pess: float,
    sla_meta: float,
    min_aloc: float = 1.0,
    top_n: int = 999_999,
) -> None:
    """Fluxo completo de análise por segmento (Migração ou PME) com PDF."""
    if "TIPO_SERVICO" not in df_full.columns:
        df_full, df_full["TIPO_SERVICO"] = classificar_tipo_servico(df_full)

    regioes = (
        [
            str(r).strip().upper()
            for r in df_full[Config.COL_REGIAO].dropna().unique()
            if str(r).strip()
        ]
        if Config.COL_REGIAO in df_full.columns
        else ["OUTRAS"]
    )
    _render_hero_segmento(segmento, regioes, len(df_full))

    df_seg = df_full[df_full["TIPO_SERVICO"] == segmento].copy()
    if df_seg.empty:
        render_insight(
            f"Nenhum registro classificado como **{segmento}** nos filtros atuais.  \n"
            "Verifique os critérios centralizados de classificação.",
            tipo="info",
        )
        return

    m_seg = Motor.projetar(df_seg, p_base)
    _render_card_status(segmento, m_seg, sla_meta)
    st.markdown("")

    # PDF Executivo
    col_btn, col_desc = st.columns([1, 3])
    with col_btn:
        with st.spinner("Gerando PDF..."):
            pdf_bytes = SEGMENTOS_CONFIG[segmento]["pdf_class"].gerar(
                df=df_seg,
                sla_meta=sla_meta,
                p_ot=p_ot,
                p_base=p_base,
                p_pess=p_pess,
                min_aloc=min_aloc,
                top_n=min(top_n, 15),
            )
        st.download_button(
            label=f"📄 Baixar PDF — {segmento}",
            data=pdf_bytes,
            file_name=f"relatorio_{segmento.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            key=f"pdf_dl_{segmento}",
            use_container_width=True,
            type="primary",
        )
    with col_desc:
        render_insight(
            "O PDF inclui métricas, projeções, top técnicos e plano de ação.",
            tipo="info",
        )

    st.divider()

    sub1, sub2, sub3, sub4, sub5 = st.tabs(
        [
            "📊 Visão Geral",
            "🔍 Causa Raiz",
            "👤 Técnicos",
            "🎯 Plano de Ação",
            "📋 Pendentes",
        ]
    )
    with sub1:
        _sub_visao_geral(segmento, df_seg, m_seg, p_ot, p_base, p_pess, sla_meta)
    with sub2:
        _sub_causa_raiz_segmento(segmento, df_seg)
    with sub3:
        _sub_tecnicos_segmento(segmento, df_seg, p_base, min_aloc, top_n, sla_meta)
    with sub4:
        _sub_plano_acao(segmento, df_seg, p_base, sla_meta)
    with sub5:
        _sub_pendentes(segmento, df_seg)


# ═══════════════════════════════════════════════════════════════════════
# SANITIZAÇÃO E SIDEBAR
# ═══════════════════════════════════════════════════════════════════════
def garantir_colunas_criticas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "MONITOR" not in df.columns:
        col_mon_alt = next(
            (
                c
                for c in df.columns
                if str(c).strip().upper() in ("MONITOR", "GESTOR", "SUPERVISOR")
            ),
            None,
        )
        df["MONITOR"] = (
            df[col_mon_alt].fillna("SEM MONITOR").astype(str).str.strip().str.upper()
            if col_mon_alt
            else "SEM MONITOR"
        )
    if "TÉCNICO" not in df.columns:
        col_tec_alt = next(
            (
                c
                for c in df.columns
                if str(c).strip().upper()
                in ("TÉCNICO", "TECNICO", "NOME", "NOME TÉCNICO")
            ),
            None,
        )
        df["TÉCNICO"] = (
            df[col_tec_alt].fillna("NÃO MAPEADO").astype(str).str.strip().str.upper()
            if col_tec_alt
            else "NÃO MAPEADO"
        )
    df.loc[df["MONITOR"].isin(["", "NAN", "NONE", "NULL"]), "MONITOR"] = "SEM MONITOR"
    df.loc[df["TÉCNICO"].isin(["", "NAN", "NONE", "NULL"]), "TÉCNICO"] = "NÃO MAPEADO"
    return df


def render_sidebar(df_full: pd.DataFrame) -> Dict[str, Any]:
    with st.sidebar:
        st.markdown("### 👁️ Selecione a Visão")
        visao = st.radio(
            "Módulo:",
            [
                "📑 Resumo Executivo (Matriz)",
                "📈 Análise Detalhada (Projeções)",
                "🔄 Segmento — Migração",
                "🏢 Segmento — PME",
                "📊 Critérios de Classificação",
            ],
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("### 🎯 Filtros Globais")

        monitores = ["Todos"] + sorted(
            str(x)
            for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon = st.selectbox("👔 Monitor", monitores)
        df_filt = (
            df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]
        )

        tecnicos = ["Todos"] + sorted(
            str(x)
            for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        )
        sel_tec = st.selectbox("👤 Técnico", tecnicos)
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.caption(f"📊 **{len(df):,}** registros após filtros".replace(",", "."))

        st.divider()
        st.subheader("🔮 Cenários de Projeção")
        p_ot = st.slider("Otimista (%)", 0, 100, 15, 5) / 100.0

        # SLA dinâmico conforme visão
        if visao == "🔄 Segmento — Migração":
            default_base = 25
            default_sla = float(Config.SLA_MIGRACAO * 100)
        elif visao == "🏢 Segmento — PME":
            default_base = 20
            default_sla = float(Config.SLA_PME * 100)
        else:
            default_base = 20
            default_sla = float(Config.SLA_QUEBRA_MAXIMA * 100)

        p_base = st.slider("Base (%)", 0, 100, default_base, 5) / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 50, 5) / 100.0

        st.divider()
        meta = st.number_input("🎯 Meta SLA (%)", 0.0, 100.0, default_sla, 0.5) / 100.0

        st.divider()
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("🔄 Reiniciar", use_container_width=True):
                st.session_state["df_memoria"] = None
                st.rerun()
        with col_r2:
            if st.button("🗑️ Limpar Cache", use_container_width=True):
                st.cache_data.clear()
                st.session_state["df_memoria"] = None
                st.rerun()

        st.divider()
        render_debug_criterios(df_full, expanded=False)

    return {
        "visao": visao,
        "df": df,
        "df_full": df_full,
        "p_ot": p_ot,
        "p_base": p_base,
        "p_pess": p_pess,
        "meta": meta,
    }


# ═══════════════════════════════════════════════════════════════════════
# FLUXO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
def main() -> None:
    if st.session_state["df_memoria"] is None:
        render_hero_upload()
        render_card_destaque_migracao()

        render_section("📁 Importação de Dados")
        arq = st.file_uploader("Selecione a base (Excel/CSV)", type=["xlsx", "csv"])

        if arq:
            with st.spinner("🔄 Limpando dados e classificando segmentos..."):
                raw = DataLoader.ler_arquivo(arq.getvalue(), arq.name)
                gs = DataLoader.buscar_gsheets()
                df_proc = DataLoader.preparar_base(raw, gs)
                df_proc = garantir_colunas_criticas(df_proc)
                st.session_state["df_memoria"] = df_proc

            n_susp = df_proc.attrs.get("removidos_suspensos", 0)
            n_con = df_proc.attrs.get("removidos_contrato", 0)
            col_atv = df_proc.attrs.get("col_status_atividade", None)
            col_con = df_proc.attrs.get("col_contrato", None)
            total = len(raw)
            restou = len(df_proc)

            render_section("🧹 Relatório de Limpeza da Base")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📥 Total Importado", f"{total:,}".replace(",", "."))
            c2.metric(
                "🚫 Suspensos Removidos",
                f"{n_susp:,}".replace(",", "."),
                delta=f"-{n_susp}" if n_susp else None,
                delta_color="inverse",
            )
            c3.metric(
                "📄 Contratos Inválidos",
                f"{n_con:,}".replace(",", "."),
                delta=f"-{n_con}" if n_con else None,
                delta_color="inverse",
            )
            c4.metric("✅ Base Final", f"{restou:,}".replace(",", "."))

            if not col_atv:
                st.warning(
                    "⚠️ STATUS DA ATIVIDADE não detectada — suspensos não removidos."
                )
            else:
                st.success(f"✅ `{col_atv}` → **{n_susp}** suspensos removidos")

            if not col_con:
                st.warning("⚠️ CONTRATO não detectada — inválidos não removidos.")
            else:
                st.success(
                    f"✅ `{col_con}` → **{n_con}** contratos inválidos removidos"
                )

            if df_proc.attrs.get("merge_aplicado"):
                matches = df_proc.attrs.get("merge_matches", 0)
                total_m = df_proc.attrs.get("merge_total", len(df_proc))
                st.toast(
                    f"✅ Merge: {matches:,}/{total_m:,}".replace(",", "."), icon="🔗"
                )
            else:
                st.toast("⚠️ lista_ativos não carregada", icon="⚠️")

            st.rerun()
        return

    df_full = st.session_state["df_memoria"].copy()
    df_full = garantir_colunas_criticas(df_full)
    st.session_state["df_memoria"] = df_full

    config_user = render_sidebar(df_full)
    visao = config_user["visao"]
    df = config_user["df"]
    p_ot = config_user["p_ot"]
    p_base = config_user["p_base"]
    p_pess = config_user["p_pess"]
    meta = config_user["meta"]

    regioes_disp = (
        sorted(df[Config.COL_REGIAO].unique())
        if Config.COL_REGIAO in df.columns
        else ["OUTRAS"]
    )

    # Configuração dinâmica de hero
    HEROES = {
        "📑 Resumo Executivo (Matriz)": (
            "📉 Super Relatório de Quebra — Resumo Executivo",
            "Matriz Monitor × Segmento · Novos Domicílios · Migração · PME",
            "VISÃO CONSOLIDADA",
        ),
        "📊 Critérios de Classificação": (
            "📊 Super Relatório de Quebra — Critérios de Classificação",
            "Análise de regras e volumes por TOTAL DE TAREFAS",
            "AUDITORIA DE CRITÉRIOS",
        ),
        "📈 Análise Detalhada (Projeções)": (
            "📉 Super Relatório de Quebra — Análise Detalhada",
            "Projeções · Rankings · Causas · Backoffice · Base Completa",
            "VISÃO OPERACIONAL",
        ),
    }

    # Renderiza hero comum para visões globais; segmentos usam hero próprio
    if visao in HEROES:
        titulo_visao, subtitulo_visao, badge_visao = HEROES[visao]
        render_hero_topo_fixo(
            titulo=titulo_visao,
            subtitulo=subtitulo_visao,
            regioes=list(regioes_disp),
            total=len(df),
            badge=badge_visao,
        )

    # Roteamento
    if visao == "📊 Critérios de Classificação":
        render_painel_criterios(df_full)
        return

    if df.empty:
        render_insight(
            "🔍 <b>Nenhum dado para os filtros selecionados.</b><br>"
            "Ajuste os filtros na barra lateral ou clique em <b>🔄 Reiniciar</b>.",
            tipo="alerta",
        )
        return

    if visao == "📑 Resumo Executivo (Matriz)":
        render_visao_resumo(df, meta)
    elif visao == "📈 Análise Detalhada (Projeções)":
        render_visao_detalhada(df, p_ot, p_base, p_pess, meta)
    elif visao == "🔄 Segmento — Migração":
        render_visao_segmento(df, "Migração", p_ot, p_base, p_pess, meta)
    elif visao == "🏢 Segmento — PME":
        render_visao_segmento(df, "PME", p_ot, p_base, p_pess, meta)


if __name__ == "__main__":
    main()
