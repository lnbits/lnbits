from typing import List, Optional

from lnbits.db import SQLITE

from . import db
from .models import Item, Shop
from .wordlists import animals


async def create_shop(*, wallet_id: str) -> int:
    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone

    result = await (method)(
        f"""
        INSERT INTO offlineshop.shops (wallet, wordlist, method)
        VALUES (?, ?, 'wordlist')
        {returning}
        """,
        (wallet_id, "\n".join(animals)),
    )
    if db.type == SQLITE:
        return result._result_proxy.lastrowid
    else:
        return result[0]  # type: ignore


async def get_shop(id: int) -> Optional[Shop]:
    row = await db.fetchone("SELECT * FROM offlineshop.shops WHERE id = ?", (id,))
    return Shop(**row) if row else None


async def get_or_create_shop_by_wallet(wallet: str) -> Optional[Shop]:
    row = await db.fetchone(
        "SELECT * FROM offlineshop.shops WHERE wallet = ?", (wallet,)
    )

    if not row:
        # create on the fly
        ls_id = await create_shop(wallet_id=wallet)
        return await get_shop(ls_id)

    return Shop(**row) if row else None


async def set_method(shop: int, method: str, wordlist: str = "") -> Optional[Shop]:
    await db.execute(
        "UPDATE offlineshop.shops SET method = ?, wordlist = ? WHERE id = ?",
        (method, wordlist, shop),
    )
    return await get_shop(shop)


async def add_item(
    shop: int,
    name: str,
    description: str,
    image: Optional[str],
    price: int,
    unit: str,
    fiat_base_multiplier: int,
) -> int:
    result = await db.execute(
        """
        INSERT INTO offlineshop.items (shop, name, description, image, price, unit, fiat_base_multiplier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (shop, name, description, image, price, unit, fiat_base_multiplier),
    )
    return result._result_proxy.lastrowid


async def update_item(
    shop: int,
    item_id: int,
    name: str,
    description: str,
    image: Optional[str],
    price: int,
    unit: str,
    fiat_base_multiplier: int,
) -> int:
    await db.execute(
        """
        UPDATE offlineshop.items SET
          name = ?,
          description = ?,
          image = ?,
          price = ?,
          unit = ?,
          fiat_base_multiplier = ?
        WHERE shop = ? AND id = ?
        """,
        (name, description, image, price, unit, fiat_base_multiplier, shop, item_id),
    )
    return item_id


async def get_item(id: int) -> Optional[Item]:
    row = await db.fetchone(
        "SELECT * FROM offlineshop.items WHERE id = ?  LIMIT 1", (id,)
    )
    return Item.from_row(row) if row else None


async def get_items(shop: int) -> List[Item]:
    rows = await db.fetchall("SELECT * FROM offlineshop.items WHERE shop = ?", (shop,))
    return [Item.from_row(row) for row in rows]


async def delete_item_from_shop(shop: int, item_id: int):
    await db.execute(
        """
        DELETE FROM offlineshop.items WHERE shop = ? AND id = ?
        """,
        (shop, item_id),
    )
