import json

import pytest
from nostr_sdk import (
    EventBuilder,
    Keys,
    Kind,
    Nip44Version,
    NostrSigner,
    Tag,
    UnwrappedGift,
    gift_wrap_from_seal,
    nip44_encrypt,
)
from pytest_mock.plugin import MockerFixture

from lnbits.core.services.nostr import (
    NostrGroupTicket,
    _fetch_events_from_relay,
    _select_latest_nostr_group_ticket,
    _send_event_to_relays,
    fetch_latest_nostr_group_ticket,
    fetch_nip5_details,
    resolve_nostr_recipient,
    send_nostr_dm,
    send_nostr_nip17_dm,
    send_nostr_nip17b_dm,
)


class FakeWebSocket:
    def __init__(self, messages: list[str] | None = None):
        self.sent: list[str] = []
        self.closed = False
        self.messages = list(messages or [])
        self.timeout: float | None = None

    def send(self, message: str):
        self.sent.append(message)

    def recv(self):
        return self.messages.pop(0)

    def settimeout(self, timeout: float):
        self.timeout = timeout

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
    validate_pub_key = mocker.patch(
        "lnbits.core.services.nostr.validate_pub_key",
        return_value="f" * 64,
    )
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


@pytest.mark.anyio
async def test_resolve_nostr_recipient_uses_nip5_or_fallback_relays(
    mocker: MockerFixture,
):
    keys = Keys.generate()
    npub = keys.public_key().to_bech32()
    nip5_mock = mocker.patch(
        "lnbits.core.services.nostr.fetch_nip5_details",
        mocker.AsyncMock(return_value=(keys.public_key().to_hex(), ["wss://nip5"])),
    )

    assert await resolve_nostr_recipient("alice@example.com") == (
        keys.public_key().to_hex(),
        ["wss://nip5"],
    )
    assert await resolve_nostr_recipient(npub, ["wss://fallback"]) == (
        keys.public_key().to_hex(),
        ["wss://fallback"],
    )
    nip5_mock.assert_awaited_once_with("alice@example.com")


@pytest.mark.anyio
async def test_send_nostr_nip17_dm_builds_gift_wrap(
    mocker: MockerFixture,
):
    sender = Keys.generate()
    receiver = Keys.generate()
    send_mock = mocker.patch(
        "lnbits.core.services.nostr._send_event_to_relays",
        mocker.AsyncMock(),
    )

    result = await send_nostr_nip17_dm(
        sender.secret_key().to_hex(),
        receiver.public_key().to_hex(),
        "hello",
        ["wss://relay"],
    )

    assert result["kind"] == 1059
    assert result["tags"] == [["p", receiver.public_key().to_hex()]]
    send_mock.assert_awaited_once()
    gift = send_mock.await_args.args[0]
    unwrapped = await UnwrappedGift.from_gift_wrap(
        NostrSigner.keys(receiver),
        gift,
    )
    assert unwrapped.rumor().content() == "hello"
    assert unwrapped.sender().to_hex() == sender.public_key().to_hex()
    assert send_mock.await_args.args[1] == ["wss://relay"]


@pytest.mark.anyio
async def test_send_nostr_nip17b_dm_uses_epoch_ticket(
    mocker: MockerFixture,
):
    member = Keys.generate()
    group = Keys.generate()
    epoch = Keys.generate()
    ticket = NostrGroupTicket(
        group_pubkey=group.public_key().to_hex(),
        epoch=4,
        epoch_private_key=epoch.secret_key().to_hex(),
        invited_at=123,
        invitation_proof="f" * 128,
        event_id="ticket-id",
    )
    fetch_mock = mocker.patch(
        "lnbits.core.services.nostr.fetch_latest_nostr_group_ticket",
        mocker.AsyncMock(return_value=ticket),
    )
    send_mock = mocker.patch(
        "lnbits.core.services.nostr._send_event_to_relays",
        mocker.AsyncMock(),
    )

    await send_nostr_nip17b_dm(
        member.secret_key().to_hex(),
        group.public_key().to_hex(),
        "hello group",
        ["wss://group"],
    )

    fetch_mock.assert_awaited_once_with(
        member.secret_key().to_hex(),
        group.public_key().to_hex(),
        ["wss://group"],
    )
    gift = send_mock.await_args.args[0]
    unwrapped = await UnwrappedGift.from_gift_wrap(
        NostrSigner.keys(epoch),
        gift,
    )
    rumor = json.loads(unwrapped.rumor().as_json())
    assert rumor["content"] == "hello group"
    assert rumor["tags"] == [
        ["p", epoch.public_key().to_hex()],
        ["h", group.public_key().to_hex()],
        ["epoch", "4"],
        ["invited_at", "123"],
        ["invitation_proof", "f" * 128],
    ]
    assert unwrapped.sender().to_hex() == member.public_key().to_hex()
    assert send_mock.await_args.args[1] == ["wss://group"]


@pytest.mark.anyio
@pytest.mark.parametrize("sealed", [False, True])
async def test_fetch_latest_nostr_group_ticket_uses_direct_relay_events(
    mocker: MockerFixture, sealed: bool
):
    member = Keys.generate()
    group = Keys.generate()
    epoch = Keys.generate()
    ticket = (
        EventBuilder(Kind(1014), epoch.secret_key().to_hex())
        .tags(
            [
                Tag.parse(["p", member.public_key().to_hex()]),
                Tag.parse(["epoch", "3"]),
            ]
        )
        .sign_with_keys(group)
    )
    if sealed:
        encrypted_ticket = nip44_encrypt(
            group.secret_key(),
            member.public_key(),
            ticket.as_json(),
            Nip44Version.V2,
        )
        seal = EventBuilder(Kind(13), encrypted_ticket).sign_with_keys(group)
        gift = gift_wrap_from_seal(member.public_key(), seal)
    else:
        wrapper = Keys.generate()
        encrypted_ticket = nip44_encrypt(
            wrapper.secret_key(),
            member.public_key(),
            ticket.as_json(),
            Nip44Version.V2,
        )
        gift = (
            EventBuilder(Kind(1059), encrypted_ticket)
            .tags([Tag.parse(["p", member.public_key().to_hex()])])
            .sign_with_keys(wrapper)
        )
    fetch_mock = mocker.patch(
        "lnbits.core.services.nostr._fetch_events_from_relays",
        mocker.AsyncMock(return_value=[gift]),
    )

    parsed = await fetch_latest_nostr_group_ticket(
        member.secret_key().to_hex(),
        group.public_key().to_hex(),
        ["wss://relay"],
    )

    fetch_mock.assert_awaited_once_with(
        ["wss://relay"],
        {
            "kinds": [1059],
            "#p": [member.public_key().to_hex()],
            "limit": 200,
        },
    )
    assert parsed.epoch_private_key == epoch.secret_key().to_hex()
    assert parsed.group_pubkey == group.public_key().to_hex()
    assert parsed.epoch == 3
    assert parsed.epoch_pubkey == epoch.public_key().to_hex()
    assert parsed.invited_at == ticket.created_at().as_secs()
    assert parsed.invitation_proof == ticket.signature()
    assert parsed.event_id == ticket.id().to_hex()


def test_fetch_events_from_relay_uses_nostr_subscription(mocker: MockerFixture):
    event = EventBuilder(Kind(1059), "gift").sign_with_keys(Keys.generate())
    websocket = FakeWebSocket(
        [
            json.dumps(["EVENT", "subscription", json.loads(event.as_json())]),
            json.dumps(["EOSE", "subscription"]),
        ]
    )
    mocker.patch(
        "lnbits.core.services.nostr.create_connection",
        return_value=websocket,
    )
    mocker.patch(
        "lnbits.core.services.nostr.secrets.token_hex",
        return_value="subscription",
    )

    events = _fetch_events_from_relay(
        "wss://relay",
        {"kinds": [1059]},
        5,
    )

    assert [item.id().to_hex() for item in events] == [event.id().to_hex()]
    assert json.loads(websocket.sent[0]) == [
        "REQ",
        "subscription",
        {"kinds": [1059]},
    ]
    assert json.loads(websocket.sent[1]) == ["CLOSE", "subscription"]
    assert websocket.closed is True


@pytest.mark.anyio
async def test_send_event_to_relays_uses_direct_websockets(
    mocker: MockerFixture,
):
    event = EventBuilder(Kind(1059), "gift").sign_with_keys(Keys.generate())
    first = FakeWebSocket()
    second = FakeWebSocket()
    mocker.patch(
        "lnbits.core.services.nostr.create_connection",
        side_effect=[first, second],
    )

    await _send_event_to_relays(
        event,
        ["wss://one", "wss://two"],
    )

    expected = ["EVENT", json.loads(event.as_json())]
    assert json.loads(first.sent[0]) == expected
    assert json.loads(second.sent[0]) == expected
    assert first.closed is True
    assert second.closed is True


def test_select_latest_nostr_group_ticket():
    tickets = [
        NostrGroupTicket("a", 1, "1" * 64, 20, "proof", "b"),
        NostrGroupTicket("a", 2, "2" * 64, 10, "proof", "c"),
        NostrGroupTicket("a", 2, "2" * 64, 30, "proof", "b"),
        NostrGroupTicket("a", 2, "2" * 64, 30, "proof", "a"),
    ]

    assert _select_latest_nostr_group_ticket(tickets).event_id == "a"

    tickets[-1] = NostrGroupTicket("a", 2, "3" * 64, 30, "proof", "a")
    with pytest.raises(ValueError, match="conflicting epoch private keys"):
        _select_latest_nostr_group_ticket(tickets)
