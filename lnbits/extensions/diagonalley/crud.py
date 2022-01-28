import re
from base64 import urlsafe_b64encode
from typing import List, Optional, Union
from uuid import uuid4

import httpx

# from lnbits.db import open_ext_db
from lnbits.db import SQLITE
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import WALLET

from . import db
from .models import (
    Orders,
    Products,
    Stalls,
    Zones,
    createOrder,
    createProduct,
    createStalls,
    createZones,
)

regex = re.compile(
    r"^(?:http|ftp)s?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


###Products


async def create_diagonalley_product(
    data: createProduct
) -> Products:
    # returning = "" if db.type == SQLITE else "RETURNING ID"
    # method = db.execute if db.type == SQLITE else db.fetchone
    product_id = urlsafe_short_hash()
    # with open_ext_db("diagonalley") as db:
    # result = await (method)(
    await db.execute(
        f"""
        INSERT INTO diagonalley.products (id, stall, product, categories, description, image, price, quantity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product_id,
            data.stall,
            data.product,
            data.categories,
            data.description,
            data.image,
            data.price,
            data.quantity,
        ),
    )
    product = await get_diagonalley_product(product_id)
    assert product, "Newly created product couldn't be retrieved"
    return product


async def update_diagonalley_product(product_id: str, **kwargs) -> Optional[Stalls]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    # with open_ext_db("diagonalley") as db:
    await db.execute(
        f"UPDATE diagonalley.products SET {q} WHERE id = ?",
        (*kwargs.values(), product_id),
    )
    row = await db.fetchone(
        "SELECT * FROM diagonalley.products WHERE id = ?", (product_id,)
    )

    return get_diagonalley_stall(product_id)


async def get_diagonalley_product(product_id: str) -> Optional[Products]:
    row = await db.fetchone(
        "SELECT * FROM diagonalley.products WHERE id = ?", (product_id,)
    )
    return Products(**row) if row else None


async def get_diagonalley_products(wallet_ids: Union[str, List[str]]) -> List[Products]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    # with open_ext_db("diagonalley") as db:
    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM diagonalley.products WHERE stall IN ({q})
        """,
        (*wallet_ids,),
    )
    return [Products(**row) for row in rows]


async def delete_diagonalley_product(product_id: str) -> None:
    await db.execute("DELETE FROM diagonalley.products WHERE id = ?", (product_id,))


###zones


async def create_diagonalley_zone(
    wallet,
    data: createZones
) -> Zones:
    zone_id = urlsafe_short_hash()
    await db.execute(
        f"""
        INSERT INTO diagonalley.zones (
            id,
            wallet,
            cost,
            countries

        )
        VALUES (?, ?, ?, ?)
        """,
        (zone_id, wallet, data.cost, data.countries),
    )

    zone = await get_diagonalley_zone(zone_id)
    assert zone, "Newly created zone couldn't be retrieved"
    return zone


async def update_diagonalley_zone(zone_id: str, **kwargs) -> Optional[Zones]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE diagonalley.zones SET {q} WHERE id = ?",
        (*kwargs.values(), zone_id),
    )
    row = await db.fetchone("SELECT * FROM diagonalley.zones WHERE id = ?", (zone_id,))
    return Zones(**row) if row else None


async def get_diagonalley_zone(zone_id: str) -> Optional[Zones]:
    row = await db.fetchone("SELECT * FROM diagonalley.zones WHERE id = ?", (zone_id,))
    return Zones(**row) if row else None


async def get_diagonalley_zones(wallet_ids: Union[str, List[str]]) -> List[Zones]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]
        print(wallet_ids)

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM diagonalley.zones WHERE wallet IN ({q})", (*wallet_ids,)
    )

    for r in rows:
        try:
            x = httpx.get(r["zoneaddress"] + "/" + r["ratingkey"])
            if x.status_code == 200:
                await db.execute(
                    "UPDATE diagonalley.zones SET online = ? WHERE id = ?",
                    (
                        True,
                        r["id"],
                    ),
                )
            else:
                await db.execute(
                    "UPDATE diagonalley.zones SET online = ? WHERE id = ?",
                    (
                        False,
                        r["id"],
                    ),
                )
        except:
            print("An exception occurred")
    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM diagonalley.zones WHERE wallet IN ({q})", (*wallet_ids,)
    )
    return [Zones(**row) for row in rows]


async def delete_diagonalley_zone(zone_id: str) -> None:
    await db.execute("DELETE FROM diagonalley.zones WHERE id = ?", (zone_id,))


###Stalls


async def create_diagonalley_stall(
    data: createStalls
) -> Stalls:
    stall_id = urlsafe_short_hash()
    await db.execute(
        f"""
        INSERT INTO diagonalley.stalls (
            id,
            wallet,
            name,
            publickey,
            privatekey,
            relays,
            shippingzones
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stall_id,
            data.wallet,
            data.name,
            data.publickey,
            data.privatekey,
            data.relays,
            data.shippingzones),
    )

    stall = await get_diagonalley_stall(stall_id)
    assert stall, "Newly created stall couldn't be retrieved"
    return stall


async def update_diagonalley_stall(stall_id: str, **kwargs) -> Optional[Stalls]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE diagonalley.stalls SET {q} WHERE id = ?",
        (*kwargs.values(), stall_id),
    )
    row = await db.fetchone(
        "SELECT * FROM diagonalley.stalls WHERE id = ?", (stall_id,)
    )
    return Stalls(**row) if row else None


async def get_diagonalley_stall(stall_id: str) -> Optional[Stalls]:
    roww = await db.fetchone(
        "SELECT * FROM diagonalley.stalls WHERE id = ?", (stall_id,)
    )

    try:
        x = httpx.get(roww["stalladdress"] + "/" + roww["ratingkey"])
        if x.status_code == 200:
            await db.execute(
                "UPDATE diagonalley.stalls SET online = ? WHERE id = ?",
                (
                    True,
                    stall_id,
                ),
            )
        else:
            await db.execute(
                "UPDATE diagonalley.stalls SET online = ? WHERE id = ?",
                (
                    False,
                    stall_id,
                ),
            )
    except:
        print("An exception occurred")

    # with open_ext_db("diagonalley") as db:
    row = await db.fetchone(
        "SELECT * FROM diagonalley.stalls WHERE id = ?", (stall_id,)
    )
    return Stalls(**row) if row else None


async def get_diagonalley_stalls(wallet_ids: Union[str, List[str]]) -> List[Stalls]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM diagonalley.stalls WHERE wallet IN ({q})", (*wallet_ids,)
    )

    for r in rows:
        try:
            x = httpx.get(r["stalladdress"] + "/" + r["ratingkey"])
            if x.status_code == 200:
                await db.execute(
                    "UPDATE diagonalley.stalls SET online = ? WHERE id = ?",
                    (
                        True,
                        r["id"],
                    ),
                )
            else:
                await db.execute(
                    "UPDATE diagonalley.stalls SET online = ? WHERE id = ?",
                    (
                        False,
                        r["id"],
                    ),
                )
        except:
            print("An exception occurred")
    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM diagonalley.stalls WHERE wallet IN ({q})", (*wallet_ids,)
    )
    return [Stalls(**row) for row in rows]


async def delete_diagonalley_stall(stall_id: str) -> None:
    await db.execute("DELETE FROM diagonalley.stalls WHERE id = ?", (stall_id,))


###Orders


async def create_diagonalley_order(
    data: createOrder
) -> Orders:

    order_id = urlsafe_short_hash()
    await db.execute(
        f"""
            INSERT INTO diagonalley.orders (id, productid, wallet, product,
            quantity, shippingzone, address, email, invoiceid, paid, shipped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
        (
            order_id,
            data.productid,
            data.wallet,
            data.product,
            data.quantity,
            data.shippingzone,
            data.address,
            data.email,
            data.invoiceid,
            False,
            False,
        ),
    )
    # if db.type == SQLITE:
    #     order_id = result._result_proxy.lastrowid
    # else:
    #     order_id = result[0]

    link = await get_diagonalley_order(order_id)
    assert link, "Newly created link couldn't be retrieved"
    return link


async def get_diagonalley_order(order_id: str) -> Optional[Orders]:
    row = await db.fetchone(
        "SELECT * FROM diagonalley.orders WHERE id = ?", (order_id,)
    )
    return Orders(**row) if row else None


async def get_diagonalley_orders(wallet_ids: Union[str, List[str]]) -> List[Orders]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM diagonalley.orders WHERE wallet IN ({q})", (*wallet_ids,)
    )
    #
    return [Orders(**row) for row in rows]


async def delete_diagonalley_order(order_id: str) -> None:
    await db.execute("DELETE FROM diagonalley.orders WHERE id = ?", (order_id,))
