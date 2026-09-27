"""
Integridade das páginas do portal (compilação + execução).

Cobre a regressão que quebrou o menu "Quebra": f-strings com aspas duplas
aninhadas (PEP 701) só existem a partir do Python 3.12, e o projeto declara
3.11 — o arquivo não compilava e derrubava duas páginas. O primeiro teste
abaixo pega esse tipo de erro em qualquer arquivo, em segundos.

Executar: pytest tests/test_paginas.py -v
"""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PAGINAS = sorted(glob.glob(str(RAIZ / "pages" / "*.py")))
ARQUIVOS = PAGINAS + [str(RAIZ / "streamlit_app.py")] + [
    *(glob.glob(str(RAIZ / "components" / "*.py"))),
    *(glob.glob(str(RAIZ / "robo" / "*.py"))),
]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Compilação (barato e pega erro fatal de sintaxe)
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda a: os.path.relpath(a, RAIZ))
def test_arquivos_compilam(arquivo):
    compile(Path(arquivo).read_text(encoding="utf-8"), arquivo, "exec")


def test_python_do_projeto_e_311():
    """O alvo é 3.11: sintaxe exclusiva de 3.12+ (PEP 701) não é válida."""
    assert sys.version_info[:2] == (3, 11), (
        f"rodando em {sys.version_info[:2]}; o projeto é Python 3.11"
    )


def test_nenhuma_sintaxe_de_python_312():
    """Detecta f-string com a mesma aspa aninhada (PEP 701) sem depender da versão."""
    import re

    padrao = re.compile(r'f"[^"\n]*\{[^}\n]*"[^}\n]*\}')
    for arquivo in ARQUIVOS:
        fonte = Path(arquivo).read_text(encoding="utf-8")
        for numero, linha in enumerate(fonte.splitlines(), start=1):
            if linha.lstrip().startswith("#"):
                continue
            if padrao.search(linha) and linha.count('"') >= 4:
                # casos aceitos: aspas simples internas
                if re.search(r'f"[^"\n]*\{[^}\n]*""', linha):
                    pytest.fail(
                        f"{os.path.relpath(arquivo, RAIZ)}:{numero} usa PEP 701 "
                        f"(inválido no Python 3.11): {linha.strip()[:120]}"
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Execução das páginas (AppTest)
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def apptest():
    from streamlit.testing.v1 import AppTest

    def _rodar(caminho: str):
        at = AppTest.from_file(str(RAIZ / caminho), default_timeout=90)
        at.run()
        return at

    return _rodar


def _excecoes(at) -> list[str]:
    return [str(e.value).replace("\n", " | ")[:200] for e in at.exception]


@pytest.mark.parametrize("pagina", PAGINAS, ids=lambda p: os.path.basename(p))
def test_pagina_executa_sem_excecao(apptest, pagina):
    at = apptest(os.path.relpath(pagina, RAIZ))
    erros = _excecoes(at)
    # dashboard_meta depende de rede/segredos; falha de dados não é erro de código
    assert not erros, erros


def test_portal_sobe(apptest):
    at = apptest("streamlit_app.py")
    assert not _excecoes(at)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Higiene do repositório
# ═══════════════════════════════════════════════════════════════════════════════
def test_sem_credenciais_hardcoded():
    for arquivo in ARQUIVOS:
        fonte = Path(arquivo).read_text(encoding="utf-8")
        assert "admin123" not in fonte, f"{arquivo} contém senha fixa"


def test_arquivos_de_segredo_ignorados():
    fonte = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert ".streamlit/secrets.toml" in fonte
    assert "usuarios.db" in fonte
    assert ".streamlit_cache/" in fonte


def test_codigo_morto_removido():
    """pages/home.py e pages/login.py não eram alcançáveis com st.navigation."""
    assert not (RAIZ / "pages" / "home.py").exists()
    assert not (RAIZ / "pages" / "login.py").exists()
