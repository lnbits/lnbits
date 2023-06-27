import asyncio
import hashlib
from time import time

import pytest

from lnbits import bolt11
from lnbits.core.models import Payment
from lnbits.core.views.admin_api import api_auditor
from lnbits.core.views.api import api_payment
from lnbits.db import DB_TYPE, SQLITE
from lnbits.wallets import get_wallet_class
from tests.conftest import CreateInvoiceData, api_payments_create_invoice

from ...helpers import get_random_invoice_data, is_fake, pay_real_invoice

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
    assert response.json()["paid"] is True
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
    assert response.json()["paid"] is True
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


# check POST /api/v1/payments: payment with admin key, trying to pay twice [should fail]
@pytest.mark.asyncio
async def test_pay_invoice_adminkey(client, invoice, adminkey_headers_from):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    # try payment with admin key
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code > 300  # should fail


@pytest.mark.asyncio
async def test_get_payments(client, from_wallet, adminkey_headers_from):
    # Because sqlite only stores timestamps with milliseconds we have to wait a second to ensure
    # a different timestamp than previous invoices
    # due to this limitation both payments (normal and paginated) are tested at the same time as they are almost
    # identical anyways
    if DB_TYPE == SQLITE:
        await asyncio.sleep(1)
    ts = time()

    fake_data = [
        CreateInvoiceData(amount=10, memo="aaaa"),
        CreateInvoiceData(amount=100, memo="bbbb"),
        CreateInvoiceData(amount=1000, memo="aabb"),
    ]

    for invoice in fake_data:
        await api_payments_create_invoice(invoice, from_wallet)

    async def get_payments(params: dict):
        params["time[ge]"] = ts
        response = await client.get(
            "/api/v1/payments",
            params=params,
            headers=adminkey_headers_from,
        )
        assert response.status_code == 200
        return [Payment(**payment) for payment in response.json()]

    payments = await get_payments({"sortby": "amount", "direction": "desc", "limit": 2})
    assert payments[-1].amount < payments[0].amount
    assert len(payments) == 2

    payments = await get_payments({"offset": 2, "limit": 2})
    assert len(payments) == 1

    payments = await get_payments({"sortby": "amount", "direction": "asc"})
    assert payments[-1].amount > payments[0].amount

    payments = await get_payments({"search": "aaa"})
    assert len(payments) == 1

    payments = await get_payments({"search": "aa"})
    assert len(payments) == 2

    # amount is in msat
    payments = await get_payments({"amount[gt]": 10000})
    assert len(payments) == 2

    response = await client.get(
        "/api/v1/payments/paginated",
        params={"limit": 2, "time[ge]": ts},
        headers=adminkey_headers_from,
    )
    assert response.status_code == 200
    paginated = response.json()
    assert len(paginated["data"]) == 2
    assert paginated["total"] == len(fake_data)


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
    assert response["paid"] is True
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
    assert response["paid"] is True
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


async def get_node_balance_sats():
    audit = await api_auditor()
    return audit["node_balance_msats"] / 1000


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_real_invoice(
    client, real_invoice, adminkey_headers_from, inkey_headers_from
):
    prev_balance = await get_node_balance_sats()
    response = await client.post(
        "/api/v1/payments", json=real_invoice, headers=adminkey_headers_from
    )
    assert response.status_code < 300
    invoice = response.json()
    assert len(invoice["payment_hash"]) == 64
    assert len(invoice["checking_id"]) > 0

    # check the payment status
    response = await api_payment(
        invoice["payment_hash"], inkey_headers_from["X-Api-Key"]
    )
    assert response["paid"]

    status = await WALLET.get_payment_status(invoice["payment_hash"])
    assert status.paid

    await asyncio.sleep(0.3)
    balance = await get_node_balance_sats()
    assert prev_balance - balance == 100


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_create_real_invoice(client, adminkey_headers_from, inkey_headers_from):
    prev_balance = await get_node_balance_sats()
    create_invoice = CreateInvoiceData(out=False, amount=1000, memo="test")
    response = await client.post(
        "/api/v1/payments",
        json=create_invoice.dict(),
        headers=adminkey_headers_from,
    )
    assert response.status_code < 300
    invoice = response.json()
    response = await api_payment(
        invoice["payment_hash"], inkey_headers_from["X-Api-Key"]
    )
    assert not response["paid"]

    async def listen():
        async for payment_hash in get_wallet_class().paid_invoices_stream():
            assert payment_hash == invoice["payment_hash"]
            return

    task = asyncio.create_task(listen())
    pay_real_invoice(invoice["payment_request"])
    await asyncio.wait_for(task, timeout=3)
    response = await api_payment(
        invoice["payment_hash"], inkey_headers_from["X-Api-Key"]
    )
    assert response["paid"]

    await asyncio.sleep(0.3)
    balance = await get_node_balance_sats()
    assert balance - prev_balance == create_invoice.amount
