# =====================================
# 📄 ARQUIVO: pages/home.py
# 📌 PÁGINA: Home - Portal TOTALE
# 🔖 Versão: 3.2.0
# =====================================

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from components.componentes import (
    render_hero_totale_1,
    render_insight,
    render_section_header,
    render_spacer,
)

# =====================================
# 🔧 BLOCO 1: CONFIGURAÇÕES LOCAIS
# =====================================

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
VERSAO_PADRAO = "3.2.0"
AMBIENTE_PADRAO = "Produção"


# =====================================
# 🎨 BLOCO 2: CSS (complementar, sem conflito)
# =====================================


def injetar_css() -> None:
    """CSS específico da Home — classes com prefixo home- para evitar colisão."""
    st.markdown(
        """
        <style>
        .home-card {
            background: #FFFFFF;
            padding: 24px;
            border-radius: 12px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 4px 12px rgba(1, 40, 105, 0.06);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
            box-sizing: border-box;
        }
        .home-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(1, 40, 105, 0.10);
        }
        .home-card h4 {
            margin: 0 0 8px 0;
            color: #012869;
            font-size: 16px;
            font-weight: 800;
        }
        .home-card p {
            margin: 0;
            color: #64748B;
            font-size: 13px;
            line-height: 1.55;
        }

        .home-status-ok {
            background: #F0FDF4 !important;
            border-left: 5px solid #059669 !important;
        }
        .home-status-warn {
            background: #FFF7ED !important;
            border-left: 5px solid #F37C04 !important;
        }

        .home-footer {
            margin-top: 36px;
            padding: 14px 20px;
            background: #012869;
            color: #FFFFFF;
            font-size: 13px;
            font-weight: 500;
            text-align: center;
            border-radius: 10px;
            box-shadow: 0 4px 14px rgba(1, 40, 105, 0.18);
        }
        .home-footer b { color: #FFFFFF; }
        .home-footer .sep {
            margin: 0 8px;
            opacity: 0.55;
        }

        /* Garante espaço inferior sem footer fixed */
        .main .block-container {
            padding-bottom: 2.5rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =====================================
# 🔧 BLOCO 3: HELPERS
# =====================================


def _agora() -> datetime:
    return datetime.now(FUSO_HORARIO)


def _formatar_ultima_atualizacao(valor: object) -> str:
    """Aceita datetime, str ou None sem quebrar a página."""
    if valor is None:
        return "Não disponível"
    if isinstance(valor, datetime):
        dt = valor
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=FUSO_HORARIO)
        return dt.strftime("%d/%m/%Y às %H:%M:%S")
    # string ou outro tipo serializado no session_state
    texto = str(valor).strip()
    return texto if texto and texto.lower() != "none" else "Não disponível"


def _dados_carregados() -> bool:
    return st.session_state.get("dados_prod") is not None


# =====================================
# 🧩 BLOCO 4: COMPONENTES
# =====================================


def render_header() -> None:
    render_hero_totale_1(
        titulo="Portal TOTALE",
        subtitulo="Painéis de Produção, Indicadores e Gestão Estratégica",
        badge="HOME",
        icone="📊",
    )


def render_intro() -> None:
    st.markdown(
        """
        <div class="home-card">
            <p style="color:#334155;font-size:14px;line-height:1.65;margin:0;">
                <b style="color:#012869;">Bem-vindo ao ambiente centralizado de dados da TOTALE.</b><br><br>
                Este portal fornece uma visão clara e estratégica dos processos produtivos e
                indicadores de performance, apoiando decisões com base em dados confiáveis.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_spacer(14)


def render_status_sistema() -> None:
    if not _dados_carregados():
        st.markdown(
            """
            <div class="home-card home-status-warn">
                <b style="color:#C2410C;">⚠️ Sistema aguardando atualização de dados</b>
                <p style="margin:10px 0 0 0;color:#9A3412;font-size:13px;line-height:1.7;">
                    1️⃣ Acesse <b>🔁 Atualização de Dados</b> no menu lateral<br>
                    2️⃣ Clique em <b>Sincronizar Agora</b> / <b>Atualizar Agora</b><br>
                    3️⃣ Aguarde a conclusão da sincronização
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_insight(
            msg="Sem dados em memória. Os painéis operacionais ficam limitados até a sincronização.",
            tipo="alerta",
            titulo="Ação necessária",
        )
    else:
        hora_str = _formatar_ultima_atualizacao(
            st.session_state.get("ultima_atualizacao")
        )
        st.markdown(
            f"""
            <div class="home-card home-status-ok">
                <b style="color:#15803D;">✅ Sistema atualizado e pronto para uso</b>
                <p style="margin:8px 0 0 0;color:#166534;font-size:13px;">
                    Última sincronização: <b>{hora_str}</b>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_insight(
            msg="Bases operacionais carregadas na sessão. Navegue pelos módulos no menu lateral.",
            tipo="ok",
            titulo="Ambiente operacional",
        )
    render_spacer(8)


def render_cards_navegacao() -> None:
    render_section_header(
        titulo="Módulos em destaque",
        icone="🧭",
        subtitulo="Atalhos conceituais para a jornada operacional",
    )

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            """
            <div class="home-card">
                <h4>⚙️ Produção Operacional</h4>
                <p>
                    Monitore eficiência operacional, volume produzido e desempenho
                    por setor, equipe e técnico em tempo quase real.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="home-card">
                <h4>📈 Indicadores Estratégicos</h4>
                <p>
                    Acompanhe metas, resultados consolidados e os principais KPIs
                    do negócio com visão executiva e tática.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_spacer(10)


def render_atalhos_rapidos() -> None:
    """Atalhos opcionais — só renderiza se st.page_link estiver disponível."""
    render_section_header(
        titulo="Acesso rápido",
        icone="⚡",
        badge="Navegação",
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        try:
            st.page_link("pages/envio_excel.py", label="Atualizar Dados", icon="🔁")
        except Exception:
            st.caption("🔁 Atualização de Dados")

    with c2:
        try:
            st.page_link("pages/pontos.py", label="Produção Mensal", icon="📈")
        except Exception:
            st.caption("📈 Produção Mensal")

    with c3:
        try:
            st.page_link("pages/dashboard_meta.py", label="Metas", icon="🎯")
        except Exception:
            st.caption("🎯 Metas Operacionais")

    with c4:
        try:
            st.page_link("pages/gestao_ativos.py", label="Ativos", icon="👷")
        except Exception:
            st.caption("👷 Gestão de Ativos")

    render_spacer(8)


def render_footer() -> None:
    versao = st.session_state.get("versao_sistema", VERSAO_PADRAO)
    ambiente = st.session_state.get("ambiente_sistema", AMBIENTE_PADRAO)
    agora = _agora()

    st.markdown(
        f"""
        <div class="home-footer">
            🏢 <b>Painel TOTALE</b>
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


# =====================================
# 🚀 BLOCO 5: MAIN
# =====================================


def main() -> None:
    injetar_css()
    render_header()
    render_intro()
    render_status_sistema()
    render_cards_navegacao()
    render_atalhos_rapidos()
    render_footer()
    # Auto-refresh removido de propósito:
    # use botão manual ou st.fragment se precisar atualizar trechos.


if __name__ == "__main__":
    main()
