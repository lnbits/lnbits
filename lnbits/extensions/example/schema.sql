/* create your extensions table and the variables needed here */
CREATE TABLE IF NOT EXISTS events (
    key INTEGER PRIMARY KEY AUTOINCREMENT,
    usr TEXT,
    wal TEXT,
    walnme TEXT
);
