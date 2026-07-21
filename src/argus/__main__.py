from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from .collector import collect
from .config import load_sources
from .database import ArticleStore
from .extraction import RulesExtractor, load_rules, run_extraction
from .http import HttpClient
from .report import generate_evidence_report, generate_report


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="python -m argus", description="Argus climate-tech collector")
    cli.add_argument("--database", default="data/argus.db", help="Percorso del database SQLite")
    commands = cli.add_subparsers(dest="command", required=True)

    collect_command = commands.add_parser("collect", help="Raccoglie gli articoli dai feed")
    collect_command.add_argument("--sources", default="sources.yaml", help="File YAML delle fonti")
    collect_command.add_argument("--timeout", type=float, default=15, help="Timeout HTTP in secondi")

    report_command = commands.add_parser("report", help="Genera il report Markdown giornaliero")
    report_command.add_argument("--date", type=date.fromisoformat, help="Data YYYY-MM-DD (default: oggi)")
    report_command.add_argument("--output", default="reports", help="Directory dei report")

    extract_command = commands.add_parser("extract", help="Estrae evidenze deterministiche")
    extract_command.add_argument("--rules", default="extraction_rules.yaml", help="File YAML delle regole")
    extract_command.add_argument("--force", action="store_true", help="Ricalcola le evidenze rules-v1")
    extract_command.add_argument("--limit", type=int, help="Numero massimo di articoli")

    evidence_report = commands.add_parser("evidence-report", help="Genera il report delle evidenze")
    evidence_report.add_argument("--output", default="reports/evidence.md", help="File Markdown di output")
    return cli


def main() -> int:
    args = parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    store = ArticleStore(Path(args.database))

    try:
        if args.command == "collect":
            sources = load_sources(args.sources)
            result = collect(sources, store, HttpClient(timeout=args.timeout))
            logging.info(
                "Completato: %d nuovi, %d ignorati, %d fonti fallite",
                result.added,
                result.skipped,
                result.failed_sources,
            )
            return 1 if result.failed_sources == len(sources) else 0

        if args.command == "report":
            store.initialize()
            output = generate_report(store, args.output, args.date)
            logging.info("Report generato: %s", output)
            return 0

        if args.command == "extract":
            extractor = RulesExtractor(load_rules(args.rules))
            result = run_extraction(store, extractor, args.force, args.limit)
            logging.info(
                "Estrazione completata: %d processati, %d evidenze create, "
                "%d senza evidenze, %d errori",
                result.processed,
                result.created,
                result.without_evidence,
                result.errors,
            )
            return 1 if result.errors else 0

        store.initialize()
        output = generate_evidence_report(store, args.output)
        logging.info("Evidence report generato: %s", output)
        return 0
    except (OSError, ValueError) as exc:
        logging.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
