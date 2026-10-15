"""
pages/retornos.py
================================
Auditoria e Identificação de Dono do Retorno (TOA ↔ Sinapse).

Regras de Negócio:
    1. Base TOA: Filtrar 'Tipo de Atividade.1' == 'Retorno Credenciada'
    2. Remoção de registros suspensos (em ambas as bases)
    3. Base Sinapse: Cruzar por Contrato e extrair:
       - CódAuxEquipe
       - Técnico Dono (Nome Equipe)
       - Monitor (Supervisor)
    4. Exibição via render_table_html na ordem oficial com coloração condicional garantida.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import unicodedata
from datetime import date
from io import BytesIO
from typing import Any, cast

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import streamlit as st

from components.componentes import (
    ColorMapDict,
    aplicar_estilo,
    render_hero,
    render_insight,
    render_kpi,
    render_table_html,
)
from components.dashboards import abrir_dashboard, fechar_dashboard
from components.layout_pagina import cabecalho_secao
from components.sidebar import render_page_sidebar_theme_selector
from services.planilhas import gerar_excel_multiabas

logger = logging.getLogger(__name__)

#: Seções ancoradas do sumário (títulos usados em ``cabecalho_secao``).
SECOES_PAGINA: tuple[str, ...] = (
    "Fontes de Dados",
    "Filtros do Relatório",
    "Indicadores da Auditoria",
    "Legenda de Supervisores",
    "Base Detalhada de Retornos",
    "Exportação",
)

# ==========================================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================================
st.set_page_config(
    page_title="Dono do Retorno | Auditoria TOA ↔ Sinapse",
    page_icon="🔍",
    layout="wide",
)

aplicar_estilo()
render_page_sidebar_theme_selector()

# O CSS de shell (container, sidebar, hero e tabelas) vem do entrypoint +
# components.css_global — a página não repete essas regras.

# ==========================================================
# ORDEM OFICIAL DAS COLUNAS
# ==========================================================
COLUNAS_ORDEM_OFICIAL: list[str] = [
    "Contrato",
    "Login do Técnico",
    "Recurso",
    "DONO_CÓD_AUX_EQUIPE",
    "DONO_TÉCNICO_NOME",
    "DONO_MONITOR_SUPERVISOR",
    "STATUS_AUDITORIA",
    "Status da Atividade",
    "Intervalo de Tempo",
    "Endereço",
    "Cidade",
    "Número da O.S 1",
    "SINAPSE_DATA_ORIGINAL",
]

# Colunas criadas pelo cruzamento (usadas para evitar colisão no merge)
COLUNAS_DESTINO_SINAPSE: list[str] = [
    "DONO_CÓD_AUX_EQUIPE",
    "DONO_TÉCNICO_NOME",
    "DONO_MONITOR_SUPERVISOR",
    "SINAPSE_DATA_ORIGINAL",
]

PLACEHOLDER = "-"
VALORES_VAZIOS: set[str] = {
    "",
    "-",
    "--",
    "nan",
    "none",
    "null",
    "na",
    "n/a",
    "#n/a",
    "sem_equipe",
    "sem equipe",
    "não informado",
    "nao informado",
    "sem monitor",
}

# ==========================================================
# CONSTANTES DE MAPEAMENTO — TOA
# ==========================================================
TOA_TIPO_ATIVIDADE: list[str] = [
    "Tipo de Atividade.1",
    "Tipo de Atividade",
    "Tipo Atividade",
    "Tipo de OS",
    "Tipo OS",
    "Tipo de Ordem",
    "Tipo",
    "Serviço",
]
TOA_CONTRATO: list[str] = [
    "Contrato",
    "Nº Contrato",
    "Numero do Contrato",
    "Número do Contrato",
    "Cod Contrato",
    "Código do Contrato",
    "Num Contrato",
    "Nro Contrato",
    "CONTRATO",
]
TOA_LOGIN_TECNICO: list[str] = [
    "Login do Técnico",
    "Login do Tecnico",
    "Login Técnico",
    "Login Tecnico",
    "Login",
    "Usuário",
    "Usuario",
    "Login do Recurso",
]
TOA_RECURSO: list[str] = [
    "Recurso",
    "Nome do Recurso",
    "Nome Recurso",
    "Resource",
    "Responsável",
    "Responsavel",
    "Técnico",
    "Tecnico",
]
TOA_STATUS_ATIVIDADE: list[str] = [
    "Status da Atividade",
    "Status",
    "Situação",
    "Situacao",
    "Status OS",
    "Status da OS",
    "Resultado",
    "Resultado da Atividade",
]
TOA_INTERVALO_TEMPO: list[str] = [
    "Intervalo de Tempo",
    "Intervalo",
    "Janela",
    "Janela de Atendimento",
    "Time Slot",
    "Slot",
    "SLA",
    "Horário",
    "Horario",
]
TOA_ENDERECO: list[str] = [
    "Endereço",
    "Endereco",
    "Logradouro",
    "Endereço do Cliente",
    "Endereco do Cliente",
    "Rua",
    "Endereço Completo",
]
TOA_CIDADE: list[str] = ["Cidade", "Município", "Municipio", "CIDADE", "Localidade"]
TOA_NUMERO_OS: list[str] = [
    "Número da O.S 1",
    "Numero da O.S 1",
    "Número da OS 1",
    "Numero da OS 1",
    "Número da O.S. 1",
    "Número da O.S",
    "Numero da OS",
    "Nº OS",
    "Numero OS",
    "OS",
]

# ==========================================================
# CONSTANTES DE MAPEAMENTO — SINAPSE
# ==========================================================
SINAPSE_CONTRATO: list[str] = [
    "Contrato",
    "Nº Contrato",
    "Numero do Contrato",
    "Número do Contrato",
    "Cod Contrato",
    "Código do Contrato",
    "Num Contrato",
    "Nro Contrato",
    "Contrato Cliente",
    "CONTRATO",
]
SINAPSE_COD_AUX_EQUIPE: list[str] = [
    "CódAuxEquipe",
    "CodAuxEquipe",
    "Cod Aux Equipe",
    "Cód Aux Equipe",
    "Cod_Aux_Equipe",
    "COD_AUX_EQUIPE",
    "Código Auxiliar Equipe",
    "CodAux",
    "Cod Aux",
    "CódAux",
    "CodEquipe",
    "Cód Equipe",
    "Equipe",
]
SINAPSE_NOME_EQUIPE: list[str] = [
    "Nome Equipe",
    "Nome da Equipe",
    "Nome da Equipe/Técnico",
    "NOME_EQUIPE",
    "Nome Técnico",
    "Nome Tecnico",
    "Nome do Técnico",
    "Técnico Dono",
    "Tecnico Dono",
    "Técnico",
    "Tecnico",
    "Executor",
]
SINAPSE_SUPERVISOR_MONITOR: list[str] = [
    "Monitor",
    "Supervisor",
    "Monitor/Supervisor",
    "Supervisor/Monitor",
    "Nome Monitor",
    "Nome Supervisor",
    "Coordenador",
    "Gestor",
    "SUPERVISOR",
    "MONITOR",
    "Líder",
    "Lider",
]
SINAPSE_DATA: list[str] = [
    "Data",
    "DATA",
    "DATA AGENDA",
    "Data Agenda",
    "Data Agendamento",
    "Data Início",
    "Data Inicio",
    "Data Atividade",
    "Data Atendimento",
    "Data de Execução",
    "Data Execucao",
    "DT_AGENDA",
    "DATA_EXECUCAO",
]
SINAPSE_STATUS: list[str] = [
    "Status da Atividade",
    "SITUAÇÃO APP",
    "Situação App",
    "Situacao App",
    "Status",
    "Situação",
    "Situacao",
    "RESULTADO DA ATIVIDADE",
]

VALOR_FILTRO_ATIVIDADE: str = "Retorno Credenciada"


# ==========================================================
# UTILITÁRIOS
# ==========================================================
def _normalizar_texto(texto: Any) -> str:
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    t = str(texto).lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _normalizar_contrato(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    txt = str(valor).strip().upper()
    txt = re.sub(r"\.0$", "", txt)
    txt = re.sub(r"[^\w]", "", txt)
    return txt.lstrip("0") or txt


def _eh_vazio(valor: Any) -> bool:
    """Detecta placeholders/nulos de forma consistente."""
    if valor is None or pd.isna(valor):
        return True
    return str(valor).strip().lower() in VALORES_VAZIOS


def _serie(df: pd.DataFrame, coluna: str | None, default: Any = PLACEHOLDER) -> pd.Series:
    """Retorna sempre uma Series — inclusive com coluna ausente ou duplicada."""
    if not coluna or coluna not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="object")

    posicao = next(i for i, nome in enumerate(df.columns) if nome == coluna)
    return df.iloc[:, posicao]


def _normalizar_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    novos: list[str] = []
    contador: dict[str, int] = {}
    for col in df.columns:
        nome = str(col).strip().replace("\ufeff", "").replace("\u200b", "").replace("\xa0", " ")
        nome = re.sub(r"\s+", " ", nome).strip() or "coluna_sem_nome"
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
        "",
        "nan",
        "none",
        "null",
        "na",
        "n/a",
        "#n/a",
        "#na",
        "-",
        "--",
        "?",
    }
    for col in df.select_dtypes(include=["object", "string"]).columns:
        mask_original_na = df[col].isna()
        serie = (
            df[col]
            .astype("string")
            .str.replace("\xa0", " ", regex=False)
            .str.replace("\u200b", "", regex=False)
            .str.replace("\ufeff", "", regex=False)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        mask_nulos = serie.str.lower().isin(nulos_padrao) | mask_original_na
        df[col] = serie.mask(mask_nulos, pd.NA)
    return df


@st.cache_data(show_spinner="Processando arquivo...")
def carregar_arquivo(
    arquivo_bytes: bytes, nome_arquivo: str
) -> tuple[pd.DataFrame, dict[str, str]]:
    if not arquivo_bytes:
        raise ValueError("Arquivo vazio ou não lido corretamente.")

    nome = nome_arquivo.lower()
    stats: dict[str, str] = {"metodo": "", "separador": "", "encoding": ""}

    if nome.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(BytesIO(arquivo_bytes), dtype=str)
            df = _limpar_valores_string(_normalizar_nomes_colunas(df))
            df = df.dropna(how="all").reset_index(drop=True)
            stats["metodo"] = "Excel"
            return df, stats
        except Exception as e:
            raise ValueError(f"Erro ao processar Excel: {e}") from e

    tentativas = [
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "latin-1"},
        {"sep": ";", "encoding": "cp1252"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "latin-1"},
        {"sep": "\t", "encoding": "utf-8-sig"},
        {"sep": "|", "encoding": "utf-8-sig"},
    ]

    melhor_df: pd.DataFrame | None = None
    melhor_score = 0
    melhor_cfg: dict[str, str] = {}

    for cfg in tentativas:
        try:
            df = pd.read_csv(
                BytesIO(arquivo_bytes),
                dtype=str,
                low_memory=False,
                on_bad_lines="skip",
                sep=cfg["sep"],
                encoding=cfg["encoding"],
            )
            score = len(df.columns) if len(df.columns) > 1 else 0
            if score > melhor_score:
                melhor_score, melhor_df, melhor_cfg = score, df, cfg
        except Exception:
            logger.debug(
                "Tentativa de leitura do CSV falhou; tentando próximo formato.", exc_info=True
            )
            continue

    if melhor_df is None or melhor_score == 0:
        raise ValueError("Não foi possível identificar o formato do arquivo CSV.")

    df_final = _limpar_valores_string(_normalizar_nomes_colunas(melhor_df))
    df_final = df_final.dropna(how="all").reset_index(drop=True)

    stats.update(
        metodo="CSV",
        separador=repr(melhor_cfg["sep"]),
        encoding=melhor_cfg["encoding"],
    )
    return df_final, stats


def identificar_coluna(
    df: pd.DataFrame,
    nomes_possiveis: list[str],
    excluir: set[str] | None = None,
) -> str | None:
    """
    FIX #6 — Casamento em 3 níveis (exato → prefixo → contido) e respeito a
    colunas já atribuídas a outro campo (evita 'Equipe' roubar 'Nome Equipe').
    """
    if len(df.columns) == 0:
        return None

    excluir = excluir or set()
    cols_norm: dict[str, str] = {}
    for c in df.columns:
        if str(c) in excluir:
            continue
        cols_norm.setdefault(_normalizar_texto(c), str(c))

    # Nível 1 — igualdade exata (respeita a ordem de prioridade da lista)
    for nome in nomes_possiveis:
        chave = _normalizar_texto(nome)
        if chave and chave in cols_norm:
            return cols_norm[chave]

    # Nível 2 — coluna começa com o alvo
    for nome in nomes_possiveis:
        chave = _normalizar_texto(nome)
        if not chave:
            continue
        for col_norm, col_orig in cols_norm.items():
            if col_norm.startswith(chave):
                return col_orig

    # Nível 3 — contido em qualquer posição
    for nome in nomes_possiveis:
        chave = _normalizar_texto(nome)
        if len(chave) < 4:  # evita matches espúrios com termos curtos
            continue
        for col_norm, col_orig in cols_norm.items():
            if chave in col_norm:
                return col_orig
    return None


def converter_data_robusto(serie: pd.Series) -> pd.Series:
    s = serie.astype(str).str.strip()
    resultado = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if resultado.isna().sum() > len(s) * 0.3:
        formatos = [
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d-%m-%Y",
        ]
        for fmt in formatos:
            tentativa = pd.to_datetime(s, errors="coerce", format=fmt)
            if tentativa.notna().sum() > resultado.notna().sum():
                resultado = tentativa
    return resultado


# ==========================================================
# 1️⃣ REFINAR TOA
# ==========================================================
def refinar_base_toa(
    df_toa: pd.DataFrame,
    col_tipo: str | None,
    col_contrato: str | None,
    col_status: str | None,
    valor_filtro: str = VALOR_FILTRO_ATIVIDADE,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    stats: dict[str, Any] = {
        "linhas_originais": len(df_toa),
        "retornos_encontrados": 0,
        "suspensos_removidos": 0,
        "sem_contrato": 0,
        "linhas_finais": 0,
        "filtro_tipo_aplicado": False,
        "filtro_suspenso_aplicado": False,
    }

    df_filt = df_toa.copy()

    # 1. Filtro Tipo de Atividade
    if col_tipo and col_tipo in df_filt.columns:
        serie_norm = _serie(df_filt, col_tipo).map(_normalizar_texto)
        alvo_norm = _normalizar_texto(valor_filtro)
        mask_tipo = (serie_norm == alvo_norm) | (
            serie_norm.str.contains("retorno", na=False)
            & serie_norm.str.contains("credenciad", na=False)
        )
        df_filt = df_filt[mask_tipo].copy()
        stats["filtro_tipo_aplicado"] = True

    stats["retornos_encontrados"] = len(df_filt)

    # 2. Remoção de Suspensos
    if col_status and col_status in df_filt.columns:
        mask_suspenso = (
            _serie(df_filt, col_status).astype(str).str.contains("suspen", case=False, na=False)
        )
        stats["suspensos_removidos"] = int(mask_suspenso.sum())
        stats["filtro_suspenso_aplicado"] = True
        df_filt = df_filt[~mask_suspenso].copy()

    # 3. Validação de Contrato
    if col_contrato and col_contrato in df_filt.columns:
        chaves = _serie(df_filt, col_contrato).map(_normalizar_contrato)
        mask_valido = chaves != ""
        stats["sem_contrato"] = int((~mask_valido).sum())
        df_filt = df_filt[mask_valido].copy()

    stats["linhas_finais"] = len(df_filt)
    return df_filt.reset_index(drop=True), stats


# ==========================================================
# 2️⃣ CRUZAR COM SINAPSE
# ==========================================================
def cruzar_com_sinapse(
    df_toa_retornos: pd.DataFrame,
    df_sinapse: pd.DataFrame,
    col_contrato_toa: str,
    col_contrato_sin: str,
    col_cod_aux_sin: str | None,
    col_nome_equipe_sin: str | None,
    col_supervisor_sin: str | None,
    col_data_sin: str | None,
    col_status_sin: str | None,
    col_login_toa: str | None,
    col_recurso_toa: str | None,
    col_status_toa: str | None,
    col_intervalo_toa: str | None,
    col_endereco_toa: str | None,
    col_cidade_toa: str | None,
    col_numero_os_toa: str | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    stats: dict[str, Any] = {
        "total_retornos": len(df_toa_retornos),
        "com_cod_equipe": 0,
        "sem_dono": 0,
        "taxa_identificacao": 0.0,
        "suspensos_sinapse": 0,
        "contratos_sinapse": 0,
    }

    df_t = df_toa_retornos.copy()
    df_s = df_sinapse.copy()

    # FIX #3 — remove do TOA nomes que colidiriam com as colunas do cruzamento
    df_t = df_t.drop(
        columns=[c for c in COLUNAS_DESTINO_SINAPSE if c in df_t.columns],
        errors="ignore",
    )

    # Limpeza de suspensos no Sinapse
    if col_status_sin and col_status_sin in df_s.columns:
        mask_susp = (
            _serie(df_s, col_status_sin).astype(str).str.contains("suspen", case=False, na=False)
        )
        stats["suspensos_sinapse"] = int(mask_susp.sum())
        df_s = df_s[~mask_susp].copy()

    df_t["_chave_contrato_"] = _serie(df_t, col_contrato_toa).map(_normalizar_contrato)
    df_s["_chave_contrato_"] = _serie(df_s, col_contrato_sin).map(_normalizar_contrato)
    df_s = df_s[df_s["_chave_contrato_"] != ""].copy()

    # FIX #11 — prioriza linha COM CódAuxEquipe preenchido e, depois, a mais recente
    df_s["_tem_dono_"] = (
        ~_serie(df_s, col_cod_aux_sin, default=None).map(_eh_vazio)
        if col_cod_aux_sin and col_cod_aux_sin in df_s.columns
        else False
    )
    if col_data_sin and col_data_sin in df_s.columns:
        df_s["_dt_temp_"] = converter_data_robusto(_serie(df_s, col_data_sin))
    else:
        df_s["_dt_temp_"] = pd.NaT

    df_s = df_s.sort_values(
        by=["_tem_dono_", "_dt_temp_"],
        ascending=[False, False],
        na_position="last",
    )

    # FIX #2 — monta o resumo campo a campo (imune a fonte duplicada/ausente)
    df_s_resumo = pd.DataFrame({"_chave_contrato_": df_s["_chave_contrato_"]})
    mapeamento_sinapse: list[tuple[str | None, str]] = [
        (col_cod_aux_sin, "DONO_CÓD_AUX_EQUIPE"),
        (col_nome_equipe_sin, "DONO_TÉCNICO_NOME"),
        (col_supervisor_sin, "DONO_MONITOR_SUPERVISOR"),
        (col_data_sin, "SINAPSE_DATA_ORIGINAL"),
    ]
    for origem, destino in mapeamento_sinapse:
        if origem and origem in df_s.columns:
            df_s_resumo[destino] = _serie(df_s, origem, default=None).values

    df_s_resumo = df_s_resumo.drop_duplicates(subset=["_chave_contrato_"], keep="first")
    stats["contratos_sinapse"] = len(df_s_resumo)

    df_resultado = df_t.merge(df_s_resumo, on="_chave_contrato_", how="left")
    df_resultado = df_resultado.drop(columns=["_chave_contrato_"])

    # ---- Normalização das colunas do Dono ----
    cod_aux = _serie(df_resultado, "DONO_CÓD_AUX_EQUIPE", default=None)
    # FIX #7 — identificação considera nulos, vazios e placeholders
    mask_identificado = ~cod_aux.map(_eh_vazio)

    df_resultado["DONO_CÓD_AUX_EQUIPE"] = cod_aux.where(mask_identificado, "SEM_EQUIPE")

    nome_tec = _serie(df_resultado, "DONO_TÉCNICO_NOME", default=None)
    df_resultado["DONO_TÉCNICO_NOME"] = nome_tec.where(~nome_tec.map(_eh_vazio), "NÃO INFORMADO")

    monitor = _serie(df_resultado, "DONO_MONITOR_SUPERVISOR", default=None)
    df_resultado["DONO_MONITOR_SUPERVISOR"] = monitor.where(~monitor.map(_eh_vazio), "SEM MONITOR")

    data_sin = _serie(df_resultado, "SINAPSE_DATA_ORIGINAL", default=None)
    data_fmt = converter_data_robusto(data_sin).dt.strftime("%d/%m/%Y")
    df_resultado["SINAPSE_DATA_ORIGINAL"] = data_fmt.fillna(
        data_sin.where(~data_sin.map(_eh_vazio), PLACEHOLDER)
    ).fillna(PLACEHOLDER)

    df_resultado["STATUS_AUDITORIA"] = mask_identificado.map(
        {True: "Identificado", False: "Sem Dono no Sinapse"}
    )

    # ---- Padronização na ordem oficial ----
    df_padronizado = pd.DataFrame(index=df_resultado.index)
    df_padronizado["Contrato"] = _serie(df_resultado, col_contrato_toa)
    df_padronizado["Login do Técnico"] = _serie(df_resultado, col_login_toa)
    df_padronizado["Recurso"] = _serie(df_resultado, col_recurso_toa)
    df_padronizado["DONO_CÓD_AUX_EQUIPE"] = df_resultado["DONO_CÓD_AUX_EQUIPE"]
    df_padronizado["DONO_TÉCNICO_NOME"] = df_resultado["DONO_TÉCNICO_NOME"]
    df_padronizado["DONO_MONITOR_SUPERVISOR"] = df_resultado["DONO_MONITOR_SUPERVISOR"]
    df_padronizado["STATUS_AUDITORIA"] = df_resultado["STATUS_AUDITORIA"]
    df_padronizado["Status da Atividade"] = _serie(df_resultado, col_status_toa)
    df_padronizado["Intervalo de Tempo"] = _serie(df_resultado, col_intervalo_toa)
    df_padronizado["Endereço"] = _serie(df_resultado, col_endereco_toa)
    df_padronizado["Cidade"] = _serie(df_resultado, col_cidade_toa)
    df_padronizado["Número da O.S 1"] = _serie(df_resultado, col_numero_os_toa)
    df_padronizado["SINAPSE_DATA_ORIGINAL"] = df_resultado["SINAPSE_DATA_ORIGINAL"]

    df_padronizado = df_padronizado.astype("object").fillna(PLACEHOLDER)

    total = len(df_padronizado)
    com_equipe = int(mask_identificado.sum())
    stats["com_cod_equipe"] = com_equipe
    stats["sem_dono"] = total - com_equipe
    stats["taxa_identificacao"] = round(com_equipe / total * 100, 1) if total else 0.0

    return df_padronizado[COLUNAS_ORDEM_OFICIAL].reset_index(drop=True), stats


# ==========================================================
# EXPORTAÇÃO EXCEL MULTI-ABAS
# ==========================================================
@st.cache_data(show_spinner="Gerando planilha...")
def _gerar_excel_por_equipe(
    df_consolidado: pd.DataFrame,
    coluna_agrupamento: str = "DONO_CÓD_AUX_EQUIPE",
    max_abas: int = 150,
) -> bytes:
    """Relatório multi-abas — delega a :func:`services.planilhas.gerar_excel_multiabas`.

    Mantém o cache (o arquivo não é regerado a cada rerun de filtro) e o contrato
    histórico: aba ``Consolidado_Geral`` + uma aba por CódAuxEquipe.
    """
    return gerar_excel_multiabas(
        df_consolidado,
        coluna_grupo=coluna_agrupamento,
        max_abas=max_abas,
    )


# ==========================================================
# 🎨 CABEÇALHO + CONTEXTO (padrão do portal)
# ==========================================================
abrir_dashboard(
    "Donos do Retorno — Equipe & Monitor",
    secoes=SECOES_PAGINA,
    hero=render_hero,
    hero_kwargs={
        "titulo": "Donos do Retorno — Equipe & Monitor",
        "subtitulo": (
            "Auditoria precisa dos retornos do TOA cruzados com o Sinapse, "
            "excluindo suspensos e destacando a cadeia de supervisão."
        ),
        "badge": "Auditoria TOA ↔ Sinapse",
    },
    chips={"Fontes": "TOA + Sinapse"},
)

# ==========================================================
# 📁 UPLOAD DOS ARQUIVOS
# ==========================================================
cabecalho_secao(
    "Fontes de Dados",
    icone="upload_file",
    subtitulo="Importe os arquivos do TOA e do Sinapse.",
)

c_up1, c_up2 = st.columns(2)

with c_up1:
    st.markdown("### 1️⃣ Base TOA (Retornos)")
    st.caption("Origem dos retornos a serem auditados (Tipo = Retorno Credenciada).")
    arquivo_toa = st.file_uploader(
        "Importar arquivo TOA", type=["csv", "xlsx", "xls"], key="up_toa"
    )
    if arquivo_toa:
        st.success(f"Carregado: {arquivo_toa.name}", icon="✅")

with c_up2:
    st.markdown("### 2️⃣ Base Sinapse (Histórico)")
    st.caption("Origem dos contratos para identificar CódAuxEquipe, Nome Equipe e Monitor.")
    arquivo_sinapse = st.file_uploader(
        "Importar arquivo Sinapse", type=["csv", "xlsx", "xls"], key="up_sinapse"
    )
    if arquivo_sinapse:
        st.success(f"Carregado: {arquivo_sinapse.name}", icon="✅")

if not arquivo_toa or not arquivo_sinapse:
    st.markdown("<br>", unsafe_allow_html=True)
    render_insight(
        "Para iniciar a auditoria, envie **ambos os arquivos**: a base de retornos "
        "(**TOA**) e o histórico (**Sinapse**).",
        tipo="info",
    )
    st.stop()

# ==========================================================
# 📥 PROCESSAMENTO
# ==========================================================
df_toa_raw: pd.DataFrame = pd.DataFrame()
df_sin_raw: pd.DataFrame = pd.DataFrame()
try:
    # FIX #1 — getvalue() é idempotente entre reruns; read() esvazia o buffer
    df_toa_raw, _ = carregar_arquivo(arquivo_toa.getvalue(), arquivo_toa.name)
    df_sin_raw, _ = carregar_arquivo(arquivo_sinapse.getvalue(), arquivo_sinapse.name)
except Exception as e:
    render_insight(f"Erro ao ler os arquivos enviados: `{e}`", tipo="critico")
    st.stop()

if df_toa_raw.empty or df_sin_raw.empty:
    render_insight("Um dos arquivos enviados está vazio.", tipo="critico")
    st.stop()

# ---- Identificação das colunas — TOA ----
col_tipo_toa = identificar_coluna(df_toa_raw, TOA_TIPO_ATIVIDADE)
col_contrato_toa = identificar_coluna(df_toa_raw, TOA_CONTRATO)
col_login_toa = identificar_coluna(df_toa_raw, TOA_LOGIN_TECNICO)
col_recurso_toa = identificar_coluna(df_toa_raw, TOA_RECURSO)
col_status_toa = identificar_coluna(df_toa_raw, TOA_STATUS_ATIVIDADE)
col_intervalo_toa = identificar_coluna(df_toa_raw, TOA_INTERVALO_TEMPO)
col_endereco_toa = identificar_coluna(df_toa_raw, TOA_ENDERECO)
col_cidade_toa = identificar_coluna(df_toa_raw, TOA_CIDADE)
col_numero_os_toa = identificar_coluna(df_toa_raw, TOA_NUMERO_OS)

# ---- Identificação das colunas — Sinapse (com exclusão progressiva) ----
usadas_sin: set[str] = set()


def _detectar_sin(nomes: list[str]) -> str | None:
    col = identificar_coluna(df_sin_raw, nomes, excluir=usadas_sin)
    if col:
        usadas_sin.add(col)
    return col


col_contrato_sin = _detectar_sin(SINAPSE_CONTRATO)
col_cod_aux_sin = _detectar_sin(SINAPSE_COD_AUX_EQUIPE)
col_nome_equipe_sin = _detectar_sin(SINAPSE_NOME_EQUIPE)
col_supervisor_sin = _detectar_sin(SINAPSE_SUPERVISOR_MONITOR)
col_data_sin = _detectar_sin(SINAPSE_DATA)
col_status_sin = _detectar_sin(SINAPSE_STATUS)

if not col_contrato_toa:
    render_insight("❌ Coluna de **Contrato** não localizada no arquivo TOA.", tipo="critico")
    st.stop()

if not col_contrato_sin:
    render_insight("❌ Coluna de **Contrato** não localizada no arquivo Sinapse.", tipo="critico")
    st.stop()

# FIX #10 — transparência sobre o mapeamento
faltantes: list[str] = []
if not col_tipo_toa:
    faltantes.append("TOA · Tipo de Atividade (filtro de retorno **não** aplicado)")
if not col_status_toa:
    faltantes.append("TOA · Status da Atividade (suspensos **não** removidos)")
if not col_cod_aux_sin:
    faltantes.append("Sinapse · CódAuxEquipe")
if not col_nome_equipe_sin:
    faltantes.append("Sinapse · Nome Equipe")
if not col_supervisor_sin:
    faltantes.append("Sinapse · Monitor/Supervisor")

if faltantes:
    render_insight(
        "⚠️ Colunas não localizadas automaticamente:<br>• " + "<br>• ".join(faltantes),
        tipo="alerta",
    )

with st.expander("🔧 Mapeamento de colunas detectado"):
    st.dataframe(
        pd.DataFrame(
            {
                "Campo": [
                    "TOA · Tipo de Atividade",
                    "TOA · Contrato",
                    "TOA · Login",
                    "TOA · Recurso",
                    "TOA · Status",
                    "TOA · Intervalo",
                    "TOA · Endereço",
                    "TOA · Cidade",
                    "TOA · Nº OS",
                    "SIN · Contrato",
                    "SIN · CódAuxEquipe",
                    "SIN · Nome Equipe",
                    "SIN · Monitor",
                    "SIN · Data",
                    "SIN · Status",
                ],
                "Coluna no arquivo": [
                    col_tipo_toa,
                    col_contrato_toa,
                    col_login_toa,
                    col_recurso_toa,
                    col_status_toa,
                    col_intervalo_toa,
                    col_endereco_toa,
                    col_cidade_toa,
                    col_numero_os_toa,
                    col_contrato_sin,
                    col_cod_aux_sin,
                    col_nome_equipe_sin,
                    col_supervisor_sin,
                    col_data_sin,
                    col_status_sin,
                ],
            }
        ).fillna("— não encontrada —"),
        width="stretch",
        hide_index=True,
    )

# ── 1. Refina TOA ──
df_toa_refinado, stats_toa_filt = refinar_base_toa(
    df_toa=df_toa_raw,
    col_tipo=col_tipo_toa,
    col_contrato=col_contrato_toa,
    col_status=col_status_toa,
    valor_filtro=VALOR_FILTRO_ATIVIDADE,
)

if df_toa_refinado.empty:
    render_insight(
        f"Nenhum registro ativo (não suspenso) do tipo **'{VALOR_FILTRO_ATIVIDADE}'** "
        "foi localizado no TOA.",
        tipo="critico",
    )
    st.stop()

# ── 2. Cruzamento TOA ↔ Sinapse ──
df_auditado, stats_cruzamento = cruzar_com_sinapse(
    df_toa_retornos=df_toa_refinado,
    df_sinapse=df_sin_raw,
    col_contrato_toa=col_contrato_toa,
    col_contrato_sin=col_contrato_sin,
    col_cod_aux_sin=col_cod_aux_sin,
    col_nome_equipe_sin=col_nome_equipe_sin,
    col_supervisor_sin=col_supervisor_sin,
    col_data_sin=col_data_sin,
    col_status_sin=col_status_sin,
    col_login_toa=col_login_toa,
    col_recurso_toa=col_recurso_toa,
    col_status_toa=col_status_toa,
    col_intervalo_toa=col_intervalo_toa,
    col_endereco_toa=col_endereco_toa,
    col_cidade_toa=col_cidade_toa,
    col_numero_os_toa=col_numero_os_toa,
)

# ==========================================================
# 🔎 FILTROS DINÂMICOS
# ==========================================================
cabecalho_secao(
    "Filtros do Relatório",
    icone="filter_alt",
    subtitulo="Refine a visualização por equipe ou supervisor.",
)

f_col1, f_col2, f_col3, f_col4 = st.columns([1, 1, 1, 1])

with f_col1:
    monitor_sel = st.multiselect(
        "👔 Monitor (Supervisor)",
        sorted(df_auditado["DONO_MONITOR_SUPERVISOR"].astype(str).unique()),
        default=[],
    )
with f_col2:
    equipe_sel = st.multiselect(
        "🏷️ CódAuxEquipe",
        sorted(df_auditado["DONO_CÓD_AUX_EQUIPE"].astype(str).unique()),
        default=[],
    )
with f_col3:
    status_aud_sel = st.multiselect(
        "📌 Status da Auditoria",
        sorted(df_auditado["STATUS_AUDITORIA"].astype(str).unique()),
        default=[],
    )
with f_col4:
    busca_contrato = st.text_input("🔎 Buscar contrato / OS", value="").strip()

df_view = df_auditado.copy()
if monitor_sel:
    df_view = df_view[df_view["DONO_MONITOR_SUPERVISOR"].astype(str).isin(monitor_sel)]
if equipe_sel:
    df_view = df_view[df_view["DONO_CÓD_AUX_EQUIPE"].astype(str).isin(equipe_sel)]
if status_aud_sel:
    df_view = df_view[df_view["STATUS_AUDITORIA"].astype(str).isin(status_aud_sel)]
if busca_contrato:
    alvo = _normalizar_contrato(busca_contrato)
    mask_busca = df_view["Contrato"].map(_normalizar_contrato).str.contains(
        alvo, na=False
    ) | df_view["Número da O.S 1"].astype(str).str.contains(busca_contrato, case=False, na=False)
    df_view = df_view[mask_busca]

df_view = df_view.reset_index(drop=True)

# ==========================================================
# 📊 PAINEL EXECUTIVO
# ==========================================================
cabecalho_secao(
    "Indicadores da Auditoria",
    icone="monitoring",
    subtitulo="Resumo executivo do cruzamento.",
)

k1, k2, k3, k4 = st.columns(4)
render_kpi(
    k1,
    "Retornos Auditados",
    f"{stats_cruzamento['total_retornos']:,}".replace(",", "."),
    f"{stats_toa_filt['suspensos_removidos']} suspensos removidos",
    tema="azul",
)
render_kpi(
    k2,
    "Donos Localizados",
    f"{stats_cruzamento['com_cod_equipe']:,}".replace(",", "."),
    f"{stats_cruzamento['taxa_identificacao']}% com CódAuxEquipe",
    tema="verde",
)
render_kpi(
    k3,
    "Sem Dono no Sinapse",
    f"{stats_cruzamento['sem_dono']:,}".replace(",", "."),
    "contrato ausente no histórico",
    tema="vermelho",
)
total_monitores = int(
    df_auditado.loc[
        df_auditado["DONO_MONITOR_SUPERVISOR"] != "SEM MONITOR",
        "DONO_MONITOR_SUPERVISOR",
    ].nunique()
)
render_kpi(
    k4,
    "Monitores Envolvidos",
    f"{total_monitores:,}",
    "supervisores distintos",
    tema="cinza",
)

# ==========================================================
# 📈 LEGENDA DE CORES DOS MONITORES
# ==========================================================
cabecalho_secao(
    "Legenda de Supervisores",
    icone="palette",
    subtitulo="Identificação visual por monitor.",
)

LEGENDA = [
    ("🔵 EDSON MARCO PINHEIRO", "#DBEAFE", "#1E40AF", "#BFDBFE"),
    ("🟢 MARCOS ROBERTO DO NASCIMENTO", "#ECFDF5", "#047857", "#A7F3D0"),
    ("🟣 MAICON APARECIDO FARIA", "#F5F3FF", "#6D28D9", "#DDD6FE"),
    ("⚪ NELSON ALVES OLIVEIRA JUNIOR", "#F8FAFC", "#475569", "#CBD5E1"),
]
for coluna, (rotulo, bg, fg, borda) in zip(st.columns(4), LEGENDA, strict=False):
    with coluna:
        st.markdown(
            f'<div style="padding:10px;border-radius:6px;background:{bg};color:{fg};'
            f'font-weight:700;font-size:12px;border:1px solid {borda};">{rotulo}</div>',
            unsafe_allow_html=True,
        )

# ==========================================================
# 🔍 BASE DETALHADA
# ==========================================================
cabecalho_secao(
    "Base Detalhada de Retornos",
    icone="table",
    subtitulo=f"{len(df_view):,} registros na ordem oficial.",
)


def _pred(val: Any, trecho: str) -> bool:
    return trecho in _normalizar_texto(val)


color_rules = cast(
    ColorMapDict,
    {
        "DONO_MONITOR_SUPERVISOR": [
            (
                lambda val: _pred(val, "edson marco pinheiro"),
                "#1E40AF; background-color: #DBEAFE; border-left: 3px solid #1E40AF",
            ),
            (
                lambda val: _pred(val, "marcos roberto do nascimento"),
                "#047857; background-color: #ECFDF5; border-left: 3px solid #047857",
            ),
            (
                lambda val: _pred(val, "maicon aparecido faria"),
                "#6D28D9; background-color: #F5F3FF; border-left: 3px solid #6D28D9",
            ),
            (
                lambda val: _pred(val, "nelson alves"),
                "#475569; background-color: #F8FAFC; border-left: 3px solid #475569",
            ),
            (
                lambda val: _eh_vazio(val),
                "#92400E; background-color: #FFFBEB",
            ),
        ],
        "DONO_CÓD_AUX_EQUIPE": [
            (
                lambda val: _eh_vazio(val),
                "#B91C1C; background-color: #FEF2F2",
            ),
            (
                lambda val: not _eh_vazio(val),
                "#1E40AF; background-color: #DBEAFE; font-family: var(--font-codigo)",
            ),
        ],
        "DONO_TÉCNICO_NOME": [
            (
                lambda val: _eh_vazio(val),
                "#9CA3AF; background-color: transparent",
            ),
            (
                lambda val: not _eh_vazio(val),
                "#047857; background-color: #ECFDF5",
            ),
        ],
        "STATUS_AUDITORIA": [
            (
                lambda val: str(val) == "Identificado",
                "#047857; background-color: #ECFDF5",
            ),
            (
                lambda val: str(val) != "Identificado",
                "#B91C1C; background-color: #FEF2F2",
            ),
        ],
    },
)

# FIX #9 — guarda para resultado vazio
if df_view.empty:
    render_insight(
        "Nenhum registro atende aos filtros selecionados. Ajuste os critérios acima.",
        tipo="alerta",
    )
else:
    render_table_html(df=df_view, color_rules=color_rules, height=480, max_rows=100)
    if len(df_view) > 100:
        st.caption(
            f"Exibindo as 100 primeiras de {len(df_view):,} linhas — "
            "faça o download para ver a base completa."
        )

# ==========================================================
# 📤 EXPORTAÇÃO
# ==========================================================
cabecalho_secao("Exportação", icone="download", subtitulo="Download dos relatórios oficiais.")

if df_view.empty:
    st.info("Sem dados para exportar com os filtros atuais.", icon="ℹ️")
else:
    sufixo = date.today().strftime("%Y%m%d")
    exp_c1, exp_c2 = st.columns(2)

    with exp_c1:
        # FIX #8 — geração cacheada (não reprocessa a cada rerun de filtro)
        try:
            excel_bytes = _gerar_excel_por_equipe(df_view, "DONO_CÓD_AUX_EQUIPE")
            st.download_button(
                "📊 Baixar Relatório Excel (Abas por CódAuxEquipe)",
                data=excel_bytes,
                file_name=f"retornos_auditoria_{sufixo}.xlsx",
                mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                width="stretch",
                type="primary",
            )
        except Exception as e:
            logger.exception("Falha ao gerar Excel")
            st.error(f"Não foi possível gerar o Excel: {e}", icon="🚫")

    with exp_c2:
        # FIX #12 — encoding aplicado uma única vez
        csv_bytes = df_view.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "📄 Baixar Base Consolidada (CSV)",
            data=csv_bytes,
            file_name=f"retornos_auditoria_{sufixo}.csv",
            mime="text/csv",
            width="stretch",
        )

# ==========================================================
# 🏁 RODAPÉ (padrão do portal)
# ==========================================================
fechar_dashboard(
    texto=(f"Auditoria TOA ({arquivo_toa.name}) ↔ Sinapse ({arquivo_sinapse.name})"),
)
