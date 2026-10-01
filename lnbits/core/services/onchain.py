"""Onchain wallet key management, signing, and synchronization.

Private material is kept outside the settings database. The database pins its
fingerprint so a lost key cannot silently be replaced when restoring an instance.
"""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from lnbits.core.crud.onchain import (
    get_address_snapshot,
    get_addresses,
    get_wallet_snapshots,
    update_address_snapshot,
)
from lnbits.core.crud.settings import get_settings_field, set_settings_field
from lnbits.core.crud.wallets import (
    acquire_onchain_scan_lease,
    finish_scan,
    get_onchain_sync_status,
    get_onchain_wallet,
    get_onchain_wallet_ids,
)
from lnbits.core.models.onchain import (
    Address,
    HotWalletPayment,
    MasterPublicKey,
    SignedTransaction,
    Snapshot,
)
from lnbits.core.models.wallets import OnchainMeta, OnchainWallet
from lnbits.core.services.blockexplorer import TXID, Explorer, explorer_client
from lnbits.core.services.wallets import get_wallet_addresses
from lnbits.settings import settings
from lnbits.task_manager import task_manager
from lnbits.utils.onchain_bindings import wally
from lnbits.utils.onchain_descriptors import address_script, script_address
from lnbits.utils.onchain_keys import (
    decrypt_mnemonic,
    encrypt_mnemonic,
    root_key,
    wallet_descriptor,
)
from lnbits.utils.onchain_transactions import (
    create_psbt,
    finalize_signed_psbt,
    psbt_fee,
    transaction_details,
)

KEY_RECORD = "onchain_key"
SCAN_SLOTS = asyncio.Semaphore(4)


class OnchainKeyStatus(BaseModel):
    configured: bool = False
    backup_confirmed: bool = False
    fingerprint: str | None = None
    source: str | None = None
    error: str | None = None


def key_path() -> Path:
    return Path(settings.lnbits_data_folder) / ".onchain_key"


def decode_key(encoded: str) -> bytes:
    try:
        key = base64.b64decode(encoded.strip(), validate=True)
        if len(key) != 32:
            raise ValueError
        return key
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "The onchain encryption key must contain 32 random bytes."
        ) from exc


def key_fingerprint(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()


def read_onchain_key() -> bytes:
    configured = settings.lnbits_onchain_master_key
    # Compatibility with Watchonly installations configured before core integration.
    encoded = (
        configured.get_secret_value()
        if configured
        else os.getenv("WATCHONLY_MASTER_KEY")
    )
    try:
        stored = decode_key(key_path().read_text()) if key_path().exists() else None
    except OSError as exc:
        raise ValueError("Cannot read the onchain encryption key file.") from exc
    if encoded:
        key = decode_key(encoded)
        if stored is not None and key != stored:
            raise ValueError(
                "The environment key does not match the saved onchain key."
            )
        return key
    if stored is None:
        raise ValueError(
            "Restore the onchain encryption key or complete setup in Payments settings."
        )
    return stored


async def onchain_key_status() -> OnchainKeyStatus:
    record = await get_settings_field(KEY_RECORD)
    pinned = (record.value or {}) if record else {}
    status = OnchainKeyStatus(fingerprint=pinned.get("fingerprint"))
    try:
        key = await run_in_threadpool(read_onchain_key)
        fingerprint = key_fingerprint(key)
        if status.fingerprint and fingerprint != status.fingerprint:
            raise ValueError(
                "The onchain encryption key does not match this database. "
                "Restore its original key."
            )
        status.fingerprint = fingerprint
        status.configured = True
        status.backup_confirmed = bool(pinned.get("backup_confirmed"))
        status.source = (
            "environment"
            if settings.lnbits_onchain_master_key or os.getenv("WATCHONLY_MASTER_KEY")
            else "file"
        )
    except ValueError as exc:
        status.error = str(exc)
    return status


async def setup_onchain_key(restore: str | None = None) -> OnchainKeyStatus:
    record = await get_settings_field(KEY_RECORD)
    pinned = (record.value or {}) if record else {}
    if restore is not None:
        key = decode_key(restore)
        if record and pinned.get("fingerprint") != key_fingerprint(key):
            raise ValueError("This recovery key does not match the database.")
        # An operator-managed environment key must agree with a restored file.
        configured = settings.lnbits_onchain_master_key
        encoded = (
            configured.get_secret_value()
            if configured
            else os.getenv("WATCHONLY_MASTER_KEY")
        )
        if encoded and decode_key(encoded) != key:
            raise ValueError(
                "This recovery key does not match the configured environment key."
            )
        await run_in_threadpool(_save_key, key)
    else:
        try:
            key = await run_in_threadpool(read_onchain_key)
        except ValueError:
            if (
                record
                or key_path().exists()
                or settings.lnbits_onchain_master_key
                or os.getenv("WATCHONLY_MASTER_KEY")
            ):
                raise ValueError(
                    "Restore the original onchain key before continuing."
                ) from None
            key = secrets.token_bytes(32)
            await run_in_threadpool(_save_key, key)
    fingerprint = key_fingerprint(key)
    if record and pinned.get("fingerprint") != fingerprint:
        raise ValueError("The onchain encryption key does not match this database.")
    if not record:
        await set_settings_field(
            KEY_RECORD, {"fingerprint": fingerprint, "backup_confirmed": False}
        )
    return await onchain_key_status()


async def confirm_onchain_key_backup(fingerprint: str) -> OnchainKeyStatus:
    status = await setup_onchain_key()
    if not status.configured or status.fingerprint != fingerprint:
        raise ValueError(
            "The backup does not match the current onchain encryption key."
        )
    await set_settings_field(
        KEY_RECORD, {"fingerprint": fingerprint, "backup_confirmed": True}
    )
    return await onchain_key_status()


async def require_onchain_payments() -> None:
    if not settings.lnbits_allow_onchain_payments:
        raise ValueError("Server onchain payments are disabled in Payments settings.")
    status = await onchain_key_status()
    if not status.configured or not status.backup_confirmed:
        raise ValueError(
            "The administrator must set up and back up the onchain "
            "encryption key in Payments settings."
        )


def encrypt_wallet_mnemonic(mnemonic: str, wallet: OnchainWallet) -> str:
    return encrypt_mnemonic(mnemonic, read_onchain_key(), _mnemonic_context(wallet))


def decrypt_wallet_mnemonic(encrypted: str, wallet: OnchainWallet) -> str:
    return decrypt_mnemonic(encrypted, read_onchain_key(), _mnemonic_context(wallet))


def sign_payment(  # noqa: C901
    wallet: OnchainWallet, encrypted: str, payment: HotWalletPayment
) -> SignedTransaction:
    data = payment.transaction.copy(deep=True)
    if not wallet.onchain_network:
        raise ValueError("Onchain wallet network is not configured")
    if not wallet.onchain_backup_confirmed:
        raise ValueError("Back up this wallet before sending")
    if not 1 <= len(data.inputs) <= 200 or not 1 <= len(data.outputs) <= 100:
        raise ValueError("Invalid number of transaction inputs or outputs")
    seen = set()
    for inp in data.inputs:
        if inp.wallet != wallet.id:
            raise ValueError("Every input must belong to the selected wallet")
        if inp.branch_index not in (0, 1) or not 0 <= inp.address_index < 2**31:
            raise ValueError("Invalid input derivation")
        if (inp.tx_id, inp.vout) in seen:
            raise ValueError("Duplicate transaction input")
        seen.add((inp.tx_id, inp.vout))
        if not 0 < inp.amount <= 2_100_000_000_000_000:
            raise ValueError("Invalid input amount")
    network = (
        wally.WALLY_NETWORK_BITCOIN_MAINNET
        if wallet.onchain_network == "Mainnet"
        else wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    for out in data.outputs:
        if not 546 <= out.amount <= 2_100_000_000_000_000:
            raise ValueError("Output is below the minimum or exceeds the supply")
        if (
            script_address(address_script(out.address), network).lower()
            != out.address.lower()
        ):
            raise ValueError("Recipient is on a different network")
        if out.wallet is not None and (
            out.wallet != wallet.id
            or out.branch_index != 1
            or out.address_index is None
            or not 0 <= out.address_index < 2**31
        ):
            raise ValueError("Invalid change output")
    # Never trust public keys supplied by the client to select a private key.
    data.masterpubs = [
        MasterPublicKey(
            id=wallet.id,
            public_key=wallet.onchain_meta.masterpub,
            fingerprint=wallet.onchain_meta.fingerprint,
        )
    ]
    psbt = create_psbt(data)
    fee = psbt_fee(psbt)
    if not 0 < fee <= payment.max_fee_sat:
        raise ValueError("Transaction fee exceeds the approved maximum")
    mnemonic = decrypt_wallet_mnemonic(encrypted, wallet)
    if (
        wallet_descriptor(mnemonic, wallet.onchain_network)[0]
        != wallet.onchain_meta.masterpub
    ):
        raise ValueError("Wallet key does not match its descriptor")
    wally.psbt_sign_bip32(psbt, root_key(mnemonic, wallet.onchain_network), 0)
    transaction = finalize_signed_psbt(psbt)
    details = transaction_details(transaction, network)
    details["fee"] = fee
    return SignedTransaction(
        tx_hex=wally.tx_to_hex(transaction, wally.WALLY_TX_FLAG_USE_WITNESS),
        tx_json=json.dumps(details),
    )


async def scan_address(client: Explorer, address: Address) -> None:
    transactions = await client.history(address.address)
    utxos = await client.utxos(address.address)
    if not isinstance(utxos, list):
        raise ValueError("Invalid UTXOs")
    outpoints = set()
    amount = 0
    for coin in utxos:
        point = (coin["txid"], coin["vout"])
        if (
            not TXID.fullmatch(coin["txid"])
            or type(coin["vout"]) is not int
            or coin["vout"] < 0
            or type(coin["value"]) is not int
            or not 0 <= coin["value"] <= 2_100_000_000_000_000
            or point in outpoints
        ):
            raise ValueError("Invalid UTXO")
        outpoints.add(point)
        amount += coin["value"]
    if amount > 2_100_000_000_000_000:
        raise ValueError("Invalid balance")
    previous = await get_address_snapshot(address.id)
    first_seen = (
        {tx["txid"]: tx.get("first_seen") for tx in previous.transactions}
        if previous
        else {}
    )
    now = int(time.time())
    for tx in transactions:
        tx["first_seen"] = first_seen.get(tx["txid"]) or now
    await update_address_snapshot(
        Snapshot(
            address_id=address.id,
            transactions=transactions,
            utxos=utxos,
            checked_at=now,
        ),
        amount,
    )


async def scan_wallet(wallet_id: str) -> None:
    async with SCAN_SLOTS:
        await _scan_with_lease(wallet_id)


def request_scan(wallet_id: str) -> None:
    name = f"onchain-sync-{wallet_id}"
    existing = task_manager.get_task(name)
    if existing and not existing.task.done():
        return
    task_manager.create_task(scan_wallet(wallet_id), name=name)


async def sync_wallets() -> None:
    # Bound provider load. API-triggered scans share the database lease.
    for wallet_id in await get_onchain_wallet_ids():
        await scan_wallet(wallet_id)


async def get_wallet_state(wallet_id: str) -> dict:
    wallet = await get_onchain_wallet(wallet_id)
    addresses = (
        await get_addresses(wallet.id) if wallet and wallet.onchain_wallet_kind else []
    )
    snapshots = await get_wallet_snapshots(wallet_id)
    status = await get_onchain_sync_status(wallet_id)
    meta = OnchainMeta.parse_raw(status.get("onchain_meta", "{}"))
    balances: dict[str, int] = {}
    for address in addresses:
        balances[address.address] = max(
            balances.get(address.address, 0), address.amount
        )
    return {
        "addresses": addresses,
        "snapshots": snapshots,
        "scanning": status.get("onchain_sync_lease_until", 0) > time.time(),
        "checked_at": meta.sync_checked_at,
        "error": meta.sync_error,
        "balance_sat": sum(balances.values()),
    }


async def get_onchain_daily_stats(wallet_id: str) -> list[dict]:
    state = await get_wallet_state(wallet_id)
    own = {a.address for a in state["addresses"]}
    transactions = {
        tx["txid"]: tx
        for snapshot in state["snapshots"]
        for tx in snapshot.transactions
    }
    days: dict[str, dict] = {}
    for tx in transactions.values():
        if not tx["status"]["confirmed"]:
            continue
        date = (
            datetime.fromtimestamp(tx["status"]["block_time"], timezone.utc)
            .date()
            .isoformat()
        )
        row = days.setdefault(
            date,
            {
                "date": date,
                "balance_in": 0,
                "balance_out": 0,
                "count_in": 0,
                "count_out": 0,
                "fee": 0,
            },
        )
        incoming = sum(
            o["value"] for o in tx["vout"] if o.get("scriptpubkey_address") in own
        )
        outgoing = sum(
            i["prevout"]["value"]
            for i in tx["vin"]
            if (i.get("prevout") or {}).get("scriptpubkey_address") in own
        )
        net = incoming - outgoing
        if net >= 0:
            row["balance_in"] += net
            row["count_in"] += 1
        else:
            row["balance_out"] += -net
            row["count_out"] += 1
            row["fee"] += tx.get("fee", 0)
    balance = 0
    result = []
    for date in sorted(days):
        row = days[date]
        balance += row["balance_in"] - row["balance_out"]
        row["balance"] = balance
        result.append(row)
    return result


def _save_key(key: bytes) -> None:
    """Publish a complete mode-0600 file without ever replacing an existing key."""
    target = key_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".onchain-key-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as file:
            file.write(base64.b64encode(key).decode() + "\n")
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if decode_key(target.read_text()) != key:
                raise ValueError(
                    "An onchain key already exists. It cannot be replaced."
                ) from None
        if os.name == "posix":
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _mnemonic_context(wallet: OnchainWallet) -> bytes:
    # Keep the original context: account ID and wallet ID were the same ID.
    return json.dumps(
        [
            "onchain-v1",
            wallet.id,
            wallet.id,
            wallet.onchain_network,
            wallet.onchain_meta.masterpub,
        ],
        separators=(",", ":"),
    ).encode()


async def _scan(wallet_id: str) -> None:
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or not wallet.onchain_wallet_kind:
        return
    async with explorer_client(
        wallet.onchain_config, wallet.onchain_network or "Mainnet"
    ) as client:
        checked = set()
        for _ in range(1000):
            addresses = await get_wallet_addresses(wallet)
            current = await get_onchain_wallet(wallet_id)
            if (
                not current
                or not current.onchain_wallet_kind
                or current.onchain_meta.masterpub != wallet.onchain_meta.masterpub
                or current.onchain_network != wallet.onchain_network
            ):
                return
            pending = [a for a in addresses if a.id not in checked]
            if not pending:
                break
            for address in pending:
                await scan_address(client, address)
                checked.add(address.id)
        else:
            raise ValueError("Address discovery limit reached")


async def _scan_with_lease(wallet_id: str) -> None:
    now = int(time.time())
    lease = now + 1800
    if not await acquire_onchain_scan_lease(wallet_id, lease, now):
        return
    error = None
    try:
        await asyncio.wait_for(_scan(wallet_id), timeout=1500)
    except asyncio.CancelledError:
        error = "Update interrupted. Retry to refresh the blockchain snapshot."
        raise
    except Exception:
        # Never return credentials, explorer URLs, raw responses or stack traces.
        error = "Blockchain update failed. Previous balances and history are retained."
    finally:
        await finish_scan(wallet_id, lease, error)
