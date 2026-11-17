# 📊 Painel TOTALE — Proposta de dashboards e melhorias

> **Documento de proposta.** Não altera comportamento do portal; serve para priorizar o
> próximo ciclo com a diretoria, a operação e o time técnico.
>
> **Base analisada:** branch `arena/1d72b44d-painel-totale`, commit `f790d8b` (17/11/2026).
> **Escopo:** código-fonte do repositório. Nenhuma planilha de produção foi lida nesta
> análise — a viabilidade de cada proposta foi inferida das colunas, abas e módulos já
> consumidos pelo app. Onde a viabilidade depende de um dado que o código não comprova,
> o item está marcado como **“validar com dados reais”**.

---

## 1. Sumário executivo

O portal já resolveu o problema de **existir**: são 19 páginas, 6 áreas de navegação,
camada de design system, fábrica de gráficos, exportação corporativa, cache HTTP/Parquet
e 35 arquivos de teste. O próximo salto não é “mais um painel”, e sim **confiança,
integração e decisão**:

| # | Achado do diagnóstico | Consequência prática |
|---|------------------------|----------------------|
| 1 | O portal não tem login; autenticação existe só dentro de `pages/gestao_ativos.py` | Qualquer pessoa com a URL vê produção, nomes, logins e ausências. O README lista autenticação, perfis e auditoria como funcionalidades; a seção de organização esclarece depois que a autenticação é só da Gestão de Ativos. |
| 2 | Cada dashboard olha uma fonte; nada cruza produção × presença × indicadores × quebra | Perguntas de gestão (“quantas O.S. perdemos por falta?”, “quem precisa de apoio?”) exigem juntar planilhas à mão. |
| 3 | O histórico é gravado (`Historico_OS`, `Historico_Equipe`, `Previas_Diarias`), mas quase não é lido | Não há tendência, sazonalidade nem projeção de médio prazo — só foto do dia/mês. |
| 4 | Os painéis são reativos: ninguém é avisado quando meta, SLA ou frescor quebra | O desvio é descoberto na reunião, não quando acontece. |
| 5 | Regra de negócio e metas vivem dentro de páginas de 2.000+ linhas, em cinco pontos do código, sem vigência | Cada mudança de meta exige caça ao hardcode; testes cobrem serviços, não a regra da página. |
| 6 | `requirements.txt` não instala tudo o que o app importa; CI instala só as dependências de teste | Um `pip install -r requirements.txt` deixa Rota Inicial e Quebra por Segmento quebradas — e o CI não percebe. |

**As cinco apostas recomendadas para os próximos 90 dias**

1. **Fechar a porta (P0):** login único + perfis por base + política de dados sensíveis.
2. **Tornar o dado confiável (P0/P1):** contrato de colunas, SLO de frescor visível em
   todas as páginas e reconciliação entre fontes.
3. **Uma tela para decidir (P1):** *Sala de Situação* consolidando dia, fechamento,
   quebra, presença e saúde das fontes.
4. **Cruzar o que hoje vive separado (P1):** *Produtividade × Disponibilidade* e
   *Scorecard 360* por equipe.
5. **Transformar histórico em tendência (P1):** data mart em DuckDB/Parquet e a página
   *Tendências & Sazonalidade*, que destrava metas e dimensionamento.

O restante do documento detalha **10 dashboards** e **39 melhorias** com evidência no
código, esforço, impacto, riscos e critérios de aceite, além de roadmap e receitas de
implementação.

---

## 2. Como o diagnóstico foi feito

- Leitura do entrypoint (`streamlit_app.py`), da navegação declarativa
  (`config/navegacao.py`), das 19 páginas de `pages/`, dos 19 módulos de
  `services/` e dos 14 componentes de `components/`.
- Inspeção das abas e colunas realmente consumidas: `Prod`, `lista_ativos`,
  `controle_absenteismo`, `Historico_OS`, `Historico_Consultivo`, `Config_Equipe`,
  `Historico_Equipe`, `Previas_Diarias`, indicadores do Drive e bases de quebra/retorno.
- Verificação de dependências por AST (imports de topo) contra `requirements.txt`,
  `requirements-test.txt` e o workflow `.github/workflows/quality.yml`.
- Leitura dos guards existentes (`tests/test_organizacao_dashboards.py`,
  `tests/test_sintaxe.py`, `tests/test_higiene_repositorio.py`) para que as propostas
  nasçam compatíveis com o padrão v3.7.0 já cobrado em CI.

**Fora de escopo:** redesenho da marca, troca do Google Sheets como fonte de entrada,
contratação de ferramenta de BI e qualquer decisão sobre dados pessoais que não seja
estritamente necessária para operar o painel.

---

## 3. O que já existe (e deve ser reaproveitado)

### 3.1 Mapa atual do portal

| Área | Páginas | Fonte principal | Pergunta que responde hoje |
|------|---------|-----------------|----------------------------|
| Visão Geral | Home, Visão Geral, Atualização de Dados | sessão + status de sync | “O portal está carregado? Onde fica cada painel?” |
| Central de Performance | Produção Mensal, Quantidade de O.S., Consultivos, Metas Operacionais, Indicadores, Prévia Diária, Lista de Presença | `Prod`, Drive de consultivos, indicadores, planilha da prévia, `controle_absenteismo` | “Produzimos o quê, contra qual meta, com quem?” |
| Rotas & Campo | Rota Inicial, Rota Geral, Volumetria, Retornos, 1º Atendimento | uploads ABCDM/Guarulhos/Leste, `lista_ativos`, TOA × Sinapse | “Como a carga se distribui e o que acontece na rua?” |
| SLA & Quebra | Quebra Geral, Quebra por Segmento | base de quebra (status, tipo de serviço, motivo de baixa, cidade) | “Quanta quebra tivemos e por qual motivo?” |
| Cadastros & Disparos | Gestão de Ativos | `lista_ativos` | “Quem está ativo, em qual base e sob qual monitor?” |
| Utilitários | Assinatura de E-mail | — | “Padronizar a assinatura corporativa.” |

### 3.2 Ativos técnicos que reduzem o custo de qualquer nova página

| Ativo | O que entrega | Onde |
|-------|---------------|------|
| Esqueleto de dashboard | `abrir_dashboard` → chips → sumário → `secao()` → exportação → rodapé | `components/dashboards.py`, `components/layout_pagina.py` |
| Cartões de KPI | Variação D-1/W-1, sparkline SVG, progresso vs meta, ícone, 6 temas | `components/kpi_cards.py` |
| Fábrica de gráficos | 24 tipos sobre Plotly com tema `totale_min` e paleta oficial | `components/graficos.py` |
| Contrato de leitura | `exigir_base`, `obter_dataframe`, `resumir_carga` para DataFrame ou dict de abas | `services/dados_sessao.py` |
| Carga performática | HTTP com pool, `304`, Parquet em disco, download paralelo, downcast | `services.cache_dados.py` |
| Exportação | XLSX corporativo, CSV pt-BR, multiabas, botões padronizados | `services/planilhas.py` |
| Hierarquia | Base → monitor → técnico a partir da lista de ativos | `services/hierarquia.py` |
| Datas | Parsing ISO/BR sem inversão e janela temporal consistente | `services/datas.py` |
| Saúde de dados | Frescor e consistência estrutural | `components/saude_dados.py` |
| Padrão cobrado em teste | Toda página nova precisa entrar na navegação e no esqueleto | `tests/test_organizacao_dashboards.py` |

### 3.3 Números que ajudam a dimensionar o esforço

- ~52 mil linhas de Python; 19 páginas; 19 serviços; 14 componentes; 35 arquivos de teste.
- Seis páginas concentram o risco de manutenção: `indicadores.py` (2.520 linhas),
  `rota_inicial.py` (2.354), `dashboard_meta.py` (2.307), `quebra_unificada.py` (2.030),
  `volumetria.py` (1.794), `quebra_geral.py` (1.792).
- `pages/quebra_unificada.py` importa `pages.quebra_geral` (linha 73) — uma página depende
  do código de outra, não de um serviço.

---

## 4. Lacunas observadas (com evidência no código)

### 4.1 Acesso, privacidade e governança

| Lacuna | Evidência | Risco |
|--------|-----------|-------|
| Sem autenticação no portal | `streamlit_app.py` registra páginas e renderiza a sidebar sem gate; o único login do repositório está em `pages/gestao_ativos.py:705` (`tela_login`) | Acesso irrestrito a dados de produção, nomes, logins e ausências |
| Perfis e filtro por base não existem no entrypoint | `.streamlit/secrets.example.toml` declara `[usuarios.admin]` com `role` e `bases`, mas só a Gestão de Ativos consome | O README descreve “perfis de acesso” e “filtros por base conforme permissão”; no portal, nenhum dos dois é aplicado |
| Dados sensíveis expostos sem camada de proteção | `services/absenteismo.py:73-87` grava `Tipo` (Atestado, Afastamento), `Justificativa` e `Motivo` no `controle_absenteismo`; exportações CSV/XLSX existem em várias páginas | Dado de saúde (LGPD art. 5º, II) em tela e em planilha baixada, sem trilha de acesso |
| Auditoria só onde há escrita | `gestao_ativos` e o fluxo de presença auditam a alteração; leitura, filtro e download não são registrados | Impossível responder “quem exportou a lista de atestados?” |
| Demo pública anunciada no README | Link `painel-totale.streamlit.app` | Se a demo usa base real, o risco acima é externo e imediato |

### 4.2 Dados e confiabilidade

| Lacuna | Evidência | Consequência |
|--------|-----------|--------------|
| Não há contrato de colunas por fonte | Cada página procura colunas por sinônimos (ex.: `buscar_coluna(...)`) e segue com aviso | Coluna renomeada na planilha gera número zerado em uma página e erro em outra |
| Frescor não tem meta | `components/saude_dados.avaliar_frescor` usa 15/60 min genéricos; não há SLO por fonte | Ninguém sabe se “Produção” de hoje está atualizada ou parada desde ontem |
| Fontes não são reconciliadas | Produção, consultivos e prévia são carregadas em fluxos distintos | Divergência entre painéis mina a confiança na reunião |
| Hierarquia é sempre “a foto de agora” | `services/hierarquia.py` deriva base/monitor da `lista_ativos` atual | Ao mudar alguém de base, o histórico passa a ser lido com a estrutura nova |
| Metas e limiares espalhados pelo código | `config/metas_operacionais.py`; `dashboard_meta.py:335-336`; `qtde_os.py:136-162`; `indicadores.py:76-83`; `quebra_geral.py:121-122` | Mudar meta exige alterar código em cinco pontos; não se audita “qual meta valia em março” |
| Sem camada analítica | `duckdb` está em `requirements.txt`, mas não é importado em lugar algum | Histórico longo e joins continuam caros, dentro do processo do Streamlit |

### 4.3 Produto e experiência

| Lacuna | Evidência | Consequência |
|--------|-----------|--------------|
| Sem tendência consolidada | O histórico é gravado (`pages/previa_totale.py:72-120`), mas as páginas mostram, no máximo, o mês corrente | Decisão olha o dia, não a curva |
| Sem alerta proativo | Todo o portal é leitura sob demanda | Desvio de meta/SLA é descoberto tarde |
| Exportação executiva em PDF só em um painel | `reportlab` aparece apenas em `pages/quebra_unificada.py` | Reunião de diretoria junta prints de telas |
| Sem link profundo (salvo exceção) | `st.query_params` só em `dashboard_meta.py:1352-1359` | Não se compartilha “a visão de Guarulhos de ontem” |
| Sem dicionário único de métricas | `GLOSSARIO` e `NOMES_AMIGAVEIS` só em `indicadores.py` | “Quebra”, “retorno”, “pontos” e “montados” variam de significado entre áreas |
| Tabelas truncam sem avisar | `render_table_html` usa `max_rows=100` por padrão (`components/componentes.py:1772`) | O leitor acredita que viu a lista completa |
| Mobile tratado pontualmente | `@media` só em alguns componentes (`componentes.py:832`, `kpi_cards.py:784`, `css_paginas.py:509`) | Tabelas e grades de 6 KPIs quebram no celular do supervisor |

### 4.4 Engenharia e operação

| Lacuna | Evidência | Consequência |
|--------|-----------|--------------|
| Dependências incompletas e não fixadas | `folium`, `geobr`, `geopandas`, `streamlit_folium`, `reportlab`, `xlsxwriter`, `holidays`, `gdown`, `streamlit_autorefresh` e `extract_msg` são importados, mas **não** estão em `requirements.txt` | Instalação “limpa” quebra Rota Inicial e Quebra por Segmento |
| Dependências não usadas | `duckdb`, `sqlglot`, `sql_metadata`, `gspread-pandas` e `matplotlib` não aparecem em imports | Instalação mais lenta, superfície de ataque maior |
| CI não valida a instalação real | `.github/workflows/quality.yml` instala apenas `requirements-test.txt` | O erro acima passa verde |
| Páginas monolíticas e acopladas | `quebra_unificada` importa `pages.quebra_geral`; `dashboard_meta` baixa produção por conta própria (`@st.cache_data` em 631-760) | Regra testável só via página; correção em um painel pode quebrar outro |
| Versão divergente | `config/settings.py` declara 3.7.0; README e `docs/DESIGN_SYSTEM.md` falam em 3.6.0; não há `CHANGELOG.md` | Dúvida sobre o que está em produção |
| Sem telemetria de uso | Nenhum registro de abertura/exportação | Priorização de dashboards é opinativa |

---

# Parte I — Sugestões de dashboards

Dez propostas, organizadas da decisão diária ao planejamento. Todas foram desenhadas para reusar
`components/dashboards.py`, `components/kpi_cards.py`, `components/graficos.py` e a camada
de `services/`. Esforço estimado para **1 desenvolvedor já familiarizado** com o portal:

- **P** ≤ 3 dias · **M** 4–10 dias · **G** > 10 dias (inclui validação com a área).

## D1. Sala de Situação TOTALE (cockpit diário) — *recomendado para a Onda 1*

**Pergunta:** “Como está o dia e o fechamento do mês, em uma tela, em dois minutos?”
**Para quem:** diretoria, gerência e sala de operações (modo TV).

**Fontes (já existem):** `Previas_Diarias` e `Historico_OS` (planilha da prévia),
`Historico_Equipe`, `controle_absenteismo`, base de produção da sessão e status das fontes
(`services/dados_sessao` + `components/saude_dados`).

**KPIs:** O.S. do dia vs meta diária; projeção de fechamento vs meta mensal; quebra do dia
vs SLA (20% geral, 25% migração); técnicos disponíveis (montados − ausências); consultivos
do dia; fontes dentro do SLO.

**Visualizações:** 6 cartões avançados com sparkline de 14 dias e progresso contra meta;
*gauge* “Projeção × Meta”; linha de 30 dias com faixa de meta; barras por base; calendário
de quebra.

**O que muda:** hoje a mesma leitura exige abrir Prévia Diária, Metas, Produção, Quebra e
Lista de Presença — e a prévia depende de upload manual. O cockpit lê o histórico já
gravado e mostra **o que mudou desde ontem**.

**Esforço:** M (5–8 dias) · **Impacto:** 5/5 · **Confiança:** 4/5.
**Depende de:** login (A1) e SLO de frescor (B2); dados de `Previas_Diarias` completos para
o período exibido.
**Aceite:** abre em menos de 3 s com cache quente; todo número tem fonte e horário; um
clique leva ao painel de detalhe correspondente; funciona em 1366×768 sem rolagem
horizontal.

---

## D2. Torre de Controle de Quebra (SLA preditivo) — *Onda 2*

**Pergunta:** “Quanta quebra vamos fechar e onde agir primeiro?”
**Para quem:** coordenação de SLA, supervisores, diretoria.

**Fontes:** motor de `pages/quebra_geral.py` (`MOTIVO DE BAIXA`, `TIPO_SERVICO`, `CIDADE`,
status, datas), `Historico_OS` e, opcionalmente, presença para explicar picos.

**Métricas:** taxa de quebra geral e por segmento vs meta; projeção de fechamento do mês;
Pareto de motivos (80/20); quebra por cidade; reincidência por contrato; “quebra evitável”
(motivos mapeados para ação, com a mesma tabela de ações que já existe em
`SEGMENTOS_CONFIG`).

**Visualizações:** linha com projeção e faixa de meta; ranking Pareto com acumulado;
treemap motivo → cidade; heatmap cidade × motivo; tabela priorizada com volume, impacto
estimado e dono.

**O que muda:** a página atual mostra matriz executiva e análise detalhada, mas **não
projeta fechamento** nem ordena a ação por impacto; as metas ficam em `Config` na página.

**Esforço:** M · **Impacto:** 4/5 · **Confiança:** 4/5.
**Risco:** associação automática “motivo → ação” pode ser simplista; manter a decisão
humana e mostrar a premissa.
**Aceite:** toda taxa exibe numerador e denominador; projeção declara o método e os dias
considerados; filtros por base/período/segmento persistem na URL.

---

## D3. Produtividade × Disponibilidade (eficiência real da equipe) — *Onda 2*

> **Status (17/11/2026): implementado.** Página
> `pages/produtividade_disponibilidade.py`, regra pura em
> `services/produtividade.py` e testes em
> `tests/test_produtividade_disponibilidade.py`. Entregues: dispersão
> absenteísmo × produtividade, ranking de O.S./técnico-dia, barras empilhadas
> por tipo, treemap base → supervisor, donut de composição, combinado semanal e
> calendário diário de ausências. O detalhe é sempre agregado por
> supervisor/base; a página não expõe login, motivo ou atestado individual.

**Pergunta:** “Quanta produção perdemos por ausência e como isso varia por equipe e base?”
**Para quem:** gerência de operações e RH/planejamento.

**Fontes:** produção (`Nome Equipe`, `Pontos`, `O.S.`, `Supervisor`, datas),
`controle_absenteismo` (`Tipo`, `Data Início`, `Data Fim`, `Dias Úteis`, `Monitor`, `Base`)
e `lista_ativos` (headcount).

**Métricas:** O.S. e pontos por técnico-dia disponível; dias perdidos por tipo de ausência;
taxa de absenteísmo; impacto estimado em O.S. (dias perdidos × produtividade média —
premissa explícita, parametrizável); tendência de 8 semanas.

**Visualizações:** dispersão absenteísmo × produtividade (cada ponto = equipe, tamanho =
headcount); barras empilhadas de dias perdidos por tipo; treemap base → monitor; linha
semanal.

**O que muda:** produção e presença são mundos separados hoje; não existe denominador
“técnico-dia disponível” em lugar nenhum.

**Esforço:** M — G (o cruzamento exige chave login/data consistente) · **Impacto:** 4/5 ·
**Confiança:** 3/5.
**Cuidado obrigatório:** atestado e afastamento são dados sensíveis. A visão deve ser
**agregada por equipe/base**; ranking individual de saúde é vedado. Ver A3.
**Aceite:** nenhuma linha individual de saúde em tela ampla; premissas de cálculo visíveis;
exportação agregada por padrão.

---

## D4. Scorecard 360 (qualidade + produtividade por equipe/técnico) — *Onda 1*

**Pergunta:** “Quem precisa de apoio e em qual dimensão?”
**Para quem:** supervisores e coordenação de qualidade.

**Fontes:** as seis abas de indicadores do Drive (`Geoloc_Os`, `OS_Digital`,
`Aderencia_Ura`, `Nr35`, `Tec1`, `Baixa_Pda`) já mapeadas em
`pages/indicadores.py:76-83`; produção; quebra; retorno.

**Métricas:** índice composto 0–100 com pesos configuráveis; cada indicador vs meta
(95%, e 97% em Tec1); produtividade vs meta; taxa de quebra; taxa de retorno; faixas
(exemplar / atenção / crítico); evolução de 6 meses.

**Visualizações:** radar por técnico/equipe; bullet por indicador; heatmap equipe ×
indicador; ranking com faixas; cartão de “plano de ação sugerido”.

**O que muda:** hoje os indicadores estão em abas por login e a produção em outra página;
não há índice integrado nem faixa de priorização.

**Esforço:** M · **Impacto:** 5/5 para supervisores · **Confiança:** 4/5.
**Riscos:** índice composto sem amostra mínima distorce (usar ≥ 20 O.S. para entrar no
ranking); pesos precisam ser públicos e versionados; ranking individual deve respeitar
perfil de acesso.
**Aceite:** pesos e fórmula documentados no próprio painel; “sem amostra” aparece como
estado, não como zero; mesmo login reconciliado entre as seis abas.

---

## D5. Retrabalho e Reincidência (custo da não qualidade) — *Onda 2*

**Pergunta:** “Quanto estamos refazendo e onde o retorno se concentra?”
**Para quem:** qualidade, supervisores, diretoria.

**Fontes:** `pages/retorno.py` (TOA × Sinapse: contrato, técnico dono, monitor),
quebra e primeiro atendimento.

**Métricas:** retornos por 100 O.S.; % de contratos com retorno; reincidência em 7 e 30
dias; concentração top 10 contratos/técnicos; evolução mensal; tempo entre atendimentos.

**Visualizações:** linha/área de tendência; ranking; Pareto de contratos; heatmap
contrato × mês; tabela com “dono do retorno”.

**O que muda:** a página atual audita o dono do retorno, mas não calcula taxa,
reincidência nem série histórica.

**Esforço:** M · **Impacto:** 4/5 · **Confiança:** 3/5 (depende do vínculo contrato ↔
retorno).
**Aceite:** taxa com denominador explícito; reincidência definida por janela; filtro por
supervisor e cidade.

---

## D6. Funil do Atendimento (jornada da O.S.) — *Onda 3*

**Pergunta:** “Onde a O.S. trava: rota, primeiro atendimento, execução ou baixa?”
**Para quem:** operação e planejamento de campo.

**Fontes:** `pages/p_atendimento.py` (início, status, técnico), produção (status do
contrato), quebra e retorno.

**Métricas:** volume por etapa; conversão entre etapas; tempo médio por etapa; pendências
acima de X dias; distribuição do primeiro horário de saída.

**Visualizações:** funil; barras por etapa; caixa (distribuição de tempos); heatmap
hora × dia da semana.

**Esforço:** G — exige chave de ligação contrato + data + login validada com dados reais ·
**Impacto:** 4/5 · **Confiança:** 3/5.
**Aceite:** taxa de casamento entre bases reportada; se o casamento for < 80%, a página
abre em modo “por base”, não individual.

---

## D7. Geointeligência Operacional — *Onda 2*

**Pergunta:** “Onde estão demanda, capacidade e quebra no mapa?”
**Para quem:** coordenação de campo e diretoria.

**Fontes:** `pages/rota_inicial.py` (`CIDADE`, `COORDENADA X/Y`, velocidade), o cache
geográfico já versionado em `.streamlit_cache/geo_sp_2022.parquet`, volumetria e quebra
por cidade.

**Métricas:** O.S. por município; técnicos por município; O.S./técnico; quebra por
município; municípios sem cobertura; distância média estimada entre atendimentos.

**Visualizações:** mapa de calor/cluster; coroplético por município; bolha demanda ×
capacidade; tabela de prioridade por município.

**O que muda:** existe mapa da carga inicial, mas ele não conversa com capacidade nem com
quebra.

**Esforço:** M — G · **Impacto:** 4/5 · **Confiança:** 3/5.
**Riscos:** performance de renderização; coordenadas ausentes/inválidas; leitura apressada
de distância como tempo real.
**Aceite:** tempo de abertura < 5 s; legenda de cobertura de coordenadas; exportação da
tabela municipal.

---

## D8. Dimensionamento e Simulador de Capacidade — *Onda 3*

**Pergunta:** “Quantos técnicos preciso por base para fechar a meta?”
**Para quem:** diretoria e planejamento.

**Fontes:** `pages/volumetria.py` (escalados × montados), configuração da prévia (Rota
Inicial, montados, parados), histórico e calendário de feriados (`holidays`, hoje opcional
em `qtde_os.py`).

**Métricas:** capacidade instalada (técnicos × produtividade × dias úteis); demanda
projetada; gap por base; cenários de headcount, produtividade e absenteísmo esperado.

**Visualizações:** bullet capacidade vs demanda; cascata do gap; linha de cenários;
tabela *what-if*.

**Esforço:** M · **Impacto:** 4/5 · **Confiança:** 4/5.
**Aceite:** cada premissa é editável e visível; cenário não sobrescreve configuração real;
exporta o cenário simulado com carimbo de data.

---

## D9. Tendências e Sazonalidade (data mart histórico) — *Onda 1*

**Pergunta:** “O que é sazonal, o que é tendência e o que é ruído?”
**Para quem:** diretoria e planejamento.

**Fontes:** `Historico_OS`, `Historico_Equipe`, `Previas_Diarias` e snapshots mensais dos
indicadores (a criar — hoje só existe a leitura corrente).

**Métricas:** série diária/mensal; médias móveis 7/30; comparação ano contra ano; dias
atípicos; heatmap calendário (dia da semana × semana); decomposição tendência/sazonalidade.

**Visualizações:** linha com MM7/MM30; calendário; barras de desvio vs média; heatmap
mês × segmento.

**O que muda:** o portal tem histórico gravado, mas nenhuma página o lê como série longa.
Esta é a base para metas, projeções e dimensionamento.

**Esforço:** M (com data mart já pronto) — G sem ele · **Impacto:** 5/5 · **Confiança:** 4/5.
**Depende de:** C1 (DuckDB/Parquet) e padronização de chaves (B4).
**Aceite:** série cobre ≥ 12 meses; lacunas aparecem como lacuna, não como zero;
comparação ano contra ano só quando houver base comparável.

---

## D10. Observabilidade de Dados e Alertas — *Onda 1, quick win*

**Pergunta:** “Posso confiar no número que estou vendo?”
**Para quem:** todos, especialmente quem apresenta número para fora.

**Fontes:** `services/cache_dados.ResultadoCarga` (origem, duração, idade, ETag, linhas,
memória), `components/saude_dados`, status de sincronização, histórico para reconciliação.

**Métricas:** frescor por fonte vs SLO; sucesso/falha por tentativa; duração p50/p95;
colunas ausentes/novas; duplicidade e nulos; divergência entre fontes; última
sincronização por aba.

**Visualizações:** semáforo por fonte; linha de duração; barras de falhas; tabela de
incidentes; banner global nas demais páginas.

**O que muda:** a Home mostra status da última tentativa, mas não SLO, histórico de falhas,
contrato de colunas nem alerta.

**Esforço:** P — M · **Impacto:** 5/5 · **Confiança:** 5/5.
**Aceite:** banner global com no máximo uma linha; cada fonte tem SLO documentado; alerta
dispara uma vez por incidente (sem spam).

---

### Outras ideias (para o backlog, não para agora)

- **Carteira de contratos em risco:** combina quebra + retorno + indicadores para ranquear
  contratos que precisam de visita técnica. Depende de D4 e D5.
- **Painel de adesão a ferramentas (NR35, Tec1, OS Digital)** por base e por mês, como
  recorte do Scorecard.
- **Central de auditoria de acessos:** quem abriu, filtrou e exportou o quê (só faz sentido
  depois de A1/A5).

---

# Parte II — Melhorias

Organizadas por eixo, com prioridade **P0** (risco imediato), **P1** (próximo ciclo) e
**P2** (evolução). Cada item traz o problema, a ação e o critério de pronto.

## Eixo A — Acesso, privacidade e LGPD

### A1. Login único no entrypoint (P0 · M)
**Problema:** o portal abre direto; o único login é o da Gestão de Ativos.
**Ação:** proteger o `streamlit_app.py` com `st.login()` (OIDC Google, recomendado para
não manter senha no app) ou, como fallback, autenticação em `st.secrets` com hash forte
(reaproveitar `_hash_senha`/`_verificar_senha` de `gestao_ativos.py:133-150`). Criar
`services/acesso.py` com `usuario_atual()`, `exigir_login()` e `st.logout()` na sidebar.
**Pronto quando:** nenhuma página renderiza conteúdo sem sessão autenticada; teste
`AppTest` garante bloqueio; sessão expira por inatividade.

### A2. Perfis e filtro por base aplicados na camada de dados (P0 · M)
**Problema:** `role` e `bases` existem no modelo de secrets, mas não são aplicados no
portal.
**Ação:** papéis `admin`, `gestor`, `supervisor`, `leitura`; `escopo_do_usuario()` injetado
em `services/dados_sessao` e em cada serviço de leitura, de modo que o filtro valha também
para exportação e para gráficos — não só para o selectbox.
**Pronto quando:** um supervisor de Guarulhos não consegue obter dados de outra base nem
via URL, nem via exportação.

### A3. Política de dados sensíveis e LGPD (P0 · M)
**Problema:** `controle_absenteismo` guarda tipo de ausência, justificativa e motivo —
inclusive atestado e afastamento — e o dado circula em tela e em planilha.
**Ação:** classificar as colunas (aberto/interno/restrito/sensível); mascarar motivo em
exportações amplas; restringir a visão individual a RH e gestão direta; definir base legal,
retenção e descarte; registrar acesso a dado sensível; incluir aviso de uso no rodapé.
**Pronto quando:** existe inventário de dados; exportação ampla não carrega motivo de
saúde; política aprovada e referenciada em `docs/`.

### A4. Segredos, contas e ambientes (P1 · P)
**Problema:** `config/settings.py` traz IDs padrão de planilhas/Drive; a mesma conta de
serviço lê e escreve em tudo.
**Ação:** exigir configuração por ambiente (dev/prod), separar credencial de leitura da de
escrita, rotacionar a chave, validar `st.secrets` na inicialização e remover fallback de
ID em produção.
**Pronto quando:** app falha com mensagem clara se faltar configuração, em vez de usar
ID de exemplo; escrita usa credencial distinta.

### A5. Auditoria de leitura, filtro e exportação (P1 · M)
**Problema:** só a escrita é auditada.
**Ação:** `services/auditoria.py` com evento `{quem, quando, página, filtros, linhas,
formato}` gravado em aba `Auditoria_Painel`; nunca gravar o conteúdo, apenas metadados.
**Pronto quando:** é possível responder “quem baixou a base de presença de outubro?”.

### A6. Superfície pública da demo (P0 · P)
**Problema:** o README aponta uma demo pública.
**Ação:** confirmar com a empresa se a demo usa dados reais; se sim, despublicar, proteger
com login ou popular com base sintética.
**Pronto quando:** nenhuma base real é acessível sem autenticação.

---

## Eixo B — Confiabilidade e qualidade de dados

### B1. Contrato de dados por fonte (P0 · M)
**Problema:** colunas são descobertas por sinônimos e a página segue com aviso.
**Ação:** `services/contratos_dados.py` com, por fonte: colunas obrigatórias, tipos,
faixas aceitas, unicidade e regra de nulo. Validar na carga, falhar com mensagem
acionável (“a aba Prod perdeu a coluna DATA; última carga válida há 2 h”) e cobrir cada
fonte com teste.
**Pronto quando:** renomear uma coluna crítica produz erro claro, não número zerado.

### B2. SLO de frescor por fonte e banner global (P0 · P)

> **Status (17/11/2026): parcialmente implementado.** Faixa global em
> `components/frescor_fontes.py` (renderizada por `abrir_dashboard`), limites
> por fonte em `config/slo_fontes.py` e regra pura em `services/frescor.py`.
> Pendente: página de status com histórico, SLO de Indicadores/Prévia ligado às
> cargas próprias dessas páginas e janela comercial (hoje o cálculo é em tempo
> corrido).

**Problema:** `avaliar_frescor` usa limites genéricos e só a Home consome.
**Ação:** declarar SLO (ex.: Produção 15 min em horário comercial; Ativos e Indicadores
24 h; Prévia D-1 até 09h), exibir faixa global discreta e página de status com histórico.
**Pronto quando:** qualquer dashboard mostra a idade do dado e o estado contra o SLO.

### B3. Reconciliação entre fontes (P1 · M)
**Problema:** produção, consultivo e prévia não são conferidos entre si.
**Ação:** rotina diária que compara totais por base e reporta diferença acima de um
limiar (ex.: 2%) na página de observabilidade e no alerta.
**Pronto quando:** divergência do dia é visível antes da reunião.

### B4. Chaves canônicas e dimensão histórica de técnico (P1 · M)
**Problema:** a hierarquia é sempre a atual; mudança de base reescreve o passado.
**Ação:** consolidar `normalizar_login` como chave; criar dimensão `dim_tecnico` com
vigência (início/fim) por base e monitor, alimentada pela `lista_ativos`; usar a dimensão
vigente na data do fato.
**Pronto quando:** relatório de janeiro continua mostrando a base de janeiro.

### B5. Metas centralizadas, versionadas e auditáveis (P0 · M)
**Problema:** metas e limiares espalhados por cinco módulos, sem vigência.
**Ação:** `config/metas.py` com `{escopo, chave, valor, vigência_inicio, vigência_fim,
responsável}` e `metas_vigentes(data)`. Migrar `config/metas_operacionais.py`,
`dashboard_meta.py:335-336`, `qtde_os.py:136-162`, `indicadores.py:76-83` e
`quebra_geral.py:121-122`. Registrar alteração em auditoria.
**Pronto quando:** mudar a meta de Guarulhos é um registro com data e autor, não um
deploy.

### B6. Dependências completas, fixadas e testadas (P0 · P)
**Problema:** `requirements.txt` não instala `folium`, `geobr`, `geopandas`,
`streamlit_folium`, `reportlab` (imports de topo) nem `xlsxwriter`, `holidays`, `gdown`,
`streamlit_autorefresh`, `extract_msg` (opcionais); em compensação, carrega pacotes sem uso
(`duckdb`, `sqlglot`, `sql_metadata`, `gspread-pandas`, `matplotlib`); o CI instala apenas
`requirements-test.txt`.
**Ação:** dividir em `requirements.txt` (núcleo fixado), `requirements-extras.txt` (mapa,
PDF, e-mail) e `requirements-dev.txt`; gerar lock; no CI, instalar o conjunto real e rodar
`pip check` + smoke test que importa todas as páginas.
**Pronto quando:** ambiente limpo sobe todas as 19 páginas; CI reproduz o ambiente de
produção.

### B7. CI mais rígido (P1 · P)
**Ação:** adicionar cobertura (`--cov`, piso para `services/`), `ruff format --check`,
`pip-audit`, smoke test de páginas com base vazia e com base sintética.
**Pronto quando:** PR que quebra import ou reduz cobertura fica vermelho.

---

## Eixo C — Performance e escala

### C1. Camada analítica DuckDB/Parquet (P1 · G)
**Problema:** `duckdb` está instalado e ocioso; joins e histórico rodam em memória no
processo do Streamlit.
**Ação:** pipeline que materializa CSV/Sheets em Parquet e tabelas fato/dimensão
(`fato_os`, `fato_quebra`, `fato_retorno`, `dim_tecnico`, `dim_tempo`); dashboards
consultam agregados. Diretório fora do Git (como já ocorre com o cache).
**Pronto quando:** série de 12 meses responde em < 1 s; Sheets deixa de ser lido em
tempo de dashboard.

### C2. Pré-agregações diárias (P1 · M)
**Ação:** gerar na sincronização: produção por dia/base/supervisor, quebra por
dia/motivo/cidade, retorno por dia/contrato. Ler agregado nas telas executivas.
**Pronto quando:** Sala de Situação e Tendências não tocam a base bruta.

### C3. Padrões de runtime do Streamlit (P1 · M)
**Problema:** `st.tabs` renderiza todas as abas; filtros disparam rerun global.
**Ação:** `st.fragment` em filtros e blocos pesados (o padrão já existe em
`envio_excel.py:1285`); trocar abas densas por `st.segmented_control` + render sob
demanda; `st.cache_resource` para clientes; invalidar cache por versão de esquema.
**Pronto quando:** mudar um filtro não recarrega a página inteira; abrir uma aba não
calcula as outras.

### C4. Tabelas: truncamento silencioso e duas linguagens visuais (P1 · M)

> **Status (17/11/2026): parcialmente implementado.** `render_table_html` avisa
> “Exibindo X de N”, aceita `max_rows=None` e exporta o conjunto completo.
> Pendente: paginação/busca no componente e substituição das tabelas que ainda
> caem para `st.dataframe`.

**Problema:** `render_table_html` corta em `max_rows=100` por padrão
(`components/componentes.py:1772`) e **não avisa**; a página que precisa do total cai
para `st.dataframe`, criando dois padrões visuais. O HTML é montado inteiro no servidor.
**Ação:** componente único de tabela com paginação (“mostrar mais”), aviso “exibindo 100
de N”, busca e exportação do total; `st.dataframe` só para inspeção bruta.
**Pronto quando:** nenhuma tabela esconde linha sem dizer; 10 mil linhas navegam sem
travar o navegador.

### C5. Orçamento de performance em teste (P2 · M)
**Ação:** base sintética de 100 mil O.S., medir p95 de abertura das páginas principais e
falhar o CI acima do orçamento (ex.: 4 s com cache quente).
**Pronto quando:** regressão de performance aparece no PR, não na reunião.

### C6. Payload de gráficos (P2 · P)
**Ação:** agregar no servidor antes de plotar, limitar pontos, usar
`config_minimalista`, evitar milhares de marcadores.
**Pronto quando:** nenhuma figura envia mais de ~5 mil pontos ao navegador.

---

## Eixo D — Arquitetura e manutenção

### ARQ1. Decompor as páginas monolíticas (P1 · G, incremental)
**Problema:** seis páginas acima de 1.700 linhas; regra de negócio dentro da página.
**Ação:** meta de ≤ 400 linhas por página; mover cálculo para `services/` e visual para
`components/`; usar `services/previa_diaria.py` como referência de camada pura testável.
Começar por `quebra_unificada` e `dashboard_meta` (maior acoplamento).
**Pronto quando:** página só orquestra estado, layout e chamadas de serviço.

### ARQ2. Eliminar import entre páginas (P1 · M)
**Problema:** `pages/quebra_unificada.py:73` importa `pages.quebra_geral`.
**Ação:** mover `Motor`, `DataLoader` e `Config` de quebra para `services/quebra.py`;
páginas consomem o serviço.
**Pronto quando:** nenhuma página importa outra.

### ARQ3. Porta única de acesso a fontes (P1 · G)
**Problema:** `dashboard_meta` baixa produção e consultivo por conta própria
(`@st.cache_data` em 631-760); `indicadores` tem o próprio download.
**Ação:** `services/fontes.py` como fachada (contrato + cache + telemetria), consumida por
todas as páginas.
**Pronto quando:** existe um só caminho para cada fonte; trocar transporte é mudança local.

### ARQ4. Contratos tipados para resultados (P2 · M)
**Ação:** `dataclass`/`TypedDict` para resumos e achados; `mypy` gradual em `services/` e
`components/`; proibir `Any` em APIs públicas.
**Pronto quando:** `mypy` roda no CI sem bloquear, com módulos críticos cobertos.

### ARQ5. Estratégia de testes de página (P1 · M)
**Problema:** `AppTest` existe em quatro arquivos; a maioria das páginas não tem smoke
test.
**Ação:** teste para cada página com (a) base vazia, (b) base sintética mínima, (c) base
com coluna ausente; golden files para exportações.
**Pronto quando:** toda página tem ao menos um teste de fumaça.

### ARQ6. Versão, changelog e ADRs (P2 · P)

> **Status (17/11/2026): implementado na parte de versão/changelog.** Fonte única
> em `config.settings`, `CHANGELOG.md` e teste `tests/test_versao_portal.py`.
> ADRs continuam no backlog.

**Problema:** `config/settings.py` diz 3.7.0; README e `docs/DESIGN_SYSTEM.md` dizem 3.6.0;
não há changelog.
**Ação:** fonte única de versão, `CHANGELOG.md` (Keep a Changelog), teste que compara
README/badges com `settings`, ADRs para decisões estruturais (auth, Sheets × DuckDB,
propriedade das metas).
**Pronto quando:** `docs/` e código contam a mesma história.

### ARQ7. Limpeza de código e dependências mortas (P2 · P)
**Ação:** remover imports sem uso, duplicações de normalização e pacotes não usados;
manter `ruff` e ampliar regras aos poucos.
**Pronto quando:** `ruff check` sem exceções desnecessárias e lista de dependências enxuta.

---

## Eixo E — Experiência e design

### E1. Filtros globais e link profundo (P2 · M)
**Problema:** cada página tem filtros próprios; só `dashboard_meta` usa `st.query_params`.
**Ação:** escopo global (período, base, segmento) na sidebar, sincronizado com a URL;
botão “copiar link desta visão”.
**Pronto quando:** enviar “Produção, Guarulhos, outubro” por mensagem abre a mesma tela.

### E2. Dicionário único de métricas (P2 · P)
**Problema:** definições e nomes variam; `GLOSSARIO` só existe em `indicadores.py`.
**Ação:** `config/glossario.py` com nome, fórmula, fonte, dono e sinônimos; usar o campo
`ajuda` dos cartões de KPI; página “Como lemos os números”.
**Pronto quando:** toda métrica de destaque tem tooltip com fórmula e fonte.

### E3. Relatório executivo em PDF (P2 · M)
**Problema:** PDF existe só na Quebra por Segmento.
**Ação:** `services/relatorio_pdf.py` com capa, KPIs, três gráficos e insights; “pacote
diretoria” a partir de qualquer dashboard; marca e rodapé padronizados.
**Pronto quando:** reunião mensal é servida por um PDF gerado do painel.

### E4. Modo Sala/TV (P2 · P)
**Ação:** modo tela cheia via query param protegido por token, auto-refresh, tipografia
ampliada, filtros escondidos; dependência `streamlit_autorefresh` incluída de verdade.
**Pronto quando:** TV da operação roda 8 h sem intervenção.

### E5. Acessibilidade AA (P2 · M)
**Ação:** revisar contraste (especialmente heroes e textos sobre gradiente), foco visível,
`aria-label` em chips/status, cabeçalhos de tabela com escopo, alternativa textual e
tabela de dados para gráficos, respeito a `prefers-reduced-motion` (já previsto em
`css_global.py`).
**Pronto quando:** checklist AA aplicado nas páginas principais e testado com teclado.

### E6. Mobile de verdade (P2 · M)
**Problema:** `@media` só em alguns componentes; grades de 6 KPIs e tabelas largas
quebram.
**Ação:** testar em 390 px; KPIs em 2 colunas; tabelas viram cartões; altura de gráfico
adaptativa; filtros em expansor.
**Pronto quando:** supervisor consulta produção e presença no celular sem zoom horizontal.

### E7. Estados vazios, carregamento e erro acionável (P2 · P)
**Ação:** padronizar skeleton, mensagem com causa provável e botão “tentar novamente”;
carimbo de atualização por bloco, não só no topo.
**Pronto quando:** nenhuma tela fica em branco sem explicar o que fazer.

### E8. Busca global e favoritos (P2 · P)
**Ação:** busca unificada de painel, técnico e contrato; favoritos e “últimos acessados”
por usuário.
**Pronto quando:** achar um técnico não exige escolher a página certa antes.

---

## Eixo F — Operação e cultura

### F1. Alertas proativos (P1 · G)
**Ação:** regras (meta abaixo de X% até o dia 20, quebra acima do SLA, fonte fora do SLO,
absenteísmo acima da média) com deduplicação, janela de silêncio e canal Teams/e-mail;
execução por agendador (GitHub Actions/Cloud Scheduler) chamando um script, não uma sessão
Streamlit.
**Pronto quando:** desvio relevante chega antes da reunião, uma vez por incidente.

### F2. Relatórios agendados (P2 · M)
**Ação:** prévia diária às 07:30, fechamento semanal e pacote mensal em PDF para a
diretoria; histórico de envios.
**Pronto quando:** diretoria recebe o padrão sem alguém montar planilha.

### F3. Planos de ação ligados ao desvio (P2 · M)
**Ação:** aba `Planos_Acao` (desvio, dono, prazo, status, evidência); botão “criar plano”
no ponto do gráfico; acompanhamento na reunião seguinte.
**Pronto quando:** todo desvio crítico tem dono e prazo visíveis no painel.

### F4. Telemetria de uso privada (P2 · P)
**Ação:** contar abertura de página, filtros aplicados e exportações (sem PII), gerar
relatório mensal de adoção.
**Pronto quando:** priorização de dashboards usa dado, não opinião.

### F5. Runbook e governança de métricas (P2 · P)
**Ação:** runbook de falha de fonte (contatos, passos, RTO/RPO), dono por métrica, processo
de mudança de meta e revisão trimestral do dicionário.
**Pronto quando:** qualquer pessoa de plantão sabe o que fazer e quem avisar.

---

# Parte III — Priorização e roadmap

A ordem abaixo combina impacto, esforço e confiança. “Onda” é a janela sugerida; itens
marcados como “contínuo” atravessam as ondas e não bloqueiam entrega.

## 5.1 Matriz de prioridade

| ID | Iniciativa | Impacto | Esforço | Confiança | Onda |
|----|------------|---------|---------|-----------|------|
| A1 | Login único + logout | 5 | M | 5 | 0 |
| A2 | Perfis e filtro por base no serviço | 5 | M | 4 | 0 |
| A3 | Política de dados sensíveis e LGPD | 5 | M | 4 | 0 |
| A6 | Rever demo pública | 5 | P | 5 | 0 |
| B5 | Metas centralizadas e versionadas | 4 | M | 5 | 0 |
| B6 | Dependências completas + CI real | 4 | P | 5 | 0 |
| B1 | Contrato de dados | 4 | M | 5 | 0 |
| B2 | SLO de frescor + banner | 4 | P | 5 | 0 |
| D10 | Observabilidade de dados e alertas | 5 | P–M | 5 | 1 |
| D1 | Sala de Situação | 5 | M | 4 | 1 |
| D9 | Tendências e sazonalidade | 5 | M–G | 4 | 1 |
| D4 | Scorecard 360 | 5 | M | 4 | 1 |
| C1 | Data mart DuckDB/Parquet | 5 | G | 4 | 1 |
| B3 | Reconciliação entre fontes | 4 | M | 4 | 1 |
| B4 | Dimensão histórica de técnico | 4 | M | 4 | 1 |
| D2 | Torre de Quebra preditiva | 4 | M | 4 | 2 |
| D3 | Produtividade × Disponibilidade | 4 | M–G | 3 | 2 |
| D5 | Retrabalho e reincidência | 4 | M | 3 | 2 |
| D7 | Geointeligência operacional | 4 | M–G | 3 | 2 |
| F1 | Alertas proativos | 4 | G | 3 | 2 |
| D6 | Funil do atendimento | 4 | G | 3 | 3 |
| D8 | Simulador de capacidade | 4 | M | 4 | 3 |
| E3 | PDF executivo | 3 | M | 5 | 3 |
| E6 | Mobile | 3 | M | 4 | 3 |
| E1 | Filtros globais + link profundo | 3 | M | 4 | 3 |
| E2 | Dicionário de métricas | 3 | P | 5 | 1 |
| ARQ1 | Decompor páginas | 4 | G | 4 | contínuo |
| ARQ2 | Remover import entre páginas | 3 | M | 5 | 1 |
| ARQ3 | Porta única de fontes | 4 | G | 4 | contínuo |
| ARQ5 | Smoke tests por página | 4 | M | 5 | 1 |
| ARQ6 | Versão + changelog | 2 | P | 5 | 0 |
| E5 | Acessibilidade AA | 3 | M | 4 | 3 |
| F2 | Relatórios agendados | 3 | M | 4 | 3 |
| F3 | Planos de ação | 3 | M | 4 | 3 |

## 5.2 Três ondas

### Onda 0 — “Fechar a porta e arrumar a casa” (2 semanas)

- A1, A2 (MVP: login + supervisor por base), A6, A3 (política e mascaramento inicial).
- B6 + B7 (dependências e CI), B5 (metas em um só lugar), B1 (contrato das 4 fontes
  críticas), B2 (SLO + banner).
- ARQ6 (versão/changelog).

**Entregável:** portal autenticado, instalação reproduzível e qualquer número acompanhado
de idade e estado da fonte.

**Métrica de saída:** 100% das páginas atrás de login; `pip install -r requirements.txt`
sobe as 19 páginas; toda fonte tem SLO exibido.

### Onda 1 — “Confiança e primeira decisão” (semanas 3–6)

- D10 (observabilidade), D1 (Sala de Situação), D9 (Tendências MVP), D4 (Scorecard 360).
- C1 (data mart), B3 (reconciliação), B4 (dimensão de técnico), ARQ2
  (dessacoplar quebra), E2 (dicionário), ARQ5 (smoke tests).

**Entregável:** uma tela de decisão diária, uma de tendência e uma de pessoas, todas
alimentadas por dados reconciliados.

**Métrica de saída:** tempo para responder “vamos fechar a meta?” cai para < 2 min;
≥ 95% das fontes dentro do SLO no horário comercial.

### Onda 2 — “Ação e campo” (semanas 7–12)

- D2, D3, D5, D7, F1 (alertas), ARQ1/ARQ3 (decomposição incremental).

**Entregável:** quebra e retrabalho priorizados por impacto; eficiência real por equipe;
mapa de demanda × capacidade; desvio avisado por canal.

**Métrica de saída:** ≥ 80% dos desvios críticos com plano de ação aberto; redução
mensurável de retrabalho na base piloto.

### Onda 3 — Backlog priorizado

- D6 (funil), D8 (simulador), E3 (PDF), E1 (links), E5 (acessibilidade), E6 (mobile),
F2 (agendamento), F3 (planos), F4 (telemetria), ARQ4/ARQ7 (tipagem e limpeza).

## 5.3 Métricas de sucesso do ciclo

| Dimensão | Métrica | Meta |
|----------|---------|------|
| Segurança | Páginas atrás de login | 100% |
| Privacidade | Exportações de dado sensível registradas | 100% |
| Confiança | Fontes dentro do SLO em horário comercial | ≥ 95% |
| Confiança | Divergência entre fontes no fechamento | < 2% |
| Adoção | Gestores usando ≥ 3 painéis por semana | ≥ 70% |
| Eficiência | Tempo de fechamento diário | −30% |
| Eficiência | Planilhas manuais paralelas eliminadas | ≥ 3 |
| Engenharia | Cobertura de `services/` | ≥ 70% |
| Engenharia | Páginas acima de 800 linhas | 0 (meta de 12 meses) |
| Produto | Tempo para responder pergunta executiva | < 2 min |

---

# Parte IV — Como implementar (receitas)

## 6.1 Nova página no padrão vigente

Toda página nova precisa entrar em `config/navegacao.PAGINAS` e em
`DASHBOARDS_PADRONIZADOS`; o teste `tests/test_organizacao_dashboards.py` falha se a
página não estiver no mapa, se repetir ícone/título ou se reimplementar helpers.

```python
"""pages/sala_situacao.py — cockpit diário (esqueleto)."""

from __future__ import annotations

import streamlit as st

from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.kpi_cards import render_kpi_row, SpecKPIAvancado
from components.layout_pagina import secao
from services.dados_sessao import exigir_base, resumir_carga
from services.sala_situacao import consolidar_dia  # regra pura, testável

st.set_page_config(page_title="Sala de Situação | TOTALE", page_icon="🛰️", layout="wide")

SECOES = ("Dia", "Fechamento", "Quebra", "Equipe", "Exportação")


def main() -> None:
    base = exigir_base(pagina="Sala de Situação")
    consolidado = consolidar_dia(base)          # nada de cálculo na página

    abrir_dashboard(
        "Sala de Situação",
        subtitulo="Dia, fechamento, quebra e equipe em uma tela",
        badge="COCKPIT",
        icone="🛰️",
        secoes=SECOES,
        resumo=resumir_carga(base),
        origem="Produção + Prévia + Presença",
    )

    with secao("Dia", icone="today"):
        specs: list[SpecKPIAvancado] = [
            {
                "label": "O.S. HOJE",
                "valor": consolidado["os_hoje_fmt"],
                "delta": consolidado["delta_ontem"],
                "sparkline": consolidado["serie_14d"],
                "progresso": (consolidado["os_hoje"], consolidado["meta_dia"]),
                "meta_rotulo": "da meta diária",
                "icone": "bolt",
                "ajuda": "O.S. baixadas hoje contra a meta diária rateada.",
            },
        ]
        render_kpi_row(specs, colunas=3)

    with secao("Fechamento", icone="flag"):
        st.plotly_chart(consolidado["fig_projecao"], width="stretch")

    secao_exportacao(consolidado["tabela"], nome_arquivo="sala_situacao", chave="sala")
    fechar_dashboard()


if __name__ == "__main__":
    main()
```

## 6.2 Gráfico pela fábrica oficial

```python
from components.graficos import criar_grafico, render_grafico

fig = criar_grafico(
    "ranking",
    df_motivos,
    "Motivo de Baixa",
    "Volume",
    titulo="Pareto de motivos",
)
render_grafico(fig)
```

Tipos disponíveis em `TIPOS_GRAFICO`: linha, área, barras, ranking, pizza, donut,
dispersão, histograma, caixa, violino, calor, calendário, treemap, sunburst, funil, radar,
cascata, bullet, gauge, polar, densidade, combinado, progresso e comparativo.

## 6.3 Contrato de dados (esboço)

```python
# services/contratos_dados.py
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class Contrato:
    fonte: str
    obrigatorias: tuple[str, ...]
    numericas: tuple[str, ...] = ()
    unicidade: tuple[str, ...] = ()

    def validar(self, df: pd.DataFrame) -> list[str]:
        erros: list[str] = []
        ausentes = [c for c in self.obrigatorias if c not in df.columns]
        if ausentes:
            erros.append(f"colunas ausentes: {', '.join(ausentes)}")
        for coluna in self.numericas:
            if coluna in df.columns and not pd.api.types.is_numeric_dtype(df[coluna]):
                erros.append(f"coluna {coluna} não é numérica")
        for chave in self.unicidade:
            if chave in df.columns and df[chave].duplicated().any():
                erros.append(f"chave {chave} duplicada")
        return erros
```

A validação deve rodar **antes** do primeiro gráfico e produzir mensagem acionável, com a
idade da última carga boa. Nunca “seguir com zero”.

## 6.4 Frescor e banner global

```python
import streamlit as st

from components.saude_dados import avaliar_frescor

estado, texto = avaliar_frescor(
    ultimo_sucesso=st.session_state.get("ultima_atualizacao"),
    sucesso_na_tentativa_atual=True,
)
# estado em {"ok", "alerta", "critico"} → faixa discreta no topo de cada dashboard
```

Evolução sugerida: `avaliar_frescor(..., slo=timedelta(minutes=15))` por fonte, com o SLO
vindo de `config/slo_fontes.py` e `ultima_atualizacao` por chave, não só global.

## 6.5 Login (esboço)

```python
# streamlit_app.py (topo, antes de st.navigation)
import streamlit as st

if not st.user.is_logged_in:
    st.markdown("## Portal TOTALE")
    st.button("Entrar com Google", on_click=st.login)
    st.stop()

# sidebar
with st.sidebar:
    st.caption(f"Conectado como {st.user.email}")
    st.button("Sair", on_click=st.logout)
```

Requer a seção `[auth]` em `secrets.toml` (client ID/secret, cookie secret, redirect URI).
A autorização da conversa Arena **não** é transferida ao app — a configuração OIDC é da
empresa. Alternativa sem OIDC: validar usuário/senha contra `st.secrets` com hash e
expiração de sessão, reaproveitando a rotina já existente na Gestão de Ativos.

## 6.6 Data mart (esboço)

```python
import duckdb

con = duckdb.connect("analitico.duckdb")
con.execute("""
    CREATE OR REPLACE TABLE fato_os AS
    SELECT CAST(data AS DATE) AS dia,
           UPPER(TRIM(base)) AS base,
           UPPER(TRIM(supervisor)) AS supervisor,
           1 AS os,
           CAST(pontos AS DOUBLE) AS pontos
    FROM ler_parquet('cache/prod_*.parquet')
""")
serie = con.execute("""
    SELECT dia, SUM(os) AS os
    FROM fato_os
    WHERE dia BETWEEN ? AND ?
    GROUP BY dia ORDER BY dia
""", [inicio, fim]).df()
```

Manter o banco **fora do repositório** (mesma política do cache Parquet) e reconstruível a
partir das fontes.

---

# Parte V — Definição de pronto e governança

## 7.1 Checklist de um novo dashboard

- [ ] Entrou em `config.navegacao.PAGINAS` e em `DASHBOARDS_PADRONIZADOS`.
- [ ] Abre com `abrir_dashboard` e fecha com `fechar_dashboard`; seções em `secao()`.
- [ ] Lê a base por `services.dados_sessao` e regra de negócio em `services/` (página só
      orquestra).
- [ ] Contrato de dados validado, com mensagem acionável em caso de falha.
- [ ] Frescor e origem visíveis nos chips e no banner.
- [ ] KPIs com `ajuda` (definição + fonte) e variação com período comparável.
- [ ] Exportação CSV/XLSX respeitando o perfil do usuário.
- [ ] Teste `AppTest` com base vazia e base sintética.
- [ ] Orçamento de performance verificado (p95 com cache quente).
- [ ] Revisão de mobile (390 px) e acessibilidade (teclado + contraste).
- [ ] Glossário atualizado; `CHANGELOG.md` com a entrega.
- [ ] Nenhuma métrica sem dono definido.

## 7.2 Riscos e mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Exposição de dado pessoal/sensível | Alta (hoje) | Alto | Onda 0 de acesso e LGPD antes de qualquer novo dashboard |
| Dependência do Google Sheets como “banco” | Alta | Médio | Data mart + SLO + reconciliação; Sheets como entrada |
| Vínculo impreciso entre bases (contrato/data/login) | Média | Alto | Medir taxa de casamento antes de publicar visão individual |
| Índice composto virar “nota” injusta | Média | Alto | Amostra mínima, pesos públicos, revisão com RH |
| Excesso de dashboards sem adoção | Média | Médio | Telemetria de uso + critério de aposentadoria de painel |
| Metas mudarem sem registro | Alta | Médio | B5 com vigência e auditoria |
| Refatoração parar no meio | Média | Médio | Decomposição incremental por página, coberta por smoke tests |

## 7.3 O que evitar

- Criar painel porque “todo mundo tem”, sem pergunta de negócio e dono.
- Publicar média ou ranking sem amostra mínima.
- Transformar ausência médica em ranking individual visível.
- Colocar regra de negócio na página “só desta vez”.
- Duplicar leitura de fonte em uma página nova em vez de evoluir o serviço.
- Usar planilha como banco transacional para histórico longo.
- Esconder dado faltante com zero: lacuna é informação.

---

# Anexo A — Mapa de fontes e chaves

| Fonte | Onde é lida | Chaves/colunas relevantes | Uso atual |
|-------|-------------|---------------------------|-----------|
| `Prod` (produção) | `services/dados_sessao`, `pages/*` | `Nome Equipe`, `CódAuxEquipe`, `Supervisor`, `Projeto`, `Pontos`, `O.S.`, datas, base | Produção, metas, prévia |
| `lista_ativos` | `services/hierarquia`, `pages/gestao_ativos` | login, nome, base, monitor, situação | Hierarquia, presença, quebra |
| `controle_absenteismo` | `services/absenteismo` | `ID`, `Login`, `Tipo`, `Data Início/Fim`, `Dias Úteis`, `Justificativa`, `Motivo`, `Status` | Lista de presença |
| `Historico_OS` | `pages/previa_totale` | `Data`, `Base`, `OS_Inicial`, contadores | Histórico diário |
| `Historico_Consultivo` | `pages/previa_totale` | data, base, contadores | Histórico diário |
| `Config_Equipe` / `Historico_Equipe` | `pages/previa_totale` | base, supervisor, montados, parados, rota inicial | Equipe e capacidade |
| `Previas_Diarias` | `pages/previa_totale` | data, base, 33 colunas da prévia | Apresentação e reabertura |
| Indicadores (Drive) | `pages/indicadores` | `Geoloc_Os`, `OS_Digital`, `Aderencia_Ura`, `Nr35`, `Tec1`, `Baixa_Pda` por login | Qualidade por técnico |
| Consultivos (Drive) | `pages/consultivo`, `pages/dashboard_meta` | projeto, supervisor, data, quantidade | Consultivos e metas |
| Base de quebra | upload em `pages/quebra_*` | `STATUS CONTRATO`, `TIPO_SERVICO`, `MOTIVO DE BAIXA`, `CIDADE`, `TOTAL DE TAREFAS`, `FLAG_GPON` | SLA e causa raiz |
| TOA × Sinapse | `pages/retorno` | contrato, login do técnico, monitor, status, intervalo, cidade | Dono do retorno |
| Bases de rota | upload em `pages/rota_*` | `CIDADE`, `COORDENADA X/Y`, velocidade, status | Mapa e volumetria |

# Anexo B — Referências de código usadas no diagnóstico

- Navegação e padrão: `config/navegacao.py`, `components/dashboards.py`,
  `tests/test_organizacao_dashboards.py`.
- Acesso: `streamlit_app.py`, `pages/gestao_ativos.py:705`, `.streamlit/secrets.example.toml`.
- Dados sensíveis: `services/absenteismo.py:73-87`.
- Frescor: `components/saude_dados.py`; telemetria de carga em `services/cache_dados.py`.
- Metas: `config/metas_operacionais.py`, `pages/dashboard_meta.py:335-336`,
  `pages/qtde_os.py:136-162`, `pages/indicadores.py:76-83`,
  `pages/quebra_geral.py:121-122`.
- Acoplamento: `pages/quebra_unificada.py:73`.
- Páginas monolíticas: `pages/indicadores.py` (2.520), `pages/rota_inicial.py` (2.354),
  `pages/dashboard_meta.py` (2.307), `pages/quebra_unificada.py` (2.030).
- Dependências e CI: `requirements.txt`, `requirements-test.txt`,
  `.github/workflows/quality.yml`.
- Histórico: `pages/previa_totale.py:72-120`.

---

**Próximo passo sugerido:** aprovar a Onda 0 (acesso, dependências, metas e frescor) e
escolher **um** dashboard da Onda 1 para piloto — recomendação: **Sala de Situação**, por
ser o que mais reduz o tempo entre “o número existe” e “a decisão acontece”.
