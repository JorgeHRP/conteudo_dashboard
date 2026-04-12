import threading
import time
import logging
from pathlib import Path
import pandas as pd
import config

log = logging.getLogger(__name__)

# Cache global para armazenar os dados na RAM
_cache: dict = {}
_lock  = threading.Lock()
_ready = threading.Event()

def _load():
    """Carregamento otimizado para dados agregados com correção de tipagem"""
    log.info("Iniciando carregamento de dados otimizados...")
    start = time.time()
    parquet_dir = Path(config.PARQUET_DIR).resolve()

    if not parquet_dir.exists():
        log.error(f"PASTA DE DADOS NÃO ENCONTRADA: {parquet_dir}")
        _ready.set()
        return

    try:
        with _lock:
            # 1. CARREGAR CURSOS (Versão Agregada)
            cursos_path = parquet_dir / "MICRODADOS_CADASTRO_CURSOS_2024.parquet"
            if cursos_path.exists():
                # Colunas reais presentes no seu arquivo otimizado
                cols_cursos = [
                    "QT_MAT", "QT_ING", "QT_CONC", "QT_VG_TOTAL", 
                    "QT_MAT_FEM", "QT_MAT_MASC", "NO_REGIAO", "SG_UF", 
                    "TP_MODALIDADE_ENSINO", "NO_CINE_AREA_GERAL", "TP_REDE",
                    "TP_GRAU_ACADEMICO", "CO_IES", "NO_CURSO", "NO_MUNICIPIO"
                ]
                
                df_cursos = pd.read_parquet(cursos_path, columns=cols_cursos, engine='pyarrow')

                # --- CORREÇÃO CRÍTICA PARA EVITAR VALUERROR (750 MIL DÍGITOS) ---
                # Garante que as métricas sejam tratadas como números, não como texto
                metricas = ["QT_MAT", "QT_ING", "QT_CONC", "QT_VG_TOTAL", "QT_MAT_FEM", "QT_MAT_MASC"]
                for col in metricas:
                    if col in df_cursos.columns:
                        # Converte para numérico, forçando erros para NaN e depois para 0
                        df_cursos[col] = pd.to_numeric(df_cursos[col], errors='coerce').fillna(0).astype('int64')

                # Otimização de memória usando categorias para colunas de texto repetitivo
                cat_cols = ["SG_UF", "NO_REGIAO", "TP_MODALIDADE_ENSINO", "TP_REDE", "TP_GRAU_ACADEMICO"]
                for col in cat_cols:
                    if col in df_cursos.columns:
                        df_cursos[col] = df_cursos[col].astype("category")

                _cache["cursos"] = df_cursos
                log.info(f"Cursos carregados com sucesso: {len(df_cursos):,} registros.")
            else:
                log.error(f"Arquivo de cursos não encontrado: {cursos_path}")

            # 2. CARREGAR IES
            ies_path = parquet_dir / "MICRODADOS_ED_SUP_IES_2024.parquet"
            if ies_path.exists():
                cols_ies = [
                    "CO_IES", "NO_IES", "SG_IES", "SG_UF_IES", 
                    "TP_ORGANIZACAO_ACADEMICA", "NO_REGIAO_IES", "NO_MUNICIPIO_IES"
                ]
                df_ies = pd.read_parquet(ies_path, columns=cols_ies, engine='pyarrow')
                
                if "SG_UF_IES" in df_ies.columns:
                    df_ies["SG_UF_IES"] = df_ies["SG_UF_IES"].astype("category")
                
                _cache["ies"] = df_ies
                log.info(f"IES carregadas com sucesso: {len(df_ies):,} registros.")

    except Exception as e:
        log.error(f"ERRO CRÍTICO NO LOADER: {e}")
    finally:
        _ready.set()
        log.info(f"Carga de dados finalizada em {time.time() - start:.2f}s")

def start_loader():
    """Inicia o carregamento em thread separada"""
    t = threading.Thread(target=_load, daemon=True, name="DataLoaderThread")
    t.start()

def get_cursos() -> pd.DataFrame:
    _ready.wait()
    return _cache.get("cursos", pd.DataFrame())

def get_ies() -> pd.DataFrame:
    _ready.wait()
    return _cache.get("ies", pd.DataFrame())

def aplicar_filtros(df: pd.DataFrame, params, prefixo: str = "curso") -> pd.DataFrame:
    """Aplica filtros baseados nos parâmetros da requisição"""
    if df is None or df.empty:
        return pd.DataFrame()

    # Define colunas dinamicamente
    col_regiao = "NO_REGIAO_IES" if prefixo == "ies" else "NO_REGIAO"
    col_uf     = "SG_UF_IES"     if prefixo == "ies" else "SG_UF"
    col_mun    = "NO_MUNICIPIO_IES" if prefixo == "ies" else "NO_MUNICIPIO"

    # Dicionário de filtros exatos
    filtros = {
        col_regiao:                 params.get("regiao"),
        col_uf:                     params.get("uf"),
        "TP_MODALIDADE_ENSINO":     params.get("modalidade"),
        "NO_CINE_AREA_GERAL":       params.get("area"),
        "TP_REDE":                  params.get("rede"),
        "TP_GRAU_ACADEMICO":        params.get("grau"),
        "TP_ORGANIZACAO_ACADEMICA": params.get("org_academica"),
    }

    # Aplica cada filtro presente nos parâmetros
    for col, val in filtros.items():
        if val and col in df.columns:
            # Força comparação como string para evitar erros de tipo
            df = df[df[col].astype(str) == str(val)]

    # Filtro de texto parcial para município
    mun_val = params.get("municipio")
    if mun_val and col_mun in df.columns:
        df = df[df[col_mun].astype(str).str.contains(mun_val, case=False, na=False)]

    return df