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
F_EVO  = BASE / "EVOLUCAO_CENSO_2020_2024.parquet"

# ── Globals ────────────────────────────────────────────────────────────
_cursos:   pd.DataFrame | None = None
_ies:      pd.DataFrame | None = None
_evolucao: pd.DataFrame | None = None
_lock      = threading.Lock()
_ready     = threading.Event()

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
    global _cursos, _ies, _evolucao

    cur = pd.read_parquet(F_CUR)
    ies = pd.read_parquet(F_IES)
    evo = pd.read_parquet(F_EVO)

    # ── Normaliza tipos — cursos ───────────────────────────────────────
    cur["TP_MODALIDADE_ENSINO"] = cur["TP_MODALIDADE_ENSINO"].astype(str)
    cur["TP_REDE"]              = cur["TP_REDE"].astype(str)
    cur["CO_IES"]               = cur["CO_IES"].astype(str)
    ies["CO_IES"]               = ies["CO_IES"].astype(str)

    # ── Colunas numéricas — garante int ────────────────────────────────
    for col in ["QT_MAT", "QT_ING", "QT_CONC", "QT_VG_TOTAL",
                "QT_MAT_FEM", "QT_MAT_MASC"]:
        if col in cur.columns:
            cur[col] = pd.to_numeric(cur[col], errors="coerce").fillna(0).astype(int)

    # ── Join cursos ↔ IES ──────────────────────────────────────────────
    ies_join = ies[["CO_IES", "NO_IES", "SG_IES",
                    "TP_ORGANIZACAO_ACADEMICA", "NO_REGIAO_IES",
                    "NO_MUNICIPIO_IES", "SG_UF_IES"]].copy()
    cur = cur.merge(ies_join, on="CO_IES", how="left", suffixes=("", "_ies"))

    if "NO_MICRORREGIAO" not in cur.columns:
        cur["NO_MICRORREGIAO"] = cur.get("NO_MUNICIPIO", pd.Series(dtype=str))

    cur["TP_REDE_LABEL"] = cur["TP_REDE"].map(REDE_MAP).fillna("Outro")

    # ── Normaliza tipos — evolução ─────────────────────────────────────
    evo["NU_ANO_CENSO"]         = evo["NU_ANO_CENSO"].astype(str)
    evo["TP_MODALIDADE_ENSINO"] = evo["TP_MODALIDADE_ENSINO"].astype(str)
    evo["TP_REDE"]              = evo["TP_REDE"].astype(str)
    evo["CO_IES"]               = evo["CO_IES"].astype(str)

    for col in ["QT_MAT", "QT_ING", "QT_CONC", "QT_VG_TOTAL"]:
        evo[col] = pd.to_numeric(evo[col], errors="coerce").fillna(0).astype(int)

    evo["TP_REDE_LABEL"] = evo["TP_REDE"].map(REDE_MAP).fillna("Outro")

    with _lock:
        _cursos   = cur
        _ies      = ies
        _evolucao = evo


def start_loader():
    """Chama _load() em background para não bloquear o boot do Flask."""
    def _run():
        _load()
        _ready.set()
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _wait(timeout: int = 60):
    """Bloqueia até os dados estarem prontos (máx. timeout segundos)."""
    if not _ready.wait(timeout):
        raise RuntimeError("Timeout ao aguardar carregamento dos dados.")


# ── Accessors ──────────────────────────────────────────────────────────
def get_cursos() -> pd.DataFrame:
    _wait()
    with _lock:
        return _cursos


def get_ies() -> pd.DataFrame:
    _wait()
    with _lock:
        return _ies


def get_evolucao() -> pd.DataFrame:
    _wait()
    with _lock:
        return _evolucao


# ── Filtro genérico ────────────────────────────────────────────────────
def aplicar_filtros(df: pd.DataFrame, params: dict, prefixo: str = "") -> pd.DataFrame:
    if df is None or df.empty:
        return df

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
        "co_ies":        "CO_IES",
        "no_ies":        "NO_IES",
        "sg_ies":        "SG_IES",
        "tipo_ies":      "TP_ORGANIZACAO_ACADEMICA",
        "no_curso":      "NO_CURSO",
    }

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