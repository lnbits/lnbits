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
    API_updateUser,
    API_lose,
    API_win,
    getSettings,
    accountSetup
)

# account authorized api calls

# local & remote
@winlose_ext.route("/api/v1/settings", methods=["GET"])
@api_check_wallet_key('invoice')
async def settings_get():
    usr = dict(request.headers)['X-Api-Key']
    settings = await getSettings(usr,None)
    return settings ,HTTPStatus.OK

@winlose_ext.route("/api/v1/settings", methods=["POST"])
@api_check_wallet_key('invoice')
async def settings_post():
    usr_id = await usrFromWallet(dict(request.headers)['X-Api-Key'])
    json_data = json.loads(await request.data)
    data = data if 'data' in json_data else None
    settings = await accountSetup(
        usr_id,
        json_data['invoice_wallet'],
        json_data['payout_wallet'],
        data
        )
    return settings ,HTTPStatus.OK

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
@api_check_wallet_key('admin')
async def users_delete(id):
    p = dict(request.args)
    wlOnly = False
    if 'wl_only' in p:
        url = request.url.rsplit('?',1)[0]
        wlOnly = p['wl_only']
    else:
        url = request.url
    deleted = await API_deleteUser(id, url, request.headers['X-Api-Key'], wlOnly)
    return deleted, HTTPStatus.OK

@winlose_ext.route("/api/v1/users", methods=["GET"])
@api_check_wallet_key('invoice')
async def users_get():
    params = dict(request.args)
    params['inKey'] = request.headers['X-Api-Key']
    params['url'] = request.url
    users = await API_getUsers(params)
    return users, HTTPStatus.OK

@winlose_ext.route("/api/v1/lose/<id>", methods=["GET"])
@api_check_wallet_key('invoice')
async def lose_get_(id):
    params = dict(request.args)
    lose = await API_lose(id, params)
    return lose, HTTPStatus.OK

@winlose_ext.route("/api/v1/win/<id>", methods=["GET"])
@api_check_wallet_key('admin')
async def win_get_(id):
    params = dict(request.args)
    params['url'] = request.url
    win = await API_win(id, params)
    return win, HTTPStatus.OK