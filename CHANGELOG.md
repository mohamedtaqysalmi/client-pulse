# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- A Telegram error (for example a rejected token) printed the full request URL, including the bot token. Errors and status lines now show only the host.
- Webhook URLs were not restricted. Only `https://` is accepted now (not `http://`, `file://` or others), and redirects are no longer followed.
- Timeouts and connection resets while posting ended in a traceback. They are reported as a failed post.
- A control character in a YAML file ended in a traceback. It is now an error with the line number.
- A YAML alias bomb in a text field made error reporting hang while it formatted the value.
- Names, clients, milestones and blockers could contain line breaks. A line break in a name could add a heading to the report; Markdown characters are now escaped as well.
- `.inf` and `.nan` were accepted as hours. Hours of a million or more printed as `1.23457e+06`, and `100000.5` printed as `100000`.
- Non-ASCII client names could fail to print on consoles with a legacy code page, and `--json` escaped them as unicode escapes.
- `--output` to a folder that does not exist ended in a traceback. The file is now written with Unix line endings on every OS.
- Unclosed quotes were reported at the end of the file; the message now also names the line where they started.
- A non-string YAML key was reported without a line number, and an empty `deadline` said `None is not a valid date`.
- `--today` and deadlines accepted `20260316` and week dates on some Python versions. Only `YYYY-MM-DD` is accepted.
- Loading reused no parser and was about twice as slow as needed.

### Changed

- Rebuilt the GitHub Pages site on the shared page style: the sample report rendered from the real command, terminal output of `list`, `overdue` and `blockers`, and the YAML schema table. Tests check the page against the CLI and the loader.

## [0.1.0] - 2026-11-11

### Added

- Project scaffold: packaging, linting, type checking and test setup.
- Loading of project files from YAML, with errors that give the file, line and what to fix.
- `list`, `overdue`, `blockers` and `weekly-report` commands, each with `--json`. `--today` (or `CLIENT_PULSE_TODAY`) sets the date.
- `weekly-report --webhook-url` and Telegram (`--telegram-token` / `--telegram-chat-id`) posting, with `--dry-run` and matching environment variables.
- Example project files in `examples/` (fictional clients only).
- Static GitHub Pages sample weekly report and YAML schema reference under `site/`.
- QA notes and architecture doc.
