from base64 import urlsafe_b64encode
from uuid import uuid4
from typing import List, Optional, Union

from lnbits.db import open_ext_db

from .models import Products, Orders, Indexers


###Products

def create_diagonalleys_product(*, wallet_id: str, product: str,  categories: str, description: str, image: str, price: int, quantity: int) -> Products:
    with open_ext_db("diagonalley") as db:
        product_id = urlsafe_b64encode(uuid4().bytes_le).decode('utf-8')
        db.execute(
            """
            INSERT INTO products (id, wallet, product, categories, description, image, price, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (product_id, wallet_id, product, categories, description, image, price, quantity),
        )

    return get_diagonalleys_product(product_id)


def get_diagonalleys_product(product_id: str) -> Optional[Products]:
    with open_ext_db("diagonalley") as db:
        row = db.fetchone("SELECT * FROM products WHERE id = ?", (product_id,))

    return Products(**row) if row else None


def get_diagonalleys_products(wallet_ids: Union[str, List[str]]) -> List[Products]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("diagonalley") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM products WHERE wallet IN ({q})", (*wallet_ids,))

    return [Products(**row) for row in rows]


def delete_diagonalleys_product(product_id: str) -> None:
    with open_ext_db("diagonalley") as db:
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))




###Indexers

def create_diagonalleys_indexer(*, wallet_id: str, shopname: str,  indexeraddress: str, shippingzone1: str, shippingzone2: str, zone1cost: int, zone2cost: int, email: str) -> Indexers:
    with open_ext_db("diagonalley") as db:
        indexer_id = urlsafe_b64encode(uuid4().bytes_le).decode('utf-8')
        rating_key = urlsafe_b64encode(uuid4().bytes_le).decode('utf-8')
        db.execute(
            """
            INSERT INTO indexers (id, wallet, shopname, indexeraddress, ratingkey, rating, shippingzone1, shippingzone2, zone1cost, zone2cost, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (indexer_id, wallet_id, shopname, indexeraddress, rating_key, 100, shippingzone1, shippingzone2, zone1cost, zone2cost, email),
        )

    return get_diagonalleys_indexer(indexer_id)


def get_diagonalleys_indexer(indexer_id: str) -> Optional[Indexers]:
    with open_ext_db("diagonalley") as db:
        row = db.fetchone("SELECT * FROM indexers WHERE id = ?", (indexer_id,))

    return Indexers(**row) if row else None


def get_diagonalleys_indexers(wallet_ids: Union[str, List[str]]) -> List[Indexers]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("diagonalley") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM indexers WHERE wallet IN ({q})", (*wallet_ids,))

    return [Indexers(**row) for row in rows]


def delete_diagonalleys_indexer(indexer_id: str) -> None:
    with open_ext_db("diagonalley") as db:
        db.execute("DELETE FROM indexers WHERE id = ?", (indexer_id,))



###Orders
 
def create_diagonalleys_order(*, productid: str, wallet: str,  product: str, quantity: int, shippingzone: str, address: str, email: str, invoiceid: str, paid: bool, shipped: bool) -> Indexers:
    with open_ext_db("diagonalley") as db:
        order_id = urlsafe_b64encode(uuid4().bytes_le).decode('utf-8')
        db.execute(
            """
            INSERT INTO orders (id, productid, wallet, product, quantity, shippingzone, address, email, invoiceid, paid, shipped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (order_id, productid, wallet, product, quantity, shippingzone, address, email, invoiceid, False, False),
        )
    
    return get_diagonalleys_order(order_id)


def get_diagonalleys_order(order_id: str) -> Optional[Orders]:
    with open_ext_db("diagonalley") as db:
        row = db.fetchone("SELECT * FROM orders WHERE id = ?", (order_id,))

    return Orders(**row) if row else None


def get_diagonalleys_orders(wallet_ids: Union[str, List[str]]) -> List[Orders]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("diagonalley") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM orders WHERE wallet IN ({q})", (*wallet_ids,))

    return [Orders(**row) for row in rows]


def delete_diagonalleys_order(order_id: str) -> None:
    with open_ext_db("diagonalley") as db:
        db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
