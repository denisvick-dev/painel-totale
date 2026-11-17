"""Testes do frescor global e dos SLOs por fonte (B2).

Cobrem a regra pura (:mod:`services.frescor`), a tabela de SLO
(:mod:`config.slo_fontes`) e a faixa HTML — sem depender do runtime do
Streamlit. O caso que motivou a melhoria: a lista de ativos lida ontem não pode
ser tratada como "desatualizada" pela mesma régua de 15 min da produção.

    pytest tests/test_frescor_fontes.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from components.frescor_fontes import html_faixa_frescor
from config.slo_fontes import SLO_PADRAO, obter_slo
from services.frescor import (
    estado_geral,
    idade_curta,
    leitura_de_sessao,
    resumir_frescor,
    resumo_curto,
)

FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 11, 17, 12, 0, tzinfo=FUSO)


def test_slo_por_fonte_reconhece_nomes_e_variacoes() -> None:
    assert obter_slo("Produção").alerta_min == 15
    assert obter_slo("dados_prod").nome == "Produção"
    assert obter_slo("Consultivo").critico_min == 72 * 60
    assert obter_slo("lista_ativos").nome == "Ativos"
    assert obter_slo("Indicadores do Drive").nome == "Indicadores"
    assert obter_slo("Prévia Diária").nome == "Prévia"
    assert obter_slo("fonte nova").nome == SLO_PADRAO.nome


def test_idade_curta_usa_unidade_e_decimal_brasileiro() -> None:
    assert idade_curta(0) == "0 min"
    assert idade_curta(42) == "42 min"
    assert idade_curta(90) == "1,5 h"
    assert idade_curta(30 * 60) == "1,2 d"
    assert idade_curta(None) == "—"


def test_producao_fresca_e_ativos_de_ontem_nao_usam_a_mesma_regua() -> None:
    leituras = resumir_frescor(
        {
            "Produção": {
                "ok": True,
                "linhas": 1200,
                "ultimo_sucesso": AGORA - timedelta(minutes=5),
            },
            "Ativos": {
                "ok": True,
                "linhas": 250,
                "ultimo_sucesso": AGORA - timedelta(hours=20),
            },
        },
        agora=AGORA,
    )

    por_nome = {leitura.nome: leitura for leitura in leituras}
    assert por_nome["Produção"].estado == "ok"
    assert por_nome["Ativos"].estado == "ok"  # 20 h ainda está dentro de 24 h
    assert estado_geral(leituras) == "ok"


def test_falha_recente_rebaixa_para_alerta_e_atraso_longo_para_critico() -> None:
    leituras = resumir_frescor(
        {
            "Produção": {
                "ok": False,
                "ultimo_sucesso": AGORA - timedelta(minutes=2),
                "erro": "timeout",
            },
            "Consultivo": {
                "ok": True,
                "ultimo_sucesso": AGORA - timedelta(days=4),
            },
        },
        agora=AGORA,
    )

    por_nome = {leitura.nome: leitura for leitura in leituras}
    assert por_nome["Produção"].estado == "alerta"
    assert "última tentativa falhou" in por_nome["Produção"].texto
    assert "timeout" in por_nome["Produção"].detalhe
    assert por_nome["Consultivo"].estado == "critico"
    assert estado_geral(leituras) == "critico"


def test_fonte_sem_sucesso_e_critica_mesmo_com_tentativa() -> None:
    leituras = resumir_frescor(
        {
            "Ativos": {
                "ok": False,
                "ultima_tentativa": AGORA - timedelta(minutes=3),
                "erro": "permissão negada",
            }
        },
        agora=AGORA,
    )

    assert len(leituras) == 1
    assert leituras[0].estado == "critico"
    assert "sem sucesso" in leituras[0].texto
    assert "permissão negada" in leituras[0].detalhe


def test_status_em_lista_e_horarios_em_texto_sao_aceitos() -> None:
    leituras = resumir_frescor(
        [
            {
                "nome": "Ativos",
                "ok": True,
                "ultimo_sucesso": "17/11/2026 11:00",
            },
            {
                "nome": "Consultivo",
                "ok": True,
                "ultimo_sucesso": "2026-11-17T11:30:00",
            },
        ],
        agora=AGORA,
    )

    assert [leitura.nome for leitura in leituras] == ["Ativos", "Consultivo"]
    assert [leitura.estado for leitura in leituras] == ["ok", "ok"]


def test_leitura_de_sessao_e_fallback_sem_status_fontes() -> None:
    sem_data = leitura_de_sessao(None, agora=AGORA)
    assert sem_data == []

    leituras = leitura_de_sessao(AGORA - timedelta(minutes=10), agora=AGORA)
    assert len(leituras) == 1
    assert leituras[0].nome == "Sessão"
    assert leituras[0].estado == "ok"
    assert "10 min" in leituras[0].texto


def test_resumo_curto_limita_fontes_e_anuncia_o_restante() -> None:
    leituras = resumir_frescor(
        {
            "Produção": {"ok": True, "ultimo_sucesso": AGORA - timedelta(minutes=1)},
            "Ativos": {"ok": True, "ultimo_sucesso": AGORA - timedelta(hours=1)},
            "Consultivo": {"ok": True, "ultimo_sucesso": AGORA - timedelta(hours=2)},
            "Indicadores": {"ok": True, "ultimo_sucesso": AGORA - timedelta(hours=3)},
        },
        agora=AGORA,
    )

    resumo = resumo_curto(leituras, maximo=2)
    assert resumo.startswith("Produção há 1 min · Ativos há 1 h")
    assert "+2 fonte(s)" in resumo


def test_html_da_faixa_escapa_conteudo_e_explica_o_estado() -> None:
    leituras = resumir_frescor(
        {
            "<script>Produção</script>": {
                "ok": False,
                "ultima_tentativa": AGORA - timedelta(minutes=1),
                "erro": "<img src=x onerror=alert(1)>",
            }
        },
        agora=AGORA,
    )
    markup = html_faixa_frescor(leituras)

    assert "Dados desatualizados" in markup
    assert "&lt;script&gt;" in markup
    assert "<script>" not in markup
    assert "<img" not in markup
    assert "SLO" in markup  # detalhe no title/aria-label


def test_faixa_vazia_nao_renderiza_nada() -> None:
    assert html_faixa_frescor([]) == ""
