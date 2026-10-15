"""Contratos do motor de datas movido de pages/ para services/."""

from datetime import date

import pandas as pd

from services.datas import (
    converter_serie_datas,
    converter_serie_datas_mdy,
    garantir_datetime,
    limites_datas_disponiveis,
    mascara_periodo,
    normalizar_janela_datas,
    validar_estado_janela,
)


def test_parser_preserva_iso_br_fuso_e_indice() -> None:
    serie = pd.Series(
        ["2026-10-02", "02/10/2026", "2026-10-02T12:00:00Z", "inválida", 123],
        index=[10, 20, 30, 40, 50],
        name="DATA",
    )
    resultado = converter_serie_datas(serie)

    assert resultado.index.equals(serie.index)
    assert resultado.name == "DATA"
    assert resultado.loc[10] == resultado.loc[20] == pd.Timestamp("2026-10-02")
    assert resultado.loc[30] == pd.Timestamp("2026-10-02 09:00:00")
    assert resultado.loc[[40, 50]].isna().all()
    assert resultado.dt.tz is None


def test_parser_mdy_explicito_nao_inverte_iso() -> None:
    resultado = converter_serie_datas_mdy(pd.Series(["10/02/2026", "2026-10-02"]))
    assert resultado.eq(pd.Timestamp("2026-10-02")).all()


def test_normalizacao_nao_modifica_dataframe_original() -> None:
    original = pd.DataFrame({"DATA": ["02/10/2026"]})
    resultado = garantir_datetime(original)
    assert original.loc[0, "DATA"] == "02/10/2026"
    assert resultado.loc[0, "DATA"] == pd.Timestamp("2026-10-02")


def test_limites_preservam_fonte_valida_quando_outra_esta_vazia() -> None:
    fontes = [pd.DataFrame(), pd.DataFrame({"DATA": ["30/09/2026", "02/10/2026"]})]
    assert limites_datas_disponiveis(fontes, date(2026, 10, 15)) == (
        date(2026, 9, 30),
        date(2026, 10, 2),
        date(2026, 10, 1),
    )


def test_janela_incompleta_nao_vira_recorte_de_um_dia() -> None:
    dia = date(2026, 10, 2)
    assert normalizar_janela_datas((dia,)) is None
    assert validar_estado_janela((dia,), date(2026, 10, 1), date(2026, 10, 15))
    assert not validar_estado_janela((pd.NaT,), date(2026, 10, 1), date(2026, 10, 15))


def test_filtro_inclui_horario_do_ultimo_dia() -> None:
    serie = pd.Series(["01/10/2026 23:59:59", "02/10/2026 23:59:59", "03/10/2026"])
    assert mascara_periodo(serie, date(2026, 10, 1), date(2026, 10, 2)).tolist() == [
        True,
        True,
        False,
    ]
