from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from pydantic.types import UUID4
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from lnbits.helpers import create_access_token, valid_email_address
from lnbits.settings import settings

from ..crud import (
    create_user,
    get_account_by_username_or_email,
    get_user,
)
from ..models import CreateUser, User

user_router = APIRouter()


@user_router.get("/api/v1/user")
async def user(user=Depends()) -> User:
    return user


@user_router.post(
    "/api/v1/login", description="Login to the API via the username and password"
)
async def login_endpoint(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    usr: Optional[UUID4] = None,
) -> JSONResponse:
    if usr and settings.is_user_id_auth_allowed():
        user = await get_user(usr.hex)
    else:
        user = await get_account_by_username_or_email(form_data.username)

    if not user or not user.valid_password(form_data.password):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Invalid credentials."
        )
    return _auth_success_response(user.username or "", usr.hex if usr else None)


@user_router.post("/api/v1/logout")
async def logout(response: Response) -> JSONResponse:
    response.delete_cookie("cookie_access_token")
    return JSONResponse({"status": "success"}, status_code=status.HTTP_200_OK)


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

    if data.email and not valid_email_address(data.email):
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid email.")

    try:
        user = await create_user(data)
        return _auth_success_response(username=user.username)

    except ValueError as e:
        raise HTTPException(HTTP_403_FORBIDDEN, str(e))
    except Exception as e:
        logger.debug(e)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot create user.")


def _auth_success_response(username: str, user_id: Optional[str] = None) -> Response:
    access_token = create_access_token(data={"sub": username, "usr": user_id})
    response = JSONResponse(
        content={"access_token": access_token, "token_type": "bearer"}
    )
    response.set_cookie(key="cookie_access_token", value=access_token, httponly=True)
    return response
