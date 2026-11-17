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
    from services.absenteismo import normalizar_quadro_identidade
    from services.presenca_grade import interpretar_valores
    dias = list(pd.date_range("2026-11-01", "2026-11-30").date)
    pessoas = normalizar_quadro_identidade(_quadro())
    valores = [list(pessoas.columns) + [d.isoformat() for d in dias]]
    valores += [list(linha) + [""] * len(dias) for linha in pessoas.itertuples(index=False, name=None)]
    snapshot = interpretar_valores(valores)
    snapshot["registros"] = _registros()
    app.session_state["presenca_grade_snapshot"] = snapshot
    # Fixa o mês do mapa (o padrão da página é o mês corrente).
    app.session_state["absenteismo_periodo_inicio"] = date(2026, 11, 1)
    app.session_state["absenteismo_periodo_fim"] = date(2026, 11, 30)
    return app.run()


def test_pagina_absenteismo_renderiza_o_mapa_mensal() -> None:
    app = _rodar(origem_grade=False)
    app.radio(key="presenca_area").set_value("Mapa mensal").run()

    assert not app.exception
    html = "\n".join(elemento.value for elemento in app.markdown)
    assert '<table class="abs-mapa"' in html
    assert "1/nov." in html
    assert "30/nov." in html
    assert "Alex Bernardes Da Silva" in html
    assert "NET-ABCDM" in html
    assert ">FE</td>" in html  # férias de 03 a 05/11
    assert ">AT/FE</td>" in html  # atestado + férias em 04/11
    assert len(app.get("form")) == 0  # mapa somente leitura; editor fica na chamada


def test_pagina_absenteismo_com_grade_oferece_edicao_direta() -> None:
    app = _rodar(origem_grade=True)
    assert not app.exception
    assert len(app.get("form")) >= 1
    textos = "\n".join(elemento.value for elemento in app.caption)
    assert "Fonte principal: aba absenteismo" in textos
    assert not any("Criar Lista de Presença a partir" in str(e.label) for e in app.expander)


def test_chamada_diaria_e_padrao_e_periodo_e_opcional() -> None:
    app = _rodar(origem_grade=False)
    assert not app.exception
    visualizacao = next(s for s in app.selectbox if s.label == "Visualização")
    assert visualizacao.value == "Chamada do dia"
    assert any(s.label == "Data da chamada" for s in app.selectbox)
    assert any(t.label == "Somente pendentes" for t in app.toggle)
    assert any(t.label == "Exibir dados cadastrais" for t in app.toggle)
    assert not any(s.label == "Dias do período" for s in app.multiselect)
    visualizacao.select("Preenchimento por período").run()
    assert not app.exception
    assert any(s.label == "Dias do período" for s in app.multiselect)


def test_busca_local_sem_resultados_mostra_orientacao() -> None:
    app = _rodar(origem_grade=False)
    busca = next(t for t in app.text_input if t.label == "Localizar técnico")
    busca.input("tecnico-inexistente-xyz").run()
    assert not app.exception
    assert any("Nenhum técnico encontrado" in aviso.value for aviso in app.info)


def test_acoes_diarias_exigem_confirmacao_antes_de_enviar():
    app = _rodar(origem_grade=False)
    assert not app.exception
    botao = next(b for b in app.button if b.label == "Confirmar lote")
    botao.click().run()
    assert not app.exception
    assert any("Informe o responsável e confirme" in erro.value for erro in app.error)
    assert any(t.label == "Preencher em lote" for t in app.tabs)
    assert any(t.label == "Corrigir com histórico" for t in app.tabs)
    assert any(t.label == "Fechar chamada" for t in app.tabs)


def test_forca_trabalho_tem_agrupamento_e_consulta_independente():
    app = _rodar(origem_grade=False)
    app.radio(key="presenca_area").set_value("Força de Trabalho").run()
    assert not app.exception
    agrupamento = next(s for s in app.selectbox if s.label == "Agrupar força de trabalho por")
    agrupamento.select("Monitor").run()
    assert not app.exception
    consulta = next(t for t in app.text_input if t.label == "Buscar na força de trabalho")
    consulta.input("tecnico-inexistente-xyz").run()
    assert not app.exception
    assert any("Nenhum técnico encontrado. Ajuste o nome" in i.value for i in app.info)


def test_navegacao_prioriza_chamada_e_separa_areas() -> None:
    app = _rodar(origem_grade=True)
    assert not app.exception
    navegacao = app.radio(key="presenca_area")
    assert navegacao.options == [
        "Chamada diária", "Força de Trabalho", "Mapa mensal", "Análises", "Histórico e dados",
    ]
    assert navegacao.value == "Chamada diária"
    assert any(e.label == "Ações da chamada · lote, correção, fechamento e Excel" for e in app.expander)
    assert not any('<table class="abs-mapa"' in e.value for e in app.markdown)
    assert not any(s.label == "Agrupar força de trabalho por" for s in app.selectbox)
    assert not any(e.key == "absenteismo_preencher_grade" for e in app.toggle)


def test_todas_as_visoes_de_analise_renderizam() -> None:
    app = _rodar(origem_grade=True)
    app.radio(key="presenca_area").set_value("Análises").run()
    for visao in ["Calendário", "Bases e monitores", "Hoje e próximas", "Tipos de ausência"]:
        app.radio(key="presenca_tipo_analise").set_value(visao).run()
        assert not app.exception


def test_periodo_de_analise_nao_remove_datas_da_chamada() -> None:
    app = _rodar(origem_grade=True)
    app.date_input(key="absenteismo_periodo_inicio").set_value(date(2026, 11, 10))
    app.date_input(key="absenteismo_periodo_fim").set_value(date(2026, 11, 12))
    app.run()
    assert not app.exception
    datas = next(s for s in app.selectbox if s.label == "Data da chamada")
    assert len(datas.options) == 30


def test_chamada_nao_carrega_cadastro_auxiliar_nem_mapa_oculto(monkeypatch) -> None:
    import services.absenteismo as ausencias
    import services.hierarquia as hierarquia

    def nao_deveria_executar(*args, **kwargs):
        raise AssertionError("Carga oculta desnecessária durante a chamada")

    monkeypatch.setattr(hierarquia, "lista_ativos_da_sessao", nao_deveria_executar)
    # A lista diária usa a implementação importada em services.lista_presenca;
    # a página não deve construir também o mapa mensal oculto.
    monkeypatch.setattr(ausencias, "montar_matriz_ausencias", nao_deveria_executar)
    app = _rodar(origem_grade=True)
    assert not app.exception
    assert any(s.label == "Data da chamada" for s in app.selectbox)


def test_voltar_a_chamada_apos_consultar_mapa() -> None:
    app = _rodar(origem_grade=True)
    app.radio(key="presenca_area").set_value("Mapa mensal").run()
    assert not app.exception
    assert not any(s.label == "Data da chamada" for s in app.selectbox)
    app.radio(key="presenca_area").set_value("Chamada diária").run()
    assert not app.exception
    assert any(s.label == "Data da chamada" for s in app.selectbox)


def test_mapa_mensal_inclui_presenca_operacional_e_pendencias_sem_filtro_de_tipo():
    app = _rodar(origem_grade=True)
    snapshot = app.session_state["presenca_grade_snapshot"]
    extras = pd.DataFrame([
        {"ID": "presenca", "Login": "Z663524", "Técnico": "Alex De Jesus Freire",
         "Tipo": "Presente", "Data Início": "01/11/2026", "Data Fim": "01/11/2026", "Status": "Ativo"},
        {"ID": "operacional", "Login": "Z663524", "Técnico": "Alex De Jesus Freire",
         "Tipo": "DUPLADO", "Data Início": "02/11/2026", "Data Fim": "02/11/2026", "Status": "Ativo"},
    ])
    snapshot["registros"] = normalizar_registros(pd.concat([_registros(), extras], ignore_index=True))
    app.session_state["presenca_grade_snapshot"] = snapshot
    app.radio(key="presenca_area").set_value("Mapa mensal").run()
    app.multiselect(key="absenteismo_filtro_tipo").set_value(["Férias"]).run()
    assert not app.exception
    html = "\n".join(e.value for e in app.markdown)
    assert ">P</td>" in html
    assert ">NP</td>" in html
    assert ">duplado</td>" in html.casefold()
    assert ">AT/FE</td>" in html  # filtro não apaga atestado sobreposto
    assert 'title="Presente"' in html
    assert 'title="Não preenchido"' in html
    assert "TOTAL DE MARCAÇÕES" in html
    assert "TOTAL DE AUSÊNCIAS" not in html
    valores = {m.label: m.value for m in app.metric}
    assert valores["Dias preenchidos"] == "5"
    assert valores["Dias não preenchidos"] == "85"


def test_filtro_base_recorta_chamada_mapa_e_exportacao():

    app = _rodar(origem_grade=True)
    filtro = app.multiselect(key="absenteismo_filtro_base")
    assert set(filtro.options) == {"Abcdm-Totale", "Spo-Totalleste"}
    filtro.set_value(["Spo-Totalleste"]).run()
    assert not app.exception
    # Alex tem registros históricos em outra base: não pode reaparecer na grade.
    editor = app.dataframe[0].value
    assert editor["Login"].tolist() == ["Z657046"]
    app.radio(key="presenca_area").set_value("Mapa mensal").run()
    assert not app.exception
    html = "\n".join(e.value for e in app.markdown)
    assert "Abner Makalas" in html
    assert "Alex Bernardes Da Silva" not in html
    # O download usa a mesma matriz filtrada exibida na tela.
    assert any(e.key == "absenteismo_mapa_download" for e in app.get("download_button"))
    app.multiselect(key="absenteismo_filtro_base").set_value(["Abcdm-Totale", "Spo-Totalleste"]).run()
    assert not app.exception
    html = "\n".join(e.value for e in app.markdown)
    assert "Alex Bernardes Da Silva" in html
    assert "Abner Makalas" in html
    app.multiselect(key="absenteismo_filtro_base").set_value([]).run()
    assert not app.exception
    assert any("Todas as bases" in e.value for e in app.caption)
