async def m001_schedule(db):
    await db.execute(
        f"""
       CREATE TABLE scheduledpayments.schedule (
           id TEXT PRIMARY KEY,
           wallet TEXT NOT NULL,

           recipient TEXT NOT NULL,

           famount INT NOT NULL,
           currency TEXT NOT NULL,

		   interval TEXT NOT NULL,
           timezone TEXT NOT NULL,
           
           start_date DATE DEFAULT NULL,
           end_date DATE DEFAULT NULL,

           time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
       );
   """
    )


async def m001_events(db):
    await db.execute(
        f"""
       CREATE TABLE scheduledpayments.schedule_events (
           id TEXT PRIMARY KEY,
           schedule_id TEXT NOT NULL,

           amount INT NOT NULL,
           payment_hash TEXT DEFAULT NULL,

           status TEXT NOT NULL,

           time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},

           FOREIGN KEY(schedule_id) REFERENCES {db.references_schema}schedule(id)
       );
   """
    )
