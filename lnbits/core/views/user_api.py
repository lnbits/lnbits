from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from lnbits.helpers import create_access_token, is_valid_email_address
from lnbits.settings import AuthMethods, settings

from ..crud import (
    create_user,
    get_account_by_username_or_email,
    get_user,
    verify_user_password,
)
from ..models import CreateUser, LoginUser

user_router = APIRouter()


@user_router.post(
    "/api/v1/login", description="Login to the API via the username and password"
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.username_and_password):
        raise HTTPException(
            HTTP_401_UNAUTHORIZED, "Login by 'Username and Password' not allowed."
        )

    invalid_credentials = HTTPException(HTTP_401_UNAUTHORIZED, "Invalid credentials.")
    user = await get_account_by_username_or_email(form_data.username)

    if not user:
        raise invalid_credentials
    if not await verify_user_password(user.id, form_data.password):
        raise invalid_credentials

    return _auth_success_response(user.username, user.id)


@user_router.post("/api/v1/login/usr", description="Login to the API via the User ID")
async def login_usr(data: LoginUser) -> JSONResponse:
    if not settings.is_auth_method_allowed(AuthMethods.user_id_only):
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Login by 'User ID' not allowed.")

    user = await get_user(data.usr.hex)
    if not user:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "User ID does not exist.")

    return _auth_success_response(user.username, user.id)


@user_router.post("/api/v1/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"status": "success"}, status_code=status.HTTP_200_OK)
    response.delete_cookie("cookie_access_token")
    return response


@user_router.post("/api/v1/register")
async def register(data: CreateUser) -> JSONResponse:
    if data.password != data.password_repeat:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST, detail="Passwords do not match."
        )

    if not data.username:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST, detail="Missing username."
        )

    if data.email and not is_valid_email_address(data.email):
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid email.")

    try:
        user = await create_user(data)
        return _auth_success_response(user.username)

    except ValueError as e:
        raise HTTPException(HTTP_403_FORBIDDEN, str(e))
    except Exception as e:
        logger.debug(e)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot create user.")


def _auth_success_response(
    username: Optional[str] = "", user_id: Optional[str] = None
) -> JSONResponse:
    access_token = create_access_token(data={"sub": username, "usr": user_id})
    response = JSONResponse(
        content={"access_token": access_token, "token_type": "bearer"}
    )
    response.set_cookie(key="cookie_access_token", value=access_token, httponly=True)
    return response
