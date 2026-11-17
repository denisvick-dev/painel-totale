"""Apresentação da força de trabalho, separada das regras de disponibilidade."""
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.kpi_cards import render_kpi_row
from services.texto import formatar_inteiro, formatar_percentual


def agrupar_visao(resumo: pd.DataFrame, dimensao: str) -> pd.DataFrame:
    """Recalcula a taxa ponderada, sem tirar média dos percentuais de monitores."""
    grupo = resumo.groupby(dimensao, as_index=False)[["Quadro", "Ausentes", "Disponíveis estimados"]].sum()
    grupo["Disponibilidade (%)"] = (grupo["Disponíveis estimados"] / grupo["Quadro"] * 100).round(1)
    return grupo.sort_values(["Disponibilidade (%)", dimensao], kind="stable")


def excel_forca_trabalho(resumo: pd.DataFrame, detalhes: pd.DataFrame, dia: date) -> bytes:
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nome, tabela in (("Resumo", resumo), ("Técnicos", detalhes)):
            exportar = tabela.copy()
            exportar["Data de referência"] = dia.strftime("%d/%m/%Y")
            exportar.to_excel(writer, index=False, sheet_name=nome)
            aba = writer.sheets[nome]
            aba.freeze_panes = "C2"
            aba.auto_filter.ref = aba.dimensions
            for celula in aba[1]:
                celula.fill = PatternFill("solid", fgColor="012869")
                celula.font = Font(color="FFFFFF", bold=True)
            for i, coluna in enumerate(exportar.columns, start=1):
                maior = max([len(str(coluna)), *exportar[coluna].fillna("").astype(str).str.len().tolist()])
                aba.column_dimensions[get_column_letter(i)].width = min(42, maior + 3)
    return buffer.getvalue()


def render_forca_trabalho(resumo: pd.DataFrame, detalhes: pd.DataFrame, dia: date) -> None:
    total = int(resumo["Quadro"].sum())
    ausentes = int(resumo["Ausentes"].sum())
    disponiveis = total - ausentes
    taxa = disponiveis / total if total else 0
    render_kpi_row([
        {"label": "Quadro cadastrado", "valor": formatar_inteiro(total), "icone": "groups",
         "sub": "Técnicos únicos no recorte", "tema": "azul"},
        {"label": "Disponíveis estimados", "valor": formatar_inteiro(disponiveis), "icone": "badge",
         "sub": "Sem ausência registrada no dia", "tema": "verde"},
        {"label": "Ausências registradas", "valor": formatar_inteiro(ausentes), "icone": "event_busy",
         "sub": "Todos os tipos · sem duplicidade", "tema": "laranja"},
        {"label": "Disponibilidade estimada", "valor": formatar_percentual(taxa), "icone": "donut_large",
         "sub": f"Referência: {dia:%d/%m/%Y}", "tema": "azul", "progresso": (disponiveis, total),
         "ajuda": "Não confirma presença ou escala. Pessoas sem lançamento também entram nesta estimativa."},
    ])
    visao, equipe = st.tabs(["Visão operacional", "Consultar equipe"])
    with visao:
        with st.container(border=True):
            col_titulo, col_grupo = st.columns([2, 1])
            with col_titulo:
                st.markdown("#### Distribuição da equipe")
                st.caption("Disponibilidade estimada e ausências, em quantidade de técnicos.")
            with col_grupo:
                dimensao = st.selectbox("Agrupar força de trabalho por", ["Base", "Monitor"], key="forca_agrupar")
            grupo = agrupar_visao(resumo, dimensao)
            # Limita a altura para equipes grandes; o detalhamento completo fica abaixo.
            exibido = grupo.head(15)
            grafico = go.Figure()
            for campo, nome, cor in (
                ("Disponíveis estimados", "Disponíveis estimados", "#157F78"),
                ("Ausentes", "Ausências registradas", "#E99035"),
            ):
                grafico.add_trace(go.Bar(
                    y=exibido[dimensao], x=exibido[campo], name=nome, orientation="h",
                    marker_color=cor, text=exibido[campo], textposition="auto",
                    hovertemplate="%{y}<br>" + nome + ": %{x}<extra></extra>",
                ))
            grafico.update_layout(
                barmode="stack", height=max(260, len(exibido) * 42 + 95),
                margin=dict(l=0, r=15, t=10, b=10),
                legend=dict(orientation="h", y=1.12, x=0),
                xaxis=dict(title="Técnicos", rangemode="tozero", dtick=1 if total < 15 else None),
                yaxis=dict(title=None, autorange="reversed"),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(grafico, width="stretch", key="forca_distribuicao", config={"displayModeBar": False})
            if len(grupo) > 15:
                st.caption("Gráfico: 15 grupos com menor disponibilidade percentual. Consulte todos na tabela abaixo.")
        st.markdown("##### Disponibilidade por base e monitor")
        st.caption("Ordenado da menor para a maior disponibilidade. A ordem não representa uma meta de desempenho.")
        st.dataframe(
            resumo.sort_values(["Disponibilidade (%)", "Base", "Monitor"]),
            column_config={
                "Disponibilidade (%)": st.column_config.ProgressColumn(
                    "Disponibilidade estimada", min_value=0, max_value=100, format="%.1f%%", width="medium",
                ),
                "Disponíveis estimados": st.column_config.NumberColumn("Disponíveis estimados", format="%d"),
            }, hide_index=True, width="stretch",
        )
    with equipe:
        col_busca, col_situacao = st.columns([2, 1])
        with col_busca:
            busca = st.text_input("Buscar na força de trabalho", placeholder="Nome ou login…", key="forca_busca")
        with col_situacao:
            situacao = st.selectbox("Situação da equipe", ["Todas", "Disponível estimado", "Ausência registrada"], key="forca_situacao")
        consulta = detalhes.copy()
        if busca.strip():
            nomes = consulta["Técnico"].fillna("") + " " + consulta["Login"].fillna("")
            consulta = consulta.loc[nomes.str.casefold().str.contains(busca.strip().casefold(), regex=False)]
        if situacao != "Todas":
            consulta = consulta.loc[consulta["Situação no dia"].eq(situacao)]
        st.caption(f"{len(consulta)} de {len(detalhes)} técnicos · filtros desta consulta não alteram os indicadores.")
        if consulta.empty:
            st.info("Nenhum técnico encontrado. Ajuste o nome, login ou situação.")
        else:
            st.dataframe(consulta[["Login", "Técnico", "Base", "Monitor", "Situação no dia", "Códigos", "U.N.", "RE"]], hide_index=True, width="stretch")
    with st.container(border=True):
        texto, botao = st.columns([2, 1])
        with texto:
            st.markdown("**Relatório da força de trabalho**")
            st.caption("Resumo e técnicos do recorte completo · data de referência incluída · Excel com filtros.")
        with botao:
            st.download_button(
                "Exportar relatório Excel", data=excel_forca_trabalho(resumo, detalhes, dia),
                file_name=f"forca_trabalho_{dia:%Y_%m_%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="absenteismo_forca_download", width="stretch",
            )
