from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.schemas import AuthOut, LoginInput, RegisterInput, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _auth_out(user: User) -> AuthOut:
    return AuthOut(access_token=create_access_token(user.id),
                   user=UserOut(id=user.id, email=user.email, name=user.name))


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterInput, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        # Generic message would be better for enumeration resistance; kept explicit for the MVP UX.
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return _auth_out(user)


@router.post("/login", response_model=AuthOut)
def login(body: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    return _auth_out(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, name=user.name)
