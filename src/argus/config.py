from __future__ import annotations

from pathlib import Path

import yaml


def load_sources(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("La configurazione deve contenere una lista 'sources' non vuota")

    result = []
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict) or not source.get("name") or not source.get("url"):
            raise ValueError(f"Fonte #{index} non valida: sono richiesti name e url")
        result.append({"name": str(source["name"]), "url": str(source["url"])})
    return result

