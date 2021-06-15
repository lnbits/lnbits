async def m001_initial(db):

   await db.execute(
       """
       CREATE TABLE IF NOT EXISTS royalties (
           id TEXT PRIMARY KEY,
           paid BOOLEAN NOT NULL,
           data TEXT NOT NULL,
           time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
       );
   """
   )

   await db.execute(
       """
       CREATE TABLE IF NOT EXISTS royalty_account (
           id TEXT PRIMARY KEY,
           wallet TEXT NOT NULL,
           time TIMESTAMP NOT NULL DEFAULT (strftime('%s', 'now'))
       );
   """
   )
