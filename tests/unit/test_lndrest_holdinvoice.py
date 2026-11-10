import base64
import hashlib
import json

import httpx
import pytest

from lnbits.wallets.lndrest import LndRestWallet


@pytest.mark.anyio
@pytest.mark.parametrize("expiry", [None, 0, 600])
@pytest.mark.parametrize(
    ("description_hash", "unhashed_description"),
    [
        (None, None),
        (None, b"hold metadata"),
        (b"e" * 32, None),
        (b"e" * 32, b"hold metadata"),
    ],
)
async def test_lndrest_hold_invoice_optional_fields(
    expiry, description_hash, unhashed_description
):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"payment_request": "hold-bolt11"})

    wallet = object.__new__(LndRestWallet)
    async with httpx.AsyncClient(
        base_url="https://lnd.test", transport=httpx.MockTransport(handler)
    ) as wallet.client:
        response = await wallet.create_hold_invoice(
            1000,
            "ab" * 32,
            memo="hold",
            expiry=expiry,
            description_hash=description_hash,
            unhashed_description=unhashed_description,
        )

    assert response.ok
    assert requests[0].url.path == "/v2/invoices/hodl"
    data = json.loads(requests[0].content)
    if expiry:
        assert data["expiry"] == expiry
    else:
        # Leave LND's default in place for direct adapter calls.
        assert "expiry" not in data
    expected_hash = description_hash or (
        hashlib.sha256(unhashed_description).digest() if unhashed_description else None
    )
    if expected_hash:
        assert base64.b64decode(data["description_hash"]) == expected_hash
        assert "memo" not in data
    else:
        assert data["memo"] == "hold"
        assert "description_hash" not in data
