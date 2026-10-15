"""
p_atendimento.py
================
App standalone para Primeiro Atendimento de OS.

Funcionalidades:
    - Upload central de Excel/CSV
    - Merge com Google Sheets (lista_ativos) — Técnico + Monitor + Base
    - Limpeza automática (contratos vazios + suspensos)
    - 🚙 PRIMEIRO HORÁRIO por técnico (coluna "Início" + status iniciado)
    - 🏆 Ranking de técnicos (mais madrugadores)
    - 👔 Ranking de monitores (média do primeiro atendimento)
    - KPIs executivos
    - Exportação Excel/CSV

Uso:
    streamlit run p_atendimento.py

A página segue o padrão do portal (``components.dashboards`` +
``components.layout_pagina``) e consome a camada compartilhada de serviços
(``services.planilhas``/``hierarquia``/``texto``/``dados_sessao``).
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any

import pandas as pd
import streamlit as st

from components.componentes import aplicar_estilo as aplicar_estilo_ds
from components.componentes import render_hero, render_insight, render_kpi
from components.css_paginas import aplicar_css_cartao_upload
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.layout_pagina import cabecalho_secao
from components.sidebar import render_page_sidebar_theme_selector
from config.settings import obter_sheet_id_ativos
from services.dados_sessao import CHAVE_MEMORIA, obter_dataframe
from services.hierarquia import hierarquia_da_sessao
from services.planilhas import gerar_excel as gerar_excel_servico
from services.planilhas import ler_bytes
from services.texto import formatar_inteiro
from services.texto import normalizar_texto as normalizar_texto_servico

logger = logging.getLogger(__name__)

#: Seções ancoradas do sumário (títulos usados em ``cabecalho_secao``).
SECOES_PAGINA: tuple[str, ...] = (
    "Panorama Geral",
    "Ranking de Técnicos — Primeiro Horário de Saída",
    "Ranking de Monitores — Média de Primeiro Atendimento",
    "Contratos Pendentes para Rota",
    "Exportação",
)

#: A hierarquia compartilhada usa colunas canônicas em caixa alta; o merge desta
#: página espera o case histórico.
COLUNAS_HIERARQUIA_LEGADAS: dict[str, str] = {
    "LOGIN": "Login",
    "TÉCNICO": "Técnico",
    "MONITOR": "Monitor",
    "BASE": "Base",
}

# ═══════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════
st.set_page_config(
    page_title="Primeiro Atendimento | TOTALE",
    page_icon="🚙",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ═══════════════════════════════════════════════════════
# CSS CORPORATIVO
# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════
CONTRATO_VALORES_VAZIOS = {
    "",
    "NAN",
    "NONE",
    "N/A",
    "NA",
    "-",
    "0",
    "NULL",
    "<NA>",
}


# ═══════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════
# COMPONENTES (adaptadores finos do Design System)
# ═══════════════════════════════════════════════════════
#: Cores usadas nos KPIs desta página → temas do Design System.
TEMAS_POR_COR: dict[str, str] = {
    "#012869": "azul",
    "#0284C7": "azul",
    "#059669": "verde",
    "#F37C04": "laranja",
    "#7C3AED": "roxo",
    "#475569": "cinza",
    "#B91C1C": "vermelho",
}


def _kpi(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    cor: str = "#012869",
    icone: str = "",
) -> None:
    """KPI da página → :func:`components.componentes.render_kpi`.

    O Design System pinta o cartão pelo *tema* (não por hex avulso): o mapa acima
    traduz as cores históricas desta página para os temas equivalentes.
    """
    render_kpi(
        col,
        label,
        valor,
        sub=sub,
        tema=TEMAS_POR_COR.get(str(cor).upper(), "azul"),
        icone=icone,
    )


# ═══════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════
#: Normalização de texto delegada a :func:`services.texto.normalizar_texto`
#: (maiúscula, sem acentos e sem espaços sobrando — fonte única do portal).
normalizar_texto = normalizar_texto_servico


def buscar_coluna(df: pd.DataFrame, palavras_chave: list[str]) -> str | None:
    if df is None or df.empty:
        return None
    cols_norm = {normalizar_texto(c): c for c in df.columns}
    for palavra in palavras_chave:
        pn = normalizar_texto(palavra)
        for cn, co in cols_norm.items():
            if pn in cn:
                return co
    return None


def buscar_coluna_exata(df: pd.DataFrame, nome: str) -> str | None:
    if df is None or df.empty:
        return None
    nome_norm = normalizar_texto(nome)
    for c in df.columns:
        if normalizar_texto(c) == nome_norm:
            return c
    return None


#: Exportação delegada a :func:`services.planilhas.gerar_excel` (cabeçalho
#: corporativo, larguras seguras para NaN e linha congelada).
gerar_excel_padrao = gerar_excel_servico


#: Formatação de inteiros delegada a :func:`services.texto.formatar_inteiro`.
fmt_int = formatar_inteiro


def fmt_hora(t: time) -> str:
    """Formata datetime.time como HH:MM:SS."""
    if t is None:
        return "-"
    if isinstance(t, str):
        return t
    try:
        import math

        import numpy as np

        if t is getattr(pd, "NaT", None):
            return "-"
        if isinstance(t, float) and math.isnan(t):
            return "-"
        if isinstance(t, (np.floating,)) and np.isnan(t):
            return "-"
    except Exception:
        pass

    return t.strftime("%H:%M:%S")


# ═══════════════════════════════════════════════════════
# GOOGLE SHEETS — MERGE COM LISTA_ATIVOS (CORRIGIDO)
# ═══════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner="🔗 Conectando com Google Sheets...")
def carregar_lista_ativos() -> pd.DataFrame:
    """Lista de ativos (Login | Técnico | Monitor | Base) via camada compartilhada.

    Antes a página abria o Sheets por conta própria e reimplementava a limpeza do
    login; hoje delega a :func:`services.hierarquia.hierarquia_da_sessao`, que já
    normaliza colunas, remove o ``.0`` do Excel e degrada graciosamente sem rede
    (devolve DataFrame vazio). O cache continua aqui para o botão *Reiniciar*
    conseguir limpar a leitura desta página.
    """
    hierarquia = hierarquia_da_sessao(obter_sheet_id_ativos(), ttl=600)
    if hierarquia.empty:
        return pd.DataFrame()
    saida = hierarquia.rename(columns=COLUNAS_HIERARQUIA_LEGADAS)
    colunas = [c for c in ("Login", "Técnico", "Monitor", "Base") if c in saida.columns]
    if "Login" not in colunas:
        st.warning("⚠️ A coluna 'Login' não foi encontrada no Google Sheets.")
        return pd.DataFrame()
    saida = saida[colunas].copy()
    saida["Login"] = (
        saida["Login"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.upper()
    )
    saida = saida.drop_duplicates(subset=[["Login"]], keep="last")
    return saida[saida["Login"] != ""].reset_index(drop=True)


def aplicar_merge_ativos(
    df: pd.DataFrame,
    df_ativos: pd.DataFrame,
    col_login: str | None,
) -> tuple[pd.DataFrame, dict]:
    """Faz merge da base carregada com a lista_ativos."""
    diag = {
        "aplicado": False,
        "matches": 0,
        "sem_match": 0,
        "total": len(df),
    }

    if df_ativos.empty or not col_login or col_login not in df.columns:
        return df, diag

    df = df.copy()

    df["_LOGIN_KEY"] = (
        df[col_login].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.upper()
    )

    for c in ["Técnico", "Monitor", "Base"]:
        if c in df.columns:
            df = df.rename(columns={c: f"{c}_original"})

    df = df.merge(
        df_ativos,
        left_on="_LOGIN_KEY",
        right_on="Login",
        how="left",
        suffixes=("", "_gs"),
    )

    df = df.drop(columns=["_LOGIN_KEY", "Login"], errors="ignore")

    if "Técnico" in df.columns:
        matches = int(df["Técnico"].notna().sum())
        diag["matches"] = matches
        diag["sem_match"] = len(df) - matches
        diag["aplicado"] = True

    return df, diag


# ═══════════════════════════════════════════════════════
# CARREGAMENTO E LIMPEZA
# ═══════════════════════════════════════════════════════
@st.cache_data(show_spinner="🚗 Processando arquivo...")
def carregar_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Leitura do upload delegada a :func:`services.planilhas.ler_bytes`.

    Mantém o cache por conteúdo e o contrato da página (tudo como texto), sem
    repetir a detecção de separador/encoding que o serviço já faz.
    """
    return ler_bytes(file_bytes, filename, dtype=str)


# ═══════════════════════════════════════════════════════
# CLASSIFICAÇÃO
# ═══════════════════════════════════════════════════════
def classificar_pendentes(df: pd.DataFrame, col_status: str) -> pd.Series:
    if col_status not in df.columns:
        return pd.Series([True] * len(df), index=df.index)

    s = df[col_status].fillna("").astype(str).str.upper()

    termos_pendentes = [
        "PENDENTE",
        "PENDING",
        "ABERTO",
        "EM ABERTO",
        "AGUARDAND",
        "AGENDAD",
        "NOVO",
        "NAO INICIAD",
        "NAO INICIA",
        "AGUARDA",
    ]
    termos_concluidos = [
        "EXECUTAD",
        "CONCLUID",
        "FINALIZAD",
        "REALIZAD",
        "ATENDID",
        "CANCELAD",
        "SUCESSO",
        "IMPRODUTIV",
    ]

    mask_pendente = s.apply(lambda v: any(t in v for t in termos_pendentes))
    mask_concluido = s.apply(lambda v: any(t in v for t in termos_concluidos))

    return mask_pendente | (~mask_concluido & (s == ""))


def limpar_base(
    df: pd.DataFrame,
    col_contrato: str | None,
    col_status_atividade: str | None,
) -> tuple[pd.DataFrame, dict]:
    df_clean = df.copy()
    diag = {
        "total_inicial": len(df),
        "contratos_vazios": 0,
        "suspensos": 0,
        "total_final": 0,
    }

    if col_contrato and col_contrato in df_clean.columns:
        contrato_norm = (
            df_clean[col_contrato]
            .astype("string")
            .str.replace("\u00a0", " ", regex=False)
            .str.strip()
            .str.upper()
        )
        mask_vazio = (
            contrato_norm.isna()
            | contrato_norm.eq("")
            | contrato_norm.isin(CONTRATO_VALORES_VAZIOS)
        )
        diag["contratos_vazios"] = int(mask_vazio.sum())
        df_clean = df_clean.loc[~mask_vazio].copy()

    if col_status_atividade and col_status_atividade in df_clean.columns:
        status_norm = df_clean[col_status_atividade].fillna("").astype(str).str.upper()
        mask_suspenso = status_norm.str.contains(r"SUSPEN|BLOQUEAD|INATIV", regex=True, na=False)
        diag["suspensos"] = int(mask_suspenso.sum())
        df_clean = df_clean.loc[~mask_suspenso].copy()

    diag["total_final"] = len(df_clean)
    return df_clean.reset_index(drop=True), diag


# ═══════════════════════════════════════════════════════
# 🚗 PRIMEIRO HORÁRIO POR TÉCNICO
# ═══════════════════════════════════════════════════════
def calcular_primeiro_horario_tecnico(
    df: pd.DataFrame,
    col_tecnico: str | None,
    col_monitor: str | None,
    col_status_atividade: str | None,
    col_inicio: str | None,
) -> pd.DataFrame:
    if not col_tecnico or col_tecnico not in df.columns:
        return pd.DataFrame()
    if not col_status_atividade or col_status_atividade not in df.columns:
        return pd.DataFrame()
    if not col_inicio or col_inicio not in df.columns:
        return pd.DataFrame()

    status_norm = df[col_status_atividade].fillna("").astype(str).str.upper()
    termos_iniciado = [
        "INICIAD",
        "INICIA",
        "EM ANDAMENTO",
        "ANDAMENTO",
        "EXECUTANDO",
        "EM EXECUCAO",
        "EM EXECUÇÃO",
        "TRABALHANDO",
        "ATIVO",
    ]
    mask_iniciado = status_norm.apply(lambda v: any(t in v for t in termos_iniciado))

    df_iniciados = df.loc[mask_iniciado].copy()
    if df_iniciados.empty:
        return pd.DataFrame()

    df_iniciados["_INICIO"] = pd.to_datetime(
        df_iniciados[col_inicio],
        errors="coerce",
        dayfirst=True,
    )

    df_iniciados = df_iniciados.dropna(subset=["_INICIO"])
    if df_iniciados.empty:
        return pd.DataFrame()

    agg_dict = {
        "Primeiro_Inicio": ("_INICIO", "min"),
        "Status_Original": (col_status_atividade, "first"),
        "Qtd_Atividades": (col_status_atividade, "count"),
    }

    if col_monitor and col_monitor in df_iniciados.columns:
        agg_dict["Monitor"] = (col_monitor, "first")

    df_primeiro = (
        df_iniciados.sort_values(["_INICIO"])
        .groupby(col_tecnico)
        .agg(**agg_dict)
        .reset_index()
        .rename(columns={col_tecnico: "Técnico"})
    )

    df_primeiro["Data"] = df_primeiro["Primeiro_Inicio"].dt.strftime("%d/%m/%Y")
    df_primeiro["Hora Início"] = df_primeiro["Primeiro_Inicio"].dt.strftime("%H:%M:%S")

    df_primeiro = df_primeiro.sort_values("Primeiro_Inicio").reset_index(drop=True)
    df_primeiro["Rank"] = range(1, len(df_primeiro) + 1)

    cols_finais = ["Rank", "Técnico"]
    if "Monitor" in df_primeiro.columns:
        cols_finais.append("Monitor")
    cols_finais.extend(["Data", "Hora Início", "Status_Original", "Qtd_Atividades"])

    df_final = df_primeiro[cols_finais].rename(
        columns={
            "Status_Original": "Status",
            "Qtd_Atividades": "Qtd. Atividades",
        }
    )

    df_final["_datetime"] = df_primeiro["Primeiro_Inicio"].values

    return df_final


# ═══════════════════════════════════════════════════════
# 👔 RANKING DE MONITORES (média do primeiro atendimento)
# ═══════════════════════════════════════════════════════
def calcular_ranking_monitores(
    df_primeiro_horario: pd.DataFrame,
) -> pd.DataFrame:
    if df_primeiro_horario.empty:
        return pd.DataFrame()
    if "Monitor" not in df_primeiro_horario.columns:
        return pd.DataFrame()
    if "_datetime" not in df_primeiro_horario.columns:
        return pd.DataFrame()

    df_work = df_primeiro_horario.copy()

    df_work["_segundos"] = df_work["_datetime"].apply(
        lambda dt: dt.hour * 3600 + dt.minute * 60 + dt.second if pd.notna(dt) else None
    )

    df_work = df_work[
        df_work["Monitor"].notna() & (df_work["Monitor"].astype(str).str.strip() != "")
    ].copy()

    if df_work.empty:
        return pd.DataFrame()

    df_mon = (
        df_work.groupby("Monitor")
        .agg(
            Media_Segundos=("_segundos", "mean"),
            Primeiro=("_segundos", "min"),
            Ultimo=("_segundos", "max"),
            Qtd_Tecnicos=("Técnico", "nunique"),
            Total_Atividades=("Qtd. Atividades", "sum"),
        )
        .reset_index()
    )

    def segundos_para_hora(seg: float) -> str:
        if pd.isna(seg):
            return "-"
        seg = int(seg)
        h = seg // 3600
        m = (seg % 3600) // 60
        s = seg % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    df_mon["Média do Primeiro Atend."] = df_mon["Media_Segundos"].apply(segundos_para_hora)
    df_mon["Mais Cedo"] = df_mon["Primeiro"].apply(segundos_para_hora)
    df_mon["Mais Tarde"] = df_mon["Ultimo"].apply(segundos_para_hora)

    df_mon = df_mon.sort_values("Media_Segundos").reset_index(drop=True)
    df_mon["Rank"] = range(1, len(df_mon) + 1)

    return df_mon[
        [
            "Rank",
            "Monitor",
            "Média do Primeiro Atend.",
            "Mais Cedo",
            "Mais Tarde",
            "Qtd_Tecnicos",
            "Total_Atividades",
        ]
    ].rename(
        columns={
            "Qtd_Tecnicos": "Qtd. Técnicos",
            "Total_Atividades": "Total Atividades",
        }
    )


# ═══════════════════════════════════════════════════════
# BADGES E CORES
# ═══════════════════════════════════════════════════════
def rank_medal(rank: int) -> str:
    if rank == 1:
        return "🥇"
    if rank == 2:
        return "🥈"
    if rank == 3:
        return "🥉"
    return f"#{rank}"


def formatar_ranking_para_exibicao(df: pd.DataFrame, col_rank: str = "Rank") -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    if "_datetime" in df.columns:
        df = df.drop(columns=["_datetime"])
    df[col_rank] = df[col_rank].apply(rank_medal)
    return df


def aplicar_cor_horario(valor: Any) -> str:
    """Aplica cores corporativas baseado no horário exato (HH:MM:SS)"""
    if pd.isna(valor) or valor == "-" or not isinstance(valor, str):
        return ""

    try:
        horario = valor[:8].strip()

        if len(horario) == 7 and horario[1] == ":":
            horario = "0" + horario

        if horario <= "08:30:00":
            return "background-color: #D1FAE5; color: #065F46; font-weight: 600;"
        elif horario < "08:40:00":
            return "background-color: #FEF3C7; color: #92400E; font-weight: 600;"
        else:
            return "background-color: #FEE2E2; color: #991B1B; font-weight: 600;"
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════
# APP PRINCIPAL
# ═══════════════════════════════════════════════════════
def main() -> None:
    # O shell principal aplica o tema no app; a chamada também mantém a página
    # operável quando executada isoladamente.
    aplicar_estilo_ds()
    render_page_sidebar_theme_selector()
    aplicar_css_cartao_upload()

    abrir_dashboard(
        "Painel de Primeiro Atendimento",
        secoes=SECOES_PAGINA,
        hero=render_hero,
        hero_kwargs={
            "titulo": "Painel de Primeiro Atendimento",
            "subtitulo": (
                "Gestão Operacional de Ordens de Serviço · "
                "Merge automático via Google Sheets"
            ),
            "badge": "SISTEMA TOTALE",
        },
        chips={"Fontes": "Upload + lista de ativos"},
    )

    with st.sidebar:
        st.markdown("### ⚙️ Painel de Controle")

        if st.button("🔄 Reiniciar Aplicação", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            carregar_lista_ativos.clear()
            carregar_arquivo.clear()
            st.rerun()

    # ─────────────────────────────────────────────────
    # UPLOAD
    # ─────────────────────────────────────────────────
    st.markdown(
        "**Como funciona:** envie um Excel (.xlsx, .xls) ou CSV com as O.S. — a base é "
        "enriquecida com a lista de ativos do Google Sheets (Técnico + Monitor + Base)."
    )

    arq = st.file_uploader(
        "Selecione o arquivo",
        type=["xlsx", "xls", "csv"],
        label_visibility="collapsed",
    )

    if not arq:
        with st.sidebar:
            st.divider()
            st.caption("💡 Aguardando upload de arquivo...")

        st.markdown("### 📋 Como funciona")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(
                '<div style="background:white;padding:20px;border-radius:10px;'
                "border-left:4px solid #012869;box-shadow:0 2px 8px rgba(0,0,0,0.06);"
                'min-height:170px;">'
                '<div style="font-size:32px;margin-bottom:8px;">🚙</div>'
                '<h4 style="margin:0 0 8px 0;color:#012869;">Upload da Base</h4>'
                '<p style="margin:0;color:#64748B;font-size:13px;">'
                "Envie o arquivo Excel/CSV com as OSs. O sistema fará o merge "
                "automático com a lista de técnicos ativos.</p>"
                "</div>",
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                '<div style="background:white;padding:20px;border-radius:10px;'
                "border-left:4px solid #F37C04;box-shadow:0 2px 8px rgba(0,0,0,0.06);"
                'min-height:170px;">'
                '<div style="font-size:32px;margin-bottom:8px;">🔗</div>'
                '<h4 style="margin:0 0 8px 0;color:#F37C04;">Enriquecimento</h4>'
                '<p style="margin:0;color:#64748B;font-size:13px;">'
                "Merge automático com <b>Google Sheets</b> traz Técnico, "
                "Monitor e Base pelo Login.</p>"
                "</div>",
                unsafe_allow_html=True,
            )

        with col3:
            st.markdown(
                '<div style="background:white;padding:20px;border-radius:10px;'
                "border-left:4px solid #059669;box-shadow:0 2px 8px rgba(0,0,0,0.06);"
                'min-height:170px;">'
                '<div style="font-size:32px;margin-bottom:8px;">🏆</div>'
                '<h4 style="margin:0 0 8px 0;color:#059669;">Rankings</h4>'
                '<p style="margin:0;color:#64748B;font-size:13px;">'
                "Ranking de SLAs operacionais e média de horário "
                "de saída por monitor.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        return

    # ─────────────────────────────────────────────────
    # PROCESSAMENTO
    # ─────────────────────────────────────────────────
    try:
        df_raw = carregar_arquivo(arq.getvalue(), arq.name)
    except Exception as e:
        render_insight(f"**Erro ao ler arquivo:** `{e}`", tipo="critico")
        return

    if df_raw.empty:
        render_insight("**Arquivo vazio.**", tipo="alerta")
        return

    # Detecção de colunas
    col_contrato = buscar_coluna(df_raw, ["CONTRATO", "NUM CONTRATO", "NUMERO", "N CONTRATO"])
    col_status = buscar_coluna(
        df_raw, ["STATUS DA O.S", "STATUS OS", "STATUS", "SITUACAO", "SITUAÇÃO"]
    )
    col_status_atividade = buscar_coluna(df_raw, ["STATUS DA ATIVIDADE", "STATUS ATIVIDADE"])
    col_cliente = buscar_coluna(df_raw, ["CLIENTE", "NOME", "RAZAO SOCIAL", "RAZÃO SOCIAL"])
    col_tipo = buscar_coluna(df_raw, ["TIPO", "SERVICO", "SERVIÇO"])
    col_regiao = buscar_coluna(df_raw, ["REGIAO", "REGIÃO", "CIDADE", "UF", "ESTADO"])
    col_login = buscar_coluna(
        df_raw,
        ["LOGIN DO TÉCNICO", "LOGIN DO TECNICO", "LOGIN", "USUÁRIO", "MATRÍCULA"],
    )

    col_inicio = buscar_coluna_exata(df_raw, "Início")
    if not col_inicio:
        col_inicio = buscar_coluna(df_raw, ["INICIO", "INÍCIO"])

    # Limpeza
    df, diag_limpeza = limpar_base(
        df_raw,
        col_contrato=col_contrato,
        col_status_atividade=col_status_atividade,
    )

    # Merge com Google Sheets
    df_ativos = carregar_lista_ativos()
    df, diag_merge = aplicar_merge_ativos(df, df_ativos, col_login)
    # A base limpa fica na chave compartilhada: outras páginas e o resumo da
    # barra lateral leem dela (services.dados_sessao), sem recalcular.
    st.session_state[CHAVE_MEMORIA] = df

    col_tecnico = (
        "Técnico"
        if "Técnico" in df.columns
        else buscar_coluna(df_raw, ["TECNICO", "TÉCNICO", "PROFISSIONAL", "NOME EQUIPE"])
    )
    col_monitor = "Monitor" if "Monitor" in df.columns else None
    col_base_final = "Base" if "Base" in df.columns else col_regiao

    with st.sidebar:
        st.divider()
        st.markdown("### 📊 Base Carregada")
        st.caption(f"📄 **Arquivo:** `{arq.name}`")
        base_limpa = obter_dataframe(CHAVE_MEMORIA)
        registros = len(base_limpa) if isinstance(base_limpa, pd.DataFrame) else len(df)
        st.caption(f"🔢 **Registros:** {fmt_int(registros)} após limpeza e merge")

    if df.empty:
        render_insight("Após a limpeza, não restou nenhum registro válido.", tipo="critico")
        return

    if col_status:
        mask_pend = classificar_pendentes(df, col_status)
        df_pend = df[mask_pend].copy().reset_index(drop=True)
    else:
        df_pend = df.copy()

    # ─────────────────────────────────────────────────
    # KPIs PRINCIPAIS
    # ─────────────────────────────────────────────────
    total = len(df)
    pendentes = len(df_pend)
    executados = total - pendentes
    pct_pend = (pendentes / total * 100) if total > 0 else 0

    cabecalho_secao("Panorama Geral", icone="monitoring", subtitulo="KPIs")

    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, "Base Válida", fmt_int(total), sub="após limpeza", cor="#059669", icone="🚗")
    _kpi(
        c2,
        "Pendentes",
        fmt_int(pendentes),
        sub=f"{pct_pend:.1f}% do total",
        cor="#F37C04",
        icone="⏳",
    )
    _kpi(
        c3,
        "Executadas/Fechadas",
        fmt_int(executados),
        sub=f"{100 - pct_pend:.1f}% do total",
        cor="#012869",
        icone="✅",
    )

    if col_monitor and col_monitor in df.columns:
        monitores_qtd = df[col_monitor].dropna().nunique()
        _kpi(
            c4,
            "Monitores",
            str(monitores_qtd),
            sub="na base",
            cor="#7C3AED",
            icone="👔",
        )
    elif col_base_final:
        regioes = df[col_base_final].dropna().nunique()
        _kpi(
            c4,
            "Regiões/Bases",
            str(regioes),
            sub="com pendências",
            cor="#7C3AED",
            icone="🌎",
        )
    else:
        _kpi(
            c4,
            "Colunas",
            str(len(df.columns)),
            sub="detectadas",
            cor="#7C3AED",
            icone="📋",
        )

    # ─────────────────────────────────────────────────
    # 🏆 RANKING DE TÉCNICOS (primeiro horário)
    # ─────────────────────────────────────────────────
    df_primeiro_horario = calcular_primeiro_horario_tecnico(
        df,
        col_tecnico=col_tecnico,
        col_monitor=col_monitor,
        col_status_atividade=col_status_atividade,
        col_inicio=col_inicio,
    )

    cabecalho_secao(
        "Ranking de Técnicos — Primeiro Horário de Saída",
        icone="emoji_events",
        badge=(
            f"{len(df_primeiro_horario)} técnicos"
            if not df_primeiro_horario.empty
            else "sem dados"
        ),
    )

    if df_primeiro_horario.empty:
        motivos = []
        if not col_tecnico:
            motivos.append("coluna de <b>Técnico</b> não detectada")
        if not col_status_atividade:
            motivos.append("coluna de <b>Status da Atividade</b> não detectada")
        if not col_inicio:
            motivos.append(
                "coluna <b>Início</b> não encontrada (nome esperado: <code>Início</code>)"
            )
        if not motivos:
            motivos.append(
                "nenhum registro com status <code>INICIADO</code>, <code>EM ANDAMENTO</code> ou similar"
            )

        render_insight(
            "⚠️ <b>Não foi possível calcular o ranking:</b><br>"
            + "<br>".join(f"• {m}" for m in motivos),
            tipo="alerta",
        )
    else:
        kh1, kh2, kh3 = st.columns(3)

        tec_iniciaram = len(df_primeiro_horario)
        primeiro = df_primeiro_horario.iloc[0]
        ultimo = df_primeiro_horario.iloc[-1]

        _kpi(
            kh1,
            "Primeiro Início (Técnico)",
            primeiro["Hora Início"],
            sub=str(primeiro["Técnico"])[:30],
            cor="#0284C7",
            icone="⏱️",
        )
        _kpi(
            kh2,
            "Último Início (Técnico)",
            ultimo["Hora Início"],
            sub=str(ultimo["Técnico"])[:30],
            cor="#475569",
            icone="📉",
        )
        _kpi(
            kh3,
            "Volume em Rota",
            str(tec_iniciaram),
            sub="técnicos com status iniciado",
            cor="#059669",
            icone="📈",
        )

        st.markdown("")

        df_exibir_tec = formatar_ranking_para_exibicao(df_primeiro_horario)
        df_exibir_tec = df_exibir_tec.rename(columns={"Hora Início": "Primeiro Horário"})

        colunas_desejadas = [
            "Rank",
            "Técnico",
            "Monitor",
            "Data",
            "Primeiro Horário",
            "Status",
        ]
        colunas_exibir = [c for c in colunas_desejadas if c in df_exibir_tec.columns]

        df_exibir_tec = df_exibir_tec[colunas_exibir]

        styled_tec = df_exibir_tec.style
        style_func = getattr(styled_tec, "map", None) or getattr(styled_tec, "applymap", None)
        if style_func is not None:
            styled_tec = style_func(aplicar_cor_horario, subset=["Primeiro Horário"])

        st.dataframe(
            styled_tec,
            width="stretch",
            hide_index=True,
            height=400,
            column_config={
                "Rank": st.column_config.TextColumn("Rank", width="small"),
                "Técnico": st.column_config.TextColumn("Técnico", width="medium"),
                "Monitor": (
                    st.column_config.TextColumn("Monitor", width="medium")
                    if "Monitor" in colunas_exibir
                    else None
                ),
                "Data": st.column_config.TextColumn("Data", width="small"),
                "Status": st.column_config.TextColumn("Status", width="medium"),
            },
        )

        col_dl1, col_dl2, _ = st.columns([1, 1, 2])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        with col_dl1:
            st.download_button(
                "📥 **Baixar Excel**",
                data=gerar_excel_padrao(df_exibir_tec, "Ranking_Tecnicos"),
                file_name=f"ranking_tecnicos_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        with col_dl2:
            csv_t = df_exibir_tec.to_csv(index=False, sep=";", encoding="utf-8-sig").encode(
                "utf-8-sig"
            )
            st.download_button(
                "📄 **Baixar CSV**",
                data=csv_t,
                file_name=f"ranking_tecnicos_{timestamp}.csv",
                mime="text/csv",
                width="stretch",
            )

        # ─────────────────────────────────────────────────
        # 👔 RANKING DE MONITORES
        # ─────────────────────────────────────────────────
        df_ranking_monitores = calcular_ranking_monitores(df_primeiro_horario)

        cabecalho_secao(
            "Ranking de Monitores — Média de Primeiro Atendimento",
            icone="badge",
            badge=(
                f"{len(df_ranking_monitores)} monitores"
                if not df_ranking_monitores.empty
                else "sem dados"
            ),
        )

        if df_ranking_monitores.empty:
            render_insight(
                "⚠️ Não foi possível calcular o ranking de monitores. Verifique a coluna <b>Monitor</b>.",
                tipo="alerta",
            )
        else:
            km1, km2, km3 = st.columns(3)
            monitor_madrugador = df_ranking_monitores.iloc[0]

            _kpi(
                km1,
                "Melhor SLA (Monitor)",
                monitor_madrugador["Média do Primeiro Atend."],
                sub=str(monitor_madrugador["Monitor"])[:30],
                cor="#0284C7",
                icone="👤",
            )
            _kpi(
                km2,
                "Cobertura",
                f"{len(df_ranking_monitores)} monitores",
                sub="com equipes ativas",
                cor="#475569",
                icone="📊",
            )
            _kpi(
                km3,
                "Atividades Processadas",
                fmt_int(int(df_ranking_monitores["Total Atividades"].sum())),
                sub="O.S. iniciadas no total",
                cor="#059669",
                icone="📋",
            )

            st.markdown("")

            df_exibir_mon = formatar_ranking_para_exibicao(df_ranking_monitores)

            styled_mon = df_exibir_mon.style
            style_func_mon = getattr(styled_mon, "map", None) or getattr(
                styled_mon, "applymap", None
            )
            if style_func_mon is not None:
                styled_mon = style_func_mon(
                    aplicar_cor_horario, subset=["Média do Primeiro Atend."]
                )

            st.dataframe(
                styled_mon,
                width="stretch",
                hide_index=True,
                height="auto",
                column_config={
                    "Rank": st.column_config.TextColumn("Rank", width="small"),
                    "Monitor": st.column_config.TextColumn("Monitor", width="medium"),
                    "Média do Primeiro Atend.": st.column_config.TextColumn(
                        "Média de Saída",
                        width="small",
                        help="Média do horário do primeiro atendimento dos técnicos",
                    ),
                    "Mais Cedo": st.column_config.TextColumn("Mais Cedo", width="small"),
                    "Mais Tarde": st.column_config.TextColumn("Mais Tarde", width="small"),
                    "Qtd. Técnicos": st.column_config.NumberColumn(
                        "Técnicos", width="small", format="%d"
                    ),
                    "Total Atividades": st.column_config.NumberColumn(
                        "Atividades", width="small", format="%d"
                    ),
                },
            )

            col_dm1, col_dm2, _ = st.columns([1, 1, 2])

            with col_dm1:
                st.download_button(
                    "📥 **Baixar Excel**",
                    data=gerar_excel_padrao(df_exibir_mon, "Ranking_Monitores"),
                    file_name=f"ranking_monitores_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
            with col_dm2:
                csv_m = df_exibir_mon.to_csv(index=False, sep=";", encoding="utf-8-sig").encode(
                    "utf-8-sig"
                )
                st.download_button(
                    "📄 **Baixar CSV**",
                    data=csv_m,
                    file_name=f"ranking_monitores_{timestamp}.csv",
                    mime="text/csv",
                    width="stretch",
                )

    # ─────────────────────────────────────────────────
    # FILTROS + TABELA DE PENDENTES
    # ─────────────────────────────────────────────────
    cabecalho_secao(
        "Contratos Pendentes para Rota",
        icone="local_shipping",
        subtitulo=f"{fmt_int(pendentes)} pendentes",
        ancora=False,
    )

    df_filtrado = df_pend.copy()

    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        if col_base_final and col_base_final in df_filtrado.columns:
            regioes = ["Todas"] + sorted(
                [
                    str(r).strip()
                    for r in df_filtrado[col_base_final].dropna().unique()
                    if str(r).strip()
                ]
            )
            sel_regiao = st.selectbox("🌎 Base/Região", regioes)
            if sel_regiao != "Todas":
                df_filtrado = df_filtrado[
                    df_filtrado[col_base_final].astype(str).str.strip() == sel_regiao
                ]

    with col_f2:
        if col_monitor and col_monitor in df_filtrado.columns:
            monitores = ["Todos"] + sorted(
                [
                    str(m).strip()
                    for m in df_filtrado[col_monitor].dropna().unique()
                    if str(m).strip()
                ]
            )
            sel_monitor = st.selectbox("👔 Monitor", monitores)
            if sel_monitor != "Todos":
                df_filtrado = df_filtrado[
                    df_filtrado[col_monitor].astype(str).str.strip() == sel_monitor
                ]

    with col_f3:
        if col_tecnico and col_tecnico in df_filtrado.columns:
            tecnicos = ["Todos"] + sorted(
                [
                    str(t).strip()
                    for t in df_filtrado[col_tecnico].dropna().unique()
                    if str(t).strip()
                ]
            )
            sel_tecnico = st.selectbox("👤 Técnico", tecnicos)
            if sel_tecnico != "Todos":
                df_filtrado = df_filtrado[
                    df_filtrado[col_tecnico].astype(str).str.strip() == sel_tecnico
                ]

    busca = st.text_input(
        "🔎 Busca livre",
        placeholder="Digite para pesquisar em toda a base...",
    )

    if busca:
        mask_busca = pd.Series(False, index=df_filtrado.index)
        for col in df_filtrado.columns:
            mask_busca |= df_filtrado[col].astype(str).str.contains(busca, case=False, na=False)
        df_filtrado = df_filtrado[mask_busca]

    # Resultado
    pct_apos = (len(df_filtrado) / pendentes * 100) if pendentes > 0 else 0
    st.markdown(
        f'<div class="resultado-base">'
        f'<span class="resultado-label">🚗 Resultado:</span>'
        f'<span class="resultado-badge" style="background:#DBEAFE;color:#1E40AF;border-color:#3B82F6;">'
        f"{fmt_int(len(df_filtrado))} pendentes</span>"
        f'<span class="resultado-count">{pct_apos:.0f}% dos {fmt_int(pendentes)} originais</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    if df_filtrado.empty:
        render_insight("Nenhum registro encontrado com os filtros.", tipo="alerta")
        return

    # Tabela
    colunas_prio = [
        c
        for c in [
            col_contrato,
            col_cliente,
            col_tecnico,
            col_monitor,
            col_base_final,
            col_tipo,
            col_status,
            col_inicio,
        ]
        if c is not None and c in df_filtrado.columns
    ]
    outras = [c for c in df_filtrado.columns if c not in colunas_prio]
    df_exibir = df_filtrado[colunas_prio + outras].copy()

    with st.spinner("Montando tabela de pendentes..."):
        st.dataframe(df_exibir, width="stretch", hide_index=True, height=500)

    # Exportação — bloco padrão do portal (Excel + CSV na última seção ancorada)
    st.caption(
        f"📅 **{datetime.now().strftime('%d/%m/%Y às %H:%M')}** · "
        f"🚗 **{fmt_int(len(df_exibir))}** registros para rota"
    )
    secao_exportacao(
        df_exibir,
        nome_arquivo="rota_pendentes",
        chave="p_atendimento_pendentes",
        titulo="Exportação",
        subtitulo="Lista de contratos pendentes já na ordem oficial de rota.",
        rotulo_secao="Exportar lista para rota",
    )

    # Rodapé no padrão do portal
    fechar_dashboard(texto="Primeiro Atendimento · Ferramenta operacional TOTALE")


if __name__ == "__main__":
    main()
