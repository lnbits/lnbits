from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import UUID4

from lnbits.core.crud import get_installed_extension, get_user_from_account
from lnbits.core.models import Account
from lnbits.decorators import (
    check_access_token,
    check_account_exists,
    optional_user_id,
)

from ..wasm.loader import WasmExtension
from .api import (
    WasmRequestBodyTooLargeError,
    _has_route,
    _path_template_pattern,
    _read_json_object,
    _snake_to_camel,
    _wasm_extension_api_export,
    _wasm_extension_api_method,
    _wasm_extension_api_path,
    _wasm_extension_route_auth,
)
from .security import (
    consume_wasm_extension_frame_token,
    wasm_extension_frame_csp,
    wasm_extension_frame_url,
    wasm_extension_wrapper_response,
)


def register_wasm_extension_ui_routes(app: FastAPI, extension: WasmExtension) -> None:
    _add_wasm_extension_frame_config_route(app, extension)

    for route_index, route_config in enumerate(extension.config.ui_routes):
        route_path = _wasm_extension_ui_route_path(extension, route_config.path)
        entrypoint = _wasm_extension_entrypoint(extension, route_config.entrypoint)
        frame_path = f"/ext-frame/{extension.id}/{route_index}"
        auth = _wasm_extension_route_auth(extension, route_config.auth)
        _add_wasm_extension_frame_route(app, extension, frame_path, entrypoint)
        _add_wasm_extension_wrapper_route(
            app,
            extension,
            route_path,
            auth,
        )


def _add_wasm_extension_frame_config_route(
    app: FastAPI,
    extension: WasmExtension,
) -> None:
    route_path = _wasm_extension_frame_config_path(extension)
    if _has_route(app, route_path, "POST"):
        return

    async def create_wasm_extension_frame_config(
        request: Request,
        access_token: Annotated[str | None, Depends(check_access_token)],
        usr: UUID4 | None = None,
    ) -> dict[str, Any]:
        try:
            body = await _read_json_object(request)
        except WasmRequestBodyTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        ui_route = _match_wasm_extension_ui_route(extension, body.get("path"))
        auth = ui_route["auth"]

        if auth == "user":
            account = await check_account_exists(request, access_token, usr)
            user_id: str | None = account.id
        else:
            user_id = await _optional_wasm_user_id(request, access_token, usr)

        granted_permission_ids = await _wasm_extension_granted_permission_ids(extension)

        return _wasm_extension_frame_config(
            extension,
            ui_route["frame_path"],
            auth,
            ui_route["path_params"],
            ui_route["route_params"],
            _read_wasm_extension_route_query(body.get("query")),
            user_id,
            granted_permission_ids,
        )

    app.add_api_route(
        route_path,
        create_wasm_extension_frame_config,
        methods=["POST"],
        name=f"{extension.id}:frame-config",
        include_in_schema=False,
    )


def _add_wasm_extension_wrapper_route(
    app: FastAPI,
    extension: WasmExtension,
    route_path: str,
    auth: str,
) -> None:
    if _has_route(app, route_path, "GET"):
        return

    async def serve_private_wasm_extension_page(
        request: Request,
        account: Account = Depends(check_account_exists),
    ) -> Any:
        user = await get_user_from_account(account)
        return wasm_extension_wrapper_response(
            request,
            extension,
            auth,
            user.json() if user else None,
        )

    async def serve_public_wasm_extension_page(request: Request) -> Any:
        return wasm_extension_wrapper_response(
            request,
            extension,
            auth,
            None,
        )

    app.add_api_route(
        route_path,
        (
            serve_public_wasm_extension_page
            if auth == "public"
            else serve_private_wasm_extension_page
        ),
        methods=["GET"],
        name=f"{extension.id}:{route_path}",
        include_in_schema=False,
    )


def _add_wasm_extension_frame_route(
    app: FastAPI,
    extension: WasmExtension,
    frame_path: str,
    entrypoint: Path,
) -> None:
    if _has_route(app, frame_path, "GET"):
        return

    async def serve_wasm_extension_frame(
        request: Request,
        user_id: str | None = Depends(_optional_wasm_user_id),
    ) -> FileResponse:
        consume_wasm_extension_frame_token(request, extension, frame_path, user_id)
        response = FileResponse(entrypoint)
        response.headers["Content-Security-Policy"] = wasm_extension_frame_csp(
            request, extension
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        # Extension access goes through the parent bridge.
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), "
            "clipboard-read=(), usb=()"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    app.add_api_route(
        frame_path,
        serve_wasm_extension_frame,
        methods=["GET"],
        name=f"{extension.id}:frame:{frame_path}",
        include_in_schema=False,
    )


def _wasm_extension_bridge_api_routes(
    extension: WasmExtension,
    public: bool,
) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    for route_config in extension.config.api_routes:
        auth = _wasm_extension_route_auth(extension, route_config.auth)
        if public and auth != "public":
            continue
        method = _wasm_extension_api_method(extension, route_config.method)
        path = _wasm_extension_api_path(extension, route_config.path)
        _wasm_extension_api_export(extension, route_config.export)
        routes.append(
            {
                "method": method,
                "path": path,
                "pattern": _path_template_pattern(path),
            }
        )
    return routes


def _wasm_extension_frame_config_path(extension: WasmExtension) -> str:
    return f"/api/v1/ext/{extension.id}/_ui/frame"


def _match_wasm_extension_ui_route(
    extension: WasmExtension,
    path: Any,
) -> dict[str, Any]:
    if not isinstance(path, str) or not path.startswith("/"):
        raise HTTPException(status_code=404, detail="Not found")

    for route_index, route_config in enumerate(extension.config.ui_routes):
        route_path = _wasm_extension_ui_route_path(extension, route_config.path)
        route_params = _path_template_params(route_path, path)
        if route_params is None:
            continue

        return {
            "frame_path": f"/ext-frame/{extension.id}/{route_index}",
            "auth": _wasm_extension_route_auth(extension, route_config.auth),
            "path_params": route_config.path_params,
            "route_params": route_params,
        }

    raise HTTPException(status_code=404, detail="Not found")


def _path_template_params(template: str, path: str) -> dict[str, str] | None:
    template_parts = _path_parts(template)
    path_parts = _path_parts(path)
    if len(template_parts) != len(path_parts):
        return None

    params: dict[str, str] = {}
    for template_part, path_part in zip(template_parts, path_parts, strict=False):
        if template_part.startswith("{") and template_part.endswith("}"):
            param_name = template_part[1:-1]
            if not param_name:
                return None
            params[param_name] = path_part
            continue

        if template_part != path_part:
            return None

    return params


def _path_parts(path: str) -> list[str]:
    return [part for part in path.strip("/").split("/") if part]


def _wasm_extension_frame_config(
    extension: WasmExtension,
    frame_path: str,
    auth: str,
    path_params: dict[str, str],
    route_params: dict[str, str],
    query: dict[str, Any],
    user_id: str | None,
    permissions: set[str],
) -> dict[str, Any]:
    public = auth == "public"
    return {
        "extension": {
            "id": extension.id,
            "name": extension.name,
        },
        "frameUrl": wasm_extension_frame_url(extension, frame_path, user_id),
        "bridge": {
            "extensionId": extension.id,
            "public": public,
            "routeParams": _map_wasm_extension_route_params(route_params, path_params),
            "query": query,
            "permissions": sorted(permissions),
            "apiRoutes": _wasm_extension_bridge_api_routes(extension, public),
        },
    }


async def _wasm_extension_granted_permission_ids(
    extension: WasmExtension,
) -> set[str]:
    installed_extension = await get_installed_extension(extension.id)
    if not installed_extension:
        return set()
    return {permission.id for permission in installed_extension.permissions}


def _map_wasm_extension_route_params(
    route_params: dict[str, str],
    path_params: dict[str, str],
) -> dict[str, str]:
    payload: dict[str, str] = {}
    for key, value in route_params.items():
        target = path_params.get(key) or _snake_to_camel(key)
        payload[target] = value
    return payload


def _read_wasm_extension_route_query(query: Any) -> dict[str, Any]:
    if not isinstance(query, dict):
        return {}

    payload: dict[str, Any] = {}
    for key, value in query.items():
        if value is None:
            continue
        payload[_snake_to_camel(str(key))] = value
    return payload


async def _optional_wasm_user_id(
    request: Request,
    access_token: Annotated[str | None, Depends(check_access_token)],
    usr: UUID4 | None = None,
) -> str | None:
    try:
        return await optional_user_id(request, access_token, usr)
    except HTTPException:
        return None


def _wasm_extension_ui_route_path(extension: WasmExtension, path: Any) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError(f"Invalid route path for WASM extension '{extension.id}'.")
    if path == "/":
        return "/ext"
    return f"/ext{path}"


def _wasm_extension_entrypoint(extension: WasmExtension, entrypoint: Any) -> Path:
    if not isinstance(entrypoint, str) or not entrypoint:
        raise ValueError(
            f"Invalid route entrypoint for WASM extension '{extension.id}'."
        )
    if entrypoint.startswith("/"):
        raise ValueError(
            f"Route entrypoint for WASM extension '{extension.id}' must be a "
            "relative extension path."
        )

    path = (extension.root_path / entrypoint).resolve()
    root_path = extension.root_path.resolve()
    if path != root_path and root_path not in path.parents:
        raise ValueError(f"Route entrypoint escapes extension root: {entrypoint}")

    static_path = (extension.root_path / "static").resolve()
    if path == static_path or static_path in path.parents:
        raise ValueError(
            f"Route entrypoint for WASM extension '{extension.id}' must not be "
            "inside the static asset directory."
        )
    if path.suffix.lower() != ".html":
        raise ValueError(
            f"Route entrypoint for WASM extension '{extension.id}' must be "
            "an HTML file."
        )
    if not path.is_file():
        raise FileNotFoundError(f"Route entrypoint not found: {path}")
    return path
