"""components/kpi_cards.py
==========================
Cartões de KPI avançados — substitutos diretos do ``st.metric`` nativo.

Versão: 1.0.0
Autor: TOTALE Tecnologia

O ``st.metric`` do Streamlit entrega rótulo, valor e delta — e só. Nos painéis
da TOTALE faltavam contexto (tendência dos últimos dias), comparação com meta e
identidade visual. Este módulo resolve isso sem depender de Plotly no cartão
(sparkline em SVG inline: ~300 bytes, sem runtime de gráfico no navegador):

• ``render_kpi_card``: cartão completo — rótulo, valor, delta com semântica
  (normal/inverso), subtítulo, ícone, sparkline, barra de progresso contra a
  meta, tooltip de ajuda e três densidades (compacto/padrão/destaque).
• ``render_metric``: assinatura 1:1 com ``st.metric`` (``label``, ``value``,
  ``delta``, ``delta_color``, ``help``) para trocar o componente nativo sem
  reescrever a página.
• ``render_kpi_de_serie``: monta o cartão a partir de uma série diária —
  calcula valor atual, variação contra D-1 e desenho da tendência.
• ``render_kpi_row``: fileira declarativa de cartões (menos ``st.columns``
  repetido nas páginas).
• ``calcular_variacao_pct`` / ``rotulo_tendencia``: matemática pura das
  variações (fonte única — ``components.dashboard_kit`` reutiliza daqui).
• ``css_kpi_avancado``: estilos dos cartões, agregados pelo CSS global
  (``components.css_global``) e injetados uma vez por sessão.

Exemplo::

    from components.kpi_cards import render_kpi_card, render_metric

    render_kpi_card(
        label="Ordens de serviço",
        valor="1.248",
        delta="+12,5%",
        delta_tipo="up",
        sparkline=[980, 1_010, 1_140, 1_120, 1_248],
        progresso=(1_248, 1_500),
        icone="⚡",
        tema="azul",
    )
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from typing import Any, Literal, NotRequired, TypeAlias, TypedDict

import pandas as pd

from components.componentes import (
    ConfigCores,
    Cores,
    TemaKPIType,
    TipoTrendType,
    Validadores,
    _resolver_gradiente,
    _safe_render_html,
    _texto_icone_seguro,
    formatar_numero_br,
    normalizar_tema_kpi,
    normalizar_tipo_trend,
)

logger = logging.getLogger(__name__)

VERSAO_KPI = "1.0.0"

TipoDeltaColorType: TypeAlias = Literal["normal", "inverse", "off"]
TamanhoKPIType: TypeAlias = Literal["compacto", "padrao", "destaque"]

_DENSIDADES: dict[str, dict[str, str]] = {
    "compacto": {"padding": "12px 14px", "valor": "22px", "rotulo": "10px"},
    "padrao": {"padding": "16px 18px", "valor": "30px", "rotulo": "11px"},
    "destaque": {"padding": "20px 22px", "valor": "38px", "rotulo": "12px"},
}

_SETAS: dict[str, str] = {
    "up": "▲",
    "down": "▼",
    "neutral": "■",
    "none": "",
}

_ESCAPAR = Validadores.html_escape


# ====================================================
# 📐 BLOCO 1: MATEMÁTICA PURA DAS VARIAÇÕES
# ====================================================
def calcular_variacao_pct(atual: float | None, anterior: float | None) -> float | None:
    """Variação percentual entre dois valores; ``None`` quando não calculável.

    Retorna a variação em pontos percentuais (ex.: ``12.5`` para +12,5%) e
    preserva o sinal. Retorna ``None`` se algum lado falta, não é finito ou se
    o denominador é zero (diferença absoluta sem base não vira percentual).
    """
    if atual is None or anterior is None:
        return None
    try:
        atual_f = float(atual)
        anterior_f = float(anterior)
    except (TypeError, ValueError, OverflowError):
        return None
    if not (pd.notna(atual_f) and pd.notna(anterior_f)) or anterior_f == 0:
        return None
    if math.isinf(atual_f) or math.isinf(anterior_f):
        return None
    return (atual_f - anterior_f) / abs(anterior_f) * 100.0


def rotulo_tendencia(
    atual: float | None,
    anterior: float | None,
    *,
    casas: int = 1,
    inverso: bool = False,
    tolerancia_pct: float = 0.05,
) -> tuple[str, TipoTrendType]:
    """Rótulo pt-BR + direção de tendência prontos para os cartões de KPI.

    ``inverso=True`` inverte a semântica (para métricas em que "menor é
    melhor", ex.: taxa de quebra). Variações dentro de ``tolerancia_pct``
    são tratadas como neutras para não sugerir movimento espúrio.
    """
    variacao = calcular_variacao_pct(atual, anterior)
    if variacao is None:
        return "", "none"
    rotulo = f"{variacao:+.{casas}f}%".replace(".", ",").replace("-", "−")
    if abs(variacao) < tolerancia_pct:
        return rotulo, "neutral"
    sobe = variacao > 0
    positivo = not sobe if inverso else sobe
    return rotulo, ("up" if positivo else "down")


def direcao_delta(
    delta: Any,
    *,
    delta_color: TipoDeltaColorType = "normal",
) -> TipoTrendType:
    """Converte o ``delta`` textual do padrão ``st.metric`` em direção visual.

    ``delta_color="inverse"`` inverte a cor (métricas em que crescer é ruim);
    ``"off"`` devolve ``"none"`` (delta neutro, sem cor de tendência).
    """
    if delta_color == "off" or delta in (None, ""):
        return "none"
    texto = str(delta).strip()
    if not texto:
        return "none"
    limpo = texto.replace("−", "-").replace("+", "").replace("%", "").replace(".", "").replace(",", ".")
    try:
        valor = float(limpo)
    except ValueError:
        # Delta não numérico ("Sem OS", "novo"): tratado como informação neutra.
        return "neutral"
    if valor == 0:
        return "neutral"
    sobe = valor > 0
    if delta_color == "inverse":
        return "down" if sobe else "up"
    return "up" if sobe else "down"


def resumo_de_serie(
    serie: pd.Series | Sequence[float] | None,
    *,
    casas: int = 0,
    unidade: str = "",
    inverso: bool = False,
) -> dict[str, Any]:
    """Resume uma série diária em valor atual, delta e sparkline.

    Retorna um dicionário pronto para ``render_kpi_de_serie``:

    ``{"valor": str, "delta": str, "delta_tipo": str, "sparkline": list[float],
    "anterior": float | None, "atual": float | None, "pontos": int}``
    """
    vazio: dict[str, Any] = {
        "valor": "—",
        "delta": "",
        "delta_tipo": "none",
        "sparkline": [],
        "anterior": None,
        "atual": None,
        "pontos": 0,
    }
    if serie is None:
        return vazio
    if isinstance(serie, pd.Series):
        numerica = pd.to_numeric(serie, errors="coerce").dropna()
    else:
        numerica = pd.to_numeric(pd.Series(list(serie)), errors="coerce").dropna()
    if numerica.empty:
        return vazio

    atual = float(numerica.iloc[-1])
    anterior = float(numerica.iloc[-2]) if len(numerica) > 1 else None
    delta, direcao = rotulo_tendencia(atual, anterior, casas=1, inverso=inverso)
    sufixo = f" {unidade}" if unidade else ""
    valor = (
        f"{atual:.{casas}f}".replace(".", ",") + sufixo
        if casas > 0
        else formatar_numero_br(atual) + sufixo
    )
    return {
        "valor": valor,
        "delta": delta,
        "delta_tipo": direcao,
        "sparkline": [float(v) for v in numerica.tail(30)],
        "anterior": anterior,
        "atual": atual,
        "pontos": int(len(numerica)),
    }


# ====================================================
# 📈 BLOCO 2: SPARKLINE EM SVG (SEM PLOTLY, SEM PESO)
# ====================================================
def sparkline_svg(
    valores: Sequence[float] | pd.Series | None,
    *,
    cor: str = Cores.PRIMARIA,
    largura: int = 132,
    altura: int = 34,
    espessura: float = 1.8,
    area: bool = True,
    ponto_final: bool = True,
    rotulo: str = "Tendência recente",
) -> str:
    """Desenha uma sparkline em SVG inline (string vazia se não houver série).

    SVG inline custa ~300 bytes e não carrega runtime de gráfico — ideal para
    cartões de KPI repetidos em fileiras de 4 a 6 colunas.
    """
    if valores is None:
        return ""
    if isinstance(valores, pd.Series):
        numerica = pd.to_numeric(valores, errors="coerce").dropna()
        pontos_y = [float(v) for v in numerica]
    else:
        pontos_y = []
        for bruto in valores:
            try:
                numero = float(bruto)
            except (TypeError, ValueError):
                continue
            if not math.isnan(numero):
                pontos_y.append(numero)
    if len(pontos_y) < 2:
        return ""

    minimo, maximo = min(pontos_y), max(pontos_y)
    amplitude = maximo - minimo
    margem = 3.0
    largura_util = max(1.0, float(largura))
    altura_util = max(1.0, float(altura) - 2 * margem)
    passo_x = largura_util / (len(pontos_y) - 1)

    coordenadas: list[tuple[float, float]] = []
    for indice, valor in enumerate(pontos_y):
        x = round(indice * passo_x, 2)
        if amplitude <= 0:
            y = round(margem + altura_util / 2, 2)
        else:
            y = round(margem + altura_util - ((valor - minimo) / amplitude) * altura_util, 2)
        coordenadas.append((x, y))

    linha = " ".join(f"{x},{y}" for x, y in coordenadas)
    ultimo_x, ultimo_y = coordenadas[-1]
    partes = [
        f'<svg class="kpi-avancado__spark-svg" viewBox="0 0 {largura} {altura}" '
        f'width="100%" height="{altura}" preserveAspectRatio="none" '
        f'role="img" aria-label="{_ESCAPAR(rotulo)}">',
        f'<polyline points="{linha}" fill="none" stroke="{cor}" '
        f'stroke-width="{espessura}" stroke-linecap="round" stroke-linejoin="round" '
        'vector-effect="non-scaling-stroke" opacity="0.95"/>',
    ]
    if area:
        base = float(altura)
        caminho = (
            f"M{coordenadas[0][0]},{coordenadas[0][1]} "
            + " ".join(f"L{x},{y}" for x, y in coordenadas[1:])
            + f" L{ultimo_x},{base} L{coordenadas[0][0]},{base} Z"
        )
        partes.insert(1, f'<path d="{caminho}" fill="{cor}" opacity="0.12"/>')
    if ponto_final:
        partes.append(
            f'<circle cx="{ultimo_x}" cy="{ultimo_y}" r="2.6" fill="{cor}" '
            'stroke="#FFFFFF" stroke-width="1.2"/>'
        )
    partes.append("</svg>")
    return "".join(partes)


# ====================================================
# 🧱 BLOCO 3: CARTÃO DE KPI AVANÇADO
# ====================================================
def _barra_progresso(
    valor: float,
    meta: float,
    *,
    cor: str,
    cor_texto: str,
    mostrar_rotulo: bool = True,
) -> str:
    """Barra fina de atingimento (valor × meta) com percentual em pt-BR."""
    if meta <= 0:
        return ""
    proporcao = max(0.0, min(1.0, valor / meta))
    percentual = proporcao * 100.0
    rotulo = (
        f'<span class="kpi-avancado__progresso-txt" style="color:{cor_texto};">'
        f'{formatar_numero_br(percentual, 1)}% da meta</span>'
        if mostrar_rotulo
        else ""
    )
    return (
        '<div class="kpi-avancado__progresso">'
        f'<div class="kpi-avancado__trilho" style="background:{cor_texto}22;">'
        f'<div class="kpi-avancado__cheio" style="width:{percentual:.2f}%;background:{cor};"></div>'
        f"</div>{rotulo}</div>"
    )


def _delta_html(delta: Any, direcao: TipoTrendType, cor_texto: str) -> str:
    texto = "" if delta is None else str(delta).strip()
    if not texto:
        return ""
    seta = _SETAS.get(direcao, "")
    classe_cor = {
        "up": "kpi-avancado__delta--up",
        "down": "kpi-avancado__delta--down",
        "neutral": "kpi-avancado__delta--neutro",
        "none": "kpi-avancado__delta--neutro",
    }.get(direcao, "kpi-avancado__delta--neutro")
    return (
        f'<span class="kpi-avancado__delta {classe_cor}" style="--kpi-delta-fg:{cor_texto};">'
        f'<span aria-hidden="true">{seta}</span>{_ESCAPAR(texto)}</span>'
    )


def render_kpi_card(
    container: Any = None,
    *,
    label: str,
    valor: str,
    delta: Any = None,
    delta_tipo: TipoTrendType | None = None,
    delta_color: TipoDeltaColorType = "normal",
    sub: str = "",
    icone: str = "",
    tema: TemaKPIType = "azul",
    colorida: bool = False,
    sparkline: Sequence[float] | pd.Series | None = None,
    progresso: float | tuple[float, float] | None = None,
    meta_rotulo: str = "",
    ajuda: str = "",
    tamanho: TamanhoKPIType = "padrao",
    rodape: str = "",
) -> None:
    """Cartão de KPI avançado (substituto rico do ``st.metric``).

    Args:
        container: coluna/container do Streamlit (usa a raiz quando ``None``).
        label: rótulo curto em caixa alta (ex.: ``"ORDENS DE SERVIÇO"``).
        valor: valor já formatado em pt-BR (ex.: ``"1.248"``).
        delta: variação textual (``"+12,5%"``, ``"−3 p.p."``, ``"Sem OS"``).
        delta_tipo: direção explícita (``up``/``down``/``neutral``/``none``);
            quando omitida, é deduzida de ``delta`` + ``delta_color``.
        delta_color: ``"normal"`` (subir é bom), ``"inverse"`` (subir é ruim)
            ou ``"off"`` (sem cor) — mesma semântica do ``st.metric``.
        sub: texto de apoio abaixo do valor (contexto/período).
        icone: emoji ou ligadura Material Symbols (ex.: ``"⚡"``, ``"trending_up"``).
        tema: família de cor (``azul``, ``laranja``, ``verde``, ``vermelho``,
            ``roxo``, ``cinza``, ``gradiente``).
        colorida: pinta o cartão com o gradiente do tema (texto branco).
        sparkline: série de valores para o mini-gráfico de tendência em SVG.
        progresso: percentual (0–100) ou par ``(valor, meta)`` para a barra.
        meta_rotulo: texto opcional exibido no rodapé da barra de progresso.
        ajuda: tooltip nativo (``title``) com a definição da métrica.
        tamanho: densidade do cartão (``compacto``, ``padrao``, ``destaque``).
        rodape: linha final discreta (fonte da métrica, atualizado em…).
    """
    tema_norm = normalizar_tema_kpi(tema)
    cor_inicio, cor_fim = _resolver_gradiente(tema_norm)
    densidade = _DENSIDADES.get(str(tamanho).strip().lower(), _DENSIDADES["padrao"])
    cor_acento = ConfigCores.TEMA.get(tema_norm, Cores.PRIMARIA)

    if colorida or tema_norm == "gradiente":
        fundo = f"linear-gradient(155deg, {cor_inicio} 0%, {cor_inicio} 58%, {cor_fim} 140%)"
        cor_texto = "#FFFFFF"
        cor_rotulo = "rgba(255,255,255,0.80)"
        cor_borda = "rgba(255,255,255,0.16)"
        fundo_icone = "rgba(255,255,255,0.16)"
        cor_faixa = Cores.SECUNDARIA if tema_norm != "laranja" else "#FFFFFF"
        classes_extra = " kpi-avancado--colorida"
        cor_spark = Cores.SECUNDARIA_LIGHT
    else:
        fundo = "#FFFFFF"
        cor_texto = Cores.TEXTO
        cor_rotulo = Cores.TEXTO_3
        cor_borda = Cores.BORDA
        fundo_icone = f"{cor_inicio}14"
        cor_faixa = cor_acento
        classes_extra = ""
        cor_spark = cor_acento

    direcao: TipoTrendType = (
        normalizar_tipo_trend(delta_tipo)
        if delta_tipo
        else direcao_delta(delta, delta_color=delta_color)
    )

    icone_seguro = _texto_icone_seguro(icone) if icone else ""
    icone_html = (
        f'<span class="kpi-avancado__icone" style="background:{fundo_icone};color:{cor_texto};">'
        f'<span class="totale-icon-glyph" aria-hidden="true">{_ESCAPAR(icone_seguro)}</span></span>'
        if icone_seguro
        else ""
    )
    ajuda_html = (
        f'<span class="kpi-avancado__ajuda" title="{_ESCAPAR(ajuda)}" '
        f'style="color:{cor_rotulo};" aria-label="{_ESCAPAR(ajuda)}">ⓘ</span>'
        if ajuda
        else ""
    )

    barra_html = ""
    if progresso is not None:
        if isinstance(progresso, (tuple, list)) and len(progresso) == 2:
            try:
                valor_barra, meta_barra = float(progresso[0]), float(progresso[1])
            except (TypeError, ValueError):
                valor_barra, meta_barra = 0.0, 0.0
            barra_html = _barra_progresso(valor_barra, meta_barra, cor=cor_acento, cor_texto=cor_texto)
        else:
            try:
                percentual = float(progresso)
            except (TypeError, ValueError):
                percentual = 0.0
            barra_html = _barra_progresso(
                percentual, 100.0, cor=cor_acento, cor_texto=cor_texto, mostrar_rotulo=False
            )
        if barra_html and meta_rotulo:
            barra_html = barra_html.replace(
                "</div></div>",
                f'<span class="kpi-avancado__meta-txt" style="color:{cor_rotulo};">'
                f"{_ESCAPAR(meta_rotulo)}</span></div></div>",
                1,
            )

    spark_html = (
        f'<div class="kpi-avancado__spark">{sparkline_svg(sparkline, cor=cor_spark)}</div>'
        if sparkline is not None and sparkline_svg(sparkline, cor=cor_spark)
        else ""
    )
    rodape_html = (
        f'<div class="kpi-avancado__rodape" style="color:{cor_rotulo};">{_ESCAPAR(rodape)}</div>'
        if rodape
        else ""
    )
    sub_html = (
        f'<span class="kpi-avancado__sub" style="color:{cor_rotulo};">{_ESCAPAR(sub)}</span>'
        if sub
        else ""
    )
    linha_inferior = _delta_html(delta, direcao, cor_texto) + sub_html
    linha_html = (
        f'<div class="kpi-avancado__linha">{linha_inferior}</div>' if linha_inferior else ""
    )

    classes = f"kpi-avancado kpi-avancado--{tamanho}{classes_extra}"
    markup = (
        f'<div class="{classes}" role="group" '
        f'aria-label="{_ESCAPAR(label)}: {_ESCAPAR(str(valor))}" '
        f'style="background:{fundo};color:{cor_texto};border-color:{cor_borda};'
        f'padding:{densidade["padding"]};">'
        f'<span class="kpi-avancado__faixa" style="background:{cor_faixa};"></span>'
        '<div class="kpi-avancado__topo">'
        f'<span class="kpi-avancado__rotulo" style="color:{cor_rotulo};'
        f'font-size:{densidade["rotulo"]};">{_ESCAPAR(label)}{ajuda_html}</span>'
        f"{icone_html}</div>"
        f'<div class="kpi-avancado__valor" style="font-size:{densidade["valor"]};'
        f'color:{cor_texto};">{_ESCAPAR(str(valor))}</div>'
        f"{linha_html}{barra_html}{spark_html}{rodape_html}</div>"
    )
    _safe_render_html(markup, container)


def render_metric(
    label: str,
    value: Any = "",
    delta: Any = None,
    delta_color: TipoDeltaColorType = "normal",
    help: str | None = None,  # noqa: A002 - paridade com st.metric
    *,
    container: Any = None,
    tema: TemaKPIType = "azul",
    icone: str = "",
    colorida: bool = False,
    sparkline: Sequence[float] | pd.Series | None = None,
    progresso: float | tuple[float, float] | None = None,
    meta_rotulo: str = "",
    tamanho: TamanhoKPIType = "padrao",
    sub: str = "",
    rodape: str = "",
) -> None:
    """Substituto direto de ``st.metric`` com o acabamento TOTALE.

    Aceita os mesmos argumentos posicionais do componente nativo — trocar é
    apenas substituir ``st.metric(...)`` por ``render_metric(...)``::

        # antes
        st.metric("Municípios", 12)
        # depois
        render_metric("Municípios", 12, icone="🏙️", tema="laranja")

    Os parâmetros extras (``sparkline``, ``progresso``, ``meta_rotulo``,
    ``rodape``, ``tamanho``, ``sub``) são opcionais e ativam os recursos dos
    cartões avançados sem mudar a chamada mínima.
    """
    if isinstance(value, bool):
        valor_txt = "Sim" if value else "Não"
    elif isinstance(value, float):
        valor_txt = formatar_numero_br(value, 2 if abs(value) < 10 else 0)
    elif isinstance(value, int) or pd.api.types.is_integer(value):
        valor_txt = formatar_numero_br(value)
    elif isinstance(value, (pd.Timestamp,)):
        valor_txt = value.strftime("%d/%m/%Y")
    else:
        valor_txt = str(value) if value not in (None, "") else "—"
    render_kpi_card(
        container,
        label=str(label or ""),
        valor=valor_txt,
        delta=delta,
        delta_color=delta_color,
        ajuda=str(help or ""),
        tema=tema,
        icone=icone,
        colorida=colorida,
        sparkline=sparkline,
        progresso=progresso,
        meta_rotulo=meta_rotulo,
        tamanho=tamanho,
        sub=sub,
        rodape=rodape,
    )


def render_kpi_de_serie(
    container: Any = None,
    *,
    label: str,
    serie: pd.Series | Sequence[float] | None,
    unidade: str = "",
    casas: int = 0,
    inverso: bool = False,
    tema: TemaKPIType = "azul",
    icone: str = "",
    colorida: bool = False,
    ajuda: str = "",
    progresso: float | tuple[float, float] | None = None,
    tamanho: TamanhoKPIType = "padrao",
    mostrar_sparkline: bool = True,
) -> None:
    """Cartão de KPI derivado de uma série (valor atual + delta + tendência).

    Útil para painéis que já têm a série diária calculada: o cartão mostra o
    último valor, a variação contra o ponto anterior e o desenho dos últimos
    30 pontos — sem Plotly e sem custo extra de renderização.
    """
    resumo = resumo_de_serie(serie, casas=casas, unidade=unidade, inverso=inverso)
    sub = (
        f"{resumo['pontos']} dia(s) no recorte"
        if resumo["pontos"]
        else "Sem histórico no recorte atual"
    )
    render_kpi_card(
        container,
        label=label,
        valor=str(resumo["valor"]),
        delta=resumo["delta"] or None,
        delta_tipo=resumo["delta_tipo"],
        sub=sub,
        icone=icone,
        tema=tema,
        colorida=colorida,
        sparkline=resumo["sparkline"] if mostrar_sparkline else None,
        progresso=progresso,
        ajuda=ajuda,
        tamanho=tamanho,
    )


class SpecKPIAvancado(TypedDict):
    """Especificação declarativa de um cartão avançado (ver ``render_kpi_row``)."""

    label: str
    valor: str
    delta: NotRequired[Any]
    delta_tipo: NotRequired[TipoTrendType]
    delta_color: NotRequired[TipoDeltaColorType]
    sub: NotRequired[str]
    icone: NotRequired[str]
    tema: NotRequired[TemaKPIType]
    colorida: NotRequired[bool]
    sparkline: NotRequired[Sequence[float] | pd.Series | None]
    progresso: NotRequired[float | tuple[float, float] | None]
    meta_rotulo: NotRequired[str]
    ajuda: NotRequired[str]
    tamanho: NotRequired[TamanhoKPIType]
    rodape: NotRequired[str]


def render_kpi_row(
    specs: Sequence[SpecKPIAvancado],
    *,
    colunas: int | None = None,
    gap: str = "small",
    container: Any = None,
) -> None:
    """Renderiza uma fileira de cartões avançados a partir de especificações.

    Com mais cartões do que colunas, a fileira quebra em linhas seguintes
    mantendo o mesmo espaçamento (evita ``st.columns`` manual nas páginas).
    """
    import streamlit as st

    if not specs:
        return
    alvo = container if container is not None else st
    quantidade = max(1, int(colunas or len(specs)))
    for inicio in range(0, len(specs), quantidade):
        lote = list(specs[inicio : inicio + quantidade])
        grade = alvo.columns(quantidade, gap=gap)
        for posicao, spec in enumerate(lote):
            render_kpi_card(
                grade[posicao],
                label=spec["label"],
                valor=str(spec["valor"]),
                delta=spec.get("delta"),
                delta_tipo=spec.get("delta_tipo"),
                delta_color=spec.get("delta_color", "normal"),
                sub=spec.get("sub", ""),
                icone=spec.get("icone", ""),
                tema=spec.get("tema", "azul"),
                colorida=spec.get("colorida", False),
                sparkline=spec.get("sparkline"),
                progresso=spec.get("progresso"),
                meta_rotulo=spec.get("meta_rotulo", ""),
                ajuda=spec.get("ajuda", ""),
                tamanho=spec.get("tamanho", "padrao"),
                rodape=spec.get("rodape", ""),
            )


# ====================================================
# 🎨 BLOCO 4: CSS DOS CARTÕES (AGREGADO PELO CSS GLOBAL)
# ====================================================
def css_kpi_avancado() -> str:
    """Estilos dos cartões de KPI avançados (escopados no corpo da página)."""
    return f"""
    /* ============================================================
       KPI AVANÇADO v{VERSAO_KPI} — substituto do st.metric
       ============================================================ */
    [data-testid="stMain"] .kpi-avancado {{
        position: relative;
        display: flex;
        flex-direction: column;
        gap: 8px;
        border: 1px solid var(--cor-borda, {Cores.BORDA});
        border-radius: 14px;
        min-height: 118px;
        overflow: hidden;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 20px rgba(15, 23, 42, 0.04);
        transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
        contain: paint;
    }}
    [data-testid="stMain"] .kpi-avancado:hover {{
        transform: translateY(-2px);
        box-shadow: 0 14px 30px rgba(1, 40, 105, 0.13);
        border-color: rgba(1, 40, 105, 0.18);
    }}
    [data-testid="stMain"] .kpi-avancado--compacto {{ min-height: 0; gap: 6px; }}
    [data-testid="stMain"] .kpi-avancado__faixa {{
        position: absolute; top: 0; left: 0; right: 0; height: 3px; z-index: 2;
    }}
    [data-testid="stMain"] .kpi-avancado__topo {{
        display: flex; align-items: flex-start; justify-content: space-between;
        gap: 10px; position: relative; z-index: 2;
    }}
    [data-testid="stMain"] .kpi-avancado__rotulo {{
        display: flex; align-items: center; gap: 6px;
        font-weight: 750; letter-spacing: .07em; text-transform: uppercase;
        line-height: 1.35; min-width: 0;
    }}
    [data-testid="stMain"] .kpi-avancado__ajuda {{
        cursor: help; font-size: 12px; line-height: 1; opacity: .8; flex-shrink: 0;
    }}
    [data-testid="stMain"] .kpi-avancado__icone {{
        width: 32px; height: 32px; border-radius: 10px; flex-shrink: 0;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 15px; line-height: 1;
        transition: transform .2s ease;
    }}
    [data-testid="stMain"] .kpi-avancado:hover .kpi-avancado__icone {{
        transform: scale(1.07) rotate(-3deg);
    }}
    [data-testid="stMain"] .kpi-avancado__valor {{
        font-family: var(--font-titulo);
        font-weight: 800; letter-spacing: -.04em; line-height: 1.05;
        font-variant-numeric: tabular-nums; position: relative; z-index: 2;
        overflow-wrap: anywhere;
    }}
    [data-testid="stMain"] .kpi-avancado__linha {{
        display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
        position: relative; z-index: 2;
    }}
    [data-testid="stMain"] .kpi-avancado__delta {{
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 8px; border-radius: 999px;
        font-size: 11px; font-weight: 800; line-height: 1.15;
        font-variant-numeric: tabular-nums; white-space: nowrap;
    }}
    [data-testid="stMain"] .kpi-avancado__delta--up {{
        background: #ECFDF5; color: {Cores.SUCESSO};
    }}
    [data-testid="stMain"] .kpi-avancado__delta--down {{
        background: #FEF2F2; color: {Cores.ALERTA};
    }}
    [data-testid="stMain"] .kpi-avancado__delta--neutro {{
        background: #F1F5F9; color: {Cores.NEUTRO};
    }}
    [data-testid="stMain"] .kpi-avancado--colorida .kpi-avancado__delta--up {{
        background: rgba(255, 255, 255, 0.20); color: #D1FAE5;
    }}
    [data-testid="stMain"] .kpi-avancado--colorida .kpi-avancado__delta--down {{
        background: rgba(255, 255, 255, 0.20); color: #FECACA;
    }}
    [data-testid="stMain"] .kpi-avancado--colorida .kpi-avancado__delta--neutro {{
        background: rgba(255, 255, 255, 0.16); color: #FFFFFF;
    }}
    [data-testid="stMain"] .kpi-avancado__sub {{
        font-size: 12px; line-height: 1.45; min-width: 0;
    }}
    [data-testid="stMain"] .kpi-avancado__progresso {{
        display: flex; flex-direction: column; gap: 4px;
        position: relative; z-index: 2; margin-top: 2px;
    }}
    [data-testid="stMain"] .kpi-avancado__trilho {{
        width: 100%; height: 6px; border-radius: 999px; overflow: hidden;
    }}
    [data-testid="stMain"] .kpi-avancado__cheio {{
        height: 100%; border-radius: 999px;
        transition: width .35s ease;
    }}
    [data-testid="stMain"] .kpi-avancado__progresso-txt {{
        font-size: 10.5px; font-weight: 750; letter-spacing: .02em;
        font-variant-numeric: tabular-nums;
    }}
    [data-testid="stMain"] .kpi-avancado__meta-txt {{
        font-size: 10.5px; opacity: .8;
    }}
    [data-testid="stMain"] .kpi-avancado__spark {{
        margin-top: auto; position: relative; z-index: 2; line-height: 0;
    }}
    [data-testid="stMain"] .kpi-avancado__spark-svg {{ display: block; width: 100%; }}
    [data-testid="stMain"] .kpi-avancado__rodape {{
        font-size: 10.5px; letter-spacing: .02em; position: relative; z-index: 2;
        border-top: 1px dashed rgba(100, 116, 139, 0.28); padding-top: 6px; margin-top: 2px;
    }}
    [data-testid="stMain"] .kpi-avancado--colorida .kpi-avancado__rodape {{
        border-top-color: rgba(255, 255, 255, 0.24);
    }}
    @media (max-width: 640px) {{
        [data-testid="stMain"] .kpi-avancado__valor {{ font-size: 24px !important; }}
    }}
    @media print {{
        [data-testid="stMain"] .kpi-avancado {{ break-inside: avoid; box-shadow: none; }}
    }}
    """


__all__ = [
    "SpecKPIAvancado",
    "TamanhoKPIType",
    "TipoDeltaColorType",
    "VERSAO_KPI",
    "calcular_variacao_pct",
    "css_kpi_avancado",
    "direcao_delta",
    "render_kpi_card",
    "render_kpi_de_serie",
    "render_kpi_row",
    "render_metric",
    "resumo_de_serie",
    "rotulo_tendencia",
    "sparkline_svg",
]
