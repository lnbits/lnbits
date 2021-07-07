import secrets
import time
from uuid import uuid4
from typing import List, Optional, Union
from . import db
from .models import Bleskomat, BleskomatLnurl
from .helpers import generate_bleskomat_lnurl_hash


async def create_bleskomat(
    *,
    wallet_id: str,
    name: str,
    fiat_currency: str,
    exchange_rate_provider: str,
    fee: str,
) -> Bleskomat:
    bleskomat_id = uuid4().hex
    api_key_id = secrets.token_hex(8)
    api_key_secret = secrets.token_hex(32)
    api_key_encoding = "hex"
    await db.execute(
        """
        INSERT INTO bleskomat.bleskomats (id, wallet, api_key_id, api_key_secret, api_key_encoding, name, fiat_currency, exchange_rate_provider, fee)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bleskomat_id,
            wallet_id,
            api_key_id,
            api_key_secret,
            api_key_encoding,
            name,
            fiat_currency,
            exchange_rate_provider,
            fee,
        ),
    )
    bleskomat = await get_bleskomat(bleskomat_id)
    assert bleskomat, "Newly created bleskomat couldn't be retrieved"
    return bleskomat


async def get_bleskomat(bleskomat_id: str) -> Optional[Bleskomat]:
    row = await db.fetchone(
        "SELECT * FROM bleskomat.bleskomats WHERE id = ?", (bleskomat_id,)
    )
    return Bleskomat(**row) if row else None


async def get_bleskomat_by_api_key_id(api_key_id: str) -> Optional[Bleskomat]:
    row = await db.fetchone(
        "SELECT * FROM bleskomat.bleskomats WHERE api_key_id = ?", (api_key_id,)
    )
    return Bleskomat(**row) if row else None


async def get_bleskomats(wallet_ids: Union[str, List[str]]) -> List[Bleskomat]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]
    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM bleskomat.bleskomats WHERE wallet IN ({q})", (*wallet_ids,)
    )
    return [Bleskomat(**row) for row in rows]


async def update_bleskomat(bleskomat_id: str, **kwargs) -> Optional[Bleskomat]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE bleskomat.bleskomats SET {q} WHERE id = ?",
        (*kwargs.values(), bleskomat_id),
    )
    row = await db.fetchone(
        "SELECT * FROM bleskomat.bleskomats WHERE id = ?", (bleskomat_id,)
    )
    return Bleskomat(**row) if row else None


async def delete_bleskomat(bleskomat_id: str) -> None:
    await db.execute("DELETE FROM bleskomat.bleskomats WHERE id = ?", (bleskomat_id,))


async def create_bleskomat_lnurl(
    *, bleskomat: Bleskomat, secret: str, tag: str, params: str, uses: int = 1
) -> BleskomatLnurl:
    bleskomat_lnurl_id = uuid4().hex
    hash = generate_bleskomat_lnurl_hash(secret)
    now = int(time.time())
    await db.execute(
        """
        INSERT INTO bleskomat.bleskomat_lnurls (id, bleskomat, wallet, hash, tag, params, api_key_id, initial_uses, remaining_uses, created_time, updated_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bleskomat_lnurl_id,
            bleskomat.id,
            bleskomat.wallet,
            hash,
            tag,
            params,
            bleskomat.api_key_id,
            uses,
            uses,
            now,
            now,
        ),
    )
    bleskomat_lnurl = await get_bleskomat_lnurl(secret)
    assert bleskomat_lnurl, "Newly created bleskomat LNURL couldn't be retrieved"
    return bleskomat_lnurl


async def get_bleskomat_lnurl(secret: str) -> Optional[BleskomatLnurl]:
    hash = generate_bleskomat_lnurl_hash(secret)
    row = await db.fetchone(
        "SELECT * FROM bleskomat.bleskomat_lnurls WHERE hash = ?", (hash,)
    )
    return BleskomatLnurl(**row) if row else None
