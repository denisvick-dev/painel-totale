"""
robo/robo_config.py
====================
Configurações centralizadas do robô para todas as páginas.
"""

from typing import Optional, Callable, Dict, List, Any
import pandas as pd


class ConfigRobo:
    """Configurações do robô por página."""

    # Configurações globais
    PASTA_PADRAO = None  # None = Downloads do usuário
    TEMPO_VERIFICACAO = "10s"
    COLUNAS_ESPERADAS = None

    # Configurações por página
    PAGINAS: Dict[str, Dict[str, Any]] = {
        "rota_inicial": {
            "titulo": "ROTA INICIAL",
            "subtitulo": "Monitoramento de Rotas",
            "pasta": None,  # Usa padrão
            "etl_fn": None,
            "colunas": None,
            "ativo_padrao": True,
        },
        "p_atendimento": {
            "titulo": "ATENDIMENTO",
            "subtitulo": "Dados de Atendimento",
            "pasta": None,
            "etl_fn": None,
            "colunas": None,
            "ativo_padrao": True,
        },
        "volumetria": {
            "titulo": "VOLUMETRIA",
            "subtitulo": "Volume de Produção",
            "pasta": None,
            "etl_fn": None,
            "colunas": None,
            "ativo_padrao": True,
        },
    }

    @classmethod
    def get_config(cls, pagina: str) -> Dict[str, Any]:
        """Retorna configuração específica da página."""
        return cls.PAGINAS.get(
            pagina,
            {
                "titulo": "DASHBOARD",
                "subtitulo": "Monitoramento",
                "pasta": cls.PASTA_PADRAO,
                "etl_fn": None,
                "colunas": cls.COLUNAS_ESPERADAS,
                "ativo_padrao": True,
            },
        )