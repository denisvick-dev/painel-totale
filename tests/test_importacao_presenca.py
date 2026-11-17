from datetime import date

import pandas as pd
import pytest

from services.absenteismo import normalizar_registros
from services.importacao_presenca import MANTER_PENDENTE, converter_grade, preparar_importacao

REF = date(2026, 11, 1)


def grade():
    return pd.DataFrame({
        "Login": ["Z1", "Z2"], "RE": ["10", "20"], "Técnico": ["Ana", "Bia"],
        "Monitor": ["Mon", "Mon"], "Base": ["ABC", "ABC"], "U.N.": ["U", "U"],
        "1/nov.": ["ATIVO", "FALTA"], "2/nov.": ["", "DUPLADO"],
        "3/nov.": ["ATESTADO", "BAIXA DE KIT"],
    })


def test_preserva_presenca_e_bloqueia_codigos_sem_regra():
    convertidos, pendencias, pulados = converter_grade(grade(), REF)
    assert len(convertidos) == 3
    assert set(convertidos["Tipo"]) == {"Presente", "Falta", "Atestado"}
    assert set(pendencias["Valor"]) == {"DUPLADO", "BAIXA DE KIT"}
    assert pulados == 0
    assert convertidos["Data Início"].str.startswith("2026-11").all()


def test_decisoes_explicitas_e_ids_estaveis():
    mapa = {"DUPLADO": "Presente", "BAIXA DE KIT": MANTER_PENDENTE}
    antes = grade()
    convertidos, pendencias, pulados = converter_grade(antes, REF, mapa)
    assert len(convertidos) == 4
    assert pendencias.empty
    assert pulados == 1
    repetidos, _, _ = converter_grade(antes.iloc[::-1], REF, mapa)
    assert set(convertidos["ID"]) == set(repetidos["ID"])
    pd.testing.assert_frame_equal(antes, grade())


def test_marcacao_sem_login_nao_vira_identidade_por_re():
    bruto = grade()
    bruto.loc[0, "Login"] = ""
    _, pendencias, _ = converter_grade(bruto, REF)
    assert "Login ausente" in pendencias["Motivo"].tolist()


def test_logins_repetidos_na_mesma_data_exigem_revisao():
    bruto = pd.concat([grade(), grade().iloc[:1]], ignore_index=True)
    _, pendencias, _ = converter_grade(bruto, REF)
    assert "Login/dia repetido na grade" in pendencias["Motivo"].tolist()


def test_importacao_nao_duplica_e_nao_ressuscita_cancelado():
    importados, _, _ = converter_grade(grade(), REF)
    lista, quantidade = preparar_importacao(normalizar_registros(None), importados, "Maria")
    assert quantidade == 3
    assert lista["Motivo"].str.contains("Maria").all()
    lista.loc[0, "Status"] = "Cancelado"
    nova, quantidade = preparar_importacao(lista, importados, "Maria")
    assert quantidade == 0
    assert len(nova) == 3
    assert nova["Status"].eq("Cancelado").sum() == 1


def test_importacao_exige_autor_e_nao_sobrescreve_registro_importado():
    importados, _, _ = converter_grade(grade(), REF)
    with pytest.raises(ValueError):
        preparar_importacao(normalizar_registros(None), importados, "")
    modificados = importados.copy()
    modificados.loc[0, "Tipo"] = "Folga"
    with pytest.raises(ValueError, match="correção"):
        preparar_importacao(importados, modificados, "Maria")
