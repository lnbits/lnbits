import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.services.nostr import fetch_nip5_details, send_nostr_dm


class FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []
        self.closed = False

    def send(self, message: str):
        self.sent.append(message)

    def close(self):
        self.closed = True


class MockHTTPClient:
    def __init__(self, response):
        self.response = response
        self.calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        self.calls.append(url)
        return self.response


class MockHTTPResponse:
    def __init__(self, json_data: dict, error: Exception | None = None):
        self._json_data = json_data
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._json_data


@pytest.mark.anyio
async def test_send_nostr_dm_sends_to_available_relays_and_closes_connections(
    mocker: MockerFixture,
):
    event = mocker.Mock()
    event.to_message.return_value = "nostr-message"
    event.to_dict.return_value = {"id": "event-id"}
    dm = mocker.Mock()
    dm.to_event.return_value = event
    mocker.patch("lnbits.core.services.nostr.EncryptedDirectMessage", return_value=dm)

    ws_one = FakeWebSocket()
    ws_two = FakeWebSocket()
    mocker.patch(
        "lnbits.core.services.nostr.create_connection",
        side_effect=[ws_one, RuntimeError("boom"), ws_two],
    )
    mocker.patch("lnbits.core.services.nostr.asyncio.sleep", mocker.AsyncMock())

    result = await send_nostr_dm(
        "privkey",
        "pubkey",
        "hello",
        ["wss://relay-1", "wss://broken", "wss://relay-2"],
    )

    assert ws_one.sent == ["nostr-message"]
    assert ws_two.sent == ["nostr-message"]
    assert ws_one.closed is True
    assert ws_two.closed is True
    assert result == {"id": "event-id"}


@pytest.mark.anyio
async def test_fetch_nip5_details_returns_pubkey_and_relays(mocker: MockerFixture):
    response = MockHTTPResponse(
        {
            "names": {"alice": "f" * 64},
            "relays": {"f" * 64: ["wss://relay.example.com"]},
        }
    )
    client = MockHTTPClient(response)
    mocker.patch("lnbits.core.services.nostr.is_valid_url", return_value=True)
    validate_identifier = mocker.patch("lnbits.core.services.nostr.validate_identifier")
    validate_pub_key = mocker.patch("lnbits.core.services.nostr.validate_pub_key")
    mocker.patch("lnbits.core.services.nostr.httpx.AsyncClient", return_value=client)

    pubkey, relays = await fetch_nip5_details("alice@example.com")

    validate_identifier.assert_called_once_with("alice")
    validate_pub_key.assert_called_once_with("f" * 64)
    assert client.calls == ["https://example.com/.well-known/nostr.json?name=alice"]
    assert pubkey == "f" * 64
    assert relays == ["wss://relay.example.com"]


@pytest.mark.anyio
async def test_fetch_nip5_details_rejects_invalid_values(mocker: MockerFixture):
    with pytest.raises(ValueError, match="not enough values to unpack"):
        await fetch_nip5_details("invalid")

    mocker.patch("lnbits.core.services.nostr.is_valid_url", return_value=False)
    with pytest.raises(ValueError, match="Invalid NIP5 domain"):
        await fetch_nip5_details("alice@example.com")

    mocker.patch("lnbits.core.services.nostr.is_valid_url", return_value=True)
    client = MockHTTPClient(MockHTTPResponse({"names": {}}))
    mocker.patch("lnbits.core.services.nostr.httpx.AsyncClient", return_value=client)
    with pytest.raises(ValueError, match="NIP5 not name found"):
        await fetch_nip5_details("alice@example.com")
