import asyncio
import base64
import json

import pytest

from lnbits.wallets.eclair import EclairWallet


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("url", "ws_url"),
    [
        ("https://eclair.test", "wss://eclair.test/ws"),
        ("https://eclair.test:443", "wss://eclair.test:443/ws"),
        ("https://eclair.test:8443", "wss://eclair.test:8443/ws"),
        ("https://eclair.test:8443/", "wss://eclair.test:8443/ws"),
        ("https://[::1]:8443", "wss://[::1]:8443/ws"),
        ("eclair.test:8443", "wss://eclair.test:8443/ws"),
        ("http://eclair.test", "ws://eclair.test/ws"),
        ("http://127.0.0.1:8283", "ws://127.0.0.1:8283/ws"),
    ],
)
async def test_invoice_stream_preserves_configured_transport(
    settings, mocker, url, ws_url
):
    settings.eclair_url = url
    settings.eclair_pass = "test-password"
    settings.lnbits_running = True
    websocket = mocker.AsyncMock()
    websocket.recv.return_value = json.dumps(
        {"type": "payment-received", "paymentHash": "test-payment-hash"}
    )
    connect = mocker.patch("lnbits.wallets.eclair.connect")
    connect.return_value.__aenter__.return_value = websocket

    wallet = EclairWallet()
    stream = wallet.paid_invoices_stream()
    try:
        assert await asyncio.wait_for(anext(stream), timeout=1) == "test-payment-hash"
        auth = base64.b64encode(b":test-password").decode()
        connect.assert_called_once_with(
            ws_url, additional_headers=[("Authorization", f"Basic {auth}")]
        )
        assert wallet.client.base_url.scheme == (
            "https" if ws_url.startswith("wss:") else "http"
        )
    finally:
        await stream.aclose()
        await wallet.cleanup()
