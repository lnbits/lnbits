from pathlib import Path
from urllib.parse import urlparse

import pytest

from lnbits.core.views.admin_api import (
    _build_pg_dump_command,
    api_download_backup,
)
from lnbits.settings import Settings


def test_build_pg_dump_command_keeps_metacharacters_in_argv(tmp_path: Path):
    dump_filename = tmp_path / "lnbits-database.dmp"

    command = _build_pg_dump_command(
        urlparse("postgres://user;id:password@db.example;id:5433/lnbits;id"),
        dump_filename,
    )

    assert command == [
        "pg_dump",
        "--host=db.example;id",
        "--port=5433",
        "--dbname=lnbits;id",
        "--username=user;id",
        "--no-password",
        "--format=c",
        f"--file={dump_filename}",
    ]


@pytest.mark.parametrize(
    "database_url",
    [
        "postgres://localhost/lnbits",
        "postgres://user@/lnbits",
        "postgres://user@localhost/",
        "postgres://user@localhost:not-a-port/lnbits",
        "sqlite://user@localhost/lnbits",
    ],
)
def test_build_pg_dump_command_rejects_invalid_url(database_url: str):
    with pytest.raises(ValueError, match="Invalid PostgreSQL database URL"):
        _build_pg_dump_command(urlparse(database_url), "backup.dmp")


@pytest.mark.anyio
async def test_postgres_backup_does_not_use_shell(
    mocker, settings: Settings, tmp_path: Path
):
    data_folder = tmp_path / "data"
    data_folder.mkdir()
    dump_filename = data_folder / "lnbits-database.dmp"
    dump_filename.touch()
    original_database_url = settings.lnbits_database_url
    original_data_folder = settings.lnbits_data_folder
    process = mocker.Mock()
    process.wait.return_value = 0
    popen = mocker.patch("lnbits.core.views.admin_api.Popen", return_value=process)
    make_archive = mocker.patch("lnbits.core.views.admin_api.make_archive")

    try:
        settings.lnbits_database_url = (
            "postgres://user;id:secret@db.example:5433/lnbits;id"
        )
        settings.lnbits_data_folder = str(data_folder)

        await api_download_backup()
    finally:
        settings.lnbits_database_url = original_database_url
        settings.lnbits_data_folder = original_data_folder

    command = popen.call_args.args[0]
    assert isinstance(command, list)
    assert "--username=user;id" in command
    assert "--dbname=lnbits;id" in command
    assert popen.call_args.kwargs["shell"] is False
    assert popen.call_args.kwargs["env"]["PGPASSWORD"] == "secret"
    assert "secret" not in command
    make_archive.assert_called_once_with("lnbits-backup", "zip", str(data_folder))
    assert not dump_filename.exists()
