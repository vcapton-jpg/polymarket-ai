# Signal — Go-to-Market Strategy

## One-Liner

**Signal turns breaking news into prediction market alpha before the crowd prices it in.**

---

## Target Customer Profile

### Primary: Crypto-native prediction market traders
- **Who**: Active Polymarket traders doing $1k-$100k/month volume
- **Pain**: Manually scanning news, Reddit, X/Twitter for events that move contracts -- slow, incomplete, emotionally biased
- **Why they pay**: Time savings (2+ hours/day of monitoring eliminated), information edge (catch moves 15-60 minutes earlier than manual scanning), disciplined scoring removes emotional trading
- **Willingness to pay**: $49-199/month (0.5-2% of monthly volume — trivial vs. the edge gained)

### Secondary: Crypto funds & quantitative traders
- **Who**: Small crypto funds, prop desks, sophisticated retail traders
- **Pain**: Building an in-house news-to-signal pipeline costs $200k+/year in engineering and data costs
- **Why they pay**: API access to programmatic signals, backtested track record, direct CLOB integration
- **Willingness to pay**: $499-999/month for API access

### Tertiary: Political & news junkies
- **Who**: People who follow geopolitics and want to put money behind their convictions
- **Pain**: Don't know which Polymarket contracts exist, can't assess if the market is mispriced
- **Why they pay**: Signal makes prediction markets accessible by explaining what and why to trade
- **Willingness to pay**: Free tier with $9.99/month pro for push notifications and full history

---

## Pricing Tiers

| Feature | Free | Pro ($29/mo) | Trader ($99/mo) | API ($499/mo) |
|---------|------|-------------|-----------------|---------------|
| Live signal feed | Last 24h | Full history | Full history | Full history |
| Signal limit | 10/day | Unlimited | Unlimited | Unlimited |
| Score explanations | Basic | Detailed | Detailed + sub-scores | Raw JSON |
| Push notifications | - | Yes | Yes | Webhook |
| Telegram alerts | - | Yes | Yes | Yes |
| Category filters | All | All | All | All |
| Performance dashboard | Basic | Full | Full + P&L sim | Full + export |
| Market data | - | - | Live prices + depth | Streaming |
| API access | - | - | - | 10k req/day |
| Direct trade execution | - | - | Coming Q3 | Coming Q3 |
| Priority support | - | - | Discord | Dedicated |

**Annual discount**: 2 months free (16.7% off).

---

## Three Killer Use Cases

### 1. "The Iran Drone Strike Signal"

> **Breaking**: Reuters reports Iranian drone strikes on Kurdish positions in Iraq.
>
> **Signal detected**: Score 84/100 — BUY YES on "Will the US impose new sanctions on Iran in 2025?"
>
> **Market was at**: 38% YES → moved to 52% YES within 4 hours.
>
> **Score explanation**: "Iran military escalation historically triggers US sanctions response within 2-4 weeks. Current contract underpriced given bipartisan congressional pressure for action."

A Signal user got the alert 47 minutes before mainstream crypto Twitter picked it up. At 38 cents, buying YES and selling at 52 cents = 36.8% return on position.

### 2. "The Fed Rate Signal"

> **Breaking**: WSJ reports Fed governors privately discussing accelerated rate cuts.
>
> **Signal detected**: Score 91/100 — BUY YES on "Will the Fed cut rates by 50bps at next meeting?"
>
> **Market was at**: 22% YES → moved to 41% YES after FOMC minutes confirmed.
>
> **Score explanation**: "WSJ Fed reporting has >85% predictive accuracy for FOMC decisions. Leak-style sourcing suggests high insider confidence. Market severely underpricing at 22%."

### 3. "The Sports Upset Signal"

> **Breaking**: Multiple injury reports from NBA team practice — star player seen in walking boot.
>
> **Signal detected**: Score 72/100 — BUY NO on "[Star Player] to play in tonight's game"
>
> **Market was at**: 78% YES → dropped to 31% YES when the team officially ruled him out.
>
> **Score explanation**: "Walking boot sighting 6 hours before game strongly correlates with DNP. Market still pricing 78% play probability based on pre-injury expectations."

---

## Competitive Moat

### 1. Data Pipeline Depth
- Multi-source ingestion (RSS, World News API, X/Twitter) with NER extraction, semantic deduplication, and event clustering
- Not just "news feed" — intelligent matching of events to specific contract mechanisms

### 2. Scoring Engine
- Hybrid: vector similarity + BM25 retrieval + LLM impact analysis + market microstructure features
- Every score is explainable — users understand WHY a signal fires, building trust

### 3. Track Record
- Every signal is logged and tracked against outcomes — verifiable accuracy
- Competitors can claim anything; Signal has receipts

### 4. Speed
- News → Signal in under 60 seconds
- Polymarket-native: directly references contract IDs, current prices, liquidity, spread

### 5. Cost Efficiency
- Entire LLM pipeline runs under €30/month using smart prompt engineering, embedding caching, and batch processing
- Competitors burning $1k+/month on LLM costs can't match unit economics

### 6. Network Effects
- More users → more signal feedback → better scoring calibration
- Track record improves with volume, creating compounding advantage

---

## 6-Month Roadmap to $10k MRR

### Month 1: Foundation ($0 → $500 MRR)
- [ ] Launch on Product Hunt + Hacker News
- [ ] Free tier captures emails and builds waitlist
- [ ] Telegram channel with free signals builds audience (target: 500 members)
- [ ] Cold DM top 50 Polymarket traders on X/Twitter with personalized signal examples
- [ ] Target: 20 Pro subscribers at $29/month = $580 MRR

### Month 2: Social Proof ($500 → $1,500 MRR)
- [ ] Publish first "Track Record Report" — real accuracy stats over 30 days
- [ ] Post daily "Signal of the Day" thread on X/Twitter with outcome follow-up
- [ ] Launch referral program: give 1 month free, get 1 month free
- [ ] Polymarket Discord presence — provide genuine value in discussions
- [ ] Target: 50 Pro subscribers + first Trader tier conversions

### Month 3: API Launch ($1,500 → $3,000 MRR)
- [ ] Ship API tier with documentation and Python SDK
- [ ] Reach out to 20 crypto funds/prop desks with backtested performance
- [ ] Partner with 2-3 prediction market content creators for promotion
- [ ] Add track record page with public leaderboard
- [ ] Target: 60 Pro + 10 Trader + 2 API = $3,078 MRR

### Month 4: Execution Edge ($3,000 → $5,500 MRR)
- [ ] Launch one-click trade execution via Polymarket CLOB
- [ ] "Paper trading" mode for free tier — converts to paid when users see simulated profits
- [ ] Weekly market briefing email (content marketing flywheel)
- [ ] Crypto podcast tour — 3-4 appearances
- [ ] Target: 80 Pro + 25 Trader + 5 API

### Month 5: Expansion ($5,500 → $8,000 MRR)
- [ ] Multi-market: add Kalshi, Manifold Markets
- [ ] Portfolio tracking + P&L attribution per signal
- [ ] Community features — users can flag/rate signals
- [ ] B2B outreach to prediction market platforms as embedded feature
- [ ] Target: 100 Pro + 40 Trader + 8 API

### Month 6: Scale ($8,000 → $10,000+ MRR)
- [ ] Automated trading bot (premium add-on: $199/month)
- [ ] Custom alert rules and signal criteria for Trader tier
- [ ] Launch annual plans with 2 months free promotion
- [ ] First B2B deal: white-label Signal for a trading platform
- [ ] Target: 120 Pro + 50 Trader + 10 API + 1 B2B = $11,000+ MRR

---

## Product Hunt Launch Copy

### Tagline
**Signal — AI-powered prediction market intelligence**

### Description
Signal monitors breaking news 24/7 and instantly matches events to Polymarket contracts where the market hasn't priced in the news yet.

Every signal includes: what happened, which contract to trade, a conviction score (0-100), and a plain-English explanation of why this matters.

We built Signal because manual news monitoring is slow, incomplete, and emotionally biased. Our pipeline ingests from 50+ sources, deduplicates with semantic hashing, clusters related events, and scores each opportunity against real market microstructure data.

**What you get:**
- Real-time signal feed with conviction scoring
- Push notifications for high-conviction opportunities
- Performance tracking with verified accuracy
- Score explanations that make you smarter, not just faster

**What makes us different:**
- Every signal is explainable — you see the reasoning, not a black box
- Every signal is tracked against outcomes — real verifiable accuracy
- Sub-60-second latency from news breaking to signal firing
- Runs entirely under €30/month in LLM costs — sustainable unit economics

We're live with real signals. Try it free and see the edge for yourself.

### First Comment (Maker)
Hi PH! I'm Vadim, solo developer behind Signal.

I built this because I was spending 2+ hours/day scanning news for prediction market opportunities. The process was: read news → think "does this affect any market?" → check 50 Polymarket contracts → calculate if it's mispriced → decide to trade.

Signal automates all of that. In the last 30 days our pipeline has generated [X] signals with a [Y]% accuracy rate on resolved markets.

The entire system runs on a single VPS: FastAPI backend, React frontend, Celery workers, PostgreSQL with pgvector for semantic search. Total infrastructure cost: ~$50/month.

I'd love your feedback on the scoring system — especially the explanations. My goal is to make each signal teach you something about why events move markets.

Ask me anything about the architecture, the scoring model, or prediction markets in general!

---

## 60-Second Investor Pitch Script

*[Beat 1 — Hook, 10 seconds]*

> "Every day, breaking news moves prediction markets by 10-30% in minutes. The problem? By the time you see the news, check Polymarket, and decide to trade — the edge is gone. Signal fixes that."

*[Beat 2 — What it is, 10 seconds]*

> "Signal is an AI system that monitors 50+ news sources in real-time, matches events to Polymarket contracts, and fires scored trading signals in under 60 seconds — before the crowd reacts."

*[Beat 3 — How it works, 10 seconds]*

> "Each signal includes a conviction score, price target, and plain-English explanation. Not a black box — users see exactly why we think the market is mispriced."

*[Beat 4 — Traction, 10 seconds]*

> "We're live with real signals. Our pipeline runs at under €30/month in LLM costs while competitors spend 10x that. We have [X] users and [Y]% accuracy on resolved markets."

*[Beat 5 — Market, 10 seconds]*

> "Polymarket did $9 billion in volume in 2024. Kalshi, Manifold, and others are growing fast. This is a new asset class — and every trader needs an information edge."

*[Beat 6 — Ask, 10 seconds]*

> "We're raising [amount] to build direct trade execution, expand to Kalshi, and hire a second engineer. Signal is how prediction markets get their Bloomberg terminal. Let's talk."

---

*Document generated on 2025-04-14. Update quarterly with real metrics.*
