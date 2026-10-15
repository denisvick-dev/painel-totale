# 📊 Documentação: Sidebar TOTALE (`components/sidebar.py`)

## Visão Geral

O módulo `components/sidebar.py` concentra o CSS dos temas, o seletor de tema persistente e os
componentes corporativos da sidebar do portal. Ele substitui o CSS que antes ficava acoplado ao
`streamlit_app.py`, evitando duplicação entre o entrypoint e as páginas. O robô local também é
renderizado uma única vez pelo shell global do app, para monitorar a mesma pasta em todas as páginas.

O Design System (`components/componentes.py`) reexporta os principais símbolos deste módulo, então
as páginas podem importar tanto de `components.sidebar` quanto de `components.componentes`.

---

## 🏗️ Estrutura de Arquivos

```
painel-totale-teste/
├── streamlit_app.py            # Entry point: navegação, shell raiz e sidebar completa
├── components/
│   ├── componentes.py          # Design System; reexporta os helpers do sidebar
│   └── sidebar.py              # 🎨 Sidebar corporativo: temas, seletor e componentes
├── pages/                      # Páginas; usam render_page_sidebar_theme_selector()
└── tests/
    └── test_tema_sidebar.py    # Guardas de tema, seletor e persistência
```

---

## 🎨 Temas

| Tema | Nome exibido no seletor | Papel |
|------|-------------------------|-------|
| `claro` | ☀️ Claro Corporativo | Tema padrão |
| `azul` | 🔷 Deep Executive Navy | Fundo escuro corporativo |
| `laranja` | 🔶 Terracotta & Amber | Fundo quente com acento laranja |

O alias legado `padrao` é normalizado para `claro` por `normalizar_tema_sidebar()`; valores
inválidos caem no tema padrão em vez de quebrar o widget.

### Estado na sessão

| Chave | Conteúdo |
|-------|----------|
| `_totale_sidebar_theme` | Tema ativo — fonte da verdade entre reruns e páginas |
| `_totale_sidebar_css_tema` | Tema do CSS de sidebar já injetado |
| `_totale_sidebar_theme_select` | Chave do widget `selectbox` do seletor |
| `_totale_root_navigation_shell` | Marcado pelo entrypoint quando o shell raiz está ativo |
| `_totale_css_head_tema` | Tema sincronizado pelo `aplicar_sidebar_corp()` do Design System |

---

## ✨ API

### Aplicação de estilo

| Função | Descrição |
|--------|-----------|
| `aplicar_estilo(tema_sidebar=None)` | Aplica o CSS **do sidebar**, mantendo o tema da sessão quando omitido |
| `aplicar_estilo_corp(tema_sidebar=None)` | Alias corporativo de `aplicar_estilo()` |
| `aplicar_sidebar_corp(tema=None)` | Reaplica o tema atual ou aplica um tema explícito |
| `carregar_layout_corporativo(...)` | Atalho: aplica o tema e, se pedido, desenha marca + seletor |

> Para o CSS **global** do portal (Design System + Plotly + fontes + sidebar), use
> `components.componentes.aplicar_estilo()`, que internamente já chama o CSS do sidebar.

### Tema

| Função | Descrição |
|--------|-----------|
| `normalizar_tema_sidebar(tema)` | Normaliza nomes (`padrao` → `claro`) e valida valores |
| `definir_tema_sidebar(tema)` | Persiste o tema ativo e sincroniza o seletor |
| `render_sidebar_theme_selector(...)` | Seletor de tema completo, com persistência automática |
| `render_page_sidebar_theme_selector()` | Seletor **apenas** quando a página não usa o shell raiz |

### Componentes

| Função | Descrição |
|--------|-----------|
| `render_sidebar_brand(...)` | Marca, subtítulo, ícone/logotipo e badge de versão |
| `render_sidebar_section(titulo, icone, collapsible)` | Título de seção (ou `expander`) |
| `render_sidebar_divider(estilo, espacamento, cor, label)` | Divisor, linha rotulada ou espaço |
| `render_sidebar_info(...)` | Cartão de usuário, dados complementares e presença |
| `render_sidebar_status(...)` | Badge compacto ou cartão detalhado de status do sistema |
| `render_sidebar_footer_info(...)` | Versão, ambiente, relógio opcional e copyright |
| `render_sidebar_spacer(altura)` | Espaço vertical controlado |
| `formatar_datetime_exibicao(valor, com_segundos=False)` | Formata `datetime`/`Timestamp`/texto para exibição |

---

## 🚀 Uso

### No entrypoint (`streamlit_app.py`)

```python
from components.componentes import aplicar_estilo
from components.sidebar import (
    definir_tema_sidebar,
    render_sidebar_brand,
    render_sidebar_divider,
    render_sidebar_footer_info,
    render_sidebar_section,
    render_sidebar_spacer,
    render_sidebar_status,
    render_sidebar_theme_selector,
)

definir_tema_sidebar(tema_ativo)
aplicar_estilo()                                    # Design System + sidebar

render_sidebar_brand(nome="TOTALE", subtitulo="Portal de Operações", versao="3.4.0")
render_sidebar_section("Aparência", icone="🎨")
tema_escolhido = render_sidebar_theme_selector()    # já persiste e reaplica o CSS
render_sidebar_divider()
render_sidebar_status(status="ok", label="Sistema operacional")
render_sidebar_spacer("pequeno")
render_sidebar_footer_info(versao="v3.4.0", ambiente="Produção")
```

### Nas páginas

```python
from components.sidebar import render_page_sidebar_theme_selector

render_page_sidebar_theme_selector()  # no-op quando o shell raiz já renderizou o seletor
```

O entrypoint marca `_totale_root_navigation_shell = True`; com isso, as páginas não criam um
segundo seletor de tema (o que quebraria a chave única do widget). O mesmo shell renderiza o
`renderizar_robo_local()` compartilhado (importado de `robo.py`); páginas não devem criar outra
instância. Motor, monitor e CLI estão no mesmo arquivo, sem pacote `robo/`. O DataFrame bruto
fica em `st.session_state["df_memoria_raw"]` e cada página aplica seu próprio ETL sobre essa fonte.

### Atalho

```python
from components.sidebar import carregar_layout_corporativo

carregar_layout_corporativo(renderizar_sidebar=True, nome="TOTALE", versao="3.4.0")
```

---

## ✅ Boas práticas e guardas

- **Não** passe `use_container_width` (depreciado): use `width="stretch"` / `width="content"`.
  Guarda: `tests/test_sem_depreciados.py`.
- **Não** chame `st.cache_data.clear()` / `st.cache_resource.clear()` globalmente nas páginas;
  invalide funções específicas. Guarda: `tests/test_refatoracao_arquitetura.py`.
- Mantenha o tema em `st.session_state["_totale_sidebar_theme"]` — nunca replique a chave em
  outra constante.
- Novos estilos de sidebar devem usar os tokens de `_TEMAS` e os placeholders `@@...@@` do CSS,
  para que os três temas continuem consistentes.

Guarda principal de comportamento: `tests/test_tema_sidebar.py`.
