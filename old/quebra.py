from __future__ import annotations

import csv
import unicodedata
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from streamlit_gsheets import GSheetsConnection

from datetime import datetime
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ────────────────────────────────────────────────────────────────
# 🎨 IMPORTS DO SISTEMA DE DESIGN CORPORATIVO
# ────────────────────────────────────────────────────────────────
from components.componentes import (
    aplicar_estilo,
    render_hero,
    render_kpi as _render_kpi_global,
    render_kpi_sm as _render_kpi_sm_global,
    render_insight as _render_insight_global,
    render_section_header,
    COR_PRIMARIA,
    COR_SECUNDARIA,
    COR_TEXTO,
    COR_TEXTO_3,
    COR_BORDA,
    FONTE_TEXTO,
    FONTE_TITULO,
)

# ====================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(
    page_title="Quebra de Agenda",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ⚠️ Aplica o design system ANTES de qualquer render
aplicar_estilo()

if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None


# ====================================================
# 2. CONFIGURAÇÕES DE DOMÍNIO
# ====================================================
class Config:
    SLA_QUEBRA_MAXIMA: float = 0.20
    SLA_PME: float = 0.20
    SLA_MIGRACAO: float = 0.25
    URL_ATIVOS: str = (
        "https://docs.google.com/spreadsheets/d/"
        "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    )
    CONTRATO_VALORES_VAZIOS = {"", "NAN", "NONE", "N/A", "NA", "-", "0", "NULL"}
    STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]
    CORES_STATUS = {
        "Executada": "#10B981",
        "Não Executada": "#EF4444",
        "Pendente": "#94A3B8",
    }
    COL_REGIAO = "REGIÃO"
    REGIOES_PRINCIPAIS = ["LESTE", "GRU", "ABCDM"]

    SEGMENTOS_CONFIG: Dict[str, Dict] = {
        "PME": {
            "icone": "🏢",
            "cor": "#7C3AED",
            "cor_clara": "#EDE9FE",
            "sla": 0.20,
            "tema_kpi": "roxo",
            "descricao": "Pequenas e Médias Empresas",
        },
        "Migração": {
            "icone": "🔄",
            "cor": "#0369A1",
            "cor_clara": "#E0F2FE",
            "sla": 0.25,
            "tema_kpi": "azul",
            "descricao": "Mudança de Pacote + GPON",
        },
    }


# ====================================================
# 3. TEMAS LOCAIS COMPLEMENTARES
# ────────────────────────────────────────────────────
# ⚠️ Estes temas adicionam variantes específicas do domínio
# (amarelo, roxo, indigo, teal, escuro) que o design system
# global não expõe diretamente. São usados apenas em
# render_kpi_local() / render_kpi_sm_local() como fallback.
# ====================================================
TEMAS_CARD_EXTRA: Dict[str, Dict[str, str]] = {
    "amarelo": {"fundo": "#FEF9C3", "texto": "#854D0E", "borda": "#EAB308", "titulo": "#A16207"},
    "roxo":    {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#6B21A8"},
    "escuro":  {"fundo": "#1E293B", "texto": "#FFFFFF", "borda": "#475569", "titulo": "#E2E8F0"},
    "indigo":  {"fundo": "#EEF2FF", "texto": "#3730A3", "borda": "#6366F1", "titulo": "#312E81"},
    "teal":    {"fundo": "#F0FDFA", "texto": "#0F766E", "borda": "#14B8A6", "titulo": "#0D9488"},
}

# Mapeia temas locais → temas do design system global
_MAPA_TEMA_GLOBAL: Dict[str, str] = {
    "azul": "azul",
    "verde": "verde",
    "vermelho": "vermelho",
    "laranja": "laranja",
    "cinza": "cinza",
    # variantes locais → aproximações no global
    "roxo": "azul",
    "amarelo": "laranja",
    "indigo": "azul",
    "teal": "verde",
    "escuro": "cinza",
}

CORES_REGIAO: Dict[str, Dict[str, str]] = {
    "LESTE":  {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU":    {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM":  {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

RENOMEAR_COLUNAS: Dict[str, str] = {
    "TÉCNICO": "Técnico",
    "MONITOR": "Monitor",
    "REGIÃO": "Região",
    "Executada": "Executadas",
    "Não Executada": "Não Exec.",
    "Pendente": "Pendentes",
    "Alocado": "Alocado",
    "Considerado": "Considerado",
    "Quebra Atual": "Quebra Atual",
    "Fechamento Otimista": "Fech. Otimista",
    "Fechamento Base": "Fech. Base",
    "Fechamento Pessimista": "Fech. Pessimista",
}

COLUNAS_INTEIRAS = [
    "Executada", "Não Executada", "Pendente",
    "Alocado", "Considerado", "Qtd Não Executadas",
    "Volume", "Não Executadas",
]


# ====================================================
# 4. WRAPPERS DE KPI (usam global quando possível,
#    fallback para temas extras)
# ====================================================
def render_kpi(col, label: str, value: str, sub: str = "", tema: str = "azul") -> None:
    """
    Wrapper de KPI que roteia entre o design system global (5 temas
    corporativos) e um fallback local para variantes extras (roxo,
    amarelo, indigo, teal, escuro).
    """
    if tema in TEMAS_CARD_EXTRA:
        t = TEMAS_CARD_EXTRA[tema]
        col.markdown(
            f"""
<div style="background:{t['fundo']};border-left:4px solid {t['borda']};
     border-radius:10px;padding:20px 24px;box-shadow:0 4px 12px rgba(0,0,0,0.08);
     transition:transform 0.2s ease;">
    <div style="font-family:{FONTE_TEXTO};font-size:11px;font-weight:700;
         color:{t['titulo']};text-transform:uppercase;letter-spacing:1.2px;
         margin-bottom:6px;">{label}</div>
    <div style="font-family:{FONTE_TITULO};font-size:28px;font-weight:800;
         color:{t['texto']};line-height:1;font-variant-numeric:tabular-nums;">{value}</div>
    <div style="font-family:{FONTE_TEXTO};font-size:12px;color:{t['titulo']};
         margin-top:6px;font-weight:500;">{sub}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        tema_global = _MAPA_TEMA_GLOBAL.get(tema, "azul")
        _render_kpi_global(col, label, value, sub, tema_global)  # type: ignore[arg-type]


def render_kpi_sm(col, label: str, value: str, sub: str = "", tema: str = "azul") -> None:
    """Versão compacta de render_kpi."""
    if tema in TEMAS_CARD_EXTRA:
        t = TEMAS_CARD_EXTRA[tema]
        col.markdown(
            f"""
<div style="background:{t['fundo']};border-left:3px solid {t['borda']};
     border-radius:6px;padding:12px 16px;margin-bottom:8px;
     box-shadow:0 1px 4px rgba(0,0,0,0.06);">
    <div style="font-family:{FONTE_TEXTO};font-size:10px;color:{t['titulo']};
         text-transform:uppercase;letter-spacing:1px;font-weight:700;">{label}</div>
    <div style="font-family:{FONTE_TITULO};font-size:20px;color:{t['texto']};
         font-weight:800;line-height:1.2;margin-top:4px;
         font-variant-numeric:tabular-nums;">{value}</div>
    <div style="font-family:{FONTE_TEXTO};font-size:11px;color:{t['titulo']};
         margin-top:2px;">{sub}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        tema_global = _MAPA_TEMA_GLOBAL.get(tema, "azul")
        _render_kpi_sm_global(col, label, value, sub, tema_global)  # type: ignore[arg-type]


def render_insight(texto: str, tipo: str = "info") -> None:
    """
    Wrapper que aceita HTML embutido (ex: <strong>) já usado no código
    e delega ao render_insight global (que também processa **markdown**).
    """
    _render_insight_global(texto, tipo)  # type: ignore[arg-type]


def render_section(titulo: str) -> None:
    """
    Header de seção estilo domínio. Extrai emoji inicial se houver,
    para usar como icon do render_section_header global.
    """
    partes = titulo.strip().split(" ", 1)
    if len(partes) == 2 and not partes[0].isalnum():
        icon, title = partes[0], partes[1]
    else:
        icon, title = "📊", titulo
    render_section_header(icon, title)


# ====================================================
# 5. CSS COMPLEMENTAR (apenas classes de domínio)
# ────────────────────────────────────────────────────
# ⚠️ O CSS base (fontes, hero, KPIs, seções) já vem do
# aplicar_estilo() do design system. Aqui só adicionamos
# classes específicas do domínio de quebra de agenda.
# ====================================================
def aplicar_estilo_dominio() -> None:
    st.markdown(
        """
<style>
/* ── Segmento Header (PME / Migração) ── */
.segmento-header {
    padding: 1rem 1.5rem; border-radius: 0.75rem;
    margin-bottom: 1rem; display: flex; align-items: center; gap: 1rem;
    border-left: 6px solid;
}
.segmento-titulo { font-size: 1.3rem; font-weight: 800; }
.segmento-desc   { font-size: 0.82rem; opacity: 0.75; }
.segmento-sla {
    margin-left: auto; font-size: 0.78rem; font-weight: 700;
    padding: 0.3rem 0.8rem; border-radius: 999px;
}

/* ── Alertas de SLA ── */
.alerta-sla-critico, .alerta-sla-ok, .alerta-sla-atencao {
    border-radius: 0.75rem; padding: 1rem 1.5rem; color: white;
    margin: 0.5rem 0; display: flex; align-items: center; gap: 0.8rem;
}
.alerta-sla-critico  { background: linear-gradient(135deg, #450A0A, #7F1D1D); border: 1px solid #EF4444; }
.alerta-sla-ok       { background: linear-gradient(135deg, #052E16, #14532D); border: 1px solid #22C55E; }
.alerta-sla-atencao  { background: linear-gradient(135deg, #422006, #7C2D12); border: 1px solid #F97316; }

/* ── Resultado Base ── */
.resultado-base {
    background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
    padding: 1rem 1.5rem; border-radius: 0.75rem; margin-bottom: 1.5rem;
    display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem;
}
.resultado-base-label {
    color: #94A3B8; font-size: 0.8rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
}
.resultado-base-regiao {
    padding: 0.3rem 0.9rem; border-radius: 999px;
    font-size: 0.82rem; font-weight: 700; border: 2px solid;
}
.resultado-base-count {
    color: #64748B; font-size: 0.72rem;
    margin-left: auto; font-weight: 600;
}

/* ── Wrapper de tabelas estilizadas ── */
.styled-table-wrapper {
    background: #FFFFFF; border-radius: 0.75rem;
    padding: 1rem 1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    margin-bottom: 0.5rem;
}
.styled-table-title {
    font-size: 1rem; font-weight: 700; color: #0F172A;
    margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.5rem;
}
.styled-table-badge {
    font-size: 0.68rem; background: #E0F2FE; color: #0369A1;
    padding: 0.15rem 0.5rem; border-radius: 999px; font-weight: 600;
}
div[data-testid="stDataFrame"] > div { border-radius: 0.5rem; overflow: hidden; }
</style>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# 6. COMPONENTES DE DOMÍNIO
# ====================================================
def render_segmento_header(tipo: str, sla_atual: float, sla_meta: float) -> None:
    cfg = Config.SEGMENTOS_CONFIG.get(tipo, {})
    icone = cfg.get("icone", "📋")
    cor = cfg.get("cor", "#334155")
    cor_clara = cfg.get("cor_clara", "#F8FAFC")
    desc = cfg.get("descricao", tipo)

    status_sla = "✅ Dentro do SLA" if sla_atual <= sla_meta else "❌ Fora do SLA"
    cor_sla_bg = "#DCFCE7" if sla_atual <= sla_meta else "#FEE2E2"
    cor_sla_txt = "#166534" if sla_atual <= sla_meta else "#991B1B"

    st.markdown(
        f"""
<div class="segmento-header" style="background:{cor_clara};border-left-color:{cor};">
    <span style="font-size:2rem">{icone}</span>
    <div>
        <div class="segmento-titulo" style="color:{cor}">{tipo}</div>
        <div class="segmento-desc" style="color:{cor}">{desc}</div>
    </div>
    <div class="segmento-sla" style="background:{cor_sla_bg};color:{cor_sla_txt}">
        {status_sla} &nbsp;|&nbsp; Quebra: {sla_atual:.2%} &nbsp;|&nbsp; Meta: {sla_meta:.2%}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_alerta_sla(quebra: float, meta: float, tipo: str) -> None:
    excesso = quebra - meta
    if quebra > meta * 1.2:
        classe, icone = "alerta-sla-critico", "🚨"
        msg = (
            f"<strong>CRÍTICO:</strong> {tipo} está {excesso:.2%} acima da meta. "
            f"Acione plano de contingência imediato."
        )
    elif quebra > meta:
        classe, icone = "alerta-sla-atencao", "⚠️"
        msg = (
            f"<strong>ATENÇÃO:</strong> {tipo} ultrapassou a meta em {excesso:.2%}. "
            f"Reforce a execução de pendentes."
        )
    else:
        classe, icone = "alerta-sla-ok", "✅"
        folga = meta - quebra
        msg = (
            f"<strong>SLA OK:</strong> {tipo} com folga de {folga:.2%}. "
            f"Manter ritmo de execução."
        )
    st.markdown(
        f'<div class="{classe}"><span style="font-size:1.5rem">{icone}</span>'
        f"<span>{msg}</span></div>",
        unsafe_allow_html=True,
    )


def render_resultado_base(regioes: List[str], total: int) -> None:
    badges = ""
    for reg in sorted(regioes):
        c = CORES_REGIAO.get(reg, CORES_REGIAO["OUTRAS"])
        badges += (
            f'<span class="resultado-base-regiao" '
            f'style="background:{c["bg"]};color:{c["text"]};border-color:{c["border"]}">'
            f"{reg}</span>"
        )
    st.markdown(
        f"""
<div class="resultado-base">
    <span class="resultado-base-label">📋 Resultado da Base:</span>
    {badges}
    <span class="resultado-base-count">{total:,} registros</span>
</div>
        """,
        unsafe_allow_html=True,
    )


def resolver_renomeacao(df: pd.DataFrame, mapa: Dict[str, str]) -> Dict[str, str]:
    nomes_existentes = set(df.columns)
    nomes_ja_usados: set[str] = set()
    resultado: Dict[str, str] = {}
    for col_original in df.columns:
        if col_original not in mapa:
            continue
        novo_nome = mapa[col_original]
        if novo_nome == col_original or novo_nome in nomes_existentes or novo_nome in nomes_ja_usados:
            continue
        resultado[col_original] = novo_nome
        nomes_ja_usados.add(novo_nome)
    return resultado


def render_dataframe(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    badge: str = "",
    fmt: Optional[Dict[str, Any]] = None,
    color_col: Optional[str] = None,
    color_meta: Optional[float] = None,
    color_invertido: bool = True,
    height: int | Literal["auto", "stretch", "content"] = "auto",
) -> None:
    """
    DataFrame estilizado com heatmap condicional.
    ⚠️ Componente específico do domínio — mantém styler avançado
    (destaque de coluna 'Quebra Atual' em preto, gradiente por meta).
    """
    badge_text = badge or f"{len(df)} registros"
    st.markdown(
        f"""
<div class="styled-table-wrapper">
    <div class="styled-table-title">
        <span>{icone}</span><span>{titulo}</span>
        <span class="styled-table-badge">{badge_text}</span>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    df_display = df.copy()
    mapa_seguro = resolver_renomeacao(df_display, RENOMEAR_COLUNAS)
    df_display = df_display.rename(columns=mapa_seguro)

    if fmt:
        fmt = {mapa_seguro.get(k, k): v for k, v in fmt.items()}
    if color_col:
        color_col = mapa_seguro.get(color_col, color_col)

    col_quebra_display = mapa_seguro.get("Quebra Atual", "Quebra Atual")

    for col_orig in COLUNAS_INTEIRAS:
        col_disp = mapa_seguro.get(col_orig, col_orig)
        if col_disp in df_display.columns:
            df_display[col_disp] = (
                pd.to_numeric(df_display[col_disp], errors="coerce")
                .fillna(0).astype(int)
            )

    styler = df_display.style
    if fmt:
        styler = styler.format(fmt)  # type: ignore[arg-type]

    if color_col and color_col in df_display.columns and color_meta is not None:
        colunas_condicionais = [c for c in [color_col] if c != col_quebra_display]
        if colunas_condicionais:
            def _cor(val):
                try:
                    v = float(val)
                except (ValueError, TypeError):
                    return ""
                if color_invertido:
                    if v > color_meta:
                        return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"
                    if v > color_meta * 0.85:
                        return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
                    return "background-color:#DCFCE7;color:#166534;font-weight:600;"
                else:
                    if v >= color_meta:
                        return "background-color:#DCFCE7;color:#166534;font-weight:600;"
                    if v >= color_meta * 0.85:
                        return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
                    return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"

            styler = styler.map(_cor, subset=pd.Index(colunas_condicionais))

    if col_quebra_display in df_display.columns:
        styler = styler.map(
            lambda val: (
                "background-color:#1E293B;color:#FFFFFF;font-weight:600;"
                if not pd.isna(val) and str(val).strip() != ""
                else ""
            ),
            subset=pd.Index([col_quebra_display]),
        )

    styler = styler.set_table_styles([
        {"selector": "th", "props": [
            ("background-color", "#0F172A"), ("color", "#FFFFFF"),
            ("font-size", "0.78rem"), ("font-weight", "700"),
            ("text-transform", "uppercase"), ("letter-spacing", "0.03em"),
            ("padding", "0.6rem 0.8rem"), ("border", "none"),
        ]},
        {"selector": "td", "props": [
            ("font-size", "0.82rem"), ("padding", "0.5rem 0.8rem"),
            ("border-bottom", "1px solid #F1F5F9"),
        ]},
        {"selector": "tr:hover td", "props": [("background-color", "#F8FAFC")]},
    ])

    st.dataframe(styler, use_container_width=True, hide_index=True, height=height)


# ====================================================
# 7. UTILITÁRIOS (INTOCADOS)
# ====================================================
class Utils:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras: list) -> Optional[str]:
        if df is None or df.empty:
            return None

        def norm(t):
            t = str(t).strip().upper()
            t = unicodedata.normalize("NFKD", t).encode("ASCII", "ignore").decode()
            return t.replace(".", "").replace("_", "").replace("  ", " ")

        cols = {norm(c): c for c in df.columns}
        for p in palavras:
            pn = norm(p)
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
            for i in range(1, len(df.columns) + 1):
                ws.column_dimensions[get_column_letter(i)].width = 20
        return out.getvalue()

    @staticmethod
    def calcular_delta(atual: float, anterior: float) -> Tuple[float, str]:
        if anterior == 0:
            return 0.0, "→"
        delta = atual - anterior
        simbolo = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        return delta, simbolo

    @staticmethod
    def top_n_por_quebra(df: pd.DataFrame, grupo: str, n: int = 5) -> pd.DataFrame:
        if df.empty or grupo not in df.columns:
            return pd.DataFrame()
        res = (
            df[df["Status Contrato"] == "Não Executada"]
            .groupby(grupo)["TOTAL DE TAREFAS"]
            .sum().nlargest(n).reset_index()
        )
        res.columns = [grupo, "Não Executadas"]
        return res


# ====================================================
# 8. DATA LOADER (INTOCADO)
# ====================================================
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
                    sep = csv.Sniffer().sniff(amostra).delimiter
                except Exception:
                    sep = ";"
                return pd.read_csv(bio, sep=sep, encoding="utf-8", dtype=str, engine="python")
            return pd.read_excel(bio, engine="openpyxl", dtype=str)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_gsheets() -> pd.DataFrame:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            raw = conn.read(spreadsheet=Config.URL_ATIVOS)
            if raw is None or raw.empty:
                return pd.DataFrame()

            raw.columns = raw.columns.astype(str).str.strip().str.upper()
            rename = {}
            if c := Utils.buscar_coluna(raw, ["LOGIN", "ID", "MATRÍCULA"]):
                rename[c] = "LOGIN"
            if c := Utils.buscar_coluna(raw, ["TÉCNICO", "NOME"]):
                rename[c] = "TÉCNICO"
            if c := Utils.buscar_coluna(raw, ["MONITOR", "GESTOR"]):
                rename[c] = "MONITOR"

            raw = raw.rename(columns=rename)
            raw = raw[[c for c in ["LOGIN", "TÉCNICO", "MONITOR"] if c in raw.columns]].copy()
            if "LOGIN" in raw.columns:
                raw["LOGIN"] = (
                    raw["LOGIN"].astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip().str.upper()
                )
                raw = raw.drop_duplicates(subset=["LOGIN"], keep="last")
            return raw
        except Exception as e:
            st.warning(f"GSheets falhou ({e}). Usando dados locais.")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def preparar_base(df: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.upper()

        removidos_suspensos = 0
        removidos_contrato = 0

        col_atv = Utils.buscar_coluna(df, ["STATUS DA ATIVIDADE"])
        if col_atv:
            susp = df[col_atv].fillna("").astype(str).str.upper().str.contains("SUSP", na=False)
            removidos_suspensos = int(susp.sum())
            df = df[~susp].copy()

        col_tot = Utils.buscar_coluna(df, ["TOTAL DE TAREFAS"])
        df["TOTAL DE TAREFAS"] = (
            pd.to_numeric(df[col_tot].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
            if col_tot else 0
        )

        col_con = Utils.buscar_coluna(df, ["CONTRATO", "Nº CONTRATO"])
        if col_con:
            norm = df[col_con].astype(str).str.strip().str.upper()
            valido = ~norm.isin(Config.CONTRATO_VALORES_VAZIOS)
            removidos_contrato = int((~valido).sum())
            df = df[valido].copy()

        col_login = Utils.buscar_coluna(df, ["LOGIN", "LOGIN DO TÉCNICO", "USUÁRIO", "MATRÍCULA"])
        gs_valido = isinstance(df_gs, pd.DataFrame) and not df_gs.empty
        if col_login and gs_valido and "LOGIN" in df_gs.columns:
            df[col_login] = (
                df[col_login].astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.strip().str.upper()
            )
            for c in ["TÉCNICO", "MONITOR"]:
                if c in df.columns:
                    df = df.drop(columns=[c])
            df = df.merge(df_gs, left_on=col_login, right_on="LOGIN", how="left")

        df["TÉCNICO"] = df.get("TÉCNICO", pd.Series("NÃO MAPEADO", index=df.index)).fillna("NÃO MAPEADO")
        df["MONITOR"] = df.get("MONITOR", pd.Series("SEM MONITOR", index=df.index)).fillna("SEM MONITOR")

        col_cid = Utils.buscar_coluna(df, ["CIDADE", "LOCALIDADE"])
        if col_cid:
            cidade = (
                df[col_cid].fillna("").astype(str).str.strip().str.upper()
                .apply(lambda v: unicodedata.normalize("NFKD", v).encode("ASCII", "ignore").decode())
            )
        else:
            cidade = pd.Series("", index=df.index)

        df["REGIÃO"] = np.select(
            [
                cidade.isin(["SAO PAULO"]),
                cidade.isin(["GUARULHOS", "ARUJA", "MOGI DAS CRUZES", "SUZANO",
                             "ITAQUAQUECETUBA", "FERRAZ DE VASCONCELOS", "POA"]),
                cidade.isin(["SANTO ANDRE", "SAO BERNARDO DO CAMPO", "SAO CAETANO DO SUL",
                             "DIADEMA", "MAUA", "RIBEIRAO PIRES", "RIO GRANDE DA SERRA"]),
            ],
            ["LESTE", "GRU", "ABCDM"],
            default="OUTRAS",
        )

        col_status = Utils.buscar_coluna(df, ["STATUS DA O.S 1", "STATUS OS 1"])
        df["Status Contrato"] = (
            Utils.classificar_status(df[col_status]) if col_status else "Pendente"
        )

        col_tipo = Utils.buscar_coluna(df, ["TIPO O.S 1"])
        col_hab = Utils.buscar_coluna(df, ["HABILIDADE DE TRABALHO", "HABILIDADE"])

        tipo_upper = (
            df[col_tipo].fillna("").astype(str).str.strip().str.upper()
            .apply(lambda v: unicodedata.normalize("NFKD", v).encode("ASCII", "ignore").decode())
            if col_tipo else pd.Series("", index=df.index, dtype=str)
        )
        hab_upper = (
            df[col_hab].fillna("").astype(str).str.upper()
            if col_hab else pd.Series("", index=df.index, dtype=str)
        )

        flag_gpon = hab_upper.str.contains(r"PON", regex=True, na=False)
        flag_nd = tipo_upper.str.contains("ADESAO", na=False)
        flag_migracao = tipo_upper.str.contains("MUDANCA DE PACOTE", na=False) & flag_gpon
        flag_pme = flag_nd & hab_upper.str.contains("PME", na=False)

        df["TIPO_SERVICO"] = pd.Series(
            np.select(
                condlist=[flag_pme, flag_migracao, flag_gpon, flag_nd],
                choicelist=["PME", "Migração", "GPON", "Novos Domicílios"],
                default="Outros",
            ),
            index=df.index, dtype=str,
        )

        if st.checkbox("🔍 Debug PME", value=False):
            col1, col2 = st.columns(2)
            with col1:
                st.caption("📋 Valores únicos — TIPO O.S (normalizado)")
                st.dataframe(
                    pd.Series(tipo_upper.unique()).sort_values().reset_index(drop=True),
                    use_container_width=True,
                )
            with col2:
                st.caption("📋 Valores únicos — HABILIDADE (normalizado)")
                st.dataframe(
                    pd.Series(hab_upper.unique()).sort_values().reset_index(drop=True),
                    use_container_width=True,
                )

            st.caption("🔎 Flags por linha (amostra 20)")
            df_debug = pd.DataFrame({
                "TIPO_ORIG":     df[col_tipo].fillna("") if col_tipo else "",
                "HAB_ORIG":      df[col_hab].fillna("")  if col_hab  else "",
                "tipo_upper":    tipo_upper,
                "hab_upper":     hab_upper,
                "flag_nd":       flag_nd,
                "flag_pme":      flag_pme,
                "flag_gpon":     flag_gpon,
                "flag_migracao": flag_migracao,
                "TIPO_SERVICO":  df["TIPO_SERVICO"],
            })
            st.dataframe(df_debug.head(20), use_container_width=True)

            st.caption("📊 Contagem por TIPO_SERVICO")
            st.dataframe(
                df["TIPO_SERVICO"].value_counts().reset_index()
                .rename(columns={"index": "Tipo", "TIPO_SERVICO": "Qtd"}),
                use_container_width=True,
            )

            if (df["TIPO_SERVICO"] == "PME").any():
                st.success(f"✅ Encontrados {(df['TIPO_SERVICO'] == 'PME').sum()} registros PME")
                df_pme_sample = df[df["TIPO_SERVICO"] == "PME"][
                    [col_tipo or "TIPO", col_hab or "HABILIDADE", "TIPO_SERVICO"]
                ].head(5)
                st.caption("Amostra de registros PME:")
                st.dataframe(df_pme_sample, use_container_width=True)
            else:
                st.warning("❌ Nenhum registro classificado como PME encontrado")
                if flag_nd.sum() > 0:
                    st.info(f"→ Existem {flag_nd.sum()} registros com flag_nd=True (ADESAO)")
                    st.info(f"→ Desses, {flag_pme.sum()} também têm habilidade PME")

        col_cod = Utils.buscar_coluna(df, ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "CÓDIGO DE BAIXA 1"])
        df["_COL_BAIXA"] = df[col_cod].astype(str) if col_cod else ""

        col_data = Utils.buscar_coluna(df, ["DATA", "DT AGENDA", "DATA AGENDA"])
        if col_data:
            df["_DATA_AGENDA"] = pd.to_datetime(df[col_data], errors="coerce", dayfirst=True)
        else:
            df["_DATA_AGENDA"] = pd.NaT

        df.attrs["diagnostico"] = {
            "suspensos": removidos_suspensos,
            "contrato_vazio": removidos_contrato,
            "col_status_encontrada": bool(col_status),
            "col_baixa": col_cod or "",
        }
        return df


# ====================================================
# 9. MOTOR DE CÁLCULO (INTOCADO)
# ====================================================
class Motor:
    @staticmethod
    def quebra_atual(df: pd.DataFrame) -> Tuple[float, float]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return 0.0, 0.0
        exe = float(df.loc[df["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
        nex = float(df.loc[df["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
        cons = exe + nex
        return cons, (nex / cons) if cons > 0 else 0.0

    @staticmethod
    def projetar(df: pd.DataFrame, p: float) -> Dict[str, float]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return dict(alocado=0, exec=0, naoexec=0, pend=0, quebra_atual=0,
                        fechamento_proj=0, naoexec_proj=0)
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = float(df.loc[df["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
        nex = float(df.loc[df["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
        pen = max(0.0, aloc - exe - nex)
        _, qa = Motor.quebra_atual(df)
        nex_proj = nex + (pen * p)
        return dict(
            alocado=aloc, exec=exe, naoexec=nex, pend=pen,
            quebra_atual=qa,
            fechamento_proj=(nex_proj / aloc) if aloc > 0 else 0,
            naoexec_proj=nex_proj,
        )

    @staticmethod
    def folga_sla(df: pd.DataFrame, sla: float) -> Dict[str, Any]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return dict(alocado=0, exec=0, naoexec=0, pend=0, limite_ne_total=0,
                        folga_ne_pendente=0, folga_pct_pendente=0,
                        precisa_executar_pendente=0, estourado=False)
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = float(df.loc[df["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
        nex = float(df.loc[df["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
        pen = max(0.0, aloc - exe - nex)
        limite = sla * aloc
        folga_tot = limite - nex
        folga_pen = max(0.0, min(pen, folga_tot))
        return dict(
            alocado=aloc, exec=exe, naoexec=nex, pend=pen,
            limite_ne_total=limite,
            folga_ne_pendente=folga_pen,
            folga_pct_pendente=(folga_pen / pen) if pen > 0 else 0,
            precisa_executar_pendente=max(0.0, pen - folga_pen),
            estourado=folga_tot < 0,
        )

    @staticmethod
    def tabela_cenarios(
        df: pd.DataFrame, grupo: str,
        p_ot: float, p_base: float, p_pess: float,
        min_aloc: float = 5,
    ) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty or grupo not in df.columns:
            return pd.DataFrame()
        pv = pd.pivot_table(
            df, index=grupo, columns="Status Contrato",
            values="TOTAL DE TAREFAS", aggfunc="sum", fill_value=0,
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
                (out["Não Executada"] + out["Pendente"] * p) / out["Alocado"], 0,
            )
        return out[out["Alocado"] >= min_aloc].sort_values("Fechamento Base", ascending=False)

    @staticmethod
    def causa_raiz_segmento(df: pd.DataFrame, tipo: str, col_baixa: str, top_n: int = 8) -> pd.DataFrame:
        df_seg = df[df["TIPO_SERVICO"] == tipo].copy()
        if df_seg.empty or col_baixa not in df_seg.columns:
            return pd.DataFrame()
        df_nex = df_seg[df_seg["Status Contrato"] == "Não Executada"].copy()
        if df_nex.empty:
            return pd.DataFrame()
        df_nex["_baixa_norm"] = (
            df_nex[col_baixa].fillna("Sem Registro").astype(str)
            .str.strip().str.upper()
            .replace({"NAN": "Sem Registro", "": "Sem Registro"})
        )
        resumo = (
            df_nex.groupby("_baixa_norm")["TOTAL DE TAREFAS"]
            .sum().nlargest(top_n).reset_index()
        )
        resumo.columns = ["Motivo de Baixa", "Volume"]
        total = resumo["Volume"].sum()
        resumo["% do Total"] = resumo["Volume"] / total if total > 0 else 0
        resumo["Acumulado"] = resumo["% do Total"].cumsum()
        return resumo

    @staticmethod
    def evolucao_temporal(df: pd.DataFrame, tipo: str) -> pd.DataFrame:
        df_seg = df[(df["TIPO_SERVICO"] == tipo) & (df["_DATA_AGENDA"].notna())].copy()
        if df_seg.empty:
            return pd.DataFrame()
        df_seg["_dia"] = df_seg["_DATA_AGENDA"].dt.date
        pv = (
            df_seg.groupby(["_dia", "Status Contrato"])["TOTAL DE TAREFAS"]
            .sum().unstack(fill_value=0)
        )
        for col in ["Executada", "Não Executada", "Pendente"]:
            if col not in pv.columns:
                pv[col] = 0
        pv["Considerado"] = pv["Executada"] + pv["Não Executada"]
        pv["Quebra"] = np.where(pv["Considerado"] > 0, pv["Não Executada"] / pv["Considerado"], 0)
        return pv.reset_index().rename(columns={"_dia": "Data"})

    @staticmethod
    def comparativo_regioes(df: pd.DataFrame, tipo: str) -> pd.DataFrame:
        df_seg = df[df["TIPO_SERVICO"] == tipo].copy()
        if df_seg.empty:
            return pd.DataFrame()
        pv = pd.pivot_table(
            df_seg, index="REGIÃO", columns="Status Contrato",
            values="TOTAL DE TAREFAS", aggfunc="sum", fill_value=0,
        )
        for c in ["Executada", "Não Executada", "Pendente"]:
            if c not in pv.columns:
                pv[c] = 0
        pv = pv.reset_index()
        pv["Alocado"] = pv["Executada"] + pv["Não Executada"] + pv["Pendente"]
        pv["Considerado"] = pv["Executada"] + pv["Não Executada"]
        pv["Quebra"] = np.where(pv["Considerado"] > 0, pv["Não Executada"] / pv["Considerado"], 0)
        return pv.sort_values("Quebra", ascending=False)

    @staticmethod
    def tecnicos_criticos(
        df: pd.DataFrame, tipo: str, p_base: float,
        min_aloc: float = 3, top_n: int = 10,
    ) -> pd.DataFrame:
        df_seg = df[df["TIPO_SERVICO"] == tipo].copy()
        return Motor.tabela_cenarios(df_seg, "TÉCNICO", 0.1, p_base, 0.6, min_aloc).head(top_n)


# ====================================================
# 10. RELATÓRIO PDF (INTOCADO)
# ====================================================
class RelatorioPDF:
    @staticmethod
    def _fmt(v: Any, col: str = "") -> str:
        if pd.isna(v):
            return "-"
        col_u = str(col).upper()
        if isinstance(v, (float, np.floating)):
            if any(x in col_u for x in ["QUEBRA", "FECHAMENTO", "META", "%", "PERCENTUAL"]):
                return f"{v:.2%}"
            if float(v).is_integer():
                return f"{int(v):,}".replace(",", ".")
            return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if isinstance(v, (int, np.integer)):
            return f"{v:,}".replace(",", ".")
        return escape(str(v))

    @staticmethod
    def _tab(df: pd.DataFrame, limite: Optional[int] = None,
             larguras: Optional[List[float]] = None) -> Table:
        if df is None or df.empty:
            tab = Table([["Sem dados disponíveis"]], colWidths=[26.5 * cm])
            tab.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#334155")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            return tab

        base = df.copy()
        if limite is not None:
            base = base.head(limite)
        dados = [list(base.columns)]
        for _, ln in base.iterrows():
            dados.append([RelatorioPDF._fmt(ln[c], c) for c in base.columns])

        col_widths = (
            [w * cm for w in larguras] if larguras is not None
            else [(26.5 * cm) / max(len(base.columns), 1)] * len(base.columns)
        )

        tab = Table(dados, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
        tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, 0), 7),
            ("FONTSIZE", (0, 1), (-1, -1), 6.5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tab

    @staticmethod
    def _rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(1.2 * cm, 0.7 * cm, "Gestão de Quebra de Agenda")
        canvas.drawRightString(28.3 * cm, 0.7 * cm, f"Página {doc.page}")
        canvas.restoreState()

    @staticmethod
    def _styles():
        s = getSampleStyleSheet()
        s.add(ParagraphStyle(
            name="TituloExec", parent=s["Title"],
            fontName="Helvetica-Bold", fontSize=22, leading=26,
            textColor=colors.HexColor("#0F172A"),
            alignment=TA_CENTER, spaceAfter=6,
        ))
        s.add(ParagraphStyle(
            name="SubExec", parent=s["Normal"],
            fontName="Helvetica", fontSize=10, leading=14,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER, spaceAfter=18,
        ))
        s.add(ParagraphStyle(
            name="TextoPDF", parent=s["Normal"],
            fontName="Helvetica", fontSize=8.5, leading=11,
            textColor=colors.HexColor("#334155"),
            alignment=TA_LEFT,
        ))
        s["Heading2"].fontName = "Helvetica-Bold"
        s["Heading2"].fontSize = 13
        s["Heading2"].leading = 17
        s["Heading2"].textColor = colors.HexColor("#1E3A5F")
        return s

    @staticmethod
    @st.cache_data(show_spinner=False)
    def gerar_segmento(
        df: pd.DataFrame, tipo: str, sla_meta: float,
        p_ot: float, p_base: float, p_pess: float,
        min_aloc: float = 3, top_n: int = 10,
    ) -> bytes:
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            rightMargin=1.0 * cm, leftMargin=1.0 * cm,
            topMargin=1.0 * cm, bottomMargin=1.2 * cm,
        )
        s = RelatorioPDF._styles()
        df_seg = df[df["TIPO_SERVICO"] == tipo].copy()

        elementos: List[Any] = [
            Paragraph(f"RELATÓRIO EXECUTIVO<br/>{escape(tipo.upper())} — QUEBRA DE AGENDA", s["TituloExec"]),
            Paragraph(
                f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
                f"Registros analisados: {len(df_seg):,}".replace(",", "."),
                s["SubExec"],
            ),
        ]

        if df_seg.empty:
            elementos.append(Paragraph(
                f"Não há registros de {escape(tipo)} para os filtros aplicados.", s["TextoPDF"]))
            doc.build(elementos, onFirstPage=RelatorioPDF._rodape, onLaterPages=RelatorioPDF._rodape)
            buf.seek(0)
            return buf.getvalue()

        m = Motor.projetar(df_seg, p_base)
        folga = Motor.folga_sla(df_seg, sla_meta)

        resumo = pd.DataFrame([{
            "Alocado": m["alocado"], "Executadas": m["exec"], "Não Exec.": m["naoexec"],
            "Pendentes": m["pend"], "Quebra Atual": m["quebra_atual"],
            "Proj. Base": m["fechamento_proj"], "Meta": sla_meta,
            "Exec. Mínima": folga["precisa_executar_pendente"],
        }])
        elementos.append(Paragraph("1. Resumo Executivo", s["Heading2"]))
        elementos.append(RelatorioPDF._tab(resumo, larguras=[3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 2.6, 3.6]))
        elementos.append(Spacer(1, 0.25 * cm))

        if m["fechamento_proj"] > sla_meta:
            diagnostico = (
                f"O cenário base projeta fechamento de {m['fechamento_proj']:.2%}, "
                f"{(m['fechamento_proj'] - sla_meta):.2%} acima da meta de {sla_meta:.2%}. "
                f"Será necessário executar ao menos "
                f"{int(np.ceil(folga['precisa_executar_pendente'])):,} OS pendentes "
                f"para retorno ao limite."
            )
        else:
            diagnostico = (
                f"O cenário base projeta fechamento de {m['fechamento_proj']:.2%}, "
                f"com folga de {(sla_meta - m['fechamento_proj']):.2%} em relação à meta "
                f"de {sla_meta:.2%}. A operação ainda suporta até "
                f"{int(np.floor(folga['folga_ne_pendente'])):,} OS adicionais como "
                f"não executadas dentro do SLA."
            )
        elementos.append(Paragraph(escape(diagnostico), s["TextoPDF"]))
        elementos.append(Spacer(1, 0.35 * cm))

        cenarios = []
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            proj = Motor.projetar(df_seg, p)
            cenarios.append({
                "Cenário": nome, "Probab. Pend.": p,
                "Fechamento": proj["fechamento_proj"],
                "Não Exec. Proj.": proj["naoexec_proj"],
            })
        elementos.append(Paragraph("2. Cenários de Fechamento", s["Heading2"]))
        elementos.append(RelatorioPDF._tab(pd.DataFrame(cenarios), larguras=[5.0, 5.0, 6.0, 6.0]))
        elementos.append(Spacer(1, 0.35 * cm))

        df_causa = Motor.causa_raiz_segmento(df_seg, tipo, "_COL_BAIXA", top_n=8)
        acoes: List[str] = []
        if folga["estourado"]:
            excesso = abs(folga["naoexec"] - folga["limite_ne_total"])
            acoes.append(f"Atuar imediatamente sobre {int(np.ceil(excesso)):,} OS acima do limite do SLA.")
        if folga["precisa_executar_pendente"] > 0:
            acoes.append(
                f"Executar no mínimo {int(np.ceil(folga['precisa_executar_pendente'])):,} "
                f"OS pendentes para atingir a meta de {sla_meta:.0%}."
            )
        if not df_causa.empty:
            top1 = df_causa.iloc[0]
            acoes.append(
                f"Atacar o principal motivo de baixa '{top1['Motivo de Baixa']}', "
                f"responsável por {top1['% do Total']:.1%} das quebras do segmento."
            )
        if tipo == "PME":
            acoes.extend([
                "Redistribuir ordens para técnicos habilitados em PME nas regiões críticas.",
                "Fazer contato proativo com clientes empresariais com agenda em risco.",
                "Revisar janelas de atendimento corporativo para reduzir indisponibilidade do cliente.",
            ])
        elif tipo == "Migração":
            acoes.extend([
                "Validar estoque de equipamentos GPON e materiais nas regiões com maior quebra.",
                "Priorizar migrações no início do turno por maior tempo médio de execução.",
                "Confirmar habilitação técnica GPON antes da alocação das ordens.",
            ])

        elementos.append(Paragraph("3. Plano de Ação Prioritário", s["Heading2"]))
        if acoes:
            for i, acao in enumerate(acoes, 1):
                elementos.append(Paragraph(f"{i}. {escape(acao)}", s["TextoPDF"]))
                elementos.append(Spacer(1, 0.08 * cm))
        else:
            elementos.append(Paragraph("Sem ações automáticas identificadas.", s["TextoPDF"]))

        elementos.append(PageBreak())

        elementos.append(Paragraph("4. Técnicos Críticos", s["Heading2"]))
        df_tec = Motor.tecnicos_criticos(df_seg, tipo, p_base, float(min_aloc), int(top_n))
        cols_tec = [c for c in ["TÉCNICO", "Alocado", "Executada", "Não Executada",
                                "Pendente", "Quebra Atual", "Fechamento Base"]
                    if c in df_tec.columns]
        elementos.append(RelatorioPDF._tab(
            df_tec[cols_tec] if not df_tec.empty else df_tec,
            limite=min(int(top_n), 10),
        ))
        elementos.append(Spacer(1, 0.35 * cm))

        elementos.append(Paragraph("5. Performance Regional", s["Heading2"]))
        df_reg = Motor.comparativo_regioes(df_seg, tipo)
        cols_reg = [c for c in ["REGIÃO", "Alocado", "Executada", "Não Executada", "Pendente", "Quebra"]
                    if c in df_reg.columns]
        elementos.append(RelatorioPDF._tab(df_reg[cols_reg] if not df_reg.empty else df_reg))
        elementos.append(Spacer(1, 0.35 * cm))

        elementos.append(Paragraph("6. Principais Motivos de Baixa", s["Heading2"]))
        elementos.append(RelatorioPDF._tab(df_causa, limite=8))
        elementos.append(Spacer(1, 0.35 * cm))

        elementos.append(Paragraph("7. Monitores do Segmento", s["Heading2"]))
        df_mon = Motor.tabela_cenarios(df_seg, "MONITOR", p_ot, p_base, p_pess, float(min_aloc))
        cols_mon = [c for c in ["MONITOR", "Alocado", "Executada", "Não Executada",
                                "Pendente", "Quebra Atual", "Fechamento Base"]
                    if c in df_mon.columns]
        elementos.append(RelatorioPDF._tab(
            df_mon[cols_mon] if not df_mon.empty else df_mon,
            limite=min(int(top_n), 10),
        ))

        doc.build(elementos, onFirstPage=RelatorioPDF._rodape, onLaterPages=RelatorioPDF._rodape)
        buf.seek(0)
        return buf.getvalue()


# ====================================================
# 11. ABA SEGMENTO DETALHADO (INTOCADA - só usa os wrappers)
# ====================================================
def render_aba_segmento(
    df: pd.DataFrame, tipo: str,
    p_ot: float, p_base: float, p_pess: float,
    min_aloc: float, top_n: int,
    col_baixa: str, sla_meta: float,
) -> None:
    df_seg = df[df["TIPO_SERVICO"] == tipo].copy()

    if df_seg.empty:
        st.info(f"Nenhum dado para o segmento **{tipo}** nos filtros selecionados.")
        return

    m_seg = Motor.projetar(df_seg, p_base)
    render_segmento_header(tipo, m_seg["quebra_atual"], sla_meta)
    render_alerta_sla(m_seg["quebra_atual"], sla_meta, tipo)
    st.markdown("")

    if tipo in {"PME", "Migração"}:
        col_pdf1, col_pdf2 = st.columns([1.2, 2.8])
        with col_pdf1:
            pdf_bytes = RelatorioPDF.gerar_segmento(
                df=df, tipo=tipo, sla_meta=sla_meta,
                p_ot=p_ot, p_base=p_base, p_pess=p_pess,
                min_aloc=float(min_aloc), top_n=min(int(top_n), 10),
            )
            st.download_button(
                f"📄 Baixar PDF Executivo — {tipo}",
                data=pdf_bytes,
                file_name=f"relatorio_executivo_{tipo.lower().replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"pdf_exec_{tipo}",
                use_container_width=True,
            )
        with col_pdf2:
            st.info(
                "O PDF executivo consolida resumo operacional, cenários de fechamento, "
                "técnicos críticos, performance regional, principais causas de quebra "
                "e plano de ação prioritário."
            )
        st.markdown("")

    sub1, sub2, sub3, sub4, sub5 = st.tabs([
        "📊 Visão Geral", "🔍 Causa Raiz", "👤 Técnicos Críticos",
        "🗺️ Por Região", "🎯 Plano de Ação",
    ])

    # ── SUB 1 ── VISÃO GERAL ─────────────────────────────
    with sub1:
        render_section(f"📊 Resumo Operacional — {tipo}")

        k1, k2, k3, k4, k5 = st.columns(5)
        render_kpi(k1, "Alocado", f"{int(m_seg['alocado']):,}", tema="azul")
        render_kpi(k2, "Executadas", f"{int(m_seg['exec']):,}", tema="verde")
        render_kpi(k3, "Não Exec.", f"{int(m_seg['naoexec']):,}", tema="laranja")
        render_kpi(k4, "Pendentes", f"{int(m_seg['pend']):,}", tema="cinza")
        render_kpi(
            k5, "Quebra Atual", f"{m_seg['quebra_atual']:.2%}",
            sub=f"Meta: {sla_meta:.0%}",
            tema="vermelho" if m_seg["quebra_atual"] > sla_meta else "verde",
        )
        st.markdown("")

        render_section("🔮 Projeções de Fechamento")
        cen_seg = {
            "Otimista": Motor.projetar(df_seg, p_ot),
            "Base": Motor.projetar(df_seg, p_base),
            "Pessimista": Motor.projetar(df_seg, p_pess),
        }

        c_cen, c_gauge = st.columns([2, 3])
        with c_cen:
            for nome, cdata in cen_seg.items():
                cor = "vermelho" if cdata["fechamento_proj"] > sla_meta else "verde"
                render_kpi_sm(
                    st, nome, f"{cdata['fechamento_proj']:.2%}",
                    sub=f"Não Exec. proj.: {int(cdata['naoexec_proj']):,}",
                    tema=cor,
                )

        with c_gauge:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=m_seg["quebra_atual"] * 100,
                delta={"reference": sla_meta * 100,
                       "increasing": {"color": "#EF4444"},
                       "decreasing": {"color": "#10B981"}, "suffix": "%"},
                number={"suffix": "%", "font": {"size": 40, "color": "#0F172A"}},
                gauge={
                    "axis": {"range": [0, 50], "ticksuffix": "%"},
                    "bar": {"color": ("#EF4444" if m_seg["quebra_atual"] > sla_meta else "#10B981")},
                    "steps": [
                        {"range": [0, sla_meta * 100], "color": "#DCFCE7"},
                        {"range": [sla_meta * 100, sla_meta * 120], "color": "#FEF9C3"},
                        {"range": [sla_meta * 120, 50], "color": "#FEE2E2"},
                    ],
                    "threshold": {"line": {"color": "#DC2626", "width": 3},
                                  "thickness": 0.85, "value": sla_meta * 100},
                },
                title={"text": f"Quebra Atual vs. Meta {sla_meta:.0%}", "font": {"size": 14}},
            ))
            fig_gauge.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
            st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})

        st.markdown("")
        render_section("🛡️ Folga de SLA")
        folga = Motor.folga_sla(df_seg, sla_meta)
        f1, f2, f3 = st.columns(3)
        cor_folga = (
            "vermelho" if folga["estourado"]
            else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
        )
        render_kpi(f1, "Folga (OS)",
                   f"{int(np.floor(folga['folga_ne_pendente'])):,}",
                   sub="Não Exec. ainda permitidas", tema=cor_folga)
        render_kpi(f2, "Execução Mínima",
                   f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
                   sub="Pendentes que devem ser executadas", tema="azul")
        render_kpi(f3, "Limite NE Total",
                   f"{int(folga['limite_ne_total']):,}",
                   sub=f"= {sla_meta:.0%} × {int(folga['alocado']):,}", tema="cinza")

        st.progress(min(1.0, max(0.0, float(m_seg["quebra_atual"] / (sla_meta * 2)))))

        df_ev = Motor.evolucao_temporal(df_seg, tipo)
        if not df_ev.empty:
            st.markdown("")
            render_section("📅 Evolução Diária")
            fig_ev = go.Figure()
            fig_ev.add_trace(go.Scatter(
                x=df_ev["Data"], y=df_ev["Quebra"],
                mode="lines+markers", name="Quebra",
                line=dict(color="#EF4444", width=2),
                fill="tozeroy", fillcolor="rgba(239,68,68,0.08)",
            ))
            fig_ev.add_hline(y=sla_meta, line_dash="dash", line_color="#DC2626",
                             annotation_text=f"Meta {sla_meta:.0%}",
                             annotation_position="top left")
            fig_ev.update_layout(
                yaxis_tickformat=".1%", height=280,
                margin=dict(t=20, b=20, l=10, r=10),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_ev, use_container_width=True, config={"displayModeBar": False})
        else:
            render_insight(
                "Data de agenda não encontrada na base — análise temporal indisponível. "
                "Certifique-se de que a coluna 'DATA AGENDA' está presente.",
                tipo="alerta",
            )

    # ── SUB 2 ── CAUSA RAIZ ──────────────────────────────
    with sub2:
        render_section(f"🔍 Causa Raiz — {tipo}")
        df_causa = Motor.causa_raiz_segmento(df_seg, tipo, "_COL_BAIXA", top_n=8)

        if df_causa.empty:
            render_insight(
                "Coluna de código/motivo de baixa não identificada. "
                "Verifique se a base contém 'CÓD DE BAIXA 1' ou similar.",
                tipo="alerta",
            )
        else:
            c_tab, c_chart = st.columns([1.2, 2])
            with c_tab:
                render_dataframe(
                    df_causa, titulo=f"Top Motivos — {tipo}", icone="🔍",
                    fmt={"% do Total": "{:.2%}", "Acumulado": "{:.2%}"},
                    height=350,
                )
            with c_chart:
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(
                    x=df_causa["Motivo de Baixa"], y=df_causa["Volume"],
                    name="Volume", marker_color="#EF4444",
                    text=df_causa["Volume"], textposition="outside",
                ))
                fig_pareto.add_trace(go.Scatter(
                    x=df_causa["Motivo de Baixa"], y=df_causa["Acumulado"],
                    name="Acumulado %", yaxis="y2", mode="lines+markers",
                    line=dict(color="#0EA5E9", width=2), marker=dict(size=7),
                ))
                fig_pareto.update_layout(
                    title=f"Pareto de Motivos de Quebra — {tipo}",
                    yaxis=dict(title="Volume de OS"),
                    yaxis2=dict(title="Acumulado %", overlaying="y", side="right",
                                tickformat=".0%", range=[0, 1.1]),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    height=380, margin=dict(t=50, b=80, l=10, r=60),
                    xaxis=dict(tickangle=-30),
                )
                fig_pareto.add_hline(
                    y=0.8, line_dash="dot", line_color="#F59E0B", yref="y2",
                    annotation_text="80%", annotation_position="top right",
                )
                st.plotly_chart(fig_pareto, use_container_width=True, config={"displayModeBar": False})

            if len(df_causa) >= 2:
                top1 = df_causa.iloc[0]
                top2 = df_causa.iloc[1]
                acum2 = df_causa.iloc[1]["Acumulado"]
                render_insight(
                    f"Os 2 principais motivos (**{top1['Motivo de Baixa']}** e "
                    f"**{top2['Motivo de Baixa']}**) respondem por "
                    f"**{acum2:.1%}** do total de quebras em {tipo}. "
                    f"Focar nesses pontos é o caminho mais rápido para redução de SLA.",
                    tipo="acao",
                )

    # ── SUB 3 ── TÉCNICOS CRÍTICOS ────────────────────────
    with sub3:
        render_section(f"👤 Técnicos com Maior Quebra — {tipo}")
        df_tec = Motor.tecnicos_criticos(df_seg, tipo, p_base, float(min_aloc), int(top_n))

        if df_tec.empty:
            render_insight(
                f"Não há técnicos com volume mínimo de {int(min_aloc)} OS neste segmento.",
                tipo="info",
            )
        else:
            fmt_rank: Dict[str, Any] = {
                "Quebra Atual": "{:.2%}",
                "Fechamento Otimista": "{:.2%}",
                "Fechamento Base": "{:.2%}",
                "Fechamento Pessimista": "{:.2%}",
            }
            render_dataframe(
                df_tec, titulo=f"Técnicos Críticos — {tipo}", icone="🚨",
                fmt=fmt_rank, color_col="Fechamento Base",
                color_meta=sla_meta, color_invertido=True, height=450,
            )
            st.download_button(
                f"📥 Exportar Técnicos {tipo}",
                Utils.gerar_excel(df_tec, f"Tec_{tipo[:25]}"),
                f"tecnicos_criticos_{tipo.lower().replace(' ', '_')}.xlsx",
                key=f"dl_tec_{tipo}",
            )

            df_plot_tec = df_tec.head(10).copy()
            df_plot_tec_sorted = df_plot_tec.sort_values("Fechamento Base")
            fig_tec = go.Figure()
            cores_barra = ["#EF4444" if v > sla_meta else "#10B981"
                           for v in df_plot_tec_sorted["Fechamento Base"]]
            fig_tec.add_trace(go.Bar(
                y=df_plot_tec_sorted["TÉCNICO"],
                x=df_plot_tec_sorted["Fechamento Base"],
                orientation="h", marker_color=cores_barra,
                text=[f"{v:.1%}" for v in df_plot_tec_sorted["Fechamento Base"]],
                textposition="outside",
            ))
            fig_tec.add_vline(x=sla_meta, line_dash="dash", line_color="#DC2626",
                              annotation_text=f"Meta {sla_meta:.0%}")
            fig_tec.update_layout(
                title=f"Quebra Projetada (Base) por Técnico — {tipo}",
                xaxis_tickformat=".1%",
                height=max(300, len(df_plot_tec_sorted) * 36),
                margin=dict(t=40, b=20, l=10, r=60),
            )
            st.plotly_chart(fig_tec, use_container_width=True, config={"displayModeBar": False})

            acima_meta = (df_tec["Fechamento Base"] > sla_meta).sum()
            pct_acima = acima_meta / len(df_tec)
            if pct_acima > 0.5:
                render_insight(
                    f"**{acima_meta} de {len(df_tec)}** técnicos ({pct_acima:.0%}) "
                    f"estão acima da meta de {sla_meta:.0%} no segmento {tipo}. "
                    f"Avalie redistribuição de carteira e suporte técnico especializado.",
                    tipo="critico",
                )
            elif acima_meta > 0:
                render_insight(
                    f"**{acima_meta} técnico(s)** com quebra acima da meta. "
                    f"Ação individual recomendada: feedback + acompanhamento de campo.",
                    tipo="alerta",
                )
            else:
                render_insight(
                    f"Todos os técnicos com quebra dentro da meta no segmento {tipo}. "
                    f"Mantenha o monitoramento preventivo.",
                    tipo="ok",
                )

    # ── SUB 4 ── REGIÕES ─────────────────────────────────
    with sub4:
        render_section(f"🗺️ Performance por Região — {tipo}")
        df_reg = Motor.comparativo_regioes(df_seg, tipo)

        if df_reg.empty:
            render_insight("Coluna de região não encontrada.", tipo="alerta")
        else:
            c_mapa, c_tab = st.columns([2, 1.5])
            with c_mapa:
                cores_reg = ["#EF4444" if v > sla_meta else "#10B981" for v in df_reg["Quebra"]]
                fig_reg = go.Figure()
                fig_reg.add_trace(go.Bar(
                    x=df_reg["REGIÃO"], y=df_reg["Quebra"],
                    marker_color=cores_reg,
                    text=[f"{v:.1%}" for v in df_reg["Quebra"]],
                    textposition="outside", name="Quebra",
                ))
                fig_reg.add_hline(y=sla_meta, line_dash="dash", line_color="#DC2626",
                                  annotation_text=f"Meta {sla_meta:.0%}")
                fig_reg.add_trace(go.Scatter(
                    x=df_reg["REGIÃO"], y=df_reg["Alocado"],
                    mode="lines+markers", name="Alocado", yaxis="y2",
                    line=dict(color="#0EA5E9", width=2, dash="dot"),
                ))
                fig_reg.update_layout(
                    title=f"Quebra e Volume por Região — {tipo}",
                    yaxis=dict(tickformat=".1%", title="Quebra"),
                    yaxis2=dict(title="Alocado", overlaying="y", side="right"),
                    height=320, margin=dict(t=40, b=20, l=10, r=60),
                    legend=dict(orientation="h"),
                )
                st.plotly_chart(fig_reg, use_container_width=True, config={"displayModeBar": False})

            with c_tab:
                render_dataframe(
                    df_reg[["REGIÃO", "Alocado", "Executada", "Não Executada", "Pendente", "Quebra"]],
                    titulo="Detalhamento Regional", icone="🗺️",
                    fmt={"Quebra": "{:.2%}"},
                    color_col="Quebra", color_meta=sla_meta,
                    color_invertido=True, height=300,
                )

            if not df_reg.empty:
                pior = df_reg.loc[df_reg["Quebra"].idxmax()]
                melhor = df_reg.loc[df_reg["Quebra"].idxmin()]
                render_insight(
                    f"Região mais crítica: **{pior['REGIÃO']}** com quebra de "
                    f"**{pior['Quebra']:.2%}** ({int(pior['Alocado'].item()):,} OS alocadas). "
                    f"Melhor desempenho: **{melhor['REGIÃO']}** ({melhor['Quebra']:.2%}). "
                    f"Diferença de **{(pior['Quebra'] - melhor['Quebra']):.2%}** entre as regiões.",
                    tipo="info",
                )

            st.markdown("")
            render_section("👔 Monitores × Região")
            if "MONITOR" in df_seg.columns:
                df_mon_reg = Motor.tabela_cenarios(
                    df_seg, "MONITOR", p_ot, p_base, p_pess, float(min_aloc)
                )
                if not df_mon_reg.empty:
                    render_dataframe(
                        df_mon_reg, titulo=f"Monitores — {tipo}", icone="👔",
                        fmt={"Quebra Atual": "{:.2%}",
                             "Fechamento Otimista": "{:.2%}",
                             "Fechamento Base": "{:.2%}",
                             "Fechamento Pessimista": "{:.2%}"},
                        color_col="Fechamento Base", color_meta=sla_meta,
                        color_invertido=True, height=380,
                    )

    # ── SUB 5 ── PLANO DE AÇÃO ────────────────────────────
    with sub5:
        render_section(f"🎯 Plano de Ação — {tipo}")
        folga_pa = Motor.folga_sla(df_seg, sla_meta)
        cen_pa = Motor.projetar(df_seg, p_base)

        excesso_ne = max(0.0, folga_pa["naoexec"] - folga_pa["limite_ne_total"])
        pend_exec = folga_pa["precisa_executar_pendente"]

        col_diag, col_acoes = st.columns([1, 1.5])

        with col_diag:
            render_section("📋 Diagnóstico")
            render_kpi_sm(st, "Excesso de NE vs. Limite",
                          f"{int(excesso_ne):,}",
                          sub="OS além do permitido pela meta",
                          tema="vermelho" if excesso_ne > 0 else "verde")
            render_kpi_sm(st, "Pendentes a Executar",
                          f"{int(np.ceil(pend_exec)):,}",
                          sub=f"Mínimo para atingir meta {sla_meta:.0%}",
                          tema="azul")
            render_kpi_sm(st, "Proj. Cenário Base",
                          f"{cen_pa['fechamento_proj']:.2%}",
                          sub=f"c/ {p_base:.0%} de quebra nos pendentes",
                          tema="vermelho" if cen_pa["fechamento_proj"] > sla_meta else "verde")

            st.markdown("")
            if folga_pa["pend"] > 0:
                taxa_exec_necessaria = 1 - (folga_pa["folga_ne_pendente"] / folga_pa["pend"])
                st.markdown(
                    f"**Taxa mínima de execução nos pendentes:** "
                    f"`{max(0, taxa_exec_necessaria):.1%}`"
                )
                st.progress(min(1.0, max(0.0, float(taxa_exec_necessaria))))

        with col_acoes:
            render_section("✅ Ações Recomendadas")

            acoes: List[Dict[str, str]] = []
            if folga_pa["estourado"]:
                acoes.append({
                    "prioridade": "🔴 IMEDIATA",
                    "acao": f"Acionar equipe de plantão para recuperação das "
                            f"{int(excesso_ne):,} OS não executadas acima do limite.",
                    "tipo": "critico",
                })
            if pend_exec > 0:
                acoes.append({
                    "prioridade": "🟠 ALTA",
                    "acao": f"Garantir execução de pelo menos "
                            f"{int(np.ceil(pend_exec)):,} das OS pendentes de {tipo} "
                            f"para atingir a meta de {sla_meta:.0%}.",
                    "tipo": "alerta",
                })

            if tipo == "PME":
                acoes.extend([
                    {"prioridade": "🟡 MÉDIA",
                     "acao": "Verificar disponibilidade de técnicos habilitados em PME "
                             "para redistribuição de carteira nas regiões críticas.",
                     "tipo": "acao"},
                    {"prioridade": "🟡 MÉDIA",
                     "acao": "Acionar equipe comercial PME para comunicação proativa "
                             "com clientes com agenda em risco de quebra.",
                     "tipo": "acao"},
                    {"prioridade": "🟢 BAIXA",
                     "acao": "Revisar janelas de atendimento PME — clientes empresariais "
                             "têm menor flexibilidade de horário. Ajustar agendamentos "
                             "para períodos de maior disponibilidade.",
                     "tipo": "info"},
                ])
            elif tipo == "Migração":
                acoes.extend([
                    {"prioridade": "🟠 ALTA",
                     "acao": "Verificar estoque de equipamentos GPON nos almoxarifados "
                             "das regiões com maior quebra — falta de material é causa "
                             "frequente em migrações.",
                     "tipo": "alerta"},
                    {"prioridade": "🟡 MÉDIA",
                     "acao": "Confirmar certificação dos técnicos em instalação GPON. "
                             "Migrações exigem habilitação técnica específica.",
                     "tipo": "acao"},
                    {"prioridade": "🟡 MÉDIA",
                     "acao": "Priorizar agendamentos de migração no início do turno — "
                             "instações GPON têm tempo médio maior e impactam mais "
                             "a quebra quando reagendadas.",
                     "tipo": "acao"},
                    {"prioridade": "🟢 BAIXA",
                     "acao": "Validar se ordens de Migração com status 'Pendente' possuem "
                             "pré-vistoria aprovada. Evita quebra por impedimento técnico "
                             "no dia do atendimento.",
                     "tipo": "info"},
                ])

            for acao in acoes:
                render_insight(f"**{acao['prioridade']}** — {acao['acao']}", tipo=acao["tipo"])

        st.markdown("")
        df_plano = pd.DataFrame([
            {"Segmento": tipo, "Prioridade": a["prioridade"], "Ação": a["acao"]}
            for a in acoes
        ])
        if not df_plano.empty:
            st.download_button(
                f"📥 Exportar Plano de Ação — {tipo}",
                Utils.gerar_excel(df_plano, f"Plano_{tipo[:25]}"),
                f"plano_acao_{tipo.lower().replace(' ', '_')}.xlsx",
                key=f"dl_plano_{tipo}",
            )


# ====================================================
# 12. APLICAÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    aplicar_estilo_dominio()

    render_hero(
        titulo="📉 Gestão de Quebra de Agenda",
        subtitulo="Análise de quebra, projeções de SLA e plano de ação operacional",
        badge="Painel Operacional",
    )

    with st.sidebar:
        st.header("⚙️ Configurações")
        if st.button("🔄 Reiniciar Painel", use_container_width=True):
            st.session_state["df_memoria"] = None
            st.rerun()
        st.divider()

    # ── Upload ──────────────────────────────────────────────
    if st.session_state["df_memoria"] is None:
        render_section("📁 Importação de Dados")
        arq = st.file_uploader("Selecione a base (Excel/CSV)", type=["xlsx", "csv"])
        if arq:
            with st.spinner("Processando..."):
                raw = DataLoader.ler_arquivo(arq.getvalue(), arq.name)
                gs = DataLoader.buscar_gsheets()
                df_proc = DataLoader.preparar_base(raw, gs)
                st.session_state["df_memoria"] = df_proc

            diag = df_proc.attrs.get("diagnostico", {})
            if diag.get("contrato_vazio", 0) > 0:
                st.toast(f"🗑️ {diag['contrato_vazio']} linha(s) sem contrato removida(s).", icon="⚠️")
            if diag.get("suspensos", 0) > 0:
                st.toast(f"🗑️ {diag['suspensos']} ordens suspensas removidas.", icon="ℹ️")
            if not diag.get("col_status_encontrada", False):
                st.warning("⚠️ Coluna 'Status da O.S 1' não encontrada.")
            st.rerun()
        return

    df_mem = st.session_state["df_memoria"]
    df_full = df_mem.copy() if isinstance(df_mem, pd.DataFrame) else pd.DataFrame()

    if df_full.empty:
        st.error("Base carregada está vazia. Envie um novo arquivo.")
        st.session_state["df_memoria"] = None
        return

    if "Status Contrato" not in df_full.columns:
        col_status = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1"])
        df_full["Status Contrato"] = (
            Utils.classificar_status(df_full[col_status]) if col_status else "Pendente"
        )

    # ── Sidebar Filtros ─────────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros")
        monitores = ["Todos"] + sorted([
            str(x) for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        ])
        sel_mon = st.selectbox("👔 Monitor", monitores)

        df_filt = df_full.copy()
        if sel_mon != "Todos":
            df_filt = df_filt[df_filt["MONITOR"] == sel_mon]

        tecnicos = ["Todos"] + sorted([
            str(x) for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        ])
        sel_tec = st.selectbox("👤 Técnico", tecnicos)

        df = df_filt.copy()
        if sel_tec != "Todos":
            df = df[df["TÉCNICO"] == sel_tec]

        st.divider()
        st.subheader("🔮 Probabilidade de Quebra")
        p_ot = st.slider("Otimista (%)", 0, 100, 15, 5) / 100.0
        p_base = st.slider("Base (%)", 0, 100, 20, 5) / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 50, 5) / 100.0

        min_aloc = 1
        top_n = 999999

    if df.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    render_resultado_base(sorted(df[Config.COL_REGIAO].unique()), len(df))

    st.info(
        "👈 Para análises detalhadas de segmentos específicos, acesse **PME** ou "
        "**Migração** no menu lateral."
    )

    m = Motor.projetar(df, p_base)
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    render_kpi(k1, "Alocado", f"{int(m['alocado']):,}", tema="azul")
    render_kpi(k2, "Executadas", f"{int(m['exec']):,}", tema="verde")
    render_kpi(k3, "Não Exec", f"{int(m['naoexec']):,}", tema="laranja")
    render_kpi(k4, "Pendentes", f"{int(m['pend']):,}", tema="cinza")
    render_kpi(k5, "Quebra Atual", f"{m['quebra_atual']:.2%}", tema="cinza")
    render_kpi(
        k6, "Proj. Base", f"{m['fechamento_proj']:.2%}",
        tema="vermelho" if m["fechamento_proj"] > Config.SLA_QUEBRA_MAXIMA else "roxo",
    )
    st.markdown("")

    aba_visao, aba_rank, aba_causa, aba_back, aba_tipos = st.tabs([
        "📊 Visão & Projeções", "🧭 Desempenho", "🔍 Causas",
        "🚨 Backoffice", "📂 Por Tipo de Serviço",
    ])

    # ── ABA: VISÃO & PROJEÇÕES ───────────────────────────
    with aba_visao:
        render_section("🔮 Análise e Simulações de SLA")
        cen = {
            "Otimista": Motor.projetar(df, p_ot),
            "Base": Motor.projetar(df, p_base),
            "Pessimista": Motor.projetar(df, p_pess),
        }
        c_cards, c_graf = st.columns([3, 2.5])
        with c_cards:
            o1, o2, o3 = st.columns(3)
            for col_ui, nome, tema_d in [(o1, "Otimista", "cinza"),
                                          (o2, "Base", "roxo"),
                                          (o3, "Pessimista", "cinza")]:
                proj = cen[nome]
                cor = ("vermelho" if proj["fechamento_proj"] > Config.SLA_QUEBRA_MAXIMA else tema_d)
                render_kpi(
                    col_ui, nome, f"{proj['fechamento_proj']:.2%}",
                    sub=f"Vol: {int(proj['naoexec_proj']):,}", tema=cor,
                )
            st.markdown("")
            folga = Motor.folga_sla(df, Config.SLA_QUEBRA_MAXIMA)
            f1, f2 = st.columns(2)
            cor_f = ("vermelho" if folga["estourado"]
                     else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja"))
            render_kpi(f1, "Folga no SLA",
                       f"{int(np.floor(folga['folga_ne_pendente'])):,}",
                       sub=f"Pendente aceitável: {folga['folga_pct_pendente']:.1%}",
                       tema=cor_f)
            render_kpi(f2, "Garantia Mínima",
                       f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
                       sub="OS a executar", tema="azul")
            st.progress(min(1.0, max(0.0, float(folga["folga_pct_pendente"]))))
            if folga["estourado"]:
                st.error(f"❌ SLA estourado em "
                         f"{abs(folga['naoexec'] - folga['limite_ne_total']):,.0f} OS.")
        with c_graf:
            df_plot = pd.DataFrame({
                "Cenário": ["Otimista", "Base", "Pessimista"],
                "Fechamento": [cen[s]["fechamento_proj"]
                               for s in ["Otimista", "Base", "Pessimista"]],
            })
            fig = px.bar(
                df_plot, x="Cenário", y="Fechamento",
                color="Fechamento", color_continuous_scale="Purples",
                title="Cenários Projetados",
            )
            fig.update_traces(texttemplate="%{y:.2%}", textposition="outside")
            fig.add_hline(y=Config.SLA_QUEBRA_MAXIMA, line_dash="dash",
                          line_color="red", annotation_text="Meta",
                          annotation_position="top left")
            fig.update_layout(yaxis_tickformat=".0%", coloraxis_showscale=False,
                              height=380, margin=dict(t=40, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── ABA: DESEMPENHO ──────────────────────────────────
    with aba_rank:
        t_mon, t_tec = st.tabs(["👔 Monitores", "👤 Técnicos"])
        fmt_rank: Dict[str, Any] = {
            "Quebra Atual": "{:.2%}",
            "Fechamento Otimista": "{:.2%}",
            "Fechamento Base": "{:.2%}",
            "Fechamento Pessimista": "{:.2%}",
        }
        with t_mon:
            df_rm = Motor.tabela_cenarios(df_full, "MONITOR", p_ot, p_base, p_pess, float(min_aloc))
            if df_rm.empty:
                st.info("Sem dados suficientes.")
            else:
                render_dataframe(
                    df_rm, titulo="Ranking de Monitores", icone="👔",
                    fmt=fmt_rank, color_col="Fechamento Base",
                    color_meta=Config.SLA_QUEBRA_MAXIMA, color_invertido=True,
                    height="stretch",
                )
                st.download_button("📥 Baixar Ranking Monitores",
                                   Utils.gerar_excel(df_rm, "Monitores"),
                                   "ranking_monitores.xlsx")
        with t_tec:
            df_rt = Motor.tabela_cenarios(df, "TÉCNICO", p_ot, p_base, p_pess, float(min_aloc))
            if df_rt.empty:
                st.info("Sem dados suficientes.")
            else:
                df_rt_sorted = df_rt.sort_values(
                    by=["Fechamento Base", "Quebra Atual", "Alocado"],
                    ascending=[False, False, False],
                ).reset_index(drop=True)
                render_dataframe(
                    df_rt_sorted, titulo="Ranking de Técnicos", icone="👤",
                    fmt=fmt_rank, color_col="Fechamento Base",
                    color_meta=Config.SLA_QUEBRA_MAXIMA, color_invertido=True,
                    height=500,
                )
                st.download_button("📥 Baixar Ranking Técnicos",
                                   Utils.gerar_excel(df_rt_sorted, "Tecnicos"),
                                   "ranking_tecnicos.xlsx")

    # ── ABA: CAUSAS ──────────────────────────────────────
    with aba_causa:
        render_section("🔍 Análise de Causa Raiz")
        col_cod_baixa = Utils.buscar_coluna(
            df_full,
            ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "CÓDIGO DE BAIXA 1", "COD BAIXA 1"],
        )
        ca1, ca2 = st.columns([1, 2])
        with ca1:
            df_dist = df.groupby("Status Contrato")["TOTAL DE TAREFAS"].sum().reset_index()
            fig_pie = px.pie(
                df_dist, names="Status Contrato", values="TOTAL DE TAREFAS",
                hole=0.5, color="Status Contrato",
                color_discrete_map=Config.CORES_STATUS,
            )
            fig_pie.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                margin=dict(t=10, b=10, l=10, r=10), height=350,
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        with ca2:
            if col_cod_baixa and col_cod_baixa in df.columns:
                df_cod = (
                    df[df["Status Contrato"] == "Não Executada"]
                    .groupby(col_cod_baixa)["TOTAL DE TAREFAS"]
                    .sum().nlargest(5).reset_index()
                )
                if not df_cod.empty:
                    fig_mot = px.bar(
                        df_cod, x="TOTAL DE TAREFAS", y=col_cod_baixa,
                        orientation="h", text="TOTAL DE TAREFAS",
                        color_discrete_sequence=["#EF4444"],
                    )
                    fig_mot.update_layout(
                        yaxis={"categoryorder": "total ascending"},
                        margin=dict(t=10, b=10, l=5, r=5), height=350,
                    )
                    st.plotly_chart(fig_mot, use_container_width=True)
                else:
                    st.info("Nenhuma OS 'Não Executada' com motivo.")
            else:
                st.warning("Coluna 'Código de Baixa' não encontrada.")

    # ── ABA: BACKOFFICE ──────────────────────────────────
    with aba_back:
        render_section("🚨 Fila de Tratamento (Backoffice)")
        df_back = df[df["Status Contrato"] == "Não Executada"].copy()

        if not df_back.empty:
            resumo_back = (
                df_back.groupby(["MONITOR", "TÉCNICO", "TIPO_SERVICO"])["TOTAL DE TAREFAS"]
                .sum().reset_index()
                .sort_values("TOTAL DE TAREFAS", ascending=False)
            )
            resumo_back.columns = ["Monitor", "Técnico", "Tipo", "Qtd Não Executadas"]
            render_dataframe(
                resumo_back, titulo="Resumo Backoffice — Não Executadas", icone="🚨",
                badge=f"{int(df_back['TOTAL DE TAREFAS'].sum()):,} OS", height=500,
            )
            st.download_button("📥 Baixar Resumo Backoffice",
                               Utils.gerar_excel(resumo_back, "Backoffice_Resumo"),
                               "backoffice_resumo.xlsx")
        else:
            st.info("Sem dados de Backoffice para 'Não Executada'.")

    # ── ABA: POR TIPO ────────────────────────────────────
    with aba_tipos:
        render_section("📂 Análise por Tipo de Serviço")

        if "TIPO_SERVICO" not in df.columns:
            st.warning("Coluna de tipo não encontrada.")
        else:
            tipos_disponiveis = [
                t for t in ["PME", "Novos Domicílios", "Migração", "GPON", "Outros"]
                if t in df["TIPO_SERVICO"].unique()
            ]
            st.markdown("")
            if tipos_disponiveis:
                sub_abas = st.tabs([f"📋 {t}" for t in tipos_disponiveis])
                fmt_r: Dict[str, Any] = {
                    "Quebra Atual": "{:.2%}",
                    "Fechamento Otimista": "{:.2%}",
                    "Fechamento Base": "{:.2%}",
                    "Fechamento Pessimista": "{:.2%}",
                }
                for sub_aba, tipo in zip(sub_abas, tipos_disponiveis):
                    with sub_aba:
                        df_tipo = df[df["TIPO_SERVICO"] == tipo].copy()
                        if df_tipo.empty:
                            st.info(f"Sem dados para **{tipo}**.")
                            continue
                        m_tipo = Motor.projetar(df_tipo, p_base)
                        t1, t2, t3, t4 = st.columns(4)
                        render_kpi(t1, "Alocado", f"{int(m_tipo['alocado']):,}", tema="azul")
                        render_kpi(t2, "Executadas", f"{int(m_tipo['exec']):,}", tema="verde")
                        render_kpi(t3, "Não Exec", f"{int(m_tipo['naoexec']):,}", tema="laranja")
                        render_kpi(
                            t4, "Quebra Atual", f"{m_tipo['quebra_atual']:.2%}",
                            tema=("vermelho"
                                  if m_tipo["quebra_atual"] > Config.SLA_QUEBRA_MAXIMA
                                  else "cinza"),
                        )
                        st.markdown("")
                        df_rank_tipo = Motor.tabela_cenarios(
                            df_tipo, "MONITOR", p_ot, p_base, p_pess, float(min_aloc)
                        )
                        if not df_rank_tipo.empty:
                            render_dataframe(
                                df_rank_tipo, titulo=f"Monitores — {tipo}", icone="👔",
                                fmt=fmt_r, color_col="Fechamento Base",
                                color_meta=Config.SLA_QUEBRA_MAXIMA,
                                color_invertido=True, height="stretch",
                            )
                            st.download_button(
                                f"📥 Baixar {tipo}",
                                Utils.gerar_excel(df_rank_tipo, tipo[:31]),
                                f"ranking_{tipo.lower().replace(' ', '_')}.xlsx",
                                key=f"dl_tipo_{tipo}",
                            )
            else:
                st.info("Nenhum tipo disponível encontrado.")


if __name__ == "__main__":
    main()