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
    log.info("Iniciando carregamento otimizado de dados...")
    start   = time.time()
    parquet = Path(config.PARQUET_DIR).resolve()

    if not parquet.exists():
        log.error(f"PASTA NÃO ENCONTRADA: {parquet}")
        _ready.set()
        return

    try:
        with _lock:
            # ── IES (Colunas Essenciais) ──────────────────────
            ies_path = parquet / "MICRODADOS_ED_SUP_IES_2024.parquet"
            if ies_path.exists():
                # Carrega apenas o necessário para o dashboard e filtros
                cols_ies = [
                    "CO_IES", "NO_IES", "SG_IES", "SG_UF_IES", 
                    "TP_ORGANIZACAO_ACADEMICA", "NO_REGIAO_IES",
                    "NO_MICRORREGIAO_IES", "NO_MUNICIPIO_IES"
                ]
                ies = pd.read_parquet(ies_path, columns=cols_ies, engine='pyarrow')
                
                # Otimiza memória transformando textos repetitivos em categorias
                for col in ["SG_UF_IES", "NO_REGIAO_IES", "TP_ORGANIZACAO_ACADEMICA"]:
                    if col in ies.columns:
                        ies[col] = ies[col].astype("category")
                
                _cache["ies"] = ies
                log.info(f"IES carregado: {len(ies):,} linhas")
            else:
                log.error(f"Arquivo não encontrado: {ies_path}")
                _cache["ies"] = pd.DataFrame()

            # ── CURSOS (Colunas Essenciais) ───────────────────
            cursos_path = parquet / "MICRODADOS_CADASTRO_CURSOS_2024.parquet"
            if cursos_path.exists():
                # Lista exata das colunas usadas no seu app.py (KPIs e Gráficos)
                cols_cursos = [
                    "QT_MAT", "QT_ING", "QT_CONC", "QT_VG_TOTAL", 
                    "QT_MAT_FEM", "QT_MAT_MASC", "NO_REGIAO", "SG_UF", 
                    "TP_MODALIDADE_ENSINO", "NO_CINE_AREA_GERAL", "TP_REDE",
                    "TP_GRAU_ACADEMICO", "CO_IES", "NO_CURSO", 
                    "NO_MICRORREGIAO", "NO_MUNICIPIO"
                ]
                cursos = pd.read_parquet(cursos_path, columns=cols_cursos, engine='pyarrow')
                
                # Garante que colunas de contagem sejam numéricas e leves
                numeric_cols = ["QT_MAT", "QT_ING", "QT_CONC", "QT_VG_TOTAL"]
                for c in numeric_cols:
                    cursos[c] = pd.to_numeric(cursos[c], errors="coerce").fillna(0).astype("int32")
                
                # Otimização de memória para filtros
                cat_cols = ["SG_UF", "NO_REGIAO", "TP_MODALIDADE_ENSINO", "TP_REDE", "TP_GRAU_ACADEMICO"]
                for col in cat_cols:
                    if col in cursos.columns:
                        cursos[col] = cursos[col].astype("category")

                _cache["cursos"] = cursos
                log.info(f"Cursos carregado: {len(cursos):,} linhas")
            else:
                log.error(f"Arquivo não encontrado: {cursos_path}")
                _cache["cursos"] = pd.DataFrame()

            # ── IBGE (Opcional) ──────────────────────────────
            frames = [pd.read_parquet(f, engine='pyarrow') for f in parquet.glob("tabela_2_1_*.parquet")]
            if frames:
                _cache["ibge"] = pd.concat(frames, ignore_index=True)
                log.info(f"IBGE carregado: {len(_cache['ibge']):,} linhas")
            else:
                _cache["ibge"] = pd.DataFrame()

        log.info(f"Dados prontos em {time.time() - start:.1f}s")

    except Exception:
        import traceback
        log.error("ERRO CRÍTICO NO LOADER:")
        log.error(traceback.format_exc())
    finally:
        _ready.set()

def start_loader():
    # daemon=True garante que o thread não trave o desligamento do servidor
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

def aplicar_filtros(df: pd.DataFrame, params, prefixo: str = "curso") -> pd.DataFrame:
    if df.empty:
        return df

    col_regiao = "NO_REGIAO_IES" if prefixo == "ies" else "NO_REGIAO"
    col_uf     = "SG_UF_IES"     if prefixo == "ies" else "SG_UF"

    # Filtros exatos
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

    # Filtros de texto parcial (Município/Micro)
    for p_key, col_base in [("microrregiao", "NO_MICRORREGIAO"), ("municipio", "NO_MUNICIPIO")]:
        val = params.get(p_key)
        if val:
            c = f"{col_base}_IES" if prefixo == "ies" else col_base
            if c in df.columns:
                df = df[df[c].astype(str).str.contains(val, case=False, na=False)]

    return df