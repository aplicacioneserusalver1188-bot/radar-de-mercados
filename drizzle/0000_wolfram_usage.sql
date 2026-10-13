CREATE TABLE IF NOT EXISTS wolfram_usage_monthly (
  month_key TEXT PRIMARY KEY,
  calls_used INTEGER NOT NULL DEFAULT 0
);
