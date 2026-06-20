"""
scripts/chat.py
===============
Interactive REPL — watch the loop run step by step.

Run:  python scripts/chat.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.agent.llm import LLMClient
from src.agent.loop import AgentLoop, LoopConfig


def main() -> None:
    writer = LLMClient(model=os.getenv("AGENT_MODEL", "gpt-4o-mini"))
    verifier = LLMClient(model=os.getenv("VERIFIER_MODEL", "gpt-4o-mini"))
    loop = AgentLoop(
        writer=writer,
        verifier=verifier,
        config=LoopConfig(max_steps=6, max_revisions=1, verifier_enabled=True),
    )

    print("Customer Service Agent (Loop Engineering demo)")
    print("Type 'exit' to quit, 'trace' after a reply to see the full trajectory.\n")

    last_traj = None
    while True:
        try:
            query = input("you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            break
        if query.lower() == "trace" and last_traj:
            print(json.dumps(last_traj.to_dict(), ensure_ascii=False, indent=2, default=str))
            continue

        traj = loop.run(query)
        last_traj = traj
        print(f"\nagent ▸ {traj.final_answer}\n")
        print(
            f"   [tools used: {traj.tool_names}  "
            f"steps: {traj.step_count}  "
            f"revisions: {traj.revision_count}  "
            f"tokens: {sum(traj.token_usage.values())}]\n"
        )


if __name__ == "__main__":
    main()
