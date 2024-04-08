import asyncio
import hashlib

import bolt11
import pytest

from lnbits.core.crud import get_standalone_payment, update_payment_details
from lnbits.core.models import CreateInvoice, Payment
from lnbits.core.views.admin_api import api_auditor
from lnbits.core.views.payment_api import api_payment
from lnbits.settings import get_wallet_class
from tests.helpers import (
    cancel_invoice,
    is_fake,
    pay_real_invoice,
    settle_invoice,
)

wallet_class = get_wallet_class()


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

    wallet_class = get_wallet_class()
    status = await wallet_class.get_payment_status(invoice["payment_hash"])
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
    wallet_class = get_wallet_class()
    status = await wallet_class.get_payment_status(invoice["payment_hash"])
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
