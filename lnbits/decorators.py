from http import HTTPStatus
from typing import Union

from cerberus import Validator  # type: ignore
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.openapi.models import APIKey, APIKeyIn
from fastapi.params import Security
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi.security.base import SecurityBase
from pydantic.types import UUID4
from starlette.requests import Request

from lnbits.core.crud import get_user, get_wallet_for_key
from lnbits.core.models import User, Wallet
from lnbits.requestvars import g
from lnbits.settings import (
    LNBITS_ADMIN_EXTENSIONS,
    LNBITS_ADMIN_USERS,
    LNBITS_ALLOWED_USERS,
)


class KeyChecker(SecurityBase):
    def __init__(
        self, scheme_name: str = None, auto_error: bool = True, api_key: str = None
    ):
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error
        self._key_type = "invoice"
        self._api_key = api_key
        if api_key:
            key = APIKey(
                **{"in": APIKeyIn.query},
                name="X-API-KEY",
                description="Wallet API Key - QUERY",
            )
        else:
            key = APIKey(
                **{"in": APIKeyIn.header},
                name="X-API-KEY",
                description="Wallet API Key - HEADER",
            )
        self.wallet = None  # type: ignore
        self.model: APIKey = key

    async def __call__(self, request: Request):
        try:
            key_value = (
                self._api_key
                if self._api_key
                else request.headers.get("X-API-KEY") or request.query_params["api-key"]
            )
            # FIXME: Find another way to validate the key. A fetch from DB should be avoided here.
            #        Also, we should not return the wallet here - thats silly.
            #        Possibly store it in a Redis DB
            self.wallet = await get_wallet_for_key(key_value, self._key_type)  # type: ignore
            if not self.wallet:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    detail="Invalid key or expired key.",
                )

        except KeyError:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="`X-API-KEY` header missing."
            )


class WalletInvoiceKeyChecker(KeyChecker):
    """
    WalletInvoiceKeyChecker will ensure that the provided invoice
    wallet key is correct and populate g().wallet with the wallet
    for the key in `X-API-key`.

    The checker will raise an HTTPException when the key is wrong in some ways.
    """

    def __init__(
        self, scheme_name: str = None, auto_error: bool = True, api_key: str = None
    ):
        super().__init__(scheme_name, auto_error, api_key)
        self._key_type = "invoice"


class WalletAdminKeyChecker(KeyChecker):
    """
    WalletAdminKeyChecker will ensure that the provided admin
    wallet key is correct and populate g().wallet with the wallet
    for the key in `X-API-key`.

    The checker will raise an HTTPException when the key is wrong in some ways.
    """

    def __init__(
        self, scheme_name: str = None, auto_error: bool = True, api_key: str = None
    ):
        super().__init__(scheme_name, auto_error, api_key)
        self._key_type = "admin"


class WalletTypeInfo:
    wallet_type: int
    wallet: Wallet

    def __init__(self, wallet_type: int, wallet: Wallet) -> None:
        self.wallet_type = wallet_type
        self.wallet = wallet


api_key_header = APIKeyHeader(
    name="X-API-KEY",
    auto_error=False,
    description="Admin or Invoice key for wallet API's",
)
api_key_query = APIKeyQuery(
    name="api-key",
    auto_error=False,
    description="Admin or Invoice key for wallet API's",
)


async def get_key_type(
    r: Request,
    api_key_header: str = Security(api_key_header),  # type: ignore
    api_key_query: str = Security(api_key_query),  # type: ignore
) -> WalletTypeInfo:
    # 0: admin
    # 1: invoice
    # 2: invalid
    pathname = r["path"].split("/")[1]

    if not api_key_header and not api_key_query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    token = api_key_header if api_key_header else api_key_query

    try:
        admin_checker = WalletAdminKeyChecker(api_key=token)
        await admin_checker.__call__(r)
        wallet = WalletTypeInfo(0, admin_checker.wallet)  # type: ignore
        if (LNBITS_ADMIN_USERS and wallet.wallet.user not in LNBITS_ADMIN_USERS) and (
            LNBITS_ADMIN_EXTENSIONS and pathname in LNBITS_ADMIN_EXTENSIONS
        ):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
            )
        return wallet
    except HTTPException as e:
        if e.status_code == HTTPStatus.BAD_REQUEST:
            raise
        if e.status_code == HTTPStatus.UNAUTHORIZED:
            pass
    except:
        raise

    try:
        invoice_checker = WalletInvoiceKeyChecker(api_key=token)
        await invoice_checker.__call__(r)
        wallet = WalletTypeInfo(1, invoice_checker.wallet)  # type: ignore
        if (LNBITS_ADMIN_USERS and wallet.wallet.user not in LNBITS_ADMIN_USERS) and (
            LNBITS_ADMIN_EXTENSIONS and pathname in LNBITS_ADMIN_EXTENSIONS
        ):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
            )
        return wallet
    except HTTPException as e:
        if e.status_code == HTTPStatus.BAD_REQUEST:
            raise
        if e.status_code == HTTPStatus.UNAUTHORIZED:
            return WalletTypeInfo(2, None)  # type: ignore
    except:
        raise
    return wallet


async def require_admin_key(
    r: Request,
    api_key_header: str = Security(api_key_header),  # type: ignore
    api_key_query: str = Security(api_key_query),  # type: ignore
):
    token = api_key_header if api_key_header else api_key_query

    wallet = await get_key_type(r, token)

    if wallet.wallet_type != 0:
        # If wallet type is not admin then return the unauthorized status
        # This also covers when the user passes an invalid key type
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin key required."
        )
    else:
        return wallet


async def require_invoice_key(
    r: Request,
    api_key_header: str = Security(api_key_header),  # type: ignore
    api_key_query: str = Security(api_key_query),  # type: ignore
):
    token = api_key_header if api_key_header else api_key_query

    wallet = await get_key_type(r, token)

    if wallet.wallet_type > 1:
        # If wallet type is not invoice then return the unauthorized status
        # This also covers when the user passes an invalid key type
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invoice (or Admin) key required.",
        )
    else:
        return wallet


async def check_user_exists(usr: UUID4) -> User:
    g().user = await get_user(usr.hex)
    if not g().user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="User  does not exist."
        )

    if LNBITS_ALLOWED_USERS and g().user.id not in LNBITS_ALLOWED_USERS:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
        )

    if LNBITS_ADMIN_USERS and g().user.id in LNBITS_ADMIN_USERS:
        g().user.admin = True

    return g().user
