import asyncio
from unittest.mock import AsyncMock

import pytest
from bolt11 import TagChar
from bolt11 import decode as bolt11_decode
from bolt11 import encode as bolt11_encode
from bolt11.types import MilliSatoshi
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import create_wallet, get_standalone_payment, get_wallet
from lnbits.core.crud.payments import get_payment, get_payments_paginated
from lnbits.core.crud.wallets import delete_wallet
from lnbits.core.db import db
from lnbits.core.models import Payment, PaymentState, Wallet
from lnbits.core.models.payments import ValidatedPaymentRequest
from lnbits.core.services import create_invoice, create_user_account, pay_invoice
from lnbits.core.services.payments import (
    _validate_payment_request,
    update_pending_payment,
    update_wallet_balance,
)
from lnbits.exceptions import InvoiceError, PaymentError
from lnbits.settings import Settings
from lnbits.task_manager import task_manager
from lnbits.wallets.base import (
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentSuccessStatus,
)
from lnbits.wallets.fake import FakeWallet


@pytest.mark.anyio
async def test_validate_invoice_payment_request(to_wallet: Wallet):
    payment = await create_invoice(
        wallet_id=to_wallet.id, amount=21, memo="Validated invoice", expiry=120
    )

    pr = _validate_payment_request(payment.bolt11, max_sat=21)

    assert isinstance(pr, ValidatedPaymentRequest)
    assert pr.is_offer is False
    assert pr.payment_request == payment.bolt11
    assert pr.amount_msat == 21_000
    assert pr.payment_hash == payment.payment_hash
    assert pr.expiry_date == payment.expiry
    assert pr.description == "Validated invoice"


@pytest.mark.anyio
async def test_invalid_bolt11(to_wallet: Wallet):
    with pytest.raises(PaymentError):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request="lnbcr1123123n",
        )


@pytest.mark.anyio
async def test_amountless_invoice(to_wallet: Wallet):
    zero_amount_invoice = (
        "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
        "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
        "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
        "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
        "6hjxepwp93cq398l3s"
    )
    with pytest.raises(PaymentError, match="Amountless invoices not supported."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=zero_amount_invoice,
        )


@pytest.mark.anyio
async def test_bad_wallet_id(to_wallet: Wallet):
    payment = await create_invoice(wallet_id=to_wallet.id, amount=31, memo="Bad Wallet")
    bad_wallet_id = to_wallet.id[::-1]
    with pytest.raises(
        PaymentError, match=f"Could not fetch wallet '{bad_wallet_id}'."
    ):
        await pay_invoice(
            wallet_id=bad_wallet_id,
            payment_request=payment.bolt11,
        )


@pytest.mark.anyio
async def test_payment_explicit_limit(to_wallet: Wallet):
    payment = await create_invoice(wallet_id=to_wallet.id, amount=101, memo="")
    with pytest.raises(
        PaymentError,
        match="Invoice amount 101 sats is too high. Max allowed: 100 sats.",
    ):
        await pay_invoice(
            wallet_id=to_wallet.id,
            max_sat=100,
            payment_request=payment.bolt11,
        )


@pytest.mark.anyio
async def test_payment_system_limit(to_wallet: Wallet, settings: Settings):
    settings.lnbits_max_outgoing_payment_amount_sats = 100
    payment = await create_invoice(wallet_id=to_wallet.id, amount=200, memo="")
    with pytest.raises(
        PaymentError,
        match="Invoice amount 200 sats is too high. Max allowed: 100 sats.",
    ):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment.bolt11,
        )


@pytest.mark.anyio
async def test_create_payment_system_limit(to_wallet: Wallet, settings: Settings):
    settings.lnbits_max_incoming_payment_amount_sats = 101

    with pytest.raises(
        InvoiceError,
        match="Invoice amount 202 sats is too high. Max allowed: 101 sats.",
    ):
        await create_invoice(wallet_id=to_wallet.id, amount=202, memo="")


@pytest.mark.anyio
async def test_pay_twice(to_wallet: Wallet):
    payment = await create_invoice(wallet_id=to_wallet.id, amount=3, memo="Twice")
    await pay_invoice(
        wallet_id=to_wallet.id,
        payment_request=payment.bolt11,
    )
    with pytest.raises(PaymentError, match="Internal invoice already paid."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment.bolt11,
        )


@pytest.mark.anyio
async def test_pay_invoice_reuses_connection(to_wallet: Wallet):
    invoice = await create_invoice(wallet_id=to_wallet.id, amount=3, memo="Reuse conn")

    async with db.connect() as conn:
        payment = await asyncio.wait_for(
            pay_invoice(
                wallet_id=to_wallet.id,
                payment_request=invoice.bolt11,
                conn=conn,
            ),
            timeout=5,
        )
        assert payment.success

        with pytest.raises(PaymentError, match="Internal invoice already paid."):
            await asyncio.wait_for(
                pay_invoice(
                    wallet_id=to_wallet.id,
                    payment_request=invoice.bolt11,
                    conn=conn,
                ),
                timeout=5,
            )


@pytest.mark.anyio
async def test_pay_twice_fast():
    user = await create_user_account()
    wallet_one = await create_wallet(user_id=user.id)
    wallet_two = await create_wallet(user_id=user.id)

    await update_wallet_balance(wallet_one, 1000)
    payment_a = await create_invoice(wallet_id=wallet_two.id, amount=1000, memo="AAA")
    payment_b = await create_invoice(wallet_id=wallet_two.id, amount=1000, memo="BBB")

    async def pay_first():
        return await pay_invoice(
            wallet_id=wallet_one.id,
            payment_request=payment_a.bolt11,
        )

    async def pay_second():
        return await pay_invoice(
            wallet_id=wallet_one.id,
            payment_request=payment_b.bolt11,
        )

    with pytest.raises(PaymentError, match="Insufficient balance."):
        await asyncio.gather(pay_first(), pay_second())

    wallet_one_after = await get_wallet(wallet_one.id)
    assert wallet_one_after
    assert wallet_one_after.balance == 0, "One payment should be deducted."

    wallet_two_after = await get_wallet(wallet_two.id)
    assert wallet_two_after
    assert wallet_two_after.balance == 1000, "One payment received."


@pytest.mark.anyio
async def test_pay_twice_fast_same_invoice(to_wallet: Wallet):
    payment = await create_invoice(
        wallet_id=to_wallet.id, amount=3, memo="Twice fast same invoice"
    )

    async def pay_first():
        return await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment.bolt11,
        )

    async def pay_second():
        return await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment.bolt11,
        )

    with pytest.raises(PaymentError, match="Payment already paid."):
        await asyncio.gather(pay_first(), pay_second())


@pytest.mark.anyio
async def test_fake_wallet_pay_external(
    to_wallet: Wallet, external_funding_source: FakeWallet
):
    external_invoice = await external_funding_source.create_invoice(21)
    assert external_invoice.payment_request
    with pytest.raises(
        PaymentError, match="Payment failed: Only internal invoices can be used!"
    ):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=external_invoice.payment_request,
        )


@pytest.mark.anyio
async def test_invoice_changed(to_wallet: Wallet):
    payment = await create_invoice(wallet_id=to_wallet.id, amount=21, memo="original")

    invoice = bolt11_decode(payment.bolt11)
    invoice.amount_msat = MilliSatoshi(12000)
    payment_request = bolt11_encode(invoice)

    with pytest.raises(PaymentError, match="Invalid invoice. Bolt11 changed."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment_request,
        )

    invoice = bolt11_decode(payment_request)
    invoice.tags.add(TagChar.description, "mock stuff")
    payment_request = bolt11_encode(invoice)

    with pytest.raises(PaymentError, match="Invalid invoice."):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment_request,
        )


@pytest.mark.anyio
async def test_pay_for_extension(to_wallet: Wallet, settings: Settings):
    payment = await create_invoice(wallet_id=to_wallet.id, amount=3, memo="Allowed")
    await pay_invoice(
        wallet_id=to_wallet.id, payment_request=payment.bolt11, tag="lnurlp"
    )
    payment = await create_invoice(wallet_id=to_wallet.id, amount=3, memo="Not Allowed")
    settings.lnbits_admin_extensions = ["lnurlp"]
    with pytest.raises(
        PaymentError, match="User not authorized for extension 'lnurlp'."
    ):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=payment.bolt11,
            tag="lnurlp",
        )


@pytest.mark.anyio
async def test_notification_for_internal_payment(
    to_wallet: Wallet, mocker: MockerFixture
):
    test_name = "test_notification_for_internal_payment"

    # Drain stale items left by session-scoped fixtures (e.g. update_wallet_balance)
    while not task_manager.internal_invoice_queue.empty():
        try:
            task_manager.internal_invoice_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    on_paid_mock = mocker.AsyncMock()
    # create_task(internal_invoice_listener())

    task_manager.register_invoice_listener(on_paid_mock, test_name)

    payment = await create_invoice(
        wallet_id=to_wallet.id,
        amount=123,
        memo=test_name,
        webhook="http://test.404.lnbits.com",
    )
    paid_payment = await pay_invoice(
        wallet_id=to_wallet.id, payment_request=payment.bolt11, extra={"tag": "lnurlp"}
    )
    assert paid_payment.status == PaymentState.SUCCESS.value
    assert paid_payment.bolt11 == payment.bolt11
    assert paid_payment.amount == -123_000

    await asyncio.sleep(1)

    assert on_paid_mock.call_count == 1
    _payment = on_paid_mock.call_args_list[0][0][0]

    assert _payment.memo == test_name
    assert _payment.status == PaymentState.SUCCESS.value
    assert _payment.bolt11 == payment.bolt11
    assert _payment.amount == 123_000
    assert _payment.checking_id == payment.checking_id

    updated_payment = await get_payment(_payment.checking_id)
    assert (
        updated_payment.webhook_status is not None
    ), "Webhook should have been called."
    assert (
        int(updated_payment.webhook_status) >= 400
    ), "Webhook should have been called and failed."


@pytest.mark.anyio
async def test_pay_failed(
    to_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    payment_reponse_failed = PaymentResponse(ok=False, error_message="Mock failure!")
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_failed),
    )
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=external_funding_source,
    )

    external_invoice = await external_funding_source.create_invoice(2101)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    with pytest.raises(PaymentError, match="Payment failed: Mock failure!"):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    payment = await get_standalone_payment(external_invoice.checking_id)
    assert payment
    assert payment.status == PaymentState.FAILED.value
    assert payment.amount == -2101_000


@pytest.mark.anyio
async def test_retry_failed_invoice(
    from_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    payment_reponse_failed = PaymentResponse(ok=False, error_message="Mock failure!")

    invoice_amount = 2102
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request

    ws_notification = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background",
        AsyncMock(return_value=None),
    )

    wallet = await get_wallet(from_wallet.id)
    assert wallet
    balance_before = wallet.balance

    with pytest.raises(PaymentError, match="Payment failed: Mock failure!"):
        mocker.patch(
            "lnbits.wallets.FakeWallet.pay_invoice",
            AsyncMock(return_value=payment_reponse_failed),
        )
        await pay_invoice(
            wallet_id=from_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    with pytest.raises(
        PaymentError, match="Payment is failed node, retrying is not possible."
    ):
        mocker.patch(
            "lnbits.wallets.FakeWallet.get_payment_status",
            AsyncMock(return_value=payment_reponse_failed),
        )
        await pay_invoice(
            wallet_id=from_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    wallet = await get_wallet(from_wallet.id)
    assert wallet
    assert (
        balance_before == wallet.balance
    ), "Failed payments should not affect the balance."

    with pytest.raises(
        PaymentError, match="Failed payment was already paid on the fundingsource."
    ):
        payment_reponse_success = PaymentResponse(ok=True, error_message=None)
        mocker.patch(
            "lnbits.wallets.FakeWallet.get_payment_status",
            AsyncMock(return_value=payment_reponse_success),
        )
        await pay_invoice(
            wallet_id=from_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    wallet = await get_wallet(from_wallet.id)
    assert wallet
    # TODO: revisit
    # assert (
    #     balance_before - invoice_amount == wallet.balance
    # ), "Payment successful on retry."

    assert ws_notification.call_count == 0, "Websocket notification not sent."


@pytest.mark.anyio
@pytest.mark.parametrize("returns_checking_id", [True, False])
async def test_pay_external_invoice_pending(
    from_wallet: Wallet,
    mocker: MockerFixture,
    external_funding_source: FakeWallet,
    settings: Settings,
    returns_checking_id: bool,
):
    settings.lnbits_reserve_fee_min = 1000  # msats
    invoice_amount = 2103
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id
    backend_checking_id = (
        f"backend_{external_invoice.checking_id}" if returns_checking_id else None
    )
    expected_checking_id = backend_checking_id or external_invoice.checking_id

    payment_reponse_pending = PaymentResponse(ok=None, checking_id=backend_checking_id)
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_pending),
    )
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=external_funding_source,
    )
    ws_notification = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background",
        AsyncMock(return_value=None),
    )
    wallet = await get_wallet(from_wallet.id)
    assert wallet
    balance_before = wallet.balance
    payment = await pay_invoice(
        wallet_id=from_wallet.id,
        payment_request=external_invoice.payment_request,
    )

    _payment = await get_standalone_payment(payment.payment_hash)
    assert _payment
    assert _payment.status == PaymentState.PENDING.value
    assert _payment.checking_id == expected_checking_id
    assert _payment.payment_hash == external_invoice.checking_id
    assert payment.checking_id == expected_checking_id
    assert _payment.amount == -2103_000
    assert _payment.bolt11 == external_invoice.payment_request

    wallet = await get_wallet(from_wallet.id)
    assert wallet
    reserve_fee_sat = int(abs(settings.lnbits_reserve_fee_min // 1000))
    assert (
        balance_before - invoice_amount - reserve_fee_sat == wallet.balance
    ), "Pending payment is subtracted."

    assert ws_notification.call_count == 0, "Websocket notification not sent."


@pytest.mark.anyio
async def test_retry_pay_external_invoice_pending(
    from_wallet: Wallet,
    mocker: MockerFixture,
    external_funding_source: FakeWallet,
    settings: Settings,
):
    settings.lnbits_reserve_fee_min = 2000  # msats
    invoice_amount = 2106
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    preimage = "0000000000000000000000000000000000000000000000000000000000002106"
    payment_reponse_pending = PaymentResponse(
        ok=None, checking_id=external_invoice.checking_id, preimage=preimage
    )
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_pending),
    )
    ws_notification = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background",
        AsyncMock(return_value=None),
    )
    wallet = await get_wallet(from_wallet.id)
    assert wallet
    balance_before = wallet.balance
    await pay_invoice(
        wallet_id=from_wallet.id,
        payment_request=external_invoice.payment_request,
    )
    assert ws_notification.call_count == 0, "Websocket notification not sent."
    with pytest.raises(PaymentError, match="Payment is still pending."):
        await pay_invoice(
            wallet_id=from_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    wallet = await get_wallet(from_wallet.id)
    assert wallet
    reserve_fee_sat = int(abs(settings.lnbits_reserve_fee_min // 1000))

    assert (
        balance_before - invoice_amount - reserve_fee_sat == wallet.balance
    ), "Failed payment is subtracted."

    assert ws_notification.call_count == 0, "Websocket notification not sent."


@pytest.mark.anyio
async def test_pay_external_invoice_success(
    from_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    invoice_amount = 2104
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    preimage = "0000000000000000000000000000000000000000000000000000000000002104"
    payment_reponse_pending = PaymentResponse(
        ok=True, checking_id=external_invoice.checking_id, preimage=preimage
    )
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_pending),
    )
    ws_notification = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background",
        AsyncMock(return_value=None),
    )
    wallet = await get_wallet(from_wallet.id)
    assert wallet
    balance_before = wallet.balance
    payment = await pay_invoice(
        wallet_id=from_wallet.id,
        payment_request=external_invoice.payment_request,
    )

    _payment = await get_standalone_payment(payment.payment_hash)
    assert _payment
    assert _payment.status == PaymentState.SUCCESS.value
    assert _payment.checking_id == payment.payment_hash
    assert _payment.amount == -2104_000
    assert _payment.bolt11 == external_invoice.payment_request
    assert _payment.preimage == preimage

    wallet = await get_wallet(from_wallet.id)
    assert wallet
    assert (
        balance_before - invoice_amount == wallet.balance
    ), "Success payment is subtracted."

    assert ws_notification.call_count == 1, "Websocket notification sent."


@pytest.mark.anyio
async def test_retry_pay_success(
    from_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    invoice_amount = 2107
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    preimage = "0000000000000000000000000000000000000000000000000000000000002107"
    payment_reponse_pending = PaymentResponse(
        ok=True, checking_id=external_invoice.checking_id, preimage=preimage
    )
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_pending),
    )
    ws_notification = mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background",
        AsyncMock(return_value=None),
    )
    wallet = await get_wallet(from_wallet.id)
    assert wallet
    balance_before = wallet.balance
    await pay_invoice(
        wallet_id=from_wallet.id,
        payment_request=external_invoice.payment_request,
    )
    assert ws_notification.call_count == 1, "Websocket notification sent."

    with pytest.raises(PaymentError, match="Payment already paid."):
        await pay_invoice(
            wallet_id=from_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    wallet = await get_wallet(from_wallet.id)
    assert wallet
    assert (
        balance_before - invoice_amount == wallet.balance
    ), "Only one successful payment is subtracted."

    assert ws_notification.call_count == 1, "No new websocket notification sent."


@pytest.mark.anyio
async def test_pay_external_invoice_success_with_backend_checking_id(
    from_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    invoice_amount = 2108
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id
    backend_checking_id = f"backend_{external_invoice.checking_id}"

    preimage = "0000000000000000000000000000000000000000000000000000000000002108"
    payment_reponse_success = PaymentResponse(
        ok=True, checking_id=backend_checking_id, preimage=preimage
    )
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_success),
    )
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=external_funding_source,
    )

    payment = await pay_invoice(
        wallet_id=from_wallet.id,
        payment_request=external_invoice.payment_request,
    )

    stored_payment = await get_standalone_payment(external_invoice.checking_id)
    assert stored_payment
    assert stored_payment.status == PaymentState.SUCCESS.value
    assert stored_payment.checking_id == backend_checking_id
    assert stored_payment.payment_hash == external_invoice.checking_id
    assert payment.checking_id == backend_checking_id


@pytest.mark.anyio
async def test_pay_external_invoice_success_without_checking_id(
    from_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    invoice_amount = 2110
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    preimage = "0000000000000000000000000000000000000000000000000000000000002110"
    payment_response_success = PaymentResponse(
        ok=True, checking_id=None, preimage=preimage
    )
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_response_success),
    )
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=external_funding_source,
    )

    returned_payment = await pay_invoice(
        wallet_id=from_wallet.id,
        payment_request=external_invoice.payment_request,
    )

    payment = await get_standalone_payment(external_invoice.checking_id)

    assert payment
    assert payment.status == PaymentState.SUCCESS.value

    assert payment.checking_id == external_invoice.checking_id
    assert payment.payment_hash == external_invoice.checking_id
    assert payment.amount == -2110_000
    assert payment.preimage == preimage
    assert returned_payment.checking_id == external_invoice.checking_id


@pytest.mark.anyio
async def test_service_fee(
    from_wallet: Wallet,
    to_wallet: Wallet,
    mocker: MockerFixture,
    external_funding_source: FakeWallet,
    settings: Settings,
):
    invoice_amount = 2112
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    preimage = "0000000000000000000000000000000000000000000000000000000000002112"
    payment_reponse_success = PaymentResponse(
        ok=True, checking_id=external_invoice.checking_id, preimage=preimage
    )
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_success),
    )

    settings.lnbits_service_fee_wallet = to_wallet.id
    settings.lnbits_service_fee = 20

    payment = await pay_invoice(
        wallet_id=from_wallet.id,
        payment_request=external_invoice.payment_request,
    )

    _payment = await get_standalone_payment(payment.payment_hash)
    assert _payment
    assert _payment.status == PaymentState.SUCCESS.value
    assert _payment.checking_id == payment.payment_hash
    assert _payment.amount == -2112_000
    assert _payment.fee == -422_400
    assert _payment.bolt11 == external_invoice.payment_request
    assert _payment.preimage == preimage

    service_fee_payment = await get_standalone_payment(
        f"service_fee_{payment.payment_hash}",
    )
    assert service_fee_payment
    assert service_fee_payment.status == PaymentState.SUCCESS.value
    assert service_fee_payment.checking_id == f"service_fee_{payment.payment_hash}"
    assert service_fee_payment.amount == 422_400
    assert service_fee_payment.bolt11 == external_invoice.payment_request
    assert service_fee_payment.preimage is None


@pytest.fixture
async def service_fee_wallets(
    from_wallet: Wallet,
    settings: Settings,
    mocker: MockerFixture,
    external_funding_source: FakeWallet,
) -> tuple[Wallet, Wallet]:
    payer = await create_wallet(user_id=from_wallet.user)
    fee_wallet = await create_wallet(user_id=from_wallet.user)
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=external_funding_source,
    )
    mocker.patch(
        "lnbits.core.services.payments.send_payment_notification_in_background"
    )
    await update_wallet_balance(payer, 10_000)
    settings.lnbits_service_fee_wallet = fee_wallet.id
    settings.lnbits_service_fee = 1
    settings.lnbits_service_fee_max = 0
    return payer, fee_wallet


@pytest.fixture
async def pending_service_fee_payment(
    service_fee_wallets: tuple[Wallet, Wallet],
    external_funding_source: FakeWallet,
    mocker: MockerFixture,
) -> Payment:
    payer, _ = service_fee_wallets
    invoice = await external_funding_source.create_invoice(1_000)
    assert invoice.payment_request
    mocker.patch.object(
        external_funding_source,
        "pay_invoice",
        AsyncMock(
            return_value=PaymentResponse(
                ok=None, checking_id=f"backend_{invoice.checking_id}"
            )
        ),
    )
    payment = await pay_invoice(
        wallet_id=payer.id, payment_request=invoice.payment_request
    )
    assert payment.pending
    assert await get_standalone_payment(f"service_fee_{payment.payment_hash}") is None
    return payment


@pytest.mark.anyio
@pytest.mark.parametrize("succeeds", [False, True], ids=["failed", "success"])
async def test_service_fee_after_payment_timeout(
    service_fee_wallets: tuple[Wallet, Wallet],
    external_funding_source: FakeWallet,
    settings: Settings,
    mocker: MockerFixture,
    succeeds: bool,
):
    payer, fee_wallet = service_fee_wallets
    invoice = await external_funding_source.create_invoice(1_000)
    assert invoice.payment_request
    settings.lnbits_funding_source_pay_invoice_wait_seconds = 1

    async def unresolved_payment(*args, **kwargs):
        await asyncio.Event().wait()

    mocker.patch.object(
        external_funding_source,
        "pay_invoice",
        AsyncMock(side_effect=unresolved_payment),
    )
    status_mock = mocker.patch.object(
        external_funding_source,
        "get_payment_status",
        AsyncMock(return_value=PaymentPendingStatus()),
    )
    payment = await pay_invoice(
        wallet_id=payer.id, payment_request=invoice.payment_request
    )
    fee_id = f"service_fee_{payment.payment_hash}"
    assert payment.pending
    assert await get_standalone_payment(fee_id) is None

    payment = await update_pending_payment(payment)
    assert payment.pending
    assert await get_standalone_payment(fee_id) is None

    status_mock.return_value = (
        PaymentSuccessStatus(fee_msat=2_000) if succeeds else PaymentFailedStatus()
    )
    payment = await update_pending_payment(payment)
    stored = await get_payment(payment.checking_id)
    assert stored.status == (PaymentState.SUCCESS if succeeds else PaymentState.FAILED)
    fee_payment = await get_standalone_payment(fee_id)
    if succeeds:
        assert stored.fee == -12_000
        assert fee_payment is not None
        assert fee_payment.status == PaymentState.SUCCESS
        assert fee_payment.wallet_id == fee_wallet.id
        assert fee_payment.amount == 10_000
    else:
        assert fee_payment is None


@pytest.mark.anyio
async def test_service_fee_repeated_success_credits_once(
    pending_service_fee_payment: Payment,
    service_fee_wallets: tuple[Wallet, Wallet],
    external_funding_source: FakeWallet,
    mocker: MockerFixture,
):
    _, fee_wallet = service_fee_wallets
    stale_payment = pending_service_fee_payment.copy(deep=True)
    mocker.patch.object(
        external_funding_source,
        "get_payment_status",
        AsyncMock(return_value=PaymentSuccessStatus()),
    )

    first = await update_pending_payment(pending_service_fee_payment)
    second = await update_pending_payment(stale_payment)

    assert first.success and second.success
    fees = await get_payments_paginated(wallet_id=fee_wallet.id)
    assert fees.total == 1
    assert fees.data[0].amount == 10_000
    assert fees.data[0].checking_id == f"service_fee_{first.payment_hash}"


@pytest.mark.anyio
async def test_service_fee_concurrent_success_credits_once(
    pending_service_fee_payment: Payment,
    service_fee_wallets: tuple[Wallet, Wallet],
    external_funding_source: FakeWallet,
    mocker: MockerFixture,
):
    _, fee_wallet = service_fee_wallets
    ready = asyncio.Event()
    checks = 0

    async def successful_status(checking_id):
        nonlocal checks
        checks += 1
        if checks == 2:
            ready.set()
        await asyncio.wait_for(ready.wait(), timeout=2)
        return PaymentSuccessStatus()

    mocker.patch.object(
        external_funding_source,
        "get_payment_status",
        AsyncMock(side_effect=successful_status),
    )
    results = await asyncio.gather(
        update_pending_payment(pending_service_fee_payment.copy(deep=True)),
        update_pending_payment(pending_service_fee_payment.copy(deep=True)),
        return_exceptions=True,
    )

    fees = await get_payments_paginated(wallet_id=fee_wallet.id)
    assert fees.total == 1
    assert fees.data[0].amount == 10_000
    errors = [
        type(result).__name__ for result in results if isinstance(result, Exception)
    ]
    assert errors == [], "Both successful confirmations must complete without errors"
    assert all(isinstance(result, Payment) and result.success for result in results)


@pytest.mark.anyio
async def test_service_fee_settles_after_payer_wallet_deleted(
    pending_service_fee_payment: Payment,
    service_fee_wallets: tuple[Wallet, Wallet],
    external_funding_source: FakeWallet,
    mocker: MockerFixture,
):
    payer, fee_wallet = service_fee_wallets
    await delete_wallet(payer.user, payer.id)
    mocker.patch.object(
        external_funding_source,
        "get_payment_status",
        AsyncMock(return_value=PaymentSuccessStatus()),
    )

    payment = await update_pending_payment(pending_service_fee_payment)

    stored = await get_payment(payment.checking_id)
    assert stored.success
    assert stored.fee == -10_000
    fees = await get_payments_paginated(wallet_id=fee_wallet.id)
    assert fees.total == 1
    assert fees.data[0].amount == 10_000


@pytest.mark.anyio
@pytest.mark.parametrize("ignore_internal", [False, True])
async def test_service_fee_internal_payment_respects_setting(
    service_fee_wallets: tuple[Wallet, Wallet],
    settings: Settings,
    mocker: MockerFixture,
    ignore_internal: bool,
):
    payer, fee_wallet = service_fee_wallets
    receiver = await create_wallet(user_id=payer.user)
    settings.lnbits_service_fee_ignore_internal = ignore_internal
    mocker.patch.object(task_manager.internal_invoice_queue, "put_nowait")
    invoice = await create_invoice(
        wallet_id=receiver.id, amount=1_000, memo="Service fee"
    )

    payment = await pay_invoice(wallet_id=payer.id, payment_request=invoice.bolt11)

    assert payment.success and payment.is_internal
    assert payment.fee == (0 if ignore_internal else -10_000)
    assert (await get_payment(invoice.checking_id)).success
    fees = await get_payments_paginated(wallet_id=fee_wallet.id)
    assert fees.total == (0 if ignore_internal else 1)
    if not ignore_internal:
        assert fees.data[0].amount == 10_000


@pytest.mark.anyio
async def test_service_fee_incoming_success_does_not_credit(
    service_fee_wallets: tuple[Wallet, Wallet],
    external_funding_source: FakeWallet,
    mocker: MockerFixture,
):
    receiver, fee_wallet = service_fee_wallets
    invoice = await create_invoice(wallet_id=receiver.id, amount=1_000, memo="Incoming")
    mocker.patch.object(
        external_funding_source,
        "get_invoice_status",
        AsyncMock(return_value=PaymentSuccessStatus()),
    )

    invoice = await get_payment(invoice.checking_id)
    payment = await update_pending_payment(invoice)

    assert payment.success and payment.is_in
    fees = await get_payments_paginated(wallet_id=fee_wallet.id)
    assert fees.total == 0


@pytest.mark.anyio
async def test_get_payments_for_user(to_wallet: Wallet):
    all_payments = await get_payments_paginated()
    total_before = all_payments.total

    user = await create_user_account()
    wallet_one = await create_wallet(user_id=user.id, wallet_name="first wallet")
    wallet_two = await create_wallet(user_id=user.id, wallet_name="second wallet")

    user_payments = await get_payments_paginated(user_id=user.id)
    assert user_payments.total == 0

    payment = await create_invoice(wallet_id=wallet_one.id, amount=100, memo="one")
    user_payments = await get_payments_paginated(user_id=user.id)
    assert user_payments.total == 1
    # this will create a payment in the to_wallet that we need to count for at the end
    await pay_invoice(
        wallet_id=to_wallet.id,
        payment_request=payment.bolt11,
    )
    user_payments = await get_payments_paginated(user_id=user.id)
    assert user_payments.total == 1

    payment = await create_invoice(wallet_id=wallet_one.id, amount=3, memo="two")
    user_payments = await get_payments_paginated(user_id=user.id)
    assert user_payments.total == 2

    payment = await create_invoice(wallet_id=wallet_two.id, amount=3, memo="three")
    user_payments = await get_payments_paginated(user_id=user.id)
    assert user_payments.total == 3

    await pay_invoice(
        wallet_id=wallet_one.id,
        payment_request=payment.bolt11,
    )
    user_payments = await get_payments_paginated(user_id=user.id)
    assert user_payments.total == 4

    all_payments = await get_payments_paginated()
    total_after = all_payments.total

    assert total_after == total_before + 5, "Total payments should be updated."


@pytest.mark.anyio
async def test_get_payments_for_non_user():
    user_payments = await get_payments_paginated(user_id="nonexistent")
    assert (
        user_payments.total == 0
    ), "No payments should be found for non-existent user."
