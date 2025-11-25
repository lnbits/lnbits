from typing import Any
from uuid import uuid4

import pytest
import shortuuid
from httpx import AsyncClient

from lnbits.core.models.users import Account, User
from lnbits.core.services.users import create_user_account
from lnbits.settings import Settings
from lnbits.utils.nostr import generate_keypair, hex_to_npub


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
    data: dict[str, str] = {}
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


@pytest.mark.anyio
async def test_update_user_success(http_client: AsyncClient, superuser_token):
    # Create a user first
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"update_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"update_{tiny_id}@lnbits.com",
    }
    create_resp = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    user_id = create_resp.json()["id"]

    # Update the user
    _, pubkey = generate_keypair()
    update_data = {
        "id": user_id,
        "username": f"updated_{tiny_id}",
        "email": f"updated_{tiny_id}@lnbits.com",
        "pubkey": pubkey,
        "external_id": "external_1234",
        "extra": {"provider": "lnbits"},
        "extensions": [],
    }
    resp = await http_client.put(
        f"/users/api/v1/user/{user_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == update_data["username"]
    assert resp.json()["email"] == update_data["email"]
    assert resp.json()["pubkey"] == update_data["pubkey"]
    assert resp.json()["external_id"] == update_data["external_id"]


@pytest.mark.anyio
async def test_update_bad_external_id(
    http_client: AsyncClient, user_alan: User, superuser_token
):
    update_data = {"id": user_alan.id, "external_id": "external 1234"}
    resp = await http_client.put(
        f"/users/api/v1/user/{user_alan.id}",
        json=update_data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert resp.status_code == 400
    assert (
        resp.json()["detail"] == "Invalid external id. "
        "Max length is 256 characters. Space and newlines are not allowed."
    )


@pytest.mark.anyio
async def test_update_user_id_mismatch(http_client: AsyncClient, superuser_token):
    # Create a user first
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"mismatch_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"mismatch_{tiny_id}@lnbits.com",
    }
    create_resp = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    user_id = create_resp.json()["id"]

    # Try to update with mismatched id
    update_data: dict[str, Any] = {
        "id": "wrongid",
        "username": f"updated_{tiny_id}",
        "email": f"updated_{tiny_id}@lnbits.com",
        "extra": {"provider": "lnbits"},
        "extensions": [],
    }
    resp = await http_client.put(
        f"/users/api/v1/user/{user_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "User Id missmatch."


@pytest.mark.anyio
async def test_update_user_password_fields(http_client: AsyncClient, superuser_token):
    # Create a user first
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"pwfield_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"pwfield_{tiny_id}@lnbits.com",
    }
    create_resp = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    user_id = create_resp.json()["id"]

    # Try to update with password fields set
    update_data = {
        "id": user_id,
        "username": f"updated_{tiny_id}",
        "email": f"updated_{tiny_id}@lnbits.com",
        "extra": {"provider": "lnbits"},
        "extensions": [],
        "password": "newpass1234",
        "password_repeat": "newpass1234",
    }
    resp = await http_client.put(
        f"/users/api/v1/user/{user_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Use 'reset password' functionality."


@pytest.mark.anyio
async def test_update_user_invalid_username(http_client: AsyncClient, superuser_token):
    # Create a user first
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"valid_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"valid_{tiny_id}@lnbits.com",
    }
    create_resp = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    user_id = create_resp.json()["id"]

    # Try to update with invalid username
    update_data = {
        "id": user_id,
        "username": "!@#invalid",  # invalid username
        "email": f"valid_{tiny_id}@lnbits.com",
        "extra": {"provider": "lnbits"},
        "extensions": [],
    }
    resp = await http_client.put(
        f"/users/api/v1/user/{user_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid username."


@pytest.mark.anyio
async def test_update_superuser_only_allowed_by_superuser(
    http_client: AsyncClient, user_alan: User, settings: Settings
):
    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    alan_access_token = response.json().get("access_token")
    assert alan_access_token is not None, "Expected access token after login."
    settings.lnbits_admin_users = [user_alan.id]
    update_data: dict[str, Any] = {
        "id": settings.super_user,
        "username": "superadmin",
        "email": "superadmin@lnbits.com",
        "extra": {"provider": "lnbits"},
        "extensions": [],
    }
    resp = await http_client.put(
        f"/users/api/v1/user/{settings.super_user}",
        json=update_data,
        headers={"Authorization": f"Bearer {alan_access_token}"},
    )

    assert resp.json()["detail"] == "Action only allowed for super user."


@pytest.mark.anyio
async def test_create_user_with_npub(http_client: AsyncClient, superuser_token):
    tiny_id = shortuuid.uuid()[:8]
    _, pubkey = generate_keypair()
    data = {
        "username": f"user_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"user_{tiny_id}@lnbits.com",
        "pubkey": hex_to_npub(pubkey),
    }
    create_resp = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["pubkey"] == pubkey


@pytest.mark.anyio
async def test_update_user_npub_success(http_client: AsyncClient, superuser_token):
    # Create a user first
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"update_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"update_{tiny_id}@lnbits.com",
    }
    create_resp = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    user_id = create_resp.json()["id"]

    # Update the user
    _, pubkey = generate_keypair()
    update_data = {
        "id": user_id,
        "username": f"updated_{tiny_id}",
        "email": f"updated_{tiny_id}@lnbits.com",
        "pubkey": hex_to_npub(pubkey),
        "extra": {"provider": "lnbits"},
        "extensions": [],
    }
    resp = await http_client.put(
        f"/users/api/v1/user/{user_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == update_data["username"]
    assert resp.json()["email"] == update_data["email"]
    assert resp.json()["pubkey"] == pubkey


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid_pubkey",
    [
        "npub1flrz7qu87n8y04jwy6r74z44pczcwaesumth08uxrusv4sm7efs83zq8z",
        "4fc62f0387f4ce47d64e2687ea89f5a8702c3bb98736bbbcf30f906561bf653",
    ],
)
async def test_create_user_invalid_npub(
    http_client: AsyncClient, superuser_token, invalid_pubkey
):
    tiny_id = shortuuid.uuid()[:8]
    data = {
        "username": f"user_{tiny_id}",
        "password": "secret1234",
        "password_repeat": "secret1234",
        "email": f"user_{tiny_id}@lnbits.com",
        "pubkey": invalid_pubkey,
    }
    create_resp = await http_client.post(
        "/users/api/v1/user",
        json=data,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 400


@pytest.mark.anyio
async def test_search_users(http_client: AsyncClient, superuser_token):
    namespace_id = shortuuid.uuid()[:8]
    users = []
    user_count = 15
    for index in range(user_count):
        username = f"u_{namespace_id}_{index:03d}"
        user = await create_user_account(
            Account(
                id=uuid4().hex,
                username=username,
                email=f"{username}@lnbits.com",
                pubkey="",
                external_id=None,
            )
        )
        users.append(user)

    create_resp = await http_client.get(
        "/users/api/v1/user?sortby=id&direction=desc",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    create_resp = await http_client.get(
        "/users/api/v1/user"
        f"?sortby=username&direction=desc&username[like]=u_{namespace_id}",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["total"] == user_count
    assert data["data"][0]["username"] == users[user_count - 1].username

    create_resp = await http_client.get(
        "/users/api/v1/user" f"?sortby=username&direction=desc&id={users[0].id}",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["total"] == 1
    assert data["data"][0]["username"] == users[0].username
