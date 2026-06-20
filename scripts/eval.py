"""
scripts/eval.py
===============
Run the harness against eval/cases.jsonl and produce a markdown report.

Exit code:
  0  if pass rate >= PASS_RATE_THRESHOLD (gate passed)
  1  otherwise (CI-friendly)

Run:
  python scripts/eval.py --out report.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.agent.llm import LLMClient
from src.agent.loop import LoopConfig
from src.harness.metrics import PASS_RATE_THRESHOLD, aggregate, write_markdown_report
from src.harness.runner import HarnessRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="eval/cases.jsonl")
    parser.add_argument("--rubrics", default="eval/rubrics.json")
    parser.add_argument("--out", default="report.md")
    parser.add_argument("--no-verifier", action="store_true",
                        help="Disable the outer (verify-and-retry) loop")
    parser.add_argument("--threshold", type=float, default=PASS_RATE_THRESHOLD,
                        help="CI gate pass-rate threshold")
    args = parser.parse_args()

    with open(args.rubrics, encoding="utf-8") as f:
        rubrics = json.load(f)

    writer = LLMClient(model=os.getenv("AGENT_MODEL", "gpt-4o-mini"))
    verifier = None if args.no_verifier else LLMClient(model=os.getenv("VERIFIER_MODEL", "gpt-4o-mini"))
    judge = LLMClient(model=os.getenv("JUDGE_MODEL", "gpt-4o-mini"))

    runner = HarnessRunner(
        writer=writer,
        verifier=verifier,
        judge=judge,
        rubrics=rubrics,
        loop_config=LoopConfig(
            max_steps=6,
            max_revisions=1,
            verifier_enabled=not args.no_verifier,
        ),
    )

    print(f"running harness on {args.cases} ...")
    reports = runner.run_cases(args.cases)
    agg = aggregate(reports)
    write_markdown_report(reports, agg, args.out)

    print("\n=== Aggregate ===")
    print(f"  pass rate    : {agg.pass_rate:.0%} ({sum(1 for r in reports if r.passed)}/{agg.n})")
    print(f"  total tokens : {agg.total_tokens:,}")
    print(f"  latency p50  : {agg.p50_latency_s:.2f}s")
    print(f"  latency p95  : {agg.p95_latency_s:.2f}s")
    print(f"  revisions    : {agg.revisions_used}")
    for name, rate in agg.per_grader_pass_rate.items():
        print(f"  {name:>12} pass: {rate:.0%}  mean score: {agg.mean_score_per_grader[name]:.2f}")
    print(f"\nreport written -> {args.out}")

    if agg.pass_rate < args.threshold:
        print(f"\n❌ GATE FAILED: pass rate {agg.pass_rate:.0%} < threshold {args.threshold:.0%}")
        return 1
    print(f"\n✅ GATE PASSED: pass rate {agg.pass_rate:.0%} >= threshold {args.threshold:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
