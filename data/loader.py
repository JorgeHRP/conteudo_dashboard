"""
data/loader.py — Conteúdo Insights
Carrega os parquets em memória uma única vez e expõe helpers de filtro.
"""
import threading
import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
BASE   = Path(__file__).parent.parent / "parquet"
F_CUR  = BASE / "MICRODADOS_CADASTRO_CURSOS_2024.parquet"
F_IES  = BASE / "MICRODADOS_ED_SUP_IES_2024.parquet"

# ── Globals ────────────────────────────────────────────────────────────
_cursos: pd.DataFrame | None = None
_ies:    pd.DataFrame | None = None
_lock   = threading.Lock()

# ── Mapa de modalidade ──────────────────────────────────────────────────
MODALIDADE_MAP = {"1": "Presencial", "2": "EAD", "3": "Semi-presencial"}

# ── Mapa de tipo de rede ────────────────────────────────────────────────
REDE_MAP = {
    "1": "Federal",
    "2": "Estadual",
    "3": "Municipal",
    "4": "Privada",
}

# ── Loader interno ─────────────────────────────────────────────────────
def _load():
    global _cursos, _ies

    cur = pd.read_parquet(F_CUR)
    ies = pd.read_parquet(F_IES)

    # ── Normaliza tipos ────────────────────────────────────────────────
    cur["TP_MODALIDADE_ENSINO"] = cur["TP_MODALIDADE_ENSINO"].astype(str)
    cur["TP_REDE"]              = cur["TP_REDE"].astype(str)
    cur["CO_IES"]               = cur["CO_IES"].astype(str)
    ies["CO_IES"]               = ies["CO_IES"].astype(str)

    # ── Colunas numéricas — garante int ────────────────────────────────
    for col in ["QT_MAT", "QT_ING", "QT_CONC", "QT_VG_TOTAL",
                "QT_MAT_FEM", "QT_MAT_MASC"]:
        if col in cur.columns:
            cur[col] = pd.to_numeric(cur[col], errors="coerce").fillna(0).astype(int)

    # ── Join cursos ↔ IES para ter NO_IES, SG_IES, TP_ORGANIZACAO no df de cursos
    ies_join = ies[["CO_IES", "NO_IES", "SG_IES",
                    "TP_ORGANIZACAO_ACADEMICA", "NO_REGIAO_IES",
                    "NO_MUNICIPIO_IES", "SG_UF_IES"]].copy()

    cur = cur.merge(ies_join, on="CO_IES", how="left", suffixes=("", "_ies"))

    # ── Microrregião: se não existir na coluna, deriva do município ────
    if "NO_MICRORREGIAO" not in cur.columns:
        cur["NO_MICRORREGIAO"] = cur.get("NO_MUNICIPIO", pd.Series(dtype=str))

    # ── Label legível de rede ──────────────────────────────────────────
    cur["TP_REDE_LABEL"] = cur["TP_REDE"].map(REDE_MAP).fillna("Outro")

    with _lock:
        _cursos = cur
        _ies    = ies


def start_loader():
    """Chama _load() em background para não bloquear o boot do Flask."""
    t = threading.Thread(target=_load, daemon=True)
    t.start()


# ── Accessors ──────────────────────────────────────────────────────────
def get_cursos() -> pd.DataFrame:
    with _lock:
        if _cursos is None:
            raise RuntimeError("Dados ainda não carregados. Aguarde.")
        return _cursos


def get_ies() -> pd.DataFrame:
    with _lock:
        if _ies is None:
            raise RuntimeError("Dados ainda não carregados. Aguarde.")
        return _ies


# ── Filtro genérico ────────────────────────────────────────────────────
def aplicar_filtros(df: pd.DataFrame, params: dict, prefixo: str = "") -> pd.DataFrame:
    """
    Aplica os filtros do params ao DataFrame.
    Suporta prefixo para evitar colisão quando chamado sobre o df de IES.
    """
    if df is None or df.empty:
        return df

    # Mapeamento chave_param → coluna_dataframe
    mapa = {
        "regiao":        "NO_REGIAO",
        "uf":            "SG_UF",
        "modalidade":    "TP_MODALIDADE_ENSINO",
        "area":          "NO_CINE_AREA_GERAL",
        "rede":          "TP_REDE",
        "grau":          "TP_GRAU_ACADEMICO",
        "org_academica": "TP_ORGANIZACAO_ACADEMICA",
        "microrregiao":  "NO_MICRORREGIAO",
        "municipio":     "NO_MUNICIPIO",
        # filtros IES
        "co_ies":        "CO_IES",
        "no_ies":        "NO_IES",
        "sg_ies":        "SG_IES",
        "tipo_ies":      "TP_ORGANIZACAO_ACADEMICA",
    }

    # Se chamado com prefixo="ies", usa colunas do df de IES
    if prefixo == "ies":
        mapa = {
            "uf":            "SG_UF_IES",
            "regiao":        "NO_REGIAO_IES",
            "org_academica": "TP_ORGANIZACAO_ACADEMICA",
            "co_ies":        "CO_IES",
            "no_ies":        "NO_IES",
            "sg_ies":        "SG_IES",
            "tipo_ies":      "TP_ORGANIZACAO_ACADEMICA",
        }

    for chave, coluna in mapa.items():
        valor = params.get(chave)
        if not valor or coluna not in df.columns:
            continue
        df = df[df[coluna].astype(str) == str(valor)]

    return df


# ── Helper: valores únicos para popular filtros ────────────────────────
def uniq(df: pd.DataFrame, col: str) -> list:
    if col not in df.columns:
        return []
    return sorted(df[col].dropna().unique().tolist())