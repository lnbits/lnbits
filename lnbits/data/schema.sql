CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    email TEXT,
    pass TEXT
);

CREATE TABLE IF NOT EXISTS extensions (
    user TEXT NOT NULL,
    extension TEXT NOT NULL,
    active BOOLEAN DEFAULT 0,

    UNIQUE (user, extension)
);

CREATE TABLE IF NOT EXISTS wallets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    user TEXT NOT NULL,
    adminkey TEXT NOT NULL,
    inkey TEXT
);

CREATE TABLE IF NOT EXISTS apipayments (
    payhash TEXT NOT NULL,
    amount INTEGER NOT NULL,
    fee INTEGER NOT NULL DEFAULT 0,
    wallet TEXT NOT NULL,
    pending BOOLEAN NOT NULL,
    memo TEXT,
    time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now')),

    UNIQUE (wallet, payhash)
);

CREATE VIEW IF NOT EXISTS balances AS
  SELECT wallet, COALESCE(SUM(s), 0) AS balance FROM (
      SELECT wallet, SUM(amount) AS s  -- incoming
      FROM apipayments
      WHERE amount > 0 AND pending = 0  -- don't sum pending
      GROUP BY wallet
    UNION ALL
      SELECT wallet, SUM(amount + fee) AS s  -- outgoing, sum fees
      FROM apipayments
      WHERE amount < 0  -- do sum pending
      GROUP BY wallet
  )
  GROUP BY wallet;
