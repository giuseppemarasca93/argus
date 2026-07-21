from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    source_name: str
    source_url: str
    title: str
    url: str
    author: str | None
    published_at: str | None
    summary: str | None
    collected_at: str

