import calendar
import datetime
from io import BytesIO
from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from plotly.graph_objects import Figure

from components.componentes import (
    Cores,
    Fontes,
    aplicar_estilo,
    render_hero_totale_2,
    render_insight,
    render_kpi,
)
from components.css_paginas import aplicar_css_tabela_corporativa
from components.dashboards import abrir_dashboard, fechar_dashboard, secao_exportacao
from components.graficos import ESCALA_TOTALE
from components.layout_pagina import cabecalho_secao, secao
from components.metricas_executivas import resumo_frequencia
from components.sidebar import render_page_sidebar_theme_selector
from services.dados_sessao import exigir_base, resumir_carga
from services.texto import escapar_html

st.set_page_config(
    page_title="Central de Performance",
    page_icon="📈",
    layout="wide",
)

aplicar_estilo()
render_page_sidebar_theme_selector()

# CSS extra só desta página (header azul + classes de meta + redução de fontes e scrollbar)
aplicar_css_tabela_corporativa(
    fonte_px=11,
    padding="5px 8px",
    altura_linha="1.2",
    fonte_celula_px=11,
    gradiente_cabecalho="linear-gradient(180deg, #012869 0%, #0A48AA 100%)",
    raio_scrollbar="4px",
    cabecalho_extra="border-right: 1px solid rgba(255,255,255,0.12) !important; padding: 6px 8px !important; position: sticky !important; top: 0 !important; z-index: 3 !important; text-align: left !important;",
)

st.markdown(
    """
    <style>
    /* --- TABELA CORPORATIVA --- */
    .corp-table td.meta-alta {
        background: #012869 !important; color: #FFFFFF !important;
        font-weight: 800 !important; text-align: center !important;
        border-left: 3px solid #011838 !important;
        font-size: 11px !important;
    }
    .corp-table td.meta-ok {
        background: #ECFDF5 !important; color: #047857 !important;
        font-weight: 700 !important; text-align: center !important;
        border-left: 3px solid #047857 !important;
        font-size: 11px !important;
    }
    .corp-table td.meta-prox {
        background: #FFFBEB !important; color: #92400E !important;
        font-weight: 700 !important; text-align: center !important;
        border-left: 3px solid #F59E0B !important;
        font-size: 11px !important;
    }
    .corp-table td.meta-baixa {
        font-weight: 700 !important; text-align: center !important;
        border-left: 3px solid #B91C1C !important;
        font-size: 11px !important;
    }
    .corp-table td.proj {
        background: #012869 !important; color: #FFFFFF !important;
        font-weight: 800 !important; text-align: center !important;
        border-left: 3px solid #64748B !important;
        font-size: 11px !important;
    }
    .corp-table tbody tr:nth-child(even) > td:not(.meta-alta):not(.meta-ok):not(.meta-prox):not(.meta-baixa):not(.proj) {
        background: #F8FAFC !important;
    }
    .corp-table tbody tr:hover > td:not(.meta-alta):not(.meta-ok):not(.meta-prox):not(.meta-baixa):not(.proj) {
        background: #EFF6FF !important;
    }
    .corp-table td:first-child { font-weight: 700 !important; }

    .rank-card-header {
        background: #FFFFFF;
        border-radius: 12px 12px 0 0;
        padding: 10px 16px;
        border: 1px solid #E2E8F0;
        border-bottom: none;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ====================================================
# BLOCO 1: HELPERS GLOBAIS
# ====================================================
#: Escape de HTML compartilhado (``services.texto``) — sem cópia local.
_escapar_html = escapar_html


def _eh_nulo(valor: Any) -> bool:
    if valor is None or valor is pd.NaT:
        return True
    if isinstance(valor, (list, tuple, dict, set, np.ndarray, pd.Series, pd.Index)):
        return False
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


def _para_float(valor: Any, default: float = 0.0) -> float:
    try:
        if _eh_nulo(valor):
            return default
        return float(valor)
    except (TypeError, ValueError):
        return default


def _converter_numero(valor: Any) -> float:
    if _eh_nulo(valor):
        return 0.0
    if isinstance(valor, (int, float, np.integer, np.floating)):
        return float(valor)
    texto = str(valor).strip().replace("\u00a0", "").replace(" ", "")
    if not texto:
        return 0.0
    try:
        return float(texto)
    except ValueError:
        pass
    negativo = texto.startswith("-")
    texto = texto.lstrip("-+")
    if "(" in texto and ")" in texto:
        negativo, texto = True, texto.strip("()")
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        numero = float(texto)
    except ValueError:
        return 0.0
    return -numero if negativo else numero


def _serie_numerica(serie: pd.Series) -> pd.Series:
    numerica = pd.to_numeric(serie, errors="coerce")
    nao_convertidos = numerica.isna() & serie.notna()
    if nao_convertidos.any():
        numerica = numerica.copy()
        numerica.loc[nao_convertidos] = serie[nao_convertidos].map(_converter_numero)
    return numerica.fillna(0.0)


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS
# ====================================================
class ComponenteVisual:
    @staticmethod
    def exibir_ticker(dados: list) -> None:
        if not dados:
            return

        html_itens = ""
        for item in dados:
            variacao = item.get("variacao", "")
            if variacao == "positiva":
                cor, simbolo = "#22c55e", "▲"
            elif variacao == "negativa":
                cor, simbolo = "#DC2626", "▼"
            elif variacao == "share":
                cor, simbolo = "#9DB9E4", "◴"
            else:
                cor, simbolo = "#94a3b8", "■"

            html_itens += (
                f'<span class="ticker-item">'
                f'<span class="ticker-label">{_escapar_html(item.get("label", ""))}:</span>'
                f'<span class="ticker-valor">{_escapar_html(item.get("valor", ""))}</span>'
                f'<span class="ticker-delta" style="color:{cor};">'
                f"{simbolo} {_escapar_html(item.get('delta', ''))}</span>"
                f"</span>"
                f'<span class="ticker-sep">|</span>'
            )

        duracao = max(20, min(90, len(dados) * 8))

        script_fallback = f"""
<script>
(function () {{
  var DUR = {duracao};
  var el = document.querySelector('.ticker-content');
  if (!el) return;
  var wrapper = el.parentElement;

  function cssRodando() {{
    try {{
      var anims = el.getAnimations ? el.getAnimations() : [];
      return anims.some(function (a) {{ return a.playState === 'running'; }});
    }} catch (e) {{ return false; }}
  }}

  window.setTimeout(function () {{
    if (cssRodando()) return;
    el.style.animation = 'none';
    var raf = window.requestAnimationFrame ||
              function (cb) {{ return window.setTimeout(function () {{ cb(Date.now()); }}, 16); }};
    var x = 0, ultimo = null, pausado = false, contador = 0, largura = el.scrollWidth / 2;

    if (wrapper) {{
      wrapper.addEventListener('mouseenter', function () {{ pausado = true; }});
      wrapper.addEventListener('mouseleave', function () {{ pausado = false; }});
    }}

    function passo(ts) {{
      if (ultimo === null) ultimo = ts;
      var dt = (ts - ultimo) / 1000;
      ultimo = ts;
      if (++contador % 30 === 0) largura = el.scrollWidth / 2;
      if (!pausado && largura > 0) {{
        x -= (largura / DUR) * dt;
        if (-x >= largura) x += largura;
        el.style.transform = 'translate3d(' + x + 'px, 0, 0)';
      }}
      raf(passo);
    }}
    raf(passo);
  }}, 300);
}})();
</script>
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;700&family=Plus+Jakarta+Sans:wght@700;800&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    overflow: hidden;
  }}
    .ticker-wrapper {{
    width: 100%;
    overflow: hidden;
    background: linear-gradient(90deg,#011838 0%,#012869 50%,#011838 100%);
    padding: 12px 0;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    position: relative;
  }}
  .ticker-wrapper::before, .ticker-wrapper::after {{
    content: ''; position: absolute; top: 0; bottom: 0;
    width: 60px; z-index: 2; pointer-events: none;
  }}
  .ticker-wrapper::before {{
    left: 0; background: linear-gradient(90deg,#011838,transparent);
  }}
  .ticker-wrapper::after {{
    right: 0; background: linear-gradient(90deg,transparent,#011838);
  }}
  .ticker-content {{
    display: flex; width: max-content;
    animation: scroll {duracao}s linear infinite;
  }}
  .ticker-wrapper:hover .ticker-content {{ animation-play-state: paused; }}
  @keyframes scroll {{
    0%   {{ transform: translate3d(0,0,0); }}
    100% {{ transform: translate3d(-50%,0,0); }}
  }}
  .ticker-item   {{ margin: 0 40px; font-size: 15px; white-space: nowrap; }}
  .ticker-label  {{ color: #94a3b8; font-weight: 500; }}
  .ticker-valor  {{ font-weight: 700; color: #FFFFFF; margin-left: 8px; }}
  .ticker-delta  {{ font-weight: 700; margin-left: 6px; font-size: 13px; }}
  .ticker-sep    {{ color: #334155; margin: 0 15px; }}
</style>
</head>
<body>
  <div class="ticker-wrapper">
    <div class="ticker-content">{html_itens}{html_itens}</div>
  </div>
  {script_fallback}
</body>
</html>
"""
        fn_iframe = getattr(st, "iframe", None)
        if callable(fn_iframe):
            fn_iframe(html, height=60)
        else:
            components.html(html, height=60, scrolling=False)

    @staticmethod
    def gerar_podio(ranking_df: pd.DataFrame) -> None:
        if len(ranking_df) < 3:
            render_insight("Necessário ao menos 3 equipes para o pódio.", tipo="alerta")
            return

        top3 = ranking_df.head(3).reset_index(drop=True)
        c2, c1, c3 = st.columns([1, 1.2, 1])

        def _medalha_html(nome: str, pontos: float, fundo: str, borda: str, icone: str) -> str:
            return (
                f'<div style="background-color:{fundo};border:2px solid {borda};'
                f"border-radius:10px;padding:15px;text-align:center;"
                f'box-shadow:0 4px 8px rgba(0,0,0,0.1);">'
                f'<h1 style="margin:0;font-size:30px;">{icone}</h1>'
                f'<h4 style="margin:5px 0;color:#334155;">{_escapar_html(nome)}</h4>'
                f'<h3 style="margin:0;color:{borda};">'
                f"{Utilitarios.formatar_decimal(pontos)} pts</h3>"
                f"</div>"
            )

        medalhas = [
            (c1, 0, "#FEF9C3", "#EAB308", "🥇 1º Lugar"),
            (c2, 1, "#F1F5F9", "#94A3B8", "🥈 2º Lugar"),
            (c3, 2, "#FFEDD5", "#F37C04", "🥉 3º Lugar"),
        ]
        for col, idx, fundo, borda, icone in medalhas:
            with col:
                st.markdown(
                    _medalha_html(
                        top3.iloc[idx]["Nome Equipe"],
                        top3.iloc[idx]["Pontos"],
                        fundo,
                        borda,
                        icone,
                    ),
                    unsafe_allow_html=True,
                )

    @staticmethod
    def gerar_insight_ia(media: float, dias_brutos: int) -> None:
        dias_txt = (
            f"Restam {dias_brutos} dia(s) útil(is) para o fechamento. "
            if dias_brutos > 0
            else "Último dia do período. "
        )
        if media >= 400:
            render_insight(
                f"**Visão da IA:** Operação em Alta Performance! "
                f"A média de {media:.1f} pts/equipe ultrapassa o teto máximo. "
                f"{dias_txt}Mantenha o ritmo para fechar o mês com recorde.",
                tipo="ok",
            )
        elif media >= 300:
            render_insight(
                f"**Visão da IA:** Operação Estável. "
                f"Média de {media:.1f} pts garante o atingimento da meta base. "
                f"{dias_txt}Foco em puxar os retardatários para garantir a projeção.",
                tipo="info",
            )
        else:
            render_insight(
                f"**Visão da IA:** Alerta de Performance! "
                f"A média de {media:.1f} pts está abaixo da linha de corte (300). "
                f"{dias_txt}Ação imediata necessária para reverter a tendência.",
                tipo="alerta",
            )

    @staticmethod
    def _classe_meta(val: Any) -> str:
        v = _para_float(val, default=float("-inf"))
        if v >= 400:
            return "meta-alta"
        if v >= 300:
            return "meta-ok"
        if v >= 275:
            return "meta-prox"
        return "meta-baixa"

    @staticmethod
    def render_ranking_html(
        df: pd.DataFrame,
        titulo: str = "",
        icone: str = "🏆",
        badge: str = "",
        modo_diario: bool = False,
        height: int = 450,
    ) -> None:
        if df.empty:
            render_insight("Nenhum dado disponível.", tipo="info")
            return

        badge_txt = badge or f"{len(df)} equipes"
        modo_txt = "📅 Meta Diária" if modo_diario else "📆 Acumulado do Mês"

        st.markdown(
            f"""
            <div class="rank-card-header">
                <span style="font-size:1.4rem;">{_escapar_html(icone)}</span>
                <div style="flex:1;">
                    <div style="font-family:{Fontes.TITULO};font-size:0.95rem;
                         font-weight:800;color:#0F172A;">{_escapar_html(titulo)}</div>
                    <div style="font-family:{Fontes.TEXTO};font-size:0.72rem;color:#64748B;
                         text-transform:uppercase;letter-spacing:0.05em;
                         font-weight:600;margin-top:2px;">{modo_txt}</div>
                </div>
                <span style="background:#DBEAFE;color:#1E40AF;
                     padding:5px 12px;border-radius:999px;
                     font-size:0.75rem;font-weight:700;">{_escapar_html(badge_txt)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        df_display = df.copy()
        renomear = {
            "Posição": "Rank",
            "CódAuxEquipe": "Cód. Equipe",
            "Nome Equipe": "Equipe",
            "Supervisor": "Supervisor",
            "Projeto": "Projeto",
            "Base": "Base",
            "Pontos": "Pontos",
            "Projeção": "Proj. Fechamento",
        }
        df_display = df_display.rename(
            columns={k: v for k, v in renomear.items() if k in df_display.columns}
        )

        if "Rank" in df_display.columns:
            df_display["Rank"] = df_display["Rank"].apply(Utilitarios.formatar_posicao)

        fmt: dict[str, Any] = {}
        for c in df_display.columns:
            if c in ("Pontos", "Proj. Fechamento") or "Meta" in str(c):
                fmt[c] = Utilitarios.formatar_decimal

        ComponenteVisual._tabela_ranking_colorida(
            df_display,
            fmt=fmt,
            height=height,
        )

    @staticmethod
    def _tabela_ranking_colorida(
        df: pd.DataFrame,
        fmt: dict[str, Any] | None = None,
        height: int = 450,
        max_rows: int = 300,
    ) -> None:
        df_show = df.head(max_rows).copy()
        cols = list(df_show.columns)
        fmt = fmt or {}

        def _fmt(val: Any, col: str) -> str:
            if _eh_nulo(val):
                return "—"
            if col in fmt and fmt[col] is not None:
                f = fmt[col]
                try:
                    if callable(f):
                        return str(f(val))
                    if isinstance(f, str):
                        return f.format(val)
                except (ValueError, TypeError, KeyError, IndexError):
                    pass
            return str(val)

        def _cls(val: Any, col: str) -> str:
            classes = []
            if col in ("Pontos", "Proj. Fechamento") or "Meta" in str(col):
                classes.append("num")
            if col == "Pontos":
                classes.append(ComponenteVisual._classe_meta(val))
            if col == "Proj. Fechamento":
                classes.append("proj")
            return " ".join(c for c in classes if c)

        header = "".join(f"<th>{_escapar_html(c)}</th>" for c in cols)
        rows = []
        for _, row in df_show.iterrows():
            tds = []
            for c in cols:
                v = row[c]
                display = _escapar_html(_fmt(v, c))
                cls = _cls(v, c)
                cls_attr = f' class="{cls}"' if cls else ""
                tds.append(f"<td{cls_attr}>{display}</td>")
            rows.append(f"<tr>{''.join(tds)}</tr>")

        html = f"""
        <div style="background:#FFFFFF;border-radius:0 0 12px 12px;
             border:1px solid #E2E8F0;border-top:none;overflow:hidden;
             box-shadow:0 4px 12px rgba(0,0,0,0.05);margin-bottom:16px;">
          <div class="corp-table-wrap" style="max-height:{int(height)}px; overflow-y:auto; overflow-x:auto; border:none;
               border-radius:0;box-shadow:none;margin:0;">
            <table class="corp-table">
              <thead><tr>{header}</tr></thead>
              <tbody>{"".join(rows)}</tbody>
            </table>
          </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

        if len(df) > max_rows:
            st.caption(f"Exibindo {max_rows} de {len(df)} equipes.")

    @staticmethod
    def render_tabela_html_custom(
        df: pd.DataFrame,
        formatacao: dict[str, Callable] | Callable | None = None,
        height: int = 400,
    ) -> None:
        """Renderiza tabela corporativa genérica com formatação segura contra erros de tipo."""
        if df.empty:
            return

        cols = list(df.columns)
        header = "".join(f"<th>{_escapar_html(c)}</th>" for c in cols)

        rows = []
        for _, row in df.iterrows():
            tds = []
            for c in cols:
                v = row[c]
                display = ""
                align = "left"

                # Trata caso de dicionário de formatadores por coluna
                if isinstance(formatacao, dict):
                    if c in formatacao and callable(formatacao[c]):
                        display = str(formatacao[c](v))
                        align = "center"
                    elif c in formatacao:
                        display = _escapar_html(str(formatacao[c]))
                        align = "center"
                    else:
                        display = _escapar_html(str(v) if not _eh_nulo(v) else "—")
                        if isinstance(v, (int, float, np.integer, np.floating)):
                            align = "center"
                # Trata caso de uma única função de formatador
                elif callable(formatacao):
                    display = str(formatacao(v))
                    align = "center"
                # Caso padrão sem formatador
                else:
                    display = _escapar_html(str(v) if not _eh_nulo(v) else "—")
                    if isinstance(v, (int, float, np.integer, np.floating)):
                        align = "center"

                tds.append(f"<td style='text-align: {align} !important;'>{display}</td>")
            rows.append(f"<tr>{''.join(tds)}</tr>")

        html = f"""
        <div style="background:#FFFFFF;border-radius:12px;
             border:1px solid #E2E8F0;overflow:hidden;
             box-shadow:0 4px 12px rgba(0,0,0,0.05);margin-bottom:16px;">
          <div class="corp-table-wrap" style="max-height:{int(height)}px; overflow-y:auto; overflow-x:auto; margin:0;">
            <table class="corp-table" style="width:100%; border-collapse:collapse;">
              <thead><tr>{header}</tr></thead>
              <tbody>{"".join(rows)}</tbody>
            </table>
          </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)


# ====================================================
# BLOCO 3: UTILITÁRIOS
# ====================================================
class Utilitarios:
    DIAS_UTEIS = "1111110"
    SABADO_CONTA = DIAS_UTEIS[5] == "1"

    COLUNAS_DATA = [
        "Data Agendamento",
        "Data Conclusão",
        "Data",
        "Date",
        "Data_Execucao",
    ]

    COLUNAS_BASE = ["Base", "BASE", "Região", "REGIÃO", "Regiao", "REGIAO", "Filial"]

    @staticmethod
    def encontrar_coluna_data(df: pd.DataFrame) -> str | None:
        for c in Utilitarios.COLUNAS_DATA:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def encontrar_coluna_base(df: pd.DataFrame) -> str | None:
        for c in Utilitarios.COLUNAS_BASE:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def normalizar_coluna_data(df: pd.DataFrame) -> pd.DataFrame:
        col_data = Utilitarios.encontrar_coluna_data(df)
        if not col_data:
            return df
        df = df.copy()
        df[col_data] = pd.to_datetime(df[col_data], errors="coerce")
        return df

    @staticmethod
    def calcular_variacao(vf: float, vg: float) -> tuple[str, str]:
        if vg == 0 or _eh_nulo(vg):
            return "neutra", "S/D"
        if abs(vf - vg) < 0.0001:
            return "neutra", "Visão Geral"
        p = ((vf - vg) / vg) * 100
        if p > 0:
            return "positiva", f"+{p:.1f}%"
        if p < 0:
            return "negativa", f"{p:.1f}%"
        return "neutra", "0%"

    @staticmethod
    def calcular_share(vf: float, vg: float) -> tuple[str, str]:
        if vg == 0 or _eh_nulo(vg):
            return "neutra", "0%"
        if abs(vf - vg) < 0.0001:
            return "neutra", "Visão Geral"
        return "share", f"{(vf / vg) * 100:.1f}% do Total"

    @staticmethod
    def formatar_numero(v: float) -> str:
        return f"{v:,.0f}".replace(",", ".")

    @staticmethod
    def formatar_decimal(v: float) -> str:
        texto = f"{_para_float(v):,.1f}"
        return texto.replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".")

    @staticmethod
    def formatar_posicao(valor: Any) -> str:
        try:
            v = int(valor)
        except (ValueError, TypeError):
            return str(valor)
        return {1: f"🥇 {v}º", 2: f"🥈 {v}º", 3: f"🥉 {v}º"}.get(v, f"{v}º")

    @staticmethod
    def calcular_dias_uteis(df: pd.DataFrame) -> tuple[int, int, datetime.date, int]:
        data_referencia: datetime.date
        col_data = Utilitarios.encontrar_coluna_data(df)
        if col_data is not None:
            serie = pd.to_datetime(df[col_data], errors="coerce")
            data_maxima = serie.max() if serie.notna().any() else None
        else:
            data_maxima = None

        if data_maxima is not None and not _eh_nulo(data_maxima):
            data_referencia = pd.Timestamp(data_maxima).date()
        else:
            data_referencia = datetime.date.today()

        ano, mes = data_referencia.year, data_referencia.month
        primeiro = datetime.date(ano, mes, 1)
        _, ult = calendar.monthrange(ano, mes)
        ultimo = datetime.date(ano, mes, ult)

        p_np = np.datetime64(primeiro)
        m_np = np.datetime64(data_referencia)
        u_np = np.datetime64(ultimo)

        total = int(
            np.busday_count(p_np, u_np + np.timedelta64(1, "D"), weekmask=Utilitarios.DIAS_UTEIS)
        )
        passados = int(
            np.busday_count(p_np, m_np + np.timedelta64(1, "D"), weekmask=Utilitarios.DIAS_UTEIS)
        )
        brutos = max(0, total - passados)
        seguros = max(1, brutos)
        return brutos, seguros, data_referencia, passados

    @staticmethod
    def exportar_excel(dataframe: pd.DataFrame) -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Ranking")
            ws = writer.sheets["Ranking"]

            cor_cab = PatternFill("solid", fgColor="012869")
            cor_par = PatternFill("solid", fgColor="F8FAFC")
            cor_impar = PatternFill("solid", fgColor="FFFFFF")
            cor_proj = PatternFill("solid", fgColor="303030")
            cor_alta = PatternFill("solid", fgColor="1F497D")
            cor_ok = PatternFill("solid", fgColor="C6EFCE")
            cor_proximo = PatternFill("solid", fgColor="FFEB9C")

            f_cab = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            f_branca = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            f_preta = Font(name="Calibri", size=11, bold=True, color="000000")
            f_verde = Font(name="Calibri", size=11, bold=True, color="006100")
            f_amarela = Font(name="Calibri", size=11, bold=True, color="9C5700")

            borda = Border(
                left=Side(style="thin", color="D9D9D9"),
                right=Side(style="thin", color="D9D9D9"),
                top=Side(style="thin", color="D9D9D9"),
                bottom=Side(style="thin", color="D9D9D9"),
            )
            centro = Alignment(horizontal="center", vertical="center")

            cols = list(dataframe.columns)
            col_int = [i + 1 for i, c in enumerate(cols) if c.lower() in ("posição", "posicao")]
            col_dec = [
                i + 1
                for i, c in enumerate(cols)
                if c.lower() not in ("posição", "posicao")
                and pd.api.types.is_numeric_dtype(dataframe[c])
            ]
            idx_proj = cols.index("Projeção") + 1 if "Projeção" in cols else -1
            idx_pontos = cols.index("Pontos") + 1 if "Pontos" in cols else -1

            for row in ws.iter_rows(
                min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column
            ):
                for cel in row:
                    cel.border = borda
                    if cel.row == 1:
                        cel.fill = cor_cab
                        cel.font = f_cab
                        cel.alignment = centro
                        continue

                    cel.fill = cor_par if cel.row % 2 == 0 else cor_impar

                    if cel.column == idx_proj:
                        cel.fill = cor_proj
                        cel.font = f_branca
                    elif cel.column == idx_pontos:
                        v = _para_float(cel.value, default=-1.0)
                        if v >= 400:
                            cel.fill = cor_alta
                            cel.font = f_branca
                        elif v >= 300:
                            cel.fill = cor_ok
                            cel.font = f_verde
                        elif v >= 275:
                            cel.fill = cor_proximo
                            cel.font = f_amarela
                        else:
                            cel.font = f_preta

                    if cel.column in col_int:
                        cel.number_format = "#,##0"
                    elif cel.column in col_dec:
                        cel.number_format = "#,##0.0"

            for col in ws.columns:
                letra = get_column_letter(col[0].column)
                max_len = max((len(str(c.value)) for c in col if c.value), default=0)
                ws.column_dimensions[letra].width = min(max(max_len + 3, 12), 42)

            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            ws.sheet_view.showGridLines = False

        return output.getvalue()


# ====================================================
# BLOCO 4: PROCESSAMENTO
# ====================================================
class ProcessamentoDados:
    CHAVES_GRUPO = ["Nome Equipe", "Supervisor", "Projeto"]

    @staticmethod
    def calcular_rankings(
        df: pd.DataFrame, dias_brutos: int, dias_seguros: int, dias_passados: int
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        colunas_minimas = ["Nome Equipe", "Pontos"]
        if any(c not in df.columns for c in colunas_minimas) or df.empty:
            return pd.DataFrame(), pd.DataFrame()

        trabalho = df.copy()
        chaves = [c for c in ProcessamentoDados.CHAVES_GRUPO if c in trabalho.columns]

        if "Nome Equipe" in trabalho.columns:
            for atributo in ("Supervisor", "Projeto", "CódAuxEquipe"):
                if atributo not in trabalho.columns:
                    continue
                mapa = (
                    trabalho.dropna(subset=[atributo])
                    .drop_duplicates(subset=["Nome Equipe"], keep="first")
                    .set_index("Nome Equipe")[atributo]
                )
                if not mapa.empty:
                    trabalho[atributo] = trabalho[atributo].fillna(
                        trabalho["Nome Equipe"].map(mapa)
                    )

        agregacoes: dict[str, Any] = {"Pontos": "sum"}
        if "CódAuxEquipe" in trabalho.columns:
            trabalho = trabalho.sort_values("CódAuxEquipe", key=lambda s: s.isna(), kind="stable")
            agregacoes["CódAuxEquipe"] = "first"

        base = (
            trabalho.groupby(chaves, dropna=False, as_index=False)
            .agg(agregacoes)
            .sort_values("Pontos", ascending=False)
            .reset_index(drop=True)
        )

        ordem = [
            c
            for c in (
                "CódAuxEquipe",
                "Nome Equipe",
                "Supervisor",
                "Projeto",
                "Pontos",
            )
            if c in base.columns
        ]
        base = base[ordem]

        base["Pontos"] = pd.to_numeric(base["Pontos"], errors="coerce").fillna(0.0)

        if "Dias Trab Tecnico" in df.columns:
            dias_por_equipe = df.groupby("Nome Equipe")["Dias Trab Tecnico"].max()
            dias_trab = (
                pd.to_numeric(base["Nome Equipe"].map(dias_por_equipe), errors="coerce")
                .fillna(float(dias_passados))
                .astype(float)
            )
        else:
            dias_trab = pd.Series(float(dias_passados), index=base.index, dtype=float)

        dias_trab = dias_trab.where(dias_trab > 0, 1.0)

        media_pts = base["Pontos"].div(dias_trab)
        projecao = base["Pontos"] + (media_pts * float(dias_brutos))

        def _montar(modo_dia: bool) -> pd.DataFrame:
            r = base.copy()
            r.insert(0, "Posição", range(1, len(r) + 1))
            for m in [300, 350, 375, 400]:
                label = f"Meta Dia | {m}" if modo_dia else f"Meta | {m}"
                if modo_dia:
                    r[label] = (r["Pontos"] - float(m)).div(float(dias_seguros))
                else:
                    r[label] = r["Pontos"] - float(m)
            r["Projeção"] = projecao.values
            return r

        return _montar(False), _montar(True)

    @staticmethod
    def calcular_saude_operacao(ranking: pd.DataFrame) -> pd.DataFrame:
        if ranking.empty or "Pontos" not in ranking.columns:
            return pd.DataFrame(columns=["Status", "count"])
        pts = pd.to_numeric(ranking["Pontos"], errors="coerce").fillna(0.0)
        cond = [
            pts >= 400.0,
            (pts >= 300.0) & (pts < 400.0),
            pts < 300.0,
        ]
        esc = ["Alta (400+)", "Na Meta (300-399)", "Abaixo (< 300)"]
        r = ranking.copy()
        r["Status"] = np.select(cond, esc, default="Sem Dados")
        return r["Status"].value_counts().reset_index()

    @staticmethod
    def ranking_supervisores(ranking: pd.DataFrame) -> pd.DataFrame:
        colunas = ["Supervisor", "Qtd_Equipes", "Total_Pontos", "Media_por_Equipe"]
        if ranking.empty or "Supervisor" not in ranking.columns:
            return pd.DataFrame(columns=colunas)

        sup = (
            ranking.groupby("Supervisor", dropna=False, as_index=False)
            .agg(Qtd_Equipes=("Nome Equipe", "count"), Total_Pontos=("Pontos", "sum"))
            .reset_index(drop=True)
        )
        sup["Total_Pontos"] = pd.to_numeric(sup["Total_Pontos"], errors="coerce").fillna(0.0)
        sup["Qtd_Equipes"] = pd.to_numeric(sup["Qtd_Equipes"], errors="coerce").fillna(1.0)
        sup["Qtd_Equipes"] = sup["Qtd_Equipes"].where(sup["Qtd_Equipes"] > 0, 1.0)

        sup["Supervisor"] = sup["Supervisor"].fillna("(Sem supervisor)")
        sup["Media_por_Equipe"] = sup["Total_Pontos"].div(sup["Qtd_Equipes"])
        return sup.sort_values("Media_por_Equipe", ascending=True)

    @staticmethod
    def calcular_aderencia(
        ranking: pd.DataFrame, coluna_grupo: str, meta: float = 300.0
    ) -> pd.DataFrame:
        if (
            ranking.empty
            or coluna_grupo not in ranking.columns
            or "Projeção" not in ranking.columns
        ):
            return pd.DataFrame()

        temp = ranking.copy()
        temp["_Atingiu"] = temp["Projeção"] >= meta

        ag = (
            temp.groupby(coluna_grupo, dropna=False)
            .agg(Equipes=("Nome Equipe", "count"), Atingiram=("_Atingiu", "sum"))
            .reset_index()
        )

        ag[coluna_grupo] = ag[coluna_grupo].fillna("(Sem classificação)")
        ag["Aderência"] = ag["Atingiram"].astype(float) / ag["Equipes"].astype(float)
        return ag.sort_values("Aderência", ascending=False)


# ====================================================
# BLOCO 5: GRÁFICOS
# ====================================================
class Graficos:
    @staticmethod
    def _layout(fig: Figure) -> Figure:
        fig.update_layout(
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.1)"),
        )
        return fig

    @staticmethod
    def barras_horizontal(df: pd.DataFrame, x: str, y: str) -> Figure:
        fig = px.bar(
            df,
            x=x,
            y=y,
            orientation="h",
            text_auto=True,
            color=x,
            color_continuous_scale=ESCALA_TOTALE,
        )
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", textfont_size=12)
        fig.update_yaxes(automargin=True)
        fig.update_xaxes(automargin=True)
        return Graficos._layout(fig)

    @staticmethod
    def rosca(df: pd.DataFrame, names: str, values: str) -> Figure:
        fig = px.pie(
            df,
            names=names,
            values=values,
            hole=0.6,
            color=names,
            color_discrete_map={
                "Alta (400+)": "#012869",
                "Na Meta (300-399)": "#047857",
                "Abaixo (< 300)": "#B91C1C",
            },
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        )
        return fig

    @staticmethod
    def linhas(df: pd.DataFrame, x: str, y: str, color: str) -> Figure:
        fig = px.line(df, x=x, y=y, color=color, markers=True)
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.1)"),
            margin=dict(l=0, r=0, t=30, b=0),
        )
        return fig


# ====================================================
# BLOCO 6: ABERTURA PADRÃO + BASE DA SESSÃO
# ====================================================
# A guarda de entrada é a do portal (``services.dados_sessao``): aceita
# DataFrame, dict de abas (Prod/Gpon) ou a lista legada, avisa no padrão oficial
# e interrompe a página quando não há carga — antes cada página reimplementava
# esse bloco de trinta linhas.
df = exigir_base(pagina="Produção Mensal")
if "Pontos" not in df.columns:
    df["Pontos"] = 0.0
df["Pontos"] = _serie_numerica(df["Pontos"])
df = Utilitarios.normalizar_coluna_data(df)

colunas_ausentes = [
    c for c in ("Nome Equipe", "Supervisor", "CódAuxEquipe", "Projeto") if c not in df.columns
]
if colunas_ausentes:
    render_insight(
        "Atenção: a planilha não trouxe a(s) coluna(s) "
        + ", ".join(f"**{c}**" for c in colunas_ausentes)
        + ". Os rankings por equipe/supervisor podem ficar incompletos. "
        "Verifique o arquivo carregado na página principal.",
        tipo="alerta",
    )
    for c in colunas_ausentes:
        df[c] = pd.NA

TOTAL_GERAL_PONTOS = float(df["Pontos"].sum())
TOTAL_GERAL_OS = len(df)
TOTAL_GERAL_EQUIPES = df["Nome Equipe"].nunique() if "Nome Equipe" in df.columns else 0
MEDIA_GERAL_PONTOS = TOTAL_GERAL_PONTOS / TOTAL_GERAL_EQUIPES if TOTAL_GERAL_EQUIPES > 0 else 0.0

#: Seções ancoradas do sumário (mesmos títulos usados em ``cabecalho_secao``).
SECOES_PAGINA: tuple[str, ...] = (
    "Indicadores",
    "Ranking & Metas",
    "Visão Executiva",
    "Aderência (Projeção)",
    "Evolução Temporal",
    "Frequência",
    "Exportação",
)


def render_hero_producao(registros: int | None = None) -> None:
    """Herói oficial da página (destaque = O.S. do recorte carregado)."""
    render_hero_totale_2(
        titulo="📈 Central de Performance | Produção por Técnico",
        subtitulo=(
            "Acompanhamento individual de execução, produtividade e performance em campo"
        ),
        badge_texto="Acompanhamento em tempo real da produção de técnicos e equipes",
        valor_destaque=(
            Utilitarios.formatar_numero(registros) if registros is not None else "—"
        ),
        label_destaque="O.S. NO RECORTE",
    )


# 1) Cabeçalho e contexto — padrão do portal: hero + chips + sumário com âncoras.
abrir_dashboard(
    "Central de Performance | Produção por Técnico",
    secoes=SECOES_PAGINA,
    hero=render_hero_producao,
    hero_kwargs={"registros": TOTAL_GERAL_OS},
    resumo=resumir_carga(st.session_state.get("dados_prod")),
    origem=str(st.session_state.get("origem_dados") or ""),
)


# ====================================================
# BLOCO 7: FILTROS
# ====================================================
CHAVES_FILTRO = ["sel_Projeto", "sel_Supervisor", "sel_Nome Equipe", "sel_Base"]

st.sidebar.header("🎯 Filtros Avançados")

col_base_df = Utilitarios.encontrar_coluna_base(df)

filtros_dinamicos = [
    ("Projeto", "Projeto:", "sel_Projeto"),
    ("Supervisor", "Supervisor:", "sel_Supervisor"),
    ("Nome Equipe", "Equipe:", "sel_Nome Equipe"),
]

if col_base_df:
    filtros_dinamicos.insert(0, (col_base_df, "Base / Região:", "sel_Base"))

for col_nome, label, chave in filtros_dinamicos:
    if col_nome in df.columns:
        opcoes = ["Todos"] + sorted(df[col_nome].dropna().astype(str).unique().tolist())
        sel = st.sidebar.selectbox(label, opcoes, key=chave)
        if sel != "Todos":
            df = df[df[col_nome].astype(str) == sel]

if st.sidebar.button("🔄 Limpar Filtros", key="btn_limpar_filtros"):
    for chave in CHAVES_FILTRO:
        st.session_state.pop(chave, None)
    st.rerun()

if df.empty:
    render_insight(
        "Nenhuma linha atende à combinação de filtros selecionada. "
        "Use **🔄 Limpar Filtros** na lateral para voltar à visão geral.",
        tipo="alerta",
    )
    st.stop()


# ====================================================
# BLOCO 8: CÁLCULOS + KPIs — SEÇÃO ANCORADA "INDICADORES"
# ====================================================
with secao(
    "Indicadores",
    icone="monitoring",
    subtitulo="Recorte atual comparado ao total carregado da base.",
    badge=f"{TOTAL_GERAL_OS} O.S. na base",
):
    dias_brutos, dias_seguros, ultima_atualizacao, dias_passados = Utilitarios.calcular_dias_uteis(df)

    total_equipes_filtro = df["Nome Equipe"].nunique() if "Nome Equipe" in df.columns else 0
    total_os_filtro = len(df)
    total_pontos_filtro = float(df["Pontos"].sum()) if "Pontos" in df.columns else 0.0
    media_pontos_filtro = (
        total_pontos_filtro / total_equipes_filtro if total_equipes_filtro > 0 else 0.0
    )

    var_pontos = Utilitarios.calcular_share(total_pontos_filtro, TOTAL_GERAL_PONTOS)
    var_os = Utilitarios.calcular_share(total_os_filtro, TOTAL_GERAL_OS)
    var_equipes = Utilitarios.calcular_share(total_equipes_filtro, TOTAL_GERAL_EQUIPES)
    var_media = Utilitarios.calcular_variacao(media_pontos_filtro, MEDIA_GERAL_PONTOS)

    ComponenteVisual.exibir_ticker(
        [
            {
                "label": "Pontos",
                "valor": Utilitarios.formatar_numero(total_pontos_filtro),
                "variacao": var_pontos[0],
                "delta": var_pontos[1],
            },
            {
                "label": "O.S.",
                "valor": Utilitarios.formatar_numero(total_os_filtro),
                "variacao": var_os[0],
                "delta": var_os[1],
            },
            {
                "label": "Equipes",
                "valor": str(total_equipes_filtro),
                "variacao": var_equipes[0],
                "delta": var_equipes[1],
            },
            {
                "label": "Média/Equipe",
                "valor": Utilitarios.formatar_numero(media_pontos_filtro),
                "variacao": var_media[0],
                "delta": var_media[1],
            },
        ]
    )

    ComponenteVisual.gerar_insight_ia(media_pontos_filtro, dias_brutos)

    c1, c2, c3, c4 = st.columns(4)
    render_kpi(
        c1,
        "Total Pontos · Geral",
        Utilitarios.formatar_numero(TOTAL_GERAL_PONTOS),
        tema="cinza",
    )
    render_kpi(
        c2,
        "Total Pontos · Filtro",
        Utilitarios.formatar_numero(total_pontos_filtro),
        sub=var_pontos[1],
        tema="azul",
    )
    render_kpi(c3, "Equipes · Filtro", str(total_equipes_filtro), sub=var_equipes[1], tema="verde")
    render_kpi(
        c4,
        "Total O.S. · Filtro",
        Utilitarios.formatar_numero(total_os_filtro),
        sub=var_os[1],
        tema="laranja",
    )

    st.divider()


# ====================================================
# BLOCO 9: ABAS E TABELAS CUSTOMIZADAS
# ====================================================
ranking = pd.DataFrame()
ranking_dia = pd.DataFrame()

if "Nome Equipe" in df.columns:
    ranking, ranking_dia = ProcessamentoDados.calcular_rankings(
        df, dias_brutos, dias_seguros, dias_passados
    )

aba_ranking, aba_executivo, aba_aderencia, aba_evolucao, aba_frequencia = st.tabs(
    [
        "🏆 Ranking & Metas",
        "👔 Visão Executiva",
        "🎯 Aderência (Projeção)",
        "📈 Evolução Temporal",
        "🗓️ Frequência",
    ]
)

# ── ABA 1 ──────────────────────────────────────────
with aba_ranking:
    cabecalho_secao("Ranking & Metas", icone="emoji_events", subtitulo="Pódio, metas e projeção por equipe.")
    cabecalho_secao("", ancora=False)
    ComponenteVisual.gerar_podio(ranking)

    st.write("")

    col_t, col_tg = st.columns([3, 1])
    with col_t:
        cabecalho_secao("", ancora=False)
    with col_tg:
        st.write("")
        por_dia = st.toggle("📅 **Modo Meta Diária**", key="tg_meta_dia")

    df_exibir = ranking_dia if por_dia else ranking
    modo_txt = "Meta Diária" if por_dia else "Meta Mensal"

    ComponenteVisual.render_ranking_html(
        df_exibir,
        titulo=f"Performance por Equipe — {modo_txt}",
        icone="🏆",
        badge=f"{len(df_exibir)} equipes ativas",
        modo_diario=por_dia,
        height=450,
    )

    col_dl1, col_dl2, _ = st.columns([1.5, 1.5, 5])
    nome_arq = "ranking_diario.xlsx" if por_dia else "ranking_geral.xlsx"

    with col_dl1:
        st.download_button(
            "📥 **Exportar Excel**",
            data=Utilitarios.exportar_excel(df_exibir),
            file_name=nome_arq,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with col_dl2:
        st.download_button(
            "📄 **Exportar CSV**",
            data=df_exibir.to_csv(index=False, decimal=",", sep=";").encode("utf-8-sig"),
            file_name=nome_arq.replace(".xlsx", ".csv"),
            mime="text/csv",
            width="stretch",
        )

    st.markdown(
        f"""
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:16px;
             padding:12px 16px;background:#F8FAFC;border-radius:8px;
             border:1px solid #E2E8F0;font-size:0.78rem;
             font-family:{Fontes.TEXTO};">
            <span style="font-weight:700;color:{Cores.TEXTO_3};
                 text-transform:uppercase;letter-spacing:0.05em;">🎨 Legenda:</span>
            <span style="background:#012869;color:white;padding:3px 10px;
                 border-radius:6px;font-weight:700;">🏆 400+ pts — Alta Performance</span>
            <span style="background:#ECFDF5;color:#047857;padding:3px 10px;
                 border-radius:6px;font-weight:700;">✅ 300-399 — Na Meta</span>
            <span style="background:#FFFBEB;color:#92400E;padding:3px 10px;
                 border-radius:6px;font-weight:700;">⚠️ 275-299 — Próximo da Meta</span>
            <span style="background:#FFFFFF;color:#B91C1C;padding:3px 10px;
                 border-radius:6px;font-weight:700;border-left:3px solid #B91C1C;">
                 ❌ Abaixo de 275</span>
            <span style="background:#012869;color:white;padding:3px 10px;
                 border-radius:6px;font-weight:700;">🎯 Projeção</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── ABA 2 ──────────────────────────────────────────
with aba_executivo:
    cabecalho_secao("Visão Executiva", icone="business_center", subtitulo="Saúde da operação e ranking de supervisores.")
    cabecalho_secao("", ancora=False)
    if ranking.empty:
        render_insight(
            "Sem equipes para analisar neste recorte de filtro. "
            "Verifique se a planilha possui a coluna **Nome Equipe**.",
            tipo="info",
        )
    else:
        c_e1, c_e2 = st.columns([1, 2])
        with c_e1:
            st.markdown("**Saúde da Operação (Faixa de Metas)**")
            df_saude = ProcessamentoDados.calcular_saude_operacao(ranking)
            st.plotly_chart(
                Graficos.rosca(df_saude, "Status", "count"),
                width="stretch",
                key="graf_saude",
            )
        with c_e2:
            st.markdown("**Ranking de Supervisores (Média pts por Equipe)**")
            df_sup = ProcessamentoDados.ranking_supervisores(ranking)
            if df_sup.empty:
                render_insight("Sem dados de supervisor no recorte atual.", tipo="info")
            else:
                st.plotly_chart(
                    Graficos.barras_horizontal(df_sup, "Media_por_Equipe", "Supervisor"),
                    width="stretch",
                    key="graf_sup",
                )

# ── ABA 3 (Aderência Custom HTML) ────────────────────────────────────────
with aba_aderencia:
    cabecalho_secao("Aderência (Projeção)", icone="track_changes", subtitulo="Equipes com projeção acima da meta de 300 pontos.")
    cabecalho_secao("", ancora=False)
    if ranking.empty:
        render_insight("Sem dados disponíveis para calcular a aderência.", tipo="info")
    else:

        def formata_aderencia(val):
            v = _para_float(val, default=0.0)
            if v > 0.75:
                cor_bg, cor_txt, cor_bd = "#047857", "#FFFFFF", "#047857"
            elif v >= 0.65:
                cor_bg, cor_txt, cor_bd = "#F59E0B", "#1F2937", "#D97706"
            else:
                cor_bg, cor_txt, cor_bd = "#B91C1C", "#FFFFFF", "#991B1B"

            pct = f"{v:.1%}".replace(".", ",")
            return f"<div style='background:{cor_bg}; color:{cor_txt}; border:1px solid {cor_bd}; padding:4px 8px; border-radius:6px; font-weight:800; display:inline-block; min-width:60px; text-align:center;'>{pct}</div>"

        fmt_aderencia = {
            "Equipes": lambda v: f"<b>{int(_para_float(v))}</b>",
            "Atingiram": lambda v: str(int(_para_float(v))),
            "Aderência": formata_aderencia,
        }

        col_ad_sup, col_ad_proj = st.columns(2)

        with col_ad_sup:
            st.markdown("#### Por Supervisor (Monitor)")
            df_ad_sup = ProcessamentoDados.calcular_aderencia(ranking, "Supervisor", meta=300.0)
            if not df_ad_sup.empty:
                ComponenteVisual.render_tabela_html_custom(df_ad_sup, fmt_aderencia, height=450)
            else:
                st.info("Sem dados de Supervisor.")

        with col_ad_proj:
            st.markdown("#### Por Projeto")
            df_ad_proj = ProcessamentoDados.calcular_aderencia(ranking, "Projeto", meta=300.0)
            if not df_ad_proj.empty:
                ComponenteVisual.render_tabela_html_custom(df_ad_proj, fmt_aderencia, height=450)
            else:
                st.info("Sem dados de Projeto. Verifique se a coluna 'Projeto' existe na planilha.")

        # Legenda minimalista para Aderência
        st.markdown(
            f"""
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:16px;
                 padding:12px 16px;background:#F8FAFC;border-radius:8px;
                 border:1px solid #E2E8F0;font-size:0.78rem;
                 font-family:{Fontes.TEXTO};">
                <span style="font-weight:700;color:{Cores.TEXTO_3};
                     text-transform:uppercase;letter-spacing:0.05em;">🎨 Legenda de Aderência:</span>
                <span style="background:#047857;color:white;padding:3px 10px;
                     border-radius:6px;font-weight:700;">🟢 > 75% — Alta Aderência</span>
                <span style="background:#F59E0B;color:#1F2937;padding:3px 10px;
                     border-radius:6px;font-weight:700;">🟡 65% - 75% — Atenção</span>
                <span style="background:#B91C1C;color:white;padding:3px 10px;
                     border-radius:6px;font-weight:700;">🔴 < 65% — Crítico</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── ABA 4 ──────────────────────────────────────────
with aba_evolucao:
    cabecalho_secao("Evolução Temporal", icone="trending_up", subtitulo="Curva de tendência diária das equipes.")
    col_data = Utilitarios.encontrar_coluna_data(df)
    cabecalho_secao("", ancora=False)
    if col_data and not ranking.empty:
        top5 = ranking.head(5)["Nome Equipe"].dropna().astype(str).tolist()
        df_ev = df[df["Nome Equipe"].astype(str).isin(top5)].copy()

        df_ev[col_data] = pd.to_datetime(df_ev[col_data], errors="coerce").dt.date
        df_ev = df_ev.dropna(subset=[col_data])

        if df_ev.empty:
            render_insight(
                "Não há datas válidas para as equipes do Top 5.",
                tipo="info",
            )
        else:
            df_ag = (
                df_ev.groupby([col_data, "Nome Equipe"], as_index=False)["Pontos"]
                .sum()
                .sort_values(col_data)
            )
            df_ag["Pontos Acumulados"] = df_ag.groupby("Nome Equipe")["Pontos"].cumsum()

            st.plotly_chart(
                Graficos.linhas(df_ag, col_data, "Pontos Acumulados", "Nome Equipe"),
                width="stretch",
                key="graf_linha",
            )
            st.caption(
                "Evolução de pontos acumulados das Top 5 equipes atuais (ordenada por data)."
            )
    else:
        render_insight(
            "Para ver a evolução, a planilha precisa de uma coluna de Data "
            "(ex: 'Data Agendamento' ou 'Data Conclusão').",
            tipo="info",
        )

# ── ABA 5 (Frequência Custom HTML) ──────────────────────────────────────────
with aba_frequencia:
    cabecalho_secao("Frequência", icone="calendar_month", subtitulo="Dias ativos em campo por equipe, supervisor e projeto.")
    cabecalho_secao("", ancora=False)
    col_data_frequencia = Utilitarios.encontrar_coluna_data(df)
    frequencia_base = resumo_frequencia(
        df,
        data_col=col_data_frequencia,
        supervisor_col="Supervisor" if "Supervisor" in df.columns else None,
        projeto_col="Projeto" if "Projeto" in df.columns else None,
    )

    if frequencia_base.empty:
        render_insight(
            "Não há equipe e data válidas para calcular frequência de produção.",
            tipo="info",
        )
    else:
        col_f_sup, col_f_proj, col_f_busca = st.columns([1.2, 1.2, 1.6])
        opcoes_sup_freq = sorted(
            [s for s in frequencia_base["Supervisor"].dropna().unique().tolist() if str(s).strip()]
        )
        opcoes_proj_freq = sorted(
            [p for p in frequencia_base["Projeto"].dropna().unique().tolist() if str(p).strip()]
        )
        with col_f_sup:
            sup_freq_sel = st.multiselect(
                "Filtrar Supervisor",
                options=opcoes_sup_freq,
                default=[],
                placeholder="Todos os supervisores",
                key="freq_filtro_supervisor",
            )
        with col_f_proj:
            proj_freq_sel = st.multiselect(
                "Filtrar Projeto",
                options=opcoes_proj_freq,
                default=[],
                placeholder="Todos os projetos",
                key="freq_filtro_projeto",
            )
        with col_f_busca:
            busca_freq_eq = st.text_input(
                "Buscar Equipe",
                value="",
                placeholder="Digite o nome ou código da equipe...",
                key="freq_filtro_equipe",
            )

        frequencia = frequencia_base.copy()
        if sup_freq_sel:
            frequencia = frequencia[frequencia["Supervisor"].isin(sup_freq_sel)]
        if proj_freq_sel:
            frequencia = frequencia[frequencia["Projeto"].isin(proj_freq_sel)]
        if busca_freq_eq.strip():
            termo_eq = busca_freq_eq.strip().lower()
            frequencia = frequencia[
                frequencia["Equipe"].astype(str).str.lower().str.contains(termo_eq, na=False)
            ]

        c_eq, c_sup_proj, c_dias, c_periodo = st.columns(4)
        max_dias = int(frequencia["Dias com produção"].max()) if not frequencia.empty else 1
        media_dias = float(frequencia["Dias com produção"].mean()) if not frequencia.empty else 0.0
        qtd_sup_freq = int(frequencia["Supervisor"].nunique()) if not frequencia.empty else 0
        qtd_proj_freq = int(frequencia["Projeto"].nunique()) if not frequencia.empty else 0

        # Base sem coluna de data reconhecida: o período fica "Indisponível"
        # em vez de derrubar a página com KeyError (regressão coberta em
        # tests/test_organizacao_dashboards.py::test_dashboards_rodam_sem_dados).
        if col_data_frequencia and col_data_frequencia in df.columns:
            serie_datas = pd.to_datetime(df[col_data_frequencia], errors="coerce")
            data_min, data_max = serie_datas.min(), serie_datas.max()
        else:
            data_min = data_max = pd.NaT
        periodo_str = (
            f"{data_min:%d/%m}–{data_max:%d/%m}"
            if pd.notna(data_min) and pd.notna(data_max)
            else "Indisponível"
        )

        render_kpi(
            c_eq,
            "Equipes com produção",
            f"{frequencia['Equipe'].nunique():,}".replace(",", "."),
            f"Média: {media_dias:.1f} dias ativos",
            "azul",
            "👷",
        )
        render_kpi(
            c_sup_proj,
            "Supervisores · Projetos",
            f"{qtd_sup_freq} · {qtd_proj_freq}",
            "Cobertura ativa no recorte",
            "roxo",
            "🧭",
        )
        render_kpi(
            c_dias,
            "Maior frequência observada",
            f"{max_dias} dias",
            f"{int(frequencia['Registros'].sum()):,} registros".replace(",", "."),
            "verde",
            "📅",
        )
        render_kpi(
            c_periodo,
            "Período dos registros",
            periodo_str,
            "Datas com produção lançada",
            "laranja",
            "🗓️",
        )

        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

        # Formatação Visual da Barra de Progresso de Frequência
        def formata_dias(val):
            v = _para_float(val, default=0.0)
            pct = (v / max_dias) * 100 if max_dias > 0 else 0
            grad = (
                "linear-gradient(90deg, #012869, #0A48AA)"
                if pct > 50
                else "linear-gradient(90deg, #F59E0B, #D97706)"
            )
            if pct <= 25:
                grad = "linear-gradient(90deg, #DC2626, #B91C1C)"

            return f"""
            <div style="display:flex; align-items:center; gap:12px;">
                <span style="font-weight:800; min-width:24px; color:#1E293B;">{int(v)}</span>
                <div style="flex:1; height:10px; background:#E2E8F0; border-radius:5px; overflow:hidden;">
                    <div style="width:{pct}%; height:100%; background:{grad}; border-radius:5px;"></div>
                </div>
            </div>
            """

        def formata_data_freq(val):
            if pd.isna(val):
                return "-"
            try:
                return pd.to_datetime(val).strftime("%d/%m/%Y")
            except Exception:
                return _escapar_html(val)

        fmt_freq = {
            "Equipe": lambda v: (
                f"<span style='font-weight:700; color:#0F172A;'>{_escapar_html(v)}</span>"
            ),
            "Supervisor": lambda v: (
                f"<span style='font-weight:600; color:#012869;'>{_escapar_html(v)}</span>"
            ),
            "Projeto": lambda v: (
                f"<span style='display:inline-block; padding:2px 8px; border-radius:999px; "
                f"background:#EFF6FF; color:#1E40AF; font-weight:700; font-size:10px;'>"
                f"{_escapar_html(v)}</span>"
            ),
            "Dias com produção": formata_dias,
            "Registros": lambda v: f"{int(_para_float(v)):,}".replace(",", "."),
            "Última atividade": formata_data_freq,
        }

        ComponenteVisual.render_tabela_html_custom(frequencia, fmt_freq, height=480)

        if not frequencia.empty:
            st.markdown("<div style='height: 14px'></div>", unsafe_allow_html=True)
            col_res_sup, col_res_proj = st.columns(2, gap="medium")
            with col_res_sup:
                cabecalho_secao("", ancora=False)
                freq_por_sup = (
                    frequencia.groupby("Supervisor", as_index=False)
                    .agg(
                        Equipes=("Equipe", "nunique"),
                        **{
                            "Média de Dias": ("Dias com produção", "mean"),
                            "Máx. Dias": ("Dias com produção", "max"),
                            "Registros": ("Registros", "sum"),
                        },
                    )
                    .sort_values(["Média de Dias", "Registros"], ascending=[False, False])
                    .reset_index(drop=True)
                )
                fmt_sup_freq = {
                    "Supervisor": lambda v: (
                        f"<span style='font-weight:700; color:#012869;'>{_escapar_html(v)}</span>"
                    ),
                    "Equipes": lambda v: f"{int(_para_float(v)):,}".replace(",", "."),
                    "Média de Dias": lambda v: f"{_para_float(v):.1f} dias".replace(".", ","),
                    "Máx. Dias": lambda v: f"{int(_para_float(v))} dias",
                    "Registros": lambda v: f"{int(_para_float(v)):,}".replace(",", "."),
                }
                ComponenteVisual.render_tabela_html_custom(
                    freq_por_sup, fmt_sup_freq, height=280
                )

            with col_res_proj:
                cabecalho_secao("", ancora=False)
                freq_por_proj = (
                    frequencia.groupby("Projeto", as_index=False)
                    .agg(
                        Equipes=("Equipe", "nunique"),
                        **{
                            "Média de Dias": ("Dias com produção", "mean"),
                            "Máx. Dias": ("Dias com produção", "max"),
                            "Registros": ("Registros", "sum"),
                        },
                    )
                    .sort_values(["Média de Dias", "Registros"], ascending=[False, False])
                    .reset_index(drop=True)
                )
                fmt_proj_freq = {
                    "Projeto": lambda v: (
                        f"<span style='font-weight:700; color:#0F172A;'>{_escapar_html(v)}</span>"
                    ),
                    "Equipes": lambda v: f"{int(_para_float(v)):,}".replace(",", "."),
                    "Média de Dias": lambda v: f"{_para_float(v):.1f} dias".replace(".", ","),
                    "Máx. Dias": lambda v: f"{int(_para_float(v))} dias",
                    "Registros": lambda v: f"{int(_para_float(v)):,}".replace(",", "."),
                }
                ComponenteVisual.render_tabela_html_custom(
                    freq_por_proj, fmt_proj_freq, height=280
                )

    st.caption(
        "Este indicador conta apenas datas com produção registrada. Não identifica faltas: "
        "para isso é necessária uma escala ou fonte explícita de presença."
    )

# ── Exportação e rodapé ─────────────────────────────
secao_exportacao(
    df_exibir if isinstance(df_exibir, pd.DataFrame) and not df_exibir.empty else df,
    nome_arquivo="producao_mensal",
    chave="pontos",
    titulo="Exportação",
    subtitulo="Recorte exibido no ranking (CSV utf-8-sig + Excel corporativo).",
)

_regra_dias = "seg a sáb" if Utilitarios.SABADO_CONTA else "seg a sex"
st.sidebar.divider()
st.sidebar.caption(
    f"🕒 **Última Atualização:**\n"
    f"{pd.to_datetime(ultima_atualizacao).strftime('%d/%m/%Y')}\n\n"
    f"📅 **Dias úteis ({_regra_dias}):** "
    f"{dias_passados} decorrido(s) · {dias_brutos} restante(s)"
)

fechar_dashboard()
