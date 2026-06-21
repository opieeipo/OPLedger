"""Unit tests for QFX deduplication (no third-party dependencies)."""
from datetime import date
from decimal import Decimal

from backend.app.services.qfx import ParsedTransaction, deduplicate


def _txn(fitid: str) -> ParsedTransaction:
    return ParsedTransaction(
        fitid=fitid, posted=date(2026, 1, 1), amount=Decimal("1.00"), payee="X", memo=""
    )


def test_skips_fitids_already_in_ledger():
    incoming = [_txn("A"), _txn("B"), _txn("C")]
    new, dupes = deduplicate(incoming, existing_fitids={"B"})
    assert [t.fitid for t in new] == ["A", "C"]
    assert dupes == 1


def test_collapses_duplicates_within_one_file():
    incoming = [_txn("A"), _txn("A"), _txn("B")]
    new, dupes = deduplicate(incoming, existing_fitids=set())
    assert [t.fitid for t in new] == ["A", "B"]
    assert dupes == 1


def test_no_overlap_imports_everything():
    incoming = [_txn("A"), _txn("B")]
    new, dupes = deduplicate(incoming, existing_fitids={"C", "D"})
    assert len(new) == 2
    assert dupes == 0


def test_empty_input():
    new, dupes = deduplicate([], existing_fitids={"A"})
    assert new == []
    assert dupes == 0
