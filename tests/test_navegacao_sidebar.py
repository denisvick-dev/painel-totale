"""Testes de busca e organização do menu lateral do portal."""

from __future__ import annotations

from config.navegacao import GRUPOS, PAGINAS, filtrar_paginas


def test_busca_sidebar_ignora_acentos_e_case() -> None:
    resultados = filtrar_paginas("PRODUCAO mensal")

    assert [pagina.titulo for pagina in resultados] == ["Produção Mensal"]


def test_busca_sidebar_considera_descricao_e_area() -> None:
    resultados = filtrar_paginas("SLA")

    assert [pagina.grupo for pagina in resultados] == ["SLA & Quebra", "SLA & Quebra"]
    assert [pagina.titulo for pagina in resultados] == ["Quebra Geral", "Quebra por Segmento"]


def test_busca_com_mais_de_um_termo_exige_coincidencia_conjunta() -> None:
    assert [pagina.titulo for pagina in filtrar_paginas("rota geral")] == ["Rota Geral"]
    assert filtrar_paginas("rota desempenho inexistente") == []


def test_busca_vazia_devolve_todos_os_paineis_visiveis_na_ordem_do_mapa() -> None:
    assert filtrar_paginas() == [pagina for pagina in PAGINAS if pagina.visivel]
    assert all(pagina.grupo in GRUPOS for pagina in filtrar_paginas())
