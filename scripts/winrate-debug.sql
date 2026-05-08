-- Diagnose why winrate showed 0/68 on signals < 24h.
--
-- Hypothesis: worker-markets was OOM-killed for hours; markets.last_trade_price
-- went stale; both `signal.market_price_at_signal` (snapshot at signal time)
-- and `signal_outcomes.price_t*` (snapshots T+5min, T+15min, T+1h, T+24h) read
-- the same stale value → move_pct = 0 → no `> 0` wins, no `< 0` wins.
--
-- Run:
--   docker compose exec -T db psql -U postgres -d signal < scripts/winrate-debug.sql

\echo '=== Distribution of move_t5min_pct (last 24h) ==='
SELECT
  count(*) AS resolved,
  count(*) FILTER (WHERE o.move_t5min_pct = 0)   AS exactly_zero,
  count(*) FILTER (WHERE o.move_t5min_pct > 0)   AS positive,
  count(*) FILTER (WHERE o.move_t5min_pct < 0)   AS negative,
  round(min(o.move_t5min_pct)::numeric, 4) AS min_pct,
  round(max(o.move_t5min_pct)::numeric, 4) AS max_pct,
  round(avg(o.move_t5min_pct)::numeric, 4) AS avg_pct
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '24 hours'
  AND o.move_t5min_pct IS NOT NULL;

\echo ''
\echo '=== Sample (latest 10): direction, base price, t5min price, move ==='
SELECT
  s.id,
  s.direction,
  round(s.market_price_at_signal::numeric, 4) AS base_price,
  round(o.price_t5min::numeric, 4)            AS t5min_price,
  round(o.move_t5min_pct::numeric, 4)         AS move_pct,
  s.created_at::timestamp(0)                  AS signal_at
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '24 hours'
  AND o.price_t5min IS NOT NULL
ORDER BY s.created_at DESC
LIMIT 10;

\echo ''
\echo '=== Direction counts (last 24h, resolved at 5min) ==='
SELECT
  s.direction,
  count(*) AS n,
  count(*) FILTER (WHERE o.move_t5min_pct = 0) AS zero_moves,
  count(*) FILTER (WHERE o.move_t5min_pct > 0) AS up,
  count(*) FILTER (WHERE o.move_t5min_pct < 0) AS down
FROM signals s
JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '24 hours'
  AND o.move_t5min_pct IS NOT NULL
GROUP BY s.direction;
