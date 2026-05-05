"""Tests for `app.processing.ner_extractor.get_ner_extractor` singleton.

Audit follow-up 2026-05-05 — these tests pin behavior introduced in
PR #44. Pre-PR, every `process_article` task instantiated
`NERExtractor()` locally; the lazy `_load_model()` reloaded
`en_core_web_lg` (~750 MB resident) and the previous instance was not
deterministically GC'd. Workers OOM'd in 7-13 minutes of normal
ingestion.

A future contributor who calls `NERExtractor()` directly inside the
hot path (instead of `get_ner_extractor()`) is reintroducing the bug.
The first test fails immediately if the singleton is removed; the
second test pins the lazy-load contract so a "load eagerly" refactor
does not slip in unnoticed (we don't want spaCy materialised at boot
on every worker — `worker-trading` and `worker-outcomes` never NER).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_get_ner_extractor_returns_same_instance():
    """The whole point of the singleton — repeated calls reuse the same
    object so `_nlp` is loaded exactly once per process."""
    # Reset any previous singleton state so a prior test cannot taint this.
    import app.processing.ner_extractor as ner_mod

    ner_mod._ner_singleton = None

    a = ner_mod.get_ner_extractor()
    b = ner_mod.get_ner_extractor()
    c = ner_mod.get_ner_extractor()
    assert a is b is c


def test_get_ner_extractor_does_not_eagerly_load_spacy():
    """The singleton is created on first call but `spacy.load` only
    fires on the *first* `extract_entities` call, not at instantiation.
    Workers that never touch text (`worker-trading`, `worker-outcomes`)
    must not pay the 750 MB cost.
    """
    import app.processing.ner_extractor as ner_mod

    ner_mod._ner_singleton = None

    with patch("app.processing.ner_extractor.spacy") as mock_spacy:
        mock_spacy.load = MagicMock()
        ner = ner_mod.get_ner_extractor()
        # Never called — _nlp is still None right after construction
        assert mock_spacy.load.call_count == 0
        assert ner._nlp is None


def test_get_ner_extractor_loads_spacy_exactly_once_across_calls():
    """`extract_entities()` triggers `_load_model`. Subsequent calls
    must reuse the cached `_nlp` — not call `spacy.load` again. This is
    what keeps RSS flat across thousands of `process_article` invocations.
    """
    import app.processing.ner_extractor as ner_mod

    ner_mod._ner_singleton = None

    fake_nlp = MagicMock()
    fake_doc = MagicMock()
    fake_doc.ents = []
    fake_nlp.return_value = fake_doc

    with patch("app.processing.ner_extractor.spacy") as mock_spacy:
        mock_spacy.load = MagicMock(return_value=fake_nlp)

        ner = ner_mod.get_ner_extractor()
        for _ in range(5):
            ner.extract_entities("Some news text about Hungary.")

        # Exactly ONE load — the rest of the calls reuse `self._nlp`.
        assert mock_spacy.load.call_count == 1
