import pandas as pd

from services.qualidade_ativos import diagnosticar_ativos


def test_diagnostico_preserva_contagem_antes_de_deduplicar():
    bruto = pd.DataFrame({
        "Login": ["Z1", "Z2", None, "Z1"], "RE": ["10", "10", "20", "30"],
        "Técnico": ["A", "B", "C", "A"], "Monitor": ["M"] * 4,
        "U.N.": ["U"] * 4, "Base": ["B"] * 4,
        "Situação": ["ATIVO", "FÉRIAS", "ATIVO", "INVALIDA"],
        "Ultima_Modificacao": ["12/11/2026", "24/06/2026", "erro", "12/11/2026"],
    })
    antes = bruto.copy(deep=True)
    qualidade = diagnosticar_ativos(bruto)
    assert qualidade["linhas_origem"] == 4
    assert qualidade["logins_validos"] == 2
    assert qualidade["sem_login"] == 1
    assert qualidade["linhas_login_duplicado"] == 2
    assert qualidade["res_repetidos"] == 1
    assert qualidade["ultima_modificacao_cadastral"] == "12/11/2026"
    assert any(o["Linha na origem"] == 4 and o["Verificação"] == "Login ausente" for o in qualidade["ocorrencias"])
    pd.testing.assert_frame_equal(bruto, antes)


def test_vazio_nao_quebra():
    qualidade = diagnosticar_ativos(pd.DataFrame())
    assert qualidade["linhas_origem"] == 0
    assert qualidade["ocorrencias"] == []


def test_carga_anexa_diagnostico_sem_exportar_dados_pessoais(monkeypatch):
    from services import hierarquia
    bruto = pd.DataFrame({"Login": ["Z1", ""], "Técnico": ["A", "B"], "Situação": ["ATIVO", "ATIVO"]})
    monkeypatch.setattr(hierarquia, "_carregar_bruto_ativos", lambda *args, **kwargs: bruto)
    lista = hierarquia.carregar_lista_ativos()
    assert len(lista) == 1
    assert lista.attrs["qualidade_origem"]["linhas_origem"] == 2
    assert lista.attrs["qualidade_origem"]["sem_login"] == 1
    assert "Z1" not in str(lista.attrs["qualidade_origem"])
