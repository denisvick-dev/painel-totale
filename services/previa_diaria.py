"""
services/previa_diaria.py
=========================
Motor de cálculo da **Prévia Diária** — camada pura, sem Streamlit.

Versão: 1.0.0
Autor: TOTALE Tecnologia

Motivo deste módulo
-------------------
A prévia diária da diretoria nasceu como um script único (``previa_totale.py``)
que misturava, no mesmo arquivo, leitura de uploads, regras de negócio,
integração com o Google Sheets e desenho da tabela. Consequência: nenhuma regra
podia ser testada sem abrir o app, e cada ajuste de layout arriscava mudar um
número da diretoria.

Aqui ficam **somente as regras** — normalização de nomes, classificação de
quebra, cruzamento ANIEL × TOA, consultivo, calendário, projeções e leitura do
e-mail de parados. A página ``pages/previa_totale.py`` cuida de upload, estado e
renderização.

Regras do módulo:

* nenhuma dependência de Streamlit — importável em testes e em scripts;
* nenhuma exceção por dado estranho: coluna ausente, ``NaN`` e texto vazio
  viram ``0``/``""`` e a taxa correspondente fica em ``0.0``;
* as contagens de Retorno WO e PME são por **contrato único**, não por O.S. —
  era a divergência histórica entre a prévia e a tela da TV;
* o calendário ignora domingos (regra da operação), como nas telas 5/6/18.

Funções principais:

* :func:`processar_planilha_consultivo` — contratos/produtos por base e
  supervisor, com hoje, acumulado e projeção mensal;
* :func:`calcular_metricas_completas` — produtividade, quebras, ND, GPON,
  migração, retorno WO e PME de um recorte (base ou supervisor);
* :func:`projetar_os` / :func:`projetar_consultivo` — projeção a partir do
  histórico persistido (média diária × dias úteis);
* :func:`processar_arquivo_msg` — técnicos parados por supervisor lidos do
  e-mail ``.msg``.
"""

from __future__ import annotations

import calendar
import io
import re
from datetime import date, datetime
from typing import Any, Sequence

import pandas as pd

from config.settings import FUSO_BR
from services.planilhas import ler_bytes
from services.texto import formatar_numero, normalizar_texto, sem_acento

VERSAO_PREVIA_DIARIA = "1.0.0"

#: Bases acompanhadas na prévia (mesmos nomes usados na navegação do portal).
BASES_PREVIA: tuple[str, ...] = ("NET-ABCDM", "NET-Guarulhos", "NET-LESTE")

#: Rótulo curto de cada base (coluna da tabela e abas do passo 2).
ROTULOS_BASES: dict[str, str] = {
    "NET-ABCDM": "ABCDM",
    "NET-Guarulhos": "Guarulhos",
    "NET-LESTE": "Leste",
}

#: Supervisores válidos por base — fonte única do filtro de equipe.
MAPA_SUPERVISORES_BASE: dict[str, tuple[str, ...]] = {
    "NET-ABCDM": ("EDSON MARCO", "MAICON", "NELSON", "APOIO"),
    "NET-Guarulhos": ("ADRIANO", "DANIELE", "FERNANDO", "PALOMA"),
    "NET-LESTE": ("ALAN", "ELISANGELA", "FRANCISCO", "FRANCISO", "JOAO CARLOS", "MIRON"),
}

#: Apelidos aceitos no e-mail de parados (nome completo → chave canônica).
ALIASES_SUPERVISORES: dict[str, tuple[str, ...]] = {
    "EDSON": ("EDSON MARCO", "EDSON"),
    "MAICON": ("MAICON FARIA", "MAICON APARECIDO", "MAICON"),
    "NELSON": ("NELSON JUNIOR", "NELSON ALVES", "NELSON"),
    "ADRIANO": ("ADRIANO NASCIMENTO", "ADRIANO"),
    "DANIELE": ("DANIELE BARBOSA", "DANIELE"),
    "FERNANDO": ("FERNANDO CESAR", "FERNANDO COELHO", "FERNANDO"),
    "PALOMA": ("PALOMA REGINA", "PALOMA"),
    "ALAN": ("ALAN DIAS", "ALAN DE ANDRADE", "ALAN"),
    "ELISANGELA": ("ELISANGELA CASSIMIRO", "ELISANGELA"),
    "FRANCISCO": (
        "FRANCISCO JUNIOR",
        "FRANCISO JUNIOR",
        "FRANCISCO GERALDO",
        "FRANCISO",
        "FRANCISCO",
    ),
    "JOAO CARLOS": ("JOAO CARLOS", "MIRON"),
}

#: Serviços que compõem o indicador ND (Novos Domicílios).
SERVICOS_ND_ALVOS: frozenset[str] = frozenset(
    {
        "ADESAO - INSTALACAO DE ASSINATURA",
        "ADESAO - INSTALACAO DE ASSINATURA DIGITAL",
        "ADESAO ENTREGA STREAMING",
        "ADESAO - ENTREGA STREAMING",
    }
)

#: Valores de Rota Inicial usados quando a imagem de resumo do dia é anexada.
ROTA_INICIAL_PADRAO: dict[str, int] = {
    "NET-ABCDM": 529,
    "NET-Guarulhos": 611,
    "NET-LESTE": 497,
}

#: Equipe montada de referência (fallback quando o Sheets não responde).
MONTADOS_PADRAO: dict[str, int] = {
    "NET-ABCDM": 74,
    "NET-Guarulhos": 78,
    "NET-LESTE": 77,
}

#: Rótulos das categorias de quebra.
CATEGORIA_INSTALACAO = "INSTALAÇÃO"
CATEGORIA_SERVICOS = "SERVIÇOS"
CATEGORIA_RETORNO = "RETORNO"

__all__ = [
    "ALIASES_SUPERVISORES",
    "BASES_PREVIA",
    "CATEGORIA_INSTALACAO",
    "CATEGORIA_RETORNO",
    "CATEGORIA_SERVICOS",
    "MAPA_SUPERVISORES_BASE",
    "MONTADOS_PADRAO",
    "ROTULOS_BASES",
    "ROTA_INICIAL_PADRAO",
    "SERVICOS_ND_ALVOS",
    "VERSAO_PREVIA_DIARIA",
    "buscar_os_inicial",
    "calcular_calendario_automatico",
    "classificar_aniel",
    "calcular_metricas_completas",
    "eh_retorno_credenciada",
    "filtrar_por_contrato_unico",
    "fmt_br",
    "identificar_base_e_supervisor_consultivo",
    "ler_planilha",
    "limpar_chave",
    "limpar_texto",
    "normalizar_nome_base",
    "obter_coluna_contrato",
    "ordenar_datas",
    "padrao_quebra_categoria",
    "processar_arquivo_msg",
    "processar_planilha_consultivo",
    "projetar_consultivo",
    "projetar_os",
]


# ====================================================
# 🔤 BLOCO 1: NORMALIZAÇÃO E FORMATAÇÃO
# ====================================================
def fmt_br(valor: Any, decimais: int = 0) -> str:
    """Número no padrão brasileiro (``1.234`` / ``12,5``); inválido vira ``0``."""
    return formatar_numero(valor, casas=decimais)


def limpar_texto(valor: Any) -> str:
    """Texto canônico: sem acento, maiúsculo e com espaços únicos."""
    return normalizar_texto(valor)


def normalizar_nome_base(valor: Any) -> str:
    """Nome canônico da base a partir de qualquer grafia (``ABC``, ``GRU``, ``Leste``)."""
    texto = str(valor or "").strip().upper()
    if "ABC" in texto:
        return "NET-ABCDM"
    if "GUA" in texto or "GRU" in texto:
        return "NET-Guarulhos"
    if "LES" in texto:
        return "NET-LESTE"
    return texto


def limpar_chave(valor: Any) -> str:
    """Chave de contrato/OS sem o ``.0`` que o Excel acrescenta a números."""
    if pd.isna(valor):
        return ""
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def padrao_quebra_categoria(valor: Any, tipo_servico_norm: str = "") -> str:
    """Classifica a coluna ``QUEBRAS`` em INSTALAÇÃO, SERVIÇOS ou RETORNO.

    Ordem das regras (idêntica à tela da TV): retorno explícito no serviço ou na
    descrição; instalação; serviços (mudança/manutenção/reparo/troca); por fim
    o tipo de serviço decide entre instalação e serviços.
    """
    descricao = limpar_texto(valor)
    tipo = limpar_texto(tipo_servico_norm)

    if "RET" in descricao or "RETORNO" in tipo:
        return CATEGORIA_RETORNO
    if "INS" in descricao:
        return CATEGORIA_INSTALACAO
    if "SERV" in descricao or "MUD" in descricao or "MANUT" in descricao:
        return CATEGORIA_SERVICOS
    if "REP" in descricao or "TROCA" in descricao:
        return CATEGORIA_SERVICOS

    if any(
        chave in tipo
        for chave in (
            "ADESAO",
            "INSTALACAO",
            "PONTO ADICIONAL",
            "NOVO PONTO",
            "MIGRACAO",
            "VENDA",
        )
    ):
        return CATEGORIA_INSTALACAO
    if tipo:
        return CATEGORIA_SERVICOS
    return ""


def eh_retorno_credenciada(serie_tipo_servico: pd.Series) -> pd.Series:
    """Máscara de serviços de retorno de credenciada (excluídos da prévia)."""
    normalizada = serie_tipo_servico.astype(str).apply(limpar_texto)
    return normalizada.str.contains("RETORNO", na=False) & normalizada.str.contains(
        "CREDENCIADA", na=False
    )


def obter_coluna_contrato(df: pd.DataFrame | None) -> str | None:
    """Nome da coluna de contrato (primeira que contiver ``contrato``)."""
    if df is None or df.empty:
        return None
    return next((c for c in df.columns if "contrato" in str(c).lower()), None)


def filtrar_por_contrato_unico(df: pd.DataFrame | None) -> pd.DataFrame:
    """Mantém uma linha por contrato (WO), descartando chaves vazias."""
    if df is None or df.empty:
        return pd.DataFrame()
    coluna = obter_coluna_contrato(df)
    if coluna and coluna in df.columns:
        temp = df.copy()
        temp["_chave_wo_"] = temp[coluna].apply(limpar_chave)
        temp = temp[temp["_chave_wo_"] != ""]
        return temp.drop_duplicates(subset=["_chave_wo_"], keep="first")
    return df


# ====================================================
# 🧭 BLOCO 2: CONSULTIVO (TELAS 5, 6 E 18 DA TV)
# ====================================================
def identificar_base_e_supervisor_consultivo(
    supervisor: Any, base_col: Any = ""
) -> tuple[str, str]:
    """Resolve ``(base, supervisor)`` a partir do supervisor e/ou da coluna base.

    O supervisor é procurado pelo primeiro nome em todas as bases; quando não há
    correspondência, a coluna de projeto/base decide. Sem nenhuma das duas, o
    registro é descartado (``("DESCARTADO", "DESCARTADO")``).
    """
    supervisor_norm = limpar_texto(supervisor)
    for base, supervisores in MAPA_SUPERVISORES_BASE.items():
        for canonico in supervisores:
            primeiro_nome = limpar_texto(canonico.split()[0])
            if primeiro_nome and primeiro_nome in supervisor_norm:
                nome_canonico = "FRANCISCO" if primeiro_nome == "FRANCISO" else canonico
                return base, nome_canonico

    if base_col:
        base_norm = normalizar_nome_base(base_col)
        if base_norm in MAPA_SUPERVISORES_BASE:
            return base_norm, supervisor_norm or "GERAL"
    return "DESCARTADO", "DESCARTADO"


def _normalizar_colunas_consultivo(df: pd.DataFrame) -> pd.DataFrame:
    """Cabeçalhos em ``MAIUSCULO_COM_UNDERSCORE`` (o arquivo vem com múltiplas abas)."""
    copia = df.copy()
    copia.columns = [
        re.sub(
            r"\s+",
            "_",
            sem_acento(str(coluna)).strip().upper(),
        )
        for coluna in copia.columns
    ]
    return copia


def _coluna_quantidade(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """Coluna de quantidade de produtos/O.S. e coluna de observação do consultivo."""
    coluna_qtd = next(
        (
            c
            for c in df.columns
            if "QTD" in str(c) and ("PRODUTO" in str(c) or "OS" in str(c) or "SERV" in str(c))
        ),
        None,
    )
    if not coluna_qtd:
        coluna_qtd = next(
            (
                c
                for c in df.columns
                if str(c) in {"QTD", "QUANTIDADE", "PRODUTOS", "QTD_PRODUTOS", "OS", "TOTAL_OS"}
            ),
            None,
        )
    coluna_obs = next(
        (c for c in df.columns if "OBSERVACAO" in str(c) or "OBS" in str(c)), None
    )
    return coluna_qtd, coluna_obs


def _extrair_qtd_obs(texto: Any) -> int:
    """Conta O.S. embutidas no texto de observação (números com 7+ dígitos)."""
    if pd.isna(texto):
        return 0
    if str(texto).strip() == "":
        return 0
    ajustado = str(texto).upper().replace("OC", "/")
    palavras = re.split(r"[\s/.,;:|\-()\[\]{}]+", ajustado)
    os_encontradas = [p.strip() for p in palavras if len(p.strip()) >= 7 and p.strip().isdigit()]
    return max(1, len(set(os_encontradas)))


def _parse_data_consistente(serie: pd.Series) -> pd.Series:
    """Converte a coluna de data aceitando BR (``dd/mm/aaaa``), ISO e fallback."""
    bruta = serie.astype(str).str.strip().str[:10]
    convertida = pd.to_datetime(bruta, format="%d/%m/%Y", errors="coerce")
    faltantes = convertida.isna()
    if faltantes.any():
        convertida.loc[faltantes] = pd.to_datetime(
            bruta.loc[faltantes], format="%Y-%m-%d", errors="coerce"
        )
    faltantes = convertida.isna()
    if faltantes.any():
        convertida.loc[faltantes] = pd.to_datetime(
            bruta.loc[faltantes], dayfirst=True, errors="coerce"
        )
    return convertida.dt.normalize()


def _contar_contratos(df: pd.DataFrame, coluna_contrato: str | None) -> int:
    """Contratos únicos (ou linhas, quando não há coluna de contrato válida)."""
    if df is None or df.empty:
        return 0
    if coluna_contrato and coluna_contrato in df.columns:
        chaves = df[coluna_contrato].dropna().astype(str).str.strip()
        chaves = chaves[~chaves.isin(["", "NAN", "NONE", "0", "0.0"])]
        if not chaves.empty:
            return int(chaves.nunique())
    return int(len(df))


def _resolver_data_referencia(data_ref_str: Any) -> datetime:
    """``dd/mm/aaaa`` → ``datetime``; qualquer falha usa o instante atual do Brasil."""
    try:
        return datetime.strptime(str(data_ref_str).strip(), "%d/%m/%Y")
    except (TypeError, ValueError):
        return datetime.now(FUSO_BR)


def _calendario_do_mes(hoje_ref: datetime) -> dict[str, int]:
    """Dias úteis (sem domingo) do mês, já trabalhados e restantes."""
    ano, mes = hoje_ref.year, hoje_ref.month
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    hoje_meia_noite = datetime(ano, mes, hoje_ref.day)
    primeiro_dia = datetime(ano, mes, 1)

    uteis_mes = 0
    passados = 0
    for dia in range(1, ultimo_dia + 1):
        data_loop = datetime(ano, mes, dia)
        if data_loop.weekday() == 6:  # domingo
            continue
        uteis_mes += 1
        if data_loop < hoje_meia_noite:
            passados += 1

    restantes = sum(
        1 for dia in range(hoje_ref.day, ultimo_dia + 1) if calendar.weekday(ano, mes, dia) != 6
    )
    return {
        "total_dias_uteis_mes": uteis_mes,
        "dias_uteis_passados": passados,
        "dias_restantes": max(1, restantes),
        "primeiro_dia_mes": primeiro_dia,
        "hoje_meia_noite": hoje_meia_noite,
    }


def processar_planilha_consultivo(
    df_cons_raw: pd.DataFrame,
    data_ref_str: Any,
) -> dict[str, Any]:
    """Replica a lógica de Consultivo das telas 5, 6 e 18.

    Devolve, por base canônica:

    * ``hoje_contratos`` / ``hoje_produtos`` — o que foi feito na data de referência;
    * ``acum_contratos`` / ``acum_produtos`` — acumulado do mês no arquivo;
    * ``proj_contratos`` / ``proj_produtos`` — projeção mensal (média diária do
      passado × dias úteis do mês, com piso no acumulado);
    * ``historico_diario`` — produtos por data (sincroniza com o Sheets);
    * ``supervisores`` — contratos/produtos do mês e de hoje por supervisor.
    """
    vazio = {
        "hoje_contratos": {base: 0 for base in BASES_PREVIA},
        "hoje_produtos": {base: 0 for base in BASES_PREVIA},
        "proj_contratos": {base: 0 for base in BASES_PREVIA},
        "proj_produtos": {base: 0 for base in BASES_PREVIA},
        "acum_contratos": {base: 0 for base in BASES_PREVIA},
        "acum_produtos": {base: 0 for base in BASES_PREVIA},
        "historico_diario": {base: {} for base in BASES_PREVIA},
        "supervisores": {base: {} for base in BASES_PREVIA},
        "dias_restantes": 1,
        "dias_uteis_passados": 0,
        "total_dias_uteis_mes": 0,
    }
    if not isinstance(df_cons_raw, pd.DataFrame) or df_cons_raw.empty:
        return vazio

    df_cons = _normalizar_colunas_consultivo(df_cons_raw)

    coluna_qtd, coluna_obs = _coluna_quantidade(df_cons)
    if coluna_qtd:
        df_cons["QTD_PRODUTOS_CALC"] = (
            pd.to_numeric(
                df_cons[coluna_qtd].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            .fillna(0)
            .astype(int)
        )
    elif coluna_obs:
        df_cons["QTD_PRODUTOS_CALC"] = df_cons[coluna_obs].apply(_extrair_qtd_obs)
    else:
        df_cons["QTD_PRODUTOS_CALC"] = 1

    coluna_sup = next((c for c in df_cons.columns if "SUPERV" in str(c)), None)
    coluna_base = next(
        (
            c
            for c in df_cons.columns
            if any(k in str(c) for k in ("PROJETO", "BASE", "REGIONAL", "CIDADE", "UNIDADE"))
        ),
        None,
    )

    bases: list[str] = []
    supervisores: list[str] = []
    for _, linha in df_cons.iterrows():
        valor_sup = linha.get(coluna_sup, "") if coluna_sup else ""
        valor_base = linha.get(coluna_base, "") if coluna_base else ""
        base_resolvida, supervisor_resolvido = identificar_base_e_supervisor_consultivo(
            valor_sup, valor_base
        )
        bases.append(base_resolvida)
        supervisores.append(supervisor_resolvido)

    df_cons["BASE_CLEAN"] = bases
    df_cons["SUPERVISOR_CLEAN"] = supervisores
    df_cards = df_cons[df_cons["BASE_CLEAN"] != "DESCARTADO"].copy()

    coluna_contrato = next(
        (
            c
            for c in df_cards.columns
            if any(k in str(c) for k in ("CONTRATO", "OS", "O.S", "PEDIDO", "PROPOSTA"))
        ),
        None,
    )

    hoje_ref = _resolver_data_referencia(data_ref_str)
    calendario = _calendario_do_mes(hoje_ref)
    hoje_meia_noite = calendario["hoje_meia_noite"]
    primeiro_dia_mes = calendario["primeiro_dia_mes"]
    dias_passados = calendario["dias_uteis_passados"]
    uteis_mes = calendario["total_dias_uteis_mes"]

    coluna_data = next(
        (c for c in df_cards.columns if "DATA" in str(c) or "DT" in str(c) or "DIA" in str(c)),
        None,
    )
    if coluna_data and not df_cards.empty:
        bruta = df_cards[coluna_data]
        if pd.api.types.is_datetime64_any_dtype(bruta):
            df_cards["DATA_OBJ"] = pd.to_datetime(bruta, errors="coerce").dt.normalize()
        else:
            df_cards["DATA_OBJ"] = _parse_data_consistente(bruta)
    else:
        df_cards["DATA_OBJ"] = hoje_meia_noite

    resultado: dict[str, Any] = {
        "hoje_contratos": {},
        "hoje_produtos": {},
        "proj_contratos": {},
        "proj_produtos": {},
        "acum_contratos": {},
        "acum_produtos": {},
        "historico_diario": {},
        "supervisores": {},
        "dias_restantes": calendario["dias_restantes"],
        "dias_uteis_passados": dias_passados,
        "total_dias_uteis_mes": uteis_mes,
    }

    for base in BASES_PREVIA:
        df_base = df_cards[df_cards["BASE_CLEAN"] == base].copy()
        if df_base.empty:
            resultado["hoje_contratos"][base] = 0
            resultado["hoje_produtos"][base] = 0
            resultado["proj_contratos"][base] = 0
            resultado["proj_produtos"][base] = 0
            resultado["acum_contratos"][base] = 0
            resultado["acum_produtos"][base] = 0
            resultado["historico_diario"][base] = {}
            resultado["supervisores"][base] = {}
            continue

        df_mes = df_base[
            df_base["DATA_OBJ"].notna()
            & (df_base["DATA_OBJ"].dt.year == hoje_ref.year)
            & (df_base["DATA_OBJ"].dt.month == hoje_ref.month)
        ].copy()
        if df_mes.empty:
            df_mes = df_base.copy()

        total_produtos_mes = int(df_mes["QTD_PRODUTOS_CALC"].sum())
        total_contratos_mes = _contar_contratos(df_mes, coluna_contrato)

        df_hoje = df_mes[df_mes["DATA_OBJ"] == hoje_meia_noite].copy()
        produtos_hoje = int(df_hoje["QTD_PRODUTOS_CALC"].sum()) if not df_hoje.empty else 0
        contratos_hoje = _contar_contratos(df_hoje, coluna_contrato) if not df_hoje.empty else 0

        df_passado = df_mes[
            (df_mes["DATA_OBJ"] >= primeiro_dia_mes) & (df_mes["DATA_OBJ"] < hoje_meia_noite)
        ].copy()
        produtos_passado = int(df_passado["QTD_PRODUTOS_CALC"].sum()) if not df_passado.empty else 0
        contratos_passado = (
            _contar_contratos(df_passado, coluna_contrato) if not df_passado.empty else 0
        )

        if dias_passados > 0 and produtos_passado > 0:
            proj_produtos = int(round(produtos_passado / dias_passados * uteis_mes))
            proj_contratos = int(round(contratos_passado / dias_passados * uteis_mes))
        elif produtos_hoje > 0:
            proj_produtos = int(round(produtos_hoje * uteis_mes))
            proj_contratos = int(round(contratos_hoje * uteis_mes))
        else:
            proj_produtos = total_produtos_mes
            proj_contratos = total_contratos_mes

        resultado["hoje_contratos"][base] = contratos_hoje
        resultado["hoje_produtos"][base] = produtos_hoje
        resultado["proj_contratos"][base] = max(proj_contratos, total_contratos_mes)
        resultado["proj_produtos"][base] = max(proj_produtos, total_produtos_mes)
        resultado["acum_contratos"][base] = total_contratos_mes
        resultado["acum_produtos"][base] = total_produtos_mes

        resultado["historico_diario"][base] = {
            data_valor.strftime("%d/%m/%Y"): int(grupo["QTD_PRODUTOS_CALC"].sum())
            for data_valor, grupo in df_mes.groupby("DATA_OBJ")
            if pd.notna(data_valor)
        }

        por_supervisor: dict[str, dict[str, int]] = {}
        for supervisor, grupo in df_mes.groupby("SUPERVISOR_CLEAN"):
            grupo_hoje = (
                df_hoje[df_hoje["SUPERVISOR_CLEAN"] == supervisor]
                if not df_hoje.empty
                else pd.DataFrame()
            )
            por_supervisor[str(supervisor)] = {
                "contratos_mes": _contar_contratos(grupo, coluna_contrato),
                "produtos_mes": int(grupo["QTD_PRODUTOS_CALC"].sum()),
                "contratos_hoje": _contar_contratos(grupo_hoje, coluna_contrato),
                "produtos_hoje": (
                    int(grupo_hoje["QTD_PRODUTOS_CALC"].sum()) if not grupo_hoje.empty else 0
                ),
            }
        resultado["supervisores"][base] = por_supervisor

    return resultado


# ====================================================
# 📊 BLOCO 3: MÉTRICAS DE PRODUTIVIDADE E QUEBRA
# ====================================================
def _metricas_vazias() -> dict[str, Any]:
    """Estrutura de retorno de :func:`calcular_metricas_completas` sem dados."""
    return {
        "tot_os": 0,
        "os_aberta": 0,
        "produtivo": 0,
        "quebra_geral": 0,
        "pontos": 0,
        "efic": 0.0,
        "media_os": 0.0,
        "proj_dia": 0,
        "os_canc": 0,
        "saiu_toa": 0,
        "q_ins": 0.0,
        "q_serv": 0.0,
        "tot_nd": 0,
        "q_nd": 0.0,
        "tot_gpon": 0,
        "q_gpon": 0.0,
        "tot_mig": 0,
        "q_mig": 0.0,
        "canc_mig": 0,
        "retorno_wo": 0,
        "tot_pme": 0,
        "q_pme": 0.0,
        "canc_pme": 0,
        "_raw_q_ins": 0,
        "_raw_tot_ins": 0,
        "_raw_q_serv": 0,
        "_raw_tot_serv": 0,
        "_raw_q_nd": 0,
        "_raw_tot_nd": 0,
        "_raw_q_gpon": 0,
        "_raw_tot_gpon": 0,
        "_raw_q_mig": 0,
        "_raw_tot_mig": 0,
        "_raw_q_pme": 0,
        "_raw_tot_pme": 0,
    }


def _taxa_quebra(df_grupo: pd.DataFrame | None) -> tuple[float, int, int]:
    """``(taxa %, improdutivas, denominador)`` de um recorte."""
    if df_grupo is None or df_grupo.empty or "Tipo de OS" not in df_grupo.columns:
        return 0.0, 0, 0
    improdutivas = len(df_grupo[df_grupo["Tipo de OS"] == "IMPRODUTIVA"])
    produtivas = len(df_grupo[df_grupo["Tipo de OS"] == "PRODUTIVA"])
    denominador = improdutivas + produtivas
    taxa = (improdutivas / denominador * 100.0) if denominador > 0 else 0.0
    return taxa, improdutivas, denominador


def _mascara_pme(df: pd.DataFrame) -> pd.Series:
    """Máscara dos registros marcados como PME/empresarial na coluna ``PME``."""
    if "PME" not in df.columns:
        return pd.Series(False, index=df.index)
    valores = df["PME"].fillna("").astype(str).str.strip().str.upper()
    return (valores != "") & (valores != "NAN") & valores.str.contains("PME|EMP", regex=True)


def calcular_metricas_completas(
    df_sub_raw: pd.DataFrame | None,
    montados: int,
    df_base_bruta: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Calcula produtividade, quebras, ND, GPON, migração, retorno WO e PME.

    ``df_sub_raw`` é o recorte já validado (base ou supervisor). ``df_base_bruta``
    é a base ANIEL completa da base: serve para contar Retorno WO por contrato
    único mesmo quando o supervisor não é o dono do retorno.
    """
    if not isinstance(df_sub_raw, pd.DataFrame) or df_sub_raw.empty:
        return _metricas_vazias()

    referencia_retorno = (
        df_base_bruta
        if (df_base_bruta is not None and not df_base_bruta.empty)
        else df_sub_raw
    )
    mascara_retorno = pd.Series(False, index=referencia_retorno.index)
    if "QUEBRAS" in referencia_retorno.columns:
        mascara_retorno = mascara_retorno | (
            referencia_retorno["QUEBRAS"].apply(limpar_texto) == CATEGORIA_RETORNO
        )
    if "Tipo de Serviço" in referencia_retorno.columns:
        mascara_retorno = mascara_retorno | (
            referencia_retorno["Tipo de Serviço"]
            .apply(limpar_texto)
            .str.contains("RETORNO", na=False)
        )
    retorno_wo = len(filtrar_por_contrato_unico(referencia_retorno[mascara_retorno]))

    if "Tipo de Serviço" in df_sub_raw.columns:
        df_sub = df_sub_raw[~eh_retorno_credenciada(df_sub_raw["Tipo de Serviço"])].copy()
    else:
        df_sub = df_sub_raw.copy()

    if "QUEBRAS" in df_sub.columns and "Tipo de Serviço" in df_sub.columns:
        df_sub["_quebra_padrao_"] = [
            padrao_quebra_categoria(quebra, tipo)
            for quebra, tipo in zip(df_sub["QUEBRAS"], df_sub["Tipo de Serviço"])
        ]
    else:
        df_sub["_quebra_padrao_"] = ""

    tem_tipo_os = "Tipo de OS" in df_sub.columns
    df_prod = df_sub[df_sub["Tipo de OS"] == "PRODUTIVA"] if tem_tipo_os else pd.DataFrame()
    df_improd = df_sub[df_sub["Tipo de OS"] == "IMPRODUTIVA"] if tem_tipo_os else pd.DataFrame()
    df_aberto = df_sub[df_sub["Tipo de OS"] == "EM ABERTO"] if tem_tipo_os else pd.DataFrame()
    df_canc = df_sub[df_sub["Tipo de OS"] == "CANCELADO"] if tem_tipo_os else pd.DataFrame()
    df_saiu = df_sub[df_sub["Tipo de OS"] == "SAIU DO TOA"] if tem_tipo_os else pd.DataFrame()

    produtivas = len(df_prod)
    improdutivas = len(df_improd)
    abertas = len(df_aberto)

    denominador_quebra = improdutivas + produtivas
    quebra = (improdutivas / denominador_quebra) if denominador_quebra > 0 else 0.0
    eficiencia = max(0.0, 1.0 - quebra)

    projecao_executada = produtivas + (abertas * eficiencia)
    projecao_dia = int(round(projecao_executada, 0))

    pontos_prod = df_prod["Pontos Prev."].sum() if "Pontos Prev." in df_prod.columns else 0.0
    pontos_improd = (
        df_improd["Pontos Prev."].sum() if "Pontos Prev." in df_improd.columns else 0.0
    )
    pontos_aberto = (
        df_aberto["Pontos Prev."].sum() if "Pontos Prev." in df_aberto.columns else 0.0
    )

    denominador_pontos = pontos_improd + pontos_prod
    eficiencia_pontos = (
        max(0.0, 1.0 - (pontos_improd / denominador_pontos))
        if denominador_pontos > 0
        else 0.0
    )
    pontos = int(round(pontos_prod + (pontos_aberto * eficiencia_pontos), 0))

    media_os = (projecao_dia / montados) if montados > 0 else 0.0

    df_ins = df_sub[df_sub["_quebra_padrao_"] == CATEGORIA_INSTALACAO]
    df_serv = df_sub[df_sub["_quebra_padrao_"] == CATEGORIA_SERVICOS]
    q_ins, raw_q_ins, raw_tot_ins = _taxa_quebra(df_ins)
    q_serv, raw_q_serv, raw_tot_serv = _taxa_quebra(df_serv)

    if "Tipo de Serviço" in df_sub.columns:
        tipos = df_sub["Tipo de Serviço"].apply(limpar_texto)
        mascara_nd = tipos.isin(SERVICOS_ND_ALVOS) | (
            tipos.str.contains("ADESAO", na=False)
            & (
                tipos.str.contains("ASSINATURA", na=False)
                | tipos.str.contains("STREAMING", na=False)
            )
        )
        df_nd = df_sub[mascara_nd]
    else:
        df_nd = pd.DataFrame()

    q_nd, nd_improd, den_nd = _taxa_quebra(df_nd)
    nd_prod = (
        len(df_nd[df_nd["Tipo de OS"] == "PRODUTIVA"])
        if not df_nd.empty and "Tipo de OS" in df_nd.columns
        else 0
    )
    nd_aberto = (
        len(df_nd[df_nd["Tipo de OS"] == "EM ABERTO"])
        if not df_nd.empty and "Tipo de OS" in df_nd.columns
        else 0
    )
    eficiencia_nd = max(0.0, 1.0 - (nd_improd / den_nd)) if den_nd > 0 else 0.0
    proj_nd = int(round(nd_prod + (nd_aberto * eficiencia_nd), 0))

    df_gpon = df_sub[df_sub["ATIVIDADES"] == "GPON"] if "ATIVIDADES" in df_sub.columns else pd.DataFrame()
    df_mig = (
        df_sub[df_sub["ATIVIDADES"] == "MIGRAÇÃO"]
        if "ATIVIDADES" in df_sub.columns
        else pd.DataFrame()
    )

    df_gpon_serv = (
        df_gpon[df_gpon["_quebra_padrao_"] == CATEGORIA_SERVICOS] if not df_gpon.empty else pd.DataFrame()
    )
    q_gpon, raw_q_gpon, raw_tot_gpon = _taxa_quebra(
        df_gpon_serv if not df_gpon_serv.empty else df_gpon
    )

    df_mig_ins = (
        df_mig[df_mig["_quebra_padrao_"] == CATEGORIA_INSTALACAO] if not df_mig.empty else pd.DataFrame()
    )
    q_mig, raw_q_mig, raw_tot_mig = _taxa_quebra(df_mig_ins if not df_mig_ins.empty else df_mig)

    df_pme_os = df_sub[_mascara_pme(df_sub)] if "PME" in df_sub.columns else pd.DataFrame()
    df_pme_wo = filtrar_por_contrato_unico(df_pme_os)
    df_pme_wo_ins = (
        df_pme_wo[df_pme_wo["_quebra_padrao_"] == CATEGORIA_INSTALACAO]
        if not df_pme_wo.empty
        else pd.DataFrame()
    )
    q_pme, raw_q_pme_wo, raw_tot_pme_wo = _taxa_quebra(
        df_pme_wo_ins if not df_pme_wo_ins.empty else df_pme_wo
    )
    canc_pme = (
        len(df_pme_wo[df_pme_wo["CANCELADAS"] == "CANCELADO"])
        if not df_pme_wo.empty and "CANCELADAS" in df_pme_wo.columns
        else 0
    )
    canc_mig = (
        len(df_mig[df_mig["CANCELADAS"] == "CANCELADO"])
        if not df_mig.empty and "CANCELADAS" in df_mig.columns
        else 0
    )

    return {
        "tot_os": len(df_sub),
        "os_aberta": abertas,
        "produtivo": produtivas,
        "quebra_geral": improdutivas,
        "pontos": pontos,
        "efic": round(eficiencia * 100, 1),
        "media_os": round(media_os, 2),
        "proj_dia": projecao_dia,
        "os_canc": len(df_canc),
        "saiu_toa": len(df_saiu),
        "q_ins": round(q_ins, 1),
        "q_serv": round(q_serv, 1),
        "tot_nd": proj_nd,
        "q_nd": round(q_nd, 1),
        "tot_gpon": len(df_gpon),
        "q_gpon": round(q_gpon, 1),
        "tot_mig": len(df_mig),
        "q_mig": round(q_mig, 1),
        "canc_mig": canc_mig,
        "retorno_wo": retorno_wo,
        "tot_pme": len(df_pme_wo),
        "q_pme": round(q_pme, 1),
        "canc_pme": canc_pme,
        "_raw_q_ins": raw_q_ins,
        "_raw_tot_ins": raw_tot_ins,
        "_raw_q_serv": raw_q_serv,
        "_raw_tot_serv": raw_tot_serv,
        "_raw_q_nd": nd_improd,
        "_raw_tot_nd": den_nd,
        "_raw_q_gpon": raw_q_gpon,
        "_raw_tot_gpon": raw_tot_gpon,
        "_raw_q_mig": raw_q_mig,
        "_raw_tot_mig": raw_tot_mig,
        "_raw_q_pme": raw_q_pme_wo,
        "_raw_tot_pme": raw_tot_pme_wo,
    }


# ====================================================
# 📅 BLOCO 4: CALENDÁRIO E PROJEÇÕES
# ====================================================
def calcular_calendario_automatico(
    data_ref: date | datetime | None = None,
) -> tuple[int, int, str]:
    """``(dias úteis do mês, dias úteis até a data, data formatada)``."""
    referencia = data_ref or datetime.now(FUSO_BR)
    if isinstance(referencia, datetime):
        ano, mes, dia = referencia.year, referencia.month, referencia.day
    else:
        ano, mes, dia = referencia.year, referencia.month, referencia.day

    total_dias = calendar.monthrange(ano, mes)[1]
    dias_uteis_mes = sum(
        1 for d in range(1, total_dias + 1) if datetime(ano, mes, d).weekday() != 6
    )
    dias_trabalhados = sum(
        1 for d in range(1, dia + 1) if datetime(ano, mes, d).weekday() != 6
    )
    return dias_uteis_mes, max(1, dias_trabalhados), referencia.strftime("%d/%m/%Y")


def _filtrar_historico(
    historico: pd.DataFrame | None,
    base: str,
    data_ref_str: str | None,
) -> pd.DataFrame:
    """Histórico de uma base, sem duplicidade de data e limitado ao mês de referência."""
    if not isinstance(historico, pd.DataFrame) or historico.empty:
        return pd.DataFrame()
    df_base = historico.copy()
    if "Base" in df_base.columns:
        df_base["_base_norm_"] = df_base["Base"].apply(normalizar_nome_base)
    else:
        df_base["_base_norm_"] = base
    df_base = df_base[df_base["_base_norm_"].astype(str).str.upper() == base.upper()].copy()
    if df_base.empty or "Data" not in df_base.columns:
        return df_base

    df_base = df_base.drop_duplicates(subset=["Data", "_base_norm_"], keep="last")
    if data_ref_str and len(str(data_ref_str)) >= 10:
        mes_ano = str(data_ref_str).strip()[3:]
        df_base = df_base[df_base["Data"].astype(str).str.strip().str.endswith(mes_ano)].copy()
    return df_base


def _inserir_dia(
    df_base: pd.DataFrame,
    base: str,
    data_ref_str: str,
    valor: int,
    coluna: str,
) -> pd.DataFrame:
    """Acrescenta/atualiza a linha do dia no histórico informado."""
    if df_base.empty:
        return pd.DataFrame([{"Data": str(data_ref_str), "Base": base, coluna: int(valor)}])
    filtro = df_base["Data"].astype(str).str.strip() == str(data_ref_str).strip()
    if not filtro.any():
        nova = pd.DataFrame([{"Data": str(data_ref_str), "Base": base, coluna: int(valor)}])
        return pd.concat([df_base, nova], ignore_index=True)
    df_base.loc[filtro, coluna] = int(valor)
    return df_base


def projetar_os(
    base: str,
    historico: pd.DataFrame | None,
    dias_uteis_mes: int = 25,
    os_hoje: int | None = None,
    data_ref_str: str | None = None,
) -> tuple[int, float, int]:
    """``(projeção mensal, média diária, dias considerados)`` de O.S. por base."""
    base_norm = normalizar_nome_base(base)
    df_base = _filtrar_historico(historico, base_norm, data_ref_str)

    if data_ref_str and os_hoje is not None and os_hoje >= 0:
        df_base = _inserir_dia(df_base, base_norm, str(data_ref_str), os_hoje, "OS_Executadas")

    if df_base.empty or "OS_Executadas" not in df_base.columns:
        return 0, 0.0, 1

    total = pd.to_numeric(df_base["OS_Executadas"], errors="coerce").sum()
    dias = max(1, df_base["Data"].nunique())
    media = total / dias
    return int(round(media * dias_uteis_mes, 0)), media, dias


def projetar_consultivo(
    base: str,
    historico: pd.DataFrame | None,
    dias_uteis_mes: int = 25,
    consultivo_hoje: int | None = None,
    data_ref_str: str | None = None,
    *,
    projecao_tv: int | None = None,
    dias_passados: int = 1,
) -> tuple[int, float, int]:
    """``(projeção mensal, média diária, dias considerados)`` do Consultivo.

    Quando o arquivo do consultivo já trouxe a projeção da regra da TV
    (``projecao_tv``), ela é a fonte — como nas telas 5 e 6. O histórico do
    Sheets é apenas fallback, ignorando valores claramente distorcidos (> 300).
    """
    base_norm = normalizar_nome_base(base)
    if projecao_tv is not None and projecao_tv >= 0:
        return (
            int(projecao_tv),
            projecao_tv / max(1, dias_uteis_mes),
            max(1, dias_passados),
        )

    df_base = _filtrar_historico(historico, base_norm, data_ref_str)
    if not df_base.empty:
        if "Qtd_Consultivo" not in df_base.columns:
            return 0, 0.0, 1
        df_base["Qtd_Consultivo"] = pd.to_numeric(
            df_base["Qtd_Consultivo"], errors="coerce"
        ).fillna(0)
        df_base = df_base[df_base["Qtd_Consultivo"] < 300]

    if data_ref_str and consultivo_hoje is not None and consultivo_hoje >= 0:
        df_base = _inserir_dia(
            df_base, base_norm, str(data_ref_str), consultivo_hoje, "Qtd_Consultivo"
        )

    if df_base.empty or "Qtd_Consultivo" not in df_base.columns:
        return 0, 0.0, 1

    total = pd.to_numeric(df_base["Qtd_Consultivo"], errors="coerce").sum()
    dias = max(1, df_base["Data"].nunique())
    media = total / dias
    return int(round(media * dias_uteis_mes, 0)), media, dias


def buscar_os_inicial(
    base: str,
    data_ref_str: str,
    historico: pd.DataFrame | None,
    fallback: dict[str, int] | None = None,
) -> int:
    """Rota Inicial da base na data (histórico do Sheets → fallback por base)."""
    base_norm = normalizar_nome_base(base).upper()
    fallback_base = fallback or ROTA_INICIAL_PADRAO

    if isinstance(historico, pd.DataFrame) and not historico.empty:
        colunas = {"Data", "Base", "OS_Inicial"}
        if colunas.issubset(historico.columns):
            df_hist = historico.copy()
            df_hist["_base_norm_"] = df_hist["Base"].apply(normalizar_nome_base).str.upper()
            filtro_data = df_hist["Data"].astype(str).str.strip() == str(data_ref_str).strip()
            match = df_hist[filtro_data & (df_hist["_base_norm_"] == base_norm)]
            if match.empty:
                palavra_chave = (
                    "ABC"
                    if "ABC" in base_norm
                    else ("GUARULHOS" if "GUA" in base_norm or "GRU" in base_norm else "LESTE")
                )
                match = df_hist[
                    filtro_data & df_hist["_base_norm_"].str.contains(palavra_chave, na=False)
                ]
            if not match.empty:
                valor = match.iloc[-1]["OS_Inicial"]
                if pd.notna(valor) and str(valor).strip() != "":
                    try:
                        return int(float(valor))
                    except (TypeError, ValueError):
                        pass

    return int(fallback_base.get(normalizar_nome_base(base), 0))


# ====================================================
# 🏷️ BLOCO 4B: CLASSIFICAÇÃO DA ANIEL (REGRAS DA OPERAÇÃO)
# ====================================================
def _texto_celula(valor: Any) -> str:
    """Texto de célula ANIEL: ``NaN``/``None``/``"nan"`` viram ``""``."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        return str(valor).strip()
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def classificar_aniel(
    df_aniel: pd.DataFrame,
    baixas: dict[str, str] | None = None,
    pontos: dict[str, float] | None = None,
    descricoes: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Aplica as regras do dia à ANIEL: tipo de O.S., quebra, atividade e pontos.

    Entradas:

    * ``baixas`` — ``ST3`` (código de baixa) → tipo de O.S. (aba ``Baixas``);
    * ``pontos`` — tipo de serviço → pontos previstos (aba ``Pontos``);
    * ``descricoes`` — tipo de serviço → descrição da quebra (aba ``Desc_OS``).

    A rotina é linha a linha de propósito: as regras dependem de correspondência
    parcial entre o código de baixa e o dicionário, o que não se expressa com
    segurança apenas com operações vetoriais.
    """
    baixas_norm = {limpar_texto(k): limpar_texto(v) for k, v in (baixas or {}).items()}
    pontos_norm = {limpar_texto(k): float(v) for k, v in (pontos or {}).items()}
    desc_norm = {limpar_texto(k): v for k, v in (descricoes or {}).items()}

    for coluna in ("ST1", "ST2", "ST3", "CANCELADAS", "PME", "QUEBRAS", "ATIVIDADES", "Cidade"):
        if coluna not in df_aniel.columns:
            df_aniel[coluna] = ""

    if "Tipo de OS" not in df_aniel.columns:
        df_aniel["Tipo de OS"] = ""
    if "Supervisor" not in df_aniel.columns:
        df_aniel["Supervisor"] = ""
    if "Pontos Prev." not in df_aniel.columns:
        df_aniel["Pontos Prev."] = 0.0
    else:
        df_aniel["Pontos Prev."] = pd.to_numeric(
            df_aniel["Pontos Prev."]
            .astype(str)
            .str.replace(" ", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False),
            errors="coerce",
        ).fillna(0.0)

    coluna_tipo_servico = next(
        (c for c in df_aniel.columns if "tipo de serv" in limpar_texto(c).lower()),
        "Tipo de Serviço",
    )
    if coluna_tipo_servico not in df_aniel.columns:
        df_aniel[coluna_tipo_servico] = ""
    coluna_obs = next(
        (
            c
            for c in df_aniel.columns
            if "observacao 1" in limpar_texto(c).lower() or "obs" in str(c).lower()
        ),
        "Observação 1",
    )
    if coluna_obs not in df_aniel.columns:
        df_aniel[coluna_obs] = ""

    # Colunas de texto que serão reescritas: o Excel pode tê-las lido como
    # float (coluna só de vazios) e o Pandas 3 recusa gravar string em float64.
    for coluna in (
        "Tipo de OS",
        "ST1",
        "ST2",
        "ST3",
        "CANCELADAS",
        "PME",
        "QUEBRAS",
        "ATIVIDADES",
        "Cidade",
        "Supervisor",
        coluna_tipo_servico,
        coluna_obs,
    ):
        df_aniel[coluna] = df_aniel[coluna].astype(object)

    for indice, linha in df_aniel.iterrows():
        tipo_os = limpar_texto(_texto_celula(linha.get("Tipo de OS", "")))
        st1 = _texto_celula(linha.get("ST1", ""))
        st2 = limpar_texto(_texto_celula(linha.get("ST2", ""))).lower()
        st3_norm = limpar_texto(_texto_celula(linha.get("ST3", "")).upper())

        encontrou_baixa = False
        if st3_norm:
            if st3_norm in baixas_norm:
                tipo_os = baixas_norm[st3_norm]
                encontrou_baixa = True
            else:
                for chave, valor in baixas_norm.items():
                    if chave and (st3_norm in chave or chave in st3_norm):
                        tipo_os = valor
                        encontrou_baixa = True
                        break
        if not encontrou_baixa and tipo_os in {"N/A", "#N/A", "", "SAIU DO TOA"}:
            tipo_os = "EM ABERTO"
        if tipo_os == "EM ABERTO" and not st1:
            tipo_os = "SAIU DO TOA"
        if (
            "liberado no sistema netsms" in st2 or "cancelado no sistema netsms" in st2
        ) and tipo_os == "EM ABERTO":
            tipo_os = "CANCELADO"
        if "executado no sistema netsms" in st2:
            tipo_os = "PRODUTIVA"

        df_aniel.at[indice, "Tipo de OS"] = tipo_os
        df_aniel.at[indice, "CANCELADAS"] = "CANCELADO" if "cancelado" in st2 else ""

        tipo_servico_norm = limpar_texto(_texto_celula(linha.get(coluna_tipo_servico, "")))
        obs = limpar_texto(_texto_celula(linha.get(coluna_obs, ""))).lower()

        quebra_bruta = ""
        if tipo_servico_norm in desc_norm:
            quebra_bruta = desc_norm[tipo_servico_norm]
        else:
            for chave, valor in desc_norm.items():
                if tipo_servico_norm and chave and (
                    tipo_servico_norm in chave or chave in tipo_servico_norm
                ):
                    quebra_bruta = valor
                    break
        df_aniel.at[indice, "QUEBRAS"] = padrao_quebra_categoria(quebra_bruta, tipo_servico_norm)

        atividade = ""
        tipo_servico_lower = tipo_servico_norm.lower()
        if "const" in tipo_servico_lower:
            atividade = "CONSTRUÇÃO"
        elif "pon " in obs or "fibra" in obs or "virtua pon" in obs or "gpon" in obs:
            atividade = "GPON"
            if (
                "instalacao de cabo gpon" in tipo_servico_lower
                or "mudanca de pacote" in tipo_servico_lower
            ):
                atividade = "MIGRAÇÃO"
        if not atividade:
            atividade = "HFC"
        if atividade == "HFC" and "instalacao de cabo gpon" in tipo_servico_lower:
            atividade = "MIGRAÇÃO"
        df_aniel.at[indice, "ATIVIDADES"] = atividade

        if float(df_aniel.at[indice, "Pontos Prev."]) == 0.0:
            ponto = None
            if tipo_servico_norm in pontos_norm:
                ponto = pontos_norm[tipo_servico_norm]
            else:
                for chave, valor in pontos_norm.items():
                    if tipo_servico_norm and chave and (
                        tipo_servico_norm in chave or chave in tipo_servico_norm
                    ):
                        ponto = valor
                        break
            if ponto is not None:
                df_aniel.at[indice, "Pontos Prev."] = float(ponto)

    df_aniel["Supervisor"] = df_aniel["Supervisor"].fillna("").astype(str).str.strip().str.upper()
    df_aniel["Tipo de Serviço"] = (
        df_aniel[coluna_tipo_servico].fillna("").astype(str).str.strip().str.upper()
    )
    return df_aniel


# ====================================================
# 📥 BLOCO 5: LEITURA DE ARQUIVOS E E-MAIL DE PARADOS
# ====================================================
def ler_planilha(arquivo: Any, prefer_sheet: str | None = None) -> pd.DataFrame:
    """Lê um upload (``.xlsx``/``.xlsm``/``.csv``) com fallbacks progressivos.

    Uploads reais do TOA chegam em CSV com separador/encoding variados; alguns
    arquivos do consultivo têm mais de uma aba (a de interesse contém
    ``CONSULTIVO`` no nome). Nada de retornar vazio para disfarçar erro: se
    nenhuma tentativa funcionar, levanta ``ValueError``.
    """
    nome = str(getattr(arquivo, "name", "") or "")
    conteudo = arquivo.getvalue() if hasattr(arquivo, "getvalue") else bytes(arquivo or b"")
    if not conteudo:
        raise ValueError("O arquivo enviado está vazio.")

    if prefer_sheet and nome.lower().endswith((".xlsx", ".xlsm")):
        try:
            abas = pd.ExcelFile(io.BytesIO(conteudo), engine="openpyxl")
            aba_alvo = next(
                (aba for aba in abas.sheet_names if prefer_sheet.upper() in aba.upper()),
                abas.sheet_names[0],
            )
            return pd.read_excel(io.BytesIO(conteudo), sheet_name=aba_alvo, engine="openpyxl")
        except Exception:  # noqa: BLE001 - segue para os fallbacks
            pass

    try:
        return ler_bytes(conteudo, nome)
    except Exception:  # noqa: BLE001 - formato inesperado, tenta leituras tolerantes
        pass

    tentativas: tuple[tuple[str, dict[str, Any]], ...] = (
        ("excel_openpyxl", {"engine": "openpyxl"}),
        ("excel_padrao", {}),
        ("csv_python", {"sep": None, "engine": "python", "encoding": "utf-8"}),
        ("csv_ponto_virgula", {"sep": ";", "encoding": "latin1", "on_bad_lines": "skip"}),
        ("csv_tab", {"sep": "\t", "encoding": "latin1"}),
    )
    ultimo_erro: Exception | None = None
    for tipo, opcoes in tentativas:
        try:
            if tipo.startswith("excel"):
                return pd.read_excel(io.BytesIO(conteudo), **opcoes)
            return pd.read_csv(io.BytesIO(conteudo), **opcoes)
        except Exception as exc:  # noqa: BLE001 - tenta o próximo leitor
            ultimo_erro = exc

    try:
        tabelas = pd.read_html(io.BytesIO(conteudo))
        if tabelas:
            return tabelas[0]
    except Exception as exc:  # noqa: BLE001 - última tentativa
        ultimo_erro = exc

    raise ValueError(f"Erro na leitura de '{nome or 'arquivo'}': {ultimo_erro}")


def _texto_do_msg(conteudo: bytes) -> tuple[str, str]:
    """Extrai assunto e texto do ``.msg`` (com fallback de decodificação bruta).

    ``extract-msg`` é dependência opcional: sem ela, a rotina ainda encontra os
    técnicos porque o e-mail é decodificado em latin1 e UTF-16LE e varrido por
    expressão regular.
    """
    texto = ""
    assunto = ""
    try:
        import extract_msg  # type: ignore[import-not-found]

        mensagem = extract_msg.Message(io.BytesIO(conteudo))
        assunto = str(mensagem.subject or "")
        corpo = str(mensagem.body or "")
        corpo_html = ""
        if getattr(mensagem, "htmlBody", None):
            html = mensagem.htmlBody
            corpo_html = html.decode("utf-8", errors="ignore") if isinstance(html, bytes) else str(html)
            corpo_html = re.sub(r"<[^>]+>", " \n ", corpo_html)
        texto = "\n".join(parte for parte in (assunto, corpo, corpo_html) if parte)
    except Exception:  # noqa: BLE001 - segue com a decodificação bruta
        pass

    if len(texto.strip()) < 50:
        texto += "\n" + conteudo.decode("latin1", errors="ignore")
        texto += "\n" + conteudo.decode("utf-16le", errors="ignore")
    return assunto, texto


def processar_arquivo_msg(conteudo: bytes) -> tuple[str | None, dict[str, int], list[str]]:
    """Lê o e-mail de parados e devolve ``(data, parados por supervisor, técnicos)``.

    Duas estratégias: primeiro a linha estruturada
    (``matrícula - nome | supervisor | motivo``); se o corpo do e-mail não seguir
    esse formato, conta uma ocorrência por supervisor citado na linha.
    """
    if not conteudo:
        return None, {chave: 0 for chave in ALIASES_SUPERVISORES}, []

    _, texto = _texto_do_msg(conteudo)
    texto_normalizado = sem_acento(texto.upper())

    match_data = re.search(r"\b(\d{2}/\d{2}/202\d)\b", texto_normalizado)
    data_extraida = match_data.group(1) if match_data else None

    parados = {chave: 0 for chave in ALIASES_SUPERVISORES}
    tecnicos: list[str] = []

    padrao_linha = re.compile(
        r"(\d{4,6}\s*-\s*[A-Z\s]{4,45}?)\s+"
        r"(MAICON[A-Z\s]*|NELSON[A-Z\s]*|EDSON[A-Z\s]*|ADRIANO[A-Z\s]*|DANIELE[A-Z\s]*|"
        r"FERNANDO[A-Z\s]*|PALOMA[A-Z\s]*|ALAN[A-Z\s]*|ELISANGELA[A-Z\s]*|"
        r"FRANCISC?O[A-Z\s]*|JOAO CARLOS[A-Z\s]*)\s+"
        r"(FALTA|FOLGA|ATESTADO|FERIAS|SUSPENSAO|TREINAMENTO|SINISTRO|OFICINA|MANUTENCAO)",
        re.IGNORECASE,
    )
    ocorrencias = padrao_linha.findall(texto_normalizado)
    if ocorrencias:
        for condutor, supervisor_encontrado, motivo in ocorrencias:
            condutor_limpo = re.sub(r"\s+", " ", condutor).strip()
            supervisor_limpo = re.sub(r"\s+", " ", supervisor_encontrado).strip()
            for chave, aliases in ALIASES_SUPERVISORES.items():
                if any(alias in supervisor_limpo for alias in aliases):
                    parados[chave] += 1
                    tecnicos.append(f"{condutor_limpo} ({chave}) - {motivo.strip()}")
                    break
    else:
        for linha in texto_normalizado.split("\n"):
            linha_limpa = re.sub(r"\s+", " ", linha).strip()
            if not linha_limpa or "SMTP:" in linha_limpa or "@" in linha_limpa:
                continue
            for chave, aliases in ALIASES_SUPERVISORES.items():
                aliases_compostos = [alias for alias in aliases if " " in alias]
                if any(alias in linha_limpa for alias in aliases_compostos):
                    parados[chave] += 1
                    encontrado = re.search(r"(\d{4,6}\s*-\s*[A-Z\s]{4,35})", linha_limpa)
                    tecnicos.append(
                        f"{encontrado.group(1).strip()} ({chave})"
                        if encontrado
                        else f"Técnico parado ({chave})"
                    )
                    break

    return data_extraida, parados, tecnicos


def rotulo_base(base: str) -> str:
    """Rótulo curto de uma base (``NET-ABCDM`` → ``ABCDM``)."""
    return ROTULOS_BASES.get(normalizar_nome_base(base), str(base))


def ordenar_datas(datas: Sequence[Any]) -> list[str]:
    """Datas ``dd/mm/aaaa`` da mais recente para a mais antiga (ignora inválidas)."""
    validas: list[tuple[datetime, str]] = []
    for valor in datas:
        texto = str(valor).strip()
        if not re.match(r"^\d{2}/\d{2}/\d{4}$", texto):
            continue
        try:
            validas.append((datetime.strptime(texto, "%d/%m/%Y"), texto))
        except ValueError:
            continue
    return [texto for _, texto in sorted(validas, reverse=True)]
