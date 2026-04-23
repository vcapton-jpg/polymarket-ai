import pytest

from app.measurement.variant_registry import (
    VariantPrediction,
    VariantRegistry,
    get_registry,
)


def _noop(_ctx):
    return VariantPrediction(direction=None, probability=None)


def test_register_baseline_and_enumerate():
    reg = VariantRegistry()
    reg.register_baseline("baseline_x", _noop)
    assert list(reg.baselines().keys()) == ["baseline_x"]
    assert reg.baselines()["baseline_x"] is _noop


def test_register_baseline_is_idempotent_duplicate_name_raises():
    reg = VariantRegistry()
    reg.register_baseline("baseline_x", _noop)
    with pytest.raises(ValueError, match="already registered"):
        reg.register_baseline("baseline_x", _noop)


def test_register_shadow_separate_from_baselines():
    reg = VariantRegistry()
    reg.register_baseline("b", _noop)
    reg.register_shadow("s", _noop)
    assert "b" not in reg.shadows()
    assert "s" not in reg.baselines()


def test_get_registry_returns_singleton():
    assert get_registry() is get_registry()
