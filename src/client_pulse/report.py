from datetime import date, timedelta
from typing import Any

from client_pulse.models import Project

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


def _hours(value: float) -> str:
    return f"{value:g}"


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
                f"- **{p.name}** ({p.client}): due {p.deadline.isoformat()}, "
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
            milestone = f", next: {p.next_milestone}" if p.next_milestone else ""
            lines.append(
                f"- **{p.name}** ({p.client}): {p.deadline.isoformat()}, "
                f"{when}{milestone}"
            )
    else:
        lines.append("Nothing due.")

    lines += ["", "## Blockers", ""]
    if blocked:
        for p in blocked:
            lines.append(f"- **{p.name}** ({p.client})")
            lines.extend(f"  - {b}" for b in p.blockers)
    else:
        lines.append("No open blockers.")

    lines += ["", "## Hours over estimate", ""]
    if over:
        for p in over:
            extra = p.hours_spent - p.hours_estimated
            lines.append(
                f"- **{p.name}** ({p.client}): {_hours(p.hours_spent)} h spent of "
                f"{_hours(p.hours_estimated)} h estimated, {_hours(extra)} h over"
            )
    else:
        lines.append("All open projects are within their estimate.")

    return "\n".join(lines) + "\n"
