"""Reject CLN invoices outside the amount authorized by the wallet owner."""

import json
from unittest.mock import Mock

import httpx
import pytest
from pyln.client import Millisatoshi

from lnbits.core.crud import create_wallet, get_wallet
from lnbits.core.services import create_user_account, pay_offer, update_wallet_balance
from lnbits.exceptions import PaymentError
from lnbits.utils.bolt12 import is_bolt12_invoice_amount_valid
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.clnrest import CLNRestWallet
from lnbits.wallets.corelightning import CoreLightningWallet
from tests.helpers import BOLT12_OFFER


@pytest.mark.parametrize("amount_msat", [None, 0, -1, True, 21000.5])
def test_invoice_amount_requires_explicit_positive_integer(amount_msat):
    assert not is_bolt12_invoice_amount_valid({}, amount_msat)


@pytest.fixture(params=["cln", "clnrest", "clnrest-renepay"])
async def cln_offer_backend(request, monkeypatch, settings):
    calls = []
    fetched = {"invoice": "lni1resolvedinvoice"}
    preimage, payment_hash = random_secret_and_hash()
    paid = {
        "status": "complete",
        "payment_hash": payment_hash,
        "payment_preimage": preimage,
        "amount_msat": 21000,
        "amount_sent_msat": 21050,
    }

    def rpc(method, payload):
        calls.append((method, payload))
        if method == "fetchinvoice":
            return fetched
        assert method in ("pay", "renepay")
        return paid

    if request.param == "cln":
        backend = object.__new__(CoreLightningWallet)
        backend.pay = "pay"
        backend.ln = Mock()
        backend.ln.call = rpc
        monkeypatch.setattr(
            "lnbits.core.services.payments.get_funding_source", lambda: backend
        )
        yield backend, fetched, calls
    else:
        renepay = request.param == "clnrest-renepay"
        monkeypatch.setattr(settings, "clnrest_pay_rune", None if renepay else "pay")
        monkeypatch.setattr(
            settings, "clnrest_renepay_rune", "rene" if renepay else None
        )
        backend = object.__new__(CLNRestWallet)
        backend.url = "http://clnrest.test"
        backend.pay_headers = {"rune": "pay"}
        backend.renepay_headers = {"rune": "rene"}
        backend.statuses = {"complete": True}

        def handler(request):
            return httpx.Response(
                200,
                json=rpc(
                    request.url.path.removeprefix("/v1/"), json.loads(request.content)
                ),
            )

        monkeypatch.setattr(
            "lnbits.core.services.payments.get_funding_source", lambda: backend
        )
        async with httpx.AsyncClient(
            base_url=backend.url, transport=httpx.MockTransport(handler)
        ) as backend.client:
            yield backend, fetched, calls


@pytest.mark.anyio
@pytest.mark.parametrize(
    "report",
    [
        {},  # Missing changes is not the same as an empty changes object.
        {"changes": None},
        {"changes": []},
        {"changes": "invalid"},
        {"changes": {"amount_msat": 1_000_000}},
        {"changes": {"amount_msat": 20000}},
        {"changes": {"amount_msat": "1000000msat"}},
        {"changes": {"amount_msat": None}},
        {"changes": {"amount_msat": 21000.5}},
        {"changes": {"amount_msat": 21000.0}},
        {"changes": {"amount_msat": True}},
        {"changes": {"amount_msat": "21sat"}},
        {"changes": {"amount_msat": "21000"}},
        {"changes": {"amount_msat": "9" * 4301 + "msat"}},
    ],
)
async def test_offer_amount_rejection_preserves_balance(app, cln_offer_backend, report):
    _, fetched, calls = cln_offer_backend
    fetched.update(report)
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)

    with pytest.raises(PaymentError, match="invoice amount.*authorized amount"):
        await pay_offer(wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=21)

    assert calls == [("fetchinvoice", {"offer": BOLT12_OFFER, "amount_msat": 21000})]
    after = await get_wallet(wallet.id)
    assert after and after.balance_msat == 1_000_000


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes", [{}, {"amount_msat": 21000}, {"amount_msat": "21000msat"}]
)
async def test_matching_invoice_amount_can_be_paid(cln_offer_backend, changes):
    backend, fetched, calls = cln_offer_backend
    fetched["changes"] = changes
    result = await backend.pay_offer(BOLT12_OFFER, 50, amount_msat=21000)
    assert result.success
    assert [method for method, _ in calls] in (
        ["fetchinvoice", "pay"],
        ["fetchinvoice", "renepay"],
    )


@pytest.mark.parametrize("amount", [21000, 20000, 1_000_000])
def test_pyln_millisatoshi_amount(amount):
    assert is_bolt12_invoice_amount_valid(
        {"amount_msat": Millisatoshi(amount)}, 21000
    ) is (amount == 21000)
