"""Retrieval package. Prefer `hybrid_search_markets` (the dispatcher) over
importing v1 / v2 directly."""

from app.retrieval.ranking_variant import hybrid_search_markets_dispatch as hybrid_search_markets

__all__ = ["hybrid_search_markets"]
