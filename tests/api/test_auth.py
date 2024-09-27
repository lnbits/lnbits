import pytest
from httpx import AsyncClient

from lnbits.core.models import User
from lnbits.settings import AuthMethods, settings


@pytest.mark.asyncio
async def test_login_bad_user(http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": "non_existing_user", "password": "secret1234"}
    )

    assert response.status_code == 401, "User does not exist"
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.asyncio
async def test_login_alan_usr(user_alan: User, http_client: AsyncClient):
    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None, "Expected access token after login."

    response = await http_client.get(
        "/api/v1/auth", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200, "Alan logs in OK."
    alan = response.json()
    assert alan["id"] == user_alan.id
    assert alan["username"] == user_alan.username
    assert alan["email"] == user_alan.email


@pytest.mark.asyncio
async def test_login_usr_not_allowed(user_alan: User, http_client: AsyncClient):
    auth_allowed_methods_initial = [*settings.auth_allowed_methods]

    # exclude 'user_id_only'
    settings.auth_allowed_methods = [AuthMethods.username_and_password.value]

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 401, "Login method not allowed."
    assert response.json().get("detail") == "Login by 'User ID' not allowed."

    settings.auth_allowed_methods = auth_allowed_methods_initial

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})
    assert response.status_code == 200, "Login with 'usr' allowed."
    assert (
        response.json().get("access_token") is not None
    ), "Expected access token after login."


@pytest.mark.asyncio
async def test_login_alan_password_ok(user_alan: User, http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )

    assert response.status_code == 200, "Alan logs in OK"
    assert response.json().get("access_token") is not None


@pytest.mark.asyncio
async def test_login_alan_password_nok(user_alan: User, http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "bad_pasword"}
    )

    assert response.status_code == 401, "User does not exist"
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.asyncio
async def test_login_username_password_not_allowed(
    user_alan: User, http_client: AsyncClient
):

    auth_allowed_methods_initial = [*settings.auth_allowed_methods]

    # exclude 'user_id_only'
    settings.auth_allowed_methods = [AuthMethods.user_id_only.value]

    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )

    assert response.status_code == 401, "Login method not allowed."
    assert (
        response.json().get("detail") == "Login by 'Username and Password' not allowed."
    )

    settings.auth_allowed_methods = auth_allowed_methods_initial

    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )
    assert response.status_code == 200, "Username and password is allowed."
    assert response.json().get("access_token") is not None


@pytest.mark.asyncio
async def test_register_ok(http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": "u21",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": "u21@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    assert response.json().get("access_token") is not None
