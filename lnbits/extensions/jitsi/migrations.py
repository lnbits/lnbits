async def m006_initial(db):         # TODO(nochiel) Reset this to m001 when ready to PR.

    await db.execute(
            """
            CREATE TABLE jitsi.conferences (
                "name" TEXT NOT NULL,
                admin TEXT REFERENCES accounts(id),
                PRIMARY KEY(name, admin)
                );
            """
            )

    await db.execute(
            """
            CREATE TABLE jitsi.participants (
                id TEXT PRIMARY KEY,
                user TEXT REFERENCES accounts(id),
                conference TEXT REFERENCES 'jitsi.conferences(name)',
                wallet TEXT REFERENCES wallets(id)
                );
            """
            )
