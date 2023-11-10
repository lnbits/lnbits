from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from loguru import logger
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from lnbits.helpers import valid_email_address
from lnbits.settings import settings

from ..crud import (
    create_user,
    get_account_by_username_or_email,
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
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> JSONResponse:
    username_or_email = form_data.username

    user = await get_account_by_username_or_email(username_or_email)

    if not user or not user.valid_password(form_data.password):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Invalid credentials."
        )

    access_token = _create_access_token(data={"sub": user.username})
    response = JSONResponse(
        content={"access_token": access_token, "token_type": "bearer"}
    )
    response.set_cookie(key="cookie_access_token", value=access_token, httponly=True)
    return response


@user_router.post("/api/v1/logout")
async def logout(response: Response) -> JSONResponse:
    response.delete_cookie("cookie_access_token")
    return JSONResponse({"status": "success"}, status_code=status.HTTP_200_OK)


@user_router.post("/api/v1/register")
async def register(data: CreateUser, response: Response) -> JSONResponse:
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
        access_token = _create_access_token(data={"sub": user.username})
        response.set_cookie(
            key="cookie_access_token", value=access_token, httponly=True
        )
        return JSONResponse(
            {"access_token": access_token, "token_type": "bearer"},
            status_code=status.HTTP_200_OK,
        )

    except ValueError as e:
        raise HTTPException(HTTP_403_FORBIDDEN, str(e))
    except Exception as e:
        logger.debug(e)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "Cannot create user.")


def _create_access_token(data: dict):
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt
