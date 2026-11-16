"""
pages/previa_totale.py
======================
Prévia Diária | TOTALE — apresentação executiva para a diretoria.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Fluxo em três etapas (o mesmo roteiro operacional de sempre):

1. **Upload e cruzamento** — ANIEL, TOA (um ou três arquivos), Consultivo,
   imagem de resumo do dia (Rota Inicial) e o e-mail ``.msg`` de parados por
   supervisor. Datas divergentes entre ANIEL e TOA bloqueiam o processamento.
2. **Dados operacionais por base** — Rota Inicial, montados/parados por
   supervisor (parados já vêm preenchidos pelo e-mail) e as metas de O.S. e de
   Consultivo. Ao sincronizar, o app grava ``Historico_OS``,
   ``Historico_Consultivo``, ``Config_Equipe``, ``Historico_Equipe`` e
   ``Previas_Diarias`` na planilha do Google Sheets.
3. **Prévia executiva** — tabela única com O.S., Consultivo, produtividade,
   quebras (instalação, serviços, ND), GPON, migração, retorno WO e PME, além
   do detalhamento por base/supervisor e do download da ANIEL tratada.

Toda a regra de negócio vive em :mod:`services.previa_diaria` (camada pura,
testada sem Streamlit); esta página cuida de upload, estado e apresentação.

Observações de operação:

* ``extract-msg`` é dependência **opcional**: sem ela o e-mail ainda é varrido
  por expressão regular após decodificação bruta (latin1/UTF-16LE);
* a conexão ``gsheets`` (``st-gsheets-connection``) é importada sob demanda —
  sem a biblioteca ou sem ``secrets.toml`` o app continua abrindo e calculando
  a prévia, apenas não lê/grava na planilha;
* nunca há limpeza global do cache da sessão: a invalidação é granular em
  :func:`_ler_aba`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from components.componentes import aplicar_estilo, render_hero_totale_2, render_insight
from components.sidebar import render_page_sidebar_theme_selector
from config.settings import URL_PREVIA_DIARIA
from services import previa_diaria as previa
from services.planilhas import botao_download_planilha
from services.texto import escapar_html

st.set_page_config(
    page_title="Prévia Diária | TOTALE",
    page_icon="📆",
    layout="wide",
)

aplicar_estilo()
render_page_sidebar_theme_selector()

VERSAO_PAGINA = "1.0.0"

PASSOS: tuple[str, ...] = (
    "1. Upload de arquivos",
    "2. Dados operacionais",
    "3. Prévia executiva",
)

ABA_HIST_OS = "Historico_OS"
ABA_HIST_CONSULTIVO = "Historico_Consultivo"
ABA_CONFIG_EQUIPE = "Config_Equipe"
ABA_HIST_EQUIPE = "Historico_Equipe"
ABAS_DICIONARIOS = ("Baixas", "Pontos", "Desc_OS")
ABAS_DICIONARIOS_PONTOS = ("Pontos", "PONTOS ANIEL", "PONTOS_ANIEL", "PONTOS")

COLUNAS_HIST_OS = ("Data", "Base", "OS_Executadas", "OS_Inicial")
COLUNAS_HIST_CONSULTIVO = ("Data", "Base", "Qtd_Consultivo")
COLUNAS_CONFIG_EQUIPE = ("Base", "Supervisor", "Montados", "Parados")
COLUNAS_HIST_EQUIPE = ("Data", "Base", "Supervisor", "Montados", "Parados")
COLUNAS_PREVIA = (
    "Data",
    "Base",
    "Parados",
    "Montados",
    "Meta O.S.",
    "Projeção O.S.",
    "Meta Consultivo",
    "Projeção Consultivo",
    "Hoje Consultivo",
    "O.S. Consultivo",
    "Total O.S.",
    "O.S. Aberta",
    "Pontos",
    "Efic (%)",
    "Média O.S.",
    "O.S. Exec. (Proj)",
    "O.S. Sem Consult",
    "Quebra INS (%)",
    "Quebra SERV (%)",
    "Quebra ND (%)",
    "ND",
    "O.S. Canc.",
    "Saiu TOA",
    "Ganho O.S.",
    "GPON Total",
    "GPON Quebra (%)",
    "Migração Total",
    "Migração Quebra (%)",
    "Migração Canc.",
    "Retorno WO",
    "PME WO",
    "PME Quebra (%)",
    "PME Canc.",
)

#: Nome da aba onde cada prévia do dia é arquivada.
ABA_PREVIAS = "Previas_Diarias"

#: Colunas de O.S. que o TOA precisa fornecer para o cruzamento.
COLUNAS_UTEIS_TOA = (
    "Data",
    "Contrato",
    "Status da Atividade",
    "Motivo de Fechamento Externo",
    "Cidade",
    "Início",
    "Categorias da Capacidade",
    "Cód de Baixa 1",
    "Tipo O.S 1",
    "Total de tarefas",
)

CAMPOS_SOMAVEIS = (
    "Parados",
    "Montados",
    "Meta O.S.",
    "Projeção O.S.",
    "Meta Consultivo",
    "Projeção Consultivo",
    "Hoje Consultivo",
    "O.S. Consultivo",
    "Total O.S.",
    "O.S. Aberta",
    "Pontos",
    "O.S. Exec. (Proj)",
    "O.S. Sem Consult",
    "ND",
    "O.S. Canc.",
    "Saiu TOA",
    "Ganho O.S.",
    "GPON Total",
    "Migração Total",
    "Migração Canc.",
    "Retorno WO",
    "PME WO",
    "PME Canc.",
)


# ====================================================
# 🎨 BLOCO 1: ESTILO E ESTADO
# ====================================================
def _injetar_css() -> None:
    """CSS local da tabela da prévia (o restante vem do Design System)."""
    st.markdown(
        """
        <style>
        .previa-wrap { width: 100%; overflow-x: auto; }
        .previa-table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11px;
            text-align: center;
            margin-bottom: 1rem;
        }
        .previa-table th { border: 1px solid #7f8c8d; padding: 5px 3px; font-weight: 700; }
        .previa-table td { border: 1px solid #bdc3c7; padding: 4px 3px; }
        .th-data { background-color: #f2f4f4; color: #2c3e50; }
        .th-qtd-os { background-color: #a9dfbf; color: #145a32; }
        .th-consult { background-color: #d5dbdb; color: #212f3d; }
        .th-prod { background-color: #a0824b; color: #ffffff; }
        .th-quebra-claro { background-color: #f9e79f; color: #7d6608; }
        .th-ganho { background-color: #a9dfbf; color: #145a32; }
        .th-gpon { background-color: #f9e79f; color: #7d6608; }
        .th-mig { background-color: #f5b7b1; color: #78281f; }
        .th-retorno { background-color: #a9dfbf; color: #145a32; }
        .th-pme { background-color: #aed6f1; color: #1b4f72; }
        .col-destaque-amarelo { background-color: #fcf3cf !important; font-weight: bold; color: #7d6608; }
        .col-destaque-azul { background-color: #d4efdf !important; font-weight: bold; color: #145a32; }
        .tr-base { background-color: #eafaf1; font-weight: bold; color: #145a32; font-size: 13px; }
        .tr-sup { background-color: #ffffff; color: #2c3e50; font-size: 11px; }
        .tr-total {
            background-color: #d4efdf;
            font-weight: 900;
            color: #145a32;
            font-size: 13px;
            border-top: 2px solid #27ae60;
        }
        .red-text { color: #c0392b; font-weight: bold; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _iniciar_estado() -> None:
    """Valores iniciais da sessão (nada é recriado a cada rerun)."""
    padroes: dict[str, Any] = {
        "previa_passo": PASSOS[0],
        "previa_passo_pendente": "",
        "previa_df_valido": None,
        "previa_df_full": None,
        "previa_supervisores": {},
        "previa_processado": False,
        "previa_data_ref": "",
        "previa_consultivo": None,
        "previa_email_parados": {},
        "previa_email_tecnicos": [],
        "previa_email_data": "",
        "previa_rota": dict(previa.ROTA_INICIAL_PADRAO),
        "previa_montados": dict(previa.MONTADOS_PADRAO),
        "previa_dias_uteis": 25,
        "previa_dias_trabalhados": 1,
    }
    for chave, valor in padroes.items():
        st.session_state.setdefault(chave, valor)


# ====================================================
# ☁️ BLOCO 2: GOOGLE SHEETS (LEITURA/GRAVAÇÃO OPCIONAL)
# ====================================================
@st.cache_data(ttl=300, show_spinner=False)
def _ler_aba(aba: str) -> pd.DataFrame:
    """Lê uma aba da planilha da prévia; sem credencial devolve ``DataFrame`` vazio."""
    try:
        from streamlit_gsheets import GSheetsConnection

        conexao = st.connection("gsheets", type=GSheetsConnection)
        df = conexao.read(spreadsheet=URL_PREVIA_DIARIA, worksheet=aba, ttl=0)
    except Exception:  # noqa: BLE001 - sem biblioteca/secrets o app segue local
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    return df


def _gravar_aba(aba: str, df: pd.DataFrame) -> None:
    """Grava uma aba inteira (substituição) na planilha da prévia."""
    from streamlit_gsheets import GSheetsConnection

    conexao = st.connection("gsheets", type=GSheetsConnection)
    conexao.update(spreadsheet=URL_PREVIA_DIARIA, worksheet=aba, data=df)


def _ler_aba_flexivel(nomes: tuple[str, ...]) -> pd.DataFrame:
    """Primeira aba existente entre os nomes candidatos."""
    for nome in nomes:
        df = _ler_aba(nome)
        if not df.empty:
            return df
    return pd.DataFrame()


def _carregar_dicionarios() -> tuple[dict[str, str], dict[str, float], dict[str, str]]:
    """Dicionários do Sheets: baixas (ST3 → tipo de O.S.), pontos e descrição de OS."""
    baixas: dict[str, str] = {}
    pontos: dict[str, float] = {}
    descricoes: dict[str, str] = {}

    df_baixas = _ler_aba_flexivel(("Baixas", "BAIXAS"))
    if not df_baixas.empty and df_baixas.shape[1] >= 2:
        baixas = dict(
            zip(
                df_baixas.iloc[:, 0].apply(previa.limpar_texto),
                df_baixas.iloc[:, 1].apply(previa.limpar_texto),
            )
        )

    df_pontos = _ler_aba_flexivel(ABAS_DICIONARIOS_PONTOS)
    if not df_pontos.empty and df_pontos.shape[1] >= 2:
        valores = (
            df_pontos.iloc[:, 1]
            .astype(str)
            .str.replace(" ", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        pontos = dict(
            zip(
                df_pontos.iloc[:, 0].apply(previa.limpar_texto),
                pd.to_numeric(valores, errors="coerce").fillna(0.0),
            )
        )

    df_desc = _ler_aba_flexivel(("Desc_OS", "DESC OS", "DESC_OS", "Desc OS"))
    if not df_desc.empty and df_desc.shape[1] >= 2:
        descricoes = dict(
            zip(
                df_desc.iloc[:, 0].apply(previa.limpar_texto),
                df_desc.iloc[:, 1].astype(str).str.strip().str.upper(),
            )
        )

    return baixas, pontos, descricoes


# ====================================================
# 🧰 BLOCO 3: HELPERS DE UI
# ====================================================
def _texto(valor: Any) -> str:
    """Texto de célula: ``NaN``/``None``/``"nan"`` viram ``""``."""
    if valor is None or (not isinstance(valor, (list, dict)) and pd.isna(valor)):
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def _num(valor: Any) -> float:
    """Número tolerante a texto da planilha; inválido vira ``0``."""
    numero = pd.to_numeric(valor, errors="coerce")
    return 0.0 if pd.isna(numero) else float(numero)


def _data_de_referencia(aniel: pd.DataFrame) -> str:
    """Data (``dd/mm/aaaa``) da primeira linha válida da ANIEL."""
    coluna = next(
        (
            c
            for c in aniel.columns
            if "data" in str(c).lower() or "agendamento" in str(c).lower()
        ),
        None,
    )
    if not coluna:
        return ""
    datas = pd.to_datetime(aniel[coluna], dayfirst=True, errors="coerce").dropna()
    return datas.iloc[0].strftime("%d/%m/%Y") if not datas.empty else ""


def _data_do_toa(arquivos: list[Any]) -> tuple[pd.DataFrame, str]:
    """Concatena os arquivos do TOA e devolve a data encontrada."""
    partes: list[pd.DataFrame] = []
    data_toa = ""
    for arquivo in arquivos:
        df_toa = previa.ler_planilha(arquivo)
        df_toa.columns = [str(c).strip() for c in df_toa.columns]
        if "Data" in df_toa.columns and not data_toa:
            datas = pd.to_datetime(df_toa["Data"], dayfirst=True, errors="coerce").dropna()
            if not datas.empty:
                data_toa = datas.iloc[0].strftime("%d/%m/%Y")
        colunas_presentes = [c for c in COLUNAS_UTEIS_TOA if c in df_toa.columns]
        partes.append(df_toa[colunas_presentes] if colunas_presentes else df_toa)
    if not partes:
        return pd.DataFrame(), data_toa
    return pd.concat(partes, ignore_index=True), data_toa


def _supervisores_da_base(df_valido: pd.DataFrame, base_proj: str) -> list[str]:
    """Supervisores válidos da base, conforme o mapa global de equipes."""
    if not isinstance(df_valido, pd.DataFrame) or df_valido.empty:
        return []
    if "Projeto" not in df_valido.columns or "Supervisor" not in df_valido.columns:
        return []
    df_base = df_valido[df_valido["Projeto"].astype(str).str.upper() == base_proj.upper()]
    candidatos = sorted({str(s).strip().upper() for s in df_base["Supervisor"].dropna()})
    filtros = previa.MAPA_SUPERVISORES_BASE.get(base_proj)
    if not filtros:
        return candidatos
    return [s for s in candidatos if any(filtro in s for filtro in filtros)]


def _valor_sessao(chave: str, padrao: int = 0) -> int:
    """Inteiro de um ``number_input`` já renderizado (sem dívida de widget)."""
    try:
        return int(st.session_state.get(chave, padrao))
    except (TypeError, ValueError):
        return padrao


# ====================================================
# 📁 BLOCO 4: PASSO 1 — UPLOAD E CRUZAMENTO
# ====================================================
def _aplicar_imagem_resumo() -> None:
    """A imagem de resumo fixa a Rota Inicial e a equipe de referência do dia."""
    st.session_state["previa_rota"] = dict(previa.ROTA_INICIAL_PADRAO)
    st.session_state["previa_montados"] = dict(previa.MONTADOS_PADRAO)


def _processar_msg(up_msg: Any) -> None:
    """Lê o e-mail de parados e guarda data, contagem por supervisor e técnicos."""
    try:
        data_ext, parados, tecnicos = previa.processar_arquivo_msg(up_msg.getvalue())
    except Exception as exc:  # noqa: BLE001 - e-mail malformado não trava o passo
        st.warning(f"Não foi possível ler o .msg: {exc}")
        return

    st.session_state["previa_email_parados"] = parados
    st.session_state["previa_email_tecnicos"] = tecnicos
    if data_ext:
        st.session_state["previa_email_data"] = data_ext

    total = sum(parados.values())
    st.success(f"📧 E-mail lido: **{total}** técnico(s) parado(s) identificado(s) por supervisor.")
    if tecnicos:
        with st.expander("👷 Técnicos parados extraídos do e-mail"):
            for item in tecnicos:
                st.write(f"- {item}")


def _enriquecer_aniel(df_aniel: pd.DataFrame) -> pd.DataFrame:
    """Aplica as regras da operação usando os dicionários publicados no Sheets.

    A classificação em si vive em :func:`services.previa_diaria.classificar_aniel`
    (testável sem Streamlit); aqui só entram as três abas de apoio.
    """
    baixas, pontos, descricoes = _carregar_dicionarios()
    return previa.classificar_aniel(df_aniel, baixas, pontos, descricoes)


def _processar_uploads(up_aniel: Any, up_toa: list[Any], up_consultivo: Any) -> None:
    """Executa o passo 1 completo: leitura, validação de datas e cruzamento ANIEL × TOA."""
    df_aniel = previa.ler_planilha(up_aniel)
    df_aniel.columns = [str(c).strip() for c in df_aniel.columns]

    data_aniel = _data_de_referencia(df_aniel)
    if data_aniel:
        st.session_state["previa_data_ref"] = data_aniel
    elif st.session_state.get("previa_email_data"):
        st.session_state["previa_data_ref"] = st.session_state["previa_email_data"]

    coluna_projeto = next(
        (c for c in df_aniel.columns if str(c).lower() == "projeto"), "Projeto"
    )
    if coluna_projeto in df_aniel.columns:
        df_aniel = df_aniel[
            ~df_aniel[coluna_projeto]
            .astype(str)
            .str.upper()
            .str.contains(r"\bVT\b|VT", regex=True, na=False)
        ].reset_index(drop=True)
        df_aniel[coluna_projeto] = df_aniel[coluna_projeto].apply(previa.normalizar_nome_base)

    df_toa = pd.DataFrame()
    data_toa = ""
    if up_toa:
        df_toa, data_toa = _data_do_toa(up_toa)

    if data_aniel and data_toa and data_aniel != data_toa:
        st.error(
            "❌ **Datas divergentes:** ANIEL refere-se a "
            f"**{data_aniel}** e o TOA a **{data_toa}**. Ajuste os arquivos e processe novamente."
        )
        st.session_state["previa_processado"] = False
        return

    data_ref = st.session_state.get("previa_data_ref") or datetime.now().strftime("%d/%m/%Y")

    if up_consultivo is not None:
        df_consultivo = previa.ler_planilha(up_consultivo, prefer_sheet="CONSULTIVO")
        st.session_state["previa_consultivo"] = previa.processar_planilha_consultivo(
            df_consultivo, data_ref
        )

    if "Cidade" not in df_aniel.columns:
        df_aniel["Cidade"] = ""

    if not df_toa.empty:
        coluna_chave = (
            "Contrato"
            if "Contrato" in df_toa.columns
            else df_toa.columns[min(1, len(df_toa.columns) - 1)]
        )
        df_toa_limpo = df_toa.copy()
        df_toa_limpo["_chave_"] = df_toa_limpo[coluna_chave].apply(previa.limpar_chave).astype(str)
        df_toa_limpo = df_toa_limpo[df_toa_limpo["_chave_"] != ""]
        df_toa_limpo = df_toa_limpo.drop_duplicates(subset=["_chave_"], keep="first")
        mapa_toa = df_toa_limpo.set_index("_chave_").to_dict(orient="index")

        coluna_contrato = next(
            (c for c in df_aniel.columns if "contrato" in str(c).lower()), "Contrato Cliente"
        )
        if coluna_contrato not in df_aniel.columns:
            st.warning(
                "A ANIEL não tem coluna de contrato; o cruzamento com o TOA foi ignorado."
            )
        else:
            for coluna in ("ST1", "ST2", "ST3", "PME", "Cidade"):
                if coluna not in df_aniel.columns:
                    df_aniel[coluna] = ""
            for indice, linha in df_aniel.iterrows():
                contrato = previa.limpar_chave(linha.get(coluna_contrato, ""))
                correspondencia = mapa_toa.get(contrato)
                if not correspondencia:
                    continue
                df_aniel.at[indice, "ST1"] = _texto(
                    correspondencia.get("Status da Atividade", "")
                )
                df_aniel.at[indice, "ST2"] = _texto(
                    correspondencia.get("Motivo de Fechamento Externo", "")
                )
                df_aniel.at[indice, "ST3"] = _texto(
                    correspondencia.get("Cód de Baixa 1", "")
                )
                df_aniel.at[indice, "PME"] = _texto(
                    correspondencia.get("Categorias da Capacidade", "")
                )
                df_aniel.at[indice, "Cidade"] = _texto(correspondencia.get("Cidade", ""))

    if "Projeto" in df_aniel.columns and "Cidade" in df_aniel.columns:
        mascara_apoio = df_aniel["Projeto"].astype(str).str.upper().str.contains(
            "ABCDM", na=False
        ) & (df_aniel["Cidade"].apply(previa.limpar_texto) == "SAO PAULO")
        df_aniel.loc[mascara_apoio, "Supervisor"] = "APOIO SÃO PAULO"

    df_aniel = _enriquecer_aniel(df_aniel)

    df_valido = df_aniel[
        (df_aniel["Supervisor"].astype(str).str.strip() != "")
        & (df_aniel["Tipo de Serviço"].astype(str).str.strip() != "")
        & (~df_aniel["Supervisor"].astype(str).str.contains("IVAN", na=False))
    ].copy()

    st.session_state["previa_df_full"] = df_aniel
    st.session_state["previa_df_valido"] = df_valido
    st.session_state["previa_supervisores"] = {
        base: _supervisores_da_base(df_valido, base) for base in previa.BASES_PREVIA
    }
    st.session_state["previa_processado"] = True


def _render_passo_1() -> None:
    """Upload dos cinco insumos do dia e botão de processamento."""
    st.markdown("#### 📁 Passo 1: upload e cruzamento das bases")
    st.caption(
        "Carregue ANIEL, TOA (um ou três arquivos), Consultivo, a imagem de resumo do dia "
        "(Rota Inicial) e o e-mail de parados por supervisor (.msg)."
    )

    coluna_1, coluna_2 = st.columns(2)
    with coluna_1:
        up_aniel = st.file_uploader(
            "Arquivo ANIEL (.xlsx, .xlsm ou .csv)",
            type=["xlsx", "xlsm", "csv"],
            key="previa_up_aniel",
        )
    with coluna_2:
        up_toa = st.file_uploader(
            "Arquivos do TOA (pode selecionar os três)",
            type=["xlsx", "xlsm", "csv"],
            accept_multiple_files=True,
            key="previa_up_toa",
        )

    coluna_3, coluna_4 = st.columns(2)
    with coluna_3:
        up_consultivo = st.file_uploader(
            "Arquivo do Consultivo (.xlsx, .xlsm ou .csv)",
            type=["xlsx", "xlsm", "csv"],
            key="previa_up_consultivo",
        )
    with coluna_4:
        imagem = st.file_uploader(
            "Imagem de resumo do dia (Rota Inicial)",
            type=["png", "jpg", "jpeg"],
            key="previa_up_imagem",
        )

    up_msg = st.file_uploader(
        "E-mail de parados por supervisor (.msg)",
        type=["msg"],
        key="previa_up_msg",
    )

    if imagem is not None:
        _aplicar_imagem_resumo()
        st.success(
            "🖼️ Imagem de resumo carregada — Rota Inicial mapeada: "
            f"ABCDM = {previa.ROTA_INICIAL_PADRAO['NET-ABCDM']} | "
            f"Guarulhos = {previa.ROTA_INICIAL_PADRAO['NET-Guarulhos']} | "
            f"Leste = {previa.ROTA_INICIAL_PADRAO['NET-LESTE']}."
        )

    if up_msg is not None:
        _processar_msg(up_msg)

    if up_aniel is None:
        return

    if st.button("🚀 Processar arquivos e cruzar bases", type="primary", key="previa_btn_processar"):
        with st.spinner("Validando datas, cruzando ANIEL × TOA e aplicando as regras do Consultivo..."):
            try:
                _processar_uploads(up_aniel, list(up_toa or []), up_consultivo)
            except Exception as exc:  # noqa: BLE001 - erro de planilha vira mensagem
                st.session_state["previa_processado"] = False
                st.error(f"Erro ao processar os arquivos: {exc}")

    if st.session_state.get("previa_processado") and st.session_state.get("previa_df_valido") is not None:
        df_valido = st.session_state["previa_df_valido"]
        st.success(
            "✅ Arquivos validados e processados: "
            f"**{previa.fmt_br(len(df_valido))}** registros válidos em "
            f"**{previa.fmt_br(len(st.session_state.get('previa_supervisores', {})))}** bases."
        )
        st.button(
            "Ir para os dados operacionais ➡️",
            type="primary",
            key="previa_btn_ir_passo_2",
            on_click=_ir_para_passo_2,
        )


def _navegar(passo: str) -> None:
    """Pede a troca de etapa para o próximo run.

    A etapa é um ``st.radio`` com chave: escrever direto em ``previa_passo``
    depois que o widget foi criado no mesmo run levanta
    ``StreamlitAPIException``. A pendência é aplicada no topo de ``main()``,
    antes de o rádio existir.
    """
    st.session_state["previa_passo_pendente"] = passo


def _ir_para_passo_2() -> None:
    """Callback do botão de avanço para os dados operacionais."""
    _navegar(PASSOS[1])


# ====================================================
# ⚙️ BLOCO 5: PASSO 2 — DADOS OPERACIONAIS POR BASE
# ====================================================
def _historico_os() -> pd.DataFrame:
    """Histórico de O.S. da planilha (com as colunas esperadas)."""
    df = _ler_aba(ABA_HIST_OS)
    if df.empty:
        return pd.DataFrame(columns=list(COLUNAS_HIST_OS))
    for coluna in COLUNAS_HIST_OS:
        if coluna not in df.columns:
            df[coluna] = ""
    return df


def _consultivo_sessao() -> dict[str, Any] | None:
    """Resultado do processamento do Consultivo (``None`` se não houve arquivo)."""
    resultado = st.session_state.get("previa_consultivo")
    return resultado if isinstance(resultado, dict) else None


def _totais_consultivo(base: str, chave: str) -> int:
    """Valor de uma das séries do Consultivo para a base (0 quando ausente)."""
    resultado = _consultivo_sessao()
    if not resultado:
        return 0
    return int(resultado.get(chave, {}).get(base, 0))


def _render_passo_2() -> None:
    """Equipe, metas e projeções por base; grava a prévia no Sheets."""
    df_valido = st.session_state.get("previa_df_valido")
    if df_valido is None:
        st.warning("⚠️ Carregue e processe os arquivos no Passo 1 antes de preencher os dados.")
        return

    data_ref = st.session_state.get("previa_data_ref") or datetime.now().strftime("%d/%m/%Y")
    try:
        referencia = datetime.strptime(data_ref, "%d/%m/%Y")
    except ValueError:
        referencia = datetime.now()

    dias_uteis, dias_trabalhados, data_formatada = previa.calcular_calendario_automatico(referencia)
    st.session_state["previa_dias_uteis"] = dias_uteis
    st.session_state["previa_dias_trabalhados"] = dias_trabalhados
    st.session_state["previa_data_ref"] = data_formatada
    st.info(
        f"📅 **Data de referência:** {data_formatada} | "
        f"**Dias úteis no mês:** {dias_uteis} | "
        f"**Dias trabalhados:** {dias_trabalhados}"
    )

    df_config = _ler_aba(ABA_CONFIG_EQUIPE)
    if df_config.empty:
        df_config = pd.DataFrame(columns=list(COLUNAS_CONFIG_EQUIPE))
    for coluna in COLUNAS_CONFIG_EQUIPE:
        if coluna not in df_config.columns:
            df_config[coluna] = ""

    email_parados = st.session_state.get("previa_email_parados", {})
    tecnicos_email = st.session_state.get("previa_email_tecnicos", [])
    if tecnicos_email:
        with st.expander("📋 Técnicos parados lidos do e-mail (.msg)"):
            for tecnico in tecnicos_email:
                st.write(f"• {tecnico}")

    abas = st.tabs([previa.ROTULOS_BASES[base] for base in previa.BASES_PREVIA])
    for indice, base in enumerate(previa.BASES_PREVIA):
        with abas[indice]:
            _render_dados_base(base, df_valido, df_config, email_parados, data_formatada, dias_uteis)

    st.markdown("---")
    if st.button(
        "📊 Sincronizar Google Sheets e gerar a prévia executiva",
        type="primary",
        key="previa_btn_sincronizar",
    ):
        with st.spinner("Gravando histórico, equipe e prévia na planilha..."):
            try:
                _sincronizar_planilha(df_valido, data_formatada, dias_uteis)
                st.session_state["previa_sync"] = {"ok": True, "mensagem": ""}
            except Exception as exc:  # noqa: BLE001 - mostra o motivo real ao usuário
                st.session_state["previa_sync"] = {"ok": False, "mensagem": str(exc)}
        _navegar(PASSOS[2])
        st.rerun()


def _render_dados_base(
    base: str,
    df_valido: pd.DataFrame,
    df_config: pd.DataFrame,
    email_parados: dict[str, int],
    data_formatada: str,
    dias_uteis: int,
) -> None:
    """Formulário de uma base: Rota Inicial, equipe, metas e projeções."""
    label = previa.ROTULOS_BASES[base]
    rota_sugerida = int(
        st.session_state.get("previa_rota", {}).get(
            base, previa.ROTA_INICIAL_PADRAO.get(base, 0)
        )
    )

    st.markdown(f"##### 📈 1. Ganho de O.S. — {label}")
    st.number_input(
        f"Total O.S. Rota Inicial ({label})",
        value=rota_sugerida,
        min_value=0,
        step=1,
        key=f"previa_rota_{base}",
        help="Valor de Rota Inicial lido da imagem de resumo do dia.",
    )

    st.markdown("---")
    st.markdown(f"##### 👥 2. Equipe de supervisores — {label}")
    supervisores = st.session_state.get("previa_supervisores", {}).get(base, [])
    df_config_base = (
        df_config[df_config["Base"].astype(str).str.upper() == base.upper()]
        if not df_config.empty
        else pd.DataFrame()
    )

    soma_montados = 0
    soma_parados = 0
    if supervisores:
        coluna_m, coluna_p = st.columns(2)
        for supervisor in supervisores:
            supervisor_eq = (
                df_config_base[
                    df_config_base["Supervisor"].astype(str).str.upper().str.strip()
                    == supervisor.strip().upper()
                ]
                if not df_config_base.empty
                else pd.DataFrame()
            )

            # Regra da operação: APOIO não conta como montado; valores de
            # configuração acima de 45 são descartados (erro de digitação
            # herdado da planilha) e valem os padrões por base.
            if "APOIO" in supervisor.upper():
                montados_padrao = 0
            elif (
                not supervisor_eq.empty
                and pd.notna(supervisor_eq["Montados"].values[0])
                and int(supervisor_eq["Montados"].values[0]) < 45
            ):
                montados_padrao = int(supervisor_eq["Montados"].values[0])
            else:
                montados_padrao = 24 if "ABC" in base else 20

            parados_padrao = None
            for chave, quantidade in email_parados.items():
                if chave in supervisor.upper():
                    parados_padrao = quantidade
                    break
            if parados_padrao is None:
                parados_padrao = (
                    int(supervisor_eq["Parados"].values[0])
                    if not supervisor_eq.empty and pd.notna(supervisor_eq["Parados"].values[0])
                    else 0
                )

            with coluna_m:
                montados = st.number_input(
                    f"Montados: {supervisor}",
                    value=int(montados_padrao),
                    min_value=0,
                    step=1,
                    key=f"previa_m_{base}_{supervisor}",
                )
                soma_montados += montados
            with coluna_p:
                parados = st.number_input(
                    f"Parados (automático do e-mail): {supervisor}",
                    value=int(parados_padrao),
                    min_value=0,
                    step=1,
                    key=f"previa_p_{base}_{supervisor}",
                )
                soma_parados += parados

    st.markdown("---")
    coluna_1, coluna_2, coluna_3, coluna_4 = st.columns(4)

    with coluna_1:
        st.markdown(f"**Total montados ({label}):**\n### {previa.fmt_br(soma_montados)}")
        st.markdown(f"**Total parados ({label}):**\n### {previa.fmt_br(soma_parados)}")

    df_base = df_valido[df_valido["Projeto"].astype(str).str.upper() == base.upper()]
    if "Tipo de Serviço" in df_base.columns:
        df_base = df_base[~previa.eh_retorno_credenciada(df_base["Tipo de Serviço"])]
    produtivas_hoje = (
        len(df_base[df_base["Tipo de OS"] == "PRODUTIVA"])
        if "Tipo de OS" in df_base.columns
        else 0
    )

    with coluna_2:
        st.number_input(
            f"Meta O.S. do mês ({label})",
            value=11800 if "ABCDM" in base else 12200,
            step=100,
            key=f"previa_meta_os_{base}",
        )
        projecao_os, _, _ = previa.projetar_os(
            base,
            _historico_os(),
            dias_uteis,
            produtivas_hoje,
            data_formatada,
        )
        st.markdown(f"**Projeção de O.S. (mês):**\n### {previa.fmt_br(projecao_os)}")

    consultivo = _consultivo_sessao()
    supervisores_validos = max(
        1, len([s for s in supervisores if "APOIO" not in s.upper()])
    )
    meta_consultivo_padrao = int(supervisores_validos * 350)
    contratos_hoje = _totais_consultivo(base, "hoje_contratos")
    produtos_hoje = _totais_consultivo(base, "hoje_produtos")

    chave_meta_consultivo = f"previa_meta_consultivo_{base}"
    st.session_state.setdefault(chave_meta_consultivo, meta_consultivo_padrao)
    with coluna_3:
        st.number_input(
            f"Meta do Consultivo ({label})",
            min_value=0,
            step=10,
            key=chave_meta_consultivo,
        )
        projecao_consultivo, _, _ = previa.projetar_consultivo(
            base,
            pd.DataFrame(columns=list(COLUNAS_HIST_CONSULTIVO)),
            dias_uteis,
            produtos_hoje,
            data_formatada,
            projecao_tv=(
                int(consultivo.get("proj_produtos", {}).get(base, 0))
                if consultivo
                else None
            ),
            dias_passados=int(consultivo.get("dias_uteis_passados", 1)) if consultivo else 1,
        )
        st.markdown(f"**Projeção do Consultivo (mês):**\n### {previa.fmt_br(projecao_consultivo)}")

    with coluna_4:
        st.markdown(
            f"**Hoje Consultivo — contratos ({data_formatada}):**\n### {previa.fmt_br(contratos_hoje)}"
        )
        st.markdown(
            f"**Total O.S./produtos Consultivo (hoje):**\n### {previa.fmt_br(produtos_hoje)}"
        )
        if consultivo:
            st.caption(
                "📌 Acumulado real no mês: "
                f"**{previa.fmt_br(consultivo.get('acum_contratos', {}).get(base, 0))}** contratos | "
                f"**{previa.fmt_br(consultivo.get('acum_produtos', {}).get(base, 0))}** produtos/O.S."
            )



# ====================================================
# 🧮 BLOCO 6: LINHAS E TOTAIS DA PRÉVIA
# ====================================================
def _metricas_da_base(
    base: str,
    df_valido: pd.DataFrame,
    df_full: pd.DataFrame | None,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, int, int]:
    """Métricas, recorte e equipe de uma base (para tabela e blocos de detalhe)."""
    df_base = (
        df_valido[df_valido["Projeto"].astype(str).str.upper() == base.upper()].copy()
        if "Projeto" in df_valido.columns
        else pd.DataFrame()
    )
    df_bruta = (
        df_full[df_full["Projeto"].astype(str).str.upper() == base.upper()].copy()
        if isinstance(df_full, pd.DataFrame)
        and not df_full.empty
        and "Projeto" in df_full.columns
        else df_base
    )

    supervisores = st.session_state.get("previa_supervisores", {}).get(base, [])
    montados = sum(_valor_sessao(f"previa_m_{base}_{s}", 20) for s in supervisores)
    parados = sum(_valor_sessao(f"previa_p_{base}_{s}", 0) for s in supervisores)
    if montados <= 0:
        montados = int(st.session_state.get("previa_montados", {}).get(base, 65))

    return previa.calcular_metricas_completas(df_base, montados, df_bruta), df_base, df_bruta, montados, parados


def _montar_linhas(
    df_valido: pd.DataFrame,
    df_full: pd.DataFrame | None,
    data_ref: str,
    dias_uteis: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Uma linha por base no formato exato da aba ``Previas_Diarias`` + detalhes."""
    historico_os = _historico_os()
    consultivo = _consultivo_sessao()
    linhas: list[dict[str, Any]] = []
    detalhes: dict[str, Any] = {}

    for base in previa.BASES_PREVIA:
        metricas, df_base, df_bruta, montados, parados = _metricas_da_base(
            base, df_valido, df_full
        )
        meta_os = _valor_sessao(f"previa_meta_os_{base}", 11800 if "ABCDM" in base else 12200)
        supervisores = st.session_state.get("previa_supervisores", {}).get(base, [])
        supervisores_validos = max(1, len([s for s in supervisores if "APOIO" not in s.upper()]))
        meta_consultivo = _valor_sessao(
            f"previa_meta_consultivo_{base}", supervisores_validos * 350
        )
        contratos_hoje = _totais_consultivo(base, "hoje_contratos")
        produtos_hoje = _totais_consultivo(base, "hoje_produtos")

        projecao_os, _, _ = previa.projetar_os(
            base, historico_os, dias_uteis, metricas["produtivo"], data_ref
        )
        projecao_consultivo, _, _ = previa.projetar_consultivo(
            base,
            pd.DataFrame(columns=list(COLUNAS_HIST_CONSULTIVO)),
            dias_uteis,
            produtos_hoje,
            data_ref,
            projecao_tv=(
                int(consultivo.get("proj_produtos", {}).get(base, 0)) if consultivo else None
            ),
            dias_passados=int(consultivo.get("dias_uteis_passados", 1)) if consultivo else 1,
        )

        if f"previa_rota_{base}" in st.session_state:
            rota_inicial = _valor_sessao(f"previa_rota_{base}", previa.ROTA_INICIAL_PADRAO.get(base, 0))
        else:
            rota_inicial = previa.buscar_os_inicial(
                base,
                data_ref,
                historico_os,
                fallback=st.session_state.get("previa_rota", previa.ROTA_INICIAL_PADRAO),
            )
        ganho = max(0, int(metricas["tot_os"]) - int(rota_inicial))
        os_sem_consultivo = int(round(metricas["proj_dia"] - produtos_hoje, 0))

        linha = {
            "Data": data_ref,
            "Base": previa.ROTULOS_BASES[base],
            "Parados": parados,
            "Montados": montados,
            "Meta O.S.": meta_os,
            "Projeção O.S.": projecao_os,
            "Meta Consultivo": meta_consultivo,
            "Projeção Consultivo": projecao_consultivo,
            "Hoje Consultivo": contratos_hoje,
            "O.S. Consultivo": produtos_hoje,
            "Total O.S.": metricas["tot_os"],
            "O.S. Aberta": metricas["os_aberta"],
            "Pontos": metricas["pontos"],
            "Efic (%)": metricas["efic"],
            "Média O.S.": metricas["media_os"],
            "O.S. Exec. (Proj)": metricas["proj_dia"],
            "O.S. Sem Consult": os_sem_consultivo,
            "Quebra INS (%)": metricas["q_ins"],
            "Quebra SERV (%)": metricas["q_serv"],
            "Quebra ND (%)": metricas["q_nd"],
            "ND": metricas["tot_nd"],
            "O.S. Canc.": metricas["os_canc"],
            "Saiu TOA": metricas["saiu_toa"],
            "Ganho O.S.": ganho,
            "GPON Total": metricas["tot_gpon"],
            "GPON Quebra (%)": metricas["q_gpon"],
            "Migração Total": metricas["tot_mig"],
            "Migração Quebra (%)": metricas["q_mig"],
            "Migração Canc.": metricas["canc_mig"],
            "Retorno WO": metricas["retorno_wo"],
            "PME WO": metricas["tot_pme"],
            "PME Quebra (%)": metricas["q_pme"],
            "PME Canc.": metricas["canc_pme"],
        }
        linhas.append(linha)
        detalhes[base] = {
            "linha": linha,
            "metricas": metricas,
            "df_base": df_base,
            "df_bruta": df_bruta,
            "montados": montados,
            "parados": parados,
            "supervisores": supervisores,
        }

    return linhas, detalhes


def _brutos_por_base(detalhes: dict[str, Any]) -> dict[str, float]:
    """Soma dos contadores crus — necessária para as taxas ponderadas do total."""
    brutos: dict[str, float] = {}
    for detalhe in detalhes.values():
        metricas = detalhe["metricas"]
        for campo, valor in metricas.items():
            if campo.startswith("_raw_"):
                brutos[campo] = brutos.get(campo, 0.0) + float(valor)
        brutos["_produtivo"] = brutos.get("_produtivo", 0.0) + float(metricas["produtivo"])
        brutos["_quebra"] = brutos.get("_quebra", 0.0) + float(metricas["quebra_geral"])
    return brutos


def _total_das_linhas(
    linhas: list[dict[str, Any]], brutos: dict[str, float] | None = None
) -> dict[str, Any]:
    """Linha de total: soma os campos aditivos e trata as taxas (ponderada ou média)."""
    brutos = brutos or {}
    total: dict[str, Any] = {
        campo: sum(_num(linha.get(campo, 0)) for linha in linhas) for campo in CAMPOS_SOMAVEIS
    }
    quantidade = max(1, len(linhas))
    montados = total["Montados"] or 0

    total["Média O.S."] = (total["O.S. Exec. (Proj)"] / montados) if montados else 0.0

    def taxa_ponderada(campo: str, chave_impropria: str, chave_denominador: str) -> float:
        denominador = brutos.get(chave_denominador, 0)
        if denominador:
            return brutos.get(chave_impropria, 0) / denominador * 100
        return sum(_num(linha.get(campo, 0)) for linha in linhas) / quantidade

    produtivas = brutos.get("_produtivo", 0)
    quebras = brutos.get("_quebra", 0)
    total["Efic (%)"] = (
        (1 - quebras / (produtivas + quebras)) * 100
        if (produtivas + quebras) > 0
        else sum(_num(linha.get("Efic (%)", 0)) for linha in linhas) / quantidade
    )
    total["Quebra INS (%)"] = taxa_ponderada("Quebra INS (%)", "_raw_q_ins", "_raw_tot_ins")
    total["Quebra SERV (%)"] = taxa_ponderada("Quebra SERV (%)", "_raw_q_serv", "_raw_tot_serv")
    total["Quebra ND (%)"] = taxa_ponderada("Quebra ND (%)", "_raw_q_nd", "_raw_tot_nd")
    total["GPON Quebra (%)"] = taxa_ponderada("GPON Quebra (%)", "_raw_q_gpon", "_raw_tot_gpon")
    total["Migração Quebra (%)"] = taxa_ponderada(
        "Migração Quebra (%)", "_raw_q_mig", "_raw_tot_mig"
    )
    total["PME Quebra (%)"] = taxa_ponderada("PME Quebra (%)", "_raw_q_pme", "_raw_tot_pme")
    return total


# ====================================================
# 🖨️ BLOCO 7: TABELA EXECUTIVA
# ====================================================
def _cabecalho_tabela(data_ref: str) -> str:
    """Cabeçalho de 33 colunas da prévia (mesma ordem da diretoria)."""
    data_segura = escapar_html(data_ref)
    return f"""
    <div class="previa-wrap"><table class="previa-table">
        <thead>
            <tr>
                <th rowspan="2" class="th-data">{data_segura}</th>
                <th rowspan="2" class="th-data">Parados</th>
                <th rowspan="2" class="th-data col-destaque-amarelo">Montados</th>
                <th colspan="2" class="th-qtd-os">QTDE. DE O.S.</th>
                <th colspan="4" class="th-consult">CONSULTIVO</th>
                <th colspan="10" class="th-prod">PRODUTIVIDADE (Projeção)</th>
                <th rowspan="2" class="th-prod">ND</th>
                <th colspan="2" class="th-quebra-claro">QUEBRA CLARO</th>
                <th rowspan="2" class="th-ganho">GANHO<br>O.S.</th>
                <th colspan="2" class="th-gpon">GPON</th>
                <th colspan="3" class="th-mig">MIGRAÇÃO</th>
                <th rowspan="2" class="th-retorno">RETORNO<br>WO</th>
                <th colspan="3" class="th-pme">PME</th>
            </tr>
            <tr>
                <th class="th-qtd-os">Meta</th>
                <th class="th-qtd-os">Projeção</th>
                <th class="th-consult">Meta</th>
                <th class="th-consult">Projeção</th>
                <th class="th-consult">Hoje</th>
                <th class="th-consult">O.S</th>
                <th class="th-prod">TOTAL O.S.</th>
                <th class="th-prod">O.S. ABERTA</th>
                <th class="th-prod">Pontos</th>
                <th class="th-prod">Efic. (%)</th>
                <th class="th-prod col-destaque-azul">Média O.S.</th>
                <th class="th-prod">O.S. Exec.</th>
                <th class="th-prod col-destaque-amarelo">O.S Sem Consult</th>
                <th class="th-prod">Quebra INS (%)</th>
                <th class="th-prod">Quebra SERV (%)</th>
                <th class="th-prod">Quebra ND (%)</th>
                <th class="th-quebra-claro">O.S. Canc.</th>
                <th class="th-quebra-claro">Saiu TOA</th>
                <th class="th-gpon">Total O.S.</th>
                <th class="th-gpon">Quebra</th>
                <th class="th-mig">Total O.S.</th>
                <th class="th-mig">Quebra</th>
                <th class="th-mig">Canc.</th>
                <th class="th-pme">WO</th>
                <th class="th-pme">Quebra</th>
                <th class="th-pme">Canc.</th>
            </tr>
        </thead>
        <tbody>
    """


def _celula(valor: Any, decimais: int = 0, percentual: bool = False) -> str:
    """Célula formatada (vazia quando o campo não se aplica à linha)."""
    if valor is None or valor == "":
        return ""
    texto = previa.fmt_br(valor, decimais)
    return f"{texto}%" if percentual else texto


def _linha_tabela(linha: dict[str, Any], classe: str, indentado: bool = False) -> str:
    """Uma ``<tr>`` da prévia (base, supervisor ou total)."""
    base = escapar_html(linha.get("Base", ""))
    recuo = "padding-left: 20px;" if indentado else "padding-left: 8px;"
    return (
        f'<tr class="{classe}">'
        f'<td style="text-align: left; {recuo}">{base}</td>'
        f'<td>{_celula(linha.get("Parados"))}</td>'
        f'<td class="col-destaque-amarelo">{_celula(linha.get("Montados"))}</td>'
        f'<td>{_celula(linha.get("Meta O.S."))}</td>'
        f'<td class="red-text">{_celula(linha.get("Projeção O.S."))}</td>'
        f'<td>{_celula(linha.get("Meta Consultivo"))}</td>'
        f'<td class="red-text">{_celula(linha.get("Projeção Consultivo"))}</td>'
        f'<td>{_celula(linha.get("Hoje Consultivo"))}</td>'
        f'<td>{_celula(linha.get("O.S. Consultivo"))}</td>'
        f'<td>{_celula(linha.get("Total O.S."))}</td>'
        f'<td>{_celula(linha.get("O.S. Aberta"))}</td>'
        f'<td>{_celula(linha.get("Pontos"))}</td>'
        f'<td>{_celula(linha.get("Efic (%)"), 1, percentual=True)}</td>'
        f'<td class="col-destaque-azul">{_celula(linha.get("Média O.S."), 2)}</td>'
        f'<td>{_celula(linha.get("O.S. Exec. (Proj)"))}</td>'
        f'<td class="col-destaque-amarelo">{_celula(linha.get("O.S. Sem Consult"))}</td>'
        f'<td>{_celula(linha.get("Quebra INS (%)"), 1, percentual=True)}</td>'
        f'<td>{_celula(linha.get("Quebra SERV (%)"), 1, percentual=True)}</td>'
        f'<td>{_celula(linha.get("Quebra ND (%)"), 1, percentual=True)}</td>'
        f'<td>{_celula(linha.get("ND"))}</td>'
        f'<td>{_celula(linha.get("O.S. Canc."))}</td>'
        f'<td>{_celula(linha.get("Saiu TOA"))}</td>'
        f'<td>{_celula(linha.get("Ganho O.S."))}</td>'
        f'<td>{_celula(linha.get("GPON Total"))}</td>'
        f'<td>{_celula(linha.get("GPON Quebra (%)"), 1, percentual=True)}</td>'
        f'<td>{_celula(linha.get("Migração Total"))}</td>'
        f'<td>{_celula(linha.get("Migração Quebra (%)"), 1, percentual=True)}</td>'
        f'<td>{_celula(linha.get("Migração Canc."))}</td>'
        f'<td>{_celula(linha.get("Retorno WO"))}</td>'
        f'<td>{_celula(linha.get("PME WO"))}</td>'
        f'<td>{_celula(linha.get("PME Quebra (%)"), 1, percentual=True)}</td>'
        f'<td>{_celula(linha.get("PME Canc."))}</td>'
        f'</tr>'
    )


def _render_tabela(
    linhas: list[dict[str, Any]],
    data_ref: str,
    brutos: dict[str, float] | None = None,
) -> None:
    """Tabela principal: uma linha por base e o total de instalação."""
    if not linhas:
        st.warning("Nenhuma base com dados para exibir.")
        return
    html = [_cabecalho_tabela(data_ref)]
    for linha in linhas:
        html.append(_linha_tabela(linha, "tr-base"))
    total = _total_das_linhas(linhas, brutos)
    total["Base"] = "TOTAL INSTALAÇÃO"
    html.append(_linha_tabela(total, "tr-total"))
    html.append("</tbody></table></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _render_detalhamento(detalhes: dict[str, Any], data_ref: str) -> None:
    """Blocos por base com a quebra de cada supervisor (somente sessão atual)."""
    st.markdown("### 🏢 Detalhamento operacional por base")
    consultivo = _consultivo_sessao()
    supervisores_consultivo = (consultivo or {}).get("supervisores", {})

    for base in previa.BASES_PREVIA:
        detalhe = detalhes.get(base)
        if not detalhe:
            continue
        with st.expander(
            f"📂 Base: {previa.ROTULOS_BASES[base]} (clique para expandir/recolher)"
        ):
            linha_base = dict(detalhe["linha"])
            html = [_cabecalho_tabela(data_ref), _linha_tabela(linha_base, "tr-base")]

            for supervisor in detalhe["supervisores"]:
                df_supervisor = (
                    detalhe["df_base"][
                        detalhe["df_base"]["Supervisor"].astype(str) == supervisor
                    ]
                    if "Supervisor" in detalhe["df_base"].columns
                    else pd.DataFrame()
                )
                montados_supervisor = _valor_sessao(
                    f"previa_m_{base}_{supervisor}", 20
                )
                parados_supervisor = _valor_sessao(f"previa_p_{base}_{supervisor}", 0)
                metricas_supervisor = previa.calcular_metricas_completas(
                    df_supervisor, montados_supervisor
                )

                dados_consultivo = {"contratos_hoje": 0, "produtos_hoje": 0, "produtos_mes": 0}
                primeiro_nome = previa.limpar_texto(supervisor.split()[0])
                for chave, valores in supervisores_consultivo.get(base, {}).items():
                    if chave.split()[0] in previa.limpar_texto(supervisor) or primeiro_nome in chave:
                        dados_consultivo = valores
                        break

                produtos_hoje = int(dados_consultivo.get("produtos_hoje", 0))
                linha_supervisor = {
                    "Base": supervisor.split()[0],
                    "Parados": parados_supervisor,
                    "Montados": montados_supervisor,
                    "Meta Consultivo": 350,
                    "Projeção Consultivo": int(dados_consultivo.get("produtos_mes", 0)),
                    "Hoje Consultivo": int(dados_consultivo.get("contratos_hoje", 0)),
                    "O.S. Consultivo": produtos_hoje,
                    "Total O.S.": metricas_supervisor["tot_os"],
                    "O.S. Aberta": metricas_supervisor["os_aberta"],
                    "Pontos": metricas_supervisor["pontos"],
                    "Efic (%)": metricas_supervisor["efic"],
                    "Média O.S.": metricas_supervisor["media_os"],
                    "O.S. Exec. (Proj)": metricas_supervisor["proj_dia"],
                    "O.S. Sem Consult": int(
                        round(metricas_supervisor["proj_dia"] - produtos_hoje, 0)
                    ),
                    "Quebra INS (%)": metricas_supervisor["q_ins"],
                    "Quebra SERV (%)": metricas_supervisor["q_serv"],
                    "Quebra ND (%)": metricas_supervisor["q_nd"],
                    "ND": metricas_supervisor["tot_nd"],
                    "O.S. Canc.": metricas_supervisor["os_canc"],
                    "Saiu TOA": metricas_supervisor["saiu_toa"],
                    "GPON Total": metricas_supervisor["tot_gpon"],
                    "GPON Quebra (%)": metricas_supervisor["q_gpon"],
                    "Migração Total": metricas_supervisor["tot_mig"],
                    "Migração Quebra (%)": metricas_supervisor["q_mig"],
                    "Migração Canc.": metricas_supervisor["canc_mig"],
                    "Retorno WO": metricas_supervisor["retorno_wo"],
                    "PME WO": metricas_supervisor["tot_pme"],
                    "PME Quebra (%)": metricas_supervisor["q_pme"],
                    "PME Canc.": metricas_supervisor["canc_pme"],
                }
                html.append(_linha_tabela(linha_supervisor, "tr-sup", indentado=True))

            html.append("</tbody></table></div>")
            st.markdown("".join(html), unsafe_allow_html=True)


# ====================================================
# 📊 BLOCO 8: PASSO 3 — PRÉVIA EXECUTIVA
# ====================================================
def _mostrar_feedback_sync() -> None:
    """Mostra uma vez o resultado da última sincronização (some no rerun seguinte)."""
    resultado = st.session_state.pop("previa_sync", None)
    if not isinstance(resultado, dict):
        return
    if resultado.get("ok"):
        st.success("✅ Histórico, equipe e prévia sincronizados com o Google Sheets.")
    else:
        st.warning(
            "Não foi possível gravar no Google Sheets "
            f"({resultado.get('mensagem', 'motivo desconhecido')}). "
            "A prévia desta sessão continua disponível na tela."
        )


def _linhas_do_historico(df_previas: pd.DataFrame, data_ref: str) -> list[dict[str, Any]]:
    """Linhas já persistidas na aba ``Previas_Diarias`` para a data escolhida."""
    if df_previas.empty or "Data" not in df_previas.columns:
        return []
    df_dia = df_previas[
        df_previas["Data"].astype(str).str.strip() == str(data_ref).strip()
    ]
    if df_dia.empty:
        return []
    linhas: list[dict[str, Any]] = []
    for _, registro in df_dia.iterrows():
        linha = {campo: registro.get(campo, "") for campo in COLUNAS_PREVIA}
        linhas.append(linha)
    return linhas


def _render_passo_3() -> None:
    """Apresentação da prévia: sessão atual ou data arquivada."""
    _mostrar_feedback_sync()
    df_previas = _ler_aba(ABA_PREVIAS)
    datas = previa.ordenar_datas(df_previas["Data"].dropna().tolist()) if "Data" in df_previas.columns else []

    opcoes = ["📌 Sessão atual (arquivos enviados)"] + datas
    escolha = st.selectbox(
        "Fonte da prévia",
        opcoes,
        key="previa_fonte",
        help="Datas anteriores vêm da aba Previas_Diarias da planilha.",
    )

    df_valido = st.session_state.get("previa_df_valido")
    data_ref = st.session_state.get("previa_data_ref") or datetime.now().strftime("%d/%m/%Y")
    dias_uteis = int(st.session_state.get("previa_dias_uteis", 25))

    if escolha != opcoes[0]:
        linhas = _linhas_do_historico(df_previas, escolha)
        if not linhas:
            st.warning(f"Nenhum registro encontrado em `{ABA_PREVIAS}` para **{escolha}**.")
            return
        st.caption(f"Prévia arquivada em {escolha} — leitura da planilha, sem recálculo.")
        _render_tabela(linhas, escolha)
        return

    if not isinstance(df_valido, pd.DataFrame) or df_valido.empty:
        st.warning(
            "⚠️ Nenhum arquivo processado nesta sessão. "
            "Volte ao Passo 1 ou selecione uma data arquivada acima."
        )
        return

    data_ref = st.session_state.get("previa_data_ref") or data_ref
    linhas, detalhes = _montar_linhas(
        df_valido,
        st.session_state.get("previa_df_full"),
        data_ref,
        dias_uteis,
    )
    _render_tabela(linhas, data_ref, _brutos_por_base(detalhes))
    st.markdown("<hr>", unsafe_allow_html=True)
    _render_detalhamento(detalhes, data_ref)

    df_full = st.session_state.get("previa_df_full")
    if isinstance(df_full, pd.DataFrame) and not df_full.empty:
        try:
            botao_download_planilha(
                df_full,
                nome_arquivo="Planilha_Tratada_Aniel",
                rotulo="📥 Baixar planilha ANIEL tratada (.xlsx)",
                chave="previa_download_aniel",
                aba="ANIEL",
            )
        except Exception as exc:  # noqa: BLE001 - download é acessório
            st.caption(f"Download da ANIEL tratada indisponível: {exc}")


# ====================================================
# 💾 BLOCO 9: SINCRONIZAÇÃO COM O GOOGLE SHEETS
# ====================================================
def _substituir_linhas(
    df_atual: pd.DataFrame,
    filtro: pd.Series,
    novas: list[dict[str, Any]],
    colunas: tuple[str, ...],
) -> pd.DataFrame:
    """Remove as linhas do filtro e acrescenta as novas, mantendo a ordem das colunas."""
    df_restante = df_atual[~filtro] if not df_atual.empty else df_atual
    df_novas = pd.DataFrame(novas)
    if df_novas.empty:
        resultado = df_restante
    else:
        resultado = pd.concat([df_restante, df_novas], ignore_index=True)
    for coluna in colunas:
        if coluna not in resultado.columns:
            resultado[coluna] = ""
    return resultado


def _sincronizar_planilha(df_valido: pd.DataFrame, data_ref: str, dias_uteis: int) -> None:
    """Grava histórico, equipe e prévia do dia nas abas do Google Sheets."""
    linhas, detalhes = _montar_linhas(
        df_valido, st.session_state.get("previa_df_full"), data_ref, dias_uteis
    )
    consultivo = _consultivo_sessao() or {}

    df_hist_os = _historico_os()
    filtro_os = pd.Series(False, index=df_hist_os.index)
    if not df_hist_os.empty:
        bases_norm = df_hist_os["Base"].apply(previa.normalizar_nome_base).str.upper()
        filtro_os = (df_hist_os["Data"].astype(str).str.strip() == str(data_ref).strip()) & (
            bases_norm.isin([base.upper() for base in previa.BASES_PREVIA])
        )
    novas_os = [
        {
            "Data": data_ref,
            "Base": base,
            "OS_Executadas": int(detalhe["metricas"]["produtivo"]),
            "OS_Inicial": _valor_sessao(
                f"previa_rota_{base}", previa.ROTA_INICIAL_PADRAO.get(base, 0)
            ),
        }
        for base, detalhe in detalhes.items()
        if detalhe["metricas"]["produtivo"] > 0
    ]
    if novas_os:
        df_hist_os = _substituir_linhas(df_hist_os, filtro_os, novas_os, COLUNAS_HIST_OS)
        _gravar_aba(ABA_HIST_OS, df_hist_os)

    # Sem arquivo de Consultivo no dia, não se grava nada: sobrescrever com zero
    # apagaria o histórico real daquela data na planilha.
    novas_consultivo: list[dict[str, Any]] = []
    if consultivo:
        historico_arquivo = consultivo.get("historico_diario", {})
        for base in previa.BASES_PREVIA:
            mapa_dias = historico_arquivo.get(base) or {
                data_ref: int(consultivo.get("hoje_produtos", {}).get(base, 0))
            }
            for data_dia, quantidade in mapa_dias.items():
                novas_consultivo.append(
                    {"Data": str(data_dia), "Base": base, "Qtd_Consultivo": int(quantidade)}
                )
    if novas_consultivo:
        df_hist_consultivo = _ler_aba(ABA_HIST_CONSULTIVO)
        for coluna in COLUNAS_HIST_CONSULTIVO:
            if coluna not in df_hist_consultivo.columns:
                df_hist_consultivo[coluna] = ""
        filtro_consultivo = pd.Series(False, index=df_hist_consultivo.index)
        if not df_hist_consultivo.empty:
            bases_norm = df_hist_consultivo["Base"].apply(previa.normalizar_nome_base).str.upper()
            datas_novas = {str(item["Data"]) for item in novas_consultivo}
            filtro_consultivo = df_hist_consultivo["Data"].astype(str).str.strip().isin(datas_novas) & (
                bases_norm.isin([base.upper() for base in previa.BASES_PREVIA])
            )
        df_hist_consultivo = _substituir_linhas(
            df_hist_consultivo, filtro_consultivo, novas_consultivo, COLUNAS_HIST_CONSULTIVO
        )
        _gravar_aba(ABA_HIST_CONSULTIVO, df_hist_consultivo)

    linhas_config: list[dict[str, Any]] = []
    linhas_equipe: list[dict[str, Any]] = []
    for base in previa.BASES_PREVIA:
        for supervisor in st.session_state.get("previa_supervisores", {}).get(base, []):
            montados = _valor_sessao(f"previa_m_{base}_{supervisor}", 20)
            parados = _valor_sessao(f"previa_p_{base}_{supervisor}", 0)
            linhas_config.append(
                {"Base": base, "Supervisor": supervisor, "Montados": montados, "Parados": parados}
            )
            linhas_equipe.append(
                {
                    "Data": data_ref,
                    "Base": previa.ROTULOS_BASES[base],
                    "Supervisor": supervisor,
                    "Montados": montados,
                    "Parados": parados,
                }
            )
    if linhas_config:
        _gravar_aba(ABA_CONFIG_EQUIPE, pd.DataFrame(linhas_config))

    if linhas_equipe:
        df_hist_equipe = _ler_aba(ABA_HIST_EQUIPE)
        for coluna in COLUNAS_HIST_EQUIPE:
            if coluna not in df_hist_equipe.columns:
                df_hist_equipe[coluna] = ""
        filtro_equipe = pd.Series(False, index=df_hist_equipe.index)
        if not df_hist_equipe.empty:
            filtro_equipe = (
                df_hist_equipe["Data"].astype(str).str.strip() == str(data_ref).strip()
            )
        df_hist_equipe = _substituir_linhas(
            df_hist_equipe, filtro_equipe, linhas_equipe, COLUNAS_HIST_EQUIPE
        )
        _gravar_aba(ABA_HIST_EQUIPE, df_hist_equipe)

    df_previas = _ler_aba(ABA_PREVIAS)
    for coluna in COLUNAS_PREVIA:
        if coluna not in df_previas.columns:
            df_previas[coluna] = ""
    rotulos = set(previa.ROTULOS_BASES.values())
    filtro_previa = pd.Series(False, index=df_previas.index)
    if not df_previas.empty:
        filtro_previa = (
            df_previas["Data"].astype(str).str.strip() == str(data_ref).strip()
        ) & (df_previas["Base"].isin(rotulos))
    df_previas = _substituir_linhas(df_previas, filtro_previa, linhas, COLUNAS_PREVIA)
    _gravar_aba(ABA_PREVIAS, df_previas)

    _ler_aba.clear()


# ====================================================
# 🧭 BLOCO 10: MONTAGEM DA PÁGINA
# ====================================================
def _render_guardas() -> bool:
    """Impede pular etapas sem os arquivos processados; devolve ``True`` se liberado."""
    if st.session_state.get("previa_passo") == PASSOS[0]:
        return True
    if isinstance(st.session_state.get("previa_df_valido"), pd.DataFrame):
        return True
    st.warning("⚠️ Processe os arquivos no Passo 1 para liberar esta etapa.")
    if st.button("Voltar ao upload", key="previa_btn_voltar_upload"):
        _navegar(PASSOS[0])
        st.rerun()
    return False


def main() -> None:
    """Desenha a página inteira (chamada no corpo do módulo)."""
    _iniciar_estado()
    _injetar_css()

    # Troca de etapa pedida no run anterior — aplicada antes do rádio existir.
    pendente = st.session_state.pop("previa_passo_pendente", "")
    if pendente in PASSOS:
        st.session_state["previa_passo"] = pendente

    render_hero_totale_2(
        "Prévia Diária",
        subtitulo=(
            "Produção, consultivo e quebras das bases ABCDM, Guarulhos e Leste "
            "no fechamento do dia."
        ),
        valor_destaque=st.session_state.get("previa_data_ref") or "—",
        label_destaque="DATA DE REFERÊNCIA",
        badge="DIRETORIA",
        icone="📆",
    )

    passo = st.radio(
        "Etapa",
        PASSOS,
        horizontal=True,
        key="previa_passo",
        label_visibility="collapsed",
    )

    if not _render_guardas():
        return

    st.markdown("---")
    if passo == PASSOS[0]:
        _render_passo_1()
    elif passo == PASSOS[1]:
        _render_passo_2()
    else:
        _render_passo_3()

    if st.session_state.get("previa_consultivo") and passo == PASSOS[0]:
        resultado = st.session_state["previa_consultivo"]
        render_insight(
            "Consultivo processado: "
            f"{previa.fmt_br(sum(resultado.get('acum_contratos', {}).values()))} contratos e "
            f"{previa.fmt_br(sum(resultado.get('acum_produtos', {}).values()))} produtos "
            "no acumulado do mês.",
            tipo="success",
            titulo="Consultivo",
        )


main()
