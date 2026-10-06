from pathlib import Path

import pytest

from lnbits.core import migrations
from lnbits.core.crud.db_versions import get_db_version, update_migration_version
from lnbits.core.helpers import run_migration
from lnbits.db import DB_TYPE, SQLITE, Database
from lnbits.settings import Settings


@pytest.mark.anyio
@pytest.mark.parametrize("current_version", [51, 52])
async def test_onchain_schema_uses_wallets_and_addresses(
    tmp_path: Path, settings: Settings, current_version: int
):
    if DB_TYPE != SQLITE:
        pytest.skip("temporary migration database is SQLite-only")

    settings.lnbits_data_folder = str(tmp_path)
    db = Database("onchain_migration")
    try:
        async with db.connect() as conn:
            await migrations.m000_create_migrations_table(conn)
            await conn.execute("CREATE TABLE accounts (id TEXT PRIMARY KEY)")
            await conn.execute("""
                CREATE TABLE wallets (
                    id TEXT PRIMARY KEY,
                    wallet_type TEXT NOT NULL,
                    deleted BOOLEAN NOT NULL DEFAULT false
                )
            """)
            await conn.execute(
                "INSERT INTO wallets (id, wallet_type) VALUES ('existing', 'lightning')"
            )
            if current_version == 52:
                await migrations.m052_core_onchain_wallets(conn)
            await update_migration_version(conn, "core", current_version)
            await run_migration(
                conn, migrations, "core", await get_db_version("core", conn)
            )
            migrated = await get_db_version("core", conn)
            assert migrated is not None and migrated.version == 54
            await run_migration(conn, migrations, "core", migrated)

            tables = {
                row["name"]
                for row in await conn.fetchall(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
                if row["name"].startswith("onchain_")
            }
            assert tables == {"onchain_addresses"}
            columns = {
                row["name"] for row in await conn.fetchall("PRAGMA table_info(wallets)")
            }
            assert {column for column in columns if column.startswith("onchain_")} == {
                "onchain_network",
                "onchain_meta",
                "onchain_config",
                "onchain_wallet_kind",
                "onchain_address_no",
                "onchain_encrypted_seed",
                "onchain_sync_lease_until",
            }
            existing = await conn.fetchone(
                "SELECT * FROM wallets WHERE id = 'existing'"
            )
            assert existing["wallet_type"] == "lightning"
            assert existing["onchain_wallet_kind"] is None
            assert existing["onchain_encrypted_seed"] is None
            assert existing["onchain_meta"] == "{}"
            assert existing["onchain_config"] == "{}"
            foreign_keys = await conn.fetchall(
                "PRAGMA foreign_key_list(onchain_addresses)"
            )
            assert not foreign_keys
            await conn.execute(
                "INSERT INTO wallets (id, wallet_type) VALUES ('onchain', 'onchain')"
            )
            await conn.execute("""
                INSERT INTO onchain_addresses
                    (id, walet_id, address, branch_index, address_index)
                VALUES ('address', 'onchain', 'test-address', 0, 0)
            """)
            address = await conn.fetchone("SELECT * FROM onchain_addresses")
            assert address["walet_id"] == "onchain"
            assert address["transactions"] == "[]"
            assert address["utxos"] == "[]"
            assert address["snapshot_checked_at"] == 0
    finally:
        await db.engine.dispose()
