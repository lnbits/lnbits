async def m001_initial_invoices(db):

    await db.execute(
        f"""
       CREATE TABLE nostrnip5.domains (
           id TEXT PRIMARY KEY,
           wallet TEXT NOT NULL,

           currency TEXT NOT NULL,
           amount INTEGER NOT NULL,

           domain TEXT NOT NULL,

           time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
       );
   """
    )

    await db.execute(
        f"""
       CREATE TABLE nostrnip5.addresses (
           id TEXT PRIMARY KEY,
           domain_id TEXT NOT NULL,

           local_part TEXT NOT NULL,
           pubkey TEXT NOT NULL,
           
           active BOOLEAN NOT NULL DEFAULT false,

           time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},

           FOREIGN KEY(domain_id) REFERENCES {db.references_schema}domains(id)
        );
   """
    )
