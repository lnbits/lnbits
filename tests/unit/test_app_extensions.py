import json
from pathlib import Path

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.app import (
    build_all_installed_extensions_list,
    check_and_register_extensions,
    register_async_tasks,
)
from lnbits.core.tasks import scheduled_extension_updates
from lnbits.settings import Settings
from lnbits.task_manager import TaskManager


@pytest.mark.anyio
async def test_startup_updates_extensions_before_restoring_and_registering(mocker):
    calls = mocker.Mock()
    for name in (
        "auto_update_extensions",
        "check_installed_extensions",
        "get_valid_extensions",
    ):
        calls.attach_mock(mocker.patch(f"lnbits.app.{name}", return_value=[]), name)
    app = mocker.Mock()

    await check_and_register_extensions(app)

    assert calls.mock_calls == [
        mocker.call.auto_update_extensions(),
        mocker.call.check_installed_extensions(app),
        mocker.call.get_valid_extensions(False),
    ]


def test_scheduled_extension_updates_are_registered(mocker):
    manager = mocker.patch("lnbits.app.task_manager")
    mocker.patch("lnbits.app.initialize_server_websocket_logger")

    register_async_tasks()

    manager.create_permanent_task.assert_any_call(scheduled_extension_updates)


@pytest.mark.anyio
@pytest.mark.parametrize("interval", [1, 15, 60])
async def test_scheduled_extension_updates_use_configured_interval(
    settings, mocker, monkeypatch, interval
):
    monkeypatch.setattr(settings, "lnbits_running", True)
    monkeypatch.setattr(
        settings, "lnbits_autoupdate_extensions_interval_minutes", interval
    )
    calls = mocker.Mock()
    sleep = mocker.patch("lnbits.core.tasks.asyncio.sleep")
    update = mocker.patch("lnbits.core.tasks.auto_update_extensions")
    calls.attach_mock(sleep, "sleep")
    calls.attach_mock(update, "update")

    async def stop_after_two_checks(**kwargs):
        settings.lnbits_autoupdate_extensions_interval_minutes = 5
        if update.await_count == 2:
            settings.lnbits_running = False

    update.side_effect = stop_after_two_checks
    manager = TaskManager()
    monkeypatch.setattr(manager, "tasks", [])
    task = manager.create_permanent_task(scheduled_extension_updates)
    await task.task

    assert calls.mock_calls == [
        mocker.call.sleep(interval * 60),
        mocker.call.update(reload_active=True),
        mocker.call.sleep(5 * 60),
        mocker.call.update(reload_active=True),
    ]


@pytest.mark.anyio
async def test_scheduled_extension_updates_wait_while_disabled_and_can_be_enabled(
    settings, mocker, monkeypatch
):
    monkeypatch.setattr(settings, "lnbits_running", True)
    monkeypatch.setattr(settings, "lnbits_autoupdate_extensions_interval_minutes", 0)
    calls = mocker.Mock()
    sleep = mocker.patch("lnbits.core.tasks.asyncio.sleep")
    update = mocker.patch("lnbits.core.tasks.auto_update_extensions")
    calls.attach_mock(sleep, "sleep")
    calls.attach_mock(update, "update")

    async def enable_updates(_seconds):
        settings.lnbits_autoupdate_extensions_interval_minutes = 2

    async def stop_after_update(**kwargs):
        settings.lnbits_running = False

    sleep.side_effect = enable_updates
    update.side_effect = stop_after_update
    manager = TaskManager()
    monkeypatch.setattr(manager, "tasks", [])
    task = manager.create_permanent_task(scheduled_extension_updates)
    await task.task

    assert calls.mock_calls == [
        mocker.call.sleep(60),
        mocker.call.sleep(120),
        mocker.call.update(reload_active=True),
    ]


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
