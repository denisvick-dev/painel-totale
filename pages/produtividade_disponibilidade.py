"""Produtividade & Contratos — produção e contratos de clientes atendidos."""
from __future__ import annotations

from datetime import timedelta
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from components.componentes import aplicar_estilo
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.kpi_cards import render_kpi_row
from components.layout_pagina import secao
from components.sidebar import render_page_sidebar_theme_selector
from services.dados_sessao import exigir_base, resumir_carga
from services.produtividade_contratos import (
    agrupar,
    analisar_retornos,
    diagnostico_os,
    distribuicao_contratos,
    preparar_producao,
    preparar_retornos,
    resumir,
    resumo_equipes,
)
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
    projetos = st.multiselect("Projeto", sorted(dados["Projeto"].unique()), key="contratos_projetos")
    supervisores = st.multiselect("Supervisor", sorted(dados["Supervisor"].unique()), key="contratos_supervisores")
    equipes = st.multiselect("Equipe", sorted(dados["Equipe"].unique()), key="contratos_equipes")
    amostra_minima = st.number_input("Mínimo de equipe-dias para comparar", min_value=1, max_value=365, value=3, key="contratos_amostra")
    if st.button("Limpar filtros", key="contratos_limpar"):
        for chave in ("contratos_inicio", "contratos_fim", "contratos_projetos", "contratos_supervisores", "contratos_equipes", "contratos_amostra"):
            st.session_state.pop(chave, None)
        st.rerun()

filtrado = dados.copy()
for coluna, selecionados in (("Projeto", projetos), ("Supervisor", supervisores), ("Equipe", equipes)):
    if selecionados:
        filtrado = filtrado.loc[filtrado[coluna].isin(selecionados)]
recorte = filtrado.copy()
sem_data = int(recorte["Data"].isna().sum())
if inicio is not None and fim is not None:
    recorte = recorte.loc[recorte["Data"].dt.date.between(inicio, fim)].copy()
resumo = resumir(recorte)
por_supervisor = agrupar(recorte, ["Projeto", "Supervisor"])
periodo = f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}" if inicio is not None else "Toda a carga (sem data)"

abrir_dashboard(
    PAGINA, subtitulo="Produção e contratos de clientes atendidos, por projeto, supervisor e equipe.",
    icone="📊", secoes=("Indicadores", "Evolução", "Detalhe", "Produtividade por equipe", "Perfil dos contratos", "Retornos e reincidência", "Exportação"),
    resumo=resumir_carga(st.session_state.get("dados_prod")), periodo=periodo,
)

with secao("Indicadores", icone="🎯", subtitulo="Contratos identificados e produção no recorte selecionado."):
    coluna_os, repetidas, os_identificadas = diagnostico_os(origem)
    if coluna_os is None:
        st.info("Não foi possível verificar O.S. repetidas: identificador de O.S. não reconhecido na carga.")
    else:
        st.caption(f"Qualidade da carga completa: {repetidas} repetição(ões) do identificador {coluna_os} em {os_identificadas} linha(s) identificadas. Repetições não são removidas automaticamente.")
    projetos_nao_informados = int(recorte["Projeto"].eq("NÃO INFORMADO").sum())
    if projetos_nao_informados:
        st.warning(f"{projetos_nao_informados} linha(s) sem projeto reconhecido no recorte. Não usamos base ou contrato como projeto; confira a coluna Projeto da produção.")
    cobertura = resumo["os_com_contrato"] / resumo["os"] * 100 if resumo["os"] else None
    if coluna_contrato is None:
        st.warning("Nenhuma coluna de identificador de contrato reconhecida na produção. Os indicadores de contratos estão indisponíveis; O.S. não são usadas como substituto.")
    elif cobertura is not None and cobertura < 100:
        st.warning(f"Identificador de contrato presente em {cobertura:.1f}% das O.S. do recorte. Contratos distintos são uma contagem parcial.")
    if recorte["Pontos"].isna().all() and not recorte.empty:
        st.info("Coluna de pontos indisponível na carga; a soma de pontos não será exibida.")
    if sem_data:
        st.warning(f"{sem_data} linha(s) sem data nos filtros de equipe/projeto/supervisor " + ("foram excluídas do período." if inicio is not None else "não podem ser filtradas por período."))
    if resumo["os"] and resumo["os_com_equipe_data"] < resumo["os"]:
        st.info("O.S./equipe-dia considera apenas linhas com equipe e data identificadas; não mede disponibilidade ou escala.")
    ncontratos = resumo["contratos"]
    render_kpi_row([
        {"label": "O.S. NO RECORTE", "valor": formatar_inteiro(resumo["os"]), "sub": "Uma linha da carga = uma O.S.", "icone": "📦", "tema": "azul"},
        {"label": "CONTRATOS ATENDIDOS", "valor": formatar_inteiro(ncontratos) if ncontratos is not None else "—", "sub": "Identificadores distintos", "icone": "📋", "tema": "verde"},
        {"label": "COBERTURA DE CONTRATO", "valor": f"{formatar_numero(cobertura, 1)}%" if cobertura is not None else "—", "sub": "O.S. com contrato identificado", "icone": "🔎", "tema": "laranja"},
        {"label": "O.S. / EQUIPE-DIA", "valor": formatar_numero(resumo["os_equipe_dia"], 2) if resumo["os_equipe_dia"] is not None else "—", "sub": "Somente equipes e dias com produção", "icone": "⚙️", "tema": "roxo"},
    ], colunas=4)
    if inicio is not None:
        duracao = (fim - inicio).days + 1
        fim_anterior = inicio - timedelta(days=1)
        inicio_anterior = fim_anterior - timedelta(days=duracao - 1)
        anterior = filtrado.loc[filtrado["Data"].dt.date.between(inicio_anterior, fim_anterior)]
        anterior_resumo = resumir(anterior)
        datas_filtradas = filtrado["Data"].dropna()
        # Extremos e cobertura são verificações necessárias, não prova de completude.
        comparavel = (not datas_filtradas.empty and not sem_data and not recorte.empty and not anterior.empty
                      and datas_filtradas.min().date() <= inicio_anterior
                      and datas_filtradas.max().date() >= fim
                      and cobertura is not None and cobertura >= 90
                      and anterior_resumo["os_com_contrato"] / anterior_resumo["os"] >= .9)
        if comparavel:
            st.markdown(f"**Comparação com {inicio_anterior:%d/%m/%Y} a {fim_anterior:%d/%m/%Y}**")
            comparativos = []
            for label, atual_val, anterior_val in (
                ("O.S.", resumo["os"], anterior_resumo["os"]),
                ("Contratos", resumo["contratos"], anterior_resumo["contratos"]),
                ("O.S./equipe-dia", resumo["os_equipe_dia"], anterior_resumo["os_equipe_dia"]),
            ):
                confiavel_equipe = (label != "O.S./equipe-dia" or
                                    (resumo["os_com_equipe_data"] / resumo["os"] >= .9 and
                                     anterior_resumo["os_com_equipe_data"] / anterior_resumo["os"] >= .9))
                delta = ((atual_val / anterior_val - 1) * 100 if confiavel_equipe and atual_val is not None
                         and anterior_val is not None and anterior_val != 0 else None)
                comparativos.append({"label": label, "valor": formatar_numero(atual_val, 2) if atual_val is not None else "—", "delta": f"{delta:+.1f}%" if delta is not None else "", "sub": "vs. período anterior"})
            render_kpi_row(comparativos, colunas=3)
            st.caption("Períodos de mesma duração em dias corridos. Variação de equipe-dia exige 90% de linhas com equipe e data em ambos os períodos. Limites de data e cobertura de contrato não garantem carga completa; confira dias sem produção e equipe ausente da base.")
        else:
            st.info("Comparação anterior indisponível: é preciso dados nos dois períodos, datas válidas abrangendo seus limites e cobertura de contrato de pelo menos 90% em ambos. Os limites não comprovam completude.")
    st.caption(f"O.S. com equipe e data: {resumo['os_com_equipe_data']} de {resumo['os']} · Equipe-dias observados: {resumo['equipes_dia']} · Coluna de contrato: {coluna_contrato or 'não encontrada'}.")

with secao("Evolução", icone="📈", subtitulo="Produção diária no período selecionado."):
    diarios = recorte.dropna(subset=["Data"])
    if diarios.empty:
        st.info("Não há produção com data reconhecida neste recorte.")
    else:
        semanas = diarios.copy()
        semanas["Semana"] = semanas["Data"] - pd.to_timedelta(semanas["Data"].dt.day_of_week, unit="D")
        serie = agrupar(semanas, ["Semana"]).sort_values("Semana")
        col_os, col_contratos = st.columns(2)
        with col_os:
            st.plotly_chart(px.line(serie, x="Semana", y="O.S.", markers=True, title="O.S. por semana"), width="stretch")
        with col_contratos:
            if serie["Contratos"].notna().any():
                st.plotly_chart(px.line(serie, x="Semana", y="Contratos", markers=True, title="Contratos distintos por semana"), width="stretch")
            else:
                st.info("Sem contratos identificados para a evolução semanal.")
        st.caption("Semanas começam na segunda-feira; as bordas podem ser parciais. Contratos semanais não são somáveis: o mesmo contrato pode aparecer em várias semanas.")

with secao("Detalhe", icone="🧾", subtitulo="O.S., contratos identificados e pontos por projeto e supervisor."):
    if por_supervisor.empty:
        st.info("Nenhuma produção encontrada para os filtros selecionados.")
    else:
        st.dataframe(por_supervisor, hide_index=True, width="stretch")
        st.caption("Contratos distintos por grupo não são somáveis: um mesmo contrato pode aparecer em mais de uma equipe, projeto ou supervisor.")
    with st.expander("Como calculamos"):
        st.markdown("""- **O.S.**: cada linha da carga de produção é considerada uma O.S.; duplicações na origem não são removidas.
- **Contratos atendidos**: identificadores de contratos de clientes distintos no recorte; valores vazios ou inválidos são excluídos. Sem identificador, não há estimativa.
- **O.S./equipe-dia observado**: linhas com equipe e data ÷ combinações distintas de projeto, supervisor, equipe e dia com produção. Não mede quadro, presença, disponibilidade nem produtividade de equipes sem produção.
- **Pontos**: soma dos pontos informados na produção; confira a cobertura da origem.
- Períodos filtram pela data da produção; linhas sem data são excluídas quando há datas reconhecidas.
""")

with secao("Produtividade por equipe", icone="⚙️", subtitulo="Comparação de volume e produtividade observada por equipe."):
    equipes_resumo = resumo_equipes(recorte)
    if equipes_resumo.empty:
        st.info("Nenhuma equipe no recorte.")
    else:
        st.dataframe(equipes_resumo, hide_index=True, width="stretch")
        comparaveis = equipes_resumo.loc[equipes_resumo["Equipe-dias"] >= amostra_minima].copy()
        if comparaveis.empty:
            st.info(f"Nenhuma equipe atingiu {amostra_minima} equipe-dia(s) observados para comparação.")
        else:
            comparaveis["Equipe exibida"] = comparaveis["Projeto"] + " · " + comparaveis["Supervisor"] + " · " + comparaveis["Equipe"]
            st.plotly_chart(px.bar(comparaveis.sort_values("O.S./equipe-dia").tail(20), x="O.S./equipe-dia", y="Equipe exibida", orientation="h", title="Produtividade das equipes comparáveis"), width="stretch")
            st.plotly_chart(px.scatter(comparaveis, x="O.S. com data", y="O.S./equipe-dia", size="Equipe-dias", color="Projeto", hover_name="Equipe exibida", title="Volume × produtividade observada"), width="stretch")
        st.caption("Mínimo aplicado somente aos gráficos comparativos. O.S. com data usa apenas linhas elegíveis; equipe-dias não representam disponibilidade, escala ou equipes sem produção.")

with secao("Perfil dos contratos", icone="📋", subtitulo="Frequência dos atendimentos por contrato identificado."):
    distribuicao = distribuicao_contratos(recorte)
    if distribuicao.empty:
        st.info("Sem contratos identificados no recorte; não há perfil a calcular.")
    else:
        media = resumo["os_com_contrato"] / resumo["contratos"]
        render_kpi_row([{"label": "O.S. POR CONTRATO IDENTIFICADO", "valor": formatar_numero(media, 2), "sub": "Somente linhas com contrato válido ÷ contratos distintos"}], colunas=1)
        st.plotly_chart(px.bar(distribuicao, x="O.S. por contrato", y="Contratos", title="Distribuição de contratos por número de O.S."), width="stretch")
        st.caption("Cada linha da carga conta como uma O.S. Múltiplas O.S. no mesmo contrato não significam necessariamente retorno ou falha.")

with secao("Retornos e reincidência", icone="🔁", subtitulo="Coorte de contratos atendidos no recorte × retornos de arquivo TOA."):
    st.caption("Envie o arquivo TOA com contrato, data, tipo de atividade e status. São considerados apenas Retorno Credenciada não suspensos; o vínculo por contrato não comprova causa ou responsabilidade e pressupõe identificadores únicos entre unidades.")
    arquivo = st.file_uploader("Arquivo TOA de retornos (CSV ou Excel)", type=["csv", "xlsx"], key="contratos_retorno_arquivo")
    if arquivo is None:
        st.info("Envie a fonte de retornos para habilitar esta visão. A produção sozinha não identifica reincidência.")
    else:
        try:
            conteudo = arquivo.getvalue()
            if arquivo.name.lower().endswith(".csv"):
                try:
                    bruto_retorno = pd.read_csv(BytesIO(conteudo), sep=None, engine="python", dtype=str, encoding="utf-8-sig")
                except UnicodeDecodeError:
                    bruto_retorno = pd.read_csv(BytesIO(conteudo), sep=None, engine="python", dtype=str, encoding="latin-1")
            else:
                bruto_retorno = pd.read_excel(BytesIO(conteudo), dtype=str)
            retornos, qualidade_retorno = preparar_retornos(bruto_retorno)
        except (ValueError, OSError, pd.errors.ParserError) as exc:
            st.error(f"Não foi possível interpretar a fonte de retornos: {exc}")
        else:
            st.caption(f"Arquivo: {qualidade_retorno['origem']} linhas · {qualidade_retorno['selecionados']} retornos não suspensos · {qualidade_retorno['invalidos']} sem contrato ou data · {qualidade_retorno['sem_status']} sem status.")
            if inicio is None or recorte["Contrato"].notna().sum() == 0:
                st.warning("É necessário produção com data e contrato válidos no recorte para formar a coorte.")
            else:
                col_ini, col_fim = st.columns(2)
                with col_ini:
                    inicio_cobertura = st.date_input("Início da cobertura completa do TOA", value=inicio, key="retornos_cobertura_inicio")
                with col_fim:
                    fim_cobertura = st.date_input("Fim da cobertura completa do TOA", value=fim, key="retornos_cobertura_fim")
                confirmado = st.checkbox("Confirmo que o arquivo cobre integralmente o intervalo informado e as unidades selecionadas", key="retornos_confirmar_cobertura")
                st.caption("Informe a cobertura real do arquivo, incluindo até 30 dias após o atendimento. Só contratos cuja janela completa cabe nessa cobertura entram na taxa; retornos no mesmo dia não são considerados.")
                if inicio_cobertura > fim_cobertura:
                    st.error("O início da cobertura deve ser anterior ao fim.")
                elif not confirmado:
                    st.info("Confirme a cobertura para calcular taxas; ausência de registros não comprova ausência de retorno.")
                elif qualidade_retorno["invalidos"] or qualidade_retorno["sem_status"]:
                    st.warning("Taxas indisponíveis: corrija retornos sem contrato, data ou status antes de confirmar a cobertura.")
                else:
                    janela = st.radio("Janela após o atendimento", [7, 30], horizontal=True, key="retornos_janela")
                    coorte, eventos = analisar_retornos(recorte, retornos, inicio_cobertura, fim_cobertura, janela)
                    excluidos = recorte.dropna(subset=["Data", "Contrato"])["Contrato"].nunique() - len(coorte)
                    if coorte.empty:
                        st.info("Nenhum contrato com janela completa na cobertura declarada. Amplie o intervalo ou ajuste o período.")
                    else:
                        total = len(coorte)
                        com_retorno = int(coorte["Com retorno"].sum())
                        render_kpi_row([
                            {"label": "CONTRATOS ELEGÍVEIS", "valor": str(total)},
                            {"label": f"COM RETORNO EM {janela} DIAS", "valor": str(com_retorno)},
                            {"label": "TAXA DE CONTRATOS COM RETORNO", "valor": f"{com_retorno / total * 100:.1f}%"},
                        ], colunas=3)
                        st.caption(f"{excluidos} contrato(s) fora do denominador por janela incompleta ou atribuição ambígua de projeto/supervisor no último dia. A coorte usa o último atendimento de cada contrato no recorte; o primeiro retorno posterior na janela é associado ao projeto e supervisor desse atendimento. Não identifica dono do retorno.")
                        por_grupo = coorte.groupby(["Projeto", "Supervisor"], as_index=False).agg(Contratos=("Contrato", "size"), Retornos=("Com retorno", "sum"))
                        por_grupo["Taxa (%)"] = (por_grupo["Retornos"] / por_grupo["Contratos"] * 100).round(1)
                        st.dataframe(por_grupo, hide_index=True, width="stretch")
                        serie_coorte = coorte.copy()
                        serie_coorte["Semana"] = serie_coorte["Atendimento"] - pd.to_timedelta(serie_coorte["Atendimento"].dt.day_of_week, unit="D")
                        evolucao = serie_coorte.groupby("Semana", as_index=False).agg(Contratos=("Contrato", "size"), Retornos=("Com retorno", "sum"))
                        evolucao["Taxa (%)"] = evolucao["Retornos"] / evolucao["Contratos"] * 100
                        st.plotly_chart(px.line(evolucao, x="Semana", y="Taxa (%)", markers=True, title=f"Taxa de retorno em {janela} dias por semana de atendimento"), width="stretch")
                        if qualidade_retorno["tem_motivo"] and not eventos.empty:
                            motivos = eventos.loc[eventos["Motivo"].ne("")].groupby("Motivo").size().sort_values(ascending=False).reset_index(name="Contratos")
                            if not motivos.empty:
                                motivos["Acumulado (%)"] = motivos["Contratos"].cumsum() / motivos["Contratos"].sum() * 100
                                fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
                                fig_pareto.add_trace(go.Bar(x=motivos["Motivo"], y=motivos["Contratos"], name="Contratos"), secondary_y=False)
                                fig_pareto.add_trace(go.Scatter(x=motivos["Motivo"], y=motivos["Acumulado (%)"], name="Acumulado (%)", mode="lines+markers"), secondary_y=True)
                                fig_pareto.update_layout(title="Pareto dos motivos informados do primeiro retorno")
                                fig_pareto.update_yaxes(title_text="Contratos", secondary_y=False)
                                fig_pareto.update_yaxes(title_text="Acumulado (%)", range=[0, 100], secondary_y=True)
                                st.plotly_chart(fig_pareto, width="stretch")
                                st.caption("Motivos vazios não entram no Pareto; percentuais acumulados referem-se apenas aos motivos informados.")
                        else:
                            st.info("Pareto indisponível: não há coluna de motivo ou retornos vinculados na janela.")

exportacao = por_supervisor.copy()
if not exportacao.empty:
    exportacao.insert(0, "Período", periodo)
secao_exportacao(exportacao, nome_arquivo="produtividade_contratos", chave="produtividade_contratos", titulo="Exportação", subtitulo="Resumo agregado por projeto e supervisor.")
fechar_dashboard()
