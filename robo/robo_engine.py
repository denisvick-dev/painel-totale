"""
Motor de IO para arquivos TOTALE (CSV/Excel).

Não importa Streamlit. O ciclo de 5s do app deve usar `assinatura()`;
`verificar_estabilidade()` dorme de propósito e serve para script ou teste.

Por padrão `buscar_mais_recente()` continua devolvendo um arquivo.
`arquivos_por_base()` devolve o mais novo de cada marcador, que é o certo
quando o TOTALE reexporta o snapshot do mês.
"""

from __future__ import annotations

import fnmatch
import logging
import math
import os
import tempfile
import time
import zipfile
from collections.abc import Callable, Iterable, Sequence
from io import BytesIO
from pathlib import Path
from typing import Literal, cast

import pandas as pd

try:
    from pandas.errors import OptionError as PandasOptionError
except ImportError:  # pandas < 1.0
    PandasOptionError = KeyError  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)

EngineExcel = Literal["openpyxl", "calamine", "xlrd"]
_EXTENSOES_TEMP = (".tmp", ".crdownload", ".partial", ".download", ".part")
_AUSENTES = frozenset({"", "nan", "none", "na", "n/a", "<na>", "nat", "null", "-"})
_TAMANHO_MINIMO_XLSX = 2_000
_TAMANHO_MAXIMO = 80 * 1024 * 1024


class _BytesNomeados(BytesIO):
    """O pandas usa .name para escolher o engine. Sem isso, .xlsx vira zip."""

    def __init__(self, raw: bytes, nome: str) -> None:
        super().__init__(raw)
        self.name = nome


class TotaleRoboEngine:
    """Detecção e leitura de exportações TOTALE."""

    PADROES = ("Atividades-*.csv", "Atividades-*.xlsx", "Atividades-*.xls")
    MAPA_BASES = {
        "ABCDM": "NET-ABCDM",
        "SPO": "NET-LESTE",
        "GRS": "NET-GUARULHOS",
    }

    _ultimo_erro: str | None = None
    _ultimo_motor: str | None = None

    @classmethod
    def ultimo_erro(cls) -> str | None:
        return cls._ultimo_erro

    @classmethod
    def ultimo_motor(cls) -> str | None:
        return cls._ultimo_motor

    @classmethod
    def _registrar(cls, erro: str | None, motor: str | None = None) -> None:
        cls._ultimo_erro = erro
        cls._ultimo_motor = motor
        if erro:
            logger.debug("%s", erro)

    @staticmethod
    def detectar_base(caminho: str | Path | None) -> str | None:
        if not caminho:
            return None
        nome = Path(caminho).name.upper()
        for marcador in sorted(TotaleRoboEngine.MAPA_BASES, key=len, reverse=True):
            if marcador in nome:
                return TotaleRoboEngine.MAPA_BASES[marcador]
        return None

    @staticmethod
    def listar_validos(pasta: str | Path, *, recursivo: bool = False) -> list[Path]:
        raiz = Path(pasta)
        if not raiz.is_dir():
            return []
        try:
            arquivos = [
                p
                for p in (raiz.rglob("*") if recursivo else raiz.iterdir())
                if p.is_file()
            ]
        except OSError as e:
            TotaleRoboEngine._registrar(f"Não foi possível listar {raiz}: {e}")
            return []

        validos = [
            arq
            for arq in arquivos
            if TotaleRoboEngine._aceita(arq) and TotaleRoboEngine._mtime(arq) >= 0
        ]
        validos.sort(key=TotaleRoboEngine._mtime, reverse=True)
        return validos

    @staticmethod
    def buscar_mais_recente(pasta: str | Path) -> Path | None:
        validos = TotaleRoboEngine.listar_validos(pasta)
        return validos[0] if validos else None

    @staticmethod
    def arquivos_por_base(pasta: str | Path) -> dict[str, Path]:
        """O mais novo de cada base. Arquivo sem SPO/GRS/ABCDM não entra."""
        por_base: dict[str, Path] = {}
        for caminho in TotaleRoboEngine.listar_validos(pasta):
            base = TotaleRoboEngine.detectar_base(caminho)
            if base and base not in por_base:
                por_base[base] = caminho
        return por_base

    @staticmethod
    def assinatura(caminho: str | Path) -> tuple[int, int] | None:
        """Tamanho e mtime. Compare no próximo ciclo, sem dormir a thread."""
        try:
            stat = Path(caminho).stat()
        except OSError:
            return None
        return int(stat.st_size), int(stat.st_mtime_ns)

    @staticmethod
    def verificar_estabilidade(
        caminho: str | Path,
        ciclos: int = 2,
        intervalo: float = 0.8,
    ) -> bool:
        """Bloqueia a thread. No Streamlit, prefira `assinatura()`."""
        arquivo = Path(caminho)
        if not arquivo.is_file():
            return False
        try:
            anterior = arquivo.stat()
        except OSError:
            return False
        if anterior.st_size <= 0:
            return False
        for _ in range(max(ciclos, 1)):
            time.sleep(intervalo)
            try:
                atual = arquivo.stat()
            except OSError:
                return False
            if (
                atual.st_size != anterior.st_size
                or atual.st_mtime_ns != anterior.st_mtime_ns
            ):
                return False
            anterior = atual
        return anterior.st_size > 0

    @staticmethod
    def ler_dados(
        caminho: str | Path,
        *,
        aplicar_base: bool = False,
        sheet_name: str | int = 0,
    ) -> pd.DataFrame | None:
        arquivo = Path(caminho)
        if not arquivo.is_file():
            TotaleRoboEngine._registrar(f"Arquivo não encontrado: {arquivo.name}")
            return None

        ext = arquivo.suffix.lower()
        try:
            raw = _ler_bytes_estavel(arquivo)
        except _ArquivoInstavel as e:
            TotaleRoboEngine._registrar(str(e))
            return None
        except OSError as e:
            TotaleRoboEngine._registrar(
                f"{arquivo.name} está bloqueado ou inacessível: {e}"
            )
            return None

        try:
            if ext in (".xlsx", ".xls"):
                df, motor = _ler_excel(raw, arquivo.name, ext, sheet_name)
            elif ext == ".csv":
                lido = _ler_csv(raw, arquivo.name)
                if lido is None:
                    TotaleRoboEngine._registrar(
                        f"{arquivo.name}: falha ao decodificar CSV"
                    )
                    return None
                df, motor = lido
            else:
                TotaleRoboEngine._registrar(
                    f"{arquivo.name}: extensão {ext or '—'} não suportada"
                )
                return None
        except Exception as e:
            TotaleRoboEngine._registrar(f"{arquivo.name}: {type(e).__name__} — {e}")
            logger.debug("Falha ao ler %s", arquivo.name, exc_info=True)
            return None

        if df.empty:
            TotaleRoboEngine._registrar(
                f"{arquivo.name}: arquivo lido, porém sem linhas"
            )
            return None

        if aplicar_base:
            base = TotaleRoboEngine.detectar_base(arquivo)
            if base:
                df = _aplicar_base(df, base)
        TotaleRoboEngine._registrar(None, motor)
        return df

    @staticmethod
    def _aceita(caminho: Path) -> bool:
        nome = caminho.name
        baixo = nome.lower()
        if baixo.startswith("~$") or baixo.startswith("."):
            return False
        if baixo.endswith(_EXTENSOES_TEMP):
            return False
        if any(
            fnmatch.fnmatch(baixo, padrao.lower())
            for padrao in TotaleRoboEngine.PADROES
        ):
            return True
        return "atividades" in baixo and caminho.suffix.lower() in {
            ".csv",
            ".xlsx",
            ".xls",
        }

    @staticmethod
    def _mtime(caminho: Path) -> float:
        try:
            return caminho.stat().st_mtime
        except OSError:
            return -1.0


class _ArquivoInstavel(Exception):
    """O arquivo mudou enquanto era lido. O próximo ciclo tenta de novo."""


def _ler_bytes_estavel(caminho: Path) -> bytes:
    tamanho = caminho.stat().st_size
    if tamanho > _TAMANHO_MAXIMO:
        raise ValueError(
            f"{caminho.name} tem {tamanho} bytes, acima do limite de {_TAMANHO_MAXIMO}."
        )
    if tamanho <= 0:
        raise ValueError(f"{caminho.name} está vazio.")
    with caminho.open("rb") as fh:
        raw = fh.read()
    if len(raw) != tamanho or caminho.stat().st_size != tamanho:
        raise _ArquivoInstavel(
            f"{caminho.name} mudou durante a leitura. Aguardando o arquivo fechar."
        )
    return raw


def _validar_xlsx(raw: bytes, nome: str) -> None:
    if len(raw) < _TAMANHO_MINIMO_XLSX:
        raise ValueError(f"{nome} tem {len(raw)} bytes — download incompleto.")
    bio = BytesIO(raw)
    if not zipfile.is_zipfile(bio):
        raise ValueError(f"{nome} não é um .xlsx válido.")
    bio.seek(0)
    with zipfile.ZipFile(bio) as zf:
        ruim = zf.testzip()
    if ruim is not None:
        raise ValueError(f"{nome} está corrompido no membro interno: {ruim}")


def _texto_celula(valor: object) -> str:
    if valor is None or valor is pd.NA:
        return ""
    if isinstance(valor, bool):
        return "True" if valor else "False"
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        if math.isnan(valor):
            return ""
        if valor.is_integer():
            return str(int(valor))
        return str(valor).strip()
    texto = valor.strip() if isinstance(valor, str) else str(valor).strip()
    if texto.lower() in _AUSENTES:
        return ""
    corpo = texto[:-2] if texto.endswith(".0") else ""
    if corpo and corpo.replace("-", "", 1).isdigit():
        return corpo
    return texto


def _nomes_colunas(nomes: Iterable[object]) -> list[str]:
    vistos: dict[str, int] = {}
    saida: list[str] = []
    for i, bruto in enumerate(nomes):
        nome = (
            ""
            if bruto is None
            else str(bruto).replace("\ufeff", "").replace("\xa0", " ").strip()
        )
        if not nome or nome.lower().startswith("unnamed"):
            nome = f"col_{i}"
        if nome in vistos:
            vistos[nome] += 1
            nome = f"{nome}.{vistos[nome]}"
        else:
            vistos[nome] = 0
        saida.append(nome)
    return saida


def _cabecalho_fraco(colunas: Sequence[object]) -> bool:
    nomes = [str(c).strip() for c in colunas]
    if not nomes:
        return True
    ruins = sum(
        1
        for n in nomes
        if not n or n.lower().startswith("unnamed") or n.lower().startswith("col_")
    )
    return ruins / len(nomes) >= 0.5


def _padronizar(df: pd.DataFrame) -> pd.DataFrame:
    saida = df.copy()
    saida.columns = pd.Index(_nomes_colunas(list(saida.columns)))
    for col in saida.columns:
        texto = saida[col].map(_texto_celula)
        saida[col] = texto.mask(texto.eq(""))
    return saida.dropna(how="all")


def _como_frame(bruto: pd.DataFrame | dict[str, pd.DataFrame]) -> pd.DataFrame:
    if isinstance(bruto, dict):
        if not bruto:
            return pd.DataFrame()
        return next(iter(bruto.values()))
    return bruto


def _ler_excel_nativo(raw: bytes, sheet_name: str | int, header: int) -> pd.DataFrame:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(raw), read_only=True, data_only=True)
    try:
        ws = None
        if isinstance(sheet_name, int) and 0 <= sheet_name < len(wb.worksheets):
            ws = wb.worksheets[sheet_name]
        elif isinstance(sheet_name, str) and sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        if ws is None:
            ws = wb.active
        if ws is None and wb.worksheets:
            ws = wb.worksheets[0]
        if ws is None:
            return pd.DataFrame()

        linhas = list(ws.iter_rows(values_only=True))
        if header >= len(linhas) or linhas[header] is None:
            return pd.DataFrame()
        colunas = _nomes_colunas(linhas[header])
        data: list[list[object]] = []
        for row in linhas[header + 1 :]:
            valores: list[object] = [celula for celula in row]
            if len(valores) < len(colunas):
                valores.extend([None] * (len(colunas) - len(valores)))
            elif len(valores) > len(colunas):
                valores = valores[: len(colunas)]
            data.append(valores)
        return pd.DataFrame(data, columns=pd.Index(colunas))
    finally:
        wb.close()


def _ler_excel(
    raw: bytes,
    nome: str,
    ext: str,
    sheet_name: str | int,
) -> tuple[pd.DataFrame, str]:
    if ext == ".xlsx":
        _validar_xlsx(raw, nome)

    erros: list[str] = []
    reserva: tuple[pd.DataFrame, str] | None = None

    def tentar(
        rotulo: str,
        fn: Callable[[], pd.DataFrame | dict[str, pd.DataFrame]],
    ) -> pd.DataFrame | None:
        try:
            df = _como_frame(fn())
        except PandasOptionError as e:
            erros.append(f"{rotulo}: OptionError {e}")
            return None
        except ImportError as e:
            erros.append(f"{rotulo}: engine ausente ({e})")
            return None
        except Exception as e:
            erros.append(f"{rotulo}: {type(e).__name__}: {e}")
            return None
        if df.empty:
            erros.append(f"{rotulo}: planilha vazia")
            return None
        return df

    def via_temp(engine: str, sufixo: str, header: int) -> pd.DataFrame:
        fd, tmp = tempfile.mkstemp(suffix=sufixo)
        os.close(fd)
        try:
            with open(tmp, "wb") as out:
                out.write(raw)
            return _como_frame(
                pd.read_excel(
                    tmp,
                    sheet_name=sheet_name,
                    header=header,
                    dtype=str,
                    engine=cast(EngineExcel, engine),
                )
            )
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def via_buffer(engine: str, nome_buffer: str, header: int) -> pd.DataFrame:
        return _como_frame(
            pd.read_excel(
                _BytesNomeados(raw, nome_buffer),
                sheet_name=sheet_name,
                header=header,
                dtype=str,
                engine=cast(EngineExcel, engine),
            )
        )

    for header in (0, 1):
        if ext == ".xls":
            tentativas = [
                (
                    f"calamine header={header}",
                    lambda h=header: via_temp("calamine", ".xls", h),
                ),
                (f"xlrd header={header}", lambda h=header: via_temp("xlrd", ".xls", h)),
            ]
        else:
            tentativas = [
                (
                    f"openpyxl/temp header={header}",
                    lambda h=header: via_temp("openpyxl", ".xlsx", h),
                ),
                (
                    f"openpyxl/BytesIO header={header}",
                    lambda h=header: via_buffer("openpyxl", "arquivo.xlsx", h),
                ),
                (
                    f"calamine header={header}",
                    lambda h=header: via_buffer("calamine", "arquivo.xlsx", h),
                ),
                (
                    f"openpyxl nativo header={header}",
                    lambda h=header: _ler_excel_nativo(raw, sheet_name, h),
                ),
            ]
        for rotulo, fn in tentativas:
            df = tentar(rotulo, fn)
            if df is None:
                continue
            if not _cabecalho_fraco(list(df.columns)):
                return _padronizar(df), rotulo
            if reserva is None:
                reserva = (df, rotulo)

    if reserva is not None:
        df, rotulo = reserva
        return _padronizar(df), rotulo

    dica = ""
    joined = " | ".join(erros)
    if "engine ausente" in joined.lower():
        dica = (
            " → pip install openpyxl"
            if ext != ".xls"
            else " → pip install python-calamine"
        )
    raise RuntimeError(
        f"{joined}{dica}" if erros else f"Falha desconhecida ao ler {nome}."
    )


def _ler_csv(raw: bytes, nome: str) -> tuple[pd.DataFrame, str] | None:
    ultimo: Exception | None = None
    for enc in ("utf-8-sig", "cp1252", "latin1", "iso-8859-1", "utf-8"):
        for sep in (";", ","):
            try:
                df = pd.read_csv(
                    BytesIO(raw),
                    sep=sep,
                    encoding=enc,
                    dtype=str,
                    low_memory=False,
                    on_bad_lines="skip",
                )
            except Exception as e:
                ultimo = e
                continue
            if df.shape[1] <= 1:
                continue
            return _padronizar(df), f"csv {enc} sep={sep!r}"
    if ultimo is not None:
        logger.debug("CSV %s esgotou encodings: %s", nome, ultimo)
    return None


def _aplicar_base(df: pd.DataFrame, base: str) -> pd.DataFrame:
    saida = df.copy()
    variantes = [
        col for col in saida.columns if str(col).casefold() == "base" and col != "BASE"
    ]
    if variantes and "BASE" not in saida.columns:
        saida = saida.rename(columns={variantes[0]: "BASE"})
        variantes = variantes[1:]
    for col in variantes:
        if "BASE" not in saida.columns:
            break
        texto = saida["BASE"].map(_texto_celula)
        vazios = texto.eq("")
        saida.loc[vazios, "BASE"] = saida.loc[vazios, col].map(_texto_celula)
        saida = saida.drop(columns=[col])
    if "BASE" not in saida.columns:
        saida["BASE"] = base
        return saida
    texto = saida["BASE"].map(_texto_celula)
    saida.loc[texto.eq(""), "BASE"] = base
    return saida
