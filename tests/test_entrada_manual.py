"""Regressões da entrada explícita de arquivos e filtros dos dashboards."""
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import pages.quebra_geral as quebra
import pages.volumetria as volumetria

RAIZ = Path(__file__).resolve().parents[1]


def test_automacao_local_removida_do_app() -> None:
    assert not (RAIZ / "robo.py").exists()
    for pasta in ("pages", "components", "services"):
        for arquivo in (RAIZ / pasta).rglob("*.py"):
            codigo = arquivo.read_text().casefold()
            assert "robô" not in codigo, arquivo
            assert "import robo" not in codigo, arquivo
            assert "renderizar_robo" not in codigo, arquivo


def test_upload_manual_compartilha_base_e_nao_reprocessa(monkeypatch) -> None:
    from contextlib import nullcontext

    estado = {}
    reruns = []
    monkeypatch.setattr(quebra, "st", SimpleNamespace(
        session_state=estado, spinner=lambda *_: nullcontext(),
        rerun=lambda: reruns.append(True), error=lambda texto: (_ for _ in ()).throw(AssertionError(texto)),
    ))
    bruto = pd.DataFrame({"OS": ["1"]})
    processado = pd.DataFrame({"TÉCNICO": ["EXEMPLO"]})
    chamadas = []
    monkeypatch.setattr(quebra.DataLoader, "ler_arquivo", staticmethod(lambda *_: bruto))
    def preparar(*args, **kwargs):
        chamadas.append(True)
        return processado
    monkeypatch.setattr(quebra.DataLoader, "preparar_base", staticmethod(preparar))
    arquivo = SimpleNamespace(name="base.csv", getvalue=lambda: b"OS\n1")
    quebra._processar_upload(arquivo, pd.DataFrame())
    quebra._processar_upload(arquivo, pd.DataFrame())
    assert len(chamadas) == 1
    assert len(reruns) == 1
    assert estado["df_memoria_raw"] is bruto
    assert estado["df_memoria"] is processado
    assert estado["origem_dados"] == "Upload (base.csv)"


def test_limpar_filtros_preserva_base_carregada(monkeypatch) -> None:
    estado = {f"vol_filtro_{nome}": ["A"] for nome in ("monitor", "regiao", "tecnico", "status")}
    base = pd.DataFrame({"OS": [1]})
    estado["base_data"] = base
    monkeypatch.setattr(volumetria, "st", SimpleNamespace(session_state=estado))
    volumetria._limpar_filtros_volumetria()
    assert list(estado) == ["base_data"]
    assert estado["base_data"] is base
