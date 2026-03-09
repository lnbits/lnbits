from typing import Any

import pytest
from httpx import AsyncClient
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.misc import SimpleStatus
from lnbits.fiat.base import FiatSubscriptionResponse


class FakeStripeWallet:
    def __init__(self, secret: str | None = "secret"):
        self._secret = secret

    async def create_terminal_connection_token(self) -> dict[str, str]:
        if self._secret is None:
            return {}
        return {"secret": self._secret}


@pytest.mark.anyio
async def test_fiat_api_test_provider_and_subscription_lifecycle(
    client: AsyncClient,
    superuser_token: str,
    adminkey_headers_from: dict[str, str],
    from_wallet,
    mocker: MockerFixture,
):
    test_connection = mocker.patch(
        "lnbits.core.views.fiat_api.test_connection",
        mocker.AsyncMock(return_value=SimpleStatus(success=True, message="ok")),
    )
    response = await client.put(
        "/api/v1/fiat/check/stripe",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    test_connection.assert_awaited_once_with("stripe")

    provider = mocker.Mock()
    provider.create_subscription = mocker.AsyncMock(
        return_value=FiatSubscriptionResponse(
            ok=True,
            subscription_request_id="sub-1",
            checkout_session_url="https://stripe.example/checkout",
        )
    )
    provider.cancel_subscription = mocker.AsyncMock(
        return_value=FiatSubscriptionResponse(ok=True, subscription_request_id="sub-1")
    )
    get_provider = mocker.patch(
        "lnbits.core.views.fiat_api.get_fiat_provider",
        mocker.AsyncMock(return_value=provider),
    )

    mismatch = await client.post(
        "/api/v1/fiat/stripe/subscription",
        headers=adminkey_headers_from,
        json={
            "subscription_id": "sub-1",
            "quantity": 2,
            "payment_options": {"wallet_id": "wrong-wallet"},
        },
    )
    assert mismatch.status_code == 403

    created = await client.post(
        "/api/v1/fiat/stripe/subscription",
        headers=adminkey_headers_from,
        json={
            "subscription_id": "sub-1",
            "quantity": 2,
            "payment_options": {"memo": "hello", "wallet_id": from_wallet.id},
        },
    )
    assert created.status_code == 200
    assert created.json()["checkout_session_url"] == "https://stripe.example/checkout"
    provider.create_subscription.assert_awaited_once()
    assert provider.create_subscription.await_args.args[2].wallet_id == from_wallet.id

    cancelled = await client.delete(
        "/api/v1/fiat/stripe/subscription/sub-1",
        headers=adminkey_headers_from,
    )
    assert cancelled.status_code == 200
    provider.cancel_subscription.assert_awaited_once_with("sub-1", from_wallet.id)
    assert get_provider.await_count == 3


@pytest.mark.anyio
async def test_fiat_api_connection_token_validates_provider_configuration(
    client: AsyncClient,
    superuser_token: str,
    mocker: MockerFixture,
):
    headers = {"Authorization": f"Bearer {superuser_token}"}

    not_found = mocker.patch(
        "lnbits.core.views.fiat_api.get_fiat_provider",
        mocker.AsyncMock(return_value=None),
    )
    missing = await client.post("/api/v1/fiat/stripe/connection_token", headers=headers)
    assert missing.status_code == 404
    assert not_found.await_count == 1

    unsupported_provider = mocker.patch(
        "lnbits.core.views.fiat_api.get_fiat_provider",
        mocker.AsyncMock(return_value=object()),
    )
    unsupported = await client.post(
        "/api/v1/fiat/paypal/connection_token", headers=headers
    )
    assert unsupported.status_code == 400
    assert unsupported_provider.await_count == 1

    mocker.patch("lnbits.core.views.fiat_api.StripeWallet", FakeStripeWallet)
    bad_wallet = FakeStripeWallet(secret=None)
    bad_provider = mocker.patch(
        "lnbits.core.views.fiat_api.get_fiat_provider",
        mocker.AsyncMock(return_value=bad_wallet),
    )
    no_secret = await client.post(
        "/api/v1/fiat/stripe/connection_token", headers=headers
    )
    assert no_secret.status_code == 500
    assert no_secret.json()["detail"] == "Failed to create connection token"
    assert bad_provider.await_count == 1

    good_wallet = FakeStripeWallet(secret="tok_live")
    good_provider = mocker.patch(
        "lnbits.core.views.fiat_api.get_fiat_provider",
        mocker.AsyncMock(return_value=good_wallet),
    )
    ok = await client.post("/api/v1/fiat/stripe/connection_token", headers=headers)
    assert ok.status_code == 200
    assert ok.json() == {"secret": "tok_live"}
    assert good_provider.await_count == 1
