from quart import g, jsonify, request
from http import HTTPStatus
from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from . import winlose_ext
from .helpers import usrFromWallet, inKeyFromWallet, getPayoutBalance
import json
from .crud import(
    API_createUser,
    API_deleteUser,
    API_getUsers,
    API_updateUser
)

# account authorized api calls

# local & remote
@winlose_ext.route("/api/v1/users", methods=["POST"])
@api_check_wallet_key('invoice')
async def users_post():
    local = dict(request.args)['local'] if 'local' in dict(request.args) else None
    data = json.loads(await request.data)
    auto = True if not 'auto' in data else data['auto']
    user = await API_createUser(
        request.headers['X-Api-Key'],
        auto,
        {"data":data, "url":request.url, "local":local})
    return user,HTTPStatus.OK

@winlose_ext.route("/api/v1/users", methods=["PUT"])
@api_check_wallet_key('invoice')
async def users_put():
    data = json.loads(await request.data)
    update = await API_updateUser(data)
    return update, HTTPStatus.OK

@winlose_ext.route("/api/v1/users/<id>", methods=["DELETE"])
@api_check_wallet_key('invoice')
async def users_delete(id):
    deleted = await API_deleteUser(id, request.url, request.headers['X-Api-Key'])
    return deleted, HTTPStatus.OK

@winlose_ext.route("/api/v1/users", methods=["GET"])
@api_check_wallet_key('invoice')
async def users_get():
    params = dict(request.args)
    params['inKey'] = request.headers['X-Api-Key']
    params['url'] = request.url
    users = await API_getUsers(params)
    return users, HTTPStatus.OK

@winlose_ext.route("/api/v1/users/payout/<id>", methods=["GET"])
@api_check_wallet_key('invoice')
async def users_payoutBalance_get_(id):
    ikey = await inKeyFromWallet(id)
    balance = await getPayoutBalance(ikey, request.url)
    return balance, HTTPStatus.OK
