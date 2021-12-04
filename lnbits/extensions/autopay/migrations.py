async def m001_initial(db):
   await db.execute(
       f"""
       CREATE TABLE autopay.schedule_entries (
           id INTEGER PRIMARY KEY,
           wallet_id TEXT NOT NULL,
           title TEXT NOT NULL,
           base_datetime TIMESTAMP NOT NULL,
           repeat_freq TEXT NOT NULL,
           lnurl TEXT NOT NULL,
           amount_msat INTEGER NOT NULL,
           created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
           is_deleted INTEGER NOT NULL DEFAULT 0
       );
   """
   )
   await db.execute(
       f"""
       CREATE TABLE autopay.payment_log (
           id INTEGER PRIMARY KEY,
           schedule_id INTEGER NOT NULL,
           created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
           payment_hash TEXT
       );
   """
   )
