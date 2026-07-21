from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Article, Evidence


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    author TEXT,
    published_at TEXT,
    summary TEXT,
    collected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_collected_at ON articles(collected_at);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL CHECK (length(trim(evidence_type)) > 0),
    value TEXT NOT NULL CHECK (length(trim(value)) > 0),
    normalized_value TEXT NOT NULL CHECK (length(trim(normalized_value)) > 0),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    extractor TEXT NOT NULL CHECK (length(trim(extractor)) > 0),
    created_at TEXT NOT NULL,
    rules_fingerprint TEXT,
    UNIQUE (article_id, evidence_type, normalized_value, extractor)
);
CREATE INDEX IF NOT EXISTS idx_evidence_type_value
    ON evidence(evidence_type, normalized_value);

CREATE TABLE IF NOT EXISTS article_extractions (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    extractor TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    evidence_count INTEGER NOT NULL CHECK (evidence_count >= 0),
    rules_fingerprint TEXT,
    PRIMARY KEY (article_id, extractor)
);
"""


class ArticleStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate_02_schema(connection)

    @staticmethod
    def _migrate_02_schema(connection: sqlite3.Connection) -> None:
        evidence_columns = {row["name"] for row in connection.execute("PRAGMA table_info(evidence)")}
        if "rules_fingerprint" not in evidence_columns:
            connection.execute("ALTER TABLE evidence ADD COLUMN rules_fingerprint TEXT")

        extraction_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(article_extractions)")
        }
        if "rules_fingerprint" not in extraction_columns:
            connection.execute("ALTER TABLE article_extractions ADD COLUMN rules_fingerprint TEXT")

    def add_many(self, articles: list[Article]) -> tuple[int, int]:
        """Insert a source batch in one transaction and return (added, duplicates)."""
        if not articles:
            return 0, 0
        with self.connect() as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT OR IGNORE INTO articles (
                    source_name, source_url, title, url, author,
                    published_at, summary, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        article.source_name,
                        article.source_url,
                        article.title,
                        article.url,
                        article.author,
                        article.published_at,
                        article.summary,
                        article.collected_at,
                    )
                    for article in articles
                ],
            )
            added = connection.total_changes - before
        return added, len(articles) - added

    def add(self, article: Article) -> bool:
        added, _ = self.add_many([article])
        return added == 1

    def collected_on(self, day: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT * FROM articles
                WHERE substr(collected_at, 1, 10) = ?
                ORDER BY COALESCE(published_at, collected_at) DESC, id DESC
                """,
                (day,),
            ).fetchall()

    def articles_without_evidence(
        self,
        extractor: str,
        rules_fingerprint: str,
        limit: int | None = None,
    ) -> list[sqlite3.Row]:
        query = """
            SELECT a.* FROM articles a
            LEFT JOIN article_extractions x
                ON x.article_id = a.id
                AND x.extractor = ?
                AND x.rules_fingerprint = ?
            WHERE x.article_id IS NULL
            ORDER BY a.id
        """
        parameters: list[object] = [extractor, rules_fingerprint]
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self.connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def articles(self, limit: int | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM articles ORDER BY id"
        parameters: list[object] = []
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self.connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def add_evidence_many(self, evidence: list[Evidence]) -> tuple[int, int]:
        if not evidence:
            return 0, 0
        with self.connect() as connection:
            added = self._insert_evidence(connection, evidence)
        return added, len(evidence) - added

    def save_extraction(
        self,
        article_id: int,
        extractor: str,
        evidence: list[Evidence],
        processed_at: str,
        rules_fingerprint: str,
        force: bool = False,
    ) -> int:
        """Persist one extraction atomically, replacing only this extractor on force."""
        with self.connect() as connection:
            if force:
                connection.execute(
                    "DELETE FROM evidence WHERE article_id = ? AND extractor = ?",
                    (article_id, extractor),
                )
            else:
                connection.execute(
                    """
                    DELETE FROM evidence
                    WHERE article_id = ? AND extractor = ?
                        AND rules_fingerprint IS NOT ?
                    """,
                    (article_id, extractor, rules_fingerprint),
                )
            added = self._insert_evidence(connection, evidence)
            connection.execute(
                """
                INSERT INTO article_extractions (
                    article_id, extractor, processed_at, evidence_count, rules_fingerprint
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(article_id, extractor) DO UPDATE SET
                    processed_at = excluded.processed_at,
                    evidence_count = excluded.evidence_count,
                    rules_fingerprint = excluded.rules_fingerprint
                """,
                (article_id, extractor, processed_at, len(evidence), rules_fingerprint),
            )
        return added

    @staticmethod
    def _insert_evidence(connection: sqlite3.Connection, evidence: list[Evidence]) -> int:
        before = connection.total_changes
        connection.executemany(
            """
            INSERT OR IGNORE INTO evidence (
                article_id, evidence_type, value, normalized_value,
                confidence, extractor, created_at, rules_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.article_id,
                    item.evidence_type,
                    item.value,
                    item.normalized_value,
                    item.confidence,
                    item.extractor,
                    item.created_at,
                    item.rules_fingerprint,
                )
                for item in evidence
            ],
        )
        return connection.total_changes - before

    def evidence_for_article(self, article_id: int) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM evidence WHERE article_id = ? ORDER BY evidence_type, normalized_value",
                (article_id,),
            ).fetchall()

    def evidence_by_type(self, evidence_type: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT e.*, a.title, a.url, a.source_name
                FROM evidence e JOIN articles a ON a.id = e.article_id
                WHERE e.evidence_type = ?
                ORDER BY e.normalized_value, e.article_id
                """,
                (evidence_type,),
            ).fetchall()

    def all_evidence_with_articles(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT e.*, a.title, a.url, a.source_name
                FROM evidence e JOIN articles a ON a.id = e.article_id
                ORDER BY e.evidence_type, e.normalized_value, e.article_id
                """
            ).fetchall()
