from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from .collector import collect
from .config import load_sources
from .database import ArticleStore
from .report import generate_report


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="python -m argus", description="Argus climate-tech collector")
    cli.add_argument("--database", default="data/argus.db", help="Percorso del database SQLite")
    commands = cli.add_subparsers(dest="command", required=True)

    collect_command = commands.add_parser("collect", help="Raccoglie gli articoli dai feed")
    collect_command.add_argument("--sources", default="sources.yaml", help="File YAML delle fonti")

    report_command = commands.add_parser("report", help="Genera il report Markdown giornaliero")
    report_command.add_argument("--date", type=date.fromisoformat, help="Data YYYY-MM-DD (default: oggi)")
    report_command.add_argument("--output", default="reports", help="Directory dei report")
    return cli


def main() -> int:
    args = parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    store = ArticleStore(Path(args.database))

    try:
        if args.command == "collect":
            sources = load_sources(args.sources)
            result = collect(sources, store)
            logging.info(
                "Completato: %d nuovi, %d ignorati, %d fonti fallite",
                result.added,
                result.skipped,
                result.failed_sources,
            )
            return 1 if result.failed_sources == len(sources) else 0

        store.initialize()
        output = generate_report(store, args.output, args.date)
        logging.info("Report generato: %s", output)
        return 0
    except (OSError, ValueError) as exc:
        logging.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
