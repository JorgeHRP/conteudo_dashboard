import threading
import time
import logging
from pathlib import Path
import pandas as pd
import config

log = logging.getLogger(__name__)

_cache: dict = {}
_lock  = threading.Lock()
_ready = threading.Event()


def _load():
    log.info("Carregando dados...")
    start   = time.time()
    parquet = Path(config.PARQUET_DIR).resolve()

    log.info(f"Procurando parquets em: {parquet}")

    if not parquet.exists():
        log.error(f"PASTA NÃO ENCONTRADA: {parquet}")
        _ready.set()
        return

    try:
        with _lock:
            # ── IES ──────────────────────────────────────────
            ies_path = parquet / "MICRODADOS_ED_SUP_IES_2024.parquet"
            if not ies_path.exists():
                log.error(f"Arquivo não encontrado: {ies_path}")
                _cache["ies"] = pd.DataFrame()
            else:
                ies = pd.read_parquet(ies_path)
                for c in ["QT_DOC_TOTAL", "QT_DOC_EXE", "QT_TEC_TOTAL"]:
                    if c in ies.columns:
                        ies[c] = pd.to_numeric(ies[c], errors="coerce")
                _cache["ies"] = ies
                log.info(f"IES carregado: {len(ies):,} linhas")

            # ── CURSOS ───────────────────────────────────────
            cursos_path = parquet / "MICRODADOS_CADASTRO_CURSOS_2024.parquet"
            if not cursos_path.exists():
                log.error(f"Arquivo não encontrado: {cursos_path}")
                _cache["cursos"] = pd.DataFrame()
            else:
                cursos = pd.read_parquet(cursos_path)
                for c in ["QT_MAT","QT_ING","QT_CONC","QT_VG_TOTAL",
                          "QT_MAT_FEM","QT_MAT_MASC","QT_ING_FEM","QT_ING_MASC",
                          "QT_CONC_FEM","QT_CONC_MASC"]:
                    if c in cursos.columns:
                        cursos[c] = pd.to_numeric(cursos[c], errors="coerce")
                _cache["cursos"] = cursos
                log.info(f"Cursos carregado: {len(cursos):,} linhas")

            # ── IBGE ─────────────────────────────────────────
            frames = [pd.read_parquet(f) for f in parquet.glob("tabela_2_1_*.parquet")]
            if frames:
                ibge = pd.concat(frames, ignore_index=True)
                for c in ["populacao", "area_km2", "densidade"]:
                    if c in ibge.columns:
                        ibge[c] = pd.to_numeric(ibge[c], errors="coerce")
                _cache["ibge"] = ibge
                log.info(f"IBGE carregado: {len(ibge):,} linhas")
            else:
                log.warning("Nenhum arquivo tabela_2_1_*.parquet encontrado — IBGE vazio")
                _cache["ibge"] = pd.DataFrame()

        log.info(f"Dados prontos em {time.time() - start:.1f}s")

    except Exception as e:
        '''log.exception(f"ERRO ao carregar dados: {e}")'''
        import traceback
        log.error("ERRO COMPLETO:")
        log.error(traceback.format_exc())


    finally:
        _ready.set()   # sempre libera, mesmo com erro


def start_loader():
    t = threading.Thread(target=_load, daemon=True, name="DataLoader")
    t.start()


def get_cursos() -> pd.DataFrame:
    _ready.wait()
    return _cache.get("cursos", pd.DataFrame())


def get_ies() -> pd.DataFrame:
    _ready.wait()
    return _cache.get("ies", pd.DataFrame())


def get_ibge() -> pd.DataFrame:
    _ready.wait()
    return _cache.get("ibge", pd.DataFrame())


def is_ready() -> bool:
    return _ready.is_set()


def aplicar_filtros(df: pd.DataFrame, params, prefixo: str = "curso") -> pd.DataFrame:
    if df.empty:
        return df

    col_regiao = "NO_REGIAO_IES" if prefixo == "ies" else "NO_REGIAO"
    col_uf     = "SG_UF_IES"     if prefixo == "ies" else "SG_UF"

    mapa = {
        col_regiao:                 params.get("regiao"),
        col_uf:                     params.get("uf"),
        "TP_MODALIDADE_ENSINO":     params.get("modalidade"),
        "NO_CINE_AREA_GERAL":       params.get("area"),
        "TP_REDE":                  params.get("rede"),
        "TP_GRAU_ACADEMICO":        params.get("grau"),
        "TP_ORGANIZACAO_ACADEMICA": params.get("org_academica"),
    }

    for col, val in mapa.items():
        if val and col in df.columns:
            df = df[df[col] == val]

    micro = params.get("microrregiao")
    mun   = params.get("municipio")
    if micro:
        c = "NO_MICRORREGIAO_IES" if prefixo == "ies" else "NO_MICRORREGIAO"
        if c in df.columns:
            df = df[df[c].str.contains(micro, case=False, na=False)]
    if mun:
        c = "NO_MUNICIPIO_IES" if prefixo == "ies" else "NO_MUNICIPIO"
        if c in df.columns:
            df = df[df[c].str.contains(mun, case=False, na=False)]

    return df