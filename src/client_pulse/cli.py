import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

from client_pulse import __version__
from client_pulse.loader import load_projects
from client_pulse.models import Project
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


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True)
    ] = False,
) -> None:
    pass


def _today(value: str | None) -> date:
    if value is None:
        return date.today()
    try:
        return date.fromisoformat(value)
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
    typer.echo(json.dumps(data, indent=2))


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
            f"{p.hours_spent:g}/{p.hours_estimated:g}",
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
) -> None:
    """Write the weekly report as Markdown (or JSON with --json)."""
    now = _today(today)
    projects = _load(path)
    if json_out:
        text = json.dumps(report_data(projects, now), indent=2) + "\n"
    else:
        text = render_markdown(projects, now)
    if output is None:
        typer.echo(text, nl=False)
        return
    output.write_text(text, encoding="utf-8")
    typer.echo(f"Wrote {output}", err=True)
