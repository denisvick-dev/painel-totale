"""
services/google_drive_client.py
===============================
Cliente HTTP resiliente e utilitários unificados para download e leitura de
arquivos CSV/Excel no Google Drive e Google Sheets.
"""

from __future__ import annotations

import csv
import logging
import os
import re
import tempfile
from io import BytesIO
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import (
    TIMEOUT_HTTP_PADRAO,
    obter_sheet_id_ativos,
    url_drive_download,
    url_gsheets_edit,
    url_gsheets_export,
    url_gsheets_gviz_csv,
)

logger = logging.getLogger(__name__)

_DELIMITADORES_CSV: tuple[str, ...] = (",", ";", "\t", "|")


def criar_sessao_http(user_agent: str | None = None) -> requests.Session:
    """Cria uma sessão HTTP com política de Retry para falhas transitórias (429/5xx)."""
    sess = requests.Session()
    sess.headers["User-Agent"] = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    try:
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
    except TypeError:  # urllib3 < 1.26
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
        )
    sess.mount("https://", HTTPAdapter(max_retries=retry))
    return sess


def urls_download_drive(url: str) -> list[str]:
    """Retorna a URL principal e o fallback `drive.usercontent.google.com` com `confirm=t`."""
    urls = [url]
    m = re.search(r"(?:[?&]id=|d/)([A-Za-z0-9_-]{20,})", url)
    if m:
        alt = (
            "https://drive.usercontent.google.com/download"
            f"?id={m.group(1)}&export=download&confirm=t"
        )
        if alt not in urls:
            urls.append(alt)
    return urls


def e_resposta_html(conteudo: bytes, content_type: str = "") -> bool:
    """Detecta se os bytes retornados são uma página HTML de aviso/login do Google."""
    amostra = conteudo[:512].lstrip()
    if amostra.startswith(b"PK\x03\x04"):
        return False
    ctype = content_type.lower()
    if "text/html" in ctype or "application/xhtml" in ctype:
        return True
    baixo = amostra[:64].lower()
    return baixo.startswith((b"<!doctype", b"<html", b"<head", b"<body"))


def extrair_token_confirm(corpo: bytes) -> str | None:
    """Extrai o token de confirmação de vírus das páginas intermediárias do Google Drive."""
    m = re.search(rb"[?&]confirm=([0-9A-Za-z_\-]+)", corpo)
    if m:
        return m.group(1).decode("ascii", "ignore")
    m = re.search(rb"name=[\"']confirm[\"'][^>]*value=[\"']([^\"']+)", corpo)
    if not m:
        m = re.search(rb"value=[\"']([^\"']+)[\"'][^>]*name=[\"']confirm[\"']", corpo)
    if m:
        return m.group(1).decode("ascii", "ignore")
    if b"download_warning" in corpo or b"uc-download-link" in corpo:
        return "t"
    return None


def adicionar_confirm_url(url: str, token: str) -> str:
    """Adiciona ou substitui o parâmetro `confirm` na query string da URL."""
    partes = urlsplit(url)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    query["confirm"] = token
    return urlunsplit(
        (partes.scheme, partes.netloc, partes.path, urlencode(query), "")
    )


def baixar_bytes_drive(
    sess: requests.Session | None,
    url: str,
    timeout: int = TIMEOUT_HTTP_PADRAO,
) -> bytes:
    """Baixa bytes de uma URL do Google Drive/Sheets tratando confirmação de HTML."""
    cliente = sess or criar_sessao_http()
    for candidato in urls_download_drive(url):
        resposta = cliente.get(candidato, timeout=timeout)
        resposta.raise_for_status()
        corpo = resposta.content
        ctype = resposta.headers.get("Content-Type", "")
        if not e_resposta_html(corpo, ctype):
            return corpo
        token = next(
            (
                v
                for k, v in resposta.cookies.items()
                if k.startswith("download_warning")
            ),
            None,
        ) or extrair_token_confirm(corpo)
        if not token:
            continue
        resposta2 = cliente.get(
            adicionar_confirm_url(candidato, token), timeout=timeout
        )
        resposta2.raise_for_status()
        if not e_resposta_html(
            resposta2.content, resposta2.headers.get("Content-Type", "")
        ):
            return resposta2.content
    raise RuntimeError(
        "O Google Drive respondeu com uma página HTML. "
        "Verifique se o arquivo está compartilhado como "
        "'qualquer pessoa com o link'."
    )


def baixar_arquivo_drive(
    file_id: str,
    sess: requests.Session | None = None,
    timeout: int = 60,
) -> bytes:
    """Baixa um arquivo pelo ID do Google Drive com fallback opcional para `gdown`."""
    url = url_drive_download(file_id)
    try:
        return baixar_bytes_drive(sess, url, timeout=timeout)
    except Exception as exc:
        logger.warning("Download HTTP direto falhou (%s). Tentando gdown...", exc)
        tmp_path = ""
        try:
            from gdown.download import download as gdown_download

            with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp_file:
                tmp_path = tmp_file.name
            gdown_download(id=file_id, output=tmp_path, quiet=True, resume=True)
            with open(tmp_path, "rb") as handle:
                return handle.read()
        except Exception:
            raise exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


def separadores_csv(texto: str) -> list[str]:
    """Infere separadores CSV usando `csv.Sniffer` com contagem como desempate."""
    primeira = texto.splitlines()[0] if texto else ""
    contagem = {s: primeira.count(s) for s in _DELIMITADORES_CSV}
    seps: list[str] = []
    try:
        sniff = csv.Sniffer().sniff(texto[:8000], delimiters=",;\t|").delimiter
    except csv.Error:
        sniff = ""
    if sniff in _DELIMITADORES_CSV:
        seps.append(sniff)
    for sep, qtde in sorted(contagem.items(), key=lambda item: item[1], reverse=True):
        if qtde > 0 and sep not in seps:
            seps.append(sep)
    return seps or [","]


def ler_csv_uma_tentativa(conteudo: bytes, sep: str, enc: str) -> pd.DataFrame:
    """Lê bytes CSV com separador e encoding explícitos."""
    kwargs: dict[str, object] = {
        "sep": sep,
        "encoding": enc,
        "dtype": str,
        "low_memory": False,
    }
    try:
        return pd.read_csv(BytesIO(conteudo), on_bad_lines="skip", **kwargs)  # type: ignore[call-overload]
    except TypeError:
        return pd.read_csv(BytesIO(conteudo), **kwargs)  # type: ignore[call-overload]


def ler_csv_remoto(conteudo: bytes) -> pd.DataFrame:
    """Decodifica e parseia CSV remoto inferindo encoding e separador."""
    if not conteudo or not conteudo.strip():
        raise ValueError("O arquivo remoto veio vazio.")
    if e_resposta_html(conteudo, ""):
        raise ValueError("O remoto devolveu HTML em vez de CSV.")

    amostra = conteudo.split(b"\n", 1)[0][:8000]
    melhor: pd.DataFrame | None = None
    ultimo_erro: Exception | None = None

    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            cabecalho = amostra.decode(enc)
        except UnicodeDecodeError as e:
            ultimo_erro = e
            continue
        for sep in separadores_csv(cabecalho):
            try:
                df = ler_csv_uma_tentativa(conteudo, sep, enc)
            except UnicodeDecodeError as e:
                ultimo_erro = e
                break
            except Exception as e:
                ultimo_erro = e
                continue
            if df.empty:
                continue
            if df.shape[1] > 1:
                return df
            if melhor is None:
                melhor = df

    if melhor is not None:
        return melhor
    raise ValueError(f"Não foi possível ler o CSV ({ultimo_erro or 'sem colunas'}).")


def carregar_excel_drive(
    file_id: str,
    sess: requests.Session | None = None,
    timeout: int = 60,
) -> dict[str, pd.DataFrame]:
    """Baixa uma pasta de trabalho Excel do Google Drive e retorna todas as abas."""
    raw = baixar_arquivo_drive(file_id, sess=sess, timeout=timeout)
    all_sheets: dict[str, pd.DataFrame] = pd.read_excel(
        BytesIO(raw), sheet_name=None, engine="openpyxl"
    )
    for sheet in all_sheets.values():
        sheet.columns = sheet.columns.astype(str).str.strip()
    return all_sheets


def carregar_planilha_gsheets_csv(
    sheet_id: str | None = None,
    aba: str | None = None,
    sess: requests.Session | None = None,
    timeout: int = TIMEOUT_HTTP_PADRAO,
    usar_conexao_streamlit: bool = True,
) -> pd.DataFrame:
    """Carrega uma aba do Google Sheets tentando export CSV, GViz CSV e GSheetsConnection."""
    sid = sheet_id or obter_sheet_id_ativos()
    cliente = sess or criar_sessao_http()
    urls = [
        url_gsheets_export(sid, fmt="csv", sheet=aba),
        url_gsheets_gviz_csv(sid, sheet=aba),
    ]
    for url in urls:
        try:
            raw = baixar_bytes_drive(cliente, url, timeout=timeout)
            df = ler_csv_remoto(raw)
            if not df.empty:
                df.columns = df.columns.astype(str).str.strip()
                return df
        except Exception:
            continue

    if usar_conexao_streamlit:
        try:
            import streamlit as st
            from streamlit_gsheets import GSheetsConnection

            conn = st.connection("gsheets", type=GSheetsConnection)
            kwargs: dict[str, object] = {
                "spreadsheet": url_gsheets_edit(sid),
                "ttl": 0,
            }
            if aba:
                kwargs["worksheet"] = aba
            df_conn = conn.read(**kwargs)  # type: ignore[arg-type]
            if isinstance(df_conn, pd.DataFrame) and not df_conn.empty:
                df_conn.columns = df_conn.columns.astype(str).str.strip()
                return df_conn
        except Exception:
            pass

    return pd.DataFrame()


__all__ = [
    "adicionar_confirm_url",
    "baixar_arquivo_drive",
    "baixar_bytes_drive",
    "carregar_excel_drive",
    "carregar_planilha_gsheets_csv",
    "criar_sessao_http",
    "e_resposta_html",
    "extrair_token_confirm",
    "ler_csv_remoto",
    "ler_csv_uma_tentativa",
    "separadores_csv",
    "urls_download_drive",
]
