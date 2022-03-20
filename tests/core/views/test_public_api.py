import pytest
from lnbits.core.crud import get_wallet

# check if the client is working
@pytest.mark.asyncio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200


# check GET /public/v1/payment/{payment_hash}: correct hash [should pass]
@pytest.mark.asyncio
async def test_api_public_payment_longpolling(client, invoice):
    response = await client.get(f"/public/v1/payment/{invoice['payment_hash']}")
    assert response.status_code < 300
    assert response.json()["status"] == "paid"


# check GET /public/v1/payment/{payment_hash}: wrong hash [should fail]
@pytest.mark.asyncio
async def test_api_public_payment_longpolling_wrong_hash(client, invoice):
    response = await client.get(
        f"/public/v1/payment/{invoice['payment_hash'] + '0'*64}"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment does not exist."


# check GET /.well-known/lnurlp/{username}: wrong username [should fail]
@pytest.mark.asyncio
async def test_lnaddress_wrong_hash(client):
    username = "wrong_name"
    response = await client.get(f"/.well-known/lnurlp/{username}")
    assert response.status_code == 200
    assert response.json()["status"] == "ERROR"
    assert response.json()["reason"] == "Address not found."
