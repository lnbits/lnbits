import pytest


@pytest.mark.asyncio
async def test_sql_json(db, json_test_table):
    obj = {"a": "foo", "b": "bar", "c": {"nested": "d"}}
    await db.execute("INSERT INTO test VALUES(?)", (obj,))

    row = await db.fetchone(
        f"SELECT * FROM test WHERE {db.json_path('data', 'a')} = ?",
        (obj["a"],),
    )
    assert row.data == obj

    row = await db.fetchone(
        f"SELECT * FROM test WHERE {db.json_path('data', 'c', 'nested')} = ?",
        (obj["c"]["nested"],),
    )
    assert row.data == obj

    row = await db.fetchone(
        f"SELECT * FROM test WHERE {db.json_path('data', 'b')} != ?", (obj["b"],)
    )
    assert not row

    update = {"b": "baz"}
    obj |= update
    await db.execute(f"UPDATE test SET {db.json_partial_update('data')}", (update,))
    row = await db.fetchone("SELECT * FROM test")
    assert row.data == obj
