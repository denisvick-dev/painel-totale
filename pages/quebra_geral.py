"""
quebra_geral.py
===============
Super Relatório Corporativo Unificado | Quebra Operacional TOTALE

Versão: 5.5.0 (camada compartilhada de componentes/serviços + esqueleto padrão do portal)
Author: TOTALE Tecnologia

Esta página é um dos 11 dashboards padronizados: consome a camada compartilhada
(:mod:`components.dashboards`, :mod:`components.layout_pagina` e
:mod:`services.*`) em vez de reimplementar helpers, CSS global e exportação.
O motor de negócio continua local (``Motor``/``DataLoader``/``Config``), pois
``pages/quebra_unificada.py`` o importa.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal, cast

import numpy as np
import pandas as pd
import streamlit as st

# Bootstrap de caminhos antes dos imports locais.
_DIR: Final[Path] = Path(__file__).resolve().parent
_ROOT: Final[Path] = _DIR.parent
for _path in (_DIR, _ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

logger = logging.getLogger(__name__)

# ── Camada compartilhada do portal (componentes + serviços) ──────────────────
from components.componentes import (
    render_hero as render_hero_portal,
)
from components.componentes import render_insight, render_kpi_sm, render_table_html
from components.css_paginas import aplicar_css_quebra_operacional
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.layout_pagina import cabecalho_secao
from services.dados_sessao import obter_dataframe
from services.google_drive_client import carregar_planilha_gsheets_csv
from services.planilhas import gerar_excel as gerar_excel_formatado
from services.planilhas import ler_bytes
from services.texto import (
    escapar_html,
    formatar_inteiro,
    formatar_percentual,
    normalizar_chave,
    valor_nan,
)
from services.texto import normalizar_login as _normalizar_login_servico
from services.texto import normalizar_texto as _normalizar_texto_servico

TemaKPI = Literal["azul", "verde", "vermelho", "laranja", "cinza", "roxo", "amarelo", "escuro"]
TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]


@dataclass
class ModuloCriterios:
    """Encapsula o módulo opcional de critérios."""

    disponivel: bool = False
    termos_nd: tuple[str, ...] = ("ADESAO", "ADESÃO")
    termo_gpon: str = "PON"
    termo_migracao: str = "MUDANCA DE PACOTE"
    termo_pme: str = "PME"
    vazios_gerais: set[str] = field(default_factory=set)
    classificar: Callable[..., Any] | None = None
    criar_flag_gpon: Callable[..., Any] | None = None
    detect_tipo_os: Callable[..., Any] | None = None
    detect_habilidade: Callable[..., Any] | None = None
    detect_flag_gpon: Callable[..., Any] | None = None
    render_painel: Callable[..., Any] | None = None


def _carregar_criterios() -> ModuloCriterios:
    try:
        from components import criterios as c  # type: ignore

        return ModuloCriterios(
            disponivel=True,
            termos_nd=c.TERMOS_ND,
            termo_gpon=c.TERMO_GPON_HABILIDADE,
            termo_migracao=c.TERMO_MIGRACAO_OS,
            termo_pme=c.TERMO_PME_HABILIDADE,
            vazios_gerais=c.VAZIOS_GERAIS,
            classificar=c.classificar_tipo_servico,
            criar_flag_gpon=c.criar_flag_gpon,
            detect_tipo_os=c.detectar_col_tipo_os_1,
            detect_habilidade=c.detectar_col_habilidade,
            detect_flag_gpon=c.detectar_col_flag_gpon,
            render_painel=c.render_painel_criterios,
        )
    except ImportError as erro:
        logger.warning("Módulo critérios não disponível: %s", erro)
        return ModuloCriterios()


CRITERIOS: Final[ModuloCriterios] = _carregar_criterios()


from config.settings import (
    SHEET_ABA_ATIVOS as _DEFAULT_WORKSHEET_ATIVOS,
)
from config.settings import (
    SHEET_ID_ATIVOS as _DEFAULT_SHEET_ID_ATIVOS,
)


class Config:
    """Constantes de negócio e visuais."""

    SLA_QUEBRA_MAXIMA: Final[float] = 0.20
    SLA_MIGRACAO_MAXIMA: Final[float] = 0.25
    SHEET_ID_ATIVOS: Final[str] = _DEFAULT_SHEET_ID_ATIVOS
    WORKSHEET_ATIVOS: Final[str] = _DEFAULT_WORKSHEET_ATIVOS
    STATUS_ORDEM: Final[tuple[str, ...]] = ("Executada", "Não Executada", "Pendente")
    ORDEM_TIPOS: Final[tuple[str, ...]] = (
        "Novos Domicílios",
        "PME",
        "Migração",
        "Outros",
    )
    COLUNAS_TIPO_SERVICO: Final[tuple[str, ...]] = (
        "TIPO_SERVICO",
        "TIPO SERVICO",
        "TIPO O.S 1",
        "TIPO OS 1",
        "TIPO O.S. 1",
    )
    CORES_STATUS: Final[dict[str, str]] = {
        "Executada": "#10B981",
        "Não Executada": "#EF4444",
        "Pendente": "#94A3B8",
    }
    CORES_TIPO: Final[dict[str, str]] = {
        "Novos Domicílios": "#012869",
        "PME": "#0A48AA",
        "Migração": "#F37C04",
        "Quebra Geral": "#334155",
        "Outros": "#64748B",
    }


class Fontes:
    TITULO: Final[str] = (
        "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    )
    TEXTO: Final[str] = (
        "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    )


_CODIGOS_NAO_EXECUTADA: Final[tuple[int, ...]] = (
    100,
    101,
    103,
    104,
    105,
    106,
    107,
    108,
    110,
    112,
    113,
    114,
    125,
    203,
    204,
    205,
    206,
    301,
    302,
    303,
    305,
    306,
    307,
    308,
    312,
    316,
    400,
    402,
)
_CODIGOS_EXECUTADA: Final[tuple[int, ...]] = (
    128,
    328,
    408,
    409,
    425,
    430,
    440,
    467,
    470,
    474,
    475,
    477,
    *range(500, 591),
)
MAPA_CODIGO_NUMERICO: Final[dict[int, str]] = {
    **{c: "Não Executada" for c in _CODIGOS_NAO_EXECUTADA},
    **{c: "Executada" for c in _CODIGOS_EXECUTADA},
}
CORES_REGIAO: Final[dict[str, dict[str, str]]] = {
    "LESTE": {"bg": "#EFF6FF", "text": "#1E40AF", "border": "#BFDBFE"},
    "GRU": {"bg": "#ECFDF5", "text": "#047857", "border": "#A7F3D0"},
    "ABCDM": {"bg": "#F5F3FF", "text": "#6D28D9", "border": "#DDD6FE"},
    "OUTRAS": {"bg": "#F8FAFC", "text": "#475569", "border": "#CBD5E1"},
}
CIDADES_LESTE: Final[frozenset[str]] = frozenset({"SAO PAULO"})
CIDADES_GRU: Final[frozenset[str]] = frozenset(
    {
        "GUARULHOS",
        "ARUJA",
        "MOGI DAS CRUZES",
        "SUZANO",
        "ITAQUAQUECETUBA",
        "FERRAZ DE VASCONCELOS",
        "POA",
    }
)
CIDADES_ABCDM: Final[frozenset[str]] = frozenset(
    {
        "SANTO ANDRE",
        "SAO BERNARDO DO CAMPO",
        "SAO CAETANO DO SUL",
        "DIADEMA",
        "MAUA",
        "RIBEIRAO PIRES",
        "RIO GRANDE DA SERRA",
    }
)
VALORES_AUSENTES: Final[frozenset[str]] = frozenset(
    {"", "NAN", "NONE", "NULL", "NAT", "NA", "N/A", "-", "None"}
)
RE_NUMERO_INICIAL: Final[re.Pattern[str]] = re.compile(r"^(\d+)")


#: Helpers de texto/número delegados a :mod:`services.texto` (fonte única do
#: portal — antes cada página tinha a sua cópia, com diferenças sutis).
html_safe = escapar_html
fmt_int_br = formatar_inteiro
fmt_pct_br = formatar_percentual
is_missing = valor_nan
normalizar_texto = _normalizar_texto_servico
normalizar_coluna = normalizar_chave
normalizar_login = _normalizar_login_servico


def div_segura(num: pd.Series, den: pd.Series, padrao: float = 0.0) -> pd.Series:
    """Divisão vetorizada sem ``inf``/``ZeroDivisionError`` (denominador 0 → ``padrao``)."""
    n = pd.to_numeric(num, errors="coerce").fillna(0).to_numpy(dtype=float)
    d = pd.to_numeric(den, errors="coerce").fillna(0).to_numpy(dtype=float)
    out = np.full_like(n, padrao, dtype=float)
    np.divide(n, d, out=out, where=d > 0)
    return pd.Series(out, index=num.index)


def df_sessao(chave: str) -> pd.DataFrame | None:
    """DataFrame guardado em ``st.session_state[chave]`` (``None`` se ausente).

    Usa o :func:`services.dados_sessao.obter_dataframe` quando o contexto real do
    Streamlit está disponível e cai para a leitura direta do ``st`` deste módulo
    em testes que fazem *monkeypatch* do ``st`` da página
    (``tests/test_quebra_geral.py``).
    """
    obtido = obter_dataframe(chave)
    if not isinstance(obtido, pd.DataFrame):
        obtido = getattr(st.session_state, "get", lambda *_: None)(chave)
    return obtido if isinstance(obtido, pd.DataFrame) else None


def hash_upload(nome: str, conteudo: bytes) -> str:
    """Identidade estável de um upload (nome + tamanho + SHA-256)."""
    return f"{nome}|{len(conteudo)}|{hashlib.sha256(conteudo).hexdigest()}"


def padronizar_tipo_servico(tipo: Any) -> str:
    if tipo is None or (isinstance(tipo, float) and np.isnan(tipo)):
        return "Outros"
    t = normalizar_texto(tipo)
    if not t:
        return "Outros"
    if any(k in t for k in ("PME", "PJ", "JURIDICO", "CORPORATIVO", "EMPRESA")):
        return "PME"
    if any(k in t for k in ("MIGRA", "MUDANCA DE PACOTE", "UPGRADE", "TROCA", "SWAP")):
        return "Migração"
    if (
        any(
            k in t
            for k in (
                "NOVOS DOMICILIOS",
                "NOVO DOMICILIO",
                "DOMICIL",
                "ADESAO",
                "INSTALACAO",
                "INSTAL",
                "RESIDENCIAL",
                "FIBRA NOVA",
            )
        )
        or t == "ND"
    ):
        return "Novos Domicílios"
    return "Outros"


class DF:
    @staticmethod
    def obter_serie(
        df: pd.DataFrame | None,
        coluna: str | None,
        padrao: Any = "",
        *,
        copiar: bool = False,
    ) -> pd.Series:
        if df is None:
            return pd.Series(dtype="object", name=coluna)
        if coluna is None or coluna not in df.columns:
            return pd.Series(padrao, index=df.index, dtype="object", name=coluna)
        obtido = df[coluna]
        if isinstance(obtido, pd.DataFrame):
            obtido = cast(pd.DataFrame, obtido).T.bfill().iloc[0]
        serie = cast(pd.Series, obtido)
        if not serie.index.equals(df.index):
            serie = serie.reindex(df.index)
        serie.name = coluna
        return serie.copy() if copiar else serie

    @staticmethod
    def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        resultado = df.copy()
        nomes, usados = [], {}
        for col in resultado.columns:
            base = normalizar_texto(col) or "COLUNA"
            usados[base] = usados.get(base, 0) + 1
            nomes.append(base if usados[base] == 1 else f"{base}__{usados[base]}")
        resultado.columns = nomes
        return resultado

    @staticmethod
    def buscar_coluna(df: pd.DataFrame | None, palavras: tuple[str, ...] | list[str]) -> str | None:
        if df is None:
            return None
        mapa = {normalizar_coluna(c): str(c) for c in df.columns}
        for p in palavras:
            alvo = normalizar_coluna(p)
            if alvo and alvo in mapa:
                return mapa[alvo]
        for p in palavras:
            alvo = normalizar_coluna(p)
            if len(alvo) < 3:
                continue
            for norm, orig in mapa.items():
                if alvo == "CONTRATO" and "STATUS" in norm:
                    continue
                if "TECNICO" in alvo and "LOGIN" not in alvo and "LOGIN" in norm:
                    continue
                if alvo in norm or norm in alvo:
                    return orig
        return None

    @staticmethod
    def remover_duplicatas_coluna(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        vistos: set[str] = set()
        remover = []
        for col in df.columns:
            norm = normalizar_texto(col)
            if norm in vistos:
                remover.append(col)
            else:
                vistos.add(norm)
        return df.drop(columns=remover) if remover else df

    @staticmethod
    def corrigir_colunas_vazias(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["DATA AGENDA MDU", "ID SGD", "DATA_AGENDA_MDU", "ID_SGD"]:
            if col in df.columns and (
                df[col].isna().all() or (df[col].astype(str) == "None").all()
            ):
                for alt in df.columns:
                    if alt != col and (
                        ("AGENDA" in alt.upper() and col in alt.upper())
                        or ("ID" in alt.upper() and "SGD" in alt.upper())
                    ):
                        df[col] = df[alt]
                        break
        return df

    @staticmethod
    def limpar_texto(serie: pd.Series, padrao: str) -> pd.Series:
        r = serie.fillna("").astype(str).str.strip().str.upper()
        return r.mask(r.isin(VALORES_AUSENTES), padrao)


def converter_numero(valor: Any) -> float:
    if valor is None:
        return np.nan
    if isinstance(valor, (int, float, np.number)):
        n = float(valor)
        return n if np.isfinite(n) else np.nan
    texto = re.sub(r"[^\d,.\-]", "", str(valor).strip())
    if not texto or texto in {"-", ".", ","}:
        return np.nan
    try:
        if "," in texto and "." in texto:
            texto = (
                texto.replace(".", "").replace(",", ".")
                if texto.rfind(",") > texto.rfind(".")
                else texto.replace(",", "")
            )
        elif "," in texto:
            texto = (
                texto.replace(",", "")
                if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+", texto)
                else texto.replace(",", ".")
            )
        elif "." in texto and re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", texto):
            texto = texto.replace(".", "")
        n = float(texto)
        return n if np.isfinite(n) else np.nan
    except (TypeError, ValueError):
        return np.nan


class ClassificadorStatus:
    @staticmethod
    def status_texto(valor: Any) -> str | None:
        texto = normalizar_texto(valor)
        if texto in VALORES_AUSENTES:
            return None
        if "SUSPENS" in texto:
            return "Suspenso"
        if "CANCEL" in texto:
            return "Cancelado"
        if "NAO EXECUT" in texto or "NAO CONCLU" in texto:
            return "Não Executada"
        if "EXECUT" in texto or "CONCLUID" in texto:
            return "Executada"
        if any(t in texto for t in ("PEND", "EM ROTA", "INICIADO", "AGENDADO", "ABERTO")):
            return "Pendente"
        return None

    @staticmethod
    def codigo_baixa(valor: Any) -> str | None:
        texto = normalizar_texto(valor)
        if texto in VALORES_AUSENTES:
            return None
        if texto in {"EM ROTA", "INICIADO", "PENDENTE"}:
            return "Pendente"
        m = RE_NUMERO_INICIAL.match(texto)
        return MAPA_CODIGO_NUMERICO.get(int(m.group(1))) if m else None

    @classmethod
    def classificar(cls, df: pd.DataFrame) -> pd.Series:
        col_inicio = DF.buscar_coluna(
            df, ("INÍCIO", "INICIO", "DATA INÍCIO", "DT INICIO", "HORA INICIO")
        )
        col_fechamento = DF.buscar_coluna(
            df,
            (
                "MOTIVO DE FECHAMENTO EXTERNO",
                "FECHAMENTO EXTERNO",
                "MOTIVO DE FECHAMENTO",
            ),
        )
        col_atividade = DF.buscar_coluna(
            df, ("STATUS DA ATIVIDADE", "STATUS ATIVIDADE", "STATUS_ATIVIDADE")
        )
        col_cod_baixa = DF.buscar_coluna(
            df, ("CÓD DE BAIXA 1", "COD DE BAIXA 1", "MOTIVO DE BAIXA", "COD_BAIXA")
        )
        col_status_os = DF.buscar_coluna(
            df,
            (
                "STATUS DA O.S 1",
                "STATUS OS 1",
                "STATUS CONTRATO",
                "STATUS O.S.",
                "STATUS OS",
            ),
        )
        inicio = DF.obter_serie(df, col_inicio).map(normalizar_texto)
        fechamento = DF.obter_serie(df, col_fechamento).map(normalizar_texto)
        atividade = DF.obter_serie(df, col_atividade).map(normalizar_texto)
        cod_baixa = DF.obter_serie(df, col_cod_baixa)
        status_os = DF.obter_serie(df, col_status_os).map(cls.status_texto)
        s_atividade, s_codigo = atividade.map(cls.status_texto), cod_baixa.map(cls.codigo_baixa)
        resultado = s_codigo.where(s_codigo.notna(), status_os)
        resultado = resultado.where(resultado.notna(), s_atividade).fillna("Pendente")
        fech_alvo = {"LIBERADO NO SISTEMA NETSMS", "CANCELADO NO SISTEMA NETSMS"}
        inicio_vazio = inicio.isin(VALORES_AUSENTES)
        c_fech = fechamento.isin(fech_alvo)
        resultado = resultado.mask(
            atividade.str.contains("NAO CONCLU", regex=False, na=False), "Não Executada"
        )
        resultado = resultado.mask(
            atividade.str.contains("SUSPENS", regex=False, na=False), "Suspenso"
        )
        resultado = resultado.mask(
            atividade.str.contains("CANCEL", regex=False, na=False), "Cancelado"
        )
        resultado = resultado.mask(~inicio_vazio & c_fech, "Não Executada")
        resultado = resultado.mask(inicio_vazio & c_fech, "Cancelado")
        return resultado.astype("object")


_PALAVRAS_PCT_EXCEL: Final[tuple[str, ...]] = (
    "QUEBRA",
    "FECHAMENTO",
    "CONVERSÃO",
    "CONVERSAO",
    "PROJEÇÃO",
    "PROJECAO",
    "%",
    "PME",
    "MIGRAÇÃO",
    "MIGRACAO",
    "DOMICÍLIOS",
    "DOMICILIOS",
    "GPON",
)


class Utils:
    normalizar_login = staticmethod(normalizar_login)

    @staticmethod
    def classificar_status_excel(df: pd.DataFrame) -> pd.Series:
        return ClassificadorStatus.classificar(df)

    @staticmethod
    def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
        """Exportação delegada a :func:`services.planilhas.gerar_excel`."""
        return gerar_excel_formatado(df, aba, autofiltro=True, colunas_pct=_PALAVRAS_PCT_EXCEL)


class DataLoader:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        """Leitura de upload delegada a :func:`services.planilhas.ler_bytes`.

        Mantém o contrato histórico da página (tudo como texto, NA preservado
        como string vazia) sem duplicar a detecção de encoding/separador.
        """
        return ler_bytes(
            file_bytes,
            filename,
            dtype=str,
            manter_na=False,
            on_bad_lines="skip",
        )

    @staticmethod
    @st.cache_data(ttl=300, show_spinner="Sincronizando Lista de Ativos...")
    def buscar_gsheets() -> pd.DataFrame:
        """Lista de ativos via camada compartilhada (CSV do Sheets + aliases).

        Antes a página abria URLs com ``urllib`` e reimplementava o dicionário de
        aliases; hoje delega a :mod:`services.google_drive_client` e normaliza
        com :meth:`processar_lista_ativos` (que ``tests/test_quebra_geral.py``
        cobre). Sem rede devolve DataFrame vazio — o upload manual continua
        disponível na barra lateral.
        """
        raw = carregar_planilha_gsheets_csv(
            Config.SHEET_ID_ATIVOS, Config.WORKSHEET_ATIVOS, usar_cache=True, ttl=300
        )
        if isinstance(raw, pd.DataFrame) and not raw.empty:
            processada = DataLoader.processar_lista_ativos(raw)
            if not processada.empty:
                return processada
        logger.warning(
            "Lista de ativos indisponível (sheet %s); siga com upload manual se necessário.",
            Config.SHEET_ID_ATIVOS,
        )
        return pd.DataFrame()

    @staticmethod
    def processar_lista_ativos(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        base = raw.copy()
        base.columns = base.columns.astype(str).str.strip()
        aliases = {
            "LOGIN": (
                "LOGIN",
                "LOGIN DO TÉCNICO",
                "LOGIN DO TECNICO",
                "LOGIN_TECNICO",
                "MATRÍCULA",
                "MATRICULA",
                "ID",
                "USUARIO",
                "USUÁRIO",
                "RE",
                "COD_TECNICO",
            ),
            "TÉCNICO": (
                "TÉCNICO",
                "TECNICO",
                "NOME",
                "COLABORADOR",
                "NOME TÉCNICO",
                "NOME TECNICO",
                "NOME COMPLETO",
                "NOME DO TÉCNICO",
                "NOME DO TECNICO",
            ),
            "MONITOR": (
                "MONITOR",
                "GESTOR",
                "SUPERVISOR",
                "COORDENADOR",
                "LIDER",
                "LÍDER",
                "NOME MONITOR",
                "NOME SUPERVISOR",
                "NOME GESTOR",
            ),
            "BASE": ("BASE", "REGIÃO", "REGIAO", "FILIAL", "LOCALIDADE"),
        }
        resultado = pd.DataFrame(index=base.index)
        for destino, nomes in aliases.items():
            col = DF.buscar_coluna(base, nomes)
            if col:
                resultado[destino] = DF.obter_serie(base, col)
        if "LOGIN" not in resultado.columns:
            return pd.DataFrame()
        resultado["LOGIN"] = resultado["LOGIN"].map(normalizar_login)
        resultado = resultado.loc[~resultado["LOGIN"].isin(VALORES_AUSENTES)].copy()
        for col in ("TÉCNICO", "MONITOR"):
            if col in resultado.columns:
                resultado[col] = resultado[col].fillna("").astype(str).str.strip().str.upper()
        return resultado.drop_duplicates(subset=["LOGIN"], keep="last").reset_index(drop=True)

    _processar_lista_ativos = processar_lista_ativos

    @staticmethod
    def classificar_regiao(valor: Any) -> str:
        cidade = normalizar_texto(valor)
        if cidade in CIDADES_LESTE:
            return "LESTE"
        if cidade in CIDADES_GRU:
            return "GRU"
        if cidade in CIDADES_ABCDM:
            return "ABCDM"
        return cidade if cidade in CORES_REGIAO else "OUTRAS"

    @staticmethod
    def gerar_tipo_servico(df: pd.DataFrame) -> pd.Series:
        if df.empty:
            return pd.Series(dtype="object")
        if CRITERIOS.disponivel and CRITERIOS.classificar:
            try:
                _, serie = CRITERIOS.classificar(df.copy())
                return serie.map(padronizar_tipo_servico)
            except Exception as erro:
                st.warning(f"Erro ao usar critérios; fallback aplicado: {erro}")
        col = DF.buscar_coluna(df, Config.COLUNAS_TIPO_SERVICO)
        return (
            pd.Series("Outros", index=df.index, dtype="object")
            if col is None
            else DF.obter_serie(df, col).map(padronizar_tipo_servico)
        )

    @staticmethod
    def criar_flag_gpon(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            df["FLAG_GPON"] = "Não"
            return df
        if CRITERIOS.disponivel and CRITERIOS.criar_flag_gpon:
            try:
                result, _, _ = CRITERIOS.criar_flag_gpon(df)
                return result
            except Exception as erro:
                st.warning(f"Erro ao criar FLAG_GPON; fallback aplicado: {erro}")
        col = DF.buscar_coluna(
            df,
            ("HABILIDADE DE TRABALHO", "HABILIDADE", "HABILIDADES", "SKILL", "SKILLS"),
        )
        df["FLAG_GPON"] = (
            np.where(
                df[col].fillna("").astype(str).str.upper().str.contains("PON", na=False),
                "Sim",
                "Não",
            )
            if col
            else "Não"
        )
        return df

    @staticmethod
    def _mesclar_ativos(
        base: pd.DataFrame, ativos: pd.DataFrame, col_login: str | None
    ) -> pd.DataFrame:
        col_mon_os = DF.buscar_coluna(base, ("MONITOR", "GESTOR", "SUPERVISOR", "COORDENADOR"))
        col_tec_os = DF.buscar_coluna(
            base, ("TÉCNICO", "TECNICO", "NOME TÉCNICO", "NOME TECNICO", "COLABORADOR")
        )
        mon_os = (
            DF.obter_serie(base, col_mon_os).map(normalizar_texto)
            if col_mon_os
            else pd.Series("", index=base.index)
        )
        tec_os = (
            DF.obter_serie(base, col_tec_os).map(normalizar_texto)
            if col_tec_os
            else pd.Series("", index=base.index)
        )
        if ativos is None or ativos.empty or "LOGIN" not in ativos.columns:
            base["TÉCNICO"] = tec_os.mask(
                tec_os.isin(VALORES_AUSENTES) | (tec_os == ""), "NÃO MAPEADO"
            )
            base["MONITOR"] = mon_os.mask(
                mon_os.isin(VALORES_AUSENTES) | (mon_os == ""), "SEM MONITOR"
            )
            return base
        at = ativos.copy()
        at["_JOIN_KEY"] = at["LOGIN"].map(normalizar_login)
        at["_JOIN_CLEAN"] = at["_JOIN_KEY"].str.lstrip("0")
        for col in ("TÉCNICO", "MONITOR", "BASE"):
            if col not in at.columns:
                at[col] = ""
        at_key = at.drop_duplicates(subset=["_JOIN_KEY"], keep="last")
        at_clean = at.loc[at["_JOIN_CLEAN"] != ""].drop_duplicates(
            subset=["_JOIN_CLEAN"], keep="last"
        )
        os_login = DF.obter_serie(base, col_login) if col_login else pd.Series("", index=base.index)
        work = base.copy()
        work["_JOIN_KEY"] = os_login.map(normalizar_login)
        work["_JOIN_CLEAN"] = work["_JOIN_KEY"].str.lstrip("0")
        work["_MON_OS"], work["_TEC_OS"] = mon_os, tec_os
        rename = {"TÉCNICO": "_TEC_AT", "MONITOR": "_MON_AT", "BASE": "_BASE_AT"}
        m1 = work.merge(
            at_key[["_JOIN_KEY", "TÉCNICO", "MONITOR", "BASE"]].rename(columns=rename),
            on="_JOIN_KEY",
            how="left",
        )
        m2 = work.merge(
            at_clean[["_JOIN_CLEAN", "TÉCNICO", "MONITOR", "BASE"]].rename(columns=rename),
            on="_JOIN_CLEAN",
            how="left",
        )

        def resolve(col: str, fallback: str, default: str) -> pd.Series:
            a = m1[col].fillna("").astype(str).str.strip()
            b = m2[col].fillna("").astype(str).str.strip()
            c = m1[fallback].fillna("").astype(str).str.strip()
            result = np.where(a != "", a, np.where(b != "", b, c))
            return DF.limpar_texto(pd.Series(result, index=base.index), default)

        result = base.copy()
        result["TÉCNICO"] = resolve("_TEC_AT", "_TEC_OS", "NÃO MAPEADO")
        result["MONITOR"] = resolve("_MON_AT", "_MON_OS", "SEM MONITOR")
        b1 = m1["_BASE_AT"].fillna("").astype(str).str.strip()
        b2 = m2["_BASE_AT"].fillna("").astype(str).str.strip()
        b_final = np.where(b1 != "", b1, b2)
        if any(b_final != ""):
            result["_B"] = pd.Series(b_final, index=result.index)
        match_mask = (
            m1["_JOIN_KEY"].isin(set(at_key["_JOIN_KEY"]))
            | m2["_JOIN_CLEAN"].isin(set(at_clean["_JOIN_CLEAN"]))
        ) & (work["_JOIN_KEY"] != "")
        result.attrs["logins_encontrados"] = int(match_mask.sum())
        return result

    @staticmethod
    def _definir_regiao(base: pd.DataFrame) -> pd.Series:
        col = DF.buscar_coluna(base, ("CIDADE", "LOCALIDADE", "MUNICÍPIO", "MUNICIPIO"))
        if col:
            return DF.obter_serie(base, col).map(DataLoader.classificar_regiao)
        if "_B" in base.columns:
            return base["_B"].map(DataLoader.classificar_regiao)
        if "BASE" in base.columns:
            return base["BASE"].map(DataLoader.classificar_regiao)
        return pd.Series("OUTRAS", index=base.index)

    @staticmethod
    def preparar_base(
        df: pd.DataFrame, df_gs: pd.DataFrame | None, filename: str = ""
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        base = DF.corrigir_colunas_vazias(DF.remover_duplicatas_coluna(DF.padronizar_colunas(df)))
        total_importado = len(base)
        base = DataLoader.criar_flag_gpon(base)
        flag_gpon_sim = int((base["FLAG_GPON"] == "Sim").sum())
        col_tipo = DF.buscar_coluna(base, Config.COLUNAS_TIPO_SERVICO)
        valores_tipo = {}
        if col_tipo:
            serie = DF.obter_serie(base, col_tipo).fillna("").astype(str).str.strip()
            valores_tipo = {str(k): int(v) for k, v in serie.value_counts().head(20).items()}
        base["STATUS CONTRATO"] = ClassificadorStatus.classificar(base)
        status = base["STATUS CONTRATO"].fillna("").astype(str).str.upper().str.strip()
        removidos_status = int(status.isin({"CANCELADO", "SUSPENSO"}).sum())
        base = base.loc[~status.isin({"CANCELADO", "SUSPENSO"})].copy()
        if base.empty:
            return pd.DataFrame()
        col_contrato = DF.buscar_coluna(
            base,
            (
                "CONTRATO",
                "NR CONTRATO",
                "NÚMERO CONTRATO",
                "NUMERO CONTRATO",
                "CONTRATO_ID",
            ),
        )
        removidos_contrato = 0
        if col_contrato:
            contratos = DF.obter_serie(base, col_contrato).map(normalizar_texto)
            invalidos = contratos.isin({"", "NAN", "NONE", "NULL", "N/A", "NA", "-", "0"})
            removidos_contrato = int(invalidos.sum())
            base = base.loc[~invalidos].copy()
        if base.empty:
            return pd.DataFrame()
        col_total = DF.buscar_coluna(
            base, ("TOTAL DE TAREFAS", "QTD TAREFAS", "QUANTIDADE", "VOLUME")
        )
        base["TOTAL DE TAREFAS"] = (
            pd.to_numeric(DF.obter_serie(base, col_total).map(converter_numero), errors="coerce")
            .fillna(1)
            .clip(lower=0)
            .round()
            .astype(int)
            if col_total
            else 1
        )
        col_login = DF.buscar_coluna(
            base,
            (
                "LOGIN DO TÉCNICO",
                "LOGIN DO TECNICO",
                "LOGIN_DO_TECNICO",
                "LOGIN TÉCNICO",
                "LOGIN TECNICO",
                "LOGIN_TECNICO",
                "LOGIN",
                "MATRÍCULA",
                "MATRICULA",
                "RE",
                "ID TÉCNICO",
                "ID TECNICO",
                "ID_TECNICO",
                "COD_TECNICO",
            ),
        )
        ativos = (
            DataLoader.processar_lista_ativos(df_gs)
            if isinstance(df_gs, pd.DataFrame)
            else pd.DataFrame()
        )
        base = DataLoader._mesclar_ativos(base, ativos, col_login)
        base["REGIÃO"] = DataLoader._definir_regiao(base)
        base["TIPO_SERVICO"] = DataLoader.gerar_tipo_servico(base).map(padronizar_tipo_servico)
        base["Status Contrato"] = base["STATUS CONTRATO"]
        aux = [
            c
            for c in base.columns
            if c.startswith("_LOGIN_") or c.startswith("_ATIVO") or c in ("_T", "_M", "_B")
        ]
        logins_encontrados = int(base.attrs.get("logins_encontrados", 0))
        base = base.drop(columns=aux, errors="ignore").reset_index(drop=True)
        base.attrs.update(
            {
                "arquivo_origem": filename,
                "total_importado": total_importado,
                "removidos_suspensos_cancelados": removidos_status,
                "removidos_contrato": removidos_contrato,
                "tipo_servico_coluna": col_tipo or "",
                "valores_tipo_servico_originais": valores_tipo,
                "total_processado": len(base),
                "flag_gpon_sim_count": flag_gpon_sim,
                "logins_encontrados": logins_encontrados,
            }
        )
        return base

    @staticmethod
    def callback_robo_etl(df_raw: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        caminho = st.session_state.get(
            "robo_ultimo_processado_path", st.session_state.get("robo_candidato_path", "")
        )
        nome = Path(str(caminho)).name if caminho else "Arquivo_Robo"
        df_proc = DataLoader.preparar_base(df_raw, df_gs, filename=nome)
        st.session_state.update(
            {
                "_robo_df_pronto": df_proc,
                "_robo_nome_arquivo": nome,
                "_robo_dados_disponiveis": not df_proc.empty,
                "df_memoria_raw": df_raw,
                "df_memoria": df_proc,
                "origem_dados": f"Robô ({nome})",
                "robo_hora_sucesso": datetime.now(),
            }
        )
        return df_proc


class Motor:
    @staticmethod
    def _matriz_logic(df: pd.DataFrame) -> pd.DataFrame:
        obrig = {"MONITOR", "TIPO_SERVICO", "Status Contrato", "TOTAL DE TAREFAS"}
        if df is None or df.empty or not obrig.issubset(df.columns):
            return pd.DataFrame()
        t = df.copy()
        t["MONITOR"] = t["MONITOR"].fillna("SEM MONITOR").astype(str).str.strip().str.upper()
        t["TIPO_SERVICO"] = t["TIPO_SERVICO"].apply(padronizar_tipo_servico)
        t["Status Contrato"] = t["Status Contrato"].fillna("").astype(str).str.strip()
        t["TOTAL DE TAREFAS"] = (
            pd.to_numeric(t["TOTAL DE TAREFAS"], errors="coerce").fillna(0).clip(lower=0)
        )
        validos = t.loc[t["Status Contrato"].isin(Config.STATUS_ORDEM)].copy()
        if validos.empty:
            return pd.DataFrame()
        validos["_EXEC"] = np.where(
            validos["Status Contrato"].eq("Executada"), validos["TOTAL DE TAREFAS"], 0
        )
        validos["_NEX"] = np.where(
            validos["Status Contrato"].eq("Não Executada"),
            validos["TOTAL DE TAREFAS"],
            0,
        )
        ag = (
            validos.groupby(["MONITOR", "TIPO_SERVICO"], dropna=False)
            .agg(executados=("_EXEC", "sum"), nao_executados=("_NEX", "sum"))
            .reset_index()
        )
        ag["DENOMINADOR"] = ag["executados"] + ag["nao_executados"]
        ag["PERCENTUAL"] = div_segura(ag["nao_executados"], ag["DENOMINADOR"], padrao=np.nan)
        monitores = pd.Index(sorted(validos["MONITOR"].dropna().unique()), name="MONITOR")
        pivot = ag.pivot(index="MONITOR", columns="TIPO_SERVICO", values="PERCENTUAL").reindex(
            monitores
        )
        for tipo in Config.ORDEM_TIPOS:
            if tipo not in pivot.columns:
                pivot[tipo] = np.nan
        pivot = pivot.loc[:, list(Config.ORDEM_TIPOS)]
        totais = validos.groupby("MONITOR")[["_EXEC", "_NEX"]].sum().reindex(monitores).fillna(0)
        denom = totais["_EXEC"] + totais["_NEX"]
        pivot["Quebra Geral"] = div_segura(totais["_NEX"], denom, padrao=np.nan)
        pivot["Total Tasks"] = (
            validos.groupby("MONITOR")["TOTAL DE TAREFAS"]
            .sum()
            .reindex(monitores)
            .fillna(0)
            .round()
            .astype(int)
        )
        pivot = pivot.reset_index().rename(columns={"MONITOR": "Monitor"})
        exec_g, nex_g = float(validos["_EXEC"].sum()), float(validos["_NEX"].sum())
        total_row: dict[str, Any] = {
            "Monitor": "TOTAL GERAL",
            "Quebra Geral": nex_g / (exec_g + nex_g) if exec_g + nex_g > 0 else np.nan,
            "Total Tasks": int(validos["TOTAL DE TAREFAS"].sum()),
        }
        for tipo in Config.ORDEM_TIPOS:
            r = validos.loc[validos["TIPO_SERVICO"].eq(tipo)]
            e, n = float(r["_EXEC"].sum()), float(r["_NEX"].sum())
            total_row[tipo] = n / (e + n) if e + n > 0 else np.nan
        return pd.concat(
            [pivot, pd.DataFrame([total_row], columns=pivot.columns)], ignore_index=True
        )

    @staticmethod
    def matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame() if df is None or df.empty else _cache_matriz(df.copy())

    @staticmethod
    def _pivot_status(df: pd.DataFrame, grupo: str) -> pd.DataFrame:
        t = df.copy()
        t["TOTAL DE TAREFAS"] = (
            pd.to_numeric(t["TOTAL DE TAREFAS"], errors="coerce").fillna(0).clip(lower=0)
        )
        pivot = pd.pivot_table(
            t,
            index=grupo,
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        )
        for s in Config.STATUS_ORDEM:
            if s not in pivot.columns:
                pivot[s] = 0.0
        return pivot.reset_index()

    @staticmethod
    def tabela_cenarios(
        df: pd.DataFrame,
        grupo: str,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 5,
    ) -> pd.DataFrame:
        obrig = {grupo, "Status Contrato", "TOTAL DE TAREFAS"}
        if df.empty or not obrig.issubset(df.columns):
            return pd.DataFrame()
        p_ot, p_base, p_pess = (float(np.clip(x, 0, 1)) for x in (p_ot, p_base, p_pess))
        r = Motor._pivot_status(df, grupo)
        r["Considerado"] = r["Executada"] + r["Não Executada"]
        r["Alocado"] = r["Considerado"] + r["Pendente"]
        r["Quebra Atual"] = div_segura(r["Não Executada"], r["Considerado"])
        for nome, prob in (
            ("Otimista", p_ot),
            ("Base", p_base),
            ("Pessimista", p_pess),
        ):
            r[f"Fechamento {nome}"] = div_segura(
                r["Não Executada"] + r["Pendente"] * prob, r["Alocado"]
            )
        return (
            r.loc[r["Alocado"] >= min_aloc]
            .sort_values("Fechamento Base", ascending=False)
            .reset_index(drop=True)
        )

    @staticmethod
    def tecnicos_criticos(
        df: pd.DataFrame,
        segmento: str,
        p_base: float,
        min_aloc: float,
        top_n: int,
        p_ot: float = 0.15,
        p_pess: float = 0.50,
    ) -> pd.DataFrame:
        recorte = (
            df.loc[df["TIPO_SERVICO"].eq(segmento)].copy()
            if segmento and segmento != "TODOS" and "TIPO_SERVICO" in df.columns
            else df.copy()
        )
        return (
            pd.DataFrame()
            if recorte.empty
            else Motor.tabela_cenarios(recorte, "TÉCNICO", p_ot, p_base, p_pess, min_aloc).head(
                top_n
            )
        )

    @staticmethod
    def causa_raiz(df: pd.DataFrame, coluna_baixa: str, top_n: int = 8) -> pd.DataFrame:
        if not {"Status Contrato", "TOTAL DE TAREFAS", coluna_baixa}.issubset(df.columns):
            return pd.DataFrame()
        r = df.loc[df["Status Contrato"].eq("Não Executada")].copy()
        if r.empty:
            return pd.DataFrame()
        r["_B"] = (
            r[coluna_baixa]
            .fillna("SEM REGISTRO")
            .astype(str)
            .map(normalizar_texto)
            .replace("", "SEM REGISTRO")
        )
        r["TOTAL DE TAREFAS"] = (
            pd.to_numeric(r["TOTAL DE TAREFAS"], errors="coerce").fillna(0).clip(lower=0)
        )
        total = float(r["TOTAL DE TAREFAS"].sum())
        res = r.groupby("_B")["TOTAL DE TAREFAS"].sum().nlargest(top_n).reset_index()
        res.columns = ["Motivo de Baixa", "Volume"]
        res["% do Total"] = div_segura(res["Volume"], pd.Series(total, index=res.index))
        res["Acumulado"] = res["% do Total"].cumsum()
        return res

    @staticmethod
    def backoffice_fila(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or "Status Contrato" not in df.columns:
            return pd.DataFrame()
        t = df.copy()
        for col, pad in (
            ("MONITOR", "SEM MONITOR"),
            ("TÉCNICO", "NÃO MAPEADO"),
            ("TIPO_SERVICO", "Outros"),
        ):
            if col not in t.columns:
                t[col] = pad
        if "TOTAL DE TAREFAS" in t.columns:
            t["TOTAL DE TAREFAS"] = (
                pd.to_numeric(t["TOTAL DE TAREFAS"], errors="coerce").fillna(0).clip(lower=0)
            )
        else:
            t["TOTAL DE TAREFAS"] = 0
        fila = t.loc[t["Status Contrato"].isin(["Não Executada", "Pendente"])].copy()
        if fila.empty:
            return pd.DataFrame()
        ag = (
            fila.groupby(["MONITOR", "TÉCNICO", "TIPO_SERVICO", "Status Contrato"], dropna=False)[
                "TOTAL DE TAREFAS"
            ]
            .sum()
            .reset_index()
        )
        pivot = pd.pivot_table(
            ag,
            index=["MONITOR", "TÉCNICO", "TIPO_SERVICO"],
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        ).reset_index()
        for c in ("Não Executada", "Pendente"):
            if c not in pivot.columns:
                pivot[c] = 0
        pivot["Total Fila"] = pivot["Não Executada"] + pivot["Pendente"]
        pivot["Prioridade"] = pivot["Não Executada"] * 2 + pivot["Pendente"]
        pivot["Classificação"] = np.select(
            [
                pivot["Prioridade"].ge(20),
                pivot["Prioridade"].ge(10),
                pivot["Prioridade"].ge(5),
            ],
            ["🔴 CRÍTICO", "🟠 ALTA", "🟡 MÉDIA"],
            default="⚪ BAIXA",
        )
        pivot = pivot.rename(
            columns={
                "MONITOR": "Monitor",
                "TÉCNICO": "Técnico",
                "TIPO_SERVICO": "Segmento",
            }
        )
        return pivot.sort_values("Prioridade", ascending=False).reset_index(drop=True)[
            [
                "Classificação",
                "Monitor",
                "Técnico",
                "Segmento",
                "Não Executada",
                "Pendente",
                "Total Fila",
                "Prioridade",
            ]
        ]

    @staticmethod
    def projetar(
        df: pd.DataFrame,
        probabilidade: float = 0.30,
        grupo: str = "MONITOR",
        incluir_meta: bool = True,
        meta_sla: float = Config.SLA_QUEBRA_MAXIMA,
    ) -> pd.DataFrame:
        obrig = {grupo, "Status Contrato", "TOTAL DE TAREFAS"}
        if not obrig.issubset(df.columns):
            return pd.DataFrame()
        probabilidade, meta_sla = (
            float(np.clip(probabilidade, 0, 1)),
            float(np.clip(meta_sla, 0, 1)),
        )
        r = Motor._pivot_status(df, grupo)
        r["Considerado"] = r["Executada"] + r["Não Executada"]
        r["Alocado"] = r["Considerado"] + r["Pendente"]
        r["Quebra Atual"] = div_segura(r["Não Executada"], r["Considerado"])
        r["Projeção Fechamento"] = div_segura(
            r["Não Executada"] + r["Pendente"] * (1 - probabilidade), r["Alocado"]
        )
        r["Executadas Projetadas"] = r["Executada"] + r["Pendente"] * probabilidade
        conv = div_segura(r["Alocado"] * (1 - meta_sla) - r["Executada"], r["Pendente"]).clip(0, 1)
        r["Conversão Necessária"] = np.where(r["Pendente"].gt(0), conv, 0.0)
        if incluir_meta:
            p = r["Projeção Fechamento"]
            r["Status Meta"] = np.select(
                [p.le(meta_sla), p.le(meta_sla * 1.25), p.le(meta_sla * 1.50)],
                ["✅ Dentro da Meta", "⚠️ Atenção", "🔶 Crítico"],
                default="🚨 Muito Crítico",
            )
        for c in ("Executada", "Não Executada", "Pendente", "Considerado", "Alocado"):
            r[c] = r[c].fillna(0).round().astype(int)
        return r.sort_values("Projeção Fechamento", ascending=False).reset_index(drop=True)

    @staticmethod
    def resumo_gpon(df: pd.DataFrame) -> dict[str, Any]:
        if df is None or df.empty or "FLAG_GPON" not in df.columns:
            return {"total": 0, "sim": 0, "nao": 0, "percentual": 0.0}
        total, sim = len(df), int((df["FLAG_GPON"] == "Sim").sum())
        return {
            "total": total,
            "sim": sim,
            "nao": total - sim,
            "percentual": sim / total * 100 if total > 0 else 0.0,
        }


@st.cache_data(ttl=3600, show_spinner=False)
def _cache_matriz(df: pd.DataFrame) -> pd.DataFrame:
    return Motor._matriz_logic(df)


_METAS_COLUNA_MATRIZ: Final[dict[str, str]] = {
    "NOVOS DOMICÍLIOS": "geral",
    "NOVOS DOMICILIOS": "geral",
    "PME": "geral",
    "MIGRAÇÃO": "migracao",
    "MIGRACAO": "migracao",
    "OUTROS": "geral",
    "QUEBRA GERAL": "geral",
}


def render_matriz_executiva(df: pd.DataFrame, meta_geral: float = Config.SLA_QUEBRA_MAXIMA) -> None:
    if df.empty:
        st.info("Sem dados na Matriz Executiva.")
        return
    metas = {
        k: meta_geral if v == "geral" else Config.SLA_MIGRACAO_MAXIMA
        for k, v in _METAS_COLUNA_MATRIZ.items()
    }
    linhas = ['<div class="matriz-table-container"><table class="matriz-table"><thead><tr>']
    linhas.extend(f"<th>{html_safe(c)}</th>" for c in df.columns)
    linhas.append("</tr></thead><tbody>")
    for _, linha in df.iterrows():
        is_total = str(linha.iloc[0]).strip().upper() == "TOTAL GERAL"
        linhas.append("<tr class='total-row'>" if is_total else "<tr>")
        for i, col in enumerate(df.columns):
            v, cu = linha.iloc[i], str(col).strip().upper()
            if cu in metas:
                try:
                    n = float(v)
                    if not np.isfinite(n):
                        linhas.append(
                            "<td><span style='color:#94A3B8;font-weight:700;'>—</span></td>"
                        )
                    else:
                        cls = "badge-meta-ok" if n <= metas[cu] else "badge-meta-nok"
                        # Motor._matriz_logic retorna frações (0–1), diferente do
                        # helper de apresentação, cujo padrão recebe pontos percentuais.
                        linhas.append(
                            f"<td><span class='{cls}'>{fmt_pct_br(n, ja_e_pct=False)}</span></td>"
                        )
                except (TypeError, ValueError):
                    linhas.append(f"<td>{html_safe(v)}</td>")
            elif cu in {"TOTAL TASKS", "TOTAL_TASKS"}:
                linhas.append(f"<td><strong>{fmt_int_br(v)}</strong></td>")
            else:
                conteudo = (
                    html_safe(v) if not is_missing(v) else "<span style='color:#94A3B8;'>—</span>"
                )
                linhas.append(f"<td>{conteudo}</td>")
        linhas.append("</tr>")
    linhas.append("</tbody></table></div>")
    st.markdown("".join(linhas), unsafe_allow_html=True)


def render_bloco_importacao(dados_prontos: bool = False) -> bool:
    st.markdown(
        """<div style="margin-top:6px;margin-bottom:4px"><span class="import-header-title">Importação de Dados</span><span class="import-header-badge">EXCEL, CSV OU AUTO</span></div><div class="import-header-sub">Envie a base consolidada de O.S. ou aguarde o robô detectar o arquivo automaticamente.</div><div class="import-header-line"></div>""",
        unsafe_allow_html=True,
    )
    if not dados_prontos:
        return False
    st.markdown(
        '<div class="import-alert-green"><span>Dados carregados e processados. O relatório está pronto.</span></div>',
        unsafe_allow_html=True,
    )
    return st.button(
        "Atualizar relatório",
        type="primary",
        width="stretch",
        key="btn_atualizar_relatorio",
    )


def render_hero_quebra(
    titulo: str,
    subtitulo: str,
    regioes: list[str],
    total: int,
    badge: str = "",
    origem: str = "",
) -> None:
    """Cabeçalho da página: hero do Design System + resumo das bases analisadas.

    Antes a página montava o próprio HTML do hero (``.hero-card``/``.base-info``)
    com CSS local; hoje usa :func:`components.componentes.render_hero` — o mesmo
    cabeçalho dos outros dashboards — e mantém as bases/regiões em legenda.
    """
    render_hero_portal(titulo, subtitulo, badge=badge)
    nomes = sorted({str(regiao).upper().strip() for regiao in regioes if str(regiao).strip()})
    if total > 0 and nomes:
        st.caption(
            f"Bases analisadas: {', '.join(nomes)} · {fmt_int_br(total)} registros"
            + (f" · fonte: {origem}" if origem else "")
        )


_PALAVRAS_PCT_TABELA: Final[tuple[str, ...]] = (
    "QUEBRA",
    "FECHAMENTO",
    "%",
    "PROJEÇÃO",
    "PROJECAO",
    "CONVERSÃO",
    "CONVERSAO",
    "ACUMULADO",
)
_PALAVRAS_INT_TABELA: Final[tuple[str, ...]] = (
    "TOTAL",
    "VOLUME",
    "TAREFAS",
    "PRIORIDADE",
    "EXECUTADA",
    "TASKS",
    "ALOCADO",
    "CONSIDERADO",
)


def render_tabela(
    df: pd.DataFrame,
    titulo: str,
    icone: str,
    color_col: str | None = None,
    meta: float = Config.SLA_QUEBRA_MAXIMA,
    height: int = 400,
) -> None:
    st.markdown(
        f"""<div style="background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:.9rem 1rem;margin-bottom:.5rem"><div style="font-size:.95rem;font-weight:700;color:#0F172A;display:flex;align-items:center;gap:.5rem"><span>{html_safe(icone)}</span><span>{html_safe(titulo)}</span><span style="font-size:.68rem;background:#EFF6FF;color:#1D4ED8;padding:.18rem .55rem;border-radius:999px">{len(df)} registros</span></div></div>""",
        unsafe_allow_html=True,
    )
    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return
    formatos = {}
    for col in df.columns:
        cu = str(col).upper()
        if any(k in cu for k in _PALAVRAS_PCT_TABELA):
            formatos[str(col)] = "{:.2%}"
        elif any(k in cu for k in _PALAVRAS_INT_TABELA):
            formatos[str(col)] = "{:,.0f}"
    regras = (
        {
            "coluna": color_col,
            "meta": meta,
            "acima_meta": {"bg": "#FEF2F2", "text": "#991B1B", "bold": True},
            "abaixo_meta": {"bg": "#ECFDF5", "text": "#166534", "bold": True},
        }
        if color_col and color_col in df.columns
        else None
    )
    render_table_html(
        df,
        fmt=formatos,
        color_rules=regras,
        colunas_num=df.select_dtypes(include=np.number).columns.astype(str).tolist(),
        height=height,
    )


def render_card_gpon(df: pd.DataFrame) -> None:
    r = Motor.resumo_gpon(df)
    st.markdown(
        f"""<div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;margin-bottom:1rem;padding:1rem 1.2rem;border:1px solid #BFDBFE;border-radius:12px;background:#EFF6FF"><div><div style="color:#475569;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase">Indicador GPON</div><div style="margin-top:.25rem;color:#1E3A8A;font-size:1.45rem;font-weight:750">{fmt_int_br(r["sim"])}</div><div style="color:#475569;font-size:.78rem">{r["percentual"]:.1f}% com GPON habilitado</div></div><div style="text-align:right"><div style="color:#64748B;font-size:.7rem">Total analisado</div><div style="color:#0F172A;font-size:1.1rem;font-weight:700">{fmt_int_br(r["total"])}</div></div></div>""",
        unsafe_allow_html=True,
    )


def view_resumo_executivo(df: pd.DataFrame, meta_sla: float) -> None:
    col_tipo = str(df.attrs.get("tipo_servico_coluna", ""))
    tipos_proc = set(
        df.get("TIPO_SERVICO", pd.Series(dtype="object")).dropna().astype(str).unique()
    )
    if not col_tipo:
        st.warning(
            "A base não possui coluna identificável de tipo de serviço. Os registros foram classificados como 'Outros'."
        )
    if tipos_proc and tipos_proc <= {"Outros"}:
        originais = df.attrs.get("valores_tipo_servico_originais", {})
        st.warning(
            "A coluna de segmento foi encontrada, mas nenhum valor foi reconhecido como Novos Domicílios, PME ou Migração."
        )
        if isinstance(originais, dict) and originais:
            st.caption("Valores originais encontrados: " + ", ".join(list(originais.keys())[:10]))
    if "FLAG_GPON" in df.columns:
        render_card_gpon(df)
    matriz = Motor.matriz_resumo(df)
    if matriz.empty:
        st.warning("Dados insuficientes para montar a Matriz Executiva.")
        return
    if "Monitor" in matriz.columns:
        mask = matriz["Monitor"].astype(str).str.strip().str.upper().eq("TOTAL GERAL")
        matriz = pd.concat([matriz.loc[~mask], matriz.loc[mask]], ignore_index=True)
    render_matriz_executiva(matriz, meta_geral=meta_sla)
    st.download_button(
        "Baixar matriz (Excel)",
        data=gerar_excel_formatado(
            matriz, "Matriz_Resumo", autofiltro=True, colunas_pct=_PALAVRAS_PCT_EXCEL
        ),
        file_name="Matriz_Resumo_Quebra.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )


def view_analise_detalhada(
    df: pd.DataFrame,
    p_ot: float,
    p_base: float,
    p_pess: float,
    min_aloc: float,
    meta_sla: float,
) -> None:
    if CRITERIOS.disponivel and CRITERIOS.render_painel:
        with st.expander("Critérios de classificação", expanded=False):
            CRITERIOS.render_painel(df)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Projeções", "Projeção personalizada", "Rankings", "Causas raiz", "Backoffice"]
    )
    with tab1:
        cabecalho_secao("Cenários de Projeção de Fechamento", ancora=False)
        render_tabela(
            Motor.tabela_cenarios(df, "MONITOR", p_ot, p_base, p_pess, min_aloc),
            "Projeção por Monitor",
            "",
            color_col="Fechamento Base",
            meta=meta_sla,
        )
    with tab2:
        cabecalho_secao("Projeção Personalizada", ancora=False)
        c1, c2 = st.columns(2)
        with c1:
            prob = st.slider("Probabilidade de Conversão (%)", 0, 100, 30, step=5) / 100
        with c2:
            grupo = st.selectbox("Agrupar por", ["MONITOR", "TÉCNICO", "REGIÃO"])
        proj = Motor.projetar(df, probabilidade=prob, grupo=grupo, meta_sla=meta_sla)
        render_tabela(
            proj,
            f"Projeção por {grupo}",
            "",
            color_col="Projeção Fechamento",
            meta=meta_sla,
        )
        if not proj.empty:
            k1, k2, k3, k4 = st.columns(4)
            total = len(proj)
            dentro = int(proj["Projeção Fechamento"].le(meta_sla).sum())
            atencao = int(
                (
                    proj["Projeção Fechamento"].gt(meta_sla)
                    & proj["Projeção Fechamento"].le(meta_sla * 1.25)
                ).sum()
            )
            critico = int(proj["Projeção Fechamento"].gt(meta_sla * 1.25).sum())
            conv_med = float(proj["Conversão Necessária"].mean())

            def pct(x: int) -> str:
                return f"{x / total:.0%}" if total else "0%"

            render_kpi_sm(k1, "Dentro da Meta", str(dentro), pct(dentro), "verde")
            render_kpi_sm(k2, "Atenção", str(atencao), pct(atencao), "laranja")
            render_kpi_sm(k3, "Crítico", str(critico), pct(critico), "vermelho")
            render_kpi_sm(k4, "Conversão Média", f"{conv_med:.1%}", "Para atingir meta", "azul")
    with tab3:
        cabecalho_secao("Técnicos Mais Críticos", ancora=False)
        render_tabela(
            Motor.tecnicos_criticos(df, "TODOS", p_base, min_aloc, 20, p_ot, p_pess),
            "Top 20 Técnicos com Maior Risco",
            "",
            color_col="Fechamento Base",
            meta=meta_sla,
        )
    with tab4:
        cabecalho_secao("Análise de Causa Raiz", ancora=False)
        col = DF.buscar_coluna(
            df, ("CÓD DE BAIXA 1", "COD DE BAIXA 1", "MOTIVO DE BAIXA", "COD_BAIXA")
        )
        if col:
            render_tabela(Motor.causa_raiz(df, col, 10), "Pareto de Motivos", "")
        else:
            st.warning("Coluna de Código/Motivo de Baixa não encontrada.")
    with tab5:
        cabecalho_secao("Gestão de Fila (Backoffice)", ancora=False)
        render_tabela(Motor.backoffice_fila(df), "Fila Priorizada", "")


def view_auditoria(df: pd.DataFrame) -> None:
    cabecalho_secao(
        "Auditoria de Processamento",
        icone="rule",
        subtitulo="Rastreabilidade do ETL aplicado à base carregada.",
        ancora=False,
    )
    total = len(df)
    importado = int(df.attrs.get("total_importado", total))
    rem_status = int(df.attrs.get("removidos_suspensos_cancelados", 0))
    rem_contrato = int(df.attrs.get("removidos_contrato", 0))
    gpon_sim = int(df.attrs.get("flag_gpon_sim_count", 0))
    k1, k2, k3, k4 = st.columns(4)
    render_kpi_sm(k1, "Importados", fmt_int_br(importado), tema="azul")
    render_kpi_sm(k2, "Processados", fmt_int_br(total), tema="verde")
    render_kpi_sm(k3, "Removidos por status", fmt_int_br(rem_status), tema="laranja")
    render_kpi_sm(k4, "Contratos inválidos", fmt_int_br(rem_contrato), tema="vermelho")
    st.caption(f"Arquivo de origem: {df.attrs.get('arquivo_origem', 'Não identificado')}")
    st.caption(
        f"Coluna de tipo de serviço: {df.attrs.get('tipo_servico_coluna', 'Não identificada')}"
    )
    if "FLAG_GPON" in df.columns:
        st.markdown("#### Indicador GPON")
        g1, g2 = st.columns(2)
        pct_sim = gpon_sim / total * 100 if total > 0 else 0.0
        pct_nao = (total - gpon_sim) / total * 100 if total > 0 else 0.0
        render_kpi_sm(g1, "FLAG_GPON = Sim", fmt_int_br(gpon_sim), f"{pct_sim:.1f}%", tema="verde")
        render_kpi_sm(
            g2,
            "FLAG_GPON = Não",
            fmt_int_br(total - gpon_sim),
            f"{pct_nao:.1f}%",
            tema="cinza",
        )
    if "TIPO_SERVICO" in df.columns:
        st.markdown("### Distribuição de tipo de serviço")
        dist = df["TIPO_SERVICO"].value_counts().reset_index()
        dist.columns = ["Segmento", "Registros"]
        dist["%"] = (dist["Registros"] / total * 100).round(1).astype(str) + "%"
        st.dataframe(dist, hide_index=True, width="stretch")
        nd = int(dist.loc[dist["Segmento"] == "Novos Domicílios", "Registros"].sum())
        pme = int(dist.loc[dist["Segmento"] == "PME", "Registros"].sum())
        if nd == 0 and pme == 0:
            st.error(
                "Novos Domicílios e PME estão zerados. Verifique a coluna de tipo de serviço e os critérios de classificação."
            )
    if (
        CRITERIOS.disponivel
        and CRITERIOS.detect_tipo_os
        and CRITERIOS.detect_habilidade
        and CRITERIOS.detect_flag_gpon
    ):
        with st.expander("Diagnóstico de critérios", expanded=False):
            col_tipo, col_hab, col_gpon = (
                CRITERIOS.detect_tipo_os(df),
                CRITERIOS.detect_habilidade(df),
                CRITERIOS.detect_flag_gpon(df),
            )
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "TIPO O.S 1",
                "Encontrada" if col_tipo else "Não encontrada",
                col_tipo or "—",
            )
            c2.metric(
                "HABILIDADE",
                "Encontrada" if col_hab else "Não encontrada",
                col_hab or "—",
            )
            c3.metric(
                "FLAG_GPON",
                "Encontrada" if col_gpon else "Não encontrada",
                col_gpon or "—",
            )
            if col_tipo:
                st.markdown("Amostras de tipo de O.S.")
                st.code(df[col_tipo].dropna().astype(str).unique()[:15].tolist())
            if col_hab:
                st.markdown("Amostras de habilidade")
                st.code(df[col_hab].dropna().astype(str).unique()[:15].tolist())
    with st.expander("Visualizar amostra da base processada", expanded=False):
        st.dataframe(df.head(200), width="stretch", hide_index=True)


_CHAVES_SESSAO: Final[tuple[str, ...]] = (
    "df_memoria",
    "df_memoria_raw",
    "arquivo_processado",
    "origem_dados",
    "_robo_df_pronto",
    "_robo_nome_arquivo",
    "_robo_dados_disponiveis",
    "robo_hora_sucesso",
    "_quebra_robo_processado_sig",
)
_CHAVES_ROBO: Final[tuple[str, ...]] = (
    "robo_processado_sig",
    "robo_candidato_sig",
    "robo_candidato_stable",
    "robo_ultimo_processado_path",
    "robo_ultimo_processado_mtime",
    "robo_arquivos_processados",
    "robo_bases_carregadas",
    "robo_base_detectada",
    "robo_motores",
    "robo_duplicatas_removidas",
    "_robo_aguardando_lock",
)
_CHAVES_ATIVOS: Final[tuple[str, ...]] = ("df_gs_manual", "arquivo_ativos_processado")


def limpar_sessao(incluir_ativos: bool = True) -> None:
    for k in (
        list(_CHAVES_SESSAO) + list(_CHAVES_ROBO) + (list(_CHAVES_ATIVOS) if incluir_ativos else [])
    ):
        st.session_state.pop(k, None)
    st.session_state["upload_nonce"] = int(st.session_state.get("upload_nonce", 0)) + 1


def _sidebar_ativos(nonce: int) -> None:
    with st.sidebar.expander("Configurações e Lista de Ativos", expanded=False):
        st.markdown("### Lista de Ativos")
        upload = st.file_uploader(
            "Upload de contingência de ativos",
            type=["csv", "xlsx", "xlsm"],
            key=f"uploaded_ativos_manual_{nonce}",
        )
        if upload:
            try:
                b = upload.getvalue()
                hid = hash_upload(upload.name, b)
                if st.session_state.get("arquivo_ativos_processado") != hid:
                    proc = DataLoader.processar_lista_ativos(DataLoader.ler_arquivo(b, upload.name))
                    if proc.empty:
                        raise ValueError("A base de ativos não possui coluna LOGIN válida.")
                    (
                        st.session_state["df_gs_manual"],
                        st.session_state["arquivo_ativos_processado"],
                    ) = (proc, hid)
                    st.toast(f"{len(proc)} ativos carregados.")
            except Exception as erro:
                st.error(f"Erro ao processar base de ativos: {erro}")
        if st.button("Reiniciar aplicação", width="stretch", type="secondary"):
            limpar_sessao(True)
            DataLoader.ler_arquivo.clear()
            DataLoader.buscar_gsheets.clear()
            _cache_matriz.clear()
            st.rerun()
        if st.button("Limpar cache", width="stretch", type="secondary"):
            limpar_sessao(True)
            DataLoader.ler_arquivo.clear()
            DataLoader.buscar_gsheets.clear()
            _cache_matriz.clear()
            st.rerun()


def _sidebar_filtros() -> tuple[float, float, float, float]:
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Filtros de projeção")
    p_ot = st.sidebar.slider("Probabilidade otimista (%)", 0, 100, 15, step=5) / 100
    p_base = st.sidebar.slider("Probabilidade base (%)", 0, 100, 30, step=5) / 100
    p_pess = st.sidebar.slider("Probabilidade pessimista (%)", 0, 100, 50, step=5) / 100
    min_aloc = float(st.sidebar.number_input("Mínimo de alocações", min_value=1, value=5))
    if not (p_ot <= p_base <= p_pess):
        st.sidebar.warning("O esperado é: otimista ≤ base ≤ pessimista.")
    return p_ot, p_base, p_pess, min_aloc


def _aplicar_etl_robo_global(df_ativos: pd.DataFrame) -> None:
    """Aplica o ETL da página sobre a saída bruta do robô global, uma vez por arquivo."""
    origem = str(st.session_state.get("origem_dados", ""))
    if not origem.startswith("Robô Local"):
        return

    df_raw = df_sessao("df_memoria_raw")
    if df_raw is None or df_raw.empty:
        df_raw = df_sessao("df_memoria")
    if df_raw is None or df_raw.empty:
        return

    assinatura = st.session_state.get("robo_processado_sig")
    if assinatura is None:
        assinatura = (
            st.session_state.get("robo_ultimo_processado_path"),
            st.session_state.get("robo_ultimo_processado_mtime"),
        )
    if st.session_state.get("_quebra_robo_processado_sig") == assinatura:
        return

    DataLoader.callback_robo_etl(df_raw, df_ativos)
    st.session_state["_quebra_robo_processado_sig"] = assinatura


def _processar_upload(upload: Any, df_ativos: pd.DataFrame) -> None:
    if not upload:
        return
    try:
        b = upload.getvalue()
        hid = hash_upload(upload.name, b)
        if st.session_state.get("arquivo_processado") == hid:
            return
        with st.spinner(f"Processando {upload.name}..."):
            raw = DataLoader.ler_arquivo(b, upload.name)
            base = DataLoader.preparar_base(raw, df_ativos, filename=upload.name)
            if base.empty:
                raise ValueError("Nenhuma O.S. válida permaneceu após o tratamento.")
            st.session_state.update(
                {
                    "df_memoria_raw": raw,
                    "df_memoria": base,
                    "arquivo_processado": hid,
                    "origem_dados": f"Upload ({upload.name})",
                    "_robo_dados_disponiveis": True,
                    "mensagem_flash": "Base processada com sucesso.",
                }
            )
            st.rerun()
    except Exception as erro:
        st.error(f"Erro no processamento do arquivo: {erro}")


def _render_upload_os(dados_prontos: bool, nonce: int) -> Any:
    if not dados_prontos:
        return st.file_uploader(
            "Carregar base de O.S. manualmente",
            type=["csv", "xlsx", "xlsm"],
            key=f"upload_os_principal_{nonce}",
        )
    with st.expander("Substituir base de O.S. manualmente", expanded=False):
        return st.file_uploader(
            "Upload manual O.S.",
            type=["csv", "xlsx", "xlsm"],
            key=f"upload_os_substituir_{nonce}",
        )


#: Seções ancoradas do sumário (títulos usados em ``cabecalho_secao``).
SECOES_PAGINA: tuple[str, ...] = (
    "Resumo executivo",
    "Análise detalhada",
    "Auditoria",
    "Exportação",
)


def main() -> None:
    # O CSS de shell (body/sidebar/hero/KPI/tabelas) pertence ao streamlit_app.py
    # + components.css_global; aqui entra só o CSS específico desta página
    # (bloco de importação e matriz executiva), compartilhado em css_paginas.
    aplicar_css_quebra_operacional()
    msg = st.session_state.pop("mensagem_flash", "")
    if msg:
        st.success(str(msg))

    st.session_state.setdefault("upload_nonce", 0)
    nonce = int(st.session_state["upload_nonce"])
    _sidebar_ativos(nonce)
    ativos_sessao = df_sessao("df_gs_manual")
    df_ativos = (
        ativos_sessao
        if ativos_sessao is not None and not ativos_sessao.empty
        else DataLoader.buscar_gsheets()
    )
    if df_ativos is None:
        df_ativos = pd.DataFrame()
    if not df_ativos.empty:
        st.sidebar.caption(f"Lista de ativos: {len(df_ativos)} registros")
    else:
        st.sidebar.warning(
            "Lista de ativos indisponível. Utilize o upload manual nas configurações."
        )
    _aplicar_etl_robo_global(df_ativos)

    df_atual = df_sessao("df_memoria")
    dados_prontos = df_atual is not None and not df_atual.empty
    if render_bloco_importacao(dados_prontos):
        st.session_state["mensagem_flash"] = "Relatório atualizado com sucesso."
        st.rerun()
    upload = _render_upload_os(dados_prontos, nonce)
    _processar_upload(upload, df_ativos)

    df = df_sessao("df_memoria")
    if df is None or df.empty:
        render_insight(
            "Carregue uma base de O.S. para iniciar a análise — use o robô local "
            "(barra lateral) ou o upload manual acima.",
            tipo="alerta",
            titulo="Sem base carregada",
        )
        fechar_dashboard()
        return

    p_ot, p_base, p_pess, min_aloc = _sidebar_filtros()
    regioes = (
        sorted(df["REGIÃO"].dropna().astype(str).unique().tolist())
        if "REGIÃO" in df.columns
        else ["TODAS"]
    )

    # 1) Cabeçalho e contexto — padrão do portal (hero + chips + sumário).
    abrir_dashboard(
        "Quebra Geral",
        secoes=SECOES_PAGINA,
        hero=render_hero_quebra,
        hero_kwargs={
            "titulo": "Super Relatório Corporativo",
            "subtitulo": "Análise unificada de desempenho operacional",
            "regioes": regioes,
            "total": len(df),
            "badge": "TOTALE OPERACIONAL",
            "origem": str(st.session_state.get("origem_dados", "Base carregada")),
        },
        chips={
            "Origem": str(st.session_state.get("origem_dados", "Base carregada")),
            "Regiões": len(regioes) if regioes != ["TODAS"] else "todas",
        },
        registros=len(df),
    )

    if "TÉCNICO" in df.columns:
        nao_mapeados = int(df["TÉCNICO"].eq("NÃO MAPEADO").sum())
        if nao_mapeados > 0:
            pct = nao_mapeados / len(df) * 100
            st.warning(
                f"Aviso de integração: {nao_mapeados} O.S. ({pct:.1f}% do volume ativo) sem correspondência na Lista de Ativos."
            )
        else:
            st.success("Todos os logins estão mapeados na Lista de Ativos.")

    # 2) Detalhamento por visão (âncoras do sumário)
    aba = st.radio(
        "Navegação",
        list(SECOES_PAGINA[:3]),
        horizontal=True,
        key="quebra_geral_navegacao",
    )
    cabecalho_secao(
        aba,
        icone="monitoring"
        if aba == "Resumo executivo"
        else "search"
        if aba == "Análise detalhada"
        else "rule",
        subtitulo=(
            "Matriz executiva de SLA por segmento."
            if aba == "Resumo executivo"
            else "Cenários de projeção, causa raiz e gestão de fila."
            if aba == "Análise detalhada"
            else "Rastreabilidade do ETL aplicado à base carregada."
        ),
    )
    rotas: dict[str, Callable[[], None]] = {
        "Resumo executivo": lambda: view_resumo_executivo(df, Config.SLA_QUEBRA_MAXIMA),
        "Análise detalhada": lambda: view_analise_detalhada(
            df, p_ot, p_base, p_pess, min_aloc, Config.SLA_QUEBRA_MAXIMA
        ),
        "Auditoria": lambda: view_auditoria(df),
    }
    rotas[aba]()

    # 3) Exportação e rodapé (padrão do portal)
    secao_exportacao(
        df,
        nome_arquivo="quebra_geral",
        chave="quebra_geral",
        titulo="Exportação",
        subtitulo="Base processada com as colunas de classificação do ETL.",
    )
    fechar_dashboard()


if __name__ == "__main__":
    main()
