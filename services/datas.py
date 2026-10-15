"""Motor de datas para dashboard_meta.py (sem dependência de Streamlit).

Política:
- ISO: ano/mês/dia; BR: dia/mês/ano, com ano de quatro dígitos.
- Datas sem fuso mantêm o horário original.
- Datas com fuso são convertidas para America/Sao_Paulo e ficam sem tz.
- Valores inválidos viram NaT; números NÃO são interpretados como datas.
- Seriais Excel só são aceitos mediante aceitar_serial_excel=True.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Iterable, TypeAlias
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pandas._libs.tslibs.nattype import NaTType

# pandas 2.0+: NaT é um tipo próprio, não uma subclasse de Timestamp.
DataConvertida: TypeAlias = pd.Timestamp | NaTType

logger = logging.getLogger("dashboard_meta")
TZ_PADRAO = "America/Sao_Paulo"
VAZIOS = {"", "NAN", "NAT", "NONE", "NULL", "<NA>", "NA", "N/A", "-"}
ISO = re.compile(r"^(\d{4})[-/](\d{2})[-/](\d{2})(.*)$")
BR = re.compile(r"^(\d{1,2})([/.-])(\d{1,2})\2(\d{4})(.*)$")
HORA = re.compile(
    r"^[ T]\d{2}:\d{2}(?::\d{2}(?:[.,]\d{1,9})?)?" r"(?:Z|[+-]\d{2}:?\d{2})?$",
    re.IGNORECASE,
)


def _timestamp_local(valor: Any, timezone: str) -> DataConvertida:
    ts = pd.Timestamp(valor)
    if pd.isna(ts):
        return pd.NaT
    if ts.tzinfo is not None:
        ts = ts.tz_convert(ZoneInfo(timezone)).tz_localize(None)
    # Impõe intervalo representável por datetime64[ns].
    return ts.as_unit("ns")


@lru_cache(maxsize=100_000)
def _parse_texto(texto: str, timezone: str) -> DataConvertida:
    if texto.upper() in VAZIOS:
        return pd.NaT
    match_iso = ISO.fullmatch(texto)
    match_br = BR.fullmatch(texto) if match_iso is None else None
    if match_iso:
        ano, mes, dia, sufixo = match_iso.groups()
    elif match_br:
        dia, _, mes, ano, sufixo = match_br.groups()
    else:
        return pd.NaT
    if sufixo and not HORA.fullmatch(sufixo):
        return pd.NaT
    canonico = f"{ano}-{int(mes):02d}-{int(dia):02d}{sufixo}"
    canonico = canonico.replace(",", ".")
    if canonico.endswith(("z", "Z")):
        canonico = canonico[:-1] + "+00:00"
    try:
        # Sem dayfirst e sem inferência: o texto já está em ISO inequívoco.
        return _timestamp_local(canonico, timezone)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def converter_serie_datas(
    serie: pd.Series,
    *,
    timezone: str = TZ_PADRAO,
    aceitar_serial_excel: bool = False,
) -> pd.Series:
    """Converte formatos mistos por valor e preserva o índice da série."""
    ZoneInfo(timezone)  # Falha cedo se a configuração de fuso for inválida.

    def converter(valor: Any) -> DataConvertida:
        if valor is None or valor is pd.NA or valor is pd.NaT:
            return pd.NaT
        if isinstance(valor, (pd.Timestamp, datetime, date, np.datetime64)):
            try:
                return _timestamp_local(valor, timezone)
            except (ValueError, TypeError, OverflowError):
                return pd.NaT
        if isinstance(valor, (int, float, np.number)):
            if aceitar_serial_excel:
                try:
                    numero = float(valor)
                    if np.isfinite(numero) and 1 <= numero < 100_000:
                        return _timestamp_local(
                            pd.to_datetime(numero, unit="D", origin="1899-12-30"),
                            timezone,
                        )
                except (ValueError, TypeError, OverflowError):
                    pass
            return pd.NaT
        texto = str(valor).strip()
        if aceitar_serial_excel and re.fullmatch(r"\d{1,5}(?:\.\d+)?", texto):
            return converter(float(texto))
        return _parse_texto(texto, timezone)

    valores = [converter(v) for v in serie]
    return pd.Series(valores, index=serie.index, name=serie.name, dtype="datetime64[ns]")


def garantir_datetime_auto(
    df: pd.DataFrame, col: str = "DATA", nome_fonte: str = ""
) -> pd.DataFrame:
    resultado = df.copy()
    if col not in resultado.columns or resultado.empty:
        return resultado
    original = resultado[col]
    parsed = converter_serie_datas(original)
    resultado[col] = parsed
    nao_vazios = original.notna() & ~original.astype(str).str.strip().str.upper().isin(VAZIOS)
    invalidas = int((nao_vazios & parsed.isna()).sum())
    logger.info(
        "Datas %s/%s: %d válidas; %d inválidas não vazias.",
        nome_fonte,
        col,
        int(parsed.notna().sum()),
        invalidas,
    )
    return resultado


def garantir_datetime(df: pd.DataFrame, col: str = "DATA", origem: str = "") -> pd.DataFrame:
    # Mantém a assinatura usada pelo render_tabela_segura.
    # 'origem' identifica a fonte; não altera a ordem dia/mês.
    return garantir_datetime_auto(df, col=col, nome_fonte=origem)


def detectar_coluna_data(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    nomes = (
        "DATA",
        "DATE",
        "DT",
        "DATA_OS",
        "DATA_EXECUCAO",
        "DT_EXECUCAO",
        "DATA_FINALIZACAO",
        "DT_FINALIZACAO",
        "DATA_CONSULTIVO",
        "DT_CRIACAO",
        "DATA_CRIACAO",
        "DATA_ATENDIMENTO",
        "DATA_SOLICITACAO",
        "DATA_ABERTURA",
        "DATA HORA",
        "DATA/HORA",
        "TIMESTAMP",
        "CREATED_AT",
        "UPDATED_AT",
        "PERIODO",
    )
    colunas = {str(c).strip().upper(): c for c in df.columns}
    for nome in nomes:
        if nome in colunas:
            return colunas[nome]
    # Não confunde palavras como QUANTIDADE com uma coluna de data.
    for col in df.columns:
        tokens = set(re.split(r"[\s_/.-]+", str(col).strip().upper()))
        if tokens & {"DATA", "DATE", "DT", "TIMESTAMP"}:
            return col
    # Verificação de conteúdo usa o mesmo parser, nunca timestamps numéricos.
    for col in df.columns:
        amostra = df[col].dropna().head(30)
        if len(amostra) >= 3:
            validas = converter_serie_datas(amostra).notna()
            if int(validas.sum()) >= 3 and float(validas.mean()) >= 0.8:
                return col
    return None


def data_ancora_projecao(df: pd.DataFrame, coluna_data: str = "DATA") -> date | None:
    if df.empty or coluna_data not in df.columns:
        return None
    datas = converter_serie_datas(df[coluna_data]).dropna()
    return None if datas.empty else datas.max().date()


def limites_datas_disponiveis(
    fontes: Iterable[pd.DataFrame], hoje: date
) -> tuple[date, date, date]:
    """Retorna (mínimo disponível, máximo disponível, início padrão).

    Uma fonte vazia ou sem DATA não apaga as datas da outra fonte.
    O padrão é o último mês disponível, como no dashboard original.
    """
    partes = [
        converter_serie_datas(df["DATA"]).dropna()
        for df in fontes
        if "DATA" in df.columns and not df.empty
    ]
    partes = [s for s in partes if not s.empty]
    if not partes:
        return hoje.replace(day=1), hoje, hoje.replace(day=1)
    datas = pd.concat(partes, ignore_index=True)
    minimo, maximo = datas.min().date(), datas.max().date()
    return minimo, maximo, max(minimo, maximo.replace(day=1))


def normalizar_janela_datas(valor: Any) -> tuple[date, date] | None:
    """Uma seleção incompleta retorna None; não vira um recorte de um dia."""
    if not isinstance(valor, (tuple, list)) or len(valor) != 2:
        return None
    inicio, fim = valor
    if not isinstance(inicio, date) or not isinstance(fim, date):
        return None
    if isinstance(inicio, datetime):
        inicio = inicio.date()
    if isinstance(fim, datetime):
        fim = fim.date()
    if inicio > fim:
        return None
    return inicio, fim


def validar_estado_janela(
    valor: Any,
    minimo: date,
    maximo: date,
) -> bool:
    """Valida o estado salvo do date_input antes de criar o widget.

    Aceita:
    - () — seleção ainda vazia;
    - (inicio,) — seleção incompleta, dentro dos limites;
    - (inicio, fim) — seleção completa, ordenada e dentro dos limites.

    Rejeita NaT, tipos inválidos, datas fora dos limites e ordem invertida.
    Não interpreta strings como datas.
    """

    def converter_limite(item: Any) -> date | None:
        # NaT precisa ser rejeitado antes do teste de datetime/date.
        if item is pd.NaT:
            return None
        if isinstance(item, datetime):
            return item.date()
        if isinstance(item, date):
            return item
        return None

    minimo_validado = converter_limite(minimo)
    maximo_validado = converter_limite(maximo)

    if minimo_validado is None or maximo_validado is None:
        return False
    if minimo_validado > maximo_validado:
        return False

    if not isinstance(valor, (tuple, list)) or len(valor) > 2:
        return False

    datas: list[date] = []

    for item in valor:
        limite = converter_limite(item)
        if limite is None:
            return False
        if not minimo_validado <= limite <= maximo_validado:
            return False
        datas.append(limite)

    return len(datas) < 2 or datas[0] <= datas[1]


def converter_serie_datas_mdy(
    serie: pd.Series,
    *,
    timezone: str = TZ_PADRAO,
) -> pd.Series:
    """Converte datas de uma fonte explicitamente MM/DD/AAAA.

    Exemplos:
        10/1/2026  -> 2026-10-01
        10/3/2026  -> 2026-10-03
        10/13/2026 -> 2026-10-13

    Datas ISO e objetos datetime permanecem com sua ordem original.
    Valores inválidos viram NaT.

    Aplicar na carga, antes do parser BR. Não corrige Timestamp
    que já tenha sido interpretado com dia e mês invertidos.
    """

    def canonizar(valor: Any) -> Any:
        if not isinstance(valor, str):
            return valor

        texto = valor.strip()
        match = BR.fullmatch(texto)

        if match is None:
            return texto

        mes, _, dia, ano, sufixo = match.groups()

        # Converte MM/DD/AAAA em ISO inequívoco.
        # O parser comum valida a data, o horário e o fuso.
        return f"{ano}-{int(mes):02d}-{int(dia):02d}{sufixo}"

    return converter_serie_datas(
        serie.map(canonizar),
        timezone=timezone,
    )


def mascara_periodo(serie: pd.Series, inicio: date, fim: date) -> pd.Series:
    """Inclui todo o último dia, inclusive registros com horário."""
    datas = converter_serie_datas(serie).dt.normalize()
    return datas.between(pd.Timestamp(inicio), pd.Timestamp(fim), inclusive="both").fillna(False)
