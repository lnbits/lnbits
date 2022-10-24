async def m001_initial(db):
    """
    Initial lnurlpayouts table.
    """
    await db.execute(
        f"""
        CREATE TABLE lnurlpayout.lnurlpayouts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            wallet TEXT NOT NULL,
            admin_key TEXT NOT NULL,
            lnurlpay TEXT NOT NULL,
            threshold {db.big_int} NOT NULL
        );
    """
    )
