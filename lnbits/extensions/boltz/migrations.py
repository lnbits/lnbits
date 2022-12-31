async def m001_initial(db):
    await db.execute(
        f"""
        CREATE TABLE boltz.submarineswap (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            payment_hash TEXT NOT NULL,
            amount {db.big_int} NOT NULL,
            status TEXT NOT NULL,
            boltz_id TEXT NOT NULL,
            refund_address TEXT NOT NULL,
            refund_privkey TEXT NOT NULL,
            expected_amount {db.big_int} NOT NULL,
            timeout_block_height INT NOT NULL,
            address TEXT NOT NULL,
            bip21 TEXT NOT NULL,
            redeem_script TEXT NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE boltz.reverse_submarineswap (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            onchain_address TEXT NOT NULL,
            amount {db.big_int} NOT NULL,
            instant_settlement BOOLEAN NOT NULL,
            status TEXT NOT NULL,
            boltz_id TEXT NOT NULL,
            timeout_block_height INT NOT NULL,
            redeem_script TEXT NOT NULL,
            preimage TEXT NOT NULL,
            claim_privkey TEXT NOT NULL,
            lockup_address TEXT NOT NULL,
            invoice TEXT NOT NULL,
            onchain_amount {db.big_int} NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )


async def m002_auto_swaps(db):
    await db.execute(
        """
        CREATE TABLE boltz.auto_reverse_submarineswap (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            onchain_address TEXT NOT NULL,
            amount INT NOT NULL,
            balance INT NOT NULL,
            instant_settlement BOOLEAN NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
