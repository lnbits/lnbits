import pytest
import pytest_asyncio

from tests.helpers import is_fake, is_regtest


@pytest.mark.asyncio
async def test_mempool_url(client):
    response = await client.get("/boltz/api/v1/swap/mempool")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_boltz_config(client):
    response = await client.get("/boltz/api/v1/swap/boltz")
    assert response.status_code == 200


@pytest.mark.asyncio
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


@pytest.mark.asyncio
@pytest.mark.skipif(is_regtest, reason="this test is only passes with fakewallet")
async def test_endpoints_adminkey_fakewallet(client, from_wallet, adminkey_headers_to):
    response = await client.post(
        "/boltz/api/v1/swap/check", headers=adminkey_headers_to
    )
    assert response.status_code == 200
    swap = {
        "wallet": from_wallet.id,
        "refund_address": "bcrt1q3cwq33y435h52gq3qqsdtczh38ltlnf69zvypm",
        "amount": 50_000,
    }
    response = await client.post(
        "/boltz/api/v1/swap", json=swap, headers=adminkey_headers_to
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "could not find route to pay invoice"
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
    reverse_swap = response.json()
    assert reverse_swap["id"] is not None
    response = await client.post(
        "/boltz/api/v1/swap/status",
        params={"swap_id": reverse_swap["id"]},
        headers=adminkey_headers_to,
    )
    assert response.status_code == 200
    response = await client.post(
        "/boltz/api/v1/swap/status",
        params={"swap_id": "wrong"},
        headers=adminkey_headers_to,
    )
    assert response.status_code == 404
    response = await client.post(
        "/boltz/api/v1/swap/refund",
        params={"swap_id": "wrong"},
        headers=adminkey_headers_to,
    )
    assert response.status_code == 404


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
