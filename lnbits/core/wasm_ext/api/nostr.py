from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar

import nostr_sdk as sdk
from pydantic import BaseModel, ConfigDict, Field

from .models import EmptyRequest
from .registry import extension_api_method

if TYPE_CHECKING:
    from .host import ExtensionHostAPI

_Request = TypeVar("_Request", bound=BaseModel)
_Response = TypeVar("_Response", bound=BaseModel)
_Key = Annotated[str, Field(min_length=1, max_length=128)]
_Text = Annotated[str, Field(max_length=262144)]
_Relay = Annotated[str, Field(min_length=1, max_length=2048)]


class NostrModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class NostrPrivateKey(NostrModel):
    private_key: _Key


class NostrPublicKey(NostrModel):
    public_key: _Key


class NostrKeypair(NostrPrivateKey):
    public_key: str


class NostrEvent(NostrModel):
    event_json: _Text


class NostrEventWithKey(NostrEvent):
    private_key: _Key


class NostrEventId(NostrModel):
    event_id: str


class NostrVerification(NostrModel):
    valid: bool


class NostrGiftRequest(NostrEventWithKey):
    recipient: _Key


class NostrUnwrappedGift(NostrEvent):
    sender: str


class NostrPlaintext(NostrModel):
    plaintext: str


class NostrCiphertext(NostrModel):
    ciphertext: str


class NostrEncryptionRequest(NostrPlaintext):
    plaintext: _Text
    private_key: _Key
    public_key: _Key


class NostrDecryptionRequest(NostrCiphertext):
    ciphertext: str = Field(max_length=1_400_000)
    private_key: _Key
    public_key: _Key


class NostrIdentifier(NostrModel):
    encoded: str = Field(min_length=1, max_length=16384)


class NostrIdentifierParts(NostrModel):
    prefix: Literal["npub", "nsec", "note", "nprofile", "nevent", "naddr"]
    value: str = Field(max_length=16384)
    relays: list[_Relay] | None = Field(default_factory=list, max_length=128)
    author: _Key | None = None
    kind: int | None = Field(default=None, ge=0, le=65535)


class NostrAuthRequest(NostrModel):
    relay: _Relay
    challenge: str = Field(min_length=1, max_length=16384)


def nostr_method(sdk_name: str, description: str) -> Callable[
    [Callable[[Any, _Request], Awaitable[_Response]]],
    Callable[[Any, _Request], Awaitable[_Response]],
]:
    def register(
        function: Callable[[Any, _Request], Awaitable[_Response]],
    ) -> Callable[[Any, _Request], Awaitable[_Response]]:
        name = function.__name__

        @extension_api_method(
            method_id=f"nostr.{name}",
            namespace="nostr",
            name=name.replace("_", " ").capitalize(),
            host_interface="nostr",
            host_name=name,
            sdk_name=sdk_name,
            description=description,
            require_auth=False,
        )
        @wraps(function)
        async def call(self: Any, request: _Request) -> _Response:
            try:
                return await function(self, request)
            except (sdk.NostrSdkError.Generic, ValueError, RecursionError):
                # Invocation failures are recorded. Never include keys or payloads.
                raise ValueError(f"Invalid input for nostr.{name}.") from None

        return call

    return register


class ExtensionNostrAPI:
    def __init__(self, api: ExtensionHostAPI) -> None:
        self.api = api

    @nostr_method("verifyEvent", "Verify the NIP-01 event ID and signature.")
    async def verify_event(self, request: NostrEvent) -> NostrVerification:
        try:
            valid = sdk.Event.from_json(request.event_json).verify()
        except sdk.NostrSdkError.Generic:
            valid = False
        return NostrVerification(valid=valid)

    @nostr_method("signEvent", "Sign an unsigned event with the supplied key.")
    async def sign_event(self, request: NostrEventWithKey) -> NostrEvent:
        keys = sdk.Keys.parse(request.private_key)
        event = _unsigned_for_key(request.event_json, keys)
        return NostrEvent(event_json=event.sign_with_keys(keys).as_json())

    @nostr_method("eventId", "Compute the canonical NIP-01 event ID.")
    async def event_id(self, request: NostrEvent) -> NostrEventId:
        event = sdk.UnsignedEvent.from_json(request.event_json)
        return NostrEventId(event_id=_event_id(event))

    @nostr_method("generateKeypair", "Generate fresh private and public keys in hex.")
    async def generate_keypair(self, request: EmptyRequest) -> NostrKeypair:
        keys = sdk.Keys.generate()
        return NostrKeypair(
            private_key=keys.secret_key().to_hex(),
            public_key=keys.public_key().to_hex(),
        )

    @nostr_method("getPublicKey", "Derive the hex public key from a private key.")
    async def get_public_key(self, request: NostrPrivateKey) -> NostrPublicKey:
        return NostrPublicKey(
            public_key=sdk.Keys.parse(request.private_key).public_key().to_hex()
        )

    @nostr_method("giftWrap", "Seal and gift-wrap an unsigned event for one recipient.")
    async def gift_wrap(self, request: NostrGiftRequest) -> NostrEvent:
        keys = sdk.Keys.parse(request.private_key)
        wrapped = await sdk.gift_wrap(
            sdk.NostrSigner.keys(keys),
            sdk.PublicKey.parse(request.recipient),
            _unsigned_for_key(request.event_json, keys),
        )
        return NostrEvent(event_json=wrapped.as_json())

    @nostr_method("unwrapGift", "Verify and decrypt a NIP-59 gift and its sender.")
    async def unwrap_gift(self, request: NostrEventWithKey) -> NostrUnwrappedGift:
        keys = sdk.Keys.parse(request.private_key)
        gift = sdk.Event.from_json(request.event_json)
        if gift.kind().as_u16() not in (1059, 21059) or not gift.verify():
            raise ValueError("Invalid gift.")
        recipient = keys.public_key().to_hex()
        if not any(key.to_hex() == recipient for key in gift.tags().public_keys()):
            raise ValueError("Wrong recipient.")
        signer = sdk.NostrSigner.keys(keys)
        seal = sdk.Event.from_json(
            await signer.nip44_decrypt(gift.author(), gift.content())
        )
        if (
            seal.kind().as_u16() != 13
            or not seal.tags().is_empty()
            or not seal.verify()
        ):
            raise ValueError("Invalid seal.")
        payload = await signer.nip44_decrypt(seal.author(), seal.content())
        data = _event_object(payload)
        rumor = sdk.UnsignedEvent.from_json(payload)
        sender = seal.author().to_hex()
        if (
            "sig" in data
            or rumor.author().to_hex() != sender
            or data.get("id") != _event_id(rumor)
        ):
            raise ValueError("Invalid rumor.")
        return NostrUnwrappedGift(sender=sender, event_json=rumor.as_json())

    @nostr_method("nip44Encrypt", "Encrypt text with NIP-44 v2.")
    async def nip44_encrypt(self, request: NostrEncryptionRequest) -> NostrCiphertext:
        return NostrCiphertext(
            ciphertext=await _signer(request.private_key).nip44_encrypt(
                sdk.PublicKey.parse(request.public_key),
                request.plaintext,
            )
        )

    @nostr_method("nip44Decrypt", "Decrypt and authenticate a NIP-44 v2 payload.")
    async def nip44_decrypt(self, request: NostrDecryptionRequest) -> NostrPlaintext:
        return NostrPlaintext(
            plaintext=await _signer(request.private_key).nip44_decrypt(
                sdk.PublicKey.parse(request.public_key),
                request.ciphertext,
            )
        )

    @nostr_method(
        "decodeNip19", "Decode a NIP-19 identifier, optionally prefixed with nostr:."
    )
    async def decode_nip19(self, request: NostrIdentifier) -> NostrIdentifierParts:
        entity = sdk.Nip19.from_bech32(request.encoded.removeprefix("nostr:")).as_enum()
        if isinstance(entity, sdk.Nip19Enum.PUBKEY):
            return NostrIdentifierParts(prefix="npub", value=entity.npub.to_hex())
        if isinstance(entity, sdk.Nip19Enum.SECRET):
            return NostrIdentifierParts(prefix="nsec", value=entity.nsec.to_hex())
        if isinstance(entity, sdk.Nip19Enum.NOTE):
            return NostrIdentifierParts(prefix="note", value=entity.event_id.to_hex())
        if isinstance(entity, sdk.Nip19Enum.PROFILE):
            profile = entity.nprofile
            return NostrIdentifierParts(
                prefix="nprofile",
                value=profile.public_key().to_hex(),
                relays=[str(r) for r in profile.relays()],
            )
        if isinstance(entity, sdk.Nip19Enum.EVENT):
            event = entity.event
            author, kind = event.author(), event.kind()
            return NostrIdentifierParts(
                prefix="nevent",
                value=event.event_id().to_hex(),
                author=author.to_hex() if author else None,
                kind=kind.as_u16() if kind else None,
                relays=[str(r) for r in event.relays()],
            )
        if isinstance(entity, sdk.Nip19Enum.ADDR):
            address = entity.coordinate
            coord = address.coordinate()
            return NostrIdentifierParts(
                prefix="naddr",
                value=coord.identifier(),
                author=coord.public_key().to_hex(),
                kind=coord.kind().as_u16(),
                relays=[str(r) for r in address.relays()],
            )
        raise ValueError("Unsupported NIP-19 identifier.")

    @nostr_method("encodeNip19", "Encode NIP-19 identifier parts as bech32.")
    async def encode_nip19(self, request: NostrIdentifierParts) -> NostrIdentifier:
        return NostrIdentifier(encoded=_encode_identifier(request))

    @nostr_method(
        "buildAuthEvent", "Build an unsigned NIP-42 relay authentication event."
    )
    async def build_auth_event(self, request: NostrAuthRequest) -> NostrEvent:
        relay = sdk.RelayUrl.parse(request.relay)
        return NostrEvent(
            event_json=json.dumps(
                {
                    "kind": 22242,
                    "created_at": int(time.time()),
                    "content": "",
                    "tags": [["relay", str(relay)], ["challenge", request.challenge]],
                }
            )
        )

    @nostr_method("normalizePublicKey", "Normalize a hex or npub public key to hex.")
    async def normalize_public_key(self, request: NostrPublicKey) -> NostrPublicKey:
        return NostrPublicKey(
            public_key=sdk.PublicKey.parse(request.public_key).to_hex()
        )

    @nostr_method("nip04Decrypt", "Decrypt a legacy NIP-04 message.")
    async def nip04_decrypt(self, request: NostrDecryptionRequest) -> NostrPlaintext:
        return NostrPlaintext(
            plaintext=await _signer(request.private_key).nip04_decrypt(
                sdk.PublicKey.parse(request.public_key),
                request.ciphertext,
            )
        )

    @nostr_method("nip04Encrypt", "Encrypt text for a legacy NIP-04 peer.")
    async def nip04_encrypt(self, request: NostrEncryptionRequest) -> NostrCiphertext:
        return NostrCiphertext(
            ciphertext=await _signer(request.private_key).nip04_encrypt(
                sdk.PublicKey.parse(request.public_key),
                request.plaintext,
            )
        )


def _signer(private_key: str) -> sdk.NostrSigner:
    return sdk.NostrSigner.keys(sdk.Keys.parse(private_key))


def _event_object(payload: str) -> dict:
    event = json.loads(payload)
    if not isinstance(event, dict):
        raise ValueError("Expected a Nostr event object.")
    return event


def _unsigned_for_key(payload: str, keys: sdk.Keys) -> sdk.UnsignedEvent:
    data = _event_object(payload)
    pubkey = keys.public_key().to_hex()
    if "sig" in data or data.get("pubkey", pubkey) != pubkey:
        raise ValueError("Expected an unsigned event for the supplied key.")
    data["pubkey"] = pubkey
    data.pop("id", None)
    return sdk.UnsignedEvent.from_json(json.dumps(data))


def _event_id(event: sdk.UnsignedEvent) -> str:
    return sdk.EventId(
        event.author(), event.created_at(), event.kind(), event.tags(), event.content()
    ).to_hex()


def _encode_identifier(parts: NostrIdentifierParts) -> str:
    if parts.relays and parts.prefix in ("npub", "note", "nsec"):
        raise ValueError("This identifier cannot carry relay hints.")
    if parts.prefix not in ("naddr", "nevent") and (
        parts.author is not None or parts.kind is not None
    ):
        raise ValueError("This identifier cannot carry an author or kind.")
    if parts.prefix == "npub":
        return sdk.PublicKey.parse(parts.value).to_bech32()
    if parts.prefix == "nsec":
        return sdk.SecretKey.parse(parts.value).to_bech32()
    if parts.prefix == "note":
        return sdk.EventId.parse(parts.value).to_bech32()
    relays = [sdk.RelayUrl.parse(r) for r in parts.relays or []]
    # NIP-19 TLV lengths occupy one byte. The SDK truncates longer lengths.
    if any(len(str(relay).encode()) > 255 for relay in relays):
        raise ValueError("Relay hint exceeds the NIP-19 TLV length.")
    if parts.prefix == "nprofile":
        return sdk.Nip19Profile(sdk.PublicKey.parse(parts.value), relays).to_bech32()
    author = sdk.PublicKey.parse(parts.author) if parts.author else None
    kind = sdk.Kind(parts.kind) if parts.kind is not None else None
    if parts.prefix == "nevent":
        return sdk.Nip19Event(
            sdk.EventId.parse(parts.value), author, kind, relays
        ).to_bech32()
    if author is None or kind is None or len(parts.value.encode()) > 255:
        raise ValueError("Invalid naddr coordinate.")
    return sdk.Nip19Coordinate(
        sdk.Coordinate(kind, author, parts.value), relays
    ).to_bech32()
