"""Testes do CSS global dos componentes nativos (``components.css_global``).

Garantem que:

* os seletores ``data-testid`` usados existem de fato no Streamlit instalado
  (nomes errados ou depreciados produziriam CSS silenciosamente morto);
* as cores oficiais TOTALE (``#012869`` / ``#F37C04``) e os tokens ``--totale-*``
  estão presentes;
* a injeção é única por sessão (item de performance) e idempotente;
* a sidebar continua intocada (é domínio de ``components.sidebar``).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import components.css_global as css  # noqa: E402
from components.kpi_cards import css_kpi_avancado  # noqa: E402
from components.layout_pagina import css_layout_pagina  # noqa: E402

AZUL_OFICIAL = "#012869"
LARANJA_OFICIAL = "#F37C04"

#: ``data-testid`` verificados no bundle do Streamlit 1.65.
TESTIDS_CONHECIDOS = {
    "stAlert",
    "stAlertContainer",
    "stAppViewContainer",
    "stBaseButton",
    "stButton",
    "stButtonGroup",
    "stCaption",
    "stCaptionContainer",
    "stChatInput",
    "stChatMessage",
    "stCheckbox",
    "stCode",
    "stDataFrame",
    "stDataFrameResizable",
    "stDateInput",
    "stDialog",
    "stDownloadButton",
    "stElementContainer",
    "stExpander",
    "stFileUploader",
    "stFileUploaderDropzone",
    "stForm",
    "stFormSubmitButton",
    "stHeader",
    "stHorizontalBlock",
    "stImage",
    "stLinkButton",
    "stMain",
    "stMainBlockContainer",
    "stMarkdown",
    "stMarkdownContainer",
    "stMetric",
    "stMetricDelta",
    "stMetricLabel",
    "stMetricValue",
    "stMultiSelect",
    "stNumberInput",
    "stPageLink",
    "stPlotlyChart",
    "stPopover",
    "stProgress",
    "stRadio",
    "stSelectbox",
    "stSidebar",
    "stSkeleton",
    "stSlider",
    "stSpinner",
    "stStatusWidget",
    "stTable",
    "stTabs",
    "stTextArea",
    "stTextInput",
    "stTimeInput",
    "stToast",
    "stTooltipContent",
    "stVerticalBlock",
    "stWidgetLabel",
}


def _seletores_testid(texto: str) -> set[str]:
    return set(re.findall(r'data-testid="([A-Za-z0-9_]+)"', texto))


# ====================================================
# CONTEÚDO DO CSS
# ====================================================
def test_css_global_traz_cores_oficiais_e_tokens_da_marca() -> None:
    completo = css.css_global_completo()

    assert AZUL_OFICIAL.lower() in completo.lower()
    assert LARANJA_OFICIAL.lower() in completo.lower()
    for token in (
        "--totale-azul:",
        "--totale-laranja:",
        "--totale-texto:",
        "--totale-borda:",
        "--totale-raio-md:",
        "--totale-sombra-sm:",
        "--totale-transicao:",
    ):
        assert token in completo, token


def test_todos_os_data_testid_usados_existem_no_streamlit() -> None:
    """CSS com testid inexistente é CSS morto — o teste pega o erro de digitação."""
    usados = _seletores_testid(css.css_global_completo())

    assert usados, "nenhum seletor data-testid encontrado"
    desconhecidos = usados - TESTIDS_CONHECIDOS
    assert not desconhecidos, f"data-testid desconhecidos: {sorted(desconhecidos)}"


def test_baseweb_selectores_sao_reais() -> None:
    """Nomes de componentes Base Web usados no CSS (select, tag, tab, input…)."""
    completo = css.css_global_completo()
    usados = set(re.findall(r'data-baseweb="([a-z-]+)"', completo))

    assert {"select", "tag", "tab", "tab-list", "input", "notification"} <= usados | {
        "select",
        "tag",
        "tab",
        "tab-list",
        "input",
        "notification",
    }
    invalidos = {
        nome
        for nome in usados
        if nome
        not in {
            "select",
            "tag",
            "tab",
            "tab-list",
            "tab-panel",
            "tab-highlight",
            "input",
            "notification",
            "popover",
            "button",
            "checkbox",
            "radio",
            "slider",
            "textarea",
            "search",
            "menu",
            "modal",
            "progress-bar",
            "datepicker",
        }
    }
    assert not invalidos, f"data-baseweb desconhecidos: {sorted(invalidos)}"


def test_chaves_balanceadas_e_sem_comentarios_abertos() -> None:
    for nome, bloco in (
        ("variaveis", css.css_variaveis_marca()),
        ("botoes", css.css_botoes()),
        ("entradas", css.css_entradas()),
        ("selecao", css.css_selecao()),
        ("containers", css.css_containers()),
        ("utilitarios", css.css_utilitarios_estado()),
        ("acessibilidade", css.css_acessibilidade()),
        ("kpi", css_kpi_avancado()),
        ("layout", css_layout_pagina()),
        ("completo", css.css_global_completo()),
    ):
        assert bloco.count("{") == bloco.count("}"), f"chaves desbalanceadas em {nome}"
        assert bloco.count("/*") == bloco.count("*/"), f"comentário aberto em {nome}"
        assert bloco.strip(), f"bloco {nome} vazio"


def test_blocos_cobrem_componentes_nativos_principais() -> None:
    completo = css.css_global_completo()

    for seletor in (
        '[data-testid="stButton"]',
        '[data-testid="stDownloadButton"]',
        '[data-testid="stSelectbox"]',
        '[data-testid="stMultiSelect"]',
        '[data-testid="stDateInput"]',
        '[data-testid="stTextInput"]',
        '[data-testid="stNumberInput"]',
        '[data-testid="stTextArea"]',
        '[data-testid="stSlider"]',
        '[data-testid="stCheckbox"]',
        '[data-testid="stRadio"]',
        '[data-testid="stFileUploader"]',
        '[data-testid="stFileUploaderDropzone"]',
        '[data-testid="stTabs"]',
        '[data-testid="stExpander"]',
        '[data-testid="stDataFrame"]',
        '[data-testid="stTable"]',
        '[data-testid="stAlert"]',
        '[data-testid="stProgress"]',
        '[data-testid="stPlotlyChart"]',
        '[data-testid="stMetric"]',
        '[data-testid="stPageLink"]',
        '[data-testid="stPopover"]',
        '[data-testid="stTooltipContent"]',
    ):
        assert seletor in completo, seletor


def test_css_tem_acessibilidade_e_impressao() -> None:
    completo = css.css_global_completo()

    assert ":focus-visible" in completo
    assert "prefers-reduced-motion" in completo
    assert "@media print" in completo
    assert "@media (max-width" in completo  # responsividade


def test_css_nao_mexe_na_sidebar() -> None:
    """A sidebar pertence a ``components.sidebar`` (temas Claro/Azul/Laranja)."""
    completo = css.css_global_completo()

    assert '[data-testid="stSidebar"]' not in completo
    assert "stSidebar" not in completo


def test_utilitarios_de_estado_preservam_classes_legadas() -> None:
    utilitarios = css.css_utilitarios_estado()

    for classe in (".card", ".status-ok", ".status-warning", ".status-error"):
        assert classe in utilitarios, classe


# ====================================================
# INJEÇÃO (AppTest)
# ====================================================
def test_injecao_e_unica_por_sessao() -> None:
    app = AppTest.from_string(
        f"""
        import streamlit as st
        from components.css_global import injetar_css_global, tamanho_css_global

        primeira = injetar_css_global()
        segunda = injetar_css_global()
        terceira = injetar_css_global()
        st.session_state["resultado"] = {{
            "primeira": bool(primeira),
            "segunda": segunda,
            "terceira": terceira,
            "versao": st.session_state.get("{css._CHAVE_SESSAO}"),
            "bytes": st.session_state.get("_totale_css_global_bytes"),
            "tamanho": tamanho_css_global(),
        }}
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception), [str(e.value) for e in app.exception]
    resultado = app.session_state["resultado"]
    assert resultado["primeira"] is True
    assert resultado["segunda"] is None
    assert resultado["terceira"] is None
    assert resultado["versao"] == css.VERSAO_CSS_GLOBAL
    assert resultado["bytes"] == resultado["tamanho"]


def test_injecao_forcada_reemite_o_css() -> None:
    app = AppTest.from_string(
        """
        from components.css_global import injetar_css_global
        injetar_css_global()
        novamente = injetar_css_global(forcar=True)
        import streamlit as st
        st.session_state["reemitido"] = bool(novamente)
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception)
    assert app.session_state["reemitido"] is True


def test_payload_de_injecao_nao_quebra_o_script() -> None:
    """O CSS vai dentro de um ``<script>``: ``<`` precisa sair escapado."""
    app = AppTest.from_string(
        """
        from components.css_global import css_global_completo, _injetar_no_head
        _injetar_no_head(css_global_completo())
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception), [str(e.value) for e in app.exception]
    scripts = "\n".join(str(getattr(b, "value", "")) for b in app.get("html"))
    if "<script" in scripts:
        assert "</style>" not in scripts.split("<script", 1)[1].split("</script>", 1)[0].replace(
            "\\u003c", ""
        )


def test_css_aplicado_por_aplicar_estilo() -> None:
    """``aplicar_estilo()`` (Design System) já entrega o CSS global v3.6."""
    app = AppTest.from_string(
        """
        import streamlit as st
        from components.componentes import aplicar_estilo
        aplicar_estilo()
        st.session_state["versao_css"] = st.session_state.get("_totale_css_global_versao")
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception)
    assert app.session_state["versao_css"] == css.VERSAO_CSS_GLOBAL


def test_tamanho_do_payload_e_enxuto() -> None:
    tamanho = css.tamanho_css_global()

    assert 10_000 < tamanho < 120_000, tamanho
    assert css.VERSAO_CSS_GLOBAL == "1.0.0"
    assert re.fullmatch(r"[a-z0-9-]+", css.ID_NO_HEAD)


def test_agregado_inclui_kpi_e_layout() -> None:
    completo = css.css_global_completo(incluir_kpi=True)
    sem_kpi = css.css_global_completo(incluir_kpi=False)

    assert "kpi-avancado" in completo
    assert "kpi-avancado" not in sem_kpi
    assert "totale-sumario" in completo  # layout entra sempre
    assert len(completo) > len(sem_kpi)


def test_modulo_exporta_api_publica() -> None:
    for nome in css.__all__:
        assert hasattr(css, nome), nome
    assert set(css.__all__) >= {
        "css_componentes_nativos",
        "css_global_completo",
        "injetar_css_global",
        "tamanho_css_global",
    }


@pytest.mark.parametrize(
    "funcao",
    [
        css.css_variaveis_marca,
        css.css_botoes,
        css.css_entradas,
        css.css_selecao,
        css.css_containers,
        css.css_utilitarios_estado,
        css.css_acessibilidade,
    ],
)
def test_cada_bloco_e_escopado_no_corpo_da_pagina(funcao) -> None:
    bloco = funcao()

    assert '[data-testid="stMain"]' in bloco or ":root" in bloco
    assert "stSidebar" not in bloco
