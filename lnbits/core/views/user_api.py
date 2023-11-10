from datetime import datetime, timedelta
from typing import Annotated, Union

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from starlette.status import HTTP_401_UNAUTHORIZED

from lnbits.settings import settings

from ..crud import (
    create_user,
    get_user_by_username_or_email,
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
    response: Response, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> JSONResponse:
    username_or_email = form_data.username

    user = await get_user_by_username_or_email(username_or_email)

    if not user or not user.valid_password(form_data.password):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Invalid credentials."
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    response.set_cookie(key="cookie_access_token", value=access_token, httponly=True)
    return {"access_token": access_token, "token_type": "bearer"}


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
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


@user_router.post("/api/v1/logout")
async def logout(response: Response) -> JSONResponse:
    response.delete_cookie("access-token")
    return JSONResponse({"status": "success"}, status_code=status.HTTP_200_OK)


@user_router.post("/api/v1/register")
async def register_endpoint(data: CreateUser, response: Response) -> JSONResponse:
    if data.password != data.password_repeat:
        return JSONResponse(
            {
                "detail": [
                    {
                        "loc": ["body", "password_repeat"],
                        "msg": "passwords do not match",
                    }
                ]
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    try:
        user = await create_user(data)
        # access_token = login_manager.create_access_token(data=dict(sub=user.id))
        # login_manager.set_cookie(response, access_token)
        return JSONResponse(
            {"access_token": "access_token", "token_type": "bearer", "usr": user.id},
            status_code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return JSONResponse(
            {"detail": [{"loc": ["body", "error"], "msg": str(exc)}]},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
