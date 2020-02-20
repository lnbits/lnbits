CREATE TABLE IF NOT EXISTS events (
    key INTEGER PRIMARY KEY AUTOINCREMENT,
    usr TEXT,
    wal TEXT,
    walnme TEXT,
    walinvkey INTEGER,
    uni TEXT,
    tit TEXT,
    cldate TEXT,
    notickets INTEGER,
    sold INTEGER DEFAULT 0,
    prtick INTEGER
);

CREATE TABLE IF NOT EXISTS eventssold (
    key INTEGER PRIMARY KEY AUTOINCREMENT,
    uni TEXT,
    email TEXT,
    name TEXT,
    hash TEXT
);
