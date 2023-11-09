from datetime import timedelta
import datetime
from typing import Annotated, Union

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt

from ..crud import create_user
from ..models import CreateUser, User
from ..services import login_manager
from lnbits.settings import settings

user_router = APIRouter()


@user_router.get("/api/v1/user")
async def user(user=Depends(login_manager)) -> User:
    return user


@user_router.post(
    "/api/v1/login", description="Login to the API via the username and password"
)
async def login_endpoint(response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> JSONResponse:
    print("### login_endpoint.form_data", form_data)
    access_token = {"access_token": form_data.username, "token_type": "bearer"}
    print("### access_token", access_token)
    response.set_cookie(key="access_token",value=f"Bearer {access_token}", httponly=True)
    return access_token
    # if usr:
    #     user = await get_user(usr)
    #     if not user:
    #         return JSONResponse(
    #             {"error": "not found"}, status_code=status.HTTP_404_NOT_FOUND
    #         )
    # else:
    #     try:
    #         user = await get_account_by_email(username)
    #         if not user:
    #             return JSONResponse(
    #                 {"error": "not found"}, status_code=status.HTTP_404_NOT_FOUND
    #             )
    #         _ = await load_user(user.id)  # type: ignore
    #         user.login(password)
    #     except Exception as exc:
    #         return JSONResponse(
    #             {"error": str(exc)}, status_code=status.HTTP_401_NOT_FOUND
    #         )
    # access_token = login_manager.create_access_token(data=dict(sub=user.id))
    # login_manager.set_cookie(response, access_token)
    # return JSONResponse(
    #     {"access_token": access_token, "token_type": "bearer"},
    #     status_code=status.HTTP_200_OK,
    # )


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
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
        access_token = login_manager.create_access_token(data=dict(sub=user.id))
        login_manager.set_cookie(response, access_token)
        return JSONResponse(
            {"access_token": access_token, "token_type": "bearer", "usr": user.id},
            status_code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return JSONResponse(
            {"detail": [{"loc": ["body", "error"], "msg": str(exc)}]},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
