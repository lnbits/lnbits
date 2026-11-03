import json
from collections.abc import AsyncIterator

import httpx
import pytest

from lnbits.wallets.lndrest import LndRestWallet


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("state", "paid"),
    [("IN_FLIGHT", None), ("SUCCEEDED", True), ("FAILED", False)],
)
async def test_lndrest_returns_current_payment_status_without_waiting(
    state: str, paid: bool | None
):
    class StatusStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield (
                json.dumps(
                    {
                        "result": {
                            "status": state,
                            "fee_msat": "123",
                            "payment_preimage": "ab" * 32,
                        }
                    }
                ).encode()
                + b"\n"
            )
            raise httpx.ReadTimeout("No further payment status updates")

        async def aclose(self) -> None:
            self.closed = True

    stream = StatusStream()
    wallet = object.__new__(LndRestWallet)
    async with httpx.AsyncClient(
        base_url="https://lnd.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=stream)
        ),
    ) as wallet.client:
        status = await wallet.get_payment_status("01" * 32)

    assert status.paid is paid
    assert stream.closed
    if paid:
        assert status.fee_msat == 123
        assert status.preimage == "ab" * 32
