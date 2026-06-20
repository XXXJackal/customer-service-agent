# Security Policy

## Reporting a Vulnerability

If you discover a security issue in this project, please **do not open a public issue**. Instead, report it privately so it can be fixed before being disclosed.

**How to report:**

1. Use GitHub's private vulnerability reporting:
   `Security` tab → `Report a vulnerability` on this repository, OR
2. Email the maintainer: `libanbao@gmail.com`

Please include:

- A description of the issue and its potential impact
- Steps to reproduce
- Any suggested mitigation, if you have one

You can expect an acknowledgement within 5 business days. We aim to publish a fix or mitigation within 30 days for high-severity issues.

## Scope

This project is an educational reference implementation for Loop Engineering and Harness Engineering patterns. It is **not** intended to be deployed unmodified in production. Specifically, the following are out of scope:

- The fake order/refund tables in `src/agent/tools.py` are demo data, not a real datastore. Their authorization checks are deliberately minimal.
- The verifier loop is not a security boundary. A determined prompt injection in the user query can influence both writer and verifier. Production deployments need additional input sanitization and output filtering.
- The CI eval gate depends on the API key set via repository secrets. Rotate it if exposed.

## Things that ARE in scope

- Bugs in the loop that allow tools to be invoked with unsanitized arguments leading to RCE on the host (none expected; all tools operate on in-memory dicts).
- Bugs in the harness that cause the CI gate to falsely report PASS when cases failed.
- Bugs that cause API keys or other secrets in `.env` to leak into trajectory files or reports.

## Dependency security

We rely on Dependabot (configured in `.github/dependabot.yml`) for upstream security advisories on `openai`, `python-dotenv`, and `pydantic`.
