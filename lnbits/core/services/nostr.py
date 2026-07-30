import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta

import httpx
from loguru import logger
from nostr_sdk import (
    Client,
    Event,
    EventBuilder,
    Filter,
    Keys,
    Kind,
    NostrSigner,
    PublicKey,
    RelayUrl,
    Tag,
    gift_wrap,
    nip44_decrypt,
)
from pynostr.encrypted_dm import EncryptedDirectMessage
from websocket import WebSocket, create_connection

from lnbits.core.helpers import is_valid_url
from lnbits.utils.nostr import (
    normalize_public_key,
    validate_identifier,
    validate_pub_key,
)

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
    signer = NostrSigner.keys(keys)
    receiver = PublicKey.parse(to_pubkey_hex)
    rumor = EventBuilder.private_msg_rumor(receiver, message).build(keys.public_key())
    gift = await gift_wrap(signer, receiver, rumor)
    await _send_event_to_relays(signer, gift, relays)
    return json.loads(gift.as_json())


async def send_nostr_nip17b_dm(
    from_private_key_hex: str,
    group_pubkey_hex: str,
    message: str,
    relays: list[str],
    ticket_relays: list[str],
) -> dict:
    ticket = await fetch_latest_nostr_group_ticket(
        from_private_key_hex,
        group_pubkey_hex,
        ticket_relays,
    )
    keys = Keys.parse(from_private_key_hex)
    signer = NostrSigner.keys(keys)
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
    gift = await gift_wrap(signer, epoch_pubkey, rumor)
    await _send_event_to_relays(signer, gift, relays)
    return json.loads(gift.as_json())


async def fetch_latest_nostr_group_ticket(
    private_key_hex: str,
    group_pubkey_hex: str,
    relays: list[str],
) -> NostrGroupTicket:
    keys = Keys.parse(private_key_hex)
    group_pubkey = PublicKey.parse(group_pubkey_hex).to_hex()
    signer = NostrSigner.keys(keys)
    relay_urls = _parse_relay_urls(relays)
    if not relay_urls:
        raise ValueError("No relays configured for NIP-17B ticket discovery.")

    client = Client(signer)
    try:
        for relay_url in relay_urls:
            await client.add_relay(relay_url)
        await client.connect()
        events = await client.fetch_events_from(
            relay_urls,
            Filter()
            .kind(Kind(NIP17_GIFT_WRAP_KIND))
            .pubkey(keys.public_key())
            .limit(200),
            timedelta(seconds=5),
        )
    finally:
        await client.disconnect()

    tickets: list[NostrGroupTicket] = []
    for wrapped_event in events.to_vec():
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

    return sorted(
        current_tickets,
        key=lambda ticket: (-ticket.invited_at, ticket.event_id),
    )[0]


def _decrypt_nostr_group_ticket(
    wrapped_event: Event,
    member_keys: Keys,
    group_pubkey: str,
) -> NostrGroupTicket:
    if wrapped_event.kind().as_u16() != NIP17_GIFT_WRAP_KIND:
        raise ValueError("Event is not a NIP-59 gift wrap.")
    if not wrapped_event.verify():
        raise ValueError("Gift wrap signature is invalid.")

    decrypted = nip44_decrypt(
        member_keys.secret_key(),
        wrapped_event.author(),
        wrapped_event.content(),
    )
    ticket_event = _unwrap_nostr_group_ticket_event(
        decrypted,
        member_keys,
        group_pubkey,
    )
    return _parse_nostr_group_ticket_event(
        ticket_event,
        member_keys,
        group_pubkey,
    )


def _unwrap_nostr_group_ticket_event(
    decrypted: str,
    member_keys: Keys,
    group_pubkey: str,
) -> Event:
    wrapped_content = json.loads(decrypted)
    if wrapped_content.get("kind") == NIP17_SEAL_KIND:
        seal = Event.from_json(json.dumps(wrapped_content))
        if not seal.verify():
            raise ValueError("Ticket seal signature is invalid.")
        if not seal.tags().is_empty():
            raise ValueError("Ticket seal tags must be empty.")
        if seal.author().to_hex() != group_pubkey:
            raise ValueError("Ticket seal was not signed by the group identity.")
        decrypted = nip44_decrypt(
            member_keys.secret_key(),
            seal.author(),
            seal.content(),
        )
    return Event.from_json(decrypted)


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
    if not epoch_tags[0][1].isdecimal():
        raise ValueError("Epoch ticket number is invalid.")

    epoch_private_key = ticket_event.content()
    if len(epoch_private_key) != 64 or epoch_private_key.lower() != epoch_private_key:
        raise ValueError("Epoch private key must be 32-byte lowercase hex.")
    Keys.parse(epoch_private_key)

    return NostrGroupTicket(
        group_pubkey=group_pubkey,
        epoch=int(epoch_tags[0][1]),
        epoch_private_key=epoch_private_key,
        invited_at=ticket_event.created_at().as_secs(),
        invitation_proof=ticket_event.signature(),
        event_id=ticket_event.id().to_hex(),
    )


async def _send_event_to_relays(
    signer: NostrSigner,
    event: Event,
    relays: list[str],
) -> None:
    relay_urls = _parse_relay_urls(relays)
    if not relay_urls:
        raise ValueError("No Nostr relays found for recipient.")

    client = Client(signer)
    try:
        for relay_url in relay_urls:
            await client.add_relay(relay_url)
        await client.connect()
        await client.send_event_to(relay_urls, event)
    finally:
        await client.disconnect()


def _parse_relay_urls(relays: list[str]) -> list[RelayUrl]:
    relay_urls: list[RelayUrl] = []
    for relay in dict.fromkeys(relays):
        try:
            relay_urls.append(RelayUrl.parse(relay))
        except Exception as exc:
            logger.warning(f"Ignoring invalid Nostr relay '{relay}': {exc}")
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

        relays = data["relays"].get(pubkey, []) if "relays" in data else []

        return pubkey, relays


async def resolve_nostr_recipient(
    identifier: str,
    fallback_relays: list[str] | None = None,
) -> tuple[str, list[str]]:
    if "@" in identifier:
        pubkey, relays = await fetch_nip5_details(identifier)
        return normalize_public_key(pubkey), relays

    return normalize_public_key(identifier), list(fallback_relays or [])
