"""Ledger exports: TXF, CSV, and PDF.

- TXF imports directly into TurboTax and most desktop tax software for Schedule C.
- CSV is for manual review or CPA handoff.
- PDF is a formatted P&L + Schedule C summary for records or filing support.
"""
from typing import Iterable

from backend.app.models.models import Transaction


def to_txf(transactions: Iterable[Transaction]) -> str:
    """Render business transactions as a TXF document for tax software import."""
    raise NotImplementedError


def to_csv(transactions: Iterable[Transaction]) -> str:
    """Render the full ledger as CSV."""
    raise NotImplementedError


def to_pdf(transactions: Iterable[Transaction]) -> bytes:
    """Render a formatted P&L and Schedule C summary PDF (reportlab)."""
    raise NotImplementedError
