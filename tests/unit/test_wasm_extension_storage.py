import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import extensions as extension_crud
from lnbits.core.crud import update_migration_version
from lnbits.core.db import db as core_db
from lnbits.core.migrations import (
    m010_create_installed_extensions_table,
    m046_add_permissions_to_installed_extensions,
    m047_create_wasm_invocations_table,
    m048_add_wasm_runtime_limits_to_installed_extensions,
)
from lnbits.core.models.extensions import ExtensionPermission, WasmInvocation
from lnbits.core.wasm_ext.storage import crud as storage_crud
from lnbits.core.wasm_ext.storage.crud import (
    OWNER_ID_FIELD,
    VERSION_FIELD,
    migrate_wasm_extension_database,
    storage_append_public_row,
    storage_compare_and_set_row,
    storage_count_rows,
    storage_delete_row,
    storage_get_immutable_row,
    storage_get_paginated_rows,
    storage_get_public_row,
    storage_get_row,
    storage_get_row_with_version,
    storage_insert_if_absent_row,
    storage_insert_immutable_row,
    storage_set_row,
)
from lnbits.db import DB_TYPE, SQLITE, Compat, Connection, Database
from lnbits.settings import Settings
from tests.helpers import make_installable_extension


@pytest.mark.anyio
async def test_wasm_storage_reuses_database_engine_per_extension(mocker: MockerFixture):
    factory = mocker.patch.object(
        storage_crud, "Database", side_effect=lambda _: object()
    )
    first_id = f"cached_{uuid4().hex}"
    second_id = f"cached_{uuid4().hex}"

    first = storage_crud._database(first_id)
    assert storage_crud._database(first_id) is first
    assert storage_crud._database(second_id) is not first
    assert factory.call_count == 2


@pytest.mark.anyio
async def test_core_wasm_migrations_create_persistent_columns(
    tmp_path: Path, settings: Settings
):
    if DB_TYPE != SQLITE:
        pytest.skip("temporary core databases are SQLite-only")

    db = _temporary_database(tmp_path, settings, "wasm_core_migrations")

    async with db.connect() as conn:
        await m010_create_installed_extensions_table(conn)
        await m046_add_permissions_to_installed_extensions(conn)
        await m047_create_wasm_invocations_table(conn)
        await m048_add_wasm_runtime_limits_to_installed_extensions(conn)

        installed_columns = {
            row["name"]
            for row in await conn.fetchall("PRAGMA table_info(installed_extensions)")
        }
        invocation_columns = {
            row["name"]
            for row in await conn.fetchall("PRAGMA table_info(wasm_invocations)")
        }

    assert {"permissions", "wasm_runtime_limits"}.issubset(installed_columns)
    assert {
        "extension_id",
        "status",
        "request_bytes",
        "response_bytes",
        "host_call_count",
        "http_call_count",
        "storage_call_count",
        "wallet_call_count",
        "context",
    }.issubset(invocation_columns)


@pytest.mark.anyio
async def test_installed_extension_permissions_and_wasm_limits_round_trip(
    app,
    tmp_path: Path,
    settings: Settings,
    mocker: MockerFixture,
):
    db = await _temporary_core_crud_database(tmp_path, settings)
    mocker.patch.object(extension_crud, "db", db)

    ext_id = f"wasmlimits_{uuid4().hex[:8]}"
    extension = make_installable_extension(ext_id)
    extension.permissions = [ExtensionPermission(id="utils.basic")]
    extension.wasm_runtime_limits = {"wasm_runtime_max_execution_ms": 1234}

    await extension_crud.create_installed_extension(extension)
    stored = await extension_crud.get_installed_extension(ext_id)

    assert stored is not None
    assert stored.permissions == [ExtensionPermission(id="utils.basic")]
    assert stored.wasm_runtime_limits == {"wasm_runtime_max_execution_ms": 1234}

    stored.wasm_runtime_limits = {"wasm_runtime_max_fuel": 0}
    await extension_crud.update_installed_extension(stored)
    updated = await extension_crud.get_installed_extension(ext_id)

    assert updated is not None
    assert updated.wasm_runtime_limits == {"wasm_runtime_max_fuel": 0}


@pytest.mark.anyio
async def test_wasm_invocation_crud_stats_and_cleanup_are_isolated(
    app,
    tmp_path: Path,
    settings: Settings,
    mocker: MockerFixture,
):
    db = await _temporary_core_crud_database(tmp_path, settings)
    mocker.patch.object(extension_crud, "db", db)

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=10)
    ext_id = f"wasminv_{uuid4().hex[:8]}"
    other_ext_id = f"wasminv_{uuid4().hex[:8]}"
    invocations = [
        WasmInvocation(
            id=f"inv_{uuid4().hex}",
            extension_id=ext_id,
            export_name="render",
            status="completed",
            started_at=old,
            finished_at=old + timedelta(milliseconds=20),
            duration_ms=20,
            host_call_count=2,
            http_call_count=1,
        ),
        WasmInvocation(
            id=f"inv_{uuid4().hex}",
            extension_id=ext_id,
            export_name="render",
            status="failed",
            started_at=now,
            finished_at=now,
            duration_ms=40,
            host_call_count=3,
            storage_call_count=2,
        ),
        WasmInvocation(
            id=f"inv_{uuid4().hex}",
            extension_id=ext_id,
            export_name="render",
            status="running",
            started_at=old,
        ),
        WasmInvocation(
            id=f"inv_{uuid4().hex}",
            extension_id=other_ext_id,
            export_name="render",
            status="completed",
            started_at=now,
            duration_ms=100,
        ),
    ]
    for invocation in invocations:
        await extension_crud.create_wasm_invocation(invocation)

    failed = await extension_crud.get_wasm_invocations(
        extension_id=ext_id,
        status="failed",
    )
    stats = await extension_crud.get_wasm_invocation_stats(
        extension_id=ext_id,
        since=now - timedelta(days=30),
    )
    deleted = await extension_crud.delete_old_wasm_invocations(retention_days=7)
    remaining_running = await extension_crud.get_wasm_invocations(
        extension_id=ext_id,
        status="running",
    )

    assert [invocation.id for invocation in failed] == [invocations[1].id]
    assert stats.total == 3
    assert stats.completed == 1
    assert stats.failed == 1
    assert stats.running == 1
    assert stats.host_call_count == 5
    assert stats.http_call_count == 1
    assert stats.storage_call_count == 2
    assert deleted == 1
    assert [invocation.id for invocation in remaining_running] == [invocations[2].id]


@pytest.mark.anyio
async def test_wasm_datetime_queries_use_postgres_placeholders(
    mocker: MockerFixture,
):
    db = mocker.Mock()
    db.timestamp_placeholder.side_effect = lambda key: f"to_timestamp(:{key})"
    db.fetchone = mocker.AsyncMock(return_value=None)
    db.execute = mocker.AsyncMock(return_value=SimpleNamespace(rowcount=0))

    field = {"name": "created_at", "type": "datetime"}
    assert (
        storage_crud._value_placeholder(cast(Compat, db), field, "created_at")
        == "to_timestamp(:created_at)"
    )
    where_sql, _ = storage_crud._where_sql(
        cast(Compat, db), {"fields": [field]}, {"created_at": 0}, None, []
    )
    assert "created_at = to_timestamp(:filter_created_at)" in where_sql

    conn = cast(Connection, db)
    await extension_crud.get_wasm_invocation_stats(
        since=datetime.now(timezone.utc), conn=conn
    )
    await extension_crud.delete_old_wasm_invocations(1, conn=conn)
    await extension_crud.mark_stale_wasm_invocations(conn=conn)

    queries = [
        db.fetchone.call_args.args[0],
        *[c.args[0] for c in db.execute.call_args_list],
    ]
    assert all("to_timestamp(:" in query for query in queries)


@pytest.mark.anyio
async def test_wasm_storage_migration_and_owner_scoped_crud(
    tmp_path: Path,
    settings: Settings,
):
    ext_id = f"wasmstore_{uuid4().hex[:8]}"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    original_data_folder = settings.lnbits_data_folder
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
        Path(settings.lnbits_data_folder).mkdir(parents=True)
        ext_dir = _write_storage_extension(settings, ext_id)

        await migrate_wasm_extension_database(make_installable_extension(ext_id))
        await storage_set_row(
            ext_id,
            "notes",
            {
                "id": "note-1",
                "title": "First",
                "count": 1,
                "published": True,
                "tags": ["alpha", "beta"],
                "created_at": 1_700_000_000,
            },
            "owner-1",
        )
        await storage_set_row(
            ext_id,
            "notes",
            {
                "id": "note-1",
                "title": "Other owner attempt",
                "count": 2,
                "published": False,
                "tags": ["gamma"],
                "created_at": 1_700_000_001,
            },
            "owner-2",
        )

        owner_row = await storage_get_row(ext_id, "notes", "note-1", "owner-1")
        other_owner_row = await storage_get_row(ext_id, "notes", "note-1", "owner-2")
        public_row = await storage_get_public_row(ext_id, "notes", "note-1")
        page = await storage_get_paginated_rows(
            ext_id,
            "notes",
            {"published": True},
            owner_id="owner-1",
            search="fir",
            search_fields=["title"],
            sort_by="count",
            descending=True,
            limit=50,
            offset=0,
        )
        await storage_delete_row(ext_id, "notes", "note-1", "owner-2")
        still_owned = await storage_get_row(ext_id, "notes", "note-1", "owner-1")
        await storage_delete_row(ext_id, "notes", "note-1", "owner-1")
        deleted = await storage_get_row(ext_id, "notes", "note-1", "owner-1")
    finally:
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_wasm_extensions_path = original_wasm_extensions_path
        settings.lnbits_data_folder = original_data_folder

    assert ext_dir.is_dir()
    assert owner_row is not None
    assert owner_row["title"] == "First"
    assert owner_row["tags"] == ["alpha", "beta"]
    assert owner_row["created_at"] == 1_700_000_000
    assert other_owner_row is None
    assert public_row is not None
    assert public_row["title"] == "First"
    assert page["total"] == 1
    assert page["data"][0]["id"] == "note-1"
    assert still_owned is not None
    assert deleted is None


@pytest.mark.anyio
async def test_wasm_storage_atomic_operations_are_owner_scoped_and_versioned(
    tmp_path: Path,
    settings: Settings,
):
    ext_id = f"wasmatomic_{uuid4().hex[:8]}"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    original_data_folder = settings.lnbits_data_folder
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
        Path(settings.lnbits_data_folder).mkdir(parents=True)
        _write_storage_extension(settings, ext_id)
        await migrate_wasm_extension_database(make_installable_extension(ext_id))

        original_row = {
            "id": "match-1",
            "title": "<b>Waiting</b>",
            "count": 1,
            "published": False,
            "tags": ["match"],
            "created_at": 1_700_000_000,
            "owner_id": "row-owner",
            "expected_version": 41,
            "make_immutable": False,
        }
        insert_results = await asyncio.gather(
            storage_insert_if_absent_row(
                ext_id, "notes", "match-1", original_row, "owner-1"
            ),
            storage_insert_if_absent_row(
                ext_id,
                "notes",
                "match-1",
                {**original_row, "title": "Must not replace"},
                "owner-1",
            ),
        )
        created, row, version = next(result for result in insert_results if result[0])
        duplicate = next(result for result in insert_results if not result[0])
        await storage_set_row(
            ext_id,
            "notes",
            {**original_row, "title": "Updated through storage.set"},
            "owner-1",
        )
        foreign = await storage_insert_if_absent_row(
            ext_id,
            "notes",
            "match-1",
            original_row,
            "owner-2",
        )

        update_one = {**original_row, "title": "Finished A"}
        update_two = {**original_row, "title": "Finished B"}
        results = await asyncio.gather(
            storage_compare_and_set_row(
                ext_id,
                "notes",
                "match-1",
                2,
                update_one,
                "owner-1",
                make_immutable=True,
            ),
            storage_compare_and_set_row(
                ext_id,
                "notes",
                "match-1",
                2,
                update_two,
                "owner-1",
                make_immutable=True,
            ),
        )
        stale = await storage_compare_and_set_row(
            ext_id, "notes", "match-1", 2, update_one, "owner-1"
        )
        foreign_update = await storage_compare_and_set_row(
            ext_id, "notes", "match-1", 3, update_one, "owner-2"
        )
        finalized_update = await storage_compare_and_set_row(
            ext_id, "notes", "match-1", 3, update_one, "owner-1"
        )
        await storage_set_row(
            ext_id,
            "notes",
            {**original_row, "title": "Must remain finalized"},
            "owner-1",
        )
        await storage_delete_row(ext_id, "notes", "match-1", "owner-1")
        stored_row, stored_version = await storage_get_row_with_version(
            ext_id, "notes", "match-1", "owner-1"
        )
        foreign_row, foreign_version = await storage_get_row_with_version(
            ext_id, "notes", "match-1", "owner-2"
        )
    finally:
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_wasm_extensions_path = original_wasm_extensions_path
        settings.lnbits_data_folder = original_data_folder

    assert created is True
    assert row["title"] in {"Waiting", "Must not replace"}
    assert version == 1
    assert duplicate[0] is False
    assert duplicate[1:] == (row, 1)
    assert sorted(result[0] for result in insert_results) == [False, True]
    assert foreign == (False, None, None)
    assert sorted(results) == [False, True]
    assert stale is False
    assert foreign_update is False
    assert finalized_update is False
    assert stored_row is not None
    assert stored_row["title"] in {"Finished A", "Finished B"}
    assert stored_row["owner_id"] == "row-owner"
    assert stored_row["expected_version"] == 41
    assert stored_row["make_immutable"] is False
    assert stored_version == 3
    assert foreign_row is None
    assert foreign_version is None


@pytest.mark.anyio
async def test_wasm_storage_immutable_insert_compares_only_provided_fields(
    tmp_path: Path,
    settings: Settings,
):
    from lnbits.core.wasm_ext.api.authoritative_channels import _transaction

    ext_id = f"wasmimmutable_{uuid4().hex[:8]}"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    original_data_folder = settings.lnbits_data_folder
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
        Path(settings.lnbits_data_folder).mkdir(parents=True)
        _write_storage_extension(settings, ext_id)
        await migrate_wasm_extension_database(make_installable_extension(ext_id))

        # Omit nullable/defaulted columns: the write-once check must only
        # compare the fields the caller supplied.
        partial_row = {
            "id": "partial-1",
            "title": "Waiting",
            "tags": ["match"],
            "created_at": 1_700_000_000,
        }
        database = storage_crud._database(ext_id)
        async with database.connect() as conn:
            async with _transaction(conn):
                await storage_insert_immutable_row(
                    conn, ext_id, "notes", partial_row, "owner-1"
                )
            # Replaying the same provided fields stays idempotent.
            async with _transaction(conn):
                await storage_insert_immutable_row(
                    conn, ext_id, "notes", partial_row, "owner-1"
                )
            with pytest.raises(
                ValueError, match="conflicts with an existing immutable row"
            ):
                async with _transaction(conn):
                    await storage_insert_immutable_row(
                        conn,
                        ext_id,
                        "notes",
                        {**partial_row, "title": "changed"},
                        "owner-1",
                    )
        stored = await storage_get_immutable_row(
            ext_id, "notes", "partial-1", "owner-1"
        )
    finally:
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_wasm_extensions_path = original_wasm_extensions_path
        settings.lnbits_data_folder = original_data_folder

    assert stored is not None
    assert stored["title"] == "Waiting"
    assert stored["count"] == 0
    assert stored["published"] is False


@pytest.mark.anyio
async def test_wasm_storage_migration_adds_version_to_existing_tables(
    tmp_path: Path,
    settings: Settings,
):
    ext_id = f"wasmupgrade_{uuid4().hex[:8]}"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    original_data_folder = settings.lnbits_data_folder
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
        Path(settings.lnbits_data_folder).mkdir(parents=True)
        _write_storage_extension(settings, ext_id)

        database = Database(f"ext_{ext_id}")
        async with database.connect() as conn:
            await conn.execute(f"""
                CREATE TABLE {ext_id}.notes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    count INT NOT NULL DEFAULT 0,
                    published BOOLEAN NOT NULL DEFAULT false,
                    tags TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    {OWNER_ID_FIELD} TEXT NOT NULL
                )
                """)
            await conn.execute(
                f"""
                INSERT INTO {ext_id}.notes
                    (id, title, count, published, tags, created_at, {OWNER_ID_FIELD})
                VALUES
                    (:id, :title, :count, :published, :tags,
                     {conn.timestamp_placeholder('created_at')}, :owner_id)
                """,  # noqa: S608
                {
                    "id": "legacy-1",
                    "title": "Legacy",
                    "count": 1,
                    "published": False,
                    "tags": "[]",
                    "created_at": 1_700_000_000,
                    "owner_id": "owner-1",
                },
            )

        await migrate_wasm_extension_database(make_installable_extension(ext_id))
        row, version = await storage_get_row_with_version(
            ext_id, "notes", "legacy-1", "owner-1"
        )
    finally:
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_wasm_extensions_path = original_wasm_extensions_path
        settings.lnbits_data_folder = original_data_folder

    assert row is not None
    assert row["title"] == "Legacy"
    assert version == 1
    assert VERSION_FIELD not in row


@pytest.mark.anyio
async def test_wasm_storage_public_append_generates_id_and_counts_by_owner(
    tmp_path: Path,
    settings: Settings,
):
    ext_id = f"wasmstore_{uuid4().hex[:8]}"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    original_data_folder = settings.lnbits_data_folder
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
        Path(settings.lnbits_data_folder).mkdir(parents=True)
        _write_storage_extension(settings, ext_id)

        await migrate_wasm_extension_database(make_installable_extension(ext_id))
        await storage_set_row(
            ext_id,
            "threads",
            {"id": "thread-1", "title": "Support"},
            "owner-1",
        )
        message_id = await storage_append_public_row(
            ext_id,
            "messages",
            {"thread_id": "thread-1", "message": "Hello"},
            "owner-1",
        )
        owner_count = await storage_count_rows(
            ext_id,
            "messages",
            {"thread_id": "thread-1"},
            owner_id="owner-1",
        )
        other_owner_count = await storage_count_rows(
            ext_id,
            "messages",
            {"thread_id": "thread-1"},
            owner_id="owner-2",
        )
        message = await storage_get_row(ext_id, "messages", message_id, "owner-1")
    finally:
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_wasm_extensions_path = original_wasm_extensions_path
        settings.lnbits_data_folder = original_data_folder

    assert message_id
    assert owner_count == 1
    assert other_owner_count == 0
    assert message is not None
    assert message["id"] == message_id
    assert message["thread_id"] == "thread-1"
    assert message["message"] == "Hello"


@pytest.mark.anyio
async def test_wasm_storage_rejects_reserved_fields_and_invalid_identifiers(
    tmp_path: Path,
    settings: Settings,
):
    ext_id = f"wasmstore_{uuid4().hex[:8]}"
    original_extensions_path = settings.lnbits_extensions_path
    original_wasm_extensions_path = settings.lnbits_wasm_extensions_path
    original_data_folder = settings.lnbits_data_folder
    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
        Path(settings.lnbits_data_folder).mkdir(parents=True)
        _write_storage_extension(settings, ext_id)

        with pytest.raises(ValueError, match="Invalid WASM storage SQL identifier"):
            await storage_get_row(ext_id, "notes;DROP", "note-1", "owner-1")

        with pytest.raises(ValueError, match="reserved owner field"):
            await storage_set_row(
                ext_id,
                "notes",
                {"id": "note-1", OWNER_ID_FIELD: "owner-2"},
                "owner-1",
            )

        schema_path = settings.wasm_extensions_dir / ext_id / "storage" / "schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["tables"]["notes"]["fields"].append(
            {"name": OWNER_ID_FIELD, "type": "string"}
        )
        schema_path.write_text(json.dumps(schema), encoding="utf-8")

        with pytest.raises(ValueError, match="reserved field"):
            await storage_get_row(ext_id, "notes", "note-1", "owner-1")
    finally:
        settings.lnbits_extensions_path = original_extensions_path
        settings.lnbits_wasm_extensions_path = original_wasm_extensions_path
        settings.lnbits_data_folder = original_data_folder


def _temporary_database(
    tmp_path: Path,
    settings: Settings,
    name: str,
) -> Database:
    settings.lnbits_data_folder = str(tmp_path / "data")
    Path(settings.lnbits_data_folder).mkdir(parents=True, exist_ok=True)
    return Database(name)


async def _temporary_core_crud_database(
    tmp_path: Path,
    settings: Settings,
) -> Database:
    if DB_TYPE != SQLITE:
        return core_db

    db = _temporary_database(tmp_path, settings, f"core_{uuid4().hex[:8]}")
    async with db.connect() as conn:
        await conn.execute("""
            CREATE TABLE dbversions (
                db TEXT PRIMARY KEY,
                version INT NOT NULL
            )
        """)
        await update_migration_version(conn, "core", 48)
        await m010_create_installed_extensions_table(conn)
        await m046_add_permissions_to_installed_extensions(conn)
        await m047_create_wasm_invocations_table(conn)
        await m048_add_wasm_runtime_limits_to_installed_extensions(conn)
    return db


def _write_storage_extension(settings: Settings, ext_id: str) -> Path:
    ext_dir = settings.wasm_extensions_dir / ext_id
    storage_dir = ext_dir / "storage"
    migrations_dir = storage_dir / "migrations"
    migrations_dir.mkdir(parents=True)
    schema: dict[str, Any] = {
        "tables": {
            "notes": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "title", "type": "string"},
                    {"name": "count", "type": "integer", "default": 0},
                    {"name": "published", "type": "boolean", "default": False},
                    {"name": "tags", "type": "string", "list": True},
                    {"name": "created_at", "type": "datetime"},
                    {"name": "owner_id", "type": "string", "nullable": True},
                    {
                        "name": "expected_version",
                        "type": "integer",
                        "nullable": True,
                    },
                    {
                        "name": "make_immutable",
                        "type": "boolean",
                        "nullable": True,
                    },
                ]
            },
            "threads": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "title", "type": "string"},
                ]
            },
            "messages": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "thread_id", "type": "string"},
                    {"name": "message", "type": "string"},
                ]
            },
        }
    }
    migration = {
        "operations": [
            {
                "op": "create_table",
                "table": "notes",
                "fields": schema["tables"]["notes"]["fields"],
            },
            {
                "op": "create_table",
                "table": "threads",
                "fields": schema["tables"]["threads"]["fields"],
            },
            {
                "op": "create_table",
                "table": "messages",
                "fields": schema["tables"]["messages"]["fields"],
            },
        ]
    }
    (storage_dir / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (migrations_dir / "001_init.json").write_text(
        json.dumps(migration),
        encoding="utf-8",
    )
    return ext_dir
