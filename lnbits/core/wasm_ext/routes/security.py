from __future__ import annotations

from typing import Any, NoReturn
from uuid import uuid4

from fastapi import HTTPException, Request
from loguru import logger

from lnbits.helpers import template_renderer
from lnbits.utils.cache import cache

from ..wasm.loader import WasmExtension

WASM_FRAME_TOKEN_EXPIRY_SECONDS = 60


def wasm_extension_wrapper_response(
    request: Request,
    extension: WasmExtension,
    auth: str,
    user_json: str | None,
) -> Any:
    public = auth == "public"
    response = template_renderer().TemplateResponse(
        request,
        "wasm_extension.html",
        {
            "extension": extension,
            "public": public,
            "user": user_json,
        },
    )
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


def wasm_extension_frame_csp(request: Request, extension: WasmExtension) -> str:
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


def wasm_extension_frame_url(
    extension: WasmExtension, frame_path: str, user_id: str | None
) -> str:
    token = _create_wasm_extension_frame_token(extension, frame_path, user_id)
    return f"{frame_path}?frame_token={token}"


def consume_wasm_extension_frame_token(
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
