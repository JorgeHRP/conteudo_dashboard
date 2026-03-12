from functools import wraps
from flask import session, redirect, url_for, abort
import bcrypt
import config


# ─── HELPERS DE SESSÃO ───────────────────────────────

def get_current_user():
    """Retorna dict com dados do usuário logado ou None."""
    if "user_id" not in session:
        return None
    return {
        "id":       session.get("user_id"),
        "username": session.get("username"),
        "email":    session.get("email"),
        "role":     session.get("role"),
    }


def is_admin():
    user = get_current_user()
    return user and user["role"] == "admin"


def set_session(user: dict):
    """Popula a sessão após login bem-sucedido."""
    session.permanent = True
    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    session["email"]    = user["email"]
    session["role"]     = user["role"]


def clear_session():
    session.clear()


# ─── VERIFICAÇÃO DE SENHA ────────────────────────────

def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ─── AUTENTICAÇÃO ────────────────────────────────────

def authenticate(username: str, password: str):
    """
    Retorna dict do usuário autenticado ou None.
    Verifica admin master do .env primeiro, depois banco.
    """
    # Admin master via .env
    if (
        username == config.ADMIN_USERNAME
        and password == config.ADMIN_PASSWORD
    ):
        return {
            "id":       0,
            "username": config.ADMIN_USERNAME,
            "email":    config.ADMIN_EMAIL,
            "role":     "admin",
        }

    # Usuários do banco
    try:
        res = (
            config.supabase
            .table("users_conteudo_dash")
            .select("*")
            .eq("username", username)
            .eq("ativo", "true")
            .execute()
        )
        if not res.data:
            return None

        user = res.data[0]

        if not check_password(password, user["password_hash"]):
            return None

        # Atualiza ultimo_acesso
        from datetime import datetime, timezone
        config.supabase.table("users_conteudo_dash").update(
            {"ultimo_acesso": datetime.now(timezone.utc).isoformat()}
        ).eq("id", user["id"]).execute()

        return user

    except Exception as e:
        print(f"[auth] Erro ao autenticar: {e}")
        return None


# ─── MÓDULOS PERMITIDOS ──────────────────────────────

def get_allowed_modules(user_id: int, role: str) -> list:
    """Admin e analista veem tudo. Viewer só o que foi liberado."""
    if role in ("admin", "analista"):
        return config.MODULOS

    try:
        res = (
            config.supabase
            .table("user_modules_conteudo_dash")
            .select("modulo")
            .eq("user_id", str(user_id))
            .execute()
        )
        return [r["modulo"] for r in res.data]
    except Exception as e:
        print(f"[auth] Erro ao buscar módulos: {e}")
        return []


# ─── DECORADORES ─────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("login"))
        if user["role"] != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def module_required(modulo: str):
    """Decorador que verifica se o usuário tem acesso ao módulo."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for("login"))
            allowed = get_allowed_modules(user["id"], user["role"])
            if modulo not in allowed:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
