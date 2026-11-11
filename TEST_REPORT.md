# Test report — client-pulse v0.1.0

Local gate run used for the v0.1.0 tag. Public CI on `main` after merge is the record for Linux.

## Environment

- OS: Windows 10 (build 26300)
- Python: 3.15.2 (local). CI matrix: 3.11 and 3.14 on `ubuntu-latest`.
- Commands: `ruff check .`, `ruff format --check .`, `mypy`, `pytest`

## Results

| Check | Result |
| --- | --- |
| Ruff lint | pass |
| Ruff format | pass |
| Mypy (strict) | pass |
| Pytest | **69 passed** |
| Coverage | **98.38%** (floor 85%) |

## Notes

- Webhook and Telegram posting are covered with injected posters and mocked `urllib`; no live network calls in CI.
- Snapshot: `tests/snapshots/weekly_report.md` matches `examples/projects` for `--today 2026-03-16`.
- Wheel build is exercised in GitHub Actions (`python -m build`), not in this local Windows note (editable install only).
