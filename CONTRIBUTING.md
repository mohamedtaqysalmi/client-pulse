# Contributing

client-pulse is maintained by one person, so replies to issues and pull requests may take a few days. Small, focused changes get reviewed fastest.

## Setup

You need Python 3.11 or newer.

```bash
git clone https://github.com/mohamedtaqysalmi/client-pulse.git
cd client-pulse
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
```

## Running the checks

CI runs the same commands on Python 3.11 and 3.14.

```bash
ruff check .
ruff format --check .
mypy
pytest
```

`pytest` reports coverage and fails below 85%. New behaviour needs tests.

## Branches and commits

Branch from `main` and name the branch `type/short-description`, for example `feat/overdue-command` or `fix/yaml-line-numbers`. The type matches the commit types below.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`. Pull requests are squash-merged, so the PR title becomes the commit message on `main`.

## Pull requests

- Open an issue first for anything larger than a small fix, so we agree on the approach before you spend time on it.
- Keep one change per PR and fill in the template.
- Add a line to the Unreleased section of `CHANGELOG.md` for user-visible changes.
- CI must be green before merge.
- Use fake data in tests and examples. Never commit real client names or secrets.

## Reporting security problems

Do not open a public issue. See [SECURITY.md](SECURITY.md).
