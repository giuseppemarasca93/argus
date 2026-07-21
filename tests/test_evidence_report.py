from datetime import datetime, timezone

from argus.database import ArticleStore
from argus.models import Article, Evidence
from argus.report import generate_evidence_report


def test_generates_evidence_report_with_counts_and_article_links(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    item = Article(
        "Climate Source",
        "feed",
        "Battery factory expands",
        "https://example.com/article",
        None,
        None,
        None,
        datetime(2026, 1, 3, tzinfo=timezone.utc).isoformat(),
    )
    store.add(item)
    with store.connect() as connection:
        item_id = connection.execute("SELECT id FROM articles").fetchone()[0]
    evidence = Evidence(item_id, "topic", "Battery", "batteries", 0.8, "rules-v1", "2026-01-03T00:00:00+00:00")
    store.add_evidence_many([evidence])

    output = generate_evidence_report(store, tmp_path / "evidence.md")
    content = output.read_text(encoding="utf-8")

    assert "Evidenze totali: **1**" in content
    assert "### batteries — 1 articoli" in content
    assert "[Battery factory expands](https://example.com/article)" in content
    assert "Climate Source" in content
