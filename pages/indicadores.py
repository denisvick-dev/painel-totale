import streamlit as st
import pandas as pd
import numpy as np
import requests
import unicodedata
from io import BytesIO, StringIO
from typing import Literal, Optional, Dict, List, Tuple, Union, cast, Any, Hashable
from datetime import datetime, timezone

# Importação do Design System TOTALE
from components.componentes import (
    aplicar_estilo,
    render_sidebar_brand,
    render_sidebar_divider,
    render_sidebar_footer_info,
    render_sidebar_status,
    render_section_header,
    render_kpi,
    render_metric_card,
    render_insight,
    render_empty_state,
    render_progress_bar,
    render_table_html,
    converter_data_br,
    Cores,
)

# Configuração da Página
st.set_page_config(
    page_title="Painel de Qualidade e Indicadores Técnicos",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="⚡",
)

# Inicialização do Design System TOTALE
aplicar_estilo()

# Definição estrita para junções suportadas pelo Pandas
MergeHowType = Literal["left", "right", "outer", "inner", "cross"]

# --- DATA/HORA DE FALLBACK (SISTEMA) ---
DATA_SISTEMA_STR = datetime.now().strftime("%d/%m/%Y às %H:%M")

# --- CONFIGURAÇÃO DOS ARQUIVOS ---
DRIVE_FILE_ID = "1k6NrvdZzdSV_sGOQkMKIssEhh7p7wyO0"
LISTA_ATIVOS_ID = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"

SHEET_LOGIN_MAPPING: Dict[str, str] = {
    "Geoloc_Os": "LOGIN_TEC",
    "Aderencia_Ura": "CD_LOGIN_TECNICO",
    "Nr35": "LOGIN_FIELD",
    "Baixa_Pda": "LOGIN_TECNICO_DESPACHADO",
    "Tec1": "COD_TECNICO_WFM",
    "OS_Digital": "LOGIN_TEC",
}

METAS_POR_ABA: Dict[str, float] = {
    "Geoloc_Os": 95.0,
    "OS_Digital": 95.0,
    "Aderencia_Ura": 95.0,
    "Nr35": 95.0,
    "Tec1": 97.0,
    "Baixa_Pda": 95.0,
}

NOMES_AMIGAVEIS: Dict[str, str] = {
    "Geoloc_Os": "Geolocalização",
    "OS_Digital": "O.S. Digital",
    "Aderencia_Ura": "Aderência URA",
    "Nr35": "NR35",
    "Tec1": "TEC1 - Status Nota",
    "Baixa_Pda": "Baixa PDA",
}

NOMES_ICONES: Dict[str, str] = {
    "Geoloc_Os": "📍",
    "OS_Digital": "💻",
    "Aderencia_Ura": "📞",
    "Nr35": "🔰",
    "Tec1": "🔧",
    "Baixa_Pda": "📱",
}

# Coluna de data de cada base. TEC1 usa DAT_NOTA — a data final da base.
COLUNAS_DATA_POR_ABA: Dict[str, List[str]] = {
    "Geoloc_Os": ["DATA", "DT", "DATA_OS", "DT_EXECUCAO"],
    "OS_Digital": ["DATA", "DT", "DATA_OS"],
    "Aderencia_Ura": ["DT_AGENDA", "DATA", "DATA_AGENDA"],
    "Nr35": ["DATA", "DT", "DATA_OS"],
    "Tec1": ["DAT_NOTA", "DATA_NOTA", "DT_NOTA", "DATA"],
    "Baixa_Pda": ["DATA_NET", "DATA", "DT_BAIXA", "DATA_BAIXA"],
}

CRITERIOS_POR_ABA: Dict[str, Dict[str, Any]] = {
    "Geoloc_Os": {
        "colunas_possiveis_num": [
            "MENOR_STATUS_GEOLOC",
            "MENOR STATUS GEOLOC",
            "MENOR_STATUS_GEO",
        ],
        "colunas_possiveis_den": ["STATUS_GEOLOC", "STATUS GEOLOC", "STATUS_GEO"],
        "tipo": "dual_column_ratio",
        "numerador": ["COM PADRAO", "COM PADRÃO", "COMPADRAO"],
        "denominador": [
            "COM PADRAO",
            "COM PADRÃO",
            "COMPADRAO",
            "SEM PADRAO",
            "SEM PADRÃO",
            "SEMPADRAO",
        ],
        "label": "Atingimento Geoloc Com Padrão",
        "nome_atingido": "Com Padrão",
        "nome_nao_atingido": "Sem Padrão",
    },
    "Nr35": {
        "colunas_possiveis": [
            "SUBIU",
            "DS_SUBIU",
            "STATUS_SUBIU",
            "SUBIU_ESCADA",
            "FLG_SUBIU",
        ],
        "tipo": "nao_vazio_total",
        "label": "Aderência NR35 (Subiu)",
        "nome_atingido": "Subiu",
        "nome_nao_atingido": "Não Subiu",
    },
    "Aderencia_Ura": {
        "colunas_possiveis": ["OBJETIVO_URA", "OBJETIVO URA", "OBJETIVO", "STATUS_URA"],
        "tipo": "sucesso_total",
        "numerador": ["SUCESSO"],
        "label": "Aderência URA (Sucesso)",
        "nome_atingido": "Sucesso",
        "nome_nao_atingido": "Insucesso",
    },
    "Baixa_Pda": {
        "colunas_possiveis": [
            "STATUS BAIXA",
            "STATUS_BAIXA",
            "STATUSBAIXA",
            "DS_STATUS_BAIXA",
        ],
        "tipo": "sucesso_total",
        "numerador": ["TOA"],
        "label": "Baixa PDA (TOA)",
        "nome_atingido": "Baixa TOA",
        "nome_nao_atingido": "Outras Baixas",
    },
    "Tec1": {
        "colunas_possiveis": [
            "DSC_STATUS_NOTA",
            "DSC STATUS NOTA",
            "STATUS_NOTA",
            "STATUS NOTA",
        ],
        "tipo": "sucesso_total",
        "numerador": ["COM PADRAO", "COM PADRÃO", "COMPADRAO"],
        "label": "Status Nota (Com Padrão)",
        "nome_atingido": "Com Padrão",
        "nome_nao_atingido": "Sem Padrão",
    },
    "OS_Digital": {
        "colunas_possiveis": [
            "GEROU_OS",
            "GEROU OS",
            "GEROUOS",
            "FLG_GEROU_OS",
            "STATUS_GEROU_OS",
        ],
        "tipo": "sucesso_total",
        "numerador": ["SIM", "S", "1", "TRUE", "SIM."],
        "label": "Gerou OS Digital (Sim)",
        "nome_atingido": "O.S. Gerada",
        "nome_nao_atingido": "Não Gerada",
    },
}


# --- FUNÇÕES UTILITÁRIAS E DE EXTRAÇÃO DE DATA ---
def remover_acentos_e_padronizar(texto: Any) -> str:
    if not isinstance(texto, str):
        texto = str(texto)
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return sem_acento.lower().strip().replace("_", "").replace(" ", "").replace("-", "")


def normalizar_chave(serie: pd.Series) -> pd.Series:
    return serie.astype(str).str.strip().str.upper()


def encontrar_coluna_flexivel(
    df: pd.DataFrame, nomes_candidatos: List[str]
) -> Optional[str]:
    cols_map: Dict[str, str] = {
        remover_acentos_e_padronizar(c): str(c) for c in df.columns
    }
    for candidato in nomes_candidatos:
        cand_norm = remover_acentos_e_padronizar(candidato)
        if cand_norm in cols_map:
            return cols_map[cand_norm]
    return None


def _tokens_coluna(nome_coluna: str) -> List[str]:
    bruto = str(nome_coluna).replace("-", " ").replace("_", " ").replace(".", " ")
    return [remover_acentos_e_padronizar(t) for t in bruto.split() if str(t).strip()]


def _coluna_e_data(nome_coluna: str) -> bool:
    """Reconhece DATA, DT_AGENDA, DATA_NET e também DAT_NOTA (TEC1)."""
    tokens = _tokens_coluna(nome_coluna)
    prefixos = ("dt", "data", "date", "dat")
    if any(tok == pref or tok.startswith(pref) for tok in tokens for pref in prefixos):
        return True
    c_norm = remover_acentos_e_padronizar(nome_coluna)
    return any(
        k in c_norm
        for k in [
            "created",
            "fechamento",
            "execucao",
            "abertura",
            "notificacao",
        ]
    )


def _serie_para_datetime(serie: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(serie):
        return pd.to_datetime(serie, errors="coerce")

    try:
        convertida = converter_data_br(serie)
        if convertida is not None:
            s_conv = pd.to_datetime(convertida, errors="coerce")
            if int(s_conv.notna().sum()) > 0:
                return s_conv
    except Exception:
        pass

    numeric = pd.to_numeric(serie, errors="coerce")
    numeric_ok = numeric.dropna()
    if not numeric_ok.empty and float(numeric_ok.between(20000, 80000).mean()) > 0.8:
        return pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")

    return pd.to_datetime(serie, errors="coerce", dayfirst=True)


def _formatar_data_maxima(max_dt: Any) -> str:
    if hasattr(max_dt, "hour") and (
        int(getattr(max_dt, "hour", 0) or 0) != 0
        or int(getattr(max_dt, "minute", 0) or 0) != 0
    ):
        return max_dt.strftime("%d/%m/%Y às %H:%M")
    if hasattr(max_dt, "strftime"):
        return max_dt.strftime("%d/%m/%Y")
    return str(max_dt)


def maior_texto_data(datas: List[str], fallback: str) -> str:
    """Escolhe a maior data entre textos dd/mm/yyyy (com ou sem hora)."""
    validas: List[pd.Timestamp] = []
    for texto in datas:
        if not texto:
            continue
        parsed = pd.to_datetime(
            str(texto).replace(" às ", " "), dayfirst=True, errors="coerce"
        )
        if pd.notna(parsed):
            validas.append(pd.Timestamp(parsed))
    if not validas:
        return fallback
    return _formatar_data_maxima(max(validas))


def extrair_data_maxima_aba(
    df: Optional[pd.DataFrame], aba: Optional[str] = None
) -> Optional[str]:
    """Inspeciona a data da base e devolve a maior data válida (data final).

    No TEC1 a referência é DAT_NOTA, não o relógio do sistema.
    """
    if df is None or df.empty:
        return None

    cols_prioritarias: List[str] = []
    if aba:
        for k_aba, candidatas in COLUNAS_DATA_POR_ABA.items():
            if remover_acentos_e_padronizar(k_aba) == remover_acentos_e_padronizar(aba):
                for cand in candidatas:
                    encontrada = encontrar_coluna_flexivel(df, [cand])
                    if encontrada and encontrada not in cols_prioritarias:
                        cols_prioritarias.append(encontrada)
                break

    if cols_prioritarias:
        cols_candidatas = cols_prioritarias
    else:
        cols_candidatas = [str(col) for col in df.columns if _coluna_e_data(str(col))]

    max_dt: Optional[pd.Timestamp] = None
    # Trava de segurança para ignorar datas do futuro espúrias (anos incorretos > hoje)
    limite_futuro = pd.Timestamp.now() + pd.Timedelta(days=2)
    limite_passado = pd.Timestamp("2000-01-01")

    for col in cols_candidatas:
        try:
            s_dt = _serie_para_datetime(df[col])
            s_valid = s_dt.dropna()
            s_valid = s_valid[(s_valid <= limite_futuro) & (s_valid >= limite_passado)]
            if not s_valid.empty:
                c_max = pd.Timestamp(s_valid.max())
                if max_dt is None or c_max > max_dt:
                    max_dt = c_max
        except Exception:
            continue

    if max_dt is not None and not pd.isna(max_dt):
        try:
            return _formatar_data_maxima(max_dt)
        except Exception:
            return str(max_dt)

    return None


def gerar_regras_cores(
    df_data: pd.DataFrame,
    col_realizado: Optional[str] = None,
    col_desvio: Optional[str] = None,
    col_meta: Optional[str] = None,
    meta_padrao: float = 95.0,
) -> Dict[str, Dict[str, str]]:
    """Gera mapeamentos de cores para render_table_html destacando percentuais e desvios."""
    color_rules: Dict[str, Dict[str, str]] = {}

    if df_data is None or df_data.empty:
        return color_rules

    if col_realizado and col_realizado in df_data.columns:
        regras_realizado: Dict[str, str] = {}
        for _, row in df_data.iterrows():
            val_real = row[col_realizado]
            meta_val = (
                row[col_meta]
                if (col_meta and col_meta in df_data.columns)
                else meta_padrao
            )
            try:
                v = float(val_real)
                m = float(meta_val)
                regras_realizado[str(val_real)] = "sucesso" if v >= m else "alerta"
            except (ValueError, TypeError):
                pass
        color_rules[col_realizado] = regras_realizado

    if col_desvio and col_desvio in df_data.columns:
        regras_desvio: Dict[str, str] = {}
        for _, row in df_data.iterrows():
            val_desv = row[col_desvio]
            try:
                d = float(val_desv)
                regras_desvio[str(val_desv)] = "sucesso" if d >= 0 else "alerta"
            except (ValueError, TypeError):
                pass
        color_rules[col_desvio] = regras_desvio

    return color_rules


# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=3600)
def load_excel_from_drive(file_id: str) -> Optional[Dict[str, pd.DataFrame]]:
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        all_sheets: Dict[str, pd.DataFrame] = pd.read_excel(
            BytesIO(response.content), sheet_name=None, engine="openpyxl"
        )
        for name in all_sheets:
            all_sheets[name].columns = all_sheets[name].columns.astype(str).str.strip()
        return all_sheets
    except Exception as e:
        st.error(f"❌ Erro ao carregar Excel do Drive: {e}")
        return None


@st.cache_data(ttl=3600)
def load_google_sheet(sheet_id: str) -> Optional[pd.DataFrame]:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        df.columns = df.columns.astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar lista_ativos: {e}")
        return None


def resolver_chave_excel(sheet_name: str, df_sheet: pd.DataFrame) -> Optional[str]:
    sheet_name_norm = remover_acentos_e_padronizar(sheet_name)

    for aba_config, col_esperada in SHEET_LOGIN_MAPPING.items():
        if remover_acentos_e_padronizar(aba_config) == sheet_name_norm:
            col_encontrada = encontrar_coluna_flexivel(
                df_sheet, [col_esperada, aba_config]
            )
            if col_encontrada:
                return col_encontrada

    todas_cols: List[str] = list(SHEET_LOGIN_MAPPING.values()) + list(
        SHEET_LOGIN_MAPPING.keys()
    )
    col_encontrada = encontrar_coluna_flexivel(df_sheet, todas_cols)
    if col_encontrada:
        return col_encontrada

    for col in df_sheet.columns:
        c_norm = remover_acentos_e_padronizar(col)
        if any(
            termo in c_norm
            for termo in ["login", "codtec", "cdtec", "matricula", "tecnico"]
        ):
            return str(col)

    return None


def merge_aba(
    df_sheet: pd.DataFrame,
    df_ativos: pd.DataFrame,
    chave_excel: str,
    col_login_ativos: str,
    col_tec_ativos: Optional[str],
    col_mon_ativos: Optional[str],
    col_base_ativos: Optional[str],
    how: MergeHowType = "left",
) -> pd.DataFrame:
    cols_importar: List[str] = [
        c for c in [col_tec_ativos, col_mon_ativos, col_base_ativos] if c is not None
    ]
    cols_right: List[str] = [col_login_ativos] + cols_importar

    left = df_sheet.copy()
    right = df_ativos[cols_right].drop_duplicates(subset=[col_login_ativos]).copy()

    left["_KEY"] = normalizar_chave(left[chave_excel])
    right["_KEY"] = normalizar_chave(right[col_login_ativos])
    right = right.drop(columns=[col_login_ativos])

    merged = pd.merge(left, right, on="_KEY", how=how, suffixes=("", "_ativos"))

    renomear: Dict[str, str] = {}
    if (
        col_tec_ativos
        and col_tec_ativos in merged.columns
        and col_tec_ativos != "Tecnico"
    ):
        renomear[col_tec_ativos] = "Tecnico"
    if (
        col_mon_ativos
        and col_mon_ativos in merged.columns
        and col_mon_ativos != "Monitor"
    ):
        renomear[col_mon_ativos] = "Monitor"
    if (
        col_base_ativos
        and col_base_ativos in merged.columns
        and col_base_ativos != "Base"
    ):
        renomear[col_base_ativos] = "Base"

    if renomear:
        merged = merged.rename(columns=renomear)

    return merged.drop(columns=["_KEY"])


def merge_todas_abas(
    excel_sheets: Dict[str, pd.DataFrame],
    df_ativos: pd.DataFrame,
    col_login_ativos: str,
    col_tec_ativos: Optional[str],
    col_mon_ativos: Optional[str],
    col_base_ativos: Optional[str],
    how: MergeHowType = "left",
) -> Dict[str, Dict[str, Any]]:
    resultados: Dict[str, Dict[str, Any]] = {}
    for aba, df_sheet in excel_sheets.items():
        chave_excel = resolver_chave_excel(aba, df_sheet)

        if not chave_excel:
            resultados[aba] = {
                "df": None,
                "erro": "Coluna de login não detectada.",
                "chave_excel": None,
            }
            continue

        try:
            df_merged = merge_aba(
                df_sheet,
                df_ativos,
                chave_excel,
                col_login_ativos,
                col_tec_ativos,
                col_mon_ativos,
                col_base_ativos,
                how,
            )
            resultados[aba] = {
                "df": df_merged,
                "erro": None,
                "chave_excel": chave_excel,
            }
        except Exception as e:
            resultados[aba] = {"df": None, "erro": str(e), "chave_excel": chave_excel}
    return resultados


# --- MOTOR DE CÁLCULO ---
def calcular_aderencia_criterio(
    df: pd.DataFrame, aba: str
) -> Tuple[Optional[str], Optional[pd.Series], Dict[str, Any]]:
    regra: Optional[Dict[str, Any]] = None
    for k_aba, v_regra in CRITERIOS_POR_ABA.items():
        if remover_acentos_e_padronizar(k_aba) == remover_acentos_e_padronizar(aba):
            regra = v_regra
            break

    if not regra:
        return None, None, {}

    tipo = regra["tipo"]

    if tipo == "dual_column_ratio":
        col_num = encontrar_coluna_flexivel(df, regra["colunas_possiveis_num"])
        col_den = encontrar_coluna_flexivel(df, regra["colunas_possiveis_den"])
        if not col_num or not col_den:
            return None, None, {"erro": "Colunas Geoloc não encontradas."}

        serie_num = df[col_num].astype(str).str.strip().str.upper()
        serie_den = df[col_den].astype(str).str.strip().str.upper()
        num_norm = [str(n).upper() for n in regra["numerador"]]
        den_norm = [str(d).upper() for d in regra["denominador"]]

        serie_score = pd.Series(np.nan, index=df.index, dtype=float)
        mask_den_valida = serie_den.isin(den_norm)
        mask_num_valida = serie_num.isin(num_norm)
        serie_score.loc[mask_den_valida & mask_num_valida] = 1.0
        serie_score.loc[mask_den_valida & ~mask_num_valida] = 0.0

        qtd_num = int((serie_score == 1.0).sum())
        qtd_den = int(serie_score.notna().sum())
        pct = (qtd_num / qtd_den * 100.0) if qtd_den > 0 else 0.0

        return (
            col_den,
            serie_score,
            {
                "coluna": col_den,
                "label": regra["label"],
                "nome_atingido": regra.get("nome_atingido", "Atingidos"),
                "nome_nao_atingido": regra.get("nome_nao_atingido", "Não Atingidos"),
                "numerador": qtd_num,
                "denominador": qtd_den,
                "pct": pct,
            },
        )

    elif tipo == "nao_vazio_total":
        col_avaliada = encontrar_coluna_flexivel(df, regra["colunas_possiveis"])
        if not col_avaliada:
            return None, None, {"erro": "Coluna não encontrada."}

        serie_raw = df[col_avaliada]
        serie_str = serie_raw.astype(str).str.strip().str.upper()
        valores_invalidos = ["", "NAN", "NAT", "NULL", "NONE", "-"]
        mask_vazio = serie_raw.isna() | serie_str.isin(valores_invalidos)

        serie_score = pd.Series(0.0, index=df.index, dtype=float)
        serie_score.loc[~mask_vazio] = 1.0

        qtd_num = int((serie_score == 1.0).sum())
        qtd_den = int(len(df))
        pct = (qtd_num / qtd_den * 100.0) if qtd_den > 0 else 0.0

        return (
            col_avaliada,
            serie_score,
            {
                "coluna": col_avaliada,
                "label": regra["label"],
                "nome_atingido": regra.get("nome_atingido", "Atingidos"),
                "nome_nao_atingido": regra.get("nome_nao_atingido", "Não Atingidos"),
                "numerador": qtd_num,
                "denominador": qtd_den,
                "pct": pct,
            },
        )

    else:
        col_avaliada = encontrar_coluna_flexivel(df, regra["colunas_possiveis"])
        if not col_avaliada:
            return None, None, {"erro": "Coluna não encontrada."}

        serie_norm = df[col_avaliada].astype(str).str.strip().str.upper()
        num_norm = [str(n).upper() for n in regra["numerador"]]

        serie_score = pd.Series(0.0, index=df.index, dtype=float)
        serie_score.loc[serie_norm.isin(num_norm)] = 1.0

        qtd_num = int((serie_score == 1.0).sum())
        qtd_den = int(len(df))
        pct = (qtd_num / qtd_den * 100.0) if qtd_den > 0 else 0.0

        return (
            col_avaliada,
            serie_score,
            {
                "coluna": col_avaliada,
                "label": regra["label"],
                "nome_atingido": regra.get("nome_atingido", "Atingidos"),
                "nome_nao_atingido": regra.get("nome_nao_atingido", "Não Atingidos"),
                "numerador": qtd_num,
                "denominador": qtd_den,
                "pct": pct,
            },
        )


# --- VISÃO EXECUTIVA GERAL (CONSOLIDADA COM FILTRO DE BASE) ---
def renderizar_visao_executiva_geral(resultados: Dict[str, Dict[str, Any]]) -> None:
    # 1. Coletar todas as bases únicas disponíveis nas planilhas
    todas_bases_set: set[str] = set()
    for aba_k, aba_info in resultados.items():
        df_tmp = aba_info.get("df")
        if df_tmp is not None and not df_tmp.empty and "Base" in df_tmp.columns:
            bases_aba = df_tmp["Base"].dropna().astype(str).unique().tolist()
            todas_bases_set.update(bases_aba)

    # 2. Renderizar Filtro por Base no topo da visão consolidada
    col_filtro_base, col_espaco = st.columns([1, 3])
    with col_filtro_base:
        bases_lista = ["Todas"] + sorted(list(todas_bases_set))
        sel_base_cons = st.selectbox(
            "🏢 Filtrar Visão Consolidada por Base:",
            bases_lista,
            key="exec_consolidada_base_filter",
        )

    dados_executivo: List[Dict[str, Any]] = []
    datas_maximas_encontradas: List[str] = []

    # 3. Processar Indicadores Filtrados
    for aba, info in resultados.items():
        df_info = info.get("df")
        if df_info is None or df_info.empty:
            continue

        # Aplicar filtro de base se selecionado
        if sel_base_cons != "Todas" and "Base" in df_info.columns:
            df_info = df_info[df_info["Base"].astype(str) == sel_base_cons]
            if df_info.empty:
                continue

        _, _, info_crit = calcular_aderencia_criterio(df_info, aba)
        dt_max_aba = extrair_data_maxima_aba(df_info, aba) or DATA_SISTEMA_STR
        datas_maximas_encontradas.append(dt_max_aba)

        if "pct" in info_crit:
            meta = METAS_POR_ABA.get(aba, 95.0)
            dados_executivo.append(
                {
                    "Indicador": f"{NOMES_ICONES.get(aba, '')} {NOMES_AMIGAVEIS.get(aba, aba)}",
                    "Realizado (%)": float(info_crit["pct"]),
                    "Meta (%)": float(meta),
                    "Desvio (%)": float(info_crit["pct"]) - float(meta),
                    "Atingidos": int(info_crit["numerador"]),
                    "Total": int(info_crit["denominador"]),
                    "Atualizado até": dt_max_aba,
                    "Status": (
                        "CONCLUIDO"
                        if float(info_crit["pct"]) >= float(meta)
                        else (
                            "PENDENTE"
                            if float(info_crit["pct"]) >= (float(meta) - 5.0)
                            else "CANCELADO"
                        )
                    ),
                }
            )

    # Adicionar o indicador O.S. Digital explicitamente, que roda sobre a base Geoloc_Os
    df_geoloc = resultados.get("Geoloc_Os", {}).get("df")
    if df_geoloc is not None and not df_geoloc.empty:
        if sel_base_cons != "Todas" and "Base" in df_geoloc.columns:
            df_geoloc_os = df_geoloc[df_geoloc["Base"].astype(str) == sel_base_cons]
        else:
            df_geoloc_os = df_geoloc

        if not df_geoloc_os.empty:
            _, _, info_crit_os = calcular_aderencia_criterio(df_geoloc_os, "OS_Digital")
            dt_max_os = (
                extrair_data_maxima_aba(df_geoloc_os, "OS_Digital") or DATA_SISTEMA_STR
            )
            datas_maximas_encontradas.append(dt_max_os)
            if "pct" in info_crit_os:
                meta_os = METAS_POR_ABA.get("OS_Digital", 95.0)
                dados_executivo.append(
                    {
                        "Indicador": f"{NOMES_ICONES.get('OS_Digital', '')} {NOMES_AMIGAVEIS.get('OS_Digital', 'OS_Digital')}",
                        "Realizado (%)": float(info_crit_os["pct"]),
                        "Meta (%)": float(meta_os),
                        "Desvio (%)": float(info_crit_os["pct"]) - float(meta_os),
                        "Atingidos": int(info_crit_os["numerador"]),
                        "Total": int(info_crit_os["denominador"]),
                        "Atualizado até": dt_max_os,
                        "Status": (
                            "CONCLUIDO"
                            if float(info_crit_os["pct"]) >= float(meta_os)
                            else (
                                "PENDENTE"
                                if float(info_crit_os["pct"]) >= (float(meta_os) - 5.0)
                                else "CANCELADO"
                            )
                        ),
                    }
                )

    dt_global = maior_texto_data(datas_maximas_encontradas, DATA_SISTEMA_STR)
    subtitulo_header = (
        f"Consolidação geral dos KPIs em tempo real • 🕒 Atualizado até: {dt_global}"
    )
    if sel_base_cons != "Todas":
        subtitulo_header += f" • 🏢 Base: {sel_base_cons}"

    render_section_header(
        titulo="Visão Executiva Consolidada", subtitulo=subtitulo_header, icone="🎯"
    )

    if not dados_executivo:
        render_empty_state(
            tipo="dados",
            descricao=f"Nenhum indicador disponível para a base '{sel_base_cons}'.",
        )
        return

    # Visualização em Blocos de KPIs com barra de progresso individual
    cols_kpi = st.columns(len(dados_executivo))
    for col, dado in zip(cols_kpi, dados_executivo):
        with col:
            is_meta = dado["Status"] == "CONCLUIDO"
            tema_kpi = (
                "verde"
                if is_meta
                else ("laranja" if dado["Status"] == "PENDENTE" else "vermelho")
            )
            trend_type = (
                "up"
                if is_meta
                else ("neutral" if dado["Status"] == "PENDENTE" else "down")
            )

            render_kpi(
                col=col,
                label=dado["Indicador"],
                valor=f"{dado['Realizado (%)']:.1f}%",
                sub=f"Meta: {dado['Meta (%)']}% | Até: {dado['Atualizado até']}",
                tema=tema_kpi,
                delta=f"{dado['Desvio (%)']:+.1f}%",
                delta_tipo=trend_type,
                colorida=True,
            )
            render_progress_bar(
                valor=dado["Realizado (%)"],
                maximo=100.0,
                mostrar_valor=False,
                tema=tema_kpi,
                altura="pequeno",
            )

    st.markdown("---")

    df_exec = pd.DataFrame(dados_executivo)
    color_rules_exec = gerar_regras_cores(
        df_exec,
        col_realizado="Realizado (%)",
        col_desvio="Desvio (%)",
        col_meta="Meta (%)",
    )

    render_table_html(
        df_exec,
        titulo="Tabela Consolidada de Indicadores",
        colunas=[
            "Indicador",
            "Realizado (%)",
            "Meta (%)",
            "Desvio (%)",
            "Atingidos",
            "Total",
            "Atualizado até",
            "Status",
        ],
        alinhamentos={
            "Indicador": "left",
            "Realizado (%)": "right",
            "Meta (%)": "right",
            "Desvio (%)": "right",
            "Atingidos": "right",
            "Total": "right",
            "Atualizado até": "center",
            "Status": "center",
        },
        fmt={
            "Realizado (%)": "{:.1f}%",
            "Meta (%)": "{:.1f}%",
            "Desvio (%)": "{:+.1f}%",
            "Atingidos": "{:,}",
            "Total": "{:,}",
        },
        color_rules=color_rules_exec,
        mostrar_data=False,
    )


# --- PAINEL EXECUTIVO PADRONIZADO PARA QUALQUER ABA ---
def renderizar_painel_executivo_aba(
    df_indicador: Optional[pd.DataFrame], nome_kpi: str
) -> None:
    nome_amigavel = NOMES_AMIGAVEIS.get(nome_kpi, nome_kpi)
    icone = NOMES_ICONES.get(nome_kpi, "📋")

    data_max_aba = extrair_data_maxima_aba(df_indicador, nome_kpi) or DATA_SISTEMA_STR
    complemento_data = ""
    if remover_acentos_e_padronizar(nome_kpi) == "tec1":
        complemento_data = " (data final da base)"

    render_section_header(
        titulo=f"Painel Executivo — {nome_amigavel}",
        subtitulo=(
            f"Análise de desempenho em {nome_amigavel} • "
            f"🕒 Atualizado até: {data_max_aba}{complemento_data}"
        ),
        icone=icone,
    )

    if df_indicador is None or df_indicador.empty:
        render_empty_state(
            tipo="dados",
            descricao=f"Dados indisponíveis para o indicador {nome_amigavel}.",
        )
        return

    meta_kpi = float(METAS_POR_ABA.get(nome_kpi, 95.0))
    col_crit, serie_score, info_crit = calcular_aderencia_criterio(
        df_indicador, nome_kpi
    )

    if "erro" in info_crit:
        st.error(f"❌ {info_crit['erro']}")
        return

    df = df_indicador.copy()
    if serie_score is not None:
        df["_SCORE"] = serie_score

    col_tec: Optional[str] = "Tecnico" if "Tecnico" in df.columns else None
    col_mon: Optional[str] = "Monitor" if "Monitor" in df.columns else None
    col_base: Optional[str] = "Base" if "Base" in df.columns else None

    # --- KPIs Principais ---
    st.markdown("### 🎯 Indicadores-Chave de Desempenho")

    pct = float(info_crit["pct"])
    total = int(info_crit["denominador"])
    atingidos = int(info_crit["numerador"])
    nao_atingidos = total - atingidos
    desvio = pct - meta_kpi

    label_atingido = info_crit.get("nome_atingido", "Atingidos")
    label_nao_atingido = info_crit.get("nome_nao_atingido", "Não Atingidos")

    k1, k2, k3, k4, k5 = st.columns(5)
    is_meta = pct >= meta_kpi
    tema_global = (
        "verde" if is_meta else ("laranja" if pct >= (meta_kpi - 5.0) else "vermelho")
    )
    trend_type = "up" if is_meta else ("neutral" if pct >= (meta_kpi - 5.0) else "down")

    render_kpi(
        k1,
        "Aderência Geral",
        f"{pct:.1f}%",
        sub=info_crit.get("label", nome_amigavel),
        delta=f"{desvio:+.1f}%",
        delta_tipo=trend_type,
        tema=tema_global,
        colorida=True,
    )
    render_metric_card(
        k2,
        label_atingido,
        f"{atingidos:,}",
        trend="none",
        sub="Registros conformes",
        colorida=False,
    )
    render_metric_card(
        k3,
        label_nao_atingido,
        f"{nao_atingidos:,}",
        trend="none",
        sub="Fora do padrão",
        colorida=False,
    )
    render_metric_card(
        k4,
        "Total Processado",
        f"{total:,}",
        trend="none",
        sub="Volume avaliado",
        colorida=False,
    )
    render_metric_card(
        k5,
        "Meta Estabelecida",
        f"{meta_kpi:.0f}%",
        trend="none",
        sub="Objetivo",
        colorida=False,
    )

    render_progress_bar(
        valor=pct,
        maximo=100.0,
        label=f"Progresso de Aderência vs Meta de {meta_kpi:.1f}% (Atualizado até {data_max_aba})",
        tema=tema_global,
    )

    st.markdown("---")

    # --- Filtros de Análise ---
    st.markdown("### 🔍 Filtros de Análise")
    fc1, fc2, fc3, fc4 = st.columns(4)

    df_view = df.copy()

    with fc1:
        if col_base:
            bases = ["Todas"] + sorted(
                df[col_base].dropna().astype(str).unique().tolist()
            )
            sel_base = st.selectbox("🏢 Base", bases, key=f"base_filter_{nome_kpi}")
            if sel_base != "Todas":
                df_view = df_view[df_view[col_base].astype(str) == sel_base]

    with fc2:
        if col_mon:
            mons = sorted(df_view[col_mon].dropna().astype(str).unique().tolist())
            sel_mon = st.multiselect(
                "👥 Monitor", mons, key=f"mon_filter_{nome_kpi}", placeholder="Todos"
            )
            if sel_mon:
                df_view = df_view[df_view[col_mon].astype(str).isin(sel_mon)]

    with fc3:
        if col_tec:
            tecs = sorted(df_view[col_tec].dropna().astype(str).unique().tolist())
            sel_tec = st.multiselect(
                "👷 Técnico", tecs, key=f"tec_filter_{nome_kpi}", placeholder="Todos"
            )
            if sel_tec:
                df_view = df_view[df_view[col_tec].astype(str).isin(sel_tec)]

    with fc4:
        sel_perf = st.selectbox(
            "🎨 Filtrar por Performance",
            ["Todos", "🟢 Meta Atingida", "🟡 Próximo à Meta", "🔴 Abaixo da Meta"],
            key=f"perf_filter_{nome_kpi}",
        )

    st.markdown("---")

    # --- Análise por Base ---
    if col_base and "_SCORE" in df_view.columns and not df_view.empty:
        grouped_base = df_view.groupby(col_base, dropna=False)
        df_base = pd.DataFrame(
            {
                "Total_OS": grouped_base["_SCORE"].count(),
                "Atingidos": grouped_base["_SCORE"].sum().astype(int),
                "Qtd_Tecnicos": (
                    grouped_base[col_tec].nunique()
                    if col_tec
                    else grouped_base["_SCORE"].count()
                ),
            }
        ).reset_index()

        df_base["Nao_Atingidos"] = df_base["Total_OS"] - df_base["Atingidos"]
        df_base["Realizado"] = (df_base["Atingidos"] / df_base["Total_OS"]) * 100.0
        df_base["Meta"] = meta_kpi
        df_base["Desvio"] = df_base["Realizado"] - df_base["Meta"]
        df_base["Status"] = df_base["Realizado"].apply(
            lambda v: (
                "CONCLUIDO"
                if v >= meta_kpi
                else ("PENDENTE" if v >= (meta_kpi - 5.0) else "CANCELADO")
            )
        )
        df_base = df_base.sort_values("Realizado", ascending=False)

        if sel_perf != "Todos":
            emoji = sel_perf.split(" ")[0]
            if emoji == "🟢":
                df_base_filtro = df_base[df_base["Status"] == "CONCLUIDO"]
            elif emoji == "🟡":
                df_base_filtro = df_base[df_base["Status"] == "PENDENTE"]
            else:
                df_base_filtro = df_base[df_base["Status"] == "CANCELADO"]
        else:
            df_base_filtro = df_base

        color_rules_base = gerar_regras_cores(
            df_base_filtro,
            col_realizado="Realizado",
            col_desvio="Desvio",
            meta_padrao=meta_kpi,
        )

        render_table_html(
            df_base_filtro,
            titulo="🏢 Desempenho Detalhado por Base",
            colunas=[
                col_base,
                "Total_OS",
                "Atingidos",
                "Nao_Atingidos",
                "Qtd_Tecnicos",
                "Realizado",
                "Desvio",
                "Status",
            ],
            alinhamentos={
                col_base: "left",
                "Total_OS": "right",
                "Atingidos": "right",
                "Nao_Atingidos": "right",
                "Qtd_Tecnicos": "right",
                "Realizado": "right",
                "Desvio": "right",
                "Status": "center",
            },
            fmt={
                "Total_OS": "{:,}",
                "Atingidos": "{:,}",
                "Nao_Atingidos": "{:,}",
                "Qtd_Tecnicos": "{:,}",
                "Realizado": "{:.1f}%",
                "Desvio": "{:+.1f}%",
            },
            color_rules=color_rules_base,
            height=350,
            mostrar_data=False,
        )

    st.markdown("---")

    # --- Análise por Técnico: uma tabela acima da outra ---
    if col_tec and "_SCORE" in df_view.columns and not df_view.empty:
        grouped_tec = df_view.groupby(col_tec, dropna=False)
        df_tec = pd.DataFrame(
            {
                "Total_OS": grouped_tec["_SCORE"].count(),
                "Atingidos": grouped_tec["_SCORE"].sum().astype(int),
            }
        ).reset_index()

        df_tec["Total_OS"] = df_tec["Total_OS"].astype(int)
        df_tec = df_tec[df_tec["Total_OS"] >= 1]

        if not df_tec.empty:
            df_tec["Realizado"] = (df_tec["Atingidos"] / df_tec["Total_OS"]) * 100.0
            df_tec["Meta"] = meta_kpi
            df_tec["Desvio"] = df_tec["Realizado"] - df_tec["Meta"]
            df_tec["Status"] = df_tec["Realizado"].apply(
                lambda v: (
                    "CONCLUIDO"
                    if v >= meta_kpi
                    else ("PENDENTE" if v >= (meta_kpi - 5.0) else "CANCELADO")
                )
            )

            st.markdown("#### 👷 Desempenho Geral por Técnico (Todos)")
            df_all_tec = df_tec.sort_values(
                ["Realizado", "Total_OS"], ascending=[False, False]
            )
            color_rules_all = gerar_regras_cores(
                df_all_tec,
                col_realizado="Realizado",
                col_desvio="Desvio",
                meta_padrao=meta_kpi,
            )
            render_table_html(
                df_all_tec,
                colunas=[
                    col_tec,
                    "Total_OS",
                    "Atingidos",
                    "Realizado",
                    "Desvio",
                    "Status",
                ],
                alinhamentos={
                    col_tec: "left",
                    "Total_OS": "right",
                    "Atingidos": "right",
                    "Realizado": "right",
                    "Desvio": "right",
                    "Status": "center",
                },
                fmt={
                    "Total_OS": "{:,}",
                    "Atingidos": "{:,}",
                    "Realizado": "{:.1f}%",
                    "Desvio": "{:+.1f}%",
                },
                color_rules=color_rules_all,
                height=850,
                mostrar_data=False,
            )

            st.markdown("#### ⚠️ Bottom 10 — Requer Atenção")
            df_bot = (
                df_tec[df_tec["Total_OS"] >= 3]
                .sort_values(["Realizado", "Total_OS"], ascending=[True, False])
                .head(10)
            )
            if df_bot.empty:
                df_bot = df_tec.sort_values(
                    ["Realizado", "Total_OS"], ascending=[True, False]
                ).head(10)

            color_rules_bot = gerar_regras_cores(
                df_bot,
                col_realizado="Realizado",
                col_desvio="Desvio",
                meta_padrao=meta_kpi,
            )
            render_table_html(
                df_bot,
                colunas=[
                    col_tec,
                    "Total_OS",
                    "Atingidos",
                    "Realizado",
                    "Desvio",
                    "Status",
                ],
                alinhamentos={
                    col_tec: "left",
                    "Total_OS": "right",
                    "Atingidos": "right",
                    "Realizado": "right",
                    "Desvio": "right",
                    "Status": "center",
                },
                fmt={
                    "Total_OS": "{:,}",
                    "Atingidos": "{:,}",
                    "Realizado": "{:.1f}%",
                    "Desvio": "{:+.1f}%",
                },
                color_rules=color_rules_bot,
                height=480,
                mostrar_data=False,
            )

    st.markdown("---")

    # --- Desempenho por Monitor ---
    if col_mon and "_SCORE" in df_view.columns and not df_view.empty:
        grouped_mon = df_view.groupby(col_mon, dropna=False)
        df_mon = pd.DataFrame(
            {
                "Total_OS": grouped_mon["_SCORE"].count(),
                "Atingidos": grouped_mon["_SCORE"].sum().astype(int),
                "Qtd_Tecnicos": (
                    grouped_mon[col_tec].nunique()
                    if col_tec
                    else grouped_mon["_SCORE"].count()
                ),
            }
        ).reset_index()

        df_mon["Realizado"] = (df_mon["Atingidos"] / df_mon["Total_OS"]) * 100.0
        df_mon["Meta"] = meta_kpi
        df_mon["Desvio"] = df_mon["Realizado"] - df_mon["Meta"]
        df_mon["Status"] = df_mon["Realizado"].apply(
            lambda v: (
                "CONCLUIDO"
                if v >= meta_kpi
                else ("PENDENTE" if v >= (meta_kpi - 5.0) else "CANCELADO")
            )
        )
        df_mon = df_mon.sort_values("Realizado", ascending=False)

        color_rules_mon = gerar_regras_cores(
            df_mon, col_realizado="Realizado", col_desvio="Desvio", meta_padrao=meta_kpi
        )

        render_table_html(
            df_mon,
            titulo="👥 Consolidado por Monitor",
            colunas=[
                col_mon,
                "Total_OS",
                "Atingidos",
                "Qtd_Tecnicos",
                "Realizado",
                "Desvio",
                "Status",
            ],
            alinhamentos={
                col_mon: "left",
                "Total_OS": "right",
                "Atingidos": "right",
                "Qtd_Tecnicos": "right",
                "Realizado": "right",
                "Desvio": "right",
                "Status": "center",
            },
            fmt={
                "Total_OS": "{:,}",
                "Atingidos": "{:,}",
                "Qtd_Tecnicos": "{:,}",
                "Realizado": "{:.1f}%",
                "Desvio": "{:+.1f}%",
            },
            color_rules=color_rules_mon,
            mostrar_data=False,
        )


# --- EXECUÇÃO PRINCIPAL E MONTAGEM DA SIDEBAR ---
with st.spinner("⏳ Processando e cruzando bases de dados..."):
    excel_sheets = load_excel_from_drive(DRIVE_FILE_ID)
    df_ativos = load_google_sheet(LISTA_ATIVOS_ID)

if not excel_sheets or df_ativos is None:
    render_empty_state(
        tipo="erro",
        titulo="Erro ao Carregar Arquivos",
        descricao="Verifique a conectividade e permissão das planilhas integradas no Google Drive.",
    )
    st.stop()

col_login_ativos = encontrar_coluna_flexivel(
    df_ativos, ["Login", "LOGIN", "Cd_Login", "LOGIN_TEC"]
)
col_tec_ativos = encontrar_coluna_flexivel(
    df_ativos, ["Tecnico", "Técnico", "TECNICO", "Nome_Tecnico"]
)
col_mon_ativos = encontrar_coluna_flexivel(
    df_ativos, ["Monitor", "MONITOR", "Nome_Monitor"]
)
col_base_ativos = encontrar_coluna_flexivel(
    df_ativos, ["Base", "BASE", "Filial", "Unidade"]
)

if not col_login_ativos:
    st.error("❌ Coluna 'Login' não encontrada em lista_ativos.")
    st.stop()

# Tipo de junção fixado internamente em 'left'
tipo_merge: MergeHowType = "left"

resultados = merge_todas_abas(
    excel_sheets=excel_sheets,
    df_ativos=df_ativos,
    col_login_ativos=col_login_ativos,
    col_tec_ativos=col_tec_ativos,
    col_mon_ativos=col_mon_ativos,
    col_base_ativos=col_base_ativos,
    how=tipo_merge,
)

# Descobrir a maior data de atualização entre todas as bases para exibir na Sidebar
todas_datas_maximas: List[str] = []
for res_k, res_v in resultados.items():
    if res_v.get("df") is not None:
        dt_m = extrair_data_maxima_aba(res_v["df"], res_k)
        if dt_m:
            todas_datas_maximas.append(dt_m)

data_max_global_str = maior_texto_data(todas_datas_maximas, DATA_SISTEMA_STR)

with st.sidebar:
    render_sidebar_brand(
        nome="TOTALE Analytics",
        subtitulo="Painel de Qualidade e Indicadores",
        versao="v4.7.1",
        icone="⚡",
    )

    render_sidebar_status(
        status="Sincronizado",
        label="Integração de Dados",
        ultima_atualizacao=data_max_global_str,
        tipo="ok",
    )

    render_sidebar_divider(estilo="gradiente", label="Legenda")
    st.markdown("🟢 **CONCLUIDO**: Meta atingida")
    st.markdown("🟡 **PENDENTE**: Margem crítica (até 5% abaixo)")
    st.markdown("🔴 **CANCELADO**: Fora do objetivo")

    render_sidebar_divider(estilo="linha", label="Metas")
    for aba_name_side, meta_val_side in METAS_POR_ABA.items():
        st.markdown(
            f"- **{NOMES_AMIGAVEIS.get(aba_name_side, aba_name_side)}**: {meta_val_side}%"
        )

    render_sidebar_footer_info(empresa="TOTALE Tecnologia", versao="4.7.1")

# Renderização das Abas de Exibição
abas_ok: List[str] = [
    aba for aba, info in resultados.items() if info.get("df") is not None
]
abas_erro: List[str] = [
    aba for aba, info in resultados.items() if info.get("df") is None
]

if abas_erro:
    for aba_err in abas_erro:
        render_insight(
            f"Aba operacional **{aba_err}**: {resultados[aba_err].get('erro', 'Erro desconhecido')}",
            tipo="alerta",
            titulo="Erro ao mesclar base",
        )

if not abas_ok:
    render_empty_state(
        tipo="erro",
        titulo="Processamento Inválido",
        descricao="Nenhuma das tabelas de indicadores pode ser mapeada com a lista de ativos.",
    )
    st.stop()

# Lista de abas operacionais organizadas
abas_exibicao: List[Tuple[str, str, Optional[pd.DataFrame]]] = []

# 1. Indicador Geolocalização
df_geoloc = resultados.get("Geoloc_Os", {}).get("df")
if df_geoloc is not None:
    abas_exibicao.append(("Geoloc_Os", "Geoloc_Os", df_geoloc))

# 2. Indicador O.S. Digital (Extraído de Geoloc_Os)
if df_geoloc is not None:
    abas_exibicao.append(("OS_Digital", "OS_Digital", df_geoloc))

# 3. Demais abas importadas da planilha Excel
for aba_planilha in abas_ok:
    if aba_planilha not in ["Geoloc_Os", "OS_Digital"]:
        abas_exibicao.append(
            (aba_planilha, aba_planilha, resultados[aba_planilha].get("df"))
        )

# Montagem dos nomes amigáveis para as Tabs
nomes_tabs: List[str] = ["🎯 Visão Consolidada"] + [
    f"{NOMES_ICONES.get(chave_kpi, '📋')} {NOMES_AMIGAVEIS.get(chave_kpi, chave_kpi)}"
    for chave_kpi, _, _ in abas_exibicao
]

tabs = st.tabs(nomes_tabs)

# Tab 0: Visão Executiva Geral
with tabs[0]:
    renderizar_visao_executiva_geral(resultados)

# Tabs Executivas Individuais para cada Indicador
for idx, (chave_kpi, aba_origem, df_kpi) in enumerate(abas_exibicao):
    with tabs[idx + 1]:
        renderizar_painel_executivo_aba(df_kpi, chave_kpi)
