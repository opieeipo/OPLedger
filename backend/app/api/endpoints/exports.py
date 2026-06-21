"""Export endpoints: CSV (full ledger), TXF and PDF (tax filing)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.models.models import Transaction, TxnType
from backend.app.services import export, reports

router = APIRouter(tags=["export"])


def _attachment(filename: str) -> dict:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db), _=Depends(get_current_user)) -> Response:
    txns = db.scalars(select(Transaction).order_by(Transaction.posted)).all()
    return Response(
        content=export.to_csv(txns),
        media_type="text/csv",
        headers=_attachment("opledger.csv"),
    )


@router.get("/export/txf")
def export_txf(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> Response:
    stmt = select(Transaction).where(Transaction.txn_type == TxnType.business)
    if year is not None:
        stmt = stmt.where(
            Transaction.posted >= date(year, 1, 1),
            Transaction.posted <= date(year, 12, 31),
        )
    txns = db.scalars(stmt.order_by(Transaction.posted)).all()
    return Response(
        content=export.to_txf(txns),
        media_type="text/plain",
        headers=_attachment(f"opledger-{year or 'all'}.txf"),
    )


@router.get("/export/pdf")
def export_pdf(
    year: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> Response:
    summary = reports.schedule_c_summary(db, year)
    return Response(
        content=export.to_pdf(summary),
        media_type="application/pdf",
        headers=_attachment(f"opledger-schedule-c-{year}.pdf"),
    )
