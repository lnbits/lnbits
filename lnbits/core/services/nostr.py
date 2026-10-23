import asyncio
from datetime import timedelta

import httpx
from loguru import logger
from nostr_sdk import (
    Client,
    EventBuilder,
    Filter,
    Keys,
    Kind,
    NostrSigner,
    PublicKey,
    RelayUrl,
    gift_wrap,
)
from pynostr.encrypted_dm import EncryptedDirectMessage
from websocket import WebSocket, create_connection

from lnbits.core.helpers import is_valid_url
from lnbits.utils.nostr import (
    validate_identifier,
    validate_pub_key,
)


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


async def send_nostr_dm_nip17(
    from_private_key_hex: str,
    to_pubkey_hex: str,
    message: str,
    relays: list[str],
) -> None:
    if not relays:
        raise ValueError("No NIP-05 relays available to discover the recipient's inbox")

    signer = NostrSigner.keys(Keys.parse(from_private_key_hex))
    receiver = PublicKey.parse(to_pubkey_hex)
    client = Client(signer)
    try:
        await asyncio.wait_for(
            _send_nip17_message(client, signer, receiver, message, relays), timeout=30
        )
    except asyncio.TimeoutError as exc:
        raise ValueError("NIP-17 notification timed out") from exc
    finally:
        await client.shutdown()


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
        validate_pub_key(pubkey)

        relays = data["relays"].get(pubkey, []) if "relays" in data else []

        return pubkey, relays


async def _send_nip17_message(
    client: Client,
    signer: NostrSigner,
    receiver: PublicKey,
    message: str,
    relays: list[str],
) -> None:
    timeout = timedelta(seconds=5)
    for relay in relays:
        await client.add_relay(RelayUrl.parse(relay))
    await client.connect()
    await client.wait_for_connection(timeout)

    # NIP-05 relays are discovery hints, not necessarily the recipient's DM inboxes.
    events = await client.fetch_events(
        Filter().author(receiver).kind(Kind(10050)).limit(1), timeout
    )
    inbox = max(
        events.to_vec(), key=lambda event: event.created_at().as_secs(), default=None
    )
    if inbox is None:
        raise ValueError("Recipient has no NIP-17 inbox relay list (kind 10050)")

    inbox_relays = []
    for tag in inbox.tags().to_vec():
        values = tag.as_vec()
        if len(values) >= 2 and values[0] == "relay":
            relay_url = RelayUrl.parse(values[1])
            if relay_url not in inbox_relays:
                inbox_relays.append(relay_url)
    if not inbox_relays:
        raise ValueError("Recipient's NIP-17 inbox relay list is empty")

    for relay_url in inbox_relays:
        await client.add_relay(relay_url)
    await client.connect()
    await client.wait_for_connection(timeout)
    rumor = EventBuilder.private_msg_rumor(receiver, message).build(
        await signer.get_public_key()
    )
    event = await gift_wrap(signer, receiver, rumor)
    result = await client.send_event_to(inbox_relays, event)
    if not result.success:
        raise ValueError("No NIP-17 inbox relay accepted the notification")
