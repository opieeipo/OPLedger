"""Quarterly estimated-tax calculation.

Three methods, selected in Settings:
  - set_aside:    a flat fraction of net profit set aside each quarter.
  - se_income:    self-employment tax (Social Security + Medicare, with the wage
                  base and additional-Medicare threshold) plus federal income tax
                  via brackets and filing status.
  - safe_harbor:  target the prior year's total tax, split across four quarters
                  (the IRS underpayment safe harbor).

These are ESTIMATES. The dollar constants are year-specific; defaults below are a
recent tax year and can be overridden in config/tax_constants.yaml so installs
stay current without code changes.
"""
from __future__ import annotations

from decimal import Decimal

import yaml

from backend.app.core.config import settings

_SE_RATE = Decimal("0.9235")        # 92.35% of net profit is subject to SE tax
_SS_RATE = Decimal("0.124")         # Social Security portion
_MEDICARE_RATE = Decimal("0.029")   # Medicare portion
_ADDL_MEDICARE_RATE = Decimal("0.009")

# Recent-year defaults (override in config/tax_constants.yaml).
_DEFAULTS = {
    "ss_wage_base": 168600,
    "standard_deduction": {
        "single": 14600, "married_joint": 29200,
        "married_separate": 14600, "head_of_household": 21900,
    },
    "addl_medicare_threshold": {
        "single": 200000, "married_joint": 250000,
        "married_separate": 125000, "head_of_household": 200000,
    },
    # Ordinary-income brackets: [upper_bound, rate]; final bound is null (∞).
    "brackets": {
        "single": [[11600, 0.10], [47150, 0.12], [100525, 0.22], [191950, 0.24], [243725, 0.32], [609350, 0.35], [None, 0.37]],
        "married_joint": [[23200, 0.10], [94300, 0.12], [201050, 0.22], [383900, 0.24], [487450, 0.32], [731200, 0.35], [None, 0.37]],
        "married_separate": [[11600, 0.10], [47150, 0.12], [100525, 0.22], [191950, 0.24], [243725, 0.32], [365600, 0.35], [None, 0.37]],
        "head_of_household": [[16550, 0.10], [63100, 0.12], [100500, 0.22], [191950, 0.24], [243700, 0.32], [609350, 0.35], [None, 0.37]],
    },
}


def _constants() -> dict:
    path = settings.config_dir / "tax_constants.yaml"
    if not path.exists():
        return _DEFAULTS
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return _DEFAULTS
    return {**_DEFAULTS, **data}  # top-level keys override defaults


def _income_tax(taxable: Decimal, brackets: list) -> Decimal:
    tax = Decimal("0")
    lower = Decimal("0")
    for upper, rate in brackets:
        cap = Decimal(str(upper)) if upper is not None else None
        slice_top = taxable if cap is None else min(taxable, cap)
        if slice_top > lower:
            tax += (slice_top - lower) * Decimal(str(rate))
        if cap is not None:
            lower = cap
        if cap is not None and taxable <= cap:
            break
    return tax


def _money(v: Decimal) -> float:
    return float(v.quantize(Decimal("0.01")))


def quarterly_estimate(
    net_profit: Decimal,
    *,
    method: str,
    set_aside_rate: float,
    filing_status: str,
    prior_year_tax: float,
) -> dict:
    """Return {method, net_profit, annual, per_quarter, detail{}} for the method."""
    net = net_profit if net_profit > 0 else Decimal("0")
    detail: dict[str, float] = {}

    if method == "safe_harbor":
        annual = Decimal(str(prior_year_tax))
        detail = {"prior_year_tax": float(prior_year_tax)}
    elif method == "se_income":
        c = _constants()
        wage_base = Decimal(str(c["ss_wage_base"]))
        std = Decimal(str(c["standard_deduction"].get(filing_status, c["standard_deduction"]["single"])))
        threshold = Decimal(str(c["addl_medicare_threshold"].get(filing_status, c["addl_medicare_threshold"]["single"])))
        brackets = c["brackets"].get(filing_status, c["brackets"]["single"])

        se_base = net * _SE_RATE
        se_tax = min(se_base, wage_base) * _SS_RATE + se_base * _MEDICARE_RATE
        if se_base > threshold:
            se_tax += (se_base - threshold) * _ADDL_MEDICARE_RATE
        half_se = se_tax / 2
        taxable = net - half_se - std
        if taxable < 0:
            taxable = Decimal("0")
        income_tax = _income_tax(taxable, brackets)
        annual = se_tax + income_tax
        detail = {
            "self_employment_tax": _money(se_tax),
            "income_tax": _money(income_tax),
            "half_se_deduction": _money(half_se),
            "taxable_income": _money(taxable),
            "filing_status": filing_status,
        }
    else:  # set_aside
        rate = Decimal(str(set_aside_rate))
        annual = net * rate
        detail = {"set_aside_rate": float(set_aside_rate)}

    return {
        "method": method,
        "net_profit": _money(net),
        "annual": _money(annual),
        "per_quarter": _money(annual / 4),
        "detail": detail,
    }
