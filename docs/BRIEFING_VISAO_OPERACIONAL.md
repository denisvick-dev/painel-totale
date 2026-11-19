# Briefing — Painel Produtividade · Contratos & Consultivos

Página: `pages/visao_operacional.py` · Grupo: Performance · Ícone: 🧾
(Histórico: anteriormente publicada como `pages/produtividade_disponibilidade.py`.)

## Em uma frase
Um painel único que coloca lado a lado a **produção (O.S.)**, os **contratos de
clientes atendidos** e os **consultivos/produtos comerciais**, cruzados pelas
dimensões operacionais comuns — **projeto** e **supervisor/monitor** — e pelo
**tempo**, para enxergar volume, cobertura e desempenho comercial na mesma tela.

## Por que existe
Produção e comercial viviam em abas e painéis separados (`dados_prod` e
`dados_cons`). Para responder "onde estamos entregando mais e vendendo mais?"
era preciso juntar tudo à mão. Este painel consolida as três lentes em um recorte
único de período/projeto/supervisor, mantendo cada fonte com sua regra própria e
deixando explícito o que é comparável e o que não é.

## Público-alvo
Coordenação e supervisão operacional, gestão de performance e diretoria — qualquer
perfil que precise acompanhar volume de O.S., carteira atendida e resultado de
consultivos sem trocar de aba.

## Fontes de dados
| Fonte | Chave de sessão | Origem | Uso no painel |
|---|---|---|---|
| Produção | `dados_prod` | Atualização de Dados / upload | O.S., contratos, pontos, projeto, equipe |
| Consultivos | `dados_cons` (aba `Consultivo`) | Atualização de Dados | Consultivos, produtos e mix (Mesh/TV/Virtua) |
| Hierarquia | `lista_ativos` (Drive) | Cache compartilhado | Herdar Monitor/Base dos consultivos (opcional) |

- A produção é **obrigatória**: sem ela o painel para com o aviso oficial de carga.
- Os consultivos são **opcionais**: se não houver `dados_cons`, as visões de O.S.
  e contratos seguem funcionando e o painel avisa que as seções comerciais estão
  desabilitadas.
- Falha de acesso à hierarquia remota **não derruba** a página; consultivos apenas
  ficam sem Monitor/Base enriquecidos.

## Como as fontes se cruzam
Não há chave única entre produção e consultivos. O casamento é feito por:
1. **Projeto** e **Supervisor/Monitor** — rótulos normalizados (caixa alta, sem acento),
   de modo que `GRS-TOTALE` e `grs totale` apontem para a mesma linha;
2. **Tempo** — séries alinhadas por semana (segunda-feira) e pelo filtro de período.

Os consultivos não trazem projeto próprio: o projeto deles é derivado do supervisor
(projeto modal daquele supervisor na produção). É uma relação derivada e documentada,
não uma chave nativa da base comercial. Valores presentes em apenas uma das fontes
aparecem com zero na outra (junção externa). Nada é inventado para preencher lacuna.

## Métricas e regras de cálculo
### Produção / Contratos (regra em `services/produtividade_contratos.py`)
- **O.S.**: cada linha da carga de produção conta como uma O.S.; duplicações da
  origem não são removidas.
- **Contratos atendidos**: identificadores de contrato **distintos** e válidos no
  recorte; vazios/inválidos são excluídos. Sem coluna de contrato reconhecida, o
  indicador fica indisponível (O.S. não é usada como substituto).
- **Cobertura de contrato**: % das O.S. que têm identificador de contrato válido.
- **Pontos**: soma dos pontos informados na produção (conferir cobertura da origem).
- Distribuição de contratos por nº de O.S.: frequência de quantas O.S. cada contrato
  recebeu. **Contratos distintos não são somáveis** entre grupos/períodos (o mesmo
  contrato pode aparecer em vários).

### Consultivos (base `dados_cons`)
- **Consultivos / Produtos**: somas de `QTDE_CONSULTIVO` e `QTDE_PRODUTOS`.
- **Mix de produtos**: somas independentes de Mesh, TV e Virtua (não compõem o total
  de produtos automaticamente).
- **Equipes com consultivo**: logins distintos com ao menos 1 consultivo.
- **Conversão de equipes**: equipes com consultivo ÷ equipes com login identificado.
- **% de Consultivos na Produção**: relação agregada consultivos ÷ O.S. do recorte
  (também por projeto/supervisor na coluna `Cons./O.S. (%)`). Não é uma taxa por O.S.
  individual — não existe chave única ligando cada atendimento à sua venda.

## Estrutura do painel
**Filtros (sidebar):** período (início/fim, padrão últimos 30 dias), Projeto e
Supervisor/Monitor (valem para as duas fontes; o projeto dos consultivos é derivado
do supervisor) e Equipe (filtra só a produção).

| Seção | O que entrega |
|---|---|
| 🎯 Indicadores | KPIs de produção (O.S., contratos, cobertura, pontos) e, quando há consultivos, KPIs comerciais (consultivos, produtos, equipes com consultivo, conversão) |
| 📈 Evolução semanal | Linhas por semana: O.S. × contratos e consultivos × produtos, lado a lado |
| 🧭 Visão por projeto e supervisor | Tabela consolidada casando as três lentes + gráfico Top 20 O.S. × Consultivos |
| 📋 Perfil dos contratos | O.S. por contrato identificado e distribuição de frequência |
| 📞 Consultivos e mix de produtos | Donut do mix (Mesh/TV/Virtua) e Top 15 supervisores em consultivos |
| 📤 Exportação | Resumo consolidado por projeto/supervisor em XLSX |

## Perguntas que o painel responde
- Qual o volume de O.S. e a carteira de contratos no período, por projeto/supervisor?
- Quão completa está a identificação de contratos (cobertura)?
- Onde a operação entrega O.S. e também gera consultivos/produtos?
- Como evoluem, semana a semana, produção e resultado comercial?
- Qual o mix de produtos vendidos e quem lidera consultivos?

## Premissas e limitações (lidas junto com os números)
- **Sem chave única**: o cruzamento por projeto/supervisor aproxima equipes; não prova
  causalidade entre produção e venda.
- **Contratos não somáveis**: totais de contratos distintos entre grupos/semanas
  superestimam se somados diretamente.
- **Retrato atual**: base/monitor vêm do cadastro vigente; recortes antigos usam a
  hierarquia de hoje (limitação herdada do portal).
- **Produção sem data**: se a carga não traz data reconhecida, o período não filtra
  as O.S. (aviso exibido); o total mostrado é o da carga inteira.
- **Estimativas de conversão/mix** refletem o que foi registrado; ausência de
  registro não significa ausência de atividade.

## Manutenção e governança
- Regra de negócio pura e testada: `services/produtividade_contratos.py`.
- Camada de sessão padronizada: `services/dados_sessao.py` (`exigir_base`/`obter_base`).
- Testes: `tests/test_produtividade_contratos.py` (inclui execução da página via
  `streamlit.testing.v1.AppTest`) e guarda de padrão em
  `tests/test_organizacao_dashboards.py`.
- A análise avançada de **retornos/reincidência (TOA)** deixou esta página na
  reformulação; sua lógica permanece intacta e testada em
  `services/produtividade_contratos.py` (`preparar_retornos`/`analisar_retornos`).
