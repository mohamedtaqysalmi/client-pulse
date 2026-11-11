from collections.abc import Callable
from pathlib import Path

import pytest

VALID = """\
name: {name}
client: Acme Bakery
status: {status}
next_milestone: Review call
deadline: {deadline}
blockers: {blockers}
hours_estimated: {estimated}
hours_spent: {spent}
"""

ProjectWriter = Callable[..., Path]


@pytest.fixture
def write_project(tmp_path: Path) -> ProjectWriter:
    def write(
        filename: str = "p.yaml",
        *,
        name: str = "Site",
        status: str = "active",
        deadline: str = "2026-03-20",
        blockers: str = "[]",
        estimated: str = "10",
        spent: str = "5",
    ) -> Path:
        path = tmp_path / filename
        path.write_text(
            VALID.format(
                name=name,
                status=status,
                deadline=deadline,
                blockers=blockers,
                estimated=estimated,
                spent=spent,
            ),
            encoding="utf-8",
        )
        return path

    return write
