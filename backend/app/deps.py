"""Shared FastAPI dependencies: database session and the authenticated user."""
from typing import Iterator

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import User
from app.security import token_problem

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    def unauthorized(reason: str) -> HTTPException:
        # The detail text is what the browser checks; the reason travels in a header so the app can show it.
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in again.",
            headers={"WWW-Authenticate": "Bearer", "X-Auth-Reason": reason},
        )

    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized("no sign-in token was sent")
    user_id, reason = token_problem(creds.credentials)
    if not user_id:
        raise unauthorized(reason)
    user = db.get(User, user_id)
    if user is None:
        logging.getLogger("healthu.auth").warning("Token is valid but its user no longer exists (sub=%s)", user_id)
        raise unauthorized("account not found on this server (database changed or account deleted)")
    return user
