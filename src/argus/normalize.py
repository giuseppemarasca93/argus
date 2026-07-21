from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Article


TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _text(value: object) -> str | None:
    if not value:
        return None
    parser = _TextExtractor()
    parser.feed(str(value))
    cleaned = re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip()
    return cleaned or None


def _url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    query = [
        (key, query_value)
        for key, query_value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMETERS
    ]
    query.sort()
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query, doseq=True), "")
    )


def _published_at(entry: object) -> str | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime.fromtimestamp(calendar.timegm(parsed), timezone.utc).isoformat()
    return None


def normalize_article(
    entry: object,
    source_name: str,
    source_url: str,
    collected_at: datetime | None = None,
) -> Article | None:
    """Convert a feedparser entry into the small canonical article model."""
    url = _url(entry.get("link"))
    title = _text(entry.get("title"))
    if not url or not title:
        return None

    now = collected_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    return Article(
        source_name=source_name,
        source_url=source_url,
        title=title,
        url=url,
        author=_text(entry.get("author")),
        published_at=_published_at(entry),
        summary=_text(entry.get("summary") or entry.get("description")),
        collected_at=now.astimezone(timezone.utc).isoformat(),
    )
