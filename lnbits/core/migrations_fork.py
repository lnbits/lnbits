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
