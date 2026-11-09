from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from lnbits.core.models import Account
from lnbits.core.models.users import RegisterUser
from lnbits.core.services import users
from lnbits.core.views import api, auth_api
from lnbits.settings import AuthMethods, UsersSettings


def test_public_registration_defaults_to_disabled():
    assert UsersSettings.model_fields["lnbits_allow_new_accounts"].default is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    "restriction", ["closed", "auth_method", "activation", "allowlist"]
)
async def test_anonymous_account_endpoint_rejects_restricted_registration(
    settings, monkeypatch, restriction
):
    if restriction == "closed":
        settings.lnbits_allow_new_accounts = False
    elif restriction == "auth_method":
        settings.auth_allowed_methods = [AuthMethods.username_and_password.value]
    elif restriction == "activation":
        settings.lnbits_require_user_activation = True
        settings.lnbits_user_activation_by_invitation_code = True
    else:
        settings.lnbits_allowed_users = ["existing-user"]
    create = AsyncMock()
    monkeypatch.setattr(api, "create_user_account", create)
    app = FastAPI()
    app.include_router(api.api_router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/account", json={"name": "wallet"})
    assert response.status_code == 403
    create.assert_not_awaited()


@pytest.mark.anyio
async def test_anonymous_account_endpoint_explicit_opt_in(settings, monkeypatch):
    settings.lnbits_allow_new_accounts = True
    settings.auth_allowed_methods = [AuthMethods.user_id_only.value]
    monkeypatch.setattr(
        users,
        "create_user_account_no_ckeck",
        AsyncMock(return_value=SimpleNamespace(wallets=[{"id": "new-wallet"}])),
    )
    app = FastAPI()
    app.include_router(api.api_router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/account", json={"name": "wallet"})
    assert response.status_code == 200
    assert response.json()["id"] == "new-wallet"


@pytest.mark.anyio
@pytest.mark.parametrize("account", [None, Account(id="a" * 32, username="newuser")])
async def test_shared_account_creation_requires_activation(
    settings, monkeypatch, account
):
    settings.lnbits_require_user_activation = True
    create = AsyncMock()
    monkeypatch.setattr(users, "create_user_account_no_ckeck", create)
    with pytest.raises(ValueError, match="invitation or activation"):
        await users.create_user_account(account)
    create.assert_not_awaited()


@pytest.mark.anyio
async def test_closed_registration_does_not_consume_invitation(settings, monkeypatch):
    settings.lnbits_allow_new_accounts = False
    settings.lnbits_register_one_time_activation_codes = ["one-use"]
    check = AsyncMock()
    monkeypatch.setattr(auth_api, "check_register_activation_settings", check)
    with pytest.raises(HTTPException) as exc:
        await auth_api.register(_registration("one-use"))
    assert exc.value.status_code == 403
    assert settings.lnbits_register_one_time_activation_codes == ["one-use"]
    check.assert_not_awaited()


@pytest.mark.anyio
async def test_registration_consumes_valid_invitation_once(settings, monkeypatch):
    settings.lnbits_require_user_activation = True
    settings.lnbits_user_activation_by_invitation_code = True
    settings.lnbits_register_one_time_activation_codes = ["one-use"]
    monkeypatch.setattr(
        auth_api, "get_account_by_username", AsyncMock(return_value=None)
    )
    persist = AsyncMock()
    monkeypatch.setattr(users, "set_settings_field", persist)
    create = AsyncMock()
    monkeypatch.setattr(users, "create_user_account_no_ckeck", create)
    login = AsyncMock()
    monkeypatch.setattr(auth_api, "_login_response", login)

    for code in (None, "invalid"):
        with pytest.raises(ValueError, match="[Ii]nvitation"):
            await auth_api.register(_registration(code))
    create.assert_not_awaited()
    await auth_api.register(_registration("one-use"))
    create.assert_awaited_once()
    login.assert_awaited_once()
    assert settings.lnbits_register_one_time_activation_codes == []
    persist.assert_awaited_once_with("lnbits_register_one_time_activation_codes", [])
    with pytest.raises(ValueError, match="Invalid invitation"):
        await auth_api.register(_registration("one-use"))
    assert create.await_count == 1


def _registration(code):
    return RegisterUser(
        username="newuser",
        password="password123",
        password_repeat="password123",
        invitation_code=code,
    )
