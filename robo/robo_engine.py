import time
from pathlib import Path

import pandas as pd


class TotaleRoboEngine:
    """Motor de IO de alta performance para detecção e leitura de arquivos."""

    PADROES = ("Atividades-*.csv", "Atividades-*.xlsx", "Atividades-*.xls")

    @staticmethod
    def buscar_mais_recente(pasta: str) -> Path | None:
        p = Path(pasta)
        if not p.exists() or not p.is_dir():
            return None

        candidatos = []
        for padrao in TotaleRoboEngine.PADROES:
            candidatos.extend(p.glob(padrao))

        # Filtra arquivos temporários (Excel aberto ou Downloads incompletos)
        validos = [
            c
            for c in candidatos
            if not c.name.startswith("~$")
            and c.suffix.lower() not in (".tmp", ".crdownload")
        ]

        if not validos:
            return None

        return max(validos, key=lambda x: x.stat().st_mtime)

    @staticmethod
    def verificar_estabilidade(caminho: Path, ciclos: int = 2) -> bool:
        """Garante que o arquivo não está sendo gravado/baixado no momento."""
        try:
            for _ in range(ciclos):
                size1 = caminho.stat().st_size
                time.sleep(0.8)
                if size1 != caminho.stat().st_size:
                    return False
            return size1 > 0
        except Exception:
            return False

    @staticmethod
    def ler_dados(caminho: Path) -> pd.DataFrame | None:
        """Leitura polimórfica com fallback de encoding."""
        ext = caminho.suffix.lower()
        try:
            if ext in (".xlsx", ".xls"):
                return pd.read_excel(caminho, dtype=str)

            # Estratégia de decodificação para CSV
            for enc in ["utf-8-sig", "latin1", "cp1252", "iso-8859-1"]:
                try:
                    df = pd.read_csv(
                        caminho, sep=None, engine="python", encoding=enc, dtype=str
                    )
                    if df.shape[1] > 2:  # Validação mínima de colunas
                        return df
                except:
                    continue
        except Exception as e:
            print(f"Erro crítico na leitura do arquivo {caminho.name}: {e}")
        return None
