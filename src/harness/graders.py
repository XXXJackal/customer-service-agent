"""
src/harness/graders.py
======================
THE HEART OF HARNESS ENGINEERING in this project.

Anthropic's harness pattern names three grader types — we implement all three:

  1. CodeGrader        deterministic checks (fast, free, exact)
                       e.g. "did the agent call lookup_order with the right id?"

  2. LLMJudgeGrader    model-based semantic checks (flexible, has variance)
                       e.g. "is the tone polite? is the answer faithful?"

  3. TrajectoryGrader  process metrics (efficient runs vs. wasteful runs)
                       e.g. "did the agent stay under the step/token budget?"

Each grader returns a GradeResult with a numeric score in [0, 1] and a
pass/fail boolean. The runner then aggregates across all cases and graders.

Reading order: GradeResult → CodeGrader → LLMJudgeGrader → TrajectoryGrader.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..agent.llm import LLMClient
from .trajectory import Trajectory


# ---------------------------------------------------------------------------
# Common result type
# ---------------------------------------------------------------------------
@dataclass
class GradeResult:
    grader: str
    score: float                                  # in [0, 1]
    passed: bool
    detail: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1) CodeGrader — DETERMINISTIC
# ---------------------------------------------------------------------------
class CodeGrader:
    """
    Reads the test case's expectations and checks them against the trajectory.
    Supported checks (any subset can appear in a case):

      expected_tools         list[str]   tool names that MUST appear (in any order)
      forbidden_tools        list[str]   tool names that MUST NOT appear
      must_contain           list[str]   substrings that MUST be in the final answer
      must_not_contain       list[str]   substrings that MUST NOT be in the final answer
      expected_tool_args     dict[str, dict]  per-tool subset of args that must match
                                              e.g. {"lookup_order": {"order_id": "A1001"}}
    """

    name = "code"

    def grade(self, trajectory: Trajectory, case: dict[str, Any]) -> GradeResult:
        checks: list[tuple[str, bool]] = []
        detail: dict[str, Any] = {}

        called = trajectory.tool_names
        final = (trajectory.final_answer or "").lower()

        # expected_tools
        for t in case.get("expected_tools", []):
            ok = t in called
            checks.append((f"expected_tools::{t}", ok))
        # forbidden_tools
        for t in case.get("forbidden_tools", []):
            ok = t not in called
            checks.append((f"forbidden_tools::{t}", ok))
        # must_contain
        for s in case.get("must_contain", []):
            ok = s.lower() in final
            checks.append((f"must_contain::{s}", ok))
        # must_not_contain
        for s in case.get("must_not_contain", []):
            ok = s.lower() not in final
            checks.append((f"must_not_contain::{s}", ok))
        # expected_tool_args
        for tool_name, expected_args in case.get("expected_tool_args", {}).items():
            matched = False
            for call in trajectory.tool_calls:
                if call["name"] != tool_name:
                    continue
                actual = call.get("args", {})
                # subset match — every expected key/value must appear in actual
                if all(str(actual.get(k, "")).lower() == str(v).lower()
                       for k, v in expected_args.items()):
                    matched = True
                    break
            checks.append((f"expected_tool_args::{tool_name}", matched))

        detail["checks"] = checks
        if not checks:
            # No deterministic expectations in this case → vacuously pass.
            return GradeResult(grader=self.name, score=1.0, passed=True,
                               detail={"note": "no_checks_defined"})

        passed = sum(1 for _, ok in checks if ok)
        score = passed / len(checks)
        return GradeResult(grader=self.name, score=score, passed=(score == 1.0), detail=detail)


# ---------------------------------------------------------------------------
# 2) LLMJudgeGrader — MODEL-BASED
# ---------------------------------------------------------------------------
_JUDGE_SYSTEM = """You are a strict evaluator of customer service replies.

You will be given a rubric (a list of criteria, each scored 0–2):
  0 = fails the criterion
  1 = partially meets it
  2 = fully meets it

Reply ONLY with JSON of the shape:
{
  "scores":   {"<criterion>": <0|1|2>, ...},
  "comments": {"<criterion>": "<short reason>", ...}
}
"""


class LLMJudgeGrader:
    """
    Asks an LLM (the 'judge') to score the agent's reply against a rubric
    written in the test case.

    Rubric format inside a case:
        "rubric": ["faithful", "polite", "concise"]

    The criterion strings are taken straight from eval/rubrics.json so you can
    edit them without touching code.
    """
    name = "llm_judge"

    def __init__(self, client: LLMClient, rubrics: dict[str, str], pass_threshold: float = 0.75):
        self.client = client
        self.rubrics = rubrics            # criterion -> description
        self.pass_threshold = pass_threshold

    def grade(self, trajectory: Trajectory, case: dict[str, Any]) -> GradeResult:
        criteria = case.get("rubric") or list(self.rubrics.keys())
        rubric_block = "\n".join(
            f"- {c}: {self.rubrics.get(c, c)}" for c in criteria
        )

        prompt = (
            f"RUBRIC:\n{rubric_block}\n\n"
            f"CUSTOMER QUESTION:\n{trajectory.query}\n\n"
            f"TOOL CALLS:\n{json.dumps(trajectory.tool_calls, ensure_ascii=False)[:1500]}\n\n"
            f"AGENT REPLY:\n{trajectory.final_answer}\n"
        )
        resp = self.client.chat(
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        content = (resp.content or "").strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        try:
            data = json.loads(content)
            scores = data.get("scores", {})
            comments = data.get("comments", {})
        except json.JSONDecodeError:
            return GradeResult(grader=self.name, score=0.0, passed=False,
                               detail={"error": "judge_returned_non_json",
                                       "raw": content[:400]})

        if not scores:
            return GradeResult(grader=self.name, score=0.0, passed=False,
                               detail={"error": "no_scores"})

        normalized = sum(min(2, max(0, int(v))) for v in scores.values()) / (2 * len(scores))
        return GradeResult(
            grader=self.name,
            score=normalized,
            passed=normalized >= self.pass_threshold,
            detail={"scores": scores, "comments": comments},
        )


# ---------------------------------------------------------------------------
# 3) TrajectoryGrader — PROCESS METRICS
# ---------------------------------------------------------------------------
class TrajectoryGrader:
    """
    Looks at HOW the agent ran, not just what it produced.

    Checks (all optional, configured in the case OR globally):
      max_steps      — penalize runs that used too many ReAct steps
      max_tokens     — penalize runs that burned too many tokens
      max_latency_s  — penalize slow runs
    """
    name = "trajectory"

    def __init__(self,
                 max_steps: int = 6,
                 max_tokens: int = 4000,
                 max_latency_s: float = 30.0):
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.max_latency_s = max_latency_s

    def grade(self, trajectory: Trajectory, case: dict[str, Any]) -> GradeResult:
        budgets = case.get("budgets", {})
        max_steps = budgets.get("max_steps", self.max_steps)
        max_tokens = budgets.get("max_tokens", self.max_tokens)
        max_latency_s = budgets.get("max_latency_s", self.max_latency_s)

        used_tokens = trajectory.token_usage["prompt"] + trajectory.token_usage["completion"]
        used_steps = trajectory.step_count
        used_latency = trajectory.latency_s

        # Each dimension contributes a 0-or-1; total averaged
        checks = {
            "steps":   used_steps   <= max_steps,
            "tokens":  used_tokens  <= max_tokens,
            "latency": used_latency <= max_latency_s,
        }
        passed = all(checks.values())
        score = sum(checks.values()) / len(checks)

        return GradeResult(
            grader=self.name,
            score=score,
            passed=passed,
            detail={
                "used":    {"steps": used_steps, "tokens": used_tokens,
                            "latency_s": round(used_latency, 2)},
                "budgets": {"steps": max_steps, "tokens": max_tokens,
                            "latency_s": max_latency_s},
                "checks":  checks,
            },
        )
