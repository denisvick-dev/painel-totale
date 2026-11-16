"""
absenteismo.py
==============
Controle de Absenteísmo — Portal TOTALE.

É o **controle de ausências** do quadro: faltas, folgas, férias, atestados,
afastamentos, licenças, suspensões e treinamentos, com data de início/fim e
contagem em **dias corridos** e **dias úteis** (seg–sex).

Fontes (camada compartilhada, nenhuma leitura própria nesta página):

* **quem é o quadro** — aba ``lista_ativos`` via
  :func:`services.hierarquia.lista_ativos_da_sessao` (técnico, monitor e base
  do formulário e dos recortes);
* **os registros de ausência** — aba ``controle_absenteismo`` da mesma
  planilha, via :mod:`services.absenteismo` (leitura compartilhada; gravação
  com ``gspread``/conta de serviço, o mesmo padrão da Gestão de Ativos; a aba
  é criada com o cabeçalho oficial no primeiro lançamento).

Regras do controle (detalhes em :mod:`services.absenteismo`):

* dias no período são contados só na interseção com o período filtrado;
* cancelar não apaga — o registro fica ``Cancelado`` e auditável;
* sem credencial de escrita (``[gcp_service_account]`` nos secrets), o
  lançamento fica **somente na sessão** e a página avisa: nada é fingido
  como salvo na planilha.

A página segue o padrão do portal (``components.dashboards`` +
``components.layout_pagina``): hero → chips → sumário → indicadores →
lançamento → análises → registros → exportação → rodapé.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from components.componentes import aplicar_estilo, render_empty_state, render_insight
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.graficos import (
    grafico_barras,
    grafico_calendario,
    grafico_donut,
    grafico_ranking,
    render_grafico,
)
from components.kpi_cards import SpecKPIAvancado, render_kpi_row
from components.layout_pagina import secao
from components.sidebar import render_page_sidebar_theme_selector
from config.settings import SHEET_ABA_ABSENTEISMO, SHEET_ABA_ATIVOS
from services.absenteismo import (
    JUSTIFICATIVAS,
    STATUS_ATIVO,
    STATUS_CANCELADO,
    TIPOS_AUSENCIA,
    agrupar_registros,
    calcular_dias,
    fase_do_registro,
    filtrar_registros_periodo,
    gravar_registros,
    normalizar_registros,
    registrar_ausencia,
    registros_da_sessao,
    resumir_controle,
    serie_diaria_ausencias,
)
from services.dados_sessao import resumir_carga, ultima_atualizacao
from services.hierarquia import SITUACOES_QUADRO, lista_ativos_da_sessao
from services.texto import formatar_inteiro, formatar_percentual

logger = logging.getLogger(__name__)

#: Seções ancoradas do sumário (mesmos títulos usados em ``secao()``).
SECOES_PAGINA: tuple[str, ...] = (
    "Indicadores do Período",
    "Registrar Ausência",
    "Ausências por Tipo",
    "Calendário de Ausências",
    "Ranking por Base e Monitor",
    "Ausentes Hoje e Próximas Ausências",
    "Registros do Controle",
    "Exportação",
)

CHAVES_FILTRO: tuple[str, ...] = (
    "absenteismo_periodo_inicio",
    "absenteismo_periodo_fim",
    "absenteismo_filtro_base",
    "absenteismo_filtro_monitor",
    "absenteismo_filtro_tipo",
    "absenteismo_busca",
    "absenteismo_incluir_cancelados",
)

#: Registros lançados sem persistência (sem credencial de escrita) nesta sessão.
CHAVE_PENDENTES = "absenteismo_registros_pendentes"
#: IDs cancelados sem persistência nesta sessão (override sobre a leitura).
CHAVE_CANCELADOS_PENDENTES = "absenteismo_cancelados_pendentes"

st.set_page_config(page_title="Absenteísmo | TOTALE", page_icon="🗓️", layout="wide")

aplicar_estilo()
render_page_sidebar_theme_selector()


# ============================================================
# CARGA: QUADRO (lista_ativos) + REGISTROS (controle_absenteismo)
# ============================================================
def _carregar_registros() -> tuple[pd.DataFrame, int]:
    """Registros da planilha + pendentes da sessão, com cancelamentos aplicados."""
    base = registros_da_sessao(aba=SHEET_ABA_ABSENTEISMO, ttl=300)
    pendentes: list[dict] = st.session_state.get(CHAVE_PENDENTES, [])
    cancelados: set[str] = st.session_state.get(CHAVE_CANCELADOS_PENDENTES, set())

    registros = base
    if pendentes:
        brutos = pd.concat(
            [base.drop(columns=["_inicio", "_fim"], errors="ignore"), pd.DataFrame(pendentes)],
            ignore_index=True,
        )
        registros = normalizar_registros(brutos)
    if cancelados and not registros.empty:
        registros = registros.copy()
        registros.loc[registros["ID"].isin(cancelados), "Status"] = STATUS_CANCELADO
    return registros, len(pendentes)


def _persistir(registros: pd.DataFrame) -> bool:
    """Grava a aba inteira; em sucesso, limpa pendências e relê da planilha."""
    ok, motivo = gravar_registros(registros)
    if ok:
        st.session_state.pop(CHAVE_PENDENTES, None)
        st.session_state.pop(CHAVE_CANCELADOS_PENDENTES, None)
        registros_da_sessao(aba=SHEET_ABA_ABSENTEISMO, ttl=300, forcar=True)
    else:
        logger.warning("Controle de absenteísmo sem persistência: %s", motivo)
    return ok


def _primeiro_e_ultimo_dia_mes(hoje: date) -> tuple[date, date]:
    inicio = hoje.replace(day=1)
    fim = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return inicio, fim


lista_ativos = lista_ativos_da_sessao(aba=SHEET_ABA_ATIVOS, ttl=600)
registros, qtd_pendentes = _carregar_registros()
hoje = date.today()
mes_inicio, mes_fim = _primeiro_e_ultimo_dia_mes(hoje)

# Técnicos do quadro (sem desligados/inativos) para o formulário e recortes.
quadro_df = (
    lista_ativos[lista_ativos["SITUAÇÃO"].isin(SITUACOES_QUADRO)].copy()
    if not lista_ativos.empty
    else lista_ativos
)

abrir_dashboard(
    "Absenteísmo",
    subtitulo=(
        "Controle de faltas, folgas, férias, atestados e afastamentos do quadro "
        "— registros na aba controle_absenteismo, técnicos da lista_ativos."
    ),
    icone="🗓️",
    secoes=SECOES_PAGINA,
    resumo=resumir_carga(registros, atualizado_em=ultima_atualizacao()),
    origem=f"controle_absenteismo + lista_ativos ({SHEET_ABA_ATIVOS})",
)

for tipo_flash, texto_flash in st.session_state.pop("absenteismo_flash", []):
    if tipo_flash == "sucesso":
        st.success(texto_flash)
    elif tipo_flash == "alerta":
        st.warning(texto_flash)
    else:
        st.error(texto_flash)

if qtd_pendentes:
    render_insight(
        f"**{formatar_inteiro(qtd_pendentes)} registro(s)** estão salvos **somente "
        "nesta sessão**: a gravação na planilha falhou (credencial de escrita "
        "`[gcp_service_account]` ausente ou sem permissão na planilha). Eles "
        "aparecem nas análises, mas se perdem ao fechar a sessão — exporte a "
        "aba Registros do Controle se precisar guardar.",
        tipo="alerta",
        titulo="Lançamentos não sincronizados",
    )

# ============================================================
# FILTROS (SIDEBAR)
# ============================================================
with st.sidebar:
    st.markdown("### 🗓️ Filtros — Absenteísmo")
    periodo_inicio = st.date_input(
        "Início do período", value=mes_inicio, key="absenteismo_periodo_inicio"
    )
    periodo_fim = st.date_input("Fim do período", value=mes_fim, key="absenteismo_periodo_fim")
    if periodo_fim < periodo_inicio:
        periodo_inicio, periodo_fim = periodo_fim, periodo_inicio
    bases_sel = st.multiselect(
        "Base",
        sorted(registros["Base"].replace("", "Não informado").unique())
        if not registros.empty
        else [],
        key="absenteismo_filtro_base",
    )
    monitores_sel = st.multiselect(
        "Monitor",
        sorted(registros["Monitor"].replace("", "Não informado").unique())
        if not registros.empty
        else [],
        key="absenteismo_filtro_monitor",
    )
    tipos_sel = st.multiselect("Tipo de ausência", list(TIPOS_AUSENCIA), key="absenteismo_filtro_tipo")
    busca = st.text_input(
        "Buscar técnico ou login", key="absenteismo_busca", placeholder="Nome ou login…"
    )
    incluir_cancelados = st.checkbox(
        "Incluir registros cancelados na lista", key="absenteismo_incluir_cancelados"
    )
    if st.button("Limpar filtros", key="absenteismo_limpar_filtros"):
        for chave in CHAVES_FILTRO:
            st.session_state.pop(chave, None)
        st.rerun()
    if st.button("🔄 Atualizar registros e quadro", key="absenteismo_atualizar"):
        registros_da_sessao(aba=SHEET_ABA_ABSENTEISMO, ttl=300, forcar=True)
        lista_ativos_da_sessao(aba=SHEET_ABA_ATIVOS, ttl=600, forcar=True)
        st.rerun()


def _aplicar_recorte(df: pd.DataFrame) -> pd.DataFrame:
    """Recorte da sidebar (base/monitor/tipo/busca) sobre os registros."""
    recorte = df.copy()
    if bases_sel:
        recorte = recorte[recorte["Base"].replace("", "Não informado").isin(bases_sel)]
    if monitores_sel:
        recorte = recorte[recorte["Monitor"].replace("", "Não informado").isin(monitores_sel)]
    if tipos_sel:
        recorte = recorte[recorte["Tipo"].isin(tipos_sel)]
    if busca.strip():
        termo = busca.strip().casefold()
        alvo = recorte["Técnico"].str.casefold() + " " + recorte["Login"].str.casefold()
        recorte = recorte[alvo.str.contains(termo, regex=False)]
    return recorte


registros_recorte = _aplicar_recorte(registros)
resumo = resumir_controle(
    registros_recorte, periodo_inicio=periodo_inicio, periodo_fim=periodo_fim, hoje=hoje
)

# Quadro no mesmo recorte de base/monitor (denominador da taxa do período).
quadro_recorte = quadro_df
if bases_sel:
    quadro_recorte = quadro_recorte[
        quadro_recorte["BASE"].replace("", "Não informado").isin(bases_sel)
    ]
if monitores_sel:
    quadro_recorte = quadro_recorte[
        quadro_recorte["MONITOR"].replace("", "Não informado").isin(monitores_sel)
    ]
qtd_quadro = len(quadro_recorte)
_, dias_uteis_no_periodo = calcular_dias(periodo_inicio, periodo_fim)
taxa_periodo = (
    resumo["dias_uteis_periodo"] / (qtd_quadro * dias_uteis_no_periodo)
    if qtd_quadro and dias_uteis_no_periodo
    else 0.0
)


def _tabela_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    """Registros para leitura/exportação (datas BR, fase calculada, sem auxiliares)."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Login", "Técnico", "Monitor", "Base", "Tipo", "Início", "Fim",
                "Dias Corridos", "Dias Úteis", "Justificativa", "Motivo", "Fase",
                "Status", "Registrado em",
            ]
        )
    tabela = df.copy()
    tabela["Início"] = tabela["_inicio"].dt.strftime("%d/%m/%Y")
    tabela["Fim"] = tabela["_fim"].dt.strftime("%d/%m/%Y")
    tabela["Fase"] = [fase_do_registro(linha, hoje) for linha in tabela.to_dict("records")]
    colunas = [
        "Login", "Técnico", "Monitor", "Base", "Tipo", "Início", "Fim",
        "Dias Corridos", "Dias Úteis", "Justificativa", "Motivo", "Fase",
        "Status", "Registrado em",
    ]
    return tabela[colunas].sort_values(["Início", "Técnico"]).reset_index(drop=True)


# ============================================================
# INDICADORES DO PERÍODO
# ============================================================
with secao(
    "Indicadores do Período",
    icone="monitoring",
    subtitulo=f"{periodo_inicio:%d/%m/%Y} a {periodo_fim:%d/%m/%Y} · dias úteis contam seg–sex (sem feriados).",
    badge=f"{formatar_inteiro(qtd_quadro)} técnicos no quadro",
):
    specs: list[SpecKPIAvancado] = [
        {
            "label": "Ausentes hoje",
            "valor": formatar_inteiro(resumo["ausentes_hoje"]),
            "sub": f"{formatar_inteiro(resumo['registros_hoje'])} registro(s) cobrindo hoje",
            "icone": "🗓️",
            "tema": "vermelho",
        },
        {
            "label": "Técnicos ausentes no período",
            "valor": formatar_inteiro(resumo["tecnicos_periodo"]),
            "sub": f"{formatar_inteiro(resumo['registros_periodo'])} registro(s) no período",
            "icone": "👷",
            "tema": "azul",
        },
        {
            "label": "Dias úteis de ausência",
            "valor": formatar_inteiro(resumo["dias_uteis_periodo"]),
            "sub": f"{formatar_inteiro(resumo['dias_corridos_periodo'])} dias corridos",
            "icone": "📆",
            "tema": "laranja",
            "ajuda": "Soma dos dias úteis de cada registro, só na interseção com o período.",
        },
        {
            "label": "Taxa de absenteísmo",
            "valor": formatar_percentual(taxa_periodo * 100),
            "sub": "Dias úteis ausentes ÷ (quadro × dias úteis do período)",
            "icone": "📉",
            "tema": "roxo",
            "progresso": min(taxa_periodo * 100, 100.0),
            "ajuda": f"Quadro do recorte: {formatar_inteiro(qtd_quadro)} técnicos · {dias_uteis_no_periodo} dias úteis no período.",
        },
    ]
    render_kpi_row(specs, colunas=4)
    render_insight(
        f"No período: **{formatar_inteiro(resumo['faltas_periodo'])}** falta(s), "
        f"**{formatar_inteiro(resumo['ferias_periodo'])}** férias e "
        f"**{formatar_inteiro(resumo['programadas'])}** ausência(s) programadas "
        f"(férias/folgas/treinamentos futuros). Total histórico do controle: "
        f"**{formatar_inteiro(resumo['registros_total'])}** registro(s) ativos"
        f" e **{formatar_inteiro(resumo['cancelados'])}** cancelado(s).",
        tipo="info",
    )

# ============================================================
# REGISTRAR AUSÊNCIA
# ============================================================
with secao(
    "Registrar Ausência",
    icone="edit_calendar",
    subtitulo="O lançamento grava na aba controle_absenteismo da planilha da lista_ativos.",
):
    opcoes_tecnicos: dict[str, pd.Series] = {}
    if not quadro_df.empty:
        ordenado = quadro_df.sort_values(["BASE", "MONITOR", "TÉCNICO"])
        for _, linha in ordenado.iterrows():
            rotulo = (
                f"{linha['TÉCNICO']} — Login {linha['LOGIN']} · "
                f"{linha['BASE'] or 'Sem base'} / {linha['MONITOR'] or 'Sem monitor'}"
            )
            opcoes_tecnicos[rotulo] = linha

    with st.form("form_registro_ausencia", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            if opcoes_tecnicos:
                tecnico_sel = st.selectbox("Técnico (lista_ativos)", list(opcoes_tecnicos))
                login_manual = nome_manual = ""
            else:
                tecnico_sel = ""
                nome_manual = st.text_input("Técnico (lista_ativos indisponível)")
                login_manual = st.text_input("Login")
            tipo_sel = st.selectbox("Tipo de ausência", list(TIPOS_AUSENCIA))
            justificativa_sel = st.selectbox("Justificativa", list(JUSTIFICATIVAS), index=2)
        with col_b:
            data_inicio = st.date_input("Data de início", value=hoje)
            data_fim = st.date_input("Data de fim", value=hoje)
            motivo_txt = st.text_area("Motivo / observação", height=68)
        enviado = st.form_submit_button("💾 Registrar ausência", width="stretch")

    if enviado:
        if opcoes_tecnicos and tecnico_sel:
            linha_tec = opcoes_tecnicos[tecnico_sel]
            login_novo, nome_novo = str(linha_tec["LOGIN"]), str(linha_tec["TÉCNICO"])
            monitor_novo, base_novo = str(linha_tec["MONITOR"]), str(linha_tec["BASE"])
        else:
            login_novo, nome_novo = login_manual.strip(), nome_manual.strip()
            monitor_novo = base_novo = ""
        if not login_novo or not nome_novo:
            st.error("Selecione um técnico da lista_ativos (ou informe nome e login).")
        elif data_fim < data_inicio:
            st.error("A data de fim não pode ser anterior à data de início.")
        else:
            registro = {
                "ID": uuid.uuid4().hex[:12],
                "Login": login_novo,
                "Técnico": nome_novo,
                "Monitor": monitor_novo,
                "Base": base_novo,
                "Tipo": tipo_sel,
                "Data Início": data_inicio.isoformat(),
                "Data Fim": data_fim.isoformat(),
                "Justificativa": justificativa_sel,
                "Motivo": motivo_txt.strip(),
                "Status": STATUS_ATIVO,
                "Registrado em": datetime.now().strftime("%d/%m/%Y %H:%M"),
            }
            sobrepostos = filtrar_registros_periodo(registros, data_inicio, data_fim)
            sobrepostos = sobrepostos[sobrepostos["Login"] == login_novo]
            _novo_df, persistiu, motivo_falha = registrar_ausencia(registros, registro)
            mensagens: list[tuple[str, str]] = []
            if persistiu:
                mensagens.append(
                    (
                        "sucesso",
                        f"Ausência registrada na planilha: {nome_novo} · {tipo_sel} · "
                        f"{data_inicio:%d/%m/%Y} a {data_fim:%d/%m/%Y}.",
                    )
                )
            else:
                pendentes = st.session_state.get(CHAVE_PENDENTES, [])
                pendentes.append(registro)
                st.session_state[CHAVE_PENDENTES] = pendentes
                mensagens.append(
                    (
                        "alerta",
                        "Não foi possível gravar na planilha "
                        f"({motivo_falha}). O registro ficou **somente nesta sessão**.",
                    )
                )
            if not sobrepostos.empty:
                mensagens.append(
                    (
                        "alerta",
                        f"⚠️ {nome_novo} já tinha {len(sobrepostos)} registro(s) ativo(s) "
                        "nesse período — confira se não é duplicidade (Registros do Controle).",
                    )
                )
            st.session_state["absenteismo_flash"] = mensagens
            st.rerun()

# ============================================================
# AUSÊNCIAS POR TIPO / CALENDÁRIO / RANKINGS
# ============================================================
with secao(
    "Ausências por Tipo",
    icone="pie_chart",
    subtitulo="Dias úteis e registros de cada tipo dentro do período filtrado.",
):
    por_tipo = agrupar_registros(
        registros_recorte, "Tipo", periodo_inicio=periodo_inicio, periodo_fim=periodo_fim
    )
    if por_tipo.empty:
        render_empty_state(
            tipo="dados",
            titulo="Nenhuma ausência no período",
            descricao="Lance a primeira ausência em Registrar Ausência ou amplie o período.",
        )
    else:
        colunas_graficos = st.columns(2)
        with colunas_graficos[0]:
            render_grafico(
                grafico_donut(por_tipo, "Tipo", "Dias Úteis", titulo="Dias úteis por tipo", altura=340),
                chave="absenteismo_donut_tipo",
            )
        with colunas_graficos[1]:
            render_grafico(
                grafico_barras(
                    por_tipo, "Tipo", "Registros", titulo="Registros por tipo",
                    altura=340, mostrar_valores=True,
                ),
                chave="absenteismo_barras_tipo",
            )
        st.dataframe(por_tipo, width="stretch", hide_index=True)

with secao(
    "Calendário de Ausências",
    icone="calendar_month",
    subtitulo="Técnicos ausentes por dia no período (seg–sex úteis e fins de semana).",
):
    serie = serie_diaria_ausencias(
        registros_recorte, periodo_inicio=periodo_inicio, periodo_fim=periodo_fim
    )
    if serie.empty:
        render_empty_state(tipo="dados", titulo="Sem dias com ausência no período.")
    else:
        render_grafico(
            grafico_calendario(
                serie, col_data="Data", col_valor="Técnicos",
                titulo="Técnicos ausentes por dia", altura=300, mostrar_valores=True,
            ),
            chave="absenteismo_calendario",
        )

with secao(
    "Ranking por Base e Monitor",
    icone="leaderboard",
    subtitulo="Onde estão concentrados os dias úteis de ausência do período.",
):
    colunas_ranking = st.columns(2)
    for coluna, dimensao, chave_grafico in (
        (colunas_ranking[0], "Base", "absenteismo_ranking_base"),
        (colunas_ranking[1], "Monitor", "absenteismo_ranking_monitor"),
    ):
        agrupado = agrupar_registros(
            registros_recorte, dimensao, periodo_inicio=periodo_inicio, periodo_fim=periodo_fim
        )
        with coluna:
            if agrupado.empty:
                render_empty_state(tipo="dados", titulo=f"Sem dados por {dimensao.lower()}.")
            else:
                render_grafico(
                    grafico_ranking(
                        agrupado, dimensao, "Dias Úteis",
                        titulo=f"Dias úteis de ausência por {dimensao.lower()}", top=10,
                    ),
                    chave=chave_grafico,
                )
                st.dataframe(agrupado, width="stretch", hide_index=True)

# ============================================================
# AUSENTES HOJE E PRÓXIMAS AUSÊNCIAS
# ============================================================
with secao(
    "Ausentes Hoje e Próximas Ausências",
    icone="upcoming",
    subtitulo="Quem está fora hoje e o que vem nos próximos 30 dias.",
):
    ativos = registros_recorte[registros_recorte["Status"] == STATUS_ATIVO]
    if ativos.empty:
        render_empty_state(tipo="dados", titulo="Nenhum registro ativo no recorte.")
    else:
        de_hoje = ativos[
            (ativos["_inicio"].dt.date <= hoje) & (ativos["_fim"].dt.date >= hoje)
        ]
        proximas = ativos[
            (ativos["_inicio"].dt.date > hoje)
            & (ativos["_inicio"].dt.date <= hoje + timedelta(days=30))
        ]
        colunas_listas = st.columns(2)
        with colunas_listas[0]:
            st.markdown(f"**Ausentes hoje ({hoje:%d/%m/%Y})** — {len(de_hoje)} registro(s)")
            if de_hoje.empty:
                st.caption("Ninguém ausente hoje neste recorte.")
            else:
                st.dataframe(_tabela_exibicao(de_hoje), width="stretch", hide_index=True)
        with colunas_listas[1]:
            st.markdown(f"**Próximas ausências (30 dias)** — {len(proximas)} registro(s)")
            if proximas.empty:
                st.caption("Nada programado para os próximos 30 dias neste recorte.")
            else:
                st.dataframe(_tabela_exibicao(proximas), width="stretch", hide_index=True)

# ============================================================
# REGISTROS DO CONTROLE (DETALHAMENTO + CANCELAMENTO)
# ============================================================
with secao(
    "Registros do Controle",
    icone="list_alt",
    subtitulo="Todos os lançamentos do período. Cancelar mantém o registro auditável.",
    badge=f"{formatar_inteiro(len(registros_recorte))} no recorte",
):
    if incluir_cancelados:
        exibidos = registros_recorte[
            (registros_recorte["_inicio"] <= pd.Timestamp(periodo_fim))
            & (registros_recorte["_fim"] >= pd.Timestamp(periodo_inicio))
        ]
    else:
        # Só ativos cobrindo o período (cancelados ficam fora da lista).
        exibidos = filtrar_registros_periodo(registros_recorte, periodo_inicio, periodo_fim)
    if exibidos.empty:
        render_empty_state(
            tipo="filtro",
            titulo="Nenhum registro no recorte atual",
            descricao="Ajuste o período/filtros ou lance uma nova ausência.",
        )
    else:
        st.dataframe(_tabela_exibicao(exibidos), width="stretch", hide_index=True)

        ativos_exibidos = exibidos[exibidos["Status"] == STATUS_ATIVO]
        if not ativos_exibidos.empty:
            rotulos_cancelar = {
                f"{linha['Técnico']} · {linha['Tipo']} · {linha['_inicio']:%d/%m/%Y} a "
                f"{linha['_fim']:%d/%m/%Y} (Login {linha['Login']})": str(linha["ID"])
                for _, linha in ativos_exibidos.iterrows()
            }
            col_cancelar_a, col_cancelar_b = st.columns([3, 1])
            with col_cancelar_a:
                escolha = st.selectbox(
                    "Registro para cancelar", list(rotulos_cancelar), key="absenteismo_cancelar_sel"
                )
            with col_cancelar_b:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🚫 Cancelar registro", key="absenteismo_cancelar_btn"):
                    id_escolhido = rotulos_cancelar[escolha]
                    atualizados = registros.copy()
                    atualizados.loc[atualizados["ID"] == id_escolhido, "Status"] = STATUS_CANCELADO
                    if _persistir(atualizados):
                        st.session_state["absenteismo_flash"] = [
                            ("sucesso", "Registro cancelado e gravado na planilha.")
                        ]
                    else:
                        pendentes = [
                            r for r in st.session_state.get(CHAVE_PENDENTES, [])
                            if str(r.get("ID")) != id_escolhido
                        ]
                        st.session_state[CHAVE_PENDENTES] = pendentes
                        cancelados = st.session_state.get(CHAVE_CANCELADOS_PENDENTES, set())
                        cancelados.add(id_escolhido)
                        st.session_state[CHAVE_CANCELADOS_PENDENTES] = cancelados
                        st.session_state["absenteismo_flash"] = [
                            (
                                "alerta",
                                "Cancelamento aplicado **somente nesta sessão** "
                                "(gravação na planilha indisponível).",
                            )
                        ]
                    st.rerun()

# ============================================================
# EXPORTAÇÃO
# ============================================================
secao_exportacao(
    _tabela_exibicao(exibidos if not exibidos.empty else registros_recorte),
    nome_arquivo="controle_absenteismo",
    chave="absenteismo",
)

fechar_dashboard()
