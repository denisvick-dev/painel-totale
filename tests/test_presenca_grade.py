from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from services.absenteismo import normalizar_registros
from services.lista_presenca import montar_lista_presenca, resumo_presenca
from services.presenca_grade import interpretar_valores, planejar_alteracoes, salvar_grade

DIA = date(2026, 11, 17)
CABECALHO = ["RE", "Login", "Técnico", "Monitor", "U.N.", "Base", "2026-11-17", "2026-11-18"]


def valores(presenca="ATIVO"):
    return [CABECALHO, ["1", "Z1", "Ana", "Monitor", "UN", "BASE", presenca, "FALTA"],
            ["2", "Z2", "Bia", "Monitor", "UN", "BASE", "", ""]]


def preencher(snapshot, tipo="Presente"):
    return normalizar_registros(pd.concat([
        snapshot["registros"].drop(columns=["_inicio", "_fim"]),
        pd.DataFrame([{"ID": "novo", "Login": "Z2", "Técnico": "Bia", "Tipo": tipo,
                       "Data Início": DIA.isoformat(), "Data Fim": DIA.isoformat()}]),
    ], ignore_index=True))


def test_leitura_presenca_vazio_e_ano_real_do_cabecalho():
    bruto = valores()
    bruto[0] = CABECALHO[:6] + [46343, 46344]  # novembro de 2026, sem inferência por hoje
    snapshot = interpretar_valores(bruto)
    assert all(d.year == 2026 for d in snapshot["dias"])
    assert snapshot["registros"]["Tipo"].tolist() == ["Presente", "Falta"]
    assert len(snapshot["pessoas"]) == 2


def test_rotulo_afastado_da_chamada_e_reconhecido_na_leitura_da_grade():
    snapshot = interpretar_valores(valores("AFASTADO"))
    assert snapshot["registros"]["Tipo"].tolist() == ["Afastamento", "Falta"]


def test_leitura_preserva_codigos_opcionais_do_quadro_para_chamada_diaria():
    cabecalho = ["Cód.Equipe", "Cód.Aux.Equipe", *CABECALHO]
    linha = ["EQ-10", "AUX-10", "1", "Z1", "Ana", "Monitor", "UN", "BASE", "", ""]
    snapshot = interpretar_valores([cabecalho, linha])
    pessoa = snapshot["pessoas"].iloc[0]
    assert pessoa["Cód.Equipe"] == "EQ-10"
    assert pessoa["Cód.Aux.Equipe"] == "AUX-10"


def test_somente_celula_alterada_e_presente_gravado_como_ativo():
    snapshot = interpretar_valores(valores())
    plano = planejar_alteracoes(snapshot, snapshot["registros"], preencher(snapshot), snapshot)
    assert len(plano) == 1
    assert plano[0]["posicao"] == (2, 6)
    assert plano[0]["antes"] == ""
    assert plano[0]["depois"] == "ATIVO"


def test_afastado_e_salvo_com_o_rotulo_do_layout_diario():
    snapshot = interpretar_valores(valores(""))
    plano = planejar_alteracoes(snapshot, snapshot["registros"], preencher(snapshot, "Afastamento"), snapshot)
    assert len(plano) == 1
    assert plano[0]["depois"] == "AFASTADO"


def test_conflito_bloqueia_celula_tocada_mas_preserva_outras():
    snapshot = interpretar_valores(valores())
    alterado = valores()
    alterado[2][6] = "FOLGA"
    with pytest.raises(ValueError, match="Conflito"):
        planejar_alteracoes(snapshot, snapshot["registros"], preencher(snapshot), interpretar_valores(alterado))
    alterado = valores("ATESTADO")  # outra pessoa, não deve impedir o novo preenchimento
    plano = planejar_alteracoes(snapshot, snapshot["registros"], preencher(snapshot), interpretar_valores(alterado))
    assert len(plano) == 1


def test_formula_nunca_e_substituida():
    snapshot = interpretar_valores(valores())
    remoto = interpretar_valores(valores())
    remoto["celulas"][("Z2", DIA)]["formula"] = '=IF(A1,"","")'
    with pytest.raises(ValueError, match="fórmula"):
        planejar_alteracoes(snapshot, snapshot["registros"], preencher(snapshot), remoto)


def test_novo_login_sem_linha_e_data_ausente_nao_criam_colunas():
    snapshot = interpretar_valores(valores())
    novo = preencher(snapshot)
    novo.loc[novo["ID"].eq("novo"), "Login"] = "Z9"
    with pytest.raises(ValueError, match="não existe"):
        planejar_alteracoes(snapshot, snapshot["registros"], novo, snapshot)


def test_grade_invalida_bloqueia_sem_inventar_login():
    bruto = valores()
    bruto[1][1] = ""
    with pytest.raises(ValueError, match="sem login"):
        interpretar_valores(bruto)
    bruto = valores()
    bruto.append(bruto[1])
    with pytest.raises(ValueError, match="repetido"):
        interpretar_valores(bruto)


def test_situacao_operacional_preservada_sem_inferir_falta():
    snapshot = interpretar_valores(valores("DUPLADO"))
    lista = montar_lista_presenca(snapshot["registros"], snapshot["pessoas"], DIA, DIA)
    resumo = resumo_presenca(lista, DIA)
    assert resumo["Presentes"] == resumo["Ausentes"] == 0
    assert resumo["Situação operacional"] == 1
    assert resumo["Pendentes"] == 1


def test_batch_localizado_inclui_auditoria_sem_clear(monkeypatch):
    import sys

    from services import presenca_grade as modulo

    class WorksheetNotFound(Exception):
        pass

    monkeypatch.setitem(sys.modules, "gspread.exceptions", SimpleNamespace(WorksheetNotFound=WorksheetNotFound))
    chamadas = []
    grade = SimpleNamespace(id=42, get_all_values=lambda **kw: valores())
    auditoria = SimpleNamespace(id=43, get_all_values=lambda **kw: [])
    planilha = SimpleNamespace(worksheet=lambda nome: grade if nome == "absenteismo" else auditoria,
                              batch_update=chamadas.append)
    monkeypatch.setattr(modulo, "_abrir", lambda: planilha)
    snapshot = interpretar_valores(valores())
    ok, motivo, confirmado = salvar_grade(snapshot, snapshot["registros"], preencher(snapshot))
    assert ok, motivo
    assert len(chamadas) == 1
    pedidos = chamadas[0]["requests"]
    assert len(pedidos) == 2
    assert pedidos[0]["updateCells"]["range"] == {
        "sheetId": 42, "startRowIndex": 2, "endRowIndex": 3,
        "startColumnIndex": 6, "endColumnIndex": 7,
    }
    assert "appendCells" in pedidos[1]
    assert confirmado["celulas"][("Z2", DIA)]["texto"] == "ATIVO"
    assert len(confirmado["registros"]) == 3


def test_correcao_e_cancelamento_alteram_apenas_o_dia_escolhido():
    from services.presenca_operacoes import corrigir_dia
    snapshot = interpretar_valores(valores())
    local = corrigir_dia(snapshot["registros"], "Z1", DIA, "Atestado", "Documento recebido", "Maria")
    plano = planejar_alteracoes(snapshot, snapshot["registros"], local, snapshot)
    assert len(plano) == 1
    assert plano[0]["depois"] == "ATESTADO"
    local = snapshot["registros"].copy()
    local.loc[local["_inicio"].eq(pd.Timestamp(DIA)), "Status"] = "Cancelado"
    plano = planejar_alteracoes(snapshot, snapshot["registros"], local, snapshot)
    assert len(plano) == 1
    assert plano[0]["depois"] == ""


def test_reordenacao_de_linhas_nao_grava_na_pessoa_errada():
    snapshot = interpretar_valores(valores())
    trocado = valores()
    trocado[1], trocado[2] = trocado[2], trocado[1]
    remoto = interpretar_valores(trocado)
    plano = planejar_alteracoes(snapshot, snapshot["registros"], preencher(snapshot), remoto)
    assert plano[0]["par"] == ("Z2", DIA)
    assert plano[0]["posicao"] == (1, 6)


def test_falha_de_escrita_nao_confirma_snapshot(monkeypatch):
    import sys

    from services import presenca_grade as modulo

    class WorksheetNotFound(Exception):
        pass

    monkeypatch.setitem(sys.modules, "gspread.exceptions", SimpleNamespace(WorksheetNotFound=WorksheetNotFound))
    grade = SimpleNamespace(id=42, get_all_values=lambda **kw: valores())
    auditoria = SimpleNamespace(id=43, get_all_values=lambda **kw: [])
    def falhar(_):
        raise RuntimeError("sem permissão")
    monkeypatch.setattr(modulo, "_abrir", lambda: SimpleNamespace(
        worksheet=lambda nome: grade if nome == "absenteismo" else auditoria, batch_update=falhar))
    snapshot = interpretar_valores(valores())
    ok, motivo, retorno = salvar_grade(snapshot, snapshot["registros"], preencher(snapshot))
    assert not ok and "sem permissão" in motivo
    assert retorno is snapshot
    assert retorno["celulas"][("Z2", DIA)]["texto"] == ""


def test_acesso_grade_define_timeout_de_rede(monkeypatch):
    import services.presenca_grade as grade
    chamadas = []
    planilha = object()
    cliente = SimpleNamespace(
        set_timeout=lambda valor: chamadas.append(valor),
        open_by_key=lambda chave: planilha,
    )
    monkeypatch.setattr(grade, "_cliente_gspread", lambda: cliente)
    assert grade._abrir() is planilha
    assert chamadas == [(5, 20)]
