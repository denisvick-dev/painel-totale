"""Garante o padrão visual corporativo aplicado aos dataframes nativos."""
from __future__ import annotations

import tomllib
from pathlib import Path

from streamlit import config

from components.css_global import css_containers

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / ".streamlit" / "config.toml"

COR_CABECALHO = "#0B3A8F"
COR_TEXTO_CABECALHO = "#FFFFFF"
COR_BORDA = "#CBD5E1"


def test_config_traz_tema_corporativo_dos_dataframes() -> None:
    dados = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    tema = dados["theme"]
    assert tema["dataframeHeaderBackgroundColor"] == COR_CABECALHO
    assert tema["dataframeHeaderTextColor"] == COR_TEXTO_CABECALHO
    assert tema["dataframeBorderColor"] == COR_BORDA
    assert dados["theme"]["dark"]["dataframeHeaderTextColor"] == COR_TEXTO_CABECALHO
    assert dados["theme"]["sidebar"]["dataframeHeaderBackgroundColor"] == COR_CABECALHO


def test_streamlit_reconhece_opcoes_de_cabecalho() -> None:
    assert config.get_option("theme.dataframeHeaderBackgroundColor") == COR_CABECALHO
    assert config.get_option("theme.dataframeHeaderTextColor") == COR_TEXTO_CABECALHO
    assert config.get_option("theme.dataframeBorderColor") == COR_BORDA


def test_css_das_tabelas_usa_cabecalho_azul_e_linhas_escurecidas() -> None:
    css = css_containers()
    assert '[data-testid="stDataFrame"]' in css
    assert '[data-testid="stTable"]' in css
    assert "linear-gradient(180deg, #012869 0%, #1E40AF 100%)" in css
    assert "tbody tr:nth-child(even) td" in css
    assert "text-transform: uppercase" in css
