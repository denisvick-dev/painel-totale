"""
robo_local.py
=============
Robô monitor de pasta local/downloads para arquivos CSV do TOTALE.
Detecta automaticamente o arquivo mais recente do padrão 'Atividades-*.csv',
evidencia os metadados do arquivo em disco e aciona o pipeline de ETL.
"""

from __future__ import annotations

import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

# Importação defensiva dos componentes do Design System
try:
    from components.componentes import render_sidebar_status
except ImportError:
    from components.componentes import render_sidebar_status  # Fallback


def _obter_pasta_downloads_padrao() -> str:
    """Retorna o caminho padrão da pasta Downloads do usuário."""
    return str(Path.home() / "Downloads")


def _obter_metadados_arquivo(caminho: str) -> Dict[str, str]:
    """Extrai e formata metadados do arquivo físico em disco."""
    try:
        stat = os.stat(caminho)
        tam_bytes = stat.st_size

        if tam_bytes < 1024 * 1024:
            tam_str = f"{tam_bytes / 1024:.1f} KB"
        else:
            tam_str = f"{tam_bytes / (1024 * 1024):.2f} MB"

        dt_mod = datetime.fromtimestamp(stat.st_mtime)
        dt_mod_str = dt_mod.strftime("%d/%m/%Y %H:%M:%S")

        return {
            "nome": os.path.basename(caminho),
            "tamanho": tam_str,
            "modificado": dt_mod_str,
            "caminho_completo": caminho,
        }
    except Exception:
        return {
            "nome": os.path.basename(caminho),
            "tamanho": "—",
            "modificado": "—",
            "caminho_completo": caminho,
        }


def buscar_csv_mais_recente(
    pasta: str, padrao: str = "Atividades-*.csv"
) -> Tuple[Optional[str], Optional[float]]:
    """Busca o arquivo mais recente que atenda ao padrão na pasta."""
    if not os.path.exists(pasta):
        return None, None

    caminho_busca = os.path.join(pasta, padrao)
    arquivos = [
        f
        for f in glob.glob(caminho_busca)
        if not f.endswith(".tmp") and not f.endswith(".crdownload")
    ]

    if not arquivos:
        caminho_busca_flex = os.path.join(pasta, "*Atividades*.csv")
        arquivos = [
            f
            for f in glob.glob(caminho_busca_flex)
            if not f.endswith(".tmp") and not f.endswith(".crdownload")
        ]

    if not arquivos:
        return None, None

    try:
        arquivo_mais_recente = max(arquivos, key=os.path.getmtime)
        mtime = os.path.getmtime(arquivo_mais_recente)
        return arquivo_mais_recente, mtime
    except Exception:
        return None, None


def ler_csv_totale(caminho_arquivo: str) -> Optional[pd.DataFrame]:
    """Lê o arquivo CSV tratando delimitadores e encodings corporativos."""
    encodings = ["utf-8-sig", "latin1", "iso-8859-1", "cp1252", "utf-8"]

    for enc in encodings:
        for sep in [";", ","]:
            try:
                df = pd.read_csv(
                    caminho_arquivo, sep=sep, encoding=enc, dtype=str, low_memory=False
                )
                if df.shape[1] > 3:  # Garante que não leu uma única coluna fundida
                    return df
            except Exception:
                continue

    return None


@st.fragment(run_every="10s")
def _executar_verificacao_robo(
    pasta_monitorada: str,
    etl_fn: Optional[Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]] = None,
    gsheets_fn: Optional[Callable[[], pd.DataFrame]] = None,
):
    """Verifica periodicamente se há um CSV mais novo e executa o ETL."""
    if not st.session_state.get("robo_ativo", False):
        return

    arquivo_rec, mtime = buscar_csv_mais_recente(pasta_monitorada)

    if not arquivo_rec or not mtime:
        return

    ultimo_arquivo = st.session_state.get("robo_ultimo_arquivo")
    ultimo_mtime = st.session_state.get("robo_ultimo_mtime")

    # Detecta se é um novo arquivo ou se o arquivo atual foi modificado
    if arquivo_rec != ultimo_arquivo or mtime != ultimo_mtime:
        df_novo = ler_csv_totale(arquivo_rec)

        if df_novo is not None and not df_novo.empty:
            # Executa o pipeline de saneamento se fornecido
            if etl_fn is not None:
                df_gs = gsheets_fn() if gsheets_fn is not None else pd.DataFrame()
                df_final = etl_fn(df_novo, df_gs)
            else:
                df_final = df_novo

            # Atualiza a memória de sessão global com os metadados do arquivo
            st.session_state["df_memoria"] = df_final
            st.session_state["robo_ultimo_arquivo"] = arquivo_rec
            st.session_state["robo_ultimo_mtime"] = mtime
            st.session_state["robo_hora_sucesso"] = datetime.now()
            st.session_state["origem_dados"] = (
                f"Robô Local ({os.path.basename(arquivo_rec)})"
            )

            st.rerun()


def renderizar_robo_local(
    etl_fn: Optional[Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]] = None,
    gsheets_fn: Optional[Callable[[], pd.DataFrame]] = None,
    pasta_padrao: Optional[str] = None,
) -> None:
    """Renderiza a interface do robô na sidebar evidenciando o arquivo encontrado."""
    if "robo_ativo" not in st.session_state:
        st.session_state["robo_ativo"] = False

    pasta_alvo = pasta_padrao or st.session_state.get(
        "robo_pasta_alvo", _obter_pasta_downloads_padrao()
    )

    st.sidebar.markdown(
        "<div style='font-size:12px; font-weight:700; color:#64748B; "
        "text-transform:uppercase; letter-spacing:0.8px; margin: 14px 0 6px;'>🤖 Robô de Sincronismo</div>",
        unsafe_allow_html=True,
    )

    ativo = st.sidebar.toggle(
        "⚡ Auto-Sincronizar (10s)",
        value=st.session_state["robo_ativo"],
        help="Lê automaticamente o CSV 'Atividades-*.csv' mais recente da pasta monitorada.",
    )
    st.session_state["robo_ativo"] = ativo

    with st.sidebar.expander("⚙️ Configurar Pasta", expanded=False):
        pasta_input = st.text_input(
            "Caminho do Disco:", value=pasta_alvo, key="input_pasta_robo"
        )
        st.session_state["robo_pasta_alvo"] = pasta_input
        pasta_alvo = pasta_input

    # ── EVIDENCIAÇÃO DO ARQUIVO ENCONTRADO ─────────────────────────────
    arq_detectado, _ = buscar_csv_mais_recente(pasta_alvo)

    if ativo:
        if arq_detectado:
            meta = _obter_metadados_arquivo(arq_detectado)
            df_mem = st.session_state.get("df_memoria")

            # Formata quantidade de registros
            if isinstance(df_mem, pd.DataFrame) and not df_mem.empty:
                qtd_linhas = f"{len(df_mem):,}".replace(",", ".")
            else:
                qtd_linhas = "Lendo..."

            is_sincronizado = arq_detectado == st.session_state.get(
                "robo_ultimo_arquivo"
            )

            dados_evidencia = {
                "📄 Nome": (
                    meta["nome"][:22] + "..."
                    if len(meta["nome"]) > 22
                    else meta["nome"]
                ),
                "📊 Linhas": qtd_linhas,
                "💾 Tamanho": meta["tamanho"],
                "🕒 Físico": meta["modificado"].split(" ")[1],  # Exibe Hora:Min:Seg
            }

            if is_sincronizado:
                render_sidebar_status(
                    label="Base Sincronizada",
                    status="ativo",
                    tag_customizada="EM DIA",
                    descricao=f"Arquivo ativo: **{meta['nome']}**",
                    dados=dados_evidencia,
                    ultima_atualizacao=st.session_state.get("robo_hora_sucesso"),
                    compacto=False,
                )
            else:
                render_sidebar_status(
                    label="Novo CSV Detectado",
                    status="pendente",
                    tag_customizada="Sincronizando",
                    descricao=f"Carregando: **{meta['nome']}**",
                    dados=dados_evidencia,
                    compacto=False,
                )
        else:
            render_sidebar_status(
                label="Buscando Base",
                status="pendente",
                tag_customizada="Procurando",
                descricao=f"Nenhum 'Atividades-*.csv' em:\n`{pasta_alvo}`",
                compacto=False,
            )
    else:
        # Estado quando o Robô está em pausa
        if arq_detectado:
            meta = _obter_metadados_arquivo(arq_detectado)
            render_sidebar_status(
                label="Robô Pausado",
                status="inativo",
                tag_customizada="Pronto",
                descricao=f"Disponível: **{meta['nome']}** ({meta['tamanho']})",
                compacto=False,
            )
        else:
            render_sidebar_status(
                label="Robô Pausado",
                status="inativo",
                descricao="Ative o monitoramento para sincronização automática.",
                compacto=True,
            )

    # Executa a verificação em background (loop do Streamlit fragment)
    _executar_verificacao_robo(pasta_alvo, etl_fn=etl_fn, gsheets_fn=gsheets_fn)
