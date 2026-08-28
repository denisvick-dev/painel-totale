import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO, StringIO
from datetime import datetime
from zoneinfo import ZoneInfo
from components.componentes import (
    aplicar_estilo,
    render_hero_totale_1,
    render_kpi,
    render_section_header,
    render_insight,
    render_sidebar_brand,
    render_table_html,
)

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
    URL_PROD = "https://docs.google.com/spreadsheets/d/11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v/export?format=xlsx"
    URL_CONS = "https://drive.google.com/uc?id=1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs&export=download"
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/export?format=csv"
    VAZIOS = {"-", "nan", "None", "", "NaN", "nat", "NAT", "<NA>"}
    FUSO = ZoneInfo("America/Sao_Paulo")
    TIMEOUT = 20
    # Abas de produção que importam (não carrega o Excel inteiro se possível)
    ABAS_PROD = None  # ex: ["Prod"] — se souber o nome exato, coloque aqui


class ProcessadorDeDados:
    @staticmethod
    def _normalizar(serie: pd.Series) -> pd.Series:
        return (
            serie.fillna("")
            .astype(str)
            .str.strip()
            .replace(list(Configuracoes.VAZIOS), "")
        )

    @staticmethod
    def tratar_planos(df: pd.DataFrame) -> pd.DataFrame:
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df

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
        cond = [tem_tv & tem_net, tem_tv & ~tem_net, ~tem_tv & tem_net]
        opts = [tv_final + " & " + internet_limpa, tv_final, internet_limpa]
        df["TIPO SERVIÇO"] = np.select(cond, opts, default="Sem Tipo")
        df["PLANO TV"] = tv_final
        df["PLANO INTERNET"] = internet_limpa
        return df

    @staticmethod
    def _processar_quantidades(cons: pd.DataFrame) -> pd.DataFrame:
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
    def sincronizar():
        # 1) Produção — se souber a aba, NÃO leia sheet_name=None
        try:
            if Configuracoes.ABAS_PROD:
                prod_raw = pd.read_excel(
                    Configuracoes.URL_PROD,
                    sheet_name=Configuracoes.ABAS_PROD,
                    engine="openpyxl",
                )
                if isinstance(prod_raw, pd.DataFrame):
                    prod_raw = {Configuracoes.ABAS_PROD[0]: prod_raw}
            else:
                # fallback: todas as abas (mais lento)
                prod_raw = pd.read_excel(
                    Configuracoes.URL_PROD, sheet_name=None, engine="openpyxl"
                )
        except Exception as e:
            raise RuntimeError(f"Falha ao baixar Produção: {e}") from e

        # 2) Consultivo
        try:
            resp = requests.get(Configuracoes.URL_CONS, timeout=Configuracoes.TIMEOUT)
            resp.raise_for_status()
            if "text/html" in resp.headers.get("Content-Type", "").lower():
                raise RuntimeError(
                    "Google Drive bloqueou o download automático do CSV."
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
            raise RuntimeError(f"Falha ao baixar Consultivo: {e}") from e

        # 3) Ativos
        try:
            ativos = pd.read_csv(Configuracoes.URL_ATIVOS, dtype=str)
            ativos.columns = ativos.columns.str.strip()
        except Exception as e:
            raise RuntimeError(f"Falha ao baixar Ativos: {e}") from e

        if cons is None or cons.empty:
            return prod_raw, {"Consultivo": pd.DataFrame()}, ativos

        cons.columns = cons.columns.str.strip()
        cons = ProcessadorDeDados.tratar_planos(cons)
        cons = ProcessadorDeDados._processar_quantidades(cons)
        cons = ProcessadorDeDados._merge_ativos(cons, ativos)
        return prod_raw, {"Consultivo": cons}, ativos


# ====================================================
# INTERFACE
# ====================================================
with st.sidebar:
    render_sidebar_brand("TOTALE", "Data Management", icone="🏢")
    st.markdown("---")
    render_insight(
        "Use **Sincronizar Agora** para atualizar Produção, Consultivos e Ativos.",
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
            f"Última sincronização: **{ultima.strftime('%d/%m/%Y às %H:%M:%S')}**",
            "ok",
        )
    else:
        render_insight("Os dados ainda não foram carregados nesta sessão.", "alerta")

with col_btn:
    sincronizar = st.button(
        "🔄 Sincronizar Agora",
        use_container_width=True,
        type="primary",
    )

if sincronizar:
    try:
        with st.status("Conectando aos servidores...", expanded=True) as status:
            st.write("Baixando planilhas mestras...")
            ProcessadorDeDados.sincronizar.clear()
            p, c, a = ProcessadorDeDados.sincronizar()

            st.write("Aplicando regras de negócio...")
            st.session_state["dados_prod"] = p
            st.session_state["dados_cons"] = c
            st.session_state["dados_ativos"] = a
            st.session_state["ultima_atualizacao"] = datetime.now(Configuracoes.FUSO)

            status.update(
                label="Sincronização concluída!",
                state="complete",
                expanded=False,
            )
        st.success("✅ Bases atualizadas com sucesso!")
        # Sem st.rerun() — evita recarregar a página inteira
        # Os widgets abaixo já leem o session_state neste mesmo run
    except Exception as e:
        st.error(f"❌ Falha na sincronização: {e}")

st.divider()

# ---------- resolve dfs ----------
dados_prod = st.session_state.get("dados_prod", {})
if isinstance(dados_prod, dict) and dados_prod:
    df_prod = dados_prod.get("Prod")
    if df_prod is None or not isinstance(df_prod, pd.DataFrame):
        first = next(iter(dados_prod.values()))
        df_prod = first if isinstance(first, pd.DataFrame) else pd.DataFrame()
else:
    df_prod = pd.DataFrame()

dados_cons = st.session_state.get("dados_cons", {})
df_cons = (
    dados_cons.get("Consultivo", pd.DataFrame())
    if isinstance(dados_cons, dict)
    else pd.DataFrame()
)
if not isinstance(df_cons, pd.DataFrame):
    df_cons = pd.DataFrame()

tem_dados = (not df_prod.empty) or (not df_cons.empty)

if tem_dados:
    total_equip = (
        int(df_cons["QTDE_PRODUTOS"].fillna(0).sum())
        if not df_cons.empty and "QTDE_PRODUTOS" in df_cons.columns
        else 0
    )
    media_servicos = (
        float(df_cons["QTDE_CONSULTIVO"].fillna(0).mean())
        if not df_cons.empty and "QTDE_CONSULTIVO" in df_cons.columns
        else 0.0
    )

    k1, k2, k3, k4 = st.columns(4)
    render_kpi(
        k1,
        "Registros Produção",
        f"{len(df_prod):,}".replace(",", "."),
        "Aba 'Prod'",
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
        k4, "Serviços/Venda", f"{media_servicos:.2f}", "Média de penetração", "cinza"
    )

    tab_p, tab_c = st.tabs(["📊 Produção (Preview)", "📋 Consultivo Processado"])

    with tab_p:
        render_section_header("📊", "Base de Produção", "Top 50")
        if not df_prod.empty:
            # Preview leve: 50 linhas, 15 colunas
            render_table_html(
                df_prod,
                max_rows=50,
                max_cols=15,
                height=360,
            )
        else:
            render_insight(
                "Aba **Prod** não encontrada na planilha de Produção.", "alerta"
            )

    with tab_c:
        render_section_header("📋", "Base Consultiva Detalhada", "Processado")
        if not df_cons.empty:
            render_table_html(
                df_cons,
                max_rows=50,
                max_cols=15,
                height=360,
            )
        else:
            render_insight("Base consultiva vazia.", "alerta")
else:
    render_insight(
        "Clique em **Sincronizar Agora** para carregar e visualizar as bases.",
        "acao",
    )
