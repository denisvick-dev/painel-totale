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

import sys
import os
import re
import unicodedata
import logging
from io import BytesIO
from datetime import date
from typing import cast, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_hero,
    render_kpi,
    render_insight,
    render_table_html,
    COR_PRIMARIA,
    COR_SECUNDARIA,
    COR_SUCESSO,
    COR_ALERTA,
    COR_NEUTRO,
    TemaKPI,
    ColorMapDict,
)

logger = logging.getLogger(__name__)

# ==========================================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================================
st.set_page_config(
    page_title="Dono do Retorno | Auditoria TOA ↔ Sinapse",
    page_icon="🔍",
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
# ORDEM OFICIAL DAS COLUNAS SOLICITADAS
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

TOA_CIDADE: list[str] = [
    "Cidade",
    "Município",
    "Municipio",
    "CIDADE",
    "Localidade",
]

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

TOA_DATA: list[str] = [
    "Data",
    "DATA",
    "Data Agendamento",
    "Data Agenda",
    "DATA AGENDA",
    "Data Criação",
    "Data Criacao",
    "Data Abertura",
    "Dt Criação",
    "Data Execução",
    "Data Execucao",
    "Data Atividade",
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
    "CódAuxEquipe]",
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
    "Equipe",
]

SINAPSE_NOME_EQUIPE: list[str] = [
    "Nome Equipe",
    "Nome da Equipe",
    "Nome Técnico",
    "Nome Tecnico",
    "Nome do Técnico",
    "Técnico Dono",
    "Tecnico Dono",
    "Técnico",
    "Tecnico",
    "Executor",
    "NOME_EQUIPE",
    "Nome da Equipe/Técnico",
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
# UTILITÁRIOS DE TRATAMENTO
# ==========================================================
def _normalizar_texto(texto: Any) -> str:
    t = str(texto).lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _normalizar_contrato(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    txt = str(valor).strip().upper()
    txt = re.sub(r"\.0$", "", txt)
    txt = re.sub(r"[^\w]", "", txt)
    return txt.lstrip("0") if txt.lstrip("0") else txt


def _normalizar_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    novos: list[str] = []
    contador: dict[str, int] = {}
    for col in df.columns:
        nome = (
            str(col)
            .strip()
            .replace("\ufeff", "")
            .replace("\u200b", "")
            .replace("\xa0", " ")
        )
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
    nome = nome_arquivo.lower()
    stats: dict[str, str] = {"metodo": "", "separador": "", "encoding": ""}

    if nome.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(BytesIO(arquivo_bytes), dtype=str)
            df = _normalizar_nomes_colunas(df)
            df = _limpar_valores_string(df)
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
                melhor_score = score
                melhor_df = df
                melhor_cfg = cfg
        except Exception:
            continue

    if melhor_df is None or melhor_score == 0:
        raise ValueError("Não foi possível identificar o formato do arquivo CSV.")

    df_final = _normalizar_nomes_colunas(melhor_df)
    df_final = _limpar_valores_string(df_final)
    df_final = df_final.dropna(how="all").reset_index(drop=True)

    stats["metodo"] = "CSV"
    stats["separador"] = repr(melhor_cfg["sep"])
    stats["encoding"] = melhor_cfg["encoding"]
    return df_final, stats


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
# 1️⃣ REFINAR TOA (FILTRO TIPO ATIVIDADE + REMOÇÃO DE SUSPENSOS)
# ==========================================================
def refinar_base_toa(
    df_toa: pd.DataFrame,
    col_tipo: str | None,
    col_contrato: str | None,
    col_status: str | None,
    valor_filtro: str = VALOR_FILTRO_ATIVIDADE,
) -> tuple[pd.DataFrame, dict[str, int]]:
    stats = {
        "linhas_originais": len(df_toa),
        "retornos_encontrados": 0,
        "suspensos_removidos": 0,
        "sem_contrato": 0,
        "linhas_finais": 0,
    }

    df_filt = df_toa.copy()

    # 1. Filtro Tipo de Atividade
    if col_tipo and col_tipo in df_filt.columns:
        serie_norm = df_filt[col_tipo].astype(str).apply(_normalizar_texto)
        alvo_norm = _normalizar_texto(valor_filtro)
        mask_tipo = (serie_norm == alvo_norm) | (
            serie_norm.str.contains("retorno", na=False)
            & serie_norm.str.contains("credenciad", na=False)
        )
        df_filt = df_filt[mask_tipo].copy()

    stats["retornos_encontrados"] = len(df_filt)

    # 2. Remoção de Suspensos
    if col_status and col_status in df_filt.columns:
        mask_nao_suspenso = (
            ~df_filt[col_status]
            .astype(str)
            .str.contains("suspen", case=False, na=False)
        )
        stats["suspensos_removidos"] = int((~mask_nao_suspenso).sum())
        df_filt = df_filt[mask_nao_suspenso].copy()

    # 3. Validação de Contrato
    if col_contrato and col_contrato in df_filt.columns:
        chaves = df_filt[col_contrato].apply(_normalizar_contrato)
        mask_valido = chaves != ""
        stats["sem_contrato"] = int((~mask_valido).sum())
        df_filt = df_filt[mask_valido].copy()

    stats["linhas_finais"] = len(df_filt)
    return df_filt.reset_index(drop=True), stats


# ==========================================================
# 2️⃣ CRUZAR COM SINAPSE E MAPEAR COLUNAS OFICIAIS
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
    # Colunas TOA adicionais
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
    }

    df_t = df_toa_retornos.copy()
    df_s = df_sinapse.copy()

    # Limpeza de suspensos no Sinapse
    if col_status_sin and col_status_sin in df_s.columns:
        df_s = df_s[
            ~df_s[col_status_sin]
            .astype(str)
            .str.contains("suspen", case=False, na=False)
        ]

    df_t["_chave_contrato_"] = df_t[col_contrato_toa].apply(_normalizar_contrato)
    df_s["_chave_contrato_"] = df_s[col_contrato_sin].apply(_normalizar_contrato)
    df_s = df_s[df_s["_chave_contrato_"] != ""].copy()

    # Ordena para pegar a execução mais recente
    if col_data_sin and col_data_sin in df_s.columns:
        df_s["_dt_temp_"] = converter_data_robusto(df_s[col_data_sin])
        df_s = df_s.sort_values(by="_dt_temp_", ascending=False)
        df_s = df_s.drop(columns=["_dt_temp_"])

    # Extrações do Sinapse
    cols_sin_export: dict[str, str] = {}
    if col_cod_aux_sin and col_cod_aux_sin in df_s.columns:
        cols_sin_export[col_cod_aux_sin] = "DONO_CÓD_AUX_EQUIPE"
    if col_nome_equipe_sin and col_nome_equipe_sin in df_s.columns:
        cols_sin_export[col_nome_equipe_sin] = "DONO_TÉCNICO_NOME"
    if col_supervisor_sin and col_supervisor_sin in df_s.columns:
        cols_sin_export[col_supervisor_sin] = "DONO_MONITOR_SUPERVISOR"
    if col_data_sin and col_data_sin in df_s.columns:
        cols_sin_export[col_data_sin] = "SINAPSE_DATA_ORIGINAL"

    df_s_resumo = df_s[["_chave_contrato_"] + list(cols_sin_export.keys())].copy()
    df_s_resumo = df_s_resumo.rename(columns=cols_sin_export)
    df_s_resumo = df_s_resumo.drop_duplicates(subset=["_chave_contrato_"], keep="first")

    df_resultado = df_t.merge(df_s_resumo, on="_chave_contrato_", how="left")
    df_resultado = df_resultado.drop(columns=["_chave_contrato_"])

    # Tratamento das colunas do Dono
    if "DONO_CÓD_AUX_EQUIPE" in df_resultado.columns:
        df_resultado["DONO_CÓD_AUX_EQUIPE"] = df_resultado[
            "DONO_CÓD_AUX_EQUIPE"
        ].fillna("SEM_EQUIPE")
        mask_identificado = df_resultado["DONO_CÓD_AUX_EQUIPE"] != "SEM_EQUIPE"
    else:
        df_resultado["DONO_CÓD_AUX_EQUIPE"] = "SEM_EQUIPE"
        mask_identificado = pd.Series(False, index=df_resultado.index)

    if "DONO_TÉCNICO_NOME" in df_resultado.columns:
        df_resultado["DONO_TÉCNICO_NOME"] = df_resultado["DONO_TÉCNICO_NOME"].fillna(
            "NÃO INFORMADO"
        )
    else:
        df_resultado["DONO_TÉCNICO_NOME"] = "NÃO INFORMADO"

    if "DONO_MONITOR_SUPERVISOR" in df_resultado.columns:
        df_resultado["DONO_MONITOR_SUPERVISOR"] = df_resultado[
            "DONO_MONITOR_SUPERVISOR"
        ].fillna("SEM MONITOR")
    else:
        df_resultado["DONO_MONITOR_SUPERVISOR"] = "SEM MONITOR"

    if "SINAPSE_DATA_ORIGINAL" not in df_resultado.columns:
        df_resultado["SINAPSE_DATA_ORIGINAL"] = "-"
    else:
        df_resultado["SINAPSE_DATA_ORIGINAL"] = df_resultado[
            "SINAPSE_DATA_ORIGINAL"
        ].fillna("-")

    df_resultado["STATUS_AUDITORIA"] = mask_identificado.map(
        {
            True: "Identificado",
            False: "Sem Dono no Sinapse",
        }
    )

    # Padronização e estruturação na ordem exata solicitada
    df_padronizado = pd.DataFrame(index=df_resultado.index)

    df_padronizado["Contrato"] = (
        df_resultado[col_contrato_toa]
        if col_contrato_toa in df_resultado.columns
        else "-"
    )
    df_padronizado["Login do Técnico"] = (
        df_resultado[col_login_toa]
        if col_login_toa and col_login_toa in df_resultado.columns
        else "-"
    )
    df_padronizado["Recurso"] = (
        df_resultado[col_recurso_toa]
        if col_recurso_toa and col_recurso_toa in df_resultado.columns
        else "-"
    )
    df_padronizado["DONO_CÓD_AUX_EQUIPE"] = df_resultado["DONO_CÓD_AUX_EQUIPE"]
    df_padronizado["DONO_TÉCNICO_NOME"] = df_resultado["DONO_TÉCNICO_NOME"]
    df_padronizado["DONO_MONITOR_SUPERVISOR"] = df_resultado["DONO_MONITOR_SUPERVISOR"]
    df_padronizado["STATUS_AUDITORIA"] = df_resultado["STATUS_AUDITORIA"]
    df_padronizado["Status da Atividade"] = (
        df_resultado[col_status_toa]
        if col_status_toa and col_status_toa in df_resultado.columns
        else "-"
    )
    df_padronizado["Intervalo de Tempo"] = (
        df_resultado[col_intervalo_toa]
        if col_intervalo_toa and col_intervalo_toa in df_resultado.columns
        else "-"
    )
    df_padronizado["Endereço"] = (
        df_resultado[col_endereco_toa]
        if col_endereco_toa and col_endereco_toa in df_resultado.columns
        else "-"
    )
    df_padronizado["Cidade"] = (
        df_resultado[col_cidade_toa]
        if col_cidade_toa and col_cidade_toa in df_resultado.columns
        else "-"
    )
    df_padronizado["Número da O.S 1"] = (
        df_resultado[col_numero_os_toa]
        if col_numero_os_toa and col_numero_os_toa in df_resultado.columns
        else "-"
    )
    df_padronizado["SINAPSE_DATA_ORIGINAL"] = df_resultado["SINAPSE_DATA_ORIGINAL"]

    df_padronizado = df_padronizado.fillna("-")

    total = len(df_padronizado)
    com_equipe = int(mask_identificado.sum())
    stats["com_cod_equipe"] = com_equipe
    stats["sem_dono"] = total - com_equipe
    stats["taxa_identificacao"] = (
        round((com_equipe / total * 100), 1) if total > 0 else 0.0
    )

    return df_padronizado[COLUNAS_ORDEM_OFICIAL], stats


# ==========================================================
# EXPORTAÇÃO EXCEL MULTI-ABAS
# ==========================================================
def gerar_excel_por_equipe(
    df_consolidado: pd.DataFrame,
    coluna_agrupamento: str = "DONO_CÓD_AUX_EQUIPE",
) -> BytesIO:
    output = BytesIO()
    try:
        import xlsxwriter  # noqa: F401

        engine = "xlsxwriter"
    except ImportError:
        engine = "openpyxl"

    with pd.ExcelWriter(output, engine=engine) as writer:
        df_consolidado.to_excel(writer, sheet_name="Consolidado_Geral", index=False)

        if coluna_agrupamento in df_consolidado.columns:
            grupos = df_consolidado.groupby(coluna_agrupamento)
            for grupo_nome, df_g in grupos:
                nome_limpo = str(grupo_nome)[:30]
                nome_limpo = re.sub(r"[\\/*?:\[\]]", "-", nome_limpo).strip()
                if not nome_limpo:
                    nome_limpo = "Sem_Equipe"
                df_g.to_excel(writer, sheet_name=nome_limpo, index=False)

        if engine == "xlsxwriter":
            wb: Any = writer.book
            header_fmt = wb.add_format(
                {
                    "bold": True,
                    "bg_color": "#012869",
                    "font_color": "white",
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                }
            )
            for sheet_name, ws in writer.sheets.items():
                ws_any: Any = ws
                ws_any.set_column(0, 20, 20)

    output.seek(0)
    return output


def secao(titulo: str, sub: str = "") -> None:
    subhtml = (
        f'<span style="font-size:12px;color:#9CA3AF;margin-left:12px;">{sub}</span>'
        if sub
        else ""
    )
    st.markdown(
        f'<div style="margin:28px 0 12px 0;padding-bottom:8px;border-bottom:1px solid #E5E7EB;">'
        f"<span style=\"font-family:'Manrope',sans-serif;font-size:16px;font-weight:700;color:#012869;\">{titulo}</span>"
        f"{subhtml}</div>",
        unsafe_allow_html=True,
    )


# ==========================================================
# 🎨 CABEÇALHO HERO
# ==========================================================
render_hero(
    titulo="🔍 Donos do Retorno — Equipe & Monitor",
    subtitulo="Auditoria precisa dos retornos do TOA cruzados com o Sinapse, excluindo suspensos e destacando a cadeia de supervisão.",
    badge="Auditoria TOA ↔ Sinapse",
)

# ==========================================================
# 📁 UPLOAD DOS ARQUIVOS
# ==========================================================
secao("Fontes de Dados", "importe os arquivos do TOA e do Sinapse")

c_up1, c_up2 = st.columns(2)

with c_up1:
    st.markdown("### 1️⃣ Base TOA (Retornos)")
    st.caption("Origem dos retornos a serem auditados (Tipo = Retorno Credenciada).")
    arquivo_toa = st.file_uploader(
        "Importar arquivo TOA",
        type=["csv", "xlsx", "xls"],
        key="up_toa",
    )
    if arquivo_toa:
        st.success(f"Carregado: {arquivo_toa.name}", icon="✅")

with c_up2:
    st.markdown("### 2️⃣ Base Sinapse (Histórico)")
    st.caption(
        "Origem dos contratos para identificar CódAuxEquipe, Nome Equipe e Monitor."
    )
    arquivo_sinapse = st.file_uploader(
        "Importar arquivo Sinapse",
        type=["csv", "xlsx", "xls"],
        key="up_sinapse",
    )
    if arquivo_sinapse:
        st.success(f"Carregado: {arquivo_sinapse.name}", icon="✅")

if not arquivo_toa or not arquivo_sinapse:
    st.markdown("<br>", unsafe_allow_html=True)
    render_insight(
        "Para iniciar a auditoria, envie **ambos os arquivos**: a base de retornos (**TOA**) e o histórico (**Sinapse**).",
        tipo="info",
    )
    st.stop()

# ==========================================================
# 📥 PROCESSAMENTO DOS ARQUIVOS
# ==========================================================
try:
    df_toa_raw, _ = carregar_arquivo(arquivo_toa.read(), arquivo_toa.name)
    df_sin_raw, _ = carregar_arquivo(arquivo_sinapse.read(), arquivo_sinapse.name)
except Exception as e:
    render_insight(f"Erro ao ler os arquivos enviados: `{e}`", tipo="critico")
    st.stop()

# Identificação das colunas — TOA
col_tipo_toa = identificar_coluna(df_toa_raw, TOA_TIPO_ATIVIDADE)
col_contrato_toa = identificar_coluna(df_toa_raw, TOA_CONTRATO)
col_login_toa = identificar_coluna(df_toa_raw, TOA_LOGIN_TECNICO)
col_recurso_toa = identificar_coluna(df_toa_raw, TOA_RECURSO)
col_status_toa = identificar_coluna(df_toa_raw, TOA_STATUS_ATIVIDADE)
col_intervalo_toa = identificar_coluna(df_toa_raw, TOA_INTERVALO_TEMPO)
col_endereco_toa = identificar_coluna(df_toa_raw, TOA_ENDERECO)
col_cidade_toa = identificar_coluna(df_toa_raw, TOA_CIDADE)
col_numero_os_toa = identificar_coluna(df_toa_raw, TOA_NUMERO_OS)

# Identificação das colunas — Sinapse
col_contrato_sin = identificar_coluna(df_sin_raw, SINAPSE_CONTRATO)
col_cod_aux_sin = identificar_coluna(df_sin_raw, SINAPSE_COD_AUX_EQUIPE)
col_nome_equipe_sin = identificar_coluna(df_sin_raw, SINAPSE_NOME_EQUIPE)
col_supervisor_sin = identificar_coluna(df_sin_raw, SINAPSE_SUPERVISOR_MONITOR)
col_data_sin = identificar_coluna(df_sin_raw, SINAPSE_DATA)
col_status_sin = identificar_coluna(df_sin_raw, SINAPSE_STATUS)

if not col_contrato_toa:
    render_insight(
        "❌ Coluna de **Contrato** não localizada no arquivo TOA.", tipo="critico"
    )
    st.stop()

if not col_contrato_sin:
    render_insight(
        "❌ Coluna de **Contrato** não localizada no arquivo Sinapse.", tipo="critico"
    )
    st.stop()

# ── 1. Refina TOA (Retorno Credenciada + Sem Suspensos) ──
df_toa_refinado, stats_toa_filt = refinar_base_toa(
    df_toa=df_toa_raw,
    col_tipo=col_tipo_toa,
    col_contrato=col_contrato_toa,
    col_status=col_status_toa,
    valor_filtro=VALOR_FILTRO_ATIVIDADE,
)

if df_toa_refinado.empty:
    render_insight(
        f"Nenhum registro ativo (não suspenso) do tipo **'{VALOR_FILTRO_ATIVIDADE}'** foi localizado no TOA.",
        tipo="critico",
    )
    st.stop()

# ── 2. Cruzamento TOA ↔ Sinapse e Padronização Oficial ──
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
secao("Filtros do Relatório", "refine a visualização por equipe ou supervisor")

f_col1, f_col2, f_col3 = st.columns(3)

with f_col1:
    monitores_disponiveis = sorted(
        df_auditado["DONO_MONITOR_SUPERVISOR"].unique().tolist()
    )
    monitor_sel = st.multiselect(
        "👔 Monitor (Supervisor)", monitores_disponiveis, default=[]
    )

with f_col2:
    equipes_disponiveis = sorted(df_auditado["DONO_CÓD_AUX_EQUIPE"].unique().tolist())
    equipe_sel = st.multiselect("🏷️ CódAuxEquipe", equipes_disponiveis, default=[])

with f_col3:
    status_aud = sorted(df_auditado["STATUS_AUDITORIA"].unique().tolist())
    status_aud_sel = st.multiselect("📌 Status da Auditoria", status_aud, default=[])

df_view = df_auditado.copy()
if monitor_sel:
    df_view = df_view[df_view["DONO_MONITOR_SUPERVISOR"].isin(monitor_sel)]
if equipe_sel:
    df_view = df_view[df_view["DONO_CÓD_AUX_EQUIPE"].isin(equipe_sel)]
if status_aud_sel:
    df_view = df_view[df_view["STATUS_AUDITORIA"].isin(status_aud_sel)]

# ==========================================================
# 📊 PAINEL EXECUTIVO
# ==========================================================
secao("Indicadores da Auditoria", "resumo executivo do cruzamento")

k1, k2, k3, k4 = st.columns(4)
render_kpi(
    k1,
    "Retornos Auditados",
    f"{stats_cruzamento['total_retornos']:,}",
    f"{stats_toa_filt['suspensos_removidos']} suspensos removidos",
    tema="azul",
)
render_kpi(
    k2,
    "Donos Localizados",
    f"{stats_cruzamento['com_cod_equipe']:,}",
    f"{stats_cruzamento['taxa_identificacao']}% com CódAuxEquipe",
    tema="verde",
)
render_kpi(
    k3,
    "Sem Dono no Sinapse",
    f"{stats_cruzamento['sem_dono']:,}",
    "contrato ausente no histórico",
    tema="vermelho",
)
total_monitores = df_auditado[df_auditado["DONO_MONITOR_SUPERVISOR"] != "SEM MONITOR"][
    "DONO_MONITOR_SUPERVISOR"
].nunique()
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
secao("Legenda de Supervisores", "identificação visual por monitor")

leg_cols = st.columns(4)
with leg_cols[0]:
    st.markdown(
        '<div style="padding:10px;border-radius:6px;background:#DBEAFE;color:#1E40AF;font-weight:700;font-size:12px;border:1px solid #BFDBFE;">'
        "🔵 EDSON MARCO PINHEIRO"
        "</div>",
        unsafe_allow_html=True,
    )
with leg_cols[1]:
    st.markdown(
        '<div style="padding:10px;border-radius:6px;background:#DCFCE7;color:#166534;font-weight:700;font-size:12px;border:1px solid #BBF7D0;">'
        "🟢 MARCOS ROBERTO DO NASCIMENTO"
        "</div>",
        unsafe_allow_html=True,
    )
with leg_cols[2]:
    st.markdown(
        '<div style="padding:10px;border-radius:6px;background:#FCE7F3;color:#9D174D;font-weight:700;font-size:12px;border:1px solid #FBCFE8;">'
        "🌸 MAICON APARECIDO FARIA"
        "</div>",
        unsafe_allow_html=True,
    )
with leg_cols[3]:
    st.markdown(
        '<div style="padding:10px;border-radius:6px;background:#F3F4F6;color:#374151;font-weight:700;font-size:12px;border:1px solid #E5E7EB;">'
        "⚪ NELSON ALVES OLIVEIRA JUNIOR"
        "</div>",
        unsafe_allow_html=True,
    )

# ==========================================================
# 🔍 BASE DE DADOS DESTACADA (CONFORME componentes.py)
# ==========================================================
secao(
    "Base Detalhada de Retornos",
    f"{len(df_view):,} registros exibidos na ordem oficial",
)

# Configuração de mapeamento cromático para render_table_html sem perder tipografia ou cores
color_rules: ColorMapDict = {
    "DONO_MONITOR_SUPERVISOR": [
        (
            lambda val: "edson marco pinheiro" in _normalizar_texto(val),
            "#1E40AF; background-color: #DBEAFE; border-left: 3px solid #1E40AF",
        ),
        (
            lambda val: "marcos roberto do nascimento" in _normalizar_texto(val),
            "#166534; background-color: #DCFCE7; border-left: 3px solid #166534",
        ),
        (
            lambda val: "maicon aparecido faria" in _normalizar_texto(val),
            "#9D174D; background-color: #FCE7F3; border-left: 3px solid #9D174D",
        ),
        (
            lambda val: any(
                x in _normalizar_texto(val)
                for x in ["nelson alves oliveira junior", "nelson alves"]
            ),
            "#374151; background-color: #F3F4F6; border-left: 3px solid #374151",
        ),
        (
            lambda val: str(val) in ("SEM MONITOR", "-", ""),
            "#B45309; background-color: #FFFBEB",
        ),
    ],
    "DONO_CÓD_AUX_EQUIPE": [
        (
            lambda val: str(val) in ("SEM_EQUIPE", "-", ""),
            "#991B1B; background-color: #FEF2F2",
        ),
        (
            lambda val: True,
            "#3730A3; background-color: #EEF2FF; font-family: var(--font-codigo)",
        ),
    ],
    "DONO_TÉCNICO_NOME": [
        (
            lambda val: str(val) in ("NÃO INFORMADO", "-", ""),
            "#9CA3AF; background-color: transparent",
        ),
        (lambda val: True, "#15803D; background-color: #F0FDF4"),
    ],
    "STATUS_AUDITORIA": [
        (lambda val: str(val) == "Identificado", "#03543F; background-color: #DEF7EC"),
        (lambda val: True, "#9B1C1C; background-color: #FDE8E8"),
    ],
}

render_table_html(
    df=df_view,
    color_rules=color_rules,
    height=480,
    max_rows=100,
)

# ==========================================================
# 📤 EXPORTAÇÃO
# ==========================================================
secao("Exportação", "download dos relatórios oficiais")

excel_bytes = gerar_excel_por_equipe(df_view, coluna_agrupamento="DONO_CÓD_AUX_EQUIPE")
nome_arquivo = f"retornos_auditoria_{date.today().strftime('%Y%m%d')}.xlsx"

exp_c1, exp_c2 = st.columns(2)
with exp_c1:
    st.download_button(
        "📊 Baixar Relatório Excel (Abas por CódAuxEquipe)",
        data=excel_bytes,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
with exp_c2:
    csv_bytes = df_view.to_csv(index=False, sep=";", encoding="utf-8-sig").encode(
        "utf-8-sig"
    )
    st.download_button(
        "📄 Baixar Base Consolidada (CSV)",
        data=csv_bytes,
        file_name=f"retornos_auditoria_{date.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ==========================================================
# 🏁 RODAPÉ
# ==========================================================
st.markdown(
    f'<div style="text-align:center;color:#9CA3AF;font-size:11px;padding:24px 0;'
    f'margin-top:32px;border-top:1px solid #F1F5F9;">'
    f"Auditoria TOA ({arquivo_toa.name}) ↔ Sinapse ({arquivo_sinapse.name}) "
    f'· Gerado em {date.today().strftime("%d/%m/%Y")}</div>',
    unsafe_allow_html=True,
)
