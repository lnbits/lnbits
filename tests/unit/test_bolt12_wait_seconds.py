import asyncio
from unittest.mock import AsyncMock

import pytest

from lnbits.core.crud import create_wallet, get_super_settings, update_admin_settings
from lnbits.core.services import create_user_account, pay_invoice, pay_offer
from lnbits.core.services.payments import update_wallet_balance
from lnbits.core.services.settings import dict_to_settings, update_cached_settings
from lnbits.settings import EditableSettings, FundingSourcesSettings
from lnbits.wallets.base import PaymentResponse
from lnbits.wallets.fake import FakeWallet
from tests.helpers import BOLT12_OFFER


def test_bolt12_wait_setting_defaults_and_validation(settings):
    assert FundingSourcesSettings().lnbits_funding_source_pay_offer_wait_seconds == 20
    parsed = dict_to_settings({"lnbits_funding_source_pay_offer_wait_seconds": 17})
    assert parsed.lnbits_funding_source_pay_offer_wait_seconds == 17
    invoice_wait = settings.lnbits_funding_source_pay_invoice_wait_seconds
    update_cached_settings({"lnbits_funding_source_pay_offer_wait_seconds": 17})
    assert settings.lnbits_funding_source_pay_offer_wait_seconds == 17
    assert settings.lnbits_funding_source_pay_invoice_wait_seconds == invoice_wait
    with pytest.raises(ValueError):
        FundingSourcesSettings(lnbits_funding_source_pay_offer_wait_seconds=-1)


@pytest.mark.anyio
async def test_bolt12_wait_setting_persists(app):
    previous = await get_super_settings()
    assert previous
    try:
        await update_admin_settings(
            EditableSettings(lnbits_funding_source_pay_offer_wait_seconds=17)
        )
        stored = await get_super_settings()
        assert stored and stored.lnbits_funding_source_pay_offer_wait_seconds == 17
        assert (
            stored.lnbits_funding_source_pay_invoice_wait_seconds
            == previous.lnbits_funding_source_pay_invoice_wait_seconds
        )
    finally:
        await update_admin_settings(
            EditableSettings(
                lnbits_funding_source_pay_offer_wait_seconds=(
                    previous.lnbits_funding_source_pay_offer_wait_seconds
                )
            )
        )


@pytest.mark.anyio
@pytest.mark.parametrize("is_offer", [True, False])
@pytest.mark.parametrize(("offer_wait", "invoice_wait"), [(17, 3), (0, 0)])
async def test_bolt12_wait_setting_is_independent(
    app, settings, monkeypatch, is_offer, offer_wait, invoice_wait
):
    settings.lnbits_funding_source_pay_offer_wait_seconds = offer_wait
    settings.lnbits_funding_source_pay_invoice_wait_seconds = invoice_wait
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)
    observed = []
    wait_for = asyncio.wait_for

    async def observe_wait(task, timeout):
        if task.get_name().startswith("fundingsource_pay_"):
            observed.append(timeout)
        return await wait_for(task, timeout=timeout)

    monkeypatch.setattr(asyncio, "wait_for", observe_wait)
    if is_offer:
        payment = await pay_offer(wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=1)
    else:
        invoice = await FakeWallet().create_invoice(1)
        monkeypatch.setattr(
            FakeWallet,
            "pay_invoice",
            AsyncMock(
                return_value=PaymentResponse(ok=True, checking_id=invoice.checking_id)
            ),
        )
        assert invoice.payment_request
        payment = await pay_invoice(
            wallet_id=wallet.id, payment_request=invoice.payment_request
        )
    assert payment.success
    assert observed == [max(1, offer_wait if is_offer else invoice_wait)]
