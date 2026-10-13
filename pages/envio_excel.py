"""
Central de Atualização de Dados | TOTALE

Página do app Streamlit (rodar como página em pages/ ou como main).

1. Atualização automática: selectbox na sidebar (Desligado / 1 / 5 / 15 min).
   O fragmento reexecuta sozinho no intervalo, mas a rede só é chamada de novo
   quando o intervalo venceu, na primeira carga ou no botão. Clicar em
   download não dispara outro download das fontes.
2. Fontes independentes: Produção, Consultivo e Ativos são baixadas uma a uma.
   Se uma falha, a última carga boa das outras permanece.
3. Retries HTTP + página HTML de confirmação do Drive (confirm=t e
   drive.usercontent.google.com).
4. CSV: separador inferido uma vez (Sniffer, com contagem como reserva).
5. Excel: tenta openpyxl e depois calamine.
6. Sem time.sleep + st.rerun().
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Literal

import pandas as pd
import requests
import streamlit as st

from components.saude_dados import avaliar_consistencia, avaliar_frescor
from config.settings import (
    FUSO_BR,
    TIMEOUT_HTTP_PADRAO,
    URL_ATIVOS_CSV,
    URL_CONS_DOWNLOAD,
    URL_PROD_XLSX,
)
from robo.robo_local import renderizar_robo_local
from services.google_drive_client import (
    adicionar_confirm_url,
    baixar_bytes_drive,
    criar_sessao_http,
    e_resposta_html,
    extrair_token_confirm,
    ler_csv_uma_tentativa,
    separadores_csv,
    urls_download_drive,
)

AlinhamentoColuna = Literal["top", "center", "bottom"]


def _noop(*_a: object, **_k: object) -> None:
    return None


def _insight_fb(texto: str, tipo: str = "info", **_k: object) -> None:
    del tipo
    st.info(texto)


def _kpi_fb(
    col: object,
    label: str,
    valor: object,
    sub: str = "",
    tema: str = "azul",
    **_k: object,
) -> None:
    del tema
    metric = getattr(col, "metric", None)
    if callable(metric):
        metric(label, str(valor), sub)


def _tabela_fb(df: object, **_k: object) -> None:
    st.dataframe(df, width="stretch")


def _hero_fb(**k: object) -> None:
    st.title(str(k.get("titulo", "")))


def _header_fb(*a: object, **k: object) -> None:
    titulo = a[1] if len(a) > 1 else k.get("titulo", "")
    st.markdown(f"## {titulo}")


try:
    from components.componentes import (
        aplicar_estilo,
        render_hero_totale_1,
        render_insight,
        render_kpi,
        render_section_header,
        render_table_html,
    )
    from components.sidebar import (
        render_page_sidebar_theme_selector,
        render_sidebar_brand,
    )
except Exception:  # ambiente sem o design system — o app ainda abre
    aplicar_estilo = _noop
    render_hero_totale_1 = _hero_fb
    render_insight = _insight_fb
    render_kpi = _kpi_fb
    render_page_sidebar_theme_selector = _noop  # type: ignore[assignment]
    render_section_header = _header_fb
    render_sidebar_brand = _noop
    render_table_html = _tabela_fb


class Configuracoes:
    """Central de configurações e URLs das fontes de dados."""

    URL_PROD = URL_PROD_XLSX
    URL_CONS = URL_CONS_DOWNLOAD
    URL_ATIVOS = URL_ATIVOS_CSV

    VAZIOS = {"-", "nan", "None", "", "NaN", "nat", "NAT", "<NA>", "null", "NULL"}
    PADRAO_VAZIO = r"^(?:-|nan|none|na|n/a|<na>|nat|null)$"
    _RE_VAZIO = re.compile(PADRAO_VAZIO, re.IGNORECASE)

    FUSO = FUSO_BR
    TIMEOUT = TIMEOUT_HTTP_PADRAO
    FOLGA_TIMER_SEG = 2
    ABAS_PROD: list[str] | None = None  # None = todas as abas
    ABA_PROD_UI = "Prod"
    COLUNAS_ATIVOS = ("Monitor", "U.N.", "Base")

    INTERVALOS_AUTOMATICOS = {
        "Desligado": 0,
        "A cada 1 minuto": 60,
        "A cada 5 minutos": 300,
        "A cada 15 minutos": 900,
    }

    @classmethod
    def vazio_texto(cls, valor: object) -> str:
        if valor is None or (isinstance(valor, float) and math.isnan(valor)):
            return ""
        texto = str(valor).strip()
        return "" if cls._RE_VAZIO.fullmatch(texto) is not None else texto


@dataclass
class StatusFonte:
    """Estado da última tentativa/sucesso de cada fonte."""

    nome: str
    ok: bool = False
    linhas: int = 0
    ultima_tentativa: datetime | None = None
    ultimo_sucesso: datetime | None = None
    erro: str | None = None

    def rotulo(self) -> str:
        quando = (
            self.ultimo_sucesso.strftime("%d/%m às %H:%M")
            if self.ultimo_sucesso
            else "nunca"
        )
        if self.ok:
            return f"{self.nome} • {_fmt_int(self.linhas)} linhas • ok em {quando}"
        if self.ultimo_sucesso is None:
            erro = f" • {_erro_curto(self.erro, 180)}" if self.erro else ""
            return f"{self.nome} • sem carga{erro}"
        erro = f" • {_erro_curto(self.erro, 180)}" if self.erro else ""
        return f"{self.nome} • usando dados de {quando}{erro}"


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _erro_curto(erro: str | None, limite: int = 120) -> str:
    if not erro:
        return "falha na leitura"
    texto = " ".join(erro.split())
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1] + "…"


def _intervalo_vencido(
    ultima: datetime | None,
    agora: datetime,
    intervalo_seg: int,
) -> bool:
    """True se a automação deve baixar de novo. Widget interaction não entra aqui."""
    if intervalo_seg <= 0:
        return False
    if not isinstance(ultima, datetime):
        return True
    ref = (
        ultima
        if ultima.tzinfo is not None
        else ultima.replace(tzinfo=Configuracoes.FUSO)
    )
    decorrido = (agora - ref).total_seconds()
    return decorrido + Configuracoes.FOLGA_TIMER_SEG >= intervalo_seg


class ProcessadorDeDados:
    """ETL e regras de negócio — sem dependência de estado Streamlit."""

    @staticmethod
    def _como_serie(valor: object, index: pd.Index) -> pd.Series:
        if isinstance(valor, pd.Series):
            return valor
        return pd.Series("", index=index, dtype="object")

    @classmethod
    def _normalizar_serie(cls, serie: pd.Series) -> pd.Series:
        texto = serie.fillna("").astype(str).str.strip()
        return texto.where(~texto.str.match(Configuracoes.PADRAO_VAZIO, case=False), "")

    @staticmethod
    def _login_chave(valor: object) -> str:
        """Chave de join: sem sufixo de float ('12345.0'), caixa alta, sem vazio."""
        if valor is None or (isinstance(valor, float) and math.isnan(valor)):
            return ""
        s = str(valor).strip().upper()
        s = re.sub(r"\.0+$", "", s)
        if re.fullmatch(Configuracoes.PADRAO_VAZIO, s, flags=re.IGNORECASE):
            return ""
        return s

    @staticmethod
    def urls_download(url: str) -> list[str]:
        """URL principal + usercontent com confirm=t (pula o HTML do Drive)."""
        return urls_download_drive(url)

    @staticmethod
    def _e_html(conteudo: bytes, content_type: str) -> bool:
        return e_resposta_html(conteudo, content_type)

    @staticmethod
    def _token_confirm(corpo: bytes) -> str | None:
        return extrair_token_confirm(corpo)

    @classmethod
    def _com_confirm(cls, url: str, token: str) -> str:
        return adicionar_confirm_url(url, token)

    @classmethod
    def baixar_bytes(cls, sess: requests.Session, url: str) -> bytes:
        """Baixa o arquivo; segue o confirm do Drive e o fallback usercontent."""
        return baixar_bytes_drive(sess, url, timeout=Configuracoes.TIMEOUT)

    @staticmethod
    def criar_sessao() -> requests.Session:
        return criar_sessao_http()

    _DELIMITADORES_CSV = (",", ";", "\t", "|")

    @classmethod
    def _separadores_csv(cls, texto: str) -> list[str]:
        """Sniffer primeiro (respeita aspas); contagem só como desempate."""
        return separadores_csv(texto)

    @classmethod
    def _ler_csv_uma(cls, conteudo: bytes, sep: str, enc: str) -> pd.DataFrame:
        return ler_csv_uma_tentativa(conteudo, sep, enc)

    @classmethod
    def ler_csv_remoto(cls, conteudo: bytes) -> pd.DataFrame:
        if not conteudo or not conteudo.strip():
            raise ValueError("O arquivo remoto veio vazio.")
        if cls._e_html(conteudo, ""):
            raise ValueError("O remoto devolveu HTML em vez de CSV.")

        amostra = conteudo[:16384]
        melhor: pd.DataFrame | None = None
        reserva_1col: pd.DataFrame | None = None
        ultimo_erro: Exception | None = None
        for enc in ("utf-8-sig", "cp1252", "latin1"):
            try:
                texto = amostra.decode(enc)
            except UnicodeDecodeError:
                continue
            for sep in cls._separadores_csv(texto):
                try:
                    df = cls._ler_csv_uma(conteudo, sep, enc)
                except Exception as e:
                    ultimo_erro = e
                    continue
                if df.shape[1] > 1:
                    melhor = df
                    break
                if reserva_1col is None and df.shape[1] == 1:
                    reserva_1col = df
            if melhor is not None:
                break
            if reserva_1col is not None and not any(
                texto.count(s) > 0 for s in cls._DELIMITADORES_CSV
            ):
                melhor = reserva_1col
                break

        if melhor is None and reserva_1col is not None:
            melhor = reserva_1col
        if melhor is None:
            raise ValueError(
                f"Nenhum combinado de encoding/separador produziu colunas: {ultimo_erro}"
            )
        melhor.columns = pd.Index(
            [str(c).strip().lstrip("\ufeff") for c in melhor.columns]
        )
        return melhor

    @classmethod
    def ler_excel_remoto(cls, conteudo: bytes) -> dict[str, pd.DataFrame]:
        if not conteudo:
            raise ValueError("O arquivo remoto veio vazio.")
        if cls._e_html(conteudo, ""):
            raise ValueError("O remoto devolveu HTML em vez de Excel.")
        erros: list[str] = []
        for engine in ("openpyxl", "calamine"):
            try:
                bruto = pd.read_excel(
                    BytesIO(conteudo),
                    sheet_name=Configuracoes.ABAS_PROD,
                    engine=engine,
                )
            except ImportError as e:
                erros.append(f"{engine}: não instalado ({e})")
                continue
            except Exception as e:
                erros.append(f"{engine}: {type(e).__name__}: {e}")
                continue
            if isinstance(bruto, dict):
                return {
                    str(k): v for k, v in bruto.items() if isinstance(v, pd.DataFrame)
                }
            if isinstance(bruto, pd.DataFrame):
                return {"Prod": bruto}
            erros.append(f"{engine}: retorno inesperado")
        raise RuntimeError(
            "Não foi possível ler o Excel da Produção: "
            + " | ".join(erros)
            + " → pip install openpyxl"
        )

    @classmethod
    def _separar_internet_tv(
        cls, internet_bruta: pd.Series
    ) -> tuple[pd.Series, pd.Series]:
        """Separa TV embutida depois do ponto."""
        bruto = cls._normalizar_serie(internet_bruta)
        partes = bruto.str.split(".", n=1, expand=True)
        primeira = cls._normalizar_serie(cls._como_serie(partes[0], bruto.index))
        if partes.shape[1] < 2:
            return primeira, pd.Series("", index=bruto.index, dtype="object")

        segunda = cls._normalizar_serie(cls._como_serie(partes[1], bruto.index))
        tem_letra = segunda.str.contains(r"[A-Za-z]", na=False)
        comeca_digito = segunda.str.match(r"\d", na=False)
        parece_tv = tem_letra & ~comeca_digito
        decimal_puro = segunda.str.fullmatch(r"\d+", na=False)
        preservar = segunda.ne("") & ~decimal_puro & ~parece_tv
        internet = primeira.where(~preservar, bruto)
        tv = segunda.where(parece_tv, "")
        return internet, tv

    @classmethod
    def tratar_planos(cls, df: pd.DataFrame) -> pd.DataFrame:
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df

        df = df.copy()
        internet_limpa, tv_embutida = cls._separar_internet_tv(df["PLANO INTERNET"])
        tv_original = cls._normalizar_serie(df["PLANO TV"]).replace(
            "SERVIÇOS AVANÇADOS", "CLARO TV+ BOX"
        )
        tv_final = tv_original.mask(tv_original.eq(""), tv_embutida)

        tem_tv = tv_final.ne("")
        tem_net = internet_limpa.ne("")
        df["QTDE_CONSULTIVO"] = tem_tv.astype(int) + tem_net.astype(int)

        tipo_servico = pd.Series("Sem Tipo", index=df.index, dtype="object")
        mask_ambos = tem_tv & tem_net
        mask_tv = tem_tv & ~tem_net
        mask_net = ~tem_tv & tem_net
        tipo_servico.loc[mask_ambos] = (
            tv_final.loc[mask_ambos] + " & " + internet_limpa.loc[mask_ambos]
        )
        tipo_servico.loc[mask_tv] = tv_final.loc[mask_tv]
        tipo_servico.loc[mask_net] = internet_limpa.loc[mask_net]

        df["TIPO SERVIÇO"] = tipo_servico
        df["PLANO TV"] = tv_final
        df["PLANO INTERNET"] = internet_limpa
        return df

    @classmethod
    def processar_quantidades(cls, cons: pd.DataFrame) -> pd.DataFrame:
        cons = cons.copy()
        if "OBSERVACAO" in cons.columns:
            obs = cons["OBSERVACAO"].fillna("").astype(str)
            # Extrai listas temporárias para contagem
            produtos_encontrados = obs.str.findall(r"\b\d{9,12}\b")
            cons["QTDE_PRODUTOS"] = produtos_encontrados.map(
                lambda x: len(x) if isinstance(x, (list, tuple)) else 0
            ).fillna(0).astype(int)
            # Salva como string delimitada por vírgula (evita list não-hashável no DataFrame)
            cons["LISTA_PRODUTOS"] = produtos_encontrados.map(
                lambda x: ", ".join(x) if isinstance(x, (list, tuple)) else ""
            )
        else:
            cons["LISTA_PRODUTOS"] = ""
            cons["QTDE_PRODUTOS"] = 0

        if "TIPO SERVIÇO" in cons.columns:
            tipo_servico = cons["TIPO SERVIÇO"].fillna("").astype(str)
        else:
            tipo_servico = pd.Series("", index=cons.index, dtype="object")
        qtde_prod = cons["QTDE_PRODUTOS"].fillna(0).astype(int)

        tem_tv_bool = tipo_servico.str.contains("TV", case=False, regex=False, na=False)
        tem_virtua_bool = tipo_servico.str.contains(
            r"MEGA|GIGA", case=False, regex=True, na=False
        )
        is_combinado = tipo_servico.str.contains(
            "&", case=False, regex=False, na=False
        ) | (tem_tv_bool & tem_virtua_bool)
        tem_tv = tem_tv_bool.astype(int)
        tem_virtua = tem_virtua_bool.astype(int)
        cons["QTDE_TV"] = (tem_tv * qtde_prod).mask(is_combinado, tem_tv).astype(int)
        cons["QTDE_VIRTUA"] = (
            (tem_virtua * qtde_prod).mask(is_combinado, tem_virtua).astype(int)
        )
        cons["QTDE_MESH"] = (
            (cons["QTDE_PRODUTOS"] - cons["QTDE_TV"] - cons["QTDE_VIRTUA"])
            .clip(lower=0)
            .astype(int)
        )
        return cons

    @classmethod
    def merge_ativos(cls, cons: pd.DataFrame, ativos: pd.DataFrame) -> pd.DataFrame:
        if (
            ativos.empty
            or "Login" not in ativos.columns
            or "LOGIN NETSALES" not in cons.columns
        ):
            return cons

        cols = [
            c for c in ("Login", *Configuracoes.COLUNAS_ATIVOS) if c in ativos.columns
        ]
        ativos_limpo = ativos.loc[:, cols].dropna(subset=["Login"]).copy()
        ativos_limpo["Login_JOIN"] = ativos_limpo["Login"].map(cls._login_chave)
        ativos_limpo = ativos_limpo.loc[ativos_limpo["Login_JOIN"].ne("")]
        ativos_limpo = ativos_limpo.drop_duplicates(subset=["Login_JOIN"], keep="first")
        for c in Configuracoes.COLUNAS_ATIVOS:
            if c in ativos_limpo.columns:
                ativos_limpo[c] = ativos_limpo[c].map(Configuracoes.vazio_texto)
                ativos_limpo[c] = ativos_limpo[c].where(ativos_limpo[c].ne(""), pd.NA)

        cons = cons.copy()
        cons["Login_JOIN"] = cons["LOGIN NETSALES"].map(cls._login_chave)
        merged = pd.merge(
            cons,
            ativos_limpo.drop(columns=["Login"]),
            on="Login_JOIN",
            how="left",
            suffixes=("", "_ATIVOS"),
        ).drop(columns=["Login_JOIN"])

        for c in Configuracoes.COLUNAS_ATIVOS:
            alt = f"{c}_ATIVOS"
            if alt in merged.columns:
                atual = (
                    merged[c].map(Configuracoes.vazio_texto)
                    if c in merged.columns
                    else pd.Series("", index=merged.index, dtype="object")
                )
                extra = merged[alt].map(Configuracoes.vazio_texto)
                merged[c] = atual.mask(atual.eq(""), extra)
                merged = merged.drop(columns=[alt])
            if c in merged.columns:
                merged[c] = (
                    merged[c]
                    .map(Configuracoes.vazio_texto)
                    .replace("", "Não Identificado")
                )
        return merged

    _sessao = criar_sessao
    _processar_quantidades = processar_quantidades
    _merge_ativos = merge_ativos


FonteFn = Callable[[requests.Session], pd.DataFrame | dict[str, pd.DataFrame]]


def _status(nome: str) -> StatusFonte:
    stats = st.session_state.setdefault("status_fontes", {})
    if not isinstance(stats, dict):
        stats = {}
        st.session_state["status_fontes"] = stats
    atual = stats.get(nome)
    if not isinstance(atual, StatusFonte):
        atual = StatusFonte(nome=nome)
        stats[nome] = atual
        st.session_state["status_fontes"] = stats
    return atual


def _salvar_status(stf: StatusFonte) -> None:
    stats = st.session_state.setdefault("status_fontes", {})
    if not isinstance(stats, dict):
        stats = {}
    stats[stf.nome] = stf
    st.session_state["status_fontes"] = stats


def _contar_linhas(resultado: object) -> int:
    if isinstance(resultado, pd.DataFrame):
        return len(resultado)
    if isinstance(resultado, Mapping):
        return sum(len(v) for v in resultado.values() if isinstance(v, pd.DataFrame))
    return 0


def _baixar_producao(sess: requests.Session) -> dict[str, pd.DataFrame]:
    return ProcessadorDeDados.ler_excel_remoto(
        ProcessadorDeDados.baixar_bytes(sess, Configuracoes.URL_PROD)
    )


def _baixar_consultivo(sess: requests.Session) -> pd.DataFrame:
    return ProcessadorDeDados.ler_csv_remoto(
        ProcessadorDeDados.baixar_bytes(sess, Configuracoes.URL_CONS)
    )


def _baixar_ativos(sess: requests.Session) -> pd.DataFrame:
    return ProcessadorDeDados.ler_csv_remoto(
        ProcessadorDeDados.baixar_bytes(sess, Configuracoes.URL_ATIVOS)
    )


def executar_sincronizacao(
    sess: requests.Session | None = None,
) -> dict[str, StatusFonte]:
    sess = sess or ProcessadorDeDados.criar_sessao()
    agora = datetime.now(Configuracoes.FUSO)
    st.session_state["ultima_tentativa_sync"] = agora

    fontes: list[tuple[str, FonteFn]] = [
        ("Produção", _baixar_producao),
        ("Consultivo", _baixar_consultivo),
        ("Ativos", _baixar_ativos),
    ]
    baixados: dict[str, pd.DataFrame | dict[str, pd.DataFrame]] = {}
    for nome, fn in fontes:
        stf = _status(nome)
        sucesso_anterior = stf.ultimo_sucesso
        linhas_anteriores = stf.linhas
        stf.ultima_tentativa = agora
        try:
            resultado = fn(sess)
        except Exception as e:
            stf.ok = False
            stf.erro = f"{type(e).__name__}: {e}"
            stf.ultimo_sucesso = sucesso_anterior
            stf.linhas = linhas_anteriores
            _salvar_status(stf)
            continue
        baixados[nome] = resultado
        if nome == "Consultivo":
            st.session_state["dados_cons_bruto"] = resultado
            continue
        stf.ok = True
        stf.erro = None
        stf.linhas = _contar_linhas(resultado)
        stf.ultimo_sucesso = agora
        _salvar_status(stf)

    if "Produção" in baixados:
        st.session_state["dados_prod"] = baixados["Produção"]
    if "Ativos" in baixados:
        st.session_state["dados_ativos"] = baixados["Ativos"]

    bruto = st.session_state.get("dados_cons_bruto")
    if isinstance(bruto, pd.DataFrame) and (
        "Consultivo" in baixados or "Ativos" in baixados
    ):
        stf = _status("Consultivo")
        sucesso_anterior = stf.ultimo_sucesso
        linhas_anteriores = stf.linhas
        try:
            _processar_consultivo(bruto)
        except Exception as e:
            stf.ok = False
            stf.erro = f"{type(e).__name__}: {e}"
            stf.ultimo_sucesso = sucesso_anterior
            stf.linhas = linhas_anteriores
            _salvar_status(stf)
        else:
            if "Consultivo" in baixados or stf.ultimo_sucesso is None:
                stf.ok = True
                stf.erro = None
                stf.linhas = len(bruto)
                stf.ultimo_sucesso = agora
                _salvar_status(stf)

    stats = _mapa_status()
    if any(s.ok for s in stats.values()):
        st.session_state["ultima_atualizacao"] = agora
    return stats


def _processar_consultivo(cons: object) -> None:
    if not isinstance(cons, pd.DataFrame) or cons.empty:
        st.session_state["dados_cons"] = {"Consultivo": pd.DataFrame()}
        return
    cons = ProcessadorDeDados.tratar_planos(cons)
    cons = ProcessadorDeDados.processar_quantidades(cons)
    ativos = st.session_state.get("dados_ativos")
    if not isinstance(ativos, pd.DataFrame):
        ativos = pd.DataFrame()
    cons = ProcessadorDeDados.merge_ativos(cons, ativos)
    st.session_state["dados_cons"] = {"Consultivo": cons}


def _mapa_status() -> dict[str, StatusFonte]:
    bruto = st.session_state.get("status_fontes", {})
    if not isinstance(bruto, dict):
        return {}
    return {str(k): v for k, v in bruto.items() if isinstance(v, StatusFonte)}


def _resolver_aba(
    dados: Mapping[str, pd.DataFrame],
    nome_aba: str | None,
) -> tuple[pd.DataFrame, str | None]:
    if not dados:
        return pd.DataFrame(), "A planilha não tem abas."
    if not nome_aba:
        return next(iter(dados.values())), None
    if nome_aba in dados:
        return dados[nome_aba], None
    alvo = nome_aba.casefold()
    for nome, df in dados.items():
        if str(nome).casefold() == alvo:
            return df, None
    nome, df = next(iter(dados.items()))
    return (
        df,
        f"Aba '{nome_aba}' não encontrada. Exibindo '{nome}'. Disponíveis: {', '.join(dados)}.",
    )


def _obter_dataframe(
    chave_state: str, nome_aba: str | None = None
) -> tuple[pd.DataFrame, str | None]:
    dados = st.session_state.get(chave_state)
    if dados is None:
        return pd.DataFrame(), None
    if isinstance(dados, dict):
        frames = {str(k): v for k, v in dados.items() if isinstance(v, pd.DataFrame)}
        if not frames:
            return pd.DataFrame(), None
        return _resolver_aba(frames, nome_aba)
    if isinstance(dados, pd.DataFrame):
        return dados, None
    return pd.DataFrame(), None


def _colunas(
    larguras: list[float],
    alinhamento: AlinhamentoColuna | None = None,
) -> list:
    if alinhamento is None:
        return list(st.columns(larguras))
    try:
        return list(st.columns(larguras, vertical_alignment=alinhamento))
    except TypeError:
        return list(st.columns(larguras))


def _sanitizar_para_analise(df: pd.DataFrame) -> pd.DataFrame:
    """Garante que colunas com list/dict/set sejam convertidas em string para não travar .duplicated()."""
    if df.empty:
        return df
    df_copia = df.copy()
    for col in df_copia.columns:
        if df_copia[col].dtype == "object":
            amostra = df_copia[col].dropna().head(15)
            if any(isinstance(v, (list, dict, set, tuple)) for v in amostra):
                df_copia[col] = df_copia[col].map(
                    lambda x: (
                        ", ".join(x)
                        if isinstance(x, (list, tuple, set))
                        else str(x) if isinstance(x, dict) else x
                    )
                )
    return df_copia


def _frames_carregados() -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for fonte, chave in (
        ("Produção", "dados_prod"),
        ("Consultivo", "dados_cons"),
        ("Ativos", "dados_ativos"),
    ):
        dados = st.session_state.get(chave)
        if isinstance(dados, pd.DataFrame):
            frames[fonte] = _sanitizar_para_analise(dados)
        elif isinstance(dados, dict):
            partes = [
                frame for frame in dados.values() if isinstance(frame, pd.DataFrame)
            ]
            if partes:
                frames[fonte] = _sanitizar_para_analise(
                    pd.concat(partes, ignore_index=True, sort=False)
                )
    return frames


def _renderizar_status_fontes() -> None:
    stats = _mapa_status()
    if not stats:
        render_insight("Os dados ainda não foram carregados nesta sessão.", "alerta")
        return

    render_section_header(
        "🩺", "Saúde dos dados", "Frescor da sincronização e consistência estrutural"
    )
    frames = _frames_carregados()
    cols = st.columns(len(stats))
    for col, stf in zip(cols, stats.values()):
        estado_frescor, frescor = avaliar_frescor(stf.ultimo_sucesso, stf.ok)
        estado_consistencia, consistencia = avaliar_consistencia(frames.get(stf.nome))
        icones = {"ok": "🟢", "alerta": "🟡", "critico": "🔴"}
        with col:
            with st.container(border=True):
                st.markdown(f"**{stf.nome}**")
                st.caption(f"{_fmt_int(stf.linhas)} linhas na última sincronização")
                st.markdown(f"{icones[estado_frescor]} **Frescor:** {frescor}")
                st.markdown(
                    f"{icones[estado_consistencia]} **Consistência:** {consistencia}"
                )
                if stf.erro:
                    st.caption(_erro_curto(stf.erro, 300))
    st.caption(
        "Frescor: verde até 15 min, amarelo até 60 min ou após falha recente, vermelho acima disso/sem sucesso. "
        "Consistência estrutural verifica registros, colunas vazias e duplicatas; não substitui validação de negócio."
    )


def _render_sidebar_status() -> None:
    stats = _mapa_status()
    with st.sidebar:
        st.markdown("---")
        if not stats:
            st.caption("Fontes ainda não consultadas nesta sessão.")
            return
        render_section_header("📡", "Status das Fontes", "")
        for stf in stats.values():
            icone = "🟢" if stf.ok else "🔴"
            st.markdown(f"{icone} {stf.rotulo()}")


def _render_banner() -> None:
    ultima = st.session_state.get("ultima_atualizacao")
    tentativa = st.session_state.get("ultima_tentativa_sync")
    stats = _mapa_status()
    falhou = [s.nome for s in stats.values() if not s.ok]
    if isinstance(ultima, datetime):
        texto = (
            "Última sincronização com alguma fonte ok em: "
            f"**{ultima.strftime('%d/%m/%Y às %H:%M:%S')}**"
        )
        if falhou:
            texto += f". Falha nesta leitura: **{', '.join(falhou)}**."
        render_insight(texto, "ok" if not falhou else "alerta")
        return
    if isinstance(tentativa, datetime):
        render_insight(
            "A última tentativa falhou em "
            f"**{tentativa.strftime('%d/%m/%Y às %H:%M:%S')}** e não há carga anterior.",
            "alerta",
        )
        return
    render_insight("Os dados ainda não foram carregados nesta sessão.", "alerta")


def _deve_sincronizar(intervalo_seg: int, forcado: bool) -> bool:
    if forcado or not st.session_state.get("sync_iniciada", False):
        return True
    ultima = st.session_state.get("ultima_tentativa_sync")
    if not isinstance(ultima, datetime):
        ultima = None
    return _intervalo_vencido(
        ultima,
        datetime.now(Configuracoes.FUSO),
        intervalo_seg,
    )


def _detalhes_falha() -> None:
    falhas = [s for s in _mapa_status().values() if s.erro]
    if not falhas:
        return
    with st.expander("Detalhes das falhas"):
        for stf in falhas:
            st.markdown(f"**{stf.nome}**")
            st.code(stf.erro or "")


def _painel_dados(intervalo_seg: int) -> None:
    tem_dados_em_sessao = any(
        st.session_state.get(k) is not None
        for k in ("dados_prod", "dados_cons", "dados_ativos")
    )
    col_status, col_btn = _colunas([3, 1], "center")
    with col_btn:
        clicou = st.button(
            "🔄 Sincronizar Agora",
            width="stretch",
            type="primary",
            key="btn_sincronizar_dados",
        )

    if _deve_sincronizar(intervalo_seg, forcado=clicou):
        notificar = clicou or not st.session_state.get("sync_iniciada", False)
        try:
            with st.status(
                (
                    "🔄 Baixando e processando dados..."
                    if tem_dados_em_sessao
                    else "🔄 Primeira carga das bases..."
                ),
                expanded=notificar,
            ) as status_box:
                st.write("Conectando aos servidores do Google Drive...")
                stats = executar_sincronizacao()
                st.write("Aplicando regras de negócio e relacionamentos...")
                ok = [s.nome for s in stats.values() if s.ok]
                falhou = [s.nome for s in stats.values() if not s.ok]
                if ok and not falhou:
                    status_box.update(
                        label="Bases sincronizadas com sucesso!",
                        state="complete",
                        expanded=False,
                    )
                    if notificar:
                        st.toast("Bases atualizadas com sucesso!", icon="✅")
                elif ok:
                    status_box.update(
                        label=f"Parcial: {', '.join(ok)} ok • {', '.join(falhou)} falhou",
                        state="complete",
                        expanded=False,
                    )
                    if notificar:
                        st.toast(
                            f"Atualização parcial: {', '.join(falhou)} falhou",
                            icon="⚠️",
                        )
                else:
                    status_box.update(
                        label="Falha em todas as fontes. Veja os detalhes abaixo.",
                        state="error",
                        expanded=True,
                    )
        except Exception as e:
            st.error(f"❌ Falha na sincronização: {e}")
            with st.expander("🔍 Detalhes do Erro"):
                st.exception(e)
        finally:
            st.session_state["sync_iniciada"] = True

    with col_status:
        _render_banner()

    if intervalo_seg > 0:
        proxima = _proxima_execucao(intervalo_seg)
        st.caption(
            f"🔁 Atualização automática a cada {intervalo_seg // 60} min "
            "(enquanto esta aba estiver aberta). "
            f"Próxima leitura ≈ {proxima.strftime('%H:%M:%S')}. "
            "Interagir com a página não baixa de novo antes disso."
        )

    _renderizar_status_fontes()
    _detalhes_falha()
    _render_sidebar_status()

    df_prod, aviso_prod = _obter_dataframe("dados_prod", Configuracoes.ABA_PROD_UI)
    df_cons, _aviso_cons = _obter_dataframe("dados_cons", "Consultivo")
    tem_dados = len(df_prod) > 0 or len(df_cons) > 0
    if not tem_dados:
        if st.session_state.get("sync_iniciada"):
            render_insight(
                "A sincronização rodou, mas nenhuma base ficou disponível. "
                "Veja o status das fontes.",
                "alerta",
            )
        else:
            render_insight(
                "Clique em **Sincronizar Agora** para carregar e visualizar as bases de dados.",
                "acao",
            )
        return

    total_equip = (
        int(df_cons["QTDE_PRODUTOS"].fillna(0).sum())
        if "QTDE_PRODUTOS" in df_cons.columns and len(df_cons) > 0
        else 0
    )
    media_servicos = (
        float(df_cons["QTDE_CONSULTIVO"].fillna(0).mean())
        if "QTDE_CONSULTIVO" in df_cons.columns and len(df_cons) > 0
        else 0.0
    )

    k1, k2, k3, k4 = st.columns(4)
    render_kpi(
        k1, "Registros Produção", _fmt_int(len(df_prod)), "Base Produção", "azul"
    )
    render_kpi(k2, "Base Consultiva", _fmt_int(len(df_cons)), "Processados", "laranja")
    render_kpi(
        k3, "Total Equipamentos", _fmt_int(total_equip), "Detectados em OBS", "verde"
    )
    render_kpi(
        k4, "Serviços / Venda", f"{media_servicos:.2f}", "Média de penetração", "cinza"
    )

    tab_p, tab_c = st.tabs(["📊 Produção (Preview)", "📋 Consultivo Processado"])
    with tab_p:
        render_section_header("📊", "Base de Produção", "Primeiros 50 registros")
        if aviso_prod:
            render_insight(aviso_prod, "alerta")
        _preview_e_download(
            df_prod,
            "producao",
            "download_producao",
            "Aba de Produção vazia ou não encontrada.",
        )
    with tab_c:
        render_section_header("📋", "Base Consultiva Detalhada", "Processado")
        _preview_e_download(
            df_cons, "consultivo", "download_consultivo", "Base consultiva vazia."
        )


def _preview_e_download(df: pd.DataFrame, prefixo: str, key: str, vazio: str) -> None:
    if len(df) == 0:
        render_insight(vazio, "alerta")
        return
    render_table_html(df.head(50), max_rows=50, colunas_num=[], height=360)
    st.download_button(
        "⬇️ Baixar base completa (.csv)",
        df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"{prefixo}_{datetime.now(Configuracoes.FUSO):%Y%m%d_%H%M}.csv",
        mime="text/csv",
        key=key,
    )


def _proxima_execucao(intervalo_seg: int) -> datetime:
    agora = datetime.now(Configuracoes.FUSO)
    ultima = st.session_state.get("ultima_tentativa_sync")
    if isinstance(ultima, datetime):
        ref = (
            ultima
            if ultima.tzinfo is not None
            else ultima.replace(tzinfo=Configuracoes.FUSO)
        )
        return ref + timedelta(seconds=intervalo_seg)
    return agora + timedelta(seconds=intervalo_seg)


def _intervalo_da_sidebar() -> int:
    modo = st.session_state.get("modo_autosync", "A cada 5 minutos")
    if not isinstance(modo, str):
        return 300
    return Configuracoes.INTERVALOS_AUTOMATICOS.get(modo, 300)


def _painel_fragmento() -> None:
    _painel_dados(_intervalo_da_sidebar())


def _pipeline_robo_local(
    df_local: pd.DataFrame,
    _df_gsheets: pd.DataFrame,
) -> pd.DataFrame:
    df = df_local.copy()
    df.columns = [str(col).strip().upper() for col in df.columns]
    st.session_state["dados_totale"] = df
    st.session_state["df_memoria"] = df
    return df


def _pasta_padrao_robo_local() -> str:
    pasta = Path(__file__).resolve().parents[1] / "robo" / "dados"
    pasta.mkdir(parents=True, exist_ok=True)
    return str(pasta)


def _painel_saida_robo_local() -> None:
    render_section_header(
        "🤖", "Robô local", "Saída do arquivo mais recente na pasta monitorada"
    )
    dados = st.session_state.get("dados_totale")
    if not isinstance(dados, pd.DataFrame):
        st.info("Aguardando a detecção e o processamento de um arquivo local.")
        return

    fonte = st.session_state.get("origem_dados", "Robô Local")
    st.success(f"Dados carregados via {fonte}")
    st.dataframe(dados.head(), width="stretch")


def _rodar() -> None:
    st.set_page_config(
        page_title="Atualização de Dados | TOTALE",
        page_icon="🔁",
        layout="wide",
    )
    aplicar_estilo()
    render_page_sidebar_theme_selector()

    with st.sidebar:
        render_sidebar_brand("TOTALE", "Data Management")
        st.markdown("---")
        opcoes = list(Configuracoes.INTERVALOS_AUTOMATICOS)
        st.selectbox(
            "🔁 Atualização automática",
            opcoes,
            index=opcoes.index("A cada 5 minutos"),
            key="modo_autosync",
        )
        render_insight(
            "A atualização automática roda enquanto a aba do navegador estiver "
            "aberta. Use **Sincronizar Agora** para forçar a leitura na hora.",
            "info",
        )

    render_hero_totale_1(
        titulo="🔁 Central de Atualização",
        subtitulo=(
            "Sincronização de Produção, Consultivos e Ativos, com monitoramento "
            "de arquivos locais"
        ),
    )

    intervalo_seg = _intervalo_da_sidebar()
    if hasattr(st, "fragment"):
        st.fragment(run_every=intervalo_seg or None)(_painel_fragmento)()
    else:
        render_insight(
            "Este Streamlit não tem st.fragment: a atualização automática "
            "fica limitada ao botão manual.",
            "alerta",
        )
        _painel_dados(intervalo_seg)

    st.sidebar.markdown("---")
    renderizar_robo_local(
        etl_fn=_pipeline_robo_local,
        pasta_padrao=_pasta_padrao_robo_local(),
    )
    _painel_saida_robo_local()


if __name__ == "__main__":
    _rodar()
