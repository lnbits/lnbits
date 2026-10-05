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
from time import monotonic

from loguru import logger
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from lnbits.core.crud.onchain import (
    create_fresh_addresses,
    get_address_at_index,
    get_address_snapshot,
    get_addresses,
    get_last_used_address_index,
    get_wallet_snapshots,
    update_address_snapshot,
)
from lnbits.core.crud.settings import get_settings_field, set_settings_field
from lnbits.core.crud.wallets import (
    acquire_onchain_scan_lease,
    get_onchain_scan_meta,
    get_onchain_sync_status,
    get_onchain_wallet,
    get_onchain_wallet_ids,
    reserve_onchain_address_index,
    update_onchain_scan_meta,
)
from lnbits.core.models.onchain import (
    Address,
    HotWalletPayment,
    MasterPublicKey,
    ScanCheckpoint,
    SignedTransaction,
    Snapshot,
)
from lnbits.core.models.wallets import OnchainMeta, OnchainWallet
from lnbits.core.services.blockexplorer import TXID, Explorer, explorer_client
from lnbits.core.services.wallets import get_wallet_addresses
from lnbits.db import Connection
from lnbits.settings import settings
from lnbits.task_manager import task_manager
from lnbits.utils.onchain import (
    address_script,
    create_psbt,
    decrypt_mnemonic,
    encrypt_mnemonic,
    finalize_signed_psbt,
    psbt_fee,
    root_key,
    script_address,
    transaction_details,
    wallet_descriptor,
    wally,
)

KEY_RECORD = "onchain_key"
SCAN_SLOTS = asyncio.Semaphore(4)
SCAN_MAX_AGE = 120
SCAN_RETRY_DELAY = 60


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
    if not wallet.onchain_meta.backup_confirmed:
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
        wallet_descriptor(
            mnemonic,
            wallet.onchain_network,
            wallet.onchain_meta.script_type or "p2wpkh",
            wallet.onchain_meta.accountPath or None,
        )[0]
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


async def scan_address(
    client: Explorer, address: Address, checkpoint: ScanCheckpoint | None = None
) -> None:
    previous = await get_address_snapshot(address.id)
    transactions = await client.history(
        address.address,
        previous=previous.transactions if previous else None,
        checkpoint=checkpoint,
    )
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


def scan_skip_reason(
    status: dict, now: float, max_age: int = SCAN_MAX_AGE
) -> str | None:
    if status.get("onchain_sync_lease_until", 0) > now:
        return "another scan holds the wallet lease"
    meta = OnchainMeta.parse_raw(status.get("onchain_meta", "{}"))
    if meta.sync_error:
        if now - meta.sync_failed_at < SCAN_RETRY_DELAY:
            return f"retry cooldown is active ({SCAN_RETRY_DELAY}s)"
    elif meta.sync_checked_at and now - meta.sync_checked_at <= max_age:
        return f"last successful scan is within {max_age}s"
    return None


def scan_due(status: dict, now: float, max_age: int = SCAN_MAX_AGE) -> bool:
    return scan_skip_reason(status, now, max_age) is None


async def is_scan_due(wallet_id: str) -> bool:
    return scan_due(await get_onchain_sync_status(wallet_id), int(time.time()))


async def scan_wallet(wallet_id: str, *, max_age: int | None = None) -> None:
    async with SCAN_SLOTS:
        await _scan_with_lease(wallet_id, max_age=max_age)


def request_scan(wallet_id: str, *, if_needed: bool = False) -> bool:
    name = f"onchain-sync-{wallet_id}"
    existing = task_manager.get_task(name)
    if existing and not existing.task.done():
        logger.info(
            f"Skipping onchain scan request for wallet {wallet_id}: "
            "scan already queued or running."
        )
        return False
    if if_needed:
        logger.info(f"Requesting onchain scan if needed for wallet {wallet_id}.")
        # A queued conditional check must not swallow a later explicit refresh.
        # Both tasks still share the database lease once they begin scanning.
        name += "-if-needed"
        existing = task_manager.get_task(name)
        if existing and not existing.task.done():
            logger.info(
                f"Skipping conditional onchain scan request for wallet {wallet_id}: "
                "check already queued or running."
            )
            return False
    task_manager.create_task(
        scan_wallet(wallet_id, max_age=SCAN_MAX_AGE if if_needed else None), name=name
    )
    return True


async def sync_wallets() -> None:
    # Bound provider load. API-triggered scans share the database lease.
    for wallet_id in await get_onchain_wallet_ids():
        await scan_wallet(wallet_id, max_age=0)


async def get_fresh_address(
    wallet_id: str, conn: Connection | None = None
) -> Address | None:
    wallet = await get_onchain_wallet(wallet_id, conn=conn)
    if not wallet or not wallet.onchain_wallet_kind:
        return None

    last_used = await get_last_used_address_index(wallet_id, conn=conn)
    index = max(wallet.onchain_address_no, last_used) + 1
    if not await reserve_onchain_address_index(
        wallet_id, index, wallet.onchain_address_no, conn=conn
    ):
        raise ValueError("Another process changed the wallet")

    address = await get_address_at_index(wallet_id, 0, index, conn=conn)
    if not address:
        await create_fresh_addresses(wallet_id, index, index + 1, conn=conn)
        address = await get_address_at_index(wallet_id, 0, index, conn=conn)

    return address


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
        "sync_due": bool(wallet and wallet.onchain_wallet_kind)
        and scan_due(status, int(time.time())),
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


async def _scan(wallet_id: str) -> ScanCheckpoint | str:
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet or not wallet.onchain_wallet_kind:
        return "Wallet was removed or is no longer configured."
    async with explorer_client(
        wallet.onchain_config, wallet.onchain_network or "Mainnet"
    ) as client:
        tip = await client.checkpoint()
        checkpoint = wallet.onchain_meta.sync_checkpoint
        # A failed scan may have written only part of a reorganised history.
        if checkpoint and (
            wallet.onchain_meta.sync_error
            or checkpoint.height > tip.height
            or await client.block_hash(checkpoint.height) != checkpoint.block_hash
        ):
            checkpoint = None
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
                return "Wallet was removed or reconfigured during the scan."
            pending = [a for a in addresses if a.id not in checked]
            if not pending:
                break
            for address in pending:
                await scan_address(client, address, checkpoint)
                checked.add(address.id)
        else:
            raise ValueError("Address discovery limit reached")
        if await client.block_hash(tip.height) != tip.block_hash:
            raise ValueError("Blockchain changed during scan")
    return tip


async def _finish_scan(
    wallet_id: str,
    lease: int,
    error: str | None,
    conn: Connection | None = None,
    *,
    checkpoint: ScanCheckpoint | None = None,
) -> bool:
    now = int(time.time())
    state: dict = {"sync_error": error, "sync_failed_at": now if error else 0}
    if error is None:
        state["sync_checked_at"] = now
        if checkpoint is not None:
            state["sync_checkpoint"] = checkpoint.dict()
    row = await get_onchain_scan_meta(wallet_id, lease, conn)
    if not row:
        return False
    meta = json.loads(row["onchain_meta"])
    meta.update(state)
    return await update_onchain_scan_meta(wallet_id, lease, meta, conn)


async def _scan_with_lease(wallet_id: str, *, max_age: int | None = None) -> None:
    now = int(time.time())
    lease = now + 1800
    expected_meta = None
    if max_age is not None:
        status = await get_onchain_sync_status(wallet_id)
        reason = scan_skip_reason(status, now, max_age)
        if reason:
            logger.info(f"Onchain scan skipped for wallet {wallet_id}: {reason}.")
            return
        expected_meta = status.get("onchain_meta")
    if not await acquire_onchain_scan_lease(
        wallet_id, lease, now, expected_meta=expected_meta
    ):
        logger.info(
            f"Onchain scan skipped for wallet {wallet_id}: "
            "scan lease was not acquired (wallet state changed or lease unavailable)."
        )
        return
    started = monotonic()
    logger.info(f"Onchain scan started for wallet {wallet_id}.")
    error = None
    checkpoint = None
    outcome = "success"
    reason = ""
    try:
        result = await asyncio.wait_for(_scan(wallet_id), timeout=1500)
        if isinstance(result, str):
            error = result
            outcome = "aborted"
            reason = error
        else:
            checkpoint = result
    except asyncio.CancelledError:
        outcome = "cancelled"
        error = "Update interrupted. Retry to refresh the blockchain snapshot."
        raise
    except Exception as exc:
        outcome = "failed"
        reason = type(exc).__name__
        # Never return credentials, explorer URLs, raw responses or stack traces.
        error = "Blockchain update failed. Previous balances and history are retained."
    finally:
        try:
            saved = await _finish_scan(wallet_id, lease, error, checkpoint=checkpoint)
            if not saved and outcome == "success":
                outcome = "aborted"
                reason = "wallet or scan lease changed before status could be saved"
        except asyncio.CancelledError:
            outcome = "cancelled"
            reason = "interrupted while saving scan status"
            raise
        except Exception as exc:
            outcome = "failed"
            reason = f"could not save scan status ({type(exc).__name__})"
            raise
        finally:
            detail = f", reason={reason.rstrip('.')}" if reason else ""
            logger.info(
                f"Onchain scan ended for wallet {wallet_id}: "
                f"outcome={outcome}, duration={monotonic() - started:.2f}s{detail}."
            )
