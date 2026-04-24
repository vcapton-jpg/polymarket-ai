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
