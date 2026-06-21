"""Schedule C category mapping.

Categories are defined in the data volume's config/categories.yaml (seeded from
the bundled template on first run), so installs can customize the list without
code changes.
"""
from __future__ import annotations

import yaml

from backend.app.core.config import settings

# Fallback if the config file is missing — the standard IRS Schedule C items.
_DEFAULT = [
    "Advertising", "Car and truck expenses", "Commissions and fees",
    "Contract labor", "Depreciation", "Insurance",
    "Legal and professional services", "Office expenses",
    "Rent or lease (equipment)", "Repairs and maintenance", "Supplies",
    "Taxes and licenses", "Travel", "Utilities", "Wages", "Other expenses",
]


# Personal-spending categories (not tax categories). Editable like the Schedule
# C list; users extend these freely.
_DEFAULT_PERSONAL = [
    "Housing", "Groceries", "Dining", "Transportation", "Utilities", "Health",
    "Insurance", "Entertainment", "Shopping", "Travel", "Education",
    "Savings/Investment", "Gifts/Donations", "Income", "Other",
]


def _load_list(filename: str, key: str, default: list[str]) -> list[str]:
    path = settings.config_dir / filename
    if not path.exists():
        return list(default)
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return list(default)
    values = data.get(key)
    return [str(c) for c in values] if values else list(default)


def load_categories() -> list[str]:
    """Return the configured Schedule C (business) categories."""
    return _load_list("categories.yaml", "categories", _DEFAULT)


def load_personal_categories() -> list[str]:
    """Return the configured personal-spending categories."""
    return _load_list("personal_categories.yaml", "personal_categories", _DEFAULT_PERSONAL)


def is_valid(category: str) -> bool:
    return category in load_categories()


def is_valid_personal(category: str) -> bool:
    return category in load_personal_categories()
