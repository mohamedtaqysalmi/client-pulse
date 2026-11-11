import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from client_pulse import __version__
from client_pulse.cli import app

from .conftest import ProjectWriter

runner = CliRunner()
ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "projects"
SNAPSHOT = Path(__file__).parent / "snapshots" / "weekly_report.md"
TODAY = ["--today", "2026-03-16"]


def run_json(command: str, path: Path) -> Any:
    result = runner.invoke(app, [command, str(path), "--json", *TODAY])
    assert result.exit_code == 0, result.stderr
    return json.loads(result.stdout)


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.stdout.strip() == __version__


def test_python_dash_m_entry_point() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "client_pulse", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == __version__


def test_list_text_output_sorted_by_deadline() -> None:
    result = runner.invoke(app, ["list", str(EXAMPLES), *TODAY])
    assert result.exit_code == 0
    names = [line.split("  ")[0] for line in result.stdout.splitlines()[1:]]
    assert names == [
        "Hooli landing page",
        "Globex order API",
        "Initech sales dashboard",
        "Acme website refresh",
        "Umbrella accessibility audit",
    ]


def test_list_json_shape() -> None:
    data = run_json("list", EXAMPLES)
    assert len(data) == 5
    globex = next(p for p in data if p["name"] == "Globex order API")
    assert globex["source"].endswith("examples/projects/globex-api.yaml")
    del globex["source"]
    assert globex == {
        "name": "Globex order API",
        "client": "Globex Logistics",
        "status": "active",
        "next_milestone": "Staging deploy",
        "deadline": "2026-03-12",
        "days_until_deadline": -4,
        "blockers": [
            "No access to the staging server yet",
            "Payment sandbox keys not received",
        ],
        "hours_estimated": 80.0,
        "hours_spent": 92.0,
        "over_estimate": True,
    }


def test_overdue_lists_only_open_late_projects() -> None:
    result = runner.invoke(app, ["overdue", str(EXAMPLES), *TODAY])
    assert result.exit_code == 0
    assert "Globex order API" in result.stdout
    assert "Hooli" not in result.stdout  # done, even though its deadline passed
    assert "Initech" not in result.stdout  # due today is not overdue


def test_overdue_boundary_on_the_deadline_day(write_project: ProjectWriter) -> None:
    path = write_project(deadline="2026-03-16")
    folder = str(path.parent)
    on_day = runner.invoke(app, ["overdue", folder, "--today", "2026-03-16"])
    assert on_day.stdout.strip() == "Nothing overdue."
    next_day = runner.invoke(app, ["overdue", folder, "--today", "2026-03-17"])
    assert "Site" in next_day.stdout
    assert next_day.stdout.rstrip().endswith("1")


def test_overdue_json() -> None:
    data = run_json("overdue", EXAMPLES)
    assert [p["name"] for p in data] == ["Globex order API"]


def test_blockers_text_and_json() -> None:
    result = runner.invoke(app, ["blockers", str(EXAMPLES)])
    assert "  - Waiting for product photos from the client" in result.stdout
    data = run_json("blockers", EXAMPLES)
    assert [p["name"] for p in data] == [
        "Globex order API",
        "Acme website refresh",
        "Umbrella accessibility audit",
    ]


def test_blockers_none(write_project: ProjectWriter) -> None:
    path = write_project()
    result = runner.invoke(app, ["blockers", str(path.parent)])
    assert result.stdout.strip() == "No open blockers."


def test_weekly_report_matches_snapshot() -> None:
    result = runner.invoke(app, ["weekly-report", str(EXAMPLES), *TODAY])
    assert result.exit_code == 0
    assert result.stdout == SNAPSHOT.read_text(encoding="utf-8")


def test_weekly_report_writes_a_file(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    result = runner.invoke(
        app, ["weekly-report", str(EXAMPLES), *TODAY, "--output", str(out)]
    )
    assert result.exit_code == 0
    assert result.stdout == ""
    assert out.read_text(encoding="utf-8") == SNAPSHOT.read_text(encoding="utf-8")


def test_weekly_report_json_shape() -> None:
    result = runner.invoke(app, ["weekly-report", str(EXAMPLES), "--json", *TODAY])
    data = json.loads(result.stdout)
    assert set(data) == {
        "today",
        "window_days",
        "open_projects",
        "overdue",
        "due_soon",
        "blockers",
        "over_estimate",
    }
    assert data["today"] == "2026-03-16"
    assert data["open_projects"] == 4
    assert [p["name"] for p in data["due_soon"]] == [
        "Initech sales dashboard",
        "Acme website refresh",
    ]
    assert [p["name"] for p in data["over_estimate"]] == ["Globex order API"]


def test_weekly_report_json_to_file(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    runner.invoke(
        app, ["weekly-report", str(EXAMPLES), "--json", *TODAY, "-o", str(out)]
    )
    assert json.loads(out.read_text(encoding="utf-8"))["today"] == "2026-03-16"


def test_empty_directory(tmp_path: Path) -> None:
    text = runner.invoke(app, ["list", str(tmp_path)])
    assert text.exit_code == 0
    assert "No project files found" in text.stdout
    assert run_json("list", tmp_path) == []
    report = runner.invoke(app, ["weekly-report", str(tmp_path), *TODAY])
    assert "0 open projects" in report.stdout


def test_invalid_files_exit_1_with_file_and_line(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text(
        "name: A\nclient: C\nstatus: active\ndeadline: soon\n"
        "hours_estimated: 1\nhours_spent: 0\n"
    )
    result = runner.invoke(app, ["list", str(tmp_path)])
    assert result.exit_code == 1
    assert "bad.yaml:4: deadline:" in result.stderr
    assert "1 problem found" in result.stderr
    assert result.stdout == ""


def test_several_problems_are_all_reported(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("name: A\n")
    (tmp_path / "b.yaml").write_text("- x\n")
    result = runner.invoke(app, ["list", str(tmp_path)])
    assert result.exit_code == 1
    assert "problems found" in result.stderr


def test_missing_path_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["list", str(tmp_path / "nope")])
    assert result.exit_code == 2
    assert "does not exist" in result.stderr


def test_bad_today_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["list", str(tmp_path), "--today", "tomorrow"])
    assert result.exit_code == 2
    assert "YYYY-MM-DD" in result.stderr


def test_today_can_come_from_the_environment() -> None:
    result = runner.invoke(
        app,
        ["overdue", str(EXAMPLES), "--json"],
        env={"CLIENT_PULSE_TODAY": "2026-03-01"},
    )
    assert json.loads(result.stdout) == []


def test_today_defaults_to_system_date(tmp_path: Path) -> None:
    result = runner.invoke(app, ["list", str(tmp_path)])
    assert result.exit_code == 0


def test_weekly_report_webhook_dry_run_does_not_print_body() -> None:
    result = runner.invoke(
        app,
        [
            "weekly-report",
            str(EXAMPLES),
            *TODAY,
            "--webhook-url",
            "https://hooks.example/inbox",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "dry-run: would POST Markdown" in result.stderr
    assert result.stdout == ""


def test_weekly_report_telegram_requires_both_options() -> None:
    result = runner.invoke(
        app,
        [
            "weekly-report",
            str(EXAMPLES),
            *TODAY,
            "--telegram-token",
            "tok",
        ],
    )
    assert result.exit_code == 2
    assert "both --telegram-token and --telegram-chat-id" in result.stderr


def test_weekly_report_rejects_json_with_webhook() -> None:
    result = runner.invoke(
        app,
        [
            "weekly-report",
            str(EXAMPLES),
            *TODAY,
            "--json",
            "--webhook-url",
            "https://hooks.example/inbox",
        ],
    )
    assert result.exit_code == 2
    assert "--json cannot be combined" in result.stderr


def test_weekly_report_posts_via_injected_poster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from client_pulse.notify import Poster, PostResult

    seen: list[str] = []

    def fake_webhook(
        url: str,
        markdown: str,
        *,
        dry_run: bool = False,
        poster: Poster | None = None,
    ) -> PostResult:
        del poster
        seen.append(url)
        assert "Weekly report" in markdown
        assert not dry_run
        return PostResult(destination=url, status_code=204)

    monkeypatch.setattr("client_pulse.cli.post_webhook", fake_webhook)
    result = runner.invoke(
        app,
        [
            "weekly-report",
            str(EXAMPLES),
            *TODAY,
            "--webhook-url",
            "https://hooks.example/inbox",
        ],
    )
    assert result.exit_code == 0
    assert seen == ["https://hooks.example/inbox"]
    assert "Posted webhook (204)" in result.stderr
    assert result.stdout == ""


def test_weekly_report_telegram_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from client_pulse.notify import Poster, PostResult

    def fake_telegram(
        token: str,
        chat_id: str,
        markdown: str,
        *,
        dry_run: bool = False,
        poster: Poster | None = None,
    ) -> PostResult:
        del token, markdown, poster
        assert dry_run
        return PostResult(
            destination=f"telegram:{chat_id}", status_code=0, dry_run=True
        )

    monkeypatch.setattr("client_pulse.cli.post_telegram", fake_telegram)
    result = runner.invoke(
        app,
        [
            "weekly-report",
            str(EXAMPLES),
            *TODAY,
            "--telegram-token",
            "tok",
            "--telegram-chat-id",
            "99",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "dry-run: would send Telegram" in result.stderr


def test_weekly_report_webhook_failure_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr("client_pulse.cli.post_webhook", boom)
    result = runner.invoke(
        app,
        [
            "weekly-report",
            str(EXAMPLES),
            *TODAY,
            "--webhook-url",
            "https://hooks.example/inbox",
        ],
    )
    assert result.exit_code == 1
    assert "webhook: connection refused" in result.stderr


def test_weekly_report_telegram_posts_and_can_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from client_pulse.notify import Poster, PostResult

    def ok_telegram(
        token: str,
        chat_id: str,
        markdown: str,
        *,
        dry_run: bool = False,
        poster: Poster | None = None,
    ) -> PostResult:
        del token, markdown, dry_run, poster
        return PostResult(destination=f"telegram:{chat_id}", status_code=200)

    monkeypatch.setattr("client_pulse.cli.post_telegram", ok_telegram)
    ok = runner.invoke(
        app,
        [
            "weekly-report",
            str(EXAMPLES),
            *TODAY,
            "--telegram-token",
            "tok",
            "--telegram-chat-id",
            "99",
        ],
    )
    assert ok.exit_code == 0
    assert "Posted Telegram (200)" in ok.stderr

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("chat not found")

    monkeypatch.setattr("client_pulse.cli.post_telegram", boom)
    bad = runner.invoke(
        app,
        [
            "weekly-report",
            str(EXAMPLES),
            *TODAY,
            "--telegram-token",
            "tok",
            "--telegram-chat-id",
            "99",
        ],
    )
    assert bad.exit_code == 1
    assert "telegram: chat not found" in bad.stderr
