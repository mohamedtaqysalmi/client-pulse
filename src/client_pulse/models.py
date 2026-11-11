from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any


class Status(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on-hold"
    DONE = "done"


@dataclass(frozen=True)
class Project:
    name: str
    client: str
    status: Status
    deadline: date
    hours_estimated: float
    hours_spent: float
    next_milestone: str | None = None
    blockers: tuple[str, ...] = field(default_factory=tuple)
    source: Path = Path()

    @property
    def is_open(self) -> bool:
        return self.status is not Status.DONE

    @property
    def over_estimate(self) -> bool:
        return self.hours_spent > self.hours_estimated

    def days_until_deadline(self, today: date) -> int:
        return (self.deadline - today).days

    def is_overdue(self, today: date) -> bool:
        # A project due today is not overdue yet.
        return self.is_open and self.deadline < today

    def to_dict(self, today: date) -> dict[str, Any]:
        return {
            "name": self.name,
            "client": self.client,
            "status": self.status.value,
            "next_milestone": self.next_milestone,
            "deadline": self.deadline.isoformat(),
            "days_until_deadline": self.days_until_deadline(today),
            "blockers": list(self.blockers),
            "hours_estimated": self.hours_estimated,
            "hours_spent": self.hours_spent,
            "over_estimate": self.over_estimate,
            "source": self.source.as_posix(),
        }
