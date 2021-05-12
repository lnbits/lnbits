from quart import g, jsonify, request
from http import HTTPStatus
from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from . import winlose_ext
from .helpers import usrFromWallet
import json
from .crud import(
    API_createUser
)

# account authorized api calls

@winlose_ext.route("/api/v1/users", methods=["POST"])
@api_check_wallet_key('invoice')
async def users_get():
    user = await API_createUser(
        request.headers['X-Api-Key'],
        True,
        {"data":None, "url":request.url})
    print(user)
    return user,HTTPStatus.OK
