"""services/frescor.py
=====================
Leitura de frescor das fontes — regra pura, sem Streamlit.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
O status de sincronização já existia em ``st.session_state["status_fontes"]``,
mas só a Home sabia interpretá-lo. Cada dashboard mostrava "Atualizado em" sem
dizer **de qual fonte** era aquele horário, nem se ele estava dentro do
combinado. Este módulo transforma o estado bruto em uma lista reproduzível de
leituras (idade, estado e SLO) e uma frase curta para a faixa global.

Regras:

* o SLO vem de :mod:`config.slo_fontes` (Produção 15 min, Ativos 24 h etc.);
* ``ultimo_sucesso`` ausente é **crítico**, não "ok";
* tentativa mais recente com erro rebaixa uma fonte fresca para **alerta**;
* horários sem fuso são interpretados em America/Sao_Paulo;
* datas em texto (ISO ou dd/mm/aaaa) são aceitas porque o status pode vir de
  uma sessão serializada;
* nenhuma exceção sobe por dado faltante: o pior caso é ``desconhecido``.

A camada de apresentação (:mod:'components.frescor_fontes') só decide cor e
layout; a conta fica aqui e é testada sem runtime.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal
from zoneinfo import ZoneInfo

from config.slo_fontes import SLO_PADRAO, SLOFonte, obter_slo

VERSAO_FRESCOR = "1.0.0"
FUSO_BR = ZoneInfo("America/Sao_Paulo")

EstadoFrescor = Literal["ok", "alerta", "critico", "desconhecido"]

ROTULOS_ESTADO: dict[str, str] = {
    "ok": "Dados atualizados",
    "alerta": "Atenção no frescor",
    "critico": "Dados desatualizados",
    "desconhecido": "Frescor indisponível",
}

__all__ = [
    "EstadoFrescor",
    "FUSO_BR",
    "LeituraFrescor",
    "ROTULOS_ESTADO",
    "VERSAO_FRESCOR",
    "estado_geral",
    "idade_curta",
    "leitura_de_sessao",
    "resumir_frescor",
    "resumo_curto",
]


@dataclass(frozen=True)
class LeituraFrescor:
    """Uma fonte avaliada contra o próprio SLO."""

    nome: str
    estado: EstadoFrescor
    texto: str
    detalhe: str
    slo: SLOFonte
    idade_min: float | None = None
    linhas: int = 0
    ok: bool = False
    ultimo_sucesso: datetime | None = None
    ultima_tentativa: datetime | None = None
    erro: str = ""

    @property
    def critica(self) -> bool:
        return self.estado == "critico"


# ====================================================
# 🕒 BLOCO 1: TEMPO E TEXTO
# ====================================================
def _como_datetime(valor: Any) -> datetime | None:
    """Converte datetime/Timestamp/data/texto em datetime com fuso do Brasil."""
    if valor is None or valor is _valor_ausente(valor):
        return None
    if isinstance(valor, datetime):
        convertido = valor
    elif isinstance(valor, date):
        convertido = datetime.combine(valor, time.min)
    else:
        texto = str(valor).strip()
        if not texto or texto.upper() in {"NAN", "NAT", "NONE", "N/A"}:
            return None
        convertido = _parse_texto(texto)
        if convertido is None:
            return None
    if convertido.tzinfo is None:
        return convertido.replace(tzinfo=FUSO_BR)
    return convertido.astimezone(FUSO_BR)


def _valor_ausente(valor: Any) -> bool:
    """``True`` para ``pd.NA``/``NaT`` sem importar pandas no caminho comum."""
    return type(valor).__name__ in {"NAType", "NaTType"}


def _parse_texto(texto: str) -> datetime | None:
    formatos = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    )
    for formato in formatos:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def idade_curta(minutos: float | None) -> str:
    """Idade legível: ``4 min``, ``2 h``, ``3 d`` (sem casas desnecessárias)."""
    if minutos is None:
        return "—"
    total = max(0.0, float(minutos))
    if total < 60:
        return f"{int(round(total))} min"
    if total < 1440:
        horas = total / 60.0
        return (
            f"{horas:.0f} h"
            if abs(horas - round(horas)) < 0.05
            else f"{horas:.1f} h".replace(".", ",")
        )
    dias = total / 1440.0
    return f"{dias:.0f} d" if abs(dias - round(dias)) < 0.05 else f"{dias:.1f} d".replace(".", ",")


# ====================================================
# 🔎 BLOCO 2: AVALIAÇÃO DE UMA FONTE
# ====================================================
def _campo(fonte: Any, nome: str, padrao: Any = None) -> Any:
    if isinstance(fonte, Mapping):
        return fonte.get(nome, padrao)
    return getattr(fonte, nome, padrao)


def _linhas(valor: Any) -> int:
    try:
        return max(0, int(valor or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _erro_curto(valor: Any, limite: int = 120) -> str:
    texto = " ".join(str(valor or "").split())
    return f"{texto[: limite - 1]}…" if len(texto) > limite else texto


def _avaliar(
    nome: str,
    *,
    ok: bool,
    ultimo_sucesso: datetime | None,
    ultima_tentativa: datetime | None,
    linhas: int,
    erro: str,
    slo: SLOFonte,
    agora: datetime,
) -> LeituraFrescor:
    if ultimo_sucesso is None:
        if ultima_tentativa is not None:
            idade_tentativa = (agora - ultima_tentativa).total_seconds() / 60.0
            texto = f"sem sucesso (tentativa há {idade_curta(idade_tentativa)})"
        else:
            texto = "sem sincronização registrada"
        detalhe = f"{nome}: {texto} · SLO {slo.rotulo()}"
        if erro:
            detalhe += f" · erro: {erro}"
        return LeituraFrescor(
            nome=nome,
            estado="critico",
            texto=texto,
            detalhe=detalhe,
            slo=slo,
            idade_min=None,
            linhas=linhas,
            ok=ok,
            ultimo_sucesso=None,
            ultima_tentativa=ultima_tentativa,
            erro=erro,
        )

    idade_min = max(0.0, (agora - ultimo_sucesso).total_seconds() / 60.0)
    idade = idade_curta(idade_min)
    if idade_min <= slo.alerta_min and ok:
        estado: EstadoFrescor = "ok"
        texto = f"há {idade}"
    elif idade_min <= slo.critico_min:
        estado = "alerta"
        texto = f"há {idade}" + ("" if ok else " · última tentativa falhou")
    else:
        estado = "critico"
        texto = f"há {idade} · acima do SLO de {idade_curta(slo.critico_min)}"

    detalhe = f"{nome}: atualizado há {idade} · SLO {slo.rotulo()} · {linhas} linha(s)"
    if not ok:
        detalhe += " · tentativa mais recente falhou"
    if erro:
        detalhe += f" · erro: {erro}"
    return LeituraFrescor(
        nome=nome,
        estado=estado,
        texto=texto,
        detalhe=detalhe,
        slo=slo,
        idade_min=idade_min,
        linhas=linhas,
        ok=ok,
        ultimo_sucesso=ultimo_sucesso,
        ultima_tentativa=ultima_tentativa,
        erro=erro,
    )


# ====================================================
# 📋 BLOCO 3: LISTA E RESUMO GLOBAL
# ====================================================
def _itens(status_fontes: Any) -> list[tuple[str, Any]]:
    if isinstance(status_fontes, Mapping):
        return [(str(nome), fonte) for nome, fonte in status_fontes.items()]
    if isinstance(status_fontes, Sequence) and not isinstance(status_fontes, (str, bytes)):
        itens: list[tuple[str, Any]] = []
        for fonte in status_fontes:
            if isinstance(fonte, Mapping):
                nome = str(fonte.get("nome", "")).strip()
            else:
                nome = str(getattr(fonte, "nome", "")).strip()
            if nome:
                itens.append((nome, fonte))
        return itens
    return []


def resumir_frescor(
    status_fontes: Any,
    *,
    agora: datetime | None = None,
) -> list[LeituraFrescor]:
    """Avalia cada fonte do status da sessão contra seu SLO.

    Aceita o ``dict`` gravado pela sincronização (valores :class:`StatusFonte`
    ou dicts) e também uma lista de objetos com ``nome``. Devolve na ordem em
    que as fontes foram sincronizadas — Produção, Consultivo, Ativos.
    """
    referencia = agora or datetime.now(FUSO_BR)
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=FUSO_BR)
    else:
        referencia = referencia.astimezone(FUSO_BR)

    leituras: list[LeituraFrescor] = []
    for nome, fonte in _itens(status_fontes):
        leituras.append(
            _avaliar(
                nome,
                ok=bool(_campo(fonte, "ok", False)),
                ultimo_sucesso=_como_datetime(_campo(fonte, "ultimo_sucesso")),
                ultima_tentativa=_como_datetime(_campo(fonte, "ultima_tentativa")),
                linhas=_linhas(_campo(fonte, "linhas", 0)),
                erro=_erro_curto(_campo(fonte, "erro", "")),
                slo=obter_slo(nome),
                agora=referencia,
            )
        )
    return leituras


def estado_geral(leituras: Sequence[LeituraFrescor]) -> EstadoFrescor:
    """Pior estado do conjunto (crítico > alerta > ok)."""
    if not leituras:
        return "desconhecido"
    if any(leitura.estado == "critico" for leitura in leituras):
        return "critico"
    if any(leitura.estado == "alerta" for leitura in leituras):
        return "alerta"
    return "ok"


def resumo_curto(leituras: Sequence[LeituraFrescor], *, maximo: int = 3) -> str:
    """Frase de uma linha: ``Produção há 4 min · Ativos há 2 h``."""
    if not leituras:
        return "Frescor indisponível"
    partes = [f"{leitura.nome} {leitura.texto}" for leitura in leituras[:maximo]]
    restantes = len(leituras) - len(partes)
    if restantes > 0:
        partes.append(f"+{restantes} fonte(s)")
    return " · ".join(partes)


def leitura_de_sessao(
    ultima_atualizacao: Any,
    *,
    agora: datetime | None = None,
) -> list[LeituraFrescor]:
    """Leitura sintética da carga manual quando não há ``status_fontes``."""
    sucesso = _como_datetime(ultima_atualizacao)
    if sucesso is None:
        return []
    slo = SLOFonte(
        nome="Sessão",
        descricao="Carga manual da sessão",
        alerta_min=SLO_PADRAO.alerta_min,
        critico_min=SLO_PADRAO.critico_min,
    )
    referencia = agora or datetime.now(FUSO_BR)
    return [
        _avaliar(
            "Sessão",
            ok=True,
            ultimo_sucesso=sucesso,
            ultima_tentativa=sucesso,
            linhas=0,
            erro="",
            slo=slo,
            agora=referencia if referencia.tzinfo else referencia.replace(tzinfo=FUSO_BR),
        )
    ]
