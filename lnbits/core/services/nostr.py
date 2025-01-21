from typing import Tuple

import httpx
from loguru import logger
from pynostr.encrypted_dm import EncryptedDirectMessage
from pynostr.key import PrivateKey
from websocket import create_connection

from lnbits.core.helpers import is_valid_url
from lnbits.utils.nostr import (
    validate_identifier,
    validate_pub_key,
)


async def send_nostr_dm(
    from_privkey: str,
    to_pubkey: str,
    message: str,
    relays: list[str],
) -> dict:
    private_key = PrivateKey(bytes.fromhex(from_privkey))

    dm = EncryptedDirectMessage()
    dm.encrypt(
        private_key.hex(),
        recipient_pubkey=to_pubkey,
        cleartext_content=message,
    )

    dm_event = dm.to_event()
    dm_event.sign(private_key.hex())
    message = dm_event.to_message()

    for relay in relays:
        try:
            ws = create_connection(relay, timeout=2)
            # TODO: test with clients
            # Does not work as expected at the moment
            ws.send(message)
            ws.close()
        except Exception as e:
            logger.warning(f"Error sending notification to relay {relay}: {e}")

    return dm_event.to_dict()


async def fetch_nip5_details(identifier: str) -> Tuple[str, list[str]]:
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
