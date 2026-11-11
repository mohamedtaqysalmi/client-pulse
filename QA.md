# QA notes (v0.1.0)

Manual and automated checks before tagging. Automated results live in [TEST_REPORT.md](TEST_REPORT.md).

## Scope

In scope: YAML project loading with line-aware errors; `list` / `overdue` / `blockers` / `weekly-report`; webhook and Telegram posting (stdlib HTTP); JSON flags; static Pages sample report and schema; CI on Python 3.11 and 3.14.

Out of scope for this tag: PyPI publish, Slack/Discord-shaped webhook payloads, client/status filters, demo GIF.

## Automated gate (must be green)

| Check | Command / place |
| --- | --- |
| Lint | `ruff check .` |
| Format | `ruff format --check .` |
| Types | `mypy` |
| Tests + coverage ≥ 85% | `pytest` |
| Wheel build | `python -m build` (CI) |
| CI matrix | Python 3.11 and 3.14 on `ubuntu-latest` |

## Manual checklist (human)

- [ ] Open https://mohamedtaqysalmi.github.io/client-pulse/ after Pages deploy
- [ ] Sample report shows Globex overdue and three blocker groups
- [ ] Copy Markdown button works in a Chromium browser
- [ ] Schema table and `schema.json` match the README field list
- [ ] Mobile width (~375px): hero brand and report readable, no horizontal scroll on the report body
- [ ] `client-pulse weekly-report examples/projects --today 2026-03-16` matches `tests/snapshots/weekly_report.md`
- [ ] `client-pulse weekly-report examples/projects --webhook-url https://example.invalid --dry-run` prints a dry-run line and does not hang
- [ ] Record a short demo GIF for the README (not in this tag yet)

## Honesty checks

- Sample clients are fictional (Acme, Globex, Initech, Hooli, Umbrella)
- README states webhook body is raw Markdown (not Slack/Discord JSON)
- Security policy notes there is no published PyPI package yet if that is still true at tag time

## Sign-off

Automated gate: see TEST_REPORT.md for the local run used at tag time. CI on `main` after squash-merge is the public record.
