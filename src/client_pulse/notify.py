"""Post a weekly report to a webhook URL or Telegram chat.

Webhook URLs and Telegram tokens are secrets. They are never printed: errors and
status lines name only the host.
"""

from __future__ import annotations

import http.client
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

TELEGRAM_MAX_CHARS = 4096
TIMEOUT_SECONDS = 15
TELEGRAM_HOST = "api.telegram.org"

_TOKEN = re.compile(r"\d+:[A-Za-z0-9_-]+")
_CHAT_ID = re.compile(r"-?\d+|@[A-Za-z0-9_]+")


@dataclass(frozen=True)
class PostResult:
    destination: str
    status_code: int
    dry_run: bool = False


Poster = Callable[[str, bytes, dict[str, str]], tuple[int, str]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # A redirect would resend the report to a host the user did not choose,
    # possibly over plain HTTP.
    def redirect_request(
        self, *args: Any, **kwargs: Any
    ) -> urllib.request.Request | None:
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _host(url: str) -> str:
    return urlsplit(url).hostname or "?"


def _default_poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    # Errors must not contain the URL: for Telegram it holds the bot token.
    host = _host(url)
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.getcode(), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"POST to {host} failed with HTTP {exc.code}: {detail[:500]}"
        ) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST to {host} failed: {exc.reason}") from None
    except (OSError, http.client.HTTPException) as exc:
        # Timeouts and connection resets while reading the response.
        raise RuntimeError(
            f"POST to {host} failed: {exc or type(exc).__name__}"
        ) from None


def webhook_destination(url: str) -> str:
    """Check that the URL is usable and return a printable form without secrets."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("webhook URL must start with https:// and include a host")
    return f"https://{parts.hostname}"


def post_webhook(
    url: str,
    markdown: str,
    *,
    dry_run: bool = False,
    poster: Poster | None = None,
) -> PostResult:
    """POST the Markdown report body to a generic webhook URL."""
    destination = webhook_destination(url)
    if dry_run:
        return PostResult(destination=destination, status_code=0, dry_run=True)
    send = poster or _default_poster
    status, _ = send(
        url,
        markdown.encode("utf-8"),
        {"Content-Type": "text/markdown; charset=utf-8", "User-Agent": "client-pulse"},
    )
    return PostResult(destination=destination, status_code=status)


def _telegram_text(markdown: str) -> str:
    text = markdown.strip()
    if len(text) <= TELEGRAM_MAX_CHARS:
        return text
    suffix = "\n\n…truncated for Telegram (4096 char limit)."
    keep = TELEGRAM_MAX_CHARS - len(suffix)
    return text[:keep].rstrip() + suffix


def post_telegram(
    token: str,
    chat_id: str,
    markdown: str,
    *,
    dry_run: bool = False,
    poster: Poster | None = None,
) -> PostResult:
    """Send the report as plain text via Telegram Bot API sendMessage."""
    token = token.strip()
    chat_id = chat_id.strip()
    if not token:
        raise ValueError("Telegram bot token is empty")
    if not chat_id:
        raise ValueError("Telegram chat id is empty")
    # The messages below deliberately do not repeat the value.
    if not _TOKEN.fullmatch(token):
        raise ValueError("Telegram bot token is not in the form 123456:ABC-def")
    if not _CHAT_ID.fullmatch(chat_id):
        raise ValueError("Telegram chat id must be a number or @channelname")
    destination = f"telegram:{chat_id}"
    if dry_run:
        return PostResult(destination=destination, status_code=0, dry_run=True)
    url = f"https://{TELEGRAM_HOST}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": _telegram_text(markdown),
        "disable_web_page_preview": True,
    }
    send = poster or _default_poster
    status, body = send(
        url,
        json.dumps(payload).encode("utf-8"),
        {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "client-pulse",
        },
    )
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Telegram response was not JSON: {body[:200]}") from exc
    if isinstance(data, dict) and data.get("ok") is False:
        description = data.get("description", "unknown error")
        raise RuntimeError(f"Telegram API error: {description}")
    return PostResult(destination=destination, status_code=status)
