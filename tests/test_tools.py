"""
tests/test_tools.py
===================
Direct unit tests for the customer-service tools.

These don't touch the LLM at all — they hit the Python implementations to
verify each tool's HAPPY path AND its structured ERROR paths. Structured
errors are the contract: the loop relies on them to never raise into the
ReAct cycle, and the LLM relies on them to know how to recover.
"""
from __future__ import annotations

from src.agent.tools import (
    check_return_policy,
    lookup_order,
    lookup_refund,
    search_faq,
    update_shipping_address,
)


# ---------- lookup_order ----------
def test_lookup_order_happy():
    out = lookup_order("A1001")
    assert out["status"] == "shipped"
    assert out["tracking"] == "SF1234567890"


def test_lookup_order_case_insensitive():
    assert lookup_order("a1001")["order_id"] == "A1001"


def test_lookup_order_not_found():
    out = lookup_order("Z9999")
    assert out == {"error": "ORDER_NOT_FOUND", "order_id": "Z9999"}


# ---------- lookup_refund ----------
def test_lookup_refund_approved():
    out = lookup_refund("A1003")
    assert out["status"] == "approved"
    assert out["amount_usd"] == 12.99


def test_lookup_refund_rejected():
    out = lookup_refund("A1001")
    assert out["status"] == "rejected"
    assert "reason" in out


def test_lookup_refund_none_on_record():
    """A1002 exists but never requested a refund — must NOT 404."""
    out = lookup_refund("A1002")
    assert out["status"] == "NO_REFUND_FOUND"


def test_lookup_refund_order_not_found():
    out = lookup_refund("Z9999")
    assert out["error"] == "ORDER_NOT_FOUND"


# ---------- update_shipping_address ----------
def test_update_address_processing_allowed():
    """A1002 is 'processing' — change should go through."""
    out = update_shipping_address("A1002", "500 King St, Toronto, ON")
    assert out["status"] == "updated"
    assert out["new_address"] == "500 King St, Toronto, ON"


def test_update_address_shipped_blocked():
    """A1001 is already 'shipped' — must be ADDRESS_LOCKED."""
    out = update_shipping_address("A1001", "99 New St, Beijing")
    assert out["error"] == "ADDRESS_LOCKED"


def test_update_address_invalid_input():
    out = update_shipping_address("A1002", ".")
    assert out["error"] == "ADDRESS_INVALID"


def test_update_address_order_not_found():
    out = update_shipping_address("Z9999", "anywhere valid")
    assert out["error"] == "ORDER_NOT_FOUND"


# ---------- check_return_policy ----------
def test_return_policy_electronics():
    out = check_return_policy("electronics")
    assert out["window_days"] == 15


def test_return_policy_unknown_category_lists_available():
    out = check_return_policy("furniture")
    assert out["error"] == "CATEGORY_NOT_FOUND"
    assert "available_categories" in out


# ---------- search_faq ----------
def test_search_faq_returns_results():
    out = search_faq("shipping delivery time")
    assert "results" in out
    assert len(out["results"]) > 0
