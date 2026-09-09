"""
robo/robo_local.py
==================
Robô monitor de pasta local para arquivos TOTALE (CSV/Excel).
API pública: renderizar_robo_local(etl_fn, gsheets_fn, ...)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Constantes ──────────────────────────────────────────────────────
PADROES_TOTALE: tuple[str, ...] = (
    "Atividades-*.csv",
    "Atividades-*.xlsx",
    "Atividades-*.xls",
)
EXTENSOES_VALIDAS: tuple[str, ...] = (".csv", ".xlsx", ".xls")
EXTENSOES_TEMP: tuple[str, ...] = (".tmp", ".crdownload")


# ── Utilitários ─────────────────────────────────────────────────────
def obter_pasta_robo_padrao() -> str:
    """Pasta padrão: ./robo (dados), ~/robo, ou Downloads."""
    base = Path(__file__).resolve().parent
    for cand in (base / "dados", Path.home() / "robo", Path.home() / "Downloads"):
        if cand.exists() and cand.is_dir():
            return str(cand.resolve())
    return str(Path.home() / "Downloads")


def formatar_tamanho(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_ / (1024 * 1024):.2f} MB"


def obter_metadados_arquivo(caminho: str | None) -> dict[str, str]:
    if not caminho or not os.path.exists(caminho):
        return {
            "nome": Path(caminho).name if caminho else "Desconhecido",
            "ext": Path(caminho).suffix.lower() if caminho else "",
            "tamanho": "—",
            "modificado": "—",
            "caminho_completo": caminho or "",
        }
    try:
        p = Path(caminho)
        stat = p.stat()
        return {
            "nome": p.name,
            "ext": p.suffix.lower(),
            "tamanho": formatar_tamanho(stat.st_size),
            "modificado": datetime.fromtimestamp(stat.st_mtime).strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "caminho_completo": str(p.resolve()),
        }
    except Exception:
        return {
            "nome": Path(caminho).name if caminho else "Desconhecido",
            "ext": Path(caminho).suffix.lower() if caminho else "",
            "tamanho": "—",
            "modificado": "—",
            "caminho_completo": caminho or "",
        }


def _stat_basico(caminho: str) -> tuple[float | None, int | None]:
    try:
        st_ = os.stat(caminho)
        return float(st_.st_mtime), int(st_.st_size)
    except Exception:
        return None, None


def _toast_dedup(mensagem: str, icon: str = "✅") -> None:
    assinatura = f"{icon}:{mensagem}"
    if st.session_state.get("_robo_ultimo_toast") != assinatura:
        st.session_state["_robo_ultimo_toast"] = assinatura
        st.toast(mensagem, icon=icon)


# ── Busca ───────────────────────────────────────────────────────────
def buscar_arquivo_mais_recente(
    pasta: str,
    padroes: tuple[str, ...] = PADROES_TOTALE,
) -> tuple[str | None, float | None, int | None]:
    p = Path(pasta)
    if not p.exists() or not p.is_dir():
        return None, None, None

    candidatos: list[Path] = []
    for padrao in padroes:
        candidatos.extend(p.glob(padrao))

    if not candidatos:
        for ext in EXTENSOES_VALIDAS:
            candidatos.extend(p.glob(f"*Atividades*{ext}"))

    def _eh_valido(arq: Path) -> bool:
        nome = arq.name.lower()
        if nome.endswith(EXTENSOES_TEMP) or nome.startswith("~$"):
            return False
        return arq.is_file()

    validos = [c for c in candidatos if _eh_valido(c)]
    if not validos:
        return None, None, None

    try:
        mais = max(validos, key=lambda x: x.stat().st_mtime)
        mtime, size = _stat_basico(str(mais))
        return str(mais), mtime, size
    except Exception:
        return None, None, None


# ── Leitura ─────────────────────────────────────────────────────────
def ler_arquivo_totale(
    caminho_arquivo: str,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
) -> pd.DataFrame | None:
    if not caminho_arquivo or not os.path.exists(caminho_arquivo):
        _toast_dedup(
            f"Arquivo não encontrado: {Path(caminho_arquivo).name if caminho_arquivo else '—'}",
            icon="❌",
        )
        return None

    ext = Path(caminho_arquivo).suffix.lower()

    if ext in (".xlsx", ".xls"):
        planilha = 0 if sheet_name is None else sheet_name
        try:
            df = pd.read_excel(caminho_arquivo, sheet_name=planilha, dtype=str)
            if isinstance(df, dict):
                df = list(df.values())[0] if df else pd.DataFrame()  # type: ignore
            if colunas_esperadas and not all(
                c in df.columns for c in colunas_esperadas
            ):
                _toast_dedup("Excel OK, mas colunas esperadas ausentes.", icon="⚠️")
                return None
            _toast_dedup(f"Arquivo carregado: {Path(caminho_arquivo).name}", icon="✅")
            return df
        except Exception as e:
            st.session_state["robo_erro"] = str(e)
            _toast_dedup(f"Falha Excel: {Path(caminho_arquivo).name}", icon="⚠️")
            return None

    for enc in ("utf-8-sig", "cp1252", "latin1", "iso-8859-1", "utf-8"):
        for sep in (";", ","):
            try:
                df = pd.read_csv(
                    caminho_arquivo,
                    sep=sep,
                    encoding=enc,
                    dtype=str,
                    low_memory=False,
                    on_bad_lines="skip",
                )
                if df.shape[1] <= 3:
                    continue
                if colunas_esperadas and not all(
                    c in df.columns for c in colunas_esperadas
                ):
                    continue
                _toast_dedup(
                    f"Arquivo carregado: {Path(caminho_arquivo).name}", icon="✅"
                )
                return df
            except Exception:
                continue

    _toast_dedup(f"Falha ao ler: {Path(caminho_arquivo).name}", icon="⚠️")
    return None


# ── Loop (fragment) ─────────────────────────────────────────────────
@st.fragment(run_every="10s")
def _executar_verificacao_robo(
    pasta_monitorada: str,
    etl_fn: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame] | None = None,
    gsheets_fn: Callable[[], pd.DataFrame] | None = None,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    ciclos_estabilidade: int = 2,
) -> None:
    if not st.session_state.get("robo_ativo", True):
        return
    if st.session_state.get("robo_processando", False):
        return

    caminho, mtime, size = buscar_arquivo_mais_recente(pasta_monitorada)
    if caminho is None or mtime is None or size is None:
        return

    cand_prev = st.session_state.get("robo_candidato_path")
    mtime_prev = st.session_state.get("robo_candidato_mtime")
    size_prev = st.session_state.get("robo_candidato_size")
    stable: int = int(st.session_state.get("robo_candidato_stable", 0) or 0)

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

    ultimo = st.session_state.get("robo_ultimo_processado_path")
    ultimo_m = st.session_state.get("robo_ultimo_processado_mtime")
    if caminho == ultimo and mtime == ultimo_m:
        return

    st.session_state["robo_processando"] = True
    try:
        df_local = ler_arquivo_totale(caminho, colunas_esperadas, sheet_name)
        if df_local is None:
            return

        mtime_pos, size_pos = _stat_basico(caminho)
        if mtime_pos != mtime or size_pos != size:
            st.session_state["robo_candidato_stable"] = 0
            _toast_dedup("Arquivo mudou durante a leitura. Aguardando...", icon="⚠️")
            return

        # Proteção contra erros de 'not callable' no gsheets_fn
        if callable(gsheets_fn):
            df_gs = gsheets_fn()
        elif isinstance(gsheets_fn, pd.DataFrame):
            df_gs = gsheets_fn
        else:
            df_gs = pd.DataFrame()

        st.session_state["robo_ultimo_processado_path"] = caminho
        st.session_state["robo_ultimo_processado_mtime"] = mtime
        st.session_state["robo_hora_sucesso"] = datetime.now()
        st.session_state["origem_dados"] = f"Robô Local ({Path(caminho).name})"
        st.session_state.pop("robo_erro", None)

        # Proteção contra erros de 'not callable' no etl_fn
        if callable(etl_fn):
            resultado = etl_fn(df_local, df_gs)
            if (
                resultado is not None
                and isinstance(resultado, pd.DataFrame)
                and st.session_state.get("df_memoria") is None
            ):
                st.session_state["df_memoria"] = resultado
        else:
            st.session_state["df_memoria"] = df_local

        _toast_dedup("Pipeline concluído!", icon="🚀")
        st.rerun()
    except Exception as e:
        st.session_state["robo_erro"] = str(e)
        _toast_dedup(f"Erro no pipeline: {e}", icon="❌")
    finally:
        st.session_state["robo_processando"] = False


# ── UI Sidebar ──────────────────────────────────────────────────────
def renderizar_robo_local(
    etl_fn: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame] | None = None,
    gsheets_fn: Callable[[], pd.DataFrame] | None = None,
    pasta_padrao: str | None = None,
    colunas_esperadas: list[str] | None = None,
    sheet_name: str | int | None = 0,
    ciclos_estabilidade: int = 2,
    mostrar_toggle: bool = True,
    mostrar_config: bool = True,
) -> None:
    if "robo_ativo" not in st.session_state:
        st.session_state["robo_ativo"] = True

    if "robo_pasta_alvo" not in st.session_state or not st.session_state.get(
        "robo_pasta_alvo"
    ):
        st.session_state["robo_pasta_alvo"] = pasta_padrao or obter_pasta_robo_padrao()

    if pasta_padrao and not st.session_state.get("_robo_pasta_user_set"):
        if st.session_state.get("robo_pasta_alvo") in (
            None,
            "",
            obter_pasta_robo_padrao(),
        ):
            st.session_state["robo_pasta_alvo"] = pasta_padrao

    pasta_alvo: str = str(st.session_state["robo_pasta_alvo"])

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
            "⚡ Auto-Sincronizar (10s)",
            value=bool(st.session_state["robo_ativo"]),
            key="robo_toggle_ui",
            help="Monitora a pasta em busca de Atividades-*.csv/xlsx",
        )
        st.session_state["robo_ativo"] = ativo
    else:
        ativo = bool(st.session_state["robo_ativo"])

    if mostrar_config:
        with st.sidebar.expander("⚙️ Configurar Pasta", expanded=False):
            pasta_input = st.text_input(
                "Caminho do Disco:",
                value=pasta_alvo,
                key="input_pasta_robo",
            )
            if pasta_input != pasta_alvo:
                st.session_state["_robo_pasta_user_set"] = True
            st.session_state["robo_pasta_alvo"] = pasta_input
            pasta_alvo = pasta_input

            if os.path.isdir(pasta_alvo):
                st.success("✅ Pasta válida")
                try:
                    n = len(
                        [
                            f
                            for f in os.listdir(pasta_alvo)
                            if f.lower().endswith(EXTENSOES_VALIDAS)
                        ]
                    )
                    st.caption(f"📄 {n} arquivo(s) compatível(is)")
                except Exception:
                    st.caption("⚠️ Não foi possível listar")
            else:
                st.error("❌ Pasta não existe")

    caminho_arq, mtime, _ = buscar_arquivo_mais_recente(pasta_alvo)
    if caminho_arq:
        meta = obter_metadados_arquivo(caminho_arq)
        ultimo = st.session_state.get("robo_ultimo_processado_path")
        ultimo_m = st.session_state.get("robo_ultimo_processado_mtime")
        is_ok = caminho_arq == ultimo and mtime == ultimo_m
        stable = int(st.session_state.get("robo_candidato_stable", 0) or 0)

        if is_ok:
            hora = st.session_state.get("robo_hora_sucesso")
            hs = hora.strftime("%H:%M:%S") if isinstance(hora, datetime) else "—"
            st.sidebar.success(f"✅ Base OK: {meta['nome'][:40]}\nSync {hs}")
        else:
            st.sidebar.warning(
                f"📥 {meta['nome'][:40]}\n"
                f"Estável {stable}/{ciclos_estabilidade} · {meta['tamanho']}"
            )
    else:
        st.sidebar.info(
            f"{'🟢 Monitorando' if ativo else '⏸ Pausado'}: `{Path(pasta_alvo).name}`"
        )

    erro = st.session_state.get("robo_erro")
    if erro:
        st.sidebar.error(f"❌ {erro}")
        if st.sidebar.button("🧹 Limpar Erro", key="limpar_erro_robo"):
            st.session_state.pop("robo_erro", None)
            st.rerun()

    _executar_verificacao_robo(
        pasta_monitorada=pasta_alvo,
        etl_fn=etl_fn,
        gsheets_fn=gsheets_fn,
        colunas_esperadas=colunas_esperadas,
        sheet_name=sheet_name,
        ciclos_estabilidade=ciclos_estabilidade,
    )


# Aliases
renderizar_sidebar_robo = renderizar_robo_local
_obter_pasta_robo_padrao = obter_pasta_robo_padrao
_obter_metadados_arquivo = obter_metadados_arquivo

__all__ = [
    "EXTENSOES_VALIDAS",
    "buscar_arquivo_mais_recente",
    "ler_arquivo_totale",
    "obter_metadados_arquivo",
    "obter_pasta_robo_padrao",
    "renderizar_robo_local",
    "renderizar_sidebar_robo",
]
