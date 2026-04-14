-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- ══════════════════════════════════════════════════════════════════════
-- Views (created after tables exist — safe to run multiple times)
-- ══════════════════════════════════════════════════════════════════════

-- Ingestion health: median lag per source over 24 h
CREATE OR REPLACE VIEW v_ingestion_health AS
SELECT
    source_name,
    source_tier,
    COUNT(*)                                                    AS articles_24h,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ingestion_lag_seconds) AS median_lag_s
FROM news
WHERE ingestion_date > NOW() - INTERVAL '24 hours'
GROUP BY source_name, source_tier
ORDER BY source_tier, median_lag_s;

-- LLM daily cost by call type
CREATE OR REPLACE VIEW v_llm_daily_cost AS
SELECT
    DATE(called_at)  AS day,
    call_type,
    SUM(cost_usd)    AS total_cost_usd,
    SUM(tokens_input + tokens_output) AS total_tokens,
    COUNT(*)          AS calls
FROM llm_cost_log
GROUP BY DATE(called_at), call_type
ORDER BY 1 DESC;

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_markets_embedding_hnsw
ON markets USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Signal accuracy by score bucket (10-point buckets)
CREATE OR REPLACE VIEW v_signal_accuracy AS
SELECT
    WIDTH_BUCKET(s.signal_score::numeric, 0, 100, 10) * 10 AS score_bucket,
    COUNT(*)                                                AS total,
    COUNT(so.outcome_label)                                 AS resolved,
    AVG(so.outcome_label::float)                            AS accuracy
FROM signals s
LEFT JOIN signal_outcomes so ON so.signal_id = s.id
GROUP BY 1
ORDER BY 1;
