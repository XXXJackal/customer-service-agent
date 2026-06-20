"""
src/harness/metrics.py
======================
Aggregator + report writer + the CI Gate decision.

The CI Gate (used by .github/workflows/eval.yml) is just:

    overall pass rate >= PASS_RATE_THRESHOLD

If that holds, the workflow exits 0. Otherwise it exits non-zero and blocks
the PR. This is the "evaluation gate" pattern from Anthropic's harness
engineering literature in its simplest form.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path

from .runner import CaseReport

PASS_RATE_THRESHOLD = 0.80   # the CI gate


@dataclass
class Aggregate:
    n: int
    pass_rate: float
    per_grader_pass_rate: dict[str, float]
    mean_score_per_grader: dict[str, float]
    total_tokens: int
    p50_latency_s: float
    p95_latency_s: float
    revisions_used: int

    def gate_passed(self, threshold: float = PASS_RATE_THRESHOLD) -> bool:
        return self.pass_rate >= threshold


def aggregate(reports: list[CaseReport]) -> Aggregate:
    n = len(reports)
    if n == 0:
        return Aggregate(0, 0.0, {}, {}, 0, 0.0, 0.0, 0)

    pass_rate = sum(1 for r in reports if r.passed) / n

    grader_names = {g.grader for r in reports for g in r.grades}
    per_pass: dict[str, float] = {}
    per_score: dict[str, float] = {}
    for name in grader_names:
        relevant = [g for r in reports for g in r.grades if g.grader == name]
        per_pass[name] = sum(1 for g in relevant if g.passed) / len(relevant)
        per_score[name] = sum(g.score for g in relevant) / len(relevant)

    total_tokens = sum(
        r.token_usage.get("prompt", 0) + r.token_usage.get("completion", 0)
        for r in reports
    )
    latencies = sorted(r.latency_s for r in reports)
    p50 = statistics.median(latencies) if latencies else 0.0
    p95_idx = max(0, int(round(0.95 * (len(latencies) - 1))))
    p95 = latencies[p95_idx] if latencies else 0.0
    revisions = sum(r.revision_count for r in reports)

    return Aggregate(
        n=n,
        pass_rate=pass_rate,
        per_grader_pass_rate=per_pass,
        mean_score_per_grader=per_score,
        total_tokens=total_tokens,
        p50_latency_s=p50,
        p95_latency_s=p95,
        revisions_used=revisions,
    )


def write_markdown_report(
    reports: list[CaseReport], agg: Aggregate, out_path: str | Path
) -> None:
    lines: list[str] = []
    lines.append("# Customer Service Agent — Eval Report\n")
    lines.append(
        f"**Pass rate:** {agg.pass_rate:.0%} ({sum(1 for r in reports if r.passed)}/{agg.n})  ·  "
        f"**Gate:** {'✅ PASS' if agg.gate_passed() else '❌ FAIL'} "
        f"(threshold = {PASS_RATE_THRESHOLD:.0%})\n"
    )

    lines.append("## Aggregate metrics\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Cases | {agg.n} |")
    lines.append(f"| Overall pass rate | {agg.pass_rate:.0%} |")
    lines.append(f"| Total tokens | {agg.total_tokens:,} |")
    lines.append(f"| Latency p50 / p95 | {agg.p50_latency_s:.2f}s / {agg.p95_latency_s:.2f}s |")
    lines.append(f"| Outer-loop revisions used | {agg.revisions_used} |\n")

    lines.append("## Per-grader breakdown\n")
    lines.append("| Grader | Pass rate | Mean score |")
    lines.append("|---|---|---|")
    for name in sorted(agg.per_grader_pass_rate):
        lines.append(
            f"| {name} | {agg.per_grader_pass_rate[name]:.0%} | "
            f"{agg.mean_score_per_grader[name]:.2f} |"
        )
    lines.append("")

    lines.append("## Per-case detail\n")
    lines.append("| ID | Category | Pass | Code | Judge | Trajectory | Revisions |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in reports:
        by_name = {g.grader: g for g in r.grades}
        cells = []
        for grader_name in ("code", "llm_judge", "trajectory"):
            g = by_name.get(grader_name)
            if not g:
                cells.append("-")
            else:
                mark = "✅" if g.passed else "❌"
                cells.append(f"{mark} {g.score:.2f}")
        lines.append(
            f"| {r.case_id} | {r.category} | "
            f"{'✅' if r.passed else '❌'} | "
            f"{cells[0]} | {cells[1]} | {cells[2]} | "
            f"{r.revision_count} |"
        )

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
