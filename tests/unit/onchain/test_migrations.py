from pathlib import Path

import pytest

from lnbits.core import migrations
from lnbits.core.crud.db_versions import get_db_version, update_migration_version
from lnbits.core.helpers import run_migration
from lnbits.db import DB_TYPE, SQLITE, Database
from lnbits.settings import Settings

TABLE_QUERIES = {
    "onchain_accounts": "SELECT * FROM onchain_accounts",
    "onchain_addresses": "SELECT * FROM onchain_addresses",
    "onchain_config": "SELECT * FROM onchain_config",
    "onchain_keys": "SELECT * FROM onchain_keys",
    "onchain_snapshots": "SELECT * FROM onchain_snapshots",
    "onchain_sync": "SELECT * FROM onchain_sync",
    "wallets": "SELECT * FROM wallets",
}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("version", "existing_schema"),
    [(50, "missing"), (51, "missing"), (51, "complete"), (51, "partial")],
)
async def test_onchain_schema_upgrade_preserves_existing_data(
    tmp_path: Path, settings: Settings, version: int, existing_schema: str
):
    if DB_TYPE != SQLITE:
        pytest.skip("temporary migration database is SQLite-only")

    settings.lnbits_data_folder = str(tmp_path)
    db = Database("onchain_migration")
    try:
        async with db.connect() as conn:
            await migrations.m000_create_migrations_table(conn)
            await conn.execute("""
                CREATE TABLE wallets (
                    id TEXT PRIMARY KEY,
                    wallet_type TEXT NOT NULL,
                    deleted BOOLEAN NOT NULL DEFAULT false
                )
            """)
            await conn.execute(
                "INSERT INTO wallets (id, wallet_type) VALUES ('wallet', 'onchain')"
            )
            await update_migration_version(conn, "core", version)

            if existing_schema != "missing":
                await migrations.m051_core_onchain_wallets(conn)
                await conn.execute("""
                    INSERT INTO onchain_accounts (
                        id, wallet_id, masterpub, fingerprint, title, network
                    ) VALUES ('account', 'wallet', 'descriptor', '00000000',
                              'Existing account', 'Testnet4')
                """)
                await conn.execute("""
                    INSERT INTO onchain_addresses (
                        id, wallet, address, amount, branch_index, address_index
                    ) VALUES ('address', 'account', 'test-address', 12345, 0, 0)
                """)
                await conn.execute("""
                    INSERT INTO onchain_keys (wallet, encrypted_seed)
                    VALUES ('account', 'test-ciphertext')
                """)
                await conn.execute("""
                    INSERT INTO onchain_snapshots (address_id, transactions, utxos)
                    VALUES ('address', '[{"txid":"test-transaction"}]', '[]')
                """)
                if existing_schema == "partial":
                    await conn.execute("DROP TABLE onchain_sync")
                    await conn.execute("DROP TABLE onchain_config")

            existing_tables = {
                row["name"]
                for row in await conn.fetchall(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            preserved = {
                table: await conn.fetchall(query)
                for table, query in TABLE_QUERIES.items()
                if table in existing_tables
            }

            await run_migration(
                conn, migrations, "core", await get_db_version("core", conn)
            )
            migrated = await get_db_version("core", conn)
            assert migrated is not None and migrated.version == 53
            # Restarting after the upgrade must also be safe.
            await run_migration(conn, migrations, "core", migrated)

            indexes = await conn.fetchall("PRAGMA index_list(onchain_accounts)")
            assert any(
                index["name"] == "idx_onchain_accounts_wallet_id" and index["unique"]
                for index in indexes
            )

            for table, query in TABLE_QUERIES.items():
                assert await conn.fetchall(query) == preserved.get(table, [])

            # Exercise the query that failed in the background scanner.
            wallets = await conn.fetchall("""
                SELECT DISTINCT w.id FROM wallets w
                JOIN onchain_accounts a ON a.wallet_id = w.id
                WHERE w.wallet_type = 'onchain' AND w.deleted = false
            """)
            assert len(wallets) == (0 if existing_schema == "missing" else 1)
    finally:
        await db.engine.dispose()
