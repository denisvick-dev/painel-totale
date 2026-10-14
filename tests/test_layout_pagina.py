"""Testes da camada de organização de página (``components.layout_pagina``).

Cobrem o item "organização das informações nas páginas": ordem canônica das
seções, âncoras que casam com o sumário, barra de filtros fixa, painéis, abas,
rodapé — mais dois guardas de plataforma que evitam armadilhas do Streamlit 1.65.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import components.layout_pagina as lp  # noqa: E402


# ====================================================
# CONTRATO DO MÓDULO
# ====================================================
def test_ordem_padrao_da_pagina() -> None:
    assert lp.ORDEM_PADRAO == (
        "Cabeçalho e contexto",
        "Sumário (âncoras)",
        "Filtros",
        "KPIs",
        "Gráficos principais",
        "Detalhamento (abas/expansores)",
        "Exportação",
        "Rodapé",
    )
    assert len(set(lp.ORDEM_PADRAO)) == len(lp.ORDEM_PADRAO)


def test_ancoras_sao_estaveis_e_legiveis_na_url() -> None:
    assert lp._slug("Filtros e Período") == "totale-secao-filtros-e-periodo"
    assert lp._slug("Visão Geral") == "totale-secao-visao-geral"
    assert lp._slug("  Múltiplos   Espaços  ") == "totale-secao-multiplos-espacos"
    assert lp._slug("Ação & Reação") == "totale-secao-acao-reacao"
    assert lp._slug("100% Metas") == "totale-secao-100-metas"
    # Nunca devolve id vazio: sem texto utilizável cai no sufixo "secao".
    assert lp._slug("") == "totale-secao-secao"
    assert lp._slug("###") == "totale-secao-secao"
    assert lp._slug("Filtros").startswith(lp._PREFIXO_ANCORA)


def test_api_publica_exportada() -> None:
    assert lp.VERSAO_LAYOUT == "1.0.0"
    for nome in lp.__all__:
        assert hasattr(lp, nome), nome
    assert set(lp.__all__) >= {
        "ORDEM_PADRAO",
        "barra_filtros",
        "colunas",
        "css_layout_pagina",
        "painel",
        "render_abas",
        "render_barra_acoes",
        "render_cabecalho_pagina",
        "render_chips",
        "render_divisor",
        "render_rodape_pagina",
        "render_sumario",
        "secao",
    }


def test_css_de_layout_tem_barra_fixa_sumario_e_rodape() -> None:
    css = lp.css_layout_pagina()

    assert "position: sticky" in css
    assert f'[class*="{lp._CLASSE_FILTROS}"]' in css
    assert ".totale-sumario" in css
    assert ".totale-rodape" in css
    assert ".totale-chip" in css
    assert ".totale-secao" in css
    assert css.count("{") == css.count("}")
    assert '[data-testid="stMain"]' in css
    assert "stSidebar" not in css  # sidebar pertence a components.sidebar


# ====================================================
# RENDERIZAÇÃO (AppTest)
# ====================================================
PAGINA_MODELO = """
import streamlit as st
from components.layout_pagina import (
    barra_filtros, colunas, painel, render_abas, render_barra_acoes,
    render_cabecalho_pagina, render_chips, render_divisor,
    render_rodape_pagina, render_sumario, secao,
)

render_cabecalho_pagina(
    "Visão Geral",
    subtitulo="Contexto do portal",
    badge="PRODUÇÃO",
    icone="insights",
    chips=[("Atualizado", "12/10/2026")],
    atualizado_em="13/10/2026 08:00",
    registros=12500,
    periodo="set/2026",
)
render_sumario(["Filtros", "KPIs", "Gráficos"])
render_chips([("Total", "1.248"), ("Meta", "92%")], destaque=("Meta",), acao=("Total",))

with barra_filtros("demo", titulo="Filtros", colunas=3) as cols:
    st.session_state["n_cols"] = len(cols)
    for indice, coluna in enumerate(cols):
        coluna.selectbox("Base", ["Produção", "Consultivo"], key=f"base_{indice}")

with secao("Filtros", icone="tune", subtitulo="Recorte aplicado", badge="3 ativos"):
    st.markdown("corpo da seção")

corpo_painel = painel("Painel de saída", icone="bolt", altura=200)
with corpo_painel:
    st.write("dentro do painel")

st.session_state["n_abas"] = len(render_abas(["Um", "Dois"], chave="demo_abas"))

with render_barra_acoes():
    st.button("Exportar")

render_divisor("Detalhes")
st.session_state["n_colunas"] = len(colunas(4, proporcao=[2, 1, 1, 1]))
render_rodape_pagina(versao="3.6.0", ambiente="produção")
"""


@pytest.fixture(scope="module")
def pagina() -> AppTest:
    app = AppTest.from_string(PAGINA_MODELO, default_timeout=60).run()
    assert not list(app.exception), [str(e.value) for e in app.exception]
    return app


def _html(app: AppTest) -> str:
    return "\n".join(str(getattr(bloco, "value", "")) for bloco in app.get("html"))


def test_cabecalho_traz_titulo_contexto_e_badge(pagina: AppTest) -> None:
    html = _html(pagina)

    assert "Visão Geral" in html
    assert "Contexto do portal" in html
    assert "PRODUÇÃO" in html
    assert "totale-hero" in html
    assert "12.500" in html or "12500" in html  # registros formatados
    assert "set/2026" in html
    assert "Atualizado" in html and "12/10/2026" in html


def test_sumario_aponta_para_ancoras_reais(pagina: AppTest) -> None:
    html = _html(pagina)

    links = set(re.findall(r'href="#(totale-secao-[a-z0-9-]+)"', html))
    assert links == {
        "totale-secao-filtros",
        "totale-secao-kpis",
        "totale-secao-graficos",
    }
    # A seção renderizada existe com o mesmo id — o link não pode ser morto.
    ids = set(re.findall(r'id="(totale-secao-[a-z0-9-]+)"', html))
    assert "totale-secao-filtros" in ids
    assert "totale-sumario" in html


def test_barra_filtros_entrega_as_colunas_e_recebe_widgets(pagina: AppTest) -> None:
    assert pagina.session_state["n_cols"] == 3
    assert len(pagina.selectbox) == 3
    assert "totale-filtros-titulo" in _html(pagina)


def test_chips_tem_modificadores_de_destaque_e_acao(pagina: AppTest) -> None:
    html = _html(pagina)

    assert "totale-chip--destaque" in html
    assert "totale-chip--acao" in html
    assert "1.248" in html and "92%" in html


def test_secao_e_painel_recebem_conteudo(pagina: AppTest) -> None:
    html = _html(pagina)

    assert "totale-secao-cabecalho" in html
    assert "totale-secao-corpo" in html
    assert "Recorte aplicado" in html
    assert "3 ativos" in html
    assert any("corpo da seção" in str(m.value) for m in pagina.markdown)
    assert any("dentro do painel" in str(m.value) for m in pagina.markdown)


def test_abas_acoes_divisor_e_colunas(pagina: AppTest) -> None:
    html = _html(pagina)

    assert pagina.session_state["n_abas"] == 2
    assert len(pagina.tabs) == 2
    assert len(pagina.button) == 1
    assert "totale-acoes" in html
    assert "totale-divisor" in html and "Detalhes" in html
    assert pagina.session_state["n_colunas"] == 4


def test_rodape_com_versao_ambiente_e_horario(pagina: AppTest) -> None:
    html = _html(pagina)

    rodape = next(bloco for bloco in html.split("\n") if "totale-rodape" in bloco)
    assert "Portal TOTALE Analytics" in rodape
    assert "v3.6.0" in rodape
    assert "produção" in rodape
    assert "BRT" in rodape


def test_barra_fixa_e_solta_usam_chaves_distintas() -> None:
    """Só a barra ``fixa=True`` casa com o seletor sticky do CSS de layout."""
    app = AppTest.from_string(
        """
        import streamlit as st
        import components.layout_pagina as lp

        chaves = []
        original = lp.st.container

        def espiao(*args, **kwargs):
            chaves.append(kwargs.get("key"))
            return original(*args, **kwargs)

        lp.st.container = espiao
        try:
            with lp.barra_filtros("solta", fixa=False):
                pass
            with lp.barra_filtros("presa", fixa=True):
                pass
        finally:
            lp.st.container = original

        st.session_state["chaves"] = chaves
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception), [str(e.value) for e in app.exception]
    chaves = [c for c in app.session_state["chaves"] if c]
    assert chaves == ["totale_barra_solta", "totale_filtros_presa"]
    assert lp._CLASSE_FILTROS == "st-key-totale_filtros"
    assert chaves[0].replace("_", "", 1) not in lp._CLASSE_FILTROS  # barra solta não gruda
    assert chaves[1].startswith("totale_filtros")


def test_renderizacao_e_segura_sem_script_run_context() -> None:
    """Chamadas fora de runtime não podem derrubar import/CLI."""
    import components.layout_pagina as modulo

    # Sem contexto ativo, os primitivos apenas silenciam (não levantam).
    assert callable(modulo.render_cabecalho_pagina)
    assert callable(modulo.secao)


# ====================================================
# GUARDAS DE PLATAFORMA (Streamlit 1.65)
# ====================================================
def _arquivos_python(pasta: str) -> list[Path]:
    return sorted(p for p in (RAIZ / pasta).rglob("*.py") if p.is_file())


def _chamadas_de(codigo: str, atributo: str) -> list[ast.Call]:
    arvore = ast.parse(codigo)
    return [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == atributo
        and isinstance(no.func.value, ast.Name)
        and no.func.value.id == "st"
    ]


def test_nenhuma_pagina_usa_st_metric_nativo() -> None:
    """Item 1 concluído: cartões avançados no lugar de ``st.metric``."""
    infratores: list[str] = []
    for arquivo in _arquivos_python("pages") + _arquivos_python("services"):
        codigo = arquivo.read_text(encoding="utf-8")
        if _chamadas_de(codigo, "metric"):
            infratores.append(str(arquivo.relative_to(RAIZ)))

    assert not infratores, f"st.metric nativo em: {infratores}"


def test_nenhum_with_st_container_captura_o_retorno() -> None:
    """``st.container(...)`` como context manager entrega ``None`` no 1.65.

    Capturar o valor em ``with st.container(...) as alvo:`` produziria um alvo
    ``None`` e falhas silenciosas; o padrão do projeto é criar o contêiner antes
    do ``with`` (ver ``components.layout_pagina``).
    """
    infratores: list[str] = []
    pastas = ("pages", "components", "services", "robo")
    arquivos = [RAIZ / "streamlit_app.py"] + [a for pasta in pastas for a in _arquivos_python(pasta)]

    for arquivo in arquivos:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.With):
                continue
            for item in no.items:
                if item.optional_vars is None:
                    continue
                chamada = item.context_expr
                if (
                    isinstance(chamada, ast.Call)
                    and isinstance(chamada.func, ast.Attribute)
                    and chamada.func.attr == "container"
                ):
                    infratores.append(f"{arquivo.relative_to(RAIZ)}:{no.lineno}")

    assert not infratores, f"with st.container(...) as x em: {infratores}"


def test_pagina_referencia_usa_as_primitivas_de_layout() -> None:
    """``pages/home.py`` é a implementação de referência do layout v3.6."""
    caminho = RAIZ / "pages" / "home.py"
    codigo = caminho.read_text(encoding="utf-8")

    for primitiva in (
        "render_sumario(",  # sumário com âncoras
        "barra_filtros(",  # filtros fixos no topo
        "secao(",  # seções com âncora
        "painel(",  # painéis com altura controlada
        "render_barra_acoes(",  # exportação
        "render_rodape_pagina(",  # rodapé com versão/ambiente
        "render_kpi_row(",  # cartões de KPI avançados
        "render_hero_totale_",  # cabeçalho do Design System
    ):
        assert primitiva in codigo, primitiva

    # As seções publicadas na página alimentam o sumário (âncoras não-mortas).
    arvore = ast.parse(codigo)
    secoes = next(
        (
            no.value
            for no in arvore.body
            if isinstance(no, ast.AnnAssign)
            and getattr(no.target, "id", "") == "SECOES_PAGINA"
        ),
        None,
    )
    assert isinstance(secoes, ast.Tuple) and len(secoes.elts) == 7
    assert "render_sumario([titulo for titulo, _, _ in SECOES_PAGINA]" in codigo
