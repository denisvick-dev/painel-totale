# Presença: grade de análise e chamada na planilha externa

O painel mantém duas frentes complementares:

- **Análises e histórico** usam a grade `absenteismo` da planilha de ativos.
- **Preencher presença do dia** usa a planilha externa `lista_de_presenca`, que
  é também a origem do Painel executivo. Nenhuma linha é criada nas duas
  planilhas pelo aplicativo.

## Fonte da chamada

- A equipe vem das linhas da planilha `lista_de_presenca` (`RE`, `Login`,
  `Técnico`, `Monitor`, `U.N.` e `Base`). Técnicos presentes apenas em
  `lista_ativos` ou na grade `absenteismo` não aparecem nessa chamada.
- As colunas diárias da planilha (por exemplo, `1/nov.`) definem as datas
  disponíveis. O seletor usa o ano da data de referência e ajusta planilhas que
  atravessam a virada do ano.
- A tabela da chamada segue o leiaute compacto `RE`, `Login`, `Técnico`,
  `Monitor` e `Status`. Em branco é pendência; nunca é presença presumida.
- ATIVO é a confirmação de presença. FALTA, ATESTADO, FOLGA, FÉRIAS, LICENÇA,
  TREINAMENTO, SUSPENSÃO, BAIXA DE KIT e AFASTADO são as demais situações
  oferecidas. Valores históricos fora dessa lista são preservados enquanto
  não forem alterados.
- Os filtros de unidade, monitor e busca da chamada são combinados com os
  filtros da lateral. A visualização por período mostra uma coluna de situação
  por dia selecionado.

## Escrita e auditoria

A gravação acontece somente nas células alteradas da planilha
`lista_de_presenca`:

1. o painel relê a planilha remota antes de escrever;
2. confirma que o login e a coluna do dia ainda existem e que a célula não mudou
   desde a leitura;
3. envia um `batchUpdate` com as posições alteradas, sem tocar em cadastros,
   fórmulas ou formatação;
4. recarrega a página com o resultado confirmado.

Conflito, login duplicado, login ausente, coluna de dia inexistente ou valor
fora das opções bloqueiam o envio. A conta de serviço precisa ter permissão de
edição na planilha `lista_de_presenca`. A conexão Drive da conversa não é
repassada ao Streamlit.

As operações de lote, correção com histórico, fechamento e auditoria continuam
associadas à grade `absenteismo` e seguem valendo para as análises. A chamada
diária não mistura esses fluxos: ela grava direto na planilha externa.

## Configuração

`SHEET_ID_PRESENCA` (variável de ambiente ou entrada em `secrets.toml`)
identifica a planilha externa. `[gcp_service_account]` ou
`GOOGLE_APPLICATION_CREDENTIALS` fornece a credencial de leitura e escrita. Use
**Atualizar registros e quadro** para reler as fontes depois de alterações
manuais.

Testes utilizam planilha e cliente simulados. Nenhuma gravação foi executada na
planilha real durante a implementação. Validar em uma cópia antes de implantar.
