"""Persistent blockchain snapshots. Failed scans never erase the previous snapshot."""

import asyncio
import json
import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from lnbits.core.db import db
from lnbits.task_manager import task_manager

from .crud import get_addresses, get_config, get_watch_wallets
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
        "SELECT * FROM onchain_snapshots WHERE address_id = :id",
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
    # Update balance, activity and the complete snapshot together.
    async with db.connect() as conn:
        await conn.conn.commit()
        async with conn.conn.begin():
            await conn.conn.execute(
                text("""
                INSERT INTO onchain_snapshots
                    (address_id, transactions, utxos, checked_at)
                VALUES (:id, :transactions, :utxos, :now)
                ON CONFLICT(address_id) DO UPDATE SET
                    transactions = excluded.transactions,
                    utxos = excluded.utxos, checked_at = excluded.checked_at
            """),
                {
                    "id": address.id,
                    "transactions": json.dumps(transactions),
                    "utxos": json.dumps(utxos),
                    "now": now,
                },
            )
            await conn.conn.execute(
                text("""
                UPDATE onchain_addresses SET amount = :amount,
                    has_activity = :active WHERE id = :id
            """),
                {
                    "id": address.id,
                    "amount": amount,
                    "active": bool(transactions) or address.has_activity,
                },
            )


async def _scan(wallet_id: str) -> None:
    from .views_api import api_get_addresses

    config = await get_config(wallet_id)
    async with explorer_client(config) as client:
        for account in await get_watch_wallets(wallet_id, config.network):
            checked = set()
            for _ in range(1000):
                addresses = await api_get_addresses(account.id, OnchainAuth(wallet_id))
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
    await db.execute(
        """
        INSERT INTO onchain_sync (wallet_id) VALUES (:wallet)
        ON CONFLICT(wallet_id) DO NOTHING
    """,
        {"wallet": wallet_id},
    )
    lease = now + 1800
    acquired = await db.execute(
        """
        UPDATE onchain_sync SET lease_until = :lease
        WHERE wallet_id = :wallet AND lease_until < :now
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
        await db.execute(
            """
            UPDATE onchain_sync SET lease_until = 0, error = :error,
                checked_at = CASE WHEN :error IS NULL THEN :now ELSE checked_at END
            WHERE wallet_id = :wallet AND lease_until = :lease
        """,
            {
                "wallet": wallet_id,
                "lease": lease,
                "error": error,
                "now": int(time.time()),
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
        SELECT DISTINCT w.id FROM wallets w
        JOIN onchain_accounts a ON a.wallet_id = w.id
        WHERE w.wallet_type = 'onchain' AND w.deleted = false
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
    config = await get_config(auth.wallet_id)
    accounts = await get_watch_wallets(auth.wallet_id, config.network)
    addresses = []
    for account in accounts:
        addresses.extend(await get_addresses(account.id))
    snapshots = await db.fetchall(
        """
        SELECT s.* FROM onchain_snapshots s
        JOIN onchain_addresses a ON a.id = s.address_id
        JOIN onchain_accounts c ON c.id = a.wallet
        WHERE c.wallet_id = :wallet
    """,
        {"wallet": auth.wallet_id},
        Snapshot,
    )
    status: dict = (
        await db.fetchone(
            "SELECT * FROM onchain_sync WHERE wallet_id = :wallet",
            {"wallet": auth.wallet_id},
        )
        or {}
    )
    balances: dict[str, int] = {}
    for address in addresses:
        balances[address.address] = max(
            balances.get(address.address, 0), address.amount
        )
    return {
        "addresses": addresses,
        "snapshots": snapshots,
        "scanning": status.get("lease_until", 0) > time.time(),
        "checked_at": status.get("checked_at", 0),
        "error": status.get("error"),
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
    config = await get_config(auth.wallet_id)
    try:
        async with explorer_client(config) as client:
            return await client.fees()
    except Exception as exc:
        raise HTTPException(503, "Fee estimates are unavailable") from exc


@sync_router.get("/api/v1/tx/{tx_id}/hex")
async def previous_transaction(
    tx_id: str, auth: OnchainAuth = Depends(require_onchain_read)
):
    if not TXID.fullmatch(tx_id):
        raise HTTPException(400, "Invalid transaction ID")
    config = await get_config(auth.wallet_id)
    try:
        async with explorer_client(config) as client:
            raw = await client.raw_transaction(tx_id)
            if len(raw) > 8_000_000 or not re.fullmatch(r"[0-9a-fA-F]+", raw):
                raise ValueError("Invalid transaction")
            return raw
    except Exception as exc:
        raise HTTPException(503, "Previous transaction is unavailable") from exc
