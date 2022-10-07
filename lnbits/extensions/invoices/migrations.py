async def m001_initial_invoices(db):

    # STATUS COLUMN OPTIONS: 'draft', 'open', 'paid', 'canceled'

    await db.execute(
        f"""
       CREATE TABLE invoices.invoices (
           id TEXT PRIMARY KEY,
           wallet TEXT NOT NULL,

           status TEXT NOT NULL DEFAULT 'draft',

           currency TEXT NOT NULL,

           company_name TEXT DEFAULT NULL,
           first_name TEXT DEFAULT NULL,
           last_name TEXT DEFAULT NULL,
           email TEXT DEFAULT NULL,
           phone TEXT DEFAULT NULL,
           address TEXT DEFAULT NULL,


           time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
       );
   """
    )

    await db.execute(
        f"""
       CREATE TABLE invoices.invoice_items (
           id TEXT PRIMARY KEY,
           invoice_id TEXT NOT NULL,

           description TEXT NOT NULL,
           amount INTEGER NOT NULL,

           FOREIGN KEY(invoice_id) REFERENCES {db.references_schema}invoices(id)
        );
   """
    )

    await db.execute(
        f"""
       CREATE TABLE invoices.payments (
           id TEXT PRIMARY KEY,
           invoice_id TEXT NOT NULL,

           amount {db.big_int} NOT NULL,

           time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},

           FOREIGN KEY(invoice_id) REFERENCES {db.references_schema}invoices(id)
       );
   """
    )
