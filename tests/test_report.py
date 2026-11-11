from datetime import date

from client_pulse.models import Project, Status
from client_pulse.report import (
    due_soon,
    over_estimate,
    overdue,
    render_markdown,
    with_blockers,
)

TODAY = date(2026, 3, 16)


def make(
    name: str = "P",
    *,
    deadline: date = TODAY,
    status: Status = Status.ACTIVE,
    estimated: float = 10,
    spent: float = 5,
    blockers: tuple[str, ...] = (),
) -> Project:
    return Project(
        name=name,
        client="C",
        status=status,
        deadline=deadline,
        hours_estimated=estimated,
        hours_spent=spent,
        blockers=blockers,
    )


def test_deadline_day_is_not_overdue_but_the_next_day_is() -> None:
    project = make(deadline=TODAY)
    assert overdue([project], TODAY) == []
    assert overdue([project], date(2026, 3, 17)) == [project]


def test_done_projects_are_never_overdue_blocked_or_over_estimate() -> None:
    project = make(
        deadline=date(2020, 1, 1),
        status=Status.DONE,
        spent=99,
        blockers=("x",),
    )
    assert overdue([project], TODAY) == []
    assert with_blockers([project]) == []
    assert over_estimate([project]) == []


def test_on_hold_projects_still_count_as_open() -> None:
    project = make(deadline=date(2026, 3, 1), status=Status.ON_HOLD)
    assert overdue([project], TODAY) == [project]


def test_hours_exactly_on_estimate_is_not_over() -> None:
    assert over_estimate([make(estimated=10, spent=10)]) == []
    assert len(over_estimate([make(estimated=10, spent=10.5)])) == 1


def test_due_soon_window_includes_both_ends() -> None:
    first = make("first", deadline=TODAY)
    last = make("last", deadline=date(2026, 3, 23))
    outside = make("outside", deadline=date(2026, 3, 24))
    assert due_soon([outside, last, first], TODAY) == [first, last]


def test_overdue_is_sorted_by_deadline_then_name() -> None:
    a = make("a", deadline=date(2026, 3, 10))
    b = make("b", deadline=date(2026, 3, 1))
    assert overdue([a, b], TODAY) == [b, a]


def test_empty_report_says_so() -> None:
    text = render_markdown([], TODAY)
    assert "0 open projects, 0 overdue, 0 blocked." in text
    assert "Nothing overdue." in text
    assert "Nothing due." in text
    assert "No open blockers." in text
    assert "within their estimate" in text


def test_singular_day_wording() -> None:
    late = make("late", deadline=date(2026, 3, 15))
    soon = make("soon", deadline=date(2026, 3, 17))
    text = render_markdown([late, soon], TODAY)
    assert "1 day late" in text
    assert "in 1 day" in text
