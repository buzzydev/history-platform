import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bool(name, default=False):
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _fix_url(url):
    if url and url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def load_config():
    env = os.environ.get("APP_ENV", "development")
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        if env == "production":
            raise RuntimeError("SECRET_KEY environment variable is required in production")
        secret = "dev-only-insecure-secret-key"
    db_url = _fix_url(os.environ.get("DATABASE_URL")) or "sqlite:///" + os.path.join(BASE_DIR, "instance", "dev.db")
    return {
        "SECRET_KEY": secret,
        "APP_ENV": env,
        "DATABASE_URL": db_url,
        "BACKUP_DATABASE_URL": _fix_url(os.environ.get("BACKUP_DATABASE_URL")) or "",
        "MAX_CONTENT_LENGTH": int(os.environ.get("PDF_MAX_MB", "25")) * 1024 * 1024,
        "PDF_MAX_PAGES": int(os.environ.get("PDF_MAX_PAGES", "300")),
        "OCR_LANGS": os.environ.get("OCR_LANGS", "uzb+uzb_cyrl+rus+eng"),
        "TZ_OFFSET_HOURS": int(os.environ.get("TZ_OFFSET_HOURS", "5")),
        "SESSION_COOKIE_SECURE": env == "production",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": 60 * 60 * 24 * 30,
        "RUN_SCHEDULER": _bool("RUN_SCHEDULER", True),
        "TESTING": False,
    }
