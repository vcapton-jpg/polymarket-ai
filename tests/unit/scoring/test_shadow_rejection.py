"""Pin the dispatch contract for shadow-rejection capture.

The function `_log_shadow_rejection` in `app.signal.signal_builder`
is the only entry-point that writes to the shadow tables. We need to
guarantee:

  1. **Setting gate** — when `enable_shadow_capture=False` no Celery
     task is dispatched (zero overhead, zero DB write).
  2. **Argument shape** — when enabled, the kwargs passed to
     `record_shadow_signal.apply_async` match what the worker expects
     and the rejection_reason / market_price are propagated unmodified.
  3. **Failure-isolation** — a broker-down exception inside the
     dispatch must not bubble up to the caller (the rejection path in
     signal_builder must remain ASCII-art simple).

DB-touching paths (the worker tasks themselves) are exercised in the
integration suite; here we only pin the in-process dispatch logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.config import get_settings
from app.signal.signal_builder import _log_shadow_rejection


def _call_with_defaults(**overrides):
    """Helper: invoke `_log_shadow_rejection` with sane defaults and
    let each test override only what it asserts on."""
    kwargs = dict(
        event_id=1234,
        market_id="0xMARKET",
        direction="BUY_NO",
        market_price=0.15,
        rejection_reason="t001_low_price",
        llm_analysis={"llm_model_version": "gpt-4o-mini@v2"},
    )
    kwargs.update(overrides)
    _log_shadow_rejection(**kwargs)


def test_no_dispatch_when_setting_disabled(monkeypatch):
    """The default prod posture: setting OFF → zero dispatch."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_shadow_capture", False)

    with patch("app.workers.tasks_shadow.record_shadow_signal") as mock_task:
        _call_with_defaults()
        mock_task.apply_async.assert_not_called()


def test_dispatch_when_setting_enabled_t001(monkeypatch):
    """Setting ON + T-001 reject → one apply_async, kwargs propagated."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_shadow_capture", True)

    mock_task = MagicMock()
    with patch(
        "app.workers.tasks_shadow.record_shadow_signal", mock_task
    ):
        _call_with_defaults(
            rejection_reason="t001_low_price",
            market_price=0.18,
        )

    mock_task.apply_async.assert_called_once()
    _, kwargs = mock_task.apply_async.call_args
    payload = kwargs["kwargs"]
    assert payload["event_id"] == 1234
    assert payload["market_id"] == "0xMARKET"
    assert payload["direction"] == "BUY_NO"
    assert payload["market_price_at_signal"] == 0.18
    assert payload["rejection_reason"] == "t001_low_price"
    assert payload["llm_model_version"] == "gpt-4o-mini@v2"
    # signal_score is unknown at the rejection site — must be None.
    assert payload["signal_score"] is None
    assert kwargs["queue"] == "default"


def test_dispatch_when_setting_enabled_t013(monkeypatch):
    """Same shape works for the T-013 high-price rejection reason."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_shadow_capture", True)

    mock_task = MagicMock()
    with patch(
        "app.workers.tasks_shadow.record_shadow_signal", mock_task
    ):
        _call_with_defaults(
            rejection_reason="t013_high_price",
            market_price=0.82,
        )

    mock_task.apply_async.assert_called_once()
    _, kwargs = mock_task.apply_async.call_args
    payload = kwargs["kwargs"]
    assert payload["rejection_reason"] == "t013_high_price"
    assert payload["market_price_at_signal"] == 0.82


def test_dispatch_handles_missing_llm_model_version(monkeypatch):
    """Legacy LLM-analysis dicts may not carry `llm_model_version` yet
    (pre-PR #101). Must default to None, not crash."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_shadow_capture", True)

    mock_task = MagicMock()
    with patch(
        "app.workers.tasks_shadow.record_shadow_signal", mock_task
    ):
        _call_with_defaults(llm_analysis={"impact_strength": 0.7})  # no version

    _, kwargs = mock_task.apply_async.call_args
    payload = kwargs["kwargs"]
    assert payload["llm_model_version"] is None


def test_dispatch_handles_none_llm_analysis(monkeypatch):
    """If llm_analysis is None (defensive — caller should always pass
    a dict, but...), the dispatch still proceeds with model_version=None."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_shadow_capture", True)

    mock_task = MagicMock()
    with patch(
        "app.workers.tasks_shadow.record_shadow_signal", mock_task
    ):
        _call_with_defaults(llm_analysis=None)

    _, kwargs = mock_task.apply_async.call_args
    assert kwargs["kwargs"]["llm_model_version"] is None


def test_broker_failure_is_swallowed(monkeypatch, caplog):
    """The dispatch is BEST-EFFORT — a broker outage must not abort
    the rejection path. Caller (signal_builder) returns None regardless."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_shadow_capture", True)

    mock_task = MagicMock()
    mock_task.apply_async.side_effect = RuntimeError("broker down")

    with patch("app.workers.tasks_shadow.record_shadow_signal", mock_task):
        # Must NOT raise.
        with caplog.at_level("WARNING"):
            _call_with_defaults()

    # The warning is logged so an operator can spot a broken broker.
    assert any("shadow rejection dispatch failed" in rec.message for rec in caplog.records)


def test_market_price_is_coerced_to_float(monkeypatch):
    """`market_price` arrives as a numeric type from SQLAlchemy
    (`Decimal` from `NUMERIC(6,4)`). The dispatched payload must
    serialize cleanly through Celery (i.e. be a plain Python float)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_shadow_capture", True)

    from decimal import Decimal

    mock_task = MagicMock()
    with patch("app.workers.tasks_shadow.record_shadow_signal", mock_task):
        _call_with_defaults(market_price=Decimal("0.2500"))

    _, kwargs = mock_task.apply_async.call_args
    val = kwargs["kwargs"]["market_price_at_signal"]
    assert isinstance(val, float)
    assert val == 0.25
