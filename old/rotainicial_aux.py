"""
rota_inicial.py
===============
Dashboard de Rota Inicial — Distribuição de OS por Monitor e Turno
"""

from __future__ import annotations

import re  # CORREÇÃO 1: import no topo, não dentro de função
import sys
from pathlib import Path

_DIR  = Path(__file__).resolve().parent
_ROOT = _DIR.parent
for _p in [_DIR, _ROOT]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from datetime import date as date_type  # CORREÇÃO 2: alias claro para o tipo date
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st

try:
    from components.componentes import aplicar_estilo  # type: ignore
except ImportError:
    aplicar_estilo = lambda: None

# ====================================================
# CONFIGURAÇÃO DA PÁGINA — deve ser o primeiro comando st.*
# ====================================================
st.set_page_config(
    page_title="Rota Inicial",
    page_icon="🗺️",
    layout="wide",
)

# CORREÇÃO 3: setdefault APÓS set_page_config
st.session_state.setdefault("df_memoria",   None)
st.session_state.setdefault("dados_ativos", None)

# ====================================================
# CONSTANTES
# ====================================================
COL_TECNICO_LOGIN = "Login do Técnico"
COL_TECNICO_NOME  = "Recurso"
COL_TIPO_ATIV     = "Tipo de Atividade"
COL_TIPO_OS       = "Tipo de O.S"
COL_JANELA        = "Janela de Serviço"
COL_DATA          = "Data"
COL_NUM_WO        = "Número da WO"
COL_STATUS_ATIV   = "Status da Atividade"
COL_TOTAL_TAREFAS = "Total de tarefas"

MAPA_SEGMENTO: Dict[str, List[str]] = {
    "WO":       ["WO", "NOVO", "DOMICILIO", "DOMICÍLIO", "ND", "INSTALAÇÃO", "INSTALACAO"],
    "GPON":     ["GPON", "FIBRA"],
    "MIGRACAO": ["MIGRA", "MUDANÇA", "MUDANCA", "TROCA PACOTE"],
}

TURNOS: Dict[str, List[str]] = {
    "Manhã":    ["MANHÃ", "MANHA", "MATUTINO"],
    "Tarde I":  ["TARDE I", "TARDE 1", "TARDE1", "T1"],
    "Tarde II": ["TARDE II", "TARDE 2", "TARDE2", "T2", "VESPERTINO"],
}

# ====================================================
# CSS CORPORATIVO
# ====================================================
def _injetar_css_rota() -> None:
    st.markdown(
        """
        <style>
        .rota-wrapper { margin: 24px 0; font-family: 'Segoe UI', -apple-system, sans-serif; }

        .rota-titulo {
            background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
            color: white; font-weight: 800; font-size: 14px;
            text-align: center; padding: 10px 14px;
            border-top-left-radius: 8px; border-top-right-radius: 8px;
            letter-spacing: .5px; text-transform: uppercase;
            border-bottom: 2px solid #F59E0B;
        }

        table.rota-tab {
            width: 100%; border-collapse: separate; border-spacing: 0;
            background: white; box-shadow: 0 4px 12px rgba(0,0,0,.10);
            font-family: 'Segoe UI', sans-serif; font-size: 13px;
        }
        table.rota-tab th {
            background: linear-gradient(180deg,#1E3A8A 0%,#1E40AF 100%);
            color: white; font-weight: 700; font-size: 12px;
            text-transform: uppercase; letter-spacing: .5px;
            padding: 10px 8px; text-align: center;
            border-right: 1px solid rgba(255,255,255,.15);
        }
        table.rota-tab th.th-os     { background: linear-gradient(180deg,#FBBF24 0%,#F59E0B 100%); color:#1E293B; }
        table.rota-tab th.th-equipe { background: linear-gradient(180deg,#10B981 0%,#059669 100%); }
        table.rota-tab th.th-media  { background: linear-gradient(180deg,#F59E0B 0%,#D97706 100%); }

        table.rota-tab td {
            padding: 8px 10px; text-align: center;
            border-bottom: 1px solid #E2E8F0; color: #1F2937;
            font-variant-numeric: tabular-nums;
        }
        table.rota-tab td.col-monitor  { text-align:left; font-weight:600; padding-left:14px; color:#0F172A; }
        table.rota-tab td.col-os       { background:#FEF3C7; font-weight:700; color:#78350F; }
        table.rota-tab td.col-equipe   { background:#D1FAE5; font-weight:700; color:#065F46; }
        table.rota-tab td.col-media    { background:#F1F5F9; font-weight:700; color:#0F172A; }

        table.rota-tab tr.total-escalados td {
            background: linear-gradient(180deg,#1E40AF 0%,#1E3A8A 100%);
            color:white; font-weight:800; font-size:13px; border-top:2px solid #FBBF24;
        }
        table.rota-tab tr.total-escalados td.col-monitor { color:white; }
        table.rota-tab tr.total-escalados td.col-os      { background:#FBBF24; color:#1E293B; }
        table.rota-tab tr.total-escalados td.col-equipe  { background:#10B981; color:white; }
        table.rota-tab tr.total-escalados td.col-media   { background:#F59E0B; color:white; }

        table.rota-tab tr.total-montados td {
            background: linear-gradient(180deg,#38BDF8 0%,#0EA5E9 100%);
            color:white; font-weight:800; font-size:13px;
        }
        table.rota-tab tr.total-montados td.col-monitor { color:white; }
        table.rota-tab tr.total-montados td.col-os      { background:#FBBF24; color:#1E293B; }
        table.rota-tab tr.total-montados td.col-equipe  { background:#10B981; color:white; }
        table.rota-tab tr.total-montados td.col-media   { background:#F59E0B; color:white; }

        table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td         { background:#F9FAFB; }
        table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td.col-os  { background:#FEF3C7; }
        table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td.col-equipe { background:#D1FAE5; }
        table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td.col-media  { background:#E2E8F0; }

        .hero-rota {
            background: linear-gradient(135deg,#1E40AF 0%,#0EA5E9 100%);
            padding:28px 36px; border-radius:14px; color:white;
            box-shadow:0 8px 32px rgba(30,64,175,.25); margin-bottom:20px;
            position:relative; overflow:hidden;
        }
        .hero-rota::before {
            content:''; position:absolute; top:-50%; right:-10%;
            width:400px; height:400px; background:rgba(255,255,255,.06); border-radius:50%;
        }
        .hero-rota h1 {
            font-size:30px; font-weight:800; margin:0;
            letter-spacing:-.5px; position:relative; z-index:2;
            text-shadow:0 2px 4px rgba(0,0,0,.25);
        }
        .hero-rota p {
            font-size:14px; opacity:.92; margin:6px 0 0;
            font-weight:400; position:relative; z-index:2;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# UTILITÁRIOS
# ====================================================
def _encontrar_coluna(df: pd.DataFrame, candidatos: List[str]) -> Optional[str]:
    """Retorna o nome real da coluna se algum candidato existir."""
    cols_upper = {c.upper().strip(): c for c in df.columns}
    for cand in candidatos:
        resultado = cols_upper.get(cand.upper().strip())
        if resultado is not None:
            return resultado
    return None


def _classificar_segmento(valor: Any) -> Optional[str]:
    """Classifica em: WO, GPON, MIGRACAO ou None."""
    if pd.isna(valor):
        return None
    s = str(valor).upper().strip()
    # MIGRACAO primeiro (mais específico)
    if any(t in s for t in MAPA_SEGMENTO["MIGRACAO"]):
        return "MIGRACAO"
    if any(t in s for t in MAPA_SEGMENTO["GPON"]):
        return "GPON"
    if any(t in s for t in MAPA_SEGMENTO["WO"]):
        return "WO"
    return None


def _extrair_hora_inicio(janela: Any) -> Optional[int]:
    """Extrai a hora de início de uma janela de serviço."""
    if pd.isna(janela):
        return None
    s = str(janela).strip()

    # CORREÇÃO 4: re importado no topo, sem overhead de import repetido
    match = re.search(r"(\d{1,2}):\d{2}", s)
    if match:
        try:
            hora = int(match.group(1))
            if 0 <= hora <= 23:
                return hora
        except ValueError:
            pass

    # Tenta somente número
    match2 = re.search(r"\b(\d{1,2})\b", s)
    if match2:
        try:
            hora = int(match2.group(1))
            if 0 <= hora <= 23:
                return hora
        except ValueError:
            pass

    return None


def _classificar_turno(janela: Any) -> Optional[str]:
    """
    Classifica turno:
    - Manhã:    06–11
    - Tarde I:  12–14
    - Tarde II: 15–20
    """
    if pd.isna(janela):
        return None

    s = str(janela).upper().strip()

    # Verifica termos textuais primeiro
    for turno, termos in TURNOS.items():
        if any(t in s for t in termos):
            return turno

    # Fallback por horário
    hora = _extrair_hora_inicio(janela)
    if hora is None:
        return None

    if 6 <= hora <= 11:
        return "Manhã"
    if 12 <= hora <= 14:
        return "Tarde I"
    if 15 <= hora <= 20:
        return "Tarde II"

    return None


def _fmt_num(v: Any) -> str:
    try:
        return f"{int(v):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _fmt_media(v: Any) -> str:
    try:
        return f"{float(v):.2f}".replace(".", ",")
    except (ValueError, TypeError):
        return "0,00"


# ====================================================
# ENRIQUECE COM MONITOR VIA ATIVOS
# ====================================================
def enriquecer_com_monitor(df: pd.DataFrame) -> pd.DataFrame:
    """Faz join com a base de Ativos para trazer a coluna Monitor."""
    df_work = df.copy()

    # Se já existe coluna Monitor, retorna
    if _encontrar_coluna(df_work, ["Monitor"]):
        return df_work

    ativos = st.session_state.get("dados_ativos")
    if not isinstance(ativos, pd.DataFrame) or ativos.empty:
        df_work["Monitor"] = "SEM MONITOR"
        return df_work

    ativos_cols = {c.upper().strip(): c for c in ativos.columns}
    # CORREÇÃO 5: busca mais robusta das colunas de login e monitor
    col_login_ativos   = (
        ativos_cols.get("LOGIN")
        or ativos_cols.get("LOGIN DO TÉCNICO")
        or ativos_cols.get("LOGIN TÉCNICO")
    )
    col_monitor_ativos = ativos_cols.get("MONITOR")

    if not col_login_ativos or not col_monitor_ativos:
        df_work["Monitor"] = "SEM MONITOR"
        return df_work

    ativos_slim = (
        ativos[[col_login_ativos, col_monitor_ativos]]
        .drop_duplicates(subset=[col_login_ativos])
        .rename(columns={col_login_ativos: "_login_key", col_monitor_ativos: "Monitor"})
    )

    col_login_df = _encontrar_coluna(df_work, [COL_TECNICO_LOGIN, "LOGIN", "Recurso"])
    if not col_login_df:
        df_work["Monitor"] = "SEM MONITOR"
        return df_work

    df_work = df_work.merge(
        ativos_slim,
        left_on=col_login_df,
        right_on="_login_key",
        how="left",
    ).drop(columns=["_login_key"], errors="ignore")

    df_work["Monitor"] = df_work["Monitor"].fillna("SEM MONITOR")
    return df_work


# ====================================================
# MOTOR DE CÁLCULO
# ====================================================
def calcular_tabela_rota(
    df: pd.DataFrame,
    turno: Optional[str] = None,
    total_equipe_montada: Optional[int] = None,
) -> pd.DataFrame:
    """Calcula a tabela por Monitor: WO · GPON · OS · ND · Migração · Equipe · Média"""

    if df.empty:
        return pd.DataFrame()

    df_work = df.copy()

    col_mon    = _encontrar_coluna(df_work, ["Monitor", "MONITOR"])
    col_tec    = _encontrar_coluna(df_work, [COL_TECNICO_LOGIN, COL_TECNICO_NOME])
    col_tipo   = _encontrar_coluna(df_work, [COL_TIPO_ATIV, COL_TIPO_OS])
    col_janela = _encontrar_coluna(df_work, [COL_JANELA])

    if not col_mon or not col_tipo:
        st.warning("Colunas obrigatórias 'Monitor' ou 'Tipo de Atividade' não encontradas.")
        return pd.DataFrame()

    # Filtro de turno
    if turno and col_janela:
        df_work["_TURNO"] = df_work[col_janela].apply(_classificar_turno)
        df_work = df_work[df_work["_TURNO"] == turno].copy()

    if df_work.empty:
        return pd.DataFrame()

    df_work["_SEG"] = df_work[col_tipo].apply(_classificar_segmento)
    df_work["_MON"] = (
        df_work[col_mon].fillna("SEM MONITOR").astype(str).str.strip().str.upper()
    )

    # Remove monitores inválidos
    df_work = df_work[
        ~df_work["_MON"].isin({"NAN", "NÃO MAPEADO", "SEM MONITOR", "", "NAO MAPEADO"})
    ].copy()

    if df_work.empty:
        return pd.DataFrame()

    monitores = sorted(df_work["_MON"].unique())
    linhas: List[Dict[str, Any]] = []

    for mon in monitores:
        df_mon = df_work[df_work["_MON"] == mon]

        wo   = int((df_mon["_SEG"] == "WO").sum())
        gpon = int((df_mon["_SEG"] == "GPON").sum())
        mig  = int((df_mon["_SEG"] == "MIGRACAO").sum())
        nd   = wo  # ND = mesma quantidade que WO (instalações em domicílio)

        total_os = wo + gpon + mig
        equipe   = int(df_mon[col_tec].nunique()) if col_tec else 0
        media    = total_os / equipe if equipe > 0 else 0.0

        linhas.append({
            "Monitor":  mon,
            "WO":       wo,
            "GPON":     gpon,
            "OS":       total_os,
            "ND":       nd,
            "Migração": mig,
            "Equipe":   equipe,
            "Média":    media,
        })

    df_out = pd.DataFrame(linhas)

    # ── Totais ──────────────────────────────────
    total_wo           = int(df_out["WO"].sum())
    total_gpon         = int(df_out["GPON"].sum())
    total_os_geral     = int(df_out["OS"].sum())
    total_nd           = int(df_out["ND"].sum())
    total_mig          = int(df_out["Migração"].sum())
    total_eq_escalados = int(df_out["Equipe"].sum())

    total_eq_montados = (
        total_equipe_montada
        if total_equipe_montada is not None
        else (int(df_work[col_tec].nunique()) if col_tec else total_eq_escalados)
    )

    media_esc = total_os_geral / total_eq_escalados if total_eq_escalados > 0 else 0.0
    media_mon = total_os_geral / total_eq_montados  if total_eq_montados  > 0 else 0.0

    df_totais = pd.DataFrame([
        {
            "Monitor":  "Total Geral | Escalados",
            "WO": total_wo, "GPON": total_gpon, "OS": total_os_geral,
            "ND": total_nd, "Migração": total_mig,
            "Equipe": total_eq_escalados, "Média": media_esc,
        },
        {
            "Monitor":  "Total Geral | Montados",
            "WO": total_wo, "GPON": total_gpon, "OS": total_os_geral,
            "ND": total_nd, "Migração": total_mig,
            "Equipe": total_eq_montados, "Média": media_mon,
        },
    ])

    return pd.concat([df_out, df_totais], ignore_index=True)


# ====================================================
# RENDERIZAÇÃO HTML
# ====================================================
def render_tabela_rota(df: pd.DataFrame, titulo: str) -> str:
    """Gera HTML da tabela com visual corporativo."""
    if df.empty:
        return (
            f'<div class="rota-wrapper">'
            f'<div class="rota-titulo">{titulo}</div>'
            f'<table class="rota-tab"><tr><td colspan="8" '
            f'style="padding:20px;color:#64748B;text-align:center;">'
            f'Sem dados disponíveis para este turno.</td></tr></table></div>'
        )

    linhas_html = ""
    for _, row in df.iterrows():
        monitor     = str(row["Monitor"])
        classe_linha = ""

        if "Escalados" in monitor:
            classe_linha = "total-escalados"
        elif "Montados" in monitor:
            classe_linha = "total-montados"

        linhas_html += (
            f'<tr class="{classe_linha}">'
            f'<td class="col-monitor">{monitor}</td>'
            f'<td>{_fmt_num(row["WO"])}</td>'
            f'<td>{_fmt_num(row["GPON"])}</td>'
            f'<td class="col-os">{_fmt_num(row["OS"])}</td>'
            f'<td>{_fmt_num(row["ND"])}</td>'
            f'<td>{_fmt_num(row["Migração"])}</td>'
            f'<td class="col-equipe">{_fmt_num(row["Equipe"])}</td>'
            f'<td class="col-media">{_fmt_media(row["Média"])}</td>'
            f'</tr>'
        )

    return (
        f'<div class="rota-wrapper">'
        f'<div class="rota-titulo">{titulo}</div>'
        f'<table class="rota-tab">'
        f'<thead><tr>'
        f'<th style="width:32%;">Monitor</th>'
        f'<th>WO</th><th>GPON</th>'
        f'<th class="th-os">OS</th>'
        f'<th>ND</th><th>Migração</th>'
        f'<th class="th-equipe">Equipe</th>'
        f'<th class="th-media">Média</th>'
        f'</tr></thead>'
        f'<tbody>{linhas_html}</tbody>'
        f'</table></div>'
    )


# ====================================================
# APLICAÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    try:
        aplicar_estilo()
    except Exception:
        pass

    _injetar_css_rota()

    data_hoje = datetime.now().strftime("%d/%m/%Y")

    st.markdown(
        f"""
        <div class="hero-rota">
            <h1>🗺️ Rota Inicial</h1>
            <p>Distribuição de Ordens de Serviço por Monitor e Turno · {data_hoje}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("df_memoria") is None:
        st.warning("⚠️ **Nenhuma base carregada.**")
        st.info("👈 Volte ao **Dashboard Geral** no menu lateral e faça o upload.")
        return

    df_full: pd.DataFrame = st.session_state["df_memoria"].copy()

    if df_full.empty:
        st.warning("A base carregada está vazia.")
        return

    df_full = enriquecer_com_monitor(df_full)

    # ── Sidebar ──────────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros")

        col_data = _encontrar_coluna(df_full, [COL_DATA, "DATA"])
        data_selecionada: Any = None

        if col_data:
            try:
                df_full[col_data] = pd.to_datetime(
                    df_full[col_data], dayfirst=True, errors="coerce"
                )
                datas_unicas = sorted(df_full[col_data].dropna().dt.date.unique())
                if datas_unicas:
                    data_selecionada = st.selectbox(
                        "📅 Data",
                        options=["Todas"] + datas_unicas,
                        format_func=lambda x: (
                            "Todas as datas"
                            if x == "Todas"
                            else x.strftime("%d/%m/%Y")
                        ),
                        key="rota_data",
                    )
            except Exception as exc:
                st.caption(f"Não foi possível filtrar por data: {exc}")

        col_mon = _encontrar_coluna(df_full, ["Monitor", "MONITOR"])
        sel_mon = "Todos os Monitores"
        if col_mon:
            opcoes_mon = ["Todos os Monitores"] + sorted(
                str(x)
                for x in df_full[col_mon].dropna().unique()
                if str(x).upper() not in {"NAN", "SEM MONITOR", "NÃO MAPEADO", "NAO MAPEADO"}
            )
            sel_mon = st.selectbox("👔 Monitor", opcoes_mon, key="rota_mon")

        st.divider()

    # ── Aplica filtros ────────────────────────────────
    df = df_full.copy()

    if col_data and data_selecionada and data_selecionada != "Todas":
        df = df[df[col_data].dt.date == data_selecionada]

    if col_mon and sel_mon != "Todos os Monitores":
        df = df[df[col_mon] == sel_mon]

    if df.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    st.sidebar.caption(f"**Base filtrada:** {len(df):,} registros".replace(",", "."))

    # CORREÇÃO 6: verificação de tipo de data segura
    data_titulo = data_hoje
    if data_selecionada and data_selecionada != "Todas":
        try:
            data_titulo = data_selecionada.strftime("%d/%m/%Y")
        except AttributeError:
            data_titulo = str(data_selecionada)

    # ── Equipe montada total ──────────────────────────
    col_tec = _encontrar_coluna(df, [COL_TECNICO_LOGIN, COL_TECNICO_NOME])
    total_montada = int(df[col_tec].nunique()) if col_tec else 0

    # ── Tabela 1: Dia todo ────────────────────────────
    df_rota = calcular_tabela_rota(df, turno=None, total_equipe_montada=total_montada)
    st.markdown(render_tabela_rota(df_rota, f"Rota Inicial — {data_titulo}"), unsafe_allow_html=True)

    # ── Tabela 2: Manhã ───────────────────────────────
    df_manha = calcular_tabela_rota(df, turno="Manhã", total_equipe_montada=total_montada)
    st.markdown(render_tabela_rota(df_manha, f"Manhã — {data_titulo}"), unsafe_allow_html=True)

    # ── Tabela 3: Tarde I ─────────────────────────────
    df_tarde1 = calcular_tabela_rota(df, turno="Tarde I", total_equipe_montada=total_montada)
    st.markdown(render_tabela_rota(df_tarde1, f"Tarde I — {data_titulo}"), unsafe_allow_html=True)

    # ── Tabela 4: Tarde II ────────────────────────────
    df_tarde2 = calcular_tabela_rota(df, turno="Tarde II", total_equipe_montada=total_montada)
    st.markdown(render_tabela_rota(df_tarde2, f"Tarde II — {data_titulo}"), unsafe_allow_html=True)

    # ── Rodapé ────────────────────────────────────────
    st.markdown(
        f"""
        <div style="text-align:center;margin-top:32px;padding:16px;
             border-top:1px solid #E2E8F0;color:#94A3B8;font-size:12px;">
            <b style="color:#1E40AF;">Rota Inicial · Distribuição por Turno</b><br>
            Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()