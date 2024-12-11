import pytest

from lnbits.core.models import Payment


# check if the client is working
@pytest.mark.anyio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200


# check GET /public/v1/payment/{payment_hash}: correct hash [should pass]
@pytest.mark.anyio
async def test_api_public_payment_longpolling(client, invoice: Payment):
    response = await client.get(f"/public/v1/payment/{invoice.payment_hash}")
    assert response.status_code < 300
    assert response.json()["status"] == "paid"


# check GET /public/v1/payment/{payment_hash}: wrong hash [should fail]
@pytest.mark.anyio
async def test_api_public_payment_longpolling_wrong_hash(client, invoice: Payment):
    response = await client.get(f"/public/v1/payment/{invoice.payment_hash + '0'*64}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment does not exist."
