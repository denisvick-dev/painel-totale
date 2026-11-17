"""Metas mensais de produção de O.S. usadas em Metas Operacionais."""

METAS_OS_POR_BASE = {
    "NET-ABCDM": 10_000,
    "NET-GUARULHOS": 10_700,
    "NET-LESTE": 10_300,
}

# Limiares de mínimo e alta performance preservados; altera-se a meta mensal.
METAS_PRODUCAO_OS_BASE = {"minima": 10_000, "meta_base": 11_000, "alta_perf": 12_000}
METAS_PRODUCAO_OS_GERAL = {
    "minima": 30_000,
    "meta_base": sum(METAS_OS_POR_BASE.values()),
    "alta_perf": 36_000,
}


def metas_os_da_base(base: str) -> dict[str, int]:
    """Resolve a meta por base; outros projetos mantêm os valores anteriores."""
    nome = str(base).strip().upper()
    if nome in {"ABCDM", "GUARULHOS", "LESTE"}:
        nome = f"NET-{nome}"
    return {
        **METAS_PRODUCAO_OS_BASE,
        "meta_base": METAS_OS_POR_BASE.get(nome, METAS_PRODUCAO_OS_BASE["meta_base"]),
    }
