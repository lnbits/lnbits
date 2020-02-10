CREATE TABLE IF NOT EXISTS withdraws (
    key INTEGER PRIMARY KEY AUTOINCREMENT,
    usr TEXT,
    wal TEXT,
    walnme TEXT,
    adm INTEGER,
    uni TEXT,
    tit TEXT,
    maxamt INTEGER,
    minamt INTEGER,
    spent INTEGER,
    inc INTEGER,
    tme INTEGER,
    uniq INTEGER DEFAULT 0,
    withdrawals TEXT,
    tmestmp INTEGER,
    rand TEXT
);
