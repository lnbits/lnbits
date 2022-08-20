import pytest
import pytest_asyncio

from tests.helpers import is_regtest


@pytest.mark.asyncio
async def test_mempool_url(client):
    response = await client.get("/boltz/api/v1/swap/mempool")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_boltz_config(client):
    if is_regtest:
        response = await client.get("/boltz/api/v1/swap/boltz")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_endpoints_inkey(client, inkey_headers_to):
    response = await client.get(
        "/boltz/api/v1/swap?all_wallets=true", headers=inkey_headers_to
    )
    assert response.status_code == 200
    response = await client.get(
        "/boltz/api/v1/swap/reverse?all_wallets=true", headers=inkey_headers_to
    )
    assert response.status_code == 200
    response = await client.post("/boltz/api/v1/swap", headers=inkey_headers_to)
    assert response.status_code == 401
    response = await client.post("/boltz/api/v1/swap/reverse", headers=inkey_headers_to)
    assert response.status_code == 401
    response = await client.post("/boltz/api/v1/swap/refund", headers=inkey_headers_to)
    assert response.status_code == 401
    response = await client.post("/boltz/api/v1/swap/status", headers=inkey_headers_to)
    assert response.status_code == 401
    response = await client.post("/boltz/api/v1/swap/check", headers=inkey_headers_to)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_endpoints_adminkey_nocontent(client, adminkey_headers_to):
    if is_regtest:
        response = await client.post(
            "/boltz/api/v1/swap/check", headers=adminkey_headers_to
        )
        assert response.status_code == 200
        response = await client.post("/boltz/api/v1/swap", headers=adminkey_headers_to)
        assert response.status_code == 204
        response = await client.post(
            "/boltz/api/v1/swap/reverse", headers=adminkey_headers_to
        )
        assert response.status_code == 204
        response = await client.post(
            "/boltz/api/v1/swap/refund", headers=adminkey_headers_to
        )
        assert response.status_code == 204
        response = await client.post(
            "/boltz/api/v1/swap/status", headers=adminkey_headers_to
        )
        assert response.status_code == 204


# @pytest.mark.asyncio
# async def test_endpoints_adminkey(client, adminkey_headers_to):
#     if is_regtest:
#         response = await client.post("/boltz/api/v1/swap", headers=adminkey_headers_to)
#         assert response.status_code == 200
#         response = await client.post("/boltz/api/v1/swap/reverse", headers=adminkey_headers_to)
#         assert response.status_code == 200
#         response = await client.post("/boltz/api/v1/swap/refund", headers=adminkey_headers_to)
#         assert response.status_code == 200
#         response = await client.post("/boltz/api/v1/swap/status", headers=adminkey_headers_to)
#         assert response.status_code == 200


@pytest.mark.asyncio
async def test_endpoints_unauthenticated(client):
    response = await client.get("/boltz/api/v1/swap?all_wallets=true")
    assert response.status_code == 400
    response = await client.get("/boltz/api/v1/swap/reverse?all_wallets=true")
    assert response.status_code == 400
    # https://github.com/lnbits/lnbits-legend/pull/848
    # response = await client.post("/boltz/api/v1/swap")
    # assert response.status_code == 400
