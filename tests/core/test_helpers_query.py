import pytest
from pydantic import BaseModel

from lnbits.helpers import (
    insert_query,
    update_query,
)


class DbTestModel(BaseModel):
    id: int
    name: str


test = DbTestModel(id=1, name="test")


@pytest.mark.asyncio
async def test_helpers_insert_query():
    q = insert_query("test_helpers_query", test)
    assert q == "INSERT INTO test_helpers_query (id, name) VALUES (?, ?)"


@pytest.mark.asyncio
async def test_helpers_update_query():
    q = update_query("test_helpers_query", test)
    assert q == "UPDATE test_helpers_query SET id = ?, name = ? WHERE id = ?"
