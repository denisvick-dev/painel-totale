# components/criterios.py
from __future__ import annotations

import unicodedata
from typing import Any, Final

import numpy as np
import pandas as pd
import streamlit as st

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════
VAZIOS_GERAIS: set[str] = {
    "",
    "NAN",
    "NONE",
    "NULL",
    "N/A",
    "NA",
    "NAO INFORMADO",
    "NÃO INFORMADO",
    "-",
    "SEM INFORMACAO",
    "SEM INFORMAÇÃO",
    ".",
    "..",
    "...",
}

VAZIOS_CONTRATO: set[str] = {"", "NULL", "NAN", "NONE"}

# ═══════════════════════════════════════════════════════════════════════
# CRITÉRIOS DE CLASSIFICAÇÃO
# ═══════════════════════════════════════════════════════════════════════
# 🏠 Novos Domicílios: TIPO O.S 1 contém "ADESAO", "INSTALACAO", etc.
# 🔄 Migração: TIPO O.S 1 contém "MUDANCA DE PACOTE" + Habilidade contém "PON"
# 🏢 PME: Novos Domicílios + Habilidade contém "PME"
# ═══════════════════════════════════════════════════════════════════════

TERMOS_ND: tuple[str, ...] = (
    "ADESAO",
    "ADESÃO",
    "ADESA",
    "NOVO",
    "INSTALACAO",
    "INSTALAÇÃO",
    "INST",
    "NOVA",
    "NOVO DOMICILIO",
    "NOVO DOMICÍLIO",
    "PRIMEIRA",
    "1 VIA",
    "PRIMEIRO ACESSO",
)
TERMO_MIGRACAO_OS: Final[str] = "MUDANCA DE PACOTE"
TERMO_GPON_HABILIDADE: Final[str] = "PON"
TERMO_PME_HABILIDADE: Final[str] = "PME"
VALOR_FLAG_GPON_SIM: Final[str] = "SIM"

TERMOS_PME: tuple[str, ...] = (TERMO_PME_HABILIDADE,)

CANDS_TIPO_OS_1: list[str] = [
    "TIPO O.S 1",
    "TIPO OS 1",
    "TIPO O.S. 1",
    "TIPO_OS_1",
    "TIPO_O_S_1",
    "TIPOOS1",
    "TIPO OS",
    "TIPO O.S",
    "TIPO_DE_OS",
    "TIPO DE OS",
]
CANDS_FLAG_GPON: list[str] = [
    "FLAG_GPON",
    "FLAG GPON",
    "FLAGGPON",
    "IS_GPON",
]
CANDS_HABILIDADE: list[str] = [
    "HABILIDADE DE TRABALHO",
    "HABILIDADES DE TRABALHO",
    "HABILIDADE",
    "HABILIDADES",
    "SKILL",
    "SKILLS",
    "HABILIDADE_TECNICA",
    "HABILIDADE TÉCNICA",
]


def _norm_str(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", errors="ignore")
        .decode("ascii")
        .upper()
        .strip()
    )


def normalizar_str(texto: str) -> str:
    return _norm_str(texto)


def norm_col_nome(nome: str) -> str:
    return (
        unicodedata.normalize("NFKD", str(nome))
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
def detectar_col_tipo_os_1(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None

    cols_norm = {norm_col_nome(str(c)): str(c) for c in df.columns}

    # 1. Busca exata
    for cand in CANDS_TIPO_OS_1:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]

    # 2. Busca parcial (TIPO + OS + 1)
    for col_norm, col_real in cols_norm.items():
        if "TIPO" in col_norm and ("OS" in col_norm or "O S" in col_norm):
            if col_norm.endswith("1") or col_norm.endswith(" 1") or " 1 " in col_norm:
                return col_real

    # 3. Busca alternativa (qualquer coluna com TIPO e OS)
    for col_norm, col_real in cols_norm.items():
        if "TIPO" in col_norm and "OS" in col_norm:
            return col_real

    # 4. Busca por colunas de "TIPO" genéricas
    for col_norm, col_real in cols_norm.items():
        if "TIPO" in col_norm and "SERVICO" not in col_norm:
            return col_real

    return None


def detectar_col_flag_gpon(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    cols_norm = {norm_col_nome(str(c)): str(c) for c in df.columns}
    for cand in CANDS_FLAG_GPON:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "GPON" in col_norm and "FLAG" in col_norm:
            return col_real
    return None


def detectar_col_habilidade(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    cols_norm = {norm_col_nome(str(c)): str(c) for c in df.columns}
    for cand in CANDS_HABILIDADE:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "HABILIDAD" in col_norm or "SKILL" in col_norm:
            return col_real
    return None


# ═══════════════════════════════════════════════════════════════════════
# COLUNAS AUXILIARES
# ═══════════════════════════════════════════════════════════════════════
def criar_coluna_tipos_agrupados(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_TIPOS_OS_SET"] = pd.Series(
        [frozenset() for _ in range(len(df))],
        index=df.index,
        dtype=object,
    )
    df["_TIPOS_OS_AGRUPADOS"] = ""
    return df


def criar_flag_gpon(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None, int]:
    df = df.copy()
    col_ex = detectar_col_flag_gpon(df)
    if col_ex and col_ex != "FLAG_GPON":
        df = df.rename(columns={col_ex: "FLAG_GPON"})

    if "FLAG_GPON" in df.columns:
        n_sim = int(
            df["FLAG_GPON"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .eq(VALOR_FLAG_GPON_SIM)
            .sum()
        )
        return df, None, n_sim

    col_hab = detectar_col_habilidade(df)
    if not col_hab:
        df["FLAG_GPON"] = "Não"
        return df, None, 0

    serie = df[col_hab].fillna("").astype(str).str.strip()
    mask = serie.str.upper().str.contains(TERMO_GPON_HABILIDADE, na=False, regex=False)
    df["FLAG_GPON"] = np.where(mask, "Sim", "Não")
    return df, col_hab, int(mask.sum())


# ═══════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
def classificar_tipo_servico(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    df = df.copy()
    df = criar_coluna_tipos_agrupados(df)
    df, _, _ = criar_flag_gpon(df)

    col_tipo_os_1 = detectar_col_tipo_os_1(df)
    col_hab = detectar_col_habilidade(df)

    # Normalização das séries para ASCII sem acentos
    serie_tipo_os_1 = (
        df[col_tipo_os_1].fillna("").astype(str).map(_norm_str)
        if col_tipo_os_1
        else pd.Series("", index=df.index, dtype=object)
    )
    serie_habilidade = (
        df[col_hab].fillna("").astype(str).map(_norm_str)
        if col_hab
        else pd.Series("", index=df.index, dtype=object)
    )

    # ─────────────────────────────────────────────────────────────────
    # CRITÉRIO 1: NOVOS DOMICÍLIOS (Iterativo com regex=False para segurança)
    # ─────────────────────────────────────────────────────────────────
    flag_nd = pd.Series(False, index=df.index)
    for termo in TERMOS_ND:
        termo_norm = _norm_str(termo)
        if termo_norm:
            flag_nd |= serie_tipo_os_1.str.contains(termo_norm, na=False, regex=False)

    # ─────────────────────────────────────────────────────────────────
    # CRITÉRIO 2: MIGRAÇÃO (TIPO O.S 1 = MUDANCA DE PACOTE + Habilidade = PON)
    # ─────────────────────────────────────────────────────────────────
    termo_mig_norm = _norm_str(TERMO_MIGRACAO_OS)
    termo_pon_norm = _norm_str(TERMO_GPON_HABILIDADE)

    flag_migracao_tipo = serie_tipo_os_1.str.contains(
        termo_mig_norm, na=False, regex=False
    )
    flag_hab_pon = serie_habilidade.str.contains(termo_pon_norm, na=False, regex=False)
    flag_migracao = flag_migracao_tipo & flag_hab_pon

    # ─────────────────────────────────────────────────────────────────
    # CRITÉRIO 3: PME (Novos Domicílios + Habilidade = PME)
    # ─────────────────────────────────────────────────────────────────
    termo_pme_norm = _norm_str(TERMO_PME_HABILIDADE)
    flag_hab_pme = serie_habilidade.str.contains(termo_pme_norm, na=False, regex=False)
    flag_pme = flag_nd & flag_hab_pme

    # ─────────────────────────────────────────────────────────────────
    # APLICAÇÃO DA LÓGICA DE PRIORIDADE
    # ─────────────────────────────────────────────────────────────────
    tipo = pd.Series("Outros", index=df.index, dtype=object)
    tipo[flag_nd] = "Novos Domicílios"
    tipo[flag_migracao] = "Migração"
    tipo[flag_pme] = "PME"  # PME sobrepõe ND se houver habilidade PME

    df["TIPO_SERVICO"] = tipo
    return df, tipo


# ═══════════════════════════════════════════════════════════════════════
# MÉTRICAS DOS CRITÉRIOS
# ═══════════════════════════════════════════════════════════════════════
def _serie_total_tarefas(df: pd.DataFrame) -> pd.Series:
    if "TOTAL DE TAREFAS" not in df.columns:
        return pd.Series(1, index=df.index, dtype="float64")
    return (
        pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce")
        .fillna(1)
        .round()
        .clip(lower=0)
    )


def extrair_metricas_criterios(df: pd.DataFrame) -> dict[str, int]:
    if df is None or df.empty or "TIPO_SERVICO" not in df.columns:
        return {}

    tarefas = _serie_total_tarefas(df)
    tipo_final = df["TIPO_SERVICO"].fillna("").astype(str).str.strip()

    col_tipo_os_1 = detectar_col_tipo_os_1(df)
    col_hab = detectar_col_habilidade(df)

    serie_tipo_os_1 = (
        df[col_tipo_os_1].fillna("").astype(str).map(_norm_str)
        if col_tipo_os_1
        else pd.Series("", index=df.index)
    )
    serie_habilidade = (
        df[col_hab].fillna("").astype(str).map(_norm_str)
        if col_hab
        else pd.Series("", index=df.index)
    )

    # Flag ND Corrigida
    flag_nd = pd.Series(False, index=df.index)
    for termo in TERMOS_ND:
        termo_norm = _norm_str(termo)
        if termo_norm:
            flag_nd |= serie_tipo_os_1.str.contains(termo_norm, na=False, regex=False)

    flag_migracao_tipo = serie_tipo_os_1.str.contains(
        _norm_str(TERMO_MIGRACAO_OS), na=False, regex=False
    )
    flag_hab_pon = serie_habilidade.str.contains(
        _norm_str(TERMO_GPON_HABILIDADE), na=False, regex=False
    )
    flag_hab_pme = serie_habilidade.str.contains(
        _norm_str(TERMO_PME_HABILIDADE), na=False, regex=False
    )

    flag_migracao = flag_migracao_tipo & flag_hab_pon
    flag_pme = flag_nd & flag_hab_pme

    def _soma(mask: pd.Series) -> int:
        return int(tarefas[mask.fillna(False)].sum())

    return {
        "total": int(tarefas.sum()),
        "total_registros": len(df),
        "migracao": _soma(tipo_final.eq("Migração")),
        "novos_domicilios": _soma(tipo_final.eq("Novos Domicílios")),
        "pme": _soma(tipo_final.eq("PME")),
        "outros": _soma(tipo_final.eq("Outros")),
        "criterio_adesao": _soma(flag_nd),
        "criterio_mudanca_pacote": _soma(flag_migracao_tipo),
        "criterio_habilidade_pon": _soma(flag_hab_pon),
        "criterio_and_migracao": _soma(flag_migracao),
        "criterio_habilidade_pme": _soma(flag_hab_pme),
        "criterio_and_pme": _soma(flag_pme),
    }


# ═══════════════════════════════════════════════════════════════════════
# PAINEL INTERNO
# ═══════════════════════════════════════════════════════════════════════
def render_painel_criterios(df: pd.DataFrame) -> None:
    metricas = extrair_metricas_criterios(df)

    if not metricas:
        st.warning("⚠️ Base ainda não classificada. `TIPO_SERVICO` ausente.")
        return

    total_tarefas = metricas["total"]
    total_registros = metricas["total_registros"]

    def fmt(v: int) -> str:
        return f"{int(v):,}".replace(",", ".")

    def pct(v: int) -> str:
        if total_tarefas <= 0:
            return "0,0%"
        return f"{(v / total_tarefas) * 100:.1f}%".replace(".", ",")

    st.markdown(
        f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;'
        f'border-radius:10px;padding:14px 16px;margin-bottom:16px;">'
        f'<div style="font-size:17px;font-weight:800;color:#0F172A;">'
        f"📊 Critérios de Classificação</div>"
        f'<div style="font-size:12px;color:#64748B;margin-top:4px;">'
        f"Base consolidada: <b>{fmt(total_tarefas)}</b> tarefas "
        f"em <b>{fmt(total_registros)}</b> registros importados."
        f"</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### 📦 Distribuição Final por Segmento")
    c1, c2, c3, c4 = st.columns(4)
    for col, emoji, titulo, val, fundo, borda, texto, num in [
        (
            c1,
            "🔄",
            "Migração",
            metricas["migracao"],
            "#EFF6FF",
            "#0369A1",
            "#0369A1",
            "#0C4A6E",
        ),
        (
            c2,
            "🏠",
            "Novos Domicílios",
            metricas["novos_domicilios"],
            "#F0FDF4",
            "#16A34A",
            "#15803D",
            "#14532D",
        ),
        (c3, "🏢", "PME", metricas["pme"], "#FAF5FF", "#7C3AED", "#6D28D9", "#4C1D95"),
        (
            c4,
            "⚪",
            "Outros",
            metricas["outros"],
            "#F8FAFC",
            "#64748B",
            "#475569",
            "#334155",
        ),
    ]:
        col.markdown(
            f'<div style="background:{fundo};border-left:4px solid {borda};'
            f'border-radius:8px;padding:15px 16px;min-height:112px;">'
            f'<div style="font-size:11px;font-weight:700;color:{texto};'
            f'text-transform:uppercase;letter-spacing:0.4px;">'
            f"{emoji} {titulo}</div>"
            f'<div style="font-size:28px;font-weight:800;color:{num};'
            f'line-height:1.15;margin-top:7px;">{fmt(val)}</div>'
            f'<div style="font-size:11px;color:#475569;margin-top:3px;">'
            f"{pct(val)} das tarefas</div></div>",
            unsafe_allow_html=True,
        )


def render_debug_criterios(df_full: pd.DataFrame, expanded: bool = True) -> None:
    with st.expander("🔎 Diagnóstico Técnico de Critérios", expanded=expanded):
        col_tipo = detectar_col_tipo_os_1(df_full)
        col_hab = detectar_col_habilidade(df_full)
        col_gpon = detectar_col_flag_gpon(df_full)

        st.markdown("**Colunas detectadas:**")
        cc1, cc2 = st.columns(2)
        cc1.markdown(
            "**TIPO O.S 1:** "
            + (f"✅ `{col_tipo}`" if col_tipo else "❌")
            + "\n\n**FLAG_GPON:** "
            + (f"✅ `{col_gpon}`" if col_gpon else "❌")
        )
        cc2.markdown("**HABILIDADE:** " + (f"✅ `{col_hab}`" if col_hab else "❌"))


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
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
        <div style="background:rgba(255,255,255,0.10);padding:12px 16px;border-radius:8px;">
            1️⃣ <code>TIPO O.S 1</code> contém <b>"MUDANCA DE PACOTE"</b>
        </div>
        <div style="background:rgba(255,255,255,0.10);padding:12px 16px;border-radius:8px;">
            2️⃣ <code>Habilidade</code> contém <b>"PON"</b>
        </div>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_lista_colunas(df: pd.DataFrame, expanded: bool = False) -> None:
    if df.empty:
        return
    with st.expander("📋 Colunas da Base", expanded=expanded):
        df_cols = pd.DataFrame(
            {
                "#": range(1, len(df.columns) + 1),
                "Coluna": df.columns.tolist(),
                "Tipo": [str(df[c].dtype) for c in df.columns],
            }
        )
        st.dataframe(df_cols, hide_index=True, use_container_width=True)


def detectar_col_capacidade(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    for c in df.columns:
        if "CAPACIDADE" in str(c).upper():
            return str(c)
    return None


def detectar_col_contrato(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    for c in df.columns:
        if str(c).strip().upper() == "CONTRATO":
            return str(c)
    return None


def detectar_col_status_atividade(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    for c in df.columns:
        if "STATUS" in str(c).upper() and "ATIVIDADE" in str(c).upper():
            return str(c)
    return None


def detectar_cols_tipo(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    return [
        str(c)
        for c in df.columns
        if "TIPO" in str(c).upper()
        and ("OS" in str(c).upper() or "O S" in str(c).upper())
    ]


__all__ = [
    "TERMOS_ND",
    "TERMOS_PME",
    "TERMO_GPON_HABILIDADE",
    "TERMO_MIGRACAO_OS",
    "TERMO_PME_HABILIDADE",
    "VALOR_FLAG_GPON_SIM",
    "VAZIOS_GERAIS",
    "VAZIOS_CONTRATO",
    "classificar_tipo_servico",
    "criar_coluna_tipos_agrupados",
    "criar_flag_gpon",
    "detectar_col_capacidade",
    "detectar_col_contrato",
    "detectar_col_flag_gpon",
    "detectar_col_habilidade",
    "detectar_col_status_atividade",
    "detectar_col_tipo_os_1",
    "detectar_cols_tipo",
    "extrair_metricas_criterios",
    "norm_col_nome",
    "normalizar_str",
    "render_card_destaque_migracao",
    "render_debug_criterios",
    "render_lista_colunas",
    "render_painel_criterios",
]
