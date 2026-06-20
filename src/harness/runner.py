"""
src/harness/runner.py
=====================
The "Task Runner" + glue of the harness.

Workflow per case:

    1. Load case from cases.jsonl
    2. Build a fresh AgentLoop, run it on case["query"]
    3. Persist the Trajectory to disk (replayable later)
    4. Apply every grader, collect GradeResults
    5. Repeat for all cases, return a CaseReport list

The runner is intentionally synchronous and single-process so the loop is
easy to step through with a debugger. Add asyncio + a worker pool when you
need throughput.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agent.llm import LLMClient
from ..agent.loop import AgentLoop, LoopConfig
from .graders import CodeGrader, GradeResult, LLMJudgeGrader, TrajectoryGrader


@dataclass
class CaseReport:
    case_id: str
    category: str
    query: str
    final_answer: str | None
    grades: list[GradeResult] = field(default_factory=list)
    passed_verification: bool | None = None
    revision_count: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)
    latency_s: float = 0.0

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.grades)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "query": self.query,
            "final_answer": self.final_answer,
            "passed": self.passed,
            "passed_verification": self.passed_verification,
            "revision_count": self.revision_count,
            "token_usage": self.token_usage,
            "latency_s": round(self.latency_s, 2),
            "grades": [g.__dict__ for g in self.grades],
        }


class HarnessRunner:
    def __init__(
        self,
        writer: LLMClient,
        verifier: LLMClient | None,
        judge: LLMClient,
        rubrics: dict[str, str],
        traj_dir: str | os.PathLike = "trajectories",
        loop_config: LoopConfig | None = None,
    ):
        self.writer = writer
        self.verifier = verifier
        self.judge = judge
        self.rubrics = rubrics
        self.traj_dir = Path(traj_dir)
        self.traj_dir.mkdir(parents=True, exist_ok=True)
        self.loop_config = loop_config or LoopConfig()

        # Build the grader suite once
        self.code_grader = CodeGrader()
        self.judge_grader = LLMJudgeGrader(client=judge, rubrics=rubrics)
        self.trajectory_grader = TrajectoryGrader()

    # ------------------------------------------------------------------
    def run_cases(self, cases_path: str | os.PathLike) -> list[CaseReport]:
        reports: list[CaseReport] = []
        for case in self._load_cases(cases_path):
            print(f"  ▶ running {case['id']}  [{case.get('category', '-')}]")
            reports.append(self._run_one(case))
        return reports

    # ------------------------------------------------------------------
    def _run_one(self, case: dict[str, Any]) -> CaseReport:
        loop = AgentLoop(
            writer=self.writer,
            verifier=self.verifier,
            config=self.loop_config,
        )
        traj = loop.run(case["query"])
        traj.case_id = case["id"]

        # Persist trajectory for offline inspection / replay
        (self.traj_dir / f"{case['id']}.json").write_text(
            traj.to_json(), encoding="utf-8"
        )

        # Apply every grader
        grades: list[GradeResult] = [
            self.code_grader.grade(traj, case),
            self.judge_grader.grade(traj, case),
            self.trajectory_grader.grade(traj, case),
        ]

        return CaseReport(
            case_id=case["id"],
            category=case.get("category", "-"),
            query=case["query"],
            final_answer=traj.final_answer,
            grades=grades,
            passed_verification=traj.passed_verification,
            revision_count=traj.revision_count,
            token_usage=traj.token_usage,
            latency_s=traj.latency_s,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _load_cases(path: str | os.PathLike) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                cases.append(json.loads(line))
        return cases
