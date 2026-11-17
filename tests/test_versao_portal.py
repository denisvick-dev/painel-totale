"""Guarda da versão publicada (ARQ6).

A versão do portal estava em três lugares (``config/settings``, README e
Design System) e eles divergiam. Este teste falha quando código e documentação
contam histórias diferentes, antes que o rodapé de produção seja a única pista.

    pytest tests/test_versao_portal.py
"""

from __future__ import annotations

import re
from pathlib import Path

from components.dashboards import versao_do_portal
from config.settings import (
    AMBIENTE_PORTAL,
    VERSAO_PORTAL,
    VERSAO_PORTAL_PADRAO,
)

RAIZ = Path(__file__).resolve().parents[1]


def _texto(caminho: str) -> str:
    return (RAIZ / caminho).read_text(encoding="utf-8")


def test_versao_do_rodape_vem_da_fonte_unica() -> None:
    assert versao_do_portal() == (VERSAO_PORTAL, AMBIENTE_PORTAL)


def test_readme_e_design_system_estao_na_mesma_versao() -> None:
    readme = _texto("README.md")
    design = _texto("docs/DESIGN_SYSTEM.md")

    assert f"Versão atual: **{VERSAO_PORTAL_PADRAO}**" in readme
    assert f"v{VERSAO_PORTAL_PADRAO}" in readme
    assert f"v{VERSAO_PORTAL_PADRAO}" in design.splitlines()[0]


def test_changelog_tem_a_versao_atual_no_topo() -> None:
    linhas = _texto("CHANGELOG.md").splitlines()
    titulos = [linha for linha in linhas if linha.startswith("## [")]

    assert titulos, "CHANGELOG.md sem entradas versionadas."
    assert titulos[0].startswith(f"## [{VERSAO_PORTAL_PADRAO}]")


def test_home_nao_hardcoda_a_versao() -> None:
    codigo = _texto("pages/home.py")

    assert "VERSAO_SISTEMA = VERSAO_PORTAL_PADRAO" in codigo
    assert not re.search(r'VERSAO_SISTEMA\s*=\s*"', codigo)


def test_docstrings_de_entrada_anunciam_a_versao_atual() -> None:
    for caminho in ("streamlit_app.py", "pages/home.py"):
        cabecalho = "\n".join(_texto(caminho).splitlines()[:12])
        assert f"Versão: {VERSAO_PORTAL_PADRAO}" in cabecalho, caminho
