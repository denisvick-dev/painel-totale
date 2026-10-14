"""Camada de serviços de infraestrutura e integração externa do Portal TOTALE.

Desde a v3.6.0 inclui :mod:`services.cache_dados` — HTTP reutilizável, cache
condicional (``304``), cache Parquet em disco, carga paralela e diagnósticos de
desempenho.
"""

from .cache_dados import (
    TTL_PADRAO,
    EspecificacaoFonte,
    ResultadoCarga,
    baixar_condicional,
    carregar_com_cache,
    carregar_planilha_gsheets,
    carregar_varias,
    datas_normalizadas,
    diretorio_cache,
    estatisticas_cache,
    ler_csv_rapido,
    limpar_cache,
    memoria_dataframe,
    otimizar_dtypes,
    render_painel_desempenho,
    sessao_http,
    temporizar,
)
from .google_drive_client import (
    adicionar_confirm_url,
    baixar_arquivo_drive,
    baixar_bytes_drive,
    carregar_excel_drive,
    carregar_planilha_gsheets_csv,
    criar_sessao_http,
    e_resposta_html,
    extrair_token_confirm,
    ler_csv_remoto,
    ler_csv_uma_tentativa,
    separadores_csv,
    urls_download_drive,
)

__all__ = [
    "EspecificacaoFonte",
    "ResultadoCarga",
    "TTL_PADRAO",
    "adicionar_confirm_url",
    "baixar_condicional",
    "carregar_com_cache",
    "carregar_planilha_gsheets",
    "carregar_varias",
    "datas_normalizadas",
    "diretorio_cache",
    "estatisticas_cache",
    "baixar_arquivo_drive",
    "baixar_bytes_drive",
    "carregar_excel_drive",
    "carregar_planilha_gsheets_csv",
    "criar_sessao_http",
    "e_resposta_html",
    "extrair_token_confirm",
    "ler_csv_remoto",
    "ler_csv_rapido",
    "ler_csv_uma_tentativa",
    "limpar_cache",
    "memoria_dataframe",
    "otimizar_dtypes",
    "render_painel_desempenho",
    "separadores_csv",
    "sessao_http",
    "temporizar",
    "urls_download_drive",
]
