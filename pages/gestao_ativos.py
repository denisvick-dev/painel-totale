"""
═══════════════════════════════════════════════════════════════════════════════
 GESTÃO DE ATIVOS TOTALE — V 4.0.0
 LEITURA : streamlit-gsheets  (conn.read  — sem erro 404)
 ESCRITA : gspread direto      (sem erro 400)
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Tuple

import gspread
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials
from streamlit_gsheets import GSheetsConnection

# ═══════════════════════════════════════════════════════════════════════════════
# [0] SAFE — converte qualquer valor para str limpa
# ═══════════════════════════════════════════════════════════════════════════════
class Safe:
    _N = frozenset({"none","nan","nat","null","n/a","na","<na>","#n/a",""})

    @classmethod
    def celula(cls, v: Any) -> str:
        if v is None:                                         return ""
        if isinstance(v, (bool, np.bool_)):                  return "SIM" if v else "NÃO"
        if isinstance(v, np.integer):                         return str(int(v))
        if isinstance(v, (float, np.floating)):
            try:
                if np.isnan(v): return ""
            except Exception:  pass
            return str(int(v)) if v == int(v) else str(v)
        try:
            if pd.isna(v): return ""
        except Exception: pass
        s = str(v).strip()
        return "" if s.lower() in cls._N else s

    @classmethod
    def str(cls, v: Any, d="")  -> str:  r = cls.celula(v); return r if r else d
    @classmethod
    def upper(cls, v, d="")     -> str:  return cls.str(v,d).upper()
    @classmethod
    def lower(cls, v, d="")     -> str:  return cls.str(v,d).lower()

    @classmethod
    def limpar_df(cls, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty: return pd.DataFrame() if df is None else df
        for c in df.columns:
            df[c] = df[c].apply(cls.celula)
        return df[~(df=="").all(axis=1)].reset_index(drop=True)

    @classmethod
    def para_api(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Sanitização final antes de qualquer escrita na API.
        Garante que cada célula é str pura — nunca None, NaN, bool, int, float.
        """
        if df is None or df.empty: return pd.DataFrame()
        df = df.copy().fillna("").replace({None: ""})
        for c in df.columns:
            df[c] = df[c].apply(cls.celula)
        df.columns = [cls.str(c, f"c{i}") for i,c in enumerate(df.columns)]
        return df.astype(str)                    # força dtype str

    @classmethod
    def garantir_colunas(cls, df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        def n(s):
            return str(s).lower().translate(str.maketrans(
                "ãáâéêíóôúç ","aaaeeioouc_"))
        for c in cols:
            if c not in df.columns:
                for ex in df.columns:
                    if n(ex)==n(c): df=df.rename(columns={ex:c}); break
                else: df[c]=""
        return df[list(cols)].copy()


# ═══════════════════════════════════════════════════════════════════════════════
# [1] GSPREAD — cliente direto para escrita (sem erro 400)
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def _gspread_client() -> gspread.Client:
    """
    Cria cliente gspread usando as mesmas credenciais do secrets.toml.
    cache_resource → instância reutilizada em toda a sessão.
    """
    info = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds  = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def _gspread_sheet(worksheet_name: str) -> gspread.Worksheet:
    """Retorna o worksheet pelo nome."""
    gc  = _gspread_client()
    sh  = gc.open_by_key(Config.SHEET_ID)
    return sh.worksheet(worksheet_name)


def _gravar_gspread(worksheet_name: str, df: pd.DataFrame) -> bool:
    """
    Substitui TODO o conteúdo da aba com o DataFrame.
    Compatível com gspread 5.x e 6.x.
    """
    try:
        df_api = Safe.para_api(df)
        if df_api.empty:
            st.warning(f"⚠️ DataFrame vazio — '{worksheet_name}' não alterada.")
            return False

        ws = _gspread_sheet(worksheet_name)
        
        # Monta lista de listas: [cabeçalho] + linhas
        cabecalho = df_api.columns.tolist()
        linhas    = df_api.values.tolist()
        dados     = [cabecalho] + linhas
        
        # Calcular range necessário (ex: A1:G100)
        num_linhas = len(dados)
        num_colunas = len(cabecalho)
        
        # Converter número da coluna para letra (A, B, ..., Z, AA, AB, ...)
        def col_letra(n: int) -> str:
            resultado = ""
            while n > 0:
                n, resto = divmod(n - 1, 26)
                resultado = chr(65 + resto) + resultado
            return resultado
        
        ultima_col = col_letra(num_colunas)
        range_completo = f"A1:{ultima_col}{num_linhas}"
        
        # Limpar TUDO antes de escrever
        ws.clear()
        
        # ✅ CORRETO para gspread 6.x — usa range_name e values como keywords
        try:
            ws.update(
                range_name=range_completo,
                values=dados,
                value_input_option="USER_ENTERED"
            )
        except TypeError:
            # Fallback para gspread 5.x (ordem posicional invertida)
            ws.update(range_completo, dados, value_input_option="USER_ENTERED")
        
        st.cache_data.clear()
        return True

    except gspread.exceptions.APIError as exc:
        st.error(f"❌ API Google Sheets ({worksheet_name}): {exc}")
        return False
    except Exception as exc:
        st.error(f"❌ Erro ao gravar '{worksheet_name}': {exc}")
        st.exception(exc)
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# [2] CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
class Config:
    APP_NOME   = "Gestão de Ativos TOTALE"
    APP_ICONE  = "👷"
    APP_VERSAO = "4.0.0"
    SHEET_ID   = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"

    ABAS = {
        "ativos":     "lista_ativos",
        "desligados": "desligados",
        "auditoria":  "log_auditoria",
    }

    COL_ATIVOS = ["RE","Login","Técnico","Monitor","Base","Situação","Ultima_Modificacao"]
    COL_DESLIG = ["RE","Login","Técnico","Monitor","Base","Situação",
                  "Ultima_Modificacao","Data_Desligamento","Motivo"]
    COL_AUDIT  = ["Data","Usuario","Perfil","Acao","Alvo","Detalhe"]

    SITS_ATIVAS = ["ATIVO","FÉRIAS","INOPERANTE","ETN","AFASTADO"]
    SITS_SAIDA  = ["DESLIGADO","INATIVO"]
    MOTIVOS     = [
        "PEDIDO DE DEMISSÃO","DEMISSÃO SEM JUSTA CAUSA",
        "DEMISSÃO POR JUSTA CAUSA","FIM DE CONTRATO",
        "TRANSFERÊNCIA","ABANDONO DE EMPREGO","OUTROS",
    ]
    CACHE_TTL = 300
    COR = {
        "ATIVO":"#059669","FÉRIAS":"#F59E0B","INOPERANTE":"#DC2626",
        "ETN":"#7C3AED","AFASTADO":"#6B7280","DESLIGADO":"#374151","INATIVO":"#1F2937",
    }

    @staticmethod
    def usuarios() -> Dict[str,dict]:
        try:
            raw = dict(st.secrets.get("usuarios", {}))
            return {
                str(login): {
                    "senha": Safe.str(d.get("senha","")),
                    "nome":  Safe.str(d.get("nome",login)),
                    "role":  Safe.str(d.get("role","leitura")),
                    "bases": [Safe.str(b) for b in list(d.get("bases",[]))],
                }
                for login, d in raw.items()
            }
        except Exception:
            return {}


# ═══════════════════════════════════════════════════════════════════════════════
# [3] REPOSITÓRIO
#   LEITURA  → streamlit-gsheets  (conn.read)
#   ESCRITA  → gspread direto     (_gravar_gspread)
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=Config.CACHE_TTL, show_spinner=False)
def _fetch(chave: str, colunas: Tuple[str, ...]) -> pd.DataFrame:
    """Leitura via gspread direto (sem bug 400 do streamlit-gsheets)."""
    worksheet_name = Config.ABAS.get(chave, chave)
    empty = pd.DataFrame(columns=list(colunas))
    
    try:
        ws = _gspread_sheet(worksheet_name)
        
        # get_all_records retorna list[dict] com cabeçalhos como chaves
        registros = ws.get_all_records(
            empty2zero=False,
            head=1,
            default_blank=""
        )
        
        if not registros:
            return empty
        
        df = pd.DataFrame(registros)
        
        # Normalizar colunas
        df.columns = [Safe.str(c, f"c{i}") for i, c in enumerate(df.columns)]
        df = Safe.limpar_df(df)
        df = Safe.garantir_colunas(df, list(colunas))
        
        # Remover linhas com PK vazia
        pk = list(colunas)[0]
        df = df[df[pk].str.strip() != ""]
        
        return df.reset_index(drop=True)
    
    except gspread.exceptions.WorksheetNotFound:
        st.warning(f"⚠️ Aba **'{worksheet_name}'** não encontrada. Crie-a no Google Sheets.")
        return empty
    
    except gspread.exceptions.APIError as exc:
        msg = str(exc).lower()
        if "400" in msg:
            st.error(f"❌ HTTP 400 em '{worksheet_name}': verifique o nome da aba.")
        elif "403" in msg:
            st.error(f"❌ HTTP 403 em '{worksheet_name}': sem permissão. Compartilhe a planilha.")
        elif "404" in msg:
            st.error(f"❌ HTTP 404 em '{worksheet_name}': planilha não encontrada.")
        else:
            st.error(f"❌ API ({worksheet_name}): {exc}")
        return empty
    
    except Exception as exc:
        st.warning(f"⚠️ Erro leitura '{worksheet_name}': {exc}")
        return empty


class Repo:
    sid = Config.SHEET_ID

    def ler(self, chave: str, cols: List[str]) -> pd.DataFrame:
        return _fetch(chave, tuple(cols)).copy()

    def gravar(self, chave: str, df: pd.DataFrame) -> bool:
        worksheet = Config.ABAS.get(chave, chave)
        return _gravar_gspread(worksheet, df)

    def hierarquia(self) -> pd.DataFrame:
        df = self.ler("ativos", ["Login","Técnico","Monitor","Base"])
        return df.drop_duplicates(subset=["Login"]).reset_index(drop=True)

    def log(self, usr: str, perfil: str, acao: str, alvo: str, detalhe: str=""):
        try:
            df   = self.ler("auditoria", Config.COL_AUDIT)
            nova = pd.DataFrame([{
                "Data":    datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "Usuario": Safe.str(usr),   "Perfil":  Safe.str(perfil),
                "Acao":    Safe.str(acao),  "Alvo":    Safe.str(alvo),
                "Detalhe": Safe.str(detalhe),
            }])
            self.gravar("auditoria", pd.concat([df,nova], ignore_index=True))
        except Exception as exc:
            st.warning(f"⚠️ Log não registrado: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# [4] MODELOS
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class Usuario:
    login:str; nome:str; role:str; bases:List[str]=field(default_factory=list)
    def pode(self, a:str)->bool:
        P={
            "admin":      {"ler","escrever","editar","desligar","importar","auditoria"},
            "supervisor": {"ler","escrever","editar","desligar","importar"},
            "operador":   {"ler","escrever","editar"},
            "leitura":    {"ler"},
        }
        return a in P.get(self.role, set())

@dataclass
class Tecnico:
    RE:str; Login:str; Técnico:str; Monitor:str; Base:str; Situação:str
    Ultima_Modificacao:str=""
    def normalizar(self)->"Tecnico":
        self.RE=Safe.upper(self.RE); self.Login=Safe.lower(self.Login)
        self.Técnico=Safe.upper(self.Técnico); self.Monitor=Safe.upper(self.Monitor)
        self.Base=Safe.upper(self.Base);       self.Situação=Safe.upper(self.Situação)
        return self


# ═══════════════════════════════════════════════════════════════════════════════
# [5] SERVIÇOS
# ═══════════════════════════════════════════════════════════════════════════════
class Svc:
    def __init__(self, repo:Repo): self.r=repo

    def _f(self, df:pd.DataFrame, usr:Usuario)->pd.DataFrame:
        if usr.role=="admin" or not usr.bases: return df
        return df[df["Base"].str.upper().isin([b.upper() for b in usr.bases])]

    def ativos(self, usr:Usuario)->pd.DataFrame:
        return self._f(self.r.ler("ativos",Config.COL_ATIVOS), usr)

    def desligados(self, usr:Usuario)->pd.DataFrame:
        return self._f(self.r.ler("desligados",Config.COL_DESLIG), usr)

    def hierarquia(self)->pd.DataFrame: return self.r.hierarquia()

    def cadastrar(self, tec:Tecnico, usr:Usuario)->bool:
        tec.normalizar()
        df=self.r.ler("ativos",Config.COL_ATIVOS)
        if tec.RE and (df["RE"].str.upper()==tec.RE).any():
            st.error(f"RE {tec.RE} já existe."); return False
        tec.Ultima_Modificacao=f"{datetime.now():%d/%m/%y %H:%M} | Por {usr.login}"
        ok=self.r.gravar("ativos",pd.concat([df,pd.DataFrame([asdict(tec)])],ignore_index=True))
        if ok: self.r.log(usr.login,usr.role,"CADASTRO",tec.RE,f"{tec.Técnico}|{tec.Base}")
        return ok

    def editar(self, re:str, campo:str, novo:str, usr:Usuario)->bool:
        df=self.r.ler("ativos",Config.COL_ATIVOS)
        mask=df["RE"].str.upper()==Safe.upper(re)
        if not mask.any(): st.error(f"RE {re} não encontrado."); return False
        ant=df.loc[mask,campo].values[0]
        df.loc[mask,campo]=Safe.str(novo)
        df.loc[mask,"Ultima_Modificacao"]=f"{datetime.now():%d/%m/%y %H:%M} | Por {usr.login}"
        ok=self.r.gravar("ativos",df)
        if ok: self.r.log(usr.login,usr.role,"EDIÇÃO",re,f"{campo}:'{ant}'→'{novo}'")
        return ok

    def desligar(self, re:str, motivo:str, usr:Usuario)->bool:
        df_at=self.r.ler("ativos",Config.COL_ATIVOS)
        mask=df_at["RE"].str.upper()==Safe.upper(re)
        if not mask.any(): st.error(f"RE {re} não encontrado."); return False
        linha=df_at[mask].copy()
        linha["Situação"]="DESLIGADO"
        linha["Data_Desligamento"]=datetime.now().strftime("%d/%m/%Y %H:%M")
        linha["Motivo"]=Safe.str(motivo)
        df_de=pd.concat([self.r.ler("desligados",Config.COL_DESLIG),linha],ignore_index=True)
        df_at=df_at[~mask].reset_index(drop=True)
        ok=self.r.gravar("desligados",df_de) and self.r.gravar("ativos",df_at)
        if ok: self.r.log(usr.login,usr.role,"DESLIGAMENTO",re,motivo)
        return ok

    def importar(self, df_imp:pd.DataFrame, usr:Usuario)->tuple[int,int]:
        df_imp=Safe.limpar_df(df_imp)
        df_at=self.r.ler("ativos",Config.COL_ATIVOS)
        exist=set(df_at["RE"].str.upper())
        novos,falhas=[],0
        for _,row in df_imp.iterrows():
            re=Safe.upper(row.get("RE",""))
            if not re or re in exist: falhas+=1; continue
            tec=Tecnico(
                RE=re, Login=Safe.lower(row.get("Login","")),
                Técnico=Safe.upper(row.get("Técnico",row.get("Tecnico",""))),
                Monitor=Safe.upper(row.get("Monitor","")),
                Base=Safe.upper(row.get("Base","")),
                Situação=Safe.upper(row.get("Situação","ATIVO")),
                Ultima_Modificacao=f"{datetime.now():%d/%m/%y %H:%M}|Import {usr.login}",
            ).normalizar()
            novos.append(asdict(tec)); exist.add(re)
        if novos:
            self.r.gravar("ativos",pd.concat([df_at,pd.DataFrame(novos)],ignore_index=True))
            self.r.log(usr.login,usr.role,"IMPORTAÇÃO",f"{len(novos)}",f"{falhas} ignorados")
        return len(novos),falhas


# ═══════════════════════════════════════════════════════════════════════════════
# [6] DESIGN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
class DS:
    _T={
        "light":{"p":"#012869","s":"#059669","a":"#DC2626","av":"#D97706",
                 "t":"#1F2937","f":"#F1F5F9","su":"#FFFFFF","b":"#E2E8F0"},
        "dark": {"p":"#60A5FA","s":"#34D399","a":"#F87171","av":"#FCD34D",
                 "t":"#F1F5F9","f":"#0F172A","su":"#1E293B","b":"#334155"},
    }
    @classmethod
    def css(cls,m="light"):
        t=cls._T.get(m,cls._T["light"])
        st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Manrope:wght@800&display=swap');
        html,body,[data-testid="stAppViewContainer"]{{background:{t['f']}!important;font-family:'Inter',sans-serif!important;color:{t['t']}!important;}}
        [data-testid="stSidebar"]{{background:{t['su']}!important;border-right:1px solid {t['b']};}}
        .kpi{{background:{t['su']};padding:1.2rem 1.4rem;border-radius:14px;border-left:5px solid {t['p']};
              box-shadow:0 2px 8px rgba(0,0,0,.06);transition:transform .15s;margin-bottom:.5rem;}}
        .kpi:hover{{transform:translateY(-2px);}}
        .kpi.v{{border-left-color:{t['s']};}} .kpi.a{{border-left-color:{t['a']};}} .kpi.av{{border-left-color:{t['av']};}}
        .kpi-l{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;opacity:.55;}}
        .kpi-n{{font-size:1.9rem;font-weight:800;font-family:'Manrope',sans-serif;color:{t['p']};}}
        .kpi-s{{font-size:.72rem;opacity:.45;margin-top:.2rem;}}
        .hero{{background:linear-gradient(120deg,#0F172A 0%,#1E3A5F 55%,#1E40AF 100%);padding:2rem 2.5rem;border-radius:18px;color:#fff;margin-bottom:1.6rem;box-shadow:0 10px 28px rgba(0,0,0,.22);}}
        .hero h1{{margin:0;font-size:1.85rem;font-family:'Manrope',sans-serif;font-weight:800;}}
        .hero p{{opacity:.75;margin:.4rem 0 0;}} .hero-b{{display:inline-block;background:rgba(255,255,255,.15);padding:3px 14px;border-radius:20px;font-size:11px;font-weight:700;margin-top:.6rem;}}
        .sec{{font-family:'Manrope',sans-serif;font-weight:800;font-size:1.15rem;color:{t['p']};margin:1.2rem 0 .7rem;}}
        ::-webkit-scrollbar{{width:5px;height:5px;}} ::-webkit-scrollbar-thumb{{background:{t['b']};border-radius:3px;}}
        </style>""",unsafe_allow_html=True)

    @staticmethod
    def hero(t,s,b=""): st.markdown(f'<div class="hero"><h1>{t}</h1><p>{s}</p><span class="hero-b">{b}</span></div>',unsafe_allow_html=True)
    @staticmethod
    def sec(i,t): st.markdown(f'<div class="sec">{i}&nbsp;{t}</div>',unsafe_allow_html=True)
    @staticmethod
    def kpi(col,l,v,s="",tema=""):
        c={"v":"v","a":"a","av":"av"}.get(tema,"")
        col.markdown(f'<div class="kpi {c}"><div class="kpi-l">{l}</div><div class="kpi-n">{v}</div><div class="kpi-s">{s}</div></div>',unsafe_allow_html=True)
    @staticmethod
    def vazio(m="Sem dados."): st.markdown(f'<div style="text-align:center;padding:3rem;opacity:.38;"><div style="font-size:3rem">📭</div><p>{m}</p></div>',unsafe_allow_html=True)
    @staticmethod
    def badge(role):
        M={"admin":("#1E40AF","#DBEAFE"),"supervisor":("#065F46","#D1FAE5"),"operador":("#92400E","#FEF3C7"),"leitura":("#374151","#F3F4F6")}
        c,bg=M.get(role,("#374151","#F3F4F6"))
        return f'<span style="background:{bg};color:{c};padding:2px 10px;border-radius:12px;font-size:.72rem;font-weight:700;">{role.upper()}</span>'


# ═══════════════════════════════════════════════════════════════════════════════
# [7] HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _excel(df,aba="Dados")->bytes:
    b=BytesIO()
    with pd.ExcelWriter(b,engine="openpyxl") as w: df.to_excel(w,index=False,sheet_name=aba)
    return b.getvalue()
def _csv(df)->bytes: return df.to_csv(index=False,encoding="utf-8-sig").encode("utf-8-sig")
def exportar(df,p="dados"):
    ts=datetime.now().strftime("%Y%m%d_%H%M")
    c1,c2,*_=st.columns([1,1,4])
    c1.download_button("📥 Excel",_excel(df),f"{p}_{ts}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
    c2.download_button("📄 CSV",_csv(df),f"{p}_{ts}.csv","text/csv",use_container_width=True)
def fig_l(fig,**kw): fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(t=30,b=10,l=10,r=10),**kw)


# ═══════════════════════════════════════════════════════════════════════════════
# [8] VIEWS — TODAS COM KEYS ÚNICAS
# ═══════════════════════════════════════════════════════════════════════════════
def view_dashboard(df_raw, usr):
    DS.sec("📊", "Panorama Operacional")
    with st.expander("🔎 Filtros", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        ft = c1.text_input("🔍 Nome/RE/Login", key="dash_busca")
        fb = c2.multiselect("Base", sorted(df_raw["Base"].dropna().unique()), key="dash_base")
        fm = c3.multiselect("Monitor", sorted(df_raw["Monitor"].dropna().unique()), key="dash_monitor")
        fs = c4.multiselect("Situação", sorted(df_raw["Situação"].dropna().unique()), key="dash_situacao")
    
    df = df_raw.copy()
    if ft: df = df[df.apply(lambda r: ft.lower() in str(r).lower(), axis=1)]
    if fb: df = df[df["Base"].isin(fb)]
    if fm: df = df[df["Monitor"].isin(fm)]
    if fs: df = df[df["Situação"].isin(fs)]
    if df.empty: DS.vazio("Nenhum registro."); return

    tot = len(df)
    atv = (df["Situação"].str.upper() == "ATIVO").sum()
    fer = (df["Situação"].str.upper() == "FÉRIAS").sum()
    inop = (df["Situação"].str.upper() == "INOPERANTE").sum()
    
    k1, k2, k3, k4, k5 = st.columns(5)
    DS.kpi(k1, "Total", tot, f"{df['Base'].nunique()} bases")
    DS.kpi(k2, "Em Operação", atv, f"{atv/tot*100:.1f}% disponível", "v")
    DS.kpi(k3, "Em Férias", fer, "", "av")
    DS.kpi(k4, "Inoperantes", inop, "", "a")
    DS.kpi(k5, "Monitores", df["Monitor"].nunique(), "")
    st.divider()

    g1, g2 = st.columns(2)
    with g1:
        DS.sec("🗂️", "Por Situação")
        sit = df["Situação"].value_counts().reset_index()
        sit.columns = ["Situação", "Qtd"]
        fig = px.pie(sit, names="Situação", values="Qtd", hole=.5,
                     color_discrete_sequence=[Config.COR.get(s, "#94A3B8") for s in sit["Situação"]])
        fig_l(fig, legend=dict(orientation="h", y=-.22))
        st.plotly_chart(fig, use_container_width=True, key="dash_pie_situacao")
    
    with g2:
        DS.sec("🏢", "Por Base")
        bc = df.groupby(["Base", "Situação"]).size().reset_index(name="Qtd")
        fig2 = px.bar(bc, x="Base", y="Qtd", color="Situação", barmode="stack",
                      color_discrete_map=Config.COR)
        fig_l(fig2, xaxis_title="", yaxis_title="Técnicos", legend=dict(orientation="h", y=-.32))
        st.plotly_chart(fig2, use_container_width=True, key="dash_bar_base")

    DS.sec("🌡️", "Calor — Monitor × Base")
    pv = df.pivot_table(index="Monitor", columns="Base", values="RE", aggfunc="count", fill_value=0)
    if not pv.empty:
        fig3 = px.imshow(pv, text_auto=True, color_continuous_scale="Blues", aspect="auto")
        fig_l(fig3)
        st.plotly_chart(fig3, use_container_width=True, key="dash_heatmap")

    st.divider()
    DS.sec("📋", "Listagem")
    exportar(df, "ativos")
    st.dataframe(df, use_container_width=True, hide_index=True, key="dash_tabela")


def view_hierarquia(svc):
    DS.sec("🗂️", "Hierarquia")
    df = svc.hierarquia()
    if df.empty: DS.vazio("Hierarquia vazia."); return
    
    c1, c2, c3 = st.columns(3)
    fb = c1.multiselect("Base", sorted(df["Base"].unique()), key="hier_base")
    fm = c2.multiselect("Monitor", sorted(df["Monitor"].unique()), key="hier_monitor")
    fs = c3.text_input("🔍 Buscar", key="hier_busca")
    
    if fb: df = df[df["Base"].isin(fb)]
    if fm: df = df[df["Monitor"].isin(fm)]
    if fs: df = df[df.apply(lambda r: fs.lower() in str(r).lower(), axis=1)]
    
    k1, k2, k3 = st.columns(3)
    DS.kpi(k1, "Técnicos", len(df), "")
    DS.kpi(k2, "Monitores", df["Monitor"].nunique(), "")
    DS.kpi(k3, "Bases", df["Base"].nunique(), "")
    
    tree = df.groupby(["Base", "Monitor"]).size().reset_index(name="Técnicos")
    if not tree.empty:
        fig = px.treemap(tree, path=["Base", "Monitor"], values="Técnicos",
                         color="Técnicos", color_continuous_scale="Blues")
        fig_l(fig)
        st.plotly_chart(fig, use_container_width=True, key="hier_treemap")
    
    exportar(df, "hierarquia")
    st.dataframe(df, use_container_width=True, hide_index=True, key="hier_tabela")


def view_cadastro(svc, usr):
    DS.sec("➕", "Cadastrar Técnico")
    if not usr.pode("escrever"): st.warning("⛔ Sem permissão."); return
    
    hier = svc.hierarquia()
    bases = sorted(hier["Base"].unique()) if not hier.empty else []
    mons = sorted(hier["Monitor"].unique()) if not hier.empty else []
    
    with st.form("cad_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        re = c1.text_input("RE *", key="cad_re")
        nome = c1.text_input("Nome *", key="cad_nome")
        login = c1.text_input("Login *", key="cad_login")
        
        if bases:
            bi = c2.selectbox("Base *", [""] + bases, key="cad_base_sel")
        else:
            bi = c2.text_input("Base *", key="cad_base_txt")
        
        if mons:
            mi = c2.selectbox("Monitor *", [""] + mons, key="cad_monitor_sel")
        else:
            mi = c2.text_input("Monitor *", key="cad_monitor_txt")
        
        sit = c2.selectbox("Situação", Config.SITS_ATIVAS, key="cad_situacao")
        ok = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)
    
    if ok:
        erros = [k for k, v in [("RE", re), ("Nome", nome), ("Base", str(bi)), ("Monitor", str(mi))] if not Safe.str(v)]
        if erros:
            st.error(f"⛔ Obrigatórios: {', '.join(erros)}")
        else:
            tec = Tecnico(
                Safe.upper(re), Safe.lower(login), Safe.upper(nome),
                Safe.upper(str(mi)), Safe.upper(str(bi)), sit
            )
            with st.spinner("Salvando..."):
                ok2 = svc.cadastrar(tec, usr)
            if ok2:
                st.success("✅ Cadastrado!"); time.sleep(1); st.rerun()


def view_edicao(df_at, svc, usr):
    DS.sec("✏️", "Edição Rápida")
    if not usr.pode("editar"): st.warning("⛔ Sem permissão."); return
    if df_at.empty: DS.vazio("Sem ativos."); return
    
    re_sel = st.selectbox("RE:", sorted(df_at["RE"].unique()), key="ed_re")
    linha = df_at[df_at["RE"] == re_sel]
    if linha.empty: return
    
    row = linha.iloc[0]
    st.info(f"**{row['Técnico']}** | {row['Base']} | {row['Monitor']} | {row['Situação']}")
    
    campo = st.selectbox("Campo:", ["Técnico", "Login", "Monitor", "Base", "Situação"], key="ed_campo")
    
    if campo == "Situação":
        novo = st.selectbox("Novo:", Config.SITS_ATIVAS + Config.SITS_SAIDA, key="ed_novo_sit")
    else:
        novo = st.text_input("Novo:", value=Safe.str(row[campo]), key="ed_novo_txt")
    
    if st.button("💾 Aplicar", type="primary", key="ed_btn"):
        if not Safe.str(novo):
            st.error("Vazio.")
        else:
            with st.spinner("..."):
                ok = svc.editar(re_sel, campo, Safe.str(novo), usr)
            if ok:
                st.success("✅ Atualizado!"); time.sleep(1); st.rerun()


def view_desligamento(df_at, svc, usr):
    DS.sec("🚪", "Desligamento")
    if not usr.pode("desligar"): st.warning("⛔ Apenas admin/supervisor."); return
    if df_at.empty: DS.vazio("Sem ativos."); return
    
    c1, c2 = st.columns(2)
    re_sel = c1.selectbox("RE:", sorted(df_at["RE"].unique()), key="desl_re")
    motivo = c2.selectbox("Motivo:", Config.MOTIVOS, key="desl_motivo")
    
    linha = df_at[df_at["RE"] == re_sel]
    if not linha.empty:
        r = linha.iloc[0]
        st.info(f"**{r['Técnico']}** | {r['Base']} | {r['Monitor']}")
    
    conf = st.checkbox(f"✔️ Confirmo desligamento de **{re_sel}**", key="desl_conf")
    
    if st.button("🚨 Confirmar", type="primary", disabled=not conf, key="desl_btn"):
        with st.spinner("Processando..."):
            if svc.desligar(re_sel, motivo, usr):
                st.success("✅ Desligado!"); time.sleep(1.2); st.rerun()


def view_importacao(svc, usr):
    DS.sec("📤", "Importação em Lote")
    if not usr.pode("importar"): st.warning("⛔ Sem permissão."); return
    
    modelo = pd.DataFrame(columns=["RE", "Login", "Técnico", "Monitor", "Base", "Situação"])
    st.download_button(
        "⬇️ Modelo",
        _excel(modelo, "Modelo"),
        "modelo.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="imp_modelo"
    )
    
    arq = st.file_uploader("Arquivo:", type=["xlsx", "csv"], key="imp_arquivo")
    if arq is None: return
    
    try:
        df_imp = pd.read_csv(arq, dtype=str) if arq.name.endswith(".csv") else pd.read_excel(arq, dtype=str)
    except Exception as e:
        st.error(f"❌ {e}"); return
    
    df_imp = Safe.limpar_df(df_imp)
    st.dataframe(df_imp.head(20), use_container_width=True, key="imp_preview")
    st.caption(f"{len(df_imp)} linhas.")
    
    if st.button("🚀 Importar", type="primary", key="imp_btn"):
        with st.spinner("..."):
            ok, fl = svc.importar(df_imp, usr)
        st.success(f"✅ {ok} importados. ⚠️ {fl} ignorados.")
        time.sleep(1); st.rerun()


def view_desligados(svc, usr):
    DS.sec("🗃️", "Histórico Desligamentos")
    df = svc.desligados(usr)
    if df.empty: DS.vazio("Sem registros."); return
    
    d1, d2, d3 = st.columns(3)
    mv = df[df["Motivo"].str.strip() != ""]["Motivo"] if "Motivo" in df.columns else pd.Series(dtype=str)
    DS.kpi(d1, "Total", len(df), "")
    DS.kpi(d2, "Motivo Principal", mv.value_counts().idxmax() if not mv.empty else "—", "", "a")
    DS.kpi(d3, "Bases", df["Base"].nunique(), "")
    
    if not mv.empty:
        m = mv.value_counts().reset_index()
        m.columns = ["Motivo", "Qtd"]
        fig = px.bar(m, x="Qtd", y="Motivo", orientation="h", color_discrete_sequence=["#DC2626"])
        fig_l(fig)
        st.plotly_chart(fig, use_container_width=True, key="deslig_bar_motivos")
    
    exportar(df, "desligados")
    st.dataframe(df.iloc[::-1].reset_index(drop=True), use_container_width=True, hide_index=True, key="deslig_tabela")


def view_relatorios(svc, usr):
    DS.sec("📑", "Relatórios")
    df_at = svc.ativos(usr)
    df_de = svc.desligados(usr)
    r1, r2, r3, r4 = st.tabs(["📈 Monitor", "⚖️ Ativo×Deslig", "🧩 Base", "📅 Timeline"])
    
    with r1:
        if df_at.empty:
            DS.vazio("Sem dados.")
        else:
            mon = df_at.groupby("Monitor").size().reset_index(name="Técnicos").sort_values("Técnicos")
            fig = px.bar(mon, x="Técnicos", y="Monitor", orientation="h",
                         color="Técnicos", color_continuous_scale="Blues")
            fig_l(fig)
            st.plotly_chart(fig, use_container_width=True, key="rel_monitor_chart")
            exportar(mon, "rel_monitor")
    
    with r2:
        dfa = df_at[["Base"]].copy(); dfa["S"] = "ATIVO"
        dfd = df_de[["Base"]].copy(); dfd["S"] = "DESLIGADO"
        combo = pd.concat([
            dfa.rename(columns={"S": "Status"}),
            dfd.rename(columns={"S": "Status"})
        ], ignore_index=True)
        
        if not combo.empty:
            comp = combo.groupby(["Base", "Status"]).size().reset_index(name="Qtd")
            fig = px.bar(comp, x="Base", y="Qtd", color="Status", barmode="group",
                         color_discrete_map={"ATIVO": "#059669", "DESLIGADO": "#DC2626"})
            fig_l(fig)
            st.plotly_chart(fig, use_container_width=True, key="rel_comp_chart")
            exportar(comp, "rel_comp")
    
    with r3:
        if df_at.empty:
            DS.vazio("Sem dados.")
        else:
            bs = df_at.groupby(["Base", "Situação"]).size().reset_index(name="Qtd")
            fig = px.bar(bs, x="Qtd", y="Base", color="Situação", orientation="h",
                         barmode="stack", color_discrete_map=Config.COR)
            fig_l(fig)
            st.plotly_chart(fig, use_container_width=True, key="rel_base_chart")
            exportar(bs, "rel_base")
    
    with r4:
        cdt = "Data_Desligamento"
        if df_de.empty or cdt not in df_de.columns:
            DS.vazio("Sem dados.")
        else:
            try:
                df_tl = df_de[df_de[cdt].str.strip() != ""].copy()
                df_tl[cdt] = pd.to_datetime(df_tl[cdt], dayfirst=True, errors="coerce")
                df_tl = df_tl.dropna(subset=[cdt])
                df_tl["Mês"] = df_tl[cdt].dt.to_period("M").astype(str)
                tl = df_tl.groupby("Mês").size().reset_index(name="Desligamentos")
                fig = px.line(tl, x="Mês", y="Desligamentos", markers=True,
                              line_shape="spline", color_discrete_sequence=["#DC2626"])
                fig_l(fig)
                st.plotly_chart(fig, use_container_width=True, key="rel_timeline_chart")
                exportar(tl, "rel_timeline")
            except Exception as exc:
                DS.vazio(f"Erro: {exc}")


def view_auditoria(repo, usr):
    DS.sec("🔍", "Auditoria")
    if not usr.pode("auditoria"): st.warning("⛔ Acesso restrito."); return
    
    df = repo.ler("auditoria", Config.COL_AUDIT)
    if df.empty: DS.vazio("Sem logs."); return
    
    c1, c2, c3 = st.columns(3)
    fu = c1.multiselect("Usuário:", sorted(df["Usuario"].unique()), key="aud_usuario")
    fa = c2.multiselect("Ação:", sorted(df["Acao"].unique()), key="aud_acao")
    fd = c3.text_input("Detalhe:", key="aud_detalhe")
    
    if fu: df = df[df["Usuario"].isin(fu)]
    if fa: df = df[df["Acao"].isin(fa)]
    if fd: df = df[df["Detalhe"].str.contains(fd, case=False, na=False)]
    
    a1, a2, a3 = st.columns(3)
    DS.kpi(a1, "Eventos", len(df), "")
    DS.kpi(a2, "Usuários", df["Usuario"].nunique(), "")
    DS.kpi(a3, "Ações", df["Acao"].nunique(), "")
    
    ac = df["Acao"].value_counts().reset_index()
    ac.columns = ["Ação", "Qtd"]
    fig = px.bar(ac, x="Qtd", y="Ação", orientation="h", color_discrete_sequence=["#1E40AF"])
    fig_l(fig)
    st.plotly_chart(fig, use_container_width=True, key="aud_chart")
    
    exportar(df.iloc[::-1], "auditoria")
    st.dataframe(df.iloc[::-1].reset_index(drop=True), use_container_width=True, hide_index=True, key="aud_tabela")

# ═══════════════════════════════════════════════════════════════════════════════
# [9] LOGIN / MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def _init():
    for k,v in {"autenticado":False,"usuario":None,"tema":"light"}.items():
        if k not in st.session_state: st.session_state[k]=v

def tela_login():
    DS.css("light"); _,col,_=st.columns([1,1.4,1])
    with col:
        DS.hero(Config.APP_NOME,"Plataforma Corporativa",f"v{Config.APP_VERSAO}")
        with st.form("login"):
            u=st.text_input("👤 Usuário"); p=st.text_input("🔑 Senha",type="password")
            ok=st.form_submit_button("Entrar →",type="primary",use_container_width=True)
        if ok:
            dados=Config.usuarios().get(Safe.str(u))
            if dados and dados["senha"]==p:
                st.session_state.update({"autenticado":True,"usuario":Usuario(Safe.str(u),dados["nome"],dados["role"],dados["bases"])})
                st.rerun()
            else: st.error("❌ Credenciais inválidas.")

def tela_principal():
    usr:Usuario=st.session_state.usuario
    repo=Repo(); svc=Svc(repo)
    DS.css(st.session_state.tema)

    with st.sidebar:
        st.markdown(f'<div style="text-align:center;padding:1.2rem 0 .5rem"><div style="font-size:2.8rem">👷</div><div style="font-weight:800;font-size:1.05rem;margin:.3rem 0 .2rem">{usr.nome}</div>{DS.badge(usr.role)}<div style="opacity:.4;font-size:.72rem;margin-top:.4rem">v{Config.APP_VERSAO}</div></div>',unsafe_allow_html=True)
        st.divider()
        tema=st.toggle("🌙 Modo Escuro",value=st.session_state.tema=="dark")
        st.session_state.tema="dark" if tema else "light"
        st.divider()
        if st.button("🔄 Sincronizar",use_container_width=True): st.cache_data.clear(); st.rerun()
        if st.button("🚪 Sair",use_container_width=True): st.session_state.update({"autenticado":False,"usuario":None}); st.rerun()
        st.divider()
        if usr.bases: st.caption("**Bases:**\n"+"\n".join(f"• {b}" for b in usr.bases))
        else: st.caption("**Acesso:** todas as bases")

    DS.hero(Config.APP_NOME,f"Bem-vindo, {usr.nome}!",usr.role.upper())
    with st.spinner("Carregando..."): df_ativos=svc.ativos(usr)

    if df_ativos.empty:
        st.warning("⚠️ Aba `lista_ativos` vazia ou não encontrada.")
        if st.button("🔄 Tentar novamente"): st.cache_data.clear(); st.rerun()
        return

    abas=st.tabs(["📊 Dashboard","🗂️ Hierarquia","➕ Cadastro","✏️ Edição","🚪 Desligamento","📤 Importação","🗃️ Desligados","📑 Relatórios","🔍 Auditoria"])
    with abas[0]: view_dashboard(df_ativos,usr)
    with abas[1]: view_hierarquia(svc)
    with abas[2]: view_cadastro(svc,usr)
    with abas[3]: view_edicao(df_ativos,svc,usr)
    with abas[4]: view_desligamento(df_ativos,svc,usr)
    with abas[5]: view_importacao(svc,usr)
    with abas[6]: view_desligados(svc,usr)
    with abas[7]: view_relatorios(svc,usr)
    with abas[8]: view_auditoria(repo,usr)

def main():
    st.set_page_config(
        page_title=Config.APP_NOME,
        page_icon=Config.APP_ICONE,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    _init()
    
    # Suprimir "None" indesejado
    resultado = None
    if not st.session_state.autenticado:
        resultado = tela_login()
    else:
        resultado = tela_principal()
    
    # Não fazer nada com o resultado (evita "None" na tela)
    del resultado


if __name__ == "__main__":
    main()