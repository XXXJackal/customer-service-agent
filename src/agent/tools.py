"""
src/agent/tools.py
==================
The agent's action surface. Six customer-service tools:

    search_faq               — look up a knowledge-base article
    lookup_order             — fetch order status by id
    lookup_refund            — fetch refund status by order id
    update_shipping_address  — change the shipping address of a pending order
    check_return_policy      — fetch return rules by product category
    escalate_to_human        — hand off to a human operator

We hand-write the JSON schemas the LLM will see (TOOL_SPECS) AND the Python
implementations (TOOLS). Both are deliberately small so the loop is the focus,
not the tools themselves.

Adding a new tool? Three steps:
    1. write a Python function that takes typed kwargs and returns a dict
       (use {"error": "..."} for structured errors — never raise to the loop)
    2. add a JSON Schema entry to TOOL_SPECS
    3. register it in the TOOLS dict at the bottom of this file
Then add at least one expected_tools test case to eval/cases.jsonl.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Knowledge base — loaded once at import time
# ---------------------------------------------------------------------------
_FAQ_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge", "faq.json")
with open(_FAQ_PATH, encoding="utf-8") as f:
    _FAQ: list[dict[str, str]] = json.load(f)

# Fake order database for the demo
# `shipping_address` lives here so update_shipping_address can mutate it.
_ORDERS: dict[str, dict[str, Any]] = {
    "A1001": {"status": "shipped", "carrier": "SF Express", "tracking": "SF1234567890",
              "eta": "2026-06-22", "items": ["Wireless Headphones"],
              "shipping_address": "1 Market St, San Francisco, CA"},
    "A1002": {"status": "processing", "carrier": None, "tracking": None,
              "eta": "2026-06-25", "items": ["Smart Watch"],
              "shipping_address": "200 Elm Ave, Apt 4B, New York, NY"},
    "A1003": {"status": "delivered", "carrier": "JD Logistics", "tracking": "JD9876543210",
              "eta": "2026-06-18", "items": ["USB-C Cable"],
              "shipping_address": "88 Long Rd, Austin, TX"},
}

# Fake refund records keyed by order id. Not every order has a refund.
_REFUNDS: dict[str, dict[str, Any]] = {
    "A1003": {"status": "approved", "amount_usd": 12.99,
              "method": "original_payment", "eta_days": 5,
              "requested_at": "2026-06-19"},
    "A1001": {"status": "rejected", "amount_usd": 0.0,
              "method": None, "eta_days": None,
              "requested_at": "2026-06-18",
              "reason": "Item already shipped and outside the cancel window"},
}

# Fake return policy table
_RETURN_POLICY: dict[str, dict[str, Any]] = {
    "electronics": {"window_days": 15, "condition": "unopened, original packaging",
                    "restocking_fee": 0.0, "exceptions": ["earphones once opened"]},
    "apparel":     {"window_days": 30, "condition": "unworn, tags attached",
                    "restocking_fee": 0.0, "exceptions": ["intimates", "swimwear"]},
    "books":       {"window_days": 7,  "condition": "no markings or damage",
                    "restocking_fee": 0.0, "exceptions": []},
}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def search_faq(query: str) -> dict[str, Any]:
    """Very naive keyword overlap search. Good enough for the demo."""
    q_tokens = {t.lower() for t in query.split() if len(t) > 1}
    scored: list[tuple[int, dict[str, str]]] = []
    for entry in _FAQ:
        hay = (entry["question"] + " " + entry["answer"]).lower()
        score = sum(1 for t in q_tokens if t in hay)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda x: -x[0])
    return {"results": [e for _, e in scored[:3]]}


def lookup_order(order_id: str) -> dict[str, Any]:
    order = _ORDERS.get(order_id.upper().strip())
    if not order:
        return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
    return {"order_id": order_id.upper().strip(), **order}


def check_return_policy(category: str) -> dict[str, Any]:
    key = category.lower().strip()
    policy = _RETURN_POLICY.get(key)
    if not policy:
        return {"error": "CATEGORY_NOT_FOUND",
                "available_categories": list(_RETURN_POLICY.keys())}
    return {"category": key, **policy}


def lookup_refund(order_id: str) -> dict[str, Any]:
    """Refund status for an order.

    Returns NO_REFUND_FOUND if the customer never requested a refund —
    this is a separate state from a rejected refund, and the LLM should
    relay it as 'no refund on record', not invent one.
    """
    oid = order_id.upper().strip()
    if oid not in _ORDERS:
        return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
    refund = _REFUNDS.get(oid)
    if not refund:
        return {"order_id": oid, "status": "NO_REFUND_FOUND"}
    return {"order_id": oid, **refund}


def update_shipping_address(order_id: str, new_address: str) -> dict[str, Any]:
    """Mutate an order's shipping address.

    Policy: only allowed while status == 'processing'. This is a *write* tool
    so the LLM has to handle business-rule rejections gracefully — exactly
    the kind of thing the verifier loop and the LLM-judge grader stress-test.
    """
    oid = order_id.upper().strip()
    order = _ORDERS.get(oid)
    if not order:
        return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
    if order["status"] != "processing":
        return {
            "error": "ADDRESS_LOCKED",
            "reason": f"order status is '{order['status']}', address can only be "
                      f"changed while status is 'processing'",
            "order_id": oid,
        }
    if not new_address or len(new_address.strip()) < 5:
        return {"error": "ADDRESS_INVALID",
                "reason": "address must be at least 5 characters"}
    old = order["shipping_address"]
    order["shipping_address"] = new_address.strip()
    return {
        "order_id": oid,
        "status": "updated",
        "old_address": old,
        "new_address": order["shipping_address"],
    }


def escalate_to_human(reason: str) -> dict[str, Any]:
    return {
        "ticket_id": f"T{int(datetime.now(timezone.utc).timestamp())}",
        "status": "queued",
        "reason": reason,
        "expected_wait_minutes": 5,
    }


# ---------------------------------------------------------------------------
# Registry consumed by the loop
# ---------------------------------------------------------------------------
TOOLS: dict[str, Any] = {
    "search_faq": search_faq,
    "lookup_order": lookup_order,
    "lookup_refund": lookup_refund,
    "update_shipping_address": update_shipping_address,
    "check_return_policy": check_return_policy,
    "escalate_to_human": escalate_to_human,
}

# OpenAI-compatible tool schemas
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_faq",
            "description": "Search the company FAQ knowledge base for help articles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The user's question or keywords"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up an order's status, carrier, and ETA by order id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order id, e.g. A1001"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_return_policy",
            "description": "Get the return policy for a product category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["electronics", "apparel", "books"],
                    }
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_refund",
            "description": (
                "Look up the refund status for an order by id. "
                "Returns status NO_REFUND_FOUND if the customer never requested one — "
                "that is distinct from a rejected refund."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order id, e.g. A1001"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_shipping_address",
            "description": (
                "Change the shipping address of an order. "
                "Only allowed while order status is 'processing'. "
                "Call lookup_order FIRST to confirm the order exists and is still "
                "processing before calling this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id":    {"type": "string", "description": "Order id, e.g. A1002"},
                    "new_address": {"type": "string",
                                    "description": "Full new shipping address"},
                },
                "required": ["order_id", "new_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Hand the conversation over to a human agent. Use ONLY when the "
                "issue is outside policy, the customer explicitly asks for a "
                "human, or you cannot resolve after reasonable attempts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why escalation is needed"}
                },
                "required": ["reason"],
            },
        },
    },
]
