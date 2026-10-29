import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.payments import CreateInvoice
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.core.services.users import create_user_account
from lnbits.core.views.callback_api import handle_paypal_event


@pytest.mark.anyio
async def test_paypal_capture_completed_event_finds_the_payment(
    app, mocker: MockerFixture
):
    user = await create_user_account()
    payment = await create_wallet_invoice(
        user.wallets[0].id, CreateInvoice(out=False, amount=11, memo="paypal capture")
    )
    fiat_status = mocker.patch(
        "lnbits.core.views.callback_api.check_fiat_status", mocker.AsyncMock()
    )

    await handle_paypal_event(
        {
            "id": "WH-CAPTURE-1",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource_type": "capture",
            "resource": {
                "id": "3C679366HH908993F",
                "status": "COMPLETED",
                "amount": {"currency_code": "USD", "value": "5.00"},
                "invoice_id": payment.payment_hash,
                "custom_id": payment.payment_hash,
                "supplementary_data": {
                    "related_ids": {"order_id": "5O190127TN364715T"}
                },
            },
        }
    )
    fiat_status.assert_awaited_once()
