async def m004_initial(db):         # TODO(nochiel) Reset this to m001 when ready to PR.

    await db.execute(
            """
            CREATE TABLE jitsi.conferences (
                id TEXT NOT NULL,
                admin TEXT NOT NULL
                );
            """
            )

    await db.execute(
            """
            CREATE TABLE jitsi.participants (
                id TEXT PRIMARY KEY,
                user TEXT NOT NULL,
                conference TEXT NOT NULL,
                wallet TEXT NOT NULL
                );
            """
            )


    await db.execute(
