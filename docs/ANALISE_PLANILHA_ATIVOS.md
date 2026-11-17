# Análise da planilha lista_ativos

Referência: exportações CSV e XLSX consultadas em 17/11/2026 pela conexão
Google Drive. Não foram alterados dados, abas, fórmulas ou permissões no Drive.
As cópias locais da análise ficam em `dados/`, ignorado pelo Git.

## Estrutura identificada

| Aba | Conteúdo observado |
|---|---|
| lista_ativos | Cadastro principal; 339 linhas de dados |
| Página8 | 78 linhas de dados; cabeçalhos Login, RE, Técnico e Monitor |
| desligados | 119 linhas de dados; cadastro, data de desligamento e motivo |
| log_auditoria | 6 linhas de dados; data, usuário, perfil, ação, alvo e detalhe |
| absenteismo | 254 linhas de dados; grade de 30 dias de novembro/2026 |

As contagens consideram linhas com algum valor; não o tamanho formatado da aba.

As abas `controle_absenteismo` e `fechamentos_presenca`, utilizadas pelas novas
rotinas do aplicativo, não aparecem na exportação consultada. Portanto, não
há comprovação de que os envios do aplicativo já estejam funcionando nessa
planilha, nem de que a grade antiga esteja sendo usada pela nova chamada.

## Qualidade do cadastro

- 339 linhas; 338 logins preenchidos e distintos.
- 1 linha sem login: linha 328 da aba principal. Ela é descartada pela
  normalização da lista de ativos, explicando a diferença de totais.
- Nenhum login preenchido duplicado.
- 1 RE aparece em duas linhas: 151 e 152. Os logins são diferentes: não unir
  automaticamente as pessoas e não escolher uma matrícula arbitrariamente.
- Técnico, monitor, U.N., base e situação estão preenchidos nas 339 linhas.
- 17 monitores; 6 U.N.; 6 bases. U.N. e base são campos distintos: os valores
  observados não devem ser trocados nem renomeados automaticamente.
- Situações: 320 ATIVO, 8 AFASTADO, 6 FÉRIAS e 5 INOPERANTE.
- Maior data informada em `Ultima_Modificacao`: 12/11/2026. É um campo
  cadastral, não o horário de edição do arquivo nem a última chamada.

## Histórico em grade

3.185 células preenchidas nas colunas diárias da aba `absenteismo`:

| Valor | Quantidade |
|---|---:|
| ATIVO | 3.005 |
| FALTA | 94 |
| ATESTADO | 47 |
| FOLGA | 26 |
| SUSPENSÃO | 6 |
| DUPLADO | 3 |
| TREINAMENTO | 2 |
| BAIXA DE KIT | 2 |

Essas contagens são marcações por célula, não técnicos únicos. O cadastro tem
mais linhas que a grade: não assumir que ambos cobrem o mesmo quadro.

## Refinamento implementado no painel

Diagnóstico da carga bruta antes da deduplicação e exclusão de linhas, anexado
à lista normalizada e exibido na página de presença. Inclui logins ausentes,
duplicados, RE repetido, campos obrigatórios, situações desconhecidas e datas
inválidas. O diagnóstico informa linhas para revisão sem gravar nomes ou
logins no repositório. Nenhuma correção cadastral é automática.

## Próxima etapa recomendada: migração controlada

1. Validar os valores corretos do login ausente e dos RE das linhas sinalizadas.
2. Confirmar que ATIVO na grade antiga significa Presente naquele dia.
3. Definir tratamento de DUPLADO e BAIXA DE KIT; não mapear silenciosamente
   para falta, presença ou outros. Preservar SUSPENSÃO mesmo não sendo uma
   opção padrão da nova lista.
4. Gerar prévia da conversão em registros, com logins/datas/IDs estáveis e
   relatório de conflitos. Confrontar grade e cadastro sem descartar pessoas.
5. Criar uma cópia de segurança e validar a prévia antes de escrever
   `controle_absenteismo`. Preservar a aba original como histórico.
6. Testar a conta de serviço do aplicativo com uma marcação controlada e
   confirmar leitura após reabrir o painel. A conexão Drive da conversa não
   fornece credenciais automaticamente ao Streamlit.

A migração não foi executada. Não substituir o conteúdo inteiro da planilha
por CSV nem renomear a grade para a aba de registros: isso não converte o
formato e pode destruir histórico.

## Assistente de importação (histórico, removido)

**Fluxo descontinuado:** a página atual lê e grava diretamente na grade
`absenteismo`, sem copiar os dados para `controle_absenteismo`. Os módulos
órfãos do assistente e seus testes exclusivos foram removidos. As proteções
de conflito, fórmulas e auditoria são mantidas em `services/presenca_grade.py`.
Consulte `PRESENCA_GRADE_DIRETA.md` para o fluxo vigente.

Na implementação anterior, a página oferecia **Criar Lista de Presença a partir da aba absenteismo**.
O botão de leitura usa a conta de serviço do aplicativo, não as credenciais da
conversa. O operador confirma a referência dos cabeçalhos abreviados, escolhe o
tratamento de códigos desconhecidos, revisa as linhas e informa o responsável.
É possível decidir explicitamente manter um código pendente, sem importar a
célula; essa decisão e a contagem são mostradas antes da confirmação.

A origem é relida antes da confirmação. Mudanças desde a prévia bloqueiam o
processo. IDs determinísticos por login/dia impedem repetir a mesma importação;
registros cancelados não são reativados. Mudanças de tipo em IDs já importados
exigem correção com histórico. O salvamento usa a conferência otimista existente
e não substitui marcações remotas sobrepostas silenciosamente.

Validação na cópia exportada: 3.180 registros reconhecidos, sendo 3.005 Presente,
94 Falta, 47 Atestado, 26 Folga, 6 Suspensão e 2 Treinamento. Cinco células
permanecem para decisão: DUPLADO (3), BAIXA DE KIT (2). Nenhuma importação foi
confirmada no Google Sheets nesta implementação.
