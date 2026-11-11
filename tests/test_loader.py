from datetime import date
from pathlib import Path

from client_pulse.loader import load_projects
from client_pulse.models import Status

from .conftest import ProjectWriter

HEADER = "name: A\nclient: C\nstatus: active\ndeadline: 2026-03-01\n"


def test_loads_a_valid_file(write_project: ProjectWriter, tmp_path: Path) -> None:
    write_project(blockers="[Waiting for logo]")
    result = load_projects(tmp_path)
    assert result.errors == []
    (project,) = result.projects
    assert project.name == "Site"
    assert project.status is Status.ACTIVE
    assert project.deadline == date(2026, 3, 20)
    assert project.blockers == ("Waiting for logo",)
    assert project.hours_spent == 5


def test_empty_directory_gives_no_projects_and_no_errors(tmp_path: Path) -> None:
    result = load_projects(tmp_path)
    assert result.projects == []
    assert result.errors == []


def test_accepts_a_single_file_path(write_project: ProjectWriter) -> None:
    path = write_project()
    assert len(load_projects(path).projects) == 1


def test_missing_field_is_reported_with_file_and_field(tmp_path: Path) -> None:
    file = tmp_path / "a.yaml"
    file.write_text("name: A\nclient: C\nstatus: active\nhours_estimated: 1\n")
    messages = [str(e) for e in load_projects(tmp_path).errors]
    assert any("missing required field 'deadline'" in m for m in messages)
    assert any("missing required field 'hours_spent'" in m for m in messages)
    assert all(str(file) in m for m in messages)


def test_bad_date_reports_the_line_of_the_value(
    write_project: ProjectWriter, tmp_path: Path
) -> None:
    write_project(deadline="2026-13-45")
    (error,) = load_projects(tmp_path).errors
    assert error.line == 5
    assert "deadline" in error.message
    assert "YYYY-MM-DD" in error.message


def test_quoted_iso_date_is_accepted(
    write_project: ProjectWriter, tmp_path: Path
) -> None:
    write_project(deadline='"2026-03-20"')
    assert load_projects(tmp_path).errors == []


def test_datetime_is_rejected(write_project: ProjectWriter, tmp_path: Path) -> None:
    write_project(deadline="2026-03-20 10:00:00")
    (error,) = load_projects(tmp_path).errors
    assert "without a time" in error.message


def test_wrong_type_for_hours(write_project: ProjectWriter, tmp_path: Path) -> None:
    write_project(estimated="lots")
    (error,) = load_projects(tmp_path).errors
    assert error.line == 7
    assert "hours_estimated" in error.message
    assert "lots" in error.message


def test_boolean_is_not_a_number_of_hours(
    write_project: ProjectWriter, tmp_path: Path
) -> None:
    write_project(spent="true")
    (error,) = load_projects(tmp_path).errors
    assert "hours_spent" in error.message


def test_negative_hours(write_project: ProjectWriter, tmp_path: Path) -> None:
    write_project(spent="-2")
    (error,) = load_projects(tmp_path).errors
    assert "negative" in error.message


def test_unknown_status_lists_the_allowed_values(
    write_project: ProjectWriter, tmp_path: Path
) -> None:
    write_project(status="paused")
    (error,) = load_projects(tmp_path).errors
    assert error.line == 3
    assert "on-hold" in error.message


def test_unknown_field_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(
        HEADER + "hours_estimated: 1\nhours_spent: 0\nbudget: 5\n"
    )
    (error,) = load_projects(tmp_path).errors
    assert error.line == 7
    assert "unknown field" in error.message


def test_name_given_as_a_number_is_a_type_error(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(
        "name: 2026\nclient: C\nstatus: active\ndeadline: 2026-03-01\n"
        "hours_estimated: 1\nhours_spent: 0\n"
    )
    (error,) = load_projects(tmp_path).errors
    assert error.line == 1
    assert "quotes" in error.message


def test_blockers_must_be_a_list(write_project: ProjectWriter, tmp_path: Path) -> None:
    write_project(blockers="waiting")
    (error,) = load_projects(tmp_path).errors
    assert error.line == 6
    assert "list" in error.message


def test_blocker_item_error_points_at_the_item(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(
        HEADER + "hours_estimated: 1\nhours_spent: 0\nblockers:\n  - ok\n  - 5\n"
    )
    (error,) = load_projects(tmp_path).errors
    assert error.line == 9


def test_duplicate_project_names_across_files(
    write_project: ProjectWriter, tmp_path: Path
) -> None:
    write_project("a.yaml", name="Site")
    second = write_project("b.yaml", name="site")
    (error,) = load_projects(tmp_path).errors
    assert error.path == second
    assert "duplicate project name" in error.message
    assert "a.yaml:1" in error.message


def test_yaml_syntax_error_has_a_line(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("name: A\nclient: [unclosed\nstatus: active\n")
    (error,) = load_projects(tmp_path).errors
    assert error.line is not None
    assert "invalid YAML" in error.message


def test_duplicate_key_in_one_file_is_reported(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("name: A\nname: B\n")
    (error,) = load_projects(tmp_path).errors
    assert error.line == 2
    assert "invalid YAML" in error.message


def test_top_level_list_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("- one\n- two\n")
    (error,) = load_projects(tmp_path).errors
    assert "mapping" in error.message


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("")
    assert len(load_projects(tmp_path).errors) == 1


def test_unreadable_bytes_are_reported_without_a_line(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_bytes(b"\xff\xfe\x00bad")
    (error,) = load_projects(tmp_path).errors
    assert "cannot read file" in error.message
    assert str(error).startswith(str(tmp_path / "a.yaml") + ": ")
