import json
import urllib.error
from email.message import Message
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from client_pulse import notify
from client_pulse.notify import (
    TELEGRAM_MAX_CHARS,
    _default_poster,
    post_telegram,
    post_webhook,
    webhook_destination,
)

TOKEN = "123456:ABC-def_GHI"


def no_network(*_args: Any) -> tuple[int, str]:
    raise AssertionError("should not be called")


def test_post_webhook_sends_markdown_body() -> None:
    calls: list[tuple[str, bytes, dict[str, str]]] = []

    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        calls.append((url, body, headers))
        return 204, ""

    result = post_webhook(
        "https://hooks.example/inbox/secret", "# Weekly report\n", poster=poster
    )
    assert result.status_code == 204
    assert not result.dry_run
    assert calls[0][0] == "https://hooks.example/inbox/secret"
    assert calls[0][1] == b"# Weekly report\n"
    assert calls[0][2]["Content-Type"].startswith("text/markdown")


def test_webhook_destination_hides_the_path() -> None:
    result = post_webhook(
        "https://user:pw@hooks.example/inbox/secret?k=v",
        "hi",
        poster=lambda *_: (200, ""),
    )
    assert result.destination == "https://hooks.example"


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example/inbox",
        "file:///etc/passwd",
        "ftp://hooks.example/x",
        "hooks.example/inbox",
        "https:///nohost",
        "",
    ],
)
def test_webhook_rejects_anything_but_https(url: str) -> None:
    with pytest.raises(ValueError, match="https://"):
        post_webhook(url, "hi", poster=no_network)
    with pytest.raises(ValueError, match="https://"):
        post_webhook(url, "hi", dry_run=True)
    with pytest.raises(ValueError, match="https://"):
        webhook_destination(url)


def test_post_webhook_dry_run_skips_network() -> None:
    result = post_webhook(
        "https://hooks.example/inbox", "hi", dry_run=True, poster=no_network
    )
    assert result.dry_run
    assert result.status_code == 0
    assert result.destination == "https://hooks.example"


def test_post_webhook_surfaces_http_errors() -> None:
    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        raise RuntimeError("POST to hooks.example failed with HTTP 500: boom")

    with pytest.raises(RuntimeError, match="HTTP 500"):
        post_webhook("https://hooks.example/inbox", "hi", poster=poster)


def test_post_telegram_json_payload() -> None:
    calls: list[tuple[str, bytes, dict[str, str]]] = []

    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        calls.append((url, body, headers))
        return 200, json.dumps({"ok": True, "result": {}})

    result = post_telegram(TOKEN, "123", "# Hello\n\nworld", poster=poster)
    assert result.status_code == 200
    assert result.destination == "telegram:123"
    assert calls[0][0] == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = json.loads(calls[0][1].decode())
    assert payload == {
        "chat_id": "123",
        "text": "# Hello\n\nworld",
        "disable_web_page_preview": True,
    }


def test_post_telegram_accepts_channel_names_and_negative_group_ids() -> None:
    ok = lambda *_: (200, "{}")  # noqa: E731
    assert post_telegram(TOKEN, "@my_channel", "hi", poster=ok).status_code == 200
    assert post_telegram(TOKEN, "-100123", "hi", poster=ok).status_code == 200


def test_post_telegram_rejects_api_error() -> None:
    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        return 200, json.dumps({"ok": False, "description": "chat not found"})

    with pytest.raises(RuntimeError, match="chat not found"):
        post_telegram(TOKEN, "999", "hi", poster=poster)


def test_post_telegram_truncates_long_messages() -> None:
    captured: dict[str, Any] = {}

    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        captured["payload"] = json.loads(body.decode())
        return 200, json.dumps({"ok": True})

    long_text = "x" * (TELEGRAM_MAX_CHARS + 50)
    post_telegram(TOKEN, "1", long_text, poster=poster)
    text = captured["payload"]["text"]
    assert len(text) == TELEGRAM_MAX_CHARS
    assert text.endswith("…truncated for Telegram (4096 char limit).")


def test_post_telegram_requires_token_and_chat() -> None:
    with pytest.raises(ValueError, match="token is empty"):
        post_telegram("  ", "1", "hi", dry_run=True)
    with pytest.raises(ValueError, match="chat id is empty"):
        post_telegram(TOKEN, "", "hi", dry_run=True)


def test_post_telegram_validation_errors_do_not_echo_the_values() -> None:
    bad_token = "secret token with spaces\n"
    with pytest.raises(ValueError, match="token") as token_error:
        post_telegram(bad_token, "1", "hi", poster=no_network)
    assert "secret" not in str(token_error.value)
    with pytest.raises(ValueError, match="chat id") as chat_error:
        post_telegram(TOKEN, "not a chat", "hi", poster=no_network)
    assert "not a chat" not in str(chat_error.value)


def test_default_poster_success() -> None:
    response = MagicMock()
    response.getcode.return_value = 201
    response.read.return_value = b"ok"
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    with patch.object(notify._opener, "open", return_value=response) as opened:
        status, body = _default_poster(
            "https://hooks.example/inbox",
            b"hi",
            {"Content-Type": "text/markdown"},
        )
    assert status == 201
    assert body == "ok"
    assert opened.call_args.kwargs["timeout"] == notify.TIMEOUT_SECONDS


def test_default_poster_http_error_hides_the_url() -> None:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    err = urllib.error.HTTPError(
        url, 401, "Unauthorized", hdrs=Message(), fp=MagicMock()
    )
    err.read = MagicMock(return_value=b"unauthorized")  # type: ignore[method-assign]
    with (
        patch.object(notify._opener, "open", side_effect=err),
        pytest.raises(RuntimeError, match="HTTP 401") as raised,
    ):
        _default_poster(url, b"hi", {})
    assert TOKEN not in str(raised.value)
    assert str(raised.value).startswith("POST to api.telegram.org failed")


def test_default_poster_url_error_hides_the_url() -> None:
    url = "https://hooks.example/inbox/secret-path"
    with (
        patch.object(
            notify._opener, "open", side_effect=urllib.error.URLError("refused")
        ),
        pytest.raises(RuntimeError, match="refused") as raised,
    ):
        _default_poster(url, b"hi", {})
    assert "secret-path" not in str(raised.value)


@pytest.mark.parametrize("failure", [TimeoutError("timed out"), ConnectionResetError()])
def test_default_poster_reports_timeouts_and_resets(failure: OSError) -> None:
    with (
        patch.object(notify._opener, "open", side_effect=failure),
        pytest.raises(RuntimeError, match="failed"),
    ):
        _default_poster("https://hooks.example/inbox", b"hi", {})


def test_redirects_are_not_followed() -> None:
    handler = notify._NoRedirect()
    request = MagicMock()
    assert (
        handler.redirect_request(request, None, 302, "Found", {}, "http://evil") is None
    )


def test_post_telegram_rejects_non_json_body() -> None:
    def poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        return 200, "not-json"

    with pytest.raises(RuntimeError, match="not JSON"):
        post_telegram(TOKEN, "1", "hi", poster=poster)


def test_post_telegram_dry_run() -> None:
    result = post_telegram(TOKEN, "42", "hi", dry_run=True, poster=no_network)
    assert result.dry_run
    assert result.destination == "telegram:42"
