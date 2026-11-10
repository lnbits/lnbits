import httpx
import pytest

from lnbits.core.crud import create_wallet, get_payments, get_wallet
from lnbits.core.services import create_user_account, pay_offer, update_wallet_balance
from lnbits.core.services.payments import update_pending_payment
from lnbits.exceptions import PaymentError
from lnbits.wallets.clnrest import CLNRestWallet
from tests.helpers import BOLT12_OFFER


@pytest.fixture(params=["pay", "renepay"])
async def clnrest_offer_backend(request, monkeypatch, settings):
    endpoint = f"/v1/{request.param}"
    calls = []
    outcome = {"stage": endpoint, "response": httpx.Response(500)}

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == outcome["stage"]:
            response = outcome["response"]
            if isinstance(response, Exception):
                raise response
            return response
        assert request.url.path == "/v1/fetchinvoice"
        return httpx.Response(200, json={"invoice": "lni1resolved", "changes": {}})

    settings.clnrest_url = "http://localhost:3010"
    settings.clnrest_readonly_rune = "read"
    settings.clnrest_pay_rune = "pay" if request.param == "pay" else None
    settings.clnrest_renepay_rune = "rene" if request.param == "renepay" else None
    async with httpx.AsyncClient(
        base_url=settings.clnrest_url, transport=httpx.MockTransport(handler)
    ) as client:
        monkeypatch.setattr(CLNRestWallet, "_create_client", lambda self: client)
        yield CLNRestWallet(), calls, outcome


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["fetchinvoice", "payment"])
@pytest.mark.parametrize(
    "body,definitive",
    [
        ({"error": {"code": -32602, "message": "Invalid parameters"}}, True),
        ({"error": {"code": 203, "message": "Permanent failure"}}, True),
        ({"error": {"code": 205, "message": "No route"}}, True),
        ({"error": {"code": 206, "message": "Route too expensive"}}, True),
        ({"error": {"code": 207, "message": "Invoice expired"}}, True),
        ({"error": {"code": 210, "message": "No payment in progress"}}, True),
        ({"error": {"code": 401, "message": "Unauthorized"}}, True),
        ({"error": {"code": -1, "message": "Unknown error"}}, False),
        ({"error": {"code": 200, "message": "Payment in progress"}}, False),
        ({"error": {"code": 201, "message": "Already paid"}}, False),
        ({"error": {"code": 999, "message": "Unknown code"}}, False),
        ({"error": {"code": 205.5, "message": "Malformed code"}}, False),
        ({"error": {"code": None, "message": "Missing code"}}, False),
        ({"error": "Internal server error"}, False),
        ({"error": None}, False),
        ({}, False),
        ([], False),
    ],
)
async def test_bolt12_clnrest_http_failure_classification(
    clnrest_offer_backend, stage, body, definitive
):
    backend, calls, outcome = clnrest_offer_backend
    if stage == "fetchinvoice":
        outcome["stage"] = "/v1/fetchinvoice"
    outcome["response"] = httpx.Response(500, json=body)
    response = await backend.pay_offer(BOLT12_OFFER, 20000, amount_msat=100000)
    assert response.ok is (False if stage == "fetchinvoice" or definitive else None)
    assert calls == (
        ["/v1/fetchinvoice"]
        if stage == "fetchinvoice"
        else ["/v1/fetchinvoice", outcome["stage"]]
    )


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["fetchinvoice", "payment"])
@pytest.mark.parametrize("error", ["http", "invalid_json", "timeout", "no_route"])
async def test_bolt12_clnrest_ambiguous_errors_do_not_refund(
    app, clnrest_offer_backend, monkeypatch, stage, error
):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)
    backend, calls, outcome = clnrest_offer_backend
    if stage == "fetchinvoice":
        outcome["stage"] = "/v1/fetchinvoice"
    outcome["response"] = {
        "http": httpx.Response(500, json={"error": {"message": "Response lost"}}),
        "invalid_json": httpx.Response(500, text="Invalid response"),
        "timeout": httpx.ReadTimeout("Response lost"),
        "no_route": httpx.Response(500, json={"error": {"code": 205}}),
    }[error]
    monkeypatch.setattr(
        "lnbits.core.services.payments.get_funding_source", lambda: backend
    )
    if stage == "fetchinvoice" or error == "no_route":
        with pytest.raises(PaymentError, match="Payment failed"):
            await pay_offer(wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=100)
        payments = await get_payments(wallet_id=wallet.id, outgoing=True)
        assert len(payments) == 1 and payments[0].failed
        expected_balance = 1_000_000
    else:
        payment = await pay_offer(
            wallet_id=wallet.id, offer=BOLT12_OFFER, amount_sat=100
        )
        assert payment.pending
        assert (await update_pending_payment(payment)).pending
        expected_balance = 880_000
    after = await get_wallet(wallet.id)
    assert after and after.balance_msat == expected_balance
    assert calls == (
        ["/v1/fetchinvoice"]
        if stage == "fetchinvoice"
        else ["/v1/fetchinvoice", outcome["stage"]]
    )
