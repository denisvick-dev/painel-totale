"""
robo_local.py
=============
Robô monitor de pasta local para arquivos do TOTALE (CSV ou Excel).
Detecta automaticamente o arquivo mais recente do padrão 'Atividades-*.(csv|xlsx|xls)',
evidencia metadados em disco e aciona o pipeline de ETL.

Pasta padrão: ./robo (relativa ao projeto) ou caminho absoluto configurado.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple, List

import pandas as pd
import streamlit as st

# Importação do Design System Corporativo
try:
    from components.componentes import render_sidebar_status
except ImportError:
    # Fallback caso componentes.py não esteja disponível
    def render_sidebar_status(**kwargs):
        st.sidebar.info("Status do robô indisponível")


# ----------------------------
# Utilitários
# ----------------------------
def _obter_pasta_robo_padrao() -> str:
    """
    Retorna o caminho padrão da pasta 'robo'.
    Prioridade:
    1. Pasta 'robo' relativa ao diretório do projeto
    2. Pasta 'robo' no diretório home do usuário
    3. Pasta Downloads como fallback
    """
    pasta_relativa = Path(__file__).parent.parent / "robo"
    if pasta_relativa.exists():
        return str(pasta_relativa.resolve())

    pasta_home = Path.home() / "robo"
    if pasta_home.exists():
        return str(pasta_home.resolve())

    return str(Path.home() / "Downloads")


def _formatar_tamanho(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_ / (1024 * 1024):.2f} MB"


def _obter_metadados_arquivo(caminho: str) -> Dict[str, str]:
    """Extrai e formata metadados do arquivo físico em disco."""
    try:
        p = Path(caminho)
        stat = p.stat()
        dt_mod = datetime.fromtimestamp(stat.st_mtime)
        return {
            "nome": p.name,
            "ext": p.suffix.lower(),
            "tamanho": _formatar_tamanho(stat.st_size),
            "modificado": dt_mod.strftime("%d/%m/%Y %H:%M:%S"),
            "caminho_completo": str(p),
        }
    except Exception:
        return {
            "nome": Path(caminho).name if caminho else "Desconhecido",
            "ext": Path(caminho).suffix.lower() if caminho else "",
            "tamanho": "—",
            "modificado": "—",
            "caminho_completo": caminho or "",
        }


def _stat_basico(caminho: str) -> Tuple[Optional[float], Optional[int]]:
    """Retorna (mtime, size) ou (None, None)."""
    try:
        st_ = os.stat(caminho)
        return float(st_.st_mtime), int(st_.st_size)
    except Exception:
        return None, None


# ----------------------------
# Busca do arquivo mais recente
# ----------------------------
def buscar_arquivo_mais_recente(
    pasta: str,
    padroes: Tuple[str, ...] = (
        "Atividades-*.csv",
        "Atividades-*.xlsx",
        "Atividades-*.xls",
    ),
) -> Tuple[Optional[str], Optional[float], Optional[int]]:
    """
    Busca o arquivo mais recente que atenda aos padrões na pasta.

    Retorna:
        (caminho, mtime, size)
    """
    p = Path(pasta)
    if not p.exists() or not p.is_dir():
        return None, None, None

    candidatos: List[Path] = []
    for padrao in padroes:
        candidatos.extend(p.glob(padrao))

    # Fallback flexível se nenhum encontrado
    if not candidatos:
        candidatos.extend(p.glob("*Atividades*.csv"))
        candidatos.extend(p.glob("*Atividades*.xlsx"))
        candidatos.extend(p.glob("*Atividades*.xls"))

    # Filtra temporários comuns (Chrome/Windows/Excel)
    def _eh_valido(arq: Path) -> bool:
        nome = arq.name.lower()
        if nome.endswith((".tmp", ".crdownload")):
            return False
        # Excel cria arquivos começando com "~$" quando está aberto/escrevendo
        if nome.startswith("~$"):
            return False
        return arq.is_file()

    candidatos = [c for c in candidatos if _eh_valido(c)]
    if not candidatos:
        return None, None, None

    try:
        mais_recente = max(candidatos, key=lambda x: x.stat().st_mtime)
        mtime, size = _stat_basico(str(mais_recente))
        return str(mais_recente), mtime, size
    except Exception:
        return None, None, None


# ----------------------------
# Leitura (CSV ou Excel)
# ----------------------------
def ler_arquivo_totale(
    caminho_arquivo: str,
    colunas_esperadas: Optional[List[str]] = None,
    sheet_name: Optional[str | int] = 0,
) -> Optional[pd.DataFrame]:
    """
    Lê arquivo do TOTALE em CSV ou Excel.
    - CSV: tenta encodings e separadores comuns.
    - Excel: lê a planilha indicada (padrão: primeira).
    """
    if not caminho_arquivo or not os.path.exists(caminho_arquivo):
        st.toast(f" Arquivo não encontrado: {Path(caminho_arquivo).name}", icon="❌")
        return None

    ext = Path(caminho_arquivo).suffix.lower()

    # --- Excel ---
    if ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(
                caminho_arquivo,
                sheet_name=sheet_name if sheet_name is not None else 0,
                dtype=str,
            )
            if colunas_esperadas and not all(
                col in df.columns for col in colunas_esperadas
            ):
                st.toast(
                    "⚠️ Excel carregado, mas colunas esperadas não encontradas.",
                    icon="⚠️",
                )
                return None

            st.toast(f"✅ Arquivo carregado: {Path(caminho_arquivo).name}", icon="✅")
            return df
        except Exception as e:
            st.toast(f"⚠️ Falha ao ler Excel: {Path(caminho_arquivo).name}", icon="⚠️")
            st.session_state["robo_erro"] = str(e)
            return None

    # --- CSV ---
    encodings = ["utf-8-sig", "cp1252", "latin1", "iso-8859-1", "utf-8"]
    separadores = [";", ","]

    for enc in encodings:
        for sep in separadores:
            try:
                df = pd.read_csv(
                    caminho_arquivo,
                    sep=sep,
                    encoding=enc,
                    dtype=str,
                    low_memory=False,
                    on_bad_lines="skip",
                )
                if df.shape[1] > 3:
                    if colunas_esperadas and not all(
                        col in df.columns for col in colunas_esperadas
                    ):
                        continue
                    st.toast(
                        f"✅ Arquivo carregado: {Path(caminho_arquivo).name}", icon="✅"
                    )
                    return df
            except Exception:
                continue

    st.toast(f"⚠️ Falha ao ler arquivo: {Path(caminho_arquivo).name}", icon="⚠️")
    return None


# ----------------------------
# Loop de verificação (fragment)
# ----------------------------
@st.fragment(run_every="10s")
def _executar_verificacao_robo(
    pasta_monitorada: str,
    etl_fn: Optional[Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]] = None,
    gsheets_fn: Optional[Callable[[], pd.DataFrame]] = None,
    colunas_esperadas: Optional[List[str]] = None,
    sheet_name: Optional[str | int] = 0,
    ciclos_estabilidade: int = 2,
) -> None:
    """
    Verifica periodicamente e executa o ETL automaticamente.
    Robustez:
      - evita overlap (lock em session_state)
      - só processa quando arquivo estável por N ciclos (mtime+size constantes)
    """
    if not st.session_state.get("robo_ativo", True):
        return

    if st.session_state.get("robo_processando", False):
        return

    caminho, mtime, size = buscar_arquivo_mais_recente(pasta_monitorada)

    if not caminho or not mtime or size is None:
        return

    # Controle de estabilidade
    cand_prev = st.session_state.get("robo_candidato_path")
    mtime_prev = st.session_state.get("robo_candidato_mtime")
    size_prev = st.session_state.get("robo_candidato_size")
    stable = st.session_state.get("robo_candidato_stable", 0)

    if caminho == cand_prev and mtime == mtime_prev and size == size_prev:
        stable += 1
    else:
        stable = 0

    st.session_state["robo_candidato_path"] = caminho
    st.session_state["robo_candidato_mtime"] = mtime
    st.session_state["robo_candidato_size"] = size
    st.session_state["robo_candidato_stable"] = stable

    if stable < ciclos_estabilidade:
        return

    ultimo_processado = st.session_state.get("robo_ultimo_processado_path")
    ultimo_mtime = st.session_state.get("robo_ultimo_processado_mtime")

    if caminho == ultimo_processado and mtime == ultimo_mtime:
        return

    # --- Execução do Pipeline ---
    st.session_state["robo_processando"] = True
    try:
        df_local = ler_arquivo_totale(caminho, colunas_esperadas, sheet_name)
        if df_local is not None:
            df_gsheets = pd.DataFrame()
            if gsheets_fn:
                df_gsheets = gsheets_fn()

            # Salva na session_state para as páginas usarem
            st.session_state["df_memoria"] = df_local
            st.session_state["robo_ultimo_processado_path"] = caminho
            st.session_state["robo_ultimo_processado_mtime"] = mtime
            st.session_state["robo_hora_sucesso"] = datetime.now()
            st.session_state["origem_dados"] = f"Robô Local ({Path(caminho).name})"

            # Executa ETL se fornecido
            if etl_fn:
                etl_fn(df_local, df_gsheets)

            st.session_state.pop("robo_erro", None)
            st.toast("🚀 Pipeline concluído com sucesso!", icon="")
    except Exception as e:
        st.session_state["robo_erro"] = str(e)
        st.toast(f"❌ Erro crítico no pipeline: {str(e)}", icon="❌")
    finally:
        st.session_state["robo_processando"] = False


# ----------------------------
# Interface do Robô (Sidebar)
# ----------------------------
def renderizar_robo_local(
    etl_fn: Optional[Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]] = None,
    gsheets_fn: Optional[Callable[[], pd.DataFrame]] = None,
    pasta_padrao: Optional[str] = None,
    colunas_esperadas: Optional[List[str]] = None,
    sheet_name: Optional[str | int] = 0,
    ciclos_estabilidade: int = 2,
    mostrar_toggle: bool = True,
    mostrar_config: bool = True,
) -> None:
    """
    Renderiza a interface do robô na sidebar com início automático.

    Args:
        etl_fn: Função de transformação de dados (recebe df_local, df_gsheets)
        gsheets_fn: Função para carregar dados do Google Sheets
        pasta_padrao: Caminho da pasta a monitorar (None = usa padrão ./robo)
        colunas_esperadas: Lista de colunas esperadas para validação
        sheet_name: Nome ou índice da planilha (para Excel)
        ciclos_estabilidade: Nº de ciclos sem mudança para considerar arquivo estável
        mostrar_toggle: Exibe o toggle de ativar/desativar
        mostrar_config: Exibe o expander de configuração de pasta

    Exemplo:
        >>> renderizar_robo_local(
        ...     etl_fn=processar_dados,
        ...     gsheets_fn=carregar_hierarquia,
        ...     pasta_padrao=None,  # Usa ./robo
        ... )
    """

    # ── Inicialização de Estado ────────────────────────────────────────
    if "robo_ativo" not in st.session_state:
        st.session_state["robo_ativo"] = True

    if "robo_pasta_alvo" not in st.session_state:
        st.session_state["robo_pasta_alvo"] = pasta_padrao or _obter_pasta_robo_padrao()

    pasta_alvo = st.session_state["robo_pasta_alvo"]

    # ── Cabeçalho do Robô na Sidebar ───────────────────────────────────
    st.sidebar.markdown(
        """
        <div style='
            font-size: 11px;
            font-weight: 700;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin: 14px 0 6px;
            padding-left: 4px;
        '>
             Robô de Sincronismo
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Toggle de Ativação (Opcional) ──────────────────────────────────
    if mostrar_toggle:
        ativo = st.sidebar.toggle(
            "⚡ Auto-Sincronizar (10s)",
            value=st.session_state["robo_ativo"],
            help="Monitora automaticamente a pasta 'robo' em busca de novos arquivos.",
        )
        st.session_state["robo_ativo"] = ativo
    else:
        ativo = st.session_state["robo_ativo"]

    # ── Configuração de Pasta (Opcional) ──────────────────────────────
    if mostrar_config:
        with st.sidebar.expander("️ Configurar Pasta", expanded=False):
            pasta_input = st.text_input(
                "Caminho do Disco:",
                value=pasta_alvo,
                key="input_pasta_robo",
                help="Caminho absoluto da pasta a ser monitorada.",
            )
            st.session_state["robo_pasta_alvo"] = pasta_input
            pasta_alvo = pasta_input

            # Mostra informações da pasta
            if os.path.exists(pasta_alvo):
                st.success(f"✅ Pasta válida")
                try:
                    n_arquivos = len(
                        [
                            f
                            for f in os.listdir(pasta_alvo)
                            if f.endswith((".csv", ".xlsx", ".xls"))
                        ]
                    )
                    st.caption(f"📄 {n_arquivos} arquivo(s) compatível(is)")
                except Exception:
                    st.caption("⚠️ Não foi possível listar arquivos")
            else:
                st.error(f"❌ Pasta não existe")

            # Botão para abrir a pasta
            if st.button("📂 Abrir Pasta", use_container_width=True):
                try:
                    import subprocess
                    import platform

                    sistema = platform.system()
                    if sistema == "Windows":
                        subprocess.run(["explorer", pasta_alvo], check=True)
                    elif sistema == "Darwin":
                        subprocess.run(["open", pasta_alvo], check=True)
                    else:
                        subprocess.run(["xdg-open", pasta_alvo], check=True)
                except Exception as e:
                    st.error(f"Não foi possível abrir: {e}")

    # ── Detecção de Arquivo ────────────────────────────────────────────
    caminho_arquivo, mtime, size = buscar_arquivo_mais_recente(pasta_alvo)

    # ─ Renderização de Status ────────────────────────────────────────
    if caminho_arquivo:
        meta = _obter_metadados_arquivo(caminho_arquivo)

        # Verifica se já foi processado
        ultimo_processado = st.session_state.get("robo_ultimo_processado_path")
        ultimo_mtime = st.session_state.get("robo_ultimo_processado_mtime")

        is_processado = caminho_arquivo == ultimo_processado and mtime == ultimo_mtime

        # Dados para exibição
        dados_evidencia = {
            " Arquivo": (
                meta["nome"][:25] + "..." if len(meta["nome"]) > 25 else meta["nome"]
            ),
            "📐 Extensão": meta["ext"].upper(),
            "💾 Tamanho": meta["tamanho"],
            "🕒 Modificado": (
                meta["modificado"].split(" ")[1] if meta["modificado"] != "—" else "—"
            ),
        }

        # Adiciona info do último processamento
        if is_processado and st.session_state.get("robo_hora_sucesso"):
            dados_evidencia["✅ Última Sync"] = st.session_state[
                "robo_hora_sucesso"
            ].strftime("%H:%M:%S")

        if is_processado:
            # ✅ Arquivo já processado
            render_sidebar_status(
                status="sucesso",
                label="Base Sincronizada",
                descricao=f"Arquivo processado: **{meta['nome']}**",
                tag_customizada="EM DIA",
                dados=dados_evidencia,
                ultima_atualizacao=st.session_state.get("robo_hora_sucesso"),
                compacto=False,
            )
        else:
            # 🟡 Arquivo detectado, aguardando processamento
            stable = st.session_state.get("robo_candidato_stable", 0)
            if stable >= ciclos_estabilidade:
                render_sidebar_status(
                    status="pendente",
                    label="Novo Arquivo Detectado",
                    descricao=f"Processando: **{meta['nome']}**",
                    tag_customizada="PROCESSANDO",
                    dados=dados_evidencia,
                    compacto=False,
                )
            else:
                render_sidebar_status(
                    status="pendente",
                    label="Verificando Estabilidade",
                    descricao=f"Aguardando: **{meta['nome']}**",
                    tag_customizada=f"ESTÁVEL {stable}/{ciclos_estabilidade}",
                    dados=dados_evidencia,
                    compacto=False,
                )
    else:
        #  Nenhum arquivo encontrado
        render_sidebar_status(
            status="ativo" if ativo else "inativo",
            label="Aguardando Arquivo",
            descricao=f"Nenhum arquivo compatível em:\n`{Path(pasta_alvo).name}`",
            tag_customizada="MONITORANDO" if ativo else "PAUSADO",
            dados={"📁 Pasta": Path(pasta_alvo).name},
            compacto=False,
        )

    # ── Exibe Erros (se houver) ───────────────────────────────────────
    erro = st.session_state.get("robo_erro")
    if erro:
        st.sidebar.error(f"❌ **Erro:** {erro}")
        if st.sidebar.button("️ Limpar Erro", key="limpar_erro_robo"):
            st.session_state.pop("robo_erro", None)
            st.rerun()

    # ── Executa Verificação em Background ─────────────────────────────
    _executar_verificacao_robo(
        pasta_monitorada=pasta_alvo,
        etl_fn=etl_fn,
        gsheets_fn=gsheets_fn,
        colunas_esperadas=colunas_esperadas,
        sheet_name=sheet_name,
        ciclos_estabilidade=ciclos_estabilidade,
    )


# ----------------------------
# Exportações Públicas
# ----------------------------
__all__ = [
    "renderizar_robo_local",
    "buscar_arquivo_mais_recente",
    "ler_arquivo_totale",
    "_obter_pasta_robo_padrao",
    "_obter_metadados_arquivo",
]