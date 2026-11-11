from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.constructor import RoundTripConstructor
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.nodes import ScalarNode

from client_pulse.models import Project, Status

REQUIRED = ("name", "client", "status", "deadline", "hours_estimated", "hours_spent")
OPTIONAL = ("next_milestone", "blockers")


@dataclass(frozen=True)
class LoadError:
    path: Path
    line: int | None
    message: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else str(self.path)
        return f"{where}: {self.message}"


@dataclass(frozen=True)
class LoadResult:
    projects: list[Project]
    errors: list[LoadError]


class _Constructor(RoundTripConstructor):
    pass


def _timestamp(constructor: RoundTripConstructor, node: ScalarNode) -> Any:
    # ruamel raises a bare ValueError for 2026-13-45, which has no line number.
    # Keep the text instead so the date check can report the line.
    try:
        return RoundTripConstructor.construct_yaml_timestamp(constructor, node)
    except ValueError:
        return constructor.construct_scalar(node)


_Constructor.add_constructor("tag:yaml.org,2002:timestamp", _timestamp)


def find_project_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files = [*path.glob("*.yaml"), *path.glob("*.yml")]
    return sorted(files)


def load_projects(path: Path) -> LoadResult:
    projects: list[Project] = []
    errors: list[LoadError] = []
    seen: dict[str, tuple[Path, int | None]] = {}
    for file in find_project_files(path):
        project, file_errors, name_line = _load_file(file)
        errors.extend(file_errors)
        if project is None:
            continue
        key = project.name.casefold()
        if key in seen:
            other, other_line = seen[key]
            first = f"{other}:{other_line}" if other_line else str(other)
            errors.append(
                LoadError(
                    file,
                    name_line,
                    f"duplicate project name {project.name!r}, already defined in "
                    f"{first}. Rename one of them.",
                )
            )
            continue
        seen[key] = (file, name_line)
        projects.append(project)
    return LoadResult(projects, errors)


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.Constructor = _Constructor
    return yaml


def _line(node: CommentedMap | CommentedSeq, key: Any) -> int | None:
    try:
        return int(node.lc.data[key][0]) + 1  # ruamel lines are 0-based
    except (KeyError, IndexError, AttributeError):
        return None


def _load_file(file: Path) -> tuple[Project | None, list[LoadError], int | None]:
    try:
        data = _yaml().load(file.read_text(encoding="utf-8"))
    except MarkedYAMLError as exc:
        mark = exc.problem_mark
        line = mark.line + 1 if mark is not None else None
        problem = exc.problem or "invalid YAML"
        return None, [LoadError(file, line, f"invalid YAML: {problem}")], None
    except (OSError, UnicodeDecodeError) as exc:
        return None, [LoadError(file, None, f"cannot read file: {exc}")], None

    if not isinstance(data, CommentedMap):
        return (
            None,
            [
                LoadError(
                    file, 1, "expected a mapping of project fields at the top level"
                )
            ],
            None,
        )

    errors: list[LoadError] = []

    def err(key: str, message: str, line: int | None = None) -> None:
        errors.append(LoadError(file, line or _line(data, key), f"{key}: {message}"))

    for key in data:
        if key not in REQUIRED and key not in OPTIONAL:
            err(
                str(key),
                f"unknown field. Allowed fields: {', '.join(REQUIRED + OPTIONAL)}",
            )
    for key in REQUIRED:
        if key not in data:
            errors.append(LoadError(file, 1, f"missing required field '{key}'"))

    name = _text(data, "name", err, required=True)
    client = _text(data, "client", err, required=True)
    milestone = _text(data, "next_milestone", err, required=False)
    status = _status(data, err)
    deadline = _date(data, "deadline", err)
    estimated = _hours(data, "hours_estimated", err)
    spent = _hours(data, "hours_spent", err)
    blockers = _blockers(data, err)

    name_line = _line(data, "name")
    if (
        errors
        or name is None
        or client is None
        or status is None
        or deadline is None
        or estimated is None
        or spent is None
    ):
        return None, errors, name_line
    project = Project(
        name=name,
        client=client,
        status=status,
        deadline=deadline,
        hours_estimated=estimated,
        hours_spent=spent,
        next_milestone=milestone,
        blockers=tuple(blockers),
        source=file,
    )
    return project, errors, name_line


def _type_name(value: object) -> str:
    return type(value).__name__


def _text(data: CommentedMap, key: str, err: Any, *, required: bool) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        err(
            key,
            f"expected non-empty text, got {_describe(value)}. "
            "Wrap it in quotes if it is a number.",
        )
        return None
    return value.strip()


def _describe(value: object) -> str:
    if value is None:
        return "an empty value"
    if isinstance(value, str) and not value.strip():
        return "an empty string"
    return f"{_type_name(value)} {value!r}"


def _status(data: CommentedMap, err: Any) -> Status | None:
    if "status" not in data:
        return None
    value = data["status"]
    allowed = ", ".join(s.value for s in Status)
    try:
        return Status(value)
    except ValueError:
        err("status", f"{value!r} is not a valid status. Use one of: {allowed}")
        return None


def _date(data: CommentedMap, key: str, err: Any) -> date | None:
    if key not in data:
        return None
    value = data[key]
    if isinstance(value, datetime):
        err(key, "expected a date like 2026-03-31 without a time of day")
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    err(
        key,
        f"{value!r} is not a valid date. "
        "Use the form YYYY-MM-DD, for example 2026-03-31",
    )
    return None


def _hours(data: CommentedMap, key: str, err: Any) -> float | None:
    if key not in data:
        return None
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        err(key, f"expected a number of hours, got {_describe(value)}")
        return None
    if value < 0:
        err(key, f"hours cannot be negative, got {value}")
        return None
    return float(value)


def _blockers(data: CommentedMap, err: Any) -> list[str]:
    if "blockers" not in data or data["blockers"] is None:
        return []
    value = data["blockers"]
    if not isinstance(value, CommentedSeq):
        err("blockers", f"expected a list of text items, got {_describe(value)}")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            err(
                "blockers",
                f"item {index + 1} should be text, got {_describe(item)}",
                _line(value, index),
            )
            continue
        result.append(item.strip())
    return result
