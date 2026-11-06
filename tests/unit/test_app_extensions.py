import json
from pathlib import Path

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.app import build_all_installed_extensions_list
from lnbits.settings import Settings
from tests.helpers import make_installable_extension


@pytest.mark.anyio
async def test_wasm_extension_discovery_uses_configured_directory(
    tmp_path: Path,
    settings: Settings,
    mocker: MockerFixture,
):
    discovered_id = "discovered_wasm"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    original_installed_ids = set(settings.lnbits_installed_extensions_ids)

    settings.lnbits_extensions_path = str(tmp_path / "code")
    settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
    Path(settings.lnbits_extensions_path, "extensions").mkdir(parents=True)
    _write_wasm_config(settings.wasm_extensions_dir / discovered_id, discovered_id)

    mocker.patch(
        "lnbits.app.get_installed_extensions",
        mocker.AsyncMock(return_value=[]),
    )
    create_mock = mocker.patch(
        "lnbits.app.create_installed_extension",
        mocker.AsyncMock(),
    )
    mocker.patch(
        "lnbits.app.get_db_version",
        mocker.AsyncMock(return_value=None),
    )
    migrate_mock = mocker.patch(
        "lnbits.app.migrate_extension_database",
        mocker.AsyncMock(),
    )

    try:
        installed = await build_all_installed_extensions_list()
    finally:
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_wasm_extensions_path = original_wasm_extensions_path
        settings.lnbits_installed_extensions_ids = original_installed_ids

    assert [extension.id for extension in installed] == [discovered_id]
    create_mock.assert_awaited_once()
    assert create_mock.await_args is not None
    assert create_mock.await_args.args[0].id == discovered_id
    migrate_mock.assert_awaited_once()


@pytest.mark.anyio
async def test_startup_rebuilds_admin_only_extensions_from_release_metadata(
    tmp_path: Path, settings: Settings, mocker: MockerFixture
):
    settings.lnbits_extensions_path = str(tmp_path / "code")
    settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm")
    settings.lnbits_admin_only_extensions = {"removed"}
    settings.lnbits_admin_extensions = ["configured"]
    restricted = make_installable_extension("restricted", admin_only=True)
    restricted.active = False
    configured = make_installable_extension("configured")
    latest_only = make_installable_extension("latest_only", admin_only=True)
    assert latest_only.meta
    latest_only.meta.latest_release = latest_only.meta.installed_release
    latest_only.meta.installed_release = None
    unrestricted = make_installable_extension("unrestricted")
    assert unrestricted.meta
    unrestricted.meta.latest_release = latest_only.meta.latest_release
    no_meta = make_installable_extension("no_meta")
    no_meta.meta = None
    extensions = [restricted, configured, latest_only, unrestricted, no_meta]
    get_extensions = mocker.patch(
        "lnbits.app.get_installed_extensions", return_value=extensions
    )

    assert await build_all_installed_extensions_list() == extensions

    get_extensions.assert_awaited_once_with()
    assert settings.lnbits_admin_only_extensions == {"restricted", "latest_only"}
    assert settings.lnbits_admin_extensions == ["configured"]
    assert settings.is_admin_extension("configured")


def _write_wasm_config(ext_dir: Path, ext_id: str) -> None:
    ext_dir.mkdir(parents=True)
    (ext_dir / "config.json").write_text(
        json.dumps(
            {
                "id": ext_id,
                "name": ext_id,
                "version": "1.0.0",
                "extension_type": "wasm",
                "wasm": {"module": "extension.wasm"},
            }
        ),
        encoding="utf-8",
    )
