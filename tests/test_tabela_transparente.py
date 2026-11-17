"""Testes do aviso de truncamento das tabelas (C4).

``render_table_html`` cortava em 100 linhas sem avisar. Estes testes travam o
contrato novo: a prévia é declarada, o total aparece no aviso e ``max_rows=None``
renderiza tudo. A exportação usa o conjunto completo por construção
(``df_completo``), inclusive quando a tabela está truncada.

    pytest tests/test_tabela_transparente.py
"""

from __future__ import annotations

import pandas as pd
import pytest

from components import componentes


@pytest.fixture()
def capturar_html(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    capturado: list[str] = []

    def _fake(html: str, container: object = None) -> None:
        capturado.append(html)

    monkeypatch.setattr(componentes, "_safe_render_html", _fake)
    return capturado


def _tabela(linhas: int = 5) -> pd.DataFrame:
    return pd.DataFrame({"Técnico": [f"T{i}" for i in range(linhas)], "O.S.": range(linhas)})


def test_tabela_truncada_declara_quantas_linhas_ficaram_fora(capturar_html: list[str]) -> None:
    componentes.render_table_html(_tabela(5), max_rows=2, caption="Recorte de teste")

    html = capturar_html[-1]
    assert "Exibindo <strong>2</strong> de <strong>5</strong> linhas (40,0%)" in html
    assert "A exportação abaixo inclui o conjunto completo" in html
    assert "Recorte de teste" in html
    assert html.count("<td") == 4  # 2 linhas × 2 colunas, não as 10 células do total


def test_sem_truncamento_nao_mostra_aviso(capturar_html: list[str]) -> None:
    componentes.render_table_html(_tabela(3), max_rows=100)

    html = capturar_html[-1]
    assert "Exibindo" not in html
    assert html.count("<td") == 6


def test_max_rows_none_renderiza_o_conjunto_completo(capturar_html: list[str]) -> None:
    componentes.render_table_html(_tabela(12), max_rows=None)

    html = capturar_html[-1]
    assert "Exibindo" not in html
    assert html.count("<td") == 24


def test_caption_e_escapados_na_tabela(capturar_html: list[str]) -> None:
    componentes.render_table_html(_tabela(2), caption="<script>alert(1)</script>")

    html = capturar_html[-1]
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
