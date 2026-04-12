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
from lnbits.decorators import (
    access_token_payload,
    check_access_token,
    check_admin_ui,
    check_extension_builder,
    check_first_install,
    check_user_exists,
    optional_user_id,
)
from lnbits.helpers import create_access_token
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


@pytest.mark.anyio
async def test_check_access_token_prefers_available_source():
    assert await check_access_token("header", "cookie", "bearer") == "header"
    assert await check_access_token(None, "cookie", "bearer") == "cookie"
    assert await check_access_token(None, None, "bearer") == "bearer"


@pytest.mark.anyio
async def test_access_token_payload_success_and_missing(settings: Settings):
    token = create_access_token({"sub": "alice", "usr": "user-id"})

    payload = await access_token_payload(token)

    assert isinstance(payload, AccessTokenPayload)
    assert payload.sub == "alice"
    assert payload.usr == "user-id"

    with pytest.raises(HTTPException, match="Missing access token."):
        await access_token_payload(None)


@pytest.mark.anyio
async def test_optional_user_id_uses_user_id_or_access_token(
    user_alan: User, settings: Settings
):
    settings.auth_allowed_methods = [AuthMethods.user_id_only.value]
    request = Request({"type": "http", "path": "/wallet", "method": "GET"})

    assert (
        await optional_user_id(request, access_token=None, usr=UUID4(user_alan.id))
        == user_alan.id
    )

    settings.auth_allowed_methods = []
    token = create_access_token({"sub": user_alan.username, "usr": user_alan.id})
    assert await optional_user_id(request, access_token=token, usr=None) == user_alan.id
    assert await optional_user_id(request, access_token=None, usr=None) is None


@pytest.mark.anyio
async def test_check_admin_ui_and_first_install(settings: Settings):
    original_admin_ui = settings.lnbits_admin_ui
    original_first_install = settings.first_install
    try:
        settings.lnbits_admin_ui = False
        with pytest.raises(HTTPException, match="Admin UI is disabled."):
            await check_admin_ui()

        settings.lnbits_admin_ui = True
        await check_admin_ui()

        settings.first_install = False
        with pytest.raises(
            HTTPException, match="Super user account has already been configured."
        ):
            await check_first_install()

        settings.first_install = True
        await check_first_install()
    finally:
        settings.lnbits_admin_ui = original_admin_ui
        settings.first_install = original_first_install


@pytest.mark.anyio
async def test_check_extension_builder_requires_admin_when_disabled_for_users(
    settings: Settings, user_alan: User
):
    settings.lnbits_extensions_builder_activate_non_admins = False

    with pytest.raises(
        HTTPException, match="Extension Builder is disabled for non admin users."
    ):
        await check_extension_builder(user_alan)

    admin_user = user_alan.copy(deep=True)
    admin_user.admin = True
    await check_extension_builder(admin_user)
