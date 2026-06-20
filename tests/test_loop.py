"""
tests/test_loop.py
==================
Unit tests for the loop using a fake LLM client — no API key required.

These tests exercise:
  - The INNER loop (ReAct) with multi-step tool use
  - The OUTER loop (verifier revising a bad answer)
  - The step budget guard
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from src.agent.loop import AgentLoop, LoopConfig


@dataclass
class FakeResp:
    content: str | None
    tool_calls: list[dict]
    raw: object = None
    usage: dict = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = {"prompt_tokens": 10, "completion_tokens": 5}


class FakeWriter:
    """Scripted writer — pops one response per call."""
    def __init__(self, scripted: list[FakeResp]):
        self._script = list(scripted)

    def chat(self, messages, tools=None, temperature=0.2):
        return self._script.pop(0)


class FakeVerifier:
    def __init__(self, verdicts: list[str]):
        self._v = list(verdicts)

    def chat(self, messages, tools=None, temperature=0.2):
        verdict = self._v.pop(0)
        body = json.dumps({"verdict": verdict, "feedback": "needs more detail"})
        return FakeResp(content=body, tool_calls=[])


# ---------------------------------------------------------------------------
def test_react_inner_loop_single_tool_then_answer():
    writer = FakeWriter([
        FakeResp(content=None, tool_calls=[
            {"id": "1", "name": "lookup_order",
             "arguments": json.dumps({"order_id": "A1001"})}
        ]),
        FakeResp(content="Your order A1001 has shipped via SF Express.", tool_calls=[]),
    ])
    loop = AgentLoop(writer=writer, verifier=None,
                     config=LoopConfig(max_steps=4, verifier_enabled=False))
    traj = loop.run("Where is order A1001?")
    assert "A1001" in (traj.final_answer or "")
    assert traj.tool_names == ["lookup_order"]


def test_outer_loop_revises_on_fail_then_passes():
    writer = FakeWriter([
        FakeResp(content="i dunno lol", tool_calls=[]),                  # bad reply
        FakeResp(content="Sorry — please share your order id.", tool_calls=[]),  # revised reply
    ])
    verifier = FakeVerifier(["revise", "pass"])
    loop = AgentLoop(writer=writer, verifier=verifier,
                     config=LoopConfig(max_steps=3, max_revisions=1,
                                       verifier_enabled=True))
    traj = loop.run("Where is my order?")
    assert traj.revision_count == 1
    assert traj.passed_verification is True
    assert "order id" in (traj.final_answer or "").lower()


def test_step_budget_is_respected():
    # Writer keeps requesting tools forever — should hit the budget.
    looper = FakeWriter([
        FakeResp(content=None, tool_calls=[
            {"id": str(i), "name": "search_faq",
             "arguments": json.dumps({"query": "x"})}
        ])
        for i in range(10)
    ])
    loop = AgentLoop(writer=looper, verifier=None,
                     config=LoopConfig(max_steps=3, verifier_enabled=False))
    traj = loop.run("anything")
    # final_answer is the budget-exhausted fallback
    assert "human" in (traj.final_answer or "").lower()
    assert traj.step_count <= 6   # 3 llm + 3 tool
