"""Lista de Presença — leitura e escrita localizada na grade absenteismo.

A grade é a fonte principal. A camada de análise usa registros virtuais por
login/dia. Nenhum fluxo desta página substitui a aba por registros longos.
As alterações são conferidas contra o snapshot remoto e enviadas por célula,
com auditoria no mesmo batchUpdate. Controle otimista não é CAS distribuído.
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.componentes import aplicar_estilo, render_empty_state, render_insight
from components.dashboards import abrir_dashboard, fechar_dashboard
from components.forca_trabalho import render_forca_trabalho
from components.graficos import (
    aplicar_tema,
    grafico_barras,
    grafico_calendario,
    grafico_donut,
    grafico_ranking,
    render_grafico,
)
from components.kpi_cards import SpecKPIAvancado, render_kpi_row
from components.layout_pagina import secao
from components.sidebar import render_page_sidebar_theme_selector
from config.settings import SHEET_ABA_ATIVOS, obter_sheet_id_ativos
from services.absenteismo import (
    ABREVIACOES_AUSENCIA,
    CHAVE_SESSAO_REGISTROS,
    DIAS_SEMANA_ABREVIADOS,
    JUSTIFICATIVAS,
    MESES_ABREVIADOS,
    STATUS_ATIVO,
    STATUS_CANCELADO,
    TIPOS_AUSENCIA,
    agrupar_registros,
    calcular_dias,
    fase_do_registro,
    filtrar_registros_periodo,
    normalizar_registros,
    resumir_controle,
    serie_diaria_ausencias,
)
from services.absenteismo_grade import (
    filtrar_grade_preenchimento,
)
from services.dados_sessao import resumir_carga, ultima_atualizacao
from services.forca_trabalho import calcular_forca_trabalho
from services.hierarquia import lista_ativos_da_sessao
from services.lista_presenca import (
    OPCOES_PRESENCA,
    OPCOES_STATUS_DIA,
    agrupar_colunas_dias_por_mes,
    agrupar_marcacoes_presenca,
    carregar_planilha_lista_presenca,
    gerar_excel_executivo_presenca,
    identificar_colunas_dias_planilha,
    montar_lista_presenca,
    montar_tabela_chamada_diaria,
    registros_da_chamada_diaria,
    registros_da_presenca,
    resumir_marcacoes_presenca,
    resumo_presenca,
)
from services.presenca_grade import (
    CHAVE_SNAPSHOT,
    carregar_grade_sessao,
    consultar_auditoria_grade,
    salvar_grade,
)
from services.presenca_operacoes import (
    assinatura,
    consultar_fechamentos,
    corrigir_dia,
    fechar_chamada,
    preparar_lote,
)
from services.texto import escapar_html, formatar_inteiro, formatar_percentual, normalizar_texto

logger = logging.getLogger(__name__)

#: Áreas de trabalho em ordem operacional, sem navegação para âncoras ocultas.
UNIDADES_NEGOCIO = ("ABCDM-TOTALE", "GRS-TOTALE", "SPO-TOTALLESTE")

AREAS_PAGINA = ("Planilha externa",)

CHAVES_FILTRO: tuple[str, ...] = (
    "absenteismo_periodo_inicio",
    "absenteismo_periodo_fim",
    "absenteismo_filtro_base",
    "absenteismo_filtro_monitor",
    "absenteismo_filtro_tipo",
    "absenteismo_busca",
    "absenteismo_incluir_cancelados",
)

#: Registros lançados sem persistência (sem credencial de escrita) nesta sessão.
CHAVE_PENDENTES = "presenca_grade_registros_pendentes"
#: IDs cancelados sem persistência nesta sessão (override sobre a leitura).
CHAVE_CANCELADOS_PENDENTES = "presenca_grade_cancelados_pendentes"

st.set_page_config(page_title="Lista de Presença | TOTALE", page_icon="🗓️", layout="wide")

aplicar_estilo()
render_page_sidebar_theme_selector()


# ============================================================
# CARGA: GRADE absenteismo + CADASTRO AUXILIAR lista_ativos
# ============================================================
def _carregar_registros() -> tuple[pd.DataFrame, int]:
    """Marcações da grade + pendentes desta sessão."""
    try:
        base = carregar_grade_sessao()
    except Exception as exc:
        st.error(f"Não foi possível ler a aba absenteismo: {exc}. Confira a conta de serviço e a permissão da planilha. Nenhum dado vazio será tratado como presença.")
        with st.expander("Configurar acesso local ao Google Sheets", expanded=True):
            st.markdown("**1.** Na raiz do projeto, crie o arquivo de configuração a partir do modelo:")
            st.code(r'if (!(Test-Path .streamlit\secrets.toml)) { Copy-Item .streamlit\secrets.example.toml .streamlit\secrets.toml }', language="powershell")
            st.markdown("**2.** No arquivo local, preencha a seção `[gcp_service_account]` com os dados do JSON da conta de serviço. Não cole essas credenciais no chat nem versione o arquivo.")
            st.markdown("**3.** Compartilhe a planilha com o `client_email` da conta de serviço como **Editor** e habilite a API Google Sheets no projeto Google Cloud.")
            st.markdown("**4.** Reinicie o Streamlit a partir da raiz do projeto:")
            st.code("streamlit run streamlit_app.py", language="powershell")
            st.caption("Alternativa: defina GOOGLE_APPLICATION_CREDENTIALS com o caminho de um JSON de conta de serviço guardado fora do repositório. A conexão Drive desta conversa não configura o Streamlit local.")
        st.stop()
    pendentes: list[dict] = st.session_state.get(CHAVE_PENDENTES, [])
    cancelados: set[str] = st.session_state.get(CHAVE_CANCELADOS_PENDENTES, set())

    registros = base
    if pendentes:
        brutos = pd.concat(
            [base.drop(columns=["_inicio", "_fim"], errors="ignore"), pd.DataFrame(pendentes)],
            ignore_index=True,
        )
        registros = normalizar_registros(brutos)
    if cancelados and not registros.empty:
        registros = registros.copy()
        registros.loc[registros["ID"].isin(cancelados), "Status"] = STATUS_CANCELADO
    return registros, len(pendentes)


def _persistir(registros: pd.DataFrame) -> bool:
    """Grava e mantém na sessão a versão confirmada, sem reler cache antigo."""
    base_confirmada = st.session_state.get(CHAVE_SESSAO_REGISTROS, normalizar_registros(None))
    snapshot = st.session_state.get(CHAVE_SNAPSHOT)
    if snapshot is None:
        st.error("Atualize a grade antes de salvar.")
        return False
    ok, motivo, confirmado = salvar_grade(snapshot, base_confirmada, registros)
    st.session_state["absenteismo_ultima_sync"] = {
        "ok": ok,
        "horario": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "motivo": motivo if not ok else "",
    }
    if ok:
        st.session_state.pop(CHAVE_PENDENTES, None)
        st.session_state.pop(CHAVE_CANCELADOS_PENDENTES, None)
        st.session_state[CHAVE_SNAPSHOT] = confirmado
        st.session_state[CHAVE_SESSAO_REGISTROS] = confirmado["registros"].copy()
    else:
        logger.warning("Controle de absenteísmo sem persistência: %s", motivo)
    return ok


def _primeiro_e_ultimo_dia_mes(hoje: date) -> tuple[date, date]:
    inicio = hoje.replace(day=1)
    fim = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return inicio, fim


registros, qtd_pendentes = _carregar_registros()
hoje = date.today()
datas_grade = st.session_state[CHAVE_SNAPSHOT]["dias"]
mes_inicio, mes_fim = _primeiro_e_ultimo_dia_mes(hoje if hoje in datas_grade else min(datas_grade))

# A lista da própria grade é o quadro da chamada; não cria linhas implicitamente.
quadro_df = st.session_state[CHAVE_SNAPSHOT]["pessoas"].rename(columns={
    "Login": "LOGIN", "Técnico": "TÉCNICO", "Monitor": "MONITOR", "Base": "BASE",
}).copy()
# A grade pode conter outras operações. Limitar a visão, sem alterar o
# snapshot completo usado para comparar e gravar as células no Drive.
quadro_df = quadro_df.loc[quadro_df["BASE"].map(normalizar_texto).isin(UNIDADES_NEGOCIO)].copy()
logins_unidades = set(quadro_df["LOGIN"])

abrir_dashboard(
    "Lista de Presença",
    subtitulo=(
        "Presença diária, faltas, folgas, férias e afastamentos do quadro "
        "— leitura e preenchimento direto na aba absenteismo."
    ),
    icone="🗓️",
    secoes=(),
    resumo=resumir_carga(registros.loc[registros["Login"].isin(logins_unidades)], atualizado_em=ultima_atualizacao()),
    origem="absenteismo (grade mensal) · cadastro auxiliar: lista_ativos",
)

st.caption(
    f"Fonte principal: aba absenteismo · datas de {min(datas_grade):%d/%m/%Y} a {max(datas_grade):%d/%m/%Y}. "
    "A visão usa a base atual do cadastro para limitar as três unidades. Presente é gravado como ATIVO. Somente células alteradas são atualizadas; cadastros, fórmulas e formatação permanecem intactos."
)

def _render_qualidade_origem() -> None:
    lista_ativos = lista_ativos_da_sessao(aba=SHEET_ABA_ATIVOS, ttl=600)
    qualidade_origem = lista_ativos.attrs.get("qualidade_origem")
    if qualidade_origem:
        with st.expander("Qualidade da lista de ativos", expanded=bool(qualidade_origem["ocorrencias"])):
            c_origem, c_validos, c_pendencias = st.columns(3)
            c_origem.metric("Linhas na origem", qualidade_origem["linhas_origem"])
            c_validos.metric("Logins únicos preenchidos", qualidade_origem["logins_validos"])
            c_pendencias.metric("Ocorrências para revisar", len(qualidade_origem["ocorrencias"]))
            st.caption("Diagnóstico da carga completa, antes dos filtros e da deduplicação. Uma linha pode ter mais de uma ocorrência; o número de logins não representa o quadro ativo.")
            if qualidade_origem["ocorrencias"]:
                st.warning("Há cadastros para revisar na planilha. Linhas sem login não entram na lista; RE repetido não une técnicos automaticamente.")
                st.dataframe(pd.DataFrame(qualidade_origem["ocorrencias"]), hide_index=True, width="stretch")
            else:
                st.success("Nenhuma inconsistência detectada nas verificações cadastrais.")
            if qualidade_origem["ultima_modificacao_cadastral"]:
                st.caption("Maior data informada em Ultima_Modificacao: " + qualidade_origem["ultima_modificacao_cadastral"] + ". Esse campo é cadastral e não confirma a data da última presença.")


for tipo_flash, texto_flash in st.session_state.pop("absenteismo_flash", []):
    if tipo_flash == "sucesso":
        st.success(texto_flash)
    elif tipo_flash == "alerta":
        st.warning(texto_flash)
    else:
        st.error(texto_flash)

if qtd_pendentes:
    render_insight(
        f"**{formatar_inteiro(qtd_pendentes)} registro(s)** estão salvos **somente "
        "nesta sessão**: a gravação na planilha falhou (credencial de escrita "
        "`[gcp_service_account]` ausente ou sem permissão na planilha). Eles "
        "aparecem nas análises, mas se perdem ao fechar a sessão — exporte a "
        "aba Registros do Controle se precisar guardar.",
        tipo="alerta",
        titulo="Lançamentos não sincronizados",
    )

if qtd_pendentes:
    if st.button("Tentar sincronizar pendências com o Drive", key="absenteismo_sincronizar"):
        if _persistir(registros):
            st.session_state["absenteismo_flash"] = [
                ("sucesso", "Pendências gravadas na planilha do Drive.")
            ]
            st.rerun()
        else:
            st.error("Não foi possível sincronizar. Confira a conta de serviço e a permissão de edição da planilha. Os dados continuam somente nesta sessão.")

# ============================================================
# FILTROS (SIDEBAR)
# ============================================================
# Migra seleções de versões anteriores (inclusive diferenças de caixa) antes
# de instanciar o widget; opções antigas não podem derrubar a página no rerun.
if "absenteismo_filtro_base" in st.session_state:
    st.session_state["absenteismo_filtro_base"] = [
        valor for valor in dict.fromkeys(
            normalizar_texto(v) for v in st.session_state["absenteismo_filtro_base"]
        ) if valor in UNIDADES_NEGOCIO
    ]
bases_sel = st.multiselect(
    "Unidade de negócio", UNIDADES_NEGOCIO, key="absenteismo_filtro_base",
    placeholder="Todas as unidades",
    help="O filtro vale para todas as áreas e suas exportações; somente as três unidades autorizadas são exibidas.",
)
st.caption("Unidades selecionadas: " + (", ".join(bases_sel) if bases_sel else "Todas as unidades"))

with st.sidebar:
    st.markdown("### Filtros da equipe")
    st.caption("Base, monitor e busca afetam todas as áreas. O período define o mês do mapa. O filtro de tipo afeta apenas análises e histórico.")
    periodo_inicio = st.date_input(
        "Início do período de análise", value=mes_inicio, key="absenteismo_periodo_inicio"
    )
    periodo_fim = st.date_input("Fim do período de análise", value=mes_fim, key="absenteismo_periodo_fim")
    if periodo_fim < periodo_inicio:
        periodo_inicio, periodo_fim = periodo_fim, periodo_inicio
    monitores_disponiveis = sorted(
        set(registros.loc[registros["Login"].isin(logins_unidades), "Monitor"].replace("", "Não informado"))
        | set(quadro_df["MONITOR"].replace("", "Não informado"))
    )
    monitores_sel = st.multiselect(
        "Monitor",
        monitores_disponiveis,
        key="absenteismo_filtro_monitor",
    )
    tipos_sel = st.multiselect("Tipo de ausência", list(TIPOS_AUSENCIA), key="absenteismo_filtro_tipo")
    busca = st.text_input(
        "Buscar técnico ou login", key="absenteismo_busca", placeholder="Nome ou login…"
    )
    incluir_cancelados = st.checkbox(
        "Exibir também presenças e situações operacionais", key="absenteismo_incluir_cancelados"
    )
    if st.button("Limpar filtros", key="absenteismo_limpar_filtros"):
        for chave in CHAVES_FILTRO:
            st.session_state.pop(chave, None)
        st.rerun()
    if st.button("🔄 Atualizar registros e quadro", key="absenteismo_atualizar"):
        carregar_grade_sessao(forcar=True)
        st.session_state.pop("totale_lista_ativos", None)
        st.rerun()


def _aplicar_recorte(df: pd.DataFrame) -> pd.DataFrame:
    """Recorte da sidebar (base/monitor/tipo/busca) sobre os registros."""
    recorte = df.loc[df["Login"].isin(logins_unidades)].copy()
    if bases_sel:
        logins_base = set(quadro_df.loc[quadro_df["BASE"].map(normalizar_texto).isin(bases_sel), "LOGIN"])
        recorte = recorte[recorte["Login"].isin(logins_base)]
    if monitores_sel:
        recorte = recorte[recorte["Monitor"].replace("", "Não informado").isin(monitores_sel)]
    if tipos_sel:
        recorte = recorte[recorte["Tipo"].isin(tipos_sel)]
    if busca.strip():
        termo = busca.strip().casefold()
        alvo = recorte["Técnico"].str.casefold() + " " + recorte["Login"].str.casefold()
        recorte = recorte[alvo.str.contains(termo, regex=False)]
    return recorte


registros_recorte = _aplicar_recorte(registros)
resumo = resumir_controle(
    registros_recorte, periodo_inicio=periodo_inicio, periodo_fim=periodo_fim, hoje=hoje
)

# Quadro no mesmo recorte de base/monitor (denominador da taxa do período).
quadro_recorte = quadro_df
if bases_sel:
    quadro_recorte = quadro_recorte[
        quadro_recorte["BASE"].map(normalizar_texto).isin(bases_sel)
    ]
if monitores_sel:
    quadro_recorte = quadro_recorte[
        quadro_recorte["MONITOR"].replace("", "Não informado").isin(monitores_sel)
    ]
qtd_quadro = len(quadro_recorte)
_, dias_uteis_no_periodo = calcular_dias(periodo_inicio, periodo_fim)
taxa_periodo = (
    resumo["dias_uteis_periodo"] / (qtd_quadro * dias_uteis_no_periodo)
    if qtd_quadro and dias_uteis_no_periodo
    else 0.0
)


def _cadastro_por_login(coluna: str) -> dict[str, str]:
    """Coluna de cadastro (RE/U.N.) do quadro indexada pelo login."""
    if quadro_df.empty or coluna not in quadro_df.columns:
        return {}
    return dict(zip(quadro_df["LOGIN"], quadro_df[coluna].fillna("").astype(str)))


CADASTRO_RE = _cadastro_por_login("RE")
CADASTRO_UN = _cadastro_por_login("U.N.")


def _tabela_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    """Registros para leitura/exportação (identidade + datas BR + fase)."""
    colunas = [
        "RE", "Login", "Técnico", "Monitor", "Base", "U.N.", "Tipo", "Início", "Fim",
        "Dias Corridos", "Dias Úteis", "Justificativa", "Motivo", "Fase",
        "Status", "Registrado em",
    ]
    if df.empty:
        return pd.DataFrame(columns=colunas)
    tabela = df.copy()
    tabela["Início"] = tabela["_inicio"].dt.strftime("%d/%m/%Y")
    tabela["Fim"] = tabela["_fim"].dt.strftime("%d/%m/%Y")
    tabela["Fase"] = [fase_do_registro(linha, hoje) for linha in tabela.to_dict("records")]
    tabela["RE"] = tabela["Login"].map(CADASTRO_RE).fillna("")
    tabela["U.N."] = tabela["Login"].map(CADASTRO_UN).fillna("")
    return tabela[colunas].sort_values(["Início", "Técnico"]).reset_index(drop=True)


# ============================================================
# MAPA MENSAL (TÉCNICO × DIA) — MESMO FORMATO DA PLANILHA
# ============================================================
#: Cores de cada código na célula (fundo, texto) — legenda abaixo do mapa.
_CODIGOS_MAPA = {**ABREVIACOES_AUSENCIA, "Presente": "P", "Não preenchido": "NP"}

_CORES_MAPA: dict[str, tuple[str, str]] = {
    "P": ("#DCFCE7", "#166534"),
    "NP": ("#F8FAFC", "#64748B"),
    "F": ("#FEE2E2", "#991B1B"),
    "FO": ("#DBEAFE", "#1E40AF"),
    "FE": ("#FEF3C7", "#92400E"),
    "AT": ("#EDE9FE", "#5B21B6"),
    "AF": ("#E5E7EB", "#374151"),
    "LI": ("#CCFBF1", "#115E59"),
    "SU": ("#FCE7F3", "#9D174D"),
    "TR": ("#DCFCE7", "#166534"),
    "OUT": ("#F1F5F9", "#334155"),
}


def _injetar_css_mapa() -> None:
    """CSS local do mapa mensal (tabela densa com cabeçalho/colunas fixas)."""
    st.markdown(
        """
        <style>
        .abs-mapa-wrap {
            background: #fff; color-scheme: light; border: 1px solid #E6EDF5;
            border-radius: 14px; box-shadow: 0 8px 24px rgba(15,23,42,0.04);
            overflow: hidden; margin: 8px 0 10px;
        }
        .abs-mapa-scroll { max-height: 620px; overflow: auto; scrollbar-width: thin; }
        .abs-mapa {
            border-collapse: separate; border-spacing: 0; width: max-content; min-width: 100%;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 11px;
        }
        .abs-mapa th, .abs-mapa td {
            border-right: 1px solid #EDF2F7; border-bottom: 1px solid #EDF2F7;
            padding: 4px 6px; text-align: center; white-space: nowrap; background: #fff;
        }
        .abs-mapa thead th {
            position: sticky; top: 0; z-index: 3; background: #F8FAFC; color: #012869;
            font-weight: 800; font-size: 10px; letter-spacing: .02em; line-height: 1.15;
            border-bottom: 1px solid #D8E2EE;
        }
        .abs-mapa thead th span {
            display: block; font-size: 8.5px; font-weight: 700; color: #94A3B8;
            text-transform: uppercase; margin-top: 1px;
        }
        .abs-mapa td { height: 27px; color: #1E293B; }
        .abs-mapa td.abs-cel { width: 30px; min-width: 30px; padding: 2px; font-size: 10px; font-weight: 800; }
        .abs-mapa td.abs-vazia { background: #fff; }
        .abs-mapa th.abs-fds { background: #F1F5F9 !important; }
        .abs-mapa td.abs-fds.abs-vazia { background: #F1F5F9 !important; }
        .abs-mapa th.abs-hoje { box-shadow: inset 0 -3px 0 #F37C04; color: #9A3412; }
        .abs-mapa td.abs-hoje { box-shadow: inset 0 0 0 1.5px #F37C04; }
        .abs-mapa td.abs-nome, .abs-mapa th.abs-nome { text-align: left; }
        .abs-mapa td.abs-nome {
            text-transform: uppercase; font-size: 10.5px; font-weight: 700; color: #1E293B;
            max-width: 210px; overflow: hidden; text-overflow: ellipsis;
        }
        .abs-mapa td.abs-dim {
            text-align: left; text-transform: uppercase; font-size: 9.5px; color: #475569;
            max-width: 150px; overflow: hidden; text-overflow: ellipsis;
        }
        .abs-mapa td.abs-re { font-weight: 800; color: #012869; font-variant-numeric: tabular-nums; }
        .abs-mapa td.abs-login { color: #475569; font-variant-numeric: tabular-nums; }
        .abs-mapa th.col-re, .abs-mapa td.col-re {
            position: sticky; left: 0; z-index: 2; width: 56px; min-width: 56px; max-width: 56px;
        }
        .abs-mapa th.col-login, .abs-mapa td.col-login {
            position: sticky; left: 56px; z-index: 2; width: 86px; min-width: 86px; max-width: 86px;
        }
        .abs-mapa th.col-tec, .abs-mapa td.col-tec {
            position: sticky; left: 142px; z-index: 2; width: 210px; min-width: 210px;
            max-width: 210px;
        }
        .abs-mapa td.col-tec { box-shadow: 2px 0 5px rgba(15,23,42,.06); }
        .abs-mapa thead th.col-re, .abs-mapa thead th.col-login,
        .abs-mapa thead th.col-tec { z-index: 5; }
        .abs-mapa th.col-total, .abs-mapa td.col-total {
            position: sticky; right: 0; z-index: 2; width: 50px; min-width: 50px;
            background: #FFF7ED; color: #9A3412; font-weight: 900;
        }
        .abs-mapa thead th.col-total { z-index: 5; }
        .abs-mapa tr.abs-nova-base td { border-top: 2px solid #CBD5E1; }
        .abs-mapa tfoot td {
            position: sticky; bottom: 0; z-index: 2; background: #F8FAFC;
            color: #012869; font-weight: 800; font-size: 10px;
        }
        .abs-mapa tfoot td.abs-rodape-rotulo { text-align: left; letter-spacing: .03em; }
        .abs-legenda { display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 4px 0 10px; }
        .abs-legenda-item { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: #475569; }
        .abs-legenda-codigo {
            display: inline-flex; align-items: center; justify-content: center;
            min-width: 26px; height: 19px; padding: 0 4px; border-radius: 5px;
            font-size: 9.5px; font-weight: 800;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _rotulo_dia(dia: date) -> str:
    """Cabeçalho da coluna como na planilha: ``1/nov.``."""
    return f"{dia.day}/{MESES_ABREVIADOS[dia.month - 1]}"


def _truncar_mapa(valor: object, limite: int) -> str:
    """Texto curto para a célula (o valor completo fica no ``title``)."""
    texto = str(valor or "").strip()
    return texto if len(texto) <= limite else f"{texto[: limite - 1]}…"


def _colunas_dia_mapa(matriz: pd.DataFrame) -> list[date]:
    """Colunas de dia da matriz (objetos ``date``), na ordem do DataFrame."""
    dias: list[date] = []
    for coluna in matriz.columns:
        if isinstance(coluna, (date, datetime, pd.Timestamp)):
            dias.append(pd.Timestamp(coluna).date())
    return dias


def _celula_mapa(valor: object) -> str:
    """Célula com código e descrição; ausência de marca nunca implica presença."""
    codigo = str(valor or "").strip()
    if not codigo:
        return '<td class="abs-cel abs-vazia"></td>'
    primeiro = codigo.split("/")[0].strip().upper()
    fundo, cor = _CORES_MAPA.get(primeiro, _CORES_MAPA["OUT"])
    descricoes = {v: k for k, v in _CODIGOS_MAPA.items()}
    titulo = escapar_html(" / ".join(descricoes.get(c, c) for c in codigo.split("/")), aspas=True)
    return (
        f'<td class="abs-cel" style="background:{fundo};color:{cor}" title="{titulo}">'
        f"{escapar_html(codigo)}</td>"
    )


def _mapa_para_excel(matriz: pd.DataFrame) -> bytes:
    """Matriz com os dias no cabeçalho da planilha (``1/nov.``) em xlsx."""
    exportar = matriz.copy()
    exportar = exportar.rename(
        columns={dia: _rotulo_dia(dia) for dia in _colunas_dia_mapa(matriz)}
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        exportar.to_excel(writer, index=False, sheet_name="Mapa")
    return buffer.getvalue()


def _render_mapa_mensal(
    matriz: pd.DataFrame, inicio: date, fim: date
) -> None:
    """Renderiza a grade mensal com legenda, totais e download do xlsx."""
    dias = _colunas_dia_mapa(matriz)
    _injetar_css_mapa()

    st.caption("Fonte: grade absenteismo. Para editar, use a área Chamada diária.")
    st.caption(
        f"Período do mapa: **{_rotulo_dia(inicio)} a {_rotulo_dia(fim)}** "
        f"({len(dias)} dias) · usa o mês do início do período · "
        "P = **Presente** · NP = **Não preenchido**, nunca presença presumida · "
        "passe o mouse na célula para ver o tipo completo."
    )

    ths = [
        '<th class="col-re" scope="col">RE</th>',
        '<th class="col-login" scope="col">Login</th>',
        '<th class="col-tec abs-nome" scope="col">Técnico</th>',
        '<th class="abs-nome" scope="col">Monitor</th>',
        '<th class="abs-nome" scope="col">Base</th>',
        '<th class="abs-nome" scope="col">U.N.</th>',
    ]
    hoje = date.today()
    for dia in dias:
        classes = ["abs-dia"]
        if dia.weekday() >= 5:
            classes.append("abs-fds")
        if dia == hoje:
            classes.append("abs-hoje")
        ths.append(
            f'<th class="{" ".join(classes)}" scope="col" '
            f'title="{DIAS_SEMANA_ABREVIADOS[dia.weekday()]}">{_rotulo_dia(dia)}'
            f"<span>{DIAS_SEMANA_ABREVIADOS[dia.weekday()]}</span></th>"
        )
    ths.append('<th class="col-total" scope="col">Dias</th>')

    linhas_html: list[str] = []
    base_anterior = ""
    for _, pessoa in matriz.iterrows():
        base_atual = str(pessoa.get("Base", ""))
        nova_base = bool(base_anterior) and base_atual != base_anterior
        base_anterior = base_atual
        tds = [
            f'<td class="col-re abs-re">{escapar_html(pessoa.get("RE", ""))}</td>',
            f'<td class="col-login abs-login">{escapar_html(pessoa.get("Login", ""))}</td>',
            f'<td class="col-tec abs-nome" title="{escapar_html(pessoa.get("Técnico", ""), aspas=True)}">'
            f'{escapar_html(_truncar_mapa(pessoa.get("Técnico", ""), 30))}</td>',
            f'<td class="abs-dim" title="{escapar_html(pessoa.get("Monitor", ""), aspas=True)}">'
            f'{escapar_html(_truncar_mapa(pessoa.get("Monitor", ""), 22))}</td>',
            f'<td class="abs-dim" title="{escapar_html(pessoa.get("Base", ""), aspas=True)}">'
            f'{escapar_html(_truncar_mapa(pessoa.get("Base", ""), 16))}</td>',
            f'<td class="abs-dim" title="{escapar_html(pessoa.get("U.N.", ""), aspas=True)}">'
            f'{escapar_html(_truncar_mapa(pessoa.get("U.N.", ""), 14))}</td>',
        ]
        for dia in dias:
            classe_extra = ""
            if dia.weekday() >= 5:
                classe_extra = " abs-fds"
            if dia == hoje:
                classe_extra += " abs-hoje"
            celula = _celula_mapa(pessoa.get(dia, ""))
            if classe_extra:
                celula = celula.replace('class="abs-cel', f'class="abs-cel{classe_extra}', 1)
            tds.append(celula)
        total_bruto = pessoa.get("Total", 0)
        total = 0 if pd.isna(total_bruto) else int(total_bruto)
        tds.append(f'<td class="col-total">{total if total else ""}</td>')
        linhas_html.append(
            f'<tr class="abs-nova-base">{"".join(tds)}</tr>'
            if nova_base
            else f"<tr>{''.join(tds)}</tr>"
        )

    totais_dia = [
        int((~matriz[dia].fillna("").astype(str).str.strip().isin(["", "NP"])).sum())
        if dia in matriz
        else 0
        for dia in dias
    ]
    total_geral = sum(totais_dia)
    rodape = (
        '<tr><td class="abs-rodape-rotulo" colspan="6">TOTAL DE MARCAÇÕES '
        "(técnicos/dia)</td>"
        + "".join(f"<td>{valor if valor else ''}</td>" for valor in totais_dia)
        + f'<td class="col-total">{total_geral if total_geral else ""}</td></tr>'
    )

    st.markdown(
        '<div class="abs-mapa-wrap"><div class="abs-mapa-scroll">'
        '<table class="abs-mapa"><thead><tr>'
        + "".join(ths)
        + "</tr></thead><tbody>"
        + "".join(linhas_html)
        + "</tbody><tfoot>"
        + rodape
        + "</tfoot></table></div></div>",
        unsafe_allow_html=True,
    )

    st.caption(
        "Para editar, use **Chamada diária**. Totais contam dias preenchidos, incluindo presença e situações operacionais; NP não entra na contagem."
    )

    legenda = "".join(
        f'<span class="abs-legenda-item">'
        f'<span class="abs-legenda-codigo" style="background:{_CORES_MAPA.get(codigo, _CORES_MAPA["OUT"])[0]};'
        f'color:{_CORES_MAPA.get(codigo, _CORES_MAPA["OUT"])[1]}">{codigo}</span>'
        f"{escapar_html(tipo)}</span>"
        for tipo, codigo in _CODIGOS_MAPA.items()
    )
    st.markdown(f'<div class="abs-legenda">{legenda}</div>', unsafe_allow_html=True)

    coluna_download, _ = st.columns([1, 3])
    with coluna_download:
        st.download_button(
            "⬇️ Baixar mapa em Excel",
            data=_mapa_para_excel(matriz),
            file_name=f"mapa_absenteismo_{inicio:%Y_%m}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="absenteismo_mapa_download",
            width="stretch",
            help="Baixa a grade exatamente como está na tela (códigos por dia).",
        )


def _render_acoes_presenca(matriz: pd.DataFrame, dia: date) -> None:
    """Ações explícitas sobre o recorte diário, antes do filtro só pendentes."""
    diario = filtrar_grade_preenchimento(matriz, [dia])
    diario["Total"] = diario[dia].ne("Não preenchido").astype(int)
    diario_exportar = diario.rename(columns={dia: "Situação"}).drop(columns="Total")
    diario_exportar["Data"] = dia.strftime("%d/%m/%Y")
    diario_exportar["Gerado em"] = datetime.now().isoformat(timespec="seconds")
    arquivo = io.BytesIO()
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        diario_exportar.to_excel(writer, index=False, sheet_name="Chamada diária")
    st.download_button(
        "Baixar lista diária em Excel", arquivo.getvalue(),
        file_name=f"lista_presenca_{dia:%Y_%m_%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="presenca_exportar_dia", help="Data, U.N., monitor e busca atuais; inclui todas as situações do recorte.",
    )
    sync = st.session_state.get("absenteismo_ultima_sync")
    if qtd_pendentes:
        st.warning(f"Pendente de sincronização · {qtd_pendentes} lançamento(s) apenas nesta sessão.")
    elif sync:
        if sync["ok"]:
            st.success(f"Salvo no Drive · {sync['horario']}")
        else:
            st.error(f"Envio não confirmado · {sync['horario']} · {sync['motivo']}")
    else:
        st.caption("Nenhum envio realizado nesta sessão. As marcações exibidas não confirmam atualização em tempo real.")
    lote, correcao, fechamento = st.tabs(["Preencher em lote", "Corrigir com histórico", "Fechar chamada"])
    with lote:
        pendentes = diario.loc[diario[dia].eq("Não preenchido")]
        rotulos = dict(zip(pendentes["Login"], pendentes["Técnico"]))
        with st.form("presenca_lote_form"):
            selecionados = st.multiselect("Técnicos pendentes", list(rotulos), format_func=lambda x: f"{rotulos[x]} · {x}")
            situacao = st.selectbox("Situação para o lote", OPCOES_PRESENCA[1:])
            autor = st.text_input("Responsável pelo lote")
            confirmar = st.checkbox(f"Confirmo aplicar a situação escolhida aos técnicos selecionados em {dia:%d/%m/%Y}")
            enviar = st.form_submit_button("Confirmar lote")
        if enviar:
            try:
                if not confirmar or not autor.strip():
                    raise ValueError("Informe o responsável e confirme o lote.")
                novos = preparar_lote(diario, dia, selecionados, situacao)
                for novo in novos:
                    novo["Motivo"] = f"Lote por {autor.strip()}"
                atualizados = normalizar_registros(pd.concat([
                    registros.drop(columns=["_inicio", "_fim"], errors="ignore"), pd.DataFrame(novos)
                ], ignore_index=True))
                with st.spinner("Conferindo e salvando lote…"):
                    ok = _persistir(atualizados)
                if ok:
                    st.session_state["absenteismo_flash"] = [("sucesso", f"Lote de {len(novos)} marcações salvo.")]
                    st.rerun()
                else:
                    st.error("Lote não confirmado. Nenhuma seleção foi assumida como salva; confira o status e tente novamente.")
            except ValueError as exc:
                st.error(str(exc))
    with correcao:
        marcados = diario.loc[diario[dia].ne("Não preenchido")]
        rotulos_correcao = {r["Login"]: f"{r['Técnico']} · {r[dia]}" for _, r in marcados.iterrows()}
        with st.form("presenca_correcao_form"):
            login = st.selectbox("Marcação para corrigir", list(rotulos_correcao), format_func=lambda x: rotulos_correcao[x])
            nova = st.selectbox("Nova situação", OPCOES_PRESENCA[1:])
            responsavel = st.text_input("Responsável pela correção")
            motivo = st.text_area("Motivo obrigatório")
            corrigir = st.form_submit_button("Salvar correção com histórico", disabled=marcados.empty)
        if corrigir:
            try:
                alterados = corrigir_dia(registros, login, dia, nova, motivo, responsavel)
                with st.spinner("Conferindo e gravando correção…"):
                    ok = _persistir(alterados)
                if ok:
                    st.session_state["absenteismo_flash"] = [("sucesso", "Correção salva na grade; valores anterior e novo registrados em auditoria_presenca.")]
                    st.rerun()
                else:
                    st.error("Correção não confirmada. Confira o status de sincronização; o histórico local não foi alterado.")
            except ValueError as exc:
                st.error(str(exc))
        st.caption("A célula é corrigida na grade. O valor anterior, novo valor e motivo ficam em auditoria_presenca; os demais dias são preservados.")
        with st.expander("Histórico de alterações da grade"):
            st.caption("Consulta os valores anteriores e novos registrados em auditoria_presenca para o dia e a equipe selecionados.")
            if st.button("Consultar auditoria da grade", key="presenca_auditoria_grade"):
                try:
                    historico = consultar_auditoria_grade(dia, diario["Login"].tolist())
                    if historico.empty:
                        st.info("Nenhuma alteração pelo painel foi registrada neste recorte.")
                    else:
                        st.dataframe(historico, hide_index=True, width="stretch")
                except Exception as exc:
                    st.error(f"Não foi possível consultar a auditoria: {exc}")
    with fechamento:
        resumo_fechamento = resumo_presenca(diario, dia)
        st.write(f"{dia:%d/%m/%Y} · {len(diario)} técnicos · " + " · ".join(f"{k}: {v}" for k, v in resumo_fechamento.items()))
        st.caption("U.N.: " + ", ".join(sorted(diario["U.N."].replace("", "Não informado").unique())) + " · Monitor: " + ", ".join(sorted(diario["Monitor"].replace("", "Não informado").unique())))
        st.caption("O fechamento registra um retrato deste recorte no Drive, sem bloquear futuras correções. Responsável informado é declaratório, não autenticação.")
        with st.form("presenca_fechar_form"):
            responsavel_fecha = st.text_input("Responsável pelo fechamento")
            confirma_pendencias = st.checkbox("Confirmo concluir mesmo com pendências")
            confirma_fecha = st.checkbox("Conferi a data, a equipe e os totais acima")
            concluir = st.form_submit_button("Concluir chamada")
        if concluir:
            try:
                if not confirma_fecha:
                    raise ValueError("Confirme a conferência da chamada.")
                if qtd_pendentes:
                    raise ValueError("Sincronize os lançamentos pendentes antes de fechar.")
                with st.spinner("Conferindo dados remotos e registrando fechamento…"):
                    evento = fechar_chamada(diario, dia, responsavel_fecha, confirma_pendencias, fonte_grade=True)
                st.session_state["presenca_ultimo_fechamento"] = evento
            except Exception as exc:
                st.error(f"Fechamento não confirmado: {exc}")
        ultimo = st.session_state.get("presenca_ultimo_fechamento")
        if ultimo and ultimo["Data"] == dia.isoformat():
            if ultimo["Assinatura"] == assinatura(diario[["Login", dia]]):
                st.success(f"Fechamento registrado no Drive por {ultimo['Responsável']} às {ultimo['Horário']}.")
            else:
                st.warning("O recorte ou as marcações mudaram desde o último fechamento. Conclua novamente para registrar a nova versão.")
        if st.button("Consultar fechamentos desta data no Drive", key="presenca_consultar_fechamentos"):
            try:
                with st.spinner("Consultando histórico de fechamentos…"):
                    historico = consultar_fechamentos(dia)
                if historico.empty:
                    st.info("Nenhum fechamento encontrado para esta data.")
                else:
                    st.dataframe(historico, hide_index=True, width="stretch")
            except Exception as exc:
                st.error(f"Não foi possível consultar os fechamentos: {exc}")


def _css_tabela_chamada_compacta() -> None:
    """Aproxima o editor diário da grade operacional: bordas finas e linhas compactas."""
    st.markdown(
        """
        <style>
        [data-testid="stMain"] [data-testid="stDataEditor"] {
            border: 1px solid #9ca3af !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }
        [data-testid="stMain"] [data-testid="stDataEditor"] [role="columnheader"] {
            background-color: #f3f4f6 !important;
            color: #111827 !important;
            font-size: 12px !important;
            font-weight: 600 !important;
        }
        [data-testid="stMain"] [data-testid="stDataEditor"] [role="gridcell"] {
            font-size: 12px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_preenchimento_mapa(matriz: pd.DataFrame) -> None:
    """Editor com identidade protegida e salvamento automático por seleção."""
    st.markdown("#### Chamada da equipe")
    st.caption("Escolha a data, localize sua equipe e registre a situação. Cada seleção é salva automaticamente.")
    dias_mes = _colunas_dia_mapa(matriz)
    hoje_editor = date.today()
    dia_padrao = hoje_editor if hoje_editor in dias_mes else dias_mes[0]
    with st.container(border=True):
        col_data, col_unidade, col_monitor = st.columns([1, 1.4, 1.4])
        with col_data:
            dia_resumo = st.selectbox(
                "Data da chamada", dias_mes, index=dias_mes.index(dia_padrao),
                format_func=lambda d: f"{d:%d/%m/%Y} · {DIAS_SEMANA_ABREVIADOS[d.weekday()]}",
                key=f"presenca_data_{dias_mes[0]:%Y_%m}",
            )
        with col_unidade:
            unidades = st.multiselect(
                "U.N. cadastral",
                sorted(matriz["U.N."].fillna("").astype(str).str.strip().replace("", "Não informado").unique()),
                placeholder="Todas as unidades", key="absenteismo_grade_unidades",
            )
        with col_monitor:
            monitores = st.multiselect(
                "Monitor",
                sorted(matriz["Monitor"].fillna("").astype(str).str.strip().replace("", "Não informado").unique()),
                placeholder="Todos os monitores", key="absenteismo_grade_monitores",
            )
        col_busca, col_visual = st.columns([2, 1])
        with col_busca:
            busca_editor = st.text_input(
                "Localizar técnico", placeholder="Digite nome ou login…", key="presenca_busca_editor",
            )
        with col_visual:
            visualizacao = st.selectbox(
                "Visualização", ["Chamada do dia", "Preenchimento por período"], key="presenca_visualizacao",
            )
        dias_visiveis = [dia_resumo]
        if visualizacao == "Preenchimento por período":
            dias_visiveis = st.multiselect(
                "Dias do período", dias_mes, default=[dia_padrao],
                format_func=lambda d: f"{d:%d/%m} · {DIAS_SEMANA_ABREVIADOS[d.weekday()]}",
                key=f"presenca_periodo_{dias_mes[0]:%Y_%m}",
                help="Selecione poucos dias para manter as situações legíveis.",
            )
        st.caption("Estes filtros afetam somente o preenchimento e são combinados com os filtros da lateral.")
    if not dias_visiveis:
        st.info("Selecione ao menos um dia para preencher a lista.")
        return
    # Resumo sempre corresponde à data da chamada, mesmo no modo por período.
    dias_calculo = sorted(set([*dias_visiveis, dia_resumo]))
    matriz = filtrar_grade_preenchimento(matriz, dias_calculo, unidades, monitores)
    if busca_editor.strip():
        alvo = matriz["Técnico"].fillna("") + " " + matriz["Login"].fillna("")
        matriz = matriz.loc[alvo.str.casefold().str.contains(busca_editor.strip().casefold(), regex=False)].copy()
    if matriz.empty:
        st.info("Nenhum técnico encontrado. Ajuste a unidade, o monitor ou a busca.")
        return
    resumo_dia = resumo_presenca(matriz, dia_resumo)
    colunas_resumo = st.columns(len(resumo_dia))
    for coluna, (rotulo, valor) in zip(colunas_resumo, resumo_dia.items()):
        coluna.metric(rotulo, valor)
    concluidos = len(matriz) - resumo_dia["Pendentes"]
    st.progress(
        concluidos / len(matriz),
        text=f"Chamada de {dia_resumo:%d/%m} · {concluidos} de {len(matriz)} técnicos preenchidos",
    )
    matriz_acoes = matriz.copy()
    col_pendentes, col_detalhes, col_link = st.columns([1.3, 1.3, 1])
    with col_pendentes:
        somente_pendentes = st.toggle("Somente pendentes", key="presenca_so_pendentes")
    with col_detalhes:
        if visualizacao == "Chamada do dia":
            mostrar_detalhes = True
            st.caption("Layout diário completo")
        else:
            mostrar_detalhes = st.toggle("Exibir dados cadastrais", key="presenca_dados_cadastrais")
    with col_link:
        st.link_button("Abrir no Drive ↗", f"https://docs.google.com/spreadsheets/d/{obter_sheet_id_ativos()}/edit")
    if somente_pendentes:
        matriz = matriz.loc[matriz[dias_visiveis].eq("Não preenchido").any(axis=1)].copy()
    if matriz.empty:
        st.success("Chamada concluída para os dias exibidos. Nenhum técnico pendente neste recorte.")
        with st.expander("Exportar, corrigir ou concluir chamada"):
            _render_acoes_presenca(matriz_acoes, dia_resumo)
        return
    matriz = filtrar_grade_preenchimento(matriz, dias_visiveis)
    diario = visualizacao == "Chamada do dia"
    if diario:
        dias = [dia_resumo]
        matriz = filtrar_grade_preenchimento(matriz, dias)
        tabela_editor = montar_tabela_chamada_diaria(matriz, dia_resumo, layout="simples")
        opcoes = list(OPCOES_STATUS_DIA)
        existentes = {str(valor).strip() for valor in tabela_editor["Status"] if str(valor).strip()}
        opcoes.extend(sorted(existentes - set(opcoes)))
        configuracao = {
            "RE": st.column_config.TextColumn("RE", width="small"),
            "Login": st.column_config.TextColumn("Login", width="small"),
            "Técnico": st.column_config.TextColumn("Técnico", width="large"),
            "Monitor": st.column_config.TextColumn("Monitor", width="medium"),
            "Status": st.column_config.SelectboxColumn(
                "Status", options=opcoes, width="medium",
                help="Escolha uma situação. Vazio significa chamada pendente; os demais campos são protegidos.",
            ),
        }
        ordem = list(tabela_editor.columns)
        nomes_editaveis = {"Status"}
        tabela_estilizada = (
            tabela_editor.style
            .set_properties(**{
                "background-color": "#FFFFFF",
                "color": "#111827",
                "border": "1px solid #9CA3AF",
                "font-size": "13px",
            })
            .set_table_styles([
                {"selector": "th", "props": [
                    ("background-color", "#F3F4F6"),
                    ("color", "#111827"),
                    ("font-weight", "600"),
                    ("border", "1px solid #9CA3AF"),
                ]},
                {"selector": "tbody tr:nth-child(even) td", "props": [
                    ("background-color", "#F9FAFB"),
                ]},
            ])
        )
        chave_editor = f"absenteismo_grade_editor_diaria_{dia_resumo:%Y%m%d}_{hashlib.sha256(matriz.to_csv(index=False).encode()).hexdigest()[:12]}"
        _css_tabela_chamada_compacta()
    else:
        dias = _colunas_dia_mapa(matriz)
        matriz["Total"] = matriz[dias].ne("Não preenchido").sum(axis=1)
        opcoes = list(OPCOES_PRESENCA)
        existentes = {str(v) for dia in dias for v in matriz[dia].dropna() if str(v)}
        opcoes += sorted(existentes - set(opcoes))
        # O editor recebe chaves de texto explícitas para aplicar corretamente o
        # SelectboxColumn; a conversão de volta preserva a validação por data.
        nomes_dias = {dia: dia.isoformat() for dia in dias}
        tabela_editor = matriz.rename(columns=nomes_dias)
        configuracao = {
            "Técnico": st.column_config.TextColumn("Técnico", width="large"),
            "Login": st.column_config.TextColumn("Login", width="small"),
            "Monitor": st.column_config.TextColumn("Monitor", width="medium"),
            "RE": st.column_config.TextColumn("RE", width="small"),
            "Total": None,
        }
        configuracao.update({
            nomes_dias[dia]: st.column_config.SelectboxColumn(
                "Situação do dia" if len(dias) == 1 else f"{dia:%d/%m} · {DIAS_SEMANA_ABREVIADOS[dia.weekday()]}",
                options=opcoes, width="medium",
                help="Não preenchido é pendência, nunca presença. Marcações existentes são preservadas.",
            ) for dia in dias
        })
        ordem = ["Login", "Técnico", *nomes_dias.values()]
        if mostrar_detalhes:
            ordem = ["RE", "Login", "Técnico", "Monitor", "Base", "U.N.", *nomes_dias.values()]
        nomes_editaveis = set(nomes_dias.values())
        chave_editor = f"absenteismo_grade_editor_{hashlib.sha256(matriz.to_csv(index=False).encode()).hexdigest()[:16]}"

    st.caption(f"{len(matriz)} técnico(s) na lista · selecione a situação na célula · salvamento automático")
    editada = st.data_editor(
        tabela_estilizada if diario else tabela_editor,
        hide_index=True, num_rows="fixed",
        disabled=[c for c in tabela_editor.columns if c not in nomes_editaveis],
        column_config=configuracao, column_order=ordem,
        height=min(600, 40 + len(matriz) * (30 if diario else 35)), width="stretch",
        key=chave_editor,
    )
    if not diario:
        editada = editada.rename(columns={nome: dia for dia, nome in nomes_dias.items()})
    with st.expander("Ações da chamada · lote, correção, fechamento e Excel"):
        _render_acoes_presenca(matriz_acoes, dia_resumo)
    with st.expander("Como preencher e corrigir marcações"):
        if diario:
            st.markdown("**Status em branco** é uma pendência. Selecione **ATIVO** para confirmar presença ou escolha uma das situações do menu.")
        else:
            st.markdown("**Não preenchido** é uma pendência. Selecione **Presente** para confirmar a presença ou escolha o motivo da ausência.")
        st.caption("O preenchimento atua apenas em dias pendentes. Para corrigir uma marcação, use a aba Corrigir com histórico. A auditoria preserva o valor anterior. Em falha de envio, os dados ficam apenas nesta sessão.")
    try:
        novos = (
            registros_da_chamada_diaria(matriz, editada, dia_resumo)
            if diario
            else registros_da_presenca(matriz, editada)
        )
    except ValueError as erro:
        st.error(str(erro))
        return
    if not novos:
        return
    # Confere contra todos os registros, inclusive os ocultos pelo filtro de tipo.
    for novo in novos:
        dia = date.fromisoformat(novo["Data Início"])
        existentes_dia = registros.loc[
            registros["Status"].ne(STATUS_CANCELADO)
            & (registros["_inicio"].dt.date <= dia)
            & (registros["_fim"].dt.date >= dia)
        ]
        if existentes_dia["Login"].eq(novo["Login"]).any():
            st.error("Um dos dias já tem ausência. Remova o filtro de tipo e confira o mapa antes de salvar.")
            return
    atualizados = normalizar_registros(pd.concat(
        [registros.drop(columns=["_inicio", "_fim"], errors="ignore"), pd.DataFrame(novos)],
        ignore_index=True,
    ))
    with st.spinner("Salvando preenchimento no Google Sheets…"):
        sincronizou = _persistir(atualizados)
    if sincronizou:
        mensagem = ("sucesso", f"{len(novos)} dia(s) salvo(s) automaticamente no Drive (aba absenteismo).")
    else:
        st.session_state[CHAVE_PENDENTES] = [
            *st.session_state.get(CHAVE_PENDENTES, []), *novos,
        ]
        mensagem = ("alerta", "Preenchimento mantido somente nesta sessão; não foi possível gravar na planilha. Exporte os registros para guardar.")
    st.session_state["absenteismo_flash"] = [mensagem]
    st.rerun()


# Quadro do mapa: mesmo recorte de base/monitor/busca da página.
quadro_mapa = quadro_df.copy()
if bases_sel:
    quadro_mapa = quadro_mapa[
        quadro_mapa["BASE"].map(normalizar_texto).isin(bases_sel)
    ]
if monitores_sel:
    quadro_mapa = quadro_mapa[
        quadro_mapa["MONITOR"].replace("", "Não informado").isin(monitores_sel)
    ]
if busca.strip():
    _termo_mapa = busca.strip().casefold()
    quadro_mapa = quadro_mapa[
        (
            quadro_mapa["TÉCNICO"].str.casefold()
            + " "
            + quadro_mapa["LOGIN"].str.casefold()
        ).str.contains(_termo_mapa, regex=False)
    ]

mapa_inicio = periodo_inicio.replace(day=1)
mapa_fim = (mapa_inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)

def _render_forca():
    with secao(
        "Força de Trabalho",
        icone="groups",
        subtitulo="Disponibilidade estimada do quadro por base e monitor na data escolhida.",
    ):
        with st.container(border=True):
            col_referencia, col_contexto = st.columns([1, 2])
            with col_referencia:
                data_forca = st.date_input("Data da força de trabalho", value=hoje, key="absenteismo_data_forca")
            with col_contexto:
                st.markdown("**Panorama da capacidade operacional**")
                st.caption("Equipe do recorte atual de base, monitor e busca. Todos os tipos de ausência são considerados.")
        with st.expander("Como interpretar esta visão"):
            st.caption("Disponível estimado é o integrante do quadro sem ausência registrada na data, inclusive quem ainda não teve a presença preenchida. Não confirma presença ou escala. Feriados, jornadas e plantões não são aplicados. O filtro de tipo de ausência não altera esta visão.")
        if data_forca.weekday() >= 5:
            st.info("Fim de semana: confira a escala. Este cálculo não aplica jornadas, feriados ou plantões.")
        if qtd_pendentes:
            st.warning("A força de trabalho inclui lançamentos ainda não sincronizados desta sessão.")
        resumo_forca, detalhes_forca = calcular_forca_trabalho(quadro_mapa, registros, data_forca)
        if detalhes_forca.empty:
            render_empty_state(
                tipo="dados", titulo="Nenhum integrante do quadro no recorte",
                descricao="Confira a lista_ativos ou ajuste base, monitor e busca.",
            )
        else:
            render_forca_trabalho(resumo_forca, detalhes_forca, data_forca)


def _render_mapa():
    # Tipos não filtram a grade: esconder presença transformaria marcações em falsas pendências.
    matriz_mapa = _lista_presenca_em_cache(registros, quadro_mapa, mapa_inicio, mapa_fim)
    dias_mapa = _colunas_dia_mapa(matriz_mapa)
    for dia in dias_mapa:
        matriz_mapa[dia] = matriz_mapa[dia].map(lambda valor: _CODIGOS_MAPA.get(valor, valor))
    with secao(
        "Mapa Mensal de Presença",
        icone="calendar_view_month",
        subtitulo=(
            f"{mapa_inicio:%m/%Y} · uma coluna por dia, do mesmo jeito da planilha "
            "de controle (RE, Login, Técnico, Monitor, Base, U.N.)."
        ),
        badge=f"{formatar_inteiro(len(matriz_mapa))} técnicos",
    ):
        if matriz_mapa.empty:
            render_empty_state(
                tipo="dados",
                titulo="Nenhum técnico no recorte",
                descricao=(
                    "A lista_ativos não está disponível e não há registros no período. "
                    "Ajuste os filtros ou atualize a planilha."
                ),
            )
        else:
            marcadas = ~matriz_mapa[dias_mapa].isin(["", "NP"])
            col_quadro, col_marcadas, col_pendentes = st.columns(3)
            col_quadro.metric("Técnicos no mapa", len(matriz_mapa))
            col_marcadas.metric("Dias preenchidos", int(marcadas.sum().sum()))
            col_pendentes.metric("Dias não preenchidos", int((~marcadas).sum().sum()))
            st.caption("Mapa completo da equipe no mês: presença, ausências e situações operacionais. O filtro de tipo não oculta marcações nesta visão.")
            ultima_sync = st.session_state.get("absenteismo_ultima_sync")
            if qtd_pendentes:
                st.warning(f"{qtd_pendentes} lançamento(s) somente nesta sessão — sincronização pendente.")
            elif ultima_sync and ultima_sync["ok"]:
                st.caption(f"Última gravação confirmada no Drive: {ultima_sync['horario']}")
            elif ultima_sync:
                st.warning(f"Última tentativa sem confirmação: {ultima_sync['horario']}. Confira as pendências antes de fechar a sessão.")
            _render_mapa_mensal(matriz_mapa, mapa_inicio, mapa_fim)


# ============================================================
# INDICADORES DO PERÍODO
# ============================================================
def _render_indicadores():
    with secao(
        "Indicadores do Período",
        icone="monitoring",
        subtitulo=f"{periodo_inicio:%d/%m/%Y} a {periodo_fim:%d/%m/%Y} · dias úteis contam seg–sex (sem feriados).",
        badge=f"{formatar_inteiro(qtd_quadro)} técnicos no quadro",
    ):
        specs: list[SpecKPIAvancado] = [
            {
                "label": "Ausentes hoje",
                "valor": formatar_inteiro(resumo["ausentes_hoje"]),
                "sub": f"{formatar_inteiro(resumo['registros_hoje'])} registro(s) cobrindo hoje",
                "icone": "🗓️",
                "tema": "vermelho",
            },
            {
                "label": "Técnicos ausentes no período",
                "valor": formatar_inteiro(resumo["tecnicos_periodo"]),
                "sub": f"{formatar_inteiro(resumo['registros_periodo'])} registro(s) no período",
                "icone": "👷",
                "tema": "azul",
            },
            {
                "label": "Dias úteis de ausência",
                "valor": formatar_inteiro(resumo["dias_uteis_periodo"]),
                "sub": f"{formatar_inteiro(resumo['dias_corridos_periodo'])} dias corridos",
                "icone": "📆",
                "tema": "laranja",
                "ajuda": "Soma dos dias úteis de cada registro, só na interseção com o período.",
            },
            {
                "label": "Taxa de absenteísmo",
                "valor": formatar_percentual(taxa_periodo * 100),
                "sub": "Dias úteis ausentes ÷ (quadro × dias úteis do período)",
                "icone": "📉",
                "tema": "roxo",
                "progresso": min(taxa_periodo * 100, 100.0),
                "ajuda": f"Quadro do recorte: {formatar_inteiro(qtd_quadro)} técnicos · {dias_uteis_no_periodo} dias úteis no período.",
            },
        ]
        render_kpi_row(specs, colunas=4)
        render_insight(
            f"No período: **{formatar_inteiro(resumo['faltas_periodo'])}** falta(s), "
            f"**{formatar_inteiro(resumo['ferias_periodo'])}** férias e "
            f"**{formatar_inteiro(resumo['programadas'])}** ausência(s) programadas "
            f"(férias/folgas/treinamentos futuros). Total histórico do controle: "
            f"**{formatar_inteiro(resumo['registros_total'])}** registro(s) ativos"
            f" e **{formatar_inteiro(resumo['cancelados'])}** cancelado(s).",
            tipo="info",
        )

# ============================================================
# REGISTRAR AUSÊNCIA
# ============================================================
def _render_formulario_ausencia() -> None:
    """Formulário de lançamento (aba no formato de registros)."""
    opcoes_tecnicos: dict[str, pd.Series] = {}
    if not quadro_df.empty:
        ordenado = quadro_df.sort_values(["BASE", "MONITOR", "TÉCNICO"])
        for _, linha in ordenado.iterrows():
            rotulo = (
                f"{linha['TÉCNICO']} — Login {linha['LOGIN']} · "
                f"{linha['BASE'] or 'Sem base'} / {linha['MONITOR'] or 'Sem monitor'}"
            )
            opcoes_tecnicos[rotulo] = linha

    with st.form("form_registro_ausencia", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            if opcoes_tecnicos:
                tecnico_sel = st.selectbox("Técnico (lista_ativos)", list(opcoes_tecnicos))
                login_manual = nome_manual = ""
            else:
                tecnico_sel = ""
                nome_manual = st.text_input("Técnico (lista_ativos indisponível)")
                login_manual = st.text_input("Login")
            tipo_sel = st.selectbox("Tipo de ausência", list(TIPOS_AUSENCIA))
            justificativa_sel = st.selectbox("Justificativa", list(JUSTIFICATIVAS), index=2)
        with col_b:
            data_inicio = st.date_input("Data de início", value=hoje)
            data_fim = st.date_input("Data de fim", value=hoje)
            motivo_txt = st.text_area("Motivo / observação", height=68)
        enviado = st.form_submit_button("💾 Registrar ausência", width="stretch")

    if enviado:
        if opcoes_tecnicos and tecnico_sel:
            linha_tec = opcoes_tecnicos[tecnico_sel]
            login_novo, nome_novo = str(linha_tec["LOGIN"]), str(linha_tec["TÉCNICO"])
            monitor_novo, base_novo = str(linha_tec["MONITOR"]), str(linha_tec["BASE"])
        else:
            login_novo, nome_novo = login_manual.strip(), nome_manual.strip()
            monitor_novo = base_novo = ""
        if not login_novo or not nome_novo:
            st.error("Selecione um técnico da lista_ativos (ou informe nome e login).")
        elif data_fim < data_inicio:
            st.error("A data de fim não pode ser anterior à data de início.")
        else:
            registro = {
                "ID": uuid.uuid4().hex[:12],
                "Login": login_novo,
                "Técnico": nome_novo,
                "Monitor": monitor_novo,
                "Base": base_novo,
                "Tipo": tipo_sel,
                "Data Início": data_inicio.isoformat(),
                "Data Fim": data_fim.isoformat(),
                "Justificativa": justificativa_sel,
                "Motivo": motivo_txt.strip(),
                "Status": STATUS_ATIVO,
                "Registrado em": datetime.now().strftime("%d/%m/%Y %H:%M"),
            }
            sobrepostos = filtrar_registros_periodo(registros, data_inicio, data_fim)
            sobrepostos = sobrepostos[sobrepostos["Login"] == login_novo]
            _novo_df = normalizar_registros(pd.concat([
                registros.drop(columns=["_inicio", "_fim"], errors="ignore"), pd.DataFrame([registro])
            ], ignore_index=True))
            persistiu = _persistir(_novo_df)
            motivo_falha = st.session_state.get("absenteismo_ultima_sync", {}).get("motivo", "")
            mensagens: list[tuple[str, str]] = []
            if persistiu:
                mensagens.append(
                    (
                        "sucesso",
                        f"Ausência registrada na planilha: {nome_novo} · {tipo_sel} · "
                        f"{data_inicio:%d/%m/%Y} a {data_fim:%d/%m/%Y}.",
                    )
                )
            else:
                pendentes = st.session_state.get(CHAVE_PENDENTES, [])
                pendentes.append(registro)
                st.session_state[CHAVE_PENDENTES] = pendentes
                mensagens.append(
                    (
                        "alerta",
                        "Não foi possível gravar na planilha "
                        f"({motivo_falha}). O registro ficou **somente nesta sessão**.",
                    )
                )
            if not sobrepostos.empty:
                mensagens.append(
                    (
                        "alerta",
                        f"⚠️ {nome_novo} já tinha {len(sobrepostos)} registro(s) ativo(s) "
                        "nesse período — confira se não é duplicidade (Registros do Controle).",
                    )
                )
            st.session_state["absenteismo_flash"] = mensagens
            st.rerun()


def _render_lancamento():
    with secao(
        "Registrar Ausência",
        icone="edit_calendar",
        subtitulo="O lançamento preenche somente dias e técnicos já cadastrados na grade absenteismo.",
    ):
        _render_formulario_ausencia()


# ============================================================
# AUSÊNCIAS POR TIPO / CALENDÁRIO / RANKINGS
# ============================================================
def _render_por_tipo():
    with secao(
        "Ausências por Tipo",
        icone="pie_chart",
        subtitulo="Dias úteis e registros de cada tipo dentro do período filtrado.",
    ):
        por_tipo = agrupar_registros(
            registros_recorte, "Tipo", periodo_inicio=periodo_inicio, periodo_fim=periodo_fim
        )
        if por_tipo.empty:
            render_empty_state(
                tipo="dados",
                titulo="Nenhuma ausência no período",
                descricao="Lance a primeira ausência em Registrar Ausência ou amplie o período.",
            )
        else:
            colunas_graficos = st.columns(2)
            with colunas_graficos[0]:
                render_grafico(
                    grafico_donut(por_tipo, "Tipo", "Dias Úteis", titulo="Dias úteis por tipo", altura=340),
                    chave="absenteismo_donut_tipo",
                )
            with colunas_graficos[1]:
                render_grafico(
                    grafico_barras(
                        por_tipo, "Tipo", "Registros", titulo="Registros por tipo",
                        altura=340, mostrar_valores=True,
                    ),
                    chave="absenteismo_barras_tipo",
                )
            st.dataframe(por_tipo, width="stretch", hide_index=True)

def _render_calendario():
    with secao(
        "Calendário de Ausências",
        icone="calendar_month",
        subtitulo="Técnicos ausentes por dia no período (seg–sex úteis e fins de semana).",
    ):
        serie = serie_diaria_ausencias(
            registros_recorte, periodo_inicio=periodo_inicio, periodo_fim=periodo_fim
        )
        if serie.empty:
            render_empty_state(tipo="dados", titulo="Sem dias com ausência no período.")
        else:
            render_grafico(
                grafico_calendario(
                    serie, col_data="Data", col_valor="Técnicos",
                    titulo="Técnicos ausentes por dia", altura=300, mostrar_valores=True,
                ),
                chave="absenteismo_calendario",
            )

def _render_ranking():
    with secao(
        "Ranking por Base e Monitor",
        icone="leaderboard",
        subtitulo="Onde estão concentrados os dias úteis de ausência do período.",
    ):
        colunas_ranking = st.columns(2)
        for coluna, dimensao, chave_grafico in (
            (colunas_ranking[0], "Base", "absenteismo_ranking_base"),
            (colunas_ranking[1], "Monitor", "absenteismo_ranking_monitor"),
        ):
            agrupado = agrupar_registros(
                registros_recorte, dimensao, periodo_inicio=periodo_inicio, periodo_fim=periodo_fim
            )
            with coluna:
                if agrupado.empty:
                    render_empty_state(tipo="dados", titulo=f"Sem dados por {dimensao.lower()}.")
                else:
                    render_grafico(
                        grafico_ranking(
                            agrupado, dimensao, "Dias Úteis",
                            titulo=f"Dias úteis de ausência por {dimensao.lower()}", top=10,
                        ),
                        chave=chave_grafico,
                    )
                    st.dataframe(agrupado, width="stretch", hide_index=True)

# ============================================================
# AUSENTES HOJE E PRÓXIMAS AUSÊNCIAS
# ============================================================
def _render_agenda():
    with secao(
        "Ausentes Hoje e Próximas Ausências",
        icone="upcoming",
        subtitulo="Quem está fora hoje e o que vem nos próximos 30 dias.",
    ):
        ativos = registros_recorte[registros_recorte["Status"] == STATUS_ATIVO]
        if ativos.empty:
            render_empty_state(tipo="dados", titulo="Nenhum registro ativo no recorte.")
        else:
            de_hoje = ativos[
                (ativos["_inicio"].dt.date <= hoje) & (ativos["_fim"].dt.date >= hoje)
            ]
            proximas = ativos[
                (ativos["_inicio"].dt.date > hoje)
                & (ativos["_inicio"].dt.date <= hoje + timedelta(days=30))
            ]
            colunas_listas = st.columns(2)
            with colunas_listas[0]:
                st.markdown(f"**Ausentes hoje ({hoje:%d/%m/%Y})** — {len(de_hoje)} registro(s)")
                if de_hoje.empty:
                    st.caption("Ninguém ausente hoje neste recorte.")
                else:
                    st.dataframe(_tabela_exibicao(de_hoje), width="stretch", hide_index=True)
            with colunas_listas[1]:
                st.markdown(f"**Próximas ausências (30 dias)** — {len(proximas)} registro(s)")
                if proximas.empty:
                    st.caption("Nada programado para os próximos 30 dias neste recorte.")
                else:
                    st.dataframe(_tabela_exibicao(proximas), width="stretch", hide_index=True)

# ============================================================
# REGISTROS DO CONTROLE (DETALHAMENTO + CANCELAMENTO)
# ============================================================
def _render_registros():
    with secao(
        "Registros do Controle",
        icone="list_alt",
        subtitulo="Marcações atuais da grade. Cancelar limpa a célula e registra o valor anterior em auditoria_presenca.",
        badge=f"{formatar_inteiro(len(registros_recorte))} no recorte",
    ):
        if incluir_cancelados:
            exibidos = registros_recorte[
                (registros_recorte["_inicio"] <= pd.Timestamp(periodo_fim))
                & (registros_recorte["_fim"] >= pd.Timestamp(periodo_inicio))
            ]
        else:
            # Só ativos cobrindo o período (cancelados ficam fora da lista).
            exibidos = filtrar_registros_periodo(registros_recorte, periodo_inicio, periodo_fim)
        if exibidos.empty:
            render_empty_state(
                tipo="filtro",
                titulo="Nenhum registro no recorte atual",
                descricao="Ajuste o período/filtros ou lance uma nova ausência.",
            )
        else:
            st.dataframe(_tabela_exibicao(exibidos), width="stretch", hide_index=True)

            ativos_exibidos = exibidos[exibidos["Status"] == STATUS_ATIVO]
            if not ativos_exibidos.empty:
                rotulos_cancelar = {
                    f"{linha['Técnico']} · {linha['Tipo']} · {linha['_inicio']:%d/%m/%Y} a "
                    f"{linha['_fim']:%d/%m/%Y} (Login {linha['Login']})": str(linha["ID"])
                    for _, linha in ativos_exibidos.iterrows()
                }
                col_cancelar_a, col_cancelar_b = st.columns([3, 1])
                with col_cancelar_a:
                    escolha = st.selectbox(
                        "Registro para cancelar", list(rotulos_cancelar), key="absenteismo_cancelar_sel"
                    )
                with col_cancelar_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚫 Cancelar registro", key="absenteismo_cancelar_btn"):
                        id_escolhido = rotulos_cancelar[escolha]
                        atualizados = registros.copy()
                        atualizados.loc[atualizados["ID"] == id_escolhido, "Status"] = STATUS_CANCELADO
                        atualizados.loc[atualizados["ID"] == id_escolhido, "Motivo"] = "Cancelamento via Registros do Controle"
                        if _persistir(atualizados):
                            st.session_state["absenteismo_flash"] = [
                                ("sucesso", "Registro cancelado e gravado na planilha.")
                            ]
                        else:
                            st.session_state["absenteismo_flash"] = [
                                ("alerta", "Cancelamento não confirmado. A marcação anterior foi mantida; confira o status de sincronização.")
                            ]
                        st.rerun()
    return exibidos

# ============================================================
# EXPORTAÇÃO
# ============================================================
@st.cache_data(show_spinner=False, max_entries=4, ttl=120)
def _lista_presenca_em_cache(registros, quadro, inicio, fim):
    """Reutiliza a transformação da grade nos reruns dos filtros e do editor."""
    # O construtor genérico inclui pessoas presentes só nos registros. Aqui a
    # grade é o cadastro oficial: não reintroduzir técnicos excluídos por filtros.
    registros_equipe = registros.loc[registros["Login"].isin(quadro["LOGIN"])]
    return montar_lista_presenca(registros_equipe, quadro, inicio, fim)


def _render_chamada_diaria() -> None:
    st.caption("01 · Selecione a data e a equipe → 02 · Registre as situações → 03 · Confira e conclua a chamada")
    st.info("A chamada considera todos os tipos de situação. Os filtros de tipo e período da lateral são usados nas análises; a data da chamada é escolhida abaixo.")
    lista = _lista_presenca_em_cache(registros, quadro_mapa, min(datas_grade), max(datas_grade)).copy()
    for coluna in ("Cód.Equipe", "Cód.Aux.Equipe"):
        if coluna in quadro_mapa.columns:
            codigos = quadro_mapa.set_index("LOGIN")[coluna].fillna("").astype(str).to_dict()
            lista[coluna] = lista["Login"].map(codigos).fillna("").astype(str)
        else:
            lista[coluna] = ""
    if lista.empty:
        render_empty_state(tipo="filtro", titulo="Nenhum técnico neste recorte", descricao="Ajuste o filtro Base acima ou os filtros de monitor e busca na lateral.")
        return
    _render_preenchimento_mapa(lista)
    with st.expander("Registrar ausência por período"):
        _render_lancamento()


def _estilo_celula_presenca_externa(valor: object) -> str:
    """Aplica cor discreta às células de status na planilha externa."""
    texto = str(valor or "").strip().upper()
    if texto == "ATIVO":
        return "background-color: rgba(34, 197, 94, 0.16); color: #166534; font-weight: 600;"
    if texto == "FALTA":
        return "background-color: rgba(239, 68, 68, 0.18); color: #991b1b; font-weight: 600;"
    if texto == "ATESTADO":
        return "background-color: rgba(245, 158, 11, 0.18); color: #92400e; font-weight: 600;"
    if texto in ("NÃO PREENCHIDO", ""):
        return "color: #9ca3af;"
    return ""


def _valor_dimensao_presenca(df: pd.DataFrame, coluna: str) -> pd.Series:
    """Rótulo estável para filtros e grupos, incluindo cadastros sem valor."""
    if coluna not in df.columns:
        return pd.Series("Não informado", index=df.index, dtype="object")
    valores = df[coluna].where(df[coluna].notna(), "").astype(str).str.strip()
    ausentes = valores.eq("") | valores.str.upper().isin({"NAN", "NONE", "NULL", "N/A"})
    return valores.mask(ausentes, "Não informado")


def _opcoes_filtro_presenca(df: pd.DataFrame, coluna: str, todas: str) -> list[str]:
    valores = _valor_dimensao_presenca(df, coluna) if coluna in df.columns else pd.Series(dtype=str)
    unicos = sorted(valores.unique().tolist(), key=str.casefold)
    return [todas, *unicos]


def _grafico_percentual_horizontal(
    resumo: pd.DataFrame,
    dimensao: str,
    *,
    chave: str,
) -> None:
    """Ranking horizontal das menores taxas para priorizar supervisão."""
    if resumo.empty:
        st.info(f"Sem dados de presença por {dimensao.lower()} no recorte.")
        return
    dados_com_preenchimento = resumo.loc[resumo["Dias preenchidos"].gt(0)]
    if dados_com_preenchimento.empty:
        st.info(f"Sem marcações preenchidas para calcular presença por {dimensao.lower()}.")
        return
    if len(dados_com_preenchimento) < len(resumo):
        st.caption("Grupos sem marcações preenchidas não entram no ranking de presença.")
    dados = (
        dados_com_preenchimento.sort_values(
            ["% Presença", "FALTA + ATESTADO"], ascending=[True, False]
        )
        .head(10)
        .reset_index(drop=True)
    )
    valores = pd.to_numeric(dados["% Presença"], errors="coerce").fillna(0.0)
    cores = ["#DC2626" if indice == 0 else "#0A48AA" for indice in range(len(dados))]
    figura = go.Figure(
        go.Bar(
            x=valores,
            y=dados[dimensao].astype(str),
            orientation="h",
            marker_color=cores,
            text=[formatar_percentual(valor, 1) for valor in valores],
            textposition="outside",
            cliponaxis=False,
            customdata=dados[["FALTA + ATESTADO", "Técnicos"]].to_numpy(),
            hovertemplate=(
                "<b>%{y}</b><br>% Presença: %{x:.1f}%"
                "<br>FALTA + ATESTADO: %{customdata[0]}"
                "<br>Técnicos: %{customdata[1]}<extra></extra>"
            ),
        )
    )
    aplicar_tema(
        figura,
        titulo=f"Menor % de Presença por {dimensao.lower()} · Top 10",
        altura=max(280, 38 * len(dados) + 100),
        hover_unificado=False,
        legenda=False,
        rotulos={"x": "% Presença", "y": ""},
    )
    figura.update_xaxes(
        range=[0, 115], tickvals=list(range(0, 101, 20)), ticksuffix="%", rangemode="tozero"
    )
    figura.update_yaxes(autorange="reversed")
    render_grafico(figura, chave=chave)


def _tabela_percentual_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    """Formata percentuais para leitura pt-BR sem alterar o DataFrame exportável."""
    exibicao = df.copy()
    for coluna in ("% Presença", "% Preenchimento"):
        if coluna in exibicao.columns:
            exibicao[coluna] = exibicao[coluna].map(lambda valor: formatar_percentual(valor, 1))
    return exibicao


def _render_planilha_externa() -> None:
    """Painel executivo da planilha mensal ``lista_de_presenca``."""
    from config.settings import URL_PRESENCA_EDIT

    col_titulo, col_link, col_reload = st.columns([3, 1.2, 1])
    with col_titulo:
        st.subheader("Lista de Presença · Painel Executivo")
    with col_link:
        st.link_button("Abrir no Google Sheets", URL_PRESENCA_EDIT, width="stretch")
    with col_reload:
        recarregar = st.button(
            "Recarregar planilha", key="btn_reload_planilha_presenca", width="stretch"
        )

    ttl = 0 if recarregar else 300
    try:
        df_planilha = carregar_planilha_lista_presenca(ttl=ttl)
    except Exception as exc:
        st.error(f"Não foi possível carregar a planilha de presença: {exc}")
        return

    if df_planilha.empty:
        st.info("Nenhum registro encontrado na planilha externa de lista de presença.")
        return

    todas_colunas_dias = identificar_colunas_dias_planilha(df_planilha)
    meses_disponiveis = agrupar_colunas_dias_por_mes(todas_colunas_dias)
    mes_selecionado = next(iter(meses_disponiveis), "Todos os dias")
    if len(meses_disponiveis) > 1:
        if st.session_state.get("presenca_ext_mes") not in meses_disponiveis:
            st.session_state["presenca_ext_mes"] = mes_selecionado
        mes_selecionado = st.selectbox(
            "Mês da análise", list(meses_disponiveis), key="presenca_ext_mes"
        )
    elif meses_disponiveis:
        st.caption(f"Mês analisado: **{mes_selecionado}**")
    colunas_dias = meses_disponiveis.get(mes_selecionado, todas_colunas_dias)

    filtros = st.columns(4)
    opcoes_monitor = _opcoes_filtro_presenca(df_planilha, "Monitor", "Todos")
    opcoes_base = _opcoes_filtro_presenca(df_planilha, "Base", "Todas")
    opcoes_un = _opcoes_filtro_presenca(df_planilha, "U.N.", "Todas")
    for chave, opcoes in (
        ("presenca_ext_monitor", opcoes_monitor),
        ("presenca_ext_base", opcoes_base),
        ("presenca_ext_un", opcoes_un),
    ):
        if st.session_state.get(chave) not in opcoes:
            st.session_state[chave] = opcoes[0]
    with filtros[0]:
        sel_monitor = st.selectbox("Monitor", opcoes_monitor, key="presenca_ext_monitor")
    with filtros[1]:
        sel_base = st.selectbox("Base", opcoes_base, key="presenca_ext_base")
    with filtros[2]:
        sel_un = st.selectbox("U.N.", opcoes_un, key="presenca_ext_un")
    with filtros[3]:
        busca = st.text_input("Buscar técnico / login / RE", key="presenca_ext_busca").strip()

    filtrado = df_planilha.copy()
    for coluna, valor, todas in (
        ("Monitor", sel_monitor, "Todos"),
        ("Base", sel_base, "Todas"),
        ("U.N.", sel_un, "Todas"),
    ):
        if coluna in filtrado.columns and valor != todas:
            filtrado = filtrado.loc[_valor_dimensao_presenca(filtrado, coluna).eq(valor)]
    if busca:
        termo = busca.casefold()
        mascara = pd.Series(False, index=filtrado.index)
        for coluna in ("RE", "Login", "Técnico"):
            if coluna in filtrado.columns:
                mascara |= (
                    filtrado[coluna]
                    .fillna("")
                    .astype(str)
                    .str.casefold()
                    .str.contains(termo, regex=False, na=False)
                )
        filtrado = filtrado.loc[mascara]

    resumo_exec = resumir_marcacoes_presenca(filtrado, colunas_dias)
    resumo_dimensoes = {
        dimensao: agrupar_marcacoes_presenca(filtrado, colunas_dias, dimensao)
        for dimensao in ("Monitor", "Base")
        if dimensao in filtrado.columns
    }
    dimensoes_resumo = [coluna for coluna in ("Monitor", "Base") if coluna in filtrado.columns]
    resumo_monitor_base = (
        agrupar_marcacoes_presenca(filtrado, colunas_dias, dimensoes_resumo)
        if dimensoes_resumo and colunas_dias
        else pd.DataFrame()
    )
    if not resumo_monitor_base.empty:
        resumo_monitor_base = resumo_monitor_base.sort_values(
            ["FALTA + ATESTADO", "% Presença"], ascending=[False, True]
        ).reset_index(drop=True)

    colunas_exportacao = [
        coluna
        for coluna in df_planilha.columns
        if coluna not in todas_colunas_dias or coluna in colunas_dias
    ]
    recorte_exportacao = filtrado.loc[:, colunas_exportacao]
    slug_mes = normalizar_texto(mes_selecionado).replace(" ", "_").lower()
    arquivo_excel = gerar_excel_executivo_presenca(recorte_exportacao, resumo_monitor_base)

    linha_contexto, linha_download = st.columns([3, 1])
    with linha_contexto:
        st.caption(
            f"Exibindo {len(filtrado)} de {len(df_planilha)} técnicos · "
            f"{len(colunas_dias)} dias no mês · filtros aplicados também aos gráficos e exportações."
        )
    with linha_download:
        st.download_button(
            "⬇️ Baixar Excel executivo",
            data=arquivo_excel,
            file_name=f"absenteismo_executivo_{slug_mes or 'periodo'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="presenca_exportar_executivo",
            width="stretch",
            help="Inclui o recorte filtrado e uma aba de resumo por Monitor/Base.",
        )

    if not colunas_dias:
        st.info("Não foram encontradas colunas diárias para montar as análises deste recorte.")
    else:
        st.subheader(f"Indicadores do mês · {mes_selecionado}")
        kpis = st.columns(7)
        valores_kpi = (
            ("Técnicos", formatar_inteiro(resumo_exec["tecnicos"])),
            ("% Presença", formatar_percentual(resumo_exec["percentual_presenca"])),
            ("FALTA + ATESTADO", formatar_inteiro(resumo_exec["faltas_atestados"])),
            ("ATIVO", formatar_inteiro(resumo_exec["ativo"])),
            ("FALTA", formatar_inteiro(resumo_exec["falta"])),
            ("ATESTADO", formatar_inteiro(resumo_exec["atestado"])),
            ("Não preenchido", formatar_inteiro(resumo_exec["nao_preenchido"])),
        )
        for coluna, (rotulo, valor) in zip(kpis, valores_kpi):
            coluna.metric(rotulo, valor)
        st.caption(
            "% Presença = ATIVO ÷ marcações preenchidas. Pendências não reduzem a taxa; "
            "outros status operacionais aparecem como ‘Outros’ na distribuição."
        )

        st.subheader("Distribuição de status")
        if filtrado.empty:
            st.info("Sem técnicos no recorte atual para exibir a distribuição.")
        else:
            distribuicao = [
                ("ATIVO", resumo_exec["ativo"]),
                ("FALTA", resumo_exec["falta"]),
                ("ATESTADO", resumo_exec["atestado"]),
                ("Não preenchido", resumo_exec["nao_preenchido"]),
            ]
            if resumo_exec["outros"]:
                distribuicao.append(("Outros", resumo_exec["outros"]))
            dados_donut = pd.DataFrame(distribuicao, columns=["Status", "Marcações"])
            render_grafico(
                grafico_donut(
                    dados_donut,
                    "Status",
                    "Marcações",
                    titulo="Proporção das marcações no recorte",
                    altura=370,
                    top=None,
                ),
                chave="presenca_executiva_status_donut",
            )

        st.subheader("Ranking de absenteísmo por Monitor e Base")
        st.caption(
            "Barras horizontais: maiores ocorrências de FALTA + ATESTADO e menores taxas de presença. "
            "O ranking considera somente os dias do mês e os filtros acima."
        )
        dimensoes_ranking = [dim for dim in ("Monitor", "Base") if dim in resumo_dimensoes]
        if not dimensoes_ranking:
            st.info("A planilha não contém as colunas Monitor/Base necessárias para o ranking.")
        else:
            abas_ranking = st.tabs([f"Por {dim}" for dim in dimensoes_ranking])
            for aba, dimensao in zip(abas_ranking, dimensoes_ranking):
                with aba:
                    agrupado = resumo_dimensoes[dimensao]
                    if agrupado.empty:
                        st.info(f"Sem dados por {dimensao.lower()} no recorte atual.")
                        continue
                    coluna_absencia, coluna_presenca = st.columns(2)
                    with coluna_absencia:
                        if agrupado["FALTA + ATESTADO"].sum() <= 0:
                            st.info(f"Sem ocorrências de FALTA/ATESTADO por {dimensao.lower()}.")
                        else:
                            render_grafico(
                                grafico_ranking(
                                    agrupado,
                                    dimensao,
                                    "FALTA + ATESTADO",
                                    titulo=f"FALTA + ATESTADO por {dimensao.lower()} · Top 10",
                                    altura=max(280, 38 * min(10, len(agrupado)) + 100),
                                    top=10,
                                    rotulos={"x": "FALTA + ATESTADO", "y": ""},
                                ),
                                chave=f"presenca_ranking_absencia_{dimensao.lower()}",
                            )
                    with coluna_presenca:
                        _grafico_percentual_horizontal(
                            agrupado,
                            dimensao,
                            chave=f"presenca_ranking_pct_{dimensao.lower()}",
                        )

        st.subheader("Alerta · técnicos com mais faltas e atestados")
        dimensoes_tecnico = [
            coluna
            for coluna in ("Técnico", "Login", "Monitor", "Base")
            if coluna in filtrado.columns
        ]
        if not dimensoes_tecnico or filtrado.empty:
            st.info("Sem dados suficientes para identificar técnicos no recorte.")
        else:
            ranking_tecnicos = agrupar_marcacoes_presenca(filtrado, colunas_dias, dimensoes_tecnico)
            ranking_tecnicos = (
                ranking_tecnicos.loc[ranking_tecnicos["FALTA + ATESTADO"].gt(0)]
                .sort_values(
                    ["FALTA + ATESTADO", "FALTA", "ATESTADO", "Técnico"],
                    ascending=[False, False, False, True],
                )
                .head(10)
                .reset_index(drop=True)
            )
            if ranking_tecnicos.empty:
                st.success(
                    "Nenhuma FALTA ou ATESTADO registrado no mês para os filtros selecionados."
                )
            else:
                ranking_tecnicos.insert(0, "Posição", range(1, len(ranking_tecnicos) + 1))
                colunas_alerta = [
                    coluna
                    for coluna in (
                        "Posição",
                        "Técnico",
                        "Login",
                        "Monitor",
                        "Base",
                        "FALTA",
                        "ATESTADO",
                        "FALTA + ATESTADO",
                        "% Presença",
                    )
                    if coluna in ranking_tecnicos.columns
                ]
                st.dataframe(
                    _tabela_percentual_exibicao(ranking_tecnicos[colunas_alerta]),
                    width="stretch",
                    hide_index=True,
                )

    aba_tabela, aba_resumo = st.tabs(["Tabela detalhada", "Resumo por Monitor e Base"])
    with aba_tabela:
        if colunas_dias:
            estilizado = recorte_exportacao.style.map(
                _estilo_celula_presenca_externa, subset=colunas_dias
            )
            st.dataframe(estilizado, width="stretch", hide_index=True)
        else:
            st.dataframe(recorte_exportacao, width="stretch", hide_index=True)

    with aba_resumo:
        if not colunas_dias or not dimensoes_resumo or resumo_monitor_base.empty:
            st.info("Sem dados suficientes para agrupar por Monitor e Base.")
        else:
            colunas_resumo = [
                coluna
                for coluna in (
                    "Monitor",
                    "Base",
                    "Técnicos",
                    "ATIVO",
                    "FALTA",
                    "ATESTADO",
                    "FALTA + ATESTADO",
                    "Não preenchido",
                    "Outros",
                    "% Presença",
                )
                if coluna in resumo_monitor_base.columns
            ]
            st.dataframe(
                _tabela_percentual_exibicao(resumo_monitor_base[colunas_resumo]),
                width="stretch",
                hide_index=True,
            )


aba_painel, aba_chamada = st.tabs(
    ["Painel executivo", "Preencher presença do dia"],
    key="absenteismo_aba_principal",
    on_change="rerun",
)
if aba_painel.open:
    with aba_painel:
        _render_planilha_externa()
if aba_chamada.open:
    with aba_chamada:
        _render_chamada_diaria()

fechar_dashboard()
