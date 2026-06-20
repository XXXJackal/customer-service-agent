# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Bilingual README. The default `README.md` is now English; the Chinese
  version moved to `README.zh-CN.md`. Both have language switchers at the top.

## [0.2.0] — 2026-06-20

### Added
- Two new tools: `lookup_refund`, `update_shipping_address`.
- Five new eval cases covering refund happy/rejected/missing paths and address-change allowed/blocked paths (C011–C015).
- `tests/test_tools.py` with 14 direct unit tests on the tool implementations.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`.
- GitHub issue templates (bug + feature) and PR template.
- `.github/dependabot.yml` for weekly dependency updates.
- `.github/workflows/ci.yml` — fast lint + unit-test workflow that runs without an API key.
- Status badges in the README.
- `pyproject.toml` to enable `pip install -e .`.

### Changed
- System prompt teaches the agent to call `lookup_order` before `update_shipping_address`.
- `tools.py` docstring updated with the 3-step "how to add a tool" checklist.

## [0.1.0] — 2026-06-20

### Added
- Initial release.
- Loop Engineering core: ReAct inner loop + verify-and-retry outer loop in `src/agent/loop.py`.
- Harness Engineering core: trajectory store + three grader types + CI gate.
- Four customer-service tools: `search_faq`, `lookup_order`, `check_return_policy`, `escalate_to_human`.
- 10 eval cases (C001–C010).
- Interactive `scripts/chat.py` and harness runner `scripts/eval.py`.
- `.github/workflows/eval.yml` — full eval CI gate.

[Unreleased]: https://github.com/XXXJackal/customer-service-agent/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/XXXJackal/customer-service-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/XXXJackal/customer-service-agent/releases/tag/v0.1.0
