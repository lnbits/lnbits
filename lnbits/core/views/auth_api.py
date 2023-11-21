from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_sso.sso.base import OpenID
from fastapi_sso.sso.github import GithubSSO
from fastapi_sso.sso.google import GoogleSSO
from loguru import logger
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from lnbits.decorators import check_user_exists
from lnbits.helpers import (
    create_access_token,
    is_valid_email_address,
    is_valid_username,
)
from lnbits.settings import AuthMethods, settings

# todo: move this class to a `crypto.py` file
from lnbits.wallets.macaroon.macaroon import AESCipher

from ..crud import (
    create_account,
    create_user,
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
    UpdateUser,
    UpdateUserPassword,
    User,
    UserConfig,
)

auth_router = APIRouter()


def _init_google_sso() -> Optional[GoogleSSO]:
    if not settings.is_auth_method_allowed(AuthMethods.google_auth):
        return None
    if not settings.is_google_auth_configured:
        logger.warning("Google Auth allowed but not configured.")
        return None
    return GoogleSSO(
        settings.google_client_id,
        settings.google_client_secret,
        None,
        allow_insecure_http=True,
    )


def _init_github_sso() -> Optional[GithubSSO]:
    if not settings.is_auth_method_allowed(AuthMethods.github_auth):
        return None
    if not settings.is_github_auth_configured:
        logger.warning("Github Auth allowed but not configured.")
        return None
    return GithubSSO(
        settings.github_client_id,
        settings.github_client_secret,
        None,
        allow_insecure_http=True,
    )


google_sso = _init_google_sso()
github_sso = _init_github_sso()


@auth_router.get("/api/v1/auth", description="Get the authenticated user")
async def get_auth_user(user: User = Depends(check_user_exists)) -> User:
    return user


@auth_router.post("/api/v1/auth", description="Login via the username and password")
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
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(e)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot login.")


@auth_router.post("/api/v1/auth/usr", description="Login via the User ID")
async def login_usr(data: LoginUsr) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.user_id_only):
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Login by 'User ID' not allowed.")

    try:
        user = await get_user(data.usr)
        if not user:
            raise HTTPException(HTTP_401_UNAUTHORIZED, "User ID does not exist.")

        return _auth_success_response(user.username or "", user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.debug(e)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot login.")


@auth_router.get("/api/v1/auth/google", description="Google SSO")
async def login_with_google(request: Request, user_id: Optional[str] = None):
    if not google_sso:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Login by 'Google' not allowed.")

    google_sso.redirect_uri = str(request.base_url) + "api/v1/auth/google/token"
    with google_sso:
        state = _encrypt_message(user_id)
        return await google_sso.get_login_redirect(state=state)


@auth_router.get("/api/v1/auth/github", description="Github SSO")
async def login_with_github(request: Request, user_id: Optional[str] = None):
    if not github_sso:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Login by 'GitHub' not allowed.")

    github_sso.redirect_uri = str(request.base_url) + "api/v1/auth/github/token"
    with github_sso:
        state = _encrypt_message(user_id)
        return await github_sso.get_login_redirect(state=state)


@auth_router.get(
    "/api/v1/auth/google/token", description="Handle Google OAuth callback"
)
async def handle_google_token(request: Request) -> JSONResponse:
    if not google_sso:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Login by 'Google' not allowed.")

    try:
        with google_sso:
            userinfo: OpenID = await google_sso.verify_and_process(request)
            user_id = _decrypt_message(google_sso.state)
        request.session.pop("user", None)
        return await _handle_sso_login(userinfo, user_id)
    except HTTPException as e:
        raise e
    except ValueError as e:
        raise HTTPException(HTTP_403_FORBIDDEN, str(e))
    except Exception as e:
        logger.debug(e)
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR, "Cannot authenticate user with Google Auth."
        )


@auth_router.get(
    "/api/v1/auth/github/token", description="Handle Github OAuth callback"
)
async def handle_github_token(request: Request) -> JSONResponse:
    if not github_sso:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Login by 'GitHub' not allowed.")

    try:
        with github_sso:
            userinfo = await github_sso.verify_and_process(request)
            user_id = _decrypt_message(google_sso.state)
        request.session.pop("user", None)
        return await _handle_sso_login(userinfo, user_id)

    except HTTPException as e:
        raise e
    except ValueError as e:
        raise HTTPException(HTTP_403_FORBIDDEN, str(e))
    except Exception as e:
        logger.debug(e)
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR, "Cannot authenticate user with GitHub Auth."
        )


@auth_router.post("/api/v1/auth/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"status": "success"}, status_code=status.HTTP_200_OK)
    response.delete_cookie("cookie_access_token")
    response.delete_cookie("is_lnbits_user_authorized")
    response.delete_cookie("is_access_token_expired")
    return response


@auth_router.post("/api/v1/auth/register")
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
        user = await create_user(data)
        return _auth_success_response(user.username)

    except ValueError as e:
        raise HTTPException(HTTP_403_FORBIDDEN, str(e))
    except Exception as e:
        logger.debug(e)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot create user.")


@auth_router.put("/api/v1/auth/password")
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
    except AssertionError as e:
        raise HTTPException(HTTP_403_FORBIDDEN, str(e))
    except Exception as e:
        logger.debug(e)
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR, "Cannot update user password."
        )


@auth_router.put("/api/v1/auth/update")
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
    except AssertionError as e:
        raise HTTPException(HTTP_403_FORBIDDEN, str(e))
    except Exception as e:
        logger.debug(e)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot update user.")


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
        user = await create_account(email=email, user_config=user_config)

    if not user:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Not authorized.")

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


def _encrypt_message(m: Optional[str] = None) -> str:
    if not m:
        return None
    return AESCipher(key=settings.auth_secret_key).encrypt(m.encode())


def _decrypt_message(m: Optional[str] = None) -> str:
    if not m:
        return None
    return AESCipher(key=settings.auth_secret_key).decrypt(m)
