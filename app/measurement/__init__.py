"""Measurement layer — baselines, variants, metrics.

Importing this module registers the four built-in baselines with the global
VariantRegistry singleton. The signal builder and backfill script rely on
that side-effect — keep this import order stable.
"""

from app.measurement.baselines import (
    baseline_market_price,
    baseline_momentum,
    baseline_news_sentiment,
    baseline_random,
)
from app.measurement.variant_registry import get_registry

_r = get_registry()

# Idempotency: re-import is a no-op (register_baseline raises on duplicate),
# so swallow the error if someone re-imports in a long-running worker.
for _name, _fn in [
    ("baseline_random", baseline_random),
    ("baseline_market_price", baseline_market_price),
    ("baseline_momentum", baseline_momentum),
    ("baseline_news_sentiment", baseline_news_sentiment),
]:
    if _name not in _r.baselines():
        _r.register_baseline(_name, _fn)
