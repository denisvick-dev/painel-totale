"""Renderização da página de Absenteísmo (mapa mensal no estilo da planilha).

A página é executada com o quadro e o controle já na sessão — nenhuma leitura
de rede — para garantir que a grade (técnico × dia) aparece, que os códigos
das ausências chegam ao HTML e que a aba em formato de grade fica somente
leitura (sem formulário de gravação).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from services.absenteismo import normalizar_registros

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = RAIZ / "pages" / "absenteismo.py"


def _quadro() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "LOGIN": ["Z641759", "Z663524", "Z657046"],
            "TÉCNICO": ["Alex Bernardes Da Silva", "Alex De Jesus Freire", "Abner Makalas"],
            "MONITOR": ["Edson Marco Pinheiro", "Edson Marco Pinheiro", "Alan De Andrade Dias"],
            "BASE": ["Abcdm-Totale", "Abcdm-Totale", "Spo-Totalleste"],
            "SITUAÇÃO": ["ATIVO", "ATIVO", "FÉRIAS"],
            "RE": ["8368", "8496", "8554"],
            "U.N.": ["NET-ABCDM", "NET-ABCDM", "NET-LESTE"],
        }
    )


def _registros() -> pd.DataFrame:
    return normalizar_registros(
        pd.DataFrame(
            [
                {
                    "ID": "1",
                    "Login": "Z641759",
                    "Técnico": "Alex Bernardes Da Silva",
                    "Monitor": "Edson Marco Pinheiro",
                    "Base": "Abcdm-Totale",
                    "Tipo": "Férias",
                    "Data Início": "03/11/2026",
                    "Data Fim": "05/11/2026",
                    "Status": "Ativo",
                },
                {
                    "ID": "2",
                    "Login": "Z641759",
                    "Técnico": "Alex Bernardes Da Silva",
                    "Monitor": "Edson Marco Pinheiro",
                    "Base": "Abcdm-Totale",
                    "Tipo": "Atestado",
                    "Data Início": "04/11/2026",
                    "Data Fim": "04/11/2026",
                    "Status": "Ativo",
                },
            ]
        )
    )


def _rodar(origem_grade: bool) -> AppTest:
    app = AppTest.from_file(str(PAGINA), default_timeout=60)
    app.session_state["totale_lista_ativos"] = _quadro()
    app.session_state["totale_controle_absenteismo"] = _registros()
    app.session_state["totale_absenteismo_origem_grade"] = origem_grade
    # Fixa o mês do mapa (o padrão da página é o mês corrente).
    app.session_state["absenteismo_periodo_inicio"] = date(2026, 11, 1)
    app.session_state["absenteismo_periodo_fim"] = date(2026, 11, 30)
    return app.run()


def test_pagina_absenteismo_renderiza_o_mapa_mensal() -> None:
    app = _rodar(origem_grade=False)

    assert not app.exception
    html = "\n".join(elemento.value for elemento in app.markdown)
    assert '<table class="abs-mapa"' in html
    assert "1/nov." in html
    assert "30/nov." in html
    assert "Alex Bernardes Da Silva" in html
    assert "NET-ABCDM" in html
    assert ">FE</td>" in html  # férias de 03 a 05/11
    assert ">AT/FE</td>" in html  # atestado + férias em 04/11
    assert len(app.get("form")) >= 1  # controle em registros: formulário disponível


def test_pagina_absenteismo_com_grade_nao_oferece_gravacao() -> None:
    app = _rodar(origem_grade=True)

    assert not app.exception
    assert len(app.get("form")) == 0
    textos = "\n".join(elemento.value for elemento in app.caption)
    assert "direto na planilha" in textos.lower()  # aviso de fonte em grade
