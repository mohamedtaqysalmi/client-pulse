import json
import sys
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

from client_pulse import __version__
from client_pulse.loader import load_projects
from client_pulse.models import Project, format_hours, parse_date
from client_pulse.notify import post_telegram, post_webhook
from client_pulse.report import (
    overdue,
    render_markdown,
    report_data,
    with_blockers,
)

app = typer.Typer(
    help="Track several client projects from YAML files.",
    no_args_is_help=True,
    add_completion=False,
)

PathArg = Annotated[
    Path,
    typer.Argument(help="Directory of project YAML files, or a single file."),
]
JsonOpt = Annotated[bool, typer.Option("--json", help="Print JSON instead of text.")]
TodayOpt = Annotated[
    str | None,
    typer.Option(
        "--today",
        envvar="CLIENT_PULSE_TODAY",
        help="Treat this date (YYYY-MM-DD) as today. Defaults to the system date.",
    ),
]


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def _use_utf8() -> None:
    # Client names are not always ASCII, and a Windows console or a pipe can
    # default to a legacy code page that cannot encode them.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True)
    ] = False,
) -> None:
    _use_utf8()


def _today(value: str | None) -> date:
    if value is None:
        return date.today()
    try:
        return parse_date(value)
    except ValueError:
        typer.echo(f"error: --today {value!r} is not a date. Use YYYY-MM-DD.", err=True)
        raise typer.Exit(2) from None


def _load(path: Path) -> list[Project]:
    if not path.exists():
        typer.echo(f"error: {path} does not exist", err=True)
        raise typer.Exit(2)
    result = load_projects(path)
    for error in result.errors:
        typer.echo(f"error: {error}", err=True)
    if result.errors:
        count = len(result.errors)
        typer.echo(
            f"{count} problem{'s' if count != 1 else ''} found, nothing reported.",
            err=True,
        )
        raise typer.Exit(1)
    return result.projects


def _emit_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    out = ["  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)).rstrip()]
    for row in rows:
        out.append(
            "  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)).rstrip()
        )
    return "\n".join(out)


@app.command("list")
def list_projects(
    path: PathArg = Path("."), json_out: JsonOpt = False, today: TodayOpt = None
) -> None:
    """List all projects, soonest deadline first."""
    now = _today(today)
    projects = sorted(_load(path), key=lambda p: (p.deadline, p.name))
    if json_out:
        _emit_json([p.to_dict(now) for p in projects])
        return
    if not projects:
        typer.echo(f"No project files found in {path}.")
        return
    rows = [
        [
            p.name,
            p.client,
            p.status.value,
            p.deadline.isoformat(),
            f"{format_hours(p.hours_spent)}/{format_hours(p.hours_estimated)}",
            p.next_milestone or "-",
        ]
        for p in projects
    ]
    typer.echo(
        _table(
            ["PROJECT", "CLIENT", "STATUS", "DEADLINE", "HOURS", "NEXT MILESTONE"], rows
        )
    )


@app.command("overdue")
def overdue_cmd(
    path: PathArg = Path("."), json_out: JsonOpt = False, today: TodayOpt = None
) -> None:
    """Show open projects whose deadline has passed."""
    now = _today(today)
    late = overdue(_load(path), now)
    if json_out:
        _emit_json([p.to_dict(now) for p in late])
        return
    if not late:
        typer.echo("Nothing overdue.")
        return
    rows = [
        [p.name, p.client, p.deadline.isoformat(), str(-p.days_until_deadline(now))]
        for p in late
    ]
    typer.echo(_table(["PROJECT", "CLIENT", "DEADLINE", "DAYS LATE"], rows))


@app.command("blockers")
def blockers_cmd(
    path: PathArg = Path("."), json_out: JsonOpt = False, today: TodayOpt = None
) -> None:
    """Show blockers on open projects."""
    now = _today(today)
    blocked = with_blockers(_load(path))
    if json_out:
        _emit_json([p.to_dict(now) for p in blocked])
        return
    if not blocked:
        typer.echo("No open blockers.")
        return
    for p in blocked:
        typer.echo(f"{p.name} ({p.client}), due {p.deadline.isoformat()}")
        for blocker in p.blockers:
            typer.echo(f"  - {blocker}")


@app.command("weekly-report")
def weekly_report(
    path: PathArg = Path("."),
    json_out: JsonOpt = False,
    today: TodayOpt = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write to this file instead of stdout."),
    ] = None,
    webhook_url: Annotated[
        str | None,
        typer.Option(
            "--webhook-url",
            envvar="CLIENT_PULSE_WEBHOOK_URL",
            help="POST the Markdown report to this URL (Content-Type: text/markdown).",
        ),
    ] = None,
    telegram_token: Annotated[
        str | None,
        typer.Option(
            "--telegram-token",
            envvar="TELEGRAM_BOT_TOKEN",
            help="Telegram bot token. Used with --telegram-chat-id.",
        ),
    ] = None,
    telegram_chat_id: Annotated[
        str | None,
        typer.Option(
            "--telegram-chat-id",
            envvar="TELEGRAM_CHAT_ID",
            help="Telegram chat id. Used with --telegram-token.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Build the report and show where it would be posted, without sending.",
        ),
    ] = False,
) -> None:
    """Write the weekly report as Markdown (or JSON with --json).

    Optionally POST the Markdown to a webhook and/or Telegram. JSON mode cannot
    be combined with posting: post the Markdown form, or pipe --json yourself.
    """
    now = _today(today)
    projects = _load(path)
    posting = bool(webhook_url or telegram_token or telegram_chat_id)
    if json_out and posting:
        typer.echo(
            "error: --json cannot be combined with webhook or Telegram posting.",
            err=True,
        )
        raise typer.Exit(2)
    if (telegram_token and not telegram_chat_id) or (
        telegram_chat_id and not telegram_token
    ):
        typer.echo(
            "error: Telegram posting needs both --telegram-token and "
            "--telegram-chat-id (or TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID).",
            err=True,
        )
        raise typer.Exit(2)

    if json_out:
        text = json.dumps(report_data(projects, now), indent=2) + "\n"
    else:
        text = render_markdown(projects, now)

    if webhook_url:
        try:
            result = post_webhook(webhook_url, text, dry_run=dry_run)
        except (RuntimeError, ValueError) as exc:
            typer.echo(f"error: webhook: {exc}", err=True)
            raise typer.Exit(1) from None
        if result.dry_run:
            typer.echo(
                f"dry-run: would POST Markdown to {result.destination}",
                err=True,
            )
        else:
            typer.echo(
                f"Posted webhook ({result.status_code}) to {result.destination}",
                err=True,
            )

    if telegram_token and telegram_chat_id:
        try:
            result = post_telegram(
                telegram_token, telegram_chat_id, text, dry_run=dry_run
            )
        except (RuntimeError, ValueError) as exc:
            typer.echo(f"error: telegram: {exc}", err=True)
            raise typer.Exit(1) from None
        if result.dry_run:
            typer.echo(
                f"dry-run: would send Telegram message to {result.destination}",
                err=True,
            )
        else:
            typer.echo(
                f"Posted Telegram ({result.status_code}) to {result.destination}",
                err=True,
            )

    if output is not None:
        try:
            # Same bytes on every OS, so no \r\n translation on Windows.
            with output.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except OSError as exc:
            typer.echo(f"error: cannot write {output}: {exc.strerror or exc}", err=True)
            raise typer.Exit(1) from None
        typer.echo(f"Wrote {output}", err=True)
        return
    if posting and not json_out:
        # Avoid dumping the same body twice when the user only wanted to post.
        return
    typer.echo(text, nl=False)
