"""Admin-only extended pipeline stats — winrate breakdowns + estimated RTP.

GET /api/admin/stats/extended  (header: X-Admin-Token)

Returns:
  - Global winrate at T+5m / T+15m / T+1h / T+24h (over the last 30 days,
    matching the public stats horizon).
  - Avg signed move per trade (estimates the Polymarket "RTP" you'd
    realise if every signal was traded at unit size, ignoring spread).
  - Breakdown by direction (BUY_YES vs BUY_NO).
  - Breakdown by score bucket (65-74 / 75-84 / 85+).
  - Breakdown by category (top 6 by volume).
  - Same X-Admin-Token gate as /api/admin/telegram/*.

The point of the "signed move" estimator: every Polymarket signal trades
a $1 share of a binary outcome. If we BUY_YES at price p_yes and the
price moves to p_yes', our raw PnL per share is (p_yes' - p_yes). For
BUY_NO we trade the complement, so PnL = -(p_yes' - p_yes). Multiplying
by the share count we paid for gives total $ PnL. As a percent of the
stake, that's exactly `move_pct × sign(direction)` and averages directly
into a "return-to-player" estimate. Real spread + fees shave a few
percent off — this is an upper bound, not a realised PnL.
"""

from __future__ import annotations

import hmac
import logging
import math

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])


# ── Statistical helpers ──────────────────────────────────────────────────


def _wilson_ci_95(wins: int, n: int) -> tuple[float | None, float | None]:
    """Wilson score 95% confidence interval for a binomial proportion.

    Returns (low, high) in percentage points, or (None, None) if n == 0.
    The Wilson interval is well-defined at small n and at boundary
    proportions (0% or 100%), unlike the normal approximation.
    """
    if n <= 0:
        return None, None
    z = 1.96
    p = wins / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half = (z * math.sqrt(max(0.0, p * (1.0 - p) / n + (z * z) / (4.0 * n * n)))) / denom
    return round(100.0 * (center - half), 2), round(100.0 * (center + half), 2)


def _reliability(n: int) -> str:
    """Tag bucket size for the consumer.

    - n >= 200  → 'robust'   (Wilson half-width typically ≤ 7pp)
    - n >= 50   → 'moderate' (half-width 7-14pp — usable but noisy)
    - n < 50    → 'anecdotal'(half-width > 14pp — not actionable)
    """
    if n >= 200:
        return "robust"
    if n >= 50:
        return "moderate"
    return "anecdotal"


def _bucket_with_ci(
    n: int, wins: int, ties: int, avg_signed_move: float | None
) -> dict:
    """Standard bucket payload with winrate, CI95, ties, RTP, reliability."""
    resolved = n - ties
    wr = round(100.0 * wins / resolved, 2) if resolved else None
    ci_low, ci_high = _wilson_ci_95(wins, resolved)
    return {
        "n": n,
        "n_resolved": resolved,
        "n_ties": ties,
        "wins": wins,
        "losses": resolved - wins if resolved else 0,
        "winrate_pct": wr,
        "ci_low_95": ci_low,
        "ci_high_95": ci_high,
        "rtp_pct": round(avg_signed_move or 0, 2),
        "reliability": _reliability(resolved),
    }


def _check_admin_token(x_admin_token: str | None) -> None:
    settings = get_settings()
    expected = settings.admin_token or ""
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="admin endpoints not configured — set ADMIN_TOKEN on the server",
        )
    if not hmac.compare_digest(expected, x_admin_token or ""):
        raise HTTPException(status_code=403, detail="forbidden")


@router.get("/extended")
async def admin_stats_extended(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    days: int = 30,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _check_admin_token(x_admin_token)
    if days <= 0 or days > 365:
        raise HTTPException(status_code=400, detail="days must be in [1, 365]")

    # ── Global, all horizons ────────────────────────────────────────────
    # Ties (move = 0) excluded from the denominator (n_*) so winrate is a
    # true binomial proportion. Tracked separately as n_ties_* for audit.
    q_global = text(f"""
        SELECT
          COUNT(*) AS total_signals,
          -- T+5min
          COUNT(*) FILTER (WHERE so.move_t5min_pct IS NOT NULL AND so.move_t5min_pct <> 0) AS n_t5m,
          COUNT(*) FILTER (WHERE so.move_t5min_pct = 0) AS ties_t5m,
          COUNT(*) FILTER (
            WHERE (so.move_t5min_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
               OR (so.move_t5min_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
          ) AS wins_t5m,
          -- T+15min
          COUNT(*) FILTER (WHERE so.move_t15min_pct IS NOT NULL AND so.move_t15min_pct <> 0) AS n_t15m,
          COUNT(*) FILTER (WHERE so.move_t15min_pct = 0) AS ties_t15m,
          COUNT(*) FILTER (
            WHERE (so.move_t15min_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
               OR (so.move_t15min_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
          ) AS wins_t15m,
          -- T+1h
          COUNT(*) FILTER (WHERE so.move_t1h_pct IS NOT NULL AND so.move_t1h_pct <> 0) AS n_t1h,
          COUNT(*) FILTER (WHERE so.move_t1h_pct = 0) AS ties_t1h,
          COUNT(*) FILTER (
            WHERE (so.move_t1h_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
               OR (so.move_t1h_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
          ) AS wins_t1h,
          -- T+24h
          COUNT(*) FILTER (WHERE so.move_t24h_pct IS NOT NULL AND so.move_t24h_pct <> 0) AS n_t24h,
          COUNT(*) FILTER (WHERE so.move_t24h_pct = 0) AS ties_t24h,
          COUNT(*) FILTER (
            WHERE (so.move_t24h_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
               OR (so.move_t24h_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
          ) AS wins_t24h,
          -- Avg signed move (RTP estimator) — ties contribute 0 to the mean
          AVG(CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN  so.move_t1h_pct
                   WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN -so.move_t1h_pct
                   ELSE NULL END)::float AS avg_signed_move_t1h_pct,
          AVG(CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN  so.move_t24h_pct
                   WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN -so.move_t24h_pct
                   ELSE NULL END)::float AS avg_signed_move_t24h_pct
        FROM signals s
        JOIN signal_outcomes so ON so.signal_id = s.id
        WHERE s.created_at > NOW() - INTERVAL '{int(days)} days'
    """)
    g = (await session.execute(q_global)).mappings().one()

    # ── Direction breakdown (T+1h) — ties excluded from denominator ─────
    q_dir = text(f"""
        SELECT
          CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN 'BUY_YES'
               WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN 'BUY_NO'
               ELSE s.direction END AS direction,
          COUNT(*) FILTER (WHERE so.move_t1h_pct IS NOT NULL AND so.move_t1h_pct <> 0) AS n,
          COUNT(*) FILTER (WHERE so.move_t1h_pct = 0) AS ties,
          COUNT(*) FILTER (
            WHERE (so.move_t1h_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
               OR (so.move_t1h_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
          ) AS wins,
          AVG(CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN  so.move_t1h_pct
                   WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN -so.move_t1h_pct
                   ELSE NULL END)::float AS avg_signed_move_pct
        FROM signals s
        JOIN signal_outcomes so ON so.signal_id = s.id
        WHERE s.created_at > NOW() - INTERVAL '{int(days)} days'
          AND so.move_t1h_pct IS NOT NULL
        GROUP BY 1
        ORDER BY n DESC
    """)
    by_dir = [
        {"direction": r["direction"], **_bucket_with_ci(
            n=r["n"] + r["ties"], wins=r["wins"], ties=r["ties"],
            avg_signed_move=r["avg_signed_move_pct"],
        )}
        for r in (await session.execute(q_dir)).mappings().all()
    ]

    # ── Score bucket breakdown (T+1h) — ties excluded from denominator ──
    q_score = text(f"""
        SELECT
          CASE
            WHEN s.signal_score >= 85 THEN '85+'
            WHEN s.signal_score >= 75 THEN '75-84'
            WHEN s.signal_score >= 65 THEN '65-74'
            ELSE '<65'
          END AS bucket,
          COUNT(*) FILTER (WHERE so.move_t1h_pct IS NOT NULL AND so.move_t1h_pct <> 0) AS n,
          COUNT(*) FILTER (WHERE so.move_t1h_pct = 0) AS ties,
          COUNT(*) FILTER (
            WHERE (so.move_t1h_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
               OR (so.move_t1h_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
          ) AS wins,
          AVG(CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN  so.move_t1h_pct
                   WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN -so.move_t1h_pct
                   ELSE NULL END)::float AS avg_signed_move_pct
        FROM signals s
        JOIN signal_outcomes so ON so.signal_id = s.id
        WHERE s.created_at > NOW() - INTERVAL '{int(days)} days'
          AND so.move_t1h_pct IS NOT NULL
        GROUP BY 1
        ORDER BY 1 DESC
    """)
    by_score = [
        {"bucket": r["bucket"], **_bucket_with_ci(
            n=r["n"] + r["ties"], wins=r["wins"], ties=r["ties"],
            avg_signed_move=r["avg_signed_move_pct"],
        )}
        for r in (await session.execute(q_score)).mappings().all()
    ]

    # ── Category breakdown (T+1h) — ties excluded from denominator ──────
    q_cat = text(f"""
        SELECT
          COALESCE(m.category, 'unknown') AS category,
          COUNT(*) FILTER (WHERE so.move_t1h_pct IS NOT NULL AND so.move_t1h_pct <> 0) AS n,
          COUNT(*) FILTER (WHERE so.move_t1h_pct = 0) AS ties,
          COUNT(*) FILTER (
            WHERE (so.move_t1h_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
               OR (so.move_t1h_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
          ) AS wins,
          AVG(CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN  so.move_t1h_pct
                   WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN -so.move_t1h_pct
                   ELSE NULL END)::float AS avg_signed_move_pct
        FROM signals s
        JOIN signal_outcomes so ON so.signal_id = s.id
        JOIN markets m ON m.market_id = s.market_id
        WHERE s.created_at > NOW() - INTERVAL '{int(days)} days'
          AND so.move_t1h_pct IS NOT NULL
        GROUP BY 1
        HAVING COUNT(*) >= 10
        ORDER BY n DESC
        LIMIT 10
    """)
    by_cat = [
        {"category": r["category"], **_bucket_with_ci(
            n=r["n"] + r["ties"], wins=r["wins"], ties=r["ties"],
            avg_signed_move=r["avg_signed_move_pct"],
        )}
        for r in (await session.execute(q_cat)).mappings().all()
    ]

    # Global block with Wilson CI95 + ties on every horizon.
    def _horizon(n_key: str, ties_key: str, wins_key: str) -> dict:
        n = g[n_key]
        ties = g[ties_key]
        wins = g[wins_key]
        wr = round(100.0 * wins / n, 2) if n else None
        ci_low, ci_high = _wilson_ci_95(wins, n)
        return {
            "n_resolved": n,
            "n_ties": ties,
            "wins": wins,
            "losses": (n - wins) if n else 0,
            "winrate_pct": wr,
            "ci_low_95": ci_low,
            "ci_high_95": ci_high,
            "reliability": _reliability(n),
        }

    return {
        "window_days": days,
        "total_signals": g["total_signals"],
        "methodology": {
            "ties_excluded_from_denominator": True,
            "ties_definition": "move_pct == 0 at the given horizon",
            "ci_method": "Wilson score 95%",
            "reliability_thresholds": {"robust": 200, "moderate": 50, "anecdotal": 0},
        },
        "global": {
            "t5min":  _horizon("n_t5m",  "ties_t5m",  "wins_t5m"),
            "t15min": _horizon("n_t15m", "ties_t15m", "wins_t15m"),
            "t1h":    _horizon("n_t1h",  "ties_t1h",  "wins_t1h"),
            "t24h":   _horizon("n_t24h", "ties_t24h", "wins_t24h"),
            # RTP estimator (avg signed move) — ties contribute 0 to mean.
            "rtp_t1h_pct":  round(g["avg_signed_move_t1h_pct"]  or 0, 3),
            "rtp_t24h_pct": round(g["avg_signed_move_t24h_pct"] or 0, 3),
        },
        "by_direction": by_dir,
        "by_score":     by_score,
        "by_category":  by_cat,
    }
