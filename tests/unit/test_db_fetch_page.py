import pytest

from lnbits.db import Filters
from tests.helpers import DbTestModel

TEST_DB_FETCH_PAGE_ROWS: tuple[dict[str, str], ...] = (
    {"id": "1", "name": "Alice", "value": "foo"},
    {"id": "2", "name": "Bob", "value": "bar"},
    {"id": "3", "name": "Carol", "value": "bar"},
    {"id": "4", "name": "Dave", "value": "bar"},
    {"id": "5", "name": "Dave", "value": "foo"},
    {"id": "6", "name": "Eve", "value": "foo"},
    {"id": "7", "name": "Frank", "value": "bar"},
    {"id": "8", "name": "Grace", "value": "foo"},
    {"id": "9", "name": "Heidi", "value": "bar"},
    {"id": "10", "name": "Ivan", "value": "foo"},
    {"id": "11", "name": "Judy", "value": "bar"},
    {"id": "12", "name": "Mallory", "value": "foo"},
    {"id": "13", "name": "Niaj", "value": "bar"},
    {"id": "14", "name": "Olivia", "value": "foo"},
    {"id": "15", "name": "Peggy", "value": "bar"},
    {"id": "16", "name": "Rupert", "value": "foo"},
    {"id": "17", "name": "Sybil", "value": "bar"},
    {"id": "18", "name": "Trent", "value": "foo"},
    {"id": "19", "name": "Victor", "value": "bar"},
    {"id": "20", "name": "Walter", "value": "foo"},
    {"id": "21", "name": "Zoe", "value": "bar"},
)


@pytest.fixture(scope="session")
async def fetch_page(db):
    await db.execute("DROP TABLE IF EXISTS test_db_fetch_page")
    await db.execute("""
        CREATE TABLE test_db_fetch_page (
            id TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            name TEXT NOT NULL
        )
        """)
    for row in TEST_DB_FETCH_PAGE_ROWS:
        await db.execute(
            """
            INSERT INTO test_db_fetch_page (id, name, value)
            VALUES (:id, :name, :value)
            """,
            row,
        )
    yield
    await db.execute("DROP TABLE test_db_fetch_page")


@pytest.mark.anyio
async def test_db_fetch_page_simple(fetch_page, db):
    row = await db.fetch_page(
        query="select * from test_db_fetch_page",
        model=DbTestModel,
    )

    assert row
    assert row.total == len(TEST_DB_FETCH_PAGE_ROWS)
    assert len(row.data) == Filters().limit


@pytest.mark.anyio
async def test_db_fetch_page_limit_zero_returns_all(fetch_page, db):
    row = await db.fetch_page(
        query="select * from test_db_fetch_page",
        filters=Filters(limit=0),
        model=DbTestModel,
    )

    assert row
    assert row.total == len(TEST_DB_FETCH_PAGE_ROWS)
    assert len(row.data) == len(TEST_DB_FETCH_PAGE_ROWS)


@pytest.mark.anyio
async def test_db_fetch_page_group_by(fetch_page, db):
    row = await db.fetch_page(
        query="select max(id) as id, name from test_db_fetch_page",
        model=DbTestModel,
        group_by=["name"],
    )
    assert row
    assert row.total == len({test_row["name"] for test_row in TEST_DB_FETCH_PAGE_ROWS})


@pytest.mark.anyio
async def test_db_fetch_page_group_by_multiple(fetch_page, db):
    row = await db.fetch_page(
        query="select max(id) as id, name, value from test_db_fetch_page",
        model=DbTestModel,
        group_by=["value", "name"],
    )
    assert row
    assert row.total == len(
        {(test_row["value"], test_row["name"]) for test_row in TEST_DB_FETCH_PAGE_ROWS}
    )


@pytest.mark.anyio
async def test_db_fetch_page_group_by_evil(fetch_page, db):
    with pytest.raises(ValueError, match="Value for GROUP BY is invalid"):
        await db.fetch_page(
            query="select * from test_db_fetch_page",
            model=DbTestModel,
            group_by=["name;"],
        )
