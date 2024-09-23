import pytest
from httpx import AsyncClient

from lnbits.core.models import User


@pytest.mark.asyncio
async def test_login_bad_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth", json={"username": "non_existing_user", "password": "secret1234"}
    )

    assert response.status_code == 401, "User does not exist"
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.asyncio
async def test_login_alan_password_ok(user_alan: User, client: AsyncClient):
    response = await client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )

    assert response.status_code == 200, "Alan logs in OK"
    assert response.json().get("access_token") is not None


@pytest.mark.asyncio
async def test_login_alan_usr(user_alan: User, client: AsyncClient):
    response = await client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK"
    assert response.json().get("access_token") is not None


@pytest.mark.asyncio
async def test_login_alan_password_nok(user_alan: User, client: AsyncClient):
    response = await client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "bad_pasword"}
    )

    assert response.status_code == 401, "User does not exist"
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.asyncio
async def test_register_ok(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth",
        json={
            "username": "u21",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": "u21@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    assert response.json().get("access_token") is not None
