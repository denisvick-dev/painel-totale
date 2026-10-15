"""
services/dados_sessao.py
========================
Contrato único de leitura das bases carregadas na sessão do portal.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
A carga de dados é feita uma única vez (``Atualização de Dados`` ou o robô
local) e consumida por todos os dashboards através de ``st.session_state``.
Cada página, porém, reimplementava a mesma guarda de entrada — ler
``dados_prod``, aceitar ``DataFrame`` **ou** ``dict`` de abas, avisar quando
estivesse vazio e parar com ``st.stop()``. Onze cópias com mensagens quase
iguais e diferenças sutis (umas aceitavam ``dict`` sem a aba ``Prod``, outras
não; umas paravam, outras seguiam com base vazia).

Este módulo fixa o contrato:

* :func:`coletar_dataframes` percorre containers aninhados sem contar chaves
  como linhas;
* :func:`resumir_carga` devolve registros/abas/última atualização para os chips
  de contexto do cabeçalho;
* :func:`obter_base` é a guarda de entrada das páginas — devolve o DataFrame já
  concatenado ou ``None``;
* :func:`exigir_base` é :func:`obter_base` + aviso padronizado + ``st.stop()``,
  o padrão de onze dashboards em uma chamada.

As chaves de sessão oficiais são ``dados_prod`` (produção consolidada),
``dados_cons`` (consultivos), ``df_memoria`` (saída bruta do robô) e
``ultima_atualizacao``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

VERSAO_DADOS_SESSAO = "1.0.0"

#: Chave principal da carga consolidada (produção).
CHAVE_PRODUCAO = "dados_prod"

#: Chave da base de consultivos (Drive/CSV de consultivos).
CHAVE_CONSULTIVO = "dados_cons"

#: Chave da saída bruta/processada do robô local.
CHAVE_MEMORIA = "df_memoria"

#: Chave do carimbo da última atualização bem-sucedida.
CHAVE_ATUALIZACAO = "ultima_atualizacao"

#: Ordem de procura quando a página não declara a aba desejada.
ABAS_PREFERENCIAIS: tuple[str, ...] = ("Prod", "Produção", "Producao", "Gpon", "GPON")

MENSAGEM_SEM_DADOS = (
    "Nenhuma base carregada na sessão. Use **Atualização de Dados** (ou o robô "
    "local, na barra lateral) para sincronizar as planilhas antes de abrir este painel."
)

__all__ = [
    "ABAS_PREFERENCIAIS",
    "CHAVE_ATUALIZACAO",
    "CHAVE_CONSULTIVO",
    "CHAVE_MEMORIA",
    "CHAVE_PRODUCAO",
    "MENSAGEM_SEM_DADOS",
    "VERSAO_DADOS_SESSAO",
    "ResumoCarga",
    "coletar_dataframes",
    "concatenar_abas",
    "exigir_base",
    "obter_base",
    "obter_dataframe",
    "resumir_carga",
    "ultima_atualizacao",
]


# ====================================================
# 🧮 BLOCO 1: INSPEÇÃO DA CARGA (FUNÇÕES PURAS)
# ====================================================
@dataclass(frozen=True)
class ResumoCarga:
    """Fotografia da carga disponível na sessão (para chips e KPIs de contexto)."""

    registros: int = 0
    tabelas: int = 0
    tabelas_com_dados: int = 0
    atualizado_em: datetime | str | None = None

    @property
    def carregado(self) -> bool:
        """``True`` quando há ao menos uma aba ou registro na sessão."""
        return self.tabelas > 0 or self.registros > 0


def coletar_dataframes(valor: Any) -> list[pd.DataFrame]:
    """Extrai DataFrames de containers aninhados (dict de abas, listas, tuplas)."""
    if isinstance(valor, pd.DataFrame):
        return [valor]
    if isinstance(valor, Mapping):
        return [frame for conteudo in valor.values() for frame in coletar_dataframes(conteudo)]
    if isinstance(valor, (list, tuple)):
        return [frame for conteudo in valor for frame in coletar_dataframes(conteudo)]
    return []


def resumir_carga(dados: Any, *, atualizado_em: Any = None) -> ResumoCarga:
    """Conta linhas e abas com dados, inclusive quando a carga é um dict de abas."""
    frames = coletar_dataframes(dados)
    if frames:
        return ResumoCarga(
            registros=sum(len(frame) for frame in frames),
            tabelas=len(frames),
            tabelas_com_dados=sum(not frame.empty for frame in frames),
            atualizado_em=atualizado_em,
        )
    # Compatibilidade com cargas antigas que guardavam linhas diretamente.
    if isinstance(dados, (list, tuple)):
        quantidade = len(dados)
        return ResumoCarga(
            registros=quantidade,
            tabelas=1 if quantidade else 0,
            tabelas_com_dados=1 if quantidade else 0,
            atualizado_em=atualizado_em,
        )
    return ResumoCarga(atualizado_em=atualizado_em)


def concatenar_abas(dados: Any, *, abas: Sequence[str] = ()) -> pd.DataFrame:
    """Concatena as abas pedidas (ou todas as disponíveis) em um único DataFrame."""
    frames: list[pd.DataFrame] = []
    if isinstance(dados, Mapping):
        pedidas = list(abas) if abas else [a for a in ABAS_PREFERENCIAIS if a in dados]
        for chave in pedidas:
            conteudo = dados.get(chave)
            if isinstance(conteudo, pd.DataFrame):
                frames.append(conteudo)
        if not frames and not pedidas:
            frames = [f for f in dados.values() if isinstance(f, pd.DataFrame)]
    else:
        frames = coletar_dataframes(dados)
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0].copy()
    return pd.concat(frames, ignore_index=True)


# ====================================================
# 🔑 BLOCO 2: LEITURA DA SESSÃO
# ====================================================
def _sessao() -> Any:
    import streamlit as st

    return st.session_state


def obter_dataframe(chave: str = CHAVE_PRODUCAO) -> Any:
    """Valor bruto guardado em ``st.session_state[chave]`` (``None`` se ausente)."""
    return _sessao().get(chave)


def ultima_atualizacao(chave: str = CHAVE_ATUALIZACAO) -> datetime | str | None:
    """Carimbo da última sincronização bem-sucedida (para os chips de contexto)."""
    return _sessao().get(chave)


def obter_base(
    chave: str = CHAVE_PRODUCAO,
    *,
    abas: Sequence[str] = (),
    copiar: bool = True,
) -> pd.DataFrame | None:
    """Devolve a base consolidada da sessão, ou ``None`` quando não há dados.

    Aceita os três formatos que o portal já produziu: ``DataFrame`` único,
    ``dict`` de abas (``{"Prod": df, "Gpon": df}``) e a lista legada de linhas.
    Com ``abas`` a página pede recortes específicos; sem ela, as abas oficiais
    de :data:`ABAS_PREFERENCIAIS` são concatenadas na ordem.
    """
    dados = obter_dataframe(chave)
    if dados is None:
        return None
    if isinstance(dados, pd.DataFrame):
        base = dados
    else:
        base = concatenar_abas(dados, abas=abas)
    if base is None or base.empty:
        return None
    return base.copy() if copiar else base


def exigir_base(
    chave: str = CHAVE_PRODUCAO,
    *,
    abas: Sequence[str] = (),
    mensagem: str = MENSAGEM_SEM_DADOS,
    tipo_aviso: str = "alerta",
    pagina: str = "",
) -> pd.DataFrame:
    """Guarda de entrada padrão dos dashboards: base pronta ou página parada.

    Quando não há dados, mostra o aviso oficial do portal e chama ``st.stop()``
    — o mesmo comportamento que onze páginas reimplementavam à mão::

        df = exigir_base(pagina="Produção Mensal")

    Levanta ``RuntimeError`` fora do runtime do Streamlit (testes unitários),
    para o problema não passar silenciosamente.
    """
    import streamlit as st

    base = obter_base(chave, abas=abas)
    if base is not None and not base.empty:
        return base

    texto = f"**{pagina}** — {mensagem}" if pagina else mensagem
    try:
        from components.componentes import render_insight

        render_insight(texto, tipo=tipo_aviso)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover - fora do runtime do Streamlit
        logger.debug("render_insight indisponível; usando st.warning.", exc_info=True)
        st.warning(texto)
    if not st.session_state.get("_totale_root_navigation_shell", False):
        # Página aberta fora do shell de navegação: oferece o atalho para a carga.
        try:
            st.page_link("pages/envio_excel.py", label="🔁 Ir para Atualização de Dados")
        except Exception:  # pragma: no cover - app de página única
            logger.debug("st.page_link indisponível neste contexto.", exc_info=True)
    st.stop()
    raise RuntimeError("exigir_base() deveria ter interrompido a página.")  # pragma: no cover
