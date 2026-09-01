# 📊 Documentação: Melhorias do Sidebar TOTALE

## Visão Geral

Este documento descreve todas as melhorias implementadas no sidebar em ambos os projetos (`painel-totale` e `producao-totale`), incluindo funcionalidades novas, componentes reutilizáveis e boas práticas de implementação.

---

## 🏗️ Estrutura de Arquivos

```
painel-totale/
├── components/
│   ├── __init__.py
│   ├── componentes.py          # Componentes gerais (KPI, charts, etc)
│   └── sidebar.py              # 🆕 Sidebar corporativo com componentização
│
└── streamlit_app.py            # ✏️ Atualizado para usar novo sidebar

producao-totale/
├── components/
│   ├── componentes.py
│   └── sidebar.py              # ✏️ Melhorado com novas funções helper
│
└── streamlit_app.py
```

---

## ✨ Melhorias Implementadas

### 1. Centralização & Componentização

#### painel-totale
- ✅ Novo arquivo **`components/sidebar.py`** dedicado
- ✅ CSS removido de `streamlit_app.py` (evita duplicação)
- ✅ Função `aplicar_sidebar_corp()` para injeção única
- ✅ Caching de CSS com `@st.cache_data`

**Antes:**
```python
# streamlit_app.py - CSS acoplado ❌
class Visual:
    def injetar_css_global():
        st.html("""<style>...sidebar css...</style>""")
```

**Depois:**
```python
# components/sidebar.py - Separado e cacheado ✅
from components.sidebar import aplicar_sidebar_corp

aplicar_sidebar_corp()  # Chamada única, CSS cacheado
```

#### producao-totale
- ✅ Mantida estrutura existente (já tinha `sidebar.py`)
- ✅ Adicionadas funções auxiliares para consistência
- ✅ Melhorada documentação

---

### 2. Recursos Corporativos Completos

#### 2.1 Informações do Usuário
Novo componente para exibir dados do usuário logado:

```python
from components.sidebar import render_sidebar_info

render_sidebar_info(
    user_name="João Silva",
    email="joao@totale.com",
    role="Técnico de Produção",
    avatar="👤"
)
```

**Apresentação:**
- Avatar customizável (emoji ou URL)
- Nome em destaque
- Cargo/função
- Email (quebra de linha automática)
- Estilos corporativos

#### 2.2 Indicador de Status do Sistema
Novo componente para mostrar saúde do sistema:

```python
from components.sidebar import render_sidebar_status
from datetime import datetime

render_sidebar_status(
    sistema_ok=True,
    ultima_atualizacao=datetime.now(),
    mensagem="Sistema operacional"
)
```

**Características:**
- Indicador visual (✅ ou ❌)
- Status OK (verde) ou erro (vermelho)
- Timestamp da última atualização
- Mensagem customizável

#### 2.3 Filtros Corporativos
Novo wrapper para inputs com styling:

```python
from components.sidebar import render_sidebar_filtro

filtro = render_sidebar_filtro(
    label="Selecione a Region",
    options=["SP", "RJ", "MG", "RS"],
    default="SP",
    key="filtro_regiao"
)
```

**Vantagens:**
- Styling corporativo automático
- Suporte a multi-seleção
- Ajuda contextual
- Índice padrão configurável

#### 2.4 Componentes de Organização
Novos helpers para estruturar o sidebar:

```python
from components.sidebar import (
    render_sidebar_section,
    render_sidebar_divider,
    render_sidebar_footer_info
)

# Seção com título corporativo
render_sidebar_section("📊 Relatórios")

# Divisor visual
render_sidebar_divider()

# Footer com versão, ambiente e hora
render_sidebar_footer_info(
    versao="3.1.0",
    ambiente="Produção",
    mostrar_timestamp=True
)
```

#### 2.5 Funções Auxiliares de Tempo
Helpers para trabalhar com timezone do Brasil:

```python
from components.sidebar import get_hora_atual_brt, get_data_atual_br

hora = get_hora_atual_brt()      # "14:32:45"
data = get_data_atual_br()        # "01/09/2026"
```

---

### 3. Estilo Visual Corporativo

#### 3.1 Paleta de Cores
```python
TOTALE_AZUL = "#012869"           # Deep Midnight Navy
TOTALE_LARANJA = "#F37C04"        # Solar Orange
TOTALE_LARANJA_CLARO = "#FFBE64"  # Light Orange
```

#### 3.2 Gradiente do Sidebar (painel-totale)
```
Topo:        Laranja claro → Laranja → Marrom
Transição:   Transição suave para azul
Base:        Azul profundo → Azul muito escuro
```

**Efeito:** Tema corporativo moderno com bom contraste

#### 3.3 Menu de Navegação
- Links com cards arredondados
- Hover com transição suave (+2px translate)
- Página ativa com:
  - Gradiente azul-laranja
  - Borda laranja destacada
  - Sombra aumentada
  - Texto branco em destaque

#### 3.4 Inputs (Selectbox, Datepicker)
- Fundo semi-transparente
- Borda com cor corporativa
- Hover com intensificação de cor
- Focus com sombra colorida

#### 3.5 Botões
- Gradiente laranja (hover)
- Sombra suave
- Transição de elevação
- Estados secundários suportados

---

### 4. Performance & Otimizações

#### 4.1 Caching de CSS
```python
@st.cache_data(ttl=3600)
def _get_sidebar_css() -> str:
    """Retorna o CSS do sidebar (cacheado para performance)."""
    return f"""<style>...</style>"""
```

**Benefício:** CSS compilado apenas uma vez por hora

#### 4.2 Injeção Única
```python
# Evita múltiplas injeções do mesmo CSS
if "sidebar_applied" not in st.session_state:
    aplicar_sidebar_corp()
    st.session_state.sidebar_applied = True
```

#### 4.3 Responsividade
- Scrollbar customizada (WebKit)
- Layout fluido em mobile
- Colapsibilidade melhorada
- Ícones escaláveis

---

### 5. Recursos Avançados

#### 5.1 Scrollbar Customizada
```css
[data-testid="stSidebar"] ::-webkit-scrollbar {
    width: 8px;
}
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
    background: rgba(243, 124, 4, 0.4);
}
```

**Efeito:** Scrollbar estilizada em laranja corporativo

#### 5.2 Animações Suaves
- Hover com `transition: all 0.22s ease`
- Active com `transform: translateY(-2px)`
- Pulsação de status online

#### 5.3 Acessibilidade
- Bom contraste de cores (WCAG AA+)
- Ícones com fallback CSS
- Labels descritivos
- Espaçamento adequado

---

## 📚 Guia de Uso

### Para Painel-Totale

**1. No `streamlit_app.py`:**
```python
from components.sidebar import aplicar_sidebar_corp

def main():
    aplicar_sidebar_corp()  # Chamar uma vez no início
    st.logo("assets/images/novo-logo-totale.png")
    # ... resto da app
```

**2. Em qualquer página:**
```python
from components.sidebar import (
    render_sidebar_info,
    render_sidebar_status,
    render_sidebar_filtro
)

# No sidebar
with st.sidebar:
    render_sidebar_info(
        user_name=st.session_state.get("user"),
        email="user@totale.com"
    )
    render_sidebar_status(sistema_ok=True)
    
    filtro = render_sidebar_filtro("Região", ["SP", "RJ", "MG"])
```

### Para Producao-Totale

**Já funciona com `render_sidebar_corp()`:**
```python
from components.sidebar import render_sidebar_corp

render_sidebar_corp(on_logout=handle_logout)
```

**Novos recursos disponíveis:**
```python
from components.sidebar import render_sidebar_info, render_sidebar_footer_info

# Adicionar info do usuário
render_sidebar_info(user_name=st.session_state.tecnico)

# Adicionar footer
render_sidebar_footer_info(versao="1.0.0")
```

---

## 🔍 Recursos por Arquivo

### painel-totale/components/sidebar.py

| Função | Descrição | Uso |
|--------|-----------|-----|
| `aplicar_sidebar_corp()` | Aplica CSS corporativo | `aplicar_sidebar_corp()` |
| `render_sidebar_info()` | Info do usuário | `render_sidebar_info(user_name="João")` |
| `render_sidebar_status()` | Status do sistema | `render_sidebar_status(sistema_ok=True)` |
| `render_sidebar_filtro()` | Filtros corporativos | `render_sidebar_filtro("Label", options)` |
| `render_sidebar_section()` | Título de seção | `render_sidebar_section("Título")` |
| `render_sidebar_divider()` | Divisor visual | `render_sidebar_divider()` |
| `render_sidebar_footer_info()` | Footer com versão | `render_sidebar_footer_info(versao="3.1.0")` |
| `get_hora_atual_brt()` | Hora em BRT | `hora = get_hora_atual_brt()` |
| `get_data_atual_br()` | Data em DD/MM/YYYY | `data = get_data_atual_br()` |

### producao-totale/components/sidebar.py

| Função | Descrição |
|--------|-----------|
| `injetar_css_sidebar_corp()` | Aplica CSS (metálico) |
| `render_sidebar_corp()` | Renderiza sidebar completo com perfil |
| *(+ todas as funções acima)* | Novos helpers adicionados |

---

## 🎨 Customizações Possíveis

### 1. Alterar Cores
```python
# Em qualquer arquivo, substituir cores no CSS:
COR_PRIMARIA = "#seu-azul"
COR_SECUNDARIA = "#sua-laranja"
```

### 2. Adicionar Componentes
```python
# Criar nova função em sidebar.py
def render_sidebar_custom_widget():
    st.markdown("""<div>Seu componente aqui</div>""", 
                unsafe_allow_html=True)
```

### 3. Modificar Estilo de Inputs
Todos os inputs no sidebar herdam o styling automático via CSS

---

## 📊 Antes vs Depois

| Aspecto | Antes | Depois |
|--------|--------|---------|
| **Centralização** | CSS em 3+ lugares | Arquivo único `sidebar.py` |
| **Componentização** | Nenhuma | 8+ funções reutilizáveis |
| **Performance** | CSS reinjection | CSS cacheado (1h) |
| **User Info** | Manual com HTML | Componente automático |
| **Status Sistema** | Não existia | Indicador visual + timestamp |
| **Filtros** | Sem styling | Styling corporativo automático |
| **Footer** | Manual | Função helper |
| **Timezone** | Não padronizado | Funções helper (BRT) |
| **Documentação** | Nenhuma | Completa e detalhada |

---

## ✅ Checklist de Implementação

### painel-totale
- [x] Criar `components/sidebar.py` com all features
- [x] Remover CSS do sidebar de `streamlit_app.py`
- [x] Adicionar import de `aplicar_sidebar_corp`
- [x] Testar visual em todas as páginas
- [x] Verificar performance (cache)

### producao-totale
- [x] Adicionar funções helper a `sidebar.py`
- [x] Documentar uso das novas funções
- [x] Garantir compatibilidade com código existente

---

## 🚀 Próximas Melhorias Sugeridas

1. **Tema Escuro/Claro**: Adicionar toggle de tema
2. **Responder ao Mobile**: Sidebar colapsível adaptativo
3. **Animações CSS**: Transições mais elaboradas no menu
4. **Search no Menu**: Campo de busca em páginas
5. **Notificações**: Badge de notificações no sidebar
6. **Preferências de Usuário**: Salvar preferências no localStorage
7. **Internacionalização (i18n)**: Suporte a múltiplos idiomas

---

## 📝 Notas de Desenvolvimento

- Todos os componentes usam `unsafe_allow_html=True` (CSS personalizado necessário)
- Timezone padrão: `America/Sao_Paulo` (BRT)
- Paleta corporativa padronizada em constantes
- Todas as funções têm docstrings completas
- CSS usa seletores `[data-testid]` para compatibilidade Streamlit

---

**Versão:** 1.0.0  
**Última Atualização:** 01/09/2026  
**Mantido por:** Equipe TOTALE
