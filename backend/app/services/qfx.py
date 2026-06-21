"""QFX import and deduplication.

QFX is an open standard built on OFX (available since 1997) that every major
U.S. institution supports. We parse the file, normalize transactions, and
deduplicate on the bank-provided FITID so overlapping export windows are safe.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class ParsedTransaction:
    fitid: str
    posted: date
    amount: Decimal
    payee: str
    memo: str


def parse_qfx(raw: bytes) -> list[ParsedTransaction]:
    """Parse a QFX/OFX byte stream into normalized transactions.

    Transactions across all statements in the file are flattened; account
    routing is decided by the caller (the import targets one ledger account).
    """
    from ofxparse import OfxParser  # lazy: keeps dedup logic import-light

    ofx = OfxParser.parse(io.BytesIO(raw))
    parsed: list[ParsedTransaction] = []
    for account in ofx.accounts:
        for txn in account.statement.transactions:
            posted = txn.date.date() if hasattr(txn.date, "date") else txn.date
            parsed.append(
                ParsedTransaction(
                    fitid=str(txn.id),
                    posted=posted,
                    amount=Decimal(str(txn.amount)),
                    payee=(txn.payee or "").strip(),
                    memo=(txn.memo or "").strip(),
                )
            )
    return parsed


def deduplicate(
    incoming: list[ParsedTransaction], existing_fitids: set[str]
) -> tuple[list[ParsedTransaction], int]:
    """Split incoming transactions into (new, duplicate_count).

    A transaction is a duplicate if its FITID already exists for the account, or
    if it repeats within the same file. FITID is the bank's stable per-account
    transaction identifier, which is exactly what makes overlapping exports safe.
    """
    new: list[ParsedTransaction] = []
    seen: set[str] = set(existing_fitids)
    duplicates = 0
    for txn in incoming:
        if txn.fitid in seen:
            duplicates += 1
            continue
        seen.add(txn.fitid)
        new.append(txn)
    return new, duplicates
