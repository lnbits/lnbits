import asyncio
import json
import sys
from pathlib import Path

from wasmtime import (
    Caller,
    Config,
    Engine,
    Func,
    FuncType,
    Linker,
    Module,
    Store,
    ValType,
)

from lnbits.db import Database
from lnbits.settings import settings

_kv_schema_cache: dict[str, dict] = {}


def _load_kv_schema(ext_id: str) -> dict:
    if ext_id in _kv_schema_cache:
        return _kv_schema_cache[ext_id]
    try:
        conf_path = Path(
            settings.lnbits_extensions_path, "extensions", ext_id, "config.json"
        )
        if not conf_path.is_file():
            _kv_schema_cache[ext_id] = {}
            return _kv_schema_cache[ext_id]
        with open(conf_path, "r+") as json_file:
            config_json = json.load(json_file)
        schema = config_json.get("kv_schema", {})
        if not isinstance(schema, dict):
            schema = {}
        _kv_schema_cache[ext_id] = schema
        return schema
    except Exception:
        _kv_schema_cache[ext_id] = {}
        return _kv_schema_cache[ext_id]


def _schema_for_key(schema: dict, key: str) -> dict | None:
    if not schema:
        return None
    entry = schema.get(key)
    return entry if isinstance(entry, dict) else None


def _coerce_schema_value(schema_entry: dict, value: str):
    value_type = schema_entry.get("type", "string")
    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "bool":
        if value.lower() in {"true", "1", "yes", "y"}:
            return True
        if value.lower() in {"false", "0", "no", "n"}:
            return False
        raise ValueError("Invalid bool value")
    if value_type == "json":
        return json.loads(value)
    return value


def _run(coro):
    return asyncio.run(coro)


def _ensure_kv_table(db: Database, ext_id: str) -> str:
    table = f"{ext_id}.kv" if db.schema else "kv"
    return f"""
    CREATE TABLE IF NOT EXISTS {table} (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """


def _get_memory(caller: Caller):
    memory = caller.get_export("memory")
    if memory is None:
        raise RuntimeError("WASM module does not export memory")
    return memory


def _read_bytes(caller: Caller, ptr: int, length: int) -> bytes:
    memory = _get_memory(caller)
    return memory.read(caller, ptr, ptr + length)


def _write_bytes(caller: Caller, ptr: int, data: bytes) -> None:
    memory = _get_memory(caller)
    memory.write(caller, data, ptr)


def _db_get(
    db: Database,
    ext_id: str,
    caller: Caller,
    key_ptr: int,
    key_len: int,
    out_ptr: int,
    out_len: int,
) -> int:
    key = _read_bytes(caller, key_ptr, key_len).decode(errors="ignore")
    _run(db.execute(_ensure_kv_table(db, ext_id)))
    table = f"{ext_id}.kv" if db.schema else "kv"
    row = _run(
        db.fetchone(
            f"SELECT value FROM {table} WHERE key = :key", {"key": key}
        )
    )
    if not row:
        return 0
    value = str(row.get("value", ""))
    data = value.encode()[: max(0, out_len)]
    _write_bytes(caller, out_ptr, data)
    return len(data)


def _db_set(
    db: Database,
    ext_id: str,
    caller: Caller,
    key_ptr: int,
    key_len: int,
    val_ptr: int,
    val_len: int,
) -> int:
    key = _read_bytes(caller, key_ptr, key_len).decode(errors="ignore")
    value = _read_bytes(caller, val_ptr, val_len).decode(errors="ignore")
    schema = _load_kv_schema(ext_id)
    entry = _schema_for_key(schema, key)
    if schema and not entry:
        raise RuntimeError("Key not allowed by schema")
    if entry:
        try:
            coerced = _coerce_schema_value(entry, value)
        except Exception as exc:
            raise RuntimeError("Invalid value for schema") from exc
        value = json.dumps(coerced) if entry.get("type") == "json" else str(coerced)
    _run(db.execute(_ensure_kv_table(db, ext_id)))
    table = f"{ext_id}.kv" if db.schema else "kv"
    row = _run(
        db.fetchone(
            f"SELECT key FROM {table} WHERE key = :key", {"key": key}
        )
    )
    if row:
        _run(
            db.execute(
                f"UPDATE {table} SET value = :value WHERE key = :key",
                {"key": key, "value": value},
            )
        )
    else:
        _run(
            db.execute(
                f"INSERT INTO {table} (key, value) VALUES (:key, :value)",
                {"key": key, "value": value},
            )
        )
    return len(value)


def _load_module(module_path: Path, ext_id: str):
    config = Config()
    config.consume_fuel = True
    engine = Engine(config)
    store = Store(engine)
    if hasattr(store, "add_fuel"):
        store.add_fuel(settings.lnbits_wasm_fuel)
    module = Module.from_file(engine, str(module_path))
    db = Database(f"ext_{ext_id}")

    def db_get(
        caller: Caller, key_ptr: int, key_len: int, out_ptr: int, out_len: int
    ) -> int:
        return _db_get(db, ext_id, caller, key_ptr, key_len, out_ptr, out_len)

    def db_set(
        caller: Caller, key_ptr: int, key_len: int, val_ptr: int, val_len: int
    ) -> int:
        return _db_set(db, ext_id, caller, key_ptr, key_len, val_ptr, val_len)

    linker = Linker(engine)
    linker.define(
        "host",
        "db_get",
        Func(
            store,
            FuncType(
                [ValType.i32(), ValType.i32(), ValType.i32(), ValType.i32()],
                [ValType.i32()],
            ),
            db_get,
        ),
    )
    linker.define(
        "host",
        "db_set",
        Func(
            store,
            FuncType(
                [ValType.i32(), ValType.i32(), ValType.i32(), ValType.i32()],
                [ValType.i32()],
            ),
            db_set,
        ),
    )

    instance = linker.instantiate(store, module)
    return store, instance


def main() -> int:
    if len(sys.argv) < 4:
        sys.stderr.write(
            "usage: runner.py <module_path> <ext_id> <function> [args...]\n"
        )
        return 2

    module_path = Path(sys.argv[1])
    ext_id = sys.argv[2]
    function_name = sys.argv[3]
    args = sys.argv[4:]

    if not module_path.exists():
        sys.stderr.write(f"module not found: {module_path}\n")
        return 2

    try:
        store, instance = _load_module(module_path, ext_id)
        func = instance.exports(store)[function_name]
        int_args = [int(a) for a in args]
        result = func(store, *int_args)
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        sys.stdout.write(json.dumps(payload))
        return 1

    payload = {"ok": True, "result": int(result)}
    sys.stdout.write(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
