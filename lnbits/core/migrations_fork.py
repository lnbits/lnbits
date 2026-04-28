"""
Fork-specific database migrations.

Forks of LNbits that need to add their own schema changes (extra columns,
tables, indexes, etc.) can add migrations to this file. They are tracked
separately under the 'core_fork' key in the dbversions table, so they do not
collide with upstream's `core` migrations when pulling from upstream.

Conventions:
  - Use sequential numbering starting from m001.
  - Each migration is `async def m{NNN}_<description>(db: Connection)`.
  - Wrap idempotent DDL (e.g. ALTER TABLE ADD COLUMN) in a try/except for
    `OperationalError` so re-runs on partially-migrated databases don't fail.

This file is intentionally empty in upstream. Forks fill it in.
"""

# Example (uncomment and adapt in your fork):
#
# from sqlalchemy.exc import OperationalError
#
# from lnbits.db import Connection
#
#
# async def m001_add_custom_column_to_accounts(db: Connection):
#     """Adds a fork-specific column to the accounts table."""
#     try:
#         await db.execute("ALTER TABLE accounts ADD COLUMN my_column TEXT")
#     except OperationalError:
#         pass
