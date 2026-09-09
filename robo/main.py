import pandas as pd
import streamlit as st

from robo.robo_local import renderizar_sidebar_robo


def meu_pipeline_etl(df_local: pd.DataFrame, df_gsheets: pd.DataFrame) -> pd.DataFrame:
    """
    Tratamento dos dados.
    Recebe o DataFrame local e o DataFrame do Google Sheets,
    retornando o DataFrame processado.
    """
    try:
        df = df_local.copy()
        df.columns = [str(c).strip().upper() for c in df.columns]

        # Salva no session_state para acesso em outras partes do app
        st.session_state["dados_totale"] = df
        return df
    except Exception as e:
        st.error(f"Erro no ETL: {e}")
        return pd.DataFrame()


# Configuração da página
st.title("Dashboard Operacional TOTALE")

# Chamada corrigida usando etl_fn
renderizar_sidebar_robo(
    etl_fn=meu_pipeline_etl,
    pasta_padrao="./dados",  # Opcional: define uma pasta padrão inicial
)

# Exibe os dados processados se existirem
if "dados_totale" in st.session_state and isinstance(
    st.session_state["dados_totale"], pd.DataFrame
):
    fonte = st.session_state.get("origem_dados", "Robô Local")
    st.success(f"Dados carregados via {fonte}")
    st.dataframe(st.session_state["dados_totale"].head())
else:
    st.info("Aguardando detecção de arquivo pelo robô na pasta configurada...")
