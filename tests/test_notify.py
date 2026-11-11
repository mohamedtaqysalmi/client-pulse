import json
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from client_pulse.notify import (
    TELEGRAM_MAX_CHARS,
    _default_poster,
    post_telegram,
    post_webhook,
)


def test_post_webhook_sends_markdown_body() -> None:
    calls: list[tuple[str, bytes, dict[str, str]]] = []

    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        calls.append((url, body, headers))
        return 204, ""

    result = post_webhook(
        "https://hooks.example/inbox", "# Weekly report\n", poster=poster
    )
    assert result.status_code == 204
    assert result.destination == "https://hooks.example/inbox"
    assert not result.dry_run
    assert calls[0][0] == "https://hooks.example/inbox"
    assert calls[0][1] == b"# Weekly report\n"
    assert calls[0][2]["Content-Type"].startswith("text/markdown")


def test_post_webhook_dry_run_skips_network() -> None:
    def poster(*_args: Any) -> tuple[int, str]:
        raise AssertionError("should not be called")

    result = post_webhook(
        "https://hooks.example/inbox", "hi", dry_run=True, poster=poster
    )
    assert result.dry_run
    assert result.status_code == 0


def test_post_webhook_surfaces_http_errors() -> None:
    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        raise RuntimeError(f"POST {url} failed with HTTP 500: boom")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        post_webhook("https://hooks.example/inbox", "hi", poster=poster)


def test_post_telegram_json_payload() -> None:
    calls: list[tuple[str, bytes, dict[str, str]]] = []

    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        calls.append((url, body, headers))
        return 200, json.dumps({"ok": True, "result": {}})

    result = post_telegram("tok", "123", "# Hello\n\nworld", poster=poster)
    assert result.status_code == 200
    assert result.destination == "telegram:123"
    assert calls[0][0] == "https://api.telegram.org/bottok/sendMessage"
    payload = json.loads(calls[0][1].decode())
    assert payload == {
        "chat_id": "123",
        "text": "# Hello\n\nworld",
        "disable_web_page_preview": True,
    }


def test_post_telegram_rejects_api_error() -> None:
    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        return 200, json.dumps({"ok": False, "description": "chat not found"})

    with pytest.raises(RuntimeError, match="chat not found"):
        post_telegram("tok", "999", "hi", poster=poster)


def test_post_telegram_truncates_long_messages() -> None:
    captured: dict[str, Any] = {}

    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        captured["payload"] = json.loads(body.decode())
        return 200, json.dumps({"ok": True})

    long_text = "x" * (TELEGRAM_MAX_CHARS + 50)
    post_telegram("tok", "1", long_text, poster=poster)
    text = captured["payload"]["text"]
    assert len(text) == TELEGRAM_MAX_CHARS
    assert text.endswith("…truncated for Telegram (4096 char limit).")


def test_post_telegram_requires_token_and_chat() -> None:
    with pytest.raises(ValueError, match="token"):
        post_telegram("  ", "1", "hi", dry_run=True)
    with pytest.raises(ValueError, match="chat"):
        post_telegram("tok", "", "hi", dry_run=True)


def test_default_poster_success() -> None:
    response = MagicMock()
    response.getcode.return_value = 201
    response.read.return_value = b"ok"
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        status, body = _default_poster(
            "https://hooks.example/inbox",
            b"hi",
            {"Content-Type": "text/markdown"},
        )
    assert status == 201
    assert body == "ok"
    assert urlopen.called


def test_default_poster_http_error() -> None:
    from email.message import Message

    headers = Message()
    err = urllib.error.HTTPError(
        "https://hooks.example/inbox", 500, "boom", hdrs=headers, fp=MagicMock()
    )
    err.read = MagicMock(return_value=b"server down")  # type: ignore[method-assign]
    with (
        patch("urllib.request.urlopen", side_effect=err),
        pytest.raises(RuntimeError, match="HTTP 500"),
    ):
        _default_poster("https://hooks.example/inbox", b"hi", {})


def test_default_poster_url_error() -> None:
    with (
        patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timed out"),
        ),
        pytest.raises(RuntimeError, match="timed out"),
    ):
        _default_poster("https://hooks.example/inbox", b"hi", {})


def test_post_telegram_rejects_non_json_body() -> None:
    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        return 200, "not-json"

    with pytest.raises(RuntimeError, match="not JSON"):
        post_telegram("tok", "1", "hi", poster=poster)


def test_post_telegram_dry_run() -> None:
    def poster(*_args: Any) -> tuple[int, str]:
        raise AssertionError("should not be called")

    result = post_telegram("tok", "42", "hi", dry_run=True, poster=poster)
    assert result.dry_run
    assert result.destination == "telegram:42"
