-- Quick winrate over signals < 24h.
--
-- Usage (avoids the underscore-mangling Hetzner web console):
--   docker compose exec -T db psql -U postgres -d signal -f /work/scripts/winrate_recent.sql
-- or (via stdin from host)
--   docker compose exec -T db psql -U postgres -d signal < scripts/winrate_recent.sql
--
-- `direction_correct` is filled in by the outcomes worker once the price
-- horizon (5min / 15min / 1h / 24h) elapses. Recent signals (< 1h old)
-- typically still have NULL direction_correct — they show up in `total`
-- but not in `resolved`.

\echo '=== Signals emitted in the last 24h ==='
SELECT
  count(*) AS total,
  count(o.direction_correct) AS resolved,
  count(*) FILTER (WHERE o.direction_correct IS TRUE) AS wins,
  count(*) FILTER (WHERE o.direction_correct IS FALSE) AS losses,
  round(
    100.0 * count(*) FILTER (WHERE o.direction_correct IS TRUE)
      / NULLIF(count(o.direction_correct), 0),
    1
  ) AS winrate_pct
FROM signals s
LEFT JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '24 hours';

\echo ''
\echo '=== Per-horizon resolved winrate (last 24h) ==='
SELECT
  '5min'  AS horizon,
  count(o.move_t5min_pct) AS resolved,
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction = 'YES' AND o.move_t5min_pct > 0)
      OR (s.direction = 'NO'  AND o.move_t5min_pct < 0)
    ) / NULLIF(count(o.move_t5min_pct), 0),
    1
  ) AS winrate_pct
FROM signals s LEFT JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '24 hours'
UNION ALL
SELECT
  '15min',
  count(o.move_t15min_pct),
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction = 'YES' AND o.move_t15min_pct > 0)
      OR (s.direction = 'NO'  AND o.move_t15min_pct < 0)
    ) / NULLIF(count(o.move_t15min_pct), 0),
    1
  )
FROM signals s LEFT JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '24 hours'
UNION ALL
SELECT
  '1h',
  count(o.move_t1h_pct),
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction = 'YES' AND o.move_t1h_pct > 0)
      OR (s.direction = 'NO'  AND o.move_t1h_pct < 0)
    ) / NULLIF(count(o.move_t1h_pct), 0),
    1
  )
FROM signals s LEFT JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '24 hours'
UNION ALL
SELECT
  '24h',
  count(o.move_t24h_pct),
  round(
    100.0 * count(*) FILTER (WHERE
      (s.direction = 'YES' AND o.move_t24h_pct > 0)
      OR (s.direction = 'NO'  AND o.move_t24h_pct < 0)
    ) / NULLIF(count(o.move_t24h_pct), 0),
    1
  )
FROM signals s LEFT JOIN signal_outcomes o ON o.signal_id = s.id
WHERE s.created_at > now() - interval '24 hours';
