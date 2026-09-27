"""
Login e senha — testes da autenticação de pages/gestao_ativos.py

Arquitetura definida pelo projeto: **todo o controle de login/senha vive
exclusivamente em `pages/gestao_ativos.py`**. Este arquivo valida as regras de
segurança dessa implementação e a própria exclusividade do módulo.

Executar: pytest tests/test_gestao_ativos_auth.py -v
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import streamlit as st

from pages import gestao_ativos as ga

SENHA = "SenhaForte!2026"
RAIZ = Path(__file__).resolve().parents[1]
MODULO_AUTH = RAIZ / "pages" / "gestao_ativos.py"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Hash e verificação de senha
# ═══════════════════════════════════════════════════════════════════════════════
def test_hash_pbkdf2_formato_e_verificacao():
    h = ga.gerar_hash_senha(SENHA)
    assert h.startswith("pbkdf2_sha256$")
    assert len(h.split("$")) == 4
    assert ga._verificar_senha(SENHA, h) is True


def test_hash_usa_salt_aleatorio():
    assert ga.gerar_hash_senha(SENHA) != ga.gerar_hash_senha(SENHA)


def test_senha_incorreta_recusada():
    assert ga._verificar_senha("outra", ga.gerar_hash_senha(SENHA)) is False


def test_legado_sha256_aceito_apenas_para_migracao():
    legado = hashlib.sha256(SENHA.encode()).hexdigest()
    assert ga._verificar_senha(SENHA, legado) is True
    assert ga._senha_precisa_migrar(legado) is True


@pytest.mark.parametrize("texto_plano", ["admin123", "senha", "123456", SENHA])
def test_senha_em_texto_plano_rejeitada(texto_plano):
    """Regressão: o código aceitava senha em claro como fallback."""
    assert ga._verificar_senha(texto_plano, texto_plano) is False
    assert ga._senha_precisa_migrar(texto_plano) is True


def test_valores_vazios_ou_corrompidos():
    assert ga._verificar_senha("", "") is False
    assert ga._verificar_senha("x", "pbkdf2_sha256$abc$zz$zz") is False
    assert ga._verificar_senha("x", "pbkdf2_sha256$0$$") is False


def test_gerar_hash_recusa_senha_vazia():
    with pytest.raises(ValueError):
        ga.gerar_hash_senha("")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Usuários vindos de st.secrets
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def secrets_fake(monkeypatch):
    def _aplicar(dados):
        monkeypatch.setattr(st, "secrets", dados, raising=False)
    return _aplicar


def test_sem_secrets_ninguem_entra(secrets_fake):
    secrets_fake({})
    assert ga.Config.usuarios() == {}


def test_usuarios_normalizam_login_role_e_bases(secrets_fake):
    secrets_fake({
        "usuarios": {
            "DenisVick": {
                "senha": ga.gerar_hash_senha(SENHA),
                "nome": "Denis Vick",
                "role": "ADMIN",
                "bases": ["São Paulo", "  Guarulhos  ", ""],
            },
            "sem_senha": {"nome": "Ignorado"},
            "role_invalido": {"senha": "x", "role": "super-usuario"},
        }
    })
    usuarios = ga.Config.usuarios()
    assert set(usuarios) == {"denisvick", "role_invalido"}
    assert usuarios["denisvick"]["role"] == "admin"
    assert usuarios["denisvick"]["bases"] == ["São Paulo", "Guarulhos"]
    # role desconhecido cai para o perfil mais restritivo
    assert usuarios["role_invalido"]["role"] == "leitura"


def test_nenhuma_credencial_embutida_no_codigo():
    """O módulo não pode conter usuário/senha fixos."""
    fonte = MODULO_AUTH.read_text(encoding="utf-8")
    assert "admin123" not in fonte
    assert '"senha": "' not in fonte.replace('senha = "pbkdf2', "")
    assert "denisvick" not in fonte.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Permissões por perfil
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("role", "acao", "esperado"),
    [
        ("admin", "auditoria", True),
        ("admin", "desligar", True),
        ("supervisor", "importar", True),
        ("supervisor", "auditoria", False),
        ("operador", "escrever", True),
        ("operador", "desligar", False),
        ("leitura", "ler", True),
        ("leitura", "escrever", False),
        ("desconhecido", "ler", False),
    ],
)
def test_permissoes(role, acao, esperado):
    assert ga.Usuario("x", "X", role, []).pode(acao) is esperado


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Bloqueio por tentativas repetidas
# ═══════════════════════════════════════════════════════════════════════════════
def test_bloqueio_apos_tentativas():
    for chave in ("login_falhas", "login_bloqueado_ate"):
        st.session_state.pop(chave, None)
    assert ga._segundos_bloqueio_restantes() == 0
    for _ in range(ga.MAX_TENTATIVAS):
        ga._registrar_falha_login()
    assert ga._segundos_bloqueio_restantes() > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Exclusividade: login/senha só existem em gestao_ativos.py
# ═══════════════════════════════════════════════════════════════════════════════
def _modulos_do_projeto() -> list[Path]:
    arquivos = list((RAIZ / "pages").glob("*.py"))
    arquivos += list((RAIZ / "components").glob("*.py"))
    arquivos += list((RAIZ / "robo").glob("*.py"))
    arquivos.append(RAIZ / "streamlit_app.py")
    return sorted(arquivos)


@pytest.mark.parametrize(
    "termo",
    ["type=\"password\"", "pbkdf2", "verificar_senha", "gerar_hash_senha", "senha"],
)
def test_login_e_senha_apenas_em_gestao_ativos(termo):
    """
    Regra de arquitetura do projeto: nenhum outro módulo pode tratar
    login/senha. Este teste falha se alguém reintroduzir autenticação paralela.
    """
    infratores = [
        str(a.relative_to(RAIZ))
        for a in _modulos_do_projeto()
        if a != MODULO_AUTH and termo in a.read_text(encoding="utf-8").lower()
    ]
    assert not infratores, f"{termo!r} encontrado fora de gestao_ativos.py: {infratores}"


def test_nao_existe_modulo_de_auth_separado():
    assert not (RAIZ / "components" / "auth.py").exists()
    assert not (RAIZ / "pages" / "login.py").exists()


def test_fluxo_de_login_ponta_a_ponta(secrets_fake):
    """Senha errada é recusada; senha correta autentica a página."""
    from streamlit.testing.v1 import AppTest

    secrets_fake({
        "usuarios": {
            "denis": {
                "nome": "Denis Vick",
                "role": "admin",
                "bases": [],
                "senha": ga.gerar_hash_senha(SENHA),
            }
        }
    })

    at = AppTest.from_file(str(MODULO_AUTH), default_timeout=90)
    at.run()
    assert [t.label for t in at.text_input] == ["👤 Usuário", "🔑 Senha"]
    assert at.session_state["autenticado"] is False

    # senha incorreta -> permanece bloqueado
    at.text_input[0].set_value("denis")
    at.text_input[1].set_value("senha-errada")
    at.button[0].click()
    at.run()
    assert any("Credenciais inválidas" in e.value for e in at.error)
    assert at.session_state["autenticado"] is False

    # senha correta -> autentica
    at.text_input[0].set_value("denis")
    at.text_input[1].set_value(SENHA)
    at.button[0].click()
    at.run()
    assert at.session_state["autenticado"] is True
    assert at.session_state["usuario"].login == "denis"
    assert not _excecoes_apptest(at)


def test_pagina_bloqueia_sem_usuarios_configurados(secrets_fake):
    from streamlit.testing.v1 import AppTest

    secrets_fake({})
    at = AppTest.from_file(str(MODULO_AUTH), default_timeout=90)
    at.run()
    assert any("Nenhum usuário configurado" in e.value for e in at.error)
    assert at.session_state["autenticado"] is False


def _excecoes_apptest(at) -> list[str]:
    return [str(e.value).replace("\n", " | ")[:200] for e in at.exception]


def test_cli_de_geracao_de_hash():
    """O helper documentado no módulo precisa funcionar fora do Streamlit."""
    import subprocess
    import sys

    codigo = (
        "from pages.gestao_ativos import gerar_hash_senha;"
        "print(gerar_hash_senha('SenhaTeste123'))"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True, text=True, cwd=str(RAIZ), check=False,
    )
    if resultado.returncode != 0:  # pragma: no cover
        pytest.skip(f"CLI indisponível: {resultado.stderr[:200]}")
    saida = resultado.stdout.strip()
    assert saida.startswith("pbkdf2_sha256$")
    assert ga._verificar_senha("SenhaTeste123", saida) is True
