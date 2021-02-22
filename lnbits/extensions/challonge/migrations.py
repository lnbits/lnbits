async def m001_initial(db):

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS tournament (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            tournament_name TEXT NOT NULL,
            challonge_api TEXT NOT NULL,
            challonge_tournament_id TEXT NOT NULL,
            challonge_tournament_name TEXT NOT NULL,
            signup_fee INTEGER NOT NULL,
            prize_pool INTEGER NOT NULL,
            total_prize_pool INTEGER NOT NULL,
            max_participants INTEGER NOT NULL,
            current_participants INTEGER NOT NULL,
            status TEXT NOT NULL,
            winner_id TEXT,
            webhook TEXT,
            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
            start_time TIMESTAMP NOT NULL
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS participant (
            id TEXT PRIMARY KEY,
            payment_hash TEXT NOT NULL,
            tournament TEXT NOT NULL,
            secret TEXT NOT NULL,
            status TEXT NOT NULL,
            username: TEXT NOT NULL,
            challonge_username TEXT NOT NULL
        );
    """
    )
