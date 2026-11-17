# Segurança da sincronização — Absenteísmo e Prévia

## Implementado

- Absenteísmo: substituição de valores via `spreadsheets.batchUpdate` com
  `updateCells`. Não existe mais intervalo entre limpar e escrever. Valores
  excedentes são removidos na mesma operação; formatação é preservada.
- Criação da aba apenas quando o erro é `WorksheetNotFound`, não em falhas
  genéricas de permissão ou de conexão.
- Abas separadas para edição e visualização/exportação do mapa.
- Prévia: leituras remotas estritas e sem cache antes de gravar históricos.
  Falhas de leitura bloqueiam a sincronização, em vez de virarem histórico vazio.
- Preparação de todas as alterações antes do primeiro envio.
- Resultado persistente da última tentativa, com abas gravadas/pendentes e
  invalidação granular de cache após cada gravação bem-sucedida.
- Geração local separada do envio ao Sheets e alerta quando os resultados
  calculados diferem da versão sincronizada.

## Limites e próximos passos

A gravação da prévia ainda não é uma transação entre abas. Uma falha pode gerar
sucesso parcial, agora explicitado. A substituição atômica do absenteísmo
protege contra limpeza sem atualização, mas não é controle de concorrência:
uma sessão desatualizada ainda pode sobrescrever alterações externas.

Não há fila durável de pendências; o fallback continua na sessão. Uma fila
persistente exige armazenamento protegido e política de retenção para dados
pessoais — não gravar esses lançamentos no repositório Git. Auditoria por usuário,
calendário de feriados, correção de células com histórico e integração de
parados entre as telas ficam para uma próxima etapa. Nenhuma autorização de
Drive da conversa é transferida para o aplicativo.

Os testes usam clientes simulados; validar em uma cópia da planilha antes de
implantar. A integração real com Google não foi executada neste ambiente.
