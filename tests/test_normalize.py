from datetime import datetime, timezone
from time import struct_time

from argus.normalize import normalize_article


def test_normalizes_article_and_strips_html_and_fragment():
    entry = {
        "title": "  Clean <b>energy</b>  ",
        "link": "HTTPS://Example.com/story?a=1#section",
        "author": "Ada Lovelace",
        "published_parsed": struct_time((2026, 1, 2, 12, 30, 0, 4, 2, 0)),
        "summary": "<p>A useful &amp; short summary.</p>",
    }
    article = normalize_article(entry, "Example", "https://example.com/feed", datetime(2026, 1, 3, tzinfo=timezone.utc))

    assert article is not None
    assert article.title == "Clean energy"
    assert article.url == "https://example.com/story?a=1"
    assert article.summary == "A useful & short summary."
    assert article.published_at == "2026-01-02T12:30:00+00:00"
    assert article.collected_at == "2026-01-03T00:00:00+00:00"


def test_rejects_entry_without_url():
    assert normalize_article({"title": "No link"}, "Example", "feed") is None


def test_removes_tracking_parameters_and_sorts_query():
    article = normalize_article(
        {
            "title": "Tracked",
            "link": "HTTPS://EXAMPLE.COM/story?z=2&utm_source=rss&fbclid=abc&a=1#top",
        },
        "Example",
        "feed",
    )

    assert article is not None
    assert article.url == "https://example.com/story?a=1&z=2"


def test_keeps_non_tracking_parameters_including_blank_values():
    article = normalize_article(
        {"title": "Query", "link": "https://example.com/story?page=2&filter=&gclid=x"},
        "Example",
        "feed",
    )

    assert article is not None
    assert article.url == "https://example.com/story?filter=&page=2"
