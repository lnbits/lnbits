from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.staticfiles import PathLike as StaticFilesPathLike
from starlette.types import Scope

from lnbits.settings import settings

from ..wasm.loader import WasmExtension

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


def mount_wasm_extension_static(app: FastAPI, extension: WasmExtension) -> None:
    static_path = extension.root_path / "static"

    mount_path = f"/ext-assets/{extension.id}"
    if any(getattr(route, "path", None) == mount_path for route in app.routes):
        return

    app.mount(
        mount_path,
        GuardedWasmExtensionStaticFiles(directory=static_path, check_dir=False),
        name=f"{extension.id}-static",
    )


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
