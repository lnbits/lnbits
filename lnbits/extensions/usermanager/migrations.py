from sqlalchemy.exc import OperationalError  # type: ignore

async def m001_initial(db):
    """
    Initial users table.
    """
    await db.execute(
        """
        CREATE TABLE usermanager.users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            admin TEXT NOT NULL,
            email TEXT,
            password TEXT
        );
    """
    )

    """
    Initial wallets table.
    """
    await db.execute(
        """
        CREATE TABLE usermanager.wallets (
            id TEXT PRIMARY KEY,
            admin TEXT NOT NULL,
            name TEXT NOT NULL,
            "user" TEXT NOT NULL,
            adminkey TEXT NOT NULL,
            inkey TEXT NOT NULL
        );
    """
    )

async def m002_add_fields_to_users(db):
    try:
        await db.execute("ALTER TABLE usermanager.users ADD COLUMN metadata TEXT DEFAULT '{}'")
        await db.execute("ALTER TABLE usermanager.users ADD COLUMN custom_id TEXT")
        await db.execute("CREATE UNIQUE INDEX idx_custom_id ON usermanager.users (admin,custom_id)")

    except OperationalError:
        # this is necessary now because it may be the case that this migration will
        # run twice in some environments.
        # catching errors like this won't be necessary in anymore now that we
        # keep track of db versions so no migration ever runs twice.
        pass
