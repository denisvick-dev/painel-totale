"""
services/texto.py
=================
Normalização de texto, colunas e identificadores — camada pura (sem Streamlit).

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
Cada dashboard reimplementava o mesmo conjunto de helpers: ``normalizar_texto``,
``remover_acentos``, ``normalizar_login``, ``buscar_coluna``, ``fmt_int``,
``html_safe``... Onze cópias quase idênticas, com diferenças sutis (umas
removiam o ``.0`` final do login, outras não; umas escapavam HTML, outras não).
Divergência nesse tipo de função vira bug silencioso de *join*: a base de ativos
normaliza o login de um jeito e a base de produção normaliza de outro, e o
cruzamento simplesmente não casa.

Aqui vive **uma** implementação, vetorial quando importa (``normalizar_serie``,
``buscar_coluna``) e escalar quando é para um rótulo (``formatar_inteiro``).

Regras do módulo:

* nenhuma dependência de Streamlit — pode ser importado em testes, no robô e na
  camada de serviços;
* nada de exceção por valor estranho: ``None``, ``NaN`` e objetos viram ``""``;
* ``normalizar_login`` é a função canônica de identidade de técnico no portal —
  sempre a use dos dois lados de um *join*.
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
import pandas as pd

VERSAO_TEXTO = "1.0.0"

#: Tokens que representam "sem valor" nas bases do portal.
VALORES_AUSENTES: frozenset[str] = frozenset(
    {
        "",
        "-",
        "--",
        "N/A",
        "NA",
        "NAN",
        "NAT",
        "NONE",
        "NULL",
        "<NA>",
        "NENHUM",
        "NENHUMA",
        "VAZIO",
    }
)

_RE_ESPACOS = re.compile(r"\s+")
_RE_ALFANUMERICO = re.compile(r"[^A-Z0-9]+")
_RE_DECIMAL_SUJO = re.compile(r"(?<=\d)\.0+$")

__all__ = [
    "VALORES_AUSENTES",
    "colunas_presentes",
    "VERSAO_TEXTO",
    "buscar_coluna",
    "escapar_html",
    "formatar_inteiro",
    "formatar_numero",
    "formatar_percentual",
    "limpar_nome_coluna",
    "normalizar_chave",
    "normalizar_coluna",
    "normalizar_login",
    "normalizar_serie",
    "normalizar_texto",
    "sem_acento",
    "valor_nan",
    "valor_vazio",
]


# ====================================================
# 🔤 BLOCO 1: NORMALIZAÇÃO ESCALAR
# ====================================================
def _eh_nan(valor: Any) -> bool:
    """``True`` para ``None``/``NaN``/``NaT`` escalares (nunca levanta)."""
    if valor is None:
        return True
    try:
        resultado = pd.isna(valor)
    except (TypeError, ValueError):
        return False
    return bool(resultado) if isinstance(resultado, (bool, np.bool_)) else False


def sem_acento(texto: Any) -> str:
    """Remove acentos preservando UTF-8 (não converte para ASCII à força)."""
    if _eh_nan(texto):
        return ""
    normalizado = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def normalizar_texto(valor: Any) -> str:
    """Texto canônico de comparação: sem acento, maiúsculo e com espaços únicos."""
    if _eh_nan(valor):
        return ""
    return _RE_ESPACOS.sub(" ", sem_acento(valor).upper().strip())


def normalizar_chave(valor: Any) -> str:
    """Chave de *join*: normaliza e remove tudo que não é letra/dígito."""
    return _RE_ALFANUMERICO.sub("", normalizar_texto(valor))


def normalizar_coluna(valor: Any) -> str:
    """Nome de coluna normalizado (sinônimo de :func:`normalizar_chave`)."""
    return normalizar_chave(valor)


def limpar_nome_coluna(nome: Any) -> str:
    """Rótulo de coluna legível: sem acento, pontuação virando espaço."""
    texto = sem_acento(nome).upper().strip()
    texto = _RE_ALFANUMERICO.sub(" ", texto)
    return _RE_ESPACOS.sub(" ", texto).strip()


def normalizar_login(valor: Any) -> str:
    """Identidade canônica do técnico: ``'123.0'`` → ``'123'``, ``' a.b '`` → ``'A.B'``.

    Remove o sufixo ``.0`` que o Excel/Sheets acrescenta a números lidos como
    float — a causa histórica de *joins* que não casavam entre as bases — e os
    zeros à esquerda de logins puramente numéricos (``"00123.00"`` → ``"123"``),
    mantendo intactos os identificadores alfanuméricos (``" a.b "`` → ``"A.B"``).
    """
    if _eh_nan(valor):
        return ""
    if isinstance(valor, float) and float(valor).is_integer():
        return str(int(valor))
    texto = normalizar_texto(valor).replace(" ", "")
    sem_decimal = _RE_DECIMAL_SUJO.sub("", texto)
    if sem_decimal.isdigit():
        return sem_decimal.lstrip("0") or "0"
    return sem_decimal


def valor_nan(valor: Any) -> bool:
    """``True`` apenas para valores ausentes (``None``/``NaN``/``NaT``) escalares.

    Diferente de :func:`valor_vazio`, não trata tokens textuais (``"N/A"``) como
    ausência — serve para decidir a exibição de um número em tabela.
    """
    return _eh_nan(valor)


def valor_vazio(valor: Any, extras: Iterable[str] = ()) -> bool:
    """``True`` quando o valor não carrega informação (NaN ou token vazio)."""
    if _eh_nan(valor):
        return True
    texto = normalizar_texto(valor)
    return texto in VALORES_AUSENTES or texto in {normalizar_texto(e) for e in extras}


def escapar_html(valor: Any, *, aspas: bool = False) -> str:
    """Escape de HTML para textos interpolados em blocos ``unsafe_allow_html``.

    Por padrão escapa ``&``, ``<``, ``>`` e ``"`` — exatamente o conjunto que os
    dashboards já aplicavam à mão em células de tabela. ``aspas=True`` também
    escapa ``'`` (necessário apenas em atributos delimitados por aspa simples).
    """
    if _eh_nan(valor):
        return ""
    return _html.escape(str(valor), quote=aspas)


# ====================================================
# 🧮 BLOCO 2: FORMATAÇÃO PT-BR
# ====================================================
def _pt_br(texto_en: str) -> str:
    """``1,248.50`` → ``1.248,50`` (troca de separadores em duas etapas)."""
    return texto_en.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero(valor: Any, casas: int = 0) -> str:
    """Número em pt-BR (``1.248,50``); valores inválidos viram ``0``."""
    casas = max(0, int(casas))
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        numero = 0.0
    if np.isnan(numero):
        numero = 0.0
    return _pt_br(f"{numero:,.{casas}f}")


def formatar_inteiro(valor: Any) -> str:
    """Inteiro em pt-BR sem casas decimais."""
    return formatar_numero(valor, casas=0)


def formatar_percentual(valor: Any, casas: int = 1, *, ja_e_pct: bool = True) -> str:
    """Percentual em pt-BR. ``ja_e_pct=False`` multiplica por 100 (fração)."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "—"
    if np.isnan(numero):
        return "—"
    if not ja_e_pct:
        numero *= 100.0
    return f"{formatar_numero(numero, casas)}%"


# ====================================================
# 🧭 BLOCO 3: LOCALIZAÇÃO DE COLUNAS POR ALIAS
# ====================================================
def normalizar_serie(serie: pd.Series) -> pd.Series:
    """Versão vetorial de :func:`normalizar_texto` para uma coluna inteira."""
    return (
        serie.where(serie.notna(), "")
        .astype(str)
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
        .str.upper()
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )


def _mapa_colunas(df: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    """Dois índices das colunas de ``df``: exato e alfanumérico.

    O índice exato preserva pontuação (``"Nº CONTRATO"`` → ``"Nº CONTRATO"``);
    o alfanumérico a descarta (``"Nº CONTRATO"`` → ``"NCONTRATO"``), o que faz
    ``buscar_coluna("contrato")`` encontrar ``"Nº CONTRATO"`` sem que cada
    dashboard precise listar as variantes com símbolo de cada base.
    """
    nomes = list(df.columns)
    serie = pd.Series(nomes)
    chaves = normalizar_serie(serie).tolist()
    exato = {chave: nome for chave, nome in zip(chaves, nomes)}
    compacto = {_RE_ALFANUMERICO.sub("", chave): nome for chave, nome in zip(chaves, nomes)}
    return exato, compacto


def buscar_coluna(df: pd.DataFrame, aliases: Sequence[str]) -> str | None:
    """Primeira coluna de ``df`` que casa com um dos ``aliases`` (sem acento/caixa).

    A correspondência é feita em três passadas, da mais estrita para a mais
    flexível:

    1. nome normalizado completo (``"Técnico"`` ≡ ``"TECNICO"`` ≡ ``" técnico "``);
    2. versão só com letras e dígitos (``"N.º do Contrato"`` ≡ ``"NCONTRATO"``);
    3. contenção de chaves com 4+ caracteres (``"contrato"`` acha
       ``"Nº CONTRATO"`` e ``"base"`` acha ``"Base / Região"``).
    """
    if df is None or not len(df.columns):
        return None
    exato, compacto = _mapa_colunas(df)
    chaves = [(alias, normalizar_texto(alias)) for alias in aliases]

    for _, chave in chaves:
        coluna = exato.get(chave)
        if coluna is not None:
            return coluna
    for _, chave in chaves:
        coluna = compacto.get(_RE_ALFANUMERICO.sub("", chave))
        if coluna is not None:
            return coluna
    for _, chave in chaves:
        alvo = _RE_ALFANUMERICO.sub("", chave)
        if len(alvo) < 4:
            continue
        for nome_compacto, coluna in compacto.items():
            if alvo in nome_compacto:
                return coluna
    return None


def colunas_presentes(df: pd.DataFrame, candidatas: Sequence[str]) -> list[str]:
    """Subconjunto de ``candidatas`` que existe em ``df`` (na ordem informada)."""
    if df is None or not len(df.columns):
        return []
    saida: list[str] = []
    for candidata in candidatas:
        coluna = buscar_coluna(df, [candidata])
        if coluna is not None and coluna not in saida:
            saida.append(coluna)
    return saida
