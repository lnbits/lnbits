from base64 import urlsafe_b64encode
from typing import List, Optional, Union
from uuid import uuid4

# from lnbits.db import open_ext_db
from lnbits.db import SQLITE
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import WALLET

from . import db
from .models import (
    ChatMessage,
    CreateChatMessage,
    CreateMarket,
    CreateMarketStalls,
    Market,
    OrderDetail,
    Orders,
    Products,
    ShopSettings,
    Stalls,
    Zones,
    createOrder,
    createOrderDetails,
    createProduct,
    createStalls,
    createZones,
)

###Products


async def create_shop_product(data: createProduct) -> Products:
    product_id = urlsafe_short_hash()
    await db.execute(
        f"""
        INSERT INTO shop.products (id, stall, product, categories, description, image, price, quantity)
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
    product = await get_shop_product(product_id)
    assert product, "Newly created product couldn't be retrieved"
    return product


async def update_shop_product(product_id: str, **kwargs) -> Optional[Products]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    await db.execute(
        f"UPDATE shop.products SET {q} WHERE id = ?",
        (*kwargs.values(), product_id),
    )
    row = await db.fetchone("SELECT * FROM shop.products WHERE id = ?", (product_id,))

    return Products(**row) if row else None


async def get_shop_product(product_id: str) -> Optional[Products]:
    row = await db.fetchone("SELECT * FROM shop.products WHERE id = ?", (product_id,))
    return Products(**row) if row else None


async def get_shop_products(stall_ids: Union[str, List[str]]) -> List[Products]:
    if isinstance(stall_ids, str):
        stall_ids = [stall_ids]

    # with open_ext_db("shop") as db:
    q = ",".join(["?"] * len(stall_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM shop.products WHERE stall IN ({q})
        """,
        (*stall_ids,),
    )
    return [Products(**row) for row in rows]


async def delete_shop_product(product_id: str) -> None:
    await db.execute("DELETE FROM shop.products WHERE id = ?", (product_id,))


###zones


async def create_shop_zone(user, data: createZones) -> Zones:
    zone_id = urlsafe_short_hash()
    await db.execute(
        f"""
        INSERT INTO shop.zones (
            id,
            "user",
            cost,
            countries

        )
        VALUES (?, ?, ?, ?)
        """,
        (zone_id, user, data.cost, data.countries.lower()),
    )

    zone = await get_shop_zone(zone_id)
    assert zone, "Newly created zone couldn't be retrieved"
    return zone


async def update_shop_zone(zone_id: str, **kwargs) -> Optional[Zones]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE shop.zones SET {q} WHERE id = ?",
        (*kwargs.values(), zone_id),
    )
    row = await db.fetchone("SELECT * FROM shop.zones WHERE id = ?", (zone_id,))
    return Zones(**row) if row else None


async def get_shop_zone(zone_id: str) -> Optional[Zones]:
    row = await db.fetchone("SELECT * FROM shop.zones WHERE id = ?", (zone_id,))
    return Zones(**row) if row else None


async def get_shop_zones(user: str) -> List[Zones]:
    rows = await db.fetchall('SELECT * FROM shop.zones WHERE "user" = ?', (user,))
    return [Zones(**row) for row in rows]


async def delete_shop_zone(zone_id: str) -> None:
    await db.execute("DELETE FROM shop.zones WHERE id = ?", (zone_id,))


###Stalls


async def create_shop_stall(data: createStalls) -> Stalls:
    stall_id = urlsafe_short_hash()
    await db.execute(
        f"""
        INSERT INTO shop.stalls (
            id,
            wallet,
            name,
            currency,
            publickey,
            relays,
            shippingzones
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stall_id,
            data.wallet,
            data.name,
            data.currency,
            data.publickey,
            data.relays,
            data.shippingzones,
        ),
    )

    stall = await get_shop_stall(stall_id)
    assert stall, "Newly created stall couldn't be retrieved"
    return stall


async def update_shop_stall(stall_id: str, **kwargs) -> Optional[Stalls]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE shop.stalls SET {q} WHERE id = ?",
        (*kwargs.values(), stall_id),
    )
    row = await db.fetchone("SELECT * FROM shop.stalls WHERE id = ?", (stall_id,))
    return Stalls(**row) if row else None


async def get_shop_stall(stall_id: str) -> Optional[Stalls]:
    row = await db.fetchone("SELECT * FROM shop.stalls WHERE id = ?", (stall_id,))
    return Stalls(**row) if row else None


async def get_shop_stalls(wallet_ids: Union[str, List[str]]) -> List[Stalls]:
    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM shop.stalls WHERE wallet IN ({q})", (*wallet_ids,)
    )
    return [Stalls(**row) for row in rows]


async def get_shop_stalls_by_ids(stall_ids: Union[str, List[str]]) -> List[Stalls]:
    q = ",".join(["?"] * len(stall_ids))
    rows = await db.fetchall(
        f"SELECT * FROM shop.stalls WHERE id IN ({q})", (*stall_ids,)
    )
    return [Stalls(**row) for row in rows]


async def delete_shop_stall(stall_id: str) -> None:
    await db.execute("DELETE FROM shop.stalls WHERE id = ?", (stall_id,))


###Orders


async def create_shop_order(data: createOrder, invoiceid: str):
    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone

    result = await (method)(
        f"""
            INSERT INTO shop.orders (wallet, shippingzone, address, email, total, invoiceid, paid, shipped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            {returning}
            """,
        (
            data.wallet,
            data.shippingzone,
            data.address,
            data.email,
            data.total,
            invoiceid,
            False,
            False,
        ),
    )
    if db.type == SQLITE:
        return result._result_proxy.lastrowid
    else:
        return result[0]


async def create_shop_order_details(order_id: str, data: List[createOrderDetails]):
    for item in data:
        item_id = urlsafe_short_hash()
        await db.execute(
            """
            INSERT INTO shop.order_details (id, order_id, product_id, quantity)
            VALUES (?, ?, ?, ?)
            """,
            (
                item_id,
                order_id,
                item.product_id,
                item.quantity,
            ),
        )
    order_details = await get_shop_order_details(order_id)
    return order_details


async def get_shop_order_details(order_id: str) -> List[OrderDetail]:
    rows = await db.fetchall(
        f"SELECT * FROM shop.order_details WHERE order_id = ?", (order_id,)
    )

    return [OrderDetail(**row) for row in rows]


async def get_shop_order(order_id: str) -> Optional[Orders]:
    row = await db.fetchone("SELECT * FROM shop.orders WHERE id = ?", (order_id,))
    return Orders(**row) if row else None


async def get_shop_order_invoiceid(invoice_id: str) -> Optional[Orders]:
    row = await db.fetchone(
        "SELECT * FROM shop.orders WHERE invoiceid = ?", (invoice_id,)
    )
    return Orders(**row) if row else None


async def set_shop_order_paid(payment_hash: str):
    await db.execute(
        """
            UPDATE shop.orders
            SET paid = true
            WHERE invoiceid = ?
            """,
        (payment_hash,),
    )


async def set_shop_order_pubkey(payment_hash: str, pubkey: str):
    await db.execute(
        """
            UPDATE shop.orders
            SET pubkey = ?
            WHERE invoiceid = ?
            """,
        (
            pubkey,
            payment_hash,
        ),
    )


async def update_shop_product_stock(products):

    q = "\n".join(
        [f"""WHEN id='{p.product_id}' THEN quantity - {p.quantity}""" for p in products]
    )
    v = ",".join(["?"] * len(products))

    await db.execute(
        f"""
            UPDATE shop.products
            SET quantity=(CASE
                        {q}
                        END)
            WHERE id IN ({v});
        """,
        (*[p.product_id for p in products],),
    )


async def get_shop_orders(wallet_ids: Union[str, List[str]]) -> List[Orders]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM shop.orders WHERE wallet IN ({q})", (*wallet_ids,)
    )
    #
    return [Orders(**row) for row in rows]


async def delete_shop_order(order_id: str) -> None:
    await db.execute("DELETE FROM shop.orders WHERE id = ?", (order_id,))


### Market/Marketplace


async def get_shop_markets(user: str) -> List[Market]:
    rows = await db.fetchall("SELECT * FROM shop.markets WHERE usr = ?", (user,))
    return [Market(**row) for row in rows]


async def get_shop_market(market_id: str) -> Optional[Market]:
    row = await db.fetchone("SELECT * FROM shop.markets WHERE id = ?", (market_id,))
    return Market(**row) if row else None


async def get_shop_market_stalls(market_id: str):
    rows = await db.fetchall(
        "SELECT * FROM shop.market_stalls WHERE marketid = ?", (market_id,)
    )

    ids = [row["stallid"] for row in rows]

    return await get_shop_stalls_by_ids(ids)


async def create_shop_market(data: CreateMarket):
    market_id = urlsafe_short_hash()

    await db.execute(
        """
            INSERT INTO shop.markets (id, usr, name)
            VALUES (?, ?, ?)
            """,
        (
            market_id,
            data.usr,
            data.name,
        ),
    )
    market = await get_shop_market(market_id)
    assert market, "Newly created market couldn't be retrieved"
    return market


async def create_shop_market_stalls(market_id: str, data: List[str]):
    for stallid in data:
        id = urlsafe_short_hash()

        await db.execute(
            """
            INSERT INTO shop.market_stalls (id, marketid, stallid)
            VALUES (?, ?, ?)
            """,
            (
                id,
                market_id,
                stallid,
            ),
        )
    market_stalls = await get_shop_market_stalls(market_id)
    return market_stalls


async def update_shop_market(market_id: str, name: str):
    await db.execute(
        "UPDATE shop.markets SET name = ? WHERE id = ?",
        (name, market_id),
    )
    await db.execute(
        "DELETE FROM shop.market_stalls WHERE marketid = ?",
        (market_id,),
    )

    market = await get_shop_market(market_id)
    return market


### CHAT / MESSAGES


async def create_chat_message(data: CreateChatMessage):
    await db.execute(
        """
            INSERT INTO shop.messages (msg, pubkey, id_conversation)
            VALUES (?, ?, ?)
            """,
        (
            data.msg,
            data.pubkey,
            data.room_name,
        ),
    )


async def get_shop_latest_chat_messages(room_name: str):
    rows = await db.fetchall(
        "SELECT * FROM shop.messages WHERE id_conversation = ? ORDER BY timestamp DESC LIMIT 20",
        (room_name,),
    )

    return [ChatMessage(**row) for row in rows]


async def get_shop_chat_messages(room_name: str):
    rows = await db.fetchall(
        "SELECT * FROM shop.messages WHERE id_conversation = ? ORDER BY timestamp DESC",
        (room_name,),
    )

    return [ChatMessage(**row) for row in rows]


async def get_shop_chat_by_merchant(ids: List[str]) -> List[ChatMessage]:

    q = ",".join(["?"] * len(ids))
    rows = await db.fetchall(
        f"SELECT * FROM shop.messages WHERE id_conversation IN ({q})",
        (*ids,),
    )
    return [ChatMessage(**row) for row in rows]


async def get_shop_settings(user) -> Optional[ShopSettings]:
    row = await db.fetchone("""SELECT * FROM shop.settings WHERE "user" = ?""", (user,))

    return ShopSettings(**row) if row else None


async def create_shop_settings(user: str, data):
    await db.execute(
        """
            INSERT INTO shop.settings ("user", currency, fiat_base_multiplier)
            VALUES (?, ?, ?)
        """,
        (
            user,
            data.currency,
            data.fiat_base_multiplier,
        ),
    )


async def set_shop_settings(user: str, data):
    await db.execute(
        """
            UPDATE shop.settings
            SET currency = ?, fiat_base_multiplier = ?
            WHERE "user" = ?;
        """,
        (
            data.currency,
            data.fiat_base_multiplier,
            user,
        ),
    )
