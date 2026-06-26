from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from lnbits.core.crud import update_migration_version
from lnbits.core.db import db as core_db
from lnbits.core.models import DbVersion
from lnbits.core.models.extensions import InstallableExtension
from lnbits.db import POSTGRES, SQLITE, Connection, Database

_MIGRATION_FILE_RE = re.compile(r"^(\d+)_.*\.json$")
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


async def migrate_wasm_extension_database(
    ext: InstallableExtension,
    current_version: DbVersion | None = None,
) -> None:
    migrations_dir = ext.ext_dir / "storage" / "migrations"
    migration_files = _migration_files(migrations_dir)
    if not migration_files:
        logger.debug(f"No storage migrations for WASM extension '{ext.id}'.")
        return

    ext_db = Database(f"ext_{ext.id}")
    async with ext_db.connect() as conn:
        for version, path in migration_files:
            if current_version and version <= current_version.version:
                continue
            logger.debug(f"running WASM storage migration {ext.id}.{version}")
            print(f"running migration {ext.id}.{version}")
            await _run_storage_migration(conn, path)
            await _update_wasm_migration_version(conn, ext.id, version)


def _migration_files(migrations_dir: Path) -> list[tuple[int, Path]]:
    if not migrations_dir.is_dir():
        return []

    files: list[tuple[int, Path]] = []
    for path in migrations_dir.glob("*.json"):
        match = _MIGRATION_FILE_RE.match(path.name)
        if not match:
            raise ValueError(f"Invalid WASM storage migration filename: {path.name}")
        files.append((int(match.group(1)), path))
    return sorted(files)


async def _run_storage_migration(db: Connection, path: Path) -> None:
    migration = _load_json(path)
    operations = migration.get("operations")
    if not isinstance(operations, list):
        raise ValueError(f"WASM storage migration '{path}' has no operations list.")

    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError(f"WASM storage migration '{path}' has invalid operation.")
        sql = _operation_sql(db, operation)
        await db.execute(sql)


def _operation_sql(db: Connection, operation: dict[str, Any]) -> str:
    op = operation.get("op")
    if op == "create_table":
        return _create_table_sql(db, operation)
    if op == "add_field":
        return _add_field_sql(db, operation)
    if op == "create_index":
        return _create_index_sql(db, operation)
    raise ValueError(f"Unsupported WASM storage migration operation: {op}")


def _create_table_sql(db: Connection, operation: dict[str, Any]) -> str:
    table = _require_identifier(operation, "table")
    fields = _require_fields(operation)
    if not any(field.get("name") == "id" for field in fields):
        raise ValueError(f"WASM storage table '{table}' must define an id field.")

    columns = [
        _column_sql(db, field, primary_key=field.get("name") == "id")
        for field in fields
    ]
    return f"""
        CREATE TABLE IF NOT EXISTS {_table_ref(db, table)} (
            {", ".join(columns)}
        );
    """


def _add_field_sql(db: Connection, operation: dict[str, Any]) -> str:
    table = _require_identifier(operation, "table")
    field = _field_from_add_field_operation(operation)
    return f"""
        ALTER TABLE {_table_ref(db, table)}
        ADD COLUMN {_column_sql(db, field)};
    """


def _create_index_sql(db: Connection, operation: dict[str, Any]) -> str:
    table = _require_identifier(operation, "table")
    name = _require_identifier(operation, "name")
    field = _require_identifier(operation, "field")

    if db.type == SQLITE and db.schema:
        return f"""
            CREATE INDEX IF NOT EXISTS {_schema_ref(db, name)}
            ON {table} ({field});
        """

    return f"""
        CREATE INDEX IF NOT EXISTS {name}
        ON {_table_ref(db, table)} ({field});
    """


def _column_sql(
    db: Connection,
    field: dict[str, Any],
    *,
    primary_key: bool = False,
) -> str:
    name = _require_identifier(field, "name")
    column_type = _field_type_sql(db, field)
    parts = [name, column_type]

    if primary_key:
        parts.append("PRIMARY KEY")
    elif not field.get("nullable", False):
        parts.append("NOT NULL")

    if "default" in field:
        parts.append(f"DEFAULT {_default_sql(field['default'])}")

    return " ".join(parts)


def _field_type_sql(db: Connection, field: dict[str, Any]) -> str:
    if field.get("list") is True:
        return "TEXT"

    field_type = field.get("type")
    if field_type == "string":
        return "TEXT"
    if field_type == "integer":
        return db.big_int
    if field_type == "number":
        return "DOUBLE PRECISION" if db.type == POSTGRES else "REAL"
    if field_type == "boolean":
        return "BOOLEAN"
    if field_type == "datetime":
        return "TIMESTAMP"
    raise ValueError(f"Unsupported WASM storage field type: {field_type}")


def _default_sql(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return _quote_sql_string(value)
    if isinstance(value, list | dict):
        return _quote_sql_string(json.dumps(value))
    raise ValueError(f"Unsupported WASM storage default value: {value}")


def _field_from_add_field_operation(operation: dict[str, Any]) -> dict[str, Any]:
    field = {
        "name": operation.get("field"),
        "type": operation.get("type"),
    }
    for key in ("default", "list", "nullable"):
        if key in operation:
            field[key] = operation[key]
    return field


def _require_fields(operation: dict[str, Any]) -> list[dict[str, Any]]:
    fields = operation.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError("WASM storage create_table operation requires fields.")
    if not all(isinstance(field, dict) for field in fields):
        raise ValueError("WASM storage fields must be objects.")
    return fields


def _require_identifier(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not _SQL_IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid WASM storage SQL identifier for '{key}': {value}")
    return value


def _table_ref(db: Connection, table: str) -> str:
    if db.schema:
        return f"{_schema_ref(db, table)}"
    return table


def _schema_ref(db: Connection, name: str) -> str:
    if not db.schema:
        return name
    if not _SQL_IDENTIFIER_RE.match(db.schema):
        raise ValueError(f"Invalid WASM extension storage schema: {db.schema}")
    return f"{db.schema}.{name}"


def _quote_sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as json_file:
        data = json.load(json_file)
    if not isinstance(data, dict):
        raise ValueError(f"WASM storage migration '{path}' must be a JSON object.")
    return data


async def _update_wasm_migration_version(
    db: Connection,
    ext_id: str,
    version: int,
) -> None:
    if db.schema is None:
        await update_migration_version(db, ext_id, version)
    else:
        async with core_db.connect() as conn:
            await update_migration_version(conn, ext_id, version)
