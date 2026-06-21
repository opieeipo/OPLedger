"""First-run setup and unlock.

These endpoints are deliberately outside the auth/unlock gate: they are how the
database first comes into existence and how it is unlocked on later boots.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, status

from backend.app.core.runtime import runtime
from backend.app.core.security import create_access_token, hash_password
from backend.app.db import database
from backend.app.models.models import Account, Role, Setting, User
from backend.app.schemas import SetupRequest, SetupStatus, Token, UnlockRequest

router = APIRouter(tags=["setup"])


def _load_jwt_secret(db) -> None:
    """Load the install's JWT secret from the DB into runtime state."""
    setting = db.get(Setting, "jwt_secret")
    runtime.jwt_secret = setting.value if setting else None


@router.get("/setup/status", response_model=SetupStatus)
def setup_status() -> SetupStatus:
    return SetupStatus(
        initialized=database.database_exists(),
        unlocked=runtime.unlocked,
    )


@router.post("/setup", response_model=Token, status_code=status.HTTP_201_CREATED)
def first_run_setup(body: SetupRequest) -> Token:
    """Create the encrypted database, the Owner account, and the ledger."""
    if database.database_exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already initialized; use /unlock",
        )

    # Creates the SQLCipher database keyed with the passphrase and builds schema.
    database.open_database(body.passphrase, create=True)

    db = database.new_session()
    try:
        jwt_secret = secrets.token_urlsafe(48)
        db.add_all(
            [
                Setting(key="jwt_secret", value=jwt_secret),
                Setting(key="ledger_name", value=body.ledger_name),
            ]
        )
        owner = User(
            username=body.owner_username,
            password_hash=hash_password(body.owner_password),
            role=Role.owner,
        )
        db.add(owner)
        if body.first_account is not None:
            db.add(
                Account(
                    nickname=body.first_account.nickname,
                    institution=body.first_account.institution,
                    account_number=body.first_account.account_number,
                )
            )
        db.commit()
        db.refresh(owner)

        runtime.jwt_secret = jwt_secret
        runtime.unlocked = True
        token = create_access_token(
            username=owner.username, user_id=owner.id, role=owner.role.value
        )
        return Token(access_token=token)
    finally:
        db.close()


@router.post("/unlock", status_code=status.HTTP_204_NO_CONTENT)
def unlock(body: UnlockRequest) -> None:
    """Unlock an existing encrypted database with the passphrase."""
    if not database.database_exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Not initialized; use /setup",
        )
    if runtime.unlocked:
        return None

    if not database.open_database(body.passphrase, create=False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect passphrase",
        )

    db = database.new_session()
    try:
        _load_jwt_secret(db)
    finally:
        db.close()
    runtime.unlocked = True
    return None
