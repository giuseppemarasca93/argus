from __future__ import annotations

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
