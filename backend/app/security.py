"""Password hashing (PBKDF2-SHA256 from the standard library) and signed access tokens (HS256 JWT)."""
import hashlib
import logging
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.config import JWT_SECRET, TOKEN_TTL_MINUTES

PBKDF2_ITERATIONS = 310_000
_ALGO = "HS256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(candidate.hex(), digest_hex)


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=TOKEN_TTL_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=_ALGO)


log = logging.getLogger("healthu.auth")


def token_problem(token: str) -> tuple[str | None, str]:
    """Returns (user_id, "ok") for a valid token, or (None, reason) explaining why it was rejected."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[_ALGO])
    except jwt.ExpiredSignatureError:
        reason = "token expired"
    except jwt.InvalidSignatureError:
        reason = "token signed with a different JWT_SECRET"
    except jwt.PyJWTError as exc:
        reason = f"token malformed or invalid ({type(exc).__name__})"
    else:
        return payload.get("sub"), "ok"
    # The reason tells us why the browser was signed out (expired, bad signature, malformed, ...).
    log.warning("Rejected token: %s", reason)
    return None, reason


def decode_access_token(token: str) -> str | None:
    return token_problem(token)[0]
