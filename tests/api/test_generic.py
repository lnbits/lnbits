import pytest

from lnbits.core.models.users import User


@pytest.mark.anyio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200, f"{response.url} {response.status_code}"


# check GET /wallet: wrong user, expect 400
@pytest.mark.anyio
async def test_get_wallet_with_nonexistent_user(client):
    response = await client.get("wallet", params={"usr": "1"})
    assert response.status_code == 400, f"{response.url} {response.status_code}"


# check GET /wallet: wallet and user
@pytest.mark.anyio
async def test_get_wallet_with_user_and_wallet(client, to_user, to_wallet):
    response = await client.get(
        "wallet", params={"usr": to_user.id, "wal": to_wallet.id}
    )
    assert response.status_code == 200, f"{response.url} {response.status_code}"


# check GET /wallet: wrong wallet and user, expect 400
@pytest.mark.anyio
async def test_get_wallet_with_user_and_wrong_wallet(client, to_user):
    response = await client.get("wallet", params={"usr": to_user.id, "wal": "1"})
    assert response.status_code == 400, f"{response.url} {response.status_code}"


# check GET /extensions: extensions list
@pytest.mark.anyio
async def test_get_extensions(client, to_user):
    response = await client.get("extensions", params={"usr": to_user.id})
    assert response.status_code == 200, f"{response.url} {response.status_code}"


# check GET /extensions: extensions list wrong user, expect 400
@pytest.mark.anyio
async def test_get_extensions_wrong_user(client):
    response = await client.get("extensions", params={"usr": "1"})
    assert response.status_code == 400, f"{response.url} {response.status_code}"


# check GET /extensions: no user given, expect code 400 bad request
@pytest.mark.anyio
async def test_get_extensions_no_user(client):
    response = await client.get("extensions")
    # bad request
    assert response.status_code == 401, f"{response.url} {response.status_code}"


ADMIN_PATHS = [
    "/users",
    "/audit",
    "/node",
    "/admin",
]


# Test admin access to protected paths
@pytest.mark.anyio
@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_admin_paths_access_granted_for_admin(
    client, admin_user: User, path: str
):
    response = await client.post(
        "/api/v1/auth", json={"username": admin_user.username, "password": "secret1234"}
    )

    assert response.status_code == 200, "Admin logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None

    response = await client.get(
        path, headers={"Authorization": f"Bearer {access_token}"}
    )
    assert (
        response.status_code == 200
    ), f"{path} should be accessible for admin, got {response.status_code}"


# Test non-admin access to protected paths
@pytest.mark.anyio
@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_admin_paths_access_denied_for_non_admin(
    client, to_user: User, path: str
):
    client.cookies.clear()
    response = await client.get(path, params={"usr": to_user.id})
    assert response.status_code in (
        401,
        403,
    ), f"{path} should be forbidden for non-admin, got {response.status_code}"
