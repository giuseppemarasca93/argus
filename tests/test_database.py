from argus.database import ArticleStore
from argus.models import Article


def test_url_deduplication(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    article = Article("Source", "feed", "Title", "https://example.com/a", None, None, None, "2026-01-03T10:00:00+00:00")

    assert store.add(article) is True
    assert store.add(article) is False
    assert len(store.collected_on("2026-01-03")) == 1

