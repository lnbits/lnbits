import pytest
import shortuuid
from httpx import AsyncClient


@pytest.mark.anyio
async def test_create_user_success(http_client: AsyncClient, superuser_token):
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"user_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"user_{tiny_id}@lnbits.com",
    }
    response = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    resp = response.json()
    assert resp["username"] == data["username"]
    assert resp["email"] == data["email"]
    assert resp["id"] is not None


@pytest.mark.anyio
async def test_create_user_passwords_do_not_match(
    http_client: AsyncClient, superuser_token
):
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"user_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret0000",
        "email": f"user_{tiny_id}@lnbits.com",
    }
    response = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Passwords do not match."


@pytest.mark.anyio
async def test_create_user_missing_username_with_password(
    http_client: AsyncClient, superuser_token
):
    data = {
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": "nouser@lnbits.com",
    }
    response = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Username required when password provided."


@pytest.mark.anyio
async def test_create_user_no_password_random_generated(
    http_client: AsyncClient, superuser_token
):
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"user_{tiny_id}",
        "email": f"user_{tiny_id}@lnbits.com",
    }
    response = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    resp = response.json()
    assert resp["username"] == data["username"]
    assert resp["email"] == data["email"]
    assert resp["id"] is not None
    assert resp["password"] is not None


@pytest.mark.anyio
async def test_create_user_with_extensions_and_extra(
    http_client: AsyncClient, superuser_token
):
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"user_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"user_{tiny_id}@lnbits.com",
        "extensions": ["testext1", "testext2"],
        "extra": {"provider": "custom", "foo": "bar"},
    }
    response = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    resp = response.json()
    assert resp["username"] == data["username"]
    assert resp["email"] == data["email"]
    assert resp["id"] is not None
    assert resp["extra"]["provider"] == "custom"
    assert "foo" not in resp["extra"], "random fields should not be in extra"


@pytest.mark.anyio
async def test_create_user_minimum_fields(http_client: AsyncClient, superuser_token):
    data = {}
    response = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    resp = response.json()
    assert resp["id"] is not None
    assert resp["extra"]["provider"] == "lnbits"


@pytest.mark.anyio
async def test_create_user_duplicate_username(
    http_client: AsyncClient, superuser_token
):
    tiny_id = shortuuid.uuid()[:8]
    username = f"user_{tiny_id}"
    data = {
        "username": username,
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"user_{tiny_id}@lnbits.com",
    }
    # First creation should succeed
    response1 = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response1.status_code == 200
    # Second creation with same username should fail
    data2 = data.copy()
    data2["email"] = f"other_{tiny_id}@lnbits.com"
    response2 = await http_client.post(
        "/users/api/v1/user",
        json=data2,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response2.status_code == 400 or response2.status_code == 422


@pytest.mark.anyio
async def test_create_user_duplicate_email(http_client: AsyncClient, superuser_token):
    tiny_id = shortuuid.uuid()[:8]
    email = f"user_{tiny_id}@lnbits.com"
    data = {
        "username": f"user_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": email,
    }
    # First creation should succeed
    response1 = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response1.status_code == 200
    # Second creation with same email should fail
    data2 = data.copy()
    data2["username"] = f"other_{tiny_id}"
    response2 = await http_client.post(
        "/users/api/v1/user",
        json=data2,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response2.status_code == 400 or response2.status_code == 422
