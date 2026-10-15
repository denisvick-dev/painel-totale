"""
config/navegacao.py
===================
Mapa de navegação do portal — fonte única de menu, ordem, ícones e descrições.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
As páginas do sistema eram declaradas dentro de ``streamlit_app.py``, em um
``dict`` montado na hora por ``GerenciadorNavegacao._definir_paginas()``. O menu
era, portanto, impossível de reaproveitar: a página inicial não conseguia listar
os painéis disponíveis, os testes não tinham como conferir a cobertura do menu e
qualquer reorganização exigia mexer no entrypoint inteiro.

Aqui o menu vira **dado**:

* :data:`PAGINAS` é a lista ordenada de :class:`PaginaPortal` (arquivo, título,
  ícone, grupo e uma descrição de uma linha);
* :data:`GRUPOS` define as seções da barra lateral, na ordem de leitura do
  gestor (visão geral → performance → campo → SLA → cadastros → utilitários);
* :func:`mapa_de_navegacao` devolve o ``dict[str, list[st.Page]]`` que o
  ``st.navigation`` consome;
* :func:`paginas_do_grupo` / :func:`pagina_por_arquivo` servem à página
  ``Visão Geral``, aos testes e a qualquer atalho de navegação.

Regras:

* todo arquivo de ``pages/`` aparece em :data:`PAGINAS`; módulos de apoio
  ficam em ``services/`` ou ``components/`` — o guarda
  ``tests/test_organizacao_dashboards.py`` confere isso;
* a URL de cada página continua sendo derivada do nome do arquivo
  (``pages/pontos.py`` → ``/pontos``), então renomear título/ícone não quebra
  links compartilhados;
* ícone é único por página: repetir ``⚡``/``📉`` em itens vizinhos fazia o menu
  parecer um bloco só.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # evita importar Streamlit em quem só quer os metadados
    import streamlit as st

VERSAO_NAVEGACAO = "1.0.0"

#: Nome do grupo de painéis que abrem o portal.
GRUPO_VISAO_GERAL = "Visão Geral"
GRUPO_PERFORMANCE = "Central de Performance"
GRUPO_CAMPO = "Rotas & Campo"
GRUPO_SLA = "SLA & Quebra"
GRUPO_CADASTROS = "Cadastros & Disparos"
GRUPO_UTILITARIOS = "Utilitários"

#: Ordem das seções na barra lateral.
GRUPOS: tuple[str, ...] = (
    GRUPO_VISAO_GERAL,
    GRUPO_PERFORMANCE,
    GRUPO_CAMPO,
    GRUPO_SLA,
    GRUPO_CADASTROS,
    GRUPO_UTILITARIOS,
)

#: Uma linha de contexto por seção (usada na página Visão Geral).
DESCRICAO_GRUPOS: dict[str, str] = {
    GRUPO_VISAO_GERAL: "Ponto de entrada: o estado das fontes e a carga dos dados.",
    GRUPO_PERFORMANCE: "Produção, metas e indicadores por técnico, equipe e supervisor.",
    GRUPO_CAMPO: "Roteirização, volumetria e o que acontece na ponta (rua).",
    GRUPO_SLA: "Quebra de SLA por segmento, região e causa raiz.",
    GRUPO_CADASTROS: "Cadastros de apoio e disparos diários automáticos.",
    GRUPO_UTILITARIOS: "Ferramentas que não são painel (assinatura de e-mail).",
}


@dataclass(frozen=True)
class PaginaPortal:
    """Metadados de uma página do portal (menu, ícone, grupo e descrição)."""

    arquivo: str
    titulo: str
    icone: str
    grupo: str
    descricao: str = ""
    padrao: bool = False
    visivel: bool = True

    @property
    def caminho(self) -> str:
        """Caminho relativo usado por ``st.Page`` (``pages/<arquivo>``)."""
        return f"pages/{self.arquivo}"


#: Todas as páginas do portal, na ordem em que aparecem dentro de cada grupo.
PAGINAS: tuple[PaginaPortal, ...] = (
    # ── Visão Geral ──────────────────────────────────────────────────────
    PaginaPortal(
        arquivo="home.py",
        titulo="Home",
        icone="🏠",
        grupo=GRUPO_VISAO_GERAL,
        descricao="Estado das fontes, última sincronização e atalhos do portal.",
        padrao=True,
    ),
    PaginaPortal(
        arquivo="visao_geral.py",
        titulo="Visão Geral",
        icone="🧭",
        grupo=GRUPO_VISAO_GERAL,
        descricao="Índice de todos os dashboards, agrupados por área.",
    ),
    PaginaPortal(
        arquivo="envio_excel.py",
        titulo="Atualização de Dados",
        icone="🔁",
        grupo=GRUPO_VISAO_GERAL,
        descricao="Sincroniza planilhas (Sheets/Drive/upload) e alimenta os painéis.",
    ),
    # ── Central de Performance ───────────────────────────────────────────
    PaginaPortal(
        arquivo="pontos.py",
        titulo="Produção Mensal",
        icone="📈",
        grupo=GRUPO_PERFORMANCE,
        descricao="Pontos e O.S. por técnico, equipe e supervisor no mês.",
    ),
    PaginaPortal(
        arquivo="qtde_os.py",
        titulo="Quantidade de O.S.",
        icone="⚡",
        grupo=GRUPO_PERFORMANCE,
        descricao="Volumetria, projeção de fechamento e metas por supervisor/projeto.",
    ),
    PaginaPortal(
        arquivo="consultivo.py",
        titulo="Consultivos",
        icone="📋",
        grupo=GRUPO_PERFORMANCE,
        descricao="Consultivos por base e monitor, com ranking e resumo diário.",
    ),
    PaginaPortal(
        arquivo="dashboard_meta.py",
        titulo="Metas Operacionais",
        icone="🎯",
        grupo=GRUPO_PERFORMANCE,
        descricao="Atingimento de metas por equipe, com folga e ritmo necessário.",
    ),
    PaginaPortal(
        arquivo="indicadores.py",
        titulo="Indicadores",
        icone="🧮",
        grupo=GRUPO_PERFORMANCE,
        descricao="Painel consolidado de indicadores por período, base e categoria.",
    ),
    # ── Rotas & Campo ────────────────────────────────────────────────────
    PaginaPortal(
        arquivo="rota_inicial.py",
        titulo="Rota Inicial",
        icone="🗺️",
        grupo=GRUPO_CAMPO,
        descricao="Mapa e roteirização da carga inicial por município.",
    ),
    PaginaPortal(
        arquivo="rota_geral.py",
        titulo="Rota Geral",
        icone="🚏",
        grupo=GRUPO_CAMPO,
        descricao="Visão geral de rotas, turnos e distribuição da equipe.",
    ),
    PaginaPortal(
        arquivo="volumetria.py",
        titulo="Volumetria",
        icone="📊",
        grupo=GRUPO_CAMPO,
        descricao="Técnicos escalados × montados e projeção de demanda.",
    ),
    PaginaPortal(
        arquivo="retorno.py",
        titulo="Retornos",
        icone="↩️",
        grupo=GRUPO_CAMPO,
        descricao="Retornos por equipe e cruzamento com a base Sinapse.",
    ),
    PaginaPortal(
        arquivo="p_atendimento.py",
        titulo="1º Atendimento",
        icone="🚙",
        grupo=GRUPO_CAMPO,
        descricao="Primeiro atendimento: horários, pendências e ranking de monitores.",
    ),
    # ── SLA & Quebra ─────────────────────────────────────────────────────
    PaginaPortal(
        arquivo="quebra_geral.py",
        titulo="Quebra Geral",
        icone="📉",
        grupo=GRUPO_SLA,
        descricao="Quebra de SLA consolidada, matriz executiva e auditoria.",
    ),
    PaginaPortal(
        arquivo="quebra_unificada.py",
        titulo="Quebra por Segmento",
        icone="🧩",
        grupo=GRUPO_SLA,
        descricao="Novos Domicílios, PME e Migração lado a lado, com causa raiz.",
    ),
    # ── Cadastros & Disparos ─────────────────────────────────────────────
    PaginaPortal(
        arquivo="gestao_ativos.py",
        titulo="Gestão de Ativos",
        icone="👷",
        grupo=GRUPO_CADASTROS,
        descricao="Cadastro de técnicos, bases e monitores (com trilha de auditoria).",
    ),
    # ── Utilitários ──────────────────────────────────────────────────────
    PaginaPortal(
        arquivo="assinatura.py",
        titulo="Assinatura de E-mail",
        icone="✉️",
        grupo=GRUPO_UTILITARIOS,
        descricao="Gerador de assinatura corporativa de e-mail.",
    ),
)

#: Dashboards que seguem o padrão de organização da v3.7.0 (abertura com
#: ``components.dashboards.abrir_dashboard``, base via ``services.dados_sessao``
#: e fechamento com ``fechar_dashboard``). O guarda
#: ``tests/test_organizacao_dashboards.py`` impede que uma página saia do padrão.
DASHBOARDS_PADRONIZADOS: tuple[str, ...] = (
    "home.py",
    "visao_geral.py",
    "pontos.py",
    "qtde_os.py",
    "consultivo.py",
    "dashboard_meta.py",
    "indicadores.py",
    "rota_inicial.py",
    "rota_geral.py",
    "volumetria.py",
    "retorno.py",
    "p_atendimento.py",
    "quebra_geral.py",
    "quebra_unificada.py",
)


def paginas_do_grupo(grupo: str) -> list[PaginaPortal]:
    """Páginas de uma seção do menu, na ordem declarada."""
    return [p for p in PAGINAS if p.grupo == grupo]


def pagina_por_arquivo(arquivo: str) -> PaginaPortal | None:
    """Metadados de uma página a partir do nome do arquivo (``pontos.py``)."""
    nome = str(arquivo or "").strip().split("/")[-1]
    return next((p for p in PAGINAS if p.arquivo == nome), None)


def grupos_ordenados() -> list[str]:
    """Seções que possuem ao menos uma página (na ordem do menu)."""
    presentes = {p.grupo for p in PAGINAS}
    return [grupo for grupo in GRUPOS if grupo in presentes]


def mapa_de_paginas() -> dict[str, list["st.Page"]]:
    """``dict`` de seções → ``st.Page`` consumido por ``st.navigation``."""
    import streamlit as st

    mapa: dict[str, list[st.Page]] = {}
    for grupo in grupos_ordenados():
        mapa[grupo] = [
            st.Page(
                pagina.caminho,
                title=pagina.titulo,
                icon=pagina.icone,
                default=pagina.padrao,
                visibility="visible" if pagina.visivel else "hidden",
            )
            for pagina in paginas_do_grupo(grupo)
        ]
    return mapa


def mapa_de_navegacao() -> dict[str, list["st.Page"]]:
    """Sinônimo público de :func:`mapa_de_paginas` (contrato do entrypoint)."""
    return mapa_de_paginas()


__all__ = [
    "DASHBOARDS_PADRONIZADOS",
    "DESCRICAO_GRUPOS",
    "GRUPO_CADASTROS",
    "GRUPO_CAMPO",
    "GRUPO_PERFORMANCE",
    "GRUPO_SLA",
    "GRUPO_UTILITARIOS",
    "GRUPO_VISAO_GERAL",
    "GRUPOS",
    "PAGINAS",
    "PaginaPortal",
    "VERSAO_NAVEGACAO",
    "grupos_ordenados",
    "mapa_de_navegacao",
    "mapa_de_paginas",
    "pagina_por_arquivo",
    "paginas_do_grupo",
]
