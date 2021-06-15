from quart import g, jsonify, request
from http import HTTPStatus
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.helpers import urlsafe_short_hash
from . import royalties_ext
import json
from .crud import (
    create_royalty,
    royalty,
    generate_royalty,
    pay_royalty,
    create_royalty_account,
    get_royalty_account,
    delete_royalty_account
)



# account authorized api calls
# setup royalty
@royalties_ext.route("/api/v1/create", methods=["POST"])
@api_check_wallet_key('invoice')
async def royalty_db_post():
    id = urlsafe_short_hash()
    paid = False
    data = await request.data
    _royalty = await create_royalty(id, paid, data)
    if 'error' in _royalty:
        return _royalty, 400
    return _royalty, HTTPStatus.OK

@royalties_ext.route("/api/v1/r_create", methods=["POST"])
@api_check_wallet_key('invoice')
async def roy_db_get():
    inkey = dict(request.headers)['X-Api-Key']
    amount = request.args.get('amount')
    data = await royalty(inkey, int(amount))
    if 'error' in data:
        return data, 400
    return data, HTTPStatus.OK

@royalties_ext.route("/api/v1/account", methods=["GET"])
@royalties_ext.route("/api/v1/account", methods=["POST"])
@royalties_ext.route("/api/v1/account", methods=["DELETE"])
@api_check_wallet_key('admin')
async def royalty_account():
    method = str(request.method)
    if method == 'POST':
        data = json.loads(await request.data)
        print(data)
        id, wallet = data.values()
        id = id if id is not None else urlsafe_short_hash()
        account = await create_royalty_account(id, wallet)
        if 'error' in account:
            return account, 400
        return account, HTTPStatus.OK
    elif method == 'DELETE':
        id = request.args.get('id')
        del_account = await delete_royalty_account(id)
        if 'error' in del_account:
            return del_account, 400
        return del_account, HTTPStatus.OK
    else:
        accounts = await get_royalty_account(None)
        if 'error' in accounts:
            return accounts, 400
        return accounts, HTTPStatus.OK

# public route to create royalty invoice
@royalties_ext.route("/api/v1/generate/<id>", methods=["GET"])
async def invoice_gen_get(id):
    amount = int(request.args.get('amount'))
    invoice = await generate_royalty(id,amount)
    if 'error' in invoice:
        return invoice, 400
    return invoice, HTTPStatus.OK

# public webhook to pay royalty invoice(s)
@royalties_ext.route("/api/v1/pay/<id>", methods=["POST"])
async def invoice_pay_post(id):
    pay_royalties = await pay_royalty(id)
    if 'error' in pay_royalties:
        return pay_royalties, 400
    return pay_royalties, HTTPStatus.OK