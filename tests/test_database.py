import sqlite3

from argus.database import ArticleStore
from argus.models import Article
from argus.normalize import normalize_article


def test_url_deduplication(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    article = Article("Source", "feed", "Title", "https://example.com/a", None, None, None, "2026-01-03T10:00:00+00:00")

    assert store.add(article) is True
    assert store.add(article) is False
    assert len(store.collected_on("2026-01-03")) == 1


def test_batch_insert_returns_added_and_duplicates(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    first = Article("Source", "feed", "One", "https://example.com/1", None, None, None, "2026-01-03T10:00:00+00:00")
    second = Article("Source", "feed", "Two", "https://example.com/2", None, None, None, "2026-01-03T10:00:00+00:00")

    assert store.add_many([first, second, first]) == (2, 1)
    assert store.add_many([first, second]) == (0, 2)
    assert len(store.collected_on("2026-01-03")) == 2


def test_urls_with_and_without_utm_are_deduplicated_after_normalization(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    tracked = normalize_article({"title": "One", "link": "https://example.com/a?utm_source=rss"}, "Source", "feed")
    clean = normalize_article({"title": "One", "link": "https://example.com/a"}, "Source", "feed")

    assert tracked is not None and clean is not None
    assert store.add_many([tracked, clean]) == (1, 1)


def test_initialize_migrates_existing_articles_database(tmp_path):
    database = tmp_path / "existing.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL,
                source_url TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
                author TEXT, published_at TEXT, summary TEXT, collected_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO articles (source_name, source_url, title, url, collected_at) VALUES (?, ?, ?, ?, ?)",
            ("Source", "feed", "Existing", "https://example.com", "2026-01-03T00:00:00+00:00"),
        )

    store = ArticleStore(database)
    store.initialize()

    assert len(store.articles()) == 1
    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 0
