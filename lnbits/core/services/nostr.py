import asyncio
import json
import secrets
import time
from dataclasses import dataclass

import httpx
from loguru import logger
from nostr_sdk import (
    Event,
    EventBuilder,
    Keys,
    Kind,
    Nip44Version,
    PublicKey,
    Tag,
    Timestamp,
    UnsignedEvent,
    gift_wrap_from_seal,
    nip44_decrypt,
    nip44_encrypt,
)
from pynostr.encrypted_dm import EncryptedDirectMessage
from websocket import WebSocket, WebSocketTimeoutException, create_connection

from lnbits.core.helpers import is_valid_url
from lnbits.utils.nostr import (
    is_ws_url,
    normalize_public_key,
    validate_identifier,
    validate_pub_key,
)

MAX_NOSTR_RELAYS = 20
MAX_NOSTR_RELAY_MESSAGE_SIZE = 64_000
NIP17_GIFT_WRAP_KIND = 1059
NIP17_SEAL_KIND = 13
NIP17_MESSAGE_KIND = 14
NIP17B_TICKET_KIND = 1014


@dataclass(frozen=True)
class NostrGroupTicket:
    group_pubkey: str
    epoch: int
    epoch_private_key: str
    invited_at: int
    invitation_proof: str
    event_id: str

    @property
    def epoch_pubkey(self) -> str:
        return Keys.parse(self.epoch_private_key).public_key().to_hex()


async def send_nostr_dm(
    from_private_key_hex: str,
    to_pubkey_hex: str,
    message: str,
    relays: list[str],
) -> dict:
    dm = EncryptedDirectMessage()
    dm.encrypt(
        private_key_hex=from_private_key_hex,
        recipient_pubkey=to_pubkey_hex,
        cleartext_content=message,
    )

    dm_event = dm.to_event()
    dm_event.sign(private_key_hex=from_private_key_hex)
    notification = dm_event.to_message()

    ws_connections: list[WebSocket] = []
    for relay in relays:
        try:
            ws = create_connection(relay, timeout=2)
            ws.send(notification)
            ws_connections.append(ws)
        except Exception as e:
            logger.warning(f"Error sending notification to relay {relay}: {e}")
    await asyncio.sleep(1)
    for ws in ws_connections:
        try:
            ws.close()
        except Exception as e:
            logger.debug(f"Failed to close websocket connection: {e}")

    return dm_event.to_dict()


async def send_nostr_nip17_dm(
    from_private_key_hex: str,
    to_pubkey_hex: str,
    message: str,
    relays: list[str],
) -> dict:
    keys = Keys.parse(from_private_key_hex)
    receiver = PublicKey.parse(to_pubkey_hex)
    rumor = EventBuilder.private_msg_rumor(receiver, message).build(keys.public_key())
    gift = _gift_wrap_with_keys(keys, receiver, rumor)
    await _send_event_to_relays(gift, relays)
    return json.loads(gift.as_json())


async def send_nostr_nip17b_dm(
    from_private_key_hex: str,
    group_pubkey_hex: str,
    message: str,
    relays: list[str],
) -> dict:
    ticket = await fetch_latest_nostr_group_ticket(
        from_private_key_hex,
        group_pubkey_hex,
        relays,
    )
    keys = Keys.parse(from_private_key_hex)
    epoch_pubkey = PublicKey.parse(ticket.epoch_pubkey)
    tags = [
        Tag.parse(["p", ticket.epoch_pubkey]),
        Tag.parse(["h", ticket.group_pubkey]),
        Tag.parse(["epoch", str(ticket.epoch)]),
        Tag.parse(["invited_at", str(ticket.invited_at)]),
        Tag.parse(["invitation_proof", ticket.invitation_proof]),
    ]
    rumor = (
        EventBuilder(Kind(NIP17_MESSAGE_KIND), message)
        .tags(tags)
        .build(keys.public_key())
    )
    gift = _gift_wrap_with_keys(keys, epoch_pubkey, rumor)
    await _send_event_to_relays(gift, relays)
    return json.loads(gift.as_json())


async def fetch_latest_nostr_group_ticket(
    private_key_hex: str,
    group_pubkey_hex: str,
    relays: list[str],
) -> NostrGroupTicket:
    keys = Keys.parse(private_key_hex)
    group_pubkey = PublicKey.parse(group_pubkey_hex).to_hex()
    relay_urls = _parse_relay_urls(relays)
    if not relay_urls:
        raise ValueError("No relays configured for NIP-17B ticket discovery.")

    events = await _fetch_events_from_relays(
        relay_urls,
        {
            "kinds": [NIP17_GIFT_WRAP_KIND],
            "#p": [keys.public_key().to_hex()],
            "limit": 200,
        },
    )

    tickets: list[NostrGroupTicket] = []
    for wrapped_event in events:
        try:
            ticket = _decrypt_nostr_group_ticket(
                wrapped_event,
                keys,
                group_pubkey,
            )
            tickets.append(ticket)
        except Exception as exc:
            logger.debug(f"Ignoring invalid NIP-17B ticket: {exc}")

    if not tickets:
        raise ValueError("No valid NIP-17B epoch ticket found for this group.")

    return _select_latest_nostr_group_ticket(tickets)


def _select_latest_nostr_group_ticket(
    tickets: list[NostrGroupTicket],
) -> NostrGroupTicket:
    highest_epoch = max(ticket.epoch for ticket in tickets)
    current_tickets = [ticket for ticket in tickets if ticket.epoch == highest_epoch]
    epoch_keys = {ticket.epoch_private_key for ticket in current_tickets}
    if len(epoch_keys) != 1:
        raise ValueError(
            f"NIP-17B epoch {highest_epoch} has conflicting epoch private keys."
        )

    return min(
        current_tickets,
        key=lambda ticket: (-ticket.invited_at, ticket.event_id),
    )


def _decrypt_nostr_group_ticket(
    wrapped_event: Event,
    member_keys: Keys,
    group_pubkey: str,
) -> NostrGroupTicket:
    if wrapped_event.kind().as_u16() != NIP17_GIFT_WRAP_KIND:
        raise ValueError("Event is not a NIP-59 gift wrap.")
    if not wrapped_event.verify():
        raise ValueError("Gift wrap signature is invalid.")
    tags = [tag.as_vec() for tag in wrapped_event.tags().to_vec()]
    recipient_tags = [tag for tag in tags if tag and tag[0] == "p"]
    member_pubkey = member_keys.public_key().to_hex()
    if (
        len(recipient_tags) != 1
        or len(recipient_tags[0]) < 2
        or recipient_tags[0][1] != member_pubkey
    ):
        raise ValueError("Gift wrap is not addressed to this member.")

    decrypted = nip44_decrypt(
        member_keys.secret_key(),
        wrapped_event.author(),
        wrapped_event.content(),
    )
    ticket_event = Event.from_json(decrypted)
    if ticket_event.kind().as_u16() == NIP17_SEAL_KIND:
        if not ticket_event.verify():
            raise ValueError("Ticket seal signature is invalid.")
        if ticket_event.author().to_hex() != group_pubkey:
            raise ValueError("Ticket seal was not signed by the group identity.")
        seal_tags = [tag.as_vec() for tag in ticket_event.tags().to_vec()]
        if seal_tags and (
            len(seal_tags) != 1
            or len(seal_tags[0]) != 2
            or seal_tags[0][0] != "invitation_proof"
        ):
            raise ValueError("Ticket seal tags are invalid.")
        decrypted_ticket = nip44_decrypt(
            member_keys.secret_key(),
            ticket_event.author(),
            ticket_event.content(),
        )
        if seal_tags:
            # Some clients carry an unsigned ticket's signature on its seal.
            ticket_data = json.loads(decrypted_ticket)
            if not isinstance(ticket_data, dict) or "sig" in ticket_data:
                raise ValueError("Ticket seal does not contain an unsigned ticket.")
            ticket_data["sig"] = seal_tags[0][1]
            decrypted_ticket = json.dumps(ticket_data)
        ticket_event = Event.from_json(decrypted_ticket)
    return _parse_nostr_group_ticket_event(
        ticket_event,
        member_keys,
        group_pubkey,
    )


def _parse_nostr_group_ticket_event(
    ticket_event: Event,
    member_keys: Keys,
    group_pubkey: str,
) -> NostrGroupTicket:
    if ticket_event.kind().as_u16() != NIP17B_TICKET_KIND:
        raise ValueError("Gift wrap does not contain an epoch ticket.")
    if not ticket_event.verify():
        raise ValueError("Epoch ticket signature is invalid.")
    if ticket_event.author().to_hex() != group_pubkey:
        raise ValueError("Epoch ticket group identity does not match.")

    tags = [tag.as_vec() for tag in ticket_event.tags().to_vec()]
    member_tags = [tag for tag in tags if tag[0] == "p"]
    epoch_tags = [tag for tag in tags if tag[0] == "epoch"]
    if len(member_tags) != 1 or len(member_tags[0]) != 2:
        raise ValueError("Epoch ticket must contain exactly one member tag.")
    if member_tags[0][1] != member_keys.public_key().to_hex():
        raise ValueError("Epoch ticket is addressed to a different member.")
    if len(epoch_tags) != 1 or len(epoch_tags[0]) != 2:
        raise ValueError("Epoch ticket must contain exactly one epoch tag.")
    epoch_value = epoch_tags[0][1]
    if not epoch_value.isascii() or not epoch_value.isdecimal():
        raise ValueError("Epoch ticket number is invalid.")
    epoch = int(epoch_value)
    if epoch_value != str(epoch):
        raise ValueError("Epoch ticket number is not canonically encoded.")

    epoch_private_key = ticket_event.content()
    if len(epoch_private_key) != 64 or epoch_private_key.lower() != epoch_private_key:
        raise ValueError("Epoch private key must be 32-byte lowercase hex.")
    Keys.parse(epoch_private_key)

    return NostrGroupTicket(
        group_pubkey=group_pubkey,
        epoch=epoch,
        epoch_private_key=epoch_private_key,
        invited_at=ticket_event.created_at().as_secs(),
        invitation_proof=ticket_event.signature(),
        event_id=ticket_event.id().to_hex(),
    )


def _gift_wrap_with_keys(
    sender_keys: Keys,
    receiver: PublicKey,
    rumor: UnsignedEvent,
) -> Event:
    encrypted_rumor = nip44_encrypt(
        sender_keys.secret_key(),
        receiver,
        rumor.as_json(),
        Nip44Version.V2,
    )
    random_past = secrets.randbelow(172_801)
    created_at = Timestamp.from_secs(max(0, Timestamp.now().as_secs() - random_past))
    seal = (
        EventBuilder(Kind(NIP17_SEAL_KIND), encrypted_rumor)
        .custom_created_at(created_at)
        .sign_with_keys(sender_keys)
    )
    return gift_wrap_from_seal(receiver, seal)


async def _fetch_events_from_relays(
    relays: list[str],
    filter_data: dict,
    timeout: float = 5,
) -> list[Event]:
    results = await asyncio.gather(
        *(
            asyncio.to_thread(
                _fetch_events_from_relay,
                relay,
                filter_data,
                timeout,
            )
            for relay in relays
        ),
        return_exceptions=True,
    )
    events: dict[str, Event] = {}
    connected = False
    for relay, result in zip(relays, results, strict=True):
        if isinstance(result, BaseException):
            if isinstance(result, asyncio.CancelledError):
                raise result
            logger.warning(f"Error fetching Nostr events from relay {relay}: {result}")
            continue
        connected = True
        for event in result:
            events[event.id().to_hex()] = event
    if not connected:
        raise ConnectionError("Failed to connect to any Nostr ticket relay.")
    return list(events.values())


def _fetch_events_from_relay(
    relay: str,
    filter_data: dict,
    timeout: float,
) -> list[Event]:
    subscription_id = secrets.token_hex(8)
    ws = create_connection(relay, timeout=timeout)
    events: list[Event] = []
    deadline = time.monotonic() + timeout
    max_events = filter_data.get("limit", 200)
    try:
        ws.send(json.dumps(["REQ", subscription_id, filter_data]))
        while time.monotonic() < deadline and len(events) < max_events:
            ws.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                raw_message = ws.recv()
            except WebSocketTimeoutException:
                break
            if isinstance(raw_message, bytes):
                raw_message = raw_message.decode()
            if len(raw_message) > MAX_NOSTR_RELAY_MESSAGE_SIZE:
                continue
            message = json.loads(raw_message)
            if not isinstance(message, list) or len(message) < 2:
                continue
            if message[0] == "EOSE" and message[1] == subscription_id:
                break
            if (
                message[0] == "EVENT"
                and message[1] == subscription_id
                and len(message) == 3
            ):
                events.append(Event.from_json(json.dumps(message[2])))
    finally:
        try:
            ws.send(json.dumps(["CLOSE", subscription_id]))
        except Exception as exc:
            logger.debug(f"Failed to close Nostr subscription: {exc}")
        try:
            ws.close()
        except Exception as exc:
            logger.debug(f"Failed to close Nostr relay connection: {exc}")
    return events


def _publish_event_to_relay(relay: str, event: Event) -> None:
    ws = create_connection(relay, timeout=5)
    try:
        ws.send(json.dumps(["EVENT", json.loads(event.as_json())]))
    finally:
        try:
            ws.close()
        except Exception as exc:
            logger.debug(f"Failed to close Nostr relay connection: {exc}")


async def _send_event_to_relays(
    event: Event,
    relays: list[str],
) -> None:
    relay_urls = _parse_relay_urls(relays)
    if not relay_urls:
        raise ValueError("No Nostr relays found for recipient.")

    results = await asyncio.gather(
        *(
            asyncio.to_thread(_publish_event_to_relay, relay_url, event)
            for relay_url in relay_urls
        ),
        return_exceptions=True,
    )
    sent = False
    for relay_url, result in zip(relay_urls, results, strict=True):
        if isinstance(result, BaseException):
            if isinstance(result, asyncio.CancelledError):
                raise result
            logger.warning(f"Error sending notification to relay {relay_url}: {result}")
            continue
        sent = True
    if not sent:
        raise ConnectionError("Failed to send Nostr event to any recipient relay.")


def _parse_relay_urls(relays: list[str]) -> list[str]:
    relay_urls: list[str] = []
    for relay in relays[:MAX_NOSTR_RELAYS]:
        if isinstance(relay, str) and is_ws_url(relay):
            if relay in relay_urls:
                continue
            relay_urls.append(relay)
        else:
            logger.warning(f"Ignoring invalid Nostr relay '{relay}'.")
    return relay_urls


async def fetch_nip5_details(identifier: str) -> tuple[str, list[str]]:
    identifier, domain = identifier.split("@")
    if not identifier or not domain:
        raise ValueError("Invalid NIP5 identifier")

    if not is_valid_url(f"https://{domain}"):
        raise ValueError("Invalid NIP5 domain")

    validate_identifier(identifier)

    url = f"https://{domain}/.well-known/nostr.json?name={identifier}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if "names" not in data or identifier not in data["names"]:
            raise ValueError("NIP5 not name found")
        pubkey = data["names"][identifier]
        pubkey = validate_pub_key(pubkey)

        relay_map = data.get("relays", {})
        relays = relay_map.get(pubkey, []) if isinstance(relay_map, dict) else []
        relays = _parse_relay_urls(relays) if isinstance(relays, list) else []

        return pubkey, relays


async def resolve_nostr_recipient(
    identifier: str,
    fallback_relays: list[str] | None = None,
) -> tuple[str, list[str]]:
    if "@" in identifier:
        pubkey, relays = await fetch_nip5_details(identifier)
        return normalize_public_key(pubkey), relays

    return normalize_public_key(identifier), list(fallback_relays or [])
