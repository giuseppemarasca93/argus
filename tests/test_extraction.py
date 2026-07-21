from copy import deepcopy
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
    "technology": {
        "direct air capture": ["direct air capture", "DAC"],
        "green hydrogen": ["green hydrogen"],
    },
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

    extractor = RulesExtractor(RULES)
    result = run_extraction(store, extractor, limit=1)

    assert result.processed == 1
    assert len(store.articles_without_evidence(extractor.name, extractor.fingerprint)) == 1


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


def test_semantic_rule_change_reprocesses_and_replaces_stale_evidence(tmp_path):
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    item_id = article_id(store, article("Battery factory"))
    old_extractor = RulesExtractor(RULES)
    run_extraction(store, old_extractor)
    manual = Evidence(item_id, "company", "Curated Co", "curated co", 1.0, "manual-v1", NOW.isoformat())
    store.add_evidence_many([manual])

    changed_rules = deepcopy(RULES)
    changed_rules["topic"] = {"energy systems": ["battery"]}
    new_extractor = RulesExtractor(changed_rules)
    result = run_extraction(store, new_extractor)
    topics = [row for row in store.evidence_for_article(item_id) if row["evidence_type"] == "topic"]

    assert old_extractor.fingerprint != new_extractor.fingerprint
    assert result.processed == 1
    assert [row["normalized_value"] for row in topics] == ["energy systems"]
    assert topics[0]["rules_fingerprint"] == new_extractor.fingerprint
    assert any(row["extractor"] == "manual-v1" for row in store.evidence_for_article(item_id))


def test_equivalent_yaml_has_same_fingerprint_and_does_not_reprocess(tmp_path):
    first_yaml = tmp_path / "first.yaml"
    second_yaml = tmp_path / "second.yaml"
    first_yaml.write_text(
        """
topic: {batteries: [battery]}
company: {tesla: [Tesla]}
technology: {green hydrogen: [green hydrogen]}
problem: {shortage: [shortage]}
market_signal: {funding: [raised]}
""",
        encoding="utf-8",
    )
    second_yaml.write_text(
        """
market_signal:
  funding:
    - raised
problem: {shortage: [shortage]}
technology: {green hydrogen: [green hydrogen]}
company: {tesla: [Tesla]}
topic:
  batteries:
    - battery
""",
        encoding="utf-8",
    )
    first = RulesExtractor(load_rules(first_yaml))
    second = RulesExtractor(load_rules(second_yaml))
    store = ArticleStore(tmp_path / "argus.db")
    store.initialize()
    article_id(store, article("Battery factory"))

    assert first.fingerprint == second.fingerprint
    assert run_extraction(store, first).processed == 1
    assert run_extraction(store, second).processed == 0


def test_phrase_does_not_match_across_title_and_summary():
    evidence = RulesExtractor(RULES).extract(1, "Green", "hydrogen project", NOW)

    assert "green hydrogen" not in values(evidence, "technology")


@pytest.mark.parametrize(
    ("title", "summary"),
    [("Green hydrogen project", None), ("Project", "Uses green hydrogen today")],
)
def test_phrase_still_matches_inside_a_single_field(title, summary):
    evidence = RulesExtractor(RULES).extract(1, title, summary, NOW)

    assert "green hydrogen" in values(evidence, "technology")
