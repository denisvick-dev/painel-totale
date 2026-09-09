import time
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

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
    ABAS_PROD: list | None = None


class ProcessadorDeDados:
    """Classe responsável pelo ETL e aplicação de regras de negócio nas bases."""

    @staticmethod
    def _normalizar(serie: pd.Series) -> pd.Series:
        """Limpa e padroniza séries de texto."""
        if serie is None or not isinstance(serie, pd.Series):
            return pd.Series(dtype=str)
        return (
            serie.fillna("")
            .astype(str)
            .str.strip()
            .replace(list(Configuracoes.VAZIOS), "")
        )

    @staticmethod
    def _ler_csv_remoto(url: str) -> pd.DataFrame:
        """Faz download e lê CSV remoto testando separadores e encodings comuns."""
        resp = requests.get(url, timeout=Configuracoes.TIMEOUT)
        resp.raise_for_status()

        if "text/html" in resp.headers.get("Content-Type", "").lower():
            raise RuntimeError(
                "Download bloqueado pelo Google Drive ou link inválido (retornou página HTML)."
            )

        conteudo = resp.content
        for enc in ["utf-8", "latin1", "cp1252"]:
            for sep in [",", ";", "\t"]:
                try:
                    df = pd.read_csv(
                        BytesIO(conteudo), sep=sep, encoding=enc, dtype=str
                    )
                    if df.shape[1] > 1:
                        df.columns = df.columns.str.strip()
                        return df
                except Exception:
                    continue

        df = pd.read_csv(BytesIO(conteudo), sep=None, engine="python", dtype=str)
        df.columns = df.columns.str.strip()
        return df

    @staticmethod
    def tratar_planos(df: pd.DataFrame) -> pd.DataFrame:
        """Trata e separa os planos de TV e Internet sem depender de np.select/np.where."""
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df

        df = df.copy()
        internet_bruta = df["PLANO INTERNET"].fillna("").astype(str).str.strip()
        partes = internet_bruta.str.split(".", n=1, expand=True)

        internet_limpa = ProcessadorDeDados._normalizar(partes[0])
        if partes.shape[1] > 1:
            tv_embutida = ProcessadorDeDados._normalizar(partes[1])
        else:
            tv_embutida = pd.Series("", index=df.index, dtype=str)

        tv_original = ProcessadorDeDados._normalizar(df["PLANO TV"]).replace(
            "SERVIÇOS AVANÇADOS", "CLARO TV+ BOX"
        )

        tv_final = tv_original.mask(tv_original.eq(""), tv_embutida)

        tem_tv = tv_final.ne("")
        tem_net = internet_limpa.ne("")

        df["QTDE_CONSULTIVO"] = tem_tv.astype(int) + tem_net.astype(int)

        tipo_servico = pd.Series("Sem Tipo", index=df.index, dtype=str)
        mask_ambos = tem_tv & tem_net
        mask_tv = tem_tv & (~tem_net)
        mask_net = (~tem_tv) & tem_net

        tipo_servico.loc[mask_ambos] = (
            tv_final.loc[mask_ambos] + " & " + internet_limpa.loc[mask_ambos]
        )
        tipo_servico.loc[mask_tv] = tv_final.loc[mask_tv]
        tipo_servico.loc[mask_net] = internet_limpa.loc[mask_net]

        df["TIPO SERVIÇO"] = tipo_servico
        df["PLANO TV"] = tv_final
        df["PLANO INTERNET"] = internet_limpa
        return df

    @staticmethod
    def _processar_quantidades(cons: pd.DataFrame) -> pd.DataFrame:
        """Calcula a quantidade de equipamentos e serviços por linha de forma vetorizada."""
        cons = cons.copy()

        if "OBSERVACAO" in cons.columns:
            cons["LISTA_PRODUTOS"] = (
                cons["OBSERVACAO"].fillna("").astype(str).str.findall(r"\b\d{9,12}\b")
            )
            cons["QTDE_PRODUTOS"] = (
                cons["LISTA_PRODUTOS"].str.len().fillna(0).astype(int)
            )
        else:
            cons["LISTA_PRODUTOS"] = [[] for _ in range(len(cons))]
            cons["QTDE_PRODUTOS"] = 0

        tipo_servico = (
            cons.get("TIPO SERVIÇO", pd.Series("", index=cons.index))
            .fillna("")
            .astype(str)
        )
        qtde_prod = cons["QTDE_PRODUTOS"].fillna(0).astype(int)

        is_combinado = tipo_servico.str.contains("&", case=False, regex=False, na=False)
        tem_tv = tipo_servico.str.contains(
            "TV", case=False, regex=False, na=False
        ).astype(int)
        tem_virtua = tipo_servico.str.contains(
            r"MEGA|GIGA", case=False, regex=True, na=False
        ).astype(int)

        cons["QTDE_TV"] = (tem_tv * qtde_prod).mask(is_combinado, tem_tv)
        cons["QTDE_VIRTUA"] = (tem_virtua * qtde_prod).mask(is_combinado, tem_virtua)
        cons["QTDE_MESH"] = (
            cons["QTDE_PRODUTOS"] - cons["QTDE_TV"] - cons["QTDE_VIRTUA"]
        ).clip(lower=0)

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
    def sincronizar() -> tuple[
        dict[str, pd.DataFrame], dict[str, pd.DataFrame], pd.DataFrame
    ]:
        """Faz o download e processamento de todas as bases remotas."""
        prod_raw: dict[str, pd.DataFrame] = {}

        # 1) Produção
        try:
            prod_result = pd.read_excel(
                Configuracoes.URL_PROD,
                sheet_name=Configuracoes.ABAS_PROD,
                engine="openpyxl",
            )
            if isinstance(prod_result, dict):
                prod_raw = {
                    str(k): v
                    for k, v in prod_result.items()
                    if isinstance(v, pd.DataFrame)
                }
            elif isinstance(prod_result, pd.DataFrame):
                prod_raw = {"Prod": prod_result}
            else:
                prod_raw = {"Prod": pd.DataFrame()}
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar Produção Excel: {e}") from e

        # 2) Consultivo
        try:
            cons = ProcessadorDeDados._ler_csv_remoto(Configuracoes.URL_CONS)
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar Consultivo CSV: {e}") from e

        # 3) Ativos
        try:
            ativos = ProcessadorDeDados._ler_csv_remoto(Configuracoes.URL_ATIVOS)
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar Lista de Ativos: {e}") from e

        cons_dict: dict[str, pd.DataFrame] = {}

        if cons is None or cons.empty:
            cons_dict = {"Consultivo": pd.DataFrame()}
            return prod_raw, cons_dict, ativos

        cons = ProcessadorDeDados.tratar_planos(cons)
        cons = ProcessadorDeDados._processar_quantidades(cons)
        cons = ProcessadorDeDados._merge_ativos(cons, ativos)

        cons_dict = {"Consultivo": cons}
        return prod_raw, cons_dict, ativos


def _obter_dataframe(chave_state: str, nome_aba: str | None = None) -> pd.DataFrame:
    """Helper seguro para extrair DataFrames do st.session_state."""
    dados = st.session_state.get(chave_state)
    if dados is None:
        return pd.DataFrame()
    if isinstance(dados, dict):
        if len(dados) == 0:
            return pd.DataFrame()
        if nome_aba and nome_aba in dados:
            res = dados[nome_aba]
        else:
            res = next(iter(dados.values()))
        return res if isinstance(res, pd.DataFrame) else pd.DataFrame()
    if isinstance(dados, pd.DataFrame):
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
    titulo="🔁 Central de Atualização",
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

tem_dados = (len(df_prod) > 0) or (len(df_cons) > 0)

if tem_dados:
    total_equip = (
        int(df_cons["QTDE_PRODUTOS"].fillna(0).sum())
        if ("QTDE_PRODUTOS" in df_cons.columns and len(df_cons) > 0)
        else 0
    )
    media_servicos = (
        float(df_cons["QTDE_CONSULTIVO"].fillna(0).mean())
        if ("QTDE_CONSULTIVO" in df_cons.columns and len(df_cons) > 0)
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
        if len(df_prod) > 0:
            render_table_html(df_prod, max_rows=50, colunas_num=[], height=360)
        else:
            render_insight("Aba de Produção vazia ou não encontrada.", "alerta")

    with tab_c:
        render_section_header("📋", "Base Consultiva Detalhada", "Processado")
        if len(df_cons) > 0:
            render_table_html(df_cons, max_rows=50, colunas_num=[], height=360)
        else:
            render_insight("Base consultiva vazia.", "alerta")
else:
    render_insight(
        "Clique em **Sincronizar Agora** para carregar e visualizar as bases de dados.",
        "acao",
    )
