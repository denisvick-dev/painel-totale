"""
robo/robo_local.py
==================
Interface Streamlit e orquestrador de ciclo para o motor unificado (`robo.robo_engine`).

Delega toda a descoberta de arquivos, detecção de base (ABCDM, SPO, GRS) e
leitura resiliente de CSV/Excel para `robo.robo_engine`.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pandas as pd

from robo.robo_engine import (
    _TAMANHO_MAXIMO_PADRAO,
    _TAMANHO_MINIMO_XLSX,
    _VALORES_AUSENTES,
    EXTENSOES_TEMP,
    EXTENSOES_VALIDAS,
    MAPA_BASES_ARQUIVO,
    PADROES_TOTALE,
    ArquivoBloqueadoError,
    Candidato,
    LeituraArquivo,
    ModoLeitura,
    ResultadoCiclo,
    TotaleRoboEngine,
    _aplicar_base_no_dataframe,
    _cabecalho_fraco,
    _celula_para_texto,
    _listar_candidatos_com_stat,
    _nomes_colunas_unicos,
    _padronizar_dataframe,
    _unificar_nomes_colunas,
    buscar_arquivo_mais_recente,
    contar_arquivos_por_base,
    detectar_base_arquivo,
    detectar_marcador_arquivo,
    formatar_tamanho,
    ler_arquivo_detalhado,
    mapear_arquivos_por_base,
    obter_metadados_arquivo,
    obter_pasta_robo_padrao,
    processar_candidatos,
    selecionar_arquivos,
)

try:
    import streamlit as st
except ImportError:  # permite testar a leitura sem o app
    st = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_LOCK_STALE_SEGUNDOS: int = 180

EtlFn = Callable[[pd.DataFrame, pd.DataFrame], "pd.DataFrame | None"]
FonteSheets = Callable[[], pd.DataFrame] | pd.DataFrame | None


def ler_arquivo_totale(
    caminho_arquivo: str,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    notificar: bool = True,
) -> pd.DataFrame | None:
    try:
        leitura = ler_arquivo_detalhado(caminho_arquivo, colunas_esperadas, sheet_name)
    except ArquivoBloqueadoError:
        raise
    if st is None or not notificar:
        return leitura.df
    nome = Path(caminho_arquivo).name if caminho_arquivo else "—"
    if leitura.erro:
        st.session_state["robo_erro"] = leitura.erro
        _toast_dedup(f"Falha ao ler: {nome}", icon="⚠️")
        return None
    _toast_dedup(f"Arquivo carregado: {nome}", icon="✅")
    return leitura.df


# ── UI e Controle de Sessão Streamlit ───────────────────────────────
def _exigir_streamlit() -> object:
    if st is None:
        raise RuntimeError(
            "Streamlit não está instalado. A sidebar do robô só roda no app."
        )
    return st


def _toast_dedup(mensagem: str, icon: str = "✅") -> None:
    if st is None:
        return
    assinatura = f"{icon}:{mensagem}"
    if st.session_state.get("_robo_ultimo_toast") != assinatura:
        st.session_state["_robo_ultimo_toast"] = assinatura
        st.toast(mensagem, icon=icon)


def _estado_str(chave: str, padrao: str) -> str:
    if st is None:
        return padrao
    valor = st.session_state.get(chave, padrao)
    return str(valor) if valor else padrao


def _estado_bool(chave: str, padrao: bool) -> bool:
    if st is None:
        return padrao
    valor = st.session_state.get(chave, padrao)
    return bool(valor)


def _modo_atual() -> ModoLeitura:
    """O modo é fixo: somente o arquivo de maior mtime entra no pipeline."""
    return "ultimo"


def _lock_ativo() -> bool:
    if st is None or not st.session_state.get("robo_processando", False):
        return False
    inicio = st.session_state.get("robo_processando_desde")
    if not isinstance(inicio, datetime):
        return False
    if (datetime.now() - inicio).total_seconds() < _LOCK_STALE_SEGUNDOS:
        return True
    st.session_state["robo_processando"] = False
    logger.warning("Lock do robô expirou depois de %ss.", _LOCK_STALE_SEGUNDOS)
    return False


def _obter_gsheets(gsheets_fn: FonteSheets) -> pd.DataFrame:
    if callable(gsheets_fn):
        return gsheets_fn()
    if isinstance(gsheets_fn, pd.DataFrame):
        return gsheets_fn
    return pd.DataFrame()


def _rerun_aplicacao() -> None:
    if st is None:
        return
    rerun = st.rerun
    try:
        rerun(scope="app")
    except TypeError:
        rerun()


def _executar_verificacao_robo(
    pasta_monitorada: str,
    etl_fn: EtlFn | None = None,
    gsheets_fn: FonteSheets = None,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    ciclos_estabilidade: int = 2,
    modo: ModoLeitura = "ultimo",
    recursivo: bool = False,
) -> None:
    if st is None or not _estado_bool("robo_ativo", True) or _lock_ativo():
        return

    candidatos = _listar_candidatos_com_stat(pasta_monitorada, recursivo=recursivo)
    selecionados = selecionar_arquivos(candidatos, modo)
    if not selecionados:
        return

    assinatura = tuple(selecionados)
    if st.session_state.get("robo_candidato_sig") == assinatura:
        stable = int(st.session_state.get("robo_candidato_stable", 0) or 0) + 1
    else:
        stable = 1
    st.session_state["robo_candidato_sig"] = assinatura
    st.session_state["robo_candidato_stable"] = stable
    if stable < max(ciclos_estabilidade, 1):
        return
    if st.session_state.get("robo_processado_sig") == assinatura:
        return

    st.session_state["robo_processando"] = True
    st.session_state["robo_processando_desde"] = datetime.now()
    try:
        if (
            tuple(
                selecionar_arquivos(
                    _listar_candidatos_com_stat(pasta_monitorada, recursivo=recursivo),
                    modo,
                )
            )
            != assinatura
        ):
            st.session_state["robo_candidato_stable"] = 0
            _toast_dedup("Arquivos mudaram durante a espera. Aguardando...", icon="⚠️")
            return

        resultado = processar_candidatos(
            candidatos,
            modo=modo,
            colunas_esperadas=colunas_esperadas,
            sheet_name=sheet_name,
        )
        if resultado.bloqueio and resultado.df is None:
            st.session_state["robo_candidato_stable"] = 0
            st.session_state["_robo_aguardando_lock"] = resultado.bloqueio
            return
        if resultado.df is None:
            if resultado.erros:
                st.session_state["robo_erro"] = " | ".join(resultado.erros)
            return

        if (
            tuple(
                selecionar_arquivos(
                    _listar_candidatos_com_stat(pasta_monitorada, recursivo=recursivo),
                    modo,
                )
            )
            != assinatura
        ):
            st.session_state["robo_candidato_stable"] = 0
            _toast_dedup("Arquivos mudaram durante a leitura. Aguardando...", icon="⚠️")
            return

        caminho_recente = selecionados[0][0]
        st.session_state["robo_ultimo_processado_path"] = caminho_recente
        st.session_state["robo_ultimo_processado_mtime"] = selecionados[0][1]
        st.session_state["robo_processado_sig"] = assinatura
        st.session_state["robo_arquivos_processados"] = {
            caminho: mtime for caminho, mtime, _ in selecionados
        }
        st.session_state["robo_bases_carregadas"] = list(resultado.bases)
        st.session_state["robo_base_detectada"] = detectar_base_arquivo(caminho_recente)
        st.session_state["robo_hora_sucesso"] = datetime.now()
        st.session_state["robo_motores"] = list(resultado.motores)
        st.session_state["robo_duplicatas_removidas"] = resultado.duplicatas_removidas
        st.session_state.pop("_robo_aguardando_lock", None)

        sufixo = f" · {', '.join(resultado.bases)}" if resultado.bases else ""
        st.session_state["origem_dados"] = (
            f"Robô Local ({len(resultado.arquivos)} arquivo(s){sufixo})"
        )
        if resultado.erros:
            st.session_state["robo_erro"] = "Parcial: " + " | ".join(resultado.erros)
        else:
            st.session_state.pop("robo_erro", None)

        df_gs = _obter_gsheets(gsheets_fn)
        if callable(etl_fn):
            transformado = etl_fn(resultado.df, df_gs)
            if isinstance(transformado, pd.DataFrame):
                st.session_state["df_memoria"] = transformado
        else:
            st.session_state["df_memoria"] = resultado.df

        if resultado.bases:
            _toast_dedup(
                f"Bases: {', '.join(resultado.bases)} — pipeline concluído!", icon="🚀"
            )
        else:
            _toast_dedup("Pipeline concluído!", icon="🚀")
        _rerun_aplicacao()
    except Exception as e:
        logger.exception("Falha no ciclo do robô")
        st.session_state["robo_erro"] = f"{type(e).__name__}: {e}"
        _toast_dedup(f"Erro no pipeline: {e}", icon="❌")
    finally:
        st.session_state["robo_processando"] = False


if st is not None and hasattr(st, "fragment"):
    _executar_verificacao_robo = st.fragment(run_every="5s")(_executar_verificacao_robo)


def renderizar_robo_local(
    etl_fn: EtlFn | None = None,
    gsheets_fn: FonteSheets = None,
    pasta_padrao: str | None = None,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    ciclos_estabilidade: int = 2,
    mostrar_toggle: bool = True,
    mostrar_config: bool = True,
) -> None:
    _exigir_streamlit()
    assert st is not None

    if "robo_ativo" not in st.session_state:
        st.session_state["robo_ativo"] = True
    st.session_state["robo_modo_leitura"] = "ultimo"
    if "robo_recursivo" not in st.session_state:
        st.session_state["robo_recursivo"] = False
    if not st.session_state.get("robo_pasta_alvo"):
        st.session_state["robo_pasta_alvo"] = pasta_padrao or obter_pasta_robo_padrao()
    if (
        pasta_padrao
        and not st.session_state.get("_robo_pasta_user_set")
        and st.session_state.get("robo_pasta_alvo")
        in (None, "", obter_pasta_robo_padrao())
    ):
        st.session_state["robo_pasta_alvo"] = pasta_padrao

    pasta_alvo = str(st.session_state["robo_pasta_alvo"])
    st.sidebar.markdown(
        """
        <div style='font-size:11px;font-weight:700;color:#64748B;text-transform:uppercase;
        letter-spacing:0.8px;margin:14px 0 6px;padding-left:4px;'>
            Robô de Sincronismo
        </div>
        """,
        unsafe_allow_html=True,
    )

    if mostrar_toggle:
        ativo = st.sidebar.toggle(
            "⚡ Auto-Sincronizar",
            value=_estado_bool("robo_ativo", True),
            key="robo_toggle_ui",
            help=(
                "Monitora a pasta a cada 5s enquanto esta sessão estiver aberta. "
                "SPO→Leste, GRS→Guarulhos, ABCDM→ABCDM."
            ),
        )
        st.session_state["robo_ativo"] = bool(ativo)
    else:
        ativo = _estado_bool("robo_ativo", True)

    if mostrar_config:
        with st.sidebar.expander("⚙️ Configurar Pasta", expanded=False):
            pasta_input = st.text_input(
                "Caminho do Disco:", value=pasta_alvo, key="input_pasta_robo"
            )
            if pasta_input != pasta_alvo:
                st.session_state["_robo_pasta_user_set"] = True
            st.session_state["robo_pasta_alvo"] = pasta_input
            pasta_alvo = str(pasta_input)
            st.caption("Leitura fixa: somente o arquivo mais recente da pasta inteira.")
            st.session_state["robo_recursivo"] = bool(
                st.checkbox(
                    "Incluir subpastas",
                    value=_estado_bool("robo_recursivo", False),
                    key="robo_recursivo_ui",
                )
            )
            if os.path.isdir(pasta_alvo):
                st.success("✅ Pasta válida")
            else:
                st.error("❌ Pasta não existe")

    modo = _modo_atual()
    recursivo = _estado_bool("robo_recursivo", False)
    candidatos_ui = _listar_candidatos_com_stat(pasta_alvo, recursivo=recursivo)
    selecionados_ui = selecionar_arquivos(candidatos_ui, modo)
    por_base = mapear_arquivos_por_base(pasta_alvo, recursivo=recursivo)

    if candidatos_ui:
        hora = st.session_state.get("robo_hora_sucesso")
        hs = hora.strftime("%H:%M:%S") if isinstance(hora, datetime) else "—"
        sig_ok = st.session_state.get("robo_processado_sig") == tuple(selecionados_ui)
        stable = int(st.session_state.get("robo_candidato_stable", 0) or 0)
        aguardando_lock = st.session_state.get("_robo_aguardando_lock")
        if sig_ok:
            st.sidebar.success(
                f"✅ Sincronizado às {hs}\n{len(selecionados_ui)} arquivo(s) no pipeline"
            )
        elif isinstance(aguardando_lock, str) and aguardando_lock:
            st.sidebar.info(f"⏳ {aguardando_lock}")
        else:
            st.sidebar.warning(
                f"📥 {len(candidatos_ui)} na pasta, {len(selecionados_ui)} na fila\n"
                f"Estável {stable}/{ciclos_estabilidade}"
            )

        extras = len(candidatos_ui) - len(selecionados_ui)
        if extras > 0:
            st.sidebar.caption(f"{extras} arquivo(s) mais antigo(s) fora do pipeline.")

        st.sidebar.markdown(
            """
            <div style='font-size:10px;font-weight:700;color:#64748B;text-transform:uppercase;
            letter-spacing:0.6px;margin:10px 0 4px;padding-left:4px;'>
                Bases Monitoradas
            </div>
            """,
            unsafe_allow_html=True,
        )
        processados_bruto = st.session_state.get("robo_arquivos_processados")
        processados_map: dict[object, object] = (
            processados_bruto if isinstance(processados_bruto, dict) else {}
        )
        for marcador, base in MAPA_BASES_ARQUIVO.items():
            info = por_base.get(base)
            if info is None:
                st.sidebar.caption(f"⬜ {base} — aguardando arquivo com '{marcador}'")
                continue
            caminho_b, mtime_b, _ = info
            meta = obter_metadados_arquivo(caminho_b)
            ok = processados_map.get(caminho_b) == mtime_b
            icone = "✅" if ok else "📥"
            st.sidebar.caption(
                f"{icone} {base} — {meta['nome'][:32]} ({meta['tamanho']})"
            )

        sem_base = [c for c, _, _ in candidatos_ui if detectar_base_arquivo(c) is None]
        if sem_base:
            st.sidebar.caption(
                f"⚠️ {len(sem_base)} arquivo(s) sem SPO, GRS ou ABCDM no nome."
            )
        removidas = st.session_state.get("robo_duplicatas_removidas")
        if isinstance(removidas, int) and removidas > 0:
            st.sidebar.caption(
                f"{removidas} linha(s) idêntica(s) removida(s) na junção."
            )
    else:
        estado = "🟢 Monitorando" if ativo else "⏸ Pausado"
        st.sidebar.info(f"{estado}: `{Path(pasta_alvo).name}`")

    erro = st.session_state.get("robo_erro")
    if isinstance(erro, str) and erro:
        st.sidebar.error(f"❌ {erro}")
        c_a, c_b = st.sidebar.columns(2)
        with c_a:
            if st.button("🧹 Limpar", key="limpar_erro_robo", width="stretch"):
                st.session_state.pop("robo_erro", None)
                _rerun_aplicacao()
        with c_b:
            if st.button("🔄 Retentar", key="retry_erro_robo", width="stretch"):
                st.session_state.pop("robo_erro", None)
                st.session_state["robo_candidato_sig"] = None
                st.session_state["robo_processado_sig"] = None
                st.session_state["robo_candidato_stable"] = 0
                _rerun_aplicacao()

    _executar_verificacao_robo(
        pasta_monitorada=pasta_alvo,
        etl_fn=etl_fn,
        gsheets_fn=gsheets_fn,
        colunas_esperadas=colunas_esperadas,
        sheet_name=sheet_name,
        ciclos_estabilidade=ciclos_estabilidade,
        modo=modo,
        recursivo=recursivo,
    )


def executar_ciclo_headless(
    pasta: str,
    destino_csv: str | None = None,
    modo: ModoLeitura = "ultimo",
    colunas_esperadas: list[str] | None = None,
) -> ResultadoCiclo:
    """Um ciclo sem Streamlit. Processa apenas o arquivo mais recente da pasta."""
    resultado = processar_candidatos(
        _listar_candidatos_com_stat(pasta),
        modo=modo,
        colunas_esperadas=colunas_esperadas,
    )
    if resultado.df is not None and destino_csv:
        Path(destino_csv).parent.mkdir(parents=True, exist_ok=True)
        resultado.df.to_csv(destino_csv, index=False, sep=";", encoding="utf-8-sig")
    return resultado


renderizar_sidebar_robo = renderizar_robo_local
_obter_pasta_robo_padrao = obter_pasta_robo_padrao
_obter_metadados_arquivo = obter_metadados_arquivo

__all__ = [
    "EXTENSOES_TEMP",
    "EXTENSOES_VALIDAS",
    "MAPA_BASES_ARQUIVO",
    "PADROES_TOTALE",
    "ArquivoBloqueadoError",
    "Candidato",
    "LeituraArquivo",
    "ModoLeitura",
    "ResultadoCiclo",
    "TotaleRoboEngine",
    "_TAMANHO_MAXIMO_PADRAO",
    "_TAMANHO_MINIMO_XLSX",
    "_VALORES_AUSENTES",
    "_aplicar_base_no_dataframe",
    "_cabecalho_fraco",
    "_celula_para_texto",
    "_nomes_colunas_unicos",
    "_padronizar_dataframe",
    "_unificar_nomes_colunas",
    "buscar_arquivo_mais_recente",
    "contar_arquivos_por_base",
    "detectar_base_arquivo",
    "detectar_marcador_arquivo",
    "executar_ciclo_headless",
    "formatar_tamanho",
    "ler_arquivo_detalhado",
    "ler_arquivo_totale",
    "mapear_arquivos_por_base",
    "obter_metadados_arquivo",
    "obter_pasta_robo_padrao",
    "processar_candidatos",
    "renderizar_robo_local",
    "renderizar_sidebar_robo",
    "selecionar_arquivos",
]


if __name__ == "__main__":
    pasta_cli = sys.argv[1] if len(sys.argv) > 1 else obter_pasta_robo_padrao()
    destino = (
        sys.argv[2] if len(sys.argv) > 2 else str(Path(pasta_cli) / "_robo_cache.csv")
    )
    ciclo = executar_ciclo_headless(pasta_cli, destino_csv=destino)
    if ciclo.df is None:
        print(ciclo.bloqueio or " | ".join(ciclo.erros) or "Nenhum arquivo processado.")
        raise SystemExit(1)
    print(f"{len(ciclo.df)} linhas, bases={', '.join(ciclo.bases) or '—'} → {destino}")
