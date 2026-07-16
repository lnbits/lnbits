import json

import pytest
from bolt11 import decode as bolt11_decode

from lnbits.wallets.bark import BarkWallet

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
        bark_wallet, "_request_json", return_value="websocket-ticket"
    )

    stream = bark_wallet.paid_invoices_stream()
    try:
        assert await anext(stream) == checking_id
    finally:
        await stream.aclose()
        await bark_wallet.cleanup()

    request.assert_awaited_once_with(
        "GET", "/api/v1/notifications/ws/ticket", timeout=10
    )
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
