# Architecture

client-pulse is a small CLI. There is no server process in the tagged release.

## Flow

1. `loader.load_projects` reads one YAML file per project (or every `*.yaml` / `*.yml` in a directory) with `ruamel.yaml` so field errors can cite a line number.
2. Valid files become frozen `Project` dataclasses in `models.py`.
3. `report.py` filters overdue / due-soon / blockers / over-estimate and renders Markdown or a JSON payload.
4. `cli.py` (Typer) prints tables or the report. `weekly-report` can also POST Markdown through `notify.py` to a generic webhook or Telegram `sendMessage`.

## Posting

- Webhook: raw Markdown body, `Content-Type: text/markdown`. Adapters for Slack/Discord shapes are left to the caller or a later release.
- Telegram: plain text (no `parse_mode`), truncated at 4096 characters.
- `--dry-run` builds the report and prints destinations without opening a socket.
- Tokens travel only through CLI flags or environment variables; nothing is logged.

## Pages

`site/` is a static sample of the weekly report plus a human-readable schema table and `schema.json`. It is not a live editor.
