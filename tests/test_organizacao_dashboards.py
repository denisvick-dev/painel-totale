"""Guarda de organização dos dashboards (v3.7.0).

A v3.7.0 organizou o portal em três frentes:

1. **navegação declarativa** — ``config/navegacao.py`` é a fonte única de
   páginas, grupos, ícones e descrições (o entrypoint só consome);
2. **layout padrão** — todo dashboard abre com ``abrir_dashboard`` (hero + chips
   de contexto + sumário), organiza o corpo em ``secao()`` e fecha com
   ``fechar_dashboard``;
3. **camada compartilhada** — leitura da base da sessão, lista de ativos,
   exportação e normalização de texto vivem em ``services/``, não copiadas em
   cada página.

Estes testes impedem o retorno do padrão antigo:

* nenhuma página de ``pages/`` fica fora (ou duplicada) do mapa de navegação;
* ícone e título são únicos — ``⚡``/``📉`` repetidos faziam o menu parecer um bloco só;
* os dashboards padronizados usam a camada compartilhada e não reimplementam
  ``gerar_excel``/``ler_arquivo``/``render_hero`` nem chamam ``st.metric``;
* o entrypoint não volta a declarar ``st.Page`` na mão.

    pytest tests/test_organizacao_dashboards.py
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from config.navegacao import (
    DASHBOARDS_PADRONIZADOS,
    DESCRICAO_GRUPOS,
    GRUPOS,
    MODULOS_DE_APOIO,
    PAGINAS,
    grupos_ordenados,
    mapa_de_paginas,
    pagina_por_arquivo,
    paginas_do_grupo,
)

RAIZ = Path(__file__).resolve().parents[1]
PASTA_PAGINAS = RAIZ / "pages"

#: Funções que precisam vir da camada compartilhada (não podem ser redefinidas).
FUNCOES_DUPILCADAS_PROIBIDAS = {
    "gerar_excel",
    "gerar_excel_por_equipe",
    "ler_arquivo",
    "buscar_google_sheets",
    "buscar_hierarquia_gsheets",
    "buscar_gsheets",
    "carregar_hierarquia",
    "normalizar_login",
    "normalizar_texto",
    "remover_acentos",
    "html_safe",
    "escapar_html",
    "fmt_int",
    "fmt_int_br",
    "_fmt_int",
}

#: Componentes de interface que já existem no Design System.
COMPONENTES_PROIBIDOS = {
    "render_hero",
    "render_kpi",
    "render_kpi_sm",
    "render_insight",
    "render_section",
    "render_section_header",
    "secao",
    "injetar_css",
}


def _codigo(nome: str) -> str:
    caminho = PASTA_PAGINAS / nome
    assert caminho.is_file(), f"Página não encontrada: {caminho}"
    return caminho.read_text(encoding="utf-8")


def _arvore(nome: str) -> ast.AST:
    return ast.parse(_codigo(nome))


def _modulos_importados(nome: str) -> set[str]:
    """Módulos importados pela página (``from x.y import z`` → ``x.y``)."""
    importados: set[str] = set()
    for no in ast.walk(_arvore(nome)):
        if isinstance(no, ast.Import):
            importados.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
    return importados


def _funcoes_definidas(nome: str) -> set[str]:
    """Nomes de funções definidas no topo do arquivo (helpers locais)."""
    return {
        no.name
        for no in _arvore(nome).body  # type: ignore[attr-defined]
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _chamadas(nome: str) -> list[tuple[str, int]]:
    """``(função, linha)`` de chamadas diretas ``st.x(...)`` e de componentes."""
    saida: list[tuple[str, int]] = []
    for no in ast.walk(_arvore(nome)):
        if not isinstance(no, ast.Call):
            continue
        funcao = no.func
        if isinstance(funcao, ast.Attribute):
            base = funcao.value
            if isinstance(base, ast.Name):
                saida.append((f"{base.id}.{funcao.attr}", no.lineno))
            else:
                saida.append((funcao.attr, no.lineno))
        elif isinstance(funcao, ast.Name):
            saida.append((funcao.id, no.lineno))
    return saida


# ====================================================
# 🧭 BLOCO 1: MAPA DE NAVEGAÇÃO
# ====================================================
def test_toda_pagina_do_portal_esta_no_mapa_uma_vez() -> None:
    """``pages/*.py`` ou é painel do menu ou é módulo de apoio declarado."""
    arquivos = sorted(c.name for c in PASTA_PAGINAS.glob("*.py") if c.name != "__init__.py")
    no_menu = [p.arquivo for p in PAGINAS]

    assert len(no_menu) == len(set(no_menu)), "Há página duplicada no mapa de navegação."
    fora = [a for a in arquivos if a not in no_menu and a not in MODULOS_DE_APOIO]
    inexistentes = [a for a in no_menu if a not in arquivos]

    assert not fora, (
        "Páginas fora do mapa de navegação (adicione em config/navegacao.py ou "
        f"declare como módulo de apoio): {fora}"
    )
    assert not inexistentes, f"O mapa cita páginas que não existem: {inexistentes}"
    assert MODULOS_DE_APOIO, "Módulos de apoio precisam estar documentados no mapa."


def test_existe_uma_unica_pagina_padrao_do_portal() -> None:
    padrao = [p for p in PAGINAS if p.padrao]
    assert len(padrao) == 1, f"Exatamente uma página deve ser a default: {padrao}"
    assert padrao[0].arquivo == "home.py"


def test_icones_e_titulos_sao_unicos() -> None:
    """Ícone repetido em itens vizinhos faz o menu parecer um bloco só."""
    icones = [p.icone for p in PAGINAS]
    titulos = [p.titulo for p in PAGINAS]
    assert len(set(icones)) == len(icones), f"Ícones repetidos: {icones}"
    assert len(set(titulos)) == len(titulos), f"Títulos repetidos: {titulos}"


def test_toda_pagina_tem_descricao_e_grupo_valido() -> None:
    sem_descricao = [p.arquivo for p in PAGINAS if not p.descricao.strip()]
    grupo_invalido = [p.arquivo for p in PAGINAS if p.grupo not in GRUPOS]
    assert not sem_descricao, f"Páginas sem descrição de uma linha: {sem_descricao}"
    assert not grupo_invalido, f"Páginas em grupo inexistente: {grupo_invalido}"


def test_mapa_de_navegacao_cobre_todos_os_grupos_com_paginas() -> None:
    """As seções cobrem todas as páginas, na ordem declarada, sem grupo vazio."""
    grupos_com_pagina = [grupo for grupo in GRUPOS if paginas_do_grupo(grupo)]
    assert grupos_com_pagina == grupos_ordenados()

    cobertas = [p.arquivo for grupo in grupos_ordenados() for p in paginas_do_grupo(grupo)]
    assert cobertas == [p.arquivo for p in PAGINAS], "A ordem do mapa difere de PAGINAS."
    assert len(cobertas) == len(set(cobertas))

    for grupo in grupos_ordenados():
        assert paginas_do_grupo(grupo), f"Grupo '{grupo}' declarado sem páginas."
        assert grupo in DESCRICAO_GRUPOS, f"Grupo '{grupo}' sem descrição."


def test_mapa_de_paginas_exige_runtime_do_streamlit() -> None:
    """``st.Page`` só resolve caminhos dentro do runtime.

    A montagem real do menu é coberta por ``tests/test_app_shell.py`` (que roda o
    entrypoint no ``AppTest``); aqui garantimos apenas que fora do runtime o
    mapa não devolve um menu pela metade em silêncio.
    """
    with pytest.raises(Exception):
        mapa_de_paginas()


def test_ordem_dos_grupos_e_do_portal() -> None:
    """Visão geral → performance → campo → SLA → cadastros → utilitários."""
    assert grupos_ordenados() == [g for g in GRUPOS if paginas_do_grupo(g)]
    assert grupos_ordenados()[0] == "Visão Geral"
    assert grupos_ordenados()[-1] == "Utilitários"


def test_consultores_do_mapa_funcionam() -> None:
    assert pagina_por_arquivo("pontos.py").titulo == "Produção Mensal"
    assert pagina_por_arquivo("pages/quebra_geral.py").grupo == "SLA & Quebra"
    assert pagina_por_arquivo("inexistente.py") is None
    assert [p.arquivo for p in paginas_do_grupo("SLA & Quebra")] == [
        "quebra_geral.py",
        "quebra_unificada.py",
    ]


def test_entrypoint_nao_declara_paginas_na_mao() -> None:
    """O menu é dado: ``streamlit_app.py`` só consome ``config.navegacao``."""
    codigo = (RAIZ / "streamlit_app.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo)
    chamadas_page = [
        no.lineno
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and isinstance(no.func.value, ast.Name)
        and no.func.value.id == "st"
        and no.func.attr == "Page"
    ]
    assert not chamadas_page, (
        f"st.Page() no entrypoint (linhas {chamadas_page}): declare em config/navegacao.py."
    )
    assert "mapa_de_navegacao" in codigo


# ====================================================
# 🧱 BLOCO 2: PADRÃO DE LAYOUT DAS PÁGINAS
# ====================================================
def test_dashboards_padronizados_estao_no_menu() -> None:
    fora = [a for a in DASHBOARDS_PADRONIZADOS if pagina_por_arquivo(a) is None]
    assert not fora, f"Dashboards padronizados fora do mapa: {fora}"


@pytest.mark.parametrize("pagina", DASHBOARDS_PADRONIZADOS)
def test_dashboard_usa_esqueleto_padrao(pagina: str) -> None:
    """Abre com contexto/sumário, organiza em seções e fecha com rodapé único."""
    if pagina == "home.py":
        pytest.skip("A Home já usa os primitivos de layout_pagina diretamente.")
    codigo = _codigo(pagina)
    assert "abrir_dashboard(" in codigo, f"{pagina} não abre com abrir_dashboard()."
    assert "fechar_dashboard(" in codigo, f"{pagina} não fecha com fechar_dashboard()."
    tem_secoes = "secao(" in codigo or "cabecalho_secao(" in codigo
    assert tem_secoes, (
        f"{pagina} não organiza o corpo em seções ancoradas "
        "(use secao() ou cabecalho_secao() de components.layout_pagina)."
    )


@pytest.mark.parametrize("pagina", DASHBOARDS_PADRONIZADOS)
def test_dashboard_usa_camada_de_dados_compartilhada(pagina: str) -> None:
    """A base vem de ``services.dados_sessao`` — nunca de um bloco copiado."""
    if pagina in {"visao_geral.py"}:
        pytest.skip("O índice não consome a base de produção.")
    importados = _modulos_importados(pagina)
    assert any(m.startswith("services.dados_sessao") for m in importados), (
        f"{pagina} não importa services.dados_sessao (guarda de entrada padrão)."
    )


@pytest.mark.parametrize("pagina", DASHBOARDS_PADRONIZADOS)
def test_dashboard_nao_reimplementa_helpers_compartilhados(pagina: str) -> None:
    """Exportação, leitura de upload, hierarquia e texto vêm dos serviços."""
    definidas = _funcoes_definidas(pagina)
    ofensas = sorted(definidas & FUNCOES_DUPILCADAS_PROIBIDAS)
    assert not ofensas, (
        f"{pagina} redefine helpers que vivem em services/: {ofensas} "
        "(use services.planilhas, services.hierarquia e services.texto)."
    )


@pytest.mark.parametrize("pagina", DASHBOARDS_PADRONIZADOS)
def test_dashboard_nao_reimplementa_componentes_de_interface(pagina: str) -> None:
    """Herói, KPI, insight e seção são do Design System, não da página."""
    definidas = _funcoes_definidas(pagina)
    ofensas = sorted(definidas & COMPONENTES_PROIBIDOS)
    assert not ofensas, (
        f"{pagina} redefine componentes do Design System: {ofensas} "
        "(importe de components.componentes / components.layout_pagina)."
    )


@pytest.mark.parametrize("pagina", DASHBOARDS_PADRONIZADOS)
def test_dashboard_nao_usa_st_metric(pagina: str) -> None:
    """``st.metric`` está banido do portal (ver DESIGN_SYSTEM.md, seção 1)."""
    ofensas = [linha for nome, linha in _chamadas(pagina) if nome == "st.metric"]
    assert not ofensas, f"{pagina} usa st.metric nas linhas {ofensas}."


def test_exportacao_usa_servico_unico() -> None:
    """``services.planilhas`` é a fonte do XLSX; o kit apenas delega."""
    codigo_kit = (RAIZ / "components" / "dashboard_kit.py").read_text(encoding="utf-8")
    assert "services.planilhas" in codigo_kit
    assert "def _excel_xlsxwriter" not in codigo_kit


def test_pagina_visao_geral_existe_e_usa_o_mapa() -> None:
    """O índice de painéis lê ``config.navegacao`` (nada de lista à mão)."""
    codigo = _codigo("visao_geral.py")
    assert "config.navegacao" in codigo
    assert "grupos_ordenados" in codigo
    assert "paginas_do_grupo" in codigo
