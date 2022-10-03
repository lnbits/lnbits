import os

from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Cashu, Pegs, Proof, Promises

from embit import script
from embit import ec
from embit.networks import NETWORKS
from embit import bip32
from embit import bip39
from binascii import unhexlify, hexlify
import random

from loguru import logger

async def create_cashu(wallet_id: str, data: Cashu) -> Cashu:
    cashu_id = urlsafe_short_hash()

    entropy = bytes([random.getrandbits(8) for i in range(16)])
    mnemonic = bip39.mnemonic_from_bytes(entropy)
    seed = bip39.mnemonic_to_seed(mnemonic)
    root = bip32.HDKey.from_seed(seed, version=NETWORKS["main"]["xprv"])
    
    bip44_xprv = root.derive("m/44h/1h/0h")
    bip44_xpub = bip44_xprv.to_public()

    await db.execute(
        """
        INSERT INTO cashu.cashu (id, wallet, name, tickershort, fraction, maxsats, coins, prvkey, pubkey)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cashu_id,
            wallet_id,
            data.name,
            data.tickershort,
            data.fraction,
            data.maxsats,
            data.coins,
            bip44_xprv.to_base58(),
            bip44_xpub.to_base58()
        ),
    )

    cashu = await get_cashu(cashu_id)
    assert cashu, "Newly created cashu couldn't be retrieved"
    return cashu


async def update_cashu_keys(cashu_id, wif: str = None) -> Optional[Cashu]:
    entropy = bytes([random.getrandbits(8) for i in range(16)])
    mnemonic = bip39.mnemonic_from_bytes(entropy)
    seed = bip39.mnemonic_to_seed(mnemonic)
    root = bip32.HDKey.from_seed(seed, version=NETWORKS["main"]["xprv"])
    
    bip44_xprv = root.derive("m/44h/1h/0h")
    bip44_xpub = bip44_xprv.to_public()

    await db.execute("UPDATE cashu.cashu SET prv = ?, pub = ? WHERE id = ?", bip44_xprv.to_base58(), bip44_xpub.to_base58(), cashu_id)
    row = await db.fetchone("SELECT * FROM cashu.cashu WHERE id = ?", (cashu_id,))
    return Cashu(**row) if row else None


async def get_cashu(cashu_id) -> Optional[Cashu]:
    row = await db.fetchone("SELECT * FROM cashu.cashu WHERE id = ?", (cashu_id,))
    return Cashu(**row) if row else None


async def get_cashus(wallet_ids: Union[str, List[str]]) -> List[Cashu]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM cashu.cashu WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Cashu(**row) for row in rows]


async def delete_cashu(cashu_id) -> None:
    await db.execute("DELETE FROM cashu.cashu WHERE id = ?", (cashu_id,))


##########################################
###############MINT STUFF#################
##########################################

async def store_promise(
    amount: int,
    B_: str,
    C_: str,
    cashu_id
):
    promise_id = urlsafe_short_hash()

    await (conn or db).execute(
        """
        INSERT INTO cashu.promises
          (id, amount, B_b, C_b, cashu_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            promise_id,
            amount,
            str(B_),
            str(C_),
            cashu_id
        ),
    )

async def get_promises(cashu_id) -> Optional[Cashu]:
    row = await db.fetchall("SELECT * FROM cashu.promises WHERE cashu_id = ?", (promises_id,))
    return Promises(**row) if row else None

async def get_proofs_used(cashu_id):
    rows = await db.fetchall("SELECT secret from cashu.proofs_used WHERE id = ?", (cashu_id,))
    return [row[0] for row in rows]


async def invalidate_proof(
    proof: Proof,
    cashu_id
):
    invalidate_proof_id = urlsafe_short_hash()
    await (conn or db).execute(
        """
        INSERT INTO cashu.proofs_used
          (id, amount, C, secret, cashu_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            invalidate_proof_id,
            proof.amount,
            str(proof.C),
            str(proof.secret),
            cashu_id
        ),
    )