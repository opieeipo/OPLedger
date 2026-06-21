"""QFX import and deduplication.

QFX is an open standard built on OFX (available since 1997) that every major
U.S. institution supports. We parse the file, normalize transactions, and
deduplicate on the bank-provided FITID so overlapping export windows are safe.
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class ParsedTransaction:
    fitid: str
    posted: date
    amount: float
    payee: str
    memo: str


def parse_qfx(raw: bytes) -> list[ParsedTransaction]:
    """Parse a QFX/OFX byte stream into normalized transactions."""
    raise NotImplementedError  # backed by ofxparse


def deduplicate(
    incoming: list[ParsedTransaction], existing_fitids: set[str]
) -> list[ParsedTransaction]:
    """Drop transactions whose FITID is already in the ledger."""
    return [t for t in incoming if t.fitid not in existing_fitids]
