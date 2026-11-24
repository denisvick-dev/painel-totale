from datetime import date

import pandas as pd
import pytest

from services.absenteismo import normalizar_registros, resumir_controle
from services.lista_presenca import (
    OPCOES_STATUS_DIA,
    montar_lista_presenca,
    montar_tabela_chamada_diaria,
    registros_da_chamada_diaria,
    registros_da_presenca,
    resumo_presenca,
    status_tela_para_tipo,
    tipo_para_status_tela,
)

DIA = date(2026, 11, 17)


def _quadro():
    return pd.DataFrame(
        {
            "LOGIN": ["Z1", "Z2", "Z3"],
            "TÉCNICO": ["A", "B", "C"],
            "MONITOR": ["M"] * 3,
            "BASE": ["ABC"] * 3,
        }
    )


def _registros():
    return normalizar_registros(
        pd.DataFrame(
            [
                {"ID": "1", "Login": "Z1", "Tipo": "Presente", "Data Início": DIA.isoformat()},
                {"ID": "2", "Login": "Z2", "Tipo": "Falta", "Data Início": DIA.isoformat()},
            ]
        )
    )


def test_presente_ausente_pendente_sao_distintos():
    matriz = montar_lista_presenca(_registros(), _quadro(), DIA, DIA)
    assert resumo_presenca(matriz, DIA) == {"Presentes": 1, "Ausentes": 1, "Pendentes": 1}


def test_presenca_nao_entra_em_ausencias():
    resumo = resumir_controle(_registros(), periodo_inicio=DIA, periodo_fim=DIA, hoje=DIA)
    assert resumo["tecnicos_periodo"] == 1


def test_preenchimento_presente_gera_registro_persistivel():
    original = montar_lista_presenca(normalizar_registros(None), _quadro(), DIA, DIA)
    editada = original.copy()
    editada.at[0, DIA] = "Presente"
    novos = registros_da_presenca(original, editada)
    assert len(novos) == 1
    assert novos[0]["Tipo"] == "Presente"
    relida = normalizar_registros(pd.DataFrame(novos))
    assert (
        resumo_presenca(montar_lista_presenca(relida, _quadro(), DIA, DIA), DIA)["Presentes"] == 1
    )


def test_status_diario_usa_rotulos_da_planilha_e_mapeia_tipos_canonicos():
    assert OPCOES_STATUS_DIA == (
        "", "ATIVO", "ATESTADO", "FALTA", "FOLGA", "LICENÇA", "TREINAMENTO",
        "SUSPENSÃO", "BAIXA DE KIT", "FÉRIAS", "AFASTADO",
    )
    assert status_tela_para_tipo("ATIVO") == "Presente"
    assert status_tela_para_tipo("AFASTADO") == "Afastamento"
    assert status_tela_para_tipo("BAIXA DE KIT") == "Baixa De Kit"
    assert tipo_para_status_tela("Baixa De Kit") == "BAIXA DE KIT"
    assert all(
        tipo_para_status_tela(status_tela_para_tipo(status)) == status
        for status in OPCOES_STATUS_DIA[1:]
    )
    assert tipo_para_status_tela("Não preenchido") == ""


def test_tabela_diaria_tem_layout_exato_e_persiste_situacoes_na_grade():
    original = pd.DataFrame(
        {
            "Cód.Equipe": ["EQ-01", "EQ-02"],
            "Cód.Aux.Equipe": ["AUX-1", "AUX-2"],
            "RE": ["8368", "8496"],
            "Login": ["Z1", "Z2"],
            "Técnico": ["Ana", "Bia"],
            "Monitor": ["Supervisor A", "Supervisor B"],
            "Base": ["ABC", "ABC"],
            DIA: ["Não preenchido", "Não preenchido"],
        }
    )
    tabela = montar_tabela_chamada_diaria(original, DIA)
    assert tabela.columns.tolist() == [
        "Cód.Equipe", "Cód.Aux.Equipe", "Matrícula", "Nome Equipe", "Supervisor", "Status Dia",
    ]
    assert tabela["Matrícula"].tolist() == ["8368", "8496"]
    assert tabela["Status Dia"].tolist() == ["", ""]

    tabela.loc[0, "Status Dia"] = "ATIVO"
    tabela.loc[1, "Status Dia"] = "BAIXA DE KIT"
    novos = registros_da_chamada_diaria(original, tabela, DIA)
    assert [(registro["Login"], registro["Tipo"]) for registro in novos] == [
        ("Z1", "Presente"), ("Z2", "BAIXA DE KIT"),
    ]
    assert all(registro["Data Início"] == DIA.isoformat() for registro in novos)


def test_tabela_diaria_compacta_exibe_re_login_tecnico_monitor_e_status():
    original = pd.DataFrame(
        {
            "RE": ["8368", "8496"],
            "Login": ["Z641759", "Z663524"],
            "Técnico": ["Ana", "Bia"],
            "Monitor": ["Edson Marco Pinheiro", "Edson Marco Pinheiro"],
            "Base": ["ABC", "ABC"],
            DIA: ["Não preenchido", "Não preenchido"],
        }
    )
    tabela = montar_tabela_chamada_diaria(original, DIA, layout="simples")

    assert tabela.columns.tolist() == ["RE", "Login", "Técnico", "Monitor", "Status"]
    assert tabela["Login"].tolist() == ["Z641759", "Z663524"]
    assert tabela["Status"].tolist() == ["", ""]

    tabela.loc[0, "Status"] = "ATIVO"
    novos = registros_da_chamada_diaria(original, tabela, DIA)
    assert [(registro["Login"], registro["Tipo"]) for registro in novos] == [
        ("Z641759", "Presente")
    ]

    tabela.loc[1, "Monitor"] = "Outro monitor"
    with pytest.raises(ValueError, match="cadastr"):
        registros_da_chamada_diaria(original, tabela, DIA)


def test_tabela_diaria_protege_cadastro_e_nao_reescreve_status_existente():
    original = pd.DataFrame(
        {
            "RE": ["8368"],
            "Login": ["Z1"],
            "Técnico": ["Ana"],
            "Monitor": ["Supervisor A"],
            "Base": ["ABC"],
            DIA: ["Baixa De Kit"],
        }
    )
    tabela = montar_tabela_chamada_diaria(original, DIA)
    assert tabela.loc[0, "Status Dia"] == "BAIXA DE KIT"
    assert registros_da_chamada_diaria(original, tabela, DIA) == []

    tabela.loc[0, "Nome Equipe"] = "Outra pessoa"
    with pytest.raises(ValueError, match="cadastr"):
        registros_da_chamada_diaria(original, tabela, DIA)


def test_cancelamento_remove_presenca_e_ausencia_tem_precedencia():
    registros = _registros()
    registros.loc[registros["ID"].eq("1"), "Status"] = "Cancelado"
    matriz = montar_lista_presenca(registros, _quadro(), DIA, DIA)
    assert resumo_presenca(matriz, DIA)["Pendentes"] == 2


def test_planilha_externa_normalizacao_e_resumo():
    from services.lista_presenca import (
        identificar_colunas_dias_planilha,
        normalizar_planilha_lista_presenca,
        resumir_planilha_lista_presenca,
    )

    bruto = pd.DataFrame(
        {
            "RE": ["8368", "8496"],
            "Login": ["Z641759", "Z663524"],
            "Técnico": ["ALEX BERNARDES", "ALEX DE JESUS"],
            "Monitor": ["EDSON", "EDSON"],
            "U.N.": ["ABCDM-TOTALE", "ABCDM-TOTALE"],
            "Base": ["NET-ABCDM", "NET-ABCDM"],
            "1/nov.": ["", ""],
            "3/nov.": ["ativo", "falta"],
            "4/nov.": ["ATIVO", "ATESTADO"],
        }
    )
    normalizado = normalizar_planilha_lista_presenca(bruto)
    assert identificar_colunas_dias_planilha(normalizado) == ["1/nov.", "3/nov.", "4/nov."]
    assert normalizado.loc[0, "1/nov."] == "Não preenchido"
    assert normalizado.loc[0, "3/nov."] == "ATIVO"

    resumo = resumir_planilha_lista_presenca(normalizado)
    assert resumo == {
        "tecnicos": 2,
        "dias_total": 3,
        "dias_preenchidos": 2,
        "ativo": 2,
        "falta": 1,
        "atestado": 1,
        "outros": 0,
    }


def _planilha_mensal_executiva():
    from services.lista_presenca import normalizar_planilha_lista_presenca

    return normalizar_planilha_lista_presenca(
        pd.DataFrame(
            {
                "Login": ["Z1", "Z2", "Z3"],
                "Técnico": ["Ana", "Bia", "Caio"],
                "Monitor": ["Monitor A", "Monitor A", "Monitor B"],
                "Base": ["NET-ABCDM", "NET-ABCDM", "NET-LESTE"],
                "U.N.": ["ABCDM-TOTALE", "ABCDM-TOTALE", "LESTE"],
                "1/nov.": ["ATIVO", "FALTA", ""],
                "2/nov.": ["FALTA", "ATESTADO", "FALTA"],
                "3/nov.": ["", "ATIVO", "FOLGA"],
                "1/dez.": ["ATESTADO", "", "ATIVO"],
            }
        )
    )


def test_resumo_executivo_conta_status_pendencias_e_outros_no_mes():
    from services.lista_presenca import resumir_marcacoes_presenca

    dados = _planilha_mensal_executiva()
    resumo = resumir_marcacoes_presenca(dados, ["1/nov.", "2/nov.", "3/nov."])
    assert resumo == {
        "tecnicos": 3,
        "dias_total": 3,
        "total_marcacoes": 9,
        "dias_preenchidos": 7,
        "ativo": 2,
        "falta": 3,
        "atestado": 1,
        "nao_preenchido": 2,
        "outros": 1,
        "faltas_atestados": 4,
        "percentual_presenca": 2 / 7 * 100,
        "percentual_preenchimento": 7 / 9 * 100,
    }


def test_agrupa_resumo_por_monitor_base_e_tecnico():
    from services.lista_presenca import agrupar_marcacoes_presenca

    dados = _planilha_mensal_executiva()
    dias = ["1/nov.", "2/nov.", "3/nov."]
    por_base = agrupar_marcacoes_presenca(dados, dias, ["Monitor", "Base"])
    abcdm = por_base.loc[por_base["Base"].eq("NET-ABCDM")].iloc[0]
    assert abcdm["Técnicos"] == 2
    assert abcdm["ATIVO"] == 2
    assert abcdm["FALTA"] == 2
    assert abcdm["ATESTADO"] == 1
    assert abcdm["FALTA + ATESTADO"] == 3
    assert abcdm["Não preenchido"] == 1
    assert abcdm["% Presença"] == 40.0

    por_tecnico = agrupar_marcacoes_presenca(dados, dias, ["Técnico", "Login", "Monitor", "Base"])
    top = por_tecnico.sort_values("FALTA + ATESTADO", ascending=False).iloc[0]
    assert top["Técnico"] == "Bia"
    assert top["FALTA + ATESTADO"] == 2
    assert top["FALTA"] == 1
    assert top["ATESTADO"] == 1


def test_percentual_nao_trata_pendencia_sem_marcacao_como_zero_presenca():
    from services.lista_presenca import agrupar_marcacoes_presenca, resumir_marcacoes_presenca

    dados = pd.DataFrame(
        {
            "Login": ["Z1"],
            "Técnico": ["Ana"],
            "Monitor": ["Monitor A"],
            "1/nov.": ["Não preenchido"],
        }
    )
    resumo = resumir_marcacoes_presenca(dados, ["1/nov."])
    por_monitor = agrupar_marcacoes_presenca(dados, ["1/nov."], "Monitor")

    assert pd.isna(resumo["percentual_presenca"])
    assert pd.isna(por_monitor.iloc[0]["% Presença"])


def test_agrupar_colunas_dia_separa_meses_em_portugues():
    from services.lista_presenca import agrupar_colunas_dias_por_mes

    assert agrupar_colunas_dias_por_mes(["1/nov.", "2/nov.", "1/dez."]) == {
        "Novembro": ["1/nov.", "2/nov."],
        "Dezembro": ["1/dez."],
    }


def test_excel_executivo_tem_recorte_e_resumo_em_abas_separadas():
    from io import BytesIO

    from openpyxl import load_workbook

    from services.lista_presenca import (
        agrupar_marcacoes_presenca,
        gerar_excel_executivo_presenca,
    )

    dados = _planilha_mensal_executiva()
    recorte = dados.loc[
        dados["Monitor"].eq("Monitor A"),
        ["Login", "Técnico", "Monitor", "Base", "1/nov.", "2/nov.", "3/nov."],
    ]
    resumo = agrupar_marcacoes_presenca(
        recorte, ["1/nov.", "2/nov.", "3/nov."], ["Monitor", "Base"]
    )
    conteudo = gerar_excel_executivo_presenca(recorte, resumo)
    arquivo = load_workbook(BytesIO(conteudo), data_only=True)

    assert arquivo.sheetnames == ["Recorte filtrado", "Resumo Monitor Base"]
    assert arquivo["Recorte filtrado"].max_row == 3
    assert arquivo["Recorte filtrado"].freeze_panes == "A2"
    assert arquivo["Resumo Monitor Base"].max_row == 2
    assert arquivo["Resumo Monitor Base"]["K2"].value == 3  # faltas + atestados
