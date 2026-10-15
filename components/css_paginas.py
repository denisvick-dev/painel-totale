"""CSS compartilhado das páginas TOTALE (Design System).

Este módulo concentra os blocos de CSS que estavam **duplicados** entre páginas —
hoje, a família de tabelas corporativas (`.corp-table`), repetida em
`consultivo.py`, `pontos.py` e `qtde_os.py` com pequenas variações de densidade.

Cada página informa os parâmetros que já usava, então o CSS gerado é equivalente
ao que estava escrito à mão; o que muda é existir **um único lugar** para ajustar
a aparência corporativa das tabelas.

Uso (chamar antes do CSS local da página, preservando a ordem do cascade)::

    from components.css_paginas import aplicar_css_tabela_corporativa

    aplicar_css_tabela_corporativa(fonte_px=10.5, padding="4px 6px", altura_linha="1.25")

Páginas que não usam `.corp-table` seguem apenas com o próprio CSS local.
"""

from __future__ import annotations

from components.componentes import injetar_css

# Aparência padrão da marca (cabeçalho e barras de rolagem).
GRADIENTE_CABECALHO_PADRAO = "linear-gradient(180deg, #012869 0%, #1E40AF 100%)"
COR_TRILHO_SCROLLBAR = "#F1F5F9"
COR_BARRA_SCROLLBAR = "#CBD5E1"
COR_BARRA_SCROLLBAR_HOVER = "#94A3B8"


def _bloco(seletor: str, declaracoes: str) -> str:
    """Formata um bloco CSS simples, com indentação legível."""
    linhas = [f"    {seletor} {{"]
    linhas += [
        f"        {linha.strip()}" for linha in declaracoes.strip().splitlines() if linha.strip()
    ]
    linhas.append("    }")
    return "\n".join(linhas)


def css_tabela_corporativa(
    *,
    fonte_px: float = 11.0,
    padding: str = "5px 8px",
    altura_linha: str = "1.2",
    fonte_celula_px: float | None = None,
    gradiente_cabecalho: str = GRADIENTE_CABECALHO_PADRAO,
    raio_scrollbar: str = "4px",
    colapsar_bordas: bool = True,
    cabecalho_extra: str = "",
    celulas_extra: str = "",
) -> str:
    """Devolve o CSS da tabela corporativa (`.corp-table`).

    Args:
        fonte_px: tamanho da fonte base da tabela.
        padding: espaçamento interno das células.
        altura_linha: `line-height` das células.
        fonte_celula_px: fonte própria das células (opcional).
        gradiente_cabecalho: fundo do `thead`.
        raio_scrollbar: raio das barras de rolagem.
        colapsar_bordas: emite `border-collapse: collapse` (a página `qtde_os`
            mantém o padrão `separate` do navegador — preservado por parâmetro).
        cabecalho_extra: declarações extras do `thead` (ex.: sticky).
        celulas_extra: declarações extras das células.
    """
    celulas = f"font-size: {fonte_celula_px}px !important;" if fonte_celula_px else ""
    if celulas_extra:
        celulas = f"{celulas} {celulas_extra}".strip()

    blocos = [
        _bloco(
            ".corp-table",
            f"""
            width: 100% !important;
            {("border-collapse: collapse !important;" if colapsar_bordas else "")}
            font-size: {fonte_px}px !important;
            """,
        ),
        _bloco(
            ".corp-table th,\n    .corp-table td",
            f"""
            padding: {padding} !important;
            {celulas}
            line-height: {altura_linha} !important;
            """,
        ),
        _bloco(
            ".corp-table thead th",
            f"""
            background: {gradiente_cabecalho} !important;
            color: #FFFFFF !important;
            text-transform: uppercase !important;
            letter-spacing: 0.04em !important;
            font-size: 10px !important;
            {cabecalho_extra}
            """,
        ),
        # A classe "num" era gerada no HTML das páginas mas não existia no CSS;
        # vivia duplicada em consultivo/pontos — agora é responsabilidade do DS.
        _bloco(
            ".corp-table td.num",
            """
            text-align: right !important;
            font-variant-numeric: tabular-nums !important;
            """,
        ),
        _bloco(
            ".corp-table-wrap::-webkit-scrollbar",
            """
            width: 6px !important;
            height: 6px !important;
            """,
        ),
        _bloco(
            ".corp-table-wrap::-webkit-scrollbar-track",
            f"""
            background: {COR_TRILHO_SCROLLBAR} !important;
            border-radius: {raio_scrollbar} !important;
            """,
        ),
        _bloco(
            ".corp-table-wrap::-webkit-scrollbar-thumb",
            f"""
            background: {COR_BARRA_SCROLLBAR} !important;
            border-radius: {raio_scrollbar} !important;
            """,
        ),
        _bloco(
            ".corp-table-wrap::-webkit-scrollbar-thumb:hover",
            f"""
            background: {COR_BARRA_SCROLLBAR_HOVER} !important;
            """,
        ),
    ]
    return "\n".join(blocos)


def aplicar_css_tabela_corporativa(**kwargs: object) -> None:
    """Injeta na página o CSS de :func:`css_tabela_corporativa`."""
    injetar_css(css_tabela_corporativa(**kwargs))  # type: ignore[arg-type]


# ── Quebra operacional (matriz executiva + bloco de importação) ──────────────
# Estes blocos viviam em `pages/quebra_geral.py::_CSS_GLOBAL`, junto de regras de
# shell (body/sidebar/hero/KPI) que já pertencem a `components/css_global.py`.
# Ficam aqui porque são a aparência de tabelas e do cabeçalho de importação —
# a mesma família de CSS compartilhado das `.corp-table`.
COR_TINTA = "#0F172A"
COR_SUAVE = "#F8FAFC"
COR_TEXTO_SECUNDARIO = "#64748B"
COR_LINHA = "#E2E8F0"
COR_NAVY = "#012869"
COR_LARANJA = "#F37C04"


def css_quebra_operacional() -> str:
    """CSS das páginas de quebra (matriz executiva e bloco de importação).

    Preserva, caractere a caractere, as regras que ``pages/quebra_geral.py``
    injetava por conta própria — apenas sem as regras de shell/hero/KPI, que o
    Design System já aplica em todas as páginas.
    """
    return "\n".join(
        [
            _bloco(
                ".import-header-title",
                f"""
                font-size: 1.65rem;
                font-weight: 750;
                color: {COR_TINTA};
                letter-spacing: -.035em;
                """,
            ),
            _bloco(
                ".import-header-badge",
                """
                display: inline-flex;
                margin-left: .7rem;
                padding: .25rem .65rem;
                border: 1px solid #BFDBFE;
                border-radius: 999px;
                background: #EFF6FF;
                color: #1D4ED8;
                font-size: .68rem;
                font-weight: 700;
                """,
            ),
            _bloco(
                ".import-header-sub",
                f"""
                margin: .4rem 0 1rem;
                color: {COR_TEXTO_SECUNDARIO};
                font-size: .9rem;
                """,
            ),
            _bloco(
                ".import-header-line",
                f"""
                height: 2px;
                margin-bottom: 1.25rem;
                border-radius: 2px;
                background: linear-gradient(90deg, {COR_NAVY}, {COR_LARANJA} 65%, {COR_LINHA});
                """,
            ),
            _bloco(
                ".import-alert-green",
                """
                display: flex;
                align-items: center;
                gap: .6rem;
                margin-bottom: 1rem;
                padding: .85rem 1rem;
                border: 1px solid #A7F3D0;
                border-radius: 10px;
                background: #ECFDF5;
                color: #065F46;
                font-size: .85rem;
                font-weight: 650;
                """,
            ),
            _bloco(
                ".matriz-table-container",
                f"""
                width: 100%;
                overflow-x: auto;
                margin-bottom: 1rem;
                border: 1px solid {COR_LINHA};
                border-radius: 12px;
                background: #fff;
                box-shadow: 0 3px 12px rgba(15, 23, 42, .04);
                """,
            ),
            _bloco(
                ".matriz-table",
                """
                width: 100%;
                border-collapse: collapse;
                font-size: .82rem;
                """,
            ),
            _bloco(
                ".matriz-table th",
                f"""
                padding: .85rem 1rem;
                border-bottom: 1px solid {COR_LINHA};
                background: {COR_SUAVE};
                color: #475569;
                font-size: .68rem;
                font-weight: 700;
                letter-spacing: .06em;
                text-align: center;
                text-transform: uppercase;
                """,
            ),
            _bloco(
                ".matriz-table th:first-child, .matriz-table td:first-child",
                "text-align: left;",
            ),
            _bloco(
                ".matriz-table td",
                """
                padding: .7rem 1rem;
                border-bottom: 1px solid #F1F5F9;
                color: #334155;
                text-align: center;
                """,
            ),
            _bloco(
                ".matriz-table td:first-child",
                f"""
                color: {COR_TINTA};
                font-weight: 650;
                """,
            ),
            _bloco(".matriz-table tr:hover", f"background: {COR_SUAVE};"),
            _bloco(
                ".matriz-table tr.total-row",
                """
                border-top: 2px solid #CBD5E1;
                background: #F1F5F9;
                font-weight: 750;
                """,
            ),
            _bloco(
                ".badge-meta-ok, .badge-meta-nok",
                """
                display: inline-block;
                min-width: 68px;
                padding: .28rem .55rem;
                border: 1px solid;
                border-radius: 7px;
                font-size: .74rem;
                font-weight: 700;
                """,
            ),
            _bloco(
                ".badge-meta-ok",
                """
                border-color: #A7F3D0;
                background: #ECFDF5;
                color: #047857;
                """,
            ),
            _bloco(
                ".badge-meta-nok",
                """
                border-color: #FECACA;
                background: #FEF2F2;
                color: #B91C1C;
                """,
            ),
        ]
    )


def aplicar_css_quebra_operacional() -> None:
    """Injeta na página o CSS de :func:`css_quebra_operacional`."""
    injetar_css(css_quebra_operacional())


def css_cartao_segmento(cor_marca: str = COR_NAVY) -> str:
    """CSS do painel de quebra por segmento (cartão de status, alertas e abas).

    Vem de ``pages/quebra_unificada.py::_injetar_css_dinamico``, que além destas
    regras repetia o CSS de shell (``:root``, sidebar, container, heróis) já
    aplicado pelo Design System em todas as páginas. ``cor_marca`` pinta a marca
    do segmento (azul/laranja/azul-claro) sem alterar o restante do visual.
    """
    cor = str(cor_marca or COR_NAVY)
    return "\n".join(
        [
            f":root {{ --brand: {cor}; }}",
            _bloco(
                ".status-card",
                f"""
                margin: 1rem 0 1.25rem;
                padding: 1.25rem 1.4rem;
                border: 1px solid {COR_LINHA};
                border-top: 3px solid var(--status);
                border-radius: 16px;
                background: #fff;
                box-shadow: 0 4px 16px rgba(15, 23, 42, .045);
                """,
            ),
            _bloco(
                ".status-card__header",
                """
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: .75rem;
                """,
            ),
            _bloco(
                ".status-card__eyebrow",
                f"""
                margin: 0;
                color: {COR_TEXTO_SECUNDARIO};
                font-size: .68rem;
                font-weight: 700;
                letter-spacing: .09em;
                text-transform: uppercase;
                """,
            ),
            _bloco(
                ".status-card__title",
                f"""
                margin-top: .2rem;
                color: {COR_TINTA};
                font-size: 1.05rem;
                font-weight: 750;
                """,
            ),
            _bloco(
                ".status-pill",
                """
                padding: .38rem .75rem;
                border: 1px solid;
                border-radius: 999px;
                font-size: .7rem;
                font-weight: 750;
                letter-spacing: .04em;
                text-transform: uppercase;
                """,
            ),
            _bloco(
                ".status-card__metrics",
                """
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: .75rem;
                margin-top: 1.1rem;
                """,
            ),
            _bloco(
                ".status-metric",
                f"""
                padding: .8rem .9rem;
                border: 1px solid {COR_LINHA};
                border-radius: 12px;
                background: {COR_SUAVE};
                """,
            ),
            _bloco(
                ".status-metric__label",
                f"""
                display: block;
                color: {COR_TEXTO_SECUNDARIO};
                font-size: .7rem;
                font-weight: 600;
                """,
            ),
            _bloco(
                ".status-metric__value",
                f"""
                display: block;
                margin-top: .25rem;
                color: {COR_TINTA};
                font-size: 1.25rem;
                font-weight: 750;
                """,
            ),
            _bloco(
                ".status-card__bar-labels",
                f"""
                display: flex;
                justify-content: space-between;
                margin: 1rem 0 .4rem;
                color: {COR_TEXTO_SECUNDARIO};
                font-size: .68rem;
                font-weight: 600;
                """,
            ),
            _bloco(
                ".status-track",
                """
                position: relative;
                height: 8px;
                overflow: visible;
                border-radius: 999px;
                background: #E2E8F0;
                """,
            ),
            _bloco(".status-fill", "height: 100%; border-radius: 999px; background: var(--status);"),
            _bloco(
                ".status-target",
                """
                position: absolute;
                top: -3px;
                width: 2px;
                height: 14px;
                background: #334155;
                transform: translateX(-50%);
                """,
            ),
            _bloco(
                ".status-card__foot",
                f"""
                margin-top: .5rem;
                color: {COR_TEXTO_SECUNDARIO};
                font-size: .68rem;
                """,
            ),
            _bloco(
                ".alert-chip",
                """
                display: inline-flex;
                align-items: center;
                gap: 6px;
                margin: 4px 6px 4px 0;
                padding: 6px 11px;
                border-radius: 999px;
                font-size: .74rem;
                font-weight: 650;
                """,
            ),
            _bloco(
                '.stTabs [data-baseweb="tab-list"]',
                f"""
                gap: .35rem;
                padding: .35rem;
                border: 1px solid {COR_LINHA};
                border-radius: 12px;
                background: #fff;
                """,
            ),
            _bloco(
                '.stTabs [data-baseweb="tab"]',
                """
                height: 2.55rem;
                padding: 0 1rem;
                border-radius: 9px;
                color: #475569;
                font-size: .82rem;
                font-weight: 650;
                """,
            ),
            _bloco(
                '.stTabs [aria-selected="true"]',
                """
                background: #EFF6FF;
                color: #1D4ED8;
                """,
            ),
            "@media (max-width: 760px) { .status-card__metrics { grid-template-columns: 1fr; } }",
        ]
    )


def aplicar_css_cartao_segmento(cor_marca: str = COR_NAVY) -> None:
    """Injeta na página o CSS de :func:`css_cartao_segmento`."""
    injetar_css(css_cartao_segmento(cor_marca))


def css_cartao_upload() -> str:
    """CSS do cartão de upload e da barra de resultado (página Primeiro Atendimento).

    Vem de ``pages/p_atendimento.py::_injetar_css_local``, que além destas duas
    famílias repetia o CSS de shell (fontes, container, sidebar), o herói
    corporativo, os cartões de KPI, os cabeçalhos de seção e os alertas — tudo já
    entregue pelo Design System (``components/css_global.py`` e
    ``components/componentes.py``).
    """
    return "\n".join(
        [
            _bloco(
                ".upload-card",
                """
                background: #FFFFFF;
                border: 1px dashed #CBD5E1;
                border-radius: 8px;
                padding: 32px;
                text-align: center;
                margin-bottom: 16px;
                transition: all 0.2s;
                """,
            ),
            _bloco(
                ".upload-icon",
                f"""
                font-size: 32px;
                color: {COR_TINTA};
                margin-bottom: 12px;
                """,
            ),
            _bloco(
                ".upload-title",
                f"""
                font-size: 16px;
                font-weight: 600;
                color: {COR_TINTA};
                margin-bottom: 4px;
                """,
            ),
            _bloco(
                ".upload-subtitle",
                f"""
                font-size: 13px;
                color: {COR_TEXTO_SECUNDARIO};
                """,
            ),
            _bloco(
                ".resultado-base",
                f"""
                background: #FFFFFF;
                border: 1px solid {COR_LINHA};
                padding: 12px 16px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                gap: .5rem;
                flex-wrap: wrap;
                font-size: 13px;
                """,
            ),
            _bloco(
                ".resultado-label",
                f"""
                color: {COR_TEXTO_SECUNDARIO};
                font-weight: 600;
                """,
            ),
            _bloco(
                ".resultado-badge",
                """
                display: inline-flex;
                padding: .2rem .6rem;
                border: 1px solid;
                border-radius: 999px;
                font-size: .78rem;
                font-weight: 700;
                """,
            ),
            _bloco(
                ".resultado-count",
                f"""
                margin-left: auto;
                color: {COR_TINTA};
                font-weight: 700;
                """,
            ),
        ]
    )


def aplicar_css_cartao_upload() -> None:
    """Injeta na página o CSS de :func:`css_cartao_upload`."""
    injetar_css(css_cartao_upload())
