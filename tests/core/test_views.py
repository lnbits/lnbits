import pytest


@pytest.mark.asyncio
async def test_homepage(client):
    r = await client.get("/")
    assert b"Add a new wallet" in await r.get_data()
