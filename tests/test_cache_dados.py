"""Testes da camada de desempenho de dados (``services.cache_dados``).

Cobrem o item "resolver a lentidão": download condicional (ETag/304), cache em
disco (parquet) fora do repositório, leitura rápida de CSV, otimização de
dtypes, memoização e o painel de diagnóstico. Nada aqui toca a internet: o HTTP
é exercitado contra um servidor local em thread.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd
import pytest
import requests
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import services.cache_dados as c  # noqa: E402

CSV_PONTO_VIRGULA = "EQUIPE;OS;DATA\nAlpha;10;01/09/2026\nBeta;20;02/09/2026\n".encode("utf-8")
ETAG = '"totale-v1"'
ULTIMA_MODIFICACAO = "Mon, 13 Oct 2026 06:00:00 GMT"


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cada teste usa um diretório de cache próprio (e fora do repositório)."""
    diretorio = tmp_path / "cache"
    monkeypatch.setenv(c.VARIAVEL_DIRETORIO_CACHE, str(diretorio))
    yield diretorio
    c.limpar_cache()


# ====================================================
# SERVIDOR HTTP LOCAL (sem internet)
# ====================================================
class _Servidor(BaseHTTPRequestHandler):
    """Serve CSV com ETag/Last-Modified e conta quantas vezes foi acessado."""

    requisicoes: dict[str, int] = {}

    def log_message(self, *args: object) -> None:  # silencia o log do http.server
        return None

    def do_GET(self) -> None:  # noqa: N802 - nome exigido pela stdlib
        _Servidor.requisicoes[self.path] = _Servidor.requisicoes.get(self.path, 0) + 1
        if self.path.startswith("/ausente"):
            self.send_response(404)
            self.end_headers()
            return
        if self.path.startswith("/lento"):
            time.sleep(0.25)
        if self.headers.get("If-None-Match") == ETAG:
            self.send_response(304)
            self.end_headers()
            return
        if self.headers.get("If-Modified-Since") == ULTIMA_MODIFICACAO:
            self.send_response(304)
            self.end_headers()
            return
        corpo = CSV_PONTO_VIRGULA
        self.send_response(200)
        self.send_header("ETag", ETAG)
        self.send_header("Last-Modified", ULTIMA_MODIFICACAO)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)


@pytest.fixture(scope="module")
def servidor() -> str:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Servidor)
    linha = threading.Thread(target=httpd.serve_forever, daemon=True)
    linha.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


# ====================================================
# CONTRATO DO MÓDULO
# ====================================================
def test_constantes_e_api_publica() -> None:
    assert c.VERSAO_CAMADA
    assert c.TTL_PADRAO == 300
    assert c.VARIAVEL_DIRETORIO_CACHE == "TOTALE_CACHE_DIR"
    assert c.TIMEOUT_PADRAO == (10, 60)
    for nome in c.__all__:
        assert hasattr(c, nome), nome


def test_resultado_carga_e_imutavel_e_tem_resumo() -> None:
    df = pd.DataFrame({"A": [1, 2, 3]})
    resultado = c.ResultadoCarga(
        df=df, origem="produtor", duracao_ms=12.4, linhas=3, colunas=1, chave="k"
    )

    assert resultado.ok is True
    assert "3 linhas" in resultado.resumo_texto()
    assert "produtor" in resultado.resumo_texto()
    with pytest.raises(Exception):  # dataclass congelada
        resultado.origem = "cache"  # type: ignore[misc]

    vazio = c.resultado_vazio("k")
    assert vazio.ok is False
    assert vazio.origem == "vazio"
    assert vazio.df.empty


# ====================================================
# CACHE EM DISCO
# ====================================================
def test_diretorio_cache_vem_da_variavel_de_ambiente(cache_isolado: Path) -> None:
    diretorio = c.diretorio_cache()

    assert diretorio == cache_isolado
    assert diretorio.exists()


def test_diretorio_padrao_fica_fora_do_repositorio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(c.VARIAVEL_DIRETORIO_CACHE, raising=False)

    diretorio = c.diretorio_cache(criar=False)

    assert not str(diretorio).startswith(str(RAIZ)), "cache não pode morar no repositório"
    assert ".streamlit_cache" not in str(diretorio)


def test_caminhos_cache_sanitizam_a_chave() -> None:
    parquet, meta = c.caminhos_cache("fonte/produção 2026:set")

    assert parquet.suffix == ".parquet"
    assert meta.suffix == ".json"
    assert "/" not in parquet.name
    assert ":" not in parquet.name
    assert " " not in parquet.name
    assert parquet.parent == meta.parent


def test_gravar_e_ler_cache_preserva_dados_e_metadados() -> None:
    df = pd.DataFrame({"EQUIPE": ["Alpha", "Beta"], "OS": [10, 20]})

    assert c.gravar_cache_dataframe("round", df, meta_extra={"etag": ETAG}) is True

    lido, meta = c.ler_cache_dataframe("round")
    assert lido is not None
    pd.testing.assert_frame_equal(lido.reset_index(drop=True), df)
    assert meta["chave"] == "round"
    assert meta["etag"] == ETAG
    assert meta["versao_camada"] == c.VERSAO_CAMADA
    assert meta["linhas"] == 2


def test_ler_cache_inexistente_devolve_none() -> None:
    df, meta = c.ler_cache_dataframe("chave_que_nao_existe")

    assert df is None
    assert meta == {} or not meta


def test_idade_e_estatisticas_do_cache() -> None:
    assert c.idade_cache_segundos("nada") is None

    c.gravar_cache_dataframe("idade", pd.DataFrame({"A": [1]}))
    idade = c.idade_cache_segundos("idade")
    assert idade is not None and 0 <= idade < 60

    estatisticas = c.estatisticas_cache()
    assert estatisticas["itens"] >= 1
    assert estatisticas["tamanho_bytes"] > 0
    assert "KB" in estatisticas["tamanho_legivel"] or "B" in estatisticas["tamanho_legivel"]
    assert estatisticas["diretorio"]


def test_formatar_bytes_em_pt_br() -> None:
    assert c.formatar_bytes(0) == "0 B"
    assert c.formatar_bytes(900) == "900 B"
    assert c.formatar_bytes(1536) == "1,5 KB"
    assert c.formatar_bytes(5_242_880) == "5,0 MB"
    assert c.formatar_bytes(3_221_225_472) == "3,0 GB"


def test_limpar_cache_por_chave_e_total() -> None:
    c.gravar_cache_dataframe("a", pd.DataFrame({"A": [1]}))
    c.gravar_cache_dataframe("b", pd.DataFrame({"B": [2]}))

    assert c.limpar_cache("a") == 2  # parquet + sidecar
    assert c.ler_cache_dataframe("a")[0] is None
    assert c.ler_cache_dataframe("b")[0] is not None

    assert c.limpar_cache() >= 2
    assert c.estatisticas_cache()["itens"] == 0


def test_sanitizar_para_parquet_remove_colunas_duplicadas() -> None:
    df = pd.DataFrame([[1, 2, 3]], columns=["OS Total", "OS Total", "A/B"])

    saida = c.sanitizar_para_parquet(df)

    assert len(set(saida.columns)) == len(saida.columns)
    assert saida.shape[1] == 3
    assert c.gravar_cache_dataframe("sanitizado", saida) is True


# ====================================================
# LEITURA RÁPIDA DE CSV
# ====================================================
def test_detectar_separador() -> None:
    assert c.detectar_separador("a;b;c\n1;2;3\n") == ";"
    assert c.detectar_separador("a,b,c\n1,2,3\n") == ","
    assert c.detectar_separador("a\tb\n1\t2\n") == "\t"
    assert c.detectar_separador("a|b\n1|2\n") == "|"
    assert c.detectar_separador("coluna unica\nvalor\n") in {",", ";"}


def test_detectar_encoding() -> None:
    assert c.detectar_encoding("olá;mundo\n1;2\n".encode("utf-8")) in ("utf-8-sig", "utf-8")
    assert c.detectar_encoding(b"\xef\xbb\xbfEQUIPE;OS\n") == "utf-8-sig"
    assert c.detectar_encoding("SÃO PAULO;OS\n".encode("cp1252")) == "cp1252"


def test_ler_csv_rapido_mantem_tudo_como_texto_por_padrao() -> None:
    df = c.ler_csv_rapido(CSV_PONTO_VIRGULA)

    assert list(df.columns) == ["EQUIPE", "OS", "DATA"]
    assert len(df) == 2
    assert all(pd.api.types.is_string_dtype(t) for t in df.dtypes)


def test_ler_csv_rapido_aceita_separador_e_colunas_explicitas() -> None:
    df = c.ler_csv_rapido(CSV_PONTO_VIRGULA, sep=";", usecols=["EQUIPE", "OS"])

    assert list(df.columns) == ["EQUIPE", "OS"]
    assert df["OS"].iloc[0] == "10"


def test_ler_csv_rapido_explica_entrada_invalida() -> None:
    """Conteúdo vazio/ilegível levanta ``ValueError`` (virar resultado de erro)."""
    with pytest.raises(ValueError, match="vazio"):
        c.ler_csv_rapido(b"")
    with pytest.raises(ValueError):
        c.ler_csv_rapido(b"\x00\x01\x02")


def test_ler_csv_grande_e_rapido() -> None:
    linhas = 120_000
    corpo = ("EQUIPE;OS;SLA\n" + "Alpha;123;98.5\n" * linhas).encode("utf-8")

    inicio = time.perf_counter()
    df = c.ler_csv_rapido(corpo)
    duracao = time.perf_counter() - inicio

    assert len(df) == linhas
    assert duracao < 6.0, f"leitura de {linhas} linhas levou {duracao:.2f}s"


# ====================================================
# OTIMIZAÇÃO E MEMOIZAÇÃO
# ====================================================
@pytest.fixture
def base_texto() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "EQUIPE": ["Alpha", "Beta"] * 500,
            "OS": ["1248"] * 500 + ["900"] * 500,
            "SLA": ["98.5", "70.25"] * 500,
            "MISTO": ["a1", "2"] * 500,
        }
    )


def test_otimizar_dtypes_faz_downcast_numerico() -> None:
    df = pd.DataFrame({"inteiro": [1, 2, 3], "flutuante": [1.5, 2.5, 3.5]})

    saida = c.otimizar_dtypes(df)

    assert saida["inteiro"].dtype.itemsize < df["inteiro"].dtype.itemsize
    assert saida["flutuante"].dtype.itemsize < df["flutuante"].dtype.itemsize


def test_otimizar_dtypes_converte_texto_numerico_sem_perdas(base_texto: pd.DataFrame) -> None:
    saida = c.otimizar_dtypes(base_texto, numericas=True)

    assert pd.api.types.is_numeric_dtype(saida["OS"])
    assert pd.api.types.is_numeric_dtype(saida["SLA"])
    assert int(saida["OS"].sum()) == 1248 * 500 + 900 * 500
    # Coluna mista (texto + número) nunca é corrompida.
    assert not pd.api.types.is_numeric_dtype(saida["MISTO"])


def test_otimizar_dtypes_categoricas_reduz_memoria(base_texto: pd.DataFrame) -> None:
    antes = c.memoria_dataframe(base_texto)
    saida = c.otimizar_dtypes(base_texto, categoricas=True, numericas=True)
    depois = c.memoria_dataframe(saida)

    assert depois < antes
    assert (antes - depois) / antes > 0.3, f"ganho de apenas {(antes - depois) / antes:.0%}"
    assert isinstance(saida["EQUIPE"].dtype, pd.CategoricalDtype)


def test_otimizar_dtypes_respeita_limite_e_protecoes() -> None:
    df = pd.DataFrame({"TURNO": [f"T{i % 5}" for i in range(100)], "OS": ["10"] * 100})

    limitada = c.otimizar_dtypes(df, categoricas=True, limite_categoricas=3)
    ampla = c.otimizar_dtypes(df, categoricas=True, limite_categoricas=10)
    protegida = c.otimizar_dtypes(df, numericas=True, colunas_protegidas=("OS",))

    assert not isinstance(limitada["TURNO"].dtype, pd.CategoricalDtype)
    assert isinstance(ampla["TURNO"].dtype, pd.CategoricalDtype)
    assert pd.api.types.is_string_dtype(protegida["OS"])


def test_otimizar_dtypes_nao_modifica_o_original(base_texto: pd.DataFrame) -> None:
    dtypes_antes = dict(base_texto.dtypes.astype(str))

    c.otimizar_dtypes(base_texto, numericas=True, categoricas=True)

    assert dict(base_texto.dtypes.astype(str)) == dtypes_antes


def test_otimizar_dtypes_aceita_vazio() -> None:
    vazio = pd.DataFrame()

    assert c.otimizar_dtypes(vazio).empty
    assert c.otimizar_dtypes(vazio, numericas=True, categoricas=True).empty


def test_memoria_dataframe_cresce_com_os_dados() -> None:
    pequeno = pd.DataFrame({"A": range(10)})
    grande = pd.DataFrame({"A": range(10_000)})

    assert c.memoria_dataframe(pequeno) > 0
    assert c.memoria_dataframe(grande) > c.memoria_dataframe(pequeno)
    assert c.memoria_dataframe(grande, indice=False) <= c.memoria_dataframe(grande)


def test_chave_conteudo_e_estavel_e_sensivel() -> None:
    serie = pd.Series(["a", "b", "c"])

    assert c.chave_conteudo(serie) == c.chave_conteudo(serie.copy())
    assert c.chave_conteudo(serie) != c.chave_conteudo(pd.Series(["a", "b", "d"]))
    assert c.chave_conteudo(serie) != c.chave_conteudo(pd.Series(["a", "b"]))
    assert c.chave_conteudo(pd.Series(dtype="object")) == "vazio"


def test_datas_normalizadas_converte_formato_brasileiro() -> None:
    serie = pd.Series(["01/09/2026", "15/10/2026", None, "inválida"])

    saida = c.datas_normalizadas(serie)

    assert pd.api.types.is_datetime64_any_dtype(saida)
    assert saida.iloc[0] == pd.Timestamp("2026-09-01")
    assert saida.iloc[1] == pd.Timestamp("2026-10-15")
    assert pd.isna(saida.iloc[2]) and pd.isna(saida.iloc[3])


def test_datas_normalizadas_e_memoizada() -> None:
    serie = pd.Series(["01/09/2026"] * 5_000)

    primeira = c.datas_normalizadas(serie)
    inicio = time.perf_counter()
    segunda = c.datas_normalizadas(serie)
    repetida = time.perf_counter() - inicio

    pd.testing.assert_series_equal(primeira, segunda, check_names=False)
    assert repetida < 0.5, "repetição deveria vir da memoização"


def test_agregar_com_cache_executa_o_produtor_uma_vez() -> None:
    df = pd.DataFrame({"EQUIPE": ["A", "B", "A"], "OS": [10, 20, 30]})
    chamadas = {"n": 0}

    def produtor(base: pd.DataFrame) -> pd.DataFrame:
        chamadas["n"] += 1
        return base.groupby("EQUIPE", as_index=False)["OS"].sum()

    primeira = c.agregar_com_cache(df, "agg_teste", produtor)
    segunda = c.agregar_com_cache(df, "agg_teste", produtor)

    assert chamadas["n"] == 1
    pd.testing.assert_frame_equal(primeira, segunda)
    assert int(primeira["OS"].sum()) == 60


# ====================================================
# HTTP: SESSÃO POOLED E DOWNLOAD CONDICIONAL
# ====================================================
def test_sessao_http_e_reutilizada_e_com_retry() -> None:
    sessao = c.sessao_http()

    assert sessao is c.sessao_http(), "sessão deveria vir de pool"
    assert isinstance(sessao, requests.Session)
    assert sessao.adapters
    assert any(getattr(a.max_retries, "total", 0) > 0 for a in sessao.adapters.values())


def test_cabecalhos_condicionais_seguem_a_rfc() -> None:
    assert c.cabecalhos_condicionais(ETAG, ULTIMA_MODIFICACAO) == {
        "If-None-Match": ETAG,
        "If-Modified-Since": ULTIMA_MODIFICACAO,
    }
    assert c.cabecalhos_condicionais(None, None) == {}


def test_baixar_condicional_devolve_etag_verbatim(servidor: str) -> None:
    status, corpo, cabecalhos = c.baixar_condicional(f"{servidor}/dados.csv")

    assert status == 200
    assert corpo == CSV_PONTO_VIRGULA
    # O ETag é opaco (RFC 9110): as aspas precisam voltar intactas na revalidação.
    assert cabecalhos["etag"] == ETAG
    assert cabecalhos["last_modified"] == ULTIMA_MODIFICACAO


def test_baixar_condicional_revalida_com_304(servidor: str) -> None:
    status, corpo, _ = c.baixar_condicional(f"{servidor}/dados.csv", etag=ETAG)

    assert status == 304
    assert corpo == b""


def test_baixar_condicional_revalida_com_last_modified(servidor: str) -> None:
    status, corpo, _ = c.baixar_condicional(
        f"{servidor}/dados.csv", last_modified=ULTIMA_MODIFICACAO
    )

    assert status == 304
    assert corpo == b""


def test_baixar_condicional_levanta_em_erro_http(servidor: str) -> None:
    with pytest.raises(requests.HTTPError):
        c.baixar_condicional(f"{servidor}/ausente.csv")


# ====================================================
# carregar_com_cache
# ====================================================
def test_carregar_com_produtor_grava_cache() -> None:
    resultado = c.carregar_com_cache(
        "prod", produtor=lambda: c.ler_csv_rapido(CSV_PONTO_VIRGULA), ttl=300
    )

    assert resultado.ok is True
    assert resultado.origem == "produtor"
    assert resultado.linhas == 2
    assert resultado.colunas == 3
    assert resultado.tamanho_bytes == 0  # nada trafegou pela rede
    assert resultado.duracao_ms >= 0
    assert c.ler_cache_dataframe("prod")[0] is not None  # ficou em disco


def test_carregar_por_url_registra_bytes_e_etag(servidor: str) -> None:
    resultado = c.carregar_com_cache(
        "rede", url=f"{servidor}/dados.csv", leitor=c.ler_csv_rapido, ttl=300
    )

    assert resultado.ok is True
    assert resultado.origem == "rede"
    assert resultado.linhas == 2
    assert resultado.tamanho_bytes == len(CSV_PONTO_VIRGULA)
    assert resultado.etag == ETAG
    assert resultado.last_modified == ULTIMA_MODIFICACAO


def test_segunda_carga_vem_do_cache_sem_reexecutar() -> None:
    chamadas = {"n": 0}

    def produtor() -> pd.DataFrame:
        chamadas["n"] += 1
        return c.ler_csv_rapido(CSV_PONTO_VIRGULA)

    primeira = c.carregar_com_cache("cache_hit", produtor=produtor, ttl=300)
    segunda = c.carregar_com_cache("cache_hit", produtor=produtor, ttl=300)

    assert chamadas["n"] == 1
    assert primeira.origem == "produtor"
    assert segunda.origem == "cache"
    assert segunda.idade_segundos is not None
    pd.testing.assert_frame_equal(
        primeira.df.reset_index(drop=True), segunda.df.reset_index(drop=True)
    )


def test_forcar_refaz_a_carga() -> None:
    chamadas = {"n": 0}

    def produtor() -> pd.DataFrame:
        chamadas["n"] += 1
        return pd.DataFrame({"A": [chamadas["n"]]})

    c.carregar_com_cache("forcar", produtor=produtor, ttl=300)
    forçada = c.carregar_com_cache("forcar", produtor=produtor, ttl=300, forcar=True)

    assert chamadas["n"] == 2
    assert forçada.origem == "produtor"
    assert int(forçada.df["A"].iloc[0]) == 2


def test_ttl_vencido_revalida_por_url(servidor: str) -> None:
    url = f"{servidor}/dados.csv"
    primeira = c.carregar_com_cache("ttl", url=url, ttl=300, leitor=c.ler_csv_rapido)
    assert primeira.origem == "rede"

    expirada = c.carregar_com_cache("ttl", url=url, ttl=0, leitor=c.ler_csv_rapido)

    # Com ETag preservado o servidor responde 304: dado do disco, sem reparse.
    assert expirada.origem == "cache_validado"
    assert expirada.ok is True
    assert expirada.linhas == 2
    assert expirada.etag == ETAG


def test_erro_do_produtor_vira_resultado_sem_excecao() -> None:
    def produtor() -> pd.DataFrame:
        raise RuntimeError("falha simulada")

    resultado = c.carregar_com_cache("erro", produtor=produtor)

    assert resultado.ok is False
    assert resultado.origem == "erro"
    assert "falha simulada" in (resultado.erro or "")
    assert resultado.df.empty
    assert "erro" in resultado.resumo_texto()


def test_resultado_vazio_quando_nao_ha_linhas() -> None:
    resultado = c.carregar_com_cache("vazio", produtor=pd.DataFrame)

    assert resultado.ok is False
    assert resultado.origem == "vazio"
    assert resultado.linhas == 0


def test_leitor_personalizado_e_usado_no_parse(servidor: str) -> None:
    vistos = {"n": 0}

    def leitor(conteudo: bytes) -> pd.DataFrame:
        vistos["n"] += 1
        return c.ler_csv_rapido(conteudo, sep=";")

    resultado = c.carregar_com_cache("leitor", url=f"{servidor}/dados.csv", leitor=leitor)

    assert vistos["n"] == 1
    assert resultado.linhas == 2


def test_otimizar_aplica_dtypes_na_carga(servidor: str) -> None:
    resultado = c.carregar_com_cache(
        "otimizada",
        url=f"{servidor}/dados.csv",
        leitor=c.ler_csv_rapido,
        otimizar=True,
    )

    assert resultado.ok is True
    # Otimização padrão é conservadora: texto continua texto (páginas usam .str).
    assert all(pd.api.types.is_string_dtype(t) for t in resultado.df.dtypes)


def test_carregar_planilha_gsheets_monta_url_de_exportacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capturado: dict[str, str] = {}

    def baixar_fake(url: str, **kwargs: object) -> tuple[int, bytes, dict[str, str]]:
        capturado["url"] = url
        return 200, CSV_PONTO_VIRGULA, {"etag": ETAG, "last_modified": ""}

    monkeypatch.setattr(c, "baixar_condicional", baixar_fake)

    resultado = c.carregar_planilha_gsheets("ID_DA_PLANILHA", "Aba1")

    assert resultado.ok is True
    assert resultado.linhas == 2
    assert "ID_DA_PLANILHA" in capturado["url"]
    assert "Aba1" in capturado["url"]
    assert capturado["url"].startswith("https://docs.google.com/spreadsheets/d/")


# ====================================================
# carregar_varias (paralelo)
# ====================================================
def test_carregar_varias_executa_fontes_em_paralelo() -> None:
    def produtor_lento(indice: int):
        def _interno() -> pd.DataFrame:
            time.sleep(0.25)
            return pd.DataFrame({"FONTE": [indice]})

        return _interno

    fontes = [c.EspecificacaoFonte(chave=f"f{i}", produtor=produtor_lento(i)) for i in range(4)]

    inicio = time.perf_counter()
    resultados = c.carregar_varias(fontes, max_workers=4)
    duracao = time.perf_counter() - inicio

    assert set(resultados) == {"f0", "f1", "f2", "f3"}
    assert all(r.ok for r in resultados.values())
    # Sequencial seriam ≥1,0s; em paralelo deve caber em ~0,25–0,8s.
    assert duracao < 0.9, f"carga paralela levou {duracao:.2f}s (esperado <0,9s)"


def test_carregar_varias_isola_falha_de_uma_fonte() -> None:
    def falha() -> pd.DataFrame:
        raise ValueError("fonte indisponível")

    fontes = {
        "ok": {"produtor": lambda: pd.DataFrame({"A": [1]})},
        "ruim": {"produtor": falha},
    }

    resultados = c.carregar_varias(fontes)

    assert resultados["ok"].ok is True
    assert resultados["ruim"].ok is False
    assert resultados["ruim"].origem == "erro"
    assert "fonte indisponível" in (resultados["ruim"].erro or "")


def test_carregar_varias_por_url_usa_o_servidor_local(servidor: str) -> None:
    fontes = [
        c.EspecificacaoFonte(chave="csv", url=f"{servidor}/dados.csv"),
        c.EspecificacaoFonte(chave="ausente", url=f"{servidor}/ausente.csv"),
    ]

    resultados = c.carregar_varias(fontes, max_workers=2)

    assert resultados["csv"].ok is True
    assert resultados["csv"].linhas == 2
    assert resultados["ausente"].ok is False


# ====================================================
# MEDIÇÃO E PAINEL DE DIAGNÓSTICO
# ====================================================
def test_temporizar_mede_e_registra() -> None:
    with c.temporizar("etapa_teste", registrar=False) as medidor:
        time.sleep(0.02)

    assert medidor["rotulo"] == "etapa_teste"
    assert medidor["ms"] >= 15


def test_temporizar_registra_no_resumo_da_sessao() -> None:
    app = AppTest.from_string(
        """
        import time
        from services.cache_dados import temporizar, resumo_desempenho
        import streamlit as st
        with temporizar("carga_producao"):
            time.sleep(0.01)
        with temporizar("parse"):
            time.sleep(0.01)
        st.session_state["resumo"] = resumo_desempenho()
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception), [str(e.value) for e in app.exception]
    resumo = app.session_state["resumo"]
    assert len(resumo["tempos"]) >= 2
    assert resumo["total_ms"] >= 15
    assert resumo["mais_lento"]["rotulo"] in {"carga_producao", "parse"}
    assert any(item["rotulo"] == "carga_producao" for item in resumo["tempos"])
    assert "itens" in resumo["cache"]


def test_painel_desempenho_renderiza_cartoes_avancados() -> None:
    app = AppTest.from_string(
        """
        import pandas as pd
        from services.cache_dados import (
            EspecificacaoFonte, ResultadoCarga, carregar_varias,
            render_painel_desempenho,
        )

        resultados = carregar_varias(
            {
                "producao": {"produtor": lambda: pd.DataFrame({"A": [1, 2]})},
                "consultivo": {"produtor": lambda: pd.DataFrame({"B": [3]})},
            }
        )
        render_painel_desempenho(
            resultados=resultados,
            fontes=[
                {"Fonte": "Produção", "Download (ms)": 12.0, "Linhas": 2, "Situação": "ok"},
            ],
            expandido=True,
        )
        """,
        default_timeout=90,
    ).run()

    assert not list(app.exception), [str(e.value) for e in app.exception]
    assert len(app.get("metric")) == 0, "não pode usar st.metric nativo"

    assert len(app.expander) == 1
    assert "Desempenho da carga de dados" in str(app.expander[0].label)

    html = "\n".join(str(getattr(b, "value", "")) for b in app.get("html"))
    assert html.count("kpi-avancado kpi-avancado--compacto") >= 4  # 4 cartões de diagnóstico
    assert "Tempo medido" in html and "Itens em cache" in html
    # fontes + resultados viram tabelas nativas
    assert len(app.dataframe) >= 2


def test_painel_desempenho_sem_dados_nao_quebra() -> None:
    app = AppTest.from_string(
        """
        from services.cache_dados import render_painel_desempenho
        render_painel_desempenho()
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception), [str(e.value) for e in app.exception]
    assert len(app.get("metric")) == 0


# ====================================================
# GUARDA: PÁGINAS NÃO INVALIDAM CACHE GLOBALMENTE
# ====================================================
def test_paginas_nao_invalidam_cache_global() -> None:
    """``st.cache_data.clear()`` derrubaria o cache de todas as páginas."""
    infratores: list[str] = []
    for arquivo in sorted((RAIZ / "pages").rglob("*.py")):
        codigo = arquivo.read_text(encoding="utf-8")
        for padrao in ("st.cache_data.clear()", "st.cache_resource.clear()"):
            if padrao in codigo:
                infratores.append(f"{arquivo.name}:{padrao}")

    assert not infratores, infratores


def test_cache_em_disco_nao_entra_no_repositorio() -> None:
    """Nenhum artefato de runtime pode aparecer na árvore versionada."""
    proibidos = list((RAIZ).rglob("*.parquet"))
    permitidos = {".streamlit_cache/geo_sp_2022.parquet"}

    suspeitos = [
        str(p.relative_to(RAIZ))
        for p in proibidos
        if str(p.relative_to(RAIZ)) not in permitidos and "totale_painel_cache" not in str(p)
    ]
    assert not suspeitos, f"parquet fora do cache permitido: {suspeitos}"
    assert not os.environ.get(c.VARIAVEL_DIRETORIO_CACHE, "").startswith(str(RAIZ))
