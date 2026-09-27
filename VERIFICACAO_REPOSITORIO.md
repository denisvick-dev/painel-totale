# 🔎 Verificação Completa do Repositório — Painel TOTALE

**Data:** 27/09/2026
**Commit verificado:** `824ee88` (base `main`)
**Branch desta verificação:** `arena/01a0e4b8-painel-totale`
**Ambiente de teste:** Python 3.11.2 · Streamlit 1.64.0 · pandas 3.0.6 · numpy 2.4.6 · Plotly 7.1.0 (instalação limpa a partir do `requirements.txt`)

---

## 1. Sumário Executivo

| Área | Situação |
|---|---|
| Estrutura do projeto | ⚠️ OK, com 2 módulos órfãos e 1/3 do código em `old/` (morto) |
| Sintaxe / importabilidade | ❌ **1 arquivo não compilava** (bloqueava 2 páginas do menu) |
| Boot da aplicação | ✅ Sobe normalmente (Streamlit 1.64, porta 8501, health `ok`) |
| Execução das 17 páginas | ⚠️ 2 falhavam por erro fatal; 2 falham sem `secrets.toml` |
| Autenticação / Segurança | ❌ Credenciais fixas no código, sem auth no app principal, senha em texto plano suportada |
| Integridade de dados | ❌ Gravação destrutiva (`ws.clear()` + `update`) sem backup/confirmação |
| Dependências | ⚠️ 2 libs usadas e não declaradas; 9 declaradas e nunca usadas; nenhum pin de versão |
| Testes / CI / Lint | ❌ Inexistentes (0 testes, 0 workflows) |
| Documentação | ⚠️ README desatualizado (5 caminhos citados que não existem) |

### 🔧 Correção aplicada nesta verificação

Um **bloqueador fatal** foi corrigido em `pages/quebra_geral.py` (detalhes na seção 3.1).
Fora isso, **nenhum outro arquivo foi alterado** — os demais achados estão documentados aqui para decisão.

---

## 2. Método da Verificação

Tudo abaixo é reproduzível. O que foi executado:

```bash
# 1. Ambiente isolado + dependências declaradas
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. Compilação de todos os módulos (AST real do CPython 3.11)
python3 -m compileall -q .            # -> SyntaxError em pages/quebra_geral.py

# 3. Análise estática (pyflakes + ruff, várias regras, target py311)
.venv/bin/python -m pyflakes pages/*.py components/*.py robo/*.py streamlit_app.py
.venv/bin/python -m ruff check --target-version py311 --exclude old,.venv \
    --select F,E,W,B,C4,UP,SIM,PIE,RET,ARG,PL,RUF,DTZ pages components robo streamlit_app.py

# 4. Execução real de cada uma das 17 páginas + app principal
#    (harness oficial streamlit.testing.v1.AppTest)

# 5. Boot do servidor real e checagem de endpoints
.venv/bin/streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
curl -s http://localhost:8501/_stcore/health    # -> "ok"

# 6. Auditoria de dependências (AST x importlib.metadata.packages_distributions x requirements.txt)
# 7. Auditoria de segurança (segredos, credenciais, escaping de HTML, escaping de fórmulas)
```

---

## 3. Achados por Severidade

### 🔴 P0 — Bloqueadores (impedem o uso)

#### 3.1 `pages/quebra_geral.py` não compilava em Python < 3.12 — ✅ CORRIGIDO

O arquivo usava **f-strings com aspas duplas aninhadas dentro de aspas duplas**, sintaxe
permitida apenas a partir do **Python 3.12 (PEP 701)**. Como o projeto declara Python 3.11+
(o `devcontainer.json` usa 3.11) e o Streamlit Cloud roda 3.11 por padrão, o arquivo era
**inválido em produção**.

```python
# Linha 1712 (antes) — SyntaxError em Python 3.11
html += f"<tr {"class='total-row'" if is_total else ''}>"

# Linha 1735 (antes) — SyntaxError em Python 3.11
html += f"<td>{_html(valor) if not _is_missing_scalar(valor) else "<span style='color:#94A3B8;'>—</span>"}</td>"
```

**Impacto:** derrubava **duas entradas de menu**:
- `Quebra → Geral` (`pages/quebra_geral.py`)
- `Quebra → Visão Segmentos` (`pages/quebra_unificada.py`, que faz `from pages.quebra_geral import Config, Motor, Utils`)

```text
SyntaxError: invalid character '—' (U+2014)
  File "pages/quebra_geral.py", line 1735
```

**Correção aplicada** (mínima, sem mudança de comportamento; a saída HTML gerada é idêntica à pretendida):

```python
# Linha 1712 (depois)
classe_linha = " class='total-row'" if is_total else ""
html += f"<tr{classe_linha}>"

# Linha 1735 (depois)
vazio = "<span style='color:#94A3B8;'>—</span>"
html += f"<td>{_html(valor) if not _is_missing_scalar(valor) else vazio}</td>"
```

**Validação após a correção:**

| Verificação | Resultado |
|---|---|
| `ast.parse()` / `compileall` (py3.11) | ✅ sem erros |
| `ruff --target-version py311 --select E9` | ✅ `All checks passed!` |
| `AppTest` em `pages/quebra_geral.py` | ✅ executa sem exceção |
| `AppTest` em `pages/quebra_unificada.py` | ✅ executa sem exceção |
| Teste unitário do HTML gerado | ✅ linha `TOTAL GERAL` recebe `class='total-row'`, dados continuam escapados, placeholder `—` presente, 3 `<tr>` (1 thead + 2 linhas) |

> ℹ️ **Atenção:** existe o **PR #1 aberto** (`devin/1789755684-refatora-quebra-geral`) que
> reescreve este mesmo arquivo (+1052/−1704). Verifiquei o conteúdo daquele branch:
> ele **também corrige** este erro (`quebra_geral.py` de 1998 linhas, parse OK).
> Se preferir resolver por lá, reverta esta alteração local antes do merge para evitar conflito.

#### 3.2 `pages/dashboard_meta.py` quebra sem `secrets.toml`

```python
158: @dataclass
159: class Configuracoes:
160:     URL_ATIVOS: str = field(
161:         default_factory=lambda: st.secrets.get("URL_ATIVOS", "https://docs.google.com/...")
```

`st.secrets.get()` **levanta `StreamlitSecretNotFoundError`** quando não existe arquivo de segredos —
e aqui ele é avaliado durante a construção do dataclass, **fora de qualquer `try/except`**.

```text
Exception: No secrets found. Valid paths for a secrets.toml file or secret directories are:
  ~/.streamlit/secrets.toml, /home/user/painel-totale/.streamlit/secrets.toml
```

**Impacto:** a página `Metas Operacionais` não abre (erro em tela cheia) sempre que o
`secrets.toml` estiver ausente ou malformado — inclusive localmente e em forks do repositório.
**Correção sugerida:** envolver os `default_factory` em try/except (ou usar um helper
`_secret(key, default)`) e cair no valor padrão.

---

### 🟠 P1 — Segurança

#### 3.3 Credencial de administrador fixa no código (e pública)

```python
# pages/gestao_ativos.py:256-262
@staticmethod
def usuarios() -> dict[str, dict]:
    base = {
        "denisvick": {
            "senha": "admin123",     # <-- usuário admin com senha fixa, versionada no Git
            "nome": "Denis Vick",
            "role": "admin",
            "bases": [],
        }
    }
```

Como a senha é mesclada com os usuários do `secrets.toml`, **uma conta admin com senha
conhecida existe sempre**, mesmo em produção. **Ação:** remover o usuário semente do código
e migrá-lo para `secrets.toml` (ou para a planilha de usuários, com hash).

#### 3.4 O app principal (`streamlit_app.py`) não tem autenticação

O README afirma *"Autenticação por usuário e senha / Perfis de acesso: Admin, Supervisor,
Operador, Leitura"*, mas o roteador não faz nenhum gate de sessão:

```python
# streamlit_app.py — main()
GerenciadorNavegacao.renderizar_sidebar_corporativa()
paginas = GerenciadorNavegacao._definir_paginas()
pg = st.navigation(paginas)
pg.run()          # nenhuma checagem de st.session_state/autenticacao
```

Somente `pages/gestao_ativos.py` tem tela de login própria (e isolada). **Todas as outras 15
páginas são abertas a qualquer pessoa com a URL.**

> 📌 **Decisão registrada em 27/09/2026:** o projeto optou por **manter** esse desenho —
> o login existe apenas em `pages/gestao_ativos.py` (a única página que grava na
> planilha) e as páginas de leitura seguem abertas. Um guard central chegou a ser
> implementado e foi revertido a pedido do responsável. Reforçado por teste
> (`tests/test_gestao_ativos_auth.py::test_login_e_senha_apenas_em_gestao_ativos`),
> que falha se alguém reintroduzir autenticação em outro módulo.

#### 3.5 `pages/login.py`: senha em texto plano aceita + cadastro aberto (código órfão)

```python
# pages/gestao_ativos.py:116-123
if len(a) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in a):
    return hmac.compare_digest(_hash_senha(d), a.lower())
return hmac.compare_digest(d, a)    # <-- aceita senha em claro (fallback)
```

- O fallback comparando **texto plano** anula a proteção de hash (aceita qualquer senha gravada
  em claro na planilha).
- `pages/login.py` usa **SHA-256 sem salt** (vulnerável a rainbow tables) e oferece uma aba
  **"Criar Nova Conta" sem aprovação**, gravando em `usuarios.db` no diretório de trabalho.
- Esse módulo **não é alcançável** (ver 4.1), ou seja: é superfície de ataque morta, mas que
  será reativada se alguém "consertar" a navegação.

**Comprovado na prática durante esta verificação:** o simples `AppTest` sobre `pages/login.py`
criou o arquivo no diretório de trabalho e semeou a conta padrão:

```text
usuarios.db criado (12 KB)  ->  tabela usuarios
admin | 240be518fabd2724...   = sha256("admin123")   <- hash SEM salt, quebrável por rainbow table
```

**Ação:** remover o fallback de texto plano, migrar para `hashlib.scrypt`/`bcrypt` com salt,
eliminar o auto-cadastro e apagar/arquivar `pages/login.py`.

#### 3.6 `usuarios.db` não está no `.gitignore`

`pages/login.py` cria `usuarios.db` no cwd. O `.gitignore` só cobre `db.sqlite3`:

```bash
$ git check-ignore -v usuarios.db
  -> (nada) => NÃO ignorado: risco de commitar o banco de usuários
```

---

### 🟠 P1 — Integridade e perda de dados

#### 3.7 Gravação destrutiva no Google Sheets sem backup nem confirmação

```python
# pages/gestao_ativos.py — _gravar_gspread()
ws.clear()                     # apaga a aba inteira
try:
    ws.update(range_name=..., values=dados, value_input_option="USER_ENTERED")
except TypeError:              # fallback de assinatura da API
    ws.update(f"A1:...", dados, value_input_option="USER_ENTERED")
```

O `clear()` acontece **antes** do `update()`. Qualquer falha entre as duas chamadas
(rate-limit 429, timeout, queda de rede, exceção de validação) deixa a aba **vazia** — sem
rollback, sem snapshot, sem diálogo de confirmação e sem autenticação na frente (ver 3.4).

**Ação:** gravar em aba temporária + trocar, ou usar `batch_update` (não destrutivo),
+ `st.dialog` de confirmação e log de auditoria antes de qualquer escrita.

#### 3.8 CSV/Excel exportado — risco de formula injection

Há *n* exports (`st.download_button`/OpenPyXL) alimentados por dados de planilha.
Valores iniciados por `=`, `+`, `-`, `@` não são neutralizados antes da exportação para CSV
(o `openpyxl` escrevendo em `.xlsx` só vira fórmula se o valor *for* fórmula, então o risco é
maior no caminho CSV). **Ação:** prefixar com `'` ou forçar `str()` nos campos exportados.

#### 3.9 `st.cache_data` sobre dados sensíveis/filtrados

`pages/gestao_ativos.py` cacheia o resultado de `_fetch` (`@st.cache_data(ttl=300)`), e
`st.cache_data` é **global por processo**, não por sessão. Se o filtro por base/perfil passar a
ser aplicado dentro da função cacheada, um usuário pode ver dados de outro. Hoje o filtro é
aplicado fora (ok), mas o padrão é frágil para o modelo multi-perfil prometido no README.

---

### 🟡 P2 — Robustez e qualidade de código

#### 3.10 Tratamento de exceções excessivamente amplo

- **30** blocos `except ...: pass` puros engolindo falhas silenciosamente
  (`gestao_ativos.py`, `indicadores.py`, `pontos.py`, `consultivo.py`, `qtde_os.py`, `envio_excel.py`…).
- **1** `except:` puro (bare except) — `pages/p_atendimento.py:869`, que captura até `KeyboardInterrupt`.
- O decorator `handle_exceptions` em `streamlit_app.py` exibe a mensagem crua da exceção
  ao usuário final (`st.error(f"Ocorreu um erro inesperado: {e!s}")`) — vaza caminhos internos.

#### 3.11 Concorrência entre arquivos: `robo` e `pages` divergentes

- `robo/robo_engine.py` e `robo/robo_local.py` foram alterados no commit base junto com
  `components/componentes.py` e `pages/envio_excel.py`, mas o `robo/main.py` é um **script solto**
  (`st.title(...)` no topo, fora de `main()`), que não é importável por nenhuma página.
- `robo_local.py:868` usa `getattr(objeto, "atributo_constante")` (B009) — não protege nada.

#### 3.12 Dependências (auditoria via AST × `importlib.metadata`)

**Usadas mas NÃO declaradas** (hoje funcionam só por serem transitivas — quebram se o
Streamlit/Google mudar a árvore):

| Módulo | Pacote | Usado em |
|---|---|---|
| `requests` | `requests` | `pages/dashboard_meta.py`, `pages/envio_excel.py`, `pages/indicadores.py` |
| `urllib3` | `urllib3` | `pages/envio_excel.py` |

**Declaradas e nunca usadas** (peso de build/instalação e superfície de CVE à toa):
`chardet`, `pytz`, `duckdb`, `matplotlib`, `pydeck`, `fastapi`, `starlette`, `streamlit-autorefresh`,
`streamlit-carousel`, `gspread-pandas`, `gspread-formatting`, `gspread-dataframe`.

> `fastapi` + `starlette<1.4.0` são especialmente estranhos num app Streamlit puro — parece
> sobra de um experimento. O pin `starlette<1.4.0` é frágil/inespecífico.

**Nenhum pin de versão.** Instalação limpa hoje trouxe **pandas 3.0.6 / numpy 2.4.6 / Plotly 7.1.0** —
três majors lançados depois que o código foi escrito. O app subiu, mas não há garantia de
reprodutibilidade entre ambientes (Streamlit Cloud x devcontainer x máquina local).
**Ação:** fixar versões (`pip-compile` / `requirements.lock`) e declarar `runtime.txt`.

#### 3.13 `streamlit/carousel`, `autorefresh` e outras libs não usadas vs. solução caseira

`streamlit_app.py` implementa refresh manual com `time.time()` + `st.rerun()`
(`INTERVALO_REFRESH = 60`) enquanto a dependência `streamlit-autorefresh` está instalada e ociosa.
O `st.rerun()` a cada 60 s no Home descarta estado de UI sem necessidade.

#### 3.14 Funções gigantes (inviável manter / testar)

| Arquivo | Função | Tamanho |
|---|---|---|
| `pages/rota_inicial.py:1303` | `main` | **1053 linhas** |
| `pages/p_atendimento.py:876` | `main` | **618 linhas** |
| `pages/volumetria.py:1414` | `main` | **488 linhas** |
| `pages/indicadores.py:1319` | `renderizar_visao_executiva_geral` | 348 linhas |
| `pages/indicadores.py:1671` | `render_painel_executivo_aba` | 290 linhas |
| `pages/rota_geral.py:730` | `_injetar_css` | 261 linhas |
| `pages/quebra_unificada.py:1833` | `main` | 250 linhas |

#### 3.15 Depreciações do Streamlit (avisos reais no boot)

```text
Please replace `st.components.v1.html` with `st.iframe`.
`st.components.v1.html` will be removed after 2026-06-01.
```

Ou seja: **já passou da data de remoção** anunciada. As **4 chamadas** reais (`components/componentes.py` ×3,
`pages/pontos.py` ×1) passam a **avisar em log a cada render** e quebram numa atualização futura.

#### 3.16 `st.set_page_config()` duplicado

`streamlit_app.py` chama `set_page_config` no `main()` e **11 páginas chamam de novo**.
Hoje (Streamlit 1.64) a segunda chamada é ignorada silenciosamente — mas você perde o
`page_title`/favicon definidos no entrypoint e fica dependente de um comportamento não
documentado. Boa prática: manter apenas no entrypoint.

#### 3.17 `page_icon` apontando para arquivo inexistente

```python
# streamlit_app.py
ICON_PATH: str = "assets/images/icons/totale.ico"
```

O arquivo real está em **`assets/icons/totale.ico`** (`assets/images/icons/` não existe).
O Streamlit **não levanta erro e não loga nada** — o favicon simplesmente não é aplicado.
Verifiquei todos os caminhos de asset: só esse está quebrado.

#### 3.18 Binário de cache versionado + desserialização insegura

`.streamlit_cache/geo_sp_2022.pkl` (40 KB) está **commitado** e é lido com `pickle.load()`
(`pages/rota_inicial.py:978`). `pickle` executa código arbitrário na desserialização — se o
arquivo for alterado, é RCE no servidor. **Ação:** remover do Git, adicionar `.streamlit_cache/`
ao `.gitignore`, e trocar `pickle` por `parquet`/`geopandas` (`to_file/read_file`).

#### 3.19 `runpy`/import de página por caminho

`pages/quebra_unificada.py:57` faz `from pages.quebra_geral import Config, Motor, Utils`.
Isso acopla duas páginas que o `st.navigation` executa como scripts independentes:
qualquer `set_page_config`/efeito colateral do módulo importado roda duas vezes, e o
arquivo "quebra_unificada" herda toda a base de "quebra_geral" (2.400 linhas) só para usar 3 classes.

---

### 🟢 P3 — Higiene do repositório e documentação

#### 3.20 Código morto: `old/` = 13.590 linhas (1/3 do projeto)

`old/` contém 13 arquivos (incluindo `jogodavelha.py`, `convert_toml.py`) que **duplicam**
as versões ativas:

| Antigo (morto) | Ativo |
|---|---|
| `old/quebra.py` (2.617 linhas) | `pages/quebra_geral.py` (2.436) |
| `old/quebra_aux.py` (1.650) | `pages/quebra_unificada.py` (2.087) |
| `old/rotainicial_aux.py` (639) | `pages/rota_inicial.py` (2.360) |
| `old/gestaoativos_aux.py` (688) | `pages/gestao_ativos.py` (751) |

Como o `st.navigation` **ignora o diretório `pages/`**, dois módulos são inalcançáveis:

- **`pages/home.py`** (319 linhas) — nunca é renderizado (a Home real é `pagina_home()` em `streamlit_app.py`);
- **`pages/login.py`** (175 linhas) — o sistema de login paralelo descrito em 3.5.

```text
docstring oficial do st.navigation:
"As soon as any session of your app executes the st.navigation command,
 your app will ignore the pages/ directory (across all sessions)."
```

**Ação:** mover `old/` e os 2 órfãos para um branch/tag histórico e apagar do `main`.

#### 3.21 README desatualizado — 5 caminhos citados não existem

| Caminho no README | Realidade |
|---|---|
| `.streamlit/config.toml` | ❌ não existe (`cp .streamlit/secrets.example.toml ...` **falha**) |
| `.streamlit/secrets.example.toml` | ❌ não existe — o passo 4 do "Instalação Local" é impossível |
| `componentes.py` (raiz) | ❌ é `components/componentes.py` |
| `pages/gerador_assinatura.py` | ❌ é `pages/assinatura.py` |
| `docs/screenshots/*.png` | ❌ diretório `docs/` não existe (3 screenshots "quebrados" no README) |

Outras divergências:
- README diz **"Deploy no Streamlit Cloud"** e aponta `painel-totale.streamlit.app`; não há
  `runtime.txt`/`.python-version` fixando o Python — e é justamente aí que o erro do item 3.1 morde.
- LICENSE é **Apache 2.0**, mas o badge do README diz **"Proprietary"**. Escolha um.
- `.github/CODEOWNERS` aponta para `@streamlit/community-cloud` (resquício do template).
- Roadmap diz "Integração Google Sheets ✅" mas **o `secrets.toml` de exemplo não existe**, então
  ninguém consegue reproduzir a integração.

#### 3.22 Sem testes, sem CI, sem lint configurado

- **0** arquivos de teste (`pytest.ini`, `tests/`, `test_*.py`: nenhum).
- **0** workflows (`.github/` só tem `CODEOWNERS`).
- Sem `pyproject.toml` / `ruff.toml` / `.pre-commit-config.yaml` / `setup.cfg` — nenhuma regra
  de estilo é aplicada, o que explica as inconsistências (ver 3.23).
- `.vscode/settings.json` desliga a análise de tipo exatamente para `pandas`, `numpy`, `gdown` —
  as três libs onde os erros de runtime mais aparecem.

#### 3.23 Volume de alertas de análise estática

```text
ruff (target py311, regras F,E,W,B,C4,UP,SIM,PIE,RET,ARG,RUF,PL,DTZ, sem E501):
  Found 349 errors  (142 corrigíveis automaticamente)
```

Sem contar `E501` (linha longa), que sozinho soma **529** ocorrências. Nada disso é fatal,
mas indica ausência total de gate de qualidade. Nota positiva: **não há imports não usados
relevantes** (2 no total) nem variáveis órfãs — a base está bem cuidada nesse aspecto.

#### 3.24 Duplicação de CSS/estilo entre páginas

7 páginas injetam blocos próprios de `<style>` (`pages/home.py`, `pages/quebra_unificada.py`,
`pages/rota_geral.py` com `_injetar_css` de 261 linhas, …) além de `components/componentes.py`
(2.318 linhas) e do `GerenciadorEstilos` de `streamlit_app.py`. O próprio
`streamlit_app.py` já registra a regra "não duplicar `[data-testid="stSidebar"]`" — sinal de
que o problema já causou conflito antes.

---

## 4. Inventário do Repositório

### 4.1 Mapa de páginas x navegação

| Página registrada em `st.navigation` | Arquivo | Estado |
|---|---|---|
| Home | `pagina_home()` (em `streamlit_app.py`) | ✅ |
| Atualização de Dados | `pages/envio_excel.py` | ✅ |
| Produção Mensal | `pages/pontos.py` | ✅ |
| Quantidade de O.S. | `pages/qtde_os.py` | ✅ |
| Consultivos | `pages/consultivo.py` | ✅ |
| Metas Operacionais | `pages/dashboard_meta.py` | ⚠️ quebra sem `secrets.toml` (3.2) |
| Indicadores | `pages/indicadores.py` | ✅ (depende de download externo) |
| Gestão de Ativos | `pages/gestao_ativos.py` | ⚠️ credencial fixa (3.3) / escrita destrutiva (3.7) |
| Rota Inicial | `pages/rota_inicial.py` | ✅ |
| Rota Geral | `pages/rota_geral.py` | ✅ |
| Volumetria | `pages/volumetria.py` | ⚠️ exige pasta local (`Pasta não existe`) |
| Retornos | `pages/retorno.py` | ✅ |
| 1º Atendimento | `pages/p_atendimento.py` | ✅ |
| Quebra → Geral | `pages/quebra_geral.py` | ❌→✅ **corrigido nesta verificação** |
| Quebra → Visão Segmentos | `pages/quebra_unificada.py` | ❌→✅ (dependia do item acima) |
| Assinatura | `pages/assinatura.py` | ✅ |
| *(fora do menu)* | `pages/home.py` | 🗑️ código morto |
| *(fora do menu)* | `pages/login.py` | 🗑️ código morto + auth fraca |

### 4.2 Métricas

| Métrica | Valor |
|---|---|
| Arquivos rastreados pelo Git | 62 |
| Linhas Python (total) | 40.922 |
| `pages/` | 22.018 linhas (17 arquivos) |
| `old/` (morto) | 13.590 linhas |
| `components/` | 2.952 linhas |
| `robo/` | 1.806 linhas |
| `streamlit_app.py` | 552 linhas |
| Tamanho (sem `.git`) | 4,6 MB |
| Testes | 0 |
| Workflows/CI | 0 |
| Histórico Git | 1 commit (`824ee88`) |

### 4.3 Pontos fortes encontrados

Vale registrar o que está bem feito — não é só problema:

- ✅ **Escaping de HTML**: `_html()` em `quebra_geral.py`, `Validadores.html_escape()` em
  `componentes.py`, `escape()` em `quebra_unificada.py` e `.replace("&","&amp;")` em `consultivo.py`
  mostram que a injeção via planilha foi tratada na maior parte dos caminhos.
- ✅ **Comparação de senha em tempo constante** com `hmac.compare_digest` (não `==`).
- ✅ **Fallbacks em cascata documentados** para `st.connection("gsheets")` → HTTP público
  (`dashboard_meta.py`, `p_atendimento.py`), com `st.cache_data(ttl=...)` correto.
- ✅ **Logging estruturado** com `logging.basicConfig` no entrypoint.
- ✅ **Timezone explicitado** (`America/Sao_Paulo` via `zoneinfo`, não `datetime.now()` puro em
  `streamlit_app.py`) e formatação BR centralizada.
- ✅ **Type hints modernos** (`X | None`, `list[str]`, dataclasses `frozen`), docstrings em português
  e organização em blocos numerados — a base é legível.
- ✅ Todos os **assets referenciados existem**, exceto o ícone do item 3.17.

---

## 5. Plano de Ação Sugerido

### Sprint 0 — desbloqueio (horas)
1. ✅ **Feito:** corrigir o `SyntaxError` de `pages/quebra_geral.py`. (Alternativa: merge do PR #1)
2. Definir `runtime.txt` → `python-3.11` (ou 3.12) e fixar `requirements.txt` com versões.
3. Criar `.streamlit/config.toml` + `.streamlit/secrets.example.toml` (o PR #2 já traz o `config.toml`).
4. `try/except` nos `st.secrets.get()` de `pages/dashboard_meta.py` (item 3.2).
5. Corrigir `ICON_PATH` → `assets/icons/totale.ico`.

### Sprint 1 — segurança (dias) — ✅ implementado em 27/09/2026
6. ✅ Remover `denisvick/admin123` do código; usuários só via `secrets.toml`.
7. ✅ **Decisão do projeto:** a autenticação é concentrada **exclusivamente** em
   `pages/gestao_ativos.py` (única página que escreve na planilha). Não há gate
   central no entrypoint nem autenticação nas demais páginas — elas são de
   leitura e permanecem abertas no portal.
8. ✅ Remover o fallback de senha em texto plano (`gestao_ativos.py:123`) +
   migração para PBKDF2-HMAC-SHA256.
9. ✅ Remover `ws.clear()` de `_gravar_gspread` (grava sobrepondo e só limpa as
   sobras depois do sucesso) + backup da versão anterior disponível para download.
10. ✅ Adicionar `usuarios.db`, `.streamlit_cache/` e `*.db` ao `.gitignore`;
    `git rm --cached` do `.pkl`.

> 🧪 Além dos itens acima: suíte de testes (`tests/`) com pytest + `AppTest`,
> `pyproject.toml` com configuração de pytest/ruff, `runtime.txt`,
> `.streamlit/config.toml` e `.streamlit/secrets.example.toml`.

### Sprint 2 — engenharia (semanas)
11. Apagar `old/`, `pages/home.py`, `pages/login.py` (guardar em tag).
12. Introduzir `pyproject.toml` + ruff + pre-commit e um workflow de CI rodando `ruff` e `compileall`.
13. Primeiros testes com `streamlit.testing.v1.AppTest` (o mesmo harness usado nesta verificação) —
    já provou pegar o bug fatal em segundos.
14. Quebrar as funções de 1000/618/488 linhas em unidades testáveis.
15. Substituir `st.components.v1.html` por `st.iframe`/`st.html` e remover `set_page_config` das páginas.
16. Atualizar o README (caminhos, licença, screenshots) e alinhar LICENSE x badge.

---

## 6. Comandos de Reprodução

```bash
# Erro fatal (antes da correção)
python3 -m compileall -q pages/                     # SyntaxError: pages/quebra_geral.py:1735
.venv/bin/ruff check --target-version py311 --select E9 pages/

# Execução de todas as páginas
python3 - <<'PY'
import glob, os
from streamlit.testing.v1 import AppTest
os.chdir("/caminho/painel-totale")
for a in ["streamlit_app.py"] + sorted(glob.glob("pages/*.py")):
    at = AppTest.from_file(os.path.abspath(a)); at.run()
    print(a, [str(e.value)[:120] for e in at.exception])
PY

# Boot real
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
curl -s localhost:8501/_stcore/health      # ok
```
