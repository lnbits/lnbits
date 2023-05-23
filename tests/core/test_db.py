import pytest


@pytest.mark.asyncio
async def test_sql_json(db):
    try:
        await db.execute("CREATE TABLE test (data JSON)")
        obj = {"a": 2}
        await db.execute("INSERT INTO test VALUES(?)", (obj,))
        row = await db.fetchone("SELECT * FROM test")
        assert row.data == obj
    finally:
        await db.execute("DROP TABLE test")
