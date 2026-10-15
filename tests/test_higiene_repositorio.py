"""Guarda de higiene do repositório.

Contexto (limpeza de 2026-10-12): a árvore carregava artefatos sem uso — um CSV de PIB
do Banco Mundial (264 KB, nenhuma referência no código), cinco ícones órfãos em
`assets/icons/`, um `.secrets.baseline` vazio e em UTF-16 gerado no Windows para uma
ferramenta que o projeto não usa, um `.github/CODEOWNERS` de template apontando para
`@streamlit/community-cloud` e um caminho absoluto de máquina no `.vscode/settings.json`.
O README ainda documentava um diretório `old/` que não existe.

Estes testes impedem que o lixo volte:

* nenhum arquivo de sistema operacional/editor versionado;
* todo asset versionado precisa ser citado por algum arquivo do repositório — um ícone
  sem referência é peso morto (ou sintoma de código removido pela metade);
* nenhuma configuração versionada pode conter caminho absoluto de máquina;
* nada de arquivos UTF-16 (BOM) na árvore, que quebram diff, lint e leitura no Linux;
* nenhum diretório vazio (o Git não versiona diretórios, então diretório vazio = sobra);
* baseline de segredos só existe se a ferramenta estiver realmente ligada no projeto;
* a árvore publicada no README precisa corresponder aos diretórios reais.

    python tests/test_higiene_repositorio.py     # execução direta (stdlib)
    pytest tests/test_higiene_repositorio.py     # via pytest
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

IGNORADOS = {
    ".git",
    "__pycache__",
    ".venv",
    ".venv-check",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "build",
    "dist",
    "node_modules",
}

# Diretórios cujo conteúdo é asset binário: todo arquivo precisa de referência no código.
DIRETORIOS_DE_ASSETS = ("assets", "fonts", ".streamlit_cache", "data")

# Lixo de sistema operacional e de editores que nunca deve entrar no repositório.
LIXO_DE_SO = {".DS_Store", "Thumbs.db", "desktop.ini", ".directory", ".localized"}
SUFIXOS_DE_LIXO = (".pyc", ".pyo", ".orig", ".rej", ".bak", ".swp", ".swo", ".tmp", "~")

# Caminhos absolutos de máquina. O `[\\/]+` cobre de propósito o caso do JSON, onde a
# barra invertida vem escapada e multiplicada (`C:\\\\Users\\\\denis\\\\...`) — foi assim que
# o `.vscode/settings.json` carregava o caminho da máquina antes da limpeza.
PADROES_DE_CAMINHO_DE_MAQUINA = (
    re.compile(r"[A-Za-z]:[\\/]+(?:Users|Documents and Settings|AppData)[\\/]", re.IGNORECASE),
    re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/"),
)

# Arquivos de configuração versionados (código Python pode citar fontes do sistema).
SUFIXOS_DE_CONFIG = (".json", ".toml", ".yml", ".yaml", ".ini", ".cfg")
NOMES_DE_CONFIG = {"CODEOWNERS", ".editorconfig", ".gitattributes"}


def _arquivos(ignorar_ocultos: bool = False) -> list[Path]:
    """Arquivos do repositório, sem os diretórios de ambiente/cache."""
    arquivos = (
        caminho
        for caminho in RAIZ.rglob("*")
        if caminho.is_file()
        and not any(parte in IGNORADOS for parte in caminho.relative_to(RAIZ).parts)
    )
    if ignorar_ocultos:
        return sorted(caminho for caminho in arquivos if not caminho.name.startswith("."))
    return sorted(arquivos)


def _texto(caminho: Path) -> str | None:
    """Conteúdo do arquivo se for texto legível; ``None`` para binários."""
    try:
        return caminho.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _arquivos_de_config() -> list[Path]:
    return [
        caminho
        for caminho in _arquivos()
        if caminho.suffix.lower() in SUFIXOS_DE_CONFIG or caminho.name in NOMES_DE_CONFIG
    ]


def test_sem_lixo_de_sistema_operacional() -> None:
    """Nenhum arquivo de SO/editor versionado (`.DS_Store`, `Thumbs.db`, `*.pyc`...)."""
    ofensas = [
        str(caminho.relative_to(RAIZ))
        for caminho in _arquivos()
        if caminho.name in LIXO_DE_SO
        or (caminho.suffix.lower() in SUFIXOS_DE_LIXO and not caminho.name.endswith("~"))
        or caminho.name.endswith("~")
        or caminho.suffix == ".pyc"
    ]
    assert not ofensas, (
        "Lixo de sistema operacional/editor versionado — remova e mantenha o "
        ".gitignore atualizado:\n  " + "\n  ".join(sorted(ofensas))
    )


def test_todo_asset_versionado_tem_referencia() -> None:
    """Ícone/imagem/fonte/cache sem nenhuma referência é peso morto no repositório."""
    textos: dict[Path, str] = {}
    for caminho in _arquivos():
        conteudo = _texto(caminho)
        if conteudo is not None:
            textos[caminho] = conteudo

    orfaos: list[str] = []
    for diretorio in DIRETORIOS_DE_ASSETS:
        base = RAIZ / diretorio
        if not base.is_dir():
            continue
        for asset in sorted(base.rglob("*")):
            if not asset.is_file():
                continue
            citado = any(
                asset.name in conteudo for outro, conteudo in textos.items() if outro != asset
            )
            if not citado:
                orfaos.append(f"{asset.relative_to(RAIZ)} (nenhuma referência)")

    assert not orfaos, (
        "Assets sem referência no código/docs — remova-os ou registre o uso:\n  "
        + "\n  ".join(orfaos)
    )


def test_sem_diretorios_vazios() -> None:
    """Diretório vazio é sobra de arquivo removido (o Git não versiona diretórios)."""
    vazios: list[str] = []
    for caminho in RAIZ.rglob("*"):
        if not caminho.is_dir():
            continue
        partes = caminho.relative_to(RAIZ).parts
        if any(parte in IGNORADOS for parte in partes):
            continue
        if not any(filho.is_file() for filho in caminho.rglob("*")):
            # Reporta apenas o diretório mais alto da sobra.
            if not any(
                (RAIZ / parent).is_dir()
                and not any(f.is_file() for f in (RAIZ / parent).rglob("*"))
                for parent in (Path(*partes[:i]) for i in range(1, len(partes)))
                if parent.parts
            ):
                vazios.append(str(caminho.relative_to(RAIZ)))
    assert not vazios, "Diretórios vazios na árvore (remova-os):\n  " + "\n  ".join(sorted(vazios))


def test_config_versionada_sem_caminho_de_maquina() -> None:
    """Configuração versionada não pode carregar caminho absoluto de uma máquina."""
    ofensas: list[str] = []
    for caminho in _arquivos_de_config():
        conteudo = _texto(caminho)
        if conteudo is None:
            continue
        for numero, linha in enumerate(conteudo.splitlines(), start=1):
            if any(padrao.search(linha) for padrao in PADROES_DE_CAMINHO_DE_MAQUINA):
                ofensas.append(f"{caminho.relative_to(RAIZ)}:{numero}")
    assert not ofensas, (
        "Configuração versionada com caminho absoluto de máquina — use caminho "
        "relativo ou variável de ambiente:\n  " + "\n  ".join(ofensas)
    )


def test_sem_arquivos_em_utf16() -> None:
    """Arquivo em UTF-16 (BOM) quebra diff, lint e leitura no Linux/CI."""
    ofensas: list[str] = []
    for caminho in _arquivos():
        try:
            inicio = caminho.open("rb").read(2)
        except OSError:
            continue
        if inicio in (b"\xff\xfe", b"\xfe\xff"):
            ofensas.append(str(caminho.relative_to(RAIZ)))
    assert not ofensas, "Arquivos em UTF-16 (BOM) — salve em UTF-8:\n  " + "\n  ".join(
        sorted(ofensas)
    )


def test_baseline_de_segredos_exige_ferramenta_ligada() -> None:
    """Baseline do `detect-secrets` só faz sentido se a ferramenta estiver no projeto."""
    baseline = RAIZ / ".secrets.baseline"
    if not baseline.exists():
        return

    fontes = [
        *RAIZ.glob("requirements*.txt"),
        *(RAIZ / ".github" / "workflows").glob("*.y*ml"),
        RAIZ / ".pre-commit-config.yaml",
    ]
    ligada = any(
        "detect-secrets" in texto
        for caminho in fontes
        if caminho.is_file() and (texto := _texto(caminho))
    )
    assert ligada, (
        ".secrets.baseline presente sem `detect-secrets` em requirements/CI/pre-commit. "
        "Ligue a ferramenta ou remova o baseline (é sobra de uma execução local)."
    )


def _entradas_da_arvore_do_readme() -> list[tuple[int, str]]:
    """Extrai (profundidade, caminho) do bloco de estrutura do README."""
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    marcador = "## 📁 Estrutura do Projeto"
    assert marcador in texto, "README sem a seção de estrutura do projeto."
    bloco = re.search(r"```\n(.*?)```", texto.split(marcador, 1)[1], re.DOTALL)
    assert bloco, "README sem bloco de código com a árvore de arquivos."

    linhas = [linha for linha in bloco.group(1).splitlines() if linha.strip()]
    entradas: list[tuple[int, str]] = []
    for linha in linhas[1:]:  # primeira linha é o nome do projeto
        posicao = min((linha.index(g) for g in ("├", "└") if g in linha), default=-1)
        if posicao < 0:
            continue
        nome = linha[posicao:].lstrip("├└─ ").split("#", 1)[0].strip().rstrip("/")
        if nome:
            entradas.append((posicao // 4, nome))
    return entradas


def test_arvore_do_readme_corresponde_ao_repositorio() -> None:
    """Cada entrada da árvore do README precisa existir de verdade no repositório."""
    pilha: list[str] = []
    inexistentes: list[str] = []
    for profundidade, nome in _entradas_da_arvore_do_readme():
        while len(pilha) > profundidade:
            pilha.pop()
        relativo = Path(*pilha, nome) if pilha else Path(nome)
        if not (RAIZ / relativo).exists():
            inexistentes.append(str(relativo))
        pilha.append(nome)

    assert not inexistentes, (
        "README documenta caminhos que não existem na árvore — atualize a seção "
        "de estrutura:\n  " + "\n  ".join(inexistentes)
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
        except Exception as exc:  # noqa: BLE001 - runner de linha de comando
            falhas += 1
            print(f"FALHOU  {teste.__name__}: {exc}")
        else:
            print(f"OK      {teste.__name__}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram.")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(_main())
