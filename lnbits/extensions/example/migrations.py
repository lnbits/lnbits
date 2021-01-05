# async def m001_initial(db):

#    await db.execute(
#        """
#        CREATE TABLE IF NOT EXISTS example (
#            id TEXT PRIMARY KEY,
#            wallet TEXT NOT NULL,
#            time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
#        );
#    """
#    )
