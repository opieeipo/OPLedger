"""Reporting: P&L, Schedule C summary, and year-over-year comparison.

Bank sign convention: credits are positive, debits negative. For business
transactions, positive amounts are income (gross receipts) and negative amounts
are expenses, grouped by Schedule C category.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.models import Transaction, TxnType

_UNCATEGORIZED = "Uncategorized"


def _business_rows(
    db: Session,
    start: Optional[date],
    end: Optional[date],
    account_id: Optional[int],
):
    stmt = select(Transaction).where(Transaction.txn_type == TxnType.business)
    if start is not None:
        stmt = stmt.where(Transaction.posted >= start)
    if end is not None:
        stmt = stmt.where(Transaction.posted <= end)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    return db.scalars(stmt).all()


def pnl(
    db: Session,
    start: Optional[date] = None,
    end: Optional[date] = None,
    account_id: Optional[int] = None,
) -> dict:
    """Profit & loss over a period: income, expenses, net, and by-category."""
    income = Decimal("0")
    expenses = Decimal("0")
    by_category: dict[str, Decimal] = {}
    for txn in _business_rows(db, start, end, account_id):
        amount = txn.amount or Decimal("0")
        if amount >= 0:
            income += amount
        else:
            magnitude = -amount
            expenses += magnitude
            category = txn.schedule_c_category or _UNCATEGORIZED
            by_category[category] = by_category.get(category, Decimal("0")) + magnitude
    return {
        "start": start,
        "end": end,
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
        "by_category": [
            {"category": c, "amount": a}
            for c, a in sorted(by_category.items(), key=lambda kv: -kv[1])
        ],
    }


def schedule_c_summary(db: Session, year: int, account_id: Optional[int] = None) -> dict:
    """Schedule C summary for a tax year."""
    report = pnl(db, date(year, 1, 1), date(year, 12, 31), account_id)
    return {
        "year": year,
        "gross_receipts": report["income"],
        "total_expenses": report["expenses"],
        "net_profit": report["net"],
        "by_category": report["by_category"],
    }


def year_over_year(
    db: Session, start_year: int, end_year: int, account_id: Optional[int] = None
) -> dict:
    """Income/expenses/net for each year in the inclusive range."""
    years = []
    for year in range(start_year, end_year + 1):
        report = pnl(db, date(year, 1, 1), date(year, 12, 31), account_id)
        years.append({
            "year": year,
            "income": report["income"],
            "expenses": report["expenses"],
            "net": report["net"],
        })
    return {"years": years}
