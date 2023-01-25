async def m001_initial(db):
    """
    Initial nostrrelays table.
    """
    await db.execute(
        """
        CREATE TABLE nostrrelay.nostrrelays (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            currency TEXT NOT NULL
        );
    """
    )


async def m002_addtip_wallet(db):
    """
    Add tips to nostrrelays table
    """
    await db.execute(
        """
        ALTER TABLE nostrrelay.nostrrelays ADD tip_wallet TEXT NULL;
    """
    )


async def m003_addtip_options(db):
    """
    Add tips to nostrrelays table
    """
    await db.execute(
        """
        ALTER TABLE nostrrelay.nostrrelays ADD tip_options TEXT NULL;
    """
    )
