"""Keep Eclair offer payments within the wallet's reserved routing fees."""

from urllib.parse import parse_qs

import httpx
import pytest

from lnbits.core.crud import create_wallet, get_wallet
from lnbits.core.services import create_user_account, pay_offer, update_wallet_balance
from lnbits.exceptions import PaymentError
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.eclair import EclairWallet
from tests.helpers import BOLT12_OFFER


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fee_limit_msat,route_fee_msat,success",
    [
        (0, 0, True),
        (0, 1, False),
        (999, 999, False),
        (1000, 1000, True),
        (1000, 1001, False),
        (1999, 1000, True),
        (1999, 1999, False),
        (2000, 10000, False),
    ],
)
async def test_eclair_offer_fee_reserve_preserves_balance(
    app, settings, monkeypatch, fee_limit_msat, route_fee_msat, success
):
    settings.lnbits_reserve_fee_min = fee_limit_msat
    settings.lnbits_reserve_fee_percent = 0
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 102)
    preimage, payment_hash = random_secret_and_hash()
    node_debit_msat = 0

    def handler(request):
        nonlocal node_debit_msat
        if request.url.path == "/payoffer":
            form = parse_qs(request.content.decode())
            amount_msat = int(form["amountMsat"][0])
            # Eclair v0.11.0 accepts these two caps and uses the larger one.
            # Omitted caps retain the node defaults (21 sats and 3%).
            flat_msat = int(form.get("maxFeeFlatSat", ["21"])[0]) * 1000
            proportional_msat = int(
                amount_msat * float(form.get("maxFeePct", ["3"])[0]) / 100
            )
            if route_fee_msat > max(flat_msat, proportional_msat):
                return httpx.Response(200, json={"type": "payment-failed"})
            node_debit_msat += amount_msat + route_fee_msat
            return httpx.Response(
                200,
                json={
                    "type": "payment-sent",
                    "paymentHash": payment_hash,
                    "paymentPreimage": preimage,
                },
            )
        assert request.url.path == "/getsentinfo"
        return httpx.Response(
            200,
            json=[
                {
                    "status": {
                        "type": "sent",
                        "feesPaid": route_fee_msat,
                        "paymentPreimage": preimage,
                    }
                }
            ],
        )

    backend = object.__new__(EclairWallet)
    backend.url = "http://eclair.test"
    async with httpx.AsyncClient(
        base_url=backend.url, transport=httpx.MockTransport(handler)
    ) as backend.client:
        monkeypatch.setattr(
            "lnbits.core.services.payments.get_funding_source", lambda: backend
        )
        if success:
            payment = await pay_offer(
                wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=100
            )
            assert payment.success
            assert payment.fee == -route_fee_msat
            assert node_debit_msat == 100_000 + route_fee_msat
        else:
            with pytest.raises(PaymentError, match="Payment failed"):
                await pay_offer(wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=100)
            assert node_debit_msat == 0

    after = await get_wallet(wallet.id)
    assert after and after.balance_msat == 102_000 - node_debit_msat
    assert after.balance_msat >= 0
