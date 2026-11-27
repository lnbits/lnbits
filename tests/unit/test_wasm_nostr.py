import hashlib
import json

import nostr_sdk as sdk
import pytest

from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost

pytestmark = pytest.mark.anyio


@pytest.fixture
def nostr():
    host = ExtensionAPIHost(ExtensionHostAPI("testbot", [], context="public"))
    return host.import_object()["lnbits:extension/nostr"]


async def test_nostr_unsigned_signed_and_auth_events(nostr):
    alice = await nostr["generateKeypair"]()
    assert (await nostr["getPublicKey"]({"privateKey": alice["privateKey"]})) == {
        "publicKey": alice["publicKey"]
    }
    relay = "wss://example.org/relay"
    unsigned = await nostr["buildAuthEvent"]({"relay": relay, "challenge": "雪"})
    event = json.loads(unsigned["eventJson"])
    assert event["kind"] == 22242
    assert event["tags"] == [["relay", relay], ["challenge", "雪"]]
    assert "sig" not in event
    signed = await nostr["signEvent"]({**unsigned, "privateKey": alice["privateKey"]})
    signed_event = json.loads(signed["eventJson"])
    pubkey = signed_event["pubkey"]
    assert pubkey == alice["publicKey"]
    canonical = [0, pubkey, event["created_at"], 22242, event["tags"], ""]
    event_id = hashlib.sha256(
        json.dumps(canonical, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert signed_event["id"] == event_id
    assert await nostr["eventId"](signed) == {"eventId": event_id}
    assert await nostr["verifyEvent"](signed) == {"valid": True}
    for tampered in (
        {"id": "01" * 32},
        {"content": "changed"},
        {"sig": "00" * 64},
    ):
        payload = {"eventJson": json.dumps({**signed_event, **tampered})}
        assert await nostr["verifyEvent"](payload) == {"valid": False}
    assert await nostr["verifyEvent"]({"eventJson": "invalid"}) == {"valid": False}


@pytest.mark.parametrize("nip", ["nip44", "nip04"])
async def test_nostr_encrypt_decrypt(nostr, nip):
    alice, bob = sdk.Keys.generate(), sdk.Keys.generate()
    message = "BTC price in €"
    encrypted = await nostr[nip + "Encrypt"](
        {
            "privateKey": alice.secret_key().to_bech32(),
            "publicKey": bob.public_key().to_hex(),
            "plaintext": message,
        }
    )
    decrypt = sdk.nip44_decrypt if nip == "nip44" else sdk.nip04_decrypt
    assert (
        decrypt(bob.secret_key(), alice.public_key(), encrypted["ciphertext"])
        == message
    )
    decrypted = await nostr[nip + "Decrypt"](
        {
            "privateKey": bob.secret_key().to_hex(),
            "publicKey": alice.public_key().to_bech32(),
            **encrypted,
        }
    )
    assert decrypted == {"plaintext": message}
    if nip == "nip44":
        with pytest.raises(ValueError, match="Invalid input"):
            await nostr["nip44Decrypt"](
                {
                    "privateKey": alice.secret_key().to_hex(),
                    "publicKey": alice.public_key().to_hex(),
                    **encrypted,
                }
            )


async def test_nostr_gift_wrap_interoperates_with_sdk(nostr):
    alice, bob = sdk.Keys.generate(), sdk.Keys.generate()
    draft = {
        "kind": 14,
        "created_at": 42,
        "content": "/price",
        "tags": [["p", bob.public_key().to_hex()]],
    }
    wrapped = await nostr["giftWrap"](
        {
            "privateKey": alice.secret_key().to_hex(),
            "recipient": bob.public_key().to_hex(),
            "eventJson": json.dumps(draft),
        }
    )
    opened = await sdk.UnwrappedGift.from_gift_wrap(
        sdk.NostrSigner.keys(bob), sdk.Event.from_json(wrapped["eventJson"])
    )
    assert opened.sender().to_hex() == alice.public_key().to_hex()
    assert opened.rumor().content() == "/price"
    wrapped_by_sdk = await sdk.gift_wrap(
        sdk.NostrSigner.keys(alice), bob.public_key(), opened.rumor()
    )
    result = await nostr["unwrapGift"](
        {"privateKey": bob.secret_key().to_hex(), "eventJson": wrapped_by_sdk.as_json()}
    )
    assert result["sender"] == alice.public_key().to_hex()
    assert json.loads(result["eventJson"]) == json.loads(opened.rumor().as_json())
    with pytest.raises(ValueError, match="Invalid input"):
        await nostr["unwrapGift"](
            {"privateKey": alice.secret_key().to_hex(), **wrapped}
        )


@pytest.mark.parametrize(
    "change",
    [
        "outer_signature",
        "seal_signature",
        "rumor_author",
        "rumor_id",
        "signed_rumor",
        "seal_tags",
    ],
)
async def test_nostr_gift_checks_each_layer(nostr, change):
    alice, bob, ephemeral = (
        sdk.Keys.generate(),
        sdk.Keys.generate(),
        sdk.Keys.generate(),
    )
    peer = bob.public_key()

    def signed(keys, kind, tags, content):
        return sdk.UnsignedEvent.from_json(
            json.dumps(
                {
                    "pubkey": keys.public_key().to_hex(),
                    "created_at": 0,
                    "kind": kind,
                    "tags": tags,
                    "content": content,
                }
            )
        ).sign_with_keys(keys)

    def encrypt(keys, obj):
        return sdk.nip44_encrypt(
            keys.secret_key(), peer, json.dumps(obj), sdk.Nip44Version.V2
        )

    rumor_author = bob if change == "rumor_author" else alice
    rumor = json.loads(signed(rumor_author, 14, [], "test").as_json())
    if change != "signed_rumor":
        del rumor["sig"]
    if change == "rumor_id":
        rumor["id"] = "00" * 32
    seal = json.loads(
        signed(
            alice, 13, [["x"]] if change == "seal_tags" else [], encrypt(alice, rumor)
        ).as_json()
    )
    if change == "seal_signature":
        seal["sig"] = "00" * 64
    gift = json.loads(
        signed(
            ephemeral, 1059, [["p", peer.to_hex()]], encrypt(ephemeral, seal)
        ).as_json()
    )
    if change == "outer_signature":
        gift["sig"] = "00" * 64
    with pytest.raises(ValueError, match="Invalid input"):
        await nostr["unwrapGift"](
            {"privateKey": bob.secret_key().to_hex(), "eventJson": json.dumps(gift)}
        )


async def test_nostr_identifiers(nostr):
    keys = sdk.Keys.generate()
    pubkey = keys.public_key().to_hex()
    event_id = "ab" * 32
    relays = ["wss://one.example", "wss://two.example/path"]
    assert await nostr["normalizePublicKey"](
        {"publicKey": keys.public_key().to_bech32()}
    ) == {"publicKey": pubkey}
    assert await nostr["encodeNip19"](
        {"prefix": "npub", "value": pubkey, "relays": None}
    ) == {"encoded": keys.public_key().to_bech32()}
    for parts in [
        {"prefix": "npub", "value": pubkey},
        {"prefix": "nsec", "value": keys.secret_key().to_hex()},
        {"prefix": "note", "value": event_id},
        {"prefix": "nprofile", "value": pubkey, "relays": relays},
        {"prefix": "nevent", "value": event_id},
        {
            "prefix": "nevent",
            "value": event_id,
            "author": pubkey,
            "kind": 0,
            "relays": relays,
        },
        {
            "prefix": "naddr",
            "value": "rants",
            "kind": 34550,
            "author": pubkey,
            "relays": relays,
        },
    ]:
        identifier = await nostr["encodeNip19"](parts)
        assert identifier["encoded"].startswith(parts["prefix"] + "1")
        decoded = await nostr["decodeNip19"](
            {"encoded": "nostr:" + identifier["encoded"]}
        )
        assert decoded == {"relays": [], "kind": None, "author": None, **parts}
    with pytest.raises(ValueError, match="Invalid input"):
        await nostr["encodeNip19"](
            {"prefix": "naddr", "value": "雪" * 100, "kind": 34550, "author": pubkey}
        )


async def test_nostr_errors_do_not_echo_keys_or_messages(nostr):
    for payload in [
        {
            "privateKey": "do-not-echo",
            "publicKey": "invalid",
            "plaintext": "sensitive-content",
        },
        {
            "privateKey": "do-not-echo" * 20,
            "publicKey": "invalid",
            "plaintext": "sensitive-content",
        },
    ]:
        with pytest.raises(ValueError) as error:
            await nostr["nip44Encrypt"](payload)
        assert "do-not-echo" not in str(error.value)
        assert "sensitive-content" not in str(error.value)
