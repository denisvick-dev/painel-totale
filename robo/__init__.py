"""Pacote de sincronismo local TOTALE."""
from .robo_local import (
    renderizar_robo_local,
    buscar_arquivo_mais_recente,
    ler_arquivo_totale,
    obter_pasta_robo_padrao,
    obter_metadados_arquivo,
)

__all__ = [
    "renderizar_robo_local",
    "buscar_arquivo_mais_recente",
    "ler_arquivo_totale",
    "obter_pasta_robo_padrao",
    "obter_metadados_arquivo",
]