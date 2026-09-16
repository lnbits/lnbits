import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from lnbits.core.migrations import m051_unique_active_fiat_wallet_currency
from lnbits.db import SQLITE, Connection


@pytest.mark.anyio
@pytest.mark.parametrize("conflict", [None, "", "sats", "invalid", "EUR"])
async def test_fiat_wallet_migration_rejects_conflicts_before_updates(conflict):
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.connect() as connection:
            db = Connection(connection, SQLITE, "test", None)
            await db.execute("""
                CREATE TABLE wallets (
                    id TEXT, "user" TEXT, currency TEXT,
                    wallet_type TEXT, deleted BOOLEAN
                )
            """)
            await db.execute(
                """INSERT INTO wallets VALUES
                    ('first', 'owner', ' eur ', 'fiat', false),
                    ('second', 'owner', :currency, 'fiat', false)""",
                {"currency": conflict},
            )

            with pytest.raises(ValueError, match="previous release before upgrading"):
                await m051_unique_active_fiat_wallet_currency(db)

            wallet = await db.fetchone(
                "SELECT currency FROM wallets WHERE id = 'first'"
            )
            assert wallet["currency"] == " eur "
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_fiat_wallet_migration_normalizes_deleted_wallets_and_enforces_uniqueness(
    settings,
):
    settings.lnbits_allowed_currencies = ["USD"]
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.connect() as connection:
            db = Connection(connection, SQLITE, "test", None)
            await db.execute("""
                CREATE TABLE wallets (
                    id TEXT, "user" TEXT, currency TEXT,
                    wallet_type TEXT, deleted BOOLEAN
                )
            """)
            await db.execute("""
                INSERT INTO wallets VALUES
                    ('first', 'owner', ' eur ', 'fiat', false),
                    ('deleted', 'owner', ' eur ', 'fiat', true),
                    ('other', 'other-owner', 'EUR', 'fiat', false),
                    ('lightning', 'owner', ' eur ', 'lightning', false)
            """)

            await m051_unique_active_fiat_wallet_currency(db)
            wallets = await db.fetchall("SELECT id, currency FROM wallets")
            assert {wallet["id"]: wallet["currency"] for wallet in wallets} == {
                "first": "EUR",
                "deleted": "EUR",
                "other": "EUR",
                "lightning": " eur ",
            }
            with pytest.raises(IntegrityError):
                await db.execute(
                    "UPDATE wallets SET deleted = false WHERE id = 'deleted'"
                )
    finally:
        await engine.dispose()
