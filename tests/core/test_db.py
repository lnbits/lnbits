import pytest
import pytest_asyncio

from lnbits.db import QueryValues


@pytest_asyncio.fixture
async def json_test_table(db):
    try:
        await db.execute("CREATE TABLE test (data JSON)")
        yield db
    finally:
        await db.execute("DROP TABLE test")


@pytest.mark.asyncio
async def test_sql_json(db, json_test_table):
    obj = {"a": 3, "b": "bar", "c": {"nested": "d"}}
    another_obj = {"a": 2, "b": "baz"}

    await db.execute("INSERT INTO test VALUES(?)", (obj,))
    await db.execute("INSERT INTO test VALUES(?)", (another_obj,))

    values = QueryValues()
    rows = await db.fetchall(
        f"""
        SELECT * FROM test WHERE {values.json_path('data', 'a', type_=int)} >= {values(obj["a"])}
        """,
        values,
    )
    assert len(rows) == 1
    assert rows[0].data == obj

    values = QueryValues()
    rows = await db.fetchall(
        f"SELECT * FROM test WHERE {values.json_path('data', 'c', 'nested')} = {values(obj['c']['nested'])}",
        values,
    )
    assert len(rows) == 1
    assert rows[0].data == obj

    values = QueryValues()
    rows = await db.fetchall(
        f"SELECT * FROM test WHERE {values.json_path('data', 'b')} != {values(obj['b'])}",
        values,
    )
    assert len(rows) == 1
    assert rows[0].data == another_obj

    update = {"b": "baz"}
    obj |= update
    values = QueryValues()
    await db.execute(
        f"UPDATE test SET {values.json_partial_update('data', update)}", values
    )
    row = await db.fetchone("SELECT * FROM test")
    assert row.data == obj


@pytest.mark.asyncio
async def test_sql_json_null(db, json_test_table):
    await db.execute("INSERT INTO test VALUES(?)", (None,))
    row = await db.fetchone("SELECT * FROM test")
    assert row.data is None
