"""Recurring transaction detection.

Groups transactions by payee and approximate amount, then flags series of three
or more occurrences at a regular cadence (weekly, biweekly, monthly, annual).
Useful for spotting subscriptions and predictable expenses.
"""
from __future__ import annotations

from decimal import Decimal
from statistics import mean
from typing import Iterable

from backend.app.models.models import Transaction
from backend.app.services.categorize import normalize_payee

# (label, low, high) inclusive day-gap windows for each cadence.
_CADENCES = [
    ("weekly", 6, 8),
    ("biweekly", 12, 16),
    ("monthly", 27, 32),
    ("quarterly", 85, 95),
    ("annual", 358, 372),
]

_MIN_OCCURRENCES = 3


def _classify(avg_gap: float) -> str:
    for label, low, high in _CADENCES:
        if low <= avg_gap <= high:
            return label
    return "irregular"


def detect(transactions: Iterable[Transaction]) -> list[dict]:
    """Return detected recurring series, most recent first."""
    groups: dict[tuple[str, int], list[Transaction]] = {}
    for txn in transactions:
        key = (normalize_payee(txn.payee), int(round(abs(txn.amount or Decimal("0")))))
        groups.setdefault(key, []).append(txn)

    series: list[dict] = []
    for (payee, _amount), rows in groups.items():
        if len(rows) < _MIN_OCCURRENCES or not payee:
            continue
        dates = sorted(t.posted for t in rows)
        gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
        if len(gaps) < _MIN_OCCURRENCES - 1:
            continue
        avg_gap = mean(gaps)
        cadence = _classify(avg_gap)
        if cadence == "irregular":
            continue
        # Representative amount = mean magnitude, to 2dp.
        amount = (sum((abs(t.amount or Decimal("0")) for t in rows), Decimal("0")) / len(rows))
        series.append({
            "payee": rows[-1].payee or payee,
            "amount": amount.quantize(Decimal("0.01")),
            "occurrences": len(rows),
            "cadence": cadence,
            "average_gap_days": round(avg_gap, 1),
            "last_seen": dates[-1],
        })

    series.sort(key=lambda s: s["last_seen"], reverse=True)
    return series
