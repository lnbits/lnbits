import asyncio
import json
import socket
import time

import httpx
import pytest
from nostr_sdk import (
    Client,
    Event,
    EventBuilder,
    Keys,
    Kind,
    PublicKey,
    RelayUrl,
    Tag,
    Timestamp,
    nip44_decrypt,
)
from pytest_mock.plugin import MockerFixture

from lnbits.core.services.nostr import (
    fetch_nip5_details,
    send_nostr_dm,
    send_nostr_dm_nip17,
)
from lnbits.utils.nostr import normalize_identifier, validate_identifier


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
    mocker.patch("lnbits.core.services.nostr.SafeHttpClient", return_value=client)

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
    mocker.patch("lnbits.core.services.nostr.SafeHttpClient", return_value=client)
    with pytest.raises(ValueError, match="NIP5 not name found"):
        await fetch_nip5_details("alice@example.com")


@pytest.mark.anyio
async def test_nip05_pins_public_host_without_applying_webhook_rules(
    safe_http_mock, settings
):
    resolver, handler = safe_http_mock
    settings.lnbits_callback_url_rules = [r"https://webhooks\.example"]
    pubkey = Keys.generate().public_key().to_hex()
    handler.side_effect = lambda request: httpx.Response(
        200, json={"names": {"alice": pubkey}}
    )

    assert await fetch_nip5_details("alice@example.com") == (pubkey, [])

    resolver.assert_awaited_once()
    request = handler.call_args.args[0]
    assert str(request.url) == "https://93.184.216.34/.well-known/nostr.json?name=alice"
    assert request.headers["host"] == "example.com"
    assert request.extensions["sni_hostname"] == "example.com"
    assert request.extensions["timeout"]["read"] == 5


@pytest.mark.anyio
@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.2", "169.254.169.254", "64:ff9b::7f00:1", "8.8.8.8"],
)
async def test_nip05_rejects_private_and_self_addresses(
    safe_http_mock, settings, address
):
    resolver, handler = safe_http_mock
    settings.lnbits_callback_allow_private_ips = True
    settings.lnbits_outbound_host_ips = ["8.8.8.8"]
    resolver.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
    ]
    with pytest.raises(ValueError):
        await fetch_nip5_details("alice@example.com")
    handler.assert_not_called()


@pytest.mark.anyio
async def test_nip05_rejects_instance_hostname_before_dns(safe_http_mock, settings):
    resolver, handler = safe_http_mock
    settings.lnbits_baseurl = "https://example.com"
    with pytest.raises(ValueError, match="this server"):
        await fetch_nip5_details("alice@example.com")
    resolver.assert_not_awaited()
    handler.assert_not_called()


@pytest.mark.anyio
async def test_nip05_bounds_response_and_does_not_follow_redirects(safe_http_mock):
    _, handler = safe_http_mock
    handler.side_effect = lambda request: httpx.Response(
        302, headers={"location": "http://127.0.0.1/"}
    )
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_nip5_details("alice@example.com")
    handler.assert_called_once()
    handler.side_effect = lambda request: httpx.Response(200, content=b"x" * 1048577)
    with pytest.raises(ValueError, match="too large"):
        await fetch_nip5_details("alice@example.com")


@pytest.mark.parametrize("local_part", ["alice", "john-doe", "a.b_c-d", "Bob-42"])
def test_validate_identifier_accepts_nip05_characters(local_part: str):
    validate_identifier(local_part)


@pytest.mark.parametrize("local_part", ["", "bad!", "white space", "a+b", "ü"])
def test_validate_identifier_rejects_other_characters(local_part: str):
    with pytest.raises(ValueError):
        validate_identifier(local_part)


def test_normalize_identifier_keeps_hyphens():
    assert normalize_identifier("John-Doe@example.com") == "john-doe"


@pytest.fixture
def nip17_sender(mocker: MockerFixture):
    sender = Keys.generate()
    receiver = Keys.generate()
    client = mocker.Mock(spec=Client)
    client.fetch_events.return_value = mocker.Mock()
    mocker.patch("lnbits.core.services.nostr.Client", return_value=client)
    inbox = (
        EventBuilder(Kind(10050), "")
        .tags([Tag.parse(["relay", "wss://inbox.example.com"])])
        .sign_with_keys(receiver)
    )
    client.fetch_events.return_value.to_vec.return_value = [inbox]
    client.send_event_to.return_value.success = [
        RelayUrl.parse("wss://inbox.example.com")
    ]
    return sender, receiver, client


@pytest.mark.anyio
async def test_send_nip17_wraps_and_signs_message_for_recipient(nip17_sender):
    sender, receiver, client = nip17_sender
    message = "Payment received: 21 sats ⚡\nLNbits notification"
    before = int(time.time())

    await send_nostr_dm_nip17(
        sender.secret_key().to_hex(),
        receiver.public_key().to_hex(),
        message,
        ["wss://discovery.example.com"],
    )

    relay_urls, event = client.send_event_to.call_args.args
    assert relay_urls == [RelayUrl.parse("wss://inbox.example.com")]
    query = json.loads(client.fetch_events.call_args.args[0].as_json())
    assert query == {
        "authors": [receiver.public_key().to_hex()],
        "kinds": [10050],
        "limit": 1,
    }

    wrapper = json.loads(event.as_json())
    assert event.verify()
    assert wrapper["kind"] == 1059
    assert wrapper["pubkey"] != sender.public_key().to_hex()
    assert wrapper["tags"] == [["p", receiver.public_key().to_hex()]]
    assert message not in wrapper["content"]
    seal_json = nip44_decrypt(
        receiver.secret_key(), PublicKey.parse(wrapper["pubkey"]), wrapper["content"]
    )
    assert Event.from_json(seal_json).verify()
    seal = json.loads(seal_json)
    assert seal["kind"] == 13
    assert seal["tags"] == []
    assert seal["pubkey"] == sender.public_key().to_hex()
    rumor = json.loads(
        nip44_decrypt(receiver.secret_key(), sender.public_key(), seal["content"])
    )
    assert rumor["kind"] == 14
    assert rumor["pubkey"] == sender.public_key().to_hex()
    assert rumor["tags"] == [["p", receiver.public_key().to_hex()]]
    assert rumor["content"] == message
    assert "sig" not in rumor
    assert len(rumor["id"]) == 64
    after = int(time.time())
    assert before <= rumor["created_at"] <= after
    for envelope in (seal, wrapper):
        assert before - 2 * 24 * 60 * 60 <= envelope["created_at"] <= after
    client.shutdown.assert_awaited_once()


@pytest.mark.anyio
async def test_send_nip17_uses_newest_inbox_list_and_deduplicates(nip17_sender):
    sender, receiver, client = nip17_sender
    older = (
        EventBuilder(Kind(10050), "")
        .tags([Tag.parse(["relay", "wss://old.example.com"])])
        .custom_created_at(Timestamp.from_secs(100))
        .sign_with_keys(receiver)
    )
    newer = (
        EventBuilder(Kind(10050), "")
        .tags(
            [
                Tag.parse(["relay", "wss://inbox.example.com"]),
                Tag.parse(["relay", "wss://inbox.example.com/"]),
                Tag.parse(["r", "wss://not-an-inbox.example.com"]),
            ]
        )
        .custom_created_at(Timestamp.from_secs(200))
        .sign_with_keys(receiver)
    )
    client.fetch_events.return_value.to_vec.return_value = [older, newer]

    await send_nostr_dm_nip17(
        sender.secret_key().to_hex(),
        receiver.public_key().to_hex(),
        "hi",
        ["wss://hint"],
    )

    assert client.send_event_to.call_args.args[0] == [
        RelayUrl.parse("wss://inbox.example.com")
    ]


@pytest.mark.anyio
async def test_send_nip17_uses_existing_relays_when_inbox_list_is_missing(nip17_sender):
    sender, receiver, client = nip17_sender
    client.fetch_events.return_value.to_vec.return_value = []
    relays = ["wss://relay-one.example.com", "wss://relay-two.example.com"]
    relay_urls = [RelayUrl.parse(relay) for relay in relays]
    client.send_event_to.return_value.success = relay_urls[:1]

    await send_nostr_dm_nip17(
        sender.secret_key().to_hex(), receiver.public_key().to_hex(), "hi", relays
    )

    client.send_event_to.assert_awaited_once()
    published_relays, event = client.send_event_to.call_args.args
    assert published_relays == relay_urls
    assert event.kind() == Kind(1059)
    assert event.verify()
    assert json.loads(event.as_json())["tags"] == [
        ["p", receiver.public_key().to_hex()]
    ]
    client.shutdown.assert_awaited_once()


@pytest.mark.anyio
async def test_send_nip17_rejects_empty_inbox_list(nip17_sender):
    sender, receiver, client = nip17_sender
    client.fetch_events.return_value.to_vec.return_value = [
        EventBuilder(Kind(10050), "").sign_with_keys(receiver)
    ]

    with pytest.raises(ValueError, match="inbox relay list"):
        await send_nostr_dm_nip17(
            sender.secret_key().to_hex(),
            receiver.public_key().to_hex(),
            "hi",
            ["wss://hint"],
        )

    client.send_event_to.assert_not_awaited()
    client.shutdown.assert_awaited_once()


@pytest.mark.anyio
async def test_send_nip17_requires_discovery_relays(nip17_sender):
    sender, receiver, client = nip17_sender
    with pytest.raises(ValueError, match="No NIP-05 relays"):
        await send_nostr_dm_nip17(
            sender.secret_key().to_hex(), receiver.public_key().to_hex(), "hi", []
        )
    client.connect.assert_not_awaited()


@pytest.mark.anyio
async def test_send_nip17_requires_relay_acceptance(nip17_sender):
    sender, receiver, client = nip17_sender
    client.send_event_to.return_value.success = []

    with pytest.raises(ValueError, match="No NIP-17 inbox relay accepted"):
        await send_nostr_dm_nip17(
            sender.secret_key().to_hex(),
            receiver.public_key().to_hex(),
            "hi",
            ["wss://hint"],
        )
    client.shutdown.assert_awaited_once()


@pytest.mark.anyio
async def test_send_nip17_times_out_and_closes_client(
    nip17_sender, mocker: MockerFixture
):
    sender, receiver, client = nip17_sender
    wait_for = asyncio.wait_for

    async def short_timeout(awaitable, timeout):
        assert timeout == 30
        return await wait_for(awaitable, timeout=0.01)

    async def never_connect():
        await asyncio.Event().wait()

    mocker.patch(
        "lnbits.core.services.nostr.asyncio.wait_for", side_effect=short_timeout
    )
    client.connect.side_effect = never_connect

    with pytest.raises(ValueError, match="NIP-17 notification timed out"):
        await send_nostr_dm_nip17(
            sender.secret_key().to_hex(),
            receiver.public_key().to_hex(),
            "hi",
            ["wss://hint"],
        )
    client.send_event_to.assert_not_awaited()
    client.shutdown.assert_awaited_once()
