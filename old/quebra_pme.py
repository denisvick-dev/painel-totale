from __future__ import annotations

import sys
from pathlib import Path

# ── Adiciona pages/ ao sys.path (onde quebra.py está) ───────────────
_DIR = Path(__file__).resolve().parent   # .../projeto/pages/
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

# ── Raiz do projeto (um nível acima de pages/) ───────────────────────
_ROOT = _DIR.parent                      # .../projeto/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from datetime import datetime
from html import escape
from io import BytesIO
from textwrap import dedent
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pandas.io.formats.style import Styler

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ────────────────────────────────────────────────────────────────
# 🎨 DESIGN SYSTEM CORPORATIVO
# ⚠️ Cards KPI, insights e o tipo TemaKPI vêm DIRETO do
# componentes.py — garante visual corporativo global (fontes
# Manrope/Inter, gradientes, sombras) e type-safety consistente.
# ────────────────────────────────────────────────────────────────
from components.componentes import (
    aplicar_estilo as _aplicar_estilo_global,
    render_kpi,
    render_kpi_sm,
    render_insight,
    TemaKPI,          # ← Literal["azul","verde","vermelho","laranja","cinza"]
)

# ────────────────────────────────────────────────────────────────
# 🧠 LÓGICA DE DOMÍNIO — quebra de agenda
# Apenas componentes EXCLUSIVOS deste dashboard (segmento-header,
# alerta-sla, dataframe com styler condicional).
# ────────────────────────────────────────────────────────────────
from old.quebra import (
    Config,
    Motor,
    Utils,
    aplicar_estilo,             # CSS de classes de domínio
    render_alerta_sla,
    render_dataframe,
    render_resultado_base,
    render_section,
    render_segmento_header,
)

# ====================================================
# CONFIGURAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(
    page_title="PME — Quebra de Agenda",
    page_icon="🏢",
    layout="wide",
)

# ⚠️ Aplica AMBAS as camadas de estilo:
# 1) Design system global (fontes, KPI cards, tema Plotly)
# 2) Classes de domínio (segmento-header, alerta-sla, styled-table-wrapper)
_aplicar_estilo_global()
aplicar_estilo()

for k in ("df_memoria",):
    st.session_state.setdefault(k, None)


# ====================================================
# CONSTANTES DE DOMÍNIO
# ====================================================
TIPO = "PME"
SLA_DEFAULT = Config.SLA_PME

ACOES_PME: List[tuple] = [
    (
        "🟡 MÉDIA",
        "Verificar disponibilidade de técnicos habilitados em PME para "
        "redistribuição de carteira nas regiões críticas.",
        "acao",
    ),
    (
        "🟡 MÉDIA",
        "Acionar equipe comercial PME para comunicação proativa com "
        "clientes com agenda em risco de quebra.",
        "acao",
    ),
    (
        "🟢 BAIXA",
        "Revisar janelas de atendimento PME — clientes empresariais têm "
        "menor flexibilidade de horário. Ajustar agendamentos para períodos "
        "de maior disponibilidade.",
        "info",
    ),
]

FMT_QUEBRA: Dict[str, str] = {
    "Quebra Atual": "{:.2%}",
    "Fechamento Otimista": "{:.2%}",
    "Fechamento Base": "{:.2%}",
    "Fechamento Pessimista": "{:.2%}",
}


# ====================================================
# TOPO FIXO — HERO ROXO PME + RESULTADO DA BASE
# ────────────────────────────────────────────────────
# ⚠️ Hero PME PRESERVADO na cor roxa original (identidade
# visual do segmento). NÃO substituir pelo hero azul-laranja
# global — cada segmento (PME, Migração) tem cor própria
# definida em Config.SEGMENTOS_CONFIG.
# ====================================================
def _injetar_css_topo_fixo_pme() -> None:
    """CSS local para fixar Hero + Resultado da Base durante a rolagem."""
    st.markdown(
        dedent(
            """
<style>
/* Wrapper do elemento Streamlit que contém o topo */
div[data-testid="stElementContainer"]:has(.topo-fixo-pme) {
    position: sticky !important;
    top: 0.75rem !important;
    z-index: 1000 !important;
}

/* Fundo sutil evita que o conteúdo atrás apareça ao rolar */
.topo-fixo-pme {
    background: rgba(248, 250, 252, 0.96);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    padding: 0.5rem 0;
    border-radius: 16px;
}

/* ── Hero PME (ROXO — IDENTIDADE DO SEGMENTO) ───────── */
.topo-fixo-pme .hero-pme {
    background: linear-gradient(
        135deg,
        #4C1D95 0%,
        #7C3AED 55%,
        #A855F7 100%
    );
    padding: 32px 40px;
    border-radius: 16px;
    color: white;
    box-shadow: 0 10px 40px rgba(76, 29, 149, 0.25);
    margin-bottom: 12px;
    position: relative;
    overflow: hidden;
}

.topo-fixo-pme .hero-pme::before {
    content: "";
    position: absolute;
    top: -55%;
    right: -8%;
    width: 390px;
    height: 390px;
    background: rgba(255, 255, 255, 0.07);
    border-radius: 50%;
    pointer-events: none;
}

.topo-fixo-pme .hero-pme h1 {
    position: relative;
    z-index: 2;
    color: white !important;
    font-family: "Manrope", "Segoe UI", Arial, sans-serif !important;
    font-size: 34px;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.28);
}

.topo-fixo-pme .hero-pme p {
    position: relative;
    z-index: 2;
    color: rgba(255, 255, 255, 0.92) !important;
    font-family: "Inter", "Segoe UI", Arial, sans-serif !important;
    font-size: 15px;
    margin: 8px 0 0;
    font-weight: 400;
}

/* ── Resultado da Base (fica sob o hero) ─────────────── */
.topo-fixo-pme .resultado-base {
    margin-bottom: 0 !important;
    background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
    padding: 1rem 1.5rem;
    border-radius: 0.75rem;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.6rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.topo-fixo-pme .resultado-base-label {
    color: #94A3B8;
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.topo-fixo-pme .resultado-base-regiao {
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 700;
    border: 2px solid;
}

.topo-fixo-pme .resultado-base-count {
    color: #64748B;
    font-size: 0.72rem;
    margin-left: auto;
    font-weight: 600;
}

/* Ajuste para telas menores */
@media (max-width: 768px) {
    div[data-testid="stElementContainer"]:has(.topo-fixo-pme) {
        top: 0.25rem !important;
    }
    .topo-fixo-pme .hero-pme { padding: 22px 20px; }
    .topo-fixo-pme .hero-pme h1 { font-size: 25px; }
    .topo-fixo-pme .resultado-base-count {
        width: 100%;
        margin-left: 0;
    }
}
</style>
            """
        ),
        unsafe_allow_html=True,
    )

# ====================================================
# 🎨 CARD DE STATUS PME (novo — visual unificado)
# ====================================================
def _render_card_status_pme(m_seg: Dict[str, Any], sla_meta: float) -> None:
    """
    Card unificado de status do segmento PME.
    Substitui os antigos `render_segmento_header` + `render_alerta_sla`
    por um único componente visual coeso e corporativo.
    """
    quebra_atual = float(m_seg["quebra_atual"])
    dentro_sla = quebra_atual <= sla_meta
    diferenca = sla_meta - quebra_atual

    # ─── Configuração de estado ────────────────────
    if dentro_sla:
        status_label = "DENTRO DO SLA"
        status_icone = "✓"
        cor_principal = "#059669"      # verde
        cor_bg_status = "#D1FAE5"
        cor_texto_status = "#065F46"
        mensagem = (
            f"PME com folga de <strong>{diferenca:.2%}</strong> em relação à meta. "
            "Manter ritmo de execução para preservar o desempenho."
        )
        icone_mensagem = "✅"
    else:
        excesso = quebra_atual - sla_meta
        status_label = "FORA DO SLA"
        status_icone = "!"
        cor_principal = "#DC2626"      # vermelho
        cor_bg_status = "#FEE2E2"
        cor_texto_status = "#991B1B"
        mensagem = (
            f"PME acima da meta em <strong>{excesso:.2%}</strong>. "
            "Ação corretiva necessária — reforçar equipe e priorizar execução."
        )
        icone_mensagem = "🚨"

    # ─── Formatação dos números ────────────────────
    quebra_fmt = f"{quebra_atual:.2%}".replace(".", ",")
    meta_fmt = f"{sla_meta:.2%}".replace(".", ",")

    # ─── HTML em uma linha só (evita virar code block) ──
    header_esq = (
        f'<div style="display:flex;align-items:center;gap:14px;">'
        f'<div style="width:44px;height:44px;background:linear-gradient(135deg,#7C3AED 0%,#A855F7 100%);'
        f'border-radius:10px;display:flex;align-items:center;justify-content:center;'
        f'box-shadow:0 4px 12px rgba(124,58,237,0.25);">'
        f'<span style="font-size:22px;">🏢</span>'
        f'</div>'
        f'<div>'
        f'<div style="font-family:\'Manrope\',sans-serif;font-size:18px;font-weight:800;'
        f'color:#1F2937;letter-spacing:-0.3px;line-height:1.1;">PME</div>'
        f'<div style="font-family:\'Inter\',sans-serif;font-size:12px;color:#6B7280;'
        f'font-weight:500;margin-top:2px;">Pequenas e Médias Empresas</div>'
        f'</div>'
        f'</div>'
    )

    badge_status = (
        f'<div style="display:inline-flex;align-items:center;gap:6px;'
        f'padding:6px 14px;background:{cor_bg_status};border-radius:999px;'
        f'border:1px solid {cor_principal};">'
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:18px;height:18px;background:{cor_principal};color:white;border-radius:50%;'
        f'font-size:11px;font-weight:800;">{status_icone}</span>'
        f'<span style="font-family:\'Inter\',sans-serif;font-size:11px;font-weight:700;'
        f'color:{cor_texto_status};text-transform:uppercase;letter-spacing:0.6px;">'
        f'{status_label}</span>'
        f'</div>'
    )

    pill_quebra = (
        f'<div style="display:inline-flex;flex-direction:column;padding:6px 14px;'
        f'background:#F8FAFC;border-radius:8px;border:1px solid #E2E8F0;">'
        f'<span style="font-size:10px;color:#6B7280;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.6px;">Quebra Atual</span>'
        f'<span style="font-family:\'Manrope\',sans-serif;font-size:16px;color:{cor_principal};'
        f'font-weight:800;font-variant-numeric:tabular-nums;line-height:1.2;">{quebra_fmt}</span>'
        f'</div>'
    )

    pill_meta = (
        f'<div style="display:inline-flex;flex-direction:column;padding:6px 14px;'
        f'background:#F8FAFC;border-radius:8px;border:1px solid #E2E8F0;">'
        f'<span style="font-size:10px;color:#6B7280;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.6px;">Meta SLA</span>'
        f'<span style="font-family:\'Manrope\',sans-serif;font-size:16px;color:#374151;'
        f'font-weight:800;font-variant-numeric:tabular-nums;line-height:1.2;">{meta_fmt}</span>'
        f'</div>'
    )

    header_dir = (
        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">'
        f'{badge_status}{pill_quebra}{pill_meta}'
        f'</div>'
    )

    # ─── Barra de progresso ─────────────────────────
    pct_barra = min(100.0, (quebra_atual / (sla_meta * 2)) * 100) if sla_meta > 0 else 0
    barra = (
        f'<div style="margin:16px 0 12px 0;">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:6px;'
        f'font-size:11px;color:#6B7280;font-weight:600;">'
        f'<span>0%</span><span>Meta {meta_fmt}</span><span>{sla_meta*2:.0%}</span>'
        f'</div>'
        f'<div style="position:relative;height:8px;background:#E5E7EB;border-radius:4px;overflow:hidden;">'
        f'<div style="position:absolute;left:50%;top:0;width:2px;height:100%;background:#374151;z-index:2;"></div>'
        f'<div style="width:{pct_barra}%;height:100%;background:linear-gradient(90deg,{cor_principal} 0%,{cor_principal}CC 100%);border-radius:4px;transition:width 0.4s;"></div>'
        f'</div>'
        f'</div>'
    )

    # ─── Mensagem final ─────────────────────────────
    mensagem_html = (
        f'<div style="display:flex;align-items:flex-start;gap:10px;'
        f'padding:12px 14px;background:{cor_bg_status};border-left:3px solid {cor_principal};'
        f'border-radius:6px;">'
        f'<span style="font-size:16px;line-height:1;flex-shrink:0;">{icone_mensagem}</span>'
        f'<div style="font-family:\'Inter\',sans-serif;font-size:13px;color:{cor_texto_status};'
        f'line-height:1.55;font-weight:500;">{mensagem}</div>'
        f'</div>'
    )

    # ─── Header (linha superior: título + status) ──
    header_completo = (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'flex-wrap:wrap;gap:16px;">{header_esq}{header_dir}</div>'
    )

    # ─── Card final ────────────────────────────────
    card_html = (
        f'<div style="background:white;border:1px solid #E5E7EB;border-radius:14px;'
        f'padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.04);margin:16px 0 24px 0;'
        f'border-top:3px solid #7C3AED;">'
        f'{header_completo}'
        f'{barra}'
        f'{mensagem_html}'
        f'</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)

def _html_resultado_base_pme(regioes: List[str], total: int) -> str:
    """Gera o HTML do Resultado da Base para uso dentro do topo fixo."""
    cores_regiao = {
        "LESTE":  {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
        "GRU":    {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
        "ABCDM":  {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
        "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
    }

    badges = ""
    for regiao in sorted(regioes):
        regiao_str = str(regiao).strip().upper()
        if not regiao_str or regiao_str in {"NAN", "NONE"}:
            continue
        cor = cores_regiao.get(regiao_str, cores_regiao["OUTRAS"])
        badges += (
            f'<span class="resultado-base-regiao" '
            f'style="background:{cor["bg"]};'
            f'color:{cor["text"]};'
            f'border-color:{cor["border"]};">'
            f"{escape(regiao_str)}"
            f"</span>"
        )

    if not badges:
        cor = cores_regiao["OUTRAS"]
        badges = (
            f'<span class="resultado-base-regiao" '
            f'style="background:{cor["bg"]};'
            f'color:{cor["text"]};'
            f'border-color:{cor["border"]};">'
            f"OUTRAS"
            f"</span>"
        )

    total_fmt = f"{total:,}".replace(",", ".")

    return (
        f'<div class="resultado-base">'
        f'<span class="resultado-base-label">📋 Resultado da Base:</span>'
        f"{badges}"
        f'<span class="resultado-base-count">{total_fmt} registros</span>'
        f"</div>"
    )


def _render_topo_fixo_pme(regioes: List[str], total: int) -> None:
    """Renderiza Hero PME + Resultado Base em um único bloco fixo."""
    resultado_html = _html_resultado_base_pme(regioes, total)

    st.markdown(
        dedent(
            f"""
<div class="topo-fixo-pme">
    <div class="hero-pme">
        <h1>🏢 PME — Quebra de Agenda</h1>
        <p>Análise estratégica dedicada às Pequenas e Médias Empresas</p>
    </div>
    {resultado_html}
</div>
            """
        ),
        unsafe_allow_html=True,
    )


# ====================================================
# GERAÇÃO DE PDF EXECUTIVO PME (INTOCADO)
# ====================================================
class PDFExecutivoPME:
    """Relatório executivo em PDF dedicado ao segmento PME."""

    # ── Paleta de cores ─────────────────────────────────────────────
    COR_PRIMARIA:   str = "#4C1D95"
    COR_SECUNDARIA: str = "#7C3AED"
    COR_TEXTO:      str = "#1E1B4B"
    COR_SUBTEXTO:   str = "#6B7280"
    COR_OK:         str = "#059669"
    COR_ALERTA:     str = "#D97706"
    COR_CRITICO:    str = "#DC2626"
    COR_LINHA:      str = "#E5E7EB"
    COR_LINHA_ALT:  str = "#F9FAFB"

    LARGURA_UTIL: float = 27.7
    MARGEM_H:     float = 0.8
    MARGEM_TOP:   float = 0.8
    MARGEM_BOT:   float = 1.3

    LOGO_PATH: Path = (
        Path(__file__).resolve().parent.parent
        / "assets" / "images" / "novo-logo-totale.png"
    )

    @classmethod
    def _fmt(cls, v: Any, col: str = "") -> str:
        if pd.isna(v):
            return "—"
        col_u = str(col).upper()
        pct_keys = {"QUEBRA", "FECHAMENTO", "META", "PROBAB", "%", "ACUMULADO", "TOTAL"}
        if isinstance(v, (float, np.floating)):
            if any(k in col_u for k in pct_keys):
                return f"{v:.2%}"
            return (
                f"{int(v):,}".replace(",", ".")
                if float(v).is_integer()
                else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
        if isinstance(v, (int, np.integer)):
            return f"{v:,}".replace(",", ".")
        return escape(str(v))

    @classmethod
    def _estilos(cls) -> Any:
        s = getSampleStyleSheet()
        s.add(ParagraphStyle(
            name="PME_Titulo", fontName="Helvetica-Bold", fontSize=24, leading=30,
            textColor=colors.white, alignment=TA_CENTER, spaceAfter=4,
        ))
        s.add(ParagraphStyle(
            name="PME_Subtitulo", fontName="Helvetica", fontSize=10, leading=14,
            textColor=colors.HexColor("#DDD6FE"), alignment=TA_CENTER, spaceAfter=0,
        ))
        s.add(ParagraphStyle(
            name="PME_Secao", fontName="Helvetica-Bold", fontSize=11, leading=15,
            textColor=colors.HexColor(cls.COR_PRIMARIA),
            spaceBefore=10, spaceAfter=4,
        ))
        s.add(ParagraphStyle(
            name="PME_Texto", fontName="Helvetica", fontSize=8, leading=11,
            textColor=colors.HexColor(cls.COR_TEXTO),
            alignment=TA_LEFT, spaceAfter=3,
        ))
        s.add(ParagraphStyle(
            name="PME_Destaque", fontName="Helvetica-Bold", fontSize=8, leading=11,
            textColor=colors.HexColor(cls.COR_PRIMARIA),
            alignment=TA_LEFT, spaceAfter=2,
        ))
        s.add(ParagraphStyle(
            name="PME_Alerta", fontName="Helvetica-Bold", fontSize=8, leading=11,
            textColor=colors.HexColor(cls.COR_CRITICO),
            alignment=TA_LEFT, spaceAfter=2,
        ))
        s.add(ParagraphStyle(
            name="PME_OK", fontName="Helvetica-Bold", fontSize=8, leading=11,
            textColor=colors.HexColor(cls.COR_OK),
            alignment=TA_LEFT, spaceAfter=2,
        ))
        return s

    @classmethod
    def _tab(
        cls,
        df: pd.DataFrame,
        limite: Optional[int] = None,
        larguras: Optional[List[float]] = None,
        cor_col_quebra: Optional[str] = None,
        sla_meta: float = 0.20,
    ) -> Table:
        def _fazer_tabela_interna() -> Table:
            if df is None or df.empty:
                vazio: List[List[Any]] = [["Sem dados disponíveis"]]
                t = Table(vazio, colWidths=[cls.LARGURA_UTIL * cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(cls.COR_LINHA_ALT)),
                    ("TEXTCOLOR",  (0, 0), (-1, -1), colors.HexColor(cls.COR_SUBTEXTO)),
                    ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE",   (0, 0), (-1, -1), 8),
                    ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor(cls.COR_LINHA)),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                return t

            base = df.head(limite) if limite else df.copy()

            st_h = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=6.5, leading=8,
                                  textColor=colors.white, alignment=TA_CENTER)
            st_c = ParagraphStyle("tc", fontName="Helvetica", fontSize=6.5, leading=8.5,
                                  textColor=colors.HexColor(cls.COR_TEXTO), alignment=TA_CENTER)
            st_c_left = ParagraphStyle("tc_left", fontName="Helvetica", fontSize=6.5, leading=8.5,
                                       textColor=colors.HexColor(cls.COR_TEXTO), alignment=TA_LEFT)

            dados: List[List[Any]] = [[Paragraph(str(c), st_h) for c in base.columns]]
            for _, row in base.iterrows():
                linha: List[Any] = []
                for idx_c, c in enumerate(base.columns):
                    cell_st = st_c_left if idx_c == 0 else st_c
                    linha.append(Paragraph(cls._fmt(row[c], c), cell_st))
                dados.append(linha)

            if larguras:
                col_widths = [w * cm for w in larguras]
            else:
                col_widths = [w * cm for w in cls._calcular_larguras(base)]

            soma = sum(col_widths)
            if soma > cls.LARGURA_UTIL * cm:
                fator = (cls.LARGURA_UTIL * cm) / soma
                col_widths = [w * fator for w in col_widths]

            tab = Table(dados, colWidths=col_widths, repeatRows=1)

            style: List[Any] = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(cls.COR_PRIMARIA)),
                ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
                ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",   (0, 0), (-1, 0), 6.5),
                ("LINEBELOW",  (0, 0), (-1, 0), 1.5, colors.HexColor(cls.COR_SECUNDARIA)),
                ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE",   (0, 1), (-1, -1), 6.5),
                ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
                ("ALIGN",      (0, 1), (0, -1), "LEFT"),
                ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
                ("BOX",        (0, 0), (-1, -1), 0.75, colors.HexColor(cls.COR_PRIMARIA)),
                ("INNERGRID",  (0, 0), (-1, -1), 0.25, colors.HexColor(cls.COR_LINHA)),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ]

            for i in range(1, len(dados)):
                bg = colors.white if i % 2 == 1 else colors.HexColor(cls.COR_LINHA_ALT)
                style.append(("BACKGROUND", (0, i), (-1, i), bg))

            if cor_col_quebra and cor_col_quebra in base.columns:
                col_idx = list(base.columns).index(cor_col_quebra)
                for row_i, (_, row) in enumerate(base.iterrows(), start=1):
                    try:
                        val = float(row[cor_col_quebra])
                        if val > sla_meta:
                            bg_c = colors.HexColor("#FEE2E2")
                            txt_c = colors.HexColor(cls.COR_CRITICO)
                        elif val > sla_meta * 0.85:
                            bg_c = colors.HexColor("#FEF9C3")
                            txt_c = colors.HexColor(cls.COR_ALERTA)
                        else:
                            bg_c = colors.HexColor("#DCFCE7")
                            txt_c = colors.HexColor(cls.COR_OK)
                        style += [
                            ("BACKGROUND", (col_idx, row_i), (col_idx, row_i), bg_c),
                            ("TEXTCOLOR",  (col_idx, row_i), (col_idx, row_i), txt_c),
                            ("FONTNAME",   (col_idx, row_i), (col_idx, row_i), "Helvetica-Bold"),
                        ]
                    except (ValueError, TypeError):
                        pass

            tab.setStyle(TableStyle(style))
            return tab

        tabela_interna = _fazer_tabela_interna()
        wrapper_data: List[List[Any]] = [[tabela_interna]]
        wrapper = Table(wrapper_data, colWidths=[cls.LARGURA_UTIL * cm], hAlign="CENTER")
        wrapper.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return wrapper

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
    def _rodape(cls, canvas: Any, doc: Any) -> None:
        canvas.saveState()
        page_w, _ = landscape(A4)
        x_esq   = cls.MARGEM_H * cm
        x_dir   = page_w - cls.MARGEM_H * cm
        y_linha = 1.05 * cm
        y_txt   = 0.52 * cm

        canvas.setStrokeColor(colors.HexColor(cls.COR_LINHA))
        canvas.setLineWidth(0.5)
        canvas.line(x_esq, y_linha, x_dir, y_linha)

        x_txt = x_esq
        if cls.LOGO_PATH.exists():
            try:
                logo_h = 0.50 * cm
                reader  = ImageReader(str(cls.LOGO_PATH))
                iw, ih  = reader.getSize()
                logo_w  = logo_h * (iw / ih) if ih > 0 else logo_h * 3.5
                canvas.drawImage(
                    str(cls.LOGO_PATH),
                    x_esq, y_txt - 0.02 * cm,
                    width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask="auto",
                )
                x_txt = x_esq + logo_w + 0.25 * cm
            except Exception:
                pass

        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor(cls.COR_SUBTEXTO))
        canvas.drawString(
            x_txt, y_txt,
            f"PME — Gestão de Quebra de Agenda  |  "
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Confidencial",
        )
        canvas.drawRightString(x_dir, y_txt, f"Página {doc.page}")
        canvas.restoreState()

    @classmethod
    def _capa(cls, s: Any, m: dict, sla_meta: float, total_registros: int) -> List[Any]:
        el: List[Any] = []

        if cls.LOGO_PATH.exists():
            try:
                reader  = ImageReader(str(cls.LOGO_PATH))
                iw, ih  = reader.getSize()
                logo_h  = 1.5 * cm
                logo_w  = logo_h * (iw / ih) if ih > 0 else logo_h * 3.5

                logo_img = RLImage(str(cls.LOGO_PATH), width=logo_w, height=logo_h)
                logo_wrapper = Table(
                    [[logo_img]], colWidths=[cls.LARGURA_UTIL * cm], hAlign="CENTER",
                )
                logo_wrapper.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                    ("TOPPADDING",    (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                el.append(logo_wrapper)
            except Exception:
                pass

        banner_data: List[List[Any]] = [
            [Paragraph("RELATÓRIO EXECUTIVO — PME", s["PME_Titulo"])],
            [Paragraph(
                f"Quebra de Agenda  •  "
                f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}  •  "
                f"{total_registros:,} registros analisados".replace(",", "."),
                s["PME_Subtitulo"],
            )],
        ]
        tab_banner = Table(banner_data, colWidths=[cls.LARGURA_UTIL * cm], hAlign="CENTER")
        tab_banner.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(cls.COR_PRIMARIA)),
            ("TOPPADDING",    (0, 0), (0, 0),   20),
            ("BOTTOMPADDING", (0, 0), (0, 0),   6),
            ("TOPPADDING",    (0, 1), (0, 1),   4),
            ("BOTTOMPADDING", (0, 1), (0, 1),   20),
            ("LEFTPADDING",   (0, 0), (-1, -1), 20),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 20),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("BOX",           (0, 0), (-1, -1), 3, colors.HexColor(cls.COR_SECUNDARIA)),
        ]))
        el.append(tab_banner)
        el.append(Spacer(1, 0.3 * cm))

        dentro_sla = m["quebra_atual"] <= sla_meta
        status_txt = "DENTRO DO SLA" if dentro_sla else "FORA DO SLA"
        icone      = "✅" if dentro_sla else "❌"
        cor_status = cls.COR_OK if dentro_sla else cls.COR_CRITICO

        st_status = ParagraphStyle(
            "st_status", fontName="Helvetica-Bold", fontSize=11,
            leading=15, textColor=colors.white, alignment=TA_CENTER,
        )
        tab_badge = Table(
            [[Paragraph(f"{icone}  {status_txt}", st_status)]],
            colWidths=[cls.LARGURA_UTIL * cm], hAlign="CENTER",
        )
        tab_badge.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(cor_status)),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor(cor_status)),
        ]))
        el.append(tab_badge)
        el.append(Spacer(1, 0.3 * cm))

        kpis: List[tuple] = [
            ("Alocado",      cls._fmt(m["alocado"]),        cls.COR_PRIMARIA),
            ("Executadas",   cls._fmt(m["exec"]),           cls.COR_OK),
            ("Não Exec.",    cls._fmt(m["naoexec"]),        cls.COR_CRITICO),
            ("Pendentes",    cls._fmt(m["pend"]),           cls.COR_SUBTEXTO),
            ("Quebra Atual", f"{m['quebra_atual']:.2%}",
                cls.COR_CRITICO if m["quebra_atual"] > sla_meta else cls.COR_OK),
            ("Meta SLA",     f"{sla_meta:.2%}",             cls.COR_PRIMARIA),
            ("Proj. Base",   f"{m['fechamento_proj']:.2%}",
                cls.COR_CRITICO if m["fechamento_proj"] > sla_meta else cls.COR_OK),
            ("Status",       status_txt,                     cor_status),
        ]

        kpi_col_w = cls.LARGURA_UTIL / 4
        kpi_rows: List[List[Any]] = []

        for i in range(0, len(kpis), 4):
            chunk = kpis[i : i + 4]
            while len(chunk) < 4:
                chunk.append(("", "", cls.COR_SUBTEXTO))

            linha_lbl = [
                Paragraph(k[0], ParagraphStyle(
                    f"kl_{i}_{j}", fontName="Helvetica", fontSize=7,
                    leading=9, textColor=colors.HexColor(cls.COR_SUBTEXTO),
                    alignment=TA_CENTER,
                ))
                for j, k in enumerate(chunk)
            ]
            linha_val = [
                Paragraph(k[1], ParagraphStyle(
                    f"kv_{i}_{j}", fontName="Helvetica-Bold", fontSize=17,
                    leading=21, textColor=colors.HexColor(k[2]),
                    alignment=TA_CENTER,
                ))
                for j, k in enumerate(chunk)
            ]
            kpi_rows.append(linha_lbl)
            kpi_rows.append(linha_val)

        tab_kpi = Table(kpi_rows, colWidths=[kpi_col_w * cm] * 4, hAlign="CENTER")
        tab_kpi.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(cls.COR_LINHA_ALT)),
            ("BOX",           (0, 0), (-1, -1), 1.5, colors.HexColor(cls.COR_PRIMARIA)),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, colors.HexColor(cls.COR_LINHA)),
            ("TOPPADDING",    (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, colors.HexColor(cls.COR_LINHA)),
            ("LINEBELOW",     (0, 2), (-1, 2),  0.5, colors.HexColor(cls.COR_LINHA)),
        ]))
        el.append(tab_kpi)
        return el

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
            buf, pagesize=landscape(A4),
            rightMargin=1.0 * cm, leftMargin=1.0 * cm,
            topMargin=1.0 * cm, bottomMargin=1.3 * cm,
        )

        s = cls._estilos()
        df_seg = df[df["TIPO_SERVICO"] == TIPO].copy()
        m = Motor.projetar(df_seg, p_base)
        folga = Motor.folga_sla(df_seg, sla_meta)

        el: List[Any] = []
        el += cls._capa(s, m, sla_meta, len(df_seg))
        el.append(Spacer(1, 0.4 * cm))

        # ── Seção 1 — Cenários ────────────────────────────────
        el.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor(cls.COR_SECUNDARIA)))
        el.append(Spacer(1, 0.15 * cm))
        el.append(Paragraph("1. Cenários de Fechamento", s["PME_Secao"]))

        cenarios = []
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            proj = Motor.projetar(df_seg, p)
            cenarios.append({
                "Cenário": nome, "Probab. Pend.": p,
                "Fechamento": proj["fechamento_proj"],
                "Não Exec. Proj.": proj["naoexec_proj"],
                "vs Meta": proj["fechamento_proj"] - sla_meta,
            })
        el.append(cls._tab(
            pd.DataFrame(cenarios),
            larguras=[4.5, 4.5, 5.5, 5.5, 5.0],
            cor_col_quebra="Fechamento",
            sla_meta=sla_meta,
        ))
        el.append(Spacer(1, 0.2 * cm))

        if m["fechamento_proj"] > sla_meta:
            diag = (
                f"O cenário base projeta fechamento de {m['fechamento_proj']:.2%}, "
                f"{m['fechamento_proj'] - sla_meta:.2%} acima da meta de {sla_meta:.2%}. "
                f"Serão necessárias ao menos "
                f"{int(np.ceil(folga['precisa_executar_pendente'])):,} execuções "
                f"nos pendentes para retornar ao SLA."
            )
            el.append(Paragraph(escape(diag), s["PME_Alerta"]))
        else:
            diag = (
                f"O cenário base projeta fechamento de {m['fechamento_proj']:.2%}, "
                f"com folga de {sla_meta - m['fechamento_proj']:.2%}. "
                f"Ainda é possível ter até "
                f"{int(np.floor(folga['folga_ne_pendente'])):,} OS adicionais "
                f"como não executadas dentro do SLA."
            )
            el.append(Paragraph(escape(diag), s["PME_OK"]))

        el.append(Spacer(1, 0.3 * cm))

        # ── Seção 2 — Técnicos Críticos ───────────────────────
        el.append(Paragraph("2. Técnicos Críticos", s["PME_Secao"]))
        el.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor(cls.COR_LINHA)))
        el.append(Spacer(1, 0.15 * cm))

        df_tec = Motor.tecnicos_criticos(df_seg, TIPO, p_base, float(min_aloc), int(top_n))
        cols_tec = [c for c in [
            "TÉCNICO", "Alocado", "Executada", "Não Executada", "Pendente",
            "Quebra Atual", "Fechamento Otimista", "Fechamento Base", "Fechamento Pessimista",
        ] if c in df_tec.columns]

        el.append(cls._tab(
            df_tec[cols_tec] if not df_tec.empty else df_tec,
            limite=10, cor_col_quebra="Fechamento Base", sla_meta=sla_meta,
        ))

        if not df_tec.empty:
            acima = int((df_tec["Fechamento Base"] > sla_meta).sum())
            txt_tec = (
                f"{acima} de {len(df_tec)} técnicos projetam fechamento "
                f"acima da meta de {sla_meta:.2%}."
            )
            el.append(Spacer(1, 0.15 * cm))
            el.append(Paragraph(escape(txt_tec),
                                s["PME_Alerta"] if acima > 0 else s["PME_OK"]))

        el.append(Spacer(1, 0.4 * cm))

        # ── Seção 3 — Causas ──────────────────────────────────
        el.append(Paragraph("3. Principais Causas de Quebra (Pareto)", s["PME_Secao"]))
        el.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor(cls.COR_LINHA)))
        el.append(Spacer(1, 0.15 * cm))

        df_causa = Motor.causa_raiz_segmento(df_seg, TIPO, "_COL_BAIXA", top_n=8)
        el.append(cls._tab(df_causa, limite=8, larguras=[9.0, 4.5, 4.5, 4.5]))

        el.append(Spacer(1, 0.4 * cm))

        # ── Seção 4 — Monitores ───────────────────────────────
        el.append(Paragraph("4. Monitores do Segmento PME", s["PME_Secao"]))
        el.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor(cls.COR_LINHA)))
        el.append(Spacer(1, 0.15 * cm))

        df_mon = Motor.tabela_cenarios(df_seg, "MONITOR", p_ot, p_base, p_pess, float(min_aloc))
        cols_mon = [c for c in [
            "MONITOR", "Alocado", "Executada", "Não Executada", "Pendente",
            "Quebra Atual", "Fechamento Base",
        ] if c in df_mon.columns]

        el.append(cls._tab(
            df_mon[cols_mon] if not df_mon.empty else df_mon,
            limite=10, cor_col_quebra="Fechamento Base", sla_meta=sla_meta,
        ))

        doc.build(el, onFirstPage=cls._rodape, onLaterPages=cls._rodape)
        buf.seek(0)
        return buf.getvalue()


# ====================================================
# UTILITÁRIO — DataFrame de Pendentes PME (INTOCADO)
# ====================================================
def _build_df_pendentes(df_seg: pd.DataFrame) -> pd.DataFrame:
    """Retorna DataFrame com OS pendentes do segmento PME."""
    MAPA_COLUNAS = {
        "Contrato": [
            "CONTRATO", "Nº CONTRATO", "NUM_CONTRATO",
            "NUMERO CONTRATO", "NÚMERO CONTRATO", "CONTRATO_ID",
            "COD_CONTRATO", "CÓDIGO CONTRATO",
        ],
        "Login": [
            "LOGIN", "LOGIN TÉCNICO", "LOGIN_TECNICO",
            "USER", "USUÁRIO", "USERNAME",
        ],
        "Técnico": [
            "TÉCNICO", "TECNICO", "NOME TÉCNICO",
            "NOME_TECNICO", "NOME DO TÉCNICO",
        ],
        "Monitor": [
            "MONITOR", "SUPERVISOR", "NOME MONITOR", "NOME_MONITOR",
        ],
        "Qtde. O.S.": ["TOTAL DE TAREFAS"],
    }

    def _encontrar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
        cols_upper = {c.upper(): c for c in df.columns}
        for cand in candidatos:
            if cand.upper() in cols_upper:
                return cols_upper[cand.upper()]
        return None

    if "Status Contrato" in df_seg.columns:
        mask_pend = df_seg["Status Contrato"].str.upper().isin(
            ["PENDENTE", "PENDING", "ABERTO", "EM ABERTO", "NÃO EXECUTADO"]
        )
    else:
        mask_pend = pd.Series([True] * len(df_seg), index=df_seg.index)

    df_pend = df_seg[mask_pend].copy()

    if df_pend.empty:
        return pd.DataFrame(
            columns=["Contrato", "Login", "Técnico", "Monitor", "Qtde. de O.S."]
        )

    df_out = pd.DataFrame(index=df_pend.index)
    for nome_saida, candidatos in MAPA_COLUNAS.items():
        col_real = _encontrar_coluna(df_pend, candidatos)
        df_out[nome_saida] = df_pend[col_real].values if col_real else "N/D"

    if "Qtde. O.S." in df_out.columns:
        df_out["Qtde. O.S."] = (
            pd.to_numeric(df_out["Qtde. O.S."], errors="coerce")
            .fillna(0).astype(int)
        )

    df_out = (
        df_out.drop_duplicates()
        .sort_values(["Técnico"], na_position="last")
        .reset_index(drop=True)
    )
    df_out.index = df_out.index + 1
    return df_out


# ====================================================
# FUNÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    _injetar_css_topo_fixo_pme()

    # ── Guarda de estado ────────────────────────────────────────────
    if st.session_state.get("df_memoria") is None:
        render_insight(
            "Nenhuma base carregada. Volte ao **Dashboard Geral** no menu "
            "lateral e faça o upload.",
            tipo="alerta",
        )
        return

    df_full = st.session_state["df_memoria"].copy()
    if "Status Contrato" not in df_full.columns:
        col_s = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1"])
        df_full["Status Contrato"] = (
            Utils.classificar_status(df_full[col_s]) if col_s else "Pendente"
        )

    # ── Sidebar ─────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros PME")

        monitores = ["Todos"] + sorted(
            str(x) for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon = st.selectbox("👔 Monitor", monitores, key="mon_pme")
        df_filt = df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]

        tecnicos = ["Todos"] + sorted(
            str(x) for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        )
        sel_tec = st.selectbox("👤 Técnico", tecnicos, key="tec_pme")
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.divider()
        st.subheader("🔮 Probabilidades")
        p_ot   = st.slider("Otimista (%)",   0, 100, 15, 5, key="pot_pme")   / 100.0
        p_base = st.slider("Base (%)",       0, 100, 20, 5, key="pbase_pme") / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 50, 5, key="ppess_pme") / 100.0

        st.divider()
        sla_meta = (
            st.number_input(
                "Meta SLA PME (%)",
                0.0, 100.0, float(SLA_DEFAULT * 100), 1.0,
                key="sla_pme_v",
            ) / 100
        )

        min_aloc = 1
        top_n = 999_999

    if df.empty:
        render_insight("Nenhum dado para os filtros selecionados.", tipo="alerta")
        return

    # ── HERO ROXO + RESULTADO DA BASE (topo fixo) ───────────────────
    if Config.COL_REGIAO in df.columns:
        regioes_pme = [
            str(regiao).strip().upper()
            for regiao in df[Config.COL_REGIAO].dropna().unique()
            if str(regiao).strip()
        ]
    else:
        regioes_pme = ["OUTRAS"]

    _render_topo_fixo_pme(regioes_pme, len(df))

    # ── Filtra somente PME ──────────────────────────────────────────
    df_seg = df[df["TIPO_SERVICO"] == TIPO].copy()
    if df_seg.empty:
        render_insight(
            "Nenhum registro classificado como PME nos filtros atuais.",
            tipo="info",
        )
        return

    m_seg = Motor.projetar(df_seg, p_base)
    _render_card_status_pme(m_seg, sla_meta)
    st.markdown("")

    # ── Botão de PDF Executivo ────────────────────────────────────────
    with st.container():
        col_btn, col_desc = st.columns([1, 3])

        with col_btn:
            with st.spinner("Gerando PDF..."):
                pdf_bytes = PDFExecutivoPME.gerar(
                    df=df, sla_meta=sla_meta,
                    p_ot=p_ot, p_base=p_base, p_pess=p_pess,
                    min_aloc=float(min_aloc), top_n=min(int(top_n), 10),
                )

            st.download_button(
                label="📄 Baixar PDF Executivo PME",
                data=pdf_bytes,
                file_name=f"relatorio_pme_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                key="pdf_pme_dl",
                use_container_width=True,
                type="primary",
            )

        with col_desc:
            render_insight(
                "**O relatório PDF inclui:** Capa com métricas executivas · "
                "Cenários de fechamento (Otimista / Base / Pessimista) · "
                "Plano de ação prioritário automático · Top 10 Técnicos Críticos "
                "com coloração por SLA · Performance por Região · Pareto de "
                "causas de quebra · Ranking de Monitores",
                tipo="info",
            )

    st.divider()

    # ── Sub-abas ─────────────────────────────────────────────────────
    sub1, sub2, sub3, sub4, sub5 = st.tabs([
        "📊 Visão Geral", "🔍 Causa Raiz", "👤 Técnicos",
        "🎯 Plano de Ação", "📋 Pendentes",
    ])

    with sub1:
        _sub_visao_geral(df_seg, m_seg, p_ot, p_base, p_pess, sla_meta)
    with sub2:
        _sub_causa_raiz(df_seg)
    with sub3:
        _sub_tecnicos(df_seg, p_base, min_aloc, top_n, sla_meta)
    with sub4:
        _sub_plano_acao(df_seg, p_base, sla_meta)
    with sub5:
        _sub_pendentes(df_seg, sla_meta)


# ====================================================
# SUB-ABAS
# ====================================================
def _sub_visao_geral(df_seg, m_seg, p_ot, p_base, p_pess, sla_meta) -> None:
    render_section(f"📊 Resumo Operacional — {TIPO}")

    # ✅ Tema anotado como TemaKPI resolve o erro do Pyright
    tema_quebra: TemaKPI = (
        "vermelho" if m_seg["quebra_atual"] > sla_meta else "verde"
    )

    cols = st.columns(5)
    kpis: list[tuple[str, str, TemaKPI, str]] = [
        ("Alocado",      f"{int(m_seg['alocado']):,}",  "azul",     ""),
        ("Executadas",   f"{int(m_seg['exec']):,}",     "verde",    ""),
        ("Não Exec.",    f"{int(m_seg['naoexec']):,}",  "laranja",  ""),
        ("Pendentes",    f"{int(m_seg['pend']):,}",     "cinza",    ""),
        ("Quebra Atual", f"{m_seg['quebra_atual']:.2%}",
         tema_quebra,    f"Meta: {sla_meta:.0%}"),
    ]
    for c, (lab, val, tema, sub) in zip(cols, kpis):
        render_kpi(c, lab, val, sub=sub, tema=tema)

    st.markdown("")
    render_section("🔮 Projeções de Fechamento")

    cen = {
        n: Motor.projetar(df_seg, p)
        for n, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]
    }

    c_cen, c_gauge = st.columns([2, 3])
    with c_cen:
        for nome, cd in cen.items():
            cor_proj: TemaKPI = (
                "vermelho" if cd["fechamento_proj"] > sla_meta else "verde"
            )
            render_kpi_sm(
                st, nome, f"{cd['fechamento_proj']:.2%}",
                sub=f"Não Exec. proj.: {int(cd['naoexec_proj']):,}",
                tema=cor_proj,
            )

    with c_gauge:
        cor_bar = "#EF4444" if m_seg["quebra_atual"] > sla_meta else "#10B981"
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=m_seg["quebra_atual"] * 100,
            delta={"reference": sla_meta * 100,
                   "increasing": {"color": "#EF4444"},
                   "decreasing": {"color": "#10B981"}, "suffix": "%"},
            number={"suffix": "%", "font": {"size": 40}},
            gauge={
                "axis": {"range": [0, 50], "ticksuffix": "%"},
                "bar":  {"color": cor_bar},
                "steps": [
                    {"range": [0, sla_meta * 100], "color": "#DCFCE7"},
                    {"range": [sla_meta * 100, sla_meta * 120], "color": "#FEF9C3"},
                    {"range": [sla_meta * 120, 50], "color": "#FEE2E2"},
                ],
                "threshold": {"line": {"color": "#DC2626", "width": 3},
                              "thickness": 0.85, "value": sla_meta * 100},
            },
            title={"text": f"Quebra vs. Meta {sla_meta:.0%}", "font": {"size": 14}},
        ))
        fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("")
    render_section("🛡️ Folga de SLA")

    folga = Motor.folga_sla(df_seg, sla_meta)
    f1, f2, f3 = st.columns(3)

    # ✅ Anotação evita erro do Pyright na expressão ternária
    cor_f: TemaKPI = (
        "vermelho" if folga["estourado"]
        else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
    )
    render_kpi(f1, "Folga (OS)",
               f"{int(np.floor(folga['folga_ne_pendente'])):,}",
               sub="Não Exec. ainda permitidas", tema=cor_f)
    render_kpi(f2, "Execução Mínima",
               f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
               sub="Pendentes que devem ser executadas", tema="azul")
    render_kpi(f3, "Limite NE Total",
               f"{int(folga['limite_ne_total']):,}",
               sub=f"= {sla_meta:.0%} × {int(folga['alocado']):,}",
               tema="cinza")

    st.progress(min(1.0, max(0.0, float(m_seg["quebra_atual"] / (sla_meta * 2)))))


def _sub_causa_raiz(df_seg) -> None:
    render_section(f"🔍 Causa Raiz — {TIPO}")
    df_c = Motor.causa_raiz_segmento(df_seg, TIPO, "_COL_BAIXA", top_n=8)

    if df_c.empty:
        render_insight(
            "Coluna de código/motivo de baixa não identificada.",
            tipo="alerta",
        )
        return

    c_tab, c_chart = st.columns([1.2, 2])

    with c_tab:
        render_dataframe(
            df_c, titulo=f"Top Motivos — {TIPO}", icone="🔍",
            fmt={"% do Total": "{:.2%}", "Acumulado": "{:.2%}"},
            height=350,
        )

    with c_chart:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_c["Motivo de Baixa"], y=df_c["Volume"], name="Volume",
            marker_color="#EF4444", text=df_c["Volume"], textposition="outside",
        ))
        fig.add_trace(go.Scatter(
            x=df_c["Motivo de Baixa"], y=df_c["Acumulado"],
            name="Acumulado %", yaxis="y2", mode="lines+markers",
            line=dict(color="#7C3AED", width=2), marker=dict(size=7),
        ))
        fig.update_layout(
            title=f"Pareto de Motivos — {TIPO}",
            yaxis=dict(title="Volume"),
            yaxis2=dict(title="Acumulado %", overlaying="y", side="right",
                        tickformat=".0%", range=[0, 1.1]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=380, xaxis=dict(tickangle=-30),
        )
        fig.add_hline(y=0.8, line_dash="dot", line_color="#F59E0B",
                      yref="y2", annotation_text="80%",
                      annotation_position="top right")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if len(df_c) >= 2:
        t1, t2 = df_c.iloc[0], df_c.iloc[1]
        # ✅ Markdown **bold** em vez de <b></b>
        render_insight(
            f"Os 2 principais motivos (**{t1['Motivo de Baixa']}** e "
            f"**{t2['Motivo de Baixa']}**) respondem por "
            f"**{t2['Acumulado']:.1%}** das quebras em {TIPO}.",
            tipo="acao",
        )


def _sub_tecnicos(df_seg, p_base, min_aloc, top_n, sla_meta) -> None:
    render_section(f"👤 Técnicos com Maior Quebra — {TIPO}")
    df_tec = Motor.tecnicos_criticos(df_seg, TIPO, p_base, float(min_aloc), int(top_n))

    if df_tec.empty:
        render_insight(
            f"Não há técnicos com volume mínimo de {int(min_aloc)} OS.",
            tipo="info",
        )
        return

    render_dataframe(
        df_tec, titulo=f"Técnicos Críticos — {TIPO}", icone="🚨",
        fmt=FMT_QUEBRA, color_col="Fechamento Base",
        color_meta=sla_meta, color_invertido=True, height=450,
    )
    st.download_button(
        f"📥 Exportar Técnicos {TIPO}",
        Utils.gerar_excel(df_tec, f"Tec_{TIPO[:25]}"),
        f"tecnicos_{TIPO.lower()}.xlsx",
        key="dl_tec_pme",
    )

    df_plot = df_tec.head(10).sort_values("Fechamento Base")
    cores = ["#EF4444" if v > sla_meta else "#10B981" for v in df_plot["Fechamento Base"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_plot["TÉCNICO"], x=df_plot["Fechamento Base"],
        orientation="h", marker_color=cores,
        text=[f"{v:.1%}" for v in df_plot["Fechamento Base"]],
        textposition="outside",
    ))
    fig.add_vline(x=sla_meta, line_dash="dash", line_color="#DC2626",
                  annotation_text=f"Meta {sla_meta:.0%}")
    fig.update_layout(
        title=f"Quebra Projetada por Técnico — {TIPO}",
        xaxis_tickformat=".1%",
        height=max(300, len(df_plot) * 36),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    acima = int((df_tec["Fechamento Base"] > sla_meta).sum())
    pct = acima / len(df_tec)
    if pct > 0.5:
        # ✅ Markdown **bold**
        render_insight(
            f"**{acima} de {len(df_tec)}** técnicos ({pct:.0%}) "
            f"estão acima da meta. Avalie redistribuição de carteira.",
            tipo="critico",
        )
    elif acima > 0:
        render_insight(
            f"**{acima} técnico(s)** com quebra acima da meta.",
            tipo="alerta",
        )
    else:
        render_insight(f"Todos os técnicos dentro da meta em {TIPO}.", tipo="ok")


def _sub_plano_acao(df_seg, p_base, sla_meta) -> None:
    render_section(f"🎯 Plano de Ação — {TIPO}")

    folga = Motor.folga_sla(df_seg, sla_meta)
    cen = Motor.projetar(df_seg, p_base)
    excesso = max(0.0, folga["naoexec"] - folga["limite_ne_total"])
    pend_exec = folga["precisa_executar_pendente"]

    col_d, col_a = st.columns([1, 1.5])

    with col_d:
        render_section("📋 Diagnóstico")

        # ✅ Temas anotados
        tema_excesso: TemaKPI = "vermelho" if excesso > 0 else "verde"
        render_kpi_sm(st, "Excesso de NE", f"{int(excesso):,}",
                      sub="OS além do permitido",
                      tema=tema_excesso)

        render_kpi_sm(st, "Pendentes a Executar",
                      f"{int(np.ceil(pend_exec)):,}",
                      sub=f"Mínimo para meta {sla_meta:.0%}", tema="azul")

        tema_proj: TemaKPI = (
            "vermelho" if cen["fechamento_proj"] > sla_meta else "verde"
        )
        render_kpi_sm(st, "Proj. Base", f"{cen['fechamento_proj']:.2%}",
                      sub=f"c/ {p_base:.0%} de quebra nos pendentes",
                      tema=tema_proj)

        st.markdown("")
        if folga["pend"] > 0:
            tx = 1 - (folga["folga_ne_pendente"] / folga["pend"])
            st.markdown(f"**Taxa mínima de execução:** `{max(0, tx):.1%}`")
            st.progress(min(1.0, max(0.0, float(tx))))

    with col_a:
        render_section("✅ Ações Recomendadas")
        acoes: List[tuple] = []

        if folga["estourado"]:
            acoes.append((
                "🔴 IMEDIATA",
                f"Acionar plantão para recuperar {int(excesso):,} OS não executadas "
                f"acima do limite do SLA.",
                "critico",
            ))
        if pend_exec > 0:
            acoes.append((
                "🟠 ALTA",
                f"Garantir execução de pelo menos {int(np.ceil(pend_exec)):,} "
                f"OS pendentes de {TIPO} para atingir a meta de {sla_meta:.0%}.",
                "alerta",
            ))

        acoes.extend(ACOES_PME)

        # ✅ Markdown **bold**
        for pri, ac, tp in acoes:
            render_insight(f"**{pri}** — {ac}", tipo=tp)

    st.markdown("")
    df_plano = pd.DataFrame([
        {"Segmento": TIPO, "Prioridade": p, "Ação": a} for p, a, _ in acoes
    ])
    if not df_plano.empty:
        st.download_button(
            f"📥 Exportar Plano — {TIPO}",
            Utils.gerar_excel(df_plano, f"Plano_{TIPO[:25]}"),
            f"plano_{TIPO.lower()}.xlsx",
            key="dl_plano_pme",
        )


def _sub_pendentes(df_seg: pd.DataFrame, sla_meta: float) -> None:
    render_section(f"📋 Contratos Pendentes — {TIPO}")

    df_pend = _build_df_pendentes(df_seg)
    total_pend = len(df_pend)

    # ✅ Tema anotado
    tema_total: TemaKPI = "laranja" if total_pend > 0 else "verde"

    m1, m2, m3 = st.columns(3)
    render_kpi(m1, "Total Pendentes", f"{total_pend:,}",
               sub="contratos sem execução",
               tema=tema_total)

    tec_unicos = df_pend["Técnico"].replace("N/D", pd.NA).dropna().nunique()
    render_kpi(m2, "Técnicos Envolvidos", f"{tec_unicos:,}",
               sub="com contrato pendente", tema="azul")

    mon_unicos = df_pend["Monitor"].replace("N/D", pd.NA).dropna().nunique()
    render_kpi(m3, "Monitores Envolvidos", f"{mon_unicos:,}",
               sub="supervisionando pendências", tema="cinza")

    st.markdown("")

    if df_pend.empty:
        render_insight(
            "Nenhum contrato pendente encontrado para os filtros atuais.",
            tipo="ok",
        )
        return

    with st.expander("🔎 Filtros rápidos na tabela de pendentes", expanded=False):
        fc1, fc2 = st.columns(2)
        with fc1:
            opts_tec = ["Todos"] + sorted(
                str(x) for x in df_pend["Técnico"].dropna().unique()
                if str(x) not in {"N/D", "nan"}
            )
            f_tec = st.selectbox("Técnico", opts_tec, key="pend_f_tec")
        with fc2:
            opts_mon = ["Todos"] + sorted(
                str(x) for x in df_pend["Monitor"].dropna().unique()
                if str(x) not in {"N/D", "nan"}
            )
            f_mon = st.selectbox("Monitor", opts_mon, key="pend_f_mon")

    df_view = df_pend.copy()
    if f_tec != "Todos":
        df_view = df_view[df_view["Técnico"] == f_tec]
    if f_mon != "Todos":
        df_view = df_view[df_view["Monitor"] == f_mon]

    st.markdown(f"**Exibindo {len(df_view):,} de {total_pend:,} contratos pendentes**")

    render_dataframe(
        df_view.reset_index(drop=True),
        titulo=f"Contratos Pendentes — {TIPO}",
        icone="📋", height=480,
    )

    st.markdown("")
    render_section("📊 Distribuição das Pendências")

    df_top_mon = (
        df_view[df_view["Monitor"] != "N/D"]
        .groupby("Monitor").size().reset_index(name="Pendentes")
        .sort_values("Pendentes")
    )

    if not df_top_mon.empty:
        fig_mon = go.Figure(go.Bar(
            x=df_top_mon["Pendentes"], y=df_top_mon["Monitor"],
            orientation="h",
            marker=dict(
                color=df_top_mon["Pendentes"],
                colorscale=[
                    [0.0, "#FFF7ED"], [0.2, "#FFEDD5"], [0.4, "#FDBA74"],
                    [0.6, "#FB923C"], [0.8, "#EA580C"], [1.0, "#9A3412"],
                ],
                showscale=True,
                colorbar=dict(title="Qtd.", thickness=12, len=0.6),
            ),
            text=df_top_mon["Pendentes"], textposition="outside",
        ))
        fig_mon.update_layout(
            title="Pendentes por Monitor",
            xaxis_title="Qtd. Contratos Pendentes",
            yaxis=dict(autorange="reversed"),
            height=max(300, len(df_top_mon) * 38),
            margin=dict(l=10, r=30, t=40, b=10),
        )
        st.plotly_chart(fig_mon, use_container_width=True, config={"displayModeBar": False})
    else:
        render_insight("Sem dados de monitor para exibir.", tipo="info")

    st.markdown("")
    col_exp1, col_exp2, _ = st.columns([1, 1, 2])

    with col_exp1:
        st.download_button(
            label="📥 Exportar Pendentes (filtrado)",
            data=Utils.gerar_excel(
                df_view.reset_index(drop=True),
                f"Pendentes_{TIPO[:20]}_filtrado",
            ),
            file_name=(
                f"pendentes_pme_filtrado_"
                f"{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_pend_pme_filtrado",
        )

    with col_exp2:
        st.download_button(
            label="📥 Exportar Pendentes (completo)",
            data=Utils.gerar_excel(
                df_pend.reset_index(drop=True),
                f"Pendentes_{TIPO[:20]}_completo",
            ),
            file_name=(
                f"pendentes_pme_completo_"
                f"{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_pend_pme_completo",
        )


if __name__ == "__main__":
    main()