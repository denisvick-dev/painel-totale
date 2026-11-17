# Changelog — Painel TOTALE

Todas as mudanças relevantes do portal são registradas aqui. O formato segue
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e a versão segue
[SemVer](https://semver.org/lang/pt-BR/). A fonte única da versão publicada é
`config.settings.VERSAO_PORTAL_PADRAO` (ou `TOTALE_VERSAO` em secrets/ambiente);
README, Design System e rodapé leem o mesmo valor.

## [3.8.0] - 2026-11-17

### Adicionado
- Dashboard **Produtividade × Disponibilidade** (`pages/produtividade_disponibilidade.py`):
  O.S. por técnico-dia, disponibilidade, absenteísmo, impacto estimado,
  dispersão, ranking, barras empilhadas, treemap, donut, combinado semanal,
  calendário e exportação agregada por supervisor/base.
- Regra pura do cruzamento em `services/produtividade.py`: quadro por login,
  ausências em pares login × dia, deduplicação por prioridade, séries e avisos
  de qualidade. Testes em `tests/test_produtividade_disponibilidade.py`.
- Faixa global de **frescor e SLO** em todos os dashboards
  (`components/frescor_fontes.py` + `services/frescor.py`), com limites por
  fonte em `config/slo_fontes.py`.

### Alterado
- `render_table_html` agora declara **“Exibindo X de N linhas”** quando corta a
  prévia e exporta o conjunto completo, não apenas as linhas visíveis.
- `max_rows=None` desliga o truncamento para tabelas que precisam do total.
- Versão do portal centralizada em `3.8.0`; Home deixou de hardcodar a versão.
- `abrir_dashboard` aceita `mostrar_frescor=False` para telas que já exibem o
  status completo.

### Corrigido
- Divergência entre `settings` (3.7.0), README e Design System (3.6.0) sobre a
  versão publicada.

## [3.7.0] - 2026-11

### Adicionado
- Navegação declarativa em `config/navegacao.py` (páginas, grupos, ícones,
  descrições e busca sem acento).
- Esqueleto único de dashboard em `components/dashboards.py`
  (`abrir_dashboard` / `secao_exportacao` / `fechar_dashboard`).
- Camada compartilhada `services/dados_sessao.py`, `services/texto.py`,
  `services/planilhas.py` e `services/hierarquia.py`.

### Alterado
- Páginas padronizadas passaram a abrir/fechar pelo mesmo esqueleto e a não
  reimplementar exportação, leitura de upload ou normalização de texto.

## [3.6.0] - 2026-10

### Adicionado
- Cartões de KPI avançados (`components/kpi_cards.py`) com variação, sparkline,
  progresso e temas; substituição de `st.metric`.
- Fábrica de gráficos (`components/graficos.py`) com tema `totale_min`.
- CSS global dos componentes nativos e cache HTTP/Parquet em
  `services/cache_dados.py`.
