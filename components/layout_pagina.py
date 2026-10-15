"""components/layout_pagina.py
==============================
Primitivas de organização da informação nas páginas do portal.

Versão: 1.0.0
Autor: TOTALE Tecnologia

As páginas do portal cresciam com ordens diferentes: algumas abriam com filtros,
outras com tabelas, outras com dez gráficos seguidos — o leitor precisava
"aprender" cada painel. Este módulo fixa **uma hierarquia de leitura** e entrega
os blocos prontos para respeitá-la:

    1. Cabeçalho      → o que é a página e qual o recorte atual
    2. Sumário        → para onde posso ir (âncoras)
    3. Filtros        → como recortar os dados (barra fixa no topo)
    4. KPIs           → os 3 a 6 números que importam
    5. Gráficos       → tendência, ranking e participação
    6. Detalhamento   → tabelas e análises específicas (abas/expansores)
    7. Exportação     → sair do painel com o dado
    8. Rodapé         → versão, ambiente e horário

Componentes:

• ``render_cabecalho_pagina``: hero compacto + faixa de contexto (chips com
  última atualização, registros e período).
• ``render_sumario``: navegação por âncoras para as seções da página.
• ``barra_filtros``: context manager de filtros **fixo no topo** ao rolar.
• ``secao`` / ``painel``: blocos com cabeçalho padronizado e âncora própria.
• ``render_abas``: abas com ícones e chaves estáveis.
• ``render_barra_acoes``: linha de ações (exportar, atualizar, limpar).
• ``render_rodape_pagina``: rodapé corporativo único.
• ``colunas``: atalho de grade com quebra automática em telas estreitas.

Exemplo::

    from components.layout_pagina import barra_filtros, render_cabecalho_pagina, secao

    render_cabecalho_pagina(
        "Volumetria", subtitulo="Demanda diária por base",
        chips={"Registros": "12.480", "Período": "01/10 a 13/10"},
    )
    with barra_filtros(chave="volumetria"):
        base = st.selectbox("Base", opcoes)
    with secao("Visão geral", icone="monitoring"):
        render_kpi_row(specs)
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import streamlit as st

from components.componentes import (
    Cores,
    TipoBadgeType,
    Validadores,
    _icone_tile,
    _safe_render_html,
    formatar_numero_br,
)

logger = logging.getLogger(__name__)

VERSAO_LAYOUT = "1.0.0"

#: Hierarquia de leitura recomendada para todas as páginas do portal.
ORDEM_PADRAO: tuple[str, ...] = (
    "Cabeçalho e contexto",
    "Sumário (âncoras)",
    "Filtros",
    "KPIs",
    "Gráficos principais",
    "Detalhamento (abas/expansores)",
    "Exportação",
    "Rodapé",
)

_PREFIXO_ANCORA = "totale-secao"
_CLASSE_FILTROS = "st-key-totale_filtros"


def _slug(texto: str) -> str:
    """Slug estável e seguro para âncoras de seção."""
    sem_acento = unicodedata.normalize("NFKD", str(texto or ""))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    limpo = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return f"{_PREFIXO_ANCORA}-{limpo or 'secao'}"


# ====================================================
# 🎨 BLOCO 1: CSS DE LAYOUT (AGREGADO PELO CSS GLOBAL)
# ====================================================
def css_layout_pagina() -> str:
    """Estilos das primitivas de organização (chips, sumário, filtros fixos)."""
    return f"""
    /* ============================================================
       LAYOUT DE PÁGINA v{VERSAO_LAYOUT} — hierarquia de leitura
       ============================================================ */
    [data-testid="stMain"] .totale-contexto {{
        display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
        margin: -8px 0 18px;
    }}
    [data-testid="stMain"] .totale-chip {{
        display: inline-flex; align-items: center; gap: 6px;
        background: #FFFFFF; border: 1px solid var(--totale-borda, {Cores.BORDA});
        border-radius: 999px; padding: 5px 12px;
        font-size: 11.5px; font-weight: 650; color: {Cores.TEXTO_2};
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        white-space: nowrap;
    }}
    [data-testid="stMain"] .totale-chip__rotulo {{
        color: {Cores.TEXTO_3}; font-weight: 700; letter-spacing: .04em;
        text-transform: uppercase; font-size: 10px;
    }}
    [data-testid="stMain"] .totale-chip__valor {{
        color: {Cores.PRIMARIA}; font-variant-numeric: tabular-nums; font-weight: 800;
    }}
    [data-testid="stMain"] .totale-chip--acao {{
        border-color: rgba(243, 124, 4, 0.35); background: #FFF7ED;
        color: {Cores.SECUNDARIA_DARK};
    }}
    [data-testid="stMain"] .totale-chip--destaque {{
        background: {Cores.PRIMARIA}; border-color: {Cores.PRIMARIA}; color: #FFFFFF;
    }}
    [data-testid="stMain"] .totale-chip--destaque .totale-chip__rotulo {{
        color: rgba(255, 255, 255, 0.72);
    }}
    [data-testid="stMain"] .totale-chip--destaque .totale-chip__valor {{ color: #FFFFFF; }}

    /* Sumário (navegação por âncoras) */
    [data-testid="stMain"] .totale-sumario {{
        display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
        padding: 10px 12px; margin-bottom: 18px;
        background: linear-gradient(90deg, #FFFFFF 0%, #F8FAFD 100%);
        border: 1px solid var(--totale-borda, {Cores.BORDA});
        border-left: 3px solid {Cores.SECUNDARIA};
        border-radius: 12px;
    }}
    [data-testid="stMain"] .totale-sumario__titulo {{
        font-size: 10px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
        color: {Cores.TEXTO_3}; margin-right: 4px;
    }}
    [data-testid="stMain"] .totale-sumario a {{
        display: inline-flex; align-items: center; gap: 5px;
        padding: 4px 11px; border-radius: 999px;
        background: #FFFFFF; border: 1px solid {Cores.BORDA};
        color: {Cores.PRIMARIA}; font-size: 11.5px; font-weight: 700;
        text-decoration: none; transition: all .16s ease;
    }}
    [data-testid="stMain"] .totale-sumario a:hover {{
        background: {Cores.PRIMARIA}; border-color: {Cores.PRIMARIA}; color: #FFFFFF;
        transform: translateY(-1px);
    }}

    /* Cabeçalho de seção com âncora */
    [data-testid="stMain"] .totale-secao-cabecalho {{
        display: flex; align-items: flex-start; gap: 10px;
        margin: var(--totale-espaco-secao, 26px) 0 12px;
        padding-bottom: 10px; border-bottom: 1px solid var(--totale-borda, {Cores.BORDA});
        scroll-margin-top: 90px;
    }}
    [data-testid="stMain"] .totale-secao-cabecalho:first-child {{ margin-top: 4px; }}
    [data-testid="stMain"] .totale-secao-titulo {{
        font-family: var(--font-titulo); font-size: clamp(17px, 1.9vw, 21px);
        font-weight: 800; color: {Cores.PRIMARIA}; margin: 0; line-height: 1.2;
        letter-spacing: -0.03em;
    }}
    [data-testid="stMain"] .totale-secao-subtitulo {{
        margin: 4px 0 0; font-size: 12.5px; color: {Cores.TEXTO_3}; line-height: 1.5;
    }}
    [data-testid="stMain"] .totale-secao-corpo {{ flex: 1; min-width: 0; }}
    [data-testid="stMain"] .totale-secao-linha {{
        display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0;
    }}

    /* Barra de filtros fixa ao rolar */
    [data-testid="stMain"] [class*="{_CLASSE_FILTROS}"] {{
        position: sticky; top: 0; z-index: 995;
        background: rgba(255, 255, 255, 0.94);
        backdrop-filter: blur(10px);
        border: 1px solid var(--totale-borda, {Cores.BORDA}) !important;
        border-radius: 14px !important;
        box-shadow: 0 10px 26px rgba(1, 40, 105, 0.09);
        padding: 10px 14px 4px !important;
        margin-bottom: 14px;
    }}
    [data-testid="stMain"] .totale-filtros-titulo {{
        display: flex; align-items: center; gap: 6px;
        font-size: 10px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
        color: {Cores.TEXTO_3}; margin: 0 0 6px;
    }}

    /* Barra de ações (exportar / atualizar / limpar) */
    [data-testid="stMain"] .totale-acoes {{
        display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
        padding: 10px 12px; margin: 6px 0 14px;
        background: #FFFFFF; border: 1px dashed {Cores.BORDA}; border-radius: 12px;
    }}
    [data-testid="stMain"] .totale-acoes__rotulo {{
        font-size: 10px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
        color: {Cores.TEXTO_3};
    }}

    /* Divisor com texto */
    [data-testid="stMain"] .totale-divisor {{
        display: flex; align-items: center; gap: 12px; margin: 22px 0 14px;
        font-size: 10.5px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase;
        color: {Cores.TEXTO_3};
    }}
    [data-testid="stMain"] .totale-divisor::before,
    [data-testid="stMain"] .totale-divisor::after {{
        content: ""; flex: 1; height: 1px;
        background: linear-gradient(90deg, transparent, {Cores.BORDA} 40%, transparent);
    }}

    /* Rodapé */
    [data-testid="stMain"] .totale-rodape {{
        margin-top: 34px; padding: 14px 22px; text-align: center;
        background: linear-gradient(90deg, {Cores.PRIMARIA_DARK} 0%, {Cores.PRIMARIA} 55%, {Cores.PRIMARIA_LIGHT} 100%);
        color: #FFFFFF; border-radius: 14px; font-size: 12px; font-weight: 600;
        letter-spacing: .2px; box-shadow: 0 10px 24px rgba(1, 40, 105, 0.2);
        border-top: 3px solid {Cores.SECUNDARIA};
    }}
    [data-testid="stMain"] .totale-rodape span.sep {{
        color: {Cores.SECUNDARIA_LIGHT}; margin: 0 9px; font-weight: 900;
    }}
    """


# ====================================================
# 🧭 BLOCO 2: CABEÇALHO E CONTEXTO DA PÁGINA
# ====================================================
def _chip_html(
    rotulo: str,
    valor: str,
    *,
    variante: str = "",
    icone: str = "",
) -> str:
    classe = f"totale-chip {variante}".strip()
    icone_html = (
        f'<span class="totale-icon-glyph" aria-hidden="true">{Validadores.html_escape(icone)}</span>'
        if icone
        else ""
    )
    rotulo_html = (
        f'<span class="totale-chip__rotulo">{Validadores.html_escape(str(rotulo))}</span>'
        if rotulo
        else ""
    )
    return (
        f'<span class="{classe}">{icone_html}{rotulo_html}'
        f'<span class="totale-chip__valor">{Validadores.html_escape(str(valor))}</span></span>'
    )


def render_chips(
    itens: Mapping[str, Any] | Sequence[tuple[str, Any]],
    *,
    destaque: Sequence[str] = (),
    acao: Sequence[str] = (),
    container: Any = None,
) -> None:
    """Faixa de chips com o contexto da página (período, registros, fontes…)."""
    if not itens:
        return
    pares = list(itens.items()) if isinstance(itens, Mapping) else [tuple(i) for i in itens]
    marcados = {str(d) for d in destaque}
    acoes = {str(a) for a in acao}
    chips: list[str] = []
    for rotulo, valor in pares:
        if valor in (None, ""):
            continue
        variante = ""
        if str(rotulo) in marcados:
            variante = "totale-chip--destaque"
        elif str(rotulo) in acoes:
            variante = "totale-chip--acao"
        texto_valor = (
            formatar_numero_br(valor)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool)
            else str(valor)
        )
        chips.append(_chip_html(str(rotulo), texto_valor, variante=variante))
    if not chips:
        return
    _safe_render_html(f'<div class="totale-contexto">{"".join(chips)}</div>', container)


def render_cabecalho_pagina(
    titulo: str,
    *,
    subtitulo: str = "",
    badge: str = "",
    icone: str = "",
    chips: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
    atualizado_em: datetime | str | None = None,
    registros: int | None = None,
    periodo: str = "",
    hero: bool = True,
    container: Any = None,
) -> None:
    """Cabeçalho padrão: hero (ou título simples) + faixa de contexto.

    A faixa de contexto responde, sem o leitor precisar rolar a página, a três
    perguntas: *quando* os dados foram atualizados, *quanto* há de dado e *qual*
    o período do recorte.
    """
    if hero:
        from components.componentes import render_hero_totale_1

        meta = " · ".join(
            parte
            for parte in (
                periodo,
                f"{formatar_numero_br(registros)} registros" if registros else "",
                f"Atualizado em {_texto_horario(atualizado_em)}" if atualizado_em else "",
            )
            if parte
        )
        render_hero_totale_1(
            titulo=titulo,
            subtitulo=subtitulo,
            badge=badge or "PAINEL TOTALE",
            icone=icone or "⚡",
            meta_info=meta,
        )
    else:
        titulo_html = (
            f'<h1 class="totale-secao-titulo" style="font-size:26px;">'
            f"{Validadores.html_escape(titulo)}</h1>"
        )
        icone_html = _icone_tile(icone) if icone else ""
        sub_html = (
            f'<p class="totale-secao-subtitulo">{Validadores.html_escape(subtitulo)}</p>'
            if subtitulo
            else ""
        )
        _safe_render_html(
            f'<div class="totale-secao-cabecalho">{icone_html}'
            f'<div class="totale-secao-corpo"><div class="totale-secao-linha">{titulo_html}</div>'
            f"{sub_html}</div></div>",
            container,
        )

    itens: list[tuple[str, Any]] = []
    if isinstance(chips, Mapping):
        itens.extend(chips.items())
    elif chips:
        itens.extend(tuple(item) for item in chips)
    if atualizado_em:
        itens.append(("Atualizado", _texto_horario(atualizado_em)))
    if registros:
        itens.append(("Registros", formatar_numero_br(registros)))
    if periodo:
        itens.append(("Período", periodo))
    if itens:
        render_chips(itens, destaque=("Registros",), container=container)


def _texto_horario(valor: datetime | str | None) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    return str(valor)


def render_sumario(
    secoes: Sequence[str] | Sequence[tuple[str, str]],
    *,
    titulo: str = "Nesta página",
    container: Any = None,
) -> None:
    """Sumário com âncoras para as seções (ordem de leitura explícita)."""
    if not secoes:
        return
    itens: list[tuple[str, str]] = []
    for item in secoes:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            rotulo, ancora = str(item[0]), str(item[1])
        else:
            rotulo = str(item)
            ancora = _slug(rotulo)
        itens.append((rotulo, ancora))
    links = "".join(
        f'<a href="#{Validadores.html_escape(ancora)}">{Validadores.html_escape(rotulo)}</a>'
        for rotulo, ancora in itens
    )
    _safe_render_html(
        f'<nav class="totale-sumario" aria-label="{Validadores.html_escape(titulo)}">'
        f'<span class="totale-sumario__titulo">{Validadores.html_escape(titulo)}</span>{links}</nav>',
        container,
    )


# ====================================================
# 🧱 BLOCO 3: SEÇÕES, PAINÉIS E ABAS
# ====================================================
# ⚠️ Em Streamlit 1.65 ``DeltaGenerator.__enter__`` devolve ``None``: o padrão
# ``with st.container(...) as alvo:`` entrega ``None``. Por isso os context
# managers abaixo capturam o contêiner **antes** do ``with`` e o devolvem ao
# chamador (o bloco continua direcionando os elementos para ele).


def _cabecalho_secao(
    titulo: str,
    *,
    icone: str = "",
    subtitulo: str = "",
    badge: str = "",
    badge_tipo: TipoBadgeType = "default",
    ancora: str = "",
) -> None:
    icone_html = _icone_tile(icone) if icone else ""
    badge_html = ""
    if badge:
        from components.componentes import ConfigCores, normalizar_tipo_badge

        fundo, cor, borda = ConfigCores.BADGE[normalizar_tipo_badge(badge_tipo)]
        badge_html = (
            f'<span class="totale-badge-pill" style="background:{fundo};color:{cor};'
            f'border:1px solid {borda};">{Validadores.html_escape(badge)}</span>'
        )
    sub_html = (
        f'<p class="totale-secao-subtitulo">{Validadores.html_escape(subtitulo)}</p>'
        if subtitulo
        else ""
    )
    id_attr = f' id="{Validadores.html_escape(ancora)}"' if ancora else ""
    _safe_render_html(
        f'<header class="totale-secao-cabecalho"{id_attr}>{icone_html}'
        '<div class="totale-secao-corpo">'
        f'<div class="totale-secao-linha"><h2 class="totale-secao-titulo">'
        f"{Validadores.html_escape(titulo)}</h2>{badge_html}</div>{sub_html}</div></header>"
    )


def cabecalho_secao(
    titulo: str,
    *,
    icone: str = "",
    subtitulo: str = "",
    badge: str = "",
    badge_tipo: TipoBadgeType = "default",
    ancora: bool = True,
) -> str:
    """Cabeçalho de seção **sem** abrir bloco — devolve a âncora usada.

    Existe para as páginas longas que já têm seu próprio fluxo de contêineres
    (abas, colunas e HTML em f-string): trocar ``st.subheader`` por este
    cabeçalho padroniza o visual e cria a âncora do sumário sem reindentar o
    corpo. Para blocos novos prefira o context manager :func:`secao`.
    """
    id_ancora = _slug(titulo) if ancora and titulo else ""
    if titulo:
        _cabecalho_secao(
            titulo,
            icone=icone,
            subtitulo=subtitulo,
            badge=badge,
            badge_tipo=badge_tipo,
            ancora=id_ancora,
        )
    return id_ancora


@contextmanager
def secao(
    titulo: str,
    *,
    icone: str = "",
    subtitulo: str = "",
    badge: str = "",
    badge_tipo: TipoBadgeType = "default",
    borda: bool = False,
    ancora: bool = True,
) -> Iterator[Any]:
    """Seção padronizada: cabeçalho com âncora + corpo (com ou sem borda).

    Uso::

        with secao("Visão geral", icone="monitoring", subtitulo="Últimos 30 dias"):
            render_kpi_row(specs)
    """
    id_ancora = _slug(titulo) if ancora and titulo else ""
    if titulo:
        _cabecalho_secao(
            titulo,
            icone=icone,
            subtitulo=subtitulo,
            badge=badge,
            badge_tipo=badge_tipo,
            ancora=id_ancora,
        )
    corpo = st.container(border=borda)
    with corpo:
        yield corpo


@contextmanager
def painel(
    titulo: str = "",
    *,
    icone: str = "",
    subtitulo: str = "",
    badge: str = "",
    altura: int | None = None,
) -> Iterator[Any]:
    """Cartão com borda para agrupar conteúdo secundário (evita páginas longas).

    ``altura`` define rolagem interna em pixels (útil para tabelas longas); sem
    ela o painel cresce conforme o conteúdo. O Streamlit rejeita ``height=None``,
    então o parâmetro só é enviado quando informado.
    """
    if titulo:
        _cabecalho_secao(titulo, icone=icone, subtitulo=subtitulo, badge=badge, ancora="")
    opcoes: dict[str, Any] = {"border": True}
    if altura and int(altura) > 0:
        opcoes["height"] = int(altura)
    corpo = st.container(**opcoes)
    with corpo:
        yield corpo


@contextmanager
def barra_filtros(
    chave: str,
    *,
    titulo: str = "Filtros",
    icone: str = "tune",
    fixa: bool = True,
    colunas: int = 4,
    gap: str = "small",
) -> Iterator[list[Any]]:
    """Barra de filtros fixa no topo da página ao rolar (sticky).

    Mantém os filtros sempre visíveis — o leitor nunca precisa voltar ao começo
    para trocar o recorte. O bloco entrega as colunas já criadas::

        with barra_filtros("producao", colunas=3) as cols:
            base = cols[0].selectbox("Base", opcoes)
            inicio = cols[1].date_input("Início", value=...)
            status = cols[2].multiselect("Status", opcoes)

    ``colunas=0`` devolve o contêiner (para layouts livres).
    """
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", str(chave)).strip("_") or "geral"
    # ``fixa=False`` usa prefixo distinto para não casar com o seletor sticky
    # ``[class*="st-key-totale_filtros"]`` do CSS de layout.
    nome_chave = f"totale_filtros_{slug}" if fixa else f"totale_barra_{slug}"
    corpo = st.container(border=True, key=nome_chave)
    with corpo:
        if titulo:
            _safe_render_html(
                '<div class="totale-filtros-titulo">'
                f'<span class="totale-icon-glyph" aria-hidden="true">'
                f"{Validadores.html_escape(icone)}</span>"
                f"{Validadores.html_escape(titulo)}</div>"
            )
        quantidade = int(colunas)
        if quantidade <= 0:
            yield [corpo]
        else:
            yield list(corpo.columns(quantidade, gap=gap))


def render_abas(
    rotulos: Sequence[str],
    *,
    chave: str = "",
    icones: Sequence[str] | None = None,
) -> list[Any]:
    """Abas com ícones opcionais e chave estável (evita colisão entre páginas)."""
    nomes = [str(r) for r in rotulos]
    if not nomes:
        return []
    if icones:
        nomes = [
            f"{icone} {nome}".strip() if icone else nome
            for nome, icone in zip(nomes, list(icones) + [""] * max(0, len(nomes) - len(icones)))
        ]
    try:
        return list(st.tabs(nomes))
    except Exception:  # pragma: no cover - proteção de runtime
        logger.debug("st.tabs falhou com chave %r.", chave, exc_info=True)
        return [st.container() for _ in nomes]


def render_divisor(texto: str = "", *, container: Any = None) -> None:
    """Divisor horizontal com rótulo opcional (marca mudança de bloco)."""
    if texto:
        _safe_render_html(
            f'<div class="totale-divisor">{Validadores.html_escape(texto)}</div>', container
        )
    else:
        st.divider()


def render_barra_acoes(
    rotulo: str = "Ações",
    *,
    container: Any = None,
    icone: str = "bolt",
) -> Any:
    """Faixa de ações (exportar, atualizar, limpar) separada do conteúdo.

    Devolve um contêiner horizontal já pronto para receber os controles::

        acoes = render_barra_acoes("Exportar e atualizar")
        acoes.download_button("CSV", data=csv, file_name="dados.csv")
        if acoes.button("Atualizar", type="primary"):
            ...

    Também funciona como contexto (``with render_barra_acoes():`` + ``st.…``).
    Nunca devolve o módulo ``st`` nem ``None``: o padrão
    ``with st.container(...) as alvo:`` entrega ``None`` no Streamlit 1.65.
    """
    alvo = container if container is not None else st
    faixa = alvo.container(border=False)
    if rotulo:
        _safe_render_html(
            f'<div class="totale-acoes">'
            f'<span class="totale-icon-glyph" aria-hidden="true">'
            f"{Validadores.html_escape(icone)}</span>"
            f'<span class="totale-acoes__rotulo">{Validadores.html_escape(rotulo)}</span></div>',
            faixa,
        )
    try:
        return faixa.container(horizontal=True, gap="small", wrap=True)
    except TypeError:  # Streamlit < 1.47 sem layout horizontal
        return faixa.container()


def colunas(
    quantidade: int, *, gap: str = "small", proporcao: Sequence[float] | None = None
) -> list[Any]:
    """Atalho de grade: aceita número de colunas ou proporções."""
    if proporcao:
        return list(st.columns(list(proporcao), gap=gap))
    return list(st.columns(max(1, int(quantidade)), gap=gap))


# ====================================================
# 🏁 BLOCO 4: RODAPÉ PADRONIZADO
# ====================================================
def render_rodape_pagina(
    *,
    versao: str = "",
    ambiente: str = "",
    texto: str = "Portal TOTALE Analytics",
    horario: datetime | None = None,
    container: Any = None,
) -> None:
    """Rodapé corporativo único (marca, ambiente, horário e versão)."""
    agora = horario or datetime.now()
    partes = [f"🏢 <b>{Validadores.html_escape(texto)}</b>"]
    if ambiente:
        partes.append(f"🌐 {Validadores.html_escape(ambiente)}")
    partes.append(f"🕒 {agora.strftime('%d/%m/%Y')} • {agora.strftime('%H:%M')} BRT")
    if versao:
        partes.append(f"🔖 v{Validadores.html_escape(str(versao))}")
    corpo = '<span class="sep">|</span>'.join(partes)
    _safe_render_html(f'<footer class="totale-rodape">{corpo}</footer>', container)


__all__ = [
    "ORDEM_PADRAO",
    "VERSAO_LAYOUT",
    "barra_filtros",
    "cabecalho_secao",
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
]
