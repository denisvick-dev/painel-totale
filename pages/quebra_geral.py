"""
quebra.py
=========
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


# ═══════════════════════════════════════════════════════════════════════
# VISUALIZAÇÃO DOS MÓDULOS DE NAVEGAÇÃO
# ═══════════════════════════════════════════════════════════════════════
def view_resumo_executivo(df: pd.DataFrame, meta_sla: float) -> None:
    render_section("📊 Resumo Executivo — Matriz de Quebra por Monitor")
    df_valid = df[df["TIPO_SERVICO"] != "Outros"]
    regioes = df_valid["REGIÃO"].unique().tolist()
    total_reg = len(df_valid)

    mat = Motor.matriz_resumo(df)
    if mat.empty:
        st.warning("⚠️ Dados insuficientes para montar a Matriz Resumo.")
        return

    st.markdown(
        f'<div style="font-size:0.85rem;color:#64748B;margin-bottom:1rem;">'
        f"Visão consolidada do percentual de quebra (% Não Executadas sobre Executadas + Não Executadas) "
        f"por Monitor e Segmento Operacional. "
        f'Células em <span style="color:#991B1B;font-weight:700;">vermelho</span> '
        f"indicam quebra acima da meta de <b>{meta_sla:.0%}</b>.</div>",
        unsafe_allow_html=True,
    )

    styler = estilizar_matriz(mat, meta_sla)
    st.dataframe(styler, use_container_width=True, hide_index=True, height=520)

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        st.download_button(
            "📥 Baixar Matriz (Excel)",
            data=Utils.gerar_excel(mat, "Matriz_Resumo"),
            file_name=f"matriz_resumo_quebra_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        render_section("📈 Quebra Geral por Segmento")
        df_seg = (
            df_valid.groupby("TIPO_SERVICO")
            .agg(
                Executadas=(
                    "TOTAL DE TAREFAS",
                    lambda x: x[
                        df_valid.loc[x.index, "Status Contrato"] == "Executada"
                    ].sum(),
                ),
                NaoExecutadas=(
                    "TOTAL DE TAREFAS",
                    lambda x: x[
                        df_valid.loc[x.index, "Status Contrato"] == "Não Executada"
                    ].sum(),
                ),
                Total=("TOTAL DE TAREFAS", "sum"),
            )
            .reset_index()
        )
        df_seg["Considerado"] = df_seg["Executadas"] + df_seg["NaoExecutadas"]
        df_seg["Quebra %"] = np.where(
            df_seg["Considerado"] > 0,
            df_seg["NaoExecutadas"] / df_seg["Considerado"],
            0,
        )

        fig = px.bar(
            df_seg,
            x="TIPO_SERVICO",
            y="Quebra %",
            color="TIPO_SERVICO",
            color_discrete_map=Config.CORES_TIPO,
            text=df_seg["Quebra %"].apply(_fmt_pct_br),
            labels={"TIPO_SERVICO": "Segmento", "Quebra %": "% Quebra"},
        )
        fig.add_shape(
            type="line",
            x0=-0.5,
            x1=len(df_seg) - 0.5,
            y0=meta_sla,
            y1=meta_sla,
            line=dict(color="#DC2626", width=2, dash="dash"),
        )
        fig.update_layout(
            showlegend=False,
            height=320,
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis=dict(tickformat=".0%"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        render_section("🧩 Distribuição de Volume Por Status")
        df_st = (
            df_valid.groupby("Status Contrato")["TOTAL DE TAREFAS"].sum().reset_index()
        )
        fig_pie = px.pie(
            df_st,
            names="Status Contrato",
            values="TOTAL DE TAREFAS",
            color="Status Contrato",
            color_discrete_map=Config.CORES_STATUS,
            hole=0.4,
        )
        fig_pie.update_layout(
            height=320,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig_pie, use_container_width=True)


def view_analise_detalhada(df: pd.DataFrame, meta_sla: float) -> None:
    st.markdown("### 🔍 Módulo de Análise Detalhada & Operacional")
    t1, t2, t3, t4, t5 = st.tabs(
        [
            "🔮 Projeções & SLA",
            "🏆 Rankings & Pior Caso",
            "🪵 Causa Raiz & Pareto",
            "🚨 Fila de Backoffice",
            "💾 Base Higienizada",
        ]
    )

    with t1:
        render_section("🔮 Projeção de Fechamento de Quebra")
        c_proj1, c_proj2 = st.columns([1, 2])
        with c_proj1:
            p_pen = (
                st.slider(
                    "Probabilidade de Quebra nos Pendentes (%):",
                    min_value=0,
                    max_value=100,
                    value=30,
                    step=5,
                    help="Taxa estimada de não execução para as tarefas que ainda estão pendentes.",
                )
                / 100.0
            )
            proj = Motor.projetar(df, p_pen)
            folga = Motor.folga_sla(df, meta_sla)

            k1, k2 = st.columns(2)
            render_kpi_sm(
                k1,
                "Quebra Atual",
                _fmt_pct_br(proj["quebra_atual"]),
                "Realizada até agora",
                "laranja" if proj["quebra_atual"] > meta_sla else "verde",
            )
            render_kpi_sm(
                k2,
                "Fechamento Projetado",
                _fmt_pct_br(proj["fechamento_proj"]),
                f"Com {p_pen:.0%} nos pendentes",
                "vermelho" if proj["fechamento_proj"] > meta_sla else "azul",
            )

            if folga["estourado"]:
                render_insight(
                    f"⚠️ <b>SLA Estourado!</b> O volume atual de Não Executadas ({int(folga['naoexec'])}) "
                    f"já superou o limite máximo do SLA ({int(folga['limite_ne_total'])}).",
                    "critico",
                )
            else:
                render_insight(
                    f"✅ <b>Dentro do SLA:</b> Você ainda pode ter até <b>{int(folga['folga_ne_pendente'])}</b> "
                    f"tarefas Não Executadas nos pendentes sem estourar a meta de {meta_sla:.0%}.",
                    "ok",
                )

        with c_proj2:
            st.markdown("#### Cenários de Fechamento por Monitor")
            tab_cen = Motor.tabela_cenarios(
                df, "MONITOR", p_ot=0.15, p_base=0.30, p_pess=0.50, min_aloc=5
            )
            render_dataframe_profundo(
                tab_cen,
                "Simulação de Cenários por Monitor",
                "🎭",
                color_col="Fechamento Base",
                meta=meta_sla,
                height=320,
            )

    with t2:
        render_section("🏆 Rankings da Operação & Pior Caso")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("##### 🔴 Monitores com Maior Taxa de Quebra")
            tab_mon = Motor.tabela_cenarios(
                df, "MONITOR", p_ot=0.15, p_base=0.30, p_pess=0.50, min_aloc=5
            )
            render_dataframe_profundo(
                tab_mon.head(10),
                "Top 10 Monitores Críticos",
                "📊",
                color_col="Quebra Atual",
                meta=meta_sla,
            )

        with col_r2:
            st.markdown("##### 👷 Técnicos Críticos (Maior Volume NE + Pendente)")
            tab_tec = Motor.tabela_cenarios(
                df, "TÉCNICO", p_ot=0.15, p_base=0.30, p_pess=0.50, min_aloc=3
            )
            render_dataframe_profundo(
                tab_tec.head(10),
                "Top 10 Técnicos Críticos",
                "👷",
                color_col="Fechamento Base",
                meta=meta_sla,
            )

    with t3:
        render_section("🪵 Análise de Causa Raiz & Pareto")
        c_par1, c_par2 = st.columns([2, 1])
        df_causa = Motor.causa_raiz(df, "_COL_BAIXA", top_n=10)

        with c_par1:
            if not df_causa.empty:
                fig_par = go.Figure()
                fig_par.add_trace(
                    go.Bar(
                        x=df_causa["Motivo de Baixa"],
                        y=df_causa["Volume"],
                        name="Volume NE",
                        marker_color="#EF4444",
                    )
                )
                fig_par.add_trace(
                    go.Scatter(
                        x=df_causa["Motivo de Baixa"],
                        y=df_causa["Acumulado"],
                        name="% Acumulado",
                        yaxis="y2",
                        line=dict(color="#1E3A8A", width=3),
                    )
                )
                fig_par.update_layout(
                    height=380,
                    margin=dict(l=20, r=20, t=20, b=20),
                    yaxis=dict(title="Volume de Não Executadas"),
                    yaxis2=dict(
                        title="% Acumulado",
                        overlaying="y",
                        side="right",
                        tickformat=".0%",
                        range=[0, 1.05],
                    ),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig_par, use_container_width=True)
            else:
                st.info("Sem dados de causa raiz.")

        with c_par2:
            render_dataframe_profundo(
                df_causa, "Tabela de Causas (Pareto)", "📌", height=380
            )

    with t4:
        render_section("🚨 Gestão de Fila & Reincidência de Backoffice")
        fb1, fb2 = st.columns(2)
        with fb1:
            st.markdown("##### 📥 Fila Operacional Pendente / NE")
            fila = Motor.backoffice_fila(df)
            render_dataframe_profundo(
                fila.head(15), "Prioridade na Fila", "⚡", height=350
            )

        with fb2:
            st.markdown("##### 🔄 Reincidência de Motivos por Técnico")
            reinc = Motor.backoffice_reincidencia(df, "_COL_BAIXA", min_ocorrencias=2)
            render_dataframe_profundo(
                reinc.head(15), "Técnicos Reincidentes", "🔁", height=350
            )

    with t5:
        render_section("💾 Base de Dados Tratada & Higienizada")
        st.markdown(
            f"Abaixo estão os **{len(df):,}** registros higienizados e padronizados."
        )
        st.dataframe(df, use_container_width=True, height=400)
        st.download_button(
            "📥 Exportar Base Completa (Excel)",
            data=Utils.gerar_excel(df, "Base_Tratada"),
            file_name=f"base_tratada_quebra_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def view_analise_segmento(df: pd.DataFrame, segmento: str) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    df_seg = df[df["TIPO_SERVICO"] == segmento].copy()
    regioes = df_seg["REGIÃO"].unique().tolist() if not df_seg.empty else []
    total_seg = len(df_seg)

    _render_hero_segmento(segmento, regioes, total_seg)

    if df_seg.empty:
        st.warning(f"⚠️ Nenhuma ordem encontrada para o segmento **{segmento}**.")
        return

    # Controles de Parâmetros na Sidebar
    st.sidebar.markdown(f"### ⚙️ Parâmetros — {segmento}")
    sla_meta = st.sidebar.slider(
        f"Meta de SLA ({segmento})",
        0.05,
        0.50,
        conf["sla_default"],
        0.01,
        key=f"sla_{segmento}",
    )

    c_p1, c_p2, c_p3 = st.sidebar.columns(3)
    p_ot = c_p1.number_input(
        "Otimista",
        0.0,
        1.0,
        0.15,
        0.05,
        key=f"ot_{segmento}",
        help="Probabilidade de quebra nos pendentes no cenário otimista",
    )
    p_base = c_p2.number_input(
        "Base",
        0.0,
        1.0,
        0.30,
        0.05,
        key=f"base_{segmento}",
        help="Probabilidade de quebra nos pendentes no cenário base",
    )
    p_pess = c_p3.number_input(
        "Pessimista",
        0.0,
        1.0,
        0.50,
        0.05,
        key=f"pess_{segmento}",
        help="Probabilidade de quebra nos pendentes no cenário pessimista",
    )

    min_aloc = st.sidebar.number_input(
        "Min. Alocado (Técnicos)",
        1,
        50,
        3,
        key=f"min_{segmento}",
        help="Volume mínimo de OSs alocadas para considerar o técnico no ranking",
    )

    # Indicadores
    proj = Motor.projetar(df_seg, p_base)
    folga = Motor.folga_sla(df_seg, sla_meta)

    m1, m2, m3, m4 = st.columns(4)
    render_kpi(
        m1,
        "Alocado Total",
        _fmt_int_br(proj["alocado"]),
        "Volume de OSs",
        "escuro",
    )
    render_kpi(
        m2,
        "Quebra Atual",
        _fmt_pct_br(proj["quebra_atual"]),
        f"Exec: {int(proj['exec'])} | NE: {int(proj['naoexec'])}",
        "laranja" if proj["quebra_atual"] > sla_meta else "verde",
    )
    render_kpi(
        m3,
        "Fechamento Base",
        _fmt_pct_br(proj["fechamento_proj"]),
        f"Com {p_base:.0%} nos pendentes",
        "vermelho" if proj["fechamento_proj"] > sla_meta else "azul",
    )
    render_kpi(
        m4,
        "Folga no SLA",
        _fmt_int_br(folga["folga_ne_pendente"]),
        "NEs toleradas no pendente",
        "vermelho" if folga["estourado"] else "roxo",
    )

    st.markdown("---")
    col_l, col_r = st.columns([2, 1])

    with col_l:
        render_section(f"👷 Técnicos Críticos — {segmento}")
        tab_tec = Motor.tecnicos_criticos(
            df_seg, segmento, p_base, float(min_aloc), top_n=15
        )
        render_dataframe_profundo(
            tab_tec,
            f"Top Técnicos em {segmento}",
            "👷",
            color_col="Fechamento Base",
            meta=sla_meta,
            height=360,
        )

    with col_r:
        render_section("🪵 Causas Raiz da Quebra")
        df_causa_seg = Motor.causa_raiz_segmento(
            df_seg, segmento, "_COL_BAIXA", top_n=6
        )
        render_dataframe_profundo(df_causa_seg, f"Pareto {segmento}", "📌", height=360)

    st.markdown("---")
    render_section("🎯 Recomendações & Exportação")
    c_rec1, c_rec2 = st.columns([2, 1])

    with c_rec1:
        st.markdown("##### 📋 Plano de Ação Recomendado")
        for prioridade, texto, tipo in conf["acoes"]:
            render_insight(f"<b>[{prioridade}]</b> {texto}", tipo)

    with c_rec2:
        st.markdown("##### 📄 Exportar Relatório Executivo")
        st.info("Gere o PDF formatado com gráficos e tabelas para envio à diretoria.")
        pdf_bytes = conf["pdf_class"].gerar(
            df_seg, sla_meta, p_ot, p_base, p_pess, min_aloc, top_n=10
        )
        st.download_button(
            f"📥 Baixar PDF Executivo ({segmento})",
            data=pdf_bytes,
            file_name=f"relatorio_executivo_{segmento.lower()}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


def view_auditoria_criterios(df: pd.DataFrame) -> None:
    render_section("🔬 Auditoria de Critérios de Classificação")
    render_painel_criterios(df)
    st.markdown("---")
    render_debug_criterios(df)


# ═══════════════════════════════════════════════════════════════════════
# CONTROLLER PRINCIPAL (MAIN)
# ═══════════════════════════════════════════════════════════════════════
def main() -> None:
    st.sidebar.image(
        "https://via.placeholder.com/200x60.png?text=TOTALE+OPERACIONAL",
        width="stretch",
    )
    st.sidebar.title("📉 Quebra TOTALE")

    # Ingestão de Dados na Sidebar
    file = st.sidebar.file_uploader(
        "📂 Importar Base de Dados", type=["xlsx", "xls", "csv"]
    )

    if file is not None:
        df_raw = DataLoader.ler_arquivo(file.getvalue(), file.name)
        if not df_raw.empty:
            df_gs = DataLoader.buscar_gsheets()
            st.session_state["df_memoria"] = DataLoader.preparar_base(df_raw, df_gs)
            st.sidebar.success(f"✅ Base carregada: {len(df_raw):,} linhas")

    df = st.session_state["df_memoria"]

    if df is None or df.empty:
        render_hero_upload()
        st.info(
            "👉 Por favor, faça o upload de um arquivo **Excel (.xlsx)** ou **CSV** no menu lateral para iniciar a análise."
        )

        # Instruções de Uso
        st.markdown("""
            ### ℹ️ Estrutura Esperada da Base
            Para o correto funcionamento de todos os módulos, a base deve conter idealmente:
            - **Status O.S. / Status Contrato:** Executada, Não Executada, Pendente
            - **Tipo de Serviço / Pacote:** Identificação de Migração, PME, Novos Domicílios
            - **Login do Técnico / Nome do Técnico / Monitor:** Mapeamento operacional
            - **Cidade / Localidade:** Classificação automática por Região (LESTE, GRU, ABCDM, OUTRAS)
            """)
        return

    # Filtros Globais da Operação
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🌪️ Filtros Globais")

    regioes_disponiveis = sorted(df["REGIÃO"].unique().tolist())
    regioes_sel = st.sidebar.multiselect(
        "Região", regioes_disponiveis, default=regioes_disponiveis
    )

    monitores_disponiveis = sorted(df["MONITOR"].unique().tolist())
    monitores_sel = st.sidebar.multiselect(
        "Monitor", monitores_disponiveis, default=monitores_disponiveis
    )

    # Aplicação dos filtros
    df_filtrado = df[
        (df["REGIÃO"].isin(regioes_sel)) & (df["MONITOR"].isin(monitores_sel))
    ]

    # Navegação Módulos
    modulo = st.sidebar.radio(
        "🧭 Módulo de Análise",
        [
            "📊 Resumo Executivo",
            "🔍 Análise Detalhada",
            "🔄 Segmento: Migração",
            "🏢 Segmento: PME",
            "🔬 Auditoria de Critérios",
        ],
    )

    meta_sla_global = st.sidebar.slider(
        "Meta Global de SLA", 0.05, 0.50, Config.SLA_QUEBRA_MAXIMA, 0.01
    )

    # Top Hero Fixo
    render_hero_topo_fixo(
        "📉 Gestão Operacional de Quebra de Agenda",
        "Super Relatório Corporativo Unificado | TOTALE Operações",
        regioes_sel,
        len(df_filtrado),
        badge=modulo,
    )

    # Roteamento de Módulos
    if modulo == "📊 Resumo Executivo":
        view_resumo_executivo(df_filtrado, meta_sla_global)
    elif modulo == "🔍 Análise Detalhada":
        view_analise_detalhada(df_filtrado, meta_sla_global)
    elif modulo == "🔄 Segmento: Migração":
        view_analise_segmento(df_filtrado, "Migração")
    elif modulo == "🏢 Segmento: PME":
        view_analise_segmento(df_filtrado, "PME")
    elif modulo == "🔬 Auditoria de Critérios":
        view_auditoria_criterios(df_filtrado)


if __name__ == "__main__":
    main()
