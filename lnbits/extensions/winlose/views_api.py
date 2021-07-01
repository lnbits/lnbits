from quart import g, jsonify, request
from http import HTTPStatus
from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from . import winlose_ext
from .helpers import usrFromWallet, inKeyFromWallet, getPayoutBalance, accountRecovery, checkWalletExists
import json
from .crud import (
    API_createUser,
    API_deleteUser,
    API_getUsers,
    API_updateUser,
    API_lose,
    API_win,
    API_fund,
    API_withdraw,
    handlePaymentWebhook,
    getSettings,
    accountSetup,
)

# account authorized api calls

# local & remote


@winlose_ext.route("/api/v1/settings", methods=["GET"])
@api_check_wallet_key("invoice")
async def settings_get():
    usr = dict(request.headers)["X-Api-Key"]
    settings = await getSettings(usr, None)
    return settings, HTTPStatus.OK


@winlose_ext.route("/api/v1/settings", methods=["POST"])
@api_check_wallet_key("invoice")
async def settings_post():
    usr_id = await usrFromWallet(dict(request.headers)["X-Api-Key"])
    json_data = json.loads(await request.data)
    data = json_data["data"] if "data" in json_data else None
    settings = await accountSetup(
        usr_id, json_data["invoice_wallet"], json_data["payout_wallet"], data
    )
    return settings, HTTPStatus.OK


@winlose_ext.route("/api/v1/users", methods=["POST"])
@api_check_wallet_key("invoice")
async def users_post():
    usr = dict(request.headers)["X-Api-Key"]
    settings = await getSettings(usr, None)
    if not settings["success"]:
        return {"error": "No Settings for the account"}, 400
    local = dict(request.args)["local"] if "local" in dict(request.args) else None
    data = json.loads(await request.data)
    print(data)
    if {"uid", "wid"} <= set(data):
        wal_check = await checkWalletExists(data['wid'])
        if not wal_check:
            return {"error": "No wallet found!"}, HTTPStatus.OK
    auto = True if not "auto" in data else data["auto"]
    user = await API_createUser(
        request.headers["X-Api-Key"],
        auto,
        {"data": data, "url": request.url, "local": local},
    )
    return user, HTTPStatus.OK


@winlose_ext.route("/api/v1/users", methods=["PUT"])
@api_check_wallet_key("invoice")
async def users_put():
    data = json.loads(await request.data)
    update = await API_updateUser(data)
    return update, HTTPStatus.OK


@winlose_ext.route("/api/v1/users/<id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def users_delete(id):
    p = dict(request.args)
    wlOnly = False
    if "wl_only" in p:
        url = request.url.rsplit("?", 1)[0]
        wlOnly = p["wl_only"]
    else:
        url = request.url
    deleted = await API_deleteUser(id, url, request.headers["X-Api-Key"], wlOnly)
    return deleted, HTTPStatus.OK


@winlose_ext.route("/api/v1/users", methods=["GET"])
@api_check_wallet_key("invoice")
async def users_get():
    params = dict(request.args)
    params["inKey"] = request.headers["X-Api-Key"]
    params["url"] = request.url
    users = await API_getUsers(params)
    return users, HTTPStatus.OK


@winlose_ext.route("/api/v1/lose/<id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def lose_get_(id):
    params = dict(request.args)
    lose = await API_lose(id, params)
    if "error" in lose:
        return lose, 400
    return lose, HTTPStatus.OK


@winlose_ext.route("/api/v1/win/<id>", methods=["GET"])
@api_check_wallet_key("admin")
async def win_get_(id):
    params = dict(request.args)
    params["url"] = request.url
    win = await API_win(id, params)
    return win, HTTPStatus.OK


@winlose_ext.route("/api/v1/fund/<id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def fund_get_(id):
    params = dict(request.args)
    if not {"credits", "amount"} <= set(params):
        return {"error": "credits or amount parameters missing!"}, 400
    params["inKey"] = request.headers["X-Api-Key"]
    params["url"] = request.url
    fund = await API_fund(id, params)
    if "error" in fund:
        return fund, 403
    else:
        return fund, HTTPStatus.OK


@winlose_ext.route("/api/v1/withdraw/<id>", methods=["GET"])
@api_check_wallet_key("admin")
async def withdraw_get_(id):
    params = dict(request.args)
    params["host"] = request.headers["Host"]
    params["inKey"] = request.headers["X-Api-Key"]
    params["url"] = request.url
    withdraw = await API_withdraw(id, params)
    if "error" in withdraw:
        return withdraw, 403
    else:
        return withdraw, HTTPStatus.OK


@winlose_ext.route("/api/v1/recovery", methods=["POST"])
@api_check_wallet_key("admin")
async def recovery_post():
    json_data = json.loads(await request.data)
    # data = data if 'data' in json_data else None
    recovery = await accountRecovery(json_data)
    if "error" in recovery:
        return recovery, 400
    return recovery, HTTPStatus.OK


# public api endpoints


@winlose_ext.route("/api/v1/payments/<id>", methods=["POST"])
async def payments_get_(id):
    params = dict(request.args)
    if not params:
        params["payment"] = True
    params["host"] = request.headers["Host"]
    if "X-Api-Key" in request.headers:
        params["inKey"] = request.headers["X-Api-Key"]
    payment = await handlePaymentWebhook(id, params)
    if "error" in payment:
        return payment, 400
    return payment, HTTPStatus.OK
