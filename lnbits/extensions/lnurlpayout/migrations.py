async def m001_initial(db):
    """
    Initial lnurlpayouts table.
    """
    await db.execute(
        """
        CREATE TABLE lnurlpayout.lnurlpayouts (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            lnurlpay TEXT NOT NULL,
            threshold INT NOT NULL
        );
    """
    )
