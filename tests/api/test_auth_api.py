from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.responses import RedirectResponse
from httpx import AsyncClient

from lnbits.core.crud.users import get_account, update_account
from lnbits.core.models.users import Account
from lnbits.core.services.users import create_user_account
from lnbits.core.views.auth_api import get_account_by_email
from lnbits.settings import Settings


class _FakeSSO:
    def __init__(self, userinfo: object | None = None, state: str = ""):
        self.userinfo = userinfo
        self.state = state
        self.redirect_uri: str | None = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    async def get_login_redirect(self, state: str):
        self.state = state
        return RedirectResponse("https://example.com/sso/login")

    async def verify_and_process(self, _request):
        return self.userinfo


@pytest.mark.anyio
async def test_auth_api_logout_and_update_ui_customization(
    http_client: AsyncClient,
):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )

    response = await http_client.patch(
        f"/api/v1/auth/ui?usr={user.id}",
        json={"theme": "amber", "walletLayout": "grid"},
    )
    assert response.status_code == 200
    assert response.json()["ui_customization"]["theme"] == "amber"
    assert response.json()["ui_customization"]["walletLayout"] == "grid"

    logout = await http_client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["status"] == "success"
    assert "cookie_access_token=" in logout.headers["set-cookie"]


@pytest.mark.anyio
async def test_auth_api_sso_login_and_callback(http_client: AsyncClient, mocker):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )

    provider = "github"
    login_sso = _FakeSSO()
    mocker.patch("lnbits.core.views.auth_api._new_sso", return_value=login_sso)

    response = await http_client.get(
        f"/api/v1/auth/{provider}", params={"user_id": user.id}
    )
    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com/sso/login"
    assert login_sso.redirect_uri == f"{http_client.base_url}/api/v1/auth/github/token"
    assert login_sso.state

    email = f"sso_{uuid4().hex[:8]}@lnbits.com"
    callback_sso = _FakeSSO(userinfo=SimpleNamespace(email=email), state="")
    mocker.patch("lnbits.core.views.auth_api._new_sso", return_value=callback_sso)

    callback = await http_client.get(f"/api/v1/auth/{provider}/token")
    assert callback.status_code == 307
    assert callback.headers["location"] == "/wallet"

    account = await get_account_by_email(email, active_only=False)
    assert account is not None
    assert account.email == email
    assert account.extra.email_verified is True


@pytest.mark.anyio
async def test_auth_api_first_install_success_and_validation(
    http_client: AsyncClient, settings: Settings
):
    superuser = await get_account(settings.super_user, active_only=False)
    assert superuser is not None

    original_username = superuser.username
    original_password_hash = superuser.password_hash
    original_first_install = settings.first_install
    original_first_install_token = settings.first_install_token

    first_install_token = f"install_{uuid4().hex[:8]}"
    new_username = f"reinstall_{uuid4().hex[:8]}"

    try:
        settings.first_install = True
        settings.first_install_token = first_install_token

        missing_token = await http_client.put(
            "/api/v1/auth/first_install",
            json={
                "username": new_username,
                "password": "secret1234",
                "password_repeat": "secret1234",
            },
        )
        assert missing_token.status_code == 401
        assert missing_token.json()["detail"] == "Missing first_install_token."

        success = await http_client.put(
            "/api/v1/auth/first_install",
            json={
                "username": new_username,
                "password": "secret1234",
                "password_repeat": "secret1234",
                "first_install_token": first_install_token,
            },
        )
        assert success.status_code == 200
        assert success.json()["access_token"]
        assert "cookie_access_token=" in success.headers["set-cookie"]
        assert "Secure" not in success.headers["set-cookie"]

        updated_superuser = await get_account(settings.super_user, active_only=False)
        assert updated_superuser is not None
        assert updated_superuser.username == new_username
        assert settings.first_install is False

        forbidden = await http_client.put(
            "/api/v1/auth/first_install",
            json={
                "username": f"blocked_{uuid4().hex[:8]}",
                "password": "secret1234",
                "password_repeat": "secret1234",
            },
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"] == "This is not your first install"
    finally:
        restored_superuser = await get_account(settings.super_user, active_only=False)
        assert restored_superuser is not None
        restored_superuser.username = original_username
        restored_superuser.password_hash = original_password_hash
        await update_account(restored_superuser)
        settings.first_install = original_first_install
        settings.first_install_token = original_first_install_token


@pytest.mark.anyio
async def test_auth_api_first_install_uses_secure_cookie_when_enabled(
    http_client: AsyncClient, settings: Settings
):
    superuser = await get_account(settings.super_user, active_only=False)
    assert superuser is not None

    original_username = superuser.username
    original_password_hash = superuser.password_hash
    original_first_install = settings.first_install
    original_auth_https_only = settings.auth_https_only

    new_username = f"secure_{uuid4().hex[:8]}"

    try:
        settings.first_install = True
        settings.auth_https_only = True

        success = await http_client.put(
            "/api/v1/auth/first_install",
            json={
                "username": new_username,
                "password": "secret1234",
                "password_repeat": "secret1234",
            },
        )

        assert success.status_code == 200
        assert "cookie_access_token=" in success.headers["set-cookie"]
        assert "Secure" in success.headers["set-cookie"]
    finally:
        restored_superuser = await get_account(settings.super_user, active_only=False)
        assert restored_superuser is not None
        restored_superuser.username = original_username
        restored_superuser.password_hash = original_password_hash
        await update_account(restored_superuser)
        settings.first_install = original_first_install
        settings.auth_https_only = original_auth_https_only
