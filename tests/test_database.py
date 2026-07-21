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


def test_initialize_migrates_milestone_02_evidence_schema(tmp_path):
    database = tmp_path / "milestone-02.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL,
                source_url TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
                author TEXT, published_at TEXT, summary TEXT, collected_at TEXT NOT NULL
            );
            CREATE TABLE evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                evidence_type TEXT NOT NULL, value TEXT NOT NULL, normalized_value TEXT NOT NULL,
                confidence REAL NOT NULL, extractor TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE (article_id, evidence_type, normalized_value, extractor)
            );
            CREATE TABLE article_extractions (
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                extractor TEXT NOT NULL, processed_at TEXT NOT NULL, evidence_count INTEGER NOT NULL,
                PRIMARY KEY (article_id, extractor)
            );
            INSERT INTO articles (
                source_name, source_url, title, url, collected_at
            ) VALUES ('Source', 'feed', 'Battery factory', 'https://example.com', '2026-01-03');
            INSERT INTO evidence (
                article_id, evidence_type, value, normalized_value, confidence, extractor, created_at
            ) VALUES
                (1, 'topic', 'Battery', 'batteries', 0.8, 'rules-v1', '2026-01-03'),
                (1, 'company', 'Curated Co', 'curated co', 1.0, 'manual-v1', '2026-01-03');
            INSERT INTO article_extractions (
                article_id, extractor, processed_at, evidence_count
            ) VALUES (1, 'rules-v1', '2026-01-03', 1);
            """
        )

    store = ArticleStore(database)
    store.initialize()

    with store.connect() as connection:
        evidence_columns = {row["name"] for row in connection.execute("PRAGMA table_info(evidence)")}
        extraction_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(article_extractions)")
        }
        assert "rules_fingerprint" in evidence_columns
        assert "rules_fingerprint" in extraction_columns
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 2
