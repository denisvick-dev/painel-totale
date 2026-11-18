"""Produtividade & Contratos — produção e contratos de clientes atendidos."""
from __future__ import annotations

from datetime import timedelta

import plotly.express as px
import streamlit as st

from components.componentes import aplicar_estilo
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.kpi_cards import render_kpi_row
from components.layout_pagina import secao
from components.sidebar import render_page_sidebar_theme_selector
from services.dados_sessao import exigir_base, resumir_carga
from services.produtividade_contratos import agrupar, preparar_producao, resumir
from services.texto import formatar_inteiro, formatar_numero

PAGINA = "Produtividade & Contratos"
st.set_page_config(page_title=PAGINA, page_icon="📊", layout="wide")
aplicar_estilo()
render_page_sidebar_theme_selector()

origem = exigir_base(pagina=PAGINA)
dados, coluna_contrato = preparar_producao(origem)
datas = dados["Data"].dropna()

with st.sidebar:
    st.markdown("### Filtros do painel")
    if not datas.empty:
        maximo = datas.max().date()
        minimo = datas.min().date()
        inicio = st.date_input("Início do período", value=max(minimo, maximo - timedelta(days=29)), key="contratos_inicio")
        fim = st.date_input("Fim do período", value=maximo, key="contratos_fim")
        if inicio > fim:
            inicio, fim = fim, inicio
    else:
        inicio = fim = None
        st.warning("Sem data reconhecida: exibindo toda a carga, sem filtro por período.")
    bases = st.multiselect("Base", sorted(dados["Base"].unique()), key="contratos_bases")
    supervisores = st.multiselect("Supervisor", sorted(dados["Supervisor"].unique()), key="contratos_supervisores")
    equipes = st.multiselect("Equipe", sorted(dados["Equipe"].unique()), key="contratos_equipes")
    if st.button("Limpar filtros", key="contratos_limpar"):
        for chave in ("contratos_inicio", "contratos_fim", "contratos_bases", "contratos_supervisores", "contratos_equipes"):
            st.session_state.pop(chave, None)
        st.rerun()

recorte = dados.copy()
for coluna, selecionados in (("Base", bases), ("Supervisor", supervisores), ("Equipe", equipes)):
    if selecionados:
        recorte = recorte.loc[recorte[coluna].isin(selecionados)]
sem_data = int(recorte["Data"].isna().sum())
if inicio is not None:
    recorte = recorte.loc[recorte["Data"].dt.date.between(inicio, fim)].copy()
resumo = resumir(recorte)
por_supervisor = agrupar(recorte, ["Base", "Supervisor"])
periodo = f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}" if inicio is not None else "Toda a carga (sem data)"

abrir_dashboard(
    PAGINA, subtitulo="Produção e contratos de clientes atendidos, por base, supervisor e equipe.",
    icone="📊", secoes=("Indicadores", "Evolução", "Detalhe", "Exportação"),
    resumo=resumir_carga(st.session_state.get("dados_prod")), periodo=periodo,
)

with secao("Indicadores", icone="🎯", subtitulo="Contratos identificados e produção no recorte selecionado."):
    cobertura = resumo["os_com_contrato"] / resumo["os"] * 100 if resumo["os"] else None
    if coluna_contrato is None:
        st.warning("Nenhuma coluna de identificador de contrato reconhecida na produção. Os indicadores de contratos estão indisponíveis; O.S. não são usadas como substituto.")
    elif cobertura is not None and cobertura < 100:
        st.warning(f"Identificador de contrato presente em {cobertura:.1f}% das O.S. do recorte. Contratos distintos são uma contagem parcial.")
    if recorte["Pontos"].isna().all() and not recorte.empty:
        st.info("Coluna de pontos indisponível na carga; a soma de pontos não será exibida.")
    if sem_data:
        st.warning(f"{sem_data} linha(s) sem data nos filtros de equipe/base/supervisor " + ("foram excluídas do período." if inicio is not None else "não podem ser filtradas por período."))
    if resumo["os"] and resumo["os_com_equipe_data"] < resumo["os"]:
        st.info("O.S./equipe-dia considera apenas linhas com equipe e data identificadas; não mede disponibilidade ou escala.")
    ncontratos = resumo["contratos"]
    render_kpi_row([
        {"label": "O.S. NO RECORTE", "valor": formatar_inteiro(resumo["os"]), "sub": "Uma linha da carga = uma O.S.", "icone": "📦", "tema": "azul"},
        {"label": "CONTRATOS ATENDIDOS", "valor": formatar_inteiro(ncontratos) if ncontratos is not None else "—", "sub": "Identificadores distintos", "icone": "📋", "tema": "verde"},
        {"label": "COBERTURA DE CONTRATO", "valor": f"{formatar_numero(cobertura, 1)}%" if cobertura is not None else "—", "sub": "O.S. com contrato identificado", "icone": "🔎", "tema": "laranja"},
        {"label": "O.S. / EQUIPE-DIA", "valor": formatar_numero(resumo["os_equipe_dia"], 2) if resumo["os_equipe_dia"] is not None else "—", "sub": "Somente equipes e dias com produção", "icone": "⚙️", "tema": "roxo"},
    ], colunas=4)
    st.caption(f"O.S. com equipe e data: {resumo['os_com_equipe_data']} de {resumo['os']} · Equipe-dias observados: {resumo['equipes_dia']} · Coluna de contrato: {coluna_contrato or 'não encontrada'}.")

with secao("Evolução", icone="📈", subtitulo="Produção diária no período selecionado."):
    diarios = recorte.dropna(subset=["Data"])
    if diarios.empty:
        st.info("Não há produção com data reconhecida neste recorte.")
    else:
        serie = agrupar(diarios, ["Data"]).sort_values("Data")
        fig = px.line(serie, x="Data", y="O.S.", markers=True, labels={"O.S.": "O.S."})
        st.plotly_chart(fig, width="stretch")
        st.caption("Contratos por dia não são somáveis: o mesmo contrato pode ser atendido em dias diferentes.")

with secao("Detalhe", icone="🧾", subtitulo="O.S., contratos identificados e pontos por base e supervisor."):
    if por_supervisor.empty:
        st.info("Nenhuma produção encontrada para os filtros selecionados.")
    else:
        st.dataframe(por_supervisor, hide_index=True, width="stretch")
        st.caption("Contratos distintos por grupo não são somáveis: um mesmo contrato pode aparecer em mais de uma equipe, base ou supervisor.")
    with st.expander("Como calculamos"):
        st.markdown("""- **O.S.**: cada linha da carga de produção é considerada uma O.S.; duplicações na origem não são removidas.
- **Contratos atendidos**: identificadores de contratos de clientes distintos no recorte; valores vazios ou inválidos são excluídos. Sem identificador, não há estimativa.
- **O.S./equipe-dia observado**: linhas com equipe e data ÷ combinações distintas de base, supervisor, equipe e dia com produção. Não mede quadro, presença, disponibilidade nem produtividade de equipes sem produção.
- **Pontos**: soma dos pontos informados na produção; confira a cobertura da origem.
- Períodos filtram pela data da produção; linhas sem data são excluídas quando há datas reconhecidas.
""")

exportacao = por_supervisor.copy()
if not exportacao.empty:
    exportacao.insert(0, "Período", periodo)
secao_exportacao(exportacao, nome_arquivo="produtividade_contratos", chave="produtividade_contratos", titulo="Exportação", subtitulo="Resumo agregado por base e supervisor.")
fechar_dashboard()
