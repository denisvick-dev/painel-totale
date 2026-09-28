"""
pages/home.py
=============
Home — Portal TOTALE de Inteligência Operacional

Versão: 3.3.0 (Integração Total Design System TOTALE v4.9.0)
Autor: TOTALE Tecnologia

Evoluções desta versão:
• Header Hero dinâmico com métricas em tempo real e identificação contextual de ambiente.
• Faixa executiva de KPIs resumidos (Status, Volume, Módulos e Integridade da Base).
• Card inteligente de status operacional com direcionamento dinâmico para sincronização.
• Grid interativo de módulos estratégicos com atalhos diretos e cartões executivos.
• Acesso rápido categorizado para as páginas mais acessadas do dia a dia.
• Tipagem estrita, tratamento resiliente de exceções e alinhamento cromático à marca TOTALE.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from components.componentes import (
    Cores,
    formatar_numero_br,
    render_badge,
    render_hero_totale_1,
    render_hero_totale_2,
    render_insight,
    render_kpi,
    render_section_header,
    render_spacer,
)

logger = logging.getLogger(__name__)

# ====================================================
# 🔧 BLOCO 1: CONFIGURAÇÕES E CONSTANTES
# ====================================================
FUSO_BR = ZoneInfo("America/Sao_Paulo")
VERSAO_SISTEMA = "3.3.0"
AMBIENTE_SISTEMA = "Produção"


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

        /* Footer da Home */
        .totale-home-footer {{
            margin-top: 36px;
            padding: 16px 24px;
            background: linear-gradient(90deg, {Cores.PRIMARIA_DARK} 0%, {Cores.PRIMARIA} 60%, {Cores.PRIMARIA_LIGHT} 100%);
            color: #FFFFFF;
            font-size: 12.5px;
            font-weight: 600;
            text-align: center;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(1, 40, 105, 0.16);
            border-top: 2px solid {Cores.SECUNDARIA};
        }}
        .totale-home-footer span.sep {{
            color: {Cores.SECUNDARIA_LIGHT};
            margin: 0 10px;
            font-weight: bold;
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


def _formatar_data_hora(valor: Any) -> str:
    """Formata com segurança datetime, string ou timestamp."""
    if valor is None:
        return "Não disponível"
    if isinstance(valor, datetime):
        dt = valor if valor.tzinfo is not None else valor.replace(tzinfo=FUSO_BR)
        return dt.strftime("%d/%m/%Y às %H:%M:%S")
    txt = str(valor).strip()
    return txt if txt and txt.lower() != "none" else "Não disponível"


def _obter_metricas_base() -> dict[str, Any]:
    """Inspeciona o session_state para extrair métricas de volume e integridade."""
    dados_prod = st.session_state.get("dados_prod")
    carregado = False
    total_linhas = 0

    if isinstance(dados_prod, pd.DataFrame):
        carregado = not dados_prod.empty
        total_linhas = len(dados_prod)
    elif isinstance(dados_prod, (list, tuple, dict)):
        carregado = len(dados_prod) > 0
        total_linhas = len(dados_prod)
    elif dados_prod is not None:
        carregado = True

    ultima_atualizacao = st.session_state.get("ultima_atualizacao")
    return {
        "carregado": carregado,
        "total_linhas": total_linhas,
        "ultima_atualizacao": _formatar_data_hora(ultima_atualizacao),
    }


# ====================================================
# 🧩 BLOCO 4: COMPONENTES DA PÁGINA
# ====================================================
def render_header(info_base: dict[str, Any]) -> None:
    """Renderiza o Hero Banner adaptativo da TOTALE."""
    data_hoje = _agora().strftime("%d de %B de %Y")

    if info_base["carregado"] and info_base["total_linhas"] > 0:
        render_hero_totale_2(
            titulo="Portal TOTALE — Inteligência Operacional",
            subtitulo=f"Visão consolidada de produção, eficiência de campo e KPIs estratégicos. {data_hoje}.",
            valor_destaque=formatar_numero_br(info_base["total_linhas"]),
            label_destaque="REGISTROS ATIVOS",
            badge="AMBIENTE OPERACIONAL ATIVO",
            tag_info=f"Sincronizado: {info_base['ultima_atualizacao']}",
        )
    else:
        render_hero_totale_1(
            titulo="Portal TOTALE — Inteligência Operacional",
            subtitulo="Ambiente unificado para monitoramento de rotas, produtividade técnica e gestão de metas.",
            badge="PORTAL EXECUTIVO",
            icone="⚡",
            meta_info=f"Atualizado em tempo real • {data_hoje} • São Paulo/SP",
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
    """Renderiza a faixa executiva de indicadores rápidos."""
    render_section_header(
        titulo="Visão Geral do Sistema",
        subtitulo="Status dos serviços analíticos e integridade das bases de dados",
        icone="insights",
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status_label = "Operacional" if info_base["carregado"] else "Aguardando Carga"
        tema_status = "verde" if info_base["carregado"] else "laranja"
        render_kpi(
            col1,
            label="STATUS DA BASE",
            valor=status_label,
            sub="Serviços 100% online",
            tema=tema_status,
            icone="dns",
        )

    with col2:
        val_vol = (
            formatar_numero_br(info_base["total_linhas"])
            if info_base["total_linhas"] > 0
            else "Pendente"
        )
        render_kpi(
            col2,
            label="REGISTROS EM MEMÓRIA",
            valor=val_vol,
            sub=f"Última carga: {info_base['ultima_atualizacao']}",
            tema="azul",
            icone="storage",
        )

    with col3:
        render_kpi(
            col3,
            label="PAINÉIS DISPONÍVEIS",
            valor="8 Módulos",
            sub="Operação, Ativos e Metas",
            tema="gradiente",
            icone="dashboard_customize",
        )

    with col4:
        render_kpi(
            col4,
            label="AMBIENTE & SEGURANÇA",
            valor=AMBIENTE_SISTEMA,
            sub="Criptografia & Sessão Ativa",
            tema="cinza",
            icone="security",
        )

    render_spacer(14)


def render_status_operacional(info_base: dict[str, Any]) -> None:
    """Exibe o diagnóstico do sistema e CTA para atualização de dados."""
    if not info_base["carregado"]:
        col_msg, col_btn = st.columns([3, 1], gap="medium")
        with col_msg:
            render_insight(
                msg="O ambiente está iniciado, porém **nenhuma base de dados foi carregada na sessão atual**. "
                "Para visualizar os gráficos de volumetria, rotas e KPIs de produção, acesse o módulo de atualização.",
                tipo="alerta",
                titulo="Ação Necessária: Sincronização de Dados Pendente",
            )
        with col_btn:
            render_spacer(10)
            try:
                st.page_link(
                    "pages/envio_excel.py",
                    label="🔁 Sincronizar Bases Agora",
                    icon="📥",
                    use_container_width=True,
                )
            except Exception:
                if st.button("🔁 Ir para Atualização", use_container_width=True):
                    st.info("Navegue até 'Atualização de Dados' no menu lateral.")
    else:
        render_insight(
            msg=f"Bases de produção validadas e ativas na sessão em **{info_base['ultima_atualizacao']}**. "
            "Todos os cálculos analíticos, tabelas de quebra e relatórios diários estão prontos para consulta.",
            tipo="ok",
            titulo="Ambiente Operacional Atualizado e em Conformidade",
        )

    render_spacer(12)


def render_modulos_principais() -> None:
    """Exibe os módulos corporativos organizados em cartões estratégicos de alto padrão."""
    render_section_header(
        titulo="Módulos de Gestão & Operação",
        subtitulo="Acesse diretamente as frentes táticas e estratégicas da TOTALE",
        icone="hub",
    )

    c1, c2, c3 = st.columns(3, gap="medium")

    # Módulo 1: Produção de Campo
    with c1:
        st.markdown(
            f"""
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
                use_container_width=True,
            )
        except Exception:
            pass

    # Módulo 2: Indicadores & Metas
    with c2:
        st.markdown(
            f"""
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
                use_container_width=True,
            )
        except Exception:
            pass

    # Módulo 3: Ativos & Governança
    with c3:
        st.markdown(
            f"""
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
                use_container_width=True,
            )
        except Exception:
            pass

    render_spacer(14)


def render_atalhos_rapidos() -> None:
    """Renderiza atalhos rápidos com visual de alta produtividade."""
    render_section_header(
        titulo="Atalhos Rápidos de Navegação",
        subtitulo="Acesse com um clique as ferramentas e relatórios de rotina diária",
        icone="bolt",
        badge="AGILIDADE",
    )

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
    """Rodapé corporativo alinhado à marca TOTALE."""
    agora = _agora()
    versao = st.session_state.get("versao_sistema", VERSAO_SISTEMA)
    ambiente = st.session_state.get("ambiente_sistema", AMBIENTE_SISTEMA)

    st.markdown(
        f"""
        <div class="totale-home-footer">
            🏢 <b>Portal TOTALE Analytics</b>
            <span class="sep">|</span>
            🌐 {ambiente}
            <span class="sep">|</span>
            🕒 {agora.strftime("%d/%m/%Y")} • {agora.strftime("%H:%M")} BRT
            <span class="sep">|</span>
            🔖 v{versao}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# 🚀 BLOCO 5: FUNÇÃO PRINCIPAL DA PÁGINA
# ====================================================
def main() -> None:
    """Ponto de entrada da página Home."""
    _injetar_css_home()

    info_base = _obter_metricas_base()

    render_header(info_base)
    render_boas_vindas()
    render_kpi_strip(info_base)
    render_status_operacional(info_base)
    render_modulos_principais()
    render_atalhos_rapidos()
    render_footer()


if __name__ == "__main__":
    main()
