"""Account management. Viewers can list; bookkeepers and owners can create."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db, require_role
from backend.app.models.models import Account, Role
from backend.app.schemas import AccountCreate, AccountOut

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db), _=Depends(get_current_user)
) -> list[Account]:
    return list(db.scalars(select(Account).order_by(Account.nickname)))


@router.post("/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    body: AccountCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role(Role.bookkeeper)),
) -> Account:
    account = Account(
        nickname=body.nickname,
        institution=body.institution,
        account_number=body.account_number,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account
