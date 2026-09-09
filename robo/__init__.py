"""Pacote de sincronismo local TOTALE."""

from .robo_local import (
    buscar_arquivo_mais_recente,
    ler_arquivo_totale,
    obter_metadados_arquivo,
    obter_pasta_robo_padrao,
    renderizar_robo_local,
)

__all__ = [
    "buscar_arquivo_mais_recente",
    "ler_arquivo_totale",
    "obter_metadados_arquivo",
    "obter_pasta_robo_padrao",
    "renderizar_robo_local",
]
