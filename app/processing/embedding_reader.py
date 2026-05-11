"""Read-side helpers that route embedding access through a per-surface feature
flag, so consumers transparently read either `embedding` (v1) or `embedding_v2`
(v2) depending on the active variant for that surface.

Two flavors:
- get_active_embedding(row, surface): for ORM consumers that hold a row object.
- active_column_name(surface): for raw-SQL consumers that templatize column
  names into a query string. Only returns the literal "embedding" or
  "embedding_v2"; whitelist-enforced, safe against injection.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings

_VALID_SURFACES = ("news", "market", "event")


def _variant_for_surface(surface: str) -> str:
    if surface not in _VALID_SURFACES:
        raise ValueError(
            f"Unknown surface {surface!r}; must be one of {_VALID_SURFACES}"
        )
    settings = get_settings()
    attr = f"embeddings_variant_{surface}"
    v = getattr(settings, attr, "v1")
    return v if v in ("v1", "v2") else "v1"


def get_active_embedding(row: Any, surface: str) -> list[float] | None:
    """Return the embedding column matching the active variant for `surface`."""
    variant = _variant_for_surface(surface)
    if variant == "v1":
        return row.embedding
    return row.embedding_v2


def active_column_name(surface: str) -> str:
    """Return the literal column name ('embedding' or 'embedding_v2') for the
    active variant. Safe to interpolate into raw SQL — the return value is
    whitelist-enforced."""
    variant = _variant_for_surface(surface)
    return "embedding" if variant == "v1" else "embedding_v2"
