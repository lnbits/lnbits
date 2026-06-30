from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Annotated, Any, NoReturn
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import UUID4
from starlette.staticfiles import PathLike as StaticFilesPathLike
from starlette.types import Scope

from lnbits.core.db import core_app_extra
from lnbits.core.models import Account
from lnbits.decorators import (
    check_access_token,
    check_account_exists,
    optional_user_id,
)
from lnbits.helpers import template_renderer
from lnbits.settings import settings
from lnbits.utils.cache import cache

from .loader import WasmExtension, load_wasm_extension

WASM_FRAME_TOKEN_EXPIRY_SECONDS = 60
WASM_EXTENSION_CORE_ASSET_PREFIX = "_lnbits"
WASM_EXTENSION_CORE_STATIC_ASSETS = {
    "bundle.min.css": ("static/bundle.min.css", "text/css; charset=utf-8"),
    "material-icons-v50.woff2": (
        "static/fonts/material-icons-v50.woff2",
        "font/woff2",
    ),
    "quasar.css": ("static/vendor/quasar.css", "text/css; charset=utf-8"),
    "quasar.umd.prod.js": (
        "static/vendor/quasar.umd.prod.js",
        "text/javascript; charset=utf-8",
    ),
    "qrcode.vue.browser.js": (
        "static/vendor/qrcode.vue.browser.js",
        "text/javascript; charset=utf-8",
    ),
    "vue.global.prod.js": (
        "static/vendor/vue.global.prod.js",
        "text/javascript; charset=utf-8",
    ),
}
WASM_EXTENSION_GENERATED_CORE_ASSETS = {
    "material-icons.css": (
        """
        @font-face {
          font-family: 'Material Icons';
          font-style: normal;
          font-weight: 400;
          src: url('./material-icons-v50.woff2') format('woff2');
        }
        """,
        "text/css; charset=utf-8",
    )
}
WASM_EXTENSION_STATIC_MIME_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript; charset=utf-8",
    ".png": "image/png",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}
WASM_EXTENSION_TEXT_STATIC_EXTENSIONS = {".css", ".js"}
WASM_EXTENSION_HTML_PREFIXES = (b"<!doctype", b"<html", b"<script")


class GuardedWasmExtensionStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        if path.startswith(f"{WASM_EXTENSION_CORE_ASSET_PREFIX}/"):
            return _wasm_extension_core_asset_response(path)
        if Path(path).suffix.lower() not in WASM_EXTENSION_STATIC_MIME_TYPES:
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)

    def file_response(
        self,
        full_path: StaticFilesPathLike,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        suffix = Path(full_path).suffix.lower()
        if suffix in WASM_EXTENSION_TEXT_STATIC_EXTENSIONS:
            _reject_html_like_wasm_static_asset(Path(full_path))

        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Content-Type"] = WASM_EXTENSION_STATIC_MIME_TYPES[suffix]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response


def register_wasm_extension(app: FastAPI, ext_id: str) -> WasmExtension:
    loaded = load_wasm_extension(ext_id)
    from .wasm import warm_wasm_extension

    warm_wasm_extension(loaded)
    _mount_wasm_extension_static(app, loaded)
    _register_wasm_extension_ui_routes(app, loaded)
    _register_wasm_extension_api_routes(app, loaded)

    core_app_extra.wasm_extension_registry.register(loaded)

    settings.activate_extension_paths(ext_id, "", [])
    logger.info(
        f"Loaded WASM extension '{loaded.id}' "
        f"({loaded.module_path.stat().st_size} bytes)."
    )
    return loaded


def _mount_wasm_extension_static(app: FastAPI, extension: WasmExtension) -> None:
    static_path = extension.root_path / "static"

    mount_path = f"/ext-assets/{extension.id}"
    if any(getattr(route, "path", None) == mount_path for route in app.routes):
        return

    app.mount(
        mount_path,
        GuardedWasmExtensionStaticFiles(directory=static_path, check_dir=False),
        name=f"{extension.id}-static",
    )


def _register_wasm_extension_ui_routes(app: FastAPI, extension: WasmExtension) -> None:
    for route_index, route_config in enumerate(extension.config.get("ui_routes") or []):
        route_path = _wasm_extension_ui_route_path(extension, route_config.get("path"))
        entrypoint = _wasm_extension_entrypoint(
            extension, route_config.get("entrypoint")
        )
        frame_path = f"/ext-frame/{extension.id}/{route_index}"
        auth = _wasm_extension_route_auth(extension, route_config.get("auth"))
        path_params = route_config.get("path_params") or {}
        _add_wasm_extension_frame_route(app, extension, frame_path, entrypoint)
        _add_wasm_extension_wrapper_route(
            app,
            extension,
            route_path,
            frame_path,
            auth,
            path_params,
        )


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
    auth = _wasm_extension_route_auth(extension, route_config.get("auth"))

    if _has_route(app, route_path, method):
        return

    async def invoke_wasm_api_request(
        request: Request, account: Account | None = None
    ) -> dict[str, Any]:
        from .wasm import invoke_wasm_extension_export as invoke_wasm_export

        try:
            payload = await _read_api_payload(request, path_params)
            return await invoke_wasm_export(
                extension.id,
                export_name,
                payload,
                user=account,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def invoke_private_wasm_extension_export(
        request: Request,
        account: Account = Depends(check_account_exists),
    ) -> dict[str, Any]:
        return await invoke_wasm_api_request(request, account)

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


def _add_wasm_extension_wrapper_route(
    app: FastAPI,
    extension: WasmExtension,
    route_path: str,
    frame_path: str,
    auth: str,
    path_params: dict[str, str],
) -> None:
    if _has_route(app, route_path, "GET"):
        return

    async def serve_private_wasm_extension_page(
        request: Request,
        account: Account = Depends(check_account_exists),
    ) -> Any:
        return _wasm_extension_wrapper_response(
            request,
            extension,
            frame_path,
            auth,
            path_params,
            None,
            account.id,
        )

    async def serve_public_wasm_extension_page(
        request: Request,
        user_id: str | None = Depends(_optional_wasm_user_id),
    ) -> Any:
        return _wasm_extension_wrapper_response(
            request,
            extension,
            frame_path,
            auth,
            path_params,
            None,
            user_id,
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
        _consume_wasm_extension_frame_token(request, extension, frame_path, user_id)
        response = FileResponse(entrypoint)
        response.headers["Content-Security-Policy"] = _wasm_extension_frame_csp(
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


def _wasm_extension_wrapper_response(
    request: Request,
    extension: WasmExtension,
    frame_path: str,
    auth: str,
    path_params: dict[str, str],
    user_json: str | None,
    user_id: str | None,
) -> Any:
    public = auth == "public"
    response = template_renderer().TemplateResponse(
        request,
        "wasm_extension.html",
        {
            "extension": extension,
            "frame_url": _wasm_extension_frame_url(extension, frame_path, user_id),
            "bridge": {
                "extensionId": extension.id,
                "public": public,
                "routeParams": _read_api_path_params(request, path_params),
                "query": _read_api_query_params(request),
                "apiRoutes": _wasm_extension_bridge_api_routes(extension, public),
            },
            "public": public,
            "user": user_json,
        },
    )
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


def _wasm_extension_frame_csp(request: Request, extension: WasmExtension) -> str:
    origin = str(request.base_url).rstrip("/")
    extension_assets = f"{origin}/ext-assets/{extension.id}/"
    return (
        "sandbox allow-scripts; "
        "default-src 'none'; "
        f"script-src {extension_assets}; "
        "script-src-attr 'none'; "
        f"style-src {extension_assets}; "
        "style-src-attr 'none'; "
        f"img-src {extension_assets} data:; "
        f"font-src {extension_assets}; "
        "connect-src 'none'; "
        "form-action 'none'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "frame-src 'none'; "
        "worker-src 'none'; "
        "media-src 'none'; "
        "manifest-src 'none'; "
        "frame-ancestors 'self'"
    )


def _wasm_extension_frame_url(
    extension: WasmExtension, frame_path: str, user_id: str | None
) -> str:
    token = _create_wasm_extension_frame_token(extension, frame_path, user_id)
    return f"{frame_path}?frame_token={token}"


def _create_wasm_extension_frame_token(
    extension: WasmExtension,
    frame_path: str,
    user_id: str | None,
) -> str:
    token = uuid4().hex
    cache.set(
        _wasm_extension_frame_token_cache_key(token),
        {
            "extension_id": extension.id,
            "frame_path": frame_path,
            "user_id": user_id,
        },
        expiry=WASM_FRAME_TOKEN_EXPIRY_SECONDS,
    )
    return token


def _consume_wasm_extension_frame_token(
    request: Request,
    extension: WasmExtension,
    frame_path: str,
    user_id: str | None,
) -> None:
    token = request.query_params.get("frame_token")
    if not token:
        _raise_wasm_extension_frame_not_found(extension, frame_path, "missing")

    cache_key = _wasm_extension_frame_token_cache_key(token)
    token_data = cache.get(cache_key)
    if (
        not isinstance(token_data, dict)
        or token_data.get("extension_id") != extension.id
        or token_data.get("frame_path") != frame_path
    ):
        _raise_wasm_extension_frame_not_found(
            extension, frame_path, "unknown or expired"
        )

    token_user_id = token_data.get("user_id")
    if token_user_id and token_user_id != user_id:
        _raise_wasm_extension_frame_not_found(extension, frame_path, "wrong user")

    cache.pop(cache_key)


def _wasm_extension_frame_token_cache_key(token: str) -> str:
    return f"wasm-frame-token:{token}"


def _raise_wasm_extension_frame_not_found(
    extension: WasmExtension,
    frame_path: str,
    reason: str,
) -> NoReturn:
    logger.warning(
        f"WASM frame token {reason} for extension '{extension.id}' at '{frame_path}'."
    )
    raise HTTPException(status_code=404, detail="Not found")


def _wasm_extension_bridge_api_routes(
    extension: WasmExtension,
    public: bool,
) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    for route_config in extension.config.get("api_routes") or []:
        auth = _wasm_extension_route_auth(extension, route_config.get("auth"))
        if public and auth != "public":
            continue
        method = _wasm_extension_api_method(extension, route_config.get("method"))
        path = _wasm_extension_api_path(extension, route_config.get("path"))
        _wasm_extension_api_export(extension, route_config.get("export"))
        routes.append(
            {
                "method": method,
                "path": path,
                "pattern": _path_template_pattern(path),
            }
        )
    return routes


def _path_template_pattern(path: str) -> str:
    pattern = re.sub(r"\\{[^/{}]+\\}", r"[^/]+", re.escape(path))
    return f"^{pattern}$"


async def _optional_wasm_user_id(
    request: Request,
    access_token: Annotated[str | None, Depends(check_access_token)],
    usr: UUID4 | None = None,
) -> str | None:
    try:
        return await optional_user_id(request, access_token, usr)
    except HTTPException:
        return None


def _wasm_extension_route_auth(extension: WasmExtension, auth: Any) -> str:
    if auth in {"public", "user"}:
        return auth
    raise ValueError(f"Invalid route auth for WASM extension '{extension.id}'.")


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


def _reject_html_like_wasm_static_asset(path: Path) -> None:
    with path.open("rb") as asset_file:
        prefix = asset_file.read(512).lstrip().lower()
    if prefix.startswith(WASM_EXTENSION_HTML_PREFIXES):
        raise HTTPException(status_code=404)


def _wasm_extension_core_asset_response(path: str) -> Response:
    asset_name = path.removeprefix(f"{WASM_EXTENSION_CORE_ASSET_PREFIX}/")
    if not asset_name or "/" in asset_name or "\\" in asset_name:
        raise HTTPException(status_code=404)

    generated_asset = WASM_EXTENSION_GENERATED_CORE_ASSETS.get(asset_name)
    if generated_asset:
        content, content_type = generated_asset
        response = Response(content=content, media_type=content_type)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    asset_config = WASM_EXTENSION_CORE_STATIC_ASSETS.get(asset_name)
    if not asset_config:
        raise HTTPException(status_code=404)

    relative_path, content_type = asset_config
    asset_path = Path(settings.lnbits_path, relative_path)
    if not asset_path.is_file():
        raise HTTPException(status_code=404)

    response = FileResponse(asset_path)
    response.headers["Content-Type"] = content_type
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response
