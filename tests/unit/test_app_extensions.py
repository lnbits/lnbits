import json
from pathlib import Path

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.app import build_all_installed_extensions_list
from lnbits.core.helpers import migrate_extension_database
from lnbits.core.models.extensions import InstallableExtension
from lnbits.settings import Settings


@pytest.mark.anyio
async def test_extension_discovery_separates_wasm_and_regular_directories(
    tmp_path: Path,
    settings: Settings,
    mocker: MockerFixture,
):
    ignored_id = "ignored_wasm"
    discovered_id = "discovered_wasm"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    original_installed_ids = set(settings.lnbits_installed_extensions_ids)

    settings.lnbits_extensions_path = str(tmp_path / "code")
    settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
    regular_extensions_dir = Path(settings.lnbits_extensions_path, "extensions")
    _write_wasm_config(regular_extensions_dir / ignored_id, ignored_id)
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
async def test_extension_migration_ignores_wasm_in_regular_directory(
    tmp_path: Path,
    settings: Settings,
    mocker: MockerFixture,
):
    ext_id = "ignored_wasm"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    settings.lnbits_extensions_path = str(tmp_path / "code")
    settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
    _write_wasm_config(
        Path(settings.lnbits_extensions_path, "extensions", ext_id),
        ext_id,
    )
    py_migration_mock = mocker.patch(
        "lnbits.core.helpers.migrate_py_extension_database",
        mocker.AsyncMock(),
    )
    wasm_migration_mock = mocker.patch(
        "lnbits.core.helpers.migrate_wasm_extension_database",
        mocker.AsyncMock(),
    )

    try:
        await migrate_extension_database(
            InstallableExtension(id=ext_id, name=ext_id, version="1.0.0")
        )
    finally:
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_wasm_extensions_path = original_wasm_extensions_path

    py_migration_mock.assert_not_awaited()
    wasm_migration_mock.assert_not_awaited()


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
