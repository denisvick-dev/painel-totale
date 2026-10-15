"""Testes de guarda para a refatoração de arquitetura, performance e higiene do repositório."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd

import config.settings as cfg
import pages.envio_excel as envio_excel
import robo
import services.google_drive_client as drive_client

RAIZ = Path(__file__).resolve().parents[1]
IGNORADOS = {"__pycache__", ".venv", ".venv-check", ".git", "build", "dist"}


def test_diretorios_legados_e_submodulos_orfaos_removidos() -> None:
    """Diretório old/ e submódulos órfãos não devem existir na árvore."""
    for nome in ("old", "painel-totale", "painel-totale-teste"):
        assert not (RAIZ / nome).exists(), f"Artefato órfão/legado ainda existe: {nome}"


def test_cache_geoespacial_migrado_para_parquet_sem_pickle() -> None:
    """O cache geoespacial deve usar Parquet e rota_inicial.py não deve usar pickle."""
    assert not (RAIZ / ".streamlit_cache" / "geo_sp_2022.pkl").exists()
    assert (RAIZ / ".streamlit_cache" / "geo_sp_2022.parquet").is_file()

    codigo_rota = (RAIZ / "pages" / "rota_inicial.py").read_text(encoding="utf-8")
    assert "pickle" not in codigo_rota
    assert "geo_sp_2022.parquet" in codigo_rota


def test_requirements_possui_versoes_minimas_fixadas() -> None:
    """Todas as dependências em requirements.txt devem declarar piso de versão (>=)."""
    linhas = [
        ln.strip()
        for ln in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert linhas
    sem_piso = [ln for ln in linhas if not re.search(r">=\s*\d+", ln)]
    assert not sem_piso, f"Pacotes sem versão mínima em requirements.txt: {sem_piso}"


def test_robo_em_um_unico_arquivo() -> None:
    """Motor, monitor e CLI usam o mesmo módulo, sem submódulos duplicados."""
    assert (RAIZ / "robo.py").is_file()
    assert not list((RAIZ / "robo").glob("*.py"))  # robo/dados legada é permitida
    assert Path(robo.__file__).resolve() == RAIZ / "robo.py"
    for nome in robo.__all__:
        assert hasattr(robo, nome), nome
    for nome in ("processar_candidatos", "executar_ciclo_headless", "renderizar_robo_local"):
        assert getattr(robo, nome).__module__ == "robo"


def test_robo_local_exclusivo_na_pagina_envio_excel() -> None:
    """Os controles ficam no corpo da Central, não no shell ou em outras páginas."""
    codigo_app = (RAIZ / "streamlit_app.py").read_text(encoding="utf-8")
    assert "renderizar_robo_local" not in codigo_app

    codigo_envio = (RAIZ / "pages" / "envio_excel.py").read_text(encoding="utf-8")
    arvore_envio = ast.parse(codigo_envio)
    chamadas_robo = [
        no
        for no in ast.walk(arvore_envio)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Name)
        and no.func.id == "renderizar_robo_local"
    ]
    assert "from robo import renderizar_robo_local" in codigo_envio
    assert len(chamadas_robo) == 1
    for pagina in ("volumetria.py", "quebra_geral.py", "quebra_unificada.py"):
        codigo_pagina = (RAIZ / "pages" / pagina).read_text(encoding="utf-8")
        assert "renderizar_robo_local(" not in codigo_pagina
    assert "_aplicar_etl_robo_global" in (
        RAIZ / "pages" / "quebra_unificada.py"
    ).read_text(encoding="utf-8")
    assert "df_memoria_raw" in (RAIZ / "robo.py").read_text(encoding="utf-8")


def test_saida_robo_preserva_os_dois_contratos_de_sessao(monkeypatch) -> None:
    """O resultado local conserva `dados_totale` e `df_memoria` para consumidores."""
    from types import SimpleNamespace

    estado: dict[str, object] = {}
    monkeypatch.setattr(envio_excel, "st", SimpleNamespace(session_state=estado))
    original = pd.DataFrame({" nome ": ["Técnico"], " os ": [42]})

    resultado = envio_excel._pipeline_robo_local(original, pd.DataFrame())

    assert resultado.columns.tolist() == ["NOME", "OS"]
    assert original.columns.tolist() == [" nome ", " os "]
    assert estado["dados_totale"] is resultado
    assert estado["df_memoria"] is resultado


def test_config_e_services_centralizam_google_drive_e_sheets() -> None:
    """A camada config/ + services/ fornece IDs, URLs e parser CSV/Drive."""
    assert cfg.SHEET_ID_ATIVOS
    assert cfg.SHEET_ID_PROD
    assert cfg.DRIVE_ID_CONS
    assert cfg.DRIVE_ID_INDICADORES
    assert cfg.URL_ATIVOS_EDIT.endswith("/edit")
    assert "export?format=csv" in cfg.URL_ATIVOS_CSV

    urls = drive_client.urls_download_drive(cfg.URL_CONS_DOWNLOAD)
    assert len(urls) == 2
    assert "drive.usercontent.google.com" in urls[1]
    assert not drive_client.e_resposta_html(b"col1;col2\n1;2", "text/csv")
    assert drive_client.e_resposta_html(b"<!DOCTYPE html><html></html>", "text/html")


def test_sem_cache_data_clear_global_nas_paginas() -> None:
    """Nenhuma página deve invalidar todo o cache global com st.cache_data.clear()."""
    ofensas: list[str] = []
    for caminho in sorted((RAIZ / "pages").glob("*.py")):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr == "clear"
                and isinstance(no.func.value, ast.Attribute)
                and no.func.value.attr in {"cache_data", "cache_resource"}
            ):
                ofensas.append(f"{caminho.relative_to(RAIZ)}:{no.lineno}")
    assert not ofensas, (
        "Uso global de st.cache_data.clear() / st.cache_resource.clear() encontrado "
        f"(use invalidação granular `<funcao>.clear()`): {ofensas}"
    )
