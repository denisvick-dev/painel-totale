import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from io import BytesIO, StringIO
from datetime import datetime, timezone, timedelta
from components.componentes import aplicar_estilo

# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================

# ✅ set_page_config SEMPRE deve ser o primeiro comando Streamlit
st.set_page_config(page_title="Atualização de Dados", page_icon="🔁", layout="wide")

# ✅ aplicar_estilo() DEPOIS do set_page_config
aplicar_estilo()

class Configuracoes:
    """Parâmetros e configurações gerais da aplicação."""

    FUSO = timezone(timedelta(hours=-3))  # Fuso horário de Brasília

    TEMAS_CARD = {
        "azul": {
            "fundo": "#F0F9FF",
            "texto": "#0369A1",
            "borda": "#0EA5E9",
            "titulo": "#075985",
        },
        "verde": {
            "fundo": "#F0FDF4",
            "texto": "#15803D",
            "borda": "#22C55E",
            "titulo": "#166534",
        },
        "cinza": {
            "fundo": "#F8FAFC",
            "texto": "#334155",
            "borda": "#94A3B8",
            "titulo": "#64748B",
        },
    }

    # URLs de Exportação
    URL_PROD = "https://docs.google.com/spreadsheets/d/11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v/export?format=xlsx"
    URL_CONS = "https://drive.google.com/uc?id=1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs&export=download"
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/export?format=csv"

    # Valores considerados "vazios" — centralizado aqui para ser usado em todo o projeto
    VAZIOS = {"-", "nan", "None", "", "NaN"}


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS
# ====================================================


class Visual:
    """Responsável por renderizar componentes na tela."""

    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul") -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        return f"""
        <div style="
            background-color: {cores['fundo']};
            padding: 20px;
            border-radius: 10px;
            border-left: 6px solid {cores['borda']};
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 15px;
            transition: transform 0.2s;
            font-family: 'Manrope', 'Segoe UI', Arial, sans-serif;"
            onmouseover="this.style.transform='scale(1.02)'"
            onmouseout="this.style.transform='scale(1)'">
            <p style="
                margin: 0;
                font-size: 14px;
                color: {cores['titulo']};
                font-family: 'Manrope', 'Segoe UI', Arial, sans-serif;">
                <b>{titulo}</b>
            </p>
            <h2 style="
                margin: 0;
                padding-top: 5px;
                color: {cores['texto']};
                font-weight: 900;
                font-family: 'Manrope', 'Segoe UI', Arial, sans-serif;">
                {valor}
            </h2>
        </div>
        """

    @staticmethod
    def aplicar_capa():
        st.markdown(
            """
        <style>
        /* CRIAÇÃO DE ESTILOS PARA A HERO (barra de títulos) — ESTILO PORTAL TOTALE */
        .hero-corp {
            background: linear-gradient(90deg, 
                #1E293B 0%,       /* Slate escuro (esquerda) */
                #334155 25%,      /* Slate médio */
                #64748B 55%,      /* Prata slate */
                #94A3B8 75%,      /* Prata claro */
                #CBD5E1 92%,      /* Prata brilhante */
                #94A3B8 100%      /* Retorno sutil ao prata */
            );
            padding: 32px 48px;
            border-radius: 12px;
            color: white;
            box-shadow: 
                0 8px 32px rgba(15, 23, 42, 0.35),
                inset 0 1px 0 rgba(255, 255, 255, 0.20);
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(203, 213, 225, 0.25);
            min-height: 110px;
        }

        /* Círculo prata brilhante no canto direito (como o dourado da imagem) */
        .hero-corp::before {
            content: '';
            position: absolute;
            top: 50%;
            right: -80px;
            transform: translateY(-50%);
            width: 380px;
            height: 380px;
            background: radial-gradient(
                circle at center,
                rgba(226, 232, 240, 0.35) 0%,      /* Centro prata brilhante */
                rgba(203, 213, 225, 0.20) 30%,     /* Prata médio */
                rgba(148, 163, 184, 0.08) 55%,     /* Prata suave */
                transparent 75%
            );
            border-radius: 50%;
            pointer-events: none;
            filter: blur(2px);
        }

        /* Reflexo prata diagonal (efeito metálico escovado) */
        .hero-corp::after {
            content: '';
            position: absolute;
            top: 0;
            left: 40%;
            width: 30%;
            height: 100%;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.06) 40%,
                rgba(255, 255, 255, 0.12) 50%,
                rgba(255, 255, 255, 0.06) 60%,
                transparent 100%
            );
            transform: skewX(-15deg);
            pointer-events: none;
        }

        .hero-title {
            font-size: 36px;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.8px;
            font-family: 'Segoe UI', -apple-system, sans-serif;
            color: #FFFFFF;
            text-shadow: 
                0 2px 4px rgba(0, 0, 0, 0.5),
                0 1px 2px rgba(0, 0, 0, 0.3),
                0 0 24px rgba(255, 255, 255, 0.12);
            position: relative;
            z-index: 2;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .hero-subtitle {
            font-size: 14px;
            opacity: 0.90;
            margin: 8px 0 0 0;
            font-weight: 400;
            color: #F1F5F9;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
            position: relative;
            z-index: 2;
            letter-spacing: 0.3px;
        }

        .hero-badge {
            display: inline-block;
            background: linear-gradient(135deg,
                rgba(255, 255, 255, 0.22) 0%,
                rgba(255, 255, 255, 0.10) 100%
            );
            padding: 5px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 12px;
            letter-spacing: 0.6px;
            text-transform: uppercase;
            color: #FFFFFF;
            border: 1px solid rgba(255, 255, 255, 0.25);
            backdrop-filter: blur(10px);
            box-shadow: 
                0 2px 8px rgba(0, 0, 0, 0.2),
                inset 0 1px 0 rgba(255, 255, 255, 0.2);
            position: relative;
            z-index: 2;
        }
        
            .kpi-card {
                padding: 1.4rem 1.6rem; border-radius: 1rem; border-left: 5px solid;
                box-shadow: 0 4px 12px rgba(0,0,0,0.06);
                min-height: 110px; display: flex; flex-direction: column; justify-content: center;
            }
            .kpi-val  { font-size: 1.85rem; font-weight: 800; line-height: 1.1; margin: 0.3rem 0; }
            .kpi-lab  { font-size: 0.72rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; }
            .kpi-sub  { font-size: 0.78rem; margin-top: 0.2rem; }
            .section-header {
                display: flex; align-items: center; gap: 0.6rem;
                margin: 1.5rem 0 0.8rem; padding-bottom: 0.4rem;
                border-bottom: 2px solid #E2E8F0;
            }
            .section-header h3 { margin: 0; font-size: 1.1rem; color: #0F172A; }
        </style>
        """,
            unsafe_allow_html=True,
        )


# ====================================================
# BLOCO 3: PROCESSAMENTO DE DADOS (VETORIZADO)
# ====================================================


class ProcessadorDeDados:

    @staticmethod
    def _normalizar_serie(serie: pd.Series) -> pd.Series:
        """
        Utilitário interno: converte uma Series para string, remove espaços
        e substitui qualquer valor da lista VAZIOS por string vazia ''.
        Garante que np.nan também seja tratado.
        """
        return (
            serie.astype(str)
            .str.strip()
            .replace(
                list(Configuracoes.VAZIOS), ""
            )  # Substitui strings vazias conhecidas
            .fillna("")  # Garante que np.nan vire ""
        )

    @staticmethod
    def tratar_planos_vetorizado(df: pd.DataFrame) -> pd.DataFrame:
        """
        Processa e limpa os nomes dos planos de forma vetorizada.
        Garante contagem correta em QTDE_CONSULTIVO.

        Regras:
        - Se PLANO TV for vazio, tenta extrair do campo PLANO INTERNET (após o ponto)
        - TIPO SERVIÇO = TV & Internet | só TV | só Internet | Sem Tipo
        - QTDE_CONSULTIVO = quantidade de serviços ativos (0, 1 ou 2)
        """
        # 1. Cláusula de guarda
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df

        # ----------------------------------------------------------------
        # 2. Limpeza e normalização do PLANO TV
        # ----------------------------------------------------------------
        tv_bruta = (
            df["PLANO TV"]
            .astype(str)
            .str.strip()
            .replace("SERVIÇOS AVANÇADOS", "CLARO TV+ BOX")  # Substituição de negócio
        )

        # ----------------------------------------------------------------
        # 3. Limpeza e split do PLANO INTERNET
        #    Alguns registros chegam como: "500 MEGA.CLARO TV+ BOX"
        #    → internet_limpa = "500 MEGA"
        #    → tv_do_internet  = "CLARO TV+ BOX"
        # ----------------------------------------------------------------
        internet_bruta = df["PLANO INTERNET"].astype(str).str.strip()
        partes = internet_bruta.str.split(".", n=1, expand=True)

        internet_limpa = ProcessadorDeDados._normalizar_serie(partes[0])

        # TV embutida no campo internet (parte após o ponto), se existir
        tv_do_internet = (
            ProcessadorDeDados._normalizar_serie(partes[1])
            if partes.shape[1] > 1
            else pd.Series("", index=df.index, dtype=str)
        )

        # ----------------------------------------------------------------
        # 4. Resolução final do PLANO TV:
        #    Usa o valor original, mas se for vazio, pega o que veio do campo internet
        # ----------------------------------------------------------------
        tv_normalizada = ProcessadorDeDados._normalizar_serie(tv_bruta)

        tv_limpa = pd.Series(
            np.where(tv_normalizada != "", tv_normalizada, tv_do_internet),
            index=df.index,
            dtype=str,
        )

        # ----------------------------------------------------------------
        # 5. Flags booleanas (base para contagem e tipo de serviço)
        # ----------------------------------------------------------------
        tem_tv = tv_limpa != ""
        tem_internet = internet_limpa != ""

        # ----------------------------------------------------------------
        # 6. QTDE_CONSULTIVO — contagem robusta e explícita
        #    Cada serviço ativo contribui com +1 (máximo 2)
        # ----------------------------------------------------------------
        df["QTDE_CONSULTIVO"] = tem_tv.astype(int) + tem_internet.astype(int)

        # ----------------------------------------------------------------
        # 7. TIPO SERVIÇO — np.select deixa as condições legíveis
        # ----------------------------------------------------------------
        condicoes = [
            tem_tv & tem_internet,  # Tem ambos
            tem_tv & ~tem_internet,  # Só TV
            ~tem_tv & tem_internet,  # Só Internet
        ]
        opcoes = [
            tv_limpa + " & " + internet_limpa,
            tv_limpa,
            internet_limpa,
        ]
        df["TIPO SERVIÇO"] = np.select(condicoes, opcoes, default="Sem Tipo")

        # ----------------------------------------------------------------
        # 8. Persiste as colunas limpas no DataFrame
        # ----------------------------------------------------------------
        df["PLANO TV"] = tv_limpa
        df["PLANO INTERNET"] = internet_limpa

        return df

    # ------------------------------------------------------------------

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)
    def baixar_e_processar():
        """Faz o download e processamento matemático dos dados."""

        # 1. Download de Produção
        try:
            prod_raw = pd.read_excel(
                Configuracoes.URL_PROD, sheet_name=None, engine="openpyxl"
            )
        except Exception as e:
            st.error(f"Erro ao baixar Produção: {e}")
            prod_raw = {}

        # 2. Download do CSV Consultivo (Google Drive)
        cons_raw = {}
        try:
            resposta = requests.get(Configuracoes.URL_CONS)
            resposta.raise_for_status()

            if "text/html" in resposta.headers.get("Content-Type", ""):
                st.error(
                    "❌ O Google Drive bloqueou o download automático do CSV "
                    "(Aviso de Antivírus ou Arquivo Restrito)."
                )
            else:
                try:
                    df_csv = pd.read_csv(StringIO(resposta.text), sep=",")
                except Exception:
                    df_csv = pd.read_csv(
                        BytesIO(resposta.content),
                        sep=";",
                        encoding="utf-8",
                        engine="python",
                    )
                cons_raw = {"Aba_Dinamica": df_csv}

        except Exception as e:
            st.error(f"❌ Erro ao baixar ou ler o arquivo CSV do Google Drive: {e}")

        # 3. Download da Lista de Ativos
        try:
            ativos = pd.read_csv(Configuracoes.URL_ATIVOS)
            ativos.columns = ativos.columns.str.strip()
        except Exception as e:
            st.error(f"Erro ao baixar ATIVOS: {e}")
            ativos = pd.DataFrame()

        # Extração segura da aba dinâmica
        if cons_raw and isinstance(cons_raw, dict):
            cons = cons_raw[list(cons_raw.keys())[0]]
        else:
            cons = pd.DataFrame()

        if cons.empty:
            return prod_raw, {"Consultivo": pd.DataFrame()}, ativos

        cons.columns = cons.columns.str.strip()

        # 4. Processamento de Produtos (códigos numéricos na OBSERVACAO)
        if "OBSERVACAO" in cons.columns:
            cons["LISTA_PRODUTOS"] = (
                cons["OBSERVACAO"].fillna("").astype(str).str.findall(r"\b\d{9,12}\b")
            )
            cons["QTDE_PRODUTOS"] = cons["LISTA_PRODUTOS"].apply(len)
        else:
            cons["LISTA_PRODUTOS"] = [[] for _ in range(len(cons))]
            cons["QTDE_PRODUTOS"] = 0

        # 5. Tratamento vetorizado de planos (TV / Internet / Tipo)
        cons = ProcessadorDeDados.tratar_planos_vetorizado(cons)

        # 6. Cálculos de Equipamentos
        tipo_servico = (
            cons.get("TIPO SERVIÇO", pd.Series("", index=cons.index))
            .fillna("")
            .astype(str)
        )
        qtde_prod = cons["QTDE_PRODUTOS"].fillna(0).astype(int)

        is_combinado = tipo_servico.str.contains("&", case=False, regex=False)
        tem_tv = tipo_servico.str.contains("TV", case=False, regex=False)
        tem_virtua = tipo_servico.str.contains(r"MEGA|GIGA", case=False, regex=True)

        # Quando é combinado (TV + Internet), cada serviço conta como 1 equipamento
        # Quando é simples, multiplica pela qtde de produtos (ex: mesh)
        cons["QTDE_TV"] = np.where(
            is_combinado, tem_tv.astype(int), tem_tv.astype(int) * qtde_prod
        )
        cons["QTDE_VIRTUA"] = np.where(
            is_combinado, tem_virtua.astype(int), tem_virtua.astype(int) * qtde_prod
        )
        cons["QTDE_MESH"] = (qtde_prod - cons["QTDE_TV"] - cons["QTDE_VIRTUA"]).clip(
            lower=0
        )

        # 7. Merge com Ativos
        if (
            not ativos.empty
            and "Login" in ativos.columns
            and "LOGIN NETSALES" in cons.columns
        ):
            ativos_limpo = ativos[["Login", "Monitor", "U.N.", "Base"]].drop_duplicates(
                subset=["Login"]
            )
            cons = pd.merge(
                cons,
                ativos_limpo,
                left_on="LOGIN NETSALES",
                right_on="Login",
                how="left",
            ).drop(columns=["Login"])
            cons["Monitor"] = cons["Monitor"].fillna("Não Identificado")

        return prod_raw, {"Consultivo": cons}, ativos


# ====================================================
# BLOCO 4: INTERFACE E LÓGICA DE ATUALIZAÇÃO
# ====================================================
Visual.aplicar_capa()
st.markdown(
    f"""
    <div class="hero-corp">
        <div style="position:relative;z-index:2;">
            <h1 class="hero-title">🔁 Central de Atualização de Dados</h1>
            <p class="hero-subtitle">Sincronização e gestão de bases operacionais</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def executar_atualizacao() -> bool:
    status = st.empty()
    barra = st.progress(0)

    try:
        status.info("⏳ Fazendo download e processando dados em nuvem. Aguarde...")
        barra.progress(20)

        ProcessadorDeDados.baixar_e_processar.clear()
        p_raw, c_raw, a_raw = ProcessadorDeDados.baixar_e_processar()
        barra.progress(90)

        st.session_state["dados_prod"] = p_raw
        st.session_state["dados_cons"] = c_raw
        st.session_state["dados_ativos"] = a_raw
        st.session_state["ultima_atualizacao"] = datetime.now(Configuracoes.FUSO)

        barra.progress(100)
        time.sleep(0.5)
        status.empty()
        barra.empty()
        return True

    except Exception as e:
        status.empty()
        barra.empty()
        st.error(f"❌ Ocorreu um erro crítico durante a atualização: {e}")
        return False


# Carrega automaticamente na primeira visita
if "dados_cons" not in st.session_state:
    executar_atualizacao()

col_btn, _ = st.columns([1, 4])
with col_btn:
    if st.button("🔄 Atualizar Agora", use_container_width=True, type="primary"):
        if executar_atualizacao():
            st.success(
                "✅ Dados atualizados com sucesso e disponíveis para todas as páginas!"
            )

st.divider()

# ====================================================
# BLOCO 5: EXIBIÇÃO EM TABS
# ====================================================

dados_prod = st.session_state.get("dados_prod", {})
df_prod = (
    dados_prod["Prod"]
    if isinstance(dados_prod, dict) and "Prod" in dados_prod
    else pd.DataFrame()
)

dados_cons = st.session_state.get("dados_cons", {})
df_cons = (
    dados_cons["Consultivo"]
    if isinstance(dados_cons, dict) and "Consultivo" in dados_cons
    else pd.DataFrame()
)

ultima_data = st.session_state.get("ultima_atualizacao")
hora_str = (
    ultima_data.strftime("%d/%m/%Y às %H:%M:%S")
    if isinstance(ultima_data, datetime)
    else "Nunca atualizado"
)

aba1, aba2 = st.tabs(
    ["📊 Pré-visualização: Produção", "📋 Pré-visualização: Consultivos"]
)

# ---------- Aba Produção ----------
with aba1:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            Visual.criar_card(
                "Total Registros", f"{len(df_prod):,}".replace(",", "."), "azul"
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            Visual.criar_card("Total Colunas", str(len(df_prod.columns)), "cinza"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            Visual.criar_card("Última Sincronização", hora_str, "verde"),
            unsafe_allow_html=True,
        )

    if not df_prod.empty:
        st.dataframe(
            df_prod.head(100), use_container_width=True, height=400, hide_index=True
        )
    else:
        st.warning("⚠️ Nenhuma aba chamada 'Prod' encontrada.")

# ---------- Aba Consultivo ----------
with aba2:
    c4, c5, c6 = st.columns(3)
    with c4:
        st.markdown(
            Visual.criar_card(
                "Total Registros", f"{len(df_cons):,}".replace(",", "."), "azul"
            ),
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            Visual.criar_card("Total Colunas", str(len(df_cons.columns)), "cinza"),
            unsafe_allow_html=True,
        )
    with c6:
        st.markdown(
            Visual.criar_card("Última Sincronização", hora_str, "verde"),
            unsafe_allow_html=True,
        )

    if not df_cons.empty:
        st.dataframe(
            df_cons.head(100), use_container_width=True, height=400, hide_index=True
        )
    else:
        st.warning("⚠️ Nenhuma aba encontrada ou o arquivo CSV está vazio.")
