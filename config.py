import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ─── FLASK ───────────────────────────────────────────
SECRET_KEY  = os.getenv("FLASK_SECRET_KEY", "dev-key-insegura")
FLASK_ENV   = os.getenv("FLASK_ENV", "production")
DEBUG       = os.getenv("FLASK_DEBUG", "False") == "True"
PARQUET_DIR = os.getenv("PARQUET_DIR", "parquet")

# ─── ADMIN MASTER (via .env, não entra no banco) ─────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# ─── SUPABASE ────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── MÓDULOS DISPONÍVEIS ─────────────────────────────
MODULOS = [
    "overview",
    "matriculas",
    "ingressantes",
    "concluintes",
    "funil",
    "cursos",
    "ies",
]
