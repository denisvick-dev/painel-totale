"""
quebra_unificada.py
===================
Análise de Quebra por Segmento (Novos Domicílios / Migração / PME + Comparativo)
Inclui aba dedicada para contratos com MOTIVO DE BAIXA = SEM REGISTRO.

Version: 2.3.0 (esqueleto padrão do portal + camada compartilhada de componentes/serviços)
Author: TOTALE Tecnologia
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, cast

# ── Bootstrap sys.path ───────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_ROOT = _DIR.parent
for _p in (_DIR, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from components.componentes import aplicar_estilo as _aplicar_estilo_global
from components.componentes import (
    render_hero,
    render_hero_migracao,
    render_hero_novos_domicilios,
    render_hero_pme,
    render_insight,
    render_kpi,
    render_kpi_sm,
    render_table_html,
)
from components.criterios import classificar_tipo_servico, render_debug_criterios

# ── Camada compartilhada do portal (esqueleto padrão + serviços) ─────────────
from components.css_paginas import aplicar_css_cartao_segmento
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.layout_pagina import cabecalho_secao
from services.dados_sessao import CHAVE_MEMORIA, obter_dataframe
from services.texto import formatar_inteiro, sem_acento

#: Seções ancoradas do sumário (títulos usados em ``cabecalho_secao``/``secao``).
SECOES_PAGINA: tuple[str, ...] = (
    "Visão geral",
    "Causa raiz",
    "Técnicos",
    "Plano de ação",
    "Pendentes",
    "Sem registro",
    "Exportação",
)

# ── Importação Inteligente e Resiliente de quebra.py ──────────────────
try:
    from pages.quebra_geral import (
        Config,
        DataLoader,
        Motor,
        Utils,
        _aplicar_etl_robo_global,
        _cache_matriz,
    )
except ImportError:
    DataLoader = None  # type: ignore[assignment]
    _aplicar_etl_robo_global = None  # type: ignore[assignment]
    _cache_matriz = None  # type: ignore[assignment]
    try:
        import quebra  # type: ignore

        Config = quebra.Config
        Motor = quebra.Motor
        Utils = quebra.Utils
    except ImportError:
        from quebra import Config, Motor, Utils  # type: ignore

# ── Tipos Locais para Robustez Estática ───────────────────────────────
TemaKPIType = Literal["azul", "verde", "vermelho", "laranja", "cinza", "roxo", "amarelo", "escuro"]
TipoInsightType = Literal["ok", "info", "alerta", "critico", "acao"]

_COL_REGIAO: str = str(getattr(Config, "COL_REGIAO", "REGIÃO"))


def _obter_folga_sla(df: pd.DataFrame, sla_meta: float) -> dict[str, Any]:
    """Wrapper seguro com tipagem explícita para Motor.folga_sla."""
    folga_fn = getattr(Motor, "folga_sla", None)
    if folga_fn is not None and callable(folga_fn):
        folga_resultado: Any = folga_fn(df, sla_meta)  # pylint: disable=not-callable
        return cast(dict[str, Any], folga_resultado)

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
        df["Status Contrato"].astype(str).str.upper().isin(["NÃO EXECUTADA", "NAO EXECUTADA"])
    ]
    df_pend = df[
        df["Status Contrato"]
        .astype(str)
        .str.upper()
        .isin(["PENDENTE", "EM ABERTO", "ABERTO", "EM ROTA"])
    ]

    if "TOTAL DE TAREFAS" in df.columns:
        naoexec = float(pd.to_numeric(df_ne["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum())
        pend = float(pd.to_numeric(df_pend["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum())
        alocado = float(pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum())
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
    """Calcula volumetrias e projeções do segmento."""
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
        nao_exec = int(pd.to_numeric(df_ne["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum())
        pendentes = int(pd.to_numeric(df_pend["TOTAL DE TAREFAS"], errors="coerce").fillna(1).sum())
    else:
        executadas = int((s_status == "EXECUTADA").sum())
        nao_exec = int(s_status.isin(["NÃO EXECUTADA", "NAO EXECUTADA"]).sum())
        pendentes = int(s_status.isin(["PENDENTE", "EM ABERTO", "ABERTO", "EM ROTA"]).sum())

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
st.set_page_config(page_title="Análise de Quebra | TOTALE", page_icon="📉", layout="wide")
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
#: Formatação de inteiros delegada a :func:`services.texto.formatar_inteiro`
#: (fonte única do portal; antes cada página tinha a sua cópia).
fmt_int_br = formatar_inteiro
_fmt_int = formatar_inteiro


def _norm_txt(s: Any) -> str:
    """Chave de comparação de colunas: sem acento, maiúscula, sem ``_`` nem ``.``."""
    return sem_acento(str(s)).upper().strip().replace("_", " ").replace(".", "")


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


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_")


def _hash_df(df: pd.DataFrame) -> str:
    try:
        b = pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes()
        return hashlib.md5(b).hexdigest()[:10]
    except Exception:
        return str(len(df))


def _causa_raiz_segmento(df: pd.DataFrame, segmento: str, top_n: int = 8) -> pd.DataFrame:
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
    COR_OK = "#047857"
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
    def _fmt(cls, v: Any, col: str = "") -> str:
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
    def _calcular_larguras(cls, df: pd.DataFrame) -> list[float]:
        if df.empty:
            return [cls.LARGURA_UTIL]
        pesos = []
        for col in df.columns:
            max_len = len(str(col))
            for val in df[col].head(50):
                max_len = max(max_len, len(cls._fmt(val, str(col))))
            pesos.append(min(max(max_len, 5), 30))
        total = sum(pesos) or 1
        return [(p / total) * cls.LARGURA_UTIL for p in pesos]

    @classmethod
    def _estilos(cls) -> Any:
        s = getSampleStyleSheet()
        if "X_Titulo" not in s:
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
        if "X_Subtitulo" not in s:
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
        if "X_Secao" not in s:
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
    def _cabecalho(cls, s: Any) -> Table:
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
    def _tab(
        cls,
        df: pd.DataFrame,
        limite: int | None = None,
        larguras: list[float] | None = None,
        cor_col_quebra: str | None = None,
        sla_meta: float = 0.25,
    ) -> Table:
        def _interna() -> Table:
            if df is None or df.empty:
                t = Table([["Sem dados disponíveis"]], colWidths=[cls.LARGURA_UTIL * cm])
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
                        Paragraph(cls._fmt(row[c], str(c)), st_cl if i == 0 else st_c)
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
            if not col_widths or sum(col_widths) == 0:
                col_widths = [cls.LARGURA_UTIL * cm / max(1, len(base.columns))] * len(base.columns)
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
                        (colors.white if i % 2 == 1 else colors.HexColor(cls.COR_LINHA_ALT)),
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
                        bg_c, tx_c = colors.HexColor("#FEE2E2"), colors.HexColor(cls.COR_CRITICO)
                    elif val > sla_meta * 0.85:
                        bg_c, tx_c = colors.HexColor("#FEF9C3"), colors.HexColor(cls.COR_ALERTA)
                    else:
                        bg_c, tx_c = colors.HexColor("#DCFCE7"), colors.HexColor(cls.COR_OK)
                    style.extend(
                        [
                            ("BACKGROUND", (col_idx, row_i), (col_idx, row_i), bg_c),
                            ("TEXTCOLOR", (col_idx, row_i), (col_idx, row_i), tx_c),
                            (
                                "FONTNAME",
                                (col_idx, row_i),
                                (col_idx, row_i),
                                "Helvetica-Bold",
                            ),
                        ]
                    )
            tab.setStyle(TableStyle(style))
            return tab

        wrapper = Table([[_interna()]], colWidths=[cls.LARGURA_UTIL * cm], hAlign="CENTER")
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
        canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
        canvas.setLineWidth(0.5)
        canvas.line(0.8 * cm, 1.05 * cm, page_w - 0.8 * cm, 1.05 * cm)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(
            0.8 * cm,
            0.52 * cm,
            f"{cls.NOME_SEGMENTO} — Gestão de Quebra | {datetime.now().strftime('%d/%m/%Y %H:%M')} | Confidencial",
        )
        canvas.drawRightString(page_w - 0.8 * cm, 0.52 * cm, f"Página {doc.page}")
        canvas.restoreState()

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
            title=f"Relatório Executivo — {cls.NOME_SEGMENTO}",
            author="TOTALE",
        )
        s = cls._estilos()
        el = [
            cls._cabecalho(s),
            Spacer(1, 0.8 * cm),
            Paragraph("1 ─ Cenários de Fechamento", s["X_Secao"]),
        ]
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
        el.extend([Spacer(1, 0.5 * cm), Paragraph("2 ─ Técnicos Críticos", s["X_Secao"])])
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
        el.extend(
            [
                Spacer(1, 0.5 * cm),
                Paragraph("3 ─ Principais Causas de Quebra (Pareto)", s["X_Secao"]),
            ]
        )
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
    COR_PRIMARIA = "#012869"
    COR_SECUNDARIA = "#4E7FC4"
    COR_LINHA_ALT = "#F4F7FC"
    COR_SUBTITULO = "#9DB9E4"
    NOME_SEGMENTO = "Novos Domicílios"
    DESCRICAO = "Adesão e Novas Instalações"


class PDFExecutivoMigracao(_PDFExecutivoBase):
    COR_PRIMARIA = "#C2410C"
    COR_SECUNDARIA = "#F37C04"
    COR_LINHA_ALT = "#FFF7ED"
    COR_SUBTITULO = "#FED7AA"
    NOME_SEGMENTO = "Migração"
    DESCRICAO = "Mudança de Pacote + FLAG_GPON = Sim"


class PDFExecutivoPME(_PDFExecutivoBase):
    COR_PRIMARIA = "#0A48AA"
    COR_SECUNDARIA = "#FFB870"
    COR_TEXTO = "#122033"
    COR_LINHA_ALT = "#F4F7FC"
    COR_SUBTITULO = "#9DB9E4"
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
            el.extend(
                [
                    Paragraph("1 ─ Comparativo por Segmento (Base)", s["X_Secao"]),
                    cls._tab(
                        pd.DataFrame(comp),
                        cor_col_quebra="Fechamento Base",
                        sla_meta=sla_meta,
                    ),
                    Spacer(1, 0.5 * cm),
                ]
            )
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
        el.extend(
            [
                cls._tab(pd.DataFrame(cen), cor_col_quebra="Fechamento", sla_meta=sla_meta),
                Spacer(1, 0.5 * cm),
                Paragraph("3 ─ Técnicos Críticos (Geral)", s["X_Secao"]),
            ]
        )
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
        "cor_secundaria": "#4E7FC4",
        "grad_hero": "linear-gradient(128deg, #011838 0%, #012869 48%, #123E86 118%)",
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
        "cor_primaria": "#F37C04",
        "cor_secundaria": "#C2410C",
        "grad_hero": "linear-gradient(128deg, #011838 0%, #012869 52%, #0A48AA 100%)",
        "sombra_hero": "rgba(1,40,105,0.28)",
        "sla_default": SLA_MIGRACAO_DEFAULT,
        "p_base_default": 25,
        "pdf_class": PDFExecutivoMigracao,
        "hero_fn": render_hero_migracao,
        "hero_kwargs": {"badge": "MIGRAÇÃO DE DADOS", "icone": "🔄"},
        "acoes": [("🔴 ALTA", "Verificar estoque de equipamentos (ONT/ONU).", "alerta")],
    },
    "PME": {
        "icone": "🏢",
        "subtitulo": "Análise estratégica dedicada às Pequenas e Médias Empresas",
        "cor_primaria": "#0A48AA",
        "cor_secundaria": "#FFB870",
        "grad_hero": "linear-gradient(128deg, #012869 0%, #0A48AA 52%, #123E86 100%)",
        "sombra_hero": "rgba(1,40,105,0.28)",
        "sla_default": SLA_PME_DEFAULT,
        "p_base_default": 20,
        "pdf_class": PDFExecutivoPME,
        "hero_fn": render_hero_pme,
        "hero_kwargs": {"badge": "PME CONNECT", "icone": "🚀"},
        "acoes": [("🔴 ALTA", "Verificar técnicos habilitados em PME.", "acao")],
    },
}


def render_hero_segmento(segmento: str, regioes: list[str], total: int) -> None:
    """Herói da página: o do Design System para cada carteira (ou o corporativo).

    Substitui ``_render_hero_comparativo``/``_html_resultado_base`` — HTML e CSS
    próprios que duplicavam o cabeçalho padrão. As bases analisadas viram legenda,
    com as regiões já usadas pelos chips de contexto.
    """
    conf = SEGMENTOS_CONFIG.get(str(segmento), {})
    hero_fn = conf.get("hero_fn")
    if hero_fn is None:
        render_hero(
            "Quebra por Segmento",
            "Visão consolidada de Novos Domicílios, Migração e PME.",
            badge="RELATÓRIO OPERACIONAL",
        )
    else:
        hero_fn(
            titulo=f"{segmento} — Quebra de Agenda",
            subtitulo=str(conf.get("subtitulo", "")),
            **conf.get("hero_kwargs", {}),
        )
    nomes = sorted({str(regiao).strip().upper() for regiao in regioes if str(regiao).strip()})
    if total > 0 and nomes:
        st.caption(f"Bases analisadas: {', '.join(nomes)} · {fmt_int_br(total)} registros")


def _render_card_status(segmento: str, m_seg: Any, sla_meta: float) -> None:
    quebra = float(m_seg["quebra_atual"])
    alocado = int(m_seg.get("alocado", 0))
    dentro = quebra <= sla_meta
    cor_status = "#047857" if dentro else "#B91C1C"
    cor_fundo = "#ECFDF5" if dentro else "#FEF2F2"
    cor_texto = "#065F46" if dentro else "#991B1B"
    rotulo = "Dentro do SLA" if dentro else "Acima do SLA"
    cor_marca = escape(str(SEGMENTOS_CONFIG.get(segmento, {}).get("cor_primaria", "#012869")))
    progresso = min(100.0, (quebra / (sla_meta * 2)) * 100) if sla_meta > 0 else 0.0
    pos_meta = 50 if sla_meta > 0 else 0
    st.markdown(
        f"""
<div class="status-card" style="--status:{cor_status};--brand:{cor_marca}">
  <div class="status-card__header">
    <div><p class="status-card__eyebrow">Indicador operacional</p><div class="status-card__title">{escape(segmento)}</div></div>
    <span class="status-pill" style="background:{cor_fundo};color:{cor_texto};border-color:{cor_status}">{rotulo}</span>
  </div>
  <div class="status-card__metrics">
    <div class="status-metric"><span class="status-metric__label">Quebra atual</span><span class="status-metric__value">{quebra:.2%}</span></div>
    <div class="status-metric"><span class="status-metric__label">Meta SLA</span><span class="status-metric__value">{sla_meta:.2%}</span></div>
    <div class="status-metric"><span class="status-metric__label">Alocado</span><span class="status-metric__value">{_fmt_int(alocado)}</span></div>
  </div>
  <div class="status-card__bar-labels"><span>0%</span><span>Meta {sla_meta:.2%}</span><span>{sla_meta * 2:.0%}</span></div>
  <div class="status-track"><div class="status-fill" style="width:{progresso:.2f}%"></div><span class="status-target" style="left:{pos_meta}%"></span></div>
  <div class="status-card__foot">Escala visual apresentada até duas vezes a meta.</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _gerar_alertas(
    df_seg: pd.DataFrame, m_seg: dict[str, Any], sla_meta: float, folga: dict[str, Any]
) -> list[dict[str, Any]]:
    alerts = []
    quebra = float(m_seg.get("quebra_atual", 0))
    pend = float(m_seg.get("pend", 0))
    if quebra > sla_meta:
        alerts.append(
            {
                "tipo": "critico",
                "icone": "🔴",
                "msg": f"Quebra {quebra:.2%} acima da meta {sla_meta:.0%} (+{quebra - sla_meta:.2%})",
            }
        )
    if folga.get("estourado"):
        alerts.append(
            {
                "tipo": "critico",
                "icone": "🚨",
                "msg": f"Estouro de {int(folga['naoexec'] - folga['limite_ne_total'])} OS além do limite",
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


def _render_alerts_chips(alerts: list[dict[str, Any]]) -> None:
    if not alerts:
        return
    cores = {
        "critico": ("#FEE2E2", "#991B1B", "#FCA5A5"),
        "alerta": ("#FEF3C7", "#92400E", "#FCD34D"),
        "acao": ("#DBEAFE", "#1E40AF", "#93C5FD"),
    }
    html = '<div style="display:flex;flex-wrap:wrap;margin:8px 0 16px 0">'
    for a in alerts:
        bg, txt, bd = cores.get(str(a["tipo"]), ("#F1F5F9", "#475569", "#E2E8F0"))
        html += f'<span class="alert-chip" style="background:{bg};color:{txt};border:1px solid {bd}">{a["icone"]} {escape(a["msg"])}</span>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


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


def _achar_coluna(df: pd.DataFrame, cands: list[str]) -> str | None:
    cols_norm = {_norm_txt(c): c for c in df.columns}
    for cand in cands:
        if _norm_txt(cand) in cols_norm:
            return cols_norm[_norm_txt(cand)]
    for cand in cands:
        for cn, cr in cols_norm.items():
            if _norm_txt(cand) in cn:
                return cr
    return None


def _build_df_pendentes(df_seg: pd.DataFrame) -> pd.DataFrame:
    cols_saida = list(_MAPA_PENDENTES.keys())
    if "Status Contrato" in df_seg.columns:
        mask = df_seg["Status Contrato"].astype(str).str.strip().str.upper().isin(STATUS_PENDENTE)
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


def _calcular_quebra_expurgada(
    df_seg: pd.DataFrame, m_seg: dict[str, Any], segmento: str
) -> dict[str, Any] | None:
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
def _token_parece_icone(token: str) -> bool:
    return any(0x2300 <= ord(c) <= 0x2BFF or 0x1F000 <= ord(c) <= 0x1FAFF for c in token)


def _render_subsecao(titulo: str) -> None:
    """Cabeçalho de subseção — delega a :func:`components.layout_pagina.cabecalho_secao`.

    Mantém o contrato local (emoji opcional no início do título) e não ancora:
    são subtítulos dentro das abas, e o sumário usa as âncoras de
    ``SECOES_PAGINA``.
    """
    texto = str(titulo or "").strip()
    if not texto:
        return
    partes = texto.split(maxsplit=1)
    icone_final, titulo_final = "", texto
    if len(partes) == 2 and _token_parece_icone(partes[0]):
        icone_final, titulo_final = partes[0], partes[1]
    cabecalho_secao(titulo_final, icone=icone_final, ancora=False)


def _sub_visao_geral(
    segmento: str,
    df_seg: pd.DataFrame,
    m_seg: dict[str, Any],
    p_ot: float,
    p_base: float,
    p_pess: float,
    sla_meta: float,
) -> None:
    _render_subsecao(f"📊 Resumo Operacional — {segmento}")
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
                hole=0.58,
                marker_colors=["#047857", "#B91C1C", "#94A3B8"],
            )
        )
        fig_pie.update_layout(
            height=280,
            margin=dict(t=20, b=10, l=10, r=10),
            showlegend=True,
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig_pie, width="stretch", config={"displayModeBar": False})
    with col_gauge:
        cor_bar = "#B91C1C" if m_seg["quebra_atual"] > sla_meta else "#047857"
        limite_eixo = max(50.0, sla_meta * 100 * 1.6, m_seg["quebra_atual"] * 100 * 1.2)
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number+delta",
                value=m_seg["quebra_atual"] * 100,
                delta={
                    "reference": sla_meta * 100,
                    "increasing": {"color": "#B91C1C"},
                    "decreasing": {"color": "#047857"},
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
                        "line": {"color": "#B91C1C", "width": 3},
                        "thickness": 0.85,
                        "value": sla_meta * 100,
                    },
                },
                title={"text": f"Quebra vs. Meta {sla_meta:.0%}", "font": {"size": 14}},
            )
        )
        fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    _render_subsecao("📈 Projeções de Fechamento")
    cen = {
        n: _obter_resumo_segmento(df_seg, p)
        for n, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]
    }
    c_cen, _ = st.columns([2, 1])
    with c_cen:
        cols = st.columns(3)
        for (nome, cd), col in zip(cen.items(), cols):
            cor_p: TemaKPIType = "vermelho" if cd["fechamento_proj"] > sla_meta else "verde"
            render_kpi_sm(
                col,
                nome,
                f"{cd['fechamento_proj']:.2%}",
                sub=f"NE proj.: {_fmt_int(cd['naoexec_proj'])}",
                tema=cor_p,
            )
    _render_subsecao("Folga de SLA")
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
        _render_subsecao("Simulação de Expurgo do Maior Ofensor")
        motivo_html = escape(sim["motivo"])
        dentro = sim["quebra_expurgada"] <= sla_meta
        bg_grad = (
            "linear-gradient(135deg,#ECFDF5 0%,#D1FAE5 100%)"
            if dentro
            else "linear-gradient(135deg,#FFFBEB 0%,#FEF3C7 100%)"
        )
        border_color = badge_bg = "#047857" if dentro else "#D97706"
        status_text = "DENTRO DA META SLA" if dentro else "AINDA FORA DA META SLA"
        call = (
            f"Atuar em <b>'{motivo_html}'</b> pode resolver o desvio."
            if dentro
            else f"Eliminar <b>'{motivo_html}'</b> ajuda, mas são necessárias ações complementares para atingir a meta de {sla_meta:.0%}."
        )
        st.markdown(
            f"""<div style="background:{bg_grad};border:1px solid {border_color};border-radius:14px;padding:20px 24px;margin:8px 0 20px"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px"><div><div style="font-size:11px;color:#64748B;font-weight:700">MAIOR OFENSORA</div><div style="font-size:16px;font-weight:700;margin-top:4px">{motivo_html} <span style="background:#FEE2E2;color:#991B1B;font-size:11px;padding:2px 8px;border-radius:4px">{_fmt_int(sim["volume"])} ocorrências</span></div></div><span style="background:{badge_bg};color:#FFF;font-size:10px;font-weight:700;padding:4px 12px;border-radius:999px">{status_text}</span></div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:14px"><div class="status-metric"><span class="status-metric__label">Quebra atual</span><span class="status-metric__value">{sim["quebra_atual"]:.2%}</span></div><div class="status-metric"><span class="status-metric__label">Quebra com expurgo</span><span class="status-metric__value">{sim["quebra_expurgada"]:.2%}</span></div><div class="status-metric"><span class="status-metric__label">Redução estimada</span><span class="status-metric__value">−{sim["impacto_abs"]:.2%}</span></div></div><div style="font-size:13px;color:#1E293B">{call}</div></div>""",
            unsafe_allow_html=True,
        )


def _sub_causa_raiz(segmento: str, df_seg: pd.DataFrame) -> None:
    _render_subsecao(f"Causa Raiz — {segmento}")
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
        colunas_num=[c for c in ["Volume", "% do Total", "Acumulado"] if c in df_c.columns],
        height=380,
    )
    conf = SEGMENTOS_CONFIG.get(segmento, {"cor_primaria": "#012869", "cor_secundaria": "#4E7FC4"})
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
        line=dict(color="#D97706", width=2, dash="dash"),
    )
    fig.add_annotation(
        xref="paper",
        x=1,
        yref="y2",
        y=0.8,
        text="80% Pareto",
        showarrow=False,
        xanchor="right",
        font=dict(color="#D97706", size=12),
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
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    if _COL_REGIAO in df_seg.columns and col_baixa:
        try:
            _render_subsecao("Quebra por Região")
            reg_rows = []
            for reg, grp in df_seg.groupby(_COL_REGIAO):
                val = _obter_resumo_segmento(grp, 0.2)["quebra_atual"]
                reg_rows.append({_COL_REGIAO: reg, "Quebra": val})
            reg_agg = pd.DataFrame(reg_rows)
            fig_reg = px.bar(
                reg_agg,
                x=_COL_REGIAO,
                y="Quebra",
                color="Quebra",
                color_continuous_scale="Reds",
            )
            fig_reg.update_layout(yaxis_tickformat=".1%", height=320)
            st.plotly_chart(fig_reg, width="stretch", config={"displayModeBar": False})
        except Exception:
            pass


def _sub_tecnicos(
    segmento: str,
    df_seg: pd.DataFrame,
    p_ot: float,
    p_base: float,
    p_pess: float,
    min_aloc: float,
    top_n: int,
    sla_meta: float,
) -> None:
    _render_subsecao(f"Técnicos com Maior Quebra — {segmento}")
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
        "Exportar técnicos",
        Utils.gerar_excel(df_tec, f"Tec_{segmento[:20]}"),
        f"tecnicos_{_slug(segmento)}.xlsx",
        key=f"dl_tec_{segmento}",
    )
    if {"TÉCNICO", "Fechamento Base"}.issubset(df_tec.columns):
        df_plot = df_tec.head(10).sort_values("Fechamento Base")
        cores = ["#B91C1C" if v > sla_meta else "#047857" for v in df_plot["Fechamento Base"]]
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
            line_color="#B91C1C",
            annotation_text=f"Meta {sla_meta:.0%}",
        )
        fig.update_layout(
            title="Quebra Projetada por Técnico",
            xaxis_tickformat=".1%",
            height=max(360, len(df_plot) * 42),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _sub_plano_acao(segmento: str, df_seg: pd.DataFrame, p_base: float, sla_meta: float) -> None:
    _render_subsecao(f"Plano de Ação — {segmento}")
    folga = _obter_folga_sla(df_seg, sla_meta)
    cen = _obter_resumo_segmento(df_seg, p_base)
    excesso = max(0.0, folga["naoexec"] - folga["limite_ne_total"])
    pend_exec = folga["precisa_executar_pendente"]
    col_d, col_a = st.columns([1, 1.5])
    with col_d:
        _render_subsecao("Diagnóstico")
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
            "Projeção Base",
            f"{cen['fechamento_proj']:.2%}",
            sub=f"com {p_base:.0%} de quebra pendente",
            tema="vermelho" if cen["fechamento_proj"] > sla_meta else "verde",
        )
    acoes = []
    if folga["estourado"]:
        acoes.append(
            (
                "IMEDIATA",
                f"Acionar plantão para recuperar {_fmt_int(excesso)} OS não executadas.",
                "alerta",
            )
        )
    if pend_exec > 0:
        acoes.append(
            (
                "ALTA",
                f"Garantir execução de {_fmt_int(np.ceil(pend_exec))} OS pendentes.",
                "alerta",
            )
        )
    acoes.extend(SEGMENTOS_CONFIG.get(segmento, {"acoes": []})["acoes"])
    with col_a:
        _render_subsecao("Ações Recomendadas")
        for pri, ac, tp in acoes:
            render_insight(f"**{pri}** — {ac}", tipo=cast(TipoInsightType, tp))
    df_plano = pd.DataFrame(
        [{"Segmento": segmento, "Prioridade": p, "Ação": a} for p, a, _ in acoes]
    )
    if not df_plano.empty:
        st.download_button(
            "Exportar plano",
            Utils.gerar_excel(df_plano, f"Plano_{segmento[:20]}"),
            f"plano_{_slug(segmento)}.xlsx",
            key=f"dl_plano_{segmento}",
        )


def _sub_pendentes(segmento: str, df_seg: pd.DataFrame) -> None:
    _render_subsecao(f"Contratos Pendentes — {segmento}")
    df_pend = _build_df_pendentes(df_seg)
    total = len(df_pend)

    def _nunique(col: str) -> int:
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

    def _opts(col: str) -> list[str]:
        return ["Todos"] + sorted(
            str(x) for x in df_pend[col].dropna().unique() if str(x) not in {"N/D", "nan"}
        )

    with st.expander("Filtros rápidos"):
        fc1, fc2 = st.columns(2)
        f_tec = fc1.selectbox("Técnico", _opts("Técnico"), key=f"pend_f_tec_{segmento}")
        f_mon = fc2.selectbox("Monitor", _opts("Monitor"), key=f"pend_f_mon_{segmento}")
    df_view = df_pend.copy()
    if f_tec != "Todos":
        df_view = df_view[df_view["Técnico"].astype(str) == f_tec]
    if f_mon != "Todos":
        df_view = df_view[df_view["Monitor"].astype(str) == f_mon]
    st.markdown(f"**Exibindo {_fmt_int(len(df_view))} de {_fmt_int(total)} registros**")
    render_table_html(df_view.reset_index(drop=True), height=480)
    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button(
        "Exportar filtrado",
        Utils.gerar_excel(df_view, "Filtrado"),
        f"pendentes_{_slug(segmento)}_filtrado.xlsx",
        key=f"dl_pend_f_{segmento}",
        width="stretch",
    )
    c2.download_button(
        "Exportar completo",
        Utils.gerar_excel(df_pend, "Completo"),
        f"pendentes_{_slug(segmento)}_completo.xlsx",
        key=f"dl_pend_c_{segmento}",
        width="stretch",
    )


def _sub_sem_registro(segmento: str, df_seg: pd.DataFrame) -> None:
    _render_subsecao(f"Motivo de Baixa: Sem Registro — {segmento}")
    col_baixa = _resolver_col_baixa(df_seg)
    if not col_baixa:
        render_insight("Coluna de baixa não encontrada.", tipo="alerta")
        return
    serie = df_seg[col_baixa].fillna("").astype(str).str.strip().str.upper()
    mask_baixa = serie.isin(["SEM REGISTRO", "SEM_REGISTRO", "", "NAN", "NONE"])
    if "Status Contrato" in df_seg.columns:
        status_serie = df_seg["Status Contrato"].fillna("").astype(str).str.strip().str.upper()
        mask = mask_baixa & ~status_serie.isin(STATUS_PENDENTE)
    else:
        mask = mask_baixa
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
        "Exportar sem registro",
        Utils.gerar_excel(df_view, "Sem_Registro"),
        f"sem_registro_{_slug(segmento)}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        key=f"dl_sr_{segmento}",
        width="stretch",
    )


def _sub_comparativo(
    df_full: pd.DataFrame, sla_meta: float, p_base: float, p_ot: float, p_pess: float
) -> None:
    _render_subsecao("Comparativo entre Segmentos")
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
    c1, c2, c3 = st.columns(3)
    for i, (_, row) in enumerate(df_comp.iterrows()):
        col_target = [c1, c2, c3][i % 3]
        tema: TemaKPIType = "vermelho" if row["Quebra Atual"] > sla_meta else "verde"
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
            marker_color="#2563EB",
        )
    )
    fig.add_hline(
        y=sla_meta,
        line_dash="dash",
        line_color="#B91C1C",
        annotation_text=f"Meta {sla_meta:.0%}",
    )
    fig.update_layout(barmode="group", yaxis_tickformat=".1%", height=380)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
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
        _render_subsecao("Quebra por Região e Segmento")
        try:
            heat_rows = []
            for (tipo_ser, reg), grp in df_full.groupby(["TIPO_SERVICO", _COL_REGIAO]):
                val = _obter_resumo_segmento(grp, p_base)["quebra_atual"]
                heat_rows.append({"TIPO_SERVICO": tipo_ser, _COL_REGIAO: reg, "Quebra": val})
            heat = pd.DataFrame(heat_rows)
            fig_h = px.density_heatmap(
                heat,
                x=_COL_REGIAO,
                y="TIPO_SERVICO",
                z="Quebra",
                color_continuous_scale="Reds",
                histfunc="avg",
            )
            fig_h.update_layout(height=320)
            st.plotly_chart(fig_h, width="stretch", config={"displayModeBar": False})
        except Exception:
            pass


def _processar_saida_robo_global() -> None:
    """Reutiliza o ETL comum de Quebra quando esta página é a primeira aberta."""
    if DataLoader is None or not callable(_aplicar_etl_robo_global):
        return
    if not str(st.session_state.get("origem_dados", "")).startswith("Robô Local"):
        return

    bruto = st.session_state.get("df_memoria_raw")
    if not isinstance(bruto, pd.DataFrame) or bruto.empty:
        return

    ativos = st.session_state.get("df_gs_manual")
    if not isinstance(ativos, pd.DataFrame) or ativos.empty:
        try:
            ativos = DataLoader.buscar_gsheets()
        except Exception:
            ativos = pd.DataFrame()
    if not isinstance(ativos, pd.DataFrame):
        ativos = pd.DataFrame()

    _aplicar_etl_robo_global(ativos)


# =====================================================================
# FLUXO PRINCIPAL
# =====================================================================
def main() -> None:
    _processar_saida_robo_global()
    df_original = obter_dataframe(CHAVE_MEMORIA)
    if not isinstance(df_original, pd.DataFrame) or df_original.empty:
        render_insight(
            "Nenhuma base carregada. Volte à página 'Dashboard Geral' e envie os dados do Excel.",
            tipo="alerta",
            titulo="Sem base carregada",
        )
        fechar_dashboard()
        return
    df_full = _preparar_base(df_original.copy())
    df_full.attrs = dict(getattr(df_original, "attrs", {}))

    with st.sidebar:
        st.markdown("### Escolha a Carteira")
        opcoes = list(SEGMENTOS_CONFIG.keys()) + ["Todos os Segmentos"]
        segmento = st.selectbox("Segmento", opcoes, index=0, key="sel_segmento_principal")
        conf = SEGMENTOS_CONFIG.get(segmento, {"sla_default": 0.20, "p_base_default": 20})
        st.divider()
        st.header(f"Filtros — {segmento}")
        monitores = _opcoes_filtro(df_full, "MONITOR", {"nan", "SEM MONITOR", "NÃO MAPEADO"})
        sel_mon = st.selectbox("Monitor", monitores, key=f"mon_{segmento}")
        df_filt = (
            df_full
            if sel_mon == "Todos" or "MONITOR" not in df_full.columns
            else df_full[df_full["MONITOR"].astype(str) == sel_mon]
        )
        df_filt.attrs = dict(getattr(df_full, "attrs", {}))
        tecnicos = _opcoes_filtro(df_filt, "TÉCNICO", {"nan", "NÃO MAPEADO"})
        sel_tec = st.selectbox("Técnico", tecnicos, key=f"tec_{segmento}")
        df = (
            df_filt
            if sel_tec == "Todos" or "TÉCNICO" not in df_filt.columns
            else df_filt[df_filt["TÉCNICO"].astype(str) == sel_tec]
        )
        df.attrs = dict(getattr(df_filt, "attrs", {}))
        st.divider()
        st.subheader("Probabilidades")
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
        p_pess = st.slider("Pessimista (%)", 0, 100, 50, 5, key=f"ppess_{segmento}") / 100.0
        if not (p_ot <= p_base <= p_pess):
            st.warning("Ajuste recomendado: Otimista ≤ Base ≤ Pessimista")

        valores_padrao = {
            f"sla_v_{segmento}": float(conf["sla_default"] * 100),
            f"minaloc_{segmento}": 1,
            f"topn_{segmento}": 50,
        }
        for chave, valor_padrao in valores_padrao.items():
            if chave not in st.session_state or st.session_state[chave] is None:
                st.session_state[chave] = valor_padrao

        st.divider()
        sla_meta = (
            st.number_input(
                "Meta SLA (%)",
                0.0,
                100.0,
                value=float(st.session_state[f"sla_v_{segmento}"] or 0.0),
                step=0.5,
                key=f"sla_v_{segmento}",
            )
            / 100.0
        )
        min_aloc = float(
            st.number_input(
                "Mínimo de OS por técnico",
                min_value=1,
                max_value=500,
                value=st.session_state[f"minaloc_{segmento}"],
                step=1,
                key=f"minaloc_{segmento}",
            )
        )
        top_n = int(
            st.number_input(
                "Quantidade de técnicos",
                min_value=5,
                max_value=1000,
                value=st.session_state[f"topn_{segmento}"],
                step=5,
                key=f"topn_{segmento}",
            )
        )
        st.divider()
        with st.expander("Sistema", expanded=False):
            if st.button("Reiniciar", width="stretch"):
                st.rerun()
            if st.button("Limpar cache", width="stretch"):
                if DataLoader is not None:
                    DataLoader.ler_arquivo.clear()
                    DataLoader.buscar_gsheets.clear()
                if _cache_matriz is not None and hasattr(_cache_matriz, "clear"):
                    _cache_matriz.clear()
                st.success("Cache limpo.")
                st.rerun()
        st.divider()
        render_debug_criterios(df_full, expanded=False)

    if df.empty:
        render_insight(
            "Nenhum dado encontrado para os filtros e segmentação selecionados.",
            tipo="alerta",
        )
        return
    regioes = (
        [str(r).strip().upper() for r in df[_COL_REGIAO].dropna().unique() if str(r).strip()]
        if _COL_REGIAO in df.columns
        else ["OUTRAS"]
    )

    # 1) Cabeçalho e contexto — padrão do portal (hero do segmento + chips + sumário)
    conf_hero = SEGMENTOS_CONFIG.get(str(segmento), {})
    aplicar_css_cartao_segmento(str(conf_hero.get("cor_primaria", "#012869")))
    abrir_dashboard(
        "Quebra por Segmento",
        secoes=SECOES_PAGINA,
        hero=render_hero_segmento,
        hero_kwargs={
            "segmento": str(segmento),
            "regioes": regioes,
            "total": len(df),
        },
        chips={
            "Segmento": str(segmento),
            "Regiões": len(regioes),
        },
        origem=str(st.session_state.get("origem_dados", "Base carregada")),
        registros=len(df),
    )

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
                "Gerar PDF comparativo",
                key="gen_pdf_todos",
                type="primary",
                width="stretch",
            ):
                with st.spinner("Gerando PDF comparativo..."):
                    try:
                        st.session_state[key_pdf] = PDFExecutivoComparativo.gerar(
                            df_seg, sla_meta, p_ot, p_base, p_pess, min_aloc, top_n
                        )
                    except Exception as e:
                        st.error(f"Falha ao gerar PDF: {e}")
        with c2:
            if key_pdf in st.session_state:
                st.download_button(
                    "Baixar PDF",
                    st.session_state[key_pdf],
                    f"comparativo_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    "application/pdf",
                    key="dl_pdf_todos",
                    width="stretch",
                )
        st.divider()
        cabecalho_secao(
            "Visões do consolidado",
            icone="hub",
            subtitulo="Comparativo entre Novos Domicílios, Migração e PME.",
        )
        t1, t2, t3, t4, t5 = st.tabs(
            ["Comparativo", "Causas de quebra", "Técnicos", "Pendentes", "Sem registro"]
        )
        with t1:
            _sub_comparativo(df, sla_meta, p_base, p_ot, p_pess)
            _sub_visao_geral("Consolidado Geral", df_seg, m_seg, p_ot, p_base, p_pess, sla_meta)
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

        # Exportação e rodapé no padrão do portal (última seção ancorada).
        secao_exportacao(
            df_seg,
            nome_arquivo="quebra_todos_segmentos",
            chave="quebra_unificada_todos",
            titulo="Exportação",
            subtitulo="Consolidado de todos os segmentos com as projeções aplicadas.",
        )
        fechar_dashboard()
        return

    df_seg = (
        df[df["TIPO_SERVICO"] == segmento].copy() if "TIPO_SERVICO" in df.columns else df.copy()
    )
    df_seg.attrs = dict(getattr(df, "attrs", {}))
    if df_seg.empty:
        render_insight(f"Nenhum registro encontrado para o segmento {segmento}.", tipo="info")
        return
    m_seg = _obter_resumo_segmento(df_seg, p_base)
    folga = _obter_folga_sla(df_seg, sla_meta)
    _render_card_status(str(segmento), m_seg, sla_meta)
    _render_alerts_chips(_gerar_alertas(df_seg, m_seg, sla_meta, folga))
    h = _hash_df(df_seg)
    key_pdf = f"pdf_bytes_{_slug(str(segmento))}_{h}_{sla_meta}_{p_base}_{p_ot}_{p_pess}_{min_aloc}_{top_n}"
    col_btn, col_dl, col_desc = st.columns([1, 1, 2])
    with col_btn:
        if st.button(
            f"Gerar PDF — {segmento}",
            key=f"gen_pdf_{segmento}",
            type="primary",
            width="stretch",
        ):
            with st.spinner("Gerando PDF..."):
                try:
                    st.session_state[key_pdf] = SEGMENTOS_CONFIG[str(segmento)]["pdf_class"].gerar(
                        df_seg, sla_meta, p_ot, p_base, p_pess, min_aloc, top_n
                    )
                except Exception as e:
                    st.error(f"Falha ao gerar PDF: {e}")
    with col_dl:
        if key_pdf in st.session_state:
            st.download_button(
                "Baixar PDF",
                st.session_state[key_pdf],
                f"relatorio_{_slug(str(segmento))}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                "application/pdf",
                key=f"dl_pdf_{segmento}",
                width="stretch",
            )
    with col_desc:
        render_insight(
            "O PDF executivo inclui cenários, curva de Pareto e técnicos críticos.",
            tipo="info",
        )
    st.divider()
    cabecalho_secao(
        "Visões do segmento",
        icone="monitoring",
        subtitulo=f"Carteira {segmento} — do resumo operacional ao plano de ação.",
    )
    sub1, sub2, sub3, sub4, sub5, sub6 = st.tabs(
        [
            "Visão geral",
            "Causa raiz",
            "Técnicos",
            "Plano de ação",
            "Pendentes",
            "Sem registro",
        ]
    )
    with sub1:
        _sub_visao_geral(str(segmento), df_seg, m_seg, p_ot, p_base, p_pess, sla_meta)
    with sub2:
        _sub_causa_raiz(str(segmento), df_seg)
    with sub3:
        _sub_tecnicos(str(segmento), df_seg, p_ot, p_base, p_pess, min_aloc, top_n, sla_meta)
    with sub4:
        _sub_plano_acao(str(segmento), df_seg, p_base, sla_meta)
    with sub5:
        _sub_pendentes(str(segmento), df_seg)
    with sub6:
        _sub_sem_registro(str(segmento), df_seg)

    # Exportação e rodapé no padrão do portal (última seção ancorada).
    secao_exportacao(
        df_seg,
        nome_arquivo=f"quebra_segmento_{_slug(str(segmento))}",
        chave=f"quebra_unificada_{_slug(str(segmento))}",
        titulo="Exportação",
        subtitulo=(
            f"Recorte do segmento {segmento} já com as colunas de classificação "
            "e projeção aplicadas."
        ),
    )
    fechar_dashboard()


if __name__ == "__main__":
    main()
