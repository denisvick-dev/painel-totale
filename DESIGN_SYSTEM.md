# 🎨 Design System TOTALE — v3.6.0

Guia de uso dos componentes de interface e da camada de desempenho do Painel
TOTALE. Tudo aqui já está instalado e testado; **prefira estas funções a escrever
HTML/CSS/Plotly à mão** — elas mantêm as cores oficiais, a acessibilidade e o
acabamento visual coerentes entre as páginas.

Cores oficiais (únicas permitidas em destaque de marca):

| Token | Hex | Uso |
|-------|-----|-----|
| `Cores.PRIMARIA` / `AZUL_TOTALE` | `#012869` | Títulos, séries principais, botões |
| `Cores.SECUNDARIA` / `LARANJA_TOTALE` | `#F37C04` | Destaques, alertas de atenção, 2ª série |
| `Cores.SUCESSO` | `#047857` | Estado positivo |
| `Cores.ALERTA` | `#B91C1C` | Estado crítico |
| `Cores.BORDA` | `#E6EDF5` | Bordas e grades |

---

## 1. Cartões de KPI — `components/kpi_cards.py`

Substituem o `st.metric` nativo (nenhuma página o usa mais).

```python
from components.kpi_cards import render_metric, render_kpi_row, render_kpi_de_serie

# Drop-in replacement de st.metric (mesma posição dos argumentos)
render_metric("OS concluídas", "1.248", delta="+8,4%", delta_color="normal",
              tema="azul", icone="verified", ajuda="Total no período")

# Linha de cartões declarativa (padrão das páginas)
render_kpi_row([
    {"label": "OS abertas", "valor": "1.248", "sub": "set/2026", "tema": "azul",
     "icone": "assignment", "ajuda": "Somente produção"},
    {"label": "SLA", "valor": "92,4%", "delta": 3.1, "tema": "verde",
     "progresso": (92.4, 95.0), "sparkline": serie_diaria},
], colunas=2)

# Cartão derivado de uma série (calcula último valor, variação e sparkline)
render_kpi_de_serie(label="Volume diário", serie=serie, unidade=" OS", inverso=False)
```

Temas: `azul`, `laranja`, `verde`, `vermelho`, `cinza`, `gradiente`.
Densidades (`tamanho`): `compacto`, `padrao`, `destaque`.
Funções puras (testáveis sem runtime): `calcular_variacao_pct`, `direcao_delta`,
`rotulo_tendencia`, `resumo_de_serie`, `sparkline_svg`, `css_kpi_avancado`.

> `components/dashboard_kit.py` reexporta a mesma matemática de delta — a fonte
> única é `kpi_cards.py`.

---

## 2. Gráficos — `components/graficos.py`

24 tipos prontos, tema minimalista `totale_min` aplicado automaticamente
(colorway liderado por `#012869` e `#F37C04`, fundo transparente, legenda
horizontal abaixo do gráfico, grade apenas no eixo Y).

```python
from components.graficos import criar_grafico, render_grafico, render_graficos_em_abas

fig = criar_grafico("linha", df, "DATA", "OS", col_grupo="EQUIPE",
                    titulo="Evolução diária", altura=380)
render_grafico(fig, chave="home_evolucao")

# Vários recortes do mesmo dado em abas
render_graficos_em_abas(
    {"Volume": fig_volume, "SLA": fig_sla, "Quebra": fig_quebra},
    chave="cockpit",
)
```

Tipos: `linha, area, barras, ranking, pizza, donut, dispersao, histograma, caixa,
violino, calor, calendario, treemap, sunburst, funil, radar, cascata, bullet,
gauge, polar, densidade, combinado, progresso, comparativo` (sinônimos aceitos:
`pie`, `box`, `heatmap`, `waterfall`, `colunas`, …).

Regras do módulo:

- `criar_grafico` **nunca levanta exceção**: dado vazio, coluna ausente ou tipo
  inválido devolvem `figura_vazia` com a explicação desenhada no gráfico. Um
  painel nunca cai por causa de um recorte sem dados.
- `col_grupo` separa a série em vários traços (paleta categórica); `cor` define a
  cor única (hex) quando não há agrupamento — padrão azul oficial.
- Rótulos de valor desenhados pelo Python saem em **pt-BR** (`1.248`, `275.000`);
  `hovertemplate` usa formatação d3 (nunca aplique `.replace(",", ".")` neles).
- `render_grafico` já usa `width="stretch"` e normaliza `ao_selecionar`
  (`noop` → `ignore`); `use_container_width` está proibido no repositório.

---

## 3. CSS global — `components/css_global.py`

Padroniza os componentes **nativos** do Streamlit (botões, inputs, selects, abas,
tabelas, alertas, upload, progresso, tooltips, diálogos).

```python
from components.css_global import injetar_css_global
injetar_css_global()          # chamado uma única vez por sessão
```

- Idempotente: a 1ª chamada injeta (~31 KB), as seguintes devolvem `None`
  — o CSS fica em `<style id="totale-css-global-v1">` no `head`, com fallback
  inline. Isso remove ~40 KB de payload por *rerun*.
- `aplicar_estilo()` (Design System) já chama a injeção; páginas não precisam
  repetir.
- **Não toca na sidebar** — os temas Claro/Azul/Laranja continuam em
  `components/sidebar.py`.
- Seletores usam `data-testid` reais do Streamlit 1.65; o teste
  `tests/test_css_global.py` falha se algum nome deixar de existir (CSS morto).

---

## 4. Organização da página — `components/layout_pagina.py`

Ordem canônica (`ORDEM_PADRAO`), usada como referência em `pages/home.py`:

1. Cabeçalho e contexto · 2. Sumário (âncoras) · 3. Filtros · 4. KPIs ·
5. Gráficos principais · 6. Detalhamento (abas/expansores) · 7. Exportação ·
8. Rodapé

```python
from components.layout_pagina import (
    barra_filtros, painel, render_barra_acoes, render_cabecalho_pagina,
    render_chips, render_rodape_pagina, render_sumario, secao,
)

render_cabecalho_pagina("Volumetria", subtitulo="Produção por equipe",
                        badge="PRODUÇÃO", chips=[("Atualizado", "13/10 08:00")])
render_sumario(["Filtros", "KPIs", "Gráficos"])     # âncoras clicáveis

with barra_filtros("volumetria", colunas=3) as (c1, c2, c3):   # barra fixa no topo
    base = c1.selectbox("Base", opcoes)
    inicio = c2.date_input("Início", value=hoje)
    status = c3.multiselect("Status", opcoes)

with secao("KPIs", icone="monitoring", subtitulo="Recorte atual"):
    render_kpi_row(specs, colunas=4)

with painel("Saída do robô", altura=260):           # altura controlada, com scroll
    st.dataframe(df, width="stretch")

with render_barra_acoes():
    st.download_button("Exportar CSV", dados, "producao.csv")

render_rodape_pagina(versao="3.6.0", ambiente="produção")
```

Detalhes que evitam bugs:

- `st.container(...)` **não** pode ser usado como `with st.container(...) as alvo:`
  no Streamlit 1.65 (o valor é `None`). Os primitivos devolvem o contêiner e o
  guarda `tests/test_layout_pagina.py` impede o padrão antigo.
- `barra_filtros(fixa=True)` cria a chave `totale_filtros_<slug>`, casando com o
  seletor *sticky* do CSS; `fixa=False` usa `totale_barra_<slug>`.
- Âncoras: `totale-secao-<slug>` (slug sem acento, estável).

---

## 5. Esqueleto dos dashboards — `components/dashboards.py`

Camada fina sobre `layout_pagina` que garante que **todo painel abra, organize e
feche do mesmo jeito**. É o padrão exigido pelo guarda
`tests/test_organizacao_dashboards.py` para as páginas de
`DASHBOARDS_PADRONIZADOS` (`config/navegacao.py`).

```python
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.layout_pagina import cabecalho_secao, secao

SECOES_PAGINA = ("Filtros", "Indicadores", "Detalhamento", "Exportação")

abrir_dashboard(
    "Volumetria | TOTALE",
    secoes=SECOES_PAGINA,              # gera o sumário de âncoras
    chips={"Período": "01/10 a 15/10", "Registros": len(df)},
    registros=len(df),
    hero=render_hero_totale_1,         # opcional; sem hero usa o cabeçalho padrão
)

cabecalho_secao("Indicadores", icone="insights", subtitulo="Recorte atual")
with secao("Detalhamento", icone="table"):
    st.dataframe(df, width="stretch")

secao_exportacao(                      # Excel + CSV com nome/carimbo padronizados
    df, nome_arquivo="volumetria", chave="volumetria",
    rotulo_secao="Baixar resultado",
)
fechar_dashboard()                     # rodapé com versão e ambiente
```

Detalhes:

- `abrir_dashboard` aceita `chips` como `dict` ou sequência de pares e devolve os
  chips exibidos (útil em testes e diagnósticos).
- `cabecalho_secao(..., ancora=False)` para seções internas de abas/expansores,
  que não entram no sumário.
- `secao_exportacao` usa `services.planilhas` (aba, autofiltro, larguras e nome
  com carimbo de data) — nunca monte o `download_button` à mão.
- Caminhos de saída antecipada (`return`, página sem base) devem chamar
  `fechar_dashboard()` para o rodapé não sumir.

---

## 6. Camada de dados compartilhada — `services/`

Sem UI: só leitura, normalização e exportação. Regra de ouro — **página não
reimplementa helper que já existe aqui** (o guarda lista os nomes proibidos).

| Módulo | O que oferece |
|--------|---------------|
| `services/texto.py` | `normalizar_texto`, `sem_acento`, `limpar_nome_coluna`, `normalizar_login`, `buscar_coluna`, `formatar_numero/_pt_br/_inteiro/_percentual` |
| `services/planilhas.py` | `ler_upload`, `ler_bytes`, `gerar_excel`, `gerar_excel_multiabas`, `gerar_csv`, `botao_download_planilha/_csv`, `nome_com_carimbo` |
| `services/hierarquia.py` | `hierarquia_da_sessao()` → colunas canônicas `LOGIN`/`TÉCNICO`/`MONITOR`/`BASE`, com cache e degradação graciosa offline |
| `services/dados_sessao.py` | chaves `CHAVE_PRODUCAO`/`CHAVE_CONSULTIVO`/`CHAVE_MEMORIA`/`CHAVE_ATUALIZACAO`, `obter_dataframe`, `obter_base`, `exigir_base`, `resumir_carga`, `concatenar_abas` |
| `services/google_drive_client.py` | `carregar_planilha_gsheets_csv`, `baixar_arquivo_drive`, `criar_sessao_http` |

```python
from services.dados_sessao import CHAVE_MEMORIA, exigir_base, obter_dataframe
from services.planilhas import gerar_excel, ler_bytes
from services.texto import formatar_inteiro, normalizar_texto

df = exigir_base(CHAVE_MEMORIA, titulo="Volumetria")   # ou obter_dataframe(...)
planilha = gerar_excel(df, aba="Base", autofiltro=True)
```

Quando a página precisa de um detalhe que o serviço não cobre (outra opção de
`to_excel`, por exemplo), use `functools.partial` em vez de reescrever a função:

```python
gerar_excel = partial(gerar_excel_padrao, autofiltro=True)
```

---

## 7. Desempenho de dados — `services/cache_dados.py`

```python
from services.cache_dados import (
    EspecificacaoFonte, carregar_varias, otimizar_dtypes, render_painel_desempenho,
    temporizar,
)

fontes = [
    EspecificacaoFonte(chave="producao", url=url_producao, ttl=300, otimizar=True),
    EspecificacaoFonte(chave="consultivo", url=url_consultivo, ttl=300),
    EspecificacaoFonte(chave="ativos", produtor=carregar_ativos_local),
]
with temporizar("sincronizacao"):
    resultados = carregar_varias(fontes, max_workers=4)   # downloads em paralelo

for nome, r in resultados.items():
    if r.ok:
        df = r.df            # r.origem: rede | cache | cache_validado | produtor
render_painel_desempenho(resultados=resultados)
```

Como a velocidade é obtida:

| Técnica | Efeito |
|---------|--------|
| Requisição condicional (`ETag` / `If-Modified-Since`) | `304` → sem download nem reparse; origem `cache_validado` |
| Cache Parquet em disco (`$TOTALE_CACHE_DIR`, padrão `tempdir`) | Relê em ~40 ms o que levava ~280 ms em CSV; fora do repositório |
| Sessão HTTP com pool + retry | Reuso de conexão e tolerância a falhas transitórias |
| `carregar_varias(max_workers=4)` | Fontes baixadas em paralelo (0,9 s → 0,31 s medidos) |
| `ler_csv_rapido` (engine C + detecção de separador/encoding) | Sem custo de inferência de tipos |
| `otimizar_dtypes(numericas=True, categoricas=True)` | −81% de memória no caso medido |
| Normalização vetorial no robô (`robo.py`) | 1,03 s → 0,22 s em 120 mil linhas |
| `datas_normalizadas` / `agregar_com_cache` (memoizadas por conteúdo) | Reexecuções não reparsam nem reagregam |
| CSS injetado uma vez por sessão | ~40 KB a menos por *rerun* |

Regras:

- O cache grava os dtypes no sidecar e os restaura na leitura — a 1ª carga
  (rede) e as seguintes (cache) devolvem **o mesmo DataFrame**.
- Falha com cache antigo disponível → devolve o cache com `erro` preenchido
  (degradação graciosa) em vez de derrubar a página.
- Proibido `st.cache_data.clear()` / `st.cache_resource.clear()` em `pages/`
  (guarda em `tests/test_refatoracao_arquitetura.py`); use `limpar_cache(chave)`.

---

## 8. Checklist para nova página

1. `abrir_dashboard(...)` com `secoes` (ou `render_cabecalho_pagina` +
   `render_sumario` quando a página não é um dashboard padronizado).
2. `barra_filtros` para o recorte (fixa no topo).
3. `render_kpi_row` para os números — nunca `st.metric`.
4. `criar_grafico`/`render_grafico` para os gráficos — nunca `px.*` direto.
5. `secao`/`cabecalho_secao`/`painel` para agrupar, na ordem `ORDEM_PADRAO`.
6. `secao_exportacao` para a saída de dados (ou `render_barra_acoes` em ações mistas).
7. `fechar_dashboard()` com versão e ambiente — inclusive nas saídas antecipadas.
8. Dados por `services/` (`exigir_base`, `ler_bytes`, `hierarquia_da_sessao`) e
   `carregar_varias`/`render_painel_desempenho` para fontes externas.
9. Página nova entra em `config/navegacao.py` (grupo, ícone e ordem da sidebar).
10. `ruff check .` e `pytest -q tests/` verdes antes do push.

Testes que protegem este contrato: `test_kpi_cards.py`, `test_graficos.py`,
`test_css_global.py`, `test_layout_pagina.py`, `test_cache_dados.py`,
`test_dashboard_kit.py`, `test_sem_depreciados.py`, `test_higiene_repositorio.py`,
`test_organizacao_dashboards.py` e `test_dashboards_compartilhados.py`.
