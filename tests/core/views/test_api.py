import hashlib

import pytest
import pytest_asyncio

from lnbits import bolt11
from lnbits.core.crud import get_wallet
from lnbits.core.views.api import (
    CreateInvoiceData,
    api_payment,
    api_payments_create_invoice,
)
from lnbits.settings import get_wallet_class

from ...helpers import get_random_invoice_data, is_regtest

WALLET = get_wallet_class()

# check if the client is working
@pytest.mark.asyncio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200


# check GET /api/v1/wallet with inkey: wallet info, no balance
@pytest.mark.asyncio
async def test_get_wallet_inkey(client, inkey_headers_to):
    response = await client.get("/api/v1/wallet", headers=inkey_headers_to)
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    assert "balance" in result
    assert "id" not in result


# check GET /api/v1/wallet with adminkey: wallet info with balance
@pytest.mark.asyncio
async def test_get_wallet_adminkey(client, adminkey_headers_to):
    response = await client.get("/api/v1/wallet", headers=adminkey_headers_to)
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    assert "balance" in result
    assert "id" in result


# check PUT /api/v1/wallet/newwallet: empty request where admin key is needed
@pytest.mark.asyncio
async def test_put_empty_request_expected_admin_keys(client):
    response = await client.put("/api/v1/wallet/newwallet")
    assert response.status_code == 401


# check POST /api/v1/payments: empty request where invoice key is needed
@pytest.mark.asyncio
async def test_post_empty_request_expected_invoice_keys(client):
    response = await client.post("/api/v1/payments")
    assert response.status_code == 401


# check POST /api/v1/payments: invoice creation
@pytest.mark.asyncio
async def test_create_invoice(client, inkey_headers_to):
    data = await get_random_invoice_data()
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    assert response.status_code == 201
    invoice = response.json()
    assert "payment_hash" in invoice
    assert len(invoice["payment_hash"]) == 64
    assert "payment_request" in invoice
    assert "checking_id" in invoice
    assert len(invoice["checking_id"])
    return invoice


# check POST /api/v1/payments: invoice creation for internal payments only
@pytest.mark.asyncio
async def test_create_internal_invoice(client, inkey_headers_to):
    data = await get_random_invoice_data()
    data["internal"] = True
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    invoice = response.json()
    assert response.status_code == 201
    assert "payment_hash" in invoice
    assert len(invoice["payment_hash"]) == 64
    assert "payment_request" in invoice
    assert "checking_id" in invoice
    assert len(invoice["checking_id"])
    return invoice


# check POST /api/v1/payments: invoice with custom expiry
@pytest.mark.asyncio
async def test_create_invoice_custom_expiry(client, inkey_headers_to):
    data = await get_random_invoice_data()
    expiry_seconds = 600 * 6 * 24 * 31  # 31 days in the future
    data["expiry"] = expiry_seconds
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    assert response.status_code == 201
    invoice = response.json()
    bolt11_invoice = bolt11.decode(invoice["payment_request"])
    assert bolt11_invoice.expiry == expiry_seconds


# check POST /api/v1/payments: make payment
@pytest.mark.asyncio
async def test_pay_invoice(client, invoice, adminkey_headers_from):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code < 300
    assert len(response.json()["payment_hash"]) == 64
    assert len(response.json()["checking_id"]) > 0


# check GET /api/v1/payments/<hash>: payment status
@pytest.mark.asyncio
async def test_check_payment_without_key(client, invoice):
    # check the payment status
    response = await client.get(f"/api/v1/payments/{invoice['payment_hash']}")
    assert response.status_code < 300
    assert response.json()["paid"] == True
    assert invoice
    # not key, that's why no "details"
    assert "details" not in response.json()


# check GET /api/v1/payments/<hash>: payment status
# NOTE: this test is sensitive to which db is used.
# If postgres: it will succeed only with inkey_headers_from
# If sqlite: it will succeed only with adminkey_headers_to
# TODO: fix this
@pytest.mark.asyncio
async def test_check_payment_with_key(client, invoice, inkey_headers_from):
    # check the payment status
    response = await client.get(
        f"/api/v1/payments/{invoice['payment_hash']}", headers=inkey_headers_from
    )
    assert response.status_code < 300
    assert response.json()["paid"] == True
    assert invoice
    # with key, that's why with "details"
    assert "details" in response.json()


# check POST /api/v1/payments: payment with wrong key type
@pytest.mark.asyncio
async def test_pay_invoice_wrong_key(client, invoice, adminkey_headers_from):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    # try payment with wrong key
    wrong_adminkey_headers = adminkey_headers_from.copy()
    wrong_adminkey_headers["X-Api-Key"] = "wrong_key"
    response = await client.post(
        "/api/v1/payments", json=data, headers=wrong_adminkey_headers
    )
    assert response.status_code >= 300  # should fail


# check POST /api/v1/payments: payment with invoice key [should fail]
@pytest.mark.asyncio
async def test_pay_invoice_invoicekey(client, invoice, inkey_headers_from):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    # try payment with invoice key
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_from
    )
    assert response.status_code >= 300  # should fail


# check POST /api/v1/payments: payment with admin key [should pass]
@pytest.mark.asyncio
@pytest.mark.skipif(is_regtest, reason="this only works in fakewallet")
async def test_pay_invoice_adminkey(client, invoice, adminkey_headers_from):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    # try payment with admin key
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code < 300  # should pass


# check POST /api/v1/payments/decode
@pytest.mark.asyncio
async def test_decode_invoice(client, invoice):
    data = {"data": invoice["payment_request"]}
    response = await client.post(
        "/api/v1/payments/decode",
        json=data,
    )
    assert response.status_code < 300
    assert response.json()["payment_hash"] == invoice["payment_hash"]


# check api_payment() internal function call (NOT API): payment status
@pytest.mark.asyncio
async def test_api_payment_without_key(invoice):
    # check the payment status
    response = await api_payment(invoice["payment_hash"])
    assert type(response) == dict
    assert response["paid"] == True
    # no key, that's why no "details"
    assert "details" not in response


# check api_payment() internal function call (NOT API): payment status
@pytest.mark.asyncio
async def test_api_payment_with_key(invoice, inkey_headers_from):
    # check the payment status
    response = await api_payment(
        invoice["payment_hash"], inkey_headers_from["X-Api-Key"]
    )
    assert type(response) == dict
    assert response["paid"] == True
    assert "details" in response


# check POST /api/v1/payments: invoice creation with a description hash
@pytest.mark.skipif(
    WALLET.__class__.__name__ in ["CoreLightningWallet"],
    reason="wallet does not support description_hash",
)
@pytest.mark.asyncio
async def test_create_invoice_with_description_hash(client, inkey_headers_to):
    data = await get_random_invoice_data()
    descr_hash = hashlib.sha256("asdasdasd".encode()).hexdigest()
    data["description_hash"] = descr_hash

    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    invoice = response.json()

    invoice_bolt11 = bolt11.decode(invoice["payment_request"])
    assert invoice_bolt11.description_hash == descr_hash
    assert invoice_bolt11.description is None
    return invoice


@pytest.mark.asyncio
async def test_create_invoice_with_unhashed_description(client, inkey_headers_to):
    data = await get_random_invoice_data()
    descr_hash = hashlib.sha256("asdasdasd".encode()).hexdigest()
    data["unhashed_description"] = "asdasdasd".encode().hex()

    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    invoice = response.json()

    invoice_bolt11 = bolt11.decode(invoice["payment_request"])
    assert invoice_bolt11.description_hash == descr_hash
    assert invoice_bolt11.description is None
    return invoice
