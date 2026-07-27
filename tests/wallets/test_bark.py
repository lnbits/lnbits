import asyncio
import json

import httpx
import pytest
from bolt11 import decode as bolt11_decode

from lnbits.wallets.bark import BarkWallet
from lnbits.wallets.base import PaymentResponse

BOLT11 = (
    "lnbc1u1pjl0uhypp5yxvdqq923atm9ywkpgtu3yxv9w2n44ensrkwfyagvmzqhml2x9gq"
    "dpv2phhwetjv4jzqcneypqyc6t8dp6xu6twva2xjuzzda6qcqzzsxqrrsssp5h3qlnnlfq"
    "ekquacwwj9yu7fhujyzxhzqegpxenscw45pgv6xakfq9qyyssqqjruygw0jrcg3365jksxn"
    "6yhsxx7c5pdjrjdlyvuhs7xh8r409h4e3kucc54kgh34pscaq3mg7hn55l8a0qszgzex80"
    "amwrp4gkdgqcpkse88y"
)


class FakeWebSocket:
    def __init__(self, messages: list[dict]):
        self.messages = messages

    async def recv(self):
        return json.dumps(self.messages.pop(0))


class FakeConnection:
    def __init__(self, websocket: FakeWebSocket):
        self.websocket = websocket

    async def __aenter__(self):
        return self.websocket

    async def __aexit__(self, *_):
        return None


@pytest.fixture
def bark_wallet(settings):
    settings.bark_api_endpoint = "http://localhost:3000"
    settings.bark_api_token = "test-token"
    return BarkWallet()


def payment_response(status_code: int, **kwargs) -> httpx.Response:
    request = httpx.Request("POST", "http://localhost:3000/api/v1/lightning/pay")
    return httpx.Response(status_code, request=request, **kwargs)


@pytest.mark.anyio
async def test_paid_invoices_stream_yields_successful_receive(
    bark_wallet: BarkWallet, mocker
):
    checking_id = bolt11_decode(BOLT11).payment_hash
    notification = {
        "type": "movement-updated",
        "movement": {
            "status": "successful",
            "received_on": [
                {
                    "destination": {"type": "invoice", "value": BOLT11},
                    "amount_sat": 100,
                }
            ],
        },
    }
    websocket = FakeWebSocket([notification])
    connect = mocker.patch(
        "lnbits.wallets.bark.connect", return_value=FakeConnection(websocket)
    )
    request = mocker.patch.object(
        bark_wallet,
        "_request_json",
        side_effect=[
            "websocket-ticket",
            {"state": "preimage-revealed", "payment_preimage": "preimage"},
        ],
    )

    stream = bark_wallet.paid_invoices_stream()
    try:
        assert await anext(stream) == checking_id
        status = await bark_wallet.get_invoice_status(checking_id)
        assert status.success
        assert status.preimage == "preimage"
    finally:
        await stream.aclose()
        await bark_wallet.cleanup()

    assert request.await_args_list == [
        mocker.call("GET", "/api/v1/notifications/ws/ticket", timeout=10),
        mocker.call("GET", f"/api/v1/lightning/receives/{checking_id}"),
    ]
    connect.assert_called_once_with(
        "ws://localhost:3000/api/v1/notifications/ws?ticket=websocket-ticket"
    )


def test_incoming_payment_hash_ignores_non_receive_movements(bark_wallet: BarkWallet):
    notification = {
        "type": "movement-updated",
        "movement": {
            "status": "successful",
            "received_on": [],
            "sent_to": [{"destination": {"type": "invoice", "value": BOLT11}}],
        },
    }

    assert bark_wallet._incoming_payment_hash(notification) is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("data", "expected_paid"),
    [
        (
            {
                "state": "settled",
                "settled_at": "2026-07-16T12:00:00Z",
                "payment_preimage": "preimage",
            },
            True,
        ),
        (
            {
                "finished_at": "2026-07-16T12:00:00Z",
                "preimage_revealed_at": "2026-07-16T12:00:00Z",
                "payment_preimage": "preimage",
            },
            True,
        ),
        ({"state": "awaiting-payment"}, None),
        ({"finished_at": "2026-07-16T12:00:00Z"}, False),
    ],
    ids=["settled", "legacy-settled", "pending", "failed"],
)
async def test_get_invoice_status_maps_receive_state(
    bark_wallet: BarkWallet, mocker, data: dict, expected_paid: bool | None
):
    checking_id = bolt11_decode(BOLT11).payment_hash
    request = mocker.patch.object(bark_wallet, "_request_json", return_value=data)

    status = await bark_wallet.get_invoice_status(checking_id)

    assert status.paid is expected_paid
    assert status.preimage == ("preimage" if expected_paid else None)
    request.assert_awaited_once_with("GET", f"/api/v1/lightning/receives/{checking_id}")


@pytest.mark.anyio
@pytest.mark.parametrize("ok", [True, None], ids=["settled", "pending"])
async def test_send_payment_checks_status_after_payment_is_initiated(
    bark_wallet: BarkWallet, mocker, settings, ok: bool | None
):
    settings.lnbits_funding_source_pay_invoice_wait_seconds = 0
    checking_id = bolt11_decode(BOLT11).payment_hash
    expected = PaymentResponse(ok=ok, checking_id=checking_id)
    mocker.patch.object(
        bark_wallet.client,
        "post",
        return_value=payment_response(
            200, json={"message": "Payment initiated successfully"}
        ),
    )
    get_status = mocker.patch.object(
        bark_wallet, "_payment_response_from_status", return_value=expected
    )

    response = await bark_wallet._send_payment(BOLT11, checking_id)

    assert response == expected
    assert bark_wallet.pending_payments[checking_id] == BOLT11
    get_status.assert_awaited_once_with(checking_id)


@pytest.mark.anyio
async def test_send_payment_waits_for_successful_movement_notification(
    bark_wallet: BarkWallet, mocker, settings
):
    settings.lnbits_funding_source_pay_invoice_wait_seconds = 5
    checking_id = bolt11_decode(BOLT11).payment_hash
    mocker.patch.object(
        bark_wallet.client,
        "post",
        return_value=payment_response(
            200, json={"message": "Payment initiated successfully"}
        ),
    )
    mocker.patch.object(
        bark_wallet,
        "_payment_response_from_status",
        return_value=PaymentResponse(ok=None, checking_id=checking_id),
    )

    payment_task = asyncio.create_task(bark_wallet._send_payment(BOLT11, checking_id))
    await asyncio.sleep(0)
    bark_wallet._notify_outgoing_payment(
        {
            "type": "movement-updated",
            "movement": {
                "status": "successful",
                "offchain_fee_sat": 2,
                "metadata": {"payment_preimage": "preimage"},
                "sent_to": [
                    {
                        "destination": {"type": "invoice", "value": BOLT11},
                        "amount_sat": 100,
                    }
                ],
            },
        }
    )

    response = await payment_task

    assert response.ok is True
    assert response.checking_id == checking_id
    assert response.fee_msat == 2000
    assert response.preimage == "preimage"
    assert checking_id not in bark_wallet.outgoing_payment_waiters


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [
        httpx.TimeoutException("timeout"),
        httpx.ReadError("connection lost"),
    ],
    ids=["timeout", "read-error"],
)
async def test_send_payment_keeps_transport_errors_pending(
    bark_wallet: BarkWallet, mocker, error: httpx.RequestError
):
    checking_id = bolt11_decode(BOLT11).payment_hash
    mocker.patch.object(bark_wallet.client, "post", side_effect=error)

    response = await bark_wallet._send_payment(BOLT11, checking_id)

    assert response.pending
    assert response.checking_id == checking_id
    assert bark_wallet.pending_payments[checking_id] == BOLT11


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "expected_ok"),
    [(400, False), (500, None)],
    ids=["client-error", "server-error"],
)
async def test_send_payment_maps_http_errors(
    bark_wallet: BarkWallet,
    mocker,
    status_code: int,
    expected_ok: bool | None,
):
    checking_id = bolt11_decode(BOLT11).payment_hash
    mocker.patch.object(
        bark_wallet.client,
        "post",
        return_value=payment_response(status_code, json={"message": "payment error"}),
    )

    response = await bark_wallet._send_payment(BOLT11, checking_id)

    assert response.ok is expected_ok
    assert response.checking_id == checking_id
    assert (checking_id in bark_wallet.pending_payments) is (expected_ok is None)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        payment_response(200, content=b"not json"),
        payment_response(200, json={"unexpected": "response"}),
    ],
    ids=["invalid-json", "missing-message"],
)
async def test_send_payment_keeps_invalid_responses_pending(
    bark_wallet: BarkWallet, mocker, response: httpx.Response
):
    checking_id = bolt11_decode(BOLT11).payment_hash
    mocker.patch.object(bark_wallet.client, "post", return_value=response)

    payment = await bark_wallet._send_payment(BOLT11, checking_id)

    assert payment.pending
    assert payment.checking_id == checking_id
    assert bark_wallet.pending_payments[checking_id] == BOLT11
