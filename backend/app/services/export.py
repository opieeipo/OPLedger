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

# Map our Schedule C categories to their official Part II line numbers. Unknown
# (user-added) categories roll up into line 27a, "Other expenses".
_SCHEDULE_C_LINE = {
    "Advertising": "8",
    "Car and truck expenses": "9",
    "Commissions and fees": "10",
    "Contract labor": "11",
    "Depreciation": "13",
    "Insurance": "15",
    "Legal and professional services": "17",
    "Office expenses": "18",
    "Rent or lease (equipment)": "20a",
    "Repairs and maintenance": "21",
    "Supplies": "22",
    "Taxes and licenses": "23",
    "Travel": "24a",
    "Utilities": "25",
    "Wages": "26",
    "Other expenses": "27a",
}

# Full Part II line list in official order — rendered even when zero.
_PART_II_LINES = [
    ("8", "Advertising"),
    ("9", "Car and truck expenses"),
    ("10", "Commissions and fees"),
    ("11", "Contract labor"),
    ("12", "Depletion"),
    ("13", "Depreciation and section 179"),
    ("14", "Employee benefit programs"),
    ("15", "Insurance (other than health)"),
    ("16a", "Interest — Mortgage"),
    ("16b", "Interest — Other"),
    ("17", "Legal and professional services"),
    ("18", "Office expense"),
    ("19", "Pension and profit-sharing plans"),
    ("20a", "Rent or lease — Vehicles, machinery, equipment"),
    ("20b", "Rent or lease — Other business property"),
    ("21", "Repairs and maintenance"),
    ("22", "Supplies"),
    ("23", "Taxes and licenses"),
    ("24a", "Travel"),
    ("24b", "Deductible meals"),
    ("25", "Utilities"),
    ("26", "Wages"),
    ("27a", "Other expenses"),
]


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


def to_pdf(summary: dict, *, name: str | None = None, ein: str | None = None) -> bytes:
    """Render a Schedule C summary as a PDF that mirrors the official form layout.

    Follows the real Schedule C (Form 1040): Part I income (lines 1–7) and Part II
    expenses by their official line numbers (8–27), then totals and net profit.
    This is a formatted summary for records/filing support — not the fillable IRS
    form itself.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    accent = colors.HexColor("#2e6b52")
    rule = colors.HexColor("#d0d6c9")
    money = lambda v: f"{Decimal(v):,.2f}"  # noqa: E731

    gross = Decimal(summary["gross_receipts"])
    total_exp = Decimal(summary["total_expenses"])
    net = Decimal(summary["net_profit"])

    # Fold category amounts onto their official Part II lines; unknowns -> 27a.
    by_line: dict[str, Decimal] = {}
    for item in summary["by_category"]:
        line = _SCHEDULE_C_LINE.get(item["category"], "27a")
        by_line[line] = by_line.get(line, Decimal("0")) + Decimal(item["amount"])

    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading2"], textColor=accent, spaceBefore=14, spaceAfter=4, fontSize=12)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6c7873"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title=f"Schedule C {summary['year']}",
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    story = [
        Paragraph("Schedule C (Form 1040)", styles["Title"]),
        Paragraph(f"Profit or Loss From Business &nbsp;·&nbsp; Tax year {summary['year']}", small),
        Spacer(1, 10),
        Paragraph(f"<b>Name of proprietor:</b> {name or '—'} &nbsp;&nbsp;&nbsp; "
                  f"<b>EIN:</b> {ein or '—'}", styles["Normal"]),
    ]

    def money_table(rows):
        t = Table(rows, colWidths=[0.6 * inch, 4.6 * inch, 1.4 * inch], hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, rule),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return t

    # Part I — Income
    story += [Paragraph("Part I — Income", h), money_table([
        ["1", "Gross receipts or sales", money(gross)],
        ["2", "Returns and allowances", money(0)],
        ["3", "Subtract line 2 from line 1", money(gross)],
        ["4", "Cost of goods sold", money(0)],
        ["5", "Gross profit (line 3 − line 4)", money(gross)],
        ["6", "Other income", money(0)],
        ["7", "Gross income (line 5 + line 6)", money(gross)],
    ])]

    # Part II — Expenses
    part2 = [[num, desc, money(by_line.get(num, Decimal("0")))] for num, desc in _PART_II_LINES]
    part2.append(["28", "Total expenses", money(total_exp)])
    t2 = money_table(part2)
    t2.setStyle(TableStyle([("FONTNAME", (0, len(part2) - 1), (-1, len(part2) - 1), "Helvetica-Bold"),
                            ("LINEABOVE", (0, len(part2) - 1), (-1, len(part2) - 1), 0.8, accent)]))
    story += [Paragraph("Part II — Expenses", h), t2]

    # Net profit
    t3 = money_table([
        ["29", "Tentative profit (line 7 − line 28)", money(gross - total_exp)],
        ["30", "Expenses for business use of home", money(0)],
        ["31", "Net profit or (loss)", money(net)],
    ])
    t3.setStyle(TableStyle([("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                            ("TEXTCOLOR", (2, 2), (2, 2), accent)]))
    story += [Paragraph("Net Profit", h), t3, Spacer(1, 14),
              Paragraph("Generated by OPLedger from your categorized ledger. A formatted summary for "
                        "records and filing support — not the official IRS form. Lines without tracked "
                        "data show 0.00.", small)]

    doc.build(story)
    return buf.getvalue()
