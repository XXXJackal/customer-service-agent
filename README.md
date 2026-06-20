# Customer Service Agent · Minimal

[简体中文](README.zh-CN.md) | **English**

[![CI](https://github.com/XXXJackal/customer-service-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/XXXJackal/customer-service-agent/actions/workflows/ci.yml)
[![Eval Gate](https://github.com/XXXJackal/customer-service-agent/actions/workflows/eval.yml/badge.svg)](https://github.com/XXXJackal/customer-service-agent/actions/workflows/eval.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

> A production-style customer service agent skeleton for learning **Loop Engineering** and **Harness Engineering** — the two patterns that are reshaping how serious LLM agents are built and evaluated in 2026.
> Every core module is hand-written. No LangChain / LangGraph / DSPy. You can read and understand every file.

> ⚠️ Before pushing to GitHub: replace every `XXXJackal` in this README, in `pyproject.toml`,
> in `CHANGELOG.md`, and in `.github/ISSUE_TEMPLATE/config.yml` with your GitHub username.

---

## 1. Why these two patterns

| Pattern | One-line definition | What it solves |
|---|---|---|
| **Loop Engineering** | Stop prompting single-step tasks — *design* a loop that iterates toward a goal | The "process" — how the agent thinks, calls tools, and knows when to stop |
| **Harness Engineering** | Treat evaluation as production **infrastructure**: trajectory store + multi-grader suite + CI gate | The "quality" — how you know the agent hasn't regressed before shipping |

This project splits those two things into the two thinnest possible directories: `src/agent/` is the loop, `src/harness/` is the eval harness. Open any single file and you can read it top to bottom.

---

## 2. Project layout

```
customer-service-agent/
├── src/
│   ├── agent/            # === Loop Engineering core ===
│   │   ├── loop.py       # Inner loop (ReAct) + outer loop (Verify-and-Retry)
│   │   ├── tools.py      # 6 tools: FAQ / order / refund / address / return policy / escalation
│   │   ├── prompts.py    # System prompts
│   │   └── llm.py        # Ultra-thin LLM client wrapper
│   ├── harness/          # === Harness Engineering core ===
│   │   ├── runner.py     # Runs the agent across every test case
│   │   ├── graders.py    # Three grader types: Code / LLM-Judge / Trajectory
│   │   ├── trajectory.py # Replayable trajectory data model
│   │   └── metrics.py    # Aggregation + Pass/Fail decision
│   └── knowledge/faq.json
├── eval/
│   ├── cases.jsonl       # Test cases (15 cases, 13 categories)
│   └── rubrics.json      # Rubric definitions for the LLM judge
├── scripts/
│   ├── chat.py           # Interactive chat — watch the loop run
│   └── eval.py           # Run the harness, produce a report
├── tests/
│   ├── test_loop.py      # Loop unit tests (fake LLM, no API key needed)
│   └── test_tools.py     # Direct tool unit tests
└── .github/workflows/
    ├── ci.yml            # Every push: lint + unit tests
    └── eval.yml          # PR gate: full eval harness
```

---

## 3. What Loop Engineering looks like here

`src/agent/loop.py` implements two nested loops:

```
┌─────────────────────────────────────────────────────────┐
│  Outer Loop (Verify-and-Retry, up to N revisions)       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Inner Loop (ReAct, up to K steps)                │  │
│  │    LLM reasons → picks tool → executes → observes │  │
│  │    → reasons again ...                            │  │
│  │    stops when the LLM emits a final answer        │  │
│  └───────────────────────────────────────────────────┘  │
│  Verifier scores it → if "revise", inject feedback into │
│  messages and run the inner loop one more time          │
└─────────────────────────────────────────────────────────┘
```

Key design points (all documented inline in `loop.py`):

1. **Step budget** — the inner loop runs at most `max_steps` steps, preventing infinite tool calls
2. **Goal condition** — the outer loop uses a lightweight verifier to judge "is the answer good enough?"
3. **Writer/Reviewer split** — the verifier uses a cheaper model. This is the mainstream Loop Engineering practice
4. **Full trajectory** — every LLM call, tool call, observation, and grade is recorded, replayable, and gradeable

---

## 4. What Harness Engineering looks like here

`src/harness/` implements an Anthropic-style evaluation harness. The four core components:

| Component | File | Role |
|---|---|---|
| **Task Runner** | `runner.py` | Runs the agent across every case in `cases.jsonl` |
| **Trajectory Store** | `trajectory.py` | Serializes every run to disk for offline replay |
| **Grader Suite** | `graders.py` | Three grader types:<br>· `CodeGrader` — deterministic checks (right tool? right arguments?)<br>· `LLMJudgeGrader` — semantic quality against a rubric<br>· `TrajectoryGrader` — process metrics (steps, tokens, latency) |
| **Aggregator** | `metrics.py` | Pass-rate computation, deployment decision, CI gate |
| **CI Gate** | `.github/workflows/eval.yml` | PRs must clear the threshold to merge |

---

## 5. Quick start

```bash
# 1. Install
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY (or any compatible provider's key)

# 2. Chat with the agent (watch the loop run)
python scripts/chat.py

# 3. Run the eval harness (produces a markdown report)
python scripts/eval.py --out report.md
```

The `OPENAI_BASE_URL` in `.env` can point at any OpenAI-compatible endpoint (DeepSeek / Qwen / Moonshot / local vLLM / etc.) — the code itself doesn't need to change.

---

## 6. The 3 files most worth reading

If you only have time for three:

1. `src/agent/loop.py` — see how "inner loop + outer loop" is written
2. `src/harness/graders.py` — see how the three grader types are written
3. `src/harness/runner.py` — see how the harness glues the two together

---

## 7. Next steps (exercises)

- [ ] Swap the verifier for a smaller (7B-class) model and measure the cost/quality trade-off
- [ ] Add schema validation to `CodeGrader`
- [ ] Wire OpenTelemetry so trajectories stream to Langfuse / Phoenix
- [ ] Add a `human` grader that routes uncertain samples to a labeller
- [ ] Tighten the pass-rate threshold in `eval.yml` and enforce it on PRs

---

## 8. Publishing to GitHub

```bash
# 1. Replace XXXJackal placeholders with your GitHub username
#    Linux:
sed -i 's|XXXJackal|your-github-username|g' README.md README.zh-CN.md pyproject.toml CHANGELOG.md .github/ISSUE_TEMPLATE/config.yml
#    macOS:
sed -i '' 's|XXXJackal|your-github-username|g' README.md README.zh-CN.md pyproject.toml CHANGELOG.md .github/ISSUE_TEMPLATE/config.yml

# 2. Replace your.email@example.com in SECURITY.md with a real address

# 3. Initialize and push
git init
git add .
git commit -m "init: minimal customer-service agent for loop + harness engineering"
gh repo create customer-service-agent --public --source=. --push
```

After pushing, go to `Settings → Secrets and variables → Actions` on the repo and add:

| Secret | Required? | Notes |
|---|---|---|
| `OPENAI_API_KEY` | yes | Used by the eval harness |
| `OPENAI_BASE_URL` | no | Set when using DeepSeek / Qwen / Moonshot / local vLLM |
| `AGENT_MODEL` / `VERIFIER_MODEL` / `JUDGE_MODEL` | no | Default is `gpt-4o-mini` |

Then visit `Insights → Community Standards` — every item should already be checked: README, LICENSE, Code of Conduct, Contributing, Security policy, Issue templates, Pull request template.

---

## License

MIT
