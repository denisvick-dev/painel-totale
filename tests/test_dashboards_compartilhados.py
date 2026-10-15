"""Testes da camada compartilhada dos dashboards (v3.7.0).

Cobre os quatro serviços novos e o esqueleto de página:

* :mod:`services.texto` — normalização de texto, colunas, logins e pt-BR;
* :mod:`services.planilhas` — leitura de uploads e exportação CSV/XLSX;
* :mod:`services.hierarquia` — lista de ativos canônica (Login/Técnico/Monitor/Base);
* :mod:`services.dados_sessao` — contrato das bases carregadas na sessão;
* :mod:`components.dashboards` — abertura/fechamento padrão dos painéis.

    pytest tests/test_dashboards_compartilhados.py
"""

from __future__ import annotations

import io
import sys
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from components.dashboards import chips_de_contexto, versao_do_portal
from services.dados_sessao import (
    ResumoCarga,
    concatenar_abas,
    obter_base,
    resumir_carga,
)
from services.hierarquia import COLUNAS_CANONICAS, hierarquia_vazia, normalizar_hierarquia
from services.planilhas import (
    gerar_csv,
    gerar_excel,
    gerar_excel_multiabas,
    ler_bytes,
    nome_com_carimbo,
)
from services.texto import (
    buscar_coluna,
    colunas_presentes,
    escapar_html,
    formatar_inteiro,
    formatar_numero,
    formatar_percentual,
    normalizar_login,
    normalizar_texto,
    valor_nan,
    valor_vazio,
)

# ====================================================
# services.texto
# ====================================================


def test_normalizar_login_remove_sufixo_decimal_e_espacos() -> None:
    """``'123.0'`` do Sheets e o float ``123.0`` precisam virar a mesma chave."""
    assert normalizar_login("123.0") == "123"
    assert normalizar_login(123.0) == "123"
    assert normalizar_login(" a.b ") == "A.B"
    assert normalizar_login("00123.00") == "123"
    assert normalizar_login(None) == ""
    assert normalizar_login(float("nan")) == ""


def test_normalizar_texto_e_chave_sao_estaveis() -> None:
    assert normalizar_texto("  São   Paulo ") == "SAO PAULO"
    assert normalizar_texto(None) == ""
    assert valor_vazio("N/A") and valor_vazio(None) and not valor_vazio("SPO")
    assert valor_nan(None) and valor_nan(float("nan"))
    assert not valor_nan("N/A") and not valor_nan("SPO")
    assert escapar_html("<b>x</b>") == "&lt;b&gt;x&lt;/b&gt;"


def test_formatacao_pt_br() -> None:
    assert formatar_numero(1248.5, 2) == "1.248,50"
    assert formatar_inteiro("1234567") == "1.234.567"
    assert formatar_inteiro(None) == "0"
    assert formatar_percentual(92.4) == "92,4%"
    assert formatar_percentual(0.924, ja_e_pct=False) == "92,4%"
    assert formatar_percentual("abc") == "—"


def test_buscar_coluna_cobre_acento_caixa_pontuacao_e_contencao() -> None:
    """As bases reais trazem ``Nº CONTRATO``, ``Base / Região`` e ``Técnico``."""
    df = pd.DataFrame({"Técnico": ["a"], "Nº CONTRATO": [1], "Base / Região": ["SPO"]})
    assert buscar_coluna(df, ["TECNICO"]) == "Técnico"
    assert buscar_coluna(df, ["contrato"]) == "Nº CONTRATO"
    assert buscar_coluna(df, ["base"]) == "Base / Região"
    assert buscar_coluna(df, ["inexistente"]) is None
    assert buscar_coluna(pd.DataFrame(), ["a"]) is None
    assert colunas_presentes(df, ["tecnico", "base", "x"]) == ["Técnico", "Base / Região"]


# ====================================================
# services.planilhas
# ====================================================


def test_ler_bytes_csv_detecta_encoding_e_separador() -> None:
    csv_ponto_virgula = "Técnico;Pontos\nJosé;1,5\nAna;2,5\n".encode("utf-8-sig")
    df = ler_bytes(csv_ponto_virgula, "producao.csv")
    assert list(df.columns) == ["Técnico", "Pontos"]
    assert len(df) == 2

    df_texto = ler_bytes(csv_ponto_virgula, "producao.csv", dtype=str)
    assert df_texto["Pontos"].tolist() == ["1,5", "2,5"]

    df_manter_texto = ler_bytes(csv_ponto_virgula, "producao.csv", dtype=str, manter_na=False)
    assert len(df_manter_texto) == 2


def test_ler_bytes_csv_latin1_e_arquivo_vazio() -> None:
    conteudo = "Base;Total\nSão Paulo;10\n".encode("latin-1")
    df = ler_bytes(conteudo, "bases.csv")
    assert df.loc[0, "Base"] == "São Paulo"

    with pytest.raises(ValueError, match="vazio"):
        ler_bytes(b"", "bases.csv")
    with pytest.raises(ValueError, match="não suportado"):
        ler_bytes(b"x", "bases.pdf")


def test_ler_bytes_xlsx_roundtrip() -> None:
    original = pd.DataFrame({"Técnico": ["Ana", "José"], "Pontos": [10, 20]})
    buffer = io.BytesIO()
    original.to_excel(buffer, index=False, sheet_name="Prod")
    lido = ler_bytes(buffer.getvalue(), "carga.xlsx")
    assert lido["Técnico"].tolist() == ["Ana", "José"]
    assert int(lido["Pontos"].sum()) == 30


def test_gerar_excel_e_csv_no_padrao_corporativo() -> None:
    df = pd.DataFrame({"Técnico": ["Ana"], "Pontos": [1.5]})

    xlsx = gerar_excel(df, aba="Produção Mensal")
    assert xlsx[:2] == b"PK"
    lido = pd.read_excel(io.BytesIO(xlsx), sheet_name="Produção Mensal")
    assert lido["Técnico"].tolist() == ["Ana"]

    # Nome de aba acima de 31 caracteres é truncado (limite do Excel).
    longo = gerar_excel(df, aba="X" * 40)
    assert pd.read_excel(io.BytesIO(longo)).columns.tolist() == ["Técnico", "Pontos"]

    csv_bytes = gerar_csv(df)
    texto = csv_bytes.decode("utf-8-sig")
    assert texto.splitlines()[0] == "Técnico;Pontos"
    assert texto.splitlines()[1] == "Ana;1,5"


def test_gerar_excel_sobrevive_a_coluna_vazia() -> None:
    """Coluna só com ``NaN`` não pode derrubar a exportação (regressão real)."""
    import numpy as np

    from services.planilhas import larguras_colunas

    df = pd.DataFrame({"Técnico": ["Ana", None], "Obs": [np.nan, np.nan]})
    assert larguras_colunas(df)[1] >= len("Obs") + 2
    assert gerar_excel(df)[:2] == b"PK"


def test_nome_com_carimbo_e_estavel() -> None:
    instante = datetime(2026, 10, 14, 18, 30)
    assert nome_com_carimbo("producao mensal", "xlsx", quando=instante) == (
        "producao_mensal_20261014_1830.xlsx"
    )
    assert nome_com_carimbo("Quebra/Geral", "csv", quando=instante).startswith("Quebra-Geral_")


# ====================================================
# services.hierarquia
# ====================================================


def test_normalizar_hierarquia_aplica_aliases_oficiais() -> None:
    bruto = pd.DataFrame(
        {
            " login ": [123.0, "456.0", None],
            "Nome do Técnico": ["ana souza", "JOSÉ LIMA", "x"],
            "Gestor": ["Monitor A", "Monitor B", "Monitor C"],
            "Região": ["spO", "Campinas", "SPO"],
        }
    )

    hierarquia = normalizar_hierarquia(bruto)

    assert list(hierarquia.columns) == list(COLUNAS_CANONICAS)
    assert hierarquia["LOGIN"].tolist() == ["123", "456"]
    assert hierarquia["TÉCNICO"].tolist() == ["Ana Souza", "José Lima"]  # acento preservado
    assert hierarquia["BASE"].tolist() == ["Spo", "Campinas"]


def test_normalizar_hierarquia_sem_login_devolve_vazia_com_colunas() -> None:
    assert normalizar_hierarquia(pd.DataFrame({"X": [1]})).empty
    assert list(hierarquia_vazia().columns) == list(COLUNAS_CANONICAS)
    assert normalizar_hierarquia(None).empty


def test_normalizar_hierarquia_remove_duplicados_pelo_ultimo() -> None:
    bruto = pd.DataFrame({"Login": ["1", "1"], "Técnico": ["Antigo", "Atual"]})
    hierarquia = normalizar_hierarquia(bruto)
    assert len(hierarquia) == 1
    assert hierarquia.loc[0, "TÉCNICO"] == "Atual"


# ====================================================
# services.dados_sessao
# ====================================================


def test_resumir_carga_conta_linhas_e_abas() -> None:
    dados = {
        "Prod": pd.DataFrame({"os": [1, 2, 3]}),
        "Gpon": pd.DataFrame(columns=["id"]),
    }
    resumo = resumir_carga(dados)
    assert (resumo.registros, resumo.tabelas, resumo.tabelas_com_dados) == (3, 2, 1)
    assert resumo.carregado
    assert not resumir_carga({}).carregado
    assert resumir_carga([{"os": 1}, {"os": 2}]).registros == 2


def test_concatenar_abas_respeita_ordem_oficial() -> None:
    dados = {
        "Gpon": pd.DataFrame({"fonte": ["gpon"]}),
        "Prod": pd.DataFrame({"fonte": ["prod"]}),
        "Outra": pd.DataFrame({"fonte": ["outra"]}),
    }
    assert concatenar_abas(dados)["fonte"].tolist() == ["prod", "gpon"]
    assert concatenar_abas(dados, abas=["Outra"])["fonte"].tolist() == ["outra"]
    assert concatenar_abas(pd.DataFrame({"a": [1]}))["a"].tolist() == [1]
    assert concatenar_abas(None).empty


def test_obter_base_le_da_sessao(monkeypatch) -> None:
    import services.dados_sessao as dados_sessao

    estado = {
        "dados_prod": {"Prod": pd.DataFrame({"os": [1, 2]}), "Gpon": pd.DataFrame()},
        "df_memoria": pd.DataFrame({"os": [9]}),
    }
    monkeypatch.setattr(dados_sessao, "_sessao", lambda: estado)

    assert obter_base()["os"].tolist() == [1, 2]
    assert obter_base("df_memoria")["os"].tolist() == [9]
    assert obter_base("ausente") is None

    estado["dados_prod"] = pd.DataFrame()
    assert obter_base() is None


class _Parada(Exception):
    """Substitui o ``StopException`` que o ``st.stop()`` real levanta."""


def _streamlit_falso(estado: dict[str, object]) -> tuple[SimpleNamespace, list[str]]:
    """``st`` mínimo para exercitar a guarda de entrada fora do runtime."""
    avisos: list[str] = []

    def _stop() -> None:
        raise _Parada

    falso = SimpleNamespace(
        session_state=estado,
        warning=avisos.append,
        stop=_stop,
        page_link=lambda *args, **kwargs: None,
    )
    return falso, avisos


def test_exigir_base_devolve_a_base_quando_ha_dados(monkeypatch) -> None:
    import services.dados_sessao as dados_sessao

    base = pd.DataFrame({"os": [1, 2]})
    estado = {"dados_prod": base}
    falso, avisos = _streamlit_falso(estado)
    monkeypatch.setitem(sys.modules, "streamlit", falso)
    monkeypatch.setattr(dados_sessao, "_sessao", lambda: estado)

    assert dados_sessao.exigir_base()["os"].tolist() == [1, 2]
    assert avisos == []


def test_exigir_base_avisa_e_para_a_pagina_sem_dados(monkeypatch) -> None:
    import components.componentes as componentes
    import services.dados_sessao as dados_sessao

    avisos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        componentes, "render_insight", lambda msg, tipo="info", **kw: avisos.append((msg, tipo))
    )
    estado: dict[str, object] = {"dados_prod": None}
    falso, _ = _streamlit_falso(estado)
    monkeypatch.setitem(sys.modules, "streamlit", falso)
    monkeypatch.setattr(dados_sessao, "_sessao", lambda: estado)

    with pytest.raises(_Parada):
        dados_sessao.exigir_base(pagina="Produção Mensal")

    assert len(avisos) == 1
    mensagem, tipo = avisos[0]
    assert tipo == "alerta"
    assert "Produção Mensal" in mensagem
    assert "Atualização de Dados" in mensagem


def test_exigir_base_oferece_atalho_fora_do_shell(monkeypatch) -> None:
    """Sem o shell de navegação a página mostra o link para a carga de dados."""
    import services.dados_sessao as dados_sessao

    links: list[str] = []
    estado: dict[str, object] = {"dados_prod": {}}
    falso, _ = _streamlit_falso(estado)
    falso.page_link = lambda pagina, **kwargs: links.append(pagina)
    monkeypatch.setitem(sys.modules, "streamlit", falso)
    monkeypatch.setattr(dados_sessao, "_sessao", lambda: estado)

    with pytest.raises(_Parada):
        dados_sessao.exigir_base()

    assert links == ["pages/envio_excel.py"]


# ====================================================
# components.dashboards
# ====================================================


def test_chips_de_contexto_vem_do_resumo_da_carga() -> None:
    instante = datetime(2026, 10, 14, 8, 5)
    resumo = ResumoCarga(registros=12480, tabelas=2, tabelas_com_dados=2, atualizado_em=instante)

    chips = chips_de_contexto(resumo=resumo, origem="Robô Local", periodo="01/10 a 14/10")

    assert chips["Atualizado em"] == "14/10/2026 08:05"
    assert chips["Registros"] == 12480
    assert chips["Abas"] == 2
    assert chips["Origem"] == "Robô Local"
    assert chips["Período"] == "01/10 a 14/10"


def test_chips_de_contexto_ignora_campos_vazios() -> None:
    assert chips_de_contexto() == {}
    assert chips_de_contexto(registros=0, origem="") == {}
    assert chips_de_contexto(extras={"Base": "SPO", "Vazio": ""}) == {"Base": "SPO"}


def test_versao_do_portal_vem_de_config() -> None:
    from config.settings import AMBIENTE_PORTAL, VERSAO_PORTAL

    assert versao_do_portal() == (VERSAO_PORTAL, AMBIENTE_PORTAL)


def test_gerar_excel_multiabas_cria_consolidado_e_abas_por_grupo() -> None:
    df = pd.DataFrame(
        {
            "Contrato": ["C1", "C2", "C3", "C4"],
            "Equipe": ["Alpha", "Alpha", "Beta", None],
            "Qtde": [1, 2, 3, 4],
        }
    )

    dados = gerar_excel_multiabas(df, coluna_grupo="Equipe")

    abas = pd.read_excel(io.BytesIO(dados), sheet_name=None)
    assert list(abas) == ["Consolidado_Geral", "Alpha", "Beta", "nan"]
    assert len(abas["Consolidado_Geral"]) == 4
    assert len(abas["Alpha"]) == 2
    assert list(abas["Beta"]["Contrato"]) == ["C3"]


def test_gerar_excel_multiabas_desambigua_nomes_de_aba_repetidos() -> None:
    df = pd.DataFrame(
        {
            "Equipe": ["A" * 40, "A" * 40 + "x", "curta"],
            "Qtde": [1, 2, 3],
        }
    )

    dados = gerar_excel_multiabas(df, coluna_grupo="Equipe", aba_geral="Geral")

    abas = pd.read_excel(io.BytesIO(dados), sheet_name=None)
    assert list(abas)[0] == "Geral"
    assert all(len(nome) <= 31 for nome in abas)
    assert len(set(abas)) == len(abas)


def test_gerar_excel_multiabas_respeita_limite_de_abas() -> None:
    df = pd.DataFrame({"Equipe": [f"E{i}" for i in range(10)], "Qtde": range(10)})

    dados = gerar_excel_multiabas(df, coluna_grupo="Equipe", max_abas=3)

    abas = pd.read_excel(io.BytesIO(dados), sheet_name=None)
    assert len(abas) == 4  # consolidado + 3 grupos
