"""
EXEMPLO DE USO: Sidebar Corporativo TOTALE
===========================================

Este arquivo demonstra como usar todos os recursos do novo sidebar
em painel-totale.

Copie e adapte os exemplos para suas páginas.
"""

import streamlit as st
from datetime import datetime
from components.componentes import (
    aplicar_sidebar_corp,
    render_sidebar_info,
    render_sidebar_status,
    render_sidebar_filtro,
    render_sidebar_section,
    render_sidebar_divider,
    render_sidebar_footer_info,
    get_hora_atual_brt,
    get_data_atual_br,
)

# ====================================================
# 1. SETUP INICIAL (em streamlit_app.py)
# ====================================================
def exemplo_setup():
    """Configuração inicial - chamar UMA VEZ no início da app"""
    aplicar_sidebar_corp()  # Aplica CSS corporativo


# ====================================================
# 2. INFORMAÇÕES DO USUÁRIO
# ====================================================
def exemplo_user_info():
    """Mostrar dados do usuário logado no sidebar"""
    with st.sidebar:
        # Método 1: Com dados de session_state
        if "user_name" in st.session_state:
            render_sidebar_info(
                user_name=st.session_state.user_name,
                email=st.session_state.get("user_email"),
                role=st.session_state.get("user_role", "Técnico"),
                avatar="👤"
            )
        
        # Método 2: Com dados fixos (para teste)
        else:
            render_sidebar_info(
                user_name="João Silva",
                email="joao@totale.com.br",
                role="Técnico de Produção",
                avatar="👨‍💼"
            )


# ====================================================
# 3. STATUS DO SISTEMA
# ====================================================
def exemplo_status_sistema():
    """Mostrar indicador de status do sistema"""
    with st.sidebar:
        # Status OK com timestamp
        render_sidebar_status(
            sistema_ok=True,
            ultima_atualizacao=datetime.now(),
            mensagem="Sistema operacional"
        )
        
        st.divider()
        
        # Status com erro
        # render_sidebar_status(
        #     sistema_ok=False,
        #     mensagem="Falha na sincronização"
        # )


# ====================================================
# 4. FILTROS CORPORATIVOS
# ====================================================
def exemplo_filtros():
    """Adicionar filtros ao sidebar"""
    with st.sidebar:
        render_sidebar_section("🔍 Filtros")
        
        # Filtro simples
        regiao = render_sidebar_filtro(
            label="Região",
            options=["São Paulo", "Rio de Janeiro", "Minas Gerais", "Rio Grande do Sul"],
            default="São Paulo",
            key="filtro_regiao"
        )
        
        # Filtro com múltipla seleção
        tipos = render_sidebar_filtro(
            label="Tipos de Serviço",
            options=["Instalação", "Manutenção", "Diagnóstico", "Reparos"],
            default=["Instalação"],
            key="filtro_tipos",
            multi=True
        )
        
        # Filtro com datas
        data_inicio = render_sidebar_filtro(
            label="Data Início",
            options=["2026-01-01", "2026-02-01", "2026-03-01"],
            default="2026-01-01",
            key="filtro_data_inicio"
        )
        
        st.write(f"✅ Filtros selecionados:")
        st.write(f"- Região: {regiao}")
        st.write(f"- Tipos: {tipos}")
        st.write(f"- Data: {data_inicio}")


# ====================================================
# 5. ORGANIZAÇÃO DE SEÇÕES
# ====================================================
def exemplo_secoes():
    """Organizar sidebar em seções lógicas"""
    with st.sidebar:
        # Seção 1: Usuário
        render_sidebar_info(user_name="Maria Santos", role="Analista")
        render_sidebar_divider()
        
        # Seção 2: Status
        render_sidebar_status(sistema_ok=True)
        render_sidebar_divider()
        
        # Seção 3: Filtros
        render_sidebar_section("📊 Relatórios")
        render_sidebar_filtro("Período", ["Hoje", "Esta Semana", "Este Mês"], "Hoje")
        render_sidebar_filtro("Status", ["Ativo", "Pendente", "Concluído"], "Ativo")
        render_sidebar_divider()
        
        # Seção 4: Links úteis
        render_sidebar_section("⚙️ Configurações")
        if st.button("⚙️ Configurações", use_container_width=True):
            st.switch_page("pages/configuracoes.py")
        
        if st.button("📞 Suporte", use_container_width=True):
            st.write("Entre em contato com suporte@totale.com")
        
        # Seção 5: Footer
        render_sidebar_footer_info(
            versao="3.1.0",
            ambiente="Produção"
        )


# ====================================================
# 6. FUNÇÕES AUXILIARES DE TEMPO
# ====================================================
def exemplo_time_helpers():
    """Usar funções de data/hora em BRT"""
    st.sidebar.info(f"""
    **Data & Hora:**
    - Hora: {get_hora_atual_brt()}
    - Data: {get_data_atual_br()}
    """)


# ====================================================
# 7. EXEMPLO COMPLETO
# ====================================================
def exemplo_completo():
    """Exemplo completo de sidebar com todos os recursos"""
    st.set_page_config(layout="wide", initial_sidebar_state="expanded")
    
    # Setup
    aplicar_sidebar_corp()
    
    # Sidebar
    with st.sidebar:
        # Header: Info do usuário
        render_sidebar_info(
            user_name="Técnico João",
            email="joao@totale.com",
            role="Operador",
            avatar="👨‍🔧"
        )
        render_sidebar_divider()
        
        # Status do sistema
        render_sidebar_status(
            sistema_ok=True,
            ultima_atualizacao=datetime.now(),
            mensagem="✅ Sincronizado"
        )
        render_sidebar_divider()
        
        # Filtros
        render_sidebar_section("📊 Filtros")
        regiao = render_sidebar_filtro(
            "Região",
            ["SP", "RJ", "MG", "RS"],
            "SP",
            key="ex_regiao"
        )
        periodo = render_sidebar_filtro(
            "Período",
            ["Hoje", "Semana", "Mês"],
            "Dia",
            key="ex_periodo"
        )
        render_sidebar_divider()
        
        # Actions
        render_sidebar_section("⚡ Ações")
        if st.button("🔄 Sincronizar", use_container_width=True):
            st.success("✅ Sincronização completa!")
        if st.button("📥 Exportar", use_container_width=True):
            st.info("📊 Relatório exportado!")
        
        # Footer
        render_sidebar_footer_info("3.1.0", "Produção")
    
    # Main content
    st.title("📊 Dashboard")
    st.markdown(f"""
    Bem-vindo ao painel! 
    
    **Filtros Ativos:**
    - Região: {regiao}
    - Período: {periodo}
    
    Use o sidebar esquerdo para interagir com a aplicação.
    """)


# ====================================================
# TESTE
# ====================================================
if __name__ == "__main__":
    st.set_page_config(page_title="Exemplos - Sidebar", layout="wide")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Setup",
        "User Info",
        "Status",
        "Exemplo Completo"
    ])
    
    with tab1:
        st.header("1️⃣ Setup Inicial")
        st.code("""
from components.componentes import aplicar_sidebar_corp

def main():
    aplicar_sidebar_corp()  # Chamar UMA VEZ no início
    # ... resto da app
        """, language="python")
        st.info("✅ Aplique em `streamlit_app.py` antes de usar qualquer componente")
    
    with tab2:
        st.header("2️⃣ Informações do Usuário")
        with st.sidebar:
            st.markdown("### Demo: User Info")
            render_sidebar_info(
                user_name="Demo User",
                email="demo@totale.com",
                role="Técnico Teste"
            )
        st.code("""
render_sidebar_info(
    user_name="João Silva",
    email="joao@totale.com",
    role="Técnico",
    avatar="👤"
)
        """, language="python")
    
    with tab3:
        st.header("3️⃣ Status do Sistema")
        render_sidebar_status(
            sistema_ok=True,
            ultima_atualizacao=datetime.now()
        )
        st.code("""
render_sidebar_status(
    sistema_ok=True,
    ultima_atualizacao=datetime.now(),
    mensagem="Sistema operacional"
)
        """, language="python")
    
    with tab4:
        st.header("4️⃣ Exemplo Completo")
        st.info("""
        Clique em 'Run' abaixo para ver o exemplo completo em ação.
        Note o sidebar com todos os componentes!
        """)
        st.button("▶️ Ver exemplo completo abaixo:")
        st.divider()
        exemplo_completo()
