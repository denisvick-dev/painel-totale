"""Regras determinísticas de alerta para o estado atual das fontes e do robô."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

import pandas as pd

# Funções externas
from components.saude_dados import avaliar_consistencia, avaliar_frescor

Severidade = Literal["CRÍTICO", "ALTO", "MÉDIO", "BAIXO"]
FUSO_BR = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class Alerta:
    severidade: Severidade
    titulo: str
    origem: str
    detalhe: str


def _limpar_para_str(valor: Any) -> str:
    """Garante que o valor seja uma string, convertendo listas se necessário."""
    if isinstance(valor, (list, tuple)):
        return "; ".join(map(str, valor))
    return str(valor) if valor is not None else ""


def avaliar_alertas(
    estado: Mapping[str, Any],
    *,
    agora: datetime | None = None,
) -> list[Alerta]:
    referencia = agora or datetime.now(FUSO_BR)
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=FUSO_BR)

    alertas: list[Alerta] = []

    # 1. Erro do Robô
    erro = estado.get("robo_erro")
    if erro and _limpar_para_str(erro).strip():
        erro_str = _limpar_para_str(erro).strip()
        parcial = erro_str.lower().startswith("parcial:")
        alertas.append(
            Alerta(
                "MÉDIO" if parcial else "ALTO",
                "Robô reportou erro de processamento",
                "Robô local",
                erro_str,
            )
        )

    # 2. Bloqueio (Lock)
    bloqueio = estado.get("_robo_aguardando_lock")
    if bloqueio and _limpar_para_str(bloqueio).strip():
        alertas.append(
            Alerta(
                "MÉDIO",
                "Arquivo aguardando liberação",
                "Robô local",
                _limpar_para_str(bloqueio).strip(),
            )
        )

    # 3. Tempo de Processamento
    if estado.get("robo_processando"):
        inicio = estado.get("robo_processando_desde")
        if isinstance(inicio, datetime):
            if inicio.tzinfo is None:
                inicio = inicio.replace(tzinfo=FUSO_BR)
            duracao = (referencia - inicio).total_seconds()
            if duracao > 180:
                alertas.append(
                    Alerta(
                        "ALTO",
                        "Processamento lento",
                        "Robô local",
                        f"Ativo há {duracao / 60:.0f} min.",
                    )
                )

    # 3b. Duplicatas removidas pelo robô
    duplicatas = estado.get("robo_duplicatas_removidas")
    if isinstance(duplicatas, int) and duplicatas > 0:
        alertas.append(
            Alerta(
                "BAIXO",
                "Duplicatas removidas na consolidação",
                "Robô local",
                f"{duplicatas} linha(s) duplicada(s) ignorada(s).",
            )
        )

    # 4. Status das Fontes (Frescor)
    status_fontes = estado.get("status_fontes")
    if isinstance(status_fontes, Mapping):
        for nome, status in status_fontes.items():
            # Proteção: garantir que 'nome' não seja uma lista (causa do erro unhashable)
            nome_str = _limpar_para_str(nome)

            ultimo_sucesso = (
                getattr(status, "ultimo_sucesso", None)
                if not isinstance(status, Mapping)
                else status.get("ultimo_sucesso")
            )
            ok = (
                bool(getattr(status, "ok", False))
                if not isinstance(status, Mapping)
                else bool(status.get("ok", False))
            )

            nivel, resumo = avaliar_frescor(ultimo_sucesso, ok, agora=referencia)

            if nivel != "ok":
                # Garantir que nivel seja uma das Severidades válidas
                sev: Severidade = "ALTO" if str(nivel).lower() == "critico" else "MÉDIO"
                alertas.append(
                    Alerta(
                        sev,
                        f"Fonte {nome_str} desatualizada",
                        "Saúde dos dados",
                        _limpar_para_str(resumo),
                    )
                )

    # 5. Consistência (Pandas)
    chaves_dados = {
        "Produção": "dados_prod",
        "Consultivo": "dados_cons",
        "Ativos": "dados_ativos",
    }
    possui_dados = False

    for nome, chave in chaves_dados.items():
        dados = estado.get(chave)
        partes = []

        # O estado pode conter o DF direto, um dicionário de DFs ou uma LISTA de DFs
        if isinstance(dados, pd.DataFrame):
            partes = [dados]
        elif isinstance(dados, Mapping):
            partes = [v for v in dados.values() if isinstance(v, pd.DataFrame)]
        elif isinstance(dados, Iterable) and not isinstance(dados, (str, bytes)):
            partes = [v for v in dados if isinstance(v, pd.DataFrame)]

        if partes:
            possui_dados = True
            df_fonte = pd.concat(partes, ignore_index=True)
            if not df_fonte.empty:
                try:
                    # O erro "unhashable type: list" costuma ocorrer AQUI dentro se houver colunas com listas
                    nivel_c, resumo_c = avaliar_consistencia(df_fonte)
                    if nivel_c != "ok":
                        sev_c: Severidade = "ALTO" if str(nivel_c).lower() == "critico" else "MÉDIO"
                        alertas.append(
                            Alerta(
                                sev_c,
                                f"Dados inconsistentes: {nome}",
                                "Saúde dos dados",
                                _limpar_para_str(resumo_c),
                            )
                        )
                except TypeError as e:
                    if "unhashable type: 'list'" in str(e):
                        alertas.append(
                            Alerta(
                                "ALTO",
                                f"Erro de leitura na fonte {nome}",
                                "Saúde dos dados",
                                "A planilha contém células com formatos inválidos (listas internas).",
                            )
                        )

    # 6. Verificação de Sessão Vazia
    df_memoria = estado.get("df_memoria")
    if not alertas and not possui_dados and not isinstance(df_memoria, pd.DataFrame):
        alertas.append(
            Alerta(
                "ALTO",
                "Nenhuma base carregada",
                "Sistema",
                "Sincronize os dados para começar.",
            )
        )

    # Ordenação Segura
    pesos: dict[str, int] = {"CRÍTICO": 0, "ALTO": 1, "MÉDIO": 2, "BAIXO": 3}

    return sorted(alertas, key=lambda a: (pesos.get(str(a.severidade).upper(), 99), a.titulo))
