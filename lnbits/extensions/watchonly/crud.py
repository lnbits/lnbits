from typing import List, Optional, Union

#from lnbits.db import open_ext_db
from . import db
from .models import Wallets, Payments, Addresses, Mempool

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

########################ADDRESSES#######################

def get_derive_address(wallet_id: str, num: int):
    
    wallet = get_watch_wallet(wallet_id)
    k = bip32.HDKey.from_base58(str(wallet[2]))
    child = k.derive([0, num])
    address = script.p2wpkh(child).address()

    return address

def get_fresh_address(wallet_id: str) -> Addresses:
    wallet = get_watch_wallet(wallet_id)
    
    address = get_derive_address(wallet_id, wallet[4] + 1)

    update_watch_wallet(wallet_id = wallet_id, address_no = wallet[4] + 1)
    with open_ext_db("watchonly") as db:
        db.execute(
            """
            INSERT INTO addresses (
                address,
                wallet,
                amount
            )
            VALUES (?, ?, ?)
            """,
            (address, wallet_id, 0),
        )

    return get_address(address)


def get_address(address: str) -> Addresses:
    with open_ext_db("watchonly") as db:
        row = db.fetchone("SELECT * FROM addresses WHERE address = ?", (address,))
    return Addresses.from_row(row) if row else None


def get_addresses(wallet_id: str) -> List[Addresses]:
    with open_ext_db("watchonly") as db:
        rows = db.fetchall("SELECT * FROM addresses WHERE wallet = ?", (wallet_id,))
    return [Addresses(**row) for row in rows]


##########################WALLETS####################

def create_watch_wallet(*, user: str, masterpub: str, title: str) -> Wallets:
    wallet_id = urlsafe_short_hash()
    with open_ext_db("watchonly") as db:
        db.execute(
            """
            INSERT INTO wallets (
                id,
                user,
                masterpub,
                title,
                address_no,
                amount
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wallet_id, user, masterpub, title, 0, 0),
        )
       # weallet_id = db.cursor.lastrowid
    address = get_fresh_address(wallet_id)
    return get_watch_wallet(wallet_id)


def get_watch_wallet(wallet_id: str) -> Wallets:
    with open_ext_db("watchonly") as db:
        row = db.fetchone("SELECT * FROM wallets WHERE id = ?", (wallet_id,))
    return Wallets.from_row(row) if row else None

def get_watch_wallets(user: str) -> List[Wallets]:
    with open_ext_db("watchonly") as db:
        rows = db.fetchall("SELECT * FROM wallets WHERE user = ?", (user,))
    return [Wallets(**row) for row in rows]

def update_watch_wallet(wallet_id: str, **kwargs) -> Optional[Wallets]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    with open_ext_db("watchonly") as db:
        db.execute(f"UPDATE wallets SET {q} WHERE id = ?", (*kwargs.values(), wallet_id))
        row = db.fetchone("SELECT * FROM wallets WHERE id = ?", (wallet_id,))
    return Wallets.from_row(row) if row else None


def delete_watch_wallet(wallet_id: str) -> None:
    with open_ext_db("watchonly") as db:
        db.execute("DELETE FROM wallets WHERE id = ?", (wallet_id,))


###############PAYMENTS##########################

def create_payment(*, user: str, ex_key: str, description: str, amount: int) -> Payments:

    address = get_fresh_address(ex_key)
    payment_id = urlsafe_short_hash()
    with open_ext_db("watchonly") as db:
        db.execute(
            """
            INSERT INTO payments (
                payment_id,
                user,
                ex_key,
                address,
                amount
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (payment_id, user, ex_key, address, amount),
        )
        payment_id = db.cursor.lastrowid
    return get_payment(payment_id)


def get_payment(payment_id: str) -> Payments:
    with open_ext_db("watchonly") as db:
        row = db.fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))
    return Payments.from_row(row) if row else None


def get_payments(user: str) -> List[Payments]:
    with open_ext_db("watchonly") as db:
        rows = db.fetchall("SELECT * FROM payments WHERE user IN ?", (user,))
    return [Payments.from_row(row) for row in rows]


def delete_payment(payment_id: str) -> None:
    with open_ext_db("watchonly") as db:
        db.execute("DELETE FROM payments WHERE id = ?", (payment_id,))


######################MEMPOOL#######################

def create_mempool(user: str) -> Mempool:
    with open_ext_db("watchonly") as db:
        db.execute(
            """
            INSERT INTO mempool (
                user, 
                endpoint
            ) 
            VALUES (?, ?)
            """,
            (user, 'https://mempool.space'),
        )
        row = db.fetchone("SELECT * FROM mempool WHERE user = ?", (user,))
    return Mempool.from_row(row) if row else None

def update_mempool(user: str, **kwargs) -> Optional[Mempool]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    with open_ext_db("watchonly") as db:
        db.execute(f"UPDATE mempool SET {q} WHERE user = ?", (*kwargs.values(), user))
        row = db.fetchone("SELECT * FROM mempool WHERE user = ?", (user,))
    return Mempool.from_row(row) if row else None


def get_mempool(user: str) -> Mempool:
    with open_ext_db("watchonly") as db:
        row = db.fetchone("SELECT * FROM mempool WHERE user = ?", (user,))
    return Mempool.from_row(row) if row else None
