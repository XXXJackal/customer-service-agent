# Contributing

Thanks for your interest. This project is meant to stay **minimal and educational**, so PRs are evaluated through that lens first.

## Ground rules

1. **No new heavyweight dependencies.** The point of the project is to expose the loop and the harness; framework imports defeat that. If your change needs a new top-level dependency, open an issue first.
2. **Every new tool ships with at least one eval case.** If you add a tool to `src/agent/tools.py`, add a matching entry to `eval/cases.jsonl` so the CI gate exercises it.
3. **Code grader expectations are required where deterministic.** Use `expected_tools`, `expected_tool_args`, `forbidden_tools`, `must_contain`, or `must_not_contain` whenever the right answer is mechanically checkable.
4. **The CI gate must stay green.** PRs that drop pass rate below the threshold in `.github/workflows/eval.yml` will not be merged without justification.

## Local workflow

```bash
git clone <your fork>
cd customer-service-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY
pytest -q                                    # fast unit tests
python scripts/eval.py --out report.md       # full harness, costs tokens
```

## Adding a tool — checklist

- [ ] Function in `src/agent/tools.py` returning structured errors (never raises)
- [ ] JSON schema in `TOOL_SPECS` with a precise `description`
- [ ] Registered in the `TOOLS` dict
- [ ] System prompt in `src/agent/prompts.py` updated with when to use it
- [ ] At least one happy-path case in `eval/cases.jsonl` with `expected_tools`
- [ ] At least one error-path case (e.g. business-rule rejection)
- [ ] Unit test in `tests/test_tools.py`

## Adding a grader

If you invent a new grader, add it under `src/harness/graders.py`, register it in `HarnessRunner.__init__`, and aggregate it in `metrics.py`. Open an issue first so we can discuss whether it belongs in core or as an example.

## Style

- Python 3.10+, type hints encouraged.
- Comments explain **why**, not what. The point of this codebase is to be readable.
- Keep files short. If one file passes ~250 lines, consider splitting.
