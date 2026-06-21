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


def load_categories() -> list[str]:
    """Return the configured Schedule C categories."""
    path = settings.config_dir / "categories.yaml"
    if not path.exists():
        return list(_DEFAULT)
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return list(_DEFAULT)
    categories = data.get("categories")
    return [str(c) for c in categories] if categories else list(_DEFAULT)


def is_valid(category: str) -> bool:
    return category in load_categories()
