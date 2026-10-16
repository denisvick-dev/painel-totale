"""Smoke test do shell multipágina do Streamlit."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from config.navegacao import GRUPOS, PAGINAS
from streamlit_app import GerenciadorNavegacao

RAIZ = Path(__file__).resolve().parents[1]


def test_entrypoint_inicializa_sem_excecao() -> None:
    """O entrypoint monta o menu recolhível e expõe a busca sem falhas."""
    app = AppTest.from_file(str(RAIZ / "streamlit_app.py"), default_timeout=60).run()
    assert not list(app.exception), f"Falha ao iniciar o portal: {list(app.exception)}"
    assert any(
        widget.key == "_totale_sidebar_navigation_search" for widget in app.sidebar.text_input
    ), "O campo de busca do menu lateral não foi renderizado."
    assert len(app.sidebar.page_link) == sum(pagina.visivel for pagina in PAGINAS)
    rotulos_expanders = {expander.label for expander in app.sidebar.expander}
    assert "🎨 Aparência" in rotulos_expanders
    assert all(any(grupo in rotulo for rotulo in rotulos_expanders) for grupo in GRUPOS)
    estado_grupos = {
        grupo: next(expander for expander in app.sidebar.expander if grupo in expander.label)
        for grupo in GRUPOS
    }
    assert estado_grupos[GRUPOS[0]].proto.expanded
    assert all(not estado_grupos[grupo].proto.expanded for grupo in GRUPOS[1:])


def test_status_sidebar_conta_linhas_nas_abas_e_detecta_base_vazia() -> None:
    dados = {
        "Prod": pd.DataFrame({"os": [1, 2]}),
        "Gpon": pd.DataFrame({"os": [3]}),
    }
    assert GerenciadorNavegacao._resumir_status_dados(dados) == (
        "Dados disponíveis",
        "ok",
        3,
    )
    assert GerenciadorNavegacao._resumir_status_dados({"Prod": pd.DataFrame(columns=["os"])}) == (
        "Base carregada sem registros",
        "alerta",
        0,
    )
    assert GerenciadorNavegacao._resumir_status_dados(None) == (
        "Aguardando dados",
        "info",
        None,
    )
