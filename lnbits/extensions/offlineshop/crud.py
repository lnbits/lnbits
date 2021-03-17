from typing import List, Optional

from . import db
from .wordlists import animals
from .models import Shop, Item


async def create_shop(*, wallet_id: str) -> int:
    result = await db.execute(
        """
        INSERT INTO shops (wallet, wordlist, method)
        VALUES (?, ?, 'wordlist')
        """,
        (wallet_id, "\n".join(animals)),
    )
    return result._result_proxy.lastrowid


async def get_shop(id: int) -> Optional[Shop]:
    row = await db.fetchone("SELECT * FROM shops WHERE id = ?", (id,))
    return Shop(**dict(row)) if row else None


async def get_or_create_shop_by_wallet(wallet: str) -> Optional[Shop]:
    row = await db.fetchone("SELECT * FROM shops WHERE wallet = ?", (wallet,))

    if not row:
        # create on the fly
        ls_id = await create_shop(wallet_id=wallet)
        return await get_shop(ls_id)

    return Shop(**dict(row)) if row else None


async def set_method(shop: int, method: str, wordlist: str = "") -> Optional[Shop]:
    await db.execute(
        "UPDATE shops SET method = ?, wordlist = ? WHERE id = ?",
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
) -> int:
    result = await db.execute(
        """
        INSERT INTO items (shop, name, description, image, price, unit)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (shop, name, description, image, price, unit),
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
) -> int:
    await db.execute(
        """
        UPDATE items SET
          name = ?,
          description = ?,
          image = ?,
          price = ?,
          unit = ?
        WHERE shop = ? AND id = ?
        """,
        (name, description, image, price, unit, shop, item_id),
    )
    return item_id


async def get_item(id: int) -> Optional[Item]:
    row = await db.fetchone("SELECT * FROM items WHERE id = ?  LIMIT 1", (id,))
    return Item(**dict(row)) if row else None


async def get_items(shop: int) -> List[Item]:
    rows = await db.fetchall("SELECT * FROM items WHERE shop = ?", (shop,))
    return [Item(**dict(row)) for row in rows]


async def delete_item_from_shop(shop: int, item_id: int):
    await db.execute(
        """
        DELETE FROM items WHERE shop = ? AND id = ?
        """,
        (shop, item_id),
    )
