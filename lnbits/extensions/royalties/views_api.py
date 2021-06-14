from quart import g, jsonify, request
from http import HTTPStatus
from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from . import royalties_ext
import json
from .crud import (
    create_royalty,
    royalty
)



# account authorized api calls
# setup royalty
@royalties_ext.route("/api/v1/create", methods=["POST"])
@api_check_wallet_key('invoice')
async def royalty_db_post():
    data = await request.data
    _royalty = await create_royalty(data)
    print(_royalty)
    return _royalty, HTTPStatus.OK

@royalties_ext.route("/api/v1/r_create", methods=["POST"])
@api_check_wallet_key('invoice')
async def roy_db_get():
    inkey = dict(request.headers)['X-Api-Key']
    amount = request.args.get('amount')
    data = await royalty(inkey, int(amount))
    return data, HTTPStatus.OK

# public route to create royalty invoice
@royalties_ext.route("/api/v1/generate/<id>", methods=["GET"])
async def invoice_gen_get(id):
    invoice = 'ok'
    return invoice, HTTPStatus.OK

# public webhook to pay royalty invoice
@royalties_ext.route("/api/v1/pay/<id>", methods=["POST"])
async def invoice_pay_post(id):
    invoice = 'ok'
    return invoice, HTTPStatus.OK