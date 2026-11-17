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
import streamlit as st

from components.componentes import aplicar_estilo, render_empty_state, render_insight
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.forca_trabalho import render_forca_trabalho
from components.graficos import (
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
    montar_matriz_ausencias,
    normalizar_registros,
    resumir_controle,
    serie_diaria_ausencias,
)
from services.absenteismo_grade import (
    filtrar_grade_preenchimento,
    resumir_grade,
)
from services.dados_sessao import resumir_carga, ultima_atualizacao
from services.forca_trabalho import calcular_forca_trabalho
from services.hierarquia import lista_ativos_da_sessao
from services.lista_presenca import (
    OPCOES_PRESENCA,
    montar_lista_presenca,
    registros_da_presenca,
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
from services.texto import escapar_html, formatar_inteiro, formatar_percentual

logger = logging.getLogger(__name__)

#: Seções ancoradas do sumário (mesmos títulos usados em ``secao()``).
SECOES_PAGINA: tuple[str, ...] = (
    "Força de Trabalho",
    "Mapa Mensal de Ausências",
    "Indicadores do Período",
    "Registrar Ausência",
    "Ausências por Tipo",
    "Calendário de Ausências",
    "Ranking por Base e Monitor",
    "Ausentes Hoje e Próximas Ausências",
    "Registros do Controle",
    "Exportação",
)

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


lista_ativos = lista_ativos_da_sessao(aba=SHEET_ABA_ATIVOS, ttl=600)
registros, qtd_pendentes = _carregar_registros()
hoje = date.today()
datas_grade = st.session_state[CHAVE_SNAPSHOT]["dias"]
mes_inicio, mes_fim = _primeiro_e_ultimo_dia_mes(hoje if hoje in datas_grade else min(datas_grade))

# A lista da própria grade é o quadro da chamada; não cria linhas implicitamente.
quadro_df = st.session_state[CHAVE_SNAPSHOT]["pessoas"].rename(columns={
    "Login": "LOGIN", "Técnico": "TÉCNICO", "Monitor": "MONITOR", "Base": "BASE",
}).copy()

abrir_dashboard(
    "Lista de Presença",
    subtitulo=(
        "Presença diária, faltas, folgas, férias e afastamentos do quadro "
        "— leitura e preenchimento direto na aba absenteismo."
    ),
    icone="🗓️",
    secoes=SECOES_PAGINA,
    resumo=resumir_carga(registros, atualizado_em=ultima_atualizacao()),
    origem="absenteismo (grade mensal) · cadastro auxiliar: lista_ativos",
)

st.caption(
    f"Fonte principal: aba absenteismo · datas de {min(datas_grade):%d/%m/%Y} a {max(datas_grade):%d/%m/%Y}. "
    "Presente é gravado como ATIVO. Somente células alteradas são atualizadas; cadastros, fórmulas e formatação permanecem intactos."
)

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
with st.sidebar:
    st.markdown("### 🗓️ Filtros — Lista de Presença")
    periodo_inicio = st.date_input(
        "Início do período", value=mes_inicio, key="absenteismo_periodo_inicio"
    )
    periodo_fim = st.date_input("Fim do período", value=mes_fim, key="absenteismo_periodo_fim")
    if periodo_fim < periodo_inicio:
        periodo_inicio, periodo_fim = periodo_fim, periodo_inicio
    bases_disponiveis = sorted(
        set(registros["Base"].replace("", "Não informado"))
        | set(quadro_df["BASE"].replace("", "Não informado"))
    )
    monitores_disponiveis = sorted(
        set(registros["Monitor"].replace("", "Não informado"))
        | set(quadro_df["MONITOR"].replace("", "Não informado"))
    )
    bases_sel = st.multiselect(
        "Base",
        bases_disponiveis,
        key="absenteismo_filtro_base",
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
        lista_ativos_da_sessao(aba=SHEET_ABA_ATIVOS, ttl=600, forcar=True)
        st.rerun()


def _aplicar_recorte(df: pd.DataFrame) -> pd.DataFrame:
    """Recorte da sidebar (base/monitor/tipo/busca) sobre os registros."""
    recorte = df.copy()
    if bases_sel:
        recorte = recorte[recorte["Base"].replace("", "Não informado").isin(bases_sel)]
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
        quadro_recorte["BASE"].replace("", "Não informado").isin(bases_sel)
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
_CORES_MAPA: dict[str, tuple[str, str]] = {
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
    """``<td>`` de um dia: vazia (presente) ou com o código e a cor do tipo."""
    codigo = str(valor or "").strip()
    if not codigo:
        return '<td class="abs-cel abs-vazia"></td>'
    primeiro = codigo.split("/")[0].strip().upper()
    fundo, cor = _CORES_MAPA.get(primeiro, _CORES_MAPA["OUT"])
    titulo = escapar_html(codigo, aspas=True)
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

    st.caption("Fonte: grade absenteismo. Use Preencher para editar; apenas as células alteradas são gravadas.")
    st.caption(
        f"Período do mapa: **{_rotulo_dia(inicio)} a {_rotulo_dia(fim)}** "
        f"({len(dias)} dias) · usa o mês do início do período · "
        "célula vazia = **sem ausência no recorte** · "
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
        int((matriz[dia].fillna("").astype(str).str.strip() != "").sum())
        if dia in matriz
        else 0
        for dia in dias
    ]
    total_geral = sum(totais_dia)
    rodape = (
        '<tr><td class="abs-rodape-rotulo" colspan="6">TOTAL DE AUSÊNCIAS '
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
        "Para editar, use **Preencher**. O mapa de ausências não trata células vazias como presença."
    )

    legenda = "".join(
        f'<span class="abs-legenda-item">'
        f'<span class="abs-legenda-codigo" style="background:{_CORES_MAPA.get(codigo, _CORES_MAPA["OUT"])[0]};'
        f'color:{_CORES_MAPA.get(codigo, _CORES_MAPA["OUT"])[1]}">{codigo}</span>'
        f"{escapar_html(tipo)}</span>"
        for tipo, codigo in ABREVIACOES_AUSENCIA.items()
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
                "Unidade de negócio",
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
    _render_acoes_presenca(matriz, dia_resumo)
    col_pendentes, col_detalhes, col_link = st.columns([1.3, 1.3, 1])
    with col_pendentes:
        somente_pendentes = st.toggle("Somente pendentes", key="presenca_so_pendentes")
    with col_detalhes:
        mostrar_detalhes = st.toggle("Exibir dados cadastrais", key="presenca_dados_cadastrais")
    with col_link:
        st.link_button("Abrir no Drive ↗", f"https://docs.google.com/spreadsheets/d/{obter_sheet_id_ativos()}/edit")
    if somente_pendentes:
        matriz = matriz.loc[matriz[dias_visiveis].eq("Não preenchido").any(axis=1)].copy()
    if matriz.empty:
        st.success("Chamada concluída para os dias exibidos. Nenhum técnico pendente neste recorte.")
        return
    matriz = filtrar_grade_preenchimento(matriz, dias_visiveis)
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
    versao = hashlib.sha256(matriz.to_csv(index=False).encode()).hexdigest()[:16]
    st.caption(f"{len(matriz)} técnico(s) na lista · selecione a situação na célula · salvamento automático")
    editada = st.data_editor(
        tabela_editor, hide_index=True, num_rows="fixed",
        disabled=[c for c in tabela_editor.columns if c not in nomes_dias.values()],
        column_config=configuracao, column_order=ordem,
        height=min(600, 40 + len(matriz) * 35), width="stretch",
        key=f"absenteismo_grade_editor_{versao}",
    ).rename(columns={nome: dia for dia, nome in nomes_dias.items()})
    with st.expander("Como preencher e corrigir marcações"):
        st.markdown("**Não preenchido** é uma pendência. Selecione **Presente** para confirmar a presença ou escolha o motivo da ausência.")
        st.caption("O preenchimento atua apenas em dias pendentes. Para corrigir uma marcação, use a aba Corrigir com histórico. A auditoria preserva o valor anterior. Em falha de envio, os dados ficam apenas nesta sessão.")
    try:
        novos = registros_da_presenca(matriz, editada)
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
        quadro_mapa["BASE"].replace("", "Não informado").isin(bases_sel)
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
matriz_mapa = montar_matriz_ausencias(
    registros_recorte, quadro_mapa, inicio=mapa_inicio, fim=mapa_fim
)

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


with secao(
    "Mapa Mensal de Ausências",
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
        resumo_mapa = resumir_grade(matriz_mapa)
        col_quadro, col_ausentes, col_dias = st.columns(3)
        col_quadro.metric("Técnicos no mapa", resumo_mapa["tecnicos"])
        col_ausentes.metric("Com ausência no mês", resumo_mapa["com_ausencia"])
        col_dias.metric("Dias marcados", resumo_mapa["dias_marcados"])
        st.caption("Resumo do mês e dos filtros atuais. Dois códigos no mesmo dia contam como um dia marcado.")
        ultima_sync = st.session_state.get("absenteismo_ultima_sync")
        if qtd_pendentes:
            st.warning(f"{qtd_pendentes} lançamento(s) somente nesta sessão — sincronização pendente.")
        elif ultima_sync and ultima_sync["ok"]:
            st.caption(f"Última gravação confirmada no Drive: {ultima_sync['horario']}")
        elif ultima_sync:
            st.warning(f"Última tentativa sem confirmação: {ultima_sync['horario']}. Confira as pendências antes de fechar a sessão.")
        preencher = st.toggle(
            "Preencher lista de presença", value=True,
            help="Edita as células dos técnicos e dias que já existem na aba absenteismo.",
            key="absenteismo_preencher_grade",
        )
        if preencher:
            aba_edicao, aba_visualizacao = st.tabs(["Preencher", "Visualizar e exportar"])
            with aba_edicao:
                lista_presenca = montar_lista_presenca(
                    registros, quadro_mapa, mapa_inicio, mapa_fim
                )
                _render_preenchimento_mapa(lista_presenca)
            with aba_visualizacao:
                _render_mapa_mensal(matriz_mapa, mapa_inicio, mapa_fim)
        else:
            _render_mapa_mensal(matriz_mapa, mapa_inicio, mapa_fim)


# ============================================================
# INDICADORES DO PERÍODO
# ============================================================
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


with secao(
    "Registrar Ausência",
    icone="edit_calendar",
    subtitulo="O lançamento preenche somente dias e técnicos já cadastrados na grade absenteismo.",
):
    _render_formulario_ausencia()


# ============================================================
# AUSÊNCIAS POR TIPO / CALENDÁRIO / RANKINGS
# ============================================================
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

# ============================================================
# EXPORTAÇÃO
# ============================================================
secao_exportacao(
    _tabela_exibicao(exibidos if not exibidos.empty else registros_recorte),
    nome_arquivo="presenca_grade_absenteismo",
    chave="absenteismo",
)

fechar_dashboard()
