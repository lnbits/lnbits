import pytest


@pytest.mark.asyncio
async def test_admin_index(client, adminkey_headers_to):
    response = await client.get("/admin/api/v1/", headers=adminkey_headers_to)
    assert response.status_code == 200
    # result = response.json()
