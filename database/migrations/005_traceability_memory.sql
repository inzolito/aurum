-- Migration 005: Traceability and Long-Term Memory
-- Create tables for raw news and market catalysts

CREATE TABLE IF NOT EXISTS raw_news_feed (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(100),
    title TEXT NOT NULL,
    content_summary TEXT,
    hash_id VARCHAR(64) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS market_catalysts (
    id SERIAL PRIMARY KEY,
    event_name VARCHAR(255) UNIQUE NOT NULL,
    start_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    estimated_end_date TIMESTAMPTZ,
    ai_sentiment_score DECIMAL(3, 2),
    is_active BOOLEAN DEFAULT TRUE,
    last_update TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_raw_news_hash ON raw_news_feed(hash_id);
CREATE INDEX IF NOT EXISTS idx_catalysts_active ON market_catalysts(is_active);
