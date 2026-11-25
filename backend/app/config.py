"""Runtime configuration for Health-U, read from environment variables (and backend/.env).

Secrets are never hard-coded. See backend/.env.example for every variable.
"""
import logging
import os
import secrets

from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Explicit path: avoids find_dotenv() failures when run from stdin or a heredoc.
load_dotenv(os.path.join(BACKEND_DIR, ".env"), override=False)

log = logging.getLogger("healthu")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BACKEND_DIR, 'healthu.db')}")
REPORTS_DIR: str = os.getenv("REPORTS_DIR", os.path.join(BACKEND_DIR, "reports"))
MAX_UPLOAD_BYTES: int = _int("MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
MAX_UPLOAD_PAGES: int = _int("MAX_UPLOAD_PAGES", 20)
TOKEN_TTL_MINUTES: int = _int("TOKEN_TTL_MINUTES", 60 * 24)
CORS_ORIGINS: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

def _load_jwt_secret() -> str:
    """Use JWT_SECRET if set. Otherwise share one secret through a private file.

    A random per-process secret breaks sign-in whenever the API restarts or runs more than one worker:
    a token issued by one process is rejected by another, which the app shows as a sign-out.
    """
    configured = os.getenv("JWT_SECRET", "").strip()
    if configured:
        return configured
    path = os.path.join(BACKEND_DIR, ".jwt_secret")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            stored = fh.read().strip()
        if stored:
            return stored
    except FileNotFoundError:
        pass
    fresh = secrets.token_urlsafe(48)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(fresh)
    log.warning("JWT_SECRET is not set; created backend/.jwt_secret. Set JWT_SECRET in production.")
    return fresh


JWT_SECRET: str = _load_jwt_secret()
