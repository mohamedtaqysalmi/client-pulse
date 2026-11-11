"""The Pages site shows real output. These tests fail if it drifts from the code."""

import html
import json
import re
from pathlib import Path

from typer.testing import CliRunner

from client_pulse.cli import app
from client_pulse.loader import OPTIONAL, REQUIRED
from client_pulse.models import Status

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ARGS = ["examples/projects", "--today", "2026-03-16"]
runner = CliRunner()


def cli(command: str) -> str:
    result = runner.invoke(app, [command, str(ROOT / ARGS[0]), *ARGS[1:]])
    assert result.exit_code == 0, result.stderr
    return result.stdout


def pre_text(page: str, element_id: str) -> str:
    match = re.search(rf'<pre id="{element_id}"><code>(.*?)</code></pre>', page, re.S)
    assert match, element_id
    return html.unescape(match.group(1))


def test_sample_report_file_matches_the_command() -> None:
    text = (SITE / "sample-report.md").read_text(encoding="utf-8")
    assert text == cli("weekly-report")


def test_page_embeds_the_real_command_output() -> None:
    page = (SITE / "index.html").read_text(encoding="utf-8")
    assert pre_text(page, "report-md") + "\n" == cli("weekly-report")
    for command, element in [
        ("list", "out-list"),
        ("overdue", "out-overdue"),
        ("blockers", "out-blockers"),
    ]:
        expected = f"$ client-pulse {command} {' '.join(ARGS)}\n" + cli(command)
        assert pre_text(page, element) + "\n" == expected


def test_schema_json_matches_the_loader() -> None:
    schema = json.loads((SITE / "schema.json").read_text(encoding="utf-8"))
    assert set(schema["properties"]) == set(REQUIRED + OPTIONAL)
    assert set(schema["required"]) == set(REQUIRED)
    assert schema["properties"]["status"]["enum"] == [s.value for s in Status]
    assert schema["additionalProperties"] is False


def test_page_schema_table_lists_every_field() -> None:
    page = (SITE / "index.html").read_text(encoding="utf-8")
    fields = re.findall(r"<tr>\s*<td><code>(\w+)</code></td>", page)
    assert fields == [*REQUIRED, *OPTIONAL]


def test_page_example_yaml_is_a_valid_project() -> None:
    page = (SITE / "index.html").read_text(encoding="utf-8")
    assert pre_text(page, "yaml-example") + "\n" == (
        ROOT / "examples" / "projects" / "acme-site.yaml"
    ).read_text(encoding="utf-8")
