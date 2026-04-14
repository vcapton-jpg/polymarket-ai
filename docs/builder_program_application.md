# Polymarket Builder Program Application

## Project: Signal — AI-Powered Prediction Market Intelligence & Execution Platform

### What we're building

Signal is a platform that uses a team of 6 specialized AI agents to automate the full prediction market trading lifecycle:

1. **Scout Agent** — Monitors 50+ news sources (RSS, World News API, social feeds) in real-time
2. **Analyst Agent** — LLM-powered impact analysis scoring each event's effect on specific markets
3. **Strategist Agent** — Kelly criterion position sizing with concentration limits and correlation detection
4. **Trader Agent** — Automated execution on Polymarket via Builder API (this application)
5. **Risk Manager Agent** — Continuous position monitoring with stop-loss and take-profit alerts
6. **Reporter Agent** — Daily intelligence briefs and weekly performance reports

### Why Builder Program

We need Builder Program access to:
- Execute trades gas-free via the Builder Relayer
- Tag volume with our Builder Code for USDC rewards
- Access 15x API rate limits for real-time position monitoring
- Deploy Gnosis Safe wallets for users via Relayer

### Technical Integration

- **Stack**: Python (FastAPI, Celery, SQLAlchemy) + React + PostgreSQL/pgvector + Redis
- **SDKs**: py-clob-client, py-order-utils, py-builder-signing-sdk, py-builder-relayer-client
- **Auth**: L1 EIP-712 signing → L2 HMAC credentials
- **Orders**: GTC limit orders and FOK market orders via CLOB API
- **Data**: Gamma API for market discovery, CLOB API for execution, Data API for positions

### Volume Potential

- Current signal generation: 20-50 signals/day above score threshold
- Target user base: 100+ active traders in first 3 months
- Estimated monthly volume: $50K-$500K depending on user adoption
- Volume grows with signal quality improvements (flywheel)

### What's Already Built

- Full news ingestion pipeline (RSS, World News API, X social feeds)
- NLP pipeline (NER, embeddings, clustering, semantic search)
- LLM impact analysis with GPT-4o
- Heuristic + ML-ready scoring system
- Real-time signal delivery (WebSocket, Push notifications, Telegram)
- Frontend dashboard with signal cards, market explorer, performance tracking
- Track record with public accuracy metrics
- Agent framework with activity logging
- Trading infrastructure (portfolio, positions, orders DB schema)
- B2B API with key management and tiered access

### Revenue Model

1. **Volume Rewards** — USDC proportional to volume routed through our Builder Code
2. **SaaS** — Free (5 signals/day) / Pro ($29/mo: execution + agents) / Enterprise ($199/mo: API)
3. **B2B API** — Signal webhooks and streaming for other builders and quant traders
4. **Grants** — Application to Builder Grants program ($10K-$75K)

### Team

Solo developer with full-stack expertise in AI/ML, web3, and financial data systems.

### Links

- GitHub: [repository URL]
- Live Demo: [demo URL]
- API Documentation: Available at /api/docs (Swagger)

### Contact

[Your contact information]
