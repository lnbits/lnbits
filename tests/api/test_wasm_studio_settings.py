import pytest

from lnbits.core.crud.settings import (
    get_settings_field,
    get_super_settings,
    set_settings_field,
)

API = "/admin/api/v1/settings"
PAGE = "/admin/extensions/wasm/studio"
FIELD = "lnbits_wasm_studio_models"


@pytest.fixture(autouse=True)
async def clean_studio_settings(app):
    original = await get_settings_field(FIELD)
    await set_settings_field(FIELD, [])
    yield
    await set_settings_field(FIELD, original.value if original else [])


@pytest.fixture
async def studio_admin_headers(http_client, admin_user):
    login = await http_client.post(
        "/api/v1/auth", json={"username": admin_user.username, "password": "secret1234"}
    )
    assert login.status_code == 200
    http_client.cookies.clear()
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.anyio
async def test_wasm_studio_settings_use_normal_settings_list(
    http_client, studio_admin_headers, superuser_token, settings
):
    secret = "test-studio-api-key-not-for-display"
    models = [
        {
            "name": " Coding assistant ",
            "provider": "openai",
            "model": " coding-model ",
            "api_key": secret,
        },
        {
            "name": "Local coder",
            "provider": "ollama",
            "model": "local/coder:latest",
            "base_url": "http://localhost:11434/v1",
        },
    ]
    saved = await http_client.put(
        API, headers=studio_admin_headers, json={FIELD: models}
    )
    assert saved.status_code == 200, saved.text
    assert secret not in saved.text

    stored = await get_settings_field(FIELD)
    assert stored is not None and stored.value is not None
    assert len(stored.value) == 2
    assert stored.value[0]["api_key"] == secret
    assert settings.lnbits_wasm_studio_models[0].name == "Coding assistant"
    assert settings.lnbits_wasm_studio_models[0].model == "coding-model"
    assert settings.lnbits_wasm_studio_models[1].api_key == ""

    # Standard settings reads and reloads preserve keys for subsequent saves.
    reloaded = await get_super_settings()
    assert reloaded is not None
    assert reloaded.lnbits_wasm_studio_models[0].api_key == secret
    headers = {"Authorization": f"Bearer {superuser_token}"}
    listed = await http_client.get(API, headers=headers)
    assert listed.status_code == 200
    assert listed.json()[FIELD][0]["api_key"] == secret
    assert listed.json()[FIELD][1]["api_key"] == ""
    assert FIELD not in settings.to_public().dict()
    assert secret not in settings.to_public().json()

    page = await http_client.get(PAGE, headers=headers)
    assert page.status_code == 200
    assert 'id="page-wasm-studio"' in page.text
    assert secret not in page.text

    # Updating unrelated settings must preserve the model list and its keys.
    changed = await http_client.put(
        API, headers=headers, json={"lnbits_site_title": settings.lnbits_site_title}
    )
    assert changed.status_code == 200
    listed_again = await http_client.get(API, headers=headers)
    assert listed_again.json()[FIELD] == listed.json()[FIELD]

    remaining = listed.json()[FIELD][1:]
    removed = await http_client.put(API, headers=headers, json={FIELD: remaining})
    assert removed.status_code == 200
    assert (await http_client.get(API, headers=headers)).json()[FIELD] == remaining
    assert settings.lnbits_wasm_studio_models[0].name == "Local coder"

    cleared = await http_client.patch(API, headers=headers, json={FIELD: []})
    assert cleared.status_code == 200
    assert (await http_client.get(API, headers=headers)).json()[FIELD] == []
    assert settings.lnbits_wasm_studio_models == []


@pytest.mark.anyio
@pytest.mark.parametrize("role, status", [("anonymous", 401), ("user", 403)])
async def test_wasm_studio_settings_require_admin(
    http_client, user_headers_from, role, status
):
    headers = user_headers_from if role == "user" else {}
    http_client.cookies.clear()
    for method, url, body in [
        ("GET", PAGE, None),
        ("GET", API, None),
        ("PUT", API, {FIELD: []}),
        ("PATCH", API, {FIELD: []}),
    ]:
        response = await http_client.request(method, url, headers=headers, json=body)
        assert response.status_code == status, (method, url, response.text)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid",
    [
        {"name": "   "},
        {"name": "x" * 101},
        {"provider": "unknown-provider"},
        {"model": ""},
        {"model": "two words"},
        {"base_url": "file:///tmp/model"},
        {"base_url": "https://user:secret@example.com/v1"},
        {"base_url": "http://localhost:99999/v1"},
        {"base_url": "https://example.com/v1?api_key=secret"},
        {"base_url": "https://example.com/v1#fragment"},
        {"api_key": "x" * 4097},
    ],
)
async def test_wasm_studio_settings_validate_input(
    http_client, studio_admin_headers, invalid
):
    model = {
        "name": "Test",
        "provider": "openai",
        "model": "test-model",
        "api_key": "secret-never-in-errors",
        **invalid,
    }
    response = await http_client.put(
        API, headers=studio_admin_headers, json={FIELD: [model]}
    )
    assert response.status_code == 400, response.text
    assert model["api_key"] not in response.text
    listed = await http_client.get(API, headers=studio_admin_headers)
    assert listed.json()[FIELD] == []


@pytest.mark.anyio
async def test_wasm_studio_settings_page_respects_disabled_admin_ui(
    http_client, studio_admin_headers, settings
):
    settings.lnbits_admin_ui = False
    response = await http_client.get(PAGE, headers=studio_admin_headers)
    assert response.status_code == 503
