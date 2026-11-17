# Lista de Presença diretamente na aba absenteismo

A fonte principal da página é agora a grade `absenteismo` da planilha de ativos.
A página não depende de importação nem grava registros em `controle_absenteismo`.
Os serviços antigos de registros continuam no repositório por compatibilidade,
mas não são o caminho de persistência desta página.

## Fonte e semântica

- A equipe da chamada vem das linhas da própria grade. Técnicos que só existem
  em `lista_ativos` não ganham linhas automaticamente. O cadastro segue como
  diagnóstico auxiliar, não como uma segunda lista concorrente.
- Datas numéricas são lidas como seriais para preservar o ano verdadeiro,
  mesmo quando o Sheets mostra apenas `1/nov.`. Cabeçalhos de texto sem ano
  ainda usam a referência padrão do interpretador (ano corrente); recomenda-se
  manter datas reais na planilha, formatadas como dia/mês.
- ATIVO é mostrado como Presente. Novas presenças são gravadas como ATIVO.
- Vazio significa Não preenchido. Tipos reconhecidos mantêm os rótulos do
  aplicativo. Nenhuma célula é preenchida automaticamente como presença.
- DUPLADO e BAIXA DE KIT são preservados e mostrados como situação operacional,
  sem entrar nas contagens de presentes ou ausentes. Outros valores históricos
  também não são regravados se não forem alterados.

## Escrita e auditoria

O painel monta registros virtuais por login/dia apenas para as análises. Para
gravar, calcula a diferença entre a versão carregada e a edição. Faz leitura
remota atualizada, localiza novamente o login e a data e confere o valor da
célula. Grava somente as células alteradas em uma requisição `batchUpdate`.
Não limpa a grade, não altera cadastro, não cria dias/linhas e não substitui
formatação. Células com fórmulas são bloqueadas.

Cada célula alterada gera antes/depois, login, data, horário e motivo em
`auditoria_presenca`, anexados na mesma requisição das alterações. A aba de
auditoria é criada se não existir; um cabeçalho incompatível bloqueia o envio.
A correção por motivo mantém o histórico nessa auditoria, não em linhas
canceladas na grade. O cancelamento limpa a célula e também gera auditoria.

Lotes e correções utilizam esse caminho. O fechamento confere a grade antes
de registrar o retrato em `fechamentos_presenca`. A auditoria pode ser consultada
pela tela. Responsáveis digitados são declaratórios, não identidades verificadas.

## Configuração e limites

São necessários `[gcp_service_account]` nos secrets e permissão de edição da
conta de serviço na planilha. A conexão Drive da conversa não é repassada ao
Streamlit. Se a leitura falhar, a página mostra o erro e interrompe a montagem:
a falha não vira uma lista vazia nem uma confirmação de presença.

Login duplicado, marcação sem login, coluna/data ausente, fórmula ou conflito
bloqueiam a gravação. Linhas vazias sem marcação podem ser ignoradas. Corrigir
um cadastro é feito na planilha. Use Atualizar registros e quadro para reler.

Há trava dentro de um processo e conferência otimista por célula, não uma
transação compare-and-swap entre processos. Alterações simultâneas na mesma
célula depois da última leitura ainda podem competir. A escrita localizada
evita sobrescrever o restante da aba. Para garantia transacional entre réplicas,
é necessário backend com controle de concorrência.

Testes utilizam grade e cliente simulados. Nenhuma gravação foi executada na
planilha real durante a implementação. Validar em uma cópia antes de implantar.
