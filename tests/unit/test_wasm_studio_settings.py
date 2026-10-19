import asyncio

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from lnbits.core.crud.settings import update_admin_settings
from lnbits.core.services.settings import dict_to_settings
from lnbits.middleware import AuditMiddleware
from lnbits.settings import UpdateSettings, WasmStudioModel, WasmStudioSettings


def test_wasm_studio_models_are_a_normal_settings_field():
    model = WasmStudioModel(
        name="Test", provider="openai", model="test-model", api_key="secret-key"
    )
    config = WasmStudioSettings(lnbits_wasm_studio_models=[model])
    assert WasmStudioSettings().lnbits_wasm_studio_models == []
    assert "secret-key" not in repr(config)
    parsed = dict_to_settings(config.dict())
    assert parsed.lnbits_wasm_studio_models == [model]
    assert parsed.dict()["lnbits_wasm_studio_models"][0]["api_key"] == "secret-key"


@pytest.mark.parametrize("key", [{}, {"api_key": ""}, {"api_key": "test-key"}])
def test_wasm_studio_model_accepts_optional_api_key(key):
    model = WasmStudioModel(name="Local", provider="ollama", model="local-model", **key)
    assert model.api_key == key.get("api_key", "")


@pytest.mark.anyio
async def test_wasm_studio_settings_audit_omits_api_keys(settings):
    settings.lnbits_audit_log_request_body = True
    settings.lnbits_audit_log_query_params = True

    async def receive():
        raise AssertionError("Settings API keys must never enter audit details")

    request = Request(
        {
            "type": "http",
            "method": "PUT",
            "path": "/admin/api/v1/settings",
            "headers": [],
            "query_string": b"api_key=private-api-key",
        },
        receive,
    )
    middleware = AuditMiddleware(FastAPI(), asyncio.Queue())
    assert await middleware._request_details(request) == "{}"


@pytest.mark.anyio
async def test_wasm_studio_settings_database_errors_do_not_log_keys(mocker):
    mocker.patch("lnbits.core.crud.settings.get_settings_by_tag", return_value={})
    mocker.patch(
        "lnbits.core.crud.settings.set_settings_field",
        side_effect=Exception("SQL parameters: private-api-key"),
    )
    warning = mocker.patch("lnbits.core.crud.settings.logger.warning")
    await update_admin_settings(
        UpdateSettings(
            lnbits_wasm_studio_models=[
                WasmStudioModel(
                    name="Test",
                    provider="openai",
                    model="test-model",
                    api_key="private-api-key",
                )
            ]
        )
    )
    warning.assert_called_once_with(
        "Failed to update settings for 'core.lnbits_wasm_studio_models'."
    )
