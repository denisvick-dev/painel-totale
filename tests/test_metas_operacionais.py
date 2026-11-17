"""Metas por base e sua aplicação ao resumo, sem executar a página/rede."""
import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from config.metas_operacionais import METAS_PRODUCAO_OS_GERAL, metas_os_da_base


@pytest.mark.parametrize("base,meta", [("NET-ABCDM", 10000), ("NET-GUARULHOS", 10700), ("NET-LESTE", 10300)])
def test_meta_mensal_por_base(base, meta):
    assert metas_os_da_base(base)["meta_base"] == meta
    assert metas_os_da_base(base.removeprefix("NET-").lower())["meta_base"] == meta


def test_consolidado_soma_as_tres_metas():
    assert METAS_PRODUCAO_OS_GERAL["meta_base"] == 31000
    assert metas_os_da_base("OUTRO")["meta_base"] == 11000
    assert metas_os_da_base("NET-LESTE VT")["meta_base"] == 11000


def test_resumo_aplica_meta_correta_a_saldo_percentual_e_status():
    caminho = Path(__file__).resolve().parents[1] / "pages/dashboard_meta.py"
    arvore = ast.parse(caminho.read_text())
    nomes = {"processar_resumo_agrupado", "calcular_atingimento_series", "classificar_semaforo", "_to_float_safe", "_is_na_scalar"}
    funcoes = [no for no in arvore.body if isinstance(no, ast.FunctionDef) and no.name in nomes]
    contexto = {
        "pd": pd, "np": np, "Any": object, "metas_os_da_base": metas_os_da_base,
        "METAS_CONSULTIVO_BASE": {"minima": 400, "meta_base": 525, "alta_perf": 600},
        "contar_tecnicos_validos": lambda s: s.nunique(),
        "adicionar_cenarios_agrupados": lambda df, *args: df,
    }
    exec(compile(ast.Module(body=funcoes, type_ignores=[]), str(caminho), "exec"), contexto)
    # Mesmo volume: atingimento e saldo devem diferir conforme a base.
    prod = pd.DataFrame({
        "CHAVE_AGRUPAMENTO": np.repeat(["NET-ABCDM", "NET-GUARULHOS", "NET-LESTE"], 10000),
        "DATA": pd.Timestamp("2026-11-17"), "TECNICO": "Z1",
    })
    resumo = contexto["processar_resumo_agrupado"](prod, pd.DataFrame(), 1.0, 1.0).set_index("Agrupamento")
    for base, saldo, percentual in [("NET-ABCDM", 0, 100), ("NET-GUARULHOS", 700, 93.5), ("NET-LESTE", 300, 97.1)]:
        assert resumo.loc[base, "O.S. Faltantes"] == saldo
        assert resumo.loc[base, "% Meta O.S. (Proj)"] == percentual
    assert resumo.loc["NET-ABCDM", "Status O.S."] != resumo.loc["NET-GUARULHOS", "Status O.S."]
