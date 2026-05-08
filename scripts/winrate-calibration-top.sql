-- Just sections 1-3 of winrate-calibration.sql, so the output fits on one
-- screen of the Hetzner web console.

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
\echo '=== 2. Category breakdown (1h horizon, n>=20) ==='
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
