# BUY_NO toxic-band exploration — 2026-05-12

Performed during the v2-flip surveillance window. Read-only queries against
prod `signals × signal_outcomes` for the 30-day rolling sample (n=707
resolved on t1h, 38 ties excluded).

## Headline

The pipeline has been splitting almost exactly evenly on direction:

| Direction | n | RTP (signed move, t1h) |
|---|---:|---:|
| BUY_NO  | 380 | **−10.24 %** |
| BUY_YES | 289 |  **+9.09 %** |

BUY_YES is doing the work. BUY_NO is doing the bleeding.

## RTP by `signal_score` bucket

| score | n | RTP t1h |
|---|---:|---:|
| <65   | 259 | −0.0 % |
| 65-74 | 327 | **−5.3 %** |
| 75-84 |  79 | +5.6 % |
| 85+   |   4 | (+32 %, n too small) |

`signal_score 65-74` is half the volume and the most toxic bucket.
The `signal_score_threshold=65` default is therefore picking up the
worst slice; raising it would help but is blunt — see the cross-tab.

## Cross-tab — `signal_score` × direction

| score | BUY_NO n / RTP | BUY_YES n / RTP |
|---|---:|---:|
| <65   | 166 / **−4.4 %** |  93 /  +7.5 % |
| 65-74 | 174 / **−14.5 %** | 153 /  +5.0 % |
| 75+   |  40 / **−16.0 %** |  43 / **+27.2 %** |

**Higher score makes BUY_NO worse, not better.** Score and BUY_NO are
anti-correlated for RTP — the model is "confidently wrong" on BUY_NO,
which is the textbook over-fit / over-confident-on-toxic-bucket
behaviour.

## BUY_NO RTP by market YES price (post-T-001)

| price bucket | n | RTP |
|---|---:|---:|
| YES<0.30 (T-001) | 201 | **−17.1 %** ← already filtered |
| YES 0.30-0.40 |  46 |  −3.6 % |
| YES 0.40-0.50 |  23 |  +5.9 % |
| YES 0.50-0.60 |  13 |  −1.8 % |
| YES 0.60-0.70 |  27 |  −1.7 % |
| **YES≥0.70** |  **70** | **−4.6 %** ← new toxic zone |

The "deep-YES" zone is the mirror of T-001: when the market already
prices YES highly, betting NO is a contrarian bet against consensus,
and it loses in expectation.

## BUY_YES RTP by market YES price

| price bucket | n | RTP |
|---|---:|---:|
| YES<0.30 | 113 | **+19.9 %** |
| YES 0.30-0.40 | 33 | +13.4 % |
| YES 0.40-0.50 | 15 |  −2.3 % |
| YES 0.50-0.60 | 22 | **−7.2 %** |
| YES 0.60-0.70 | 30 |  −0.2 % |
| YES≥0.70 | 76 |  +1.7 % |

BUY_YES gains the most when the market is being "too pessimistic"
(YES<0.40). The 0.40-0.60 mid-band is shallowly toxic for BUY_YES
too but the n is small; not enough signal for a dedicated filter yet.

## T-013 candidate rule

Drop BUY_NO outside the `[0.30, 0.70]` band — layered on top of T-001.

| metric | baseline | T-001 + T-013 |
|---|---:|---:|
| n_input | 707 | 707 |
| n_kept | 707 | 423 |
| **retention** | 100 % | **59.8 %** |
| **winrate** | 49.78 % | **51.76 %** |
| CI95 | [46.00, 53.56] | [46.86, 56.63] |
| **RTP t1h** | **−1.75 %** | **+6.42 %** |
| t-stat | −0.6 | **1.82** (~93 % confidence) |

**+8.2 pp of RTP for a 40 % volume cut.** Just below the 95 %
significance bar (t=1.82 < 1.96), but the direction is clear.

## Decision

The T-013 filter is shipped in `signal_builder.py` behind
`ENABLE_BUYNO_HIGHPRICE_FILTER` (default OFF). It is **not flipped on
yet** because:

1. v2 prompt (T-009, flipped 22:08 UTC 2026-05-11) is already
   actively reasoning price-conditional. v2 will reject the same
   contrarian BUY_NO trades upstream — we may not need T-013 at all
   once v2 has run for 7 days.
2. Flipping both T-013 and v2 in the same week confounds the
   measurement on `by_llm_model_version` — we lose the ability to
   attribute the RTP delta cleanly.
3. The 40 % volume drop is aggressive. Need to verify post-v2 volume
   first before stacking another 40 % cut.

**Replay this report at H+168** (week of 2026-05-18):
- If v2 has independently fixed `BUY_NO × YES≥0.70` (RTP no longer
  negative on `by_llm_model_version=gpt-4o-mini@v2`) → T-013 stays
  OFF, the prompt did the work.
- If v2 retained the toxic pattern → flip T-013 on.

Re-run command (read-only, ~30 s):

```bash
ssh foresight 'docker compose -f /opt/foresight/docker-compose.yml \
  exec -T db psql -U postgres -d signal -c "
SELECT
  CASE WHEN s.market_price_at_signal < 0.30 THEN '\''YES<0.30'\''
       WHEN s.market_price_at_signal < 0.70 THEN '\''YES 0.30-0.70'\''
       ELSE '\''YES≥0.70'\'' END AS bucket,
  s.llm_model_version,
  COUNT(*) AS n,
  ROUND(AVG(-so.move_t1h_pct)::numeric, 2) AS rtp_pct
FROM signals s JOIN signal_outcomes so ON so.signal_id = s.id
WHERE s.created_at > NOW() - INTERVAL '\''7 days'\''
  AND s.direction IN ('\''BUY_NO'\'','\''NO'\'','\''DOWN'\'')
  AND so.move_t1h_pct IS NOT NULL
GROUP BY 1, 2 ORDER BY 1, 2;
"'
```
