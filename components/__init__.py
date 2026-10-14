"""
components/__init__.py
======================
Pacote de componentes reutilizáveis do portal TOTALE.

Módulos do Design System v3.6.0 (carregados sob demanda via ``__getattr__``
para não importar Streamlit/Plotly em quem usa apenas :mod:`components.criterios`):

=================================  ==========================================================
Módulo                             Responsabilidade
=================================  ==========================================================
``componentes``                    Design System base (cores, fontes, KPI, heróis, tabelas)
``kpi_cards``                      Cartões de KPI avançados — substituto do ``st.metric``
``graficos``                       Fábrica minimalista de 24 tipos de gráfico (Plotly Express)
``css_global``                     CSS global dos componentes nativos (uma injeção por sessão)
``layout_pagina``                  Hierarquia de leitura das páginas (seções, filtros, rodapé)
``dashboard_kit``                  Kit de dashboards (CSS v2, filtros, insights, exportação)
``sidebar``                        Sidebar corporativa e temas
=================================  ==========================================================
"""

from typing import TYPE_CHECKING, Any

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

#: Submódulos do Design System expostos como atributos do pacote (lazy).
_MODULOS_DESIGN_SYSTEM = (
    "componentes",
    "css_global",
    "dashboard_kit",
    "graficos",
    "kpi_cards",
    "layout_pagina",
    "sidebar",
)

if TYPE_CHECKING:  # apenas para ferramentas estáticas; não importa em runtime
    from . import (  # noqa: F401
        componentes,
        css_global,
        dashboard_kit,
        graficos,
        kpi_cards,
        layout_pagina,
        sidebar,
    )


def __getattr__(nome: str) -> Any:
    """Importa os módulos de UI sob demanda (PEP 562)."""
    if nome in _MODULOS_DESIGN_SYSTEM:
        from importlib import import_module

        return import_module(f"{__name__}.{nome}")
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")


def __dir__() -> list[str]:
    return sorted([*globals().keys(), *_MODULOS_DESIGN_SYSTEM])


__all__ = [
    # Módulos do Design System (lazy)
    *_MODULOS_DESIGN_SYSTEM,
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
