"""
components/__init__.py
======================
Pacote de componentes reutilizáveis do portal TOTALE.
"""

# Use import relativo (com o ponto) para evitar conflitos de pacote
from .criterios import (
    TERMO_GPON_HABILIDADE,
    # Constantes de critérios
    TERMO_MIGRACAO_OS,
    TERMOS_ND,
    TERMOS_PME,
    VALOR_FLAG_GPON_SIM,
    VAZIOS_CONTRATO,
    # Constantes de valores vazios
    VAZIOS_GERAIS,
    # Classificação principal
    classificar_tipo_servico,
    # Criação de colunas
    criar_coluna_tipos_agrupados,
    criar_flag_gpon,
    detectar_col_capacidade,
    detectar_col_contrato,
    detectar_col_flag_gpon,
    detectar_col_habilidade,
    detectar_col_status_atividade,
    detectar_col_tipo_os_1,
    # Detecção de colunas
    detectar_cols_tipo,
    norm_col_nome,
    # Normalização
    normalizar_str,
    render_card_destaque_migracao,
    # Componentes UI
    render_debug_criterios,
    render_lista_colunas,
    render_painel_criterios,
)

__all__ = [
    # Constantes
    "VAZIOS_GERAIS",
    "VAZIOS_CONTRATO",
    "TERMO_MIGRACAO_OS",
    "VALOR_FLAG_GPON_SIM",
    "TERMO_GPON_HABILIDADE",
    "TERMOS_ND",
    "TERMOS_PME",
    # Normalização
    "normalizar_str",
    "norm_col_nome",
    # Detecção
    "detectar_cols_tipo",
    "detectar_col_tipo_os_1",
    "detectar_col_flag_gpon",
    "detectar_col_capacidade",
    "detectar_col_habilidade",
    "detectar_col_status_atividade",
    "detectar_col_contrato",
    # Criação
    "criar_coluna_tipos_agrupados",
    "criar_flag_gpon",
    # Classificação
    "classificar_tipo_servico",
    # UI
    "render_debug_criterios",
    "render_card_destaque_migracao",
    "render_lista_colunas",
    "render_painel_criterios",
]
