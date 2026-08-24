"""
quebra_unificada.py
===================
Análise de Quebra por Segmento (Migração / PME)

Critérios centralizados em: components.criterios
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Adiciona pages/ ao sys.path ───────────────────────────────────────
_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

_ROOT = _DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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

from components.componentes import (
    aplicar_estilo as _aplicar_estilo_global,
    render_kpi,
    render_kpi_sm,
    render_insight,
    TemaKPI,
    TipoInsight,
)
from old.quebra import (
    Config,
    Motor,
    Utils,
    aplicar_estilo,
    render_dataframe,
    render_section,
)

# ═══════════════════════════════════════════════════════
# ✅ IMPORT CENTRALIZADO DE CRITÉRIOS
# ═══════════════════════════════════════════════════════
from components.criterios import (
    # Classificação principal
    classificar_tipo_servico,
    # UI centralizada
    render_debug_criterios,
)

# =====================================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================================
st.set_page_config(
    page_title="Análise de Quebra | TOTALE",
    page_icon="📊",
    layout="wide",
)
_aplicar_estilo_global()
aplicar_estilo()

if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None


# =====================================================================
# PDF EXECUTIVO — BASE COMPARTILHADA
# =====================================================================
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
                    [["Sem dados disponíveis"]],
                    colWidths=[cls.LARGURA_UTIL * cm],
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
                            bg_c = colors.HexColor("#FEE2E2")
                            tx_c = colors.HexColor(cls.COR_CRITICO)
                        elif val > sla_meta * 0.85:
                            bg_c = colors.HexColor("#FEF9C3")
                            tx_c = colors.HexColor(cls.COR_ALERTA)
                        else:
                            bg_c = colors.HexColor("#DCFCE7")
                            tx_c = colors.HexColor(cls.COR_OK)
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
        canvas.line(
            cls.MARGEM_H * cm,
            1.05 * cm,
            page_w - cls.MARGEM_H * cm,
            1.05 * cm,
        )
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor(cls.COR_SUBTEXTO))
        canvas.drawString(
            cls.MARGEM_H * cm,
            0.52 * cm,
            f"{cls.NOME_SEGMENTO} — Gestão de Quebra de Agenda  |  "
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Confidencial",
        )
        canvas.drawRightString(
            page_w - cls.MARGEM_H * cm,
            0.52 * cm,
            f"Página {doc.page}",
        )
        canvas.restoreState()


# =====================================================================
# PDF EXECUTIVO MIGRAÇÃO
# =====================================================================
class PDFExecutivoMigracao(_PDFExecutivoBase):
    COR_PRIMARIA: str = "#0C4A6E"
    COR_SECUNDARIA: str = "#0369A1"
    COR_TEXTO: str = "#0F172A"
    COR_LINHA_ALT: str = "#F0F9FF"
    NOME_SEGMENTO: str = "Migração"

    @classmethod
    def _estilos(cls) -> Any:
        s = getSampleStyleSheet()
        defs = [
            (
                "MIG_Titulo",
                {
                    "fontName": "Helvetica-Bold",
                    "fontSize": 22,
                    "leading": 28,
                    "textColor": colors.white,
                    "alignment": TA_CENTER,
                    "spaceAfter": 2,
                },
            ),
            (
                "MIG_Subtitulo",
                {
                    "fontName": "Helvetica",
                    "fontSize": 9,
                    "leading": 13,
                    "textColor": colors.HexColor("#BAE6FD"),
                    "alignment": TA_CENTER,
                    "spaceAfter": 0,
                },
            ),
            (
                "MIG_Secao",
                {
                    "fontName": "Helvetica-Bold",
                    "fontSize": 11,
                    "leading": 15,
                    "textColor": colors.HexColor(cls.COR_PRIMARIA),
                    "spaceBefore": 8,
                    "spaceAfter": 4,
                    "alignment": TA_LEFT,
                },
            ),
        ]
        for nome, props in defs:
            s.add(ParagraphStyle(name=nome, parent=s["Normal"], **props))
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
                f"Mudança de Pacote + FLAG_GPON = Sim • "
                f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
                s["MIG_Subtitulo"],
            )
        )
        el.append(Spacer(1, 1 * cm))

        # ── 1. Cenários ────────────────────────────────────────────────
        el.append(Paragraph("1 ─ Cenários de Fechamento", s["MIG_Secao"]))
        cenarios = []
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            proj = Motor.projetar(df, p)
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
                cor_col_quebra="Fechamento Proj.",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.5 * cm))

        # ── 2. Técnicos ────────────────────────────────────────────────
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

        # ── 3. Causas ──────────────────────────────────────────────────
        el.append(Paragraph("3 ─ Principais Causas de Quebra", s["MIG_Secao"]))
        df_causa = Motor.causa_raiz_segmento(df, "Migração", "_COL_BAIXA", top_n=8)
        el.append(cls._tab(df_causa, limite=8))

        doc.build(el, onFirstPage=cls._rodape, onLaterPages=cls._rodape)
        buf.seek(0)
        return buf.getvalue()


# =====================================================================
# PDF EXECUTIVO PME
# =====================================================================
class PDFExecutivoPME(_PDFExecutivoBase):
    COR_PRIMARIA: str = "#4C1D95"
    COR_SECUNDARIA: str = "#7C3AED"
    COR_TEXTO: str = "#1E1B4B"
    COR_LINHA_ALT: str = "#F9FAFB"
    NOME_SEGMENTO: str = "PME"

    @classmethod
    def _estilos(cls) -> Any:
        s = getSampleStyleSheet()
        s.add(
            ParagraphStyle(
                name="PME_Titulo",
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
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=15,
                textColor=colors.HexColor(cls.COR_PRIMARIA),
                spaceBefore=10,
                spaceAfter=4,
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
                f"Pequenas e Médias Empresas • "
                f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
                s["PME_Subtitulo"],
            )
        )
        el.append(Spacer(1, 1 * cm))

        # ── 1. Cenários ────────────────────────────────────────────────
        el.append(Paragraph("1. Cenários de Fechamento", s["PME_Secao"]))
        cenarios = []
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            proj = Motor.projetar(df, p)
            cenarios.append(
                {
                    "Cenário": nome,
                    "Probab. Pend.": p,
                    "Fechamento": proj["fechamento_proj"],
                    "Não Exec. Proj.": proj["naoexec_proj"],
                    "vs Meta": proj["fechamento_proj"] - sla_meta,
                }
            )
        el.append(
            cls._tab(
                pd.DataFrame(cenarios),
                larguras=[4.5, 4.5, 5.5, 5.5, 5.0],
                cor_col_quebra="Fechamento",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.5 * cm))

        # ── 2. Técnicos ────────────────────────────────────────────────
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

        # ── 3. Causas ──────────────────────────────────────────────────
        el.append(Paragraph("3. Principais Causas de Quebra (Pareto)", s["PME_Secao"]))
        df_causa = Motor.causa_raiz_segmento(df, "PME", "_COL_BAIXA", top_n=8)
        el.append(cls._tab(df_causa, limite=8, larguras=[9.0, 4.5, 4.5, 4.5]))

        doc.build(el, onFirstPage=cls._rodape, onLaterPages=cls._rodape)
        buf.seek(0)
        return buf.getvalue()


# =====================================================================
# CONFIGURAÇÕES DINÂMICAS POR SEGMENTO
# =====================================================================
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


# =====================================================================
# COMPONENTES VISUAIS
# =====================================================================
def _injetar_css_dinamico(segmento: str) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    st.markdown(
        f"""
<style>
div[data-testid="stElementContainer"]:has(.topo-fixo-dinamico) {{
    position: sticky !important; top: 0.75rem !important; z-index: 1000 !important;
}}
.topo-fixo-dinamico {{
    background: rgba(248,250,252,0.96); backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px); padding: 0.5rem 0; border-radius: 16px;
}}
.hero-dinamico {{
    background: {conf["grad_hero"]}; padding: 32px 40px; border-radius: 16px;
    color: white; box-shadow: 0 10px 40px {conf["sombra_hero"]};
    margin-bottom: 12px; position: relative; overflow: hidden;
}}
.hero-dinamico::before {{
    content: ""; position: absolute; top: -55%; right: -8%;
    width: 390px; height: 390px; background: rgba(255,255,255,0.07);
    border-radius: 50%; pointer-events: none;
}}
.hero-dinamico h1 {{
    position: relative; z-index: 2; color: white !important;
    font-family: "Manrope", sans-serif !important;
    font-size: 34px; font-weight: 800; margin: 0; letter-spacing: -0.5px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.28);
}}
.hero-dinamico p {{
    position: relative; z-index: 2; color: rgba(255,255,255,0.92) !important;
    font-family: "Inter", sans-serif !important; font-size: 15px;
    margin: 8px 0 0; font-weight: 400;
}}
.resultado-base {{
    margin-bottom: 0 !important;
    background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
    padding: 1rem 1.5rem; border-radius: 0.75rem; display: flex;
    align-items: center; flex-wrap: wrap; gap: 0.6rem;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}}
.resultado-base-label {{
    color: #94A3B8; font-size: 0.8rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
}}
.resultado-base-regiao {{
    padding: 0.3rem 0.9rem; border-radius: 999px;
    font-size: 0.82rem; font-weight: 700; border: 2px solid;
}}
.resultado-base-count {{
    color: #64748B; font-size: 0.72rem; margin-left: auto; font-weight: 600;
}}
</style>""",
        unsafe_allow_html=True,
    )


def _html_resultado_base(regioes: List[str], total: int) -> str:
    cores_regiao = {
        "LESTE": {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
        "GRU": {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
        "ABCDM": {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
        "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
    }
    badges = ""
    for regiao in sorted(regioes):
        r = str(regiao).strip().upper()
        if not r or r in {"NAN", "NONE"}:
            continue
        cor = cores_regiao.get(r, cores_regiao["OUTRAS"])
        badges += (
            f'<span class="resultado-base-regiao" '
            f'style="background:{cor["bg"]};color:{cor["text"]};'
            f'border-color:{cor["border"]};">{escape(r)}</span>'
        )
    if not badges:
        cor = cores_regiao["OUTRAS"]
        badges = (
            f'<span class="resultado-base-regiao" '
            f'style="background:{cor["bg"]};color:{cor["text"]};'
            f'border-color:{cor["border"]};">OUTRAS</span>'
        )
    return (
        f'<div class="resultado-base">'
        f'<span class="resultado-base-label">📋 Resultado da Base:</span>'
        f"{badges}"
        f'<span class="resultado-base-count">{total:,} registros</span>'
        f"</div>"
    ).replace(",", ".")


def _render_topo_fixo(segmento: str, regioes: List[str], total: int) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    st.markdown(
        f"""
<div class="topo-fixo-dinamico">
    <div class="hero-dinamico">
        <h1>{conf["icone"]} {segmento} — Quebra de Agenda</h1>
        <p>{conf["subtitulo"]}</p>
    </div>
    {_html_resultado_base(regioes, total)}
</div>""",
        unsafe_allow_html=True,
    )


def _render_card_status(
    segmento: str,
    m_seg: Dict[str, Any],
    sla_meta: float,
) -> None:
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

    html = f"""
<div style="background:white;border:1px solid #E5E7EB;border-radius:14px;
            padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.04);
            margin:16px 0 24px 0;border-top:3px solid {conf['cor_primaria']};">
    <div style="display:flex;align-items:center;justify-content:space-between;
                flex-wrap:wrap;gap:16px;">
        <div style="display:flex;align-items:center;gap:14px;">
            <div style="width:44px;height:44px;background:{conf['grad_hero']};
                        border-radius:10px;display:flex;align-items:center;
                        justify-content:center;
                        box-shadow:0 4px 12px {conf['sombra_hero']};">
                <span style="font-size:22px;">{conf['icone']}</span>
            </div>
            <div>
                <div style="font-family:'Manrope',sans-serif;font-size:18px;
                            font-weight:800;color:#1F2937;">{segmento}</div>
                <div style="font-family:'Inter',sans-serif;font-size:12px;
                            color:#6B7280;font-weight:500;">Análise de Quebra</div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
            <div style="display:inline-flex;align-items:center;gap:6px;
                        padding:6px 14px;background:{cor_bg};
                        border-radius:999px;border:1px solid {cor_status};">
                <span style="display:inline-flex;align-items:center;
                             justify-content:center;width:18px;height:18px;
                             background:{cor_status};color:white;border-radius:50%;
                             font-size:11px;font-weight:800;">{status_icone}</span>
                <span style="font-family:'Inter',sans-serif;font-size:11px;
                             font-weight:700;color:{cor_txt};
                             text-transform:uppercase;">{status_label}</span>
            </div>
            <div style="display:inline-flex;flex-direction:column;padding:6px 14px;
                        background:#F0F9FF;border-radius:8px;border:1px solid #BAE6FD;">
                <span style="font-size:10px;color:#6B7280;font-weight:600;
                             text-transform:uppercase;">Quebra Atual</span>
                <span style="font-family:'Manrope',sans-serif;font-size:16px;
                             color:{cor_status};font-weight:800;">{quebra_atual:.2%}</span>
            </div>
            <div style="display:inline-flex;flex-direction:column;padding:6px 14px;
                        background:#F0F9FF;border-radius:8px;border:1px solid #BAE6FD;">
                <span style="font-size:10px;color:#6B7280;font-weight:600;
                             text-transform:uppercase;">Meta SLA</span>
                <span style="font-family:'Manrope',sans-serif;font-size:16px;
                             color:{conf['cor_secundaria']};
                             font-weight:800;">{sla_meta:.2%}</span>
            </div>
        </div>
    </div>
    <div style="margin:16px 0 12px 0;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;
                    font-size:11px;color:#6B7280;font-weight:600;">
            <span>0%</span><span>Meta {sla_meta:.2%}</span>
            <span>{sla_meta*2:.0%}</span>
        </div>
        <div style="position:relative;height:8px;background:#E5E7EB;
                    border-radius:4px;overflow:hidden;">
            <div style="position:absolute;left:50%;top:0;width:2px;height:100%;
                        background:#374151;z-index:2;"></div>
            <div style="width:{pct_barra}%;height:100%;
                        background:linear-gradient(90deg,{cor_status} 0%,
                        {cor_status}CC 100%);border-radius:4px;"></div>
        </div>
    </div>
    <div style="display:flex;align-items:flex-start;gap:10px;padding:12px 14px;
                background:{cor_bg};border-left:3px solid {cor_status};
                border-radius:6px;">
        <span style="font-size:16px;line-height:1;flex-shrink:0;">{icone_mensagem}</span>
        <div style="font-family:'Inter',sans-serif;font-size:13px;color:{cor_txt};
                    line-height:1.55;font-weight:500;">{mensagem}</div>
    </div>
</div>"""
    st.markdown(html.replace(".", ","), unsafe_allow_html=True)


# =====================================================================
# UTILITÁRIO — DataFrame de Pendentes
# =====================================================================
def _build_df_pendentes(df_seg: pd.DataFrame) -> pd.DataFrame:
    MAPA = {
        "Contrato":   [
            "CONTRATO", "Nº CONTRATO", "NUM_CONTRATO",
            "NUMERO CONTRATO", "NÚMERO CONTRATO",
            "CONTRATO_ID", "COD_CONTRATO", "CÓDIGO CONTRATO",
        ],
        "Login":      [
            "LOGIN DO TÉCNICO", "LOGIN DO TECNICO",
            "LOGIN_DO_TECNICO", "LOGIN_TECNICO",
            "LOGIN TÉCNICO", "LOGIN TECNICO",
            "LOGIN", "USER", "USUÁRIO", "USUARIO",
            "USERNAME", "MATRÍCULA", "MATRICULA",
        ],
        "Técnico":    [
            "TÉCNICO", "TECNICO", "NOME TÉCNICO",
            "NOME_TECNICO", "NOME DO TÉCNICO",
        ],
        "Monitor":    [
            "MONITOR", "SUPERVISOR", "NOME MONITOR", "NOME_MONITOR",
        ],
        "Qtde. O.S.": ["TOTAL DE TAREFAS"],
    }

    def _achar(df: pd.DataFrame, cands: List[str]) -> Optional[str]:
        def _norm(s: str) -> str:
            import unicodedata
            return (
                unicodedata.normalize("NFKD", str(s))
                .encode("ascii", errors="ignore")
                .decode("ascii")
                .upper()
                .strip()
                .replace("_", " ")
                .replace(".", "")
            )

        cols_norm = {_norm(c): c for c in df.columns}

        # 1) Match exato normalizado
        for cand in cands:
            cn = _norm(cand)
            if cn in cols_norm:
                return cols_norm[cn]

        # 2) Match parcial (contém)
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


# =====================================================================
# SUB-ABAS
# =====================================================================
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
    render_kpi(c1, "Alocado", f"{int(m_seg['alocado']):,}", tema="azul")
    render_kpi(c2, "Executadas", f"{int(m_seg['exec']):,}", tema="verde")
    render_kpi(c3, "Não Exec.", f"{int(m_seg['naoexec']):,}", tema="laranja")
    render_kpi(c4, "Pendentes", f"{int(m_seg['pend']):,}", tema="cinza")
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


def _sub_causa_raiz(segmento: str, df_seg: pd.DataFrame) -> None:
    render_section(f"🔍 Causa Raiz — {segmento}")
    df_c = Motor.causa_raiz_segmento(df_seg, segmento, "_COL_BAIXA", top_n=8)
    if df_c.empty:
        render_insight(
            "Coluna de código/motivo de baixa não identificada.", tipo="alerta"
        )
        return

    c_tab, c_chart = st.columns([1.2, 2])
    with c_tab:
        render_dataframe(
            df_c,
            titulo=f"Top Motivos — {segmento}",
            icone="🔍",
            fmt={"% do Total": "{:.2%}", "Acumulado": "{:.2%}"},
            height=350,
        )
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
            f"Os 2 principais motivos (**{t1['Motivo de Baixa']}** e "
            f"**{t2['Motivo de Baixa']}**) respondem por "
            f"**{t2['Acumulado']:.1%}** das quebras.",
            tipo="acao",
        )


def _sub_tecnicos(
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

    render_dataframe(
        df_tec,
        titulo=f"Técnicos Críticos — {segmento}",
        icone="🚨",
        fmt={
            "Quebra Atual": "{:.2%}",
            "Fechamento Otimista": "{:.2%}",
            "Fechamento Base": "{:.2%}",
            "Fechamento Pessimista": "{:.2%}",
        },
        color_col="Fechamento Base",
        color_meta=sla_meta,
        color_invertido=True,
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
                    f"Garantir execução de {int(np.ceil(pend_exec)):,} OS pendentes "
                    "para atingir meta.",
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
    render_dataframe(
        df_view.reset_index(drop=True), titulo="Pendentes", icone="📋", height=480
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


# =====================================================================
# PONTO DE ENTRADA PRINCIPAL
# =====================================================================
def main() -> None:
    if st.session_state.get("df_memoria") is None:
        render_insight(
            "Nenhuma base carregada. Volte ao **Dashboard Geral** e faça o upload.",
            tipo="alerta",
        )
        return

    df_full = st.session_state["df_memoria"].copy()

    # ── Status Contrato ────────────────────────────────────────────────
    if "Status Contrato" not in df_full.columns:
        col_s = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1"])
        df_full["Status Contrato"] = (
            Utils.classificar_status(df_full[col_s]) if col_s else "Pendente"
        )

    # ── ✅ Classificação centralizada ─────────────────────────────────
    # (Migração = MUDANCA DE PACOTE + FLAG_GPON auto-gerada)
    df_full, df_full["TIPO_SERVICO"] = classificar_tipo_servico(df_full)

    # ── Sidebar ────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🔍 Escolha a Carteira")
        segmento_selecionado = st.radio(
            "Segmento:",
            ["Migração", "PME"],
            index=0,
            horizontal=True,
        )
        st.divider()
        st.header(f"🎯 Filtros {segmento_selecionado}")

        monitores = ["Todos"] + sorted(
            str(x)
            for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon = st.selectbox(
            "👔 Monitor", monitores, key=f"mon_{segmento_selecionado}"
        )
        df_filt = (
            df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]
        )

        tecnicos = ["Todos"] + sorted(
            str(x)
            for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        )
        sel_tec = st.selectbox(
            "👤 Técnico", tecnicos, key=f"tec_{segmento_selecionado}"
        )
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.divider()
        st.subheader("🔮 Probabilidades")
        p_ot = (
            st.slider(
                "Otimista (%)",
                0,
                100,
                15,
                5,
                key=f"pot_{segmento_selecionado}",
            )
            / 100.0
        )
        p_base = (
            st.slider(
                "Base (%)",
                0,
                100,
                20 if segmento_selecionado == "PME" else 25,
                5,
                key=f"pbase_{segmento_selecionado}",
            )
            / 100.0
        )
        p_pess = (
            st.slider(
                "Pessimista (%)",
                0,
                100,
                50,
                5,
                key=f"ppess_{segmento_selecionado}",
            )
            / 100.0
        )

        st.divider()
        padrao_sla = float(SEGMENTOS_CONFIG[segmento_selecionado]["sla_default"] * 100)
        sla_meta = (
            st.number_input(
                "Meta SLA (%)",
                0.0,
                100.0,
                padrao_sla,
                0.5,
                key=f"sla_v_{segmento_selecionado}",
            )
            / 100.0
        )
        min_aloc = 1.0
        top_n = 999_999

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
        # ✅ Debug centralizado
        render_debug_criterios(df_full, expanded=False)

    if df.empty:
        render_insight("Nenhum dado para os filtros selecionados.", tipo="alerta")
        return

    # ── CSS dinâmico ───────────────────────────────────────────────────
    _injetar_css_dinamico(segmento_selecionado)

    regioes = (
        [
            str(r).strip().upper()
            for r in df[Config.COL_REGIAO].dropna().unique()
            if str(r).strip()
        ]
        if Config.COL_REGIAO in df.columns
        else ["OUTRAS"]
    )
    _render_topo_fixo(segmento_selecionado, regioes, len(df))

    # ── Filtra pelo segmento selecionado ──────────────────────────────
    df_seg = df[df["TIPO_SERVICO"] == segmento_selecionado].copy()
    if df_seg.empty:
        render_insight(
            f"Nenhum registro classificado como **{segmento_selecionado}** "
            "nos filtros atuais.  \n"
            "Verifique o expander **🔎 Critérios de Classificação** na sidebar.",
            tipo="info",
        )
        return

    m_seg = Motor.projetar(df_seg, p_base)
    _render_card_status(segmento_selecionado, m_seg, sla_meta)
    st.markdown("")

    # ── Geração e download do PDF ──────────────────────────────────────
    col_btn, col_desc = st.columns([1, 3])
    with col_btn:
        with st.spinner("Gerando PDF..."):
            pdf_bytes = SEGMENTOS_CONFIG[segmento_selecionado]["pdf_class"].gerar(
                df=df_seg,
                sla_meta=sla_meta,
                p_ot=p_ot,
                p_base=p_base,
                p_pess=p_pess,
                min_aloc=min_aloc,
                top_n=min(top_n, 15),
            )
        st.download_button(
            label=f"📄 Baixar PDF — {segmento_selecionado}",
            data=pdf_bytes,
            file_name=(
                f"relatorio_{segmento_selecionado.lower()}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            ),
            mime="application/pdf",
            key=f"pdf_dl_{segmento_selecionado}",
            use_container_width=True,
            type="primary",
        )
    with col_desc:
        render_insight(
            "O PDF inclui métricas, projeções, top técnicos e plano de ação.",
            tipo="info",
        )

    st.divider()

    # ── Sub-abas ───────────────────────────────────────────────────────
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
        _sub_visao_geral(
            segmento_selecionado,
            df_seg,
            m_seg,
            p_ot,
            p_base,
            p_pess,
            sla_meta,
        )
    with sub2:
        _sub_causa_raiz(segmento_selecionado, df_seg)
    with sub3:
        _sub_tecnicos(
            segmento_selecionado,
            df_seg,
            p_base,
            min_aloc,
            top_n,
            sla_meta,
        )
    with sub4:
        _sub_plano_acao(segmento_selecionado, df_seg, p_base, sla_meta)
    with sub5:
        _sub_pendentes(segmento_selecionado, df_seg)


if __name__ == "__main__":
    main()