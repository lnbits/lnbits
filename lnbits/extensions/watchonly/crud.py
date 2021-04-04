from typing import List, Optional, Union

#from lnbits.db import open_ext_db
from . import db
from .models import Wallets, Addresses, Mempool

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

    ########################ADDRESSES#######################

async def get_derive_address(wallet_id: str, num: int):

    wallet = await get_watch_wallet(wallet_id)
    key = wallet[2]
    k = bip32.HDKey.from_base58(key)
    child = k.derive([0, num])
    
    if key[0:4] == "xpub":
        address = script.p2pkh(child).address()
    elif key[0:4] == "zpub":
        address = script.p2wpkh(child).address()
    elif key[0:4] == "ypub":
        address = script.p2sh(script.p2wpkh(child)).address()

    return address

async def get_fresh_address(wallet_id: str) -> Addresses:
    wallet = await get_watch_wallet(wallet_id)
    
    address = await get_derive_address(wallet_id, wallet[4] + 1)

    await update_watch_wallet(wallet_id = wallet_id, address_no = wallet[4] + 1)
    masterpub_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO addresses (
            id,
            address,
            wallet,
            amount
        )
        VALUES (?, ?, ?, ?)
        """,
        (masterpub_id, address, wallet_id, 0),
    )

    return await get_address(address)


async def get_address(address: str) -> Addresses:
    row = await db.fetchone("SELECT * FROM addresses WHERE address = ?", (address,))
    return Addresses.from_row(row) if row else None

async def get_addresses(wallet_id: str) -> List[Addresses]:
    rows = await db.fetchall("SELECT * FROM addresses WHERE wallet = ?", (wallet_id,))
    return [Addresses(**row) for row in rows]

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
