import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pytest_mock import MockerFixture
from wasmtime import wat2wasm

from lnbits.core.crud.extensions import (
    delete_installed_extension,
    get_installed_extension,
)
from lnbits.core.models import Account
from lnbits.core.models.extensions import (
    ExtensionConfig,
    ExtensionManifestType,
    GitHubRepo,
    GitHubRepoRelease,
    InstallableExtension,
    Manifest,
)
from lnbits.core.models.wallets import Wallet
from lnbits.core.services.extensions import install_extension
from lnbits.core.wasm_ext.routes.api import register_wasm_extension_api_routes
from lnbits.core.wasm_ext.wasm.loader import load_wasm_extension
from lnbits.decorators import (
    check_account_exists,
    require_admin_key,
    require_base_admin_key,
)
from lnbits.settings import Settings
from tests.helpers import make_installable_extension


@pytest.mark.anyio
@pytest.mark.parametrize("runtime", ["python", "wasm"])
@pytest.mark.parametrize("kind", ["repos", "extensions"])
async def test_admin_only_manifest_survives_config_loading(
    runtime: str, kind: str, settings: Settings, mocker: MockerFixture
):
    source = "https://example.com/extensions.json"
    mocker.patch(
        "lnbits.core.models.extensions._extension_manifest_sources",
        return_value=[(source, ExtensionManifestType(runtime))],
    )
    archive_url = "https://example.com/demo.zip"
    entry = {
        "id": "demoext",
        "organisation": "example",
        "repository": "demoext",
        "name": "Demo",
        "version": "1.0.0",
        "archive": archive_url,
        "hash": "demo-hash",
        "details_link": "https://example.com/config.json",
        "extension_type": runtime,
        "admin_only": True,
    }
    mocker.patch.object(
        InstallableExtension,
        "fetch_manifest",
        return_value=Manifest.model_validate({kind: [entry]}),
    )
    config = ExtensionConfig(name="Demo", short_description="Demo", admin_only=False)
    github_release = GitHubRepoRelease(
        name="Demo", tag_name="1.0.0", zipball_url=archive_url, html_url=source
    )
    mocker.patch.object(
        InstallableExtension,
        "fetch_github_repo_info",
        return_value=(
            GitHubRepo(stargazers_count="0", html_url=source, default_branch="main"),
            github_release,
            config,
        ),
    )
    mocker.patch(
        "lnbits.core.models.extensions.ExtensionRelease.fetch_github_releases",
        return_value=[github_release],
    )
    mocker.patch.object(
        ExtensionConfig, "fetch_github_release_config", return_value=config
    )
    mocker.patch.object(ExtensionConfig, "fetch_release_config", return_value=config)

    catalog = await InstallableExtension._get_installable_extensions()
    releases = await InstallableExtension.get_extension_releases("demoext")

    assert len(catalog) == len(releases) == 1
    assert catalog[0].is_admin_only
    assert releases[0].admin_only


@pytest.mark.anyio
@pytest.mark.parametrize("runtime", ["python", "wasm"])
@pytest.mark.parametrize(
    "manifest_flag,config_flag", [(True, False), (False, True), (False, False)]
)
async def test_admin_only_installation_persists_for_both_runtimes(
    app,
    tmp_path: Path,
    settings: Settings,
    mocker: MockerFixture,
    runtime: str,
    manifest_flag: bool,
    config_flag: bool,
):
    settings.lnbits_data_folder = str(tmp_path / "data")
    settings.lnbits_extensions_path = str(tmp_path / "code")
    settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm")
    ext = make_installable_extension(f"ext_{uuid4().hex[:8]}", admin_only=manifest_flag)
    config = _config(ext.id, runtime, config_flag)
    with zipfile.ZipFile(ext.zip_path, "w") as archive:
        archive.writestr(f"{ext.id}/config.json", json.dumps(config))
        if runtime == "wasm":
            archive.writestr(f"{ext.id}/extension.wasm", wat2wasm("(component)"))
    mocker.patch("lnbits.core.services.extensions.migrate_extension_database")
    mocker.patch("lnbits.core.services.extensions.warm_wasm_extension")

    try:
        await install_extension(ext, skip_download=True)
        stored = await get_installed_extension(ext.id)
        assert stored and stored.meta and stored.meta.installed_release
        assert stored.meta.installed_release.admin_only == (
            manifest_flag or config_flag
        )
        assert stored.is_admin_only == (manifest_flag or config_flag)

        local = (
            InstallableExtension.from_wasm_ext_dir(ext.id)
            if runtime == "wasm"
            else InstallableExtension.from_ext_dir(ext.id)
        )
        assert local and local.is_admin_only == config_flag
    finally:
        await delete_installed_extension(ext_id=ext.id)


@pytest.mark.anyio
@pytest.mark.parametrize("auth", ["account", "wallet", "cached_wallet", "wasm"])
@pytest.mark.parametrize("role", ["user", "admin", "superuser"])
@pytest.mark.parametrize("restriction", ["package", "setting", "none"])
async def test_admin_only_authenticated_routes(
    tmp_path: Path,
    settings: Settings,
    mocker: MockerFixture,
    auth: str,
    role: str,
    restriction: str,
):
    user_id = uuid4().hex
    settings.lnbits_admin_users = [user_id] if role == "admin" else []
    mocker.patch.object(
        settings, "super_user", user_id if role == "superuser" else "other"
    )
    settings.lnbits_installed_extensions_ids = {"demoext"}
    settings.lnbits_admin_extensions = ["demoext"] if restriction == "setting" else []
    ext = make_installable_extension("demoext", admin_only=restriction == "package")
    mocker.patch("lnbits.decorators.db.connect", return_value=mocker.MagicMock())
    mocker.patch("lnbits.decorators.get_installed_extension", return_value=ext)
    mocker.patch(
        "lnbits.decorators.get_user_active_extensions_ids", return_value=[ext.id]
    )
    mocker.patch(
        "lnbits.decorators._get_account_from_token", return_value=Account(id=user_id)
    )
    wallet = Wallet(
        id=uuid4().hex,
        name="Test",
        user=user_id,
        adminkey=uuid4().hex,
        inkey=uuid4().hex,
    )
    mocker.patch("lnbits.decorators.get_wallet_for_key", return_value=wallet)
    mocker.patch("lnbits.decorators.get_base_wallet_for_key", return_value=wallet)
    headers = {"Authorization": "Bearer test-token", "X-API-KEY": wallet.adminkey}
    app = FastAPI()
    if auth == "wasm":
        settings.lnbits_wasm_extensions_path = str(tmp_path)
        ext_dir = tmp_path / ext.id
        ext_dir.mkdir()
        (ext_dir / "config.json").write_text(json.dumps(_config(ext.id, "wasm", True)))
        (ext_dir / "extension.wasm").write_bytes(wat2wasm("(component)"))
        register_wasm_extension_api_routes(app, load_wasm_extension(ext.id))
        mocker.patch(
            "lnbits.core.wasm_ext.routes.api.get_wasm_runtime_limits_for_extension",
            return_value={"wasm_runtime_max_request_bytes": 1024},
        )
        invoked = mocker.patch(
            "lnbits.core.wasm_ext.routes.api.invoke_wasm_extension_export",
            return_value={},
        )
        private_path = f"/api/v1/ext/{ext.id}/private"
        public_path = f"/api/v1/ext/{ext.id}/public"
    else:
        dependencies: dict[str, Callable[..., Any]] = {
            "account": check_account_exists,
            "wallet": require_admin_key,
            "cached_wallet": require_base_admin_key,
        }
        invoked = mocker.Mock(return_value={})
        private_path = f"/{ext.id}/api/v1/private"
        public_path = f"/{ext.id}/api/v1/public"

        @app.get(private_path, dependencies=[Depends(dependencies[auth])])
        async def private_route():
            return invoked()

        @app.get(public_path)
        async def public_route():
            return {}

    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test"
    ) as client:
        denied = restriction != "none" and role == "user"
        for _ in range(2):  # Repeat to exercise cached wallet authentication too.
            response = await client.get(private_path, headers=headers)
            assert response.status_code == (403 if denied else 200)
        assert invoked.call_count == (0 if denied else 2)
        if restriction != "none" and role != "user":
            settings.lnbits_admin_users = []
            settings.super_user = "other"
            response = await client.get(private_path, headers=headers)
            assert response.status_code == 403
            assert invoked.call_count == 2
        response = await client.get(public_path)
        assert response.status_code == 200


def _config(ext_id: str, runtime: str, admin_only: bool) -> dict:
    return {
        "id": ext_id,
        "name": "Demo",
        "short_description": "Demo extension",
        "version": "1.0.0",
        "admin_only": admin_only,
        "extension_type": runtime,
        "wasm": {
            "module": "extension.wasm",
            "exports": [
                {"name": "private", "visibility": "authenticated"},
                {"name": "public", "visibility": "public"},
            ],
        },
        "api_routes": [
            {"method": "GET", "path": "/private", "export": "private", "auth": "user"},
            {"method": "GET", "path": "/public", "export": "public", "auth": "public"},
        ],
    }
