import hashlib

import pytest

from lnbits import bolt11
from lnbits.core.models import CreateInvoice, Payment
from lnbits.core.views.payment_api import api_payment
from lnbits.settings import settings

from ..helpers import (
    get_random_invoice_data,
)


# create account POST /api/v1/account
@pytest.mark.asyncio
async def test_create_account(client):
    settings.lnbits_allow_new_accounts = False
    response = await client.post("/api/v1/account", json={"name": "test"})
    assert response.status_code == 403
    settings.lnbits_allow_new_accounts = True
    response = await client.post("/api/v1/account", json={"name": "test"})
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    assert result["name"] == "test"
    assert "balance_msat" in result
    assert "id" in result
    assert "user" in result


# check POST and DELETE /api/v1/wallet with adminkey:
# create additional wallet and delete it
@pytest.mark.asyncio
async def test_create_wallet_and_delete(client, adminkey_headers_to):
    response = await client.post(
        "/api/v1/wallet", json={"name": "test"}, headers=adminkey_headers_to
    )
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    assert result["name"] == "test"
    assert "balance_msat" in result
    assert "id" in result
    assert "adminkey" in result

    invalid_response = await client.delete(
        "/api/v1/wallet",
        headers={
            "X-Api-Key": result["inkey"],
            "Content-type": "application/json",
        },
    )
    assert invalid_response.status_code == 401

    response = await client.delete(
        "/api/v1/wallet",
        headers={
            "X-Api-Key": result["adminkey"],
            "Content-type": "application/json",
        },
    )
    assert response.status_code == 200

    # get deleted wallet
    response = await client.get(
        "/api/v1/wallet",
        headers={
            "X-Api-Key": result["adminkey"],
            "Content-type": "application/json",
        },
    )
    assert response.status_code == 404


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


@pytest.mark.asyncio
async def test_create_invoice_fiat_amount(client, inkey_headers_to):
    data = await get_random_invoice_data()
    data["unit"] = "EUR"
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    assert response.status_code == 201
    invoice = response.json()
    decode = bolt11.decode(invoice["payment_request"])
    assert decode.amount_msat != data["amount"] * 1000
    assert decode.payment_hash

    response = await client.get(
        f"/api/v1/payments/{decode.payment_hash}", headers=inkey_headers_to
    )
    assert response.is_success
    res_data = response.json()
    extra = res_data["details"]["extra"]
    assert extra["fiat_amount"] == data["amount"]
    assert extra["fiat_currency"] == data["unit"]
    assert extra["fiat_rate"]


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
async def test_pay_invoice(client, from_wallet_ws, invoice, adminkey_headers_from):
    data = {"out": True, "bolt11": invoice["payment_request"]}
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code < 300
    invoice = response.json()
    assert len(invoice["payment_hash"]) == 64
    assert len(invoice["checking_id"]) > 0

    data = from_wallet_ws.receive_json()
    assert "wallet_balance" in data
    payment = Payment(**data["payment"])
    assert payment.payment_hash == invoice["payment_hash"]

    # websocket from to_wallet cant be tested before https://github.com/lnbits/lnbits/pull/1793
    # data = to_wallet_ws.receive_json()
    # assert "wallet_balance" in data
    # payment = Payment(**data["payment"])
    # assert payment.payment_hash == invoice["payment_hash"]


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


# check POST /api/v1/payments: payment with self payment
@pytest.mark.asyncio
async def test_pay_invoice_self_payment(client, adminkey_headers_from):
    create_invoice = CreateInvoice(out=False, amount=1000, memo="test")
    response = await client.post(
        "/api/v1/payments",
        json=create_invoice.dict(),
        headers=adminkey_headers_from,
    )
    assert response.status_code < 300
    json_data = response.json()
    data = {"out": True, "bolt11": json_data["payment_request"]}
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code < 300


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
async def test_get_payments(client, adminkey_headers_from, fake_payments):
    fake_data, filters = fake_payments

    async def get_payments(params: dict):
        response = await client.get(
            "/api/v1/payments",
            params=filters | params,
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


@pytest.mark.asyncio
async def test_get_payments_paginated(client, adminkey_headers_from, fake_payments):
    fake_data, filters = fake_payments

    response = await client.get(
        "/api/v1/payments/paginated",
        params=filters | {"limit": 2},
        headers=adminkey_headers_from,
    )
    assert response.status_code == 200
    paginated = response.json()
    assert len(paginated["data"]) == 2
    assert paginated["total"] == len(fake_data)


@pytest.mark.asyncio
async def test_get_payments_history(client, adminkey_headers_from, fake_payments):
    fake_data, filters = fake_payments

    response = await client.get(
        "/api/v1/payments/history",
        params=filters,
        headers=adminkey_headers_from,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["spending"] == sum(
        payment.amount * 1000 for payment in fake_data if payment.out
    )
    assert data[0]["income"] == sum(
        payment.amount * 1000 for payment in fake_data if not payment.out
    )

    response = await client.get(
        "/api/v1/payments/history?group=INVALID",
        params=filters,
        headers=adminkey_headers_from,
    )

    assert response.status_code == 400


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
    assert isinstance(response, dict)
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
    assert isinstance(response, dict)
    assert response["paid"] is True
    assert "details" in response


# check POST /api/v1/payments: invoice creation with a description hash
@pytest.mark.asyncio
async def test_create_invoice_with_description_hash(client, inkey_headers_to):
    data = await get_random_invoice_data()
    description = "asdasdasd"
    descr_hash = hashlib.sha256(description.encode()).hexdigest()
    data["description_hash"] = descr_hash
    data["unhashed_description"] = description.encode().hex()
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    invoice = response.json()

    invoice_bolt11 = bolt11.decode(invoice["payment_request"])
    assert invoice_bolt11.description_hash == descr_hash
    return invoice


@pytest.mark.asyncio
async def test_create_invoice_with_unhashed_description(client, inkey_headers_to):
    data = await get_random_invoice_data()
    description = "test description"
    descr_hash = hashlib.sha256(description.encode()).hexdigest()
    data["unhashed_description"] = description.encode().hex()

    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    invoice = response.json()

    invoice_bolt11 = bolt11.decode(invoice["payment_request"])
    assert invoice_bolt11.description_hash == descr_hash
    assert invoice_bolt11.description is None
    return invoice


@pytest.mark.asyncio
async def test_update_wallet(client, adminkey_headers_from):
    name = "new name"
    currency = "EUR"

    response = await client.patch(
        "/api/v1/wallet", json={"name": name}, headers=adminkey_headers_from
    )
    assert response.status_code == 200
    assert response.json()["name"] == name

    response = await client.patch(
        "/api/v1/wallet", json={"currency": currency}, headers=adminkey_headers_from
    )
    assert response.status_code == 200
    assert response.json()["currency"] == currency
    # name is not changed because updates are partial
    assert response.json()["name"] == name


@pytest.mark.asyncio
async def test_fiat_tracking(client, adminkey_headers_from):
    async def create_invoice():
        data = await get_random_invoice_data()
        response = await client.post(
            "/api/v1/payments", json=data, headers=adminkey_headers_from
        )
        assert response.is_success

        response = await client.get(
            f"/api/v1/payments/{response.json()['payment_hash']}",
            headers=adminkey_headers_from,
        )
        assert response.is_success
        return response.json()["details"]

    async def update_currency(currency):
        response = await client.patch(
            "/api/v1/wallet", json={"currency": currency}, headers=adminkey_headers_from
        )
        assert response.is_success
        assert response.json()["currency"] == currency

    await update_currency("")

    settings.lnbits_default_accounting_currency = "USD"
    payment = await create_invoice()
    assert payment["extra"]["wallet_fiat_currency"] == "USD"
    assert payment["extra"]["wallet_fiat_amount"] != payment["amount"]
    assert payment["extra"]["wallet_fiat_rate"]

    await update_currency("EUR")

    payment = await create_invoice()
    assert payment["extra"]["wallet_fiat_currency"] == "EUR"
    assert payment["extra"]["wallet_fiat_amount"] != payment["amount"]
    assert payment["extra"]["wallet_fiat_rate"]
