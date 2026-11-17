"""Assistente de criação da lista a partir da grade existente no Drive."""
from datetime import date

import pandas as pd
import streamlit as st

from services.absenteismo import TIPOS_AUSENCIA
from services.importacao_presenca import (
    MANTER_PENDENTE,
    converter_grade,
    ler_grade_legada,
    preparar_importacao,
)
from services.presenca_operacoes import assinatura


def render_importacao_presenca(registros, persistir, bloqueado=False):
    with st.expander("Criar Lista de Presença a partir da aba absenteismo"):
        st.markdown("**Aproveite o histórico existente, sem apagar a grade original.**")
        st.caption("ATIVO será convertido em Presente. Campos vazios continuam pendentes. A confirmação grava registros em controle_absenteismo; a aba absenteismo é apenas lida.")
        if bloqueado:
            st.warning("A origem atual está em grade. Não é seguro substituir essa aba por registros; revise a configuração antes de importar.")
            return
        referencia = st.date_input("Referência dos cabeçalhos sem ano", value=date.today().replace(day=1), key="importacao_referencia")
        st.caption("Confirme o mês e o ano da grade antes de converter cabeçalhos abreviados. Datas completas preservam o próprio ano.")
        if st.button("Ler grade histórica do Drive", key="importacao_ler"):
            try:
                with st.spinner("Lendo a aba absenteismo…"):
                    st.session_state["presenca_grade_legada"] = ler_grade_legada()
            except Exception as exc:
                st.error(f"Não foi possível ler a grade: {exc}")
        bruto = st.session_state.get("presenca_grade_legada")
        if not isinstance(bruto, pd.DataFrame):
            return
        try:
            _, inicial, _ = converter_grade(bruto, referencia)
            mapeamento = {}
            if not inicial.empty:
                codigos = inicial.loc[inicial["Motivo"].eq("Defina o tratamento"), "Valor"].unique()
                if len(codigos):
                    st.warning("Há situações que exigem decisão explícita. Não serão classificadas automaticamente como presença ou falta.")
                for codigo in codigos:
                    decisao = st.selectbox(
                        f"Tratamento de {codigo}", ["Selecione…", MANTER_PENDENTE, "Presente", *TIPOS_AUSENCIA],
                        key=f"importacao_codigo_{codigo}",
                    )
                    if decisao != "Selecione…":
                        mapeamento[codigo] = decisao
            convertidos, pendencias, pulados = converter_grade(bruto, referencia, mapeamento)
            col_total, col_presencas, col_revisar = st.columns(3)
            col_total.metric("Marcações para converter", len(convertidos))
            col_presencas.metric("Presenças explícitas", int(convertidos["Tipo"].eq("Presente").sum()))
            col_revisar.metric("Pendências de revisão", len(pendencias))
            if pulados:
                st.info(f"{pulados} célula(s) ficarão pendentes por decisão explícita; o valor original permanece na grade.")
            if not pendencias.empty:
                st.dataframe(pendencias, hide_index=True, width="stretch")
            st.dataframe(convertidos[["Login", "Técnico", "Tipo", "Data Início", "Motivo"]], hide_index=True, width="stretch", height=260)
            st.download_button("Baixar prévia da conversão em CSV", convertidos.drop(columns=["_inicio", "_fim"], errors="ignore").to_csv(index=False).encode("utf-8-sig"), "previa_importacao_presenca.csv", "text/csv", key="importacao_previa_download")
            with st.form("importacao_confirmar"):
                responsavel = st.text_input("Responsável pela importação")
                confirmar = st.checkbox("Conferi os códigos, a referência e a prévia. Autorizo criar os registros sem alterar a grade original.")
                salvar = st.form_submit_button("Criar lista a partir desta prévia", disabled=not pendencias.empty or convertidos.empty)
            if salvar:
                if not confirmar:
                    st.error("Confirme a conferência da prévia antes de criar a lista.")
                    return
                with st.spinner("Conferindo a origem e criando a lista…"):
                    remoto = ler_grade_legada()
                    if assinatura(remoto) != assinatura(bruto):
                        st.error("A grade foi alterada no Drive. Leia novamente e revise a nova prévia.")
                        return
                    atualizados, quantidade = preparar_importacao(registros, convertidos, responsavel)
                    if not quantidade:
                        st.info("Todas as marcações desta prévia já foram importadas. Nada foi duplicado.")
                    elif persistir(atualizados):
                        st.session_state["absenteismo_flash"] = [("sucesso", f"Lista criada com {quantidade} marcações do histórico. A grade original foi preservada.")]
                        st.rerun()
                    else:
                        st.error("Importação não confirmada. Confira o status de sincronização; não assuma que os registros foram salvos.")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Não foi possível preparar ou confirmar a lista: {exc}")
