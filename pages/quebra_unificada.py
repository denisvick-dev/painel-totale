"""
quebra_unificada.py
===================
Análise de Quebra por Segmento (Novos Domicílios / Migração / PME + Comparativo)
Inclui aba dedicada para contratos com MOTIVO DE BAIXA = SEM REGISTRO.

Version: 2.2.2
Author: TOTALE Tecnologia
"""

from __future__ import annotations

import hashlib
import sys
import unicodedata
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, cast, Dict

# ── Bootstrap sys.path ───────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_ROOT = _DIR.parent
for _p in (_DIR, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from components.componentes import (
    TemaKPIType,
    TipoInsightType,
    render_hero_migracao,
    render_hero_novos_domicilios,
    render_hero_pme,
    render_insight,
    render_kpi,
    render_kpi_sm,
    render_section_header,
    render_table_html,
    aplicar_estilo as _aplicar_estilo_global,
)
from components.criterios import classificar_tipo_servico, render_debug_criterios
from pages.quebra_geral import Config, Motor, Utils

# ── Correções Avançadas Pylance (Type Safety) ────────────────────────
_COL_REGIAO: str = str(getattr(Config, "COL_REGIAO", "REGIÃO"))


def _obter_folga_sla(df: pd.DataFrame, sla_meta: float) -> dict[str, Any]:
    """Wrapper seguro com tipagem explícita para evitar o erro do Pylance sobre Motor.folga_sla"""
    if hasattr(Motor, "folga_sla"):
        return getattr(Motor, "folga_sla")(df, sla_meta)

    # Lógica de fallback para evitar quebra no runtime
    if df.empty or "Status Contrato" not in df.columns:
        return {
            "estourado": False,
            "folga_ne_pendente": 0.0,
            "precisa_executar_pendente": 0.0,
            "limite_ne_total": 0.0,
            "naoexec": 0.0,
            "alocado": 0.0,
        }

    df_ne = df[
        df["Status Contrato"]
        .astype(str)
        .str.upper()
        .isin(["NÃO EXECUTADA", "NAO EXECUTADA"])
    ]
    df_pend = df[
        df["Status Contrato"]
        .astype(str)
        .str.upper()
        .isin(["PENDENTE", "EM ABERTO", "ABERTO", "EM ROTA"])
    ]

    if "TOTAL DE TAREFAS" in df.columns:
        naoexec = float(
            pd.to_numeric(df_ne["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum()
        )
        pend = float(
            pd.to_numeric(df_pend["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum()
        )
        alocado = float(
            pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum()
        )
    else:
        naoexec, pend, alocado = float(len(df_ne)), float(len(df_pend)), float(len(df))

    limite = alocado * sla_meta
    folga = limite - naoexec
    return {
        "estourado": folga < 0,
        "folga_ne_pendente": folga,
        "precisa_executar_pendente": max(0.0, pend - folga),
        "limite_ne_total": limite,
        "naoexec": naoexec,
        "alocado": alocado,
    }


def _obter_resumo_segmento(df: pd.DataFrame, probabilidade: float) -> dict[str, Any]:
    """Calcula as volumetrias e projeções e devolve em formato Dicionário (Tipado)."""
    if df.empty or "Status Contrato" not in df.columns:
        return {
            "alocado": 0,
            "exec": 0,
            "naoexec": 0,
            "pend": 0,
            "quebra_atual": 0.0,
            "fechamento_proj": 0.0,
            "naoexec_proj": 0,
        }

    s_status = df["Status Contrato"].astype(str).str.upper()

    if "TOTAL DE TAREFAS" in df.columns:
        df_exec = df[s_status == "EXECUTADA"]
        df_ne = df[s_status.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])]
        df_pend = df[s_status.isin(["PENDENTE", "EM ABERTO", "ABERTO", "EM ROTA"])]

        executadas = int(
            pd.to_numeric(df_exec["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum()
        )
        nao_exec = int(
            pd.to_numeric(df_ne["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum()
        )
        pendentes = int(
            pd.to_numeric(df_pend["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum()
        )
    else:
        executadas = int((s_status == "EXECUTADA").sum())
        nao_exec = int(s_status.isin(["NÃO EXECUTADA", "NAO EXECUTADA"]).sum())
        pendentes = int(
            s_status.isin(["PENDENTE", "EM ABERTO", "ABERTO", "EM ROTA"]).sum()
        )

    considerado = executadas + nao_exec
    alocado = considerado + pendentes

    quebra_atual = (nao_exec / considerado) if considerado > 0 else 0.0
    naoexec_proj = nao_exec + (pendentes * (1.0 - probabilidade))
    fechamento_proj = (naoexec_proj / alocado) if alocado > 0 else 0.0

    return {
        "alocado": alocado,
        "exec": executadas,
        "naoexec": nao_exec,
        "pend": pendentes,
        "quebra_atual": quebra_atual,
        "fechamento_proj": fechamento_proj,
        "naoexec_proj": int(naoexec_proj),
    }


# ── Streamlit Config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Análise de Quebra | TOTALE", page_icon="📉", layout="wide"
)
_aplicar_estilo_global()

if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None


# =====================================================================
# CONSTANTES E PARÂMETROS OPERACIONAIS
# =====================================================================
SLA_NOVOS_DOMICILIOS_DEFAULT: float = 0.20
SLA_MIGRACAO_DEFAULT: float = 0.25
SLA_PME_DEFAULT: float = 0.20

CANDIDATOS_COL_BAIXA: list[str] = [
    "_COL_BAIXA",
    "MOTIVO DE BAIXA",
    "CÓD DE BAIXA 1",
    "COD DE BAIXA 1",
    "MOTIVO BAIXA",
]
CANDIDATOS_DATA: list[str] = [
    "DATA",
    "DATA OS",
    "DATA DA OS",
    "DATA BAIXA",
    "DATA EXECUÇÃO",
    "DATA EXECUCAO",
    "DATA AGENDAMENTO",
    "DATA_AGENDAMENTO",
]
STATUS_PENDENTE: set[str] = {"PENDENTE", "PENDING", "ABERTO", "EM ABERTO"}
COLS_TECNICOS_PDF: list[str] = [
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


# =====================================================================
# HELPERS DE TRATAMENTO DE DADOS
# =====================================================================
def _fmt_int(v: Any) -> str:
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "0"
        return f"{int(float(v)):,}".replace(",", ".")
    except Exception:
        return "0"


def _norm_txt(s: Any) -> str:
    return (
        unicodedata.normalize("NFKD", str(s))
        .encode("ascii", errors="ignore")
        .decode("ascii")
        .upper()
        .strip()
        .replace("_", " ")
        .replace(".", "")
    )


def _resolver_col_baixa(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    col_attr = df.attrs.get("_COL_BAIXA") if hasattr(df, "attrs") else None
    if col_attr and col_attr in df.columns:
        return str(col_attr)
    for c in CANDIDATOS_COL_BAIXA:
        if c in df.columns:
            return c
    cols_norm = {_norm_txt(c): c for c in df.columns}
    for c in CANDIDATOS_COL_BAIXA:
        if _norm_txt(c) in cols_norm:
            return cols_norm[_norm_txt(c)]
    return None


def _resolver_col_data(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    cols_norm = {_norm_txt(c): c for c in df.columns}
    for cand in CANDIDATOS_DATA:
        if _norm_txt(cand) in cols_norm:
            return cols_norm[_norm_txt(cand)]
    return None


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_")


def _hash_df(df: pd.DataFrame) -> str:
    try:
        b = pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes()
        return hashlib.md5(b).hexdigest()[:10]
    except Exception:
        return str(len(df))


def _causa_raiz_segmento(
    df: pd.DataFrame, segmento: str, top_n: int = 8
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if segmento and segmento != "Todos os Segmentos" and "TIPO_SERVICO" in df.columns:
        df_seg = df[df["TIPO_SERVICO"] == segmento].copy()
    else:
        df_seg = df.copy()
    if df_seg.empty:
        return pd.DataFrame()
    df_seg.attrs = dict(getattr(df, "attrs", {}))
    col_baixa = _resolver_col_baixa(df_seg)
    if not col_baixa:
        return pd.DataFrame()
    try:
        return Motor.causa_raiz(df_seg, col_baixa, top_n=top_n)
    except Exception:
        return pd.DataFrame()


def _preparar_base(df: pd.DataFrame) -> pd.DataFrame:
    if "Status Contrato" not in df.columns:
        df["Status Contrato"] = Utils.classificar_status_excel(df)
    if "TIPO_SERVICO" not in df.columns:
        res = classificar_tipo_servico(df)
        if isinstance(res, tuple):
            df_res, serie = res
            df = df_res if isinstance(df_res, pd.DataFrame) else df
            df["TIPO_SERVICO"] = serie
        elif isinstance(res, pd.DataFrame):
            df = res
        else:
            df["TIPO_SERVICO"] = res
    return df


def _opcoes_filtro(df: pd.DataFrame, col: str, excluir: set[str]) -> list[str]:
    if col not in df.columns:
        return ["Todos"]
    return ["Todos"] + sorted(
        str(x) for x in df[col].dropna().unique() if str(x).strip() not in excluir
    )


# =====================================================================
# PDF REPORTLAB ENGINE
# =====================================================================
class _PDFExecutivoBase:
    COR_PRIMARIA = "#0C4A6E"
    COR_SECUNDARIA = "#0369A1"
    COR_TEXTO = "#0F172A"
    COR_SUBTEXTO = "#6B7280"
    COR_SUBTITULO = "#BAE6FD"
    COR_OK = "#059669"
    COR_ALERTA = "#D97706"
    COR_CRITICO = "#DC2626"
    COR_LINHA = "#E5E7EB"
    COR_LINHA_ALT = "#F0F9FF"
    LARGURA_UTIL = 27.7
    MARGEM_H = 0.8
    MARGEM_TOP = 0.8
    MARGEM_BOT = 1.3
    NOME_SEGMENTO = ""
    DESCRICAO = ""
    LIMITE_TECNICOS = 15
    LARGURAS_CENARIOS = None
    LARGURAS_CAUSAS = None

    @classmethod
    def _fmt(cls, v, col=""):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return "—"
        col_u = str(col).upper()
        pct_keys = {
            "QUEBRA",
            "FECHAMENTO",
            "META",
            "PROBAB",
            "%",
            "ACUMULADO",
            "VS META",
        }
        if isinstance(v, (float, np.floating)):
            if any(k in col_u for k in pct_keys):
                return f"{v:.2%}".replace(".", ",")
            if float(v).is_integer():
                return f"{int(v):,}".replace(",", ".")
            return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if isinstance(v, (int, np.integer)):
            return f"{v:,}".replace(",", ".")
        return escape(str(v))

    @classmethod
    def _calcular_larguras(cls, df):
        if df.empty:
            return [cls.LARGURA_UTIL]
        pesos = []
        for col in df.columns:
            max_len = len(str(col))
            for val in df[col].head(50):
                max_len = max(max_len, len(cls._fmt(val, col)))
            pesos.append(min(max(max_len, 5), 30))
        total = sum(pesos) or 1
        return [(p / total) * cls.LARGURA_UTIL for p in pesos]

    @classmethod
    def _estilos(cls):
        s = getSampleStyleSheet()
        s.add(
            ParagraphStyle(
                name="X_Titulo",
                parent=s["Normal"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=colors.white,
                alignment=TA_CENTER,
                spaceAfter=2,
            )
        )
        s.add(
            ParagraphStyle(
                name="X_Subtitulo",
                parent=s["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=colors.HexColor(cls.COR_SUBTITULO),
                alignment=TA_CENTER,
            )
        )
        s.add(
            ParagraphStyle(
                name="X_Secao",
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
    def _cabecalho(cls, s):
        titulo = f"RELATÓRIO EXECUTIVO — {cls.NOME_SEGMENTO.upper()}"
        sub = f"{escape(cls.DESCRICAO)} • Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
        t = Table(
            [
                [Paragraph(escape(titulo), s["X_Titulo"])],
                [Paragraph(sub, s["X_Subtitulo"])],
            ],
            colWidths=[cls.LARGURA_UTIL * cm],
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(cls.COR_PRIMARIA)),
                    (
                        "LINEBELOW",
                        (0, -1),
                        (-1, -1),
                        2,
                        colors.HexColor(cls.COR_SECUNDARIA),
                    ),
                    ("TOPPADDING", (0, 0), (-1, 0), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                    ("TOPPADDING", (0, 1), (-1, 1), 2),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 14),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        return t

    @classmethod
    def _tab(cls, df, limite=None, larguras=None, cor_col_quebra=None, sla_meta=0.25):
        def _interna():
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
            dados = [[Paragraph(escape(str(c)), st_h) for c in base.columns]]
            for _, row in base.iterrows():
                dados.append(
                    [
                        Paragraph(cls._fmt(row[c], c), st_cl if i == 0 else st_c)
                        for i, c in enumerate(base.columns)
                    ]
                )
            col_widths = (
                [w * cm for w in larguras]
                if larguras and len(larguras) == len(base.columns)
                else [w * cm for w in cls._calcular_larguras(base)]
            )
            if sum(col_widths) > cls.LARGURA_UTIL * cm:
                fator = (cls.LARGURA_UTIL * cm) / sum(col_widths)
                col_widths = [w * fator for w in col_widths]

            # Garantia contra valores nulos de dimensionamento
            if not col_widths or sum(col_widths) == 0:
                col_widths = [cls.LARGURA_UTIL * cm / max(1, len(base.columns))] * len(
                    base.columns
                )

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
                    except Exception:
                        continue
                    if np.isnan(val):
                        continue
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
    def _rodape(cls, canvas, doc):
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
            f"{cls.NOME_SEGMENTO} — Gestão de Quebra | {datetime.now().strftime('%d/%m/%Y %H:%M')} | Confidencial",
        )
        canvas.drawRightString(
            page_w - cls.MARGEM_H * cm, 0.52 * cm, f"Página {doc.page}"
        )
        canvas.restoreState()

    @classmethod
    def gerar(cls, df, sla_meta, p_ot, p_base, p_pess, min_aloc=1.0, top_n=10):
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=cls.MARGEM_H * cm,
            leftMargin=cls.MARGEM_H * cm,
            topMargin=cls.MARGEM_TOP * cm,
            bottomMargin=cls.MARGEM_BOT * cm,
            title=f"Relatório Executivo — {cls.NOME_SEGMENTO}",
            author="TOTALE",
        )
        s = cls._estilos()
        el = []
        el.append(cls._cabecalho(s))
        el.append(Spacer(1, 0.8 * cm))
        el.append(Paragraph("1 ─ Cenários de Fechamento", s["X_Secao"]))
        cenarios = []
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            proj = _obter_resumo_segmento(df, p)
            cenarios.append(
                {
                    "Cenário": nome,
                    "Probab. Pendente": p,
                    "Fechamento Proj.": proj["fechamento_proj"],
                    "Não Exec. Proj.": proj["naoexec_proj"],
                    "vs Meta": proj["fechamento_proj"] - sla_meta,
                }
            )
        el.append(
            cls._tab(
                pd.DataFrame(cenarios),
                larguras=cls.LARGURAS_CENARIOS,
                cor_col_quebra="Fechamento Proj.",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.5 * cm))
        el.append(Paragraph("2 ─ Técnicos Críticos", s["X_Secao"]))
        df_tec = Motor.tecnicos_criticos(
            df,
            cls.NOME_SEGMENTO,
            p_base,
            float(min_aloc),
            int(top_n),
            p_ot=p_ot,
            p_pess=p_pess,
        )
        cols_tec = [c for c in COLS_TECNICOS_PDF if c in df_tec.columns]
        el.append(
            cls._tab(
                df_tec[cols_tec] if not df_tec.empty else df_tec,
                limite=cls.LIMITE_TECNICOS,
                cor_col_quebra="Fechamento Base",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.5 * cm))
        el.append(Paragraph("3 ─ Principais Causas de Quebra (Pareto)", s["X_Secao"]))
        el.append(
            cls._tab(
                _causa_raiz_segmento(df, cls.NOME_SEGMENTO, top_n=8),
                limite=8,
                larguras=cls.LARGURAS_CAUSAS,
            )
        )
        doc.build(el, onFirstPage=cls._rodape, onLaterPages=cls._rodape)
        buf.seek(0)
        return buf.getvalue()


class PDFExecutivoNovosDomicilios(_PDFExecutivoBase):
    COR_PRIMARIA = "#0A2F6B"
    COR_SECUNDARIA = "#1D4ED8"
    COR_LINHA_ALT = "#EFF6FF"
    COR_SUBTITULO = "#BFDBFE"
    NOME_SEGMENTO = "Novos Domicílios"
    DESCRICAO = "Adesão e Novas Instalações"


class PDFExecutivoMigracao(_PDFExecutivoBase):
    COR_PRIMARIA = "#0C4A6E"
    COR_SECUNDARIA = "#0369A1"
    COR_LINHA_ALT = "#F0F9FF"
    COR_SUBTITULO = "#BAE6FD"
    NOME_SEGMENTO = "Migração"
    DESCRICAO = "Mudança de Pacote + FLAG_GPON = Sim"


class PDFExecutivoPME(_PDFExecutivoBase):
    COR_PRIMARIA = "#4C1D95"
    COR_SECUNDARIA = "#7C3AED"
    COR_TEXTO = "#1E1B4B"
    COR_LINHA_ALT = "#F9FAFB"
    COR_SUBTITULO = "#DDD6FE"
    NOME_SEGMENTO = "PME"
    DESCRICAO = "Pequenas e Médias Empresas"
    LIMITE_TECNICOS = 10
    LARGURAS_CENARIOS = [4.5, 4.5, 5.5, 5.5, 5.0]
    LARGURAS_CAUSAS = [9.0, 4.5, 4.5, 4.5]


class PDFExecutivoComparativo(_PDFExecutivoBase):
    COR_PRIMARIA = "#0F172A"
    COR_SECUNDARIA = "#334155"
    COR_SUBTITULO = "#CBD5E1"
    COR_LINHA_ALT = "#F8FAFC"
    NOME_SEGMENTO = "Comparativo Geral"
    DESCRICAO = "Consolidado — Novos Domicílios + Migração + PME"

    @classmethod
    def gerar(cls, df, sla_meta, p_ot, p_base, p_pess, min_aloc=1.0, top_n=10):
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=cls.MARGEM_H * cm,
            leftMargin=cls.MARGEM_H * cm,
            topMargin=cls.MARGEM_TOP * cm,
            bottomMargin=cls.MARGEM_BOT * cm,
            title="Comparativo Geral",
            author="TOTALE",
        )
        s = cls._estilos()
        el = [cls._cabecalho(s), Spacer(1, 0.8 * cm)]
        if "TIPO_SERVICO" in df.columns:
            comp = []
            for seg in sorted(df["TIPO_SERVICO"].dropna().unique()):
                d = df[df["TIPO_SERVICO"] == seg]
                proj = _obter_resumo_segmento(d, p_base)
                comp.append(
                    {
                        "Segmento": seg,
                        "Alocado": proj["alocado"],
                        "Quebra Atual": proj["quebra_atual"],
                        "Fechamento Base": proj["fechamento_proj"],
                        "vs Meta": proj["fechamento_proj"] - sla_meta,
                    }
                )
            el.append(Paragraph("1 ─ Comparativo por Segmento (Base)", s["X_Secao"]))
            el.append(
                cls._tab(
                    pd.DataFrame(comp),
                    cor_col_quebra="Fechamento Base",
                    sla_meta=sla_meta,
                )
            )
            el.append(Spacer(1, 0.5 * cm))
        el.append(Paragraph("2 ─ Cenários Consolidados", s["X_Secao"]))
        cen = []
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            proj = _obter_resumo_segmento(df, p)
            cen.append(
                {
                    "Cenário": nome,
                    "Probab.": p,
                    "Fechamento": proj["fechamento_proj"],
                    "vs Meta": proj["fechamento_proj"] - sla_meta,
                }
            )
        el.append(
            cls._tab(pd.DataFrame(cen), cor_col_quebra="Fechamento", sla_meta=sla_meta)
        )
        el.append(Spacer(1, 0.5 * cm))
        el.append(Paragraph("3 ─ Técnicos Críticos (Geral)", s["X_Secao"]))
        df_tec = Motor.tecnicos_criticos(
            df,
            "Comparativo",
            p_base,
            float(min_aloc),
            int(top_n),
            p_ot=p_ot,
            p_pess=p_pess,
        )
        cols = [c for c in COLS_TECNICOS_PDF if c in df_tec.columns]
        el.append(
            cls._tab(
                df_tec[cols] if not df_tec.empty else df_tec,
                limite=15,
                cor_col_quebra="Fechamento Base",
                sla_meta=sla_meta,
            )
        )
        doc.build(el, onFirstPage=cls._rodape, onLaterPages=cls._rodape)
        buf.seek(0)
        return buf.getvalue()


# =====================================================================
# CONFIGURAÇÕES E ESTILOS DINÂMICOS
# =====================================================================
SEGMENTOS_CONFIG: dict[str, Any] = {
    "Novos Domicílios": {
        "icone": "🏠",
        "subtitulo": "Análise estratégica dedicada à adesão de novos clientes e domicílios",
        "cor_primaria": "#012869",
        "cor_secundaria": "#14B8A6",
        "grad_hero": "linear-gradient(135deg, #012869 0%, #0A3D62 35%, #0D9488 70%, #14B8A6 100%)",
        "sombra_hero": "rgba(1,40,105,0.28)",
        "sla_default": SLA_NOVOS_DOMICILIOS_DEFAULT,
        "p_base_default": 20,
        "pdf_class": PDFExecutivoNovosDomicilios,
        "hero_fn": render_hero_novos_domicilios,
        "hero_kwargs": {"badge": "NOVOS DOMICÍLIOS", "icone": "🏠"},
        "acoes": [
            (
                "🔴 ALTA",
                "Monitorar rota de instalação e taxa de comparecimento.",
                "alerta",
            ),
            ("🟡 MÉDIA", "Revisar triagem de viabilidade óptica.", "acao"),
        ],
    },
    "Migração": {
        "icone": "🔄",
        "subtitulo": "Análise estratégica dedicada às mudanças de pacotes com tecnologia GPON",
        "cor_primaria": "#6D28D9",
        "cor_secundaria": "#A78BFA",
        "grad_hero": "linear-gradient(135deg, #4C1D95 0%, #6D28D9 35%, #7C3AED 60%, #A78BFA 100%)",
        "sombra_hero": "rgba(124,58,237,0.35)",
        "sla_default": SLA_MIGRACAO_DEFAULT,
        "p_base_default": 25,
        "pdf_class": PDFExecutivoMigracao,
        "hero_fn": render_hero_migracao,
        "hero_kwargs": {"badge": "MIGRAÇÃO DE DADOS", "icone": "🔄"},
        "acoes": [
            ("🔴 ALTA", "Verificar estoque de equipamentos (ONT/ONU).", "alerta")
        ],
    },
    "PME": {
        "icone": "🏢",
        "subtitulo": "Análise estratégica dedicada às Pequenas e Médias Empresas",
        "cor_primaria": "#059669",
        "cor_secundaria": "#3B82F6",
        "grad_hero": "linear-gradient(135deg, #059669 0%, #10B981 35%, #3B82F6 70%, #60A5FA 100%)",
        "sombra_hero": "rgba(16,185,129,0.30)",
        "sla_default": SLA_PME_DEFAULT,
        "p_base_default": 20,
        "pdf_class": PDFExecutivoPME,
        "hero_fn": render_hero_pme,
        "hero_kwargs": {"badge": "PME CONNECT", "icone": "🚀"},
        "acoes": [("🔴 ALTA", "Verificar técnicos habilitados em PME.", "acao")],
    },
}


def _injetar_css_dinamico(segmento: str):
    conf = SEGMENTOS_CONFIG.get(
        segmento, {"sombra_hero": "rgba(0,0,0,0.15)", "cor_primaria": "#0F172A"}
    )
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
.hero-domicilios,.hero-migracao,.hero-pme,.resultado-base,.resultado-base-regiao,.resultado-base-label,.resultado-base-count,.table-html-container table{{font-family:'Inter',sans-serif!important}}
div[data-testid="stElementContainer"]:has(.hero-domicilios),div[data-testid="stElementContainer"]:has(.hero-migracao),div[data-testid="stElementContainer"]:has(.hero-pme),div[data-testid="stElementContainer"]:has(.hero-comparativo){{position:sticky!important;top:0.75rem!important;z-index:1000!important}}
.hero-domicilios,.hero-migracao,.hero-pme,.hero-comparativo{{margin-bottom:12px!important;border-radius:16px!important;box-shadow:0 10px 40px {conf["sombra_hero"]}!important}}
.resultado-base{{background:linear-gradient(135deg,#0F172A 0%,#1E3A5F 100%);padding:1rem 1.5rem;border-radius:0.75rem;display:flex;align-items:center;flex-wrap:wrap;gap:0.6rem;box-shadow:0 4px 12px rgba(0,0,0,0.15);margin-bottom:0!important}}
.resultado-base-label{{color:#94A3B8;font-size:0.8rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em}}
.resultado-base-regiao{{padding:0.3rem 0.9rem;border-radius:999px;font-size:0.82rem;font-weight:700;border:2px solid}}
.resultado-base-count{{color:#FFF;font-size:0.78rem;margin-left:auto;font-weight:700}}
.alert-chip{{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;font-size:12px;font-weight:600;margin:4px 6px 4px 0}}
</style>""",
        unsafe_allow_html=True,
    )


def _html_resultado_base(regioes: list[str], total: int) -> str:
    cores = {
        "LESTE": {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
        "GRU": {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
        "ABCDM": {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
        "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
    }
    badges = ""
    for r in sorted(set(regioes)):
        rr = str(r).strip().upper()
        if not rr or rr in {"NAN", "NONE"}:
            continue
        cor = cores.get(rr, cores["OUTRAS"])
        badges += f'<span class="resultado-base-regiao" style="background:{cor["bg"]};color:{cor["text"]};border-color:{cor["border"]};">{escape(rr)}</span>'
    if not badges:
        cor = cores["OUTRAS"]
        badges = f'<span class="resultado-base-regiao" style="background:{cor["bg"]};color:{cor["text"]};border-color:{cor["border"]};">OUTRAS</span>'
    return f'<div class="resultado-base"><span class="resultado-base-label">📋 Resultado da Base:</span>{badges}<span class="resultado-base-count">{_fmt_int(total)} registros</span></div>'


def _render_hero_comparativo(total: int):
    st.markdown(
        f"""
<div class="hero-comparativo" style="background:linear-gradient(135deg,#0F172A 0%,#1E293B 35%,#334155 70%,#475569 100%);padding:22px 26px;border-radius:16px;color:white">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
    <div><div style="font-size:11px;letter-spacing:0.12em;opacity:0.8;font-weight:700">CONSOLIDADO EXECUTIVO</div><div style="font-size:22px;font-weight:800;margin-top:4px">📊 Todos os Segmentos — Quebra de Agenda</div><div style="font-size:13px;opacity:0.85;margin-top:4px">Visão comparativa entre Novos Domicílios, Migração e PME • {total} registros</div></div>
    <div style="background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.18);padding:10px 14px;border-radius:10px;text-align:center"><div style="font-size:11px;opacity:0.8">BASE TOTAL</div><div style="font-size:20px;font-weight:800">{_fmt_int(total)}</div></div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def _render_topo_fixo(segmento: str, regioes: list[str], total: int):
    if segmento == "Todos os Segmentos":
        _render_hero_comparativo(total)
        st.markdown(_html_resultado_base(regioes, total), unsafe_allow_html=True)
        return
    conf = SEGMENTOS_CONFIG[segmento]
    conf["hero_fn"](
        titulo=f"{segmento} — Quebra de Agenda",
        subtitulo=conf["subtitulo"],
        **conf.get("hero_kwargs", {}),
    )
    st.markdown(_html_resultado_base(regioes, total), unsafe_allow_html=True)


def _render_card_status(segmento: str, m_seg: Any, sla_meta: float):
    conf = SEGMENTOS_CONFIG.get(
        segmento,
        {
            "icone": "📊",
            "grad_hero": "linear-gradient(135deg,#0F172A,#334155)",
            "sombra_hero": "rgba(0,0,0,0.2)",
            "cor_primaria": "#0F172A",
            "cor_secundaria": "#475569",
        },
    )
    quebra = float(m_seg["quebra_atual"])
    dentro = quebra <= sla_meta
    if dentro:
        status_label, status_icone, cor_status, cor_bg, cor_txt = (
            "DENTRO DO SLA",
            "✓",
            "#059669",
            "#D1FAE5",
            "#065F46",
        )
    else:
        status_label, status_icone, cor_status, cor_bg, cor_txt = (
            "FORA DO SLA",
            "!",
            "#DC2626",
            "#FEE2E2",
            "#991B1B",
        )
    pct = min(100.0, (quebra / (sla_meta * 2)) * 100) if sla_meta > 0 else 0
    st.markdown(
        f"""
<div style="background:white;border:1px solid #E5E7EB;border-radius:14px;padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.04);margin:16px 0 12px 0;border-top:3px solid {conf["cor_primaria"]};font-family:Inter,sans-serif">
  <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;align-items:center">
    <div style="display:flex;gap:14px;align-items:center"><div style="width:44px;height:44px;background:{conf["grad_hero"]};border-radius:10px;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px {conf["sombra_hero"]}"><span style="font-size:22px">{conf["icone"]}</span></div><div><div style="font-size:18px;font-weight:800;color:#1F2937">{escape(segmento)}</div><div style="font-size:12px;color:#6B7280">Análise de Quebra</div></div></div>
    <div style="display:flex;gap:10px;flex-wrap:wrap"><div style="display:inline-flex;align-items:center;gap:6px;padding:6px 14px;background:{cor_bg};border-radius:999px;border:1px solid {cor_status}"><span style="width:18px;height:18px;background:{cor_status};color:white;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:800">{status_icone}</span><span style="font-size:11px;font-weight:700;color:{cor_txt}">{status_label}</span></div><div style="padding:6px 14px;background:#F0F9FF;border-radius:8px;border:1px solid #BAE6FD"><div style="font-size:10px;color:#6B7280;font-weight:600">QUEBRA ATUAL</div><div style="font-size:16px;color:{cor_status};font-weight:800">{quebra:.2%}</div></div><div style="padding:6px 14px;background:#F0F9FF;border-radius:8px;border:1px solid #BAE6FD"><div style="font-size:10px;color:#6B7280;font-weight:600">META SLA</div><div style="font-size:16px;color:{conf["cor_secundaria"]};font-weight:800">{sla_meta:.2%}</div></div></div>
  </div>
  <div style="margin:16px 0 6px 0;display:flex;justify-content:space-between;font-size:11px;color:#6B7280;font-weight:600"><span>0%</span><span>Meta {sla_meta:.2%}</span><span>{sla_meta*2:.0%}</span></div>
  <div style="height:8px;background:#E5E7EB;border-radius:4px;overflow:hidden;position:relative"><div style="position:absolute;left:50%;top:0;width:2px;height:100%;background:#374151;z-index:2"></div><div style="width:{pct}%;height:100%;background:linear-gradient(90deg,{cor_status},{cor_status}CC);border-radius:4px"></div></div>
</div>""",
        unsafe_allow_html=True,
    )


def _gerar_alertas(
    df_seg: pd.DataFrame, m_seg: dict, sla_meta: float, folga: dict
) -> list[dict]:
    alerts = []
    quebra = float(m_seg.get("quebra_atual", 0))
    pend = float(m_seg.get("pend", 0))
    if quebra > sla_meta:
        alerts.append(
            {
                "tipo": "critico",
                "icone": "🔴",
                "msg": f"Quebra {quebra:.2%} acima da meta {sla_meta:.0%} (+{quebra-sla_meta:.2%})",
            }
        )
    if folga.get("estourado"):
        alerts.append(
            {
                "tipo": "critico",
                "icone": "🚨",
                "msg": f"Estouro de {int(folga['naoexec']-folga['limite_ne_total'])} OS além do limite",
            }
        )
    if pend > 300:
        alerts.append(
            {
                "tipo": "alerta",
                "icone": "⚠️",
                "msg": f"Backlog elevado: {_fmt_int(pend)} pendentes",
            }
        )
    col_baixa = _resolver_col_baixa(df_seg)
    if col_baixa:
        try:
            df_c = Motor.causa_raiz(df_seg, col_baixa, top_n=1)
            if (
                not df_c.empty
                and "% do Total" in df_c.columns
                and float(df_c.iloc[0]["% do Total"]) > 0.3
            ):
                alerts.append(
                    {
                        "tipo": "acao",
                        "icone": "🎯",
                        "msg": f"Concentração: '{df_c.iloc[0]['Motivo de Baixa']}' = {df_c.iloc[0]['% do Total']:.0%} das quebras",
                    }
                )
        except Exception:
            pass
    return alerts


def _render_alerts_chips(alerts: list[Dict]):
    if not alerts:
        return
    cores = {
        "critico": ("#FEE2E2", "#991B1B", "#FCA5A5"),
        "alerta": ("#FEF3C7", "#92400E", "#FCD34D"),
        "acao": ("#DBEAFE", "#1E40AF", "#93C5FD"),
    }
    html = '<div style="display:flex;flex-wrap:wrap;margin:8px 0 16px 0">'
    for a in alerts:
        bg, txt, bd = cores.get(a["tipo"], ("#F1F5F9", "#475569", "#E2E8F0"))
        html += f'<span class="alert-chip" style="background:{bg};color:{txt};border:1px solid {bd}">{a["icone"]} {escape(a["msg"])}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# =====================================================================
# GESTÃO DE BACKLOG E EXPURGOS SIMULADOS
# =====================================================================
_MAPA_PENDENTES = {
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


def _achar_coluna(df, cands):
    cols_norm = {_norm_txt(c): c for c in df.columns}
    for cand in cands:
        if _norm_txt(cand) in cols_norm:
            return cols_norm[_norm_txt(cand)]
    for cand in cands:
        for cn, cr in cols_norm.items():
            if _norm_txt(cand) in cn:
                return cr
    return None


def _build_df_pendentes(df_seg):
    cols_saida = list(_MAPA_PENDENTES.keys())
    if "Status Contrato" in df_seg.columns:
        mask = (
            df_seg["Status Contrato"]
            .astype(str)
            .str.strip()
            .str.upper()
            .isin(STATUS_PENDENTE)
        )
    else:
        mask = pd.Series(True, index=df_seg.index)
    df_p = df_seg[mask].copy()
    if df_p.empty:
        return pd.DataFrame(columns=cols_saida)
    df_out = pd.DataFrame(index=df_p.index)
    for nome, cands in _MAPA_PENDENTES.items():
        col = _achar_coluna(df_p, cands)
        df_out[nome] = df_p[col].values if col else "N/D"
    df_out["Qtde. O.S."] = (
        pd.to_numeric(df_out["Qtde. O.S."], errors="coerce").fillna(0).astype(int)
    )
    if "Contrato" in df_out.columns:
        df_out = df_out.drop_duplicates(subset=["Contrato"])
    else:
        df_out = df_out.drop_duplicates()
    df_out = df_out.sort_values("Técnico", na_position="last").reset_index(drop=True)
    df_out.index = df_out.index + 1
    return df_out


def _calcular_quebra_expurgada(df_seg, m_seg, segmento):
    df_c = _causa_raiz_segmento(df_seg, segmento, top_n=1)
    if df_c.empty or not {"Motivo de Baixa", "Volume"}.issubset(df_c.columns):
        return None
    motivo = str(df_c.iloc[0]["Motivo de Baixa"])
    volume = float(df_c.iloc[0]["Volume"])
    naoexec = float(m_seg["naoexec"])
    alocado = float(m_seg["alocado"])
    volume = max(0.0, min(volume, naoexec))
    if alocado <= volume or volume <= 0:
        return None
    quebra_exp = max(0.0, (naoexec - volume) / (alocado - volume))
    return {
        "motivo": motivo,
        "volume": int(volume),
        "quebra_atual": float(m_seg["quebra_atual"]),
        "quebra_expurgada": quebra_exp,
        "impacto_abs": float(m_seg["quebra_atual"]) - quebra_exp,
    }


# =====================================================================
# RENDERIZAÇÃO DE SEÇÕES E SUB-ABAS (STREAMLIT ENGINE)
# =====================================================================
def _token_parece_icone(token: str):
    return any(
        0x2300 <= ord(c) <= 0x2BFF or 0x1F000 <= ord(c) <= 0x1FAFF for c in token
    )


def render_section(titulo: str):
    texto = str(titulo or "").strip()
    if not texto:
        return
    partes = texto.split(maxsplit=1)
    icone_final, titulo_final = "", texto
    if len(partes) == 2 and _token_parece_icone(partes[0]):
        icone_final, titulo_final = partes[0], partes[1]
    render_section_header(titulo=titulo_final, icone=icone_final)


def _sub_visao_geral(segmento, df_seg, m_seg, p_ot, p_base, p_pess, sla_meta):
    render_section(f"📊 Resumo Operacional — {segmento}")
    tema_q: TemaKPIType = "vermelho" if m_seg["quebra_atual"] > sla_meta else "verde"
    c1, c2, c3, c4, c5 = st.columns(5)
    render_kpi(c1, "Alocado", _fmt_int(m_seg["alocado"]), tema="azul")
    render_kpi(c2, "Executadas", _fmt_int(m_seg["exec"]), tema="verde")
    render_kpi(c3, "Não Exec.", _fmt_int(m_seg["naoexec"]), tema="laranja")
    render_kpi(c4, "Pendentes", _fmt_int(m_seg["pend"]), tema="cinza")
    render_kpi(
        c5,
        "Quebra Atual",
        f"{m_seg['quebra_atual']:.2%}",
        sub=f"Meta: {sla_meta:.0%}",
        tema=tema_q,
    )

    col_pie, col_gauge = st.columns([1, 2])
    with col_pie:
        fig_pie = go.Figure(
            go.Pie(
                labels=["Executadas", "Não Exec.", "Pendentes"],
                values=[m_seg["exec"], m_seg["naoexec"], m_seg["pend"]],
                hole=0.55,
                marker_colors=["#10B981", "#EF4444", "#94A3B8"],
            )
        )
        fig_pie.update_layout(
            height=280,
            margin=dict(t=20, b=10, l=10, r=10),
            showlegend=True,
            legend=dict(orientation="h"),
        )
        st.plotly_chart(
            fig_pie, use_container_width=True, config={"displayModeBar": False}
        )
    with col_gauge:
        cor_bar = "#EF4444" if m_seg["quebra_atual"] > sla_meta else "#10B981"
        limite_eixo = max(50.0, sla_meta * 100 * 1.6, m_seg["quebra_atual"] * 100 * 1.2)
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
                number={"suffix": "%", "font": {"size": 36}},
                gauge={
                    "axis": {"range": [0, limite_eixo], "ticksuffix": "%"},
                    "bar": {"color": cor_bar},
                    "steps": [
                        {"range": [0, sla_meta * 100], "color": "#DCFCE7"},
                        {"range": [sla_meta * 100, sla_meta * 120], "color": "#FEF9C3"},
                        {"range": [sla_meta * 120, limite_eixo], "color": "#FEE2E2"},
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
    render_section("📈 Projeções de Fechamento")
    cen = {
        n: _obter_resumo_segmento(df_seg, p)
        for n, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]
    }
    c_cen, _ = st.columns([2, 1])
    with c_cen:
        cols = st.columns(3)
        for (nome, cd), col in zip(cen.items(), cols):
            cor_p: TemaKPIType = (
                "vermelho" if cd["fechamento_proj"] > sla_meta else "verde"
            )
            render_kpi_sm(
                col,
                nome,
                f"{cd['fechamento_proj']:.2%}",
                sub=f"NE proj.: {_fmt_int(cd['naoexec_proj'])}",
                tema=cor_p,
            )

    col_data = _resolver_col_data(df_seg)
    if col_data:
        try:
            render_section(f"📅 Tendência Temporal — {col_data}")
            df_tmp = df_seg.copy()
            df_tmp[col_data] = pd.to_datetime(df_tmp[col_data], errors="coerce")
            df_tmp = df_tmp.dropna(subset=[col_data])
            if not df_tmp.empty:
                df_tmp["SEMANA"] = df_tmp[col_data].dt.to_period("W").astype(str)
                df_tmp["IS_NE"] = (
                    df_tmp["Status Contrato"].astype(str).str.upper() == "NÃO EXECUTADA"
                    if "Status Contrato" in df_tmp.columns
                    else False
                )

                # Agrupamento temporal otimizado (sem apply genérico)
                trend = (
                    df_tmp.groupby("SEMANA")["IS_NE"].mean().reset_index(name="QUEBRA")
                )

                fig_line = px.line(trend, x="SEMANA", y="QUEBRA", markers=True)
                fig_line.add_hline(y=sla_meta, line_dash="dash", line_color="#DC2626")
                fig_line.update_layout(yaxis_tickformat=".1%", height=300)
                st.plotly_chart(
                    fig_line, use_container_width=True, config={"displayModeBar": False}
                )
        except Exception:
            pass

    st.markdown("")
    render_section("🛡️ Folga de SLA")
    folga = _obter_folga_sla(df_seg, sla_meta)
    f1, f2, f3 = st.columns(3)
    cor_f: TemaKPIType = (
        "vermelho"
        if folga["estourado"]
        else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
    )
    render_kpi(
        f1,
        "Folga (OS)",
        _fmt_int(np.floor(folga["folga_ne_pendente"])),
        sub="Não Exec. ainda permitidas",
        tema=cor_f,
    )
    render_kpi(
        f2,
        "Execução Mínima",
        _fmt_int(np.ceil(folga["precisa_executar_pendente"])),
        sub="Pendentes a executar",
        tema="azul",
    )
    render_kpi(
        f3,
        "Limite NE Total",
        _fmt_int(folga["limite_ne_total"]),
        sub=f"= {sla_meta:.0%} × {_fmt_int(folga['alocado'])}",
        tema="cinza",
    )

    sim = _calcular_quebra_expurgada(df_seg, m_seg, segmento)
    if sim:
        st.markdown("<br>", unsafe_allow_html=True)
        render_section("🔮 Simulação de Expurgo do Maior Ofensor")
        motivo_html = escape(sim["motivo"])
        dentro = sim["quebra_expurgada"] <= sla_meta
        bg_grad = (
            "linear-gradient(135deg,#ECFDF5 0%,#D1FAE5 100%)"
            if dentro
            else "linear-gradient(135deg,#FFFBEB 0%,#FEF3C7 100%)"
        )
        border_color = badge_bg = "#10B981" if dentro else "#F59E0B"
        status_text = "DENTRO DA META SLA" if dentro else "AINDA FORA DA META SLA"
        call = (
            f"🎯 <b>Alvo Prático:</b> Atuar em <b>'{motivo_html}'</b> resolve o desvio!"
            if dentro
            else f"⚠️ Eliminar <b>'{motivo_html}'</b> ajuda, mas precisa de ações complementares para meta {sla_meta:.0%}."
        )
        st.markdown(
            f"""
<div style="background:{bg_grad};border:1px solid {border_color};border-radius:14px;padding:20px 24px;margin:8px 0 20px 0">
  <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px"><div style="display:flex;gap:10px;align-items:center"><span style="font-size:24px">🔮</span><div><h4 style="margin:0;color:#1E293B;font-size:16px;font-weight:800">Cenário Hipotético: Expurgando a Maior Ofensora</h4><p style="margin:2px 0 0 0;color:#475569;font-size:12px">Simulação desconsiderando o motivo mais recorrente</p></div></div><span style="background:{badge_bg};color:#FFF;font-size:10px;font-weight:700;padding:4px 12px;border-radius:999px">{status_text}</span></div>
  <div style="background:rgba(255,255,255,0.65);border-radius:10px;padding:14px;border:1px dashed rgba(0,0,0,0.08);margin-bottom:16px"><div style="font-size:11px;color:#64748B;font-weight:700">MAIOR OFENSORA</div><div style="font-size:16px;font-weight:700;margin-top:4px;display:flex;gap:8px;flex-wrap:wrap"><span style="color:#DC2626">❌ {motivo_html}</span><span style="background:#FEE2E2;color:#991B1B;font-size:11px;padding:2px 8px;border-radius:4px">{_fmt_int(sim["volume"])} ocorrências</span></div></div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:16px"><div style="background:white;border-radius:8px;padding:12px;border:1px solid #E2E8F0;text-align:center"><div style="font-size:10px;color:#64748B">Quebra Atual</div><div style="font-size:24px;font-weight:800">{sim["quebra_atual"]:.2%}</div></div><div style="background:white;border-radius:8px;padding:12px;border:2px solid {border_color};text-align:center"><div style="font-size:10px;font-weight:700">Quebra com Expurgo</div><div style="font-size:26px;color:{border_color};font-weight:900">{sim["quebra_expurgada"]:.2%}</div></div><div style="background:white;border-radius:8px;padding:12px;border:1px solid #E2E8F0;text-align:center"><div style="font-size:10px;color:#64748B">Redução</div><div style="font-size:24px;color:#2563EB;font-weight:800">📉 −{sim["impacto_abs"]:.2%}</div></div></div>
  <div style="font-size:13px;color:#1E293B">{call}</div>
</div>""",
            unsafe_allow_html=True,
        )


def _sub_causa_raiz(segmento, df_seg):
    render_section(f"🔍 Causa Raiz — {segmento}")
    col_baixa = _resolver_col_baixa(df_seg)
    if not col_baixa:
        render_insight("Coluna de motivo de baixa não identificada.", tipo="alerta")
        return
    df_c = Motor.causa_raiz(df_seg, col_baixa, top_n=8)
    if df_c.empty:
        render_insight("Sem dados para Pareto.", tipo="info")
        return
    render_table_html(
        df_c,
        fmt={"Volume": "{:,.0f}", "% do Total": "{:.2%}", "Acumulado": "{:.2%}"},
        colunas_num=[
            c for c in ["Volume", "% do Total", "Acumulado"] if c in df_c.columns
        ],
        height=380,
    )
    st.markdown("<br>")
    conf = SEGMENTOS_CONFIG.get(
        segmento, {"cor_primaria": "#0F172A", "cor_secundaria": "#475569"}
    )
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_c["Motivo de Baixa"],
            y=df_c["Volume"],
            name="Volume",
            marker_color=conf["cor_primaria"],
            text=df_c["Volume"],
            textposition="outside",
            textfont=dict(size=13),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_c["Motivo de Baixa"],
            y=df_c["Acumulado"],
            name="Acumulado %",
            yaxis="y2",
            mode="lines+markers+text",
            line=dict(color=conf["cor_secundaria"], width=3),
            text=[f"{v:.1%}" for v in df_c["Acumulado"]],
            textposition="top center",
        )
    )
    fig.add_shape(
        type="line",
        xref="paper",
        x0=0,
        x1=1,
        yref="y2",
        y0=0.8,
        y1=0.8,
        line=dict(color="#F59E0B", width=2, dash="dash"),
    )
    fig.add_annotation(
        xref="paper",
        x=1,
        yref="y2",
        y=0.8,
        text="80% Pareto",
        showarrow=False,
        xanchor="right",
        font=dict(color="#F59E0B", size=12),
    )
    fig.update_layout(
        title=f"Pareto — {segmento}",
        yaxis=dict(title="Volume"),
        yaxis2=dict(
            title="Acumulado %",
            overlaying="y",
            side="right",
            tickformat=".0%",
            range=[0, 1.18],
        ),
        height=560,
        xaxis=dict(tickangle=-30),
        margin=dict(t=60, b=160),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if _COL_REGIAO in df_seg.columns and col_baixa:
        try:
            render_section("🗺️ Quebra por Região")
            reg_agg = (
                df_seg.groupby(_COL_REGIAO)
                .apply(lambda x: _obter_resumo_segmento(x, 0.2)["quebra_atual"])
                .reset_index(name="Quebra")
            )
            fig_reg = px.bar(
                reg_agg,
                x=_COL_REGIAO,
                y="Quebra",
                color="Quebra",
                color_continuous_scale="Reds",
            )
            fig_reg.update_layout(yaxis_tickformat=".1%", height=320)
            st.plotly_chart(
                fig_reg, use_container_width=True, config={"displayModeBar": False}
            )
        except Exception:
            pass


def _sub_tecnicos(segmento, df_seg, p_ot, p_base, p_pess, min_aloc, top_n, sla_meta):
    render_section(f"👤 Técnicos com Maior Quebra — {segmento}")
    df_tec = Motor.tecnicos_criticos(
        df_seg, segmento, p_base, min_aloc, top_n, p_ot=p_ot, p_pess=p_pess
    )
    if df_tec.empty:
        render_insight("Não há técnicos com volume suficiente.", tipo="info")
        return
    render_table_html(
        df_tec,
        fmt={
            "Quebra Atual": "{:.2%}",
            "Fechamento Otimista": "{:.2%}",
            "Fechamento Base": "{:.2%}",
            "Fechamento Pessimista": "{:.2%}",
        },
        height=450,
    )
    st.download_button(
        "📥 Exportar Técnicos",
        Utils.gerar_excel(df_tec, f"Tec_{segmento[:20]}"),
        f"tecnicos_{_slug(segmento)}.xlsx",
        key=f"dl_tec_{segmento}",
    )
    if {"TÉCNICO", "Fechamento Base"}.issubset(df_tec.columns):
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
            height=max(360, len(df_plot) * 42),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _sub_plano_acao(segmento, df_seg, p_base, sla_meta):
    render_section(f"🎯 Plano de Ação — {segmento}")
    folga = _obter_folga_sla(df_seg, sla_meta)
    cen = _obter_resumo_segmento(df_seg, p_base)
    excesso = max(0.0, folga["naoexec"] - folga["limite_ne_total"])
    pend_exec = folga["precisa_executar_pendente"]
    col_d, col_a = st.columns([1, 1.5])

    with col_d:
        render_section("📋 Diagnóstico")
        render_kpi_sm(
            col_d,
            "Excesso de NE",
            _fmt_int(excesso),
            sub="OS além do permitido",
            tema="vermelho" if excesso > 0 else "verde",
        )
        render_kpi_sm(
            col_d,
            "Pendentes a Executar",
            _fmt_int(np.ceil(pend_exec)),
            sub=f"Mínimo para meta {sla_meta:.0%}",
            tema="azul",
        )
        render_kpi_sm(
            col_d,
            "Proj. Base",
            f"{cen['fechamento_proj']:.2%}",
            sub=f"c/ {p_base:.0%} quebra pend.",
            tema="vermelho" if cen["fechamento_proj"] > sla_meta else "verde",
        )
    acoes = []
    if folga["estourado"]:
        acoes.append(
            (
                "🔴 IMEDIATA",
                f"Acionar plantão para recuperar {_fmt_int(excesso)} OS não executadas.",
                "alerta",
            )
        )
    if pend_exec > 0:
        acoes.append(
            (
                "🟠 ALTA",
                f"Garantir execução de {_fmt_int(np.ceil(pend_exec))} OS pendentes.",
                "alerta",
            )
        )
    acoes.extend(SEGMENTOS_CONFIG.get(segmento, {"acoes": []})["acoes"])
    with col_a:
        render_section("✅ Ações Recomendadas")
        for pri, ac, tp in acoes:
            render_insight(f"**{pri}** — {ac}", tipo=cast(TipoInsightType, tp))
    df_plano = pd.DataFrame(
        [{"Segmento": segmento, "Prioridade": p, "Ação": a} for p, a, _ in acoes]
    )
    if not df_plano.empty:
        st.download_button(
            "📥 Exportar Plano",
            Utils.gerar_excel(df_plano, f"Plano_{segmento[:20]}"),
            f"plano_{_slug(segmento)}.xlsx",
            key=f"dl_plano_{segmento}",
        )


def _sub_pendentes(segmento, df_seg):
    render_section(f"📋 Contratos Pendentes — {segmento}")
    df_pend = _build_df_pendentes(df_seg)
    total = len(df_pend)

    def _nunique(col):
        return (
            int(df_pend[col].replace("N/D", pd.NA).dropna().nunique())
            if col in df_pend.columns
            else 0
        )

    m1, m2, m3 = st.columns(3)
    render_kpi(
        m1,
        "Total Pendentes",
        _fmt_int(total),
        sub="contratos sem execução",
        tema="laranja" if total > 0 else "verde",
    )
    render_kpi(m2, "Técnicos", _fmt_int(_nunique("Técnico")), tema="azul")
    render_kpi(m3, "Monitores", _fmt_int(_nunique("Monitor")), tema="cinza")
    if df_pend.empty:
        render_insight("Nenhum pendente listado.", tipo="ok")
        return

    def _opts(col):
        return ["Todos"] + sorted(
            str(x)
            for x in df_pend[col].dropna().unique()
            if str(x) not in {"N/D", "nan"}
        )

    with st.expander("🔎 Filtros rápidos"):
        fc1, fc2 = st.columns(2)
        f_tec = fc1.selectbox("Técnico", _opts("Técnico"), key=f"pend_f_tec_{segmento}")
        f_mon = fc2.selectbox("Monitor", _opts("Monitor"), key=f"pend_f_mon_{segmento}")
    df_view = df_pend.copy()
    if f_tec != "Todos":
        df_view = df_view[df_view["Técnico"].astype(str) == f_tec]
    if f_mon != "Todos":
        df_view = df_view[df_view["Monitor"].astype(str) == f_mon]
    st.markdown(f"**Exibindo {_fmt_int(len(df_view))} de {_fmt_int(total)}**")
    render_table_html(df_view.reset_index(drop=True), height=480)
    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button(
        "📥 Filtrado",
        Utils.gerar_excel(df_view, "Filtrado"),
        f"pendentes_{_slug(segmento)}_filtrado.xlsx",
        key=f"dl_pend_f_{segmento}",
        use_container_width=True,
    )
    c2.download_button(
        "📥 Completo",
        Utils.gerar_excel(df_pend, "Completo"),
        f"pendentes_{_slug(segmento)}_completo.xlsx",
        key=f"dl_pend_c_{segmento}",
        use_container_width=True,
    )


def _sub_sem_registro(segmento, df_seg):
    render_section(f"⚠️ Motivo de Baixa: Sem Registro — {segmento}")
    col_baixa = _resolver_col_baixa(df_seg)
    if not col_baixa:
        render_insight("Coluna de baixa não encontrada.", tipo="alerta")
        return
    serie = df_seg[col_baixa].fillna("").astype(str).str.strip().str.upper()
    mask = serie.isin(["SEM REGISTRO", "SEM_REGISTRO", "", "NAN", "NONE"])
    if "Status Contrato" in df_seg.columns:
        mask &= (
            ~df_seg["Status Contrato"]
            .astype(str)
            .str.strip()
            .str.upper()
            .isin(STATUS_PENDENTE)
        )
    df_sr = df_seg[mask].copy()
    m1, m2, m3 = st.columns(3)
    render_kpi(
        m1,
        "Total Sem Registro",
        _fmt_int(len(df_sr)),
        tema="vermelho" if len(df_sr) > 0 else "verde",
    )
    render_kpi(
        m2,
        "Técnicos",
        _fmt_int(df_sr["TÉCNICO"].nunique() if "TÉCNICO" in df_sr else 0),
        tema="laranja",
    )
    render_kpi(
        m3,
        "Monitores",
        _fmt_int(df_sr["MONITOR"].nunique() if "MONITOR" in df_sr else 0),
        tema="azul",
    )
    if df_sr.empty:
        render_insight("Nenhum contrato sem registro.", tipo="ok")
        return
    cols_pad = [
        c
        for c in [
            "CONTRATO",
            "TÉCNICO",
            "MONITOR",
            _COL_REGIAO,
            "Status Contrato",
            col_baixa,
            "TOTAL DE TAREFAS",
        ]
        if c in df_sr.columns
    ]
    df_view = df_sr[cols_pad].copy() if cols_pad else df_sr.copy()
    render_table_html(df_view.reset_index(drop=True), height=480)
    st.download_button(
        "📥 Exportar Sem Registro",
        Utils.gerar_excel(df_view, "Sem_Registro"),
        f"sem_registro_{_slug(segmento)}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        key=f"dl_sr_{segmento}",
        use_container_width=True,
    )


def _sub_comparativo(df_full, sla_meta, p_base, p_ot, p_pess):
    render_section("📊 Comparativo entre Segmentos")
    if "TIPO_SERVICO" not in df_full.columns:
        render_insight("Sem coluna TIPO_SERVICO no arquivo atual.", tipo="alerta")
        return
    linhas = []
    for seg in sorted(df_full["TIPO_SERVICO"].dropna().unique()):
        d = df_full[df_full["TIPO_SERVICO"] == seg]
        m = _obter_resumo_segmento(d, p_base)
        f = _obter_folga_sla(d, sla_meta)
        linhas.append(
            {
                "Segmento": seg,
                "Alocado": m["alocado"],
                "Quebra Atual": m["quebra_atual"],
                "Fechamento Base": m["fechamento_proj"],
                "Folga": f["folga_ne_pendente"],
                "vs Meta": m["fechamento_proj"] - sla_meta,
            }
        )
    df_comp = pd.DataFrame(linhas)
    if df_comp.empty:
        return

    # Renderização de colunas sem aninhamento "with st" incorreto
    c1, c2, c3 = st.columns(3)
    for i, (_, row) in enumerate(df_comp.iterrows()):
        col_target = [c1, c2, c3][i % 3]
        tema = "vermelho" if row["Quebra Atual"] > sla_meta else "verde"
        render_kpi(
            col_target,
            row["Segmento"],
            f"{row['Quebra Atual']:.2%}",
            sub=f"Alocado {_fmt_int(row['Alocado'])} | Folga {_fmt_int(row['Folga'])}",
            tema=tema,
        )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_comp["Segmento"],
            y=df_comp["Quebra Atual"],
            name="Quebra Atual",
            marker_color="#0F172A",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df_comp["Segmento"],
            y=df_comp["Fechamento Base"],
            name="Fechamento Base",
            marker_color="#3B82F6",
        )
    )
    fig.add_hline(
        y=sla_meta,
        line_dash="dash",
        line_color="#DC2626",
        annotation_text=f"Meta {sla_meta:.0%}",
    )
    fig.update_layout(barmode="group", yaxis_tickformat=".1%", height=380)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    render_table_html(
        df_comp,
        fmt={
            "Quebra Atual": "{:.2%}",
            "Fechamento Base": "{:.2%}",
            "vs Meta": "{:.2%}",
        },
        height=260,
    )
    if _COL_REGIAO in df_full.columns:
        render_section("🗺️ Quebra por Região x Segmento")
        try:
            heat = (
                df_full.groupby(["TIPO_SERVICO", _COL_REGIAO])
                .apply(
                    lambda x: _obter_resumo_segmento(x, p_base)["quebra_atual"],
                    include_groups=False,
                )
                .reset_index(name="Quebra")
            )
            fig_h = px.density_heatmap(
                heat,
                x=_COL_REGIAO,
                y="TIPO_SERVICO",
                z="Quebra",
                color_continuous_scale="Reds",
                histfunc="avg",
            )
            fig_h.update_layout(height=320)
            st.plotly_chart(
                fig_h, use_container_width=True, config={"displayModeBar": False}
            )
        except Exception:
            pass


# =====================================================================
# FLUXO PRINCIPAL
# =====================================================================
def main():
    if st.session_state.get("df_memoria") is None:
        render_insight(
            "Nenhuma base carregada. Volte à página 'Dashboard Geral' e envie os dados do Excel.",
            tipo="alerta",
        )
        return

    # Cópia defensiva dos atributos e metadados
    df_full = _preparar_base(st.session_state["df_memoria"].copy())
    df_full.attrs = dict(getattr(st.session_state["df_memoria"], "attrs", {}))

    with st.sidebar:
        st.markdown("### 📁 Escolha a Carteira")
        opcoes = list(SEGMENTOS_CONFIG.keys()) + ["Todos os Segmentos"]
        segmento = st.selectbox(
            "Segmento:", opcoes, index=0, key="sel_segmento_principal"
        )
        conf = SEGMENTOS_CONFIG.get(
            segmento, {"sla_default": 0.20, "p_base_default": 20}
        )
        st.divider()
        st.header(f"🎯 Filtros {segmento}")
        monitores = _opcoes_filtro(
            df_full, "MONITOR", {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon = st.selectbox("👔 Monitor", monitores, key=f"mon_{segmento}")
        df_filt = (
            df_full
            if sel_mon == "Todos" or "MONITOR" not in df_full.columns
            else df_full[df_full["MONITOR"].astype(str) == sel_mon]
        )
        df_filt.attrs = dict(getattr(df_full, "attrs", {}))
        tecnicos = _opcoes_filtro(df_filt, "TÉCNICO", {"nan", "NÃO MAPEADO"})
        sel_tec = st.selectbox("👷 Técnico", tecnicos, key=f"tec_{segmento}")
        df = (
            df_filt
            if sel_tec == "Todos" or "TÉCNICO" not in df_filt.columns
            else df_filt[df_filt["TÉCNICO"].astype(str) == sel_tec]
        )
        df.attrs = dict(getattr(df_filt, "attrs", {}))
        st.divider()
        st.subheader("🔮 Probabilidades")
        p_ot = st.slider("Otimista (%)", 0, 100, 15, 5, key=f"pot_{segmento}") / 100.0
        p_base = (
            st.slider(
                "Base (%)",
                0,
                100,
                int(conf["p_base_default"]),
                5,
                key=f"pbase_{segmento}",
            )
            / 100.0
        )
        p_pess = (
            st.slider("Pessimista (%)", 0, 100, 50, 5, key=f"ppess_{segmento}") / 100.0
        )
        if not (p_ot <= p_base <= p_pess):
            st.warning("⚠️ Ajuste recomendado: Otimista ≤ Base ≤ Pessimista")
        st.divider()
        sla_meta = (
            st.number_input(
                "Meta SLA (%)",
                0.0,
                100.0,
                float(conf["sla_default"] * 100),
                0.5,
                key=f"sla_v_{segmento}",
            )
            / 100.0
        )
        min_aloc = st.number_input(
            "Mín. OS por técnico", 1, 500, 1, 1, key=f"minaloc_{segmento}"
        )
        min_aloc = float(min_aloc)
        top_n = st.number_input(
            "Top N técnicos", 5, 1000, 50, 5, key=f"topn_{segmento}"
        )
        top_n = int(top_n)
        st.divider()
        with st.expander("⚙️ Sistema", expanded=False):
            if st.button("🔄 Reiniciar", use_container_width=True):
                st.rerun()
            if st.button("🗑️ Limpar Cache", use_container_width=True):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Cache limpo!")
                st.rerun()
        st.divider()
        render_debug_criterios(df_full, expanded=False)

    if df.empty:
        render_insight(
            "Nenhum dado encontrado para os filtros e segmentação selecionados.",
            tipo="alerta",
        )
        return
    _injetar_css_dinamico(segmento)
    regioes = (
        [
            str(r).strip().upper()
            for r in df[_COL_REGIAO].dropna().unique()
            if str(r).strip()
        ]
        if _COL_REGIAO in df.columns
        else ["OUTRAS"]
    )
    _render_topo_fixo(segmento, regioes, len(df))

    if segmento == "Todos os Segmentos":
        df_seg = df.copy()
        df_seg.attrs = dict(getattr(df, "attrs", {}))
        m_seg = _obter_resumo_segmento(df_seg, p_base)
        folga = _obter_folga_sla(df_seg, sla_meta)
        _render_card_status("Consolidado Geral", m_seg, sla_meta)
        _render_alerts_chips(_gerar_alertas(df_seg, m_seg, sla_meta, folga))

        c1, c2, _ = st.columns([1, 1, 2])
        h = _hash_df(df_seg)
        key_pdf = f"pdf_bytes_Todos_{h}_{sla_meta}_{p_base}"
        with c1:
            if st.button(
                "⚙️ Gerar PDF Comparativo",
                key="gen_pdf_todos",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Gerando PDF Comparativo..."):
                    try:
                        st.session_state[key_pdf] = PDFExecutivoComparativo.gerar(
                            df_seg, sla_meta, p_ot, p_base, p_pess, min_aloc, top_n
                        )
                    except Exception as e:
                        st.error(f"Falha de PDF: {e}")
        with c2:
            if key_pdf in st.session_state:
                st.download_button(
                    "📄 Baixar PDF",
                    st.session_state[key_pdf],
                    f"comparativo_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    "application/pdf",
                    key="dl_pdf_todos",
                    use_container_width=True,
                )
        st.divider()
        t1, t2, t3, t4, t5 = st.tabs(
            [
                "📊 Comparativo",
                "🔍 Causa Raiz Global",
                "👤 Técnicos Global",
                "📋 Pendentes Global",
                "⚠️ Sem Registro Global",
            ]
        )
        with t1:
            _sub_comparativo(df, sla_meta, p_base, p_ot, p_pess)
            _sub_visao_geral(
                "Consolidado Geral", df_seg, m_seg, p_ot, p_base, p_pess, sla_meta
            )
        with t2:
            _sub_causa_raiz("Todos os Segmentos", df_seg)
        with t3:
            _sub_tecnicos(
                "Todos os Segmentos",
                df_seg,
                p_ot,
                p_base,
                p_pess,
                min_aloc,
                top_n,
                sla_meta,
            )
        with t4:
            _sub_pendentes("Todos os Segmentos", df_seg)
        with t5:
            _sub_sem_registro("Todos os Segmentos", df_seg)
        return

    # Fluxo por segmento único
    df_seg = (
        df[df["TIPO_SERVICO"] == segmento].copy()
        if "TIPO_SERVICO" in df.columns
        else df.copy()
    )
    df_seg.attrs = dict(getattr(df, "attrs", {}))
    if df_seg.empty:
        render_insight(
            f"Nenhum registro encontrado para o segmento **{segmento}**.", tipo="info"
        )
        return
    m_seg = _obter_resumo_segmento(df_seg, p_base)
    folga = _obter_folga_sla(df_seg, sla_meta)
    _render_card_status(segmento, m_seg, sla_meta)
    _render_alerts_chips(_gerar_alertas(df_seg, m_seg, sla_meta, folga))

    h = _hash_df(df_seg)
    key_pdf = f"pdf_bytes_{_slug(segmento)}_{h}_{sla_meta}_{p_base}_{p_ot}_{p_pess}_{min_aloc}_{top_n}"
    col_btn, col_dl, col_desc = st.columns([1, 1, 2])
    with col_btn:
        if st.button(
            f"⚙️ Gerar PDF — {segmento}",
            key=f"gen_pdf_{segmento}",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner("Gerando PDF..."):
                try:
                    st.session_state[key_pdf] = SEGMENTOS_CONFIG[segmento][
                        "pdf_class"
                    ].gerar(df_seg, sla_meta, p_ot, p_base, p_pess, min_aloc, top_n)
                except Exception as e:
                    st.error(f"Falha de PDF: {e}")
    with col_dl:
        if key_pdf in st.session_state:
            st.download_button(
                "📄 Baixar PDF",
                st.session_state[key_pdf],
                f"relatorio_{_slug(segmento)}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                "application/pdf",
                key=f"dl_pdf_{segmento}",
                use_container_width=True,
            )
    with col_desc:
        render_insight(
            "O PDF Executivo inclui cenários, curva de Pareto e listagem de ofensores críticos.",
            tipo="info",
        )
    st.divider()
    sub1, sub2, sub3, sub4, sub5, sub6 = st.tabs(
        [
            "📊 Visão Geral",
            "🔍 Causa Raiz",
            "👤 Técnicos",
            "🎯 Plano de Ação",
            "📋 Pendentes",
            "⚠️ Sem Registro",
        ]
    )
    with sub1:
        _sub_visao_geral(segmento, df_seg, m_seg, p_ot, p_base, p_pess, sla_meta)
    with sub2:
        _sub_causa_raiz(segmento, df_seg)
    with sub3:
        _sub_tecnicos(segmento, df_seg, p_ot, p_base, p_pess, min_aloc, top_n, sla_meta)
    with sub4:
        _sub_plano_acao(segmento, df_seg, p_base, sla_meta)
    with sub5:
        _sub_pendentes(segmento, df_seg)
    with sub6:
        _sub_sem_registro(segmento, df_seg)


if __name__ == "__main__":
    main()
