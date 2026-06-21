"""Authentication: exchange credentials for a JWT session token."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.core.security import create_access_token, verify_password
from backend.app.models.models import Setting, User
from backend.app.schemas import LoginRequest, Token, UserOut

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(
        username=user.username, user_id=user.id, role=user.role.value
    )
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/ledger")
def ledger(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict:
    """Return the ledger name set during first-run setup."""
    name = db.get(Setting, "ledger_name")
    return {"name": name.value if name else "OPLedger"}
