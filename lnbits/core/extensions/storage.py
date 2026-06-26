from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from lnbits.core.crud import update_migration_version
from lnbits.core.db import db as core_db
from lnbits.core.models import DbVersion
from lnbits.core.models.extensions import InstallableExtension
from lnbits.db import POSTGRES, SQLITE, Connection, Database
from lnbits.settings import settings

_MIGRATION_FILE_RE = re.compile(r"^(\d+)_.*\.json$")
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


async def storage_get_row(
    ext_id: str,
    table: str,
    row_id: str,
) -> dict[str, Any] | None:
    table_schema = _load_table_schema(ext_id, table)
    query = f"""
        SELECT * FROM {_table_ref_for_schema(ext_id, table)}
        WHERE id = :id
    """  # noqa: S608
    async with Database(f"ext_{ext_id}").connect() as conn:
        row = await conn.fetchone(query, {"id": row_id})
    return _row_from_db(table_schema, row) if row else None


async def storage_set_row(
    ext_id: str,
    table: str,
    data: dict[str, Any],
) -> None:
    table_schema = _load_table_schema(ext_id, table)
    clean_data = _data_to_db(table_schema, data, require_id=True)
    columns = list(clean_data.keys())
    placeholders = [f":{column}" for column in columns]
    updates = [f"{column} = excluded.{column}" for column in columns if column != "id"]
    conflict_sql = f"DO UPDATE SET {', '.join(updates)}" if updates else "DO NOTHING"
    query = f"""
        INSERT INTO {_table_ref_for_schema(ext_id, table)}
            ({", ".join(columns)})
        VALUES
            ({", ".join(placeholders)})
        ON CONFLICT (id) {conflict_sql}
    """  # noqa: S608

    async with Database(f"ext_{ext_id}").connect() as conn:
        await conn.execute(query, clean_data)


async def storage_list_rows(
    ext_id: str,
    table: str,
    filters: dict[str, Any],
    *,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    table_schema = _load_table_schema(ext_id, table)
    clean_filters = _filters_to_db(table_schema, filters)
    where_sql = ""
    if clean_filters:
        clauses = [f"{field} = :filter_{field}" for field in clean_filters]
        where_sql = "WHERE " + " AND ".join(clauses)

    values = {f"filter_{field}": value for field, value in clean_filters.items()}
    values.update({"limit": min(limit, 1000), "offset": offset})
    query = f"""
        SELECT * FROM {_table_ref_for_schema(ext_id, table)}
        {where_sql}
        LIMIT :limit
        OFFSET :offset
    """  # noqa: S608

    async with Database(f"ext_{ext_id}").connect() as conn:
        rows = await conn.fetchall(query, values)
    return [_row_from_db(table_schema, row) for row in rows]


async def storage_get_paginated_rows(
    ext_id: str,
    table: str,
    filters: dict[str, Any],
    *,
    search: str | None,
    search_fields: list[str],
    sort_by: str | None,
    descending: bool,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    table_schema = _load_table_schema(ext_id, table)
    where_sql, values = _where_sql(table_schema, filters, search, search_fields)
    order_sql = _order_sql(table_schema, sort_by, descending)
    count_values = dict(values)
    values.update({"limit": min(limit, 1000), "offset": offset})

    table_ref = _table_ref_for_schema(ext_id, table)
    rows_query = f"""
        SELECT * FROM {table_ref}
        {where_sql}
        {order_sql}
        LIMIT :limit
        OFFSET :offset
    """  # noqa: S608
    count_query = f"""
        SELECT COUNT(*) AS count FROM {table_ref}
        {where_sql}
    """  # noqa: S608

    async with Database(f"ext_{ext_id}").connect() as conn:
        rows = await conn.fetchall(rows_query, values)
        count_row = await conn.fetchone(count_query, count_values)

    return {
        "data": [_row_from_db(table_schema, row) for row in rows],
        "total": int(count_row["count"]) if count_row else 0,
    }


async def storage_delete_row(
    ext_id: str,
    table: str,
    row_id: str,
) -> None:
    _load_table_schema(ext_id, table)
    query = f"""
        DELETE FROM {_table_ref_for_schema(ext_id, table)}
        WHERE id = :id
    """  # noqa: S608
    async with Database(f"ext_{ext_id}").connect() as conn:
        await conn.execute(query, {"id": row_id})


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


def _load_table_schema(ext_id: str, table: str) -> dict[str, Any]:
    schema = _load_storage_schema(ext_id)
    tables = schema.get("tables")
    if not isinstance(tables, dict):
        raise ValueError(f"WASM extension '{ext_id}' has no storage tables schema.")

    _require_identifier({"table": table}, "table")
    table_schema = tables.get(table)
    if not isinstance(table_schema, dict):
        raise ValueError(f"WASM extension '{ext_id}' has no storage table '{table}'.")

    fields = table_schema.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError(f"WASM storage table '{table}' has no fields schema.")

    for field in fields:
        if not isinstance(field, dict):
            raise ValueError(f"WASM storage table '{table}' has invalid field schema.")
        _require_identifier(field, "name")
    return table_schema


def _load_storage_schema(ext_id: str) -> dict[str, Any]:
    schema_path = (
        Path(settings.lnbits_extensions_path)
        / "extensions"
        / ext_id
        / "storage"
        / "schema.json"
    )
    if not schema_path.is_file():
        raise ValueError(f"WASM extension '{ext_id}' has no storage schema.")
    return _load_json(schema_path)


def _data_to_db(
    table_schema: dict[str, Any],
    data: dict[str, Any],
    *,
    require_id: bool,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("WASM storage row data must be an object.")
    if require_id and not data.get("id"):
        raise ValueError("WASM storage row data must include an id.")

    fields = _fields_by_name(table_schema)
    unknown_fields = sorted(set(data) - set(fields))
    if unknown_fields:
        raise ValueError(
            "WASM storage row has unknown fields: " + ", ".join(unknown_fields)
        )

    return {
        field_name: _value_to_db(fields[field_name], value)
        for field_name, value in data.items()
    }


def _filters_to_db(
    table_schema: dict[str, Any],
    filters: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(filters, dict):
        raise ValueError("WASM storage filters must be an object.")

    fields = _fields_by_name(table_schema)
    unknown_fields = sorted(set(filters) - set(fields))
    if unknown_fields:
        raise ValueError(
            "WASM storage filters have unknown fields: " + ", ".join(unknown_fields)
        )

    return {
        field_name: _value_to_db(fields[field_name], value)
        for field_name, value in filters.items()
    }


def _where_sql(
    table_schema: dict[str, Any],
    filters: dict[str, Any],
    search: str | None,
    search_fields: list[str],
) -> tuple[str, dict[str, Any]]:
    clean_filters = _filters_to_db(table_schema, filters)
    clauses = [f"{field} = :filter_{field}" for field in clean_filters]
    values = {f"filter_{field}": value for field, value in clean_filters.items()}

    clean_search = search.strip().lower() if search else ""
    if clean_search:
        fields = _fields_by_name(table_schema)
        invalid_fields = sorted(set(search_fields) - set(fields))
        if invalid_fields:
            raise ValueError(
                "WASM storage search has unknown fields: " + ", ".join(invalid_fields)
            )
        if search_fields:
            search_clause = " OR ".join(
                f"LOWER(CAST({field} AS TEXT)) LIKE :search" for field in search_fields
            )
            clauses.append(f"({search_clause})")
            values["search"] = f"%{clean_search}%"

    return ("WHERE " + " AND ".join(clauses), values) if clauses else ("", values)


def _order_sql(
    table_schema: dict[str, Any],
    sort_by: str | None,
    descending: bool,
) -> str:
    if not sort_by:
        return ""
    fields = _fields_by_name(table_schema)
    if sort_by not in fields:
        raise ValueError(f"WASM storage sort field is unknown: {sort_by}")
    direction = "DESC" if descending else "ASC"
    return f"ORDER BY {sort_by} {direction}"


def _row_from_db(
    table_schema: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    fields = _fields_by_name(table_schema)
    return {
        field_name: _value_from_db(fields[field_name], value)
        for field_name, value in dict(row).items()
        if field_name in fields
    }


def _fields_by_name(table_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = table_schema.get("fields")
    if not isinstance(fields, list):
        raise ValueError("WASM storage table schema fields must be a list.")
    return {field["name"]: field for field in fields}


def _value_to_db(field: dict[str, Any], value: Any) -> Any:  # noqa: C901
    if value is None:
        if field.get("nullable", False):
            return None
        raise ValueError(f"WASM storage field '{field['name']}' cannot be null.")

    if field.get("list") is True:
        if not isinstance(value, list):
            raise ValueError(f"WASM storage field '{field['name']}' must be a list.")
        return json.dumps(value)

    field_type = field.get("type")
    if field_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"WASM storage field '{field['name']}' must be a string.")
        return value
    if field_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"WASM storage field '{field['name']}' must be an integer."
            )
        return value
    if field_type == "number":
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"WASM storage field '{field['name']}' must be a number.")
        return value
    if field_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"WASM storage field '{field['name']}' must be a boolean.")
        return value
    if field_type == "datetime":
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, datetime):
            return value
        raise ValueError(
            f"WASM storage field '{field['name']}' must be a Unix timestamp."
        )
    raise ValueError(f"Unsupported WASM storage field type: {field_type}")


def _value_from_db(field: dict[str, Any], value: Any) -> Any:
    if value is None:
        return None

    if field.get("list") is True:
        if isinstance(value, str):
            return json.loads(value)
        return value

    field_type = field.get("type")
    if field_type == "boolean":
        return bool(value)
    if field_type == "datetime":
        if isinstance(value, datetime):
            return int(value.replace(tzinfo=timezone.utc).timestamp())
        if isinstance(value, int | float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(datetime.fromisoformat(value).timestamp())
            except ValueError:
                return value
    return value


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


def _table_ref_for_schema(ext_id: str, table: str) -> str:
    _require_identifier({"schema": ext_id}, "schema")
    _require_identifier({"table": table}, "table")
    return f"{ext_id}.{table}"


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
