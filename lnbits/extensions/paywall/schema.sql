CREATE TABLE IF NOT EXISTS paywalls (
  id TEXT PRIMARY KEY,
  wallet TEXT NOT NULL,
  url TEXT NOT NULL,
  memo TEXT NOT NULL,
  amount INTEGER NOT NULL,
  time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
);
