import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from wasmtime import wat2wasm

from lnbits.app import build_all_installed_extensions_list
from lnbits.core.crud.extensions import (
    create_installed_extension,
    delete_installed_extension,
    get_installed_extensions,
    get_user_extension,
    get_wasm_invocations,
    update_installed_extension,
)
from lnbits.core.crud.scheduler import delete_namespace_schedules, get_scheduled_job
from lnbits.core.db import core_app_extra
from lnbits.core.models.extensions import ExtensionPermission, InstallableExtension
from lnbits.core.services.scheduler import scheduler
from lnbits.core.views import extension_api
from lnbits.core.wasm_ext.storage.crud import (
    migrate_wasm_extension_database,
    storage_get_row,
    storage_set_row,
)
from lnbits.core.wasm_ext.wasm.events import dispatch_wasm_invoice_paid
from lnbits.core.wasm_ext.wasm.scheduler import dispatch_wasm_schedule
from lnbits.helpers import sha256s


@pytest.fixture
async def studio_source(app, tmp_path, settings, mocker):
    mocker.patch.object(settings, "lnbits_data_folder", str(tmp_path))
    mocker.patch.object(
        settings, "lnbits_wasm_extensions_path", str(tmp_path / "installed")
    )
    mocker.patch.object(settings, "lnbits_extensions_deactivate_all", False)
    source_id = f"studio_{uuid4().hex[:8]}"
    root = settings.wasm_extensions_dir / source_id
    _write_extension(root, source_id)
    source = InstallableExtension(
        id=source_id,
        name="Studio test",
        version="1.0",
        active=True,
        permissions=[
            ExtensionPermission(id="ext.storage.read"),
            ExtensionPermission(id="ext.storage.write"),
        ],
    )
    await create_installed_extension(source)
    await migrate_wasm_extension_database(source)
    await storage_set_row(
        source.id, "items", {"id": "live", "value": "original"}, "owner"
    )
    opening = mocker.spy(extension_api, "open_wasm_studio")
    yield source
    await delete_installed_extension(ext_id=source.id)
    if opening.call_args:
        application = opening.call_args.args[0]
        prefix = source.id + "_"
        for extension in core_app_extra.wasm_extension_registry.list():
            if extension.id.startswith(prefix):
                core_app_extra.wasm_extension_registry.unregister(extension.id)
                scheduler.unregister(f"extension:{extension.id}")
                await delete_namespace_schedules(f"extension:{extension.id}")
        application.router.routes[:] = [
            route
            for route in application.router.routes
            if not str(getattr(route, "name", "")).startswith(prefix)
        ]
        application.openapi_schema = None


@pytest.mark.anyio
async def test_wasm_studio_copies_once_isolates_storage_and_reopens(
    studio_source, http_client, superuser_token, settings, tmp_path
):
    source = studio_source
    headers = {"Authorization": f"Bearer {superuser_token}"}
    url = f"/api/v1/extension/{source.id}/studio"
    responses = await asyncio.gather(
        http_client.post(url, headers=headers), http_client.post(url, headers=headers)
    )
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()
    draft_id = f"{source.id}_{sha256s(settings.super_user)}"
    assert responses[0].json()["preview_path"] == f"/ext/{draft_id}"
    workspace = tmp_path / "wasm_studio" / sha256s(settings.super_user) / source.id
    assert (workspace / "ext" / "config.json").read_bytes() == (
        source.wasm_ext_dir / "config.json"
    ).read_bytes()
    assert (workspace / "data" / "extension.sqlite3").is_file()
    assert await storage_get_row(draft_id, "items", "live", "owner") is None
    await storage_set_row(
        draft_id, "items", {"id": "draft", "value": "edited"}, "owner"
    )
    assert await storage_get_row(source.id, "items", "draft", "owner") is None
    live_row = await storage_get_row(source.id, "items", "live", "owner")
    assert live_row and live_row["value"] == "original"
    user_extension = await get_user_extension(settings.super_user, draft_id)
    assert user_extension and user_extension.permissions == {}

    # A restart forgets registrations, but must retain code and draft data.
    marker = workspace / "ext" / "draft.txt"
    marker.write_text("keep this edit")
    core_app_extra.wasm_extension_registry.unregister(draft_id)
    scheduler.unregister(f"extension:{draft_id}")
    installed = await build_all_installed_extensions_list()
    assert draft_id not in {extension.id for extension in installed}
    assert core_app_extra.wasm_extension_registry.get(draft_id) is None
    reopened = await http_client.post(url, headers=headers)
    assert reopened.status_code == 200
    assert marker.read_text() == "keep this edit"
    draft_row = await storage_get_row(draft_id, "items", "draft", "owner")
    assert draft_row and draft_row["value"] == "edited"
    assert draft_id not in {
        extension.id for extension in await get_installed_extensions()
    }


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["anonymous", "user", "admin"])
async def test_wasm_studio_requires_admin_on_all_http_surfaces(
    studio_source, http_client, superuser_token, user_headers_from, role
):
    admin_headers = {"Authorization": f"Bearer {superuser_token}"}
    url = f"/api/v1/extension/{studio_source.id}/studio"
    created = await http_client.post(url, headers=admin_headers)
    assert created.status_code == 200
    draft_id = created.json()["id"]
    http_client.cookies.clear()
    headers = (
        admin_headers
        if role == "admin"
        else user_headers_from if role == "user" else {}
    )
    expected = {"anonymous": 401, "user": 403, "admin": 200}[role]
    requests = [
        ("POST", url, {}),
        ("GET", f"/ext/{draft_id}", None),
        ("GET", f"/ext/{draft_id}/public", None),
        ("GET", f"/api/v1/ext/{draft_id}/public", None),
        ("POST", f"/api/v1/ext/{draft_id}/_ui/frame", {"path": f"/ext/{draft_id}"}),
        ("GET", f"/api/v1/extension/{draft_id}/permissions", None),
    ]
    for method, path, body in requests:
        response = await http_client.request(method, path, json=body, headers=headers)
        assert response.status_code == expected, (path, response.text)
    # The compiled component executes through the real runtime and invocation log.
    if role == "admin":
        response = await http_client.get(
            f"/api/v1/ext/{draft_id}/public", headers=headers
        )
        assert response.json() == {"ok": True}
    for path in (f"/ext-frame/{draft_id}/0", f"/ext-assets/{draft_id}/app.js"):
        response = await http_client.get(path, headers=headers)
        assert response.status_code in ({401, 403, 404} if role != "admin" else {404})


@pytest.mark.anyio
async def test_wasm_studio_serves_private_sandbox_assets_without_changing_source(
    studio_source, http_client, superuser_token, settings, mocker
):
    headers = {"Authorization": f"Bearer {superuser_token}"}
    created = await http_client.post(
        f"/api/v1/extension/{studio_source.id}/studio", headers=headers
    )
    draft_id = created.json()["id"]
    config = await http_client.post(
        f"/api/v1/ext/{draft_id}/_ui/frame",
        json={"path": f"/ext/{draft_id}"},
        headers=headers,
    )
    assert config.status_code == 200
    assert config.json()["bridge"]["sourceExtensionId"] == studio_source.id
    frame = await http_client.get(config.json()["frameUrl"], headers=headers)
    assert frame.status_code == 200
    assert (
        "sandbox allow-scripts allow-pointer-lock"
        in frame.headers["content-security-policy"]
    )
    asset_match = re.search(r'src="([^"]+)"', frame.text)
    assert asset_match
    asset_url = asset_match[1]
    assert asset_url.startswith(f"/ext-assets/{draft_id}/")
    assert (
        studio_source.id + "/app.js"
        in (studio_source.wasm_ext_dir / "ui.html").read_text()
    )
    # The opaque sandbox cannot send SameSite login cookies. Only its scoped
    # asset capability is accepted, and cannot authorize API requests.
    http_client.cookies.clear()
    asset = await http_client.get(asset_url)
    assert asset.status_code == 200
    assert f"/api/v1/ext/{draft_id}/public" in asset.text
    assert asset.headers["cache-control"] == "no-store"
    assert (await http_client.get(f"/api/v1/ext/{draft_id}/public")).status_code == 401
    # Revoking admin access also revokes previously issued asset capabilities.
    mocker.patch.object(settings, "super_user", "no-longer-admin")
    assert (await http_client.get(asset_url)).status_code == 403


@pytest.mark.anyio
async def test_wasm_studio_keeps_each_admin_workspace_separate(
    studio_source, http_client, superuser_token, admin_user
):
    url = f"/api/v1/extension/{studio_source.id}/studio"
    first = await http_client.post(
        url, headers={"Authorization": f"Bearer {superuser_token}"}
    )
    login = await http_client.post(
        "/api/v1/auth", json={"username": admin_user.username, "password": "secret1234"}
    )
    assert login.status_code == 200
    second = await http_client.post(
        url, headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    await storage_set_row(
        first.json()["id"], "items", {"id": "private", "value": "one"}, "owner"
    )
    assert (
        await storage_get_row(second.json()["id"], "items", "private", "owner") is None
    )


@pytest.mark.anyio
async def test_wasm_studio_rejects_unknown_extensions_and_symlinks(
    studio_source, http_client, superuser_token, tmp_path, settings
):
    headers = {"Authorization": f"Bearer {superuser_token}"}
    assert (
        await http_client.post("/api/v1/extension/missing/studio", headers=headers)
    ).status_code == 404
    assert (
        await http_client.post("/api/v1/extension/invalid.id/studio", headers=headers)
    ).status_code == 400
    outside = tmp_path / "outside"
    outside.mkdir()
    (studio_source.wasm_ext_dir / "linked").symlink_to(outside)
    response = await http_client.post(
        f"/api/v1/extension/{studio_source.id}/studio", headers=headers
    )
    assert response.status_code == 400
    assert str(tmp_path) not in response.text
    draft_id = f"{studio_source.id}_{sha256s(settings.super_user)}"
    assert core_app_extra.wasm_extension_registry.get(draft_id) is None


@pytest.mark.anyio
async def test_wasm_studio_runs_schedules_and_payment_listeners(
    studio_source, http_client, superuser_token
):
    source = studio_source
    config_path = source.wasm_ext_dir / "config.json"
    config = json.loads(config_path.read_text())
    policy = {"handler": "tick", "cron_expression": "* * * * *", "timezone": "UTC"}
    config["schedules"] = [policy]
    config_path.write_text(json.dumps(config))
    source.permissions.append(
        ExtensionPermission(id="scheduler.extension", policies=[policy])
    )
    await update_installed_extension(source)
    response = await http_client.post(
        f"/api/v1/extension/{source.id}/studio",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    draft_id = response.json()["id"]
    assert (f"extension:{draft_id}", "tick") in scheduler.handlers
    job = await get_scheduled_job(sha256s(json.dumps([draft_id, None, "tick"])))
    assert job and job.namespace == f"extension:{draft_id}"
    await dispatch_wasm_schedule(job)
    payment = SimpleNamespace(
        extension=draft_id,
        extra={},
        tag=None,
        wallet_id="missing-test-wallet",
        payment_hash="studio-test",
        checking_id="studio-test",
        amount=1000,
        fee=0,
        bolt11="",
        memo="",
        pending=False,
        status="success",
        json=lambda: "{}",
    )
    await dispatch_wasm_invoice_paid(payment)
    invocations = await get_wasm_invocations(extension_id=draft_id)
    assert {invocation.trigger_type for invocation in invocations} == {
        "schedule",
        "event",
    }
    assert all(invocation.status == "completed" for invocation in invocations)
    assert not await get_wasm_invocations(extension_id=source.id)


@pytest.mark.anyio
async def test_wasm_studio_failed_load_removes_routes_and_can_retry(
    studio_source, http_client, superuser_token, settings, tmp_path
):
    entrypoint = studio_source.wasm_ext_dir / "ui.html"
    html = entrypoint.read_text()
    entrypoint.unlink()
    headers = {"Authorization": f"Bearer {superuser_token}"}
    url = f"/api/v1/extension/{studio_source.id}/studio"
    response = await http_client.post(url, headers=headers)
    assert response.status_code == 400
    draft_id = f"{studio_source.id}_{sha256s(settings.super_user)}"
    assert core_app_extra.wasm_extension_registry.get(draft_id) is None
    assert (
        await http_client.post(f"/api/v1/ext/{draft_id}/_ui/frame", json={})
    ).status_code == 404
    workspace = (
        tmp_path / "wasm_studio" / sha256s(settings.super_user) / studio_source.id
    )
    (workspace / "ext" / "ui.html").write_text(html)
    assert (await http_client.post(url, headers=headers)).status_code == 200


def _write_extension(root: Path, ext_id: str) -> None:
    (root / "static").mkdir(parents=True)
    (root / "storage" / "migrations").mkdir(parents=True)
    config = {
        "id": ext_id,
        "name": "Studio test",
        "short_description": "Draft testing",
        "version": "1.0",
        "extension_type": "wasm",
        "wasm": {
            "module": "module.wasm",
            "exports": [
                {"name": "run", "visibility": "public"},
                {"name": "tick", "visibility": "event"},
            ],
        },
        "events": {"onInvoicePaid": "tick"},
        "ui_routes": [
            {"path": f"/{ext_id}", "entrypoint": "ui.html", "auth": "user"},
            {"path": f"/{ext_id}/public", "entrypoint": "ui.html", "auth": "public"},
        ],
        "api_routes": [
            {"method": "GET", "path": "/public", "export": "run", "auth": "public"}
        ],
    }
    (root / "config.json").write_text(json.dumps(config))
    (root / "ui.html").write_text(
        f'<html><script src="/ext-assets/{ext_id}/app.js"></script></html>'
    )
    (root / "static" / "app.js").write_text(
        f'const path = "/api/v1/ext/{ext_id}/public";'
    )
    fields = [{"name": "id", "type": "string"}, {"name": "value", "type": "string"}]
    (root / "storage" / "schema.json").write_text(
        json.dumps({"tables": {"items": {"fields": fields}}})
    )
    (root / "storage" / "migrations" / "001_initial.json").write_text(
        json.dumps(
            {"operations": [{"op": "create_table", "table": "items", "fields": fields}]}
        )
    )
    (root / "module.wasm").write_bytes(wat2wasm(r"""(component
        (core module $m
            (memory (export "memory") 1)
            (data (i32.const 0) "\08\00\00\00\0b\00\00\00{\22ok\22:true}")
            (func (export "realloc") (param i32 i32 i32 i32) (result i32)
                i32.const 1024)
            (func (export "run") (param i32 i32) (result i32) i32.const 0))
        (core instance $i (instantiate $m))
        (func (export "run") (param "input" string) (result string)
            (canon lift (core func $i "run") (memory $i "memory")
                (realloc (func $i "realloc"))))
        (export "tick" (func 0)))"""))
