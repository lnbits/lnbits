import hashlib
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.extensions import ExtensionRelease
from lnbits.core.services.extensions_builder import (
    build_extension_from_data,
    clean_extension_builder_data,
    zip_directory,
)
from lnbits.settings import Settings
from tests.helpers import make_extension_data


@pytest.mark.anyio
async def test_build_extension_from_data_orchestrates_builder_steps(
    tmp_path, mocker: MockerFixture
):
    data = make_extension_data()
    release = ExtensionRelease(
        name="stub",
        version="0.1.0",
        archive="https://example.com/stub.zip",
        source_repo="org/repo",
        is_github_release=True,
    )
    build_dir = tmp_path / "build"
    fetch_mock = mocker.patch(
        "lnbits.core.services.extensions_builder._fetch_extension_builder_stub",
        mocker.AsyncMock(),
    )
    transform_mock = mocker.patch(
        "lnbits.core.services.extensions_builder._transform_extension_builder_stub"
    )
    export_mock = mocker.patch(
        "lnbits.core.services.extensions_builder._export_extension_data_json"
    )
    mocker.patch(
        "lnbits.core.services.extensions_builder._get_extension_stub_release",
        mocker.AsyncMock(return_value=release),
    )
    mocker.patch(
        "lnbits.core.services.extensions_builder._copy_ext_stub_to_build_dir",
        return_value=build_dir,
    )
    mocker.patch(
        "lnbits.core.services.extensions_builder.uuid4",
        return_value=SimpleNamespace(hex="seed"),
    )

    built_release, output_dir = await build_extension_from_data(data, "stub-ext")

    assert output_dir == build_dir
    assert built_release == release
    assert built_release.hash == hashlib.sha256(b"seed").hexdigest()
    assert built_release.icon == "/demoext/static/image/demoext.png"
    assert built_release.is_github_release is False
    fetch_mock.assert_awaited_once_with("stub-ext", release)
    transform_mock.assert_called_once_with(data, build_dir)
    export_mock.assert_called_once_with(data, build_dir)


def test_clean_extension_builder_data_recreates_working_directory(
    settings: Settings, tmp_path
):
    original_data_folder = settings.lnbits_data_folder
    try:
        settings.lnbits_data_folder = str(tmp_path)
        working_dir = settings.extension_builder_working_dir_path
        working_dir.mkdir(parents=True, exist_ok=True)
        Path(working_dir, "stale.txt").write_text("stale")

        clean_extension_builder_data()

        assert working_dir.is_dir()
        assert list(working_dir.iterdir()) == []
    finally:
        settings.lnbits_data_folder = original_data_folder


def test_zip_directory_skips_excluded_directories(tmp_path):
    source_dir = tmp_path / "source"
    zip_path = tmp_path / "archive.zip"
    (source_dir / "nested").mkdir(parents=True)
    (source_dir / "node_modules").mkdir()
    (source_dir / "__pycache__").mkdir()
    (source_dir / "root.txt").write_text("root")
    (source_dir / "nested" / "file.txt").write_text("nested")
    (source_dir / "node_modules" / "ignored.txt").write_text("ignored")
    (source_dir / "__pycache__" / "ignored.pyc").write_text("ignored")

    from_builder = "lnbits.core.services.extensions_builder._is_excluded_dir"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            from_builder,
            lambda path: "node_modules" in path or "__pycache__" in path,
        )
        zip_directory(source_dir, zip_path)

    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(archive.namelist())

    assert names == ["nested/file.txt", "root.txt"]
