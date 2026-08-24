"""
components/criterios.py
=======================
Módulo centralizado de critérios de classificação para o portal TOTALE.

CRITÉRIOS PRINCIPAIS:
    🔄 MIGRAÇÃO (AND — os 2 critérios juntos):
        1️⃣  TIPO O.S 1  contém  "MUDANCA DE PACOTE"
        2️⃣  FLAG_GPON   =       "Sim"

    🔦 FLAG_GPON (auto-gerado):
        HABILIDADE DE TRABALHO contém "PON(1/100)" → "Sim"

    🏠 NOVOS DOMICÍLIOS: TIPO O.S contém "ADESAO"

    🏢 PME:
        É Novos Domicílios E
        HABILIDADE DE TRABALHO contém "PME(1/100)"

ARQUITETURA:
    ✅ Regras de classificação
    ✅ Detecção de colunas
    ✅ Métricas consolidadas (baseadas em TOTAL DE TAREFAS)
    ✅ Painéis internos de UI
"""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st


# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════
VAZIOS_GERAIS: set[str] = {
    "", "NAN", "NONE", "NULL", "N/A", "NA",
    "NAO INFORMADO", "NÃO INFORMADO", "-",
    "SEM INFORMACAO", "SEM INFORMAÇÃO", ".", "..", "...",
}
VAZIOS_CONTRATO: set[str] = VAZIOS_GERAIS | {
    "0", "S/N", "SEM CONTRATO", "?", "??",
}


def _norm_str(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", errors="ignore")
        .decode("ascii")
        .upper()
        .strip()
    )


TERMO_MIGRACAO_OS:     str = _norm_str("MUDANCA DE PACOTE")
VALOR_FLAG_GPON_SIM:   str = "SIM"
TERMO_GPON_HABILIDADE: str = "PON(1/100)"
TERMO_PME_HABILIDADE:  str = "PME(1/100)"

TERMOS_ND:  Tuple[str, ...] = ("ADESAO",)
TERMOS_PME: Tuple[str, ...] = (TERMO_PME_HABILIDADE,)

CANDS_TIPO_OS_1: List[str] = [
    "TIPO O.S 1", "TIPO OS 1", "TIPO O.S. 1", "TIPO_OS_1", "TIPO_O_S_1",
]
CANDS_FLAG_GPON: List[str] = [
    "FLAG_GPON", "FLAG GPON", "FLAGGPON", "IS_GPON",
]
CANDS_CAPACIDADE: List[str] = [
    "CATEGORIAS DA CAPACIDADE", "CATEGORIA DA CAPACIDADE",
    "CATEGORIAS CAPACIDADE", "CATEGORIA CAPACIDADE", "CAPACIDADE",
]
CANDS_HABILIDADE: List[str] = [
    "HABILIDADE DE TRABALHO", "HABILIDADES DE TRABALHO",
    "HABILIDADE", "HABILIDADES", "SKILL", "SKILLS",
]


# ═══════════════════════════════════════════════════════════════════════
# NORMALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════
def normalizar_str(texto: str) -> str:
    return _norm_str(texto)


def norm_col_nome(nome: str) -> str:
    return (
        unicodedata.normalize("NFKD", nome)
        .encode("ascii", errors="ignore")
        .decode("ascii")
        .upper()
        .strip()
        .replace(".", "")
        .replace("_", " ")
    )


# ═══════════════════════════════════════════════════════════════════════
# DETECÇÃO DE COLUNAS
# ═══════════════════════════════════════════════════════════════════════
def detectar_cols_tipo(df: pd.DataFrame) -> List[str]:
    return [
        c for c in df.columns
        if "TIPO" in norm_col_nome(str(c))
        and ("OS" in norm_col_nome(str(c)) or "O S" in norm_col_nome(str(c)))
    ]


def detectar_col_tipo_os_1(df: pd.DataFrame) -> Optional[str]:
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_TIPO_OS_1:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "TIPO" in col_norm and ("OS" in col_norm or "O S" in col_norm):
            if col_norm.endswith("1") or col_norm.endswith(" 1"):
                return col_real
    return None


def detectar_col_flag_gpon(df: pd.DataFrame) -> Optional[str]:
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_FLAG_GPON:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "GPON" in col_norm and "FLAG" in col_norm:
            return col_real
    return None


def detectar_col_capacidade(df: pd.DataFrame) -> Optional[str]:
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_CAPACIDADE:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "CAPACIDADE" in col_norm:
            return col_real
    return None


def detectar_col_habilidade(df: pd.DataFrame) -> Optional[str]:
    for nome in ["HABILIDADE DE TRABALHO", "Habilidade de Trabalho",
                 "habilidade de trabalho", "HABILIDADES DE TRABALHO",
                 "HABILIDADE_DE_TRABALHO", "HABILIDADE"]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "HABILIDADE DE TRABALHO":
            return c
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_HABILIDADE:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for c in df.columns:
        if "HABIL" in str(c).upper():
            return c
    for c in df.columns:
        try:
            amostra = df[c].dropna().astype(str).head(100)
            if amostra.str.contains(r"PON\(1/100\)", na=False, regex=True).any():
                return c
        except Exception:
            continue
    return None


def detectar_col_status_atividade(df: pd.DataFrame) -> Optional[str]:
    for nome in ["STATUS DA ATIVIDADE", "Status da Atividade",
                 "status da atividade", "STATUS_DA_ATIVIDADE"]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "STATUS DA ATIVIDADE":
            return c
    alvo_norm = norm_col_nome("STATUS DA ATIVIDADE")
    for c in df.columns:
        if norm_col_nome(str(c)) == alvo_norm:
            return c
    for c in df.columns:
        cu = str(c).upper()
        if "STATUS" in cu and "ATIVIDADE" in cu:
            return c
    return None


def detectar_col_contrato(df: pd.DataFrame) -> Optional[str]:
    for nome in ["CONTRATO", "Contrato", "contrato"]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "CONTRATO":
            return c
    alvo_norm = norm_col_nome("CONTRATO")
    for c in df.columns:
        if norm_col_nome(str(c)) == alvo_norm:
            return c
    _EVITAR = {"STATUS", "DATA", "TIPO", "VALOR", "PLANO", "SITUACAO"}
    candidatas = [
        c for c in df.columns
        if "CONTRATO" in str(c).upper()
        and not any(e in str(c).upper() for e in _EVITAR)
    ]
    if candidatas:
        return min(candidatas, key=lambda x: len(str(x)))
    return None


# ═══════════════════════════════════════════════════════════════════════
# COLUNAS AUXILIARES
# ═══════════════════════════════════════════════════════════════════════
def criar_coluna_tipos_agrupados(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols_tipo = detectar_cols_tipo(df)

    if not cols_tipo:
        df["_TIPOS_OS_AGRUPADOS"] = ""
        df["_TIPOS_OS_SET"] = pd.Series(
            [frozenset() for _ in range(len(df))],
            index=df.index, dtype=object,
        )
        return df

    def _agrupar(row: pd.Series) -> Tuple[str, FrozenSet[str]]:
        raw, norm = set(), set()
        for col in cols_tipo:
            val = str(row.get(col, "")).strip()
            if not val or val.upper() in VAZIOS_GERAIS:
                continue
            vn = normalizar_str(val)
            if vn and vn not in VAZIOS_GERAIS:
                raw.add(val)
                norm.add(vn)
        return (" + ".join(sorted(raw)) if raw else ""), frozenset(norm)

    res = df[cols_tipo].apply(_agrupar, axis=1, result_type="expand")
    df["_TIPOS_OS_AGRUPADOS"] = res[0]
    df["_TIPOS_OS_SET"]       = res[1]
    return df


def criar_flag_gpon(df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str], int]:
    df = df.copy()

    col_ex = detectar_col_flag_gpon(df)
    if col_ex and col_ex != "FLAG_GPON":
        df = df.rename(columns={col_ex: "FLAG_GPON"})

    if "FLAG_GPON" in df.columns:
        n_sim = int(
            df["FLAG_GPON"].fillna("").astype(str).str.strip().str.upper()
            .eq(VALOR_FLAG_GPON_SIM).sum()
        )
        return df, None, n_sim

    col_hab = detectar_col_habilidade(df)
    if not col_hab:
        df["FLAG_GPON"] = "Não"
        return df, None, 0

    serie = df[col_hab].fillna("").astype(str).str.strip()
    serie_v = serie.where(~serie.str.upper().isin(VAZIOS_GERAIS), other="")
    mask = serie_v.str.contains(TERMO_GPON_HABILIDADE, na=False, regex=False)
    df["FLAG_GPON"] = np.where(mask, "Sim", "Não")
    return df, col_hab, int(mask.sum())


# ═══════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
def classificar_tipo_servico(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Classifica cada linha em Migração / Novos Domicílios / PME / Outros.

    Regras:
        🔄 Migração:
            TIPO O.S 1 contém MUDANCA DE PACOTE
            E FLAG_GPON = Sim

        🏠 Novos Domicílios:
            Alguma coluna TIPO O.S contém ADESAO

        🏢 PME:
            É Novos Domicílios
            E HABILIDADE DE TRABALHO contém PME(1/100)

    Precedência:
        Migração > PME > Novos Domicílios > Outros
    """
    df = criar_coluna_tipos_agrupados(df)
    df, _, _ = criar_flag_gpon(df)

    col_tipo_os_1 = detectar_col_tipo_os_1(df)
    col_flag_gpon = detectar_col_flag_gpon(df)
    col_hab       = detectar_col_habilidade(df)

    print(f"[criterios] TIPO O.S 1 : {col_tipo_os_1!r}")
    print(f"[criterios] FLAG_GPON  : {col_flag_gpon!r}")
    print(f"[criterios] HABILIDADE : {col_hab!r}")

    serie_tipo_os_1 = (
        df[col_tipo_os_1].fillna("").astype(str).map(normalizar_str)
        if col_tipo_os_1
        else pd.Series("", index=df.index, dtype=object)
    )
    serie_flag_gpon = (
        df[col_flag_gpon].fillna("").astype(str).map(normalizar_str)
        if col_flag_gpon
        else pd.Series("", index=df.index, dtype=object)
    )
    serie_habilidade = (
        df[col_hab].fillna("").astype(str).map(normalizar_str)
        if col_hab
        else pd.Series("", index=df.index, dtype=object)
    )

    # ── Migração: PACOTE E FLAG_GPON = Sim ────────────────────────────
    flag_pacote = serie_tipo_os_1.str.contains(
        TERMO_MIGRACAO_OS, na=False, regex=False
    )
    flag_gpon_sim = serie_flag_gpon.eq(VALOR_FLAG_GPON_SIM)
    flag_migracao = flag_pacote & flag_gpon_sim

    # ── Novos Domicílios: algum TIPO O.S contém ADESAO ────────────────
    def _tem_nd(tipo_set: FrozenSet[str]) -> bool:
        if not isinstance(tipo_set, (set, frozenset)):
            return False
        return any(termo in val for val in tipo_set for termo in TERMOS_ND)

    flag_nd = df["_TIPOS_OS_SET"].map(_tem_nd).fillna(False)

    # ── PME: É ND E HABILIDADE contém PME(1/100) ──────────────────────
    flag_hab_pme = serie_habilidade.str.contains(
        TERMO_PME_HABILIDADE, na=False, regex=False
    )
    flag_pme = flag_nd & flag_hab_pme

    # ── Resultado com precedência ─────────────────────────────────────
    resultado = pd.Series("Outros", index=df.index, dtype=object)
    resultado.loc[flag_nd]       = "Novos Domicílios"
    resultado.loc[flag_pme]      = "PME"
    resultado.loc[flag_migracao] = "Migração"

    print(f"[criterios] MUDANCA DE PACOTE : {int(flag_pacote.sum())}")
    print(f"[criterios] FLAG_GPON = Sim   : {int(flag_gpon_sim.sum())}")
    print(f"[criterios] HABILIDADE PME    : {int(flag_hab_pme.sum())}")
    print(f"[criterios] Migração (AND)    : {int(flag_migracao.sum())}")
    print(f"[criterios] PME (ND + HAB)    : {int(flag_pme.sum())}")
    print(f"[criterios] Distribuição      : {resultado.value_counts().to_dict()}")

    return df, resultado


# ═══════════════════════════════════════════════════════════════════════
# MÉTRICAS DOS CRITÉRIOS — BASEADAS EM TOTAL DE TAREFAS
# ═══════════════════════════════════════════════════════════════════════
def _serie_total_tarefas(df: pd.DataFrame) -> pd.Series:
    """Retorna série numérica de TOTAL DE TAREFAS (default = 1)."""
    if "TOTAL DE TAREFAS" not in df.columns:
        return pd.Series(1, index=df.index, dtype="float64")

    return (
        pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce")
        .fillna(1)
        .round()
        .clip(lower=0)
    )


def _mask_novos_domicilios(df: pd.DataFrame) -> pd.Series:
    """Máscara bruta de Novos Domicílios (algum TIPO O.S contém ADESAO)."""
    if "_TIPOS_OS_SET" in df.columns:

        def _tem_nd(tipo_set: Any) -> bool:
            if not isinstance(tipo_set, (set, frozenset)):
                return False
            return any(termo in val for val in tipo_set for termo in TERMOS_ND)

        return df["_TIPOS_OS_SET"].map(_tem_nd).fillna(False).astype(bool)

    cols_tipo = detectar_cols_tipo(df)
    mascara = pd.Series(False, index=df.index, dtype=bool)
    for col in cols_tipo:
        serie = df[col].fillna("").astype(str).map(normalizar_str)
        for termo in TERMOS_ND:
            mascara = mascara | serie.str.contains(termo, na=False, regex=False)
    return mascara


def extrair_metricas_criterios(df: pd.DataFrame) -> Dict[str, int]:
    """
    Extrai métricas usando TOTAL DE TAREFAS do DF já classificado.
    NÃO recalcula classificação.
    """
    if df is None or df.empty or "TIPO_SERVICO" not in df.columns:
        return {}

    tarefas = _serie_total_tarefas(df)
    tipo_final = df["TIPO_SERVICO"].fillna("").astype(str).str.strip()

    col_tipo_os_1 = detectar_col_tipo_os_1(df)
    col_flag_gpon = detectar_col_flag_gpon(df)
    col_hab       = detectar_col_habilidade(df)

    serie_tipo_os_1 = (
        df[col_tipo_os_1].fillna("").astype(str).map(normalizar_str)
        if col_tipo_os_1
        else pd.Series("", index=df.index, dtype=object)
    )
    serie_flag_gpon = (
        df[col_flag_gpon].fillna("").astype(str).map(normalizar_str)
        if col_flag_gpon
        else pd.Series("", index=df.index, dtype=object)
    )
    serie_habilidade = (
        df[col_hab].fillna("").astype(str).map(normalizar_str)
        if col_hab
        else pd.Series("", index=df.index, dtype=object)
    )

    # ── Máscaras individuais ──────────────────────────────────────────
    flag_pacote   = serie_tipo_os_1.str.contains(TERMO_MIGRACAO_OS, na=False, regex=False)
    flag_gpon_sim = serie_flag_gpon.eq(VALOR_FLAG_GPON_SIM)
    flag_pon      = serie_habilidade.str.contains(TERMO_GPON_HABILIDADE, na=False, regex=False)
    flag_nd       = _mask_novos_domicilios(df)
    flag_hab_pme  = serie_habilidade.str.contains(TERMO_PME_HABILIDADE, na=False, regex=False)

    flag_and_mig = flag_pacote & flag_gpon_sim
    flag_and_pme = flag_nd & flag_hab_pme

    def _soma(mask: pd.Series) -> int:
        return int(tarefas[mask.fillna(False)].sum())

    return {
        # Totais
        "total":           int(tarefas.sum()),
        "total_registros": int(len(df)),

        # Classificação final
        "migracao":         _soma(tipo_final.eq("Migração")),
        "novos_domicilios": _soma(tipo_final.eq("Novos Domicílios")),
        "pme":              _soma(tipo_final.eq("PME")),
        "outros":           _soma(tipo_final.eq("Outros")),

        # Critérios de Migração
        "criterio_pacote":         _soma(flag_pacote),
        "criterio_gpon_sim":       _soma(flag_gpon_sim),
        "criterio_habilidade_pon": _soma(flag_pon),
        "criterio_and_migracao":   _soma(flag_and_mig),

        # Critérios de ND / PME
        "criterio_nd_adesao":      _soma(flag_nd),
        "criterio_habilidade_pme": _soma(flag_hab_pme),
        "criterio_and_pme":        _soma(flag_and_pme),
    }


# ═══════════════════════════════════════════════════════════════════════
# PAINEL INTERNO — CRITÉRIOS DE CLASSIFICAÇÃO
# ═══════════════════════════════════════════════════════════════════════
def render_painel_criterios(df: pd.DataFrame) -> None:
    """
    Renderiza o painel oficial de critérios.
    Valores baseados em soma de TOTAL DE TAREFAS.
    """
    metricas = extrair_metricas_criterios(df)

    if not metricas:
        st.warning("⚠️ Base ainda não classificada. `TIPO_SERVICO` ausente.")
        return

    total_tarefas   = metricas["total"]
    total_registros = metricas["total_registros"]

    def fmt(v: int) -> str:
        return f"{int(v):,}".replace(",", ".")

    def pct(v: int) -> str:
        if total_tarefas <= 0:
            return "0,0%"
        return f"{(v / total_tarefas) * 100:.1f}%".replace(".", ",")

    def card_principal(col, emoji, titulo, valor, fundo, borda, texto, numero):
        col.markdown(
            f'<div style="background:{fundo};border-left:4px solid {borda};'
            f'border-radius:8px;padding:15px 16px;min-height:112px;">'
            f'<div style="font-size:11px;font-weight:700;color:{texto};'
            f'text-transform:uppercase;letter-spacing:0.4px;">'
            f'{emoji} {titulo}</div>'
            f'<div style="font-size:28px;font-weight:800;color:{numero};'
            f'line-height:1.15;margin-top:7px;">{fmt(valor)}</div>'
            f'<div style="font-size:11px;color:#475569;margin-top:3px;">'
            f'{pct(valor)} das tarefas</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    def card_criterio(col, emoji, titulo, valor, fundo, borda, texto, numero):
        col.markdown(
            f'<div style="background:{fundo};border-left:3px solid {borda};'
            f'border-radius:8px;padding:13px 14px;min-height:87px;">'
            f'<div style="font-size:10px;font-weight:700;color:{texto};'
            f'text-transform:uppercase;letter-spacing:0.25px;">'
            f'{emoji} {titulo}</div>'
            f'<div style="font-size:22px;font-weight:800;color:{numero};'
            f'line-height:1.15;margin-top:6px;">{fmt(valor)}</div>'
            f'<div style="font-size:10px;color:#64748B;margin-top:2px;">'
            f'{pct(valor)} das tarefas</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    tab_painel, tab_detalhes = st.tabs([
        "📊 Painel de Critérios",
        "🔎 Regras e Diagnóstico",
    ])

    # ────────────────────────────────────────────────────────────────
    # ABA 1 — PAINEL
    # ────────────────────────────────────────────────────────────────
    with tab_painel:
        st.markdown(
            f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;'
            f'border-radius:10px;padding:14px 16px;margin-bottom:16px;">'
            f'<div style="font-size:17px;font-weight:800;color:#0F172A;">'
            f'📊 Critérios de Classificação</div>'
            f'<div style="font-size:12px;color:#64748B;margin-top:4px;">'
            f'Base consolidada: <b>{fmt(total_tarefas)}</b> tarefas '
            f'em <b>{fmt(total_registros)}</b> registros importados.'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        st.caption(
            "Os segmentos abaixo representam a classificação final da base. "
            "Os critérios individuais podem se sobrepor entre si."
        )

        st.markdown("#### 📦 Distribuição Final por Segmento")

        c1, c2, c3, c4 = st.columns(4)
        card_principal(c1, "🔄", "Migração", metricas["migracao"],
                       "#EFF6FF", "#0369A1", "#0369A1", "#0C4A6E")
        card_principal(c2, "🏠", "Novos Domicílios", metricas["novos_domicilios"],
                       "#F0FDF4", "#16A34A", "#15803D", "#14532D")
        card_principal(c3, "🏢", "PME", metricas["pme"],
                       "#FAF5FF", "#7C3AED", "#6D28D9", "#4C1D95")
        card_principal(c4, "⚪", "Outros", metricas["outros"],
                       "#F8FAFC", "#64748B", "#475569", "#334155")

        st.markdown("---")
        st.markdown("#### 🔄 Critérios Individuais — Migração")

        m1, m2, m3 = st.columns(3)
        card_criterio(m1, "1️⃣", "Mudança de Pacote", metricas["criterio_pacote"],
                      "#FEF3C7", "#F59E0B", "#92400E", "#78350F")
        card_criterio(m2, "2️⃣", "FLAG_GPON = Sim", metricas["criterio_gpon_sim"],
                      "#E0F2FE", "#0284C7", "#0369A1", "#0C4A6E")
        card_criterio(m3, "✅", "AND — Migração", metricas["criterio_and_migracao"],
                      "#DBEAFE", "#1D4ED8", "#1E40AF", "#1E3A8A")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🏠🏢 Critérios Individuais — Novos Domicílios e PME")

        p1, p2, p3 = st.columns(3)
        card_criterio(p1, "🏠", "ADESAO em TIPO O.S", metricas["criterio_nd_adesao"],
                      "#F0FDF4", "#16A34A", "#15803D", "#14532D")
        card_criterio(p2, "🏢", "Habilidade PME(1/100)", metricas["criterio_habilidade_pme"],
                      "#FAF5FF", "#7C3AED", "#6D28D9", "#4C1D95")
        card_criterio(p3, "✅", "AND — PME", metricas["criterio_and_pme"],
                      "#EDE9FE", "#8B5CF6", "#5B21B6", "#4C1D95")

        st.markdown("<br>", unsafe_allow_html=True)
        st.info(
            f"🔦 HABILIDADE contendo `{TERMO_GPON_HABILIDADE}`: "
            f"**{fmt(metricas['criterio_habilidade_pon'])} tarefas**."
        )

    # ────────────────────────────────────────────────────────────────
    # ABA 2 — REGRAS E DIAGNÓSTICO
    # ────────────────────────────────────────────────────────────────
    with tab_detalhes:
        st.markdown("### 📋 Regras Oficiais de Classificação")

        regras = pd.DataFrame([
            {"Classificação": "🔄 Migração",
             "Regra": "TIPO O.S 1 contém MUDANCA DE PACOTE E FLAG_GPON = Sim"},
            {"Classificação": "🔦 FLAG_GPON",
             "Regra": "HABILIDADE DE TRABALHO contém PON(1/100) → Sim"},
            {"Classificação": "🏠 Novos Domicílios",
             "Regra": "Alguma coluna TIPO O.S contém ADESAO"},
            {"Classificação": "🏢 PME",
             "Regra": "É Novos Domicílios E HABILIDADE DE TRABALHO contém PME(1/100)"},
            {"Classificação": "⚪ Outros",
             "Regra": "Não atende aos critérios acima."},
        ])
        st.dataframe(regras, hide_index=True, use_container_width=True)

        st.markdown("---")
        st.markdown("### 🔗 Colunas Detectadas")

        col_tipo_os_1 = detectar_col_tipo_os_1(df)
        col_flag_gpon = detectar_col_flag_gpon(df)
        col_hab       = detectar_col_habilidade(df)

        deteccao = pd.DataFrame([
            {"Critério": "TIPO O.S 1",
             "Coluna Detectada": col_tipo_os_1 or "Não encontrada",
             "Status": "✅" if col_tipo_os_1 else "❌"},
            {"Critério": "FLAG_GPON",
             "Coluna Detectada": col_flag_gpon or "Não encontrada",
             "Status": "✅" if col_flag_gpon else "❌"},
            {"Critério": "HABILIDADE DE TRABALHO",
             "Coluna Detectada": col_hab or "Não encontrada",
             "Status": "✅" if col_hab else "❌"},
        ])
        st.dataframe(deteccao, hide_index=True, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📊 Distribuição por TIPO_SERVICO")

        tarefas = _serie_total_tarefas(df)
        distribuicao = (
            df.assign(
                _TAREFAS=tarefas,
                _TIPO_FINAL=df["TIPO_SERVICO"].fillna("Outros"),
            )
            .groupby("_TIPO_FINAL", dropna=False)
            .agg(Tarefas=("_TAREFAS", "sum"),
                 Registros=("_TIPO_FINAL", "size"))
            .reset_index()
            .rename(columns={"_TIPO_FINAL": "Segmento"})
            .sort_values("Tarefas", ascending=False)
            .reset_index(drop=True)
        )
        distribuicao["Tarefas"] = distribuicao["Tarefas"].astype(int)
        distribuicao["% das Tarefas"] = np.where(
            total_tarefas > 0,
            distribuicao["Tarefas"] / total_tarefas,
            0,
        )
        st.dataframe(
            distribuicao.style.format({
                "Tarefas":       "{:,.0f}",
                "Registros":     "{:,.0f}",
                "% das Tarefas": "{:.1%}",
            }),
            hide_index=True, use_container_width=True,
        )

        st.markdown("---")
        st.markdown("### 🔬 Diagnóstico — Migração")

        d1, d2, d3 = st.columns(3)
        d1.metric("1️⃣ Mudança de Pacote",
                  fmt(metricas["criterio_pacote"]),
                  help="Soma das tarefas com TIPO O.S 1 = MUDANCA DE PACOTE.")
        d2.metric("2️⃣ FLAG_GPON = Sim",
                  fmt(metricas["criterio_gpon_sim"]),
                  help="Soma das tarefas com FLAG_GPON = Sim.")
        d3.metric("✅ AND — Migração",
                  fmt(metricas["criterio_and_migracao"]),
                  help="Tarefas que atendem os 2 critérios juntos.")

        if metricas["criterio_and_migracao"] == 0:
            if metricas["criterio_pacote"] == 0:
                st.error("❌ Nenhuma tarefa com MUDANCA DE PACOTE em TIPO O.S 1.")
            elif metricas["criterio_gpon_sim"] == 0:
                st.error("❌ Nenhuma tarefa com FLAG_GPON = Sim.")
            else:
                st.warning(
                    "⚠️ Existem tarefas com Mudança de Pacote e tarefas GPON, "
                    "mas nenhum registro atende aos dois juntos."
                )
        else:
            st.success(
                f"✅ {fmt(metricas['criterio_and_migracao'])} tarefas "
                "atendem simultaneamente aos critérios de Migração."
            )

        st.markdown("---")
        st.markdown("### 🔬 Diagnóstico — PME")

        p1, p2, p3 = st.columns(3)
        p1.metric("🏠 ADESAO / ND",
                  fmt(metricas["criterio_nd_adesao"]),
                  help="Soma das tarefas em que algum TIPO O.S contém ADESAO.")
        p2.metric("🏢 PME(1/100)",
                  fmt(metricas["criterio_habilidade_pme"]),
                  help="Soma das tarefas com HABILIDADE contendo PME(1/100).")
        p3.metric("✅ AND — PME",
                  fmt(metricas["criterio_and_pme"]),
                  help="Tarefas ND com HABILIDADE PME(1/100).")

        if metricas["criterio_and_pme"] == 0:
            if metricas["criterio_nd_adesao"] == 0:
                st.warning("⚠️ Nenhuma tarefa identificada como Novos Domicílios / ADESAO.")
            elif metricas["criterio_habilidade_pme"] == 0:
                st.warning("⚠️ Nenhuma tarefa com PME(1/100) em HABILIDADE DE TRABALHO.")
            else:
                st.warning(
                    "⚠️ Existem tarefas ND e tarefas com habilidade PME, "
                    "mas nenhum registro atende aos dois juntos."
                )
        else:
            st.success(
                f"✅ {fmt(metricas['criterio_and_pme'])} tarefas "
                "atendem simultaneamente aos critérios de PME."
            )


# ═══════════════════════════════════════════════════════════════════════
# COMPONENTES AUXILIARES DE UI
# ═══════════════════════════════════════════════════════════════════════
def render_debug_criterios(df_full: pd.DataFrame, expanded: bool = False) -> None:
    """Expander de diagnóstico técnico dos critérios."""
    with st.expander("🔎 Diagnóstico Técnico de Critérios", expanded=expanded):
        col_tipo = detectar_col_tipo_os_1(df_full)
        col_gpon = detectar_col_flag_gpon(df_full)
        col_hab  = detectar_col_habilidade(df_full)

        st.markdown("**🔗 Colunas detectadas:**")
        cc1, cc2 = st.columns(2)
        cc1.markdown(
            f"**TIPO O.S 1:** " + (f"✅ `{col_tipo}`" if col_tipo else "❌") +
            f"\n\n**FLAG_GPON:** " + (f"✅ `{col_gpon}`" if col_gpon else "❌")
        )
        cc2.markdown(
            f"**HABILIDADE:** " + (f"✅ `{col_hab}`" if col_hab else "❌")
        )

        st.markdown("---")
        st.markdown(
            "**📋 Regras:**\n\n"
            "🔄 **Migração**: `TIPO O.S 1` contém `MUDANCA DE PACOTE` E `FLAG_GPON = Sim`\n\n"
            "🔦 **FLAG_GPON**: `HABILIDADE` contém `PON(1/100)`\n\n"
            "🏠 **Novos Domicílios**: TIPO O.S contém `ADESAO`\n\n"
            "🏢 **PME**: é ND + `HABILIDADE` contém `PME(1/100)`"
        )

        if "TIPO_SERVICO" in df_full.columns:
            st.markdown("---")
            st.markdown("**📊 Distribuição:**")
            dist = df_full["TIPO_SERVICO"].value_counts().reset_index()
            dist.columns = ["Segmento", "Registros"]
            st.dataframe(dist, hide_index=True, use_container_width=True)


def render_card_destaque_migracao() -> None:
    st.markdown(
        """
<div style="background:linear-gradient(135deg,#0C4A6E 0%,#0369A1 50%,#0284C7 100%);
            padding:20px 26px;border-radius:12px;color:white;
            box-shadow:0 6px 24px rgba(12,74,110,0.30);margin-bottom:20px;
            border-left:5px solid #FBBF24;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
        <span style="font-size:26px;">🔄</span>
        <span style="font-size:18px;font-weight:800;">CRITÉRIO DE MIGRAÇÃO</span>
        <span style="background:rgba(255,255,255,0.20);padding:3px 10px;
                     border-radius:12px;font-size:10px;font-weight:700;">
            AND — 2 critérios juntos
        </span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
        <div style="background:rgba(255,255,255,0.10);padding:12px 16px;border-radius:8px;">
            1️⃣ <code>TIPO O.S 1</code> contém <b>"MUDANCA DE PACOTE"</b>
        </div>
        <div style="background:rgba(255,255,255,0.10);padding:12px 16px;border-radius:8px;">
            2️⃣ <code>FLAG_GPON</code> = <b>"Sim"</b>
        </div>
    </div>
    <div style="margin-top:12px;padding:10px;background:rgba(251,191,36,0.15);
                border-radius:6px;font-size:12px;color:#FEF3C7;">
        🔦 <b>FLAG_GPON</b> auto: HABILIDADE contém <b>PON(1/100)</b>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_lista_colunas(df: pd.DataFrame, expanded: bool = False) -> None:
    if df.empty:
        return
    with st.expander("📋 Colunas da Base", expanded=expanded):
        df_cols = pd.DataFrame({
            "#":      range(1, len(df.columns) + 1),
            "Coluna": df.columns.tolist(),
            "Tipo":   [str(df[c].dtype) for c in df.columns],
        })
        st.dataframe(df_cols, hide_index=True, use_container_width=True,
                     height=min(600, 40 + len(df_cols) * 35))
        st.caption(
            f"Total: **{len(df.columns)} colunas** · "
            f"**{len(df):,} registros**".replace(",", ".")
        )


__all__ = [
    "VAZIOS_GERAIS", "VAZIOS_CONTRATO",
    "TERMO_MIGRACAO_OS", "VALOR_FLAG_GPON_SIM",
    "TERMO_GPON_HABILIDADE", "TERMO_PME_HABILIDADE",
    "TERMOS_ND", "TERMOS_PME",
    "normalizar_str", "norm_col_nome",
    "detectar_cols_tipo", "detectar_col_tipo_os_1",
    "detectar_col_flag_gpon", "detectar_col_capacidade",
    "detectar_col_habilidade", "detectar_col_status_atividade",
    "detectar_col_contrato",
    "criar_coluna_tipos_agrupados", "criar_flag_gpon",
    "classificar_tipo_servico",
    "extrair_metricas_criterios",
    "render_painel_criterios",
    "render_debug_criterios",
    "render_card_destaque_migracao",
    "render_lista_colunas",
]