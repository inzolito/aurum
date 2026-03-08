-- Migration 006: Structural Update V13.0
-- Add published_at for extreme transparency and eliminate info latency

ALTER TABLE raw_news_feed ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

-- Index for instant chronology recovery
CREATE INDEX IF NOT EXISTS idx_raw_news_published ON raw_news_feed(published_at);

-- Update existing rows to have published_at = timestamp if NULL (fallback)
UPDATE raw_news_feed SET published_at = timestamp WHERE published_at IS NULL;
