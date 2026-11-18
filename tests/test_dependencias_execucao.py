"""Smoke test das páginas cujas dependências vão além da suíte mínima."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def test_rota_inicial_abre_sem_base_carregada():
    for modulo in ("folium", "geobr", "geopandas", "streamlit_folium"):
        pytest.importorskip(modulo, reason="Instale requirements-dev.txt para testar mapas")
    pagina = Path(__file__).resolve().parents[1] / "pages" / "rota_inicial.py"
    app = AppTest.from_file(str(pagina), default_timeout=30).run()
    assert not app.exception
