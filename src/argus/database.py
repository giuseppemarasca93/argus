from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Article


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
"""


class ArticleStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def add(self, article: Article) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO articles (
                    source_name, source_url, title, url, author,
                    published_at, summary, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.source_name,
                    article.source_url,
                    article.title,
                    article.url,
                    article.author,
                    article.published_at,
                    article.summary,
                    article.collected_at,
                ),
            )
            return cursor.rowcount == 1

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

