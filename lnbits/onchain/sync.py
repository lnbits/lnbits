"""Persistent blockchain snapshots. Failed scans never erase the previous snapshot."""

import asyncio
import json
import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from lnbits.core.crud.onchain import get_addresses
from lnbits.core.crud.wallets_onchain import (
    get_onchain_wallet,
    get_onchain_wallets,
)
from lnbits.core.db import db
from lnbits.core.models.wallets import OnchainMeta
from lnbits.core.services.wallets_onchain import get_wallet_addresses
from lnbits.db import SQLITE
from lnbits.task_manager import task_manager

from .decorators import OnchainAuth, require_onchain_admin, require_onchain_read
from .explorer import TXID, Explorer, explorer_client

sync_router = APIRouter()
SCAN_SLOTS = asyncio.Semaphore(4)


class Snapshot(BaseModel):
    address_id: str
    transactions: list[dict]
    utxos: list[dict]
    checked_at: int


async def scan_address(client: Explorer, address) -> None:
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
    previous = await db.fetchone(
        """SELECT id AS address_id, transactions, utxos,
            snapshot_checked_at AS checked_at
        FROM onchain_addresses WHERE id = :id""",
        {"id": address.id},
        Snapshot,
    )
    first_seen = (
        {tx["txid"]: tx.get("first_seen") for tx in previous.transactions}
        if previous
        else {}
    )
    now = int(time.time())
    for tx in transactions:
        tx["first_seen"] = first_seen.get(tx["txid"]) or now
    # One write keeps the snapshot and balance consistent, and cannot recreate
    # an address removed while the explorer request was in flight.
    async with db.connect() as conn:
        await conn.conn.execute(
            text("""
                UPDATE onchain_addresses SET transactions = :transactions,
                    utxos = :utxos, snapshot_checked_at = :now, amount = :amount,
                    has_activity = has_activity OR :active WHERE id = :id
            """),
            {
                "id": address.id,
                "transactions": json.dumps(transactions),
                "utxos": json.dumps(utxos),
                "now": now,
                "amount": amount,
                "active": bool(transactions),
            },
        )
        await conn.conn.commit()


async def _scan(wallet_id: str) -> None:
    wallet = await get_onchain_wallet(wallet_id)
    if not wallet:
        return
    async with explorer_client(
        wallet.onchain_config, wallet.onchain_network or "Mainnet"
    ) as client:
        checked = set()
        for _ in range(1000):
            addresses = await get_wallet_addresses(wallet.id, wallet_id)
            current = await get_onchain_wallet(wallet_id)
            if (
                not current
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


async def scan_wallet(wallet_id: str) -> None:
    async with SCAN_SLOTS:
        await _scan_with_lease(wallet_id)


async def _scan_with_lease(wallet_id: str) -> None:
    now = int(time.time())
    lease = now + 1800
    acquired = await db.execute(
        """
        UPDATE wallets SET onchain_sync_lease_until = :lease
        WHERE id = :wallet AND onchain_sync_lease_until < :now
            AND wallet_type = 'onchain' AND deleted = false
            AND onchain_wallet_kind IS NOT NULL
    """,
        {"wallet": wallet_id, "lease": lease, "now": now},
    )
    if acquired.rowcount != 1:
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


async def finish_scan(wallet_id: str, lease: int, error: str | None) -> None:
    now = int(time.time())
    state: dict = {"sync_error": error}
    if error is None:
        state["sync_checked_at"] = now
    # Merge only scanner-owned keys in the same conditional update that releases
    # the lease. Other metadata and newer scan leases must remain untouched.
    if db.type == SQLITE:
        expression = "json_set(onchain_meta, '$.sync_error', :error)"
        if error is None:
            expression = (
                "json_set(onchain_meta, '$.sync_error', :error, "
                "'$.sync_checked_at', :now)"
            )
    else:
        expression = (
            "CAST(CAST(onchain_meta AS JSONB) || CAST(:state AS JSONB) AS TEXT)"
        )
    await db.execute(
        f"""
        UPDATE wallets SET onchain_sync_lease_until = 0,
            onchain_meta = {expression}
        WHERE id = :wallet AND wallet_type = 'onchain'
            AND onchain_wallet_kind IS NOT NULL AND onchain_sync_lease_until = :lease
        """,  # noqa: S608
        {
            "wallet": wallet_id,
            "lease": lease,
            "error": error,
            "now": now,
            "state": json.dumps(state),
        },
    )


def request_scan(wallet_id: str) -> None:
    name = f"onchain-sync-{wallet_id}"
    existing = task_manager.get_task(name)
    if existing and not existing.task.done():
        return
    task_manager.create_task(scan_wallet(wallet_id), name=name)


async def sync_wallets() -> None:
    rows: list[dict] = await db.fetchall("""
        SELECT id FROM wallets WHERE wallet_type = 'onchain' AND deleted = false
            AND onchain_wallet_kind IS NOT NULL
    """)
    # Bound provider load. API-triggered scans share the database lease.
    for row in rows:
        await scan_wallet(row["id"])


@sync_router.post("/api/v1/sync", status_code=202)
async def start_sync(auth: OnchainAuth = Depends(require_onchain_admin)):
    request_scan(auth.wallet_id)
    return {"scheduled": True}


@sync_router.get("/api/v1/state")
async def wallet_state(auth: OnchainAuth = Depends(require_onchain_read)):
    accounts = await get_onchain_wallets(auth.wallet_id)
    addresses = []
    for account in accounts:
        addresses.extend(await get_addresses(account.id))
    snapshots = await db.fetchall(
        """
        SELECT id AS address_id, transactions, utxos, snapshot_checked_at AS checked_at
        FROM onchain_addresses WHERE wallet = :wallet AND snapshot_checked_at > 0
    """,
        {"wallet": auth.wallet_id},
        Snapshot,
    )
    status: dict = (
        await db.fetchone(
            """SELECT onchain_meta, onchain_sync_lease_until FROM wallets
            WHERE id = :wallet AND wallet_type = 'onchain'""",
            {"wallet": auth.wallet_id},
        )
        or {}
    )
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


@sync_router.get("/api/v1/stats/daily")
async def daily_stats(auth: OnchainAuth = Depends(require_onchain_read)):
    state = await wallet_state(auth)
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


@sync_router.get("/api/v1/fees")
async def fee_estimates(auth: OnchainAuth = Depends(require_onchain_read)):
    wallet = await get_onchain_wallet(auth.wallet_id, include_unconfigured=True)
    if not wallet:
        raise HTTPException(404, "Onchain wallet not found")
    try:
        async with explorer_client(
            wallet.onchain_config, wallet.onchain_network or "Mainnet"
        ) as client:
            return await client.fees()
    except Exception as exc:
        raise HTTPException(503, "Fee estimates are unavailable") from exc


@sync_router.get("/api/v1/tx/{tx_id}/hex")
async def previous_transaction(
    tx_id: str, auth: OnchainAuth = Depends(require_onchain_read)
):
    if not TXID.fullmatch(tx_id):
        raise HTTPException(400, "Invalid transaction ID")
    wallet = await get_onchain_wallet(auth.wallet_id, include_unconfigured=True)
    if not wallet:
        raise HTTPException(404, "Onchain wallet not found")
    try:
        async with explorer_client(
            wallet.onchain_config, wallet.onchain_network or "Mainnet"
        ) as client:
            raw = await client.raw_transaction(tx_id)
            if len(raw) > 8_000_000 or not re.fullmatch(r"[0-9a-fA-F]+", raw):
                raise ValueError("Invalid transaction")
            return raw
    except Exception as exc:
        raise HTTPException(503, "Previous transaction is unavailable") from exc
