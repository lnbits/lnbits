import asyncio
import base64
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from lnbits.core.crud import create_wallet, get_wallet
from lnbits.core.crud.payments import create_payment
from lnbits.core.crud.wallets import get_total_balance, get_wallets
from lnbits.core.models import CreatePayment
from lnbits.core.models.wallets import WalletType
from lnbits.core.services import create_user_account, update_wallet_balance
from lnbits.core.services import onchain as keys
from lnbits.onchain import hot_wallet_api, sync, views_api
from lnbits.onchain.crud import get_addresses, get_config, update_config
from lnbits.onchain.decorators import OnchainAuth
from lnbits.onchain.explorer import MempoolExplorer, mempool_url
from lnbits.onchain.hot_wallet import wallet_descriptor
from lnbits.settings import settings

PHRASE = "abandon " * 11 + "about"


@pytest.fixture
async def onchain_wallet(http_client, monkeypatch, tmp_path):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id, wallet_type=WalletType.ONCHAIN)
    config = await get_config(wallet.id)
    config.network = "Testnet4"
    await update_config(config, wallet.id)
    monkeypatch.setattr(
        settings,
        "lnbits_onchain_master_key",
        SecretStr(base64.b64encode(bytes(range(32))).decode()),
    )
    monkeypatch.setattr(settings, "lnbits_data_folder", str(tmp_path))
    monkeypatch.delenv("WATCHONLY_MASTER_KEY", raising=False)
    monkeypatch.setattr(settings, "lnbits_allow_onchain_payments", True)

    async def confirmed_key(_name):
        return SimpleNamespace(
            value={
                "fingerprint": keys.key_fingerprint(keys.read_onchain_key()),
                "backup_confirmed": True,
            }
        )

    monkeypatch.setattr(keys, "get_settings_field", confirmed_key)
    monkeypatch.setattr(hot_wallet_api, "request_scan", lambda _wallet: None)
    monkeypatch.setattr(views_api, "request_scan", lambda _wallet: None)
    return wallet, user, {"X-API-KEY": wallet.adminkey}


async def add_watch(client, headers, single_path=False):
    descriptor, _ = wallet_descriptor(PHRASE, "Testnet4")
    if single_path:
        descriptor = descriptor.replace("/{0,1}/*", "/0/*")
    response = await client.post(
        "/onchain/api/v1/wallet",
        headers=headers,
        json={
            "masterpub": descriptor,
            "title": "Hardware reference",
            "network": "Testnet4",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kinds", [("watch", "watch"), ("hot", "hot"), ("hot", "watch")]
)
async def test_one_bitcoin_wallet_per_core_wallet(http_client, onchain_wallet, kinds):
    wallet, user, headers = onchain_wallet
    descriptor, _ = wallet_descriptor(PHRASE, "Testnet4")

    async def setup(kind, api_headers):
        body = {"title": "Bitcoin wallet", "network": "Testnet4"}
        if kind == "watch":
            body["masterpub"] = descriptor
        return await http_client.post(
            "/onchain/api/v1/hot-wallet" if kind == "hot" else "/onchain/api/v1/wallet",
            headers=api_headers,
            json=body,
        )

    results = await asyncio.gather(*(setup(kind, headers) for kind in kinds))
    assert sorted(r.status_code for r in results) == [200, 409]
    rejected = next(r for r in results if r.status_code == 409)
    assert "already configured" in rejected.json()["detail"]
    accounts = await http_client.get("/onchain/api/v1/wallet", headers=headers)
    assert len(accounts.json()) == 1
    account = accounts.json()[0]
    stored_keys = await sync.db.fetchall(
        """SELECT k.wallet FROM onchain_keys k
           JOIN onchain_accounts a ON a.id = k.wallet
           WHERE a.wallet_id = :wallet""",
        {"wallet": wallet.id},
    )
    assert len(stored_keys) == (1 if account["wallet_kind"] == "hot" else 0)
    for kind in ("hot", "watch"):
        assert (await setup(kind, headers)).status_code == 409

    # Another core wallet can be configured independently.
    other = await create_wallet(user_id=user.id, wallet_type=WalletType.ONCHAIN)
    config = await get_config(other.id)
    config.network = "Testnet4"
    await update_config(config, other.id)
    assert (await setup(kinds[1], {"X-API-KEY": other.adminkey})).status_code == 200


@pytest.mark.anyio
async def test_onchain_api_ownership_recovery_and_network(http_client, onchain_wallet):
    wallet, user, headers = onchain_wallet
    response = await http_client.post(
        "/onchain/api/v1/hot-wallet",
        headers=headers,
        json={"title": "Server account", "network": "Testnet4"},
    )
    assert response.status_code == 200, response.text
    account = response.json()
    assert account["wallet_id"] == wallet.id
    assert "mnemonic" not in response.text and "encrypted_seed" not in response.text
    account_id = account["id"]
    path = f"/onchain/api/v1/hot-wallet/{account_id}/backup"
    for key in (wallet.inkey, user.wallets[0].adminkey):
        denied = await http_client.post(path, headers={"X-API-KEY": key})
        assert denied.status_code == 403
    other = await create_wallet(user_id=user.id, wallet_type=WalletType.ONCHAIN)
    denied = await http_client.post(path, headers={"X-API-KEY": other.adminkey})
    assert denied.status_code == 404
    export = await http_client.post(path, headers=headers)
    assert export.status_code == 200
    assert export.headers["cache-control"] == "no-store"
    assert len(export.json()["mnemonic"].split()) == 24
    receive = f"/onchain/api/v1/address/{account_id}"
    assert (await http_client.get(receive, headers=headers)).status_code == 409
    assert (
        await http_client.post(path + "/confirm", headers=headers)
    ).status_code == 200
    addresses = await asyncio.gather(
        *(
            http_client.get(receive, headers={"X-API-KEY": wallet.inkey})
            for _ in range(5)
        )
    )
    assert all(r.status_code == 200 for r in addresses)
    assert len({r.json()["address"] for r in addresses}) == 5
    wrong_network = await http_client.put(
        "/onchain/api/v1/config", headers=headers, json={"network": "Mainnet"}
    )
    assert wrong_network.status_code == 409
    foreign = await http_client.get(
        f"/onchain/api/v1/addresses/{account_id}", headers={"X-API-KEY": other.inkey}
    )
    assert foreign.status_code == 404
    unowned = await http_client.get(
        "/onchain/api/v1/wallet?network=Testnet4", headers={"X-API-KEY": other.inkey}
    )
    assert unowned.json() == []
    address = addresses[0].json()
    forged = await http_client.put(
        f"/onchain/api/v1/address/{address['id']}",
        headers=headers,
        json={"amount": 99999999},
    )
    assert forged.status_code == 400
    loaded_wallet = await get_wallet(wallet.id)
    assert loaded_wallet
    assert loaded_wallet.balance_msat == 0


@pytest.mark.anyio
async def test_onchain_isolated_from_lightning_ledger(http_client, onchain_wallet):
    wallet, _, headers = onchain_wallet
    for amount in (1000, -1000):
        with pytest.raises(ValueError, match="blockchain"):
            await update_wallet_balance(wallet, amount)
        with pytest.raises(ValueError, match="Lightning ledger"):
            await create_payment(
                checking_id="onchain-forgery",
                data=CreatePayment(
                    wallet_id=wallet.id,
                    payment_hash="f" * 64,
                    amount_msat=amount,
                    bolt11="not-an-invoice",
                    memo="test",
                ),
            )
    invoice = await http_client.post(
        "/api/v1/payments",
        headers=headers,
        json={"out": False, "amount": 100, "memo": "Must fail"},
    )
    assert invoice.status_code >= 400
    assert not wallet.can_send_payments
    assert wallet.withdrawable_balance == 0


def chain_fixture(address):
    txid = "a" * 64
    tx = {
        "txid": txid,
        "vin": [{"prevout": None}],
        "vout": [{"value": 100000, "scriptpubkey_address": address}],
        "fee": 100,
        "status": {"confirmed": True, "block_time": 1700000000, "block_height": 100},
    }
    coin = {"txid": txid, "vout": 0, "value": 100000, "status": tx["status"]}
    return tx, coin


@pytest.mark.anyio
@pytest.mark.parametrize("single_path", [False, True])
async def test_onchain_scan_persists_and_hydrates_without_lightning_credit(
    http_client, onchain_wallet, monkeypatch, single_path
):
    wallet, user, headers = onchain_wallet
    account = await add_watch(http_client, headers, single_path)
    addresses = await get_addresses(account["id"])
    funded = addresses[0].address
    tx, coin = chain_fixture(funded)
    fail = False
    empty = False
    paths = []

    def explorer(request):
        paths.append(request.url.path)
        if fail:
            return httpx.Response(503)
        values = []
        if funded in request.url.path and not empty:
            values = [coin] if request.url.path.endswith("/utxo") else [tx]
        return httpx.Response(200, json=values)

    monkeypatch.setattr(
        sync,
        "explorer_client",
        lambda config: MempoolExplorer(
            config,
            httpx.AsyncClient(
                base_url=mempool_url(config) + "/",
                transport=httpx.MockTransport(explorer),
            ),
        ),
    )
    baseline = await get_total_balance()
    await sync.scan_wallet(wallet.id)
    state = await sync.wallet_state(OnchainAuth(wallet.id))
    assert state["balance_sat"] == 100000
    assert state["error"] is None and not state["scanning"]
    assert all(path.startswith("/testnet4/api/") for path in paths)
    loaded_wallet = await get_wallet(wallet.id)
    assert loaded_wallet
    assert loaded_wallet.balance_msat == 100000000
    assert (
        next(w for w in await get_wallets(user.id) if w.id == wallet.id).balance_msat
        == 100000000
    )
    assert await get_total_balance() == baseline
    first_snapshot = next(s for s in state["snapshots"] if s.transactions)
    seen = first_snapshot.transactions[0]["first_seen"]
    await sync.scan_wallet(wallet.id)
    refreshed = await sync.wallet_state(OnchainAuth(wallet.id))
    assert (
        next(s for s in refreshed["snapshots"] if s.transactions).transactions[0][
            "first_seen"
        ]
        == seen
    )
    fail = True
    await sync.scan_wallet(wallet.id)
    failed = await sync.wallet_state(OnchainAuth(wallet.id))
    assert failed["error"] and failed["balance_sat"] == 100000
    assert any(s.transactions for s in failed["snapshots"])
    fail = False
    empty = True
    await sync.scan_wallet(wallet.id)
    replaced = await sync.wallet_state(OnchainAuth(wallet.id))
    assert replaced["balance_sat"] == 0 and replaced["error"] is None
    assert not any(s.transactions for s in replaced["snapshots"])


@pytest.mark.anyio
async def test_onchain_scan_lease_does_not_block_wallet_creation(
    http_client, onchain_wallet, monkeypatch
):
    wallet, _, headers = onchain_wallet
    started, finish = asyncio.Event(), asyncio.Event()
    count = 0

    async def blocked(_wallet):
        nonlocal count
        count += 1
        started.set()
        await finish.wait()

    monkeypatch.setattr(sync, "_scan", blocked)
    task = asyncio.create_task(sync.scan_wallet(wallet.id))
    try:
        await asyncio.wait_for(started.wait(), 2)
        await asyncio.wait_for(sync.scan_wallet(wallet.id), 2)
        assert count == 1
        state = await sync.wallet_state(OnchainAuth(wallet.id))
        assert state["scanning"]
        await asyncio.wait_for(add_watch(http_client, headers), 5)
    finally:
        finish.set()
        await task


@pytest.mark.anyio
async def test_onchain_disabled_signing_keeps_recovery(
    http_client, onchain_wallet, monkeypatch
):
    _, _, headers = onchain_wallet
    created = await http_client.post(
        "/onchain/api/v1/hot-wallet",
        headers=headers,
        json={"title": "Recovery", "network": "Testnet4"},
    )
    assert created.status_code == 200
    monkeypatch.setattr(settings, "lnbits_allow_onchain_payments", False)
    assert (
        await http_client.post(
            "/onchain/api/v1/hot-wallet",
            headers=headers,
            json={"title": "Disabled", "network": "Testnet4"},
        )
    ).status_code == 503
    account_id = created.json()["id"]
    backup = await http_client.post(
        f"/onchain/api/v1/hot-wallet/{account_id}/backup", headers=headers
    )
    assert backup.status_code == 200
    assert len(backup.json()["mnemonic"].split()) == 24


@pytest.mark.anyio
async def test_onchain_core_creation_currency_and_read_balance(
    http_client, onchain_wallet
):
    _, user, _ = onchain_wallet
    created = await http_client.post(
        f"/api/v1/wallet?usr={user.id}",
        json={
            "name": "Bitcoin savings",
            "wallet_type": "onchain",
            "onchain_network": "Testnet4",
        },
    )
    assert created.status_code == 200, created.text
    wallet = created.json()
    assert wallet["wallet_type"] == "onchain"
    assert wallet["extra"]["icon"] == "currency_bitcoin"
    assert wallet["lightning_address"] is None
    assert (await get_config(wallet["id"])).network == "Testnet4"
    headers = {"X-API-KEY": wallet["adminkey"]}
    changed = await http_client.patch(
        "/api/v1/wallet", headers=headers, json={"currency": "EUR", "pinned": True}
    )
    assert changed.status_code == 200
    assert changed.json()["currency"] == "EUR"
    assert changed.json()["extra"]["pinned"]
    assert (
        await http_client.get("/api/v1/wallet", headers={"X-API-KEY": wallet["inkey"]})
    ).json()["balance"] == 0


@pytest.mark.anyio
async def test_onchain_signing_preflight_rejects_spent_coin(
    http_client, onchain_wallet, monkeypatch
):
    from tests.unit.onchain.test_hot_wallet import wallet_and_payment

    wallet, _, headers = onchain_wallet
    created = await http_client.post(
        "/onchain/api/v1/hot-wallet",
        headers={**headers, "X-Onchain-Recovery-Phrase": PHRASE},
        json={"title": "Restored signing account", "network": "Testnet4"},
    )
    assert created.status_code == 200
    account = created.json()
    backup = f"/onchain/api/v1/hot-wallet/{account['id']}/backup"
    assert (await http_client.post(backup, headers=headers)).json()[
        "mnemonic"
    ] == PHRASE
    assert (
        await http_client.post(backup + "/confirm", headers=headers)
    ).status_code == 200
    _, payment = wallet_and_payment()
    for inp in payment.transaction.inputs:
        inp.wallet = account["id"]
    for output in payment.transaction.outputs:
        if output.wallet:
            output.wallet = account["id"]
    coin = payment.transaction.inputs[0]
    spent = True

    def explorer(_request):
        return httpx.Response(
            200,
            json=(
                []
                if spent
                else [{"txid": coin.tx_id, "vout": coin.vout, "value": coin.amount}]
            ),
        )

    monkeypatch.setattr(
        hot_wallet_api,
        "explorer_client",
        lambda config: MempoolExplorer(
            config,
            httpx.AsyncClient(
                base_url="https://explorer.test/",
                transport=httpx.MockTransport(explorer),
            ),
        ),
    )
    path = f"/onchain/api/v1/hot-wallet/{account['id']}/sign"
    rejected = await http_client.post(path, headers=headers, json=payment.dict())
    assert rejected.status_code == 400
    spent = False
    signed = await http_client.post(path, headers=headers, json=payment.dict())
    assert signed.status_code == 200, signed.text
    assert signed.json()["tx_hex"]
    assert signed.headers["cache-control"] == "no-store"
    loaded_wallet = await get_wallet(wallet.id)
    assert loaded_wallet
    assert loaded_wallet.balance_msat == 0


@pytest.mark.anyio
async def test_onchain_permanent_cleanup_preserves_accounts(
    http_client, onchain_wallet
):
    from lnbits.core.crud.users import delete_account, get_account
    from lnbits.core.crud.wallets import force_delete_wallet

    wallet, user, headers = onchain_wallet
    await add_watch(http_client, headers)
    with pytest.raises(ValueError, match="permanently deleted"):
        await force_delete_wallet(wallet.id)
    with pytest.raises(ValueError, match="permanently deleted"):
        await delete_account(user.id)
    assert await get_wallet(wallet.id)
    assert await get_account(user.id)


@pytest.mark.anyio
async def test_onchain_explorer_selection_defaults_and_persists(
    http_client, onchain_wallet, monkeypatch
):
    wallet, _, headers = onchain_wallet
    path = "/onchain/api/v1/config"
    monkeypatch.setattr(settings, "lnbits_blockexplorer_enabled", True)
    monkeypatch.setattr(settings, "lnbits_blockexplorer_network", "test4")
    config = (await http_client.get(path, headers=headers)).json()
    assert config["explorer_provider"] == "lnbits"
    assert config["explorer_url"] == "/blockexplorer"
    assert config["lnbits_explorer_network"] == "Testnet4"
    config.update(
        explorer_provider="mempool", mempool_endpoint="https://example.com/testnet4"
    )
    forbidden = await http_client.put(
        path, headers={"X-API-KEY": wallet.inkey}, json=config
    )
    assert forbidden.status_code == 403
    saved = await http_client.put(path, headers=headers, json=config)
    assert saved.status_code == 200, saved.text
    loaded = (await http_client.get(path, headers=headers)).json()
    assert loaded["explorer_provider"] == "mempool"
    assert loaded["explorer_url"] == "https://example.com/testnet4"
    assert loaded["mempool_endpoint"] == "https://example.com/testnet4"
    # An explicit user choice stays selected even when LNbits is available.
    assert (await get_config(wallet.id)).explorer_provider == "mempool"
    config["explorer_provider"] = "lnbits"
    monkeypatch.setattr(settings, "lnbits_blockexplorer_network", "main")
    rejected = await http_client.put(path, headers=headers, json=config)
    assert rejected.status_code == 400
    monkeypatch.setattr(settings, "lnbits_blockexplorer_enabled", False)
    rejected = await http_client.put(path, headers=headers, json=config)
    assert rejected.status_code == 400


@pytest.mark.anyio
async def test_onchain_local_explorer_used_for_fees_raw_tx_and_broadcast(
    http_client, onchain_wallet, monkeypatch
):
    from unittest.mock import AsyncMock

    from lnbits.core.services import blockexplorer
    from lnbits.utils.electrum import ElectrumClient

    _, _, headers = onchain_wallet
    monkeypatch.setattr(settings, "lnbits_blockexplorer_enabled", True)
    monkeypatch.setattr(settings, "lnbits_blockexplorer_network", "test4")
    client = AsyncMock(spec=ElectrumClient)
    client.estimate_fee.return_value = 0.00002
    client.get_transaction.return_value = "deadbeef"
    client.broadcast.return_value = "a" * 64
    monkeypatch.setattr(blockexplorer, "_client", lambda: client)
    fees = await http_client.get("/onchain/api/v1/fees", headers=headers)
    assert fees.status_code == 200, fees.text
    assert fees.json()["fastestFee"] == 2
    raw = await http_client.get(
        "/onchain/api/v1/tx/" + "a" * 64 + "/hex", headers=headers
    )
    assert raw.status_code == 200 and raw.json() == "deadbeef"
    broadcast = await http_client.post(
        "/onchain/api/v1/tx",
        headers=headers,
        json={"tx_hex": "deadbeef", "network": "Testnet4"},
    )
    assert broadcast.status_code == 200, broadcast.text
    assert broadcast.json() == "a" * 64
    client.broadcast.assert_awaited_once_with("deadbeef")
