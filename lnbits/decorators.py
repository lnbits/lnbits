from http import HTTPStatus
from typing import Annotated, Literal, Optional, Union

import jwt
from fastapi import Cookie, Depends, Query, Request, Security
from fastapi.exceptions import HTTPException
from fastapi.openapi.models import APIKey, APIKeyIn, SecuritySchemeType
from fastapi.security import APIKeyHeader, APIKeyQuery, HTTPBearer, OAuth2PasswordBearer
from fastapi.security.base import SecurityBase
from loguru import logger
from pydantic.types import UUID4

from lnbits.core.crud import (
    get_account,
    get_account_by_email,
    get_account_by_username,
    get_user_active_extensions_ids,
    get_user_from_account,
    get_wallet_for_key,
)
from lnbits.core.crud.users import get_user_access_control_lists
from lnbits.core.models import (
    AccessTokenPayload,
    Account,
    KeyType,
    SimpleStatus,
    User,
    WalletTypeInfo,
)
from lnbits.db import Connection, Filter, Filters, TFilterModel
from lnbits.helpers import normalize_path, path_segments
from lnbits.settings import AuthMethods, settings

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/v1/auth",
    auto_error=False,
    description="OAuth2 access token for authentication with username and password.",
)
http_bearer = HTTPBearer(
    auto_error=False,
    description="Bearer Token for custom ACL based access control",
)
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


class KeyChecker(SecurityBase):
    def __init__(
        self,
        api_key: Optional[str] = None,
        expected_key_type: Optional[KeyType] = None,
    ):
        self.auto_error: bool = True
        self.expected_key_type = expected_key_type
        self._api_key = api_key
        if api_key:
            openapi_model = APIKey(
                **{"in": APIKeyIn.query},
                type=SecuritySchemeType.apiKey,
                name="X-API-KEY",
                description="Wallet API Key - QUERY",
            )
        else:
            openapi_model = APIKey(
                **{"in": APIKeyIn.header},
                type=SecuritySchemeType.apiKey,
                name="X-API-KEY",
                description="Wallet API Key - HEADER",
            )
        self.model: APIKey = openapi_model  # type: ignore

    async def __call__(self, request: Request) -> WalletTypeInfo:

        key_value = (
            self._api_key
            if self._api_key
            else request.headers.get("X-API-KEY") or request.query_params.get("api-key")
        )

        if not key_value:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="No Api Key provided.",
            )

        wallet = await get_wallet_for_key(key_value)

        if not wallet:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Wallet not found.",
            )

        request.scope["user_id"] = wallet.user
        if self.expected_key_type is KeyType.admin and wallet.adminkey != key_value:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Invalid adminkey.",
            )

        await _check_user_extension_access(wallet.user, request["path"])

        key_type = KeyType.admin if wallet.adminkey == key_value else KeyType.invoice
        return WalletTypeInfo(key_type, wallet)


async def require_admin_key(
    request: Request,
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
) -> WalletTypeInfo:
    check: KeyChecker = KeyChecker(
        api_key=api_key_header or api_key_query,
        expected_key_type=KeyType.admin,
    )
    return await check(request)


async def require_invoice_key(
    request: Request,
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query),
) -> WalletTypeInfo:
    check: KeyChecker = KeyChecker(
        api_key=api_key_header or api_key_query,
        expected_key_type=KeyType.invoice,
    )
    return await check(request)


async def check_access_token(
    header_access_token: Annotated[Union[str, None], Depends(oauth2_scheme)],
    cookie_access_token: Annotated[Union[str, None], Cookie()] = None,
    bearer_access_token: Annotated[Union[str, None], Depends(http_bearer)] = None,
) -> Optional[str]:
    return header_access_token or cookie_access_token or bearer_access_token


async def check_user_exists(
    r: Request,
    access_token: Annotated[Optional[str], Depends(check_access_token)],
    usr: Optional[UUID4] = None,
) -> User:
    if access_token:
        account = await _get_account_from_token(access_token, r["path"], r["method"])
    elif usr and settings.is_auth_method_allowed(AuthMethods.user_id_only):
        account = await get_account(usr.hex)
        if account and account.is_admin:
            raise HTTPException(
                HTTPStatus.FORBIDDEN, "User id only access for admins is forbidden."
            )
    else:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Missing user ID or access token.")

    if not account:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "User not found.")

    r.scope["user_id"] = account.id
    if not settings.is_user_allowed(account.id):
        raise HTTPException(HTTPStatus.FORBIDDEN, "User not allowed.")

    user = await get_user_from_account(account)
    if not user:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "User not found.")
    await _check_user_extension_access(user.id, r["path"])
    return user


async def optional_user_id(
    r: Request,
    access_token: Annotated[Optional[str], Depends(check_access_token)],
    usr: Optional[UUID4] = None,
) -> Optional[str]:
    if usr and settings.is_auth_method_allowed(AuthMethods.user_id_only):
        return usr.hex
    if access_token:
        account = await _get_account_from_token(access_token, r["path"], r["method"])
        return account.id if account else None

    return None


async def access_token_payload(
    access_token: Annotated[Optional[str], Depends(check_access_token)],
) -> AccessTokenPayload:
    if not access_token:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Missing access token.")

    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    return AccessTokenPayload(**payload)


async def check_admin(user: Annotated[User, Depends(check_user_exists)]) -> User:
    if user.id != settings.super_user and user.id not in settings.lnbits_admin_users:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "User not authorized. No admin privileges."
        )
    if not user.has_password:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Admin users must have credentials configured."
        )

    return user


async def check_super_user(user: Annotated[User, Depends(check_user_exists)]) -> User:
    if user.id != settings.super_user:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "User not authorized. No super user privileges."
        )
    if not user.has_password:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Super user must have credentials configured."
        )
    return user


def parse_filters(model: type[TFilterModel]):
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
        for i, key in enumerate(params.keys()):
            try:
                filters.append(Filter.parse_query(key, params.getlist(key), model, i))
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


async def check_user_extension_access(
    user_id: str, ext_id: str, conn: Optional[Connection] = None
) -> SimpleStatus:
    """
    Check if the user has access to a particular extension.
    Raises HTTP Forbidden if the user is not allowed.
    """
    if settings.is_admin_extension(ext_id) and not settings.is_admin_user(user_id):
        return SimpleStatus(
            success=False, message=f"User not authorized for extension '{ext_id}'."
        )

    if settings.is_installed_extension_id(ext_id):
        ext_ids = await get_user_active_extensions_ids(user_id, conn=conn)
        if ext_id not in ext_ids:
            return SimpleStatus(
                success=False, message=f"Extension '{ext_id}' not enabled."
            )

    return SimpleStatus(success=True, message="OK")


async def _check_user_extension_access(user_id: str, path: str):
    ext_id = path_segments(path)[0]
    status = await check_user_extension_access(user_id, ext_id)
    if not status.success:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            status.message,
        )


async def _get_account_from_token(
    access_token: str, path: str, method: str
) -> Optional[Account]:
    try:
        payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
        return await _get_account_from_jwt_payload(
            AccessTokenPayload(**payload), path, method
        )

    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            HTTPStatus.UNAUTHORIZED, "Session expired.", {"token-expired": "true"}
        ) from exc
    except jwt.PyJWTError as exc:
        logger.debug(exc)
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid access token.") from exc


async def _get_account_from_jwt_payload(
    payload: AccessTokenPayload, path: str, method: str
) -> Optional[Account]:
    account = None
    if payload.sub:
        account = await get_account_by_username(payload.sub)
    elif payload.usr:
        account = await get_account(payload.usr)
    elif payload.email:
        account = await get_account_by_email(payload.email)

    if not account:
        return None

    if payload.api_token_id:
        await _check_account_api_access(account.id, payload.api_token_id, path, method)

    return account


async def _check_account_api_access(
    user_id: str, token_id: str, path: str, method: str
):
    segments = path.split("/")
    if len(segments) < 3:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not an API endpoint.")

    acls = await get_user_access_control_lists(user_id)
    acl = acls.get_acl_by_token_id(token_id)
    if not acl:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Invalid token id.")

    path = "/" + "/".join(path_segments(path)[:3])
    endpoint = acl.get_endpoint(path)
    if not endpoint:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Path not allowed.")
    if not endpoint.supports_method(method):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Method not allowed.")


def url_for_interceptor(original_method):
    def normalize_url(self, *args, **kwargs):
        url = original_method(self, *args, **kwargs)
        return url.replace(path=normalize_path(url.path))

    return normalize_url


# Upgraded extensions modify the path.
# This interceptor ensures that the path is normalized.
Request.url_for = url_for_interceptor(Request.url_for)  # type: ignore[method-assign]
