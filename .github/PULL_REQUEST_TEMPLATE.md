# What this PR does

<!-- One or two sentences. Link the issue this closes if any. -->

Closes #

## Type of change

- [ ] New tool
- [ ] New grader
- [ ] Loop behavior change
- [ ] Eval dataset change
- [ ] Bug fix
- [ ] Docs only
- [ ] Other

## Checklist

- [ ] `pytest -q` passes locally
- [ ] If a new tool was added, at least one eval case with `expected_tools` was added too
- [ ] If a new grader was added, it's wired into `HarnessRunner` and `metrics.aggregate`
- [ ] `python scripts/eval.py` was run locally and the pass rate is still ≥ the gate threshold
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`
- [ ] No new top-level dependencies (or they're justified in the PR description)

## Eval report excerpt

<!--
Paste the "Aggregate metrics" section from your local eval report.
If pass rate dropped, explain why the change is still worth merging.
-->

```
pass rate    : __%
total tokens : __
latency p50  : __s
```

## Anything reviewers should focus on

<!-- Tricky decisions, alternatives you tried and rejected, etc. -->
