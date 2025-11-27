import base64
import importlib
import json
from collections.abc import Callable
from http import HTTPStatus
from time import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_sso.sso.base import OpenID, SSOBase
from loguru import logger

from lnbits.core.crud.users import (
    get_user_access_control_lists,
    update_user_access_control_list,
)
from lnbits.core.models.misc import SimpleItem
from lnbits.core.models.users import (
    ApiTokenRequest,
    ApiTokenResponse,
    DeleteAccessControlList,
    DeleteTokenRequest,
    EndpointAccess,
    UpdateAccessControlList,
)
from lnbits.core.services import create_user_account
from lnbits.core.services.users import update_user_account
from lnbits.decorators import (
    access_token_payload,
    check_account_exists,
    check_user_exists,
)
from lnbits.helpers import (
    create_access_token,
    decrypt_internal_message,
    encrypt_internal_message,
    get_api_routes,
    is_valid_email_address,
    is_valid_username,
)
from lnbits.settings import AuthMethods, settings
from lnbits.utils.nostr import normalize_public_key, verify_event

from ..crud import (
    get_account,
    get_account_by_email,
    get_account_by_pubkey,
    get_account_by_username,
    get_account_by_username_or_email,
    get_user_from_account,
    update_account,
)
from ..models import (
    AccessTokenPayload,
    Account,
    LoginUsernamePassword,
    LoginUsr,
    RegisterUser,
    ResetUserPassword,
    UpdateSuperuserPassword,
    UpdateUser,
    UpdateUserPassword,
    UpdateUserPubkey,
    User,
    UserAcls,
    UserExtra,
)

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@auth_router.get("", description="Get the authenticated user")
async def get_auth_user(user: User = Depends(check_user_exists)) -> User:
    return user


@auth_router.post("", description="Login via the username and password")
async def login(data: LoginUsernamePassword) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.username_and_password):
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Login by 'Username and Password' not allowed."
        )
    account = await get_account_by_username_or_email(data.username)
    if not account or not account.verify_password(data.password):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid credentials.")
    return _auth_success_response(account.username, account.id, account.email)


@auth_router.post("/nostr", description="Login via Nostr")
async def nostr_login(request: Request) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.nostr_auth_nip98):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Login with Nostr Auth not allowed.")
    event = _nostr_nip98_event(request)
    account = await get_account_by_pubkey(event["pubkey"])
    if not account:
        account = Account(
            id=uuid4().hex,
            pubkey=event["pubkey"],
            extra=UserExtra(provider="nostr"),
        )
        await create_user_account(account)
    return _auth_success_response(account.username or "", account.id, account.email)


@auth_router.post("/usr", description="Login via the User ID")
async def login_usr(data: LoginUsr) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.user_id_only):
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            "Login by 'User ID' not allowed.",
        )
    account = await get_account(data.usr)
    if not account:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "User ID does not exist.")
    if account.is_admin:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Admin users cannot login with user id only."
        )
    return _auth_success_response(account.username, account.id, account.email)


@auth_router.get("/acl")
async def api_get_user_acls(
    request: Request,
    account: Account = Depends(check_account_exists),
) -> UserAcls:
    api_routes = get_api_routes(request.app.router.routes)

    acls = await get_user_access_control_lists(account.id)

    # Add missing/new endpoints to the ACLs
    for acl in acls.access_control_list:
        acl_api_routes = {**api_routes}
        for route in api_routes.keys():
            if acl.get_endpoint(route):
                acl_api_routes.pop(route, None)

        for path, name in acl_api_routes.items():
            acl.endpoints.append(EndpointAccess(path=path, name=name))
        acl.endpoints.sort(key=lambda e: e.name.lower())

    return UserAcls(id=account.id, access_control_list=acls.access_control_list)


@auth_router.put("/acl")
@auth_router.patch("/acl")
async def api_update_user_acl(
    request: Request,
    data: UpdateAccessControlList,
    account: Account = Depends(check_account_exists),
) -> UserAcls:

    if not account or not account.verify_password(data.password):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid credentials.")

    user_acls = await get_user_access_control_lists(account.id)
    acl = user_acls.get_acl_by_id(data.id)
    if acl:
        user_acls.access_control_list.remove(acl)
    else:
        data.endpoints = []
        data.id = uuid4().hex

        api_routes = get_api_routes(request.app.router.routes)
        for path, name in api_routes.items():
            data.endpoints.append(EndpointAccess(path=path, name=name))

    api_paths = get_api_routes(request.app.router.routes).keys()
    data.endpoints = [e for e in data.endpoints if e.path in api_paths]
    data.endpoints.sort(key=lambda e: e.name.lower())

    user_acls.access_control_list.append(data)
    user_acls.access_control_list.sort(key=lambda t: t.name.lower())
    await update_user_access_control_list(user_acls)

    return user_acls


@auth_router.delete("/acl")
async def api_delete_user_acl(
    data: DeleteAccessControlList, account: Account = Depends(check_account_exists)
):
    if not account or not account.verify_password(data.password):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid credentials.")

    user_acls = await get_user_access_control_lists(account.id)
    user_acls.delete_acl_by_id(data.id)
    await update_user_access_control_list(user_acls)


@auth_router.post("/acl/token")
async def api_create_user_api_token(
    data: ApiTokenRequest, account: Account = Depends(check_account_exists)
) -> ApiTokenResponse:
    if not data.expiration_time_minutes > 0:
        raise ValueError("Expiration time must be in the future.")

    if not account or not account.verify_password(data.password):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid credentials.")

    if not account.username:
        raise ValueError("Username must be configured.")

    acls = await get_user_access_control_lists(account.id)
    acl = acls.get_acl_by_id(data.acl_id)
    if not acl:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid ACL id.")

    api_token_id = uuid4().hex
    api_token = _auth_api_token_response(
        account.username, api_token_id, data.expiration_time_minutes
    )

    acl.token_id_list.append(SimpleItem(id=api_token_id, name=data.token_name))
    await update_user_access_control_list(acls)
    return ApiTokenResponse(id=api_token_id, api_token=api_token)


@auth_router.delete("/acl/token")
async def api_delete_user_api_token(
    data: DeleteTokenRequest, account: Account = Depends(check_account_exists)
):

    if not account or not account.verify_password(data.password):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid credentials.")

    if not account.username:
        raise ValueError("Username must be configured.")

    acls = await get_user_access_control_lists(account.id)
    acl = acls.get_acl_by_id(data.acl_id)
    if not acl:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid ACL id.")
    acl.delete_token_by_id(data.id)
    await update_user_access_control_list(acls)


@auth_router.get("/{provider}", description="SSO Provider")
async def login_with_sso_provider(
    request: Request, provider: str, user_id: str | None = None
):
    provider_sso = _new_sso(provider)
    if not provider_sso:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            f"Login by '{provider}' not allowed.",
        )

    provider_sso.redirect_uri = str(request.base_url) + f"api/v1/auth/{provider}/token"
    with provider_sso:
        state = encrypt_internal_message(user_id)
        return await provider_sso.get_login_redirect(state=state)


@auth_router.get("/{provider}/token", description="Handle OAuth callback")
async def handle_oauth_token(request: Request, provider: str) -> RedirectResponse:
    provider_sso = _new_sso(provider)
    if not provider_sso:
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            f"Login by '{provider}' not allowed.",
        )

    with provider_sso:
        userinfo = await provider_sso.verify_and_process(request)
        if not userinfo:
            raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid user info.")
        user_id = decrypt_internal_message(provider_sso.state)
    request.session.pop("user", None)
    return await _handle_sso_login(userinfo, user_id)


@auth_router.post("/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"status": "success"}, HTTPStatus.OK)
    response.delete_cookie("cookie_access_token")
    response.delete_cookie("is_lnbits_user_authorized")
    response.delete_cookie("is_access_token_expired")
    response.delete_cookie("lnbits_last_active_wallet")

    return response


@auth_router.post("/register")
async def register(data: RegisterUser) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.username_and_password):
        raise HTTPException(
            HTTPStatus.FORBIDDEN,
            "Register by 'Username and Password' not allowed.",
        )

    if data.password != data.password_repeat:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Passwords do not match.")

    if not data.username:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Missing username.")
    if not is_valid_username(data.username):
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid username.")

    if await get_account_by_username(data.username):
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Username already exists.")

    if data.email and not is_valid_email_address(data.email):
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid email.")

    account = Account(
        id=uuid4().hex,
        email=data.email,
        username=data.username,
    )
    account.hash_password(data.password)
    await create_user_account(account)
    return _auth_success_response(account.username, account.id, account.email)


@auth_router.put("/pubkey")
async def update_pubkey(
    data: UpdateUserPubkey,
    account: Account = Depends(check_account_exists),
    payload: AccessTokenPayload = Depends(access_token_payload),
) -> User | None:
    if data.user_id != account.id:
        raise ValueError("Invalid user ID.")

    _validate_auth_timeout(payload.auth_time)
    if (
        data.pubkey
        and data.pubkey != account.pubkey
        and await get_account_by_pubkey(data.pubkey)
    ):
        raise ValueError("Public key already in use.")

    account.pubkey = normalize_public_key(data.pubkey)
    await update_account(account)
    return await get_user_from_account(account)


@auth_router.put("/password")
async def update_password(
    data: UpdateUserPassword,
    account: Account = Depends(check_account_exists),
    payload: AccessTokenPayload = Depends(access_token_payload),
) -> User | None:
    _validate_auth_timeout(payload.auth_time)
    if data.user_id != account.id:
        raise ValueError("Invalid user ID.")
    if (
        data.username
        and account.username != data.username
        and await get_account_by_username(data.username)
    ):
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Username already exists.")

    # old accounts do not have a password
    if account.password_hash:
        if not data.password_old:
            raise ValueError("Missing old password.")
        if not account.verify_password(data.password_old):
            raise ValueError("Invalid old password.")

    account.username = data.username
    account.hash_password(data.password)
    await update_account(account)
    _user = await get_user_from_account(account)
    if not _user:
        raise HTTPException(HTTPStatus.NOT_FOUND, "User not found.")
    return _user


@auth_router.put("/reset")
async def reset_password(data: ResetUserPassword) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.username_and_password):
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Auth by 'Username and Password' not allowed."
        )

    if data.password != data.password_repeat:
        raise ValueError("Passwords do not match.")
    if not data.reset_key[:10].startswith("reset_key_"):
        raise ValueError("This is not a reset key.")

    try:
        reset_key = base64.b64decode(data.reset_key[10:]).decode()
        reset_data_json = decrypt_internal_message(reset_key)
    except Exception as exc:
        raise ValueError("Invalid reset key.") from exc

    if not reset_data_json:
        raise ValueError("Cannot process reset key.")

    action, user_id, request_time = json.loads(reset_data_json)
    if not action:
        raise ValueError("Missing action.")
    if not user_id:
        raise ValueError("Missing user ID.")
    if not request_time:
        raise ValueError("Missing reset time.")

    _validate_auth_timeout(request_time)

    account = await get_account(user_id)
    if not account:
        raise HTTPException(HTTPStatus.NOT_FOUND, "User not found.")

    account.hash_password(data.password)
    await update_account(account)
    return _auth_success_response(account.username, user_id, account.email)


@auth_router.put("/update")
async def update(
    data: UpdateUser, account: Account = Depends(check_account_exists)
) -> User | None:
    if data.user_id != account.id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid user ID.")

    if data.username:
        account.username = data.username
    if data.extra:
        account.extra = data.extra

    await update_user_account(account)
    return await get_user_from_account(account)


@auth_router.put("/first_install")
async def first_install(data: UpdateSuperuserPassword) -> JSONResponse:
    if not settings.first_install:
        raise HTTPException(HTTPStatus.FORBIDDEN, "This is not your first install")
    account = await get_account(settings.super_user)
    if not account:
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Superuser not found.")
    account.username = data.username
    account.extra = account.extra or UserExtra()
    account.extra.provider = "lnbits"
    account.hash_password(data.password)
    await update_account(account)
    settings.first_install = False
    return _auth_success_response(account.username, account.id, account.email)


async def _handle_sso_login(userinfo: OpenID, verified_user_id: str | None = None):
    email = userinfo.email
    if not email or not is_valid_email_address(email):
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid email.")

    redirect_path = "/wallet"
    account = await get_account_by_email(email)

    if verified_user_id:
        if account:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Email already used.")
        account = await get_account(verified_user_id)
        if not account:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Cannot verify user email.")
        redirect_path = "/account"

    if account:
        account.extra = account.extra or UserExtra()
        account.extra.email_verified = True
        await update_account(account)
    else:
        account = Account(
            id=uuid4().hex, email=email, extra=UserExtra(email_verified=True)
        )
        await create_user_account(account)
    return _auth_redirect_response(redirect_path, email)


def _auth_success_response(
    username: str | None = None,
    user_id: str | None = None,
    email: str | None = None,
) -> JSONResponse:
    payload = AccessTokenPayload(
        sub=username or "", usr=user_id, email=email, auth_time=int(time())
    )
    access_token = create_access_token(data=payload.dict())
    max_age = settings.auth_token_expire_minutes * 60
    response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        "cookie_access_token", access_token, httponly=True, max_age=max_age
    )
    response.set_cookie("is_lnbits_user_authorized", "true", max_age=max_age)
    response.delete_cookie("is_access_token_expired")

    return response


def _auth_api_token_response(
    username: str, api_token_id: str, token_expire_minutes: int
):
    payload = AccessTokenPayload(
        sub=username, api_token_id=api_token_id, auth_time=int(time())
    )
    return create_access_token(
        data=payload.dict(), token_expire_minutes=token_expire_minutes
    )


def _auth_redirect_response(path: str, email: str) -> RedirectResponse:
    payload = AccessTokenPayload(sub="" or "", email=email, auth_time=int(time()))
    access_token = create_access_token(data=payload.dict())
    max_age = settings.auth_token_expire_minutes * 60
    response = RedirectResponse(path)
    response.set_cookie(
        "cookie_access_token", access_token, httponly=True, max_age=max_age
    )
    response.set_cookie("is_lnbits_user_authorized", "true", max_age=max_age)
    response.delete_cookie("is_access_token_expired")
    return response


def _new_sso(provider: str) -> SSOBase | None:
    try:
        if not settings.is_auth_method_allowed(AuthMethods(f"{provider}-auth")):
            return None

        client_id = getattr(settings, f"{provider}_client_id", None)
        client_secret = getattr(settings, f"{provider}_client_secret", None)
        discovery_url = getattr(settings, f"{provider}_discovery_url", None)

        if not client_id or not client_secret:
            logger.warning(f"{provider} auth allowed but not configured.")
            return None

        sso_provider_class = _find_auth_provider_class(provider)
        sso_provider = sso_provider_class(
            client_id, client_secret, None, allow_insecure_http=True
        )
        if (
            discovery_url
            and getattr(sso_provider, "discovery_url", discovery_url) != discovery_url
        ):
            sso_provider.discovery_url = discovery_url
        return sso_provider
    except Exception as e:
        logger.warning(e)

    return None


def _find_auth_provider_class(provider: str) -> Callable:
    sso_modules = ["lnbits.core.models.sso", "fastapi_sso.sso"]
    for module in sso_modules:
        try:
            provider_module = importlib.import_module(f"{module}.{provider}")
            provider_class = getattr(provider_module, f"{provider.title()}SSO")
            if provider_class:
                return provider_class
        except Exception as exc:
            logger.debug(exc)

    raise ValueError(f"No SSO provider found for '{provider}'.")


def _nostr_nip98_event(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Nostr Auth header missing.")
    scheme, token = auth_header.split()
    if scheme.lower() != "nostr":
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Invalid Authorization scheme.")
    event = None
    try:
        event_json = base64.b64decode(token.encode("ascii"))
        event = json.loads(event_json)
    except Exception as exc:
        logger.warning(exc)
    if not event:
        raise ValueError("Nostr login event cannot be parsed.")

    if not verify_event(event):
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Nostr login event is not valid.")
    if not event["kind"] == 27_235:
        raise ValueError("Invalid event kind.")

    auth_threshold = settings.auth_credetials_update_threshold
    if not (abs(time() - event["created_at"]) < auth_threshold):
        raise ValueError(
            f"More than {auth_threshold} seconds have passed "
            "since the event was signed."
        )

    _check_nostr_event_tags(event)

    return event


def _check_nostr_event_tags(event: dict):
    method: str | None = next((v for k, v in event["tags"] if k == "method"), None)
    if not method:
        raise ValueError("Tag 'method' is missing.")
    if not method.upper() == "POST":
        raise ValueError("Invalid value for tag 'method'.")

    url = next((v for k, v in event["tags"] if k == "u"), None)

    if not url:
        raise ValueError("Tag 'u' for URL is missing.")
    accepted_urls = [f"{u}/nostr" for u in settings.nostr_absolute_request_urls]
    if url not in accepted_urls:
        raise ValueError(f"Invalid value for tag 'u': '{url}'.")


def _validate_auth_timeout(auth_time: int | None = 0):
    if abs(time() - (auth_time or 0)) > settings.auth_credetials_update_threshold:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "You can only update your credentials in the first"
            f" {settings.auth_credetials_update_threshold} seconds."
            " Please login again or ask a new reset key!",
        )
