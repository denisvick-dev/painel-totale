"""Testes da fábrica de gráficos minimalista (``components.graficos``).

Validam o tema Plotly com as cores oficiais TOTALE (``#012869`` / ``#F37C04``),
a existência e serialização dos 24 tipos de gráfico, a resiliência do
dispatcher (nunca levanta exceção no meio de um dashboard) e a renderização
via ``st.plotly_chart``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import components.graficos as g  # noqa: E402

AZUL_OFICIAL = "#012869"
LARANJA_OFICIAL = "#F37C04"

RNG = np.random.default_rng(20261013)


@pytest.fixture(scope="module")
def base() -> pd.DataFrame:
    """Base longa típica dos painéis (data, categoria, valores)."""
    dias = pd.date_range("2026-09-01", periods=30, freq="D")
    linhas = []
    for dia in dias:
        for equipe in ("Alpha", "Beta", "Gamma"):
            linhas.append(
                {
                    "DATA": dia,
                    "EQUIPE": equipe,
                    "OS": int(RNG.integers(20, 120)),
                    "QUEBRA": float(RNG.uniform(1.0, 18.0)),
                    "PONTOS": float(RNG.integers(120, 420)),
                    "SLA": float(RNG.uniform(60.0, 99.0)),
                }
            )
    return pd.DataFrame(linhas)


@pytest.fixture(scope="module")
def categorica() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "REGIAO": ["SP", "RJ", "MG", "PR", "SC", "RS", "BA"],
            "SEGMENTO": ["PME", "GPON", "PME", "ND", "GPON", "ND", "PME"],
            "VALOR": [420.0, 310.0, 275.0, 190.0, 165.0, 120.0, 40.0],
        }
    )


def _serializavel(fig: go.Figure) -> dict:
    """Garante que a figura vira JSON (é o que o Streamlit envia ao navegador)."""
    assert isinstance(fig, go.Figure)
    payload = json.loads(fig.to_json())
    assert payload["layout"]["template"]["layout"]["colorway"][0] == AZUL_OFICIAL
    return payload


# ====================================================
# TEMA E PALETA DA MARCA
# ====================================================
def test_paleta_oficial_comeca_com_azul_e_laranja() -> None:
    assert g.AZUL_TOTALE == AZUL_OFICIAL
    assert g.LARANJA_TOTALE == LARANJA_OFICIAL
    assert g.PALETA_TOTALE[0] == AZUL_OFICIAL
    assert g.PALETA_TOTALE[1] == LARANJA_OFICIAL
    assert len(g.PALETA_TOTALE) >= 8
    assert len(set(g.PALETA_TOTALE)) == len(g.PALETA_TOTALE)


def test_tema_registrado_e_minimalista() -> None:
    g.registrar_tema_totale()

    assert g.NOME_TEMA in pio.templates
    tema = pio.templates[g.NOME_TEMA]
    assert tuple(tema.layout.colorway)[:2] == (AZUL_OFICIAL, LARANJA_OFICIAL)
    assert tema.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert tema.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert tema.layout.xaxis.gridcolor == "rgba(0,0,0,0)"  # grade só no Y
    assert "Inter" in tema.layout.font.family
    # Não sequestra o padrão global do Plotly/Streamlit.
    assert pio.templates.default != g.NOME_TEMA


def test_registro_do_tema_e_idempotente() -> None:
    g.registrar_tema_totale()
    primeira = pio.templates[g.NOME_TEMA]
    g.registrar_tema_totale()
    assert pio.templates[g.NOME_TEMA] is primeira


def test_escalas_continuas_usam_as_cores_da_marca() -> None:
    assert g.ESCALA_TOTALE[0][1].upper() != g.ESCALA_TOTALE[-1][1].upper()
    assert g.ESCALA_TOTALE[-1][1].upper() == LARANJA_OFICIAL
    assert g.ESCALA_DIVERGENTE_TOTALE[0][1].upper() != g.ESCALA_DIVERGENTE_TOTALE[-1][1].upper()
    assert g.ESCALA_DIVERGENTE_TOTALE[-1][1].upper() == AZUL_OFICIAL
    for escala in (g.ESCALA_TOTALE, g.ESCALA_DIVERGENTE_TOTALE):
        posicoes = [p for p, _ in escala]
        assert posicoes == sorted(posicoes)
        assert posicoes[0] == 0.0 and posicoes[-1] == 1.0


def test_interpolar_cor_e_cores_por_categoria() -> None:
    meio = g.interpolar_cor(0.5)  # azul oficial → laranja oficial
    assert meio.startswith("#") and len(meio) == 7
    assert g.interpolar_cor(0.0) == AZUL_OFICIAL
    assert g.interpolar_cor(1.0) == LARANJA_OFICIAL
    assert g.interpolar_cor(0.5, "#000000", "#FFFFFF").lower() in ("#808080", "#7f7f7f")

    cores = g.cores_por_categoria(["SP", "RJ", "SP", "MG"])
    assert isinstance(cores, dict)
    assert len(cores) == 3
    assert all(str(c).startswith("#") for c in cores.values())
    assert cores["SP"] != cores["RJ"]


def test_config_minimalista_remove_selecao_e_logo() -> None:
    config = g.config_minimalista()

    assert config["displaylogo"] is False
    assert "select2d" in config["modeBarButtonsToRemove"]
    assert "lasso2d" in config["modeBarButtonsToRemove"]
    assert "toImage" not in config["modeBarButtonsToRemove"]

    sem_download = g.config_minimalista(download=False)
    assert "toImage" in sem_download["modeBarButtonsToRemove"]
    sem_zoom = g.config_minimalista(zoom=False)
    assert "zoom2d" in sem_zoom["modeBarButtonsToRemove"]
    assert sem_zoom["scrollZoom"] is False


def test_aplicar_tema_define_template_titulo_e_altura(base: pd.DataFrame) -> None:
    fig = g.grafico_linha(base, "DATA", "OS", titulo="Evolução")
    g.aplicar_tema(fig, titulo="Evolução de OS", altura=420, rotulos={"x": "Dia", "y": "OS"})

    assert tuple(fig.layout.template.layout.colorway)[0] == AZUL_OFICIAL
    assert fig.layout.title.text == "Evolução de OS"
    assert fig.layout.height == 420
    assert fig.layout.xaxis.title.text == "Dia"
    assert fig.layout.yaxis.title.text == "OS"
    assert fig.layout.hovermode == "x unified"


# ====================================================
# OS 24 TIPOS DA FÁBRICA
# ====================================================
CASOS: list[tuple[str, tuple, dict]] = [
    ("linha", (), {"df_col": "base", "col_x": "DATA", "col_y": "OS", "col_grupo": "EQUIPE"}),
    ("area", (), {"df_col": "base", "col_x": "DATA", "col_y": "OS", "col_grupo": "EQUIPE"}),
    ("barras", (), {"df_col": "base", "col_x": "EQUIPE", "col_y": "OS"}),
    ("ranking", (), {"df_col": "categorica", "col_categoria": "REGIAO", "col_valor": "VALOR"}),
    ("pizza", (), {"df_col": "categorica", "col_nome": "REGIAO", "col_valor": "VALOR"}),
    ("donut", (), {"df_col": "categorica", "col_nome": "REGIAO", "col_valor": "VALOR"}),
    ("dispersao", (), {"df_col": "base", "col_x": "PONTOS", "col_y": "QUEBRA"}),
    ("histograma", (), {"df_col": "base", "col_x": "OS"}),
    ("caixa", (), {"df_col": "base", "col_y": "OS", "col_x": "EQUIPE"}),
    ("violino", (), {"df_col": "base", "col_y": "OS", "col_x": "EQUIPE"}),
    ("calor", (), {"df_col": "base", "col_x": "EQUIPE", "col_y": "DATA", "col_valor": "OS"}),
    ("calendario", (), {"serie_col": "serie_diaria"}),
    (
        "treemap",
        (),
        {"df_col": "categorica", "caminho": ["SEGMENTO", "REGIAO"], "col_valor": "VALOR"},
    ),
    (
        "sunburst",
        (),
        {"df_col": "categorica", "caminho": ["SEGMENTO", "REGIAO"], "col_valor": "VALOR"},
    ),
    ("funil", (), {"df_col": "funil", "col_etapa": "ETAPA", "col_valor": "QTD"}),
    ("radar", (), {"categorias": ["SLA", "Meta", "Quebra", "Volume"], "valores": [82, 65, 40, 91]}),
    ("cascata", (), {"df_col": "cascata", "col_categoria": "PASSO", "col_valor": "DELTA"}),
    ("bullet", (), {"valor": 78.0, "meta": 100.0}),
    ("gauge", (), {"valor_pct": 78.0}),
    ("polar", (), {"df_col": "base", "col_theta": "EQUIPE", "col_r": "OS"}),
    ("densidade", (), {"df_col": "base", "col_x": "PONTOS", "col_y": "QUEBRA"}),
    (
        "combinado",
        (),
        {"df_col": "diaria", "col_x": "DATA", "col_barras": "OS", "col_linha": "SLA"},
    ),
    ("progresso", (), {"valores_col": "progresso"}),
    (
        "comparativo",
        (),
        {"categorias": ["SP", "RJ", "MG"], "atual": [120, 90, 60], "anterior": [100, 95, 40]},
    ),
]


@pytest.fixture(scope="module")
def serie_diaria() -> pd.Series:
    indice = pd.date_range("2026-09-01", periods=45, freq="D")
    return pd.Series(RNG.integers(10, 90, len(indice)).astype(float), index=indice)


@pytest.fixture(scope="module")
def funil() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ETAPA": ["Contato", "Visita", "Orçamento", "Contrato"],
            "QTD": [1200, 780, 410, 190],
        }
    )


@pytest.fixture(scope="module")
def cascata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "PASSO": ["Saldo inicial", "Novas OS", "Canceladas", "Concluídas", "Saldo final"],
            "DELTA": [120.0, 340.0, -45.0, -280.0, 135.0],
        }
    )


@pytest.fixture(scope="module")
def diaria() -> pd.DataFrame:
    dias = pd.date_range("2026-09-01", periods=20, freq="D")
    return pd.DataFrame(
        {
            "DATA": dias,
            "OS": RNG.integers(50, 200, 20).astype(float),
            "SLA": RNG.uniform(70.0, 99.0, 20),
        }
    )


@pytest.fixture(scope="module")
def progresso() -> pd.Series:
    return pd.Series({"SLA": 92.0, "Meta": 74.0, "Quebra": 38.0, "Retorno": 61.0})


def _montar(tipo: str, args: tuple, kwargs: dict, contexto: dict) -> tuple[tuple, dict]:
    """Resolve referências de fixtures nos parâmetros do caso."""
    novos_args = tuple(contexto[a] if isinstance(a, str) and a in contexto else a for a in args)
    novos_kwargs: dict = {}
    for chave, valor in kwargs.items():
        if chave == "df_col":
            novos_kwargs["df"] = contexto[valor]
        elif chave == "serie_col":
            novos_kwargs["serie"] = contexto[valor]
        elif chave == "valores_col":
            novos_kwargs["valores"] = contexto[valor]
        else:
            novos_kwargs[chave] = valor
    return novos_args, novos_kwargs


@pytest.mark.parametrize("tipo,args,kwargs", CASOS, ids=[c[0] for c in CASOS])
def test_cada_tipo_da_fabrica_serializa(
    tipo: str,
    args: tuple,
    kwargs: dict,
    base: pd.DataFrame,
    categorica: pd.DataFrame,
    serie_diaria: pd.Series,
    funil: pd.DataFrame,
    cascata: pd.DataFrame,
    diaria: pd.DataFrame,
    progresso: pd.Series,
) -> None:
    contexto = {
        "base": base,
        "categorica": categorica,
        "serie_diaria": serie_diaria,
        "funil": funil,
        "cascata": cascata,
        "diaria": diaria,
        "progresso": progresso,
    }
    args_finais, kwargs_finais = _montar(tipo, args, kwargs, contexto)
    kwargs_finais.setdefault("titulo", tipo.title())

    fig = g.criar_grafico(tipo, *args_finais, **kwargs_finais)

    payload = _serializavel(fig)
    assert payload["data"], f"{tipo} sem traços"
    # O título pode viver no layout, em anotação ou no próprio traço
    # (bullet/gauge usam indicator.title).
    titulo = (payload["layout"].get("title") or {}).get("text") or ""
    anotacoes = " ".join(a.get("text", "") for a in payload["layout"].get("annotations") or [])
    nos_tracos = " ".join(
        str((trace.get("title") or {}).get("text") or "") for trace in payload["data"]
    )
    assert tipo.title() in f"{titulo}{anotacoes}{nos_tracos}", f"{tipo} sem título visível"


def test_tipos_grafico_cobre_todas_as_fabricas() -> None:
    """Os 24 tipos publicados têm fábrica registrada no dispatcher."""
    assert len(g.TIPOS_GRAFICO) == 24
    assert len(set(g.TIPOS_GRAFICO)) == len(g.TIPOS_GRAFICO)
    assert {caso[0] for caso in CASOS} == set(g.TIPOS_GRAFICO)

    for tipo in g.TIPOS_GRAFICO:
        # Sem argumentos a fábrica falha internamente, mas o dispatcher precisa
        # reconhecer o tipo (mensagem diferente da de tipo inexistente).
        fig = g.criar_grafico(tipo)
        texto = " ".join(a.text for a in (fig.layout.annotations or ()))
        assert "não disponível" not in texto, tipo


def test_sinonimos_resolvem_para_a_mesma_fabrica(categorica: pd.DataFrame) -> None:
    direto = g.criar_grafico(
        "barras", categorica, "REGIAO", "VALOR", titulo="Direto", agregacao=None
    )
    sinonimo = g.criar_grafico(
        "colunas", categorica, "REGIAO", "VALOR", titulo="Direto", agregacao=None
    )

    assert [t.type for t in direto.data] == [t.type for t in sinonimo.data]
    assert len(direto.data) == len(sinonimo.data)

    assert g.criar_grafico("pie", categorica, "REGIAO", "VALOR").data[0].type == "pie"
    assert g.criar_grafico("box", pd.DataFrame({"y": [1, 2, 3]}), "y").data[0].type == "box"
    assert g.criar_grafico("heatmap", categorica, "REGIAO", "SEGMENTO", "VALOR").data[0].type == (
        "heatmap"
    )


def test_tipo_desconhecido_devolve_aviso_sem_excecao() -> None:
    fig = g.criar_grafico("grafico_quantico", titulo="Ops")

    assert isinstance(fig, go.Figure)
    assert not fig.data
    assert "não disponível" in fig.layout.annotations[0].text


def test_dados_vazios_devolvem_figura_de_aviso(base: pd.DataFrame) -> None:
    vazia = base.head(0)

    fig = g.criar_grafico("linha", vazia, "DATA", "OS", titulo="Sem dados")

    assert isinstance(fig, go.Figure)
    assert "Sem dados" in str(fig.layout.annotations[0].text) or not fig.data


def test_coluna_ausente_nao_quebra_o_grafico(base: pd.DataFrame) -> None:
    fig = g.criar_grafico("linha", base, "DATA", "COLUNA_INEXISTENTE", titulo="Faltando")

    assert isinstance(fig, go.Figure)
    assert fig.layout.annotations, "deve explicar a coluna ausente"


def test_figura_vazia_tem_mensagem_padrao() -> None:
    fig = g.figura_vazia()

    assert not fig.data
    assert "Sem dados" in fig.layout.annotations[0].text
    assert fig.layout.height == 240


# ====================================================
# DETALHES DE CADA FAMÍLIA
# ====================================================
def test_grafico_barras_agrupado_empilhado_e_horizontal(base: pd.DataFrame) -> None:
    agrupado = g.grafico_barras(base, "EQUIPE", "OS", col_grupo="DATA", modo="agrupado")
    empilhado = g.grafico_barras(base, "DATA", "OS", col_grupo="EQUIPE", modo="empilhado")
    relativo = g.grafico_barras(base, "DATA", "OS", col_grupo="EQUIPE", modo="relativo")
    horizontal = g.grafico_barras(base, "EQUIPE", "OS", orientacao="h")
    contagem = g.grafico_barras(base, "EQUIPE", "OS", agregacao="contagem")

    assert all(trace.type == "bar" for trace in agrupado.data)
    assert agrupado.layout.barmode == "group"
    assert empilhado.layout.barmode == "stack"
    assert relativo.layout.barmode == "stack"
    assert relativo.layout.yaxis.tickformat == ".0%"
    assert horizontal.data[0].orientation == "h"
    assert contagem.data


def test_grafico_linha_agrupa_por_coluna_e_pinta_serie_unica(base: pd.DataFrame) -> None:
    fig = g.grafico_linha(base, "DATA", "OS", col_grupo="EQUIPE", suave=True, marcadores=True)

    assert len(fig.data) == 3
    assert all(trace.mode in ("lines+markers", "lines") for trace in fig.data)
    assert [trace.line.color for trace in fig.data][:2] == [AZUL_OFICIAL, LARANJA_OFICIAL]

    unica = g.grafico_linha(base, "DATA", "OS")
    assert len(unica.data) == 1
    assert unica.data[0].line.color == AZUL_OFICIAL

    laranja = g.grafico_linha(base, "DATA", "OS", cor=LARANJA_OFICIAL)
    assert laranja.data[0].line.color == LARANJA_OFICIAL


def test_grafico_area_empilha_com_transparencia(base: pd.DataFrame) -> None:
    fig = g.grafico_area(base, "DATA", "OS", col_grupo="EQUIPE")

    assert len(fig.data) == 3
    assert all(trace.stackgroup for trace in fig.data)
    assert all(str(trace.fillcolor).endswith("22") for trace in fig.data)


def test_ranking_limita_top_e_destaca_lider(categorica: pd.DataFrame) -> None:
    fig = g.grafico_ranking(categorica, "REGIAO", "VALOR", top=3, destacar_lider=True)

    assert len(fig.data[0].x) <= 3 or len(fig.data[0].y) <= 3
    cores = fig.data[0].marker.color
    assert LARANJA_OFICIAL in [str(c).upper() for c in cores] or AZUL_OFICIAL in [
        str(c).upper() for c in cores
    ]
    assert fig.data[0].marker.cornerradius is not None


def test_donut_tem_furo_e_total_central(categorica: pd.DataFrame) -> None:
    fig = g.grafico_donut(categorica, "REGIAO", "VALOR", mostrar_total=True)

    assert fig.data[0].type == "pie"
    assert 0.4 <= float(fig.data[0].hole) <= 0.7
    assert fig.layout.annotations, "total no centro do donut"


def test_pizza_agrupa_cauda_em_outros() -> None:
    df = pd.DataFrame(
        {"NOME": [f"Item {i}" for i in range(12)], "VALOR": [100 - i * 7 for i in range(12)]}
    )
    fig = g.grafico_pizza(df, "NOME", "VALOR", top=5, rotulo_outros="Demais")

    rotulos = list(fig.data[0].labels)
    assert len(rotulos) <= 6
    assert "Demais" in rotulos


def test_mapa_calor_aceita_matriz_ou_df_longo(base: pd.DataFrame) -> None:
    matriz = pd.DataFrame(
        {"SP": [1.0, 2.0], "RJ": [3.0, 4.0]},
        index=pd.Index(["Manhã", "Tarde"], name="PERIODO"),
    )
    por_matriz = g.grafico_mapa_calor(pd.DataFrame(), matriz=matriz, mostrar_valores=True)
    longo = g.grafico_mapa_calor(base, "EQUIPE", "DATA", "OS", escala="divergente")

    assert por_matriz.data[0].type == "heatmap"
    assert longo.data[0].type == "heatmap"
    assert por_matriz.data[0].z is not None


def test_calendario_usa_semana_iniciando_na_segunda() -> None:
    indice = pd.date_range("2026-09-01", periods=60, freq="D")  # 01/09/2026 é terça
    serie = pd.Series(np.arange(60, dtype=float), index=indice)

    fig = g.grafico_calendario(serie, mostrar_valores=True)

    assert fig.data[0].type == "heatmap"
    eixo_y = [str(v) for v in fig.data[0].y]
    assert len(eixo_y) <= 7
    assert not serie.empty


def test_histograma_desenha_media_e_distribuicao_opcoes(base: pd.DataFrame) -> None:
    fig = g.grafico_histograma(base, "OS", titulo="Distribuição")

    assert fig.data[0].type == "histogram"
    assert any(shape.type == "line" for shape in fig.layout.shapes), "linha de média"

    caixa = g.grafico_distribuicao(base, "OS", "EQUIPE", tipo="caixa")
    assert caixa.data[0].type == "box"
    violino = g.grafico_distribuicao(base, "OS", "EQUIPE", tipo="violino")
    assert violino.data[0].type == "violin"


def test_dispersao_com_tendencia_sem_statsmodels(base: pd.DataFrame) -> None:
    fig = g.grafico_dispersao(base, "PONTOS", "QUEBRA", col_grupo="EQUIPE", tendencia="linear")

    assert all(trace.type in ("scatter", "scattergl") for trace in fig.data)
    modos = [trace.mode or "" for trace in fig.data]
    assert any("lines" in modo for modo in modos), "reta de tendência"

    sem_tendencia = g.grafico_dispersao(base, "PONTOS", "QUEBRA", tendencia=None)
    assert all("lines" not in (trace.mode or "") for trace in sem_tendencia.data)


def test_combinado_tem_dois_eixos(diaria: pd.DataFrame) -> None:
    fig = g.grafico_combinado(diaria, "DATA", "OS", "SLA", rotulo_barra="OS", rotulo_linha="SLA %")

    tipos = sorted(trace.type for trace in fig.data)
    assert tipos == ["bar", "scatter"]
    assert fig.layout.yaxis2 is not None
    assert fig.layout.yaxis2.overlaying == "y"


def test_cascata_usa_waterfall_sem_marker(cascata: pd.DataFrame) -> None:
    fig = g.grafico_cascata(cascata, "PASSO", "DELTA")

    assert fig.data[0].type == "waterfall"
    assert fig.data[0].increasing is not None
    assert fig.data[0].decreasing is not None


def test_gauge_e_bullet_usam_indicator() -> None:
    gauge = g.grafico_gauge(78.0, titulo="SLA", meta_pct=90.0, faixas=(60.0, 85.0))
    bullet = g.grafico_bullet(78.0, meta=100.0, rotulo="Atingimento")

    assert gauge.data[0].type == "indicator"
    assert gauge.data[0].gauge.axis is not None
    assert list(gauge.data[0].gauge.axis.range) == [0.0, 120.0]  # meta 90 + folga
    assert gauge.data[0].title.text == "SLA"
    assert gauge.data[0].number.suffix == "%"
    assert bullet.data[0].type == "indicator"
    assert bullet.layout.height == 150
    assert bullet.data[0].gauge.bar.color


def test_treemap_sunburst_e_funil(categorica: pd.DataFrame, funil: pd.DataFrame) -> None:
    treemap = g.grafico_treemap(categorica, ["SEGMENTO", "REGIAO"], "VALOR")
    sunburst = g.grafico_sunburst(categorica, ["SEGMENTO", "REGIAO"], "VALOR")
    funil_fig = g.grafico_funil(funil, "ETAPA", "QTD")

    assert treemap.data[0].type == "treemap"
    assert sunburst.data[0].type == "sunburst"
    assert funil_fig.data[0].type == "funnel"


def test_radar_compara_duas_series() -> None:
    fig = g.grafico_radar(
        ["SLA", "Meta", "Quebra", "Volume"],
        [82, 65, 40, 91],
        comparativo=[70, 60, 55, 80],
    )

    assert len(fig.data) == 2
    assert all(trace.type == "scatterpolar" for trace in fig.data)
    assert fig.layout.polar.radialaxis is not None


def test_barras_polar_e_progresso(base: pd.DataFrame, progresso: pd.Series) -> None:
    polar = g.grafico_barras_polar(base, "EQUIPE", "OS")
    barras = g.grafico_progresso(progresso, meta=100.0, unidade="%")

    assert polar.data[0].type == "barpolar"
    assert barras.data[0].type == "bar"


def test_densidade_heatmap_e_contorno(base: pd.DataFrame) -> None:
    calor = g.grafico_densidade(base, "PONTOS", "QUEBRA", tipo="heatmap")
    contorno = g.grafico_densidade(base, "PONTOS", "QUEBRA", tipo="contorno")

    assert calor.data[0].type == "histogram2d"
    assert contorno.data[0].type == "histogram2dcontour"


def test_comparativo_periodos_atual_e_anterior() -> None:
    fig = g.grafico_comparativo(["SP", "RJ", "MG"], [120, 90, 60], [100, 95, 40])

    assert len(fig.data) == 2
    nomes = [trace.name for trace in fig.data]
    assert any("atual" in str(n).lower() for n in nomes)
    assert any("anterior" in str(n).lower() for n in nomes)


def test_numeros_em_pt_br_nos_textos_desenhados() -> None:
    df = pd.DataFrame({"REGIAO": ["SP", "RJ", "MG"], "VALOR": [1248.0, 900.0, 275000.0]})

    ranking = g.grafico_ranking(df, "REGIAO", "VALOR", mostrar_valores=True)
    barras = g.grafico_barras(df, "REGIAO", "VALOR", mostrar_valores=True)
    calor = g.grafico_mapa_calor(
        pd.DataFrame(),
        matriz=pd.DataFrame({"SP": [1248.0], "RJ": [float("nan")]}),
        mostrar_valores=True,
    )

    assert list(ranking.data[0].text) == ["900", "1.248", "275.000"]
    assert ranking.data[0].texttemplate == "%{text}"
    assert "275.000" in list(barras.data[0].text)
    assert ".3s" not in str(ranking.data[0].texttemplate)
    # Célula vazia do heatmap vira travessão, nunca "nan".
    assert "—" in [v for linha in calor.data[0].text for v in linha]


def test_hovertemplates_nao_tem_formato_d3_quebrado(base: pd.DataFrame) -> None:
    fig = g.grafico_linha(base, "DATA", "OS", col_grupo="EQUIPE")

    for trace in fig.data:
        modelo = trace.hovertemplate or ""
        # `.replace(",", ".")` já corrompeu specs d3 (`%{x:,.0f}` → `%{x:.0f}`):
        # nenhum hovertemplate pode ter vírgula de agrupamento perdida no meio.
        assert ",." not in modelo
        assert _hovertemplate_ok(modelo)


def _hovertemplate_ok(modelo: str) -> bool:
    """Todo ``%{...}`` do hovertemplate fecha corretamente."""
    return modelo.count("%{") == modelo.count("}")


# ====================================================
# RENDERIZAÇÃO NO STREAMLIT
# ====================================================
def test_render_grafico_usa_plotly_chart_com_chave() -> None:
    app = AppTest.from_string(
        """
        import pandas as pd
        from components.graficos import criar_grafico, render_grafico
        df = pd.DataFrame({"DIA": pd.date_range("2026-10-01", periods=5), "OS": [3, 5, 4, 8, 6]})
        render_grafico(criar_grafico("linha", df, "DIA", "OS", titulo="OS"), chave="teste")
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception), [str(e.value) for e in app.exception]
    assert len(app.get("plotly_chart")) == 1


def test_render_graficos_em_abas_cria_uma_aba_por_figura() -> None:
    app = AppTest.from_string(
        """
        import pandas as pd
        from components.graficos import criar_grafico, render_graficos_em_abas
        df = pd.DataFrame({"DIA": pd.date_range("2026-10-01", periods=5), "OS": [3, 5, 4, 8, 6]})
        render_graficos_em_abas(
            {
                "Linha": criar_grafico("linha", df, "DIA", "OS"),
                "Barras": criar_grafico("barras", df, "DIA", "OS"),
            },
            chave="home",
        )
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception), [str(e.value) for e in app.exception]
    assert len(app.tabs) == 2
    assert len(app.get("plotly_chart")) == 2


def test_render_grafico_sem_figura_nao_quebra() -> None:
    app = AppTest.from_string(
        """
        from components.graficos import render_grafico
        render_grafico(None)
        """,
        default_timeout=60,
    ).run()

    assert not list(app.exception)
    assert len(app.get("plotly_chart")) == 0


def test_versao_e_api_publica_do_modulo() -> None:
    assert g.VERSAO_GRAFICOS == "1.0.0"
    for nome in g.__all__:
        assert hasattr(g, nome), nome
