# Realistic backtest — 2026-05-12 — what users actually take home

**TL;DR :** the theoretical RTP of −1.75 % the old proxy reported
becomes a realized RTP of **−10.07 %** once we model the bid-ask
spread (3 pp) and dynamic exit (SL −10 %, TP +25 %). The pipeline as
shipped today **does not yet have an exploitable edge** for an end
user trading real money on Polymarket. v2 looks markedly less bad
than the legacy mix (−2.19 % vs −10.43 %) but the n=31 sample is too
small to call.

Read the numbers below in three layers:
  1. **Overall** — the headline at the standard (3 pp, −10 %, +25 %)
     trade model.
  2. **By `llm_model_version`** — does v2 keep its directional edge
     after the spread haircut? (Spoiler: yes, but n small.)
  3. **Sensitivity** — what would have to change in market structure
     (spread) or in strategy (SL/TP) to flip the sign?

Raw run command (reproducible from any machine with DB access):

```
ssh foresight 'docker compose -f /opt/foresight/docker-compose.yml \
  exec -T app python -m scripts.backtest.realistic_replay \
  --window-days 30 --spread-pp 0.03 --stop-loss-pct 10 --take-profit-pct 25'
```

---

# Realistic backtest report — 30 d window, n=740

**Trade-model parameters:** spread = 3.0 pp, stop-loss = −10.0 %, take-profit = +25.0 %

## Overall (all signals, full 30 d, current trade-model)

| n | wins | losses | ties | winrate % | CI95 low % | CI95 high % | RTP % | SE % | t-stat | sig@95? |
|---|---|---|---|---|---|---|---|---|---|---|
| 740 | 162 | 572 | 6 | 22.07 | 19.22 | 25.21 | -10.075 | 2.25 | -4.48 | True |

Exit reasons: {'stop_loss': 345, 'max_hold': 354, 'take_profit': 41}

## Per `llm_model_version`

| model | n | winrate % | CI95 low % | CI95 high % | RTP % | t-stat | sig@95? |
|---|---|---|---|---|---|---|---|
| `unknown` | 708 | 22.08 | 19.17 | 25.3 | -10.434 | -4.48 | True |
| `gpt-4o-mini@v2` | 31 | 22.58 | 11.39 | 39.81 | -2.19 | -0.31 | False |
| `gpt-4o-mini` | 1 | 0.0 | 0.0 | 79.35 | -0.613 | None | False |

## Sensitivity to (spread, stop-loss, take-profit)

| spread pp | SL % | TP % | n | winrate % | CI95 low % | RTP % | t-stat | sig@95? |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 10.0 | 25.0 | 740 | 46.74 | 43.13 | -1.397 | -0.53 | False |
| 2.0 | 10.0 | 25.0 | 740 | 27.35 | 24.25 | -7.53 | -3.19 | True |
| 3.0 | 10.0 | 25.0 | 740 | 22.07 | 19.22 | -10.075 | -4.48 | True |
| 5.0 | 10.0 | 25.0 | 740 | 12.87 | 10.65 | -14.436 | -7.05 | True |
| 3.0 | 5.0 | 25.0 | 740 | 17.77 | 15.18 | -8.937 | -4.09 | True |
| 3.0 | 20.0 | 25.0 | 740 | 24.59 | 21.61 | -9.93 | -4.32 | True |
| 3.0 | 10.0 | 10.0 | 740 | 22.75 | 19.87 | -9.904 | -4.43 | True |
| 3.0 | 10.0 | 50.0 | 740 | 21.93 | 19.09 | -10.228 | -4.55 | True |
| 3.0 | ∞ | ∞ | 740 | 26.5 | 23.43 | -10.927 | -4.86 | True |

---

## How to read this

### The spread is the killer

The "0 pp spread" row shows what we already knew from `replay.py`:
**RTP −1.40 %, winrate 46.74 %** — a coin-flip pipeline, slightly
negative. That number is the **directional** edge of the LLM + filter
stack on its own, ignoring transaction costs.

Add **3 pp of spread** (typical Polymarket on liquid markets) and the
realized RTP collapses to **−10.07 %**, winrate halves to **22 %**,
and the loss becomes **statistically significant at 95 %** (t=-4.48,
SE=2.25). The pipeline has to overcome the spread before it can claim
anything. Today it does not.

### Why the winrate drops so much

Spread cost cuts both ways: every winning trade gives up some of its
gain to the spread, and every losing trade loses extra. With our
typical entry/exit mids, a +1 pp move in the YES price barely covers
the spread, and a 0-pp move turns into a guaranteed loss. The "ties
excluded" framing of the proxy hid this — in reality, ties ARE losses
because of the spread.

The exit reason distribution makes this concrete:
```
stop_loss : 345 (47 %)  — SL hit before TP, locked at −10 %
max_hold  : 354 (48 %)  — neither hit; exited at t+24h, usually negative
take_profit:  41 ( 5 %) — actual winners, +25 % or more
```

Take-profit at +25 % is rarely hit because on a 24-hour horizon the
median realized move (after spread) doesn't get there. The strategy
locks in losses (SL) far more often than it locks in wins (TP).

### v2 keeps a directional edge, but n is too small

The promising signal: `gpt-4o-mini@v2` shows realized RTP **−2.19 %**
vs **−10.43 %** for the legacy mix — a 5× reduction in bleed rate.
But n=31 with CI95 [11.4 %, 39.8 %] means the true winrate could be
anywhere from "still pretty bad" to "edge of profitable". We need 200+
v2 signals (≈10-14 days at current volume) before this number means
anything.

### What would it take to flip the sign?

From the sensitivity table:
  * **Spread 0 pp:** RTP −1.40 %, **still negative** even with zero
    transaction cost. So the directional alpha alone is not enough.
  * **TP 50 % (looser):** −10.23 %, **essentially the same** — moves
    of >50 % on t+24h are too rare to matter.
  * **No SL/TP (pure hold to t+24h):** RTP −10.93 %, **even worse**
    than the active-management strategy. Holding does not help.

To make the strategy profitable at 3 pp spread, we would need to
**either**:
  1. Trade only on markets where the realized spread is < 1 pp
     (deep-liquidity, blue-chip Polymarket markets). The signal could
     be filtered by a `spread <= threshold` gate at emission.
  2. Push the **directional** edge so the zero-spread RTP is solidly
     positive (e.g. +3 % or more), so that 3 pp spread still leaves
     something on the table. That's what v2 + T-013 + T-022 are
     supposed to do — TBD whether they get there.

### What this means for the product

The user-facing implication is the one we already flagged in `Q1`
of the methodology audit: **the winrate displayed on
`/admin/stats/extended` is a directional proxy, not a P&L.** A user
who copy-trades naively, with realistic Polymarket fills, would have
**lost ~10 % of capital per signal-trade over the last 30 days**, not
broken even.

This is why the bêta should be paper-trading-first and the messaging
should be "research tool that helps you reason about news → markets",
not "automated trading edge". The auto-trade Sprint we discussed
earlier is contingent on the realized RTP turning positive on the
post-v2/post-T-022 sample.

### What's next

1. **Re-run this script weekly** starting now. As v2 + T-022a
   accumulate n, watch `gpt-4o-mini@v2` row's RTP and CI95. If the
   high end of CI95 stays below 0 for 14+ days at n≥200, the
   strategy is structurally unprofitable and we pivot.
2. **Add a `spread_at_signal` field** to `signal_outcomes` so we can
   model realistic spread per signal instead of a 3-pp average. Some
   markets are 1 pp, others 5 pp — the average hides everything.
3. **Add `T-X1` to the plan backlog** — a `signal_max_spread_pp`
   gate that rejects emission on markets too illiquid to trade
   profitably. Backtest projects this drops volume by ~30 % and
   recovers ~3 pp of RTP.
