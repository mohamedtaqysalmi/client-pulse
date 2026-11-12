# client-pulse

A command line tool to track several client projects from YAML files: deadlines, blockers, hours and a weekly Markdown report. Optionally POST that report to a webhook or Telegram.

Status: v0.1.0. Install from a clone (not on PyPI yet). Sample site: [mohamedtaqysalmi.github.io/client-pulse](https://mohamedtaqysalmi.github.io/client-pulse/).

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

### Posting the weekly report

`weekly-report` can POST the Markdown body:

```bash
# Generic webhook: raw Markdown, Content-Type text/markdown
client-pulse weekly-report examples/projects \
  --webhook-url "$CLIENT_PULSE_WEBHOOK_URL"

# Telegram Bot API sendMessage (plain text, truncated at 4096 chars)
client-pulse weekly-report examples/projects \
  --telegram-token "$TELEGRAM_BOT_TOKEN" \
  --telegram-chat-id "$TELEGRAM_CHAT_ID"

# Build the report and show destinations without sending
client-pulse weekly-report examples/projects \
  --webhook-url "$CLIENT_PULSE_WEBHOOK_URL" --dry-run
```

Environment variables mirror the flags: `CLIENT_PULSE_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Slack and Discord expect their own JSON shapes; this release sends raw Markdown only. `--json` cannot be combined with posting.

Webhook URLs must start with `https://`; anything else is refused. Redirects are not followed and each request times out after 15 seconds. Error and status lines show only the host, because webhook paths and Telegram tokens are secrets. Prefer the environment variables over `--telegram-token`, since command line arguments are visible in the process list to other users of the machine.

### Validation errors

Problems are reported with the file, the line and what to fix. All files are checked before anything is printed, and the exit code is 1 if any file is invalid:

```console
$ client-pulse list examples/broken
error: examples/broken/missing-deadline.yaml:1: missing required field 'deadline'
error: examples/broken/missing-deadline.yaml:5: hours_spent: expected a number of hours, got text 'ten'
2 problems found, nothing reported.
```

(Paths are shown with forward slashes here. On Windows they print with backslashes.) The checks cover missing fields, unknown fields, bad dates (only `YYYY-MM-DD`), wrong types, negative or non-finite hours, unknown status values, line breaks and control characters in text fields, YAML syntax errors and duplicate project names across files. Names, clients, milestones and blockers must fit on one line; Markdown characters in them are escaped in the report.

## What is not built yet

- Slack / Discord shaped webhook payloads.
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

`pytest` runs with coverage and fails below 85%. See [CONTRIBUTING.md](CONTRIBUTING.md), [QA.md](QA.md) and [docs/architecture.md](docs/architecture.md).

## License

MIT, see [LICENSE](LICENSE).
