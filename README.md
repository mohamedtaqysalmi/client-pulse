# client-pulse

A command line tool to track several client projects from YAML files: deadlines, blockers, hours and a weekly Markdown report.

Status: early scaffold, nothing usable yet. The package only exposes its version for now.

## Development setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
```

## Running the checks

```bash
ruff check .
ruff format --check .
mypy
pytest
```

`pytest` runs with coverage and fails below 85%.

## License

MIT, see [LICENSE](LICENSE).
