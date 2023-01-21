from lnbits.db import Database

db2 = Database("ext_lnurlpos")


async def m001_initial(db):
    """
    Initial lnurldevice table.
    """
    await db.execute(
        f"""
        CREATE TABLE lnurldevice.lnurldevices (
            id TEXT NOT NULL PRIMARY KEY,
            key TEXT NOT NULL,
            title TEXT NOT NULL,
            wallet TEXT NOT NULL,
            currency TEXT NOT NULL,
            device TEXT NOT NULL,
            profit FLOAT NOT NULL,
            timestamp TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )
    await db.execute(
        f"""
        CREATE TABLE lnurldevice.lnurldevicepayment (
            id TEXT NOT NULL PRIMARY KEY,
            deviceid TEXT NOT NULL,
            payhash TEXT,
            payload TEXT NOT NULL,
            pin INT,
            sats {db.big_int},
            timestamp TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m002_redux(db):
    """
    Moves everything from lnurlpos to lnurldevice
    """
    try:
        for row in [
            list(row) for row in await db2.fetchall("SELECT * FROM lnurlpos.lnurlposs")
        ]:
            await db.execute(
                """
                INSERT INTO lnurldevice.lnurldevices (
                    id,
                    key,
                    title,
                    wallet,
                    currency,
                    device,
                    profit
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (row[0], row[1], row[2], row[3], row[4], "pos", 0),
            )
        for row in [
            list(row)
            for row in await db2.fetchall("SELECT * FROM lnurlpos.lnurlpospayment")
        ]:
            await db.execute(
                """
                INSERT INTO lnurldevice.lnurldevicepayment (
                    id,
                    deviceid,
                    payhash,
                    payload,
                    pin,
                    sats
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (row[0], row[1], row[3], row[4], row[5], row[6]),
            )
    except:
        return


async def m003_redux(db):
    """
    Add 'meta' for storing various metadata about the wallet
    """
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN amount INT DEFAULT 0;"
    )


async def m004_redux(db):
    """
    Add 'meta' for storing various metadata about the wallet
    """
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN pin INT DEFAULT 0"
    )

    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN profit1 FLOAT DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN amount1 INT DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN pin1 INT DEFAULT 0"
    )

    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN profit2 FLOAT DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN amount2 INT DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN pin2 INT DEFAULT 0"
    )

    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN profit3 FLOAT DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN amount3 INT DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN pin3 INT DEFAULT 0"
    )

    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN profit4 FLOAT DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN amount4 INT DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE lnurldevice.lnurldevices ADD COLUMN pin4 INT DEFAULT 0"
    )
