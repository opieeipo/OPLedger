"""Tagging memory and auto-categorization by payee.

When a transaction is tagged, OPLedger remembers the choice as a payee rule.
The next time a transaction from the same payee is imported, the rule is applied
automatically — so categorization is a one-time effort per vendor.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.models import PayeeRule, Transaction, TxnType

_WS = re.compile(r"\s+")


def normalize_payee(payee: str | None) -> str:
    """Normalize a payee name into a stable match key.

    Upper-cases, trims, and collapses whitespace so trivial formatting
    differences from the bank don't fragment the same vendor.
    """
    return _WS.sub(" ", (payee or "").strip().upper())


def remember(
    db: Session,
    payee: str | None,
    txn_type: TxnType,
    schedule_c_category: Optional[str],
) -> Optional[PayeeRule]:
    """Persist (or update) the auto-tagging rule learned from a tag action."""
    pattern = normalize_payee(payee)
    if not pattern:
        return None
    rule = db.scalar(select(PayeeRule).where(PayeeRule.pattern == pattern))
    if rule is None:
        rule = PayeeRule(pattern=pattern)
        db.add(rule)
    rule.txn_type = txn_type
    rule.schedule_c_category = schedule_c_category
    rule.enabled = True
    return rule


def suggest(db: Session, payee: str | None) -> Optional[PayeeRule]:
    """Return the enabled rule matching this payee, if any."""
    pattern = normalize_payee(payee)
    if not pattern:
        return None
    return db.scalar(
        select(PayeeRule).where(
            PayeeRule.pattern == pattern, PayeeRule.enabled.is_(True)
        )
    )


def apply_rules(db: Session, transactions: Iterable[Transaction]) -> int:
    """Auto-tag untagged transactions from known payees. Returns count tagged."""
    tagged = 0
    cache: dict[str, Optional[PayeeRule]] = {}
    for txn in transactions:
        if txn.txn_type is not None:
            continue
        key = normalize_payee(txn.payee)
        if key not in cache:
            cache[key] = suggest(db, txn.payee)
        rule = cache[key]
        if rule is not None:
            txn.txn_type = rule.txn_type
            txn.schedule_c_category = rule.schedule_c_category
            tagged += 1
    return tagged
