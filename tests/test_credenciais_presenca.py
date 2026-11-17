import sys
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from services.absenteismo import _cliente_gspread


class SemSecrets:
    def get(self, *args):
        raise StreamlitSecretNotFoundError("No secrets found")


def test_sem_secrets_mostra_orientacao_sem_expor_caminhos_internos(monkeypatch):
    monkeypatch.setattr(st, "secrets", SemSecrets())
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    with pytest.raises(RuntimeError, match="Conta de serviço não configurada") as exc:
        _cliente_gspread()
    assert "secrets.example.toml" in str(exc.value)
    assert "No secrets found" not in str(exc.value)


def preparar_google_falso(monkeypatch, credenciais):
    monkeypatch.setitem(sys.modules, "gspread", SimpleNamespace(authorize=lambda c: c))
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", SimpleNamespace(Credentials=credenciais))


def test_variavel_de_ambiente_funciona_sem_secrets(monkeypatch):
    monkeypatch.setattr(st, "secrets", SemSecrets())
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/seguro/conta.json")
    preparar_google_falso(monkeypatch, SimpleNamespace(
        from_service_account_file=lambda arquivo, scopes: (arquivo, scopes),
    ))
    arquivo, escopos = _cliente_gspread()
    assert arquivo == "/seguro/conta.json"
    assert "https://www.googleapis.com/auth/spreadsheets" in escopos


def test_secrets_tem_prioridade_e_normaliza_quebra_de_linha(monkeypatch):
    monkeypatch.setattr(st, "secrets", {"gcp_service_account": {"private_key": "linha1\\nlinha2"}})
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/nao-usar.json")
    preparar_google_falso(monkeypatch, SimpleNamespace(
        from_service_account_info=lambda info, scopes: info,
    ))
    assert _cliente_gspread()["private_key"] == "linha1\nlinha2"


def test_json_invalido_tem_erro_seguro(monkeypatch):
    monkeypatch.setattr(st, "secrets", SemSecrets())
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/seguro/conta.json")
    def falhar(*args, **kwargs):
        raise ValueError("conteudo potencialmente sensivel")
    preparar_google_falso(monkeypatch, SimpleNamespace(from_service_account_file=falhar))
    with pytest.raises(RuntimeError, match="JSON de conta de serviço válido") as exc:
        _cliente_gspread()
    assert "potencialmente sensivel" not in str(exc.value)
