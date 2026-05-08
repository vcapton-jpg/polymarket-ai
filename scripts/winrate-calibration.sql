-- Calibration tables: winrate broken down by signal/market features.
--
-- Inputs:
--   * signals.signal_score, direction, cosine_score, source_tier_mix
--   * signals.market_price_at_signal (base for "extreme price" buckets)
--   * markets.category, markets.volume_24h, markets.liquidity
--   * signal_outcomes.move_t1h_pct (label — 1 h horizon, 558 resolved as of 2026-05-08)
--
-- Win definition matches `app/signal/direction_eval.py`:
--   YES/BUY_YES/UP  + price up   → win
--   NO/BUY_NO/DOWN  + price down → win
--
-- Run:
--   docker compose exec -T db psql -U postgres -d signal < scripts/winrate-calibration.sql

\echo '=== 1. Score-bucket calibration (1h horizon) ==='
SELECT
  CASE
    WHEN s.signal_score >= 85 THEN '85+'
    WHEN s.signal_score >= 80 THEN '80-84'
    WHEN s.signal_score >= 75 THEN '75-79'
    WHEN s.signal_score >= 70 THEN '70-74'
    WHEN s.signal_score >= 65 THEN '65-69'
    ELSE                              '< 65'
  END AS score_bucket,
  count(*) AS n,
  count(*) FILTER (WHERE
    (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
    OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
  ) AS wins,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
      OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
    ) / NULLIF(count(*), 0),
    1
  ) AS winrate_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE o.move_t1h_pct IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

\echo ''
\echo '=== 2. Category breakdown (1h horizon, only buckets with n>=20) ==='
SELECT
  m.category,
  count(*) AS n,
  count(*) FILTER (WHERE
    (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
    OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
  ) AS wins,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
      OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
    ) / NULLIF(count(*), 0),
    1
  ) AS winrate_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
JOIN markets m         ON m.market_id = s.market_id
WHERE o.move_t1h_pct IS NOT NULL
GROUP BY m.category
HAVING count(*) >= 20
ORDER BY winrate_pct DESC NULLS LAST;

\echo ''
\echo '=== 3. Direction × score bucket (1h horizon) ==='
SELECT
  s.direction,
  CASE
    WHEN s.signal_score >= 80 THEN '80+'
    WHEN s.signal_score >= 70 THEN '70-79'
    ELSE                              '65-69'
  END AS score_bucket,
  count(*) AS n,
  count(*) FILTER (WHERE
    (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
    OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
  ) AS wins,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
      OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
    ) / NULLIF(count(*), 0),
    1
  ) AS winrate_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE o.move_t1h_pct IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2 DESC;

\echo ''
\echo '=== 4. Cosine-score bucket (semantic match strength) ==='
SELECT
  CASE
    WHEN s.cosine_score >= 0.70 THEN '0.70+'
    WHEN s.cosine_score >= 0.60 THEN '0.60-0.69'
    WHEN s.cosine_score >= 0.55 THEN '0.55-0.59'
    WHEN s.cosine_score >= 0.50 THEN '0.50-0.54'
    ELSE                              '< 0.50'
  END AS cosine_bucket,
  count(*) AS n,
  count(*) FILTER (WHERE
    (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
    OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
  ) AS wins,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
      OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
    ) / NULLIF(count(*), 0),
    1
  ) AS winrate_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE o.move_t1h_pct IS NOT NULL
  AND s.cosine_score IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

\echo ''
\echo '=== 5. Market volume bucket (24h volume at signal time, USD) ==='
SELECT
  CASE
    WHEN m.volume_24h >= 50000 THEN '50k+'
    WHEN m.volume_24h >= 10000 THEN '10k-50k'
    WHEN m.volume_24h >=  2000 THEN '2k-10k'
    WHEN m.volume_24h >=   500 THEN '500-2k'
    ELSE                            '< 500'
  END AS volume_bucket,
  count(*) AS n,
  count(*) FILTER (WHERE
    (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
    OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
  ) AS wins,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
      OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
    ) / NULLIF(count(*), 0),
    1
  ) AS winrate_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
JOIN markets m         ON m.market_id = s.market_id
WHERE o.move_t1h_pct IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

\echo ''
\echo '=== 6. Price extreme bucket (was the YES price already extreme?) ==='
SELECT
  CASE
    WHEN s.market_price_at_signal >= 0.90 THEN '0.90+'
    WHEN s.market_price_at_signal >= 0.70 THEN '0.70-0.89'
    WHEN s.market_price_at_signal >= 0.30 THEN '0.30-0.69 (mid)'
    WHEN s.market_price_at_signal >= 0.10 THEN '0.10-0.29'
    ELSE                                       '< 0.10'
  END AS price_bucket,
  count(*) AS n,
  count(*) FILTER (WHERE
    (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
    OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
  ) AS wins,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
      OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
    ) / NULLIF(count(*), 0),
    1
  ) AS winrate_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE o.move_t1h_pct IS NOT NULL
  AND s.market_price_at_signal IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

\echo ''
\echo '=== 7. Confidence label (LLM self-assessment) ==='
SELECT
  COALESCE(s.confidence_label, '(null)') AS confidence,
  count(*) AS n,
  count(*) FILTER (WHERE
    (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
    OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
  ) AS wins,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
      OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
    ) / NULLIF(count(*), 0),
    1
  ) AS winrate_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE o.move_t1h_pct IS NOT NULL
GROUP BY 1
ORDER BY n DESC;

\echo ''
\echo '=== 8. Baseline reminders ==='
SELECT
  count(*) AS total_resolved_1h,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction IN ('YES','BUY_YES','UP')   AND o.move_t1h_pct > 0)
      OR (s.direction IN ('NO','BUY_NO','DOWN') AND o.move_t1h_pct < 0)
    ) / NULLIF(count(*), 0),
    1
  ) AS overall_winrate_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE o.move_t1h_pct IS NOT NULL;
