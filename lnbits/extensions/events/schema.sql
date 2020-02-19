CREATE TABLE IF NOT EXISTS events (
    key INTEGER PRIMARY KEY AUTOINCREMENT,
    usr TEXT,
    wal TEXT,
    walnme TEXT,
    walinvkey INTEGER,
    uni TEXT,
    tit TEXT,
    amt INTEGER,
    sold INTEGER,
    dat TEXT,
    tme TEXT,
    price INTEGER
);

CREATE TABLE IF NOT EXISTS eventssold (
    key INTEGER PRIMARY KEY AUTOINCREMENT,
    uni TEXT,
    hash TEXT
);