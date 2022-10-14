async def m001_initial(db):

   await db.execute(
       f"""
       CREATE TABLE pushnotifications.subscriptions (
           endpoint TEXT NOT NULL,
           wallet TEXT NOT NULL,
           data TEXT NOT NULL,
           host TEXT NOT NULL,
           timestamp TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
       );
       """
   )
