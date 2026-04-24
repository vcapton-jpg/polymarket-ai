"""Text composers that produce embedding-ready strings.

Each surface (news / market / event) has a v1 composer — a bit-exact
re-implementation of the existing inline f-string — and a v2 composer with
the chantier-#3 improvements. Selecting which composer's output to embed
is the caller's responsibility (prod writes v1 + v2 in parallel; see
task 15).

All composers return a `ComposedText` carrying the text plus a
`composition_version` string persisted in `<entity>.embedding_v2_composition`
so we can always trace back which rule produced which vector.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ComposedText:
    text: str
    composition_version: str


# ══════════════════════════════════════════════════════════════════════
# News
# ══════════════════════════════════════════════════════════════════════


def compose_news_v1(title: str, clean_text: str) -> ComposedText:
    """Bit-exact re-implementation of tasks_pipeline.py:98.

        embed_text = f"{raw_title}. {clean_text[:1500]}"
    """
    text = f"{title}. {clean_text[:1500]}"
    return ComposedText(text=text, composition_version="news_v1_title_trunc")


def compose_news_v2(title: str, clean_text: str) -> ComposedText:
    """A1 — lead-paragraph + tail-paragraph composition, capped at 1800 chars.

    Splits the body on blank lines, keeps paragraphs ≥ 80 chars. If none
    survive, falls back to v1-style byte truncation at 1500 chars.
    """
    paragraphs = [p.strip() for p in (clean_text or "").split("\n\n") if len(p.strip()) >= 80]
    if not paragraphs:
        body = (clean_text or "")[:1500]
    elif len(paragraphs) == 1:
        body = paragraphs[0][:1500]
    else:
        lead = paragraphs[0][:1200]
        tail = paragraphs[-1][:400]
        body = f"{lead}\n\n{tail}"
    text = f"{(title or '').strip()}. {body}"[:1800]
    return ComposedText(text=text, composition_version="news_v2_lead_tail")


# ══════════════════════════════════════════════════════════════════════
# Market
# ══════════════════════════════════════════════════════════════════════


def compose_market_v1(mkt: dict) -> ComposedText:
    """Bit-exact re-implementation of tasks_ingestion._build_retrieval_text."""
    from app.workers.tasks_ingestion import _BOILERPLATE_RE

    question = mkt.get("question") or ""
    desc_raw = mkt.get("description") or ""
    desc_clean = _BOILERPLATE_RE.sub("", desc_raw).strip()
    desc_clean = re.sub(r"\n{2,}", "\n", desc_clean)[:400]
    tags_str = " ".join(mkt.get("tags") or [])
    text = f"{question}. {desc_clean} {tags_str}".strip()
    return ComposedText(text=text, composition_version="market_v1_q_desc_tags")


# ══════════════════════════════════════════════════════════════════════
# Event
# ══════════════════════════════════════════════════════════════════════


def compose_market_v2(mkt: dict) -> ComposedText:
    """A3 — v1 plus an explicit [category: X] marker between description and tags."""
    from app.workers.tasks_ingestion import _BOILERPLATE_RE

    question = (mkt.get("question") or "").strip()
    desc_raw = mkt.get("description") or ""
    desc_clean = _BOILERPLATE_RE.sub("", desc_raw).strip()
    desc_clean = re.sub(r"\n{2,}", "\n", desc_clean)[:400]
    category = (mkt.get("category") or "").strip()
    tags_str = " ".join(mkt.get("tags") or [])

    parts = [f"{question}."]
    if desc_clean:
        parts.append(desc_clean)
    if category:
        parts.append(f"[category: {category}]")
    if tags_str:
        parts.append(tags_str)
    text = " ".join(p for p in parts if p).strip()
    return ComposedText(text=text, composition_version="market_v2_with_category")


# ══════════════════════════════════════════════════════════════════════
# Event
# ══════════════════════════════════════════════════════════════════════


def compose_event_v1(title: str, summary: str, entities: list[str]) -> ComposedText:
    """Canonical v1 shape, matching app/event_engine/event_builder.py:56-58:

        retrieval_parts = [event_title, event_summary[:300]]
        retrieval_parts.extend(key_entities[:5])
        event_retrieval_text = " ".join(retrieval_parts)

    Note: tasks_pipeline.py previously used a slightly divergent formula
    (`event_summary[:400]`). The v1 composer unifies on [:300] — this is the
    canonical value going forward. If any call-site depends on the :400
    behavior behaviorally, wrap it in a comment and migrate explicitly.
    """
    parts = [title, (summary or "")[:300]]
    parts.extend((entities or [])[:5])
    text = " ".join(p for p in parts if p)
    return ComposedText(text=text, composition_version="event_v1_title_summary_entities")
