"""Reporting endpoints: P&L, Schedule C summary, year-over-year."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.schemas import PnLReport, QuarterlyEstimate, ScheduleCSummary, YearOverYear
from backend.app.services import reports, settings_store, tax

router = APIRouter(tags=["reports"])


@router.get("/reports/pnl", response_model=PnLReport)
def pnl_report(
    start: Optional[date] = None,
    end: Optional[date] = None,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> dict:
    return reports.pnl(db, start, end, account_id)


@router.get("/reports/schedule-c", response_model=ScheduleCSummary)
def schedule_c(
    year: int,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> dict:
    return reports.schedule_c_summary(db, year, account_id)


@router.get("/reports/quarterly-estimate", response_model=QuarterlyEstimate)
def quarterly_estimate(
    start: Optional[date] = None,
    end: Optional[date] = None,
    periods_per_year: int = 4,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> dict:
    # Net profit over the requested window, scaled to an annual basis: ×1 for a
    # full-year window, ×4 for a single quarter (annualized installment).
    net = reports.pnl(db, start, end)["net"]
    annual_net = Decimal(net) * periods_per_year
    cfg = settings_store.get_settings(db)
    return tax.quarterly_estimate(
        annual_net,
        method=cfg.quarterly_method,
        set_aside_rate=cfg.quarterly_set_aside_rate,
        filing_status=cfg.quarterly_filing_status,
        prior_year_tax=cfg.quarterly_prior_year_tax,
    )


@router.get("/reports/year-over-year", response_model=YearOverYear)
def year_over_year(
    start_year: int,
    end_year: int,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> dict:
    return reports.year_over_year(db, start_year, end_year, account_id)
