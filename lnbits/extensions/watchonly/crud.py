from typing import List, Optional, Union

#from lnbits.db import open_ext_db
from . import db
from .models import Wallets, Charges, Mempool

from lnbits.helpers import urlsafe_short_hash

from embit import bip32
from embit import ec
from embit.networks import NETWORKS
from embit import base58
from embit.util import hashlib
import io
from embit.util import secp256k1
from embit import hashes
from binascii import hexlify
from quart import jsonify
from embit import script
from embit import ec
from embit.networks import NETWORKS
from binascii import unhexlify, hexlify, a2b_base64, b2a_base64
import httpx


async def get_derive_address(wallet_id: str, num: int):
    
    wallet = await get_watch_wallet(wallet_id)
    k = bip32.HDKey.from_base58(str(wallet[2]))
    child = k.derive([0, num])
    address = script.p2wpkh(child).address()

    return address


##########################WALLETS####################

async def create_watch_wallet(*, user: str, masterpub: str, title: str) -> Wallets:
    wallet_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO wallets (
            id,
            user,
            masterpub,
            title,
            address_no,
            balance
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (wallet_id, user, masterpub, title, 0, 0),
    )
       # weallet_id = db.cursor.lastrowid
    address = await create_charge(wallet_id, user)
    print(address)
    return await get_watch_wallet(wallet_id)


async def get_watch_wallet(wallet_id: str) -> Wallets:
    row = await db.fetchone("SELECT * FROM wallets WHERE id = ?", (wallet_id,))
    return Wallets.from_row(row) if row else None


async def get_watch_wallets(user: str) -> List[Wallets]:
    rows = await db.fetchall("SELECT * FROM wallets WHERE user = ?", (user,))
    return [Wallets(**row) for row in rows]

async def update_watch_wallet(wallet_id: str, **kwargs) -> Optional[Wallets]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    await db.execute(f"UPDATE wallets SET {q} WHERE id = ?", (*kwargs.values(), wallet_id))
    row = await db.fetchone("SELECT * FROM wallets WHERE id = ?", (wallet_id,))
    return Wallets.from_row(row) if row else None


async def delete_watch_wallet(wallet_id: str) -> None:
    await db.execute("DELETE FROM wallets WHERE id = ?", (wallet_id,))


###############CHARGES##########################


async def create_charge(walletid: str, user: str, title: Optional[str] = None, time: Optional[int] = None, amount: Optional[int] = None) -> Charges:
    wallet = await get_watch_wallet(walletid)
    address = await get_derive_address(walletid, wallet[4] + 1)

    charge_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO charges (
            id,
            user,
            title,
            wallet,
            address,
            time_to_pay,
            amount,
            balance
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (charge_id, user, title,  walletid, address, time, amount, 0),
    )
    return await get_charge(charge_id)


async def get_charge(charge_id: str) -> Charges:
    row = await db.fetchone("SELECT * FROM charges WHERE id = ?", (charge_id,))
    return Charges.from_row(row) if row else None


async def get_charges(user: str) -> List[Charges]:
    rows = await db.fetchall("SELECT * FROM charges WHERE user = ?", (user,))
    for row in rows:
        await check_address_balance(row.address)
    rows = await db.fetchall("SELECT * FROM charges WHERE user = ?", (user,))
    return [charges.from_row(row) for row in rows]


async def delete_charge(charge_id: str) -> None:
    await db.execute("DELETE FROM charges WHERE id = ?", (charge_id,))

async def check_address_balance(address: str) -> List[Charges]:
    address_data = await get_address(address)
    mempool = await get_mempool(address_data.user)

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(mempool.endpoint + "/api/address/" + address)
    except Exception:
        pass

    amount_paid = r.json()['chain_stats']['funded_txo_sum'] - r.json()['chain_stats']['spent_txo_sum']
    print(amount_paid)

######################MEMPOOL#######################

async def create_mempool(user: str) -> Mempool:
    await db.execute(
        """
        INSERT INTO mempool (
            user, 
            endpoint
        ) 
        VALUES (?, ?)
        """,
        (user, 'https://mempool.space'),
    )
    row = await db.fetchone("SELECT * FROM mempool WHERE user = ?", (user,))
    return Mempool.from_row(row) if row else None

async def update_mempool(user: str, **kwargs) -> Optional[Mempool]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    await db.execute(f"UPDATE mempool SET {q} WHERE user = ?", (*kwargs.values(), user))
    row = await db.fetchone("SELECT * FROM mempool WHERE user = ?", (user,))
    return Mempool.from_row(row) if row else None


async def get_mempool(user: str) -> Mempool:
    row = await db.fetchone("SELECT * FROM mempool WHERE user = ?", (user,))
    return Mempool.from_row(row) if row else None
