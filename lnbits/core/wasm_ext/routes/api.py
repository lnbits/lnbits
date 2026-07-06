from __future__ import annotations

import json
import re
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request

from lnbits.core.models import Account
from lnbits.decorators import check_access_token, check_account_exists

from ..wasm.invoke import invoke_wasm_extension_export
from ..wasm.loader import WasmExtension


def register_wasm_extension_api_routes(app: FastAPI, extension: WasmExtension) -> None:
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
    auth = _wasm_extension_route_auth(extension, route_config.get("auth"))

    if _has_route(app, route_path, method):
        return

    async def invoke_wasm_api_request(
        request: Request,
        account: Account | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        try:
            payload = await _read_api_payload(request, path_params)
            return await invoke_wasm_extension_export(
                extension.id,
                export_name,
                payload,
                user=account,
                access_token=access_token,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def invoke_private_wasm_extension_export(
        request: Request,
        access_token: Annotated[str | None, Depends(check_access_token)],
        account: Account = Depends(check_account_exists),
    ) -> dict[str, Any]:
        return await invoke_wasm_api_request(request, account, access_token)

    async def invoke_public_wasm_extension_export(request: Request) -> dict[str, Any]:
        return await invoke_wasm_api_request(request)

    app.add_api_route(
        route_path,
        (
            invoke_public_wasm_extension_export
            if auth == "public"
            else invoke_private_wasm_extension_export
        ),
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


def _wasm_extension_route_auth(extension: WasmExtension, auth: Any) -> str:
    if auth in {"public", "user"}:
        return auth
    raise ValueError(f"Invalid route auth for WASM extension '{extension.id}'.")


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


def _path_template_pattern(path: str) -> str:
    pattern = re.sub(r"\\{[^/{}]+\\}", r"[^/]+", re.escape(path))
    return f"^{pattern}$"
