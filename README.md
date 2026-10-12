<div align="center">

![Totale Tecnologia](https://img.shields.io/badge/TOTALE-TECNOLOGIA-F37C04?style=for-the-badge&labelColor=012869)

# 📊 Painel TOTALE

### Plataforma Corporativa de Gestão de Ativos e Indicadores

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Google Sheets](https://img.shields.io/badge/Google_Sheets-34A853?style=flat&logo=google-sheets&logoColor=white)](https://sheets.google.com/)
[![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=flat&logo=plotly&logoColor=white)](https://plotly.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=flat)](LICENSE)

[🌐 Demo ao Vivo](https://painel-totale.streamlit.app) · 
[🐛 Reportar Bug](https://github.com/denisvick-dev/painel-totale/issues) · 
[✨ Solicitar Feature](https://github.com/denisvick-dev/painel-totale/issues)

</div>

---

## 📖 Sobre o Projeto

O **Painel TOTALE** é uma plataforma corporativa completa desenvolvida em [Streamlit](https://streamlit.io/) para gestão de ativos, técnicos de campo e indicadores operacionais da Totale Tecnologia. Integra-se diretamente ao [Google Sheets](https://sheets.google.com/) como backend, oferecendo dashboards interativos, controle de acesso por perfis e ferramentas de produtividade.

### 🎯 Objetivos

- ✅ Centralizar informações operacionais em uma única plataforma
- ✅ Fornecer visão em tempo real de KPIs estratégicos
- ✅ Automatizar processos manuais e reduzir erros
- ✅ Garantir rastreabilidade com auditoria completa
- ✅ Padronizar comunicações corporativas

---

## ✨ Funcionalidades

### 📊 Dashboard Operacional
- Panorama em tempo real com KPIs essenciais
- Filtros dinâmicos por Base, Monitor e Situação
- Gráficos interativos (pizza, barras, heatmap) via [Plotly](https://plotly.com/)
- Exportação em Excel e CSV

### 👥 Gestão de Técnicos
- **Cadastro** de novos técnicos com validação
- **Edição rápida** de campos individuais
- **Importação em lote** via Excel/CSV
- **Desligamento** com registro de motivo
- **Histórico completo** de desligamentos

### 🗂️ Hierarquia Organizacional
- Visualização em treemap
- Análise Base → Monitor → Técnico
- Filtros multi-nível

### 📑 Relatórios Avançados
- Distribuição por Monitor
- Comparativo Ativos × Desligados
- Análise por Base
- Timeline de desligamentos

### 🔐 Segurança e Controle
- **Autenticação** por usuário e senha
- **Perfis de acesso**: Admin, Supervisor, Operador, Leitura
- **Filtros por base** conforme permissão
- **Auditoria completa** de todas as ações

### ✉️ Gerador de Assinatura de E-mail
- Template padronizado Totale
- Personalização Nome, Cargo e Telefones
- Exportação em PNG otimizado para e-mail
- Ajustes finos de posicionamento

---

## 🚀 Demonstração

### Screenshots

<details>
<summary>📊 Dashboard Principal</summary>

![Dashboard](docs/screenshots/dashboard.png)

</details>

<details>
<summary>🗂️ Hierarquia</summary>

![Hierarquia](docs/screenshots/hierarquia.png)

</details>

<details>
<summary>✉️ Gerador de Assinatura</summary>

![Assinatura](docs/screenshots/assinatura.png)

</details>

---

## 🛠️ Tecnologias

| Categoria | Tecnologias |
|-----------|-------------|
| **Framework** | Streamlit 1.52+ |
| **Linguagem** | Python 3.11+ |
| **Backend** | Google Sheets API |
| **Visualização** | Plotly, Pandas |
| **Autenticação** | Service Account OAuth 2.0 |
| **Processamento de Imagem** | Pillow |
| **Exportação** | OpenPyXL |

---

## 📋 Pré-requisitos

- Python **3.11** ou superior
- Conta Google Cloud com **Service Account**
- Planilha Google Sheets compartilhada
- Git

---

## ⚙️ Instalação Local

### 1. Clone o Repositório
```bash
git clone https://github.com/denisvick-dev/painel-totale.git
cd painel-totale
```

### 2. Crie o Ambiente Virtual
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Instale as Dependências

Para executar o app:
```bash
pip install -r requirements.txt
```

Para desenvolver e executar a suíte completa de testes, use no lugar:
```bash
pip install -r requirements-dev.txt
```

### 4. Configure as Credenciais

Copie o arquivo de exemplo:
```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

Edite o `.streamlit/secrets.toml` com suas credenciais reais do Google Cloud e usuários.

A página de Gestão de Ativos só habilita contas declaradas em `[usuarios.<login>]`;
não há usuário/senha padrão. Configure uma senha forte antes de disponibilizar o app.

### 5. Configure o Google Sheets

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto ou selecione um existente
3. Ative as APIs:
   - Google Sheets API
   - Google Drive API
4. Crie uma **Service Account**
5. Baixe a chave JSON
6. Compartilhe sua planilha com o e-mail da service account
7. Preencha os dados no `secrets.toml`

### 6. Execute o Aplicativo
```bash
streamlit run streamlit_app.py
```

Acesse: **http://localhost:8501**

### Testes

```bash
# Guarda de sintaxe/estrutura, sem dependências externas
python tests/test_sintaxe.py

# Guarda de higiene: assets órfãos, lixo de SO, caminhos de máquina, árvore do README
python tests/test_higiene_repositorio.py

# Lint configurado no repositório
ruff check .

# Suíte completa (após instalar requirements-dev.txt)
pytest -q
```

---

## 🌐 Deploy no Streamlit Cloud

### Deploy Automático

1. Fork este repositório
2. Acesse o [Streamlit Community Cloud](https://share.streamlit.io)
3. Conecte sua conta GitHub
4. Clique em **"New app"**
5. Selecione o repositório e branch
6. Configure:
   - **Main file:** `streamlit_app.py`
   - **Python version:** `3.11`
7. Em **Advanced settings**, cole os secrets
8. Clique em **Deploy**

📚 [Guia completo do Streamlit Cloud](https://docs.streamlit.io/streamlit-community-cloud)

---

## 📁 Estrutura do Projeto

```
painel-totale/
├── streamlit_app.py              # Entry point, navegação e shell global
├── requirements.txt              # Dependências de execução
├── requirements-dev.txt          # Ambiente completo de desenvolvimento
├── requirements-test.txt         # Dependências mínimas para CI/testes
├── .ruff.toml                    # Regras de lint
├── README.md
├── .github/workflows/quality.yml # Lint e testes em push/PR
├── .streamlit/
│   └── secrets.example.toml      # Modelo local de configuração (sem credenciais reais)
├── components/                   # Componentes compartilhados
│   ├── componentes.py            # Design System (KPI, gráficos, CSS global)
│   ├── sidebar.py                # Sidebar corporativa: temas, seletor e componentes
│   ├── criterios.py              # Regras de classificação operacional
│   ├── metricas_executivas.py    # Métricas e resumos executivos
│   ├── alertas_automaticos.py    # Avaliação de alertas operacionais
│   ├── saude_dados.py            # Frescor e consistência das fontes
│   └── css_paginas.py            # Estilos reutilizáveis das páginas
├── config/                       # IDs, URLs e parâmetros centralizados
├── services/                     # Clientes externos (Google Drive/Sheets)
├── pages/                        # Páginas do aplicativo Streamlit
├── robo/                         # Leitura e monitoramento de arquivos locais
├── tests/                        # Testes de regressão e guardas estáticas
├── assets/                       # Ícones, imagens e marca usados pelo app
├── fonts/                        # Fontes corporativas
└── .streamlit_cache/             # Cache geoespacial versionado (Parquet)
```

> Não há diretório `old/`: scripts legados foram removidos e um teste-guarda
> (`tests/test_refatoracao_arquitetura.py`) impede que artefatos órfãos voltem.

---

## 🔐 Perfis de Acesso

| Perfil | Permissões |
|--------|-----------|
| 👑 **Admin** | Todas as funções + Auditoria |
| 🎯 **Supervisor** | Cadastro, Edição, Desligamento, Importação |
| ⚙️ **Operador** | Cadastro e Edição básica |
| 👁️ **Leitura** | Apenas visualização de dados |

---

## 🎨 Identidade Visual

Cores oficiais Totale Tecnologia:

| Cor | Hex | Uso |
|-----|-----|-----|
| 🔵 Azul Corporativo | `#012869` | Títulos, textos principais |
| 🟠 Laranja Marca | `#F37C04` | Destaques, botões, acentos |
| ⚪ Branco | `#FFFFFF` | Backgrounds |
| ⬜ Cinza Claro | `#F1F5F9` | Backgrounds secundários |

---

## 📊 Roadmap

- [x] ✅ Dashboard Operacional
- [x] ✅ Gestão de Técnicos completa
- [x] ✅ Sistema de Auditoria
- [x] ✅ Gerador de Assinatura
- [x] ✅ Integração Google Sheets
- [ ] 🚧 Notificações via e-mail
- [ ] 🚧 API REST para integrações
- [ ] 🚧 Aplicativo mobile
- [ ] 🚧 Autenticação 2FA
- [ ] 🚧 Backup automático diário
- [ ] 🚧 Integração com WhatsApp Business

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Siga estes passos:

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/MinhaFeature`
3. Commit suas mudanças: `git commit -m 'feat: adiciona MinhaFeature'`
4. Push para a branch: `git push origin feature/MinhaFeature`
5. Abra um Pull Request

### 📋 Padrão de Commits

Utilizamos [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `style:` Formatação
- `refactor:` Refatoração
- `test:` Testes
- `chore:` Manutenção

---

## 🐛 Reportar Bugs

Encontrou um bug? Abra uma [issue](https://github.com/denisvick-dev/painel-totale/issues) com:

- Descrição clara do problema
- Passos para reproduzir
- Comportamento esperado vs atual
- Screenshots (se aplicável)
- Ambiente (SO, versão Python, etc.)

---

## 👨‍💻 Sobre o Autor

<div align="center">

<table>
<tr>
<td align="center" width="150">
<img src="https://github.com/denisvick-dev.png" width="120" style="border-radius:50%"/>
</td>
<td align="left">

### **Denis Vick**
**Analista de COP** · *Totale Tecnologia*

Apaixonado por transformar dados em decisões estratégicas e por criar soluções que facilitam o dia a dia das operações.

</td>
</tr>
</table>

<br>

### 📬 Vamos Conectar!

<a href="https://www.linkedin.com/in/dvick13/">
  <img src="https://img.shields.io/badge/LinkedIn-Denis_Vick-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" />
</a>
<a href="https://github.com/denisvick-dev">
  <img src="https://img.shields.io/badge/GitHub-denisvick--dev-181717?style=for-the-badge&logo=github&logoColor=white" />
</a>
<a href="https://instagram.com/denisvick">
  <img src="https://img.shields.io/badge/Instagram-@denisvick-E4405F?style=for-the-badge&logo=instagram&logoColor=white" />
</a>
<br>
<a href="https://wa.me/5511993045101">
  <img src="https://img.shields.io/badge/WhatsApp-(11)_99304--5101-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" />
</a>
<a href="mailto:denis.vick@totaletecnologia.com.br">
  <img src="https://img.shields.io/badge/Email-denis.vick@totaletecnologia.com.br-D14836?style=for-the-badge&logo=gmail&logoColor=white" />
</a>

</div>

<br>

📱 **WhatsApp Corporativo:** [(11) 99304-5101](https://wa.me/5511993045101)  
📧 **E-mail:** denis.vick@totaletecnologia.com.br  
💼 **LinkedIn:** [/in/dvick13](https://www.linkedin.com/in/dvick13/)  
📸 **Instagram:** [@denisvick](https://instagram.com/denisvick)  
💻 **GitHub:** [@denisvick-dev](https://github.com/denisvick-dev)

</div>

---

## 🙏 Agradecimentos

- [Streamlit](https://streamlit.io/) pela framework incrível
- [Plotly](https://plotly.com/) pelas visualizações interativas
- [Google Cloud](https://cloud.google.com/) pela infraestrutura
- Em especial a **Vania S. Souza** pelo incentivo e confiança em meu trabalho

---

<div align="center">

**Feito com ❤️ por Denis Vick | Analista de COP | Totale Tecnologia**

⭐ Se este projeto foi útil, deixe uma estrela!

![Totale Tecnologia](https://img.shields.io/badge/TOTALE-TECNOLOGIA-F37C04?style=for-the-badge&labelColor=012869)

*Conexão em Movimento*

</div>