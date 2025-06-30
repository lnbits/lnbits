import asyncio

import httpx
from loguru import logger
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
