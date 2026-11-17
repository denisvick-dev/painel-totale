from datetime import date

import pandas as pd
import pytest

from services.absenteismo import normalizar_registros
from services.lista_presenca import montar_lista_presenca
from services.presenca_operacoes import corrigir_dia, mesclar_conferindo, preparar_lote

DIA = date(2026, 11, 17)


def registros(*linhas):
    return normalizar_registros(pd.DataFrame([
        {"ID": id_, "Login": login, "Tipo": tipo, "Data Início": "2026-11-16",
         "Data Fim": "2026-11-18", "Status": "Ativo", "Técnico": login}
        for id_, login, tipo in linhas
    ]))


def test_correcao_preserva_outros_dias_e_auditoria():
    base = registros(("1", "Z1", "Férias"))
    local = corrigir_dia(base, "Z1", DIA, "Presente", "Retornou antes", "Maria")
    assert local.loc[local["ID"].eq("1"), "Status"].iloc[0] == "Cancelado"
    ativos = local.loc[local["Status"].eq("Ativo")]
    assert len(ativos) == 3
    assert ativos.loc[ativos["Tipo"].eq("Presente"), "Motivo"].str.contains("Maria.*Retornou antes").all()
    assert set(ativos["_inicio"].dt.day) == {16, 17, 18}
    assert len(mesclar_conferindo(base, local, base)) == 4


@pytest.mark.parametrize("motivo, autor", [("", "Maria"), ("Motivo", " ")])
def test_correcao_exige_motivo_e_autor(motivo, autor):
    with pytest.raises(ValueError):
        corrigir_dia(registros(("1", "Z1", "Falta")), "Z1", DIA, "Presente", motivo, autor)


def test_lote_apenas_pendentes_e_selecao_explicita():
    base = registros(("1", "Z1", "Falta"))
    quadro = pd.DataFrame({"LOGIN": ["Z1", "Z2"], "TÉCNICO": ["A", "B"]})
    matriz = montar_lista_presenca(base, quadro, DIA, DIA)
    novos = preparar_lote(matriz, DIA, ["Z2"], "Presente")
    assert len(novos) == 1
    assert novos[0]["Login"] == "Z2"
    with pytest.raises(ValueError):
        preparar_lote(matriz, DIA, ["Z1", "Z2"], "Presente")
    with pytest.raises(ValueError):
        preparar_lote(matriz, DIA, [], "Presente")


def test_merge_preserva_novo_registro_remoto_e_e_idempotente():
    base = registros(("1", "Z1", "Presente"))
    remoto = registros(("1", "Z1", "Presente"), ("2", "Z2", "Falta"))
    local = registros(("1", "Z1", "Presente"), ("3", "Z3", "Presente"))
    combinado = mesclar_conferindo(base, local, remoto)
    assert set(combinado["ID"]) == {"1", "2", "3"}
    assert len(mesclar_conferindo(base, local, combinado)) == 3


def test_merge_bloqueia_colisao_no_mesmo_tecnico_e_dia():
    base = registros()
    with pytest.raises(ValueError, match="Conflito"):
        mesclar_conferindo(base, registros(("1", "Z1", "Presente")), registros(("2", "Z1", "Falta")))


def test_merge_bloqueia_correcao_de_registro_alterado_remotamente():
    base = registros(("1", "Z1", "Presente"))
    local = corrigir_dia(base, "Z1", DIA, "Falta", "Engano", "Maria")
    remoto = base.copy()
    remoto.loc[:, "Status"] = "Cancelado"
    with pytest.raises(ValueError, match="Conflito"):
        mesclar_conferindo(base, local, remoto)


@pytest.fixture
def planilha_fake(monkeypatch):
    import sys
    from types import SimpleNamespace

    from services import presenca_operacoes as ops
    from services.absenteismo import _df_para_planilha

    class AbaAusente(Exception):
        pass

    monkeypatch.setitem(sys.modules, "gspread.exceptions", SimpleNamespace(WorksheetNotFound=AbaAusente))

    class Aba:
        id = 1
        row_count = 100
        col_count = 20
        def __init__(self, valores=None):
            self.valores = valores or []
        def get_all_values(self):
            return self.valores
        def append_row(self, valores, **kwargs):
            self.valores.append(valores)

    class Planilha:
        def __init__(self):
            self.abas = {"controle_absenteismo": Aba(_df_para_planilha(registros(("1", "Z1", "Presente"))))}
            self.escritas = []
        def worksheet(self, nome):
            if nome not in self.abas:
                raise AbaAusente()
            return self.abas[nome]
        def add_worksheet(self, title, **kwargs):
            self.abas[title] = Aba()
            return self.abas[title]
        def batch_update(self, dados):
            self.escritas.append(dados)

    planilha = Planilha()
    monkeypatch.setattr(ops, "_abrir", lambda: planilha)
    return planilha


def test_salvar_conferencia_e_gravacao_unica(planilha_fake):
    from services.presenca_operacoes import salvar_conferindo
    base = registros(("1", "Z1", "Presente"))
    local = registros(("1", "Z1", "Presente"), ("2", "Z2", "Falta"))
    ok, motivo, confirmados = salvar_conferindo(base, local)
    assert ok and not motivo
    assert len(confirmados) == 2
    assert len(planilha_fake.escritas) == 1


def test_conflito_nao_faz_escrita(planilha_fake):
    from services.presenca_operacoes import salvar_conferindo
    ok, motivo, _ = salvar_conferindo(registros(), registros(("2", "Z1", "Falta")))
    assert not ok and "Conflito" in motivo
    assert not planilha_fake.escritas


def test_fechamento_confere_remoto_e_persiste_responsavel(planilha_fake):
    from services.presenca_operacoes import consultar_fechamentos, fechar_chamada
    quadro = pd.DataFrame({"LOGIN": ["Z1"], "TÉCNICO": ["A"]})
    matriz = montar_lista_presenca(registros(("1", "Z1", "Presente")), quadro, DIA, DIA)
    evento = fechar_chamada(matriz, DIA, "Maria", False)
    assert evento["Presentes"] == 1
    assert evento["Responsável"] == "Maria"
    assert len(consultar_fechamentos(DIA)) == 1


def test_fechamento_exige_confirmacao_das_pendencias(planilha_fake):
    from services.presenca_operacoes import fechar_chamada
    quadro = pd.DataFrame({"LOGIN": ["Z1", "Z2"], "TÉCNICO": ["A", "B"]})
    matriz = montar_lista_presenca(registros(("1", "Z1", "Presente")), quadro, DIA, DIA)
    with pytest.raises(ValueError, match="pendências"):
        fechar_chamada(matriz, DIA, "Maria", False)
    evento = fechar_chamada(matriz, DIA, "Maria", True)
    assert evento["Pendentes"] == 1


def test_fechamento_bloqueia_lista_desatualizada(planilha_fake):
    from services.presenca_operacoes import fechar_chamada
    quadro = pd.DataFrame({"LOGIN": ["Z1"], "TÉCNICO": ["A"]})
    matriz = montar_lista_presenca(registros(), quadro, DIA, DIA)
    with pytest.raises(ValueError, match="mudou"):
        fechar_chamada(matriz, DIA, "Maria", True)
    assert "fechamentos_presenca" not in planilha_fake.abas
