import ipaddress
from typing import cast
from uuid import uuid4

import httpx
import pytest
from bolt11.types import MilliSatoshi
from lnurl import (
    LnAddress,
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlResponseException,
    LnurlSuccessResponse,
    LnurlWithdrawResponse,
)
from lnurl.types import CallbackUrl, LightningInvoice
from pydantic import parse_obj_as
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import create_account, create_wallet, get_wallet
from lnbits.core.models import Account
from lnbits.core.models.lnurl import CreateLnurlPayment
from lnbits.core.models.wallets import Wallet
from lnbits.core.services import lnurl as lnurl_service
from lnbits.core.services.lnurl import (
    _get,
    _store_paylink,
    fetch_lnurl_pay_request,
    get_pr_from_lnurl,
    perform_withdraw,
)
from lnbits.settings import Settings
from tests.helpers import make_lnurl_pay_response

TEST_BOLT11 = (
    "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
    "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
    "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
    "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
    "6hjxepwp93cq398l3s"
)


@pytest.mark.anyio
async def test_lnurl_requests_reject_private_ips_by_default(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_lnurl_allow_private_ips = False

    with pytest.raises(
        LnurlResponseException, match="resolves to a private or non-global IP address"
    ):
        await lnurl_service._validate_lnurl_request_url(
            httpx.URL("https://169.254.169.254/latest/meta-data/"), tor_socks=None
        )

    mocker.patch(
        "lnbits.core.services.lnurl._resolve_lnurl_host",
        mocker.AsyncMock(return_value=[ipaddress.ip_address("10.0.0.1")]),
    )
    with pytest.raises(
        LnurlResponseException, match="resolves to a private or non-global IP address"
    ):
        await lnurl_service._validate_lnurl_request_url(
            httpx.URL("https://metadata.internal/"), tor_socks=None
        )

    settings.lnbits_lnurl_allow_private_ips = True
    with pytest.raises(LnurlResponseException, match="not allowed over HTTP"):
        await lnurl_service._validate_lnurl_request_url(
            httpx.URL("http://93.184.216.34/lnurl"), tor_socks=None
        )

    addresses, proxy = await lnurl_service._validate_lnurl_request_url(
        httpx.URL("http://127.0.0.1:8080/lnurl"), tor_socks=None
    )
    assert addresses == [ipaddress.ip_address("127.0.0.1")]
    assert proxy is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("url", "message"),
    [
        (
            "https://user:password@example.com/lnurl",
            "LNURL request URL must not include credentials.",
        ),
        ("https:///lnurl", "LNURL request target hostname is missing."),
        ("https://example.com:99999/lnurl", "LNURL request target port is invalid."),
        (
            "ftp://example.com/lnurl",
            "LNURL request URL scheme must be HTTP or HTTPS.",
        ),
    ],
)
async def test_lnurl_request_validation_errors_identify_cause(url: str, message: str):
    with pytest.raises(LnurlResponseException) as exc_info:
        await lnurl_service._validate_lnurl_request_url(httpx.URL(url), tor_socks=None)

    assert str(exc_info.value) == message


@pytest.mark.anyio
async def test_lnurl_redirects_are_denied_by_default(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_lnurl_redirect_url_rules = []
    mocker.patch(
        "lnbits.core.services.lnurl._resolve_lnurl_host",
        mocker.AsyncMock(return_value=[ipaddress.ip_address("93.184.216.34")]),
    )
    send = mocker.patch(
        "lnbits.core.services.lnurl._send_lnurl_request",
        mocker.AsyncMock(
            return_value=(
                302,
                {"location": "https://pay.example/lnurl"},
                b"",
            )
        ),
    )

    with pytest.raises(LnurlResponseException, match="redirect was not allowed"):
        await lnurl_service._request_lnurl_json(
            "https://start.example/lnurl",
            user_agent=None,
            timeout=None,
            tor_socks=None,
            params=None,
        )
    send.assert_awaited_once()


@pytest.mark.anyio
async def test_lnurl_redirect_target_is_revalidated(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_lnurl_redirect_url_rules = [r"http://169\.254\.169\.254"]
    mocker.patch(
        "lnbits.core.services.lnurl._resolve_lnurl_host",
        mocker.AsyncMock(return_value=[ipaddress.ip_address("93.184.216.34")]),
    )
    send = mocker.patch(
        "lnbits.core.services.lnurl._send_lnurl_request",
        mocker.AsyncMock(
            return_value=(
                302,
                {"location": "http://169.254.169.254/latest/meta-data/"},
                b"",
            )
        ),
    )

    with pytest.raises(LnurlResponseException, match="not allowed over HTTP"):
        await lnurl_service._request_lnurl_json(
            "https://start.example/lnurl",
            user_agent=None,
            timeout=None,
            tor_socks=None,
            params=None,
        )
    send.assert_awaited_once()


@pytest.mark.anyio
async def test_lnurl_allowed_redirect_is_followed(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_lnurl_redirect_url_rules = [r"https://pay\.example"]
    resolve = mocker.patch(
        "lnbits.core.services.lnurl._resolve_lnurl_host",
        mocker.AsyncMock(return_value=[ipaddress.ip_address("93.184.216.34")]),
    )
    send = mocker.patch(
        "lnbits.core.services.lnurl._send_lnurl_request",
        mocker.AsyncMock(
            side_effect=[
                (302, {"location": "https://pay.example/lnurl"}, b""),
                (200, {}, b'{"status":"OK"}'),
            ]
        ),
    )

    data = await lnurl_service._request_lnurl_json(
        "https://start.example/lnurl",
        user_agent=None,
        timeout=None,
        tor_socks=None,
        params=None,
    )

    assert data == {"status": "OK"}
    assert resolve.await_count == 2
    assert send.await_count == 2


@pytest.mark.anyio
async def test_lnurl_invalid_response_does_not_leak_body(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.core.services.lnurl._resolve_lnurl_host",
        mocker.AsyncMock(return_value=[ipaddress.ip_address("93.184.216.34")]),
    )
    mocker.patch(
        "lnbits.core.services.lnurl._send_lnurl_request",
        mocker.AsyncMock(return_value=(200, {}, b'{"secret":"internal-proof"}')),
    )

    with pytest.raises(LnurlResponseException) as exc_info:
        await _get("https://safe.example/lnurl")
    assert str(exc_info.value) == "Invalid LNURL response."
    assert "internal-proof" not in str(exc_info.value)


@pytest.mark.anyio
async def test_lnurl_requests_are_pinned_to_validated_ip(mocker: MockerFixture):
    client = _FakeAsyncClient(
        _FakeStreamResponse(status_code=200, chunks=[b'{"status":"OK"}'])
    )
    mocker.patch("lnbits.core.services.lnurl.httpx.AsyncClient", client.factory)

    status_code, _, body = await lnurl_service._send_lnurl_request(
        httpx.URL("https://pay.example:8443/lnurl"),
        addresses=[ipaddress.ip_address("93.184.216.34")],
        proxy=None,
        user_agent="test-agent",
        timeout=5,
    )

    assert status_code == 200
    assert body == b'{"status":"OK"}'
    assert client.stream_kwargs["url"] == httpx.URL("https://93.184.216.34:8443/lnurl")
    assert client.stream_kwargs["headers"]["Host"] == "pay.example:8443"
    assert client.stream_kwargs["extensions"] == {"sni_hostname": "pay.example"}


@pytest.mark.anyio
async def test_perform_withdraw_success_and_validation(mocker: MockerFixture):
    withdraw_response = LnurlWithdrawResponse(
        callback=parse_obj_as(CallbackUrl, "https://example.com/callback"),
        k1="k1",
        minWithdrawable=MilliSatoshi(1),
        maxWithdrawable=MilliSatoshi(1000),
        defaultDescription="test",
    )
    execute_withdraw_mock = mocker.patch(
        "lnbits.core.services.lnurl.execute_withdraw",
        mocker.AsyncMock(return_value=LnurlSuccessResponse()),
    )
    mocker.patch(
        "lnbits.core.services.lnurl.handle",
        mocker.AsyncMock(return_value=withdraw_response),
    )

    await perform_withdraw("lnurl", "bolt11")

    execute_withdraw_mock.assert_awaited_once()

    mocker.patch(
        "lnbits.core.services.lnurl.check_callback_url",
        side_effect=ValueError("blocked"),
    )
    with pytest.raises(LnurlResponseException, match="Invalid callback URL"):
        await perform_withdraw("lnurl", "bolt11")


@pytest.mark.anyio
async def test_perform_withdraw_rejects_error_response(mocker: MockerFixture):
    mocker.patch(
        "lnbits.core.services.lnurl.handle",
        mocker.AsyncMock(return_value=LnurlErrorResponse(reason="boom")),
    )

    with pytest.raises(LnurlResponseException, match="boom"):
        await perform_withdraw("lnurl", "bolt11")


@pytest.mark.anyio
async def test_get_pr_from_lnurl_success_and_error(mocker: MockerFixture):
    pay_response = make_lnurl_pay_response(min_sendable_msat=1, text="Test")
    mocker.patch(
        "lnbits.core.services.lnurl.handle",
        mocker.AsyncMock(return_value=pay_response),
    )
    mocker.patch(
        "lnbits.core.services.lnurl._execute_pay_request",
        mocker.AsyncMock(
            return_value=LnurlPayActionResponse(
                pr=cast(LightningInvoice, LightningInvoice(TEST_BOLT11))
            )
        ),
    )

    assert await get_pr_from_lnurl("lnurl", 1000, comment="hello") == TEST_BOLT11

    mocker.patch(
        "lnbits.core.services.lnurl.handle",
        mocker.AsyncMock(return_value=LnurlErrorResponse(reason="nope")),
    )
    with pytest.raises(LnurlResponseException, match="nope"):
        await get_pr_from_lnurl("lnurl", 1000)


@pytest.mark.anyio
async def test_fetch_lnurl_pay_request_converts_currency_and_stores_paylink(
    mocker: MockerFixture,
):
    pay_response = make_lnurl_pay_response(min_sendable_msat=1, text="Test")
    action_response = LnurlPayActionResponse(
        pr=cast(LightningInvoice, LightningInvoice(TEST_BOLT11)), disposable=False
    )
    mocker.patch(
        "lnbits.core.services.lnurl.fiat_amount_as_satoshis",
        mocker.AsyncMock(return_value=100),
    )
    execute_mock = mocker.patch(
        "lnbits.core.services.lnurl._execute_pay_request",
        mocker.AsyncMock(return_value=action_response),
    )
    store_paylink_mock = mocker.patch(
        "lnbits.core.services.lnurl._store_paylink",
        mocker.AsyncMock(),
    )
    wallet = _make_wallet()

    data = CreateLnurlPayment(res=pay_response, amount=2500, unit="USD", comment="hi")
    response, action = await fetch_lnurl_pay_request(data, wallet=wallet)

    assert response == pay_response
    assert action == action_response
    execute_mock.assert_awaited_once()
    assert execute_mock.await_args is not None
    assert execute_mock.await_args.kwargs["msat"] == 100_000
    store_paylink_mock.assert_awaited_once_with(
        pay_response, action_response, wallet, None
    )

    with pytest.raises(LnurlResponseException, match="No LNURL pay request provided."):
        await fetch_lnurl_pay_request(CreateLnurlPayment(amount=1))


@pytest.mark.anyio
async def test_store_paylink_appends_and_updates_existing():
    wallet = await _create_wallet()
    pay_response = make_lnurl_pay_response(min_sendable_msat=1, text="Test")
    action_response = LnurlPayActionResponse(
        pr=cast(LightningInvoice, LightningInvoice(TEST_BOLT11)), disposable=False
    )

    await _store_paylink(
        pay_response, action_response, wallet, LnAddress("alice@example.com")
    )
    stored_wallet = await get_wallet(wallet.id)

    assert stored_wallet is not None
    assert len(stored_wallet.stored_paylinks.links) == 1
    assert stored_wallet.stored_paylinks.links[0].lnurl == "alice@example.com"

    first_used = stored_wallet.stored_paylinks.links[0].last_used
    await _store_paylink(
        pay_response, action_response, wallet, LnAddress("alice@example.com")
    )
    stored_wallet = await get_wallet(wallet.id)

    assert stored_wallet is not None
    assert len(stored_wallet.stored_paylinks.links) == 1
    assert stored_wallet.stored_paylinks.links[0].last_used >= first_used


def _make_wallet() -> Wallet:
    return Wallet(
        id="wallet-id",
        user="user-id",
        name="Wallet",
        adminkey="admin-key",
        inkey="invoice-key",
    )


async def _create_wallet() -> Wallet:
    user_id = uuid4().hex
    await create_account(Account(id=user_id, username=f"user_{user_id[:8]}"))
    return await create_wallet(user_id=user_id, wallet_name="Wallet")


class _FakeAsyncClient:
    def __init__(self, response):
        self.response = response
        self.kwargs = {}
        self.stream_kwargs = {}

    def factory(self, **kwargs):
        self.kwargs = kwargs
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def stream(self, method, url, **kwargs):
        self.stream_kwargs = {"method": method, "url": url, **kwargs}
        return self.response


class _FakeStreamResponse:
    def __init__(
        self,
        *,
        status_code: int,
        chunks: list[bytes],
    ):
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk
