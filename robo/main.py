from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from robo.robo_local import renderizar_sidebar_robo

st.set_page_config(
    page_title="Dashboard Operacional TOTALE",
    layout="wide",
)


def meu_pipeline_etl(
    df_local: pd.DataFrame,
    df_gsheets: pd.DataFrame,
) -> pd.DataFrame:
    """Trata e guarda os dados lidos do arquivo TOTALE mais recente."""
    try:
        df = df_local.copy()
        df.columns = [str(col).strip().upper() for col in df.columns]

        # Disponibiliza os dados para outros componentes do app.
        st.session_state["dados_totale"] = df
        return df
    except Exception as e:
        st.error(f"Erro no ETL: {e}")
        return pd.DataFrame()


st.title("Dashboard Operacional TOTALE")
st.caption("O robô processa somente o arquivo mais recente da pasta monitorada.")

pasta_dados = Path(__file__).resolve().parent / "dados"
pasta_dados.mkdir(parents=True, exist_ok=True)

renderizar_sidebar_robo(
    etl_fn=meu_pipeline_etl,
    pasta_padrao=str(pasta_dados),
)

# Exibe os dados processados se existirem.
dados = st.session_state.get("dados_totale")
if isinstance(dados, pd.DataFrame):
    fonte = st.session_state.get("origem_dados", "Robô Local")
    st.success(f"Dados carregados via {fonte}")
    st.dataframe(dados.head(), width="stretch")
else:
    st.info("Aguardando a detecção do arquivo mais recente na pasta configurada...")
