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

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])


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
    q_global = text(f"""
        SELECT
          COUNT(*) FILTER (WHERE so.direction_correct IS NOT NULL) AS resolved,
          COUNT(*) FILTER (WHERE so.direction_correct = true) AS wins,
          COUNT(*) FILTER (WHERE so.move_t5min_pct  IS NOT NULL) AS n_t5m,
          COUNT(*) FILTER (WHERE so.move_t5min_pct  > 0 AND s.direction IN ('BUY_YES','YES','UP'))
            + COUNT(*) FILTER (WHERE so.move_t5min_pct  < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
                                                       AS wins_t5m,
          COUNT(*) FILTER (WHERE so.move_t15min_pct IS NOT NULL) AS n_t15m,
          COUNT(*) FILTER (WHERE so.move_t15min_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
            + COUNT(*) FILTER (WHERE so.move_t15min_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
                                                       AS wins_t15m,
          COUNT(*) FILTER (WHERE so.move_t1h_pct    IS NOT NULL) AS n_t1h,
          COUNT(*) FILTER (WHERE so.move_t1h_pct    > 0 AND s.direction IN ('BUY_YES','YES','UP'))
            + COUNT(*) FILTER (WHERE so.move_t1h_pct    < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
                                                       AS wins_t1h,
          COUNT(*) FILTER (WHERE so.move_t24h_pct   IS NOT NULL) AS n_t24h,
          COUNT(*) FILTER (WHERE so.move_t24h_pct   > 0 AND s.direction IN ('BUY_YES','YES','UP'))
            + COUNT(*) FILTER (WHERE so.move_t24h_pct   < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
                                                       AS wins_t24h,
          AVG(CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN  so.move_t1h_pct
                   WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN -so.move_t1h_pct
                   ELSE NULL END)::float AS avg_signed_move_t1h_pct,
          AVG(CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN  so.move_t24h_pct
                   WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN -so.move_t24h_pct
                   ELSE NULL END)::float AS avg_signed_move_t24h_pct,
          COUNT(*) AS total_signals
        FROM signals s
        JOIN signal_outcomes so ON so.signal_id = s.id
        WHERE s.created_at > NOW() - INTERVAL '{int(days)} days'
    """)
    g = (await session.execute(q_global)).mappings().one()

    def winrate(wins, n):
        return round(100.0 * wins / n, 2) if n else None

    # ── Direction breakdown (T+1h) ──────────────────────────────────────
    q_dir = text(f"""
        SELECT
          CASE WHEN s.direction IN ('BUY_YES','YES','UP') THEN 'BUY_YES'
               WHEN s.direction IN ('BUY_NO','NO','DOWN') THEN 'BUY_NO'
               ELSE s.direction END AS direction,
          COUNT(*) AS n,
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
        {
            "direction": r["direction"],
            "n": r["n"],
            "wins": r["wins"],
            "winrate_pct": winrate(r["wins"], r["n"]),
            "avg_signed_move_pct": round(r["avg_signed_move_pct"] or 0, 2),
        }
        for r in (await session.execute(q_dir)).mappings().all()
    ]

    # ── Score bucket breakdown (T+1h) ───────────────────────────────────
    q_score = text(f"""
        SELECT
          CASE
            WHEN s.signal_score >= 85 THEN '85+'
            WHEN s.signal_score >= 75 THEN '75-84'
            WHEN s.signal_score >= 65 THEN '65-74'
            ELSE '<65'
          END AS bucket,
          COUNT(*) AS n,
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
        {
            "bucket": r["bucket"],
            "n": r["n"],
            "wins": r["wins"],
            "winrate_pct": winrate(r["wins"], r["n"]),
            "avg_signed_move_pct": round(r["avg_signed_move_pct"] or 0, 2),
        }
        for r in (await session.execute(q_score)).mappings().all()
    ]

    # ── Category breakdown (T+1h) ───────────────────────────────────────
    q_cat = text(f"""
        SELECT
          COALESCE(m.category, 'unknown') AS category,
          COUNT(*) AS n,
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
        {
            "category": r["category"],
            "n": r["n"],
            "wins": r["wins"],
            "winrate_pct": winrate(r["wins"], r["n"]),
            "avg_signed_move_pct": round(r["avg_signed_move_pct"] or 0, 2),
        }
        for r in (await session.execute(q_cat)).mappings().all()
    ]

    return {
        "window_days": days,
        "total_signals": g["total_signals"],
        "global": {
            "winrate_t5m_pct":  winrate(g["wins_t5m"],  g["n_t5m"]),
            "n_t5m":            g["n_t5m"],
            "winrate_t15m_pct": winrate(g["wins_t15m"], g["n_t15m"]),
            "n_t15m":           g["n_t15m"],
            "winrate_t1h_pct":  winrate(g["wins_t1h"],  g["n_t1h"]),
            "n_t1h":            g["n_t1h"],
            "winrate_t24h_pct": winrate(g["wins_t24h"], g["n_t24h"]),
            "n_t24h":           g["n_t24h"],
            # avg signed move: the "RTP estimator". Positive = profitable
            # before fees/spread, negative = bleeding alpha.
            "avg_signed_move_t1h_pct":  round(g["avg_signed_move_t1h_pct"]  or 0, 3),
            "avg_signed_move_t24h_pct": round(g["avg_signed_move_t24h_pct"] or 0, 3),
        },
        "by_direction":  by_dir,
        "by_score":      by_score,
        "by_category":   by_cat,
    }
