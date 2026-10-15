"""Guarda de sintaxe — todo script do app precisa compilar no Python do projeto.

Contexto (corrigido em 2026-10-05): `pages/quebra_geral.py` usava aspas duplas
aninhadas dentro de f-string, sintaxe válida apenas a partir do **Python 3.12**
(PEP 701) e inválida no 3.11 — a versão fixada pelo projeto no
`.devcontainer/devcontainer.json` (`python:1-3.11-bullseye`). Resultado: a página
(o entrypoint e o `pages/quebra_unificada.py`, que a importam) não abria.

Este teste compila todos os módulos com o interpretador atual e falha apontando
arquivo + linha de qualquer `SyntaxError`, evitando que uma sintaxe nova demais
volte a entrar sem ser percebida.

Execução:

    python tests/test_sintaxe.py        # execução direta (stdlib)
    pytest tests/test_sintaxe.py        # via pytest
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# O CI executa este arquivo direto (`python tests/test_sintaxe.py`), sem o
# rootdir no `sys.path` que o pytest adiciona automaticamente. Como dois guardas
# importam `config.navegacao`/`config.settings`, a raiz precisa estar no caminho
# nos dois modos de execução.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Diretórios ignorados: `old/` guarda scripts legados que não fazem parte do app.
IGNORADOS = {"old", "__pycache__", ".venv", ".git", "build", "dist"}


def _arquivos_python() -> list[Path]:
    return sorted(
        caminho
        for caminho in RAIZ.rglob("*.py")
        if not any(parte in IGNORADOS for parte in caminho.relative_to(RAIZ).parts)
    )


def _erro_de_sintaxe(caminho: Path) -> str | None:
    """Compila o arquivo e devolve a descrição do erro, se houver."""
    try:
        compile(caminho.read_text(encoding="utf-8"), str(caminho), "exec")
    except SyntaxError as exc:
        return f"{caminho.relative_to(RAIZ)}:{exc.lineno} -> {exc.msg}"
    return None


def test_sem_marcadores_de_conflito() -> None:
    """Nenhum arquivo Python deve conter marcadores de merge não resolvidos."""
    padrao = re.compile(r"^(?:<{7}|={7}|>{7}|\|{7})(?:\s|$)")
    problemas: list[str] = []

    for caminho in sorted(RAIZ.rglob("*.py")):
        if any(parte in IGNORADOS for parte in caminho.relative_to(RAIZ).parts):
            continue
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), start=1):
            if padrao.match(linha):
                problemas.append(f"{caminho.relative_to(RAIZ)}:{numero}: {linha.strip()}")

    assert not problemas, "Marcadores de conflito de merge encontrados:\n  " + "\n  ".join(
        problemas
    )


def test_paginas_navegacao_existem() -> None:
    """Toda página do mapa de navegação deve apontar para um arquivo existente.

    Desde a v3.7.0 o menu é dado (``config/navegacao.py``), não código no
    entrypoint: o teste lê ``PAGINAS`` e confere cada ``caminho``.
    """
    from config.navegacao import PAGINAS

    assert PAGINAS, "Nenhuma página foi registrada em config/navegacao.py."
    faltantes = [p.caminho for p in PAGINAS if not (RAIZ / p.caminho).is_file()]
    assert not faltantes, "Páginas registradas inexistentes: " + ", ".join(faltantes)

    padrao = [p for p in PAGINAS if p.padrao]
    assert len(padrao) == 1, f"O menu precisa de exatamente uma página default: {padrao}"

    codigo_app = (RAIZ / "streamlit_app.py").read_text(encoding="utf-8")
    assert "mapa_de_navegacao" in codigo_app, (
        "O entrypoint deve montar o menu a partir de config.navegacao."
    )


def test_icone_do_app_existe() -> None:
    """O ícone do portal precisa ser um asset versionado (fonte única em config)."""
    from config.settings import ICON_PATH_PORTAL

    assert ICON_PATH_PORTAL, "config.settings precisa declarar ICON_PATH_PORTAL."
    assert (RAIZ / ICON_PATH_PORTAL).is_file(), (
        f"O ícone configurado não existe: {ICON_PATH_PORTAL}"
    )

    codigo_app = (RAIZ / "streamlit_app.py").read_text(encoding="utf-8")
    assert "ICON_PATH_PORTAL" in codigo_app, (
        "O entrypoint deve ler o ícone de config.settings (sem caminho hardcode)."
    )


def test_exemplo_de_secrets_e_seguro_e_valido() -> None:
    """O modelo de secrets deve ser TOML válido e não ativar uma senha padrão."""
    caminho = RAIZ / ".streamlit" / "secrets.example.toml"
    config = tomllib.loads(caminho.read_text(encoding="utf-8"))

    assert config["usuarios"]["admin"]["senha"] == ""
    for pagina in ("gestao_ativos.py", "login.py"):
        codigo = (RAIZ / "pages" / pagina).read_text(encoding="utf-8")
        assert "admin123" not in codigo, f"Senha padrão insegura encontrada em {pagina}."


def test_todos_modulos_compilam() -> None:
    """Nenhum módulo do app pode ter erro de sintaxe no interpretador atual."""
    arquivos = _arquivos_python()
    assert arquivos, "Nenhum arquivo .py encontrado — verifique o caminho da raiz."

    problemas = [erro for caminho in arquivos if (erro := _erro_de_sintaxe(caminho))]

    detalhe = (
        "\nSintaxe incompatível com o Python do projeto "
        f"({sys.version.split()[0]}) — ex.: PEP 701 (f-strings) exige 3.12+:\n  "
    )
    assert not problemas, detalhe + "\n  ".join(problemas)


def test_quebra_geral_compila() -> None:
    """Regressão específica do bug de f-string com aspas aninhadas."""
    erro = _erro_de_sintaxe(RAIZ / "pages" / "quebra_geral.py")
    assert erro is None, f"pages/quebra_geral.py não compila: {erro}"


def _main() -> int:
    testes = [
        valor
        for nome, valor in sorted(globals().items())
        if nome.startswith("test_") and callable(valor)
    ]
    falhas = 0
    for teste in testes:
        try:
            teste()
        except Exception as exc:
            falhas += 1
            print(f"FALHOU  {teste.__name__}: {exc}")
        else:
            print(f"OK      {teste.__name__}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram.")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(_main())
