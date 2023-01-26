import pytest

from tests.helpers import is_fake


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this test is only passes with regtest")
async def test_mempool_url(client):
    response = await client.get("/boltz/api/v1/swap/mempool")
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this test is only passes with regtest")
async def test_boltz_config(client):
    response = await client.get("/boltz/api/v1/swap/boltz")
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this test is only passes with regtest")
async def test_endpoints_unauthenticated(client):
    response = await client.get("/boltz/api/v1/swap?all_wallets=true")
    assert response.status_code == 401
    response = await client.get("/boltz/api/v1/swap/reverse?all_wallets=true")
    assert response.status_code == 401
    response = await client.post("/boltz/api/v1/swap")
    assert response.status_code == 401
    response = await client.post("/boltz/api/v1/swap/reverse")
    assert response.status_code == 401
    response = await client.post("/boltz/api/v1/swap/status")
    assert response.status_code == 401
    response = await client.post("/boltz/api/v1/swap/check")
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this test is only passes with regtest")
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
@pytest.mark.skipif(is_fake, reason="this test is only passes with regtest")
async def test_endpoints_adminkey_badrequest(client, adminkey_headers_to):
    response = await client.post("/boltz/api/v1/swap", headers=adminkey_headers_to)
    assert response.status_code == 400
    response = await client.post(
        "/boltz/api/v1/swap/reverse", headers=adminkey_headers_to
    )
    assert response.status_code == 400
    response = await client.post(
        "/boltz/api/v1/swap/refund", headers=adminkey_headers_to
    )
    assert response.status_code == 400
    response = await client.post(
        "/boltz/api/v1/swap/status", headers=adminkey_headers_to
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this test is only passes with regtest")
async def test_endpoints_adminkey_regtest(client, from_wallet, adminkey_headers_to):
    swap = {
        "wallet": from_wallet.id,
        "refund_address": "bcrt1q3cwq33y435h52gq3qqsdtczh38ltlnf69zvypm",
        "amount": 50_000,
    }
    response = await client.post(
        "/boltz/api/v1/swap", json=swap, headers=adminkey_headers_to
    )
    assert response.status_code == 201

    reverse_swap = {
        "wallet": from_wallet.id,
        "instant_settlement": True,
        "onchain_address": "bcrt1q4vfyszl4p8cuvqh07fyhtxve5fxq8e2ux5gx43",
        "amount": 50_000,
    }
    response = await client.post(
        "/boltz/api/v1/swap/reverse", json=reverse_swap, headers=adminkey_headers_to
    )
    assert response.status_code == 201
