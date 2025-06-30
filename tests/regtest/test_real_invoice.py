import asyncio
import hashlib

import pytest

from lnbits import bolt11
from lnbits.core.crud import get_standalone_payment, update_payment
from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.models import CreateInvoice, Payment, PaymentState
from lnbits.core.services import fee_reserve_total, get_balance_delta
from lnbits.core.services.payments import pay_invoice, update_wallet_balance
from lnbits.core.services.users import create_user_account
from lnbits.exceptions import PaymentError
from lnbits.tasks import create_task, wait_for_paid_invoices
from lnbits.wallets import get_funding_source

from ..helpers import FakeError, is_fake, is_regtest
from .helpers import (
    cancel_invoice,
    get_real_invoice,
    pay_real_invoice,
    settle_invoice,
)


async def get_node_balance_sats():
    balance = await get_balance_delta()
    return balance.node_balance_sats


@pytest.mark.anyio
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

    while True:
        data = from_wallet_ws.receive_json()
        assert "wallet_balance" in data
        assert "payment" in data
        if data["payment"]["payment_hash"] == invoice["payment_hash"]:
            payment = Payment(**data["payment"])
            break

    assert payment.payment_hash == invoice["payment_hash"]

    # check the payment status
    response = await client.get(
        f'/api/v1/payments/{invoice["payment_hash"]}', headers=inkey_headers_from
    )
    assert response.status_code < 300
    payment_status = response.json()
    assert payment_status["paid"]

    funding_source = get_funding_source()
    status = await funding_source.get_payment_status(invoice["payment_hash"])
    assert status.paid

    await asyncio.sleep(1)
    balance = await get_node_balance_sats()
    assert prev_balance - balance == 100


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_real_invoice_noroute(
    client,
    real_invoice_noroute,
    adminkey_headers_from,
    inkey_headers_from,
):
    response = await client.post(
        "/api/v1/payments", json=real_invoice_noroute, headers=adminkey_headers_from
    )
    assert response.status_code == 520
    invoice = response.json()

    assert invoice["status"] == "failed"

    # check the payment status
    response = await client.get(
        f'/api/v1/payments/{real_invoice_noroute["payment_hash"]}',
        headers=inkey_headers_from,
    )
    assert response.status_code < 300
    payment = response.json()
    assert payment["paid"] is False
    assert payment["status"] == "failed"


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_real_invoice_mainnet(
    client,
    adminkey_headers_from,
    inkey_headers_from,
):
    """regtest should fail paying a mainnet invoice"""
    inv = (
        "lnbc100n1p59ujlrpp5mn5g5tu7fz0up6asnz0gcceru4hwz0w42g7fuz8gxw67jl7kjjeqcqzyssp5qq"
        "5y92fwazqdtnu8u9p9qf333hqnkuvtuu5csdze5ak4q86hyrhq9q7sqqqqqqqqqqqqqqqqqqqsqqqqqys"
        "gqdq2f38xy6t5wvmqz9gxqrrssrzjqwryaup9lh50kkranzgcdnn2fgvx390wgj5jd07rwr3vxeje0glc"
        "lll4ttz7sp6kpvqqqqlgqqqqqeqqjqm9fkydmtwsxcxx3j44x9fckjqttg54zlxzw92yeaz9nzn8w7hgv"
        "87ph5ug4wmgxqpk929k7l6dsnc2y9532daaqlpg9tfjglshuh48cpjh0dua"
    )
    payment_hash = "dce88a2f9e489fc0ebb0989e8c6323e56ee13dd5523c9e08e833b5e97fd694b2"

    response = await client.post(
        "/api/v1/payments", json={"bolt11": inv}, headers=adminkey_headers_from
    )
    assert response.status_code == 520
    invoice = response.json()
    assert invoice["status"] == "failed"

    # check the payment status
    response = await client.get(
        f"/api/v1/payments/{payment_hash}",
        headers=inkey_headers_from,
    )
    assert response.status_code < 300
    payment = response.json()
    assert payment["paid"] is False
    assert payment["status"] == "failed"


@pytest.mark.anyio
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

    async def on_paid(payment: Payment):

        assert payment.checking_id == invoice["payment_hash"]

        response = await client.get(
            f'/api/v1/payments/{invoice["payment_hash"]}', headers=inkey_headers_from
        )
        assert response.status_code < 300
        payment_status = response.json()
        assert payment_status["paid"]

        await asyncio.sleep(1)
        balance = await get_node_balance_sats()
        assert balance - prev_balance == create_invoice.amount

        assert payment_status.get("preimage") is not None

        # exit out of infinite loop
        raise FakeError()

    task = create_task(wait_for_paid_invoices("test_create_invoice", on_paid)())
    pay_real_invoice(invoice["bolt11"])

    # wait for the task to exit
    with pytest.raises(FakeError):
        await task


@pytest.mark.anyio
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
    response = await client.get(
        f'/api/v1/payments/{invoice["payment_hash"]}', headers=inkey_headers_from
    )
    payment_status = response.json()
    assert payment_status["paid"]

    # make sure that the backend also thinks it's paid
    funding_source = get_funding_source()
    status = await funding_source.get_payment_status(invoice["payment_hash"])
    assert status.paid

    # get the outgoing payment from the db
    payment = await get_standalone_payment(invoice["payment_hash"])
    assert payment
    assert payment.success


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
async def test_pay_real_invoices_in_parallel():
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)

    # more to cover routing feems
    await update_wallet_balance(wallet, 1100)

    # these must be external invoices
    real_invoice_one = get_real_invoice(1000)
    real_invoice_two = get_real_invoice(1000)

    async def pay_first():
        return await pay_invoice(
            wallet_id=wallet.id,
            payment_request=real_invoice_one["payment_request"],
        )

    async def pay_second():
        return await pay_invoice(
            wallet_id=wallet.id,
            payment_request=real_invoice_two["payment_request"],
        )

    with pytest.raises(PaymentError, match="Insufficient balance."):
        await asyncio.gather(pay_first(), pay_second())

    wallet_after = await get_wallet(wallet.id)
    assert wallet_after
    assert 0 <= wallet_after.balance <= 100, "One payment should be deducted."


@pytest.mark.anyio
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
    await asyncio.sleep(3)
    # get payment hash from the invoice
    invoice_obj = bolt11.decode(invoice["payment_request"])
    settle_invoice(preimage)
    payment_db = await get_standalone_payment(invoice_obj.payment_hash)
    assert payment_db
    response = await task
    assert response.status_code < 300

    # check if paid
    await asyncio.sleep(1)
    payment_db_after_settlement = await get_standalone_payment(invoice_obj.payment_hash)

    assert payment_db_after_settlement


@pytest.mark.anyio
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

    preimage_hash = hashlib.sha256(bytes.fromhex(preimage)).hexdigest()

    # cancel the hodl invoice
    assert preimage_hash == invoice_obj.payment_hash
    cancel_invoice(preimage_hash)

    response = await task
    assert response.status_code > 300  # should error

    await asyncio.sleep(1)

    # payment should be in database as failed
    payment_db_after_settlement = await get_standalone_payment(invoice_obj.payment_hash)
    assert payment_db_after_settlement
    assert payment_db_after_settlement.failed is True


@pytest.mark.anyio
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

    # payment is failed
    status = await payment_db_after_settlement.check_status()
    assert not status.paid
    assert status.failed


@pytest.mark.anyio
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
    response = await client.get(
        f'/api/v1/payments/{invoice["payment_hash"]}', headers=inkey_headers_from
    )
    payment_status = response.json()
    assert not payment_status["paid"]

    async def on_paid(payment: Payment):
        assert payment.checking_id == invoice["payment_hash"]

        response = await client.get(
            f'/api/v1/payments/{invoice["payment_hash"]}', headers=inkey_headers_from
        )
        assert response.status_code < 300
        payment_status = response.json()
        assert payment_status["paid"]

        assert payment

        # set the incoming invoice to pending
        payment.status = PaymentState.PENDING
        await update_payment(payment)

        payment_pending = await get_standalone_payment(
            invoice["payment_hash"], incoming=True
        )
        assert payment_pending
        assert payment_pending.success is False
        assert payment_pending.failed is False

        # exit out of infinite loop
        raise FakeError()

    task = create_task(wait_for_paid_invoices("test_create_invoice", on_paid)())
    pay_real_invoice(invoice["bolt11"])

    with pytest.raises(FakeError):
        await task


@pytest.mark.anyio
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
        payment_request = invoice["bolt11"]

    response = await client.get(
        f"/api/v1/payments/fee-reserve?invoice={payment_request}",
    )
    assert response.status_code < 300
    fee_reserve = response.json()
    assert fee_reserve["fee_reserve"] == fee_reserve_total(1000_000)
