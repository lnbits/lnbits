from http import HTTPStatus
from typing import Literal, Optional, Type

from fastapi import Query, Request, Security
from fastapi.exceptions import HTTPException
from fastapi.openapi.models import APIKey, APIKeyIn
from fastapi.security import APIKeyHeader, APIKeyQuery
from fastapi.security.base import SecurityBase

from lnbits.core.crud import get_user, get_wallet_for_key
from lnbits.core.models import User, WalletType, WalletTypeInfo
from lnbits.db import Filter, Filters, TFilterModel
from lnbits.requestvars import g
from lnbits.settings import settings

# from pydantic.types import UUID4


def require_user(request: Request):
    user = request.state.user
    if user is None:
        raise HTTPException(401)
    return user


def require_admin(request: Request):
    user = require_user(request)
    if not user.is_admin and not user.super_user:
        raise HTTPException(401)

    return user


def require_super_user(request: Request):
    user = require_user(request)
    if not user.super_user:
        raise HTTPException(401)
    return user


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
        self._key_type = WalletType.invoice
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
        self.wallet = None
        self.model: APIKey = key

    async def __call__(self, request: Request):
        try:
            key_value = (
                self._api_key
                if self._api_key
                else request.headers.get("X-API-KEY") or request.query_params["api-key"]
            )
            # FIXME: Find another way to validate the key. A fetch from DB should be
            #        avoided here. Also, we should not return the wallet here - thats
            #        silly. Possibly store it in a Redis DB
            wallet = await get_wallet_for_key(key_value, self._key_type)
            if not wallet or wallet.deleted:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    detail="Invalid key or wallet.",
                )
            self.wallet = wallet  # type: ignore
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
        self._key_type = WalletType.invoice


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
        self._key_type = WalletType.admin


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
    token = api_key_header or api_key_query

    if not token:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Invoice (or Admin) key required.",
        )

    for wallet_type, WalletChecker in zip(
        [WalletType.admin, WalletType.invoice],
        [WalletAdminKeyChecker, WalletInvoiceKeyChecker],
    ):
        try:
            checker = WalletChecker(api_key=token)
            await checker.__call__(r)
            if checker.wallet is None:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
                )
            wallet = WalletTypeInfo(wallet_type, checker.wallet)
            if (
                wallet.wallet.user != settings.super_user
                and wallet.wallet.user not in settings.lnbits_admin_users
            ) and (
                settings.lnbits_admin_extensions
                and r["path"].split("/")[1] in settings.lnbits_admin_extensions
            ):
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="User not authorized for this extension.",
                )
            return wallet
        except HTTPException as exc:
            if exc.status_code == HTTPStatus.BAD_REQUEST:
                raise
            elif exc.status_code == HTTPStatus.UNAUTHORIZED:
                # we pass this in case it is not an invoice key, nor an admin key,
                # and then return NOT_FOUND at the end of this block
                pass
            else:
                raise
        except Exception:
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
            status_code=HTTPStatus.UNAUTHORIZED, detail="Admin key required."
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

    if (
        wallet.wallet_type != WalletType.admin
        and wallet.wallet_type != WalletType.invoice
    ):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Invoice (or Admin) key required.",
        )
    else:
        return wallet


async def check_user_exists(req: Request, usr: Optional[str] = None) -> User:
    if req.state.user:
        user = await get_user(req.state.user.id)
        assert user, "Logged in user has to exist."
        g().user = user
        return user

    if not usr:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Not logged in. or missing `?usr=` query parameter.",
        )

    g().user = await get_user(usr)

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


async def check_admin(req: Request, usr: Optional[str] = None) -> User:
    user = await check_user_exists(req, usr)
    if user.id != settings.super_user and user.id not in settings.lnbits_admin_users:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="User not authorized. No admin privileges.",
        )

    return user


async def check_super_user(req: Request, usr: Optional[str] = None) -> User:
    user = await check_admin(req, usr)
    if user.id != settings.super_user:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="User not authorized. No super user privileges.",
        )
    return user


def parse_filters(model: Type[TFilterModel]):
    """
    Parses the query params as filters.
    :param model: model used for validation of filter values
    """

    def dependency(
        request: Request,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sortby: Optional[str] = None,
        direction: Optional[Literal["asc", "desc"]] = None,
        search: Optional[str] = Query(None, description="Text based search"),
    ):
        params = request.query_params
        filters = []
        for key in params.keys():
            try:
                filters.append(Filter.parse_query(key, params.getlist(key), model))
            except ValueError:
                continue

        return Filters(
            filters=filters,
            limit=limit,
            offset=offset,
            sortby=sortby,
            direction=direction,
            search=search,
            model=model,
        )

    return dependency
