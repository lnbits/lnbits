from uuid import uuid4

import pytest

from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models.users import Account, AccountId
from lnbits.core.services.users import create_user_account
from lnbits.helpers import sha256s
from lnbits.settings import AuthMethods
from lnbits.utils.cache import cache

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("cache_minutes", [0, 5])
@pytest.mark.parametrize("with_username", [False, True])
async def test_password_accounts_reject_user_id_authentication(
    http_client, settings, cache_minutes, with_username
):
    settings.auth_authentication_cache_minutes = cache_minutes
    settings.auth_allowed_methods = [
        AuthMethods.username_and_password.value,
        AuthMethods.user_id_only.value,
    ]
    account = Account(
        id=uuid4().hex,
        username=f"password_{uuid4().hex[:8]}" if with_username else None,
    )
    account.hash_password("secret1234")
    user = await create_user_account(account)
    wallet = user.wallets[0]
    # A cache entry created before the account had a password must not grant access.
    cache_key = f"auth:user_id:{sha256s(user.id)}"
    cache.set(cache_key, AccountId(id=user.id))
    try:
        response = await http_client.post("/api/v1/auth/usr", json={"usr": user.id})
        assert response.status_code == 403
        assert response.json()["detail"] == "This account requires password login."
        assert "access_token" not in response.json()
        assert "cookie_access_token" not in response.cookies

        for method, path in (
            ("GET", "/api/v1/auth"),
            ("GET", "/api/v1/wallets"),
            ("GET", "/api/v1/status"),
            ("PUT", f"/api/v1/wallet/reset/{wallet.id}"),
        ):
            response = await http_client.request(method, path, params={"usr": user.id})
            assert response.status_code == 403
            assert response.json()["detail"] == "This account requires password login."
        stored = await get_wallet(wallet.id)
        assert stored
        assert (stored.adminkey, stored.inkey) == (wallet.adminkey, wallet.inkey)
    finally:
        cache.pop(cache_key)


@pytest.mark.parametrize("token_source", ["cookie", "header"])
async def test_password_login_session_allows_user_id_query(http_client, token_source):
    account = Account(id=uuid4().hex, username=f"session_{uuid4().hex[:8]}")
    account.hash_password("secret1234")
    user = await create_user_account(account)
    response = await http_client.post(
        "/api/v1/auth", json={"username": user.username, "password": "secret1234"}
    )
    assert response.status_code == 200
    headers = {}
    if token_source == "header":
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        http_client.cookies.clear()
    response = await http_client.get(
        "/api/v1/wallets", params={"usr": user.id}, headers=headers
    )
    assert response.status_code == 200
    wallets = {wallet["id"]: wallet for wallet in response.json()}
    wallet = user.wallets[0]
    assert wallets[wallet.id]["adminkey"] == wallet.adminkey
    assert wallets[wallet.id]["inkey"] == wallet.inkey


@pytest.mark.parametrize("cache_minutes", [0, 5])
async def test_adding_password_revokes_user_id_access(
    http_client, settings, cache_minutes
):
    settings.auth_authentication_cache_minutes = cache_minutes
    user = await create_user_account()
    for path in ("/api/v1/wallets", "/api/v1/status"):
        response = await http_client.get(path, params={"usr": user.id})
        assert response.status_code == 200
    response = await http_client.post("/api/v1/auth/usr", json={"usr": user.id})
    assert response.status_code == 200
    # Populate the session cache as well before adding credentials.
    assert (await http_client.get("/api/v1/status")).status_code == 200
    response = await http_client.put(
        "/api/v1/auth/password",
        json={
            "user_id": user.id,
            "username": f"new_pass_{uuid4().hex[:8]}",
            "password": "secret1234",
            "password_repeat": "secret1234",
        },
    )
    assert response.status_code == 200
    http_client.cookies.clear()
    response = await http_client.post("/api/v1/auth/usr", json={"usr": user.id})
    assert response.status_code == 403
    for method, path in (
        ("GET", "/api/v1/wallets"),
        ("GET", "/api/v1/status"),
        ("PUT", f"/api/v1/wallet/reset/{user.wallets[0].id}"),
    ):
        response = await http_client.request(method, path, params={"usr": user.id})
        assert response.status_code == 403
        assert response.json()["detail"] == "This account requires password login."
