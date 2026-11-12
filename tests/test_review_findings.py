"""Regression tests for problems found in the pre-0.2 code review."""

import json
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from client_pulse import notify
from client_pulse.cli import app
from client_pulse.loader import load_projects
from client_pulse.models import Project, Status, format_hours
from client_pulse.report import md_escape, render_markdown

from .conftest import ProjectWriter

runner = CliRunner()
TAIL = "client: C\nstatus: active\ndeadline: 2026-03-01\nhours_estimated: 1\n"
TOKEN = "123456:ABC-def_GHI"


def only_error(tmp_path: Path, content: str) -> tuple[int | None, str]:
    (tmp_path / "a.yaml").write_text(content, encoding="utf-8")
    (error,) = load_projects(tmp_path).errors
    return error.line, error.message


def test_control_character_in_file_is_an_error_not_a_traceback(tmp_path: Path) -> None:
    line, message = only_error(tmp_path, "name: A\n" + TAIL + "hours_spent: 0\x1b\n")
    assert line == 6
    assert "U+001B" in message


def test_line_break_in_a_text_field_is_rejected(tmp_path: Path) -> None:
    line, message = only_error(
        tmp_path, 'name: "A\\n# Injected"\n' + TAIL + "hours_spent: 0\n"
    )
    assert line == 1
    assert "line break" in message


def test_bidi_override_in_client_is_rejected(tmp_path: Path) -> None:
    content = 'name: A\nclient: "C\\u202eX"\nstatus: active\ndeadline: 2026-03-01\n'
    line, message = only_error(
        tmp_path, content + "hours_estimated: 1\nhours_spent: 0\n"
    )
    assert line == 2
    assert "U+202E" in message


def test_blocker_with_line_break_points_at_the_item(tmp_path: Path) -> None:
    content = "name: A\n" + TAIL + 'hours_spent: 0\nblockers:\n  - "x\\ny"\n'
    line, message = only_error(tmp_path, content)
    assert line == 8
    assert "line break" in message


@pytest.mark.parametrize("value", [".inf", ".nan", "-.inf"])
def test_non_finite_hours_are_rejected(tmp_path: Path, value: str) -> None:
    _, message = only_error(tmp_path, f"name: A\n{TAIL}hours_spent: {value}\n")
    assert "finite" in message or "negative" in message


def test_empty_deadline_message_is_readable(tmp_path: Path) -> None:
    content = "name: A\nclient: C\nstatus: active\ndeadline:\nhours_estimated: 1\n"
    line, message = only_error(tmp_path, content + "hours_spent: 0\n")
    assert line == 4
    assert "an empty value is not a valid date" in message


def test_non_string_key_reports_its_line(tmp_path: Path) -> None:
    content = "name: A\n1: x\n" + TAIL + "hours_spent: 0\n"
    line, message = only_error(tmp_path, content)
    assert line == 2
    assert "unknown field" in message


def test_unclosed_quote_names_the_line_where_it_started(tmp_path: Path) -> None:
    line, message = only_error(tmp_path, 'name: "A\nclient: C\n')
    assert line == 3
    assert "starting at line 1" in message


def test_second_document_is_explained(tmp_path: Path) -> None:
    line, message = only_error(
        tmp_path, "name: A\n" + TAIL + "hours_spent: 0\n---\nname: B\n"
    )
    assert line == 7
    assert "second document" in message


def test_alias_bomb_in_a_field_gives_a_short_error(tmp_path: Path) -> None:
    lines = ["a: &a [x,x,x,x,x,x,x,x,x]"]
    previous = "a"
    for name in "bcdefgh":
        lines.append(f"{name}: &{name} [{','.join(['*' + previous] * 9)}]")
        previous = name
    content = "\n".join(lines) + f"\nname: *{previous}\n" + TAIL + "hours_spent: 0\n"
    (tmp_path / "bomb.yaml").write_text(content, encoding="utf-8")
    errors = load_projects(tmp_path).errors
    assert errors
    assert all(len(str(e)) < 300 for e in errors)


def test_unsafe_python_tags_are_not_executed(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    content = f"name: !!python/object/apply:pathlib.Path.touch [{marker.as_posix()}]\n"
    (tmp_path / "a.yaml").write_text(content + TAIL + "hours_spent: 0\n")
    assert load_projects(tmp_path).errors
    assert not marker.exists()


def test_long_values_are_shortened_in_errors(tmp_path: Path) -> None:
    content = f"name: A\n{TAIL}hours_spent: {'x' * 500}\n"
    _, message = only_error(tmp_path, content)
    assert len(message) < 200


def test_utf8_bom_is_accepted(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_bytes(
        b"\xef\xbb\xbfname: A\n" + (TAIL + "hours_spent: 0\n").encode()
    )
    assert not load_projects(tmp_path).errors


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0, "0"),
        (31.5, "31.5"),
        (1234567, "1234567"),
        (100000.5, "100000.5"),
        (0.1 + 0.2, "0.3"),
        (12.0, "12"),
    ],
)
def test_format_hours_has_no_exponent_and_keeps_digits(value: float, text: str) -> None:
    assert format_hours(value) == text


def test_markdown_in_project_fields_is_escaped() -> None:
    assert md_escape("[x](http://e) *b* <b> a_b `c` \\") == (
        "\\[x\\](http://e) \\*b\\* \\<b\\> a\\_b \\`c\\` \\\\"
    )


def test_report_escapes_every_user_field() -> None:
    project = Project(
        name="[n](http://evil)",
        client="*c*",
        status=Status.ACTIVE,
        deadline=__import__("datetime").date(2026, 3, 16),
        hours_estimated=1,
        hours_spent=2,
        next_milestone="<script>",
        blockers=("_b_",),
    )
    text = render_markdown([project], project.deadline)
    assert "[n](" not in text.replace("\\[n\\](", "")
    assert "<script>" not in text.replace("\\<script\\>", "")
    for fragment in ("\\*c\\*", "\\_b\\_"):
        assert fragment in text


def test_plain_names_are_left_alone() -> None:
    assert md_escape("Acme website refresh (v2) - phase 1.") == (
        "Acme website refresh (v2) - phase 1."
    )


def test_non_ascii_names_in_json_and_markdown(write_project: ProjectWriter) -> None:
    path = write_project(name="مشروع القهوة")
    path.write_text(
        path.read_text(encoding="utf-8").replace("Acme Bakery", "Café Ünï 東京"),
        encoding="utf-8",
    )
    folder = str(path.parent)
    raw = runner.invoke(app, ["list", folder, "--json"])
    data = json.loads(raw.stdout)
    assert data[0]["name"] == "مشروع القهوة"
    assert "مشروع القهوة" in raw.stdout  # not \u-escaped
    report = runner.invoke(app, ["weekly-report", folder, "--today", "2026-03-20"])
    assert "Café Ünï 東京" in report.stdout


def test_output_to_a_missing_folder_is_an_error(
    write_project: ProjectWriter, tmp_path: Path
) -> None:
    folder = str(write_project().parent)
    target = tmp_path / "missing" / "r.md"
    result = runner.invoke(app, ["weekly-report", folder, "-o", str(target)])
    assert result.exit_code == 1
    assert "cannot write" in result.stderr
    assert "Traceback" not in result.stderr


def test_output_file_uses_unix_newlines(
    write_project: ProjectWriter, tmp_path: Path
) -> None:
    folder = str(write_project().parent)
    target = tmp_path / "r.md"
    runner.invoke(app, ["weekly-report", folder, "-o", str(target)])
    assert b"\r\n" not in target.read_bytes()


def test_webhook_must_be_https(write_project: ProjectWriter) -> None:
    folder = str(write_project().parent)
    result = runner.invoke(
        app, ["weekly-report", folder, "--webhook-url", "http://hooks.example/x"]
    )
    assert result.exit_code == 1
    assert "https://" in result.stderr


def test_webhook_url_secrets_are_not_printed(write_project: ProjectWriter) -> None:
    folder = str(write_project().parent)
    url = "https://hooks.example/services/T000/B000/SECRETPART"
    dry = runner.invoke(
        app, ["weekly-report", folder, "--webhook-url", url, "--dry-run"]
    )
    assert "SECRETPART" not in dry.stderr
    assert "hooks.example" in dry.stderr


def test_telegram_token_never_appears_when_the_api_rejects_it(
    write_project: ProjectWriter,
) -> None:
    folder = str(write_project().parent)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    err = urllib.error.HTTPError(
        url, 401, "Unauthorized", hdrs=Message(), fp=MagicMock()
    )
    err.read = MagicMock(return_value=b'{"ok":false,"description":"Unauthorized"}')  # type: ignore[method-assign]
    with patch.object(notify._opener, "open", side_effect=err):
        result = runner.invoke(
            app,
            [
                "weekly-report",
                folder,
                "--telegram-token",
                TOKEN,
                "--telegram-chat-id",
                "42",
            ],
        )
    assert result.exit_code == 1
    assert "HTTP 401" in result.stderr
    assert TOKEN not in result.stderr
    assert TOKEN not in result.stdout


def test_bad_telegram_token_is_not_echoed(write_project: ProjectWriter) -> None:
    folder = str(write_project().parent)
    result = runner.invoke(
        app,
        [
            "weekly-report",
            folder,
            "--telegram-token",
            "my-secret-value",
            "--telegram-chat-id",
            "42",
        ],
    )
    assert result.exit_code == 1
    assert "my-secret-value" not in result.stderr


@pytest.mark.parametrize("value", ["20260316", "2026-W12-1", "2026-3-16", "٢٠٢٦-٠٣-١٦"])
def test_only_yyyy_mm_dd_is_a_date(tmp_path: Path, value: str) -> None:
    content = f'name: A\nclient: C\nstatus: active\ndeadline: "{value}"\n'
    _, message = only_error(tmp_path, content + "hours_estimated: 1\nhours_spent: 0\n")
    assert "YYYY-MM-DD" in message
    result = runner.invoke(app, ["list", str(tmp_path), "--today", value])
    assert result.exit_code == 2
