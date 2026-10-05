from pathlib import Path
from zipfile import ZipFile

import pytest

from lnbits.core.views.admin_api import (
    _build_pg_dump_env,
    api_download_backup,
)
from lnbits.settings import Settings


@pytest.mark.parametrize(
    "database_url, expected",
    [
        (
            "postgres://user;id:password@db.example;id:5433/lnbits;id",
            {
                "PGHOST": "db.example;id",
                "PGPORT": "5433",
                "PGUSER": "user;id",
                "PGPASSWORD": "password",
                "PGDATABASE": "lnbits;id",
            },
        ),
        ("postgres:///lnbits", {"PGDATABASE": "lnbits"}),
        (
            "postgres://localhost/lnbits",
            {"PGHOST": "localhost", "PGDATABASE": "lnbits"},
        ),
        ("postgres://user@/lnbits", {"PGUSER": "user", "PGDATABASE": "lnbits"}),
        ("postgres://user@localhost/", {"PGHOST": "localhost", "PGUSER": "user"}),
        (
            "postgres://user:p#?word@localhost/lnbits",
            {
                "PGHOST": "localhost",
                "PGUSER": "user",
                "PGPASSWORD": "p#?word",
                "PGDATABASE": "lnbits",
            },
        ),
        (
            "postgres://user%40domain:p%40ss%23%3F%25@localhost/lnbits",
            {
                "PGHOST": "localhost",
                "PGUSER": "user@domain",
                "PGPASSWORD": "p@ss#?%",
                "PGDATABASE": "lnbits",
            },
        ),
        (
            "postgres://user:password@[::1]:5433/lnbits",
            {
                "PGHOST": "::1",
                "PGPORT": "5433",
                "PGUSER": "user",
                "PGPASSWORD": "password",
                "PGDATABASE": "lnbits",
            },
        ),
        (
            "postgres://user:password@localhost/lnbits?host=%2Fvar%2Frun%2Fpostgresql&port=5433&user=other&password=new%23%3F&database=otherdb&ssl=require&prepared_statement_cache_size=0",
            {
                "PGHOST": "/var/run/postgresql",
                "PGPORT": "5433",
                "PGUSER": "other",
                "PGPASSWORD": "new#?",
                "PGDATABASE": "otherdb",
                "PGSSLMODE": "require",
            },
        ),
        (
            "postgres:///host=other user=other",
            {"PGDATABASE": "host=other user=other"},
        ),
    ],
)
def test_build_pg_dump_env(database_url, expected, monkeypatch):
    variables = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGSSLMODE")
    for variable in variables:
        monkeypatch.delenv(variable, raising=False)

    env = _build_pg_dump_env(database_url)

    assert {key: env[key] for key in variables if key in env} == expected


def test_build_pg_dump_env_preserves_defaults(monkeypatch):
    defaults = {
        "PGHOST": "/var/run/postgresql",
        "PGPORT": "5433",
        "PGUSER": "lnbits",
        "PGPASSWORD": "secret",
        "PGDATABASE": "lnbits",
        "PGSSLMODE": "verify-full",
        "PGSSLROOTCERT": "/path/to/root.crt",
    }
    for variable, value in defaults.items():
        monkeypatch.setenv(variable, value)

    env = _build_pg_dump_env("postgres://")

    assert {key: env[key] for key in defaults} == defaults


@pytest.mark.parametrize(
    "database_url",
    [
        "postgres://user@localhost:not-a-port/lnbits",
        "sqlite://user@localhost/lnbits",
        "not a URL",
    ],
)
def test_build_pg_dump_env_rejects_invalid_url(database_url: str):
    with pytest.raises(ValueError, match="Invalid PostgreSQL database URL"):
        _build_pg_dump_env(database_url)


@pytest.mark.anyio
@pytest.mark.parametrize("returncode", [0, 1])
async def test_postgres_backup_does_not_use_shell(
    mocker, settings: Settings, tmp_path: Path, returncode: int
):
    data_folder = tmp_path / "data"
    data_folder.mkdir()
    dump_filename = data_folder / "lnbits-database.dmp"
    dump_filename.touch()
    original_database_url = settings.lnbits_database_url
    original_data_folder = settings.lnbits_data_folder
    process = mocker.Mock()
    process.wait.return_value = returncode
    popen = mocker.patch("lnbits.core.views.admin_api.Popen", return_value=process)
    make_archive = mocker.patch("lnbits.core.views.admin_api.make_archive")

    try:
        settings.lnbits_database_url = (
            "postgres://user;id:secret@db.example:5433/lnbits;id"
        )
        settings.lnbits_data_folder = str(data_folder)

        if returncode:
            with pytest.raises(ValueError, match="PostgreSQL database backup failed"):
                await api_download_backup()
        else:
            await api_download_backup()
    finally:
        settings.lnbits_database_url = original_database_url
        settings.lnbits_data_folder = original_data_folder

    command = popen.call_args.args[0]
    assert command == [
        "pg_dump",
        "--no-password",
        "--format=c",
        f"--file={dump_filename}",
    ]
    assert popen.call_args.kwargs["shell"] is False
    env = popen.call_args.kwargs["env"]
    assert env["PGPASSWORD"] == "secret"
    assert env["PGUSER"] == "user;id"
    assert env["PGDATABASE"] == "lnbits;id"
    assert "secret" not in command
    if returncode:
        make_archive.assert_not_called()
    else:
        make_archive.assert_called_once_with("lnbits-backup", "zip", str(data_folder))
    assert not dump_filename.exists()


@pytest.mark.anyio
async def test_sqlite_backup(mocker, monkeypatch, settings: Settings, tmp_path: Path):
    data_folder = tmp_path / "data"
    data_folder.mkdir()
    (data_folder / "database.sqlite3").write_bytes(b"database contents")
    (data_folder / ".onchain_key").write_bytes(b"test key backup")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "lnbits_database_url", None)
    monkeypatch.setattr(settings, "lnbits_data_folder", str(data_folder))
    popen = mocker.patch("lnbits.core.views.admin_api.Popen")

    response = await api_download_backup()

    popen.assert_not_called()
    with ZipFile(response.path) as archive:
        assert archive.read("database.sqlite3") == b"database contents"
        assert archive.read(".onchain_key") == b"test key backup"
    assert response.headers["cache-control"] == "no-store"
