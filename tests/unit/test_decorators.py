from uuid import uuid4

import jwt
import pytest
import shortuuid
from fastapi import Request
from fastapi.exceptions import HTTPException
from httpx import AsyncClient
from pydantic.types import UUID4

from lnbits.core.crud.users import delete_account
from lnbits.core.models import User
from lnbits.core.models.users import AccessTokenPayload
from lnbits.decorators import check_user_exists
from lnbits.settings import AuthMethods, Settings, settings


@pytest.mark.anyio
async def test_check_user_exists_with_valid_access_token(
    http_client: AsyncClient, user_alan: User
):
    # Login to get a valid access token
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )
    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json()["access_token"]
    assert access_token is not None

    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    user = await check_user_exists(request, access_token=access_token)

    assert user.id == user_alan.id
    assert request.scope["user_id"] == user.id


@pytest.mark.anyio
async def test_check_user_exists_with_invalid_access_token():
    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    with pytest.raises(HTTPException) as exc_info:
        await check_user_exists(request, access_token="invalid_token")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid access token."


@pytest.mark.anyio
async def test_check_user_exists_with_missing_access_token():
    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    with pytest.raises(HTTPException) as exc_info:
        await check_user_exists(request, access_token=None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing user ID or access token."


@pytest.mark.anyio
async def test_check_user_exists_with_valid_user_id(user_alan: User):
    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    user = await check_user_exists(request, access_token=None, usr=UUID4(user_alan.id))

    assert user.id == user_alan.id


@pytest.mark.anyio
async def test_check_user_exists_with_invalid_user_id():
    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    with pytest.raises(HTTPException) as exc_info:
        await check_user_exists(request, access_token=None, usr=uuid4())
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User not found."


@pytest.mark.anyio
async def test_check_user_exists_with_user_not_allowed(user_alan: User):
    settings.lnbits_admin_users = []
    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    settings.lnbits_allowed_users = ["only_this_user_id"]
    with pytest.raises(HTTPException) as exc_info:
        await check_user_exists(request, access_token=None, usr=UUID4(user_alan.id))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User not allowed."


@pytest.mark.anyio
async def test_check_user_exists_after_user_deletion(http_client: AsyncClient):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    register_response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert register_response.status_code == 200, "User registers OK"
    access_token = register_response.json()["access_token"]
    assert access_token is not None

    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    access_token_payload = AccessTokenPayload(**payload)

    # Get the user ID
    user_id = access_token_payload.usr
    assert user_id, "User ID is not None"

    # Delete the user
    await delete_account(user_id)

    # Attempt to check user existence with the deleted user's access token
    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    with pytest.raises(HTTPException) as exc_info:
        await check_user_exists(request, access_token=access_token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User not found."


@pytest.mark.anyio
async def test_check_user_exists_with_user_id_only_allowed(
    user_alan: User, settings: Settings
):
    settings.auth_allowed_methods = [AuthMethods.user_id_only.value]
    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    user = await check_user_exists(request, access_token=None, usr=UUID4(user_alan.id))

    assert user.id == user_alan.id
    assert request.scope["user_id"] == user.id


@pytest.mark.anyio
async def test_check_user_exists_with_user_id_only_not_allowed(user_alan: User):
    settings.auth_allowed_methods = []
    request = Request({"type": "http", "path": "/some/path", "method": "GET"})
    with pytest.raises(HTTPException) as exc_info:
        await check_user_exists(request, access_token=None, usr=UUID4(user_alan.id))
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing user ID or access token."
