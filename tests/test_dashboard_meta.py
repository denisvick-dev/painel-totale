"""
Regressão: pages/dashboard_meta.py quebrava com "No secrets found".

Os ``default_factory`` de :class:`Configuracoes` chamavam ``st.secrets.get``
diretamente. Sem ``.streamlit/secrets.toml`` (clone novo, CI, fork), o
Streamlit levanta ``StreamlitSecretNotFoundError`` na importação do módulo e a
página inteira falhava — mesmo existindo valor padrão no ``get``.

Executar: pytest tests/test_dashboard_meta.py -v
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]


class _SemArquivoDeSegredos:
    """Simula o comportamento do Streamlit sem .streamlit/secrets.toml."""

    def get(self, *_args, **_kwargs):
        raise FileNotFoundError("No secrets found")

    def __contains__(self, _chave):
        raise FileNotFoundError("No secrets found")


def _excecoes(at) -> list[str]:
    return [str(e.value).replace("\n", " | ")[:200] for e in at.exception]


def test_secret_devolve_padrao_sem_arquivo_de_segredos(monkeypatch):
    import pages.dashboard_meta as dm

    monkeypatch.setattr(st, "secrets", _SemArquivoDeSegredos(), raising=False)
    assert dm._secret("URL_ATIVOS", "padrao") == "padrao"


def test_secret_devolve_valor_configurado(monkeypatch):
    import pages.dashboard_meta as dm

    monkeypatch.setattr(st, "secrets", {"URL_ATIVOS": "https://exemplo"}, raising=False)
    assert dm._secret("URL_ATIVOS", "padrao") == "https://exemplo"


def test_configuracoes_usam_valores_padrao(monkeypatch):
    import pages.dashboard_meta as dm

    monkeypatch.setattr(st, "secrets", _SemArquivoDeSegredos(), raising=False)
    cfg = dm.Configuracoes()
    assert cfg.SHEET_ABA_ATIVOS == "lista_ativos"
    assert cfg.SHEET_ABA_PROD == "Prod"
    assert cfg.URL_ATIVOS.startswith("https://docs.google.com/spreadsheets/d/")
    assert cfg.SHEET_ID_ATIVOS
    assert cfg.TIMEOUT > 0


def test_pagina_abre_sem_secrets_toml(monkeypatch):
    """Sem arquivo de segredos a página deve abrir, não estourar exceção."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(st, "secrets", _SemArquivoDeSegredos(), raising=False)
    at = AppTest.from_file(str(RAIZ / "pages" / "dashboard_meta.py"), default_timeout=90)
    at.run()

    erros = _excecoes(at)
    assert not any("No secrets found" in e for e in erros), erros
    assert not any("secrets" in e.lower() for e in erros), erros
