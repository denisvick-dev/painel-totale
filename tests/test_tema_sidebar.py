"""Regressão — o tema da sidebar deve sobreviver à navegação entre páginas.

Bug corrigido na v5.3.0 do Design System (`components/componentes.py`):

    As páginas em `pages/*` chamam `aplicar_estilo()` no início da execução,
    logo depois do entrypoint (`streamlit_app.py`). Como o parâmetro
    `tema_sidebar` tinha default `"claro"`, a cor escolhida pelo usuário no
    seletor de tema era sobrescrita em toda troca de página — o sidebar
    "voltava ao branco" em todas as páginas e só ficava correto na Home,
    que não reinjeta o CSS.

Os testes abaixo garantem que:

1. `aplicar_estilo()`, `aplicar_estilo_corp()` e `aplicar_sidebar_corp()`
   chamados sem argumento preservam o tema ativo da sessão.
2. O CSS gerado é realmente o do tema ativo (paleta aplicada, não só a chave).
3. Um tema passado explicitamente continua sendo respeitado (retrocompatível).
4. No fluxo real (entrypoint + página), trocar o tema atualiza o sidebar na
   hora, em qualquer página.

Execução:

    python tests/test_tema_sidebar.py        # execução direta (stdlib)
    pytest tests/test_tema_sidebar.py        # via pytest
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from streamlit.testing.v1 import AppTest

from components.componentes import CSSInjector

# Cores-âncora de cada tema (ConfigCores.SIDEBAR[tema]["fundo_base"]).
CORES_ANCORA = {
    "claro": "#F1F5F9",
    "azul": "#112B4A",
    "laranja": "#5A260F",
}

# Diretório de trabalho dos scripts temporários — precisa sobreviver aos
# reruns dos widgets, por isso fica no nível do módulo.
_DIR_TMP = TemporaryDirectory(prefix="totale-testes-")
_CONTADOR = itertools.count()

# Reproduz a ordem real de execução do portal em cada rerun:
#   1) entrypoint (`streamlit_app.main`) aplica o tema e desenha o seletor;
#   2) a página selecionada (`pages/*`) roda em seguida e reaplica o Design
#      System sem informar tema — era aqui que a cor era resetada.
_SCRIPT_FLUXO = """
import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_sidebar_brand,
    render_sidebar_theme_selector,
)
from streamlit_app import _aplicar_estilo_seguro

if "tema_sidebar" not in st.session_state:
    st.session_state["tema_sidebar"] = "laranja"

# ── 1) Entrypoint ────────────────────────────────────────────────────
tema_ativo = (
    st.session_state.get("_totale_sidebar_theme_select")
    or st.session_state.get("_totale_sidebar_theme")
    or st.session_state.get("tema_sidebar", "laranja")
)
_aplicar_estilo_seguro(tema_ativo)
render_sidebar_brand(
    nome="TOTALE", subtitulo="Portal de Produção", versao="v3.4.0", icone="⚡",
    tema=tema_ativo,
)
render_sidebar_theme_selector(label="Tema visual", key="_totale_sidebar_theme_select")

# ── 2) Página de pages/* (indicadores, pontos, volumetria, ...) ──────
aplicar_estilo()

st.session_state["__resultado"] = {
    "tema": st.session_state.get("_totale_css_head_tema"),
    "widget": st.session_state.get("_totale_sidebar_theme_select"),
}
"""

# Script que simula o início de uma página de `pages/*`: o entrypoint já
# deixou o tema da sessão definido e a página aplica o Design System.
_SCRIPT_PAGINA = """
import streamlit as st

from components.componentes import CSSInjector, {funcao}

{funcao}({argumento})

tema = st.session_state.get("_totale_css_head_tema")
st.session_state["__resultado"] = {{
    "tema": tema,
    "css": CSSInjector._build_css(tema),
    "widget": st.session_state.get("_totale_sidebar_theme_select"),
}}
"""


def _app_com_script(script: str) -> AppTest:
    """Cria um AppTest a partir de um script temporário persistente."""
    caminho = Path(_DIR_TMP.name) / f"app_teste_{next(_CONTADOR)}.py"
    caminho.write_text(script, encoding="utf-8")
    return AppTest.from_file(str(caminho), default_timeout=60)


def _rodar_pagina(
    funcao: str = "aplicar_estilo",
    tema_sessao: str = "claro",
    argumento: str = "",
) -> dict[str, Any]:
    """Executa uma página simulada e devolve o que ela aplicou no sidebar."""
    app = _app_com_script(_SCRIPT_PAGINA.format(funcao=funcao, argumento=argumento))
    app.session_state["_totale_sidebar_theme"] = tema_sessao
    app.session_state["_totale_sidebar_theme_select"] = tema_sessao
    app.session_state["tema_sidebar"] = tema_sessao
    app.run()
    assert not list(app.exception), f"Página simulada falhou: {list(app.exception)}"
    return app.session_state["__resultado"]


def _app_fluxo_real() -> AppTest:
    """App de teste que reproduz entrypoint + página de `pages/*`."""
    app = _app_com_script(_SCRIPT_FLUXO)
    app.run()
    assert not list(app.exception), f"Fluxo simulado falhou: {list(app.exception)}"
    return app


def _seletor_de_tema(app: AppTest):
    return next(w for w in app.sidebar.selectbox if w.key == "_totale_sidebar_theme_select")


def test_selectbox_sidebar_estiliza_markup_atual_do_streamlit() -> None:
    """O seletor nativo mantém contraste no markup React Aria do Streamlit atual."""
    fundos = {
        "claro": "#FFFFFF",
        "azul": "rgba(255, 255, 255, 0.06)",
        "laranja": "rgba(0, 0, 0, 0.22)",
    }
    for tema, fundo in fundos.items():
        css = CSSInjector._build_css(tema)
        assert '[data-testid="stSelectbox"] [role="group"]' in css
        assert '[data-testid="stSelectbox"] [role="group"] input[role="combobox"]' in css
        assert f"--totale-sb-input-bg: {fundo};" in css
        assert "-webkit-text-fill-color: var(--totale-sb-input-text) !important;" in css


def test_widgets_da_sidebar_herdam_a_paleta_escolhida() -> None:
    """Inputs, ações, expansores, slider e upload seguem o tema selecionado."""
    cores_de_foco = {
        "claro": "#C2410C",
        "azul": "#FDBA74",
        "laranja": "#FFD09A",
    }
    seletores = (
        '[data-testid="stNumberInput"]',
        '[data-testid="stExpander"]',
        '[data-testid="stButton"]',
        '[data-testid="stSelectbox"]',
        '[data-testid="stSlider"]',
        '[data-testid="stFileUploaderDropzone"]',
    )
    for tema, cor_foco in cores_de_foco.items():
        css = CSSInjector._build_css(tema)
        assert f"--totale-sb-input-focus: {cor_foco};" in css
        for seletor in seletores:
            assert f'[data-testid="stSidebar"] {seletor}' in css, (tema, seletor)
        assert "var(--totale-sb-input-focus)" in css
        assert "var(--totale-sb-button-hover-bg)" in css
        assert "var(--totale-sb-nav-hover-bg)" in css


def test_campos_numericos_tem_fundo_opaco_e_contraste_por_tema() -> None:
    fundos = {
        "claro": "#F1F5F9",
        "azul": "#112B4A",
        "laranja": "#5A260F",
    }
    bordas = {
        "claro": "#52657D",
        "azul": "#AFC5DC",
        "laranja": "#FFD09A",
    }
    for tema, fundo in fundos.items():
        css = CSSInjector._build_css(tema)
        assert f"--totale-sb-number-bg: {fundo};" in css
        assert f"--totale-sb-number-border: {bordas[tema]};" in css
        assert '[data-testid="stNumberInput"] div[data-baseweb="input"]' in css
        assert '[data-testid="stNumberInput"] > div' in css
        assert '[data-testid="stNumberInput"] input[type="number"]' in css
        assert '[data-testid="stNumberInput"] [role="button"]' in css
        assert "width: 1.5rem !important;" in css
        assert "flex: 0 0 1.5rem !important;" in css
        assert "background-color: var(--totale-sb-number-bg) !important;" in css
        assert "fill: var(--totale-sb-input-text) !important;" in css
        assert "-webkit-text-fill-color: var(--totale-sb-input-text) !important;" in css


def test_pagina_preserva_tema_da_sessao() -> None:
    """Página que chama aplicar_estilo() sem argumento mantém o tema escolhido."""
    for tema in ("claro", "azul", "laranja"):
        resultado = _rodar_pagina("aplicar_estilo", tema)
        assert resultado["tema"] == tema, (
            f"aplicar_estilo() sem argumento trocou o tema {tema!r} por {resultado['tema']!r}"
        )
        assert CORES_ANCORA[tema] in resultado["css"], (
            f"O CSS injetado não é o do tema {tema!r} — a paleta não foi aplicada."
        )
        assert resultado["widget"] == tema, "Seletor de tema fora de sincronia."


def test_alias_corporativo_preserva_tema_da_sessao() -> None:
    """Aliases corporativos também respeitam o tema ativo da sidebar."""
    for funcao in ("aplicar_estilo_corp", "aplicar_sidebar_corp"):
        resultado = _rodar_pagina(funcao, "azul")
        assert resultado["tema"] == "azul", (
            f"{funcao}() sem argumento trocou o tema para {resultado['tema']!r}"
        )
        assert CORES_ANCORA["azul"] in resultado["css"]


def test_tema_explicito_continua_valendo() -> None:
    """Passar um tema explícito continua sobrescrevendo o da sessão."""
    resultado = _rodar_pagina("aplicar_estilo", "claro", argumento='"laranja"')
    assert resultado["tema"] == "laranja"
    assert CORES_ANCORA["laranja"] in resultado["css"]


def test_fluxo_entrypoint_e_pagina_mantem_tema() -> None:
    """Entrypoint + página de pages/* preservam a cor da sidebar."""
    app = _app_fluxo_real()
    # Tema inicial do portal (streamlit_app.main define "laranja").
    assert app.session_state["__resultado"]["tema"] == "laranja", (
        "A página resetou o tema inicial do portal — esperado 'laranja'."
    )


def test_troca_de_tema_estando_em_outra_pagina() -> None:
    """Trocar o tema com uma página aberta atualiza a cor do sidebar na hora."""
    app = _app_fluxo_real()
    for tema in ("azul", "claro", "laranja"):
        _seletor_de_tema(app).set_value(tema).run()
        assert not list(app.exception), f"Troca para {tema!r} falhou: {list(app.exception)}"
        resultado = app.session_state["__resultado"]
        assert resultado["tema"] == tema, (
            f"Sidebar não assumiu o tema {tema!r} (ficou {resultado['tema']!r}) — "
            "a página reaplicou o CSS no tema padrão."
        )
        assert resultado["widget"] == tema, "Seletor de tema dessincronizado."


def _main() -> int:
    """Runner simples para uso sem pytest."""
    testes = [
        valor
        for nome, valor in sorted(globals().items())
        if nome.startswith("test_") and callable(valor)
    ]
    falhas = 0
    for teste in testes:
        try:
            teste()
        except AssertionError as exc:
            falhas += 1
            print(f"FALHOU  {teste.__name__}: {exc}")
        else:
            print(f"OK      {teste.__name__}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram.")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(_main())
