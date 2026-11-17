"""Testes do motor da Prévia Diária e da página que o consome.

A prévia é o número que a diretoria lê no fim do dia; por isso as regras vivem
em ``services/previa_diaria.py`` (sem Streamlit) e aqui ficam cobertas:

* formatação e normalização (nomes de base, contratos e textos);
* classificação da quebra (instalação × serviços × retorno);
* consultivo por base/supervisor com hoje, acumulado e projeção;
* métricas de produtividade, ND, GPON, migração, retorno WO e PME;
* calendário (domingo não é dia útil), projeções e Rota Inicial;
* leitura do e-mail ``.msg`` de parados e de uploads reais em CSV;
* abertura da página em ``AppTest`` sem credencial de Google Sheets.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from services import previa_diaria as previa


# ====================================================
# 🔤 NORMALIZAÇÃO E FORMATAÇÃO
# ====================================================
def test_fmt_br_usa_padrao_brasileiro() -> None:
    assert previa.fmt_br(1234) == "1.234"
    assert previa.fmt_br(1234.567, 2) == "1.234,57"
    assert previa.fmt_br(0.4, 0) == "0"
    assert previa.fmt_br(float("nan")) == "0"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("ABC", "NET-ABCDM"),
        ("net-abcdm", "NET-ABCDM"),
        ("GRU", "NET-Guarulhos"),
        ("Guarulhos", "NET-Guarulhos"),
        ("Leste", "NET-LESTE"),
        ("desconhecida", "DESCONHECIDA"),
    ],
)
def test_normalizar_nome_base(entrada: str, esperado: str) -> None:
    assert previa.normalizar_nome_base(entrada) == esperado


def test_limpar_chave_remove_sufixo_de_float() -> None:
    assert previa.limpar_chave("12345.0") == "12345"
    assert previa.limpar_chave(" 987 ") == "987"
    assert previa.limpar_chave(None) == ""
    assert previa.limpar_chave(float("nan")) == ""


@pytest.mark.parametrize(
    ("descricao", "tipo_servico", "esperado"),
    [
        ("", "RETORNO DE CREDENCIADA", "RETORNO"),
        ("RETORNO", "QUALQUER", "RETORNO"),
        ("INSTALAÇÃO", "", "INSTALAÇÃO"),
        ("MUDANÇA DE PACOTE", "", "SERVIÇOS"),
        ("MANUTENÇÃO", "", "SERVIÇOS"),
        ("", "ADESAO - INSTALACAO DE ASSINATURA", "INSTALAÇÃO"),
        ("", "SERVICO DE CAMPO", "SERVIÇOS"),
        ("", "", ""),
    ],
)
def test_padrao_quebra_categoria(descricao: str, tipo_servico: str, esperado: str) -> None:
    assert previa.padrao_quebra_categoria(descricao, tipo_servico) == esperado


def test_filtrar_por_contrato_unico_descarta_chave_vazia() -> None:
    df = pd.DataFrame({"Contrato": ["1", "1.0", "2", "", None], "OS": [1, 2, 3, 4, 5]})
    unico = previa.filtrar_por_contrato_unico(df)
    assert unico["OS"].tolist() == [1, 3]


# ====================================================
# 🧭 CONSULTIVO
# ====================================================
def test_identificar_base_e_supervisor() -> None:
    assert previa.identificar_base_e_supervisor_consultivo("MAICON FARIA") == (
        "NET-ABCDM",
        "MAICON",
    )
    assert previa.identificar_base_e_supervisor_consultivo("francisco junior") == (
        "NET-LESTE",
        "FRANCISCO",
    )
    assert previa.identificar_base_e_supervisor_consultivo("", "Guarulhos") == (
        "NET-Guarulhos",
        "GERAL",
    )
    assert previa.identificar_base_e_supervisor_consultivo("FULANO", "OUTRA") == (
        "DESCARTADO",
        "DESCARTADO",
    )


def _df_consultivo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Supervisor": [
                "MAICON FARIA",
                "MAICON FARIA",
                "MAICON FARIA",
                "MAICON FARIA",
                "ALAN DIAS",
                "FULANO DE TAL",
            ],
            "Projeto": ["NET-ABCDM"] * 4 + ["NET-LESTE", "OUTRA"],
            "Contrato": ["100", "101", "102", "103", "200", "300"],
            "Qtd Produtos": [2, 1, 3, 4, 5, 9],
            "Data": [
                "09/11/2026",
                "09/11/2026",
                "09/11/2026",
                "10/11/2026",
                "10/11/2026",
                "10/11/2026",
            ],
        }
    )


def test_processar_consultivo_separa_hoje_acumulado_e_projecao() -> None:
    resultado = previa.processar_planilha_consultivo(_df_consultivo(), "10/11/2026")

    assert resultado["hoje_contratos"]["NET-ABCDM"] == 1
    assert resultado["hoje_produtos"]["NET-ABCDM"] == 4
    assert resultado["acum_contratos"]["NET-ABCDM"] == 4
    assert resultado["acum_produtos"]["NET-ABCDM"] == 10
    assert resultado["hoje_produtos"]["NET-LESTE"] == 5

    # Projeção = média do passado × dias úteis do mês, com piso no acumulado.
    uteis = resultado["total_dias_uteis_mes"]
    passados = resultado["dias_uteis_passados"]
    esperado = round(6 / passados * uteis)
    assert resultado["proj_produtos"]["NET-ABCDM"] == max(esperado, 10)
    assert resultado["dias_restantes"] >= 1

    historico = resultado["historico_diario"]["NET-ABCDM"]
    assert historico["09/11/2026"] == 6
    assert historico["10/11/2026"] == 4

    supervisor = resultado["supervisores"]["NET-ABCDM"]["MAICON"]
    assert supervisor["produtos_mes"] == 10
    assert supervisor["produtos_hoje"] == 4

    # Registro sem supervisor nem base válida não contamina nenhuma base.
    assert sum(resultado["acum_produtos"].values()) == 15


def test_processar_consultivo_aceita_planilha_vazia() -> None:
    resultado = previa.processar_planilha_consultivo(pd.DataFrame(), "10/11/2026")
    assert resultado["acum_produtos"] == {base: 0 for base in previa.BASES_PREVIA}
    assert resultado["supervisores"] == {base: {} for base in previa.BASES_PREVIA}


# ====================================================
# 🏷️ CLASSIFICAÇÃO DA ANIEL
# ====================================================
def test_classificar_aniel_aplica_baixas_quebras_atividades_e_pontos() -> None:
    df = pd.DataFrame(
        {
            "Tipo de OS": ["", "", ""],
            "ST1": ["FECHADO", "", "FECHADO"],
            "ST2": ["Executado no sistema Netsms", "", "Cancelado no sistema Netsms"],
            "ST3": ["001 - INSTALACAO", "", ""],
            "Tipo de Serviço": [
                "INSTALACAO DE CABO GPON",
                "MANUTENCAO DE REDE",
                "SERVICO GENERICO",
            ],
            "Observação 1": ["cliente fibra", "", ""],
            "Pontos Prev.": ["0", "0", "0"],
            "Supervisor": [" maicon ", "ALAN", "ADRIANO"],
        }
    )
    baixas = {"001 - INSTALACAO": "PRODUTIVA"}
    pontos = {"INSTALACAO DE CABO GPON": 3.0}
    descricoes = {"INSTALACAO DE CABO GPON": "INSTALAÇÃO"}

    classificado = previa.classificar_aniel(df, baixas, pontos, descricoes)

    # Linha 1: baixa + "executado" → produtiva; GPON com cabo → migração.
    assert classificado.loc[0, "Tipo de OS"] == "PRODUTIVA"
    assert classificado.loc[0, "QUEBRAS"] == "INSTALAÇÃO"
    assert classificado.loc[0, "ATIVIDADES"] == "MIGRAÇÃO"
    assert classificado.loc[0, "Pontos Prev."] == 3.0
    assert classificado.loc[0, "Supervisor"] == "MAICON"

    # Linha 2: sem baixa e sem ST1 → saiu do TOA; manutenção é SERVIÇOS.
    assert classificado.loc[1, "Tipo de OS"] == "SAIU DO TOA"
    assert classificado.loc[1, "QUEBRAS"] == "SERVIÇOS"
    assert classificado.loc[1, "ATIVIDADES"] == "HFC"

    # Linha 3: em aberto + cancelamento no Netsms → cancelada.
    assert classificado.loc[2, "Tipo de OS"] == "CANCELADO"
    assert classificado.loc[2, "CANCELADAS"] == "CANCELADO"

    assert classificado["Tipo de Serviço"].tolist() == [
        "INSTALACAO DE CABO GPON",
        "MANUTENCAO DE REDE",
        "SERVICO GENERICO",
    ]


def test_classificar_aniel_aceita_colunas_lidas_como_float() -> None:
    """Excel com coluna só de vazios chega float64; a classificação não pode quebrar."""
    df = pd.DataFrame(
        {
            "Tipo de OS": [float("nan"), float("nan")],
            "Tipo de Serviço": ["INSTALACAO", None],
            "ST1": ["FECHADO", "FECHADO"],
            "ST2": ["Executado no sistema Netsms", ""],
            "ST3": ["", ""],
            "Pontos Prev.": [float("nan"), float("nan")],
        }
    )
    assert df["Tipo de OS"].dtype == "float64"

    classificado = previa.classificar_aniel(df)

    assert classificado["Tipo de OS"].tolist() == ["PRODUTIVA", "EM ABERTO"]
    assert classificado["Pontos Prev."].tolist() == [0.0, 0.0]


# ====================================================
# 📊 MÉTRICAS
# ====================================================
def _df_metricas() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Contrato": ["1", "1", "2", "3", "4", "5", "6"],
            "Tipo de OS": [
                "PRODUTIVA",
                "IMPRODUTIVA",
                "PRODUTIVA",
                "EM ABERTO",
                "SAIU DO TOA",
                "PRODUTIVA",
                "PRODUTIVA",
            ],
            "Tipo de Serviço": [
                "ADESAO - INSTALACAO DE ASSINATURA",
                "ADESAO - INSTALACAO DE ASSINATURA",
                "MUDANCA DE PACOTE",
                "INSTALACAO DE CABO GPON",
                "MUDANCA DE PACOTE",
                "RETORNO DE CREDENCIADA",
                "RETORNO DE EQUIPAMENTO",
            ],
            "QUEBRAS": [
                "INSTALAÇÃO",
                "INSTALAÇÃO",
                "SERVIÇOS",
                "INSTALAÇÃO",
                "SERVIÇOS",
                "RETORNO",
                "RETORNO",
            ],
            "ATIVIDADES": ["GPON", "GPON", "MIGRAÇÃO", "GPON", "HFC", "HFC", "HFC"],
            "PME": ["", "", "", "PME", "", "", ""],
            "CANCELADAS": ["", "", "", "", "", "CANCELADO", ""],
            "Pontos Prev.": [10.0, 10.0, 5.0, 8.0, 4.0, 4.0, 4.0],
        }
    )


def test_metricas_completas_aplicam_regras_da_previa() -> None:
    metricas = previa.calcular_metricas_completas(_df_metricas(), 10)

    # Retorno de credenciada sai da contagem de O.S.
    assert metricas["tot_os"] == 6
    assert metricas["produtivo"] == 3
    assert metricas["quebra_geral"] == 1
    assert metricas["os_aberta"] == 1
    assert metricas["os_canc"] == 0
    assert metricas["saiu_toa"] == 1

    # Eficiência = 1 - improdutivas/(improdutivas + produtivas).
    assert metricas["efic"] == 75.0
    # Projeção do dia = produtivas + abertas × eficiência.
    assert metricas["proj_dia"] == 4
    assert metricas["media_os"] == 0.4
    assert metricas["pontos"] == 24

    assert (metricas["q_ins"], metricas["_raw_tot_ins"]) == (50.0, 2)
    assert metricas["q_serv"] == 0.0
    assert metricas["q_nd"] == 50.0
    assert metricas["tot_nd"] == 1

    assert metricas["tot_gpon"] == 3
    assert metricas["q_gpon"] == 50.0
    assert metricas["tot_mig"] == 1
    assert metricas["q_mig"] == 0.0

    # Retorno WO é por contrato único: contratos 5 e 6.
    assert metricas["retorno_wo"] == 2
    # PME é por contrato único e restrito ao contrato 3.
    assert metricas["tot_pme"] == 1
    assert metricas["q_pme"] == 0.0
    assert metricas["canc_pme"] == 0


def test_metricas_vazias_nao_levantam() -> None:
    metricas = previa.calcular_metricas_completas(pd.DataFrame(), 0)
    assert metricas["tot_os"] == 0
    assert metricas["efic"] == 0.0
    assert metricas["_raw_tot_ins"] == 0


# ====================================================
# 📅 CALENDÁRIO, PROJEÇÕES E ROTA INICIAL
# ====================================================
def test_calendario_ignora_domingos() -> None:
    dias_uteis, dias_trabalhados, data_formatada = previa.calcular_calendario_automatico(
        datetime(2026, 11, 10)
    )
    assert data_formatada == "10/11/2026"
    assert dias_uteis == 25  # novembro/2026 tem 30 dias e 5 domingos
    assert dias_trabalhados == 8  # até o dia 10, descontando 01 e 08 (domingos)


def test_projetar_os_usa_media_diaria_do_historico() -> None:
    historico = pd.DataFrame(
        {
            "Data": ["03/11/2026", "04/11/2026", "03/11/2026"],
            "Base": ["NET-ABCDM", "NET-ABCDM", "NET-LESTE"],
            "OS_Executadas": [10, 20, 999],
            "OS_Inicial": [0, 0, 0],
        }
    )
    projecao, media, dias = previa.projetar_os(
        "NET-ABCDM", historico, dias_uteis_mes=20, os_hoje=30, data_ref_str="05/11/2026"
    )
    assert (projecao, media, dias) == (400, 20.0, 3)


def test_projetar_consultivo_prefere_a_regra_da_tv() -> None:
    projecao, media, dias = previa.projetar_consultivo(
        "NET-LESTE",
        pd.DataFrame(),
        dias_uteis_mes=25,
        consultivo_hoje=10,
        data_ref_str="10/11/2026",
        projecao_tv=500,
        dias_passados=7,
    )
    assert projecao == 500
    assert media == 20.0
    assert dias == 7


def test_buscar_os_inicial_prefere_o_historico_e_cai_no_fallback() -> None:
    historico = pd.DataFrame(
        {
            "Data": ["10/11/2026"],
            "Base": ["NET-Guarulhos"],
            "OS_Inicial": [700],
        }
    )
    assert previa.buscar_os_inicial("GRU", "10/11/2026", historico) == 700
    assert previa.buscar_os_inicial("LESTE", "10/11/2026", historico) == 497


# ====================================================
# 📥 E-MAIL DE PARADOS E UPLOADS
# ====================================================
class _UploadFalso:
    """Upload mínimo com a interface usada por ``ler_planilha``."""

    def __init__(self, nome: str, conteudo: bytes) -> None:
        self.name = nome
        self._conteudo = conteudo

    def getvalue(self) -> bytes:
        return self._conteudo


def test_processar_msg_conta_parados_por_supervisor() -> None:
    corpo = (
        "Bom dia,\nData: 10/11/2026\n"
        "12345 - JOAO DA SILVA    MAICON FARIA    FALTA\n"
        "23456 - MARIA SOUZA      ALAN DIAS       ATESTADO\n"
    )
    data_ext, parados, tecnicos = previa.processar_arquivo_msg(corpo.encode("utf-16le"))

    assert data_ext == "10/11/2026"
    assert parados["MAICON"] == 1
    assert parados["ALAN"] == 1
    assert sum(parados.values()) == 2
    assert any("JOAO DA SILVA" in item for item in tecnicos)


def test_ler_planilha_csv_com_ponto_e_virgula() -> None:
    conteudo = "Contrato;Status\n123;OK\n".encode("latin1")
    df = previa.ler_planilha(_UploadFalso("toa.csv", conteudo))

    assert df.columns.tolist() == ["Contrato", "Status"]
    assert df.iloc[0]["Contrato"] == 123


def test_ler_planilha_prefere_aba_com_o_nome_pedido() -> None:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Resumo", index=False)
        pd.DataFrame({"Contrato": [42]}).to_excel(
            writer, sheet_name="CONSULTIVO", index=False
        )

    df = previa.ler_planilha(
        _UploadFalso("consultivo.xlsx", buffer.getvalue()), prefer_sheet="CONSULTIVO"
    )

    assert df.columns.tolist() == ["Contrato"]


def test_ler_planilha_vazia_levanta_erro() -> None:
    with pytest.raises(ValueError):
        previa.ler_planilha(_UploadFalso("vazio.csv", b""))


# ====================================================
# 🔁 FLUXO COMPLETO DO PASSO 1
# ====================================================
def _roteiro_processamento() -> None:
    """Executa o upload/cruzamento dentro do runtime do Streamlit."""
    import io

    import pandas as pd
    import streamlit as st

    from pages import previa_totale as pagina

    def excel_bytes(abas: dict[str, pd.DataFrame]) -> bytes:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for nome, df in abas.items():
                df.to_excel(writer, sheet_name=nome, index=False)
        return buffer.getvalue()

    class UploadFalso:
        def __init__(self, nome: str, conteudo: bytes) -> None:
            self.name = nome
            self._conteudo = conteudo

        def getvalue(self) -> bytes:
            return self._conteudo

    aniel = pd.DataFrame(
        {
            "Projeto": ["NET-Guarulhos", "NET-LESTE"],
            "Supervisor": ["ADRIANO", "ALAN"],
            "Tipo de OS": [None, None],
            "Contrato Cliente": ["200", "300"],
            "Data": ["10/11/2026", "10/11/2026"],
            "Tipo de Serviço": ["MANUTENCAO DE REDE", "ADESAO - INSTALACAO DE ASSINATURA"],
            "Observação 1": [None, None],
            "Pontos Prev.": [None, None],
        }
    )
    toa = pd.DataFrame(
        {
            "Data": ["10/11/2026", "10/11/2026"],
            "Contrato": ["200", "300"],
            "Status da Atividade": ["FECHADO", "FECHADO"],
            "Motivo de Fechamento Externo": ["Executado no sistema Netsms", ""],
            "Cidade": ["GUARULHOS", "SAO PAULO"],
            "Categorias da Capacidade": ["", "PME"],
            "Cód de Baixa 1": ["", ""],
        }
    )

    pagina._processar_uploads(
        UploadFalso("aniel.xlsx", excel_bytes({"ANIEL": aniel})),
        [UploadFalso("toa.xlsx", excel_bytes({"TOA": toa}))],
        None,
    )
    assert len(st.session_state["previa_df_valido"]) == 2


def test_processar_uploads_cruza_aniel_e_toa() -> None:
    """Fluxo real do Passo 1: ANIEL + TOA viram base válida por supervisor."""
    app = AppTest.from_function(_roteiro_processamento, default_timeout=120).run()

    assert not app.exception
    assert app.session_state["previa_processado"] is True
    assert app.session_state["previa_data_ref"] == "10/11/2026"
    assert app.session_state["previa_supervisores"]["NET-Guarulhos"] == ["ADRIANO"]
    assert app.session_state["previa_supervisores"]["NET-LESTE"] == ["ALAN"]

    df_valido = app.session_state["previa_df_valido"]
    assert df_valido["Tipo de OS"].tolist() == ["PRODUTIVA", "EM ABERTO"]
    assert df_valido["QUEBRAS"].tolist() == ["SERVIÇOS", "INSTALAÇÃO"]
    assert len(df_valido) == 2


def _roteiro_sincronizacao() -> None:
    """Roda a gravação da prévia com as abas em memória (sem Google Sheets)."""
    import pandas as pd
    import streamlit as st

    from pages import previa_totale as pagina

    df = pd.DataFrame(
        {
            "Projeto": ["NET-ABCDM", "NET-Guarulhos", "NET-LESTE"],
            "Supervisor": ["MAICON", "ADRIANO", "ALAN"],
            "Tipo de OS": ["PRODUTIVA", "PRODUTIVA", "EM ABERTO"],
            "Tipo de Serviço": [
                "ADESAO - INSTALACAO DE ASSINATURA",
                "MANUTENCAO DE REDE",
                "SERVICO GENERICO",
            ],
            "QUEBRAS": ["INSTALAÇÃO", "SERVIÇOS", "SERVIÇOS"],
            "ATIVIDADES": ["GPON", "HFC", "HFC"],
            "PME": ["", "", ""],
            "CANCELADAS": ["", "", ""],
            "Pontos Prev.": [10.0, 5.0, 4.0],
            "Contrato": ["1", "2", "3"],
        }
    )
    st.session_state["previa_df_valido"] = df
    st.session_state["previa_df_full"] = df
    st.session_state["previa_supervisores"] = {
        "NET-ABCDM": ["MAICON"],
        "NET-Guarulhos": ["ADRIANO"],
        "NET-LESTE": ["ALAN"],
    }
    st.session_state["previa_m_NET-ABCDM_MAICON"] = 12
    st.session_state["previa_data_ref"] = "10/11/2026"

    pagina._ler_aba_remota = lambda aba: pd.DataFrame()  # type: ignore[assignment]
    escritas: dict[str, pd.DataFrame] = {}
    pagina._gravar_aba = lambda aba, dados: escritas.__setitem__(aba, dados.copy())  # type: ignore[assignment]
    pagina._sincronizar_planilha(df, "10/11/2026", 25)
    st.session_state["_escritas"] = escritas


def test_sincronizacao_grava_historico_equipe_e_previa() -> None:
    """A sincronização cria as linhas certas em cada aba operacional."""
    app = AppTest.from_function(_roteiro_sincronizacao, default_timeout=120).run()

    assert not app.exception
    escritas = app.session_state["_escritas"]

    historico = escritas["Historico_OS"]
    assert historico["Base"].tolist() == ["NET-ABCDM", "NET-Guarulhos"]
    assert historico["OS_Executadas"].tolist() == [1, 1]
    assert historico["OS_Inicial"].tolist() == [529, 611]

    equipe = escritas["Config_Equipe"]
    assert equipe.loc[equipe["Supervisor"] == "MAICON", "Montados"].iloc[0] == 12

    previas = escritas["Previas_Diarias"]
    assert previas["Base"].tolist() == ["ABCDM", "Guarulhos", "Leste"]
    assert previas.loc[previas["Base"] == "ABCDM", "Total O.S."].iloc[0] == 1
    assert previas.loc[previas["Base"] == "Leste", "O.S. Aberta"].iloc[0] == 1

    # Sem arquivo de Consultivo no dia, o histórico dessa aba não é sobrescrito.
    assert "Historico_Consultivo" not in escritas

    historico_equipe = escritas["Historico_Equipe"]
    assert set(historico_equipe["Supervisor"]) == {"MAICON", "ADRIANO", "ALAN"}


# ====================================================
# 🧭 NAVEGAÇÃO E PÁGINA
# ====================================================
def test_pagina_esta_no_mapa_de_navegacao() -> None:
    from config.navegacao import pagina_por_arquivo

    pagina = pagina_por_arquivo("previa_totale.py")
    assert pagina is not None
    assert pagina.titulo == "Prévia Diária"
    assert pagina.grupo == "Central de Performance"


def _app_da_previa(passo: str = "1. Upload de arquivos") -> AppTest:
    """AppTest da página já com uma base processada em sessão."""
    raiz = Path(__file__).resolve().parents[1]
    df = pd.DataFrame(
        {
            "Projeto": ["NET-ABCDM", "NET-Guarulhos", "NET-LESTE"],
            "Supervisor": ["MAICON", "ADRIANO", "ALAN"],
            "Tipo de OS": ["PRODUTIVA", "PRODUTIVA", "EM ABERTO"],
            "Tipo de Serviço": [
                "ADESAO - INSTALACAO DE ASSINATURA",
                "INSTALACAO DE CABO GPON",
                "MANUTENCAO",
            ],
            "QUEBRAS": ["INSTALAÇÃO", "INSTALAÇÃO", "SERVIÇOS"],
            "ATIVIDADES": ["GPON", "GPON", "HFC"],
            "PME": ["", "", ""],
            "CANCELADAS": ["", "", ""],
            "Pontos Prev.": [10.0, 8.0, 4.0],
            "Contrato": ["1", "2", "3"],
        }
    )
    app = AppTest.from_file(raiz / "pages" / "previa_totale.py", default_timeout=60)
    app.session_state["previa_df_valido"] = df
    app.session_state["previa_df_full"] = df
    app.session_state["previa_supervisores"] = {
        "NET-ABCDM": ["MAICON"],
        "NET-Guarulhos": ["ADRIANO"],
        "NET-LESTE": ["ALAN"],
    }
    app.session_state["previa_data_ref"] = "10/11/2026"
    app.session_state["previa_passo"] = passo
    return app


def test_pagina_abre_sem_credencial_de_sheets() -> None:
    """Sem `secrets.toml` a página abre e oferece o upload (sem traceback)."""
    app = _app_da_previa()
    app.run()

    assert not app.exception
    assert app.radio[0].options == [
        "1. Upload de arquivos",
        "2. Dados operacionais",
        "3. Prévia executiva",
    ]


def test_previa_executiva_renderiza_tabela_e_detalhamento() -> None:
    app = _app_da_previa(passo="3. Prévia executiva")
    app.run()

    assert not app.exception
    tabelas = [m.value for m in app.markdown if "TOTAL INSTALAÇÃO" in str(m.value)]
    assert len(tabelas) == 1
    tabela = str(tabelas[0])
    assert "ABCDM" in tabela and "Guarulhos" in tabela and "Leste" in tabela
    assert "tr-total" in tabela
    assert len(app.expander) == 3


def test_sincronizacao_sem_credencial_avisa_e_abre_a_previa() -> None:
    """Falha de gravação não engole o aviso nem trava o acesso à prévia."""
    app = _app_da_previa(passo="2. Dados operacionais")
    app.run()

    botao = next(b for b in app.button if "Sincronizar" in b.label)
    botao.click()
    app.run()

    assert not app.exception
    assert app.radio[0].value == "3. Prévia executiva"
    assert any("Não foi possível gravar no Google Sheets" in w.value for w in app.warning)


def _roteiro_falha_leitura_sync() -> None:
    import pandas as pd
    import streamlit as st
    from pages import previa_totale as pagina

    escritas = []
    pagina._montar_linhas = lambda *args: ([], {})
    pagina._gravar_aba = lambda aba, dados: escritas.append(aba)

    def falhar(aba):
        raise RuntimeError("Leitura negada")

    pagina._ler_aba_remota = falhar
    try:
        pagina._sincronizar_planilha(pd.DataFrame(), "10/11/2026", 25)
    except RuntimeError as exc:
        st.session_state["_erro_leitura"] = str(exc)
    st.session_state["_escritas_bloqueadas"] = escritas


def test_falha_leitura_bloqueia_todas_as_gravacoes() -> None:
    app = AppTest.from_function(_roteiro_falha_leitura_sync, default_timeout=120).run()
    assert not app.exception
    assert app.session_state["_erro_leitura"] == "Leitura negada"
    assert app.session_state["_escritas_bloqueadas"] == []
