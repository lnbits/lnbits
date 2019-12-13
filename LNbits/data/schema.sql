CREATE TABLE IF NOT EXISTS accounts (
    userhash text PRIMARY KEY,
    email text,
    pass text
);

CREATE TABLE IF NOT EXISTS wallets (
    hash text PRIMARY KEY,
    name text NOT NULL,
    user text NOT NULL,
    adminkey text NOT NULL,
    inkey text
);

CREATE TABLE IF NOT EXISTS apipayments (
    payhash text PRIMARY KEY,
    amount integer NOT NULL,
    fee integer NOT NULL,
    wallet text NOT NULL,
    pending boolean NOT NULL,
    memo text
);
