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


@pytest.fixture
def extension_update_schedule(mocker, monkeypatch):
    monkeypatch.setattr("lnbits.core.tasks._last_extension_update_check", None)
    clock = mocker.patch("lnbits.core.tasks.monotonic", return_value=0)
    update = mocker.patch("lnbits.core.tasks.auto_update_extensions")
    return clock, update


@pytest.mark.anyio
@pytest.mark.parametrize("enabled", [True, False])
async def test_startup_updates_extensions_before_restoring_and_registering(
    mocker, settings, enabled
):
    settings.lnbits_autoupdate_extensions_on_startup = enabled
    calls = mocker.Mock()
    for name in (
        "auto_update_extensions",
        "check_installed_extensions",
        "get_valid_extensions",
    ):
        calls.attach_mock(mocker.patch(f"lnbits.app.{name}", return_value=[]), name)
    app = mocker.Mock()

    await check_and_register_extensions(app)

    expected_calls = [mocker.call.auto_update_extensions()] if enabled else []
    assert calls.mock_calls == [
        *expected_calls,
        mocker.call.check_installed_extensions(app),
        mocker.call.get_valid_extensions(False),
    ]


def test_scheduled_extension_updates_are_registered(mocker):
    manager = mocker.patch("lnbits.app.task_manager")
    mocker.patch("lnbits.app.initialize_server_websocket_logger")

    register_async_tasks()

    manager.create_permanent_task.assert_any_call(
        scheduled_extension_updates, interval=60
    )


@pytest.mark.anyio
@pytest.mark.parametrize("interval", [1, 12, 24])
async def test_scheduled_extension_updates_use_configured_interval(
    settings, extension_update_schedule, interval
):
    clock, update = extension_update_schedule
    settings.lnbits_autoupdate_extensions_interval_hours = interval
    await scheduled_extension_updates()

    clock.return_value = interval * 3600 - 1
    await scheduled_extension_updates()
    update.assert_not_awaited()

    clock.return_value = interval * 3600
    await scheduled_extension_updates()
    update.assert_awaited_once_with(reload_active=True)

    clock.return_value = interval * 7200 - 1
    await scheduled_extension_updates()
    update.assert_awaited_once()

    clock.return_value = interval * 7200
    await scheduled_extension_updates()
    assert update.await_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize("initial_interval", [0, 1])
async def test_scheduled_extension_updates_wait_while_disabled_and_can_be_enabled(
    settings, extension_update_schedule, initial_interval
):
    clock, update = extension_update_schedule
    settings.lnbits_autoupdate_extensions_interval_hours = initial_interval
    await scheduled_extension_updates()

    settings.lnbits_autoupdate_extensions_interval_hours = 0
    clock.return_value = 3600
    await scheduled_extension_updates()
    update.assert_not_awaited()

    settings.lnbits_autoupdate_extensions_interval_hours = 1
    clock.return_value = 3660
    await scheduled_extension_updates()
    update.assert_awaited_once_with(reload_active=True)


@pytest.mark.anyio
async def test_shorter_extension_update_interval_applies_on_next_tick(
    settings, extension_update_schedule
):
    clock, update = extension_update_schedule
    settings.lnbits_autoupdate_extensions_interval_hours = 24
    await scheduled_extension_updates()

    clock.return_value = 3600
    await scheduled_extension_updates()
    update.assert_not_awaited()

    settings.lnbits_autoupdate_extensions_interval_hours = 1
    clock.return_value = 3660
    await scheduled_extension_updates()
    update.assert_awaited_once_with(reload_active=True)


@pytest.mark.anyio
async def test_longer_extension_update_interval_delays_next_check(
    settings, extension_update_schedule
):
    clock, update = extension_update_schedule
    settings.lnbits_autoupdate_extensions_interval_hours = 1
    await scheduled_extension_updates()

    settings.lnbits_autoupdate_extensions_interval_hours = 24
    clock.return_value = 3600
    await scheduled_extension_updates()
    update.assert_not_awaited()

    clock.return_value = 86400
    await scheduled_extension_updates()
    update.assert_awaited_once_with(reload_active=True)


@pytest.mark.anyio
async def test_extension_update_interval_starts_when_check_begins(
    settings, extension_update_schedule
):
    clock, update = extension_update_schedule
    settings.lnbits_autoupdate_extensions_interval_hours = 1
    await scheduled_extension_updates()

    async def finish_update(**kwargs):
        clock.return_value += 30

    update.side_effect = finish_update
    clock.return_value = 3600
    await scheduled_extension_updates()
    update.assert_awaited_once()

    clock.return_value = 7199
    await scheduled_extension_updates()
    update.assert_awaited_once()

    clock.return_value = 7200
    await scheduled_extension_updates()
    assert update.await_count == 2


@pytest.mark.anyio
async def test_failed_extension_update_waits_for_configured_interval(
    settings, extension_update_schedule
):
    clock, update = extension_update_schedule
    settings.lnbits_autoupdate_extensions_interval_hours = 2
    await scheduled_extension_updates()
    update.side_effect = ValueError("Update check failed")

    clock.return_value = 7200
    with pytest.raises(ValueError, match="Update check failed"):
        await scheduled_extension_updates()

    clock.return_value = 10800
    await scheduled_extension_updates()
    update.assert_awaited_once()

    clock.return_value = 14400
    with pytest.raises(ValueError, match="Update check failed"):
        await scheduled_extension_updates()
    assert update.await_count == 2


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
