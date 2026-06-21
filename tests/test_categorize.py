"""Unit tests for payee normalization (tagging memory)."""
import pytest

pytest.importorskip("sqlalchemy")

from backend.app.services.categorize import normalize_payee


def test_normalize_collapses_whitespace_and_upcases():
    assert normalize_payee("  Adobe   Systems  ") == "ADOBE SYSTEMS"


def test_normalize_handles_none_and_empty():
    assert normalize_payee(None) == ""
    assert normalize_payee("   ") == ""


def test_normalize_is_stable_across_casing():
    assert normalize_payee("amazon WEB services") == normalize_payee("AMAZON web SERVICES")
