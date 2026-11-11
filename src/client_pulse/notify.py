"""Post a weekly report to a webhook URL or Telegram chat."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

TELEGRAM_MAX_CHARS = 4096


@dataclass(frozen=True)
class PostResult:
    destination: str
    status_code: int
    dry_run: bool = False


Poster = Callable[[str, bytes, dict[str, str]], tuple[int, str]]


def _default_poster(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.getcode(), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"POST {url} failed with HTTP {exc.code}: {detail[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {url} failed: {exc.reason}") from exc


def post_webhook(
    url: str,
    markdown: str,
    *,
    dry_run: bool = False,
    poster: Poster | None = None,
) -> PostResult:
    """POST the Markdown report body to a generic webhook URL."""
    if dry_run:
        return PostResult(destination=url, status_code=0, dry_run=True)
    send = poster or _default_poster
    status, _ = send(
        url,
        markdown.encode("utf-8"),
        {"Content-Type": "text/markdown; charset=utf-8", "User-Agent": "client-pulse"},
    )
    return PostResult(destination=url, status_code=status)


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
    if not token.strip():
        raise ValueError("Telegram bot token is empty")
    if not chat_id.strip():
        raise ValueError("Telegram chat id is empty")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": _telegram_text(markdown),
        "disable_web_page_preview": True,
    }
    if dry_run:
        return PostResult(
            destination=f"telegram:{chat_id}", status_code=0, dry_run=True
        )
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
    return PostResult(destination=f"telegram:{chat_id}", status_code=status)
