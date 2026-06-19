import time

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models import Payment, Wallet
from lnbits.core.services.fiat_providers import check_stripe_signature
from lnbits.core.services.notifications import (
    create_webhook_signature,
    dispatch_webhook,
)
from lnbits.settings import Settings


class MockResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self):
        pass


class MockAsyncClient:
    """Captures the constructor headers and the post() call of dispatch_webhook."""

    def __init__(self, *_args, **kwargs):
        self.headers = kwargs.get("headers", {})
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return MockResponse(200)


def _patch_client(mocker: MockerFixture) -> dict:
    """Patches the httpx client used by dispatch_webhook and captures it."""
    captured: dict = {}

    def _factory(*args, **kwargs):
        client = MockAsyncClient(*args, **kwargs)
        captured["client"] = client
        return client

    mocker.patch(
        "lnbits.core.services.notifications.httpx.AsyncClient",
        side_effect=_factory,
    )
    captured["mark_sent"] = mocker.patch(
        "lnbits.core.services.notifications.mark_webhook_sent"
    )
    return captured


def _payment(webhook: str = "https://example.com/hook") -> Payment:
    return Payment(
        checking_id="test_checking_id",
        payment_hash="test_payment_hash",
        wallet_id="test_wallet_id",
        amount=1000,
        fee=0,
        bolt11="lnbc1test",
        webhook=webhook,
    )


def _wallet(webhook_secret: str | None) -> Wallet:
    return Wallet(
        id="test_wallet_id",
        user="test_user_id",
        name="Test wallet",
        adminkey="admin",
        inkey="invoice",
        webhook_secret=webhook_secret,
    )


def test_create_webhook_signature_format():
    payload = b'{"amount":1000}'
    header = create_webhook_signature(payload, "s3cr3t", 1700000000)
    assert header.startswith("t=1700000000,v1=")
    # v1 is a hex-encoded sha256 digest
    v1 = header.split("v1=")[1]
    assert len(v1) == 64
    int(v1, 16)  # raises if not valid hex


def test_create_webhook_signature_roundtrip_verifies():
    # signed with create_webhook_signature, verified with the inbound Stripe
    # scheme: proves both directions share the same HMAC-SHA256 scheme.
    payload = b'{"amount":1000,"memo":"test"}'
    secret = "s3cr3t"
    header = create_webhook_signature(payload, secret, int(time.time()))

    # should not raise
    check_stripe_signature(payload, header, secret)


def test_create_webhook_signature_rejects_tampered_payload():
    secret = "s3cr3t"
    header = create_webhook_signature(b'{"amount":1000}', secret, int(time.time()))

    with pytest.raises(ValueError, match="signature verification failed"):
        check_stripe_signature(b'{"amount":9999}', header, secret)


def test_create_webhook_signature_rejects_wrong_secret():
    payload = b'{"amount":1000}'
    header = create_webhook_signature(payload, "s3cr3t", int(time.time()))

    with pytest.raises(ValueError, match="signature verification failed"):
        check_stripe_signature(payload, header, "wrong-secret")


@pytest.mark.anyio
async def test_dispatch_webhook_signs_payload(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_webhook_signing_enabled = True
    captured = _patch_client(mocker)

    payment = _payment()
    wallet = _wallet("s3cr3t")
    await dispatch_webhook(payment, wallet)

    client = captured["client"]
    # signature header is set on the client and verifies against the secret
    signature = client.headers["LNbits-Signature"]
    assert client.headers["Content-Type"] == "application/json"
    body = payment.json().encode()
    check_stripe_signature(body, signature, "s3cr3t")

    # body is sent verbatim via content= (not double-encoded via json=)
    assert client.calls[0][1]["content"] == body
    captured["mark_sent"].assert_awaited_once_with(payment.payment_hash, "200")


@pytest.mark.anyio
async def test_dispatch_webhook_fetches_wallet_when_not_passed(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_webhook_signing_enabled = True
    captured = _patch_client(mocker)
    # when no wallet is passed, dispatch_webhook loads it via get_wallet
    mocker.patch(
        "lnbits.core.services.notifications.get_wallet",
        mocker.AsyncMock(return_value=_wallet("s3cr3t")),
    )

    payment = _payment()
    await dispatch_webhook(payment)

    signature = captured["client"].headers["LNbits-Signature"]
    check_stripe_signature(payment.json().encode(), signature, "s3cr3t")


@pytest.mark.anyio
async def test_dispatch_webhook_no_header_when_disabled(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_webhook_signing_enabled = False
    captured = _patch_client(mocker)

    await dispatch_webhook(_payment(), _wallet("s3cr3t"))

    assert "LNbits-Signature" not in captured["client"].headers


@pytest.mark.anyio
async def test_dispatch_webhook_no_header_without_secret(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_webhook_signing_enabled = True
    captured = _patch_client(mocker)

    # wallet without a webhook_secret -> unsigned (backwards compatible)
    await dispatch_webhook(_payment(), _wallet(None))

    assert "LNbits-Signature" not in captured["client"].headers
