from typing import Union
from fastapi.param_functions import Query
from pydantic import BaseModel
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


@bleskomat_ext.get("/api/v1/bleskomats")
@api_check_wallet_key("admin")
async def api_bleskomats():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
            [bleskomat._asdict() for bleskomat in await get_bleskomats(wallet_ids)],
        HTTPStatus.OK,
    )


@bleskomat_ext.get("/api/v1/bleskomat/<bleskomat_id>")
@api_check_wallet_key("admin")
async def api_bleskomat_retrieve(bleskomat_id):
    bleskomat = await get_bleskomat(bleskomat_id)

    if not bleskomat or bleskomat.wallet != g.wallet.id:
        return (
            jsonify({"message": "Bleskomat configuration not found."}),
            HTTPStatus.NOT_FOUND,
        )

    return jsonify(bleskomat._asdict()), HTTPStatus.OK


class CreateData(BaseModel):
    name:  str
    fiat_currency:  str = "EUR" # TODO: fix this
    exchange_rate_provider:  str = "bitfinex"
    fee: Union[str, int, float] = Query(...)

@bleskomat_ext.post("/api/v1/bleskomat")
@bleskomat_ext.put("/api/v1/bleskomat/<bleskomat_id>")
@api_check_wallet_key("admin")
async def api_bleskomat_create_or_update(data: CreateData, bleskomat_id=None):
    try:
        fiat_currency = data.fiat_currency
        exchange_rate_provider = data.exchange_rate_provider
        await fetch_fiat_exchange_rate(
            currency=fiat_currency, provider=exchange_rate_provider
        )
    except Exception as e:
        print(e)
        return (
                {
                    "message": f'Failed to fetch BTC/{fiat_currency} currency pair from "{exchange_rate_provider}"'
                },
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    if bleskomat_id:
        bleskomat = await get_bleskomat(bleskomat_id)
        if not bleskomat or bleskomat.wallet != g.wallet.id:
            return (
                jsonify({"message": "Bleskomat configuration not found."}),
                HTTPStatus.NOT_FOUND,
            )
        bleskomat = await update_bleskomat(bleskomat_id, **data)
    else:
        bleskomat = await create_bleskomat(wallet_id=g.wallet.id, **data)

    return (
        bleskomat._asdict(),
        HTTPStatus.OK if bleskomat_id else HTTPStatus.CREATED,
    )


@bleskomat_ext.delete("/api/v1/bleskomat/<bleskomat_id>")
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
