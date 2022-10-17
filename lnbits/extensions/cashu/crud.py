import os
import random
import time
from binascii import hexlify, unhexlify
from typing import List, Optional, Union, Any

from embit import bip32, bip39, ec, script
from embit.networks import NETWORKS
from loguru import logger

from lnbits.helpers import urlsafe_short_hash

from . import db

from .models import Cashu, Invoice, Pegs, Promises, Proof

from cashu.core.base import MintKeyset
from lnbits.db import Database, Connection


async def create_cashu(
    cashu_id: str, keyset_id: str, wallet_id: str, data: Cashu
) -> Cashu:

    await db.execute(
        """
        INSERT INTO cashu.cashu (id, wallet, name, tickershort, fraction, maxsats, coins, keyset_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cashu_id,
            wallet_id,
            data.name,
            data.tickershort,
            data.fraction,
            data.maxsats,
            data.coins,
            keyset_id,
        ),
    )

    cashu = await get_cashu(cashu_id)
    assert cashu, "Newly created cashu couldn't be retrieved"
    return cashu


# async def update_cashu_keys(cashu_id, wif: str = None) -> Optional[Cashu]:
#     entropy = bytes([random.getrandbits(8) for i in range(16)])
#     mnemonic = bip39.mnemonic_from_bytes(entropy)
#     seed = bip39.mnemonic_to_seed(mnemonic)
#     root = bip32.HDKey.from_seed(seed, version=NETWORKS["main"]["xprv"])

#     bip44_xprv = root.derive("m/44h/1h/0h")
#     bip44_xpub = bip44_xprv.to_public()

#     await db.execute(
#         "UPDATE cashu.cashu SET prv = ?, pub = ? WHERE id = ?",
#         bip44_xprv.to_base58(),
#         bip44_xpub.to_base58(),
#         cashu_id,
#     )
#     row = await db.fetchone("SELECT * FROM cashu.cashu WHERE id = ?", (cashu_id,))
#     return Cashu(**row) if row else None


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


# ##########################################
# ###############MINT STUFF#################
# ##########################################

class LedgerCrud:
    """
    Database interface for Cashu mint.

    This class needs to be overloaded by any app that imports the Cashu mint.
    """

    async def get_keyset(*args, **kwags):
        return await get_keyset(*args, **kwags)

    async def get_lightning_invoice(*args, **kwags):
        return await get_lightning_invoice(*args, **kwags)

    async def get_proofs_used(*args, **kwags):
        return await get_proofs_used(*args, **kwags)

    async def invalidate_proof(*args, **kwags):
        return await invalidate_proof(*args, **kwags)

    async def store_keyset(*args, **kwags):
        return await store_keyset(*args, **kwags)

    async def store_lightning_invoice(*args, **kwags):
        return await store_lightning_invoice(*args, **kwags)

    async def store_promise(*args, **kwags):
        return await store_promise(*args, **kwags)

    async def update_lightning_invoice(*args, **kwags):
        return await update_lightning_invoice(*args, **kwags)



async def store_promises(
    amounts: List[int], B_s: List[str], C_s: List[str], cashu_id: str
):
    for amount, B_, C_ in zip(amounts, B_s, C_s):
        await store_promise(amount, B_, C_, cashu_id)


async def store_promise(amount: int, B_: str, C_: str, cashu_id: str):
    promise_id = urlsafe_short_hash()

    await db.execute(
        """
        INSERT INTO cashu.promises
          (id, amount, B_b, C_b, cashu_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (promise_id, amount, str(B_), str(C_), cashu_id),
    )


# async def get_promises(cashu_id) -> Optional[Cashu]:
#     row = await db.fetchall(
#         "SELECT * FROM cashu.promises WHERE cashu_id = ?", (cashu_id,)
#     )
#     return Promises(**row) if row else None


async def get_proofs_used(
    db: Database,
    conn: Optional[Connection] = None,
):

    rows = await (conn or db).fetchall(
        """
        SELECT secret from cashu.proofs_used
        """
    )
    return [row[0] for row in rows]


async def invalidate_proof(cashu_id: str, proof: Proof):
    invalidate_proof_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO cashu.proofs_used
          (id, amount, C, secret, cashu_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (invalidate_proof_id, proof.amount, str(proof.C), str(proof.secret), cashu_id),
    )


# ########################################
# ############ MINT INVOICES #############
# ########################################


async def store_lightning_invoice(cashu_id: str, invoice: Invoice):
    await db.execute(
        """
        INSERT INTO cashu.invoices
          (cashu_id, amount, pr, hash, issued)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            cashu_id,
            invoice.amount,
            invoice.pr,
            invoice.hash,
            invoice.issued,
        ),
    )


async def get_lightning_invoice(cashu_id: str, hash: str):
    row = await db.fetchone(
        """
        SELECT * from cashu.invoices
        WHERE cashu_id =? AND hash = ?
        """,
        (
            cashu_id,
            hash,
        ),
    )
    return Invoice.from_row(row)


async def update_lightning_invoice(cashu_id: str, hash: str, issued: bool):
    await db.execute(
        "UPDATE cashu.invoices SET issued = ? WHERE cashu_id = ? AND hash = ?",
        (
            issued,
            cashu_id,
            hash,
        ),
    )


##############################
######### KEYSETS ############
##############################


async def store_keyset(
    keyset: MintKeyset,
    db: Database = None,
    conn: Optional[Connection] = None,
):

    await (conn or db).execute(  # type: ignore
        """
        INSERT INTO cashu.keysets
          (id, derivation_path, valid_from, valid_to, first_seen, active, version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            keyset.id,
            keyset.derivation_path,
            keyset.valid_from or db.timestamp_now,
            keyset.valid_to or db.timestamp_now,
            keyset.first_seen or db.timestamp_now,
            True,
            keyset.version,
        ),
    )


async def get_keyset(
    id: str = None,
    derivation_path: str = "",
    db: Database = None,
    conn: Optional[Connection] = None,
):
    clauses = []
    values: List[Any] = []
    clauses.append("active = ?")
    values.append(True)
    if id:
        clauses.append("id = ?")
        values.append(id)
    if derivation_path:
        clauses.append("derivation_path = ?")
        values.append(derivation_path)
    where = ""
    if clauses:
        where = f"WHERE {' AND '.join(clauses)}"

    rows = await (conn or db).fetchall(  # type: ignore
        f"""
        SELECT * from cashu.keysets
        {where}
        """,
        tuple(values),
    )
    return [MintKeyset.from_row(row) for row in rows]
