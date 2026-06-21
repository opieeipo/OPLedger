"""Account management. Viewers can list; bookkeepers and owners can create."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db, require_role
from backend.app.models.models import Account, Role, Transaction
from backend.app.schemas import AccountCreate, AccountOut, AccountUpdate

router = APIRouter(tags=["accounts"])


def _get_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown account")
    return account


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


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int,
    body: AccountUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role(Role.bookkeeper)),
) -> Account:
    account = _get_account(db, account_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role(Role.bookkeeper)),
) -> None:
    account = _get_account(db, account_id)
    # Refuse to orphan financial records — SQLite won't enforce the FK for us.
    txn_count = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.account_id == account_id)
    )
    if txn_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account has {txn_count} transaction(s). Remove them before deleting the account.",
        )
    db.delete(account)
    db.commit()
