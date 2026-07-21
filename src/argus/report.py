from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from .database import ArticleStore


def generate_report(
    store: ArticleStore,
    output_dir: str | Path,
    day: date | None = None,
) -> Path:
    report_day = day or datetime.now(timezone.utc).date()
    articles = store.collected_on(report_day.isoformat())
    output = Path(output_dir) / f"{report_day.isoformat()}.md"
    output.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"# Argus — {report_day.isoformat()}", "", f"Articoli raccolti: **{len(articles)}**", ""]
    if not articles:
        lines.append("Nessun nuovo articolo raccolto in questa data.")
    for article in articles:
        lines.extend(
            [
                f"## [{article['title']}]({article['url']})",
                "",
                f"- Fonte: [{article['source_name']}]({article['source_url']})",
                f"- Autore: {article['author'] or 'Non indicato'}",
                f"- Pubblicato: {article['published_at'] or 'Data non indicata'}",
                f"- Raccolto: {article['collected_at']}",
                "",
            ]
        )
        if article["summary"]:
            lines.extend([article["summary"], ""])

    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output


def generate_evidence_report(store: ArticleStore, output_path: str | Path) -> Path:
    rows = store.all_evidence_with_articles()
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["evidence_type"]][row["normalized_value"]].append(row)

    labels = {
        "topic": "Topics",
        "company": "Companies",
        "technology": "Technologies",
        "problem": "Problems",
        "market_signal": "Market signals",
    }
    lines = ["# Evidence Report", "", f"Evidenze totali: **{len(rows)}**", ""]
    for evidence_type, label in labels.items():
        values = grouped.get(evidence_type, {})
        lines.extend([f"## {label}", "", f"Evidenze: **{sum(len(items) for items in values.values())}**", ""])
        if not values:
            lines.extend(["Nessuna evidenza.", ""])
            continue
        for value, items in sorted(values.items(), key=lambda item: (-len(item[1]), item[0])):
            article_count = len({item["article_id"] for item in items})
            lines.extend([f"### {value} — {article_count} articoli", ""])
            seen: set[int] = set()
            for item in items:
                if item["article_id"] in seen:
                    continue
                seen.add(item["article_id"])
                lines.append(f"- [{item['title']}]({item['url']}) — {item['source_name']}")
                if len(seen) == 5:
                    break
            lines.append("")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output
