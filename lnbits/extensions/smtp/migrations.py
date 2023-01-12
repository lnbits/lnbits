async def m001_initial(db):

    await db.execute(
        f"""
        CREATE TABLE smtp.emailaddress (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            email TEXT NOT NULL,
            testemail TEXT NOT NULL,
            smtp_server TEXT NOT NULL,
            smtp_user TEXT NOT NULL,
            smtp_password TEXT NOT NULL,
            smtp_port TEXT NOT NULL,
            anonymize BOOLEAN NOT NULL,
            description TEXT NOT NULL,
            cost INTEGER NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )

    await db.execute(
        f"""
        CREATE TABLE smtp.email (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            emailaddress_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            paid BOOLEAN NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m002_add_payment_hash(db):
    await db.execute(f"ALTER TABLE smtp.email ADD COLUMN payment_hash TEXT;")
