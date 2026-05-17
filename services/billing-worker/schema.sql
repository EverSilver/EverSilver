-- D1 schema as an alternative to KV.
-- Apply with: wrangler d1 execute eversilver-billing --file=./schema.sql

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE,
  tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'ultra')),
  subscription_id TEXT,
  subscription_status TEXT,
  current_period_end INTEGER, -- unix seconds
  cancel_at_period_end INTEGER NOT NULL DEFAULT 0, -- boolean
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_id);

CREATE TABLE IF NOT EXISTS subscription_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subscription_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  received_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_sub ON subscription_events(subscription_id);

-- Idempotency: store processed webhook event ids to drop duplicates.
CREATE TABLE IF NOT EXISTS webhook_events (
  event_id TEXT PRIMARY KEY,
  received_at INTEGER NOT NULL
);
