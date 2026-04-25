"""Audit follow-up: `bucket_classifier.py` declares `"other"` in BUCKETS
but never trains a single example for it. Result: the model cannot
predict "other" — only the `except` fallback in `predict()` can return
it. Topic-irrelevant content (celebrity gossip, weather, lifestyle)
gets force-assigned to one of the 6 real topics, polluting downstream
clustering.

Fix: add explicit "other" training examples covering the irrelevant
content the pipeline actually sees, so the classifier can honestly
return "other" instead of guessing.
"""

from __future__ import annotations

from app.processing.bucket_classifier import (
    BUCKETS,
    DEFAULT_TRAINING_DATA,
    create_bucket_classifier,
)


def test_other_label_has_training_examples():
    """Every label declared in BUCKETS must have training data."""
    for label in BUCKETS:
        assert label in DEFAULT_TRAINING_DATA, (
            f"BUCKETS declares {label!r} but DEFAULT_TRAINING_DATA has "
            "no examples — model can never predict it."
        )
        assert len(DEFAULT_TRAINING_DATA[label]) >= 5, (
            f"{label!r} has fewer than 5 training examples — too sparse "
            "for the model to converge on it."
        )


def test_classifier_predicts_other_for_clearly_irrelevant_text():
    """A piece of celebrity-gossip / lifestyle text must not be mis-classified
    into politics/economics/etc."""
    clf = create_bucket_classifier()
    clf.train()
    text = (
        "celebrity wedding paparazzi photos red carpet gown designer "
        "hollywood star couple breakup tabloid drama instagram post"
    )
    pred = clf.predict(text)
    assert pred == "other", (
        f"clearly-irrelevant celebrity text predicted as {pred!r} — "
        "the 'other' bucket isn't pulling its weight."
    )


def test_classifier_still_predicts_real_topic_for_topic_text():
    """Adding 'other' training data must not regress the existing topics."""
    clf = create_bucket_classifier()
    clf.train()
    pred = clf.predict(
        "federal reserve raises interest rates by 25 basis points fomc meeting"
    )
    assert pred == "economics", f"economics text mis-predicted as {pred!r}"
    pred2 = clf.predict(
        "bitcoin price surge cryptocurrency rally all time high btc"
    )
    assert pred2 == "crypto", f"crypto text mis-predicted as {pred2!r}"
