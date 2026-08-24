"""
pages/retornos.py
================================
Página Corporativa — Retornos do Dia.

Fluxo visível ao usuário:
    1. Upload do arquivo
    2. Painel com indicadores
    3. Download do relatório

Nos bastidores (automático):
    - Limpeza (contratos vazios + suspensos)
    - Filtro por Tipo de Atividade = Retorno Credenciada
    - Enriquecimento via Google Sheets
    - Agrupamento por credenciada no Excel
"""

from __future__ import annotations

import sys
import os
import re
import unicodedata
import logging
from io import BytesIO
from datetime import date
from typing import cast

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_hero,
    render_kpi,
    render_insight,
    render_dataframe,
    COR_PRIMARIA,
    COR_SECUNDARIA,
    COR_SUCESSO,
    COR_ALERTA,
    COR_NEUTRO,
    TemaKPI,
)

logger = logging.getLogger(__name__)

# ==========================================================
# CONFIGURAÇÃO
# ==========================================================
st.set_page_config(
    page_title="Retornos | Operação",
    page_icon="📜",
    layout="wide",
)

aplicar_estilo()

st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        max-width: 1400px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================================
# CONSTANTES
# ==========================================================
STATUS_RETORNO: list[str] = [
    "Concluída", "Concluído", "Executada", "Finalizada",
    "Cancelada", "Cancelado", "Improdutiva", "Improdutivo",
]

NOMES_DATA: list[str] = [
    "Data", "DATA", "DATA AGENDA", "Data Agenda",
    "Data Início", "Data Inicio", "Data Atividade", "Data Agendamento",
]

NOMES_CRED: list[str] = [
    "Credenciada", "Credenciada/Empresa", "Empresa",
    "Nome Credenciada", "Razão Social",
]

NOMES_STATUS: list[str] = [
    "Status da Atividade", "SITUAÇÃO APP", "Situação App",
    "Status", "Situação", "RESULTADO DA ATIVIDADE",
]

NOMES_LOGIN: list[str] = [
    "Login do Técnico", "Login", "Login Técnico", "Usuário",
]

NOMES_CONTRATO: list[str] = [
    "Contrato", "Nº Contrato", "Numero do Contrato",
    "Número do Contrato", "Cod Contrato", "Código do Contrato",
]

NOMES_TIPO_ATIV: list[str] = ["Tipo de Atividade.1"]

VALOR_RETORNO_CREDENCIADA: str = "Retorno Credenciada"

URL_ATIVOS: str = (
    "https://docs.google.com/spreadsheets/d/"
    "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit?gid=0#gid=0"
)

MESES_PT: dict[str, str] = {
    "January": "Janeiro", "February": "Fevereiro", "March": "Março",
    "April": "Abril", "May": "Maio", "June": "Junho",
    "July": "Julho", "August": "Agosto", "September": "Setembro",
    "October": "Outubro", "November": "Novembro", "December": "Dezembro",
}


# ==========================================================
# LEITURA ROBUSTA DE CSV / EXCEL
# ==========================================================
def _normalizar_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    novos: list[str] = []
    contador: dict[str, int] = {}

    for col in df.columns:
        nome = str(col).strip()
        nome = nome.replace("\ufeff", "").replace("\u200b", "").replace("\xa0", " ")
        nome = re.sub(r"\s+", " ", nome).strip()

        if nome in contador:
            contador[nome] += 1
            nome = f"{nome}_{contador[nome]}"
        else:
            contador[nome] = 0
        novos.append(nome)

    df.columns = pd.Index(novos)
    return df


def _limpar_valores_string(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    nulos_padrao: set[str] = {
        "", "nan", "none", "null", "na", "n/a",
        "#n/a", "#na", "-", "--", "?",
    }

    for col in df.select_dtypes(include=["object", "string"]).columns:
        mask_original_na = df[col].isna()
        serie = (
            df[col].astype("string")
            .str.replace("\xa0", " ", regex=False)
            .str.replace("\u200b", "", regex=False)
            .str.replace("\ufeff", "", regex=False)
            .str.replace("\r", " ", regex=False)
            .str.replace("\n", " ", regex=False)
            .str.replace("\t", " ", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        mask_nulos = serie.str.lower().isin(nulos_padrao) | mask_original_na
        df[col] = serie.mask(mask_nulos, pd.NA)

    return df


@st.cache_data(show_spinner="Processando arquivo...")
def carregar_arquivo(
    arquivo_bytes: bytes, nome_arquivo: str,
) -> tuple[pd.DataFrame, dict[str, str]]:
    nome = nome_arquivo.lower()
    stats: dict[str, str] = {"metodo": "", "separador": "", "encoding": ""}

    if nome.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(BytesIO(arquivo_bytes))
            df = _normalizar_nomes_colunas(df)
            df = _limpar_valores_string(df)
            df = df.dropna(how="all").reset_index(drop=True)
            stats["metodo"] = "Excel"
            return df, stats
        except Exception as e:
            raise ValueError(f"Erro ao ler Excel: {e}") from e

    tentativas = [
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": "\t", "encoding": "utf-8-sig"},
        {"sep": "|", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "latin-1"},
        {"sep": ",", "encoding": "latin-1"},
        {"sep": ";", "encoding": "cp1252"},
        {"sep": ",", "encoding": "cp1252"},
    ]

    melhor_df: pd.DataFrame | None = None
    melhor_score = 0
    melhor_cfg: dict[str, str] = {}

    for cfg in tentativas:
        try:
            df = pd.read_csv(
                BytesIO(arquivo_bytes),
                dtype=str, low_memory=False, on_bad_lines="skip",
                sep=cfg["sep"], encoding=cfg["encoding"],
            )
            score = len(df.columns) if len(df.columns) > 1 else 0
            if score > melhor_score:
                melhor_score = score
                melhor_df = df
                melhor_cfg = cfg
        except Exception as e:
            logger.debug(f"Falha {cfg}: {e}")

    if melhor_df is None or melhor_score == 0:
        raise ValueError("Não foi possível identificar o formato do CSV.")

    df_final = _normalizar_nomes_colunas(melhor_df)
    df_final = _limpar_valores_string(df_final)
    df_final = df_final.dropna(how="all").reset_index(drop=True)

    stats["metodo"] = "CSV"
    stats["separador"] = repr(melhor_cfg["sep"])
    stats["encoding"] = melhor_cfg["encoding"]
    return df_final, stats


# ==========================================================
# IDENTIFICAÇÃO / TRATAMENTOS
# ==========================================================
def _normalizar_texto(texto: str) -> str:
    t = str(texto).lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def identificar_coluna(df: pd.DataFrame, nomes_possiveis: list[str]) -> str | None:
    if len(df.columns) == 0:
        return None
    cols_norm = {_normalizar_texto(str(c)): str(c) for c in df.columns}
    for nome in nomes_possiveis:
        chave = _normalizar_texto(nome)
        if chave in cols_norm:
            return cols_norm[chave]
    for nome in nomes_possiveis:
        chave = _normalizar_texto(nome)
        if not chave:
            continue
        for col_norm, col_orig in cols_norm.items():
            if chave in col_norm or col_norm in chave:
                return col_orig
    return None


def converter_data_robusto(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.strip()
    resultado = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if resultado.isna().sum() > len(s) * 0.3:
        formatos = [
            "%d/%m/%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d.%m.%Y",
        ]
        for fmt in formatos:
            tentativa = pd.to_datetime(s, errors="coerce", format=fmt)
            if tentativa.notna().sum() > resultado.notna().sum():
                resultado = tentativa
    return resultado


def aplicar_limpeza_padrao(
    df: pd.DataFrame, col_contrato: str | None, col_status: str | None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    stats = {"total_inicial": len(df), "contratos_vazios": 0, "suspensos": 0, "total_removidas": 0}
    df_clean = df.copy()

    if col_contrato and col_contrato in df_clean.columns:
        contrato_valido = df_clean[col_contrato].notna() & (
            df_clean[col_contrato].astype(str).str.strip() != ""
        )
        stats["contratos_vazios"] = int((~contrato_valido).sum())
        df_clean = df_clean[contrato_valido]

    if col_status and col_status in df_clean.columns:
        nao_suspenso = ~df_clean[col_status].astype(str).str.contains(
            "suspen", case=False, na=False
        )
        stats["suspensos"] = int((~nao_suspenso).sum())
        df_clean = df_clean[nao_suspenso]

    stats["total_removidas"] = stats["total_inicial"] - len(df_clean)
    return df_clean.reset_index(drop=True), stats


def filtrar_retorno_credenciada(
    df: pd.DataFrame, col_tipo: str | None,
    valor_alvo: str = VALOR_RETORNO_CREDENCIADA,
) -> tuple[pd.DataFrame, dict[str, int]]:
    stats = {"total_inicial": len(df), "retornos_encontrados": 0, "removidas": 0}
    if not col_tipo or col_tipo not in df.columns:
        return df.copy(), stats
    valor_norm = valor_alvo.strip().lower()
    mask = df[col_tipo].astype(str).str.strip().str.lower() == valor_norm
    df_filt = df[mask].reset_index(drop=True)
    stats["retornos_encontrados"] = len(df_filt)
    stats["removidas"] = stats["total_inicial"] - len(df_filt)
    return df_filt, stats


# ==========================================================
# GOOGLE SHEETS
# ==========================================================
def montar_url_csv(url_planilha: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url_planilha)
    if not match:
        raise ValueError("URL do Google Sheets inválida.")
    sheet_id = match.group(1)
    gid_match = re.search(r"[?&#]gid=(\d+)", url_planilha)
    gid = gid_match.group(1) if gid_match else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


@st.cache_data(show_spinner="Sincronizando lista de ativos...", ttl=600)
def carregar_ativos_google_sheets(url: str) -> pd.DataFrame:
    df = pd.read_csv(montar_url_csv(url), dtype=str)
    df = _normalizar_nomes_colunas(df)
    df = _limpar_valores_string(df)
    return df.dropna(how="all").reset_index(drop=True)


def fazer_merge_ativos(
    df_principal: pd.DataFrame, df_ativos: pd.DataFrame,
    chave_principal: str, chave_ativos: str,
    cols_trazer: list[str] | None = None,
) -> pd.DataFrame:
    df_principal = df_principal.copy()
    df_ativos = df_ativos.copy()

    df_principal["_chave_"] = df_principal[chave_principal].astype(str).str.strip().str.upper()
    df_ativos["_chave_"] = df_ativos[chave_ativos].astype(str).str.strip().str.upper()

    if cols_trazer:
        cols = ["_chave_"] + [c for c in cols_trazer if c in df_ativos.columns]
        df_ativos = df_ativos[cols]
    else:
        df_ativos = df_ativos.drop(columns=[chave_ativos], errors="ignore")

    df_ativos = df_ativos.drop_duplicates(subset=["_chave_"], keep="first")
    df_merge = df_principal.merge(df_ativos, on="_chave_", how="left", suffixes=("", "_ativo"))
    return df_merge.drop(columns=["_chave_"], errors="ignore")


def enriquecer_automatico(
    df: pd.DataFrame, col_login: str | None,
) -> tuple[pd.DataFrame, dict[str, int | float | str]]:
    """
    Aplica o enriquecimento automaticamente.
    Detecta a chave mais provável na lista de ativos e faz o merge com todas as colunas.
    """
    stats: dict[str, int | float | str] = {
        "aplicado": "não",
        "matches": 0,
        "total": len(df),
        "perc": 0.0,
    }

    if not col_login or col_login not in df.columns:
        return df, stats

    try:
        df_ativos = carregar_ativos_google_sheets(URL_ATIVOS)
    except Exception as e:
        logger.debug(f"Falha ao carregar ativos: {e}")
        return df, stats

    cols_ativos = [str(c) for c in df_ativos.columns]

    # Detecta a chave mais provável na lista de ativos
    candidatos = ["Login", "Login do Técnico", "Usuário", "Usuario", "Matrícula", "Matricula", "CPF"]
    chave_at: str | None = None
    for c in candidatos:
        for col in cols_ativos:
            if _normalizar_texto(c) == _normalizar_texto(col):
                chave_at = col
                break
        if chave_at:
            break

    if not chave_at:
        return df, stats

    df_merged = fazer_merge_ativos(df, df_ativos, col_login, chave_at, cols_trazer=None)

    # Detecta % de match (usa a primeira coluna trazida)
    cols_novas = [c for c in df_merged.columns if c not in df.columns]
    if cols_novas:
        matches = int(df_merged[cols_novas[0]].notna().sum())
        stats["matches"] = matches
        stats["perc"] = round((matches / len(df_merged) * 100), 1) if len(df_merged) else 0.0
        stats["aplicado"] = "sim"

    return df_merged, stats


# ==========================================================
# MÉTRICAS
# ==========================================================
def gerar_metricas(
    df: pd.DataFrame, col_status: str | None,
) -> dict[str, int | float]:
    m: dict[str, int | float] = {
        "total": len(df),
        "concluidas": 0,
        "canceladas": 0,
        "pendentes": 0,
        "taxa_conclusao": 0.0,
    }
    if col_status and not df.empty:
        s = df[col_status].astype(str)
        m["concluidas"] = int(s.str.contains("conclu|execut|finaliz", case=False, na=False).sum())
        m["canceladas"] = int(s.str.contains("cancel|improdut", case=False, na=False).sum())
        m["pendentes"] = int(m["total"] - m["concluidas"] - m["canceladas"])
        if m["total"] > 0:
            m["taxa_conclusao"] = round((m["concluidas"] / m["total"]) * 100, 1)
    return m


def gerar_excel_multi_abas(
    dfs_por_grupo: dict[str, pd.DataFrame], resumo_geral: pd.DataFrame,
    nome_aba_padrao: str = "Sem_Grupo",
) -> BytesIO:
    output = BytesIO()
    try:
        import xlsxwriter  # noqa: F401
        engine = "xlsxwriter"
    except ImportError:
        engine = "openpyxl"

    with pd.ExcelWriter(output, engine=engine) as writer:
        resumo_geral.to_excel(writer, sheet_name="Consolidado", index=False)

        for grupo, df_g in dfs_por_grupo.items():
            aba = str(grupo)[:31] if grupo else nome_aba_padrao
            aba = (
                aba.replace("/", "-").replace("\\", "-")
                   .replace("*", "").replace("?", "")
                   .replace("[", "").replace("]", "").replace(":", "-")
            )
            df_g.to_excel(writer, sheet_name=aba, index=False)

        if engine == "xlsxwriter":
            wb = writer.book
            header_fmt = wb.add_format({  # type: ignore[attr-defined]
                "bold": True, "bg_color": "#012869", "font_color": "white",
                "border": 1, "align": "center", "valign": "vcenter",
            })
            for sheet_name, ws in writer.sheets.items():
                df_ref = resumo_geral if sheet_name == "Consolidado" else dfs_por_grupo.get(sheet_name)
                if df_ref is not None:
                    for i, v in enumerate(df_ref.columns):
                        ws.write(0, i, v, header_fmt)
                        ws.set_column(i, i, 20)

    output.seek(0)
    return output


# ==========================================================
# HELPERS DE UI
# ==========================================================
def stat_pill(label: str, valor: str, cor: str = COR_PRIMARIA) -> str:
    label_html = f'<span style="font-size:11px;color:#6B7280;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">{label}</span>'
    valor_html = f'<span style="font-size:14px;color:{cor};font-weight:700;font-variant-numeric:tabular-nums;">{valor}</span>'
    return f'<div style="display:inline-flex;align-items:baseline;gap:8px;padding:6px 14px;background:#F8FAFC;border-radius:20px;border:1px solid #E2E8F0;margin-right:8px;margin-bottom:6px;">{label_html}{valor_html}</div>'


def secao(titulo: str, sub: str = "") -> None:
    subhtml = f'<span style="font-size:12px;color:#9CA3AF;font-weight:500;margin-left:12px;">{sub}</span>' if sub else ""
    titulo_html = f'<span style="font-family:\'Manrope\',sans-serif;font-size:16px;font-weight:700;color:#012869;letter-spacing:-0.2px;">{titulo}</span>'
    st.markdown(
        f'<div style="margin:32px 0 12px 0;padding-bottom:8px;border-bottom:1px solid #E5E7EB;">{titulo_html}{subhtml}</div>',
        unsafe_allow_html=True,
    )


def data_por_extenso(d: date) -> str:
    txt = d.strftime("%d de %B de %Y")
    for en, pt in MESES_PT.items():
        txt = txt.replace(en, pt)
    return txt


# ==========================================================
# 🎨 CABEÇALHO
# ==========================================================
render_hero(
    titulo="📜 Gestão de Retornos",
    subtitulo="Importe o arquivo e obtenha o relatório executivo automaticamente.",
    badge="Relatório Executivo",
)

# ==========================================================
# 📁 UPLOAD
# ==========================================================
secao("Fonte de Dados", "importe o arquivo para iniciar")

up_c1, up_c2 = st.columns([3, 2])
with up_c1:
    arquivo_principal = st.file_uploader(
        "Arquivo de atividades (XLSX, XLS ou CSV)",
        type=["xlsx", "xls", "csv"],
        label_visibility="visible",
    )
with up_c2:
    st.markdown(
        '<div style="padding:16px 20px;background:#F8FAFC;border-left:3px solid #012869;border-radius:6px;margin-top:28px;">'
        '<div style="font-size:12px;color:#6B7280;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">Processamento automático</div>'
        '<div style="font-size:13px;color:#374151;line-height:1.5;">O sistema aplica limpeza, filtros, enriquecimento e gera o Excel pronto para envio.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

if not arquivo_principal:
    st.markdown("<br>", unsafe_allow_html=True)
    render_insight(
        "Aguardando upload do **arquivo de atividades** para iniciar o processamento.",
        tipo="info",
    )
    st.stop()

# ==========================================================
# 📥 PIPELINE AUTOMÁTICO — TUDO NOS BASTIDORES
# ==========================================================
try:
    bytes_arquivo = arquivo_principal.read()
    df, stats_leitura = carregar_arquivo(bytes_arquivo, arquivo_principal.name)
except Exception as e:
    render_insight(f"Falha no processamento: `{e}`", tipo="critico")
    st.stop()

linhas_originais = len(df)

# Identifica colunas
col_data = identificar_coluna(df, NOMES_DATA)
col_cred = identificar_coluna(df, NOMES_CRED)
col_status = identificar_coluna(df, NOMES_STATUS)
col_login = identificar_coluna(df, NOMES_LOGIN)
col_contrato = identificar_coluna(df, NOMES_CONTRATO)
col_tipo = identificar_coluna(df, NOMES_TIPO_ATIV)

if not col_data:
    render_insight(
        "❌ Não foi possível identificar a coluna de **Data** no arquivo. "
        "Verifique o layout do arquivo importado.",
        tipo="critico",
    )
    st.stop()

# Converte data
df[col_data] = converter_data_robusto(df[col_data])

if int(df[col_data].notna().sum()) == 0:
    render_insight(f"Não foi possível converter **{col_data}** para data.", tipo="critico")
    st.stop()

# ── AUTOMÁTICO: Limpeza ──
df, stats_limpeza = aplicar_limpeza_padrao(df, col_contrato, col_status)

# ── AUTOMÁTICO: Filtro por Tipo = Retorno Credenciada ──
stats_retorno = {"retornos_encontrados": len(df), "removidas": 0}
if col_tipo:
    df, stats_retorno = filtrar_retorno_credenciada(df, col_tipo)
    if stats_retorno["retornos_encontrados"] == 0:
        render_insight(
            f"Nenhum registro do tipo **'{VALOR_RETORNO_CREDENCIADA}'** foi encontrado no arquivo.",
            tipo="critico",
        )
        st.stop()

if df.empty:
    render_insight("Nenhum registro restou após o processamento automático.", tipo="critico")
    st.stop()

# ── AUTOMÁTICO: Enriquecimento com Google Sheets ──
df, stats_enriq = enriquecer_automatico(df, col_login)

# ==========================================================
# 🔎 FILTROS (apenas Data e Status)
# ==========================================================
secao("Filtros", "seleção do período e status")

data_min = df[col_data].min()
data_max = df[col_data].max()

if pd.isna(data_min) or pd.isna(data_max):
    render_insight("Sem datas válidas no arquivo.", tipo="alerta")
    st.stop()

data_min_dt: date = pd.Timestamp(data_min).date()
data_max_dt: date = pd.Timestamp(data_max).date()
hoje: date = date.today()
default_date: date = hoje if data_min_dt <= hoje <= data_max_dt else data_max_dt

filt_c1, filt_c2 = st.columns([1, 2])

with filt_c1:
    data_sel_raw = st.date_input(
        "📅 Data de referência",
        value=default_date,
        min_value=data_min_dt,
        max_value=data_max_dt,
    )
    data_sel: date = data_sel_raw[0] if isinstance(data_sel_raw, tuple) else cast(date, data_sel_raw)

with filt_c2:
    status_sel: list[str] = []
    if col_status:
        todos_status = sorted(str(x) for x in df[col_status].dropna().unique().tolist())
        status_sel = st.multiselect(
            "📌 Status (vazio = todos)",
            todos_status,
            default=[],
        )

# Aplica filtros
df_filt = df[df[col_data].dt.date == data_sel].copy()
if status_sel and col_status:
    df_filt = df_filt[df_filt[col_status].isin(status_sel)]

# ==========================================================
# 📊 PAINEL EXECUTIVO
# ==========================================================
secao(f"Painel Executivo — {data_por_extenso(data_sel)}", "indicadores do dia")

metricas = gerar_metricas(df_filt, col_status)

if df_filt.empty:
    render_insight(
        "Nenhum retorno para o período selecionado. Ajuste os filtros acima.",
        tipo="alerta",
    )
    st.stop()

# ── KPIs principais ──
k1, k2, k3, k4 = st.columns(4)
render_kpi(k1, "Retornos", f"{int(metricas['total']):,}", "atividades no dia", tema="azul")
render_kpi(k2, "Conclusão", f"{metricas['taxa_conclusao']:.1f}%", "taxa de efetividade", tema="verde")
render_kpi(k3, "Não realizadas", f"{int(metricas['canceladas']):,}", "canceladas / improdutivas", tema="vermelho")
render_kpi(k4, "Pendentes", f"{int(metricas['pendentes']):,}", "aguardando retorno", tema="cinza")

# ── Concluídas em pill ──
concluidas_pill = stat_pill("Concluídas", f"{int(metricas['concluidas']):,}", COR_SUCESSO)
st.markdown(f'<div style="margin-top:16px;">{concluidas_pill}</div>', unsafe_allow_html=True)

# ==========================================================
# 📈 DISTRIBUIÇÃO POR STATUS
# ==========================================================
if col_status:
    secao("Distribuição por Status", "composição percentual")

    dist_status = df_filt[col_status].value_counts().reset_index()
    dist_status.columns = ["Status", "Quantidade"]
    total_dist = int(dist_status["Quantidade"].sum())
    dist_status["% do Total"] = (dist_status["Quantidade"] / total_dist * 100).round(1)

    for _, row in dist_status.head(8).iterrows():
        pct = float(row["% do Total"])
        status_lower = str(row["Status"]).lower()
        cor = (
            COR_SUCESSO if any(w in status_lower for w in ("conclu", "execut", "finaliz"))
            else COR_ALERTA if any(w in status_lower for w in ("cancel", "improd"))
            else COR_NEUTRO
        )
        linha_header = f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:5px;"><span style="color:#374151;font-weight:600;">{row["Status"]}</span><span style="color:#6B7280;font-variant-numeric:tabular-nums;">{int(row["Quantidade"]):,} <span style="color:#9CA3AF;">·</span> {pct:.1f}%</span></div>'
        linha_bar = f'<div style="background:#F1F5F9;border-radius:3px;height:6px;overflow:hidden;"><div style="background:{cor};width:{pct}%;height:100%;border-radius:3px;"></div></div>'
        st.markdown(
            f'<div style="margin-bottom:12px;">{linha_header}{linha_bar}</div>',
            unsafe_allow_html=True,
        )

# ==========================================================
# 🔍 BASE DETALHADA
# ==========================================================
secao("Base Detalhada", f"{len(df_filt):,} registros filtrados")

with st.expander("Visualizar registros"):
    render_dataframe(df_filt, height=460)

# ==========================================================
# 📤 EXPORTAÇÃO
# ==========================================================
secao("Distribuição", "download do relatório")

if col_cred and col_cred in df_filt.columns:
    dfs_por_grupo: dict[str, pd.DataFrame] = {
        str(grupo): grp for grupo, grp in df_filt.groupby(col_cred)
    }
else:
    dfs_por_grupo = {"Retornos": df_filt.copy()}

excel_bytes = gerar_excel_multi_abas(dfs_por_grupo, df_filt.copy())
nome_base = f"retornos_{data_sel.strftime('%Y%m%d')}"

exp_c1, exp_c2 = st.columns(2)
with exp_c1:
    st.download_button(
        f"📊 Baixar Excel · {len(dfs_por_grupo) + 1} abas",
        data=excel_bytes,
        file_name=f"{nome_base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
with exp_c2:
    csv = df_filt.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "📄 Baixar CSV consolidado",
        data=csv,
        file_name=f"{nome_base}.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.caption(
    f"Excel: aba **Consolidado** + **{len(dfs_por_grupo)}** aba(s) de detalhamento."
)

# ==========================================================
# 🏁 RODAPÉ
# ==========================================================
rodape_html = f'<div style="text-align:center;color:#9CA3AF;font-size:11px;padding:24px 0 8px 0;margin-top:32px;border-top:1px solid #F1F5F9;">Gerado em {date.today().strftime("%d/%m/%Y")} <span style="color:#D1D5DB;margin:0 8px;">·</span> {arquivo_principal.name}</div>'
st.markdown(rodape_html, unsafe_allow_html=True)