import json

import pytest

from lnbits.core import migrations
from lnbits.core.crud.db_versions import get_db_version, update_migration_version
from lnbits.core.crud.settings import get_settings_field
from lnbits.core.helpers import run_migration
from lnbits.db import DB_TYPE, SQLITE, Database


@pytest.mark.anyio
@pytest.mark.parametrize("has_super_user", [False, True])
@pytest.mark.parametrize(
    "saved_url",
    [
        None,
        "",
        "https://demo.lnbits.com/paidreviews/api/v1/AdFzLjzuKFLsdk4Bcnff6r",
        "https://reviews.example.com/api/v1/custom",
    ],
)
async def test_reviews_url_migration_resets_once(
    tmp_path, settings, has_super_user, saved_url
):
    if DB_TYPE != SQLITE:
        pytest.skip("temporary settings database is SQLite-only")

    settings.lnbits_data_folder = str(tmp_path)
    settings.lnbits_extensions_reviews_url = "https://reviews.example.com/from-env"
    db = Database("settings_migration")
    try:
        async with db.connect() as conn:
            await migrations.m000_create_migrations_table(conn)
            await conn.execute("""
                CREATE TABLE system_settings (
                    id TEXT PRIMARY KEY,
                    value TEXT,
                    tag TEXT NOT NULL DEFAULT 'core',
                    UNIQUE(id, tag)
                )
            """)
            if has_super_user:
                await conn.execute("""
                    INSERT INTO system_settings (id, value, tag)
                    VALUES ('super_user', '"admin"', 'core'),
                           ('extension_setting', '"keep"', 'extension')
                """)
            if saved_url is not None:
                await conn.execute(
                    """
                    INSERT INTO system_settings (id, value, tag)
                    VALUES ('lnbits_extensions_reviews_url', :value, 'core')
                    """,
                    {"value": json.dumps(saved_url)},
                )
            await update_migration_version(conn, "core", 57)
            await run_migration(
                conn, migrations, "core", await get_db_version("core", conn)
            )

            assert settings.lnbits_extensions_reviews_url == ""
            field = await get_settings_field("lnbits_extensions_reviews_url", conn=conn)
            if has_super_user or saved_url is not None:
                assert field is not None
                assert field.value == ""
            else:
                assert await conn.fetchall("SELECT * FROM system_settings") == []
            if has_super_user:
                admin = await get_settings_field("super_user", conn=conn)
                assert admin is not None and admin.value == "admin"
                extension = await get_settings_field(
                    "extension_setting", "extension", conn=conn
                )
                assert extension is not None and extension.value == "keep"

            # A URL configured after the migration survives subsequent startups.
            configured_url = "https://reviews.example.com/reconfigured"
            await conn.execute(
                """
                INSERT INTO system_settings (id, value, tag)
                VALUES ('lnbits_extensions_reviews_url', :value, 'core')
                ON CONFLICT (id, tag) DO UPDATE SET value = :value
                """,
                {"value": json.dumps(configured_url)},
            )
            settings.lnbits_extensions_reviews_url = configured_url
            version = await get_db_version("core", conn)
            assert version is not None and version.version == 58
            await run_migration(conn, migrations, "core", version)
            field = await get_settings_field("lnbits_extensions_reviews_url", conn=conn)
            assert field is not None and field.value == configured_url
            assert settings.lnbits_extensions_reviews_url == configured_url
    finally:
        await db.engine.dispose()
