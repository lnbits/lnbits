from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from lnbits.settings import settings


@dataclass(frozen=True)
class WasmExtension:
    id: str
    name: str
    version: str
    root_path: Path
    module_path: Path
    wit_path: Path | None
    world: str
    host_api: str
    exports: list[dict[str, Any]]
    config: dict[str, Any]


def is_wasm_extension_id(ext_id: str) -> bool:
    config = load_wasm_extension_config(ext_id)
    return bool(config and config.get("extension_type") == "wasm")


def is_wasm_extension_dir(ext_dir: Path) -> bool:
    config = _load_json(ext_dir / "config.json")
    return bool(config and config.get("extension_type") == "wasm")


def load_wasm_extension_config(ext_id: str) -> dict[str, Any] | None:
    ext_dir = Path(settings.lnbits_extensions_path, "extensions", ext_id)
    return _load_json(ext_dir / "config.json")


def register_wasm_extension(app: FastAPI, ext_id: str) -> WasmExtension:
    loaded = load_wasm_extension(ext_id)
    from .wasm import warm_wasm_extension

    warm_wasm_extension(loaded)
    _mount_wasm_extension_static(app, loaded)
    _register_wasm_extension_routes(app, loaded)
    _register_wasm_extension_api_routes(app, loaded)

    extensions = getattr(app.state, "lnbits_wasm_extensions", {})
    extensions[ext_id] = loaded
    app.state.lnbits_wasm_extensions = extensions

    settings.activate_extension_paths(ext_id, "", [])
    logger.info(
        f"Loaded WASM extension '{loaded.id}' "
        f"({loaded.module_path.stat().st_size} bytes)."
    )
    return loaded


def load_wasm_extension(ext_id: str) -> WasmExtension:
    ext_dir = Path(settings.lnbits_extensions_path, "extensions", ext_id)
    config = load_wasm_extension_config(ext_id)
    if not config:
        raise FileNotFoundError(f"Missing WASM extension config for '{ext_id}'.")
    if config.get("extension_type") != "wasm":
        raise ValueError(f"Extension '{ext_id}' is not a WASM extension.")

    wasm_config = config.get("wasm") or {}
    module_path = _extension_path(ext_dir, wasm_config.get("module"))
    wit_path = _optional_extension_path(ext_dir, wasm_config.get("wit"))
    _check_wasm_module(module_path)
    if wit_path and not wit_path.is_file():
        raise FileNotFoundError(f"WIT file not found: {wit_path}")

    return WasmExtension(
        id=config.get("id") or ext_id,
        name=config.get("name") or ext_id,
        version=config.get("version") or "0.0",
        root_path=ext_dir,
        module_path=module_path,
        wit_path=wit_path,
        world=wasm_config.get("world") or "",
        host_api=wasm_config.get("host_api") or "lnbits.core.extensions.ExtensionAPI",
        exports=wasm_config.get("exports") or [],
        config=config,
    )


def _mount_wasm_extension_static(app: FastAPI, extension: WasmExtension) -> None:
    static_path = extension.root_path / "static"
    if not static_path.is_dir():
        return

    mount_path = f"/{extension.id}/static"
    if any(getattr(route, "path", None) == mount_path for route in app.routes):
        return

    app.mount(
        mount_path,
        StaticFiles(directory=static_path),
        name=f"{extension.id}-static",
    )


def _register_wasm_extension_routes(app: FastAPI, extension: WasmExtension) -> None:
    for route_config in extension.config.get("routes") or []:
        route_path = _wasm_extension_route_path(extension, route_config.get("path"))
        entrypoint = _wasm_extension_entrypoint(
            extension, route_config.get("entrypoint")
        )
        _add_wasm_extension_page_route(app, extension, route_path, entrypoint)


def _register_wasm_extension_api_routes(app: FastAPI, extension: WasmExtension) -> None:
    for route_config in extension.config.get("api_routes") or []:
        _add_wasm_extension_api_route(app, extension, route_config)


def _add_wasm_extension_api_route(
    app: FastAPI,
    extension: WasmExtension,
    route_config: dict[str, Any],
) -> None:
    method = _wasm_extension_api_method(extension, route_config.get("method"))
    route_path = _wasm_extension_api_path(extension, route_config.get("path"))
    export_name = _wasm_extension_api_export(extension, route_config.get("export"))
    path_params = route_config.get("path_params") or {}

    if _has_route(app, route_path, method):
        return

    async def invoke_wasm_extension_export(request: Request) -> dict[str, Any]:
        from .wasm import invoke_wasm_extension_export as invoke_export

        try:
            payload = await _read_api_payload(request, path_params)
            return await invoke_export(
                app,
                extension.id,
                export_name,
                payload,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    app.add_api_route(
        route_path,
        invoke_wasm_extension_export,
        methods=[method],
        name=f"{extension.id}:{method}:{route_path}",
        include_in_schema=False,
    )


async def _read_api_payload(
    request: Request,
    path_params: dict[str, str],
) -> dict[str, Any]:
    payload = _read_api_path_params(request, path_params)
    payload.update(_read_api_query_params(request))
    if request.method in {"POST", "PUT", "PATCH"}:
        payload.update(await _read_json_object(request))
    return payload


async def _read_json_object(request: Request) -> dict[str, Any]:
    body = await request.body()
    if not body:
        return {}
    value = json.loads(body)
    if not isinstance(value, dict):
        raise TypeError("WASM extension API payload must be a JSON object.")
    return value


def _read_api_path_params(
    request: Request,
    path_params: dict[str, str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in request.path_params.items():
        target = path_params.get(key) or _snake_to_camel(key)
        payload[target] = value
    return payload


def _read_api_query_params(request: Request) -> dict[str, Any]:
    return {_snake_to_camel(key): value for key, value in request.query_params.items()}


def _wasm_extension_api_export(extension: WasmExtension, export_name: Any) -> str:
    if not isinstance(export_name, str) or not export_name:
        raise ValueError(f"Invalid API export for WASM extension '{extension.id}'.")

    for export in extension.exports:
        if export.get("name") != export_name:
            continue
        if export.get("visibility") in {"public", "authenticated"}:
            return export_name
        raise PermissionError(f"WASM export '{export_name}' is not callable over HTTP.")
    raise KeyError(f"WASM extension '{extension.id}' has no export '{export_name}'.")


def _wasm_extension_api_method(extension: WasmExtension, method: Any) -> str:
    if not isinstance(method, str):
        raise ValueError(f"Invalid API method for WASM extension '{extension.id}'.")
    method = method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError(f"Unsupported API method for WASM extension '{extension.id}'.")
    return method


def _wasm_extension_api_path(extension: WasmExtension, path: Any) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError(f"Invalid API path for WASM extension '{extension.id}'.")
    if path == "/":
        return f"/api/v1/ext/{extension.id}"
    return f"/api/v1/ext/{extension.id}{path}"


def _has_route(app: FastAPI, route_path: str, method: str) -> bool:
    for route in app.routes:
        if getattr(route, "path", None) != route_path:
            continue
        methods = getattr(route, "methods", set()) or set()
        if method in methods:
            return True
    return False


def _snake_to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _add_wasm_extension_page_route(
    app: FastAPI,
    extension: WasmExtension,
    route_path: str,
    entrypoint: Path,
) -> None:
    if any(getattr(route, "path", None) == route_path for route in app.routes):
        return

    async def serve_wasm_extension_page() -> FileResponse:
        return FileResponse(entrypoint)

    app.add_api_route(
        route_path,
        serve_wasm_extension_page,
        methods=["GET"],
        name=f"{extension.id}:{route_path}",
        include_in_schema=False,
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as config_file:
        value = json.load(config_file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in '{path}'.")
    return value


def _extension_path(ext_dir: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing relative path for extension '{ext_dir.name}'.")
    path = (ext_dir / value).resolve()
    if ext_dir.resolve() not in path.parents:
        raise ValueError(f"Extension path escapes extension root: {value}")
    return path


def _optional_extension_path(ext_dir: Path, value: Any) -> Path | None:
    if value is None:
        return None
    return _extension_path(ext_dir, value)


def _wasm_extension_route_path(extension: WasmExtension, path: Any) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError(f"Invalid route path for WASM extension '{extension.id}'.")
    if path == "/":
        return f"/{extension.id}/"
    return f"/{extension.id}{path}"


def _wasm_extension_entrypoint(extension: WasmExtension, entrypoint: Any) -> Path:
    if not isinstance(entrypoint, str) or not entrypoint.startswith("/"):
        raise ValueError(
            f"Invalid route entrypoint for WASM extension '{extension.id}'."
        )

    static_prefix = f"/{extension.id}/static/"
    if not entrypoint.startswith(static_prefix):
        raise ValueError(
            f"Route entrypoint for WASM extension '{extension.id}' must be under "
            f"'{static_prefix}'."
        )

    path = extension.root_path / "static" / entrypoint.removeprefix(static_prefix)
    path = path.resolve()
    if extension.root_path.resolve() not in path.parents:
        raise ValueError(f"Route entrypoint escapes extension root: {entrypoint}")
    if not path.is_file():
        raise FileNotFoundError(f"Route entrypoint not found: {path}")
    return path


def _check_wasm_module(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"WASM module not found: {path}")
    with path.open("rb") as wasm_file:
        magic = wasm_file.read(4)
    if magic != b"\0asm":
        raise ValueError(f"Invalid WASM module: {path}")
