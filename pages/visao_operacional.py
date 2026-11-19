"""Visão Operacional Unificada — O.S., contratos atendidos e consultivos.

Reúne em um único painel as três lentes que a operação acompanha separadamente:

* **O.S.** — volume de produção da base ``dados_prod`` (uma linha = uma O.S.);
* **Contratos** — identificadores de clientes atendidos na produção;
* **Consultivos** — base ``dados_cons`` (aba ``Consultivo``) com consultivos e
  mix de produtos (Mesh / TV / Virtua).

As fontes não compartilham uma chave única: o cruzamento é feito pelas
dimensões operacionais comuns (**base** e **supervisor/monitor**) e pelo
**tempo**. Rótulos são normalizados (caixa alta, sem acento) antes de casar,
para que ``GRS-TOTALE`` e ``grs totale`` apontem para a mesma linha. A página é
tolerante: sem consultivos carregados, as visões de produção continuam de pé.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from components.componentes import aplicar_estilo
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.kpi_cards import render_kpi_row
from components.layout_pagina import secao
from components.sidebar import render_page_sidebar_theme_selector
from services.dados_sessao import CHAVE_CONSULTIVO, exigir_base, obter_base, resumir_carga
from services.produtividade import rotulo_dimensao
from services.produtividade_contratos import (
    agrupar,
    diagnostico_os,
    distribuicao_contratos,
    preparar_producao,
    resumir,
)
from services.texto import formatar_inteiro, formatar_numero

logger = logging.getLogger(__name__)

PAGINA = "Produtividade · Contratos & Consultivos"
st.set_page_config(page_title=PAGINA, page_icon="📊", layout="wide")
aplicar_estilo()
render_page_sidebar_theme_selector()

#: Colunas numéricas oficiais da base de consultivos → nomes amigáveis.
MAPA_COLUNAS_CONSULTIVO = {
    "QTDE_CONSULTIVO": "Consultivos",
    "QTDE_PRODUTOS": "Produtos",
    "QTDE_MESH": "Mesh",
    "QTDE_TV": "TV",
    "QTDE_VIRTUA": "Virtua",
}


# ====================================================
# 🧱 PREPARAÇÃO DAS FONTES
# ====================================================
def preparar_consultivos(bruto: pd.DataFrame | None) -> pd.DataFrame | None:
    """Normaliza a base de consultivos para as dimensões do painel.

    Devolve ``None`` quando não há carga. Traz os campos numéricos para int,
    converte ``DATA`` e casa ``LOGIN NETSALES`` com a hierarquia compartilhada
    para herdar Monitor/Base. Sem hierarquia remota, usa colunas próprias da
    origem ou rótulo de não identificado — nunca quebra a página.
    """
    if bruto is None or bruto.empty:
        return None

    dados = bruto.copy()
    for origem_coluna, nome in MAPA_COLUNAS_CONSULTIVO.items():
        serie = dados[origem_coluna] if origem_coluna in dados.columns else pd.Series(0, index=dados.index)
        dados[nome] = pd.to_numeric(serie, errors="coerce").fillna(0).astype(int)

    if "DATA" in dados.columns:
        dados["Data"] = pd.to_datetime(dados["DATA"], errors="coerce", dayfirst=True)
    else:
        dados["Data"] = pd.NaT

    if "LOGIN NETSALES" not in dados.columns:
        dados["LOGIN NETSALES"] = pd.NA
    dados["Login"] = dados["LOGIN NETSALES"].astype("string").str.strip()

    # Hierarquia compartilhada (Monitor/Base) — opcional e tolerante a falha.
    try:
        from services.hierarquia import hierarquia_da_sessao

        hierarquia = hierarquia_da_sessao().rename(
            columns={"LOGIN": "Login", "MONITOR": "Monitor", "BASE": "Base"}
        )
        dados = dados.drop(columns=["Monitor", "Base"], errors="ignore")
        dados = pd.merge(dados, hierarquia[["Login", "Monitor", "Base"]], on="Login", how="left")
    except Exception as exc:  # pragma: no cover - depende do Drive em runtime
        logger.warning("Hierarquia indisponível na visão unificada: %s", exc)

    for coluna in ("Monitor", "Base"):
        if coluna not in dados.columns:
            dados[coluna] = pd.NA

    # Dimensões normalizadas para casar com a produção (mesmo rótulo canônico).
    dados["Supervisor"] = dados["Monitor"].map(rotulo_dimensao)
    dados["Base"] = dados["Base"].map(rotulo_dimensao)
    return dados.reset_index(drop=True)


origem = exigir_base(pagina=PAGINA)
dados, coluna_contrato = preparar_producao(origem)
consultivos = preparar_consultivos(obter_base(CHAVE_CONSULTIVO, abas=["Consultivo"]))

# ── Janela de datas comum às duas fontes ────────────────────────────────
datas_fontes = [serie for serie in (dados["Data"], *([] if consultivos is None else [consultivos["Data"]])) if serie.notna().any()]
if datas_fontes:
    minimo = min(serie.min() for serie in datas_fontes).date()
    maximo = max(serie.max() for serie in datas_fontes).date()
else:
    minimo = maximo = None

# ── Filtros transversais (produção + consultivos) ───────────────────────
bases_disponiveis = sorted({*dados["Base"].unique(), *([] if consultivos is None else consultivos["Base"].unique())})
supervisores_disponiveis = sorted({*dados["Supervisor"].unique(), *([] if consultivos is None else consultivos["Supervisor"].unique())})

with st.sidebar:
    st.markdown("### Filtros do painel")
    if minimo is not None:
        fim = st.date_input("Fim do período", value=maximo, key="unificada_fim")
        inicio = st.date_input("Início do período", value=max(minimo, maximo - timedelta(days=29)), key="unificada_inicio")
        if inicio > fim:
            inicio, fim = fim, inicio
        periodo_rotulo = f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
    else:
        inicio = fim = None
        periodo_rotulo = "Sem data reconhecida nas fontes"
        st.warning("Sem data reconhecida nas fontes: exibindo toda a carga, sem filtro por período.")
    bases = st.multiselect("Base", bases_disponiveis, key="unificada_bases")
    supervisores = st.multiselect("Supervisor / Monitor", supervisores_disponiveis, key="unificada_supervisores")
    projetos = st.multiselect("Projeto (produção)", sorted(dados["Projeto"].unique()), key="unificada_projetos")
    equipes = st.multiselect("Equipe (produção)", sorted(dados["Equipe"].unique()), key="unificada_equipes")
    st.caption("Base e Supervisor valem para produção e consultivos; Projeto e Equipe filtram apenas a produção.")
    if st.button("Limpar filtros", key="unificada_limpar"):
        for chave in ("unificada_fim", "unificada_inicio", "unificada_bases", "unificada_supervisores", "unificada_projetos", "unificada_equipes"):
            st.session_state.pop(chave, None)
        st.rerun()


def _filtrar_periodo(frame: pd.DataFrame) -> pd.DataFrame:
    if inicio is None or frame.empty or frame["Data"].isna().all():
        return frame
    return frame.loc[frame["Data"].dt.date.between(inicio, fim)].copy()


def _filtrar_dimensoes(frame: pd.DataFrame, *, com_projeto_equipe: bool) -> pd.DataFrame:
    resultado = frame
    if bases:
        resultado = resultado.loc[resultado["Base"].isin(bases)]
    if supervisores:
        resultado = resultado.loc[resultado["Supervisor"].isin(supervisores)]
    if com_projeto_equipe:
        if projetos:
            resultado = resultado.loc[resultado["Projeto"].isin(projetos)]
        if equipes:
            resultado = resultado.loc[resultado["Equipe"].isin(equipes)]
    return resultado.copy()


recorte = _filtrar_periodo(_filtrar_dimensoes(dados, com_projeto_equipe=True))
resumo = resumir(recorte)
consulta_recorte = None if consultivos is None else _filtrar_periodo(_filtrar_dimensoes(consultivos, com_projeto_equipe=False))
if consulta_recorte is not None and consulta_recorte.empty:
    consulta_recorte = None  # recorte existe mas ficou vazio: trata como sem fonte

abrir_dashboard(
    PAGINA,
    subtitulo="Produção, contratos de clientes atendidos e consultivos em uma única leitura, por base e supervisor.",
    icone="📊",
    secoes=("Indicadores", "Evolução semanal", "Visão por base e supervisor", "Perfil dos contratos", "Consultivos e mix de produtos", "Exportação"),
    resumo=resumir_carga(st.session_state.get("dados_prod")),
    periodo=periodo_rotulo,
    origem="dados_prod (produção) · dados_cons (consultivos)",
)

if consultivos is None:
    st.info("Consultivos não carregados na sessão. As visões de O.S. e contratos seguem disponíveis; carregue a aba Consultivo (Atualização de Dados) para habilitar as seções comerciais.")

# ====================================================
# 🎯 INDICADORES
# ====================================================
with secao("Indicadores", icone="🎯", subtitulo="Volumes do recorte selecionado, por fonte."):
    coluna_os, repetidas, os_identificadas = diagnostico_os(origem)
    if coluna_os is not None:
        st.caption(f"Qualidade da carga de produção: {repetidas} repetição(ões) do identificador {coluna_os} em {os_identificadas} linha(s). Repetições não são removidas automaticamente.")
    cobertura = resumo["os_com_contrato"] / resumo["os"] * 100 if resumo["os"] else None

    render_kpi_row([
        {"label": "O.S. NO RECORTE", "valor": formatar_inteiro(resumo["os"]), "sub": "Uma linha da produção = uma O.S.", "icone": "📦", "tema": "azul"},
        {"label": "CONTRATOS ATENDIDOS", "valor": formatar_inteiro(resumo["contratos"]) if resumo["contratos"] is not None else "—", "sub": "Identificadores distintos", "icone": "📋", "tema": "verde"},
        {"label": "COBERTURA DE CONTRATO", "valor": f"{formatar_numero(cobertura, 1)}%" if cobertura is not None else "—", "sub": "O.S. com contrato identificado", "icone": "🔎", "tema": "laranja"},
        {"label": "PONTOS", "valor": formatar_numero(resumo["pontos"], 0) if pd.notna(resumo["pontos"]) else "—", "sub": "Soma informada na produção", "icone": "⚡", "tema": "roxo"},
    ], colunas=4)

    if consulta_recorte is not None:
        total_consultivos = int(consulta_recorte["Consultivos"].sum())
        total_produtos = int(consulta_recorte["Produtos"].sum())
        equipes_cons = consulta_recorte.loc[consulta_recorte["Consultivos"] > 0, "Login"].nunique()
        conversao = equipes_cons / consulta_recorte["Login"].nunique() * 100 if consulta_recorte["Login"].nunique() else None
        render_kpi_row([
            {"label": "CONSULTIVOS", "valor": formatar_inteiro(total_consultivos), "sub": "Qtde. consultivo no recorte", "icone": "📞", "tema": "azul"},
            {"label": "PRODUTOS", "valor": formatar_inteiro(total_produtos), "sub": "Mesh + TV + Virtua somam à parte", "icone": "🛒", "tema": "verde"},
            {"label": "EQUIPES COM CONSULTIVO", "valor": formatar_inteiro(equipes_cons), "sub": "Logins com ao menos 1", "icone": "👥", "tema": "roxo"},
            {"label": "CONVERSÃO DE EQUIPES", "valor": f"{formatar_numero(conversao, 1)}%" if conversao is not None else "—", "sub": "Com consultivo ÷ com login", "icone": "✅", "tema": "laranja"},
        ], colunas=4)

    avisos: list[str] = []
    if coluna_contrato is None:
        avisos.append("Nenhuma coluna de contrato reconhecida na produção; indicadores de contrato indisponíveis.")
    elif cobertura is not None and cobertura < 100:
        avisos.append(f"Contrato presente em {cobertura:.1f}% das O.S.; contratos distintos são contagem parcial.")
    if recorte["Pontos"].isna().all() and not recorte.empty:
        avisos.append("Coluna de pontos indisponível na produção.")
    for aviso in avisos:
        st.warning(aviso)

# ====================================================
# 📈 EVOLUÇÃO SEMANAL
# ====================================================
def _semana(serie_data: pd.Series) -> pd.Series:
    return serie_data - pd.to_timedelta(serie_data.dt.day_of_week, unit="D")


with secao("Evolução semanal", icone="📈", subtitulo="Produção e consultivos alinhados pela semana (segunda-feira)."):
    # Cada fonte contribui com um pedaço de métricas disjuntas; o merge externo
    # pela semana não duplica nomes porque produção e consultivos não os compartilham.
    pedacos: list[pd.DataFrame] = []
    producao_com_data = recorte.dropna(subset=["Data"])
    if not producao_com_data.empty:
        semanas_prod = producao_com_data.copy()
        semanas_prod["Semana"] = _semana(semanas_prod["Data"])
        pedacos.append(
            semanas_prod.groupby("Semana", as_index=False).agg(
                **{"O.S.": ("O.S.", "size"), "Contratos": ("Contrato", "nunique")}
            )
        )
    if consulta_recorte is not None and consulta_recorte["Data"].notna().any():
        semanas_cons = consulta_recorte.dropna(subset=["Data"]).copy()
        semanas_cons["Semana"] = _semana(semanas_cons["Data"])
        pedacos.append(
            semanas_cons.groupby("Semana", as_index=False).agg(
                Consultivos=("Consultivos", "sum"), Produtos=("Produtos", "sum")
            )
        )

    if not pedacos:
        st.info("Não há registros com data no recorte para montar a evolução semanal.")
    else:
        semanal = pedacos[0]
        for extra in pedacos[1:]:
            semanal = semanal.merge(extra, on="Semana", how="outer")
        semanal = semanal.sort_values("Semana").reset_index(drop=True)
        for coluna in ("O.S.", "Contratos", "Consultivos", "Produtos"):
            if coluna in semanal.columns:
                semanal[coluna] = pd.to_numeric(semanal[coluna], errors="coerce").fillna(0)

        metricas_producao = [c for c in ("O.S.", "Contratos") if c in semanal.columns]
        metricas_comercial = [c for c in ("Consultivos", "Produtos") if c in semanal.columns]
        col_esq, col_dir = st.columns(2)
        with col_esq:
            if metricas_producao:
                fig_os = px.line(semanal, x="Semana", y=metricas_producao, markers=True, title="O.S. e contratos por semana")
                fig_os.update_layout(legend_title_text=None)
                st.plotly_chart(fig_os, width="stretch")
            else:
                st.info("Sem produção com data para a evolução de O.S.")
        with col_dir:
            if metricas_comercial:
                fig_cons = px.line(semanal, x="Semana", y=metricas_comercial, markers=True, title="Consultivos e produtos por semana")
                fig_cons.update_layout(legend_title_text=None)
                st.plotly_chart(fig_cons, width="stretch")
            else:
                st.info("Consultivos sem data ou não carregados para a evolução comercial.")
        st.caption("Semanas começam na segunda-feira; bordas podem ser parciais. Contratos semanais não são somáveis entre semanas.")

# ====================================================
# 🧭 VISÃO POR BASE E SUPERVISOR
# ====================================================
with secao("Visão por base e supervisor", icone="🧭", subtitulo="As três lentes casadas pela dimensão operacional comum."):
    consolidado = agrupar(recorte, ["Base", "Supervisor"]).rename(
        columns={"O.S. com contrato": "O.S. c/ contrato"}
    )
    if consulta_recorte is not None:
        por_sup_consulta = (
            consulta_recorte.groupby(["Base", "Supervisor"], as_index=False)
            .agg(Consultivos=("Consultivos", "sum"), Produtos=("Produtos", "sum"))
        )
        consolidado = consolidado.merge(por_sup_consulta, on=["Base", "Supervisor"], how="outer")
    if consolidado.empty:
        st.info("Nenhum registro nas fontes para os filtros selecionados.")
    else:
        for coluna in ("O.S.", "Contratos", "O.S. c/ contrato", "Pontos", "Consultivos", "Produtos"):
            if coluna in consolidado.columns:
                consolidado[coluna] = pd.to_numeric(consolidado[coluna], errors="coerce").fillna(0)
        ordenacao = [c for c in ("O.S.", "Consultivos") if c in consolidado.columns]
        consolidado["_total"] = consolidado[[c for c in ("O.S.", "Consultivos") if c in consolidado.columns]].sum(axis=1)
        consolidado = consolidado.sort_values("_total", ascending=False).reset_index(drop=True)

        destaque = consolidado.head(20).melt(
            id_vars=["Base", "Supervisor"],
            value_vars=[c for c in ("O.S.", "Consultivos") if c in consolidado.columns],
            var_name="Métrica", value_name="Valor",
        )
        if not destaque.empty:
            st.plotly_chart(
                px.bar(destaque, x="Supervisor", y="Valor", color="Métrica", barmode="group",
                       hover_data=["Base"], title="Top 20 — O.S. × Consultivos por supervisor"),
                width="stretch",
            )
        exibicao = consolidado.drop(columns="_total")
        st.dataframe(exibicao, hide_index=True, width="stretch")
        st.caption("Casamento por base e supervisor normalizados. Supervisors presentes em apenas uma fonte aparecem com zero na outra; contratos distintos não são somáveis entre grupos.")

# ====================================================
# 📋 PERFIL DOS CONTRATOS
# ====================================================
with secao("Perfil dos contratos", icone="📋", subtitulo="Frequência dos atendimentos por contrato identificado."):
    distribuicao = distribuicao_contratos(recorte)
    if distribuicao.empty:
        st.info("Sem contratos identificados no recorte; não há perfil a calcular.")
    else:
        media = resumo["os_com_contrato"] / resumo["contratos"] if resumo["contratos"] else None
        render_kpi_row([
            {"label": "O.S. POR CONTRATO IDENTIFICADO", "valor": formatar_numero(media, 2) if media is not None else "—",
             "sub": "Linhas com contrato ÷ contratos distintos", "icone": "📋", "tema": "verde"},
        ], colunas=1)
        st.plotly_chart(px.bar(distribuicao, x="O.S. por contrato", y="Contratos", title="Distribuição de contratos por número de O.S."), width="stretch")
        st.caption("Cada linha da produção conta como uma O.S.; múltiplas O.S. no mesmo contrato não significam retorno ou falha.")

# ====================================================
# 📞 CONSULTIVOS E MIX DE PRODUTOS
# ====================================================
with secao("Consultivos e mix de produtos", icone="📞", subtitulo="Volume comercial e composição de produtos vendidos."):
    if consulta_recorte is None:
        st.info("Sem consultivos no recorte (ou fonte não carregada). Carregue a aba Consultivo para esta visão.")
    else:
        mix = pd.DataFrame({
            "Produto": ["Mesh", "TV", "Virtua"],
            "Quantidade": [int(consulta_recorte[c].sum()) for c in ("Mesh", "TV", "Virtua")],
        })
        col_mix, col_top = st.columns(2)
        with col_mix:
            if mix["Quantidade"].sum() > 0:
                st.plotly_chart(px.pie(mix, names="Produto", values="Quantidade", hole=0.45, title="Mix de produtos"), width="stretch")
            else:
                st.info("Nenhum produto registrado no recorte.")
        with col_top:
            por_monitor = (
                consulta_recorte.groupby("Supervisor", as_index=False)
                .agg(Consultivos=("Consultivos", "sum"))
                .sort_values("Consultivos", ascending=False)
                .head(15)
            )
            if not por_monitor.empty and por_monitor["Consultivos"].gt(0).any():
                st.plotly_chart(px.bar(por_monitor, x="Consultivos", y="Supervisor", orientation="h", title="Top 15 supervisores em consultivos"), width="stretch")
            else:
                st.info("Sem consultivos por supervisor no recorte.")

# ====================================================
# 📤 EXPORTAÇÃO
# ====================================================
exportacao = consolidado.drop(columns="_total", errors="ignore").copy()
if not exportacao.empty:
    exportacao.insert(0, "Período", periodo_rotulo)
secao_exportacao(exportacao, nome_arquivo="visao_unificada", chave="visao_unificada", titulo="Exportação", subtitulo="Resumo consolidado por base e supervisor.")

fechar_dashboard()
