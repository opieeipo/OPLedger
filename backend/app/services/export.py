"""Ledger exports: TXF, CSV, and PDF.

- TXF imports into TurboTax and most desktop tax software for Schedule C.
- CSV is for manual review or CPA handoff.
- PDF is a formatted Schedule C summary for records or filing support.
"""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Iterable

from backend.app.models.models import Transaction, TxnType

# Best-effort map from Schedule C category to TXF reference number. TXF codes
# should be validated against current tax-software versions before relying on a
# return (see the roadmap/contributing notes); unknown categories fall back to
# "Other expenses" (312).
_TXF_CODES = {
    "Advertising": 290,
    "Car and truck expenses": 292,
    "Commissions and fees": 293,
    "Contract labor": 311,
    "Depreciation": 295,
    "Insurance": 297,
    "Legal and professional services": 300,
    "Office expenses": 301,
    "Rent or lease (equipment)": 303,
    "Repairs and maintenance": 305,
    "Supplies": 306,
    "Taxes and licenses": 307,
    "Travel": 308,
    "Utilities": 310,
    "Wages": 311,
    "Other expenses": 312,
}
_TXF_OTHER = 312
_TXF_GROSS_RECEIPTS = 287


def to_csv(transactions: Iterable[Transaction]) -> str:
    """Render the full ledger as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["date", "account", "payee", "memo", "amount", "type", "schedule_c_category"]
    )
    for txn in transactions:
        writer.writerow([
            txn.posted.isoformat(),
            txn.account.nickname if txn.account else "",
            txn.payee or "",
            txn.memo or "",
            f"{txn.amount:.2f}",
            txn.txn_type.value if txn.txn_type else "",
            txn.schedule_c_category or "",
        ])
    return buf.getvalue()


def to_txf(transactions: Iterable[Transaction], export_date: date | None = None) -> str:
    """Render business transactions as a TXF document for tax-software import."""
    export_date = export_date or date.today()
    lines = ["V042", "AOPLedger", f"D{export_date.strftime('%m/%d/%Y')}", "^"]
    for txn in transactions:
        if txn.txn_type != TxnType.business:
            continue
        amount = txn.amount or Decimal("0")
        if amount >= 0:
            code = _TXF_GROSS_RECEIPTS
        else:
            code = _TXF_CODES.get(txn.schedule_c_category or "", _TXF_OTHER)
        lines += [
            "TD",
            f"N{code}",
            "C1",
            "L1",
            f"${abs(amount):.2f}",
            f"P{txn.payee or ''}",
            "^",
        ]
    return "\n".join(lines) + "\n"


def to_pdf(summary: dict) -> bytes:
    """Render a Schedule C summary dict (see services.reports) as a PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title="OPLedger Schedule C")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Schedule C Summary — {summary['year']}", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Gross receipts: {Decimal(summary['gross_receipts']):.2f}", styles["Normal"]),
        Paragraph(f"Total expenses: {Decimal(summary['total_expenses']):.2f}", styles["Normal"]),
        Paragraph(f"Net profit: {Decimal(summary['net_profit']):.2f}", styles["Normal"]),
        Spacer(1, 18),
    ]
    rows = [["Category", "Amount"]]
    for item in summary["by_category"]:
        rows.append([item["category"], f"{Decimal(item['amount']):.2f}"])
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a2129")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()
