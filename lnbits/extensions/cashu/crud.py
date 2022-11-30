import os
import random
import time
from binascii import hexlify, unhexlify
from typing import Any, List, Optional, Union

from cashu.core.base import MintKeyset
from embit import bip32, bip39, ec, script
from embit.networks import NETWORKS
from loguru import logger

from lnbits.db import Connection, Database
from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Cashu, Pegs, Promises, Proof


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
