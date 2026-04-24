"""Offline evaluation harness for embedding quality.

Modules:
- metrics    — pure retrieval/clustering metrics (no I/O).
- labels     — eval-pair loaders (DB heuristic, downstream P&L, LLM judge).
- runner     — orchestration: load pairs, score against candidates, aggregate.

Nothing in this package writes to production DB. All read-only. The CLI
lives at scripts/eval_embeddings.py.
"""
