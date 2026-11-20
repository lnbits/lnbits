"""Funding settings authorization, with real routes/CRUD and synthetic storage."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from lnbits.core.crud import settings as settings_crud
from lnbits.core.models.users import AccessTokenPayload, Account
from lnbits.core.views import admin_api
from lnbits.decorators import access_token_payload, check_account_exists
from lnbits.settings import (
    FundingSourcesSettings,
    SuperSettings,
    UpdateSettings,
    settings,
)

FUNDING_DEFAULTS = FundingSourcesSettings().model_dump()


@pytest.fixture
def funding_api(monkeypatch):
    monkeypatch.setattr(settings, "super_user", "super")
    monkeypatch.setattr(settings, "lnbits_admin_users", ["admin"])
    monkeypatch.setattr(settings, "lnbits_allow_onchain_payments", False)
    stored = UpdateSettings(
        lnbits_backend_wallet_class="LndRestWallet",
        lnd_rest_macaroon="synthetic-macaroon",
        spark_l2_mnemonic="synthetic-spark-seed",
        phoenixd_mnemonic="synthetic-phoenix-seed",
        lnbits_site_title="Original title",
    ).model_dump()
    state = {"role": "admin", "stored": stored}

    async def read_super_settings():
        return SuperSettings(super_user="super", **stored)

    async def read_tag(_tag):
        return dict(stored)

    async def write_field(key, value, _tag=None):
        stored[key] = value

    async def account():
        if state["role"] == "anonymous":
            raise HTTPException(401, "Authentication required")
        return Account(
            id=state["role"], username=state["role"], password_hash="synthetic-hash"
        )

    app = FastAPI()
    app.include_router(admin_api.admin_router)
    # Exercise the actual admin permission check; stub only authentication lookup.
    app.dependency_overrides[check_account_exists] = account
    app.dependency_overrides[access_token_payload] = lambda: AccessTokenPayload(
        sub=state["role"], usr=state["role"]
    )
    monkeypatch.setattr(settings_crud, "get_super_settings", read_super_settings)
    monkeypatch.setattr(admin_api, "get_super_settings", read_super_settings)
    monkeypatch.setattr(settings_crud, "get_settings_by_tag", read_tag)
    writer = AsyncMock(side_effect=write_field)
    monkeypatch.setattr(settings_crud, "set_settings_field", writer)
    monkeypatch.setattr(
        admin_api, "validate_two_factor_policy", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(admin_api, "enqueue_admin_notification", Mock())
    monkeypatch.setattr(
        admin_api.core_app_extra, "register_new_ratelimiter", Mock(), raising=False
    )
    cache = Mock()
    monkeypatch.setattr(admin_api, "update_cached_settings", cache)
    # Defaults can contain environment credentials. Never read real .env secrets.
    defaults = Mock(return_value=UpdateSettings(**stored))
    monkeypatch.setattr(admin_api, "Settings", defaults)
    state.update(writer=writer, cache=cache, defaults=defaults)
    return app, state


def request(app, method, path="/admin/api/v1/settings", **kwargs):
    async def run():
        async with AsyncClient(
            transport=ASGITransport(app), base_url="http://test"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("super", 200), ("user", 403), ("anonymous", 401)]
)
def test_funding_settings_read_access(funding_api, role, status):
    app, state = funding_api
    state["role"] = role
    response = request(app, "GET")
    assert response.status_code == status
    if status == 200:
        assert response.headers["cache-control"] == "no-store"
        data = response.json()
        assert data["lnbits_site_title"] == "Original title"
        for field in FundingSourcesSettings.model_fields:
            assert (field in data) is (role == "super")
        if role == "super":
            assert data["lnd_rest_macaroon"] == "synthetic-macaroon"
    if role != "super":
        assert "synthetic-" not in response.text
    state["writer"].assert_not_awaited()


@pytest.mark.parametrize("field", FUNDING_DEFAULTS)
@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_admin_cannot_write_any_funding_field(funding_api, field, method):
    app, state = funding_api
    before = dict(state["stored"])
    response = request(app, method, json={field: FUNDING_DEFAULTS[field]})
    assert response.status_code == 403
    assert state["stored"] == before
    state["writer"].assert_not_awaited()
    state["cache"].assert_not_called()


@pytest.mark.parametrize("field", FUNDING_DEFAULTS)
def test_admin_cannot_read_any_funding_default(funding_api, field):
    app, state = funding_api
    response = request(
        app, "GET", "/admin/api/v1/settings/default", params={"field_name": field}
    )
    assert response.status_code == 403
    state["defaults"].assert_not_called()


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_superuser_can_update_all_funding_fields(funding_api, method):
    app, state = funding_api
    state["role"] = "super"
    values = {**FUNDING_DEFAULTS, "lnd_rest_macaroon": "synthetic-new-macaroon"}
    response = request(app, method, json=values)
    assert response.status_code == 200, response.text
    for key, value in values.items():
        assert state["stored"][key] == value
    response = request(app, "GET")
    assert response.json()["lnd_rest_macaroon"] == "synthetic-new-macaroon"


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_admin_unrelated_save_preserves_all_funding_settings(funding_api, method):
    app, state = funding_api
    before = {key: state["stored"][key] for key in FUNDING_DEFAULTS}
    if method == "PUT":
        # Match the admin page: it saves the settings it received, minus metadata.
        data = request(app, "GET").json()
        for key in ("is_super_user", "lnbits_allowed_funding_sources", "touch"):
            data.pop(key, None)
    else:
        data = {}
    data["lnbits_site_title"] = "New title"
    response = request(app, method, json=data)
    assert response.status_code == 200, response.text
    assert state["stored"]["lnbits_site_title"] == "New title"
    for key, value in before.items():
        assert state["stored"][key] == value
        assert state["cache"].call_args.args[0][key] == value


def test_default_permissions(funding_api):
    app, state = funding_api
    response = request(
        app,
        "GET",
        "/admin/api/v1/settings/default",
        params={"field_name": "lnbits_site_title"},
    )
    assert response.status_code == 200
    assert response.json()["default_value"] == "Original title"
    state["role"] = "super"
    response = request(
        app,
        "GET",
        "/admin/api/v1/settings/default",
        params={"field_name": "lnd_rest_macaroon"},
    )
    assert response.status_code == 200
    assert response.json()["default_value"] == "synthetic-macaroon"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("role", ["user", "anonymous"])
@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_non_admin_cannot_update_settings(funding_api, role, method):
    app, state = funding_api
    state["role"] = role
    response = request(app, method, json={"lnbits_site_title": "Changed"})
    assert response.status_code in (401, 403)
    state["writer"].assert_not_awaited()


@pytest.mark.parametrize("is_super_user", [False, True])
def test_crud_filters_funding_settings_by_role(funding_api, is_super_user):
    _, state = funding_api
    before = dict(state["stored"])
    result = asyncio.run(settings_crud.get_admin_settings(is_super_user))
    assert result is not None
    data = result.model_dump(exclude_unset=True)
    assert data["is_super_user"] is is_super_user
    assert data["lnbits_site_title"] == "Original title"
    for field in FundingSourcesSettings.model_fields:
        assert (field in data) is is_super_user
    assert ("lnbits_allowed_funding_sources" in data) is is_super_user
    assert "super_user" not in data
    assert state["stored"] == before


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_admin_save_preserves_live_funding_configuration(
    funding_api, monkeypatch, method
):
    from lnbits.core.services.settings import update_cached_settings

    app, state = funding_api
    # Restore every setting that the real cache refresh can update after the test.
    for field in UpdateSettings.model_fields:
        monkeypatch.setattr(settings, field, getattr(settings, field))
    monkeypatch.setattr(admin_api, "update_cached_settings", update_cached_settings)
    response = request(app, method, json={"lnbits_site_title": "Cache check"})
    assert response.status_code == 200
    assert settings.lnbits_site_title == "Cache check"
    for field in FundingSourcesSettings.model_fields:
        assert getattr(settings, field) == state["stored"][field]
    assert settings.super_user == "super"
