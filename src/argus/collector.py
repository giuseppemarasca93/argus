from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser

from .database import ArticleStore
from .http import HttpClient
from .normalize import normalize_article

LOGGER = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    found: int = 0
    added: int = 0
    skipped: int = 0
    failed_sources: int = 0


def collect(
    sources: list[dict[str, str]],
    store: ArticleStore,
    http_client: HttpClient | None = None,
) -> CollectionResult:
    result = CollectionResult()
    client = http_client or HttpClient()
    store.initialize()

    for source in sources:
        name, url = source["name"], source["url"]
        try:
            LOGGER.info("Raccolta da %s", name)
            feed = feedparser.parse(client.fetch(url))
            if feed.bozo and not feed.entries:
                raise RuntimeError(str(feed.bozo_exception))

            collected_at = datetime.now(timezone.utc)
            articles = []
            for entry in feed.entries:
                result.found += 1
                article = normalize_article(entry, name, url, collected_at)
                if article is None:
                    result.skipped += 1
                    LOGGER.warning("Articolo senza titolo o URL ignorato da %s", name)
                else:
                    articles.append(article)

            added, duplicates = store.add_many(articles)
            result.added += added
            result.skipped += duplicates
            LOGGER.info("%s: %d nuovi, %d duplicati su %d", name, added, duplicates, len(feed.entries))
        except Exception as exc:
            result.failed_sources += 1
            LOGGER.error("Fonte %s non raccolta: %s", name, exc)

    return result
