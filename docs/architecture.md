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
- Webhook URLs must be HTTPS. Redirects are not followed, the timeout is 15 seconds, and errors and status lines name only the host, never the path or token, because both can be secrets.
- Telegram token and chat id are checked for shape before any request. Tokens travel only through CLI flags or environment variables; prefer the environment, since flags show up in the process list.

## Pages

`site/` is a static sample of the weekly report, the output of `list`, `overdue` and `blockers`, and the YAML schema table, plus `schema.json`. Tests compare the page and `schema.json` with the CLI output and the loader. It is not a live editor.
