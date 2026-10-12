"""Centraliza alertas observáveis das fontes de planilha e do robô local."""

from __future__ import annotations

import streamlit as st

from components.alertas_automaticos import Alerta, avaliar_alertas
from components.componentes import (
    aplicar_estilo,
    render_section_header,
)
from components.sidebar import render_page_sidebar_theme_selector


def _render_alerta(alerta: Alerta) -> None:
    icones = {"CRÍTICO": "🔴", "ALTO": "🟠", "MÉDIO": "🟡", "BAIXO": "🔵"}
    with st.container(border=True):
        st.markdown(f"{icones[alerta.severidade]} **{alerta.severidade} · {alerta.titulo}**")
        st.caption(f"Origem: {alerta.origem}")
        st.text(alerta.detalhe)


st.set_page_config(
    page_title="Alertas automáticos | TOTALE",
    page_icon="⚠️",
    layout="wide",
)

aplicar_estilo()
render_page_sidebar_theme_selector()

st.title("Alertas automáticos")
st.caption("Sinais calculados a partir do estado atual das fontes sincronizadas e do robô local.")
alertas = avaliar_alertas(dict(st.session_state))

criticos = sum(alerta.severidade == "CRÍTICO" for alerta in alertas)
altos = sum(alerta.severidade == "ALTO" for alerta in alertas)
medios = sum(alerta.severidade == "MÉDIO" for alerta in alertas)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Alertas ativos", len(alertas))
c2.metric("Críticos", criticos)
c3.metric("Altos", altos)
c4.metric("Médios", medios)

render_section_header("notifications_active", "Fila de alertas")
if not alertas:
    st.success("Nenhum alerta ativo nas fontes verificadas nesta sessão.")
else:
    severidades = ["CRÍTICO", "ALTO", "MÉDIO", "BAIXO"]
    selecionadas = st.multiselect(
        "Filtrar por severidade",
        severidades,
        default=severidades,
        key="filtro_severidade_alertas",
    )
    visiveis = [a for a in alertas if a.severidade in selecionadas]
    if not visiveis:
        st.info("Nenhum alerta corresponde às severidades selecionadas.")
    for alerta in visiveis:
        _render_alerta(alerta)

with st.expander("O que este módulo verifica"):
    st.markdown(
        "- Falhas ou bloqueios relatados pelo robô local.\n"
        "- Processamento do robô ativo por mais de três minutos.\n"
        "- Duplicatas removidas no último ciclo.\n"
        "- Frescor da sincronização e consistência estrutural das bases carregadas.\n\n"
        "Os alertas são recalculados a cada execução da página e não representam um histórico persistente."
    )

links = st.columns(3)
with links[0]:
    st.page_link(
        "pages/envio_excel.py",
        label="Abrir saúde dos dados",
        icon="🩺",
        width="stretch",
    )
with links[1]:
    st.page_link(
        "pages/home.py",
        label="Voltar ao cockpit",
        icon="🏠",
        width="stretch",
    )
with links[2]:
    st.page_link(
        "robo/main.py",
        label="Abrir robô local",
        icon="🤖",
        width="stretch",
    )
