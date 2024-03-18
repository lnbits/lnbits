import asyncio
import hashlib

import pytest

from lnbits import bolt11
from lnbits.core.crud import get_standalone_payment, update_payment_details
from lnbits.core.models import CreateInvoice, Payment
from lnbits.core.services import fee_reserve_total
from lnbits.core.views.admin_api import api_auditor
from lnbits.core.views.api import api_payment
from lnbits.settings import settings
from lnbits.wallets import get_wallet_class

from ...helpers import (
    cancel_invoice,
    get_random_invoice_data,
    get_real_invoice,
    is_fake,
    is_regtest,
    pay_real_invoice,
    settle_invoice,
)

WALLET = get_wallet_class()


# create account POST /api/v1/account
@pytest.mark.asyncio
async def test_create_account(client):
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
@pytest.mark.skipif(
    is_regtest, reason="payments wont be confirmed rightaway in regtest"
)
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
@pytest.mark.skipif(
    WALLET.__class__.__name__
    in ["CoreLightningWallet", "CoreLightningRestWallet", "BreezSdkWallet"],
    reason="wallet does not support description_hash",
)
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


@pytest.mark.skipif(
    WALLET.__class__.__name__ in ["CoreLightningRestWallet", "BreezSdkWallet"],
    reason="wallet does not support unhashed_description",
)
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


async def get_node_balance_sats():
    audit = await api_auditor()
    return audit["node_balance_msats"] / 1000


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_real_invoice(
    client, real_invoice, adminkey_headers_from, inkey_headers_from, from_wallet_ws
):
    prev_balance = await get_node_balance_sats()
    response = await client.post(
        "/api/v1/payments", json=real_invoice, headers=adminkey_headers_from
    )
    assert response.status_code < 300
    invoice = response.json()
    assert len(invoice["payment_hash"]) == 64
    assert len(invoice["checking_id"]) > 0

    data = from_wallet_ws.receive_json()
    assert "wallet_balance" in data
    payment = Payment(**data["payment"])
    assert payment.payment_hash == invoice["payment_hash"]

    # check the payment status
    response = await client.get(
        f'/api/v1/payments/{invoice["payment_hash"]}', headers=inkey_headers_from
    )
    assert response.status_code < 300
    payment_status = response.json()
    assert payment_status["paid"]

    WALLET = get_wallet_class()
    status = await WALLET.get_payment_status(invoice["payment_hash"])
    assert status.paid

    await asyncio.sleep(1)
    balance = await get_node_balance_sats()
    assert prev_balance - balance == 100


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_create_real_invoice(client, adminkey_headers_from, inkey_headers_from):
    prev_balance = await get_node_balance_sats()
    create_invoice = CreateInvoice(out=False, amount=1000, memo="test")
    response = await client.post(
        "/api/v1/payments",
        json=create_invoice.dict(),
        headers=adminkey_headers_from,
    )
    assert response.status_code < 300
    invoice = response.json()

    response = await client.get(
        f'/api/v1/payments/{invoice["payment_hash"]}', headers=inkey_headers_from
    )
    assert response.status_code < 300
    payment_status = response.json()
    assert not payment_status["paid"]

    async def listen():
        found_checking_id = False
        async for checking_id in get_wallet_class().paid_invoices_stream():
            if checking_id == invoice["checking_id"]:
                found_checking_id = True
                return
        assert found_checking_id

    task = asyncio.create_task(listen())
    await asyncio.sleep(1)
    pay_real_invoice(invoice["payment_request"])
    await asyncio.wait_for(task, timeout=10)

    response = await client.get(
        f'/api/v1/payments/{invoice["payment_hash"]}', headers=inkey_headers_from
    )
    assert response.status_code < 300
    payment_status = response.json()
    assert payment_status["paid"]

    await asyncio.sleep(1)
    balance = await get_node_balance_sats()
    assert balance - prev_balance == create_invoice.amount


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_real_invoice_set_pending_and_check_state(
    client, real_invoice, adminkey_headers_from, inkey_headers_from
):
    """
    1. We create an invoice
    2. We pay it
    3. We verify that the inoice was paid
    4. We set the invoice to pending in the database
    5. We recheck the state of the invoice
    6. We verify that the invoice is paid
    """
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

    # make sure that the backend also thinks it's paid
    WALLET = get_wallet_class()
    status = await WALLET.get_payment_status(invoice["payment_hash"])
    assert status.paid

    # get the outgoing payment from the db
    payment = await get_standalone_payment(invoice["payment_hash"])
    assert payment
    assert payment.pending is False

    # set the outgoing invoice to pending
    await update_payment_details(payment.checking_id, pending=True)

    payment_pending = await get_standalone_payment(invoice["payment_hash"])
    assert payment_pending
    assert payment_pending.pending is True

    # check the outgoing payment status
    await payment.check_status()

    payment_not_pending = await get_standalone_payment(invoice["payment_hash"])
    assert payment_not_pending
    assert payment_not_pending.pending is False


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_hold_invoice_check_pending(
    client, hold_invoice, adminkey_headers_from
):
    preimage, invoice = hold_invoice
    task = asyncio.create_task(
        client.post(
            "/api/v1/payments",
            json={"bolt11": invoice["payment_request"]},
            headers=adminkey_headers_from,
        )
    )
    await asyncio.sleep(1)

    # get payment hash from the invoice
    invoice_obj = bolt11.decode(invoice["payment_request"])

    payment_db = await get_standalone_payment(invoice_obj.payment_hash)

    assert payment_db
    assert payment_db.pending is True

    settle_invoice(preimage)

    response = await task
    assert response.status_code < 300

    # check if paid

    await asyncio.sleep(1)

    payment_db_after_settlement = await get_standalone_payment(invoice_obj.payment_hash)

    assert payment_db_after_settlement
    assert payment_db_after_settlement.pending is False


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_hold_invoice_check_pending_and_fail(
    client, hold_invoice, adminkey_headers_from
):
    preimage, invoice = hold_invoice
    task = asyncio.create_task(
        client.post(
            "/api/v1/payments",
            json={"bolt11": invoice["payment_request"]},
            headers=adminkey_headers_from,
        )
    )
    await asyncio.sleep(1)

    # get payment hash from the invoice
    invoice_obj = bolt11.decode(invoice["payment_request"])

    payment_db = await get_standalone_payment(invoice_obj.payment_hash)

    assert payment_db
    assert payment_db.pending is True

    preimage_hash = hashlib.sha256(bytes.fromhex(preimage)).hexdigest()

    # cancel the hodl invoice
    assert preimage_hash == invoice_obj.payment_hash
    cancel_invoice(preimage_hash)

    response = await task
    assert response.status_code > 300  # should error

    await asyncio.sleep(1)

    # payment should not be in database anymore
    payment_db_after_settlement = await get_standalone_payment(invoice_obj.payment_hash)
    assert payment_db_after_settlement is None


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_hold_invoice_check_pending_and_fail_cancel_payment_task_in_meantime(
    client, hold_invoice, adminkey_headers_from
):
    preimage, invoice = hold_invoice
    task = asyncio.create_task(
        client.post(
            "/api/v1/payments",
            json={"bolt11": invoice["payment_request"]},
            headers=adminkey_headers_from,
        )
    )
    await asyncio.sleep(1)

    # get payment hash from the invoice
    invoice_obj = bolt11.decode(invoice["payment_request"])

    payment_db = await get_standalone_payment(invoice_obj.payment_hash)

    assert payment_db
    assert payment_db.pending is True

    # cancel payment task, this simulates the client dropping the connection
    task.cancel()

    preimage_hash = hashlib.sha256(bytes.fromhex(preimage)).hexdigest()

    assert preimage_hash == invoice_obj.payment_hash
    cancel_invoice(preimage_hash)

    # check if paid
    await asyncio.sleep(1)

    # payment should still be in db
    payment_db_after_settlement = await get_standalone_payment(invoice_obj.payment_hash)
    assert payment_db_after_settlement is not None

    # status should still be available and be False
    status = await payment_db.check_status()
    assert not status.paid

    # now the payment should be gone after the status check
    # payment_db_after_status_check = await get_standalone_payment(
    #     invoice_obj.payment_hash
    # )
    # assert payment_db_after_status_check is None


@pytest.mark.asyncio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_receive_real_invoice_set_pending_and_check_state(
    client, adminkey_headers_from, inkey_headers_from
):
    """
    1. We create a real invoice
    2. We pay it from our wallet
    3. We check that the inoice was paid with the backend
    4. We set the invoice to pending in the database
    5. We recheck the state of the invoice with the backend
    6. We verify that the invoice is now marked as paid in the database
    """
    create_invoice = CreateInvoice(out=False, amount=1000, memo="test")
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
        found_checking_id = False
        async for checking_id in get_wallet_class().paid_invoices_stream():
            if checking_id == invoice["checking_id"]:
                found_checking_id = True
                return
        assert found_checking_id

    task = asyncio.create_task(listen())
    await asyncio.sleep(1)
    pay_real_invoice(invoice["payment_request"])
    await asyncio.wait_for(task, timeout=10)
    response = await api_payment(
        invoice["payment_hash"], inkey_headers_from["X-Api-Key"]
    )
    assert response["paid"]

    # get the incoming payment from the db
    payment = await get_standalone_payment(invoice["payment_hash"], incoming=True)
    assert payment
    assert payment.pending is False

    # set the incoming invoice to pending
    await update_payment_details(payment.checking_id, pending=True)

    payment_pending = await get_standalone_payment(
        invoice["payment_hash"], incoming=True
    )
    assert payment_pending
    assert payment_pending.pending is True

    # check the incoming payment status
    await payment.check_status()

    payment_not_pending = await get_standalone_payment(
        invoice["payment_hash"], incoming=True
    )
    assert payment_not_pending
    assert payment_not_pending.pending is False

    # verify we get the same result if we use the checking_id to look up the payment
    payment_by_checking_id = await get_standalone_payment(
        payment_not_pending.checking_id, incoming=True
    )

    assert payment_by_checking_id
    assert payment_by_checking_id.pending is False
    assert payment_by_checking_id.bolt11 == payment_not_pending.bolt11
    assert payment_by_checking_id.payment_hash == payment_not_pending.payment_hash


@pytest.mark.asyncio
async def test_check_fee_reserve(client, adminkey_headers_from):
    # if regtest, create a real invoice, otherwise create an internal invoice
    # call /api/v1/payments/fee-reserve?invoice=... with it and check if the fee reserve
    # is correct
    payment_request = ""
    if is_regtest:
        real_invoice = get_real_invoice(1000)
        payment_request = real_invoice["payment_request"]

    else:
        create_invoice = CreateInvoice(out=False, amount=1000, memo="test")
        response = await client.post(
            "/api/v1/payments",
            json=create_invoice.dict(),
            headers=adminkey_headers_from,
        )
        assert response.status_code < 300
        invoice = response.json()
        payment_request = invoice["payment_request"]

    response = await client.get(
        f"/api/v1/payments/fee-reserve?invoice={payment_request}",
    )
    assert response.status_code < 300
    fee_reserve = response.json()
    assert fee_reserve["fee_reserve"] == fee_reserve_total(1000_000)
