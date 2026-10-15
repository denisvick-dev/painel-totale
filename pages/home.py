"""
pages/home.py
=============
Home — Portal TOTALE de Inteligência Operacional

Versão: 3.6.0 (organização da informação, cartões de KPI avançados e gráficos
minimalistas TOTALE)
Autor: TOTALE Tecnologia

Evoluções desta versão:
• Página reorganizada na hierarquia de leitura ``ORDEM_PADRAO``
  (cabeçalho → sumário → filtros → KPIs → detalhamento → rodapé),
  usando os primitivos de ``components.layout_pagina``.
• Sumário com âncoras navegáveis: cada bloco vive em ``secao()`` com id estável.
• Barra de atualização fixa (sticky) no topo, sem perder o contexto ao rolar.
• ``st.metric`` substituído pelos cartões de KPI avançados
  (``components.kpi_cards``) com barra de progresso e ajuda.
• Rodapé padronizado do portal (marca, ambiente, horário e versão).
• Datas em português sem depender do locale configurado no servidor.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

import streamlit as st

from components.componentes import (
    Cores,
    aplicar_estilo,
    formatar_numero_br,
    render_hero_totale_1,
    render_hero_totale_2,
    render_insight,
    render_spacer,
)
from components.dashboard_kit import render_toggle_autorefresh
from components.kpi_cards import SpecKPIAvancado, render_kpi_row
from components.layout_pagina import (
    barra_filtros,
    render_rodape_pagina,
    render_sumario,
    secao,
)
from components.sidebar import render_page_sidebar_theme_selector
from services.cache_dados import temporizar
from services.dados_sessao import (
    CHAVE_ATUALIZACAO,
    CHAVE_PRODUCAO,
    obter_dataframe,
    resumir_carga,
    ultima_atualizacao,
)

logger = logging.getLogger(__name__)

# ====================================================
# 🔧 BLOCO 1: CONFIGURAÇÕES E CONSTANTES
# ====================================================
FUSO_BR = ZoneInfo("America/Sao_Paulo")
VERSAO_SISTEMA = "3.6.0"
AMBIENTE_SISTEMA = "Produção"
MESES_PT_BR = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


@dataclass(frozen=True)
class ResumoDados:
    """Métricas consolidadas da carga de produção disponível na sessão."""

    registros: int = 0
    tabelas: int = 0
    tabelas_com_dados: int = 0

    @property
    def carregado(self) -> bool:
        return self.tabelas > 0 or self.registros > 0


def resumir_dados_producao(dados: Any) -> ResumoDados:
    """Conta linhas e abas com dados, inclusive quando a carga é um dict de abas.

    A contagem em si vive em :func:`services.dados_sessao.resumir_carga` (fonte
    única do portal); aqui só adaptamos o resultado para o ``ResumoDados`` que a
    Home já expõe — inclusive para os testes em ``tests/test_home_dashboard.py``.
    """
    carga = resumir_carga(dados)
    return ResumoDados(
        registros=carga.registros,
        tabelas=carga.tabelas,
        tabelas_com_dados=carga.tabelas_com_dados,
    )


def formatar_data_pt_br(valor: datetime) -> str:
    """Formata a data em português sem depender do locale do sistema operacional."""
    return f"{valor.day} de {MESES_PT_BR[valor.month - 1]} de {valor.year}"


# ====================================================
# 🎨 BLOCO 2: CSS ESPECÍFICO E REFINADO DA HOME
# ====================================================
def _injetar_css_home() -> None:
    """Aplica estilos complementares com escopo seguro para a página Home."""
    st.markdown(
        f"""
        <style>
        /* Card executivo da Home */
        .totale-home-card {{
            background: #FFFFFF;
            border-radius: 14px;
            padding: 22px 24px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 2px 8px rgba(1, 40, 105, 0.04);
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
            box-sizing: border-box;
            position: relative;
            overflow: hidden;
        }}
        .totale-home-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 24px rgba(1, 40, 105, 0.08);
            border-color: #CBD5E1;
        }}
        .totale-home-card::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: {Cores.PRIMARIA};
        }}
        .totale-home-card--accent::before {{
            background: {Cores.SECUNDARIA};
        }}
        .totale-home-card--success::before {{
            background: {Cores.SUCESSO};
        }}

        .totale-home-card-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}
        .totale-home-icon-box {{
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: {Cores.AZUL_SUAVE};
            color: {Cores.PRIMARIA};
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            flex-shrink: 0;
        }}
        .totale-home-icon-box--orange {{
            background: {Cores.LARANJA_SUAVE};
            color: {Cores.SECUNDARIA};
        }}
        .totale-home-card-title {{
            font-family: var(--font-titulo, 'Manrope', sans-serif);
            font-size: 16px;
            font-weight: 800;
            color: {Cores.PRIMARIA};
            margin: 0;
            line-height: 1.25;
        }}
        .totale-home-card-desc {{
            font-size: 13px;
            color: #64748B;
            line-height: 1.55;
            margin: 0 0 16px 0;
            flex-grow: 1;
        }}
        .totale-home-features-list {{
            list-style: none;
            padding: 0;
            margin: 0 0 16px 0;
        }}
        .totale-home-features-list li {{
            font-size: 12px;
            color: #334155;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 0;
        }}
        .totale-home-features-list li::before {{
            content: "•";
            color: {Cores.SECUNDARIA};
            font-weight: bold;
            font-size: 14px;
        }}

        /* Card de boas-vindas executivo */
        .totale-home-welcome {{
            background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
            border: 1px solid #E2E8F0;
            border-left: 4px solid {Cores.PRIMARIA};
            border-radius: 14px;
            padding: 20px 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        }}

        /* Hub de Acesso Rápido */
        .totale-quick-link-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 12px 14px;
            font-size: 13px;
            font-weight: 700;
            color: {Cores.PRIMARIA};
            text-decoration: none;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
            transition: all 0.16s ease;
        }}
        .totale-quick-link-btn:hover {{
            background: #F8FAFC;
            border-color: {Cores.PRIMARIA};
            color: {Cores.PRIMARIA};
            box-shadow: 0 4px 12px rgba(1, 40, 105, 0.08);
            transform: translateY(-1px);
        }}

        /* Ajustes finos locais (o rodapé e os KPIs vêm do CSS global v3.6) */
        .totale-home-export {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# 🔧 BLOCO 3: HELPERS E EXTRAÇÃO DE DADOS
# ====================================================
def _agora() -> datetime:
    """Retorna datetime no fuso de São Paulo."""
    return datetime.now(FUSO_BR)


def _formatar_data_hora(valor: Any, *, com_segundos: bool = True) -> str:
    """Formata com segurança datetime, string ou timestamp."""
    if valor is None:
        return "Não disponível"
    if isinstance(valor, datetime):
        dt = valor if valor.tzinfo is not None else valor.replace(tzinfo=FUSO_BR)
        formato = "%d/%m/%Y às %H:%M:%S" if com_segundos else "%d/%m/%Y %H:%M"
        return dt.strftime(formato)
    txt = str(valor).strip()
    return txt if txt and txt.lower() != "none" else "Não disponível"


def _resumir_fontes(status_fontes: Any) -> list[dict[str, Any]]:
    """Normaliza objetos/status em dicts para a camada de apresentação."""
    if not isinstance(status_fontes, Mapping):
        return []

    resumo: list[dict[str, Any]] = []
    for nome, fonte in status_fontes.items():
        if isinstance(fonte, Mapping):
            ok = bool(fonte.get("ok", False))
            linhas = fonte.get("linhas", 0)
            ultimo_sucesso = fonte.get("ultimo_sucesso")
            ultima_tentativa = fonte.get("ultima_tentativa")
            erro = fonte.get("erro")
        else:
            ok = bool(getattr(fonte, "ok", False))
            linhas = getattr(fonte, "linhas", 0)
            ultimo_sucesso = getattr(fonte, "ultimo_sucesso", None)
            ultima_tentativa = getattr(fonte, "ultima_tentativa", None)
            erro = getattr(fonte, "erro", None)

        try:
            quantidade_linhas = max(0, int(linhas))
        except (TypeError, ValueError, OverflowError):
            quantidade_linhas = 0

        texto_erro = " ".join(str(erro or "").split())
        if len(texto_erro) > 180:
            texto_erro = f"{texto_erro[:179]}…"

        resumo.append(
            {
                "nome": str(nome),
                "ok": ok,
                "linhas": quantidade_linhas,
                "ultimo_sucesso": _formatar_data_hora(ultimo_sucesso, com_segundos=False),
                "ultima_tentativa": _formatar_data_hora(ultima_tentativa, com_segundos=False),
                "tem_sucesso_anterior": ultimo_sucesso is not None,
                "erro": texto_erro,
            }
        )
    return resumo


def _obter_metricas_base() -> dict[str, Any]:
    """Extrai métricas reais da carga e do estado das fontes na sessão."""
    resumo_dados = resumir_dados_producao(obter_dataframe(CHAVE_PRODUCAO))
    fontes = _resumir_fontes(st.session_state.get("status_fontes"))
    fontes_ok = sum(fonte["ok"] for fonte in fontes)

    if fontes:
        if fontes_ok == len(fontes):
            status_carga = "Atualizada"
        elif fontes_ok:
            status_carga = "Parcial"
        else:
            status_carga = "Com falhas"
    elif resumo_dados.tabelas:
        status_carga = "Dados disponíveis" if resumo_dados.registros else "Sem registros"
    else:
        status_carga = "Aguardando dados"

    atualizado_em = ultima_atualizacao(CHAVE_ATUALIZACAO)
    ultima_tentativa = st.session_state.get("ultima_tentativa_sync")
    return {
        "carregado": resumo_dados.carregado,
        "total_linhas": resumo_dados.registros,
        "tabelas": resumo_dados.tabelas,
        "tabelas_com_dados": resumo_dados.tabelas_com_dados,
        "fontes": fontes,
        "fontes_total": len(fontes),
        "fontes_ok": fontes_ok,
        "fontes_com_falha": [fonte["nome"] for fonte in fontes if not fonte["ok"]],
        "status_carga": status_carga,
        "ultima_atualizacao": _formatar_data_hora(atualizado_em),
        "ultima_atualizacao_curta": _formatar_data_hora(atualizado_em, com_segundos=False),
        "ultima_tentativa": _formatar_data_hora(ultima_tentativa),
        "ultima_tentativa_curta": _formatar_data_hora(ultima_tentativa, com_segundos=False),
    }


# ====================================================
# 🧩 BLOCO 4: COMPONENTES DA PÁGINA
# ====================================================
def render_header(info_base: dict[str, Any]) -> None:
    """Renderiza o Hero Banner adaptativo da TOTALE."""
    data_hoje = formatar_data_pt_br(_agora())

    if info_base["carregado"]:
        render_hero_totale_2(
            titulo="Portal TOTALE — Inteligência Operacional",
            subtitulo=f"Visão consolidada de produção, eficiência de campo e indicadores estratégicos. {data_hoje}.",
            valor_destaque=formatar_numero_br(info_base["total_linhas"]),
            label_destaque="REGISTROS NAS ABAS DE PRODUÇÃO",
            badge=info_base["status_carga"].upper(),
            tag_info=f"Última fonte atualizada: {info_base['ultima_atualizacao']}",
        )
    else:
        render_hero_totale_1(
            titulo="Portal TOTALE — Inteligência Operacional",
            subtitulo="Acompanhe produção, eficiência de campo e indicadores estratégicos em um só lugar.",
            badge="AGUARDANDO DADOS",
            icone="⚡",
            meta_info=f"Última tentativa: {info_base['ultima_tentativa']} • {data_hoje} • São Paulo/SP",
        )


def render_boas_vindas() -> None:
    """Renderiza mensagem executiva de introdução."""
    st.markdown(
        f"""
        <div class="totale-home-welcome">
            <div style="display:flex;align-items:flex-start;gap:14px;">
                <span style="font-size:24px;line-height:1;">🏢</span>
                <div style="flex:1;min-width:0;">
                    <strong style="color:{Cores.PRIMARIA};font-size:15px;display:block;margin-bottom:4px;">
                        Bem-vindo ao Portal de Inteligência e Performance da TOTALE
                    </strong>
                    <p style="margin:0;font-size:13.5px;color:#334155;line-height:1.6;">
                        Este ambiente centraliza as bases de dados corporativas, fornecendo suporte analítico de alta precisão
                        para tomada de decisão, controle de execução em campo e acompanhamento de indicadores estratégicos.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_strip(info_base: dict[str, Any]) -> None:
    """Renderiza indicadores derivados da carga e do estado real das fontes.

    Usa os cartões de KPI avançados (``components.kpi_cards``): barra de
    progresso nas fontes, ajuda contextual e hierarquia visual consistente —
    substituem o ``st.metric`` padrão em todo o portal.
    """
    status_carga = info_base["status_carga"]
    temas_status: dict[str, Literal["azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"]] = {
        "Atualizada": "verde",
        "Parcial": "laranja",
        "Com falhas": "vermelho",
        "Dados disponíveis": "azul",
        "Sem registros": "laranja",
        "Aguardando dados": "cinza",
    }
    tema_status = temas_status.get(status_carga, "cinza")

    detalhe_status = (
        f"{info_base['fontes_ok']} de {info_base['fontes_total']} fontes atualizadas"
        if info_base["fontes_total"]
        else "Estado das fontes não disponível"
    )
    registros = formatar_numero_br(info_base["total_linhas"]) if info_base["carregado"] else "—"
    total_tabelas = info_base["tabelas"]
    if info_base["fontes_total"]:
        valor_fontes = f"{info_base['fontes_ok']}/{info_base['fontes_total']}"
        subtitulo_fontes = "Fontes com atualização bem-sucedida"
        tema_fontes: Literal["azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"] = (
            "verde"
            if info_base["fontes_ok"] == info_base["fontes_total"]
            else "vermelho"
            if not info_base["fontes_ok"]
            else "laranja"
        )
    else:
        valor_fontes = "—"
        subtitulo_fontes = "Diagnóstico indisponível"
        tema_fontes = "cinza"

    progresso_fontes: tuple[float, float] | None = None
    if info_base["fontes_total"]:
        progresso_fontes = (float(info_base["fontes_ok"]), float(info_base["fontes_total"]))
    progresso_abas: tuple[float, float] | None = None
    if total_tabelas:
        progresso_abas = (float(info_base["tabelas_com_dados"]), float(total_tabelas))

    specs: list[SpecKPIAvancado] = [
        {
            "label": "STATUS DA SINCRONIZAÇÃO",
            "valor": status_carga,
            "sub": detalhe_status,
            "tema": tema_status,
            "icone": "sync",
            "ajuda": "Resultado consolidado da última tentativa de sincronização das fontes.",
        },
        {
            "label": "REGISTROS DE PRODUÇÃO",
            "valor": registros,
            "sub": f"Última tentativa: {info_base['ultima_tentativa_curta']}",
            "tema": "azul",
            "icone": "storage",
            "ajuda": "Soma das linhas de todas as abas de produção carregadas na sessão.",
        },
        {
            "label": "ABAS DE PRODUÇÃO",
            "valor": formatar_numero_br(total_tabelas) if total_tabelas else "—",
            "sub": (
                f"{info_base['tabelas_com_dados']} com registros"
                if total_tabelas
                else "Nenhuma aba carregada"
            ),
            "tema": "gradiente",
            "icone": "table_view",
            "progresso": progresso_abas,
            "meta_rotulo": "abas com dados" if progresso_abas else "",
        },
        {
            "label": "FONTES ATUALIZADAS",
            "valor": valor_fontes,
            "sub": subtitulo_fontes,
            "tema": tema_fontes,
            "icone": "cloud_sync",
            "progresso": progresso_fontes,
            "meta_rotulo": "fontes sincronizadas" if progresso_fontes else "",
        },
    ]
    render_kpi_row(specs, colunas=4)
    render_spacer(14)


SECOES_PAGINA: tuple[tuple[str, str, str], ...] = (
    ("Visão geral do sistema", "insights", "Volume carregado e resultado da última sincronização"),
    ("Saúde das fontes de dados", "database", "Resultado por fonte e cargas preservadas"),
    ("Módulos de gestão e operação", "hub", "Frentes táticas e estratégicas da TOTALE"),
    ("Atalhos rápidos", "bolt", "Ferramentas e relatórios de rotina"),
)


def render_toolbar_atualizacao(info_base: dict[str, Any]) -> None:
    """Barra de atualização fixa (sticky) com última sincronização e refresh."""
    with barra_filtros("home", titulo="Atualização dos dados", icone="schedule", colunas=2) as cols:
        cols[0].caption(
            "🕒 Última sincronização: "
            f"**{info_base['ultima_atualizacao']}** · "
            "os dados são compartilhados por todos os painéis do portal."
        )
        render_toggle_autorefresh(chave="home", padrao_min=5)


def render_sumario_pagina() -> None:
    """Sumário navegável com a hierarquia de leitura da página (âncoras)."""
    render_sumario([titulo for titulo, _, _ in SECOES_PAGINA], titulo="Nesta página")


def render_fontes_dados(info_base: dict[str, Any]) -> None:
    """Mostra o sucesso, a falha ou a idade do último dado de cada fonte.

    Mantém ``st.success`` / ``st.warning`` / ``st.error`` nativos de propósito:
    são os únicos marcadores semânticos de estado da página (ver
    ``tests/test_home_dashboard.py``) e ganham o acabamento do CSS global v3.6.
    """
    fontes = info_base["fontes"]
    if not fontes:
        st.info("O monitoramento das fontes ainda não está disponível nesta sessão.")
        render_spacer(8)
        return

    colunas = st.columns(min(3, len(fontes)), gap="small")
    for indice, fonte in enumerate(fontes):
        with colunas[indice % len(colunas)]:
            with st.container(border=True):
                st.markdown(f"**{fonte['nome']}**")
                if fonte["ok"]:
                    st.success(f"Atualizada • {formatar_numero_br(fonte['linhas'])} linhas")
                    st.caption(f"Último sucesso: {fonte['ultimo_sucesso']}")
                elif fonte["tem_sucesso_anterior"]:
                    st.warning("Atualização falhou; os dados da carga anterior foram preservados.")
                    st.caption(
                        f"Carga preservada: {formatar_numero_br(fonte['linhas'])} linhas • "
                        f"último sucesso em {fonte['ultimo_sucesso']}"
                    )
                else:
                    st.error("Sem carga bem-sucedida para esta fonte.")
                if fonte["ultima_tentativa"] != "Não disponível":
                    st.caption(f"Última tentativa: {fonte['ultima_tentativa']}")
                if fonte["erro"]:
                    st.caption(f"Motivo: {fonte['erro']}")

    render_spacer(8)


def render_status_operacional(info_base: dict[str, Any]) -> None:
    """Resume o estado da carga sem afirmar disponibilidade não verificada."""
    status = info_base["status_carga"]
    if status == "Aguardando dados":
        col_msg, col_btn = st.columns([3, 1], gap="medium")
        with col_msg:
            render_insight(
                msg="Nenhuma aba de produção está carregada nesta sessão. Sincronize as fontes para disponibilizar os dados nos painéis.",
                tipo="alerta",
                titulo="Dados de produção pendentes",
            )
        with col_btn:
            render_spacer(10)
            try:
                st.page_link(
                    "pages/envio_excel.py",
                    label="🔁 Sincronizar bases",
                    icon="📥",
                    width="stretch",
                )
            except Exception:
                if st.button("🔁 Ir para Atualização", width="stretch"):
                    st.info("Navegue até 'Atualização de Dados' no menu lateral.")
    elif status == "Com falhas":
        render_insight(
            msg="Todas as fontes monitoradas falharam na última tentativa. Confira os detalhes abaixo; cargas anteriores, quando disponíveis, podem estar desatualizadas.",
            tipo="alerta",
            titulo="Falha na sincronização",
        )
    elif status == "Parcial":
        falhas = ", ".join(info_base["fontes_com_falha"])
        render_insight(
            msg=f"A sincronização foi parcial. Falha nas fontes: **{falhas}**. Consulte os detalhes por fonte acima; cargas anteriores são mantidas quando disponíveis.",
            tipo="alerta",
            titulo="Verifique as fontes com falha",
        )
    elif status == "Atualizada":
        render_insight(
            msg=f"Todas as fontes monitoradas reportaram sucesso. A planilha de produção contém **{formatar_numero_br(info_base['total_linhas'])} registros** em **{info_base['tabelas']} abas**.",
            tipo="ok",
            titulo="Sincronização concluída",
        )
    elif status == "Sem registros":
        render_insight(
            msg="A estrutura das abas de produção foi carregada, mas nenhuma linha de dados foi encontrada.",
            tipo="alerta",
            titulo="Produção sem registros",
        )
    else:
        render_insight(
            msg=f"Há **{formatar_numero_br(info_base['total_linhas'])} registros** de produção disponíveis na sessão. O estado de atualização das fontes não está disponível.",
            tipo="info",
            titulo="Dados disponíveis",
        )

    render_spacer(12)


def render_modulos_principais() -> None:
    """Exibe os módulos corporativos organizados em cartões estratégicos de alto padrão."""
    c1, c2, c3 = st.columns(3, gap="medium")

    # Módulo 1: Produção de Campo
    with c1:
        st.markdown(
            """
            <div class="totale-home-card totale-home-card--accent">
                <div>
                    <div class="totale-home-card-header">
                        <div class="totale-home-icon-box totale-home-icon-box--orange">⚡</div>
                        <h4 class="totale-home-card-title">Produção Operacional</h4>
                    </div>
                    <p class="totale-home-card-desc">
                        Acompanhe o ritmo de atendimento das ordens de serviço, rotas diárias e eficiência técnica em campo.
                    </p>
                    <ul class="totale-home-features-list">
                        <li>Volume de O.S. Executadas</li>
                        <li>Rota Inicial & Rota Geral</li>
                        <li>Desempenho de 1º Atendimento</li>
                        <li>Análise de Retornos & Recorrência</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            st.page_link(
                "pages/qtde_os.py",
                label="Abrir Painel de O.S.",
                icon="⚡",
                width="stretch",
            )
        except Exception:
            logger.debug(
                "page_link indisponível para pages/qtde_os.py; cartão segue sem atalho.",
                exc_info=True,
            )

    # Módulo 2: Indicadores & Metas
    with c2:
        st.markdown(
            """
            <div class="totale-home-card">
                <div>
                    <div class="totale-home-card-header">
                        <div class="totale-home-icon-box">🎯</div>
                        <h4 class="totale-home-card-title">Metas & Indicadores</h4>
                    </div>
                    <p class="totale-home-card-desc">
                        Monitore o atingimento das metas contratuais, evolução mensal de pontuação e indicadores de qualidade.
                    </p>
                    <ul class="totale-home-features-list">
                        <li>Metas Operacionais por Equipe</li>
                        <li>Produção Mensal & Pontuação</li>
                        <li>Indicadores de Eficiência Técnica</li>
                        <li>Quebras por Segmento & Geral</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            st.page_link(
                "pages/dashboard_meta.py",
                label="Abrir Metas Operacionais",
                icon="🎯",
                width="stretch",
            )
        except Exception:
            logger.debug(
                "page_link indisponível para pages/dashboard_meta.py; cartão segue sem atalho.",
                exc_info=True,
            )

    # Módulo 3: Ativos & Governança
    with c3:
        st.markdown(
            """
            <div class="totale-home-card totale-home-card--success">
                <div>
                    <div class="totale-home-card-header">
                        <div class="totale-home-icon-box">👷</div>
                        <h4 class="totale-home-card-title">Gestão de Ativos</h4>
                    </div>
                    <p class="totale-home-card-desc">
                        Controle centralizado de equipamentos, frotas, ferramentas operacionais e conformidade de ativos.
                    </p>
                    <ul class="totale-home-features-list">
                        <li>Inventário de Ativos em Campo</li>
                        <li>Alocação por Técnico & Polo</li>
                        <li>Gestão de Substituições & Devoluções</li>
                        <li>Auditoria de Conformidade</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            st.page_link(
                "pages/gestao_ativos.py",
                label="Abrir Gestão de Ativos",
                icon="👷",
                width="stretch",
            )
        except Exception:
            logger.debug(
                "page_link indisponível para pages/gestao_ativos.py; cartão segue sem atalho.",
                exc_info=True,
            )

    render_spacer(14)


def render_atalhos_rapidos() -> None:
    """Renderiza atalhos rápidos com visual de alta produtividade."""
    c1, c2, c3, c4 = st.columns(4, gap="small")

    with c1:
        try:
            st.page_link(
                "pages/envio_excel.py",
                label="🔁 Atualizar Bases",
                help="Sincronizar novos relatórios Excel",
            )
        except Exception:
            st.markdown(
                "<div class='totale-quick-link-btn'>🔁 Atualizar Bases</div>",
                unsafe_allow_html=True,
            )

    with c2:
        try:
            st.page_link(
                "pages/rota_geral.py",
                label="🗺️ Rota Geral Diária",
                help="Visualizar roteirização em campo",
            )
        except Exception:
            st.markdown(
                "<div class='totale-quick-link-btn'>🗺️ Rota Geral</div>",
                unsafe_allow_html=True,
            )

    with c3:
        try:
            st.page_link(
                "pages/volumetria.py",
                label="📊 Volumetria & Demanda",
                help="Análise quantitativa de carga diária",
            )
        except Exception:
            st.markdown(
                "<div class='totale-quick-link-btn'>📊 Volumetria</div>",
                unsafe_allow_html=True,
            )

    with c4:
        try:
            st.page_link(
                "pages/consultivo.py",
                label="📋 Relatórios Consultivos",
                help="Extrações e visões detalhadas",
            )
        except Exception:
            st.markdown(
                "<div class='totale-quick-link-btn'>📋 Consultivos</div>",
                unsafe_allow_html=True,
            )

    render_spacer(8)


def render_footer() -> None:
    """Rodapé corporativo padronizado do portal (``components.layout_pagina``)."""
    versao = st.session_state.get("versao_sistema", VERSAO_SISTEMA)
    ambiente = st.session_state.get("ambiente_sistema", AMBIENTE_SISTEMA)
    render_rodape_pagina(versao=str(versao), ambiente=str(ambiente), horario=_agora())


# ====================================================
# 🚀 BLOCO 5: FUNÇÃO PRINCIPAL DA PÁGINA
# ====================================================
def main() -> None:
    """Ponto de entrada da página Home.

    A ordem dos blocos segue ``components.layout_pagina.ORDEM_PADRAO``:
    contexto → sumário → filtros → KPIs → detalhamento → rodapé.
    Cada bloco vive em ``secao()`` (âncora navegável).
    """
    aplicar_estilo()
    _injetar_css_home()
    render_page_sidebar_theme_selector()

    with temporizar("home.metricas_base"):
        info_base = _obter_metricas_base()

    # 1) Cabeçalho e contexto -------------------------------------------------
    render_header(info_base)
    render_boas_vindas()

    # 2) Sumário (âncoras) ----------------------------------------------------
    render_sumario_pagina()

    # 3) Filtros / atualização fixa -------------------------------------------
    render_toolbar_atualizacao(info_base)
    render_spacer(6)

    # 4) KPIs do sistema ------------------------------------------------------
    with secao(
        "Visão geral do sistema",
        icone="insights",
        subtitulo="Volume da produção carregada e resultado da última sincronização",
        badge=info_base["status_carga"],
    ):
        render_kpi_strip(info_base)

    # 5) Detalhamento ---------------------------------------------------------
    with secao(
        "Saúde das fontes de dados",
        icone="database",
        subtitulo=(
            "Resultado por fonte na última tentativa; falhas preservam a carga "
            "anterior quando disponível"
        ),
    ):
        render_fontes_dados(info_base)
        render_status_operacional(info_base)

    with secao(
        "Módulos de gestão e operação",
        icone="hub",
        subtitulo="Acesse diretamente as frentes táticas e estratégicas da TOTALE",
    ):
        render_modulos_principais()

    with secao(
        "Atalhos rápidos",
        icone="bolt",
        subtitulo="Ferramentas e relatórios de rotina diária, a um clique",
        badge="AGILIDADE",
    ):
        render_atalhos_rapidos()

    # 6) Rodapé ---------------------------------------------------------------
    render_footer()


if __name__ == "__main__":
    main()
