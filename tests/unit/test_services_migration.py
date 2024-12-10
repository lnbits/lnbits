import pytest

from lnbits.core.services import delete_table_column
from lnbits.db import Connection


@pytest.mark.asyncio
async def test_migration_delete_column(db: Connection):
    table_name = "test_service_delete_column"
    await db.execute(f"DROP TABLE IF EXISTS {table_name}")
    await db.execute(
        f"""
        CREATE TABLE {table_name} (
            id TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            delete_me TEXT NOT NULL
        )
        """
    )
    result = await db.execute(f"SELECT * FROM {table_name} WHERE false")
    columns = result.mappings().keys()
    assert "id" in columns
    assert "value" in columns
    assert "delete_me" in columns

    await delete_table_column(
        db,
        table=table_name,
        table_name=table_name,
        columns_to_keep=["id", "value"],
    )
    result = await db.execute(f"SELECT * FROM {table_name} WHERE true")
    columns = result.mappings().keys()
    assert "id" in columns
    assert "value" in columns
    assert "delete_me" not in columns

    await db.execute(f"DROP TABLE IF EXISTS {table_name}")
