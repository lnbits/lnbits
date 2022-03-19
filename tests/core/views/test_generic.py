import pytest
from lnbits.core.crud import get_wallet

<<<<<<< HEAD

=======
# check if the client is working
>>>>>>> 76eed47c (more tests)
@pytest.mark.asyncio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200


# check /api/v1/wallet: wallet info
@pytest.mark.asyncio
async def test_wallet(client, inkey_headers):
    response = await client.get("/api/v1/wallet", headers=inkey_headers)
    assert response.status_code < 300


# check /api/v1/payments: invoice creation
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


# check /api/v1/payments: make payment
@pytest.mark.asyncio
async def test_core_pay_invoice(client, user_wallet, invoice, adminkey_headers):
    user, wallet = user_wallet
    wal = await get_wallet(wallet.id)
    print(wal)
    print(invoice)
    data = {"out": True, "bolt11": invoice["payment_request"]}
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers
    )
    wal = await get_wallet(wallet.id)
    print(wal)
    assert response.status_code < 300
    assert invoice


# # check /api/v1/payments: payment with wrong key [should fail]
# @pytest.mark.asyncio
# async def test_core_pay_invoice_wrong_key(client, invoice, adminkey_headers):
#     data = {"out": True, "bolt11": invoice["payment_request"]}
#     print(data)
#     adminkey_headers["X-Api-Key"] = "wrong_key"
#     response = await client.post(
#         "/api/v1/payments", json=data, headers=adminkey_headers
#     )
#     assert response.status_code > 300
