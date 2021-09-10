from functools import wraps
from http import HTTPStatus

from fastapi.security import api_key
from lnbits.core.models import Wallet
from typing import List, Union
from uuid import UUID

from cerberus import Validator  # type: ignore
from fastapi.exceptions import HTTPException
from fastapi.openapi.models import APIKey, APIKeyIn
from fastapi.params import Security
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi.security.base import SecurityBase
from starlette.requests import Request

from lnbits.core.crud import get_user, get_wallet_for_key
from lnbits.requestvars import g
from lnbits.settings import LNBITS_ALLOWED_USERS


class KeyChecker(SecurityBase):
    def __init__(self, scheme_name: str = None, auto_error: bool = True, api_key: str = None):
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error
        self._key_type = "invoice"
        self._api_key = api_key
        if api_key:
            self.model: APIKey= APIKey(
                **{"in": APIKeyIn.query}, name="X-API-KEY", description="Wallet API Key - QUERY"
            )
        else:
            self.model: APIKey= APIKey(
                **{"in": APIKeyIn.header}, name="X-API-KEY", description="Wallet API Key - HEADER"
            )
        self.wallet = None

    async def __call__(self, request: Request) -> Wallet:
        try:
            key_value = self._api_key if self._api_key else request.headers.get("X-API-KEY") or request.query_params["api-key"]
            # FIXME: Find another way to validate the key. A fetch from DB should be avoided here.
            #        Also, we should not return the wallet here - thats silly.
            #        Possibly store it in a Redis DB
            self.wallet = await get_wallet_for_key(key_value, self._key_type)
            if not self.wallet:
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid key or expired key.")

        except KeyError:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, 
                                detail="`X-API-KEY` header missing.")

class WalletInvoiceKeyChecker(KeyChecker):
    """
    WalletInvoiceKeyChecker will ensure that the provided invoice
    wallet key is correct and populate g().wallet with the wallet 
    for the key in `X-API-key`.

    The checker will raise an HTTPException when the key is wrong in some ways.
    """
    def __init__(self, scheme_name: str = None, auto_error: bool = True, api_key: str = None):
        super().__init__(scheme_name, auto_error, api_key)
        self._key_type = "invoice"

class WalletAdminKeyChecker(KeyChecker):
    """
    WalletAdminKeyChecker will ensure that the provided admin
    wallet key is correct and populate g().wallet with the wallet 
    for the key in `X-API-key`.

    The checker will raise an HTTPException when the key is wrong in some ways.
    """
    def __init__(self, scheme_name: str = None, auto_error: bool = True, api_key: str = None):
        super().__init__(scheme_name, auto_error, api_key)
        self._key_type = "admin"

class WalletTypeInfo():
    wallet_type: int
    wallet: Wallet

    def __init__(self, wallet_type: int, wallet: Wallet) -> None:
        self.wallet_type = wallet_type
        self.wallet = wallet


api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False, description="Admin or Invoice key for wallet API's")
api_key_query = APIKeyQuery(name="api-key", auto_error=False, description="Admin or Invoice key for wallet API's")
async def get_key_type(r: Request, 
                        api_key_header: str = Security(api_key_header), 
                        api_key_query: str = Security(api_key_query)) -> WalletTypeInfo:
    # 0: admin
    # 1: invoice
    # 2: invalid
    try:
        checker = WalletAdminKeyChecker(api_key=api_key_query)
        await checker.__call__(r)
        return WalletTypeInfo(0, checker.wallet)
    except HTTPException as e:
        if e.status_code == HTTPStatus.UNAUTHORIZED:
            pass
    except:
        raise

    try:
        checker = WalletInvoiceKeyChecker()
        await checker.__call__(r)
        return WalletTypeInfo(1, checker.wallet)
    except HTTPException as e:
        if e.status_code == HTTPStatus.UNAUTHORIZED:
            return WalletTypeInfo(2, None)
    except:
        raise

def api_validate_post_request(*, schema: dict):
    def wrap(view):
        @wraps(view)
        async def wrapped_view(**kwargs):
            if "application/json" not in request.headers["Content-Type"]:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST, 
                    detail=jsonify({"message": "Content-Type must be `application/json`."})
                )

            v = Validator(schema)
            data = await request.get_json()
            g().data = {key: data[key] for key in schema.keys() if key in data}

            if not v.validate(g().data):
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST, 
                    detail=jsonify({"message": f"Errors in request data: {v.errors}"})
                )
                

            return await view(**kwargs)

        return wrapped_view

    return wrap


def check_user_exists(param: str = "usr"):
    def wrap(view):
        @wraps(view)
        async def wrapped_view(**kwargs):
            g().user = await get_user(request.args.get(param, type=str)) 
            if not g().user:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    detail="User  does not exist."
                )

            if LNBITS_ALLOWED_USERS and g().user.id not in LNBITS_ALLOWED_USERS:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    detail="User not authorized."
                )
                

            return await view(**kwargs)

        return wrapped_view

    return wrap



