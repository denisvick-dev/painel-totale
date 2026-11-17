"""O fluxo direto não pode voltar a depender da importação para outra aba."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_assistente_de_importacao_obsoleto_foi_removido():
    assert not (RAIZ / "components/importacao_presenca.py").exists()
    assert not (RAIZ / "services/importacao_presenca.py").exists()


def test_pagina_utiliza_grade_direta_sem_importador_legado():
    codigo = (RAIZ / "pages/absenteismo.py").read_text()
    imports = [no.module for no in ast.walk(ast.parse(codigo)) if isinstance(no, ast.ImportFrom)]
    assert "services.presenca_grade" in imports
    assert not any("importacao_presenca" in (nome or "") for nome in imports)
