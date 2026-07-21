from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .database import ArticleStore
from .models import Evidence


EXTRACTOR = "rules-v1"
EVIDENCE_TYPES = ("topic", "company", "technology", "problem", "market_signal")
LOGGER = logging.getLogger(__name__)


def normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def load_rules(path: str | Path) -> dict[str, dict[str, list[str]]]:
    try:
        with Path(path).open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML delle regole non valido: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Le regole devono essere una mappa YAML")

    rules: dict[str, dict[str, list[str]]] = {}
    for evidence_type in EVIDENCE_TYPES:
        values = data.get(evidence_type)
        if not isinstance(values, dict) or not values:
            raise ValueError(f"La sezione '{evidence_type}' deve essere una mappa non vuota")
        rules[evidence_type] = {}
        for canonical, terms in values.items():
            normalized = normalize_value(str(canonical))
            if not normalized or not isinstance(terms, list) or not terms:
                raise ValueError(f"Regola non valida in '{evidence_type}': {canonical}")
            cleaned_terms = [str(term).strip() for term in terms if str(term).strip()]
            if len(cleaned_terms) != len(terms):
                raise ValueError(f"Sinonimi non validi per '{canonical}'")
            rules[evidence_type][normalized] = cleaned_terms
    return rules


class RulesExtractor:
    name = EXTRACTOR

    def __init__(self, rules: dict[str, dict[str, list[str]]]) -> None:
        self.rules = rules

    def extract(
        self,
        article_id: int,
        title: str,
        summary: str | None,
        created_at: datetime | None = None,
    ) -> list[Evidence]:
        text = " ".join(part for part in (title, summary) if part)
        timestamp = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        found: list[Evidence] = []

        for evidence_type in EVIDENCE_TYPES:
            for canonical, terms in self.rules[evidence_type].items():
                match = self._first_match(text, terms)
                if match is None:
                    continue
                matched_text, configured_term = match
                found.append(
                    Evidence(
                        article_id=article_id,
                        evidence_type=evidence_type,
                        value=matched_text,
                        normalized_value=canonical,
                        confidence=self._confidence(canonical, configured_term),
                        extractor=self.name,
                        created_at=timestamp,
                    )
                )
        return found

    @staticmethod
    def _first_match(text: str, terms: list[str]) -> tuple[str, str] | None:
        matches = []
        for term in terms:
            match = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE)
            if match:
                matches.append((match.start(), -len(match.group(0)), match.group(0), term))
        if not matches:
            return None
        _, _, matched_text, configured_term = min(matches)
        return matched_text, configured_term

    @staticmethod
    def _confidence(canonical: str, term: str) -> float:
        if normalize_value(term) != canonical:
            return 0.8
        return 0.9 if " " in canonical or "-" in canonical else 0.7


@dataclass
class ExtractionResult:
    processed: int = 0
    created: int = 0
    without_evidence: int = 0
    errors: int = 0


def run_extraction(
    store: ArticleStore,
    extractor: RulesExtractor,
    force: bool = False,
    limit: int | None = None,
) -> ExtractionResult:
    if limit is not None and limit <= 0:
        raise ValueError("--limit deve essere maggiore di zero")
    store.initialize()
    articles = store.articles(limit) if force else store.articles_without_evidence(extractor.name, limit)
    result = ExtractionResult()

    for article in articles:
        try:
            processed_at = datetime.now(timezone.utc)
            evidence = extractor.extract(article["id"], article["title"], article["summary"], processed_at)
            result.created += store.save_extraction(
                article["id"], extractor.name, evidence, processed_at.isoformat(), force
            )
            result.processed += 1
            if not evidence:
                result.without_evidence += 1
        except Exception as exc:
            result.errors += 1
            LOGGER.error("Articolo %s non processato: %s", article["id"], exc)
    return result
