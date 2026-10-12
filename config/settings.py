"""
config/settings.py
==================
Configurações centralizadas, IDs de planilhas/arquivos e construtores de URLs
do Portal TOTALE. Prioriza `st.secrets` e variáveis de ambiente antes de usar
os valores padrão de fallback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import quote as url_quote
from zoneinfo import ZoneInfo

try:
    import streamlit as st
except ImportError:  # permite importar em testes/scripts sem Streamlit ativo
    st = None  # type: ignore[assignment]

FUSO_BR = ZoneInfo("America/Sao_Paulo")
TIMEOUT_HTTP_PADRAO: int = 30

# Valores padrão (fallbacks) dos recursos corporativos no Google Drive / Sheets
_DEFAULT_SHEET_ID_ATIVOS = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
_DEFAULT_SHEET_ID_PROD = "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
_DEFAULT_DRIVE_ID_CONS = "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"
_DEFAULT_DRIVE_ID_INDICADORES = "1k6NrvdZzdSV_sGOQkMKIssEhh7p7wyO0"


def obter_secret(chave: str, default: str = "") -> str:
    """Lê uma configuração de `st.secrets` ou `os.environ` com fallback seguro."""
    env_val = os.environ.get(chave)
    if env_val:
        return env_val.strip()
    if st is not None:
        try:
            if hasattr(st, "secrets") and chave in st.secrets:
                valor = st.secrets[chave]
                if valor is not None and str(valor).strip():
                    return str(valor).strip()
        except Exception:
            pass
    return default


def url_gsheets_edit(sheet_id: str | None = None) -> str:
    """Retorna a URL de edição/conexão de uma planilha do Google Sheets."""
    sid = sheet_id or obter_sheet_id_ativos()
    return f"https://docs.google.com/spreadsheets/d/{sid}/edit"


def url_gsheets_base(sheet_id: str | None = None) -> str:
    """Retorna a URL base (sem /edit) de uma planilha do Google Sheets."""
    sid = sheet_id or obter_sheet_id_ativos()
    return f"https://docs.google.com/spreadsheets/d/{sid}"


def url_gsheets_export(
    sheet_id: str | None = None,
    fmt: str = "csv",
    sheet: str | None = None,
) -> str:
    """Retorna a URL de exportação direta (`export?format=...`) do Google Sheets."""
    sid = sheet_id or obter_sheet_id_ativos()
    base = f"https://docs.google.com/spreadsheets/d/{sid}/export?format={fmt}"
    if sheet:
        return f"{base}&sheet={url_quote(sheet)}"
    return base


def url_gsheets_gviz_csv(
    sheet_id: str | None = None,
    sheet: str | None = None,
) -> str:
    """Retorna a URL CSV da API Google Visualization (`gviz/tq?tqx=out:csv`)."""
    sid = sheet_id or obter_sheet_id_ativos()
    base = f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv"
    if sheet:
        return f"{base}&sheet={url_quote(sheet)}"
    return base


def url_drive_download(file_id: str) -> str:
    """Retorna a URL direta de download de arquivo no Google Drive."""
    return f"https://drive.google.com/uc?id={file_id}&export=download"


def obter_sheet_id_ativos() -> str:
    return obter_secret(
        "SHEET_ID_ATIVOS",
        obter_secret("GSHEETS_ID", _DEFAULT_SHEET_ID_ATIVOS),
    )


def obter_sheet_id_prod() -> str:
    return obter_secret("SHEET_ID_PROD", _DEFAULT_SHEET_ID_PROD)


def obter_drive_id_cons() -> str:
    return obter_secret("DRIVE_ID_CONS", _DEFAULT_DRIVE_ID_CONS)


def obter_drive_id_indicadores() -> str:
    return obter_secret("DRIVE_FILE_ID", _DEFAULT_DRIVE_ID_INDICADORES)


# Constantes prontas para uso direto nos módulos
SHEET_ID_ATIVOS: str = obter_sheet_id_ativos()
SHEET_ID_PROD: str = obter_sheet_id_prod()
DRIVE_ID_CONS: str = obter_drive_id_cons()
DRIVE_ID_INDICADORES: str = obter_drive_id_indicadores()

SHEET_ABA_ATIVOS: str = "lista_ativos"
SHEET_ABA_PROD: str = "Prod"

URL_ATIVOS_EDIT: str = url_gsheets_edit(SHEET_ID_ATIVOS)
URL_ATIVOS_BASE: str = url_gsheets_base(SHEET_ID_ATIVOS)
URL_ATIVOS_CSV: str = url_gsheets_export(SHEET_ID_ATIVOS, fmt="csv")
URL_PROD_XLSX: str = url_gsheets_export(SHEET_ID_PROD, fmt="xlsx")
URL_CONS_DOWNLOAD: str = url_drive_download(DRIVE_ID_CONS)


@dataclass(frozen=True)
class FontesDadosConfig:
    """Agrupador imutável de IDs e URLs das fontes de dados do Portal TOTALE."""

    sheet_id_ativos: str = field(default_factory=obter_sheet_id_ativos)
    sheet_aba_ativos: str = SHEET_ABA_ATIVOS
    sheet_id_prod: str = field(default_factory=obter_sheet_id_prod)
    sheet_aba_prod: str = SHEET_ABA_PROD
    drive_id_cons: str = field(default_factory=obter_drive_id_cons)
    drive_id_indicadores: str = field(default_factory=obter_drive_id_indicadores)
    timeout: int = TIMEOUT_HTTP_PADRAO
    fuso: ZoneInfo = FUSO_BR


__all__ = [
    "DRIVE_ID_CONS",
    "DRIVE_ID_INDICADORES",
    "FUSO_BR",
    "SHEET_ABA_ATIVOS",
    "SHEET_ABA_PROD",
    "SHEET_ID_ATIVOS",
    "SHEET_ID_PROD",
    "TIMEOUT_HTTP_PADRAO",
    "URL_ATIVOS_BASE",
    "URL_ATIVOS_CSV",
    "URL_ATIVOS_EDIT",
    "URL_CONS_DOWNLOAD",
    "URL_PROD_XLSX",
    "FontesDadosConfig",
    "obter_drive_id_cons",
    "obter_drive_id_indicadores",
    "obter_secret",
    "obter_sheet_id_ativos",
    "obter_sheet_id_prod",
    "url_drive_download",
    "url_gsheets_base",
    "url_gsheets_edit",
    "url_gsheets_export",
    "url_gsheets_gviz_csv",
]
