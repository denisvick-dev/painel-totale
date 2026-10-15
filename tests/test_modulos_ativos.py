"""Guarda contra módulos órfãos: testes sozinhos não são consumidores do app.

Parte do entrypoint, da CLI do robô e das páginas registradas no menu. Segue
imports locais (inclusive relativos e lazy declarados para TYPE_CHECKING),
sem executar as páginas nem acessar serviços externos.
"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

from config.navegacao import PAGINAS

RAIZ = Path(__file__).resolve().parents[1]


def _modulos_do_app() -> dict[str, Path]:
    arquivos = [RAIZ / "streamlit_app.py", RAIZ / "robo.py"]
    for pasta in ("components", "services", "config", "pages"):
        arquivos.extend((RAIZ / pasta).rglob("*.py"))
    return {
        ".".join(caminho.relative_to(RAIZ).with_suffix("").parts).removesuffix(".__init__"):
        caminho
        for caminho in arquivos
        if "__pycache__" not in caminho.parts
    }


def _importacoes_locais(
    modulo: str, caminho: Path, modulos: dict[str, Path]
) -> set[str]:
    pacote = modulo if caminho.name == "__init__.py" else modulo.rpartition(".")[0]
    nomes: set[str] = set()
    for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            nomes.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom):
            base = no.module or ""
            if no.level:
                base = resolve_name("." * no.level + base, pacote)
            nomes.add(base)
            nomes.update(f"{base}.{alias.name}" for alias in no.names)

    # Importar x.y também inicializa o pacote x (__init__.py).
    dependencias: set[str] = set()
    for nome in nomes:
        partes = nome.split(".")
        for quantidade in range(1, len(partes) + 1):
            candidato = ".".join(partes[:quantidade])
            if candidato in modulos:
                dependencias.add(candidato)
    return dependencias


def test_todo_modulo_tem_ligacao_com_uma_entrada_do_app() -> None:
    modulos = _modulos_do_app()
    pendentes = {"streamlit_app", "robo"}
    pendentes.update(f"pages.{Path(p.arquivo).stem}" for p in PAGINAS)
    visitados: set[str] = set()
    while pendentes:
        modulo = pendentes.pop()
        if modulo in visitados:
            continue
        assert modulo in modulos, f"Entrada inexistente: {modulo}"
        visitados.add(modulo)
        pendentes.update(
            _importacoes_locais(modulo, modulos[modulo], modulos) - visitados
        )

    orfaos = sorted(set(modulos) - visitados)
    assert not orfaos, (
        "Módulos sem ligação com o app/CLI (uso apenas em testes não conta): "
        + ", ".join(orfaos)
        + ". Remova ou conecte ao fluxo real; novas entradas dinâmicas devem ser "
        "declaradas neste guarda."
    )


def test_importacoes_apontam_para_arquivos_locais_existentes() -> None:
    modulos = _modulos_do_app()
    for modulo, caminho in modulos.items():
        pacote = modulo if caminho.name == "__init__.py" else modulo.rpartition(".")[0]
        for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Import):
                nomes = [alias.name for alias in no.names]
            elif isinstance(no, ast.ImportFrom):
                base = no.module or ""
                if no.level:
                    base = resolve_name("." * no.level + base, pacote)
                nomes = [base]
            else:
                continue
            for nome in nomes:
                if nome.split(".")[0] in {"components", "services", "config", "pages"}:
                    assert nome in modulos, f"{caminho.relative_to(RAIZ)}: import órfão {nome}"
