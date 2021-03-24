from quart import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import bleskomat_ext
from .crud import (
    create_bleskomat,
    get_bleskomat,
    get_bleskomats,
    update_bleskomat,
    delete_bleskomat,
)

from .exchange_rates import (
    exchange_rate_providers,
    fetch_fiat_exchange_rate,
    fiat_currencies,
)


@bleskomat_ext.route("/api/v1/bleskomats", methods=["GET"])
@api_check_wallet_key("admin")
async def api_bleskomats():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify(
            [bleskomat._asdict() for bleskomat in await get_bleskomats(wallet_ids)]
        ),
        HTTPStatus.OK,
    )


@bleskomat_ext.route("/api/v1/bleskomat/<bleskomat_id>", methods=["GET"])
@api_check_wallet_key("admin")
async def api_bleskomat_retrieve(bleskomat_id):
    bleskomat = await get_bleskomat(bleskomat_id)

    if not bleskomat or bleskomat.wallet != g.wallet.id:
        return (
            jsonify({"message": "Bleskomat configuration not found."}),
            HTTPStatus.NOT_FOUND,
        )

    return jsonify(bleskomat._asdict()), HTTPStatus.OK


@bleskomat_ext.route("/api/v1/bleskomat", methods=["POST"])
@bleskomat_ext.route("/api/v1/bleskomat/<bleskomat_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "name": {"type": "string", "empty": False, "required": True},
        "fiat_currency": {
            "type": "string",
            "allowed": fiat_currencies.keys(),
            "required": True,
        },
        "exchange_rate_provider": {
            "type": "string",
            "allowed": exchange_rate_providers.keys(),
            "required": True,
        },
        "fee": {"type": ["string", "float", "number", "integer"], "required": True},
    }
)
async def api_bleskomat_create_or_update(bleskomat_id=None):

    try:
        fiat_currency = g.data["fiat_currency"]
        exchange_rate_provider = g.data["exchange_rate_provider"]
        rate = await fetch_fiat_exchange_rate(
            currency=fiat_currency, provider=exchange_rate_provider
        )
    except Exception as e:
        print(e)
        return (
            jsonify(
                {
                    "message": f'Failed to fetch BTC/{fiat_currency} currency pair from "{exchange_rate_provider}"'
                }
            ),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    if bleskomat_id:
        bleskomat = await get_bleskomat(bleskomat_id)
        if not bleskomat or bleskomat.wallet != g.wallet.id:
            return (
                jsonify({"message": "Bleskomat configuration not found."}),
                HTTPStatus.NOT_FOUND,
            )
        bleskomat = await update_bleskomat(bleskomat_id, **g.data)
    else:
        bleskomat = await create_bleskomat(wallet_id=g.wallet.id, **g.data)

    return (
        jsonify(bleskomat._asdict()),
        HTTPStatus.OK if bleskomat_id else HTTPStatus.CREATED,
    )


@bleskomat_ext.route("/api/v1/bleskomat/<bleskomat_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_bleskomat_delete(bleskomat_id):
    bleskomat = await get_bleskomat(bleskomat_id)

    if not bleskomat or bleskomat.wallet != g.wallet.id:
        return (
            jsonify({"message": "Bleskomat configuration not found."}),
            HTTPStatus.NOT_FOUND,
        )

    await delete_bleskomat(bleskomat_id)

    return "", HTTPStatus.NO_CONTENT
