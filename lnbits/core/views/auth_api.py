import importlib
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_sso.sso.base import OpenID, SSOBase
from loguru import logger
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from lnbits.core.services import create_user_account
from lnbits.decorators import check_user_exists
from lnbits.helpers import (
    create_access_token,
    decrypt_internal_message,
    encrypt_internal_message,
    is_valid_email_address,
    is_valid_username,
)
from lnbits.settings import AuthMethods, settings

from ..crud import (
    get_account,
    get_account_by_email,
    get_account_by_username_or_email,
    get_user,
    update_account,
    update_user_password,
    verify_user_password,
)
from ..models import (
    CreateUser,
    LoginUsernamePassword,
    LoginUsr,
    UpdateSuperuserPassword,
    UpdateUser,
    UpdateUserPassword,
    User,
    UserConfig,
)

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@auth_router.get("", description="Get the authenticated user")
async def get_auth_user(user: User = Depends(check_user_exists)) -> User:
    return user


@auth_router.post("", description="Login via the username and password")
async def login(data: LoginUsernamePassword) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.username_and_password):
        raise HTTPException(
            HTTP_401_UNAUTHORIZED, "Login by 'Username and Password' not allowed."
        )

    try:
        user = await get_account_by_username_or_email(data.username)

        if not user:
            raise HTTPException(HTTP_401_UNAUTHORIZED, "Invalid credentials.")
        if not await verify_user_password(user.id, data.password):
            raise HTTPException(HTTP_401_UNAUTHORIZED, "Invalid credentials.")

        return _auth_success_response(user.username, user.id)
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot login.") from exc


@auth_router.post("/usr", description="Login via the User ID")
async def login_usr(data: LoginUsr) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.user_id_only):
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Login by 'User ID' not allowed.")

    try:
        user = await get_user(data.usr)
        if not user:
            raise HTTPException(HTTP_401_UNAUTHORIZED, "User ID does not exist.")

        return _auth_success_response(user.username or "", user.id)
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot login.") from exc


@auth_router.get("/{provider}", description="SSO Provider")
async def login_with_sso_provider(
    request: Request, provider: str, user_id: Optional[str] = None
):
    provider_sso = _new_sso(provider)
    if not provider_sso:
        raise HTTPException(
            HTTP_401_UNAUTHORIZED, f"Login by '{provider}' not allowed."
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
            HTTP_401_UNAUTHORIZED, f"Login by '{provider}' not allowed."
        )

    try:
        with provider_sso:
            userinfo = await provider_sso.verify_and_process(request)
            assert userinfo is not None
            user_id = decrypt_internal_message(provider_sso.state)
        request.session.pop("user", None)
        return await _handle_sso_login(userinfo, user_id)
    except HTTPException as exc:
        raise exc
    except ValueError as exc:
        raise HTTPException(HTTP_403_FORBIDDEN, str(exc)) from exc
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR,
            f"Cannot authenticate user with {provider} Auth.",
        ) from exc


@auth_router.post("/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"status": "success"}, status_code=status.HTTP_200_OK)
    response.delete_cookie("cookie_access_token")
    response.delete_cookie("is_lnbits_user_authorized")
    response.delete_cookie("is_access_token_expired")
    response.delete_cookie("lnbits_last_active_wallet")

    return response


@auth_router.post("/register")
async def register(data: CreateUser) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.username_and_password):
        raise HTTPException(
            HTTP_401_UNAUTHORIZED, "Register by 'Username and Password' not allowed."
        )

    if data.password != data.password_repeat:
        raise HTTPException(HTTP_400_BAD_REQUEST, "Passwords do not match.")

    if not data.username:
        raise HTTPException(HTTP_400_BAD_REQUEST, "Missing username.")
    if not is_valid_username(data.username):
        raise HTTPException(HTTP_400_BAD_REQUEST, "Invalid username.")

    if data.email and not is_valid_email_address(data.email):
        raise HTTPException(HTTP_400_BAD_REQUEST, "Invalid email.")

    try:
        user = await create_user_account(
            email=data.email, username=data.username, password=data.password
        )
        return _auth_success_response(user.username)

    except ValueError as exc:
        raise HTTPException(HTTP_403_FORBIDDEN, str(exc)) from exc
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR, "Cannot create user."
        ) from exc


@auth_router.put("/password")
async def update_password(
    data: UpdateUserPassword, user: User = Depends(check_user_exists)
) -> Optional[User]:
    if not settings.is_auth_method_allowed(AuthMethods.username_and_password):
        raise HTTPException(
            HTTP_401_UNAUTHORIZED, "Auth by 'Username and Password' not allowed."
        )
    if data.user_id != user.id:
        raise HTTPException(HTTP_400_BAD_REQUEST, "Invalid user ID.")

    try:
        return await update_user_password(data)
    except AssertionError as exc:
        raise HTTPException(HTTP_403_FORBIDDEN, str(exc)) from exc
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR, "Cannot update user password."
        ) from exc


@auth_router.put("/update")
async def update(
    data: UpdateUser, user: User = Depends(check_user_exists)
) -> Optional[User]:
    if data.user_id != user.id:
        raise HTTPException(HTTP_400_BAD_REQUEST, "Invalid user ID.")
    if data.username and not is_valid_username(data.username):
        raise HTTPException(HTTP_400_BAD_REQUEST, "Invalid username.")
    if data.email != user.email:
        raise HTTPException(HTTP_400_BAD_REQUEST, "Email mismatch.")

    try:
        return await update_account(user.id, data.username, None, data.config)
    except AssertionError as exc:
        raise HTTPException(HTTP_403_FORBIDDEN, str(exc)) from exc
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR, "Cannot update user."
        ) from exc


@auth_router.put("/first_install")
async def first_install(data: UpdateSuperuserPassword) -> JSONResponse:
    if not settings.first_install:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "This is not your first install")
    try:
        await update_account(
            user_id=settings.super_user,
            username=data.username,
            user_config=UserConfig(provider="lnbits"),
        )
        super_user = UpdateUserPassword(
            user_id=settings.super_user,
            password=data.password,
            password_repeat=data.password_repeat,
            username=data.username,
        )
        await update_user_password(super_user)
        settings.first_install = False
        return _auth_success_response(username=super_user.username)
    except AssertionError as exc:
        raise HTTPException(HTTP_403_FORBIDDEN, str(exc)) from exc
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR, "Cannot update user password."
        ) from exc


async def _handle_sso_login(userinfo: OpenID, verified_user_id: Optional[str] = None):
    email = userinfo.email
    if not email or not is_valid_email_address(email):
        raise HTTPException(HTTP_400_BAD_REQUEST, "Invalid email.")

    redirect_path = "/wallet"
    user_config = UserConfig(**dict(userinfo))
    user_config.email_verified = True

    account = await get_account_by_email(email)

    if verified_user_id:
        if account:
            raise HTTPException(HTTP_401_UNAUTHORIZED, "Email already used.")
        account = await get_account(verified_user_id)
        if not account:
            raise HTTPException(HTTP_401_UNAUTHORIZED, "Cannot verify user email.")
        redirect_path = "/account"

    if account:
        user = await update_account(account.id, email=email, user_config=user_config)
    else:
        if not settings.new_accounts_allowed:
            raise HTTPException(HTTP_400_BAD_REQUEST, "Account creation is disabled.")
        user = await create_user_account(email=email, user_config=user_config)

    if not user:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "User not found.")

    return _auth_redirect_response(redirect_path, email)


def _auth_success_response(
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> JSONResponse:
    access_token = create_access_token(
        data={"sub": username or "", "usr": user_id, "email": email}
    )
    response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
    response.set_cookie("cookie_access_token", access_token, httponly=True)
    response.set_cookie("is_lnbits_user_authorized", "true")
    response.delete_cookie("is_access_token_expired")

    return response


def _auth_redirect_response(path: str, email: str) -> RedirectResponse:
    access_token = create_access_token(data={"sub": "" or "", "email": email})
    response = RedirectResponse(path)
    response.set_cookie("cookie_access_token", access_token, httponly=True)
    response.set_cookie("is_lnbits_user_authorized", "true")
    response.delete_cookie("is_access_token_expired")
    return response


def _new_sso(provider: str) -> Optional[SSOBase]:
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
    sso_modules = ["lnbits.core.sso", "fastapi_sso.sso"]
    for module in sso_modules:
        try:
            provider_module = importlib.import_module(f"{module}.{provider}")
            provider_class = getattr(provider_module, f"{provider.title()}SSO")
            if provider_class:
                return provider_class
        except Exception:
            pass

    raise ValueError(f"No SSO provider found for '{provider}'.")
