import time
from datetime import datetime
from io import BytesIO, StringIO
from typing import Dict, Optional, Tuple, Union
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_hero_totale_1,
    render_insight,
    render_kpi,
    render_section_header,
    render_sidebar_brand,
    render_table_html,
)

# ====================================================
# CONFIGURAÇÃO DA PÁGINA
# ====================================================
try:
    st.set_page_config(
        page_title="Atualização de Dados | TOTALE",
        page_icon="🔁",
        layout="wide",
    )
except Exception:
    pass

aplicar_estilo()


class Configuracoes:
    """Central de configurações e URLs das fontes de dados."""

    URL_PROD = "https://docs.google.com/spreadsheets/d/11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v/export?format=xlsx"
    URL_CONS = "https://drive.google.com/uc?id=1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs&export=download"
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/export?format=csv"

    VAZIOS = {"-", "nan", "None", "", "NaN", "nat", "NAT", "<NA>", "null", "NULL"}
    FUSO = ZoneInfo("America/Sao_Paulo")
    TIMEOUT = 30
    # Se souber o nome exato da aba de Produção, coloque aqui (ex: ["Prod"]) para acelerar
    ABAS_PROD: Optional[list] = None


class ProcessadorDeDados:
    """Classe responsável pelo ETL e aplicação de regras de negócio nas bases."""

    @staticmethod
    def _normalizar(serie: pd.Series) -> pd.Series:
        """Limpa e padroniza séries de texto."""
        return (
            serie.fillna("")
            .astype(str)
            .str.strip()
            .replace(list(Configuracoes.VAZIOS), "")
        )

    @staticmethod
    def tratar_planos(df: pd.DataFrame) -> pd.DataFrame:
        """Trata e separa os planos de TV e Internet."""
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df

        df = df.copy()
        internet_bruta = df["PLANO INTERNET"].astype(str).str.strip()
        partes = internet_bruta.str.split(".", n=1, expand=True)

        internet_limpa = ProcessadorDeDados._normalizar(partes[0])
        tv_embutida = (
            ProcessadorDeDados._normalizar(partes[1])
            if partes.shape[1] > 1
            else pd.Series("", index=df.index, dtype=str)
        )

        tv_original = ProcessadorDeDados._normalizar(df["PLANO TV"]).replace(
            "SERVIÇOS AVANÇADOS", "CLARO TV+ BOX"
        )

        tv_final = pd.Series(
            np.where(tv_original != "", tv_original, tv_embutida),
            index=df.index,
            dtype=str,
        )

        tem_tv = tv_final != ""
        tem_net = internet_limpa != ""

        df["QTDE_CONSULTIVO"] = tem_tv.astype(int) + tem_net.astype(int)

        condicoes = [tem_tv & tem_net, tem_tv & ~tem_net, ~tem_tv & tem_net]
        opcoes = [tv_final + " & " + internet_limpa, tv_final, internet_limpa]

        df["TIPO SERVIÇO"] = np.select(condicoes, opcoes, default="Sem Tipo")
        df["PLANO TV"] = tv_final
        df["PLANO INTERNET"] = internet_limpa
        return df

    @staticmethod
    def _processar_quantidades(cons: pd.DataFrame) -> pd.DataFrame:
        """Calcula a quantidade de equipamentos e serviços por linha."""
        cons = cons.copy()

        if "OBSERVACAO" in cons.columns:
            cons["LISTA_PRODUTOS"] = (
                cons["OBSERVACAO"].fillna("").astype(str).str.findall(r"\b\d{9,12}\b")
            )
            cons["QTDE_PRODUTOS"] = cons["LISTA_PRODUTOS"].str.len()
        else:
            cons["LISTA_PRODUTOS"] = [[] for _ in range(len(cons))]
            cons["QTDE_PRODUTOS"] = 0

        tipo_servico = (
            cons.get("TIPO SERVIÇO", pd.Series("", index=cons.index))
            .fillna("")
            .astype(str)
        )
        qtde_prod = cons["QTDE_PRODUTOS"].fillna(0).astype(int)

        is_combinado = tipo_servico.str.contains("&", case=False, regex=False)
        tem_tv = tipo_servico.str.contains("TV", case=False, regex=False)
        tem_virtua = tipo_servico.str.contains(r"MEGA|GIGA", case=False, regex=True)

        cons["QTDE_TV"] = np.where(
            is_combinado, tem_tv.astype(int), tem_tv.astype(int) * qtde_prod
        )
        cons["QTDE_VIRTUA"] = np.where(
            is_combinado, tem_virtua.astype(int), tem_virtua.astype(int) * qtde_prod
        )
        cons["QTDE_MESH"] = (qtde_prod - cons["QTDE_TV"] - cons["QTDE_VIRTUA"]).clip(
            lower=0
        )
        return cons

    @staticmethod
    def _merge_ativos(cons: pd.DataFrame, ativos: pd.DataFrame) -> pd.DataFrame:
        """Cruza os dados consultivos com a base de ativos usando o Login."""
        if (
            ativos.empty
            or "Login" not in ativos.columns
            or "LOGIN NETSALES" not in cons.columns
        ):
            return cons

        cols = [c for c in ["Login", "Monitor", "U.N.", "Base"] if c in ativos.columns]
        ativos_limpo = (
            ativos[cols]
            .dropna(subset=["Login"])
            .drop_duplicates(subset=["Login"])
            .copy()
        )
        ativos_limpo["Login_JOIN"] = (
            ativos_limpo["Login"].astype(str).str.strip().str.upper()
        )

        cons = cons.copy()
        cons["Login_JOIN"] = cons["LOGIN NETSALES"].astype(str).str.strip().str.upper()

        cons = pd.merge(
            cons,
            ativos_limpo.drop(columns=["Login"]),
            on="Login_JOIN",
            how="left",
        ).drop(columns=["Login_JOIN"])

        if "Monitor" in cons.columns:
            cons["Monitor"] = cons["Monitor"].fillna("Não Identificado")
        return cons

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)
    def sincronizar() -> (
        Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame], pd.DataFrame]
    ):
        """Faz o download e processamento de todas as bases remotas."""
        # 1) Produção
        try:
            prod_result = pd.read_excel(
                Configuracoes.URL_PROD,
                sheet_name=Configuracoes.ABAS_PROD,
                engine="openpyxl",
            )
            if isinstance(prod_result, pd.DataFrame):
                prod_raw: Dict[str, pd.DataFrame] = {"Prod": prod_result}
            else:
                prod_raw = {
                    str(nome): dataframe
                    for nome, dataframe in prod_result.items()
                    if isinstance(dataframe, pd.DataFrame)
                }
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar Produção Excel: {e}") from e

        # 2) Consultivo
        try:
            resp = requests.get(Configuracoes.URL_CONS, timeout=Configuracoes.TIMEOUT)
            resp.raise_for_status()

            if "text/html" in resp.headers.get("Content-Type", "").lower():
                raise RuntimeError(
                    "Download do Google Drive bloqueado ou link inválido."
                )

            try:
                cons = pd.read_csv(StringIO(resp.text), sep=",", dtype=str)
            except Exception:
                cons = pd.read_csv(
                    BytesIO(resp.content),
                    sep=";",
                    encoding="utf-8",
                    engine="python",
                    dtype=str,
                )
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar Consultivo CSV: {e}") from e

        # 3) Ativos
        try:
            ativos = pd.read_csv(Configuracoes.URL_ATIVOS, dtype=str)
            ativos.columns = ativos.columns.str.strip()
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar Lista de Ativos: {e}") from e

        if cons is None or cons.empty:
            return prod_raw, {"Consultivo": pd.DataFrame()}, ativos

        cons.columns = cons.columns.str.strip()
        cons = ProcessadorDeDados.tratar_planos(cons)
        cons = ProcessadorDeDados._processar_quantidades(cons)
        cons = ProcessadorDeDados._merge_ativos(cons, ativos)

        return prod_raw, {"Consultivo": cons}, ativos


def _obter_dataframe(chave_state: str, nome_aba: Optional[str] = None) -> pd.DataFrame:
    """Helper seguro para extrair DataFrames do st.session_state."""
    dados = st.session_state.get(chave_state, {})
    if isinstance(dados, dict) and dados:
        if nome_aba and nome_aba in dados:
            res = dados[nome_aba]
        else:
            res = next(iter(dados.values()))
        return res if isinstance(res, pd.DataFrame) else pd.DataFrame()
    elif isinstance(dados, pd.DataFrame):
        return dados
    return pd.DataFrame()


# ====================================================
# INTERFACE
# ====================================================

# Exibe mensagens Flash salvas pós-rerun
if "flash_msg" in st.session_state:
    msg, icon = st.session_state.pop("flash_msg")
    st.toast(msg, icon=icon)

with st.sidebar:
    render_sidebar_brand("TOTALE", "Data Management")
    st.markdown("---")
    render_insight(
        "Use **Sincronizar Agora** para atualizar as bases de Produção, Consultivos e Ativos.",
        "info",
    )

render_hero_totale_1(
    titulo="Central de Atualização",
    subtitulo="Sincronização de bases de Produção, Consultivos e Lista de Ativos",
)

ultima = st.session_state.get("ultima_atualizacao")
col_status, col_btn = st.columns([3, 1], vertical_alignment="center")

with col_status:
    if ultima:
        render_insight(
            f"Última sincronização realizada em: **{ultima.strftime('%d/%m/%Y às %H:%M:%S')}**",
            "ok",
        )
    else:
        render_insight("Os dados ainda não foram carregados nesta sessão.", "alerta")

with col_btn:
    sincronizar = st.button(
        "🔄 Sincronizar Agora",
        use_container_width=True,
        type="primary",
        key="btn_sincronizar_dados",
    )

if sincronizar:
    try:
        with st.status("🔄 Baixando e processando dados...", expanded=True) as status:
            st.write("Conectando aos servidores do Google Drive...")
            ProcessadorDeDados.sincronizar.clear()
            p, c, a = ProcessadorDeDados.sincronizar()

            st.write("Aplicando regras de negócio e relacionamentos...")
            st.session_state["dados_prod"] = p
            st.session_state["dados_cons"] = c
            st.session_state["dados_ativos"] = a
            st.session_state["ultima_atualizacao"] = datetime.now(Configuracoes.FUSO)

            status.update(
                label="Bases sincronizadas com sucesso!",
                state="complete",
                expanded=False,
            )

        st.session_state["flash_msg"] = ("Bases atualizadas com sucesso!", "✅")
        time.sleep(0.5)
        st.rerun()

    except Exception as e:
        st.error(f"❌ Falha na sincronização: {e}")
        with st.expander("🔍 Detalhes do Erro"):
            st.exception(e)

st.divider()

# ---------- Extração dos DataFrames ----------
df_prod = _obter_dataframe("dados_prod", "Prod")
df_cons = _obter_dataframe("dados_cons", "Consultivo")

tem_dados = not df_prod.empty or not df_cons.empty

if tem_dados:
    total_equip = (
        int(df_cons["QTDE_PRODUTOS"].fillna(0).sum())
        if "QTDE_PRODUTOS" in df_cons.columns
        else 0
    )
    media_servicos = (
        float(df_cons["QTDE_CONSULTIVO"].fillna(0).mean())
        if "QTDE_CONSULTIVO" in df_cons.columns
        else 0.0
    )

    k1, k2, k3, k4 = st.columns(4)
    render_kpi(
        k1,
        "Registros Produção",
        f"{len(df_prod):,}".replace(",", "."),
        "Base Produção",
        "azul",
    )
    render_kpi(
        k2,
        "Base Consultiva",
        f"{len(df_cons):,}".replace(",", "."),
        "Processados",
        "laranja",
    )
    render_kpi(
        k3,
        "Total Equipamentos",
        f"{total_equip:,}".replace(",", "."),
        "Detectados em OBS",
        "verde",
    )
    render_kpi(
        k4,
        "Serviços / Venda",
        f"{media_servicos:.2f}",
        "Média de penetração",
        "cinza",
    )

    tab_p, tab_c = st.tabs(["📊 Produção (Preview)", "📋 Consultivo Processado"])

    with tab_p:
        render_section_header("📊", "Base de Produção", "Primeiros 50 registros")
        if not df_prod.empty:
            render_table_html(df_prod, max_rows=50, max_cols=15, height=360)
        else:
            render_insight("Aba de Produção vazia ou não encontrada.", "alerta")

    with tab_c:
        render_section_header("📋", "Base Consultiva Detalhada", "Processado")
        if not df_cons.empty:
            render_table_html(df_cons, max_rows=50, max_cols=15, height=360)
        else:
            render_insight("Base consultiva vazia.", "alerta")
else:
    render_insight(
        "Clique em **Sincronizar Agora** para carregar e visualizar as bases de dados.",
        "acao",
    )