# Configurar acesso local à Lista de Presença

`No secrets found` significa que o Streamlit não encontrou a configuração local.
Não é uma confirmação de aba inexistente nem de falha na permissão da planilha.
A conexão Google Drive da conversa não fornece credenciais ao aplicativo local.

## Opção 1 — secrets.toml

No PowerShell, entre na raiz do projeto (`painel-totale`) e execute **apenas se o
arquivo de destino ainda não existir**:

```powershell
Copy-Item .streamlit\secrets.example.toml .streamlit\secrets.toml
```

Edite o arquivo `.streamlit/secrets.toml` localmente. Preencha os campos da seção
`[gcp_service_account]` a partir do JSON da sua conta de serviço Google Cloud.
Não deixe os valores `SUBSTITUA_...` do exemplo nas configurações usadas pelo
seu ambiente. Para esta planilha, configure a chave de nível raiz antes das
seções TOML:

```toml
SHEET_ID_ATIVOS = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
```

O arquivo precisa ser `secrets.toml`, não `secrets.toml.txt`. A pasta é
`.streamlit` dentro do projeto; execute o Streamlit a partir dessa raiz.

## Opção 2 — arquivo JSON fora do repositório

Em vez de adicionar a seção aos secrets, indique o JSON da conta de serviço na
mesma janela PowerShell em que iniciará o aplicativo:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\caminho-seguro\conta-servico.json"
streamlit run streamlit_app.py
```

Use o caminho real do seu arquivo. A variável não cria nem baixa credenciais.
Se houver uma seção `[gcp_service_account]` preenchida, ela tem prioridade.
Não versione o JSON. Não use arquivos de credenciais de OAuth de usuário no
lugar de um JSON de conta de serviço.

## Em ambas as opções

1. Habilite a API Google Sheets no projeto Google Cloud da conta de serviço.
2. Abra a planilha e compartilhe com o endereço `client_email` do JSON como
   **Editor**. Não é necessário torná-la pública.
3. Reinicie o processo Streamlit e abra Lista de Presença.
4. Confirme que a leitura encontra `absenteismo`; valide a primeira escrita
   em uma cópia da planilha antes de trabalhar em produção.

Nunca envie a chave privada por chat, inclua em print ou commit. O arquivo de
secrets já é ignorado pelo Git neste projeto.
