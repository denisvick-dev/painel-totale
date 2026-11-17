# Operação da Lista de Presença

## Preenchimento diário

A tela abre na data atual, quando ela pertence ao mês selecionado. A busca,
a U.N. e o monitor delimitam a equipe. A coluna de situação é editável;
**Não preenchido nunca significa presença**. Há também seleção de dias por
período e um filtro de exibição só de pendentes.

## Ações do dia

- **Preencher em lote**: seleção explícita de logins pendentes, situação,
  responsável informado e confirmação. Não existe seleção automática de todos.
- **Corrigir com histórico**: escolha a marcação e informe responsável e motivo.
  O original é cancelado e permanece auditável. Se ele abrangia vários dias,
  são gerados registros para preservar os dias antes e depois da correção.
- **Status**: diferencia envio em andamento, última confirmação e pendências.
  Lotes e correções sem confirmação não alteram a versão local como se salvos.
- **Concluir chamada**: confirma o recorte diário contra os registros remotos e
  grava data, responsável, horário, totais, logins/U.N./monitor e assinatura
  em `fechamentos_presenca`. Pendências exigem confirmação adicional.
  A chamada fechada não fica bloqueada: mudanças posteriores exigem novo
  fechamento. É possível consultar os fechamentos no Drive pela própria tela.
- **Excel diário**: exporta o recorte de data/U.N./monitor/busca com todas as
  situações e horário de geração. O filtro visual de pendentes não exclui
  técnicos da exportação nem do fechamento.

A aba `fechamentos_presenca` é criada na mesma planilha do controle.
São necessárias credenciais do painel com permissão de edição.
Responsável informado é uma declaração do operador, não uma identidade
verificada por autenticação.

## Concorrência e limites

Antes de cada gravação da página, há leitura autenticada e atualizada do
controle. O merge por ID preserva registros adicionados remotamente e bloqueia
alterações divergentes, colisões de datas e IDs duplicados. Não se interpretam
falhas de leitura como histórico vazio. Uma trava no processo serializa os
envios feitos por esse processo. Os valores são substituídos em uma única
requisição, preservando a formatação.

**Isso é controle otimista, não uma transação distribuída.** O Google Sheets
não oferece compare-and-swap neste fluxo: existe uma janela entre a conferência
e a escrita em processos diferentes ou na edição manual da planilha. Para
exclusão mútua garantida em múltiplas réplicas, é necessário um backend
transacional (por exemplo PostgreSQL), usando Sheets como saída.

Os fechamentos são fotografias auditáveis, não travas nem assinaturas digitais.
O último fechamento mostrado automaticamente fica na sessão; o botão de consulta
recupera os eventos persistidos após reabrir o painel. Uma resposta de rede
incerta durante fechamento pode exigir consultar o histórico antes de repetir.

Pendências individuais continuam apenas na sessão. Não feche a sessão sem
sincronizar ou exportar os dados. Os testes usam clientes simulados; validar
em uma cópia da planilha antes da implantação.
