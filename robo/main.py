"""
robo/main.py
============
Interface Standalone do Robô de Monitoramento TOTALE.

Permite testar o robô independentemente das páginas principais,
com interface simplificada para validação de detecção e carregamento.

Uso:
    streamlit run robo/main.py

    Ou via CLI:
    python -m robo.main
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

# Adiciona o path raiz para imports
_DIR = Path(__file__).resolve().parent
_ROOT = _DIR.parent
for _p in (_DIR, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Imports do robô
from robo_local import (
    _obter_metadados_arquivo,
    _obter_pasta_robo_padrao,
    buscar_csv_mais_recente,
    ler_csv_totale,
    renderizar_robo_local,
)

# Imports de componentes (opcionais)
try:
    from components.componentes import (
        aplicar_estilo,
        render_sidebar_brand,
        render_section_header,
        render_insight,
    )

    COMPONENTES_DISPONIVEIS = True
except ImportError:
    COMPONENTES_DISPONIVEIS = False


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Robô TOTALE - Teste",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ═══════════════════════════════════════════════════════════════════════
# ESTILOS
# ═══════════════════════════════════════════════════════════════════════
if COMPONENTES_DISPONIVEIS:
    aplicar_estilo()

st.markdown(
    """
    <style>
    .teste-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border: 1px solid #E2E8F0;
        margin-bottom: 16px;
    }
    .teste-card-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 2px solid #F1F5F9;
    }
    .teste-card-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        background: linear-gradient(135deg, #012869 0%, #1E40AF 100%);
        color: white;
    }
    .teste-card-title {
        font-size: 18px;
        font-weight: 700;
        color: #0F172A;
    }
    .teste-card-sub {
        font-size: 13px;
        color: #64748B;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .status-ok { background: #D1FAE5; color: #065F46; }
    .status-warn { background: #FEF3C7; color: #92400E; }
    .status-error { background: #FEE2E2; color: #991B1B; }
    .file-info {
        background: #F8FAFC;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 13px;
    }
    .file-info-row {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        border-bottom: 1px solid #E2E8F0;
    }
    .file-info-row:last-child {
        border-bottom: none;
    }
    .file-info-label {
        color: #64748B;
        font-weight: 500;
    }
    .file-info-value {
        color: #0F172A;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ═══════════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════
def render_teste_card(
    titulo: str,
    subtitulo: str,
    icone: str,
    conteudo: str,
    status: str = "ok",
) -> None:
    """Renderiza um card de teste padronizado."""
    status_class = {
        "ok": "status-ok",
        "warn": "status-warn",
        "error": "status-error",
    }.get(status, "status-ok")

    status_label = {
        "ok": "✅ OK",
        "warn": "⚠️ Atenção",
        "error": "❌ Erro",
    }.get(status, "✅ OK")

    st.markdown(
        f"""
        <div class="teste-card">
            <div class="teste-card-header">
                <div class="teste-card-icon">{icone}</div>
                <div>
                    <div class="teste-card-title">{titulo}</div>
                    <div class="teste-card-sub">{subtitulo}</div>
                </div>
                <span class="status-badge {status_class}" style="margin-left: auto;">{status_label}</span>
            </div>
            {conteudo}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_file_info(meta: Dict[str, str]) -> str:
    """Renderiza informações do arquivo em formato HTML."""
    rows = []
    for label, value in meta.items():
        if label != "caminho_completo":
            rows.append(
                f'<div class="file-info-row">'
                f'<span class="file-info-label">{label}</span>'
                f'<span class="file-info-value">{value}</span>'
                f"</div>"
            )
    return f'<div class="file-info">{"".join(rows)}</div>'


def testar_pasta(pasta: str) -> Tuple[bool, str, List[str]]:
    """
    Testa se a pasta existe e lista arquivos CSV.

    Returns:
        Tuple[bool, str, List[str]]: (sucesso, mensagem, lista_de_arquivos)
    """
    if not os.path.exists(pasta):
        return False, f"Pasta não existe: {pasta}", []

    if not os.path.isdir(pasta):
        return False, f"Não é uma pasta: {pasta}", []

    arquivos = [
        f for f in os.listdir(pasta) if f.endswith(".csv") and not f.endswith(".tmp")
    ]

    if not arquivos:
        return True, f"Pasta vazia (sem CSV): {pasta}", []

    return True, f"{len(arquivos)} arquivo(s) CSV encontrado(s)", arquivos


def testar_leitura_csv(caminho: str) -> Tuple[bool, str, Optional[pd.DataFrame]]:
    """
    Testa a leitura de um arquivo CSV.

    Returns:
        Tuple[bool, str, Optional[pd.DataFrame]]: (sucesso, mensagem, dataframe)
    """
    if not os.path.exists(caminho):
        return False, "Arquivo não encontrado", None

    df = ler_csv_totale(caminho)

    if df is None:
        return False, "Falha ao ler arquivo", None

    if df.empty:
        return False, "Arquivo vazio", df

    return True, f"{len(df)} linhas × {len(df.columns)} colunas", df


# ═══════════════════════════════════════════════════════════════════════
# INTERFACE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
def main():
    # ── CABEÇALHO ─────────────────────────────────────────────────────
    if COMPONENTES_DISPONIVEIS:
        render_sidebar_brand(
            titulo="TOTALE",
            subtitulo="Robô de Monitoramento",
            logo="smart_toy",
            ambiente="teste",
            versao="v1.0",
            mostrar_data=True,
        )
    else:
        st.sidebar.title("🤖 Robô TOTALE")
        st.sidebar.caption("Interface de Teste")
        st.sidebar.markdown("---")
        st.sidebar.caption(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
        padding: 32px 40px; border-radius: 14px; color: white;
        box-shadow: 0 10px 40px rgba(1,40,105,0.25); margin-bottom: 24px;">
            <h1 style="margin: 0; font-size: 32px; font-weight: 800;"> Teste do Robô de Monitoramento</h1>
            <p style="margin: 8px 0 0 0; font-size: 15px; opacity: 0.95;">
                Interface standalone para validação de detecção e carregamento de arquivos
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── ABA DE NAVEGAÇÃO ───────────────────────────────────────────────
    aba = st.tabs(
        [
            " Detecção de Arquivos",
            "📊 Teste de Leitura",
            "⚙️ Configurações",
            "📋 Logs",
        ]
    )

    # ══════════════════════════════════════════════════════════════════
    # ABA 1: DETECÇÃO DE ARQUIVOS
    # ═══════════════════════════════════════════════════════════════════
    with aba[0]:
        st.header(" Detecção de Arquivos na Pasta 'robo'")

        # Pasta atual
        pasta_atual = _obter_pasta_robo_padrao()

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**Pasta Monitorada:** `{pasta_atual}`")
        with col2:
            if st.button("🔄 Atualizar", use_container_width=True):
                st.rerun()

        # Teste da pasta
        sucesso, msg, arquivos = testar_pasta(pasta_atual)

        if sucesso:
            render_teste_card(
                titulo="Status da Pasta",
                subtitulo=pasta_atual,
                icone="📁",
                conteudo=f"<p>{msg}</p>",
                status="ok" if arquivos else "warn",
            )
        else:
            render_teste_card(
                titulo="Erro na Pasta",
                subtitulo=pasta_atual,
                icone="❌",
                conteudo=f"<p style='color: #DC2626;'>{msg}</p>",
                status="error",
            )

        # Lista de arquivos
        if arquivos:
            st.subheader(f"📄 Arquivos CSV Encontrados ({len(arquivos)})")

            for arq in sorted(arquivos, reverse=True):
                caminho_completo = os.path.join(pasta_atual, arq)
                meta = _obter_metadados_arquivo(caminho_completo)

                with st.expander(f"📄 {arq}", expanded=False):
                    st.markdown(render_file_info(meta), unsafe_allow_html=True)

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button(f" Testar Leitura", key=f"test_{arq}"):
                            with st.spinner("Lendo arquivo..."):
                                ok, msg_df, df = testar_leitura_csv(caminho_completo)
                                if ok:
                                    st.success(f"✅ {msg_df}")
                                    st.dataframe(df.head(10), use_container_width=True)
                                else:
                                    st.error(f"❌ {msg_df}")
                    with col_b:
                        st.caption(f"Modificado: {meta['modificado']}")
        else:
            st.info("""
                **Nenhum arquivo CSV encontrado na pasta `robo/`**
                
                Para testar o robô:
                1. Crie a pasta `robo/` na raiz do projeto
                2. Coloque um arquivo CSV (ex: `Atividades-2024.csv`)
                3. Clique em **🔄 Atualizar**
                """)

            # Criar arquivo de teste
            if st.button(" Criar Arquivo de Teste"):
                try:
                    caminho_teste = os.path.join(pasta_atual, "Atividades-teste.csv")
                    df_teste = pd.DataFrame(
                        {
                            "CONTRATO": ["12345", "12346", "12347"],
                            "STATUS DA O.S 1": [
                                "EXECUTADA",
                                "NAO EXECUTADA",
                                "PENDENTE",
                            ],
                            "TÉCNICO": ["João Silva", "Maria Santos", "Pedro Oliveira"],
                            "TOTAL DE TAREFAS": [1, 1, 1],
                        }
                    )
                    df_teste.to_csv(caminho_teste, index=False, encoding="utf-8-sig")
                    st.success(f"✅ Arquivo criado: `{caminho_teste}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao criar arquivo: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # ABA 2: TESTE DE LEITURA
    # ═══════════════════════════════════════════════════════════════════
    with aba[1]:
        st.header("📊 Teste de Leitura e Processamento")

        pasta_atual = _obter_pasta_robo_padrao()
        arquivo_rec, mtime = buscar_csv_mais_recente(pasta_atual)

        if arquivo_rec:
            meta = _obter_metadados_arquivo(arquivo_rec)

            render_teste_card(
                titulo="Arquivo Mais Recente",
                subtitulo=meta["nome"],
                icone="",
                conteudo=render_file_info(meta),
                status="ok",
            )

            # Teste de leitura
            st.subheader(" Testar Leitura do Arquivo")

            if st.button("🚀 Executar Teste de Leitura", type="primary"):
                with st.spinner("Processando arquivo..."):
                    ok, msg, df = testar_leitura_csv(arquivo_rec)

                    if ok and df is not None:
                        st.success(f"✅ {msg}")

                        # Preview
                        st.markdown("### 📋 Preview (Primeiras 20 linhas)")
                        st.dataframe(df.head(20), use_container_width=True)

                        # Estatísticas
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("📊 Total de Linhas", len(df))
                        with col2:
                            st.metric("📐 Total de Colunas", len(df.columns))
                        with col3:
                            st.metric("💾 Tamanho", meta["tamanho"])

                        # Colunas
                        st.markdown("### 📐 Colunas Detectadas")
                        st.json(list(df.columns))

                        # Tipos de dados
                        st.markdown("### 🔤 Tipos de Dados")
                        tipos = df.dtypes.astype(str).to_dict()
                        st.json(tipos)

                        # Download
                        csv = df.to_csv(index=False, encoding="utf-8-sig").encode(
                            "utf-8-sig"
                        )
                        st.download_button(
                            label="📥 Baixar CSV Processado",
                            data=csv,
                            file_name=f"teste_{meta['nome']}",
                            mime="text/csv",
                        )
                    else:
                        st.error(f"❌ {msg}")
        else:
            st.warning("""
                **Nenhum arquivo detectado**
                
                Coloque um arquivo CSV na pasta `robo/` e clique em **🔄 Atualizar** na aba anterior.
                """)

    # ═══════════════════════════════════════════════════════════════════
    # ABA 3: CONFIGURAÇÕES
    # ═══════════════════════════════════════════════════════════════════
    with aba[2]:
        st.header("⚙️ Configurações do Robô")

        # Pasta atual
        pasta_atual = _obter_pasta_robo_padrao()

        st.markdown("### 📁 Pasta de Monitoramento")
        st.info(f"**Pasta Atual:** `{pasta_atual}`")

        # Permitir alteração temporária
        nova_pasta = st.text_input(
            "Alterar Pasta (apenas para teste)",
            value=pasta_atual,
            help="Esta alteração é temporária e não persiste entre sessões",
        )

        if nova_pasta != pasta_atual:
            if os.path.exists(nova_pasta):
                st.success(f"✅ Pasta válida: {nova_pasta}")
                st.session_state["pasta_teste"] = nova_pasta
            else:
                st.error(f"❌ Pasta não existe: {nova_pasta}")

        st.markdown("---")

        st.markdown("### 📊 Padrões de Arquivo")
        st.code(
            """
            Padrão Principal: Atividades-*.csv
            Padrão Flexível:  *Atividades*.csv
            Excluídos:        *.tmp, *.crdownload
            """,
            language="text",
        )

        st.markdown("---")

        st.markdown("###  Encodings Suportados")
        st.code(
            """
            1. utf-8-sig (prioritário)
            2. cp1252
            3. latin1
            4. iso-8859-1
            5. utf-8
            """,
            language="text",
        )

        st.markdown("---")

        st.markdown("### ⏱️ Intervalo de Verificação")
        st.info("🔄 **10 segundos** (via @st.fragment)")

    # ═══════════════════════════════════════════════════════════════════
    # ABA 4: LOGS
    # ═══════════════════════════════════════════════════════════════════
    with aba[3]:
        st.header("📋 Logs e Diagnóstico")

        # Session State
        st.markdown("### 🔍 Session State")
        if st.session_state:
            st.json(dict(st.session_state))
        else:
            st.info("Session State vazia")

        st.markdown("---")

        # Informações do Sistema
        st.markdown("### 💻 Informações do Sistema")

        info_sistema = {
            "Python": sys.version.split()[0],
            "Streamlit": st.__version__,
            "Pasta Robô": _obter_pasta_robo_padrao(),
            "Pasta Atual": os.getcwd(),
            "Componentes": (
                "✅ Disponível" if COMPONENTES_DISPONIVEIS else "❌ Indisponível"
            ),
        }

        st.json(info_sistema)

        st.markdown("---")

        # Limpar Session State
        st.markdown("### 🧹 Limpeza")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Limpar Session State", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success("Session State limpo!")
                st.rerun()

        with col2:
            if st.button("🔄 Recarregar Página", use_container_width=True):
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# EXECUÇÃO
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
