"""Ground-truth labels for the event→market retrieval surface (chantier #4).

Two-stage pipeline:
  1. Human seed CLI (scripts/label_event_market_seed.py) writes a JSONL file
     where each line is {"event_id", "market_id", "verdict", "source": "human"}.
  2. LLM-judge runner (this module, task 10) writes additional lines with
     "source": "llm_calibrated".

Readers of the merged file get a list of `EventMarketPair` objects compatible
with the chantier #3 runner via the `.query_id` / `.relevant_ids` / `.surface`
attributes. `gains` is extra metadata used by graded-nDCG computation (task 13).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

STRONG_MATCH_GAIN: float = 1.0
WEAK_MATCH_GAIN: float = 0.5


@dataclass(frozen=True)
class EventMarketPair:
    query_id: int
    relevant_ids: frozenset[str]
    gains: dict[str, float]      # market_id → gain (0.5 or 1.0)
    source: str                  # "human" | "llm_calibrated"
    surface: str = "event_to_market"


def _verdict_to_gain(verdict: str) -> float | None:
    if verdict == "strong_match":
        return STRONG_MATCH_GAIN
    if verdict == "weak_match":
        return WEAK_MATCH_GAIN
    return None  # not_related or unknown → skip


def load_event_market_labels(path: Path) -> list[EventMarketPair]:
    """Parse a JSONL file of labelled event→market pairs.

    Malformed lines are skipped with a warning. Missing files return [].
    Lines with the same `event_id` are merged into a single EventMarketPair;
    `source` is the *noblest* among lines (human > llm_calibrated).
    """
    if not path.exists():
        logger.info("load_event_market_labels: file not found %s", path)
        return []

    accum: dict[int, dict[str, tuple[float, str]]] = {}

    nobility = {"human": 2, "llm_calibrated": 1}

    with path.open() as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("load_event_market_labels: skip malformed line %d", lineno)
                continue
            try:
                eid = int(row["event_id"])
                mid = str(row["market_id"])
                verdict = str(row["verdict"])
                src = str(row.get("source", "human"))
            except (KeyError, TypeError, ValueError):
                logger.warning("load_event_market_labels: skip line %d (missing fields)", lineno)
                continue
            gain = _verdict_to_gain(verdict)
            if gain is None:
                continue
            src_level = nobility.get(src, 0)
            bucket = accum.setdefault(eid, {})
            existing = bucket.get(mid)
            if existing is None or nobility.get(existing[1], 0) < src_level:
                bucket[mid] = (gain, src)

    pairs: list[EventMarketPair] = []
    for eid, market_map in accum.items():
        max_src = max(market_map.values(), key=lambda t: nobility.get(t[1], 0))[1]
        pairs.append(EventMarketPair(
            query_id=eid,
            relevant_ids=frozenset(market_map.keys()),
            gains={mid: g for mid, (g, _src) in market_map.items()},
            source=max_src,
        ))
    return pairs
