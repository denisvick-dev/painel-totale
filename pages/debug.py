"""
debug_colunas.py
================
Função para mostrar e analisar colunas dos DataFrames de Produção e Consultivo
"""

import io
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote as url_quote

import pandas as pd
import requests
import streamlit as st


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════════════

class Configuracoes:
    SHEET_ID_PROD = "11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v"
    SHEET_ABA_PROD = "Prod"
    DRIVE_ID_CONS = "1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs"
    TIMEOUT = 30


# ══════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE CARREGAMENTO
# ═══════════════════════════════════════════════════════════════════════════

def carregar_producao_raw() -> Tuple[pd.DataFrame, Optional[str]]:
    """Carrega dados brutos de produção sem normalização"""
    try:
        url = f"https://docs.google.com/spreadsheets/d/{Configuracoes.SHEET_ID_PROD}/gviz/tq?tqx=out:csv&sheet={url_quote(Configuracoes.SHEET_ABA_PROD)}"
        resp = requests.get(url, timeout=Configuracoes.TIMEOUT)
        
        if resp.status_code != 200:
            return pd.DataFrame(), f"Erro HTTP {resp.status_code}"
        
        if "<!DOCTYPE html" in resp.text[:200]:
            return pd.DataFrame(), "Planilha não está pública"
        
        df = pd.read_csv(io.StringIO(resp.text))
        return df, None
        
    except Exception as e:
        return pd.DataFrame(), str(e)[:100]


def carregar_consultivo_raw() -> Tuple[pd.DataFrame, Optional[str]]:
    """Carrega dados brutos de consultivo sem normalização"""
    try:
        url = f"https://drive.google.com/uc?export=download&id={Configuracoes.DRIVE_ID_CONS}"
        sessao = requests.Session()
        resp = sessao.get(url, timeout=Configuracoes.TIMEOUT)
        
        if resp.status_code != 200:
            return pd.DataFrame(), f"Erro HTTP {resp.status_code}"
        
        if resp.content[:4] == b"PK\x03\x04":
            df = pd.read_excel(io.BytesIO(resp.content))
        else:
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(io.StringIO(resp.content.decode(enc)), sep=",")
                    break
                except:
                    try:
                        df = pd.read_csv(io.StringIO(resp.content.decode(enc)), sep=";")
                        break
                    except:
                        continue
        
        return df, None
        
    except Exception as e:
        return pd.DataFrame(), str(e)[:100]


# ═══════════════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL DE DEBUG (Requisito do Usuário)
# ═══════════════════════════════════════════════════════════════════════════

def mostrar_colunas_e_debug() -> None:
    """
    ✅ Função completa para mostrar e analisar colunas dos DataFrames
    Exibe:
    - Todas as colunas disponíveis
    - Tipos de dados
    - Amostras dos dados
    - Colunas potenciais para mapeamento
    - Estatísticas básicas
    """
    
    st.markdown("### 🔍 Debug de Colunas - Produção e Consultivo")
    st.info("Esta função mostra todas as colunas disponíveis para ajudar no mapeamento dos dados")
    
    # Carregar dados
    with st.spinner("Carregando dados para análise..."):
        df_prod, erro_prod = carregar_producao_raw()
        df_cons, erro_cons = carregar_consultivo_raw()
    
    # Mostrar erros se houver
    if erro_prod:
        st.error(f"❌ Erro Produção: {erro_prod}")
    if erro_cons:
        st.error(f"❌ Erro Consultivo: {erro_cons}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # PRODUÇÃO
    # ═══════════════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("### 📋 Produção (O.S.)")
    
    if not df_prod.empty:
        # Resumo
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Linhas", len(df_prod))
        with col2:
            st.metric("Colunas", len(df_prod.columns))
        with col3:
            st.metric("Memória", f"{df_prod.memory_usage(deep=True).sum() / 1024:.1f} KB")
        
        # Todas as colunas
        st.markdown("#### 📑 Todas as Colunas")
        
        colunas_info = []
        for col in df_prod.columns:
            colunas_info.append({
                "Nome Original": col,
                "Nome Normalizado": re.sub(r'[^\w\s]', '', str(col).lower().strip()).replace(' ', '_'),
                "Tipo": str(df_prod[col].dtype),
                "Não Nulos": df_prod[col].notna().sum(),
                "Únicos": df_prod[col].nunique(),
                "Amostra": str(df_prod[col].dropna().head(3).tolist())[:50],
            })
        
        df_colunas_prod = pd.DataFrame(colunas_info)
        st.dataframe(df_colunas_prod, use_container_width=True, hide_index=True)
        
        # Colunas potenciais para mapeamento
        st.markdown("#### 🎯 Colunas Potenciais para Mapeamento")
        
        mapeamento_sugestoes = {
            " Ordem de Serviço": ["os", "numero_os", "num_os", "protocolo", "ordem_servico", "n_os"],
            "🗂️ Projeto/Cliente": ["projeto", "cliente", "obra", "contrato", "nome_projeto", "obras"],
            "📍 Base/Regional": ["base", "regional", "regiao", "polo", "time", "equipe", "area"],
            "📅 Data": ["data", "data_os", "competencia", "dt", "date"],
            "🔢 Quantidade": ["quantidade", "qtd", "qtde", "total"],
        }
        
        for categoria, candidatos in mapeamento_sugestoes.items():
            encontradas = []
            for col in df_prod.columns:
                col_normal = re.sub(r'[^\w\s]', '', str(col).lower().strip()).replace(' ', '_')
                for cand in candidatos:
                    if cand in col_normal or col_normal in cand:
                        encontradas.append(f"`{col}`")
                        break
            
            if encontradas:
                st.success(f"{categoria}: {', '.join(encontradas)}")
            else:
                st.warning(f"{categoria}: Nenhuma coluna encontrada")
        
        # Amostra dos dados
        with st.expander("📊 Ver Amostra dos Dados (Primeiras 10 linhas)"):
            st.dataframe(df_prod.head(10), use_container_width=True)
        
        # Estatísticas
        with st.expander("📈 Estatísticas Descritivas"):
            st.write(df_prod.describe())
    
    else:
        st.warning("📭 Nenhum dado de produção carregado")
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONSULTIVO
    # ═══════════════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("### 💼 Consultivo")
    
    if not df_cons.empty:
        # Resumo
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Linhas", len(df_cons))
        with col2:
            st.metric("Colunas", len(df_cons.columns))
        with col3:
            st.metric("Memória", f"{df_cons.memory_usage(deep=True).sum() / 1024:.1f} KB")
        
        # Todas as colunas
        st.markdown("#### 📑 Todas as Colunas")
        
        colunas_info = []
        for col in df_cons.columns:
            colunas_info.append({
                "Nome Original": col,
                "Nome Normalizado": re.sub(r'[^\w\s]', '', str(col).lower().strip()).replace(' ', '_'),
                "Tipo": str(df_cons[col].dtype),
                "Não Nulos": df_cons[col].notna().sum(),
                "Únicos": df_cons[col].nunique(),
                "Amostra": str(df_cons[col].dropna().head(3).tolist())[:50],
            })
        
        df_colunas_cons = pd.DataFrame(colunas_info)
        st.dataframe(df_colunas_cons, use_container_width=True, hide_index=True)
        
        # Colunas potenciais para mapeamento
        st.markdown("#### 🎯 Colunas Potenciais para Mapeamento")
        
        mapeamento_sugestoes = {
            "️ Projeto/Cliente": ["projeto", "cliente", "obra", "contrato", "nome_projeto", "obras"],
            "📍 Base/Regional": ["base", "regional", "regiao", "polo", "time", "equipe", "area"],
            "📅 Data": ["data", "data_os", "competencia", "dt", "date"],
            "💰 Consultivos": ["qtde_cons", "total_consultivos", "consultivos", "qtd_cons"],
            "📦 Produtos": ["qtde_prod", "total_produtos", "quantidade", "qtd", "qtde", "produtos"],
            "📡 Mesh": ["qtde_mesh", "mesh", "total_mesh"],
            "📺 TV Box": ["qtde_tv", "qtde_tv_box", "tv_box", "tv", "total_tv"],
            "🌐 Virtua": ["qtde_virtua", "virtua", "total_virtua"],
        }
        
        for categoria, candidatos in mapeamento_sugestoes.items():
            encontradas = []
            for col in df_cons.columns:
                col_normal = re.sub(r'[^\w\s]', '', str(col).lower().strip()).replace(' ', '_')
                for cand in candidatos:
                    if cand in col_normal or col_normal in cand:
                        encontradas.append(f"`{col}`")
                        break
            
            if encontradas:
                st.success(f"{categoria}: {', '.join(encontradas)}")
            else:
                st.warning(f"{categoria}: Nenhuma coluna encontrada")
        
        # Amostra dos dados
        with st.expander("📊 Ver Amostra dos Dados (Primeiras 10 linhas)"):
            st.dataframe(df_cons.head(10), use_container_width=True)
        
        # Estatísticas
        with st.expander("📈 Estatísticas Descritivas"):
            st.write(df_cons.describe())
    
    else:
        st.warning("📭 Nenhum dado de consultivo carregado")
    
    # ══════════════════════════════════════════════════════════════════════
    # RECOMENDAÇÕES
    # ═══════════════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("### 💡 Recomendações")
    
    st.markdown("""
    1. **Verifique os nomes das colunas** - Compare com o que está no código
    2. **Ajuste o mapeamento** - Atualize as listas de candidatos se necessário
    3. **Valide os tipos de dados** - Colunas numéricas devem ser int/float
    4. **Cheque valores nulos** - Muitas colunas com poucos não-nulos podem indicar problema
    """)


# ═══════════════════════════════════════════════════════════════════════════
# VERSÃO SIMPLIFICADA PARA IMPRIMIR NO CONSOLE
# ═══════════════════════════════════════════════════════════════════════════

def print_colunas_console() -> None:
    """
    Versão simplificada para imprimir no console/terminal
    Útil para debug rápido sem Streamlit
    """
    print("\n" + "="*80)
    print("🔍 DEBUG DE COLUNAS - PRODUÇÃO E CONSULTIVO")
    print("="*80)
    
    df_prod, erro_prod = carregar_producao_raw()
    df_cons, erro_cons = carregar_consultivo_raw()
    
    if erro_prod:
        print(f"\n❌ Erro Produção: {erro_prod}")
    else:
        print(f"\n PRODUÇÃO ({len(df_prod)} linhas, {len(df_prod.columns)} colunas)")
        print("-"*80)
        for i, col in enumerate(df_prod.columns, 1):
            print(f"{i:3}. {col:40} | Tipo: {str(df_prod[col].dtype):15} | Únicos: {df_prod[col].nunique():6}")
        
        print("\n🎯 Colunas Potenciais:")
        candidatos = {
            "OS": ["os", "numero_os", "num_os", "protocolo"],
            "Projeto": ["projeto", "cliente", "obra", "contrato"],
            "Base": ["base", "regional", "regiao", "polo", "equipe"],
            "Data": ["data", "dt", "competencia"],
        }
        for categoria, lista in candidatos.items():
            encontradas = [c for c in df_prod.columns if any(l in c.lower() for l in lista)]
            print(f"  {categoria}: {encontradas if encontradas else 'Nenhuma'}")
    
    if erro_cons:
        print(f"\n❌ Erro Consultivo: {erro_cons}")
    else:
        print(f"\n💼 CONSULTIVO ({len(df_cons)} linhas, {len(df_cons.columns)} colunas)")
        print("-"*80)
        for i, col in enumerate(df_cons.columns, 1):
            print(f"{i:3}. {col:40} | Tipo: {str(df_cons[col].dtype):15} | Únicos: {df_cons[col].nunique():6}")
        
        print("\n🎯 Colunas Potenciais:")
        candidatos = {
            "Projeto": ["projeto", "cliente", "obra", "contrato"],
            "Base": ["base", "regional", "regiao", "polo", "equipe"],
            "Consultivos": ["consultivos", "qtde_cons"],
            "Produtos": ["produtos", "quantidade", "qtd", "qtde"],
            "Mesh": ["mesh"],
            "TV": ["tv", "tv_box"],
            "Virtua": ["virtua"],
        }
        for categoria, lista in candidatos.items():
            encontradas = [c for c in df_cons.columns if any(l in c.lower() for l in lista)]
            print(f"  {categoria}: {encontradas if encontradas else 'Nenhuma'}")
    
    print("\n" + "="*80)


# ═══════════════════════════════════════════════════════════════════════════
# EXEMPLO DE USO NO STREAMLIT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Configurar página
    st.set_page_config(page_title="Debug Colunas", page_icon="", layout="wide")
    
    # Título
    st.title("🔍 Debug de Colunas - TOTALE")
    st.markdown("Ferramenta para visualizar e analisar a estrutura dos dados")
    
    # Botão para executar
    if st.button("🔍 Mostrar Colunas", type="primary", use_container_width=True):
        mostrar_colunas_e_debug()
    
    # Sidebar com informações
    with st.sidebar:
        st.markdown("### ℹ️ Informações")
        st.markdown("""
        **Produção:**
        - ID: `11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v`
        - Aba: `Prod`
        
        **Consultivo:**
        - ID: `1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs`
        
        **Cache:**
        - Produção: 5 minutos
        - Consultivo: 10 minutos
        """)
        
        st.divider()
        
        if st.button("🔄 Limpar Cache"):
            st.cache_data.clear()
            st.success("Cache limpo! Recarregue a página.")