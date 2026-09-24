import streamlit as st
import pandas as pd
import numpy as np
import requests
import unicodedata
from io import BytesIO, StringIO
from typing import Literal, Optional, Dict, List, Tuple, Any
from datetime import datetime

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

# Sugestões de dashboard aplicadas nesta versão:
# 1. Hierarquia: semáforo e insight no topo; tendência no meio; exceção e ranking embaixo.
# 2. Todo KPI com meta, volume e comparação dos últimos 7 dias — o delta colorido continua sendo o desvio da meta.
# 3. Filtros (período, base, monitor, técnico) aplicados antes do cálculo.
# 4. Matriz base × indicador para mostrar onde agir, não só o número consolidado.
# 5. Confiança do dado: data final da base (TEC1 = DAT_NOTA) e vínculo com a lista de ativos.
# 6. Exportação das exceções e atualização manual do cache.

MergeHowType = Literal["left", "right", "outer", "inner", "cross"]

VERSAO = "4.8.0"
DATA_SISTEMA_STR = datetime.now().strftime("%d/%m/%Y às %H:%M")
SEM_VINCULO = "(Sem vínculo)"
MARGEM_CRITICA = 5.0
MIN_OS_BOTTOM = 3

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

ORDEM_INDICADORES: List[str] = [
    "Geoloc_Os",
    "OS_Digital",
    "Aderencia_Ura",
    "Nr35",
    "Tec1",
    "Baixa_Pda",
]

NOMES_AMIGAVEIS: Dict[str, str] = {
    "Geoloc_Os": "Geolocalização",
    "OS_Digital": "O.S. Digital",
    "Aderencia_Ura": "Aderência URA",
    "Nr35": "NR35",
    "Tec1": "TEC1 - Status Nota",
    "Baixa_Pda": "Baixa PDA",
}

NOMES_CURTOS: Dict[str, str] = {
    "Geoloc_Os": "Geoloc",
    "OS_Digital": "O.S. Digital",
    "Aderencia_Ura": "URA",
    "Nr35": "NR35",
    "Tec1": "TEC1",
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

GLOSSARIO: Dict[str, str] = {
    "Geoloc_Os": "Com Padrão no menor status de geolocalização, sobre Com Padrão + Sem Padrão. Meta 95%.",
    "OS_Digital": "GEROU_OS = Sim, calculado na base de Geolocalização. Meta 95%.",
    "Aderencia_Ura": "OBJETIVO_URA = Sucesso. Meta 95%.",
    "Nr35": "Campo Subiu preenchido. Meta 95%.",
    "Tec1": "DSC_STATUS_NOTA = Com Padrão. Atualizado até a maior DAT_NOTA da base. Meta 97%.",
    "Baixa_Pda": "STATUS BAIXA = TOA. Meta 95%.",
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

MAPA_PERFORMANCE: Dict[str, Optional[str]] = {
    "Todos": None,
    "🟢 Meta Atingida": "CONCLUIDO",
    "🟡 Próximo à Meta": "PENDENTE",
    "🔴 Abaixo da Meta": "CANCELADO",
}

TipoInsightType = Literal["ok", "info", "alerta", "critico", "acao"]
TemaKPIType = Literal["azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"]
TipoProgressBarType = Literal["azul", "laranja", "verde", "vermelho", "roxo", "gradiente"]
TipoTrendType = Literal["up", "down", "neutral", "none"]

TEMAS_STATUS: Dict[str, TemaKPIType] = {
    "CONCLUIDO": "verde",
    "PENDENTE": "laranja",
    "CANCELADO": "vermelho",
}
TEMAS_BARRA: Dict[str, TipoProgressBarType] = {
    "CONCLUIDO": "verde",
    "PENDENTE": "laranja",
    "CANCELADO": "vermelho",
}
TREND_STATUS: Dict[str, TipoTrendType] = {
    "CONCLUIDO": "up",
    "PENDENTE": "neutral",
    "CANCELADO": "down",
}
COLUNAS_AUXILIARES = {"_SCORE", "_DATA", "_KEY", "_DIA", "Base_lbl"}


# --- FUNÇÕES UTILITÁRIAS ---
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


def classificar_status(pct: float, meta: float) -> str:
    if pct >= meta:
        return "CONCLUIDO"
    if pct >= (meta - MARGEM_CRITICA):
        return "PENDENTE"
    return "CANCELADO"


def tema_kpi_status(status: Any) -> TemaKPIType:
    encontrado = TEMAS_STATUS.get(str(status))
    if encontrado is None:
        return "vermelho"
    return encontrado


def tema_barra_status(status: Any) -> TipoProgressBarType:
    encontrado = TEMAS_BARRA.get(str(status))
    if encontrado is None:
        return "vermelho"
    return encontrado


def trend_de_status(status: Any) -> TipoTrendType:
    encontrado = TREND_STATUS.get(str(status))
    if encontrado is None:
        return "down"
    return encontrado


def nome_curto(chave: Any, fallback: Any = "") -> str:
    if isinstance(chave, str) and chave in NOMES_CURTOS:
        return NOMES_CURTOS[chave]
    if fallback is None:
        return "" if chave is None else str(chave)
    return str(fallback)


def rotulo_categoria(valor: Any) -> str:
    if pd.isna(valor):
        return SEM_VINCULO
    texto = str(valor).strip()
    if texto.upper() in {"", "NAN", "NONE", "NAT", "NULL", "-"}:
        return SEM_VINCULO
    return texto


def fmt_pct(valor: float, sinal: bool = False) -> str:
    numero = f"{valor:+.1f}" if sinal else f"{valor:.1f}"
    return numero.replace(".", ",") + "%"


def fmt_pp(valor: Optional[float]) -> str:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    return f"{valor:+.1f}".replace(".", ",") + " p.p."


def fmt_int(valor: Any) -> str:
    try:
        return f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def parse_data_texto(texto: Any) -> Optional[pd.Timestamp]:
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return None
    parsed = pd.to_datetime(
        str(texto).replace(" às ", " "), dayfirst=True, errors="coerce"
    )
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def atraso_em_dias(texto: str) -> Optional[int]:
    parsed = parse_data_texto(texto)
    if parsed is None:
        return None
    return int((pd.Timestamp.now().normalize() - parsed.normalize()).days)


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
        for k in ["created", "fechamento", "execucao", "abertura", "notificacao"]
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
    validas = [d for d in (parse_data_texto(t) for t in datas) if d is not None]
    if not validas:
        return fallback
    return _formatar_data_maxima(max(validas))


def menor_texto_data(datas: List[str], fallback: str) -> str:
    validas = [d for d in (parse_data_texto(t) for t in datas) if d is not None]
    if not validas:
        return fallback
    return _formatar_data_maxima(min(validas))


def resolver_coluna_data(df: pd.DataFrame, aba: Optional[str] = None) -> Optional[str]:
    if df is None or df.empty:
        return None
    if aba:
        for k_aba, candidatas in COLUNAS_DATA_POR_ABA.items():
            if remover_acentos_e_padronizar(k_aba) == remover_acentos_e_padronizar(aba):
                for cand in candidatas:
                    encontrada = encontrar_coluna_flexivel(df, [cand])
                    if encontrada:
                        return encontrada
                break
    for col in df.columns:
        if _coluna_e_data(str(col)):
            return str(col)
    return None


def anexar_data(df: pd.DataFrame, aba: Optional[str] = None) -> pd.DataFrame:
    out = df.copy()
    if "_DATA" in out.columns:
        return out
    col = resolver_coluna_data(out, aba)
    if col is None:
        out["_DATA"] = pd.NaT
        return out
    out["_DATA"] = _serie_para_datetime(out[col]).dt.normalize()
    return out


def extrair_data_maxima_aba(
    df: Optional[pd.DataFrame], aba: Optional[str] = None
) -> Optional[str]:
    """Maior data válida da base. No TEC1 a referência é DAT_NOTA, não o relógio."""
    if df is None or df.empty:
        return None

    col = resolver_coluna_data(df, aba)
    if col is None:
        return None

    limite_futuro = pd.Timestamp.now() + pd.Timedelta(days=2)
    limite_passado = pd.Timestamp("2000-01-01")
    try:
        s_dt = _serie_para_datetime(df[col]).dropna()
        s_dt = s_dt[(s_dt <= limite_futuro) & (s_dt >= limite_passado)]
        if s_dt.empty:
            return None
        return _formatar_data_maxima(pd.Timestamp(s_dt.max()))
    except Exception:
        return None


def limites_periodo(df: Optional[pd.DataFrame]) -> Tuple[Optional[datetime], Optional[datetime]]:
    if df is None or df.empty or "_DATA" not in df.columns:
        return None, None
    validas = df["_DATA"].dropna()
    if validas.empty:
        return None, None
    return validas.min().date(), validas.max().date()


def normalizar_periodo(valor: Any, padrao_ini: Any, padrao_fim: Any) -> Tuple[Any, Any]:
    if isinstance(valor, (tuple, list)):
        if len(valor) >= 2 and valor[0] is not None and valor[1] is not None:
            return valor[0], valor[1]
        if len(valor) == 1 and valor[0] is not None:
            return valor[0], valor[0]
        return padrao_ini, padrao_fim
    if valor is None:
        return padrao_ini, padrao_fim
    return valor, valor


def aplicar_periodo(df: pd.DataFrame, inicio: Any, fim: Any) -> pd.DataFrame:
    if df is None or df.empty or "_DATA" not in df.columns or inicio is None or fim is None:
        return df
    if int(df["_DATA"].notna().sum()) == 0:
        return df
    ini = pd.Timestamp(inicio)
    end = pd.Timestamp(fim)
    mascara = df["_DATA"].notna() & (df["_DATA"] >= ini) & (df["_DATA"] <= end)
    return df.loc[mascara].copy()


def aplicar_filtro_base(df: pd.DataFrame, selecionada: str) -> pd.DataFrame:
    if df is None or selecionada in (None, "Todas") or "Base" not in df.columns:
        return df
    rotulo = df["Base"].map(rotulo_categoria)
    return df.loc[rotulo == selecionada].copy()


def aplicar_filtro_lista(
    df: pd.DataFrame, coluna: Optional[str], selecionados: List[str]
) -> pd.DataFrame:
    if df is None or not selecionados or not coluna or coluna not in df.columns:
        return df
    rotulo = df[coluna].map(rotulo_categoria)
    return df.loc[rotulo.isin(selecionados)].copy()


def opcoes_categoria(serie: pd.Series) -> List[str]:
    rotulos = serie.map(rotulo_categoria)
    nomes = sorted({r for r in rotulos.unique().tolist() if r != SEM_VINCULO})
    if (rotulos == SEM_VINCULO).any():
        return [SEM_VINCULO] + nomes
    return nomes


def gerar_regras_cores(
    df_data: pd.DataFrame,
    col_realizado: Optional[str] = None,
    col_desvio: Optional[str] = None,
    col_meta: Optional[str] = None,
    meta_padrao: float = 95.0,
) -> Dict[str, Dict[str, str]]:
    """Mapeia valores numéricos para as cores do design system."""
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
                if pd.isna(val_real):
                    continue
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
                if pd.isna(val_desv):
                    continue
                d = float(val_desv)
                regras_desvio[str(val_desv)] = "sucesso" if d >= 0 else "alerta"
            except (ValueError, TypeError):
                pass
        color_rules[col_desvio] = regras_desvio

    return color_rules


def regras_texto_pp(valores: pd.Series) -> Dict[str, str]:
    regras: Dict[str, str] = {}
    for valor in valores.dropna().unique().tolist():
        texto = str(valor)
        if texto == "—":
            continue
        regras[texto] = "alerta" if texto.strip().startswith("-") else "sucesso"
    return regras


# --- CARREGAMENTO E CRUZAMENTO ---
@st.cache_data(ttl=3600)
def load_excel_from_drive(file_id: str) -> Optional[Dict[str, pd.DataFrame]]:
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        response = requests.get(url, timeout=60)
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
        response = requests.get(url, timeout=60)
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
    col_sit_ativos: Optional[str] = None,
    how: MergeHowType = "left",
) -> pd.DataFrame:
    cols_importar: List[str] = [
        c
        for c in [col_tec_ativos, col_mon_ativos, col_base_ativos, col_sit_ativos]
        if c is not None
    ]
    cols_right: List[str] = [col_login_ativos] + cols_importar

    left = df_sheet.copy()
    right = df_ativos[cols_right].drop_duplicates(subset=[col_login_ativos]).copy()

    left["_KEY"] = normalizar_chave(left[chave_excel])
    right["_KEY"] = normalizar_chave(right[col_login_ativos])
    right = right.drop(columns=[col_login_ativos])

    merged = pd.merge(left, right, on="_KEY", how=how, suffixes=("", "_ativos"))

    renomear: Dict[str, str] = {}
    if col_tec_ativos and col_tec_ativos in merged.columns and col_tec_ativos != "Tecnico":
        renomear[col_tec_ativos] = "Tecnico"
    if col_mon_ativos and col_mon_ativos in merged.columns and col_mon_ativos != "Monitor":
        renomear[col_mon_ativos] = "Monitor"
    if col_base_ativos and col_base_ativos in merged.columns and col_base_ativos != "Base":
        renomear[col_base_ativos] = "Base"
    if col_sit_ativos and col_sit_ativos in merged.columns and col_sit_ativos != "Situacao":
        renomear[col_sit_ativos] = "Situacao"
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
    col_sit_ativos: Optional[str] = None,
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
                col_sit_ativos,
                how,
            )
            resultados[aba] = {
                "df": anexar_data(df_merged, aba),
                "erro": None,
                "chave_excel": chave_excel,
            }
        except Exception as e:
            resultados[aba] = {"df": None, "erro": str(e), "chave_excel": chave_excel}
    return resultados


def dataframe_indicador(
    resultados: Dict[str, Dict[str, Any]], chave: str
) -> Optional[pd.DataFrame]:
    if chave == "OS_Digital":
        return resultados.get("Geoloc_Os", {}).get("df")
    return resultados.get(chave, {}).get("df")


def resumo_vinculo(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    if df is None or df.empty or "Tecnico" not in df.columns:
        return {"total": 0, "sem": 0, "pct": 0.0}
    rotulo = df["Tecnico"].map(rotulo_categoria)
    sem = int((rotulo == SEM_VINCULO).sum())
    total = int(len(df))
    pct = ((total - sem) / total * 100.0) if total else 0.0
    return {"total": total, "sem": sem, "pct": pct}


# --- MOTOR DE CÁLCULO ---
def _norm_regra(valores: List[Any]) -> set:
    return {remover_acentos_e_padronizar(v) for v in valores}


def _serie_norm_regra(serie: pd.Series) -> pd.Series:
    return serie.map(remover_acentos_e_padronizar)


def calcular_aderencia_criterio(
    df: pd.DataFrame, aba: str
) -> Tuple[Optional[str], Optional[pd.Series], Dict[str, Any]]:
    regra: Optional[Dict[str, Any]] = None
    for k_aba, v_regra in CRITERIOS_POR_ABA.items():
        if remover_acentos_e_padronizar(k_aba) == remover_acentos_e_padronizar(aba):
            regra = v_regra
            break
    if not regra or df is None or df.empty:
        return None, None, {"erro": "Sem regra ou sem dados para o recorte."}

    tipo = regra["tipo"]
    if tipo == "dual_column_ratio":
        col_num = encontrar_coluna_flexivel(df, regra["colunas_possiveis_num"])
        col_den = encontrar_coluna_flexivel(df, regra["colunas_possiveis_den"])
        if not col_num or not col_den:
            return None, None, {"erro": "Colunas Geoloc não encontradas."}

        serie_num = _serie_norm_regra(df[col_num])
        serie_den = _serie_norm_regra(df[col_den])
        num_norm = _norm_regra(regra["numerador"])
        den_norm = _norm_regra(regra["denominador"])

        serie_score = pd.Series(np.nan, index=df.index, dtype=float)
        mask_den = serie_den.isin(den_norm)
        mask_num = serie_num.isin(num_norm)
        serie_score.loc[mask_den & mask_num] = 1.0
        serie_score.loc[mask_den & ~mask_num] = 0.0
        coluna = col_den
    elif tipo == "nao_vazio_total":
        col_avaliada = encontrar_coluna_flexivel(df, regra["colunas_possiveis"])
        if not col_avaliada:
            return None, None, {"erro": "Coluna não encontrada."}
        serie_raw = df[col_avaliada]
        serie_str = serie_raw.astype(str).str.strip().str.upper()
        invalidos = ["", "NAN", "NAT", "NULL", "NONE", "-"]
        mask_vazio = serie_raw.isna() | serie_str.isin(invalidos)
        serie_score = pd.Series(0.0, index=df.index, dtype=float)
        serie_score.loc[~mask_vazio] = 1.0
        coluna = col_avaliada
    else:
        col_avaliada = encontrar_coluna_flexivel(df, regra["colunas_possiveis"])
        if not col_avaliada:
            return None, None, {"erro": "Coluna não encontrada."}
        serie_norm = _serie_norm_regra(df[col_avaliada])
        num_norm = _norm_regra(regra["numerador"])
        serie_score = pd.Series(0.0, index=df.index, dtype=float)
        serie_score.loc[serie_norm.isin(num_norm)] = 1.0
        coluna = col_avaliada

    qtd_num = int((serie_score == 1.0).sum())
    qtd_den = int(serie_score.notna().sum()) if tipo == "dual_column_ratio" else int(len(df))
    pct = (qtd_num / qtd_den * 100.0) if qtd_den > 0 else 0.0
    return (
        coluna,
        serie_score,
        {
            "coluna": coluna,
            "label": regra["label"],
            "nome_atingido": regra.get("nome_atingido", "Atingidos"),
            "nome_nao_atingido": regra.get("nome_nao_atingido", "Não Atingidos"),
            "numerador": qtd_num,
            "denominador": qtd_den,
            "pct": pct,
        },
    )


def com_score(df: pd.DataFrame, aba: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    work = df.copy()
    _, serie, info = calcular_aderencia_criterio(work, aba)
    if serie is not None:
        work["_SCORE"] = serie
    return work, info


def agregar_grupo(
    df: pd.DataFrame,
    col_grupo: str,
    meta: float,
    col_tec: Optional[str] = None,
    com_situacao: bool = False,
) -> pd.DataFrame:
    if df is None or df.empty or "_SCORE" not in df.columns or col_grupo not in df.columns:
        return pd.DataFrame()

    tmp = df.copy()
    tmp["_GRUPO"] = tmp[col_grupo].map(rotulo_categoria)
    grouped = tmp.groupby("_GRUPO", dropna=False)
    out = pd.DataFrame(
        {
            "Total_OS": grouped["_SCORE"].count(),
            "Atingidos": grouped["_SCORE"].sum(),
        }
    ).reset_index()
    if col_tec and col_tec in tmp.columns:
        qtd = grouped[col_tec].nunique().rename("Qtd_Tecnicos").reset_index()
        out = out.merge(qtd, on="_GRUPO", how="left")
    if com_situacao and "Situacao" in tmp.columns:
        sit = grouped["Situacao"].first().rename("Situacao").reset_index()
        out = out.merge(sit, on="_GRUPO", how="left")

    out = out.rename(columns={"_GRUPO": col_grupo})
    out["Atingidos"] = pd.to_numeric(out["Atingidos"], errors="coerce").fillna(0).astype(int)
    out["Total_OS"] = pd.to_numeric(out["Total_OS"], errors="coerce").fillna(0).astype(int)
    out = out[out["Total_OS"] > 0].copy()
    if out.empty:
        return out
    out["Nao_Atingidos"] = out["Total_OS"] - out["Atingidos"]
    out["Realizado"] = out["Atingidos"] / out["Total_OS"] * 100.0
    out["Meta"] = meta
    out["Desvio"] = out["Realizado"] - meta
    out["Status"] = out["Realizado"].apply(lambda v: classificar_status(float(v), meta))
    return out.sort_values(["Realizado", "Total_OS"], ascending=[False, False])


def serie_diaria(df: pd.DataFrame) -> pd.DataFrame:
    vazio = pd.DataFrame(columns=["Data", "Realizado", "Total", "Atingidos"])
    if df is None or df.empty or "_DATA" not in df.columns or "_SCORE" not in df.columns:
        return vazio
    valid = df[df["_DATA"].notna() & df["_SCORE"].notna()].copy()
    if valid.empty:
        return vazio
    valid["_DIA"] = valid["_DATA"].dt.normalize()
    out = (
        valid.groupby("_DIA", as_index=False)
        .agg(Atingidos=("_SCORE", "sum"), Total=("_SCORE", "count"))
        .rename(columns={"_DIA": "Data"})
    )
    out["Realizado"] = out["Atingidos"] / out["Total"] * 100.0
    return out.sort_values("Data")


def comparativo_7d(df: pd.DataFrame) -> Dict[str, Any]:
    vazio: Dict[str, Any] = {
        "pct": None,
        "pct_ant": None,
        "var": None,
        "n": 0,
        "n_ant": 0,
        "ini": None,
        "fim": None,
    }
    if df is None or df.empty or "_DATA" not in df.columns or "_SCORE" not in df.columns:
        return vazio
    datas = df["_DATA"].dropna()
    if datas.empty:
        return vazio
    fim = pd.Timestamp(datas.max()).normalize()
    ini = fim - pd.Timedelta(days=6)
    ant_fim = ini - pd.Timedelta(days=1)
    ant_ini = ant_fim - pd.Timedelta(days=6)

    def pack(inicio: pd.Timestamp, final: pd.Timestamp) -> Tuple[Optional[float], int]:
        sub = df[
            df["_DATA"].notna()
            & df["_SCORE"].notna()
            & (df["_DATA"] >= inicio)
            & (df["_DATA"] <= final)
        ]
        den = int(sub["_SCORE"].count())
        if den == 0:
            return None, 0
        return float(sub["_SCORE"].sum()) / den * 100.0, den

    pct, n = pack(ini, fim)
    pct_ant, n_ant = pack(ant_ini, ant_fim)
    var = (pct - pct_ant) if pct is not None and pct_ant is not None else None
    return {
        "pct": pct,
        "pct_ant": pct_ant,
        "var": var,
        "n": n,
        "n_ant": n_ant,
        "ini": ini,
        "fim": fim,
        "ant_ini": ant_ini,
        "ant_fim": ant_fim,
    }


def concentracao_nao_conformes(
    df: pd.DataFrame, col_tec: Optional[str], n: int = 10
) -> Dict[str, Any]:
    vazio = {"qtd": 0, "top": 0, "n": 0, "pct_top": 0.0, "nomes": []}
    if df is None or df.empty or not col_tec or col_tec not in df.columns or "_SCORE" not in df.columns:
        return vazio
    fora = df[df["_SCORE"] == 0]
    if fora.empty:
        return vazio
    por = fora.groupby(fora[col_tec].map(rotulo_categoria)).size().sort_values(ascending=False)
    por = por[por.index != SEM_VINCULO]
    if por.empty:
        return {"qtd": int(len(fora)), "top": 0, "n": 0, "pct_top": 0.0, "nomes": []}
    top = int(por.head(n).sum())
    total = int(por.sum())
    return {
        "qtd": int(len(fora)),
        "top": top,
        "n": int(min(n, len(por))),
        "pct_top": (top / total * 100.0) if total else 0.0,
        "nomes": [str(x) for x in por.head(3).index.tolist()],
    }


def filtrar_status(df: pd.DataFrame, selecao: str) -> pd.DataFrame:
    status = MAPA_PERFORMANCE.get(selecao)
    if not status or df is None or df.empty or "Status" not in df.columns:
        return df
    return df[df["Status"] == status].copy()


def escala_percentual(valores: List[float], metas: List[float]) -> Tuple[float, float]:
    numeros = [float(v) for v in valores if v is not None and not pd.isna(v)]
    metas_ok = [float(m) for m in metas if m is not None]
    if not numeros and not metas_ok:
        return 0.0, 100.0
    baixo = min(numeros + metas_ok) - 3.0
    alto = max(numeros + metas_ok + [100.0])
    return max(0.0, baixo), min(100.0, max(alto, baixo + 5.0))


# --- APRESENTAÇÃO ---
def render_barras_ranking(df: pd.DataFrame, col_nome: str, meta: float) -> None:
    """Barras na ordem do ranking, com a meta visível. Não depende da ordenação alfabética."""
    if df is None or df.empty or col_nome not in df.columns:
        return
    plot = df[[col_nome, "Realizado"]].copy()
    ordem = plot[col_nome].astype(str).tolist()
    plot[col_nome] = ordem
    y_min, y_max = escala_percentual(plot["Realizado"].tolist(), [meta])
    try:
        import altair as alt

        barras = (
            alt.Chart(plot)
            .mark_bar()
            .encode(
                x=alt.X(f"{col_nome}:N", sort=ordem, title=""),
                y=alt.Y(
                    "Realizado:Q",
                    title="Aderência (%)",
                    scale=alt.Scale(domain=[y_min, y_max]),
                ),
                color=alt.condition(
                    alt.datum.Realizado >= meta,
                    alt.value("#1E8E3E"),
                    alt.value("#C0392B"),
                ),
                tooltip=[
                    alt.Tooltip(f"{col_nome}:N", title="Técnico"),
                    alt.Tooltip("Realizado:Q", format=".1f", title="Realizado (%)"),
                ],
            )
        )
        regra = (
            alt.Chart(pd.DataFrame({"Meta": [meta]}))
            .mark_rule(strokeDash=[6, 4], color="#E67E22")
            .encode(y="Meta:Q")
        )
        st.altair_chart(
            (barras + regra)
            .properties(height=240)
            .configure(background="transparent")
            .configure_view(strokeWidth=0),
            use_container_width=True,
        )
    except Exception:
        st.bar_chart(plot.set_index(col_nome)[["Realizado"]], height=240)


def render_evolucao(df_daily: pd.DataFrame, meta: float, titulo: str) -> None:
    if df_daily is None or df_daily.empty or len(df_daily) < 2:
        st.caption("Período curto demais para mostrar tendência.")
        return
    st.markdown(f"#### {titulo}")
    st.caption(
        f"Linha de meta em {meta:.1f}%. A escala aproxima o desvio — não começa em zero para não esconder o gap."
    )
    plot = df_daily.copy()
    plot["Data"] = pd.to_datetime(plot["Data"])
    y_min, y_max = escala_percentual(plot["Realizado"].tolist(), [meta])
    try:
        import altair as alt

        linha = (
            alt.Chart(plot)
            .mark_line(point=True, color="#1F4E79")
            .encode(
                x=alt.X("Data:T", title="Data", axis=alt.Axis(format="%d/%m")),
                y=alt.Y(
                    "Realizado:Q",
                    title="Aderência (%)",
                    scale=alt.Scale(domain=[y_min, y_max]),
                ),
                tooltip=[
                    alt.Tooltip("Data:T", format="%d/%m/%Y", title="Data"),
                    alt.Tooltip("Realizado:Q", format=".1f", title="Realizado (%)"),
                    alt.Tooltip("Total:Q", format=",.0f", title="Volume"),
                ],
            )
        )
        regra = (
            alt.Chart(pd.DataFrame({"Meta": [meta]}))
            .mark_rule(strokeDash=[6, 4], color="#C0392B")
            .encode(y="Meta:Q")
        )
        st.altair_chart(
            (linha + regra)
            .properties(height=280)
            .configure(background="transparent")
            .configure_view(strokeWidth=0),
            use_container_width=True,
        )
    except Exception:
        st.line_chart(plot.set_index("Data")[["Realizado"]], height=280)


def render_evolucao_consolidada(long_df: pd.DataFrame, metas: List[float]) -> None:
    if long_df is None or long_df.empty or long_df["Data"].nunique() < 2:
        st.caption("Período curto demais para a tendência consolidada.")
        return
    st.markdown("#### 📈 Evolução diária dos indicadores")
    st.caption(
        "Referência visual em 95%. TEC1 tem meta de 97% — o valor da meta vai no detalhe de cada ponto. Escala aproximada para evidenciar desvio."
    )
    plot = long_df.copy()
    plot["Data"] = pd.to_datetime(plot["Data"])
    y_min, y_max = escala_percentual(plot["Realizado"].tolist(), metas or [95.0])
    try:
        import altair as alt

        linhas = (
            alt.Chart(plot)
            .mark_line(point=True)
            .encode(
                x=alt.X("Data:T", title="Data", axis=alt.Axis(format="%d/%m")),
                y=alt.Y(
                    "Realizado:Q",
                    title="Aderência (%)",
                    scale=alt.Scale(domain=[y_min, y_max]),
                ),
                color=alt.Color("Indicador:N", title=""),
                tooltip=[
                    alt.Tooltip("Data:T", format="%d/%m/%Y"),
                    alt.Tooltip("Indicador:N"),
                    alt.Tooltip("Realizado:Q", format=".1f", title="Realizado (%)"),
                    alt.Tooltip("Meta:Q", format=".0f", title="Meta (%)"),
                    alt.Tooltip("Total:Q", format=",.0f", title="Volume"),
                ],
            )
        )
        regra = (
            alt.Chart(pd.DataFrame({"Meta": [95.0]}))
            .mark_rule(strokeDash=[6, 4], color="#C0392B")
            .encode(y="Meta:Q")
        )
        st.altair_chart(
            (linhas + regra)
            .properties(height=320)
            .configure(background="transparent")
            .configure_view(strokeWidth=0)
            .configure_legend(orient="bottom"),
            use_container_width=True,
        )
    except Exception:
        pivot = plot.pivot_table(
            index="Data", columns="Indicador", values="Realizado", aggfunc="mean"
        )
        st.line_chart(pivot, height=320)


def render_ranking_tabela(
    df: pd.DataFrame,
    col_nome: str,
    meta: float,
    titulo: Optional[str] = None,
    height: Optional[int] = None,
    com_qtd_tec: bool = False,
    com_nao: bool = False,
    com_situacao: bool = False,
) -> None:
    if df is None or df.empty:
        st.caption("Nenhuma linha neste recorte.")
        return

    df = df.copy()
    if com_situacao and "Situacao" in df.columns:
        df["Situacao"] = df["Situacao"].map(rotulo_categoria)

    colunas = [col_nome]
    if com_situacao and "Situacao" in df.columns:
        colunas.append("Situacao")
    colunas.extend(["Total_OS", "Atingidos"])
    if com_nao and "Nao_Atingidos" in df.columns:
        colunas.append("Nao_Atingidos")
    if com_qtd_tec and "Qtd_Tecnicos" in df.columns:
        colunas.append("Qtd_Tecnicos")
    colunas.extend(["Realizado", "Desvio", "Status"])

    alinhamentos = {c: "right" for c in colunas}
    alinhamentos[col_nome] = "left"
    alinhamentos["Status"] = "center"
    if "Situacao" in alinhamentos:
        alinhamentos["Situacao"] = "left"

    fmt = {
        "Total_OS": "{:,}",
        "Atingidos": "{:,}",
        "Nao_Atingidos": "{:,}",
        "Qtd_Tecnicos": "{:,}",
        "Realizado": "{:.1f}%",
        "Desvio": "{:+.1f}%",
    }
    kwargs: Dict[str, Any] = {
        "colunas": colunas,
        "alinhamentos": alinhamentos,
        "fmt": fmt,
        "color_rules": gerar_regras_cores(
            df, col_realizado="Realizado", col_desvio="Desvio", meta_padrao=meta
        ),
        "mostrar_data": False,
    }
    if titulo:
        kwargs["titulo"] = titulo
    if height:
        kwargs["height"] = height
    render_table_html(df, **kwargs)


def publicar_insight(texto: str, titulo: str, tipo: TipoInsightType = "alerta") -> None:
    """Usa o tipo do design system e recua se a variante não existir."""
    try:
        render_insight(texto, tipo=tipo, titulo=titulo)
    except Exception:
        try:
            render_insight(texto, tipo="alerta", titulo=titulo)
        except Exception:
            st.info(f"**{titulo}** — {texto}")


def download_csv(df: pd.DataFrame, rotulo: str, nome_arquivo: str, key: str) -> None:
    if df is None or df.empty:
        st.caption(f"Sem linhas para {rotulo.lower()}.")
        return
    cols = [c for c in df.columns if c not in COLUNAS_AUXILIARES]
    csv = df[cols].to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        rotulo,
        data=csv,
        file_name=nome_arquivo,
        mime="text/csv",
        key=key,
    )


def texto_insight_executivo(
    dados: List[Dict[str, Any]], vinculo: Dict[str, Any]
) -> Tuple[str, TipoInsightType]:
    if not dados:
        return "Nenhum indicador disponível neste recorte.", "alerta"

    fora = [d for d in dados if d["Status"] != "CONCLUIDO"]
    tipo: TipoInsightType
    if not fora:
        texto = f"Os {len(dados)} indicadores estão na meta neste recorte."
        tipo = "ok"
    else:
        pior = min(fora, key=lambda d: d["Desvio (%)"])
        criticos = [d for d in fora if d["Status"] == "CANCELADO"]
        margem = [d for d in fora if d["Status"] == "PENDENTE"]
        partes: List[str] = []
        if criticos:
            nomes = ", ".join(
                nome_curto(d.get("_chave"), d.get("Indicador")) for d in criticos
            )
            partes.append(f"{len(criticos)} fora do objetivo ({nomes})")
        if margem:
            nomes = ", ".join(
                nome_curto(d.get("_chave"), d.get("Indicador")) for d in margem
            )
            partes.append(f"{len(margem)} na margem crítica, até 5 p.p. abaixo ({nomes})")
        texto = (
            f"{' e '.join(partes)}. "
            f"Maior gap: {pior['Indicador']} ({fmt_pp(pior['Desvio (%)'])})."
        )
        tipo = "critico" if criticos else "alerta"

    quedas = [d for d in dados if d.get("_var7") is not None and d["_var7"] <= -1.0]
    if quedas:
        queda = min(quedas, key=lambda d: d["_var7"])
        texto += (
            f" Queda recente mais forte: {queda['Indicador']} "
            f"({fmt_pp(queda['_var7'])} nos últimos 7 dias)."
        )
        tipo = "alerta"

    if vinculo.get("total", 0) and vinculo.get("pct", 100) < 98:
        texto += (
            f" Vínculo de logins em {fmt_pct(vinculo['pct'])}: "
            f"{fmt_int(vinculo['sem'])} registros sem técnico na lista de ativos."
        )
        tipo = "alerta"
    return texto, tipo


def texto_insight_indicador(
    nome: str,
    pct: float,
    meta: float,
    janela: Dict[str, Any],
    pior_base: Optional[pd.Series],
    concentracao: Dict[str, Any],
    vinculo: Dict[str, Any],
    volume: int,
) -> Tuple[str, TipoInsightType]:
    status = classificar_status(pct, meta)
    tipo: TipoInsightType
    if status == "CONCLUIDO":
        texto = f"{nome} está na meta ({fmt_pct(pct)} contra {fmt_pct(meta)})."
        tipo = "ok"
    elif status == "PENDENTE":
        texto = (
            f"{nome} está na margem crítica: {fmt_pct(pct)} contra a meta de {fmt_pct(meta)} "
            f"({fmt_pp(pct - meta)})."
        )
        tipo = "alerta"
    else:
        texto = (
            f"{nome} está fora do objetivo: {fmt_pct(pct)} contra a meta de {fmt_pct(meta)} "
            f"({fmt_pp(pct - meta)})."
        )
        tipo = "critico"

    if janela.get("var") is not None and janela.get("ini") is not None:
        texto += (
            f" Últimos 7 dias ({janela['ini'].strftime('%d/%m')} a {janela['fim'].strftime('%d/%m')}): "
            f"{fmt_pct(janela['pct'])}, contra {fmt_pct(janela['pct_ant'])} nos 7 dias anteriores "
            f"({fmt_pp(janela['var'])})."
        )
        if janela["var"] <= -1:
            tipo = "alerta"

    if pior_base is not None:
        texto += (
            f" Pior base com volume: {pior_base.get('Base', '—')} "
            f"({fmt_pct(float(pior_base['Realizado']))}, {fmt_int(pior_base['Total_OS'])} O.S.)."
        )
    if concentracao.get("qtd", 0) > 0 and concentracao.get("nomes"):
        nomes = ", ".join(concentracao["nomes"])
        texto += (
            f" {fmt_int(concentracao['qtd'])} registros fora do padrão; "
            f"{concentracao['n']} técnicos concentram {fmt_pct(concentracao['pct_top'])}. "
            f"Primeiros nomes: {nomes}."
        )
    if vinculo.get("sem", 0) > 0:
        texto += f" {fmt_int(vinculo['sem'])} registros sem vínculo de técnico."
        tipo = "alerta"
    if 0 < volume < 30:
        texto += " Volume baixo no recorte — leia o percentual com cautela."
        tipo = "alerta"
    return texto, tipo


# --- VISÃO EXECUTIVA ---
def renderizar_visao_executiva_geral(resultados: Dict[str, Dict[str, Any]]) -> None:
    frames = []
    for chave in ORDEM_INDICADORES:
        df_chave = dataframe_indicador(resultados, chave)
        if df_chave is not None and not df_chave.empty:
            frames.append(df_chave if "_DATA" in df_chave.columns else anexar_data(df_chave, chave))

    bases: set[str] = set()
    for df_tmp in frames:
        if "Base" in df_tmp.columns:
            bases.update(df_tmp["Base"].map(rotulo_categoria).unique().tolist())
    dmin, dmax = None, None
    for df_tmp in frames:
        ini, fim = limites_periodo(df_tmp)
        if ini and (dmin is None or ini < dmin):
            dmin = ini
        if fim and (dmax is None or fim > dmax):
            dmax = fim

    datas_fonte = []
    for chave in ORDEM_INDICADORES:
        df_chave = dataframe_indicador(resultados, chave)
        dt = extrair_data_maxima_aba(df_chave, chave)
        if dt:
            datas_fonte.append(dt)
    data_final = maior_texto_data(datas_fonte, DATA_SISTEMA_STR)
    atraso = atraso_em_dias(data_final)

    render_section_header(
        titulo="Visão Executiva Consolidada",
        subtitulo=(
            f"Seis indicadores, uma leitura: o que está fora da meta, onde e se a fonte está em dia. "
            f"🕒 Data final da base: {data_final}"
        ),
        icone="🎯",
    )
    st.caption("O detalhe operacional — técnico, monitor e exceção — fica na aba de cada indicador.")

    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        bases_lista = ["Todas"] + sorted(b for b in bases if b != SEM_VINCULO)
        if SEM_VINCULO in bases:
            bases_lista.append(SEM_VINCULO)
        sel_base = st.selectbox(
            "🏢 Base",
            bases_lista,
            key="exec_consolidada_base_filter",
        )
    ini_sel, fim_sel = dmin, dmax
    if dmin and dmax:
        with c2:
            periodo = st.date_input(
                "📅 Período",
                value=(dmin, dmax),
                min_value=dmin,
                max_value=dmax,
                key="exec_periodo",
            )
        ini_sel, fim_sel = normalizar_periodo(periodo, dmin, dmax)
        with c3:
            st.caption("Os percentuais respeitam o período.")
            st.caption("“Atualizado até” é a data final da base, não o fim do filtro.")

    dados: List[Dict[str, Any]] = []
    serie_longa: List[pd.DataFrame] = []
    matriz_partes: List[pd.DataFrame] = []
    volume_partes: List[pd.DataFrame] = []

    for chave in ORDEM_INDICADORES:
        df_fonte = dataframe_indicador(resultados, chave)
        if df_fonte is None or df_fonte.empty:
            continue
        df_base = aplicar_filtro_base(df_fonte, sel_base)
        if df_base.empty:
            continue
        dt_fonte = extrair_data_maxima_aba(df_base, chave) or data_final
        df_calc = aplicar_periodo(df_base, ini_sel, fim_sel)
        if df_calc.empty:
            continue
        work, info = com_score(df_calc, chave)
        if "pct" not in info or int(info.get("denominador", 0)) == 0:
            continue

        meta = float(METAS_POR_ABA.get(chave, 95.0))
        janela = comparativo_7d(work)
        status = classificar_status(float(info["pct"]), meta)
        dados.append(
            {
                "_chave": chave,
                "_var7": janela.get("var"),
                "Indicador": f"{NOMES_ICONES.get(chave, '')} {NOMES_AMIGAVEIS.get(chave, chave)}",
                "Realizado (%)": float(info["pct"]),
                "Meta (%)": meta,
                "Desvio (%)": float(info["pct"]) - meta,
                "7 dias (%)": janela.get("pct"),
                "Var. 7d": fmt_pp(janela.get("var")),
                "Atingidos": int(info["numerador"]),
                "Total": int(info["denominador"]),
                "Atualizado até": dt_fonte,
                "Status": status,
            }
        )

        diaria = serie_diaria(work)
        if not diaria.empty:
            diaria = diaria.copy()
            diaria["Indicador"] = NOMES_CURTOS.get(chave, chave)
            diaria["Meta"] = meta
            serie_longa.append(diaria)

        if "Base" in work.columns:
            por_base = agregar_grupo(work, "Base", meta, col_tec="Tecnico" if "Tecnico" in work.columns else None)
            if not por_base.empty:
                parte = por_base[["Base", "Realizado", "Total_OS"]].copy()
                parte["Indicador"] = NOMES_CURTOS.get(chave, chave)
                parte["Meta"] = meta
                matriz_partes.append(parte)
                volume_partes.append(parte[["Base", "Indicador", "Total_OS"]])

    if ini_sel and fim_sel:
        st.caption(
            f"Recorte ativo: base {sel_base} • período {pd.Timestamp(ini_sel).strftime('%d/%m/%Y')} a {pd.Timestamp(fim_sel).strftime('%d/%m/%Y')}."
        )

    if not dados:
        render_empty_state(
            tipo="dados",
            descricao=f"Nenhum indicador disponível para a base '{sel_base}' neste período.",
        )
        return

    # Vínculo uma vez por planilha física — O.S. Digital reutiliza Geoloc e não entra de novo.
    vinculo_total = 0
    vinculo_sem = 0
    for aba_fisica, info_fisica in resultados.items():
        df_fisica = info_fisica.get("df")
        if df_fisica is None or df_fisica.empty:
            continue
        df_fisica = aplicar_periodo(aplicar_filtro_base(df_fisica, sel_base), ini_sel, fim_sel)
        vinc_fisica = resumo_vinculo(df_fisica)
        vinculo_total += vinc_fisica["total"]
        vinculo_sem += vinc_fisica["sem"]
    vinculo = {
        "total": vinculo_total,
        "sem": vinculo_sem,
        "pct": ((vinculo_total - vinculo_sem) / vinculo_total * 100.0) if vinculo_total else 0.0,
    }

    texto, tipo_insight = texto_insight_executivo(dados, vinculo)
    if atraso is not None and atraso >= 2:
        texto += f" Fonte desatualizada: a data final da base é {data_final} ({atraso} dias atrás)."
        tipo_insight = "alerta"
    publicar_insight(texto, titulo="Leitura executiva", tipo=tipo_insight)

    na_meta = sum(1 for d in dados if d["Status"] == "CONCLUIDO")
    pior = min(dados, key=lambda d: d["Desvio (%)"])
    tema_meta: TemaKPIType = (
        "verde" if na_meta == len(dados) else ("laranja" if na_meta >= len(dados) - 1 else "vermelho")
    )
    trend_meta: TipoTrendType = "up" if na_meta == len(dados) else "down"
    s1, s2, s3 = st.columns(3)
    render_kpi(
        s1,
        "Indicadores na meta",
        f"{na_meta} de {len(dados)}",
        sub="Contrato de qualidade do recorte",
        tema=tema_meta,
        delta=f"{na_meta - len(dados):+d}" if na_meta < len(dados) else "OK",
        delta_tipo=trend_meta,
        colorida=True,
    )
    render_kpi(
        s2,
        "Maior gap",
        fmt_pp(pior["Desvio (%)"]),
        sub=str(pior["Indicador"]),
        tema=tema_kpi_status(pior["Status"]),
        delta=f"{pior['Realizado (%)']:.1f}%",
        delta_tipo=trend_de_status(pior["Status"]),
        colorida=True,
    )
    tema_fonte: TemaKPIType = (
        "verde"
        if atraso is not None and atraso <= 1
        else ("laranja" if atraso == 2 else "vermelho")
    )
    trend_fonte: TipoTrendType = "up" if atraso is not None and atraso <= 1 else "down"
    render_kpi(
        s3,
        "Data final da base",
        data_final,
        sub="Há 0 dias" if atraso == 0 else (f"Há {atraso} dias" if atraso is not None else "Fonte"),
        tema=tema_fonte,
        delta="em dia" if atraso is not None and atraso <= 1 else "atrasada",
        delta_tipo=trend_fonte,
        colorida=True,
    )
    st.caption(
        "O delta colorido de cada indicador abaixo é o desvio contra a meta. "
        "“7d” é a variação dos últimos 7 dias do recorte contra os 7 dias anteriores."
    )

    for inicio in range(0, len(dados), 3):
        grupo = dados[inicio : inicio + 3]
        cols = st.columns(3)
        for col, dado in zip(cols, grupo):
            with col:
                sub = (
                    f"Meta: {dado['Meta (%)']:.0f}% | "
                    f"{fmt_int(dado['Atingidos'])}/{fmt_int(dado['Total'])} | "
                    f"7d: {fmt_pp(dado['_var7'])}"
                )
                render_kpi(
                    col,
                    str(dado["Indicador"]),
                    f"{dado['Realizado (%)']:.1f}%",
                    sub=sub,
                    tema=tema_kpi_status(dado["Status"]),
                    delta=f"{dado['Desvio (%)']:+.1f}%",
                    delta_tipo=trend_de_status(dado["Status"]),
                    colorida=True,
                )
                render_progress_bar(
                    valor=dado["Realizado (%)"],
                    maximo=100.0,
                    mostrar_valor=False,
                    tema=tema_barra_status(dado["Status"]),
                    altura="pequeno",
                )

    st.markdown("---")
    if serie_longa:
        render_evolucao_consolidada(
            pd.concat(serie_longa, ignore_index=True),
            [float(d["Meta (%)"]) for d in dados],
        )
        st.markdown("---")

    if matriz_partes:
        bruto = pd.concat(matriz_partes, ignore_index=True)
        pct = bruto.pivot_table(index="Base", columns="Indicador", values="Realizado", aggfunc="mean")
        ordem_cols = [NOMES_CURTOS[k] for k in ORDEM_INDICADORES if NOMES_CURTOS[k] in pct.columns]
        pct = pct.reindex(columns=ordem_cols)
        metas_col = {NOMES_CURTOS[k]: METAS_POR_ABA[k] for k in ORDEM_INDICADORES}
        gap = pct.copy()
        for col in gap.columns:
            gap[col] = gap[col] - metas_col.get(col, 95.0)
        pct = pct.loc[gap.mean(axis=1).sort_values(ascending=True).index]

        color_rules: Dict[str, Dict[str, str]] = {}
        display = pd.DataFrame({"Base": pct.index.astype(str)})
        for col in pct.columns:
            meta_col = metas_col.get(col, 95.0)
            textos: List[str] = []
            regras: Dict[str, str] = {}
            for val in pct[col].tolist():
                if pd.isna(val):
                    textos.append("—")
                    continue
                texto = f"{float(val):.1f}%"
                textos.append(texto)
                regras[texto] = "sucesso" if float(val) >= meta_col else "alerta"
            display[col] = textos
            color_rules[col] = regras
        render_table_html(
            display,
            titulo="🏢 Onde agir — aderência por base",
            colunas=["Base"] + ordem_cols,
            alinhamentos={c: ("left" if c == "Base" else "right") for c in ["Base"] + ordem_cols},
            color_rules=color_rules,
            height=360,
            mostrar_data=False,
        )
        st.caption("Bases ordenadas pelo pior desvio médio. Percentual do período selecionado.")

        if volume_partes:
            with st.expander("Ver volume por base (denominador)"):
                vol = pd.concat(volume_partes, ignore_index=True)
                vol_p = vol.pivot_table(index="Base", columns="Indicador", values="Total_OS", aggfunc="sum")
                vol_p = vol_p.reindex(columns=ordem_cols).fillna(0).astype(int).reset_index()
                render_table_html(
                    vol_p,
                    colunas=["Base"] + ordem_cols,
                    alinhamentos={c: ("left" if c == "Base" else "right") for c in ["Base"] + ordem_cols},
                    fmt={c: "{:,}" for c in ordem_cols},
                    mostrar_data=False,
                )

    st.markdown("---")
    df_exec = pd.DataFrame(dados)
    df_exec["7 dias"] = df_exec["7 dias (%)"].apply(
        lambda v: "—" if v is None or pd.isna(v) else f"{float(v):.1f}%"
    )
    color_rules_exec = gerar_regras_cores(
        df_exec,
        col_realizado="Realizado (%)",
        col_desvio="Desvio (%)",
        col_meta="Meta (%)",
    )
    color_rules_exec["Var. 7d"] = regras_texto_pp(df_exec["Var. 7d"])
    regras_7d: Dict[str, str] = {}
    for _, row in df_exec.iterrows():
        texto_7d = str(row["7 dias"])
        if texto_7d == "—":
            continue
        try:
            regras_7d[texto_7d] = (
                "sucesso" if float(row["7 dias (%)"]) >= float(row["Meta (%)"]) else "alerta"
            )
        except (TypeError, ValueError):
            continue
    color_rules_exec["7 dias"] = regras_7d
    render_table_html(
        df_exec,
        titulo="Tabela consolidada de indicadores",
        colunas=[
            "Indicador",
            "Realizado (%)",
            "Meta (%)",
            "Desvio (%)",
            "7 dias",
            "Var. 7d",
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
            "7 dias": "right",
            "Var. 7d": "right",
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


# --- PAINEL DO INDICADOR ---
def renderizar_painel_executivo_aba(
    df_indicador: Optional[pd.DataFrame], nome_kpi: str
) -> None:
    nome_amigavel = NOMES_AMIGAVEIS.get(nome_kpi, nome_kpi)
    icone = NOMES_ICONES.get(nome_kpi, "📋")
    meta_kpi = float(METAS_POR_ABA.get(nome_kpi, 95.0))
    data_final = extrair_data_maxima_aba(df_indicador, nome_kpi) or DATA_SISTEMA_STR
    complemento = " (data final da base)" if remover_acentos_e_padronizar(nome_kpi) == "tec1" else ""

    render_section_header(
        titulo=f"Painel Executivo — {nome_amigavel}",
        subtitulo=(
            f"{GLOSSARIO.get(nome_kpi, nome_amigavel)} • "
            f"🕒 Atualizado até: {data_final}{complemento}"
        ),
        icone=icone,
    )

    if df_indicador is None or df_indicador.empty:
        render_empty_state(
            tipo="dados",
            descricao=f"Dados indisponíveis para o indicador {nome_amigavel}.",
        )
        return

    base_df = df_indicador if "_DATA" in df_indicador.columns else anexar_data(df_indicador, nome_kpi)
    dmin, dmax = limites_periodo(base_df)

    st.markdown("### 🔍 Recorte")
    ini_sel, fim_sel = dmin, dmax
    if dmin and dmax:
        periodo = st.date_input(
            "📅 Período",
            value=(dmin, dmax),
            min_value=dmin,
            max_value=dmax,
            key=f"periodo_{nome_kpi}",
        )
        ini_sel, fim_sel = normalizar_periodo(periodo, dmin, dmax)
    df_periodo = aplicar_periodo(base_df, ini_sel, fim_sel)

    fc1, fc2, fc3 = st.columns(3)
    df_view = df_periodo
    with fc1:
        if "Base" in df_periodo.columns:
            bases = ["Todas"] + opcoes_categoria(df_periodo["Base"])
            sel_base = st.selectbox("🏢 Base", bases, key=f"base_filter_{nome_kpi}")
            df_view = aplicar_filtro_base(df_view, sel_base)
    with fc2:
        if "Monitor" in df_view.columns:
            mons = opcoes_categoria(df_view["Monitor"])
            sel_mon = st.multiselect(
                "👥 Monitor", mons, key=f"mon_filter_{nome_kpi}", placeholder="Todos"
            )
            df_view = aplicar_filtro_lista(df_view, "Monitor", sel_mon)
    with fc3:
        if "Tecnico" in df_view.columns:
            tecs = opcoes_categoria(df_view["Tecnico"])
            sel_tec = st.multiselect(
                "👷 Técnico", tecs, key=f"tec_filter_{nome_kpi}", placeholder="Todos"
            )
            df_view = aplicar_filtro_lista(df_view, "Tecnico", sel_tec)

    if df_view.empty:
        render_empty_state(
            tipo="dados",
            descricao="Nenhum registro no recorte. Amplie o período ou limpe os filtros.",
        )
        return

    work, info = com_score(df_view, nome_kpi)
    if "erro" in info or "pct" not in info:
        st.error(f"❌ {info.get('erro', 'Não foi possível calcular o indicador.')}")
        return
    if int(info.get("denominador", 0)) == 0:
        render_empty_state(
            tipo="dados",
            descricao="O recorte não tem registros avaliáveis para este indicador.",
        )
        return

    pct = float(info["pct"])
    total = int(info["denominador"])
    atingidos = int(info["numerador"])
    nao_atingidos = total - atingidos
    desvio = pct - meta_kpi
    status = classificar_status(pct, meta_kpi)
    janela = comparativo_7d(work)
    vinculo = resumo_vinculo(work)
    col_tec = "Tecnico" if "Tecnico" in work.columns else None
    col_mon = "Monitor" if "Monitor" in work.columns else None
    col_base = "Base" if "Base" in work.columns else None

    if ini_sel and fim_sel:
        st.caption(
            f"Recorte: {pd.Timestamp(ini_sel).strftime('%d/%m/%Y')} a {pd.Timestamp(fim_sel).strftime('%d/%m/%Y')} • "
            f"{fmt_int(total)} registros avaliados. A data do cabeçalho continua sendo a data final da base."
        )

    st.markdown("### 🎯 Resultado do recorte")
    k1, k2, k3, k4, k5 = st.columns(5)
    render_kpi(
        k1,
        "Aderência",
        f"{pct:.1f}%",
        sub=f"{info.get('label', nome_amigavel)} | 7d: {fmt_pp(janela.get('var'))}",
        delta=f"{desvio:+.1f}%",
        delta_tipo=trend_de_status(status),
        tema=tema_kpi_status(status),
        colorida=True,
    )
    render_metric_card(
        k2,
        info.get("nome_atingido", "Atingidos"),
        f"{atingidos:,}",
        trend="none",
        sub="Registros conformes",
        colorida=False,
    )
    render_metric_card(
        k3,
        info.get("nome_nao_atingido", "Não Atingidos"),
        f"{nao_atingidos:,}",
        trend="none",
        sub="Fora do padrão",
        colorida=False,
    )
    render_metric_card(
        k4,
        "Volume avaliado",
        f"{total:,}",
        trend="none",
        sub="Denominador do recorte",
        colorida=False,
    )
    render_metric_card(
        k5,
        "Meta",
        f"{meta_kpi:.0f}%",
        trend="none",
        sub="Objetivo do indicador",
        colorida=False,
    )
    render_progress_bar(
        valor=pct,
        maximo=100.0,
        label=f"Aderência do recorte contra a meta de {meta_kpi:.1f}%",
        tema=tema_barra_status(status),
    )

    df_base_agg = agregar_grupo(work, col_base, meta_kpi, col_tec) if col_base else pd.DataFrame()
    pior_base = None
    if not df_base_agg.empty:
        com_volume = df_base_agg[df_base_agg["Total_OS"] >= 10]
        fonte = com_volume if not com_volume.empty else df_base_agg
        pior_base = fonte.sort_values(["Realizado", "Total_OS"], ascending=[True, False]).iloc[0]
    concentracao = concentracao_nao_conformes(work, col_tec)
    texto, tipo_insight = texto_insight_indicador(
        nome_amigavel, pct, meta_kpi, janela, pior_base, concentracao, vinculo, total
    )
    publicar_insight(texto, titulo="O que fazer com este número", tipo=tipo_insight)

    st.markdown("---")
    render_evolucao(serie_diaria(work), meta_kpi, "📈 Evolução diária vs meta")
    st.markdown("---")

    sel_perf = st.selectbox(
        "🎨 Destacar performance nas tabelas",
        list(MAPA_PERFORMANCE.keys()),
        key=f"perf_filter_{nome_kpi}",
    )

    if col_base and not df_base_agg.empty:
        render_ranking_tabela(
            filtrar_status(df_base_agg, sel_perf),
            col_nome=col_base,
            meta=meta_kpi,
            titulo="🏢 Desempenho por base",
            height=350,
            com_qtd_tec=True,
            com_nao=True,
        )
        st.markdown("---")

    if col_tec and "_SCORE" in work.columns:
        df_tec = agregar_grupo(work, col_tec, meta_kpi, com_situacao=True)
        df_tec = filtrar_status(df_tec, sel_perf)
        if df_tec.empty:
            st.caption("Nenhum técnico no recorte para a performance selecionada.")
        else:
            st.markdown("#### 👷 Desempenho Geral por Técnico (Todos)")
            render_ranking_tabela(
                df_tec.sort_values(["Realizado", "Total_OS"], ascending=[False, False]),
                col_nome=col_tec,
                meta=meta_kpi,
                height=850,
                com_situacao=True,
            )

            st.markdown("#### ⚠️ Bottom 10 — Requer Atenção")
            st.caption(f"Técnicos com pelo menos {MIN_OS_BOTTOM} O.S. no recorte, do pior resultado para o melhor.")
            df_bot = (
                df_tec[df_tec["Total_OS"] >= MIN_OS_BOTTOM]
                .sort_values(["Realizado", "Total_OS"], ascending=[True, False])
                .head(10)
            )
            if df_bot.empty:
                df_bot = df_tec.sort_values(
                    ["Realizado", "Total_OS"], ascending=[True, False]
                ).head(10)
            render_barras_ranking(df_bot, col_tec, meta_kpi)
            render_ranking_tabela(
                df_bot,
                col_nome=col_tec,
                meta=meta_kpi,
                height=480,
                com_situacao=True,
            )

            especiais = pd.DataFrame()
            if "Situacao" in df_bot.columns:
                especiais = df_bot[
                    ~df_bot["Situacao"]
                    .map(rotulo_categoria)
                    .str.upper()
                    .isin(["ATIVO", SEM_VINCULO.upper()])
                ]
            if not especiais.empty:
                nomes_esp = ", ".join(
                    f"{r[col_tec]} ({r['Situacao']})" for _, r in especiais.iterrows()
                )
                render_insight(
                    f"No Bottom 10 há técnico fora de ATIVO: {nomes_esp}.",
                    tipo="alerta",
                    titulo="Situação cadastral",
                )

            with st.expander("🏆 Top 10 — referência"):
                df_top = df_tec.sort_values(
                    ["Realizado", "Total_OS"], ascending=[False, False]
                ).head(10)
                render_ranking_tabela(
                    df_top,
                    col_nome=col_tec,
                    meta=meta_kpi,
                    com_situacao=True,
                )
        st.markdown("---")
    elif col_tec is None:
        publicar_insight(
            "Ranking por técnico indisponível: o login desta base não foi vinculado à lista de ativos.",
            titulo="Sem vínculo",
            tipo="alerta",
        )

    if col_mon and "_SCORE" in work.columns:
        df_mon = filtrar_status(
            agregar_grupo(work, col_mon, meta_kpi, col_tec=col_tec), sel_perf
        )
        render_ranking_tabela(
            df_mon,
            col_nome=col_mon,
            meta=meta_kpi,
            titulo="👥 Consolidado por monitor",
            com_qtd_tec=True,
        )

    with st.expander("Exportar recorte"):
        e1, e2, e3 = st.columns(3)
        with e1:
            download_csv(
                work[work["_SCORE"] == 0] if "_SCORE" in work.columns else work.iloc[0:0],
                "⬇️ Fora do padrão",
                f"{nome_kpi}_fora_do_padrao.csv",
                key=f"dl_fora_{nome_kpi}",
            )
        with e2:
            if col_tec:
                download_csv(
                    agregar_grupo(work, col_tec, meta_kpi, com_situacao=True),
                    "⬇️ Ranking de técnicos",
                    f"{nome_kpi}_tecnicos.csv",
                    key=f"dl_tec_{nome_kpi}",
                )
        with e3:
            download_csv(
                work,
                "⬇️ Base filtrada",
                f"{nome_kpi}_recorte.csv",
                key=f"dl_base_{nome_kpi}",
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
col_sit_ativos = encontrar_coluna_flexivel(
    df_ativos, ["Situação", "Situacao", "SITUACAO", "Status_Tecnico"]
)

if not col_login_ativos:
    st.error("❌ Coluna 'Login' não encontrada em lista_ativos.")
    st.stop()

resultados = merge_todas_abas(
    excel_sheets=excel_sheets,
    df_ativos=df_ativos,
    col_login_ativos=col_login_ativos,
    col_tec_ativos=col_tec_ativos,
    col_mon_ativos=col_mon_ativos,
    col_base_ativos=col_base_ativos,
    col_sit_ativos=col_sit_ativos,
    how="left",
)

datas_fonte: List[str] = []
datas_inicio: List[str] = []
vinculo_total = 0
vinculo_sem = 0
for res_k, res_v in resultados.items():
    df_res = res_v.get("df")
    if df_res is None:
        continue
    dt_m = extrair_data_maxima_aba(df_res, res_k)
    if dt_m:
        datas_fonte.append(dt_m)
    if "_DATA" in df_res.columns and df_res["_DATA"].notna().any():
        datas_inicio.append(pd.Timestamp(df_res["_DATA"].min()).strftime("%d/%m/%Y"))
    vinc = resumo_vinculo(df_res)
    vinculo_total += vinc["total"]
    vinculo_sem += vinc["sem"]

data_max_global_str = maior_texto_data(datas_fonte, DATA_SISTEMA_STR)
data_min_global_str = menor_texto_data(datas_inicio, "—")
pct_vinculo = ((vinculo_total - vinculo_sem) / vinculo_total * 100.0) if vinculo_total else 0.0
atraso_global = atraso_em_dias(data_max_global_str)

with st.sidebar:
    render_sidebar_brand(
        nome="TOTALE Analytics",
        subtitulo="Painel de Qualidade e Indicadores",
        versao=f"v{VERSAO}",
        icone="⚡",
    )
    render_sidebar_status(
        status="Sincronizado",
        label="Integração de Dados",
        ultima_atualizacao=data_max_global_str,
        tipo="ok",
    )
    st.caption(f"Cobertura da fonte: {data_min_global_str} a {data_max_global_str}")
    if atraso_global is not None and atraso_global >= 2:
        st.caption(f"Fonte {atraso_global} dias atrás da data de hoje.")
    st.caption(
        f"Vínculo de logins: {pct_vinculo:.1f}% ({fmt_int(vinculo_total - vinculo_sem)} de {fmt_int(vinculo_total)})"
    )
    if st.button("🔄 Atualizar bases", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    render_sidebar_divider(estilo="gradiente", label="Legenda")
    st.markdown("🟢 **CONCLUIDO**: Meta atingida")
    st.markdown("🟡 **PENDENTE**: Margem crítica (até 5% abaixo)")
    st.markdown("🔴 **CANCELADO**: Fora do objetivo")
    st.caption("O delta colorido mede desvio da meta, não a variação de 7 dias.")

    render_sidebar_divider(estilo="linha", label="Metas")
    for aba_name_side in ORDEM_INDICADORES:
        meta_val_side = METAS_POR_ABA[aba_name_side]
        st.markdown(
            f"- **{NOMES_AMIGAVEIS.get(aba_name_side, aba_name_side)}**: {meta_val_side}%"
        )

    with st.expander("Como cada indicador é calculado"):
        for aba_name_side in ORDEM_INDICADORES:
            st.markdown(f"**{NOMES_AMIGAVEIS[aba_name_side]}**")
            st.caption(GLOSSARIO[aba_name_side])

    render_sidebar_footer_info(empresa="TOTALE Tecnologia", versao=VERSAO)

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

abas_exibicao: List[Tuple[str, Optional[pd.DataFrame]]] = []
for chave in ORDEM_INDICADORES:
    df_chave = dataframe_indicador(resultados, chave)
    if df_chave is not None:
        abas_exibicao.append((chave, df_chave))

if not abas_exibicao:
    render_empty_state(
        tipo="erro",
        titulo="Processamento Inválido",
        descricao="Nenhuma das tabelas de indicadores pode ser mapeada com a lista de ativos.",
    )
    st.stop()

nomes_tabs: List[str] = ["🎯 Visão Consolidada"] + [
    f"{NOMES_ICONES.get(chave, '📋')} {NOMES_AMIGAVEIS.get(chave, chave)}"
    for chave, _ in abas_exibicao
]
tabs = st.tabs(nomes_tabs)

with tabs[0]:
    renderizar_visao_executiva_geral(resultados)

for idx, (chave_kpi, df_kpi) in enumerate(abas_exibicao):
    with tabs[idx + 1]:
        renderizar_painel_executivo_aba(df_kpi, chave_kpi)