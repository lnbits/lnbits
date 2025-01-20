import time
from typing import Tuple

import httpx
from nostr.key import PrivateKey
from nostr.relay_manager import RelayManager

from lnbits.core.helpers import is_valid_url
from lnbits.utils.nostr import (
    EncryptedDirectMessage,
    validate_identifier,
    validate_pub_key,
)


async def send_nostr_dm(
    from_privkey: str,
    to_pubkey: str,
    message: str,
    relays: list[str],
    wait_for_ws_connection_seconds: int = 1,
) -> dict:
    relay_manager = RelayManager()
    for relay in relays:
        relay_manager.add_relay(relay)
    relay_manager.open_connections()
    time.sleep(wait_for_ws_connection_seconds)

    private_key = PrivateKey(bytes.fromhex(from_privkey))

    dm = EncryptedDirectMessage(recipient_pubkey=to_pubkey, cleartext_content=message)
    private_key.sign_event(dm)
    relay_manager.publish_event(dm)
    relay_manager.close_connections()


async def fetch_nip5_details(identifier: str) -> Tuple[str, list[str]]:
    identifier, domain = identifier.split("@")
    if not identifier or not domain:
        raise ValueError("Invalid NIP5 identifier")

    if not is_valid_url(domain):
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
