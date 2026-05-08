-- How much labeled training data do we have for a recalibration model?
--
-- Run:
--   docker compose exec -T db psql -U postgres -d signal < scripts/training-data-count.sql

\echo '=== Total signals ever emitted ==='
SELECT count(*) AS total FROM signals;

\echo ''
\echo '=== With outcome rows (any horizon resolved) ==='
SELECT
  count(DISTINCT s.id) AS signals_with_outcome_row,
  count(o.move_t5min_pct)  AS resolved_5min,
  count(o.move_t15min_pct) AS resolved_15min,
  count(o.move_t1h_pct)    AS resolved_1h,
  count(o.move_t24h_pct)   AS resolved_24h,
  count(o.direction_correct) AS direction_correct_filled
FROM signals s
LEFT JOIN signal_outcomes o ON o.signal_id = s.id;

\echo ''
\echo '=== Signal age distribution ==='
SELECT
  CASE
    WHEN s.created_at > now() - interval '24 hours' THEN '< 24 h'
    WHEN s.created_at > now() - interval '7 days'   THEN '< 7 d'
    WHEN s.created_at > now() - interval '30 days'  THEN '< 30 d'
    ELSE                                                 '> 30 d'
  END AS bucket,
  count(*) AS n,
  count(o.move_t1h_pct) AS resolved_1h
FROM signals s
LEFT JOIN signal_outcomes o ON o.signal_id = s.id
GROUP BY 1
ORDER BY min(s.created_at) DESC;

\echo ''
\echo '=== Daily emission rate (last 14 days) ==='
SELECT
  date(s.created_at) AS day,
  count(*) AS signals,
  count(o.move_t1h_pct) AS with_1h_outcome
FROM signals s
LEFT JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '14 days'
GROUP BY 1
ORDER BY 1 DESC;
