import pytest
from tests.conftest import client

@pytest.mark.asyncio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200
