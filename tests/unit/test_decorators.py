from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.exceptions import HTTPException
from httpx import AsyncClient
from pydantic.types import UUID4

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.settings import settings


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
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User not allowed."
