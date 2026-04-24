"""Tests for labels_event_market loader + adapter."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


def _write_jsonl(lines: list[dict]) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for line in lines:
        f.write(json.dumps(line) + "\n")
    f.flush()
    return Path(f.name)


def test_load_event_market_labels_parses_strong_and_weak():
    from app.eval.labels_event_market import load_event_market_labels
    path = _write_jsonl([
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match", "source": "human"},
        {"event_id": 1, "market_id": "m2", "verdict": "weak_match", "source": "human"},
        {"event_id": 1, "market_id": "m3", "verdict": "not_related", "source": "human"},
        {"event_id": 2, "market_id": "m1", "verdict": "strong_match", "source": "llm_calibrated"},
    ])
    pairs = load_event_market_labels(path)
    by_eid = {p.query_id: p for p in pairs}
    assert by_eid[1].relevant_ids == frozenset({"m1", "m2"})
    assert by_eid[1].surface == "event_to_market"
    assert by_eid[1].gains == {"m1": 1.0, "m2": 0.5}
    assert by_eid[2].relevant_ids == frozenset({"m1"})
    assert by_eid[2].gains == {"m1": 1.0}


def test_load_event_market_labels_skips_malformed_lines():
    from app.eval.labels_event_market import load_event_market_labels
    path = _write_jsonl([
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match", "source": "human"},
    ])
    with path.open("a") as f:
        f.write("not json at all\n")
    pairs = load_event_market_labels(path)
    assert len(pairs) == 1


def test_load_event_market_labels_missing_file_returns_empty():
    from app.eval.labels_event_market import load_event_market_labels
    pairs = load_event_market_labels(Path("/tmp/does_not_exist_chantier4.jsonl"))
    assert pairs == []


def test_weak_match_gain_is_half():
    """Documented convention: weak = 0.5, strong = 1.0."""
    from app.eval.labels_event_market import WEAK_MATCH_GAIN, STRONG_MATCH_GAIN
    assert WEAK_MATCH_GAIN == 0.5
    assert STRONG_MATCH_GAIN == 1.0


# ═══════════ LLM-judge ═══════════

@pytest.mark.asyncio
async def test_judge_pairs_llm_uses_injected_callable(tmp_path):
    """The judge delegates LLM calls to an injectable callable, for test isolation."""
    from app.eval.labels_event_market import judge_pairs_llm
    captured: list[dict] = []

    async def fake_call(prompt: str) -> list[dict]:
        captured.append({"prompt_len": len(prompt)})
        return [
            {"market_id": "m1", "verdict": "strong_match", "reason": "exact topic"},
            {"market_id": "m2", "verdict": "not_related", "reason": "different topic"},
        ]

    out = await judge_pairs_llm(
        event={
            "event_id": 1,
            "title": "Test event",
            "summary": "",
            "bucket": "politics",
            "entities": ["A"],
        },
        markets=[
            {"market_id": "m1", "question": "Q1", "category": "politics", "end_date": None},
            {"market_id": "m2", "question": "Q2", "category": "sports", "end_date": None},
        ],
        few_shot=[],
        call_fn=fake_call,
        cache_path=tmp_path / "cache.json",
    )
    assert {r["market_id"]: r["verdict"] for r in out} == {
        "m1": "strong_match", "m2": "not_related",
    }
    assert len(captured) == 1  # batched — 1 LLM call for 2 markets


@pytest.mark.asyncio
async def test_judge_pairs_llm_cache_hit_skips_call(tmp_path):
    """A cache hit on the (event_id, market_ids) key bypasses call_fn."""
    from app.eval.labels_event_market import judge_pairs_llm
    cache_path = tmp_path / "cache.json"
    # Prime cache.
    cache_path.write_text(json.dumps({
        "1::m1,m2": [
            {"market_id": "m1", "verdict": "weak_match"},
            {"market_id": "m2", "verdict": "not_related"},
        ]
    }))

    async def fake_call(prompt: str):
        raise AssertionError("should not call LLM on cache hit")

    out = await judge_pairs_llm(
        event={"event_id": 1, "title": "t", "summary": "", "bucket": "politics", "entities": []},
        markets=[
            {"market_id": "m1", "question": "Q1", "category": "politics", "end_date": None},
            {"market_id": "m2", "question": "Q2", "category": "sports", "end_date": None},
        ],
        few_shot=[],
        call_fn=fake_call,
        cache_path=cache_path,
    )
    assert out[0]["verdict"] == "weak_match"


def test_compute_agreement_perfect_match():
    from app.eval.labels_event_market import compute_agreement
    human = [{"event_id": 1, "market_id": "m1", "verdict": "strong_match"}]
    llm = [{"event_id": 1, "market_id": "m1", "verdict": "strong_match"}]
    assert compute_agreement(human=human, llm=llm) == 1.0


def test_compute_agreement_partial():
    from app.eval.labels_event_market import compute_agreement
    human = [
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match"},
        {"event_id": 1, "market_id": "m2", "verdict": "weak_match"},
        {"event_id": 1, "market_id": "m3", "verdict": "not_related"},
    ]
    llm = [
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match"},
        {"event_id": 1, "market_id": "m2", "verdict": "not_related"},  # miss
        {"event_id": 1, "market_id": "m3", "verdict": "not_related"},
    ]
    assert compute_agreement(human=human, llm=llm) == pytest.approx(2 / 3)


def test_compute_agreement_missing_llm_row_counts_as_disagreement():
    from app.eval.labels_event_market import compute_agreement
    human = [
        {"event_id": 1, "market_id": "m1", "verdict": "strong_match"},
        {"event_id": 1, "market_id": "m2", "verdict": "strong_match"},
    ]
    llm = [{"event_id": 1, "market_id": "m1", "verdict": "strong_match"}]
    # 1 of 2 agree.
    assert compute_agreement(human=human, llm=llm) == pytest.approx(0.5)
