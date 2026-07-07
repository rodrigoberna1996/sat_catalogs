from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple
import json

from .config import CATALOGS_DIR


class CatalogNotFound(Exception):
    """Raised when a requested catalog JSON file does not exist."""


@lru_cache(maxsize=1)
def _catalog_files() -> List[Path]:
    """Return all catalog JSON files from the vendor directory (cached)."""
    return sorted(CATALOGS_DIR.glob("*.json"))


# Populated by load_catalog() and _fast_count(); avoids re-reading for list_catalogs.
_row_count_cache: Dict[str, int] = {}


@lru_cache(maxsize=64)
def load_catalog(name: str) -> List[dict]:
    """
    Load a catalog by its base name (case-insensitive) and cache it in memory.
    Attaches a pre-lowercased '_search' blob to each row for fast text search.
    Example: name='c_Pais' will load vendor/catalogos_sat_JSON/c_Pais.json
    """
    normalized = name.lower()
    match = next((p for p in _catalog_files() if p.stem.lower() == normalized), None)
    if not match:
        raise CatalogNotFound(f"Catalog '{name}' not found in {CATALOGS_DIR}")

    with open(match, "r", encoding="utf-8") as fh:
        data: List[dict] = json.load(fh)

    # Pre-compute search blob: single lowercased string of all values.
    # This avoids rebuilding strings on every search request (critical for
    # large catalogs like c_ClaveProdServ ~58k rows, c_CodigoPostal ~96k rows).
    for row in data:
        row["_search"] = " ".join(
            str(v).lower() for k, v in row.items() if not k.startswith("_")
        )

    _row_count_cache[normalized] = len(data)
    return data


def _fast_count(path: Path) -> int:
    """Count rows in a JSON catalog without building _search blobs.

    Used by list_catalogs() for catalogs that haven't been fully loaded yet.
    Result is stored in _row_count_cache so subsequent calls are free.
    """
    norm = path.stem.lower()
    if norm in _row_count_cache:
        return _row_count_cache[norm]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            count = len(json.load(fh))
    except Exception:
        count = 0
    _row_count_cache[norm] = count
    return count


@lru_cache(maxsize=256)
def _build_field_index(catalog_name: str, field: str) -> dict:
    """
    Pre-build an inverted index for exact-match filtering on a specific field.
    Maps lowercased field value -> list of row indices.
    Cached per (catalog, field) pair.
    """
    data = load_catalog(catalog_name)
    index: dict = {}
    for i, row in enumerate(data):
        key = str(row.get(field, "")).lower()
        if key not in index:
            index[key] = []
        index[key].append(i)
    return index


def list_catalogs() -> List[Tuple[str, int]]:
    """Return (catalog_name, entry_count) for each available catalog.

    Uses _row_count_cache if the catalog is already loaded; otherwise does a
    lightweight JSON parse (no _search building) so GET /catalogs stays fast
    even on cold start with large catalogs like c_CodigoPostal or c_Colonia.
    """
    return [(path.stem, _fast_count(path)) for path in _catalog_files()]


def filter_rows(
    catalog_name: str,
    query: str | None = None,
    filters: List[Tuple[str, str]] | None = None,
    offset: int = 0,
    limit: int = 200,
) -> Tuple[List[dict], int]:
    """
    Apply exact-field filters and a free-text search to a catalog.

    Returns (page, total_filtered) where:
    - page: rows[offset:offset+limit] after filtering
    - total_filtered: total count of matching rows (before limit/offset)

    Uses pre-built field indexes for exact filters and the cached '_search'
    blob for fast substring matching.
    """
    data = load_catalog(catalog_name)

    # Exact-field filters — use inverted index when filtering a whole catalog.
    if filters:
        # Start with the most selective filter using the index.
        candidate_indices: set | None = None
        for field, value in filters:
            index = _build_field_index(catalog_name, field)
            value_lower = value.lower()
            matched = set(index.get(value_lower, []))
            if candidate_indices is None:
                candidate_indices = matched
            else:
                candidate_indices &= matched

        indices = sorted(candidate_indices or set())
        filtered = [data[i] for i in indices]
    else:
        filtered = data

    # Free-text search using pre-computed '_search' blobs.
    if query:
        needle = query.lower()
        filtered = [row for row in filtered if needle in row.get("_search", "")]

    total_filtered = len(filtered)
    page = filtered[offset : offset + limit]
    return page, total_filtered
