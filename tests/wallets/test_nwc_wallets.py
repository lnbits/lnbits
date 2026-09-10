import asyncio
import base64
import hashlib
import json
import time
from types import SimpleNamespace
from typing import cast

import pytest
from coincurve import PrivateKey, PublicKey
from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from websockets import ServerConnection
from websockets import serve as ws_serve

from lnbits.wallets.nwc import NWCConnection, NWCError, NWCWallet
from tests.wallets.helpers import (
    WalletTest,
    build_test_id,
    check_assertions,
    load_funding_source,
    wallet_fixtures_from_json,
)


def encrypt_content(priv_key, dest_pub_key, content):
    p = PublicKey(bytes.fromhex("02" + dest_pub_key))
    shared = p.multiply(bytes.fromhex(priv_key)).format()[1:]
    iv = Random.new().read(AES.block_size)
    aes = AES.new(shared, AES.MODE_CBC, iv)

    content_bytes = content.encode("utf-8")
    content_bytes = pad(content_bytes, AES.block_size)

    encrypted_b64 = base64.b64encode(aes.encrypt(content_bytes)).decode("ascii")
    iv_b64 = base64.b64encode(iv).decode("ascii")
    encrypted_content = encrypted_b64 + "?iv=" + iv_b64
    return encrypted_content


def decrypt_content(priv_key, source_pub_key, content):
    p = PublicKey(bytes.fromhex("02" + source_pub_key))
    shared = p.multiply(bytes.fromhex(priv_key)).format()[1:]
    encrypted_content_b64, iv_b64 = content.split("?iv=")
    encrypted_content = base64.b64decode(encrypted_content_b64.encode("ascii"))
    iv = base64.b64decode(iv_b64.encode("ascii"))
    aes = AES.new(shared, AES.MODE_CBC, iv)
    decrypted_bytes = aes.decrypt(encrypted_content)
    decrypted_bytes = unpad(decrypted_bytes, AES.block_size)
    return decrypted_bytes.decode("utf-8")


def json_dumps(data):
    if isinstance(data, dict):
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
    s = PrivateKey(bytes.fromhex(priv_key))
    signature = s.sign_schnorr(bytes.fromhex(event_id)).hex()
    event["sig"] = signature
    return event


async def handle(  # noqa: C901
    wallet, mock_settings, data, websocket: ServerConnection
):
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
            elif 23195 in kinds:
                assert sub_filter["authors"] == [mock_settings["service_public_key"]]
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
                    p1 = json_dumps({k: v for k, v in p1.items() if v is not None})
                    p2 = json_dumps({k: v for k, v in p2.items() if v is not None})
                    if p1 == p2:
                        mock = m
                        break
            if mock:
                sub_id = None
                nwcwallet = cast(NWCWallet, wallet)
                for subscription in nwcwallet.conn.subscriptions.values():
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
                    await websocket.send(json.dumps(["EVENT", sub_id, response_event]))
            else:
                raise Exception(
                    "No mock found for "
                    + content["method"]
                    + " "
                    + json_dumps(content["params"])
                )


async def run(data: WalletTest):
    if data.skip:
        pytest.skip()

    wallet = None
    mock_settings = data.funding_source.mock_settings
    if mock_settings is None:
        return

    def handler(websocket):
        return handle(wallet, mock_settings, data, websocket)

    if mock_settings is not None:
        async with ws_serve(handler, "localhost", mock_settings["port"]) as server:
            await server.start_serving()
            wallet = load_funding_source(data.funding_source)
            await check_assertions(wallet, data)
            nwcwallet = cast(NWCWallet, wallet)
            await nwcwallet.cleanup()


@pytest.mark.anyio
async def test_nwc_rejects_event_from_unexpected_pubkey(mocker):
    async def _noop(*args, **kwargs):
        return None

    mocker.patch("lnbits.wallets.nwc.NWCConnection._connect_to_relay", new=_noop)
    mocker.patch("lnbits.wallets.nwc.NWCConnection._handle_timeouts", new=_noop)

    service_private_key = PrivateKey()
    service_public_key = service_private_key.public_key.format().hex()[2:]
    attacker_private_key = PrivateKey()
    attacker_public_key = attacker_private_key.public_key.format().hex()[2:]
    account_private_key = PrivateKey()

    conn = NWCConnection(
        service_public_key,
        account_private_key.secret.hex(),
        "ws://127.0.0.1:8555",
    )
    try:
        event = {
            "kind": 23195,
            "content": "{}",
            "created_at": int(time.time()),
            "tags": [["e", "request-event-id"]],
        }
        sign_event(attacker_public_key, attacker_private_key.secret.hex(), event)

        with pytest.raises(Exception, match="Invalid event signature"):
            await conn._on_event_message(["EVENT", "subid", event])
    finally:
        await conn.close()


@pytest.mark.anyio
async def test_nwc_marks_pending_invoice_settled_only_once():
    wallet = NWCWallet.__new__(NWCWallet)
    wallet.pending_invoice_details = {"checking-id": {"checking_id": "checking-id"}}
    wallet.pending_invoices = ["checking-id"]
    wallet.paid_invoices_queue = asyncio.Queue(0)

    wallet._mark_invoice_settled("checking-id", source="notification")
    wallet._mark_invoice_settled("checking-id", source="notification")

    assert wallet.paid_invoices_queue.qsize() == 1
    assert await wallet.paid_invoices_queue.get() == "checking-id"


@pytest.mark.anyio
async def test_nwc_registers_notification_subscriptions(mocker):
    async def _noop(*args, **kwargs):
        return None

    mocker.patch("lnbits.wallets.nwc.NWCConnection._connect_to_relay", new=_noop)
    mocker.patch("lnbits.wallets.nwc.NWCConnection._handle_timeouts", new=_noop)

    service_private_key = PrivateKey()
    service_public_key = service_private_key.public_key.format().hex()[2:]
    account_private_key = PrivateKey()

    conn = NWCConnection(
        service_public_key,
        account_private_key.secret.hex(),
        "ws://127.0.0.1:8555",
    )
    send_mock = mocker.patch.object(conn, "_send", mocker.AsyncMock())

    try:
        await conn._subscribe_to_notifications()

        assert len(conn.notification_subscription_ids) == 2
        assert len(conn.subscriptions) == 2
        assert set(conn.subscriptions.keys()) == conn.notification_subscription_ids
        assert all(
            subscription["method"] == "notification_sub"
            and subscription["event_id"] == subscription["sub_id"]
            for subscription in conn.subscriptions.values()
        )
        assert send_mock.await_count == 2
    finally:
        await conn.close()


@pytest.mark.anyio
async def test_nwc_spreads_fallback_lookups_with_cooldown(mocker):
    def _schedule_next_lookup(
        invoice: dict[str, object], now: float | None = None
    ) -> None:
        assert now is not None
        invoice["next_lookup_at"] = now + 1

    wallet = NWCWallet.__new__(NWCWallet)
    wallet.shutdown = False
    wallet.pending_invoices = ["checking-1", "checking-2"]
    wallet.pending_invoice_details = {
        "checking-1": {
            "checking_id": "checking-1",
            "next_lookup_at": 0.0,
            "lookup_attempts": 0,
        },
        "checking-2": {
            "checking_id": "checking-2",
            "next_lookup_at": 0.0,
            "lookup_attempts": 0,
        },
    }
    wallet.pending_invoices_lookup_cooldown = 1.0
    wallet._is_shutting_down = lambda: False
    wallet._payment_data_is_settled = lambda payment_data: False
    wallet._cache_payment_data = lambda *args, **kwargs: None
    wallet._schedule_next_lookup = _schedule_next_lookup
    wallet.conn = mocker.Mock()
    wallet.conn.get_info = mocker.AsyncMock()
    wallet.conn.supports_method = mocker.Mock(return_value=True)
    wallet.conn.call = mocker.AsyncMock(return_value={"settled_at": None})
    sleep_mock = mocker.patch("lnbits.wallets.nwc.asyncio.sleep", mocker.AsyncMock())

    await wallet._run_fallback_lookups(100.0)

    assert wallet.conn.call.await_count == 2
    sleep_mock.assert_awaited_once_with(1.0)


@pytest.fixture
def nwc_payment_wallet(mocker):
    conn = mocker.Mock(spec=NWCConnection)
    conn.get_info = mocker.AsyncMock(return_value={})
    conn.call = mocker.AsyncMock()
    conn.supports_method.side_effect = lambda method: method == "lookup_invoice"
    mocker.patch("lnbits.wallets.nwc.NWCConnection", return_value=conn)
    mocker.patch(
        "lnbits.wallets.nwc.parse_nwc",
        return_value={"pubkey": "pubkey", "secret": "secret", "relay": "relay"},
    )
    mocker.patch(
        "lnbits.wallets.nwc.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash", amount_msat=1000),
    )
    return NWCWallet()


@pytest.mark.anyio
@pytest.mark.parametrize("fee_msat", [0, 123])
@pytest.mark.parametrize(
    "delayed_lookup",
    [
        NWCError("NOT_FOUND", "Not indexed yet"),
        {"type": "outgoing", "state": "pending", "fees_paid": 0},
        {"type": "outgoing", "state": "settled", "preimage": "01" * 32},
    ],
)
async def test_nwc_waits_for_payment_fees(nwc_payment_wallet, delayed_lookup, fee_msat):
    wallet = nwc_payment_wallet
    preimage = "01" * 32
    wallet.conn.call.side_effect = [
        {"preimage": preimage},
        delayed_lookup,
        delayed_lookup,
        {"type": "outgoing", "state": "settled", "fees_paid": fee_msat},
    ]

    response = await wallet.pay_invoice("bolt11", 1000)
    assert response.ok is None
    assert response.checking_id == "payment-hash"

    status = await wallet.get_payment_status("payment-hash")
    assert status.paid is None
    assert status.preimage == preimage

    status = await wallet.get_payment_status("payment-hash")
    assert status.paid is True
    assert status.fee_msat == fee_msat
    assert status.preimage == preimage


@pytest.mark.anyio
@pytest.mark.parametrize("preimage", [None, ""])
async def test_nwc_missing_preimage_stays_pending(nwc_payment_wallet, preimage):
    wallet = nwc_payment_wallet
    wallet.conn.call.side_effect = [
        {"preimage": preimage},
        {"type": "outgoing", "state": "pending"},
    ]

    response = await wallet.pay_invoice("bolt11", 1000)

    assert response.ok is None
    assert response.checking_id == "payment-hash"
    assert wallet._get_cached_payment_data("payment-hash") is None
    status = await wallet.get_payment_status("payment-hash")
    assert status.paid is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("Payment response lost"),
        NWCError("INTERNAL", "Payment response lost"),
        NWCError("OTHER", "Payment response lost"),
    ],
)
async def test_nwc_reconciles_payment_after_lost_response(nwc_payment_wallet, error):
    wallet = nwc_payment_wallet
    wallet.conn.call.side_effect = [
        error,
        NWCError("NOT_FOUND", "Not indexed yet"),
        {
            "type": "outgoing",
            "state": "settled",
            "fees_paid": 123,
            "preimage": "01" * 32,
        },
    ]

    response = await wallet.pay_invoice("bolt11", 1000)
    assert response.ok is None
    assert response.checking_id == "payment-hash"
    status = await wallet.get_payment_status("payment-hash")
    assert status.paid is None
    status = await wallet.get_payment_status("payment-hash")
    assert status.paid is True
    assert status.fee_msat == 123


@pytest.mark.anyio
async def test_nwc_reconciles_explicit_payment_failure(nwc_payment_wallet):
    wallet = nwc_payment_wallet
    wallet.conn.call.side_effect = [
        TimeoutError("Payment response lost"),
        {"type": "outgoing", "state": "failed"},
    ]

    response = await wallet.pay_invoice("bolt11", 1000)
    assert response.ok is None
    status = await wallet.get_payment_status("payment-hash")
    assert status.paid is False


@pytest.mark.anyio
@pytest.mark.parametrize("fee_msat", [0, 123])
async def test_nwc_uses_payment_response_with_fees(nwc_payment_wallet, fee_msat):
    wallet = nwc_payment_wallet
    preimage = "01" * 32
    wallet.conn.call.side_effect = [
        {"preimage": preimage, "fees_paid": fee_msat},
        NWCError("NOT_FOUND", "Not indexed yet"),
    ]

    response = await wallet.pay_invoice("bolt11", 1000)
    status = await wallet.get_payment_status("payment-hash")

    assert response.ok is True
    assert response.fee_msat == fee_msat
    assert status.paid is True
    assert status.fee_msat == fee_msat
    assert status.preimage == preimage


@pytest.mark.anyio
@pytest.mark.parametrize("preimage", [None, "01" * 32])
async def test_nwc_pay_only_provider_requires_preimage(nwc_payment_wallet, preimage):
    wallet = nwc_payment_wallet
    wallet.conn.supports_method.side_effect = lambda method: False
    wallet.conn.call.return_value = {"preimage": preimage}

    response = await wallet.pay_invoice("bolt11", 1000)

    assert response.ok is (True if preimage else None)
    assert response.checking_id == "payment-hash"
    if preimage:
        assert response.fee_msat == 0


@pytest.mark.anyio
async def test_nwc_reconciles_fees_via_transactions(nwc_payment_wallet):
    wallet = nwc_payment_wallet
    wallet.conn.supports_method.side_effect = (
        lambda method: method == "list_transactions"
    )
    wallet.transactions_refresh_interval = 0
    wallet.conn.call.side_effect = [
        {"preimage": "01" * 32},
        {"transactions": []},
        {
            "transactions": [
                {
                    "payment_hash": "payment-hash",
                    "type": "outgoing",
                    "state": "settled",
                    "fees_paid": 123,
                }
            ]
        },
    ]

    response = await wallet.pay_invoice("bolt11", 1000)
    assert response.ok is None
    status = await wallet.get_payment_status("payment-hash")
    assert status.paid is True
    assert status.fee_msat == 123
    assert status.preimage == "01" * 32
    assert wallet.conn.call.call_args.args[0] == "list_transactions"


@pytest.mark.anyio
async def test_nwc_incoming_settlement_does_not_wait_for_fees(nwc_payment_wallet):
    wallet = nwc_payment_wallet
    wallet.conn.call.return_value = {"type": "incoming", "state": "settled"}

    status = await wallet.get_invoice_status("payment-hash")

    assert status.paid is True


@pytest.mark.anyio
@pytest.mark.parametrize(
    "test_data",
    wallet_fixtures_from_json("tests/wallets/fixtures/json/fixtures_nwc.json"),
    ids=build_test_id,
)
async def test_nwc_wallet(test_data: WalletTest):
    await run(test_data)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "test_data",
    wallet_fixtures_from_json("tests/wallets/fixtures/json/fixtures_nwc_bad.json"),
    ids=build_test_id,
)
async def test_nwc_wallet_bad(test_data: WalletTest):
    await run(test_data)
