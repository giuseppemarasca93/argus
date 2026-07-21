from datetime import datetime, timezone

import pytest

from argus.database import ArticleStore
from argus.extraction import RulesExtractor, load_rules, run_extraction
from argus.models import Article, Evidence


RULES = {
    "topic": {
        "electric vehicles": ["electric vehicles", "electric vehicle", "EV"],
        "batteries": ["batteries", "battery", "energy storage"],
    },
    "company": {"tesla": ["Tesla"], "form energy": ["Form Energy"]},
    "technology": {"direct air capture": ["direct air capture", "DAC"]},
    "problem": {"shortage": ["shortage", "shortages"]},
    "market_signal": {
        "funding": ["funding", "raised", "secured funding"],
        "acquisition": ["acquisition", "acquired"],
    },
}
NOW = datetime(2026, 1, 3, tzinfo=timezone.utc)


def article(title="Article", summary=None, url="https://example.com/1"):
    return Article("Source", "feed", title, url, None, None, summary, NOW.isoformat())


def article_id(store, item):
    store.add(item)
    with store.connect() as connection:
        return connection.execute("SELECT id FROM articles WHERE url = ?", (item.url,)).fetchone()[0]


def values(evidence, evidence_type):
    return {item.normalized_value for item in evidence if item.evidence_type == evidence_type}


def test_extracts_topic_from_synonym():
    evidence = RulesExtractor(RULES).extract(1, "EV sales grow", None, NOW)

    assert values(evidence, "topic") == {"electric vehicles"}
    assert next(item for item in evidence if item.evidence_type == "topic").confidence == 0.8


def test_extracts_technology():
    evidence = RulesExtractor(RULES).extract(1, "Direct air capture plant", None, NOW)

    assert values(evidence, "technology") == {"direct air capture"}


def test_normalizes_market_signal():
    evidence = RulesExtractor(RULES).extract(1, "Startup secured funding", None, NOW)

    assert values(evidence, "market_signal") == {"funding"}
    match = next(item for item in evidence if item.evidence_type == "market_signal")
    assert match.value == "secured funding"
    assert match.confidence == 0.8


def test_company_matching_uses_word_boundaries():
    extractor = RulesExtractor(RULES)

    assert values(extractor.extract(1, "Tesla launches a battery", None, NOW), "company") == {"tesla"}
    assert values(extractor.extract(1, "A teslalike prototype", None, NOW), "company") == set()


def test_single_keyword_does_not_match_substring():
    evidence = RulesExtractor(RULES).extract(1, "Every model changed", None, NOW)

    assert values(evidence, "topic") == set()


def test_article_without_summary_is_supported():
    evidence = RulesExtractor(RULES).extract(1, "Battery shortage", None, NOW)

    assert values(evidence, "topic") == {"batteries"}
    assert values(evidence, "problem") == {"shortage"}


def test_evidence_deduplication(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    item_id = article_id(store, article())
    evidence = Evidence(item_id, "topic", "EV", "electric vehicles", 0.8, "rules-v1", NOW.isoformat())

    assert store.add_evidence_many([evidence, evidence]) == (1, 1)


def test_extraction_is_idempotent_including_articles_without_evidence(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    article_id(store, article("Unrelated story"))
    extractor = RulesExtractor(RULES)

    first = run_extraction(store, extractor)
    second = run_extraction(store, extractor)

    assert (first.processed, first.without_evidence) == (1, 1)
    assert (second.processed, second.created) == (0, 0)


def test_force_recalculates_only_current_extractor(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    item_id = article_id(store, article("Tesla raised funding"))
    manual = Evidence(item_id, "company", "Curated Co", "curated co", 1.0, "manual-v1", NOW.isoformat())
    store.add_evidence_many([manual])
    extractor = RulesExtractor(RULES)
    run_extraction(store, extractor)

    result = run_extraction(store, extractor, force=True)
    persisted = store.evidence_for_article(item_id)

    assert result.processed == 1
    assert sum(row["extractor"] == "manual-v1" for row in persisted) == 1
    assert sum(row["extractor"] == "rules-v1" for row in persisted) == 2


def test_limit_restricts_processed_articles(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    article_id(store, article("Tesla", url="https://example.com/1"))
    article_id(store, article("Tesla", url="https://example.com/2"))

    result = run_extraction(store, RulesExtractor(RULES), limit=1)

    assert result.processed == 1
    assert len(store.articles_without_evidence()) == 1


def test_limit_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match="maggiore di zero"):
        run_extraction(ArticleStore(tmp_path / "argus.db"), RulesExtractor(RULES), limit=0)


def test_rules_yaml_validation(tmp_path):
    invalid = tmp_path / "rules.yaml"
    invalid.write_text("topic:\n  solar: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="topic"):
        load_rules(invalid)


def test_rules_yaml_requires_every_evidence_type(tmp_path):
    invalid = tmp_path / "rules.yaml"
    invalid.write_text("topic:\n  solar: [solar]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="company"):
        load_rules(invalid)


def test_loads_repository_rules():
    rules = load_rules("extraction_rules.yaml")

    assert "solar" in rules["topic"]
    assert "funding" in rules["market_signal"]
