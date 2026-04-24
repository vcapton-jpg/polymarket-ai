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


# ══════════════════════════════════════════════════════════════════════
# LLM-judge runner (chantier #4 task 10)
# ══════════════════════════════════════════════════════════════════════
import hashlib
from typing import Awaitable, Callable

JUDGE_MODEL = "gpt-4o-mini"
# Rough: one batched call = ~1200 input + 400 output tokens on gpt-4o-mini
# → ~$0.00024 per call at current prices. Used only for the local budget check.
_APPROX_COST_PER_BATCH_USD = 0.0003


def _judge_cache_key(event_id: int, market_ids: list[str]) -> str:
    mids = ",".join(sorted(market_ids))
    return f"{event_id}::{mids}"


def _build_judge_prompt(
    event: dict, markets: list[dict], few_shot: list[dict]
) -> str:
    """Prompt the LLM to return a strict JSON array."""
    lines = [
        "You judge relevance between a news event and a set of prediction markets.",
        "For each market, output one of: strong_match, weak_match, not_related.",
        "",
        "Definitions:",
        "  strong_match: the market directly bets on this event's core claim.",
        "  weak_match:  the market is in the same topic but does not directly resolve on the event.",
        "  not_related: the market has no meaningful topical overlap.",
        "",
    ]
    if few_shot:
        lines.append("# Examples")
        for ex in few_shot:
            lines.append(f"event: {ex['event_title']}")
            lines.append(f"market: {ex['market_question']}")
            lines.append(f"verdict: {ex['verdict']}")
            lines.append("")
    lines.append("# Now judge the following.")
    lines.append(f"event_id: {event['event_id']}")
    lines.append(f"event_title: {event['title']}")
    lines.append(f"event_bucket: {event.get('bucket')}")
    lines.append(f"event_entities: {event.get('entities', [])}")
    if event.get("summary"):
        lines.append(f"event_summary: {event['summary'][:800]}")
    lines.append("")
    lines.append("markets:")
    for m in markets:
        lines.append(
            f"  - market_id: {m['market_id']}"
            f" | question: {m.get('question')}"
            f" | category: {m.get('category')}"
            f" | end_date: {m.get('end_date')}"
        )
    lines.append("")
    lines.append(
        'Return a JSON array with one object per market: '
        '[{"market_id": ..., "verdict": ..., "reason": ...}, ...]. '
        "No surrounding prose."
    )
    return "\n".join(lines)


async def judge_pairs_llm(
    *,
    event: dict,
    markets: list[dict],
    few_shot: list[dict],
    call_fn: Callable[[str], Awaitable[list[dict]]],
    cache_path: Path,
) -> list[dict]:
    """Judge each (event, market) pair. Batched: one LLM call per event.

    `call_fn` takes a prompt string and returns the parsed JSON array. Tests
    inject a fake; production uses `openai_judge_call` below.

    Cache: keyed by (event_id, sorted market_ids). Cache file survives runs.
    """
    cache: dict[str, list[dict]] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            logger.warning("judge cache corrupt at %s, starting fresh", cache_path)
            cache = {}

    market_ids = [m["market_id"] for m in markets]
    key = _judge_cache_key(int(event["event_id"]), market_ids)
    if key in cache:
        return cache[key]

    prompt = _build_judge_prompt(event, markets, few_shot)
    raw = await call_fn(prompt)

    # Keep only fields we document.
    normalized = [
        {"market_id": r.get("market_id"), "verdict": r.get("verdict"), "reason": r.get("reason", "")}
        for r in raw if r.get("market_id") in set(market_ids)
    ]
    cache[key] = normalized
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))
    return normalized


async def openai_judge_call(prompt: str) -> list[dict]:
    """Production call_fn for judge_pairs_llm. Uses OpenAI structured output."""
    from openai import AsyncOpenAI
    from app.core.config import get_settings
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM judge returned non-JSON: %s", raw[:200])
        return []
    # The response_format=json_object forces a dict; we wrap either a bare
    # list or {"judgments": [...]}. Accept both.
    if isinstance(parsed, dict) and "judgments" in parsed:
        return list(parsed["judgments"])
    if isinstance(parsed, list):
        return parsed
    return []


def compute_agreement(*, human: list[dict], llm: list[dict]) -> float:
    """Fraction of (event_id, market_id) pairs where human and LLM verdicts match.

    Pairs present in human but missing from llm count as disagreements.
    Pairs present in llm but missing from human are ignored.
    """
    if not human:
        return 0.0
    llm_map = {(int(r["event_id"]), str(r["market_id"])): r["verdict"] for r in llm}
    agree = 0
    for h in human:
        key = (int(h["event_id"]), str(h["market_id"]))
        if llm_map.get(key) == h["verdict"]:
            agree += 1
    return agree / len(human)
