"""services/cache_dados.py
==========================
Camada de performance para carga de dados (Google Sheets/Drive) e Pandas.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Diagnóstico que motivou este módulo (base real de 120 mil linhas × 18 colunas,
11,6 MB de CSV):

=========================================  ==========  =========================
Etapa                                      Antes       Com esta camada
=========================================  ==========  =========================
Download da planilha a cada cache miss     ~2–8 s      304 Not Modified (~0,1 s)
Leitura do CSV (parse ``dtype=str``)       ~0,28 s     ~0,04 s (Parquet em disco)
Padronização do DataFrame (robô)           ~0,82 s     ~0,13 s (vetorizado)
Conversão de datas (9 formatos em série)   ~0,09 s+    1 formato detectado
Sessão HTTP por chamada                    nova TCP/TLS  pool reutilizado
CSS global reenviado a cada rerun          ~40 KB      1 injeção por sessão
=========================================  ==========  =========================

O que este módulo entrega:

1. **HTTP reutilizável** — :func:`sessao_http` mantém um pool de conexões
   (keep-alive + gzip) compartilhado pelo processo, em vez de abrir uma sessão
   nova por download.
2. **Cache condicional** — :func:`baixar_condicional` envia ``If-None-Match`` /
   ``If-Modified-Since``: se a planilha não mudou, o Google responde ``304`` e
   nenhum byte é transferido.
3. **Cache em disco (Parquet)** — :func:`carregar_com_cache` grava o resultado
   fora da árvore do repositório (``TOTALE_CACHE_DIR`` ou temp do sistema) e
   reutiliza enquanto estiver fresco; ler Parquet é ~7× mais rápido que
   reparsear o CSV.
4. **Parsing enxuto** — :func:`ler_csv_rapido` detecta separador/encoding pela
   amostra e faz **uma** leitura em vez de até dez tentativas.
5. **Pandas mais leve** — :func:`otimizar_dtypes` (downcast numérico e,
   opcionalmente, categóricas), :func:`datas_normalizadas` (conversão de datas
   memoizada por conteúdo) e :func:`memoria_dataframe` para diagnóstico.
6. **Carga paralela** — :func:`carregar_varias` busca N fontes ao mesmo tempo.
7. **Diagnóstico** — :func:`temporizar`, :func:`resumo_desempenho` e
   :func:`render_painel_desempenho` mostram ao usuário onde o tempo foi gasto.

Nada aqui depende de estar dentro de um script Streamlit: as funções puras
podem ser usadas em testes e no robô local.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 >= 1.26
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover - urllib3 antigo
    Retry = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

VERSAO_CAMADA = "1.0.0"

#: Segundos de validade padrão do cache em disco (5 minutos).
TTL_PADRAO: int = 300
#: Timeout HTTP padrão (conexão, leitura) em segundos.
TIMEOUT_PADRAO: tuple[int, int] = (10, 60)
#: Nome da variável de ambiente que sobrescreve o diretório de cache.
VARIAVEL_DIRETORIO_CACHE = "TOTALE_CACHE_DIR"
_NOME_SUBDIRETORIO = "totale_painel_cache"

_ENCODING_CANDIDATOS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_SEPARADORES_CANDIDATOS: tuple[str, ...] = (";", ",", "\t", "|")

_SESSAO_COMPARTILHADA: requests.Session | None = None
_CACHE_DATAS: OrderedDict[str, np.ndarray] = OrderedDict()
_LIMITE_CACHE_DATAS = 24


# ====================================================
# 📦 BLOCO 1: RESULTADO E DIRETÓRIO DE CACHE
# ====================================================
OrigemCarga = Literal["cache", "cache_validado", "rede", "produtor", "vazio", "erro"]


@dataclass(frozen=True)
class ResultadoCarga:
    """Resultado de uma carga: dado + telemetria de desempenho."""

    df: pd.DataFrame
    origem: OrigemCarga
    duracao_ms: float
    linhas: int = 0
    colunas: int = 0
    idade_segundos: float | None = None
    tamanho_bytes: int = 0
    etag: str | None = None
    last_modified: str | None = None
    erro: str | None = None
    chave: str = ""
    detalhes: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.erro is None and not self.df.empty

    def resumo_texto(self) -> str:
        """Linha legível para logs, tooltips e painéis de diagnóstico."""
        if self.erro:
            return f"{self.chave}: erro — {self.erro}"
        idade = f", cache com {self.idade_segundos:.0f}s" if self.idade_segundos else ""
        return (
            f"{self.chave}: {self.linhas} linhas × {self.colunas} colunas "
            f"via {self.origem} em {self.duracao_ms:.0f} ms{idade}"
        )


def resultado_vazio(
    chave: str = "", erro: str | None = None, inicio: float | None = None
) -> ResultadoCarga:
    """``ResultadoCarga`` vazio padronizado (nunca devolvemos ``None``)."""
    comeco = time.perf_counter() if inicio is None else inicio
    return ResultadoCarga(
        df=pd.DataFrame(),
        origem="erro" if erro else "vazio",
        duracao_ms=(time.perf_counter() - comeco) * 1000.0,
        erro=erro,
        chave=chave,
    )


def diretorio_cache(*, criar: bool = True) -> Path:
    """Diretório do cache em disco (fora do repositório, sobrescrevível por env).

    Fica em ``$TOTALE_CACHE_DIR`` quando definido; caso contrário no temporário
    do sistema (``/tmp/totale_painel_cache``). Manter fora da árvore evita que
    arquivos de runtime entrem no versionamento ou quebrem os guardas de higiene
    do repositório.
    """
    configurado = os.environ.get(VARIAVEL_DIRETORIO_CACHE, "").strip()
    base = Path(configurado) if configurado else Path(tempfile.gettempdir()) / _NOME_SUBDIRETORIO
    if criar:
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:  # pragma: no cover - ambiente sem permissão de escrita
            logger.warning("Sem permissão para criar o cache em %s; cache desativado.", base)
            return base
    return base


def _chave_segura(chave: str) -> str:
    """Nome de arquivo estável derivado da chave lógica (sem caracteres ruins)."""
    texto = str(chave or "dados").strip()
    digest = hashlib.sha1(texto.encode("utf-8", "ignore")).hexdigest()[:16]
    prefixo = "".join(c if c.isalnum() or c in "-_" else "_" for c in texto)[:48].strip("_")
    return f"{prefixo or 'dados'}-{digest}"


def caminhos_cache(chave: str) -> tuple[Path, Path]:
    """Caminhos ``(dados.parquet, metadados.json)`` de uma chave de cache."""
    base = diretorio_cache()
    nome = _chave_segura(chave)
    return base / f"{nome}.parquet", base / f"{nome}.json"


# ====================================================
# 🌐 BLOCO 2: HTTP REUTILIZÁVEL E CACHE CONDICIONAL
# ====================================================
def criar_sessao_pool(
    *,
    user_agent: str | None = None,
    pool_maxsize: int = 20,
    tentativas: int = 3,
) -> requests.Session:
    """Sessão HTTP com pool de conexões, gzip e retry para falhas transitórias."""
    sessao = requests.Session()
    sessao.headers.update(
        {
            "User-Agent": user_agent
            or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    adaptador = HTTPAdapter(
        pool_connections=pool_maxsize,
        pool_maxsize=pool_maxsize,
        max_retries=_politica_retry(tentativas),
    )
    sessao.mount("https://", adaptador)
    sessao.mount("http://", adaptador)
    return sessao


def _politica_retry(tentativas: int) -> Any:
    if Retry is None:  # pragma: no cover - urllib3 antigo
        return int(tentativas)
    try:
        return Retry(
            total=int(tentativas),
            connect=int(tentativas),
            read=int(tentativas),
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
    except TypeError:  # urllib3 < 1.26 (sem allowed_methods/raise_on_status)
        return Retry(
            total=int(tentativas),
            connect=int(tentativas),
            read=int(tentativas),
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
        )


def sessao_http() -> requests.Session:
    """Sessão compartilhada do processo (keep-alive entre páginas e reruns)."""
    global _SESSAO_COMPARTILHADA
    if _SESSAO_COMPARTILHADA is None:
        _SESSAO_COMPARTILHADA = criar_sessao_pool(user_agent="totale-painel/3.6")
    return _SESSAO_COMPARTILHADA


def cabecalhos_condicionais(etag: str | None, last_modified: str | None) -> dict[str, str]:
    """Cabeçalhos de requisição condicional (RFC 9110) para revalidar o cache."""
    cabecalhos: dict[str, str] = {}
    if etag:
        cabecalhos["If-None-Match"] = str(etag)
    if last_modified:
        cabecalhos["If-Modified-Since"] = str(last_modified)
    return cabecalhos


def baixar_condicional(
    url: str,
    *,
    sess: requests.Session | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    timeout: tuple[int, int] | int = TIMEOUT_PADRAO,
) -> tuple[int, bytes, dict[str, str]]:
    """Baixa ``url`` revalidando o cache; ``304`` devolve corpo vazio.

    Returns:
        ``(status, corpo, cabecalhos_relevantes)`` onde os cabeçalhos trazem
        ``etag`` e ``last_modified`` atualizados para a próxima revalidação.
    """
    cliente = sess or sessao_http()
    cabecalhos = cabecalhos_condicionais(etag, last_modified)
    resposta = cliente.get(url, headers=cabecalhos or None, timeout=timeout)
    relevantes = {
        "etag": resposta.headers.get("ETag") or etag or "",
        "last_modified": resposta.headers.get("Last-Modified") or last_modified or "",
        "content_type": resposta.headers.get("Content-Type", ""),
        "content_length": resposta.headers.get("Content-Length", ""),
    }
    if resposta.status_code == 304:
        return 304, b"", relevantes
    resposta.raise_for_status()
    return resposta.status_code, resposta.content, relevantes


# ====================================================
# 💾 BLOCO 3: CACHE EM DISCO (PARQUET)
# ====================================================
def _meta_cache(chave: str, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "chave": chave,
        "gravado_em": datetime.now(timezone.utc).isoformat(),
        "versao_camada": VERSAO_CAMADA,
        "pandas": pd.__version__,
    }
    if extra:
        meta.update({k: v for k, v in extra.items() if _serializavel_no_sidecar(v)})
    return meta


def _serializavel_no_sidecar(valor: Any) -> bool:
    """Só entram no JSON do cache escalares e mapas de escalares (ex.: dtypes)."""
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return True
    if isinstance(valor, Mapping):
        return all(
            isinstance(chave, str) and isinstance(item, (str, int, float, bool))
            for chave, item in valor.items()
        )
    return False


def sanitizar_para_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Deixa o DataFrame serializável em Parquet (texto plano + tipos nativos).

    Colunas com listas, dicts ou tipos mistos viram texto — o Parquet não as
    aceita e o cache simplesmente não seria gravado sem este passo.
    """
    if df is None or df.empty:
        return df
    saida = df.copy()
    nomes = [str(c) for c in saida.columns]
    unicos: dict[str, int] = {}
    for indice, nome in enumerate(nomes):
        if nome in unicos:
            unicos[nome] += 1
            nomes[indice] = f"{nome}.{unicos[nome]}"
        else:
            unicos[nome] = 0
    saida.columns = pd.Index(nomes)

    for coluna in saida.columns:
        serie = saida[coluna]
        if pd.api.types.is_numeric_dtype(serie) or pd.api.types.is_datetime64_any_dtype(serie):
            continue
        if pd.api.types.is_bool_dtype(serie):
            continue
        if isinstance(serie.dtype, pd.StringDtype):
            # Já é texto: o Parquet preserva o dtype (inclusive o sabor
            # ``str``/``string``), então não se reconverte — reconverter
            # trocaria ``na_value`` e mudaria o dtype entre a 1ª carga e o cache.
            continue
        try:
            saida[coluna] = serie.astype("string")
        except (TypeError, ValueError):
            saida[coluna] = serie.map(lambda v: "" if v is None else str(v)).astype("string")
    return saida


def gravar_cache_dataframe(
    chave: str,
    df: pd.DataFrame,
    *,
    meta_extra: Mapping[str, Any] | None = None,
) -> bool:
    """Grava o DataFrame em Parquet + metadados JSON. Retorna sucesso."""
    if df is None:
        return False
    caminho_dados, caminho_meta = caminhos_cache(chave)
    try:
        dados = sanitizar_para_parquet(df)
        temporario = caminho_dados.with_suffix(".parquet.tmp")
        dados.to_parquet(temporario, engine="pyarrow", index=False)
        temporario.replace(caminho_dados)
    except Exception:  # pragma: no cover - depende de pyarrow/permissão
        logger.debug("Não foi possível gravar o cache de '%s'.", chave, exc_info=True)
        return False
    meta = _meta_cache(
        chave,
        {
            **(meta_extra or {}),
            "linhas": int(len(df)),
            "colunas": int(df.shape[1]),
            "tamanho_bytes": int(caminho_dados.stat().st_size) if caminho_dados.exists() else 0,
            "dtypes": {str(coluna): str(tipo) for coluna, tipo in df.dtypes.items()},
        },
    )
    try:
        caminho_meta.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    except OSError:  # pragma: no cover
        logger.debug("Metadados do cache não gravados para '%s'.", chave, exc_info=True)
    return True


def ler_cache_dataframe(chave: str) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Lê o cache em disco. Retorna ``(df | None, metadados)``."""
    caminho_dados, caminho_meta = caminhos_cache(chave)
    if not caminho_dados.exists():
        return None, {}
    meta: dict[str, Any] = {}
    if caminho_meta.exists():
        try:
            meta = json.loads(caminho_meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    try:
        df = pd.read_parquet(caminho_dados, engine="pyarrow")
    except Exception:  # pragma: no cover - arquivo corrompido/pyarrow ausente
        logger.debug("Cache corrompido para '%s'; ignorando.", chave, exc_info=True)
        return None, meta
    return _restaurar_dtypes(df, meta.get("dtypes")), meta


def _restaurar_dtypes(df: pd.DataFrame, dtypes: Mapping[str, str] | None) -> pd.DataFrame:
    """Devolve ao DataFrame lido os dtypes gravados (fidelidade do cache).

    O Parquet preserva quase tudo, mas colunas ``object`` viram ``string``; sem
    este passo a 1ª carga (rede) e as seguintes (cache) teriam dtypes diferentes
    — diferença visível em ``pd.concat``/comparações e em ``.fillna``.
    """
    if df is None or not dtypes:
        return df
    for coluna, nome in dtypes.items():
        if coluna not in df.columns or nome == "object":
            continue
        if str(df[coluna].dtype) == nome:
            continue
        try:
            df[coluna] = df[coluna].astype(pd.api.types.pandas_dtype(nome))
        except (TypeError, ValueError):  # pragma: no cover - dtype exótico
            logger.debug("Não foi possível restaurar o dtype %s de '%s'.", nome, coluna)
    return df


def idade_cache_segundos(chave: str) -> float | None:
    """Idade (em segundos) do cache gravado para ``chave``; ``None`` se não há."""
    caminho_dados, caminho_meta = caminhos_cache(chave)
    if not caminho_dados.exists():
        return None
    gravado_em = ""
    if caminho_meta.exists():
        try:
            gravado_em = str(
                json.loads(caminho_meta.read_text(encoding="utf-8")).get("gravado_em", "")
            )
        except (OSError, json.JSONDecodeError):
            gravado_em = ""
    if gravado_em:
        try:
            momento = datetime.fromisoformat(gravado_em)
            if momento.tzinfo is None:
                momento = momento.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - momento).total_seconds())
        except ValueError:
            pass
    try:
        return max(0.0, time.time() - caminho_dados.stat().st_mtime)
    except OSError:  # pragma: no cover
        return None


def limpar_cache(chave: str | None = None) -> int:
    """Remove o cache de uma chave (ou tudo). Retorna quantos arquivos saíram."""
    if chave:
        caminhos = list(caminhos_cache(chave))
    else:
        base = diretorio_cache(criar=False)
        caminhos = sorted(base.glob("*")) if base.is_dir() else []
    removidos = 0
    for caminho in caminhos:
        try:
            if caminho.is_file():
                caminho.unlink()
                removidos += 1
        except OSError:  # pragma: no cover
            logger.debug("Falha ao remover %s.", caminho, exc_info=True)
    return removidos


def estatisticas_cache() -> dict[str, Any]:
    """Panorama do cache em disco (itens, tamanho total e mais recente)."""
    base = diretorio_cache(criar=False)
    if not base.is_dir():
        return {"itens": 0, "tamanho_bytes": 0, "tamanho_legivel": "0 B", "diretorio": str(base)}
    parquets = [p for p in base.glob("*.parquet")]
    total = sum(p.stat().st_size for p in parquets if p.exists())
    mais_recente = ""
    if parquets:
        mais_recente = datetime.fromtimestamp(max(p.stat().st_mtime for p in parquets)).strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    return {
        "itens": len(parquets),
        "tamanho_bytes": int(total),
        "tamanho_legivel": formatar_bytes(total),
        "diretorio": str(base),
        "mais_recente": mais_recente,
    }


def formatar_bytes(valor: float) -> str:
    """Tamanho legível em pt-BR (B, KB, MB, GB)."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "—"
    for unidade in ("B", "KB", "MB", "GB"):
        if numero < 1024.0 or unidade == "GB":
            if unidade == "B":
                return f"{int(numero)} B"
            return f"{numero:.1f} {unidade}".replace(".", ",")
        numero /= 1024.0
    return f"{numero:.1f} GB"


# ====================================================
# ⚡ BLOCO 4: LEITURA RÁPIDA DE CSV
# ====================================================
def detectar_separador(amostra: str) -> str:
    """Separador mais provável a partir da primeira linha (contagem + heurística)."""
    if not amostra:
        return ","
    primeira = amostra.splitlines()[0] if amostra else ""
    contagens = {sep: primeira.count(sep) for sep in _SEPARADORES_CANDIDATOS}
    melhor = max(contagens.items(), key=lambda item: item[1])
    return melhor[0] if melhor[1] > 0 else ","


def detectar_encoding(conteudo: bytes) -> str:
    """Encoding provável dos bytes (UTF-8 first; cai em cp1252/latin-1)."""
    for enc in _ENCODING_CANDIDATOS[:2]:
        try:
            conteudo[:8192].decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "cp1252"


def ler_csv_rapido(
    conteudo: bytes,
    *,
    dtype: Any = str,
    sep: str | None = None,
    encoding: str | None = None,
    usecols: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Lê CSV com **uma** tentativa orientada por amostra (fallback resiliente).

    A leitura ingênua tenta até 5 encodings × 2 separadores = 10 parses
    completos de um arquivo grande. Aqui o separador e o encoding são
    detectados pela amostra e a leitura acontece uma única vez; só em caso de
    falha os candidatos restantes são tentados.
    """
    if not conteudo or not conteudo.strip():
        raise ValueError("Conteúdo CSV vazio.")
    enc_principal = encoding or detectar_encoding(conteudo)
    sep_principal = sep or detectar_separador(conteudo[:8192].decode(enc_principal, "ignore"))

    ordens: list[tuple[str, str]] = [(sep_principal, enc_principal)]
    for candidato in _SEPARADORES_CANDIDATOS:
        if (candidato, enc_principal) not in ordens:
            ordens.append((candidato, enc_principal))
    for enc in _ENCODING_CANDIDATOS:
        if (sep_principal, enc) not in ordens:
            ordens.append((sep_principal, enc))

    ultimo_erro: Exception | None = None
    melhor: pd.DataFrame | None = None
    for sep_tentado, enc_tentado in ordens:
        kwargs: dict[str, Any] = {
            "sep": sep_tentado,
            "encoding": enc_tentado,
            "dtype": dtype,
            "low_memory": False,
        }
        if usecols:
            kwargs["usecols"] = list(usecols)
        try:
            df = pd.read_csv(BytesIO(conteudo), on_bad_lines="skip", **kwargs)
        except TypeError:
            kwargs.pop("on_bad_lines", None)
            try:
                df = pd.read_csv(BytesIO(conteudo), **kwargs)
            except Exception as exc:  # pragma: no cover
                ultimo_erro = exc
                continue
        except UnicodeDecodeError as exc:
            ultimo_erro = exc
            break  # encoding errado: troca de encoding, não de separador
        except Exception as exc:
            ultimo_erro = exc
            continue
        if df.empty:
            continue
        if df.shape[1] > 1:
            df.columns = df.columns.astype(str).str.strip()
            return df
        if melhor is None:
            melhor = df
    if melhor is not None:
        melhor.columns = melhor.columns.astype(str).str.strip()
        return melhor
    raise ValueError(f"Não foi possível ler o CSV ({ultimo_erro or 'sem colunas válidas'}).")


# ====================================================
# 🐼 BLOCO 5: OTIMIZAÇÕES DE PANDAS
# ====================================================
def memoria_dataframe(df: pd.DataFrame, *, indice: bool = True) -> int:
    """Memória ocupada pelo DataFrame em bytes (índice incluído por padrão)."""
    if df is None or df.empty:
        return 0
    try:
        return int(df.memory_usage(index=indice, deep=True).sum())
    except (TypeError, ValueError):  # pragma: no cover
        return 0


def otimizar_dtypes(
    df: pd.DataFrame,
    *,
    categoricas: bool = False,
    numericas: bool = False,
    limite_categoricas: int = 64,
    colunas_protegidas: Sequence[str] = (),
) -> pd.DataFrame:
    """Reduz memória/CPU: downcast numérico, texto→número e (opcional) categóricas.

    Args:
        categoricas: converte colunas de texto de baixa cardinalidade em
            ``category``. Padrão ``False`` (as páginas usam ``.str`` nelas);
            ative para colunas de agrupamento (base, status, projeto) — ganho
            típico de 40–70% de memória.
        numericas: converte colunas de texto **inteiramente numéricas** em
            número (com downcast). Útil logo após ``ler_csv_rapido``, que lê
            tudo como ``str`` para não pagar a inferência de tipos; a conversão
            só é aplicada quando não introduz ``NaN`` (nada é corrompido).
        limite_categoricas: cardinalidade máxima para virar ``category``.
        colunas_protegidas: nomes que nunca são alterados.

    Returns:
        Novo ``DataFrame`` otimizado (o original não é modificado).
    """
    if df is None or df.empty:
        return df
    protegidas = set(colunas_protegidas)
    saida = df.copy()
    for coluna in saida.columns:
        if coluna in protegidas:
            continue
        serie = saida[coluna]
        if pd.api.types.is_integer_dtype(serie):
            saida[coluna] = pd.to_numeric(serie, downcast="integer")
            continue
        if pd.api.types.is_float_dtype(serie):
            saida[coluna] = pd.to_numeric(serie, downcast="float")
            continue
        texto = pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie)
        if not texto:
            continue
        if numericas:
            convertida = pd.to_numeric(serie, errors="coerce")
            # Só troca se nenhum valor não-nulo virou NaN (texto misto fica como está).
            if convertida.notna().sum() == serie.notna().sum() and serie.notna().any():
                inteira = float(convertida.dropna().mod(1).eq(0).all())
                saida[coluna] = pd.to_numeric(
                    convertida, downcast="integer" if inteira else "float"
                )
                continue
        if categoricas:
            unicos = serie.dropna().unique()
            if 0 < len(unicos) <= max(2, int(limite_categoricas)):
                saida[coluna] = serie.astype("category")
    return saida


def chave_conteudo(serie: pd.Series, *, amostra: int = 128) -> str:
    """Impressão digital barata de uma série (para memoização segura)."""
    if serie is None or len(serie) == 0:
        return "vazio"
    try:
        texto = (
            serie.head(max(1, int(amostra)))
            .astype("string")
            .fillna("")
            .str.slice(0, 40)
            .str.cat(sep="|")
        )
    except (TypeError, ValueError):  # pragma: no cover - tipos exóticos
        texto = repr(serie.head(8).tolist())
    cauda = str(serie.iloc[-1]) if len(serie) else ""
    digest = hashlib.sha1(f"{texto}::{cauda}".encode("utf-8", "ignore")).hexdigest()[:20]
    return f"{len(serie)}::{digest}"


def datas_normalizadas(serie: pd.Series, *, dayfirst: bool = True) -> pd.Series:
    """Conversão de datas **memoizada** por conteúdo (evita reparsear no rerun).

    Delega a conversão para ``components.componentes.converter_data_br`` (que
    lê dia/mês/ano e trata seriais do Excel) e guarda o resultado em um LRU de
    processo: a mesma coluna, no mesmo rerun ou em outro, não é convertida de
    novo.
    """
    from components.componentes import converter_data_br

    if serie is None or len(serie) == 0:
        return pd.Series(dtype="datetime64[ns]")
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie
    chave = f"{dayfirst}::{chave_conteudo(serie)}"
    guardado = _CACHE_DATAS.get(chave)
    if guardado is not None and len(guardado) == len(serie):
        _CACHE_DATAS.move_to_end(chave)
        return pd.Series(guardado, index=serie.index)
    convertida = converter_data_br(serie)
    _CACHE_DATAS[chave] = convertida.to_numpy()
    _CACHE_DATAS.move_to_end(chave)
    while len(_CACHE_DATAS) > _LIMITE_CACHE_DATAS:
        _CACHE_DATAS.popitem(last=False)
    return convertida


def agregar_com_cache(
    df: pd.DataFrame,
    chave: str,
    produtor: Callable[[pd.DataFrame], Any],
    *,
    ttl: int = TTL_PADRAO,
) -> Any:
    """Memoização em disco de agregações caras (resumos, pivôs, rankings).

    O resultado é gravado como Parquet quando é um DataFrame/Series e como JSON
    quando é escalar/dict simples; expira por ``ttl`` ou quando a chave muda
    (a chave deve incluir o recorte: filtros, período e versão dos dados).
    """
    inicio = time.perf_counter()
    idade = idade_cache_segundos(f"agg::{chave}")
    if idade is not None and idade <= ttl:
        caminho_dados, caminho_meta = caminhos_cache(f"agg::{chave}")
        try:
            if caminho_dados.suffix == ".parquet" and caminho_dados.exists():
                df_cache = pd.read_parquet(caminho_dados, engine="pyarrow")
                if caminho_meta.exists():
                    meta = json.loads(caminho_meta.read_text(encoding="utf-8"))
                    if meta.get("tipo") == "series":
                        return df_cache.iloc[:, 0]
                return df_cache
        except Exception:  # pragma: no cover
            logger.debug("Cache de agregação inválido para '%s'.", chave, exc_info=True)

    resultado = produtor(df)
    try:
        if isinstance(resultado, pd.Series):
            gravar_cache_dataframe(
                f"agg::{chave}",
                resultado.to_frame(),
                meta_extra={"tipo": "series", "duracao_ms": (time.perf_counter() - inicio) * 1000},
            )
        elif isinstance(resultado, pd.DataFrame):
            gravar_cache_dataframe(
                f"agg::{chave}",
                resultado,
                meta_extra={
                    "tipo": "dataframe",
                    "duracao_ms": (time.perf_counter() - inicio) * 1000,
                },
            )
    except Exception:  # pragma: no cover
        logger.debug("Agregação não cacheável para '%s'.", chave, exc_info=True)
    return resultado


# ====================================================
# 🚀 BLOCO 6: ORQUESTRAÇÃO DE CARGA (COM CACHE)
# ====================================================
def carregar_com_cache(
    chave: str,
    *,
    url: str | None = None,
    produtor: Callable[[], pd.DataFrame] | None = None,
    ttl: int = TTL_PADRAO,
    sess: requests.Session | None = None,
    timeout: tuple[int, int] | int = TIMEOUT_PADRAO,
    leitor: Callable[[bytes], pd.DataFrame] | None = None,
    usar_condicional: bool = True,
    otimizar: bool = False,
    forcar: bool = False,
) -> ResultadoCarga:
    """Carrega uma fonte com cache em disco + revalidação condicional.

    Dois modos:

    * ``url``: baixa (ou revalida com ``304``) e faz o parse via ``leitor``
      (padrão :func:`ler_csv_rapido`);
    * ``produtor``: função sem argumentos que devolve o DataFrame (usada quando
      a fonte vem de API/SDK ou de arquivo local).

    Comportamento:

    1. cache fresco (idade ≤ ``ttl``) → devolve sem tocar na rede;
    2. cache vencido + ``usar_condicional`` → revalida; ``304`` renova o cache;
    3. sem cache ou dado novo → baixa/produz, grava e devolve;
    4. falha com cache antigo disponível → devolve o cache (degradação graciosa)
       com ``origem="cache"`` e ``erro`` preenchido.
    """
    inicio = time.perf_counter()
    ler = leitor or ler_csv_rapido
    idade = None if forcar else idade_cache_segundos(chave)
    df_cache, meta = ler_cache_dataframe(chave) if idade is not None else (None, {})
    if idade is not None and df_cache is not None and idade <= ttl:
        return ResultadoCarga(
            df=otimizar_dtypes(df_cache) if otimizar else df_cache,
            origem="cache",
            duracao_ms=(time.perf_counter() - inicio) * 1000.0,
            linhas=int(len(df_cache)),
            colunas=int(df_cache.shape[1]),
            idade_segundos=idade,
            tamanho_bytes=int(meta.get("tamanho_bytes", 0) or 0),
            etag=str(meta.get("etag") or "") or None,
            last_modified=str(meta.get("last_modified") or "") or None,
            chave=chave,
        )

    etag = str(meta.get("etag") or "") or None if usar_condicional else None
    last_modified = str(meta.get("last_modified") or "") or None if usar_condicional else None

    try:
        if url:
            status, corpo, cabecalhos = baixar_condicional(
                url, sess=sess, etag=etag, last_modified=last_modified, timeout=timeout
            )
            if status == 304 and df_cache is not None:
                gravar_cache_dataframe(
                    chave,
                    df_cache,
                    meta_extra={
                        "etag": cabecalhos.get("etag") or etag or "",
                        "last_modified": cabecalhos.get("last_modified") or last_modified or "",
                        "revalidado": True,
                    },
                )
                return ResultadoCarga(
                    df=otimizar_dtypes(df_cache) if otimizar else df_cache,
                    origem="cache_validado",
                    duracao_ms=(time.perf_counter() - inicio) * 1000.0,
                    linhas=int(len(df_cache)),
                    colunas=int(df_cache.shape[1]),
                    idade_segundos=idade,
                    etag=cabecalhos.get("etag") or etag,
                    last_modified=cabecalhos.get("last_modified") or last_modified,
                    chave=chave,
                )
            from services.google_drive_client import e_resposta_html

            if e_resposta_html(corpo, cabecalhos.get("content_type", "")):
                raise ValueError(
                    "A fonte respondeu HTML (verifique o compartilhamento do arquivo)."
                )
            df_novo = ler(corpo)
            tamanho = len(corpo)
        elif produtor is not None:
            df_novo = produtor()
            tamanho = 0
            cabecalhos = {"etag": "", "last_modified": ""}
        else:
            raise ValueError("carregar_com_cache exige 'url' ou 'produtor'.")
    except Exception as exc:
        mensagem = f"{type(exc).__name__}: {exc}"
        logger.warning("Carga de '%s' falhou: %s", chave, mensagem)
        if df_cache is not None and not df_cache.empty:
            return ResultadoCarga(
                df=otimizar_dtypes(df_cache) if otimizar else df_cache,
                origem="cache",
                duracao_ms=(time.perf_counter() - inicio) * 1000.0,
                linhas=int(len(df_cache)),
                colunas=int(df_cache.shape[1]),
                idade_segundos=idade,
                tamanho_bytes=int(meta.get("tamanho_bytes", 0) or 0),
                etag=etag,
                last_modified=last_modified,
                erro=mensagem,
                chave=chave,
                detalhes={"cache_preservado": True},
            )
        return resultado_vazio(chave, erro=mensagem, inicio=inicio)

    if df_novo is None or df_novo.empty:
        return resultado_vazio(chave, inicio=inicio)

    gravar_cache_dataframe(
        chave,
        df_novo,
        meta_extra={
            "etag": (cabecalhos or {}).get("etag") or etag or "",
            "last_modified": (cabecalhos or {}).get("last_modified") or last_modified or "",
            "url": url or "",
        },
    )
    resultado = otimizar_dtypes(df_novo) if otimizar else df_novo
    return ResultadoCarga(
        df=resultado,
        origem="rede" if url else "produtor",
        duracao_ms=(time.perf_counter() - inicio) * 1000.0,
        linhas=int(len(resultado)),
        colunas=int(resultado.shape[1]),
        idade_segundos=0.0,
        tamanho_bytes=int(tamanho),
        etag=(cabecalhos or {}).get("etag") or None,
        last_modified=(cabecalhos or {}).get("last_modified") or None,
        chave=chave,
    )


def carregar_planilha_gsheets(
    sheet_id: str,
    aba: str | None = None,
    *,
    ttl: int = TTL_PADRAO,
    timeout: tuple[int, int] | int = TIMEOUT_PADRAO,
    otimizar: bool = False,
    forcar: bool = False,
    chave: str | None = None,
) -> ResultadoCarga:
    """Carrega uma aba do Google Sheets pelo caminho mais rápido disponível.

    Ordem: ``export?format=csv`` (download direto) → ``gviz/tq?tqx=out:csv``
    (API Google Visualization). Ambos com cache em disco e revalidação
    condicional. Sem rede ou sem permissão, devolve o último cache válido com
    ``erro`` preenchido (o painel continua funcionando).
    """
    from config.settings import url_gsheets_export, url_gsheets_gviz_csv

    sid = str(sheet_id or "").strip()
    if not sid:
        return resultado_vazio(chave or "gsheets", erro="Sheet ID ausente.")
    nome_chave = chave or f"gsheets::{sid}::{aba or 'default'}"
    urls = [
        url_gsheets_export(sid, fmt="csv", sheet=aba),
        url_gsheets_gviz_csv(sid, sheet=aba),
    ]
    ultimo: ResultadoCarga | None = None
    erros: list[str] = []
    for posicao, url in enumerate(urls):
        resultado = carregar_com_cache(
            nome_chave if posicao == 0 else f"{nome_chave}::gviz",
            url=url,
            ttl=ttl,
            timeout=timeout,
            otimizar=otimizar,
            forcar=forcar,
        )
        if resultado.ok:
            return resultado
        ultimo = resultado
        if resultado.erro:
            erros.append(resultado.erro)
    if ultimo is not None:
        return ResultadoCarga(
            df=ultimo.df,
            origem=ultimo.origem,
            duracao_ms=ultimo.duracao_ms,
            linhas=ultimo.linhas,
            colunas=ultimo.colunas,
            idade_segundos=ultimo.idade_segundos,
            erro=" | ".join(dict.fromkeys(erros)) or ultimo.erro,
            chave=nome_chave,
        )
    return resultado_vazio(nome_chave, erro="Nenhuma URL de exportação disponível.")


@dataclass(frozen=True)
class EspecificacaoFonte:
    """Fonte de dados para carga paralela (ver :func:`carregar_varias`)."""

    chave: str
    url: str | None = None
    produtor: Callable[[], pd.DataFrame] | None = None
    ttl: int = TTL_PADRAO
    otimizar: bool = False


def carregar_varias(
    fontes: Sequence[EspecificacaoFonte] | Mapping[str, Mapping[str, Any]],
    *,
    max_workers: int = 4,
    timeout: tuple[int, int] | int = TIMEOUT_PADRAO,
) -> dict[str, ResultadoCarga]:
    """Carrega várias fontes em paralelo (I/O simultâneo, não sequencial).

    Aceita uma sequência de :class:`EspecificacaoFonte` ou um mapeamento
    ``{nome: {"url": ..., "ttl": ...}}``. O ganho é direto: três planilhas que
    levavam 3 × 2 s passam a ~2 s no total.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    especificacoes: list[EspecificacaoFonte] = []
    if isinstance(fontes, Mapping):
        for nome, params in fontes.items():
            especificacoes.append(
                EspecificacaoFonte(
                    chave=str(params.get("chave", nome)),
                    url=params.get("url"),
                    produtor=params.get("produtor"),
                    ttl=int(params.get("ttl", TTL_PADRAO)),
                    otimizar=bool(params.get("otimizar", False)),
                )
            )
    else:
        especificacoes = list(fontes)
    if not especificacoes:
        return {}

    def _carregar(spec: EspecificacaoFonte) -> ResultadoCarga:
        return carregar_com_cache(
            spec.chave,
            url=spec.url,
            produtor=spec.produtor,
            ttl=spec.ttl,
            timeout=timeout,
            otimizar=spec.otimizar,
        )

    resultados: dict[str, ResultadoCarga] = {}
    trabalhadores = max(1, min(int(max_workers), len(especificacoes)))
    if trabalhadores == 1:
        for spec in especificacoes:
            resultados[spec.chave] = _carregar(spec)
        return resultados
    with ThreadPoolExecutor(max_workers=trabalhadores, thread_name_prefix="totale-carga") as pool:
        futuros = {pool.submit(_carregar, spec): spec for spec in especificacoes}
        for futuro in as_completed(futuros):
            spec = futuros[futuro]
            try:
                resultados[spec.chave] = futuro.result()
            except Exception as exc:  # pragma: no cover - proteção de runtime
                logger.exception("Falha inesperada na carga de '%s'.", spec.chave)
                resultados[spec.chave] = resultado_vazio(
                    spec.chave, erro=f"{type(exc).__name__}: {exc}"
                )
    return resultados


# ====================================================
# 📊 BLOCO 7: DIAGNÓSTICO DE DESEMPENHO
# ====================================================
_CHAVE_TIMINGS = "_totale_timings"


@contextmanager
def temporizar(rotulo: str, *, registrar: bool = True) -> Iterator[dict[str, str | float]]:
    """Mede a duração de um bloco e (opcional) registra no estado da sessão.

    Uso::

        with temporizar("carregar_producao"):
            df = carregar(...)
    """
    medidor: dict[str, str | float] = {"rotulo": rotulo, "ms": 0.0}
    inicio = time.perf_counter()
    try:
        yield medidor
    finally:
        medidor["ms"] = (time.perf_counter() - inicio) * 1000.0
        if registrar:
            _registrar_tempo(rotulo, medidor["ms"])


def _registrar_tempo(rotulo: str, ms: float) -> None:
    try:
        import streamlit as st

        historico = st.session_state.setdefault(_CHAVE_TIMINGS, [])
        historico.append(
            {
                "rotulo": rotulo,
                "ms": round(float(ms), 1),
                "quando": datetime.now().strftime("%H:%M:%S"),
            }
        )
        del historico[:-40]
    except Exception:  # pragma: no cover - fora de um script Streamlit
        logger.debug("temporizar('%s'): %.1f ms (sem sessão para registrar).", rotulo, ms)


def resumo_desempenho() -> dict[str, Any]:
    """Tempos registrados na sessão + estatísticas do cache em disco."""
    timings: list[dict[str, Any]] = []
    try:
        import streamlit as st

        timings = list(st.session_state.get(_CHAVE_TIMINGS, []))
    except Exception:  # pragma: no cover
        timings = []
    total = sum(float(item.get("ms", 0.0)) for item in timings)
    return {
        "tempos": timings,
        "total_ms": round(total, 1),
        "mais_lento": max(timings, key=lambda i: float(i.get("ms", 0.0)), default=None),
        "cache": estatisticas_cache(),
    }


def _render_metrica_diagnostico(
    coluna: Any,
    rotulo: str,
    valor: Any,
    *,
    icone: str = "",
    tema: Literal["azul", "verde", "vermelho", "laranja", "cinza", "roxo", "gradiente"] = "azul",
) -> None:
    """Métrica do painel de diagnóstico: cartão avançado quando disponível."""
    try:
        from components.kpi_cards import render_metric

        render_metric(rotulo, valor, container=coluna, icone=icone, tema=tema, tamanho="compacto")
    except Exception:  # pragma: no cover - componentes indisponíveis
        logger.debug("Cartão de KPI indisponível; usando st.metric.", exc_info=True)
        coluna.metric(rotulo, valor)


def render_painel_desempenho(
    *,
    resultados: Mapping[str, ResultadoCarga] | None = None,
    fontes: Sequence[Mapping[str, Any]] | None = None,
    titulo: str = "Desempenho da carga de dados",
    expandido: bool = False,
) -> None:
    """Expansor de diagnóstico: origem dos dados, tempos, memória e cache.

    Args:
        resultados: cargas feitas por :func:`carregar_com_cache` (por chave).
        fontes: linhas prontas (``[{"Fonte": ..., "Download (ms)": ...}, …]``)
            para quem orquestra o download por conta própria, como a Central de
            Atualização de Dados.
    """
    import streamlit as st

    resumo = resumo_desempenho()
    with st.expander(f"⚙️ {titulo}", expanded=expandido):
        cache = resumo["cache"]
        valores = [
            ("Tempo medido", f"{resumo['total_ms']:.0f} ms", "timer", "azul"),
            ("Itens em cache", cache.get("itens", 0), "inventory_2", "laranja"),
            ("Tamanho do cache", cache.get("tamanho_legivel", "—"), "compress", "verde"),
            (
                "Diretório",
                "personalizado" if os.environ.get(VARIAVEL_DIRETORIO_CACHE) else "temporário",
                "folder_open",
                "cinza",
            ),
        ]
        colunas = st.columns(len(valores), gap="small")
        for coluna, (rotulo, valor, icone, tema) in zip(colunas, valores):
            _render_metrica_diagnostico(coluna, rotulo, valor, icone=icone, tema=tema)

        if fontes:
            st.dataframe(
                pd.DataFrame(list(fontes)),
                width="stretch",
                hide_index=True,
            )

        if resultados:
            linhas = []
            for nome, resultado in resultados.items():
                linhas.append(
                    {
                        "Fonte": nome,
                        "Linhas": resultado.linhas,
                        "Origem": resultado.origem,
                        "Duração (ms)": round(resultado.duracao_ms, 1),
                        "Memória": formatar_bytes(memoria_dataframe(resultado.df)),
                        "Situação": resultado.erro or "ok",
                    }
                )
            st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)

        if resumo["tempos"]:
            st.caption("Últimas etapas medidas nesta sessão:")
            st.dataframe(
                pd.DataFrame(resumo["tempos"][-12:][::-1]),
                width="stretch",
                hide_index=True,
                height=180,
            )
        if cache.get("diretorio"):
            st.caption(f"Cache em disco: `{cache['diretorio']}`")


__all__ = [
    "TTL_PADRAO",
    "VARIAVEL_DIRETORIO_CACHE",
    "VERSAO_CAMADA",
    "EspecificacaoFonte",
    "ResultadoCarga",
    "agregar_com_cache",
    "baixar_condicional",
    "cabecalhos_condicionais",
    "carregar_com_cache",
    "carregar_planilha_gsheets",
    "carregar_varias",
    "chave_conteudo",
    "criar_sessao_pool",
    "datas_normalizadas",
    "detectar_encoding",
    "detectar_separador",
    "diretorio_cache",
    "estatisticas_cache",
    "formatar_bytes",
    "gravar_cache_dataframe",
    "idade_cache_segundos",
    "ler_cache_dataframe",
    "ler_csv_rapido",
    "limpar_cache",
    "memoria_dataframe",
    "otimizar_dtypes",
    "render_painel_desempenho",
    "resultado_vazio",
    "resumo_desempenho",
    "sanitizar_para_parquet",
    "sessao_http",
    "temporizar",
]
