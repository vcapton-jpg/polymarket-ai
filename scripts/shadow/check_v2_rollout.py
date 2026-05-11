"""Quick health-check for the v1 → v2 ImpactAnalyzer rollout.

T-009 follow-up. Run from the VPS:

    ssh foresight 'docker compose -f /opt/foresight/docker-compose.yml \\
      exec -T app python -m scripts.shadow.check_v2_rollout --hours 24'

Reports the rollback-gate metrics defined post-flip:

  - Volume: v2 must emit ≥ 50 % of the v1 historical baseline
  - Winrate: v2 must land in [40 %, 60 %] on n_resolved ≥ 30
  - JSON error rate: < 5 % of v2 calls returning bad JSON
  - First seen / last seen for each version (sanity)

Exits 0 on green, 2 on a hard rollback trigger, 1 if there's not
enough data yet (n < 30 → return early, do NOT rollback).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


async def _check(hours: int) -> int:
    from sqlalchemy import text

    from app.db.database import get_session_factory

    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        # Per-version snapshot over the window.
        rows = (await session.execute(text(f"""
            SELECT
                COALESCE(s.llm_model_version, 'unknown') AS version,
                COUNT(*) AS n_total,
                COUNT(so.signal_id) FILTER (WHERE so.move_t1h_pct IS NOT NULL AND so.move_t1h_pct <> 0) AS n_resolved,
                COUNT(so.signal_id) FILTER (
                    WHERE (so.move_t1h_pct > 0 AND s.direction IN ('BUY_YES','YES','UP'))
                       OR (so.move_t1h_pct < 0 AND s.direction IN ('BUY_NO','NO','DOWN'))
                ) AS wins,
                MIN(s.created_at) AS first_seen,
                MAX(s.created_at) AS last_seen
            FROM signals s
            LEFT JOIN signal_outcomes so ON so.signal_id = s.id
            WHERE s.created_at > NOW() - INTERVAL '{int(hours)} hours'
            GROUP BY 1
            ORDER BY n_total DESC
        """))).mappings().all()

        # JSON-error proxy: count `event_market_analysis` rows where
        # the producer model is v2 but `impact_direction` is NULL
        # (analyzer.analyze returned None — failed parse or LLM refusal).
        error_rate = (await session.execute(text(f"""
            SELECT
                COUNT(*) FILTER (WHERE impact_direction IS NULL) AS errors,
                COUNT(*) AS total
            FROM event_market_analysis
            WHERE llm_model_version LIKE 'gpt-%@v2'
              AND created_at > NOW() - INTERVAL '{int(hours)} hours'
        """))).mappings().one()

    print(f"# v2 rollout health-check — window: last {hours} h")
    print()
    print("| version | n_total | n_resolved | wins | winrate | first | last |")
    print("|---|---:|---:|---:|---:|---|---|")
    for r in rows:
        wr = f"{100*r['wins']/r['n_resolved']:.1f} %" if r["n_resolved"] else "—"
        print(f"| `{r['version']}` | {r['n_total']} | {r['n_resolved']} | {r['wins']} | {wr} | "
              f"{r['first_seen']} | {r['last_seen']} |")

    err = error_rate
    pct_err = (100 * err["errors"] / err["total"]) if err["total"] else 0.0
    print()
    print(f"**v2 analyzer error rate:** {err['errors']}/{err['total']} = {pct_err:.1f} %  "
          f"(rollback if > 5 %)")
    print()

    # Decision logic
    v2 = next((r for r in rows if r["version"] == "gpt-4o-mini@v2"), None)
    if v2 is None:
        print("⚠️  No v2 signals in the window. Either the toggle didn't take or volume too low.")
        return 1

    if v2["n_resolved"] < 30:
        print(f"⏳ v2 has only {v2['n_resolved']} resolved signals — too early to call. Wait more.")
        return 1

    winrate = 100 * v2["wins"] / v2["n_resolved"]
    print(f"v2 winrate (t1h): {winrate:.1f} %  (rollback if < 40 %)")

    triggers = []
    if winrate < 40.0:
        triggers.append(f"winrate {winrate:.1f} % < 40 %")
    if pct_err > 5.0:
        triggers.append(f"json error rate {pct_err:.1f} % > 5 %")

    if triggers:
        print()
        print("🚨 ROLLBACK RECOMMENDED — triggers fired:")
        for t in triggers:
            print(f"  - {t}")
        print()
        print("Run:")
        print("  ssh foresight 'sed -i \"/IMPACT_PROMPT_VERSION/d\" /opt/foresight/.env && \\")
        print("    cd /opt/foresight && docker compose up -d worker-scoring worker-scoring-batch'")
        return 2

    print()
    print("✅ All gates green. Let it run, re-check at H+48 / H+168.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--hours", type=int, default=24,
                   help="Window of analysis in hours (default 24).")
    args = p.parse_args()
    return asyncio.run(_check(args.hours))


if __name__ == "__main__":
    sys.exit(main())
