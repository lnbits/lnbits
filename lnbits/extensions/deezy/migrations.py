async def m001_initial(db):
    await db.execute(
        f"""
        CREATE TABLE deezy.ln_to_btc_swap (
            id TEXT PRIMARY KEY,
            amount_sats {db.big_int} NOT NULL,
            on_chain_address TEXT NOT NULL,
            on_chain_sats_per_vbyte INT NOT NULL,
            bolt11_invoice TEXT NOT NULL,
            fee_sats {db.big_int} NOT NULL,
            txid TEXT NULL,
            tx_hex TEXT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await db.execute(
        """
        CREATE TABLE deezy.btc_to_ln_swap (
            id TEXT PRIMARY KEY,
            ln_address TEXT NOT NULL,
            on_chain_address TEXT NOT NULL,
            secret_access_key TEXT NOT NULL,
            commitment TEXT NOT NULL,
            signature TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await db.execute(
        """
        CREATE TABLE deezy.token (
            deezy_token TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
