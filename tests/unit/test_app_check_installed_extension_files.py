"""Regression tests for startup extension zip restore (#4070)."""

import json
import zipfile
from uuid import uuid4

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.app import check_installed_extension_files
from lnbits.core.models.extensions import InstallableExtension
from lnbits.settings import Settings
from tests.helpers import make_installable_extension


def _write_python_extension_zip(zip_path, ext_id: str) -> None:
    """Minimal valid extension archive with config.json (python type)."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "id": ext_id,
        "name": f"Extension {ext_id}",
        "version": "1.0.0",
        "short_description": "test",
    }
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(f"{ext_id}/config.json", json.dumps(config))


@pytest.mark.anyio
async def test_check_installed_extension_files_uses_local_zip_when_present(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    """Absolute zip paths under LNBITS_DATA_FOLDER must count as present.

    Historically compared `./{absolute zip_path}` against glob results, never
    matched, deleted the good zip via download_archive, then failed offline.
    """
    ext_id = f"ext_{uuid4().hex[:8]}"
    ext_info = make_installable_extension(ext_id)
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")

        # Present local archive; extension files intentionally missing.
        assert not ext_info.has_installed_version
        _write_python_extension_zip(ext_info.zip_path, ext_id)
        assert ext_info.zip_path.is_file()
        assert ext_info.zip_path.is_absolute()

        download_mock = mocker.patch.object(
            InstallableExtension, "download_archive", mocker.AsyncMock()
        )
        extract_mock = mocker.patch.object(InstallableExtension, "extract_archive")
        wasm_extract_mock = mocker.patch.object(
            InstallableExtension, "extract_wasm_archive"
        )

        restored = await check_installed_extension_files(ext_info)

        assert restored is False
        download_mock.assert_not_awaited()
        extract_mock.assert_called_once_with()
        wasm_extract_mock.assert_not_called()
        # Local zip must survive the path check (download_archive would delete it).
        assert ext_info.zip_path.is_file()
    finally:
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path


@pytest.mark.anyio
async def test_check_installed_extension_files_downloads_when_zip_missing(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    ext_id = f"ext_{uuid4().hex[:8]}"
    ext_info = make_installable_extension(ext_id)
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")

        assert not ext_info.has_installed_version
        assert not ext_info.zip_path.is_file()

        async def _fake_download() -> None:
            _write_python_extension_zip(ext_info.zip_path, ext_id)

        download_mock = mocker.patch.object(
            InstallableExtension,
            "download_archive",
            mocker.AsyncMock(side_effect=_fake_download),
        )
        extract_mock = mocker.patch.object(InstallableExtension, "extract_archive")
        wasm_extract_mock = mocker.patch.object(
            InstallableExtension, "extract_wasm_archive"
        )

        restored = await check_installed_extension_files(ext_info)

        assert restored is False
        download_mock.assert_awaited_once_with()
        extract_mock.assert_called_once_with()
        wasm_extract_mock.assert_not_called()
    finally:
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path


@pytest.mark.anyio
async def test_check_installed_extension_files_skips_when_version_present(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    ext_id = f"ext_{uuid4().hex[:8]}"
    ext_info = make_installable_extension(ext_id)
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")

        ext_info.ext_dir.mkdir(parents=True, exist_ok=True)
        (ext_info.ext_dir / "config.json").write_text("{}", encoding="utf-8")
        assert ext_info.has_installed_version

        download_mock = mocker.patch.object(
            InstallableExtension, "download_archive", mocker.AsyncMock()
        )
        extract_mock = mocker.patch.object(InstallableExtension, "extract_archive")

        assert await check_installed_extension_files(ext_info) is True
        download_mock.assert_not_awaited()
        extract_mock.assert_not_called()
    finally:
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path


@pytest.mark.anyio
async def test_download_archive_preserves_existing_zip_on_download_failure(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    """download_archive must not delete the existing zip before the download
    succeeds. If the remote fetch fails, the original zip must survive so a
    later startup with working DNS can try again. See issue #4070.
    """
    ext_id = f"ext_{uuid4().hex[:8]}"
    ext_info = make_installable_extension(ext_id)
    ext_info.meta.installed_release.pay_link = None  # skip payment info side-effects
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")

        # Existing valid zip on disk.
        _write_python_extension_zip(ext_info.zip_path, ext_id)
        original_zip_content = ext_info.zip_path.read_bytes()
        assert ext_info.zip_path.is_file()

        mocker.patch(
            "lnbits.core.models.extensions.download_url",
            side_effect=ConnectionError("simulated network failure"),
        )

        with pytest.raises(AssertionError, match="Cannot fetch extension archive file"):
            await ext_info.download_archive()

        # Original zip must survive; no .tmp residue.
        assert ext_info.zip_path.is_file()
        assert ext_info.zip_path.read_bytes() == original_zip_content
        tmp_zip = ext_info.zip_path.with_name(ext_info.zip_path.name + ".tmp")
        assert not tmp_zip.exists()
    finally:
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path


@pytest.mark.anyio
async def test_download_archive_atomic_replace_on_success(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    """download_archive writes to a temp file then atomically replaces the
    final zip only after the hash check passes.
    """
    ext_id = f"ext_{uuid4().hex[:8]}"
    ext_info = make_installable_extension(ext_id)
    ext_info.meta.installed_release.pay_link = None  # skip payment info side-effects
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")

        assert not ext_info.zip_path.exists()

        zip_bytes = b"fake-extension-zip-content"
        ext_info.meta.installed_release.hash = None  # skip hash verification

        def _fake_download(url: str, save_path):
            save_path.write_bytes(zip_bytes)

        mocker.patch(
            "lnbits.core.models.extensions.download_url",
            side_effect=_fake_download,
        )

        await ext_info.download_archive()

        # Final zip must contain the downloaded content.
        assert ext_info.zip_path.read_bytes() == zip_bytes
        # No .tmp residue.
        tmp_zip = ext_info.zip_path.with_name(ext_info.zip_path.name + ".tmp")
        assert not tmp_zip.exists()
    finally:
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path


@pytest.mark.anyio
async def test_check_installed_extensions_soft_fails_without_deactivation(
    tmp_path, settings: Settings, mocker: MockerFixture
):
    """When extension restoration fails, check_installed_extensions must NOT
    permanently deactivate the extension — it should soft-fail and log only.
    See issue #4070.
    """
    from fastapi import FastAPI

    from lnbits.app import check_installed_extensions

    ext_id = f"ext_{uuid4().hex[:8]}"
    ext_info = make_installable_extension(ext_id)
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")

        mocker.patch(
            "lnbits.app.build_all_installed_extensions_list",
            mocker.AsyncMock(return_value=[ext_info]),
        )
        mocker.patch(
            "lnbits.app.check_installed_extension_files",
            mocker.AsyncMock(side_effect=RuntimeError("simulated restore failure")),
        )
        mocker.patch("lnbits.app.restore_installed_extension", mocker.AsyncMock())
        deactivate_mock = mocker.patch(
            "lnbits.core.services.extensions.deactivate_extension", mocker.AsyncMock()
        )
        mocker.patch("lnbits.app.update_installed_extension_state", mocker.AsyncMock())

        app = FastAPI()
        await check_installed_extensions(app)

        # deactivate_extension must NOT have been called (soft-fail).
        deactivate_mock.assert_not_awaited()
    finally:
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path
