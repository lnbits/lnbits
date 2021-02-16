async def m001_initial(db):

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS tournament (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            challonge_API TEXT NOT NULL,
            challonge_tournament_id TEXT NOT NULL,
            challonge_tournament_name TEXT NOT NULL,
            signup_fee BIGINT NOT NULL,
            prize_pool BIGINT NOT NULL,
            total_prize_pool BIGINT NOT NULL,
            max_participants INTEGER NOT NULL,
            current_participants INTEGER,
            status TEXT NOT NULL, 
            winner_id TEXT,
            webhook TEXT,
            start_time  TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
        );
    """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS participant (
            id TEXT PRIMARY KEY,
            tournament TEXT NOT NULL,
            secret TEXT NOT NULL,
            status TEXT NOT NULL,
            username TEXT NOT NULL,
            challonge_username TEXT NOT NULL,
            email TEXT NOT NULL
        );
    """
    )
