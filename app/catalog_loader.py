from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Tuple
import json

from .config import CATALOGS_DIR


class CatalogNotFound(Exception):
    """Raised when a requested catalog JSON file does not exist."""


def _catalog_files() -> List[Path]:
    """Return all catalog JSON files shipped in the vendor directory."""
    return sorted(CATALOGS_DIR.glob("*.json"))


@lru_cache(maxsize=64)
def load_catalog(name: str) -> List[dict]:
    """
    Load a catalog by its base name (case-insensitive) and cache it in memory.
    Example: name='c_Pais' will load vendor/catalogos_sat_JSON/c_Pais.json
    """
    normalized = name.lower()
    match = next((p for p in _catalog_files() if p.stem.lower() == normalized), None)
    if not match:
        raise CatalogNotFound(f"Catalog '{name}' not found in {CATALOGS_DIR}")

    with open(match, "r", encoding="utf-8") as fh:
        return json.load(fh)


def list_catalogs() -> List[Tuple[str, int]]:
    """Return (catalog_name, entry_count) for each available catalog."""
    result: List[Tuple[str, int]] = []
    for path in _catalog_files():
        try:
            data = load_catalog(path.stem)
            result.append((path.stem, len(data)))
        except Exception:
            # Keep going; if one file is malformed we still list the others.
            result.append((path.stem, 0))
    return result


def filter_rows(
    rows: Iterable[dict],
    query: str | None = None,
    filters: List[Tuple[str, str]] | None = None,
) -> List[dict]:
    """
    Apply a free-text search plus exact-field filters to a list of dictionaries.

    filters must be a list of (field, value) tuples that will be matched
    case-insensitively on equality.
    """
    filtered = list(rows)

    if filters:
        for field, value in filters:
            value_lower = value.lower()
            filtered = [
                row
                for row in filtered
                if str(row.get(field, "")).lower() == value_lower
            ]

    if query:
        needle = query.lower()
        filtered = [
            row
            for row in filtered
            if any(needle in str(val).lower() for val in row.values())
        ]

    return filtered
