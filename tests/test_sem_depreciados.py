"""Guarda contra argumentos depreciados do Streamlit.

`use_container_width` foi depreciado (remoção prevista após 2025-12-31) em favor
de `width="stretch"` / `width="content"`. A migração (103 chamadas em 19
arquivos) foi feita em 2026-10-05 e o piso de versão do projeto subiu para
`streamlit>=1.67` — release com `width` em todos os elementos usados e com
`dataframeHeaderTextColor` para o cabeçalho escuro dos dataframes
(st.plotly_chart, st.altair_chart, st.button, st.download_button,
st.form_submit_button, st.page_link, st.dataframe, st.image).

Estes testes evitam que o argumento antigo volte a entrar no código:

    python tests/test_sem_depreciados.py      # execução direta (stdlib)
    pytest tests/test_sem_depreciados.py      # via pytest
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

IGNORADOS = {"old", "__pycache__", ".venv", ".venv-check", ".git", "painel-totale"}

# Piso mínimo exigido do Streamlit (espelhado em requirements.txt).
PISO_STREAMLIT = (1, 67)


def _arquivos_do_app() -> list[Path]:
    return sorted(
        caminho
        for caminho in RAIZ.rglob("*.py")
        if not any(parte in IGNORADOS for parte in caminho.relative_to(RAIZ).parts)
    )


def test_sem_use_container_width() -> None:
    """Nenhuma chamada pode usar o argumento depreciado."""
    ofensas: list[str] = []
    for caminho in _arquivos_do_app():
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call) and any(
                kw.arg == "use_container_width" for kw in no.keywords
            ):
                ofensas.append(f"{caminho.relative_to(RAIZ)}:{no.lineno}")

    assert not ofensas, (
        'use_container_width foi depreciado; use width="stretch" '
        '(ou width="content" para False):\n  ' + "\n  ".join(ofensas)
    )


def test_piso_de_versao_no_requirements() -> None:
    """requirements.txt precisa exigir uma versão que suporte width="stretch"."""
    texto = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    linha = next(
        (ln for ln in texto.splitlines() if ln.strip().startswith("streamlit")),
        "",
    )
    assert linha, "requirements.txt não declara o Streamlit."
    match = re.search(r">=\s*(\d+)\.(\d+)", linha)
    assert match, (
        f"Sem piso de versão em {linha.strip()!r}: versões antigas não têm "
        'width="stretch" e quebrariam com TypeError.'
    )
    assert tuple(int(p) for p in match.groups()) >= PISO_STREAMLIT, (
        f"Piso {match.group(0)} abaixo do necessário ({'.'.join(map(str, PISO_STREAMLIT))})."
    )


def test_streamlit_instalado_suporta_width() -> None:
    """O Streamlit instalado precisa aceitar width nos elementos usados."""
    import inspect

    import streamlit as st

    elementos = [
        "plotly_chart",
        "altair_chart",
        "button",
        "download_button",
        "form_submit_button",
        "page_link",
        "dataframe",
        "image",
    ]
    sem_suporte = [
        nome
        for nome in elementos
        if nome in inspect.signature(getattr(st, nome)).parameters
        and "width" not in inspect.signature(getattr(st, nome)).parameters
    ]
    assert not sem_suporte, (
        f"Streamlit {st.__version__} não aceita width em: {', '.join(sem_suporte)}. "
        "Atualize o ambiente (requirements.txt)."
    )


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
