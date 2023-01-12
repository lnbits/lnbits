from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.openapi.models import APIKey, APIKeyIn
from fastapi.security import APIKeyHeader, APIKeyQuery
from fastapi.security.base import SecurityBase
from pydantic.types import UUID4

from lnbits.core.crud import get_user, get_wallet_for_key
from lnbits.core.models import User, Wallet
from lnbits.requestvars import g
from lnbits.settings import settings


# TODO: fix type ignores
class KeyChecker(SecurityBase):
    def __init__(
        self,
        scheme_name: Optional[str] = None,
        auto_error: bool = True,
        api_key: Optional[str] = None,
    ):
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error
        self._key_type = "invoice"
        self._api_key = api_key
        if api_key:
            key = APIKey(
                **{"in": APIKeyIn.query},  # type: ignore
                name="X-API-KEY",
                description="Wallet API Key - QUERY",
            )
        else:
            key = APIKey(
                **{"in": APIKeyIn.header},  # type: ignore
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
        self,
        scheme_name: Optional[str] = None,
        auto_error: bool = True,
        api_key: Optional[str] = None,
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
        self,
        scheme_name: Optional[str] = None,
        auto_error: bool = True,
        api_key: Optional[str] = None,
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
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
) -> WalletTypeInfo:
    # 0: admin
    # 1: invoice
    # 2: invalid
    pathname = r["path"].split("/")[1]

    token = api_key_header or api_key_query

    if not token:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Invoice (or Admin) key required.",
        )

    for typenr, WalletChecker in zip(
        [0, 1], [WalletAdminKeyChecker, WalletInvoiceKeyChecker]
    ):
        try:
            checker = WalletChecker(api_key=token)
            await checker.__call__(r)
            wallet = WalletTypeInfo(typenr, checker.wallet)  # type: ignore
            if wallet is None or wallet.wallet is None:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
                )
            if (
                wallet.wallet.user != settings.super_user
                and wallet.wallet.user not in settings.lnbits_admin_users
            ) and (
                settings.lnbits_admin_extensions
                and pathname in settings.lnbits_admin_extensions
            ):
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="User not authorized for this extension.",
                )
            return wallet
        except HTTPException as e:
            if e.status_code == HTTPStatus.BAD_REQUEST:
                raise
            elif e.status_code == HTTPStatus.UNAUTHORIZED:
                # we pass this in case it is not an invoice key, nor an admin key, and then return NOT_FOUND at the end of this block
                pass
            else:
                raise
        except:
            raise
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
    )


async def require_admin_key(
    r: Request,
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
):

    token = api_key_header or api_key_query

    if not token:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Admin key required.",
        )

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
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
):

    token = api_key_header or api_key_query

    if not token:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Invoice (or Admin) key required.",
        )

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
            status_code=HTTPStatus.NOT_FOUND, detail="User does not exist."
        )

    if (
        len(settings.lnbits_allowed_users) > 0
        and g().user.id not in settings.lnbits_allowed_users
        and g().user.id not in settings.lnbits_admin_users
        and g().user.id != settings.super_user
    ):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="User not authorized."
        )

    return g().user


async def check_admin(usr: UUID4) -> User:
    user = await check_user_exists(usr)
    if user.id != settings.super_user and user.id not in settings.lnbits_admin_users:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="User not authorized. No admin privileges.",
        )
    user.admin = True
    user.super_user = False
    if user.id == settings.super_user:
        user.super_user = True

    return user


async def check_super_user(usr: UUID4) -> User:
    user = await check_admin(usr)
    if user.id != settings.super_user:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="User not authorized. No super user privileges.",
        )
    return user
