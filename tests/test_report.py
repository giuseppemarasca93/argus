from datetime import date

from argus.database import ArticleStore
from argus.models import Article
from argus.report import generate_report


def test_generates_daily_markdown_report(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    store.add(
        Article(
            "Climate Source",
            "https://example.com/feed",
            "A climate signal",
            "https://example.com/article",
            "Jane Doe",
            "2026-01-03T09:00:00+00:00",
            "Evidence summary.",
            "2026-01-04T10:00:00+00:00",
        )
    )

    output = generate_report(store, tmp_path / "reports", date(2026, 1, 4))

    assert output.name == "2026-01-04.md"
    content = output.read_text(encoding="utf-8")
    assert "Articoli raccolti: **1**" in content
    assert "[A climate signal](https://example.com/article)" in content
    assert "[Climate Source](https://example.com/feed)" in content
    assert "Evidence summary." in content

