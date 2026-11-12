import re
from datetime import date, timedelta
from typing import Any

from client_pulse.models import Project, format_hours

WINDOW_DAYS = 7


def overdue(projects: list[Project], today: date) -> list[Project]:
    found = [p for p in projects if p.is_overdue(today)]
    return sorted(found, key=lambda p: (p.deadline, p.name))


def with_blockers(projects: list[Project]) -> list[Project]:
    found = [p for p in projects if p.is_open and p.blockers]
    return sorted(found, key=lambda p: (p.deadline, p.name))


def due_soon(projects: list[Project], today: date) -> list[Project]:
    end = today + timedelta(days=WINDOW_DAYS)
    found = [p for p in projects if p.is_open and today <= p.deadline <= end]
    return sorted(found, key=lambda p: (p.deadline, p.name))


def over_estimate(projects: list[Project]) -> list[Project]:
    found = [p for p in projects if p.is_open and p.over_estimate]
    return sorted(found, key=lambda p: p.name)


def report_data(projects: list[Project], today: date) -> dict[str, Any]:
    def dump(items: list[Project]) -> list[dict[str, Any]]:
        return [p.to_dict(today) for p in items]

    open_projects = [p for p in projects if p.is_open]
    return {
        "today": today.isoformat(),
        "window_days": WINDOW_DAYS,
        "open_projects": len(open_projects),
        "overdue": dump(overdue(projects, today)),
        "due_soon": dump(due_soon(projects, today)),
        "blockers": dump(with_blockers(projects)),
        "over_estimate": dump(over_estimate(projects)),
    }


def md_escape(text: str) -> str:
    """Escape characters that would start inline Markdown or HTML.

    Project fields are user input. Without this, a name like "[x](http://...)"
    becomes a live link in the report. The report is also posted as plain text,
    so only the few characters that matter inline are escaped.
    """
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", text)


def _label(p: Project) -> str:
    return f"**{md_escape(p.name)}** ({md_escape(p.client)})"


def _days(n: int) -> str:
    return f"{n} day" if abs(n) == 1 else f"{n} days"


def render_markdown(projects: list[Project], today: date) -> str:
    late = overdue(projects, today)
    soon = due_soon(projects, today)
    blocked = with_blockers(projects)
    over = over_estimate(projects)
    open_count = sum(1 for p in projects if p.is_open)

    lines = [
        f"# Weekly report, {today.isoformat()}",
        "",
        f"{open_count} open projects, {len(late)} overdue, {len(blocked)} blocked.",
        "",
        "## Overdue",
        "",
    ]
    if late:
        for p in late:
            lines.append(
                f"- {_label(p)}: due {p.deadline.isoformat()}, "
                f"{_days(-p.days_until_deadline(today))} late"
            )
    else:
        lines.append("Nothing overdue.")

    lines += ["", f"## Due in the next {WINDOW_DAYS} days", ""]
    if soon:
        for p in soon:
            when = (
                "today"
                if p.deadline == today
                else f"in {_days(p.days_until_deadline(today))}"
            )
            milestone = (
                f", next: {md_escape(p.next_milestone)}" if p.next_milestone else ""
            )
            lines.append(f"- {_label(p)}: {p.deadline.isoformat()}, {when}{milestone}")
    else:
        lines.append("Nothing due.")

    lines += ["", "## Blockers", ""]
    if blocked:
        for p in blocked:
            lines.append(f"- {_label(p)}")
            lines.extend(f"  - {md_escape(b)}" for b in p.blockers)
    else:
        lines.append("No open blockers.")

    lines += ["", "## Hours over estimate", ""]
    if over:
        for p in over:
            extra = p.hours_spent - p.hours_estimated
            spent = format_hours(p.hours_spent)
            planned = format_hours(p.hours_estimated)
            lines.append(
                f"- {_label(p)}: {spent} h spent of {planned} h estimated, "
                f"{format_hours(extra)} h over"
            )
    else:
        lines.append("All open projects are within their estimate.")

    return "\n".join(lines) + "\n"
