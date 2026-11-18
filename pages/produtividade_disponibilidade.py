"""pages/produtividade_disponibilidade.py
========================================
Produtividade × Disponibilidade | TOTALE — produção por técnico-dia.

Versão: 1.0.0
Autor: TOTALE Tecnologia

O que esta página responde
--------------------------
Quanta produção a equipe entrega **por técnico-dia disponível** e quanto do
tempo previsto foi consumido por ausências. É o cruzamento que faltava entre a
produção (``Prod``) e o controle de presença (``controle_absenteismo``), com o
headcount da ``lista_ativos`` como denominador.

Decisões de escopo (alinhadas à proposta D3):

* o resultado é **agregado por supervisor/base** — nunca ranking individual de
  saúde, motivo ou atestado;
* ausência programada (folga, férias, treinamento) é separada da não programada
  (falta, atestado, afastamento...) na quebra por tipo;
* a produtividade é relativa (O.S. ÷ técnico-dia), não um volume absoluto que
  premia quem tem mais gente;
* quando a amostra não sustenta a comparação, a página diz isso em vez de
  desenhar um gráfico enganoso.

Toda a regra vive em :mod:`services.produtividade` (camada pura, testada sem
Streamlit). Aqui ficam apenas filtros, estado, apresentação e exportação.
"""

from __future__ import annotations

import logging
import textwrap
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_insight,
    render_table_html,
)
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.graficos import criar_grafico, render_grafico, render_graficos_em_abas
from components.kpi_cards import render_kpi_row
from components.layout_pagina import render_abas, secao
from components.sidebar import render_page_sidebar_theme_selector
from services.absenteismo import registros_da_sessao, registros_vazios
from services.dados_sessao import exigir_base, resumir_carga
from services.hierarquia import lista_ativos_da_sessao
from services.produtividade import (
    consolidar,
    gerar_insights,
    normalizar_producao,
    rotulo_dimensao,
)
from services.texto import formatar_inteiro, formatar_numero, formatar_percentual

logger = logging.getLogger(__name__)

VERSAO_PAGINA = "1.0.0"
PAGINA = "Produtividade & Disponibilidade"

SECOES_PAGINA: tuple[str, ...] = (
    "Indicadores",
    "Produtividade × Disponibilidade",
    "Ausências",
    "Evolução",
    "Detalhe por Supervisor",
    "Exportação",
)

#: Abaixo disso, dispersão/leitura comparativa viram ruído: mostramos o aviso.
AMOSTRA_MINIMA_COMPARACAO = 3

#: Quantos supervisores cabem sem transformar o gráfico em lista telefônica.
LIMITE_RANKING = 12

CHAVES_FILTRO: tuple[str, ...] = (
    "produtividade_inicio",
    "produtividade_fim",
    "produtividade_bases",
    "produtividade_supervisores",
    "produtividade_tipos",
)

ORIGEM_QUADRO: dict[str, str] = {
    "lista_ativos": "lista de ativos",
    "presença": "registros de presença (inferido)",
    "indisponível": "indisponível",
}

FMT_TABELA: dict[str, Any] = {
    "Quadro": formatar_inteiro,
    "Dias Ausência": formatar_inteiro,
    "Ausentes": formatar_inteiro,
    "Absenteísmo (%)": lambda valor: _texto_percentual(valor),
    "Técnico-dia Disponível": lambda valor: _texto_numero(valor, 0),
    "O.S.": formatar_inteiro,
    "Pontos": lambda valor: _texto_numero(valor, 0),
    "O.S./téc-dia": lambda valor: _texto_numero(valor, 2),
    "Pontos/téc-dia": lambda valor: _texto_numero(valor, 1),
    "O.S. Estimadas Perdidas": lambda valor: _texto_numero(valor, 0),
}

COLUNAS_NUMERICAS: tuple[str, ...] = (
    "Quadro",
    "Dias Ausência",
    "Ausentes",
    "Absenteísmo (%)",
    "Técnico-dia Disponível",
    "O.S.",
    "Pontos",
    "O.S./téc-dia",
    "Pontos/téc-dia",
    "O.S. Estimadas Perdidas",
)

st.set_page_config(page_title=PAGINA, page_icon="⚖️", layout="wide")
aplicar_estilo()
render_page_sidebar_theme_selector()


# ====================================================
# 🧰 BLOCO 1: FORMATAÇÃO E VARIAÇÕES
# ====================================================
def _texto_numero(valor: Any, casas: int = 1) -> str:
    """Número pt-BR ou ``—`` quando não calculável."""
    if valor is None or pd.isna(valor):
        return "—"
    return formatar_numero(float(valor), casas)


def _texto_percentual(valor: Any, casas: int = 1) -> str:
    if valor is None or pd.isna(valor):
        return "—"
    return formatar_percentual(float(valor), casas)


def _variacao_percentual(atual: float | None, anterior: float | None) -> float | None:
    if atual is None or anterior is None or pd.isna(atual) or pd.isna(anterior):
        return None
    if abs(float(anterior)) < 1e-9:
        return None
    return (float(atual) - float(anterior)) / abs(float(anterior)) * 100.0


def _variacao_pontos(atual: float | None, anterior: float | None) -> float | None:
    if atual is None or anterior is None or pd.isna(atual) or pd.isna(anterior):
        return None
    return float(atual) - float(anterior)


def _rotulo_variacao(valor: float | None, *, sufixo: str = "%", casas: int = 1) -> str:
    if valor is None or pd.isna(valor):
        return ""
    texto = formatar_numero(float(valor), casas)
    if valor > 0:
        texto = f"+{texto}"
    return f"{texto}{sufixo}"


def _direcao(valor: float | None, *, subir_e_bom: bool) -> str:
    if valor is None or pd.isna(valor) or abs(float(valor)) < 1e-9:
        return "neutral"
    positivo = float(valor) > 0
    return "up" if positivo == subir_e_bom else "down"


# ====================================================
# 🗓️ BLOCO 2: PERÍODO E CARGA DAS FONTES
# ====================================================
def _periodo_padrao(producao: pd.DataFrame) -> tuple[date, date]:
    """Últimos 30 dias até a última data de produção (ou hoje, sem data)."""
    datas = producao["Data"].dropna() if "Data" in producao.columns else pd.Series(dtype="object")
    if datas.empty:
        fim = date.today()
        return fim - timedelta(days=29), fim
    fim = pd.Timestamp(datas.max()).date()
    inicio = fim - timedelta(days=29)
    minima = pd.Timestamp(datas.min()).date()
    return max(inicio, minima), fim


def _carregar_presenca() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Presença e quadro são opcionais: a página calcula e avisa o que faltou."""
    aviso = ""
    try:
        registros = registros_da_sessao()
    except Exception:  # pragma: no cover - depende de rede/credenciais
        logger.exception("Falha ao carregar o controle de absenteísmo.")
        registros = registros_vazios()
        aviso = (
            "Não foi possível ler o controle de absenteísmo nesta sessão. "
            "A disponibilidade foi considerada integral; confira a conexão com o Sheets."
        )

    try:
        lista_ativos = lista_ativos_da_sessao()
    except Exception:  # pragma: no cover - depende de rede/credenciais
        logger.exception("Falha ao carregar a lista de ativos.")
        lista_ativos = pd.DataFrame()
        aviso += (
            "Não foi possível ler a lista de ativos. Sem o quadro, o denominador de "
            "técnico-dia fica indisponível — a produção continua sendo exibida."
        )
    return registros, lista_ativos, aviso


def _opcoes(valores: Sequence[Any]) -> list[str]:
    """Opções canônicas (caixa alta, sem acento, sem vazio) para os filtros."""
    vazios = {"", "NAN", "NONE", "<NA>", "NAT", "N/A"}
    opcoes: set[str] = set()
    for valor in valores:
        if valor is None or valor is pd.NA or valor is pd.NaT:
            continue
        if isinstance(valor, float) and pd.isna(valor):
            continue
        texto = str(valor).strip()
        if texto.upper() in vazios:
            continue
        opcoes.add(rotulo_dimensao(texto))
    return sorted(opcoes)


# Base de produção da sessão é a guarda de entrada padrão do portal.
df_producao = exigir_base(pagina=PAGINA)
producao = normalizar_producao(df_producao)

with st.spinner("Carregando presença e quadro de ativos..."):
    registros, lista_ativos, aviso_fontes = _carregar_presenca()

inicio_padrao, fim_padrao = _periodo_padrao(producao)


# ====================================================
# 🎛️ BLOCO 3: FILTROS (SIDEBAR)
# ====================================================
with st.sidebar:
    st.markdown("### Filtros do painel")
    st.caption("Período, base, supervisor e tipos afetam todos os blocos da página.")
    st.markdown("#### Calendário operacional")
    nomes_dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    dias_selecionados = st.multiselect(
        "Dias de operação", nomes_dias, default=nomes_dias[:5],
        help="Calendário comum para todo o quadro; não substitui escalas individuais.",
    )
    feriados_texto = st.text_area(
        "Feriados e datas não operacionais", placeholder="25/12/2026, 01/01/2027",
        help="Informe datas separadas por vírgulas ou linhas, incluindo períodos comparados.",
    )
    try:
        feriados = tuple(pd.to_datetime(item.strip(), format="%d/%m/%Y", errors="raise").date()
                         for item in feriados_texto.replace("\n", ",").split(",") if item.strip())
    except (ValueError, TypeError):
        st.error("Datas inválidas. Use DD/MM/AAAA, separadas por vírgula ou linha.")
        st.stop()
    if not dias_selecionados:
        st.error("Selecione pelo menos um dia de operação.")
        st.stop()
    dias_semana = tuple(nomes_dias.index(dia) for dia in dias_selecionados)
    comparacao = st.selectbox("Comparar com", ["Período anterior", "Semana anterior", "Mês anterior"],
                              help="Semana ou mês anterior desloca as duas datas do recorte.")
    inicio = st.date_input("Início do período", key="produtividade_inicio", value=inicio_padrao)
    fim = st.date_input("Fim do período", key="produtividade_fim", value=fim_padrao)
    if fim < inicio:
        inicio, fim = fim, inicio

    bases_producao = _opcoes(producao["Base"].tolist()) if not producao.empty else []
    bases_quadro = _opcoes(lista_ativos["BASE"].tolist()) if "BASE" in lista_ativos.columns else []
    bases_sel = st.multiselect(
        "Base",
        _opcoes(bases_producao + bases_quadro),
        key="produtividade_bases",
        placeholder="Todas as bases",
    )

    supervisores_producao = _opcoes(producao["Supervisor"].tolist()) if not producao.empty else []
    supervisores_quadro = (
        _opcoes(lista_ativos["MONITOR"].tolist()) if "MONITOR" in lista_ativos.columns else []
    )
    supervisores_sel = st.multiselect(
        "Supervisor / monitor",
        _opcoes(supervisores_producao + supervisores_quadro),
        key="produtividade_supervisores",
        placeholder="Todos os supervisores",
    )

    tipos_sel = st.multiselect(
        "Tipos de ausência considerados",
        [
            "Falta",
            "Folga",
            "Férias",
            "Atestado",
            "Afastamento",
            "Licença",
            "Suspensão",
            "Treinamento",
            "Outros",
        ],
        key="produtividade_tipos",
        placeholder="Todos os tipos",
        help="Vazio considera todos. A quebra por tipo separa programadas e não programadas.",
    )

    if st.button("Limpar filtros", key="produtividade_limpar"):
        for chave in CHAVES_FILTRO:
            st.session_state.pop(chave, None)
        st.rerun()

    if st.button("🔄 Recarregar presença e quadro", key="produtividade_recarregar"):
        try:
            registros = registros_da_sessao(forcar=True)
            lista_ativos = lista_ativos_da_sessao(forcar=True)
        except Exception:
            logger.exception("Falha ao recarregar presença e quadro.")
            st.warning(
                "Não foi possível recarregar agora. O recorte atual continua na tela; "
                "confira a conexão com o Sheets e tente novamente."
            )
        else:
            st.rerun()

    st.divider()
    st.caption(
        f"**{len(registros):,}** registros de presença · "
        f"**{len(lista_ativos):,}** técnicos na lista".replace(",", ".")
    )


# ====================================================
# 🧮 BLOCO 4: CONSOLIDAÇÃO (RECORTE E PERÍODO ANTERIOR)
# ====================================================
filtros = {
    "inicio": inicio,
    "fim": fim,
    "tipos": tipos_sel or None,
    "bases": bases_sel or None,
    "supervisores": supervisores_sel or None,
    "dias_semana": dias_semana,
    "feriados": feriados,
}
atual = consolidar(producao, registros, lista_ativos, **filtros)

duracao = (fim - inicio).days + 1
fim_anterior = inicio - timedelta(days=1)
inicio_anterior = fim_anterior - timedelta(days=duracao - 1)
if comparacao == "Semana anterior":
    inicio_anterior, fim_anterior = inicio - timedelta(days=7), fim - timedelta(days=7)
elif comparacao == "Mês anterior":
    inicio_anterior = (pd.Timestamp(inicio) - pd.DateOffset(months=1)).date()
    fim_anterior = (pd.Timestamp(fim) - pd.DateOffset(months=1)).date()
    if inicio.day == 1 and fim == (pd.Timestamp(fim) + pd.offsets.MonthEnd(0)).date():
        fim_anterior = (pd.Timestamp(fim_anterior) + pd.offsets.MonthEnd(0)).date()
anterior = consolidar(
    producao,
    registros,
    lista_ativos,
    **{**filtros, "inicio": inicio_anterior, "fim": fim_anterior},
)

avisos = list(atual.avisos)
if aviso_fontes:
    avisos.insert(0, aviso_fontes)

programados = (
    atual.por_tipo.loc[atual.por_tipo["Natureza"].eq("Programada"), "Dias"].sum()
    if not atual.por_tipo.empty and "Natureza" in atual.por_tipo.columns
    else 0
)
participacao_programada = (
    float(programados) / atual.dias_ausencia * 100.0 if atual.dias_ausencia else 0.0
)
disponibilidade = 100.0 - atual.taxa_absenteismo if atual.taxa_absenteismo is not None else None
disponibilidade_anterior = (
    100.0 - anterior.taxa_absenteismo if anterior.taxa_absenteismo is not None else None
)
# Não inferir cobertura temporal completa apenas porque há datas válidas.
datas_producao = producao["Data"].dropna()
presenca_verificavel = not registros.empty and not aviso_fontes
comparacao_confiavel = (
    presenca_verificavel and not datas_producao.empty and not producao["Data"].isna().any()
    and datas_producao.min().date() <= min(inicio, inicio_anterior)
    and datas_producao.max().date() >= max(fim, fim_anterior)
    and atual.cobertura_os is not None and atual.cobertura_os >= 0.9
    and anterior.cobertura_os is not None and anterior.cobertura_os >= 0.9
    and atual.headcount_origem == anterior.headcount_origem == "lista_ativos"
)
variacao_disponibilidade = _variacao_pontos(disponibilidade, disponibilidade_anterior)
variacao_absenteismo = _variacao_pontos(atual.taxa_absenteismo, anterior.taxa_absenteismo)
variacao_os = _variacao_percentual(float(atual.os), float(anterior.os))
variacao_produtividade = _variacao_percentual(atual.os_por_tecnico_dia, anterior.os_por_tecnico_dia)
variacao_impacto = _variacao_percentual(atual.os_estimadas_perdidas, anterior.os_estimadas_perdidas)

if not comparacao_confiavel:
    variacao_disponibilidade = variacao_absenteismo = variacao_os = None
    variacao_produtividade = variacao_impacto = None

sparkline_produtividade: list[float] = []
if not atual.serie_semanal.empty:
    sparkline_produtividade = [
        float(valor)
        for valor in atual.serie_semanal["O.S./téc-dia"].dropna().tolist()
        if pd.notna(valor)
    ]


# ====================================================
# 🚩 BLOCO 5: CABEÇALHO E KPIs
# ====================================================
abrir_dashboard(
    PAGINA,
    subtitulo=(
        "Produção por técnico-dia e o peso das ausências, por supervisor e base — "
        "sem ranking individual de saúde."
    ),
    badge="PAINEL TOTALE",
    icone="⚖️",
    secoes=SECOES_PAGINA,
    resumo=resumir_carga(st.session_state.get("dados_prod")),
    origem=str(st.session_state.get("origem_dados") or ""),
    periodo=(
        f"{atual.inicio:%d/%m/%Y} a {atual.fim:%d/%m/%Y} · {atual.dias_uteis} dia(s) útil(eis)"
    ),
    chips={
        "Quadro": f"{formatar_inteiro(atual.headcount)} técnico(s)",
        "Técnico-dia": _texto_numero(atual.dias_disponiveis, 0),
    },
)

with st.container(border=True):
    st.markdown("**Qualidade dos dados**")
    cobertura = "—" if atual.cobertura_os is None else f"{atual.cobertura_os:.0%}"
    sem_data = int(producao["Data"].isna().sum())
    st.write(f"Cobertura de O.S. com quadro: {cobertura} · Linhas de produção sem data na carga: {sem_data}")
    if not presenca_verificavel:
        st.warning("Controle de absenteísmo vazio ou indisponível: não é possível distinguir falha de carga de ausência de registros. Disponibilidade, produtividade e impacto abaixo são estimativas com ausência zero, não presença confirmada.")
    else:
        st.info(f"Controle carregado com {len(registros)} registro(s); isso não comprova cobertura completa do período. Quadro: {ORIGEM_QUADRO.get(atual.headcount_origem, atual.headcount_origem)}.")
    if avisos:
        for aviso in avisos:
            st.warning(aviso)

with secao(
    "Indicadores",
    icone="🎯",
    subtitulo="O recorte atual e a comparação selecionada.",
):
    render_kpi_row(
        [
            {
                "label": "O.S. POR TÉCNICO-DIA",
                "valor": _texto_numero(atual.os_por_tecnico_dia, 2),
                "delta": _rotulo_variacao(variacao_produtividade),
                "delta_tipo": _direcao(variacao_produtividade, subir_e_bom=True),
                "sub": (
                    f"{formatar_inteiro(atual.os)} O.S. ÷ "
                    f"{_texto_numero(atual.dias_disponiveis, 0)} técnico-dia"
                ),
                "icone": "⚙️",
                "tema": "azul",
                "sparkline": sparkline_produtividade or None,
                "ajuda": (
                    "O.S. do recorte divididas pelo técnico-dia disponível "
                    "(quadro × dias úteis − dias de ausência)."
                ),
            },
            {
                "label": "DISPONIBILIDADE",
                "valor": _texto_percentual(disponibilidade),
                "delta": _rotulo_variacao(variacao_disponibilidade, sufixo=" p.p."),
                "delta_tipo": _direcao(variacao_disponibilidade, subir_e_bom=True),
                "sub": (
                    f"{_texto_numero(atual.dias_disponiveis, 0)} de "
                    f"{formatar_inteiro(atual.headcount * atual.dias_uteis)} técnico-dia"
                ),
                "icone": "✅",
                "tema": "verde",
                "progresso": (
                    atual.dias_disponiveis / (atual.headcount * atual.dias_uteis)
                    if atual.headcount and atual.dias_uteis
                    else None
                ),
                "meta_rotulo": "100%",
                "ajuda": (
                    "Técnico-dia disponível dividido pelo técnico-dia previsto do quadro. "
                    "A ausência é descontada uma única vez por login e dia."
                ),
            },
            {
                "label": "ABSENTEÍSMO",
                "valor": _texto_percentual(atual.taxa_absenteismo),
                "delta": _rotulo_variacao(variacao_absenteismo, sufixo=" p.p."),
                "delta_tipo": _direcao(variacao_absenteismo, subir_e_bom=False),
                "sub": (
                    f"{formatar_inteiro(atual.dias_ausencia)} dia(s) · "
                    f"{formatar_inteiro(atual.tecnicos_ausentes)} técnico(s)"
                ),
                "icone": "🕒",
                "tema": "laranja",
                "ajuda": (
                    "Dias de ausência ÷ técnico-dia previsto. Programadas (folga, férias, "
                    "treinamento) e não programadas aparecem separadas na quebra por tipo."
                ),
            },
            {
                "label": "O.S. NO RECORTE",
                "valor": formatar_inteiro(atual.os),
                "delta": _rotulo_variacao(variacao_os),
                "delta_tipo": _direcao(variacao_os, subir_e_bom=True),
                "sub": f"{_texto_numero(atual.pontos, 0)} ponto(s) somados",
                "icone": "📦",
                "tema": "roxo",
            },
            {
                "label": "IMPACTO ESTIMADO",
                "valor": _texto_numero(atual.os_estimadas_perdidas, 0),
                "delta": _rotulo_variacao(variacao_impacto),
                "delta_tipo": _direcao(variacao_impacto, subir_e_bom=False),
                "sub": "O.S. não realizadas (estimativa)",
                "icone": "📉",
                "tema": "vermelho",
                "ajuda": (
                    "Dias de ausência × produtividade média do recorte. É uma estimativa "
                    "de ordem de grandeza, não uma demanda perdida medida."
                ),
            },
        ],
        colunas=5,
    )
    st.caption(
        f"{comparacao}: {inicio_anterior:%d/%m/%Y} a {fim_anterior:%d/%m/%Y}. "
        "O quadro usado nos dois recortes é o retrato atual da lista de ativos."
    )
    if not comparacao_confiavel:
        st.warning("Variações indisponíveis: confira as datas da produção, registros de absenteísmo, quadro e cobertura de O.S. (mínimo 90% em ambos os períodos). Datas extremas não garantem cobertura completa.")
    with st.container(border=True):
        st.markdown("**💡 Leitura automática**")
        insights = gerar_insights(atual)
        if insights:
            for mensagem, tipo in insights:
                render_insight(mensagem, tipo=tipo)
        else:
            render_insight(
                "Sem leitura automática: o recorte não tem produção nem ausência suficiente.",
                tipo="info",
            )


# ====================================================
# 📈 BLOCO 6: PRODUTIVIDADE × DISPONIBILIDADE
# ====================================================
with secao(
    "Produtividade × Disponibilidade",
    icone="📈",
    subtitulo="Cada supervisor no cruzamento entre tempo disponível e entrega por técnico-dia.",
):
    tabela = atual.por_supervisor
    comparaveis = (
        tabela.loc[(tabela["Quadro"] > 0) & tabela["O.S./téc-dia"].notna()].copy()
        if not tabela.empty
        else tabela
    )
    coluna_grafico, coluna_ranking = st.columns([1.15, 1], gap="large")

    with coluna_grafico:
        if len(comparaveis) >= AMOSTRA_MINIMA_COMPARACAO:
            dispersao = comparaveis.copy()
            dispersao["Quadro"] = dispersao["Quadro"].clip(lower=1)
            figura_dispersao = criar_grafico(
                "dispersao",
                dispersao,
                "Absenteísmo (%)",
                "O.S./téc-dia",
                col_grupo="Base",
                tamanho="Quadro",
                titulo="Quanto mais à direita, mais tempo perdido",
                altura=390,
                rotulos={
                    "Absenteísmo (%)": "Absenteísmo (%)",
                    "O.S./téc-dia": "O.S. por técnico-dia",
                    "Base": "Base",
                },
            )
            render_grafico(figura_dispersao, chave="produtividade_dispersao", altura=390)
            st.caption(
                "Bolha = supervisor (tamanho pelo headcount). A reta é tendência do "
                "recorte, não meta. Ausência maior não implica causalidade."
            )
        else:
            render_insight(
                "Amostra insuficiente para o cruzamento: são necessários pelo menos "
                f"{AMOSTRA_MINIMA_COMPARACAO} supervisores com técnico-dia disponível no "
                "recorte. Aumente o período ou remova filtros de base/supervisor.",
                tipo="info",
            )

    with coluna_ranking:
        if not comparaveis.empty:
            ranking = comparaveis.sort_values("O.S./téc-dia", ascending=False).copy()
            figura_ranking = criar_grafico(
                "ranking",
                ranking,
                "Supervisor",
                "O.S./téc-dia",
                titulo="O.S. por técnico-dia",
                altura=390,
                top=LIMITE_RANKING,
                destacar_lider=True,
                mostrar_valores=True,
            )
            render_grafico(figura_ranking, chave="produtividade_ranking", altura=390)
            st.caption("Top por entrega relativa; supervisores sem denominador ficam fora.")
        else:
            render_insight(
                "Sem supervisores comparáveis: falta quadro de referência ou O.S. no recorte.",
                tipo="alerta",
            )


# ====================================================
# 🕒 BLOCO 7: AUSÊNCIAS
# ====================================================
with secao(
    "Ausências",
    icone="🕒",
    subtitulo="Onde o tempo previsto foi consumido — por supervisor e por tipo.",
):
    if atual.dias_ausencia == 0:
        render_insight(
            "Nenhuma ausência registrada no recorte. A disponibilidade estimada é integral — "
            "confira se o controle de absenteísmo está carregado antes de comemorar.",
            tipo="info",
        )
    else:
        coluna_supervisor, coluna_tipo = st.columns([1.35, 1], gap="large")
        with coluna_supervisor:
            detalhe_tipo = atual.ausencias_por_supervisor_tipo
            totais = detalhe_tipo.groupby("Supervisor")["Dias"].sum().sort_values(ascending=False)
            ordem = list(totais.index[:LIMITE_RANKING])
            dados_barras = detalhe_tipo.loc[detalhe_tipo["Supervisor"].isin(ordem)]
            figura_barras = criar_grafico(
                "barras",
                dados_barras,
                "Supervisor",
                "Dias",
                col_grupo="Tipo",
                titulo="Dias de ausência por supervisor e tipo",
                altura=400,
                orientacao="h",
                modo="empilhado",
                mostrar_valores=True,
                ordem=ordem,
            )
            dados_treemap = (
                tabela.loc[tabela["Dias Ausência"] > 0, ["Base", "Supervisor", "Dias Ausência"]]
                if not tabela.empty
                else tabela
            )
            figura_treemap = criar_grafico(
                "treemap",
                dados_treemap,
                ["Base", "Supervisor"],
                "Dias Ausência",
                titulo="Base → supervisor: onde os dias se concentram",
                altura=400,
            )
            abas = render_abas(
                ["Por supervisor", "Base → supervisor"],
                chave="produtividade_ausencia_detalhe",
                icones=["🧑‍🔧", "🗂️"],
            )
            with abas[0]:
                render_grafico(figura_barras, chave="produtividade_ausencia_supervisor", altura=400)
                if len(totais) > LIMITE_RANKING:
                    st.caption(
                        f"Exibindo os {LIMITE_RANKING} supervisores com mais dias; "
                        "os demais seguem na tabela e na exportação."
                    )
            with abas[1]:
                render_grafico(figura_treemap, chave="produtividade_ausencia_treemap", altura=400)
                st.caption(
                    "O tamanho do bloco é o total de dias de ausência; "
                    "a hierarquia não representa subordinação formal."
                )

        with coluna_tipo:
            figura_tipo = criar_grafico(
                "donut",
                atual.por_tipo,
                "Tipo",
                "Dias",
                titulo="Composição por tipo de ausência",
                altura=400,
            )
            render_grafico(figura_tipo, chave="produtividade_ausencia_tipo", altura=400)
            st.caption(
                f"{participacao_programada:.0f}% dos dias são programados "
                "(folga, férias, treinamento); o restante é imprevisto."
            )


# ====================================================
# 🗓️ BLOCO 8: EVOLUÇÃO
# ====================================================
with secao(
    "Evolução",
    icone="📅",
    subtitulo="Como produção e ausência se movem dentro do período.",
):
    figuras: dict[str, Any] = {}
    if not atual.serie_semanal.empty:
        figuras["Semana"] = criar_grafico(
            "combinado",
            atual.serie_semanal,
            "Rótulo",
            "O.S.",
            "O.S./téc-dia",
            titulo="O.S. por semana e produtividade relativa",
            altura=360,
            rotulo_barra="O.S.",
            rotulo_linha="O.S./téc-dia",
        )
    if not atual.serie_diaria.empty:
        figuras["Dia"] = criar_grafico(
            "calendario",
            atual.serie_diaria,
            col_data="Data",
            col_valor="Técnicos",
            titulo="Técnicos ausentes por dia",
            altura=320,
        )
    if figuras:
        render_graficos_em_abas(figuras, chave="produtividade_evolucao", altura=360)
        if len(atual.serie_semanal) <= 1:
            st.caption(
                "O recorte tem uma única semana: aumente o período para ler tendência "
                "em vez de um ponto isolado."
            )
        st.caption(
            "A semana começa na segunda-feira. A produtividade da semana usa o "
            "técnico-dia disponível daquela semana, não a média do período."
        )
    else:
        render_insight(
            "Sem série temporal: a produção não trouxe datas reconhecidas e não há "
            "ausências no recorte.",
            tipo="info",
        )


# ====================================================
# 🧾 BLOCO 9: DETALHE, PREMISSAS E EXPORTAÇÃO
# ====================================================
with secao(
    "Detalhe por Supervisor",
    icone="🧾",
    subtitulo="A conta aberta: quadro, ausência, técnico-dia, O.S. e leitura comparativa.",
):
    if atual.por_supervisor.empty:
        render_insight(
            "Nada para detalhar: não há quadro, produção ou ausência no recorte atual.",
            tipo="info",
        )
    else:
        render_table_html(
            atual.por_supervisor,
            titulo="Produtividade e disponibilidade por supervisor",
            max_rows=200,
            height=520,
            fmt=FMT_TABELA,
            colunas_num=list(COLUNAS_NUMERICAS),
            caption=(
                "Leitura compara a O.S./técnico-dia com a mediana dos supervisores "
                "comparáveis do recorte (faixa de ±5%)."
            ),
        )
        st.caption(
            f"Quadro: {ORIGEM_QUADRO.get(atual.headcount_origem, atual.headcount_origem)} · "
            f"{formatar_inteiro(atual.headcount)} técnico(s) · "
            f"{atual.dias_uteis} dia(s) útil(eis) no período. "
            "“Sem base” indica supervisor com O.S. mas sem headcount conhecido."
        )

    with st.expander("Como calculamos — premissas e limites", expanded=False):
        st.markdown(
            textwrap.dedent(
                """
**Técnico-dia disponível** = `quadro × dias úteis − dias de ausência`.

- **Calendário operacional**: dias da semana e datas excluídas informados nos filtros.
  É comum a todo o quadro; escalas e jornadas individuais não são consideradas.
  Feriados não são automáticos e devem incluir os períodos comparados.
- **Quadro**: retrato atual da `lista_ativos`, contando as situações que compõem
  o quadro (ativo, férias, inoperante, ETN e afastado), deduplicadas por login.
  O portal não guarda a vigência histórica de base/monitor: recortes antigos
  usam o quadro de hoje. Por isso o painel é mais confiável para períodos
  recentes e para leitura de tendência, não para auditoria retroativa.
- **Ausência**: cada registro ativo é expandido em pares `login × dia` dentro do
  recorte. O mesmo login no mesmo dia conta **uma** vez, com o tipo de maior
  prioridade (falta > atestado > afastamento > licença > suspensão > férias >
  folga > treinamento > outros). Registros cancelados e de presença não entram.
- **Produtividade** = `O.S. ÷ técnico-dia disponível`. É relativa de propósito:
  comparar volume absoluto premiaria a equipe com mais gente.
- **Impacto estimado** = `dias de ausência × produtividade média do recorte`.
  Serve para dimensionar o tema, **não** para afirmar quantas O.S. o cliente
  deixou de pedir.
- **Cobertura**: O.S. de supervisor sem headcount entram no total, mas não têm
  denominador. A página avisa quando isso passa de 10%.
- **Privacidade**: nenhum bloco mostra login, motivo, atestado ou diagnóstico.
  O detalhe é sempre agregado por supervisor/base, como definido na proposta D3.

**Limitações conhecidas**: o controle de absenteísmo pode não cobrir todos os
tipos de afastamento; a lista de ativos é um retrato, não uma linha do tempo; e
a produção pode não ter data em todas as linhas (a página avisa quando o
período deixa de filtrar as O.S.).
                """
            )
        )

exportacao = atual.por_supervisor.copy()
if not exportacao.empty:
    exportacao.insert(0, "Período", f"{atual.inicio:%d/%m/%Y} a {atual.fim:%d/%m/%Y}")
    exportacao.insert(1, "Dias Úteis", atual.dias_uteis)
    exportacao.insert(2, "Headcount do Recorte", atual.headcount)
    exportacao.insert(3, "Cobertura de O.S. (%)", (
        round(atual.cobertura_os * 100.0, 1) if atual.cobertura_os is not None else None
    ))
    exportacao.insert(4, "Dias de operação", ", ".join(dias_selecionados))
    exportacao.insert(5, "Datas não operacionais", ", ".join(d.strftime("%d/%m/%Y") for d in feriados))
    exportacao.insert(6, "Estado do controle", "Carregado" if presenca_verificavel else "Vazio ou indisponível")

secao_exportacao(
    exportacao,
    nome_arquivo="produtividade_disponibilidade",
    chave="produtividade_disponibilidade",
    titulo="Exportação",
    subtitulo="Uma linha por supervisor, com o recorte e as premissas aplicadas.",
)

fechar_dashboard()
