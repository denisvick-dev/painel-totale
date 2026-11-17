"""config/slo_fontes.py
======================
SLO de frescor por fonte do portal — limites explícitos, versionados em código.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
A avaliação antiga de frescor usava 15/60 minutos para qualquer fonte
(``components.saude_dados.avaliar_frescor``). Isso funciona para a produção, que
sincroniza a cada poucos minutos, mas marcava a lista de ativos como
"desatualizada" no mesmo dia em que ela foi lida. Aqui cada fonte declara seu
próprio limite, com a justificativa ao lado:

* **Produção** (``Prod``/``Gpon``): o dado operacional do dia. Alerta em 15 min e
  crítico em 1 h, porque a rotina de sincronização é de 5 min em 5 min.
* **Consultivo** e **Ativos**: mudam ao longo do dia, mas não a cada minuto.
  Alerta em 24 h e crítico em 72 h.
* **Indicadores**: recorte diário, 24 h para alerta e 72 h para crítico.
* **Prévia**: recorte diário mais sensível, 24 h para alerta e 48 h para
  crítico.
* Fonte desconhecida cai no padrão conservador de 24/72 h — melhor um alerta
  tarde do que uma tela silenciosa.

O objetivo não é alarmar: é responder, em qualquer dashboard, "de quando é este
número?" e "ele está dentro do combinado?". Os limites são em **tempo corrido**,
não em horário comercial — sem uma janela operacional declarada, um sábado à
noite também conta. Se a operação passar a ter janela ou mudar a frequência de
carga, altere aqui e o portal inteiro reflete o novo combinado.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

VERSAO_SLO = "1.0.0"


@dataclass(frozen=True)
class SLOFonte:
    """Limites de frescor de uma fonte, em minutos."""

    nome: str
    descricao: str
    alerta_min: int
    critico_min: int

    def rotulo(self) -> str:
        """Texto curto do combinado (ex.: ``15 min / 1 h``)."""
        return f"{_minutos_curto(self.alerta_min)} / {_minutos_curto(self.critico_min)}"

    def detalhe(self) -> str:
        alerta = _minutos_curto(self.alerta_min)
        critico = _minutos_curto(self.critico_min)
        return f"{self.descricao}: alerta após {alerta}, crítico após {critico}"


def _minutos_curto(minutos: int) -> str:
    if minutos < 60:
        return f"{int(minutos)} min"
    if minutos < 1440:
        horas = minutos / 60
        return f"{horas:.0f} h" if horas == int(horas) else f"{horas:.1f} h"
    dias = minutos / 1440
    return f"{dias:.0f} d" if dias == int(dias) else f"{dias:.1f} d"


def _chave(texto: str) -> str:
    sem_acento = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", str(texto or ""))
        if not unicodedata.combining(caractere)
    )
    return "".join(c for c in sem_acento.upper() if c.isalnum())


SLO_PADRAO = SLOFonte(
    nome="Fonte",
    descricao="Fonte sem SLO específico",
    alerta_min=24 * 60,
    critico_min=72 * 60,
)

SLO_FONTES: tuple[SLOFonte, ...] = (
    SLOFonte(
        nome="Produção",
        descricao="Produção (abas Prod/Gpon)",
        alerta_min=15,
        critico_min=60,
    ),
    SLOFonte(
        nome="Consultivo",
        descricao="Consultivo processado",
        alerta_min=24 * 60,
        critico_min=72 * 60,
    ),
    SLOFonte(
        nome="Ativos",
        descricao="Lista de ativos",
        alerta_min=24 * 60,
        critico_min=72 * 60,
    ),
    SLOFonte(
        nome="Indicadores",
        descricao="Abas de indicadores do Drive",
        alerta_min=24 * 60,
        critico_min=72 * 60,
    ),
    SLOFonte(
        nome="Prévia",
        descricao="Prévia diária",
        alerta_min=24 * 60,
        critico_min=48 * 60,
    ),
)

_SLO_POR_CHAVE = {_chave(slo.nome): slo for slo in SLO_FONTES}


def obter_slo(nome: str) -> SLOFonte:
    """SLO da fonte pelo nome, tolerante a acento/caixa e a sinônimos comuns."""
    chave = _chave(nome)
    if chave in _SLO_POR_CHAVE:
        return _SLO_POR_CHAVE[chave]
    # Nomes reais variam ("Produção (Prod)", "dados_prod", "lista_ativos").
    if "PROD" in chave:
        return _SLO_POR_CHAVE[_chave("Produção")]
    if "CONS" in chave:
        return _SLO_POR_CHAVE[_chave("Consultivo")]
    if "ATIVO" in chave:
        return _SLO_POR_CHAVE[_chave("Ativos")]
    if "INDICADOR" in chave:
        return _SLO_POR_CHAVE[_chave("Indicadores")]
    if "PREVIA" in chave:
        return _SLO_POR_CHAVE[_chave("Prévia")]
    return SLO_PADRAO


__all__ = [
    "SLOFonte",
    "SLO_FONTES",
    "SLO_PADRAO",
    "VERSAO_SLO",
    "obter_slo",
]
