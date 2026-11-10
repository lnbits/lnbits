import asyncio
from contextlib import AsyncExitStack
from datetime import timedelta

import httpx
from loguru import logger
from nostr_sdk import (
    Client,
    ClientBuilder,
    ConnectionMode,
    CustomWebSocketTransport,
    EventBuilder,
    Filter,
    Keys,
    Kind,
    NostrSdkError,
    NostrSigner,
    PublicKey,
    RelayUrl,
    WebSocketAdapter,
    WebSocketAdapterWrapper,
    WebSocketMessage,
    gift_wrap,
    uniffi_set_event_loop,
)
from pynostr.encrypted_dm import EncryptedDirectMessage
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosedOK

from lnbits.core.helpers import is_valid_url
from lnbits.utils.nostr import (
    validate_identifier,
    validate_pub_key,
)
from lnbits.utils.safe_http import SafeHttpClient, safe_websocket, validate_url


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

    async with AsyncExitStack() as connections:
        for relay in relays:
            try:
                ws = await connections.enter_async_context(
                    safe_websocket(relay, apply_callback_rules=False)
                )
                await ws.send(notification)
            except Exception as e:
                logger.warning(f"Error sending Nostr notification: {type(e).__name__}")
        await asyncio.sleep(1)

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
    # SDK callbacks run on Rust worker threads and must use our event loop.
    uniffi_set_event_loop(asyncio.get_running_loop())
    async with AsyncExitStack() as connections:
        client = (
            ClientBuilder()
            .signer(signer)
            .websocket_transport(_SafeNostrTransport(connections))
            .build()
        )
        try:
            await asyncio.wait_for(
                _send_nip17_message(client, signer, receiver, message, relays),
                timeout=30,
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
    async with SafeHttpClient(timeout=5, apply_callback_rules=False) as client:
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
        await _validate_relay_url(relay)
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
    inbox_relays = []
    if inbox is None:
        inbox_relays = [RelayUrl.parse(relay) for relay in relays]
    else:
        for tag in inbox.tags().to_vec():
            values = tag.as_vec()
            if len(values) >= 2 and values[0] == "relay":
                relay_url = RelayUrl.parse(values[1])
                if relay_url not in inbox_relays:
                    inbox_relays.append(relay_url)
    if not inbox_relays:
        raise ValueError("Recipient's NIP-17 inbox relay list is empty")

    for relay_url in inbox_relays:
        await _validate_relay_url(str(relay_url))
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


async def _validate_relay_url(relay: str) -> None:
    url = httpx.URL(relay)
    if url.scheme not in {"ws", "wss"}:
        raise ValueError("Invalid Nostr relay URL")
    # Reject invalid discovery/inbox lists early. The transport also validates
    # and pins the destination on every connection, including SDK reconnects.
    await validate_url(
        url.copy_with(scheme="https" if url.scheme == "wss" else "http"),
        apply_callback_rules=False,
    )


class _SafeNostrTransport(CustomWebSocketTransport):
    def __init__(self, connections: AsyncExitStack):
        self.connections = connections

    def support_ping(self) -> bool:
        # websockets handles ping/pong and keepalives itself.
        return False

    async def connect(
        self, url: str, mode: ConnectionMode, timeout: timedelta
    ) -> WebSocketAdapterWrapper:
        if not mode.is_direct():
            raise NostrSdkError.Generic("Nostr notification proxies are not supported")
        try:
            async with asyncio.timeout(timeout.total_seconds()):
                ws = await self.connections.enter_async_context(
                    safe_websocket(url, apply_callback_rules=False)
                )
            return WebSocketAdapterWrapper(_SafeNostrWebSocket(ws))
        except Exception as exc:
            raise NostrSdkError.Generic("Nostr relay connection failed") from exc


class _SafeNostrWebSocket(WebSocketAdapter):
    def __init__(self, connection: ClientConnection):
        self.connection = connection

    async def send(self, msg: WebSocketMessage) -> None:
        try:
            if isinstance(msg, WebSocketMessage.TEXT):
                await self.connection.send(msg.text)
            elif isinstance(msg, WebSocketMessage.BINARY):
                await self.connection.send(msg.bytes)
            elif isinstance(msg, WebSocketMessage.CLOSE):
                await self.close_connection()
            else:
                raise ValueError("Unsupported Nostr WebSocket message")
        except Exception as exc:
            raise NostrSdkError.Generic("Nostr relay send failed") from exc

    async def recv(self) -> WebSocketMessage | None:
        try:
            message = await self.connection.recv()
            if isinstance(message, str):
                return WebSocketMessage.TEXT(message)
            return WebSocketMessage.BINARY(message)
        except ConnectionClosedOK:
            return None
        except Exception as exc:
            raise NostrSdkError.Generic("Nostr relay receive failed") from exc

    async def close_connection(self) -> None:
        try:
            await self.connection.close()
        except Exception as exc:
            raise NostrSdkError.Generic("Nostr relay close failed") from exc
