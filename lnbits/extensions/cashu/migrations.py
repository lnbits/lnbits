async def m001_initial(db):
    """
    Initial cashu table.
    """
    await db.execute(
        """
        CREATE TABLE cashu.cashu (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL,
            tickershort TEXT DEFAULT 'sats',
            fraction BOOL,
            maxsats INT,
            coins INT,
            prvkey TEXT NOT NULL,
            pubkey TEXT NOT NULL
        );
    """
    )

    """
    Initial cashus table.
    """
    await db.execute(
        """
        CREATE TABLE cashu.pegs (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            inout BOOL NOT NULL,
            amount INT
        );
    """
    )


# async def m001_initial(db):
#     await db.execute(
#         """
#             CREATE TABLE IF NOT EXISTS cashu.promises (
#                 amount INTEGER NOT NULL,
#                 B_b TEXT NOT NULL,
#                 C_b TEXT NOT NULL,

#                 UNIQUE (B_b)

#             );
#         """
#     )

#     await db.execute(
#         """
#             CREATE TABLE IF NOT EXISTS cashu.proofs_used (
#                 amount INTEGER NOT NULL,
#                 C TEXT NOT NULL,
#                 secret TEXT NOT NULL,

#                 UNIQUE (secret)

#             );
#         """
#     )

#     await db.execute(
#         """
#             CREATE TABLE IF NOT EXISTS cashu.invoices (
#                 amount INTEGER NOT NULL,
#                 pr TEXT NOT NULL,
#                 hash TEXT NOT NULL,
#                 issued BOOL NOT NULL,

#                 UNIQUE (hash)

#             );
#         """
#     )

# await db.execute(
#     """
#     CREATE VIEW IF NOT EXISTS cashu.balance_issued AS
#     SELECT COALESCE(SUM(s), 0) AS balance FROM (
#         SELECT SUM(amount) AS s
#         FROM cashu.promises
#         WHERE amount > 0
#     );
# """
# )

# await db.execute(
#     """
#     CREATE VIEW IF NOT EXISTS cashu.balance_used AS
#     SELECT COALESCE(SUM(s), 0) AS balance FROM (
#         SELECT SUM(amount) AS s
#         FROM cashu.proofs_used
#         WHERE amount > 0
#     );
# """
# )

# await db.execute(
#     """
#     CREATE VIEW IF NOT EXISTS cashu.balance AS
#     SELECT s_issued - s_used AS balance FROM (
#         SELECT bi.balance AS s_issued, bu.balance AS s_used
#         FROM cashu.balance_issued bi
#         CROSS JOIN balance_used bu
#     );
# """
# )


# async def m003_mint_keysets(db):
#     """
#     Stores mint keysets from different mints and epochs.
#     """
#     await db.execute(
#         f"""
#             CREATE TABLE IF NOT EXISTS cashu.keysets (
#                 id TEXT NOT NULL,
#                 derivation_path TEXT,
#                 valid_from TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
#                 valid_to TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
#                 first_seen TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
#                 active BOOL DEFAULT TRUE,

#                 UNIQUE (derivation_path)

#             );
#         """
#     )
#     await db.execute(
#         f"""
#             CREATE TABLE IF NOT EXISTS cashu.mint_pubkeys (
#                 id TEXT NOT NULL,
#                 amount INTEGER NOT NULL,
#                 pubkey TEXT NOT NULL,

#                 UNIQUE (id, pubkey)

#             );
#         """
#     )


# async def m004_keysets_add_version(db):
#     """
#     Column that remembers with which version
#     """
#     await db.execute("ALTER TABLE cashu.keysets ADD COLUMN version TEXT")
