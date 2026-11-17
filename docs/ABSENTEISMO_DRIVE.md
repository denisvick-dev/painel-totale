# Salvamento automático do absenteísmo

Na tela Absenteísmo, ative **Preencher com selectbox**. Ao confirmar uma
seleção de dia (sem botão de envio), o painel tenta gravar na aba
`controle_absenteismo` da planilha configurada por `SHEET_ID_ATIVOS`.
O padrão do projeto é a planilha informada:
`1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg`.

A aba é localizada pelo nome, não pelo `gid` do link. A `lista_ativos` não é
alterada. Se a aba de controle não existir, o serviço tenta criá-la.
O modo de preenchimento não substitui ausências já registradas. Abas no
formato de grade mensal permanecem somente leitura para evitar perda de dados.

## Configuração no ambiente do painel

1. Configure `SHEET_ID_ATIVOS` com o ID acima nos secrets do Streamlit.
2. Configure `[gcp_service_account]` nos secrets, conforme o arquivo de exemplo
   `.streamlit/secrets.example.toml`. Nunca coloque a chave no código ou no chat.
3. Compartilhe a planilha com o `client_email` dessa conta como **Editor**.
4. Habilite a API Google Sheets no projeto da conta de serviço.

A autorização do Google Drive na conversa Arena não é repassada ao aplicativo
Streamlit. O aplicativo usa a sua própria conta de serviço.

## Falha de gravação

O painel não confirma envio quando o Google recusa a gravação. Os lançamentos
ficam apenas na sessão e aparece um alerta. Use **Tentar sincronizar pendências
com o Drive** após corrigir a configuração, ou exporte os registros antes de
fechar a sessão. O fallback de sessão não é uma fila persistente.

## Conferência

Preencha um dia vazio, aguarde a mensagem de sucesso e confira o registro na
aba `controle_absenteismo`. Atualize o painel e confirme que a marca continua
no mapa. Teste também uma falha de permissão: deve aparecer o aviso de sessão,
nunca uma confirmação de salvamento no Drive.
