"""Camada de serviços de infraestrutura e integração externa do Portal TOTALE.

Desde a v3.6.0 inclui :mod:`services.cache_dados` — HTTP reutilizável, cache
condicional (``304``), cache Parquet em disco, carga paralela e diagnósticos de
desempenho.

Desde a v3.7.0 a camada foi completada com os serviços que os dashboards
duplicavam entre si:

=================================  ==========================================================
Módulo                             Responsabilidade
=================================  ==========================================================
``cache_dados``                    HTTP, cache condicional, Parquet em disco, carga paralela
``google_drive_client``            Google Drive / Sheets (download, CSV, confirmação)
``hierarquia``                     Lista de Ativos (Login → Técnico → Monitor → Base)
``dados_sessao``                   Contrato das bases carregadas na sessão (guarda de entrada)
``planilhas``                      Leitura de uploads e exportação CSV/XLSX corporativa
``texto``                          Normalização de texto, colunas, logins e números pt-BR
=================================  ==========================================================
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
from .dados_sessao import (
    CHAVE_ATUALIZACAO,
    CHAVE_CONSULTIVO,
    CHAVE_MEMORIA,
    CHAVE_PRODUCAO,
    MENSAGEM_SEM_DADOS,
    ResumoCarga,
    coletar_dataframes,
    concatenar_abas,
    exigir_base,
    obter_base,
    resumir_carga,
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
from .hierarquia import (
    ALIASES as ALIASES_HIERARQUIA,
)
from .hierarquia import (
    carregar_hierarquia,
    hierarquia_da_sessao,
    hierarquia_vazia,
    normalizar_hierarquia,
)
from .planilhas import (
    botao_download_csv,
    botao_download_planilha,
    gerar_csv,
    gerar_excel,
    gerar_excel_multiabas,
    ler_bytes,
    ler_upload,
    nome_com_carimbo,
)
from .texto import (
    buscar_coluna,
    colunas_presentes,
    escapar_html,
    formatar_inteiro,
    formatar_numero,
    formatar_percentual,
    normalizar_chave,
    normalizar_login,
    normalizar_texto,
    valor_nan,
    valor_vazio,
)

__all__ = [
    "ALIASES_HIERARQUIA",
    "CHAVE_ATUALIZACAO",
    "CHAVE_CONSULTIVO",
    "CHAVE_MEMORIA",
    "CHAVE_PRODUCAO",
    "EspecificacaoFonte",
    "MENSAGEM_SEM_DADOS",
    "ResumoCarga",
    "botao_download_csv",
    "botao_download_planilha",
    "buscar_coluna",
    "carregar_hierarquia",
    "coletar_dataframes",
    "colunas_presentes",
    "concatenar_abas",
    "escapar_html",
    "exigir_base",
    "formatar_inteiro",
    "formatar_numero",
    "formatar_percentual",
    "gerar_csv",
    "gerar_excel",
    "gerar_excel_multiabas",
    "hierarquia_da_sessao",
    "hierarquia_vazia",
    "ler_bytes",
    "ler_upload",
    "nome_com_carimbo",
    "normalizar_chave",
    "normalizar_hierarquia",
    "normalizar_login",
    "normalizar_texto",
    "obter_base",
    "resumir_carga",
    "valor_nan",
    "valor_vazio",
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
