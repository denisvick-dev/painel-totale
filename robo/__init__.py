"""Pacote de sincronismo local TOTALE."""

from .robo_engine import (
    EXTENSOES_VALIDAS,
    MAPA_BASES_ARQUIVO,
    ArquivoBloqueadoError,
    LeituraArquivo,
    ResultadoCiclo,
    TotaleRoboEngine,
    buscar_arquivo_mais_recente,
    detectar_base_arquivo,
    detectar_marcador_arquivo,
    ler_arquivo_detalhado,
    mapear_arquivos_por_base,
    obter_metadados_arquivo,
    obter_pasta_robo_padrao,
    processar_candidatos,
    selecionar_arquivos,
)
from .robo_local import (
    executar_ciclo_headless,
    ler_arquivo_totale,
    renderizar_robo_local,
    renderizar_sidebar_robo,
)

__all__ = [
    "EXTENSOES_VALIDAS",
    "MAPA_BASES_ARQUIVO",
    "ArquivoBloqueadoError",
    "LeituraArquivo",
    "ResultadoCiclo",
    "TotaleRoboEngine",
    "buscar_arquivo_mais_recente",
    "detectar_base_arquivo",
    "detectar_marcador_arquivo",
    "executar_ciclo_headless",
    "ler_arquivo_detalhado",
    "ler_arquivo_totale",
    "mapear_arquivos_por_base",
    "obter_metadados_arquivo",
    "obter_pasta_robo_padrao",
    "processar_candidatos",
    "renderizar_robo_local",
    "renderizar_sidebar_robo",
    "selecionar_arquivos",
]