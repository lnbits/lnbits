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
from lnbits.core.models import Payment, PaymentState, Wallet
from lnbits.core.services import create_invoice, create_user_account, pay_invoice
from lnbits.core.services.payments import update_wallet_balance
from lnbits.exceptions import InvoiceError, PaymentError
from lnbits.settings import Settings
from lnbits.tasks import (
    create_permanent_task,
    internal_invoice_listener,
    register_invoice_listener,
)
from lnbits.wallets.base import PaymentResponse
from lnbits.wallets.fake import FakeWallet


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
async def test_notification_for_internal_payment(to_wallet: Wallet):
    test_name = "test_notification_for_internal_payment"

    create_permanent_task(internal_invoice_listener)
    invoice_queue: asyncio.Queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, test_name)

    payment = await create_invoice(
        wallet_id=to_wallet.id,
        amount=123,
        memo=test_name,
        webhook="http://test.404.lnbits.com",
    )
    await pay_invoice(
        wallet_id=to_wallet.id, payment_request=payment.bolt11, extra={"tag": "lnurlp"}
    )
    await asyncio.sleep(1)

    while True:
        _payment: Payment = invoice_queue.get_nowait()  # raises if queue empty
        assert _payment
        if _payment.memo == test_name:
            assert _payment.status == PaymentState.SUCCESS.value
            assert _payment.bolt11 == payment.bolt11
            assert _payment.amount == 123_000
            updated_payment = await get_payment(_payment.checking_id)
            assert updated_payment.webhook_status == "404"

            break  # we found our payment, success


@pytest.mark.anyio
async def test_pay_failed(
    to_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    payment_reponse_failed = PaymentResponse(ok=False, error_message="Mock failure!")
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_failed),
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
async def test_pay_external_invoice_pending(
    from_wallet: Wallet,
    mocker: MockerFixture,
    external_funding_source: FakeWallet,
    settings: Settings,
):
    settings.lnbits_reserve_fee_min = 1000  # msats
    invoice_amount = 2103
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    payment_reponse_pending = PaymentResponse(
        ok=None, checking_id=external_invoice.checking_id
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
    assert _payment.status == PaymentState.PENDING.value
    assert _payment.checking_id == payment.payment_hash
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
async def test_pay_external_invoice_success_bad_checking_id(
    from_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    invoice_amount = 2108
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id
    bad_checking_id = f"bad_{external_invoice.checking_id}"

    preimage = "0000000000000000000000000000000000000000000000000000000000002108"
    payment_reponse_success = PaymentResponse(
        ok=True, checking_id=bad_checking_id, preimage=preimage
    )
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_success),
    )

    with pytest.raises(PaymentError):
        await pay_invoice(
            wallet_id=from_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    payment = await get_standalone_payment(bad_checking_id)
    assert payment is None, "Payment should not be created with bad checking_id"


@pytest.mark.anyio
async def test_no_checking_id(
    from_wallet: Wallet, mocker: MockerFixture, external_funding_source: FakeWallet
):
    invoice_amount = 2110
    external_invoice = await external_funding_source.create_invoice(invoice_amount)
    assert external_invoice.payment_request
    assert external_invoice.checking_id

    preimage = "0000000000000000000000000000000000000000000000000000000000002110"
    payment_reponse_pending = PaymentResponse(
        ok=True, checking_id=None, preimage=preimage
    )
    mocker.patch(
        "lnbits.wallets.FakeWallet.pay_invoice",
        AsyncMock(return_value=payment_reponse_pending),
    )

    with pytest.raises(PaymentError):
        await pay_invoice(
            wallet_id=from_wallet.id,
            payment_request=external_invoice.payment_request,
        )

    payment = await get_standalone_payment(external_invoice.checking_id)

    assert payment
    assert payment.status == PaymentState.FAILED.value

    assert payment.checking_id == external_invoice.checking_id
    assert payment.payment_hash == external_invoice.checking_id
    assert payment.amount == -2110_000
    assert payment.preimage is None


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
