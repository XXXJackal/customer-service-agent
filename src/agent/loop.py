"""
src/agent/loop.py
=================
THE CORE OF LOOP ENGINEERING in this project.

We implement two nested loops:

  ┌──────────────────────────────────────────────────────────┐
  │ OUTER LOOP  (Verify-and-Retry, at most cfg.max_revisions)│
  │ ┌──────────────────────────────────────────────────────┐ │
  │ │ INNER LOOP (ReAct, at most cfg.max_steps)            │ │
  │ │   LLM reasons → emits tool calls → tools execute     │ │
  │ │   → observations fed back → LLM reasons again ...    │ │
  │ │   stops when the LLM emits a final answer            │ │
  │ └──────────────────────────────────────────────────────┘ │
  │ Verifier scores the final answer.                        │
  │ - PASS   → return                                        │
  │ - REVISE → push feedback into messages, run inner loop   │
  │            once more                                     │
  └──────────────────────────────────────────────────────────┘

Why two loops?
- The INNER loop is the classic ReAct pattern (Reason + Act). It makes the
  agent capable of multi-step tool use.
- The OUTER loop is the "Writer/Reviewer split" pattern that Loop Engineering
  popularized: a separate (often cheaper) model audits the writer's output
  and pushes back. This is what makes a loop *self-correcting*.

Everything that happens inside is recorded into a Trajectory. The Harness
module replays/grades these trajectories.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..harness.trajectory import Step, Trajectory
from .llm import LLMClient
from .prompts import AGENT_SYSTEM_PROMPT, VERIFIER_SYSTEM_PROMPT
from .tools import TOOL_SPECS, TOOLS


# ---------------------------------------------------------------------------
# Config — every "budget" the loop has to respect
# ---------------------------------------------------------------------------
@dataclass
class LoopConfig:
    max_steps: int = 6            # inner loop budget
    max_revisions: int = 1        # outer loop budget (0 = no verifier)
    temperature: float = 0.2
    verifier_enabled: bool = True


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------
class AgentLoop:
    """A self-contained ReAct + Verifier loop. No framework, no magic."""

    def __init__(
        self,
        writer: LLMClient,
        verifier: LLMClient | None = None,
        config: LoopConfig | None = None,
        tool_specs: list[dict[str, Any]] | None = None,
        tools: dict[str, Callable[..., Any]] | None = None,
    ):
        self.writer = writer
        self.verifier = verifier
        self.cfg = config or LoopConfig()
        self.tool_specs = tool_specs if tool_specs is not None else TOOL_SPECS
        self.tools = tools if tools is not None else TOOLS

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self, user_query: str) -> Trajectory:
        traj = Trajectory(query=user_query)
        traj.mark_start()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
        ]

        # === OUTER LOOP: verify-and-retry ===
        for revision in range(self.cfg.max_revisions + 1):
            # --- INNER LOOP: ReAct ---
            final_answer = self._inner_react_loop(messages, traj)

            # If verifier is off or budget exhausted, return immediately.
            if not self.cfg.verifier_enabled or self.verifier is None:
                traj.final_answer = final_answer
                break

            verdict = self._verify(user_query, traj, final_answer)
            traj.add(Step(kind="verify", data=verdict))

            if verdict.get("verdict") == "pass" or revision == self.cfg.max_revisions:
                traj.final_answer = final_answer
                traj.passed_verification = (verdict.get("verdict") == "pass")
                break

            # Push reviewer feedback into the conversation and let the inner
            # loop run again. This is the "self-correction" pattern.
            messages.append({"role": "assistant", "content": final_answer})
            messages.append({
                "role": "user",
                "content": f"[reviewer feedback] {verdict.get('feedback', '')}. "
                           f"Please revise your previous reply accordingly.",
            })
            traj.revision_count += 1

        traj.mark_end()
        return traj

    # ------------------------------------------------------------------
    # Inner ReAct loop
    # ------------------------------------------------------------------
    def _inner_react_loop(
        self, messages: list[dict[str, Any]], traj: Trajectory
    ) -> str:
        """
        Run the classic Reason-Act loop until the LLM emits a final answer or
        until cfg.max_steps is reached. Returns the final assistant content.
        """
        for step_idx in range(self.cfg.max_steps):
            resp = self.writer.chat(
                messages=messages,
                tools=self.tool_specs,
                temperature=self.cfg.temperature,
            )
            traj.add(Step(kind="llm", data={
                "step": step_idx,
                "content": resp.content,
                "tool_calls": resp.tool_calls,
                "usage": resp.usage,
            }))
            traj.token_usage["prompt"] += resp.usage["prompt_tokens"]
            traj.token_usage["completion"] += resp.usage["completion_tokens"]

            # Case A: no tool calls → this is the final answer
            if not resp.tool_calls:
                return resp.content or ""

            # Case B: tool calls present → execute and feed observations back.
            # We must append the assistant message exactly as OpenAI expects.
            messages.append({
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in resp.tool_calls
                ],
            })

            for tc in resp.tool_calls:
                tool_name = tc["name"]
                try:
                    args = json.loads(tc["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self._execute_tool(tool_name, args)
                traj.add(Step(kind="tool", data={
                    "name": tool_name, "args": args, "result": result,
                }))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

        # Step budget exhausted without a final answer.
        traj.add(Step(kind="budget_exhausted", data={"max_steps": self.cfg.max_steps}))
        return ("I'm having trouble completing this request right now. "
                "Let me hand this over to a human teammate.")

    # ------------------------------------------------------------------
    # Tool execution with defensive error handling
    # ------------------------------------------------------------------
    def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        fn = self.tools.get(name)
        if fn is None:
            return {"error": "UNKNOWN_TOOL", "name": name}
        try:
            return fn(**args)
        except TypeError as e:
            return {"error": "BAD_ARGUMENTS", "detail": str(e)}
        except Exception as e:  # noqa: BLE001
            return {"error": "TOOL_RUNTIME_ERROR", "detail": str(e)}

    # ------------------------------------------------------------------
    # Verifier (Outer loop)
    # ------------------------------------------------------------------
    def _verify(
        self, user_query: str, traj: Trajectory, final_answer: str
    ) -> dict[str, Any]:
        """Ask the verifier model to PASS or REVISE."""
        # Summarize the tool trace for the reviewer
        tool_steps = [s for s in traj.steps if s.kind == "tool"]
        trace_summary = "\n".join(
            f"- {s.data['name']}({json.dumps(s.data['args'], ensure_ascii=False)}) "
            f"-> {json.dumps(s.data['result'], ensure_ascii=False)[:300]}"
            for s in tool_steps
        ) or "(no tools were called)"

        review_prompt = (
            f"CUSTOMER QUESTION:\n{user_query}\n\n"
            f"TOOL CALL TRACE:\n{trace_summary}\n\n"
            f"AGENT FINAL REPLY:\n{final_answer}\n"
        )

        resp = self.verifier.chat(
            messages=[
                {"role": "system", "content": VERIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": review_prompt},
            ],
            temperature=0.0,
        )
        traj.token_usage["prompt"] += resp.usage["prompt_tokens"]
        traj.token_usage["completion"] += resp.usage["completion_tokens"]

        content = (resp.content or "").strip()
        # The verifier sometimes wraps JSON in ```...```. Be forgiving.
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {"verdict": "pass", "feedback": "(verifier returned non-JSON)"}

        # Normalize
        verdict = (data.get("verdict") or "pass").lower()
        if verdict not in ("pass", "revise"):
            verdict = "pass"
        return {"verdict": verdict, "feedback": data.get("feedback", "")}
