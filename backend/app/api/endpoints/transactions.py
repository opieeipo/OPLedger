"""Transactions: QFX import (with dedup), listing, and tagging."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db, require_role
from backend.app.models.models import Account, Role, Transaction
from backend.app.schemas import ImportResult, TagRequest, TransactionOut
from backend.app.services import qfx

router = APIRouter(tags=["transactions"])


@router.post(
    "/transactions/import",
    response_model=ImportResult,
    status_code=status.HTTP_201_CREATED,
)
def import_qfx(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_role(Role.bookkeeper)),
) -> ImportResult:
    """Import a QFX file into an account, deduplicating on FITID."""
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown account")

    raw = file.file.read()
    try:
        parsed = qfx.parse_qfx(raw)
    except Exception as exc:  # malformed/unsupported file
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse QFX file: {exc}",
        )

    existing = set(
        db.scalars(
            select(Transaction.fitid).where(Transaction.account_id == account_id)
        )
    )
    new_txns, duplicates = qfx.deduplicate(parsed, existing)

    db.add_all(
        Transaction(
            account_id=account_id,
            fitid=t.fitid,
            posted=t.posted,
            amount=t.amount,
            payee=t.payee,
            memo=t.memo,
        )
        for t in new_txns
    )
    db.commit()

    return ImportResult(
        parsed=len(parsed), imported=len(new_txns), duplicates=duplicates
    )


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    account_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[Transaction]:
    stmt = select(Transaction).order_by(Transaction.posted.desc(), Transaction.id.desc())
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    return list(db.scalars(stmt))


@router.post("/transactions/{txn_id}/tag", response_model=TransactionOut)
def tag_transaction(
    txn_id: int,
    body: TagRequest,
    db: Session = Depends(get_db),
    _=Depends(require_role(Role.bookkeeper)),
) -> Transaction:
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    txn.txn_type = body.txn_type
    txn.schedule_c_category = body.schedule_c_category
    db.commit()
    db.refresh(txn)
    return txn
