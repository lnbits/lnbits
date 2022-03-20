import pytest
from lnbits.core.crud import get_wallet

# check if the client is working
@pytest.mark.asyncio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200


# check GET /api/v1/wallet: wallet info
@pytest.mark.asyncio
async def test_wallet(client, inkey_headers):
    response = await client.get("/api/v1/wallet", headers=inkey_headers)
    assert response.status_code < 300


# check POST /api/v1/payments: invoice creation
@pytest.mark.asyncio
async def test_core_create_invoice(client, inkey_headers):
    data = {"out": False, "amount": 100, "memo": "test_memo"}
    response = await client.post("/api/v1/payments", json=data, headers=inkey_headers)
    assert response.status_code < 300
    assert "payment_hash" in response.json()
    assert len(response.json()["payment_hash"]) == 64
    assert "payment_request" in response.json()
    assert len(response.json()["payment_request"]) == 256
    assert "checking_id" in response.json()
    assert len(response.json()["checking_id"])
    return response.json()


# check POST /api/v1/payments: make payment
# check GET /api/v1/payments/<hash>: payment status
@pytest.mark.asyncio
async def test_core_pay_invoice(
    client, user_wallet, invoice, adminkey_headers, inkey_headers
):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers
    )
    assert response.status_code < 300
    assert len(response.json()["payment_hash"]) == 64
    assert len(response.json()["checking_id"]) > 0

    # check the payment status
    response = await client.get(
        f"/api/v1/payments/{response.json()['payment_hash']}", headers=inkey_headers
    )
    # doesn't work. why?
    # assert "details" in response.json()
    assert response.status_code < 300
    assert response.json()["paid"] == True
    assert invoice


# check POST /api/v1/payments: payment with wrong key type
@pytest.mark.asyncio
async def test_core_pay_invoice_wrong_key(client, invoice, adminkey_headers):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    # try payment with wrong key
    wrong_adminkey_headers = adminkey_headers.copy()
    wrong_adminkey_headers["X-Api-Key"] = "wrong_key"
    response = await client.post(
        "/api/v1/payments", json=data, headers=wrong_adminkey_headers
    )
    assert response.status_code >= 300  # should fail


# check POST /api/v1/payments: payment with invoice key [should fail]
@pytest.mark.asyncio
async def test_core_pay_invoice_invoicekey(client, invoice, inkey_headers):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    # try payment with invoice key
    response = await client.post("/api/v1/payments", json=data, headers=inkey_headers)
    assert response.status_code >= 300  # should fail


# check POST /api/v1/payments: payment with admin key [should pass]
@pytest.mark.asyncio
async def test_core_pay_invoice_adminkey(client, invoice, adminkey_headers):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    # try payment with admin key
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers
    )
    assert response.status_code < 300  # should pass


# check POST /api/v1/payments/decode
@pytest.mark.asyncio
async def test_core_decode_invoice(client, invoice):
    data = {"data": invoice["payment_request"]}
    response = await client.post(
        "/api/v1/payments/decode",
        json=data,
    )
    assert response.status_code < 300
    assert response.json()["payment_hash"] == invoice["payment_hash"]
