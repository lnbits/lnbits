from quart import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from lnbits.extensions.diagonalley import diagonalley_ext
from .crud import (
    create_diagonalleys_product,
    get_diagonalleys_product,
    get_diagonalleys_products,
    delete_diagonalleys_product,
    create_diagonalleys_indexer,
    update_diagonalleys_indexer,
    get_diagonalleys_indexer,
    get_diagonalleys_indexers,
    delete_diagonalleys_indexer,
    create_diagonalleys_order,
    get_diagonalleys_order,
    get_diagonalleys_orders,
    update_diagonalleys_product,
)
from lnbits.core.services import create_invoice
from base64 import urlsafe_b64encode
from uuid import uuid4
from lnbits.db import open_ext_db

### Products


@diagonalley_ext.route("/api/v1/diagonalley/products", methods=["GET"])
@api_check_wallet_key(key_type="invoice")
async def api_diagonalley_products():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return (
        jsonify(
            [product._asdict() for product in get_diagonalleys_products(wallet_ids)]
        ),
        HTTPStatus.OK,
    )


@diagonalley_ext.route("/api/v1/diagonalley/products", methods=["POST"])
@diagonalley_ext.route("/api/v1/diagonalley/products<product_id>", methods=["PUT"])
@api_check_wallet_key(key_type="invoice")
@api_validate_post_request(
    schema={
        "product": {"type": "string", "empty": False, "required": True},
        "categories": {"type": "string", "empty": False, "required": True},
        "description": {"type": "string", "empty": False, "required": True},
        "image": {"type": "string", "empty": False, "required": True},
        "price": {"type": "integer", "min": 0, "required": True},
        "quantity": {"type": "integer", "min": 0, "required": True},
    }
)
async def api_diagonalley_product_create(product_id=None):

    if product_id:
        product = get_diagonalleys_indexer(product_id)

        if not product:
            return (
                jsonify({"message": "Withdraw product does not exist."}),
                HTTPStatus.NOT_FOUND,
            )

        if product.wallet != g.wallet.id:
            return (
                jsonify({"message": "Not your withdraw product."}),
                HTTPStatus.FORBIDDEN,
            )

        product = update_diagonalleys_product(product_id, **g.data)
    else:
        product = create_diagonalleys_product(wallet_id=g.wallet.id, **g.data)

    return (
        jsonify(product._asdict()),
        HTTPStatus.OK if product_id else HTTPStatus.CREATED,
    )


@diagonalley_ext.route("/api/v1/diagonalley/products/<product_id>", methods=["DELETE"])
@api_check_wallet_key(key_type="invoice")
async def api_diagonalley_products_delete(product_id):
    product = get_diagonalleys_product(product_id)

    if not product:
        return jsonify({"message": "Product does not exist."}), HTTPStatus.NOT_FOUND

    if product.wallet != g.wallet.id:
        return jsonify({"message": "Not your Diagon Alley."}), HTTPStatus.FORBIDDEN

    delete_diagonalleys_product(product_id)

    return "", HTTPStatus.NO_CONTENT


###Indexers


@diagonalley_ext.route("/api/v1/diagonalley/indexers", methods=["GET"])
@api_check_wallet_key(key_type="invoice")
async def api_diagonalley_indexers():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return (
        jsonify(
            [indexer._asdict() for indexer in get_diagonalleys_indexers(wallet_ids)]
        ),
        HTTPStatus.OK,
    )


@diagonalley_ext.route("/api/v1/diagonalley/indexers", methods=["POST"])
@diagonalley_ext.route("/api/v1/diagonalley/indexers<indexer_id>", methods=["PUT"])
@api_check_wallet_key(key_type="invoice")
@api_validate_post_request(
    schema={
        "shopname": {"type": "string", "empty": False, "required": True},
        "indexeraddress": {"type": "string", "empty": False, "required": True},
        "shippingzone1": {"type": "string", "empty": False, "required": True},
        "shippingzone2": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": False, "required": True},
        "zone1cost": {"type": "integer", "min": 0, "required": True},
        "zone2cost": {"type": "integer", "min": 0, "required": True},
    }
)
async def api_diagonalley_indexer_create(indexer_id=None):

    if indexer_id:
        indexer = get_diagonalleys_indexer(indexer_id)

        if not indexer:
            return (
                jsonify({"message": "Withdraw indexer does not exist."}),
                HTTPStatus.NOT_FOUND,
            )

        if indexer.wallet != g.wallet.id:
            return (
                jsonify({"message": "Not your withdraw indexer."}),
                HTTPStatus.FORBIDDEN,
            )

        indexer = update_diagonalleys_indexer(indexer_id, **g.data)
    else:
        indexer = create_diagonalleys_indexer(wallet_id=g.wallet.id, **g.data)

    return (
        jsonify(indexer._asdict()),
        HTTPStatus.OK if indexer_id else HTTPStatus.CREATED,
    )


@diagonalley_ext.route("/api/v1/diagonalley/indexers/<indexer_id>", methods=["DELETE"])
@api_check_wallet_key(key_type="invoice")
async def api_diagonalley_indexer_delete(indexer_id):
    indexer = get_diagonalleys_indexer(indexer_id)

    if not indexer:
        return jsonify({"message": "Indexer does not exist."}), HTTPStatus.NOT_FOUND

    if indexer.wallet != g.wallet.id:
        return jsonify({"message": "Not your Indexer."}), HTTPStatus.FORBIDDEN

    delete_diagonalleys_indexer(indexer_id)

    return "", HTTPStatus.NO_CONTENT


###Orders


@diagonalley_ext.route("/api/v1/diagonalley/orders", methods=["GET"])
@api_check_wallet_key(key_type="invoice")
async def api_diagonalley_orders():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return (
        jsonify([order._asdict() for order in get_diagonalleys_orders(wallet_ids)]),
        HTTPStatus.OK,
    )


@diagonalley_ext.route("/api/v1/diagonalley/orders", methods=["POST"])
@api_check_wallet_key(key_type="invoice")
@api_validate_post_request(
    schema={
        "id": {"type": "string", "empty": False, "required": True},
        "address": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": False, "required": True},
        "quantity": {"type": "integer", "empty": False, "required": True},
        "shippingzone": {"type": "integer", "empty": False, "required": True},
    }
)
async def api_diagonalley_order_create():
    order = create_diagonalleys_order(wallet_id=g.wallet.id, **g.data)
    return jsonify(order._asdict()), HTTPStatus.CREATED


@diagonalley_ext.route("/api/v1/diagonalley/orders/<order_id>", methods=["DELETE"])
@api_check_wallet_key(key_type="invoice")
async def api_diagonalley_order_delete(order_id):
    order = get_diagonalleys_order(order_id)

    if not order:
        return jsonify({"message": "Indexer does not exist."}), HTTPStatus.NOT_FOUND

    if order.wallet != g.wallet.id:
        return jsonify({"message": "Not your Indexer."}), HTTPStatus.FORBIDDEN

    delete_diagonalleys_indexer(order_id)

    return "", HTTPStatus.NO_CONTENT


@diagonalley_ext.route("/api/v1/diagonalley/orders/paid/<order_id>", methods=["GET"])
@api_check_wallet_key(key_type="invoice")
async def api_diagonalleys_order_paid(order_id):
    with open_ext_db("diagonalley") as db:
        db.execute(
            "UPDATE diagonalley.orders SET paid = ? WHERE id = ?",
            (
                True,
                order_id,
            ),
        )
    return "", HTTPStatus.OK


@diagonalley_ext.route("/api/v1/diagonalley/orders/shipped/<order_id>", methods=["GET"])
@api_check_wallet_key(key_type="invoice")
async def api_diagonalleys_order_shipped(order_id):
    with open_ext_db("diagonalley") as db:
        db.execute(
            "UPDATE diagonalley.orders SET shipped = ? WHERE id = ?",
            (
                True,
                order_id,
            ),
        )
        order = db.fetchone(
            "SELECT * FROM diagonalley.orders WHERE id = ?", (order_id,)
        )

    return (
        jsonify(
            [order._asdict() for order in get_diagonalleys_orders(order["wallet"])]
        ),
        HTTPStatus.OK,
    )


###List products based on indexer id


@diagonalley_ext.route(
    "/api/v1/diagonalley/stall/products/<indexer_id>", methods=["GET"]
)
async def api_diagonalleys_stall_products(indexer_id):
    with open_ext_db("diagonalley") as db:
        rows = db.fetchone(
            "SELECT * FROM diagonalley.indexers WHERE id = ?", (indexer_id,)
        )
        print(rows[1])
        if not rows:
            return jsonify({"message": "Indexer does not exist."}), HTTPStatus.NOT_FOUND

        products = db.fetchone(
            "SELECT * FROM diagonalley.products WHERE wallet = ?", (rows[1],)
        )
        if not products:
            return jsonify({"message": "No products"}), HTTPStatus.NOT_FOUND

    return (
        jsonify(
            [products._asdict() for products in get_diagonalleys_products(rows[1])]
        ),
        HTTPStatus.OK,
    )


###Check a product has been shipped


@diagonalley_ext.route(
    "/api/v1/diagonalley/stall/checkshipped/<checking_id>", methods=["GET"]
)
async def api_diagonalleys_stall_checkshipped(checking_id):
    with open_ext_db("diagonalley") as db:
        rows = db.fetchone(
            "SELECT * FROM diagonalley.orders WHERE invoiceid = ?", (checking_id,)
        )

    return jsonify({"shipped": rows["shipped"]}), HTTPStatus.OK


###Place order


@diagonalley_ext.route("/api/v1/diagonalley/stall/order/<indexer_id>", methods=["POST"])
@api_validate_post_request(
    schema={
        "id": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": False, "required": True},
        "address": {"type": "string", "empty": False, "required": True},
        "quantity": {"type": "integer", "empty": False, "required": True},
        "shippingzone": {"type": "integer", "empty": False, "required": True},
    }
)
async def api_diagonalley_stall_order(indexer_id):
    product = get_diagonalleys_product(g.data["id"])
    shipping = get_diagonalleys_indexer(indexer_id)

    if g.data["shippingzone"] == 1:
        shippingcost = shipping.zone1cost
    else:
        shippingcost = shipping.zone2cost

    checking_id, payment_request = create_invoice(
        wallet_id=product.wallet,
        amount=shippingcost + (g.data["quantity"] * product.price),
        memo=g.data["id"],
    )
    selling_id = urlsafe_b64encode(uuid4().bytes_le).decode("utf-8")
    with open_ext_db("diagonalley") as db:
        db.execute(
            """
            INSERT INTO diagonalley.orders (id, productid, wallet, product, quantity, shippingzone, address, email, invoiceid, paid, shipped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                selling_id,
                g.data["id"],
                product.wallet,
                product.product,
                g.data["quantity"],
                g.data["shippingzone"],
                g.data["address"],
                g.data["email"],
                checking_id,
                False,
                False,
            ),
        )
    return (
        jsonify({"checking_id": checking_id, "payment_request": payment_request}),
        HTTPStatus.OK,
    )
