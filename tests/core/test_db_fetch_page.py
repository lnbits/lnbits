import pytest
import pytest_asyncio

from lnbits.db import FromRowModel


class TestModel(FromRowModel):
    id: int
    name: str


@pytest_asyncio.fixture(scope="session")
async def fetch_page(db):
    await db.execute("DROP TABLE IF EXISTS test_db_fetch_page")
    await db.execute(
        """
        CREATE TABLE test_db_fetch_page (
            id TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            name TEXT NOT NULL
        )
        """
    )
    await db.execute(
        """
        INSERT INTO test_db_fetch_page (id, name, value) VALUES
            ('1', 'Alice', 'foo'),
            ('2', 'Bob', 'bar'),
            ('3', 'Carol', 'bar'),
            ('4', 'Dave', 'bar'),
            ('5', 'Dave', 'foo')
        """
    )
    yield
    await db.execute("DROP TABLE test_db_fetch_page")


@pytest.mark.asyncio
async def test_db_fetch_page_simple(fetch_page, db):
    row = await db.fetch_page(
        query="select * from test_db_fetch_page",
        model=TestModel,
    )

    assert row
    assert row.total == 5
    assert len(row.data) == 5


@pytest.mark.asyncio
async def test_db_fetch_page_group_by(fetch_page, db):
    row = await db.fetch_page(
        query="select max(id) as id, name from test_db_fetch_page",
        model=TestModel,
        group_by=["name"],
    )
    assert row
    assert row.total == 4


@pytest.mark.asyncio
async def test_db_fetch_page_group_by_multiple(fetch_page, db):
    row = await db.fetch_page(
        query="select max(id) as id, name, value from test_db_fetch_page",
        model=TestModel,
        group_by=["value", "name"],
    )
    assert row
    assert row.total == 5


@pytest.mark.asyncio
async def test_db_fetch_page_group_by_evil(fetch_page, db):
    with pytest.raises(ValueError, match="Value for GROUP BY is invalid"):
        await db.fetch_page(
            query="select * from test_db_fetch_page",
            model=TestModel,
            group_by=["name;"],
        )
