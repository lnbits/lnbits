import base64
import hashlib
import json
import time
from typing import Dict

import pytest
import secp256k1
import websockets
from Cryptodome import Random
from Cryptodome.Cipher import AES

from tests.wallets.helpers import (
    WalletTest,
    build_test_id,
    check_assertions,
    load_funding_source,
    wallet_fixtures_from_json,
)


def encrypt_content(priv_key, dest_pub_key, content):
    p = secp256k1.PublicKey(bytes.fromhex("02" + dest_pub_key), True)
    shared = p.tweak_mul(bytes.fromhex(priv_key)).serialize()[1:]
    iv = Random.new().read(AES.block_size)
    aes = AES.new(shared, AES.MODE_CBC, iv)
    pad = lambda s: s + (16 - len(s) % 16) * chr(16 - len(s) % 16)
    content = pad(content).encode("utf-8")
    encryptedB64 = base64.b64encode(aes.encrypt(content)).decode("ascii")
    ivB64 = base64.b64encode(iv).decode("ascii")
    encryptedContent = encryptedB64 + "?iv=" + ivB64
    return encryptedContent


def decrypt_content(priv_key, source_pub_key, content):
    p = secp256k1.PublicKey(bytes.fromhex("02" + source_pub_key), True)
    shared = p.tweak_mul(bytes.fromhex(priv_key)).serialize()[1:]
    (encryptedContentB64, ivB64) = content.split("?iv=")
    encryptedContent = base64.b64decode(encryptedContentB64.encode("ascii"))
    iv = base64.b64decode(ivB64.encode("ascii"))
    aes = AES.new(shared, AES.MODE_CBC, iv)
    decrypted = aes.decrypt(encryptedContent).decode("utf-8")
    unpad = lambda s: s[: -ord(s[len(s) - 1 :])]
    return unpad(decrypted)


def json_dumps(data):
    if isinstance(data, Dict):
        data = {k: v for k, v in data.items() if v is not None}
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def sign_event(pub_key, priv_key, event):
    signature_data = json_dumps(
        [
            0,
            pub_key,
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"],
        ]
    )
    event_id = hashlib.sha256(signature_data.encode()).hexdigest()
    event["id"] = event_id
    event["pubkey"] = pub_key
    s = secp256k1.PrivateKey(bytes.fromhex(priv_key))
    signature = (s.schnorr_sign(bytes.fromhex(event_id), None, raw=True)).hex()
    event["sig"] = signature
    return event


async def run(data: WalletTest):
    if data.skip:
        pytest.skip()

    wallet = None
    mock_settings = data.funding_source.mock_settings

    async def handler(websocket, path):
        async for message in websocket:
            if not wallet:
                continue
            msg = json.loads(message)
            if msg[0] == "REQ":
                sub_id = msg[1]
                sub_filter = msg[2]
                kinds = sub_filter["kinds"]
                if 13194 in kinds:  # Send info event
                    event = {
                        "kind": 13194,
                        "content": " ".join(mock_settings["supported_methods"]),
                        "created_at": int(time.time()),
                        "tags": [],
                    }
                    sign_event(
                        mock_settings["service_public_key"],
                        mock_settings["service_private_key"],
                        event,
                    )
                    await websocket.send(json.dumps(["EVENT", sub_id, event]))
            elif msg[0] == "EVENT":
                event = msg[1]
                decrypted_content = decrypt_content(
                    mock_settings["service_private_key"],
                    mock_settings["user_public_key"],
                    event["content"],
                )
                content = json.loads(decrypted_content)
                mock = None
                for m in data.mocks:
                    rb = m.request_body
                    if rb and rb["method"] == content["method"]:
                        p1 = rb["params"]
                        p2 = content["params"]
                        p1 = {k: v for k, v in p1.items() if v is not None}
                        p2 = {k: v for k, v in p2.items() if v is not None}
                        p1 = json_dumps(p1)
                        p2 = json_dumps(p2)
                        if p1 == p2:
                            mock = m
                            break
                        else:
                            pass
                if mock:
                    sub_id = None
                    for subscription in wallet.subscriptions.values():
                        if subscription["event_id"] == event["id"]:
                            sub_id = subscription["sub_id"]
                            break
                    if sub_id:
                        response = mock.response
                        encrypted_content = encrypt_content(
                            mock_settings["service_private_key"],
                            mock_settings["user_public_key"],
                            json_dumps(response),
                        )
                        response_event = {
                            "kind": 23195,
                            "content": encrypted_content,
                            "created_at": int(time.time()),
                            "tags": [
                                ["e", event["id"]],
                                ["p", mock_settings["user_public_key"]],
                            ],
                        }
                        sign_event(
                            mock_settings["service_public_key"],
                            mock_settings["service_private_key"],
                            response_event,
                        )
                        await websocket.send(
                            json.dumps(["EVENT", sub_id, response_event])
                        )
                else:
                    raise Exception(
                        "No mock found for "
                        + content["method"]
                        + " "
                        + json_dumps(content["params"])
                    )

    async with websockets.serve(handler, "localhost", mock_settings["port"]) as server:
        await server.start_serving()
        wallet = load_funding_source(data.funding_source)
        await check_assertions(wallet, data)
        await wallet.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_data",
    wallet_fixtures_from_json("tests/wallets/fixtures/json/fixtures_nwc.json"),
    ids=build_test_id,
)
async def test_nwc_wallet(test_data: WalletTest):
    await run(test_data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_data",
    wallet_fixtures_from_json("tests/wallets/fixtures/json/fixtures_nwc_bad.json"),
    ids=build_test_id,
)
async def test_nwc_wallet_bad(test_data: WalletTest):
    await run(test_data)
