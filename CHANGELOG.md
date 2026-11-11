# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-11

### Added

- Project scaffold: packaging, linting, type checking and test setup.
- Loading of project files from YAML, with errors that give the file, line and what to fix.
- `list`, `overdue`, `blockers` and `weekly-report` commands, each with `--json`. `--today` (or `CLIENT_PULSE_TODAY`) sets the date.
- `weekly-report --webhook-url` and Telegram (`--telegram-token` / `--telegram-chat-id`) posting, with `--dry-run` and matching environment variables.
- Example project files in `examples/` (fictional clients only).
- Static GitHub Pages sample weekly report and YAML schema reference under `site/`.
- QA notes and architecture doc.
