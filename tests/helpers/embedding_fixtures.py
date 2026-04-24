"""Shared fixtures for eval harness + composer tests."""

from __future__ import annotations


def make_toy_embedding(dim: int = 1536, axis: int = 0, magnitude: float = 1.0) -> list[float]:
    """Deterministic embedding pointing along one axis. Used by tests that
    need embeddings but don't care about real semantics."""
    v = [0.0] * dim
    if 0 <= axis < dim:
        v[axis] = magnitude
    return v
