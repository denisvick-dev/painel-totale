# ═══════════════════════════════════════════════════════════════════════════════
# GESTÃO DE ATIVOS TOTALE — V 4.1.0 (INTEGRADO COM COMPONENTES.PY)
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import gspread
import numpy as np
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# Importação do Design System
from components.componentes import (
    Cores,
    aplicar_estilo,
    render_empty_state,
    render_hero_totale_1,
    render_kpi,
    render_section_header,
    render_sidebar_brand,
    render_sidebar_divider,
    render_sidebar_footer_info,
    render_sidebar_info,
    render_sidebar_section,
    render_table_html,
)


# ═══════════════════════════════════════════════════════════════════════════════
# [0] SAFE & AUTH (Mantido do código anterior)
# ═══════════════════════════════════════════════════════════════════════════════
class Safe:
    _N = frozenset({"none", "nan", "nat", "null", "n/a", "na", "<na>", "#n/a", ""})

    @classmethod
    def celula(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (bool, np.bool_)):
            return "SIM" if v else "NÃO"
        if isinstance(v, np.integer):
            return str(int(v))
        if isinstance(v, (float, np.floating)):
            try:
                if np.isnan(v):
                    return ""
            except Exception:
                pass
            return str(int(v)) if v == int(v) else str(v)
        try:
            if pd.isna(v):
                return ""
        except Exception:
            pass
        s = str(v).strip()
        return "" if s.lower() in cls._N else s

    @classmethod
    def str(cls, v: Any, d="") -> str:
        r = cls.celula(v)
        return r if r else d

    @classmethod
    def upper(cls, v, d="") -> str:
        return cls.str(v, d).upper()

    @classmethod
    def lower(cls, v, d="") -> str:
        return cls.str(v, d).lower()

    @classmethod
    def limpar_df(cls, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame() if df is None else df
        for c in df.columns:
            df[c] = df[c].apply(cls.celula)
        return df[~(df == "").all(axis=1)].reset_index(drop=True)

    @classmethod
    def para_api(cls, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy().fillna("").replace({None: ""})
        for c in df.columns:
            df[c] = df[c].apply(cls.celula)
        df.columns = [cls.str(c, f"c{i}") for i, c in enumerate(df.columns)]
        return df.astype(str)

    @classmethod
    def garantir_colunas(cls, df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        def n(s):
            return str(s).lower().translate(str.maketrans("ãáâéêíóôúç ", "aaaeeioouc_"))

        for c in cols:
            if c not in df.columns:
                for ex in df.columns:
                    if n(ex) == n(c):
                        df = df.rename(columns={ex: c})
                        break
                else:
                    df[c] = ""
        return df[list(cols)].copy()


# ═══════════════════════════════════════════════════════════════════════════════
# [0.1] AUTENTICAÇÃO — exclusiva desta página
#
#  • As credenciais vêm de st.secrets["usuarios"] — NUNCA do código-fonte.
#  • Somente hash de senha:
#        pbkdf2_sha256$<iteracoes>$<salt_hex>$<hash_hex>   (recomendado)
#        SHA-256 hexadecimal                                (legado/migração)
#    Senha em texto plano é RECUSADA.
#  • Comparação em tempo constante (hmac.compare_digest).
#  • Bloqueio temporário após tentativas repetidas.
#
#  Para gerar o hash de uma senha (e colar no secrets.toml):
#     python -c "from pages.gestao_ativos import gerar_hash_senha; print(gerar_hash_senha('MinhaSenhaForte'))"
# ═══════════════════════════════════════════════════════════════════════════════
ALGORITMO_PBKDF2 = "pbkdf2_sha256"
ITERACOES_PBKDF2 = 260_000
_HEXADECIMAIS = frozenset("0123456789abcdefABCDEF")
MAX_TENTATIVAS = 5
BLOQUEIO_SEGUNDOS = 60


def gerar_hash_senha(senha: str, iteracoes: int = ITERACOES_PBKDF2) -> str:
    """Gera um hash PBKDF2-HMAC-SHA256 no formato aceito por `_verificar_senha`."""
    if not isinstance(senha, str) or not senha:
        raise ValueError("Senha vazia não pode ser transformada em hash.")
    salt = os.urandom(16)
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, iteracoes)
    return f"{ALGORITMO_PBKDF2}${iteracoes}${salt.hex()}${derivada.hex()}"


def _formato_senha(armazenada: str) -> str:
    """Classifica o valor armazenado: pbkdf2, sha256 (legado) ou texto_plano."""
    if armazenada.startswith(f"{ALGORITMO_PBKDF2}$"):
        return "pbkdf2"
    if len(armazenada) == 64 and all(c in _HEXADECIMAIS for c in armazenada):
        return "sha256_legado"
    return "texto_plano"


def _verificar_senha(digitada: str, armazenada: str) -> bool:
    """
    Verifica a senha digitada contra o valor armazenado.

    Aceita `pbkdf2_sha256$...` e SHA-256 hexadecimal (compatibilidade com
    cadastros antigos). **Não aceita** senha em texto plano: nesse caso o acesso
    é negado, forçando a migração para hash.
    """
    d = Safe.str(digitada)
    a = Safe.str(armazenada)
    if not d or not a:
        return False

    formato = _formato_senha(a)
    if formato == "pbkdf2":
        try:
            _, iteracoes_str, salt_hex, hash_hex = a.split("$")
            iteracoes = int(iteracoes_str)
            salt = bytes.fromhex(salt_hex)
            esperado = bytes.fromhex(hash_hex)
        except (ValueError, TypeError):
            return False
        if iteracoes <= 0 or not salt or not esperado:
            return False
        derivada = hashlib.pbkdf2_hmac("sha256", d.encode("utf-8"), salt, iteracoes)
        return hmac.compare_digest(derivada, esperado)

    if formato == "sha256_legado":
        legado = hashlib.sha256(d.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legado, a.lower())

    return False


def _senha_precisa_migrar(armazenada: str) -> bool:
    """True quando a senha armazenada está em formato fraco (não-PBKDF2)."""
    return _formato_senha(Safe.str(armazenada)) != "pbkdf2"


# ═══════════════════════════════════════════════════════════════════════════════
# [1] GSPREAD & CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def _gspread_client() -> gspread.Client:
    secret_map = getattr(st, "secrets", {}).get("gcp_service_account", {})
    if not isinstance(secret_map, dict):
        secret_map = dict(secret_map)
    info = dict(secret_map)
    # Correção de newline em secrets.toml
    if "private_key" in info:
        info["private_key"] = str(info["private_key"]).replace("\\n", "\n")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def _gspread_sheet(worksheet_name: str) -> gspread.Worksheet:
    gc = _gspread_client()
    sh = gc.open_by_key(Config.SHEET_ID)
    return sh.worksheet(worksheet_name)


def _append_gspread(worksheet_name: str, linha: list[Any]) -> bool:
    try:
        ws = _gspread_sheet(worksheet_name)
        ws.append_row(
            [Safe.celula(v) for v in linha], value_input_option="USER_ENTERED"
        )
        return True
    except Exception as exc:
        st.warning(f"️ Append falhou: {exc}")
        return False


def _col_letra(n: int) -> str:
    """Converte índice de coluna (1-based) em letra de planilha: 1 -> A, 27 -> AA."""
    res = ""
    while n > 0:
        n, resto = divmod(n - 1, 26)
        res = chr(65 + resto) + res
    return res


def _registrar_backup(worksheet_name: str, valores: list[list[str]]) -> None:
    """Guarda em sessão o conteúdo anterior à gravação, para download de segurança."""
    try:
        import csv
        import io

        buffer = io.StringIO()
        escritor = csv.writer(buffer, delimiter=";")
        escritor.writerows(valores)
        st.session_state["_backup_planilha"] = {
            "aba": worksheet_name,
            "quando": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "csv": buffer.getvalue(),
        }
    except Exception:
        # Backup é uma proteção adicional: se falhar, a gravação segue normalmente.
        pass


def _gravar_gspread(worksheet_name: str, df: pd.DataFrame) -> bool:
    """
    Sobrescreve uma aba do Google Sheets **sem apagar dados antes de gravar**.

    Fluxo seguro (não destrutivo):

    1. Lê o conteúdo atual da aba (backup em sessão, disponível para download).
    2. Grava o novo conteúdo por cima da área correspondente.
    3. Somente **após** o sucesso da gravação, remove eventuais linhas/colunas
       remanescentes de uma versão maior.

    Assim, uma falha de rede/API no passo 2 deixa a aba exatamente como estava —
    antes, o `ws.clear()` prévio esvaziava a aba e uma falha em seguida causava
    perda total dos dados.
    """
    try:
        df_api = Safe.para_api(df)
        if df_api.empty:
            return False
        ws = _gspread_sheet(worksheet_name)
        dados = [df_api.columns.tolist()] + df_api.values.tolist()
        num_linhas, num_colunas = len(dados), len(df_api.columns)
        intervalo = f"A1:{_col_letra(num_colunas)}{num_linhas}"

        # 1) Snapshot do estado atual (para backup/auditoria)
        try:
            anteriores = ws.get_all_values()
        except Exception:
            anteriores = []
        _registrar_backup(worksheet_name, anteriores)

        # 2) Gravação sobreposta — nada é apagado antes de dar certo
        try:
            ws.update(
                range_name=intervalo,
                values=dados,
                value_input_option="USER_ENTERED",
            )
        except TypeError:
            ws.update(
                intervalo,
                dados,
                value_input_option="USER_ENTERED",
            )

        # 3) Limpeza do excedente, apenas depois da gravação bem-sucedida
        linhas_anteriores = len(anteriores)
        colunas_anteriores = max((len(linha) for linha in anteriores), default=0)
        if linhas_anteriores > num_linhas:
            faixa = (
                f"A{num_linhas + 1}:"
                f"{_col_letra(max(num_colunas, colunas_anteriores))}{linhas_anteriores}"
            )
            try:
                ws.batch_clear([faixa])
            except Exception as exc:
                # Dados novos já estão salvos; sobras não invalidam a gravação.
                st.info(f"ℹ️ Gravação concluída; não foi possível limpar sobras ({exc}).")
        elif colunas_anteriores > num_colunas:
            faixa = (
                f"{_col_letra(num_colunas + 1)}1:"
                f"{_col_letra(colunas_anteriores)}{linhas_anteriores}"
            )
            try:
                ws.batch_clear([faixa])
            except Exception:
                pass

        st.cache_data.clear()
        return True
    except Exception as exc:
        st.error(f"❌ Erro ao gravar: {exc}")
        return False


class Config:
    APP_NOME = "Gestão de Ativos TOTALE"
    APP_VERSAO = "4.1.0"
    SHEET_ID = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    ABAS = {
        "ativos": "lista_ativos",
        "desligados": "desligados",
        "auditoria": "log_auditoria",
    }
    COL_ATIVOS = [
        "RE",
        "Login",
        "Técnico",
        "Monitor",
        "Base",
        "Situação",
        "Ultima_Modificacao",
    ]
    COL_DESLIG = [
        "RE",
        "Login",
        "Técnico",
        "Monitor",
        "Base",
        "Situação",
        "Ultima_Modificacao",
        "Data_Desligamento",
        "Motivo",
    ]
    COL_AUDIT = ["Data", "Usuario", "Perfil", "Acao", "Alvo", "Detalhe"]
    SITS_ATIVAS = ["ATIVO", "FÉRIAS", "INOPERANTE", "ETN", "AFASTADO"]
    SITS_SAIDA = ["DESLIGADO", "INATIVO"]
    MOTIVOS = [
        "PEDIDO DE DEMISSÃO",
        "DEMISSÃO SEM JUSTA CAUSA",
        "DEMISSÃO POR JUSTA CAUSA",
        "FIM DE CONTRATO",
        "TRANSFERÊNCIA",
        "ABANDONO DE EMPREGO",
        "OUTROS",
    ]
    CACHE_TTL = 300

    # Mapeamento de cores para o render_table_html
    CORES_SITUACAO = {
        "ATIVO": Cores.SUCESSO,
        "FÉRIAS": Cores.ATENCAO,
        "INOPERANTE": Cores.ALERTA,
        "ETN": "#7C3AED",
        "AFASTADO": Cores.NEUTRO,
        "DESLIGADO": "#374151",
        "INATIVO": "#1F2937",
    }

    @staticmethod
    def usuarios() -> dict[str, dict]:
        """
        Usuários cadastrados em `st.secrets["usuarios"]`.

        ⚠️ Nenhuma credencial fica no código-fonte: sem `secrets.toml`
        configurado o dicionário volta vazio e o acesso é negado.

        Formato esperado:

        .. code-block:: toml

            [usuarios.seu_login]
            nome  = "Seu Nome"
            role  = "admin"      # admin | supervisor | operador | leitura
            bases = []           # vazio = todas as bases
            senha = "pbkdf2_sha256$260000$<salt>$<hash>"
        """
        base: dict[str, dict] = {}
        try:
            bruto = st.secrets.get("usuarios", {})
            dados = bruto.to_dict() if hasattr(bruto, "to_dict") else dict(bruto)
        except Exception:
            return base

        for login, info in (dados or {}).items():
            try:
                registro = info.to_dict() if hasattr(info, "to_dict") else dict(info)
            except (TypeError, ValueError):
                continue
            senha = Safe.str(registro.get("senha"))
            if not senha:
                continue
            chave = Safe.lower(str(login))
            if not chave:
                continue
            bases = registro.get("bases") or []
            if isinstance(bases, str):
                bases = [bases] if bases.strip() else []
            role = Safe.lower(str(registro.get("role") or "leitura"))
            base[chave] = {
                "senha": senha,
                "nome": Safe.str(registro.get("nome")) or str(login),
                "role": role if role in ("admin", "supervisor", "operador", "leitura") else "leitura",
                "bases": [Safe.str(b) for b in list(bases) if Safe.str(b)],
            }
        return base


# ═══════════════════════════════════════════════════════════════════════════════
# [2] REPOSITÓRIO & SERVIÇOS (Lógica de negócio mantida)
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=Config.CACHE_TTL, show_spinner=False)
def _fetch(chave: str, colunas: tuple[str, ...]) -> pd.DataFrame:
    worksheet_name = Config.ABAS.get(chave, chave)
    empty = pd.DataFrame(columns=list(colunas))
    try:
        ws = _gspread_sheet(worksheet_name)
        registros = ws.get_all_records(empty2zero=False, head=1, default_blank="")
        if not registros:
            return empty
        df = pd.DataFrame(registros)
        df.columns = [Safe.str(c, f"c{i}") for i, c in enumerate(df.columns)]
        df = Safe.limpar_df(df)
        df = Safe.garantir_colunas(df, list(colunas))
        pk = list(colunas)[0]
        return df[df[pk].str.strip() != ""].reset_index(drop=True)
    except Exception as exc:
        st.warning(f"️ Erro leitura '{worksheet_name}': {exc}")
        return empty


class Repo:
    def ler(self, chave: str, cols: list[str]) -> pd.DataFrame:
        return _fetch(chave, tuple(cols)).copy()

    def gravar(self, chave: str, df: pd.DataFrame) -> bool:
        return _gravar_gspread(Config.ABAS.get(chave, chave), df)

    def hierarquia(self) -> pd.DataFrame:
        return (
            self.ler("ativos", ["Login", "Técnico", "Monitor", "Base"])
            .drop_duplicates(subset=["Login"])
            .reset_index(drop=True)
        )

    def log(
        self, usr: str, perfil: str, acao: str, alvo: str, detalhe: str = ""
    ) -> None:
        try:
            _append_gspread(
                Config.ABAS["auditoria"],
                [
                    datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    Safe.str(usr),
                    Safe.str(perfil),
                    Safe.str(acao),
                    Safe.str(alvo),
                    Safe.str(detalhe),
                ],
            )
            st.cache_data.clear()
        except Exception as exc:
            st.warning(f"⚠️ Log falhou: {exc}")


@dataclass
class Usuario:
    """Usuário autenticado nesta página e suas permissões."""

    login: str
    nome: str
    role: str
    bases: list[str] = field(default_factory=list)

    def pode(self, a: str) -> bool:
        P = {
            "admin": {"ler", "escrever", "editar", "desligar", "importar", "auditoria"},
            "supervisor": {"ler", "escrever", "editar", "desligar", "importar"},
            "operador": {"ler", "escrever", "editar"},
            "leitura": {"ler"},
        }
        return a in P.get(self.role, set())


@dataclass
class Tecnico:
    RE: str
    Login: str
    Técnico: str
    Monitor: str
    Base: str
    Situação: str
    Ultima_Modificacao: str = ""

    def normalizar(self) -> Tecnico:
        self.RE = Safe.upper(self.RE)
        self.Login = Safe.lower(self.Login)
        self.Técnico = Safe.upper(self.Técnico)
        self.Monitor = Safe.upper(self.Monitor)
        self.Base = Safe.upper(self.Base)
        self.Situação = Safe.upper(self.Situação)
        return self


class Svc:
    def __init__(self, repo: Repo):
        self.r = repo

    def _f(self, df: pd.DataFrame, usr: Usuario) -> pd.DataFrame:
        if usr.role == "admin" or not usr.bases:
            return df
        return df[df["Base"].str.upper().isin([b.upper() for b in usr.bases])]

    def ativos(self, usr: Usuario) -> pd.DataFrame:
        return self._f(self.r.ler("ativos", Config.COL_ATIVOS), usr)

    def desligados(self, usr: Usuario) -> pd.DataFrame:
        return self._f(self.r.ler("desligados", Config.COL_DESLIG), usr)

    def hierarquia(self) -> pd.DataFrame:
        return self.r.hierarquia()

    def cadastrar(self, tec: Tecnico, usr: Usuario) -> bool:
        tec.normalizar()
        df = self.r.ler("ativos", Config.COL_ATIVOS)
        if tec.RE and (df["RE"].str.upper() == tec.RE).any():
            st.error(f"RE {tec.RE} já existe.")
            return False
        tec.Ultima_Modificacao = f"{datetime.now():%d/%m/%y %H:%M} | Por {usr.login}"
        ok = self.r.gravar(
            "ativos", pd.concat([df, pd.DataFrame([asdict(tec)])], ignore_index=True)
        )
        if ok:
            self.r.log(
                usr.login, usr.role, "CADASTRO", tec.RE, f"{tec.Técnico}|{tec.Base}"
            )
        return ok

    def editar(self, re: str, campo: str, novo: str, usr: Usuario) -> bool:
        df = self.r.ler("ativos", Config.COL_ATIVOS)
        mask = df["RE"].str.upper() == Safe.upper(re)
        if not mask.any():
            st.error(f"RE {re} não encontrado.")
            return False
        ant = df.loc[mask, campo].values[0]
        df.loc[mask, campo] = Safe.str(novo)
        df.loc[mask, "Ultima_Modificacao"] = (
            f"{datetime.now():%d/%m/%y %H:%M} | Por {usr.login}"
        )
        ok = self.r.gravar("ativos", df)
        if ok:
            self.r.log(usr.login, usr.role, "EDIÇÃO", re, f"{campo}:'{ant}'→'{novo}'")
        return ok

    def desligar(self, re: str, motivo: str, usr: Usuario) -> bool:
        df_at = self.r.ler("ativos", Config.COL_ATIVOS)
        mask = df_at["RE"].str.upper() == Safe.upper(re)
        if not mask.any():
            st.error(f"RE {re} não encontrado.")
            return False
        linha = df_at[mask].copy()
        linha["Situação"] = "DESLIGADO"
        linha["Data_Desligamento"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        linha["Motivo"] = Safe.str(motivo)
        df_de = pd.concat(
            [self.r.ler("desligados", Config.COL_DESLIG), linha], ignore_index=True
        )
        df_at = df_at[~mask].reset_index(drop=True)
        ok = self.r.gravar("desligados", df_de) and self.r.gravar("ativos", df_at)
        if ok:
            self.r.log(usr.login, usr.role, "DESLIGAMENTO", re, motivo)
        return ok

    def importar(
        self, df_imp: pd.DataFrame, usr: Usuario
    ) -> tuple[int, int, list[str]]:
        df_imp = Safe.limpar_df(df_imp)
        df_at = self.r.ler("ativos", Config.COL_ATIVOS)
        exist = set(df_at["RE"].str.upper())
        novos = []
        falhas = 0
        erros = []
        for i, (_, row) in enumerate(df_imp.iterrows()):
            re = Safe.upper(row.get("RE", ""))
            if not re:
                falhas += 1
                erros.append(f"Linha {i + 2}: RE vazio")
                continue
            if re in exist:
                falhas += 1
                erros.append(f"Linha {i + 2}: RE '{re}' duplicado")
                continue
            tec = Tecnico(
                RE=re,
                Login=Safe.lower(row.get("Login", "")),
                Técnico=Safe.upper(row.get("Técnico", row.get("Tecnico", ""))),
                Monitor=Safe.upper(row.get("Monitor", "")),
                Base=Safe.upper(row.get("Base", "")),
                Situação=Safe.upper(row.get("Situação", "ATIVO")),
                Ultima_Modificacao=f"{datetime.now():%d/%m/%y %H:%M}|Import {usr.login}",
            ).normalizar()
            novos.append(asdict(tec))
            exist.add(re)
        if novos:
            self.r.gravar(
                "ativos", pd.concat([df_at, pd.DataFrame(novos)], ignore_index=True)
            )
            self.r.log(
                usr.login,
                usr.role,
                "IMPORTAÇÃO",
                f"{len(novos)}",
                f"{falhas} ignorados",
            )
        return len(novos), falhas, erros


# ═══════════════════════════════════════════════════════════════════════════════
# [3] VIEWS (Usando componentes.py)
# ═══════════════════════════════════════════════════════════════════════════════
def _regras_cor_situacao():
    """Gera as regras de cor para a coluna Situação no render_table_html."""
    return {
        "Situação": [
            (lambda x, sit=sit: x == sit, cor)
            for sit, cor in Config.CORES_SITUACAO.items()
        ]
    }


def view_dashboard(df_raw, usr):
    render_section_header("Panorama Operacional", icone="")

    with st.expander("🔎 Filtros Avançados", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        ft = c1.text_input("🔍 Nome/RE/Login", key="dash_busca")
        fb = c2.multiselect(
            "Base", sorted(df_raw["Base"].dropna().unique()), key="dash_base"
        )
        fm = c3.multiselect(
            "Monitor", sorted(df_raw["Monitor"].dropna().unique()), key="dash_monitor"
        )
        fs = c4.multiselect(
            "Situação",
            sorted(df_raw["Situação"].dropna().unique()),
            key="dash_situacao",
        )

    df = df_raw.copy()
    if ft:
        df = df[df.apply(lambda r: ft.lower() in str(r).lower(), axis=1)]
    if fb:
        df = df[df["Base"].isin(fb)]
    if fm:
        df = df[df["Monitor"].isin(fm)]
    if fs:
        df = df[df["Situação"].isin(fs)]

    if df.empty:
        render_empty_state("filtro")
        return

    tot = len(df)
    atv = (df["Situação"].str.upper() == "ATIVO").sum()
    fer = (df["Situação"].str.upper() == "FÉRIAS").sum()
    inop = (df["Situação"].str.upper() == "INOPERANTE").sum()

    k1, k2, k3, k4, k5 = st.columns(5)
    render_kpi(k1, "Total", str(tot), f"{df['Base'].nunique()} bases", "azul")
    render_kpi(
        k2, "Em Operação", str(atv), f"{atv / tot * 100:.1f}% disponível", "verde"
    )
    render_kpi(k3, "Em Férias", str(fer), "", "laranja")
    render_kpi(k4, "Inoperantes", str(inop), "", "vermelho")
    render_kpi(k5, "Monitores", str(df["Monitor"].nunique()), "", "roxo")

    st.divider()
    render_section_header(
        "Listagem de Ativos", icone="📋", badge=f"{tot} registros", badge_tipo="info"
    )

    # APLICAÇÃO DO RENDER_TABLE_HTML
    render_table_html(
        df,
        max_rows=500,
        height=500,
        color_rules=_regras_cor_situacao(),
        fmt={"RE": lambda x: f"<b>{x}</b>"},  # Exemplo de formatação extra
    )


def view_cadastro(svc, usr):
    render_section_header("Cadastrar Técnico", icone="")
    if not usr.pode("escrever"):
        st.warning("⛔ Sem permissão.")
        return

    hier = svc.hierarquia()
    bases = sorted(hier["Base"].unique()) if not hier.empty else []
    mons = sorted(hier["Monitor"].unique()) if not hier.empty else []

    with st.form("cad_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        re = c1.text_input("RE *", key="cad_re")
        nome = c1.text_input("Nome *", key="cad_nome")
        login = c1.text_input("Login *", key="cad_login")
        bi = (
            c2.selectbox("Base *", [""] + bases, key="cad_base_sel")
            if bases
            else c2.text_input("Base *", key="cad_base_txt")
        )
        mi = (
            c2.selectbox("Monitor *", [""] + mons, key="cad_monitor_sel")
            if mons
            else c2.text_input("Monitor *", key="cad_monitor_txt")
        )
        sit = c2.selectbox("Situação", Config.SITS_ATIVAS, key="cad_situacao")
        ok = st.form_submit_button(
            "💾 Salvar", type="primary", use_container_width=True
        )

    if ok:
        erros = [
            k
            for k, v in [
                ("RE", re),
                ("Nome", nome),
                ("Base", str(bi)),
                ("Monitor", str(mi)),
            ]
            if not Safe.str(v)
        ]
        if erros:
            st.error(f"⛔ Obrigatórios: {', '.join(erros)}")
        else:
            tec = Tecnico(
                Safe.upper(re),
                Safe.lower(login),
                Safe.upper(nome),
                Safe.upper(str(mi)),
                Safe.upper(str(bi)),
                sit,
            )
            with st.spinner("Salvando..."):
                if svc.cadastrar(tec, usr):
                    st.success("✅ Cadastrado!")
                    time.sleep(1)
                    st.rerun()


# ... (Mantenha as outras views view_edicao, view_desligamento, etc. usando a mesma lógica de substituição de st.dataframe por render_table_html) ...


def view_auditoria(repo, usr):
    render_section_header("Auditoria", icone="")
    if not usr.pode("auditoria"):
        st.warning("⛔ Acesso restrito.")
        return
    df = repo.ler("auditoria", Config.COL_AUDIT)
    if df.empty:
        render_empty_state("filtro")
        return

    # Filtros...
    c1, c2, c3 = st.columns(3)
    fu = c1.multiselect("Usuário:", sorted(df["Usuario"].unique()), key="aud_usuario")
    fa = c2.multiselect("Ação:", sorted(df["Acao"].unique()), key="aud_acao")
    fd = c3.text_input("Detalhe:", key="aud_detalhe")
    if fu:
        df = df[df["Usuario"].isin(fu)]
    if fa:
        df = df[df["Acao"].isin(fa)]
    if fd:
        df = df[df["Detalhe"].str.contains(fd, case=False, na=False)]

    render_table_html(
        df.iloc[::-1].reset_index(drop=True), titulo="Log de Eventos", max_rows=100
    )

    # Backup da última gravação (proteção contra sobrescrita indevida)
    backup = st.session_state.get("_backup_planilha")
    if isinstance(backup, dict) and backup.get("csv"):
        st.download_button(
            f"⬇️ Baixar backup — aba '{backup.get('aba')}' ({backup.get('quando')})",
            data=backup["csv"].encode("utf-8"),
            file_name=f"backup_{backup.get('aba')}.csv",
            mime="text/csv",
            key="btn_backup_planilha",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# [4] MAIN & LOGIN
# ═══════════════════════════════════════════════════════════════════════════════
def _init():
    for k, v in {"autenticado": False, "usuario": None}.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _segundos_bloqueio_restantes() -> int:
    """Tempo restante de bloqueio após tentativas de login repetidas."""
    restante = float(st.session_state.get("login_bloqueado_ate", 0)) - time.time()
    return int(restante) if restante > 0 else 0


def _registrar_falha_login() -> None:
    falhas = int(st.session_state.get("login_falhas", 0)) + 1
    st.session_state["login_falhas"] = falhas
    if falhas >= MAX_TENTATIVAS:
        st.session_state["login_bloqueado_ate"] = time.time() + BLOQUEIO_SEGUNDOS
        st.session_state["login_falhas"] = 0


def tela_login() -> None:
    """Tela de login desta página. Único ponto de autenticação do sistema."""
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        render_hero_totale_1(Config.APP_NOME, "Plataforma Corporativa de Gestão")

        usuarios = Config.usuarios()
        if not usuarios:
            st.error("⛔ Nenhum usuário configurado — o acesso está bloqueado.")
            st.markdown(
                "Cadastre os usuários em `.streamlit/secrets.toml` "
                "(veja `.streamlit/secrets.example.toml`).\n\n"
                "Para gerar o hash da senha:\n"
                "```bash\n"
                "python -c \"from pages.gestao_ativos import gerar_hash_senha; "
                "print(gerar_hash_senha('MinhaSenhaForte'))\"\n"
                "```"
            )
            return

        bloqueio = _segundos_bloqueio_restantes()
        if bloqueio:
            st.warning(
                f"⏳ Muitas tentativas inválidas. Aguarde {bloqueio}s para tentar novamente."
            )
            return

        with st.form("login"):
            u = st.text_input("👤 Usuário", autocomplete="username")
            p = st.text_input("🔑 Senha", type="password", autocomplete="current-password")
            ok = st.form_submit_button(
                "Entrar →", type="primary", use_container_width=True
            )

        if not ok:
            return

        chave = Safe.lower(str(u))
        dados = usuarios.get(chave)
        if not (chave and str(p)) or not dados or not _verificar_senha(p, dados["senha"]):
            _registrar_falha_login()
            st.error("❌ Credenciais inválidas.")
            return

        if _senha_precisa_migrar(dados["senha"]):
            st.warning(
                "⚠️ Sua senha está em formato legado (SHA-256 sem salt). "
                "Gere um novo hash PBKDF2 e atualize o `secrets.toml`."
            )
        st.session_state.update(
            {
                "autenticado": True,
                "usuario": Usuario(chave, dados["nome"], dados["role"], dados["bases"]),
            }
        )
        st.rerun()


def tela_principal():
    usr: Usuario = st.session_state.usuario
    repo = Repo()
    svc = Svc(repo)

    # Sidebar usando componentes.py
    render_sidebar_brand()
    render_sidebar_info(user_name=usr.nome, role=usr.role.upper())
    render_sidebar_section("☑️ Navegação")
    st.sidebar.markdown("---")

    # Botões de ação
    if st.sidebar.button("🔄 Sincronizar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.sidebar.button("🚪 Sair", use_container_width=True):
        st.session_state.update({"autenticado": False, "usuario": None})
        st.session_state.pop("login_falhas", None)
        st.rerun()

    render_sidebar_divider()
    render_sidebar_footer_info(versao=Config.APP_VERSAO)

    # Conteúdo Principal
    render_hero_totale_1(
        f"Bem-vindo, {usr.nome}!",
        "Selecione uma opção no menu ou utilize os filtros abaixo.",
    )

    with st.spinner("Carregando dados..."):
        df_ativos = svc.ativos(usr)
    if df_ativos.empty:
        render_empty_state(
            "dados",
            "Verifique a conexão com o Google Sheets ou cadastre novos ativos.",
        )
        return

    abas = st.tabs(
        ["📊 Dashboard", "👷 Cadastro", "🔍 Auditoria"]
    )  # Adicione as outras abas conforme necessário
    with abas[0]:
        view_dashboard(df_ativos, usr)
    with abas[1]:
        view_cadastro(svc, usr)
    with abas[2]:
        view_auditoria(repo, usr)


def main():
    st.set_page_config(
        page_title=Config.APP_NOME,
        page_icon="👷",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    aplicar_estilo()  # <--- APLICA O CSS DO COMPONENTES.PY
    _init()
    if not st.session_state.autenticado:
        tela_login()
    else:
        tela_principal()


if __name__ == "__main__":
    main()
