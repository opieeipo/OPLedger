"""Read/write owner-configurable ledger settings.

Settings live in the key/value ``settings`` table alongside ledger_name and the
JWT secret, namespaced under a ``cfg.`` prefix. Values are stored as strings and
cast back to their typed form on read, falling back to the schema defaults.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.models import Setting
from backend.app.schemas import LedgerSettings, LedgerSettingsUpdate

_PREFIX = "cfg."

# How to parse each stored string back into its typed value.
_CASTS = {
    "ein": lambda v: v,
    "fiscal_year_start": int,
    "quarterly_method": lambda v: v,
    "quarterly_set_aside_rate": float,
    "quarterly_filing_status": lambda v: v,
    "quarterly_prior_year_tax": float,
}


def _key(field: str) -> str:
    # The ledger name lives under the existing "ledger_name" key so the /ledger
    # endpoint and these settings stay a single source of truth.
    return "ledger_name" if field == "name" else _PREFIX + field


def get_settings(db: Session) -> LedgerSettings:
    defaults = LedgerSettings()
    values = dict(defaults)
    name_row = db.get(Setting, "ledger_name")
    if name_row is not None:
        values["name"] = name_row.value
    for field, cast in _CASTS.items():
        row = db.get(Setting, _PREFIX + field)
        if row is None:
            continue
        try:
            values[field] = cast(row.value)
        except (TypeError, ValueError):
            pass  # keep the default on a malformed stored value
    return LedgerSettings(**values)


def update_settings(db: Session, update: LedgerSettingsUpdate) -> None:
    for field, value in update.model_dump(exclude_unset=True).items():
        key = _key(field)
        row = db.get(Setting, key)
        stored = "" if value is None else str(value)
        if row is None:
            db.add(Setting(key=key, value=stored))
        else:
            row.value = stored
    db.commit()
