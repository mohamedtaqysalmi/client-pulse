# client-pulse

A command line tool to track several client projects from YAML files: deadlines, blockers, hours and a weekly Markdown report.

Status: early. The four core commands below work and are tested. Nothing is published to PyPI yet, so install from a clone.

## Quickstart

Requires Python 3.11 or newer.

```bash
git clone https://github.com/mohamedtaqysalmi/client-pulse.git
cd client-pulse
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
```

Each project is one YAML file in a directory. See [examples/projects](examples/projects) for five made-up ones (the clients are fictional):

```yaml
name: Acme website refresh
client: Acme Bakery
status: active            # active, on-hold or done
next_milestone: Homepage review call   # optional
deadline: 2026-03-20
blockers:                 # optional
  - Waiting for product photos from the client
hours_estimated: 40
hours_spent: 31.5
```

The commands take a directory (default: the current one) or a single file. `--today` fixes the date so the output below is reproducible; without it the system date is used. `CLIENT_PULSE_TODAY` does the same through the environment.

```console
$ client-pulse list examples/projects --today 2026-03-16
PROJECT                       CLIENT              STATUS   DEADLINE    HOURS    NEXT MILESTONE
Hooli landing page            Hooli Studio        done     2026-03-02  14/12    -
Globex order API              Globex Logistics    active   2026-03-12  92/80    Staging deploy
Initech sales dashboard       Initech Consulting  active   2026-03-16  18/25    Chart design sign-off
Acme website refresh          Acme Bakery         active   2026-03-20  31.5/40  Homepage review call
Umbrella accessibility audit  Umbrella Travel     on-hold  2026-04-30  4/16     -

$ client-pulse overdue examples/projects --today 2026-03-16
PROJECT           CLIENT            DEADLINE    DAYS LATE
Globex order API  Globex Logistics  2026-03-12  4

$ client-pulse blockers examples/projects --today 2026-03-16
Globex order API (Globex Logistics), due 2026-03-12
  - No access to the staging server yet
  - Payment sandbox keys not received
Acme website refresh (Acme Bakery), due 2026-03-20
  - Waiting for product photos from the client
Umbrella accessibility audit (Umbrella Travel), due 2026-04-30
  - Client paused the project until the new budget is approved
```

A project due today is not overdue. Projects with status `done` are left out of overdue, blockers and the report's hours check.

`client-pulse weekly-report examples/projects --today 2026-03-16` prints a Markdown report with overdue projects, what is due in the next 7 days, open blockers and projects over their hours estimate. Its exact output is checked in as [tests/snapshots/weekly_report.md](tests/snapshots/weekly_report.md). Use `--output report.md` to write it to a file.

Every command accepts `--json`. For example `client-pulse overdue examples/projects --today 2026-03-16 --json` prints a list of project objects with `name`, `client`, `status`, `next_milestone`, `deadline`, `days_until_deadline`, `blockers`, `hours_estimated`, `hours_spent`, `over_estimate` and `source`. With `weekly-report --json` you get an object with `overdue`, `due_soon`, `blockers` and `over_estimate` lists.

### Validation errors

Problems are reported with the file, the line and what to fix. All files are checked before anything is printed, and the exit code is 1 if any file is invalid:

```console
$ client-pulse list examples/broken
error: examples/broken/missing-deadline.yaml:1: missing required field 'deadline'
error: examples/broken/missing-deadline.yaml:5: hours_spent: expected a number of hours, got str 'ten'
2 problems found, nothing reported.
```

(Paths are shown with forward slashes here. On Windows they print with backslashes.) The checks cover missing fields, unknown fields, bad dates, wrong types, negative hours, unknown status values, YAML syntax errors and duplicate project names across files.

## What is not built yet

- Posting the report to a webhook or Telegram.
- A static web view.
- Filters on the commands, such as by client or status.
- A PyPI release.

## Development

```bash
pip install -e ".[dev]"
pre-commit install
ruff check .
ruff format --check .
mypy
pytest
```

`pytest` runs with coverage and fails below 85%. See [CONTRIBUTING.md](CONTRIBUTING.md) for branch and PR conventions.

## License

MIT, see [LICENSE](LICENSE).
