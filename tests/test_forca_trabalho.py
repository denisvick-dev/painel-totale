from datetime import date

import pandas as pd

from services.absenteismo import normalizar_registros
from services.forca_trabalho import calcular_forca_trabalho


def test_quadro_deduplicado_sobreposicoes_cancelamento_e_externos():
    quadro = pd.DataFrame({"LOGIN": ["Z1", "Z1", "Z2"], "TÉCNICO": ["A", "A", "B"],
                           "BASE": ["ABC"] * 3, "MONITOR": ["M"] * 3})
    registros = normalizar_registros(pd.DataFrame([
        {"ID": str(i), "Login": login, "Tipo": tipo, "Status": status,
         "Data Início": "2026-11-17", "Data Fim": "2026-11-17"}
        for i, (login, tipo, status) in enumerate([
            ("Z1", "Falta", "Ativo"), ("Z1", "Atestado", "Ativo"),
            ("Z2", "Férias", "Cancelado"), ("Z9", "Falta", "Ativo"),
        ])
    ]))
    resumo, detalhes = calcular_forca_trabalho(quadro, registros, date(2026, 11, 17))
    assert resumo.iloc[0]["Quadro"] == 2
    assert resumo.iloc[0]["Ausentes"] == 1
    assert resumo.iloc[0]["Disponíveis estimados"] == 1
    assert resumo.iloc[0]["Disponibilidade (%)"] == 50
    assert len(detalhes) == 2


def test_sem_quadro_nao_inventa_disponibilidade():
    resumo, detalhes = calcular_forca_trabalho(pd.DataFrame(), normalizar_registros(None), date(2026, 11, 17))
    assert resumo.empty
    assert detalhes.empty


def test_fora_da_data_e_dados_de_grupo_ausentes():
    quadro = pd.DataFrame({"LOGIN": ["Z1"], "TÉCNICO": ["A"]})
    resumo, detalhes = calcular_forca_trabalho(quadro, normalizar_registros(None), date(2026, 11, 18))
    assert resumo.iloc[0]["Base"] == "Não informado"
    assert resumo.iloc[0]["Disponíveis estimados"] == 1
    assert detalhes.iloc[0]["Situação no dia"] == "Disponível estimado"


def test_visao_agregada_usa_taxa_ponderada():
    from components.forca_trabalho import agrupar_visao
    resumo = pd.DataFrame({
        "Base": ["ABC", "ABC"], "Monitor": ["A", "B"],
        "Quadro": [2, 8], "Ausentes": [2, 0],
        "Disponíveis estimados": [0, 8], "Disponibilidade (%)": [0.0, 100.0],
    })
    agregado = agrupar_visao(resumo, "Base")
    assert agregado.iloc[0]["Disponibilidade (%)"] == 80.0
    assert agregado.iloc[0]["Quadro"] == 10


def test_exportacao_profissional_tem_data_filtros_e_cabecalho():
    import io

    from openpyxl import load_workbook

    from components.forca_trabalho import excel_forca_trabalho
    quadro = pd.DataFrame({"LOGIN": ["Z1"], "TÉCNICO": ["A"]})
    resumo, detalhes = calcular_forca_trabalho(quadro, normalizar_registros(None), date(2026, 11, 18))
    arquivo = excel_forca_trabalho(resumo, detalhes, date(2026, 11, 18))
    livro = load_workbook(io.BytesIO(arquivo))
    assert livro.sheetnames == ["Resumo", "Técnicos"]
    assert livro["Resumo"].freeze_panes == "C2"
    assert livro["Resumo"].auto_filter.ref
    assert livro["Resumo"].cell(2, livro["Resumo"].max_column).value == "18/11/2026"
    assert livro["Resumo"]["A1"].font.bold
