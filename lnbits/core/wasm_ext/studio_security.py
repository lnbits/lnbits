from __future__ import annotations

import re
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from lnbits.core.crud.users import get_account
from lnbits.decorators import check_account_exists, check_admin
from lnbits.utils.cache import cache

from .runtime import WasmStudioContext, get_wasm_studio_context


class WasmStudioMiddleware:
    """Protect every draft surface, including public routes and websocket upgrades."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        root_path = scope.get("root_path", "")
        if root_path and path.startswith(root_path + "/"):
            path = path[len(root_path) :]
        match = re.match(
            r"^/(?:ext|ext-frame|ext-assets|api/v1/ext/ws|api/v1/ext|api/v1/extension)"
            r"/([^/]+)(?:/|$)",
            path,
        )
        studio = get_wasm_studio_context(match[1]) if match else None
        if studio and scope["type"] in {"http", "websocket"}:
            try:
                if path.startswith("/ext-assets/"):
                    # Sandboxed frames have an opaque origin: their subresources
                    # use an admin-issued, read-only asset capability, not cookies.
                    parts = path.split("/")
                    await check_studio_asset_token(
                        parts[3] if len(parts) > 3 else "", studio
                    )
                else:
                    request = Request(
                        {**scope, "type": "http", "method": scope.get("method", "GET")}
                    )
                    authorization = request.headers.get("authorization", "")
                    token = (
                        authorization[7:]
                        if authorization.lower().startswith("bearer ")
                        else request.cookies.get("cookie_access_token")
                    )
                    account = await check_account_exists(request, token)
                    await check_admin(account)
                    scope["user_id"] = account.id
            except HTTPException as exc:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    response = JSONResponse(
                        {"detail": exc.detail}, status_code=exc.status_code
                    )
                    await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def studio_asset_token(studio: WasmStudioContext, user_id: str) -> str:
    token = uuid4().hex + uuid4().hex
    cache.set(
        f"wasm-studio-assets:{token}",
        {"extension_id": studio.extension.id, "user_id": user_id},
        expiry=3600,
    )
    return token


async def check_studio_asset_token(token: str, studio: WasmStudioContext) -> None:
    grant = cache.get(f"wasm-studio-assets:{token}")
    if not isinstance(grant, dict) or grant.get("extension_id") != studio.extension.id:
        raise HTTPException(404, "Not found")
    user_id = grant.get("user_id")
    if not isinstance(user_id, str):
        raise HTTPException(404, "Not found")
    account = await get_account(user_id)
    if not account or not account.activated:
        raise HTTPException(404, "Not found")
    await check_admin(account)


def studio_asset_prefix(studio: WasmStudioContext, token: str) -> str:
    return f"/ext-assets/{studio.extension.id}/{token}/"


def rewrite_studio_urls(content: str, studio: WasmStudioContext, token: str) -> str:
    """Rebase served files; keep the editable source copy byte-for-byte intact."""
    source = re.escape(studio.source_id)
    draft_id = studio.extension.id
    content = re.sub(
        rf"/ext-assets/(?:{source}|{re.escape(draft_id)})/",
        studio_asset_prefix(studio, token),
        content,
    )
    for prefix in ("/api/v1/ext/ws/", "/api/v1/ext/", "/api/v1/extension/", "/ext/"):
        content = re.sub(
            re.escape(prefix) + source + r"(?=$|[^A-Za-z0-9_-])",
            prefix + draft_id,
            content,
        )
    return content
