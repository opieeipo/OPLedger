"""Shared FastAPI dependencies: DB sessions, unlock gate, auth, and roles."""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.runtime import runtime
from backend.app.core.security import decode_token
from backend.app.db import database
from backend.app.models.models import Role, User

# Bearer token in the Authorization header. tokenUrl is informational (our
# login accepts JSON, not form data) and only affects the OpenAPI docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

# Role ordering for hierarchical checks (owner ⊇ bookkeeper ⊇ viewer).
_ROLE_RANK = {Role.viewer: 0, Role.bookkeeper: 1, Role.owner: 2}


def require_unlocked() -> None:
    """Block requests until the encrypted database has been unlocked."""
    if not runtime.unlocked:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is locked",
        )


def get_db(_: None = Depends(require_unlocked)) -> Iterator[Session]:
    """Yield a database session (only once the DB is unlocked)."""
    session = database.new_session()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the bearer token."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    claims = decode_token(token)
    if not claims or "uid" not in claims:
        raise credentials_error
    user = db.get(User, claims["uid"])
    if user is None:
        raise credentials_error
    return user


def require_role(minimum: Role):
    """Dependency factory: require at least the given role."""

    def _check(user: User = Depends(get_current_user)) -> User:
        if _ROLE_RANK[user.role] < _ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check
