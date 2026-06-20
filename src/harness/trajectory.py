"""
src/harness/trajectory.py
=========================
The "Trajectory Store" piece of the harness.

Why dataclasses and not Pydantic? Because dataclasses serialize cleanly to
JSON with a one-line helper, and we want zero magic in the data model so you
can read it line by line.

A Trajectory is the complete, replayable record of ONE agent run:
  - the user query
  - every LLM call (content, tool_calls, usage)
  - every tool call (name, args, result)
  - every verifier verdict
  - timing + token counters
  - final answer

You can later replay these for offline grading, regression testing, or
training data collection.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

StepKind = Literal["llm", "tool", "verify", "budget_exhausted"]


@dataclass
class Step:
    kind: StepKind
    data: dict[str, Any]
    ts: float = field(default_factory=time.time)


@dataclass
class Trajectory:
    query: str
    steps: list[Step] = field(default_factory=list)
    final_answer: str | None = None
    passed_verification: bool | None = None
    revision_count: int = 0
    token_usage: dict[str, int] = field(default_factory=lambda: {"prompt": 0, "completion": 0})
    started_at: float | None = None
    ended_at: float | None = None
    case_id: str | None = None        # set by the harness runner

    # --------------------------------------------------------------
    def add(self, step: Step) -> None:
        self.steps.append(step)

    def mark_start(self) -> None:
        self.started_at = time.time()

    def mark_end(self) -> None:
        self.ended_at = time.time()

    # --------------------------------------------------------------
    # Derived views — used heavily by graders
    # --------------------------------------------------------------
    @property
    def latency_s(self) -> float:
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return 0.0

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return [s.data for s in self.steps if s.kind == "tool"]

    @property
    def tool_names(self) -> list[str]:
        return [s.data["name"] for s in self.steps if s.kind == "tool"]

    @property
    def step_count(self) -> int:
        return sum(1 for s in self.steps if s.kind in ("llm", "tool"))

    # --------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
